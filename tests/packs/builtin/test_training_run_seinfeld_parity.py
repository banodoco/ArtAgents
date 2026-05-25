"""Seinfeld-by-config parity coverage for training.training_run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from astrid.packs.training.orchestrators.dataset_build.interfaces import ArtifactPullResult, CostEstimate, ProviderCapabilities, RemoteExecResult, RunPodHandle
from astrid.packs.training.orchestrators.training_run.defaults import AI_TOOLKIT_LTX_DEFAULTS, RUNPOD_LTX_DEFAULTS
import astrid.packs.training.orchestrators.training_run.run as training_run_module
from astrid.packs.training.orchestrators.training_run.run import main as training_run_main

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_CONFIG = REPO_ROOT / "examples" / "configs" / "training" / "seinfeld-training.yaml"


def _clip_fixture(root: Path) -> tuple[Path, Path]:
    clips = root / "clips"
    clips.mkdir()
    clip = clips / "clip_001.mp4"
    caption = clips / "clip_001.caption.json"
    clip.write_bytes(b"mp4")
    caption.write_text(json.dumps({"text": "seinfeld scene, caption"}) + "\n", encoding="utf-8")
    return clip, caption


def _flat_manifest(path: Path, clip: Path, caption: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "clips": [
                    {
                        "clip_id": "clip_001",
                        "clip_file": str(clip),
                        "path": str(clip),
                        "caption_file": str(caption),
                        "bucket": "sitcom",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _example_payload() -> dict[str, Any]:
    return yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))


def _write_temp_config(tmp_path: Path, manifest: Path, run_dir: Path) -> Path:
    payload = _example_payload()
    payload["manifest_path"] = str(manifest)
    payload["output"]["run_dir"] = str(run_dir)
    path = tmp_path / "seinfeld-training.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


class SeinfeldMockCompute:
    backend_id = "runpod"

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.provision_calls: list[dict[str, Any]] = []
        self.teardown_calls: list[RunPodHandle] = []

    def provision(self, config: dict[str, Any]) -> RunPodHandle:
        self.provision_calls.append(dict(config))
        handle_path = self.tmp_path / "pod_handle.json"
        handle_path.write_text(json.dumps({"pod_id": "pod-seinfeld"}) + "\n", encoding="utf-8")
        return RunPodHandle("pod-seinfeld", RUNPOD_LTX_DEFAULTS["gpu_type"], metadata={"handle_path": str(handle_path)})

    def teardown(self, handle: RunPodHandle) -> None:
        self.teardown_calls.append(handle)

    def estimate_cost(self, config: dict[str, Any]) -> CostEstimate:
        return CostEstimate(gpu_hours=12, estimated_cost_usd=9.48, backend="runpod", details={"source": "test"})


class SeinfeldMockRemote:
    backend_id = "runpod"
    capabilities = ProviderCapabilities(
        backend="runpod",
        supports_exec=True,
        supports_artifact_pull=True,
        supports_artifact_push=True,
        supports_cost_estimate=True,
    )

    def __init__(self) -> None:
        self.exec_calls: list[dict[str, Any]] = []
        self.pull_calls: list[dict[str, Any]] = []

    def exec(self, handle: RunPodHandle, command: list[str], config: dict[str, Any]) -> RemoteExecResult:
        self.exec_calls.append({"handle": handle, "command": list(command), "config": dict(config)})
        return RemoteExecResult(exit_code=0, stdout="ok\n", stderr="", command=list(command))

    def pull_artifacts(self, handle: RunPodHandle, remote_paths: list[str], local_dir: Path, config: dict[str, Any]) -> ArtifactPullResult:
        self.pull_calls.append({"handle": handle, "remote_paths": list(remote_paths), "local_dir": local_dir, "config": dict(config)})
        local_dir.mkdir(parents=True, exist_ok=True)
        local_paths: list[Path] = []
        for remote_path in remote_paths:
            local_path = local_dir / Path(remote_path).name
            local_path.write_bytes(b"safetensors" if local_path.suffix == ".safetensors" else b"mp4")
            local_paths.append(local_path)
        return ArtifactPullResult(local_paths=local_paths, remote_paths=list(remote_paths), metadata={})


def _install_mock_backends(monkeypatch: pytest.MonkeyPatch, compute: SeinfeldMockCompute, remote: SeinfeldMockRemote) -> None:
    monkeypatch.setattr(training_run_module, "get_compute_backend", lambda backend_id: compute)
    monkeypatch.setattr(training_run_module, "get_remote_execution_backend", lambda backend_id: remote)


def test_seinfeld_example_config_preserves_legacy_defaults_without_wrapper() -> None:
    payload = _example_payload()
    compute = payload["compute"]
    lora = payload["lora_config"]

    assert compute["image"] == RUNPOD_LTX_DEFAULTS["image"]
    assert compute["ports"] == RUNPOD_LTX_DEFAULTS["ports"]
    assert compute["storage_name"] == "seinfeld-dataset"
    assert compute["gpu_type"] == RUNPOD_LTX_DEFAULTS["gpu_type"]
    assert compute["container_disk_gb"] == RUNPOD_LTX_DEFAULTS["container_disk_gb"]
    assert compute["max_runtime_seconds"] == RUNPOD_LTX_DEFAULTS["max_runtime_seconds"]
    assert payload["base_model"] == AI_TOOLKIT_LTX_DEFAULTS["base_model_default"]
    assert lora["lora_id"] == "seinfeld-scene-v1"
    assert lora["trigger_word"] == "seinfeld scene"
    assert lora["rank"] == AI_TOOLKIT_LTX_DEFAULTS["rank"]
    assert lora["alpha"] == AI_TOOLKIT_LTX_DEFAULTS["rank"]
    assert lora["steps"] == AI_TOOLKIT_LTX_DEFAULTS["steps_default"]
    assert lora["learning_rate"] == AI_TOOLKIT_LTX_DEFAULTS["learning_rate"]
    assert lora["seed"] == AI_TOOLKIT_LTX_DEFAULTS["seed_default"]
    assert lora["width"] == AI_TOOLKIT_LTX_DEFAULTS["resolution"]
    assert lora["height"] == 768
    assert lora["num_frames"] == AI_TOOLKIT_LTX_DEFAULTS["num_frames"]
    assert lora["fps"] == AI_TOOLKIT_LTX_DEFAULTS["fps"]
    assert lora["batch_size"] == AI_TOOLKIT_LTX_DEFAULTS["batch_size"]
    assert lora["gradient_accumulation_steps"] == AI_TOOLKIT_LTX_DEFAULTS["gradient_accumulation_steps"]
    assert lora["save_every"] == AI_TOOLKIT_LTX_DEFAULTS["save_every"]
    assert lora["sample_every"] == AI_TOOLKIT_LTX_DEFAULTS["sample_every"]
    assert not (REPO_ROOT / "astrid" / "packs" / "seinfeld" / "training_run").exists()
    assert not (REPO_ROOT / "astrid" / "packs" / "seinfeld" / "builtin_training_run").exists()


def test_seinfeld_config_dry_run_emits_equivalent_ai_toolkit_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    compute = SeinfeldMockCompute(tmp_path)
    remote = SeinfeldMockRemote()
    _install_mock_backends(monkeypatch, compute, remote)
    clip, caption = _clip_fixture(tmp_path)
    manifest = _flat_manifest(tmp_path / "ai-toolkit-ltx.manifest.json", clip, caption)
    run_dir = tmp_path / "seinfeld-lora"
    config_path = _write_temp_config(tmp_path, manifest, run_dir)

    rc = training_run_main(["--config", str(config_path), "--dry-run", "--json"])

    assert rc == 0
    assert compute.provision_calls == []
    assert compute.teardown_calls == []
    assert remote.exec_calls == []
    assert remote.pull_calls == []
    state = json.loads((run_dir / "last_run.json").read_text(encoding="utf-8"))
    trainer_config_path = Path(state["artifacts"]["trainer_config_path"])
    generated = yaml.safe_load(trainer_config_path.read_text(encoding="utf-8"))
    process = generated["config"]["process"][0]
    payload = _example_payload()

    assert process["trigger_word"] == "seinfeld scene"
    assert process["network"] == {
        "type": "lora",
        "linear": AI_TOOLKIT_LTX_DEFAULTS["rank"],
        "linear_alpha": AI_TOOLKIT_LTX_DEFAULTS["rank"],
    }
    assert process["save"]["save_every"] == AI_TOOLKIT_LTX_DEFAULTS["save_every"]
    assert process["datasets"][0]["folder_path"] == "/workspace/dataset"
    assert process["datasets"][0]["resolution"] == [AI_TOOLKIT_LTX_DEFAULTS["resolution"], 768]
    assert process["datasets"][0]["num_frames"] == AI_TOOLKIT_LTX_DEFAULTS["num_frames"]
    assert process["datasets"][0]["fps"] == AI_TOOLKIT_LTX_DEFAULTS["fps"]
    assert process["train"]["batch_size"] == AI_TOOLKIT_LTX_DEFAULTS["batch_size"]
    assert process["train"]["steps"] == AI_TOOLKIT_LTX_DEFAULTS["steps_default"]
    assert process["train"]["gradient_accumulation_steps"] == AI_TOOLKIT_LTX_DEFAULTS["gradient_accumulation_steps"]
    assert process["train"]["lr"] == AI_TOOLKIT_LTX_DEFAULTS["learning_rate"]
    assert process["train"]["seed"] == AI_TOOLKIT_LTX_DEFAULTS["seed_default"]
    assert process["model"]["name_or_path"] == AI_TOOLKIT_LTX_DEFAULTS["base_model_default"]
    assert process["model"]["is_ltx"] is True
    assert process["sample"]["sample_every"] == AI_TOOLKIT_LTX_DEFAULTS["sample_every"]
    assert process["sample"]["width"] == AI_TOOLKIT_LTX_DEFAULTS["resolution"]
    assert process["sample"]["height"] == 768
    assert process["sample"]["num_frames"] == AI_TOOLKIT_LTX_DEFAULTS["num_frames"]
    assert process["sample"]["fps"] == AI_TOOLKIT_LTX_DEFAULTS["fps"]
    assert process["sample"]["prompts"] == payload["checkpoint"]["sample_prompts"]
    assert generated["meta"]["name"] == "seinfeld-scene-v1"
    assert generated["meta"]["review_labels"] == payload["checkpoint"]["review_labels"]
    assert json.loads((run_dir / "planned_cost.json").read_text(encoding="utf-8"))["within_budget"] is True


def test_seinfeld_config_live_pause_and_resume_registration_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    compute = SeinfeldMockCompute(tmp_path)
    remote = SeinfeldMockRemote()
    _install_mock_backends(monkeypatch, compute, remote)
    monkeypatch.setenv("RUNPOD_API_KEY", "present")
    monkeypatch.setenv("HF_TOKEN", "present")
    clip, caption = _clip_fixture(tmp_path)
    manifest = _flat_manifest(tmp_path / "ai-toolkit-ltx.manifest.json", clip, caption)
    run_dir = tmp_path / "seinfeld-live"
    config_path = _write_temp_config(tmp_path, manifest, run_dir)

    live_rc = training_run_main(["--config", str(config_path), "--confirm-spend", "--json"])

    assert live_rc == 0
    paused = json.loads((run_dir / "last_run.json").read_text(encoding="utf-8"))
    assert paused["status"] == "PAUSED"
    assert paused["phase"] == "review_ready"
    assert paused["review"]["human_gate"] == "checkpoint_review"
    assert "resume --out" in paused["review"]["resume_command"]
    assert paused["pod"]["id"] == "pod-seinfeld"
    assert paused["recoverability"]["teardown_guard"]["required"] is True
    checkpoint_manifest = json.loads(Path(paused["artifacts"]["checkpoint_manifest_path"]).read_text(encoding="utf-8"))
    assert checkpoint_manifest["checkpoints"][0]["remote_path"] == "/workspace/output/seinfeld-scene-v1-final.safetensors"

    register_rc = training_run_main(["resume", "--out", str(run_dir), "--pick", "final", "--notes", "parity pick", "--json"])

    assert register_rc == 0
    registered = json.loads((run_dir / "last_run.json").read_text(encoding="utf-8"))
    assert registered["status"] == "REGISTERED"
    assert registered["phase"] == "completed"
    assert registered["registration"]["chosen_checkpoint"]["remote_path"] == "/workspace/output/seinfeld-scene-v1-final.safetensors"
    assert registered["registration"]["metadata"]["lora_id"] == "seinfeld-scene-v1"
    assert registered["registration"]["notes"] == "parity pick"
    assert Path(registered["registration"]["registered_lora_path"]).is_file()
    metadata = json.loads(Path(registered["registration"]["metadata_path"]).read_text(encoding="utf-8"))
    assert metadata["lora_id"] == "seinfeld-scene-v1"
    assert registered["teardown"] == {"skipped": False, "completed": True, "pod_id": "pod-seinfeld"}
    assert compute.teardown_calls and compute.teardown_calls[-1].pod_id == "pod-seinfeld"
