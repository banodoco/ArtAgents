"""Backend-agnostic clip edit primitives.

Every public function resolves the timeline through the selector seam,
constructs a typed payload from the canonical event schema, emits the
event through ``EventLogBackend.append_event(...)``, and returns the
``TimelineEvent``.

**No function imports ``LocalFsBackend`` directly.**  The backend is
always obtained via ``select_timeline_backend`` so that the same code
works with ``LocalFsBackend``, the provisional ``SupabaseBackend``
contract, or any future backend.

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

from ._edit_helpers import (
    ClipEditError,
    _default_actor,
    _materialize,
    _resolve_backend,
)
from .events.schema import (
    ClipAddedPayload,
    ClipAnnotatedPayload,
    ClipKind,
    ClipMovedPayload,
    ClipPosition,
    ClipRemovedPayload,
    ClipReplacedPayload,
    ClipRetimedPayload,
    ClipRetrackedPayload,
    ClipSwappedPayload,
    ClipTextSetPayload,
    TimelineActor,
    TimelineEvent,
)
from .kinds import normalize_event_clip_kind

# ---------------------------------------------------------------------------
# Internal helpers (clip-specific)
# ---------------------------------------------------------------------------


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


def _load_current_assembly(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    from .crud import show_timeline

    record = show_timeline(project_slug, slug, root=root)
    if record is None:
        raise ClipEditError(f"timeline '{slug}' not found in project '{project_slug}'")
    assembly = record.get("assembly")
    if not isinstance(assembly, dict):
        raise ClipEditError(f"timeline '{slug}' has malformed assembly state")
    return assembly


def _require_target_track(
    assembly: dict[str, Any],
    *,
    track_id: str,
    clip_kind: ClipKind | None = None,
) -> dict[str, Any]:
    tracks = assembly.get("tracks")
    if not isinstance(tracks, list):
        raise ClipEditError("timeline tracks projection is malformed")
    for track in tracks:
        if isinstance(track, dict) and track.get("id") == track_id:
            track_kind = track.get("kind")
            if clip_kind is not None:
                expected_kind = "audio" if clip_kind == "audio" else "visual"
                if track_kind != expected_kind:
                    raise ClipEditError(
                        f"track '{track_id}' is {track_kind!r}; "
                        f"{clip_kind} clips require a {expected_kind!r} track"
                    )
            label = track.get("label")
            if not isinstance(label, str) or not label.strip():
                raise ClipEditError(f"track '{track_id}' is missing a non-empty label")
            return track
    raise ClipEditError(f"target track '{track_id}' not found")


def _require_clip_exists(assembly: dict[str, Any], *, clip_id: str) -> dict[str, Any]:
    clips = assembly.get("clips")
    if not isinstance(clips, list):
        raise ClipEditError("timeline clips projection is malformed")
    for clip in clips:
        if isinstance(clip, dict) and clip.get("id") == clip_id:
            return clip
    raise ClipEditError(f"clip '{clip_id}' not found")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# add_clip
# ---------------------------------------------------------------------------


def add_clip(
    project_slug: str,
    slug: str,
    *,
    kind: ClipKind,
    asset_id: str,
    track_id: str | None = None,
    position: ClipPosition | dict[str, Any] | None = None,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
    start: float = 0.0,
    duration: float | None = None,
) -> TimelineEvent:
    """Append a ``clip.added`` event to *slug* in *project_slug*.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        kind: Clip kind — ``"visual"``, ``"audio"``, or ``"text"``.
        asset_id: Asset identifier for the clip.
        track_id: Existing track identifier for the clip; defaults to the
            conventional ``visual``/``audio`` target for API callers.
        position: Where to place the new clip (optional).
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
        start: Start time in seconds (>= 0, default 0.0).
        duration: Duration in seconds (> 0). For audio clips without an
            explicit duration, the asset registry is consulted; if no
            duration is available an error is raised.
    """
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(asset_id, str) or not asset_id.strip():
        raise ClipEditError("asset_id must be a non-empty string")
    kind = normalize_event_clip_kind(kind, error_cls=ClipEditError)
    resolved_track_id = track_id or ("audio" if kind == "audio" else "visual")
    if not isinstance(resolved_track_id, str) or not resolved_track_id.strip():
        raise ClipEditError("track_id must be a non-empty string")
    resolved_track_id = resolved_track_id.strip()
    assembly = _load_current_assembly(project_slug, slug, root=root)
    _require_target_track(assembly, track_id=resolved_track_id, clip_kind=kind)

    pos = _normalise_position(position)

    # Resolve duration with precedence: explicit > registry > fail for audio
    resolved_duration = duration
    if resolved_duration is None:
        from astrid.core._shared.jsonio import read_json

        registry_path = tdir / "registry.json"
        try:
            registry = read_json(registry_path)
        except Exception:
            registry = {}
        if isinstance(registry, dict):
            assets = registry.get("assets", {})
            if isinstance(assets, dict):
                asset_entry = assets.get(asset_id)
                if isinstance(asset_entry, dict):
                    reg_duration = asset_entry.get("duration")
                    if isinstance(reg_duration, (int, float)) and reg_duration > 0:
                        resolved_duration = float(reg_duration)
        if resolved_duration is None and kind == "audio":
            raise ClipEditError(
                f"audio clip '{asset_id}' has no duration; "
                "probe or pass --duration"
            )

    act = actor or _default_actor("add_clip")
    event = backend.append_event(
        timeline_id,
        "clip.added",
        ClipAddedPayload(
            clip_id=asset_id,  # asset_id serves as the clip id for now
            kind=kind,
            track_id=resolved_track_id,
            asset_id=asset_id,
            position=pos,
            start=start,
            duration=resolved_duration,
        ),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
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
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

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
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
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
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

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
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
    return event


# ---------------------------------------------------------------------------
# retrack_clip
# ---------------------------------------------------------------------------


def retrack_clip(
    project_slug: str,
    slug: str,
    *,
    clip_id: str,
    track_id: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``clip.retracked`` event for *clip_id*."""
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_id, str) or not clip_id.strip():
        raise ClipEditError("clip_id must be a non-empty string")
    if not isinstance(track_id, str) or not track_id.strip():
        raise ClipEditError("track_id must be a non-empty string")
    resolved_track_id = track_id.strip()
    assembly = _load_current_assembly(project_slug, slug, root=root)
    _require_clip_exists(assembly, clip_id=clip_id)
    _require_target_track(assembly, track_id=resolved_track_id)

    act = actor or _default_actor("retrack_clip")
    event = backend.append_event(
        timeline_id,
        "clip.retracked",
        ClipRetrackedPayload(clip_id=clip_id, track_id=resolved_track_id),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
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
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

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
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
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
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

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
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
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
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

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
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
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
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

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
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
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
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

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
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
    return event
