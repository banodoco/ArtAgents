"""S4 rework-10 — Y1 atomic remote unit + Z1 pull-resume identity pins."""
# ruff: noqa: E501
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest

from astrid.core.timeline.eventlog.turso import (
    TursoDocumentRow,
    TursoError,
    TursoEventRow,
    TursoReplicaClient,
    TursoSyncError,
    TursoVersionRaceError,
)
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.packs import build_standard_registry, open_standard_writer


def _make_local_db(tmp_path: Path, project_slug: str = "proj"):
    from astrid.core.events.service import EventAppendService
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
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
            (tl_id, proj_id, sid, "T1", json.dumps({"clips": [], "tracks": []}), json.dumps({"assets": {}}), "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
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


def _advance_local_to_v2(tmp_path: Path, proj_id: str, tl_id: str, sid: str):
    from astrid.core.events.service import EventAppendService
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
    from astrid.core.receipts.canonical import canonical_json
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.util.time import utc_now_iso

    registry = build_standard_registry()
    db_path = derive_database_path(tmp_path)
    writer = open_standard_writer(db_path, registry=registry)
    svc = EventAppendService(registry)
    our_config = {"clips": [], "tracks": [{"id": "t1", "kind": "visual", "label": "Ours"}]}
    our_doc_json = canonical_json(our_config)

    def _adv(uow: UnitOfWork):
        uow.execute(
            "UPDATE timelines SET document_json=?, asset_registry_json=?, updated_at=? WHERE id=?",
            (our_doc_json, canonical_json({"assets": {}}), utc_now_iso(), tl_id),
        )
        svc.append(
            uow,
            stream_id=sid,
            project_id=proj_id,
            event_kind="timeline.saved",
            data={"config": our_config, "registry": {"assets": {}}},
            changes=["config"],
            idempotency_key=f"adv:{tl_id}:2",
            txn_id=generate_event_ulid(),
            actor_kind="system",
            event_id=generate_event_ulid(),
        )

    UnitOfWork(writer).run(_adv)
    writer.close()
    return our_config, our_doc_json


# ---------------------------------------------------------------------------
# Y1a same-version-different-content race
# ---------------------------------------------------------------------------


class TestY1aSameVersionDifferentContent:
    def test_same_version_different_content_race(self, tmp_path: Path):
        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
        from astrid.core.timeline.turso_sync import push_to_turso

        proj_id, tl_id, sid, home = _make_local_db(tmp_path, project_slug="proj-y1a")
        replica_path = tmp_path / "replica_y1a.db"
        _init_replica_db(replica_path)
        transport = _RealReplicaTransport(replica_path)
        replica = TursoReplicaClient(transport)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # local advances to v2 ours
        _advance_local_to_v2(tmp_path, proj_id, tl_id, sid)
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        # intercept: competitor doc-write lands AFTER classification but BEFORE batch
        orig_push = replica.push_timeline_updates

        def _wrapped(doc, events, require_document=True, expected_remote_version=None):
            conn = sqlite3.connect(str(replica_path))
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(
                "UPDATE documents SET document_json=?, version=?, name=?, updated_at=? WHERE timeline_id=?",
                ('{"owner":"theirs"}', 2, "theirs", "2026-08-23T00:00:00Z", tl_id),
            )
            conn.commit()
            conn.close()
            return orig_push(doc, events, require_document=require_document, expected_remote_version=expected_remote_version)

        replica.push_timeline_updates = _wrapped  # type: ignore[method-assign]
        with pytest.raises((TursoVersionRaceError, TursoSyncError, TursoError)):
            push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        rows = transport.query("SELECT * FROM documents WHERE timeline_id=?", (tl_id,))
        assert rows and rows[0]["document_json"] == '{"owner":"theirs"}'
        assert rows[0]["name"] == "theirs"
        cnt = transport.query("SELECT COUNT(*) as cnt FROM events WHERE timeline_id=?", (tl_id,))[0]["cnt"]
        assert int(cnt) == 1


# ---------------------------------------------------------------------------
# Y1b different-version race (version 5)
# ---------------------------------------------------------------------------


class TestY1bDifferentVersionRace:
    def test_different_version_race(self, tmp_path: Path):
        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
        from astrid.core.timeline.turso_sync import push_to_turso

        proj_id, tl_id, sid, home = _make_local_db(tmp_path, project_slug="proj-y1b")
        replica_path = tmp_path / "replica_y1b.db"
        _init_replica_db(replica_path)
        transport = _RealReplicaTransport(replica_path)
        replica = TursoReplicaClient(transport)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        _advance_local_to_v2(tmp_path, proj_id, tl_id, sid)
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        orig_push = replica.push_timeline_updates

        def _wrapped(doc, events, require_document=True, expected_remote_version=None):
            conn = sqlite3.connect(str(replica_path))
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(
                "UPDATE documents SET document_json=?, version=?, name=?, updated_at=? WHERE timeline_id=?",
                ('{"owner":"theirs-v5"}', 5, "theirs5", "2026-08-23T00:00:00Z", tl_id),
            )
            conn.commit()
            conn.close()
            return orig_push(doc, events, require_document=require_document, expected_remote_version=expected_remote_version)

        replica.push_timeline_updates = _wrapped  # type: ignore[method-assign]
        with pytest.raises((TursoVersionRaceError, TursoSyncError, TursoError)):
            push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        rows = transport.query("SELECT * FROM documents WHERE timeline_id=?", (tl_id,))
        assert rows and rows[0]["document_json"] == '{"owner":"theirs-v5"}'
        cnt = transport.query("SELECT COUNT(*) as cnt FROM events WHERE timeline_id=?", (tl_id,))[0]["cnt"]
        assert int(cnt) == 1


# ---------------------------------------------------------------------------
# Y1 success path (no race)
# ---------------------------------------------------------------------------


class TestY1SuccessPath:
    def test_success_path_pushes_doc_and_events(self, tmp_path: Path):
        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
        from astrid.core.timeline.turso_sync import push_to_turso
        proj_id, tl_id, sid, home = _make_local_db(tmp_path, project_slug="proj-y1c")
        replica_path = tmp_path / "replica_y1c.db"
        _init_replica_db(replica_path)
        transport = _RealReplicaTransport(replica_path)
        replica = TursoReplicaClient(transport)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        our_cfg, our_doc_json = _advance_local_to_v2(tmp_path, proj_id, tl_id, sid)
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "pushed"
        rows = transport.query("SELECT * FROM documents WHERE timeline_id=?", (tl_id,))
        assert rows and int(rows[0]["version"]) == 2
        assert rows[0]["document_json"] == our_doc_json
        cnt = transport.query("SELECT COUNT(*) as cnt FROM events WHERE timeline_id=?", (tl_id,))[0]["cnt"]
        assert int(cnt) == 2


# ---------------------------------------------------------------------------
# Z1 distinct-history fork
# ---------------------------------------------------------------------------


class TestZ1DistinctHistoryFork:
    def test_distinct_history_fork(self, tmp_path: Path):
        from astrid.core.events.service import build_integrity_envelope
        from astrid.core.receipts.canonical import canonical_json
        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
        from astrid.core.timeline.turso_sync import pull_from_turso, push_to_turso
        from astrid.core.util.time import utc_now_iso

        proj_id, tl_id, sid, home = _make_local_db(tmp_path, project_slug="proj-z1a")
        replica_path = tmp_path / "replica_z1a.db"
        _init_replica_db(replica_path)
        transport = _RealReplicaTransport(replica_path)
        replica = TursoReplicaClient(transport)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # local appends seq-2 id-A (valid timeline.saved)
        our_cfg, _ = _advance_local_to_v2(tmp_path, proj_id, tl_id, sid)
        backend_local = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        local_events = backend_local.read_events()
        assert len(local_events) == 2
        local_last = local_events[-1]
        # fetch local payload_json for byte-identical remote
        from astrid.core.integrations.reigh.bridge_service import derive_database_path

        db_local = derive_database_path(tmp_path)
        conn = sqlite3.connect(str(db_local))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT payload_json, seq FROM events WHERE event_id=?", (local_last.event_id,)).fetchone()
        conn.close()
        assert row is not None
        payload_json_local = str(row["payload_json"])
        seq_remote = int(row["seq"])
        # remote independently appends BYTE-IDENTICAL payload seq-2 id-B (fresh envelope)
        # Build fresh envelope to demonstrate same bytes; then verify equality
        prev_hash = local_events[0].hash
        # Re-build envelope from same data to prove byte-identical construction path
        data = json.loads(payload_json_local).get("data", {})
        env2, _h2 = build_integrity_envelope(data, prev_hash)
        pj2 = canonical_json(env2)
        # The canonical envelope should be byte-equal to stored payload (both use same canonical json)
        assert json.loads(pj2) == json.loads(payload_json_local)
        ev_id_remote = generate_event_ulid()
        # ensure different id
        assert ev_id_remote != local_last.event_id
        # Insert remote doc v2 (same content as local) + identical payload but different id
        # Read local doc json
        conn2 = sqlite3.connect(str(db_local))
        conn2.row_factory = sqlite3.Row
        doc_row = conn2.execute("SELECT document_json, name FROM timelines WHERE id=?", (tl_id,)).fetchone()
        conn2.close()
        local_doc_json = str(doc_row["document_json"])
        local_name = str(doc_row["name"])
        conn3 = sqlite3.connect(str(replica_path))
        conn3.execute("PRAGMA foreign_keys=ON")
        conn3.execute(
            "UPDATE documents SET document_json=?, version=?, name=?, updated_at=? WHERE timeline_id=?",
            (local_doc_json, 2, local_name, utc_now_iso(), tl_id),
        )
        conn3.execute(
            "INSERT INTO events (event_id, timeline_id, project_id, stream_id, seq, kind, payload_json, actor_kind, actor_id, txn_id, idempotency_key, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ev_id_remote,
                tl_id,
                proj_id,
                sid,
                seq_remote,
                "timeline.saved",
                payload_json_local,
                "system",
                "system",
                generate_event_ulid(),
                f"remote:{ev_id_remote}",
                utc_now_iso(),
            ),
        )
        conn3.commit()
        conn3.close()
        # clean pull -> conflict exactly 1 artifact pair
        backend_pull = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        res = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend_pull, replica=replica)
        assert res.action == "conflict"
        assert len(res.conflict_artifacts) == 1
        after = list(Path(home).glob("divergence-*.json"))
        # artifact pair = .json + .diagnostic.json for same stem
        json_files = [p for p in after if not p.name.endswith(".diagnostic.json")]
        diag_files = [p for p in after if p.name.endswith(".diagnostic.json")]
        assert len(json_files) == 1
        assert len(diag_files) == 1


