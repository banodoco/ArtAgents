from __future__ import annotations

import copy
import importlib.util
import inspect
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import jsonschema
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[4]
DOCS_CONTRACTS = ROOT / "docs" / "megaplan" / "epics" / "builtin-training" / "contracts"
DOCS_SCHEMAS = DOCS_CONTRACTS / "schemas"
RUNTIME_PACKAGE = ROOT / "astrid" / "packs" / "builtin" / "dataset_build"
RUNTIME_SCHEMAS = RUNTIME_PACKAGE / "schemas"

SCHEMA_VERSION_SOURCE_PROPERTY = {
    "type": "string",
    "description": "Package-local parser provenance for configs that omitted schema_version.",
    "enum": ["deprecated_inferred_v1"],
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_registry(schema_root: Path) -> Registry:
    registry = Registry()
    for path in schema_root.glob("*.schema.json"):
        schema = _load_json(path)
        registry = registry.with_resource(path.name, Resource.from_contents(schema))
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return registry


def _validator(schema_root: Path, schema_name: str) -> jsonschema.Draft7Validator:
    schema = _load_json(schema_root / schema_name)
    return jsonschema.Draft7Validator(schema, registry=_schema_registry(schema_root))


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _public_signature_map(module: ModuleType) -> dict[str, dict[str, str]]:
    class_names = [
        "SourceProvider",
        "CaptionProvider",
        "FilterStage",
        "ManifestAdapter",
        "TrainerAdapter",
        "ComputeBackend",
    ]
    signatures: dict[str, dict[str, str]] = {}
    for class_name in class_names:
        cls = getattr(module, class_name)
        members: dict[str, str] = {}
        for name, value in cls.__dict__.items():
            if name.startswith("_"):
                continue
            if isinstance(value, property):
                members[name] = f"property:{inspect.signature(value.fget)}"
            elif inspect.isfunction(value):
                members[name] = str(inspect.signature(value))
        signatures[class_name] = members
    return signatures


def test_packaged_schemas_match_frozen_m0_except_run_state_extension() -> None:
    doc_names = sorted(path.name for path in DOCS_SCHEMAS.glob("*.schema.json"))
    runtime_names = sorted(path.name for path in RUNTIME_SCHEMAS.glob("*.schema.json"))
    assert runtime_names == doc_names

    for schema_name in doc_names:
        frozen = _load_json(DOCS_SCHEMAS / schema_name)
        runtime = _load_json(RUNTIME_SCHEMAS / schema_name)
        if schema_name != "run-state.schema.json":
            assert runtime == frozen
            continue

        assert "schema_version_source" not in frozen["properties"]
        assert runtime["properties"]["schema_version_source"] == SCHEMA_VERSION_SOURCE_PROPERTY
        normalized_runtime = copy.deepcopy(runtime)
        normalized_runtime["properties"].pop("schema_version_source")
        assert normalized_runtime == frozen


def test_schema_version_source_is_package_local_to_run_state() -> None:
    for path in RUNTIME_SCHEMAS.glob("*.schema.json"):
        schema = _load_json(path)
        properties = schema.get("properties", {})
        if path.name == "run-state.schema.json":
            assert properties.get("schema_version_source") == SCHEMA_VERSION_SOURCE_PROPERTY
        else:
            assert "schema_version_source" not in properties

    frozen_run_state = _load_json(DOCS_SCHEMAS / "run-state.schema.json")
    assert "schema_version_source" not in frozen_run_state["properties"]


def test_packaged_run_state_schema_validates_m0_fixture_and_parser_provenance_extension() -> None:
    fixture = _load_json(DOCS_CONTRACTS / "fixtures" / "run-state.valid.json")
    validator = _validator(RUNTIME_SCHEMAS, "run-state.schema.json")
    validator.validate(fixture)

    with_source = {**fixture, "schema_version_source": "deprecated_inferred_v1"}
    validator.validate(with_source)

    invalid_source = {**fixture, "schema_version_source": "manual"}
    errors = sorted(validator.iter_errors(invalid_source), key=lambda error: list(error.path))
    assert errors


def test_frozen_run_state_schema_rejects_package_local_parser_provenance() -> None:
    fixture = _load_json(DOCS_CONTRACTS / "fixtures" / "run-state.valid.json")
    validator = _validator(DOCS_SCHEMAS, "run-state.schema.json")
    validator.validate(fixture)

    with_source = {**fixture, "schema_version_source": "deprecated_inferred_v1"}
    errors = sorted(validator.iter_errors(with_source), key=lambda error: list(error.path))
    assert errors
    assert any("Additional properties are not allowed" in error.message for error in errors)


def test_interfaces_port_m0_protocol_signatures() -> None:
    frozen = _load_module(DOCS_CONTRACTS / "interfaces.py", "builtin_training_m0_interfaces")
    runtime = _load_module(RUNTIME_PACKAGE / "interfaces.py", "dataset_build_runtime_interfaces")
    assert _public_signature_map(runtime) == _public_signature_map(frozen)
