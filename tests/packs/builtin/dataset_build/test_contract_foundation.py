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
RUNTIME_PACKAGE = ROOT / "astrid" / "packs" / "builtin" / "orchestrators" / "dataset_build"
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
        "RemoteExecutionBackend",
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


def test_runtime_and_frozen_schemas_accept_m2b_stage_ids_and_caption_validation_metadata() -> None:
    config = _load_json(DOCS_CONTRACTS / "fixtures" / "dataset-config.valid.json")
    config["filters"] = {
        "stages": [
            {"stage_id": "transcript_keyword_filter"},
            {"stage_id": "semantic_visual_filter"},
            {"stage_id": "semantic_video_filter"},
            {"stage_id": "near_duplicate_filter"},
        ]
    }
    config["review"]["top_up"] = {"max_rounds": 2}
    config["caption"]["validation"] = {"text_pattern": "^APPROVED:", "min_length": 10}

    item = {
        "item_id": "fixture_clip_001",
        "source_type": "local_folder",
        "source_id": "fixture",
        "source_url": "file://fixture.mp4",
        "content_hash": "0" * 64,
        "acquired_at": "2026-01-01T00:00:00Z",
        "media_type": "video",
        "media_path": "fixtures/media/fixture.mp4",
        "caption_validation": {
            "valid": False,
            "failures": [{"code": "schema_error", "message": "caption missing text", "path": "text"}],
        },
    }

    state = _load_json(DOCS_CONTRACTS / "fixtures" / "run-state.valid.json")
    state["caption_validation_failures"] = [
        {"item_id": "fixture_clip_001", "code": "schema_error", "message": "caption missing text"}
    ]
    state["quality_report"] = "runs/fixture-smoke-test/quality_report.json"
    state["acquisition_results"] = [
        {
            "provider": "local_folder",
            "round_index": 1,
            "limit_hint": 1,
            "considered": 1,
            "yielded": 0,
            "skipped_processed": 0,
            "skipped_excluded": 1,
            "skipped_duplicate_media": 0,
            "no_new_candidates": True,
            "reason": "no_new_candidates",
        }
    ]

    for schema_root in (DOCS_SCHEMAS, RUNTIME_SCHEMAS):
        _validator(schema_root, "dataset-config.schema.json").validate(config)
        _validator(schema_root, "review-item.schema.json").validate(item)

    _validator(DOCS_SCHEMAS, "run-state.schema.json").validate(state)
    runtime_state = {**state, "schema_version_source": "deprecated_inferred_v1"}
    _validator(RUNTIME_SCHEMAS, "run-state.schema.json").validate(runtime_state)


def test_training_run_config_schema_accepts_declared_required_env_contract() -> None:
    config = _load_json(DOCS_CONTRACTS / "fixtures" / "training-run-config.seinfeld.json")
    assert config["secrets"]["required_env"] == ["RUNPOD_API_KEY", "HF_TOKEN"]

    for schema_root in (DOCS_SCHEMAS, RUNTIME_SCHEMAS):
        _validator(schema_root, "training-run-config.schema.json").validate(config)


def test_interfaces_port_m0_protocol_signatures() -> None:
    frozen = _load_module(DOCS_CONTRACTS / "interfaces.py", "builtin_training_m0_interfaces")
    runtime = _load_module(RUNTIME_PACKAGE / "interfaces.py", "dataset_build_runtime_interfaces")
    assert _public_signature_map(runtime) == _public_signature_map(frozen)


