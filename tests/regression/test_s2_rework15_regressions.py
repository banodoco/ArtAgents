"""Revert-sensitive regressions for S2 rework15 N3 non-layout descendant bypass.

Covers:
 1) Exact N3 shape (production-chained events + display baseline) => typed SnapshotIntegrityError, no snapshot.
 2) Legacy direct-under-root positive: timeline dir directly under caller root still acquires via files.
 3) Canonical positive: marked timeline under <root>/<project>/timelines/<ULID> still acquires from kernel.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from pathlib import Path


def _seed_marked(tmp: Path, slug: str = "proj-a", name: str = "Proj a"):
    from astrid.application import compose_standard_application
    from astrid.core.project.project import create_project

    create_project(slug, root=str(tmp), name=name)
    app = compose_standard_application(projects_root=str(tmp))
    try:
        app.projects_service.create(slug=slug, name=name)
    except Exception:
        pass
    created = app.timelines_service.create(
        project=slug, slug="marked-slug", name="MT", idempotency_key="k-n3-canonical"
    )
    assert created.data is not None
    tid = created.data["timeline_id"]
    ulid = created.data["timeline_ulid"]
    from astrid.packs.timeline.backfill import write_backfill_state

    write_backfill_state(
        tmp, timeline_id=tid, source="local_fs", source_head_version=5, events_sha256="aaan3e"
    )
    return app, tid, ulid


def test_r15_n3_detached_non_layout_raises_integrity():
    """R15-1: N3 detached/<ULID> under root with explicit project_root => SnapshotIntegrityError."""
    tmp = Path(tempfile.mkdtemp(prefix="r15-1-"))
    app = None
    try:
        app, tid, ulid = _seed_marked(tmp, slug="proj-a")
        detached = tmp / "detached" / ulid.upper()
        detached.mkdir(parents=True, exist_ok=True)
        (detached / "assembly.identity.json").write_text(
            json.dumps(
                {
                    "timeline_id": tid,
                    "timeline_ulid": ulid.upper(),
                    "backend": "local_fs",
                    "display": {
                        "schema_version": 1,
                        "slug": "marked-slug",
                        "name": "MT",
                        "is_default": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.events.schema.types import TimelineActor

        be = LocalFsBackend(timeline_id=tid, timeline_home=detached)
        actor = TimelineActor(type="system", id="oracle:n3", display="n3")
        be.append_event(
            tid,
            "timeline.renamed",
            {"old_slug": "marked-slug", "new_slug": "renamed-n3"},
            actor=actor,
        )
        be.append_event(
            tid,
            "timeline.renamed",
            {"old_slug": "renamed-n3", "new_slug": "renamed-n4"},
            actor=actor,
        )
        import astrid.core.foundation.project_paths as pp

        orig = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            from astrid.core.timeline.snapshot import SnapshotIntegrityError, acquire_snapshot

            try:
                snap = acquire_snapshot(detached, project_slug="proj-a", project_root=tmp, retries=0)
                assert False, f"expected SnapshotIntegrityError, got snapshot tid={getattr(snap, 'timeline_id', None)!r} events={len(getattr(snap, 'events', []))}"
            except SnapshotIntegrityError as exc:
                msg = str(exc).lower()
                assert "non-canonical" in msg or "authority root cannot be determined" in msg, f"wrong message: {exc}"
        finally:
            pp.resolve_projects_root = orig  # type: ignore
    finally:
        if app is not None:
            try:
                app.close()
            except Exception:
                pass
        shutil.rmtree(tmp, ignore_errors=True)


def test_r15_legacy_direct_under_root_still_acquires_via_files():
    """R15-2: timeline dir directly under caller root still acquires via files (legacy harness)."""
    tmp = Path(tempfile.mkdtemp(prefix="r15-2-"))
    app = None
    try:
        # Seed a project to have a valid projects_root, but legacy tid not in backfill state
        from astrid.application import compose_standard_application
        from astrid.core.project.project import create_project

        create_project("proj-a", root=str(tmp), name="Proj a")
        app = compose_standard_application(projects_root=str(tmp))
        try:
            app.projects_service.create(slug="proj-a", name="Proj a")
        except Exception:
            pass
        # Need at least one real project/timeline to establish DB; legacy will be separate
        created = app.timelines_service.create(
            project="proj-a", slug="seed-slug", name="Seed", idempotency_key="k-r15-legacy-seed"
        )
        assert created.data is not None
        from astrid.packs.timeline.backfill import write_backfill_state

        write_backfill_state(
            tmp,
            timeline_id=created.data["timeline_id"],
            source="local_fs",
            source_head_version=1,
            events_sha256="0" * 64,
        )
        # Legacy timeline: direct child of caller root (tmp)
        legacy_tid = str(uuid.uuid4())
        legacy_ulid = "01J000000000000000000000FA"
        legacy_dir = tmp / legacy_ulid
        legacy_dir.mkdir(parents=True, exist_ok=True)
        (legacy_dir / "assembly.identity.json").write_text(
            json.dumps(
                {
                    "timeline_id": legacy_tid,
                    "timeline_ulid": legacy_ulid,
                    "backend": "local_fs",
                    "display": {
                        "schema_version": 1,
                        "slug": "legacy-slug",
                        "name": "Legacy",
                        "is_default": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.events.schema import TimelineActor

        be = LocalFsBackend(timeline_id=legacy_tid, timeline_home=legacy_dir)
        actor = TimelineActor(type="system", id="actor:local")
        be.append_event(
            legacy_tid,
            "timeline.created",
            {"timeline_id": legacy_tid, "slug": "legacy-slug", "name": "Legacy"},
            actor=actor,
        )
        be.append_event(
            legacy_tid,
            "timeline.config_replaced",
            {"config": {"clips": [], "tracks": []}},
            actor=actor,
        )
        import astrid.core.foundation.project_paths as pp

        orig = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            from astrid.core.timeline.snapshot import acquire_snapshot

            snap = acquire_snapshot(legacy_dir, project_slug="proj-a", project_root=tmp, retries=0)
            assert snap.timeline_id == legacy_tid
            assert len(snap.events) >= 2
        finally:
            pp.resolve_projects_root = orig  # type: ignore
    finally:
        if app is not None:
            try:
                app.close()
            except Exception:
                pass
        shutil.rmtree(tmp, ignore_errors=True)


def test_r15_canonical_marked_still_kernel():
    """R15-3: canonical <root>/<project>/timelines/<ULID> marked timeline still acquires from kernel."""
    tmp = Path(tempfile.mkdtemp(prefix="r15-3-"))
    app = None
    try:
        app, tid, ulid = _seed_marked(tmp, slug="proj-a")
        canonical = tmp / "proj-a" / "timelines" / ulid.upper()
        # Canonical path is created by the service under projects_root/proj-a/timelines/<ulid>
        # In seed, the timeline_home is under projects/proj-a? Check actual location via timeline_visualize select?
        # We seeded via compose_standard_application which creates under tmp/.astrid? No, create via service
        # The service creates via repository but LocalFs timeline_home is not auto-created under projects.
        # For snapshot kernel path, we just need a dir that matches canonical layout and has no LocalFs files;
        # The kernel path is authoritative and ignores files. So create the canonical placeholder.
        canonical.mkdir(parents=True, exist_ok=True)
        # Write a correct identity sidecar pointing to marked tid to match kernel binding (optional)
        (canonical / "assembly.identity.json").write_text(
            json.dumps(
                {
                    "timeline_id": tid,
                    "timeline_ulid": ulid.upper(),
                    "backend": "local_fs",
                    "display": {
                        "schema_version": 1,
                        "slug": "marked-slug",
                        "name": "MT",
                        "is_default": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        import astrid.core.foundation.project_paths as pp

        orig = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            from astrid.core.timeline.snapshot import acquire_snapshot

            snap = acquire_snapshot(canonical, project_slug="proj-a", project_root=tmp, retries=0)
            assert snap.timeline_id == tid, f"canonical kernel tid {snap.timeline_id!r} != {tid!r}"
            # Should be kernel-backed: head_version from kernel, not just 2 local events
            # At least one event (the creation) should be present
            assert len(snap.events) >= 1
        finally:
            pp.resolve_projects_root = orig  # type: ignore
    finally:
        if app is not None:
            try:
                app.close()
            except Exception:
                pass
        shutil.rmtree(tmp, ignore_errors=True)
