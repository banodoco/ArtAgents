"""Timeline eventlog backend and transport protocols."""

from __future__ import annotations

from typing import Protocol

from ..events.schema import TimelineActor, TimelineEvent
from .types import BackendName, EventLogHead, EventLogVerification


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

        Version semantics
        -----------------
        ``expected_version`` compares against the current stream version,
        which in m5 is the same value exposed as the local event count/head
        version. Omitting it remains a compatibility path for single-writer
        and legacy callers: the append proceeds without optimistic CAS.

        Deferred non-goals for this contract patch
        ------------------------------------------
        This interface shape reserves room for later work without implying
        it exists here:

        * soft-lock event semantics are deferred to follow-on milestone work
        * explicit multi-event transaction APIs are deferred beyond the
          per-event ``txn_id`` passthrough field
        * pack-level batch CAS hooks in ``pack_write_gateway()`` are deferred
          until transaction semantics are defined

        Args:
            timeline_id: UUID that identifies the target timeline.
            kind: Dot-separated event kind (e.g. ``timeline.renamed``,
                ``clip.added``, …).
            payload: JSON-serializable event payload dict.
            actor: Who performed the action.
            expected_version: Optional optimistic-concurrency guard
                against the current stream version. ``None`` preserves the
                pre-m5 append-without-CAS behavior for compatibility.
            txn_id: Optional correlation id carried on the event envelope.
                It is metadata only in m5; explicit transaction APIs are
                intentionally deferred.

        Returns:
            The fully-materialized ``TimelineEvent`` as stored.
        """
        ...

    def preflight_append(
        self,
        *,
        actor: TimelineActor,
        kinds: list[str] | None = None,
    ) -> None:
        """Prove append capability without mutating any state.

        Runs the deterministic preconditions :meth:`append_event` checks
        (backend config/transport availability, stream identity, kind
        support) and raises the same typed errors, while performing no
        writes and no network I/O. Write gateways call this before
        committing anything outside the eventlog so an append-incapable
        backend fails with zero mutation on either side.
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
