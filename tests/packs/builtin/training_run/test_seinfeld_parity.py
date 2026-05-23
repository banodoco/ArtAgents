"""Seinfeld example parity through generic training_run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import yaml

from astrid.packs.builtin.orchestrators.training_run.run import main as training_run_main

REPO_ROOT = Path(__file__).resolve().parents[4]
EXAMPLE_CONFIG = REPO_ROOT / "examples" / "configs" / "training" / "seinfeld-training.yaml"


def test_seinfeld_example_dry_run_uses_config_not_generic_literals(
    tmp_path: Path,
    backend_factory: Callable[..., tuple[object, object, list[str]]],
    clip_pair: Callable[[Path, str], tuple[Path, Path]],
    flat_manifest: Callable[[Path, Path, Path], Path],
) -> None:
    _compute, remote, events = backend_factory()
    clip, caption = clip_pair(tmp_path / "dataset")
    manifest = flat_manifest(tmp_path / "ai-toolkit-ltx.manifest.json", clip, caption)
    run_dir = tmp_path / "seinfeld-run"
    payload = yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    payload["manifest_path"] = str(manifest)
    payload["output"]["run_dir"] = str(run_dir)
    config_path = tmp_path / "seinfeld-training.yaml"
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    rc = training_run_main(["--config", str(config_path), "--dry-run", "--json"])

    assert rc == 0
    assert events == []
    assert remote.exec_calls == []
    assert remote.pull_calls == []
    state = json.loads((run_dir / "last_run.json").read_text(encoding="utf-8"))
    generated = yaml.safe_load(Path(state["artifacts"]["trainer_config_path"]).read_text(encoding="utf-8"))
    process = generated["config"]["process"][0]
    assert generated["config"]["name"] == "seinfeld-scene-v1"
    assert process["trigger_word"] == "seinfeld scene"
    assert process["network"]["linear"] == 32
    assert process["train"]["steps"] == 2000
    assert process["sample"]["prompts"] == payload["checkpoint"]["sample_prompts"]
