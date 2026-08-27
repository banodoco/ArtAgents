#!/usr/bin/env python3

"""Legacy rendering engine (characterized behavior).

Everything in this module is the historical monolith's render pipeline,
preserved verbatim so characterization tests can lock the legacy behavior
that the :mod:`RenderService <astrid.core.rendering.service>` now reproduces
through registered backends, planners, and finalizers.  The facade
(``run.py``) is a neutral adapter and MUST NOT import or dispatch through
this module; production callers use the service.

The legacy engine retains the private backend aliases it historically
re-exported so characterization fixtures can drive the old paths exactly.
"""

from __future__ import annotations

from contextvars import ContextVar
from fractions import Fraction
from json import dumps as _json_dumps
from json import loads as _json_loads
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Sequence

from astrid.core import timeline
from astrid.core.audit import AuditContext
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.rendering.contracts import AudioOwnership, RenderProfile
from astrid.core.rendering.profile import resolve_render_profile
from astrid.core.rendering.publication import publish_render_result
from astrid.packs.rendering.backends.ffmpeg import command as ffmpeg_command
from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg_backend
from astrid.packs.rendering.backends.remotion import run as remotion_backend
from astrid.packs.rendering.finalizers.ffmpeg import run as ffmpeg_finalizer
from astrid.packs.rendering.planners.legacy_hybrid.run import (
    _hybrid_segments,
)

# Compatibility exports for callers that historically imported these private
# helpers from the facade.  Their implementation now lives with the backend.
_RangeHTTPRequestHandler = remotion_backend._RangeHTTPRequestHandler
_validate_project_dir = remotion_backend._validate_project_dir
_serialize_timeline = remotion_backend._serialize_timeline
_resolve_theme_path = remotion_backend._resolve_theme_path
_theme_for_props = remotion_backend._theme_for_props
_theme_slug_for_render_default = remotion_backend._theme_slug_for_render_default
_resolved_theme_for_render = remotion_backend._resolved_theme_for_render
_timeline_composition_src = remotion_backend._timeline_composition_src
_registry_output_paths = remotion_backend._registry_output_paths
_registry_outputs_exist = remotion_backend._registry_outputs_exist
_active_theme_pointer_current = remotion_backend._active_theme_pointer_current
_effective_registry_state = remotion_backend._effective_registry_state
_read_registry_state = remotion_backend._read_registry_state
_write_registry_state = remotion_backend._write_registry_state
_regenerate_element_registries = remotion_backend._regenerate_element_registries
_render_asset_stage_hash = remotion_backend._render_asset_stage_hash
_effect_registry_for_assets = remotion_backend._effect_registry_for_assets
_effect_id_for_clip = remotion_backend._effect_id_for_clip
_source_pack_id = remotion_backend._source_pack_id
_inject_clip_asset_params = remotion_backend._inject_clip_asset_params
_stage_effect_assets_for_timeline = remotion_backend._stage_effect_assets_for_timeline
_render_provenance_sidecar_path = remotion_backend._render_provenance_sidecar_path
_active_pack_order_for_provenance = remotion_backend._active_pack_order_for_provenance
_active_theme_for_provenance = remotion_backend._active_theme_for_provenance
_render_provenance_payload = remotion_backend._render_provenance_payload
_write_render_provenance = remotion_backend._write_render_provenance
_timeline_canvas = ffmpeg_command.timeline_canvas
_clip_duration_seconds = ffmpeg_command.clip_duration_seconds

_PUBLICATION_PREVIOUS_OUTPUTS: ContextVar[tuple[Path, ...]] = ContextVar(
    "render_publication_previous_outputs",
    default=(),
)
_HYBRID_FINALIZER_PROFILE: ContextVar[RenderProfile | None] = ContextVar(
    "hybrid_finalizer_profile",
    default=None,
)


def _swap_from_dump(clip: dict) -> dict:
    out = dict(clip)
    if "from_" in out:
        out["from"] = out.pop("from_")
    return out


def _clip_timeline_end_seconds(clip: dict) -> float:
    start = float(clip.get("at", 0) or 0)
    if clip.get("clipType") == "media":
        return start + _clip_duration_seconds(clip)
    hold = clip.get("hold")
    if isinstance(hold, (int, float)):
        return start + max(0.0, float(hold))
    if isinstance(clip.get("to"), (int, float)):
        return float(clip["to"])
    return start


def _timeline_duration_seconds(timeline_data: dict) -> float:
    metadata = timeline_data.get("metadata", {})
    explicit = metadata.get("duration_seconds") if isinstance(metadata, dict) else None
    if not isinstance(explicit, (int, float)) and isinstance(metadata, dict):
        explicit = metadata.get("expected_duration_seconds")
    if isinstance(explicit, (int, float)):
        return float(explicit)
    return max(
        (_clip_timeline_end_seconds(clip) for clip in timeline_data.get("clips", [])), default=0.0
    )


