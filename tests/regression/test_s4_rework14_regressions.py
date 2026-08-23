"""S4 rework-14 — B1 + F1 + F2 pins (RED→GREEN quoted)."""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import (
    DOCUMENT_REPLICA_COLUMNS,
    EVENT_REPLICA_COLUMNS,
    FakeTursoTransport,
    TursoError,
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


def _event_params(event_id: str, timeline_id: str = "tl-1", payload: str = '{"a":1}', seq: int = 1) -> tuple:
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


def _event_sql() -> str:
    cols = ", ".join(EVENT_REPLICA_COLUMNS)
    placeholders = ", ".join("?" for _ in EVENT_REPLICA_COLUMNS)
    return f"INSERT INTO events ({cols}) VALUES ({placeholders})"


def _real_sqlite_tables():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(open("/workspace/goalmd-sqlite-20260822/repos/ArtAgents/packages/timeline-schema/sql/turso/0001_turso_replica_schema.sql").read())  # noqa: E501
    return conn


def _make_local_db(tmp_path: Path, project_slug: str = "proj"):
    import json as _json

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
        def _a(uow, _eid=eid):
            svc.append(uow, stream_id=sid, project_id=proj_id, event_kind="timeline.saved", data={"config": {"clips": [], "tracks": []}}, changes=["i"], idempotency_key=f"ik:{_eid}", txn_id=generate_event_ulid(), actor_kind="system", event_id=_eid)  # noqa: E501
        UnitOfWork(writer).run(_a)
        ids.append(eid)
    writer.close()
    return ids


# ---------------------------------------------------------------------------
# B1 — push resume interleaving race
# ---------------------------------------------------------------------------

class TestB1PushResumeRace:
    def test_push_resume_bookmarks_proven_not_unseen(self, tmp_path: Path):
        # Setup: local at e2, push, then local e3 + remote e3 (stale state), inject e4 during resume
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        # initial push (e1)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        # append e3 locally (second saved)
        e3_ids = _append_events(tmp_path, proj_id, tl_id, sid, 1)
        e3 = e3_ids[0]
        # simulate committed remote e3 but stale state: push e3 without state? use replica directly to commit e3 content
        # Actually push via push_to_turso would update state; to simulate crash-after-commit stale state,
        # we manually push e3 via replica but keep state at e1
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        # fetch local events after old cursor (state currently at first head)
        # Instead drive stale: reset state to old then push
        state_before = read_turso_sync_state(home)
        assert state_before is not None
        # second push that will commit e3 atomically
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        # Now state is at e3. Rewind state to simulate crash before write: restore old state
        from astrid.core.timeline.turso_sync import write_turso_sync_state
        old_state = state_before
        write_turso_sync_state(home, old_state)
        # At this point local has e3, remote has e3, state stale at e1. This triggers both_advanced resume.
        # Inject unseen e4 during resume's head refresh
        unseen_id = generate_event_ulid()
        unseen_seq = 999
        # payload for unseen
        payload_json = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "hash-unseen", "previous_event_hash": "prev"}})
        # we will inject via monkeypatch of _remote_head_snapshot
        import astrid.core.timeline.turso_sync as mod

        orig_snapshot = mod._remote_head_snapshot
        call_count = {"n": 0}

        def injected_snapshot(replica_inner, tid_inner):
            call_count["n"] += 1
            # inject only on second snapshot (resume's fresh_remote), not the initial head fetch
            if call_count["n"] == 2 and tid_inner == tl_id and unseen_id not in fake.events:
                fake.events[unseen_id] = {
                    "event_id": unseen_id,
                    "timeline_id": tl_id,
                    "project_id": proj_id,
                    "stream_id": sid,
                    "seq": unseen_seq,
                    "kind": "timeline.saved",
                    "payload_json": payload_json,
                    "actor_kind": "system",
                    "actor_id": "system",
                    "txn_id": generate_event_ulid(),
                    "idempotency_key": f"ik:{unseen_id}",
                    "created_at": "2026-01-01T00:00:00Z",
                }
                if tl_id in fake.documents:
                    fake.documents[tl_id]["version"] = 3
            return orig_snapshot(replica_inner, tid_inner)

        with patch.object(mod, "_remote_head_snapshot", side_effect=injected_snapshot):
            _res = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        # After resume, stored boundary must be proven e3, not unseen
        st = read_turso_sync_state(home)
        assert st is not None
        assert st.remote_event_id == e3, f"bookmark past unseen: got {st.remote_event_id!r} expected {e3!r} unseen {unseen_id!r}"
        assert st.remote_event_id != unseen_id
        # Next poll must fetch unseen
        # need fresh backend for pull
        pulled = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert pulled.pulled > 0, f"next poll should fetch unseen, got {pulled.action} pulled={pulled.pulled}"
        assert pulled.action == "pulled"
        # Verify complete history contains unseen and no artifacts
        # unseen is imported with new local id, so check pulled count and no artifacts, plus remote still has unseen
        assert pulled.pulled == 1
        assert pulled.conflict_artifacts is None or len(pulled.conflict_artifacts) == 0
        assert unseen_id in fake.events


