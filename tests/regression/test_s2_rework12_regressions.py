"""Revert-sensitive regressions for S2 rework12 M1 authority scoping.

Covers:
 1) B empty sidecarless dir named after A's ULID must NOT leak A's display via
    load_display_json_with_repair (no-events-file authority path).
 2) Within-project positive: A's own dir still resolves via SAME path.
 3) Scoped check through visualize seam (foreign ULID must not bind).
"""
import shutil
import tempfile
from pathlib import Path

from astrid.packs.timeline.backfill import write_backfill_state


def _tdir(tmp: Path, project_slug: str, ulid: str) -> Path:
    d = tmp / project_slug / "timelines" / ulid.upper()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _seed_two_projects_shared_ulid(tmp: Path):
    from astrid.core.project.project import create_project

    for proj in ("proj-a", "proj-b"):
        create_project(proj, root=str(tmp), name=f"Proj {proj}")
    from astrid.application import compose_standard_application

    app = compose_standard_application(projects_root=str(tmp))
    for proj in ("proj-a", "proj-b"):
        try:
            app.projects_service.create(slug=proj, name=f"Proj {proj}")
        except Exception as exc:  # noqa: BLE001
            _ = exc
    created_a = app.timelines_service.create(
        project="proj-a", slug="a-secret-slug", name="TA", idempotency_key="k-a-12"
    )
    tid_a = created_a.data["timeline_id"]
    ulid_a = created_a.data["timeline_ulid"]
    _tdir(tmp, "proj-a", ulid_a.upper())
    write_backfill_state(
        tmp, timeline_id=tid_a, source="local_fs", source_head_version=1, events_sha256="aaa12"
    )
    return app, tid_a, ulid_a


def test_r12_B_empty_sidecarless_does_not_leak_A_display_via_authority():
    """R12-1: B empty sidecarless dir named after A's ULID => load_display_json_with_repair returns NOT_A."""
    tmp = Path(tempfile.mkdtemp())
    try:
        _app, tid_a, ulid_a = _seed_two_projects_shared_ulid(tmp)
        a_cands = list((tmp / "proj-a" / "timelines").iterdir())
        a_home = next(
            (p for p in a_cands if p.is_dir() and p.name.lower() == ulid_a.lower()),
            tmp / "proj-a" / "timelines" / ulid_a.upper(),
        )
        for fn in ("assembly.jsonl", "assembly.identity.json", "display.json"):
            p = a_home / fn
            if p.is_file():
                p.unlink()
        b_dir = _tdir(tmp, "proj-b", ulid_a)
        for fn in ("assembly.jsonl", "assembly.identity.json", "display.json"):
            p = b_dir / fn
            if p.is_file():
                p.unlink()
        import astrid.core.foundation.project_paths as pp

        orig = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            from astrid.core.timeline.paths import load_display_json_with_repair

            result_b = load_display_json_with_repair(b_dir)
            if isinstance(result_b, dict):
                assert result_b.get("slug") != "a-secret-slug", f"R12 LEAKS_A True got {result_b}"
                assert result_b.get("name") != "TA", f"R12 leak name {result_b}"
            disp_b = b_dir / "display.json"
            if disp_b.is_file():
                import json

                data = json.loads(disp_b.read_text())
                assert data.get("slug") != "a-secret-slug", f"R12 cache poisoning {data}"
            assert result_b is None or (
                isinstance(result_b, dict) and result_b.get("slug") != "a-secret-slug"
            )
        finally:
            pp.resolve_projects_root = orig  # type: ignore
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r12_A_own_dir_still_resolves_through_same_no_events_path():
    """R12-2: A's own empty sidecarless dir still resolves A's display via same authority path."""
    tmp = Path(tempfile.mkdtemp())
    try:
        _app, tid_a, ulid_a = _seed_two_projects_shared_ulid(tmp)
        a_cands = list((tmp / "proj-a" / "timelines").iterdir())
        a_home = next(
            (p for p in a_cands if p.is_dir() and p.name.lower() == ulid_a.lower()),
            tmp / "proj-a" / "timelines" / ulid_a.upper(),
        )
        for fn in ("assembly.jsonl", "assembly.identity.json", "display.json"):
            p = a_home / fn
            if p.is_file():
                p.unlink()
        import astrid.core.foundation.project_paths as pp

        orig = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            from astrid.core.timeline.paths import load_display_json_with_repair

            result_a = load_display_json_with_repair(a_home)
            assert isinstance(result_a, dict), f"A own sidecarless should resolve, got {result_a}"
            assert result_a.get("slug") == "a-secret-slug", f"A own dir failed {result_a}"
            assert result_a.get("name") == "TA", f"A own name failed {result_a}"
        finally:
            pp.resolve_projects_root = orig  # type: ignore
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r12_visualize_foreign_ulid_does_not_bind():
    """R12-3: Visualize discover for proj-b with foreign ULID must not bind to A's stream."""
    tmp = Path(tempfile.mkdtemp())
    try:
        _app, tid_a, ulid_a = _seed_two_projects_shared_ulid(tmp)
        b_dir = _tdir(tmp, "proj-b", ulid_a)
        for fn in ("assembly.identity.json", "assembly.jsonl"):
            p = b_dir / fn
            if p.is_file():
                p.unlink()
        from astrid.packs.rendering.executors.timeline_visualize.select import discover_timelines

        proj_b_root = tmp / "proj-b"
        timelines_b = discover_timelines(proj_b_root)
        for t in timelines_b:
            if t.timeline_dir.name.lower() == ulid_a.lower():
                assert t.slug != "a-secret-slug", f"visualize leak slug {t}"
                assert t.timeline_id.lower() != tid_a.lower(), f"visualize leak tid {t.timeline_id} vs {tid_a}"
        tids_b = {t.timeline_id.lower() for t in timelines_b}
        assert tid_a.lower() not in tids_b, f"B discover leaks A's tid {tid_a} in {tids_b}"
        proj_a_root = tmp / "proj-a"
        timelines_a = discover_timelines(proj_a_root)
        tids_a = {t.timeline_id.lower() for t in timelines_a}
        assert tid_a.lower() in tids_a, f"A own discover missing {tid_a} in {tids_a}"
        found_a = next((t for t in timelines_a if t.timeline_id.lower() == tid_a.lower()), None)
        assert found_a is not None
        assert found_a.slug == "a-secret-slug"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
