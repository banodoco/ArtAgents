"""Process boundary for Astrid's one generic pack executor host.

The neutral runtime owns data and credentials.  This module only starts the
generic executor, waits for its registration/preflight readiness record, and
keeps a small support-directory marker so an Astrid relaunch reuses one host.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

PACK_HOST_ACTOR = "astrid-pack-host"
PACK_HOST_SCOPES = (
    "worker:register",
    "worker:execute",
    "tasks:read",
    "tasks:write",
    "objects:read",
    "objects:write",
)


class PackHostBootstrapError(RuntimeError):
    """A bounded, secret-free failure while starting the generic host."""


def _host_pid_alive(pid: Any) -> bool:
    try:
        value = int(pid)
    except (TypeError, ValueError):
        return False
    if value <= 0:
        return False
    try:
        os.kill(value, 0)
    except OSError:
        return False
    return True


def _host_command(pid: Any) -> str:
    try:
        value = int(pid)
    except (TypeError, ValueError):
        return ""
    try:
        return Path(f"/proc/{value}/cmdline").read_bytes().decode("utf-8", "ignore").replace("\x00", " ")
    except (OSError, ValueError):
        try:
            probe = subprocess.run(
                ["ps", "-p", str(value), "-o", "command="],
                capture_output=True, text=True, check=False, timeout=1.0,
            )
            return probe.stdout.strip()
        except (OSError, subprocess.SubprocessError, ValueError):
            return ""


def _our_host(pid: Any) -> bool:
    return _host_pid_alive(pid) and "astrid.core.execution.generic_host" in _host_command(pid)


def _read_object(path: Path) -> Mapping[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def _write_object(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.write_text(json.dumps(dict(value), sort_keys=True), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _terminate_old_host(state: Mapping[str, Any]) -> None:
    """Stop only a prior generic host identified by its own marker."""
    pid = state.get("pid")
    if not _our_host(pid):
        return
    try:
        os.kill(int(pid), signal.SIGTERM)
    except OSError:
        return
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and _host_pid_alive(pid):
        time.sleep(0.05)


def ensure_pack_host(value: Mapping[str, Any], *, reconfigure_action: str) -> Mapping[str, Any]:
    """Ensure the runtime-issued pack host is registered and preflight-ready."""
    worker_file = value.get("worker_credential_file")
    source_checkout = value.get("source_checkout")
    if not worker_file or not source_checkout:
        # Tiny fake launcher boundaries intentionally model only the runtime
        # handoff.  Real neutral-runtime results contain both fields.
        return {}
    from astrid.sdk.workspace_client import _safe_local_path

    try:
        worker_path = _safe_local_path(str(worker_file), field="worker credential")
        source_path = _safe_local_path(str(source_checkout), field="source checkout")
    except Exception as exc:
        raise PackHostBootstrapError(f"generic Astrid pack host handoff is unsafe; {reconfigure_action}") from exc
    if (not worker_path.is_file() or worker_path.is_symlink()
            or not source_path.is_dir() or source_path.is_symlink()):
        raise PackHostBootstrapError(f"generic Astrid pack host handoff is unavailable; {reconfigure_action}")
    pack_root = source_path / "astrid" / "packs"
    if not pack_root.is_dir() or pack_root.is_symlink():
        raise PackHostBootstrapError(f"Astrid source checkout has no pack root; {reconfigure_action}")
    scopes = tuple(str(scope) for scope in (value.get("worker_scopes") or ()))
    if str(value.get("worker_actor")) != PACK_HOST_ACTOR or scopes != PACK_HOST_SCOPES:
        raise PackHostBootstrapError(f"runtime worker credential is not the least-privilege pack-host contract; {reconfigure_action}")

    runtime_support = worker_path.parent.parent
    state_path = runtime_support / "generic-host.json"
    ready_path = runtime_support / "generic-host.ready.json"
    lock_path = runtime_support / "generic-host.lock"
    endpoint = str(value["endpoint"]).rstrip("/")
    try:
        lock_handle = lock_path.open("a+")
        os.fchmod(lock_handle.fileno(), 0o600)
    except OSError as exc:
        raise PackHostBootstrapError(f"generic Astrid pack host lock is unavailable; {reconfigure_action}") from exc
    try:
        try:
            import fcntl
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError) as exc:
            raise PackHostBootstrapError(f"generic Astrid pack host lock is unavailable; {reconfigure_action}") from exc
        current = _read_object(state_path)
        ready = _read_object(ready_path)
        if (current and ready
                and str(current.get("endpoint", "")).rstrip("/") == endpoint
                and str(current.get("executor_id")) == PACK_HOST_ACTOR
                and _our_host(current.get("pid"))
                and str(ready.get("status")) == "ready"
                and str(ready.get("pid")) == str(current.get("pid"))):
            return {
                "host_status": "ready",
                "host_pid": int(current["pid"]),
                "host_executor_id": PACK_HOST_ACTOR,
                "host_ready_file": str(ready_path),
                "host_ready_capabilities": list(ready.get("ready_capabilities", [])),
            }
        if current:
            _terminate_old_host(current)
        ready_path.unlink(missing_ok=True)
        log_path = runtime_support / "generic-host.log"
        matrix = source_path / "config" / "astrid-beta-capabilities.json"
        argv = [
            os.environ.get("PYTHON", sys.executable),
            "-m", "astrid.core.execution.generic_host", "run",
            "--pack-root", str(pack_root),
            "--runtime-endpoint", endpoint,
            "--credential-file", str(worker_path),
            "--executor-id", PACK_HOST_ACTOR,
            "--ready-file", str(ready_path),
        ]
        if matrix.is_file():
            argv.extend(("--capability-matrix", str(matrix)))
        child_env = dict(os.environ)
        existing_pythonpath = child_env.get("PYTHONPATH", "")
        child_env["PYTHONPATH"] = os.pathsep.join(item for item in (str(source_path), existing_pythonpath) if item)
        try:
            log = log_path.open("ab")
            process = subprocess.Popen(
                argv,
                cwd=str(source_path),
                env=child_env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
                close_fds=True,
            )
        except OSError as exc:
            raise PackHostBootstrapError(f"generic Astrid pack host could not be started; {reconfigure_action}") from exc
        finally:
            try:
                log.close()
            except UnboundLocalError:
                pass
        deadline = time.monotonic() + 20.0
        ready = None
        while time.monotonic() < deadline:
            ready = _read_object(ready_path)
            if ready and str(ready.get("status")) == "ready":
                break
            if process.poll() is not None:
                break
            time.sleep(0.05)
        if (not ready or ready.get("status") != "ready"
                or str(ready.get("pid")) != str(process.pid)
                or process.poll() is not None):
            _terminate_old_host({"pid": process.pid})
            raise PackHostBootstrapError(f"generic Astrid pack host did not become ready; inspect {log_path}")
        _write_object(state_path, {
            "version": 1,
            "pid": process.pid,
            "endpoint": endpoint,
            "executor_id": PACK_HOST_ACTOR,
            "ready_file": str(ready_path),
            "source_checkout": str(source_path),
        })
        return {
            "host_status": "ready",
            "host_pid": process.pid,
            "host_executor_id": PACK_HOST_ACTOR,
            "host_ready_file": str(ready_path),
            "host_ready_capabilities": list(ready.get("ready_capabilities", [])),
        }
    finally:
        try:
            import fcntl
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        lock_handle.close()


__all__ = ["PACK_HOST_ACTOR", "PACK_HOST_SCOPES", "PackHostBootstrapError", "ensure_pack_host"]
