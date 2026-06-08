"""Wait-adapter, subprocess-poll, and remote-artifact helpers for the Astrid gateway.

Extracted from ``astrid/gateway.py`` during M4 batch 37 (T38) to keep the
gateway facade below the 1,200-line threshold while preserving the
characterized facade exports that callers and monkeypatch seams rely on.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any


def _wait_adapter(decision: Any) -> int:
    """Wait for an adapter-dispatched step to complete. Returns a returncode.

    For local adapter: poll the subprocess until it exits, capture returncode.
    For manual adapter: the agent does work out-of-band; return 0 immediately.
    For remote-artifact adapter: wait for the generic subprocess wrapper.
    """
    # Look up callees through the gateway module so monkeypatch.setattr on
    # astrid.core.gateway._wait_local_subprocess (used by tests) still intercepts.
    _gw = sys.modules.get("astrid.core.gateway")
    _wls = _gw._wait_local_subprocess if _gw is not None else _wait_local_subprocess
    _wra = _gw._wait_remote_artifact if _gw is not None else _wait_remote_artifact

    adapter_kind = getattr(decision, "adapter", None)
    if adapter_kind == "local":
        return _wls(decision)
    if adapter_kind == "manual":
        # Manual steps: dispatch payload already written; agent works out-of-band.
        # Completion arrives via ack or inbox — not a subprocess exit code.
        return 0
    if adapter_kind == "remote-artifact":
        return _wra(decision)
    # Legacy / unknown: fall through to 0 (adapter handles it in record_dispatch_complete).
    return 0


def _wait_local_subprocess(decision: Any) -> int:
    """Block until the local-adapter subprocess exits. Return its exit code."""
    pid = getattr(decision, "pid", None)
    if pid is None:
        return -1
    try:
        while True:
            try:
                wpid, status = os.waitpid(pid, os.WNOHANG)
                if wpid == pid:
                    if os.WIFEXITED(status):
                        return os.WEXITSTATUS(status)
                    if os.WIFSIGNALED(status):
                        return -abs(os.WTERMSIG(status))
                    return -1
            except ChildProcessError:
                # Already reaped — check returncode sidecar.
                return _read_returncode_sidecar(decision)
            except ProcessLookupError:
                return _read_returncode_sidecar(decision)
            time.sleep(0.1)
    except KeyboardInterrupt:
        # Forward the interrupt to the child but don't crash.
        try:
            os.kill(pid, 2)  # SIGINT
        except OSError:
            pass
        return -1


def _wait_remote_artifact(decision: Any) -> int:
    """Block until the generic remote-artifact subprocess exits."""
    # Late-binding through the gateway module to preserve monkeypatch seams.
    _gw = sys.modules.get("astrid.core.gateway")
    _wls = _gw._wait_local_subprocess if _gw is not None else _wait_local_subprocess
    return _wls(decision)


def _make_run_ctx_for_poll(
    project_root: Any, run_id: Any, path_tuple: Any, step_version: Any
) -> Any:
    """Build a minimal RunContext for adapter.poll() calls."""
    from astrid.core.adapter import RunContext

    return RunContext(
        slug="",
        run_id=str(run_id),
        project_root=Path(project_root) if not isinstance(project_root, Path) else project_root,
        plan_step_path=tuple(path_tuple),
        step_version=int(step_version),
    )


def _read_returncode_sidecar(decision: Any) -> int:
    """If the subprocess pid is gone, try to read the returncode sidecar file."""

    project_root = getattr(decision, "project_root", None)
    run_id = getattr(decision, "run_id", None)
    path_tuple = getattr(decision, "plan_step_path", ())
    step_version = getattr(decision, "step_version", 1)
    if not project_root or not run_id or not path_tuple:
        return -1
    step_dir = project_root / "runs" / run_id / "steps"
    for seg in path_tuple:
        step_dir = step_dir / seg
    step_dir = step_dir / f"v{step_version}"
    rc_path = step_dir / "returncode"
    if rc_path.exists():
        try:
            return int(rc_path.read_text().strip())
        except (ValueError, OSError):
            pass
    return -1
