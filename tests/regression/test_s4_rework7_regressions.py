"""S4 rework-7 — T1 idempotent replay, T2 race honesty, R1/R2/R3 pins."""
# ruff: noqa: E501
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest

from astrid.core.timeline.eventlog.turso import (
    TursoDocumentRow,
    TursoEventCollisionError,
    TursoEventRow,
    TursoReplicaClient,
    TursoVersionRaceError,
)
from astrid.core.timeline.turso_sync import TursoSyncError, push_to_turso

# -- helpers ---------------------------------------------------------------

def _make_local_db(tmp_path: Path, project_slug: str = "proj"):
    from astrid.core.events.service import EventAppendService
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.timeline.events.schema import generate_event_ulid
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


class RealReplicaTransport:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def execute_batch(self, statements):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN")
            for sql, params in statements:
                conn.execute(sql, params)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def query(self, sql, params=()):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def close(self):
        pass


def _init_replica_db(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            timeline_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            event_stream_id TEXT NOT NULL,
            name TEXT NOT NULL,
            document_json TEXT NOT NULL,
            version INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            timeline_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            stream_id TEXT NOT NULL,
            seq INTEGER NOT NULL,
            kind TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            actor_kind TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            txn_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(timeline_id, seq),
            UNIQUE(timeline_id, idempotency_key)
        )
    """)
    conn.commit()
    conn.close()


def _doc_row(tl_id: str, proj_id: str, sid: str, version: int = 1) -> TursoDocumentRow:
    return TursoDocumentRow(
        timeline_id=tl_id,
        project_id=proj_id,
        event_stream_id=sid,
        name="T1",
        document_json=json.dumps({"tracks": [], "version": version}),
        version=version,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def _event_row(tl_id: str, proj_id: str, sid: str, event_id: str, seq: int, ik: str, payload: dict | None = None) -> TursoEventRow:
    pl = payload if payload is not None else {"data": {"x": 1}, "_integrity": {"event_hash": "abc", "previous_event_hash": None}}
    return TursoEventRow(
        event_id=event_id,
        timeline_id=tl_id,
        project_id=proj_id,
        stream_id=sid,
        seq=seq,
        kind="timeline.created",
        payload_json=json.dumps(pl),
        actor_kind="system",
        actor_id="system",
        txn_id="txn1",
        idempotency_key=ik,
        created_at="2026-01-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# R1 — three collision shapes
# ---------------------------------------------------------------------------

class TestR1Collisions:
    def test_event_id_collision(self, tmp_path: Path):
        db_path = tmp_path / "replica.db"
        _init_replica_db(db_path)
        transport = RealReplicaTransport(db_path)
        replica = TursoReplicaClient(transport)
        tl_id = uuid.uuid4().hex
        proj_id = uuid.uuid4().hex
        sid = f"{tl_id}:timeline.timeline"
        doc = _doc_row(tl_id, proj_id, sid, version=1)
        ev1 = _event_row(tl_id, proj_id, sid, event_id="evt-1", seq=1, ik="ik-1", payload={"data": {"x": 1}, "_integrity": {"event_hash": "h1"}})
        replica.push_timeline_updates(doc, [ev1], require_document=True, expected_remote_version=None)
        ev2 = _event_row(tl_id, proj_id, sid, event_id="evt-1", seq=1, ik="ik-1", payload={"data": {"x": 2}, "_integrity": {"event_hash": "h2"}})
        with pytest.raises(TursoEventCollisionError):
            replica.push_timeline_updates(None, [ev2], require_document=False)

    def test_timeline_seq_collision(self, tmp_path: Path):
        db_path = tmp_path / "replica.db"
        _init_replica_db(db_path)
        transport = RealReplicaTransport(db_path)
        replica = TursoReplicaClient(transport)
        tl_id = uuid.uuid4().hex
        proj_id = uuid.uuid4().hex
        sid = f"{tl_id}:timeline.timeline"
        doc = _doc_row(tl_id, proj_id, sid)
        ev1 = _event_row(tl_id, proj_id, sid, event_id="evt-a", seq=5, ik="ik-a", payload={"data": {"x": 1}, "_integrity": {"event_hash": "h1"}})
        replica.push_timeline_updates(doc, [ev1], require_document=True, expected_remote_version=None)
        ev2 = _event_row(tl_id, proj_id, sid, event_id="evt-b", seq=5, ik="ik-b", payload={"data": {"x": 2}, "_integrity": {"event_hash": "h2"}})
        with pytest.raises(TursoEventCollisionError):
            replica.push_timeline_updates(None, [ev2], require_document=False)

    def test_idempotency_key_collision(self, tmp_path: Path):
        db_path = tmp_path / "replica.db"
        _init_replica_db(db_path)
        transport = RealReplicaTransport(db_path)
        replica = TursoReplicaClient(transport)
        tl_id = uuid.uuid4().hex
        proj_id = uuid.uuid4().hex
        sid = f"{tl_id}:timeline.timeline"
        doc = _doc_row(tl_id, proj_id, sid)
        ev1 = _event_row(tl_id, proj_id, sid, event_id="evt-x", seq=10, ik="dup-ik", payload={"data": {"x": 1}, "_integrity": {"event_hash": "h1"}})
        replica.push_timeline_updates(doc, [ev1], require_document=True, expected_remote_version=None)
        ev2 = _event_row(tl_id, proj_id, sid, event_id="evt-y", seq=11, ik="dup-ik", payload={"data": {"x": 2}, "_integrity": {"event_hash": "h2"}})
        with pytest.raises(TursoEventCollisionError):
            replica.push_timeline_updates(None, [ev2], require_document=False)


# ---------------------------------------------------------------------------
# T1 — cross-call exact replay vs REAL sqlite
# ---------------------------------------------------------------------------

class TestT1ExactReplay:
    def test_cross_call_exact_replay_silent(self, tmp_path: Path):
        db_path = tmp_path / "replica.db"
        _init_replica_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()
        transport = RealReplicaTransport(db_path)
        replica = TursoReplicaClient(transport)
        tl_id = uuid.uuid4().hex
        proj_id = uuid.uuid4().hex
        sid = f"{tl_id}:timeline.timeline"
        doc = _doc_row(tl_id, proj_id, sid, version=1)
        ev = _event_row(tl_id, proj_id, sid, event_id="evt-replay", seq=1, ik="ik-replay", payload={"data": {"x": 99}, "_integrity": {"event_hash": "replay-hash"}})
        replica.push_timeline_updates(doc, [ev], require_document=True, expected_remote_version=None)
        # count after first push
        cnt1 = transport.query("SELECT COUNT(*) as cnt FROM events WHERE timeline_id = ?", (tl_id,))[0]["cnt"]
        assert cnt1 == 1
        # second push identical — must not raise
        replica.push_timeline_updates(doc, [ev], require_document=True, expected_remote_version=None)
        cnt2 = transport.query("SELECT COUNT(*) as cnt FROM events WHERE timeline_id = ?", (tl_id,))[0]["cnt"]
        assert cnt2 == 1
        # also mixed batch: one replay + one new should push only new
        ev_new = _event_row(tl_id, proj_id, sid, event_id="evt-new", seq=2, ik="ik-new", payload={"data": {"x": 100}, "_integrity": {"event_hash": "new-hash"}})
        replica.push_timeline_updates(doc, [ev, ev_new], require_document=False)
        cnt3 = transport.query("SELECT COUNT(*) as cnt FROM events WHERE timeline_id = ?", (tl_id,))[0]["cnt"]
        assert cnt3 == 2


# ---------------------------------------------------------------------------
# R2 — racing-fetch interleaving vs REAL sqlite
# ---------------------------------------------------------------------------

class TestR2RacingFetch:
    def test_racing_fetch_preserves_remote(self, tmp_path: Path):
        # local db with real S schema
        proj_id, tl_id, sid, home = _make_local_db(tmp_path, project_slug="proj-r2")
        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend

        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        backend.head()
        # remote replica db
        replica_path = tmp_path / "replica_r2.db"
        _init_replica_db(replica_path)
        transport = RealReplicaTransport(replica_path)
        replica = TursoReplicaClient(transport)
        orig_name = "T1"
        doc_v1 = TursoDocumentRow(
            timeline_id=tl_id,
            project_id=proj_id,
            event_stream_id=sid,
            name=orig_name,
            document_json=json.dumps({"tracks": [], "version": 1}),
            version=1,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        # seed remote with one event so version 1 has last_event_id/hash (HeadSnapshot requires it)
        local_ev = backend.read_events()[0]
        # fetch payload_json from local db for fidelity
        import sqlite3 as _sqlite

        from astrid.core.integrations.reigh.bridge_service import derive_database_path
        db_local_path = derive_database_path(tmp_path)
        _conn = _sqlite.connect(f"file:{db_local_path}?mode=ro", uri=True)
        _row = _conn.execute("SELECT payload_json, seq FROM events WHERE event_id = ?", (local_ev.event_id,)).fetchone()
        _conn.close()
        payload_json = str(_row[0]) if _row else json.dumps({"data": {}, "_integrity": {"event_hash": "h1"}})
        seq_val = int(_row[1]) if _row else 1
        ev_seed = TursoEventRow(
            event_id=local_ev.event_id,
            timeline_id=tl_id,
            project_id=proj_id,
            stream_id=sid,
            seq=seq_val,
            kind=str(getattr(local_ev, "kind", "timeline.created")),
            payload_json=payload_json,
            actor_kind="system",
            actor_id="system",
            txn_id=str(getattr(local_ev, "txn_id", "txn1")),
            idempotency_key=f"seed:{local_ev.event_id}",
            created_at=str(getattr(local_ev, "ts", "2026-01-01T00:00:00Z")),
        )
        replica.push_timeline_updates(doc_v1, [ev_seed], require_document=True, expected_remote_version=None)
        # write initial sync state at version 1 so next push is source_only, not bootstrap incompatible
        import json as _json

        from astrid.core.timeline.turso_sync import TursoSyncState, write_turso_sync_state
        _payload_hash = None
        try:
            _payload_hash = _json.loads(payload_json).get("_integrity", {}).get("event_hash")
        except Exception:
            _payload_hash = None
        init_state = TursoSyncState(
            timeline_id=tl_id,
            local_version=1,
            local_event_id=local_ev.event_id,
            local_hash=_payload_hash or local_ev.event_id,
            remote_version=1,
            remote_event_id=local_ev.event_id,
            remote_hash=_payload_hash or local_ev.event_id,
            updated_at="2026-01-01T00:00:00Z",
            last_pushed_event_id=local_ev.event_id,
        )
        write_turso_sync_state(home, init_state)
        from astrid.core.events.service import EventAppendService
        from astrid.core.integrations.reigh.bridge_service import derive_database_path
        from astrid.core.store.uow import UnitOfWork as _UoW
        from astrid.core.timeline.events.schema import generate_event_ulid
        from astrid.packs import build_standard_registry, open_standard_writer

        registry2 = build_standard_registry()
        db_local2 = derive_database_path(tmp_path)
        writer2 = open_standard_writer(db_local2, registry=registry2)
        svc2 = EventAppendService(registry2)

        def _append2(uow):
            svc2.append(
                uow,
                stream_id=sid,
                project_id=proj_id,
                event_kind="timeline.created",
                data={"timeline_id": tl_id, "timeline_ulid": generate_event_ulid(), "slug": "t1-2", "name": "T1-2"},
                changes=["timeline_id", "slug", "name"],
                idempotency_key=f"r2-{tl_id}-2",
                txn_id=generate_event_ulid(),
                actor_kind="system",
                event_id=generate_event_ulid(),
            )

        _UoW(writer2).run(_append2)
        writer2.close()
        # re-open backend after local advance
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        # wrap fetch_remote_head: call #1 advances remote alone then returns pre-advance head
        orig_fetch = replica.fetch_remote_head
        call_count = {"n": 0}

        def _wrapped(tid: str):
            head = orig_fetch(tid)
            if call_count["n"] == 0:
                call_count["n"] += 1
                # advance remote alone: bump version to 9, change name to preserve check
                conn = sqlite3.connect(str(replica_path))
                conn.execute("PRAGMA foreign_keys=ON")
                conn.execute("UPDATE documents SET version=?, name=?, updated_at=? WHERE timeline_id=?", (9, "REMOTE-ADVANCED", "2026-08-23T00:00:00Z", tid))
                conn.commit()
                conn.close()
                # return pre-advance head (stale)
                return head
            return orig_fetch(tid)

        replica.fetch_remote_head = _wrapped  # type: ignore[method-assign]
        # Now push — with our T2 choice (DELETE reclassify) we expect typed race error
        with pytest.raises(TursoVersionRaceError):
            push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        # remote name/version PRESERVED (not overwritten to local's 2)
        rows = transport.query("SELECT * FROM documents WHERE timeline_id = ?", (tl_id,))
        assert rows, "remote document missing after race"
        assert int(rows[0]["version"]) == 9, f"remote version not preserved: {rows[0]}"
        assert rows[0]["name"] == "REMOTE-ADVANCED", f"remote name not preserved: {rows[0]}"


# ---------------------------------------------------------------------------
# R3 — cursor / document validation typed
# ---------------------------------------------------------------------------

class TestR3TypedEntries:
    def test_spoke_version_nonzero_missing_event_id_typed(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path, project_slug="proj-r3a")
        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
        from astrid.core.timeline.turso_sync import TursoSyncState, write_turso_sync_state

        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        # craft corrupt state: spoke_version≠0 but missing spoke_event_id
        bad_state = TursoSyncState(
            timeline_id=tl_id,
            local_version=1,
            local_event_id=None,
            local_hash=None,
            remote_version=1,
            remote_event_id="evt-remote",
            remote_hash="hash-remote",
            updated_at="2026-01-01T00:00:00Z",
            last_pushed_event_id=None,
        )
        write_turso_sync_state(home, bad_state)
        replica_path = tmp_path / "replica_r3a.db"
        _init_replica_db(replica_path)
        replica = TursoReplicaClient(RealReplicaTransport(replica_path))
        with pytest.raises(TursoSyncError):
            push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)

    def test_non_numeric_documents_version_typed(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path, project_slug="proj-r3b")
        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend

        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        replica_path = tmp_path / "replica_r3b.db"
        _init_replica_db(replica_path)
        # inject document with non-numeric version string via raw sqlite
        conn = sqlite3.connect(str(replica_path))
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "INSERT INTO documents (timeline_id, project_id, event_stream_id, name, document_json, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tl_id, proj_id, sid, "T1", json.dumps({"tracks": []}), "not-a-number", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        conn.commit()
        conn.close()
        replica = TursoReplicaClient(RealReplicaTransport(replica_path))
        with pytest.raises(TursoSyncError):
            push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
