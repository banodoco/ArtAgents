"""Canonical 26-section text-binding materialization checks."""

from __future__ import annotations

from pathlib import Path

from scripts.proofs.astrid_intro_text_bindings import run

REPO = Path(__file__).resolve().parents[2]
SOURCE_REPO = REPO.parents[2]


def test_text_bindings_are_derived_from_the_canonical_fixture(tmp_path: Path) -> None:
    result = run(["--source-repo", str(SOURCE_REPO), "--out", str(tmp_path / "bindings.json")])
    section_count = len(result["shots"])
    assert result["counts"]["sections"] == section_count
    assert result["counts"]["text_bindings"] == len(result["text_bindings"])
    by_kind = {
        kind: sum(binding["kind"] == kind for binding in result["text_bindings"])
        for kind in result["counts"]["text_bindings_by_kind"]
    }
    assert result["counts"]["text_bindings_by_kind"] == by_kind
    assert by_kind["voiceover_script"] == section_count
    assert by_kind["transcript"] == section_count
    assert {binding["slot"] for binding in result["text_bindings"] if binding["kind"] == "prompt"} >= {
        "canonical", "regen-glitch"
    }


def test_materialization_is_deterministic(tmp_path: Path) -> None:
    first = run(["--source-repo", str(SOURCE_REPO), "--out", str(tmp_path / "first.json")])
    second = run(["--source-repo", str(SOURCE_REPO), "--out", str(tmp_path / "second.json")])
    assert first == second
    assert (tmp_path / "first.json").read_bytes() == (tmp_path / "second.json").read_bytes()
