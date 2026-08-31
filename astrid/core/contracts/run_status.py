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
