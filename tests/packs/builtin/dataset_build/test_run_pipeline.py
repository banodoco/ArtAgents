from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from astrid.packs.builtin.dataset_build import run as dataset_run
from astrid.packs.builtin.dataset_build.items import make_candidate_item
from astrid.packs.builtin.dataset_build.source_providers.local_folder import LocalFolderSourceProvider


def _config(tmp_path: Path, media_dir: Path) -> Path:
    config = {
        "schema_version": 1,
        "media_type": "video",
        "dataset_id": "fixture-run",
        "sources": [{"provider": "local_folder", "config": {"path": str(media_dir)}}],
        "buckets": {"wide": {"target_count": 1}},
        "clip_config": {"min_duration_s": 1.0, "max_duration_s": 10.0, "max_scenes_per_source": 1},
        "caption": {"provider": "visual_understand", "prompt_template": "Caption fixture."},
        "filters": {"duration": {"enabled": True, "min_s": 1.0, "max_s": 10.0}},
        "review": {"enabled": True},
        "manifest": {"adapter": "ai-toolkit-ltx"},
        "budgets": {"max_api_calls": 1, "max_estimated_cost_usd": 1.0, "providers": {}},
        "output": {"run_dir": str(tmp_path / "ignored")},
        "extensions": {"fixture_mode": True},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _patch_local_provider(monkeypatch, media_file: Path) -> None:
    def acquire(self: LocalFolderSourceProvider, config: dict[str, Any]):
        yield {
            **make_candidate_item(
                source_type="local_folder",
                source_id="source-1",
                source_url=media_file.as_uri(),
                media_path=media_file,
                media_type="video",
                source_metadata={"resolution": {"width": 64, "height": 64}},
                duration_s=5.0,
                clip_start_s=0.0,
                clip_end_s=5.0,
                scene_index=0,
            ),
            "item_id": "clip-a",
        }

    monkeypatch.setattr(LocalFolderSourceProvider, "acquire", acquire)


def test_dataset_build_cli_runs_noninteractive_pipeline_into_requested_out_dir(tmp_path: Path, monkeypatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"not-a-real-video-but-fixture-provider-is-patched")
    _patch_local_provider(monkeypatch, media_file)
    config_path = _config(tmp_path, media_dir)
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(
        json.dumps(
            [
                {
                    "item_id": "clip-a",
                    "decision": "accept",
                    "edited_caption": "Edited from non-interactive review.",
                    "reviewed_at": "2026-05-21T00:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "run"
    original_set_status = dataset_run.set_status
    statuses: list[str] = []

    def recording_set_status(path, status, **kwargs):
        statuses.append(status)
        return original_set_status(path, status, **kwargs)

    monkeypatch.setattr(dataset_run, "set_status", recording_set_status)

    exit_code = dataset_run.main(["--config", str(config_path), "--out", str(out_dir), "--review-decisions", str(decisions_path)])

    assert exit_code == 0
    assert statuses == ["acquiring", "filtering", "captioning", "reviewing", "finalized"]
    assert (out_dir / "review_data.json").is_file()
    assert (out_dir / "review_state.json").is_file()
    assert (out_dir / "review_server" / "human_review.final.json").is_file()
    assert (out_dir / "final.manifest.json").is_file()
    assert (out_dir / "ai-toolkit-ltx.manifest.json").is_file()
    assert not (media_dir / "clip-a.caption.json").exists()

    state = json.loads((out_dir / "review_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "finalized"
    assert state["submitted"] is True
    canonical = json.loads((out_dir / "final.manifest.json").read_text(encoding="utf-8"))
    assert [item["item_id"] for item in canonical["items"]] == ["clip-a"]
    assert canonical["items"][0]["caption"]["text"] == "Edited from non-interactive review."
    adapter = json.loads((out_dir / "ai-toolkit-ltx.manifest.json").read_text(encoding="utf-8"))
    assert adapter["clips"][0]["clip_file"].endswith("/run/clips/clip-a.mp4")
    assert adapter["clips"][0]["caption_file"].endswith("/run/clips/clip-a.caption.json")
    assert (out_dir / "clips" / "clip-a.mp4").is_file()
    assert json.loads((out_dir / "clips" / "clip-a.caption.json").read_text(encoding="utf-8"))["text"] == "Edited from non-interactive review."


def test_dataset_build_pipeline_marks_state_failed_on_runtime_error(tmp_path: Path, monkeypatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_local_provider(monkeypatch, media_file)
    parsed = dataset_run.load_dataset_config(_config(tmp_path, media_dir))

    try:
        dataset_run.run_pipeline(parsed, tmp_path / "run", review_decisions_path=tmp_path / "missing-decisions.json")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("missing review decisions should fail the run")

    state = json.loads((tmp_path / "run" / "review_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert state["error"]["type"] == "FileNotFoundError"


def test_dataset_build_cli_preflights_no_spend_api_config_before_run_dir_creation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = {
        "schema_version": 1,
        "media_type": "video",
        "dataset_id": "no-spend-preflight",
        "sources": [{"provider": "youtube", "config": {"source_urls": ["https://example.invalid/video"]}}],
        "buckets": {"wide": {"target_count": 1, "search_queries": ["generic training clip"]}},
        "clip_config": {"min_duration_s": 1.0, "max_duration_s": 10.0, "max_scenes_per_source": 1},
        "caption": {"provider": "visual_understand", "prompt_template": "Caption."},
        "filters": {"duration": {"enabled": True, "min_s": 1.0, "max_s": 10.0}},
        "review": {"enabled": False},
        "manifest": {"adapter": "ai-toolkit-ltx"},
        "budgets": {
            "max_api_calls": 0,
            "max_estimated_cost_usd": 1.0,
            "providers": {"caption.visual_understand": {"max_calls": 0}},
        },
        "output": {"run_dir": str(tmp_path / "ignored")},
        "extensions": {},
    }
    config_path = tmp_path / "api-config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    out_dir = tmp_path / "must-not-exist"

    exit_code = dataset_run.main(["--config", str(config_path), "--out", str(out_dir)])

    assert exit_code == 2
    assert not out_dir.exists()
