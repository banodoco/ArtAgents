from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from astrid.core.media import (
    MediaProbe,
    ffprobe_duration_seconds,
    ffprobe_metadata,
)
from astrid.packs.editorial.executors.editor_review.run import (
    _probe_duration as editor_probe_duration,
)
from astrid.core.verify.checks import ffprobe_duration_seconds as checks_ffprobe_duration_seconds


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


# ---------------------------------------------------------------------------
# MediaProbe and ffprobe_metadata tests (mocked subprocess, no real ffprobe)
# ---------------------------------------------------------------------------


HAPPY_FFPROBE_JSON = json.dumps(
    {
        "format": {"duration": "12.5"},
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "30000/1001",
            }
        ],
    }
)


class TestMediaProbeDefaults:
    """MediaProbe dataclass starts with all-None and _raw empty."""

    def test_default_all_none(self) -> None:
        probe = MediaProbe()
        assert probe.duration_seconds is None
        assert probe.fps is None
        assert probe.resolution is None
        assert probe.width is None
        assert probe.height is None
        assert probe._raw == {}

    def test_partial_construction(self) -> None:
        probe = MediaProbe(
            duration_seconds=5.0,
            width=640,
            height=480,
            resolution="640x480",
        )
        assert probe.duration_seconds == 5.0
        assert probe.fps is None
        assert probe.resolution == "640x480"
        assert probe.width == 640
        assert probe.height == 480


class TestFfprobeMetadataHappy:
    """ffprobe_metadata extracts all fields from valid JSON output."""

    def test_extracts_all_fields(self) -> None:
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=HAPPY_FFPROBE_JSON, stderr=""
            )
            probe = ffprobe_metadata("video.mp4")

        assert probe.duration_seconds == pytest.approx(12.5)
        assert probe.fps == pytest.approx(30000 / 1001)
        assert probe.resolution == "1920x1080"
        assert probe.width == 1920
        assert probe.height == 1080
        assert probe._raw  # raw JSON preserved

    def test_accepts_path_object(self, tmp_path: Path) -> None:
        vid = tmp_path / "clip.mp4"
        vid.write_bytes(b"dummy")
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=HAPPY_FFPROBE_JSON, stderr=""
            )
            probe = ffprobe_metadata(vid)

        assert probe.duration_seconds == pytest.approx(12.5)


class TestFfprobeMetadataDegraded:
    """ffprobe_metadata returns all-None MediaProbe on errors / missing ffprobe."""

    def test_no_ffprobe_on_path(self) -> None:
        with patch("shutil.which", return_value=None):
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds is None
        assert probe.fps is None
        assert probe.resolution is None
        assert probe._raw == {}

    def test_nonzero_returncode(self) -> None:
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 1, stdout="", stderr="error"
            )
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds is None

    def test_invalid_json(self) -> None:
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout="not json", stderr=""
            )
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds is None

    def test_timeout(self) -> None:
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=[], timeout=1.0)
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds is None

    def test_oserror(self) -> None:
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.side_effect = OSError("bad things")
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds is None

    def test_missing_format_block(self) -> None:
        no_fmt = json.dumps({"streams": []})
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=no_fmt, stderr=""
            )
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds is None

    def test_non_numeric_duration(self) -> None:
        bad_dur = json.dumps(
            {"format": {"duration": "nope"}, "streams": []}
        )
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=bad_dur, stderr=""
            )
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds is None

    def test_no_video_stream(self) -> None:
        no_video = json.dumps(
            {
                "format": {"duration": "3.0"},
                "streams": [{"codec_type": "audio"}],
            }
        )
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=no_video, stderr=""
            )
            probe = ffprobe_metadata("audio.aac")
        assert probe.duration_seconds == 3.0
        assert probe.fps is None
        assert probe.resolution is None

    def test_division_by_zero_fps(self) -> None:
        zero_den = json.dumps(
            {
                "format": {"duration": "1.0"},
                "streams": [
                    {
                        "codec_type": "video",
                        "width": 100,
                        "height": 100,
                        "r_frame_rate": "30/0",
                    }
                ],
            }
        )
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=zero_den, stderr=""
            )
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds == 1.0
        assert probe.resolution == "100x100"
        assert probe.fps is None  # division by zero swallowed
