"""Deterministic cold-scope selection over a frozen inspection model.

Selectors operate only on :class:`TimelineInspectionModel`; they never reopen a
timeline directory or consult current project state.  Frame intersections are
closed-open throughout and use each clip's compositor-mounted interval.  Shot
scope keeps its authored editorial bounds, then intersects mounted clips with
that window.  A project selector represents this model's per-timeline
contribution—the R9 project-index assembler combines one such scope for every
selected timeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Iterable

from astrid.core.timeline.duration import clip_start_frame
from astrid.packs.rendering.executors.timeline_visualize.model import (
    ClipModel,
    TimelineInspectionModel,
)

_KINDS = frozenset({"project", "timeline", "shot", "range", "clip", "asset", "timestamp"})


@dataclass(frozen=True, slots=True)
class Scope:
    kind: str
    ref: str | None
    start_frame: int | None
    end_frame: int | None
    clip_ids: tuple[str, ...]
    emphasized_clip_ids: tuple[str, ...]
    context_frames: int
    warnings: tuple[str, ...] = ()
    at_seconds: float | None = None
    requested_start_frame: int | None = None
    requested_end_frame: int | None = None


def _finite_nonnegative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return result


def _seconds_to_frame(seconds: float, model: TimelineInspectionModel) -> int:
    """Delegate arbitrary boundary conversion to duration.py's JS rounding."""

    return clip_start_frame({"at": seconds, "hold": 0.0}, model.fps)


def _intersects(clip: ClipModel, start_frame: int, end_frame: int) -> bool:
    """Intersect a scope window with the clip's actual mounted Sequence."""

    return (
        clip.mounted.start_frame < end_frame
        and clip.mounted.end_frame > start_frame
    )


def _clips_intersecting(
    model: TimelineInspectionModel,
    start_frame: int,
    end_frame: int,
) -> tuple[str, ...]:
    return tuple(
        clip.clip_id
        for clip in model.clips
        if _intersects(clip, start_frame, end_frame)
    )


def _ordered_ids(
    model: TimelineInspectionModel,
    ids: Iterable[str],
) -> tuple[str, ...]:
    wanted = set(ids)
    return tuple(clip.clip_id for clip in model.clips if clip.clip_id in wanted)


def _empty(kind: str, ref: str | None, warning: str) -> Scope:
    return Scope(kind, ref, None, None, (), (), 0, (warning,))


def _target_clip(
    model: TimelineInspectionModel,
    target_id: str,
) -> ClipModel | None:
    return next((clip for clip in model.clips if clip.clip_id == target_id), None)


def _clip_scope(
    model: TimelineInspectionModel,
    *,
    ref: str | None,
    target_id: str | None,
    context_seconds: float,
    neighbors: int,
) -> Scope:
    if not isinstance(target_id, str) or not target_id:
        raise ValueError("clip scope requires clip_id or an authored-id ref")
    target = _target_clip(model, target_id)
    scope_ref = ref if ref is not None else target_id
    if target is None:
        return _empty("clip", scope_ref, f"clip {target_id!r} is not present in the snapshot")

    same_track = [clip for clip in model.clips if clip.track_id == target.track_id]
    target_index = same_track.index(target)
    first = max(0, target_index - neighbors)
    last = min(len(same_track), target_index + neighbors + 1)
    focused_band = same_track[first:last]
    start_frame = min(clip.mounted.start_frame for clip in focused_band)
    end_frame = max(clip.mounted.end_frame for clip in focused_band)
    context_frames = _seconds_to_frame(context_seconds, model)
    start_frame = max(0, start_frame - context_frames)
    end_frame = min(model.extents.composition_frames, end_frame + context_frames)
    focused_ids = {clip.clip_id for clip in focused_band}
    in_scope = tuple(
        clip.clip_id
        for clip in model.clips
        if clip.clip_id in focused_ids
        or (
            clip.track_id != target.track_id
            and _intersects(clip, start_frame, end_frame)
        )
    )
    return Scope(
        kind="clip",
        ref=scope_ref,
        start_frame=start_frame,
        end_frame=end_frame,
        clip_ids=in_scope,
        emphasized_clip_ids=(target.clip_id,),
        context_frames=context_frames,
    )


