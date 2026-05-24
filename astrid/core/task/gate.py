"""Task-run dispatch gate.

Phase 2 attested/nested handling is kernel-only; Phase 5 will add the
``astrid ack`` / ``astrid next`` lifecycle verbs that drive the
``record_step_attested`` / ``record_nested_entered`` / ``record_nested_exited``
helpers exposed for symmetry below. The gate itself emits ``step_attested``,
``nested_entered``, and ``nested_exited`` events inline; the public helpers
have zero callers in Phase 2 (FLAG-007).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import shlex
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
from astrid.core.task.events import (
    canonical_event_json,
    make_cursor_rewind_event,
    make_for_each_expanded_event,
    make_item_attested_event,
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

ITERATE_FEEDBACK_PREFIX = "iterate_feedback="


class TaskRunGateError(RuntimeError):
    """Raised when task-mode dispatch is rejected."""

    def __init__(self, reason: str, recovery: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.recovery = recovery


@dataclass(frozen=True)
class GateDecision:
    active: bool
    run_id: str | None = None
    plan_step_id: str | None = None
    events_path: Path | None = None
    reentry: bool = False
    step_kind: str | None = None
    slug: str | None = None
    plan_step_path: tuple[str, ...] = ()
    produces: tuple[ProducesEntry, ...] = ()
    project_root: Path | None = None
    iteration: int | None = None
    item_id: str | None = None
    # Sprint 1 (T9) extensions — populated when a session is bound at
    # gate_command entry so post-dispatch record_* helpers can flow
    # through writer_context_from_decision.
    run_dir: Path | None = None
    writer_epoch_at_dispatch: int | None = None
    session_id: str | None = None
    session: Any = None  # astrid.core.session.model.Session | None
    # Sprint 3 (T14) adapter dispatch fields.
    step_version: int = 1
    adapter: str | None = None
    pid: int | None = None
    dispatch_event_hash: str | None = None
    # Only populated by _dispatch_attested path; code-step rewinds go through
    # the event log only. See FLAG-S1-005 (correctness-2 / callers-2): we MUST
    # NOT populate this from record_dispatch_complete — code-step rewinds are
    # intentionally NOT surfaced through cmd_ack's 'ack accepted but produces
    # check failed' branch (category error).
    inline_check_result: tuple[str, str] | None = None


@dataclass(frozen=True)
class AttestedArgs:
    agent: str | None
    evidence: tuple[str, ...] = ()
    item: str | None = None
    human: str | None = None


@dataclass
class _Frame:
    plan: TaskPlan
    path_prefix: tuple[str, ...]
    child_index: int = 0
    iteration: int | None = None
    item_id: str | None = None
    repeat_step_id: str | None = None


@dataclass
class _PendingProduces:
    names: set[str]
    step_version: int
    dispatch_event_hash: str | None = None


@dataclass
class CursorPath:
    frames: list[_Frame] = field(default_factory=list)
    for_each_progress: dict[str, dict[str, Any]] = field(default_factory=dict)
    pinned_failure: tuple[str, str] | None = None  # (reason, host_path) for iteration_exhausted=fail

    @property
    def at_root_done(self) -> bool:
        return len(self.frames) == 1 and self.frames[-1].child_index >= len(self.frames[-1].plan.steps)

    @property
    def top_exhausted(self) -> bool:
        top = self.frames[-1]
        return top.child_index >= len(top.plan.steps)


def derive_cursor(plan: TaskPlan, events: Sequence[dict[str, Any]], *, slug: str = "") -> CursorPath:
    """Replay ``events.jsonl`` left-to-right to reconstruct the path-stack cursor.

    Reconstructible from events alone (supports partial-replay resume):
    ``nested_entered`` pushes, ``nested_exited`` pops + advances parent,
    ``step_completed`` / ``step_attested`` mark a step advance-eligible iff it
    has no produces; otherwise advance is deferred until the contiguous block
    contains a ``produces_check_passed`` for every declared produces name.
    ``produces_check_failed`` / ``cursor_rewind`` clear pending state without
    advancing. ``iteration_started`` pushes an iteration frame; ``iteration_failed``
    pops it without advancing the host. ``for_each_expanded`` records the host's
    item set on the cursor (used as the source of truth — derive_cursor never
    re-reads disk during replay). ``item_started`` pushes a per-item frame;
    ``item_completed`` / ``item_attested`` pop the item frame and advance the
    host once every item is done. ``step_dispatched`` / ``run_started`` do not
    advance.
    """
    frames: list[_Frame] = [_Frame(plan=plan, path_prefix=(), child_index=0)]
    pending: list[_PendingProduces | None] = [None]
    latest_dispatch: dict[str, tuple[int, str | None]] = {}
    for_each_progress: dict[str, dict[str, Any]] = {}
    pinned_failure: tuple[str, str] | None = None
    for event in events:
        kind = event.get("kind")
        if kind == "iteration_exhausted":
            on_exhaust = event.get("on_exhaust")
            host_path = _path_str_from_event(event)
            if on_exhaust == "fail":
                pinned_failure = ("repeat.until max_iterations exhausted", host_path)
                continue
            if on_exhaust == "escalate":
                top = frames[-1]
                if top.child_index < len(top.plan.steps):
                    host_step = top.plan.steps[top.child_index]
                    override_plan = TaskPlan(
                        plan_id=f"__exhaust_{host_step.id}",
                        version=1,
                        steps=(_make_exhaust_override_step(slug, host_path),),
                    )
                    frames.append(
                        _Frame(
                            plan=override_plan,
                            path_prefix=top.path_prefix + (host_step.id,),
                            child_index=0,
                            repeat_step_id=host_step.id,
                        )
                    )
                    pending.append(None)
            continue
        if kind == "nested_entered":
            top = frames[-1]
            if top.child_index >= len(top.plan.steps):
                raise TaskRunGateError(
                    reason="nested_entered points past end of frame",
                    recovery="inspect events.jsonl",
                )
            step = top.plan.steps[top.child_index]
            if not is_group_step(step):
                raise TaskRunGateError(
                    reason="nested_entered did not land on a group step",
                    recovery="inspect events.jsonl",
                )
            frames.append(
                _Frame(
                    plan=step.plan,
                    path_prefix=top.path_prefix + (step.id,),
                    child_index=0,
                )
            )
            pending.append(None)
        elif kind == "nested_exited":
            if len(frames) <= 1:
                raise TaskRunGateError(
                    reason="nested_exited at root frame",
                    recovery="inspect events.jsonl",
                )
            frames.pop()
            pending.pop()
            frames[-1].child_index += 1
            pending[-1] = None
        elif kind == "iteration_started":
            top = frames[-1]
            if top.child_index >= len(top.plan.steps):
                continue
            host_step = top.plan.steps[top.child_index]
            iteration = int(event.get("iteration", 1))
            frames.append(_make_iteration_frame(host_step, top.path_prefix, iteration))
            pending.append(None)
        elif kind == "iteration_failed":
            if frames[-1].repeat_step_id is None:
                continue
            found = _repeat_host_for_top_frame(frames)
            if found is not None:
                _parent, host = found
                if not _event_matches_step_version(event, host):
                    continue
            frames.pop()
            pending.pop()
            pending[-1] = None
        elif kind == "for_each_expanded":
            host_path = _path_str_from_event(event)
            host_step = _current_step_for_path(frames, host_path)
            if host_step is not None and not _event_matches_step_version(event, host_step):
                continue
            items = tuple(event.get("item_ids") or ())
            for_each_progress.setdefault(host_path, {"items": items, "completed": set()})
            for_each_progress[host_path]["items"] = items
        elif kind == "item_started":
            top = frames[-1]
            if top.child_index >= len(top.plan.steps):
                continue
            host_step = top.plan.steps[top.child_index]
            if not _event_matches_step_version(event, host_step):
                continue
            item_id = event.get("item_id")
            if not isinstance(item_id, str):
                continue
            frames.append(_make_item_frame(host_step, top.path_prefix, item_id))
            pending.append(None)
        elif kind in ("item_completed", "item_attested", "item_skipped"):
            host_path = _path_str_from_event(event)
            item_id = event.get("item_id")
            if not isinstance(item_id, str):
                continue
            item_step = _current_item_step(frames, item_id)
            if item_step is not None and not _event_matches_step_version(event, item_step):
                continue
            entry = for_each_progress.setdefault(host_path, {"items": (), "completed": set()})
            entry["completed"].add(item_id)
            if frames[-1].item_id == item_id:
                frames.pop()
                pending.pop()
                pending[-1] = None
            # If all items now completed and the host's parent frame is on top, advance host.
            if entry["items"] and set(entry["items"]) <= entry["completed"]:
                host_segments = host_path.split(STEP_PATH_SEP) if host_path else []
                expected_parent_prefix = tuple(host_segments[:-1])
                if tuple(frames[-1].path_prefix) == expected_parent_prefix:
                    if frames[-1].child_index < len(frames[-1].plan.steps):
                        candidate = frames[-1].plan.steps[frames[-1].child_index]
                        if host_segments and candidate.id == host_segments[-1]:
                            frames[-1].child_index += 1
                            pending[-1] = None
        elif kind in ("step_completed", "step_attested", "step_skipped"):
            # #20 fix — repeat.until cursor stall: when the topmost frame is
            # an iteration frame whose body is already exhausted (typically
            # because the body's step_attested + produces_check_passed
            # already advanced its child_index), and a NEW step_attested for
            # a different step arrives (e.g. the host's sibling like
            # `finalize`), the prior code blocked at "top.child_index >= len"
            # and silently dropped the event. The iter frame was popped by
            # _finalize_cursor only AFTER the replay loop ended, by which
            # time the sibling's step_attested was already lost. The cursor
            # then stalled forever on the host's sibling.
            #
            # Fix: pop exhausted iter frames inline first, advancing the
            # host's child_index, THEN re-evaluate against the (now parent)
            # frame. Item frames are excluded — they're popped by their
            # specific item_* events, not by sibling step_attested.
            while (
                len(frames) > 1
                and frames[-1].repeat_step_id is not None
                and frames[-1].item_id is None
                and frames[-1].child_index >= len(frames[-1].plan.steps)
                and not _top_frame_needs_repeat_until_evaluation(frames)
            ):
                frames.pop()
                pending.pop()
                frames[-1].child_index += 1
                pending[-1] = None
            top = frames[-1]
            if top.child_index >= len(top.plan.steps):
                continue
            step = top.plan.steps[top.child_index]
            # T1 / FLAG-S1-001: a for_each host's autoclose step_attested can
            # arrive *after* item_attested already advanced child_index past
            # the host. Verify the event's step path matches the current
            # child before consuming it as an advance signal — otherwise the
            # autoclose silently skips past the host's sibling.
            event_path = _path_str_from_event(event)
            expected_path = STEP_PATH_SEP.join(list(top.path_prefix) + [step.id])
            if event_path and event_path != expected_path:
                continue
            if not _event_matches_step_version(event, step):
                continue
            dispatch_event_hash = _current_dispatch_hash(
                latest_dispatch, expected_path, step.version
            )
            if kind == "step_completed" and not _event_matches_dispatch_hash(
                event, dispatch_event_hash
            ):
                continue
            produces = getattr(step, "produces", ())
            # Skipped steps bypass produces-check gating entirely — the
            # cursor advances on the skip event without waiting for any
            # produces_check_passed coverage.
            if kind == "step_skipped" or not produces:
                top.child_index += 1
                pending[-1] = None
            else:
                pending[-1] = _PendingProduces(
                    names={entry.name for entry in produces},
                    step_version=step.version,
                    dispatch_event_hash=dispatch_event_hash,
                )
        elif kind == "produces_check_passed":
            current = pending[-1]
            if current is not None:
                if not _event_matches_pending(event, current):
                    continue
                name = event.get("produces_name")
                current.names.discard(name)
                if not current.names:
                    frames[-1].child_index += 1
                    pending[-1] = None
        elif kind in ("produces_check_failed", "cursor_rewind"):
            current = pending[-1]
            if current is None or _event_matches_pending(event, current):
                pending[-1] = None
        elif kind == "step_dispatched":
            event_path = _path_str_from_event(event)
            if event_path:
                latest_dispatch[event_path] = (
                    _event_step_version(event),
                    event.get("hash") if isinstance(event.get("hash"), str) else None,
                )
            pending[-1] = None
        # run_started / iteration_exhausted: no-op for cursor
    _finalize_cursor(frames, pending, for_each_progress)
    return CursorPath(frames=frames, for_each_progress=for_each_progress, pinned_failure=pinned_failure)


def _make_iteration_frame(host_step: Any, parent_prefix: tuple[str, ...], iteration: int) -> _Frame:
    body = dataclasses.replace(host_step, repeat=None) if hasattr(host_step, "repeat") else host_step
    body_plan = TaskPlan(plan_id=f"__iter_{host_step.id}_{iteration}", version=1, steps=(body,))
    return _Frame(
        plan=body_plan,
        path_prefix=parent_prefix,
        child_index=0,
        iteration=iteration,
        repeat_step_id=host_step.id,
    )


def _make_item_frame(host_step: Any, parent_prefix: tuple[str, ...], item_id: str) -> _Frame:
    body = dataclasses.replace(host_step, repeat=None) if hasattr(host_step, "repeat") else host_step
    body_plan = TaskPlan(plan_id=f"__item_{host_step.id}_{item_id}", version=1, steps=(body,))
    return _Frame(
        plan=body_plan,
        path_prefix=parent_prefix,
        child_index=0,
        item_id=item_id,
        repeat_step_id=host_step.id,
    )


def _repeat_host_for_top_frame(frames: list[_Frame]) -> tuple[_Frame, Step] | None:
    if len(frames) < 2:
        return None
    top = frames[-1]
    if top.repeat_step_id is None or top.item_id is not None:
        return None
    parent = frames[-2]
    if parent.child_index >= len(parent.plan.steps):
        return None
    host = parent.plan.steps[parent.child_index]
    if host.id != top.repeat_step_id:
        return None
    return parent, host


def _top_frame_needs_repeat_until_evaluation(frames: list[_Frame]) -> bool:
    found = _repeat_host_for_top_frame(frames)
    if found is None:
        return False
    _parent, host = found
    repeat = getattr(host, "repeat", None)
    return (
        isinstance(repeat, RepeatUntil)
        and not is_legacy_repeat_until_condition(repeat.condition)
    )


def _current_repeat_context(frames: Sequence[_Frame]) -> tuple[int | None, str | None]:
    for frame in reversed(frames):
        if frame.repeat_step_id is not None:
            return frame.iteration, frame.item_id
    return None, None


def _finalize_cursor(
    frames: list[_Frame],
    pending: list[_PendingProduces | None],
    for_each_progress: dict[str, dict[str, Any]],
) -> None:
    """Pop exhausted iteration/item frames after event replay.

    For verifier_passes / approve cases, the iteration frame ends with
    ``produces_check_passed`` coverage or ``step_attested`` (no following
    iteration_failed) — the iter frame's child_index is at end-of-plan.
    Pop it and advance the host. Same for item frames whose item is in
    the for_each_progress.completed set.
    """
    while True:
        top = frames[-1]
        if top.repeat_step_id is None:
            break
        if top.child_index < len(top.plan.steps):
            break
        if top.item_id is not None:
            host_path_segments = top.path_prefix + (top.repeat_step_id,)
            host_path = STEP_PATH_SEP.join(host_path_segments)
            entry = for_each_progress.get(host_path)
            frames.pop()
            pending.pop()
            pending[-1] = None
            if entry is not None and entry["items"] and set(entry["items"]) <= entry["completed"]:
                frames[-1].child_index += 1
                pending[-1] = None
        else:
            if _top_frame_needs_repeat_until_evaluation(frames):
                break
            frames.pop()
            pending.pop()
            frames[-1].child_index += 1
            pending[-1] = None


def _path_str_from_event(event: dict[str, Any]) -> str:
    path = event.get("plan_step_path")
    if isinstance(path, list):
        return STEP_PATH_SEP.join(str(p) for p in path)
    pid = event.get("plan_step_id")
    return pid if isinstance(pid, str) else ""


def _event_step_version(event: dict[str, Any]) -> int:
    raw = event.get("step_version", 1)
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 1:
        return raw
    return 1


def _event_matches_step_version(event: dict[str, Any], step: Step) -> bool:
    return _event_step_version(event) == step.version


def _current_dispatch_hash(
    latest_dispatch: dict[str, tuple[int, str | None]],
    path_str: str,
    step_version: int,
) -> str | None:
    version_and_hash = latest_dispatch.get(path_str)
    if version_and_hash is None:
        return None
    version, dispatch_hash = version_and_hash
    if version != step_version:
        return None
    return dispatch_hash


def _event_matches_dispatch_hash(
    event: dict[str, Any],
    current_dispatch_hash: str | None,
) -> bool:
    event_hash = event.get("dispatch_event_hash")
    if event_hash is None:
        return True
    return isinstance(event_hash, str) and event_hash == current_dispatch_hash


def _event_matches_pending(event: dict[str, Any], pending: _PendingProduces) -> bool:
    if _event_step_version(event) != pending.step_version:
        return False
    return _event_matches_dispatch_hash(event, pending.dispatch_event_hash)


def _current_item_step(frames: Sequence[_Frame], item_id: str) -> Step | None:
    top = frames[-1]
    if top.item_id == item_id and top.plan.steps:
        return top.plan.steps[0]
    if top.child_index < len(top.plan.steps):
        candidate = top.plan.steps[top.child_index]
        if getattr(candidate, "repeat", None) is not None:
            return candidate
    return None


def _current_step_for_path(frames: Sequence[_Frame], path_str: str) -> Step | None:
    path_tuple = tuple(path_str.split(STEP_PATH_SEP)) if path_str else ()
    if not path_tuple:
        return None
    for frame in reversed(frames):
        candidate_path = frame.path_prefix + (
            frame.plan.steps[frame.child_index].id,
        ) if frame.child_index < len(frame.plan.steps) else ()
        if candidate_path == path_tuple:
            return frame.plan.steps[frame.child_index]
    return None


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
                _enter_repeat_for_each(
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
        pass
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
            append_fn=writer.append,
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
            append_fn=writer.append,
            session=writer.session,
            run_dir=writer.run_dir,
            writer_epoch_at_dispatch=writer.expected_writer_epoch,
        )
    raise TaskRunGateError(
        reason=f"unexpected step kind: {type(current_step).__name__}",
        recovery=f"astrid next --project {slug}",
    )


def _count_iteration_failed(events: Sequence[dict[str, Any]], host_path: str) -> int:
    return sum(
        1
        for ev in events
        if isinstance(ev, dict)
        and ev.get("kind") == "iteration_failed"
        and _path_str_from_event(ev) == host_path
    )


EXHAUST_OVERRIDE_ID = "exhaust-override"


def _has_iteration_exhausted(events: Sequence[dict[str, Any]], host_path: str) -> dict[str, Any] | None:
    for ev in events:
        if (
            isinstance(ev, dict)
            and ev.get("kind") == "iteration_exhausted"
            and _path_str_from_event(ev) == host_path
        ):
            return ev
    return None


def _make_exhaust_override_step(slug: str, host_path: str) -> Step:
    override_path = f"{host_path}{STEP_PATH_SEP}{EXHAUST_OVERRIDE_ID}"
    return Step(
        id=EXHAUST_OVERRIDE_ID,
        adapter="manual",
        command=f"ack --project {slug} --step {override_path}",
        instructions="repeat.until max_iterations exhausted; human override required to advance",
        ack=AckRule(kind="human"),
        requires_ack=True,
        assignee="any-human",
    )


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
    except (TaskPlanError, TaskRunGateError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
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
        target_path = (target_id,)
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
) -> str | None:
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
    if target_item is None:
        # Pick first not-yet-completed item.
        target_item = next((it for it in items if it not in completed), None)
    if target_item is None:
        # All items done — finalize will pop. Just return.
        return None
    if target_item not in items:
        _reject(slug, f"for_each --item {target_item!r} not in expanded item set", abort=False)
    if target_item in completed:
        _reject(slug, f"for_each --item {target_item!r} already completed", abort=False)
    path_tuple = parent_prefix + (host.id,)
    append_fn(make_item_started_event(path_tuple, target_item, step_version=host.version))
    cursor.frames.append(_make_item_frame(host, parent_prefix, target_item))
    return target_item


def _resolve_adapter(step: Step):
    """Return the concrete adapter instance for ``step.adapter``."""
    from astrid.core.adapter.local import LocalAdapter
    from astrid.core.adapter.manual import ManualAdapter
    from astrid.core.adapter.remote_artifact import REMOTE_ARTIFACT_DEFERRAL

    if step.adapter == "local":
        return LocalAdapter()
    if step.adapter == "manual":
        return ManualAdapter()
    if step.adapter == "remote-artifact":
        raise TaskRunGateError(
            reason=f"{REMOTE_ARTIFACT_DEFERRAL} step={step.id!r}",
            recovery="use adapter 'local' or 'manual'",
        )
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
    if command != step.command:
        _reject(slug, "incoming command does not match plan[cursor]", abort=False)

    adapter = _resolve_adapter(step)
    step_version = step.version
    run_ctx = _make_run_ctx(
        slug, run_id, path_tuple, step_version, project_root,
        iteration=iteration, item_id=item_id,
    )

    if reentry:
        # FLAG-P3-005: scan back to the latest event for THIS plan_step_id rather than events[-1];
        # produces_check_failed must permit redispatch (cursor hasn't advanced).
        events = read_events(events_path)
        latest = _latest_event_for_step(events, path_str, step_version=step_version)
        if (
            isinstance(latest, dict)
            and latest.get("kind") == "step_dispatched"
            and latest.get("command") == command
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
        if isinstance(latest, dict) and latest.get("kind") == "produces_check_failed":
            apply_task_run_env(run_id, slug, path_str, item_id=item_id, iteration=iteration)
            dispatch_result, dispatch_event_hash = _adapter_dispatch(
                adapter, step, run_ctx, path_str, command, append_fn
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
        adapter, step, run_ctx, path_str, command, append_fn
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

    if item_id is not None:
        event = make_item_attested_event(
            path_tuple,
            item_id,
            attestor_kind=attestor_kind,
            attestor_id=attestor_id,
            evidence=args.evidence,
            step_version=step.version,
        )
    else:
        event = make_step_attested_event(
            path_str,
            attestor_kind,
            attestor_id,
            args.evidence,
            step_version=step.version,
        )
    if is_author_test_mode():
        event["source"] = "author_test"
    append_fn(event)
    # FLAG-S1-001 / all_locations-3: after appending item_attested, route
    # through the centralized autoclose helper. Any future site that emits
    # item_attested MUST also call this helper, or for_each host closure
    # silently regresses (see T1 / SD-001 / SD-004).
    if item_id is not None:
        _maybe_autoclose_for_each_host(
            events_path=events_path,
            path_tuple=path_tuple,
            project_root=project_root,
            slug=slug,
            run_id=run_id,
            append_fn=append_fn,
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
    if step.produces:
        # FLAG-S1-005: detect a fresh produces_check_failed pair attributable
        # to this dispatch by scanning the events tail appended during
        # _run_inline_checks. We deliberately do NOT push this responsibility
        # into _run_inline_checks itself, because that helper is also called
        # from record_dispatch_complete (code-step path) where we MUST NOT
        # surface the result through GateDecision.inline_check_result.
        pre_inline = read_events(events_path) if events_path.exists() else []
        pre_inline_count = len(pre_inline)
        _run_inline_checks(decision, step.produces)
        new_tail = read_events(events_path)[pre_inline_count:]
        for ev in new_tail:
            if isinstance(ev, dict) and ev.get("kind") == "produces_check_failed":
                name = str(ev.get("produces_name") or "")
                reason = str(ev.get("reason") or "")
                import dataclasses as _dc
                decision = _dc.replace(decision, inline_check_result=(name, reason))
                break
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
) -> None:
    """Append a synthetic ``step_attested`` for a for_each host once all items
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
    except Exception:
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
    auto_event = make_step_attested_event(
        STEP_PATH_SEP.join(path_tuple),
        "system",
        "gate.autoclose",
        ("auto-close: all items attested",),
        step_version=host_step.version,
    )
    if is_author_test_mode():
        auto_event["source"] = "author_test"
    append_fn(auto_event)


