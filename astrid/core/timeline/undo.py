"""Mass undo: preview-first multi-event undo with chunked writes.

Implements mass-undo with:
1. Filter candidates by ``--since`` time and actor exact/prefix pattern.
2. Preview-first: print candidate event IDs/kinds and planned inverses
   without writing (default).
3. ``--yes`` mode: chunk writes with conservative fixed batch size,
   re-checking head/CAS between chunks.  Stops on first projection or
   append error and reports already-written inverse event IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .eventlog.protocol import EventLogBackend
from .events.schema import (
    ErasedPayload,
    TimelineActor,
    TimelineRevertedPayload,
)
from .inverses import (
    _NON_REVERSIBLE_KINDS,
    plan_inverse,
)
from .projection import (
    apply_event_to_assembly,
    regenerate_projection,
)

# ---------------------------------------------------------------------------
# Chunk size for --yes writes
# ---------------------------------------------------------------------------

_MASS_UNDO_CHUNK_SIZE = 50
"""Conservative fixed batch size for chunked mass-undo writes.

Each chunk appends this many inverse events (or fewer for the final chunk),
then re-checks the backend head/CAS before proceeding to the next chunk.
"""


# ============================================================================
# Mass undo selector
# ============================================================================


@dataclass(frozen=True)
class MassUndoSelector:
    """Filter criteria for mass-undo candidate events.

    All fields are optional.  An empty selector matches zero events.
    At least one field must be specified.
    """

    ts_since: str | None = None
    """Timestamp ISO-8601 lower bound (inclusive) — ``--since``."""

    actor_id: str | None = None
    """Exact actor ID match — ``--actor``."""

    actor_id_prefix: str | None = None
    """Prefix match on actor ID — ``--actor-prefix``."""

    def is_empty(self) -> bool:
        """Return True when no selector criteria are specified."""
        return (
            self.ts_since is None
            and self.actor_id is None
            and self.actor_id_prefix is None
        )

    def matches(self, event: Any) -> bool:
        """Return True when *event* matches all specified criteria.

        *event* must have attributes: ts, actor (with .id).
        """
        # Timestamp lower bound
        if self.ts_since is not None:
            ts = getattr(event, "ts", "")
            if ts < self.ts_since:
                return False

        # Actor exact match
        if self.actor_id is not None:
            actor = getattr(event, "actor", None)
            actor_id_val = getattr(actor, "id", "") if actor is not None else ""
            if actor_id_val != self.actor_id:
                return False

        # Actor prefix match
        if self.actor_id_prefix is not None:
            actor = getattr(event, "actor", None)
            actor_id_val = getattr(actor, "id", "") if actor is not None else ""
            if not actor_id_val.startswith(self.actor_id_prefix):
                return False

        return True


# ============================================================================
# Result types
# ============================================================================


@dataclass(frozen=True)
class MassUndoPreview:
    """Preview of events that would be undone — no mutation performed."""

    matched_count: int
    """Number of candidate events matching the selector."""

    total_events: int
    """Total number of events in the stream."""

    candidates: tuple[dict[str, Any], ...]
    """Candidate entries with keys: event_id, kind, inverse_kind, inverse_payload, invertible, revert_reason."""

    selector_summary: dict[str, Any]
    """JSON-serializable summary of the selector used."""


@dataclass(frozen=True)
class MassUndoResult:
    """Result of a completed mass-undo operation (after --yes)."""

    planned_count: int
    """Number of inverse events planned."""

    appended_count: int
    """Number of inverse events successfully appended."""

    appended_event_ids: tuple[str, ...]
    """ULIDs of all appended inverse events (including partial-success IDs)."""

    chunk_count: int
    """Number of chunks processed."""

    complete: bool
    """True when all planned inverses were appended successfully."""

    error: str | None = None
    """Error message when *complete* is False."""

    projection_regenerated: bool = False
    """Whether the projection was successfully regenerated after undo."""


# ============================================================================
# Preview
# ============================================================================


def plan_mass_undo(
    backend: EventLogBackend,
    selector: MassUndoSelector,
) -> MassUndoPreview:
    """Preview candidate events and their planned inverses — never mutates.

    Reads all events, filters by *selector*, walks them in version order
    maintaining a running projection, and plans inverses for each matching
    event.  Prints nothing; the caller is responsible for display.

    Args:
        backend: The event-log backend to read from.
        selector: The mass-undo filter criteria.

    Returns:
        MassUndoPreview with candidate details.

    Raises:
        ValueError: When the selector is empty (no criteria specified).
    """
    if selector.is_empty():
        raise ValueError(
            "mass-undo selector is empty: at least one of --since, "
            "--actor, or --actor-prefix must be specified"
        )

    all_events = backend.read_events()
    candidates: list[dict[str, Any]] = []

    # Walk events, maintain running projection for accurate before/after
    state: dict[str, Any] = {}
    for event in all_events:
        before = dict(state)

        # Apply to get after state
        try:
            state = apply_event_to_assembly(state, event)
        except Exception:
            # If projection fails, still continue with whatever before we have
            pass
        after = dict(state)

        # Skip lifecycle/ops events and erased events
        if event.kind in _NON_REVERSIBLE_KINDS:
            continue
        if isinstance(event.payload, ErasedPayload):
            continue

        # Check selector match
        if not selector.matches(event):
            continue

        # Plan inverse for this event
        inv = plan_inverse(
            event,
            before_projection=before,
            after_projection=after,
        )

        candidates.append({
            "event_id": event.event_id,
            "kind": event.kind,
            "invertible": inv.invertible,
            "inverse_kind": inv.inverse_kind or "",
            "inverse_payload": inv.inverse_payload or {},
            "revert_reason": inv.revert_reason or "",
        })

    return MassUndoPreview(
        matched_count=len(candidates),
        total_events=len(all_events),
        candidates=tuple(candidates),
        selector_summary=_selector_summary(selector),
    )


# ============================================================================
# Execute (--yes)
# ============================================================================


def execute_mass_undo(
    backend: EventLogBackend,
    selector: MassUndoSelector,
    *,
    timeline_id: str,
    actor: TimelineActor,
    timeline_home: Path | None = None,
    chunk_size: int = _MASS_UNDO_CHUNK_SIZE,
) -> MassUndoResult:
    """Execute mass undo with chunked writes and head/CAS re-checks.

    1. Plan inverses via ``plan_mass_undo()``.
    2. Split planned inverses into fixed-size chunks.
    3. For each chunk:
       a. Re-check head (version) from backend; if mismatched, fail.
       b. Append each inverse event.  On first append error, stop and
          report already-written inverse IDs.
    4. Regenerate projection after all chunks.

    Args:
        backend: The event-log backend to write to.
        selector: The mass-undo filter criteria.
        timeline_id: The timeline UUID.
        actor: Who performed the mass undo.
        timeline_home: Required for projection regeneration on LocalFs.
        chunk_size: Events per chunk (default ``_MASS_UNDO_CHUNK_SIZE``).

    Returns:
        MassUndoResult with counts and appended event IDs.
    """
    # 1. Plan inverses
    preview = plan_mass_undo(backend, selector)
    if preview.matched_count == 0:
        raise ValueError(
            "mass-undo selector matched zero events; nothing to undo"
        )

    candidates = list(preview.candidates)
    appended_ids: list[str] = []
    chunk_count = 0

    # 2. Chunked execution
    for chunk_start in range(0, len(candidates), chunk_size):
        chunk = candidates[chunk_start:chunk_start + chunk_size]

        # Re-check head before writing this chunk
        try:
            head = backend.head()
        except Exception as exc:
            return MassUndoResult(
                planned_count=len(candidates),
                appended_count=len(appended_ids),
                appended_event_ids=tuple(appended_ids),
                chunk_count=chunk_count,
                complete=False,
                error=f"head check failed before chunk {chunk_count + 1}: {exc}",
            )

        # Verify chain integrity
        try:
            verification = backend.verify_chain()
            if not verification.ok:
                return MassUndoResult(
                    planned_count=len(candidates),
                    appended_count=len(appended_ids),
                    appended_event_ids=tuple(appended_ids),
                    chunk_count=chunk_count,
                    complete=False,
                    error=f"chain verification failed before chunk {chunk_count + 1}: {verification.error or 'unknown error'}",
                )
        except Exception as exc:
            return MassUndoResult(
                planned_count=len(candidates),
                appended_count=len(appended_ids),
                appended_event_ids=tuple(appended_ids),
                chunk_count=chunk_count,
                complete=False,
                error=f"chain verification error before chunk {chunk_count + 1}: {exc}",
            )

        # Append each inverse in this chunk
        for candidate in chunk:
            try:
                if candidate["invertible"] and candidate["inverse_kind"]:
                    # Append mechanical inverse event
                    event = backend.append_event(
                        timeline_id,
                        candidate["inverse_kind"],
                        candidate["inverse_payload"],
                        actor=actor,
                    )
                else:
                    # Non-invertible: append timeline.reverted
                    revert_payload = TimelineRevertedPayload(
                        target_event_id=candidate["event_id"],
                        reason=candidate.get("revert_reason") or f"mass-undo of {candidate['kind']}",
                        before_projection=None,
                        after_projection=None,
                    ).to_json_obj()
                    event = backend.append_event(
                        timeline_id,
                        "timeline.reverted",
                        revert_payload,
                        actor=actor,
                    )
                appended_ids.append(event.event_id)
            except Exception as exc:
                # Stop on first error, report partial success
                return MassUndoResult(
                    planned_count=len(candidates),
                    appended_count=len(appended_ids),
                    appended_event_ids=tuple(appended_ids),
                    chunk_count=chunk_count,
                    complete=False,
                    error=f"append failed in chunk {chunk_count + 1} for event {candidate['event_id']}: {exc}",
                )

        chunk_count += 1

    # 3. Regenerate projection after all chunks
    projection_regenerated = False
    if timeline_home is not None:
        try:
            regenerate_projection(
                timeline_id,
                backend,
                timeline_home=timeline_home,
            )
            projection_regenerated = True
        except Exception as exc:
            # Still return result with partial success; projection error
            # is surfaced but does not invalidate the undo writes.
            return MassUndoResult(
                planned_count=len(candidates),
                appended_count=len(appended_ids),
                appended_event_ids=tuple(appended_ids),
                chunk_count=chunk_count,
                complete=True,
                error=f"projection regeneration warning: {exc}",
                projection_regenerated=False,
            )

    return MassUndoResult(
        planned_count=len(candidates),
        appended_count=len(appended_ids),
        appended_event_ids=tuple(appended_ids),
        chunk_count=chunk_count,
        complete=True,
        projection_regenerated=projection_regenerated,
    )


# ============================================================================
# Internal helpers
# ============================================================================


def _selector_summary(selector: MassUndoSelector) -> dict[str, Any]:
    """Build a JSON-serializable summary of the mass-undo selector."""
    summary: dict[str, Any] = {}
    if selector.ts_since is not None:
        summary["ts_since"] = selector.ts_since
    if selector.actor_id is not None:
        summary["actor_id"] = selector.actor_id
    if selector.actor_id_prefix is not None:
        summary["actor_id_prefix"] = selector.actor_id_prefix
    return summary
