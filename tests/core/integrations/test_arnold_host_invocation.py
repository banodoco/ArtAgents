from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass, field
from typing import Any, Mapping

import pytest


def _clear_modules() -> None:
    for name in (
        "astrid.core.integrations.arnold.host.invocation",
        "astrid.core.integrations.arnold.host.compat",
        "astrid.core.integrations.arnold.host",
        "astrid.core.integrations.arnold.step_adapter",
        "astrid.core.integrations.arnold",
    ):
        sys.modules.pop(name, None)


@dataclass(frozen=True)
class _ResumeCursorRef:
    plugin_id: str = ""
    run_id: str = ""
    cursor: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _CrossCuttingEnvelope:
    cost: dict[str, Any] = field(default_factory=dict)
    lineage: tuple[str, ...] = ()


class _RuntimeEnvelope:
    run_id = ""
    artifact_root = ""
    resume_cursor = None
    cross_cutting = _CrossCuttingEnvelope()

    def __init__(
        self,
        *,
        plugin_id: str = "",
        manifest_hash: str = "",
        plugin_state_schema_version: int = 0,
        run_id: str = "",
        artifact_root: str = "",
        resume_cursor: _ResumeCursorRef | None = None,
        created_at: str = "",
        cross_cutting: _CrossCuttingEnvelope | None = None,
    ) -> None:
        self.plugin_id = plugin_id
        self.manifest_hash = manifest_hash
        self.plugin_state_schema_version = plugin_state_schema_version
        self.run_id = run_id
        self.artifact_root = artifact_root
        self.resume_cursor = resume_cursor
        self.created_at = created_at
        self.cross_cutting = cross_cutting or _CrossCuttingEnvelope()


@dataclass(frozen=True)
class _AdvanceOutcome:
    kind: str = "advanced"


@dataclass(frozen=True)
class _CheckpointOutcome:
    cursor: str = "cursor.json"


@dataclass(frozen=True)
class _Suspension:
    resume_input_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class _StepContext:
    inputs: dict[str, Any] | None = None
    hook_extensions: dict[str, Any] | None = None


@dataclass(frozen=True)
class _ContractResult:
    suspension: _Suspension | None = None


@dataclass(frozen=True)
class _StepInvocation:
    kind: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


class _StepwiseDriver:
    def advance(self, envelope: object) -> _AdvanceOutcome:
        return _AdvanceOutcome()

    def checkpoint(self, envelope: object) -> _CheckpointOutcome:
        return _CheckpointOutcome()

    def resume(self, envelope: object, cursor: object) -> _RuntimeEnvelope:
        return _RuntimeEnvelope()


def _install_fake_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = types.ModuleType("arnold.pipeline")
    exports = {
        "RuntimeEnvelope": _RuntimeEnvelope,
        "ResumeCursorRef": _ResumeCursorRef,
        "AdvanceOutcome": _AdvanceOutcome,
        "CheckpointOutcome": _CheckpointOutcome,
        "StepwiseDriver": _StepwiseDriver,
        "PipelineBuilder": type("PipelineBuilder", (), {}),
        "Stage": type("Stage", (), {}),
        "ParallelStage": type("ParallelStage", (), {}),
        "Edge": type("Edge", (), {}),
        "Suspension": _Suspension,
        "StepContext": _StepContext,
        "ExecutorHooks": type("ExecutorHooks", (), {}),
        "StepInvocation": _StepInvocation,
        "ContractResult": _ContractResult,
        "ContractStatus": type("ContractStatus", (), {"FAILED": "failed"}),
        "PipelineVerdict": type("PipelineVerdict", (), {}),
        "persist_resume_cursor": lambda *args, **kwargs: None,
        "read_resume_cursor": lambda *args, **kwargs: None,
        "EvidenceArtifactRef": type("EvidenceArtifactRef", (), {}),
        "Provenance": type("Provenance", (), {}),
        "StepResult": type("StepResult", (), {}),
        "StepInvocationAdapter": type("StepInvocationAdapter", (), {}),
        "StepInvocationAdapterRegistry": type("StepInvocationAdapterRegistry", (), {}),
        "ContentValidatorRegistry": type("ContentValidatorRegistry", (), {}),
        "no_op_content_validator": lambda *args, **kwargs: None,
    }
    for name, value in exports.items():
        setattr(pipeline, name, value)

    fake_arnold = types.ModuleType("arnold")
    fake_arnold.pipeline = pipeline
    monkeypatch.setitem(sys.modules, "arnold", fake_arnold)
    monkeypatch.setitem(sys.modules, "arnold.pipeline", pipeline)


