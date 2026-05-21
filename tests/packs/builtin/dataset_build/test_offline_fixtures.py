from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource

from astrid.packs.builtin.dataset_build import run as dataset_run
from astrid.packs.builtin.dataset_build.media import ffprobe_metadata


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

    generated_manifest = _normalize_manifest(_load_json(out_dir / "final.manifest.json"), out_dir)
    expected_manifest = _load_json(FIXTURE_ROOT / "expected" / "final.manifest.json")
    assert generated_manifest == expected_manifest

    generated_adapter = _normalize_adapter(_load_json(out_dir / "ai-toolkit-ltx.manifest.json"), out_dir)
    expected_adapter = _load_json(FIXTURE_ROOT / "expected" / "ai-toolkit-ltx.manifest.json")
    assert generated_adapter == expected_adapter

    caption = _load_json(out_dir / "clips" / "item_aaad37dfa8c5d42a.caption.json")
    assert caption["text"] == "A reviewer-edited green-frame fixture caption for export."


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
