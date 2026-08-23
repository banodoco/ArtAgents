# ruff: noqa: E501
"""S4 rework-20 — provenance-equivalent head gate pins (RED→GREEN quoted)."""

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
    _heads_event_equal,
    _heads_provenance_equivalent,
    pull_from_turso,
    push_to_turso,
    read_turso_sync_state,
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


def _set_local_document(tmp_path: Path, tl_id: str, doc: dict):
    db_path = derive_database_path(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE timelines SET document_json = ? WHERE id = ?", (json.dumps(doc), tl_id))
    conn.commit()
    conn.close()


def _establish_provenance_baseline(tmp_path: Path):
    proj_id, tl_id, sid, home = _make_local_db(tmp_path)
    backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
    fake = FakeTursoTransport()
    replica = TursoReplicaClient(fake)
    r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
    assert r1.action in ("pushed", "up_to_date")
    eid = generate_event_ulid()
    payload_json = json.dumps({"data": {"x": 1}, "_integrity": {"event_hash": "h-remote-2", "previous_event_hash": None}})
    fake.events[eid] = {
        "event_id": eid,
        "timeline_id": tl_id,
        "project_id": proj_id,
        "stream_id": sid,
        "seq": 2,
        "kind": "custom.event",
        "payload_json": payload_json,
        "actor_kind": "system",
        "actor_id": "system",
        "txn_id": generate_event_ulid(),
        "idempotency_key": f"remote:{eid}",
        "created_at": "2026-01-01T00:00:02Z",
    }
    fake.documents[tl_id]["version"] = 2
    fake.documents[tl_id]["document_json"] = json.dumps({"tracks": []})
    backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
    r2 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
    assert r2.action == "pulled", f"baseline pull should apply: {r2!r}"
    assert r2.pulled == 1
    backend3 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
    state = read_turso_sync_state(home)
    assert state is not None
    return proj_id, tl_id, sid, home, fake, replica, backend3, state


class TestPostPullSteadyStateDivergence:
    def test_same_type_value_divergence_after_pull_triggers_conflict_within_one_poll(self, tmp_path: Path):
        proj_id, tl_id, sid, home, fake, replica, _backend, _state = _establish_provenance_baseline(tmp_path)
        _set_local_document(tmp_path, tl_id, {"color": "red"})
        fake.documents[tl_id]["document_json"] = json.dumps({"color": "blue"})
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r3 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r3.action == "conflict", f"post-pull steady-state value divergence should fork within one poll: {r3!r}"
        assert r3.conflict_artifacts, "artifact missing"
        # repeated polls must stay conflict, never silent up_to_date
        for _ in range(3):
            b = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
            rr = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=b, replica=replica)
            assert rr.action == "conflict", f"persistent divergence poll should stay conflict, got {rr!r}"
            assert rr.conflict_artifacts


class TestRemoteAheadApplyWithPendingDivergence:
    def test_no_cursor_advance_past_boundary_without_artifact(self, tmp_path: Path):
        proj_id, tl_id, sid, home, fake, replica, _backend, state_before = _establish_provenance_baseline(tmp_path)
        _set_local_document(tmp_path, tl_id, {"v": True})
        fake.documents[tl_id]["document_json"] = json.dumps({"v": 1})
        eid2 = generate_event_ulid()
        payload_json2 = json.dumps({"data": {"y": 2}, "_integrity": {"event_hash": "h-remote-3", "previous_event_hash": None}})
        fake.events[eid2] = {
            "event_id": eid2,
            "timeline_id": tl_id,
            "project_id": proj_id,
            "stream_id": sid,
            "seq": 3,
            "kind": "custom.event",
            "payload_json": payload_json2,
            "actor_kind": "system",
            "actor_id": "system",
            "txn_id": generate_event_ulid(),
            "idempotency_key": f"remote2:{eid2}",
            "created_at": "2026-01-01T00:00:03Z",
        }
        fake.documents[tl_id]["version"] = 3
        fake.documents[tl_id]["document_json"] = json.dumps({"v": 1})
        state_before_pull = read_turso_sync_state(home)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r.action == "conflict", f"remote-ahead with pending divergence must conflict before advance: {r!r}"
        assert r.conflict_artifacts, "artifact must be present"
        assert getattr(r, "pulled", 0) == 0, f"pulled must be 0 when forking before advance, got {getattr(r, 'pulled', 0)}"
        state_after = read_turso_sync_state(home)
        if state_before_pull is not None and state_after is not None:
            assert state_after.remote_version == state_before_pull.remote_version, f"cursor advanced past divergence: before={state_before_pull} after={state_after}"
            assert state_after.remote_version != 3, f"cursor must not advance to remote version 3 past divergence: {state_after}"

class TestProvenanceEquivalentHeadsEqual:
    def test_provenance_chain_recognized_as_equal(self, tmp_path: Path):
        proj_id, tl_id, sid, home, fake, replica, backend, state = _establish_provenance_baseline(tmp_path)
        from astrid.core.timeline.sync_state import head_snapshot_from_backend

        local_head = head_snapshot_from_backend(backend)
        raw = replica.fetch_remote_head(tl_id)
        assert raw is not None
        remote_head = HeadSnapshot(version=int(raw["version"]), last_event_id=raw["last_event_id"], last_hash=raw["last_hash"])
        # remote_head is version 2, local_head also version 2 but raw ids differ (import remapped)
        assert local_head.version == remote_head.version == 2
        assert local_head.last_event_id != remote_head.last_event_id, "import should remap event id"
        assert not _heads_event_equal(local_head, HeadSnapshot(version=remote_head.version, last_event_id=remote_head.last_event_id, last_hash=remote_head.last_hash))
        assert _heads_provenance_equivalent(tl_id, local_head, remote_head, backend, tmp_path) is True, "provenance-equivalent heads must be equal"
        # negative: different version must not be equivalent
        fake_head_diff = HeadSnapshot(version=99, last_event_id=remote_head.last_event_id, last_hash=remote_head.last_hash)
        assert _heads_provenance_equivalent(tl_id, local_head, fake_head_diff, backend, tmp_path) is False
