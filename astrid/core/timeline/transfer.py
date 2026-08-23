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

import os
from dataclasses import dataclass
from pathlib import Path

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core.project.project import load_project
from astrid.core.timeline.banodoco_schema import canonical_empty_timeline
from astrid.core.util.time import utc_now_seconds

from .eventlog.protocol import EventLogBackend
from .eventlog.selector import (
    EventLogTarget,
    resolve_event_log_target,
    resolve_pull_destination,
)
from .eventlog.supabase import (
    TimelineMetadataPreflight,
    create_timeline_via_append_service,
    read_timeline_metadata_preflight,
)
from .events.schema import TimelineActor, TimelineEvent
from .projection import regenerate_projection
from .sync_divergence import (
    DivergenceArtifactRef,
    TransferFailure,
    write_keep_both_artifact,
)
from .sync_state import (
    HeadSnapshot,
    SyncBookmark,
    classify_sync_state,
    head_snapshot_from_backend,
    read_local_sync_bookmark,
    write_local_sync_bookmark,
)

# ============================================================================
# Structured results
# ============================================================================


@dataclass(frozen=True)
class TransferResult:
    """Result of a push or pull transfer operation.

    New in S5: carries sync classification fields populated before replay
    so callers can inspect the sync state without changing replay behavior.
    """

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

    # ------------------------------------------------------------------
    # Sync classification fields (S5 — populated before replay)
    # ------------------------------------------------------------------

    divergent: bool = False
    """Whether the sync state indicates divergence (both_advanced, conflict, etc.)."""

    sync_action: str | None = None
    """Classified sync state from classify_sync_state() (e.g. 'up_to_date', 'both_advanced')."""

    divergence_artifact: DivergenceArtifactRef | None = None
    """Reference to a keep-both artifact written before LWW replay (S5 Phase 2)."""

    bookmark_error: str | None = None
    """Human-readable detail when the bookmark is missing or incompatible."""


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
    # Resolve local source — marker-aware (S4 amendment 3a): marked ⇒ sqlite, legacy ⇒ local_fs
    source_target = resolve_event_log_target(project_slug, slug_or_id, root=root)
    # Marker-aware authority check: use canonical authority seam, fail closed on corrupt marker
    from astrid.core.timeline.authority import is_backfilled_timeline

    try:
        _is_marked = is_backfilled_timeline(source_target.timeline_id, root)
    except Exception as exc:
        # is_backfilled_timeline raises BackfillError fail-closed on corrupt marker
        raise TransferFailure(f"backfill authority marker is unreadable: {exc}") from exc
    # When DB missing, is_backfilled returns False (legacy), which maps to local_fs
    expected = "sqlite" if _is_marked else "local_fs"
    if source_target.backend_name != expected:
        raise TransferFailure(
            f"push authority mismatch for {source_target.timeline_id!r}: "
            f"marker={expected}, backend={source_target.backend_name} — failing closed (R5)"
        )

    _preflight_push_destination(
        project_slug=project_slug,
        source=source_target,
        root=root,
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

    When the destination is created via ``--create`` (or ``--create --as``),
    the remote source UUID is preserved as the local canonical
    ``timeline_id`` so the pulled timeline retains the same identity
    across backends.  ``source_timeline_id`` is also recorded as audit
    provenance.

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
            f"pull requires a Supabase source; got backend={source_target.backend_name}"
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
    # S4 amendment 3a: validate destination authority matches marker (fail closed)
    if dest.target is not None and dest.target.timeline_home is not None:
        try:
            from astrid.core.timeline.authority import is_backfilled_timeline as _is_bf2

            _is_marked2 = _is_bf2(dest.target.timeline_id, root)
            _expected2 = "sqlite" if _is_marked2 else "local_fs"
            if dest.target.backend_name != _expected2:
                raise TransferFailure(
                    f"pull destination authority mismatch for {dest.target.timeline_id!r}: "
                    f"marker={_expected2}, backend={dest.target.backend_name} — failing closed (R5)"
                )
        except TransferFailure:
            raise
        except Exception as exc:
            raise TransferFailure(f"backfill authority marker is unreadable: {exc}") from exc

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

    Before the event loop S5 sync classification is performed: source and
    destination heads are snapshotted, any available local sync bookmark is
    read, and ``classify_sync_state()`` is called.  The result gates replay
    so only validated source suffixes are imported, divergent destination
    suffixes are durably preserved first, and incompatible bookmarks abort
    before any event replay.
    """
    from .eventlog.types import EventLogIdempotentError

    source_backend: EventLogBackend = source.backend
    dest_backend: EventLogBackend = destination.backend

    # ------------------------------------------------------------------
    # S5: Pre-replay sync classification and replay gating
    # ------------------------------------------------------------------
    source_head_snapshot = head_snapshot_from_backend(source_backend)
    dest_head_snapshot = head_snapshot_from_backend(dest_backend)

    # Determine spoke vs hub for the classifier based on transfer direction.
    # Push: source=local(spoke) → hub.  Pull: source=hub → local(spoke).
    if direction == "push":
        spoke_head = source_head_snapshot
        hub_head = dest_head_snapshot
        bookmark_timeline_home = source.timeline_home
    else:
        spoke_head = dest_head_snapshot
        hub_head = source_head_snapshot
        bookmark_timeline_home = destination.timeline_home

    # Try to read a local sync bookmark.  A corrupt bookmark is an
    # incompatible boundary, not a bootstrap opportunity.
    bookmark = None
    bookmark_error: str | None = None
    if bookmark_timeline_home is not None:
        try:
            bookmark = read_local_sync_bookmark(bookmark_timeline_home)
        except Exception as exc:
            bookmark_error = f"failed to read sync bookmark: {exc}"

    # Classify sync state.  The classifier maps spoke→source, hub→destination.
    sync_action: str | None = None
    divergent = False
    partial_bootstrap_safe = False
    if bookmark is None and bookmark_error is None:
        partial_bootstrap_safe = _is_partial_import_bootstrap_safe(
            source_backend=source_backend,
            dest_backend=dest_backend,
            source_timeline_id=source.timeline_id,
        )
    if bookmark_error is None:
        try:
            sync_action = classify_sync_state(
                source_head=spoke_head,
                destination_head=hub_head,
                bookmark=bookmark,
                expected_timeline_id=source.timeline_id,
                source_known_safe=partial_bootstrap_safe if direction == "pull" else False,
                destination_known_safe=partial_bootstrap_safe if direction == "push" else False,
            )
        except Exception as exc:
            bookmark_error = f"sync classification failed: {exc}"
            sync_action = "bookmark_incompatible"
    else:
        sync_action = "bookmark_incompatible"

    if sync_action in ("both_advanced", "bookmark_incompatible", "bookmark_missing"):
        divergent = True

    if sync_action == "bookmark_incompatible":
        detail = bookmark_error or "sync bookmark is incompatible with current heads"
        raise TransferFailure(f"{detail}; aborting before event replay")

    source_events = _source_events_for_action(
        source_backend=source_backend,
        sync_action=sync_action,
        direction=direction,
        bookmark=bookmark,
    )
    destination_suffix: list[TimelineEvent] = []
    divergence_artifact: DivergenceArtifactRef | None = None
    if sync_action == "both_advanced":
        destination_suffix = _destination_suffix_for_divergence(
            dest_backend=dest_backend,
            direction=direction,
            bookmark=bookmark,
        )
        divergence_artifact = write_keep_both_artifact(
            source=source,
            destination=destination,
            source_head=source_head_snapshot,
            destination_head=dest_head_snapshot,
            source_suffix=source_events,
            destination_suffix=destination_suffix,
        )

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

    if failed == 0:
        _verify_local_chains(source=source, destination=destination)
        refreshed_source_head = head_snapshot_from_backend(source_backend)
        refreshed_dest_head = head_snapshot_from_backend(dest_backend)
        if direction == "push":
            refreshed_spoke_head = refreshed_source_head
            refreshed_hub_head = refreshed_dest_head
        else:
            refreshed_spoke_head = refreshed_dest_head
            refreshed_hub_head = refreshed_source_head
        _refresh_bookmarks(
            source=source,
            destination=destination,
            bookmark_timeline_home=bookmark_timeline_home,
            spoke_head=refreshed_spoke_head,
            hub_head=refreshed_hub_head,
        )

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
        divergent=divergent,
        sync_action=sync_action,
        divergence_artifact=divergence_artifact,
        bookmark_error=bookmark_error,
    )


def _source_events_for_action(
    *,
    source_backend: EventLogBackend,
    sync_action: str | None,
    direction: str,
    bookmark: SyncBookmark | None,
) -> list[TimelineEvent]:
    if sync_action in {"up_to_date", "destination_only"}:
        return []
    if sync_action == "bookmark_missing":
        return source_backend.read_events()
    if sync_action in {"source_only", "both_advanced"}:
        if bookmark is None:
            raise TransferFailure(f"{sync_action} requires a bookmark boundary before replay")
        boundary = bookmark.spoke_event_id if direction == "push" else bookmark.hub_event_id
        return source_backend.read_events(after=boundary)
    return source_backend.read_events()


def _destination_suffix_for_divergence(
    *,
    dest_backend: EventLogBackend,
    direction: str,
    bookmark: SyncBookmark | None,
) -> list[TimelineEvent]:
    if bookmark is None:
        raise TransferFailure("both_advanced requires a bookmark boundary")
    boundary = bookmark.hub_event_id if direction == "push" else bookmark.spoke_event_id
    return dest_backend.read_events(after=boundary)


def _is_partial_import_bootstrap_safe(
    *,
    source_backend: EventLogBackend,
    dest_backend: EventLogBackend,
    source_timeline_id: str,
) -> bool:
    dest_events = dest_backend.read_events()
    if not dest_events:
        return False
    source_events = source_backend.read_events()
    source_by_id = {event.event_id: event for event in source_events}
    for dest_event in dest_events:
        source_event_id = dest_event.source_event_id
        if dest_event.source_timeline_id != source_timeline_id or source_event_id is None:
            return False
        source_event = source_by_id.get(source_event_id)
        if source_event is None or dest_event.source_hash != source_event.hash:
            return False
    return True


def _preflight_push_destination(
    *,
    project_slug: str,
    source: EventLogTarget,
    root: str | Path | None,
) -> None:
    supabase_url = (os.environ.get("SUPABASE_URL") or "").strip()
    service_role_key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not supabase_url or not service_role_key:
        raise ValueError(
            "Supabase backend requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
            "environment variables"
        )

    local_identity = _read_local_identity(source.timeline_home)
    preflight = read_timeline_metadata_preflight(
        supabase_url=supabase_url,
        auth_token=service_role_key,
        timeline_id=source.timeline_id,
    )
    if preflight.status == "exists":
        _recover_or_refresh_promotion_bookmark(
            source=source,
            local_identity=local_identity,
            preflight=preflight,
        )
        return
    if preflight.status == "not_found":
        if not _is_born_local_identity(local_identity):
            raise TransferFailure(
                f"Supabase timeline {source.timeline_id} was not found and local identity "
                "is not a born-local timeline eligible for promotion"
            )
        _promote_born_local_timeline(
            project_slug=project_slug,
            source=source,
            local_identity=local_identity,
            root=root,
            supabase_url=supabase_url,
            service_role_key=service_role_key,
        )
        return
    if preflight.status == "unauthorized":
        raise TransferFailure(
            preflight.detail
            or f"Supabase metadata preflight for {source.timeline_id} was unauthorized"
        )
    raise TransferFailure(
        preflight.detail or f"Supabase metadata preflight for {source.timeline_id} failed"
    )


def _promote_born_local_timeline(
    *,
    project_slug: str,
    source: EventLogTarget,
    local_identity: dict[str, object],
    root: str | Path | None,
    supabase_url: str,
    service_role_key: str,
) -> None:
    project = load_project(project_slug, root=root)
    project_id = project.get("project_id")
    if not isinstance(project_id, str) or not project_id.strip():
        raise TransferFailure(
            f"born-local push requires project.json.project_id for project '{project_slug}'"
        )
    sync_user_id = _resolve_sync_user_id()
    append_service_url = _resolve_append_service_url()
    append_service_token = _resolve_append_service_token()
    source_head = head_snapshot_from_backend(source.backend)
    created = create_timeline_via_append_service(
        service_url=append_service_url,
        bearer_token=append_service_token,
        project_id=project_id,
        user_id=sync_user_id,
        timeline_id=source.timeline_id,
        name=_identity_display_name(source, local_identity),
        config=canonical_empty_timeline(),
    )
    hub_head = HeadSnapshot(
        version=created.head_version,
        last_hash=created.head_hash,
        last_event_id=created.head_event_id,
    )
    bootstrap_bookmark = SyncBookmark.from_heads(
        timeline_id=source.timeline_id,
        spoke="local",
        spoke_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
        hub_head=hub_head,
    )
    if source.timeline_home is None:
        raise TransferFailure("born-local push requires a local timeline home")
    write_local_sync_bookmark(source.timeline_home, bootstrap_bookmark)
    _record_supabase_sync_metadata(
        source=source,
        local_identity=local_identity,
        project_id=project_id,
        user_id=sync_user_id,
    )
    if source_head.version == 0:
        _upsert_supabase_bookmark(
            timeline_id=source.timeline_id,
            supabase_url=supabase_url,
            auth_token=service_role_key,
            bookmark=bootstrap_bookmark,
        )


def _recover_or_refresh_promotion_bookmark(
    *,
    source: EventLogTarget,
    local_identity: dict[str, object],
    preflight: TimelineMetadataPreflight,
) -> None:
    if not _is_born_local_identity(local_identity):
        return
    if source.timeline_home is None:
        return
    if read_local_sync_bookmark(source.timeline_home) is not None:
        return
    if preflight.event_count == 0:
        return

    source_events = source.backend.read_events()
    imported_count = preflight.event_count - 1
    if imported_count < 0 or imported_count > len(source_events):
        raise TransferFailure(
            "born-local retry found a Supabase head that cannot be reconciled with "
            "the local event count"
        )
    if imported_count == 0:
        spoke_head = HeadSnapshot(version=0, last_hash=None, last_event_id=None)
    else:
        boundary = source_events[imported_count - 1]
        spoke_head = HeadSnapshot(
            version=imported_count,
            last_hash=boundary.hash,
            last_event_id=boundary.event_id,
        )
    hub_head = HeadSnapshot(
        version=preflight.version,
        last_hash=preflight.last_hash,
        last_event_id=preflight.last_event_id,
    )
    write_local_sync_bookmark(
        source.timeline_home,
        SyncBookmark.from_heads(
            timeline_id=source.timeline_id,
            spoke="local",
            spoke_head=spoke_head,
            hub_head=hub_head,
        ),
    )


def _record_supabase_sync_metadata(
    *,
    source: EventLogTarget,
    local_identity: dict[str, object],
    project_id: str,
    user_id: str,
) -> None:
    if source.timeline_home is None:
        return
    identity = dict(local_identity)
    synced_backends = identity.get("synced_backends")
    if isinstance(synced_backends, list):
        merged_backends = [item for item in synced_backends if isinstance(item, str)]
    else:
        merged_backends = []
    if "supabase" not in merged_backends:
        merged_backends.append("supabase")
    sync_targets = identity.get("sync_targets")
    if not isinstance(sync_targets, dict):
        sync_targets = {}
    sync_targets["supabase"] = {
        "backend": "supabase",
        "timeline_id": source.timeline_id,
        "project_id": project_id,
        "user_id": user_id,
        "provenance": identity.get("provenance"),
        "synced_at": utc_now_seconds(),
    }
    identity["synced_backends"] = merged_backends
    identity["sync_targets"] = sync_targets
    write_json_atomic(source.timeline_home / "assembly.identity.json", identity)


def _read_local_identity(timeline_home: Path | None) -> dict[str, object]:
    if timeline_home is None:
        return {}
    raw = read_json(timeline_home / "assembly.identity.json")
    if not isinstance(raw, dict):
        raise TransferFailure("assembly.identity.json must contain an object")
    return dict(raw)


def _is_born_local_identity(identity: dict[str, object]) -> bool:
    return identity.get("provenance") == "created" and identity.get("backend") == "local_fs"


def _identity_display_name(
    source: EventLogTarget,
    identity: dict[str, object],
) -> str:
    display = identity.get("display")
    if isinstance(display, dict):
        name = display.get("name")
        if isinstance(name, str) and name.strip():
            return name
    if source.slug:
        return source.slug
    return f"timeline-{source.timeline_id}"


def _resolve_sync_user_id() -> str:
    for env_name in ("ASTRID_SYNC_USER_ID", "REIGH_SYNC_USER_ID"):
        value = (os.environ.get(env_name) or "").strip()
        if value:
            return value
    raise TransferFailure("born-local push requires ASTRID_SYNC_USER_ID or REIGH_SYNC_USER_ID")


def _resolve_append_service_url() -> str:
    value = (os.environ.get("REIGH_APPEND_SERVICE_URL") or "").strip()
    if value:
        return value.rstrip("/")
    raise TransferFailure("born-local push requires REIGH_APPEND_SERVICE_URL")


def _resolve_append_service_token() -> str:
    value = (os.environ.get("REIGH_APPEND_SERVICE_INTERNAL_TOKEN") or "").strip()
    if value:
        return value
    raise TransferFailure("born-local push requires REIGH_APPEND_SERVICE_INTERNAL_TOKEN")


def _upsert_supabase_bookmark(
    *,
    timeline_id: str,
    supabase_url: str,
    auth_token: str,
    bookmark: SyncBookmark,
) -> None:
    from .eventlog.supabase import LiveSupabaseAppendTransport

    transport = LiveSupabaseAppendTransport(
        supabase_url=supabase_url,
        auth_token=auth_token,
    )
    transport.upsert_bookmark(
        timeline_id=timeline_id,
        spoke=bookmark.spoke,
        spoke_version=bookmark.spoke_version,
        spoke_hash=bookmark.spoke_hash,
        spoke_event_id=bookmark.spoke_event_id,
        hub_version=bookmark.hub_version,
        hub_hash=bookmark.hub_hash,
        hub_event_id=bookmark.hub_event_id,
        synced_at=bookmark.synced_at,
    )


def _refresh_bookmarks(
    *,
    source: EventLogTarget,
    destination: EventLogTarget,
    bookmark_timeline_home: Path | None,
    spoke_head: HeadSnapshot,
    hub_head: HeadSnapshot,
) -> None:
    bookmark = SyncBookmark.from_heads(
        timeline_id=source.timeline_id,
        spoke="local",
        spoke_head=spoke_head,
        hub_head=hub_head,
    )
    if bookmark_timeline_home is not None:
        write_local_sync_bookmark(bookmark_timeline_home, bookmark)

    supabase_target = destination if destination.backend_name == "supabase" else source
    if supabase_target.backend_name != "supabase":
        return
    upsert = getattr(supabase_target.backend, "upsert_bookmark", None)
    if upsert is None:
        raise TransferFailure("Supabase backend cannot update sync bookmark")
    try:
        upsert(
            spoke=bookmark.spoke,
            spoke_version=bookmark.spoke_version,
            spoke_hash=bookmark.spoke_hash,
            spoke_event_id=bookmark.spoke_event_id,
            hub_version=bookmark.hub_version,
            hub_hash=bookmark.hub_hash,
            hub_event_id=bookmark.hub_event_id,
            synced_at=bookmark.synced_at,
        )
    except Exception as exc:
        raise TransferFailure(f"failed to update DB sync bookmark: {exc}") from exc


def _verify_local_chains(
    *,
    source: EventLogTarget,
    destination: EventLogTarget,
) -> None:
    for label, target in (("source", source), ("destination", destination)):
        if target.backend_name != "local_fs":
            continue
        verification = target.backend.verify_chain()
        if not verification.ok:
            raise TransferFailure(
                f"{label} local event chain verification failed: {verification.error}"
            )
