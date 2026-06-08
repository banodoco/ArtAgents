from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.packs.training.orchestrators.dataset_build import run as dataset_run
from astrid.packs.training.orchestrators.dataset_build.items import make_candidate_item
from astrid.packs.training.orchestrators.dataset_build.state import read_review_state
from astrid.packs.training.orchestrators.dataset_build.source_providers.local_folder import LocalFolderSourceProvider


def _config(tmp_path: Path, media_dir: Path) -> Path:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "media_type": "video",
                "dataset_id": "integrated-fixture",
                "sources": [{"provider": "local_folder", "config": {"path": str(media_dir)}}],
                "buckets": {"wide": {"target_count": 1}},
                "clip_config": {"min_duration_s": 1.0, "max_duration_s": 10.0, "max_scenes_per_source": 1},
                "caption": {"provider": "visual_understand", "prompt_template": "Caption fixture."},
                "filters": {"duration": {"enabled": True, "min_s": 1.0, "max_s": 10.0}},
                "review": {"enabled": True, "top_up": {"max_rounds": 1}},
                "manifest": {"adapter": "ai-toolkit-ltx"},
                "budgets": {"max_api_calls": 1, "max_estimated_cost_usd": 1.0, "providers": {}},
                "output": {"run_dir": str(tmp_path / "ignored")},
                "extensions": {"fixture_mode": True},
            }
        ),
        encoding="utf-8",
    )
    return path


def _candidate(media_file: Path, *, round_index: int) -> dict[str, Any]:
    return {
        **make_candidate_item(
            source_type="local_folder",
            source_id=f"source-{round_index}",
            source_url=media_file.as_uri(),
            media_path=media_file,
            media_type="video",
            source_metadata={"resolution": {"width": 64, "height": 64}},
            duration_s=5.0,
            clip_start_s=0.0,
            clip_end_s=5.0,
            scene_index=round_index,
        ),
        "item_id": f"clip-{round_index}",
    }


def _patch_novel_round_provider(monkeypatch: pytest.MonkeyPatch, media_file: Path) -> list[dict[str, Any]]:
    seen_requests: list[dict[str, Any]] = []

    def acquire(self: LocalFolderSourceProvider, config: dict[str, Any]):
        request = dict(config.get("acquisition_request") or {})
        seen_requests.append(request)
        round_index = int(request.get("round_index", 0))
        if round_index > 0:
            assert "clip-0" in request["exclude_candidate_ids"]
            assert "source-0" in request["exclude_source_ids"]
        self.last_acquisition_result = {
            "provider": "local_folder",
            "round_index": round_index,
            "limit_hint": request.get("limit_hint"),
            "considered": 1,
            "yielded": 1,
            "skipped_processed": 0,
            "skipped_excluded": 0,
            "skipped_duplicate_media": 0,
            "no_new_candidates": False,
            "reason": "candidates_yielded",
        }
        yield _candidate(media_file, round_index=round_index)

    monkeypatch.setattr(LocalFolderSourceProvider, "acquire", acquire)
    return seen_requests


def test_top_up_after_human_reject_acquires_only_novel_candidates_and_reports_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    seen_requests = _patch_novel_round_provider(monkeypatch, media_file)
    parsed = dataset_run.load_dataset_config(_config(tmp_path, media_dir))
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(
        json.dumps(
            {
                "rounds": {
                    "0": [{"item_id": "clip-0", "decision": "reject", "reject_reason": "low_quality"}],
                    "1": [{"item_id": "clip-1", "decision": "accept"}],
                }
            }
        ),
        encoding="utf-8",
    )

    summary = dataset_run.run_pipeline(parsed, tmp_path / "run", review_decisions_path=decisions_path)

    assert summary["state_status"] == "finalized"
    assert summary["accepted"] == 1
    assert [request["round_index"] for request in seen_requests] == [0, 1]
    assert seen_requests[1]["target_shortfalls"] == {"wide": 1}
    report = json.loads((tmp_path / "run" / "quality_report.json").read_text(encoding="utf-8"))
    assert report["final_shortfalls"] == {}
    assert report["bucket_counts"]["wide"]["accepted"] == 1
    assert report["bucket_counts"]["wide"]["rejected"] == 1
    assert [result["round_index"] for result in report["top_up_acquisition_results"]] == [0, 1]
    assert (tmp_path / "run" / "final.manifest.json").is_file()


def test_missing_round_aware_decisions_fail_without_silent_finalization_and_write_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_novel_round_provider(monkeypatch, media_file)
    config_path = _config(tmp_path, media_dir)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["buckets"] = {"wide": {"target_count": 2}}
    config_path.write_text(json.dumps(config), encoding="utf-8")
    parsed = dataset_run.load_dataset_config(config_path)
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(json.dumps([{"item_id": "clip-0", "decision": "accept"}]), encoding="utf-8")

    with pytest.raises(AstridError, match=r"round 1"):
        dataset_run.run_pipeline(parsed, tmp_path / "run", review_decisions_path=decisions_path)

    out_dir = tmp_path / "run"
    state = read_review_state(out_dir / "review_state.json")
    assert state["status"] == "failed"
    assert not (out_dir / "final.manifest.json").exists()
    assert not (out_dir / "ai-toolkit-ltx.manifest.json").exists()
    report = json.loads((out_dir / "quality_report.json").read_text(encoding="utf-8"))
    assert report["run_status"] == "failed"
    assert report["summary"]["pending"] == 1
    assert "source_concentration" in report
    assert "filter_rejection_breakdowns" in report


def test_invalid_accepted_caption_blocks_manifest_and_quality_report_records_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_novel_round_provider(monkeypatch, media_file)
    config_path = _config(tmp_path, media_dir)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["caption"]["validation"] = {"required_prefix": "APPROVED:"}
    config_path.write_text(json.dumps(config), encoding="utf-8")
    parsed = dataset_run.load_dataset_config(config_path)
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(json.dumps([{"item_id": "clip-0", "decision": "accept"}]), encoding="utf-8")

    summary = dataset_run.run_pipeline(parsed, tmp_path / "run", review_decisions_path=decisions_path)

    assert summary["state_status"] == "failed"
    assert summary["canonical_manifest"] is None
    assert summary["adapter_manifest"] is None
    assert not (tmp_path / "run" / "final.manifest.json").exists()
    report = json.loads((tmp_path / "run" / "quality_report.json").read_text(encoding="utf-8"))
    assert report["caption_validation_failures"][0]["code"] == "caption_text_prefix_mismatch"
    assert report["bucket_counts"]["wide"]["accepted"] == 1
    assert report["final_shortfalls"] == {}
