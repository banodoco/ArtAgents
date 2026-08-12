"""Deterministic shared geometry for timeline visualization pages.

The module has one renderer-independent page model and two readings:

``time-scaled``
    Clip geometry is derived from closed-open compositor frame intervals.  A
    page covers at most 90 seconds, so a long composition is split into
    contiguous frame windows instead of compressing its visual portion.  If a
    time/lane cell still has more than ``max_objects_per_page`` primary clips,
    it is split into deterministic object bands with the same ruler window.

``linear``
    Equal-sized cards follow ``model.clips`` order.  Width never claims to
    encode time; every card prints start, end, duration, and explicitly named
    authored seconds.  The effective page capacity is the smaller of the
    caller's cap and twelve readable cards.

Track lanes are presented topmost-first: visual tracks in configuration order,
then other tracks in configuration order.  Painting is independent of reading
order.  Visual clip ``z_order`` follows ``TrackModel.paint_index`` from bottom
to top, so the first configured visual track paints last/on top.

``max_objects_per_page`` counts primary identity-bearing clip/card objects.
Repeated page chrome, lanes, ticks, gap/overlap annotations, and continuation
primitives are deliberately outside that density cap.  A primary clip appears
exactly once across the result.  When its interval crosses a time boundary, a
``continuation`` primitive shows the clipped segment on the other page(s).

The v1 ``view-map.json`` schema has a narrower identity vocabulary than
``LayoutObject``: it accepts only ground-truth TL/SH/RG/CL/AS/TS/SP refs.
Consequently :func:`serialize_view_map` emits object boxes for semantic
``clip`` and ``asset_card`` objects and label boxes for standalone ``label``
objects, while other page chrome remains available to R11 through the full
``LayoutPage``.  This is an intentional schema adaptation; no synthetic
track/tick/badge ids are invented.
"""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from astrid.packs.rendering.executors.timeline_visualize.model import (
    ClipModel,
    TimelineInspectionModel,
    TrackModel,
)
from astrid.packs.rendering.executors.timeline_visualize.navigation import (
    IdentityMap,
    assign_range_ids,
)
from astrid.packs.rendering.executors.timeline_visualize.scope import Scope
from astrid.packs.rendering.executors.timeline_visualize.transcripts import (
    SpeechOccurrence,
    TranscriptSegment,
)

PAGE_W = 1920
PAGE_H = 1080

# A8's readable-density finding: at 1920 px, about 90 seconds is the largest
# useful ruler window at roughly 20 px/s.  The frame count is derived per model
# so non-24-fps timelines retain the same temporal policy.
MAX_TIME_SPAN_SECONDS = 90
MAX_LANES_PER_PAGE = 8
MAX_LINEAR_CARDS_PER_PAGE = 12

_PLOT_X = 240.0
_PLOT_W = 1600.0
_RULER_Y = 150.0
_RULER_LABEL_W = 320.0
_RULER_LABEL_H = 30.0
_LANES_Y = 226.0
_LANE_H = 92.0
_LANE_GAP = 10.0
_CLIP_PAD = 8.0
# Root visual clip 360px at y=234–594 (lane 226 + pad). Audio clip 48px.
_VISUAL_CLIP_H_ROOT = 220.0
_VISUAL_LANE_H_ROOT = _VISUAL_CLIP_H_ROOT + 2.0 * _CLIP_PAD
_AUDIO_CLIP_H = 48.0
_AUDIO_LANE_H = _AUDIO_CLIP_H + 2.0 * _CLIP_PAD
# Focused/zoom/range visual clip 420px; audio stays 48px.
_VISUAL_CLIP_H_FOCUS = 420.0
_VISUAL_LANE_H_FOCUS = _VISUAL_CLIP_H_FOCUS + 2.0 * _CLIP_PAD
_MIN_CLIP_W = 4.0
_MIN_VISUAL_CARD_W = 320.0
_MIN_VISUAL_CARD_H = 180.0
_INSET_GAP = 16.0
_INSET_Y_OFFSET = 48.0
_DURATION_BAR_H = 24.0
_FOCUS_RING_PX = 4.0
_LINEAR_COLUMNS = 3
_LINEAR_CARD_W = 500.0
_LINEAR_CARD_H = 176.0
_LINEAR_CARD_GAP_X = 26.0
_LINEAR_CARD_GAP_Y = 24.0

_Z_LANE = 10
_Z_TICK = 50
_Z_CLIP_BASE = 1_000_000
_Z_STRIDE = 1_000_000
_Z_ANNOTATION = 20_000_000
_Z_CHROME = 30_000_000
_TEXT_LANE_Y = 700.0
_TEXT_LANE_Y_FOCUS = 740.0
_TEXT_LANE_H = 54.0
_TEXT_LANE_GAP = 8.0


@dataclass(frozen=True)
class Box:
    """Page-local pixel rectangle."""

    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class LayoutObject:
    """One renderer-independent primitive in deterministic reading order."""

    display_id: str
    kind: str
    box: Box
    lane_index: int | None
    z_order: int
    label: str | None
    omitted_reason: str | None
    thumbnail_path: str | None = None


@dataclass(frozen=True)
class LayoutPage:
    """One 1920 x 1080 page shared by the SVG and PNG adapters."""

    page_index: int
    page_id: str
    layout: str
    scope_ref: str
    scope_bounds_frames: tuple[int, int]
    width: int
    height: int
    objects: tuple[LayoutObject, ...]
    reading_order: tuple[str, ...]
    continuation: tuple[str, ...]


@dataclass(frozen=True)
class _PageSpec:
    window_index: int
    band_index: int
    chunk_index: int
    start_frame: int
    end_frame: int
    lane_indices: tuple[int, ...]
    clip_ids: tuple[str, ...]


def _timeline_ref(model: TimelineInspectionModel, identity_map: IdentityMap) -> str:
    result = identity_map.lookup_semantic("timeline", model.timeline_uuid)
    if result is None:
        raise ValueError("identity_map has no display id for the model timeline")
    return result


def _clip_ref(identity_map: IdentityMap, clip: ClipModel) -> str:
    result = identity_map.lookup_semantic("clip", clip.clip_id)
    if result is None:
        raise ValueError(f"clip {clip.clip_id!r} has no display id in identity_map")
    return result


def _timestamp_locator(timeline_ref: str, seconds: float) -> str:
    total_ms = int(math.floor(seconds * 1000.0 + 0.5))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    return f"{timeline_ref}@{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _resolved_scope_ref(
    model: TimelineInspectionModel,
    identity_map: IdentityMap,
    scope: Scope,
) -> str:
    timeline_ref = _timeline_ref(model, identity_map)
    if scope.kind in {"project", "timeline"}:
        return timeline_ref
    if scope.kind == "timestamp":
        if isinstance(scope.ref, str) and "@" in scope.ref:
            return scope.ref
        seconds = scope.at_seconds
        if seconds is None and scope.start_frame is not None and scope.end_frame is not None:
            seconds = (scope.start_frame + scope.end_frame) / 2.0 / model.fps
        return _timestamp_locator(timeline_ref, 0.0 if seconds is None else seconds)

    semantic_kind = {
        "shot": "shot",
        "range": "range",
        "clip": "clip",
        "asset": "asset",
        "text": "transcript_source_segment",
        "speech": "speech_occurrence",
    }.get(scope.kind)
    if semantic_kind is None:
        return timeline_ref
    if isinstance(scope.ref, str):
        semantic = identity_map.lookup_display(scope.ref)
        if semantic is not None and semantic[1] == semantic_kind:
            return scope.ref
        result = identity_map.lookup_semantic(semantic_kind, scope.ref)
        if result is not None:
            return result
    if scope.kind == "clip" and scope.emphasized_clip_ids:
        result = identity_map.lookup_semantic("clip", scope.emphasized_clip_ids[0])
        if result is not None:
            return result
    if scope.kind == "range" and scope.start_frame is not None and scope.end_frame is not None:
        authored_id = scope.ref or f"range-{scope.start_frame}-{scope.end_frame}"
        ranged = assign_range_ids(
            identity_map,
            [(authored_id, scope.start_frame / model.fps, scope.end_frame / model.fps)],
        )
        result = ranged.lookup_semantic("range", authored_id)
        if result is not None:
            return result
    # Empty/missing cold scopes still need a schema-valid lineage anchor.
    return timeline_ref


def _scope_bounds(model: TimelineInspectionModel, scope: Scope) -> tuple[int, int]:
    start = 0 if scope.start_frame is None else scope.start_frame
    end = start if scope.end_frame is None else scope.end_frame
    if isinstance(start, bool) or not isinstance(start, int) or start < 0:
        raise ValueError("scope.start_frame must be a non-negative integer or None")
    if isinstance(end, bool) or not isinstance(end, int) or end < start:
        raise ValueError("scope.end_frame must be an integer not earlier than start_frame")
    return start, end


