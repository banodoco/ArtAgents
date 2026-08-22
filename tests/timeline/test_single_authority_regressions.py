"""Revert-sensitive regression tests for exec-s2-rework3 (E1-E7).

Each test MUST FAIL if the corresponding runtime fix is reverted.
See task description for revert hunks.
"""
from __future__ import annotations

import uuid
import json
import sqlite3
from pathlib import Path

import pytest

from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent, generate_event_ulid
from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _projects_root(tmp_path: Path) -> Path:
    # tmp_path itself acts as projects_root (contains .astrid folder and project dirs)
    return tmp_path

def _seed_kernel_with_backfill(tmp_path: Path, project_slug: str = "proj", timeline_slug: str = "t1", assets: dict | None = None):
    """Seed DB with one project+timeline, backfill marker, and empty timeline dir.

    Returns (project_id, timeline_id, ulid, stream_id, db_path, timeline_home)
    """
    from astrid.core.events.service import EventAppendService
    from astrid.core.store.uow import UnitOfWork
    from astrid.packs import build_standard_registry, open_standard_writer
    from astrid.packs.timeline.backfill import write_backfill_state

    registry = build_standard_registry()
    db_path = derive_database_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer = open_standard_writer(db_path, registry=registry)
    proj_id = uuid.uuid4().hex
    tl_id = uuid.uuid4().hex
    ulid = "01J0000000000000000000000A"
    stream_id = f"{tl_id}:timeline.timeline"

    def _setup(uow: UnitOfWork):
        uow.execute(
            "INSERT INTO projects (id, slug, name, settings_json, event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (proj_id, project_slug, "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO event_streams (id, project_id, stream_type, aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)",
            (stream_id, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"),
        )

    UnitOfWork(writer).run(_setup)
    svc = EventAppendService(registry)

    def _append(uow: UnitOfWork):
        svc.append(
            uow,
            stream_id=stream_id,
            project_id=proj_id,
            event_kind="timeline.created",
            data={"timeline_id": tl_id, "timeline_ulid": ulid, "slug": timeline_slug, "name": "T1"},
            changes=["timeline_id", "slug", "name"],
            idempotency_key=f"create:{tl_id}",
            txn_id=generate_event_ulid(),
            actor_kind="system",
            event_id=generate_event_ulid(),
        )

    UnitOfWork(writer).run(_append)

    # Ensure timelines projection row exists (EventAppendService alone does not create it)
    from astrid.core.receipts.canonical import canonical_json as _cj
    def _ensure_timeline_row(uow: UnitOfWork):
        row = uow.query_one("SELECT id FROM timelines WHERE id = ?", (tl_id,))
        if row is None:
            if assets is not None:
                assets_json = _cj(dict(assets))
            else:
                assets_json = _cj({})
            uow.execute(
                "INSERT INTO timelines (id, project_id, event_stream_id, name, document_json, asset_registry_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (tl_id, proj_id, stream_id, "T1", _cj({"tracks": [], "clips": []}), assets_json, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            )
        else:
            if assets is not None:
                assets_json = _cj(dict(assets))
                uow.execute("UPDATE timelines SET asset_registry_json = ? WHERE id = ?", (assets_json, tl_id))
    UnitOfWork(writer).run(_ensure_timeline_row)

    # write backfill marker
    write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=1, events_sha256="abc")

    # ensure filesystem project dir and empty timeline dir (for find_timeline_by_slug kernel fallback)
    proj_dir = tmp_path / project_slug
    proj_dir.mkdir(parents=True, exist_ok=True)
    # project.json required for some paths? create minimal
    if not (proj_dir / "project.json").exists():
        (proj_dir / "project.json").write_text(json.dumps({"slug": project_slug, "created_at": "2026-01-01T00:00:00Z", "name": project_slug, "schema_version": 1, "updated_at": "2026-01-01T00:00:00Z", "default_timeline_id": None}), encoding="utf-8")
    tdir = proj_dir / "timelines" / ulid
    tdir.mkdir(parents=True, exist_ok=True)

    return proj_id, tl_id, ulid, stream_id, db_path, tdir

def _kernel_head_seq(db_path: Path, stream_id: str) -> int:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT head_seq FROM event_streams WHERE id = ?", (stream_id,)).fetchone()
        return int(row["head_seq"]) if row else 0
    finally:
        conn.close()

def _kernel_document_json(db_path: Path, tl_id: str) -> str | None:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT document_json FROM timelines WHERE id = ?", (tl_id,)).fetchone()
        return row["document_json"] if row and row["document_json"] else None
    finally:
        conn.close()

def _kernel_asset_json(db_path: Path, tl_id: str) -> dict | None:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT asset_registry_json FROM timelines WHERE id = ?", (tl_id,)).fetchone()
        if row is None or not row["asset_registry_json"]:
            return None
        return json.loads(row["asset_registry_json"])
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# T-CAS (E4)
# ---------------------------------------------------------------------------

class TestTCasStaleVersion:
    def test_stale_expected_version_raises_and_head_unchanged(self, tmp_path: Path):
        from astrid.core.timeline._edit_helpers import pack_write_gateway
        from astrid.core.timeline.eventlog.types import EventLogStaleVersionError, TimelineVersionConflict
        from astrid.core.timeline._edit_helpers import TimelineEditError

        proj_slug = "proj"
        tl_slug = "t1"
        proj_id, tl_id, ulid, stream_id, db_path, tdir = _seed_kernel_with_backfill(tmp_path, project_slug=proj_slug, timeline_slug=tl_slug)

        head_before = _kernel_head_seq(db_path, stream_id)
        doc_before = _kernel_document_json(db_path, tl_id)
        assert head_before == 1, f"seed head should be 1, got {head_before}"

        stale_version = head_before - 1  # 0
        payload = {"config": {"tracks": [{"id": "v1", "kind": "visual", "label": "V"}], "clips": [{"id": "CLIP-A", "track": "v1", "at": 0, "clipType": "media", "asset": "a"}]}, "expected_version": stale_version}

        with pytest.raises((EventLogStaleVersionError, TimelineEditError)) as excinfo:
            pack_write_gateway(
                project_slug=proj_slug,
                timeline_slug=tl_slug,
                timeline_ulid="",
                timeline_event_stream_id="",
                events=[{"kind": "timeline.config_replaced", "payload": payload}],
                actor=TimelineActor(type="system", id="test:cas", display="CAS Test"),
                root=tmp_path,
            )
        # typed stale error carries conflict details
        exc = excinfo.value
        if isinstance(exc, EventLogStaleVersionError):
            assert exc.conflict.expected_version == stale_version
            assert exc.conflict.current_version == head_before
        # head unchanged
        head_after = _kernel_head_seq(db_path, stream_id)
        assert head_after == head_before, f"head changed on stale save: {head_before} -> {head_after}"
        doc_after = _kernel_document_json(db_path, tl_id)
        assert doc_after == doc_before, "document_json changed on stale save"

# ---------------------------------------------------------------------------
# T-REG (E5)
# ---------------------------------------------------------------------------

class TestTRegPreservesRegistry:
    def test_config_only_preserves_original_registry(self, tmp_path: Path):
        from astrid.core.timeline._edit_helpers import pack_write_gateway

        proj_slug = "proj"
        tl_slug = "t1"
        orig_assets = {"orig-asset": {"id": "orig-asset", "kind": "media", "path": "/tmp/x.mp4"}}
        proj_id, tl_id, ulid, stream_id, db_path, tdir = _seed_kernel_with_backfill(tmp_path, project_slug=proj_slug, timeline_slug=tl_slug, assets=orig_assets)

        # verify seeded registry
        seeded = _kernel_asset_json(db_path, tl_id)
        assert seeded is not None and "orig-asset" in seeded, f"seeded registry missing: {seeded}"

        head_before = _kernel_head_seq(db_path, stream_id)
        payload = {"config": {"tracks": [{"id": "v1", "kind": "visual", "label": "V"}], "clips": []}}
        # no registry key at all
        assert "registry" not in payload and "asset_registry" not in payload

        result = pack_write_gateway(
            project_slug=proj_slug,
            timeline_slug=tl_slug,
            timeline_ulid="",
            timeline_event_stream_id="",
            events=[{"kind": "timeline.config_replaced", "payload": payload}],
            actor=TimelineActor(type="system", id="test:reg", display="Reg Test"),
            root=tmp_path,
        )
        assert result.new_version == head_before + 1
        after = _kernel_asset_json(db_path, tl_id)
        assert after is not None, "asset_registry_json missing after save"
        assert "orig-asset" in after, f"registry was emptied on config-only save: {after}"
        assert after == seeded, f"registry changed: {seeded} -> {after}"

# ---------------------------------------------------------------------------
# T-SAVED (E1)
# ---------------------------------------------------------------------------

class TestTSavedClassification:
    def test_saved_event_projects_clip(self, tmp_path: Path):
        from astrid.core.timeline.projection import project_to_assembly, PROJECTOR_EVENT_CLASSIFICATION
        from astrid.core.timeline.events.schema import TimelineEvent
        import uuid

        # classification must be validated_full_config_replacement
        assert PROJECTOR_EVENT_CLASSIFICATION.get("timeline.saved") == "validated_full_config_replacement", "timeline.saved classification missing"

        tid = uuid.uuid4().hex
        saved_payload = {"config": {"tracks": [{"id": "v1", "kind": "visual", "label": "V"}], "clips": [{"id": "SAVED-CLIP", "track": "v1", "at": 0, "clipType": "media", "asset": "a"}]}}
        saved = TimelineEvent(
            event_id=generate_event_ulid(),
            timeline_id=tid,
            kind="timeline.saved",
            payload=saved_payload,
            actor=TimelineActor(type="system", id="sys:test", display="Test"),
            ts="2026-01-02T00:00:00Z",
            txn_id=generate_event_ulid(),
            prev_hash=None,
            hash=None,
        )
        assembly = project_to_assembly([saved])
        assert any(c.get("id") == "SAVED-CLIP" for c in assembly.get("clips", [])), f"saved clip missing in projection: {assembly}"

        from astrid.core.timeline.projection import apply_event_to_assembly, canonical_empty_timeline
        state = canonical_empty_timeline()
        state2 = apply_event_to_assembly(state, saved)
        assert any(c.get("id") == "SAVED-CLIP" for c in state2.get("clips", [])), f"snapshot path clip missing: {state2}"
# ---------------------------------------------------------------------------
# T-SIDECARLESS (E2)
# ---------------------------------------------------------------------------

class TestTSidecarless:
    def test_sidecarless_backfilled_write_and_discover(self, tmp_path: Path):
        from astrid.core.timeline._edit_helpers import pack_write_gateway
        from astrid.packs.rendering.executors.timeline_visualize.select import _discover, discover_timelines

        proj_slug = "proj"
        tl_slug = "t1"
        proj_id, tl_id, ulid, stream_id, db_path, tdir = _seed_kernel_with_backfill(tmp_path, project_slug=proj_slug, timeline_slug=tl_slug)

        # Create sidecars initially via crud to have 5 files, then delete all
        # For this test we just ensure tdir exists; create dummy sidecars then delete
        for name in ["assembly.identity.json", "display.json", "assembly.json", "manifest.json", "registry.json"]:
            (tdir / name).write_text(json.dumps({"dummy": True}), encoding="utf-8")
        # Ensure all five exist
        assert all((tdir / n).exists() for n in ["assembly.identity.json", "display.json", "assembly.json", "manifest.json", "registry.json"])
        # Delete ALL five sidecars
        for name in ["assembly.identity.json", "display.json", "assembly.json", "manifest.json", "registry.json"]:
            (tdir / name).unlink()
        # Also delete assembly.jsonl if present
        if (tdir / "assembly.jsonl").exists():
            (tdir / "assembly.jsonl").unlink()
        assert not (tdir / "assembly.identity.json").exists()

        proj_dir = tmp_path / proj_slug
        # 1) gateway write must succeed via kernel fallback
        head_before = _kernel_head_seq(db_path, stream_id)
        payload = {"config": {"tracks": [], "clips": []}}
        result = pack_write_gateway(
            project_slug=proj_slug,
            timeline_slug=tl_slug,
            timeline_ulid="",
            timeline_event_stream_id="",
            events=[{"kind": "timeline.config_replaced", "payload": payload}],
            actor=TimelineActor(type="system", id="test:sidecarless", display="Sidecar Test"),
            root=tmp_path,
        )
        assert result.new_version == head_before + 1, "gateway write failed for sidecarless backfilled timeline"

        # 2) _discover must include it despite missing sidecars
        discovered, diagnostics = _discover(proj_dir)
        ulids = [t.timeline_ulid for t in discovered]
        assert ulid in ulids or ulid.upper() in ulids or any(t.timeline_id == tl_id for t in discovered), f"sidecarless timeline not discovered: ulids={ulids} diagnostics={diagnostics}"
        # also via discover_timelines
        discovered2 = discover_timelines(proj_dir)
        assert any(t.timeline_id == tl_id for t in discovered2), f"discover_timelines missed sidecarless: {[t.timeline_id for t in discovered2]}"

# ---------------------------------------------------------------------------
# T-ONEWRITER (E7)
# ---------------------------------------------------------------------------

class TestTOneWriter:
    def test_compose_standard_bridge_fails_when_locked(self, tmp_path: Path):
        from astrid.core.store.ownership import DatabaseOwnerLock
        from astrid.packs import compose_standard_bridge
        from astrid.sdk.exceptions import ServiceUnavailableError
        from astrid.core.store.ownership import OwnerLockError

        proj_root = tmp_path
        db_path = derive_database_path(proj_root)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # seed minimal DB so compose doesn't fail on missing schema
        from astrid.packs import build_standard_registry
        from astrid.core.store.writer import DatabaseWriter
        registry = build_standard_registry()
        w = DatabaseWriter(db_path, registry)
        w.close()

        lock = DatabaseOwnerLock(db_path)
        try:
            with pytest.raises((ServiceUnavailableError, OwnerLockError, Exception)) as excinfo:
                compose_standard_bridge(projects_root=proj_root)
            # must be typed unavailable
            exc = excinfo.value
            # ServiceUnavailableError is the SDK contract; OwnerLockError also typed
            assert isinstance(exc, (ServiceUnavailableError, OwnerLockError)), f"wrong error type: {type(exc)} {exc}"
            msg = str(exc).lower()
            assert "owned" in msg or "unavailable" in msg or "already" in msg, f"unexpected message: {exc}"
        finally:
            lock.release()

# ---------------------------------------------------------------------------
# T-RECOVERY (E6)
# ---------------------------------------------------------------------------

class TestTRecovery:
    def test_inner_map_registry_recovered(self, tmp_path: Path):
        from astrid.core.integrations.reigh.local_bridge import _registry_from_sqlite, _ensure_bridge_registry, BridgeTimelineRecord
        from astrid.core.receipts.canonical import canonical_json

        proj_slug = "proj"
        tl_slug = "t1"
        inner_assets = {"inner-a": {"id": "inner-a", "kind": "media", "path": "/src/a.mp4"}, "inner-b": {"id": "inner-b", "kind": "media"}}
        proj_id, tl_id, ulid, stream_id, db_path, tdir = _seed_kernel_with_backfill(tmp_path, project_slug=proj_slug, timeline_slug=tl_slug, assets=inner_assets)

        # Overwrite asset_registry_json as INNER map (no outer {"assets": ...})
        inner_json = canonical_json(dict(inner_assets))
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("UPDATE timelines SET asset_registry_json = ? WHERE id = ?", (inner_json, tl_id))
            conn.commit()
        finally:
            conn.close()

        # Ensure registry.json missing
        reg_path = tdir / "registry.json"
        if reg_path.exists():
            reg_path.unlink()
        assert not reg_path.exists()

        record = BridgeTimelineRecord(project_slug=proj_slug, timeline_ulid=ulid, timeline_id=tl_id, slug=tl_slug, name="T1", is_default=False, timeline_home=tdir)

        # _registry_from_sqlite must return outer wrapper with inner assets
        recovered = _registry_from_sqlite(record, root=tmp_path)
        assert recovered is not None, "_registry_from_sqlite returned None for inner-map"
        assert "assets" in recovered, f"missing assets key: {recovered}"
        assert recovered["assets"] == inner_assets, f"inner-map recovery failed: {recovered['assets']} != {inner_assets}"

        # _ensure_bridge_registry also must recover (and write registry.json)
        ensured = _ensure_bridge_registry(record, root=tmp_path)
        assert ensured["assets"] == inner_assets, f"_ensure_bridge_registry failed: {ensured}"
        assert not (ensured["assets"] == {}), "bridge recovery returned empty assets"

# ---------------------------------------------------------------------------
# T-PAGING (E3)
# ---------------------------------------------------------------------------

class TestTPaging:
    def test_read_events_paging_after_limit(self, tmp_path: Path):
        from astrid.core.events.service import EventAppendService
        from astrid.core.store.uow import UnitOfWork
        from astrid.packs import build_standard_registry, open_standard_writer
        from astrid.packs.timeline.backfill import write_backfill_state

        proj_slug = "proj"
        tl_slug = "t1"
        # Seed base
        registry = build_standard_registry()
        db_path = derive_database_path(tmp_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        writer = open_standard_writer(db_path, registry=registry)
        proj_id = uuid.uuid4().hex
        tl_id = uuid.uuid4().hex
        ulid = "01J0000000000000000000000A"
        stream_id = f"{tl_id}:timeline.timeline"
        home = tmp_path / proj_slug / "timelines" / ulid
        home.mkdir(parents=True, exist_ok=True)

        def _setup(uow: UnitOfWork):
            uow.execute(
                "INSERT INTO projects (id, slug, name, settings_json, event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
                (proj_id, proj_slug, "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            )
            uow.execute(
                "INSERT INTO event_streams (id, project_id, stream_type, aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)",
                (stream_id, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"),
            )
        UnitOfWork(writer).run(_setup)
        svc = EventAppendService(registry)
        event_ids: list[str] = []
        for i in range(3):
            eid = generate_event_ulid()
            event_ids.append(eid)
            def _append(uow: UnitOfWork, eid=eid, i=i):
                svc.append(
                    uow,
                    stream_id=stream_id,
                    project_id=proj_id,
                    event_kind="timeline.created" if i == 0 else "timeline.config_replaced",
                    data={"timeline_id": tl_id, "timeline_ulid": ulid, "slug": tl_slug, "name": "T1"} if i == 0 else {"timeline_id": tl_id, "config": {"tracks": [], "clips": []}, "registry": {"assets": {}}},
                    changes=["timeline_id", "slug", "name"] if i == 0 else ["config", "registry"],
                    idempotency_key=f"create:{tl_id}:{i}",
                    txn_id=generate_event_ulid(),
                    actor_kind="system",
                    event_id=eid,
                )
            UnitOfWork(writer).run(_append)
        writer.close()
        write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=3, events_sha256="abc")

        backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
        all_events = backend.read_events()
        assert len(all_events) == 3, f"expected 3 events, got {len(all_events)}"
        mid_id = all_events[1].event_id
        # after=<mid id>, limit=1 should return exactly the third event
        page = backend.read_events(after=mid_id, limit=1)
        assert len(page) == 1, f"expected 1 event in page, got {len(page)}: {[e.event_id for e in page]}"
        assert page[0].event_id == all_events[2].event_id, f"paging returned wrong event: {page[0].event_id} != {all_events[2].event_id}"
        # after beyond last should return empty? also test limit without after
        first_page = backend.read_events(limit=1)
        assert len(first_page) == 1 and first_page[0].event_id == all_events[0].event_id
        after_first = backend.read_events(after=all_events[0].event_id)
        assert len(after_first) == 2 and after_first[0].event_id == all_events[1].event_id
