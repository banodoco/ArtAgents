"""Provider-neutral remote-artifact adapter contract."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

from astrid.core.adapter import CompleteResult, DispatchResult, PollResult, RunContext
from astrid.core.adapter._common import _read_cost_sidecar, _step_dir
from astrid.core.project.sidecar import write_json_sidecar
from astrid.core.subprocess_env import build_child_subprocess_env
from astrid.core.task.plan import CostEntry, Step
from astrid.core.util.time import utc_now_milliseconds


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_state(path: Path, state: dict[str, object]) -> None:
    write_json_sidecar(path, state)


def _update_state(path: Path, updates: dict[str, object]) -> dict[str, object]:
    state = _read_json(path)
    state.update(updates)
    _write_state(path, state)
    return state


class RemoteArtifactAdapter:
    """Dispatches a provider-neutral command and completes from fetched artifacts."""

    name = "remote-artifact"

    def dispatch(self, step: Step, run_ctx: RunContext) -> DispatchResult:
        if step.command is None or not step.command.strip():
            return DispatchResult(status="rejected", reason="remote-artifact adapter requires a non-empty command")
        step_dir = _step_dir(run_ctx)
        step_dir.mkdir(parents=True, exist_ok=True)
        try:
            argv = list(run_ctx.canonical_argv) if run_ctx.canonical_argv else shlex.split(step.command)
        except ValueError as exc:
            return DispatchResult(status="rejected", reason=f"command not shell-parseable: {exc}")

        log_path = step_dir / "subprocess.log"
        log_handle = open(log_path, "ab")
        try:
            proc = subprocess.Popen(
                argv,
                cwd=str(run_ctx.project_root),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                env=build_child_subprocess_env(explicit_env=run_ctx.task_env or {}),
            )
        except (FileNotFoundError, OSError) as exc:
            log_handle.close()
            return DispatchResult(status="rejected", reason=f"spawn failed: {exc}")
        finally:
            log_handle.close()

        started_at = utc_now_milliseconds()
        job_id = argv[-1] if argv else f"pid-{proc.pid}"
        state = {
            "schema_version": 1,
            "provider": "provider-neutral",
            "job_id": job_id,
            "started_at": started_at,
            "status": "running",
            "command": run_ctx.canonical_command or step.command,
            "display_command": run_ctx.display_command,
            "task_env": run_ctx.task_env or {},
            "poll_interval_seconds": step.poll_interval_seconds,
            "pid": proc.pid,
            "artifacts": [
                {"name": entry.name, "path": entry.path, "sha256": entry.checksum}
                for entry in step.produces
            ],
        }
        _write_state(step_dir / "remote_state.json", state)
        write_json_sidecar(
            step_dir / "dispatch.json",
            {
                "adapter": self.name,
                "provider": "provider-neutral",
                "command": run_ctx.canonical_command or step.command,
                "display_command": run_ctx.display_command,
                "task_env": run_ctx.task_env or {},
                "pid": proc.pid,
                "started_at": started_at,
                "runpod_smoke_manifest": {
                    "provider": "runpod",
                    "job_id": job_id,
                    "artifacts": state["artifacts"],
                },
            },
        )
        (step_dir / "returncode").write_text("-1", encoding="utf-8")
        return DispatchResult(status="dispatched", pid=proc.pid, started_at=started_at)

    def poll(self, step: Step, run_ctx: RunContext) -> PollResult:
        state_path = _step_dir(run_ctx) / "remote_state.json"
        if not state_path.exists():
            return PollResult(status="pending")
        state = _read_json(state_path)
        status = state.get("status")
        if status == "awaiting_fetch":
            return PollResult(status="done")
        if status == "failed":
            return PollResult(status="failed")
        if status == "done":
            return PollResult(status="done")
        try:
            pid = int(state.get("pid", 0))
        except (TypeError, ValueError):
            return PollResult(status="failed")
        if pid <= 0:
            return PollResult(status="failed")
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            _update_state(state_path, {"status": "done"})
            return PollResult(status="done")
        except PermissionError:
            return PollResult(status="running")
        return PollResult(status="running")

    def complete(self, step: Step, run_ctx: RunContext) -> CompleteResult:
        from astrid.core.adapter.remote_artifact_fetch import fetch_artifacts

        step_dir = _step_dir(run_ctx)
        returncode_path = step_dir / "returncode"
        if not returncode_path.exists():
            return CompleteResult(status="failed", reason="returncode sidecar missing", cost=_read_cost_sidecar(step_dir))
        try:
            returncode = int(returncode_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return CompleteResult(status="failed", reason="returncode sidecar invalid", cost=_read_cost_sidecar(step_dir))
        if returncode != 0:
            _update_state(step_dir / "remote_state.json", {"status": "failed", "returncode": returncode})
            return CompleteResult(
                status="failed",
                returncode=returncode,
                reason=f"remote command exited with returncode={returncode}",
                cost=_read_cost_sidecar(step_dir),
            )

        state_path = step_dir / "remote_state.json"
        state = _read_json(state_path)
        manifest_obj = state.get("manifest")
        manifest = manifest_obj if isinstance(manifest_obj, dict) else None
        result = fetch_artifacts(step, run_ctx, manifest=manifest)  # type: ignore[arg-type]
        state.update({
            "fetched": result.fetched,
            "missing": result.missing,
            "mismatched": result.mismatched,
            "checksums": result.checksums,
            "fetch_status": result.status,
        })
        _write_state(state_path, state)
        if result.status == "completed":
            _update_state(state_path, {"status": "done", "returncode": returncode})
            return CompleteResult(status="completed", returncode=returncode, cost=_read_cost_sidecar(step_dir))
        if result.status == "awaiting_fetch":
            _update_state(state_path, {"status": "awaiting_fetch", "returncode": returncode})
            reason = result.reason or f"awaiting remote artifacts: missing={result.missing!r} mismatched={result.mismatched!r}"
            return CompleteResult(status="awaiting_fetch", returncode=returncode, cost=_read_cost_sidecar(step_dir), reason=reason)
        _update_state(state_path, {"status": "failed", "returncode": returncode})
        return CompleteResult(status="failed", returncode=returncode, cost=_read_cost_sidecar(step_dir), reason=result.reason)


__all__ = ["RemoteArtifactAdapter"]
