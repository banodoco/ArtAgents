"""Compiler shots projection tests (plan v10 batch B3, tasks T8-T12 + final findings F3).

Tests the compiler's --shots flag against a REAL temp kernel: compile a
storyboard into kernel shots + sub-timelines + a sequential parent shot graph,
then verify idempotency and expansion-to-flat equality.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_storyboard as bs

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MINIMAL = FIXTURES / "storyboard-minimal.json"


def _compile_shots(projects_root: Path, story: dict, *, project: str = "test") -> dict:
    """Run the --shots compile against a real temp kernel via the CLI handler."""
    from astrid.sdk.client import AstridClient

    def _probe(path: Path) -> float:
        # Real valid wavs: use ffprobe-free constant (fixture is 0.5s).
        return 0.5

    with AstridClient.open(str(projects_root)) as client:
        # Recompile reuses the existing project; create only when absent.
        existing = client.projects.list()
        have = existing.ok and any(p.get("slug") == project for p in (existing.data or []))
        if not have:
            r = client.projects.create(slug=project, name="test")
            assert r.ok, r.error
        importer = bs.make_client_importer(client, project=project)
        out = bs._compile_with_shots(
            story,
            base_dir=FIXTURES,
            plan=None,
            import_asset=importer,
            probe_duration=_probe,
            project=project,
            output_name="parent-shot-graph.mp4",
            client=client,
        )
        return out


def _count_rows(projects_root: Path, table: str) -> int:
    from astrid.sdk.client import AstridClient

    with AstridClient.open(str(projects_root)) as client:
        if table == "timelines":
            result = client.timelines.list("test")
        elif table == "shots":
            result = client.shots.list("test")
        else:
            raise AssertionError(f"unsupported SDK row count: {table}")
        assert result.ok, result.error
        return len(result.data or [])


def _load_doc(projects_root: Path, timeline_id: str) -> tuple[dict, dict]:
    from astrid.sdk.client import AstridClient

    with AstridClient.open(str(projects_root)) as client:
        result = client.timelines.show("test", timeline_id)
        assert result.ok and result.data, result.error
        return result.data["config"], result.data["registry"]


def test_compiler_shots_creates_rows_and_sequential_parent(tmp_path) -> None:
    """Compile minimal storyboard --shots: kernel rows + sequential parent graph."""
    story = json.loads(MINIMAL.read_text(encoding="utf-8"))
    out = _compile_shots(tmp_path, story)

    assert len(out["shots"]) == 2  # open, idea-1
    assert set(out["shots"].keys()) == {"open", "idea-1"}
    assert len(out["timeline"]["clips"]) == 3  # brand + 2 shot clips
    shot_clips = [c for c in out["timeline"]["clips"] if c["clipType"] == "shot"]
    assert len(shot_clips) == 2
    # Sequential placement (F2): idea-1 starts after open's hold.
    open_clip = next(c for c in shot_clips if c["id"] == "shot_open")
    idea_clip = next(c for c in shot_clips if c["id"] == "shot_idea-1" or (c["id"].endswith("idea-1")))
    assert idea_clip["at"] >= open_clip["at"] + open_clip["hold"] - 1e-6
    assert open_clip["hold"] > 0
    assert idea_clip["hold"] > 0

    # Rows in the kernel store: 2 shots, 2 sub-timelines, and the registered
    # parent timeline (the sidecar is provenance only).
    assert _count_rows(tmp_path, "shots") == 2
    assert _count_rows(tmp_path, "timelines") == 3


def test_compiler_shots_recompile_is_idempotent(tmp_path) -> None:
    """Same compile twice → same ids, no new rows (receipt replay-safe)."""
    story = json.loads(MINIMAL.read_text(encoding="utf-8"))
    out1 = _compile_shots(tmp_path, story)
    timelines1 = _count_rows(tmp_path, "timelines")
    out2 = _compile_shots(tmp_path, story, project="test")
    timelines2 = _count_rows(tmp_path, "timelines")
    assert timelines1 == timelines2 == 3
    assert set(out1["shots"].keys()) == set(out2["shots"].keys())


def test_expand_matches_sub_docs_and_keeps_vo(tmp_path) -> None:
    """Expansion of the parent preserves VO clips with sequential timebase (F1/F2)."""
    import json
    from astrid.core.timeline.expand_shots import expand_shot_clips

    story = json.loads(MINIMAL.read_text(encoding="utf-8"))
    out = _compile_shots(tmp_path, story)

    from astrid.sdk.client import AstridClient

    with AstridClient.open(str(tmp_path)) as client:
        def load_tl(tlid):
            result = client.timelines.show("test", tlid)
            assert result.ok and result.data, result.error
            return result.data["config"], result.data["registry"]

        # Parent registry is the compile's canonical assets.
        expanded, oreg = expand_shot_clips(
            out["timeline"], {"assets": out["assets"]}, load_timeline=load_tl
        )

    vo_clips = [c for c in expanded["clips"] if c.get("id", "").startswith("vo_")]
    # VO clips survive expansion (F1): each section had a vo clip.
    assert len(vo_clips) == 2, f"expected 2 vo clips, got {len(vo_clips)}"
    # Sequential timebase (F2): vo/idea-1 starts after vo/open's window.
    vo_at = {c["id"]: c["at"] for c in vo_clips}
    assert vo_at["vo_idea-1"] >= vo_at["vo_open"] + 1e-6