def _extract_iterate_feedback(evidence: tuple[str, ...]) -> str | None:
    for item in evidence:
        if item.startswith(ITERATE_FEEDBACK_PREFIX):
            return item[len(ITERATE_FEEDBACK_PREFIX):]
    return None


def write_iteration_feedback(decision: GateDecision, feedback: str) -> None:
    if (
        decision.slug is None
        or decision.run_id is None
        or decision.iteration is None
        or decision.project_root is None
        or not decision.plan_step_path
    ):
        return
    iter_dir = step_dir_for_path(
        decision.slug,
        decision.run_id,
        decision.plan_step_path,
        step_version=decision.step_version,
        iteration=decision.iteration,
        root=decision.project_root.parent,
    )
    iter_dir.mkdir(parents=True, exist_ok=True)
    feedback_path = iter_dir / "feedback.json"
    cumulative: list[str] = []
    if decision.iteration > 1:
        prev_dir = step_dir_for_path(
            decision.slug,
            decision.run_id,
            decision.plan_step_path,
            step_version=decision.step_version,
            iteration=decision.iteration - 1,
            root=decision.project_root.parent,
        )
        prev_path = prev_dir / "feedback.json"
        if prev_path.exists():
            try:
                prev = json.loads(prev_path.read_text(encoding="utf-8"))
                if isinstance(prev, list):
                    cumulative = [str(x) for x in prev]
            except (json.JSONDecodeError, OSError):
                cumulative = []
    cumulative.append(feedback)
    write_json_sidecar(feedback_path, cumulative)


