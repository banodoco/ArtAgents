"""Revert-sensitive regressions for S2 rework6 H1–H2 — targeted."""

import json
import sqlite3
import tempfile
from pathlib import Path


def _tdir(tmp: Path, project_slug: str, ulid: str) -> Path:
    d = tmp / project_slug / "timelines" / ulid.upper()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _head_seq(db: Path, timeline_id: str) -> int:
    sid = f"{timeline_id}:timeline.timeline"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT head_seq FROM event_streams WHERE id = ?", (sid,)).fetchone()
        return int(row["head_seq"]) if row else 0
    finally:
        conn.close()


def test_h1_sync_with_live_app():
    """H1 (a): sync_asset_registry succeeds while a standard application is live on same root."""
    from astrid.application import compose_standard_application
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
    from astrid.core.timeline.asset_registry_edits import sync_asset_registry

    tmp = Path(tempfile.mkdtemp(prefix="h1-live-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-h1a", name="Proj H1A")
        assert proj.data is not None
        created = app.timelines_service.create(project="proj-h1a", slug="tl-h1a", name="TL H1A", idempotency_key="k1")
        tid = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        _tdir(tmp, "proj-h1a", ulid)
        db = derive_database_path(tmp)
        head_before = _head_seq(db, tid)
        from astrid.packs.timeline.backfill import write_backfill_state

        write_backfill_state(tmp, timeline_id=tid, source="local_fs", source_head_version=1, events_sha256="abc")
        man = tmp / "man.json"
        man.write_text(json.dumps({"assets": {"a": {"file": "a.png"}}}))
        sources_dir = tmp / "proj-h1a" / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        (sources_dir / "a.png").write_text("dummy")
        ev = sync_asset_registry("proj-h1a", "tl-h1a", manifest_path=man, root=str(tmp))
        assert ev is not None
        head_after = _head_seq(db, tid)
        assert head_after == head_before + 1
        man2 = tmp / "man2.json"
        man2.write_text(json.dumps({"assets": {"b": {"file": "a.png"}}}))
        ev2 = sync_asset_registry("proj-h1a", "tl-h1a", manifest_path=man2, root=str(tmp))
        assert ev2 is not None
        assert _head_seq(db, tid) == head_after + 1
        app.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_h1_standalone_sync_recompose():
    """H1 (b): standalone sync closes owned writer so recomposition succeeds."""
    from astrid.application import compose_standard_application
    from astrid.core.timeline.asset_registry_edits import sync_asset_registry

    tmp = Path(tempfile.mkdtemp(prefix="h1-standalone-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-h1b", name="Proj H1B")
        created = app.timelines_service.create(project="proj-h1b", slug="tl-h1b", name="TL H1B", idempotency_key="k1")
        tid = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        _tdir(tmp, "proj-h1b", ulid)
        from astrid.packs.timeline.backfill import write_backfill_state

        write_backfill_state(tmp, timeline_id=tid, source="local_fs", source_head_version=1, events_sha256="abc")
        app.close()
        man = tmp / "man.json"
        man.write_text(json.dumps({"assets": {"a": {"file": "a.png"}}}))
        sources_dir = tmp / "proj-h1b" / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        (sources_dir / "a.png").write_text("dummy")
        ev = sync_asset_registry("proj-h1b", "tl-h1b", manifest_path=man, root=str(tmp))
        assert ev is not None
        app2 = compose_standard_application(projects_root=str(tmp))
        app2.close()
        from astrid.packs import compose_standard_bridge

        bridge = compose_standard_bridge(projects_root=str(tmp))
        bridge.writer.close()
        from astrid.packs import _unregister_active_writer

        _unregister_active_writer(bridge.database_path)
        if bridge.owner_lock:
            bridge.owner_lock.release()
        app3 = compose_standard_application(projects_root=str(tmp))
        app3.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_h2_stale_sidecar_sync_hits_sqlite_zero_jsonl():
    """H2: fake sidecar id on marked timeline -> sync hits SQLite, zero JSONL."""
    from astrid.application import compose_standard_application
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
    from astrid.core.timeline.asset_registry_edits import sync_asset_registry

    tmp = Path(tempfile.mkdtemp(prefix="h2-stale-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-h2", name="Proj H2")
        created = app.timelines_service.create(project="proj-h2", slug="tl-h2", name="TL H2", idempotency_key="k1")
        tid_real = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        _tdir(tmp, "proj-h2", ulid)
        from astrid.packs.timeline.backfill import write_backfill_state

        write_backfill_state(tmp, timeline_id=tid_real, source="local_fs", source_head_version=1, events_sha256="abc")
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("proj-h2", "tl-h2", root=str(tmp))
        assert found is not None
        tdir_real = found[1]
        db = derive_database_path(tmp)
        head_before = _head_seq(db, tid_real)
        id_path = tdir_real / "assembly.identity.json"
        fake_id = "00000000-0000-4000-a000-000000000000"
        if id_path.is_file():
            raw = json.loads(id_path.read_text())
            raw["timeline_id"] = fake_id
            id_path.write_text(json.dumps(raw))
        else:
            id_path.write_text(json.dumps({"timeline_id": fake_id, "timeline_ulid": ulid, "backend": "local_fs"}))
        jsonl = tdir_real / "assembly.jsonl"
        lines_before = len(jsonl.read_text().splitlines()) if jsonl.is_file() else 0
        man = tmp / "man.json"
        man.write_text(json.dumps({"assets": {"a": {"file": "a.png"}}}))
        sources_dir = tmp / "proj-h2" / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        (sources_dir / "a.png").write_text("dummy")
        ev = sync_asset_registry("proj-h2", "tl-h2", manifest_path=man, root=str(tmp))
        assert ev is not None
        assert ev.timeline_id == tid_real
        head_after = _head_seq(db, tid_real)
        assert head_after == head_before + 1
        lines_after = len(jsonl.read_text().splitlines()) if jsonl.is_file() else 0
        assert lines_after == lines_before
        from astrid.core.timeline.crud import show_timeline

        rec = show_timeline("proj-h2", "tl-h2", root=str(tmp), verify=False)
        assert rec is not None
        assert rec["assembly"] is not None
        app.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_h2_stale_sidecar_edit_helper_hits_sqlite():
    """H2: fake sidecar id -> edit-helper write hits SQLite, zero JSONL."""
    from astrid.application import compose_standard_application
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
    from astrid.core.timeline.track_edits import track_add

    tmp = Path(tempfile.mkdtemp(prefix="h2-edit-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-h2e", name="Proj H2E")
        created = app.timelines_service.create(project="proj-h2e", slug="tl-h2e", name="TL H2E", idempotency_key="k1")
        tid_real = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        _tdir(tmp, "proj-h2e", ulid)
        from astrid.packs.timeline.backfill import write_backfill_state

        write_backfill_state(tmp, timeline_id=tid_real, source="local_fs", source_head_version=1, events_sha256="abc")
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("proj-h2e", "tl-h2e", root=str(tmp))
        assert found is not None
        tdir_real = found[1]
        db = derive_database_path(tmp)
        head_before = _head_seq(db, tid_real)
        fake_id = "11111111-1111-4111-a111-111111111111"
        id_path = tdir_real / "assembly.identity.json"
        raw = json.loads(id_path.read_text()) if id_path.is_file() else {}
        raw["timeline_id"] = fake_id
        raw["timeline_ulid"] = ulid
        id_path.write_text(json.dumps(raw))
        jsonl = tdir_real / "assembly.jsonl"
        lines_before = len(jsonl.read_text().splitlines()) if jsonl.is_file() else 0
        ev = track_add(project_slug="proj-h2e", slug="tl-h2e", track_id="track-1", kind="visual", label="TestTrack", root=str(tmp))
        assert ev.timeline_id == tid_real
        head_after = _head_seq(db, tid_real)
        assert head_after == head_before + 1
        lines_after = len(jsonl.read_text().splitlines()) if jsonl.is_file() else 0
        assert lines_after == lines_before
        app.close()
        from astrid.core.timeline.crud import show_timeline

        rec = show_timeline("proj-h2e", "tl-h2e", root=str(tmp), verify=False)
        assert rec is not None
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
