#!/usr/bin/env python3
"""Layer-stack planner and rendering-protocol v1 command adapter.

``rendering.layer-stack`` is an opt-in planner that routes visual tracks into
renderer-owned z-layers.  If any eligible renderer ``support()``s the full
visual stack, the planner emits one ``layer=None`` segment and pins
``rendering.ffmpeg-finalizer`` (today's concat path).  Otherwise it claims
each visual track via registry ``support()``, greedy-merges adjacent
same-renderer tracks, emits one full-window segment per layer, and pins
``rendering.ffmpeg-compositor``.

Stamped remotion/threejs layers produce ProRes 4444, not the canonical H.264
plan profile.  Per-track and per-layer ``support()`` requests therefore pass
``profile=None`` so backends resolve their own output; the planner still uses
``resolve_render_profile`` for fps, canvas, and ``total_frames``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
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
    LayerRef,
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
from astrid.packs.rendering.planners.legacy_hybrid.run import (
    _ceil,
    _CommandSupportResolver,
    _load_inputs,
    _number,
    _renderer_resolution,
    _source_pack,
    _timeline_duration,
)
from astrid.packs.rendering.planners.threejs_hybrid.run import _component_timeline

BACKEND_ID = "rendering.layer-stack"
BACKEND_VERSION = "1.0.0"
CONCAT_FINALIZER_ID = "rendering.ffmpeg-finalizer"
COMPOSITOR_FINALIZER_ID = "rendering.ffmpeg-compositor"
FFMPEG_ID = "rendering.ffmpeg"
REMOTION_ID = "rendering.remotion"
THREE_ID = "rendering.threejs"
_ZERO_DIGEST = "0" * 64
_PLANNER_IDS = frozenset(
    {
        BACKEND_ID,
        "rendering.legacy_hybrid",
        "rendering.threejs-hybrid",
    }
)
_DEFAULT_CANDIDATE_IDS = (FFMPEG_ID, REMOTION_ID, THREE_ID)
_PLANNER_CONFIG_KEYS = frozenset({"theme", "theme_path", "themes_root", "extra_pack_roots"})

SupportResolver = Callable[[str, RenderRequest, Mapping[str, Any]], SupportReport]


@dataclass(frozen=True)
class _LayerClaim:
    """One renderer-owned contiguous visual-track range after greedy merge."""

    z: int
    tracks: tuple[str, ...]
    renderer_id: str
    opacity: float
    report: SupportReport


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


def _visual_tracks_bottom_to_top(
    timeline: Mapping[str, Any],
) -> list[tuple[int, Mapping[str, Any]]]:
    """Paint order is reversed array order: first visual track is TOP.

    Returns ``(z, track)`` with ``z=0`` at the bottom (last visual track).
    """

    visual = [
        track
        for track in timeline.get("tracks", [])
        if isinstance(track, Mapping) and track.get("kind") == "visual"
    ]
    stacked = list(reversed(visual))
    return [(index, track) for index, track in enumerate(stacked)]


def _project_tracks(timeline: Mapping[str, Any], track_ids: Sequence[str]) -> dict[str, Any]:
    """Project the timeline onto the named tracks (and only their clips)."""

    raw_clips = timeline.get("clips", [])
    if not isinstance(raw_clips, list):
        raise TypeError("timeline clips must be an array")
    clips = [clip for clip in raw_clips if isinstance(clip, Mapping)]
    wanted = set(track_ids)
    indexes = [index for index, clip in enumerate(clips) if clip.get("track") in wanted]
    return _component_timeline(timeline, clips, indexes)


def _track_has_clips(timeline: Mapping[str, Any], track_id: str) -> bool:
    clips = timeline.get("clips", [])
    if not isinstance(clips, list):
        return False
    return any(isinstance(clip, Mapping) and clip.get("track") == track_id for clip in clips)


def _track_id(track: Mapping[str, Any]) -> str:
    value = track.get("id")
    if not isinstance(value, str) or not value:
        raise ValueError("visual track is missing a non-empty id")
    return value


def _track_blend(track: Mapping[str, Any]) -> str:
    value = track.get("blendMode", "normal")
    if value is None:
        return "normal"
    if not isinstance(value, str):
        raise ValueError(f"visual track {track.get('id')!r} blendMode must be a string")
    return value


def _track_opacity(track: Mapping[str, Any]) -> float:
    value = track.get("opacity")
    if value is None:
        return 1.0
    try:
        opacity = float(_number(value, "track.opacity"))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"visual track {track.get('id')!r} opacity is not a finite number"
        ) from exc
    if opacity <= 0 or opacity > 1:
        raise ValueError(f"visual track {track.get('id')!r} opacity {opacity} is outside (0, 1]")
    return opacity


def _candidate_ids(registry: RendererRegistry | None) -> tuple[str, ...]:
    if registry is None:
        return _DEFAULT_CANDIDATE_IDS
    return tuple(
        candidate.id
        for candidate in registry.candidates(eligible=True)
        if candidate.id not in _PLANNER_IDS
    )


def _resolved_renderer_id(renderer_id: str, registry: RendererRegistry | None) -> str:
    if registry is None:
        return renderer_id
    try:
        return registry.get(renderer_id).id
    except RenderingRegistryError:
        return renderer_id


def _probe_support(
    renderer_id: str,
    request: RenderRequest,
    timeline: Mapping[str, Any],
    *,
    support_resolver: SupportResolver,
    registry: RendererRegistry | None,
) -> tuple[SupportReport | None, str]:
    try:
        report = support_resolver(renderer_id, request, timeline)
    except (
        RendererException,
        RenderingRegistryError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        return None, f"{renderer_id}: {exc}"
    resolved_id = _resolved_renderer_id(renderer_id, registry)
    if report.backend != resolved_id:
        return None, f"{renderer_id}: support report named {report.backend}"
    if not report.supported:
        return None, f"{renderer_id}: " + "; ".join(report.reasons)
    return report, f"{renderer_id}: supported"


def _first_supporting(
    candidate_ids: Sequence[str],
    request: RenderRequest,
    timeline: Mapping[str, Any],
    *,
    support_resolver: SupportResolver,
    registry: RendererRegistry | None,
) -> tuple[str | None, SupportReport | None, list[str]]:
    attempts: list[str] = []
    for renderer_id in candidate_ids:
        report, note = _probe_support(
            renderer_id,
            request,
            timeline,
            support_resolver=support_resolver,
            registry=registry,
        )
        attempts.append(note)
        if report is not None:
            return renderer_id, report, attempts
    return None, None, attempts


def _support_request(
    request: RenderRequest,
    *,
    timeline_path: Path,
    assets_path: Path | None,
    window: FrameWindow,
) -> RenderRequest:
    """Request used for registry ``support()`` calls.

    ``window`` is a dummy tiling window so ``_CommandSupportResolver`` will
    materialize the provided timeline and clear the window before invoking
    backends that declare ``supports_windows: false``.  ``profile`` is always
    ``None``: stamped remotion/threejs layers emit ProRes 4444, not the
    canonical H.264 plan profile.
    """

    return replace(
        request,
        timeline_path=str(timeline_path),
        assets_registry_path=None if assets_path is None else str(assets_path),
        output_name="segment-0000.mp4",
        window=window,
        profile=None,
    )


def _assign_layers(
    timeline: Mapping[str, Any],
    *,
    support_request: RenderRequest,
    candidate_ids: Sequence[str],
    support_resolver: SupportResolver,
    registry: RendererRegistry | None,
) -> list[_LayerClaim]:
    """Claim each visual track, then greedy-merge adjacent same-renderer wins.

    Merge is attempted only when the winner still ``support()``s the merged
    projection (ffmpeg's one-visual-track contract therefore keeps adjacent
    media tracks as separate z-layers).
    """

    stacked = _visual_tracks_bottom_to_top(timeline)
    claims: list[_LayerClaim] = []
    for z, track in stacked:
        track_id = _track_id(track)
        if not _track_has_clips(timeline, track_id):
            continue
        blend = _track_blend(track)
        if blend != "normal":
            raise_unsupported_error(
                backend=BACKEND_ID,
                message=(
                    f"visual track {track_id!r} uses blendMode {blend!r}; "
                    "v1 layer-stack accepts only 'normal'"
                ),
                recovery_command=(
                    "set the track blendMode to 'normal' or use a single "
                    "renderer that supports the full stack"
                ),
                details={"track": track_id, "blendMode": blend},
            )
        try:
            opacity = _track_opacity(track)
        except ValueError as exc:
            raise_unsupported_error(
                backend=BACKEND_ID,
                message=str(exc),
                recovery_command="set the track opacity to a value in (0, 1]",
                details={"track": track_id},
            )
        projected = _project_tracks(timeline, (track_id,))
        renderer_id, report, attempts = _first_supporting(
            candidate_ids,
            support_request,
            projected,
            support_resolver=support_resolver,
            registry=registry,
        )
        if renderer_id is None or report is None:
            raise_unsupported_error(
                backend=BACKEND_ID,
                message=(f"visual track {track_id!r} is not supported by any eligible renderer"),
                recovery_command=("install or configure a renderer that supports this track"),
                details={"track": track_id, "attempts": attempts},
            )
        merged = False
        if claims and claims[-1].renderer_id == renderer_id and claims[-1].opacity == opacity:
            merged_tracks = (*claims[-1].tracks, track_id)
            merged_timeline = _project_tracks(timeline, merged_tracks)
            merged_report, _note = _probe_support(
                renderer_id,
                support_request,
                merged_timeline,
                support_resolver=support_resolver,
                registry=registry,
            )
            if merged_report is not None:
                claims[-1] = _LayerClaim(
                    z=claims[-1].z,
                    tracks=merged_tracks,
                    renderer_id=renderer_id,
                    opacity=opacity,
                    report=merged_report,
                )
                merged = True
        if not merged:
            claims.append(
                _LayerClaim(
                    z=z,
                    tracks=(track_id,),
                    renderer_id=renderer_id,
                    opacity=opacity,
                    report=report,
                )
            )
    return claims


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
                "empty timeline: the layer-stack planner cannot construct a meaningful stack"
            )
        if request.window is not None:
            if request.window.fps_rational != profile.fps_rational:
                reasons.append("request window FPS does not match the canonical render profile")
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
            "registry_support_routing": True,
            "per_layer_segments": True,
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


def _finalizer_resolution(
    registry: FinalizerRegistry | None, finalizer_id: str
) -> FinalizerResolution:
    if registry is None:
        return FinalizerResolution(
            id=finalizer_id,
            source_pack={"id": "rendering"},
            manifest_digest=_ZERO_DIGEST,
            alias_chain=[],
            override=None,
            trust_eligibility={"eligible": True},
            support_decision=None,
        )
    candidate = registry.get(finalizer_id)
    evidence = registry.resolve_evidence(finalizer_id)
    return FinalizerResolution(
        id=candidate.id,
        source_pack=_source_pack(candidate),
        manifest_digest=candidate.manifest_digest,
        alias_chain=list(evidence.get("alias_chain") or []),
        override=evidence.get("override"),
        trust_eligibility=candidate.eligibility.to_dict(),
        support_decision=None,
    )


def _input_hashes(timeline_path: Path, assets_path: Path | None) -> dict[str, str]:
    hashes = {"timeline": sha256_file(timeline_path)}
    if assets_path is not None:
        hashes["assets_registry"] = sha256_file(assets_path)
    return hashes


def _plan_window(
    request: RenderRequest, *, total_frames: int, fps_rational: tuple[int, int]
) -> tuple[int, int, FrameWindow]:
    if request.window is not None:
        return (
            request.window.start_frame,
            request.window.end_frame,
            request.window,
        )
    window = FrameWindow(
        start_frame=0,
        end_frame=total_frames,
        fps_rational=fps_rational,
    )
    return 0, total_frames, window


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
            message="layer-stack planner does not support this request",
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
    total_frames = _ceil(_timeline_duration(timeline) * fps)

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

    candidate_ids = _candidate_ids(renderer_registry)
    window_start, window_end, dummy_window = _plan_window(
        request, total_frames=total_frames, fps_rational=profile.fps_rational
    )
    probe_request = _support_request(
        request,
        timeline_path=timeline_path,
        assets_path=assets_path,
        window=dummy_window,
    )

    winner_id, winner_report, _attempts = _first_supporting(
        candidate_ids,
        probe_request,
        timeline,
        support_resolver=support_resolver,
        registry=renderer_registry,
    )
    if winner_id is not None and winner_report is not None:
        return RenderPlan(
            schema_version=SCHEMA_VERSION,
            request_digest=compute_request_digest(request.to_dict()),
            requested_policy="layer_stack",
            planner=_planner_resolution(report),
            segments=[
                RenderSegment(
                    window=dummy_window,
                    renderer=_renderer_resolution(
                        winner_id,
                        winner_report,
                        registry=renderer_registry,
                    ),
                    input_hashes=_input_hashes(timeline_path, assets_path),
                )
            ],
            finalizer=_finalizer_resolution(finalizer_registry, CONCAT_FINALIZER_ID),
            profile=profile,
            total_frames=total_frames,
            reasons={
                "0": (
                    f"fast path: {winner_id} supports the full visual stack; "
                    "concat via rendering.ffmpeg-finalizer"
                )
            },
            window=request.window,
        )

    claims = _assign_layers(
        timeline,
        support_request=probe_request,
        candidate_ids=candidate_ids,
        support_resolver=support_resolver,
        registry=renderer_registry,
    )
    if len(claims) < 2:
        raise_unsupported_error(
            backend=BACKEND_ID,
            message=(
                "no eligible renderer supports the full visual stack, and "
                "layer-stack could not split it into two or more renderer-owned "
                "layers"
            ),
            recovery_command=(
                "install a renderer that supports the full stack, or split "
                "the visual tracks so at least two renderers can claim them"
            ),
            details={
                "layers": [
                    {"z": claim.z, "tracks": list(claim.tracks), "renderer": claim.renderer_id}
                    for claim in claims
                ]
            },
        )

    window = FrameWindow(
        start_frame=window_start,
        end_frame=window_end,
        fps_rational=profile.fps_rational,
    )
    hashes = _input_hashes(timeline_path, assets_path)
    segments: list[RenderSegment] = []
    reasons: dict[str, str] = {}
    for index, claim in enumerate(claims):
        segments.append(
            RenderSegment(
                window=window,
                renderer=_renderer_resolution(
                    claim.renderer_id,
                    claim.report,
                    registry=renderer_registry,
                ),
                input_hashes=hashes,
                layer=LayerRef(
                    z=claim.z,
                    tracks=claim.tracks,
                    blend="normal",
                    opacity=claim.opacity,
                ),
            )
        )
        reasons[str(index)] = (
            f"layer z={claim.z} tracks={list(claim.tracks)} assigned to "
            f"{claim.renderer_id} by supported report"
        )

    return RenderPlan(
        schema_version=SCHEMA_VERSION,
        request_digest=compute_request_digest(request.to_dict()),
        requested_policy="layer_stack",
        planner=_planner_resolution(report),
        segments=segments,
        finalizer=_finalizer_resolution(finalizer_registry, COMPOSITOR_FINALIZER_ID),
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
    "COMPOSITOR_FINALIZER_ID",
    "CONCAT_FINALIZER_ID",
    "FFMPEG_ID",
    "REMOTION_ID",
    "THREE_ID",
    "_assign_layers",
    "_project_tracks",
    "_visual_tracks_bottom_to_top",
    "main",
    "plan",
    "support",
]
