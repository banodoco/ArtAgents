from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource

from astrid.packs.builtin.dataset_build import run as dataset_run
from astrid.packs.builtin.dataset_build.items import make_candidate_item
from astrid.packs.builtin.dataset_build.media import ffprobe_metadata
from astrid.packs.builtin.dataset_build.source_providers.local_folder import LocalFolderSourceProvider
from astrid.packs.builtin.dataset_build.state import read_review_state, set_status


ROOT = Path(__file__).resolve().parents[4]
FIXTURE_ROOT = ROOT / "fixtures" / "builtin-training"
RUNTIME_SCHEMAS = ROOT / "astrid" / "packs" / "builtin" / "dataset_build" / "schemas"
FROZEN_CONTRACTS = ROOT / "docs" / "megaplan" / "epics" / "builtin-training" / "contracts"
FROZEN_SCHEMAS = FROZEN_CONTRACTS / "schemas"
FROZEN_FIXTURES = FROZEN_CONTRACTS / "fixtures"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_registry(schema_root: Path) -> Registry:
    registry = Registry()
    for path in schema_root.glob("*.schema.json"):
        schema = _load_json(path)
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(path.name, resource)
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], resource)
    return registry


def _validate(schema_root: Path, schema_name: str, payload: Any) -> list[jsonschema.ValidationError]:
    schema = _load_json(schema_root / schema_name)
    validator = jsonschema.Draft7Validator(schema, registry=_schema_registry(schema_root))
    return sorted(validator.iter_errors(payload), key=lambda error: list(error.path))


def test_offline_fixture_media_is_valid_and_small() -> None:
    media_files = sorted((FIXTURE_ROOT / "media").glob("*.mp4"))

    assert [path.name for path in media_files] == ["test_clip_01.mp4", "test_clip_02.mp4", "test_clip_03.mp4"]
    for media_file in media_files:
        assert media_file.stat().st_size < 100_000
        metadata = ffprobe_metadata(media_file)
        assert metadata["duration_s"] == 2.0
        assert metadata["resolution"] == {"width": 64, "height": 64}


def test_runtime_and_frozen_fixture_contracts_validate_against_both_schema_locations() -> None:
    runtime_fixtures = [
        ("dataset-config.schema.json", FIXTURE_ROOT / "dataset-config.json"),
        ("dataset-config.schema.json", FIXTURE_ROOT / "dataset-config-cheap-filters.json"),
        ("run-state.schema.json", FIXTURE_ROOT / "expected" / "run-state.json"),
        ("manifest.schema.json", FIXTURE_ROOT / "expected" / "final.manifest.json"),
        ("ai-toolkit-adapter-manifest.schema.json", FIXTURE_ROOT / "expected" / "ai-toolkit-ltx.manifest.json"),
    ]
    frozen_fixtures = [
        ("dataset-config.schema.json", FROZEN_FIXTURES / "dataset-config.valid.json"),
        ("run-state.schema.json", FROZEN_FIXTURES / "run-state.valid.json"),
        ("manifest.schema.json", FROZEN_FIXTURES / "expected-manifest.json"),
        ("ai-toolkit-adapter-manifest.schema.json", FROZEN_FIXTURES / "expected-ai-toolkit-manifest.json"),
    ]

    for schema_name, fixture_path in [*runtime_fixtures, *frozen_fixtures]:
        payload = _load_json(fixture_path)
        assert _validate(RUNTIME_SCHEMAS, schema_name, payload) == []
        assert _validate(FROZEN_SCHEMAS, schema_name, payload) == []

    for path in [FIXTURE_ROOT / "review-decisions.json", FROZEN_FIXTURES / "review-decisions.valid.json"]:
        payload = _load_json(path)
        if isinstance(payload, dict) and isinstance(payload.get("decisions"), dict):
            decisions = list(payload["decisions"].values())
        else:
            decisions = payload if isinstance(payload, list) else list(payload.values())
        for decision in decisions:
            assert _validate(RUNTIME_SCHEMAS, "review-decision.schema.json", decision) == []
            assert _validate(FROZEN_SCHEMAS, "review-decision.schema.json", decision) == []

    future_config = _load_json(FROZEN_FIXTURES / "dataset-config.future-version.json")
    assert _validate(RUNTIME_SCHEMAS, "dataset-config.schema.json", future_config)
    assert _validate(FROZEN_SCHEMAS, "dataset-config.schema.json", future_config)


