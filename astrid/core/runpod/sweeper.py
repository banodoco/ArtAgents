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
from astrid.core.session.writer import writer_context_for_project
from astrid.core.util.time import utc_now_iso

logger = logging.getLogger(__name__)

POD_HANDLE_FILENAME = "pod_handle.json"
RUNPOD_SWEEPER_AUDIT_FILENAME = "runpod_sweeper_audit.jsonl"


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601."""
    return utc_now_iso()


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


def _append_hard_sweep_audit(
    projects_root: Path,
    *,
    handle_path: Path,
    run_dir: Path,
    event: dict[str, Any],
) -> None:
    """Record hard-mode sweeps in a non-task audit ledger.

    Hard mode is allowed to bypass live-session/idle policy for pod cleanup,
    but it must not bypass task-run writer authentication. The audit file sits
    at the projects root rather than in ``runs/<id>/events.jsonl`` so it cannot
    be mistaken for a task-run mutation.
    """

    audit_event = {
        **event,
        "task_event": False,
        "run_dir": str(run_dir),
        "handle_path": str(handle_path),
    }
    audit_path = projects_root / RUNPOD_SWEEPER_AUDIT_FILENAME
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_event, sort_keys=True, separators=(",", ":")) + "\n")


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
        ``terminate_at`` passed. Hard-mode observations are written to the
        projects-root sweeper audit log, not the task-run event ledger.
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
            epoch = lease["writer_epoch"]
            if attached and isinstance(epoch, int) and epoch > 0:
                detail["reason"] = f"live session {attached!r} (writer_epoch={epoch}) — skipping"
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
        default_writer = None
        if mode == "default" and not dry_run:
            try:
                slug = run_dir.parent.parent.name
                with writer_context_for_project(slug, root=projects_root) as writer:
                    default_writer = writer
            except Exception as exc:
                detail["reason"] = f"writer auth failed before termination: {exc}"
                summary["errors"] += 1
                summary["details"].append(detail)
                continue

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
            "ts": _utc_now_iso(),
        }

        if mode == "default":
            try:
                assert default_writer is not None
                default_writer.append(event)
            except Exception as exc:
                detail["reason"] = f"terminated but event append failed: {exc}"
                summary["errors"] += 1
                summary["details"].append(detail)
                continue
        else:
            try:
                _append_hard_sweep_audit(
                    projects_root,
                    handle_path=handle_path,
                    run_dir=run_dir,
                    event=event,
                )
            except Exception as exc:
                detail["reason"] = f"terminated but hard-mode audit append failed: {exc}"
                summary["errors"] += 1
                summary["details"].append(detail)
                continue

        detail["action"] = "terminated"
        detail["reason"] = f"terminated ({mode}-mode)"
        summary["terminated"] += 1
        summary["details"].append(detail)

    return summary
