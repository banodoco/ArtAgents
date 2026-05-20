"""Backend-agnostic clip edit primitives.

Every public function resolves the timeline through the selector seam,
constructs a typed payload from the canonical event schema, emits the
event through ``EventLogBackend.append_event(...)``, and returns the
``TimelineEvent``.

**No function imports ``LocalFsBackend`` directly.**  The backend is
always obtained via ``select_timeline_backend`` so that the same code
works with ``LocalFsBackend``, ``SupabaseBackend`` (stub), or any
future backend.

Pass-through keyword arguments ``actor``, ``expected_version``, and
``txn_id`` are forwarded unchanged so callers can drive authentication
and concurrency control without the module needing to know those
details (enforcement remains a m5 concern).

clip 'id' strings are the canonical m2 identity.
Migration to UUID entity_id/external_id is deferred to a later milestone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.core.project.jsonio import read_json

from .assembly_helper import materialize_clip_event
from .eventlog import EventLogBackend, select_timeline_backend
from .events.schema import (
    ClipAddedPayload,
    ClipAnnotatedPayload,
    ClipKind,
    ClipMovedPayload,
    ClipPosition,
    ClipRemovedPayload,
    ClipReplacedPayload,
    ClipRetimedPayload,
    ClipSwappedPayload,
    ClipTextSetPayload,
    TimelineActor,
    TimelineEvent,
)
from .paths import assembly_identity_path, find_timeline_by_slug


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_backend(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
) -> tuple[str, Path, EventLogBackend]:
    """Look up *slug* in *project_slug*, read the identity sidecar, and
    return ``(timeline_id, timeline_home, backend)``.

    Raises ``ClipEditError`` when the timeline cannot be found or its
    identity sidecar is missing/malformed.
    """
    found = find_timeline_by_slug(project_slug, slug, root=root)
    if found is None:
        raise ClipEditError(
            f"timeline '{slug}' not found in project '{project_slug}'"
        )
    ulid, tdir = found

    identity = read_json(assembly_identity_path(project_slug, ulid, root=root))
    if not isinstance(identity, dict):
        raise ClipEditError("timeline identity sidecar is malformed")

    timeline_id = identity.get("timeline_id")
    if not isinstance(timeline_id, str) or not timeline_id:
        raise ClipEditError("timeline identity sidecar is missing timeline_id")

    preferred_backend = identity.get("backend")
    if preferred_backend is not None and not isinstance(preferred_backend, str):
        raise ClipEditError("timeline identity sidecar has malformed backend")

    _stream, backend = select_timeline_backend(
        timeline_id=timeline_id,
        timeline_home=tdir,
        preferred_backend=preferred_backend,
    )
    return timeline_id, tdir, backend


def _materialize(tdir: Path, event: TimelineEvent) -> None:
    """Synchronous compatibility materializer call — m4 removal seam.

    Keeps ``assembly.json`` in sync with the event stream so that
    readers like ``crud.show_timeline()`` see the latest clip state
    before projection becomes authoritative in m4.

    A crash between ``append_event`` and this call leaves the event log
    ahead of ``assembly.json``.  Accept this window for m2; m4 projection
    will close it.
    """
    materialize_clip_event(tdir, event)


def _normalise_position(
    value: ClipPosition | dict[str, Any] | None,
) -> ClipPosition | None:
    """Return a :class:`ClipPosition` or ``None``, raising early on
    an invalid dict shape so the caller gets a clear message before
    the append attempt."""
    if value is None:
        return None
    if isinstance(value, ClipPosition):
        return value
    if isinstance(value, dict):
        return ClipPosition.from_dict(value)
    raise ClipEditError(
        "position must be a ClipPosition or dict, "
        f"not {type(value).__name__}"
    )


def _default_actor(fn_name: str) -> TimelineActor:
    """Return a sensible system actor for clip-editing operations."""
    return TimelineActor(
        type="system",
        id=f"timeline-clip-edits:{fn_name}",
        display="timeline-clip-edits",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ClipEditError(RuntimeError):
    """Raised when a clip edit cannot be completed."""


# ---------------------------------------------------------------------------
# add_clip
# ---------------------------------------------------------------------------


def add_clip(
    project_slug: str,
    slug: str,
    *,
    kind: ClipKind,
    asset_id: str,
    position: ClipPosition | dict[str, Any] | None = None,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``clip.added`` event to *slug* in *project_slug*.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        kind: Clip kind — ``"visual"``, ``"audio"``, or ``"text"``.
        asset_id: Asset identifier for the clip.
        position: Where to place the new clip (optional).
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(asset_id, str) or not asset_id.strip():
        raise ClipEditError("asset_id must be a non-empty string")
    if kind not in {"visual", "audio", "text"}:
        raise ClipEditError(f"kind must be 'visual', 'audio', or 'text', got {kind!r}")

    pos = _normalise_position(position)

    act = actor or _default_actor("add_clip")
    event = backend.append_event(
        timeline_id,
        "clip.added",
        ClipAddedPayload(
            clip_id=asset_id,  # asset_id serves as the clip id for now
            kind=kind,
            asset_id=asset_id,
            position=pos,
        ),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event


# ---------------------------------------------------------------------------
# remove_clip
# ---------------------------------------------------------------------------


def remove_clip(
    project_slug: str,
    slug: str,
    *,
    clip_id: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``clip.removed`` event for *clip_id*."""
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_id, str) or not clip_id.strip():
        raise ClipEditError("clip_id must be a non-empty string")

    act = actor or _default_actor("remove_clip")
    event = backend.append_event(
        timeline_id,
        "clip.removed",
        ClipRemovedPayload(clip_id=clip_id),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event


# ---------------------------------------------------------------------------
# move_clip
# ---------------------------------------------------------------------------


def move_clip(
    project_slug: str,
    slug: str,
    *,
    clip_id: str,
    position: ClipPosition | dict[str, Any],
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``clip.moved`` event for *clip_id* to *position*."""
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_id, str) or not clip_id.strip():
        raise ClipEditError("clip_id must be a non-empty string")

    pos = _normalise_position(position)
    if pos is None:
        raise ClipEditError("position is required for clip.moved")

    act = actor or _default_actor("move_clip")
    event = backend.append_event(
        timeline_id,
        "clip.moved",
        ClipMovedPayload(clip_id=clip_id, position=pos),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event


# ---------------------------------------------------------------------------
# retime_clip
# ---------------------------------------------------------------------------


def retime_clip(
    project_slug: str,
    slug: str,
    *,
    clip_id: str,
    start: float,
    duration: float,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``clip.retimed`` event for *clip_id*."""
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_id, str) or not clip_id.strip():
        raise ClipEditError("clip_id must be a non-empty string")
    if not isinstance(start, (int, float)) or isinstance(start, bool):
        raise ClipEditError("start must be a number")
    if start < 0:
        raise ClipEditError("start must be >= 0")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool):
        raise ClipEditError("duration must be a number")
    if duration <= 0:
        raise ClipEditError("duration must be > 0")

    act = actor or _default_actor("retime_clip")
    event = backend.append_event(
        timeline_id,
        "clip.retimed",
        ClipRetimedPayload(clip_id=clip_id, start=start, duration=duration),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event


# ---------------------------------------------------------------------------
# swap_clips
# ---------------------------------------------------------------------------


def swap_clips(
    project_slug: str,
    slug: str,
    *,
    clip_a_id: str,
    clip_b_id: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``clip.swapped`` event for two clips."""
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_a_id, str) or not clip_a_id.strip():
        raise ClipEditError("clip_a_id must be a non-empty string")
    if not isinstance(clip_b_id, str) or not clip_b_id.strip():
        raise ClipEditError("clip_b_id must be a non-empty string")
    if clip_a_id == clip_b_id:
        raise ClipEditError("clip_a_id and clip_b_id must be different")

    act = actor or _default_actor("swap_clips")
    event = backend.append_event(
        timeline_id,
        "clip.swapped",
        ClipSwappedPayload(clip_a_id=clip_a_id, clip_b_id=clip_b_id),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event


# ---------------------------------------------------------------------------
# replace_clip
# ---------------------------------------------------------------------------


def replace_clip(
    project_slug: str,
    slug: str,
    *,
    clip_id: str,
    with_asset_id: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``clip.replaced`` event for *clip_id*."""
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_id, str) or not clip_id.strip():
        raise ClipEditError("clip_id must be a non-empty string")
    if not isinstance(with_asset_id, str) or not with_asset_id.strip():
        raise ClipEditError("with_asset_id must be a non-empty string")

    act = actor or _default_actor("replace_clip")
    event = backend.append_event(
        timeline_id,
        "clip.replaced",
        ClipReplacedPayload(clip_id=clip_id, with_asset_id=with_asset_id),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event


# ---------------------------------------------------------------------------
# set_clip_text
# ---------------------------------------------------------------------------


def set_clip_text(
    project_slug: str,
    slug: str,
    *,
    clip_id: str,
    text: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``clip.text_set`` event for *clip_id*."""
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_id, str) or not clip_id.strip():
        raise ClipEditError("clip_id must be a non-empty string")
    if not isinstance(text, str):
        raise ClipEditError("text must be a string")

    act = actor or _default_actor("set_clip_text")
    event = backend.append_event(
        timeline_id,
        "clip.text_set",
        ClipTextSetPayload(clip_id=clip_id, text=text),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event


# ---------------------------------------------------------------------------
# annotate_clip
# ---------------------------------------------------------------------------


def annotate_clip(
    project_slug: str,
    slug: str,
    *,
    clip_id: str,
    note: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``clip.annotated`` event for *clip_id*."""
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_id, str) or not clip_id.strip():
        raise ClipEditError("clip_id must be a non-empty string")
    if not isinstance(note, str):
        raise ClipEditError("note must be a string")

    act = actor or _default_actor("annotate_clip")
    event = backend.append_event(
        timeline_id,
        "clip.annotated",
        ClipAnnotatedPayload(clip_id=clip_id, note=note),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event