def test_offline_fixture_drives_full_no_network_pipeline(tmp_path: Path) -> None:
    out_dir = tmp_path / "fixture-run"
    exit_code = dataset_run.main(
        [
            "--config",
            str(FIXTURE_ROOT / "dataset-config.json"),
            "--out",
            str(out_dir),
            "--review-decisions",
            str(FIXTURE_ROOT / "review-decisions.json"),
        ]
    )

    assert exit_code == 0
    assert not (FIXTURE_ROOT / "media" / "item_c6e3d6b92824f535.caption.json").exists()
    assert (out_dir / "clips" / "item_c6e3d6b92824f535.caption.json").is_file()
    assert (out_dir / "clips" / "item_aaad37dfa8c5d42a.caption.json").is_file()
    assert (out_dir / "clips" / "judges" / "item_ea4e240dfc31e8a5.judge.json").is_file()

    generated_state = _normalize_state(_load_json(out_dir / "review_state.json"))
    expected_state = _load_json(FIXTURE_ROOT / "expected" / "run-state.json")
    assert generated_state == expected_state

    generated_preview = _load_json(out_dir / "work_preview.json")
    expected_preview = _load_json(FIXTURE_ROOT / "expected" / "work-preview.json")
    assert generated_preview == expected_preview

    generated_manifest = _normalize_manifest(_load_json(out_dir / "final.manifest.json"), out_dir)
    expected_manifest = _load_json(FIXTURE_ROOT / "expected" / "final.manifest.json")
    assert generated_manifest == expected_manifest

    generated_adapter = _normalize_adapter(_load_json(out_dir / "ai-toolkit-ltx.manifest.json"), out_dir)
    expected_adapter = _load_json(FIXTURE_ROOT / "expected" / "ai-toolkit-ltx.manifest.json")
    assert generated_adapter == expected_adapter

    caption = _load_json(out_dir / "clips" / "item_aaad37dfa8c5d42a.caption.json")
    assert caption["text"] == "A reviewer-edited green-frame fixture caption for export."


def test_offline_cheap_filter_fixture_covers_ordered_filter_contracts(tmp_path: Path, monkeypatch) -> None:
    media_files = sorted((FIXTURE_ROOT / "media").glob("*.mp4"))
    _patch_cheap_filter_provider(monkeypatch, media_files)
    parsed = dataset_run.load_dataset_config(FIXTURE_ROOT / "dataset-config-cheap-filters.json")

    summary = dataset_run.run_pipeline(parsed, tmp_path / "cheap-filter-run", skip_review=True)

    assert summary["accepted"] == 0
    assert summary["canonical_manifest"] is None
    assert summary["adapter_manifest"] is None
    out_dir = tmp_path / "cheap-filter-run"
    preview = _load_json(out_dir / "work_preview.json")
    assert preview["phase"] == "post_deterministic_filters"
    assert preview["active_item_count"] == 2
    assert preview["rejected_item_count"] == 3
    assert preview["planned_caption_calls"] == 2
    assert preview["enabled_model_backed_stages"] == []
    assert preview["filter_rejected_counts"] == {
        "black_frame_filter": 0,
        "content_hash_filter": 1,
        "duration_filter": 0,
        "rights_filter": 1,
        "source_cap_filter": 1,
    }
    assert preview["filter_warning_counts"]["black_frame_filter"] == 1

    filtered = _load_json(out_dir / "filtered_items.json")
    assert filtered["phase"] == "post_model_backed_filters"
    assert [item["item_id"] for item in filtered["active"]] == ["fixture-keep", "fixture-missing-black"]
    assert [item["item_id"] for item in filtered["rejected"]] == [
        "fixture-restricted-rights",
        "fixture-duplicate",
        "fixture-source-cap",
    ]

    by_id = {item["item_id"]: item for item in _load_json(out_dir / "review_data.json")["items"]}
    assert by_id["fixture-duplicate"]["filter_results"]["content_hash_filter"]["reason"] == "duplicate_content_hash"
    assert by_id["fixture-source-cap"]["filter_results"]["source_cap_filter"]["reason"] == "source_cap_exceeded"
    assert by_id["fixture-restricted-rights"]["filter_results"]["rights_filter"]["reason"] == "rights_status_restricted"
    assert by_id["fixture-missing-black"]["filter_results"]["black_frame_filter"]["reason"] == "missing_black_frame_metadata"
    assert by_id["fixture-keep"]["review_sampled"]["sampled"] is True
    assert by_id["fixture-missing-black"]["review_sampled"]["sampled"] is False
    assert read_review_state(out_dir / "review_state.json")["status"] == "reviewing"


