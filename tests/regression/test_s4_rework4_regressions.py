"""S4 rework-4 — Q7 RED→GREEN: destination_only no-op + stale-doc guard."""
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
    TursoEventRow,
    TursoReplicaClient,
)
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.turso_sync import TursoSyncError, push_to_turso, read_turso_sync_state


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


class TestQ7aDestinationOnlyNoClobber:
    """Oracle exact probe: bootstrap → remote diverges alone → push must be no-op."""

    def test_remote_advances_alone_push_is_up_to_date_no_clobber(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        res0 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert res0.action == "pushed"
        cursor_before = read_turso_sync_state(home)
        assert cursor_before is not None
        remote_before = replica.fetch_remote_head(tl_id)
        assert remote_before is not None
        events_before = replica.fetch_remote_events(tl_id)
        count_before = len(events_before)

        # Remote advances alone: bump document version, change name, add one event
        from astrid.core.timeline.turso_sync import _read_local_document_snapshot

        local_doc = _read_local_document_snapshot(tl_id, tmp_path)
        remote_doc_row = local_doc.__class__(
            timeline_id=local_doc.timeline_id,
            project_id=local_doc.project_id,
            event_stream_id=local_doc.event_stream_id,
            name="T1-REMOTE",
            document_json=json.dumps({"tracks": [], "name": "T1-REMOTE"}),
            version=local_doc.version + 1,
            created_at=local_doc.created_at,
            updated_at="2026-01-02T00:00:00Z",
        )
        eid = generate_event_ulid()
        fake_event = TursoEventRow(
            event_id=eid,
            timeline_id=tl_id,
            project_id=proj_id,
            stream_id=sid,
            seq=999,
            kind="timeline.saved",
            payload_json=json.dumps({"data": {"note": "remote-only"}, "_integrity": {"event_hash": "rh1", "previous_event_hash": None}}),
            actor_kind="system",
            actor_id="remote",
            txn_id=generate_event_ulid(),
            idempotency_key=f"remote:{eid}",
            created_at="2026-01-02T00:00:00Z",
        )
        replica.push_timeline_updates(remote_doc_row, [fake_event], require_document=True)
        remote_mid = replica.fetch_remote_head(tl_id)
        assert remote_mid["version"] == local_doc.version + 1
        assert remote_mid["document"]["name"] == "T1-REMOTE"
        count_mid = len(replica.fetch_remote_events(tl_id))
        assert count_mid == count_before + 1

        # Local does NOTHING — push should be up_to_date, no clobber
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        result = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert result.action == "up_to_date"
        assert result.local_version == remote_mid["version"] - 1  # local still behind
        assert result.remote_version == remote_mid["version"]
        # remote doc unchanged
        remote_after = replica.fetch_remote_head(tl_id)
        assert remote_after["version"] == remote_mid["version"]
        assert remote_after["document"]["name"] == "T1-REMOTE"
        # zero new remote events
        assert len(replica.fetch_remote_events(tl_id)) == count_mid
        # cursor untouched
        cursor_after = read_turso_sync_state(home)
        assert cursor_after == cursor_before


class TestQ7bStaleDocumentGuard:
    """Belt-and-braces: stale doc version < remote must raise typed error, remote untouched."""

    def test_stale_snapshot_raises_typed_and_remote_untouched(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        cursor_before = read_turso_sync_state(home)

        # Make remote ahead
        from astrid.core.timeline.turso_sync import _read_local_document_snapshot

        local_doc = _read_local_document_snapshot(tl_id, tmp_path)
        remote_doc_row = local_doc.__class__(
            timeline_id=local_doc.timeline_id,
            project_id=local_doc.project_id,
            event_stream_id=local_doc.event_stream_id,
            name="T1-REMOTE2",
            document_json=json.dumps({"tracks": [], "name": "T1-REMOTE2"}),
            version=local_doc.version + 1,
            created_at=local_doc.created_at,
            updated_at="2026-01-02T00:00:00Z",
        )
        eid = generate_event_ulid()
        fake_event = TursoEventRow(
            event_id=eid,
            timeline_id=tl_id,
            project_id=proj_id,
            stream_id=sid,
            seq=999,
            kind="timeline.saved",
            payload_json=json.dumps({"data": {"note": "remote2"}, "_integrity": {"event_hash": "rh2", "previous_event_hash": None}}),
            actor_kind="system",
            actor_id="remote",
            txn_id=generate_event_ulid(),
            idempotency_key=f"remote2:{eid}",
            created_at="2026-01-02T00:00:00Z",
        )
        replica.push_timeline_updates(remote_doc_row, [fake_event], require_document=True)
        remote_before = replica.fetch_remote_head(tl_id)
        count_before = len(replica.fetch_remote_events(tl_id))

        # Force classification bypass: pretend source_only even though doc is stale
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        with patch("astrid.core.timeline.turso_sync.classify_sync_state", return_value="source_only"):
            with pytest.raises(TursoSyncError, match=r"stale document|fork required"):
                push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)

        # remote untouched
        remote_after = replica.fetch_remote_head(tl_id)
        assert remote_after["version"] == remote_before["version"]
        assert remote_after["document"]["name"] == "T1-REMOTE2"
        assert len(replica.fetch_remote_events(tl_id)) == count_before
        # cursor untouched
        assert read_turso_sync_state(home) == cursor_before