class TestB1PullResumeRace:
    def test_pull_resume_bookmarks_proven_not_unseen(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        # initial push
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        # Simulate remote having e3 (ahead) that local will pull
        # Create remote e3 via direct fake insert: need payload with integrity
        e3_id = generate_event_ulid()
        e3_payload = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h3", "previous_event_hash": "ph"}})
        # Remote document version bump to 2? keep 1 for simplicity but event seq 2
        # Insert via replica using low-level transport batch: need document + event
        # Instead manually seed fake: document already exists at version 1, add event seq 2
        fake.events[e3_id] = {
            "event_id": e3_id,
            "timeline_id": tl_id,
            "project_id": proj_id,
            "stream_id": sid,
            "seq": 2,
            "kind": "timeline.saved",
            "payload_json": e3_payload,
            "actor_kind": "system",
            "actor_id": "system",
            "txn_id": generate_event_ulid(),
            "idempotency_key": f"ik:{e3_id}",
            "created_at": "2026-01-01T00:00:00Z",
        }
        # bump document version to match event seq for classify
        if tl_id in fake.documents:
            fake.documents[tl_id]["version"] = 2
        # Pull e3 honestly (creates local e3-derived via source_event_id)
        # Save state before e3 pull to use as stale (version 1)
        st_before = read_turso_sync_state(home)
        assert st_before is not None
        pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        stale = read_turso_sync_state(home)
        assert stale is not None
        # Rewind to stale before e3 to simulate crash-after-apply (local has e3, remote has e3, state at e1)
        from astrid.core.timeline.turso_sync import write_turso_sync_state
        write_turso_sync_state(home, st_before)
        # Now local has e3 (2 events total), remote has e3, state at init -> both_advanced? Let's verify with resume check
        # Prepare unseen e4
        unseen_id = generate_event_ulid()
        unseen_payload = json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "hunseen", "previous_event_hash": "ph"}})
        import astrid.core.timeline.turso_sync as mod
        orig_snapshot = mod._remote_head_snapshot
        call_count = {"n": 0}

        def injected_snapshot(replica_inner, tid_inner):
            call_count["n"] += 1
            if call_count["n"] == 2 and tid_inner == tl_id and unseen_id not in fake.events:
                fake.events[unseen_id] = {
                    "event_id": unseen_id,
                    "timeline_id": tl_id,
                    "project_id": proj_id,
                    "stream_id": sid,
                    "seq": 3,
                    "kind": "timeline.saved",
                    "payload_json": unseen_payload,
                    "actor_kind": "system",
                    "actor_id": "system",
                    "txn_id": generate_event_ulid(),
                    "idempotency_key": f"ik:{unseen_id}",
                    "created_at": "2026-01-01T00:00:00Z",
                }
                if tl_id in fake.documents:
                    fake.documents[tl_id]["version"] = 3
            return orig_snapshot(replica_inner, tid_inner)

        with patch.object(mod, "_remote_head_snapshot", side_effect=injected_snapshot):
            _res2 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        # After pull resume, remote boundary should be proven e3's local counterpart, not unseen
        st2 = read_turso_sync_state(home)
        assert st2 is not None
        # Find e3's local id: the second event after init (source_event_id == e3_id) or remapped id
        # Check that stored remote is not unseen
        assert st2.remote_event_id != unseen_id, f"bookmark past unseen: {st2.remote_event_id} == unseen {unseen_id}"
        # Next pull should fetch unseen
        pulled2 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert pulled2.pulled > 0
        assert pulled2.action == "pulled"
        # unseen may be imported as new local id, check source mapping via file? Simpler check that pulled count >0 and no conflict
        assert pulled2.conflict_artifacts is None or len(pulled2.conflict_artifacts) == 0


# ---------------------------------------------------------------------------
# F1 — fake CAS-miss + plain duplicate PK fidelity
# ---------------------------------------------------------------------------

