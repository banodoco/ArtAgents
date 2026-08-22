"""Revert-sensitive regressions for S2 rework5 G1–G6 — targeted."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest


def _tdir(tmp: Path, project_slug: str, ulid: str) -> Path:
    d = tmp / project_slug / "timelines" / ulid.upper()
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_g1_lazy_owned_close_reacquirable():
    from astrid.application import compose_standard_application
    from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
    from astrid.core.timeline.events.schema import TimelineActor, AssetRegistryReplacedPayload

    tmp = Path(tempfile.mkdtemp(prefix="g1-lazy-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-g1a", name="Proj G1A")
        assert proj.data is not None
        created = app.timelines_service.create(project="proj-g1a", slug="tl-g1a", name="TL G1A", idempotency_key="k1")
        tid = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        tdir = _tdir(tmp, "proj-g1a", ulid)
        actor = TimelineActor(type="system", id="test:g1", display="test")
        # Close app first so lazy-owned backend can acquire lock (no contention). Then verify reacquirable.
        app.close()
        backend = SqliteEventLogBackend(timeline_id=tid, timeline_home=tdir)
        ev = backend.append_event(tid, "timeline.asset_registry_replaced", AssetRegistryReplacedPayload(registry={"assets": {"x": {"file": "x.png"}}}, source="other"), actor=actor)
        assert ev is not None
        backend.close()
        backend2 = SqliteEventLogBackend(timeline_id=tid, timeline_home=tdir)
        ev2 = backend2.append_event(tid, "timeline.asset_registry_replaced", AssetRegistryReplacedPayload(registry={"assets": {"y": {"file": "y.png"}}}, source="other"), actor=actor)
        assert ev2 is not None
        backend2.close()
        backend3 = SqliteEventLogBackend(timeline_id=tid, timeline_home=tdir, projects_root=tmp)
        ev3 = backend3.append_event(tid, "timeline.asset_registry_replaced", AssetRegistryReplacedPayload(registry={"assets": {"z": {"file": "z.png"}}}, source="other"), actor=actor)
        assert ev3 is not None
        backend3.close()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_g1_timeline_home_only_construction():
    from astrid.application import compose_standard_application
    from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend

    tmp = Path(tempfile.mkdtemp(prefix="g1-home-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-g1b", name="Proj G1B")
        assert proj.data is not None
        created = app.timelines_service.create(project="proj-g1b", slug="tl-g1b", name="TL G1B", idempotency_key="k1")
        tid = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        tdir = _tdir(tmp, "proj-g1b", ulid)
        # Construction with ONLY timeline_home (projects_root auto-derived via _projects_root_from_timeline_home)
        backend = SqliteEventLogBackend(timeline_id=tid, timeline_home=str(tdir))
        evs = backend.read_events()
        assert len(evs) >= 1
        backend.close()
        app.close()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_g2_sync_asset_registry_marked_bridge_visible():
    from astrid.application import compose_standard_application
    from astrid.core.timeline.asset_registry_edits import sync_asset_registry

    tmp = Path(tempfile.mkdtemp(prefix="g2-sync-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-g2", name="Proj G2")
        assert proj.data is not None
        created = app.timelines_service.create(project="proj-g2", slug="tl-g2", name="TL G2", idempotency_key="k1")
        tid = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        tdir = _tdir(tmp, "proj-g2", ulid)
        from astrid.packs.timeline.backfill import write_backfill_state
        write_backfill_state(tmp, timeline_id=tid, source="local_fs", source_head_version=1, events_sha256="abc")
        (tmp / "proj-g2" / "sources").mkdir(parents=True, exist_ok=True)
        (tmp / "proj-g2" / "sources" / "clip.mp4").write_text("fake")
        manifest = tmp / "manifest.json"
        manifest.write_text(json.dumps({"assets": {"asset-a": {"file": "clip.mp4"}}}))
        # Need to close app before sync if sync uses Sqlite backend with lazy ownership while app holds lock.
        # sync will reuse app writer if we pass writer via injected path? But our sync uses lazy SqliteBackend which checks shared writer.
        # Since app holds lock, lazy would contend. So close and reopen after sync with app closed to avoid contention.
        app.close()
        ev = sync_asset_registry("proj-g2", "tl-g2", manifest_path=str(manifest), root=str(tmp))
        assert ev is not None
        assert ev.kind == "timeline.asset_registry_replaced"
        from astrid.core.integrations.reigh.bridge_service import derive_database_path
        db = derive_database_path(tmp)
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT asset_registry_json FROM timelines WHERE id = ?", (tid,)).fetchone()
            assert row is not None
            reg = json.loads(row["asset_registry_json"])
            assert "asset-a" in reg
        assert (tdir / "registry.json").is_file()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_g4_sidecarless_show_verify_marked():
    from astrid.application import compose_standard_application
    from astrid.core.timeline.crud import show_timeline
    from astrid.core.timeline.paths import find_timeline_by_slug

    tmp = Path(tempfile.mkdtemp(prefix="g4-side-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-g4", name="Proj G4")
        assert proj.data is not None
        created = app.timelines_service.create(project="proj-g4", slug="tl-g4", name="TL G4", idempotency_key="k1")
        tid = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        tdir = _tdir(tmp, "proj-g4", ulid)
        from astrid.packs.timeline.backfill import write_backfill_state
        write_backfill_state(tmp, timeline_id=tid, source="local_fs", source_head_version=1, events_sha256="abc")
        for p in [tdir / "manifest.json", tdir / "display.json", tdir / "assembly.json", tdir / "assembly.jsonl"]:
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        # Close app so show reads without contention (show uses read-only, not writer)
        app.close()
        found = find_timeline_by_slug("proj-g4", "tl-g4", root=tmp)
        assert found is not None
        rec = show_timeline("proj-g4", "tl-g4", root=tmp, verify=False)
        assert rec is not None
        assert rec["assembly"] is not None
        assert rec["display"] is not None
        rec_v = show_timeline("proj-g4", "tl-g4", root=tmp, verify=True)
        assert rec_v is not None
        assert "verification" in rec_v
        assert rec_v["verification"]["event_log"] == "present"
        assert rec_v["verification"]["ok"] is True
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_g4_corrupt_marker_fail_closed():
    from astrid.application import compose_standard_application
    from astrid.core.timeline.paths import find_timeline_by_slug

    tmp = Path(tempfile.mkdtemp(prefix="g4-corrupt-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-g4c", name="Proj G4C")
        assert proj.data is not None
        created = app.timelines_service.create(project="proj-g4c", slug="tl-g4c", name="TL G4C", idempotency_key="k1")
        tid = created.data["timeline_id"]
        from astrid.packs.timeline.backfill import write_backfill_state
        write_backfill_state(tmp, timeline_id=tid, source="local_fs", source_head_version=1, events_sha256="abc")
        (tmp / ".astrid" / "backfill-state.json").write_text("not json")
        with pytest.raises(Exception):
            find_timeline_by_slug("proj-g4c", "tl-g4c", root=tmp)
        app.close()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_g5_atomic_registry_bridge_visible():
    from astrid.application import compose_standard_application
    from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
    from astrid.core.timeline.events.schema import TimelineActor, AssetRegistryReplacedPayload

    tmp = Path(tempfile.mkdtemp(prefix="g5-atomic-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-g5a", name="Proj G5A")
        assert proj.data is not None
        created = app.timelines_service.create(project="proj-g5a", slug="tl-g5a", name="TL G5A", idempotency_key="k1")
        tid = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        tdir = _tdir(tmp, "proj-g5a", ulid)
        backend = SqliteEventLogBackend(timeline_id=tid, timeline_home=tdir, projects_root=tmp, writer=app.writer)
        actor = TimelineActor(type="system", id="test:g5", display="test")
        payload = AssetRegistryReplacedPayload(registry={"assets": {"direct-a": {"file": "a.png"}}}, source="other")
        ev = backend.append_event(tid, "timeline.asset_registry_replaced", payload, actor=actor)
        assert ev is not None
        head = backend.head()
        assert head.version >= 2
        from astrid.core.integrations.reigh.bridge_service import derive_database_path
        db = derive_database_path(tmp)
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT asset_registry_json FROM timelines WHERE id = ?", (tid,)).fetchone()
            assert row is not None
            reg = json.loads(row["asset_registry_json"])
            assert "direct-a" in reg, f"asset_registry_json not updated atomically: {reg}"
        backend.close()
        app.close()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_g6_file_scan_exclusion_stale_alias_and_display_fastpath():
    from astrid.application import compose_standard_application
    from astrid.core.timeline.paths import find_timeline_by_slug, load_display_json_with_repair

    tmp = Path(tempfile.mkdtemp(prefix="g6-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-g6", name="Proj G6")
        assert proj.data is not None
        created = app.timelines_service.create(project="proj-g6", slug="real-slug", name="Real", idempotency_key="k1")
        tid = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        tdir = _tdir(tmp, "proj-g6", ulid)
        from astrid.packs.timeline.backfill import write_backfill_state
        write_backfill_state(tmp, timeline_id=tid, source="local_fs", source_head_version=1, events_sha256="abc")
        # Write stale alias display sidecar — kernel resolution must ignore it for marked timeline
        (tdir / "display.json").write_text(json.dumps({"slug": "stale-alias", "name": "Stale", "schema_version": 1, "is_default": False}))
        app.close()
        found_stale = find_timeline_by_slug("proj-g6", "stale-alias", root=tmp)
        assert found_stale is None, f"stale alias incorrectly returned {found_stale}"
        found_real = find_timeline_by_slug("proj-g6", "real-slug", root=tmp)
        assert found_real is not None
        disp = load_display_json_with_repair(tdir)
        assert disp is not None
        assert disp.get("slug") == "real-slug"
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_repeated_appends_one_writer():
    from astrid.application import compose_standard_application
    from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
    from astrid.core.timeline.events.schema import TimelineActor, AssetRegistryReplacedPayload

    tmp = Path(tempfile.mkdtemp(prefix="onewriter-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-ow", name="Proj OW")
        assert proj.data is not None
        created = app.timelines_service.create(project="proj-ow", slug="tl-ow", name="TL OW", idempotency_key="k1")
        tid = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        tdir = _tdir(tmp, "proj-ow", ulid)
        b1 = SqliteEventLogBackend(timeline_id=tid, timeline_home=tdir, projects_root=tmp, writer=app.writer)
        b2 = SqliteEventLogBackend(timeline_id=tid, timeline_home=tdir, projects_root=tmp, writer=app.writer)
        actor = TimelineActor(type="system", id="test:ow", display="test")
        for i in range(3):
            p = AssetRegistryReplacedPayload(registry={"assets": {f"k{i}": {"file": f"{i}.png"}}}, source="other")
            ev = b1.append_event(tid, "timeline.asset_registry_replaced", p, actor=actor)
            assert ev is not None
            ev2 = b2.append_event(tid, "timeline.asset_registry_replaced", p, actor=actor)
            assert ev2 is not None
        b1.close()
        b2.close()
        app.close()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
