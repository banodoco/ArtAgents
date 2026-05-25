"""Training-run trainer adapter registry and ai-toolkit LTX adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from astrid.packs.training.orchestrators.training_run.trainer_adapters import (
    ADAPTERS,
    TrainerAdapterRegistryError,
    get_trainer_adapter,
)
from astrid.packs.training.orchestrators.training_run.trainer_adapters.ai_toolkit_ltx import AiToolkitLtxTrainerAdapter


def _manifest(path: Path) -> Path:
    clip = path.parent / "clip-a.mp4"
    caption = path.parent / "clip-a.caption.json"
    clip.write_bytes(b"mp4")
    caption.write_text(json.dumps({"text": "caption"}) + "\n", encoding="utf-8")
    path.write_text(
        json.dumps(
            {
                "clips": [
                    {
                        "clip_id": "clip-a",
                        "clip_file": str(clip),
                        "caption_file": str(caption),
                    }
                ]
            }
        ) + "\n",
        encoding="utf-8",
    )
    return path


def _trainer_config(path: Path) -> dict:
    return {
        "config_path": str(path),
        "base_model": "ExampleOrg/LTX-base.safetensors",
        "dataset_dir": "/workspace/dataset",
        "output_dir": "/workspace/output",
        "lora_config": {
            "lora_id": "city-night-v1",
            "trigger_word": "city night style",
            "prompt_text": "A rain-lit city night scene with reflective pavement.",
            "rank": 12,
            "alpha": 8,
            "steps": 321,
            "learning_rate": 0.00003,
            "seed": 77,
            "width": 640,
            "height": 384,
            "num_frames": 97,
            "fps": 24,
            "batch_size": 2,
            "gradient_accumulation_steps": 3,
            "save_every": 111,
            "sample_every": 222,
        },
        "checkpoint": {
            "sample_prompts": [
                "city night style, reflective street establishing shot",
                "city night style, close character portrait under neon",
            ],
            "review_labels": ["style match", "motion", "artifacting"],
        },
        "output": {"run_dir": str(path.parent)},
    }


def test_trainer_adapter_registry_resolves_ids_and_lists_available_on_invalid_id() -> None:
    assert ADAPTERS == {"ai-toolkit-ltx": AiToolkitLtxTrainerAdapter}
    assert isinstance(get_trainer_adapter("ai-toolkit-ltx"), AiToolkitLtxTrainerAdapter)
    with pytest.raises(TrainerAdapterRegistryError, match="available: ai-toolkit-ltx"):
        get_trainer_adapter("other")


def test_ai_toolkit_adapter_validates_manifest_and_reports_errors(tmp_path: Path) -> None:
    adapter = get_trainer_adapter("ai-toolkit-ltx")
    manifest = _manifest(tmp_path / "manifest.json")

    assert adapter.validate_manifest(manifest) == []

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"clips": [{"clip_id": "x", "unexpected": "nope"}]}) + "\n", encoding="utf-8")
    assert adapter.validate_manifest(bad)


def test_ai_toolkit_adapter_builds_config_from_supplied_values_only(tmp_path: Path) -> None:
    adapter = get_trainer_adapter("ai-toolkit-ltx")
    manifest = _manifest(tmp_path / "manifest.json")
    out_path = tmp_path / "trainer" / "config.yaml"
    config = _trainer_config(out_path)

    result = adapter.build_config(manifest, config)
    payload = yaml.safe_load(result.read_text(encoding="utf-8"))
    process = payload["config"]["process"][0]

    assert result == out_path
    assert payload["config"]["name"] == "city-night-v1"
    assert process["trigger_word"] == "city night style"
    assert process["network"]["linear"] == 12
    assert process["network"]["linear_alpha"] == 8
    assert process["train"]["steps"] == 321
    assert process["train"]["lr"] == 0.00003
    assert process["train"]["batch_size"] == 2
    assert process["train"]["gradient_accumulation_steps"] == 3
    assert process["datasets"][0]["resolution"] == [640, 384]
    assert process["datasets"][0]["num_frames"] == 97
    assert process["sample"]["prompts"] == config["checkpoint"]["sample_prompts"]
    assert payload["meta"]["prompt_text"] == config["lora_config"]["prompt_text"]
    assert payload["meta"]["review_labels"] == config["checkpoint"]["review_labels"]
    assert "seinfeld" not in result.read_text(encoding="utf-8").lower()


def test_ai_toolkit_adapter_requires_config_owned_prompt_and_review_fields(tmp_path: Path) -> None:
    adapter = get_trainer_adapter("ai-toolkit-ltx")
    manifest = _manifest(tmp_path / "manifest.json")
    config = _trainer_config(tmp_path / "config.yaml")
    config["lora_config"].pop("trigger_word")

    with pytest.raises(ValueError, match="lora_config.trigger_word"):
        adapter.build_config(manifest, config)


def test_generic_training_run_adapter_code_does_not_embed_seinfeld_defaults() -> None:
    package_root = Path("astrid/packs/training/orchestrators/training_run")
    checked = [
        path
        for path in package_root.rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    assert checked
    for path in checked:
        assert "seinfeld" not in path.read_text(encoding="utf-8").lower(), str(path)
