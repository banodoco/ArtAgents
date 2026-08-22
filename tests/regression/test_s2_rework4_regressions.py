"""Revert-sensitive regressions for S2 rework4 F1-F5 — minimal."""

import json
import tempfile
from pathlib import Path

import pytest


def test_f1_compose_lifecycle():
    from astrid.packs import _unregister_active_writer, compose_standard_bridge
    tmp = Path(tempfile.mkdtemp(prefix="f1-"))
    try:
        comp1 = compose_standard_bridge(tmp)
        assert comp1.writer is not None
        comp1.writer.close()
        _unregister_active_writer(comp1.database_path)
        try:
            comp1.owner_lock.release()
        except Exception:
            pass
        comp2 = compose_standard_bridge(tmp)
        assert comp2.writer is not None
        comp2.writer.close()
        _unregister_active_writer(comp2.database_path)
        try:
            comp2.owner_lock.release()
        except Exception:
            pass
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_f2_lock_release_and_reuse():
    from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
    from astrid.packs import _unregister_active_writer, compose_standard_bridge
    tmp = Path(tempfile.mkdtemp(prefix="f2-"))
    try:
        comp = compose_standard_bridge(tmp)
        b1 = SqliteEventLogBackend(timeline_id="tid1", projects_root=tmp)
        b2 = SqliteEventLogBackend(timeline_id="tid2", projects_root=tmp)
        w1 = b1._ensure_writer()
        w2 = b2._ensure_writer()
        assert w1 is w2
        b1.close()
        b2.close()
        comp.writer.close()
        _unregister_active_writer(comp.database_path)
        try:
            comp.owner_lock.release()
        except Exception:
            pass
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_f3_stale_alias_corrupt_marker():
    from astrid.application import compose_standard_application
    from astrid.core.timeline.paths import find_timeline_by_slug
    tmp = Path(tempfile.mkdtemp(prefix="f3-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-f3", name="Proj F3")
        assert proj.data is not None
        created = app.timelines_service.create(project="proj-f3", slug="real-slug", name="Real", idempotency_key="k1")
        assert created.data is not None
        tid = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        from astrid.packs.timeline.backfill import write_backfill_state
        write_backfill_state(tmp, timeline_id=tid, source="local_fs", source_head_version=1, events_sha256="abc")
        tdir = tmp / "proj-f3" / "timelines" / ulid.upper()
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "assembly.identity.json").write_text(json.dumps({"timeline_id": tid, "timeline_ulid": ulid.upper(), "slug": "real-slug"}))
        (tdir / "display.json").write_text(json.dumps({"slug": "stale-alias", "name": "Stale"}))
        found = find_timeline_by_slug("proj-f3", "stale-alias", root=tmp)
        assert found is None
        (tmp / ".astrid" / "backfill-state.json").write_text("not json")
        with pytest.raises(Exception):
            find_timeline_by_slug("proj-f3", "real-slug", root=tmp)
        app.close()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_f4_typed_payload():
    from astrid.application import compose_standard_application
    from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
    from astrid.core.timeline.events.schema import AssetRegistryReplacedPayload, TimelineActor
    tmp = Path(tempfile.mkdtemp(prefix="f4-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-f4", name="Proj F4")
        assert proj.data is not None
        created = app.timelines_service.create(project="proj-f4", slug="tl-f4", name="TL F4", idempotency_key="k1")
        assert created.data is not None
        tid = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        tdir = tmp / "proj-f4" / "timelines" / ulid.upper()
        backend = SqliteEventLogBackend(timeline_id=tid, timeline_home=tdir, projects_root=tmp, writer=app.writer)
        payload = AssetRegistryReplacedPayload(registry={"assets": {"a": {"file": "a.png"}}}, source="other")
        actor = TimelineActor(type="system", id="test:f4", display="test")
        ev = backend.append_event(tid, "timeline.asset_registry_replaced", payload, actor=actor)
        assert ev is not None
        assert backend.verify_chain().ok
        backend.close()
        app.close()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_f5_reject_saved():
    from astrid.application import compose_standard_application
    from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
    from astrid.core.timeline.eventlog.types import EventLogError
    from astrid.core.timeline.events.schema import TimelineActor, TimelineConfigReplacedPayload
    tmp = Path(tempfile.mkdtemp(prefix="f5-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        proj = app.projects_service.create(slug="proj-f5", name="Proj F5")
        assert proj.data is not None
        created = app.timelines_service.create(project="proj-f5", slug="tl-f5", name="TL F5", idempotency_key="k1")
        assert created.data is not None
        tid = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        tdir = tmp / "proj-f5" / "timelines" / ulid.upper()
        backend = SqliteEventLogBackend(timeline_id=tid, timeline_home=tdir, projects_root=tmp, writer=app.writer)
        actor = TimelineActor(type="system", id="test:f5", display="test")
        # Schema-valid config-bearing payload that must be rejected by the guard
        # (not by schema validation). Reverting the guard should let this commit.
        valid_payload = TimelineConfigReplacedPayload(
            config={"tracks": [], "clips": []},
            registry={"assets": {}},
            source="other",
        )
        # Capture head + documents row before
        head_before = backend.head()
        import sqlite3

        from astrid.core.integrations.reigh.bridge_service import derive_database_path
        db_path = derive_database_path(tmp)
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT document_json, asset_registry_json FROM timelines WHERE id = ?", (tid,)).fetchone()
            doc_before = row["document_json"] if row else None
            reg_before = row["asset_registry_json"] if row else None
        with pytest.raises(EventLogError, match="must not be appended via generic append_event"):
            backend.append_event(tid, "timeline.saved", valid_payload, actor=actor)
        with pytest.raises(EventLogError, match="must not be appended via generic append_event"):
            backend.append_event(tid, "timeline.config_replaced", valid_payload, actor=actor)
        # Typed rejection must keep head and documents row intact
        head_after = backend.head()
        assert head_after.version == head_before.version, f"head changed {head_before.version} -> {head_after.version}"
        assert head_after.last_event_id == head_before.last_event_id
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            row2 = conn.execute("SELECT document_json, asset_registry_json FROM timelines WHERE id = ?", (tid,)).fetchone()
            assert row2["document_json"] == doc_before
            assert row2["asset_registry_json"] == reg_before
        backend.close()
        app.close()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
