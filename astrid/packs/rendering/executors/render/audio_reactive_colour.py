"""FFmpeg specialization for the audio-reactive-colour timeline element."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Sequence

EFFECT_ID = "audio-reactive-colour"
ADAPTER_ID = "audio-reactive-colour/v1"
_HEX_COLOUR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_ALLOWED_PARAM_KEYS = frozenset({"schemaVersion", "initialColor", "events"})
_ALLOWED_EVENT_KEYS = frozenset({"id", "frame", "color"})
_DISALLOWED_VISUAL_KEYS = frozenset(
    {
        "asset",
        "effects",
        "transition",
        "x",
        "y",
        "width",
        "height",
        "cropTop",
        "cropBottom",
        "cropLeft",
        "cropRight",
        "opacity",
    }
)


@dataclass(frozen=True)
class ColourEvent:
    frame: int
    color: str
    event_id: str | None = None


@dataclass(frozen=True)
class AudioReactiveColourSpec:
    width: int
    height: int
    fps: int
    total_frames: int
    initial_color: str
    events: tuple[ColourEvent, ...]
    audio_path: Path
    audio_from: float
    audio_to: float
    audio_volume: float

    @property
    def duration_seconds(self) -> float:
        return self.total_frames / self.fps

    @property
    def marker_sha256(self) -> str:
        payload = {
            "initialColor": self.initial_color,
            "events": [
                {"frame": event.frame, "color": event.color, "id": event.event_id}
                for event in self.events
            ],
        }
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    return float(value)


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _resolve_audio_path(
    entry: dict[str, Any], assets_path: Path, asset_id: str
) -> Path:
    if entry.get("url"):
        raise ValueError(
            f"{EFFECT_ID} FFmpeg specialization requires a local audio asset"
        )
    file_value = entry.get("file")
    if not isinstance(file_value, str) or not file_value:
        raise ValueError(f"Audio asset {asset_id!r} has no local file")
    path = Path(file_value)
    if not path.is_absolute():
        path = (assets_path.parent / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Audio asset missing: {path}")
    return path


def match_and_validate(
    timeline_data: dict[str, Any],
    registry: dict[str, Any],
    assets_path: Path,
) -> AudioReactiveColourSpec | None:
    """Return a strict whole-timeline spec, or None when the effect is absent."""
    clips = timeline_data.get("clips")
    tracks = timeline_data.get("tracks")
    if not isinstance(clips, list) or not isinstance(tracks, list):
        return None
    reactive = [
        clip
        for clip in clips
        if isinstance(clip, dict) and clip.get("clipType") == EFFECT_ID
    ]
    if not reactive:
        return None
    if len(reactive) != 1:
        raise ValueError(f"{EFFECT_ID} fast path requires exactly one effect clip")
    if len(clips) != 2:
        raise ValueError(
            f"{EFFECT_ID} fast path requires one effect clip and one audio clip"
        )

    track_by_id = {
        track.get("id"): track for track in tracks if isinstance(track, dict)
    }
    visual_tracks = [
        track for track in tracks if isinstance(track, dict) and track.get("kind") == "visual"
    ]
    audio_tracks = [
        track for track in tracks if isinstance(track, dict) and track.get("kind") == "audio"
    ]
    if len(visual_tracks) != 1 or len(audio_tracks) != 1:
        raise ValueError(
            f"{EFFECT_ID} fast path requires exactly one visual and one audio track"
        )

    effect_clip = reactive[0]
    if track_by_id.get(effect_clip.get("track"), {}).get("kind") != "visual":
        raise ValueError(f"{EFFECT_ID} clip must be on the visual track")
    if _number(effect_clip.get("at", 0), "Effect clip at") != 0:
        raise ValueError(f"{EFFECT_ID} clip must start at timeline zero")
    disallowed = sorted(_DISALLOWED_VISUAL_KEYS.intersection(effect_clip))
    if disallowed:
        raise ValueError(
            f"{EFFECT_ID} fast path does not support visual keys: {', '.join(disallowed)}"
        )
    hold = _number(effect_clip.get("hold"), "Effect clip hold")
    if hold <= 0:
        raise ValueError("Effect clip hold must be positive")

    canvas = (
        timeline_data.get("theme_overrides", {})
        .get("visual", {})
        .get("canvas", {})
    )
    width = _positive_integer(canvas.get("width"), "Canvas width")
    height = _positive_integer(canvas.get("height"), "Canvas height")
    fps = _positive_integer(canvas.get("fps"), "Canvas fps")
    total_frames_float = hold * fps
    total_frames = round(total_frames_float)
    if abs(total_frames_float - total_frames) > 1e-6:
        raise ValueError(
            f"{EFFECT_ID} hold must resolve to an integer number of frames"
        )

    params = effect_clip.get("params")
    if not isinstance(params, dict):
        raise ValueError(f"{EFFECT_ID} params must be an object")
    unexpected_params = sorted(set(params) - _ALLOWED_PARAM_KEYS)
    if unexpected_params:
        raise ValueError(
            f"Unexpected {EFFECT_ID} params: {', '.join(unexpected_params)}"
        )
    if params.get("schemaVersion", 1) != 1:
        raise ValueError(f"{EFFECT_ID} schemaVersion must be 1")
    initial_color = params.get("initialColor")
    if not isinstance(initial_color, str) or not _HEX_COLOUR.fullmatch(initial_color):
        raise ValueError("initialColor must be a six-digit hex colour")
    raw_events = params.get("events")
    if not isinstance(raw_events, list):
        raise ValueError("events must be an array")

    events: list[ColourEvent] = []
    previous_frame = 0
    for index, raw_event in enumerate(raw_events):
        if not isinstance(raw_event, dict):
            raise ValueError(f"events[{index}] must be an object")
        unexpected_event = sorted(set(raw_event) - _ALLOWED_EVENT_KEYS)
        if unexpected_event:
            raise ValueError(
                f"Unexpected events[{index}] keys: {', '.join(unexpected_event)}"
            )
        frame = raw_event.get("frame")
        if isinstance(frame, bool) or not isinstance(frame, int):
            raise ValueError(f"events[{index}].frame must be an integer")
        if frame <= previous_frame:
            raise ValueError("Event frames must be strictly increasing and positive")
        if frame >= total_frames:
            raise ValueError(
                f"events[{index}].frame must be below total frame count {total_frames}"
            )
        color = raw_event.get("color")
        if not isinstance(color, str) or not _HEX_COLOUR.fullmatch(color):
            raise ValueError(f"events[{index}].color must be a six-digit hex colour")
        event_id = raw_event.get("id")
        if event_id is not None and (
            not isinstance(event_id, str) or not event_id
        ):
            raise ValueError(f"events[{index}].id must be a non-empty string")
        events.append(
            ColourEvent(frame=frame, color=color.upper(), event_id=event_id)
        )
        previous_frame = frame

    audio_candidates = [clip for clip in clips if clip is not effect_clip]
    audio_clip = audio_candidates[0]
    if (
        not isinstance(audio_clip, dict)
        or audio_clip.get("clipType") != "media"
        or track_by_id.get(audio_clip.get("track"), {}).get("kind") != "audio"
    ):
        raise ValueError(f"{EFFECT_ID} fast path requires one audio media clip")
    if _number(audio_clip.get("at", 0), "Audio clip at") != 0:
        raise ValueError("Audio clip must start at timeline zero")
    if _number(audio_clip.get("speed", 1), "Audio clip speed") != 1:
        raise ValueError("Audio clip speed must be 1")
    if audio_clip.get("effects") or audio_clip.get("transition"):
        raise ValueError("Audio clip effects and transitions are not supported")
    audio_params = audio_clip.get("params")
    if isinstance(audio_params, dict) and (
        audio_params.get("fadeIn") or audio_params.get("fadeOut")
    ):
        raise ValueError("Audio fades are not supported by this fast path")
    audio_from = _number(audio_clip.get("from", 0), "Audio clip from")
    audio_to = _number(audio_clip.get("to"), "Audio clip to")
    if audio_from < 0 or audio_to <= audio_from:
        raise ValueError("Audio clip must have a positive source range")
    if round((audio_to - audio_from) * fps) != total_frames:
        raise ValueError(
            "Audio clip duration and effect hold must resolve to the same frame count"
        )
    audio_volume = _number(audio_clip.get("volume", 1), "Audio clip volume")
    if audio_volume < 0:
        raise ValueError("Audio clip volume must be non-negative")
    asset_id = audio_clip.get("asset")
    if not isinstance(asset_id, str) or not asset_id:
        raise ValueError("Audio clip must reference an asset")
    assets = registry.get("assets")
    if not isinstance(assets, dict) or asset_id not in assets:
        raise ValueError(f"Audio clip references unknown asset {asset_id!r}")
    entry = assets[asset_id]
    if not isinstance(entry, dict):
        raise ValueError(f"Audio asset {asset_id!r} must be an object")
    audio_path = _resolve_audio_path(entry, assets_path, asset_id)

    return AudioReactiveColourSpec(
        width=width,
        height=height,
        fps=fps,
        total_frames=total_frames,
        initial_color=initial_color.upper(),
        events=tuple(events),
        audio_path=audio_path,
        audio_from=audio_from,
        audio_to=audio_to,
        audio_volume=audio_volume,
    )


def write_sendcmd(spec: AudioReactiveColourSpec, path: Path) -> None:
    path.write_text(
        "".join(
            (
                f"{(event.frame - 1) / spec.fps:.9f} "
                f"drawbox@bg color 0x{event.color[1:]};\n"
            )
            for event in spec.events
        ),
        encoding="utf-8",
    )


def _escape_filter_path(path: Path) -> str:
    return (
        path.resolve()
        .as_posix()
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
    )


def build_video_command(
    spec: AudioReactiveColourSpec, sendcmd_path: Path, video_path: Path
) -> list[str]:
    initial = f"0x{spec.initial_color[1:]}"
    video_filters: list[str] = []
    if spec.events:
        video_filters.append(
            f"drawbox@bg=x=0:y=0:w=iw:h=ih:color={initial}:t=fill"
        )
        # sendcmd deliberately follows drawbox. A command delivered at the
        # previous frame then affects drawbox on the next frame, making a
        # semantic marker F visible at exactly F rather than F-1.
        video_filters.append(f"sendcmd=f='{_escape_filter_path(sendcmd_path)}'")
    video_filters.append("format=yuv420p")
    return [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-f",
        "lavfi",
        "-i",
        (
            f"color=c={initial}:s={spec.width}x{spec.height}:"
            f"r={spec.fps}:d={spec.duration_seconds:.9f}"
        ),
        "-vf",
        ",".join(video_filters),
        "-frames:v",
        str(spec.total_frames),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        str(video_path),
    ]


def build_mux_command(
    spec: AudioReactiveColourSpec, video_path: Path, out_path: Path
) -> list[str]:
    audio_filter = (
        f"atrim=start={spec.audio_from:.9f}:end={spec.audio_to:.9f},"
        "asetpts=PTS-STARTPTS,"
        "aformat=sample_rates=44100:channel_layouts=stereo,"
        f"volume={spec.audio_volume:.9f}"
    )
    return [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(spec.audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-af",
        audio_filter,
        "-shortest",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(out_path),
    ]


def render(
    spec: AudioReactiveColourSpec,
    out_path: Path,
    *,
    runner: Any = subprocess.run,
) -> Path:
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix="astrid-audio-reactive-colour-", dir=str(out_path.parent)
    ) as tmp_text:
        sendcmd_path = Path(tmp_text) / "colour.sendcmd"
        video_path = Path(tmp_text) / "colour-video.mp4"
        write_sendcmd(spec, sendcmd_path)
        # Keep the stateful sendcmd/drawbox graph video-only. Combining it with
        # an audio filter graph can cause FFmpeg to configure the graph twice,
        # leaking later drawbox state into early frames. A stream-copy mux pass
        # preserves the exact video frame sequence and remains very fast.
        runner(build_video_command(spec, sendcmd_path, video_path), check=True)
        runner(build_mux_command(spec, video_path, out_path), check=True)
    return out_path


def event_frames(spec: AudioReactiveColourSpec) -> Sequence[int]:
    return tuple(event.frame for event in spec.events)
