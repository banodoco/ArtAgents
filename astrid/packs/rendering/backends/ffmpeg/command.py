"""Pure FFmpeg command builders for the media-only renderer.

The builders read the immutable request inputs and return argv.  They do not
create directories, write files, or launch subprocesses, which keeps command
construction independently testable from execution and publication.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from astrid.core import timeline
from astrid.core.rendering.contracts import RenderRequest


@dataclass(frozen=True)
class RenderCommandInputs:
    """Resolved, validated inputs used to construct one FFmpeg argv."""

    timeline_path: Path
    assets_path: Path
    output_path: Path
    timeline_data: dict[str, Any]
    registry: dict[str, Any]
    audio_sample_rate: int = 48000
    # Probe-derived evidence from strict support: stream-copy is only
    # permitted when the actual media probe confirmed whole-source
    # compatibility (never trust registry metadata alone).
    stream_copy_allowed: bool = False


def timeline_canvas(timeline_data: Mapping[str, Any]) -> tuple[int, int, int]:
    canvas = (
        timeline_data.get("theme_overrides", {})
        .get("visual", {})
        .get("canvas", {})
    )
    return (
        int(canvas.get("width", 1920)),
        int(canvas.get("height", 1080)),
        int(canvas.get("fps", 30)),
    )


def clip_duration_seconds(clip: Mapping[str, Any]) -> float:
    clip_id = clip.get("id")

    def number(value: Any, label: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Clip {clip_id!r} {label} must be a finite number")
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f"Clip {clip_id!r} {label} must be a finite number")
        return result

    # Stills (media + hold, no from/to) are bounded by their hold duration.
    if clip.get("from") is None and clip.get("to") is None:
        if clip.get("hold") is not None:
            return number(clip.get("hold"), "hold")
        raise ValueError(f"Clip {clip_id!r} must declare a source to bound")
    start = number(clip.get("from", 0), "from")
    if "to" not in clip:
        raise ValueError(f"Clip {clip_id!r} must declare a source to bound")
    end = number(clip.get("to"), "to")
    speed = number(clip.get("speed", 1), "speed")
    if speed <= 0:
        raise ValueError(f"Clip {clip_id!r} has non-positive speed {speed}")
    if start < 0 or end <= start:
        raise ValueError(
            f"Clip {clip_id!r} must have positive source bounds with to > from"
        )
    return (end - start) / speed


def validate_ffmpeg_media_timeline(timeline_data: Mapping[str, Any]) -> None:
    """Reject every media-timeline semantic the pure builder would discard."""

    # Local import avoids a module cycle: support owns semantic validation and
    # imports this module only for command construction helpers.
    from astrid.packs.rendering.backends.ffmpeg.support import structural_reasons

    reasons = structural_reasons(
        timeline_data,
        allow_audio_reactive=False,
    )
    if reasons:
        raise ValueError(reasons[0])


def _input_path(raw_path: str, workspace: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    return (
        candidate if candidate.is_absolute() else workspace / candidate
    ).resolve()


def _coerce_request(request: RenderRequest | Mapping[str, Any]) -> RenderRequest:
    if isinstance(request, RenderRequest):
        return request
    return RenderRequest.from_dict(request)


def resolve_render_command_inputs(
    request: RenderRequest | Mapping[str, Any],
    workspace: Path,
) -> RenderCommandInputs:
    """Resolve the request's existing input files without mutating anything."""

    normalized = _coerce_request(request)
    root = Path(workspace).resolve()
    timeline_path = _input_path(normalized.timeline_path, root)
    if normalized.assets_registry_path is None:
        raise ValueError("rendering.ffmpeg requires an assets registry")
    assets_path = _input_path(normalized.assets_registry_path, root)
    if not timeline_path.exists():
        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
    if not assets_path.exists():
        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
    if not isinstance(timeline_data, dict):
        raise ValueError("timeline must contain a JSON object")
    registry = timeline.load_registry(assets_path)
    validate_ffmpeg_media_timeline(timeline_data)
    return RenderCommandInputs(
        timeline_path=timeline_path,
        assets_path=assets_path,
        output_path=(root / "outputs" / normalized.output_name).resolve(),
        timeline_data=timeline_data,
        registry=dict(registry),
    )


