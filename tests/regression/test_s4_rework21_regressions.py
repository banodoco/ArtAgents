# ruff: noqa: E501
"""S4 rework-21 — bookmark-less fork + anchored provenance equivalence pins."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import FakeTursoTransport, TursoReplicaClient
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.sync_state import HeadSnapshot
from astrid.core.timeline.turso_sync import (
    TURSO_SYNC_STATE_FILENAME,
    _heads_provenance_equivalent,
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


def _wipe_sync_state(home: Path):
    for p in home.glob("*sync-state*"):
        try:
            p.unlink()
        except Exception:
            pass
    for p in home.glob("*.json"):
        if "turso" in p.name:
            try:
                p.unlink()
            except Exception:
                pass
    sp = home / TURSO_SYNC_STATE_FILENAME
    if sp.exists():
        sp.unlink()


def _seed_via_push(tmp_path: Path, tl_id: str, home: Path, fake: FakeTursoTransport, replica: TursoReplicaClient, local_doc: dict, remote_doc_str: str | dict | None = None):
    backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
    res = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
    assert res.action in ("pushed", "up_to_date")
    db_path = derive_database_path(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE timelines SET document_json = ? WHERE id = ?", (json.dumps(local_doc), tl_id))
    conn.commit()
    conn.close()
    if remote_doc_str is not None:
        raw = remote_doc_str if isinstance(remote_doc_str, str) else json.dumps(remote_doc_str)
        fake.documents[tl_id]["document_json"] = raw


class TestBookmarkLessFiniteDivergentPush:
    def test_bookmark_less_finite_divergent_push_conflict(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        _seed_via_push(tmp_path, tl_id, home, fake, replica, local_doc={"v": 1}, remote_doc_str={"v": 2})
        _wipe_sync_state(home)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        result = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert result.action == "conflict", f"bookmark-less finite divergent push should fork, got {result.action} {result!r}"
        assert result.conflict_artifacts, "conflict must have artifacts"


class TestBookmarkLessRemoteNonFinitePush:
    def test_bookmark_less_remote_nan_push_conflict(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        _seed_via_push(tmp_path, tl_id, home, fake, replica, local_doc={"v": 1}, remote_doc_str='{"v": NaN}')
        _wipe_sync_state(home)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        result = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert result.action == "conflict", f"bookmark-less remote NaN push should fork, got {result.action} {result!r}"
        assert result.conflict_artifacts


class TestPullBookmarkLessDivergentStaysConflict:
    def test_pull_bookmark_less_divergent_stays_conflict(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        _seed_via_push(tmp_path, tl_id, home, fake, replica, local_doc={"v": 1}, remote_doc_str={"v": 2})
        _wipe_sync_state(home)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        result = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert result.action == "conflict", f"pull bookmark-less divergent should fork, got {result.action}"
        assert result.conflict_artifacts


class TestForgedNativeHeadProvenance:
    def test_forged_native_head_not_equivalent(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        from astrid.core.timeline.sync_state import head_snapshot_from_backend

        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        local_head = head_snapshot_from_backend(backend)
        remote_id = "01FORGEDREMOTEID0000000000000A"
        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE events SET source_event_id = ?, source_backend = NULL, source_timeline_id = NULL WHERE event_id = ?", (remote_id, str(local_head.last_event_id)))
        conn.commit()
        conn.close()
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        local_head2 = head_snapshot_from_backend(backend2)
        remote_head = HeadSnapshot(version=local_head2.version, last_event_id=remote_id, last_hash="h-forged")
        result = _heads_provenance_equivalent(tl_id, local_head2, remote_head, backend2, tmp_path)
        assert result is False, f"forged native-head provenance should be not-equivalent, got {result}"


class TestUnrelatedOlderEventMatch:
    def test_unrelated_older_event_not_equivalent(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        eid2 = generate_event_ulid()
        payload = json.dumps({"data": {"x": 1}, "_integrity": {"event_hash": "h2", "previous_event_hash": None}})
        fake.events[eid2] = {"event_id": eid2, "timeline_id": tl_id, "project_id": proj_id, "stream_id": sid, "seq": 2, "kind": "custom.event", "payload_json": payload, "actor_kind": "system", "actor_id": "system", "txn_id": generate_event_ulid(), "idempotency_key": f"remote:{eid2}", "created_at": "2026-01-01T00:00:02Z"}
        fake.documents[tl_id]["version"] = 2
        fake.documents[tl_id]["document_json"] = json.dumps({"tracks": []})
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        backend3 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        from astrid.core.timeline.sync_state import head_snapshot_from_backend

        local_head = head_snapshot_from_backend(backend3)
        decoy_remote = "01DECOYREMOTEID000000000000B"
        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT event_id FROM events WHERE stream_id = ? ORDER BY seq ASC LIMIT 1", (sid,)).fetchone()
        oldest_id = row[0] if row else local_head.last_event_id
        conn.execute("UPDATE events SET source_event_id = ?, source_backend = ?, source_timeline_id = ? WHERE event_id = ?", (decoy_remote, "local_fs", tl_id, oldest_id))
        conn.commit()
        conn.close()
        backend4 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        local_head4 = head_snapshot_from_backend(backend4)
        remote_head = HeadSnapshot(version=local_head4.version, last_event_id=decoy_remote, last_hash="h-decoy")
        result = _heads_provenance_equivalent(tl_id, local_head4, remote_head, backend4, tmp_path)
        assert result is False, f"unrelated older event match should be not-equivalent, got {result}"


class TestLegitimateMultiGenerationChain:
    def test_legitimate_chain_equivalent(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        eid = generate_event_ulid()
        payload = json.dumps({"data": {"x": 2}, "_integrity": {"event_hash": "h-legit", "previous_event_hash": None}})
        fake.events[eid] = {"event_id": eid, "timeline_id": tl_id, "project_id": proj_id, "stream_id": sid, "seq": 2, "kind": "custom.event", "payload_json": payload, "actor_kind": "system", "actor_id": "system", "txn_id": generate_event_ulid(), "idempotency_key": f"remote:{eid}", "created_at": "2026-01-01T00:00:02Z"}
        fake.documents[tl_id]["version"] = 2
        fake.documents[tl_id]["document_json"] = json.dumps({"tracks": []})
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r.action == "pulled"
        backend3 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        from astrid.core.timeline.sync_state import head_snapshot_from_backend

        local_head = head_snapshot_from_backend(backend3)
        raw = replica.fetch_remote_head(tl_id)
        assert raw is not None
        remote_head = HeadSnapshot(version=int(raw["version"]), last_event_id=raw["last_event_id"], last_hash=raw["last_hash"])
        assert local_head.version == remote_head.version == 2
        assert _heads_provenance_equivalent(tl_id, local_head, remote_head, backend3, tmp_path) is True
