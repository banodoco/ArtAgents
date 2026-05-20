"""Timeline eventlog backend protocol."""

from __future__ import annotations

from typing import Protocol

from .types import BackendName, EventLogHead, EventLogVerification
from ..events.schema import TimelineActor, TimelineEvent


class EventLogBackend(Protocol):
    """Storage backend for one timeline event stream.

    Every method receives an explicit ``timeline_id`` so that a single
    backend instance can service multiple timelines without thread-local
    or constructor-level binding.
    """

    def append_event(
        self,
        timeline_id: str,
        kind: str,
        payload: dict[str, object],
        *,
        actor: TimelineActor,
        expected_version: int | None = None,
        txn_id: str | None = None,
    ) -> TimelineEvent:
        """Append a semantic event to the identified timeline.

        Args:
            timeline_id: UUID that identifies the target timeline.
            kind: Dot-separated event kind (e.g. ``timeline.renamed``,
                ``clip.added``, …).
            payload: JSON-serializable event payload dict.
            actor: Who performed the action.
            expected_version: Optional optimistic-concurrency guard
                (enforced starting in m5).
            txn_id: Optional transaction-coordination id (enforced
                starting in m5).

        Returns:
            The fully-materialized ``TimelineEvent`` as stored.
        """
        ...

    def read_events(
        self,
        *,
        after: str | None = None,
        limit: int | None = None,
    ) -> list[TimelineEvent]: ...

    def head(self) -> EventLogHead: ...

    def verify_chain(self) -> EventLogVerification: ...

    def backend_name(self) -> BackendName: ...