@pytest.fixture(autouse=True)
def _clean_modules_fixture() -> None:
    _clear_modules()
    yield
    _clear_modules()


def test_allowlisted_workflow_invocations_match_adapter_metadata_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_modules()
    _install_fake_pipeline(monkeypatch)

    invocation_module = importlib.import_module("astrid.core.integrations.arnold.host.invocation")
    step_adapter = importlib.import_module("astrid.core.integrations.arnold.step_adapter")

    seen_workflows: set[str] = set()
    for workflow_id, stages in invocation_module.ALLOWLISTED_INVOCATION_TEMPLATES.items():
        for stage_id in stages:
            invocation = invocation_module.build_workflow_step_invocation(
                workflow_id,
                stage_id,
                state={"prompt": "hello", "text": "body", "candidates": ["a", "b"]},
                project="demo",
                run_root="/tmp/run-123",
                artifact_root="/tmp/run-123",
                cas_project_dir="/tmp/projects/demo",
            )
            config = step_adapter._parse_adapter_metadata(invocation.metadata)

            assert not isinstance(config, step_adapter.StepResult)
            assert invocation.kind == "model"
            assert config["executor_id"] == stages[stage_id].executor_id
            assert config["project"] == "demo"
            assert config["run_root"] == "/tmp/run-123"
            assert config["artifact_root"] == "/tmp/run-123"
            assert config["cas_project_dir"] == "/tmp/projects/demo"
            assert config["workflow_id"] == workflow_id
            assert config["stage_id"] == stage_id
            seen_workflows.add(workflow_id)

    assert seen_workflows == {
        "we.refine_image",
        "we.best_of_4",
        "text_analysis.summarize",
    }


def test_human_resume_schema_and_payload_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_modules()
    _install_fake_pipeline(monkeypatch)

    invocation_module = importlib.import_module("astrid.core.integrations.arnold.host.invocation")

    schema = invocation_module.build_human_resume_input_schema()
    payload = invocation_module.build_human_resume_payload(
        action="approve",
        notes="looks good",
        state_patch={"prompt": "refined"},
        artifacts=["produces/final.png"],
        inputs={"seed": 7},
    )
    decision, produces = invocation_module.parse_human_resume_payload(payload)

    assert schema["required"] == ["decision"]
    assert schema["properties"]["decision"]["required"] == ["action"]
    assert schema["properties"]["decision"]["properties"]["action"]["enum"] == [
        "approve",
        "reject",
    ]
    assert "produces_reverify" in schema["properties"]
    assert decision == {
        "action": "approve",
        "notes": "looks good",
        "state_patch": {"prompt": "refined"},
    }
    assert produces == {
        "artifacts": ["produces/final.png"],
        "inputs": {"seed": 7},
    }


def test_parse_human_resume_payload_fails_closed_on_invalid_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_modules()
    _install_fake_pipeline(monkeypatch)

    invocation_module = importlib.import_module("astrid.core.integrations.arnold.host.invocation")

    with pytest.raises(invocation_module.HumanResumePayloadError):
        invocation_module.parse_human_resume_payload(
            {"decision": {"action": "maybe"}}
        )

    with pytest.raises(invocation_module.HumanResumePayloadError):
        invocation_module.parse_human_resume_payload(
            {"decision": {"action": "approve"}, "produces_reverify": {"artifacts": [1]}}
        )
