"""Cross-backend transfer: push/pull event-log replay.

Push replays local events to a Supabase destination via
``append_imported_event()``.  Pull replays Supabase events to a local
destination via the same import mechanism.

Both directions use idempotency keys of the form
``transfer:<direction>:<source-backend>:<source-timeline-id>:<source-event-id>``
so interruption is safely resumable.  Transfer does **not** copy
``assembly.json``, ``display.json``, Reigh config blobs, or compatibility
projection files as authority — it is event-log transfer only.

Existing Reigh blob/config Supabase bridges (``open_in_reigh``,
``SupabaseDataProvider``, etc.) remain separate publish/handoff
mechanisms and are not redefined here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .eventlog.protocol import EventLogBackend
from .eventlog.selector import (
    EventLogTarget,
    resolve_event_log_target,
    resolve_pull_destination,
)
from .events.schema import TimelineActor
from .projection import regenerate_projection

# ============================================================================
# Structured results
# ============================================================================


@dataclass(frozen=True)
class TransferResult:
    """Result of a push or pull transfer operation."""

    direction: str  # "push" or "pull"
    source_backend_name: str
    destination_backend_name: str
    source_timeline_id: str
    destination_timeline_id: str

    scanned: int
    """Total number of source events examined."""

    appended: int
    """Number of events appended to the destination."""

    skipped_idempotent: int
    """Number of events already present in the destination (idempotent)."""

    failed: int
    """Number of events that could not be transferred."""

    destination_version: int
    """Stream version on the destination after transfer."""

    projection_regenerated: bool
    """Whether the projection was regenerated after transfer."""


# ============================================================================
# push: local → Supabase
# ============================================================================


def push_timeline(
    project_slug: str,
    slug_or_id: str,
    *,
    destination_actor: TimelineActor | None = None,
    root: str | Path | None = None,
) -> TransferResult:
    """Push a local timeline to Supabase via event-log replay.

    Replays local events through ``append_imported_event()`` on the
    Supabase backend in version order.  Uses deterministic idempotency
    keys so interruption is safely resumable — re-running the push skips
    already-imported events.

    After transfer the destination's projection is regenerated from the
    canonical event log only (no compatibility blobs copied).

    Args:
        project_slug: Project that owns the local timeline.
        slug_or_id: Local timeline slug, ULID, or event-stream UUID.
        destination_actor: Actor to use for the Supabase append calls.
            Defaults to a system actor when None.
        root: Optional project root override.

    Returns:
        TransferResult with scanned/appended/skipped-idempotent/failed counts.

    Raises:
        ValueError: When the local timeline cannot be resolved or Supabase
            credentials are missing.
    """
    # Resolve local source
    source_target = resolve_event_log_target(
        project_slug, slug_or_id, root=root
    )
    if source_target.backend_name != "local_fs":
        raise ValueError(
            f"push requires a local source timeline; "
            f"got backend={source_target.backend_name}"
        )

    # Resolve Supabase destination (same timeline_id — the Supabase stream
    # must already exist or we need to create it).
    dest_target = resolve_event_log_target(
        project_slug,
        source_target.timeline_id,
        root=root,
        preferred_backend="supabase",
    )

    actor = destination_actor or TimelineActor(
        type="system", id="transfer:push", display="push-transfer"
    )

    return _transfer_events(
        source=source_target,
        destination=dest_target,
        direction="push",
        actor=actor,
        regenerate_dest_projection=True,
    )


# ============================================================================
# pull: Supabase → local
# ============================================================================


def pull_timeline(
    project_slug: str,
    remote_slug_or_id: str,
    *,
    into: str | None = None,
    create_as: str | None = None,
    create: bool = False,
    destination_actor: TimelineActor | None = None,
    root: str | Path | None = None,
) -> TransferResult:
    """Pull a Supabase timeline to a local destination via event-log replay.

    Replays Supabase events through ``append_imported_event()`` on the
    local backend in version order.  Uses deterministic idempotency keys
    so interruption is safely resumable.

    Destination binding:
    1. ``--into <slug>``: pull into an existing local timeline.
    2. ``--create --as <slug>``: create a new local timeline home.
    3. ``--create`` (no --as): implicit creation when the remote stream
       exposes exactly one safe slug with no local collision.

    After transfer the destination's projection is regenerated from the
    canonical event log only.

    The local timeline UUID is destination-native — the remote source
    UUID is preserved in import metadata and idempotency state, not as
    the local primary identity.

    Args:
        project_slug: Project that will own the local destination.
        remote_slug_or_id: Remote timeline slug or UUID on Supabase.
        into: Existing local timeline slug to pull into.
        create_as: Create a new local timeline with this slug.
        create: Allow implicit creation from remote slug metadata.
        destination_actor: Actor for local append calls.
        root: Optional project root override.

    Returns:
        TransferResult with scanned/appended/skipped-idempotent/failed counts.

    Raises:
        ValueError: When the remote timeline cannot be resolved, Supabase
            credentials are missing, or the local destination is ambiguous.
    """
    # Resolve remote Supabase source
    source_target = resolve_event_log_target(
        project_slug,
        remote_slug_or_id,
        root=root,
        preferred_backend="supabase",
    )
    if source_target.backend_name != "supabase":
        raise ValueError(
            f"pull requires a Supabase source; "
            f"got backend={source_target.backend_name}"
        )

    # Resolve local destination
    dest = resolve_pull_destination(
        project_slug,
        into=into,
        create_as=create_as,
        create=create,
        remote_source_slug=remote_slug_or_id if create else None,
        remote_source_timeline_id=source_target.timeline_id,
        root=root,
    )

    actor = destination_actor or TimelineActor(
        type="system", id="transfer:pull", display="pull-transfer"
    )

    return _transfer_events(
        source=source_target,
        destination=dest.target,
        direction="pull",
        actor=actor,
        regenerate_dest_projection=True,
    )


# ============================================================================
# Internal: transfer loop
# ============================================================================


def _transfer_events(
    *,
    source: EventLogTarget,
    destination: EventLogTarget,
    direction: str,
    actor: TimelineActor,
    regenerate_dest_projection: bool = True,
) -> TransferResult:
    """Replay source events to destination via append_imported_event().

    Reads all events from *source*.backend, then for each event:
    1. Builds the deterministic idempotency key.
    2. Calls destination.backend.append_imported_event().
    3. Catches EventLogIdempotentError → skipped_idempotent.
    4. Catches other errors → failed.
    """
    from .eventlog.types import EventLogIdempotentError

    source_backend: EventLogBackend = source.backend
    dest_backend: EventLogBackend = destination.backend

    source_events = source_backend.read_events()

    scanned = len(source_events)
    appended = 0
    skipped_idempotent = 0
    failed = 0

    direction_label = direction  # "push" or "pull"
    source_backend_name = source.backend_name
    source_timeline_id = source.timeline_id

    # Track which destination event IDs we've already seen (for idempotency
    # detection).  append_imported_event() may return the existing event
    # without raising EventLogIdempotentError on healthy sentinel paths.
    known_dest_ids: set[str] = set()

    for event in source_events:
        idempotency_key = (
            f"transfer:{direction_label}:"
            f"{source_backend_name}:"
            f"{source_timeline_id}:"
            f"{event.event_id}"
        )

        try:
            dest_head_before = dest_backend.head().version
            dest_event = dest_backend.append_imported_event(
                timeline_id=destination.timeline_id,
                source_event=event,
                idempotency_key=idempotency_key,
                actor=actor,
            )
            # Detect idempotent returns: same version means no new event
            # was appended, OR the returned event ID was already seen.
            dest_head_after = dest_backend.head().version
            if dest_head_after == dest_head_before or dest_event.event_id in known_dest_ids:
                skipped_idempotent += 1
            else:
                appended += 1
            known_dest_ids.add(dest_event.event_id)
        except EventLogIdempotentError:
            skipped_idempotent += 1
        except Exception:
            failed += 1

    # Regenerate projection from events only
    projection_regenerated = False
    if regenerate_dest_projection and destination.timeline_home is not None:
        try:
            regenerate_projection(
                destination.timeline_id,
                dest_backend,
                timeline_home=destination.timeline_home,
            )
            projection_regenerated = True
        except Exception:
            # Projection regeneration failure is non-fatal for transfer
            # (the event log is canonical).
            pass

    head = dest_backend.head()

    return TransferResult(
        direction=direction,
        source_backend_name=str(source_backend_name),
        destination_backend_name=str(destination.backend_name),
        source_timeline_id=source_timeline_id,
        destination_timeline_id=destination.timeline_id,
        scanned=scanned,
        appended=appended,
        skipped_idempotent=skipped_idempotent,
        failed=failed,
        destination_version=head.version,
        projection_regenerated=projection_regenerated,
    )
