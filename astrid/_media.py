"""Small media-probing helpers.

This is the canonical location for shared media utilities.
Any callers outside ``astrid/core/`` should import from here.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Callable

Runner = Callable[..., subprocess.CompletedProcess[str]]


def ffprobe_duration_seconds(
    media_path: str | Path,
    *,
    runner: Runner = subprocess.run,
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
        text=True,
    )
    return float(str(result.stdout).strip())
