"""Atomic registered event append with payload-envelope hash chaining.

(m1 plan step 10.) The event append service is the single kernel path that
writes ``events`` rows. It validates the composed vocabulary (plan step 8),
enforces stream/project/aggregate agreement registry-driven, allocates
gap-free project and stream sequences, wraps domain data in the canonical
SD2 integrity envelope, and advances both heads — all inside the one
``BEGIN IMMEDIATE`` transaction the caller's unit of work provides.

Envelope (SD2 — the exact v10 DDL is preserved, so there are no hash
columns; the chain lives inside ``payload_json``)::

    {
      "data": { "...": "domain fields only" },
      "_integrity": {
        "previous_event_hash": "<sha256 hex of the preceding event's canonical
                                payload_json, or null at genesis>",
        "event_hash": "<sha256 hex of this event's canonical payload_json>"
      }
    }

``event_hash`` is the SHA-256 (hex) of the canonical JSON of the envelope
with the ``event_hash`` field itself omitted — the field is self-referential
by construction, exactly like the legacy task event log omits ``hash`` when
digesting a line. ``previous_event_hash`` is the stored ``event_hash`` of the
immediately preceding event on the same stream, and ``null`` for the genesis
event.

:meth:`EventAppendService.verify_stream` recomputes every link from genesis
to the stream head and fails on any tampering of either the domain data or
the integrity fields. Presence of the fields alone is never proof (NSA-2):
verification is an executable gate, not a shape check.

The service runs only through the typed unit-of-work operations. There is no
raw ``sqlite3`` access and no second write authority; ``data`` and ``changes``
are bounded structured inputs (canonicalized with explicit size/depth bounds),
so payload guidance is enforced by construction rather than by logging.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from astrid.core.events.registry import (
    aggregate_rule_for,
    validate_event_append,
)
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_bytes,
    canonical_json,
    parse_json,
)
from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import (
    DatabaseWriter,
    WriterError,
    WriterSession,
)
from astrid.core.util.time import utc_now_iso

# ---------------------------------------------------------------------------
# Envelope vocabulary (SD2)
# ---------------------------------------------------------------------------

DATA_KEY = "data"
INTEGRITY_KEY = "_integrity"
PREVIOUS_EVENT_HASH_KEY = "previous_event_hash"
EVENT_HASH_KEY = "event_hash"

from astrid.core.contracts.vocabulary_errors import ACTOR_KINDS  # noqa: F401
"""The exact ``events.actor_kind`` vocabulary baked into the v10 DDL CHECK."""

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EventAppendError(WriterError):
    """Base error for event append and chain verification.

    Subclasses :class:`astrid.core.store.writer.WriterError` (as do
    ``UoWError``, ``ReceiptError``, and ``RepositoryError``), so callers that
    handle the kernel store error family also catch event contract
    violations, while each concrete class stays distinguishable.
    """


class EventValidationError(EventAppendError):
    """Raised when an event append argument is invalid.

    Covers non-string/empty identifiers, non-object ``data``, non-array
    ``changes``, invalid ``actor_kind``/``schema_version``/``expected_head_seq``
    values, reserved integrity keys inside domain data, and payloads that
    exceed the canonical encoding bounds.
    """


class EventStreamNotFoundError(EventAppendError):
    """Raised when an append targets a stream id with no ``event_streams`` row."""

    def __init__(self, *, stream_id: str) -> None:
        self.stream_id: str = stream_id
        super().__init__(f"cannot append event: unknown stream {stream_id!r}")


class EventHeadConflictError(EventAppendError):
    """Raised when ``expected_head_seq`` does not match the current stream head.

    The check happens before any sequence allocation, so a stale CAS save
    leaves events, projections, heads, and receipts unchanged. Carries the
    actual head so callers can surface the current version (bridge 409).
    """

    def __init__(
        self, *, stream_id: str, expected_head_seq: int, actual_head_seq: int
    ) -> None:
        self.stream_id: str = stream_id
        self.expected_head_seq: int = expected_head_seq
        self.actual_head_seq: int = actual_head_seq
        super().__init__(
            f"event head conflict on stream {stream_id!r}: expected head "
            f"{expected_head_seq} but current head is {actual_head_seq}"
        )


class EventIdempotencyError(EventAppendError):
    """Raised when ``(stream_id, idempotency_key)`` is already committed.

    The ``UNIQUE (stream_id, idempotency_key)`` constraint is the final
    fence; this typed error is raised before any sequence allocation so a
    duplicate event can never consume a project or stream sequence.
    """

    def __init__(self, *, stream_id: str, idempotency_key: str) -> None:
        self.stream_id: str = stream_id
        self.idempotency_key: str = idempotency_key
        super().__init__(
            f"event idempotency violation: stream {stream_id!r} already has "
            f"an event with idempotency_key {idempotency_key!r}"
        )


class EventChainError(EventAppendError):
    """Raised when genesis-to-head verification fails.

    Carries the stream id, the failing event position (``None`` when the
    failure is structural, e.g. a head/event-count mismatch), and the reason.
    """

    def __init__(
        self, *, stream_id: str, position: int | None, reason: str
    ) -> None:
        self.stream_id: str = stream_id
        self.position: int | None = position
        self.reason: str = reason
        where = f" at position {position}" if position is not None else ""
        super().__init__(
            f"event chain verification failed for stream {stream_id!r}"
            f"{where}: {reason}"
        )


# ---------------------------------------------------------------------------
# Canonical envelope helpers
# ---------------------------------------------------------------------------


def payload_event_hash(payload: Mapping[str, Any]) -> str:
    """Return the canonical SHA-256 (hex) digest of one event payload.

    The digest covers the canonical JSON of *payload* with the
    ``_integrity.event_hash`` field omitted: the field is self-referential
    (it names the digest of the payload it lives in), so the digest is
    defined over the payload *before* that field is added — and recomputed
    over the stored payload *with* that field removed during verification.
    """
    envelope = dict(payload)
    integrity = envelope.get(INTEGRITY_KEY)
    if isinstance(integrity, Mapping):
        stripped = dict(integrity)
        stripped.pop(EVENT_HASH_KEY, None)
        envelope[INTEGRITY_KEY] = stripped
    return hashlib.sha256(canonical_bytes(envelope)).hexdigest()


def build_integrity_envelope(
    data: Mapping[str, Any],
    previous_event_hash: str | None,
) -> tuple[dict[str, Any], str]:
    """Wrap ``data`` in the canonical SD2 integrity envelope.

    Returns ``(envelope, event_hash)`` where *envelope* is the complete
    stored payload (``data`` plus ``_integrity`` with both hashes) and
    *event_hash* is the canonical digest of the envelope before the
    ``event_hash`` field is added. *previous_event_hash* is ``None`` at
    genesis.
    """
    envelope: dict[str, Any] = {
        DATA_KEY: dict(data),
        INTEGRITY_KEY: {
            PREVIOUS_EVENT_HASH_KEY: previous_event_hash,
        },
    }
    event_hash = payload_event_hash(envelope)
    envelope[INTEGRITY_KEY][EVENT_HASH_KEY] = event_hash
    return envelope, event_hash


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EventAppendResult:
    """One committed event append inside the active unit of work."""

    event_id: str
    project_seq: int
    stream_seq: int
    previous_event_hash: str | None
    event_hash: str
    payload_json: str
    changes_json: str
    created_at: str


@dataclass(frozen=True, slots=True)
class StreamChainVerification:
    """Genesis-to-head verification summary for one stream."""

    stream_id: str
    event_count: int
    head_seq: int
    head_hash: str | None


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise EventValidationError(f"{name} must be a non-empty string")
    return value


def _require_positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EventValidationError(f"{name} must be a positive integer")
    return value


def _require_non_negative_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EventValidationError(f"{name} must be a non-negative integer")
    return value


# ---------------------------------------------------------------------------
# The event append service
# ---------------------------------------------------------------------------


class EventAppendService:
    """Atomic registered event append and genesis-to-head verification.

    The service is stateless apart from the frozen registry it validates
    against; a single instance is safe to share across command callers.
    ``append`` must run inside an active unit of work (it allocates
    sequences and inserts rows); ``verify_stream`` submits one read-only
    callback to the writer and must **not** be called from inside a unit of
    work callback (it would deadlock the writer's FIFO queue).
    """

    def __init__(self, registry: FrozenSchemaPackRegistry) -> None:
        self._registry = registry

    # -- append ----------------------------------------------------------

    def append(
        self,
        uow: UnitOfWork,
        *,
        stream_id: str,
        project_id: str,
        event_kind: str,
        data: Mapping[str, Any],
        changes: Sequence[str],
        idempotency_key: str,
        txn_id: str,
        actor_kind: str,
        schema_version: int = 1,
        command_kind: str | None = None,
        event_id: str | None = None,
        expected_head_seq: int | None = None,
        created_at: str | None = None,
    ) -> EventAppendResult:
        """Append one registered, hash-chained event atomically.

        Inside the caller's active unit of work this:

        1. validates every argument (types, empty strings, actor kind,
           schema version, reserved integrity keys, canonical bounds);
        2. reads the stream row — the stream's project, type, aggregate,
           and head are the authority, never caller-supplied facts;
        3. enforces the optional ``expected_head_seq`` CAS *before* any
           allocation (stale saves fail with :class:`EventHeadConflictError`
           and change zero rows);
        4. enforces registry-driven stream/event/command vocabulary and
           aggregate/type/project agreement (:class:`EventAppendError`
           subclasses from ``astrid.core.repositories.errors``);
        5. rejects a duplicate ``(stream_id, idempotency_key)`` before any
           sequence allocation;
        6. derives ``previous_event_hash`` from the current tail (``null``
           at genesis) and builds the canonical SD2 envelope;
        7. allocates the next gap-free project and stream sequences,
           inserts the event row, and advances both heads atomically.

        Returns :class:`EventAppendResult` with the allocated sequences and
        the canonical hashes. Any exception rolls back the whole command:
        events, both heads, projections, and receipts stay unchanged.
        """
        _require_non_empty_string("stream_id", stream_id)
        _require_non_empty_string("project_id", project_id)
        _require_non_empty_string("event_kind", event_kind)
        _require_non_empty_string("idempotency_key", idempotency_key)
        _require_non_empty_string("txn_id", txn_id)
        _require_positive_int("schema_version", schema_version)
        if actor_kind not in ACTOR_KINDS:
            raise EventValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if not isinstance(data, Mapping):
            raise EventValidationError("data must be a JSON object")
        if INTEGRITY_KEY in data:
            raise EventValidationError(
                f"domain data must not contain the reserved {INTEGRITY_KEY!r} key"
            )
        if isinstance(changes, (str, bytes)) or not isinstance(changes, Sequence):
            raise EventValidationError(
                "changes must be a JSON array of strings"
            )
        for change in changes:
            if not isinstance(change, str):
                raise EventValidationError(
                    "changes must be a JSON array of strings"
                )
        if event_id is None:
            event_id = uuid.uuid4().hex
        else:
            _require_non_empty_string("event_id", event_id)
        if created_at is None:
            created_at = utc_now_iso()
        else:
            _require_non_empty_string("created_at", created_at)
        if command_kind is not None:
            _require_non_empty_string("command_kind", command_kind)
        if expected_head_seq is not None:
            _require_non_negative_int(
                "expected_head_seq", expected_head_seq
            )

        # The stream row is the single authority for project/type/aggregate.
        stream = uow._stream_row(stream_id)
        if stream is None:
            raise EventStreamNotFoundError(stream_id=stream_id)
        stream_project_id = str(stream["project_id"])
        stream_type = str(stream["stream_type"])
        aggregate_id = str(stream["aggregate_id"])
        head_seq = int(stream["head_seq"])

        # Expected-head CAS before any mutation.
        if expected_head_seq is not None and head_seq != expected_head_seq:
            raise EventHeadConflictError(
                stream_id=stream_id,
                expected_head_seq=expected_head_seq,
                actual_head_seq=head_seq,
            )

        # Registry-driven vocabulary and agreement (plan step 8): the
        # subject is the stream's aggregate by construction, so the caller
        # never supplies subject facts that could drift from the rule.
        rule = aggregate_rule_for(self._registry, stream_type)
        validate_event_append(
            self._registry,
            project_id=project_id,
            stream_project_id=stream_project_id,
            stream_type=stream_type,
            aggregate_id=aggregate_id,
            subject_type=rule.subject_type,
            subject_id=aggregate_id,
            event_kind=event_kind,
            command_kind=command_kind,
        )

        # Duplicate (stream_id, idempotency_key) rejected before allocation.
        if uow._has_event(stream_id, idempotency_key):
            raise EventIdempotencyError(
                stream_id=stream_id, idempotency_key=idempotency_key
            )

        # Previous hash comes from the committed tail inside this same
        # transaction, so multi-event commands chain correctly.
        tail = uow._tail_event(stream_id)
        previous_event_hash: str | None = None
        if tail is not None:
            try:
                tail_payload = parse_json(tail["payload_json"])
            except CanonicalizationError as exc:
                raise EventChainError(
                    stream_id=stream_id,
                    position=head_seq,
                    reason=f"stored tail payload is not valid JSON: {exc}",
                ) from exc
            previous_event_hash = payload_event_hash(tail_payload)

        # Canonical envelope with explicit bounds.
        envelope, event_hash = build_integrity_envelope(
            data, previous_event_hash
        )
        try:
            payload_json = canonical_json(envelope)
            changes_json = canonical_json(list(changes))
        except CanonicalizationError as exc:
            raise EventValidationError(
                f"cannot canonicalize event payload: {exc}"
            ) from exc

        # Atomic insert plus stream/project head advancement.
        project_seq, stream_seq = uow.append_event(
            stream_id=stream_id,
            project_id=project_id,
            event_id=event_id,
            subject_type=rule.subject_type,
            subject_id=aggregate_id,
            changes_json=changes_json,
            kind=event_kind,
            schema_version=schema_version,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            payload_json=payload_json,
            created_at=created_at,
        )
        return EventAppendResult(
            event_id=event_id,
            project_seq=project_seq,
            stream_seq=stream_seq,
            previous_event_hash=previous_event_hash,
            event_hash=event_hash,
            payload_json=payload_json,
            changes_json=changes_json,
            created_at=created_at,
        )

    # -- genesis-to-head verification -------------------------------------

    def verify_stream(
        self, writer: DatabaseWriter, stream_id: str
    ) -> StreamChainVerification:
        """Recompute the genesis-to-head hash chain for one stream.

        Runs as one read-only writer submission (no transaction is opened),
        so it must be called from outside any active unit of work. Returns
        the verification summary, or raises :class:`EventChainError` at the
        first broken link. Every stored event is checked:

        - the stream head equals the number of stored events and the event
          ``seq`` values are exactly ``1..head`` (gap-free, ordered);
        - each payload parses as canonical JSON and carries the
          ``_integrity`` envelope;
        - ``previous_event_hash`` equals the preceding event's stored
          ``event_hash`` (``null`` at genesis);
        - the stored ``event_hash`` equals the recomputed digest of the
          payload with the ``event_hash`` field removed — so tampering with
          domain data *or* either integrity field breaks verification.
        """
        _require_non_empty_string("stream_id", stream_id)
        return writer.submit(
            lambda session: self._verify_chain(session, stream_id)
        )

    def _verify_chain(
        self, session: WriterSession, stream_id: str
    ) -> StreamChainVerification:
        stream = session.query_one(
            "SELECT * FROM event_streams WHERE id = ?", (stream_id,)
        )
        if stream is None:
            raise EventStreamNotFoundError(stream_id=stream_id)
        head_seq = int(stream["head_seq"])
        rows = session.query(
            "SELECT seq, payload_json FROM events "
            "WHERE stream_id = ? ORDER BY seq ASC",
            (stream_id,),
        )
        if len(rows) != head_seq:
            raise EventChainError(
                stream_id=stream_id,
                position=None,
                reason=(
                    f"stream head seq is {head_seq} but {len(rows)} events "
                    "are stored"
                ),
            )
        previous_event_hash: str | None = None
        for index, row in enumerate(rows):
            seq = int(row["seq"])
            expected_seq = index + 1
            if seq != expected_seq:
                raise EventChainError(
                    stream_id=stream_id,
                    position=index,
                    reason=(
                        f"gap or reorder: expected seq {expected_seq}, "
                        f"found {seq}"
                    ),
                )
            try:
                payload = parse_json(row["payload_json"])
            except CanonicalizationError as exc:
                raise EventChainError(
                    stream_id=stream_id,
                    position=index,
                    reason=f"payload is not valid JSON: {exc}",
                ) from exc
            if not isinstance(payload, Mapping):
                raise EventChainError(
                    stream_id=stream_id,
                    position=index,
                    reason="payload is not a JSON object",
                )
            integrity = payload.get(INTEGRITY_KEY)
            if not isinstance(integrity, Mapping):
                raise EventChainError(
                    stream_id=stream_id,
                    position=index,
                    reason=(
                        f"payload is missing the {INTEGRITY_KEY!r} "
                        "integrity envelope"
                    ),
                )
            stored_hash = integrity.get(EVENT_HASH_KEY)
            if not isinstance(stored_hash, str) or not stored_hash:
                raise EventChainError(
                    stream_id=stream_id,
                    position=index,
                    reason=f"payload is missing {EVENT_HASH_KEY!r}",
                )
            stored_previous = integrity.get(PREVIOUS_EVENT_HASH_KEY)
            if stored_previous != previous_event_hash:
                raise EventChainError(
                    stream_id=stream_id,
                    position=index,
                    reason=(
                        f"{PREVIOUS_EVENT_HASH_KEY} mismatch: expected "
                        f"{previous_event_hash!r}, stored {stored_previous!r}"
                    ),
                )
            recomputed = payload_event_hash(payload)
            if recomputed != stored_hash:
                raise EventChainError(
                    stream_id=stream_id,
                    position=index,
                    reason=(
                        f"{EVENT_HASH_KEY} mismatch: recomputed "
                        f"{recomputed}, stored {stored_hash}"
                    ),
                )
            previous_event_hash = stored_hash
        return StreamChainVerification(
            stream_id=stream_id,
            event_count=len(rows),
            head_seq=head_seq,
            head_hash=previous_event_hash,
        )


__all__ = [
    "ACTOR_KINDS",
    "DATA_KEY",
    "EVENT_HASH_KEY",
    "INTEGRITY_KEY",
    "PREVIOUS_EVENT_HASH_KEY",
    "EventAppendError",
    "EventAppendResult",
    "EventAppendService",
    "EventChainError",
    "EventHeadConflictError",
    "EventIdempotencyError",
    "EventStreamNotFoundError",
    "EventValidationError",
    "StreamChainVerification",
    "build_integrity_envelope",
    "payload_event_hash",
]
