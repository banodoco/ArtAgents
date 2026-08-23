"""Revert-sensitive regressions for S2 rework13 N1 poisoned identity cache.

Covers:
 1) N1 discover shape: poisoned-sidecar B dir => discover does NOT return A's tid (diagnostic skip recorded); B's own seeded timeline still discovered.
 2) N1 snapshot shape: acquire_snapshot on same dir raises SnapshotIntegrityError, never returns A's tid.
 3) Within-project positive: A's own dir with correct sidecar still acquires from kernel (tid == A's tid).
 4) Legacy unbackfilled positive: sidecar id NOT in state => legacy LocalFs path still functions.
"""

import json
import shutil
import tempfile
import uuid
from pathlib import Path

from astrid.packs.timeline.backfill import write_backfill_state


def _tdir(tmp: Path, project_slug: str, ulid: str) -> Path:
    d = tmp / project_slug / "timelines" / ulid.upper()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_poisoned_identity(timeline_dir: Path, tid: str, ulid: str, slug: str = "b-snoop") -> None:
    ulid_u = ulid.upper()
    data = {
        "timeline_id": tid,
        "timeline_ulid": ulid_u,
        "ulid": ulid_u,
        "uuid": tid,
        "stable_id": tid,
        "qualified_ref": "TL01",
        "slug": slug,
        "display": {"slug": slug, "is_default": False},
    }
    timeline_dir.mkdir(parents=True, exist_ok=True)
    (timeline_dir / "assembly.identity.json").write_text(json.dumps(data), encoding="utf-8")


def _seed_two_projects_with_A(tmp: Path):
    from astrid.core.project.project import create_project

    for proj in ("proj-a", "proj-b"):
        create_project(proj, root=str(tmp), name=f"Proj {proj}")
    from astrid.application import compose_standard_application

    app = compose_standard_application(projects_root=str(tmp))
    for proj in ("proj-a", "proj-b"):
        try:
            app.projects_service.create(slug=proj, name=f"Proj {proj}")
        except Exception:
            pass
    created_a = app.timelines_service.create(
        project="proj-a", slug="a-secret-slug", name="TA", idempotency_key="k-a-13"
    )
    tid_a = created_a.data["timeline_id"]
    ulid_a = created_a.data["timeline_ulid"]
    # Ensure A dir exists on filesystem for snapshot/discover positive
    a_dir = tmp / "proj-a" / "timelines" / ulid_a.upper()
    a_dir.mkdir(parents=True, exist_ok=True)
    _write_poisoned_identity(a_dir, tid_a, ulid_a, slug="a-secret-slug")
    # Also ensure display.json reflects slug for completeness
    write_backfill_state(tmp, timeline_id=tid_a, source="local_fs", source_head_version=1, events_sha256="aaa13")
    return app, tid_a, ulid_a


