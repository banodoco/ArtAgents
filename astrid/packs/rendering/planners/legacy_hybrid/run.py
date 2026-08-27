#!/usr/bin/env python3
"""Legacy hybrid planner and rendering-protocol v1 command adapter.

The planner owns only deterministic window construction and renderer support
selection.  It never renders a segment or finalizes media; ``RenderService``
does both after independently resolving and rechecking every pinned capability.
"""

from __future__ import annotations

import argparse
import json
import math
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
    FinalizerResolution,
    FrameWindow,
    PlannerResolution,
    RendererResolution,
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
    RenderingCandidate,
    load_default_registries,
)
from astrid.core.rendering.transport import CommandTransport

BACKEND_ID = "rendering.legacy_hybrid"
BACKEND_VERSION = "1.0.0"
FINALIZER_ID = "rendering.ffmpeg-finalizer"
FFMPEG_ID = "rendering.ffmpeg"
REMOTION_ID = "rendering.remotion"
_ZERO_DIGEST = "0" * 64
_HANDLE_SECONDS = Fraction(1, 4)
_PLANNER_CONFIG_KEYS = frozenset(
    {
        "simple_renderers",
        "complex_renderers",
        "renderers",
        "theme",
        "theme_path",
        "themes_root",
        "extra_pack_roots",
    }
)

SupportResolver = Callable[[str, RenderRequest, Mapping[str, Any]], SupportReport]


