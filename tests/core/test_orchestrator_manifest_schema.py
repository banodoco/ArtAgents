from __future__ import annotations

from copy import deepcopy
from typing import Any

import jsonschema

from astrid.core.pack.manifest import load_manifest_mapping
from astrid.core.orchestrator.registry import load_default_registry
from astrid.core.orchestrator.schema import load_orchestrator_manifest
from astrid.core.pack.validate import KNOWN_SCHEMA_VERSIONS, PackValidator
from astrid.paths import REPO_ROOT

PACKS_ROOT = REPO_ROOT / "astrid" / "packs"
PACK_ROOTS = tuple(sorted(path for path in PACKS_ROOT.iterdir() if (path / "pack.yaml").is_file()))
BUILTIN_ORCHESTRATOR_MANIFESTS = tuple(
    sorted(path for pack_root in PACK_ROOTS for path in (pack_root / "orchestrators").glob("*/orchestrator.yaml"))
)


def _orchestrator_validator() -> jsonschema.Draft7Validator:
    schema_path = KNOWN_SCHEMA_VERSIONS[1]["orchestrator"]
    schema, registry = PackValidator(REPO_ROOT)._load_schema(
        schema_path,
        "orchestrator",
        1,
    )
    return jsonschema.Draft7Validator(schema, registry=registry)


def _schema_errors(payload: dict[str, Any]) -> list[str]:
    validator = _orchestrator_validator()
    return sorted(error.message for error in validator.iter_errors(payload))


def _pack_root_for(manifest_path):
    relative = manifest_path.relative_to(PACKS_ROOT)
    return PACKS_ROOT / relative.parts[0]


def test_all_builtin_orchestrator_manifests_validate_against_json_schema() -> None:
    assert BUILTIN_ORCHESTRATOR_MANIFESTS

    failures: dict[str, list[str]] = {}
    for manifest_path in BUILTIN_ORCHESTRATOR_MANIFESTS:
        payload = load_manifest_mapping(manifest_path, manifest_kind="orchestrator")
        if payload.get("schema_version") != 1:
            failures[str(manifest_path.relative_to(REPO_ROOT))] = [
                f"schema_version must be 1, got {payload.get('schema_version')!r}"
            ]
            continue

        errors = _schema_errors(payload)
        if errors:
            failures[str(manifest_path.relative_to(REPO_ROOT))] = errors

    assert failures == {}


def test_pack_validator_loads_every_builtin_orchestrator_manifest() -> None:
    failures: dict[str, list[str]] = {}

    for manifest_path in BUILTIN_ORCHESTRATOR_MANIFESTS:
        validator = PackValidator(_pack_root_for(manifest_path))
        before = list(validator.errors)
        payload = validator.validate_component_manifest(manifest_path, "orchestrator")
        if payload is None or validator.errors != before:
            failures[str(manifest_path.relative_to(REPO_ROOT))] = validator.errors[len(before) :]

    assert failures == {}


def test_all_builtin_orchestrator_manifests_parse_through_runtime_and_registry() -> None:
    registry = load_default_registry()
    failures: dict[str, str] = {}

    for manifest_path in BUILTIN_ORCHESTRATOR_MANIFESTS:
        parsed = load_orchestrator_manifest(manifest_path)
        try:
            registered = registry.get(parsed.id)
        except KeyError as exc:
            failures[str(manifest_path.relative_to(REPO_ROOT))] = str(exc)
            continue

        if registered.runtime != parsed.runtime:
            failures[str(manifest_path.relative_to(REPO_ROOT))] = (
                f"registry runtime {registered.runtime!r} != parsed runtime {parsed.runtime!r}"
            )

    assert failures == {}


def test_orchestrator_schema_accepts_legacy_python_cli_runtime_shape() -> None:
    payload = load_manifest_mapping(
        PACKS_ROOT / "video_editing" / "orchestrators" / "hype" / "orchestrator.yaml",
        manifest_kind="orchestrator",
    )
    legacy_payload = deepcopy(payload)
    legacy_payload["runtime"] = {
        "type": "python-cli",
        "entrypoint": "run.py",
        "callable": "main",
    }

    errors = _schema_errors(legacy_payload)

    assert errors == []


def test_orchestrator_schema_rejects_missing_schema_version() -> None:
    payload = load_manifest_mapping(
        PACKS_ROOT / "video_editing" / "orchestrators" / "hype" / "orchestrator.yaml",
        manifest_kind="orchestrator",
    )
    payload.pop("schema_version")

    errors = _schema_errors(payload)

    assert "'schema_version' is a required property" in errors