def _ordered_tracks(model: TimelineInspectionModel) -> tuple[TrackModel, ...]:
    visual = sorted(
        (track for track in model.tracks if track.kind == "visual"),
        key=lambda track: track.config_order,
    )
    other = sorted(
        (track for track in model.tracks if track.kind != "visual"),
        key=lambda track: track.config_order,
    )
    return tuple((*visual, *other))


def _lane_maps(
    model: TimelineInspectionModel,
) -> tuple[tuple[TrackModel, ...], dict[str, int], dict[str, int]]:
    tracks = _ordered_tracks(model)
    lanes = {track.track_id: index for index, track in enumerate(tracks)}
    visual_count = sum(track.kind == "visual" for track in tracks)
    paint: dict[str, int] = {}
    other_index = 0
    for track in tracks:
        if track.kind == "visual":
            paint[track.track_id] = track.paint_index
        else:
            paint[track.track_id] = visual_count + other_index
            other_index += 1
    return tracks, lanes, paint


def _clips_in_scope(
    model: TimelineInspectionModel,
    scope: Scope,
    start_frame: int,
    end_frame: int,
) -> tuple[ClipModel, ...]:
    wanted = set(scope.clip_ids)
    result: list[ClipModel] = []
    for clip in model.clips:
        if clip.clip_id not in wanted:
            continue
        if end_frame > start_frame and not (
            clip.frames.start_frame < end_frame and clip.frames.end_frame > start_frame
        ):
            continue
        result.append(clip)
    return tuple(result)


def _frame_windows(start_frame: int, end_frame: int, fps: int) -> tuple[tuple[int, int], ...]:
    if end_frame <= start_frame:
        return ((start_frame, end_frame),)
    span = max(1, MAX_TIME_SPAN_SECONDS * fps)
    windows: list[tuple[int, int]] = []
    cursor = start_frame
    while cursor < end_frame:
        next_cursor = min(end_frame, cursor + span)
        windows.append((cursor, next_cursor))
        cursor = next_cursor
    return tuple(windows)


def _lane_bands(track_count: int) -> tuple[tuple[int, ...], ...]:
    if track_count == 0:
        return ((),)
    return tuple(
        tuple(range(first, min(track_count, first + MAX_LANES_PER_PAGE)))
        for first in range(0, track_count, MAX_LANES_PER_PAGE)
    )


def _chunks(values: Sequence[str], size: int) -> tuple[tuple[str, ...], ...]:
    if not values:
        return ((),)
    return tuple(tuple(values[index : index + size]) for index in range(0, len(values), size))