def _command_inputs_for_paths(
    timeline_path: Path,
    assets_path: Path,
    output_path: Path,
) -> RenderCommandInputs:
    resolved_timeline = Path(timeline_path).resolve()
    resolved_assets = Path(assets_path).resolve()
    if not resolved_timeline.exists():
        raise FileNotFoundError(f"Timeline missing: {resolved_timeline}")
    if not resolved_assets.exists():
        raise FileNotFoundError(f"Asset registry missing: {resolved_assets}")
    timeline_data = json.loads(resolved_timeline.read_text(encoding="utf-8"))
    if not isinstance(timeline_data, dict):
        raise ValueError("timeline must contain a JSON object")
    registry = timeline.load_registry(resolved_assets)
    validate_ffmpeg_media_timeline(timeline_data)
    return RenderCommandInputs(
        timeline_path=resolved_timeline,
        assets_path=resolved_assets,
        # The legacy explicit-path helper passed the caller's spelling through
        # to FFmpeg and returned the same Path.  Protocol requests use the
        # workspace builder above, which deliberately resolves their output.
        output_path=Path(output_path),
        timeline_data=timeline_data,
        registry=dict(registry),
    )


def build_filter_graph(
    inputs: RenderCommandInputs,
) -> tuple[list[str], int | None, list[Path]]:
    """Return the filter graph, optional stream-copy input index, and the
    rasterized text PNG paths (which must be appended as ffmpeg inputs)."""

    from astrid.packs.rendering.backends.ffmpeg import text

    timeline_data = inputs.timeline_data
    text_png_paths: list[Path] = []
    registry = inputs.registry
    width, height, fps = timeline_canvas(timeline_data)
    tracks = {
        track.get("id"): track for track in timeline_data.get("tracks", [])
    }
    visual_track_ids = {
        track["id"]
        for track in tracks.values()
        if track.get("kind") == "visual"
    }
    audio_track_ids = {
        track["id"]
        for track in tracks.values()
        if track.get("kind") == "audio"
    }
    all_clips = sorted(
        [
            clip
            for clip in timeline_data.get("clips", [])
            if clip.get("track") in visual_track_ids or clip.get("track") in audio_track_ids
        ],
        key=lambda clip: float(clip.get("at", 0) or 0),
    )
    media_clips = [
        clip
        for clip in all_clips
        if clip.get("clipType") == "media"
        and clip.get("track") in visual_track_ids
    ]
    text_clips = [
        clip
        for clip in all_clips
        if clip.get("clipType") == "text"
    ]
    audio_clips = sorted(
        [
            clip
            for clip in all_clips
            if clip.get("track") in audio_track_ids
        ],
        key=lambda clip: float(clip.get("at", 0) or 0),
    )
    if not media_clips and not text_clips:
        raise ValueError("ffmpeg engine needs at least one visual media or text clip")

    asset_keys: list[str] = []
    for clip in [*media_clips, *audio_clips]:
        asset_key = str(clip.get("asset") or "")
        if not asset_key:
            raise ValueError(f"Clip {clip.get('id')!r} has no asset")
        if asset_key not in registry["assets"]:
            raise ValueError(
                f"Clip {clip.get('id')!r} references unknown asset "
                f"{asset_key!r}"
            )
        if asset_key not in asset_keys:
            asset_keys.append(asset_key)

    # Generate text overlay PNGs for text clips
    text_assets: dict[str, bytes] = {}
    for clip in text_clips:
        clip_id = clip.get("id")
        text_data = clip.get("text", {})
        try:
            text_png = text.text_to_rgba_png(
                content=text_data.get("content", ""),
                fontSize=text_data.get("fontSize", 48),
                color=text_data.get("color", "#FFFFFF"),
                align=text_data.get("align", "center"),
                bold=text_data.get("bold", False),
                anchor=text_data.get("anchor", "top-left"),
                offsetX=text_data.get("offsetX", 0),
                offsetY=text_data.get("offsetY", 0),
                maxWidth=text_data.get("maxWidth"),
                textShadow=text_data.get("textShadow"),
                weight=text_data.get("weight", 400),
            )
            text_assets[clip_id] = text_png
        except Exception as exc:
            raise ValueError(f"Failed to rasterize text for clip {clip_id!r}: {exc}") from exc

    asset_index = {
        asset_key: index for index, asset_key in enumerate(asset_keys)
    }
    filters: list[str] = []
    video_labels: list[str] = []
    text_labels: list[str] = []
    copy_video_input: int | None = None
    if len(media_clips) == 1:
        clip = media_clips[0]
        asset_key = str(clip["asset"])
        entry = registry["assets"][asset_key]
        source_duration = entry.get("duration")
        source_resolution = entry.get("resolution")
        source_fps = entry.get("fps")
        start = float(clip.get("from", 0) or 0)
        end = float(clip.get("to", start) or start)
        at = float(clip.get("at", 0) or 0)
        full_duration = (
            isinstance(source_duration, (int, float))
            and abs((end - start) - float(source_duration)) < 0.05
        )
        same_resolution = source_resolution == f"{width}x{height}"
        same_fps = (
            isinstance(source_fps, (int, float))
            and not isinstance(source_fps, bool)
            and math.isfinite(float(source_fps))
            and abs(float(source_fps) - fps) < 1e-6
        )
        no_visual_adjustments = not any(
            key in clip
            for key in (
                "x",
                "y",
                "width",
                "height",
                "cropTop",
                "cropBottom",
                "cropLeft",
                "cropRight",
                "effects",
                "transition",
            )
        )
        if (
            inputs.stream_copy_allowed
            and at == 0
            and start == 0
            and full_duration
            and same_resolution
            and same_fps
            and no_visual_adjustments
        ):
            copy_video_input = asset_index[asset_key]
    if copy_video_input is None:
        # Process media clips
        for index, clip in enumerate(media_clips):
            inp = asset_index[str(clip["asset"])]
            label = f"v{index}"
            is_still = clip.get("from") is None and clip.get("to") is None
            if is_still:
                hold = float(clip.get("hold", 0) or 0)
                # Still image: loop the single frame for `hold` seconds.
                filters.append(
                    f"[{inp}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                    f"fps={fps},trim=duration={hold:.6f},"
                    f"setpts=PTS-STARTPTS,format=yuv420p[{label}]"
                )
            else:
                start = float(clip.get("from", 0) or 0)
                end = float(clip.get("to", start) or start)
                filters.append(
                    f"[{inp}:v]trim=start={start:.6f}:end={end:.6f},"
                    "setpts=PTS-STARTPTS,"
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                    f"fps={fps},format=yuv420p[{label}]"
                )
            video_labels.append(f"[{label}]")
        # Text overlays: chain overlay filters over the base concat.
        # The text PNGs are the LAST inputs (after media + audio), so they are
        # referenced as [<media_input_count + audio_input_count + index>:v].
        import os
        if not text_clips:
            # No overlays: the base concat feeds vout directly (unchanged
            # legacy shape for pure media-only timelines).
            filters.append(
                "".join(video_labels)
                + f"concat=n={len(video_labels)}:v=1:a=0[vout]"
            )
        else:
            base_label = "vbase"
            filters.append(
                "".join(video_labels)
                + f"concat=n={len(video_labels)}:v=1:a=0[{base_label}]"
            )
            current_label = base_label
            import tempfile
            # Text PNGs are appended as inputs AFTER all media + audio assets,
            # so their input index = len(asset_keys) + text_index.
            text_base_index = len(asset_keys)
            for index, clip in enumerate(text_clips):
                clip_id = clip.get("id")
                at = float(clip.get("at", 0))
                hold = float(clip.get("hold", 4))
                end = at + hold
                text_png = text_assets.get(clip_id)
                if not text_png:
                    raise ValueError(f"No rendered text found for clip {clip_id!r}")
                fd, png_path = tempfile.mkstemp(suffix=".png")
                try:
                    with os.fdopen(fd, "wb") as fh:
                        fh.write(text_png)
                    text_png_paths.append(Path(png_path))
                    text_input = text_base_index + index
                    next_label = f"vt{index}"
                    fade_expr = ""
                    params = clip.get("params") or {}
                    fade_in = params.get("fadeIn")
                    fade_out = params.get("fadeOut")
                    if fade_in is not None:
                        fade_expr += (
                            f",format=rgba,colorchannelmixer=aa="
                            f"'if(lt(t,{at}+{fade_in}),(t-{at})/{fade_in},1)'"
                        )
                    elif fade_out is not None:
                        fade_expr += (
                            f",format=rgba,colorchannelmixer=aa="
                            f"'if(gt(t,{end}-{fade_out}),({end}-t)/{fade_out},1)'"
                        )
                    filters.append(
                        f"[{current_label}][{text_input}:v]{fade_expr}"
                        f"overlay=0:0:enable='between(t,{at},{end})'[{next_label}]"
                    )
                    current_label = next_label
                except Exception:
                    try:
                        os.unlink(png_path)
                    except OSError:
                        pass
                    raise
            filters.append(f"[{current_label}]format=yuv420p[vout]")

    audio_labels: list[str] = []
    cursor = 0.0
    audio_index = 0
    for clip in audio_clips:
        at = float(clip.get("at", 0))
        if at > cursor + 1e-9:
            duration = at - cursor
            label = f"a{audio_index}"
            filters.append(
                f"anullsrc=r={inputs.audio_sample_rate}:cl=stereo,"
                f"atrim=duration={duration:.6f}[{label}]"
            )
            audio_labels.append(f"[{label}]")
            audio_index += 1
        inp = asset_index[str(clip["asset"])]
        start = float(clip.get("from", 0))
        end = float(clip.get("to"))
        track = tracks[str(clip["track"])]
        from astrid.packs.rendering.backends.ffmpeg.support import effective_gain

        volume = effective_gain(track, clip)
        label = f"a{audio_index}"
        filters.append(
            f"[{inp}:a]atrim=start={start:.6f}:end={end:.6f},"
            "asetpts=PTS-STARTPTS,"
            f"aformat=sample_rates={inputs.audio_sample_rate}:channel_layouts=stereo,"
            f"volume={volume:.6f}[{label}]"
        )
        audio_labels.append(f"[{label}]")
        cursor = at + clip_duration_seconds(clip)
        audio_index += 1

    if audio_clips:
        visual_duration = max(
            float(clip.get("at", 0)) + clip_duration_seconds(clip)
            for clip in media_clips + text_clips
        )
        if visual_duration > cursor + 1e-9:
            duration = visual_duration - cursor
            label = f"a{audio_index}"
            filters.append(
                f"anullsrc=r={inputs.audio_sample_rate}:cl=stereo,"
                f"atrim=duration={duration:.6f}[{label}]"
            )
            audio_labels.append(f"[{label}]")
        filters.append(
            "".join(audio_labels)
            + f"concat=n={len(audio_labels)}:v=0:a=1[aout]"
        )
    return filters, copy_video_input, text_png_paths


