# ruff: noqa: E501
"""S4 rework-17 — C1 doc-identity + C2 honest push label pins (RED→GREEN quoted)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import FakeTursoTransport, TursoReplicaClient
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.turso_sync import pull_from_turso, push_to_turso
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


class TestC1DocByteDivergence:
    def test_equal_head_doc_divergence_push_is_conflict(self, tmp_path: Path):
        _, tl_id, _sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # out-of-band doc tamper at equal head
        orig_json = fake.documents[tl_id]["document_json"]
        fake.documents[tl_id]["document_json"] = json.dumps({"tampered": True, "orig": orig_json})
        # push must fork, not silently up_to_date
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "conflict"
        assert r2.conflict_artifacts and len(r2.conflict_artifacts) == 1
        arts = list(Path(home).glob("divergence-*.json"))
        assert len([p for p in arts if not p.name.endswith(".diagnostic.json")]) >= 1

    def test_equal_head_doc_divergence_pull_is_conflict(self, tmp_path: Path):
        _, tl_id, _sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        fake.documents[tl_id]["document_json"] = json.dumps({"tampered": 2})
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r3 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r3.action == "conflict"
        assert r3.conflict_artifacts and len(r3.conflict_artifacts) == 1

    def test_equal_head_doc_equal_stays_up_to_date(self, tmp_path: Path):
        _, tl_id, _sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # no tamper — byte-equal
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "up_to_date"
        assert not r2.conflict_artifacts
        r3 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r3.action == "up_to_date"
        assert not r3.conflict_artifacts


class TestC2RemoteOnlyHonestLabel:
    def test_push_remote_only_advance_not_up_to_date(self, tmp_path: Path):
        _, tl_id, _sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # seed one remote-only row: bump version + add event
        cur_version = int(fake.documents[tl_id]["version"])
        fake.documents[tl_id]["version"] = cur_version + 1
        # keep document_json same so head divergence is version-only
        new_eid = generate_event_ulid()
        payload = json.dumps({"data": {"note": "remote-only"}, "_integrity": {"event_hash": "h-" + new_eid, "previous_event_hash": None}})
        seq = max((int(v.get("seq", 0)) for v in fake.events.values()), default=0) + 1
        fake.events[new_eid] = {
            "event_id": new_eid,
            "timeline_id": tl_id,
            "project_id": fake.documents[tl_id]["project_id"],
            "stream_id": fake.documents[tl_id]["event_stream_id"],
            "seq": seq,
            "kind": "timeline.saved",
            "payload_json": payload,
            "actor_kind": "system",
            "actor_id": "system",
            "txn_id": "txn-remote",
            "idempotency_key": f"ik:{new_eid}",
            "created_at": "2026-01-01T00:00:01Z",
        }
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action != "up_to_date", f"push lied up_to_date with remote-ahead: {r2!r}"
        assert r2.action == "remote_ahead"
        assert r2.remote_version == cur_version + 1
        assert r2.local_version == cur_version
        # no cursor writes: state still at bootstrap version
        from astrid.core.timeline.turso_sync import read_turso_sync_state

        st = read_turso_sync_state(home)
        assert st is not None
        assert st.remote_version == cur_version
