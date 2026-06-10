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
import shlex
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, NoReturn, Sequence

from astrid.core.contracts.run_status import TASK_FINALIZABLE_EVENT_KINDS
from astrid.core.session.current_run_state import read_current_run_state
from astrid.core.foundation.project_paths import project_dir
from astrid.core.session.writer import writer_context_for_project, writer_context_from_decision
from astrid.core.task.cas import intern, link_into_produces
from astrid.core.project.sidecar import write_json_sidecar
from astrid.core.task.env import (
    apply_task_run_env,
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
    make_step_completed_event,
    make_step_dispatched_event,
    read_events,
)
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    AckRule,
    ProducesEntry,
    RepeatForEach,
    RepeatUntil,
    TaskPlan,
    TaskPlanError,
    compute_plan_hash,
    is_legacy_repeat_until_condition,
    is_attested_kind,
    is_code_kind,
    is_group_step,
    load_plan,
    parse_from_ref,
    parse_repeat_until_expression,
    resolve_produces_ref,
    step_dir_for_path,
)
from astrid.core.task.gate.base import (
    GateDecision,
    InlineCheckResult,
    ITERATE_FEEDBACK_PREFIX,
    TaskRunGateError,
    _reject,
)
from astrid.core.task.gate.cursor import (
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
from astrid.core.task.gate.attestation import (
    AttestedArgs,
    _extract_iterate_feedback,
    match_attested_command,
    validate_attested_identity,
    write_iteration_feedback,
)
from astrid.core.task.gate.repeat import (
    _build_autoclose_for_each_host_context,
    _build_autocomplete_for_each_host_context,
    _count_iteration_failed,
    _enter_repeat_for_each,
    _enter_repeat_until,
    _evaluate_repeat_until_expression,
    _has_iteration_exhausted,
    _json_field,
    _maybe_autoclose_for_each_host,
    _maybe_autocomplete_for_each_host,
    _resolve_for_each_items,
)
from astrid.core.task.gate.checks import (
    _intern_produces_artifact,
    _run_inline_checks,
)
from astrid.core.task.gate.dispatch import (
    _adapter_dispatch,
    _code_decision,
    _dispatch_attested,
    _dispatch_code,
    _latest_event_for_step,
    _make_run_ctx,
    _resolve_adapter,
)
from astrid.core.task.gate.finalize import (
    _finalize_step as _gate_finalize_step,
    _load_step_for_decision,
    record_dispatch_complete,
    record_nested_entered,
    record_nested_exited,
)

_GATE_FINALIZABLE_EVENT_KINDS = TASK_FINALIZABLE_EVENT_KINDS


@dataclass(frozen=True)
class _ActiveWriterAppend:
    append_fn: Callable[[dict[str, Any]], Any]


_FinalizeAppendMode = Literal["decision"] | _ActiveWriterAppend


@dataclass(frozen=True)
class _TerminalEventRequest:
    kind: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if self.kind not in _GATE_FINALIZABLE_EVENT_KINDS:
            raise ValueError(f"unknown terminal event kind: {self.kind!r}")


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
    from astrid.core.task.plan.verbs import (
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
        raise TaskRunGateError(
            reason=reason,
            recovery=f"astrid abort --project {slug}",
            code="pinned_failure",
        )
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
        code="unexpected_step_kind",
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


def _append_via_decision(decision: GateDecision, event: dict[str, Any]) -> dict[str, Any]:
    if decision.session is None:
        raise TaskRunGateError(
            reason="writer session missing for task-run mutation",
            recovery=f"astrid attach {decision.slug or '<project>'}",
            code="writer_session_missing",
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
    # Keep the terminal-event constructor map visible on the gate facade for
    # characterization tests and patch-driven debugging, while delegating the
    # real implementation to gate_finalize.py.
    if False:  # pragma: no cover
        make_step_completed_event(plan_step_path=(), returncode=0)
        make_step_failed_event(plan_step_path=(), returncode=1)
        make_step_attested_event(plan_step_path=(), attestor="agent:test")
        make_item_completed_event(plan_step_path=(), item_id="", returncode=0)
        make_item_attested_event(plan_step_path=(), item_id="", attestor="agent:test")
        make_step_awaiting_fetch_event(path_str="", missing=[], mismatched=[])
    _gate_finalize_step(
        decision,
        terminal_event,
        append_mode,
        inline_check_result=inline_check_result,
        cost=cost,
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
