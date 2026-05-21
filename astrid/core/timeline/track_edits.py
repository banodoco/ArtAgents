"""Track edit primitives (m3 secondary).

Every public function resolves the timeline through the selector seam,
constructs a typed payload from the canonical event schema, emits the
event through ``EventLogBackend.append_event(...)``, and returns the
``TimelineEvent``.

Tracks are ``list[dict]`` with ``{id, kind ("visual"|"audio"), label | None}``.
Captions remain visual tracks with label convention; no separate caption kind.
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
    TrackAddedPayload,
    TrackKind,
    TrackRemovedPayload,
)


# ---------------------------------------------------------------------------
# track_add
# ---------------------------------------------------------------------------


def track_add(
    project_slug: str,
    slug: str,
    *,
    track_id: str,
    kind: TrackKind,
    label: str | None = None,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``track.added`` event to *slug* in *project_slug*.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        track_id: Unique track identifier (UUID recommended for new tracks).
        kind: Track kind — ``"visual"`` or ``"audio"`` only.
              Captions remain visual tracks with a ``"captions"`` label.
        label: Optional human-readable label.
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(track_id, str) or not track_id.strip():
        raise TimelineEditError("track_id must be a non-empty string")
    if kind not in {"visual", "audio"}:
        raise TimelineEditError(f"kind must be 'visual' or 'audio', got {kind!r}")
    if label is not None and (not isinstance(label, str) or not label.strip()):
        raise TimelineEditError("label must be a non-empty string when provided")

    act = actor or _default_actor("track_add")
    event = backend.append_event(
        timeline_id,
        "track.added",
        TrackAddedPayload(track_id=track_id, kind=kind, label=label),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
    return event


# ---------------------------------------------------------------------------
# track_remove
# ---------------------------------------------------------------------------


def track_remove(
    project_slug: str,
    slug: str,
    *,
    track_id: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``track.removed`` event to *slug* in *project_slug*.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        track_id: The track identifier to remove.
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(track_id, str) or not track_id.strip():
        raise TimelineEditError("track_id must be a non-empty string")

    act = actor or _default_actor("track_remove")
    event = backend.append_event(
        timeline_id,
        "track.removed",
        TrackRemovedPayload(track_id=track_id),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
    return event
