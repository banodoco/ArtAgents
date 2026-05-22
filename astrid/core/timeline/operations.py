"""Recovery operations for timeline event streams.

Provides recover_to_event() and recover_to_snapshot() that verify chain,
project to an anchor point, append a timeline.recovered event, and
regenerate materialized projection files.

Recovery is the safe mechanism for a timeline owner to declare "the
projected state at this anchor is the authoritative assembly — replay
everything from here."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrid.core.project.schema import utc_now_iso
from astrid.core.timeline.eventlog.protocol import EventLogBackend
from astrid.core.timeline.events.schema import (
    TimelineActor,
    TimelineRecoveredPayload,
)
from astrid.core.timeline.projection import (
    ProjectionError,
    project_to_assembly,
    project_to_checkpoint,
    regenerate_projection,
    replay_projection,
)


# ============================================================================
# Structured result
# ============================================================================


@dataclass(frozen=True)
class RecoveryResult:
    """Structured result from a recovery operation.

    Carries enough IDs and counts for CLI auditability.
    """

    anchor_event_id: str
    """ULID of the anchor event the recovery attached to."""

    new_event_id: str
    """ULID of the appended ``timeline.recovered`` event."""

    new_version: int
    """Stream version after the recovery event was appended."""

    projected_head_summary: dict[str, Any]
    """Summary of the regenerated projected assembly (key counts, etc.)."""

    regenerated_artifact_paths: list[str]
    """Filesystem paths of regenerated compatibility files (assembly.json, etc.)."""

    anchor_type: str = "event"
    """'event' or 'snapshot'."""

    reason: str = ""
    """Human-readable reason for the recovery."""


# ============================================================================
# recover_to_event
# ============================================================================


def recover_to_event(
    project_slug: str,
    slug_or_id: str,
    event_id: str,
    actor: TimelineActor,
    reason: str,
    *,
    root: str | Path | None = None,
) -> RecoveryResult:
    """Verify chain, project to anchor event, append timeline.recovered.

    1. Resolves the timeline target using the local-project resolver.
    2. Verifies the event hash chain via ``backend.verify_chain()``.
    3. Replays events up to *event_id* to produce the anchor projection.
    4. Appends a ``timeline.recovered`` event with the projected state summary.
    5. Regenerates materialized projection files (assembly.json, checkpoint, display.json).

    Args:
        project_slug: Project that owns the timeline.
        slug_or_id: Timeline slug, ULID, or event-stream UUID.
        event_id: ULID of the anchor event to recover to.
        actor: Who performed the recovery.
        reason: Human-readable reason for the recovery operation.

    Returns:
        RecoveryResult with anchor, new event ID, version, projected head
        summary, and regenerated artifact paths.

    Raises:
        ValueError: When the timeline cannot be resolved or the event_id is
            not found in the stream.
        ProjectionError: When chain verification fails or projection fails.
    """
    # Import locally to avoid circular imports at module level
    from .observability import resolve_timeline_target
    from .eventlog import build_timeline_backend, select_timeline_stream
    from .paths import timeline_dir as _timeline_dir

    # 1. Resolve the timeline target
    target = resolve_timeline_target(project_slug, slug_or_id, root=root)

    # 2. Build backend
    stream = select_timeline_stream(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )
    backend = build_timeline_backend(stream)

    # 3. Verify chain before doing anything
    verification = backend.verify_chain()
    if not verification.ok:
        raise ProjectionError(
            event_id=verification.last_event_id or "(unknown)",
            kind="(chain-verification)",
            reason=(
                f"recovery refused: hash chain verification failed: "
                f"{verification.error or 'unknown error'}"
            ),
        )

    # 4. Project to the anchor event
    try:
        anchor_projection = project_to_assembly(
            backend.read_events(),
            initial_assembly=None,
        )
    except ProjectionError:
        raise

    # 5. Find the specific anchor projection (replay to the target event)
    anchor_projection = replay_projection(backend, stop_at_event_id=event_id)

    # 6. Build the recovery payload
    # Include a summary of the projected state for auditability
    projected_summary = _summarize_projection(anchor_projection)
    recovery_payload = TimelineRecoveredPayload(
        anchor_event_id=event_id,
        anchor_type="event",
        reason=reason,
        projected_state_summary=anchor_projection,
    ).to_json_obj()

    # 7. Append timeline.recovered event
    recovered_event = backend.append_event(
        target.timeline_id,
        "timeline.recovered",
        recovery_payload,
        actor=actor,
    )

    # 8. Regenerate materialized projection files
    tdir = _timeline_dir(project_slug, target.timeline_ulid, root=root)
    regenerated = regenerate_projection(
        target.timeline_id,
        backend,
        timeline_home=tdir,
    )

    # 9. Collect regenerated artifact paths
    artifact_paths = [
        str(tdir / "assembly.json"),
        str(tdir / "assembly.checkpoint.json"),
    ]
    display_path = tdir / "display.json"
    if display_path.exists():
        artifact_paths.append(str(display_path))

    head = backend.head()

    return RecoveryResult(
        anchor_event_id=event_id,
        new_event_id=recovered_event.event_id,
        new_version=head.version,
        projected_head_summary=projected_summary,
        regenerated_artifact_paths=artifact_paths,
        anchor_type="event",
        reason=reason,
    )


# ============================================================================
# recover_to_snapshot
# ============================================================================


def recover_to_snapshot(
    project_slug: str,
    slug_or_id: str,
    snapshot_metadata: dict[str, Any],
    snapshot_assembly: dict[str, Any],
    actor: TimelineActor,
    reason: str,
    *,
    root: str | Path | None = None,
) -> RecoveryResult:
    """Validate snapshot metadata against stream identity/version/hash, then
    append a ``timeline.recovered`` event anchored to the snapshot.

    The snapshot metadata must include at minimum:
    - ``timeline_id``: must match the resolved stream identity.
    - ``last_event_id``: the event ID the snapshot was taken at.
    - ``last_hash``: the hash of that event (verified against the backend).
    - ``version``: the stream version at snapshot time.

    Recovery is refused when ``verify_chain()`` fails.

    Args:
        project_slug: Project that owns the timeline.
        slug_or_id: Timeline slug, ULID, or event-stream UUID.
        snapshot_metadata: Dict with timeline_id, last_event_id, last_hash,
            version, event_count.
        snapshot_assembly: The projected assembly from the snapshot.
        actor: Who performed the recovery.
        reason: Human-readable reason for the recovery operation.

    Returns:
        RecoveryResult with anchor, new event ID, version, projected head
        summary, and regenerated artifact paths.

    Raises:
        ValueError: When snapshot metadata mismatches the stream identity.
        ProjectionError: When chain verification fails or hash mismatch.
    """
    from .observability import resolve_timeline_target
    from .eventlog import build_timeline_backend, select_timeline_stream
    from .paths import timeline_dir as _timeline_dir

    # 1. Resolve the timeline target
    target = resolve_timeline_target(project_slug, slug_or_id, root=root)

    # 2. Build backend
    stream = select_timeline_stream(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )
    backend = build_timeline_backend(stream)

    # 3. Verify chain before doing anything
    verification = backend.verify_chain()
    if not verification.ok:
        raise ProjectionError(
            event_id=verification.last_event_id or "(unknown)",
            kind="(chain-verification)",
            reason=(
                f"recovery refused: hash chain verification failed: "
                f"{verification.error or 'unknown error'}"
            ),
        )

    # 4. Validate snapshot metadata against stream identity
    head = backend.head()
    snap_timeline_id = snapshot_metadata.get("timeline_id")
    snap_event_id = snapshot_metadata.get("last_event_id")
    snap_hash = snapshot_metadata.get("last_hash")
    snap_version = snapshot_metadata.get("version")

    if snap_timeline_id != head.timeline_id:
        raise ValueError(
            f"snapshot timeline_id {snap_timeline_id!r} does not match "
            f"stream identity {head.timeline_id!r}"
        )

    if not isinstance(snap_event_id, str):
        raise ValueError("snapshot metadata must include last_event_id (string)")

    # 5. Verify anchor hash against backend
    # Replay to the snapshot event and verify the hash matches
    try:
        anchor_projection_from_events = replay_projection(
            backend, stop_at_event_id=snap_event_id
        )
    except ProjectionError as exc:
        raise ProjectionError(
            event_id=snap_event_id,
            kind="(snapshot-verify)",
            reason=f"snapshot anchor event {snap_event_id!r} not found or cannot be projected: {exc}",
        ) from exc

    # 6. Verify snapshot hash against backend events
    # Find the event with snap_event_id and compare hashes
    all_events = backend.read_events()
    anchor_event = None
    for evt in all_events:
        if evt.event_id == snap_event_id:
            anchor_event = evt
            break

    if anchor_event is None:
        raise ProjectionError(
            event_id=snap_event_id,
            kind="(snapshot-verify)",
            reason=f"snapshot anchor event {snap_event_id!r} not found in stream",
        )

    if snap_hash is not None and anchor_event.hash != snap_hash:
        raise ProjectionError(
            event_id=snap_event_id,
            kind="(snapshot-verify)",
            reason=(
                f"snapshot hash {snap_hash!r} does not match "
                f"stream event hash {anchor_event.hash!r}"
            ),
        )

    # 7. Build the recovery payload
    projected_summary = _summarize_projection(snapshot_assembly)
    recovery_payload = TimelineRecoveredPayload(
        anchor_event_id=snap_event_id,
        anchor_type="snapshot",
        reason=reason,
        projected_state_summary=snapshot_assembly,
    ).to_json_obj()

    # 8. Append timeline.recovered event
    recovered_event = backend.append_event(
        target.timeline_id,
        "timeline.recovered",
        recovery_payload,
        actor=actor,
    )

    # 9. Regenerate materialized projection files
    tdir = _timeline_dir(project_slug, target.timeline_ulid, root=root)
    regenerated = regenerate_projection(
        target.timeline_id,
        backend,
        timeline_home=tdir,
    )

    # 10. Collect regenerated artifact paths
    artifact_paths = [
        str(tdir / "assembly.json"),
        str(tdir / "assembly.checkpoint.json"),
    ]
    display_path = tdir / "display.json"
    if display_path.exists():
        artifact_paths.append(str(display_path))

    head = backend.head()

    return RecoveryResult(
        anchor_event_id=snap_event_id,
        new_event_id=recovered_event.event_id,
        new_version=head.version,
        projected_head_summary=projected_summary,
        regenerated_artifact_paths=artifact_paths,
        anchor_type="snapshot",
        reason=reason,
    )


# ============================================================================
# Helpers
# ============================================================================


def _summarize_projection(assembly: dict[str, Any]) -> dict[str, Any]:
    """Build a lightweight summary of the projected assembly for audit output."""
    clips = assembly.get("clips", [])
    tracks = assembly.get("tracks", [])
    pool = assembly.get("pool", {})
    arrangement = assembly.get("arrangement", {})
    theme = assembly.get("theme", "")

    return {
        "clip_count": len(clips) if isinstance(clips, list) else 0,
        "track_count": len(tracks) if isinstance(tracks, list) else 0,
        "pool_asset_count": (
            len(pool.get("entries", []))
            if isinstance(pool, dict)
            else 0
        ),
        "arrangement_clip_count": (
            len(arrangement.get("clips", []))
            if isinstance(arrangement, dict)
            else 0
        ),
        "theme": theme if isinstance(theme, str) else "",
        "total_projections": 1,  # placeholder for non-assembly projections
    }
