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
from .events.schema import TimelineActor, TimelineEvent, TransitionRemovedPayload, TransitionSetPayload


# ---------------------------------------------------------------------------
# transition_set
# ---------------------------------------------------------------------------


def transition_set(
    project_slug: str,
    slug: str,
    *,
    left_clip_id: str,
    right_clip_id: str,
    kind: str = "cross-fade",
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
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(kind, str) or not kind.strip():
        raise TimelineEditError("kind must be a non-empty string")
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
            kind=kind.strip(),
            duration_seconds=float(duration_seconds),
        ),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
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
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

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
    _materialize(tdir, event)
    return event