def match_attested_command(incoming: str, expected_prefix: str) -> tuple[bool, AttestedArgs]:
    """Strip identity/evidence/item tokens and compare the canonical remainder.
    """
    try:
        tokens = shlex.split(incoming)
    except ValueError:
        return False, AttestedArgs(agent=None)
    agent: str | None = None
    human: str | None = None
    item: str | None = None
    evidence: list[str] = []
    remaining: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "--agent" and i + 1 < len(tokens):
            agent = tokens[i + 1]
            i += 2
            continue
        if token == "--human" and i + 1 < len(tokens):
            human = tokens[i + 1]
            i += 2
            continue
        if token == "--item" and i + 1 < len(tokens):
            item = tokens[i + 1]
            i += 2
            continue
        if token == "--evidence" and i + 1 < len(tokens):
            evidence.append(tokens[i + 1])
            i += 2
            continue
        remaining.append(token)
        i += 1
    try:
        expected_tokens = shlex.split(expected_prefix)
    except ValueError:
        return False, AttestedArgs(
            agent=agent, human=human, evidence=tuple(evidence), item=item
        )
    rejoined = " ".join(shlex.quote(token) for token in remaining)
    expected = " ".join(shlex.quote(token) for token in expected_tokens)
    matched = rejoined == expected
    return matched, AttestedArgs(
        agent=agent, human=human, evidence=tuple(evidence), item=item
    )


