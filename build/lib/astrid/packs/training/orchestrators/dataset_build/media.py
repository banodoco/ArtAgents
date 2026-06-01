"""Media probing and clipping helpers for ``training.dataset_build``."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable


Runner = Callable[..., subprocess.CompletedProcess[str]]


def ffprobe_metadata(path: str | Path, *, runner: Runner = subprocess.run) -> dict[str, Any]:
    media_path = Path(path)
    proc = runner(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(media_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout or "{}")
    return _metadata_from_ffprobe(data)


def extract_clip_ffmpeg(
    source: str | Path,
    *,
    start_s: float,
    end_s: float,
    out_path: str | Path,
    runner: Runner = subprocess.run,
) -> Path:
    if end_s <= start_s:
        raise ValueError("end_s must be greater than start_s")
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    duration = end_s - start_s
    runner(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_s:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(target),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return target


def _metadata_from_ffprobe(data: MappingLike) -> dict[str, Any]:
    streams = data.get("streams") if isinstance(data, dict) else []
    video_stream = next(
        (stream for stream in streams or [] if isinstance(stream, dict) and stream.get("codec_type") == "video"),
        {},
    )
    format_data = data.get("format", {}) if isinstance(data, dict) else {}
    duration = _float_or_none(video_stream.get("duration")) or _float_or_none(format_data.get("duration"))
    width = _int_or_none(video_stream.get("width"))
    height = _int_or_none(video_stream.get("height"))
    fps = _fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))
    metadata: dict[str, Any] = {}
    if duration is not None:
        metadata["duration_s"] = duration
    if width is not None and height is not None:
        metadata["resolution"] = {"width": width, "height": height}
    if fps is not None:
        metadata["fps"] = fps
    if video_stream.get("codec_name"):
        metadata["codec"] = video_stream["codec_name"]
    if _int_or_none(format_data.get("size")) is not None:
        metadata["file_size_bytes"] = int(format_data["size"])
    return metadata


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _fps(value: object) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    if "/" not in value:
        return _float_or_none(value)
    numerator_text, denominator_text = value.split("/", 1)
    numerator = _float_or_none(numerator_text)
    denominator = _float_or_none(denominator_text)
    if numerator is None or denominator in {None, 0}:
        return None
    return numerator / denominator


MappingLike = dict[str, Any]

