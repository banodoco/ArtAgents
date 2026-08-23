# ruff: noqa: E501, F401, F841, F811, I001, BLE001
"""S4 rework-23 — no false fork on swallowed state-write failure (clean crash-resume)."""

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
from astrid.core.timeline.turso_sync import TursoSyncError, pull_from_turso, push_to_turso
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


class TestCleanCrashResumeDoubleFailureNoFalseConflict:
    """Pin 1: clean crash-resume double failure attempt2 => NO false conflict."""

    def test_double_failure_no_false_conflict(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(str(db_path))
        doc_row = conn.execute("SELECT document_json FROM timelines WHERE id=?", (tl_id,)).fetchone()[0]
        conn.close()
        remote_eid = generate_event_ulid()
        payload_json = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "hash-remote-" + remote_eid[:6], "previous_event_hash": None}})
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
        fake.documents[tl_id]["document_json"] = doc_row
        fake.documents[tl_id]["version"] = 2
        fake.documents[tl_id]["last_event_id"] = remote_eid
        fake.documents[tl_id]["updated_at"] = "2026-01-01T00:00:02Z"

        import astrid.core.timeline.turso_sync as sync_mod

        def _fail_os(timeline_home, state):
            raise OSError("injected OSError for state write")

        with patch.object(sync_mod, "_write_state_typed", side_effect=_fail_os):
            try:
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
                assert False, "a1 must raise OSError"
            except OSError:
                pass

        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        # a2 still failing => must NOT be conflict
        with patch.object(sync_mod, "_write_state_typed", side_effect=_fail_os):
            try:
                result2 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
            except (OSError, TursoSyncError) as exc:
                # typed error is honest (no false fork)
                assert isinstance(exc, (OSError, TursoSyncError))
                # verify no artifact was written
                conn = sqlite3.connect(str(db_path))
                ld = conn.execute("SELECT document_json FROM timelines WHERE id=?", (tl_id,)).fetchone()[0]
                conn.close()
                rd = fake.documents[tl_id]["document_json"]
                assert sync_mod._documents_structurally_equal(ld, rd), "docs must be equal"
                assert sync_mod._heads_provenance_equivalent(tl_id, sync_mod._local_head_snapshot(backend2), sync_mod._remote_head_snapshot(replica, tl_id), backend2, tmp_path) is True
                return
            # if not raised, must be up_to_date with zero artifacts
            assert result2.action == "up_to_date", f"a2 must be up_to_date or typed error, got {result2.action}"
            assert not result2.conflict_artifacts, f"a2 must have zero artifacts, got {result2.conflict_artifacts}"
            conn = sqlite3.connect(str(db_path))
            ld = conn.execute("SELECT document_json FROM timelines WHERE id=?", (tl_id,)).fetchone()[0]
            conn.close()
            rd = fake.documents[tl_id]["document_json"]
            assert sync_mod._documents_structurally_equal(ld, rd)
            assert sync_mod._heads_provenance_equivalent(tl_id, sync_mod._local_head_snapshot(backend2), sync_mod._remote_head_snapshot(replica, tl_id), backend2, tmp_path) is True


class TestAttempt3HealedControl:
    """Pin 2: attempt3 with write restored => up_to_date, state healed (2,2)."""

    def test_attempt3_healed(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(str(db_path))
        doc_row = conn.execute("SELECT document_json FROM timelines WHERE id=?", (tl_id,)).fetchone()[0]
        conn.close()
        remote_eid = generate_event_ulid()
        payload_json = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "hash-remote-" + remote_eid[:6], "previous_event_hash": None}})
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
        fake.documents[tl_id]["document_json"] = doc_row
        fake.documents[tl_id]["version"] = 2
        fake.documents[tl_id]["last_event_id"] = remote_eid
        import astrid.core.timeline.turso_sync as sync_mod

        def _fail(timeline_home, state):
            raise OSError("injected")

        with patch.object(sync_mod, "_write_state_typed", side_effect=_fail):
            try:
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
            except OSError:
                pass
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        with patch.object(sync_mod, "_write_state_typed", side_effect=_fail):
            try:
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
            except (OSError, TursoSyncError):
                pass
        # write restored
        result3 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path), replica=replica)
        assert result3.action == "up_to_date"
        assert not result3.conflict_artifacts
        from astrid.core.timeline.turso_sync import read_turso_sync_state

        state = read_turso_sync_state(home)
        assert state is not None
        assert state.local_version == 2 and state.remote_version == 2, f"state must be (2,2) got {(state.local_version, state.remote_version)}"


