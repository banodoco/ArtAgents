from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from astrid.packs.builtin.orchestrators.dataset_build.caption_providers import (
    BudgetTracker,
    VideoUnderstandCaptionProvider,
    VisualUnderstandCaptionProvider,
    caption_candidate,
    caption_sidecar_path,
    get_caption_provider,
)


def _candidate(tmp_path: Path) -> dict[str, Any]:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"video")
    return {
        "source_type": "local_folder",
        "source_id": "clip-001",
        "source_url": media.as_uri(),
        "content_hash": "hash",
        "acquired_at": "2026-05-21T00:00:00Z",
        "media_type": "video",
        "media_path": str(media),
        "duration_s": 6.0,
        "clip_start_s": 1.0,
        "clip_end_s": 7.0,
        "scene_index": 0,
        "bucket": "bucket-a",
    }


def test_caption_provider_registry_exposes_understanding_wrappers() -> None:
    assert isinstance(get_caption_provider("visual_understand"), VisualUnderstandCaptionProvider)
    assert isinstance(get_caption_provider("video_understand"), VideoUnderstandCaptionProvider)
    with pytest.raises(ValueError, match="unknown caption provider"):
        get_caption_provider("bucket_judge")


def test_fixture_mode_uses_prebaked_sidecar_without_runner_or_budget(tmp_path: Path) -> None:
    item = _candidate(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    (fixture_dir / "clip-001.caption.json").write_text(
        json.dumps(
            {
                "text": "Prebaked fixture caption.",
                "schema_version": 1,
                "confidence": 0.98,
                "model": "fixture",
            }
        ),
        encoding="utf-8",
    )
    tracker = BudgetTracker(max_api_calls=0)

    def runner(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        raise AssertionError("fixture captioning must not call model runners")

    provider = VisualUnderstandCaptionProvider(runner=runner)
    result = provider.caption(
        item,
        {
            "fixture_mode": True,
            "fixture_caption_dir": str(fixture_dir),
            "out_dir": str(tmp_path / "captions"),
            "budget_tracker": tracker,
        },
    )

    sidecar = tmp_path / "captions" / "clip-001.caption.json"
    assert result.text == "Prebaked fixture caption."
    assert result.confidence == 0.98
    assert tracker.total_api_calls == 0
    assert json.loads(sidecar.read_text(encoding="utf-8"))["text"] == "Prebaked fixture caption."


def test_fixture_mode_falls_back_to_deterministic_caption_sidecar(tmp_path: Path) -> None:
    item = _candidate(tmp_path)
    result, sidecar = caption_candidate(
        item,
        {"provider": "visual_understand", "fixture_mode": True, "out_dir": str(tmp_path / "captions")},
    )

    assert result.text == "Fixture caption for clip-001."
    assert json.loads(sidecar.read_text(encoding="utf-8")) == {
        "confidence": 1.0,
        "model": "fixture",
        "raw_response": {"fixture": True},
        "schema_version": 1,
        "text": "Fixture caption for clip-001.",
    }


def test_visual_understand_wrapper_writes_sidecar_and_tracks_budget(tmp_path: Path) -> None:
    item = _candidate(tmp_path)
    schema_path = tmp_path / "caption.schema.json"
    schema_path.write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []
    tracker = BudgetTracker(max_api_calls=2, provider_limits={"caption.visual_understand": 1})

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        out = Path(cmd[cmd.index("--out") + 1])
        out.write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "model": "gpt-test",
                            "status": "ok",
                            "answer": "A concise visual caption.",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    provider = VisualUnderstandCaptionProvider(runner=runner)
    result = provider.caption(
        item,
        {
            "prompt_template": "Describe {clip_id} from {bucket}.",
            "schema_path": str(schema_path),
            "out_dir": str(tmp_path / "captions"),
            "budget_tracker": tracker,
        },
    )

    sidecar = tmp_path / "captions" / "clip-001.caption.json"
    assert result.text == "A concise visual caption."
    assert tracker.as_dict()["provider_calls"] == {"caption.visual_understand": 1}
    assert json.loads(sidecar.read_text(encoding="utf-8"))["model"] == "gpt-test"
    command = calls[0]
    assert "astrid.packs.builtin.executors.visual_understand.run" in command
    assert command[command.index("--query") + 1] == "Describe clip-001 from bucket-a."
    assert command[command.index("--at") + 1] == "3.000"
    assert command[command.index("--response-schema") + 1] == str(schema_path)
    sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sidecar_payload["hashes"]["prompt_hash"]
    assert sidecar_payload["hashes"]["media_hash"] == item["content_hash"]


def test_visual_understand_wrapper_reuses_only_matching_hashed_sidecar(tmp_path: Path) -> None:
    item = _candidate(tmp_path)
    calls: list[list[str]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        out = Path(cmd[cmd.index("--out") + 1])
        out.write_text(json.dumps({"text": "Fresh caption.", "model": "gpt-test"}), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    provider = VisualUnderstandCaptionProvider(runner=runner)
    config = {
        "provider": "visual_understand",
        "prompt_template": "Describe {clip_id}.",
        "out_dir": str(tmp_path / "captions"),
        "budget_tracker": BudgetTracker(max_api_calls=2),
    }

    first = provider.caption(item, config)
    second = provider.caption(item, config)
    changed = provider.caption(item, {**config, "prompt_template": "Changed {clip_id}."})

    assert first.text == "Fresh caption."
    assert second.text == "Fresh caption."
    assert changed.text == "Fresh caption."
    assert len(calls) == 2


def test_visual_understand_wrapper_rejects_unhashed_production_sidecar(tmp_path: Path) -> None:
    item = _candidate(tmp_path)
    sidecar = tmp_path / "captions" / "clip-001.caption.json"
    sidecar.parent.mkdir()
    sidecar.write_text(json.dumps({"text": "Stale raw caption.", "model": "fixture"}), encoding="utf-8")
    calls: list[list[str]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        out = Path(cmd[cmd.index("--out") + 1])
        out.write_text(json.dumps({"text": "Fresh production caption.", "model": "gpt-test"}), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    result = VisualUnderstandCaptionProvider(runner=runner).caption(
        item,
        {"prompt_template": "Describe {clip_id}.", "out_dir": str(tmp_path / "captions")},
    )

    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert result.text == "Fresh production caption."
    assert len(calls) == 1
    assert payload["text"] == "Fresh production caption."
    assert payload["hashes"]["prompt_hash"]


def test_video_understand_wrapper_uses_video_runner_and_stays_bucket_judge_independent(tmp_path: Path) -> None:
    item = _candidate(tmp_path)
    calls: list[list[str]] = []
    tracker = BudgetTracker(max_api_calls=3)

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "results": [
                        {
                            "model": "gemini-test",
                            "status": "ok",
                            "answer": {"summary": "A synchronized audio-video caption.", "highlight_score": 7},
                        }
                    ]
                }
            ),
            stderr="",
        )

    result, sidecar = caption_candidate(
        item,
        {
            "provider": "video_understand",
            "prompt_template": "Caption only.",
            "out_dir": str(tmp_path / "captions"),
            "budget_tracker": tracker,
            "extensions": {"bucket_judge": {"enabled": True, "provider": "visual_understand"}},
        },
        runner=runner,
    )

    command = calls[0]
    assert result.text == "A synchronized audio-video caption."
    assert "astrid.packs.builtin.executors.video_understand.run" in command
    assert command[command.index("--start") + 1] == "1.000"
    assert command[command.index("--end") + 1] == "7.000"
    assert "bucket_judge" not in " ".join(command)
    assert tracker.provider_calls == {"caption.video_understand": 1}
    assert caption_sidecar_path(item, {"out_dir": str(tmp_path / "captions")}) == sidecar


def test_budget_tracker_rejects_caption_calls_over_limit(tmp_path: Path) -> None:
    item = _candidate(tmp_path)
    tracker = BudgetTracker(max_api_calls=0)

    def runner(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        raise AssertionError("budget failure must happen before model runner execution")

    provider = VideoUnderstandCaptionProvider(runner=runner)
    with pytest.raises(RuntimeError, match="API budget exceeded"):
        provider.caption(item, {"out_dir": str(tmp_path / "captions"), "budget_tracker": tracker})


def test_budget_tracker_reexport_tracks_provider_limits_and_observed_calls() -> None:
    tracker = BudgetTracker(max_api_calls=2, provider_limits={"caption.visual_understand": 1})

    tracker.increment("caption.visual_understand")

    assert tracker.as_dict()["observed_calls_by_provider"] == {"caption.visual_understand": 1}
    with pytest.raises(RuntimeError, match="caption.visual_understand"):
        tracker.increment("caption.visual_understand")


def test_budget_tracker_enforces_rate_limit_with_injected_clock_sleep() -> None:
    now = 100.0
    sleeps: list[float] = []

    def clock() -> float:
        return now

    def sleep(duration: float) -> None:
        nonlocal now
        sleeps.append(duration)
        now += duration

    tracker = BudgetTracker.from_config(
        {
            "budgets": {
                "max_api_calls": 2,
                "providers": {"caption.visual_understand": {"rate_limit_per_minute": 60}},
            }
        },
        clock=clock,
        sleep=sleep,
    )

    tracker.increment("caption.visual_understand")
    tracker.increment("caption.visual_understand")

    assert sleeps == [1.0]
    assert tracker.as_dict()["provider_rate_limits"] == {"caption.visual_understand": 60}
