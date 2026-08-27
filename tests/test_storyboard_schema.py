"""Storyboard v1 schema/loader tests (plan v8 batch B1).

The validator must list ALL problems in one pass — every test below asserts
on the complete problem list, never on short-circuit behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.storyboard import (
    StoryboardError,
    load_storyboard,
    validate_storyboard,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MINIMAL = FIXTURES / "storyboard-minimal.json"
ASSETS = FIXTURES / "storyboard-assets"


def _minimal_story() -> dict:
    return json.loads(MINIMAL.read_text(encoding="utf-8"))


def _write_storyboard(tmp_path: Path, story: dict) -> Path:
    """Write story next to a copy of the fixture assets so paths resolve."""
    for asset in ASSETS.iterdir():
        (tmp_path / "storyboard-assets" / asset.name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "storyboard-assets" / asset.name).touch()
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps(story), encoding="utf-8")
    return path


def test_minimal_fixture_is_valid_and_loads() -> None:
    assert validate_storyboard(_minimal_story(), base_dir=FIXTURES) == []
    loaded = load_storyboard(MINIMAL)
    assert isinstance(loaded, dict)
    assert loaded["version"] == 1
    assert [s["id"] for s in loaded["sections"]] == ["open", "idea-1"]


def test_duplicate_section_ids_listed(tmp_path: Path) -> None:
    story = _minimal_story()
    story["sections"][1]["id"] = "open"
    problems = validate_storyboard(story, base_dir=FIXTURES)
    assert len(problems) == 1
    assert "duplicate section id" in problems[0]
    with pytest.raises(StoryboardError) as exc_info:
        load_storyboard(_write_storyboard(tmp_path, story))
    assert any("duplicate section id" in p for p in exc_info.value.problems)


def test_nav_active_outside_zero_one_listed() -> None:
    story = _minimal_story()
    story["sections"][0]["nav"]["active"] = 2
    problems = validate_storyboard(story, base_dir=FIXTURES)
    assert len(problems) == 1
    assert "nav.active must be 0 or 1" in problems[0]
    assert "sections[open]" in problems[0]


@pytest.mark.parametrize("bad_index", [-1, 2, 99])
def test_active_index_out_of_range_listed(bad_index: int) -> None:
    story = _minimal_story()
    story["sections"][0]["image"]["active_index"] = bad_index
    problems = validate_storyboard(story, base_dir=FIXTURES)
    assert len(problems) == 1
    assert "image.active_index" in problems[0]


def test_every_broken_image_block_listed_in_one_pass() -> None:
    story = _minimal_story()
    story["sections"][0]["image"]["variants"] = []
    story["sections"][1]["image"]["active_index"] = 5
    problems = validate_storyboard(story, base_dir=FIXTURES)
    assert len(problems) == 2
    assert any("sections[open]" in p and "image.variants must be a non-empty list" in p for p in problems)
    assert any("sections[idea-1]" in p and "image.active_index" in p for p in problems)


@pytest.mark.parametrize("field", ["prompt", "alt_render_path"])
def test_gen_variant_missing_required_field_listed(field: str) -> None:
    story = _minimal_story()
    gen_variant = story["sections"][1]["image"]["variants"][1]
    assert gen_variant["source"] == "gen"
    del gen_variant[field]
    problems = validate_storyboard(story, base_dir=FIXTURES)
    assert len(problems) == 1
    assert field in problems[0]
    assert "gen variant" in problems[0]


def test_gen_variant_gen_kernel_run_id_satisfies_alt_render_path() -> None:
    story = _minimal_story()
    gen_variant = story["sections"][1]["image"]["variants"][1]
    del gen_variant["alt_render_path"]
    gen_variant["gen_kernel_run_id"] = "run_01JZZZZZZZZZZZZZZZZZZZZZZZZ"
    assert validate_storyboard(story, base_dir=FIXTURES) == []


def test_gen_variant_prompt_still_required_with_kernel_run_id() -> None:
    story = _minimal_story()
    gen_variant = story["sections"][1]["image"]["variants"][1]
    del gen_variant["alt_render_path"]
    gen_variant["gen_kernel_run_id"] = "run_01JZZZZZZZZZZZZZZZZZZZZZZZZ"
    del gen_variant["prompt"]
    story["sections"][1]["image"]["active_index"] = 0
    problems = validate_storyboard(story, base_dir=FIXTURES)
    assert len(problems) == 1
    assert "prompt" in problems[0]


def test_missing_asset_path_relative_to_storyboard_dir_listed() -> None:
    story = _minimal_story()
    story["sections"][0]["image"]["variants"][0]["path"] = "storyboard-assets/nope.png"
    problems = validate_storyboard(story, base_dir=FIXTURES)
    assert len(problems) == 1
    assert "asset path not found" in problems[0]
    assert "storyboard-assets/nope.png" in problems[0]


def test_missing_vo_audio_asset_listed() -> None:
    story = _minimal_story()
    story["sections"][1]["vo"]["audio"]["asset"] = "storyboard-assets/nope.wav"
    problems = validate_storyboard(story, base_dir=FIXTURES)
    assert len(problems) == 1
    assert "vo.audio.asset path not found" in problems[0]


def test_absolute_existing_paths_accepted() -> None:
    story = _minimal_story()
    story["sections"][0]["image"]["variants"][0]["path"] = str(ASSETS / "open.png")
    story["sections"][0]["vo"]["audio"]["asset"] = str(ASSETS / "open.wav")
    assert validate_storyboard(story, base_dir=FIXTURES) == []


def test_load_storyboard_raises_with_all_problems_at_once(tmp_path: Path) -> None:
    story = _minimal_story()
    story["version"] = 2
    story["meta"]["style"] = "neon-cyberpunk"
    story["sections"][0]["image"]["variants"] = []
    del story["sections"][1]["id"]
    path = _write_storyboard(tmp_path, story)
    with pytest.raises(StoryboardError) as exc_info:
        load_storyboard(path)
    problems = exc_info.value.problems
    assert len(problems) == 4
    assert any("version" in p for p in problems)
    assert any("meta.style" in p for p in problems)
    assert any("image.variants" in p for p in problems)
    assert any("id must match" in p for p in problems)
    assert all(p in str(exc_info.value) for p in problems)


def test_load_storyboard_invalid_json_raises(tmp_path: Path) -> None:
    bad = tmp_path / "storyboard-bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(StoryboardError) as exc_info:
        load_storyboard(bad)
    assert "invalid JSON" in exc_info.value.problems[0]


def test_expanduser_paths_resolve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    story = _minimal_story()
    story["sections"][0]["image"]["variants"][0]["path"] = "~/storyboard-assets/open.png"
    (tmp_path / "storyboard-assets").mkdir()
    (tmp_path / "storyboard-assets" / "open.png").touch()
    assert validate_storyboard(story, base_dir=FIXTURES) == []