def validate_attested_identity(
    *,
    slug: str,
    step: Step,
    args: AttestedArgs,
    run_started_actor: str | None,
) -> tuple[Literal["agent", "human"], str]:
    human = args.human
    supplied = sum(value is not None for value in (args.agent, args.human))
    if supplied == 0:
        _reject(slug, "attested step requires --agent or --human", abort=False)
    if supplied > 1:
        _reject(slug, "attested step rejects multiple identity flags", abort=False)
    if step.ack.kind == "agent":
        if args.agent is None:
            _reject(slug, "attested step ack.kind=agent requires --agent", abort=False)
        return "agent", args.agent
    # ack.kind == "human"; legacy plan ack.kind="actor" is normalized at load time.
    if human is None:
        _reject(slug, "attested step ack.kind=human requires --human", abort=False)
    if is_author_test_mode():
        # Author-test mode: skip ASTRID_ACTOR-match and self-ack checks so the
        # harness can drive attestations under a synthetic human identity.
        return "human", human
    if task_actor_env() != human:
        _reject(slug, "attested --human does not match ASTRID_ACTOR env", abort=False)
    # FLAG-005: self-ack rejection only applies to human attestations because agents
    # do not start runs in V1; an agent_id on run_started would be required to
    # symmetrically block agent self-acks, which is out of scope for Phase 2.
    if (
        run_started_actor is not None
        and run_started_actor == human
        and task_actor_env() == human
    ):
        _reject(slug, "self-ack rejected", abort=False)
    return "human", human


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
        if decision.adapter == "remote-artifact":
            from astrid.core.adapter.remote_artifact import REMOTE_ARTIFACT_DEFERRAL

            raise TaskRunGateError(
                reason=f"{REMOTE_ARTIFACT_DEFERRAL} step={decision.plan_step_id!r}",
                recovery="use adapter 'local' or 'manual'",
            )
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
        if complete_result.status == "failed":
            _append_via_decision(
                decision,
                make_step_failed_event(
                    decision.plan_step_id,
                    complete_result.returncode,
                    reason=complete_result.reason,
                    cost=cost_dict,
                    adapter=decision.adapter,
                    step_version=decision.step_version,
                    dispatch_event_hash=decision.dispatch_event_hash,
                ),
            )
        elif complete_result.status == "awaiting_fetch":
            missing, mismatched = _read_awaiting_fetch_items(run_ctx)
            _append_via_decision(
                decision,
                make_step_awaiting_fetch_event(
                    decision.plan_step_id,
                    missing=missing,
                    mismatched=mismatched,
                    reason=complete_result.reason,
                    adapter=decision.adapter,
                    step_version=decision.step_version,
                    dispatch_event_hash=decision.dispatch_event_hash,
                ),
            )
        else:
            _append_via_decision(
                decision,
                make_step_completed_event(
                    decision.plan_step_id,
                    returncode if returncode != -1 else (complete_result.returncode or 0),
                    cost=cost_dict,
                    adapter=decision.adapter,
                    step_version=decision.step_version,
                    dispatch_event_hash=decision.dispatch_event_hash,
                ),
            )
    else:
        # Legacy path: no adapter info on decision — use raw returncode.
        _append_via_decision(
            decision,
            make_step_completed_event(
                decision.plan_step_id,
                returncode,
                step_version=decision.step_version,
                dispatch_event_hash=decision.dispatch_event_hash,
            ),
        )

    if decision.produces:
        _run_inline_checks(decision, decision.produces)


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


