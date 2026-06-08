from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from astrid.media import ffprobe_duration_seconds
from astrid.packs.editorial.executors.editor_review.run import (
    _probe_duration as editor_probe_duration,
)
from astrid.verify.checks import ffprobe_duration_seconds as checks_ffprobe_duration_seconds


def test_ffprobe_duration_seconds_uses_duration_only_probe() -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="12.5\n", stderr="")

    assert ffprobe_duration_seconds("clip.mp4", runner=runner) == 12.5

    cmd, kwargs = calls[0]
    assert cmd == [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        "clip.mp4",
    ]
    assert kwargs["check"] is True
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert "PATH" in kwargs["env"]
    assert "OPENAI_API_KEY" not in kwargs["env"]


def test_ffprobe_duration_seconds_accepts_explicit_env() -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="12.5\n", stderr="")

    assert (
        ffprobe_duration_seconds(
            "clip.mp4", runner=runner, env={"FFPROBE_DATADIR": "/tmp/ffprobe"}
        )
        == 12.5
    )

    assert calls[0][1]["env"]["FFPROBE_DATADIR"] == "/tmp/ffprobe"


def test_updated_duration_helpers_preserve_float_parsing(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"not-real-media")

    def fake_runner(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout="7.25\n", stderr="")

    assert ffprobe_duration_seconds(media, runner=fake_runner) == 7.25
    assert editor_probe_duration(media, ffprobe_runner=fake_runner) == 7.25


def test_verify_uses_canonical_media_helper() -> None:
    assert checks_ffprobe_duration_seconds is ffprobe_duration_seconds
