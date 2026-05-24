"""Runtime entrypoint for external.runpod.* executors.


Four subcommands — provision, exec, teardown, session — all adapter:local.
Each writes produces files to a ``--produces-dir`` directory passed by the
framework via the ``{out}/produces`` template placeholder.
"""

from __future__ import annotations


from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint
guard_canonical_entrypoint('external.runpod')
import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast

from astrid.core.util.time import utc_now_milliseconds

# ---------------------------------------------------------------------------
# Pinned GPU pricing fallback (USD/hr).
# Used when the RunPod pricing API is unreachable.
# ---------------------------------------------------------------------------

_PRICING_TABLE: dict[str, float] = {
    "NVIDIA GeForce RTX 4090": 0.34,
    "NVIDIA RTX 4090": 0.34,
    "NVIDIA A100-SXM4-80GB": 1.89,
    "NVIDIA A100 80GB SXM4": 1.89,
    "NVIDIA A40": 0.79,
    "NVIDIA A6000": 0.79,
    "NVIDIA RTX 6000 Ada": 0.79,
    "NVIDIA L40S": 1.14,
    "NVIDIA L40": 1.14,
    "NVIDIA H100-SXM-80GB": 2.99,
    "NVIDIA H100 80GB HBM3": 2.99,
}


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 with milliseconds."""
    return utc_now_milliseconds()


def _get_hourly_rate(api_key: str, gpu_type) -> float:
    """Resolve the hourly rate for *gpu_type*.

    Accepts str or list[str]; for a list, uses the first element as the rate estimate
    (auto-fallback's actual selection only known post-launch).
    Tries the RunPod GPU listing first; falls back to the pinned table.
    """
    if isinstance(gpu_type, (list, tuple)):
        gpu_type = gpu_type[0] if gpu_type else ""
    try:
        from runpod_lifecycle.api import find_gpu_type

        gpu_info = find_gpu_type(gpu_type, api_key)
        if gpu_info:
            for field in ("securePrice", "price", "costPerHr", "minPrice"):
                rate = gpu_info.get(field)
                if rate is not None:
                    return float(rate)
    except Exception:
        pass

    # Fallback to pinned table.
    rate = _PRICING_TABLE.get(gpu_type)
    if rate is not None:
        return rate

    # Last-resort: partial match on common prefixes.
    for known_name, known_rate in _PRICING_TABLE.items():
        if gpu_type.lower() in known_name.lower() or known_name.lower() in gpu_type.lower():
            return known_rate

    return 0.50  # Sensible default for unknown GPUs.


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write *payload* as indented JSON, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def _cost_entry(amount: float, source: str, basis: str) -> dict[str, Any]:
    """Build a cost sidecar dict matching the Sprint 3 CostEntry shape."""
    return {
        "amount": round(amount, 6),
        "currency": "USD",
        "source": source,
        "basis": basis,
    }


def _cost_amount(duration_seconds: float, hourly_rate: float) -> float:
    """Compute cost from wallclock-seconds and hourly rate."""
    return duration_seconds * hourly_rate / 3600.0


def _write_cost_sidecar(produces_dir: Path, *, duration_seconds: float, hourly_rate: float, basis_prefix: str) -> None:
    _write_json(
        produces_dir / "cost.json",
        _cost_entry(
            _cost_amount(duration_seconds, hourly_rate),
            "runpod",
            f"{basis_prefix}: {duration_seconds:.1f}s * ${hourly_rate}/hr",
        ),
    )


def _artifact_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not root.is_dir():
        return records
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        records.append(
            {
                "path": str(path.relative_to(root)),
                "size_bytes": path.stat().st_size,
            }
        )
    return records


def _copy_detached_artifact_root(artifact_root: str | None, produces_dir: Path) -> tuple[str | None, list[dict[str, Any]]]:
    """Copy only the substrate-returned artifact root into produces/artifact_dir."""
    artifact_dst = produces_dir / "artifact_dir"
    if artifact_dst.exists():
        shutil.rmtree(artifact_dst)
    artifact_dst.mkdir(parents=True, exist_ok=True)

    if not artifact_root:
        return str(artifact_dst), []

    artifact_src = Path(artifact_root)
    if not artifact_src.is_dir():
        return str(artifact_dst), []

    for item in artifact_src.iterdir():
        dst = artifact_dst / item.name
        if item.is_dir():
            shutil.copytree(item, dst)
        else:
            shutil.copy2(item, dst)
    return str(artifact_dst), _artifact_records(artifact_dst)


def _termination_status(returncode: int, terminated: bool) -> str:
    if terminated:
        return "terminated"
    if returncode == 0:
        return "completed"
    return "remote_failed"


def _detached_exec_result(
    result: Any,
    *,
    produces_dir: Path,
    pod_id: str,
    name_prefix: str,
    remote_root: str,
    upload_mode: str,
    timeout: int,
) -> dict[str, Any]:
    artifact_root = str(result.artifact_root) if result.artifact_root else None
    artifact_dir, artifact_paths = _copy_detached_artifact_root(artifact_root, produces_dir)
    payload: dict[str, Any] = {
        "returncode": int(result.returncode),
        "stdout": str(result.stdout or ""),
        "stderr": str(result.stderr or ""),
        "terminated": bool(result.terminated),
        "termination_status": _termination_status(int(result.returncode), bool(result.terminated)),
        "artifact_root": artifact_root,
        "artifact_dir": artifact_dir,
        "artifact_paths": artifact_paths,
        "breach_log": result.breach_log,
        "breadcrumbs": {
            "pod_id": pod_id,
            "name_prefix": name_prefix,
            "remote_root": remote_root,
            "upload_mode": upload_mode,
            "timeout": timeout,
        },
    }
    if payload["returncode"] != 0:
        diagnostics_dir = produces_dir / "diagnostics"
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        diagnostics_path = diagnostics_dir / "remote_exit.json"
        _write_json(
            diagnostics_path,
            {
                "returncode": payload["returncode"],
                "termination_status": payload["termination_status"],
                "stdout_tail": payload["stdout"][-4000:],
                "stderr_tail": payload["stderr"][-4000:],
                "artifact_dir": artifact_dir,
                "artifact_paths": artifact_paths,
                "breadcrumbs": payload["breadcrumbs"],
            },
        )
        payload["diagnostics_path"] = str(diagnostics_path)
    return payload


def _host_hf_token_env_vars() -> dict[str, str]:
    """Return pod env vars sourced from the host process without inventing defaults."""
    token = os.environ.get("HF_TOKEN")
    return {"HF_TOKEN": token} if token else {}


def _storage_required(args: argparse.Namespace) -> bool:
    value = os.environ.get("RUNPOD_REQUIRE_STORAGE", "")
    env_required = value.lower() in {"1", "true", "yes", "on"}
    return bool(getattr(args, "require_storage", False) or env_required)


def _preflight_storage(storage_name: str | None, *, required: bool, context: str) -> int:
    if not required and not storage_name:
        return 0

    from astrid.core.runpod.storage import require_existing_storage

    try:
        asyncio.run(require_existing_storage(storage_name, context=context))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def _build_pod_handle(
    *,
    pod: Any,
    ssh: dict[str, Any],
    name_prefix: str,
    terminate_at: str,
    gpu_type: Any,
    hourly_rate: float,
    provisioned_at: str,
    datacenter_id: str | None,
    image: str,
    container_disk_gb: int,
    volume_in_gb: int,
    network_volume_id: Any,
    ports: str | None,
) -> dict[str, Any]:
    return {
        "pod_id": pod.id,
        "ssh": f"root@{ssh['ip']} -p {ssh['port']}",
        "name": pod.name,
        "name_prefix": name_prefix,
        "terminate_at": terminate_at,
        "gpu_type": gpu_type,
        "hourly_rate": hourly_rate,
        "provisioned_at": provisioned_at,
        "config_snapshot": {
            "api_key_ref": "RUNPOD_API_KEY",
            "datacenter_id": datacenter_id,
            "image": image,
            "container_disk_in_gb": container_disk_gb,
            "volume_in_gb": volume_in_gb,
            "network_volume_id": network_volume_id,
            "ports": ports or "8888/http,22/tcp",
        },
    }


async def _terminate_pod_id(pod_id: str, config: Any, *, name: str | None = None) -> bool:
    from runpod_lifecycle import get_pod

    try:
        pod = await get_pod(pod_id, config, name=name)
        await pod.terminate()
        return True
    except Exception as exc:
        msg = str(exc).lower()
        if "not found" in msg or "404" in msg or "does not exist" in msg:
            return True
        print(f"WARNING: session teardown error: {exc}", file=sys.stderr)
        return False


def _ssh_target_from_handle(handle: dict[str, Any]) -> tuple[str, str]:
    """Return ``(user_host, port)`` from the persisted RunPod ssh field."""
    ssh = str(handle.get("ssh") or "")
    match = re.match(r"(\S+)\s+-p\s+(\d+)", ssh)
    if not match:
        raise ValueError(f"pod_handle ssh field is missing or invalid: {ssh!r}")
    return match.group(1), match.group(2)


def _build_scp_pull_command(
    handle: dict[str, Any],
    *,
    remote_path: str,
    local_dir: Path,
    ssh_key: str | None = None,
) -> list[str]:
    """Build the SCP command used by ``external.runpod.run pull``."""
    target, port = _ssh_target_from_handle(handle)
    cmd = [
        "scp",
        "-r",
        "-P",
        port,
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "IdentitiesOnly=yes",
    ]
    if ssh_key:
        cmd.extend(["-i", ssh_key])
    cmd.extend([f"{target}:{remote_path}", str(local_dir)])
    return cmd


# ---------------------------------------------------------------------------
# Shared helper: load pod_handle and rebuild config
# ---------------------------------------------------------------------------


def _load_handle_and_config(handle_path: Path) -> tuple[dict[str, Any], Any]:
    """Return ``(handle_dict, RunPodConfig)`` from a pod_handle.json path."""
    from runpod_lifecycle import RunPodConfig

    handle = json.loads(handle_path.read_text(encoding="utf-8"))
    api_key_ref = handle["config_snapshot"]["api_key_ref"]
    api_key = os.environ.get(api_key_ref)
    if not api_key:
        raise RuntimeError(
            f"API key env var {api_key_ref!r} is not set. "
            f"The pod_handle stores only the env var name, never the literal key."
        )

    snap = handle["config_snapshot"]
    config = RunPodConfig(
        api_key=api_key,
        gpu_type=handle.get("gpu_type", "NVIDIA GeForce RTX 4090"),
        container_disk_gb=snap.get("container_disk_in_gb", 200),
        storage_name=snap.get("network_volume_id"),
        ssh_public_key=os.environ.get("RUNPOD_SSH_PUBLIC_KEY"),
        ssh_private_key=os.environ.get("RUNPOD_SSH_PRIVATE_KEY"),
        ssh_public_key_path=os.environ.get("RUNPOD_SSH_PUBLIC_KEY_PATH"),
        ssh_private_key_path=os.environ.get("RUNPOD_SSH_PRIVATE_KEY_PATH"),
        env_vars=_host_hf_token_env_vars(),
    )
    return handle, config


# ---------------------------------------------------------------------------
# 1. provision
# ---------------------------------------------------------------------------


def cmd_provision(args: argparse.Namespace, produces_dir: Path) -> int:
    """Provision a RunPod GPU pod → pod_handle.json + cost.json."""
    from runpod_lifecycle import RunPodConfig, launch

    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        print("ERROR: RUNPOD_API_KEY environment variable is required", file=sys.stderr)
        return 1

    gpu_type = args.gpu_type or os.environ.get("RUNPOD_GPU_TYPE", "NVIDIA GeForce RTX 4090")
    if isinstance(gpu_type, str) and "," in gpu_type:
        gpu_type = [g.strip() for g in gpu_type.split(",") if g.strip()]
    name_prefix = args.name_prefix or os.environ.get("RUNPOD_NAME_PREFIX", "pod")
    image = args.image or os.environ.get("RUNPOD_WORKER_IMAGE", "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04")
    container_disk_gb = args.container_disk_gb or int(os.environ.get("RUNPOD_CONTAINER_DISK_GB", "200"))
    datacenter_id = args.datacenter_id or os.environ.get("RUNPOD_DATACENTER_ID")
    storage_name = args.storage_name or os.environ.get("RUNPOD_STORAGE_NAME")
    storage_required = _storage_required(args)
    max_runtime = args.max_runtime_seconds or int(os.environ.get("RUNPOD_MAX_RUNTIME_SECONDS", "7200"))
    ports = getattr(args, "ports", None) or os.environ.get("RUNPOD_PORTS")

    storage_rc = _preflight_storage(storage_name, required=storage_required, context="RunPod provision")
    if storage_rc:
        return storage_rc

    hourly_rate = _get_hourly_rate(api_key, gpu_type)
    provisioned_at = _utc_now_iso()
    t0 = time.monotonic()

    config = RunPodConfig(
        api_key=api_key,
        gpu_type=gpu_type,
        worker_image=image,
        container_disk_gb=container_disk_gb,
        storage_name=storage_name,
        name_prefix=name_prefix,
        ports=ports,
        ssh_public_key=os.environ.get("RUNPOD_SSH_PUBLIC_KEY"),
        ssh_private_key=os.environ.get("RUNPOD_SSH_PRIVATE_KEY"),
        ssh_public_key_path=os.environ.get("RUNPOD_SSH_PUBLIC_KEY_PATH"),
        ssh_private_key_path=os.environ.get("RUNPOD_SSH_PRIVATE_KEY_PATH"),
        env_vars=_host_hf_token_env_vars(),
    )

    async def _provision() -> tuple[Any, dict[str, Any]]:
        pod = await launch(config, name=f"{name_prefix}-{int(time.time())}")
        await pod.wait_ready(timeout=900)
        ssh = await pod._ensure_ssh_details()
        return pod, ssh

    try:
        pod, ssh = asyncio.run(_provision())
    except Exception as exc:
        print(f"ERROR: provision failed: {exc}", file=sys.stderr)
        return 2

    terminate_at_dt = datetime.now(timezone.utc).timestamp() + max_runtime
    terminate_at = datetime.fromtimestamp(terminate_at_dt, tz=timezone.utc).isoformat()

    handle = _build_pod_handle(
        pod=pod,
        ssh=ssh,
        name_prefix=name_prefix,
        terminate_at=terminate_at,
        gpu_type=gpu_type,
        hourly_rate=hourly_rate,
        provisioned_at=provisioned_at,
        datacenter_id=datacenter_id,
        image=image,
        container_disk_gb=container_disk_gb,
        volume_in_gb=config.disk_size_gb,
        network_volume_id=pod._storage_volume,
        ports=ports,
    )

    _write_json(produces_dir / "pod_handle.json", handle)

    duration = time.monotonic() - t0
    _write_cost_sidecar(produces_dir, duration_seconds=duration, hourly_rate=hourly_rate, basis_prefix="provision")

    ssh_str = handle["ssh"]
    print(f"Provisioned pod {pod.id} ({gpu_type}) — ssh: {ssh_str}")
    return 0


# ---------------------------------------------------------------------------
# 2. exec
# ---------------------------------------------------------------------------


def cmd_exec(args: argparse.Namespace, produces_dir: Path) -> int:
    """Reattach to a provisioned pod, ship + run + download → exec_result.json + cost.json."""
    pod_handle_path = Path(args.pod_handle) if args.pod_handle else produces_dir / "pod_handle.json"
    if not pod_handle_path.is_file():
        print(f"ERROR: pod_handle.json not found at {pod_handle_path}", file=sys.stderr)
        return 1

    handle, config = _load_handle_and_config(pod_handle_path)
    hourly_rate = handle["hourly_rate"]

    remote_root = args.remote_root or "/workspace"
    remote_script = args.remote_script or (produces_dir.parent / "remote_script.sh")
    local_root = Path(args.local_root) if args.local_root else Path.cwd()
    timeout = args.timeout or 3600
    upload_mode: Literal["sftp_walk", "tarball"] = (
        cast(Literal["sftp_walk", "tarball"], args.upload_mode)
        if args.upload_mode in ("sftp_walk", "tarball")
        else "sftp_walk"
    )
    excludes = set(args.excludes.split(",")) if args.excludes else set()

    # The remote script can be either a path to a file or an inline command.
    if not isinstance(remote_script, str):
        remote_script = str(remote_script)
    if Path(remote_script).is_file():
        remote_script = Path(remote_script).read_text(encoding="utf-8").strip()

    async def _exec() -> dict[str, Any]:
        from runpod_lifecycle import get_pod, ship_and_run_detached

        pod = await get_pod(handle["pod_id"], config, name=handle.get("name"))

        result = await ship_and_run_detached(
            remote_script=remote_script,
            pod=pod,
            local_root=local_root,
            remote_root=remote_root,
            exclude=excludes,
            upload_mode=upload_mode,
            timeout=timeout,
            name_prefix=handle["name_prefix"],
            terminate_after_exec=False,
            poll_interval=30,
        )
        return _detached_exec_result(
            result,
            produces_dir=produces_dir,
            pod_id=str(handle["pod_id"]),
            name_prefix=str(handle["name_prefix"]),
            remote_root=remote_root,
            upload_mode=upload_mode,
            timeout=timeout,
        )

    t0 = time.monotonic()
    try:
        result = asyncio.run(_exec())
    except Exception as exc:
        print(f"ERROR: exec failed: {exc}", file=sys.stderr)
        return 2

    duration = time.monotonic() - t0

    _write_json(produces_dir / "exec_result.json", result)
    _write_cost_sidecar(produces_dir, duration_seconds=duration, hourly_rate=hourly_rate, basis_prefix="exec")

    print(f"Exec complete: returncode={result['returncode']}, artifacts={result['artifact_dir']}")
    return int(result["returncode"])


# ---------------------------------------------------------------------------
# 3. pull artifacts
# ---------------------------------------------------------------------------


def cmd_pull(args: argparse.Namespace, produces_dir: Path) -> int:
    """Pull files or directories from a provisioned pod using the saved handle."""
    pod_handle_path = Path(args.pod_handle) if args.pod_handle else produces_dir / "pod_handle.json"
    if not pod_handle_path.is_file():
        print(f"ERROR: pod_handle.json not found at {pod_handle_path}", file=sys.stderr)
        return 1

    handle = json.loads(pod_handle_path.read_text(encoding="utf-8"))
    local_dir = Path(args.local_dir) if args.local_dir else produces_dir / "artifact_dir"
    local_dir.mkdir(parents=True, exist_ok=True)
    remote_paths = list(args.remote_path or [])
    if not remote_paths:
        print("ERROR: at least one --remote-path is required", file=sys.stderr)
        return 2

    artifacts: list[dict[str, Any]] = []
    for remote_path in remote_paths:
        cmd = _build_scp_pull_command(
            handle,
            remote_path=remote_path,
            local_dir=local_dir,
            ssh_key=args.ssh_key,
        )
        print(f"$ {' '.join(cmd)}", file=sys.stderr)
        rv = subprocess.run(cmd)
        local_path = local_dir if remote_path.rstrip().endswith("/.") else local_dir / Path(remote_path.rstrip("/")).name
        exists = local_path.exists()
        artifacts.append(
            {
                "remote_path": remote_path,
                "local_path": str(local_path),
                "exists": exists,
                "returncode": rv.returncode,
                "command": cmd,
            }
        )
        if rv.returncode != 0:
            _write_json(produces_dir / "artifact_pull.json", {"status": "failed", "artifacts": artifacts})
            print(f"ERROR: artifact pull failed for {remote_path} rc={rv.returncode}", file=sys.stderr)
            return rv.returncode or 3
        if not exists:
            _write_json(produces_dir / "artifact_pull.json", {"status": "missing_local", "artifacts": artifacts})
            print(f"ERROR: pulled artifact missing locally: {local_path}", file=sys.stderr)
            return 3

    _write_json(produces_dir / "artifact_pull.json", {"status": "ok", "artifacts": artifacts})
    print(f"Pulled {len(artifacts)} artifact(s) into {local_dir}")
    return 0


# ---------------------------------------------------------------------------
# 4. teardown
# ---------------------------------------------------------------------------


def cmd_teardown(args: argparse.Namespace, produces_dir: Path) -> int:
    """Terminate a pod by pod_handle. Idempotent — 'not found' is a no-op."""
    pod_handle_path = Path(args.pod_handle) if args.pod_handle else produces_dir / "pod_handle.json"
    if not pod_handle_path.is_file():
        print(f"ERROR: pod_handle.json not found at {pod_handle_path}", file=sys.stderr)
        return 1

    handle, config = _load_handle_and_config(pod_handle_path)
    hourly_rate = handle["hourly_rate"]

    t0 = time.monotonic()
    receipt: dict[str, Any] = {"pod_id": handle["pod_id"], "action": "terminate", "status": "unknown"}
    try:

        async def _teardown() -> None:
            from runpod_lifecycle import get_pod

            try:
                pod = await get_pod(handle["pod_id"], config, name=handle.get("name"))
                await pod.terminate()
            except Exception as exc:
                msg = str(exc).lower()
                if "not found" in msg or "404" in msg or "does not exist" in msg:
                    receipt["status"] = "already_gone"
                    receipt["reason"] = f"pod already terminated or not found: {exc}"
                    return
                raise

        asyncio.run(_teardown())
        if receipt["status"] == "unknown":
            receipt["status"] = "terminated"
    except Exception as exc:
        receipt["status"] = "error"
        receipt["reason"] = str(exc)
        print(f"ERROR: teardown failed: {exc}", file=sys.stderr)

    duration = time.monotonic() - t0

    receipt["terminated_at"] = _utc_now_iso()
    _write_json(produces_dir / "teardown_receipt.json", receipt)
    _write_cost_sidecar(produces_dir, duration_seconds=duration, hourly_rate=hourly_rate, basis_prefix="teardown")

    status = receipt["status"]
    if status == "terminated":
        print(f"Teardown: pod {handle['pod_id']} terminated")
    elif status == "already_gone":
        print(f"Teardown: pod {handle['pod_id']} already gone (idempotent no-op)")
    else:
        print(f"Teardown: pod {handle['pod_id']} — {status}: {receipt.get('reason', '')}")
    return 0 if status in ("terminated", "already_gone") else 1


# ---------------------------------------------------------------------------
# 5. session  (provision → exec → teardown with try/finally)
# ---------------------------------------------------------------------------


def cmd_session(args: argparse.Namespace, produces_dir: Path) -> int:
    """Composite session: provision → exec+download → finally terminate.

    Writes ``pod_handle.json`` immediately after provision so the sweeper
    can recover orphaned pods on crash.  Deletes the handle on graceful
    teardown.
    """
    from runpod_lifecycle import RunPodConfig, launch

    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        print("ERROR: RUNPOD_API_KEY environment variable is required", file=sys.stderr)
        return 1

    gpu_type = args.gpu_type or os.environ.get("RUNPOD_GPU_TYPE", "NVIDIA GeForce RTX 4090")
    if isinstance(gpu_type, str) and "," in gpu_type:
        gpu_type = [g.strip() for g in gpu_type.split(",") if g.strip()]
    name_prefix = args.name_prefix or os.environ.get("RUNPOD_NAME_PREFIX", "pod")
    image = args.image or os.environ.get("RUNPOD_WORKER_IMAGE", "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04")
    container_disk_gb = args.container_disk_gb or int(os.environ.get("RUNPOD_CONTAINER_DISK_GB", "200"))
    datacenter_id = args.datacenter_id or os.environ.get("RUNPOD_DATACENTER_ID")
    storage_name = args.storage_name or os.environ.get("RUNPOD_STORAGE_NAME")
    storage_required = _storage_required(args)
    max_runtime = args.max_runtime_seconds or int(os.environ.get("RUNPOD_MAX_RUNTIME_SECONDS", "7200"))
    ports = getattr(args, "ports", None) or os.environ.get("RUNPOD_PORTS")
    remote_root = args.remote_root or "/workspace"
    remote_script = args.remote_script or ""
    local_root = Path(args.local_root) if args.local_root else Path.cwd()
    timeout = args.timeout or 3600
    upload_mode: Literal["sftp_walk", "tarball"] = (
        cast(Literal["sftp_walk", "tarball"], args.upload_mode)
        if args.upload_mode in ("sftp_walk", "tarball")
        else "sftp_walk"
    )
    excludes = set(args.excludes.split(",")) if args.excludes else set()

    storage_rc = _preflight_storage(storage_name, required=storage_required, context="RunPod session")
    if storage_rc:
        return storage_rc

    hourly_rate = _get_hourly_rate(api_key, gpu_type)
    provisioned_at = _utc_now_iso()

    config = RunPodConfig(
        api_key=api_key,
        gpu_type=gpu_type,
        worker_image=image,
        container_disk_gb=container_disk_gb,
        storage_name=storage_name,
        name_prefix=name_prefix,
        ports=ports,
        ssh_public_key=os.environ.get("RUNPOD_SSH_PUBLIC_KEY"),
        ssh_private_key=os.environ.get("RUNPOD_SSH_PRIVATE_KEY"),
        ssh_public_key_path=os.environ.get("RUNPOD_SSH_PUBLIC_KEY_PATH"),
        ssh_private_key_path=os.environ.get("RUNPOD_SSH_PRIVATE_KEY_PATH"),
        env_vars=_host_hf_token_env_vars(),
    )

    t0 = time.monotonic()
    pod_id: str | None = None
    handle: dict[str, Any] | None = None
    handle_path = produces_dir / "pod_handle.json"
    exit_code = 99  # sentinel for crash-before-exec

    try:
        # ---- provision -------------------------------------------------
        async def _provision() -> tuple[Any, dict[str, Any]]:
            pod = await launch(config, name=f"{name_prefix}-{int(time.time())}")
            await pod.wait_ready(timeout=900)
            ssh = await pod._ensure_ssh_details()
            return pod, ssh

        pod, ssh = asyncio.run(_provision())
        pod_id = pod.id
        terminate_at_dt = datetime.now(timezone.utc).timestamp() + max_runtime
        terminate_at = datetime.fromtimestamp(terminate_at_dt, tz=timezone.utc).isoformat()

        handle = _build_pod_handle(
            pod=pod,
            ssh=ssh,
            name_prefix=name_prefix,
            terminate_at=terminate_at,
            gpu_type=gpu_type,
            hourly_rate=hourly_rate,
            provisioned_at=provisioned_at,
            datacenter_id=datacenter_id,
            image=image,
            container_disk_gb=container_disk_gb,
            volume_in_gb=config.disk_size_gb,
            network_volume_id=pod._storage_volume,
            ports=ports,
        )

        # *** Write pod_handle.json IMMEDIATELY (sweeper breadcrumb) ***
        _write_json(handle_path, handle)

        # ---- exec ------------------------------------------------------
        if remote_script:
            if Path(remote_script).is_file():
                remote_script = Path(remote_script).read_text(encoding="utf-8").strip()

            async def _exec() -> dict[str, Any]:
                from runpod_lifecycle import get_pod, ship_and_run_detached

                pod_handle = await get_pod(pod_id, config, name=handle.get("name"))  # type: ignore[arg-type]
                result = await ship_and_run_detached(
                    remote_script=remote_script,
                    pod=pod_handle,
                    local_root=local_root,
                    remote_root=remote_root,
                    exclude=excludes,
                    upload_mode=upload_mode,
                    timeout=timeout,
                    name_prefix=name_prefix,
                    terminate_after_exec=False,
                    poll_interval=30,
                )
                return _detached_exec_result(
                    result,
                    produces_dir=produces_dir,
                    pod_id=str(pod_id),
                    name_prefix=name_prefix,
                    remote_root=remote_root,
                    upload_mode=upload_mode,
                    timeout=timeout,
                )

            exec_result = asyncio.run(_exec())
            exit_code = exec_result["returncode"]

            _write_json(produces_dir / "exec_result.json", exec_result)
        else:
            # No script to execute — just an empty exec_result.
            exec_result = {
                "returncode": 0,
                "stdout": "",
                "stderr": "",
                "terminated": False,
                "termination_status": "completed",
                "artifact_root": None,
                "artifact_dir": str(produces_dir / "artifact_dir"),
                "artifact_paths": [],
                "breadcrumbs": {
                    "pod_id": pod_id,
                    "name_prefix": name_prefix,
                    "remote_root": remote_root,
                    "upload_mode": upload_mode,
                    "timeout": timeout,
                },
            }
            (produces_dir / "artifact_dir").mkdir(parents=True, exist_ok=True)
            _write_json(produces_dir / "exec_result.json", exec_result)
            exit_code = 0

        total_duration = time.monotonic() - t0
        _write_cost_sidecar(produces_dir, duration_seconds=total_duration, hourly_rate=hourly_rate, basis_prefix="session")

        return exit_code

    except Exception as exc:
        print(f"ERROR: session failed: {exc}", file=sys.stderr)
        total_duration = time.monotonic() - t0
        _write_cost_sidecar(produces_dir, duration_seconds=total_duration, hourly_rate=hourly_rate, basis_prefix="session (failed)")
        return 2

    finally:
        # ---- teardown (guaranteed) ------------------------------------
        if pod_id:
            teardown_ok = False
            try:
                teardown_ok = asyncio.run(
                    _terminate_pod_id(pod_id, config, name=handle.get("name") if handle else None)
                )
            except Exception as exc:
                print(f"WARNING: session teardown failed: {exc}", file=sys.stderr)
            if teardown_ok:
                try:
                    handle_path.unlink(missing_ok=True)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for all executor subcommands."""
    parser = argparse.ArgumentParser(description="RunPod executor commands.")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- provision ---
    p_prov = sub.add_parser("provision", help="Provision a RunPod GPU pod.")
    p_prov.add_argument("--produces-dir", type=Path, required=True, help="Produces output directory.")
    p_prov.add_argument("--gpu-type", help="GPU type (e.g. 'NVIDIA GeForce RTX 4090').")
    p_prov.add_argument("--storage-name", help="Network storage volume name.")
    p_prov.add_argument("--max-runtime-seconds", type=int, help="Maximum pod lifetime in seconds.")
    p_prov.add_argument("--name-prefix", help="Pod name prefix for grouping.")
    p_prov.add_argument("--image", help="Docker image for the pod.")
    p_prov.add_argument("--container-disk-gb", type=int, help="Container disk size in GB.")
    p_prov.add_argument("--datacenter-id", help="RunPod datacenter ID.")
    p_prov.add_argument("--ports", help="Comma-separated port spec for the pod (default: '8888/http,22/tcp').")
    p_prov.add_argument("--require-storage", action="store_true", help="Require --storage-name to resolve before launch.")

    # --- exec ---
    p_exec = sub.add_parser("exec", help="Execute a script on an existing pod.")
    p_exec.add_argument("--produces-dir", type=Path, required=True, help="Produces output directory.")
    p_exec.add_argument("--pod-handle", help="Path to pod_handle.json (default: <produces-dir>/pod_handle.json).")
    p_exec.add_argument("--local-root", help="Local directory to upload.")
    p_exec.add_argument("--remote-root", help="Remote path on the pod.")
    p_exec.add_argument("--remote-script", help="Script file path or inline command.")
    p_exec.add_argument("--timeout", type=int, help="Execution timeout in seconds.")
    p_exec.add_argument("--upload-mode", choices=("sftp_walk", "tarball"), help="Upload mode.")
    p_exec.add_argument("--excludes", help="Comma-separated glob patterns to exclude from upload.")

    # --- pull ---
    p_pull = sub.add_parser("pull", help="Pull artifacts from an existing pod.")
    p_pull.add_argument("--produces-dir", type=Path, required=True, help="Produces output directory.")
    p_pull.add_argument("--pod-handle", help="Path to pod_handle.json (default: <produces-dir>/pod_handle.json).")
    p_pull.add_argument("--remote-path", action="append", help="Remote file or directory to pull. Repeatable.")
    p_pull.add_argument("--local-dir", help="Local destination directory.")
    p_pull.add_argument("--ssh-key", help="Private SSH key path. Omit to use ssh-agent/default keys.")

    # --- teardown ---
    p_tear = sub.add_parser("teardown", help="Terminate a pod (idempotent).")
    p_tear.add_argument("--produces-dir", type=Path, required=True, help="Produces output directory.")
    p_tear.add_argument("--pod-handle", help="Path to pod_handle.json (default: <produces-dir>/pod_handle.json).")

    # --- session ---
    p_sess = sub.add_parser("session", help="Provision → exec → teardown composite session.")
    p_sess.add_argument("--produces-dir", type=Path, required=True, help="Produces output directory.")
    p_sess.add_argument("--gpu-type", help="GPU type.")
    p_sess.add_argument("--storage-name", help="Network storage volume name.")
    p_sess.add_argument("--max-runtime-seconds", type=int, help="Maximum pod lifetime in seconds.")
    p_sess.add_argument("--name-prefix", help="Pod name prefix for grouping.")
    p_sess.add_argument("--image", help="Docker image for the pod.")
    p_sess.add_argument("--container-disk-gb", type=int, help="Container disk size in GB.")
    p_sess.add_argument("--datacenter-id", help="RunPod datacenter ID.")
    p_sess.add_argument("--ports", help="Comma-separated port spec for the pod (default: '8888/http,22/tcp').")
    p_sess.add_argument("--require-storage", action="store_true", help="Require --storage-name to resolve before launch.")
    p_sess.add_argument("--local-root", help="Local directory to upload.")
    p_sess.add_argument("--remote-root", help="Remote path on the pod.")
    p_sess.add_argument("--remote-script", help="Script file path or inline command.")
    p_sess.add_argument("--timeout", type=int, help="Execution timeout in seconds.")
    p_sess.add_argument("--upload-mode", choices=("sftp_walk", "tarball"), help="Upload mode.")
    p_sess.add_argument("--excludes", help="Comma-separated glob patterns to exclude from upload.")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatch to the appropriate subcommand handler."""
    args = build_parser().parse_args(argv)

    produces_dir = Path(args.produces_dir)
    produces_dir.mkdir(parents=True, exist_ok=True)

    if args.command == "provision":
        return cmd_provision(args, produces_dir)
    elif args.command == "exec":
        return cmd_exec(args, produces_dir)
    elif args.command == "pull":
        return cmd_pull(args, produces_dir)
    elif args.command == "teardown":
        return cmd_teardown(args, produces_dir)
    elif args.command == "session":
        return cmd_session(args, produces_dir)
    else:
        print(f"ERROR: unknown command {args.command!r}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
