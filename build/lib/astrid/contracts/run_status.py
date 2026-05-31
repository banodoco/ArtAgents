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

Wire / serialization formats live ONLY at their boundaries, never in core:

* the external reigh task queue uses Title-Case tokens
  (``Queued``/``In Progress``/``Complete``/``Failed``/``Cancelled``) — convert
  with :meth:`to_reigh_wire` / :meth:`from_reigh_wire` at the reigh client only;
* the project-run record schema uses ``success``/``failed``/``skipped`` — convert
  with :meth:`to_project_record_status` at the executor/orchestrator finalize
  boundary only.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping, Sequence

__all__ = ["RunStatus"]


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

    # ------------------------------------------------------------------ #
    # reigh wire boundary (Title-Case) — used ONLY by the reigh task client.
    # ------------------------------------------------------------------ #
    def to_reigh_wire(self) -> str:
        """Title-Case token the reigh task queue expects.

        ``BLOCKED`` and ``SKIPPED`` are internal-only states with no reigh wire
        analog and raise.
        """
        try:
            return _RUN_STATUS_TO_REIGH[self]
        except KeyError:
            raise ValueError(
                f"{self!r} has no reigh wire representation; it is an internal-only status"
            ) from None

    @classmethod
    def from_reigh_wire(cls, wire: str) -> "RunStatus":
        """Parse a Title-Case reigh status token into a canonical RunStatus.

        ``Queued`` is a pre-dispatch wire state with no internal analog yet and
        raises (provisional — pending a canonical pending/queued state).
        """
        try:
            return _REIGH_TO_RUN_STATUS[wire]
        except KeyError:
            raise ValueError(
                f"unmapped reigh wire status {wire!r}; expected one of "
                f"{sorted(_REIGH_TO_RUN_STATUS)!r}"
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


_RUN_STATUS_TO_REIGH: dict[RunStatus, str] = {
    RunStatus.RUNNING: "In Progress",
    RunStatus.COMPLETED: "Complete",
    RunStatus.FAILED: "Failed",
    RunStatus.ABORTED: "Cancelled",
}

_REIGH_TO_RUN_STATUS: dict[str, RunStatus] = {
    wire: status for status, wire in _RUN_STATUS_TO_REIGH.items()
}

_RUN_STATUS_TO_PROJECT_RECORD: dict[RunStatus, str] = {
    RunStatus.COMPLETED: "success",
    RunStatus.FAILED: "failed",
    RunStatus.SKIPPED: "skipped",
}
