"""W2-window regression: gateway whole-doc save atomicity."""

import tempfile
import shutil
from pathlib import Path
from unittest import mock

from astrid.core.foundation import project_paths
from astrid.core.timeline.events.schema import TimelineActor
from astrid.core.timeline._edit_helpers import pack_write_gateway

ROOT_ENV = project_paths.PROJECTS_ROOT_ENV


def _arrangement_event_with_config(config: dict | None = None):
    if config is None:
        config = {"tracks": [{"clips": [{"id": "new-clip"}]}]}
    return {"kind": "timeline.config_replaced", "payload": {"config": config, "asset_registry": {"assets": {}}}}


def test_gateway_atomic_no_old_bytes_newer_version():
    """Backfilled timeline → gateway save with config_replaced → serve read shows NEW bytes with version == head_seq."""
    import tempfile
    from pathlib import Path
    import shutil
    from astrid.application import compose_standard_application
    from astrid.core.project.project import create_project as fs_create_project
    from astrid.core.timeline.paths import find_timeline_by_slug
    from astrid.packs.timeline.repository import TimelineRepository
    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.packs.timeline.repository import TIMELINE_STREAM_TYPE

    tmp_root = Path(tempfile.mkdtemp(prefix="atomic-", dir="/tmp"))
    try:
        env = mock.patch.dict("os.environ", {ROOT_ENV: str(tmp_root)})
        env.start()
        # Kernel side
        app = compose_standard_application(projects_root=str(tmp_root))
        proj = app.projects_service.create(slug="atomic-proj", name="Atomic")
        assert proj.data is not None, proj.error
        created = app.timelines_service.create(project="atomic-proj", slug="atomic-tl", name="Atomic TL", idempotency_key="atomic-create")
        assert created.data is not None, created.error
        timeline_id = created.data["timeline_id"]
        # Kernel timeline_ulid from created data (may be in timeline_ulid key)
        kernel_ulid = created.data.get("timeline_ulid") or created.data.get("ulid")
        if not kernel_ulid:
            # Fallback: fetch via show
            shown0 = app.timelines_service.show("atomic-proj", "atomic-tl")
            assert shown0.data is not None
            kernel_ulid = shown0.data["timeline_ulid"]
        # Filesystem side: create project dir and timeline dir with SAME ULID (sidecarless backfilled)
        fs_create_project("atomic-proj")
        from pathlib import Path as _Path
        # Ensure timelines/<ulid> exists (with identity for locate, but still backfilled)
        # Kernel ULID is lowercase; filesystem uses uppercase canonical form.
        kernel_ulid_fs = kernel_ulid.upper()
        tdir = _Path(tmp_root) / "atomic-proj" / "timelines" / kernel_ulid_fs
        tdir.mkdir(parents=True, exist_ok=True)
        import json as _json2
        (tdir / "assembly.identity.json").write_text(_json2.dumps({"timeline_id": timeline_id, "timeline_ulid": kernel_ulid_fs, "slug": "atomic-tl", "backend": "sqlite"}), encoding="utf-8")
        (tdir / "display.json").write_text(_json2.dumps({"slug": "atomic-tl", "is_default": False}), encoding="utf-8")
        # Mark backfilled: need backfill-state.json to include timeline_id
        marker_path = tmp_root / ".astrid" / "backfill-state.json"
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(_json2.dumps({timeline_id: {"ulid": kernel_ulid_fs, "slug": "atomic-tl"}}), encoding="utf-8")
        ulid = kernel_ulid_fs

        # Gateway atomic save with new config
        new_config = {"tracks": [{"id": "v1", "kind": "visual", "label": "Video"}], "clips": [{"id": "NEW", "at": 0, "track": "v1", "clipType": "media", "asset": "NEW"}]}
        kernel_events = EventAppendService(app.registry)
        kernel_receipts = ReceiptService()
        kernel_projects = ProjectRepository(events=kernel_events, receipts=kernel_receipts)
        repo = TimelineRepository(events=kernel_events, receipts=kernel_receipts, projects=kernel_projects)

        result = pack_write_gateway(
            project_slug="atomic-proj",
            timeline_slug="atomic-tl",
            timeline_ulid=ulid,
            timeline_event_stream_id="",
            events=[_arrangement_event_with_config(new_config)],
            actor=TimelineActor(type="system", id="test:atomic", display="Atomic Test"),
            root=tmp_root,
            writer=app.writer,
            timeline_repository=repo,
            timeline_stream_type=TIMELINE_STREAM_TYPE,
        )
        # Serve-style read: kernel show returns new bytes and version == head_seq
        shown = app.timelines_service.show("atomic-proj", "atomic-tl")
        assert shown.data is not None, shown.error
        assert shown.data["config_version"] == result.new_version
        assert shown.data["config"]["clips"][0]["id"] == "NEW"
        # Also directly check timelines.document_json matches new config
        import sqlite3
        import json
        from astrid.core.integrations.reigh.bridge_service import derive_database_path


        db_path = derive_database_path(tmp_root)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT document_json, head_seq FROM timelines t JOIN event_streams s ON s.id=t.event_stream_id WHERE t.id=?", (timeline_id,)).fetchone()
            assert row is not None
            doc = json.loads(row["document_json"])
            assert doc["clips"][0]["id"] == "NEW"
            assert int(row["head_seq"]) == shown.data["config_version"]
            # No old-bytes-newer-version window: document reflects head_seq
        finally:
            conn.close()
            env.stop()
            app.close()
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
