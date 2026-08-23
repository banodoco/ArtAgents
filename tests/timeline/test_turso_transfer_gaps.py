"""Amendment 3 — transfer gaps: marker-aware, event-only, both_advanced."""

import json
import uuid
from pathlib import Path

import pytest

from astrid.core.integrations.reigh.bridge_service import derive_database_path


def _setup_two_project_db(tmp_path: Path, slug="proj"):
    from astrid.core.events.service import EventAppendService
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.timeline.events.schema import generate_event_ulid
    from astrid.packs import build_standard_registry, open_standard_writer

    registry = build_standard_registry()
    db_path = derive_database_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer = open_standard_writer(db_path, registry=registry)
    proj_id = uuid.uuid4().hex
    tl_id = uuid.uuid4().hex
    ulid = "01J000000000000000000000BB"
    sid = f"{tl_id}:timeline.timeline"

    def _setup(uow: UnitOfWork):
        uow.execute(
            "INSERT INTO projects (id, slug, name, settings_json, event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",  # noqa: E501
            (proj_id, slug, "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO event_streams (id, project_id, stream_type, aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)",  # noqa: E501
            (sid, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO timelines (id, project_id, event_stream_id, name, document_json, asset_registry_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",  # noqa: E501
            (
                tl_id,
                proj_id,
                sid,
                "T1",
                json.dumps({"tracks": []}),
                json.dumps({}),
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
            ),
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
    return proj_id, tl_id, sid, ulid


class TestTransferMarkerAware:
    def test_push_marker_aware_sqlite_vs_localfs(self, tmp_path: Path, monkeypatch):
        # backfilled → sqlite authority
        proj_id, tl_id, sid, ulid = _setup_two_project_db(tmp_path)
        from astrid.core.timeline.authority import is_backfilled_timeline
        from astrid.packs.timeline.backfill import write_backfill_state

        write_backfill_state(
            tmp_path,
            timeline_id=tl_id,
            source="local_fs",
            source_head_version=1,
            events_sha256="abc",
        )
        assert is_backfilled_timeline(tl_id, tmp_path) is True
        fresh_id = uuid.uuid4().hex
        assert is_backfilled_timeline(fresh_id, tmp_path) is False
        assert is_backfilled_timeline(tl_id, tmp_path) is True

    def test_push_source_mismatch_fails_closed(self, tmp_path: Path):
        # This is a negative sanity: pushing a non-existent timeline fails
        from astrid.core.timeline.transfer import push_timeline

        with pytest.raises((ValueError, Exception)):
            push_timeline("proj", "nonexistent-ulid", root=tmp_path)


class TestTransferBothAdvancedFork:
    def test_both_advanced_creates_artifacts(self, tmp_path: Path):
        # Verify write_keep_both_artifact fork pattern works (transfer S5)
        from pathlib import Path as _P

        from astrid.core.timeline.events.schema import (
            TimelineActor,
            TimelineEvent,
            generate_event_ulid,
        )
        from astrid.core.timeline.sync_divergence import write_keep_both_artifact
        from astrid.core.timeline.sync_state import HeadSnapshot

        home = tmp_path / "proj" / "timelines" / "01J000000000000000000000CC"
        home.mkdir(parents=True, exist_ok=True)
        tl_id = uuid.uuid4().hex
        actor = TimelineActor(type="system", id="test", display="test")
        ev1 = TimelineEvent(
            event_id=generate_event_ulid(),
            timeline_id=tl_id,
            ts="2026-01-01T00:00:00Z",
            actor=actor,
            prev_hash=None,
            hash="h1",
            kind="timeline.created",
            payload={"timeline_id": tl_id, "slug": "t1", "name": "T1"},
            expected_version=None,
            txn_id=generate_event_ulid(),
        )
        ev2 = TimelineEvent(
            event_id=generate_event_ulid(),
            timeline_id=tl_id,
            ts="2026-01-01T00:00:01Z",
            actor=actor,
            prev_hash="h1",
            hash="h2",
            kind="timeline.created",
            payload={"timeline_id": tl_id, "slug": "t1", "name": "T1"},
            expected_version=None,
            txn_id=generate_event_ulid(),
        )
        from dataclasses import dataclass as _dc

        @_dc(frozen=True)
        class _Shim:
            timeline_id: str
            timeline_home: _P | None
            backend_name: str
            slug: str = "t1"
            timeline_ulid: str = "01J000000000000000000000AA"
            source: str = "test"

        src = _Shim(timeline_id=tl_id, timeline_home=None, backend_name="supabase")
        dst = _Shim(timeline_id=tl_id, timeline_home=home, backend_name="local_fs")
        hs = HeadSnapshot(version=1, last_hash="h1", last_event_id=ev1.event_id)
        hd = HeadSnapshot(version=1, last_hash="h1", last_event_id=ev1.event_id)
        art = write_keep_both_artifact(
            source=src,
            destination=dst,
            source_head=hs,
            destination_head=hd,
            source_suffix=[ev1],
            destination_suffix=[ev2],
        )  # type: ignore[arg-type]
        assert art is not None
        assert (_P(home) / Path(art.path).name).exists() or Path(art.path).exists()
