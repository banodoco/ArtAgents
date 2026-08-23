"""Revert-sensitive regressions for S2 rework14 N2 guard fallbacks.

Covers:
 1) Projects-lookup fault + poisoned uppercase-import cache in B => discover skips (no A tid) AND snapshot raises typed SnapshotIntegrityError.
 2) Snapshot-guard indeterminate (connection-level fault) => typed failure, never acceptance, never silent LocalFs downgrade.
 3) Positives battery: A-own correct-sidecar kernel acquisition; legacy unbackfilled; corrupt-marker BackfillError; B own discovered.
"""

import json
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path
from unittest import mock

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
        project="proj-a", slug="a-secret-slug", name="TA", idempotency_key="k-a-14"
    )
    tid_a = created_a.data["timeline_id"]
    ulid_a = created_a.data["timeline_ulid"]
    ulid_a_up = ulid_a.upper()
    a_dir = tmp / "proj-a" / "timelines" / ulid_a_up
    a_dir.mkdir(parents=True, exist_ok=True)
    _write_poisoned_identity(a_dir, tid_a, ulid_a_up, slug="a-secret-slug")
    write_backfill_state(tmp, timeline_id=tid_a, source="local_fs", source_head_version=1, events_sha256="aaa14")
    created_b = app.timelines_service.create(
        project="proj-b", slug="b-legit", name="TB", idempotency_key="k-b-14"
    )
    tid_b = created_b.data["timeline_id"]
    ulid_b = created_b.data["timeline_ulid"]
    ulid_b_up = ulid_b.upper()
    b_dir = tmp / "proj-b" / "timelines" / ulid_b_up
    b_dir.mkdir(parents=True, exist_ok=True)
    _write_poisoned_identity(b_dir, tid_b, ulid_b_up, slug="b-legit")
    write_backfill_state(tmp, timeline_id=tid_b, source="local_fs", source_head_version=1, events_sha256="bbb14")
    return app, tid_a, ulid_a_up, tid_b, ulid_b_up


