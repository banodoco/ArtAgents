"""User compute-profile precedence and secret-safety contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.compute_profile import (
    SCHEMA_ID,
    credential_value,
    load_profile,
    resolve_compute_profile,
    write_resolved_snapshot,
)


def _profile(profile_id: str = "default", **values: object) -> dict[str, object]:
    return {
        "schema": SCHEMA_ID,
        "schema_version": 1,
        "id": profile_id,
        "provider": "runpod",
        "credentials": {"runpod_api_key": "RUNPOD_API_KEY", "hf_token": "HF_TOKEN"},
        **values,
    }


def _write(home: Path, profile_id: str, document: dict[str, object]) -> None:
    path = home / ".astrid" / "compute-profiles" / f"{profile_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_field_override_beats_selected_profile_and_defaults_fill_missing_fields(tmp_path: Path) -> None:
    _write(tmp_path, "default", _profile(gpu_type="default-gpu", storage_name="default-volume"))
    _write(tmp_path, "named", _profile("named", gpu_type="named-gpu", storage_name="named-volume"))
    _write(tmp_path, "env", _profile("env", gpu_type="env-gpu"))

    resolved = resolve_compute_profile(
        explicit={"gpu_type": "explicit-gpu"},
        env={"ASTRID_COMPUTE_PROFILE": "env"},
        profile_id="named",
        executor_defaults={"gpu_type": "executor-gpu", "container_disk_gb": 50},
        home=tmp_path,
    )

    assert resolved["gpu_type"] == "explicit-gpu"
    assert resolved["storage_name"] == "named-volume"
    assert resolved["profile_id"] == "named"
    assert resolved["profile_source"] == "explicit-profile"
    assert resolved["container_disk_gb"] == 50


def test_explicit_named_profile_beats_env_selected_profile(tmp_path: Path) -> None:
    _write(tmp_path, "named", _profile("named", gpu_type="named-gpu"))
    _write(tmp_path, "env", _profile("env", gpu_type="env-gpu"))
    resolved = resolve_compute_profile(
        profile_id="named",
        env={"ASTRID_COMPUTE_PROFILE": "env"},
        executor_defaults={"gpu_type": "executor-gpu"},
        home=tmp_path,
    )
    assert resolved["gpu_type"] == "named-gpu"
    assert resolved["profile_id"] == "named"
    assert resolved["profile_source"] == "explicit-profile"


def test_named_profile_beats_default_and_defaults_fill_missing_fields(tmp_path: Path) -> None:
    _write(tmp_path, "default", _profile(gpu_type="default-gpu", storage_name="default-volume"))
    _write(tmp_path, "named", _profile("named", gpu_type="named-gpu"))
    resolved = resolve_compute_profile(
        profile_id="named",
        executor_defaults={"gpu_type": "executor-gpu", "container_disk_gb": 50},
        home=tmp_path,
    )
    assert resolved["gpu_type"] == "named-gpu"
    assert resolved["container_disk_gb"] == 50
    assert resolved["profile_id"] == "named"


def test_profile_rejects_literal_credentials_and_snapshot_has_only_references(tmp_path: Path) -> None:
    _write(tmp_path, "bad", _profile("bad", credentials={"runpod_api_key": "rpa_literal_secret"}))
    with pytest.raises(ValueError, match="environment variable name"):
        load_profile("bad", home=tmp_path)

    resolved = resolve_compute_profile(
        executor_defaults={"credentials": {"runpod_api_key": "RUNPOD_API_KEY"}}, home=tmp_path
    )
    out = write_resolved_snapshot(tmp_path / "produces", resolved)
    persisted = json.loads(out.read_text(encoding="utf-8"))
    assert persisted["credentials"]["runpod_api_key"] == "RUNPOD_API_KEY"
    assert "rpa_literal_secret" not in out.read_text(encoding="utf-8")
    assert credential_value(resolved, "runpod_api_key", env={"RUNPOD_API_KEY": "secret"}) == "secret"


def test_env_selected_missing_profile_is_an_actionable_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="compute profile 'missing'"):
        resolve_compute_profile(env={"ASTRID_COMPUTE_PROFILE": "missing"}, home=tmp_path)
