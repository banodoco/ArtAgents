from __future__ import annotations

import json
from pathlib import Path

from astrid.packs.builtin.orchestrators.dataset_build.config import load_dataset_config


ROOT = Path(__file__).resolve().parents[4]
EXAMPLE_CONFIG = ROOT / "examples" / "configs" / "dataset" / "seinfeld-dataset.yaml"
ALWAYS_SUNNY_CONFIG = ROOT / "examples" / "configs" / "dataset" / "always-sunny-dataset.yaml"
MIGRATION_DOC = ROOT / "docs" / "builtin-dataset-build.md"
TRAINING_WORKFLOW_DOC = ROOT / "docs" / "examples" / "training-workflow.md"
BUILTIN_PACKAGE = ROOT / "astrid" / "packs" / "builtin" / "orchestrators" / "dataset_build"
ORCHESTRATOR = BUILTIN_PACKAGE / "orchestrator.yaml"
SEINFELD_ARCHIVE = ROOT / "docs" / "examples" / "seinfeld"


def test_seinfeld_example_is_strict_generic_dataset_config() -> None:
    parsed = load_dataset_config(EXAMPLE_CONFIG)

    assert parsed.data["media_type"] == "video"
    assert parsed.data["manifest"]["adapter"] == "ai-toolkit-ltx"
    assert parsed.data["extensions"]["bucket_judge"]["enabled"] is True
    assert parsed.data["caption"]["provider"] == "visual_understand"
    assert "apartment_group_dialogue" in parsed.data["buckets"]


def test_always_sunny_example_is_distinct_strict_generic_dataset_config() -> None:
    seinfeld = load_dataset_config(EXAMPLE_CONFIG).data
    always_sunny = load_dataset_config(ALWAYS_SUNNY_CONFIG).data

    assert always_sunny["media_type"] == "video"
    assert always_sunny["manifest"]["adapter"] == "ai-toolkit-ltx"
    assert list(always_sunny["buckets"]) == ["bar_argument_escalation"]
    assert len(always_sunny["buckets"]) == 1
    assert "bar-comedy" in always_sunny["caption"]["prompt_template"]
    assert always_sunny["caption"]["prompt_template"] != seinfeld["caption"]["prompt_template"]
    assert always_sunny["output"]["run_dir"].endswith("runs/always-sunny-dataset")
    assert "REPLACE_WITH_LICENSED_SOURCE" in always_sunny["sources"][0]["config"]["source_urls"][0]
    assert "astrid/packs/seinfeld" not in ALWAYS_SUNNY_CONFIG.read_text(encoding="utf-8")


def test_migration_docs_explain_m1_scope_and_no_compatibility_shim() -> None:
    text = MIGRATION_DOC.read_text(encoding="utf-8")

    assert "M1 reproduces the prototype's generic VLM bucket-judge and caption flow" in text
    assert "does not implement the M2b top-up loop" in text
    assert "no Seinfeld compatibility shim" in text
    assert "examples/configs/dataset/seinfeld-dataset.yaml" in text
    assert "python3 -m astrid orchestrators run builtin.dataset_build --" in text
    assert "python3 -m astrid.packs." + "seinfeld" not in text


def test_training_workflow_doc_uses_canonical_builtin_commands() -> None:
    text = TRAINING_WORKFLOW_DOC.read_text(encoding="utf-8")

    assert "python3 -m astrid orchestrators run builtin.dataset_build --" in text
    assert "python3 -m astrid orchestrators run builtin.training_run --" in text
    assert "python3 -m astrid executors run builtin.script_pipeline --" in text
    assert "review_state.json" in text
    assert "ai-toolkit-ltx.manifest.json" in text
    assert "checkpoints/checkpoint_manifest.json" in text
    assert "registered/registered_lora.json" in text
    assert "runs/seinfeld-dataset" in text
    assert "docs/examples/seinfeld/" in text
    assert "python3 -m astrid.packs." + "seinfeld" not in text


def test_historical_seinfeld_archive_contains_migration_materials() -> None:
    expected = [
        "README.md",
        "TRAINING_PLAN.md",
        "DATASET_QUALITY.md",
        "CAPTIONING.md",
        "RUNPOD_TRAINING_LAUNCHER_BRIEF.md",
        "vocabulary.yaml",
        "vocab_compile.py",
        "schemas/bucket_judge.json",
        "schemas/caption.json",
        "schemas/scene_verify.json",
        "dataset_build/sprint-brief.md",
        "dataset_build/review.schema.json",
        "dataset_build/review.html",
        "lora_train/config_template.yaml",
    ]
    missing = [path for path in expected if not (SEINFELD_ARCHIVE / path).is_file()]
    assert missing == []

    readme = (SEINFELD_ARCHIVE / "README.md").read_text(encoding="utf-8")
    assert "builtin.dataset_build" in readme
    assert "builtin.training_run" in readme
    assert "builtin.script_pipeline" in readme
    assert "compatibility shims" in readme


def test_builtin_dataset_build_code_has_no_seinfeld_literals() -> None:
    matches: list[Path] = []
    for path in BUILTIN_PACKAGE.rglob("*"):
        if "schemas" in path.parts:
            continue
        if path.is_file() and path.suffix in {".py", ".js", ".html", ".css", ".md", ".yaml", ".json"}:
            if "seinfeld" in path.read_text(encoding="utf-8").lower():
                matches.append(path.relative_to(ROOT))

    assert matches == []


def test_dataset_build_orchestrator_metadata_declares_m2b_discovery_outputs() -> None:
    metadata = json.loads(ORCHESTRATOR.read_text(encoding="utf-8"))

    assert "builtin.transcribe" in metadata["child_executors"]
    assert "builtin.visual_understand" in metadata["child_executors"]
    assert "builtin.video_understand" in metadata["child_executors"]
    outputs = {output["name"]: output for output in metadata["outputs"]}
    assert outputs["quality_report.json"]["path_template"] == "{out}/quality_report.json"
