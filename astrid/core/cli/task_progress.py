"""Durable task observation and copy-pasteable CLI handoff helpers.

The workspace runtime remains the sole task authority.  This module only
polls ``client.tasks.show`` and turns changes in that read model into a quiet,
operator-friendly progress stream.
"""

from __future__ import annotations

import shlex
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any, TextIO

from astrid.sdk.contracts import DomainResult, ErrorObject

_SUCCESS_STATES = frozenset({"completed", "succeeded"})
_FAILURE_STATES = frozenset({"cancelled", "canceled", "expired", "failed"})
_TERMINAL_STATES = _SUCCESS_STATES | _FAILURE_STATES
_KEEPALIVE_SECONDS = 30.0


def task_handoff(*, project: str, task_id: str, run_id: str | None) -> dict[str, str]:
    """Return shell-safe commands for observing a task and opening its run."""
    prefix = ["python3", "-m", "astrid"]
    handoff = {
        "follow": shlex.join(prefix + ["tasks", "follow", task_id, "--project", project]),
        "inspect": shlex.join(prefix + ["tasks", "show", task_id, "--project", project, "--json"]),
        "events": shlex.join(prefix + ["tasks", "events", task_id, "--project", project, "--json"]),
        "recent": shlex.join(prefix + ["tasks", "list", "--project", project, "--json"]),
    }
    if run_id:
        handoff["open"] = shlex.join(
            prefix + ["runs", "open", run_id, "--project", project]
        )
    return handoff


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _whole_seconds(value: float) -> int:
    return max(0, int(value))


def _duration(value: int | None) -> str:
    if value is None:
        return "unknown"
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _waiting_reason(task: Mapping[str, Any], state: str) -> str | None:
    for key in ("waiting_reason", "blocked_reason"):
        value = task.get(key)
        if isinstance(value, str) and value:
            return value
    if state in {"queued", "ready", "retrying"} and not task.get("attempt_id"):
        # Older generated clients omit the runtime's more specific optional
        # reason.  Keep the status truthful without pretending to know which
        # resource or executor is responsible.
        return "awaiting_execution"
    if state == "cancel_requested":
        return "cancellation_requested"
    return None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if value >= 0 else None


def _progress_view(task: Mapping[str, Any], state: str) -> dict[str, Any]:
    """Expose reported progress and calculate only dimensionally sound values."""
    raw_progress = task.get("progress")
    if not isinstance(raw_progress, Mapping):
        result = task.get("result")
        raw_progress = result.get("progress") if isinstance(result, Mapping) else None
    progress = dict(raw_progress) if isinstance(raw_progress, Mapping) else {}

    phase = task.get("phase") or progress.get("phase")
    phase = str(phase) if isinstance(phase, str) and phase else state

    queue_position = task.get("queue_position", progress.get("queue_position"))
    queue_position = int(queue_position) if isinstance(queue_position, int) and queue_position >= 0 else None
    queue_reason = None if queue_position is not None else "runtime did not report queue position"

    completed = _number(
        progress.get("completed_units", progress.get("completed", progress.get("done")))
    )
    total = _number(progress.get("total_units", progress.get("total")))
    explicit_percent = _number(progress.get("percent", progress.get("percentage")))
    if explicit_percent is not None:
        percent = min(100.0, explicit_percent)
        progress_source = "runtime"
    elif completed is not None and total is not None and total > 0 and completed <= total:
        percent = completed * 100.0 / total
        progress_source = "completed/total"
    else:
        percent = None
        progress_source = None
    progress_reason = (
        None if percent is not None else "runtime did not report completed and total work"
    )

    raw_speed = progress.get("current_speed", progress.get("speed", progress.get("rate")))
    speed_unit = progress.get("speed_unit", progress.get("rate_unit"))
    if isinstance(raw_speed, Mapping):
        speed_unit = raw_speed.get("unit", speed_unit)
        raw_speed = raw_speed.get("value")
    speed = _number(raw_speed)
    if speed == 0:
        speed = None
    speed_unit = str(speed_unit) if isinstance(speed_unit, str) and speed_unit else "units/s"
    speed_reason = None if speed is not None else "runtime did not report current speed"

    eta = _number(progress.get("eta_seconds"))
    eta_source = "runtime" if eta is not None else None
    if (
        eta is None
        and completed is not None
        and total is not None
        and completed <= total
        and speed is not None
        and speed_unit in {"units/s", "unit/s", "items/s", "item/s"}
    ):
        eta = (total - completed) / speed
        eta_source = "remaining/current_speed"
    if eta is not None:
        eta_reason = None
    elif state in _TERMINAL_STATES:
        eta_reason = "task is terminal"
    elif state in {"queued", "ready", "retrying"}:
        eta_reason = "task has not reported processing speed"
    else:
        eta_reason = "runtime did not report compatible remaining work and speed"

    return {
        "phase": phase,
        "queue_position": queue_position,
        "queue_position_unavailable_reason": queue_reason,
        "progress_percent": round(percent, 2) if percent is not None else None,
        "progress_source": progress_source,
        "progress_unavailable_reason": progress_reason,
        "completed_units": completed,
        "total_units": total,
        "current_speed": speed,
        "speed_unit": speed_unit if speed is not None else None,
        "speed_unavailable_reason": speed_reason,
        "eta_seconds": _whole_seconds(eta) if eta is not None else None,
        "eta_source": eta_source,
        "eta_unavailable_reason": eta_reason,
    }