def _asset_scope(
    model: TimelineInspectionModel,
    *,
    ref: str | None,
    asset_key: str | None,
) -> Scope:
    if not isinstance(asset_key, str) or not asset_key:
        raise ValueError("asset scope requires asset_key or an authored-id ref")
    scope_ref = ref if ref is not None else asset_key
    uses = [clip for clip in model.clips if asset_key in clip.asset_keys]
    if not uses:
        # Legacy fallback only.  Direct ``clip.asset`` / ``clip.source`` always
        # wins.  The desert fixture happens to have asset==clip id for each
        # plant frame, so either representation resolves to the same clip.
        uses = [
            clip
            for clip in model.clips
            if not clip.asset_keys and clip.clip_id == asset_key
        ]
    if not uses:
        return _empty(
            "asset",
            scope_ref,
            f"asset {asset_key!r} has no clip uses in the snapshot",
        )
    start_frame = min(clip.mounted.start_frame for clip in uses)
    end_frame = max(clip.mounted.end_frame for clip in uses)
    uses_ids = tuple(clip.clip_id for clip in uses)
    return Scope(
        kind="asset",
        ref=scope_ref,
        start_frame=start_frame,
        end_frame=end_frame,
        clip_ids=uses_ids,
        emphasized_clip_ids=uses_ids,
        context_frames=0,
    )


def _shot_scope(
    model: TimelineInspectionModel,
    *,
    ref: str | None,
) -> Scope:
    if not isinstance(ref, str) or not ref:
        raise ValueError("shot scope requires the authored pinnedShotGroups[].shotId as ref")
    shot = next((item for item in model.shots if item.shot_id == ref), None)
    if shot is None:
        return _empty(
            "shot",
            ref,
            f"pinned shot {ref!r} is unavailable; timeline.pinnedShotGroups has no match",
        )
    if shot.frames is None:
        warnings = (
            *shot.warnings,
            f"pinned shot {ref!r} has neither valid authored bounds nor present member clips",
        )
        return Scope("shot", ref, None, None, (), (), 0, warnings)
    # A pinned shot remains an authored editorial window.  Contributor
    # intersection uses compositor-mounted clip intervals so transition-retimed
    # destinations cannot leak into an earlier authored shot window.
    start_frame = shot.frames.start_frame
    end_frame = shot.frames.end_frame
    in_scope = _clips_intersecting(model, start_frame, end_frame)
    emphasized = _ordered_ids(
        model,
        (clip_id for clip_id in shot.member_clip_ids if clip_id in in_scope),
    )
    return Scope(
        kind="shot",
        ref=ref,
        start_frame=start_frame,
        end_frame=end_frame,
        clip_ids=in_scope,
        emphasized_clip_ids=emphasized,
        context_frames=0,
        warnings=shot.warnings,
    )


def _range_scope(
    model: TimelineInspectionModel,
    *,
    ref: str | None,
    start: float | None,
    end: float | None,
) -> Scope:
    if start is None or end is None:
        raise ValueError("range scope requires start and end seconds")
    start_seconds = _finite_nonnegative(start, "range start")
    end_seconds = _finite_nonnegative(end, "range end")
    if end_seconds <= start_seconds:
        raise ValueError("range end must be greater than range start")
    raw_start_frame = _seconds_to_frame(start_seconds, model)
    raw_end_frame = _seconds_to_frame(end_seconds, model)
    composition_end = model.extents.composition_frames
    clipped_start_frame = min(raw_start_frame, composition_end)
    clipped_end_frame = min(raw_end_frame, composition_end)
    warnings: tuple[str, ...] = ()
    if (
        raw_start_frame != clipped_start_frame
        or raw_end_frame != clipped_end_frame
    ):
        warnings = ("range was clipped to the composition bounds",)
    return Scope(
        kind="range",
        ref=ref,
        start_frame=raw_start_frame,
        end_frame=raw_end_frame,
        clip_ids=_clips_intersecting(
            model,
            clipped_start_frame,
            clipped_end_frame,
        ),
        emphasized_clip_ids=(),
        context_frames=0,
        warnings=warnings,
        requested_start_frame=raw_start_frame,
        requested_end_frame=raw_end_frame,
    )


