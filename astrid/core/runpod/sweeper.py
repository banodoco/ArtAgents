"""RunPod sweeper — safety net for orphaned GPU pods."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from astrid.core.session.lease import LeaseError, read_lease
from astrid.core.task.events import ZERO_HASH, StaleTailError, append_event_locked, read_events
from astrid.core.util.time import utc_now_iso

logger = logging.getLogger(__name__)

POD_HANDLE_FILENAME = "pod_handle.json"
SWEEPER_EVENT_APPEND_RETRIES = 3
RUNPOD_SWEEPER_AUDIT_FILENAME = "runpod_sweeper_audit.jsonl"


def collect_handles(projects_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Walk *projects_root* and return every ``(path, handle_dict)`` pair.

    Scans: ``<project>/runs/<run>/steps/<step>/v<N>/**/produces/pod_handle.json``.
    """
    results: list[tuple[Path, dict[str, Any]]] = []
    if not projects_root.is_dir():
        return results

    for project_dir in sorted(projects_root.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue
        runs_dir = project_dir / "runs"
        if not runs_dir.is_dir():
            continue
        for run_dir in sorted(runs_dir.iterdir()):
            if not run_dir.is_dir() or run_dir.name.startswith("."):
                continue
            steps_dir = run_dir / "steps"
            if not steps_dir.is_dir():
                continue
            # Globs: steps/<step-id>/v<N>/produces/pod_handle.json
            # and:    steps/<step-id>/v<N>/iterations/NNN/produces/pod_handle.json
            for handle_path in sorted(steps_dir.rglob(f"*/v*/**/{POD_HANDLE_FILENAME}")):
                if not handle_path.is_file():
                    continue
                try:
                    handle = json.loads(handle_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as exc:
                    logger.warning("Could not parse %s: %s", handle_path, exc)
                    continue
                if isinstance(handle, dict) and "pod_id" in handle:
                    results.append((handle_path, handle))
    return results


def _derive_run_dir(handle_path: Path, projects_root: Path) -> Path | None:
    """Derive the owning run directory from a pod_handle.json path.

    The path is: ``<project>/runs/<run-id>/steps/.../produces/pod_handle.json``.
    We extract the first three components relative to *projects_root*
    to build the run directory.
    """
    try:
        rel = handle_path.resolve().relative_to(projects_root.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 3:
        return None
    # parts[0] = project, parts[1] = "runs", parts[2] = run-id
    run_dir = projects_root / parts[0] / "runs" / parts[2]
    return run_dir if run_dir.is_dir() else None


def _tail_hash(run_dir: Path) -> str:
    events_path = run_dir / "events.jsonl"
    if not events_path.exists():
        return ZERO_HASH
    events = read_events(events_path)
    if not events:
        return ZERO_HASH
    tail = events[-1].get("hash")
    return str(tail) if isinstance(tail, str) and tail else ZERO_HASH


def _handle_path_belongs_to_run(run_dir: Path, handle_path: Path) -> bool:
    try:
        rel = handle_path.resolve().relative_to(run_dir.resolve())
    except ValueError:
        return False
    parts = rel.parts
    return (
        len(parts) >= 5
        and parts[0] == "steps"
        and parts[-2] == "produces"
        and parts[-1] == POD_HANDLE_FILENAME
    )


def _append_sweep_audit(projects_root: Path, record: dict[str, Any]) -> None:
    """Append a supplemental, non-task audit line for operator sweep summaries."""
    audit_path = projects_root / RUNPOD_SWEEPER_AUDIT_FILENAME
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def append_runpod_sweeper_event(
    run_dir: Path,
    payload: dict[str, Any],
    *,
    max_retries: int = SWEEPER_EVENT_APPEND_RETRIES,
) -> dict[str, Any]:
    """Append the sole sweeper-owned task event without a bound writer session."""
    if payload.get("kind") != "pod_terminated_by_sweep":
        raise ValueError("RunPod sweeper may only append pod_terminated_by_sweep events")

    handle_path_value = payload.get("handle_path")
    if not isinstance(handle_path_value, str) or not handle_path_value:
        raise ValueError("RunPod sweeper event payload requires handle_path")
    if not _handle_path_belongs_to_run(run_dir, Path(handle_path_value)):
        raise ValueError("RunPod sweeper handle_path does not belong to run_dir")

    read_lease(run_dir)
    event = dict(payload)

    attempts = max(1, max_retries)
    last_error: StaleTailError | None = None
    for _ in range(attempts):
        try:
            return append_event_locked(
                run_dir,
                event,
                expected_writer_epoch=None,
                expected_prev_hash=_tail_hash(run_dir),
            )
        except StaleTailError as exc:
            last_error = exc
            continue
    if last_error is None:
        raise RuntimeError("RunPod sweeper append exhausted retries without recording a stale-tail error")
    raise last_error


def _rebuild_config(handle: dict[str, Any]) -> Any:
    """Reconstruct a ``RunPodConfig`` from a pod_handle dict."""
    from runpod_lifecycle import RunPodConfig

    snap = handle.get("config_snapshot", {})
    api_key_ref = snap.get("api_key_ref", "RUNPOD_API_KEY")
    api_key = os.environ.get(api_key_ref)
    if not api_key:
        raise RuntimeError(
            f"API key env var {api_key_ref!r} is not set. "
            f"The pod_handle stores only the env var name, never the literal key."
        )

    return RunPodConfig(
        api_key=api_key,
        gpu_type=handle.get("gpu_type", ""),
        worker_image=snap.get("image", ""),
        container_disk_gb=snap.get("container_disk_in_gb", 200),
    )


def sweep(
    projects_root: Path,
    mode: Literal["default", "hard"] = "default",
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the pod sweeper across *projects_root*.

    Parameters
    ----------
    projects_root:
        Path to the ``astrid-projects/`` directory.
    mode:
        ``"default"`` — safe: only terminate pods whose ``terminate_at`` has
        passed, the owning run has no live session, and the pod is idle.
        ``"hard"`` — bypass live-session and idle checks; still requires
        ``terminate_at`` passed and a canonical handle path owned by a run.
    dry_run:
        When ``True``, report what *would* be terminated but do not
        actually call the RunPod API.

    Returns a summary dict: ``{total, terminated, skipped, errors, details}``.
    """
    return asyncio.run(_sweep_async(projects_root, mode, dry_run=dry_run))


async def _sweep_async(
    projects_root: Path,
    mode: Literal["default", "hard"],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    from runpod_lifecycle import discovery, Pod

    handles = collect_handles(projects_root)
    now_utc = datetime.now(timezone.utc)

    summary: dict[str, Any] = {
        "total": len(handles),
        "terminated": 0,
        "skipped": 0,
        "errors": 0,
        "details": [],
    }

    for handle_path, handle in handles:
        pod_id = handle.get("pod_id", "")
        terminate_at_str = handle.get("terminate_at", "")
        name_prefix = handle.get("name_prefix", "")
        detail: dict[str, Any] = {
            "pod_id": pod_id,
            "handle_path": str(handle_path),
            "action": "skip",
            "reason": "",
            "event_append_status": "not_attempted",
        }

        # 1. Check terminate_at
        if not terminate_at_str:
            detail["reason"] = "missing terminate_at in handle"
            summary["skipped"] += 1
            summary["details"].append(detail)
            continue

        try:
            terminate_at = datetime.fromisoformat(terminate_at_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            detail["reason"] = f"unparseable terminate_at: {terminate_at_str!r}"
            summary["skipped"] += 1
            summary["details"].append(detail)
            continue

        if terminate_at > now_utc:
            detail["reason"] = f"terminate_at not yet passed ({terminate_at_str} > now)"
            summary["skipped"] += 1
            summary["details"].append(detail)
            continue

        # 2. Derive run dir
        run_dir = _derive_run_dir(handle_path, projects_root)
        if run_dir is None:
            detail["reason"] = "could not derive run directory from handle path"
            summary["errors"] += 1
            summary["details"].append(detail)
            continue
        if not _handle_path_belongs_to_run(run_dir, handle_path):
            detail["reason"] = "handle path is not a canonical owned pod_handle.json"
            summary["errors"] += 1
            summary["details"].append(detail)
            continue

        # 3. Canonical lease validation. Even hard mode only bypasses the
        # live-writer/idle policy; it must not append into a run whose lease
        # state is missing or malformed.
        try:
            lease = read_lease(run_dir)
        except LeaseError as exc:
            detail["reason"] = f"failed to read lease: {exc}"
            summary["errors"] += 1
            summary["details"].append(detail)
            continue

        # 4. Default-mode checks
        if mode == "default":
            attached = lease.get("attached_session_id")
            if attached:
                detail["reason"] = (
                    f"live session {attached!r} "
                    f"(writer_epoch={lease['writer_epoch']}) - skipping"
                )
                summary["skipped"] += 1
                summary["details"].append(detail)
                continue

            # 4b. Pod idle check
            try:
                config = _rebuild_config(handle)
                pod: Pod = await discovery.get_pod(pod_id, config, name=handle.get("name"))
                idle = await pod.is_idle(threshold_seconds=300)
            except Exception as exc:
                # If the pod is already gone, that's fine — proceed to terminate.
                err_msg = str(exc)
                if "not found" in err_msg.lower() or "launchfailure" in type(exc).__name__.lower():
                    idle = True
                else:
                    detail["reason"] = f"could not check pod idle: {exc}"
                    summary["errors"] += 1
                    summary["details"].append(detail)
                    continue

            if not idle:
                detail["reason"] = "pod is not idle (active exec or recent activity)"
                summary["skipped"] += 1
                summary["details"].append(detail)
                continue

        # 4. Terminate the pod
        if dry_run:
            detail["action"] = "would_terminate"
            detail["reason"] = "dry-run: would terminate"
            summary["terminated"] += 1
            summary["details"].append(detail)
            continue

        api_key = os.environ.get(
            handle.get("config_snapshot", {}).get("api_key_ref", "RUNPOD_API_KEY",)
        )
        if not api_key:
            detail["reason"] = "API key not available"
            summary["errors"] += 1
            summary["details"].append(detail)
            continue

        try:
            await discovery.terminate(pod_id, api_key)
        except Exception as exc:
            err_msg = str(exc)
            if "not found" in err_msg.lower():
                # Already terminated — still emit the event.
                pass
            else:
                detail["reason"] = f"terminate failed: {exc}"
                summary["errors"] += 1
                summary["details"].append(detail)
                continue

        # 5. Append pod_terminated_by_sweep event
        event = {
            "kind": "pod_terminated_by_sweep",
            "pod_id": pod_id,
            "terminate_at": terminate_at_str,
            "mode": mode,
            "reason": f"sweeper {mode}-mode: pod {pod_id} terminated",
            "ts": utc_now_iso(),
            "handle_path": str(handle_path),
        }

        try:
            stored_event = append_runpod_sweeper_event(run_dir, event)
        except Exception as exc:
            detail["reason"] = f"terminated but event append failed: {exc}"
            detail["event_append_status"] = "failed"
            _append_sweep_audit(
                projects_root,
                {
                    "ts": utc_now_iso(),
                    "task_event": False,
                    "run_dir": str(run_dir),
                    "handle_path": str(handle_path),
                    "pod_id": pod_id,
                    "mode": mode,
                    "action": "terminated",
                    "event_append_status": "failed",
                    "event_append_error": str(exc),
                },
            )
            summary["errors"] += 1
            summary["details"].append(detail)
            continue

        detail["action"] = "terminated"
        detail["reason"] = f"terminated ({mode}-mode)"
        detail["event_append_status"] = "appended"
        event_hash = stored_event.get("hash")
        if isinstance(event_hash, str):
            detail["event_hash"] = event_hash
        _append_sweep_audit(
            projects_root,
            {
                "ts": utc_now_iso(),
                "task_event": False,
                "run_dir": str(run_dir),
                "handle_path": str(handle_path),
                "pod_id": pod_id,
                "mode": mode,
                "action": "terminated",
                "event_append_status": "appended",
                "event_hash": event_hash,
            },
        )
        summary["terminated"] += 1
        summary["details"].append(detail)

    event_append_counts: dict[str, int] = {}
    for detail in summary["details"]:
        status = str(detail.get("event_append_status", "not_attempted"))
        event_append_counts[status] = event_append_counts.get(status, 0) + 1
    summary["event_append"] = event_append_counts
    return summary
