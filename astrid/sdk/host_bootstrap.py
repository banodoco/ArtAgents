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

from astrid.core.execution.process_group import _process_snapshot

PACK_HOST_ACTOR = "astrid-pack-host"
PACK_HOST_SCOPES = (
    "worker:register",
    "worker:execute",
    "tasks:read",
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
    except PermissionError:
        return True
    except OSError:
        return False
    # A terminated process can remain as a zombie until its original parent
    # reaps it.  It is not a live host and must not block a fresh launch.
    try:
        stat = Path(f"/proc/{value}/stat").read_text(encoding="ascii")
        state = stat.rsplit(")", 1)[-1].lstrip().split(None, 1)[0]
        if state == "Z":
            return False
    except (OSError, UnicodeDecodeError, IndexError):
        pass
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


def _host_birth_identity(pid: Any) -> str:
    """Return the OS birth token for *pid*, or an empty value if unavailable."""
    try:
        value = int(pid)
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    try:
        info = _process_snapshot().get(value)
    except Exception:
        info = None
    return str(info.birth) if info is not None else ""


def _host_identity_matches(state: Mapping[str, Any]) -> bool:
    """Verify PID, birth, process group, and every launch binding."""
    pid = state.get("pid")
    if not _host_pid_alive(pid):
        return False
    expected_birth = str(state.get("process_birth_id") or "")
    if not expected_birth or _host_birth_identity(pid) != expected_birth:
        return False
    if not _our_host(pid):
        return False
    try:
        if os.getpgid(int(pid)) != int(pid):
            return False
    except (OSError, TypeError, ValueError):
        return False
    command = _host_command(pid)
    required = (
        "astrid.core.execution.generic_host",
        str(state.get("ready_file") or ""),
        str(state.get("source_checkout") or ""),
        str(state.get("credential_file") or ""),
        str(state.get("support_root") or ""),
        str(state.get("endpoint") or ""),
    )
    return all(value and value in command for value in required)


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


def _dependency_pythonpath() -> tuple[str, ...]:
    """Keep explicitly supplied interpreter dependency roots across the host boundary."""
    values: list[str] = []
    for raw in os.environ.get("PYTHONPATH", "").split(os.pathsep):
        if not raw:
            continue
        path = Path(raw)
        if path.name in {"site-packages", "dist-packages"}:
            values.append(str(path))
    return tuple(dict.fromkeys(values))


def _descendant_snapshot(pid: int) -> dict[int, tuple[str, int]]:
    """Capture descendant birth/PGID pairs before stopping a host."""
    try:
        snapshot = _process_snapshot()
    except Exception:
        return {}
    descendants: dict[int, tuple[str, int]] = {}
    frontier = [pid]
    while frontier:
        parent = frontier.pop()
        for info in snapshot.values():
            if info.ppid == parent and info.pid not in descendants:
                descendants[info.pid] = (str(info.birth), int(info.pgid))
                frontier.append(info.pid)
    return descendants


def _terminate_descendants(members: Mapping[int, tuple[str, int]]) -> None:
    """Clean groups/children captured from the verified host, with birth checks."""
    if not members:
        return
    groups: dict[int, str] = {
        pgid: birth
        for pid, (birth, pgid) in members.items()
        if pid == pgid
    }
    for sig, seconds in ((signal.SIGTERM, 1.0), (signal.SIGKILL, 1.0)):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            snapshot = _process_snapshot()
            live = [
                (pid, birth)
                for pid, (birth, _pgid) in members.items()
                if (info := snapshot.get(pid)) is not None and info.birth == birth
            ]
            if not live:
                return
            # A child launched by GenericPackHost is a fresh session leader.
            # Kill its whole group only while that leader's birth token still
            # matches; otherwise fall back to exact individual members so a
            # reused PGID can never receive the signal.
            for pgid, birth in groups.items():
                leader = snapshot.get(pgid)
                if leader is not None and leader.birth == birth and leader.pgid == pgid:
                    try:
                        os.killpg(pgid, sig)
                    except OSError:
                        pass
            # Signal individual birth-verified processes whose group leader is
            # already gone, including late descendants observed by the group
            # signal above on the next census.
            for pid, _birth in live:
                info = snapshot.get(pid)
                if info is not None and info.pgid in groups:
                    leader = snapshot.get(info.pgid)
                    if leader is not None and leader.birth == groups[info.pgid]:
                        continue
                try:
                    os.kill(pid, sig)
                except OSError:
                    pass
            time.sleep(0.03)


def _terminate_old_host(state: Mapping[str, Any]) -> None:
    """TERM, bounded wait, then KILL one exact prior host and its children."""
    pid_value = state.get("pid")
    try:
        pid = int(pid_value)
    except (TypeError, ValueError):
        return
    if not _host_pid_alive(pid):
        return
    if not _host_identity_matches(state):
        raise PackHostBootstrapError(
            "existing generic Astrid host cannot be verified safely; remove its stale marker and retry"
        )
    members = _descendant_snapshot(pid)

    def signal_verified(sig: int) -> None:
        if not _host_pid_alive(pid):
            return
        if not _host_identity_matches(state):
            return
        try:
            if os.getpgid(pid) == pid and hasattr(os, "killpg"):
                os.killpg(pid, sig)
            else:
                os.kill(pid, sig)
        except OSError:
            pass

    signal_verified(signal.SIGTERM)
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and _host_pid_alive(pid):
        time.sleep(0.05)
    if _host_pid_alive(pid):
        signal_verified(signal.SIGKILL)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and _host_pid_alive(pid):
            time.sleep(0.05)
    _terminate_descendants(members)
    if _host_pid_alive(pid):
        raise PackHostBootstrapError("prior generic Astrid host did not terminate")


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
            or not source_path.is_dir() or source_path.is_symlink()
            or worker_path.stat().st_mode & 0o777 != 0o600):
        raise PackHostBootstrapError(f"generic Astrid pack host handoff is unavailable; {reconfigure_action}")
    pack_root = source_path / "astrid" / "packs"
    if not pack_root.is_dir() or pack_root.is_symlink():
        raise PackHostBootstrapError(f"Astrid source checkout has no pack root; {reconfigure_action}")
    scopes = tuple(str(scope) for scope in (value.get("worker_scopes") or ()))
    if str(value.get("worker_actor")) != PACK_HOST_ACTOR or scopes != PACK_HOST_SCOPES:
        raise PackHostBootstrapError(f"runtime worker credential is not the least-privilege pack-host contract; {reconfigure_action}")

    # Bind the process to the exact source and runtime instance it registered
    # against.  The health read is intentionally performed with the worker
    # credential, never the owner credential or an ambient environment token.
    from astrid.core.execution.generic_host import RuntimeProtocolClient, source_checkout_digest

    try:
        source_digest = source_checkout_digest(source_path)
    except (OSError, ValueError) as exc:
        raise PackHostBootstrapError(
            f"generic Astrid pack source tree is not a safe checkout; {reconfigure_action}"
        ) from exc
    try:
        worker_token = worker_path.read_text(encoding="utf-8").strip()
        if not worker_token:
            raise ValueError("worker credential is empty")
        runtime_client = RuntimeProtocolClient(str(value["endpoint"]).rstrip("/"), worker_token)
        health = runtime_client.health()
    except Exception as exc:
        raise PackHostBootstrapError(
            f"generic Astrid pack host could not verify runtime identity; {reconfigure_action}"
        ) from exc
    finally:
        worker_token = ""
    health_value = dict(health) if isinstance(health, Mapping) else {
        "runtime_epoch": getattr(health, "runtime_epoch", None),
        "schema_digest": getattr(health, "schema_digest", None),
        "runtime_instance_id": getattr(health, "runtime_instance_id", None),
        "coordinator_epoch": getattr(health, "coordinator_epoch", None),
    }
    runtime_epoch = health_value.get("runtime_epoch", value.get("runtime_epoch"))
    runtime_instance_id = (
        value.get("runtime_instance_id")
        or health_value.get("runtime_instance_id")
        or value.get("coordinator_epoch")
        or health_value.get("coordinator_epoch")
        or (f"epoch:{runtime_epoch}" if runtime_epoch is not None else None)
    )
    schema_digest = health_value.get("schema_digest") or value.get("schema_digest")
    if runtime_epoch is None or runtime_instance_id is None:
        raise PackHostBootstrapError(
            f"generic Astrid pack host runtime identity is incomplete; {reconfigure_action}"
        )

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
        expected = {
            "endpoint": endpoint,
            "executor_id": PACK_HOST_ACTOR,
            "ready_file": str(ready_path),
            "credential_file": str(worker_path),
            "support_root": str(runtime_support),
            "source_checkout": str(source_path),
            "source_checkout_digest": source_digest,
            "runtime_instance_id": str(runtime_instance_id),
            "runtime_epoch": runtime_epoch,
            "schema_digest": schema_digest,
        }
        if (current and ready
                and all(current.get(key) == expected_value for key, expected_value in expected.items())
                and _host_identity_matches(current)
                and str(ready.get("status")) == "ready"
                and all(ready.get(key) == expected_value for key, expected_value in expected.items())
                and str(ready.get("pid")) == str(current.get("pid"))
                and str(ready.get("process_birth_id")) == str(current.get("process_birth_id"))):
            return {
                "host_status": "ready",
                "host_pid": int(current["pid"]),
                "host_executor_id": PACK_HOST_ACTOR,
                "host_ready_file": str(ready_path),
                "host_ready_capabilities": list(ready.get("ready_capabilities", [])),
                "host_runtime_instance_id": str(runtime_instance_id),
                "host_runtime_epoch": runtime_epoch,
                "host_source_checkout_digest": source_digest,
            }
        if current:
            _terminate_old_host(current)
        ready_path.unlink(missing_ok=True)
        log_path = runtime_support / "generic-host.log"
        matrix = source_path / "config" / "astrid-beta-capabilities.json"
        argv = [
            sys.executable,
            "-m", "astrid.core.execution.generic_host", "run",
            "--pack-root", str(pack_root),
            "--runtime-endpoint", endpoint,
            "--credential-file", str(worker_path),
            "--executor-id", PACK_HOST_ACTOR,
            "--ready-file", str(ready_path),
            "--support-root", str(runtime_support),
            "--source-checkout", str(source_path),
            "--runtime-instance-id", str(runtime_instance_id),
            "--register",
        ]
        if matrix.is_file():
            argv.extend(("--capability-matrix", str(matrix)))
        child_env = dict(os.environ)
        # The selected source profile is the complete pack-discovery fence;
        # ambient pack roots/PYTHONPATH entries must not silently add another
        # checkout to this host.
        child_env.pop("ASTRID_PACKS_PATH", None)
        child_env["PYTHONPATH"] = os.pathsep.join(
            (str(source_path), *_dependency_pythonpath())
        )
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
        process_state = {
            **expected,
            "version": 2,
            "pid": process.pid,
            "process_birth_id": _host_birth_identity(process.pid),
        }
        if not process_state["process_birth_id"]:
            _terminate_old_host(process_state)
            raise PackHostBootstrapError(f"generic Astrid pack host identity could not be captured; {reconfigure_action}")
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
                or str(ready.get("process_birth_id")) != str(process_state["process_birth_id"])
                or not all(ready.get(key) == expected_value for key, expected_value in expected.items())
                or process.poll() is not None):
            _terminate_old_host(process_state)
            raise PackHostBootstrapError(f"generic Astrid pack host did not become ready; inspect {log_path}")
        _write_object(state_path, process_state)
        return {
            "host_status": "ready",
            "host_pid": process.pid,
            "host_executor_id": PACK_HOST_ACTOR,
            "host_ready_file": str(ready_path),
            "host_ready_capabilities": list(ready.get("ready_capabilities", [])),
            "host_runtime_instance_id": str(runtime_instance_id),
            "host_runtime_epoch": runtime_epoch,
            "host_source_checkout_digest": source_digest,
        }
    finally:
        try:
            import fcntl
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        lock_handle.close()


__all__ = ["PACK_HOST_ACTOR", "PACK_HOST_SCOPES", "PackHostBootstrapError", "ensure_pack_host"]
