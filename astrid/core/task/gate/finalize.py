"""Task gate finalization and dispatch-complete helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astrid.core.project.sidecar import write_text_sidecar
from astrid.core.task.env import is_author_test_mode
from astrid.core.task.events import (
    make_cursor_rewind_event,
    make_item_attested_event,
    make_item_completed_event,
    make_iteration_failed_event,
    make_nested_entered_event,
    make_nested_exited_event,
    make_produces_check_failed_event,
    make_step_attested_event,
    make_step_awaiting_fetch_event,
    make_step_completed_event,
    make_step_failed_event,
    make_step_skipped_event,
    read_events,
)
from astrid.core.task.gate.base import GateDecision, InlineCheckResult
from astrid.core.task.plan import Step, iter_steps_with_path, load_plan


def _append_finalized(
    decision: GateDecision,
    event: dict[str, Any],
    append_mode: Any,
) -> dict[str, Any] | None:
    if append_mode == "decision":
        from astrid.core.task import gate as task_gate

        return task_gate._append_via_decision(decision, event)
    return append_mode.append_fn(event)


def _finalize_step(
    decision: GateDecision,
    terminal_event: Any,
    append_mode: Any,
    inline_check_result: InlineCheckResult | None = None,
    cost: dict[str, Any] | None = None,
) -> None:
    if isinstance(terminal_event, dict):
        event = terminal_event
    else:
        payload = terminal_event.payload
        if terminal_event.kind == "step_completed":
            event = make_step_completed_event(**payload)
        elif terminal_event.kind == "step_failed":
            event = make_step_failed_event(**payload)
        elif terminal_event.kind == "step_skipped":
            event = make_step_skipped_event(**payload)
        elif terminal_event.kind == "step_awaiting_fetch":
            event = make_step_awaiting_fetch_event(**payload)
        elif terminal_event.kind == "item_completed":
            event = make_item_completed_event(**payload)
        elif terminal_event.kind == "step_attested":
            event = make_step_attested_event(**payload)
        elif terminal_event.kind == "item_attested":
            event = make_item_attested_event(**payload)
        else:
            raise AssertionError(f"unknown terminal event kind: {terminal_event.kind}")
    if is_author_test_mode() and event.get("kind") in {"step_attested", "item_attested"}:
        event["source"] = "author_test"
    _append_finalized(decision, event, append_mode)
    result = inline_check_result or InlineCheckResult(ok=True)
    inline_events = result.events
    if not result.ok and not inline_events and result.name is not None:
        failed = make_produces_check_failed_event(
            decision.plan_step_path,
            result.name,
            check_id="inline",
            reason=result.reason or "produces check failed",
            step_version=decision.step_version,
            dispatch_event_hash=decision.dispatch_event_hash,
        )
        if decision.iteration is not None:
            rewind = make_iteration_failed_event(
                decision.plan_step_path,
                decision.iteration,
                reason=f"produces check failed: {result.name}",
                step_version=decision.step_version,
            )
        else:
            rewind = make_cursor_rewind_event(
                decision.plan_step_path,
                reason=f"produces check failed: {result.name}",
                step_version=decision.step_version,
                dispatch_event_hash=decision.dispatch_event_hash,
            )
        inline_events = (failed, rewind)
    for inline_event in inline_events:
        _append_finalized(decision, inline_event, append_mode)
    if not result.ok:
        return
    from astrid.core.task import gate as task_gate

    if event.get("kind") == "item_attested":
        task_gate._maybe_autoclose_for_each_host(
            events_path=decision.events_path or Path(),
            path_tuple=decision.plan_step_path,
            project_root=decision.project_root or Path("."),
            slug=decision.slug or "",
            run_id=decision.run_id or "",
            append_fn=(
                append_mode.append_fn
                if isinstance(append_mode, task_gate._ActiveWriterAppend)
                else lambda ev: task_gate._append_via_decision(decision, ev)
            ),
            current_item_id=str(event.get("item_id") or "") or None,
        )
    elif event.get("kind") == "item_completed":
        task_gate._maybe_autocomplete_for_each_host(
            decision=decision,
            returncode=int(event.get("returncode") or 0),
            cost=cost,
        )


def record_dispatch_complete(decision: GateDecision, returncode: int) -> None:
    if not decision.active or decision.events_path is None or decision.plan_step_id is None:
        return
    if decision.step_kind == "attested":
        return

    from astrid.core.task import gate as task_gate

    run_ctx = task_gate._make_run_ctx(
        decision.slug or "",
        decision.run_id or "",
        decision.plan_step_path,
        decision.step_version,
        decision.project_root or Path("."),
        iteration=decision.iteration,
        item_id=decision.item_id,
    )
    step = task_gate._load_step_for_decision(decision)
    adapter = task_gate._resolve_adapter(step) if step else None

    if adapter is not None:
        if returncode != -1:
            write_text_sidecar(_step_dir_from_run_ctx(run_ctx) / "returncode", f"{returncode}\n")
        complete_result = adapter.complete(step, run_ctx)
        cost_dict: dict[str, Any] | None = None
        if complete_result.cost is not None:
            cost_dict = {
                "amount": complete_result.cost.amount,
                "currency": complete_result.cost.currency,
                "source": complete_result.cost.source,
            }
        if step is not None and step.requires_ack:
            return
        completed_returncode = returncode if returncode != -1 else (complete_result.returncode or 0)
        if complete_result.status == "failed":
            terminal = task_gate._TerminalEventRequest(
                "step_failed",
                {
                    "plan_step_path": decision.plan_step_id,
                    "returncode": complete_result.returncode,
                    "reason": complete_result.reason,
                    "cost": cost_dict,
                    "adapter": decision.adapter,
                    "step_version": decision.step_version,
                    "dispatch_event_hash": decision.dispatch_event_hash,
                },
            )
        elif complete_result.status == "awaiting_fetch":
            missing, mismatched = _read_awaiting_fetch_items(run_ctx)
            terminal = task_gate._TerminalEventRequest(
                "step_awaiting_fetch",
                {
                    "path_str": decision.plan_step_id,
                    "missing": missing,
                    "mismatched": mismatched,
                    "reason": complete_result.reason,
                    "adapter": decision.adapter,
                    "step_version": decision.step_version,
                    "dispatch_event_hash": decision.dispatch_event_hash,
                },
            )
        elif decision.item_id is not None:
            terminal = task_gate._TerminalEventRequest(
                "item_completed",
                {
                    "plan_step_path": decision.plan_step_path,
                    "item_id": decision.item_id,
                    "returncode": completed_returncode,
                    "step_version": decision.step_version,
                },
            )
        else:
            terminal = task_gate._TerminalEventRequest(
                "step_completed",
                {
                    "plan_step_path": decision.plan_step_id,
                    "returncode": completed_returncode,
                    "cost": cost_dict,
                    "adapter": decision.adapter,
                    "step_version": decision.step_version,
                    "dispatch_event_hash": decision.dispatch_event_hash,
                },
            )
    else:
        cost_dict = None
        terminal = task_gate._TerminalEventRequest(
            "step_completed",
            {
                "plan_step_path": decision.plan_step_id,
                "returncode": returncode,
                "step_version": decision.step_version,
                "dispatch_event_hash": decision.dispatch_event_hash,
            },
        )

    inline_check_result: InlineCheckResult | None = None
    if decision.produces:
        inline_events: list[dict[str, Any]] = []
        inline_check_result = task_gate._run_inline_checks(
            decision,
            decision.produces,
            append_fn=inline_events.append,
        )
    _finalize_step(
        decision,
        terminal,
        append_mode="decision",
        inline_check_result=inline_check_result,
        cost=cost_dict,
    )


def _read_awaiting_fetch_items(run_ctx: Any) -> tuple[list[str], list[str]]:
    """Read missing/mismatched artifact names from the step's remote_state.json sidecar."""
    step_dir = _step_dir_from_run_ctx(run_ctx)
    remote_state_path = step_dir / "remote_state.json"
    if not remote_state_path.exists():
        return [], []
    try:
        state = json.loads(remote_state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [], []
    missing = state.get("missing", [])
    mismatched = state.get("mismatched", [])
    if not isinstance(missing, list):
        missing = []
    if not isinstance(mismatched, list):
        mismatched = []
    return list(missing), list(mismatched)


def _step_dir_from_run_ctx(run_ctx: Any) -> Path:
    """Resolve runs/<run>/steps/<id>/v<N>/ for a RunContext."""
    base = run_ctx.project_root / "runs" / run_ctx.run_id / "steps"
    for segment in run_ctx.plan_step_path:
        base = base / segment
    base = base / f"v{run_ctx.step_version}"
    if getattr(run_ctx, "iteration", None) is not None:
        base = base / "iterations" / f"{run_ctx.iteration:03d}"
    elif getattr(run_ctx, "item_id", None) is not None:
        base = base / "items" / run_ctx.item_id
    return base


def _load_step_for_decision(decision: GateDecision) -> Step | None:
    """Load the Step object for a decision by reading plan.json + events."""
    if decision.project_root is None or not decision.plan_step_path:
        return None
    plan_path = decision.project_root / "plan.json"
    if not plan_path.exists():
        return None
    plan = load_plan(plan_path)
    events_path = decision.project_root / "runs" / (decision.run_id or "") / "events.jsonl"
    events = read_events(events_path) if events_path.exists() else []
    from astrid.core.task.plan.verbs import apply_mutations

    effective = apply_mutations(plan, events)
    for path_tuple, step in iter_steps_with_path(effective):
        if path_tuple == decision.plan_step_path:
            return step
    return None


def record_nested_entered(decision: GateDecision, child_plan_hash: str) -> None:
    """Reserved for Phase 5 lifecycle verbs; gate emits inline in Phase 2."""
    if not decision.active or decision.events_path is None or decision.plan_step_id is None:
        return
    from astrid.core.task import gate as task_gate

    task_gate._append_via_decision(
        decision,
        make_nested_entered_event(decision.plan_step_id, child_plan_hash),
    )


def record_nested_exited(decision: GateDecision, returncode: int) -> None:
    """Reserved for Phase 5 lifecycle verbs; gate emits inline in Phase 2."""
    if not decision.active or decision.events_path is None or decision.plan_step_id is None:
        return
    from astrid.core.task import gate as task_gate

    task_gate._append_via_decision(
        decision,
        make_nested_exited_event(decision.plan_step_id, returncode),
    )
