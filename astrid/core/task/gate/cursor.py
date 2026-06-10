"""Cursor / path / frame helpers and exhaust-override Step builder."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Sequence

from astrid.core.contracts.run_status import STEP_TERMINAL_KINDS
from astrid.core.task.gate.base import TaskRunGateError
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    AckRule,
    RepeatUntil,
    Step,
    TaskPlan,
    is_group_step,
    is_legacy_repeat_until_condition,
)

_CURSOR_ADVANCE_KINDS = STEP_TERMINAL_KINDS


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


@dataclass(frozen=True)
class _ForEachSelection:
    item_id: str | None
    no_pending: bool = False


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
    ``nested_entered`` pushes, ``nested_exited`` pops + advances parent.
    Canonical step terminal events advance the step cursor: successful terminal
    events with produces wait for matching ``produces_check_passed`` coverage,
    while failed/skipped terminal events resolve the step immediately.
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
    last_item_terminal: dict[str, str] = {}
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
                    code="nested_entered_past_end",
                )
            step = top.plan.steps[top.child_index]
            if not is_group_step(step):
                raise TaskRunGateError(
                    reason="nested_entered did not land on a group step",
                    recovery="inspect events.jsonl",
                    code="nested_entered_not_group",
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
                    code="nested_exited_at_root",
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
            last_item_terminal[host_path] = item_id
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
                            produces = getattr(candidate, "produces", ())
                            if produces:
                                pending[-1] = _PendingProduces(
                                    names={entry.name for entry in produces},
                                    step_version=candidate.version,
                                    dispatch_event_hash=None,
                                )
                            else:
                                frames[-1].child_index += 1
                                pending[-1] = None
        elif kind in _CURSOR_ADVANCE_KINDS:
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
            event_path = _path_str_from_event(event)
            if (
                top.repeat_step_id is not None
                and top.item_id is None
                and top.child_index >= len(top.plan.steps)
                and kind == "step_completed"
                and event_path == STEP_PATH_SEP.join(top.path_prefix + (top.repeat_step_id,))
            ):
                frames.pop()
                pending.pop()
                frames[-1].child_index += 1
                pending[-1] = None
                continue
            if top.child_index >= len(top.plan.steps):
                continue
            step = top.plan.steps[top.child_index]
            # T1 / FLAG-S1-001: a for_each host's autoclose step_attested can
            # arrive *after* item_attested already advanced child_index past
            # the host. Verify the event's step path matches the current
            # child before consuming it as an advance signal — otherwise the
            # autoclose silently skips past the host's sibling.
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
            # Failed/skipped terminal events bypass produces-check gating entirely.
            if kind in ("step_failed", "step_skipped") or not produces:
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
            host_path = _path_str_from_event(event)
            failed_item_id = last_item_terminal.get(host_path)
            if failed_item_id is not None and host_path in for_each_progress:
                for_each_progress[host_path]["completed"].discard(failed_item_id)
                if frames[-1].item_id != failed_item_id:
                    host_segments = host_path.split(STEP_PATH_SEP) if host_path else []
                    expected_parent_prefix = tuple(host_segments[:-1])
                    if tuple(frames[-1].path_prefix) == expected_parent_prefix:
                        if frames[-1].child_index < len(frames[-1].plan.steps):
                            host_step = frames[-1].plan.steps[frames[-1].child_index]
                            if host_segments and host_step.id == host_segments[-1]:
                                frames.append(
                                    _make_item_frame(
                                        host_step,
                                        frames[-1].path_prefix,
                                        failed_item_id,
                                    )
                                )
                                pending.append(None)
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


EXHAUST_OVERRIDE_ID = "exhaust-override"


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