def test_r14_projects_lookup_fault_discover_skips_and_snapshot_raises():
    """R14-1: projects-lookup fault + poisoned uppercase cache in B => discover skips AND snapshot raises."""
    tmp = Path(tempfile.mkdtemp(prefix="r14-1-"))
    try:
        app, tid_a, ulid_a, tid_b, ulid_b = _seed_two_projects_with_A(tmp)
        b_poisoned = _tdir(tmp, "proj-b", ulid_a)
        _write_poisoned_identity(b_poisoned, tid_a, ulid_a, slug="b-snoop")
        import astrid.core.foundation.project_paths as pp

        orig_resolve = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        real_connect = sqlite3.connect

        def _fault_connect(*args, **kwargs):
            conn = real_connect(*args, **kwargs)
            orig_execute = conn.execute

            def _fault_execute(sql, *a, **kw):
                if "FROM projects WHERE slug=" in sql:
                    raise sqlite3.OperationalError("no such table: projects")
                return orig_execute(sql, *a, **kw)

            conn.execute = _fault_execute  # type: ignore
            return conn

        try:
            with mock.patch("sqlite3.connect", side_effect=_fault_connect):
                from astrid.packs.rendering.executors.timeline_visualize.select import _discover

                timelines, diagnostics = _discover(tmp / "proj-b")
                tids = [t.timeline_id for t in timelines]
                assert tid_a not in tids, f"R14 LEAK discover binds A tid {tid_a} in B under projects fault: {tids} diagnostics={diagnostics}"
                joined = " ".join(diagnostics)
                assert "UNVERIFIABLE" in joined, f"missing UNVERIFIABLE diagnostic under fault: {diagnostics}"
                assert "delete the disposable sidecar cache" in joined, f"missing repair hint: {diagnostics}"
            with mock.patch("sqlite3.connect", side_effect=_fault_connect):
                from astrid.core.timeline.snapshot import SnapshotIntegrityError, acquire_snapshot

                try:
                    snap = acquire_snapshot(b_poisoned, project_slug="proj-b", project_root=tmp)
                except SnapshotIntegrityError as exc:
                    msg = str(exc)
                    assert "UNVERIFIABLE" in msg, f"wrong snapshot message under projects fault: {msg}"
                    assert "delete the disposable sidecar cache" in msg, f"missing repair hint: {msg}"
                else:
                    assert False, f"expected SnapshotIntegrityError under projects fault but got snapshot tid {snap.timeline_id!r}"
        finally:
            pp.resolve_projects_root = orig_resolve  # type: ignore
        app.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r14_snapshot_connection_fault_raises_unverifiable():
    """R14-2: connection-level fault at snapshot guard => typed SnapshotIntegrityError, never LocalFs acceptance."""
    tmp = Path(tempfile.mkdtemp(prefix="r14-2-"))
    try:
        app, tid_a, ulid_a, tid_b, ulid_b = _seed_two_projects_with_A(tmp)
        b_poisoned = _tdir(tmp, "proj-b", ulid_a)
        _write_poisoned_identity(b_poisoned, tid_a, ulid_a, slug="b-snoop-conn")
        import astrid.core.foundation.project_paths as pp

        orig_resolve = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            from astrid.core.timeline.snapshot import SnapshotIntegrityError, acquire_snapshot

            def _conn_fault(*args, **kwargs):
                raise sqlite3.OperationalError("connection failed: disk I/O error")

            with mock.patch("sqlite3.connect", side_effect=_conn_fault):
                try:
                    snap = acquire_snapshot(b_poisoned, project_slug="proj-b", project_root=tmp)
                except SnapshotIntegrityError as exc:
                    msg = str(exc)
                    assert "UNVERIFIABLE" in msg, f"missing UNVERIFIABLE under conn fault: {msg}"
                    assert "delete the disposable sidecar cache" in msg, f"missing repair hint under conn fault: {msg}"
                    assert "LocalFs" not in msg
                else:
                    assert False, f"expected SnapshotIntegrityError under connection fault but got snapshot tid {snap.timeline_id!r} events={len(snap.events)}"
            with mock.patch("sqlite3.connect", side_effect=_conn_fault):
                from astrid.packs.rendering.executors.timeline_visualize.select import _discover

                timelines, diagnostics = _discover(tmp / "proj-b")
                tids = [t.timeline_id for t in timelines]
                assert tid_a not in tids, f"R14 LEAK discover binds A tid under conn fault: {tids} {diagnostics}"
                joined = " ".join(diagnostics)
                assert "UNVERIFIABLE" in joined, f"missing UNVERIFIABLE discover diagnostic under conn fault: {diagnostics}"
        finally:
            pp.resolve_projects_root = orig_resolve  # type: ignore
        app.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r14_positives_battery():
    """R14-3: positives battery — A-own kernel acquisition; legacy; corrupt marker; B own discovered."""
    tmp = Path(tempfile.mkdtemp(prefix="r14-3-"))
    try:
        app, tid_a, ulid_a, tid_b, ulid_b = _seed_two_projects_with_A(tmp)
        import astrid.core.foundation.project_paths as pp

        orig_resolve = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            from astrid.core.timeline.snapshot import SnapshotIntegrityError, acquire_snapshot

            a_dir = tmp / "proj-a" / "timelines" / ulid_a.upper()
            snap = acquire_snapshot(a_dir, project_slug="proj-a", project_root=tmp)
            assert snap.timeline_id == tid_a, f"A own tid mismatch {snap.timeline_id!r} != {tid_a!r}"
            assert snap.timeline_ulid.upper() == ulid_a.upper()
            from astrid.packs.rendering.executors.timeline_visualize.select import _discover

            timelines, diagnostics = _discover(tmp / "proj-b")
            tids = [t.timeline_id for t in timelines]
            assert tid_b in tids, f"B own timeline missing: {tids} diagnostics={diagnostics}"
            legacy_tid = str(uuid.uuid4())
            legacy_ulid = "01J00000000000000000000099"
            legacy_dir = _tdir(tmp, "proj-b", legacy_ulid)
            _write_poisoned_identity(legacy_dir, legacy_tid, legacy_ulid, slug="legacy-slug")
            from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
            from astrid.core.timeline.events.schema import TimelineActor

            backend = LocalFsBackend(timeline_id=legacy_tid, timeline_home=legacy_dir)
            backend.append_event(
                legacy_tid,
                "timeline.created",
                {"timeline_id": legacy_tid, "slug": "legacy-slug", "name": "Legacy"},
                actor=TimelineActor(type="system", id="actor:local"),
            )
            backend.append_event(
                legacy_tid,
                "timeline.config_replaced",
                {"config": {"clips": [], "tracks": []}},
                actor=TimelineActor(type="system", id="actor:local"),
            )
            from astrid.core.timeline.snapshot import _is_timeline_backfilled

            is_bf, known = _is_timeline_backfilled(legacy_dir, tmp)
            assert is_bf is False, f"legacy should not be backfilled {is_bf} {known}"
            assert known == legacy_tid
            timelines2, _ = _discover(tmp / "proj-b")
            assert legacy_tid in [t.timeline_id for t in timelines2], f"legacy tid not discovered {diagnostics}"
            snap2 = acquire_snapshot(legacy_dir, project_slug="proj-b", project_root=tmp)
            assert snap2.timeline_id == legacy_tid
            from astrid.packs.timeline.backfill import BackfillError, backfill_state_path

            marker = backfill_state_path(tmp)
            marker.write_text("{ not json", encoding="utf-8")
            try:
                acquire_snapshot(a_dir, project_slug="proj-a", project_root=tmp)
                assert False, "expected BackfillError/SnapshotIntegrityError on corrupt marker"
            except (BackfillError, SnapshotIntegrityError) as exc:
                msg = str(exc)
                assert "backfill authority marker is unreadable" in msg, f"wrong corrupt marker message: {msg}"
            finally:
                import json as _js

                marker.write_text(_js.dumps({tid_a: {"backfilled_at": "2026-01-01T00:00:00Z", "source": "local_fs", "source_head_version": 1, "events_sha256": "0"*64, "synthesized_bootstrap": False, "identity_sha256": "0"*64, "registry_sha256": ""}, tid_b: {"backfilled_at": "2026-01-01T00:00:00Z", "source": "local_fs", "source_head_version": 1, "events_sha256": "0"*64, "synthesized_bootstrap": False, "identity_sha256": "0"*64, "registry_sha256": ""}}), encoding="utf-8")
        finally:
            pp.resolve_projects_root = orig_resolve  # type: ignore
        app.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
