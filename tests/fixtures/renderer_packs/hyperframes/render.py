#!/usr/bin/env python3
"""HyperFrames render backend (third-party pack, pure stdlib).

Usage: python3 render.py render|support --request <abs.json> --result <abs.json>

Adapts a BOUNDED subset of the Astrid timeline to a HyperFrames composition:

* canvas (theme_overrides.visual.canvas) -> root ``#root`` with
  ``data-composition-id``, ``data-start="0"``, ``data-duration`` (compile-time
  ``max(at + hold)``), ``data-width``, ``data-height``, ``data-fps``;
* each ``text`` clip -> a direct child ``<section class="clip">`` with
  ``data-start`` / ``data-duration`` (the HyperFrames seek window), an
  inner ``<p>`` carrying the escaped text, CSS ``z-index`` from the Astrid
  visual track paint order, and a bounded CSS subset (fontSize, color,
  textAlign, fontWeight, textShadow, maxWidth, offsets/anchors);
* theme/canvas background -> a full-bleed child of the root (never the root
  background, which capture drops).

Deliberately rejected with an explicit support reason: media clips, effect
clips, audio clips/tracks, fades/transitions, and non-integer FPS.  The
adapter never tweens ``.clip`` visibility — HyperFrames owns the seek
window; visibility-only is the v1 contract.

Renders via ``npx --yes hyperframes@<pin> render <workdir> -c index.html
-o <output_name> --fps <int> --no-best-effort --strict`` and writes the
frozen RenderResult (visual-only, ``audio_ownership: none``) with a
backend fragment.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shutil
import subprocess
from pathlib import Path

BACKEND_ID = "hyperframes.renderer"
_BACKEND_VERSION = "1.0.0"
_HYPERFRAMES_PIN = "0.7.107"

_PROFILE = {
    "width": 640,
    "height": 360,
    "fps_rational": [24, 1],
    "time_base": [1, 12288],
    "container": "mp4",
    "video_codec": "h264",
    "video_profile": None,
    "video_level": None,
    "pixel_format": "yuv420p",
    "audio_codec": None,
    "audio_sample_rate": None,
    "audio_channel_layout": None,
    "duration_tolerance": 1,
}

_SUPPORTED_TEXT_KEYS = {
    "content",
    "fontSize",
    "color",
    "align",
    "weight",
    "textShadow",
    "maxWidth",
    "anchor",
    "offsetX",
    "offsetY",
}

_CSS_COLORS = {
    "black": "#000000",
    "white": "#ffffff",
    "red": "#ff0000",
    "green": "#008000",
    "blue": "#0000ff",
    "yellow": "#ffff00",
}


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _error(
    result_path: Path,
    kind: str,
    message: str,
    recovery_command: str | None = None,
    details: dict | None = None,
) -> None:
    _write(
        result_path,
        {
            "schema_version": 1,
            "kind": kind,
            "backend": BACKEND_ID,
            "message": message,
            "recovery_command": recovery_command,
            "details": details or {},
        },
    )


def _canvas(timeline: dict) -> tuple[int, int, int] | None:
    overrides = timeline.get("theme_overrides") or {}
    visual = overrides.get("visual") or {}
    canvas = visual.get("canvas") or {}
    width = canvas.get("width")
    height = canvas.get("height")
    fps = canvas.get("fps")
    if not all(isinstance(v, int) and v > 0 for v in (width, height, fps)):
        return None
    return int(width), int(height), int(fps)


def _clip_duration(clip: dict) -> float:
    hold = clip.get("hold")
    if isinstance(hold, (int, float)) and hold > 0:
        return float(hold)
    return 1.0


def _support_reasons(timeline: dict) -> list[str]:
    reasons: list[str] = []
    tracks = timeline.get("tracks") or []
    clips = timeline.get("clips") or []
    audio_tracks = [
        track.get("id")
        for track in tracks
        if isinstance(track, dict) and track.get("kind") == "audio"
    ]
    if audio_tracks:
        reasons.append(
            f"audio tracks are not supported by the HyperFrames adapter: {audio_tracks}"
        )
    for index, clip in enumerate(clips):
        if not isinstance(clip, dict):
            reasons.append(f"clip[{index}] is not an object")
            continue
        clip_type = clip.get("clipType", "media")
        if clip_type != "text":
            reasons.append(
                f"clip[{index}] clipType {clip_type!r} is not supported "
                "(text-only adapter)"
            )
        if clip.get("track") in audio_tracks:
            reasons.append(f"clip[{index}] sits on an audio track")
        if clip.get("effects"):
            reasons.append(f"clip[{index}] effects are not supported in v1")
        if clip.get("transition"):
            reasons.append(f"clip[{index}] transitions are not supported in v1")
        if clip.get("opacity") not in (None, 1):
            reasons.append(f"clip[{index}] opacity != 1 is not supported in v1")
        params = clip.get("params") or {}
        if isinstance(params, dict):
            unknown = sorted(set(params) - _SUPPORTED_TEXT_KEYS)
            if unknown:
                reasons.append(
                    f"clip[{index}] unsupported text params: {unknown}"
                )
        text_field = clip.get("text")
        if text_field is not None and not isinstance(text_field, dict):
            reasons.append(f"clip[{index}] text must be an object")
    width, height, fps = _canvas(timeline) or (None, None, None)
    if width is None:
        reasons.append("canvas width/height/fps must be positive integers")
    if isinstance(fps, int) and fps <= 0:
        reasons.append("canvas fps must be a positive integer")
    return reasons


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _css_color(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    lowered = value.strip().lower()
    return _CSS_COLORS.get(lowered, value if value.startswith("#") else None)


def _compose_html(
    timeline: dict,
    *,
    width: int,
    height: int,
    fps: int,
) -> str:
    clips = timeline.get("clips") or []
    tracks = timeline.get("tracks") or []
    visual_track_ids = [
        track.get("id")
        for track in tracks
        if isinstance(track, dict) and track.get("kind") == "visual"
    ]
    # data-track-index is a TIMING LANE (non-overlap), not paint order: give
    # each Astrid track its own lane so same-lane overlaps are impossible.
    lane = {track_id: index for index, track_id in enumerate(visual_track_ids)}
    # Astrid visual tracks paint in reversed array order (later = on top).
    z_index = {
        track_id: len(visual_track_ids) - index
        for index, track_id in enumerate(visual_track_ids)
    }
    duration = max(
        (float(clip.get("at", 0) or 0) + _clip_duration(clip) for clip in clips),
        default=1.0,
    )

    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html><head><meta charset="utf-8"><style>')
    parts.append("body{margin:0;background:#000;}")
    parts.append(
        f"#root{{position:relative;width:{width}px;height:{height}px;"
        "overflow:hidden;}"
    )
    parts.append(
        ".clip{position:absolute;top:0;left:0;width:100%;height:100%;"
        "display:flex;align-items:center;justify-content:center;}"
    )
    parts.append("</style></head><body>")
    parts.append(
        f'<div id="root" data-composition-id="astrid" data-start="0" data-no-timeline '
        f'data-layout-allow-overlap data-duration="{duration:g}" data-width="{width}" '
        f'data-height="{height}" data-fps="{fps}">'
    )
    # Full-bleed background child (capture drops the root background).
    bg = "#000000"
    overrides = timeline.get("theme_overrides") or {}
    visual = overrides.get("visual") or {}
    if isinstance(visual.get("background"), str) and visual["background"].startswith("#"):
        bg = visual["background"]
    parts.append(
        f'<div style="position:absolute;inset:0;background:{bg};"></div>'
    )

    for index, clip in enumerate(clips):
        if not isinstance(clip, dict) or clip.get("clipType") != "text":
            continue
        at = float(clip.get("at", 0) or 0)
        hold = _clip_duration(clip)
        params = clip.get("params") or {}
        content = clip.get("text")
        if not isinstance(content, dict):
            content = {}
        raw_text = content.get("content")
        if raw_text is None:
            raw_text = params.get("content")
        text = _esc(str(raw_text) if raw_text is not None else "")
        styles: list[str] = []
        color = _css_color(params.get("color"))
        if color:
            styles.append(f"color:{color};")
        font_size = params.get("fontSize")
        if isinstance(font_size, (int, float)) and font_size > 0:
            styles.append(f"font-size:{font_size:g}px;")
        align = params.get("align")
        if align in ("left", "center", "right"):
            justify = {"left": "flex-start", "center": "center", "right": "flex-end"}[align]
            styles.append(f"justify-content:{justify};")
        weight = params.get("weight")
        if isinstance(weight, (int, str)) and str(weight).isdigit():
            styles.append(f"font-weight:{weight};")
        shadow = params.get("textShadow")
        if isinstance(shadow, str) and shadow:
            styles.append(f"text-shadow:{shadow};")
        max_width = params.get("maxWidth")
        if isinstance(max_width, (int, float)) and max_width > 0:
            styles.append(f"max-width:{max_width:g}px;")
        offset_x = params.get("offsetX")
        offset_y = params.get("offsetY")
        if isinstance(offset_x, (int, float)):
            styles.append(f"margin-left:{offset_x:g}px;")
        if isinstance(offset_y, (int, float)):
            styles.append(f"margin-top:{offset_y:g}px;")
        track_id = clip.get("track")
        zi = z_index.get(track_id, 0)
        clip_id = f"clip-{clip.get('id', index)}"
        parts.append(
            f'<section id="{clip_id}" class="clip" data-start="{at:g}" '
            f'data-duration="{hold:g}" data-track-index="{zi}" '
            f'style="z-index:{zi};">'
        )
        parts.append(f"<p style=\"{''.join(styles)}\">{text}</p>")
        parts.append("</section>")
    parts.append("</div>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _run(verb: str, request: dict, request_path: Path, result_path: Path) -> int:
    if request.get("schema_version") != 1:
        _error(result_path, "protocol", "unsupported request schema_version; expected 1")
        return 0
    output_name = request.get("output_name")
    if not isinstance(output_name, str) or not output_name.endswith(".mp4"):
        _error(result_path, "protocol", "output_name must be a .mp4 file name")
        return 0
    workspace = request_path.resolve().parent
    timeline_path = Path(request.get("timeline_path", ""))
    if not timeline_path.is_absolute():
        timeline_path = workspace / timeline_path
    try:
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _error(result_path, "protocol", f"cannot read timeline: {exc}")
        return 0

    if verb == "support":
        reasons = _support_reasons(timeline)
        _write(
            result_path,
            {
                "schema_version": 1,
                "supported": not reasons,
                "reasons": reasons,
                "features": {
                    "media": False,
                    "audio_mode": "none",
                    "bounded_css": True,
                    "hyperframes_pin": _HYPERFRAMES_PIN,
                },
                "alternatives": [],
                "backend": BACKEND_ID,
                "backend_version": _BACKEND_VERSION,
            },
        )
        return 0

    reasons = _support_reasons(timeline)
    if reasons:
        _error(
            result_path,
            "unsupported",
            "HyperFrames adapter does not support this timeline",
            recovery_command="use a text-only timeline with integer canvas fps",
            details={"reasons": reasons},
        )
        return 0
    if shutil.which("node") is None or shutil.which("ffmpeg") is None:
        _error(
            result_path,
            "binary_missing",
            "hyperframes requires node (>=22) and ffmpeg on PATH",
            recovery_command="install node 22+ and ffmpeg",
        )
        return 0

    width, height, fps = _canvas(timeline)
    assert width is not None and height is not None and fps is not None
    index_html = _compose_html(timeline, width=width, height=height, fps=fps)
    index_path = workspace / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    out_dir = workspace / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / output_name

    env = dict(os.environ)
    env.setdefault("NODE_OPTIONS", "--max-old-space-size=2048")
    completed = subprocess.run(
        [
            "npx",
            "--yes",
            f"hyperframes@{_HYPERFRAMES_PIN}",
            "render",
            str(workspace),
            "-c",
            "index.html",
            "-o",
            str(output_path),
            "--fps",
            str(fps),
            "--no-best-effort",
            "--strict",
        ],
        cwd=str(workspace),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if completed.returncode != 0 or not output_path.is_file():
        _error(
            result_path,
            "internal",
            f"hyperframes render failed (exit {completed.returncode})",
            recovery_command="rerun hyperframes render in the workspace and inspect its output",
            details={
                "stderr": completed.stderr[-2000:],
                "stdout": completed.stdout[-1000:],
            },
        )
        return 0

    frames = int(round(duration_frames(timeline, fps)))
    media = output_path.read_bytes()
    profile = dict(_PROFILE)
    profile["width"] = width
    profile["height"] = height
    profile["fps_rational"] = [fps, 1]
    profile["time_base"] = [1, _mp4_time_base(fps)]
    _write(
        result_path,
        {
            "schema_version": 1,
            "video": {
                "path": f"outputs/{output_name}",
                "profile": profile,
                "sha256": hashlib.sha256(media).hexdigest(),
                "duration_frames": frames,
                "audio": "none",
                "attachments": {},
            },
            "backend_fragments": {
                BACKEND_ID: {
                    "renderer": "hyperframes",
                    "hyperframes_pin": _HYPERFRAMES_PIN,
                    "composition": "astrid",
                    "fps": fps,
                }
            },
            "audio_ownership": "none",
            "normalization": [],
            "logs": [],
            "metadata": {},
        },
    )
    return 0


def _mp4_time_base(fps: int) -> int:
    """MP4 video timescale: double fps until >= 10000 (Astrid's rule)."""
    scale = fps
    while scale < 10000:
        scale *= 2
    return scale


def duration_frames(timeline: dict, fps: int) -> float:
    clips = timeline.get("clips") or []
    duration = max(
        (float(clip.get("at", 0) or 0) + _clip_duration(clip) for clip in clips),
        default=1.0,
    )
    return duration * fps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("verb", choices=["render", "support"])
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _error(args.result, "protocol", f"cannot read request: {exc}")
        return 0
    return _run(args.verb, request, args.request, args.result)


if __name__ == "__main__":
    raise SystemExit(main())
