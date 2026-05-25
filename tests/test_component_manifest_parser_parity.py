from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema

from astrid._paths import REPO_ROOT
from astrid.core.element.registry import load_default_registry as load_default_element_registry
from astrid.core.element.schema import load_element_definition
from astrid.core.executor.registry import load_default_registry as load_default_executor_registry
from astrid.core.executor.schema import load_executor_manifest
from astrid.core.manifest import load_manifest_mapping
from astrid.core.orchestrator.registry import (
    load_default_registry as load_default_orchestrator_registry,
)
from astrid.core.orchestrator.schema import load_orchestrator_manifest
from astrid.packs.validate import KNOWN_SCHEMA_VERSIONS, PackValidator

BUILTIN_PACK_ROOT = REPO_ROOT / "astrid" / "packs" / "builtin"

BUILTIN_MANIFESTS: dict[str, tuple[Path, ...]] = {
    "executor": tuple(sorted((BUILTIN_PACK_ROOT / "executors").glob("*/executor.yaml"))),
    "orchestrator": tuple(sorted((BUILTIN_PACK_ROOT / "orchestrators").glob("*/orchestrator.yaml"))),
    "element": tuple(sorted((BUILTIN_PACK_ROOT / "elements").glob("*/*/element.yaml"))),
}


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _assert_direct_json_schema_accepts(
    payload: dict[str, Any],
    manifest_kind: str,
    manifest_path: Path,
) -> None:
    validator = PackValidator(BUILTIN_PACK_ROOT)
    schema_path = KNOWN_SCHEMA_VERSIONS[1][manifest_kind]
    schema, registry = validator._load_schema(schema_path, manifest_kind, 1)
    errors = sorted(
        jsonschema.Draft7Validator(schema, registry=registry).iter_errors(payload),
        key=lambda error: list(error.absolute_path),
    )
    assert [error.message for error in errors] == [], _rel(manifest_path)


def _assert_pack_validator_accepts(
    manifest_path: Path,
    manifest_kind: str,
) -> dict[str, Any]:
    validator = PackValidator(BUILTIN_PACK_ROOT)
    payload = validator.validate_component_manifest(manifest_path, manifest_kind)
    assert validator.errors == [], _rel(manifest_path)
    assert payload is not None, _rel(manifest_path)
    return payload


def _assert_executor_runtime_accepts(manifest_path: Path) -> None:
    parsed = load_executor_manifest(manifest_path)
    registry_entry = load_default_executor_registry().get(parsed.id)

    assert parsed.id == registry_entry.id, _rel(manifest_path)
    assert parsed.command == registry_entry.command, _rel(manifest_path)


def _assert_orchestrator_runtime_accepts(manifest_path: Path) -> None:
    parsed = load_orchestrator_manifest(manifest_path)
    registry_entry = load_default_orchestrator_registry().get(parsed.id)

    assert parsed.id == registry_entry.id, _rel(manifest_path)
    assert parsed.runtime == registry_entry.runtime, _rel(manifest_path)


def _assert_element_runtime_accepts(manifest_path: Path) -> None:
    element_root = manifest_path.parent
    folder_kind = element_root.parent.name
    parsed = load_element_definition(
        element_root,
        kind=folder_kind,
        source="pack:builtin",
        editable=False,
        priority=30,
    )
    registry_entry = load_default_element_registry().get(folder_kind, parsed.id)

    assert parsed.id == registry_entry.id, _rel(manifest_path)
    assert parsed.kind == registry_entry.kind, _rel(manifest_path)


def test_builtin_manifest_globs_are_nonempty_per_kind() -> None:
    missing = [manifest_kind for manifest_kind, paths in BUILTIN_MANIFESTS.items() if not paths]

    assert missing == []


def test_builtin_component_manifest_schema_versions_are_explicit() -> None:
    missing_versions: list[str] = []

    for manifest_kind, manifest_paths in BUILTIN_MANIFESTS.items():
        for manifest_path in manifest_paths:
            payload = load_manifest_mapping(manifest_path, manifest_kind=manifest_kind)
            if payload.get("schema_version") != 1:
                missing_versions.append(_rel(manifest_path))

    assert missing_versions == []


def test_builtin_component_manifest_parsers_agree_for_every_checked_file() -> None:
    failures: dict[str, str] = {}

    for manifest_kind, manifest_paths in BUILTIN_MANIFESTS.items():
        for manifest_path in manifest_paths:
            try:
                direct_payload = load_manifest_mapping(
                    manifest_path,
                    manifest_kind=manifest_kind,
                )
                _assert_direct_json_schema_accepts(
                    direct_payload,
                    manifest_kind,
                    manifest_path,
                )
                pack_payload = _assert_pack_validator_accepts(manifest_path, manifest_kind)
                assert pack_payload == direct_payload, _rel(manifest_path)

                if manifest_kind == "executor":
                    _assert_executor_runtime_accepts(manifest_path)
                elif manifest_kind == "orchestrator":
                    _assert_orchestrator_runtime_accepts(manifest_path)
                elif manifest_kind == "element":
                    _assert_element_runtime_accepts(manifest_path)
                else:  # pragma: no cover - guarded by BUILTIN_MANIFESTS keys.
                    raise AssertionError(f"unknown manifest kind {manifest_kind!r}")
            except Exception as exc:  # noqa: BLE001 - aggregate failures by manifest path.
                failures[_rel(manifest_path)] = str(exc)

    assert failures == {}
