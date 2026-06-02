"""Transition edit primitives (m3 secondary).

Every public function resolves the timeline through the selector seam,
constructs a typed payload from the canonical event schema, emits the
event through ``EventLogBackend.append_event(...)``, and returns the
``TimelineEvent``.

Transition identity is keyed by the LEFT clip of the adjacent pair.
Materialized as ``clip["transition"] = {kind, right_clip_id, duration_seconds}``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._edit_helpers import (
    TimelineEditError,
    _default_actor,
    _materialize,
    _resolve_backend,
)
from .events.schema import (
    TimelineActor,
    TimelineEvent,
    TransitionRemovedPayload,
    TransitionSetPayload,
)
from .kinds import default_transition_kind, normalize_transition_kind

# ---------------------------------------------------------------------------
# Adjacent same-track transition reconciliation (kernel-level helper)
# ---------------------------------------------------------------------------


def reconcile_adjacent_transitions(
    project_slug: str,
    slug: str,
    *,
    kind: str | None = None,
    duration_seconds: float = 0.5,
    actor: TimelineActor | None = None,
    root: str | Path | None = None,
) -> list[TimelineEvent]:
    """Compute adjacent same-track clip pairs from projected assembly and
    write exactly one ``transition.set`` event per missing adjacent pair.

    This helper is **idempotent**: it reads the current projected assembly,
    groups clips by track (sorted by ``at``), and only emits a
    ``transition.set`` event when a left clip does **not** already carry a
    ``transition`` key pointing to the expected right clip.  Repeated calls
    on an already-reconciled timeline produce zero new events.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        kind: Transition kind (defaults to the registry default, usually
            ``"cross-fade"``).
        duration_seconds: Transition duration in seconds (>0).
        actor: Who performed the action (defaults to a system actor).
        root: Filesystem root override.

    Returns:
        The list of newly-written ``TimelineEvent`` objects (may be empty
        if all adjacent pairs already carry transitions).

    Raises:
        TimelineEditError: When the timeline cannot be found or the assembly
            is malformed.
    """
    if kind is None:
        kind = default_transition_kind(root=root)

    # Read the current projected assembly.  ``show_timeline`` internally
    # resolves the timeline identity and regenerates the projection from
    # the canonical event stream, so we don't need a separate backend
    # resolution at this level.
    from .crud import show_timeline

    record = show_timeline(project_slug, slug, root=root)
    if record is None:
        raise TimelineEditError(f"timeline '{slug}' not found in project '{project_slug}'")
    assembly = record.get("assembly")
    if not isinstance(assembly, dict):
        raise TimelineEditError(f"timeline '{slug}' has malformed assembly state")

    clips: list[dict[str, Any]] = assembly.get("clips", [])
    if not clips:
        return []

    # Group clips by track and sort each group by ``at``.
    by_track: dict[str, list[dict[str, Any]]] = {}
    for clip in clips:
        track_id = clip.get("track")
        if isinstance(track_id, str) and track_id:
            by_track.setdefault(track_id, []).append(clip)

    events: list[TimelineEvent] = []

    for _track_id, track_clips in by_track.items():
        if len(track_clips) < 2:
            continue

        # Sort by ``at`` (the canonical timeline position).
        track_clips.sort(key=lambda c: float(c.get("at", 0)))

        for i in range(len(track_clips) - 1):
            left = track_clips[i]
            right = track_clips[i + 1]

            left_id = left.get("id")
            right_id = right.get("id")
            if not isinstance(left_id, str) or not left_id:
                continue
            if not isinstance(right_id, str) or not right_id:
                continue

            # Check if a transition already exists on the left clip.
            existing = left.get("transition")
            if isinstance(existing, dict):
                params = existing.get("params")
                if isinstance(params, dict) and params.get("right_clip_id") == right_id:
                    # Already reconciled — skip.
                    continue

            event = transition_set(
                project_slug,
                slug,
                left_clip_id=left_id,
                right_clip_id=right_id,
                kind=kind,
                duration_seconds=duration_seconds,
                actor=actor,
                root=root,
            )
            events.append(event)

    return events


# ---------------------------------------------------------------------------
# transition_set
# ---------------------------------------------------------------------------


def transition_set(
    project_slug: str,
    slug: str,
    *,
    left_clip_id: str,
    right_clip_id: str,
    kind: str = default_transition_kind(),
    duration_seconds: float = 0.5,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``transition.set`` event to *slug* in *project_slug*.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        left_clip_id: The LEFT clip id of the adjacent pair.
        right_clip_id: The RIGHT clip id (next same-track clip).
        kind: Transition kind (default ``"cross-fade"``).
        duration_seconds: Transition duration in seconds (>0).
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(kind, str) or not kind.strip():
        raise TimelineEditError("kind must be a non-empty string")
    kind = normalize_transition_kind(kind, error_cls=TimelineEditError)
    if not isinstance(duration_seconds, (int, float)) or isinstance(duration_seconds, bool):
        raise TimelineEditError("duration_seconds must be a number")
    if duration_seconds <= 0:
        raise TimelineEditError("duration_seconds must be > 0")

    act = actor or _default_actor("transition_set")
    event = backend.append_event(
        timeline_id,
        "transition.set",
        TransitionSetPayload(
            left_clip_id=left_clip_id,
            right_clip_id=right_clip_id,
            kind=kind,
            duration_seconds=float(duration_seconds),
        ),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
    return event


# ---------------------------------------------------------------------------
# transition_remove
# ---------------------------------------------------------------------------


def transition_remove(
    project_slug: str,
    slug: str,
    *,
    left_clip_id: str,
    right_clip_id: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``transition.removed`` event to *slug* in *project_slug*.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        left_clip_id: The LEFT clip id whose transition to remove.
        right_clip_id: The RIGHT clip id (for payload identity).
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(left_clip_id, str) or not left_clip_id.strip():
        raise TimelineEditError("left_clip_id must be a non-empty string")
    if not isinstance(right_clip_id, str) or not right_clip_id.strip():
        raise TimelineEditError("right_clip_id must be a non-empty string")

    act = actor or _default_actor("transition_remove")
    event = backend.append_event(
        timeline_id,
        "transition.removed",
        TransitionRemovedPayload(
            left_clip_id=left_clip_id,
            right_clip_id=right_clip_id,
        ),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
    return event