# ---------------------------------------------------------------------------
# Z1 X1 crash-resume trace
# ---------------------------------------------------------------------------


class TestZ1CrashResume:
    def test_crash_resume_trace(self, tmp_path: Path, monkeypatch):
        from astrid.core.events.service import build_integrity_envelope
        from astrid.core.receipts.canonical import canonical_json
        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
        from astrid.core.timeline.turso_sync import TursoSyncError, pull_from_turso, push_to_turso
        from astrid.core.util.time import utc_now_iso

        proj_id, tl_id, sid, home = _make_local_db(tmp_path, project_slug="proj-z1b")
        replica_path = tmp_path / "replica_z1b.db"
        _init_replica_db(replica_path)
        transport = _RealReplicaTransport(replica_path)
        replica = TursoReplicaClient(transport)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # remote advances alone (doc v2 + valid seq-2 event)
        backend_head = backend.read_events()
        prev_hash = backend_head[-1].hash if backend_head else None
        doc_v2_json = canonical_json({"clips": [], "tracks": [{"id": "t1", "kind": "visual", "label": "Remote"}]})
        ev_id_remote = generate_event_ulid()
        payload_data = {"config": {"clips": [], "tracks": [{"id": "t1", "kind": "visual", "label": "Remote"}]}, "registry": {"assets": {}}}
        env, _h = build_integrity_envelope(payload_data, prev_hash)
        pj = canonical_json(env)
        # need to push via replica client with expected version 1
        doc_v2 = TursoDocumentRow(
            timeline_id=tl_id,
            project_id=proj_id,
            event_stream_id=sid,
            name="T1",
            document_json=doc_v2_json,
            version=2,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        ev_row = TursoEventRow(
            timeline_id=tl_id,
            project_id=proj_id,
            stream_id=sid,
            seq=2,
            kind="timeline.saved",
            payload_json=pj,
            actor_kind="system",
            actor_id="system",
            txn_id=generate_event_ulid(),
            idempotency_key=f"remote:{ev_id_remote}",
            created_at=utc_now_iso(),
            event_id=ev_id_remote,
        )
        replica.push_timeline_updates(doc_v2, [ev_row], require_document=True, expected_remote_version=1)
        # pull with write_turso_sync_state monkeypatched to raise OSError => typed TursoSyncError
        import astrid.core.timeline.turso_sync as sync_mod

        orig = sync_mod.write_turso_sync_state

        def failing(*_a, **_kw):
            raise OSError("injected crash")

        monkeypatch.setattr(sync_mod, "write_turso_sync_state", failing)
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        with pytest.raises(TursoSyncError):
            pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        monkeypatch.setattr(sync_mod, "write_turso_sync_state", orig)
        # capture remote count before retry
        cnt_before = transport.query("SELECT COUNT(*) as cnt FROM events WHERE timeline_id=?", (tl_id,))[0]["cnt"]
        arts_before = list(Path(home).glob("divergence-*.json"))
        backend3 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend3, replica=replica)
        assert r2.action in ("pulled", "up_to_date")
        assert len(r2.conflict_artifacts) == 0
        arts_after = list(Path(home).glob("divergence-*.json"))
        assert len(arts_after) == len(arts_before)
        cnt_after = transport.query("SELECT COUNT(*) as cnt FROM events WHERE timeline_id=?", (tl_id,))[0]["cnt"]
        assert int(cnt_after) == int(cnt_before)
        # provenance: applied local event carries source_event_id == remote event id
        backend_final = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        evs = backend_final.read_events()
        # last event should be the imported remote
        last = evs[-1]
        assert getattr(last, "source_event_id", None) == ev_id_remote