def test_r13_discover_poisoned_sidecar_does_not_bind_A():
    """R13-1: poisoned-sidecar B dir => discover does NOT return any timeline with A's tid; B's own seeded timeline still discovered."""
    tmp = Path(tempfile.mkdtemp(prefix="r13-1-"))
    try:
        app, tid_a, ulid_a = _seed_two_projects_with_A(tmp)
        # Create B's own legitimate timeline
        created_b = app.timelines_service.create(
            project="proj-b", slug="b-own-slug", name="TB", idempotency_key="k-b-13"
        )
        tid_b = created_b.data["timeline_id"]
        ulid_b = created_b.data["timeline_ulid"]
        # Poisoned B dir using A's ULID and A's tid
        b_poisoned = _tdir(tmp, "proj-b", ulid_a.upper())
        _write_poisoned_identity(b_poisoned, tid_a, ulid_a, slug="b-snoop")
        # Ensure B own dir exists on fs with correct identity for discover
        b_own_dir = tmp / "proj-b" / "timelines" / ulid_b.upper()
        b_own_dir.mkdir(parents=True, exist_ok=True)
        _write_poisoned_identity(b_own_dir, tid_b, ulid_b, slug="b-own-slug")

        # Patch projects_root resolution to tmp
        import astrid.core.foundation.project_paths as pp

        orig = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            from astrid.packs.rendering.executors.timeline_visualize.select import _discover

            timelines, diagnostics = _discover(tmp / "proj-b")
            tids = [t.timeline_id for t in timelines]
            assert tid_a not in tids, f"R13 LEAK discover binds A tid {tid_a} in B: {tids} diagnostics={diagnostics}"
            # B's own legitimate timeline still discovered
            assert tid_b in tids, f"R13 B own timeline missing: {tids} diagnostics={diagnostics}"
            # Diagnostic must mention identity cache names another project's authoritative stream
            joined = " ".join(diagnostics)
            assert "identity cache names another project's authoritative stream" in joined, f"missing foreign diagnostic: {diagnostics}"
        finally:
            pp.resolve_projects_root = orig  # type: ignore
        app.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r13_snapshot_poisoned_raises_integrity():
    """R13-2: acquire_snapshot on poisoned B dir raises SnapshotIntegrityError and never returns A's tid."""
    tmp = Path(tempfile.mkdtemp(prefix="r13-2-"))
    try:
        app, tid_a, ulid_a = _seed_two_projects_with_A(tmp)
        b_poisoned = _tdir(tmp, "proj-b", ulid_a.upper())
        _write_poisoned_identity(b_poisoned, tid_a, ulid_a, slug="b-snoop")
        import astrid.core.foundation.project_paths as pp

        orig = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            from astrid.core.timeline.snapshot import SnapshotIntegrityError, acquire_snapshot

            try:
                snap = acquire_snapshot(b_poisoned, project_slug="proj-b", project_root=tmp)
            except SnapshotIntegrityError as exc:
                msg = str(exc)
                assert "another project's authoritative stream" in msg, f"wrong message: {msg}"
                assert "delete the disposable sidecar cache" in msg, f"missing repair hint: {msg}"
            else:
                assert False, f"expected SnapshotIntegrityError but got snapshot with tid {snap.timeline_id!r} events={len(snap.events)}"
        finally:
            pp.resolve_projects_root = orig  # type: ignore
        app.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r13_A_own_dir_still_kernel():
    """R13-3: A's own dir with correct sidecar still acquires from kernel (tid == A's tid)."""
    tmp = Path(tempfile.mkdtemp(prefix="r13-3-"))
    try:
        app, tid_a, ulid_a = _seed_two_projects_with_A(tmp)
        a_dir = tmp / "proj-a" / "timelines" / ulid_a.upper()
        # Ensure identity is correct (already written)
        _write_poisoned_identity(a_dir, tid_a, ulid_a, slug="a-secret-slug")
        import astrid.core.foundation.project_paths as pp

        orig = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            from astrid.core.timeline.snapshot import acquire_snapshot

            snap = acquire_snapshot(a_dir, project_slug="proj-a", project_root=tmp)
            assert snap.timeline_id == tid_a, f"A own tid mismatch: {snap.timeline_id!r} != {tid_a!r}"
            assert snap.timeline_ulid.upper() == ulid_a.upper()
        finally:
            pp.resolve_projects_root = orig  # type: ignore
        app.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r13_legacy_unbackfilled_still_legacy():
    """R13-4: sidecar id NOT in state => legacy LocalFs path still functions."""
    tmp = Path(tempfile.mkdtemp(prefix="r13-4-"))
    try:
        app, tid_a, ulid_a = _seed_two_projects_with_A(tmp)
        # Legacy random tid/ulid not in backfill state
        legacy_tid = str(uuid.uuid4())
        # Generate a fresh ULID not colliding: use uppercase random Crockford-like but guaranteed different
        # Use derive from uuid for determinism: take 26 chars from base32 alphabet via simple mapping
        legacy_ulid = "01J00000000000000000000099"
        # Ensure not same as ulid_a
        legacy_dir = _tdir(tmp, "proj-b", legacy_ulid)
        _write_poisoned_identity(legacy_dir, legacy_tid, legacy_ulid, slug="legacy-slug")
        # Create minimal valid LocalFs event log for legacy path via LocalFsBackend
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.events.schema import TimelineActor

        # Need to ensure directory has a valid event chain; use backend to append events
        # Reuse helper spec to produce a valid chain
        backend = LocalFsBackend(timeline_id=legacy_tid, timeline_home=legacy_dir)
        # Minimal created event payload
        backend.append_event(
            legacy_tid,
            "timeline.created",
            {"timeline_id": legacy_tid, "slug": "legacy-slug", "name": "Legacy"},
            actor=TimelineActor(type="system", id="actor:local"),
        )
        # At least one more event to have non-empty snapshot (optional)
        backend.append_event(
            legacy_tid,
            "timeline.config_replaced",
            {"config": {"clips": [], "tracks": []}},
            actor=TimelineActor(type="system", id="actor:local"),
        )
        import astrid.core.foundation.project_paths as pp

        orig = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            from astrid.core.timeline.snapshot import _is_timeline_backfilled, acquire_snapshot

            is_bf, known = _is_timeline_backfilled(legacy_dir, tmp)
            assert is_bf is False, f"legacy should not be backfilled: {is_bf} known={known}"
            assert known == legacy_tid, f"legacy known tid mismatch: {known!r} != {legacy_tid!r}"

            from astrid.packs.rendering.executors.timeline_visualize.select import _discover

            timelines, diagnostics = _discover(tmp / "proj-b")
            tids = [t.timeline_id for t in timelines]
            assert legacy_tid in tids, f"legacy tid not discovered: {tids} diagnostics={diagnostics}"
            # Snapshot via legacy LocalFs should succeed and not raise foreign error
            snap = acquire_snapshot(legacy_dir, project_slug="proj-b", project_root=tmp)
            assert snap.timeline_id == legacy_tid, f"legacy snapshot tid {snap.timeline_id!r} != {legacy_tid!r}"
        finally:
            pp.resolve_projects_root = orig  # type: ignore
        app.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