def _time_specs(
    clips: tuple[ClipModel, ...],
    tracks: tuple[TrackModel, ...],
    lanes: Mapping[str, int],
    windows: tuple[tuple[int, int], ...],
    max_objects_per_page: int,
) -> tuple[_PageSpec, ...]:
    bands = _lane_bands(len(tracks))
    band_for_lane = {
        lane: band_index
        for band_index, band in enumerate(bands)
        for lane in band
    }
    owners: dict[tuple[int, int], list[str]] = {}
    scope_start = windows[0][0]
    scope_end = windows[-1][1]
    nominal_span = max(1, MAX_TIME_SPAN_SECONDS * clips[0].frames.fps) if clips else None
    for clip in clips:
        lane = lanes[clip.track_id]
        band_index = band_for_lane[lane]
        if scope_end <= scope_start:
            window_index = 0
        else:
            anchor = min(max(clip.frames.start_frame, scope_start), scope_end - 1)
            assert nominal_span is not None
            window_index = min(len(windows) - 1, (anchor - scope_start) // nominal_span)
        owners.setdefault((window_index, band_index), []).append(clip.clip_id)

    specs: list[_PageSpec] = []
    for window_index, (window_start, window_end) in enumerate(windows):
        for band_index, band in enumerate(bands):
            owned = owners.get((window_index, band_index), [])
            for chunk_index, chunk in enumerate(_chunks(owned, max_objects_per_page)):
                specs.append(
                    _PageSpec(
                        window_index=window_index,
                        band_index=band_index,
                        chunk_index=chunk_index,
                        start_frame=window_start,
                        end_frame=window_end,
                        lane_indices=band,
                        clip_ids=chunk,
                    )
                )
    return tuple(specs)


def _clip_z(
    clip: ClipModel,
    clip_index: Mapping[str, int],
    paint_rank: Mapping[str, int],
) -> int:
    return _Z_CLIP_BASE + paint_rank[clip.track_id] * _Z_STRIDE + clip_index[clip.clip_id]


def _seconds(value: float) -> str:
    return f"{value:.4f}"


def _linear_clip_label(ref: str, clip: ClipModel, fps: int) -> str:
    duration = clip.frames.duration_frames
    return (
        f"{ref} · start={clip.frames.start_frame}fr/"
        f"{_seconds(clip.frames.start_frame / fps)}s · "
        f"end={clip.frames.end_frame}fr/{_seconds(clip.frames.end_frame / fps)}s · "
        f"duration={duration}fr/{_seconds(duration / fps)}s · "
        f"authored={_seconds(clip.authored.start)}s→{_seconds(clip.authored.end)}s"
    )


def _time_clip_label(ref: str, clip: ClipModel) -> str:
    return (
        f"{ref} · frames=[{clip.frames.start_frame},{clip.frames.end_frame}) · "
        f"duration={clip.frames.duration_frames}fr"
    )


def _interval_box(
    start_frame: int,
    end_frame: int,
    window_start: int,
    window_end: int,
    y: float,
    height: float,
) -> Box:
    duration = max(1, window_end - window_start)
    pixels_per_frame = _PLOT_W / duration
    clipped_start = max(start_frame, window_start)
    clipped_end = min(end_frame, window_end)
    x = _PLOT_X + (clipped_start - window_start) * pixels_per_frame
    exact_width = max(0.0, (clipped_end - clipped_start) * pixels_per_frame)
    available = max(0.5, _PLOT_X + _PLOT_W - x)
    width = min(max(_MIN_CLIP_W, exact_width), available)
    return Box(x, y, width, height)


def _frame_x(frame: int, window_start: int, window_end: int) -> float:
    duration = max(1, window_end - window_start)
    return _PLOT_X + (frame - window_start) * (_PLOT_W / duration)


def _nice_tick_step(window_frames: int, fps: int) -> int:
    if window_frames <= 0:
        return 1
    minimum = window_frames * 60.0 / _PLOT_W
    window_seconds = window_frames / max(1, fps)
    # 320px labels cannot fit on a 5s / ~89px pitch at a 90s overview.
    # Root-scale windows use 10s majors only.
    candidates = (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1200, 3600)
    if window_seconds >= 60:
        candidates = (10, 15, 30, 60, 120, 300, 600, 1200, 3600)
    for seconds in candidates:
        step = seconds * fps
        if step >= minimum:
            return step
    return max(1, int(math.ceil(minimum)))


def _tick_frames(start_frame: int, end_frame: int, fps: int) -> tuple[int, ...]:
    if end_frame <= start_frame:
        return (start_frame,)
    step = _nice_tick_step(end_frame - start_frame, fps)
    first = ((start_frame + step - 1) // step) * step
    ticks = [start_frame]
    cursor = first
    while cursor < end_frame:
        if cursor != start_frame:
            ticks.append(cursor)
        cursor += step
    if end_frame != ticks[-1]:
        ticks.append(end_frame)
    return tuple(ticks)


def _chrome(
    model: TimelineInspectionModel,
    timeline_ref: str,
    scope_ref: str,
    *,
    layout: str,
    page_index: int,
    page_count: int,
    start_frame: int,
    end_frame: int,
    snapshot_version: int | None = None,
    cue_text: str | None = None,
) -> list[LayoutObject]:
    breadcrumb = timeline_ref if scope_ref == timeline_ref else f"{timeline_ref} > {scope_ref}"
    mode = (
        "TIME-SCALED"
        if layout == "time-scaled"
        else "LINEAR — WIDTHS ARE NOT TIME-SCALED"
    )
    version_token = f" · v{snapshot_version}" if snapshot_version is not None else ""
    objects = [
        LayoutObject(
            timeline_ref,
            "breadcrumb",
            Box(40.0, 28.0, 760.0, 42.0),
            None,
            _Z_CHROME,
            breadcrumb,
            None,
        ),
        LayoutObject(
            timeline_ref,
            "snapshot_badge",
            Box(1110.0, 28.0, 770.0, 42.0),
            None,
            _Z_CHROME,
            f"SNAPSHOT · {timeline_ref}{version_token} · {model.snapshot_sns}",
            None,
        ),
        LayoutObject(
            scope_ref,
            "scope_badge",
            Box(40.0, 86.0, 1840.0, 46.0),
            None,
            _Z_CHROME,
            (
                f"{mode} · page {page_index}/{page_count} · "
                f"window=[{start_frame},{end_frame})fr · "
                f"{_seconds(start_frame / model.fps)}s→{_seconds(end_frame / model.fps)}s"
            ),
            None,
        ),
    ]
    if cue_text:
        # The cue is split into two lines so timing facts are never buried:
        # line 1 = navigation (FOCUS · PARENT · SOURCE · NEXT), line 2 = facts
        # (FOCUS CLIP window · SP @ window). Grok UX: a single long cue line
        # made the SP token unreadable at the tail.
        nav_part = cue_text
        facts_part = ""
        split_at = len(cue_text)
        for token in (" · FOCUS CLIP ", " · SP @ "):
            idx = cue_text.find(token)
            if idx != -1:
                split_at = min(split_at, idx)
        if split_at < len(cue_text):
            nav_part = cue_text[:split_at]
            facts_part = cue_text[split_at:]
        objects.append(
            LayoutObject(
                scope_ref,
                "cue",
                Box(40.0, 134.0, 1840.0, 54.0),
                None,
                _Z_CHROME,
                nav_part,
                None,
            )
        )
        if facts_part:
            objects.append(
                LayoutObject(
                    scope_ref,
                    "cue",
                    Box(40.0, 192.0, 1840.0, 48.0),
                    None,
                    _Z_CHROME,
                    facts_part,
                    None,
                )
            )
    return objects


def _scope_cue(
    model: TimelineInspectionModel,
    identity_map: IdentityMap,
    scope: Scope,
    scope_ref: str,
    timeline_ref: str,
    segments: Sequence[TranscriptSegment] = (),
    occurrences: Sequence[SpeechOccurrence] = (),
) -> str:
    """Return the deterministic FOCUS · SOURCE · TEXT cue line for a page.

    This is the visual grammar the reading guide documents under "Cues in
    images": one chrome line per page telling a reader which qualified id to
    focus next, which asset is the source card (with its role and integrity
    state), which text-evidence id is in scope, and the mapped speaker.

    Rules (single source of truth; mirrored by the reading guide):

    * FOCUS — the id to look up next: the first in-scope clip for
      timeline/range/shot/timestamp scopes, the focused clip's first source
      asset for clip scopes, the parent clip for asset scopes, the first
      speech occurrence for TS scopes, and the mapped clip for SP scopes.
    * SOURCE — the single source card of the focused object (asset ref, role,
      integrity state), or ``none`` when the scope has no single card.
    * TEXT — the first transcript-segment ref mapped into the focused clip
      (or the scope's own TS/SP ref), or ``none``.
    * SPEAKER — the mapped segment's speaker (name, else its speaker state),
      or ``none``.
    """

    def _clip_ref_of(clip_id: str) -> str | None:
        return identity_map.lookup_semantic("clip", clip_id)

    def _asset_ref_of(asset_key: str) -> str | None:
        return identity_map.lookup_semantic("asset", asset_key)

    def _clip_asset(clip_id: str) -> str | None:
        clip = next((item for item in model.clips if item.clip_id == clip_id), None)
        if clip is None:
            return None
        for asset_key in clip.asset_keys:
            ref = _asset_ref_of(asset_key)
            if ref is not None:
                return ref
        return None

    def _asset_identity(asset_ref: str | None) -> tuple[str, str] | None:
        if asset_ref is None:
            return None
        semantic = identity_map.lookup_display(asset_ref)
        if semantic is None:
            return None
        integrity = model.media_integrity.get(semantic[2])
        if integrity is None:
            return None
        return integrity.role, integrity.state

    def _speaker_of(segment_id: str) -> str:
        segment = next((item for item in segments if item.segment_id == segment_id), None)
        if segment is None:
            return "none"
        if segment.speaker is not None:
            return segment.speaker
        return segment.speaker_state or "none"

    def _ts_ref_for(segment_id: str) -> str | None:
        suffix = f":segment:{segment_id}"
        for (_uuid, kind, authored), ref in identity_map.semantic_to_display.items():
            if kind == "transcript_source_segment" and authored.endswith(suffix):
                return ref
        return None

    def _sp_ref_for(segment_id: str, clip_id: str) -> str | None:
        tail = f":segment:{segment_id}:clip:{clip_id}"
        for (_uuid, kind, authored), ref in identity_map.semantic_to_display.items():
            if kind == "speech_occurrence" and authored.endswith(tail):
                return ref
        return None

    focus: str | None = None
    source: str | None = None
    text: str | None = None
    speaker: str = "none"
    next_target: str | None = None

    if scope.kind in {"timeline", "project"}:
        focus = _clip_ref_of(scope.clip_ids[0]) if scope.clip_ids else timeline_ref
    elif scope.kind in {"range", "shot"}:
        focus = _clip_ref_of(scope.clip_ids[0]) if scope.clip_ids else timeline_ref
        source = None
    elif scope.kind == "timestamp":
        focused = scope.emphasized_clip_ids[0] if scope.emphasized_clip_ids else (
            scope.clip_ids[0] if scope.clip_ids else None
        )
        focus = _clip_ref_of(focused) if focused else timeline_ref
        if focused:
            source = _clip_asset(focused)
            for occurrence in occurrences:
                if occurrence.clip_id == focused:
                    text = _ts_ref_for(occurrence.segment_id)
                    speaker = _speaker_of(occurrence.segment_id)
                    break
    elif scope.kind == "clip":
        focused = scope.emphasized_clip_ids[0] if scope.emphasized_clip_ids else (
            scope.clip_ids[0] if scope.clip_ids else None
        )
        if focused is None:
            focus = timeline_ref
        else:
            # FOCUS names the subject (the focused clip); NEXT names the
            # action target (its source asset). Grok UX: "the header names
            # the asset, not the requested clip" — the subject comes first.
            focus = _clip_ref_of(focused) or timeline_ref
            next_target = _clip_asset(focused)
            source = _clip_asset(focused)
            for occurrence in occurrences:
                if occurrence.clip_id == focused:
                    text = _ts_ref_for(occurrence.segment_id)
                    speaker = _speaker_of(occurrence.segment_id)
                    break
    elif scope.kind == "asset":
        source = scope_ref
        parent_clip = next(
            (
                _clip_ref_of(clip.clip_id)
                for clip in model.clips
                if scope_ref in {
                    _asset_ref_of(asset_key) for asset_key in clip.asset_keys
                }
            ),
            None,
        )
        focus = parent_clip or timeline_ref
    elif scope.kind == "ts" or (scope.kind == "text"):
        text = scope_ref
        for occurrence in occurrences:
            ts_ref = _ts_ref_for(occurrence.segment_id)
            if ts_ref != scope_ref:
                continue
            sp_ref = _sp_ref_for(occurrence.segment_id, occurrence.clip_id)
            focus = sp_ref or scope_ref
            source = _clip_asset(occurrence.clip_id)
            speaker = _speaker_of(occurrence.segment_id)
            break
    elif scope.kind == "sp" or (scope.kind == "speech"):
        text = scope_ref
        for occurrence in occurrences:
            sp_ref = _sp_ref_for(occurrence.segment_id, occurrence.clip_id)
            if sp_ref != scope_ref:
                continue
            focus = _clip_ref_of(occurrence.clip_id) or timeline_ref
            source = _clip_asset(occurrence.clip_id)
            speaker = _speaker_of(occurrence.segment_id)
            break

    role_state = _asset_identity(source)
    if source is None or role_state is None:
        source_token = "SOURCE none · role none · state none"
    else:
        source_token = f"SOURCE {source} · {role_state[0]} · {role_state[1]}"

    # PARENT: the breadcrumb parent of the focused object — the timeline for
    # timeline/range/shot/timestamp/clip scopes, the parent clip for asset
    # scopes, the source segment for SP scopes. Printed explicitly so a VLM
    # never confuses it with the focused id.
    if scope.kind == "asset":
        parent_token = f"PARENT {focus or 'none'}"
    elif scope.kind in {"sp", "speech"} and text:
        parent_token = f"PARENT {text}"
    else:
        parent_token = f"PARENT {timeline_ref}"

    # SP window: exact timeline bounds of the in-scope speech occurrence
    # (3-decimal seconds), printed so timing questions are answered by the
    # page, never estimated.
    sp_token = ""
    for occurrence in occurrences:
        in_focus = False
        if scope.kind in {"ts", "text", "sp", "speech"}:
            in_focus = True
        elif scope.kind == "clip":
            in_focus = occurrence.clip_id in scope.emphasized_clip_ids
        elif scope.kind == "timestamp":
            in_focus = occurrence.clip_id in scope.clip_ids
        if in_focus:
            sp_token = (
                f" · SP @ {occurrence.timeline_start:.3f}s–{occurrence.timeline_end:.3f}s"
            )
            break

    # Focused-clip window: for clip/timestamp/range scopes whose focused clip
    # rectangle may be too narrow to carry its own frame label on a
    # full-timeline page, print the exact window here so the page always
    # answers "what are this clip's bounds" without estimating from the ruler.
    clip_window_token = ""
    focused_clip_id: str | None = None
    if scope.kind == "clip":
        focused_clip_id = (
            scope.emphasized_clip_ids[0]
            if scope.emphasized_clip_ids
            else (scope.clip_ids[0] if scope.clip_ids else None)
        )
    elif scope.kind == "timestamp":
        focused_clip_id = (
            scope.emphasized_clip_ids[0]
            if scope.emphasized_clip_ids
            else (scope.clip_ids[0] if scope.clip_ids else None)
        )
    elif scope.kind in {"range", "shot"}:
        focused_clip_id = scope.clip_ids[0] if scope.clip_ids else None
    if focused_clip_id is not None:
        focused_clip = next(
            (item for item in model.clips if item.clip_id == focused_clip_id), None
        )
        if focused_clip is not None:
            clip_window_token = (
                f" · FOCUS CLIP {focused_clip.frames.start_frame}–"
                f"{focused_clip.frames.end_frame}fr · "
                f"{_seconds(focused_clip.frames.start_frame / model.fps)}s→"
                f"{_seconds(focused_clip.frames.end_frame / model.fps)}s"
            )

    return (
        f"FOCUS {focus or 'none'} · {parent_token} · {source_token} · "
        f"TEXT {text or 'none'} · SPEAKER {speaker}"
        f"{(' · NEXT ' + next_target) if next_target else ''}"
        f"{clip_window_token}{sp_token}"
    )


def _ruler(
    timeline_ref: str,
    start_frame: int,
    end_frame: int,
    fps: int,
) -> list[LayoutObject]:
    objects: list[LayoutObject] = []
    for frame in _tick_frames(start_frame, end_frame, fps):
        x = min(
            _PLOT_X + _PLOT_W - 1.0,
            max(_PLOT_X, _frame_x(frame, start_frame, end_frame)),
        )
        objects.extend(
            _ruler_marker(
                timeline_ref,
                x=x,
                tick_height=58.0,
                label=f"{frame}fr · {_seconds(frame / fps)}s",
            )
        )
    return objects


def _ruler_marker(
    timeline_ref: str,
    *,
    x: float,
    tick_height: float,
    label: str,
) -> tuple[LayoutObject, LayoutObject]:
    """Return one axis tick and its independently positioned text label."""

    tick_box = Box(x, _RULER_Y, 1.0, tick_height)
    label_box = Box(
        tick_box.x,
        tick_box.y + tick_box.h,
        _RULER_LABEL_W,
        _RULER_LABEL_H,
    )
    return (
        LayoutObject(
            timeline_ref,
            "ruler_tick",
            tick_box,
            None,
            _Z_TICK,
            None,
            None,
        ),
        LayoutObject(
            timeline_ref,
            "label",
            label_box,
            None,
            _Z_TICK,
            label,
            None,
        ),
    )


def _visual_detail_label(
    model: TimelineInspectionModel,
    timeline_ref: str,
    start_frame: int,
    end_frame: int,
) -> LayoutObject:
    visual_tracks = {track.track_id for track in model.tracks if track.kind == "visual"}
    authored_end = max(
        (clip.authored.end for clip in model.clips if clip.track_id in visual_tracks),
        default=0.0,
    )
    x = _frame_x(model.extents.visual_frames, start_frame, end_frame)
    x = min(_PLOT_X + _PLOT_W - 420.0, max(_PLOT_X, x))
    return LayoutObject(
        timeline_ref,
        "label",
        Box(x, 190.0, 420.0, 30.0),
        None,
        _Z_ANNOTATION,
        (
            f"visual detail ends at {model.extents.visual_frames}fr "
            f"(frame-quantized {_seconds(model.extents.visual_frames / model.fps)}s) · "
            f"authored end={_seconds(authored_end)}s"
        ),
        None,
    )


def _track_lane_h(track: TrackModel, *, focused: bool) -> float:
    if track.kind == "visual":
        return _VISUAL_LANE_H_FOCUS if focused else _VISUAL_LANE_H_ROOT
    return _AUDIO_LANE_H


def _lane_metrics(
    tracks: tuple[TrackModel, ...],
    lane_indices: tuple[int, ...],
    *,
    focused: bool,
) -> tuple[dict[int, float], dict[int, float]]:
    ys: dict[int, float] = {}
    hs: dict[int, float] = {}
    y = _LANES_Y
    for lane in lane_indices:
        height = _track_lane_h(tracks[lane], focused=focused)
        ys[lane] = y
        hs[lane] = height
        y += height + _LANE_GAP
    return ys, hs


def _clip_thumbnail(model: TimelineInspectionModel, clip: ClipModel) -> str | None:
    for asset_key in clip.asset_keys:
        integrity = model.media_integrity.get(asset_key)
        if integrity is not None and integrity.state == "verified_original":
            return integrity.path
    return None


def _visual_cluster_clips(
    model: TimelineInspectionModel,
    clips: tuple[ClipModel, ...],
) -> tuple[ClipModel, ...]:
    visual_ids = {track.track_id for track in model.tracks if track.kind == "visual"}
    cluster_end = model.extents.visual_frames
    return tuple(
        clip
        for clip in clips
        if clip.track_id in visual_ids and clip.frames.start_frame < cluster_end
    )


def _cluster_inset_cards(
    model: TimelineInspectionModel,
    identity_map: IdentityMap,
    *,
    spec: _PageSpec,
    tracks: tuple[TrackModel, ...],
    lanes: Mapping[str, int],
    lane_y: Mapping[int, float],
    lane_h: Mapping[int, float],
    focused: bool,
    emphasized: set[str],
) -> list[LayoutObject]:
    """Readable 320×180 contain-fit cards for the 0–visual_frames cluster.

    Time-scaled overview boxes in that cluster are ~52×76 and cannot show a
    16:9 frame.  The inset lives inside the first visual lane.
    """

    cluster = _visual_cluster_clips(model, model.clips)
    if not cluster:
        return []
    window_overlaps = (
        spec.start_frame < model.extents.visual_frames and spec.end_frame > 0
    )
    if not window_overlaps and not focused:
        return []
    visual_lane = next(
        (lane for lane in spec.lane_indices if tracks[lane].kind == "visual"),
        None,
    )
    if visual_lane is None:
        return []
    card_y = lane_y[visual_lane] + _INSET_Y_OFFSET
    max_bottom = lane_y[visual_lane] + lane_h[visual_lane] - _CLIP_PAD
    if card_y + _MIN_VISUAL_CARD_H > max_bottom:
        card_y = max(lane_y[visual_lane] + _CLIP_PAD, max_bottom - _MIN_VISUAL_CARD_H)
    objects: list[LayoutObject] = []
    for index, clip in enumerate(cluster):
        if clip.track_id not in lanes or lanes[clip.track_id] not in spec.lane_indices:
            continue
        ref = _clip_ref(identity_map, clip)
        box = Box(
            _PLOT_X + index * (_MIN_VISUAL_CARD_W + _INSET_GAP),
            card_y,
            _MIN_VISUAL_CARD_W,
            _MIN_VISUAL_CARD_H,
        )
        if box.x + box.w > _PLOT_X + _PLOT_W:
            break
        objects.append(
            LayoutObject(
                ref,
                "inset_card",
                box,
                lanes[clip.track_id],
                _Z_ANNOTATION + 50 + index,
                ref.rsplit(".", 1)[-1],
                None,
                _clip_thumbnail(model, clip),
            )
        )
        if clip.clip_id in emphasized:
            objects.append(
                LayoutObject(
                    ref,
                    "focus_ring",
                    Box(
                        box.x - _FOCUS_RING_PX,
                        box.y - _FOCUS_RING_PX,
                        box.w + 2.0 * _FOCUS_RING_PX,
                        box.h + 2.0 * _FOCUS_RING_PX,
                    ),
                    lanes[clip.track_id],
                    _Z_ANNOTATION + 201 + index,
                    None,
                    None,
                )
            )
    return objects


def _lane_object(
    timeline_ref: str,
    track: TrackModel,
    lane_index: int,
    y: float,
    height: float,
) -> LayoutObject:
    label = track.label or track.track_id
    return LayoutObject(
        timeline_ref,
        "track_lane",
        Box(40.0, y, 1840.0, height),
        lane_index,
        _Z_LANE + lane_index,
        f"lane {lane_index} · {label} · {track.kind}",
        None,
    )


def _same_track_deltas(clips: tuple[ClipModel, ...]) -> tuple[tuple[ClipModel, int], ...]:
    by_track: dict[str, list[ClipModel]] = {}
    model_index = {clip.clip_id: index for index, clip in enumerate(clips)}
    for clip in clips:
        by_track.setdefault(clip.track_id, []).append(clip)
    result: list[tuple[ClipModel, int]] = []
    for track_clips in by_track.values():
        chronological = sorted(
            track_clips,
            key=lambda clip: (
                clip.frames.start_frame,
                clip.frames.end_frame,
                model_index[clip.clip_id],
            ),
        )
        for previous, following in zip(chronological, chronological[1:]):
            delta = following.frames.start_frame - previous.frames.end_frame
            if delta != 0:
                result.append((following, delta))
    return tuple(result)


def _continuation_sort_key(
    ref: str,
    identity_map: IdentityMap,
    timeline_ref: str,
) -> tuple[int, str]:
    if ref == timeline_ref:
        return (0, ref)
    semantic = identity_map.lookup_display(ref)
    if semantic is None:
        return (9, ref)
    order = {"shot": 1, "range": 2, "clip": 3, "asset": 4}.get(semantic[1], 8)
    return (order, ref)


def _continuation_occurrences(
    continuation_sets: Sequence[set[str]],
) -> dict[int, dict[str, tuple[str, ...]]]:
    pages_by_ref: dict[str, list[int]] = {}
    for page_index, refs in enumerate(continuation_sets):
        for ref in refs:
            pages_by_ref.setdefault(ref, []).append(page_index)
    result: dict[int, dict[str, list[str]]] = {}
    for ref, page_indices in pages_by_ref.items():
        for position, page_index in enumerate(page_indices):
            directions: list[str] = []
            if position > 0:
                directions.append("previous")
            if position + 1 < len(page_indices):
                directions.append("next")
            result.setdefault(page_index, {})[ref] = directions
    return {
        page_index: {ref: tuple(directions) for ref, directions in refs.items()}
        for page_index, refs in result.items()
    }


def _add_footer_continuations(
    objects: list[LayoutObject],
    represented: set[str],
    directions: Mapping[str, tuple[str, ...]],
    ordered_refs: Sequence[str],
) -> None:
    marker_index = 0
    for ref in ordered_refs:
        if ref in represented:
            continue
        for direction in directions.get(ref, ()):
            x = 40.0 if direction == "previous" else 1500.0
            y = 1010.0 - marker_index * 34.0
            objects.append(
                LayoutObject(
                    ref,
                    "continuation",
                    Box(x, y, 380.0, 30.0),
                    None,
                    _Z_CHROME,
                    (
                        f"CONTINUE NEXT · {ref}"
                        if direction == "next"
                        else f"CONTINUE PREV · {ref}"
                    ),
                    None,
                )
            )
            marker_index += 1


def _layout_time_scaled(
    model: TimelineInspectionModel,
    identity_map: IdentityMap,
    scope: Scope,
    scope_ref: str,
    max_objects_per_page: int,
    *,
    snapshot_version: int | None = None,
    cue_text: str | None = None,
    focused: bool = False,
) -> tuple[LayoutPage, ...]:
    start_frame, end_frame = _scope_bounds(model, scope)
    tracks, lanes, paint_rank = _lane_maps(model)
    clips = _clips_in_scope(model, scope, start_frame, end_frame)
    # Focused visual-cluster zooms must draw the rest of the 0–visual_frames
    # group (e.g. in-window CL04 next to CL02), not only neighbor-scoped ids.
    if focused and scope.kind in {"clip", "range", "shot", "timestamp"}:
        cluster = _visual_cluster_clips(model, model.clips)
        focused_ids = set(scope.emphasized_clip_ids) or set(scope.clip_ids)
        if any(clip.clip_id in focused_ids for clip in cluster):
            have = {clip.clip_id for clip in clips}
            extras = tuple(clip for clip in cluster if clip.clip_id not in have)
            if extras:
                clips = tuple((*clips, *extras))
            if cluster:
                end_frame = max(end_frame, model.extents.visual_frames)
    clip_by_id = {clip.clip_id: clip for clip in clips}
    clip_index = {clip.clip_id: index for index, clip in enumerate(model.clips)}
    windows = _frame_windows(start_frame, end_frame, model.fps)
    specs = _time_specs(clips, tracks, lanes, windows, max_objects_per_page)
    owner_page: dict[str, int] = {
        clip_id: page_index
        for page_index, spec in enumerate(specs)
        for clip_id in spec.clip_ids
    }

    # Select one representative page for every clip/window intersection.  The
    # owner carries kind=clip; subsequent windows carry kind=continuation.
    visible_pages: dict[str, list[int]] = {clip.clip_id: [] for clip in clips}
    for clip in clips:
        lane = lanes[clip.track_id]
        for window_index, (window_start, window_end) in enumerate(windows):
            if not (
                clip.frames.start_frame < window_end
                and clip.frames.end_frame > window_start
            ):
                continue
            candidates = [
                index
                for index, spec in enumerate(specs)
                if spec.window_index == window_index and lane in spec.lane_indices
            ]
            if not candidates:
                continue
            owner = owner_page[clip.clip_id]
            selected = owner if owner in candidates else candidates[0]
            visible_pages[clip.clip_id].append(selected)

    continuation_sets = [set() for _spec in specs]
    for clip in clips:
        pages = visible_pages[clip.clip_id]
        if len(pages) > 1:
            ref = _clip_ref(identity_map, clip)
            for page_index in pages:
                continuation_sets[page_index].add(ref)

    # Every explicit page break has a reciprocal marker, including density or
    # lane-band breaks that do not split a clip interval.
    timeline_ref = _timeline_ref(model, identity_map)
    for page_index in range(len(specs) - 1):
        if continuation_sets[page_index] & continuation_sets[page_index + 1]:
            continue
        next_ids = specs[page_index + 1].clip_ids
        boundary_ref = (
            _clip_ref(identity_map, clip_by_id[next_ids[0]])
            if next_ids
            else timeline_ref
        )
        continuation_sets[page_index].add(boundary_ref)
        continuation_sets[page_index + 1].add(boundary_ref)

    directions_by_page = _continuation_occurrences(continuation_sets)
    detail_page = next(
        (
            index
            for index, spec in enumerate(specs)
            if spec.start_frame <= model.extents.visual_frames <= spec.end_frame
        ),
        None,
    )
    delta_owner = {
        following.clip_id: owner_page[following.clip_id]
        for following, _delta in _same_track_deltas(clips)
        if following.clip_id in owner_page
    }
    deltas = {following.clip_id: delta for following, delta in _same_track_deltas(clips)}

    pages: list[LayoutPage] = []
    for zero_index, spec in enumerate(specs):
        page_index = zero_index + 1
        objects = _chrome(
            model,
            timeline_ref,
            scope_ref,
            layout="time-scaled",
            page_index=page_index,
            page_count=len(specs),
            start_frame=spec.start_frame,
            end_frame=spec.end_frame,
            snapshot_version=snapshot_version,
            cue_text=cue_text,
        )
        objects.extend(_ruler(timeline_ref, spec.start_frame, spec.end_frame, model.fps))

        local_by_lane = {lane: index for index, lane in enumerate(spec.lane_indices)}
        lane_y, lane_h = _lane_metrics(tracks, spec.lane_indices, focused=focused)
        for lane in spec.lane_indices:
            objects.append(
                _lane_object(
                    timeline_ref,
                    tracks[lane],
                    lane,
                    lane_y[lane],
                    lane_h[lane],
                )
            )

        primary_ids = set(spec.clip_ids)
        continued = [
            clip
            for clip in clips
            if zero_index in visible_pages[clip.clip_id]
            and clip.clip_id not in primary_ids
        ]
        page_clips = [clip_by_id[clip_id] for clip_id in spec.clip_ids]
        emphasized = set(scope.emphasized_clip_ids)
        for clip in (*page_clips, *continued):
            lane = lanes[clip.track_id]
            track = tracks[lane]
            y = lane_y[lane] + _CLIP_PAD
            height = lane_h[lane] - 2.0 * _CLIP_PAD
            box = _interval_box(
                clip.frames.start_frame,
                clip.frames.end_frame,
                spec.start_frame,
                spec.end_frame,
                y,
                height,
            )
            if track.kind == "visual" and box.w < _MIN_VISUAL_CARD_W:
                # A narrow visual clip collapses to a duration bar ONLY when
                # it has no verified thumbnail (Grok: bare chips read as dead
                # space). With a frame available, keep the full lane height
                # so the renderer contain-fits the whole image into a tall,
                # readable strip — no gutter.
                has_thumb = any(
                    model.media_integrity.get(ak) is not None
                    and model.media_integrity[ak].state == "verified_original"
                    for ak in clip.asset_keys
                )
                if not has_thumb:
                    box = Box(box.x, y, box.w, _DURATION_BAR_H)
            ref = _clip_ref(identity_map, clip)
            if clip.clip_id in primary_ids:
                label = _time_clip_label(ref, clip)
                full_width = max(96.0, len(label) * 10.0)
                if box.w >= full_width:
                    omitted = None
                elif box.w >= 44.0:
                    # Narrow but visible: print the bare ordinal (the timeline
                    # is constant on the page, so CL01 is unambiguous) — the
                    # qualified ref + frame window live in ground-truth and
                    # the reading guide. Grok UX feedback: unlabeled cells
                    # are the #1 readability failure; collisions are #2.
                    label = ref.rsplit(".", 1)[-1]
                    omitted = None
                else:
                    omitted = "time-scaled box is too narrow for its complete frame label"
                kind = "clip"
            else:
                label = f"{ref} · continued"
                omitted = None if box.w >= 96.0 else "continuation segment is too narrow"
                kind = "continuation"
            thumbnail_path = _clip_thumbnail(model, clip) if kind == "clip" else None
            objects.append(
                LayoutObject(
                    ref,
                    kind,
                    box,
                    lane,
                    _clip_z(clip, clip_index, paint_rank),
                    label,
                    omitted,
                    thumbnail_path,
                )
            )
            if kind == "clip" and (
                clip.clip_id in emphasized
                or (not emphasized and spec.clip_ids and clip.clip_id == spec.clip_ids[0])
            ):
                objects.append(
                    LayoutObject(
                        ref,
                        "focus_ring",
                        Box(
                            box.x - _FOCUS_RING_PX,
                            box.y - _FOCUS_RING_PX,
                            box.w + 2.0 * _FOCUS_RING_PX,
                            box.h + 2.0 * _FOCUS_RING_PX,
                        ),
                        lane,
                        _Z_ANNOTATION + 200,
                        None,
                        None,
                    )
                )

        objects.extend(
            _cluster_inset_cards(
                model,
                identity_map,
                spec=spec,
                tracks=tracks,
                lanes=lanes,
                lane_y=lane_y,
                lane_h=lane_h,
                focused=focused,
                emphasized=emphasized,
            )
        )

        # Preserve raw one-frame gaps and overlaps as annotations; the clip
        # rectangles themselves remain independently frame-mapped and unsnapped.
        for following_id, owner in delta_owner.items():
            if owner != zero_index:
                continue
            following = clip_by_id[following_id]
            delta = deltas[following_id]
            boundary_start = (
                following.frames.start_frame - delta if delta > 0 else following.frames.start_frame
            )
            boundary_end = (
                following.frames.start_frame if delta > 0 else following.frames.start_frame - delta
            )
            if not (boundary_start < spec.end_frame and boundary_end > spec.start_frame):
                continue
            lane = lanes[following.track_id]
            marker_y = lane_y[lane] + lane_h[lane] - 20.0
            marker_box = _interval_box(
                boundary_start,
                boundary_end,
                spec.start_frame,
                spec.end_frame,
                marker_y,
                14.0,
            )
            ref = _clip_ref(identity_map, following)
            relation = "gap" if delta > 0 else "overlap"
            # Name both boundary clips so the marker is self-describing
            # (Grok UX feedback: "1fr gap/overlap" alone doesn't say which
            # join). Preceding = the same-track clip ending at the boundary.
            preceding_ref = None
            preceding_start = (
                following.frames.start_frame - delta
                if delta > 0
                else following.frames.start_frame + abs(delta)
            )
            for candidate in clip_by_id.values():
                if (
                    candidate.track_id == following.track_id
                    and candidate.frames.end_frame == preceding_start
                ):
                    preceding_ref = _clip_ref(identity_map, candidate)
                    break
            if preceding_ref:
                marker_label = (
                    f"{abs(delta)}fr {relation} {preceding_ref}→{ref}"
                )
            else:
                marker_label = f"{abs(delta)}fr {relation}"
            objects.append(
                LayoutObject(
                    ref,
                    "gap_marker",
                    marker_box,
                    lane,
                    _Z_ANNOTATION,
                    marker_label,
                    None,
                )
            )

        if detail_page is not None and zero_index == detail_page:
            objects.append(
                _visual_detail_label(
                    model,
                    timeline_ref,
                    spec.start_frame,
                    spec.end_frame,
                )
            )

        ordered_continuations = tuple(
            sorted(
                continuation_sets[zero_index],
                key=lambda ref: _continuation_sort_key(ref, identity_map, timeline_ref),
            )
        )
        represented = {
            item.display_id for item in objects if item.kind == "continuation"
        }
        _add_footer_continuations(
            objects,
            represented,
            directions_by_page.get(zero_index, {}),
            ordered_continuations,
        )
        page_objects = tuple(objects)
        pages.append(
            LayoutPage(
                page_index=page_index,
                page_id=f"PG{page_index:03d}",
                layout="time-scaled",
                scope_ref=scope_ref,
                scope_bounds_frames=(spec.start_frame, spec.end_frame),
                width=PAGE_W,
                height=PAGE_H,
                objects=page_objects,
                reading_order=tuple(item.display_id for item in page_objects),
                continuation=ordered_continuations,
            )
        )
    return tuple(pages)


def _linear_lane_object(
    timeline_ref: str,
    track: TrackModel,
    lane: int,
    y: float,
    height: float,
) -> LayoutObject:
    return LayoutObject(
        timeline_ref,
        "track_lane",
        Box(40.0, y, 175.0, max(32.0, height)),
        lane,
        _Z_LANE + lane,
        f"lane {lane} · {track.label or track.track_id} · {track.kind}",
        None,
    )


def _layout_linear(
    model: TimelineInspectionModel,
    identity_map: IdentityMap,
    scope: Scope,
    scope_ref: str,
    max_objects_per_page: int,
    *,
    snapshot_version: int | None = None,
    cue_text: str | None = None,
) -> tuple[LayoutPage, ...]:
    start_frame, end_frame = _scope_bounds(model, scope)
    tracks, lanes, paint_rank = _lane_maps(model)
    clips = _clips_in_scope(model, scope, start_frame, end_frame)
    clip_index = {clip.clip_id: index for index, clip in enumerate(model.clips)}
    capacity = min(max_objects_per_page, MAX_LINEAR_CARDS_PER_PAGE)
    chunks = tuple(
        tuple(clips[index : index + capacity])
        for index in range(0, len(clips), capacity)
    ) or ((),)
    timeline_ref = _timeline_ref(model, identity_map)

    continuation_sets = [set() for _chunk in chunks]
    for page_index in range(len(chunks) - 1):
        following = chunks[page_index + 1]
        ref = _clip_ref(identity_map, following[0]) if following else timeline_ref
        continuation_sets[page_index].add(ref)
        continuation_sets[page_index + 1].add(ref)
    directions_by_page = _continuation_occurrences(continuation_sets)

    all_deltas = {following.clip_id: delta for following, delta in _same_track_deltas(clips)}
    pages: list[LayoutPage] = []
    for zero_index, chunk in enumerate(chunks):
        page_index = zero_index + 1
        objects = _chrome(
            model,
            timeline_ref,
            scope_ref,
            layout="linear",
            page_index=page_index,
            page_count=len(chunks),
            start_frame=start_frame,
            end_frame=end_frame,
            snapshot_version=snapshot_version,
            cue_text=cue_text,
        )
        # These are explicit scope references, not a proportional ruler.
        objects.extend(
            _ruler_marker(
                timeline_ref,
                x=_PLOT_X,
                tick_height=46.0,
                label=(
                    f"scope start={start_frame}fr/"
                    f"{_seconds(start_frame / model.fps)}s"
                ),
            )
        )
        objects.extend(
            _ruler_marker(
                timeline_ref,
                x=_PLOT_X + _PLOT_W - 1.0,
                tick_height=46.0,
                label=(
                    f"scope end={end_frame}fr/"
                    f"{_seconds(end_frame / model.fps)}s"
                ),
            )
        )

        lane_positions: dict[int, list[int]] = {}
        for position, clip in enumerate(chunk):
            lane_positions.setdefault(lanes[clip.track_id], []).append(position)
        for lane in sorted(lane_positions):
            positions = lane_positions[lane]
            first_row = min(positions) // _LINEAR_COLUMNS
            last_row = max(positions) // _LINEAR_COLUMNS
            y = _LANES_Y + first_row * (_LINEAR_CARD_H + _LINEAR_CARD_GAP_Y)
            height = (
                (last_row - first_row + 1) * _LINEAR_CARD_H
                + (last_row - first_row) * _LINEAR_CARD_GAP_Y
            )
            objects.append(_linear_lane_object(timeline_ref, tracks[lane], lane, y, height))

        for position, clip in enumerate(chunk):
            row, column = divmod(position, _LINEAR_COLUMNS)
            box = Box(
                _PLOT_X + column * (_LINEAR_CARD_W + _LINEAR_CARD_GAP_X),
                _LANES_Y + row * (_LINEAR_CARD_H + _LINEAR_CARD_GAP_Y),
                _LINEAR_CARD_W,
                _LINEAR_CARD_H,
            )
            ref = _clip_ref(identity_map, clip)
            lane = lanes[clip.track_id]
            objects.append(
                LayoutObject(
                    ref,
                    "clip",
                    box,
                    lane,
                    _clip_z(clip, clip_index, paint_rank),
                    _linear_clip_label(ref, clip, model.fps),
                    None,
                )
            )
            delta = all_deltas.get(clip.clip_id)
            if delta is not None:
                relation = "gap" if delta > 0 else "overlap"
                objects.append(
                    LayoutObject(
                        ref,
                        "gap_marker",
                        Box(box.x, max(_LANES_Y, box.y - 24.0), 150.0, 22.0),
                        lane,
                        _Z_ANNOTATION,
                        f"{abs(delta)}fr {relation}",
                        None,
                    )
                )

        if (
            zero_index == 0
            and start_frame <= model.extents.visual_frames <= end_frame
        ):
            objects.append(
                _visual_detail_label(model, timeline_ref, start_frame, max(start_frame + 1, end_frame))
            )
        ordered_continuations = tuple(
            sorted(
                continuation_sets[zero_index],
                key=lambda ref: _continuation_sort_key(ref, identity_map, timeline_ref),
            )
        )
        _add_footer_continuations(
            objects,
            set(),
            directions_by_page.get(zero_index, {}),
            ordered_continuations,
        )
        page_objects = tuple(objects)
        pages.append(
            LayoutPage(
                page_index=page_index,
                page_id=f"PG{page_index:03d}",
                layout="linear",
                scope_ref=scope_ref,
                scope_bounds_frames=(start_frame, end_frame),
                width=PAGE_W,
                height=PAGE_H,
                objects=page_objects,
                reading_order=tuple(item.display_id for item in page_objects),
                continuation=ordered_continuations,
            )
        )
    return tuple(pages)


def _excerpt(value: str, limit: int = 72) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _with_text_lanes(
    pages: tuple[LayoutPage, ...],
    model: TimelineInspectionModel,
    identity_map: IdentityMap,
    segments: Sequence[TranscriptSegment],
    occurrences: Sequence[SpeechOccurrence],
) -> tuple[LayoutPage, ...]:
    """Overlay three provenance-distinct compact evidence lanes on each page."""

    segment_by_id = {item.segment_id: item for item in segments}
    clip_by_id = {item.clip_id: item for item in model.clips}
    base_lane = len(model.tracks)
    result: list[LayoutPage] = []
    for page in pages:
        start_frame, end_frame = page.scope_bounds_frames
        span = max(1, end_frame - start_frame)
        objects = list(page.objects)
        for offset, label in enumerate(("SPEECH", "CAPTION", "OTHER TEXT · not_inspected")):
            y = _TEXT_LANE_Y + offset * (_TEXT_LANE_H + _TEXT_LANE_GAP)
            objects.append(
                LayoutObject(
                    _timeline_ref(model, identity_map),
                    "text_lane",
                    Box(40.0, y, 175.0, _TEXT_LANE_H),
                    base_lane + offset,
                    _Z_LANE + base_lane + offset,
                    label,
                    None,
                )
            )

        def evidence_box(start: float, end: float, lane_offset: int) -> Box | None:
            first = max(start_frame, int(math.floor(start * model.fps + 0.5)))
            last = min(end_frame, int(math.floor(end * model.fps + 0.5)))
            if last <= first:
                return None
            x = _PLOT_X + ((first - start_frame) / span) * _PLOT_W
            width = max(_MIN_CLIP_W, ((last - first) / span) * _PLOT_W)
            return Box(
                x,
                _TEXT_LANE_Y + lane_offset * (_TEXT_LANE_H + _TEXT_LANE_GAP) + 6.0,
                min(width, _PLOT_X + _PLOT_W - x),
                _TEXT_LANE_H - 12.0,
            )

        for occurrence in occurrences:
            start = occurrence.effective_start
            end = occurrence.effective_end
            if start is None or end is None:
                start, end = occurrence.timeline_start, occurrence.timeline_end
            box = evidence_box(start, end, 0)
            segment = segment_by_id.get(occurrence.segment_id)
            if box is None or segment is None:
                continue
            objects.append(
                LayoutObject(
                    occurrence.occurrence_id,
                    "speech",
                    box,
                    base_lane,
                    _Z_CLIP_BASE + 10,
                    f"{occurrence.occurrence_id} · SPEECH · {_excerpt(segment.text)}",
                    None if box.w >= 72 else "speech box is too narrow for excerpt",
                )
            )
        visual_tracks = {track.track_id for track in model.tracks if track.kind == "visual"}
        for clip in model.clips:
            clip_ref = _clip_ref(identity_map, clip)
            if clip.authored_text is not None:
                box = evidence_box(
                    clip.frames.start_frame / model.fps,
                    clip.frames.end_frame / model.fps,
                    1,
                )
                if box is not None:
                    objects.append(
                        LayoutObject(
                            clip_ref,
                            "caption",
                            box,
                            base_lane + 1,
                            _Z_CLIP_BASE + 20,
                            f"{clip_ref} · CAPTION · {_excerpt(clip.authored_text)}",
                            None if box.w >= 72 else "caption box is too narrow for excerpt",
                        )
                    )
            elif clip.track_id in visual_tracks:
                box = evidence_box(
                    clip.frames.start_frame / model.fps,
                    clip.frames.end_frame / model.fps,
                    2,
                )
                if box is not None:
                    objects.append(
                        LayoutObject(
                            clip_ref,
                            "pixel_text",
                            box,
                            base_lane + 2,
                            _Z_CLIP_BASE + 30,
                            f"{clip_ref} · OTHER TEXT · not_inspected",
                            None if box.w >= 72 else "pixel-text state box is too narrow",
                        )
                    )
        result.append(
            replace(
                page,
                objects=tuple(objects),
                reading_order=tuple(item.display_id for item in objects),
            )
        )
    return tuple(result)


def layout_timeline(
    model: TimelineInspectionModel,
    identity_map: IdentityMap,
    scope: Scope,
    *,
    layout: str,
    max_objects_per_page: int = 24,
    transcript_segments: Sequence[TranscriptSegment] | None = None,
    speech_occurrences: Sequence[SpeechOccurrence] | None = None,
    snapshot_version: int | None = None,
) -> tuple[LayoutPage, ...]:
    """Lay out one cold scope in the requested deterministic reading.

    Time-scaled windows are contiguous 90-second slices of the *scope* frame
    interval.  Lane bands (eight lanes) and primary-object chunks repeat that
    exact window only when vertical/object density requires it.  Linear pages
    contain at most twelve cards and never encode duration in card width.
    """

    if not isinstance(model, TimelineInspectionModel):
        raise TypeError("model must be a TimelineInspectionModel")
    if not isinstance(identity_map, IdentityMap):
        raise TypeError("identity_map must be an IdentityMap")
    if not isinstance(scope, Scope):
        raise TypeError("scope must be a Scope")
    if layout not in {"time-scaled", "linear"}:
        raise ValueError("layout must be 'time-scaled' or 'linear'")
    if (
        isinstance(max_objects_per_page, bool)
        or not isinstance(max_objects_per_page, int)
        or max_objects_per_page <= 0
    ):
        raise ValueError("max_objects_per_page must be a positive integer")

    scope_ref = _resolved_scope_ref(model, identity_map, scope)
    timeline_ref = _timeline_ref(model, identity_map)
    cue_text = _scope_cue(
        model,
        identity_map,
        scope,
        scope_ref,
        timeline_ref,
        segments=transcript_segments or (),
        occurrences=speech_occurrences or (),
    )
    if layout == "time-scaled":
        # Focused scopes (clip/range/shot/timestamp) zoom into a small time
        # window: make the clip lanes TALL so the full source frames render
        # large and the page's vertical space is used, not left dead.
        focused_scope = scope.kind in {"clip", "range", "shot", "timestamp"}
        pages = _layout_time_scaled(
            model,
            identity_map,
            scope,
            scope_ref,
            max_objects_per_page,
            snapshot_version=snapshot_version,
            cue_text=cue_text,
            focused=focused_scope,
        )
    else:
        pages = _layout_linear(
            model,
            identity_map,
            scope,
            scope_ref,
            max_objects_per_page,
            snapshot_version=snapshot_version,
            cue_text=cue_text,
        )
    return _with_text_lanes(
        pages,
        model,
        identity_map,
        transcript_segments or (),
        speech_occurrences or (),
    )


def _snapshot_fps_from_assembly(assembly: Mapping[str, Any]) -> int:
    raw: Any = None
    overrides = assembly.get("theme_overrides")
    if isinstance(overrides, Mapping):
        visual = overrides.get("visual")
        if isinstance(visual, Mapping):
            canvas = visual.get("canvas")
            if isinstance(canvas, Mapping):
                raw = canvas.get("fps")
    if raw is None:
        return 30
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw <= 0:
        raise ValueError("snapshot timeline fps must be positive")
    return int(raw)


def _snapshot_blocks(snapshot: Any, identity_map: IdentityMap) -> list[dict[str, Any]]:
    if isinstance(snapshot, Mapping):
        if isinstance(snapshot.get("snapshots"), list):
            return deepcopy(snapshot["snapshots"])
        if isinstance(snapshot.get("timeline"), Mapping):
            return [deepcopy(dict(snapshot))]
    if isinstance(snapshot, (list, tuple)):
        return deepcopy(list(snapshot))

    timeline_uuid = getattr(snapshot, "timeline_id", None)
    timeline_ulid = getattr(snapshot, "timeline_ulid", None)
    if not isinstance(timeline_uuid, str) or not isinstance(timeline_ulid, str):
        raise TypeError(
            "snapshot must be a TimelineSnapshot, a snapshot block, or a snapshot list"
        )
    timeline_ref = identity_map.lookup_semantic("timeline", timeline_uuid)
    if timeline_ref is None:
        raise ValueError("snapshot timeline has no display id in identity_map")
    slug = getattr(snapshot, "slug", None) or timeline_ulid.lower()
    assembly = getattr(snapshot, "assembly", {})
    fps = _snapshot_fps_from_assembly(assembly if isinstance(assembly, Mapping) else {})
    sns_method = getattr(snapshot, "sns", None)
    digest = sns_method() if callable(sns_method) else identity_map.root_sns
    return [
        {
            "timeline": {
                "stable_id": timeline_ref,
                "qualified_ref": timeline_ref,
                "uuid": timeline_uuid,
                "ulid": timeline_ulid,
                "slug": slug,
            },
            "digest": digest,
            "event_head": {
                "version": getattr(snapshot, "head_version", 0),
                "last_event_id": getattr(snapshot, "last_event_id", None),
                "last_hash": getattr(snapshot, "last_hash", None),
            },
            "fps": fps,
        }
    ]


def _scope_kind(scope_ref: str) -> str:
    if "@" in scope_ref:
        return "timestamp"
    suffix = scope_ref.rsplit(".", 1)[-1]
    if suffix.startswith("SH"):
        return "shot"
    if suffix.startswith("RG"):
        return "range"
    if suffix.startswith("CL"):
        return "clip"
    if suffix.startswith("AS"):
        return "asset"
    if suffix.startswith("TS"):
        return "text"
    if suffix.startswith("SP"):
        return "speech"
    if suffix.startswith("TL"):
        return "timeline"
    raise ValueError(f"cannot infer schema scope kind from {scope_ref!r}")


def _bbox(box: Box) -> dict[str, float]:
    values = (box.x, box.y, box.w, box.h)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("layout boxes must contain finite coordinates")
    if box.x < 0 or box.y < 0 or box.w <= 0 or box.h <= 0:
        raise ValueError("view-map boxes require non-negative x/y and positive width/height")
    return {"x": box.x, "y": box.y, "width": box.w, "height": box.h}


def _semantic_layout_objects(
    page: LayoutPage,
    identity_map: IdentityMap,
) -> list[LayoutObject]:
    expected_semantic_kind = {
        "clip": "clip",
        "asset_card": "asset",
        "speech": "speech_occurrence",
    }
    result: list[LayoutObject] = []
    seen: set[str] = set()
    for item in page.objects:
        expected = expected_semantic_kind.get(item.kind)
        if expected is None:
            continue
        semantic = identity_map.lookup_display(item.display_id)
        if semantic is None or semantic[1] != expected:
            raise ValueError(
                f"{item.kind} LayoutObject {item.display_id!r} has no matching semantic identity"
            )
        if item.display_id in seen:
            raise ValueError(
                f"page {page.page_id} contains duplicate semantic object {item.display_id}"
            )
        seen.add(item.display_id)
        result.append(item)
    return result


def serialize_view_map(
    pages: tuple[LayoutPage, ...],
    *,
    identity_map: IdentityMap,
    scope_ref: str,
    snapshot: Any,
) -> dict[str, Any]:
    """Serialize pages exactly to the authoritative v1 ``view-map`` schema.

    The public ``LayoutPage`` keeps renderer chrome and may repeat a semantic
    ref for labels/continuations.  The schema's ``object_boxes`` and per-page
    ``reading_order`` contain only primary identity-bearing objects, in the
    order those objects occur in ``LayoutPage.objects``.  Standalone ``label``
    objects are appended to the page's ``labels`` array with their own boxes
    but remain outside schema reading order.  Omitted labels retain their
    intended text and carry a non-empty reason with ``bbox: null``.
    """

    if not isinstance(pages, tuple):
        raise TypeError("pages must be a tuple of LayoutPage values")
    if not isinstance(identity_map, IdentityMap):
        raise TypeError("identity_map must be an IdentityMap")
    if not isinstance(scope_ref, str) or not scope_ref:
        raise ValueError("scope_ref must be a non-empty qualified reference")
    blocks = _snapshot_blocks(snapshot, identity_map)
    if not blocks:
        raise ValueError("view-map requires at least one snapshot")
    fps_raw = blocks[0].get("fps")
    if isinstance(fps_raw, bool) or not isinstance(fps_raw, (int, float)) or fps_raw <= 0:
        raise ValueError("serialized snapshot fps must be positive")
    fps = float(fps_raw)
    kind = _scope_kind(scope_ref)

    serialized_pages: list[dict[str, Any]] = []
    continuation_pages: dict[str, list[int]] = {}
    for page_position, page in enumerate(pages):
        if not isinstance(page, LayoutPage):
            raise TypeError("pages must contain only LayoutPage values")
        semantic_objects = _semantic_layout_objects(page, identity_map)
        object_boxes = []
        labels = []
        for item in semantic_objects:
            stable_id = item.display_id.rsplit(".", 1)[-1]
            bbox = _bbox(item.box)
            object_boxes.append(
                {
                    "stable_id": stable_id,
                    "object_ref": item.display_id,
                    "bbox": bbox,
                    "lane": (
                        f"lane-{item.lane_index:02d}"
                        if item.lane_index is not None
                        else "semantic-cards"
                    ),
                    "z_order": item.z_order,
                }
            )
            text = item.label if item.label is not None else item.display_id
            if item.omitted_reason is None:
                labels.append(
                    {
                        "object_ref": item.display_id,
                        "text": text,
                        "status": "printed",
                        "reason": None,
                        "bbox": bbox,
                    }
                )
            else:
                labels.append(
                    {
                        "object_ref": item.display_id,
                        "text": text,
                        "status": "omitted",
                        "reason": item.omitted_reason,
                        "bbox": None,
                    }
                )

        for item in page.objects:
            if item.kind not in {"label", "cue"}:
                continue
            if item.label is None:
                raise ValueError("label LayoutObjects must carry label text")
            # Timestamp locators (TL01@00:10.000) and continuation refs are
            # legitimate chrome without a semantic identity; record them with
            # their text (outside object_boxes/reading_order) instead of
            # raising.
            labels.append(
                {
                    "object_ref": item.display_id,
                    "text": item.label,
                    "status": (
                        "printed" if item.omitted_reason is None else "omitted"
                    ),
                    "reason": item.omitted_reason,
                    "bbox": (
                        _bbox(item.box) if item.omitted_reason is None else None
                    ),
                }
            )

        start_frame, end_frame = page.scope_bounds_frames
        page_scope_ref = scope_ref or page.scope_ref
        serialized_pages.append(
            {
                "page_id": page.page_id,
                "dimensions": {"width_px": page.width, "height_px": page.height},
                "layout": page.layout,
                "scope": {
                    "kind": kind,
                    "ref": page_scope_ref,
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "start_seconds": start_frame / fps,
                    "end_seconds": end_frame / fps,
                },
                "time_bounds": {
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "start_seconds": start_frame / fps,
                    "end_seconds": end_frame / fps,
                },
                "object_boxes": object_boxes,
                "labels": labels,
                "continuation_links": [],
                "reading_order": [item.display_id for item in semantic_objects],
            }
        )
        for ref in dict.fromkeys(page.continuation):
            if identity_map.lookup_display(ref) is None:
                # Locally minted RG scope refs are valid scope anchors but are
                # never used as continuation targets without a frozen id-map
                # entry.  Page traversal falls back to TL in layout_timeline.
                continue
            continuation_pages.setdefault(ref, []).append(page_position)

    for ref in sorted(continuation_pages):
        positions = continuation_pages[ref]
        for previous, following in zip(positions, positions[1:]):
            serialized_pages[previous]["continuation_links"].append(
                {
                    "object_ref": ref,
                    "target_page_id": pages[following].page_id,
                    "direction": "next",
                }
            )
            serialized_pages[following]["continuation_links"].append(
                {
                    "object_ref": ref,
                    "target_page_id": pages[previous].page_id,
                    "direction": "previous",
                }
            )
    for page in serialized_pages:
        page["continuation_links"].sort(
            key=lambda link: (
                0 if link["direction"] == "previous" else 1,
                link["target_page_id"],
                link["object_ref"],
            )
        )

    return {
        "schema_version": 1,
        "snapshots": blocks,
        "pages": serialized_pages,
        "reading_order": [page.page_id for page in pages],
    }


__all__ = [
    "PAGE_H",
    "PAGE_W",
    "Box",
    "LayoutObject",
    "LayoutPage",
    "layout_timeline",
    "serialize_view_map",
]
