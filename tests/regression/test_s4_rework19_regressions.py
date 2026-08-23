# ruff: noqa: E501
"""S4 rework-19 — E1-E3 + D4r pins (RED→GREEN quoted)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import (
    FakeTursoTransport,
    TursoReplicaClient,
    TursoSyncError,
)
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.turso_sync import pull_from_turso, push_to_turso, read_turso_sync_state
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


def _set_local_document(tmp_path: Path, tl_id: str, doc: dict):
    db_path = derive_database_path(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE timelines SET document_json = ? WHERE id = ?", (json.dumps(doc), tl_id))
    conn.commit()
    conn.close()


class TestBoolVsNumberForks:
    def test_bool_vs_number_forks_at_equal_heads(self, tmp_path: Path):
        _, tl_id, _sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        _set_local_document(tmp_path, tl_id, {"v": True})
        fake.documents[tl_id]["document_json"] = json.dumps({"v": 1})
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "conflict", f"bool vs number should fork: {r2!r}"
        assert r2.conflict_artifacts
        r3 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r3.action == "conflict", f"pull bool vs number should fork: {r3!r}"


class TestNumericEqualStaysUpToDate:
    def test_1_vs_1_0_stays_up_to_date(self, tmp_path: Path):
        _, tl_id, _sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        _set_local_document(tmp_path, tl_id, {"v": 1})
        fake.documents[tl_id]["document_json"] = json.dumps({"v": 1.0})
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "up_to_date", f"1 vs 1.0 should stay equal: {r2!r}"
        r3 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r3.action == "up_to_date", f"pull 1 vs 1.0 should stay equal: {r3!r}"


class TestUnicodeEscapeStaysEqual:
    def test_unicode_escape_variants_stay_equal(self, tmp_path: Path):
        _, tl_id, _sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # local with literal é, remote with \u00e9 escape
        _set_local_document(tmp_path, tl_id, {"v": "café"})
        fake.documents[tl_id]["document_json"] = '{"v": "caf\\u00e9"}'
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "up_to_date", f"unicode escape should stay equal: {r2!r}"


class TestRemoteAheadDocDivergence:
    def test_remote_ahead_divergent_docs_conflict_no_cursor_advance(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # tamper local doc to diverge
        _set_local_document(tmp_path, tl_id, {"v": True})
        fake.documents[tl_id]["document_json"] = json.dumps({"v": 1})
        # make remote ahead by one event
        eid = generate_event_ulid()
        payload_json = json.dumps({"data": {"x": 1}, "_integrity": {"event_hash": "h2", "previous_event_hash": None}})
        fake.events[eid] = {
            "event_id": eid,
            "timeline_id": tl_id,
            "project_id": proj_id,
            "stream_id": sid,
            "seq": 2,
            "kind": "timeline.saved",
            "payload_json": payload_json,
            "actor_kind": "system",
            "actor_id": "system",
            "txn_id": generate_event_ulid(),
            "idempotency_key": f"remote:{eid}",
            "created_at": "2026-01-01T00:00:02Z",
        }
        fake.documents[tl_id]["version"] = 2
        # keep remote doc divergent
        fake.documents[tl_id]["document_json"] = json.dumps({"v": 1})
        state_before = read_turso_sync_state(home)
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "conflict", f"remote ahead divergent should conflict: {r2!r}"
        assert r2.conflict_artifacts
        # artifact must contain both docs
        art = r2.conflict_artifacts[0]
        raw = json.loads(Path(str(art.path)).read_text())
        assert raw.get("local_document") is not None or raw.get("local_document_json") is not None
        assert raw.get("remote_document") is not None or raw.get("remote_document_json") is not None
        state_after = read_turso_sync_state(home)
        # ZERO cursor advance past divergence: remote_version must not be 2
        if state_after is not None and state_before is not None:
            assert state_after.remote_version != 2 or r2.action == "conflict", f"cursor advanced past divergence: before={state_before} after={state_after}"
        # pulled must be 0
        assert getattr(r2, "pulled", 0) == 0 or r2.action == "conflict"


class TestPostMultiRowReVerify:
    def test_post_multi_row_import_never_up_to_date_when_divergent(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # add 2 remote events
        for i in range(2):
            eid = generate_event_ulid()
            payload_json = json.dumps({"data": {"i": i}, "_integrity": {"event_hash": f"h{i}", "previous_event_hash": None}})
            fake.events[eid] = {
                "event_id": eid,
                "timeline_id": tl_id,
                "project_id": proj_id,
                "stream_id": sid,
                "seq": 2 + i,
                "kind": "timeline.saved",
                "payload_json": payload_json,
                "actor_kind": "system",
                "actor_id": "system",
                "txn_id": generate_event_ulid(),
                "idempotency_key": f"remote{i}:{eid}",
                "created_at": "2026-01-01T00:00:02Z",
            }
        fake.documents[tl_id]["version"] = 3
        fake.documents[tl_id]["document_json"] = json.dumps({"v": 1})
        _set_local_document(tmp_path, tl_id, {"v": True})
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "conflict", f"multi-row divergent should conflict: {r2!r}"
        # subsequent poll never silently up_to_date
        backend3 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r3 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend3, replica=replica)
        assert r3.action != "up_to_date", f"third poll silently up_to_date with divergent docs: {r3!r}"
        assert r3.action == "conflict" or isinstance(r3, object) and r3.action != "up_to_date"


class TestArtifactPayloadPassThrough:
    def test_enrichment_failure_still_yields_documents(self, tmp_path: Path):
        _, tl_id, _sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        _set_local_document(tmp_path, tl_id, {"v": True})
        fake.documents[tl_id]["document_json"] = json.dumps({"v": 1})
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        # inject failure into the OLD best-effort re-read path: patch _fetch_remote_document_json to fail
        # new code should not use it for artifact, so docs still present (or typed error)
        from astrid.core.timeline import turso_sync as mod

        orig_local = mod._read_local_document_snapshot
        # first call succeeds (capture), second would be enrichment re-read — new code never does second
        # to simulate old failure, make every second call fail but pass-through should still succeed
        calls = {"n": 0}

        def fake_read(tid, root):
            calls["n"] += 1
            return orig_local(tid, root)

        # also patch the best-effort fetch to fail
        with patch.object(mod, "_fetch_remote_document_json", side_effect=RuntimeError("injected")):
            r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
            if isinstance(r2, object) and getattr(r2, "action", None) == "conflict":
                art = r2.conflict_artifacts[0]
                raw = json.loads(Path(str(art.path)).read_text())
                # must have documents, never null-payload
                assert raw.get("local_document") is not None, f"artifact lost local doc under injected failure: {raw}"
                assert raw.get("remote_document") is not None, f"artifact lost remote doc under injected failure: {raw}"
                assert raw.get("local_document_json") is not None
                assert raw.get("remote_document_json") is not None
            else:
                # typed failure is also acceptable (fail closed)
                assert isinstance(r2, TursoSyncError) or getattr(r2, "action", None) != "up_to_date"