def _round_frame_time(seconds: float, fps: int | Fraction, *, mode: str) -> float:
    rate = fps if isinstance(fps, Fraction) else Fraction(fps, 1)
    instant = (
        seconds if isinstance(seconds, Fraction) else Fraction(seconds).limit_denominator(1_000_000)
    )
    frames = instant * rate
    if mode == "floor":
        frame = frames.numerator // frames.denominator
    elif mode == "ceil":
        frame = -(-frames.numerator // frames.denominator)
    else:
        frame = round(frames)
    return float(Fraction(frame, 1) / rate)


def _clip_overlaps(clip: dict, start: float, end: float) -> bool:
    clip_start = float(clip.get("at", 0) or 0)
    clip_end = _clip_timeline_end_seconds(clip)
    return clip_start < end and clip_end > start


def _window_clip(clip: dict, start: float, end: float) -> dict | None:
    if not _clip_overlaps(clip, start, end):
        return None
    clip_start = float(clip.get("at", 0) or 0)
    visible_start = max(clip_start, start)
    visible_end = min(_clip_timeline_end_seconds(clip), end)
    if visible_end <= visible_start:
        return None

    out = dict(clip)
    out["at"] = visible_start - start
    out["id"] = f"{clip.get('id', 'clip')}_{start:.3f}_{end:.3f}".replace(".", "_")
    if clip.get("clipType") == "media":
        speed = float(clip.get("speed", 1) or 1)
        source_from = float(clip.get("from", 0) or 0) + ((visible_start - clip_start) * speed)
        out["from"] = source_from
        out["to"] = source_from + ((visible_end - visible_start) * speed)
    elif isinstance(clip.get("hold"), (int, float)):
        out["hold"] = visible_end - visible_start
    return out


def _window_timeline_data(
    timeline_data: dict, start: float, end: float, *, media_only: bool
) -> dict:
    clips: list[dict] = []
    for clip in timeline_data.get("clips", []):
        if media_only and clip.get("clipType") != "media":
            continue
        windowed = _window_clip(clip, start, end)
        if windowed is not None:
            clips.append(windowed)
    used_tracks = {clip.get("track") for clip in clips}
    tracks = [track for track in timeline_data.get("tracks", []) if track.get("id") in used_tracks]
    out = dict(timeline_data)
    out["tracks"] = tracks
    out["clips"] = clips
    out["metadata"] = {
        **dict(timeline_data.get("metadata", {})),
        "source_window_start_seconds": start,
        "source_window_end_seconds": end,
        "duration_seconds": end - start,
    }
    return out


_validate_ffmpeg_media_timeline = ffmpeg_command.validate_ffmpeg_media_timeline


def _render_ffmpeg_media_to_path(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
) -> Path:
    return ffmpeg_backend._render_ffmpeg_media_to_path(
        timeline_path,
        assets_path,
        out_path,
    )


def _render_ffmpeg_media(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
    *,
    _previous_outputs: Sequence[Path] | None = None,
) -> Path:
    return ffmpeg_backend.render(
        timeline_path,
        assets_path,
        out_path,
        previous_outputs=(
            _PUBLICATION_PREVIOUS_OUTPUTS.get() if _previous_outputs is None else _previous_outputs
        ),
        _render_to_path=_render_ffmpeg_media_to_path,
    )


def _can_render_with_ffmpeg_media(
    timeline_path: Path,
    assets_path: Path,
) -> bool:
    return ffmpeg_backend.can_render_with_ffmpeg_media(
        timeline_path,
        assets_path,
    )


def _concat_segments(segment_paths: list[Path], out_path: Path) -> None:
    profile = _HYBRID_FINALIZER_PROFILE.get()
    audio = None
    if profile is not None:
        audio = AudioOwnership.RENDERED if profile.has_audio else AudioOwnership.NONE
    ffmpeg_finalizer.concat_segment_files(
        segment_paths,
        out_path,
        profile=profile,
        audio=audio,
    )


def _render_hybrid(
    timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs
) -> Path:
    if not timeline_path.exists():
        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
    if not assets_path.exists():
        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
    timeline_data = _json_loads(timeline_path.read_text(encoding="utf-8"))
    canonical_profile = resolve_render_profile(
        timeline_data,
        timeline.load_registry(assets_path),
        theme=remotion_kwargs.get("theme_path"),
        themes_root=REPO_ROOT / "themes",
    )
    segments = _hybrid_segments(
        timeline_data,
        fps=Fraction(*canonical_profile.fps_rational),
    )
    if (
        canonical_profile.fps_rational[1] == 1
        and len(segments) == 1
        and segments[0]["engine"] == "ffmpeg"
    ):
        return _render_ffmpeg_media(timeline_path, assets_path, out_path)

    resolved_out = out_path.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(resolved_out.parent)) as tmp:
        tmp_dir = Path(tmp)
        segment_paths: list[Path] = []
        segment_provenance: list[dict[str, Any]] = []
        for index, segment in enumerate(segments):
            engine = str(segment["engine"])
            start = float(segment["from"])
            end = float(segment["to"])
            segment_dir = tmp_dir / f"{index:04d}-{engine}"
            segment_dir.mkdir(parents=True, exist_ok=True)
            segment_timeline_path = segment_dir / "timeline.json"
            segment_out_path = segment_dir / "segment.mp4"
            segment_timeline = _window_timeline_data(
                timeline_data, start, end, media_only=(engine == "ffmpeg")
            )
            if canonical_profile.fps_rational[1] != 1:
                # Both extracted legacy renderers accept an integer canvas
                # rate.  Render the window at the nearest rate, then let the
                # finalizer normalize to the exact canonical rational rate.
                render_rate = max(
                    1,
                    round(Fraction(*canonical_profile.fps_rational)),
                )
                overrides = dict(segment_timeline.get("theme_overrides", {}))
                visual = dict(overrides.get("visual", {}))
                canvas = dict(visual.get("canvas", {}))
                canvas["fps"] = render_rate
                visual["canvas"] = canvas
                overrides["visual"] = visual
                segment_timeline["theme_overrides"] = overrides
            segment_timeline_path.write_text(
                _json_dumps(segment_timeline, indent=2) + "\n", encoding="utf-8"
            )
            if engine == "ffmpeg":
                _render_ffmpeg_media(
                    segment_timeline_path,
                    assets_path,
                    segment_out_path,
                    _previous_outputs=(),
                )
            else:
                from .run import render  # facade delegates to the service

                render(
                    segment_timeline_path,
                    assets_path,
                    segment_out_path,
                    engine="remotion",
                    **remotion_kwargs,
                )
            sidecar_path = _render_provenance_sidecar_path(segment_out_path)
            if sidecar_path.exists():
                segment_provenance.append(_json_loads(sidecar_path.read_text(encoding="utf-8")))
            segment_paths.append(segment_out_path)
        staged_video = tmp_dir / "final" / out_path.name
        staged_video.parent.mkdir(parents=True, exist_ok=True)
        profile_token = _HYBRID_FINALIZER_PROFILE.set(canonical_profile)
        try:
            _concat_segments(segment_paths, staged_video)
        finally:
            _HYBRID_FINALIZER_PROFILE.reset(profile_token)
        provenance = _render_provenance_payload(
            out_path,
            engine="hybrid",
            timeline_path=timeline_path,
            assets_path=assets_path,
            project_dir=Path(remotion_kwargs.get("project_dir") or (REPO_ROOT / "remotion")),
            composition_id=str(remotion_kwargs.get("composition_id") or "TimelineComposition"),
            theme_path=remotion_kwargs.get("theme_path"),
            active_theme=None,
            registry_state=_effective_registry_state(remotion_kwargs.get("theme_path")),
            stage_summary={"root": None, "effects": []},
            segments=segments,
            segment_provenance=segment_provenance,
        )
        output = publish_render_result(
            staged_video,
            provenance,
            out_path=out_path,
            sidecar_path=_render_provenance_sidecar_path(out_path),
            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
        )

    audit = AuditContext.from_env()
    if audit is not None:
        timeline_id = audit.register_asset(
            kind="timeline", path=timeline_path, label="Render timeline", stage="render_hybrid"
        )
        assets_id = audit.register_asset(
            kind="assets_registry",
            path=assets_path,
            label="Render asset registry",
            stage="render_hybrid",
        )
        render_id = audit.register_asset(
            kind="render",
            path=out_path,
            label="Rendered video",
            parents=[timeline_id, assets_id],
            stage="render_hybrid",
            metadata={"engine": "hybrid", "segments": segments},
        )
        audit.register_node(
            stage="render_hybrid",
            label="Render hybrid timeline",
            parents=[timeline_id, assets_id],
            outputs=[render_id],
            metadata={"engine": "hybrid", "segments": segments},
        )
    return output


def _audio_reactive_ffmpeg_element(
    theme_path: Path | None,
) -> Any | None:
    return ffmpeg_backend._audio_reactive_ffmpeg_element(theme_path)


def _render_audio_reactive_colour_if_supported(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
    *,
    project_dir: Path | None,
    composition_id: str,
    theme_path: Path | None,
) -> Path | None:
    return ffmpeg_backend.render_audio_reactive_colour_if_supported(
        timeline_path,
        assets_path,
        out_path,
        project_dir=project_dir,
        composition_id=composition_id,
        theme_path=theme_path,
        previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
        element_resolver=_audio_reactive_ffmpeg_element,
    )
