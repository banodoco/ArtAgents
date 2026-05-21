from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from astrid.packs.builtin.dataset_build.caption_providers import BudgetTracker
from astrid.packs.builtin.dataset_build.filter_stages import (
    BlackFrameFilter,
    BucketJudgeGate,
    ContentHashFilter,
    DurationFilter,
    ResolutionFilter,
    RightsFilter,
    SourceCapFilter,
    get_filter_stage,
    judge_sidecar_path,
)


def _item(tmp_path: Path, item_id: str, *, duration_s: float = 5.0) -> dict[str, Any]:
    media = tmp_path / f"{item_id}.mp4"
    media.write_bytes(b"video")
    return {
        "item_id": item_id,
        "source_type": "local_folder",
        "source_id": item_id,
        "source_url": media.as_uri(),
        "content_hash": "a" * 64,
        "acquired_at": "2026-05-21T00:00:00Z",
        "media_type": "video",
        "media_path": str(media),
        "duration_s": duration_s,
        "clip_start_s": 1.0,
        "clip_end_s": 1.0 + duration_s,
        "review_status": "pending",
    }


def _assert_filter_stats_schema(stats: dict[str, Any]) -> None:
    schema = json.loads(Path("astrid/packs/builtin/dataset_build/schemas/filter-stats.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(stats)


def test_filter_stage_registry_dispatches_known_stages() -> None:
    assert isinstance(get_filter_stage("duration_filter"), DurationFilter)
    assert isinstance(get_filter_stage("resolution_filter"), ResolutionFilter)
    assert isinstance(get_filter_stage("black_frame_filter"), BlackFrameFilter)
    assert isinstance(get_filter_stage("content_hash_filter"), ContentHashFilter)
    assert isinstance(get_filter_stage("source_cap_filter"), SourceCapFilter)
    assert isinstance(get_filter_stage("rights_filter"), RightsFilter)
    assert isinstance(get_filter_stage("bucket_judge_filter"), BucketJudgeGate)
    with pytest.raises(ValueError, match="unknown filter stage"):
        get_filter_stage("caption_filter")


def test_duration_filter_is_deterministic_and_writes_results_and_stats(tmp_path: Path) -> None:
    items = [
        _item(tmp_path, "short", duration_s=1.0),
        _item(tmp_path, "ok", duration_s=4.0),
        _item(tmp_path, "long", duration_s=9.0),
    ]

    result = DurationFilter().apply(items, {}, {"min_s": 2.0, "max_s": 5.0})

    assert [item["item_id"] for item in result.passed] == ["ok"]
    assert [item["item_id"] for item in result.rejected] == ["short", "long"]
    assert result.passed[0]["filter_results"]["duration_filter"] == {"passed": True, "reason": "", "score": 4.0}
    assert result.rejected[0]["filter_results"]["duration_filter"]["reason"] == "duration_too_short"
    assert result.rejected[1]["filter_results"]["duration_filter"]["reason"] == "duration_too_long"
    assert result.stats["items_in"] == 3
    assert result.stats["items_passed"] == 1
    assert result.stats["items_rejected"] == 2
    assert result.stats["rejection_reasons"] == {"duration_too_short": 1, "duration_too_long": 1}
    _assert_filter_stats_schema(result.stats)


def test_resolution_filter_rejects_small_media_and_warns_on_missing_metadata(tmp_path: Path) -> None:
    small = _item(tmp_path, "small")
    small["source_metadata"] = {"resolution": {"width": 640, "height": 360}}
    ok = _item(tmp_path, "ok")
    ok["source_metadata"] = {"resolution": {"width": 1920, "height": 1080}}
    missing = _item(tmp_path, "missing")

    result = ResolutionFilter().apply([small, ok, missing], {}, {"min_width": 1280, "min_height": 720})

    assert [item["item_id"] for item in result.passed] == ["ok", "missing"]
    assert result.passed[1]["filter_results"]["resolution_filter"]["reason"] == "missing_resolution"
    assert [item["item_id"] for item in result.rejected] == ["small"]
    assert result.rejected[0]["review_status"] == "rejected"
    assert result.rejected[0]["filter_results"]["resolution_filter"]["reason"] == "resolution_too_small"
    assert result.stats["warnings"] == ["missing_resolution"]
    _assert_filter_stats_schema(result.stats)


def test_resolution_filter_can_require_metadata(tmp_path: Path) -> None:
    missing = _item(tmp_path, "missing")

    result = ResolutionFilter().apply([missing], {}, {"require_metadata": True})

    assert result.passed == []
    assert result.rejected[0]["filter_results"]["resolution_filter"]["reason"] == "missing_resolution"
    assert result.rejected[0]["review_status"] == "rejected"
    assert result.stats["rejection_reasons"] == {"missing_resolution": 1}
    _assert_filter_stats_schema(result.stats)


def test_black_frame_filter_is_metadata_only_by_default_and_warns_on_missing_metadata(tmp_path: Path) -> None:
    blank = _item(tmp_path, "blank")
    blank["source_metadata"] = {"blank_frame_ratio": 0.98}
    ok = _item(tmp_path, "ok")
    ok["source_metadata"] = {"black_frame_ratio": 0.12}
    missing = _item(tmp_path, "missing")
    calls: list[list[str]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="black_duration:5.0")

    result = BlackFrameFilter(runner=runner).apply([blank, ok, missing], {}, {})

    assert calls == []
    assert [item["item_id"] for item in result.passed] == ["ok", "missing"]
    assert result.passed[1]["filter_results"]["black_frame_filter"]["reason"] == "missing_black_frame_metadata"
    assert [item["item_id"] for item in result.rejected] == ["blank"]
    assert result.rejected[0]["review_status"] == "rejected"
    assert result.rejected[0]["filter_results"]["black_frame_filter"]["score"] == 0.98
    assert result.stats["rejection_reasons"] == {"black_frame_ratio_too_high": 1}
    assert result.stats["warnings"] == ["missing_black_frame_metadata"]
    _assert_filter_stats_schema(result.stats)


def test_black_frame_filter_uses_injected_probe_only_when_enabled(tmp_path: Path) -> None:
    item = _item(tmp_path, "probe", duration_s=10.0)
    calls: list[list[str]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="black_duration:4.0\nblack_duration:6.0")

    result = BlackFrameFilter(runner=runner).apply([item], {}, {"probe_media": True})

    assert len(calls) == 1
    assert calls[0][0] == "ffmpeg"
    assert result.passed == []
    assert result.rejected[0]["item_id"] == "probe"
    assert result.rejected[0]["filter_results"]["black_frame_filter"] == {
        "passed": False,
        "reason": "black_frame_ratio_too_high",
        "score": 1.0,
    }
    _assert_filter_stats_schema(result.stats)


def test_content_hash_filter_rejects_later_duplicates_without_counting_rejections_as_kept(tmp_path: Path) -> None:
    first = _item(tmp_path, "first")
    first["content_hash"] = "1" * 64
    duplicate = _item(tmp_path, "duplicate")
    duplicate["content_hash"] = "1" * 64
    unique = _item(tmp_path, "unique")
    unique["content_hash"] = "2" * 64

    result = ContentHashFilter().apply([first, duplicate, unique], {}, {})

    assert [item["item_id"] for item in result.passed] == ["first", "unique"]
    assert [item["item_id"] for item in result.rejected] == ["duplicate"]
    duplicate_result = result.rejected[0]["filter_results"]["content_hash_filter"]
    assert duplicate_result["reason"] == "duplicate_content_hash"
    assert duplicate_result["duplicate_of_item_id"] == "first"
    assert duplicate_result["duplicate_of_source_id"] == "first"
    assert result.rejected[0]["review_status"] == "rejected"
    assert result.stats["rejection_reasons"] == {"duplicate_content_hash": 1}
    _assert_filter_stats_schema(result.stats)


def test_source_cap_filter_uses_youtube_derived_source_identity_and_preserves_order(tmp_path: Path) -> None:
    clip_a = _item(tmp_path, "clip-a")
    clip_a.update({"source_type": "youtube", "source_id": "clip-a", "derived_from": {"source_id": "video-123", "source_type": "youtube"}})
    clip_b = _item(tmp_path, "clip-b")
    clip_b.update({"source_type": "youtube", "source_id": "clip-b", "derived_from": {"source_id": "video-123", "source_type": "youtube"}})
    clip_c = _item(tmp_path, "clip-c")
    clip_c.update({"source_type": "youtube", "source_id": "clip-c", "derived_from": {"source_id": "video-456", "source_type": "youtube"}})

    result = SourceCapFilter().apply([clip_a, clip_b, clip_c], {}, {"max_per_source": 1})

    assert [item["item_id"] for item in result.passed] == ["clip-a", "clip-c"]
    assert [item["item_id"] for item in result.rejected] == ["clip-b"]
    assert result.rejected[0]["filter_results"]["source_cap_filter"]["reason"] == "source_cap_exceeded"
    assert result.rejected[0]["review_status"] == "rejected"
    assert result.stats["rejection_reasons"] == {"source_cap_exceeded": 1}
    _assert_filter_stats_schema(result.stats)


def test_source_cap_filter_reads_legacy_clip_config_max_scenes_per_source(tmp_path: Path) -> None:
    first = _item(tmp_path, "first")
    second = _item(tmp_path, "second")
    second["source_id"] = "first"

    result = SourceCapFilter().apply([first, second], {}, {"clip_config": {"max_scenes_per_source": 1}})

    assert [item["item_id"] for item in result.passed] == ["first"]
    assert [item["item_id"] for item in result.rejected] == ["second"]
    _assert_filter_stats_schema(result.stats)


def test_rights_filter_rejects_restricted_statuses_and_warns_on_unknown_rights(tmp_path: Path) -> None:
    verified = _item(tmp_path, "verified")
    verified["rights"] = {"rights_status": "verified", "license": "cc0"}
    unknown = _item(tmp_path, "unknown")
    unknown["rights"] = {"rights_status": "unknown", "license": "unknown"}
    restricted = _item(tmp_path, "restricted")
    restricted["rights"] = {"rights_status": "restricted", "license": "unknown"}
    prohibited = _item(tmp_path, "prohibited")
    prohibited["rights"] = {"rights_status": "prohibited", "license": "unknown"}

    result = RightsFilter().apply([verified, unknown, restricted, prohibited], {}, {})

    assert [item["item_id"] for item in result.passed] == ["verified", "unknown"]
    assert result.passed[1]["filter_results"]["rights_filter"]["reason"] == "unknown_rights"
    assert [item["item_id"] for item in result.rejected] == ["restricted", "prohibited"]
    assert [item["review_status"] for item in result.rejected] == ["rejected", "rejected"]
    assert result.stats["rejection_reasons"] == {"rights_status_restricted": 2}
    assert result.stats["warnings"] == ["unknown_rights"]
    _assert_filter_stats_schema(result.stats)


def test_rights_filter_rejects_configured_restricted_licenses(tmp_path: Path) -> None:
    item = _item(tmp_path, "licensed")
    item["rights"] = {"rights_status": "verified", "license": "editorial-only"}

    result = RightsFilter().apply([item], {}, {"restricted_licenses": ["editorial-only"]})

    assert result.passed == []
    assert result.rejected[0]["filter_results"]["rights_filter"]["reason"] == "license_restricted"
    assert result.rejected[0]["review_status"] == "rejected"
    assert result.stats["rejection_reasons"] == {"license_restricted": 1}
    _assert_filter_stats_schema(result.stats)


def test_bucket_judge_disabled_passes_items_without_captioning(tmp_path: Path) -> None:
    item = _item(tmp_path, "clip-a")
    result = BucketJudgeGate().apply([item], {"buckets": {"wide": 1}}, {"enabled": False})

    assert result.rejected == []
    assert result.passed[0]["item_id"] == "clip-a"
    assert "caption" not in result.passed[0]
    assert result.passed[0]["filter_results"]["bucket_judge_filter"]["reason"] == "disabled"
    _assert_filter_stats_schema(result.stats)


def test_bucket_judge_fixture_sidecars_classify_and_reject_before_captioning(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "judges"
    fixture_dir.mkdir()
    (fixture_dir / "clip-a.judge.json").write_text(
        json.dumps({"accept": True, "bucket": "wide", "reason": "matches", "score": 0.91}),
        encoding="utf-8",
    )
    (fixture_dir / "clip-b.judge.json").write_text(
        json.dumps({"accept": False, "bucket": None, "reason": "off_topic", "score": 0.12}),
        encoding="utf-8",
    )

    result = BucketJudgeGate().apply(
        [_item(tmp_path, "clip-a"), _item(tmp_path, "clip-b")],
        {},
        {
            "enabled": True,
            "fixture_mode": True,
            "fixture_judge_dir": str(fixture_dir),
            "out_dir": str(tmp_path / "out"),
            "buckets": {"wide": {"target_count": 1}},
        },
    )

    assert [item["item_id"] for item in result.passed] == ["clip-a"]
    assert result.passed[0]["bucket"] == "wide"
    assert result.passed[0]["filter_results"]["bucket_judge_filter"] == {"passed": True, "reason": "matches", "score": 0.91}
    assert "caption" not in result.passed[0]
    assert [item["item_id"] for item in result.rejected] == ["clip-b"]
    assert result.rejected[0]["review_status"] == "rejected"
    assert result.stats["rejection_reasons"] == {"off_topic": 1}
    assert json.loads((tmp_path / "out" / "clip-a.judge.json").read_text(encoding="utf-8"))["bucket"] == "wide"
    _assert_filter_stats_schema(result.stats)


def test_bucket_judge_rejects_invalid_fixture_schema(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "judges"
    fixture_dir.mkdir()
    (fixture_dir / "clip-a.judge.json").write_text(
        json.dumps({"accepted": True, "bucket": "wide", "reason": "wrong key", "score": 0.9}),
        encoding="utf-8",
    )

    with pytest.raises(jsonschema.ValidationError):
        BucketJudgeGate().apply(
            [_item(tmp_path, "clip-a")],
            {},
            {"enabled": True, "fixture_mode": True, "fixture_judge_dir": str(fixture_dir), "buckets": ["wide"]},
        )


def test_bucket_judge_visual_understand_uses_schema_constrained_output_and_budget(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    tracker = BudgetTracker(max_api_calls=2, provider_limits={"bucket_judge.visual_understand": 1})

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        out = Path(cmd[cmd.index("--out") + 1])
        out.write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "status": "ok",
                            "answer": json.dumps({"accept": True, "bucket": "closeup", "reason": "usable", "score": 0.83}),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    result = BucketJudgeGate(runner=runner).apply(
        [_item(tmp_path, "clip-a")],
        {},
        {
            "enabled": True,
            "provider": "visual_understand",
            "prompt_template": "Classify {clip_id} into {buckets}.",
            "out_dir": str(tmp_path / "out"),
            "buckets": ["closeup"],
            "budget_tracker": tracker,
        },
    )

    command = calls[0]
    assert [item["bucket"] for item in result.passed] == ["closeup"]
    assert "astrid.packs.builtin.visual_understand.run" in command
    assert command[command.index("--query") + 1] == "Classify clip-a into closeup."
    assert "--response-schema" in command
    assert tracker.provider_calls == {"bucket_judge.visual_understand": 1}
    assert json.loads(judge_sidecar_path(_item(tmp_path, "clip-a"), {"out_dir": str(tmp_path / "out")}).read_text(encoding="utf-8")) == {
        "accept": True,
        "bucket": "closeup",
        "reason": "usable",
        "score": 0.83,
    }


def test_bucket_judge_video_understand_classifies_generically(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "results": [
                        {
                            "status": "ok",
                            "answer": {"accept": True, "bucket": "action", "reason": "motion", "score": 0.74},
                        }
                    ]
                }
            ),
            stderr="",
        )

    result = BucketJudgeGate(runner=runner).apply(
        [_item(tmp_path, "clip-a")],
        {},
        {"enabled": True, "provider": "video_understand", "buckets": {"action": {}}, "out_dir": str(tmp_path / "out")},
    )

    command = calls[0]
    assert result.passed[0]["bucket"] == "action"
    assert "astrid.packs.builtin.video_understand.run" in command
    assert command[command.index("--start") + 1] == "1.000"
    assert command[command.index("--end") + 1] == "6.000"


def test_filter_stage_code_has_no_domain_specific_literals() -> None:
    root = Path("astrid/packs/builtin/dataset_build/filter_stages")
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in root.glob("*.py"))
    assert "seinfeld" not in text
