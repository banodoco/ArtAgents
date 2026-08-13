#!/usr/bin/env python3
"""Three.js/Remotion hybrid planner and rendering-protocol v1 command adapter.

``rendering.threejs-hybrid`` is an opt-in planner that performs temporal
concatenation only (never spatial compositing): occupied regions whose every
participating clip satisfies the direct Three.js text contract are routed to
``rendering.threejs``; everything else (media, effects, transitions, audible
audio, overlaps, gaps) is routed to ``rendering.remotion``.  The plan pins
``rendering.ffmpeg-finalizer`` so segment output is normalized to the
canonical profile.

The planner owns only deterministic window construction and renderer support
selection.  It never renders a segment or finalizes media; ``RenderService``
does both after independently resolving and rechecking every pinned
capability.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    _CHECKOUT_ROOT = Path(__file__).resolve().parents[5]
    if str(_CHECKOUT_ROOT) not in sys.path:
        sys.path.insert(0, str(_CHECKOUT_ROOT))

from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.hash import sha256_file
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    FrameWindow,
    PlannerResolution,
    RenderPlan,
    RenderRequest,
    RenderSegment,
    SupportReport,
    compute_request_digest,
)
from astrid.core.rendering.errors import (
    RendererException,
    make_renderer_error,
    raise_unsupported_error,
)
from astrid.core.rendering.profile import resolve_render_profile
from astrid.core.rendering.registry import (
    FinalizerRegistry,
    RendererRegistry,
    RenderingRegistryError,
    load_default_registries,
)

# Reuse the characterized legacy planner primitives (pure helpers only) and the
# Three.js backend's exact text-contract eligibility predicate (also pure).
from astrid.packs.rendering.backends.threejs.run import (
    _support_reasons as _three_support_reasons,
)
from astrid.packs.rendering.planners.legacy_hybrid.run import (
    _ceil,
    _clip_timeline_end,
    _CommandSupportResolver,
    _finalizer_resolution,
    _load_inputs,
    _number,
    _renderer_resolution,
    _timeline_duration,
    _window_timeline,
)

BACKEND_ID = "rendering.threejs-hybrid"
BACKEND_VERSION = "1.0.0"
THREE_ID = "rendering.threejs"
REMOTION_ID = "rendering.remotion"
FINALIZER_ID = "rendering.ffmpeg-finalizer"
_HANDLE_SECONDS = Fraction(1, 4)
_ZERO_DIGEST = "0" * 64
_PLANNER_CONFIG_KEYS = frozenset(
    {"theme", "theme_path", "themes_root", "extra_pack_roots"}
)

SupportResolver = Callable[[str, RenderRequest, Mapping[str, Any]], SupportReport]


# ---------------------------------------------------------------------------
# Pure profile / timescale helpers
# ---------------------------------------------------------------------------


def _mp4_time_base(fps: Fraction) -> tuple[int, int]:
    """Canonical MP4 video-track timescale for the resolved FPS.

    Integer rates are repeatedly doubled until the timescale is at least
    10,000 (24 -> 12,288; 30 -> 15,360).  NTSC-style rationals already carry
    a large numerator (30000/1001 -> 30,000) and are retained unchanged.
    This mirrors the canonical profile's MP4 time base exactly.
    """

    timescale = fps.numerator
    while timescale < 10_000:
        timescale *= 2
    return 1, timescale


# ---------------------------------------------------------------------------
# Pure occupancy / classification helpers
# ---------------------------------------------------------------------------


def _clip_frame_range(
    clip: Mapping[str, Any], fps: Fraction
) -> tuple[int, int]:
    """Half-open frame range for one clip using round(seconds * fps).

    A positive-duration clip always occupies at least one frame, so a
    sub-frame clip still owns the frame it starts on.
    """

    start_seconds = _number(clip.get("at", 0), "clip.at")
    end_seconds = _clip_timeline_end(clip)
    start_frame = round(start_seconds * fps)
    end_frame = round(end_seconds * fps)
    if end_seconds > start_seconds and end_frame <= start_frame:
        end_frame = start_frame + 1
    return start_frame, end_frame


def _merged_components(
    ranges: Sequence[tuple[int, int, int]],
) -> list[tuple[int, int, list[int]]]:
    """Merge STRICTLY overlapping occupied intervals into components.

    Intervals are half-open ``[start, end)``; touching intervals (``end ==
    next start``) do not overlap and stay separate.  Every component carries
    the indexes of its participating clips.
    """

    components: list[tuple[int, int, list[int]]] = []
    for start, end, index in sorted(ranges):
        if not components or start >= components[-1][1]:
            components.append((start, end, [index]))
        else:
            previous_start, previous_end, previous_indexes = components[-1]
            components[-1] = (
                previous_start,
                max(previous_end, end),
                [*previous_indexes, index],
            )
    return components


def _component_timeline(
    timeline: Mapping[str, Any],
    clips: Sequence[Mapping[str, Any]],
    indexes: Sequence[int],
) -> dict[str, Any]:
    """Project the timeline onto one component's participating clips.

    Only the tracks actually used by the component's clips are retained, so a
    timeline-level audio track that the component never touches does not
    poison an otherwise Three-eligible text component.
    """

    selected = [clips[index] for index in indexes]
    used_tracks = {clip.get("track") for clip in selected}
    component = dict(timeline)
    component["clips"] = selected
    component["tracks"] = [
        track
        for track in timeline.get("tracks", [])
        if isinstance(track, Mapping) and track.get("id") in used_tracks
    ]
    return component


def _component_eligible(
    timeline: Mapping[str, Any],
    clips: Sequence[Mapping[str, Any]],
    indexes: Sequence[int],
) -> bool:
    """A component is Three-eligible iff every participant satisfies the
    exact Three.js text contract (shared with the backend, never duplicated).

    Any ineligible participant sends the WHOLE connected component to
    Remotion — an overlap is never split in v1.
    """

    return not _three_support_reasons(
        _component_timeline(timeline, clips, indexes)
    )


def _handle_frame_range(
    component_start: int,
    component_end: int,
    *,
    fps: Fraction,
    total_frames: int,
    previous_occupied_end: int,
    next_occupied_start: int,
) -> tuple[int, int]:
    """Quarter-second Remotion handle, capped at adjacent occupied regions
    and the timeline boundary.

    The backward expansion never eats into the previous occupied component
    and the forward expansion never eats into the next occupied component, so
    exact half-open tiling is preserved by construction.
    """

    start = max(
        previous_occupied_end,
        _floor((Fraction(component_start, 1) / fps - _HANDLE_SECONDS) * fps),
    )
    end = min(
        next_occupied_start,
        _ceil((Fraction(component_end, 1) / fps + _HANDLE_SECONDS) * fps),
    )
    return max(0, start), min(total_frames, end)


def _floor(value: Fraction) -> int:
    return value.numerator // value.denominator


def _window_plan(
    timeline: Mapping[str, Any], fps: Fraction
) -> tuple[int, list[tuple[int, int, str]]]:
    """Tile the timeline into exact half-open (start, end, renderer) windows.

    Occupied regions are merged into connected components; Three-eligible
    components keep their exact occupancy window while Remotion components
    receive the capped quarter-second handle; gaps and the tail are Remotion;
    adjacent same-renderer windows are coalesced.
    """

    total_frames = _ceil(_timeline_duration(timeline) * fps)
    if total_frames == 0:
        return 0, []
    raw_clips = timeline.get("clips", [])
    if not isinstance(raw_clips, list):
        raise TypeError("timeline clips must be an array")
    clips = [clip for clip in raw_clips if isinstance(clip, Mapping)]
    ranges: list[tuple[int, int, int]] = []
    for index, clip in enumerate(clips):
        start, end = _clip_frame_range(clip, fps)
        start = max(0, min(start, total_frames))
        end = max(0, min(end, total_frames))
        if end > start:
            ranges.append((start, end, index))
    classified: list[tuple[int, int, str]] = []
    for start, end, indexes in _merged_components(ranges):
        renderer = (
            THREE_ID
            if _component_eligible(timeline, clips, indexes)
            else REMOTION_ID
        )
        classified.append((start, end, renderer))
    windows: list[tuple[int, int, str]] = []
    for position, (start, end, renderer) in enumerate(classified):
        if renderer == THREE_ID:
            windows.append((start, end, THREE_ID))
            continue
        previous_occupied_end = (
            classified[position - 1][1] if position > 0 else 0
        )
        next_occupied_start = (
            classified[position + 1][0]
            if position + 1 < len(classified)
            else total_frames
        )
        handle_start, handle_end = _handle_frame_range(
            start,
            end,
            fps=fps,
            total_frames=total_frames,
            previous_occupied_end=previous_occupied_end,
            next_occupied_start=next_occupied_start,
        )
        if handle_end > handle_start:
            windows.append((handle_start, handle_end, REMOTION_ID))
    segments: list[tuple[int, int, str]] = []
    cursor = 0
    for start, end, renderer in windows:
        start = max(cursor, start)
        if start > cursor:
            segments.append((cursor, start, REMOTION_ID))
        if end > start:
            segments.append((start, end, renderer))
        cursor = max(cursor, end)
    if cursor < total_frames:
        segments.append((cursor, total_frames, REMOTION_ID))
    return total_frames, _coalesce(segments)


def _coalesce(
    segments: Sequence[tuple[int, int, str]],
) -> list[tuple[int, int, str]]:
    """Merge adjacent windows with the same renderer (coverage unchanged)."""

    merged: list[tuple[int, int, str]] = []
    for start, end, renderer in segments:
        if merged and merged[-1][2] == renderer and merged[-1][1] == start:
            merged[-1] = (merged[-1][0], end, renderer)
        else:
            merged.append((start, end, renderer))
    return merged


def _assert_exact_tiling(
    segments: Sequence[tuple[int, int, str]],
    *,
    total_frames: int,
    window_start: int,
    window_end: int,
) -> None:
    """Assert exact half-open tiling: no gaps, overlaps, zero-length
    segments, or recursive planner ids."""

    planner_ids = frozenset({BACKEND_ID, "rendering.legacy_hybrid"})
    if not segments:
        raise AssertionError("exact tiling requires at least one segment")
    if segments[0][0] != window_start:
        raise AssertionError("tiling does not start at the window boundary")
    if segments[-1][1] != window_end:
        raise AssertionError("tiling does not end at the window boundary")
    for left, right in zip(segments, segments[1:]):
        if left[1] != right[0]:
            raise AssertionError("tiling has a gap or overlap")
    for start, end, renderer in segments:
        if end <= start:
            raise AssertionError("tiling contains a zero-length segment")
        if renderer in planner_ids or renderer not in {THREE_ID, REMOTION_ID}:
            raise AssertionError(
                f"tiling references a recursive or unknown renderer id: {renderer}"
            )
    if window_end > total_frames:
        raise AssertionError("tiling extends beyond the timeline")
    if any(
        start < window_start or end > window_end
        for start, end, _renderer in segments
    ):
        raise AssertionError("tiling escapes the requested window")


# ---------------------------------------------------------------------------
# Request / config plumbing
# ---------------------------------------------------------------------------


def _planner_config(request: RenderRequest) -> dict[str, Any]:
    config = dict(request.backend_config.get(BACKEND_ID, {}))
    unknown = sorted(set(config) - _PLANNER_CONFIG_KEYS)
    if unknown:
        raise ValueError(f"unknown {BACKEND_ID} configuration: {', '.join(unknown)}")
    return config


def _structural_reasons(timeline: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    tracks = timeline.get("tracks", [])
    clips = timeline.get("clips", [])
    if not isinstance(tracks, list) or not isinstance(clips, list):
        return ["timeline tracks and clips must be arrays"]
    for index, clip in enumerate(clips):
        if not isinstance(clip, Mapping):
            reasons.append(f"timeline clips must contain objects (clip[{index}])")
    return list(dict.fromkeys(reasons))


def support(request: RenderRequest, *, workspace: Path) -> SupportReport:
    reasons: list[str] = []
    try:
        _timeline_path, timeline, _assets_path, assets = _load_inputs(request, workspace)
        config = _planner_config(request)
        theme = config.get("theme_path", config.get("theme"))
        themes_root = config.get("themes_root", REPO_ROOT / "themes")
        profile = resolve_render_profile(
            timeline,
            assets,
            theme=theme,
            themes_root=themes_root,
            audio_ownership=request.audio,
        )
        fps = Fraction(*profile.fps_rational)
        reasons.extend(_structural_reasons(timeline))
        total_frames = _ceil(_timeline_duration(timeline) * fps)
        if total_frames == 0:
            reasons.append(
                "empty timeline: the hybrid planner cannot construct a "
                "meaningful tiling; use rendering.threejs directly for "
                "empty/background-only smoke"
            )
        else:
            _window_plan(timeline, fps)
        if request.window is not None:
            if request.window.fps_rational != profile.fps_rational:
                reasons.append(
                    "request window FPS does not match the canonical render profile"
                )
            elif request.window.end_frame > total_frames:
                reasons.append("request window extends beyond the timeline")
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        reasons.append(str(exc) or type(exc).__name__)
    reasons = list(dict.fromkeys(reasons))
    return SupportReport(
        schema_version=SCHEMA_VERSION,
        supported=not reasons,
        reasons=reasons,
        features={
            "integer_frame_windows": True,
            "conservative_occupancy_tiling": True,
            "explicit_finalizer": True,
            "non_recursive_dispatch": True,
        },
        alternatives=[],
        backend=BACKEND_ID,
        backend_version=BACKEND_VERSION,
    )


def _planner_resolution(report: SupportReport) -> PlannerResolution:
    manifest = Path(__file__).with_name("planner.yaml")
    return PlannerResolution(
        id=BACKEND_ID,
        source_pack={"id": "rendering", "source_kind": "source"},
        manifest_digest=sha256_file(manifest) if manifest.is_file() else _ZERO_DIGEST,
        trust_eligibility={"eligible": True, "method": "source-tree"},
        alias_chain=[],
        override=None,
        support_decision=report,
    )


def plan(
    request: RenderRequest,
    *,
    workspace: Path,
    support_resolver: SupportResolver | None = None,
    registries: tuple[RendererRegistry, FinalizerRegistry] | None = None,
) -> RenderPlan:
    report = support(request, workspace=workspace)
    if not report.supported:
        raise_unsupported_error(
            backend=BACKEND_ID,
            message="threejs-hybrid planner does not support this request",
            recovery_command="resolve the reported timeline constraints and retry",
            details={"reasons": report.reasons},
        )
    timeline_path, timeline, assets_path, assets = _load_inputs(request, workspace)
    config = _planner_config(request)
    theme = config.get("theme_path", config.get("theme"))
    profile = resolve_render_profile(
        timeline,
        assets,
        theme=theme,
        themes_root=config.get("themes_root", REPO_ROOT / "themes"),
        audio_ownership=request.audio,
    )
    fps = Fraction(*profile.fps_rational)
    if _mp4_time_base(fps) != profile.time_base:
        raise ValueError(
            f"resolved profile time base {profile.time_base} does not match the "
            f"canonical MP4 timescale {_mp4_time_base(fps)}"
        )
    total_frames, raw_segments = _window_plan(timeline, fps)

    renderer_registry: RendererRegistry | None
    finalizer_registry: FinalizerRegistry | None
    if registries is None and support_resolver is None:
        raw_extra_roots = config.get("extra_pack_roots", ())
        if isinstance(raw_extra_roots, (str, bytes)) or not isinstance(
            raw_extra_roots, Sequence
        ):
            raise TypeError("extra_pack_roots must be an array of paths")
        extra_roots = tuple(str(item) for item in raw_extra_roots)
        renderer_registry, _planners, finalizer_registry = load_default_registries(
            REPO_ROOT,
            extra_pack_roots=extra_roots,
        )
    elif registries is None:
        renderer_registry = None
        finalizer_registry = None
    else:
        renderer_registry, finalizer_registry = registries
    if support_resolver is None:
        if renderer_registry is None:
            raise RuntimeError(
                "renderer registry is required for command support resolution"
            )
        support_resolver = _CommandSupportResolver(
            renderer_registry,
            workspace=workspace,
        )

    window_start = 0
    window_end = total_frames
    if request.window is not None:
        window_start = request.window.start_frame
        window_end = request.window.end_frame
        raw_segments = [
            (max(start, window_start), min(end, window_end), renderer_id)
            for start, end, renderer_id in raw_segments
            if min(end, window_end) > max(start, window_start)
        ]
    _assert_exact_tiling(
        raw_segments,
        total_frames=total_frames,
        window_start=window_start,
        window_end=window_end,
    )

    segments: list[RenderSegment] = []
    reasons: dict[str, str] = {}
    for index, (start, end, renderer_id) in enumerate(raw_segments):
        window = FrameWindow(
            start_frame=start,
            end_frame=end,
            fps_rational=profile.fps_rational,
        )
        segment_timeline = _window_timeline(timeline, window)
        segment_request = replace(
            request,
            timeline_path=str(timeline_path),
            assets_registry_path=None if assets_path is None else str(assets_path),
            output_name=f"segment-{index:04d}.mp4",
            window=window,
        )
        try:
            candidate_report = support_resolver(
                renderer_id,
                segment_request,
                segment_timeline,
            )
        except RendererException as exc:
            raise_unsupported_error(
                backend=BACKEND_ID,
                message=f"no renderer supports planned window [{start},{end})",
                recovery_command=(
                    "install or configure a renderer supporting the reported window"
                ),
                details={
                    "window": [start, end],
                    "attempts": [f"{renderer_id}: {exc}"],
                },
            )
        # The support resolver resolved the requested id through the registry;
        # match on the resolved canonical id, never the raw spelling.
        resolved_id = renderer_id
        if renderer_registry is not None:
            try:
                resolved_id = renderer_registry.get(renderer_id).id
            except RenderingRegistryError:
                resolved_id = renderer_id
        if candidate_report.backend != resolved_id:
            raise_unsupported_error(
                backend=BACKEND_ID,
                message=f"no renderer supports planned window [{start},{end})",
                recovery_command=(
                    "install or configure a renderer supporting the reported window"
                ),
                details={
                    "window": [start, end],
                    "attempts": [
                        f"{renderer_id}: support report named {candidate_report.backend}"
                    ],
                },
            )
        if not candidate_report.supported:
            raise_unsupported_error(
                backend=BACKEND_ID,
                message=f"no renderer supports planned window [{start},{end})",
                recovery_command=(
                    "install or configure a renderer supporting the reported window"
                ),
                details={
                    "window": [start, end],
                    "attempts": [
                        f"{renderer_id}: " + "; ".join(candidate_report.reasons)
                    ],
                },
            )
        segments.append(
            RenderSegment(
                window=window,
                renderer=_renderer_resolution(
                    renderer_id,
                    candidate_report,
                    registry=renderer_registry,
                ),
                input_hashes={
                    "timeline": sha256_file(timeline_path),
                    **(
                        {"assets_registry": sha256_file(assets_path)}
                        if assets_path is not None
                        else {}
                    ),
                },
            )
        )
        reasons[str(index)] = (
            f"threejs-hybrid window assigned to {renderer_id} by supported report"
        )

    return RenderPlan(
        schema_version=SCHEMA_VERSION,
        request_digest=compute_request_digest(request.to_dict()),
        requested_policy="threejs_remotion",
        planner=_planner_resolution(report),
        segments=segments,
        finalizer=_finalizer_resolution(finalizer_registry),
        profile=profile,
        total_frames=total_frames,
        reasons=reasons,
        window=request.window,
    )


def _load_request(path: Path) -> RenderRequest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise TypeError("render request must contain a JSON object")
    return RenderRequest.from_dict(payload).for_backend(BACKEND_ID)


def _write_failure(result_path: Path, exc: BaseException, *, kind: str) -> None:
    if isinstance(exc, RendererException):
        error_kind = exc.error.kind
        message = exc.error.message
        recovery = exc.error.recovery_command
        details = exc.error.details
    else:
        error_kind = kind
        message = str(exc) or type(exc).__name__
        recovery = None
        details = {"error_type": type(exc).__name__}
    write_json_atomic(
        result_path,
        make_renderer_error(
            error_kind,
            backend=BACKEND_ID,
            message=message,
            recovery_command=recovery,
            details=details,
        ).to_dict(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("verb", choices=("plan", "support"))
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        request_path = args.request.resolve(strict=True)
        result_path = args.result.resolve()
        if request_path == result_path:
            raise ValueError("--request and --result must be different paths")
        request = _load_request(request_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, RendererException) as exc:
        _write_failure(args.result.resolve(), exc, kind="protocol")
        return 0
    try:
        workspace = request_path.parent
        response: RenderPlan | SupportReport
        if args.verb == "support":
            response = support(request, workspace=workspace)
        else:
            response = plan(request, workspace=workspace)
        write_json_atomic(result_path, response.to_dict())
    except RendererException as exc:
        _write_failure(result_path, exc, kind=exc.error.kind)
    except FileNotFoundError as exc:
        _write_failure(result_path, exc, kind="binary_missing")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        _write_failure(result_path, exc, kind="protocol")
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        _write_failure(result_path, exc, kind="internal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BACKEND_ID",
    "BACKEND_VERSION",
    "FINALIZER_ID",
    "REMOTION_ID",
    "THREE_ID",
    "_assert_exact_tiling",
    "_clip_frame_range",
    "_coalesce",
    "_merged_components",
    "_mp4_time_base",
    "_window_plan",
    "main",
    "plan",
    "support",
]
