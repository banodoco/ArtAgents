"""Repeat (until / for_each) entry helpers and iteration-state queries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Sequence

from astrid.core.task.gate_base import TaskRunGateError
from astrid.core.task.gate_cursor import (
    CursorPath,
    _ForEachSelection,
    _Frame,
    _make_exhaust_override_step,
    _make_iteration_frame,
    _make_item_frame,
    _path_str_from_event,
)
from astrid.core.task.gate_attestation import match_attested_command
from astrid.core.task.events import (
    make_for_each_expanded_event,
    make_item_started_event,
    make_iteration_exhausted_event,
    make_iteration_started_event,
)
from astrid.core.task.plan import (
    RepeatForEach,
    RepeatUntil,
    Step,
    TaskPlan,
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
        from astrid.core.task.plan_verbs import apply_mutations
        effective = apply_mutations(plan, events)
        target_path = parent_prefix + (target_id,)
        target_step = next((s for path, s in iter_steps_with_path(effective) if path == target_path), None)
        if target_step is None:
            raise TaskRunGateError(
                reason=f"for_each.from references unknown sibling step {target_id!r}",
                recovery=f"astrid abort --project {slug}",
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
            )
        try:
            payload = json.loads((prior_step_dir / "produces" / produces_entry.path).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            raise TaskRunGateError(
                reason=f"for_each.from cannot read produces JSON: {exc}",
                recovery=f"astrid abort --project {slug}",
            ) from exc
        if not isinstance(payload, list):
            raise TaskRunGateError(reason="for_each items must be unique strings", recovery=f"astrid next --project {slug}")
        items = tuple(payload)
    if not all(isinstance(x, str) and x for x in items):
        raise TaskRunGateError(reason="for_each items must be unique strings", recovery=f"astrid next --project {slug}")
    if len(set(items)) != len(items):
        raise TaskRunGateError(reason="for_each items must be unique strings", recovery=f"astrid next --project {slug}")
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
