"""Config, manifest, and trainer adapter success-criteria tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest
import yaml

from astrid.packs.builtin.training_run.config import (
    TrainingRunSecretError,
    TrainingRunSpendConfirmationError,
    load_training_run_config,
    preflight_secrets,
    preflight_training_run,
)
from astrid.packs.builtin.training_run.manifest_input import TrainingManifestError, normalize_ai_toolkit_manifest
from astrid.packs.builtin.training_run.trainer_adapters import get_trainer_adapter

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_schema_path_budget_spend_and_secrets_behavior(
    tmp_path: Path,
    clip_pair: Callable[[Path, str], tuple[Path, Path]],
    flat_manifest: Callable[[Path, Path, Path], Path],
    training_config: Callable[[Path, Path, Path, dict | None], Path],
) -> None:
    clip, caption = clip_pair(tmp_path / "dataset")
    manifest = flat_manifest(tmp_path / "dataset" / "manifest.json", clip, caption)
    config_path = training_config(tmp_path / "config.json", manifest, tmp_path / "run")

    parsed = load_training_run_config(config_path)
    assert parsed.manifest_path == manifest.resolve()
    assert parsed.run_dir == (tmp_path / "run").resolve()

    dry = preflight_secrets(parsed.data, dry_run=True, env={})
    assert dry.missing_env == ("RUNPOD_API_KEY",)
    with pytest.raises(TrainingRunSecretError):
        preflight_training_run(parsed.data, dry_run=False, spend_confirmed=True, env={})
    with pytest.raises(TrainingRunSpendConfirmationError):
        preflight_training_run(parsed.data, dry_run=False, spend_confirmed=False, env={"RUNPOD_API_KEY": "present"})


def test_manifest_normalization_accepts_valid_input_and_fails_on_missing_files(
    tmp_path: Path,
    clip_pair: Callable[[Path, str], tuple[Path, Path]],
    flat_manifest: Callable[[Path, Path, Path], Path],
) -> None:
    clip, caption = clip_pair(tmp_path / "dataset")
    manifest = flat_manifest(tmp_path / "dataset" / "ai-toolkit-ltx.manifest.json", clip, caption)

    normalized = normalize_ai_toolkit_manifest(manifest, tmp_path / "run")
    payload = json.loads(normalized.normalized_manifest_path.read_text(encoding="utf-8"))
    assert normalized.source_format == "ai-toolkit-ltx-flat"
    assert payload["clips"][0]["clip_id"] == "clip_001"

    missing_manifest = tmp_path / "missing.json"
    missing_manifest.write_text(
        json.dumps({"clips": [{"clip_id": "clip_002", "clip_file": str(tmp_path / "missing.mp4"), "caption_file": str(caption)}]}),
        encoding="utf-8",
    )
    with pytest.raises(TrainingManifestError, match="clip_file missing"):
        normalize_ai_toolkit_manifest(missing_manifest, tmp_path / "bad-run")

    missing_caption_manifest = tmp_path / "missing-caption.json"
    missing_caption_manifest.write_text(
        json.dumps({"clips": [{"clip_id": "clip_003", "clip_file": str(clip)}]}),
        encoding="utf-8",
    )
    caption.unlink()
    with pytest.raises(TrainingManifestError, match="inferred caption sidecar missing"):
        normalize_ai_toolkit_manifest(missing_caption_manifest, tmp_path / "bad-caption-run")


def test_trainer_adapter_generates_config_and_generic_python_omits_seinfeld_literals(
    tmp_path: Path,
    clip_pair: Callable[[Path, str], tuple[Path, Path]],
    flat_manifest: Callable[[Path, Path, Path], Path],
    training_config: Callable[[Path, Path, Path, dict | None], Path],
) -> None:
    clip, caption = clip_pair(tmp_path / "dataset")
    manifest = flat_manifest(tmp_path / "dataset" / "manifest.json", clip, caption)
    config_path = training_config(tmp_path / "config.json", manifest, tmp_path / "run")
    parsed = load_training_run_config(config_path)
    normalized = normalize_ai_toolkit_manifest(parsed.manifest_path, parsed.run_dir)
    adapter = get_trainer_adapter(parsed.data["trainer_id"])
    trainer_config = dict(parsed.data)
    trainer_config["config_path"] = str(parsed.run_dir / "trainer" / "ai-toolkit-ltx" / "config.yaml")

    config_yaml = adapter.build_config(normalized.normalized_manifest_path, trainer_config)
    generated = yaml.safe_load(config_yaml.read_text(encoding="utf-8"))
    process = generated["config"]["process"][0]

    assert process["trigger_word"] == "demo style"
    assert process["network"]["linear"] == 8
    assert process["datasets"][0]["resolution"] == [512, 512]
    assert process["train"]["steps"] == 100
    assert process["sample"]["prompts"] == ["demo style, test sample"]

    generic_py = REPO_ROOT / "astrid" / "packs" / "builtin" / "training_run"
    for path in generic_py.rglob("*.py"):
        assert "seinfeld" not in path.read_text(encoding="utf-8").lower(), path
