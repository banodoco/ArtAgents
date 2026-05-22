"""Compute and remote execution backend registry for training runs."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from astrid.packs.builtin.dataset_build.interfaces import (
    ArtifactPullResult,
    ComputeHandle,
    CostEstimate,
    ProviderCapabilities,
    RemoteExecResult,
    RunPodHandle,
)


class BackendRegistryError(ValueError):
    """Raised when a backend id cannot be resolved."""


class BackendExecutionError(RuntimeError):
    """Raised when a backend command fails."""


CommandRunner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]

PINNED_RUNPOD_HOURLY_RATES_USD = {
    "NVIDIA GeForce RTX 4090": 0.74,
    "NVIDIA RTX 6000 Ada Generation": 0.79,
    "NVIDIA A100 80GB PCIe": 1.89,
}


def default_command_runner(argv: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(argv), cwd=cwd, text=True, capture_output=True)


@dataclass
class RunPodComputeBackend:
    repo_root: Path = field(default_factory=lambda: Path.cwd())
    runner: CommandRunner = default_command_runner

    @property
    def backend_id(self) -> str:
        return "runpod"

    def provision(self, config: dict[str, Any]) -> ComputeHandle:
        produces_dir = _produces_dir(config, "provision")
        argv = _runpod_argv("provision", produces_dir)
        _append_optional(argv, "--gpu-type", config.get("gpu_type"))
        _append_optional(argv, "--storage-name", config.get("storage_name"))
        _append_optional(argv, "--max-runtime-seconds", config.get("max_runtime_seconds"))
        _append_optional(argv, "--name-prefix", config.get("name_prefix"))
        _append_optional(argv, "--image", config.get("image"))
        _append_optional(argv, "--container-disk-gb", config.get("container_disk_gb"))
        _append_optional(argv, "--datacenter-id", config.get("datacenter_id"))
        _append_optional(argv, "--ports", config.get("ports"))
        _run_checked(self.runner, argv, self.repo_root)

        handle_path = produces_dir / "pod_handle.json"
        handle_data = _read_json(handle_path)
        pod_id = str(handle_data.get("pod_id") or handle_data.get("id") or "")
        if not pod_id:
            raise BackendExecutionError(f"RunPod provision did not write pod_id in {handle_path}")
        return RunPodHandle(
            pod_id=pod_id,
            gpu_type=str(handle_data.get("gpu_type") or config.get("gpu_type") or ""),
            ui_url=handle_data.get("ui_url"),
            recovery_command=handle_data.get("recovery_command"),
            config_snapshot=handle_data.get("config_snapshot") if isinstance(handle_data.get("config_snapshot"), dict) else {},
            metadata={"handle_path": str(handle_path), "produces_dir": str(produces_dir), "raw_handle": handle_data},
        )

    def teardown(self, handle: ComputeHandle) -> None:
        handle_path = _handle_path(handle)
        if handle_path is None or not handle_path.exists():
            return
        produces_dir = handle_path.parent
        argv = _runpod_argv("teardown", produces_dir)
        _append_optional(argv, "--pod-handle", handle_path)
        result = self.runner(argv, self.repo_root)
        if result.returncode != 0:
            stderr = (result.stderr or "").lower()
            if "not found" in stderr or "pod not found" in stderr:
                return
            raise BackendExecutionError(f"RunPod teardown failed rc={result.returncode}: {result.stderr}")

    def estimate_cost(self, config: dict[str, Any]) -> CostEstimate:
        gpu_type = str(config.get("gpu_type") or "NVIDIA RTX 6000 Ada Generation")
        hourly_rate = PINNED_RUNPOD_HOURLY_RATES_USD.get(gpu_type, PINNED_RUNPOD_HOURLY_RATES_USD["NVIDIA RTX 6000 Ada Generation"])
        gpu_hours = float(config.get("max_gpu_hours") or 0.0)
        return CostEstimate(
            gpu_hours=gpu_hours,
            estimated_cost_usd=round(gpu_hours * hourly_rate, 4),
            backend=self.backend_id,
            details={
                "gpu_type": gpu_type,
                "hourly_rate_usd": hourly_rate,
                "pricing_source": "pinned_training_run_rates",
                "max_runpod_spend_usd": config.get("max_runpod_spend_usd"),
            },
        )


@dataclass
class RunPodRemoteExecutionBackend:
    repo_root: Path = field(default_factory=lambda: Path.cwd())
    runner: CommandRunner = default_command_runner

    @property
    def backend_id(self) -> str:
        return "runpod"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            backend=self.backend_id,
            supports_exec=True,
            supports_artifact_pull=True,
            supports_artifact_push=True,
            supports_cost_estimate=True,
            metadata={"executor_module": "astrid.packs.external.runpod.run"},
        )

    def exec(self, handle: ComputeHandle, command: list[str], config: dict[str, Any]) -> RemoteExecResult:
        produces_dir = _produces_dir(config, "exec")
        argv = _runpod_argv("exec", produces_dir)
        _append_optional(argv, "--pod-handle", _handle_path(handle))
        _append_optional(argv, "--local-root", config.get("local_root"))
        _append_optional(argv, "--remote-root", config.get("remote_root"))
        _append_optional(argv, "--remote-script", config.get("remote_script") or shlex.join(command))
        _append_optional(argv, "--timeout", config.get("timeout"))
        _append_optional(argv, "--upload-mode", config.get("upload_mode"))
        _append_optional(argv, "--excludes", config.get("excludes"))
        result = _run_checked(self.runner, argv, self.repo_root)
        payload = _read_json(produces_dir / "exec_result.json", default={})
        return RemoteExecResult(
            exit_code=int(payload.get("returncode", result.returncode)),
            stdout=str(payload.get("stdout") or result.stdout or ""),
            stderr=str(payload.get("stderr") or result.stderr or ""),
            command=list(argv),
            metadata={"produces_dir": str(produces_dir), "artifact_dir": payload.get("artifact_dir")},
        )

    def pull_artifacts(self, handle: ComputeHandle, remote_paths: list[str], local_dir: Path, config: dict[str, Any]) -> ArtifactPullResult:
        produces_dir = _produces_dir(config, "pull")
        argv = _runpod_argv("pull", produces_dir)
        _append_optional(argv, "--pod-handle", _handle_path(handle))
        for remote_path in remote_paths:
            argv.extend(["--remote-path", remote_path])
        _append_optional(argv, "--local-dir", local_dir)
        _append_optional(argv, "--ssh-key", config.get("ssh_key"))
        _run_checked(self.runner, argv, self.repo_root)
        payload = _read_json(produces_dir / "artifact_pull.json", default={})
        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), list) else []
        return ArtifactPullResult(
            local_paths=[Path(str(item["local_path"])) for item in artifacts if isinstance(item, Mapping) and item.get("local_path")],
            remote_paths=list(remote_paths),
            metadata={"produces_dir": str(produces_dir), "status": payload.get("status")},
        )


def get_compute_backend(backend_id: str, **kwargs: Any) -> RunPodComputeBackend:
    if backend_id == "runpod":
        return RunPodComputeBackend(**kwargs)
    raise BackendRegistryError(_invalid_backend_message("compute", backend_id, ["runpod"]))


def get_remote_execution_backend(backend_id: str, **kwargs: Any) -> RunPodRemoteExecutionBackend:
    if backend_id == "runpod":
        return RunPodRemoteExecutionBackend(**kwargs)
    raise BackendRegistryError(_invalid_backend_message("remote execution", backend_id, ["runpod"]))


def available_compute_backends() -> tuple[str, ...]:
    return ("runpod",)


def available_remote_execution_backends() -> tuple[str, ...]:
    return ("runpod",)


def _invalid_backend_message(kind: str, backend_id: str, available: list[str]) -> str:
    return f"unknown {kind} backend {backend_id!r}; available: {', '.join(sorted(available))}"


def _runpod_argv(command: str, produces_dir: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "astrid.packs.external.runpod.run",
        command,
        "--produces-dir",
        str(produces_dir),
    ]


def _append_optional(argv: list[str], flag: str, value: Any) -> None:
    if value is None or value == "":
        return
    argv.extend([flag, str(value)])


def _produces_dir(config: Mapping[str, Any], default_leaf: str) -> Path:
    if config.get("produces_dir"):
        return Path(str(config["produces_dir"])).expanduser().resolve()
    if config.get("run_dir"):
        return (Path(str(config["run_dir"])).expanduser() / default_leaf).resolve()
    return (Path.cwd() / "runs" / "training-run" / default_leaf).resolve()


def _handle_path(handle: ComputeHandle) -> Path | None:
    metadata = getattr(handle, "metadata", {}) or {}
    value = metadata.get("handle_path") if isinstance(metadata, Mapping) else None
    return Path(str(value)).expanduser().resolve() if value else None


def _run_checked(runner: CommandRunner, argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = runner(argv, cwd)
    if result.returncode != 0:
        raise BackendExecutionError(f"command failed rc={result.returncode}: {' '.join(argv)}\n{result.stderr}")
    return result


def _read_json(path: Path, *, default: Any | None = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if default is not None:
            return default
        raise