# step_dir_for_path is the ONLY directory API used in this gate path (FLAG-P3-001).
def _run_inline_checks(decision: GateDecision, produces: tuple[ProducesEntry, ...]) -> bool:
    if (
        decision.events_path is None
        or decision.run_id is None
        or decision.slug is None
        or decision.project_root is None
        or not decision.plan_step_path
    ):
        return True
    projects_root = decision.project_root.parent
    step_dir = step_dir_for_path(
        decision.slug,
        decision.run_id,
        decision.plan_step_path,
        step_version=decision.step_version,
        iteration=decision.iteration,
        item_id=decision.item_id,
        root=projects_root,
    )
    produces_root = step_dir / "produces"
    for entry in produces:
        artifact_path = produces_root / entry.path
        result = entry.check.run(artifact_path)
        if not result.ok:
            _append_via_decision(
                decision,
                make_produces_check_failed_event(
                    decision.plan_step_path,
                    entry.name,
                    check_id=entry.check.check_id,
                    reason=result.reason,
                    step_version=decision.step_version,
                    dispatch_event_hash=decision.dispatch_event_hash,
                ),
            )
            if decision.iteration is not None:
                _append_via_decision(
                    decision,
                    make_iteration_failed_event(
                        decision.plan_step_path,
                        decision.iteration,
                        reason=f"produces check failed: {entry.name}",
                        step_version=decision.step_version,
                    ),
                )
            else:
                _append_via_decision(
                    decision,
                    make_cursor_rewind_event(
                        decision.plan_step_path,
                        reason=f"produces check failed: {entry.name}",
                        step_version=decision.step_version,
                        dispatch_event_hash=decision.dispatch_event_hash,
                    ),
                )
            return False
        cas_sha256 = _intern_produces_artifact(decision, artifact_path)
        _append_via_decision(
            decision,
            make_produces_check_passed_event(
                decision.plan_step_path,
                entry.name,
                check_id=entry.check.check_id,
                cas_sha256=cas_sha256,
                step_version=decision.step_version,
                dispatch_event_hash=decision.dispatch_event_hash,
            ),
        )
    return True


