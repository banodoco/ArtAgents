from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.packs.understanding.executors.understand import run as understand
from astrid.packs.understanding.executors.video_understand.run import main


def _write_test_video(path: Path, *, duration: float = 1.2) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is required for video understanding tests")
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=160x90:rate=10:duration={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
    )


def test_video_understand_extracts_window_dry_run(capsys, tmp_path):
    video = tmp_path / "source.mp4"
    _write_test_video(video)

    code = main(
        [
            "--video",
            str(video),
            "--at",
            "0.6",
            "--window-sec",
            "0.6",
            "--out-dir",
            str(tmp_path / "out"),
            "--dry-run",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["provider"] == "gemini"
    assert payload["models"] == ["gemini-2.5-flash"]
    assert payload["source_kind"] == "video"
    assert len(payload["windows"]) == 1
    assert Path(payload["windows"][0]["path"]).is_file()


def test_video_understand_best_mode_dry_run(capsys, tmp_path):
    video = tmp_path / "source.mp4"
    _write_test_video(video)

    code = main(["--video", str(video), "--mode", "best", "--out-dir", str(tmp_path / "out"), "--dry-run"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["models"] == ["gemini-2.5-pro"]


def test_understand_dispatches_video(monkeypatch):
    captured = {}

    def fake_video_main(argv):
        captured["argv"] = argv
        return 17

    monkeypatch.setitem(understand.ALIASES, "video", fake_video_main)

    assert understand.main(["--mode", "video", "--video", "source.mp4", "--dry-run"]) == 17
    assert captured["argv"] == ["--video", "source.mp4", "--dry-run"]


def test_video_understand_writes_universal_result_manifest(capsys, tmp_path):
    video = tmp_path / "source.mp4"
    _write_test_video(video)
    out_dir = tmp_path / "out"
    out_path = out_dir / "result.json"

    class _FakeGeminiClient:
        def describe_video(self, **kwargs):
            return {
                "summary": "One short window with synthetic bars and tone.",
                "model": kwargs["model"],
            }

    with patch(
        "astrid.packs.understanding.executors.video_understand.run.build_gemini_client",
        return_value=_FakeGeminiClient(),
    ):
        code = main(
            [
                "--video",
                str(video),
                "--at",
                "0.6",
                "--window-sec",
                "0.6",
                "--out-dir",
                str(out_dir),
                "--out",
                str(out_path),
            ]
        )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert out_path.is_file()
    assert payload["manifest_path"] == str(manifest_path)
    assert payload["kind"] == "understanding.video_understand"
    assert manifest["kind"] == "understanding.video_understand"
    assert manifest["inputs"]["video"] == str(video)
    assert manifest["outputs"][-1]["path"] == str(out_path)
    assert manifest["outputs"][-1]["type"] == "file"
    assert "content_hash" in manifest["outputs"][-1]
    assert any(Path(item["path"]).suffix == ".mp4" for item in manifest["outputs"])
