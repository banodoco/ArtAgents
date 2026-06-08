"""Canonical shared media-probing helpers.

This is the canonical location for shared media utilities.
Any callers outside ``astrid/core/`` should import from here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from astrid.core.subprocess_env import build_child_subprocess_env

Runner = Callable[..., subprocess.CompletedProcess[str]]


# ---------------------------------------------------------------------------
# MediaProbe – structured ffprobe metadata
# ---------------------------------------------------------------------------


@dataclass
class MediaProbe:
    """Best-effort media metadata extracted via ffprobe.

    All fields are ``None`` when ffprobe is unavailable or fails.
    """

    duration_seconds: float | None = None
    fps: float | None = None
    resolution: str | None = None
    width: int | None = None
    height: int | None = None

    _raw: dict[str, Any] = field(default_factory=dict, repr=False)


def ffprobe_metadata(
    file_path: str | Path,
    *,
    timeout: float = 30.0,
) -> MediaProbe:
    """Extract duration, fps, resolution, width, and height via ffprobe.

    Returns a :class:`MediaProbe` with best-effort fields populated.
    If ffprobe is not available or fails, all fields are ``None``.
    """
    probe = MediaProbe()
    ffprobe_exe = shutil.which("ffprobe")
    if ffprobe_exe is None:
        return probe

    try:
        proc = subprocess.run(
            [
                ffprobe_exe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            return probe
        data: dict[str, Any] = json.loads(proc.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
        return probe

    probe._raw = data

    # Duration from format
    fmt = data.get("format", {})
    dur_str = fmt.get("duration")
    if dur_str is not None:
        try:
            probe.duration_seconds = float(dur_str)
        except (ValueError, TypeError):
            pass

    # Resolution, width, height, and FPS from first video stream
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            w = stream.get("width")
            h = stream.get("height")
            if w is not None and h is not None:
                try:
                    probe.width = int(w)
                    probe.height = int(h)
                except (ValueError, TypeError):
                    pass
                else:
                    probe.resolution = f"{probe.width}x{probe.height}"

            fps_str = stream.get("r_frame_rate")
            if fps_str and "/" in str(fps_str):
                try:
                    num, den = str(fps_str).split("/", 1)
                    probe.fps = float(num) / float(den)
                except (ValueError, ZeroDivisionError):
                    pass
            break

    return probe


# ---------------------------------------------------------------------------
# Narrow duration probe (preserved for callers who only need seconds)
# ---------------------------------------------------------------------------


def ffprobe_duration_seconds(
    media_path: str | Path,
    *,
    runner: Runner = subprocess.run,
    env: Mapping[str, str] | None = None,
) -> float:
    """Return format duration in seconds using the narrow ffprobe duration probe."""

    result = runner(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ],
        check=True,
        capture_output=True,
        env=build_child_subprocess_env(explicit_env=env or {}),
        text=True,
    )
    return float(str(result.stdout).strip())
