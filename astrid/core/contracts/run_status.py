"""Canonical run-status vocabulary.

`RunStatus` is the single source of truth for the lifecycle state of a run.
Before this module the same notion was spelled with ad-hoc bare strings in
several places (``"blocked"`` in operator/training output, untyped returns from
the run-audit deriver, success/failed/skipped literals on the project-run path),
each free to drift from the others.

The canonical state is derived from run-level events via
:meth:`RunStatus.from_run_events`:

==========================================  =====================
event signal                                RunStatus
==========================================  =====================
``run_completed``                           ``COMPLETED``
``run_failed``                              ``FAILED``
``run_aborted``                             ``ABORTED``
gate / produces-check rejection tail        ``BLOCKED``
``run_started`` with no terminal follow-up  ``RUNNING``
==========================================  =====================

The project-run record schema uses ``success``/``failed``/``skipped`` — convert
  with :meth:`to_project_record_status` at the executor/orchestrator finalize
  boundary only.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping, Sequence

__all__ = [
    "RunStatus",
    "STEP_IN_FLIGHT_KINDS",
    "STEP_LIFECYCLE_KINDS",
    "STEP_TERMINAL_KINDS",
    "TASK_FINALIZABLE_EVENT_KINDS",
]


STEP_TERMINAL_KINDS = frozenset(
    (
        "step_completed",
        "step_failed",
        "step_skipped",
        "step_attested",
    )
)
"""Step-level events that resolve a leaf for cursor/progress/completion."""

STEP_IN_FLIGHT_KINDS = frozenset(("step_dispatched", "step_awaiting_fetch"))
"""Step lifecycle events that keep a leaf active."""

STEP_LIFECYCLE_KINDS = STEP_TERMINAL_KINDS | STEP_IN_FLIGHT_KINDS
"""Step lifecycle events that can update a leaf's latest lifecycle state."""

TASK_FINALIZABLE_EVENT_KINDS = STEP_TERMINAL_KINDS | frozenset(
    (
        "step_awaiting_fetch",
        "item_completed",
        "item_attested",
    )
)
"""Event kinds accepted by the task gate finalization wrapper."""


class RunStatus(StrEnum):
    """Canonical lifecycle status of a run.

    The string value is the canonical, wire-neutral lowercase token. External
    wire formats are produced only at their respective serialization boundaries.
    """

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    ABORTED = "aborted"
    SKIPPED = "skipped"

    # ------------------------------------------------------------------ #
    # Canonical derivation from run-level events.
    # ------------------------------------------------------------------ #
    @classmethod
    def from_run_events(cls, events: Sequence[Mapping[str, Any]]) -> "RunStatus":
        """Derive the canonical run status from a run's event log.

        Terminal events win in the order aborted > completed > failed. Absent a
        terminal event, a gate/produces-check rejection tail (the run was halted
        awaiting operator action) maps to ``BLOCKED``; otherwise the run is still
        ``RUNNING``.
        """
        terminal_kinds = {ev.get("kind") for ev in events if isinstance(ev, Mapping)}
        if "run_aborted" in terminal_kinds:
            return cls.ABORTED
        if "run_completed" in terminal_kinds:
            return cls.COMPLETED
        if "run_failed" in terminal_kinds:
            return cls.FAILED
        if _is_blocked_tail(events):
            return cls.BLOCKED
        return cls.RUNNING

    @classmethod
    def from_run_record_status(cls, raw: str) -> "RunStatus":
        """Parse a persisted run-record status token.

        Accepts canonical persisted tokens and a read-through set of legacy
        spellings used by older project/thread records. Callers must only
        serialize canonical tokens back to disk via ``RunStatus.value``.
        """
        try:
            return _RUN_RECORD_STATUS_TO_RUN_STATUS[raw]
        except KeyError:
            raise ValueError(
                f"unmapped run-record status {raw!r}; expected one of "
                f"{sorted(_RUN_RECORD_STATUS_TO_RUN_STATUS)!r}"
            ) from None

    # ------------------------------------------------------------------ #
    # Project-run record boundary — used ONLY at executor/orchestrator finalize.
    # ------------------------------------------------------------------ #
    def to_project_record_status(self) -> str:
        """Translate to the project-run record status vocabulary.

        The persisted ``run.json`` record uses ``success``/``failed``/``skipped``
        (validated by ``validate_run_record``); this keeps that boundary token
        derived from the canonical enum rather than a bare literal.
        """
        try:
            return _RUN_STATUS_TO_PROJECT_RECORD[self]
        except KeyError:
            raise ValueError(
                f"{self!r} has no project-run record representation"
            ) from None


def _is_blocked_tail(events: Sequence[Mapping[str, Any]]) -> bool:
    """Whether the run's terminal tail is a gate/produces-check rejection.

    Mirrors the operator-view notion of "blocked": the most recent event is a
    cursor rewind or iteration failure (the rejection of a produces check / gate),
    so the run is halted awaiting operator action rather than progressing.
    """
    for ev in reversed(events):
        if not isinstance(ev, Mapping):
            continue
        return ev.get("kind") in {"cursor_rewind", "iteration_failed"}
    return False


_RUN_STATUS_TO_PROJECT_RECORD: dict[RunStatus, str] = {
    RunStatus.COMPLETED: "success",
    RunStatus.FAILED: "failed",
    RunStatus.SKIPPED: "skipped",
}

_RUN_RECORD_STATUS_TO_RUN_STATUS: dict[str, RunStatus] = {
    RunStatus.RUNNING.value: RunStatus.RUNNING,
    RunStatus.COMPLETED.value: RunStatus.COMPLETED,
    RunStatus.FAILED.value: RunStatus.FAILED,
    RunStatus.BLOCKED.value: RunStatus.BLOCKED,
    RunStatus.ABORTED.value: RunStatus.ABORTED,
    RunStatus.SKIPPED.value: RunStatus.SKIPPED,
    "prepared": RunStatus.RUNNING,
    "success": RunStatus.COMPLETED,
    "succeeded": RunStatus.COMPLETED,
    "error": RunStatus.FAILED,
    "orphaned": RunStatus.FAILED,
}
