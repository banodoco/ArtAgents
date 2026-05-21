from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from astrid.packs.builtin.dataset_build.config import (
    MISSING_SCHEMA_VERSION_SOURCE,
    MISSING_SCHEMA_VERSION_WARNING,
    BudgetPreflightError,
    ConfigParseError,
    SecretPreflightError,
    load_dataset_config,
    preflight_budget_and_secrets,
)


ROOT = Path(__file__).resolve().parents[4]
FIXTURES = ROOT / "docs" / "megaplan" / "epics" / "builtin-training" / "contracts" / "fixtures"


def _fixture(name: str) -> Path:
    return FIXTURES / name


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture(name).read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def test_load_dataset_config_accepts_strict_v1_and_resolves_relative_paths() -> None:
    parsed = load_dataset_config(_fixture("dataset-config.valid.json"))

    assert parsed.warnings == ()
    assert parsed.schema_version_source is None
    assert parsed.data["schema_version"] == 1
    assert parsed.data["media_type"] == "video"
    assert parsed.data["sources"][0]["config"]["path"] == str((FIXTURES / "fixtures" / "media").resolve())
    assert parsed.data["caption"]["schema_path"] == str((FIXTURES / "fixtures" / "schemas" / "caption.json").resolve())
    assert parsed.data["output"]["run_dir"] == str((FIXTURES / "runs" / "fixture-smoke-test").resolve())


def test_load_dataset_config_accepts_yaml_with_same_policy(tmp_path: Path) -> None:
    data = _load_fixture("dataset-config.valid.json")
    data["sources"][0]["config"]["path"] = "media"
    path = tmp_path / "dataset.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")

    parsed = load_dataset_config(path)

    assert parsed.data["sources"][0]["config"]["path"] == str((tmp_path / "media").resolve())
    assert parsed.data["schema_version"] == 1


def test_load_dataset_config_warns_exactly_for_missing_schema_version() -> None:
    parsed = load_dataset_config(_fixture("dataset-config.missing-schema-version.json"))

    assert parsed.warnings == (MISSING_SCHEMA_VERSION_WARNING,)
    assert parsed.schema_version_source == MISSING_SCHEMA_VERSION_SOURCE
    assert parsed.data["schema_version"] == 1


def test_load_dataset_config_rejects_future_schema_version_with_specified_error() -> None:
    with pytest.raises(ConfigParseError, match="unsupported schema_version 99; max supported: 1"):
        load_dataset_config(_fixture("dataset-config.future-version.json"))


def test_load_dataset_config_rejects_unknown_top_level_keys(tmp_path: Path) -> None:
    data = _load_fixture("dataset-config.valid.json")
    data["experimental_top_level"] = True
    path = _write_json(tmp_path / "unknown.json", data)

    with pytest.raises(ConfigParseError) as exc_info:
        load_dataset_config(path)

    message = str(exc_info.value)
    assert "unknown config key: 'experimental_top_level'" in message
    assert "Use 'extensions' object for experimental fields." in message


def test_load_dataset_config_accepts_unknown_keys_under_extensions(tmp_path: Path) -> None:
    data = _load_fixture("dataset-config.valid.json")
    data["extensions"] = {"experimental_top_level": True}
    path = _write_json(tmp_path / "extensions.json", data)

    parsed = load_dataset_config(path)

    assert parsed.data["extensions"]["experimental_top_level"] is True


def test_load_dataset_config_enforces_video_media_type(tmp_path: Path) -> None:
    data = _load_fixture("dataset-config.valid.json")
    data["media_type"] = "image"
    path = _write_json(tmp_path / "image.json", data)

    with pytest.raises(ConfigParseError, match="media_type must be 'video'"):
        load_dataset_config(path)


def test_preflight_allows_local_fixture_path_without_secrets(tmp_path: Path) -> None:
    data = _load_fixture("dataset-config.valid.json")
    data["caption"] = {"provider": "transcribe"}
    path = _write_json(tmp_path / "local.json", data)
    parsed = load_dataset_config(path)

    preflight_budget_and_secrets(parsed, env={})


def test_preflight_allows_explicit_fixture_mode_without_secrets(tmp_path: Path) -> None:
    data = _load_fixture("dataset-config.valid.json")
    data["extensions"] = {"fixture_mode": True}
    path = _write_json(tmp_path / "fixture-mode.json", data)
    parsed = load_dataset_config(path)

    preflight_budget_and_secrets(parsed, env={})


def test_preflight_rejects_api_backed_caption_without_secret(tmp_path: Path) -> None:
    data = _load_fixture("dataset-config.valid.json")
    data["extensions"] = {"fixture_mode": False}
    path = _write_json(tmp_path / "api.json", data)
    parsed = load_dataset_config(path)

    with pytest.raises(SecretPreflightError, match="caption.visual_understand"):
        preflight_budget_and_secrets(parsed, env={})


def test_preflight_accepts_api_backed_caption_with_secret(tmp_path: Path) -> None:
    data = _load_fixture("dataset-config.valid.json")
    data["extensions"] = {"fixture_mode": False}
    path = _write_json(tmp_path / "api.json", data)
    parsed = load_dataset_config(path)

    preflight_budget_and_secrets(parsed, env={"OPENAI_API_KEY": "test-key"})


def test_preflight_rejects_api_backed_stage_with_zero_call_budget(tmp_path: Path) -> None:
    data = _load_fixture("dataset-config.valid.json")
    data["extensions"] = {"fixture_mode": False}
    data["budgets"] = copy.deepcopy(data["budgets"])
    data["budgets"]["max_api_calls"] = 0
    path = _write_json(tmp_path / "budget.json", data)
    parsed = load_dataset_config(path)

    with pytest.raises(BudgetPreflightError, match="budgets.max_api_calls is 0"):
        preflight_budget_and_secrets(parsed, env={"OPENAI_API_KEY": "test-key"})


def test_preflight_rejects_api_backed_stage_with_provider_zero_call_budget(tmp_path: Path) -> None:
    data = _load_fixture("dataset-config.valid.json")
    data["extensions"] = {"fixture_mode": False}
    data["budgets"] = copy.deepcopy(data["budgets"])
    data["budgets"]["providers"] = {"caption.visual_understand": {"max_calls": 0}}
    path = _write_json(tmp_path / "provider-budget.json", data)
    parsed = load_dataset_config(path)

    with pytest.raises(BudgetPreflightError, match="caption.visual_understand"):
        preflight_budget_and_secrets(parsed, env={"OPENAI_API_KEY": "test-key"})


def test_env_example_documents_dataset_build_secrets() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=" in text
    assert "builtin.dataset_build" in text

