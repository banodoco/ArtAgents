"""Task-run dispatch gate.

Phase 2 nested handling is kernel-only; Phase 5 will add the ``astrid ack`` /
``astrid next`` lifecycle verbs that drive the ``record_nested_entered`` /
``record_nested_exited`` helpers exposed for symmetry below. The gate itself
emits ``step_attested``, ``nested_entered``, and ``nested_exited`` events
inline; only the nested helpers remain exported for later lifecycle wiring.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import shlex
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, NoReturn, Sequence

from astrid.core.project.current_run import read_current_run_state
from astrid.core.project.paths import project_dir
from astrid.core.session.writer import writer_context_for_project, writer_context_from_decision
from astrid.core.task.cas import intern, link_into_produces
from astrid.core.project.sidecar import write_json_sidecar, write_text_sidecar
from astrid.core.task.env import (
    apply_task_run_env,
    is_author_test_mode,
    is_in_task_run,
    task_actor_env,
)
from astrid.core.task.command_render import render_task_command, strip_task_env_prefix
from astrid.core.task.events import (
    canonical_event_json,
    EventLogError,
    make_cursor_rewind_event,
    make_for_each_expanded_event,
    make_item_attested_event,
    make_item_completed_event,
    make_item_started_event,
    make_iteration_exhausted_event,
    make_iteration_failed_event,
    make_iteration_started_event,
    make_nested_entered_event,
    make_nested_exited_event,
    make_produces_check_failed_event,
    make_produces_check_passed_event,
    make_step_attested_event,
    make_step_awaiting_fetch_event,
    make_step_completed_event,
    make_step_dispatched_event,
    make_step_failed_event,
    read_events,
)
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    AckRule,
    ProducesEntry,
    RepeatForEach,
    RepeatUntil,
    Step,
    TaskPlan,
    TaskPlanError,
    compute_plan_hash,
    is_legacy_repeat_until_condition,
    is_attested_kind,
    is_code_kind,
    is_group_step,
    iter_steps_with_path,
    load_plan,
    parse_from_ref,
    parse_repeat_until_expression,
    resolve_produces_ref,
    step_dir_for_path,
)
from astrid.core.task.gate_base import (
    GateDecision,
    InlineCheckResult,
    ITERATE_FEEDBACK_PREFIX,
    TaskRunGateError,
    _reject,
)
from astrid.core.task.gate_cursor import (
    CursorPath,
    EXHAUST_OVERRIDE_ID,
    _current_dispatch_hash,
    _current_item_step,
    _current_repeat_context,
    _current_step_for_path,
    _event_matches_dispatch_hash,
    _event_matches_pending,
    _event_matches_step_version,
    _event_step_version,
    _finalize_cursor,
    _ForEachSelection,
    _Frame,
    _make_exhaust_override_step,
    _make_iteration_frame,
    _make_item_frame,
    _path_str_from_event,
    _PendingProduces,
    _repeat_host_for_top_frame,
    _top_frame_needs_repeat_until_evaluation,
    derive_cursor,
)
from astrid.core.task.gate_attestation import (
    AttestedArgs,
    _extract_iterate_feedback,
    match_attested_command,
    validate_attested_identity,
    write_iteration_feedback,
)
from astrid.core.task.gate_repeat import (
    _count_iteration_failed,
    _enter_repeat_for_each,
    _enter_repeat_until,
    _evaluate_repeat_until_expression,
    _has_iteration_exhausted,
    _json_field,
    _resolve_for_each_items,
)
from astrid.core.task.gate_checks import (
    _intern_produces_artifact,
    _run_inline_checks,
)


@dataclass(frozen=True)
class _ActiveWriterAppend:
    append_fn: Callable[[dict[str, Any]], Any]


_FinalizeAppendMode = Literal["decision"] | _ActiveWriterAppend


@dataclass(frozen=True)
class _TerminalEventRequest:
    kind: Literal[
        "step_completed",
        "step_failed",
        "step_awaiting_fetch",
        "item_completed",
        "step_attested",
        "item_attested",
    ]
    payload: dict[str, Any]


@dataclass(frozen=True)
class _ParentFinalizationContext:
    decision: GateDecision
    terminal_event: _TerminalEventRequest


def _auto_traverse_to_leaf(
    *,
    slug: str,
    cursor: CursorPath,
    events_view: list[dict[str, Any]],
    incoming_command: str,
    project_root: Path,
    run_id: str,
    append_fn: Callable[[dict[str, Any]], Any],
    raise_on_exhausted: bool,
) -> tuple[Any, tuple[str, ...]] | None:
    """Walk the cursor through group entries and repeat-host expansions until we
    land on a dispatchable leaf. Mutates ``cursor.frames`` and pushes
    auto-traversal events through ``append_fn``. ``events_view`` must be the list
    that ``append_fn`` extends (or that mirrors the on-disk log) so the helpers
    that scan prior events (``_count_iteration_failed``, the ``for_each_expanded``
    lookup) see the latest state.

    With ``raise_on_exhausted=True`` (gate dispatch) the helper raises
    ``TaskRunGateError`` when the plan is exhausted; with ``False`` (peek) it
    returns ``None`` so the caller can report exhaustion to the operator.
    """
    while True:
        if cursor.at_root_done:
            if raise_on_exhausted:
                _reject(slug, "plan is exhausted", abort=True)
            return None
        if cursor.top_exhausted:
            top = cursor.frames[-1]
            if top.repeat_step_id is not None:
                if _top_frame_needs_repeat_until_evaluation(cursor.frames):
                    _evaluate_exhausted_repeat_until_frame(
                        slug=slug,
                        cursor=cursor,
                        project_root=project_root,
                        run_id=run_id,
                        append_fn=append_fn,
                    )
                    continue
                # Defensive: _finalize_cursor should have popped these already.
                cursor.frames.pop()
                cursor.frames[-1].child_index += 1
                continue
            exit_path_str = STEP_PATH_SEP.join(top.path_prefix)
            append_fn(make_nested_exited_event(exit_path_str, 0))
            cursor.frames.pop()
            cursor.frames[-1].child_index += 1
            continue
        top = cursor.frames[-1]
        current_step = top.plan.steps[top.child_index]
        current_path = top.path_prefix + (current_step.id,)
        path_str = STEP_PATH_SEP.join(current_path)
        repeat = getattr(current_step, "repeat", None)
        in_repeat_frame = top.repeat_step_id is not None
        if repeat is not None and not in_repeat_frame:
            if isinstance(repeat, RepeatUntil):
                _enter_repeat_until(
                    slug=slug,
                    cursor=cursor,
                    host=current_step,
                    repeat=repeat,
                    path_str=path_str,
                    parent_prefix=top.path_prefix,
                    events=events_view,
                    append_fn=append_fn,
                )
                continue
            if isinstance(repeat, RepeatForEach):
                selection = _enter_repeat_for_each(
                    slug=slug,
                    cursor=cursor,
                    host=current_step,
                    repeat=repeat,
                    path_str=path_str,
                    parent_prefix=top.path_prefix,
                    events=events_view,
                    append_fn=append_fn,
                    project_root=project_root,
                    run_id=run_id,
                    incoming_command=incoming_command,
                )
                if selection.no_pending:
                    if raise_on_exhausted:
                        _reject(slug, "for_each has no pending items", abort=True)
                    return None
                continue
        if is_group_step(current_step):
            child_hash = _compute_inline_plan_hash(current_step.plan)
            append_fn(make_nested_entered_event(path_str, child_hash))
            cursor.frames.append(
                _Frame(plan=current_step.plan, path_prefix=current_path, child_index=0)
            )
            continue
        return current_step, current_path


@dataclass(frozen=True)
class PeekResult:
    """Read-only view of the next dispatchable step under the current cursor.

    Returned by ``peek_current_step`` for ``cmd_next`` / ``cmd_status`` /
    ``cmd_ack`` to inspect what the gate would dispatch on next without
    actually mutating ``events.jsonl``. ``exhausted=True`` covers both
    ``at_root_done`` (plan complete) and ``pinned_failure``
    (repeat.until on_exhaust=fail).
    """

    step: Any
    path_tuple: tuple[str, ...]
    iteration: int | None
    item_id: str | None
    exhausted: bool


def peek_current_step(
    plan: TaskPlan,
    events: Sequence[dict[str, Any]],
    slug: str,
    *,
    project_root: Path,
    run_id: str,
) -> PeekResult:
    """Walk the cursor exactly the way the gate would, but with a list-capturing
    ``append_fn`` so ``events.jsonl`` is never mutated.

    Shares ``_auto_traverse_to_leaf`` with ``gate_command`` so peek and dispatch
    cannot drift on iteration / for_each / nested transitions (FLAG-P5-003).
    The captured events are kept in ``events_view`` so prior-event scans inside
    the auto-traverse helpers (``_count_iteration_failed``, the
    ``for_each_expanded`` lookup) see them; after every append we let the helper
    proceed and re-evaluate the cursor — which is equivalent to recomputing
    ``derive_cursor(plan, events + captured, slug=slug)`` because the helper
    performs the same frame mutations that ``derive_cursor`` would on replay.
    """
    cursor = derive_cursor(plan, events, slug=slug)
    if cursor.pinned_failure is not None or cursor.at_root_done:
        return PeekResult(step=None, path_tuple=(), iteration=None, item_id=None, exhausted=True)

    events_view = list(events)
    captured: list[dict[str, Any]] = []

    def _peek_append(ev: dict[str, Any]) -> None:
        captured.append(ev)
        events_view.append(ev)

    leaf = _auto_traverse_to_leaf(
        slug=slug,
        cursor=cursor,
        events_view=events_view,
        incoming_command="",
        project_root=project_root,
        run_id=run_id,
        append_fn=_peek_append,
        raise_on_exhausted=False,
    )
    if leaf is None:
        return PeekResult(step=None, path_tuple=(), iteration=None, item_id=None, exhausted=True)
    step, path_tuple = leaf
    iteration, item_id = _current_repeat_context(cursor.frames)
    return PeekResult(
        step=step,
        path_tuple=path_tuple,
        iteration=iteration,
        item_id=item_id,
        exhausted=False,
    )


def gate_command(
    slug: str,
    command: str,
    argv: Sequence[str],
    *,
    root: str | Path | None = None,
    reentry: bool = False,
) -> GateDecision:
    active_run = read_current_run_state(slug, root=root)
    if active_run is None:
        if not is_in_task_run(slug):
            return GateDecision(active=False)
        _reject(slug, "active_run.json is missing", abort=True)

    project_root = project_dir(slug, root=root)
    plan_path = project_root / "plan.json"
    run_id = active_run["run_id"]
    events_path = project_root / "runs" / run_id / "events.jsonl"
    # Sprint 1 (T9 / DEC-007): the tail-only CAS in append_event_locked is
    # the integrity gate for the hot append path; mid-chain corruption
    # detection is delegated to offline audit (verify_chain remains
    # callable for that purpose). Removing the per-verb O(n) re-walk here
    # is an acceptable trade-off documented in the brief.

    events = read_events(events_path)
    from astrid.core.task.plan_verbs import (
        apply_mutations,
        initial_plan_hash_from_events,
    )
    plan_hash = initial_plan_hash_from_events(events) or compute_plan_hash(plan_path)
    if plan_hash != active_run["plan_hash"]:
        _reject(slug, "plan.json hash does not match active_run.json pin", abort=True)

    plan = apply_mutations(load_plan(plan_path), events)
    cursor = derive_cursor(plan, events, slug=slug)
    if cursor.pinned_failure is not None:
        reason, _host_path = cursor.pinned_failure
        raise TaskRunGateError(reason=reason, recovery=f"astrid abort --project {slug}")
    run_started_actor = _find_run_started_actor(events)

    # Auto-traverse: nested_entered/exited for group steps; iteration_started/
    # for_each_expanded/item_started for repeat hosts. We loop until we land on a
    # dispatchable leaf inside the appropriate frame.
    with writer_context_for_project(slug, root=root) as writer:
        events_view = list(events)

        def _gate_append(ev: dict[str, Any]) -> None:
            writer.append(ev)
            events_view.append(ev)

        leaf = _auto_traverse_to_leaf(
            slug=slug,
            cursor=cursor,
            events_view=events_view,
            incoming_command=command,
            project_root=project_root,
            run_id=run_id,
            append_fn=_gate_append,
            raise_on_exhausted=True,
        )
        if leaf is None:
            # Defensive: raise_on_exhausted=True should always raise inside the helper.
            _reject(slug, "plan is exhausted", abort=True)
        current_step, current_path = leaf
        path_str = STEP_PATH_SEP.join(current_path)

        iteration, item_id = _current_repeat_context(cursor.frames)

        if is_code_kind(current_step):
            return _dispatch_code(
                slug=slug,
                command=command,
                step=current_step,
                path_str=path_str,
                path_tuple=current_path,
                events_path=events_path,
                run_id=run_id,
                reentry=reentry,
                project_root=project_root,
                iteration=iteration,
                item_id=item_id,
                append_fn=_gate_append,
                session=writer.session,
                run_dir=writer.run_dir,
                writer_epoch_at_dispatch=writer.expected_writer_epoch,
            )
        if is_attested_kind(current_step):
            return _dispatch_attested(
                slug=slug,
                command=command,
                step=current_step,
                path_str=path_str,
                path_tuple=current_path,
                events_path=events_path,
                run_id=run_id,
                run_started_actor=run_started_actor,
                project_root=project_root,
                iteration=iteration,
                item_id=item_id,
                append_fn=_gate_append,
                session=writer.session,
                run_dir=writer.run_dir,
                writer_epoch_at_dispatch=writer.expected_writer_epoch,
            )
    raise TaskRunGateError(
        reason=f"unexpected step kind: {type(current_step).__name__}",
        recovery=f"astrid next --project {slug}",
    )


def _evaluate_exhausted_repeat_until_frame(
    *,
    slug: str,
    cursor: CursorPath,
    project_root: Path,
    run_id: str,
    append_fn: Callable[[dict[str, Any]], Any],
) -> None:
    found = _repeat_host_for_top_frame(cursor.frames)
    if found is None:
        cursor.frames.pop()
        cursor.frames[-1].child_index += 1
        return
    parent, host = found
    repeat = getattr(host, "repeat", None)
    top = cursor.frames[-1]
    if not isinstance(repeat, RepeatUntil) or top.iteration is None:
        cursor.frames.pop()
        parent.child_index += 1
        return
    host_path = parent.path_prefix + (host.id,)
    passed, reason = _evaluate_repeat_until_expression(
        plan=cursor.frames[0].plan,
        repeat=repeat,
        host_path=host_path,
        iteration=top.iteration,
        slug=slug,
        project_root=project_root,
        run_id=run_id,
    )
    cursor.frames.pop()
    if passed:
        _finalize_step(
            GateDecision(
                active=True,
                run_id=run_id,
                plan_step_id=STEP_PATH_SEP.join(host_path),
                slug=slug,
                plan_step_path=host_path,
                project_root=project_root,
                adapter=host.adapter,
                step_version=host.version,
            ),
            _TerminalEventRequest(
                "step_completed",
                {
                    "plan_step_path": STEP_PATH_SEP.join(host_path),
                    "returncode": 0,
                    "adapter": host.adapter,
                    "step_version": host.version,
                },
            ),
            append_mode=_ActiveWriterAppend(append_fn),
        )
        parent.child_index += 1
        return
    append_fn(
        make_iteration_failed_event(
            host_path,
            top.iteration,
            reason=reason,
            step_version=host.version,
        )
    )


def _resolve_adapter(step: Step):
    """Return the concrete adapter instance for ``step.adapter``."""
    from astrid.core.adapter.local import LocalAdapter
    from astrid.core.adapter.manual import ManualAdapter
    from astrid.core.adapter.remote_artifact import RemoteArtifactAdapter

    if step.adapter == "local":
        return LocalAdapter()
    if step.adapter == "manual":
        return ManualAdapter()
    if step.adapter == "remote-artifact":
        return RemoteArtifactAdapter()
    raise TaskRunGateError(
        reason=f"unknown adapter {step.adapter!r}",
        recovery="use --adapter local or manual",
    )


def _make_run_ctx(
    slug: str,
    run_id: str,
    path_tuple: tuple[str, ...],
    step_version: int,
    project_root: Path,
    iteration: int | None = None,
    item_id: str | None = None,
    rendered: Any = None,
):
    """Return a RunContext for adapter dispatch. Return type is adapter.RunContext (lazy import)."""
    from astrid.core.adapter import RunContext

    return RunContext(
        slug=slug,
        run_id=run_id,
        project_root=project_root,
        plan_step_path=path_tuple,
        step_version=step_version,
        iteration=iteration,
        item_id=item_id,
        canonical_command=getattr(rendered, "canonical_command", None),
        canonical_argv=getattr(rendered, "canonical_argv", ()),
        display_command=getattr(rendered, "display_command", None),
        task_env=getattr(rendered, "task_env", None),
        produces_root=getattr(rendered, "produces_root", None),
    )


def _dispatch_code(
    *,
    slug: str,
    command: str,
    step: Step,
    path_str: str,
    path_tuple: tuple[str, ...],
    events_path: Path,
    run_id: str,
    reentry: bool,
    project_root: Path,
    iteration: int | None = None,
    item_id: str | None = None,
    append_fn: Callable[[dict[str, Any]], Any],
    session: Any = None,
    run_dir: Path | None = None,
    writer_epoch_at_dispatch: int | None = None,
) -> GateDecision:
    try:
        rendered = render_task_command(
            step,
            slug=slug,
            run_id=run_id,
            project_root=project_root,
            plan_step_path=path_tuple,
            iteration=iteration,
            item_id=item_id,
        )
    except ValueError as exc:
        _reject(slug, str(exc), abort=False)
    incoming_canonical = _normalize_command_string(strip_task_env_prefix(command))
    if incoming_canonical != rendered.canonical_command:
        _reject(slug, "incoming command does not match plan[cursor]", abort=False)

    adapter = _resolve_adapter(step)
    step_version = step.version
    run_ctx = _make_run_ctx(
        slug, run_id, path_tuple, step_version, project_root,
        iteration=iteration, item_id=item_id, rendered=rendered,
    )

    if reentry:
        # FLAG-P3-005: scan back to the latest event for THIS plan_step_id rather than events[-1];
        # produces_check_failed must permit redispatch (cursor hasn't advanced).
        events = read_events(events_path)
        latest = _latest_event_for_step(events, path_str, step_version=step_version)
        if (
            isinstance(latest, dict)
            and latest.get("kind") == "step_dispatched"
            and latest.get("command") == rendered.canonical_command
        ):
            apply_task_run_env(run_id, slug, path_str, item_id=item_id, iteration=iteration)
            return _code_decision(
                run_id=run_id,
                slug=slug,
                path_str=path_str,
                path_tuple=path_tuple,
                events_path=events_path,
                produces=step.produces,
                project_root=project_root,
                reentry=True,
                iteration=iteration,
                item_id=item_id,
                adapter=step.adapter,
                step_version=step_version,
                dispatch_event_hash=latest.get("hash") if isinstance(latest.get("hash"), str) else None,
                session=session,
                run_dir=run_dir,
                writer_epoch_at_dispatch=writer_epoch_at_dispatch,
            )
        if latest is None:
            apply_task_run_env(run_id, slug, path_str, item_id=item_id, iteration=iteration)
            dispatched = make_step_dispatched_event(
                path_str,
                rendered.canonical_command,
                adapter=step.adapter,
                step_version=step_version,
                pid=None,
            )
            appended = append_fn(dispatched)
            dispatch_event_hash = (
                appended.get("hash")
                if isinstance(appended, dict) and isinstance(appended.get("hash"), str)
                else None
            )
            return _code_decision(
                run_id=run_id,
                slug=slug,
                path_str=path_str,
                path_tuple=path_tuple,
                events_path=events_path,
                produces=step.produces,
                project_root=project_root,
                reentry=True,
                iteration=iteration,
                item_id=item_id,
                adapter=step.adapter,
                step_version=step_version,
                dispatch_event_hash=dispatch_event_hash,
                session=session,
                run_dir=run_dir,
                writer_epoch_at_dispatch=writer_epoch_at_dispatch,
            )
        if isinstance(latest, dict) and latest.get("kind") == "produces_check_failed":
            apply_task_run_env(run_id, slug, path_str, item_id=item_id, iteration=iteration)
            dispatch_result, dispatch_event_hash = _adapter_dispatch(
                adapter, step, run_ctx, path_str, rendered.canonical_command, append_fn
            )
            return _code_decision(
                run_id=run_id,
                slug=slug,
                path_str=path_str,
                path_tuple=path_tuple,
                events_path=events_path,
                produces=step.produces,
                project_root=project_root,
                reentry=False,
                iteration=iteration,
                item_id=item_id,
                adapter=step.adapter,
                step_version=step_version,
                pid=dispatch_result.pid if dispatch_result else None,
                dispatch_event_hash=dispatch_event_hash,
                session=session,
                run_dir=run_dir,
                writer_epoch_at_dispatch=writer_epoch_at_dispatch,
            )
        _reject(slug, "incoming command does not match plan[cursor]", abort=False)

    apply_task_run_env(run_id, slug, path_str, item_id=item_id, iteration=iteration)
    dispatch_result, dispatch_event_hash = _adapter_dispatch(
        adapter, step, run_ctx, path_str, rendered.canonical_command, append_fn
    )
    return _code_decision(
        run_id=run_id,
        slug=slug,
        path_str=path_str,
        path_tuple=path_tuple,
        events_path=events_path,
        produces=step.produces,
        project_root=project_root,
        reentry=False,
        iteration=iteration,
        item_id=item_id,
        adapter=step.adapter,
        step_version=step_version,
        pid=dispatch_result.pid if dispatch_result else None,
        dispatch_event_hash=dispatch_event_hash,
        session=session,
        run_dir=run_dir,
        writer_epoch_at_dispatch=writer_epoch_at_dispatch,
    )


def _adapter_dispatch(
    adapter,
    step: Step,
    run_ctx,
    path_str: str,
    command: str,
    append_fn: Callable[[dict[str, Any]], Any],
):
    """Call adapter.dispatch() and emit step_dispatched. Returns DispatchResult or None on reject."""
    result = adapter.dispatch(step, run_ctx)
    if result.status == "rejected":
        _reject(run_ctx.slug, f"adapter {step.adapter!r} rejected dispatch: {result.reason}", abort=False)
    # Single emission point: cmd_next/gate emits step_dispatched.
    dispatched = make_step_dispatched_event(
        path_str, command,
        adapter=step.adapter,
        step_version=run_ctx.step_version,
        pid=result.pid,
    )
    appended = append_fn(dispatched)
    dispatch_event_hash = (
        appended.get("hash") if isinstance(appended, dict) and isinstance(appended.get("hash"), str) else None
    )
    return result, dispatch_event_hash


def _code_decision(
    *,
    run_id: str,
    slug: str,
    path_str: str,
    path_tuple: tuple[str, ...],
    events_path: Path,
    produces: tuple[ProducesEntry, ...],
    project_root: Path,
    reentry: bool,
    iteration: int | None = None,
    item_id: str | None = None,
    adapter: str | None = None,
    step_version: int = 1,
    pid: int | None = None,
    dispatch_event_hash: str | None = None,
    session: Any = None,
    run_dir: Path | None = None,
    writer_epoch_at_dispatch: int | None = None,
) -> GateDecision:
    return GateDecision(
        active=True,
        run_id=run_id,
        plan_step_id=path_str,
        events_path=events_path,
        reentry=reentry,
        step_kind="code",
        slug=slug,
        plan_step_path=path_tuple,
        produces=produces,
        project_root=project_root,
        iteration=iteration,
        item_id=item_id,
        adapter=adapter,
        step_version=step_version,
        pid=pid,
        dispatch_event_hash=dispatch_event_hash,
        run_dir=run_dir,
        writer_epoch_at_dispatch=writer_epoch_at_dispatch,
        session_id=getattr(session, "id", None),
        session=session,
    )


def _latest_event_for_step(
    events: Sequence[dict[str, Any]],
    path_str: str,
    *,
    step_version: int | None = None,
) -> dict[str, Any] | None:
    path_list = path_str.split(STEP_PATH_SEP)
    for ev in reversed(events):
        if not isinstance(ev, dict):
            continue
        if step_version is not None and _event_step_version(ev) != step_version:
            continue
        if ev.get("plan_step_id") == path_str:
            return ev
        if ev.get("plan_step_path") == path_list:
            return ev
    return None


def _dispatch_attested(
    *,
    slug: str,
    command: str,
    step: Step,
    path_str: str,
    path_tuple: tuple[str, ...],
    events_path: Path,
    run_id: str,
    run_started_actor: str | None,
    project_root: Path,
    iteration: int | None = None,
    item_id: str | None = None,
    append_fn: Callable[[dict[str, Any]], Any],
    session: Any = None,
    run_dir: Path | None = None,
    writer_epoch_at_dispatch: int | None = None,
) -> GateDecision:
    matched, args = match_attested_command(command, step.command)
    if not matched:
        _reject(slug, "incoming command does not match plan[cursor]", abort=False)

    attestor_kind, attestor_id = validate_attested_identity(
        slug=slug,
        step=step,
        args=args,
        run_started_actor=run_started_actor,
    )

    decision = GateDecision(
        active=True,
        run_id=run_id,
        plan_step_id=path_str,
        events_path=events_path,
        reentry=False,
        step_kind="attested",
        slug=slug,
        plan_step_path=path_tuple,
        produces=step.produces,
        project_root=project_root,
        iteration=iteration,
        item_id=item_id,
        adapter=step.adapter,
        step_version=step.version,
        run_dir=run_dir,
        writer_epoch_at_dispatch=writer_epoch_at_dispatch,
        session_id=getattr(session, "id", None),
        session=session,
    )
    if item_id is not None:
        terminal = _TerminalEventRequest(
            "item_attested",
            {
                "plan_step_path": path_tuple,
                "item_id": item_id,
                "attestor_kind": attestor_kind,
                "attestor_id": attestor_id,
                "evidence": args.evidence,
                "step_version": step.version,
            },
        )
    else:
        terminal = _TerminalEventRequest(
            "step_attested",
            {
                "plan_step_path": path_str,
                "attestor_kind": attestor_kind,
                "attestor_id": attestor_id,
                "evidence": args.evidence,
                "step_version": step.version,
            },
        )
    inline_check_result: InlineCheckResult | None = None
    if step.produces:
        inline_events: list[dict[str, Any]] = []
        inline_check_result = _run_inline_checks(
            decision,
            step.produces,
            append_fn=inline_events.append,
        )
        if not inline_check_result.ok:
            decision = dataclasses.replace(
                decision,
                inline_check_result=(inline_check_result.name or "", inline_check_result.reason or ""),
            )
    _finalize_step(
        decision,
        terminal,
        append_mode=_ActiveWriterAppend(append_fn),
        inline_check_result=inline_check_result,
    )
    if iteration is not None:
        feedback = _extract_iterate_feedback(args.evidence)
        if feedback is not None:
            write_iteration_feedback(decision, feedback)
            append_fn(
                make_iteration_failed_event(
                    path_tuple,
                    iteration,
                    reason="iterate_feedback",
                    step_version=step.version,
                ),
            )
    return decision


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
) -> _ParentFinalizationContext | None:
    """Build a synthetic ``step_attested`` for a for_each host once all items
    are attested. SD-001: attestor is always ``system`` / ``gate.autoclose``
    (never inherits from the closing item). SD-004: optional bodies / any
    prior ``item_skipped`` event are loud failures, not silent.

    See FLAG-S1-001 / FLAG-S1-004. Single emit site is in ``_dispatch_attested``
    immediately after the ``item_attested`` ``append_event``; if another
    ``item_attested`` emit path appears later, it MUST route through this
    helper too or for_each closure regresses.
    """
    plan_path = project_root / "plan.json"
    try:
        plan = load_plan(plan_path)
        from astrid.core.task.plan_verbs import apply_mutations
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
) -> _ParentFinalizationContext | None:
    """Build a host ``step_completed`` when all code-repeat items completed."""
    if (
        not decision.active
        or decision.events_path is None
        or decision.project_root is None
        or decision.run_id is None
        or decision.item_id is None
    ):
        return
    plan_path = decision.project_root / "plan.json"
    try:
        plan = load_plan(plan_path)
        from astrid.core.task.plan_verbs import apply_mutations

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


def _append_via_decision(decision: GateDecision, event: dict[str, Any]) -> dict[str, Any]:
    if decision.session is None:
        raise TaskRunGateError(
            reason="writer session missing for task-run mutation",
            recovery=f"astrid attach {decision.slug or '<project>'}",
        )
    with writer_context_from_decision(
        decision,
        root=decision.project_root.parent if decision.project_root is not None else None,
    ) as writer:
        return writer.append(event)


def _append_finalized(
    decision: GateDecision,
    event: dict[str, Any],
    append_mode: _FinalizeAppendMode,
) -> dict[str, Any] | None:
    if append_mode == "decision":
        return _append_via_decision(decision, event)
    return append_mode.append_fn(event)


def _finalize_step(
    decision: GateDecision,
    terminal_event: _TerminalEventRequest | dict[str, Any],
    append_mode: _FinalizeAppendMode,
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
    if event.get("kind") == "item_attested":
        _maybe_autoclose_for_each_host(
            events_path=decision.events_path or Path(),
            path_tuple=decision.plan_step_path,
            project_root=decision.project_root or Path("."),
            slug=decision.slug or "",
            run_id=decision.run_id or "",
            append_fn=(
                append_mode.append_fn
                if isinstance(append_mode, _ActiveWriterAppend)
                else lambda ev: _append_via_decision(decision, ev)
            ),
            current_item_id=str(event.get("item_id") or "") or None,
        )
    elif event.get("kind") == "item_completed":
        _maybe_autocomplete_for_each_host(
            decision=decision,
            returncode=int(event.get("returncode") or 0),
            cost=cost,
        )


def record_dispatch_complete(decision: GateDecision, returncode: int) -> None:
    if not decision.active or decision.events_path is None or decision.plan_step_id is None:
        return
    if decision.step_kind == "attested":
        # attested steps are advanced by step_attested itself; do not double-emit
        return

    # Resolve adapter to get completion (cost, status) — the adapter owns the
    # completion logic, not the gate.
    run_ctx = _make_run_ctx(
        decision.slug or "",
        decision.run_id or "",
        decision.plan_step_path,
        decision.step_version,
        decision.project_root or Path("."),
        iteration=decision.iteration,
        item_id=decision.item_id,
    )
    # Load step from plan to get the full Step (for adapter.complete which needs produces).
    step = _load_step_for_decision(decision)
    adapter = _resolve_adapter(step) if step else None

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
        # requires_ack enforcement: cursor stays on step until non-stale ack arrives.
        # Do NOT emit step_completed for requires_ack steps — the ack event will advance.
        if step is not None and step.requires_ack:
            return
        terminal: _TerminalEventRequest
        completed_returncode = returncode if returncode != -1 else (complete_result.returncode or 0)
        if complete_result.status == "failed":
            terminal = _TerminalEventRequest(
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
            terminal = _TerminalEventRequest(
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
            terminal = _TerminalEventRequest(
                "item_completed",
                {
                    "plan_step_path": decision.plan_step_path,
                    "item_id": decision.item_id,
                    "returncode": completed_returncode,
                    "step_version": decision.step_version,
                },
            )
        else:
            terminal = _TerminalEventRequest(
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
        # Legacy path: no adapter info on decision — use raw returncode.
        completed_returncode = returncode
        cost_dict = None
        terminal = _TerminalEventRequest(
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
        inline_check_result = _run_inline_checks(
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
    """Read missing/mismatched artifact names from the step's remote_state.json sidecar.

    The remote-artifact adapter persists fetch results into ``remote_state.json``
    when fetch_artifacts returns ``awaiting_fetch``.  Returns (missing, mismatched)
    lists — empty lists if the sidecar is missing or unreadable.
    """
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
    from astrid.core.task.plan_verbs import apply_mutations
    effective = apply_mutations(plan, events)
    for path_tuple, s in iter_steps_with_path(effective):
        if path_tuple == decision.plan_step_path:
            return s
    return None


def record_nested_entered(decision: GateDecision, child_plan_hash: str) -> None:
    """Reserved for Phase 5 lifecycle verbs; gate emits inline in Phase 2."""
    if not decision.active or decision.events_path is None or decision.plan_step_id is None:
        return
    _append_via_decision(
        decision,
        make_nested_entered_event(decision.plan_step_id, child_plan_hash),
    )


def record_nested_exited(decision: GateDecision, returncode: int) -> None:
    """Reserved for Phase 5 lifecycle verbs; gate emits inline in Phase 2."""
    if not decision.active or decision.events_path is None or decision.plan_step_id is None:
        return
    _append_via_decision(
        decision,
        make_nested_exited_event(decision.plan_step_id, returncode),
    )


def command_for_argv(argv: Sequence[str]) -> str:
    tokens = [str(token) for token in argv]
    return " ".join(shlex.quote(token) for token in tokens)


def _normalize_command_string(command: str) -> str:
    try:
        return shlex.join(shlex.split(command))
    except ValueError:
        return command


def _compute_inline_plan_hash(plan: TaskPlan) -> str:
    digest = hashlib.sha256(canonical_event_json(plan.to_dict()).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _find_run_started_actor(events: Sequence[dict[str, Any]]) -> str | None:
    for event in events:
        if event.get("kind") == "run_started":
            started_by = event.get("started_by")
            if isinstance(started_by, str) and started_by.startswith("human:"):
                return started_by[len("human:"):]
            # Legacy read compatibility for pre-T5 run_started events.
            actor = event.get("actor")
            return actor if isinstance(actor, str) else None
    return None