def _has_audio_clips(timeline_data: Mapping[str, Any]) -> bool:
    tracks = {
        track.get("id"): track
        for track in timeline_data.get("tracks", [])
        if isinstance(track, Mapping)
    }
    return any(
        isinstance(clip, Mapping)
        and clip.get("clipType") == "media"
        and tracks.get(clip.get("track"), {}).get("kind") == "audio"
        for clip in timeline_data.get("clips", [])
    )


def _asset_input_argv(
    inputs: RenderCommandInputs,
    text_png_paths: list[Path] | None = None,
) -> list[str]:
    timeline_data = inputs.timeline_data
    registry = inputs.registry
    tracks = {
        track.get("id"): track for track in timeline_data.get("tracks", [])
    }
    visual_track_ids = {
        track["id"]
        for track in tracks.values()
        if track.get("kind") == "visual"
    }
    audio_track_ids = {
        track["id"]
        for track in tracks.values()
        if track.get("kind") == "audio"
    }
    video_clips = sorted(
        [
            clip
            for clip in timeline_data.get("clips", [])
            if clip.get("track") in visual_track_ids
        ],
        key=lambda clip: float(clip.get("at", 0) or 0),
    )
    audio_clips = sorted(
        [
            clip
            for clip in timeline_data.get("clips", [])
            if clip.get("track") in audio_track_ids
        ],
        key=lambda clip: float(clip.get("at", 0) or 0),
    )
    asset_keys: list[str] = []
    for clip in [*video_clips, *audio_clips]:
        asset_key = str(clip.get("asset") or "")
        if asset_key and asset_key not in asset_keys:
            asset_keys.append(asset_key)

    argv: list[str] = []
    still_asset_keys = {
        str(clip.get("asset"))
        for clip in video_clips
        if clip.get("clipType") == "media"
        and clip.get("from") is None
        and clip.get("to") is None
    }
    for asset_key in asset_keys:
        entry = registry["assets"][asset_key]
        file_value = entry.get("file")
        if not isinstance(file_value, str) or not file_value:
            raise ValueError(
                "ffmpeg engine requires local file assets; "
                f"{asset_key!r} has no file"
            )
        asset_path = Path(file_value)
        if not asset_path.is_absolute():
            asset_path = (inputs.assets_path.parent / asset_path).resolve()
        if asset_key in still_asset_keys:
            # Still image: loop its single frame for the hold duration (T3).
            argv.extend(["-loop", "1", "-i", str(asset_path)])
        else:
            argv.extend(["-i", str(asset_path)])
    for png_path in text_png_paths or []:
        argv.extend(["-i", str(png_path)])
    return argv


