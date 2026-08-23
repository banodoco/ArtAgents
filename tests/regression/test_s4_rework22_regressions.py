# ruff: noqa: E501, F401, F841, F811, I001, BLE001
"""S4 rework-22 — stale-bookmark seam fall-through eliminates dishonest up_to_date."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import FakeTursoTransport, TursoReplicaClient
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.sync_state import HeadSnapshot
from astrid.core.timeline.turso_sync import (
    _heads_provenance_equivalent,
    _verify_doc_identity_or_fork,
    pull_from_turso,
    push_to_turso,
)
from astrid.packs import build_standard_registry, open_standard_writer


def _make_local_db(tmp_path: Path, project_slug: str = "proj"):
    from astrid.core.events.service import EventAppendService
    from astrid.core.store.uow import UnitOfWork

    registry = build_standard_registry()
    db_path = derive_database_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer = open_standard_writer(db_path, registry=registry)
    proj_id = uuid.uuid4().hex
    tl_id = uuid.uuid4().hex
    ulid = "01J000000000000000000000AA"
    sid = f"{tl_id}:timeline.timeline"

    def _setup(uow: UnitOfWork):
        uow.execute(
            "INSERT INTO projects (id, slug, name, settings_json, event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (proj_id, project_slug, "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO event_streams (id, project_id, stream_type, aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)",
            (sid, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO timelines (id, project_id, event_stream_id, name, document_json, asset_registry_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tl_id, proj_id, sid, "T1", json.dumps({"tracks": []}), json.dumps({}), "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )

    UnitOfWork(writer).run(_setup)
    svc = EventAppendService(registry)

    def _append(uow: UnitOfWork):
        svc.append(uow, stream_id=sid, project_id=proj_id, event_kind="timeline.created", data={"timeline_id": tl_id, "timeline_ulid": ulid, "slug": "t1", "name": "T1"}, changes=["timeline_id", "slug", "name"], idempotency_key=f"create:{tl_id}", txn_id=generate_event_ulid(), actor_kind="system", event_id=generate_event_ulid())

    UnitOfWork(writer).run(_append)
    writer.close()
    home = tmp_path / project_slug / "timelines" / ulid
    home.mkdir(parents=True, exist_ok=True)
    from astrid.packs.timeline.backfill import write_backfill_state

    write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=1, events_sha256="abc")
    return proj_id, tl_id, sid, home


class TestStateWriteFailureRetryConflictsAtRetry:
    """Pin 1: state-write failure retry ⇒ conflict+artifact at the retry itself."""

    def test_state_write_failure_retry_conflicts_at_retry(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        # initial push to establish bookmark at v1
        res0 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert res0.action in ("pushed", "up_to_date")
        # make local doc diverge to offline (stale local)
        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE timelines SET document_json = ? WHERE id = ?", (json.dumps({"mode": "offline"}), tl_id))
        conn.commit()
        conn.close()
        # inject one remote event ahead and set remote doc to cloud
        remote_eid = generate_event_ulid()
        payload_json = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "hash-remote-" + remote_eid[:6], "previous_event_hash": None}})
        # fetch current seq for remote
        fake.events[remote_eid] = {
            "event_id": remote_eid,
            "timeline_id": tl_id,
            "project_id": proj_id,
            "stream_id": sid,
            "seq": 2,
            "kind": "timeline.saved",
            "payload_json": payload_json,
            "actor_kind": "system",
            "actor_id": "system",
            "txn_id": generate_event_ulid(),
            "idempotency_key": f"remote:{remote_eid}",
            "created_at": "2026-01-01T00:00:02Z",
        }
        fake.documents[tl_id]["document_json"] = json.dumps({"mode": "cloud"})
        fake.documents[tl_id]["version"] = 2
        fake.documents[tl_id]["last_event_id"] = remote_eid
        fake.documents[tl_id]["updated_at"] = "2026-01-01T00:00:02Z"

        import astrid.core.timeline.turso_sync as sync_mod

        orig = sync_mod._write_state_typed
        calls = {"n": 0}

        def _failing(timeline_home, state):
            if calls["n"] == 0:
                calls["n"] += 1
                raise OSError("injected OSError for state write")
            return orig(timeline_home, state)

        # first pull should import but fail on state write
        with patch.object(sync_mod, "_write_state_typed", side_effect=_failing):
            try:
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
                assert False, "first pull must raise OSError (state write failure)"
            except OSError as exc:
                assert "injected" in str(exc)
                assert calls["n"] == 1

        # verify local now has imported event, heads provenance-equivalent, bookmark stale
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        # local doc still offline, remote cloud
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT document_json FROM timelines WHERE id = ?", (tl_id,)).fetchone()
        conn.close()
        assert json.loads(row[0]) == {"mode": "offline"}
        assert json.loads(fake.documents[tl_id]["document_json"]) == {"mode": "cloud"}

        result_retry = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert result_retry.action == "conflict", f"retry must be conflict, got {result_retry.action} pulled={result_retry.pulled} artifacts={len(result_retry.conflict_artifacts or [])}"
        assert result_retry.conflict_artifacts, "conflict must have artifact"
        # should not have produced a second late conflict; first retry already honest


class TestDirectSeamStaleBookmarkForcesConflict:
    """Pin 2: direct seam call with stale bookmark + provenance-equivalent heads + unequal docs ⇒ conflict."""

    def test_direct_seam_stale_bookmark_unequal_forks(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        # diverge docs: local offline, remote cloud
        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE timelines SET document_json = ? WHERE id = ?", (json.dumps({"mode": "offline"}), tl_id))
        conn.commit()
        conn.close()
        fake.documents[tl_id]["document_json"] = json.dumps({"mode": "cloud"})
        # inject remote event and import locally to make heads provenance-equivalent at v2
        remote_eid = generate_event_ulid()
        payload_json = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "hash-seam-" + remote_eid[:6], "previous_event_hash": None}})
        fake.events[remote_eid] = {
            "event_id": remote_eid,
            "timeline_id": tl_id,
            "project_id": proj_id,
            "stream_id": sid,
            "seq": 2,
            "kind": "timeline.saved",
            "payload_json": payload_json,
            "actor_kind": "system",
            "actor_id": "system",
            "txn_id": generate_event_ulid(),
            "idempotency_key": f"remote:{remote_eid}",
            "created_at": "2026-01-01T00:00:02Z",
        }
        fake.documents[tl_id]["version"] = 2
        fake.documents[tl_id]["last_event_id"] = remote_eid
        # pull will import and normally would conflict at retry if stale; we bypass by directly faking a failed state write
        import astrid.core.timeline.turso_sync as sync_mod

        orig = sync_mod._write_state_typed

        def _fail_once(timeline_home, state):
            # fail once to keep bookmark stale at v1
            if not hasattr(_fail_once, "_called"):
                _fail_once._called = True
                raise OSError("stale seam injection")
            return orig(timeline_home, state)

        with patch.object(sync_mod, "_write_state_typed", side_effect=_fail_once):
            try:
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
            except OSError:
                pass

        # now heads are provenance-equivalent at v2, bookmark stale at v1, docs unequal
        backend3 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        from astrid.core.timeline.turso_sync import read_turso_sync_state

        state = read_turso_sync_state(home)
        # ensure bookmark is stale (not at v2)
        assert state is not None
        # stale check: bookmark version < head version
        local_head = HeadSnapshot.from_eventlog_head(backend3.head())
        remote_head = HeadSnapshot(version=int(fake.documents[tl_id]["version"]), last_event_id=remote_eid, last_hash="hash-seam-" + remote_eid[:6])
        assert local_head.version == 2
        assert remote_head.version == 2
        assert state.local_version == 1 or state.remote_version == 1, f"bookmark must be stale, got {state}"
        # provenance must be equivalent
        assert _heads_provenance_equivalent(tl_id, local_head, remote_head, backend3, tmp_path) is True
        # direct seam call must be conflict
        from astrid.core.timeline.sync_state import SyncBookmark

        bookmark = SyncBookmark(
            timeline_id=tl_id,
            spoke="local",
            spoke_version=state.local_version,
            spoke_event_id=state.local_event_id,
            spoke_hash=state.local_hash,
            hub_version=state.remote_version,
            hub_event_id=state.remote_event_id,
            hub_hash=state.remote_hash,
            synced_at="2026-01-01T00:00:00Z",
        )
        result = _verify_doc_identity_or_fork(timeline_id=tl_id, timeline_home=home, root=tmp_path, replica=replica, local_head=local_head, remote_head=remote_head, backend=backend3, bookmark=bookmark)
        assert result is not None, "stale bookmark + provenance-equivalent + unequal docs must fork (not None)"
        assert result.action == "conflict"
        assert result.conflict_artifacts


class TestAlignedBookmarkControlStillConflicts:
    """Pin 3: aligned-bookmark unequal-docs control STILL conflicts."""

    def test_aligned_bookmark_unequal_still_conflicts(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        # diverge after aligned bookmark: local offline, remote cloud, no extra events (equal heads at v1)
        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE timelines SET document_json = ? WHERE id = ?", (json.dumps({"mode": "offline"}), tl_id))
        conn.commit()
        conn.close()
        fake.documents[tl_id]["document_json"] = json.dumps({"mode": "cloud"})
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        local_head = HeadSnapshot.from_eventlog_head(backend2.head())
        remote_head = HeadSnapshot(version=local_head.version, last_event_id=local_head.last_event_id, last_hash=local_head.last_hash)
        # bookmark is aligned at v1
        from astrid.core.timeline.turso_sync import read_turso_sync_state
        from astrid.core.timeline.sync_state import SyncBookmark

        state = read_turso_sync_state(home)
        assert state is not None
        assert state.local_version == local_head.version
        assert state.remote_version == remote_head.version
        assert _heads_provenance_equivalent(tl_id, local_head, remote_head, backend2, tmp_path) is True
        bookmark = SyncBookmark(timeline_id=tl_id, spoke="local", spoke_version=state.local_version, spoke_event_id=state.local_event_id, spoke_hash=state.local_hash, hub_version=state.remote_version, hub_event_id=state.remote_event_id, hub_hash=state.remote_hash, synced_at="2026-01-01T00:00:00Z")
        result = _verify_doc_identity_or_fork(timeline_id=tl_id, timeline_home=home, root=tmp_path, replica=replica, local_head=local_head, remote_head=remote_head, backend=backend2, bookmark=bookmark)
        assert result is not None and result.action == "conflict"
        assert result.conflict_artifacts


class TestRevertShowsRed:
    """Pin 4 helper: targeted revert to 62309e84 semantics shows RED (up_to_date with zero artifacts)."""

    def test_revert_to_old_seam_returns_up_to_date(self, tmp_path: Path, monkeypatch):
        # This test documents the RED: with the old seam (final return None),
        # stale bookmark + unequal docs incorrectly returns None → pull is up_to_date.
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)

        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE timelines SET document_json = ? WHERE id = ?", (json.dumps({"mode": "offline"}), tl_id))
        conn.commit()
        conn.close()
        fake.documents[tl_id]["document_json"] = json.dumps({"mode": "cloud"})
        remote_eid = generate_event_ulid()
        payload_json = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "hash-red-" + remote_eid[:6], "previous_event_hash": None}})
        fake.events[remote_eid] = {
            "event_id": remote_eid,
            "timeline_id": tl_id,
            "project_id": proj_id,
            "stream_id": sid,
            "seq": 2,
            "kind": "timeline.saved",
            "payload_json": payload_json,
            "actor_kind": "system",
            "actor_id": "system",
            "txn_id": generate_event_ulid(),
            "idempotency_key": f"remote:{remote_eid}",
            "created_at": "2026-01-01T00:00:02Z",
        }
        fake.documents[tl_id]["version"] = 2
        fake.documents[tl_id]["last_event_id"] = remote_eid
        import astrid.core.timeline.turso_sync as sync_mod

        orig = sync_mod._write_state_typed

        def _fail_once(timeline_home, state):
            if not hasattr(_fail_once, "_called"):
                _fail_once._called = True
                raise OSError("red injection")
            return orig(timeline_home, state)

        with patch.object(sync_mod, "_write_state_typed", side_effect=_fail_once):
            try:
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
            except OSError:
                pass
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)

        def _old_verify(*, timeline_id, timeline_home, root, replica, local_head, remote_head, backend, bookmark):
            # reproduce 62309e84 semantics: stale bookmark ⇒ return None
            if not sync_mod._heads_provenance_equivalent(timeline_id, local_head, remote_head, backend, root):
                return None
            try:
                local_doc = sync_mod._read_local_document_snapshot(timeline_id, root)
            except Exception as exc:
                raise sync_mod.TursoSyncError(str(exc)) from exc
            local_doc_json = local_doc.document_json
            remote_doc_json = sync_mod._fetch_remote_document_json_strict(replica, timeline_id)
            if remote_doc_json is None:
                return None
            if sync_mod._documents_structurally_equal(local_doc_json, remote_doc_json):
                return None
            try:
                a = json.loads(local_doc_json)
                b = json.loads(remote_doc_json)
                type_mismatch = sync_mod._has_json_type_mismatch(a, b) if not sync_mod._contains_non_finite(a) and not sync_mod._contains_non_finite(b) else True
            except Exception:
                type_mismatch = True
            if type_mismatch:
                return sync_mod._doc_divergence_conflict_result(timeline_id=timeline_id, timeline_home=timeline_home, backend=backend, replica=replica, local_head=local_head, remote_head=remote_head, bookmark=bookmark, local_doc_json=local_doc_json, remote_doc_json=remote_doc_json)
            if bookmark is not None and bookmark.spoke_version == local_head.version and bookmark.hub_version == remote_head.version:
                return sync_mod._doc_divergence_conflict_result(timeline_id=timeline_id, timeline_home=timeline_home, backend=backend, replica=replica, local_head=local_head, remote_head=remote_head, bookmark=bookmark, local_doc_json=local_doc_json, remote_doc_json=remote_doc_json)
            if bookmark is None:
                return sync_mod._doc_divergence_conflict_result(timeline_id=timeline_id, timeline_home=timeline_home, backend=backend, replica=replica, local_head=local_head, remote_head=remote_head, bookmark=bookmark, local_doc_json=local_doc_json, remote_doc_json=remote_doc_json)
            return None

        with patch.object(sync_mod, "_verify_doc_identity_or_fork", side_effect=_old_verify):
            result_red = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
            assert result_red.action == "up_to_date", f"RED: old seam must return up_to_date, got {result_red.action}"
            assert not result_red.conflict_artifacts, "RED: old seam must have zero artifacts"
        # after restore, should be conflict
        result_green = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert result_green.action == "conflict"
        assert result_green.conflict_artifacts
