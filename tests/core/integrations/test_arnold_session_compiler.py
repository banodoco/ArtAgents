from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from astrid.core.task.plan import (
    Check,
    ProducesEntry,
    RepeatForEach,
    RepeatUntil,
    Step,
    SupersededRef,
    TaskPlan,
)


def _clear_arnold_modules() -> None:
    for name in tuple(sys.modules):
        if name.startswith("astrid.core.integrations.arnold"):
            sys.modules.pop(name, None)


@dataclass(frozen=True)
class _ResumeCursorRef:
    plugin_id: str
    run_id: str
    cursor: dict[str, Any]


@dataclass(frozen=True)
class _CrossCuttingEnvelope:
    cost: dict[str, Any] = field(default_factory=dict)
    lineage: tuple[str, ...] = ()


class _RuntimeEnvelope:
    run_id = ""
    artifact_root = ""
    resume_cursor = None
    cross_cutting = _CrossCuttingEnvelope()


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
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Stage:
    stage_id: str
    label: str
    invocation: Any | None = None
    suspension: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    decision_vocabulary: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class _ParallelStage:
    stage_id: str
    label: str
    stages: tuple[Any, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Edge:
    source: str
    target: str
    label: str


@dataclass(frozen=True)
class _BuiltPipeline:
    entry_stage_id: str
    stages: tuple[_Stage, ...]
    edges: tuple[_Edge, ...]


class _BuilderWithBuild:
    instances: list["_BuilderWithBuild"] = []
    build_calls = 0

    def __init__(self) -> None:
        self.entry_stage_id: str | None = None
        self.stages: list[_Stage] = []
        self.edges: list[_Edge] = []
        type(self).instances.append(self)

    def add_stage(self, stage: _Stage) -> None:
        self.stages.append(stage)

    def add_edge(self, edge: _Edge) -> None:
        self.edges.append(edge)

    def set_entry_stage(self, stage_id: str) -> None:
        self.entry_stage_id = stage_id

    def build(self) -> _BuiltPipeline:
        type(self).build_calls += 1
        assert self.entry_stage_id is not None
        return _BuiltPipeline(
            entry_stage_id=self.entry_stage_id,
            stages=tuple(self.stages),
            edges=tuple(self.edges),
        )


class _BuilderWithoutBuild:
    instances: list["_BuilderWithoutBuild"] = []

    def __init__(self) -> None:
        self.entry_stage_id: str | None = None
        self.stages: list[_Stage] = []
        self.edges: list[_Edge] = []
        type(self).instances.append(self)

    def add_stage(self, stage: _Stage) -> None:
        self.stages.append(stage)

    def add_edge(self, edge: _Edge) -> None:
        self.edges.append(edge)

    def set_entry_stage(self, stage_id: str) -> None:
        self.entry_stage_id = stage_id


class _StepwiseDriver:
    def advance(self, envelope: object) -> _AdvanceOutcome:
        return _AdvanceOutcome()

    def checkpoint(self, envelope: object) -> _CheckpointOutcome:
        return _CheckpointOutcome()

    def resume(self, envelope: object, cursor: object) -> _RuntimeEnvelope:
        return _RuntimeEnvelope()


def _install_fake_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    builder_type: type[Any],
) -> None:
    pipeline = types.ModuleType("arnold.pipeline")
    exports = {
        "RuntimeEnvelope": _RuntimeEnvelope,
        "ResumeCursorRef": _ResumeCursorRef,
        "AdvanceOutcome": _AdvanceOutcome,
        "CheckpointOutcome": _CheckpointOutcome,
        "StepwiseDriver": _StepwiseDriver,
        "PipelineBuilder": builder_type,
        "Stage": _Stage,
        "ParallelStage": _ParallelStage,
        "Edge": _Edge,
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
    _clear_arnold_modules()
    yield
    _clear_arnold_modules()


def _import_compiler_module():
    return importlib.import_module("astrid.core.integrations.arnold.session.compiler")


def _sample_plan() -> TaskPlan:
    return TaskPlan(
        plan_id="plan-1",
        version=2,
        steps=(
            Step(
                id="prepare",
                adapter="local",
                command="echo prepare",
                version=2,
                produces=(
                    ProducesEntry(
                        name="brief",
                        path="brief.txt",
                        check=Check(check_id="file_nonempty", params={}, sentinel=False),
                    ),
                ),
            ),
            Step(
                id="review",
                adapter="manual",
                command="ack --project demo --step review",
                requires_ack=True,
                version=3,
                superseded_by=SupersededRef(to_version=4, scope="future-items"),
            ),
        ),
    )


def test_compile_plan_segment_uses_fresh_builder_and_emits_stable_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _BuilderWithBuild.instances.clear()
    _BuilderWithBuild.build_calls = 0
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()

    result_a = compiler.compile_plan_segment(
        _sample_plan(),
        project="demo",
        run_root=tmp_path / "run-a",
        state={"topic": "cats"},
        segment_id="seg-01",
    )
    result_b = compiler.compile_plan_segment(
        _sample_plan(),
        project="demo",
        run_root=tmp_path / "run-b",
        state={"topic": "cats"},
        segment_id="seg-02",
    )

    assert len(_BuilderWithBuild.instances) == 2
    assert _BuilderWithBuild.build_calls == 2
    assert result_a.entry_stage_id == "prepare"
    assert result_a.plan_hash == result_b.plan_hash
    assert result_a.pipeline_manifest["entry_stage_id"] == "prepare"
    assert [stage["stage_id"] for stage in result_a.pipeline_manifest["stages"]] == [
        "prepare",
        "review",
        "halt",
    ]
    assert result_a.pipeline_manifest["edges"] == [
        {"source": "prepare", "target": "review", "label": "next"},
        {"source": "review", "target": "halt", "label": "next"},
    ]

    built_pipeline = result_a.pipeline
    first_stage = built_pipeline.stages[0]
    second_stage = built_pipeline.stages[1]
    first_adapter = first_stage.invocation.metadata["adapter_config"]
    second_adapter = second_stage.invocation.metadata["adapter_config"]

    assert first_adapter["executor_id"] == "task.local"
    assert first_adapter["command"] == "echo prepare"
    assert first_adapter["produces"][0]["name"] == "brief"
    assert first_adapter["source_plan_path"] == ["prepare"]
    assert first_adapter["state"] == {"topic": "cats"}
    assert second_adapter["executor_id"] == "task.manual"
    assert second_adapter["requires_ack"] is True
    assert second_adapter["manual"] is True
    assert second_adapter["superseded_by"] == {
        "to_version": 4,
        "scope": "future-items",
    }
    assert second_stage.metadata["plan_step_path"] == ["review"]
    assert second_stage.metadata["adapter"] == "manual"
    assert first_stage.suspension is None
    assert second_stage.suspension is not None
    assert built_pipeline.stages[2].metadata["terminal"] is True
    assert second_stage.suspension.resume_input_schema == {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "decision": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {"type": "string", "enum": ["approve", "reject"]},
                    "notes": {"type": "string"},
                    "state_patch": {"type": "object"},
                },
                "required": ["action"],
            },
            "produces_reverify": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "artifacts": {"type": "array", "items": {"type": "string"}},
                    "inputs": {"type": "object"},
                },
            },
        },
        "required": ["decision"],
    }