def _number(value: Any, label: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a finite number")
    if not math.isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    return Fraction(str(value))


def _floor(value: Fraction) -> int:
    return value.numerator // value.denominator


def _ceil(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def _clip_duration_seconds(clip: Mapping[str, Any]) -> Fraction:
    source_from = _number(clip.get("from", 0), "clip.from")
    if "to" not in clip:
        raise ValueError("media clip must declare a source to bound")
    source_to = _number(clip["to"], "clip.to")
    speed = _number(clip.get("speed", 1), "clip.speed")
    if source_from < 0 or source_to <= source_from or speed <= 0:
        raise ValueError("media clip must have positive bounds and speed")
    return (source_to - source_from) / speed


def _clip_timeline_end(clip: Mapping[str, Any]) -> Fraction:
    start = _number(clip.get("at", 0), "clip.at")
    if clip.get("clipType", "media") == "media":
        return start + _clip_duration_seconds(clip)
    hold = clip.get("hold")
    if isinstance(hold, (int, float)) and not isinstance(hold, bool):
        return start + max(Fraction(0), _number(hold, "clip.hold"))
    to_value = clip.get("to")
    if isinstance(to_value, (int, float)) and not isinstance(to_value, bool):
        return _number(to_value, "clip.to")
    return start


def _timeline_duration(timeline: Mapping[str, Any]) -> Fraction:
    metadata = timeline.get("metadata")
    explicit: Any = None
    if isinstance(metadata, Mapping):
        explicit = metadata.get("duration_seconds")
        if not isinstance(explicit, (int, float)) or isinstance(explicit, bool):
            explicit = metadata.get("expected_duration_seconds")
    if isinstance(explicit, (int, float)) and not isinstance(explicit, bool):
        duration = _number(explicit, "timeline duration")
        if duration < 0:
            raise ValueError("timeline duration must not be negative")
        return duration
    clips = timeline.get("clips", [])
    if not isinstance(clips, list):
        raise TypeError("timeline clips must be an array")
    ends = [_clip_timeline_end(clip) for clip in clips if isinstance(clip, Mapping)]
    return max(ends, default=Fraction(0))


def _base_visual_track(timeline: Mapping[str, Any], tracks: Mapping[Any, Mapping[str, Any]]) -> Any:
    visual_ids = {track_id for track_id, track in tracks.items() if track.get("kind") == "visual"}
    coverage: dict[Any, Fraction] = {}
    for clip in timeline.get("clips", []):
        if (
            isinstance(clip, Mapping)
            and clip.get("clipType", "media") == "media"
            and clip.get("track") in visual_ids
        ):
            track_id = clip.get("track")
            coverage[track_id] = coverage.get(track_id, Fraction(0)) + _clip_duration_seconds(clip)
    return max(coverage, key=coverage.get) if coverage else None


def _complex_frame_windows(
    timeline: Mapping[str, Any],
    fps: Fraction,
    *,
    handle_seconds: Fraction = _HANDLE_SECONDS,
) -> list[tuple[int, int]]:
    """Port the characterized legacy complexity/transition window rules."""

    duration = _timeline_duration(timeline)
    total_frames = _ceil(duration * fps)
    raw_tracks = timeline.get("tracks", [])
    raw_clips = timeline.get("clips", [])
    if not isinstance(raw_tracks, list) or not isinstance(raw_clips, list):
        raise TypeError("timeline tracks and clips must be arrays")
    tracks = {track.get("id"): track for track in raw_tracks if isinstance(track, Mapping)}
    base_visual_track = _base_visual_track(timeline, tracks)
    windows: list[tuple[int, int]] = []
    clips = [clip for clip in raw_clips if isinstance(clip, Mapping)]

    for index, clip in enumerate(clips):
        media = clip.get("clipType", "media") == "media"
        transition_window = False
        if media:
            track = tracks.get(clip.get("track"), {})
            params = clip.get("params") if isinstance(clip.get("params"), Mapping) else {}
            complex_media = (
                bool(clip.get("effects"))
                or bool(clip.get("transition"))
                or (track.get("kind") == "visual" and clip.get("track") != base_visual_track)
                or (
                    isinstance(clip.get("opacity"), (int, float))
                    and not isinstance(clip.get("opacity"), bool)
                    and float(clip.get("opacity") or 0) != 1.0
                )
                or (
                    track.get("kind") == "audio"
                    and (
                        isinstance(params.get("fadeIn"), (int, float))
                        or isinstance(params.get("fadeOut"), (int, float))
                    )
                )
            )
            if not complex_media:
                continue
            next_same_track = next(
                (
                    candidate
                    for candidate in clips[index + 1 :]
                    if candidate.get("track") == clip.get("track")
                ),
                None,
            )
            if clip.get("transition") and next_same_track is not None:
                transition = clip.get("transition")
                transition_seconds = Fraction(8, 1) / fps
                if isinstance(transition, Mapping):
                    if isinstance(transition.get("duration"), (int, float)):
                        transition_seconds = _number(transition["duration"], "transition.duration")
                    elif isinstance(transition.get("durationFrames"), (int, float)):
                        transition_seconds = (
                            _number(transition["durationFrames"], "transition.durationFrames") / fps
                        )
                clip_end = _clip_timeline_end(clip)
                next_start = _number(next_same_track.get("at", float(clip_end)), "clip.at")
                start = max(
                    Fraction(0),
                    min(clip_end - transition_seconds, next_start) - handle_seconds,
                )
                end = min(
                    duration,
                    max(clip_end, next_start + transition_seconds) + handle_seconds,
                )
                if end > start:
                    windows.append(
                        (max(0, _floor(start * fps)), min(total_frames, _ceil(end * fps)))
                    )
                transition_window = True
        if transition_window:
            continue
        start = max(Fraction(0), _number(clip.get("at", 0), "clip.at") - handle_seconds)
        end = min(duration, _clip_timeline_end(clip) + handle_seconds)
        if end > start:
            windows.append((max(0, _floor(start * fps)), min(total_frames, _ceil(end * fps))))

    windows = [(start, end) for start, end in windows if end > start]
    windows.sort()
    merged: list[tuple[int, int]] = []
    for start, end in windows:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _segment_kinds(
    timeline: Mapping[str, Any], fps: Fraction
) -> tuple[int, list[tuple[int, int, str]]]:
    total_frames = _ceil(_timeline_duration(timeline) * fps)
    if total_frames == 0:
        return 0, []
    complex_windows = _complex_frame_windows(timeline, fps)
    if not complex_windows:
        return total_frames, [(0, total_frames, "simple")]
    segments: list[tuple[int, int, str]] = []
    cursor = 0
    for start, end in complex_windows:
        start = max(0, min(start, total_frames))
        end = max(start, min(end, total_frames))
        if start > cursor:
            segments.append((cursor, start, "simple"))
        if end > start:
            segments.append((start, end, "complex"))
        cursor = max(cursor, end)
    if cursor < total_frames:
        segments.append((cursor, total_frames, "simple"))
    return total_frames, segments


# Compatibility projections retained for the characterized legacy facade.
def _complex_clip_windows(
    timeline_data: Mapping[str, Any],
    fps: int | Fraction,
    *,
    handle_seconds: float = 0.25,
) -> list[tuple[float, float]]:
    rate = fps if isinstance(fps, Fraction) else Fraction(fps, 1)
    return [
        (float(Fraction(start, 1) / rate), float(Fraction(end, 1) / rate))
        for start, end in _complex_frame_windows(
            timeline_data,
            rate,
            handle_seconds=Fraction(str(handle_seconds)),
        )
    ]


def _hybrid_segments(
    timeline_data: Mapping[str, Any], *, fps: Fraction | None = None
) -> list[dict[str, float | str]]:
    if fps is None:
        profile = resolve_render_profile(timeline_data, themes_root=REPO_ROOT / "themes")
        fps = Fraction(*profile.fps_rational)
    _total, kinds = _segment_kinds(timeline_data, fps)
    return [
        {
            "engine": "ffmpeg" if kind == "simple" else "remotion",
            "from": float(Fraction(start, 1) / fps),
            "to": float(Fraction(end, 1) / fps),
        }
        for start, end, kind in kinds
    ]


def _structural_reasons(timeline: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    tracks = timeline.get("tracks", [])
    clips = timeline.get("clips", [])
    if not isinstance(tracks, list) or not isinstance(clips, list):
        return ["timeline tracks and clips must be arrays"]
    track_by_id = {track.get("id"): track for track in tracks if isinstance(track, Mapping)}
    audio_ranges: list[tuple[Fraction, Fraction, Any]] = []
    for clip in clips:
        if not isinstance(clip, Mapping):
            reasons.append("timeline clips must contain objects")
            continue
        if clip.get("clipType", "media") != "media":
            continue
        try:
            speed = _number(clip.get("speed", 1), "clip.speed")
            start = _number(clip.get("at", 0), "clip.at")
            end = _clip_timeline_end(clip)
        except (TypeError, ValueError) as exc:
            reasons.append(str(exc))
            continue
        if speed != 1:
            reasons.append(
                f"Clip {clip.get('id')!r} uses unsupported speed {float(speed):g}; "
                "legacy hybrid planning requires 1.0"
            )
        track = track_by_id.get(clip.get("track"), {})
        if track.get("kind") == "audio":
            audio_ranges.append((start, end, clip.get("id")))
    audio_ranges.sort()
    cursor = Fraction(0)
    for start, end, clip_id in audio_ranges:
        if start < cursor:
            reasons.append(
                f"Overlapping audio at clip {clip_id!r}: starts before previous audio ends"
            )
        cursor = max(cursor, end)
    return list(dict.fromkeys(reasons))


def _load_inputs(
    request: RenderRequest, workspace: Path
) -> tuple[Path, dict[str, Any], Path | None, dict[str, Any]]:
    timeline_path = _input_path(request.timeline_path, workspace)
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    if not isinstance(timeline, dict):
        raise TypeError("timeline must contain a JSON object")
    assets_path = (
        None
        if request.assets_registry_path is None
        else _input_path(request.assets_registry_path, workspace)
    )
    if assets_path is None:
        assets = {"assets": {}}
    else:
        assets = json.loads(assets_path.read_text(encoding="utf-8"))
        if not isinstance(assets, dict) or not isinstance(assets.get("assets"), dict):
            raise TypeError("assets registry must contain an assets object")
    return timeline_path, timeline, assets_path, assets


def _input_path(raw: str, workspace: Path) -> Path:
    path = Path(raw).expanduser()
    return (path if path.is_absolute() else workspace / path).resolve()


def _planner_config(request: RenderRequest) -> dict[str, Any]:
    config = dict(request.backend_config.get(BACKEND_ID, {}))
    unknown = sorted(set(config) - _PLANNER_CONFIG_KEYS)
    if unknown:
        raise ValueError(f"unknown {BACKEND_ID} configuration: {', '.join(unknown)}")
    return config


def _string_list(value: Any, *, label: str, default: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        value = default
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{label} must be an array of qualified renderer ids")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or "." not in item:
            raise ValueError(f"{label} must contain qualified renderer ids")
        if item not in result:
            result.append(item)
    if not result:
        raise ValueError(f"{label} must not be empty")
    return tuple(result)


def _candidate_lists(config: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    common = config.get("renderers")
    if common is not None:
        candidates = _string_list(common, label="renderers", default=())
        return {"simple": candidates, "complex": candidates}
    return {
        "simple": _string_list(
            config.get("simple_renderers"),
            label="simple_renderers",
            default=(FFMPEG_ID, REMOTION_ID),
        ),
        "complex": _string_list(
            config.get("complex_renderers"),
            label="complex_renderers",
            default=(REMOTION_ID,),
        ),
    }


def support(request: RenderRequest, *, workspace: Path) -> SupportReport:
    reasons: list[str] = []
    try:
        _timeline_path, timeline, _assets_path, assets = _load_inputs(request, workspace)
        config = _planner_config(request)
        _candidate_lists(config)
        theme = config.get("theme_path", config.get("theme"))
        themes_root = config.get("themes_root", REPO_ROOT / "themes")
        profile = resolve_render_profile(
            timeline,
            assets,
            theme=theme,
            themes_root=themes_root,
            audio_ownership=request.audio,
        )
        reasons.extend(_structural_reasons(timeline))
        _segment_kinds(timeline, Fraction(*profile.fps_rational))
        if request.window is not None:
            if request.window.fps_rational != profile.fps_rational:
                reasons.append("request window FPS does not match the canonical render profile")
            else:
                total_frames = _ceil(_timeline_duration(timeline) * Fraction(*profile.fps_rational))
                if request.window.end_frame > total_frames:
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
            "transition_handles": True,
            "support_based_assignment": True,
            "explicit_finalizer": True,
            "non_recursive_dispatch": True,
        },
        alternatives=[],
        backend=BACKEND_ID,
        backend_version=BACKEND_VERSION,
    )


def _window_timeline(timeline: Mapping[str, Any], window: FrameWindow) -> dict[str, Any]:
    fps = Fraction(*window.fps_rational)
    start = Fraction(window.start_frame, 1) / fps
    end = Fraction(window.end_frame, 1) / fps
    clips: list[dict[str, Any]] = []
    for raw_clip in timeline.get("clips", []):
        if not isinstance(raw_clip, Mapping):
            continue
        clip_start = _number(raw_clip.get("at", 0), "clip.at")
        clip_end = _clip_timeline_end(raw_clip)
        visible_start = max(start, clip_start)
        visible_end = min(end, clip_end)
        if visible_end <= visible_start:
            continue
        clip = dict(raw_clip)
        clip["id"] = f"{raw_clip.get('id', 'clip')}_{window.start_frame}_{window.end_frame}"
        clip["at"] = float(visible_start - start)
        if raw_clip.get("clipType", "media") == "media":
            speed = _number(raw_clip.get("speed", 1), "clip.speed")
            source_from = _number(raw_clip.get("from", 0), "clip.from")
            source_from += (visible_start - clip_start) * speed
            clip["from"] = float(source_from)
            clip["to"] = float(source_from + (visible_end - visible_start) * speed)
        elif isinstance(raw_clip.get("hold"), (int, float)):
            clip["hold"] = float(visible_end - visible_start)
        clips.append(clip)
    used_tracks = {clip.get("track") for clip in clips}
    result = dict(timeline)
    result["clips"] = clips
    result["tracks"] = [
        dict(track)
        for track in timeline.get("tracks", [])
        if isinstance(track, Mapping) and track.get("id") in used_tracks
    ]
    metadata = timeline.get("metadata")
    result["metadata"] = {
        **(dict(metadata) if isinstance(metadata, Mapping) else {}),
        "source_window_start_seconds": float(start),
        "source_window_end_seconds": float(end),
        "duration_seconds": float(end - start),
    }
    return result


def _source_pack(candidate: RenderingCandidate[Any]) -> dict[str, Any]:
    return {
        "id": candidate.pack_id,
        "source_kind": candidate.source_kind,
        "pack_root": str(candidate.pack_root),
    }


def _renderer_resolution(
    renderer_id: str,
    report: SupportReport,
    *,
    registry: RendererRegistry | None,
) -> RendererResolution:
    if registry is None:
        return RendererResolution(
            id=renderer_id,
            source_pack={"id": renderer_id.split(".", 1)[0]},
            manifest_digest=_ZERO_DIGEST,
            alias_chain=[],
            override=None,
            support_decision=report,
            trust_eligibility={"eligible": True, "method": "injected-support"},
        )
    candidate = registry.get(renderer_id)
    evidence = registry.resolve_evidence(renderer_id)
    return RendererResolution(
        id=candidate.id,
        source_pack=_source_pack(candidate),
        manifest_digest=candidate.manifest_digest,
        alias_chain=list(evidence.get("alias_chain") or []),
        override=evidence.get("override"),
        support_decision=report,
        trust_eligibility=candidate.eligibility.to_dict(),
    )


def _finalizer_resolution(registry: FinalizerRegistry | None) -> FinalizerResolution:
    if registry is None:
        return FinalizerResolution(
            id=FINALIZER_ID,
            source_pack={"id": "rendering"},
            manifest_digest=_ZERO_DIGEST,
            alias_chain=[],
            override=None,
            trust_eligibility={"eligible": True},
            support_decision=None,
        )
    candidate = registry.get(FINALIZER_ID)
    evidence = registry.resolve_evidence(FINALIZER_ID)
    return FinalizerResolution(
        id=candidate.id,
        source_pack=_source_pack(candidate),
        manifest_digest=candidate.manifest_digest,
        alias_chain=list(evidence.get("alias_chain") or []),
        override=evidence.get("override"),
        trust_eligibility=candidate.eligibility.to_dict(),
        support_decision=None,
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


class _CommandSupportResolver:
    def __init__(
        self,
        registry: RendererRegistry,
        *,
        workspace: Path,
    ) -> None:
        self.registry = registry
        self.workspace = workspace
        self.counter = 0

    def __call__(
        self,
        renderer_id: str,
        request: RenderRequest,
        timeline: Mapping[str, Any],
    ) -> SupportReport:
        candidate = self.registry.get(renderer_id)
        evidence = self.registry.resolve_evidence(renderer_id)
        del evidence
        projected = request.for_backend(candidate.id)
        if candidate.manifest.capabilities.get("supports_windows") is False:
            if projected.window is None:
                raise ValueError("planned renderer support requires a frame window")
            path = self.workspace / "planner-support" / f"{self.counter:04d}-timeline.json"
            self.counter += 1
            write_json_atomic(path, timeline)
            projected = replace(projected, timeline_path=str(path), window=None)
        if "support" not in candidate.manifest.operations:
            supports = (
                candidate.manifest.capabilities.get(
                    "supports_windows" if projected.window is not None else "supports_full_timeline"
                )
                is True
            )
            return SupportReport(
                schema_version=SCHEMA_VERSION,
                supported=supports,
                reasons=[] if supports else ["renderer lacks static support for this window"],
                features={
                    str(key): value
                    for key, value in candidate.manifest.capabilities.get("features", {}).items()
                    if isinstance(value, (bool, str))
                },
                alternatives=[],
                backend=candidate.id,
                backend_version=candidate.manifest.version,
            )
        request_path = self.workspace / "planner-support" / f"{self.counter:04d}-request.json"
        result_path = self.workspace / "planner-support" / f"{self.counter:04d}-result.json"
        self.counter += 1
        write_json_atomic(request_path, projected.to_dict())
        response = CommandTransport(candidate.id).run(
            "support",
            candidate.manifest.command,
            request_path=request_path,
            result_path=result_path,
            cwd=candidate.pack_root,
            required_binaries=(),
            timeout=candidate.manifest.timeout_seconds,
        )
        if not isinstance(response, SupportReport):
            raise TypeError(f"{candidate.id} support did not return a SupportReport")
        return response


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
            message="legacy hybrid planner does not support this request",
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
    total_frames, raw_segments = _segment_kinds(timeline, fps)

    renderer_registry: RendererRegistry | None
    finalizer_registry: FinalizerRegistry | None
    if registries is None and support_resolver is None:
        raw_extra_roots = config.get("extra_pack_roots", ())
        if isinstance(raw_extra_roots, (str, bytes)) or not isinstance(raw_extra_roots, Sequence):
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
            raise RuntimeError("renderer registry is required for command support resolution")
        support_resolver = _CommandSupportResolver(
            renderer_registry,
            workspace=workspace,
        )

    candidates = _candidate_lists(config)
    if request.window is not None:
        target_start = request.window.start_frame
        target_end = request.window.end_frame
        raw_segments = [
            (max(start, target_start), min(end, target_end), kind)
            for start, end, kind in raw_segments
            if min(end, target_end) > max(start, target_start)
        ]
    segments: list[RenderSegment] = []
    reasons: dict[str, str] = {}
    for index, (start, end, kind) in enumerate(raw_segments):
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
        attempts: list[str] = []
        selected_id: str | None = None
        selected_report: SupportReport | None = None
        for renderer_id in candidates[kind]:
            try:
                candidate_report = support_resolver(
                    renderer_id,
                    segment_request,
                    segment_timeline,
                )
            except Exception as exc:  # noqa: BLE001 - renderer candidates are independently attempted
                attempts.append(f"{renderer_id}: {exc}")
                continue
            # The support resolver already resolved the requested id through
            # the registry; a configured alias or override therefore names a
            # different canonical id than the raw candidate list entry.  Match
            # on the resolved candidate id, never the raw spelling.
            resolved_id = renderer_id
            if renderer_registry is not None:
                try:
                    resolved_id = renderer_registry.get(renderer_id).id
                except Exception:  # noqa: BLE001 - retain raw id when registry lookup fails
                    resolved_id = renderer_id
            if candidate_report.backend != resolved_id:
                attempts.append(f"{renderer_id}: support report named {candidate_report.backend}")
                continue
            if candidate_report.supported:
                selected_id = renderer_id
                selected_report = candidate_report
                break
            attempts.append(f"{renderer_id}: " + "; ".join(candidate_report.reasons))
        if selected_id is None or selected_report is None:
            raise_unsupported_error(
                backend=BACKEND_ID,
                message=f"no renderer supports planned {kind} window [{start},{end})",
                recovery_command="install or configure a renderer supporting the reported window",
                details={"window": [start, end], "attempts": attempts},
            )
        segments.append(
            RenderSegment(
                window=window,
                renderer=_renderer_resolution(
                    selected_id,
                    selected_report,
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
        reasons[str(index)] = f"{kind} legacy window assigned to {selected_id} by supported report"

    return RenderPlan(
        schema_version=SCHEMA_VERSION,
        request_digest=compute_request_digest(request.to_dict()),
        requested_policy="hybrid",
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
    "_complex_clip_windows",
    "_complex_frame_windows",
    "_hybrid_segments",
    "main",
    "plan",
    "support",
]
