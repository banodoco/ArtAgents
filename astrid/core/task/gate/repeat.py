"""Repeat (until / for_each) entry helpers, iteration-state queries,
autoclose, and autocomplete helpers."""

from __future__ import annotations

import dataclasses
import json
import warnings
from pathlib import Path
from typing import Any, Callable, Sequence

from astrid.core.task.events import (
    EventLogError,
    make_for_each_expanded_event,
    make_item_started_event,
    make_iteration_exhausted_event,
    make_iteration_started_event,
    read_events,
)
from astrid.core.task.gate.attestation import match_attested_command
from astrid.core.task.gate.base import GateDecision, TaskRunGateError
from astrid.core.task.gate.cursor import (
    CursorPath,
    _ForEachSelection,
    _Frame,
    _event_matches_step_version,
    _make_exhaust_override_step,
    _make_item_frame,
    _make_iteration_frame,
    _path_str_from_event,
)
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    RepeatForEach,
    RepeatUntil,
    TaskPlan,
    TaskPlanError,
    is_attested_kind,
    iter_steps_with_path,
    load_plan,
    parse_from_ref,
    parse_repeat_until_expression,
    resolve_produces_ref,
    step_dir_for_path,
)


def _count_iteration_failed(events: Sequence[dict[str, Any]], host_path: str) -> int:
    return sum(
        1
        for ev in events
        if isinstance(ev, dict)
        and ev.get("kind") == "iteration_failed"
        and _path_str_from_event(ev) == host_path
    )


def _has_iteration_exhausted(events: Sequence[dict[str, Any]], host_path: str) -> dict[str, Any] | None:
    for ev in events:
        if (
            isinstance(ev, dict)
            and ev.get("kind") == "iteration_exhausted"
            and _path_str_from_event(ev) == host_path
        ):
            return ev
    return None


def _json_field(value: Any, field_path: tuple[str, ...], artifact_path: Path) -> Any:
    current = value
    for field in field_path:
        if not isinstance(current, dict) or field not in current:
            raise TaskRunGateError(
                reason=f"repeat.until cannot read JSON field {field!r} in {artifact_path}",
                recovery="fix the produced JSON and rerun the current step",
                code="repeat_until_json_field_missing",
            )
        current = current[field]
    return current


def _evaluate_repeat_until_expression(
    *,
    plan: TaskPlan,
    repeat: RepeatUntil,
    host_path: tuple[str, ...],
    iteration: int,
    slug: str,
    project_root: Path,
    run_id: str,
) -> tuple[bool, str]:
    try:
        expr = parse_repeat_until_expression(repeat.condition)
        resolved = resolve_produces_ref(plan, expr.ref, base_path=host_path)
        target_iteration = (
            iteration
            if resolved.step_path[: len(host_path)] == host_path
            else None
        )
        step_dir = step_dir_for_path(
            slug,
            run_id,
            resolved.step_path,
            step_version=resolved.step.version,
            iteration=target_iteration,
            root=project_root.parent,
        )
        artifact_path = step_dir / "produces" / resolved.produces.path
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        value = _json_field(payload, resolved.json_path, artifact_path)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        return False, f"repeat.until unresolved: {exc}"

    if expr.op == "==":
        passed = value == expr.literal
    elif expr.op == "!=":
        passed = value != expr.literal
    else:
        passed = value in expr.literal
    if passed:
        return True, "repeat.until satisfied"
    return False, f"repeat.until not satisfied: {value!r} {expr.op} {expr.literal!r}"


def _enter_repeat_until(
    *,
    slug: str,
    cursor: CursorPath,
    host: Any,
    repeat: RepeatUntil,
    path_str: str,
    parent_prefix: tuple[str, ...],
    events: Sequence[dict[str, Any]],
    append_fn: Callable[[dict[str, Any]], Any],
) -> None:
    failed = _count_iteration_failed(events, path_str)
    iteration = failed + 1
    path_tuple = parent_prefix + (host.id,)
    if iteration > repeat.max_iterations:
        existing = _has_iteration_exhausted(events, path_str)
        if existing is None:
            append_fn(
                make_iteration_exhausted_event(
                    path_tuple,
                    on_exhaust=repeat.on_exhaust,
                    max_iterations=repeat.max_iterations,
                )
            )
        if repeat.on_exhaust == "fail":
            raise TaskRunGateError(
                reason="repeat.until max_iterations exhausted",
                recovery=f"astrid abort --project {slug}",
                code="repeat_until_max_iterations_exhausted",
            )
        # escalate: park on a synthetic exhaust-override attested step.
        override_step = _make_exhaust_override_step(slug, path_str)
        override_plan = TaskPlan(
            plan_id=f"__exhaust_{host.id}",
            version=1,
            steps=(override_step,),
        )
        cursor.frames.append(
            _Frame(
                plan=override_plan,
                path_prefix=path_tuple,
                child_index=0,
                repeat_step_id=host.id,
            )
        )
        return
    append_fn(make_iteration_started_event(path_tuple, iteration))
    cursor.frames.append(_make_iteration_frame(host, parent_prefix, iteration))