def _intern_produces_artifact(decision: GateDecision, artifact_path: Path) -> str | None:
    if decision.project_root is None:
        return None
    if artifact_path.is_symlink():
        return None
    cas_target = intern(decision.project_root, artifact_path)
    link_into_produces(cas_target, artifact_path)
    return cas_target.name


def record_step_attested(
    decision: GateDecision,
    attestor_kind: str,
    attestor_id: str,
    evidence: tuple[str, ...] = (),
) -> None:
    """Reserved for Phase 5 lifecycle verbs; gate emits inline in Phase 2."""
    if not decision.active or decision.events_path is None or decision.plan_step_id is None:
        return
    _append_via_decision(
        decision,
        make_step_attested_event(
            decision.plan_step_id,
            attestor_kind,
            attestor_id,
            evidence,
            step_version=decision.step_version,
        ),
    )


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
    if len(tokens) >= 3 and Path(tokens[0]).name.startswith("python") and tokens[1:3] == ["-m", "astrid"]:
        tokens = tokens[3:]
    elif tokens and Path(tokens[0]).name.endswith("astrid"):
        tokens = tokens[1:]
    return " ".join(shlex.quote(token) for token in tokens)


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


def _reject(slug: str, reason: str, *, abort: bool) -> NoReturn:
    verb = "abort" if abort else "next"
    raise TaskRunGateError(reason=reason, recovery=f"astrid {verb} --project {slug}")