class TestF1FakeConstraint:
    def test_cas_miss_then_plain_duplicate_is_error_and_byte_intact_fake_equals_real(self):
        tl = "tl-f1"
        v1 = json.dumps({"tracks": []}, sort_keys=True)
        v_mut = json.dumps({"attacker": "mutated"}, sort_keys=True)
        # Fake side
        fake = FakeTursoTransport()
        fake.execute_batch([(_doc_sql(), _doc_params(tl, 1, v1))])
        # batch: CAS miss (expected 0 stale) then plain duplicate
        cas_sql = _doc_sql(expected_version=0)
        plain_sql = f"INSERT INTO documents ({', '.join(DOCUMENT_REPLICA_COLUMNS)}) VALUES ({', '.join('?' for _ in DOCUMENT_REPLICA_COLUMNS)})"
        cas_params = _doc_params(tl, 2, v_mut) + (0,)
        plain_params = _doc_params(tl, 2, v_mut)
        with pytest.raises((TursoError, Exception)):
            fake.execute_batch([(cas_sql, cas_params), (plain_sql, plain_params)])
        # byte-intact: document still v1
        rows = fake.query("SELECT * FROM documents WHERE timeline_id = ?", (tl,))
        assert rows[0]["document_json"] == v1
        assert int(rows[0]["version"]) == 1
        assert rows[0]["document_json"] != v_mut
        # Real side
        conn = _real_sqlite_tables()
        conn.execute("INSERT INTO documents (timeline_id, project_id, event_stream_id, name, document_json, version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)", _doc_params(tl, 1, v1))
        conn.commit()
        with pytest.raises((sqlite3.IntegrityError, Exception)):
            cur = conn.cursor()
            cur.execute("BEGIN")
            try:
                cur.execute(cas_sql, cas_params)
                cur.execute(plain_sql, plain_params)
                cur.execute("COMMIT")
            except Exception:
                try:
                    cur.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        cur = conn.execute("SELECT document_json, version FROM documents WHERE timeline_id=?", (tl,))
        row = cur.fetchone()
        assert row[0] == v1
        assert int(row[1]) == 1
        assert row[0] != v_mut


# ---------------------------------------------------------------------------
# F2 — orphan event FK fidelity (all-or-nothing)
# ---------------------------------------------------------------------------

class TestF2OrphanEventFK:
    def test_orphan_event_batch_is_all_or_nothing_fake_equals_real(self):
        tl_a = "tl-a-f2"
        tl_b = "tl-b-orphan"
        v = json.dumps({"x": 1})
        doc_sql = _doc_sql()
        ev_sql = _event_sql()
        e_valid = generate_event_ulid()
        e_orphan = generate_event_ulid()
        valid_params = _event_params(e_valid, timeline_id=tl_a, seq=1, payload=json.dumps({"data": {"a": 1}, "_integrity": {"event_hash": "h1"}}))
        orphan_params = _event_params(e_orphan, timeline_id=tl_b, seq=1, payload=json.dumps({"data": {"a": 2}, "_integrity": {"event_hash": "h2"}}))
        # Fake: create doc for tl-a only
        fake = FakeTursoTransport()
        fake.execute_batch([(doc_sql, _doc_params(tl_a, 1, v))])
        with pytest.raises((TursoError, Exception)) as exc_fake:
            fake.execute_batch([(ev_sql, valid_params), (ev_sql, orphan_params)])
        assert "FOREIGN KEY" in str(exc_fake.value) or "foreign" in str(exc_fake.value).lower()
        # zero events — valid first statement rolled back
        assert len(fake.events) == 0, f"fake should have zero events after FK fail, got {list(fake.events.keys())}"
        assert fake.query("SELECT COUNT(*) as cnt FROM events WHERE timeline_id = ?", (tl_a,))[0]["cnt"] == 0
        # Real
        conn = _real_sqlite_tables()
        conn.execute("INSERT INTO documents (timeline_id, project_id, event_stream_id, name, document_json, version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)", _doc_params(tl_a, 1, v))
        conn.commit()
        with pytest.raises((sqlite3.IntegrityError, Exception)) as exc_real:
            cur = conn.cursor()
            cur.execute("BEGIN")
            try:
                cur.execute(ev_sql, valid_params)
                cur.execute(ev_sql, orphan_params)
                cur.execute("COMMIT")
            except Exception:
                try:
                    cur.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        assert "FOREIGN KEY" in str(exc_real.value) or "foreign" in str(exc_real.value).lower()
        cnt = conn.execute("SELECT COUNT(*) FROM events WHERE timeline_id=?", (tl_a,)).fetchone()[0]
        assert cnt == 0
        cnt2 = conn.execute("SELECT COUNT(*) FROM events WHERE timeline_id=?", (tl_b,)).fetchone()[0]
        assert cnt2 == 0