def _settled_outputs(task: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = task.get("result")
    raw = result.get("outputs") if isinstance(result, Mapping) else None
    if not isinstance(raw, list):
        return []
    outputs: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, Mapping):
            row = dict(item)
            location = next(
                (
                    row.get(key)
                    for key in ("url", "download_url", "path", "file", "locator", "object_id")
                    if isinstance(row.get(key), str) and row.get(key)
                ),
                None,
            )
            outputs.append({"location": location, "resource": row})
        elif isinstance(item, str):
            outputs.append({"location": item, "resource": item})
    return outputs


def task_observation(
    task: Mapping[str, Any],
    *,
    kind: str,
    followed_for_seconds: float,
    now: datetime,
) -> dict[str, Any]:
    """Build one JSON-safe observation from the durable task read model."""
    state = str(task.get("state") or task.get("status") or "unknown").lower()
    created_at = _parse_timestamp(task.get("created_at"))
    heartbeat_at = None
    heartbeat_source = None
    for key in ("last_heartbeat_at", "heartbeat_at", "updated_at"):
        heartbeat_at = _parse_timestamp(task.get(key))
        if heartbeat_at is not None:
            heartbeat_source = key
            break
    elapsed = (
        _whole_seconds((now - created_at).total_seconds())
        if created_at is not None
        else _whole_seconds(followed_for_seconds)
    )
    heartbeat_age = (
        _whole_seconds((now - heartbeat_at).total_seconds())
        if heartbeat_at is not None
        else None
    )
    attempt_id = task.get("attempt_id")
    attempt_id = str(attempt_id) if attempt_id not in (None, "") else None
    attempt_number = task.get("attempt")
    if not isinstance(attempt_number, int):
        version = task.get("version")
        attempt_number = max(0, version - 1) if isinstance(version, int) else None
    observation = {
        "kind": kind,
        "task_id": str(task.get("task_id") or task.get("id") or ""),
        "run_id": str(task.get("run_id") or "") or None,
        "state": state,
        "terminal": state in _TERMINAL_STATES,
        "elapsed_seconds": elapsed,
        "heartbeat_age_seconds": heartbeat_age,
        "heartbeat_at": heartbeat_at.isoformat().replace("+00:00", "Z")
        if heartbeat_at is not None
        else None,
        "heartbeat_source": heartbeat_source,
        "attempt_id": attempt_id,
        "attempt_number": attempt_number,
        "waiting_reason": _waiting_reason(task, state),
        "version": task.get("version"),
        "updated_at": task.get("updated_at"),
    }
    observation.update(_progress_view(task, state))
    return observation


def render_observation(observation: Mapping[str, Any]) -> str:
    """Render one compact progress line with no volatile decoration."""
    elapsed = _duration(observation.get("elapsed_seconds"))
    heartbeat_age = observation.get("heartbeat_age_seconds")
    heartbeat = (
        f"{_duration(heartbeat_age)} ago" if isinstance(heartbeat_age, int) else "unknown"
    )
    attempt = observation.get("attempt_id") or "-"
    waiting = observation.get("waiting_reason") or "-"
    queue_position = observation.get("queue_position")
    queue = str(queue_position) if isinstance(queue_position, int) else "unavailable"
    progress_percent = observation.get("progress_percent")
    progress = f"{progress_percent:g}%" if isinstance(progress_percent, (int, float)) else "unavailable"
    speed = observation.get("current_speed")
    speed_text = (
        f"{speed:g} {observation.get('speed_unit')}" if isinstance(speed, (int, float)) else "unavailable"
    )
    eta_seconds = observation.get("eta_seconds")
    eta = _duration(eta_seconds) if isinstance(eta_seconds, int) else "unavailable"
    unavailable: list[str] = []
    for label, key in (
        ("queue", "queue_position_unavailable_reason"),
        ("progress", "progress_unavailable_reason"),
        ("speed", "speed_unavailable_reason"),
        ("eta", "eta_unavailable_reason"),
    ):
        reason = observation.get(key)
        if isinstance(reason, str) and reason:
            unavailable.append(f"{label}: {reason}")
    line = (
        f"[{elapsed}] {observation.get('state', 'unknown')}"
        f"  phase={observation.get('phase', 'unknown')}  queue={queue}"
        f"  progress={progress}  speed={speed_text}  eta={eta}"
        f"  heartbeat={heartbeat}  attempt={attempt}  waiting={waiting}"
    )
    return line + (f"\n  unavailable: {'; '.join(unavailable)}" if unavailable else "")


