"""Audio edit primitives (m3 secondary).

Every public function resolves the timeline through the selector seam,
constructs a typed payload from the canonical event schema, emits the
event through ``EventLogBackend.append_event(...)``, and returns the
``TimelineEvent``.

Audio bind/unbind targets the clip's ``asset_id`` field — the renderable
timeline clip asset relationship.  Arrangement-level audio
(``audio_source.pool_id``) stays with ``arrangement.replaced``.
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
    AudioBoundPayload,
    AudioUnboundPayload,
    TimelineActor,
    TimelineEvent,
)


# ---------------------------------------------------------------------------
# audio_bind
# ---------------------------------------------------------------------------


def audio_bind(
    project_slug: str,
    slug: str,
    *,
    clip_id: str,
    asset_id: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append an ``audio.bound`` event to *slug* in *project_slug*.

    Sets the clip's ``asset_id`` to *asset_id*, establishing a renderable
    timeline clip asset relationship.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        clip_id: The clip to bind audio to.
        asset_id: The audio asset identifier.
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_id, str) or not clip_id.strip():
        raise TimelineEditError("clip_id must be a non-empty string")
    if not isinstance(asset_id, str) or not asset_id.strip():
        raise TimelineEditError("asset_id must be a non-empty string")

    act = actor or _default_actor("audio_bind")
    event = backend.append_event(
        timeline_id,
        "audio.bound",
        AudioBoundPayload(clip_id=clip_id, asset_id=asset_id),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
    return event


# ---------------------------------------------------------------------------
# audio_unbind
# ---------------------------------------------------------------------------


def audio_unbind(
    project_slug: str,
    slug: str,
    *,
    clip_id: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append an ``audio.unbound`` event to *slug* in *project_slug*.

    Clears the clip's ``asset_id``, breaking the renderable timeline clip
    asset relationship.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        clip_id: The clip to unbind audio from.
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_id, str) or not clip_id.strip():
        raise TimelineEditError("clip_id must be a non-empty string")

    act = actor or _default_actor("audio_unbind")
    event = backend.append_event(
        timeline_id,
        "audio.unbound",
        AudioUnboundPayload(clip_id=clip_id),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
    return event