def test_compile_plan_segment_does_not_require_pipeline_type(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _BuilderWithoutBuild.instances.clear()
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithoutBuild)
    compiler = _import_compiler_module()

    result = compiler.compile_plan_segment(
        _sample_plan(),
        project="demo",
        run_root=tmp_path / "run-no-build",
        state={},
        segment_id="seg-03",
    )

    assert isinstance(result.pipeline, _BuilderWithoutBuild)
    assert result.pipeline.entry_stage_id == "prepare"
    assert [stage.stage_id for stage in result.pipeline.stages] == ["prepare", "review", "halt"]
    first_stage = result.pipeline.stages[0]
    second_stage = result.pipeline.stages[1]
    assert first_stage.suspension is None
    assert second_stage.suspension is not None
    assert second_stage.suspension.resume_input_schema is not None


def test_compile_plan_segment_supports_minimal_group_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-group",
        version=2,
        steps=(
            Step(
                id="group",
                children=(Step(id="leaf", adapter="local", command="echo child"),),
            ),
        ),
    )

    result = compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / "run-group",
        state={},
        segment_id="seg-04",
    )

    assert [stage.stage_id for stage in result.pipeline.stages] == [
        "group/__enter__",
        "group/leaf",
        "group/__exit__",
        "halt",
    ]
    assert [(edge.source, edge.target, edge.label) for edge in result.pipeline.edges] == [
        ("group/__enter__", "group/leaf", "next"),
        ("group/leaf", "group/__exit__", "next"),
        ("group/__exit__", "halt", "next"),
    ]