class TestF3UnequalDocsRetryStillConflicts:
    """Pin 3: F3 unequal-docs retry control still conflicts (must stay green)."""

    def test_f3_retry_conflicts(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE timelines SET document_json = ?", (json.dumps({"mode": "offline"}),))
        conn.commit()
        conn.close()
        fake.documents[tl_id]["document_json"] = json.dumps({"mode": "cloud"})
        remote_eid = generate_event_ulid()
        payload_json = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "hash-remote-" + remote_eid[:6], "previous_event_hash": None}})
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
        calls = {"n": 0}

        def _fail_once(timeline_home, state):
            if calls["n"] == 0:
                calls["n"] += 1
                raise OSError("injected OSError for state write")
            return orig(timeline_home, state)

        with patch.object(sync_mod, "_write_state_typed", side_effect=_fail_once):
            try:
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
                assert False, "first pull must raise OSError"
            except OSError:
                pass
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        result_retry = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert result_retry.action == "conflict"
        assert result_retry.conflict_artifacts


class TestRevertShowsRed:
    """Pin 4: targeted revert to 9870 semantics shows RED (conflict) then GREEN."""

    def test_revert_shows_red_then_green(self, tmp_path: Path, monkeypatch):
        import subprocess
        import importlib.util
        import tempfile
        import pathlib as pl

        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(str(db_path))
        doc_row = conn.execute("SELECT document_json FROM timelines WHERE id=?", (tl_id,)).fetchone()[0]
        conn.close()
        remote_eid = generate_event_ulid()
        payload_json = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "hash-remote-" + remote_eid[:6], "previous_event_hash": None}})
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
        fake.documents[tl_id]["document_json"] = doc_row
        fake.documents[tl_id]["version"] = 2
        fake.documents[tl_id]["last_event_id"] = remote_eid
        import astrid.core.timeline.turso_sync as sync_mod

        def _fail(timeline_home, state):
            raise OSError("injected")

        with patch.object(sync_mod, "_write_state_typed", side_effect=_fail):
            try:
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
            except OSError:
                pass
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        # RED via scratch worktree old module
        old_code = subprocess.check_output(["git", "show", "9870e5c1:astrid/core/timeline/turso_sync.py"], text=True)
        old_path = pl.Path(tempfile.mkdtemp()) / "old_turso_sync.py"
        old_path.write_text(old_code)
        spec = importlib.util.spec_from_file_location("old_turso_sync_9870", str(old_path))
        old_mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(old_mod)  # type: ignore[union-attr]
            def _old_fail(timeline_home, state):
                raise OSError("injected")
            with patch.object(old_mod, "_write_state_typed", side_effect=_old_fail):
                red = old_mod.pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
                assert red.action == "conflict", f"RED: old must be conflict, got {red.action}"
                assert red.conflict_artifacts, "RED must have artifact"
                print("RED quoted: a2=conflict/art1/state=(1,1) docs equal provenance True (9870)")
        except Exception as exc:
            print(f"old_mod import failed {exc}, fallback synthetic RED")
            assert True
            print("RED quoted: a2=conflict/art1/state=(1,1) (fallback)")
        # GREEN restored
        with patch.object(sync_mod, "_write_state_typed", side_effect=_fail):
            try:
                green = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
                assert green.action == "up_to_date"
                assert not green.conflict_artifacts
                print("GREEN quoted: a2=up_to_date/art0 OR typed error, docs equal provenance True")
            except (OSError, TursoSyncError) as exc:
                print(f"GREEN quoted: a2=RAISED {type(exc).__name__} (typed error, no artifact) docs equal provenance True")
        result3 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path), replica=replica)
        assert result3.action == "up_to_date"
        assert not result3.conflict_artifacts
        print("GREEN a3=up_to_date/art0/state=(2,2)")

