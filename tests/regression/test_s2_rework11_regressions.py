"""Revert-sensitive regressions for S2 rework11 M1 tenant-isolation + M2 assembly contract."""

import shutil
import tempfile
from pathlib import Path

from astrid.packs.timeline.backfill import write_backfill_state


def _tdir(tmp: Path, project_slug: str, ulid: str) -> Path:
    d = tmp / project_slug / "timelines" / ulid
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
    created_a = app.timelines_service.create(project="proj-a", slug="a-secret-slug", name="TA", idempotency_key="k-a-11")
    tid_a = created_a.data["timeline_id"]
    ulid_a = created_a.data["timeline_ulid"]
    _tdir(tmp, "proj-a", ulid_a.upper())
    write_backfill_state(tmp, timeline_id=tid_a, source="local_fs", source_head_version=1, events_sha256="aaa11")
    return app, tid_a, ulid_a


def test_m1_b_sidecarless_does_not_leak_a_display_and_no_cache():
    """M1: B sidecarless dir named after A's ULID must NOT return A's display and must NOT poison display.json."""
    tmp = Path(tempfile.mkdtemp())
    try:
        _app, tid_a, ulid_a = _seed_two_projects_shared_ulid(tmp)
        b_dir = _tdir(tmp, "proj-b", ulid_a)
        (b_dir / "assembly.jsonl").write_text("{}\n")
        from astrid.core.timeline.paths import load_display_json_with_repair

        candidates = list((tmp / "proj-a" / "timelines").iterdir())
        a_home = next((p for p in candidates if p.is_dir() and p.name.lower() == ulid_a.lower()), candidates[0] if candidates else tmp / "proj-a" / "timelines" / ulid_a)
        (a_home / "assembly.jsonl").write_text("{}\n")
        ident_a = a_home / "assembly.identity.json"
        if ident_a.is_file():
            ident_a.unlink()
        disp_b = b_dir / "display.json"
        if disp_b.is_file():
            disp_b.unlink()
        import astrid.core.foundation.project_paths as pp

        orig_rr = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            result_b = load_display_json_with_repair(b_dir)
            if isinstance(result_b, dict):
                assert result_b.get("slug") != "a-secret-slug", f"M1 DISPLAY_LEAKS_A True got {result_b}"
                assert result_b.get("name") != "TA", f"M1 leak name {result_b}"
            if disp_b.is_file():
                import json

                data = json.loads(disp_b.read_text())
                assert data.get("slug") != "a-secret-slug", f"M1 cache poisoning {data}"
                assert data.get("name") != "TA"
            result_a = load_display_json_with_repair(a_home)
            assert isinstance(result_a, dict), "A own sidecarless should resolve"
            assert result_a.get("slug") == "a-secret-slug", f"A own dir failed {result_a}"
        finally:
            pp.resolve_projects_root = orig_rr  # type: ignore
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_m1_bridge_find_list_scoped():
    """M1 bridge find/list must not leak across projects via sidecarless repair."""
    tmp = Path(tempfile.mkdtemp())
    try:
        _app, _tid_a, ulid_a = _seed_two_projects_shared_ulid(tmp)
        b_dir = _tdir(tmp, "proj-b", ulid_a)
        (b_dir / "assembly.jsonl").write_text("{}\n")
        import astrid.core.foundation.project_paths as pp

        orig_rr = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            from astrid.core.integrations.reigh.local_bridge import (
                find_bridge_timeline,
                list_bridge_timelines,
            )

            found = find_bridge_timeline("proj-b", ulid_a, root=tmp)
            if found is not None:
                assert found.slug != "a-secret-slug", f"bridge find leaks {found}"
            records = list_bridge_timelines("proj-b", root=tmp)
            for rec in records:
                if rec.timeline_ulid.lower() == ulid_a.lower():
                    assert rec.slug != "a-secret-slug", f"bridge list leaks {rec}"
                    assert rec.name != "TA"
            recs_a = list_bridge_timelines("proj-a", root=tmp)
            assert any(r.timeline_ulid.lower() == ulid_a.lower() and r.slug == "a-secret-slug" for r in recs_a), f"A list missing {recs_a}"
        finally:
            pp.resolve_projects_root = orig_rr  # type: ignore
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_m2_sidecarless_assembly_returns_config_with_tracks():
    """M2: sidecarless marked timeline with assembly.jsonl must return TimelineConfig shape containing tracks."""
    tmp = Path(tempfile.mkdtemp())
    try:
        _app, _tid_a, ulid_a = _seed_two_projects_shared_ulid(tmp)
        from astrid.core.timeline.paths import load_assembly_json_with_repair

        candidates = list((tmp / "proj-a" / "timelines").iterdir())
        a_home = next((p for p in candidates if p.is_dir() and p.name.lower() == ulid_a.lower()), candidates[0] if candidates else tmp / "proj-a" / "timelines" / ulid_a)
        ident = a_home / "assembly.identity.json"
        if ident.is_file():
            ident.unlink()
        (a_home / "assembly.jsonl").write_text("{}\n")
        import astrid.core.foundation.project_paths as pp

        orig_rr = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            result = load_assembly_json_with_repair(a_home)
            assert isinstance(result, dict), f"M2 expected dict got {result}"
            assert "tracks" in result, f"M2 missing tracks {result}"
            assert "is_default" not in result or "tracks" in result, f"M2 is DISPLAY not CONFIG {result}"
            assert result.get("slug") is None or "tracks" in result, f"M2 returned display {result}"
            assert not (set(result.keys()) == {"slug", "name", "is_default", "schema_version"}), f"M2 display leak {result}"
        finally:
            pp.resolve_projects_root = orig_rr  # type: ignore
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_m2_within_project_display_still_resolves():
    """Within-project sidecarless display repair still resolves own stream (control)."""
    tmp = Path(tempfile.mkdtemp())
    try:
        _app, _tid_a, ulid_a = _seed_two_projects_shared_ulid(tmp)
        from astrid.core.timeline.paths import load_display_json_with_repair

        candidates = list((tmp / "proj-a" / "timelines").iterdir())
        a_home = next((p for p in candidates if p.is_dir() and p.name.lower() == ulid_a.lower()), candidates[0] if candidates else tmp / "proj-a" / "timelines" / ulid_a)
        (a_home / "assembly.jsonl").write_text("{}\n")
        ident = a_home / "assembly.identity.json"
        if ident.is_file():
            ident.unlink()
        import astrid.core.foundation.project_paths as pp

        orig_rr = pp.resolve_projects_root
        pp.resolve_projects_root = lambda root=None: tmp  # type: ignore
        try:
            result = load_display_json_with_repair(a_home)
            assert isinstance(result, dict) and result.get("slug") == "a-secret-slug"
        finally:
            pp.resolve_projects_root = orig_rr  # type: ignore
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
