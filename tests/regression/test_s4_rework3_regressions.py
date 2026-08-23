"""S4 rework-3 — Q1-Q6 RED→GREEN pairs."""
# ruff: noqa: E501
from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import (
    FakeTursoTransport,
    TursoReplicaClient,
    apply_replica_schema,
    split_sql_statements,
)
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.sync_divergence import write_keep_both_artifact
from astrid.core.timeline.turso_sync import (
    TursoSyncError,
    pull_from_turso,
    push_to_turso,
    read_turso_sync_state,
)


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


class TestQ1PushBothAdvancedForks:
    def test_push_both_advanced_forks_without_overwrite(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        res = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert res.action == "pushed"
        # seed divergent remote: doc v+1 + 1 event (remote ahead)
        fake.documents[tl_id]["name"] = "T1-REMOTE"
        fake.documents[tl_id]["document_json"] = json.dumps({"tracks": [], "name": "T1-REMOTE"})
        fake.documents[tl_id]["version"] = 2
        eid_remote = generate_event_ulid()
        payload = json.dumps(
            {
                "data": {"timeline_id": tl_id, "config": {"clips": [], "tracks": []}},
                "_integrity": {"event_hash": "rh", "previous_event_hash": None},
            }
        )
        fake.events[eid_remote] = {
            "event_id": eid_remote,
            "timeline_id": tl_id,
            "project_id": proj_id,
            "stream_id": sid,
            "seq": 2,
            "kind": "timeline.saved",
            "payload_json": payload,
            "actor_kind": "system",
            "actor_id": "system",
            "txn_id": generate_event_ulid(),
            "idempotency_key": f"remote:{eid_remote}",
            "created_at": "2026-01-01T00:00:03Z",
        }
        # local ahead: append one local event
        _append_events(tmp_path, proj_id, tl_id, sid, 1)
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        cursor_before = read_turso_sync_state(home)
        assert cursor_before is not None
        # push should fork, not overwrite
        result = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert result.action == "conflict"
        assert len(result.conflict_artifacts) >= 1
        # remote doc unchanged
        assert fake.documents[tl_id]["name"] == "T1-REMOTE"
        assert json.loads(fake.documents[tl_id]["document_json"])["name"] == "T1-REMOTE"
        # artifact contains both suffixes with payload dicts
        art_path = Path(str(getattr(result.conflict_artifacts[0], "path", "")))
        assert art_path.exists()
        raw = json.loads(art_path.read_text())
        # both sides have suffix with payload
        assert "source" in raw and "destination" in raw
        for side in ("source", "destination"):
            assert "suffix" in raw[side]
            assert len(raw[side]["suffix"]) >= 1
            assert isinstance(raw[side]["suffix"][0].get("payload"), dict)
        # cursor unchanged
        cursor_after = read_turso_sync_state(home)
        assert cursor_after == cursor_before


class TestQ2PullUnfetchableFailClosed:
    def test_pull_remote_ahead_unfetchable_raises_and_cursor_untouched(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        # make remote ahead by bumping version and adding an event directly in fake
        fake.documents[tl_id]["version"] = 5
        eid = generate_event_ulid()
        payload = json.dumps({"data": {"x": 1}, "_integrity": {"event_hash": "h2", "previous_event_hash": None}})
        fake.events[eid] = {
            "event_id": eid,
            "timeline_id": tl_id,
            "project_id": proj_id,
            "stream_id": sid,
            "seq": 99,
            "kind": "timeline.saved",
            "payload_json": payload,
            "actor_kind": "system",
            "actor_id": "system",
            "txn_id": generate_event_ulid(),
            "idempotency_key": f"remote:{eid}",
            "created_at": "2026-01-01T00:00:04Z",
        }
        cursor_before = read_turso_sync_state(home)
        # patch fetch to return [] for both attempts
        with patch.object(replica, "fetch_remote_events", return_value=[]):
            with pytest.raises(TursoSyncError):
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        cursor_after = read_turso_sync_state(home)
        assert cursor_after == cursor_before
        # second pull still classifies remote-ahead (still raises)
        with patch.object(replica, "fetch_remote_events", return_value=[]):
            with pytest.raises(TursoSyncError):
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)


class TestQ3MarkerAwareTransferSqliteSource:
    def test_write_keep_both_artifact_sqlite_source_succeeds(self, tmp_path: Path):
        from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent
        from astrid.core.timeline.sync_state import HeadSnapshot

        # fake supabase backend shim
        class FakeSupabaseBackend:
            def __init__(self):
                self.calls = []

            def write_divergence(self, **kwargs):
                self.calls.append(kwargs)
                return {"id": "div1", "created_at": "2026-01-01T00:00:00Z", "timeline_id": "tid", "spoke": "local"}
        # Need to make destination backend be instance of SupabaseBackend for type check
        # Instead patch isinstance check by making Fake inherit? Simpler: test that source backend_name sqlite is accepted
        # We directly test the gate: write_keep_both_artifact with source sqlite should not raise TransferFailure at source gate
        # For that we need a proper SupabaseBackend-shaped target; we can mock the backend type check by patching
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend

        class DummySupabase(SupabaseBackend):  # type: ignore
            def __init__(self):
                pass

            def write_divergence(self, **kwargs):
                return {"id": "div1", "created_at": "2026-01-01T00:00:00Z", "timeline_id": "tid", "spoke": "local"}

        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Target:
            timeline_id: str
            timeline_home: Path | None
            backend: object
            backend_name: str
            slug: str = "t1"
            timeline_ulid: str = "01J000000000000000000000AA"
            source: str = "test"

        tid = uuid.uuid4().hex
        src = Target(timeline_id=tid, timeline_home=None, backend=object(), backend_name="sqlite")
        dst = Target(timeline_id=tid, timeline_home=None, backend=DummySupabase(), backend_name="supabase")
        # minimal heads/suffixes — use valid ULIDs
        eid = generate_event_ulid()
        head = HeadSnapshot(version=1, last_event_id=eid, last_hash="h1")
        ev = TimelineEvent(
            event_id=eid,
            timeline_id=tid,
            ts="2026-01-01T00:00:00Z",
            actor=TimelineActor(type="system", id="s", display="s"),
            prev_hash=None,
            hash="h1",
            kind="timeline.created",
            payload={"timeline_id": tid, "timeline_ulid": "01J000000000000000000000AA", "slug": "t1", "name": "T1"},
            expected_version=None,
            txn_id=generate_event_ulid(),
        )
        # should succeed without TransferFailure
        ref = write_keep_both_artifact(source=src, destination=dst, source_head=head, destination_head=head, source_suffix=[ev], destination_suffix=[ev])
        assert ref is not None


class TestQ4MarkerGatedEntry:
    def test_unmarked_timeline_rejected_both_entries(self, tmp_path: Path):
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
            uow.execute("INSERT INTO projects (id, slug, name, settings_json, event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)", (proj_id, "proj2", "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))
            uow.execute("INSERT INTO event_streams (id, project_id, stream_type, aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)", (sid, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"))
            uow.execute("INSERT INTO timelines (id, project_id, event_stream_id, name, document_json, asset_registry_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (tl_id, proj_id, sid, "T1", json.dumps({"tracks": []}), json.dumps({}), "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))

        UnitOfWork(writer).run(_setup)

        def _append(uow: UnitOfWork):
            svc = EventAppendService(registry)
            svc.append(uow, stream_id=sid, project_id=proj_id, event_kind="timeline.created", data={"timeline_id": tl_id, "timeline_ulid": ulid, "slug": "t1", "name": "T1"}, changes=["timeline_id", "slug", "name"], idempotency_key=f"create:{tl_id}", txn_id=generate_event_ulid(), actor_kind="system", event_id=generate_event_ulid())

        UnitOfWork(writer).run(_append)
        writer.close()
        home = tmp_path / "proj2" / "timelines" / ulid
        home.mkdir(parents=True, exist_ok=True)
        # deliberately NOT writing backfill marker -> unmarked
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        with pytest.raises(TursoSyncError):
            push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert len(fake.documents) == 0
        assert not (home / "turso-sync-state.json").exists()
        with pytest.raises(TursoSyncError):
            pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert not (home / "turso-sync-state.json").exists()


class TestQ5SplitterAndApply:
    def test_splitter_unit_cases(self):
        assert len(split_sql_statements("SELECT 1; SELECT 2;")) == 2
        assert len(split_sql_statements("SELECT 'a; b'; -- comment\n SELECT 2;")) == 2
        assert len(split_sql_statements("SELECT \"a; b\"; SELECT 2;")) == 2
        assert len(split_sql_statements("-- comment\n")) == 0
        assert len(split_sql_statements("SELECT 'a''b'; SELECT 2;")) == 2  # escaped single quote
        assert len(split_sql_statements("SELECT 1;  \n  ")) == 1

    def test_apply_real_schema_yields_tables_and_indexes(self):
        sql = Path("/workspace/goalmd-sqlite-20260822/repos/ArtAgents/packages/timeline-schema/sql/turso/0001_turso_replica_schema.sql").read_text()
        transport = FakeTursoTransport()
        stmts = apply_replica_schema(transport, sql)
        assert len(stmts) == 4
        tables = transport.query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        assert {r["name"] for r in tables} == {"documents", "events"}
        indexes = transport.query("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name;")
        assert {r["name"] for r in indexes} == {"events_stream_seq", "events_timeline_seq"}
