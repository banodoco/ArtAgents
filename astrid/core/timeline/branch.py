"""Branch creation for timeline event streams.

Provides ``create_branch_timeline()`` that creates a new timeline whose
provenance is ``branched`` (not ``created`` or ``imported``).  The branch
starts with a dedicated branch seed/recovery event containing the projected
assembly from the source timeline at a given anchor point.

Key provenance invariants:
- Branch identity: ``provenance: branched``, distinct from ``created`` and
  ``imported``.
- ``timeline.branched_from`` is emitted on the source timeline ONLY after
  the branch exists, its seed event is appended, and its projection
  verifies successfully.
- ``branches <slug>`` lists branches by reading ``timeline.branched_from``
  events from the source stream (no reverse lookup scan of all timelines).
- Normal ``provenance: created`` invariant remains intact for non-branch
  timelines.
- Failed branch creation does NOT emit ``timeline.branched_from`` on the
  source.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from astrid.core.project.jsonio import write_json_atomic
from astrid.core.util.time import utc_now_seconds as utc_now_iso
from astrid.core.timeline.banodoco_schema import validate_timeline_config_for_container

from .eventlog.local_fs import LocalFsBackend
from .events.schema import (
    EVENT_SCHEMA_VERSION,
    TimelineActor,
    TimelineBranchedFromPayload,
    TimelineRecoveredPayload,
)
from .observability import resolve_timeline_target
from .projection import ProjectionError, regenerate_projection, replay_projection

# ============================================================================
# Structured results
# ============================================================================


@dataclass(frozen=True)
class BranchResult:
    """Result of a successful branch creation operation."""

    branch_timeline_id: str
    """UUID of the new branch timeline."""

    branch_timeline_ulid: str
    """ULID of the new branch timeline directory."""

    branch_slug: str
    """Slug of the new branch timeline."""

    anchor_event_id: str
    """The source event ID the branch was created from."""

    seed_event_id: str
    """ULID of the branch seed/recovery event appended to the branch."""

    source_branched_from_event_id: str
    """ULID of the ``timeline.branched_from`` event appended to the source."""

    source_anchor_hash: str
    """Hash of the anchor event on the source stream."""

    branch_projection_summary: dict[str, Any]
    """Summary of the projected assembly on the branch."""


# ============================================================================
# create_branch_timeline
# ============================================================================


def create_branch_timeline(
    project_slug: str,
    source_slug_or_id: str,
    branch_slug: str,
    *,
    from_event_id: str,
    actor: TimelineActor,
    reason: str = "",
    root: str | Path | None = None,
) -> BranchResult:
    """Create a branch timeline from a source timeline at a given event.

    1. Resolve source timeline and verify its hash chain.
    2. Project source to the anchor event (*from_event_id*).
    3. Create a new timeline directory with ``provenance: branched`` identity.
    4. Append a branch seed/recovery event to the new branch containing the
       projected assembly from the source anchor point.
    5. Verify the branch projection.
    6. Only after steps 1-5 succeed, append ``timeline.branched_from`` to
       the source timeline.

    If any step fails before step 6, NO ``timeline.branched_from`` event
    is written to the source (invariant: failed branch creation must not
    pollute the source stream).

    Args:
        project_slug: Project that owns the source timeline.
        source_slug_or_id: Source timeline slug, ULID, or UUID.
        branch_slug: Slug for the new branch timeline.
        from_event_id: Source event ID to branch from (anchor point).
        actor: Who performed the branch creation.
        reason: Human-readable reason for the branch.
        root: Optional project root override.

    Returns:
        BranchResult with both timeline IDs, event IDs, and projection summary.

    Raises:
        ValueError: When the source cannot be resolved or the branch slug
            already exists.
        ProjectionError: When chain verification or projection fails.
    """
    from astrid.threads.ids import generate_ulid

    from .paths import (
        find_timeline_by_event_stream_id,
        find_timeline_by_slug,
        timeline_dir,
        validate_timeline_slug,
    )

    # 1. Resolve source timeline
    source_target = resolve_timeline_target(project_slug, source_slug_or_id, root=root)

    # Build backend for source
    from .eventlog import build_timeline_backend, select_timeline_stream

    source_stream = select_timeline_stream(
        timeline_id=source_target.timeline_id,
        timeline_home=source_target.timeline_home,
        preferred_backend=source_target.backend,
    )
    source_backend = build_timeline_backend(source_stream)

    # 2. Verify source chain
    verification = source_backend.verify_chain()
    if not verification.ok:
        raise ProjectionError(
            event_id=verification.last_event_id or "(unknown)",
            kind="(chain-verification)",
            reason=(
                f"branch creation refused: source hash chain verification failed: "
                f"{verification.error or 'unknown error'}"
            ),
        )

    # 3. Project source to anchor event and validate the replayed anchor as
    # the raw TimelineConfig that will seed the branch.
    try:
        anchor_projection = _validate_branch_seed_config(
            replay_projection(source_backend, stop_at_event_id=from_event_id),
            event_id=from_event_id,
            label="replayed branch anchor projection",
        )
    except ProjectionError:
        raise
    except Exception as exc:
        raise ProjectionError(
            event_id=from_event_id,
            kind="(branch-anchor)",
            reason=f"failed to project source to anchor event: {exc}",
        ) from exc

    # Find anchor event to get its hash
    all_source_events = source_backend.read_events()
    anchor_event = None
    for evt in all_source_events:
        if evt.event_id == from_event_id:
            anchor_event = evt
            break

    if anchor_event is None:
        raise ProjectionError(
            event_id=from_event_id,
            kind="(branch-anchor)",
            reason=f"anchor event {from_event_id!r} not found in source stream",
        )

    anchor_hash = anchor_event.hash or ""

    # 4. Validate branch slug
    slug = validate_timeline_slug(branch_slug)
    existing = find_timeline_by_slug(project_slug, slug, root=root)
    if existing is not None:
        raise ValueError(
            f"branch slug '{slug}' already exists in project '{project_slug}' "
            f"(ULID {existing[0]}); choose a different branch slug"
        )

    # Also check by UUID (branch UUID is new, so no collision expected, but
    # we guard anyway)
    branch_timeline_id = str(uuid4())
    existing_uuid = find_timeline_by_event_stream_id(project_slug, branch_timeline_id, root=root)
    if existing_uuid is not None:
        raise ValueError(
            f"branch timeline UUID collision: {branch_timeline_id} already exists"
        )

    # 5. Create branch timeline directory
    ulid = generate_ulid()
    tdir = timeline_dir(project_slug, ulid, root=root)
    tdir.mkdir(parents=True, exist_ok=False)

    try:
        # 6. Write branch identity with provenance: branched
        identity = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "timeline_id": branch_timeline_id,
            "timeline_ulid": ulid,
            "backend": "local_fs",
            "provenance": "branched",
            "created_at": utc_now_iso(),
            "source_timeline_id": source_target.timeline_id,
            "source_anchor_event_id": from_event_id,
            "source_anchor_hash": anchor_hash,
        }
        identity_path = tdir / "assembly.identity.json"
        write_json_atomic(identity_path, identity)

        # 7. Create branch backend and append seed/recovery event
        branch_backend = LocalFsBackend(
            timeline_id=branch_timeline_id,
            timeline_home=tdir,
        )

        # The seed event uses timeline.recovered payload to anchor the
        # branch's initial state to the source's projected assembly
        seed_payload_obj = TimelineRecoveredPayload(
            anchor_event_id=from_event_id,
            anchor_type="event",
            reason=f"branch from {source_target.slug} at {from_event_id}"
            + (f": {reason}" if reason else ""),
            projected_state_summary=anchor_projection,
        ).to_json_obj()

        seed_event = branch_backend.append_event(
            branch_timeline_id,
            "timeline.recovered",
            seed_payload_obj,
            actor=actor,
        )

        # 8. Verify branch projection
        branch_projection = replay_projection(branch_backend)
        branch_summary = _summarize_projection(branch_projection)

        # 9. Regenerate branch projection files
        regenerate_projection(
            branch_timeline_id,
            branch_backend,
            timeline_home=tdir,
        )

        # 10. Write minimal display.json for the branch
        _write_branch_display(tdir, slug)

        # === BRANCH IS NOW FULLY CREATED AND VERIFIED ===
        # Only now do we append timeline.branched_from to the source.

        # 11. Append timeline.branched_from to source
        branched_from_payload = TimelineBranchedFromPayload(
            branch_timeline_id=branch_timeline_id,
            anchor_event_id=from_event_id,
            reason=reason if reason else None,
        ).to_json_obj()

        source_branched_event = source_backend.append_event(
            source_target.timeline_id,
            "timeline.branched_from",
            branched_from_payload,
            actor=actor,
        )

        return BranchResult(
            branch_timeline_id=branch_timeline_id,
            branch_timeline_ulid=ulid,
            branch_slug=slug,
            anchor_event_id=from_event_id,
            seed_event_id=seed_event.event_id,
            source_branched_from_event_id=source_branched_event.event_id,
            source_anchor_hash=anchor_hash,
            branch_projection_summary=branch_summary,
        )

    except Exception:
        # Clean up the branch directory on failure (but never touch source)
        import shutil
        if tdir.exists():
            shutil.rmtree(tdir, ignore_errors=True)
        raise


# ============================================================================
# List branches
# ============================================================================


def list_branches(
    project_slug: str,
    slug_or_id: str,
    *,
    root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """List branches of a source timeline by reading ``timeline.branched_from``
    events from the source stream only.

    Does NOT scan all timelines for reverse lookup — uses source-stream
    events only as required by the provenance design.

    Returns a list of dicts with keys: branch_timeline_id, anchor_event_id,
    reason, event_id (the branched_from event ID), ts (when branched).
    """
    source_target = resolve_timeline_target(project_slug, slug_or_id, root=root)

    from .eventlog import build_timeline_backend, select_timeline_stream

    source_stream = select_timeline_stream(
        timeline_id=source_target.timeline_id,
        timeline_home=source_target.timeline_home,
        preferred_backend=source_target.backend,
    )
    source_backend = build_timeline_backend(source_stream)

    all_events = source_backend.read_events()

    branches: list[dict[str, Any]] = []
    for evt in all_events:
        if evt.kind == "timeline.branched_from":
            payload = evt.payload
            if isinstance(payload, TimelineBranchedFromPayload):
                branches.append({
                    "event_id": evt.event_id,
                    "ts": evt.ts,
                    "branch_timeline_id": payload.branch_timeline_id,
                    "anchor_event_id": payload.anchor_event_id,
                    "reason": payload.reason,
                })

    return branches


# ============================================================================
# Helpers
# ============================================================================


def _summarize_projection(assembly: dict[str, Any]) -> dict[str, Any]:
    """Build a lightweight summary of the projected assembly for audit output."""
    clips = assembly.get("clips", [])
    tracks = assembly.get("tracks", [])

    return {
        "clip_count": len(clips) if isinstance(clips, list) else 0,
        "track_count": len(tracks) if isinstance(tracks, list) else 0,
    }


def _validate_branch_seed_config(
    config: dict[str, Any],
    *,
    event_id: str,
    label: str,
) -> dict[str, Any]:
    try:
        return validate_timeline_config_for_container(config)
    except Exception as exc:
        raise ProjectionError(
            event_id=event_id,
            kind="(branch-anchor)",
            reason=f"{label} is not a valid raw TimelineConfig: {exc}",
        ) from exc


def _write_branch_display(tdir: Path, slug: str) -> None:
    """Write a minimal display.json for a branch timeline."""
    from astrid.core.timeline.model import Display

    display = Display(
        schema_version=1,
        slug=slug,
        name=slug,
        is_default=False,
    )
    display.write(tdir / "display.json")
