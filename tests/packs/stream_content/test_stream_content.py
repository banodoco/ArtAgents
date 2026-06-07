from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _tiny_video(tmp_path: Path, duration: float = 2.0) -> Path:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is required for the synthetic stream_content video fixture")
    video = tmp_path / "testsrc.mp4"
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
            f"testsrc=duration={duration}:size=160x90:rate=2",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
    )
    return video


def test_segment_map_fuses_ocr_and_transcript_density(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astrid.packs.stream_content.executors.segment_map import core

    video = _tiny_video(tmp_path)
    transcript = _write_json(
        tmp_path / "transcript.json",
        {
            "segments": [
                {
                    "start": 1.1,
                    "end": 1.8,
                    "text": "Now the panel starts with the real content.",
                    "words": [
                        {"start": 1.1, "end": 1.2, "word": "Now"},
                        {"start": 1.25, "end": 1.38, "word": "the"},
                        {"start": 1.4, "end": 1.55, "word": "panel"},
                        {"start": 1.58, "end": 1.8, "word": "starts"},
                    ],
                }
            ]
        },
    )

    def fake_ocr(video_path: Path, work_dir: Path, *, sample_sec: float = 10.0) -> dict[str, object]:
        return {
            "video": str(video_path),
            "sample_sec": 1.0,
            "hits": [{"time": 0.0, "matched": ["STARTING SOON"], "text": "Starting Soon"}],
            "intervals": [{"start": 0.0, "end": 0.0, "matched": ["STARTING SOON"], "text": "Starting Soon"}],
        }

    monkeypatch.setattr(core, "sample_holding_screens", fake_ocr)
    payload = core.build_segment_map(video=video, transcript_path=transcript, ocr_work_dir=tmp_path / "ocr")

    assert payload["version"] == 1
    assert payload["duration"] == pytest.approx(2.0, abs=0.08)
    segments = payload["segments"]
    assert [segment["kind"] for segment in segments] == ["holding", "content"]
    assert segments[0]["start"] == 0.0
    assert segments[-1]["end"] == pytest.approx(payload["duration"], abs=0.08)
    for left, right in zip(segments, segments[1:]):
        assert left["end"] == right["start"]
    assert "Starting Soon" in segments[0]["label"]
    assert "panel starts" in segments[1]["label"]


def test_clip_candidates_scores_brief_matches_higher(tmp_path: Path) -> None:
    from astrid.packs.stream_content.executors.clip_candidates.scoring import build_candidates

    transcript = _write_json(
        tmp_path / "transcript.json",
        {
            "segments": [
                {
                    "start": 0.0,
                    "end": 24.0,
                    "speaker": "A",
                    "text": "The important thing is to remember why this format changed. It is a useful lesson.",
                },
                {
                    "start": 30.0,
                    "end": 58.0,
                    "speaker": "B",
                    "text": "The surprising truth is that latency costs shape every live demo decision. [applause]",
                },
            ]
        },
    )
    segment_map = _write_json(
        tmp_path / "segment_map.json",
        {
            "version": 1,
            "duration": 60.0,
            "segments": [
                {"start": 0.0, "end": 60.0, "kind": "content", "label": "Main panel", "confidence": 0.9, "signals": {}}
            ],
        },
    )
    brief = tmp_path / "brief.md"
    brief.write_text("Prioritize latency and live demo costs.", encoding="utf-8")

    payload = build_candidates(transcript=transcript, segment_map=segment_map, brief=brief)

    assert payload["version"] == 1
    assert len(payload["candidates"]) >= 2
    top = payload["candidates"][0]
    assert "latency costs" in top["text"]
    assert any(reason.startswith("brief_match:") for reason in top["reasons"])
    assert top["segment_label"] == "Main panel"


def test_distill_dry_run_emits_plan_shape(tmp_path: Path) -> None:
    video = _tiny_video(tmp_path)
    transcript = _write_json(
        tmp_path / "transcript.json",
        {"segments": [{"start": 0.1, "end": 1.5, "text": "A short synthetic transcript."}]},
    )
    out = tmp_path / "run"
    env = os.environ.copy()
    env["ASTRID_INTERNAL_INVOCATION"] = "1"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "astrid.packs.stream_content.orchestrators.distill.run",
            "--video",
            str(video),
            "--transcript",
            str(transcript),
            "--out",
            str(out),
            "--no-scenes",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["version"] == 2
    assert [step["id"] for step in plan["steps"]] == [
        "segment-map",
        "extract-segments",
        "clip-candidates",
        "review",
    ]
    assert all(step["adapter"] == "local" for step in plan["steps"])
    assert (out / "run.json").is_file()

