"""Shared test fixtures for timeline backend contract tests.

Provides:
- ``FakeSupabaseTransport`` — in-memory transport that stores TimelineEvent
  objects and enforces event hash chain + expected_version CAS, matching the
  SupabaseEventLogTransport protocol.
- ``fake_supabase_transport`` fixture — fresh transport per test.
- ``local_fs_backend`` fixture — LocalFsBackend against tmp_path.
- ``supabase_backend_with_fake`` fixture — SupabaseBackend with fake transport.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from astrid.core.util.time import utc_now_iso
from astrid.core.timeline.eventlog import LocalFsBackend, SupabaseBackend
from astrid.core.timeline.eventlog.types import (
    EventLogError,
    EventLogIdempotentError,
    EventLogStaleVersionError,
    TimelineVersionConflict,
)
from astrid.core.timeline.events.schema import (
    TimelineActor,
    TimelineEvent,
    with_event_hash,
)


class FakeSupabaseTransport:
    """In-memory fake of the SupabaseEventLogTransport protocol.

    Stores real ``TimelineEvent`` objects (not dicts or raw rows) and
    enforces the event hash chain + ``expected_version`` CAS semantics
    that the backend contract requires.

    No Supabase credentials are needed — this is a pure in-memory
    contract double suitable for deterministic unit tests.
    """

    def __init__(self) -> None:
        self._streams: dict[str, list[TimelineEvent]] = {}
        self._idem_registry: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public transport surface (matches SupabaseEventLogTransport)
    # ------------------------------------------------------------------

    def append_event(
        self,
        *,
        timeline_id: str,
        kind: str,
        payload: dict[str, object],
        actor: TimelineActor,
        expected_version: int | None = None,
        txn_id: str | None = None,
    ) -> TimelineEvent:
        """Append a new event with hash-chain and CAS enforcement.

        Returns the fully-materialized ``TimelineEvent``.
        """
        stream = self._streams.setdefault(timeline_id, [])

        # CAS enforcement
        current_version = len(stream)
        if expected_version is not None and expected_version != current_version:
            tail = stream[-1] if stream else None
            raise EventLogStaleVersionError(
                TimelineVersionConflict(
                    timeline_id=timeline_id,
                    expected_version=expected_version,
                    current_version=current_version,
                    last_event_id=tail.event_id if tail else None,
                    last_event_kind=tail.kind if tail else None,
                    last_event_summary=(
                        f"{tail.kind}#{tail.event_id}" if tail else None
                    ),
                )
            )

        # Reject appends after timeline.deleted
        if stream and stream[-1].kind == "timeline.deleted":
            from astrid.core.timeline.eventlog.types import EventLogError
            raise EventLogError(
                f"timeline {timeline_id} rejects appends after timeline.deleted"
            )

        # Compute prev_hash from the tail of the stream
        prev_hash = stream[-1].hash if stream else None

        # Build the event
        event = TimelineEvent.new(
            timeline_id=timeline_id,
            ts=utc_now_iso(),
            actor=actor,
            kind=kind,
            payload=payload,
            prev_hash=prev_hash,
            expected_version=expected_version,
            txn_id=txn_id,
        )
        event = with_event_hash(event, prev_hash=prev_hash)

        stream.append(event)
        return event

    def append_imported_event(
        self,
        *,
        timeline_id: str,
        source_event: TimelineEvent,
        idempotency_key: str,
        actor: TimelineActor,
    ) -> TimelineEvent:
        """Import a source event with idempotency and CAS enforcement.

        Uses an in-memory idempotency registry keyed by ``idempotency_key``.
        Retrying the same key returns the already-appended event.
        """
        stream = self._streams.setdefault(timeline_id, [])

        # Check idempotency
        existing = self._idem_registry.get(idempotency_key)
        if existing is not None:
            # Find the existing event in the stream
            for evt in stream:
                if evt.event_id == existing:
                    return evt
            raise EventLogIdempotentError(existing)

        # Reject appends after timeline.deleted
        if stream and stream[-1].kind == "timeline.deleted":
            raise EventLogError(
                f"timeline {timeline_id} rejects appends after timeline.deleted"
            )

        # Compute prev_hash from the tail
        prev_hash = stream[-1].hash if stream else None

        # Convert source payload to dict
        payload_dict = (
            source_event.payload.to_json_obj()
            if hasattr(source_event.payload, "to_json_obj")
            else dict(source_event.payload)
        )

        # Build destination-native event with import metadata
        event = TimelineEvent.new(
            timeline_id=timeline_id,
            ts=utc_now_iso(),
            actor=actor,
            kind=source_event.kind,
            payload=payload_dict,
            prev_hash=prev_hash,
            source_backend=source_event.source_backend or "unknown",
            source_timeline_id=source_event.timeline_id,
            source_event_id=source_event.event_id,
            source_version=source_event.source_version,
            source_hash=source_event.hash,
        )
        event = with_event_hash(event, prev_hash=prev_hash)

        stream.append(event)
        self._idem_registry[idempotency_key] = event.event_id
        return event

    def read_events(
        self,
        *,
        timeline_id: str,
        after: str | None = None,
        limit: int | None = None,
    ) -> list[TimelineEvent]:
        """Return events from the in-memory stream.

        Returns ``TimelineEvent`` objects (not dicts).
        """
        events = self._streams.get(timeline_id, [])
        if after is not None:
            index = next(
                (i for i, e in enumerate(events) if e.event_id == after),
                None,
            )
            if index is None:
                return []
            events = events[index + 1:]
        if limit is not None:
            events = events[:limit]
        return list(events)

    def head(self, *, timeline_id: str) -> dict[str, object]:
        """Return head metadata dict matching the transport contract."""
        stream = self._streams.get(timeline_id, [])
        if not stream:
            return {
                "timeline_id": timeline_id,
                "last_event_id": None,
                "last_hash": None,
                "event_count": 0,
                "version": 0,
            }
        last = stream[-1]
        return {
            "timeline_id": last.timeline_id,
            "last_event_id": last.event_id,
            "last_hash": last.hash,
            "event_count": len(stream),
            "version": len(stream),
        }

    def verify_chain(self, *, timeline_id: str) -> dict[str, object]:
        """Verify the event hash chain and return a result dict."""
        stream = self._streams.get(timeline_id, [])
        if not stream:
            return {
                "ok": True,
                "checked_events": 0,
                "last_event_id": None,
                "error": None,
            }

        prev_hash: str | None = None
        last_event_id: str | None = None
        for index, event in enumerate(stream):
            expected = with_event_hash(
                TimelineEvent.from_dict(
                    {**event.to_json_obj(), "hash": None}
                ),
                prev_hash=prev_hash,
            )
            if event.prev_hash != prev_hash:
                return {
                    "ok": False,
                    "checked_events": index,
                    "last_event_id": last_event_id,
                    "error": f"event {event.event_id} prev_hash mismatch",
                }
            if event.hash != expected.hash:
                return {
                    "ok": False,
                    "checked_events": index,
                    "last_event_id": last_event_id,
                    "error": f"event {event.event_id} hash mismatch",
                }
            prev_hash = event.hash
            last_event_id = event.event_id

        return {
            "ok": True,
            "checked_events": len(stream),
            "last_event_id": last_event_id,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Test helper
    # ------------------------------------------------------------------

    def tamper_event(self, timeline_id: str, index: int, new_payload: dict[str, object]) -> None:
        """Mutate the payload of a stored event (for tamper-detection tests).

        Does NOT re-compute the hash, so ``verify_chain()`` will detect
        the mismatch.
        """
        stream = self._streams.get(timeline_id, [])
        if index < 0 or index >= len(stream):
            raise IndexError(f"event index {index} out of range")
        old = stream[index]
        tampered = TimelineEvent(
            schema_version=old.schema_version,
            event_id=old.event_id,
            timeline_id=old.timeline_id,
            ts=old.ts,
            actor=old.actor,
            kind=old.kind,
            payload=new_payload,
            prev_hash=old.prev_hash,
            hash=old.hash,  # intentionally stale — verify_chain will catch it
            txn_id=old.txn_id,
            expected_version=old.expected_version,
        )
        stream[index] = tampered

    def tamper_hash(self, timeline_id: str, index: int, new_hash: str) -> None:
        """Mutate the hash of a stored event (for tamper-detection tests)."""
        stream = self._streams.get(timeline_id, [])
        if index < 0 or index >= len(stream):
            raise IndexError(f"event index {index} out of range")
        old = stream[index]
        tampered = TimelineEvent(
            schema_version=old.schema_version,
            event_id=old.event_id,
            timeline_id=old.timeline_id,
            ts=old.ts,
            actor=old.actor,
            kind=old.kind,
            payload=old.payload,
            prev_hash=old.prev_hash,
            hash=new_hash,
            txn_id=old.txn_id,
            expected_version=old.expected_version,
        )
        stream[index] = tampered

    def repair_erasure(
        self,
        *,
        timeline_id: str,
        target_event_ids: list[str],
        reason: str,
        erased_by: str,
        policy_ref: str | None = None,
    ) -> dict[str, object]:
        """Replace payloads of selected events with ErasedPayload and recompute chain."""
        from astrid.core.timeline.events.schema import ErasedPayload

        stream = self._streams.get(timeline_id, [])
        if not stream:
            return {
                "replaced_count": 0,
                "downstream_count": 0,
                "head_event_count": 0,
                "head_version": 0,
                "last_event_id": None,
                "last_hash": None,
            }

        target_set = frozenset(target_event_ids)
        to_erase: list[int] = []
        for i, evt in enumerate(stream):
            if evt.event_id in target_set:
                if isinstance(evt.payload, ErasedPayload):
                    continue
                to_erase.append(i)

        if not to_erase:
            last = stream[-1]
            return {
                "replaced_count": 0,
                "downstream_count": 0,
                "head_event_count": len(stream),
                "head_version": len(stream),
                "last_event_id": last.event_id,
                "last_hash": last.hash,
            }

        erased_at = utc_now_iso()
        to_erase.sort()
        first_erased_idx = to_erase[0]

        repaired: list[TimelineEvent] = []
        for i, evt in enumerate(stream):
            if i in to_erase:
                erased_payload = ErasedPayload(
                    erased=True,
                    reason=reason,
                    erased_at=erased_at,
                    erased_by=erased_by,
                    policy_ref=policy_ref,
                )
                repaired_evt = TimelineEvent(
                    schema_version=evt.schema_version,
                    event_id=evt.event_id,
                    timeline_id=evt.timeline_id,
                    ts=evt.ts,
                    actor=evt.actor,
                    kind=evt.kind,
                    payload=erased_payload,
                    prev_hash=evt.prev_hash if i == 0 else repaired[-1].hash,
                    hash=None,
                    expected_version=evt.expected_version,
                    txn_id=evt.txn_id,
                    source_backend=evt.source_backend,
                    source_timeline_id=evt.source_timeline_id,
                    source_event_id=evt.source_event_id,
                    source_version=evt.source_version,
                    source_hash=evt.source_hash,
                )
                repaired.append(repaired_evt)
            elif i >= first_erased_idx:
                prev = repaired[-1].hash if repaired else None
                downstream = TimelineEvent(
                    schema_version=evt.schema_version,
                    event_id=evt.event_id,
                    timeline_id=evt.timeline_id,
                    ts=evt.ts,
                    actor=evt.actor,
                    kind=evt.kind,
                    payload=evt.payload,
                    prev_hash=prev,
                    hash=None,
                    expected_version=evt.expected_version,
                    txn_id=evt.txn_id,
                    source_backend=evt.source_backend,
                    source_timeline_id=evt.source_timeline_id,
                    source_event_id=evt.source_event_id,
                    source_version=evt.source_version,
                    source_hash=evt.source_hash,
                )
                repaired.append(downstream)
            else:
                repaired.append(evt)

        # Recompute hashes for all events from first_erased_idx onward
        for i in range(first_erased_idx, len(repaired)):
            prev_hash = repaired[i - 1].hash if i > 0 else None
            repaired[i] = with_event_hash(repaired[i], prev_hash=prev_hash)

        self._streams[timeline_id] = repaired

        last = repaired[-1]
        downstream_count = len(repaired) - first_erased_idx
        return {
            "replaced_count": len(to_erase),
            "downstream_count": downstream_count,
            "head_event_count": len(repaired),
            "head_version": len(repaired),
            "last_event_id": last.event_id,
            "last_hash": last.hash,
        }

    @property
    def stream_count(self, timeline_id: str) -> int:
        """Return the number of stored events for *timeline_id*."""
        return len(self._streams.get(timeline_id, []))


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_supabase_transport() -> FakeSupabaseTransport:
    """Fresh in-memory Supabase transport for each test."""
    return FakeSupabaseTransport()


@pytest.fixture
def local_fs_backend(tmp_path: Path) -> LocalFsBackend:
    """LocalFsBackend pointed at a fresh tmp_path timeline home.

    The timeline home is pre-created with an identity sidecar so the
    backend can be used immediately.
    """
    timeline_id = str(uuid4())
    home = tmp_path / "timeline_home"
    home.mkdir(parents=True, exist_ok=True)

    # Write a minimal identity so bootstrap_legacy is not required.
    from astrid.core.project.jsonio import write_json_atomic
    write_json_atomic(
        home / "assembly.identity.json",
        {
            "schema_version": 1,
            "timeline_id": timeline_id,
            "timeline_ulid": "01J00000000000000000000000",
            "backend": "local_fs",
            "provenance": "imported",
            "created_at": "2026-05-21T00:00:00Z",
        },
    )
    return LocalFsBackend(timeline_id=timeline_id, timeline_home=home)


@pytest.fixture
def supabase_backend_with_fake(
    fake_supabase_transport: FakeSupabaseTransport,
) -> SupabaseBackend:
    """SupabaseBackend with a fake in-memory transport.

    No Supabase credentials are required — the transport is fully
    in-memory and deterministic.
    """
    return SupabaseBackend(
        timeline_id="00000000-0000-0000-0000-000000000001",
        transport=fake_supabase_transport,
        enabled=True,
    )
