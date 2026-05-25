"""ai-toolkit remote training helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from astrid.packs.training.orchestrators.dataset_build.interfaces import ComputeHandle, RemoteExecResult


class TrainRemoteBackend(Protocol):
    def exec(self, handle: ComputeHandle, command: list[str], config: dict[str, Any]) -> RemoteExecResult:
        ...


@dataclass(frozen=True)
class Checkpoint:
    remote_path: str
    step: int | None = None
    label: str | None = None


@dataclass(frozen=True)
class TrainingResult:
    remote_config_path: str
    remote_output_dir: str
    log_path: Path
    exec_result: RemoteExecResult


def run_training(
    remote: TrainRemoteBackend,
    handle: ComputeHandle,
    *,
    remote_config_path: str,
    remote_output_dir: str,
    log_path: Path,
    produces_dir: Path | None = None,
    timeout: int | None = None,
) -> TrainingResult:
    """Run ai-toolkit training remotely and mirror captured logs locally."""
    script = f"cd /workspace/ai-toolkit && python run.py {remote_config_path}"
    config: dict[str, Any] = {
        "remote_root": "/workspace",
        "remote_script": script,
        "artifact_dir": remote_output_dir,
    }
    if produces_dir is not None:
        config["produces_dir"] = Path(produces_dir)
    if timeout is not None:
        config["timeout"] = timeout

    result = remote.exec(handle, ["bash", "-lc", script], config)
    log_path = Path(log_path).expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(_combined_log(result), encoding="utf-8")
    if result.exit_code != 0:
        raise RuntimeError(f"ai-toolkit training failed; mirrored log: {log_path}")
    return TrainingResult(remote_config_path=remote_config_path, remote_output_dir=remote_output_dir, log_path=log_path, exec_result=result)


def parse_checkpoint_manifest(path: Path) -> list[Checkpoint]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("checkpoints") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        raise ValueError("checkpoint manifest must be a list or object with checkpoints[]")
    checkpoints: list[Checkpoint] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"checkpoint {index} must be an object")
        remote_path = row.get("remote_path") or row.get("path")
        if not isinstance(remote_path, str) or not remote_path:
            raise ValueError(f"checkpoint {index} missing remote_path")
        step = row.get("step")
        if step is not None and not isinstance(step, int):
            raise ValueError(f"checkpoint {index} step must be an integer")
        label = row.get("label")
        if label is not None and not isinstance(label, str):
            raise ValueError(f"checkpoint {index} label must be a string")
        checkpoints.append(Checkpoint(remote_path=remote_path, step=step, label=label))
    if not checkpoints:
        raise ValueError("checkpoint manifest must contain at least one checkpoint")
    return checkpoints


def _combined_log(result: RemoteExecResult) -> str:
    parts = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append(result.stderr.rstrip())
    return "\n".join(parts) + ("\n" if parts else "")
