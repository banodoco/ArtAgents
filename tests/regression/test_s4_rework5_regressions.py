"""S4 rework-5 — Q8/Q9/Q10 + SHOULD-FIX RED→GREEN."""
# ruff: noqa: E501
from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import (
    FakeTursoTransport,
    LibSqlHttpTransport,
    TursoConfigError,
    TursoDocumentRow,
    TursoEventRow,
    TursoReplicaClient,
)
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.turso_sync import TursoSyncError, push_to_turso


def _make_local_db(tmp_path: Path, project_slug: str = "proj"):
    from astrid.core.events.service import EventAppendService
    from astrid.core.store.uow import UnitOfWork
    from astrid.packs import build_standard_registry, open_standard_writer

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
        svc.append(
            uow,
            stream_id=sid,
            project_id=proj_id,
            event_kind="timeline.created",
            data={"timeline_id": tl_id, "timeline_ulid": ulid, "slug": "t1", "name": "T1"},
            changes=["timeline_id", "slug", "name"],
            idempotency_key=f"create:{tl_id}",
            txn_id=generate_event_ulid(),
            actor_kind="system",
            event_id=generate_event_ulid(),
        )

    UnitOfWork(writer).run(_append)
    writer.close()
    home = tmp_path / project_slug / "timelines" / ulid
    home.mkdir(parents=True, exist_ok=True)
    from astrid.packs.timeline.backfill import write_backfill_state

    write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=1, events_sha256="abc")
    return proj_id, tl_id, sid, home


def _append_events(tmp_path: Path, proj_id: str, tl_id: str, sid: str, n: int):
    from astrid.core.events.service import EventAppendService
    from astrid.core.store.uow import UnitOfWork
    from astrid.packs import build_standard_registry, open_standard_writer

    registry = build_standard_registry()
    db_path = derive_database_path(tmp_path)
    writer = open_standard_writer(db_path, registry=registry)
    svc = EventAppendService(registry)
    ids = []
    for _ in range(n):
        eid = generate_event_ulid()

        def _ap(uow: UnitOfWork, eid=eid):
            svc.append(
                uow,
                stream_id=sid,
                project_id=proj_id,
                event_kind="timeline.saved",
                data={"timeline_id": tl_id, "config": {"clips": [], "tracks": []}},
                changes=["config"],
                idempotency_key=f"ev:{eid}",
                txn_id=generate_event_ulid(),
                actor_kind="system",
                event_id=eid,
            )

        UnitOfWork(writer).run(_ap)
        ids.append(eid)
    writer.close()
    return ids


# ---------------------------------------------------------------------------
# Q8 — real sqlite FK cascade must not happen
# ---------------------------------------------------------------------------