def test_compile_plan_segment_compiles_groups_re_exports_and_optional_skip_routes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _BuilderWithBuild.instances.clear()
    _BuilderWithBuild.build_calls = 0
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-topology",
        version=2,
        steps=(
            Step(
                id="draft",
                adapter="local",
                command="echo draft",
                produces=(
                    ProducesEntry(
                        name="draft_doc",
                        path="draft.md",
                        check=Check(check_id="file_nonempty", params={}, sentinel=False),
                    ),
                ),
            ),
            Step(
                id="revise",
                children=(
                    Step(
                        id="edit",
                        adapter="local",
                        command="echo edit",
                        optional=True,
                        produces=(
                            ProducesEntry(
                                name="edited_doc",
                                path="edited.md",
                                check=Check(check_id="file_nonempty", params={}, sentinel=False),
                            ),
                        ),
                    ),
                ),
                re_export=(("final_doc", "edit.produces.edited_doc"),),
            ),
        ),
    )

    result = compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / "run-topology",
        state={"topic": "topology"},
        segment_id="seg-05",
    )

    assert result.entry_stage_id == "draft"
    assert [stage.stage_id for stage in result.pipeline.stages] == [
        "draft",
        "revise/__enter__",
        "revise/edit",
        "revise/__exit__",
        "halt",
    ]
    assert [(edge.source, edge.target, edge.label) for edge in result.pipeline.edges] == [
        ("revise/__enter__", "revise/edit", "next"),
        ("revise/edit", "revise/__exit__", "proceed"),
        ("revise/edit", "revise/__exit__", "skip"),
        ("draft", "revise/__enter__", "next"),
        ("revise/__exit__", "halt", "next"),
    ]

    edit_stage = next(stage for stage in result.pipeline.stages if stage.stage_id == "revise/edit")
    assert edit_stage.metadata["optional"] is True
    assert edit_stage.metadata["decision_vocabulary"] == ["proceed", "skip"]
    assert edit_stage.decision_vocabulary == ("proceed", "skip")

    exit_stage = next(stage for stage in result.pipeline.stages if stage.stage_id == "revise/__exit__")
    assert exit_stage.metadata["group_boundary"] == "exit"
    assert exit_stage.metadata["re_exports"] == [
        {
            "export_name": "final_doc",
            "export_ref": "edit.produces.edited_doc",
            "source_plan_path": ["revise", "edit"],
            "source_step_id": "edit",
            "produces": {
                "name": "edited_doc",
                "path": "edited.md",
                "check": {
                    "check_id": "file_nonempty",
                    "params": {},
                    "sentinel": False,
                },
                "checksum": None,
            },
            "json_path": [],
        }
    ]


def test_compile_plan_segment_fails_closed_for_unsupported_repeat_features(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _BuilderWithBuild.instances.clear()
    _BuilderWithBuild.build_calls = 0
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-repeat",
        version=2,
        steps=(
            Step(
                id="review_loop",
                adapter="local",
                command="echo review",
                produces=(
                    ProducesEntry(
                        name="verdict",
                        path="verdict.json",
                        check=Check(check_id="file_nonempty", params={}, sentinel=False),
                    ),
                ),
                repeat=RepeatUntil(
                    condition='review_loop.produces.verdict.status == "approved"',
                    max_iterations=3,
                    on_exhaust="fail",
                ),
            ),
        ),
    )

    with pytest.raises(
        compiler.CompileUnsupportedFeature,
        match="repeat.until requires static loop_condition support",
    ):
        compiler.compile_plan_segment(
            plan,
            project="demo",
            run_root=tmp_path / "run-repeat-until",
            state={},
            segment_id="seg-06",
        )

    assert _BuilderWithBuild.instances == []
    assert _BuilderWithBuild.build_calls == 0

    for_each_plan = TaskPlan(
        plan_id="plan-for-each",
        version=2,
        steps=(
            Step(
                id="fanout",
                adapter="local",
                command="echo fanout",
                repeat=RepeatForEach(items_source="static", items=("a", "b")),
            ),
        ),
    )

    with pytest.raises(
        compiler.CompileUnsupportedFeature,
        match="repeat.for_each is not supported",
    ):
        compiler.compile_plan_segment(
            for_each_plan,
            project="demo",
            run_root=tmp_path / "run-repeat-for-each",
            state={},
            segment_id="seg-07",
        )

    assert _BuilderWithBuild.instances == []
    assert _BuilderWithBuild.build_calls == 0