def test_offline_fixture_review_modes_and_interrupted_resume_use_checkpoints(tmp_path: Path) -> None:
    parsed = dataset_run.load_dataset_config(FIXTURE_ROOT / "dataset-config.json")
    out_dir = tmp_path / "review-mode-run"

    skip_summary = dataset_run.run_pipeline(parsed, out_dir, skip_review=True)
    assert skip_summary["state_status"] == "reviewing"
    assert skip_summary["canonical_manifest"] is None
    assert (out_dir / "review_data.json").is_file()
    assert not (out_dir / "final.manifest.json").exists()

    set_status(out_dir / "review_state.json", "preview_ready")
    resumed_summary = dataset_run.run_pipeline(
        parsed,
        out_dir,
        review_decisions_path=FIXTURE_ROOT / "review-decisions.json",
    )
    assert resumed_summary["state_status"] == "finalized"
    assert resumed_summary["accepted"] == 2

    set_status(out_dir / "review_state.json", "reviewing")
    review_only_summary = dataset_run.run_pipeline(
        parsed,
        out_dir,
        review_decisions_path=FIXTURE_ROOT / "review-decisions.json",
        review_only=True,
    )
    assert review_only_summary["state_status"] == "finalized"
    assert review_only_summary["accepted"] == 2


def _normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(state)
    normalized["config_hash"] = "<CONFIG_HASH>"
    for key in ("created_at", "updated_at", "completed_at"):
        if key in normalized:
            normalized[key] = "2026-05-21T00:00:00Z"
    for stats in normalized.get("filter_stats", {}).values():
        if "duration_ms" in stats:
            stats["duration_ms"] = 0.0
    return normalized


def _normalize_manifest(manifest: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    normalized = copy.deepcopy(manifest)
    normalized["created_at"] = "2026-05-21T00:00:00Z"
    for item in normalized["items"]:
        item["acquired_at"] = "2026-05-21T00:00:00Z"
    return _replace_paths(normalized, out_dir)


def _normalize_adapter(adapter: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    normalized = copy.deepcopy(adapter)
    normalized["generated_at"] = "2026-05-21T00:00:00Z"
    return _replace_paths(normalized, out_dir)


def _replace_paths(value: Any, out_dir: Path) -> Any:
    if isinstance(value, dict):
        return {key: _replace_paths(item, out_dir) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_paths(item, out_dir) for item in value]
    if isinstance(value, str):
        repo = ROOT.as_posix()
        return value.replace(out_dir.as_posix(), "<RUN_DIR>").replace(repo, "<REPO>")
    return value


def _patch_cheap_filter_provider(monkeypatch, media_files: list[Path]) -> None:
    def acquire(self: LocalFolderSourceProvider, config: dict[str, Any]):
        yield _fixture_candidate(
            "fixture-keep",
            media_files[0],
            source_id="yt-video-1-s00",
            derived_source_id="yt-video-1",
            black_frame_ratio=0.1,
            rights_status="verified",
            scene_index=0,
        )
        yield _fixture_candidate(
            "fixture-source-cap",
            media_files[1],
            source_id="yt-video-1-s01",
            derived_source_id="yt-video-1",
            black_frame_ratio=0.1,
            rights_status="verified",
            scene_index=1,
        )
        yield _fixture_candidate(
            "fixture-duplicate",
            media_files[0],
            source_id="yt-video-2-s00",
            derived_source_id="yt-video-2",
            black_frame_ratio=0.1,
            rights_status="verified",
            scene_index=2,
        )
        yield _fixture_candidate(
            "fixture-restricted-rights",
            media_files[2],
            source_id="yt-video-3-s00",
            derived_source_id="yt-video-3",
            black_frame_ratio=0.1,
            rights_status="restricted",
            scene_index=3,
        )
        yield _fixture_candidate(
            "fixture-missing-black",
            media_files[2],
            source_id="yt-video-4-s00",
            derived_source_id="yt-video-4",
            black_frame_ratio=None,
            rights_status="verified",
            scene_index=4,
        )

    monkeypatch.setattr(LocalFolderSourceProvider, "acquire", acquire)


def _fixture_candidate(
    item_id: str,
    media_path: Path,
    *,
    source_id: str,
    derived_source_id: str,
    black_frame_ratio: float | None,
    rights_status: str,
    scene_index: int,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "duration_s": 2.0,
        "resolution": {"width": 64, "height": 64},
    }
    if black_frame_ratio is not None:
        metadata["black_frame_ratio"] = black_frame_ratio
    item = make_candidate_item(
        source_type="youtube",
        source_id=source_id,
        source_url=f"https://www.youtube.com/watch?v={derived_source_id}",
        media_path=media_path,
        media_type="video",
        source_metadata=metadata,
        rights={
            "license": "fixture",
            "attribution": "Astrid fixture media",
            "restrictions": [],
            "rights_status": rights_status,
        },
        duration_s=2.0,
        clip_start_s=0.0,
        clip_end_s=2.0,
        scene_index=scene_index,
        derived_from={
            "source_id": derived_source_id,
            "source_type": "youtube",
            "transformation": "scene",
        },
    )
    item["item_id"] = item_id
    return item
