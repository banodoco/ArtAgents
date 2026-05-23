"""ai-toolkit staging helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from astrid.packs.builtin.orchestrators.dataset_build.interfaces import ComputeHandle, RemoteExecResult


class StageRemoteBackend(Protocol):
    def exec(self, handle: ComputeHandle, command: list[str], config: dict[str, Any]) -> RemoteExecResult:
        ...


@dataclass(frozen=True)
class StageResult:
    manifest_path: Path
    trainer_config_path: Path
    local_root: Path
    remote_root: str
    exec_result: RemoteExecResult


def preflight_stage_inputs(*, manifest_path: Path, trainer_config_path: Path) -> None:
    """Validate local inputs before any remote staging call."""
    missing = [path for path in (manifest_path, trainer_config_path) if not Path(path).exists()]
    if missing:
        names = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"missing ai-toolkit staging input(s): {names}")


def stage_training_inputs(
    remote: StageRemoteBackend,
    handle: ComputeHandle,
    *,
    manifest_path: Path,
    trainer_config_path: Path,
    local_root: Path,
    remote_root: str,
    upload_mode: str = "sftp_walk",
    excludes: list[str] | None = None,
    produces_dir: Path | None = None,
    timeout: int | None = None,
) -> StageResult:
    """Upload prepared ai-toolkit files and verify the remote staging root."""
    manifest_path = Path(manifest_path).expanduser().resolve()
    trainer_config_path = Path(trainer_config_path).expanduser().resolve()
    local_root = Path(local_root).expanduser().resolve()
    preflight_stage_inputs(manifest_path=manifest_path, trainer_config_path=trainer_config_path)
    local_root.mkdir(parents=True, exist_ok=True)

    config: dict[str, Any] = {
        "local_root": local_root,
        "remote_root": remote_root,
        "upload_mode": upload_mode,
        "excludes": ",".join(excludes or []),
        "remote_script": _stage_script(remote_root),
    }
    if produces_dir is not None:
        config["produces_dir"] = Path(produces_dir)
    if timeout is not None:
        config["timeout"] = timeout

    result = remote.exec(handle, ["bash", "-lc", _stage_script(remote_root)], config)
    if result.exit_code != 0:
        raise RuntimeError(f"ai-toolkit staging failed: {result.stderr or result.stdout}")
    return StageResult(
        manifest_path=manifest_path,
        trainer_config_path=trainer_config_path,
        local_root=local_root,
        remote_root=remote_root,
        exec_result=result,
    )


def _stage_script(remote_root: str) -> str:
    return f"mkdir -p {remote_root}/dataset {remote_root}/output && test -d {remote_root}"