def test_compute_backend_stays_lifecycle_only_and_remote_execution_is_companion_protocol() -> None:
    runtime = _load_module(RUNTIME_PACKAGE / "interfaces.py", "dataset_build_runtime_interfaces_split")

    compute_members = _public_signature_map(runtime)["ComputeBackend"]
    assert compute_members == {
        "backend_id": "property:(self) -> 'str'",
        "provision": "(self, config: 'dict[str, Any]') -> 'ComputeHandle'",
        "teardown": "(self, handle: 'ComputeHandle') -> 'None'",
        "estimate_cost": "(self, config: 'dict[str, Any]') -> 'CostEstimate'",
    }

    remote_members = _public_signature_map(runtime)["RemoteExecutionBackend"]
    assert remote_members == {
        "backend_id": "property:(self) -> 'str'",
        "capabilities": "property:(self) -> 'ProviderCapabilities'",
        "exec": "(self, handle: 'ComputeHandle', command: 'list[str]', config: 'dict[str, Any]') -> 'RemoteExecResult'",
        "pull_artifacts": "(self, handle: 'ComputeHandle', remote_paths: 'list[str]', local_dir: 'Path', config: 'dict[str, Any]') -> 'ArtifactPullResult'",
    }


def test_generic_training_backend_flow_uses_registry_protocols_not_direct_runpod_helpers(tmp_path: Path) -> None:
    runtime = _load_module(RUNTIME_PACKAGE / "interfaces.py", "dataset_build_runtime_registry_protocols")

    class FakeComputeBackend:
        backend_id = "fake"

        def __init__(self) -> None:
            self.provisioned = False
            self.torn_down = False

        def provision(self, config: dict[str, Any]):
            self.provisioned = True
            return runtime.ComputeHandle(self.backend_id, "pod-123")

        def teardown(self, handle):
            assert handle.backend == self.backend_id
            self.torn_down = True

        def estimate_cost(self, config: dict[str, Any]):
            return runtime.CostEstimate(0.25, 0.10, self.backend_id)

    class FakeRemoteExecutionBackend:
        backend_id = "fake"

        @property
        def capabilities(self):
            return runtime.ProviderCapabilities(
                self.backend_id,
                supports_exec=True,
                supports_artifact_pull=True,
                supports_cost_estimate=True,
            )

        def __init__(self) -> None:
            self.commands: list[list[str]] = []
            self.pulled: list[str] = []

        def exec(self, handle, command: list[str], config: dict[str, Any]):
            assert handle.backend == self.backend_id
            self.commands.append(command)
            return runtime.RemoteExecResult(0, stdout="ok", command=command)

        def pull_artifacts(self, handle, remote_paths: list[str], local_dir: Path, config: dict[str, Any]):
            assert handle.backend == self.backend_id
            self.pulled.extend(remote_paths)
            local = local_dir / "checkpoint.safetensors"
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_text("fake checkpoint", encoding="utf-8")
            return runtime.ArtifactPullResult([local], remote_paths)

    class FakeRegistry:
        def __init__(self) -> None:
            self.compute = FakeComputeBackend()
            self.remote = FakeRemoteExecutionBackend()

        def get_compute_backend(self, backend_id: str):
            assert backend_id == "fake"
            return self.compute

        def get_remote_execution_backend(self, backend_id: str):
            assert backend_id == "fake"
            return self.remote

    def generic_training_flow(registry: Any, backend_id: str) -> Path:
        compute = registry.get_compute_backend(backend_id)
        remote = registry.get_remote_execution_backend(backend_id)
        assert isinstance(compute, runtime.ComputeBackend)
        assert isinstance(remote, runtime.RemoteExecutionBackend)
        assert remote.capabilities.supports_exec
        assert remote.capabilities.supports_artifact_pull

        handle = compute.provision({"backend": backend_id})
        try:
            result = remote.exec(handle, ["train", "--config", "/workspace/config.yaml"], {})
            assert result.exit_code == 0
            pulled = remote.pull_artifacts(handle, ["/workspace/output/checkpoint.safetensors"], tmp_path, {})
            return pulled.local_paths[0]
        finally:
            compute.teardown(handle)

    registry = FakeRegistry()
    checkpoint = generic_training_flow(registry, "fake")

    assert checkpoint.read_text(encoding="utf-8") == "fake checkpoint"
    assert registry.compute.provisioned is True
    assert registry.compute.torn_down is True
    assert registry.remote.commands == [["train", "--config", "/workspace/config.yaml"]]
    assert registry.remote.pulled == ["/workspace/output/checkpoint.safetensors"]
