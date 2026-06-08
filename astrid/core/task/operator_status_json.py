"""Task operator status JSON building.

Extracted from ``operator_view.py`` (M4 T58) to keep both modules under the
1,200-line threshold.  This module owns the ``cmd_status --json`` payload
construction plus the inline-failure helpers used by both ``_status_json``
and the human-readable diagnostics path.

``operator_view.py`` re-imports every public name from here so existing
callers (``cmd_status``, ``_dispatch_from_tail``) and test monkeypatch seams
continue to work through the ``astrid.core.task.operator_view`` namespace.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from astrid.core.contracts.run_status import RunStatus, STEP_TERMINAL_KINDS
from astrid.core.task.cli_contract import emit_lifecycle_json
from astrid.core.task.inbox import pending_count
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    is_attested_kind,
    is_group_step,
)

_PROGRESS_TERMINAL_KINDS = STEP_TERMINAL_KINDS


@dataclass(frozen=True)
class _InlineFailureTail:
    name: str | None
    reason: str
    path: tuple[str, ...]


def _path_tuple_from_event(ev: dict[str, Any]) -> tuple[str, ...]:
    path_raw = ev.get("plan_step_path")
    if isinstance(path_raw, list):
        return tuple(str(p) for p in path_raw)
    plan_step_id = ev.get("plan_step_id")
    if isinstance(plan_step_id, str) and plan_step_id:
        return tuple(plan_step_id.split(STEP_PATH_SEP))
    return ()


def _inline_failure_tail(events: Sequence[dict[str, Any]]) -> _InlineFailureTail | None:
    """Return inline-check detail for tails that rewind a just-finalized step."""
    if len(events) < 2:
        return None
    last = events[-1] if isinstance(events[-1], dict) else None
    prior = events[-2] if isinstance(events[-2], dict) else None
    if last is None or prior is None:
        return None
    if last.get("kind") not in {"cursor_rewind", "iteration_failed"}:
        return None
    if prior.get("kind") != "produces_check_failed":
        return None
    raw_reason = prior.get("reason") or last.get("reason") or "produces check failed"
    raw_name = prior.get("produces")
    if not isinstance(raw_name, str):
        raw_name = prior.get("name") if isinstance(prior.get("name"), str) else None
    return _InlineFailureTail(
        name=raw_name,
        reason=str(raw_reason),
        path=_path_tuple_from_event(last) or _path_tuple_from_event(prior),
    )


def _format_inline_failure_tail(detail: _InlineFailureTail) -> str:
    if detail.name:
        return f"{detail.name}: {detail.reason}"
    return detail.reason


def _status_json(
    *,
    slug: str,
    run_id: str,
    plan,
    events: Sequence[dict],
    peek,
    claims: dict[str, str],
    completed: int,
    total: int,
    proj_root: Path,
) -> int:
    """Emit the ``cmd_status --json`` payload via the shared lifecycle helper."""
    run_state = RunStatus.from_run_events(events).value
    payload: dict[str, Any] = {
        "progress_completed": completed,
        "progress_total": total,
        "current_step": None,
        "current_step_kind": None,
        "current_step_version": None,
        "current_step_iteration": None,
        "current_step_item_id": None,
        "inbox_pending": pending_count(proj_root / "runs" / run_id),
    }
    if not (peek.exhausted or peek.step is None):
        path_str = STEP_PATH_SEP.join(peek.path_tuple)
        payload["current_step"] = path_str
        payload["current_step_kind"] = (
            "nested" if is_group_step(peek.step)
            else "attested" if is_attested_kind(peek.step)
            else "code"
        )
        payload["current_step_version"] = peek.step.version
        payload["current_step_iteration"] = peek.iteration
        payload["current_step_item_id"] = peek.item_id
        claimed_identity = claims.get(path_str)
        if peek.step.assignee != "system" or claimed_identity is not None:
            payload["owner_assignee"] = getattr(peek.step, "assignee", "system")
            payload["owner_claimed"] = claimed_identity

    # Mirror the same diagnostics that the human path surfaces — packed into
    # the JSON payload as structured fields rather than prose.
    inline_failure = _inline_failure_tail(events)
    if inline_failure is not None:
        payload["blocked_reason"] = f"produces check failed: {_format_inline_failure_tail(inline_failure)}"
        payload["blocked_step"] = STEP_PATH_SEP.join(inline_failure.path) if inline_failure.path else None
    elif events and isinstance(events[-1], dict) and events[-1].get("kind") in {"cursor_rewind", "iteration_failed"}:
        reason = events[-1].get("reason")
        if reason:
            payload["blocked_reason"] = reason
            blocked_path = _path_tuple_from_event(events[-1])
            payload["blocked_step"] = STEP_PATH_SEP.join(blocked_path) if blocked_path else None

    return emit_lifecycle_json(
        project=slug,
        run_id=run_id,
        state=run_state,
        **payload,
    )
