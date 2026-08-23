"""S4 rework-13 — P2-1/2/3 + D1 pins (RED→GREEN quoted)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import (
    DOCUMENT_REPLICA_COLUMNS,
    EVENT_REPLICA_COLUMNS,
    FakeTursoTransport,
    TursoDocumentRow,
    TursoError,
    TursoEventRow,
    TursoReplicaClient,
)
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.turso_sync import pull_from_turso, push_to_turso, read_turso_sync_state


def _doc_params(timeline_id: str, version: int, doc_json: str, name: str = "My Timeline") -> tuple:
    row = {
        "timeline_id": timeline_id,
        "project_id": "proj-1",
        "event_stream_id": "sid-1",
        "name": name,
        "document_json": doc_json,
        "version": version,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    return tuple(row[c] for c in DOCUMENT_REPLICA_COLUMNS)


def _event_params(event_id: str, timeline_id: str = "tl-1", payload: str = '{"a":1}', seq: int = 1) -> tuple:  # noqa: E501
    row = {
        "event_id": event_id,
        "timeline_id": timeline_id,
        "project_id": "proj-1",
        "stream_id": f"{timeline_id}:timeline.timeline",
        "seq": seq,
        "kind": "timeline.saved",
        "payload_json": payload,
        "actor_kind": "system",
        "actor_id": "system",
        "txn_id": "txn-1",
        "idempotency_key": f"ik:{event_id}",
        "created_at": "2026-01-01T00:00:00Z",
    }
    return tuple(row[c] for c in EVENT_REPLICA_COLUMNS)


def _doc_sql(expected_version: int | None = None) -> str:
    cols = ", ".join(DOCUMENT_REPLICA_COLUMNS)
    placeholders = ", ".join("?" for _ in DOCUMENT_REPLICA_COLUMNS)
    base = f"INSERT INTO documents ({cols}) VALUES ({placeholders}) ON CONFLICT(timeline_id) DO UPDATE SET name=excluded.name, document_json=excluded.document_json, version=excluded.version, updated_at=excluded.updated_at"  # noqa: E501
    if expected_version is not None:
        base += " WHERE documents.version = ?"
    return base


def _event_guarded_sql() -> str:
    cols = ", ".join(EVENT_REPLICA_COLUMNS)
    placeholders = ", ".join("?" for _ in EVENT_REPLICA_COLUMNS)
    return f"INSERT INTO events ({cols}) SELECT {placeholders} WHERE EXISTS (SELECT 1 FROM documents WHERE timeline_id = ? AND version = ? AND document_json = ? AND name = ?)"  # noqa: E501


def _event_sql() -> str:
    cols = ", ".join(EVENT_REPLICA_COLUMNS)
    placeholders = ", ".join("?" for _ in EVENT_REPLICA_COLUMNS)
    return f"INSERT INTO events ({cols}) VALUES ({placeholders})"


def _real_sqlite_tables():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE documents (timeline_id TEXT PRIMARY KEY, project_id TEXT, event_stream_id TEXT, name TEXT, document_json TEXT, version INTEGER, created_at TEXT, updated_at TEXT)")  # noqa: E501
    conn.execute("CREATE TABLE events (event_id TEXT PRIMARY KEY, timeline_id TEXT, project_id TEXT, stream_id TEXT, seq INTEGER, kind TEXT, payload_json TEXT, actor_kind TEXT, actor_id TEXT, txn_id TEXT, idempotency_key TEXT, created_at TEXT)")  # noqa: E501
    return conn


class TestP21StatementOrderFaithful:
    def test_order_reversal_guard_precedes_update_zero_events_fake_equals_real(self):
        tl = "tl-order"
        v1 = json.dumps({"v": 1}, sort_keys=True)
        v2 = json.dumps({"v": 2}, sort_keys=True)
        tr = FakeTursoTransport()
        tr.execute_batch([(_doc_sql(), _doc_params(tl, 1, v1))])
        guarded = _event_guarded_sql()
        doc_update = _doc_sql(expected_version=1)
        ev_params = _event_params(generate_event_ulid(), timeline_id=tl, seq=2)
        # replace event_id with fixed for comparison
        eid = generate_event_ulid()
        ev_params = _event_params(eid, timeline_id=tl, seq=2)
        guarded_params = ev_params + (tl, 2, v2, "My Timeline")
        doc_params = _doc_params(tl, 2, v2) + (1,)
        tr.execute_batch([(guarded, guarded_params), (doc_update, doc_params)])
        assert len([e for e in tr.events.values() if e["event_id"] == eid]) == 0  # noqa: E501
        conn = _real_sqlite_tables()
        conn.execute("INSERT INTO documents (timeline_id, project_id, event_stream_id, name, document_json, version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)", _doc_params(tl, 1, v1))  # noqa: E501
        conn.commit()
        try:
            cur = conn.cursor()
            cur.execute("BEGIN")
            cur.execute(guarded, guarded_params)
            cur.execute(doc_update, doc_params)
            cur.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        cnt = conn.execute("SELECT COUNT(*) FROM events WHERE event_id=?", (eid,)).fetchone()[0]
        assert cnt == 0
        assert cnt == len([e for e in tr.events.values() if e["event_id"] == eid])

    def test_correct_order_guard_after_update_inserts_one(self):
        tl = "tl-order2"
        v1 = json.dumps({"v": 1}, sort_keys=True)
        v2 = json.dumps({"v": 2}, sort_keys=True)
        tr = FakeTursoTransport()
        tr.execute_batch([(_doc_sql(), _doc_params(tl, 1, v1))])
        guarded = _event_guarded_sql()
        doc_update = _doc_sql(expected_version=1)
        eid = generate_event_ulid()
        ev_params = _event_params(eid, timeline_id=tl, seq=2)
        guarded_params = ev_params + (tl, 2, v2, "My Timeline")
        doc_params = _doc_params(tl, 2, v2) + (1,)
        tr.execute_batch([(doc_update, doc_params), (guarded, guarded_params)])
        assert len([e for e in tr.events.values() if e["event_id"] == eid]) == 1

    def test_cross_timeline_all_or_nothing(self):
        tr = FakeTursoTransport()
        v = json.dumps({"x": 1})
        sql = _event_sql()
        e1 = _event_params(generate_event_ulid(), timeline_id="tl-a", seq=1)
        dup_id = e1[0]
        e2 = _event_params(dup_id, timeline_id="tl-b", seq=1)
        doc_a = _doc_sql()
        doc_b = _doc_sql()
        with pytest.raises(TursoError):
            tr.execute_batch([
                (doc_a, _doc_params("tl-a", 1, v)),
                (sql, e1),
                (doc_b, _doc_params("tl-b", 1, v)),
                (sql, e2),
            ])
        assert "tl-a" not in tr.documents
        assert dup_id not in tr.events

    def test_dml_before_ddl_raises(self):
        tr = FakeTursoTransport()
        tr.tables.clear()
        tr.documents.clear()
        tr.events.clear()
        v = json.dumps({"x": 1})
        with pytest.raises(TursoError, match="no such table"):
            tr.execute_batch([(_doc_sql(), _doc_params("tl-x", 1, v))])
        tr.execute_batch([("CREATE TABLE documents (timeline_id TEXT PRIMARY KEY, version INTEGER)", ()), (_doc_sql(), _doc_params("tl-x", 1, v))])  # noqa: E501
        assert "tl-x" in tr.documents


def _make_local_db(tmp_path: Path, project_slug: str = "proj"):
    import json as _json
    import uuid

    from astrid.core.events.service import EventAppendService
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
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
        uow.execute("INSERT INTO projects (id, slug, name, settings_json, event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)", (proj_id, project_slug, "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))  # noqa: E501
        uow.execute("INSERT INTO event_streams (id, project_id, stream_type, aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)", (sid, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"))  # noqa: E501
        uow.execute("INSERT INTO timelines (id, project_id, event_stream_id, name, document_json, asset_registry_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (tl_id, proj_id, sid, "T1", _json.dumps({"tracks": []}), _json.dumps({}), "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))  # noqa: E501

    UnitOfWork(writer).run(_setup)
    svc = EventAppendService(registry)

    def _append(uow: UnitOfWork):
        svc.append(uow, stream_id=sid, project_id=proj_id, event_kind="timeline.created", data={"timeline_id": tl_id, "timeline_ulid": ulid, "slug": "t1", "name": "T1"}, changes=["timeline_id", "slug", "name"], idempotency_key=f"create:{tl_id}", txn_id=generate_event_ulid(), actor_kind="system", event_id=generate_event_ulid())  # noqa: E501

    UnitOfWork(writer).run(_append)
    writer.close()
    home = tmp_path / project_slug / "timelines" / ulid
    home.mkdir(parents=True, exist_ok=True)
    from astrid.packs.timeline.backfill import write_backfill_state

    write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=1, events_sha256="abc")  # noqa: E501
    return proj_id, tl_id, sid, home


def _append_events(tmp_path: Path, proj_id: str, tl_id: str, sid: str, n: int):
    from astrid.core.events.service import EventAppendService
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
    from astrid.core.store.uow import UnitOfWork
    from astrid.packs import build_standard_registry, open_standard_writer

    registry = build_standard_registry()
    db_path = derive_database_path(tmp_path)
    writer = open_standard_writer(db_path, registry=registry)
    svc = EventAppendService(registry)
    ids = []
    for i in range(n):
        eid = generate_event_ulid()
        def _a(uow, _eid=eid, _i=i):
            svc.append(uow, stream_id=sid, project_id=proj_id, event_kind="timeline.saved", data={"config": {"clips": [], "tracks": []}}, changes=["i"], idempotency_key=f"ik:{_eid}", txn_id=generate_event_ulid(), actor_kind="system", event_id=_eid)  # noqa: E501
        UnitOfWork(writer).run(_a)
        ids.append(eid)
    writer.close()
    return ids


class TestP22CursorBoundary:
    def test_truncated_pull_state_is_k_not_n_and_retry_fetches_remainder(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)  # noqa: E501
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
        head = replica.fetch_remote_head(tl_id)
        ver = head["version"]
        r0 = generate_event_ulid()
        r1 = generate_event_ulid()
        replica_events = []
        for eid in (r0, r1):
            payload = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": f"h-{eid[:6]}", "previous_event_hash": None}})  # noqa: E501
            er = TursoEventRow(event_id=eid, timeline_id=tl_id, project_id=proj_id, stream_id=sid, seq=10 if eid == r0 else 11, kind="timeline.saved", payload_json=payload, actor_kind="system", actor_id="system", txn_id=generate_event_ulid(), idempotency_key=f"ik-{eid}", created_at="2026-01-01T00:00:00Z")  # noqa: E501
            replica_events.append(er)
        doc_row = TursoDocumentRow(timeline_id=tl_id, project_id=proj_id, event_stream_id=sid, name="T1", document_json=json.dumps({"tracks": []}), version=ver+2, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")  # noqa: E501
        replica.push_timeline_updates(doc_row, replica_events, require_document=True, expected_remote_version=ver)  # noqa: E501
        orig_fetch = replica.fetch_remote_events

        def truncated_fetch(tid, after=None, limit=None):
            rows = orig_fetch(tid, after=after, limit=limit)
            return rows[:1]

        with patch.object(replica, "fetch_remote_events", side_effect=truncated_fetch):
            res1 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
            assert res1.action == "pulled"
            assert res1.pulled == 1
            state = read_turso_sync_state(home)
            assert state.remote_event_id == r0

        res2 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
        assert res2.action == "pulled"
        assert res2.pulled == 1
        all_local = backend.read_events()
        assert len(all_local) >= 3
        assert res2.conflict_artifacts is None or len(res2.conflict_artifacts) == 0
        res3 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
        assert res3.action == "up_to_date"

    def test_push_state_never_records_post_commit_advancement(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)  # noqa: E501
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
        _append_events(tmp_path, proj_id, tl_id, sid, 1)
        res = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
        assert res.action == "pushed"
        state = read_turso_sync_state(home)
        pushed_id = state.remote_event_id
        head = replica.fetch_remote_head(tl_id)
        conc_id = generate_event_ulid()
        payload = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h-conc", "previous_event_hash": None}})  # noqa: E501
        conc = TursoEventRow(event_id=conc_id, timeline_id=tl_id, project_id=proj_id, stream_id=sid, seq=999, kind="timeline.saved", payload_json=payload, actor_kind="system", actor_id="system", txn_id=generate_event_ulid(), idempotency_key=f"ik-{conc_id}", created_at="2026-01-01T00:00:00Z")  # noqa: E501
        doc_row = TursoDocumentRow(timeline_id=tl_id, project_id=proj_id, event_stream_id=sid, name="T1", document_json=json.dumps({"tracks": []}), version=head["version"]+1, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")  # noqa: E501
        replica.push_timeline_updates(doc_row, [conc], require_document=True, expected_remote_version=head["version"])  # noqa: E501
        state2 = read_turso_sync_state(home)
        assert state2.remote_event_id == pushed_id
        res2 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
        assert res2.action == "pulled"
        assert res2.pulled == 1


class TestP23PrefixResume:
    def test_crash_after_k_then_retry_pulls_remaining_zero_artifacts(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)  # noqa: E501
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
        head = replica.fetch_remote_head(tl_id)
        ver = head["version"]
        p0 = generate_event_ulid()
        p1 = generate_event_ulid()
        rows = []
        for eid in (p0, p1):
            payload = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": f"hp-{eid[:6]}", "previous_event_hash": None}})  # noqa: E501
            er = TursoEventRow(event_id=eid, timeline_id=tl_id, project_id=proj_id, stream_id=sid, seq=20 if eid == p0 else 21, kind="timeline.saved", payload_json=payload, actor_kind="system", actor_id="system", txn_id=generate_event_ulid(), idempotency_key=f"ik-{eid}", created_at="2026-01-01T00:00:00Z")  # noqa: E501
            rows.append(er)
        doc_row = TursoDocumentRow(timeline_id=tl_id, project_id=proj_id, event_stream_id=sid, name="T1", document_json=json.dumps({"tracks": []}), version=ver+2, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")  # noqa: E501
        replica.push_timeline_updates(doc_row, rows, require_document=True, expected_remote_version=ver)  # noqa: E501
        orig_append = backend.append_imported_event
        call_count = {"n": 0}

        def failing_append(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise TursoError("injected failure after k")
            return orig_append(*args, **kwargs)

        with patch.object(backend, "append_imported_event", side_effect=failing_append):
            with pytest.raises(Exception):
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
        res = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
        assert res.action == "pulled"
        assert res.pulled == 1
        assert not res.conflict_artifacts
        all_local = backend.read_events()
        source_ids = {getattr(e, "source_event_id", None) or e.event_id for e in all_local}
        assert p0 in source_ids and p1 in source_ids

    def test_genuine_divergence_still_forks(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)  # noqa: E501
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
        _append_events(tmp_path, proj_id, tl_id, sid, 1)
        head = replica.fetch_remote_head(tl_id)
        div_id = generate_event_ulid()
        payload = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h-div", "previous_event_hash": None}})  # noqa: E501
        er = TursoEventRow(event_id=div_id, timeline_id=tl_id, project_id=proj_id, stream_id=sid, seq=50, kind="timeline.saved", payload_json=payload, actor_kind="system", actor_id="system", txn_id=generate_event_ulid(), idempotency_key=f"ik-{div_id}", created_at="2026-01-01T00:00:00Z")  # noqa: E501
        doc_row = TursoDocumentRow(timeline_id=tl_id, project_id=proj_id, event_stream_id=sid, name="T1", document_json=json.dumps({"tracks": []}), version=head["version"]+1, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")  # noqa: E501
        replica.push_timeline_updates(doc_row, [er], require_document=True, expected_remote_version=head["version"])  # noqa: E501
        res = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
        assert res.action == "conflict"
        assert res.conflict_artifacts is not None and len(res.conflict_artifacts) == 1
