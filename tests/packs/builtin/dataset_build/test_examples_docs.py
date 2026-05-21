from __future__ import annotations

from pathlib import Path

from astrid.packs.builtin.dataset_build.config import load_dataset_config


ROOT = Path(__file__).resolve().parents[4]
EXAMPLE_CONFIG = ROOT / "examples" / "configs" / "dataset" / "seinfeld-dataset.yaml"
MIGRATION_DOC = ROOT / "docs" / "builtin-dataset-build.md"
BUILTIN_PACKAGE = ROOT / "astrid" / "packs" / "builtin" / "dataset_build"


def test_seinfeld_example_is_strict_generic_dataset_config() -> None:
    parsed = load_dataset_config(EXAMPLE_CONFIG)

    assert parsed.data["media_type"] == "video"
    assert parsed.data["manifest"]["adapter"] == "ai-toolkit-ltx"
    assert parsed.data["extensions"]["bucket_judge"]["enabled"] is True
    assert parsed.data["caption"]["provider"] == "visual_understand"
    assert "apartment_group_dialogue" in parsed.data["buckets"]


def test_migration_docs_explain_m1_scope_and_no_compatibility_shim() -> None:
    text = MIGRATION_DOC.read_text(encoding="utf-8")

    assert "M1 reproduces the prototype's generic VLM bucket-judge and caption flow" in text
    assert "does not implement the M2b top-up loop" in text
    assert "no Seinfeld compatibility shim" in text
    assert "examples/configs/dataset/seinfeld-dataset.yaml" in text


def test_builtin_dataset_build_code_has_no_seinfeld_literals() -> None:
    matches: list[Path] = []
    for path in BUILTIN_PACKAGE.rglob("*"):
        if "schemas" in path.parts:
            continue
        if path.is_file() and path.suffix in {".py", ".js", ".html", ".css", ".md", ".yaml", ".json"}:
            if "seinfeld" in path.read_text(encoding="utf-8").lower():
                matches.append(path.relative_to(ROOT))

    assert matches == []