def build_render_command_from_inputs(inputs: RenderCommandInputs) -> list[str]:
    """Return FFmpeg argv for already-resolved, strictly supported inputs."""
    filters, copy_video_input, text_png_paths = build_filter_graph(inputs)
    has_audio = _has_audio_clips(inputs.timeline_data)
    return [
        "ffmpeg",
        "-hide_banner",
        "-y",
        *_asset_input_argv(inputs, text_png_paths),
        *(["-filter_complex", ";".join(filters)] if filters else []),
        "-map",
        (
            f"{copy_video_input}:v:0"
            if copy_video_input is not None
            else "[vout]"
        ),
        *(["-map", "[aout]"] if has_audio else []),
        "-c:v",
        "copy" if copy_video_input is not None else "libx264",
        *(
            ["-preset", "veryfast", "-crf", "20"]
            if copy_video_input is None
            else []
        ),
        *(
            ["-c:a", "aac", "-b:a", "192k"]
            if has_audio
            else ["-an"]
        ),
        "-movflags",
        "+faststart",
        str(inputs.output_path),
    ]


def build_render_command(
    request: RenderRequest | Mapping[str, Any],
    workspace: Path,
) -> list[str]:
    """Build FFmpeg argv for ``workspace/outputs/<request.output_name>``.

    Stream-copy is permitted only when strict support's probe evidence says
    the whole source is compatible (never trust registry metadata alone).
    """
    inputs = resolve_render_command_inputs(request, workspace)
    try:
        from astrid.core.rendering.contracts import RenderRequest
        from astrid.packs.rendering.backends.ffmpeg.support import support

        normalized_request = (
            request
            if isinstance(request, RenderRequest)
            else RenderRequest.from_dict(request)
        )
        report = support(
            normalized_request,
            inputs.timeline_data,
            inputs.registry,
        )
        stream_copy_allowed = (
            report.supported and bool(report.features.get("stream_copy"))
        )
    except Exception:
        stream_copy_allowed = False
    inputs = replace(inputs, stream_copy_allowed=stream_copy_allowed)
    return build_render_command_from_inputs(inputs)