def _change_signature(task: Mapping[str, Any]) -> tuple[Any, ...]:
    """Fields whose durable changes deserve a progress line."""
    return (
        task.get("state") or task.get("status"),
        task.get("version"),
        task.get("attempt_id"),
        task.get("waiting_reason") or task.get("blocked_reason"),
        task.get("last_heartbeat_at") or task.get("heartbeat_at") or task.get("updated_at"),
    )


def follow_task(
    client: Any,
    task_id: str,
    *,
    project: str,
    poll_seconds: float,
    timeout_seconds: float,
    stream: TextIO | None = None,
    collect_observations: bool = True,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    utcnow: Callable[[], datetime] | None = None,
) -> DomainResult[Any]:
    """Poll one task until terminal state or timeout.

    ``stream`` receives the initial observation, durable changes, and a quiet
    keepalive at most every 30 seconds.  JSON callers pass no stream and get a
    single final product envelope containing those observations.
    """
    now_utc = utcnow or (lambda: datetime.now(timezone.utc))
    started = monotonic()
    deadline = started + timeout_seconds
    last_signature: tuple[Any, ...] | None = None
    last_emitted = started - _KEEPALIVE_SECONDS
    observations: list[dict[str, Any]] = []

    while True:
        result = client.tasks.show(task_id)
        if not isinstance(result, DomainResult):
            try:
                result = DomainResult.from_dict(result)
            except (TypeError, ValueError):
                return DomainResult.failure(
                    ErrorObject(
                        code="protocol_error",
                        message="runtime task status returned an invalid result",
                        details={"task_id": task_id, "project": project},
                    )
                )
        if not result.ok:
            return result
        if not isinstance(result.data, Mapping):
            return DomainResult.failure(
                ErrorObject(
                    code="protocol_error",
                    message="runtime task status returned an invalid task resource",
                    details={"task_id": task_id, "project": project},
                )
            )

        task = dict(result.data)
        current = monotonic()
        signature = _change_signature(task)
        changed = signature != last_signature
        keepalive = current - last_emitted >= _KEEPALIVE_SECONDS
        state = str(task.get("state") or task.get("status") or "unknown").lower()
        if changed or keepalive or state in _TERMINAL_STATES:
            kind = "observed" if last_signature is None else ("changed" if changed else "heartbeat")
            observation = task_observation(
                task,
                kind=kind,
                followed_for_seconds=current - started,
                now=now_utc(),
            )
            if collect_observations:
                observations.append(observation)
            if stream is not None:
                print(render_observation(observation), file=stream, flush=True)
            last_emitted = current
        last_signature = signature

        if state in _TERMINAL_STATES:
            run_id = str(task.get("run_id") or "") or None
            summary = {
                "project": project,
                "task_id": str(task.get("task_id") or task.get("id") or task_id),
                "run_id": run_id,
                "state": state,
                "terminal": True,
                "task": task,
                "outputs": _settled_outputs(task),
                "handoff": task_handoff(project=project, task_id=task_id, run_id=run_id),
                "observations": observations,
            }
            if state in _SUCCESS_STATES:
                return DomainResult.success(summary)
            return DomainResult.failure(
                ErrorObject(
                    code=f"task_{state}",
                    message=f"task reached terminal state {state}",
                    details=summary,
                )
            )

        remaining = deadline - current
        if remaining <= 0:
            latest = task_observation(
                task,
                kind="timeout",
                followed_for_seconds=current - started,
                now=now_utc(),
            )
            return DomainResult.failure(
                ErrorObject(
                    code="task_follow_timeout",
                    message="task did not reach a terminal state before the follow timeout",
                    details={
                        "project": project,
                        "task_id": task_id,
                        "timeout_seconds": timeout_seconds,
                        "latest": latest,
                        "observations": observations,
                    },
                )
            )
        sleep(min(poll_seconds, remaining))


__all__ = [
    "follow_task",
    "render_observation",
    "task_handoff",
    "task_observation",
]