class TestQ8RealSqliteNoCascade:
    def test_real_sqlite_two_pushes_both_events_preserved(self, tmp_path: Path):
        # Use REAL sqlite file with REAL S schema, FK ON, and real client SQL
        sql_path = Path("/workspace/goalmd-sqlite-20260822/repos/ArtAgents/packages/timeline-schema/sql/turso/0001_turso_replica_schema.sql")
        assert sql_path.exists(), "S schema file must exist"
        sql_text = sql_path.read_text()

        # Verify client emits ON CONFLICT not REPLACE (pre-condition after fix)
        replica_probe = TursoReplicaClient(FakeTursoTransport())
        doc_sql = replica_probe._document_upsert_sql()
        assert "ON CONFLICT" in doc_sql
        assert "OR REPLACE" not in doc_sql

        # Build a real-sqlite transport wrapping a file DB
        real_db = tmp_path / "real_turso.db"
        conn = sqlite3.connect(str(real_db))
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(sql_text)
        conn.commit()

        class RealSqliteTransport:
            def execute_batch(self, statements):
                cur = conn.cursor()
                cur.execute("BEGIN")
                try:
                    for s, p in statements:
                        cur.execute(s, p)
                    cur.execute("COMMIT")
                except Exception:
                    cur.execute("ROLLBACK")
                    raise

            def query(self, sql, params=()):
                cur = conn.cursor()
                cur.execute(sql, params)
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = cur.fetchall()
                return [dict(zip(cols, r)) for r in rows]

            def close(self):
                pass

        transport = RealSqliteTransport()
        replica = TursoReplicaClient(transport)

        tl_id = uuid.uuid4().hex
        proj_id = uuid.uuid4().hex
        sid = f"{tl_id}:timeline.timeline"
        doc1 = TursoDocumentRow(timeline_id=tl_id, project_id=proj_id, event_stream_id=sid, name="T1-v1", document_json=json.dumps({"tracks": []}), version=1, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:01Z")
        ev1 = TursoEventRow(event_id=generate_event_ulid(), timeline_id=tl_id, project_id=proj_id, stream_id=sid, seq=1, kind="timeline.saved", payload_json=json.dumps({"data": {}, "_integrity": {"event_hash": "h1"}}), actor_kind="system", actor_id="system", txn_id=generate_event_ulid(), idempotency_key=f"ik1-{tl_id}-1", created_at="2026-01-01T00:00:01Z")
        replica.push_timeline_updates(doc1, [ev1])

        # verify first push: 1 event present, FK ON
        conn2 = sqlite3.connect(str(real_db))
        conn2.execute("PRAGMA foreign_keys=ON")
        cnt1 = conn2.execute("SELECT COUNT(*) FROM events WHERE timeline_id=?", (tl_id,)).fetchone()[0]
        assert cnt1 == 1
        conn2.close()

        doc2 = TursoDocumentRow(timeline_id=tl_id, project_id=proj_id, event_stream_id=sid, name="T1-v2", document_json=json.dumps({"tracks": [{"id": "x"}]}), version=2, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:02Z")
        ev2 = TursoEventRow(event_id=generate_event_ulid(), timeline_id=tl_id, project_id=proj_id, stream_id=sid, seq=2, kind="timeline.saved", payload_json=json.dumps({"data": {}, "_integrity": {"event_hash": "h2"}}), actor_kind="system", actor_id="system", txn_id=generate_event_ulid(), idempotency_key=f"ik2-{tl_id}-2", created_at="2026-01-01T00:00:02Z")
        replica.push_timeline_updates(doc2, [ev2])

        conn3 = sqlite3.connect(str(real_db))
        conn3.execute("PRAGMA foreign_keys=ON")
        cnt2 = conn3.execute("SELECT COUNT(*) FROM events WHERE timeline_id=?", (tl_id,)).fetchone()[0]
        doc_row = conn3.execute("SELECT name, version FROM documents WHERE timeline_id=?", (tl_id,)).fetchone()
        conn3.close()
        conn.close()
        assert cnt2 == 2, f"cascade destroyed event: expected 2 got {cnt2} (OR REPLACE bug)"
        assert doc_row[0] == "T1-v2"
        assert doc_row[1] == 2


# ---------------------------------------------------------------------------
# Q9 — push both_advanced malformed remote rows -> skipped_rows
# ---------------------------------------------------------------------------

class TestQ9PushForkSkippedRows:
    def test_push_fork_malformed_remote_row_recorded(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        # initial push to create cursor and remote doc
        res = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert res.action == "pushed"
        # make remote diverge with 2 rows: one good, one malformed
        fake.documents[tl_id]["name"] = "T1-REMOTE"
        fake.documents[tl_id]["document_json"] = json.dumps({"tracks": [], "name": "T1-REMOTE"})
        fake.documents[tl_id]["version"] = 2
        eid_good = generate_event_ulid()
        payload_good = json.dumps({"data": {"timeline_id": tl_id, "config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "rh", "previous_event_hash": None}})
        fake.events[eid_good] = {"event_id": eid_good, "timeline_id": tl_id, "project_id": proj_id, "stream_id": sid, "seq": 2, "kind": "timeline.saved", "payload_json": payload_good, "actor_kind": "system", "actor_id": "system", "txn_id": generate_event_ulid(), "idempotency_key": f"remote:{eid_good}", "created_at": "2026-01-01T00:00:03Z"}
        eid_bad = generate_event_ulid()
        # malformed: payload_json not JSON
        fake.events[eid_bad] = {"event_id": eid_bad, "timeline_id": tl_id, "project_id": proj_id, "stream_id": sid, "seq": 3, "kind": "timeline.saved", "payload_json": "{bad json!!!", "actor_kind": "system", "actor_id": "system", "txn_id": generate_event_ulid(), "idempotency_key": f"remote:{eid_bad}", "created_at": "2026-01-01T00:00:04Z"}
        # local diverge
        _append_events(tmp_path, proj_id, tl_id, sid, 1)
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        result = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert result.action == "conflict"
        assert len(result.conflict_artifacts) == 1
        art_path = Path(str(getattr(result.conflict_artifacts[0], "path", "")))
        assert art_path.exists()
        raw = json.loads(art_path.read_text())
        # their-copy (source) should contain good row, and skipped_rows should name bad row
        assert "skipped_rows" in raw
        skipped_ids = [r["event_id"] for r in raw["skipped_rows"]]
        assert eid_bad in skipped_ids
        # good row should appear in source suffix
        assert "source" in raw
        source_suffix = raw["source"]["suffix"]
        assert any(e["event_id"] == eid_good for e in source_suffix)
        # malformed row must not be silently in suffix
        assert not any(e["event_id"] == eid_bad for e in source_suffix)

    def test_push_fork_entire_suffix_malformed_raises(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        fake.documents[tl_id]["version"] = 2
        fake.documents[tl_id]["name"] = "REMOTE"
        # two bad rows only
        for seq in (2, 3):
            eid = generate_event_ulid()
            fake.events[eid] = {"event_id": eid, "timeline_id": tl_id, "project_id": proj_id, "stream_id": sid, "seq": seq, "kind": "timeline.saved", "payload_json": "not-json-{", "actor_kind": "system", "actor_id": "system", "txn_id": generate_event_ulid(), "idempotency_key": f"remote:{eid}", "created_at": "2026-01-01T00:00:05Z"}
        _append_events(tmp_path, proj_id, tl_id, sid, 1)
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        with pytest.raises(TursoSyncError):
            push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)


# ---------------------------------------------------------------------------
# Q10 — libsql_experimental-only import
# ---------------------------------------------------------------------------

class TestQ10LibsqlExperimentalFallback:
    def test_libsql_experimental_only_succeeds(self, tmp_path: Path, monkeypatch):
        # Simulate only libsql_experimental installed: libsql missing, libsql_experimental present
        monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.turso.io")
        monkeypatch.setenv("TURSO_AUTH_TOKEN", "tok")

        fake_libsql = ModuleType("libsql_experimental")

        class _FakeCursor:
            def __init__(self):
                self.description = []
            def execute(self, *a, **kw):
                pass
            def fetchall(self):
                return []
            def close(self):
                pass

        class _FakeConn:
            def cursor(self):
                return _FakeCursor()
            def close(self):
                pass

        def _fake_connect(*a, **kw):
            return _FakeConn()

        fake_libsql.connect = _fake_connect  # type: ignore[attr-defined]

        real_import = __import__

        def _import_mock(name, *args, **kwargs):
            if name == "libsql":
                raise ImportError("No module named 'libsql'")
            if name == "libsql_experimental":
                return fake_libsql
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_import_mock):
            # also patch sys.modules to ensure fallback works via __import__
            sys_modules_patch = patch.dict(sys.modules, {"libsql_experimental": fake_libsql}, clear=False)
            with sys_modules_patch:
                if "libsql" in sys.modules:
                    del sys.modules["libsql"]
                transport = LibSqlHttpTransport()
                # first operation should succeed, not raise TursoConfigError
                transport.execute_batch([])  # no-op batch
                transport.query("SELECT 1", ())

    def test_neither_driver_raises_typed(self, monkeypatch):
        monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.turso.io")
        monkeypatch.setenv("TURSO_AUTH_TOKEN", "tok")

        def _import_fail(name, *a, **kw):
            if name in ("libsql", "libsql_experimental"):
                raise ImportError(f"No module named '{name}'")
            return __import__(name, *a, **kw)

        with patch("builtins.__import__", side_effect=_import_fail):
            # ensure sys.modules doesn't have them
            orig_libsql = sys.modules.pop("libsql", None)
            orig_exp = sys.modules.pop("libsql_experimental", None)
            try:
                transport = LibSqlHttpTransport()
                with pytest.raises(TursoConfigError):
                    transport.execute_batch([])
                with pytest.raises(TursoConfigError):
                    transport.query("SELECT 1", ())
            finally:
                if orig_libsql is not None:
                    sys.modules["libsql"] = orig_libsql
                if orig_exp is not None:
                    sys.modules["libsql_experimental"] = orig_exp


# ---------------------------------------------------------------------------
# SHOULD-FIX — FakeTursoTransport COUNT dispatch
# ---------------------------------------------------------------------------

class TestFakeTransportCountDispatch:
    def test_count_after_mixed_pushes(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        # second local event and push
        _append_events(tmp_path, proj_id, tl_id, sid, 1)
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        # fetch_remote_head count should be correct via COUNT(*)
        head = replica.fetch_remote_head(tl_id)
        assert head is not None
        assert head["event_count"] == 2
        cnt_rows = fake.query("SELECT COUNT(*) as cnt FROM events WHERE timeline_id = ?", (tl_id,))
        assert cnt_rows[0]["cnt"] == 2
        # also direct COUNT without timeline filter
        cnt_all = fake.query("SELECT COUNT(*) as cnt FROM events", ())
        assert cnt_all[0]["cnt"] >= 2