def build_render_command_from_data(
    timeline_path: Path,
    assets_path: Path,
    output_path: Path,
    timeline_data: Mapping[str, Any],
    registry: Mapping[str, Any],
    *,
    audio_sample_rate: int = 48000,
    stream_copy_allowed: bool = False,
) -> list[str]:
    """Build FFmpeg argv from ALREADY-LOADED, strictly supported data.

    Used by the legacy facade path so the exact mappings it validated with
    strict support are the ones rendered — no reload, no TOCTOU window.
    """
    return build_render_command_from_inputs(
        RenderCommandInputs(
            timeline_path=Path(timeline_path).resolve(),
            assets_path=Path(assets_path).resolve(),
            output_path=Path(output_path).resolve(),
            timeline_data=dict(timeline_data),
            registry=dict(registry),
            audio_sample_rate=audio_sample_rate,
            stream_copy_allowed=stream_copy_allowed,
        )
    )


def build_render_command_for_paths(
    timeline_path: Path,
    assets_path: Path,
    output_path: Path,
) -> list[str]:
    """Compatibility builder for the legacy facade's explicit output path."""

    return build_render_command_from_inputs(
        _command_inputs_for_paths(timeline_path, assets_path, output_path)
    )


__all__ = [
    "RenderCommandInputs",
    "build_filter_graph",
    "build_render_command",
    "build_render_command_for_paths",
    "build_render_command_from_inputs",
    "clip_duration_seconds",
    "resolve_render_command_inputs",
    "timeline_canvas",
    "validate_ffmpeg_media_timeline",
]
