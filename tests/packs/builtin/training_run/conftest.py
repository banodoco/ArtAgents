"""Shared fixtures for generic training-run milestone tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from astrid.packs.builtin.dataset_build.interfaces import ArtifactPullResult, CostEstimate, ProviderCapabilities, RemoteExecResult, RunPodHandle
import astrid.packs.builtin.training_run.run as training_run_module


@pytest.fixture
def clip_pair() -> Callable[[Path, str], tuple[Path, Path]]:
    def write(root: Path, clip_id: str = "clip_001") -> tuple[Path, Path]:
        root.mkdir(parents=True, exist_ok=True)
        clip = root / f"{clip_id}.mp4"
        caption = root / f"{clip_id}.caption.json"
        clip.write_bytes(b"mp4")
        caption.write_text(json.dumps({"text": f"{clip_id} caption"}) + "\n", encoding="utf-8")
        return clip, caption

    return write


@pytest.fixture
def flat_manifest() -> Callable[[Path, Path, Path], Path]:
    def write(path: Path, clip: Path, caption: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "clips": [
                        {
                            "clip_id": clip.stem,
                            "clip_file": str(clip),
                            "path": str(clip),
                            "caption_file": str(caption),
                            "bucket": "training",
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    return write


@pytest.fixture
def training_config() -> Callable[[Path, Path, Path, dict[str, Any] | None], Path]:
    def write(path: Path, manifest: Path, run_dir: Path, extra: dict[str, Any] | None = None) -> Path:
        payload: dict[str, Any] = {
            "schema_version": 1,
            "trainer_id": "ai-toolkit-ltx",
            "manifest_path": str(manifest),
            "compute": {
                "backend": "runpod",
                "max_gpu_hours": 2,
                "max_runpod_spend_usd": 10,
                "require_spend_confirmation": True,
                "gpu_type": "NVIDIA RTX 6000 Ada Generation",
            },
            "secrets": {"required_env": ["RUNPOD_API_KEY"]},
            "base_model": "base.safetensors",
            "lora_config": {
                "lora_id": "demo",
                "trigger_word": "demo style",
                "prompt_text": "A demo training prompt.",
                "rank": 8,
                "alpha": 8,
                "steps": 100,
                "learning_rate": 0.0001,
                "seed": 1,
                "width": 512,
                "height": 512,
                "num_frames": 49,
                "fps": 24,
                "batch_size": 1,
                "gradient_accumulation_steps": 1,
                "save_every": 50,
                "sample_every": 50,
            },
            "checkpoint": {
                "sample_prompts": ["demo style, test sample"],
                "review_labels": ["style"],
            },
            "output": {"run_dir": str(run_dir)},
        }
        if extra:
            payload.update(extra)
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        return path

    return write


class MockCompute:
    backend_id = "runpod"

    def __init__(self, tmp_path: Path, events: list[str], *, include_handle_path: bool = True) -> None:
        self.tmp_path = tmp_path
        self.events = events
        self.include_handle_path = include_handle_path
        self.provision_calls: list[dict[str, Any]] = []
        self.teardown_calls: list[RunPodHandle] = []

    def provision(self, config: dict[str, Any]) -> RunPodHandle:
        self.events.append("provision")
        self.provision_calls.append(dict(config))
        metadata: dict[str, Any] = {}
        if self.include_handle_path:
            handle_path = self.tmp_path / "pod_handle.json"
            handle_path.write_text(json.dumps({"pod_id": "pod-test"}) + "\n", encoding="utf-8")
            metadata["handle_path"] = str(handle_path)
        return RunPodHandle("pod-test", "NVIDIA RTX 6000 Ada Generation", metadata=metadata)

    def teardown(self, handle: RunPodHandle) -> None:
        self.events.append("teardown")
        self.teardown_calls.append(handle)

    def estimate_cost(self, config: dict[str, Any]) -> CostEstimate:
        return CostEstimate(gpu_hours=float(config.get("max_gpu_hours") or 2), estimated_cost_usd=1.58, backend="runpod")


class MockRemote:
    backend_id = "runpod"
    capabilities = ProviderCapabilities(
        backend="runpod",
        supports_exec=True,
        supports_artifact_pull=True,
        supports_artifact_push=True,
        supports_cost_estimate=True,
    )

    def __init__(self, events: list[str], *, fail_exec_index: int | None = None) -> None:
        self.events = events
        self.fail_exec_index = fail_exec_index
        self.exec_calls: list[dict[str, Any]] = []
        self.pull_calls: list[dict[str, Any]] = []

    def exec(self, handle: RunPodHandle, command: list[str], config: dict[str, Any]) -> RemoteExecResult:
        self.events.append("exec")
        self.exec_calls.append({"handle": handle, "command": list(command), "config": dict(config)})
        if self.fail_exec_index == len(self.exec_calls):
            return RemoteExecResult(exit_code=1, stdout="", stderr="remote failed", command=command)
        return RemoteExecResult(exit_code=0, stdout="ok\n", stderr="", command=command)

    def pull_artifacts(self, handle: RunPodHandle, remote_paths: list[str], local_dir: Path, config: dict[str, Any]) -> ArtifactPullResult:
        self.events.append("pull")
        self.pull_calls.append({"handle": handle, "remote_paths": list(remote_paths), "local_dir": local_dir, "config": dict(config)})
        local_dir.mkdir(parents=True, exist_ok=True)
        local_paths: list[Path] = []
        for remote_path in remote_paths:
            local_path = local_dir / Path(remote_path).name
            local_path.write_bytes(b"safetensors" if local_path.suffix == ".safetensors" else b"mp4")
            local_paths.append(local_path)
        return ArtifactPullResult(local_paths=local_paths, remote_paths=list(remote_paths), metadata={})


@pytest.fixture
def backend_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., tuple[MockCompute, MockRemote, list[str]]]:
    def install(*, include_handle_path: bool = True, fail_exec_index: int | None = None) -> tuple[MockCompute, MockRemote, list[str]]:
        events: list[str] = []
        compute = MockCompute(tmp_path, events, include_handle_path=include_handle_path)
        remote = MockRemote(events, fail_exec_index=fail_exec_index)
        monkeypatch.setattr(training_run_module, "get_compute_backend", lambda backend_id: compute)
        monkeypatch.setattr(training_run_module, "get_remote_execution_backend", lambda backend_id: remote)
        return compute, remote, events

    return install
