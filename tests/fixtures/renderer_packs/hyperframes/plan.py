#!/usr/bin/env python3
"""HyperFrames/Remotion hybrid planner (third-party pack, pure stdlib).

Usage: python3 plan.py plan|support --request <abs.json> --result <abs.json>

Occupancy tiling of a mixed timeline into non-overlapping frame windows:

* isolated text and SILENT-media clips -> ``hyperframes.renderer`` (the
  HyperFrames engine renders ``<video>`` clips natively with source
  trimming);
* audible media / effect / transition / mixed windows ->
  ``rendering.remotion``;
* the plan pins ``rendering.ffmpeg-finalizer``, which concatenates the
  segment videos (and synthesizes silent audio onto visual-only HyperFrames
  segments).

Deliberately NO text handles (unlike the characterized legacy planner):
a HyperFrames window covers exactly its clips' occupied frames, so adjacent
media never bleeds into a HyperFrames window.  Overlapping text-on-media is
not overlaid in v1 — the merged window stays on Remotion.

The planner is non-recursive: it emits a RenderPlan with explicit renderer
ids and the finalizer; the host service executes the segments.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BACKEND_ID = "hyperframes.planner"
_BACKEND_VERSION = "1.0.0"
HYPERFRAMES_ID = "hyperframes.renderer"
REMOTION_ID = "rendering.remotion"
FINALIZER_ID = "rendering.ffmpeg-finalizer"


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _error(result_path: Path, kind: str, message: str) -> None:
    _write(
        result_path,
        {
            "schema_version": 1,
            "kind": kind,
            "backend": BACKEND_ID,
            "message": message,
            "recovery_command": "use a timeline with at least one visual clip",
            "details": {},
        },
    )


def _canvas(timeline: dict) -> tuple[int, int, int] | None:
    overrides = timeline.get("theme_overrides") or {}
    visual = overrides.get("visual") or {}
    canvas = visual.get("canvas") or {}
    width, height, fps = canvas.get("width"), canvas.get("height"), canvas.get("fps")
    if not all(isinstance(v, int) and v > 0 for v in (width, height, fps)):
        return None
    return int(width), int(height), int(fps)


def _clip_end(clip: dict) -> float:
    at = float(clip.get("at", 0) or 0)
    if clip.get("clipType") == "media":
        to = clip.get("to")
        if isinstance(to, (int, float)):
            source_span = max(0.0, float(to) - float(clip.get("from", 0) or 0))
            speed = clip.get("speed")
            rate = float(speed) if isinstance(speed, (int, float)) and speed > 0 else 1.0
            return at + source_span / rate
        return at + 1.0
    hold = clip.get("hold")
    if isinstance(hold, (int, float)) and hold > 0:
        return at + float(hold)
    return at + 1.0


def _effective_gain(clip: dict, tracks: list) -> float:
    """Exact timeline gain (track muted/volume x clip volume), 0..1."""
    track_id = clip.get("track")
    track = next(
        (t for t in tracks if isinstance(t, dict) and t.get("id") == track_id),
        None,
    )
    if isinstance(track, dict) and track.get("muted") is True:
        return 0.0
    if isinstance(track, dict):
        track_volume = track.get("volume")
        track_gain = 1.0 if track_volume is None else float(track_volume)
    else:
        track_gain = 1.0
    clip_volume = clip.get("volume")
    clip_gain = 1.0 if clip_volume is None else float(clip_volume)
    return max(0.0, min(1.0, track_gain * clip_gain))


def _is_hyperframes_eligible(clip: dict, tracks: list) -> bool:
    """A clip is HyperFrames-eligible when it is plain text or SILENT media
    with no effects/transitions/opacity (the adapter's honest boundary)."""
    if clip.get("effects") or clip.get("transition"):
        return False
    if clip.get("opacity") not in (None, 1):
        return False
    clip_type = clip.get("clipType")
    if clip_type == "text":
        return True
    if clip_type == "media":
        return _effective_gain(clip, tracks) == 0
    return False


def _support_reasons(timeline: dict) -> list[str]:
    reasons: list[str] = []
    clips = timeline.get("clips") or []
    if not any(isinstance(c, dict) for c in clips):
        reasons.append("timeline has no clips")
    if _canvas(timeline) is None:
        reasons.append("canvas width/height/fps must be positive integers")
    return reasons


def _plan_payload(
    timeline: dict,
    fps: int,
    timeline_path: Path,
) -> dict:
    """Build a RenderPlan dict from occupancy tiling."""
    clips = [c for c in (timeline.get("clips") or []) if isinstance(c, dict)]
    width, height, rate = _canvas(timeline)
    assert width is not None and height is not None and rate is not None

    # Occupancy windows: merge overlapping clip frame ranges so windows are
    # non-overlapping, then classify each window by whether it contains any
    # clip that HyperFrames cannot render (audible media, effects,
    # transitions, opacity).
    tracks = timeline.get("tracks") or []
    events: list[tuple[int, int, bool]] = []
    for clip in clips:
        start_frame = int(round(float(clip.get("at", 0) or 0) * fps))
        end_frame = int(round(_clip_end(clip) * fps))
        end_frame = max(end_frame, start_frame + 1)
        events.append(
            (start_frame, end_frame, _is_hyperframes_eligible(clip, tracks))
        )
    total_frames = max((end for _start, end, _text in events), default=1)

    # Sweep: tile the timeline into non-overlapping windows.  A window is
    # "hyperframes" only when its ENTIRE occupied range is eligible (text or
    # silent media); anything touched by an ineligible clip (including an
    # eligible window that a later ineligible clip overlaps) stays on
    # remotion.  The last window always extends to total_frames so the plan
    # tiles exactly.
    occupied: list[tuple[int, int, bool]] = []
    for start, end, is_text in sorted(events, key=lambda e: (e[0], e[1])):
        start = max(start, 0)
        end = min(end, total_frames)
        if end <= start:
            continue
        if occupied and start < occupied[-1][1]:
            # Overlap: merge into the previous window; any ineligible
            # presence makes the merged window remotion.
            prev_start, prev_end, prev_text = occupied[-1]
            occupied[-1] = (
                prev_start,
                max(prev_end, end),
                prev_text and is_text,
            )
        else:
            occupied.append((start, end, is_text))

    # Remotion windows extend by the legacy handle (0.25 s) so transition
    # rendering fits — but never past the next occupied window (a later
    # HyperFrames window must not be swallowed).  Eligible windows stay
    # exact.  Windows tile in order and never exceed total_frames.
    handle_frames = int(round(0.25 * fps))
    windows: list[tuple[int, int, str]] = []
    cursor = 0
    for index, (start, end, is_text) in enumerate(occupied):
        if start > cursor:
            windows.append((cursor, start, "remotion"))  # gap -> remotion
        if is_text:
            windows.append((start, end, "hyperframes"))
            cursor = max(cursor, end)
        else:
            next_start = (
                occupied[index + 1][0] if index + 1 < len(occupied) else total_frames
            )
            padded = min(end + handle_frames, next_start)
            windows.append((start, max(padded, cursor + 1), "remotion"))
            cursor = max(cursor, padded)
    if cursor < total_frames:
        windows.append((cursor, total_frames, "remotion"))
    if not windows:
        windows = [(0, total_frames, "remotion")]

    segments: list[dict] = []
    reasons: dict[str, str] = {}
    for index, (start, end, kind) in enumerate(windows):
        renderer_id = HYPERFRAMES_ID if kind == "hyperframes" else REMOTION_ID
        segments.append(
            {
                "window": {
                    "start_frame": start,
                    "end_frame": end,
                    "fps_rational": [fps, 1],
                },
                "renderer": {
                    "id": renderer_id,
                    "source_pack": {
                        "id": "hyperframes" if kind == "hyperframes" else "rendering"
                    },
                    "manifest_digest": "0" * 64,
                    "alias_chain": [],
                    "override": None,
                    "support_decision": {
                        "schema_version": 1,
                        "supported": True,
                        "reasons": [],
                        "features": {"planned": True},
                        "alternatives": [],
                        "backend": renderer_id,
                        "backend_version": "1.0.0",
                    },
                    "trust_eligibility": {"eligible": True},
                },
                "input_hashes": {"timeline": "0" * 64},
            }
        )
        reasons[str(index)] = f"window [{start},{end}) -> {renderer_id}"

    return {
        "schema_version": 1,
        "request_digest": "0" * 64,
        "requested_policy": "hyper_remotion",
        "planner": {
            "id": BACKEND_ID,
            "source_pack": {"id": "hyperframes"},
            "manifest_digest": "0" * 64,
            "trust_eligibility": {"eligible": True},
            "alias_chain": [],
            "override": None,
            "support_decision": None,
        },
        "segments": segments,
        "finalizer": {
            "id": FINALIZER_ID,
            "source_pack": {"id": "rendering"},
            "manifest_digest": "0" * 64,
            "trust_eligibility": {"eligible": True},
            "alias_chain": [],
            "override": None,
            "support_decision": None,
        },
        "profile": {
            "width": width,
            "height": height,
            "fps_rational": [fps, 1],
            "time_base": [1, 15360],
            "container": "mp4",
            "video_codec": "h264",
            "video_profile": None,
            "video_level": None,
            "pixel_format": "yuv420p",
            "audio_codec": "aac",
            "audio_sample_rate": 48000,
            "audio_channel_layout": "stereo",
            "duration_tolerance": 1,
        },
        "total_frames": total_frames,
        "reasons": reasons,
        "window": None,
    }


def _run(verb: str, request: dict, request_path: Path, result_path: Path) -> int:
    if request.get("schema_version") != 1:
        _error(result_path, "protocol", "unsupported request schema_version; expected 1")
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
                    "occupancy_tiling": True,
                    "hyperframes_id": HYPERFRAMES_ID,
                    "remotion_id": REMOTION_ID,
                    "finalizer_id": FINALIZER_ID,
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
            "HyperFrames/Remotion hybrid planner does not support this timeline",
        )
        return 0
    _fps = _canvas(timeline)[2]
    plan = _plan_payload(timeline, _fps, timeline_path)
    _write(result_path, plan)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("verb", choices=["plan", "support"])
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
