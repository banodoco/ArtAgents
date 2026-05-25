from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from astrid.core.util.media import ffprobe_duration_seconds
from astrid.packs.understanding.executors.audio_understand.run import _probe_duration as audio_probe_duration
from astrid.packs.editorial.executors.editor_review.run import _probe_duration as editor_probe_duration
from astrid.packs.understanding.executors.video_understand.run import _probe_duration as video_probe_duration


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
    assert kwargs == {"check": True, "capture_output": True, "text": True}


def test_updated_duration_helpers_preserve_float_parsing(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"not-real-media")

    def fake_runner(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout="7.25\n", stderr="")

    monkeypatch.setattr("astrid.packs.understanding.executors.audio_understand.run._run", fake_runner)
    monkeypatch.setattr("astrid.packs.understanding.executors.video_understand.run._run", fake_runner)

    assert audio_probe_duration(media) == 7.25
    assert video_probe_duration(media) == 7.25
    assert editor_probe_duration(media, ffprobe_runner=fake_runner) == 7.25
