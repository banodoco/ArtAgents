"""W4 — Selector isolation proof: build_timeline_backend NEVER returns Turso."""

import json
import uuid
from pathlib import Path

import pytest

from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.timeline.eventlog.selector import build_timeline_backend, select_timeline_stream
from astrid.core.timeline.eventlog.types import EventLogError


def _ensure_proj(tmp_path: Path, slug: str = "proj") -> tuple[str, str]:
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
    ulid = "01J000000000000000000000AA"
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
    return proj_id, tl_id


class TestSelectorNeverTurso:
    def test_unbackfilled_local_fs(self, tmp_path: Path):
        _, tl_id = _ensure_proj(tmp_path)
        home = tmp_path / "proj" / "timelines" / "01J000000000000000000000AA"
        home.mkdir(parents=True, exist_ok=True)
        stream = select_timeline_stream(timeline_id=tl_id, timeline_home=home)
        backend = build_timeline_backend(stream)
        assert backend.backend_name() in ("local_fs", "sqlite")
        assert backend.backend_name() != "turso"

    def test_backfilled_sqlite(self, tmp_path: Path):
        _, tl_id = _ensure_proj(tmp_path)
        from astrid.packs.timeline.backfill import write_backfill_state

        write_backfill_state(
            tmp_path,
            timeline_id=tl_id,
            source="local_fs",
            source_head_version=1,
            events_sha256="abc",
        )
        home = tmp_path / "proj" / "timelines" / "01J000000000000000000000AA"
        home.mkdir(parents=True, exist_ok=True)
        stream = select_timeline_stream(timeline_id=tl_id, timeline_home=home)
        backend = build_timeline_backend(stream)
        assert backend.backend_name() == "sqlite"
        assert backend.backend_name() != "turso"

    def test_garbage_marker_fails_closed(self, tmp_path: Path):
        _, tl_id = _ensure_proj(tmp_path)
        marker = tmp_path / ".astrid" / "backfill-state.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("{ not json")
        home = tmp_path / "proj" / "timelines" / "01J000000000000000000000AA"
        home.mkdir(parents=True, exist_ok=True)
        stream = select_timeline_stream(timeline_id=tl_id, timeline_home=home)
        with pytest.raises((EventLogError, Exception), match="unreadable"):
            build_timeline_backend(stream)

    def test_supabase_preferred_still_not_turso(self, tmp_path: Path):
        _, tl_id = _ensure_proj(tmp_path)
        from astrid.core.timeline.eventlog.types import SupabaseEventLogOptions

        opts = SupabaseEventLogOptions(
            url="https://example.supabase.co",
            auth_token="tok",
            verified_subject="sub",
            actor_id="a",
            actor_display="A",
        )
        stream = select_timeline_stream(
            timeline_id=tl_id, preferred_backend="supabase", supabase_options=opts
        )
        backend = build_timeline_backend(stream)
        assert backend.backend_name() == "supabase"
        assert backend.backend_name() != "turso"

    def test_no_turso_backend_constructed_implicitly(self, tmp_path: Path):
        # grep proof: no code path in selector returns turso
        import pathlib

        selector_src = (
            pathlib.Path(__file__).parents[2]
            / "astrid"
            / "core"
            / "timeline"
            / "eventlog"
            / "selector.py"
        ).read_text()
        assert "turso" not in selector_src.lower()
