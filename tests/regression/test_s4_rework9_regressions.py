"""S4 rework-9 — X1/X2 pins for W1/W2/W3 pull+push and first-sync restart."""
# ruff: noqa: E501

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest

from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.store.uow import UnitOfWork
from astrid.core.timeline.eventlog.turso import (
    TursoDocumentRow,
    TursoEventCollisionError,
    TursoEventRow,
    TursoReplicaClient,
    TursoReplicationError,
)
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.packs import build_standard_registry, open_standard_writer


def _make_local_db(tmp_path: Path, project_slug: str = "proj"):
    from astrid.core.events.service import EventAppendService

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


class _RealReplicaTransport:
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
    conn.execute(
        """
        CREATE TABLE documents (
            timeline_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            event_stream_id TEXT NOT NULL,
            name TEXT NOT NULL,
            document_json TEXT NOT NULL,
            version INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE events (
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
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def _doc_row(tl_id: str, proj_id: str, sid: str, version: int = 1) -> TursoDocumentRow:
    from astrid.core.util.time import utc_now_iso

    return TursoDocumentRow(
        timeline_id=tl_id,
        project_id=proj_id,
        event_stream_id=sid,
        name="T1",
        document_json=json.dumps({"tracks": []}),
        version=version,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )


def _event_row(tl_id: str, proj_id: str, sid: str, event_id: str, seq: int, ik: str, payload: dict | None = None, kind: str = "timeline.updated") -> TursoEventRow:
    from astrid.core.util.time import utc_now_iso

    pl = payload if payload is not None else {"data": {"x": 1}, "_integrity": {"event_hash": "abc", "previous_event_hash": None}}
    import json as _js

    pj = _js.dumps(pl) if isinstance(pl, dict) else str(pl)
    return TursoEventRow(
        timeline_id=tl_id,
        project_id=proj_id,
        stream_id=sid,
        seq=seq,
        kind=kind,
        payload_json=pj,
        actor_kind="system",
        actor_id="system",
        txn_id=generate_event_ulid(),
        idempotency_key=ik,
        created_at=utc_now_iso(),
        event_id=event_id,
    )


class _RecordingTransport:
    """Minimal transport with NO content checks, captures statements."""

    def __init__(self):
        self.statements: list[tuple[str, tuple]] = []
        self.documents: dict[str, dict] = {}
        self.events: dict[str, dict] = {}

    def execute_batch(self, statements):
        self.statements.extend(statements)

    def query(self, sql, params=()):
        s = sql.lower()
        if "from documents" in s and "where timeline_id" in s:
            tid = params[0] if params else None
            row = self.documents.get(str(tid)) if tid else None
            return [dict(row)] if row else []
        if "from events" in s and "where timeline_id" in s:
            tid = params[0] if params else None
            rows = [v for v in self.events.values() if str(v.get("timeline_id")) == str(tid)]
            return [dict(r) for r in rows]
        if "select count" in s:
            return [{"cnt": 0}]
        return []

    def close(self):
        pass


# ---------------------------------------------------------------------------
# W1 — recording-transport negatives
# ---------------------------------------------------------------------------


class TestW1RecordingTransport:
    def test_document_data_uri_rejected(self):
        transport = _RecordingTransport()
        replica = TursoReplicaClient(transport)
        tl_id = uuid.uuid4().hex
        proj_id = uuid.uuid4().hex
        sid = f"{tl_id}:timeline.timeline"
        doc = TursoDocumentRow(
            timeline_id=tl_id,
            project_id=proj_id,
            event_stream_id=sid,
            name="T1",
            document_json=json.dumps({"x": "data:image/png;base64,abcd"}),
            version=1,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        with pytest.raises(TursoReplicationError):
            replica.push_timeline_updates(doc, [], require_document=True)

    def test_document_asset_registry_rejected(self):
        transport = _RecordingTransport()
        replica = TursoReplicaClient(transport)
        tl_id = uuid.uuid4().hex
        proj_id = uuid.uuid4().hex
        sid = f"{tl_id}:timeline.timeline"
        doc = TursoDocumentRow(
            timeline_id=tl_id,
            project_id=proj_id,
            event_stream_id=sid,
            name="T1",
            document_json=json.dumps({"asset_registry_json": "{}"}),
            version=1,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        with pytest.raises(TursoReplicationError):
            replica.push_timeline_updates(doc, [], require_document=True)

    def test_event_blob_heuristic_rejected(self):
        transport = _RecordingTransport()
        replica = TursoReplicaClient(transport)
        tl_id = uuid.uuid4().hex
        proj_id = uuid.uuid4().hex
        sid = f"{tl_id}:timeline.timeline"
        # payload that trips blob heuristic via data-URI
        payload = {"data": {"blob": "data:image/png;base64,abcd"}, "_integrity": {"event_hash": "h", "previous_event_hash": None}}
        ev = _event_row(tl_id, proj_id, sid, generate_event_ulid(), 1, "ik1", payload=payload)
        doc = _doc_row(tl_id, proj_id, sid, version=1)
        with pytest.raises(TursoReplicationError):
            replica.push_timeline_updates(doc, [ev], require_document=True)


# ---------------------------------------------------------------------------
# W2 — kind-mismatch replay
# ---------------------------------------------------------------------------


class TestW2KindMismatch:
    def test_kind_mismatch_collision(self, tmp_path: Path):
        replica_db = tmp_path / "replica.db"
        _init_replica_db(replica_db)
        transport = _RealReplicaTransport(replica_db)
        replica = TursoReplicaClient(transport)
        tl_id = uuid.uuid4().hex
        proj_id = uuid.uuid4().hex
        sid = f"{tl_id}:timeline.timeline"
        doc = _doc_row(tl_id, proj_id, sid, version=1)
        ev_id = generate_event_ulid()
        ik = f"ik:{ev_id}"
        payload = {"data": {"x": 1}, "_integrity": {"event_hash": "h1", "previous_event_hash": None}}
        ev1 = _event_row(tl_id, proj_id, sid, ev_id, 1, ik, payload=payload, kind="timeline.created")
        replica.push_timeline_updates(doc, [ev1], require_document=True)
        # same identity+payload, different kind
        ev2 = _event_row(tl_id, proj_id, sid, ev_id, 1, ik, payload=payload, kind="timeline.updated")
        with pytest.raises(TursoEventCollisionError):
            replica.push_timeline_updates(None, [ev2], require_document=False)


# ---------------------------------------------------------------------------
# W3 push — crash-resume
# ---------------------------------------------------------------------------


class TestW3PushResume:
    def test_failing_state_write_then_resume(self, tmp_path: Path, monkeypatch):
        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
        from astrid.core.timeline.turso_sync import (
            TursoSyncError,
            push_to_turso,
        )

        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        replica_db = tmp_path / "replica.db"
        _init_replica_db(replica_db)
        transport = _RealReplicaTransport(replica_db)
        replica = TursoReplicaClient(transport)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        # bootstrap push
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # local advances
        from astrid.core.events.service import EventAppendService
        from astrid.core.store.uow import UnitOfWork
        from astrid.packs import build_standard_registry, open_standard_writer

        registry = build_standard_registry()
        svc = EventAppendService(registry)
        from astrid.core.integrations.reigh.bridge_service import derive_database_path

        db_path_w = derive_database_path(tmp_path)
        writer2 = open_standard_writer(db_path_w, registry=registry)

        def _append2(uow: UnitOfWork):
            svc.append(
                uow,
                stream_id=sid,
                project_id=proj_id,
                event_kind="timeline.saved",
                data={"config": {"clips": [], "tracks": []}},
                changes=["config"],
                idempotency_key=f"local2:{tl_id}",
                txn_id=generate_event_ulid(),
                actor_kind="system",
                event_id=generate_event_ulid(),
            )

        UnitOfWork(writer2).run(_append2)
        writer2.close()

        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        import astrid.core.timeline.turso_sync as sync_mod

        orig = sync_mod.write_turso_sync_state

        def failing(*_a, **_kw):
            raise OSError("injected failure")

        monkeypatch.setattr(sync_mod, "write_turso_sync_state", failing)
        with pytest.raises(TursoSyncError):
            push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        monkeypatch.setattr(sync_mod, "write_turso_sync_state", orig)
        backend3 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend3, replica=replica)
        assert r2.action in ("pushed", "up_to_date")
        assert len(r2.conflict_artifacts) == 0


# ---------------------------------------------------------------------------
# W3 pull — crash-resume (X1)
# ---------------------------------------------------------------------------


class TestW3PullResume:
    def test_failing_state_pull_then_resume(self, tmp_path: Path, monkeypatch):
        from astrid.core.events.service import build_integrity_envelope
        from astrid.core.receipts.canonical import canonical_json
        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
        from astrid.core.timeline.turso_sync import TursoSyncError, pull_from_turso, push_to_turso
        from astrid.core.util.time import utc_now_iso

        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        replica_db = tmp_path / "replica.db"
        _init_replica_db(replica_db)
        transport = _RealReplicaTransport(replica_db)
        replica = TursoReplicaClient(transport)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # remote advances alone
        backend_head = backend.read_events()
        prev_hash = backend_head[-1].hash if backend_head else None
        doc_v2 = TursoDocumentRow(
            timeline_id=tl_id,
            project_id=proj_id,
            event_stream_id=sid,
            name="T1",
            document_json=json.dumps({"tracks": [{"id": "a"}]}),
            version=2,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        ev_id_remote = generate_event_ulid()
        payload_data = {"hello": "remote1"}
        env, _h = build_integrity_envelope(payload_data, prev_hash)
        pj = canonical_json(env)
        ev_row = TursoEventRow(
            timeline_id=tl_id,
            project_id=proj_id,
            stream_id=sid,
            seq=2,
            kind="timeline.updated",
            payload_json=pj,
            actor_kind="system",
            actor_id="system",
            txn_id=generate_event_ulid(),
            idempotency_key=f"remote:{ev_id_remote}",
            created_at=utc_now_iso(),
            event_id=ev_id_remote,
        )
        replica.push_timeline_updates(doc_v2, [ev_row], require_document=True, expected_remote_version=1)
        # failing pull
        import astrid.core.timeline.turso_sync as sync_mod

        orig = sync_mod.write_turso_sync_state

        def failing(*_a, **_kw):
            raise OSError("injected")

        monkeypatch.setattr(sync_mod, "write_turso_sync_state", failing)
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        with pytest.raises(TursoSyncError):
            pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        monkeypatch.setattr(sync_mod, "write_turso_sync_state", orig)
        backend3 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend3, replica=replica)
        assert r2.action in ("pulled", "up_to_date")
        assert len(r2.conflict_artifacts) == 0


# ---------------------------------------------------------------------------
# First-sync restart shape
# ---------------------------------------------------------------------------


class TestFirstSyncRestart:
    def test_push_after_state_deleted(self, tmp_path: Path):
        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
        from astrid.core.timeline.turso_sync import push_to_turso

        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        replica_db = tmp_path / "replica.db"
        _init_replica_db(replica_db)
        transport = _RealReplicaTransport(replica_db)
        replica = TursoReplicaClient(transport)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # delete state file
        from astrid.core.timeline.turso_sync import turso_sync_state_path

        p = turso_sync_state_path(home)
        if p.exists():
            p.unlink()
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action in ("pushed", "up_to_date")
        assert len(r2.conflict_artifacts) == 0