def _resolve_for_each_items(
    *,
    slug: str,
    repeat: RepeatForEach,
    parent_prefix: tuple[str, ...] = (),
    project_root: Path,
    run_id: str,
    events: Sequence[dict[str, Any]],
) -> tuple[str, ...]:
    if repeat.items_source == "static":
        items = repeat.items
    else:
        target_id, produces_name = parse_from_ref(repeat.from_ref or "")
        # Find the prior step's declared produces path in the replayed projection;
        # a superseded producer must read from the cursor's current version, not v1.
        plan = load_plan(project_root / "plan.json")
        from astrid.core.task.plan.verbs import apply_mutations
        effective = apply_mutations(plan, events)
        target_path = parent_prefix + (target_id,)
        target_step = next((s for path, s in iter_steps_with_path(effective) if path == target_path), None)
        if target_step is None:
            raise TaskRunGateError(
                reason=f"for_each.from references unknown sibling step {target_id!r}",
                recovery=f"astrid abort --project {slug}",
                code="for_each_unknown_sibling_step",
            )
        prior_step_dir = step_dir_for_path(
            slug,
            run_id,
            target_path,
            step_version=target_step.version,
            root=project_root.parent,
        )
        produces_entry = next((p for p in target_step.produces if p.name == produces_name), None)
        if produces_entry is None:
            raise TaskRunGateError(
                reason=f"for_each.from references unknown produces {produces_name!r}",
                recovery=f"astrid abort --project {slug}",
                code="for_each_unknown_produces",
            )
        try:
            payload = json.loads((prior_step_dir / "produces" / produces_entry.path).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            raise TaskRunGateError(
                reason=f"for_each.from cannot read produces JSON: {exc}",
                recovery=f"astrid abort --project {slug}",
                code="for_each_produces_unreadable",
            ) from exc
        if not isinstance(payload, list):
            raise TaskRunGateError(reason="for_each items must be unique strings", recovery=f"astrid next --project {slug}", code="for_each_payload_not_list")
        items = tuple(payload)
    if not all(isinstance(x, str) and x for x in items):
        raise TaskRunGateError(reason="for_each items must be unique strings", recovery=f"astrid next --project {slug}", code="for_each_items_not_strings")
    if len(set(items)) != len(items):
        raise TaskRunGateError(reason="for_each items must be unique strings", recovery=f"astrid next --project {slug}", code="for_each_items_not_unique")
    return items


def _enter_repeat_for_each(
    *,
    slug: str,
    cursor: CursorPath,
    host: Any,
    repeat: RepeatForEach,
    path_str: str,
    parent_prefix: tuple[str, ...],
    events: Sequence[dict[str, Any]],
    append_fn: Callable[[dict[str, Any]], Any],
    project_root: Path,
    run_id: str,
    incoming_command: str,
) -> _ForEachSelection:
    # FLAG-P3-004: scan events for an existing for_each_expanded; if absent, append once.
    existing = next(
        (
            ev
            for ev in events
            if isinstance(ev, dict)
            and ev.get("kind") == "for_each_expanded"
            and _path_str_from_event(ev) == path_str
        ),
        None,
    )
    if existing is None:
        items = _resolve_for_each_items(
            slug=slug,
            repeat=repeat,
            parent_prefix=parent_prefix,
            project_root=project_root,
            run_id=run_id,
            events=events,
        )
        path_tuple = parent_prefix + (host.id,)
        append_fn(make_for_each_expanded_event(path_tuple, items, step_version=host.version))
        cursor.for_each_progress[path_str] = {"items": items, "completed": set()}
    else:
        items = tuple(existing.get("item_ids") or ())
    progress = cursor.for_each_progress.setdefault(path_str, {"items": items, "completed": set()})
    completed = progress["completed"]
    # For attested host: the incoming command may target a specific item via --item.
    target_item: str | None = None
    if is_attested_kind(host):
        _, args = match_attested_command(incoming_command, host.command)
        if args.item is not None:
            target_item = args.item
    pending_item = next((it for it in items if it not in completed), None)
    if target_item is None:
        target_item = pending_item
    elif target_item not in items or target_item in completed:
        # Explicit --item mistakes are local selection misses, not replayable
        # item outcomes. Fall back to a pending item when possible; otherwise
        # let traversal report exhaustion without appending item_skipped or
        # mutating progress.
        target_item = pending_item
    if target_item is None:
        return _ForEachSelection(item_id=None, no_pending=True)
    path_tuple = parent_prefix + (host.id,)
    append_fn(make_item_started_event(path_tuple, target_item, step_version=host.version))
    cursor.frames.append(_make_item_frame(host, parent_prefix, target_item))
    return _ForEachSelection(item_id=target_item)


# ── for_each host autoclose / autocomplete ──────────────────────────
#
# These helpers use late imports from .gate to avoid a circular import
# (gate.py imports from gate_repeat.py at module level, so gate_repeat
# cannot import gate.py at module level).


def _maybe_autoclose_for_each_host(
    *,
    events_path: Path,
    path_tuple: tuple[str, ...],
    project_root: Path,
    slug: str,
    run_id: str,
    append_fn: Callable[[dict[str, Any]], Any],
    current_item_id: str | None = None,
) -> None:
    context = _build_autoclose_for_each_host_context(
        events_path=events_path,
        path_tuple=path_tuple,
        project_root=project_root,
        slug=slug,
        run_id=run_id,
        current_item_id=current_item_id,
    )
    if context is None:
        return
    from astrid.core.task.gate import _finalize_step, _ActiveWriterAppend

    _finalize_step(
        context.decision,
        context.terminal_event,
        append_mode=_ActiveWriterAppend(append_fn),
    )


def _build_autoclose_for_each_host_context(
    *,
    events_path: Path,
    path_tuple: tuple[str, ...],
    project_root: Path,
    slug: str,
    run_id: str,
    current_item_id: str | None = None,
) -> Any:  # returns _ParentFinalizationContext | None
    """Build a synthetic ``step_attested`` for a for_each host once all items
    are attested. SD-001: attestor is always ``system`` / ``gate.autoclose``
    (never inherits from the closing item). SD-004: optional bodies / any
    prior ``item_skipped`` event are loud failures, not silent.

    See FLAG-S1-001 / FLAG-S1-004. Single emit site is in ``_dispatch_attested``
    immediately after the ``item_attested`` ``append_event``; if another
    ``item_attested`` emit path appears later, it MUST route through this
    helper too or for_each closure regresses.
    """
    from astrid.core.task.gate import _ParentFinalizationContext, _TerminalEventRequest

    plan_path = project_root / "plan.json"
    try:
        plan = load_plan(plan_path)
        from astrid.core.task.plan.verbs import apply_mutations

        events = read_events(events_path) if events_path.exists() else []
        plan = apply_mutations(plan, events)
    except (TaskPlanError, EventLogError) as exc:
        warnings.warn(
            f"for_each autoclose skipped for {'/'.join(path_tuple)}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
        return
    host_step = None
    for tup, s in iter_steps_with_path(plan):
        if tup == path_tuple:
            host_step = s
            break
    if host_step is None or not isinstance(getattr(host_step, "repeat", None), RepeatForEach):
        return
    if host_step.optional:
        raise AssertionError(
            "for_each autoclose: optional body bodies not yet supported (FLAG-S1-004 / SD-004)"
        )
    path_list = list(path_tuple)
    item_attested_ids: set[str] = set()
    has_host_step_attested = False
    for ev in events:
        if not isinstance(ev, dict):
            continue
        kind = ev.get("kind")
        if kind == "item_skipped" and ev.get("plan_step_path") == path_list:
            raise AssertionError(
                "for_each autoclose: optional body bodies not yet supported (FLAG-S1-004 / SD-004)"
            )
        if kind == "item_attested" and ev.get("plan_step_path") == path_list:
            item_id = ev.get("item_id")
            if isinstance(item_id, str):
                item_attested_ids.add(item_id)
        if kind == "step_attested":
            ev_id = ev.get("plan_step_id")
            if ev_id == STEP_PATH_SEP.join(path_tuple):
                has_host_step_attested = True
    if has_host_step_attested:
        return
    if current_item_id is not None:
        item_attested_ids.add(current_item_id)
    # Resolve expected total: prefer for_each_expanded (covers items_source='from'),
    # fall back to static items declared on the host.
    expected_items: set[str] | None = None
    for ev in events:
        if (
            isinstance(ev, dict)
            and ev.get("kind") == "for_each_expanded"
            and ev.get("plan_step_path") == path_list
        ):
            raw = ev.get("item_ids") or []
            if isinstance(raw, list):
                expected_items = {item for item in raw if isinstance(item, str)}
                break
    if expected_items is None:
        repeat = host_step.repeat
        if isinstance(repeat, RepeatForEach) and repeat.items_source == "static":
            expected_items = set(repeat.items)
    if expected_items is None or item_attested_ids != expected_items:
        return
    decision = GateDecision(
        active=True,
        run_id=run_id,
        plan_step_id=STEP_PATH_SEP.join(path_tuple),
        events_path=events_path,
        step_kind="attested",
        slug=slug,
        plan_step_path=path_tuple,
        project_root=project_root,
        step_version=host_step.version,
    )
    return _ParentFinalizationContext(
        decision=decision,
        terminal_event=_TerminalEventRequest(
            "step_attested",
            {
                "plan_step_path": STEP_PATH_SEP.join(path_tuple),
                "attestor_kind": "system",
                "attestor_id": "gate.autoclose",
                "evidence": ("auto-close: all items attested",),
                "step_version": host_step.version,
            },
        ),
    )


def _maybe_autocomplete_for_each_host(
    *,
    decision: GateDecision,
    returncode: int,
    cost: dict[str, Any] | None,
) -> None:
    context = _build_autocomplete_for_each_host_context(
        decision=decision,
        returncode=returncode,
        cost=cost,
    )
    if context is None:
        return
    from astrid.core.task.gate import _finalize_step

    _finalize_step(
        context.decision,
        context.terminal_event,
        append_mode="decision",
    )


def _build_autocomplete_for_each_host_context(
    *,
    decision: GateDecision,
    returncode: int,
    cost: dict[str, Any] | None,
) -> Any:  # returns _ParentFinalizationContext | None
    """Build a host ``step_completed`` when all code-repeat items completed."""
    if (
        not decision.active
        or decision.events_path is None
        or decision.project_root is None
        or decision.run_id is None
        or decision.item_id is None
    ):
        return
    from astrid.core.task.gate import _ParentFinalizationContext, _TerminalEventRequest

    plan_path = decision.project_root / "plan.json"
    try:
        plan = load_plan(plan_path)
        from astrid.core.task.plan.verbs import apply_mutations

        events = read_events(decision.events_path) if decision.events_path.exists() else []
        plan = apply_mutations(plan, events)
    except (TaskPlanError, EventLogError) as exc:
        warnings.warn(
            "for_each autocomplete skipped for "
            f"{'/'.join(decision.plan_step_path)}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
        return
    host_step = None
    for tup, step in iter_steps_with_path(plan):
        if tup == decision.plan_step_path:
            host_step = step
            break
    if host_step is None or not isinstance(getattr(host_step, "repeat", None), RepeatForEach):
        return

    path_list = list(decision.plan_step_path)
    completed_items: set[str] = set()
    expected_items: set[str] | None = None
    has_host_completed = False
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("kind") == "step_completed" and ev.get("plan_step_path") == path_list:
            if _event_matches_step_version(ev, host_step):
                has_host_completed = True
        if ev.get("kind") == "item_completed" and ev.get("plan_step_path") == path_list:
            if _event_matches_step_version(ev, host_step):
                item_id = ev.get("item_id")
                if isinstance(item_id, str):
                    completed_items.add(item_id)
        if ev.get("kind") == "for_each_expanded" and ev.get("plan_step_path") == path_list:
            raw = ev.get("item_ids") or []
            if isinstance(raw, list):
                expected_items = {item for item in raw if isinstance(item, str)}
    if has_host_completed:
        return
    completed_items.add(decision.item_id)
    if expected_items is None:
        repeat = host_step.repeat
        if isinstance(repeat, RepeatForEach) and repeat.items_source == "static":
            expected_items = set(repeat.items)
    if expected_items is None or completed_items != expected_items:
        return
    return _ParentFinalizationContext(
        decision=dataclasses.replace(decision, item_id=None, step_version=host_step.version),
        terminal_event=_TerminalEventRequest(
            "step_completed",
            {
                "plan_step_path": STEP_PATH_SEP.join(decision.plan_step_path),
                "returncode": returncode,
                "cost": cost,
                "adapter": decision.adapter,
                "step_version": host_step.version,
            },
        ),
    )
