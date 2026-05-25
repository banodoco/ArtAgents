"""Built-in training-run defaults."""

from __future__ import annotations

from pathlib import Path

import yaml

from astrid.packs.training.orchestrators.training_run.defaults import AI_TOOLKIT_LTX_DEFAULTS, RUNPOD_LTX_DEFAULTS
from astrid.packs.training.orchestrators.training_run.config import load_training_run_config


ROOT = Path(__file__).resolve().parents[4]
EXAMPLE_CONFIG = ROOT / "examples" / "configs" / "training" / "seinfeld-training.yaml"
ALWAYS_SUNNY_CONFIG = ROOT / "examples" / "configs" / "training" / "always-sunny-training.yaml"


def test_seinfeld_training_example_uses_builtin_defaults_and_archived_vocabulary_path() -> None:
    payload = yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    compute = payload["compute"]
    lora = payload["lora_config"]

    assert payload["vocabulary_path"] == "../../../docs/examples/seinfeld/vocabulary.yaml"
    assert "astrid/packs/seinfeld" not in payload["vocabulary_path"]
    assert compute["image"] == RUNPOD_LTX_DEFAULTS["image"]
    assert compute["ports"] == RUNPOD_LTX_DEFAULTS["ports"]
    assert compute["storage_name"] == "seinfeld-dataset"
    assert compute["gpu_type"] == RUNPOD_LTX_DEFAULTS["gpu_type"]
    assert payload["base_model"] == AI_TOOLKIT_LTX_DEFAULTS["base_model_default"]
    assert lora["lora_id"] == "seinfeld-scene-v1"
    assert lora["trigger_word"] == "seinfeld scene"
    assert lora["rank"] == AI_TOOLKIT_LTX_DEFAULTS["rank"]
    assert lora["steps"] == AI_TOOLKIT_LTX_DEFAULTS["steps_default"]


def test_always_sunny_training_example_is_distinct_and_dry_run_safe() -> None:
    payload = yaml.safe_load(ALWAYS_SUNNY_CONFIG.read_text(encoding="utf-8"))
    parsed = load_training_run_config(ALWAYS_SUNNY_CONFIG)
    text = ALWAYS_SUNNY_CONFIG.read_text(encoding="utf-8")

    assert parsed.data["trainer_id"] == "ai-toolkit-ltx"
    assert parsed.data["output"]["run_dir"].endswith("runs/always-sunny-lora")
    assert "astrid/packs/seinfeld" not in text
    assert "OPENAI_API_KEY" not in text
    assert "RUNPOD_API_KEY" in payload["secrets"]["required_env"]
    assert "HF_TOKEN" in payload["secrets"]["required_env"]
    assert payload["compute"]["storage_name"] == "always-sunny-dataset"
    assert payload["lora_config"]["lora_id"] == "always-sunny-chaos-v1"
    assert payload["lora_config"]["trigger_word"] == "paddy chaos scene"
    assert payload["lora_config"]["seed"] != yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))["lora_config"]["seed"]
    assert payload["checkpoint"]["sample_prompts"] != yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))["checkpoint"]["sample_prompts"]