def _timestamp_scope(
    model: TimelineInspectionModel,
    *,
    ref: str | None,
    at_seconds: float | None,
    context_seconds: float,
) -> Scope:
    if at_seconds is None:
        raise ValueError("timestamp scope requires at_seconds")
    instant_seconds = _finite_nonnegative(at_seconds, "timestamp")
    instant_frame = _seconds_to_frame(instant_seconds, model)
    context_frames = _seconds_to_frame(context_seconds, model)
    composition_end = model.extents.composition_frames
    start_frame = min(composition_end, max(0, instant_frame - context_frames))
    end_frame = min(composition_end, instant_frame + context_frames)
    context_ids = _clips_intersecting(model, start_frame, end_frame)
    visual_track_ids = {
        track.track_id for track in model.tracks if track.kind == "visual"
    }
    active_ids = tuple(
        clip.clip_id
        for clip in model.clips
        if clip.track_id in visual_track_ids
        and clip.mounted.start_frame <= instant_frame < clip.mounted.end_frame
    )
    warnings: tuple[str, ...] = ()
    if instant_frame < 0 or instant_frame >= composition_end:
        warnings = ("timestamp lies outside the composition bounds",)
    return Scope(
        kind="timestamp",
        ref=ref,
        start_frame=start_frame,
        end_frame=end_frame,
        clip_ids=context_ids,
        emphasized_clip_ids=active_ids,
        context_frames=context_frames,
        warnings=warnings,
        at_seconds=instant_seconds,
    )


def select_scope(
    model: TimelineInspectionModel,
    *,
    kind: str,
    ref: str | None = None,
    start: float | None = None,
    end: float | None = None,
    clip_id: str | None = None,
    asset_key: str | None = None,
    at_seconds: float | None = None,
    context_seconds: float = 3.0,
    neighbors: int = 0,
) -> Scope:
    """Select one cold scope using compositor frame intersections.

    ``clip_ids`` is the deterministic context set in model order;
    ``emphasized_clip_ids`` identifies the actual focus.  Timestamp emphasis is
    the exact visual compositor stack, while its clip set includes every visual
    or audio contributor intersecting the surrounding context window.
    """

    if not isinstance(model, TimelineInspectionModel):
        raise TypeError("model must be a TimelineInspectionModel")
    if kind not in _KINDS:
        raise ValueError(f"unsupported scope kind {kind!r}")
    context = _finite_nonnegative(context_seconds, "context_seconds")
    if isinstance(neighbors, bool) or not isinstance(neighbors, int) or neighbors < 0:
        raise ValueError("neighbors must be a non-negative integer")
    if neighbors and kind != "clip":
        raise ValueError("neighbors applies only to clip scope")

    if kind in {"project", "timeline"}:
        if kind == "project" and ref is not None:
            raise ValueError("project scope ref must be None")
        return Scope(
            kind=kind,
            ref=ref,
            start_frame=0,
            end_frame=model.extents.composition_frames,
            clip_ids=tuple(clip.clip_id for clip in model.clips),
            emphasized_clip_ids=(),
            context_frames=0,
        )
    if kind == "range":
        return _range_scope(model, ref=ref, start=start, end=end)
    if kind == "shot":
        return _shot_scope(model, ref=ref)
    if kind == "clip":
        target_id = clip_id if clip_id is not None else ref
        return _clip_scope(
            model,
            ref=ref,
            target_id=target_id,
            context_seconds=context,
            neighbors=neighbors,
        )
    if kind == "asset":
        target_key = asset_key if asset_key is not None else ref
        return _asset_scope(model, ref=ref, asset_key=target_key)
    return _timestamp_scope(
        model,
        ref=ref,
        at_seconds=at_seconds,
        context_seconds=context,
    )


__all__ = ["Scope", "select_scope"]
