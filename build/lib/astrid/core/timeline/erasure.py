"""Erasure query and command.

Implements the narrow v1 query language for selecting events to erase plus
the ``timeline.erased`` audit-event-first repair semantics:

1. Query matches by event IDs, event kind allowlist, actor exact/prefix match,
   and timestamp range.  No payload-field predicates in v1.
2. Preview-first behavior: print matching events, require ``--yes`` for mutation.
3. Append ``timeline.erased`` audit event BEFORE repair so the operation is
   itself auditable in the event stream.
4. Perform backend payload repair replacing matched payloads with canonical
   ``ErasedPayload`` envelope, then recompute hash-chain/head.
5. Regenerate projection or return a typed erasure/projection error — never
   fall back to stale compatibility blobs.
6. Retained metadata: event IDs, versions, kind, actor fields, timestamps,
   recomputed chain fields remain for audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .events.schema import (
    TimelineActor,
    TimelineErasedPayload,
)
from .eventlog.protocol import EventLogBackend
from .eventlog.types import BackendName
from .projection import ProjectionError, regenerate_projection


# ============================================================================
# Erasure selector
# ============================================================================


@dataclass(frozen=True)
class ErasureSelector:
    """Narrow v1 query language for erasure matching.

    All fields are optional.  An empty selector matches zero events.
    At least one field must be specified to avoid accidental full-stream
    erasure.
    """

    event_ids: tuple[str, ...] | None = None
    """Exact event IDs (ULIDs) to match."""

    kind_allowlist: tuple[str, ...] | None = None
    """Event kind prefix or exact match allowlist (e.g. ('clip.added', 'clip.removed'))."""

    actor_id: str | None = None
    """Exact actor ID match."""

    actor_id_prefix: str | None = None
    """Prefix match on actor ID."""

    ts_after: str | None = None
    """Timestamp ISO-8601 lower bound (inclusive)."""

    ts_before: str | None = None
    """Timestamp ISO-8601 upper bound (inclusive)."""

    def is_empty(self) -> bool:
        """Return True when no selector criteria are specified."""
        return (
            self.event_ids is None
            and self.kind_allowlist is None
            and self.actor_id is None
            and self.actor_id_prefix is None
            and self.ts_after is None
            and self.ts_before is None
        )

    def matches(self, event: Any) -> bool:
        """Return True when *event* matches all specified criteria.

        *event* must have attributes: event_id, kind, actor (with .id), ts.
        """
        # Event ID match
        if self.event_ids is not None:
            if event.event_id not in self.event_ids:
                return False

        # Kind allowlist
        if self.kind_allowlist is not None:
            kind = getattr(event, "kind", "")
            if kind not in self.kind_allowlist:
                return False

        # Actor exact match
        if self.actor_id is not None:
            actor = getattr(event, "actor", None)
            actor_id = getattr(actor, "id", "") if actor is not None else ""
            if actor_id != self.actor_id:
                return False

        # Actor prefix match
        if self.actor_id_prefix is not None:
            actor = getattr(event, "actor", None)
            actor_id = getattr(actor, "id", "") if actor is not None else ""
            if not actor_id.startswith(self.actor_id_prefix):
                return False

        # Timestamp range
        if self.ts_after is not None:
            ts = getattr(event, "ts", "")
            if ts < self.ts_after:
                return False

        if self.ts_before is not None:
            ts = getattr(event, "ts", "")
            if ts > self.ts_before:
                return False

        return True


# ============================================================================
# Erasure result
# ============================================================================


@dataclass(frozen=True)
class ErasurePreview:
    """Preview of events that would be erased — no mutation performed."""

    matched_count: int
    """Number of events matching the selector."""

    matched_event_ids: tuple[str, ...]
    """Event IDs that would be erased."""

    total_events_in_stream: int
    """Total number of events in the stream (for context)."""

    selector_summary: dict[str, Any]
    """JSON-serializable summary of the selector used."""


@dataclass(frozen=True)
class ErasureResult:
    """Result of a completed erasure operation (after --yes)."""

    erased_event_ids: tuple[str, ...]
    """Event IDs that had their payloads replaced with ErasedPayload."""

    replaced_count: int
    """Number of payloads replaced."""

    downstream_count: int
    """Number of downstream events whose hash chain was recomputed."""

    audit_event_id: str
    """ULID of the appended ``timeline.erased`` audit event."""

    selector_summary: dict[str, Any]
    """JSON-serializable summary of the selector used."""

    projection_regenerated: bool
    """Whether the projection was successfully regenerated after repair."""

    reason: str
    """The erasure reason."""

    policy_ref: str | None
    """Optional policy reference."""


# ============================================================================
# Erasure query (preview)
# ============================================================================


def query_erasure(
    backend: EventLogBackend,
    selector: ErasureSelector,
) -> ErasurePreview:
    """Preview events matching the selector.

    Never mutates — always read-only.  Callers should assert preview is
    acceptable before invoking ``apply_erasure()`` with ``--yes``.

    Args:
        backend: The event-log backend to query.
        selector: The v1 erasure selector criteria.

    Returns:
        ErasurePreview with matched event IDs and counts.

    Raises:
        ValueError: When the selector is empty (no criteria specified).
    """
    if selector.is_empty():
        raise ValueError(
            "erasure selector is empty: at least one of --event-ids, "
            "--kind, --actor, --actor-prefix, --after, or --before must "
            "be specified to prevent accidental full-stream erasure"
        )

    all_events = backend.read_events()
    matched_ids: list[str] = []
    for evt in all_events:
        if selector.matches(evt):
            matched_ids.append(evt.event_id)

    return ErasurePreview(
        matched_count=len(matched_ids),
        matched_event_ids=tuple(matched_ids),
        total_events_in_stream=len(all_events),
        selector_summary=_selector_summary(selector),
    )


# ============================================================================
# Erasure apply (mutation)
# ============================================================================


def apply_erasure(
    backend: EventLogBackend,
    selector: ErasureSelector,
    *,
    timeline_id: str,
    actor: TimelineActor,
    reason: str,
    policy_ref: str | None = None,
    regenerate_projection_after: bool = True,
    timeline_home: Path | None = None,
) -> ErasureResult:
    """Execute erasure repair with audit-event-first semantics.

    1. Preview matches via *selector*.
    2. Append ``timeline.erased`` audit event BEFORE repair.
    3. Execute backend repair (payload replacement + chain recompute).
    4. Regenerate projection or raise typed projection error.

    Never falls back to stale ``assembly.json`` — if projection fails after
    repair, the error surfaces rather than being silently hidden.

    Args:
        backend: The event-log backend to repair.
        selector: The v1 erasure selector criteria.
        timeline_id: The timeline UUID.
        actor: Who performed the erasure.
        reason: Human-readable reason for the erasure.
        policy_ref: Optional policy reference.
        regenerate_projection_after: Whether to regenerate projection files.
        timeline_home: Required for projection regeneration on LocalFs.

    Returns:
        ErasureResult with replaced count, audit event ID, and projection status.

    Raises:
        ValueError: When the selector is empty or no events match.
        ProjectionError: When projection regeneration fails after repair.
    """
    from .repair import repair_erasure_local_fs

    # 1. Preview
    preview = query_erasure(backend, selector)
    if preview.matched_count == 0:
        raise ValueError(
            "erasure selector matched zero events; nothing to erase"
        )

    matched_ids = list(preview.matched_event_ids)

    # 2. Append audit event BEFORE repair
    selector_summary = _selector_summary(selector)
    erased_payload_obj = TimelineErasedPayload(
        selector_summary=selector_summary,
        reason=reason,
        affected_count=len(matched_ids),
        policy_ref=policy_ref,
        affected_event_ids=matched_ids,
    ).to_json_obj()

    audit_event = backend.append_event(
        timeline_id,
        "timeline.erased",
        erased_payload_obj,
        actor=actor,
    )

    # 3. Execute backend repair
    backend_name = backend.backend_name().strip().lower()

    if backend_name == "local_fs":
        # LocalFs repair through internal path
        from .eventlog.local_fs import LocalFsBackend
        if not isinstance(backend, LocalFsBackend):
            raise ValueError(
                "LocalFs erasure repair requires a LocalFsBackend instance"
            )
        repair_result = repair_erasure_local_fs(
            timeline_home=backend.timeline_home,
            events_path=backend.events_path,
            head_path=backend.head_path,
            target_event_ids=matched_ids,
            reason=reason,
            erased_by=actor.id,
            policy_ref=policy_ref,
        )
        replaced_count = repair_result["replaced_count"]
        downstream_count = repair_result["downstream_count"]
    elif backend_name == "supabase":
        # Supabase repair via transport/RPC
        # The backend.repair_erasure should be called on the transport
        try:
            # Access the transport-level repair through the SupabaseBackend
            backend.repair_erasure(
                timeline_id=timeline_id,
                target_event_ids=matched_ids,
                reason=reason,
                erased_by=actor.id,
                policy_ref=policy_ref,
            )
            replaced_count = len(matched_ids)
            downstream_count = 0  # Supabase handles recompute internally
        except AttributeError:
            raise ValueError(
                "Supabase backend does not support erasure repair"
            )
    else:
        raise ValueError(f"unsupported backend for erasure: {backend_name}")

    # 4. Regenerate projection (or fail with typed error)
    projection_regenerated = False
    if regenerate_projection_after and timeline_home is not None:
        try:
            regenerate_projection(
                timeline_id,
                backend,
                timeline_home=timeline_home,
            )
            projection_regenerated = True
        except ProjectionError:
            raise
        except Exception as exc:
            raise ProjectionError(
                event_id=audit_event.event_id,
                kind="(erasure-projection)",
                reason=f"projection regeneration failed after erasure: {exc}",
            ) from exc

    return ErasureResult(
        erased_event_ids=tuple(matched_ids),
        replaced_count=replaced_count,
        downstream_count=downstream_count,
        audit_event_id=audit_event.event_id,
        selector_summary=selector_summary,
        projection_regenerated=projection_regenerated,
        reason=reason,
        policy_ref=policy_ref,
    )


# ============================================================================
# Internal helpers
# ============================================================================


def _selector_summary(selector: ErasureSelector) -> dict[str, Any]:
    """Build a JSON-serializable summary of the erasure selector."""
    summary: dict[str, Any] = {}
    if selector.event_ids is not None:
        summary["event_ids"] = list(selector.event_ids)
    if selector.kind_allowlist is not None:
        summary["kind_allowlist"] = list(selector.kind_allowlist)
    if selector.actor_id is not None:
        summary["actor_id"] = selector.actor_id
    if selector.actor_id_prefix is not None:
        summary["actor_id_prefix"] = selector.actor_id_prefix
    if selector.ts_after is not None:
        summary["ts_after"] = selector.ts_after
    if selector.ts_before is not None:
        summary["ts_before"] = selector.ts_before
    return summary
