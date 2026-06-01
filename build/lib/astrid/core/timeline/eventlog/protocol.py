"""Timeline eventlog backend and transport protocols."""

from __future__ import annotations

from typing import Protocol

from .types import BackendName, EventLogHead, EventLogVerification
from ..events.schema import TimelineActor, TimelineEvent


class SupabaseEventLogTransport(Protocol):
    """Transport seam for mocked or live Supabase eventlog operations."""

    def append_event(
        self,
        *,
        timeline_id: str,
        kind: str,
        payload: dict[str, object],
        actor: TimelineActor,
        expected_version: int | None = None,
        txn_id: str | None = None,
    ) -> object: ...

    def append_imported_event(
        self,
        *,
        timeline_id: str,
        source_event: TimelineEvent,
        idempotency_key: str,
        actor: TimelineActor,
    ) -> object: ...

    def read_events(
        self,
        *,
        timeline_id: str,
        after: str | None = None,
        limit: int | None = None,
    ) -> object: ...

    def head(self, *, timeline_id: str) -> object: ...

    def verify_chain(self, *, timeline_id: str) -> object: ...

    def repair_erasure(
        self,
        *,
        timeline_id: str,
        target_event_ids: list[str],
        reason: str,
        erased_by: str,
        policy_ref: str | None = None,
    ) -> object: ...


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

    def append_imported_event(
        self,
        timeline_id: str,
        source_event: TimelineEvent,
        *,
        idempotency_key: str,
        actor: TimelineActor,
    ) -> TimelineEvent:
        """Import a source event into the destination with idempotency.

        Creates a **destination-native** event whose ID, version, hash,
        and prev_hash are materialised locally.  The source event identity
        is preserved **only** in the import metadata fields
        (``source_backend``, ``source_timeline_id``, ``source_event_id``,
        ``source_version``, ``source_hash``) and in the idempotency state
        keyed by ``idempotency_key``.

        Idempotency keys are deterministic and follow the form:
        ``transfer:<direction>:<source-backend>:<source-timeline-id>:<source-event-id>``

        Retrying the same key after a successful import returns the
        already-appended destination event without creating a duplicate.

        Raises ``EventLogError`` when the stream is deleted,
        ``EventLogStaleVersionError`` when a CAS guard embedded in the
        idempotency state fails, and ``EventLogTransportError`` when
        the chain verification step fails.

        Args:
            timeline_id: UUID that identifies the target timeline.
            source_event: Validated source event envelope to import.
            idempotency_key: Deterministic deduplication key.
            actor: Who performed the import.

        Returns:
            The fully-materialized destination-native ``TimelineEvent``.
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
