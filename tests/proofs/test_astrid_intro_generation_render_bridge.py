"""Canonical source/artifact preparation checks for the Stage1 bridge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.proofs.astrid_intro_generation_render_bridge import run

REPO = Path(__file__).resolve().parents[2]
SOURCE_REPO = REPO.parents[2]


def test_canonical_bridge_derives_every_count_and_artifact(tmp_path: Path) -> None:
    out = tmp_path / "fixture.json"
    fixture = run(["--source-repo", str(SOURCE_REPO), "--out", str(out)])
    sections = fixture["sections"]
    assert fixture["counts"]["sections"] == len(sections)
    assert fixture["counts"]["shots"] == len(sections)
    assert fixture["counts"]["slides"] == len(fixture["slides"])
    assert [slide["slug"] for slide in fixture["slides"]] == [
        section["section_id"] for section in sections
    ]
    assert fixture["counts"]["variants"] == sum(
        len(section["image"]["variants"])
        for section in json.loads((REPO / "storyboards/astrid-intro.storyboard.json").read_text())["sections"]
    )
    assert fixture["counts"]["artifacts"] == len(fixture["artifacts"])
    assert len({section["shot_id"] for section in sections}) == len(sections)
    assert all(len(artifact["sha256"]) == 64 and artifact["size"] > 0 for artifact in fixture["artifacts"])
    assert fixture["timeline"]["tracks"] == {
        "brand": 1,
        "captions": len(sections),
        "broll": len(sections),
        "a1": len(sections),
    }
    assert fixture["timeline"]["clips"] == 3 * len(sections) + 1
    assert fixture["timeline"]["assets"] == 2 * len(sections)
    assert fixture["timeline"]["duration"] == fixture["duration"]
    assert out.is_file()


def test_canonical_pair_rejects_plan_drift(tmp_path: Path) -> None:
    plan = json.loads((REPO / "storyboards/astrid-intro.plan.json").read_text())
    plan["segments"][0]["text"] = "drift"
    bad_plan = tmp_path / "plan.json"
    bad_plan.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="narration"):
        run([
            "--source-repo", str(SOURCE_REPO),
            "--plan", str(bad_plan),
            "--out", str(tmp_path / "fixture.json"),
        ])


def test_fixture_is_runtime_neutral() -> None:
    source = (REPO / "scripts/proofs/astrid_intro_canonical_fixture.py").read_text()
    assert "AstridClient.open" not in source
    assert "sqlite" not in source.lower()
    assert "endpoint=" not in source
