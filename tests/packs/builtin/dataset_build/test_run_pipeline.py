from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml
import pytest

from astrid.packs.builtin.dataset_build import run as dataset_run
from astrid.packs.builtin.dataset_build.items import config_hash, make_candidate_item
from astrid.packs.builtin.dataset_build.state import make_initial_state, read_review_state, set_status, write_review_state
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


def _patch_local_provider_many(monkeypatch, media_file: Path, count: int) -> None:
    def acquire(self: LocalFolderSourceProvider, config: dict[str, Any]):
        for index in range(count):
            yield {
                **make_candidate_item(
                    source_type="local_folder",
                    source_id=f"source-{index + 1}",
                    source_url=media_file.as_uri(),
                    media_path=media_file,
                    media_type="video",
                    source_metadata={"resolution": {"width": 64, "height": 64}},
                    duration_s=5.0,
                    clip_start_s=0.0,
                    clip_end_s=5.0,
                    scene_index=index,
                ),
                "item_id": f"clip-{index}",
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
    assert statuses == ["acquiring", "filtering", "preview_ready", "captioning", "reviewing", "finalized"]
    assert (out_dir / "review_data.json").is_file()
    assert (out_dir / "review_state.json").is_file()
    assert (out_dir / "candidates.json").is_file()
    assert (out_dir / "work_preview.json").is_file()
    assert (out_dir / "filtered_items.json").is_file()
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
    preview = json.loads((out_dir / "work_preview.json").read_text(encoding="utf-8"))
    assert preview["phase"] == "post_deterministic_filters"
    assert preview["active_item_count"] == 1
    assert preview["rejected_item_count"] == 0
    assert preview["planned_caption_calls"] == 1
    assert preview["enabled_model_backed_stages"] == []


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


def test_dataset_build_resume_uses_existing_review_state_authoritatively(tmp_path: Path, monkeypatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_local_provider(monkeypatch, media_file)
    config_path = _config(tmp_path, media_dir)
    parsed = dataset_run.load_dataset_config(config_path)
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    config = copy.deepcopy(parsed.data)
    config.setdefault("output", {})["run_dir"] = str(out_dir.resolve())
    existing = make_initial_state(
        run_id="fixture-run",
        writer_id="builtin.dataset_build",
        config_hash=config_hash(config),
        buckets=config.get("buckets"),
        status="preview_ready",
    )
    existing["processed_source_ids"] = ["source-before-resume"]
    written = write_review_state(out_dir / "review_state.json", existing, now="2026-05-21T00:00:00Z")
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(
        json.dumps([{"item_id": "clip-a", "decision": "accept", "reviewed_at": "2026-05-21T00:00:01Z"}]),
        encoding="utf-8",
    )

    summary = dataset_run.run_pipeline(parsed, out_dir, review_decisions_path=decisions_path)

    state = read_review_state(out_dir / "review_state.json")
    assert summary["state_status"] == "finalized"
    assert state["state_version"] > written["state_version"]
    assert state["processed_source_ids"] == ["source-before-resume", "source-1"]


@pytest.mark.parametrize(
    "resume_status",
    ["initializing", "acquiring", "failed", "filtering", "preview_ready", "captioning", "reviewing", "finalized"],
)
def test_dataset_build_resume_statuses_load_existing_checkpoints_without_reacquiring(
    tmp_path: Path,
    monkeypatch,
    resume_status: str,
) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_local_provider(monkeypatch, media_file)
    config_path = _config(tmp_path, media_dir)
    parsed = dataset_run.load_dataset_config(config_path)
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(
        json.dumps([{"item_id": "clip-a", "decision": "accept", "reviewed_at": "2026-05-21T00:00:01Z"}]),
        encoding="utf-8",
    )
    out_dir = tmp_path / "run"
    dataset_run.run_pipeline(parsed, out_dir, review_decisions_path=decisions_path)
    state_path = out_dir / "review_state.json"
    assert read_review_state(state_path)["processed_source_ids"] == ["source-1"]

    if resume_status == "finalized":
        set_status(state_path, "finalized")
        manifest_mtime = (out_dir / "final.manifest.json").stat().st_mtime_ns
        state_version = read_review_state(state_path)["state_version"]
    else:
        set_status(state_path, resume_status)
        manifest_mtime = None
        state_version = None

    def fail_acquire(self: LocalFolderSourceProvider, config: dict[str, Any]):
        raise AssertionError(f"resume from {resume_status} should load checkpoints instead of acquiring")
        yield

    monkeypatch.setattr(LocalFolderSourceProvider, "acquire", fail_acquire)

    summary = dataset_run.run_pipeline(parsed, out_dir, review_decisions_path=decisions_path)

    state = read_review_state(state_path)
    assert summary["state_status"] == "finalized"
    assert state["processed_source_ids"] == ["source-1"]
    if resume_status == "finalized":
        assert state["state_version"] == state_version
        assert (out_dir / "final.manifest.json").stat().st_mtime_ns == manifest_mtime


def test_dataset_build_resume_rejects_config_hash_mismatch_without_mutating_state(tmp_path: Path, monkeypatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_local_provider(monkeypatch, media_file)
    parsed = dataset_run.load_dataset_config(_config(tmp_path, media_dir))
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    existing = make_initial_state(
        run_id="fixture-run",
        writer_id="builtin.dataset_build",
        config_hash="different-config",
        status="preview_ready",
    )
    written = write_review_state(out_dir / "review_state.json", existing, now="2026-05-21T00:00:00Z")

    try:
        dataset_run.run_pipeline(parsed, out_dir, review_decisions_path=None)
    except dataset_run.ResumeConfigMismatchError:
        pass
    else:
        raise AssertionError("config hash mismatch should fail before mutating state")

    state = read_review_state(out_dir / "review_state.json")
    assert state["state_version"] == written["state_version"]
    assert state["status"] == "preview_ready"
    assert state.get("error") is None


def test_dataset_build_skip_review_finalizes_without_auto_accepting_pending_items(tmp_path: Path, monkeypatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_local_provider(monkeypatch, media_file)
    parsed = dataset_run.load_dataset_config(_config(tmp_path, media_dir))

    def fail_human_review(*args: Any, **kwargs: Any):
        raise AssertionError("--skip-review should not launch human_review")

    summary = dataset_run.run_pipeline(parsed, tmp_path / "run", skip_review=True, human_review_runner=fail_human_review)

    assert summary["accepted"] == 0
    assert summary["canonical_manifest"] is None
    assert summary["adapter_manifest"] is None
    assert not (tmp_path / "run" / "review_server" / "human_review.final.json").exists()
    assert not (tmp_path / "run" / "final.manifest.json").exists()
    state = read_review_state(tmp_path / "run" / "review_state.json")
    assert state["status"] == "reviewing"
    assert state["submitted"] is False


def test_dataset_build_review_sampling_marks_items_without_dropping_unsampled_provenance(tmp_path: Path, monkeypatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_local_provider_many(monkeypatch, media_file, 3)
    config_path = _config(tmp_path, media_dir)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["review"] = {"enabled": True, "sampling": {"mode": "top_n", "sample_count": 1}}
    config["budgets"]["max_api_calls"] = 10
    config_path.write_text(json.dumps(config), encoding="utf-8")
    parsed = dataset_run.load_dataset_config(config_path)

    summary = dataset_run.run_pipeline(parsed, tmp_path / "run", skip_review=True)

    assert summary["accepted"] == 0
    review_data = json.loads((tmp_path / "run" / "review_data.json").read_text(encoding="utf-8"))
    items = review_data["items"]
    assert [item["item_id"] for item in items] == ["clip-0", "clip-1", "clip-2"]
    assert [item["review_status"] for item in items] == ["pending", "pending", "pending"]
    assert [item["review_sampled"]["sampled"] for item in items] == [True, False, False]
    assert {item["review_sampled"]["mode"] for item in items} == {"top_n"}
    assert {item["review_sampled"]["sample_count"] for item in items} == {1}
    assert items[0]["review_sampled"]["rank"] == 1


def test_dataset_build_review_disabled_accepts_all_without_human_review_compatibility(tmp_path: Path, monkeypatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_local_provider(monkeypatch, media_file)
    config_path = _config(tmp_path, media_dir)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["review"] = {"enabled": False}
    config_path.write_text(json.dumps(config), encoding="utf-8")
    parsed = dataset_run.load_dataset_config(config_path)

    def fail_human_review(*args: Any, **kwargs: Any):
        raise AssertionError("review.enabled=false should not launch human_review")

    summary = dataset_run.run_pipeline(parsed, tmp_path / "run", human_review_runner=fail_human_review)

    assert summary["accepted"] == 1
    state = read_review_state(tmp_path / "run" / "review_state.json")
    assert state["submitted"] is True
    assert (tmp_path / "run" / "review_server" / "human_review.final.json").is_file()


def test_dataset_build_review_only_uses_existing_review_checkpoint_without_reprocessing(tmp_path: Path, monkeypatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_local_provider(monkeypatch, media_file)
    config_path = _config(tmp_path, media_dir)
    parsed = dataset_run.load_dataset_config(config_path)
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(
        json.dumps([{"item_id": "clip-a", "decision": "accept", "reviewed_at": "2026-05-21T00:00:01Z"}]),
        encoding="utf-8",
    )
    out_dir = tmp_path / "run"
    dataset_run.run_pipeline(parsed, out_dir, review_decisions_path=decisions_path)
    set_status(out_dir / "review_state.json", "reviewing")

    def fail_acquire(self: LocalFolderSourceProvider, config: dict[str, Any]):
        raise AssertionError("--review-only should not acquire sources")
        yield

    def fail_caption(*args: Any, **kwargs: Any):
        raise AssertionError("--review-only should not caption")

    monkeypatch.setattr(LocalFolderSourceProvider, "acquire", fail_acquire)
    summary = dataset_run.run_pipeline(parsed, out_dir, review_decisions_path=decisions_path, review_only=True, caption_runner=fail_caption)

    assert summary["state_status"] == "finalized"
    assert summary["accepted"] == 1


def test_dataset_build_cli_skip_review_then_review_only_finalizes_without_reacquiring(tmp_path: Path, monkeypatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_local_provider(monkeypatch, media_file)
    config_path = _config(tmp_path, media_dir)
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(
        json.dumps([{"item_id": "clip-a", "decision": "accept", "reviewed_at": "2026-05-21T00:00:01Z"}]),
        encoding="utf-8",
    )
    out_dir = tmp_path / "run"

    skip_exit = dataset_run.main(["--config", str(config_path), "--out", str(out_dir), "--skip-review"])

    assert skip_exit == 0
    skipped_state = read_review_state(out_dir / "review_state.json")
    assert skipped_state["status"] == "reviewing"
    assert skipped_state["submitted"] is False
    assert (out_dir / "review_data.json").is_file()
    assert not (out_dir / "final.manifest.json").exists()

    def fail_acquire(self: LocalFolderSourceProvider, config: dict[str, Any]):
        raise AssertionError("--review-only CLI should use review_data.json instead of acquiring")
        yield

    monkeypatch.setattr(LocalFolderSourceProvider, "acquire", fail_acquire)
    review_only_exit = dataset_run.main(
        [
            "--config",
            str(config_path),
            "--out",
            str(out_dir),
            "--review-decisions",
            str(decisions_path),
            "--review-only",
        ]
    )

    assert review_only_exit == 0
    final_state = read_review_state(out_dir / "review_state.json")
    assert final_state["status"] == "finalized"
    assert final_state["submitted"] is True
    assert (out_dir / "final.manifest.json").is_file()


def test_dataset_build_cli_resume_from_candidates_checkpoint_without_reacquiring_processed_sources(tmp_path: Path, monkeypatch) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_local_provider(monkeypatch, media_file)
    config_path = _config(tmp_path, media_dir)
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(
        json.dumps([{"item_id": "clip-a", "decision": "accept", "reviewed_at": "2026-05-21T00:00:01Z"}]),
        encoding="utf-8",
    )
    out_dir = tmp_path / "run"
    first_exit = dataset_run.main(["--config", str(config_path), "--out", str(out_dir), "--review-decisions", str(decisions_path)])
    assert first_exit == 0
    assert read_review_state(out_dir / "review_state.json")["processed_source_ids"] == ["source-1"]
    set_status(out_dir / "review_state.json", "acquiring")

    def fail_acquire(self: LocalFolderSourceProvider, config: dict[str, Any]):
        raise AssertionError("resume should load candidates.json instead of reacquiring completed sources")
        yield

    monkeypatch.setattr(LocalFolderSourceProvider, "acquire", fail_acquire)
    resume_exit = dataset_run.main(["--config", str(config_path), "--out", str(out_dir), "--review-decisions", str(decisions_path)])

    assert resume_exit == 0
    state = read_review_state(out_dir / "review_state.json")
    assert state["status"] == "finalized"
    assert state["processed_source_ids"] == ["source-1"]


def test_dataset_build_dry_run_prints_plan_without_creating_artifacts(tmp_path: Path, capsys) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    config_path = _config(tmp_path, media_dir)
    out_dir = tmp_path / "dry-run-output"

    exit_code = dataset_run.main(["--config", str(config_path), "--out", str(out_dir), "--dry-run"])

    assert exit_code == 0
    assert not out_dir.exists()
    payload = json.loads(capsys.readouterr().out)
    assert payload["orchestrator"] == "builtin.dataset_build"
    assert [stage["stage_id"] for stage in payload["filter_stages"]] == ["duration_filter"]
    assert payload["fixture_mode"] is True
    assert payload["budget_limits"]["max_api_calls"] == 1
    assert payload["skip_review"] is False
    assert payload["review_only"] is False


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
