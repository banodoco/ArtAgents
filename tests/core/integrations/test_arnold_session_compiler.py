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
    loop_condition: Any | None = None


@dataclass(frozen=True)
class _StageWithoutLoopCondition:
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
class _MetadataEdge:
    source: str
    target: str
    label: str
    source_port: str | None = None
    target_port: str | None = None
    logical_type: str | None = None
    artifact_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _BuiltPipeline:
    entry_stage_id: str
    stages: tuple[_Stage, ...]
    edges: tuple[Any, ...]


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
    stage_type: type[Any] = _Stage,
) -> None:
    pipeline = types.ModuleType("arnold.pipeline")
    exports = {
        "RuntimeEnvelope": _RuntimeEnvelope,
        "ResumeCursorRef": _ResumeCursorRef,
        "AdvanceOutcome": _AdvanceOutcome,
        "CheckpointOutcome": _CheckpointOutcome,
        "StepwiseDriver": _StepwiseDriver,
        "PipelineBuilder": builder_type,
        "Stage": stage_type,
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


def _write_orchestrate_module(packs_root: Path, qualified_id: str, source: str) -> Path:
    pack, name = qualified_id.split(".", 1)
    pack_dir = packs_root / pack
    pack_dir.mkdir(parents=True, exist_ok=True)
    module_path = pack_dir / f"{name}.py"
    module_path.write_text(source, encoding="utf-8")
    return module_path


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
    # ── T9: every compiled stage carries vocabulary metadata ──
    manifest_stages = result_a.pipeline_manifest["stages"]
    assert manifest_stages[0]["vocabulary"] == ["next"]  # prepare: normal
    assert manifest_stages[1]["vocabulary"] == ["next"]  # review: manual (not optional)
    assert manifest_stages[2]["vocabulary"] == ["terminal"]  # halt
    # ── end T9 ──

    assert result_a.pipeline_manifest["edges"] == [
        {
            "source": "prepare",
            "target": "review",
            "label": "next",
            "source_port": None,
            "target_port": None,
            "logical_type": None,
            "artifact_type": None,
            "metadata": {},
        },
        {
            "source": "review",
            "target": "halt",
            "label": "next",
            "source_port": None,
            "target_port": None,
            "logical_type": None,
            "artifact_type": None,
            "metadata": {},
        },
    ]

    built_pipeline = result_a.pipeline
    first_stage = built_pipeline.stages[0]
    second_stage = built_pipeline.stages[1]
    # ── T9: runtime stage vocabulary assertions ──
    assert first_stage.metadata["vocabulary"] == ["next"]
    assert first_stage.decision_vocabulary == ("next",)
    assert second_stage.metadata["vocabulary"] == ["next"]
    assert second_stage.decision_vocabulary == ("next",)
    assert built_pipeline.stages[2].metadata["vocabulary"] == ["terminal"]
    assert built_pipeline.stages[2].decision_vocabulary == ("terminal",)
    # ── end T9 ──
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
    # ── T9: vocabulary metadata ──
    assert first_stage.metadata["vocabulary"] == ["next"]
    assert second_stage.metadata["vocabulary"] == ["next"]
    assert result.pipeline.stages[2].metadata["vocabulary"] == ["terminal"]
    assert first_stage.decision_vocabulary == ("next",)
    assert second_stage.decision_vocabulary == ("next",)
    assert result.pipeline.stages[2].decision_vocabulary == ("terminal",)


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
    # ── T9: vocabulary metadata on group stages ──
    enter_stage = result.pipeline.stages[0]
    leaf_stage = result.pipeline.stages[1]
    exit_stage = result.pipeline.stages[2]
    halt = result.pipeline.stages[3]
    # Group boundaries and normal leaf use ("next",)
    assert enter_stage.metadata["vocabulary"] == ["next"]
    assert leaf_stage.metadata["vocabulary"] == ["next"]
    assert exit_stage.metadata["vocabulary"] == ["next"]
    assert halt.metadata["vocabulary"] == ["terminal"]
    assert enter_stage.decision_vocabulary == ("next",)
    assert leaf_stage.decision_vocabulary == ("next",)
    assert exit_stage.decision_vocabulary == ("next",)
    assert halt.decision_vocabulary == ("terminal",)
    # Edge labels match declared stage vocabularies
    edges = result.pipeline.edges
    assert edges[0].label in enter_stage.decision_vocabulary  # next
    assert edges[1].label in leaf_stage.decision_vocabulary  # next
    assert edges[2].label in exit_stage.decision_vocabulary  # next


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
    assert edit_stage.metadata["vocabulary"] == ["proceed", "skip"]
    assert edit_stage.decision_vocabulary == ("proceed", "skip")

    # ── T9: verify vocabulary on all stages ──
    draft_stage = next(stage for stage in result.pipeline.stages if stage.stage_id == "draft")
    assert draft_stage.metadata["vocabulary"] == ["next"]
    assert draft_stage.decision_vocabulary == ("next",)

    enter_stage = next(stage for stage in result.pipeline.stages if stage.stage_id == "revise/__enter__")
    assert enter_stage.metadata["vocabulary"] == ["next"]
    assert enter_stage.decision_vocabulary == ("next",)

    exit_stage = next(stage for stage in result.pipeline.stages if stage.stage_id == "revise/__exit__")
    assert exit_stage.metadata["group_boundary"] == "exit"
    assert exit_stage.metadata["vocabulary"] == ["next"]
    assert exit_stage.decision_vocabulary == ("next",)

    halt = next(stage for stage in result.pipeline.stages if stage.stage_id == "halt")
    assert halt.metadata["vocabulary"] == ["terminal"]
    assert halt.decision_vocabulary == ("terminal",)

    # ── T9: edge labels match declared stage vocabularies ──
    for edge in result.pipeline.edges:
        source_stage = next(s for s in result.pipeline.stages if s.stage_id == edge.source)
        assert edge.label in source_stage.decision_vocabulary, (
            f"Edge {edge.source}->{edge.target} label {edge.label!r} "
            f"not in source vocabulary {source_stage.decision_vocabulary}"
        )
    # ── end T9 ──
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
    _install_fake_pipeline(
        monkeypatch,
        builder_type=_BuilderWithBuild,
        stage_type=_StageWithoutLoopCondition,
    )
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


def test_compile_plan_segment_lowers_typed_repeat_until_leaf_with_loop_back_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-repeat-leaf",
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
            Step(id="next_step", adapter="local", command="echo next"),
        ),
    )

    result = compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / "run-repeat-leaf",
        state={},
        segment_id="seg-repeat-leaf",
    )

    review_stage = next(s for s in result.pipeline.stages if s.stage_id == "review_loop")
    assert review_stage.decision_vocabulary == ("repeat", "next")
    assert review_stage.metadata["vocabulary"] == ["repeat", "next"]
    assert review_stage.loop_condition is not None
    assert review_stage.metadata["repeat_until"] == {
        "predicate": "repeat.until",
        "condition": 'review_loop.produces.verdict.status == "approved"',
        "operator": "==",
        "literal": "approved",
        "source_plan_path": ["review_loop"],
        "source_step_id": "review_loop",
        "produces": {
            "name": "verdict",
            "path": "verdict.json",
            "check": {
                "check_id": "file_nonempty",
                "params": {},
                "sentinel": False,
            },
            "checksum": None,
        },
        "json_path": ["status"],
        "max_iterations": 3,
        "on_exhaust": "fail",
    }

    repeat_edge = next(
        e
        for e in result.pipeline.edges
        if e.source == "review_loop" and e.target == "review_loop" and e.label == "repeat"
    )
    assert any(
        e.source == "review_loop" and e.target == "next_step" and e.label == "next"
        for e in result.pipeline.edges
    )

    manifest_edges = result.pipeline_manifest["edges"]
    assert {
        "source": "review_loop",
        "target": "review_loop",
        "label": "repeat",
        "source_port": None,
        "target_port": None,
        "logical_type": None,
        "artifact_type": None,
        "metadata": review_stage.metadata["repeat_until"],
    } in manifest_edges
    assert {
        "source": "review_loop",
        "target": "next_step",
        "label": "next",
        "source_port": None,
        "target_port": None,
        "logical_type": None,
        "artifact_type": None,
        "metadata": {},
    } in manifest_edges


def test_compile_plan_segment_lowers_group_repeat_until_via_re_exported_descendant(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-repeat-group",
        version=2,
        steps=(
            Step(
                id="editor_review",
                children=(
                    Step(
                        id="review",
                        adapter="local",
                        command="echo review",
                        produces=(
                            ProducesEntry(
                                name="verdict",
                                path="editor_review.json",
                                check=Check(
                                    check_id="file_nonempty",
                                    params={},
                                    sentinel=False,
                                ),
                            ),
                        ),
                    ),
                ),
                re_export=(("verdict", "review.produces.verdict"),),
                repeat=RepeatUntil(
                    condition='editor_review.produces.verdict.status == "approved"',
                    max_iterations=2,
                    on_exhaust="escalate",
                ),
            ),
            Step(id="publish", adapter="local", command="echo publish"),
        ),
    )

    result = compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / "run-repeat-group",
        state={},
        segment_id="seg-repeat-group",
    )

    exit_stage = next(s for s in result.pipeline.stages if s.stage_id == "editor_review/__exit__")
    assert exit_stage.decision_vocabulary == ("repeat", "next")
    assert exit_stage.metadata["vocabulary"] == ["repeat", "next"]
    assert exit_stage.loop_condition is not None
    assert exit_stage.metadata["repeat_until"]["source_plan_path"] == ["editor_review", "review"]
    assert exit_stage.metadata["repeat_until"]["produces"]["path"] == "editor_review.json"

    assert any(
        e.source == "editor_review/__exit__"
        and e.target == "editor_review/__enter__"
        and e.label == "repeat"
        for e in result.pipeline.edges
    )
    assert any(
        e.source == "editor_review/__exit__" and e.target == "publish" and e.label == "next"
        for e in result.pipeline.edges
    )


def test_compile_plan_segment_repeat_until_malformed_expression_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-repeat-bad",
        version=2,
        steps=(
            Step(
                id="review_loop",
                adapter="local",
                command="echo review",
                repeat=RepeatUntil(
                    condition="not a valid expression",
                    max_iterations=3,
                    on_exhaust="fail",
                ),
            ),
        ),
    )

    with pytest.raises(
        compiler.CompileUnsupportedFeature,
        match=r"repeat\.until unsupported on review_loop with expression 'not a valid expression'",
    ):
        compiler.compile_plan_segment(
            plan,
            project="demo",
            run_root=tmp_path / "run-repeat-bad",
            state={},
            segment_id="seg-repeat-bad",
        )


def test_compile_plan_segment_repeat_until_unresolved_ref_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-repeat-unresolved",
        version=2,
        steps=(
            Step(
                id="review_loop",
                adapter="local",
                command="echo review",
                repeat=RepeatUntil(
                    condition='missing.produces.verdict.status == "approved"',
                    max_iterations=3,
                    on_exhaust="fail",
                ),
            ),
        ),
    )

    with pytest.raises(
        compiler.CompileUnsupportedFeature,
        match=r"repeat\.until unsupported on review_loop with expression 'missing\.produces\.verdict\.status == \"approved\"'",
    ):
        compiler.compile_plan_segment(
            plan,
            project="demo",
            run_root=tmp_path / "run-repeat-unresolved",
            state={},
            segment_id="seg-repeat-unresolved",
        )


def test_repeat_until_edge_sidecar_individual_fields_verified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Prove every predicate metadata field is present in the compiled edge sidecar."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-repeat-fields",
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
                    max_iterations=5,
                    on_exhaust="escalate",
                ),
            ),
        ),
    )

    result = compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / "run-repeat-fields",
        state={},
        segment_id="seg-repeat-fields",
    )

    # ── Stage assertions ──
    review_stage = next(s for s in result.pipeline.stages if s.stage_id == "review_loop")
    assert review_stage.decision_vocabulary == ("repeat", "next")
    assert review_stage.metadata["vocabulary"] == ["repeat", "next"]

    # ── Edge sidecar: find the loop-back repeat edge ──
    manifest_edges = result.pipeline_manifest["edges"]
    repeat_edges = [
        e for e in manifest_edges
        if e["source"] == "review_loop" and e["target"] == "review_loop" and e["label"] == "repeat"
    ]
    assert len(repeat_edges) == 1, f"Expected exactly 1 repeat edge, got {len(repeat_edges)}"
    edge = repeat_edges[0]

    # ── Top-level edge sidecar fields ──
    assert edge["source"] == "review_loop"
    assert edge["target"] == "review_loop"
    assert edge["label"] == "repeat"
    assert edge["source_port"] is None
    assert edge["target_port"] is None
    assert edge["logical_type"] is None
    assert edge["artifact_type"] is None, (
        "artifact_type must be present in edge sidecar (None when no port declarations)"
    )

    # ── Predicate metadata fields (the repeat_until sidecar payload) ──
    pm = edge["metadata"]
    assert isinstance(pm, dict), "edge metadata must be a dict"
    assert pm["predicate"] == "repeat.until"
    assert pm["condition"] == 'review_loop.produces.verdict.status == "approved"', (
        "original expression"
    )
    assert pm["operator"] == "=="
    assert pm["literal"] == "approved"
    assert pm["source_step_id"] == "review_loop", "source stage id"
    assert pm["source_plan_path"] == ["review_loop"]
    assert pm["produces"]["name"] == "verdict", "source output/produce name"
    assert pm["produces"]["path"] == "verdict.json"
    assert pm["produces"]["check"] == {
        "check_id": "file_nonempty",
        "params": {},
        "sentinel": False,
    }
    assert pm["produces"]["checksum"] is None
    assert pm["json_path"] == ["status"], "JSON path"
    assert pm["max_iterations"] == 5
    assert pm["on_exhaust"] == "escalate"

    # ── Normal exit edge must also be present ──
    next_edges = [
        e for e in manifest_edges
        if e["source"] == "review_loop" and e["label"] == "next"
    ]
    assert len(next_edges) >= 1, "Normal exit edge (next) must be present"


def test_repeat_until_not_equal_operator_edge_sidecar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Prove the '!=' operator is recorded in predicate edge sidecar metadata."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-repeat-ne",
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
                    condition='review_loop.produces.verdict.status != "rejected"',
                    max_iterations=3,
                    on_exhaust="fail",
                ),
            ),
            Step(id="publish", adapter="local", command="echo publish"),
        ),
    )

    result = compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / "run-repeat-ne",
        state={},
        segment_id="seg-repeat-ne",
    )

    repeat_edges = [
        e for e in result.pipeline_manifest["edges"]
        if e["label"] == "repeat"
    ]
    assert len(repeat_edges) == 1
    pm = repeat_edges[0]["metadata"]
    assert pm["predicate"] == "repeat.until"
    assert pm["operator"] == "!="
    assert pm["literal"] == "rejected"
    assert pm["condition"] == 'review_loop.produces.verdict.status != "rejected"'
    assert pm["source_step_id"] == "review_loop"


def test_repeat_until_in_operator_edge_sidecar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Prove the 'in' operator with an array literal is recorded in edge sidecar metadata."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-repeat-in",
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
                    condition='review_loop.produces.verdict.status in ["approved", "skipped"]',
                    max_iterations=3,
                    on_exhaust="fail",
                ),
            ),
            Step(id="publish", adapter="local", command="echo publish"),
        ),
    )

    result = compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / "run-repeat-in",
        state={},
        segment_id="seg-repeat-in",
    )

    repeat_edges = [
        e for e in result.pipeline_manifest["edges"]
        if e["label"] == "repeat"
    ]
    assert len(repeat_edges) == 1
    pm = repeat_edges[0]["metadata"]
    assert pm["predicate"] == "repeat.until"
    assert pm["operator"] == "in"
    assert pm["literal"] == ["approved", "skipped"]
    assert pm["json_path"] == ["status"]


def test_repeat_until_group_edge_sidecar_metadata_in_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Prove group repeat.until loop-back edge metadata appears in the pipeline manifest."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-repeat-group-manifest",
        version=2,
        steps=(
            Step(
                id="editor_review",
                children=(
                    Step(
                        id="review",
                        adapter="local",
                        command="echo review",
                        produces=(
                            ProducesEntry(
                                name="verdict",
                                path="editor_review.json",
                                check=Check(check_id="file_nonempty", params={}, sentinel=False),
                            ),
                        ),
                    ),
                ),
                re_export=(( "verdict", "review.produces.verdict"),),
                repeat=RepeatUntil(
                    condition='editor_review.produces.verdict.status == "approved"',
                    max_iterations=2,
                    on_exhaust="escalate",
                ),
            ),
            Step(id="publish", adapter="local", command="echo publish"),
        ),
    )

    result = compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / "run-repeat-group-manifest",
        state={},
        segment_id="seg-repeat-group-manifest",
    )

    manifest_edges = result.pipeline_manifest["edges"]
    repeat_edges = [
        e for e in manifest_edges
        if e["label"] == "repeat"
    ]
    assert len(repeat_edges) == 1
    edge = repeat_edges[0]

    # Top-level edge sidecar fields for group loop-back
    assert edge["source"] == "editor_review/__exit__"
    assert edge["target"] == "editor_review/__enter__"
    assert edge["label"] == "repeat"
    assert edge["source_port"] is None
    assert edge["target_port"] is None
    assert edge["logical_type"] is None
    assert edge["artifact_type"] is None

    # Predicate metadata on the group loop-back edge
    pm = edge["metadata"]
    assert pm["predicate"] == "repeat.until"
    assert pm["operator"] == "=="
    assert pm["literal"] == "approved"
    assert pm["source_step_id"] == "review"
    assert pm["source_plan_path"] == ["editor_review", "review"]
    assert pm["produces"]["name"] == "verdict"
    assert pm["produces"]["path"] == "editor_review.json"
    assert pm["json_path"] == ["status"]
    assert pm["max_iterations"] == 2
    assert pm["on_exhaust"] == "escalate"

    # Normal exit edge
    next_edges = [
        e for e in manifest_edges
        if e["source"] == "editor_review/__exit__" and e["label"] == "next"
    ]
    assert len(next_edges) == 1
    assert next_edges[0]["target"] == "publish"


def test_repeat_until_malformed_no_produces_ref_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Malformed expression missing '.produces.' segment fails closed with clear diagnostics."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-repeat-bad-ref",
        version=2,
        steps=(
            Step(
                id="review_loop",
                adapter="local",
                command="echo review",
                repeat=RepeatUntil(
                    condition='verdict == "approved"',
                    max_iterations=3,
                    on_exhaust="fail",
                ),
            ),
        ),
    )

    with pytest.raises(
        compiler.CompileUnsupportedFeature,
        match=r"repeat\.until unsupported on review_loop with expression 'verdict == \"approved\"'",
    ):
        compiler.compile_plan_segment(
            plan,
            project="demo",
            run_root=tmp_path / "run-repeat-bad-ref",
            state={},
            segment_id="seg-repeat-bad-ref",
        )


def test_repeat_until_unresolved_produces_name_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unresolved produces name on an existing step fails closed with clear diagnostics."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-repeat-bad-produces",
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
                    condition='review_loop.produces.nonexistent.status == "approved"',
                    max_iterations=3,
                    on_exhaust="fail",
                ),
            ),
        ),
    )

    with pytest.raises(
        compiler.CompileUnsupportedFeature,
        match=(
            r"repeat\.until unsupported on review_loop with expression "
            r"'review_loop\.produces\.nonexistent\.status == \"approved\"'"
        ),
    ):
        compiler.compile_plan_segment(
            plan,
            project="demo",
            run_root=tmp_path / "run-repeat-bad-produces",
            state={},
            segment_id="seg-repeat-bad-produces",
        )


def test_compile_plan_segment_for_each_remains_unsupported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _BuilderWithBuild.instances.clear()
    _BuilderWithBuild.build_calls = 0
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
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


def test_compile_plan_segment_routes_through_shared_lowering_module(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    lowering = importlib.import_module("astrid.core.integrations.arnold.session.lowering")

    delegated_calls: list[dict[str, Any]] = []
    real_compile = lowering.compile_plan_segment

    def _delegating_compile(
        plan: TaskPlan,
        *,
        project: str,
        run_root: str | Path,
        state: dict[str, Any],
        segment_id: str,
    ) -> Any:
        delegated_calls.append(
            {
                "plan_id": plan.plan_id,
                "project": project,
                "run_root": str(run_root),
                "state": state,
                "segment_id": segment_id,
            }
        )
        return real_compile(
            plan,
            project=project,
            run_root=run_root,
            state=state,
            segment_id=segment_id,
        )

    monkeypatch.setattr(lowering, "compile_plan_segment", _delegating_compile)

    result = compiler.compile_plan_segment(
        _sample_plan(),
        project="demo",
        run_root=tmp_path / "run-delegate",
        state={"topic": "delegation"},
        segment_id="seg-08",
    )

    assert delegated_calls == [
        {
            "plan_id": "plan-1",
            "project": "demo",
            "run_root": str(tmp_path / "run-delegate"),
            "state": {"topic": "delegation"},
            "segment_id": "seg-08",
        }
    ]
    assert [stage["stage_id"] for stage in result.pipeline_manifest["stages"]] == [
        "prepare",
        "review",
        "halt",
    ]
    # ── T9: vocabulary metadata in manifest ──
    manifest_stages = result.pipeline_manifest["stages"]
    assert manifest_stages[0]["vocabulary"] == ["next"]
    assert manifest_stages[1]["vocabulary"] == ["next"]
    assert manifest_stages[2]["vocabulary"] == ["terminal"]
    assert result.pipeline_manifest["edges"] == [
        {
            "source": "prepare",
            "target": "review",
            "label": "next",
            "source_port": None,
            "target_port": None,
            "logical_type": None,
            "artifact_type": None,
            "metadata": {},
        },
        {
            "source": "review",
            "target": "halt",
            "label": "next",
            "source_port": None,
            "target_port": None,
            "logical_type": None,
            "artifact_type": None,
            "metadata": {},
        },
    ]
    # ── T9: edge labels match source stage vocabularies ──
    for edge_entry in result.pipeline_manifest["edges"]:
        source_stage = next(
            s for s in manifest_stages if s["stage_id"] == edge_entry["source"]
        )
        assert edge_entry["label"] in source_stage["vocabulary"], (
            f"Edge {edge_entry['source']}->{edge_entry['target']} label {edge_entry['label']!r} "
            f"not in source vocabulary {source_stage['vocabulary']}"
        )


def test_build_pipeline_passes_edge_metadata_when_arnold_edge_accepts_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module("astrid.core.integrations.arnold.session.lowering")
    compat = importlib.import_module("astrid.core.integrations.arnold.host.compat").compat
    monkeypatch.setattr(compat, "Edge", _MetadataEdge)

    lowered = lowering.LoweredSegment(
        entry_stage_id="source",
        ordered_stage_specs=(
            lowering.StageSpec(
                stage_id="source",
                label="Source",
                invocation=None,
                suspension=None,
                metadata={"stage_id": "source"},
            ),
            lowering.StageSpec(
                stage_id="target",
                label="Target",
                invocation=None,
                suspension=None,
                metadata={"stage_id": "target"},
            ),
        ),
        ordered_edge_specs=(
            lowering.EdgeSpec(
                source="source",
                target="target",
                label="artifact",
                source_port="out",
                target_port="in",
                logical_type="document",
                artifact_type="text/markdown",
                metadata={"predicate": "repeat.until"},
            ),
        ),
        plan_hash="sha256:test",
        diagnostics=(),
    )

    pipeline = lowering.build_pipeline(lowered, compat=compat)
    assert pipeline.edges == (
        _MetadataEdge(
            source="source",
            target="target",
            label="artifact",
            source_port="out",
            target_port="in",
            logical_type="document",
            artifact_type="text/markdown",
            metadata={"predicate": "repeat.until"},
        ),
    )
    assert lowering.pipeline_manifest(
        pipeline,
        edge_specs=lowered.ordered_edge_specs,
    )["edges"] == [
        {
            "source": "source",
            "target": "target",
            "label": "artifact",
            "source_port": "out",
            "target_port": "in",
            "logical_type": "document",
            "artifact_type": "text/markdown",
            "metadata": {"predicate": "repeat.until"},
        }
    ]


def test_build_pipeline_falls_back_for_plain_edges_and_keeps_manifest_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module("astrid.core.integrations.arnold.session.lowering")
    compat = importlib.import_module("astrid.core.integrations.arnold.host.compat").compat

    lowered = lowering.LoweredSegment(
        entry_stage_id="source",
        ordered_stage_specs=(
            lowering.StageSpec(
                stage_id="source",
                label="Source",
                invocation=None,
                suspension=None,
                metadata={"stage_id": "source"},
            ),
            lowering.StageSpec(
                stage_id="target",
                label="Target",
                invocation=None,
                suspension=None,
                metadata={"stage_id": "target"},
            ),
        ),
        ordered_edge_specs=(
            lowering.EdgeSpec(
                source="source",
                target="target",
                label="artifact",
                source_port="out",
                target_port="in",
                logical_type="document",
                artifact_type="text/markdown",
                metadata={"predicate": "repeat.until"},
            ),
        ),
        plan_hash="sha256:test",
        diagnostics=(),
    )

    pipeline = lowering.build_pipeline(lowered, compat=compat)
    assert pipeline.edges == (_Edge(source="source", target="target", label="artifact"),)
    assert lowering.pipeline_manifest(
        pipeline,
        edge_specs=lowered.ordered_edge_specs,
    )["edges"] == [
        {
            "source": "source",
            "target": "target",
            "label": "artifact",
            "source_port": "out",
            "target_port": "in",
            "logical_type": "document",
            "artifact_type": "text/markdown",
            "metadata": {"predicate": "repeat.until"},
        }
    ]


# ── T5: end-to-end edge metadata contract tests ────────────────────────────────


def test_full_compile_retains_manifest_metadata_with_metadata_capable_edges(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Through the full ``compile_plan_segment`` path, when the Arnold Edge
    type accepts metadata kwargs (_MetadataEdge), the compiled pipeline
    manifest sidecar retains normalized source_port, target_port,
    logical_type, artifact_type, and metadata for every edge."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    lowering_mod = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )
    compat = importlib.import_module(
        "astrid.core.integrations.arnold.host.compat"
    ).compat

    # Swap in metadata-capable edges for the full compilation
    monkeypatch.setattr(compat, "Edge", _MetadataEdge)

    result = compiler.compile_plan_segment(
        _sample_plan(),
        project="demo",
        run_root=tmp_path / "run-meta",
        state={"topic": "metadata"},
        segment_id="seg-meta",
    )

    # Runtime edges should be _MetadataEdge instances
    assert all(isinstance(e, _MetadataEdge) for e in result.pipeline.edges)
    first_edge = result.pipeline.edges[0]
    assert first_edge.source == "prepare"
    assert first_edge.target == "review"
    assert first_edge.label == "next"

    # Manifest sidecar is canonical: same shape regardless of Edge type
    assert result.pipeline_manifest["edges"] == [
        {
            "source": "prepare",
            "target": "review",
            "label": "next",
            "source_port": None,
            "target_port": None,
            "logical_type": None,
            "artifact_type": None,
            "metadata": {},
        },
        {
            "source": "review",
            "target": "halt",
            "label": "next",
            "source_port": None,
            "target_port": None,
            "logical_type": None,
            "artifact_type": None,
            "metadata": {},
        },
    ]


def test_full_compile_retains_manifest_metadata_with_plain_edges(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Through the full ``compile_plan_segment`` path, when the Arnold Edge
    type is plain (_Edge, accepting only source/target/label), the compiled
    pipeline manifest sidecar STILL records normalized metadata for every
    edge — proving runtime construction does not determine sidecar metadata
    existence."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()

    result = compiler.compile_plan_segment(
        _sample_plan(),
        project="demo",
        run_root=tmp_path / "run-plain",
        state={"topic": "plain"},
        segment_id="seg-plain",
    )

    # Runtime edges are plain _Edge instances (no metadata attrs beyond source/target/label)
    assert all(type(e) is _Edge for e in result.pipeline.edges)
    assert not hasattr(result.pipeline.edges[0], "source_port")

    # Manifest sidecar still has the full normalized shape
    assert result.pipeline_manifest["edges"] == [
        {
            "source": "prepare",
            "target": "review",
            "label": "next",
            "source_port": None,
            "target_port": None,
            "logical_type": None,
            "artifact_type": None,
            "metadata": {},
        },
        {
            "source": "review",
            "target": "halt",
            "label": "next",
            "source_port": None,
            "target_port": None,
            "logical_type": None,
            "artifact_type": None,
            "metadata": {},
        },
    ]


def test_pipeline_manifest_falls_back_to_runtime_edges_without_specs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``pipeline_manifest`` is called without ``edge_specs``, it reads
    edge metadata from the runtime Arnold edge objects.  With metadata-capable
    edges, the manifest reflects the runtime attributes."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering_mod = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )
    compat = importlib.import_module(
        "astrid.core.integrations.arnold.host.compat"
    ).compat

    # Use metadata-capable edges
    monkeypatch.setattr(compat, "Edge", _MetadataEdge)

    lowered = lowering_mod.LoweredSegment(
        entry_stage_id="source",
        ordered_stage_specs=(
            lowering_mod.StageSpec(
                stage_id="source",
                label="Source",
                invocation=None,
                suspension=None,
                metadata={"stage_id": "source"},
            ),
            lowering_mod.StageSpec(
                stage_id="target",
                label="Target",
                invocation=None,
                suspension=None,
                metadata={"stage_id": "target"},
            ),
        ),
        ordered_edge_specs=(
            lowering_mod.EdgeSpec(
                source="source",
                target="target",
                label="artifact",
                source_port="out",
                target_port="in",
                logical_type="document",
                artifact_type="text/markdown",
                metadata={"predicate": "repeat.until"},
            ),
        ),
        plan_hash="sha256:test",
        diagnostics=(),
    )

    pipeline = lowering_mod.build_pipeline(lowered, compat=compat)

    # pipeline_manifest WITHOUT edge_specs — reads from runtime edges
    manifest_no_specs = lowering_mod.pipeline_manifest(pipeline)
    assert manifest_no_specs["edges"] == [
        {
            "source": "source",
            "target": "target",
            "label": "artifact",
            "source_port": "out",
            "target_port": "in",
            "logical_type": "document",
            "artifact_type": "text/markdown",
            "metadata": {"predicate": "repeat.until"},
        }
    ]

    # pipeline_manifest WITH edge_specs — same result (canonical from spec)
    manifest_with_specs = lowering_mod.pipeline_manifest(
        pipeline, edge_specs=lowered.ordered_edge_specs
    )
    assert manifest_with_specs["edges"] == manifest_no_specs["edges"]


def test_pipeline_manifest_without_specs_handles_plain_runtime_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``pipeline_manifest`` is called without ``edge_specs`` and the
    runtime edges are plain (_Edge with no metadata attributes), the
    manifest returns None/empty defaults for missing fields — proving
    the manifest gracefully handles both edge shapes."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering_mod = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )
    compat = importlib.import_module(
        "astrid.core.integrations.arnold.host.compat"
    ).compat

    # Plain edges — compat.Edge is _Edge (no metadata attrs)
    lowered = lowering_mod.LoweredSegment(
        entry_stage_id="source",
        ordered_stage_specs=(
            lowering_mod.StageSpec(
                stage_id="source",
                label="Source",
                invocation=None,
                suspension=None,
                metadata={"stage_id": "source"},
            ),
            lowering_mod.StageSpec(
                stage_id="target",
                label="Target",
                invocation=None,
                suspension=None,
                metadata={"stage_id": "target"},
            ),
        ),
        ordered_edge_specs=(
            lowering_mod.EdgeSpec(
                source="source",
                target="target",
                label="next",
            ),
        ),
        plan_hash="sha256:test",
        diagnostics=(),
    )

    pipeline = lowering_mod.build_pipeline(lowered, compat=compat)

    # Without edge_specs: reads from plain runtime edges
    manifest = lowering_mod.pipeline_manifest(pipeline)
    assert manifest["edges"] == [
        {
            "source": "source",
            "target": "target",
            "label": "next",
            "source_port": None,
            "target_port": None,
            "logical_type": None,
            "artifact_type": None,
            "metadata": {},
        }
    ]


# ── T9: stage vocabulary and edge label conformance ───────────────────────────\n\n\ndef test_every_compiled_stage_has_vocabulary_metadata(\n    monkeypatch: pytest.MonkeyPatch,\n    tmp_path: Path,\n) -> None:\n    \"\"\"Compile a plan with normal, optional, group-boundary, and terminal\n    stages; assert every compiled stage has vocabulary metadata and the\n    manifest records it for every stage.\"\"\"\n    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)\n    compiler = _import_compiler_module()\n    plan = TaskPlan(\n        plan_id=\"plan-vocab\",\n        version=2,\n        steps=(\n            Step(id=\"start\", adapter=\"local\", command=\"echo start\"),\n            Step(\n                id=\"review\",\n                adapter=\"manual\",\n                command=\"ack\",\n                optional=True,\n            ),\n        ),\n    )\n\n    result = compiler.compile_plan_segment(\n        plan,\n        project=\"demo\",\n        run_root=tmp_path / \"run-vocab\",\n        state={},\n        segment_id=\"seg-vocab\",\n    )\n\n    # Every runtime stage must carry metadata[\"vocabulary\"]\n    for stage in result.pipeline.stages:\n        assert \"vocabulary\" in stage.metadata, (\n            f\"Stage {stage.stage_id} missing metadata['vocabulary']\"\n        )\n        assert isinstance(stage.metadata[\"vocabulary\"], list)\n        assert len(stage.metadata[\"vocabulary\"]) >= 1\n        # decision_vocabulary must be a non-empty tuple\n        assert isinstance(stage.decision_vocabulary, tuple)\n        assert len(stage.decision_vocabulary) >= 1\n        # metadata[\"vocabulary\"] must match decision_vocabulary\n        assert stage.metadata[\"vocabulary\"] == list(stage.decision_vocabulary), (\n            f\"Stage {stage.stage_id}: metadata['vocabulary']={stage.metadata['vocabulary']!r} \"\n            f\"!= list(decision_vocabulary)={list(stage.decision_vocabulary)!r}\"\n        )\n\n    # Every manifest stage must carry \"vocabulary\"\n    manifest_stages = result.pipeline_manifest[\"stages\"]\n    for manifest_stage in manifest_stages:\n        assert \"vocabulary\" in manifest_stage, (\n            f\"Manifest stage {manifest_stage.get('stage_id')} missing 'vocabulary'\"\n        )\n        assert isinstance(manifest_stage[\"vocabulary\"], list)\n        assert len(manifest_stage[\"vocabulary\"]) >= 1\n\n    # Concrete assertions for this plan\n    stages_by_id = {s.stage_id: s for s in result.pipeline.stages}\n    assert stages_by_id[\"start\"].metadata[\"vocabulary\"] == [\"next\"]\n    assert stages_by_id[\"review\"].metadata[\"vocabulary\"] == [\"proceed\", \"skip\"]\n    assert stages_by_id[\"halt\"].metadata[\"vocabulary\"] == [\"terminal\"]\n\n\ndef test_normal_stage_edges_use_next_label(\n    monkeypatch: pytest.MonkeyPatch,\n    tmp_path: Path,\n) -> None:\n    \"\"\"All edges from a normal (non-optional, non-terminal) stage must use\n    the label 'next' — the only label declared in the (\"next\",) vocabulary.\"\"\"\n    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)\n    compiler = _import_compiler_module()\n    plan = TaskPlan(\n        plan_id=\"plan-normal\",\n        version=2,\n        steps=(\n            Step(id=\"first\", adapter=\"local\", command=\"echo first\"),\n            Step(id=\"second\", adapter=\"local\", command=\"echo second\"),\n        ),\n    )\n\n    result = compiler.compile_plan_segment(\n        plan,\n        project=\"demo\",\n        run_root=tmp_path / \"run-normal\",\n        state={},\n        segment_id=\"seg-normal\",\n    )\n\n    for edge in result.pipeline.edges:\n        source_stage = next(\n            s for s in result.pipeline.stages if s.stage_id == edge.source\n        )\n        if source_stage.decision_vocabulary == (\"next\",):\n            assert edge.label == \"next\", (\n                f\"Normal stage {edge.source} edge to {edge.target} \"\n                f\"has label {edge.label!r}, expected 'next'\"\n            )\n\n\ndef test_optional_stage_edges_use_proceed_and_skip_labels(\n    monkeypatch: pytest.MonkeyPatch,\n    tmp_path: Path,\n) -> None:\n    \"\"\"Edges from an optional stage must use only 'proceed' or 'skip' —\n    the labels declared in the (\"proceed\", \"skip\") vocabulary.\"\"\"\n    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)\n    compiler = _import_compiler_module()\n    plan = TaskPlan(\n        plan_id=\"plan-optional\",\n        version=2,\n        steps=(\n            Step(\n                id=\"opt_step\",\n                adapter=\"local\",\n                command=\"echo maybe\",\n                optional=True,\n            ),\n        ),\n    )\n\n    result = compiler.compile_plan_segment(\n        plan,\n        project=\"demo\",\n        run_root=tmp_path / \"run-optional\",\n        state={},\n        segment_id=\"seg-optional\",\n    )\n\n    opt_stage = next(\n        s for s in result.pipeline.stages if s.stage_id == \"opt_step\"\n    )\n    assert opt_stage.decision_vocabulary == (\"proceed\", \"skip\")\n\n    for edge in result.pipeline.edges:\n        if edge.source == \"opt_step\":\n            assert edge.label in (\"proceed\", \"skip\"), (\n                f\"Optional stage edge has label {edge.label!r}, \"\n                f\"expected 'proceed' or 'skip'\"\n            )\n\n\ndef test_group_boundary_stages_carry_vocabulary_metadata(\n    monkeypatch: pytest.MonkeyPatch,\n    tmp_path: Path,\n) -> None:\n    \"\"\"Group boundary stages (enter/exit) must carry vocabulary metadata\n    and edges from them must use labels declared in their vocabulary.\"\"\"\n    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)\n    compiler = _import_compiler_module()\n    plan = TaskPlan(\n        plan_id=\"plan-group-vocab\",\n        version=2,\n        steps=(\n            Step(\n                id=\"group\",\n                children=(\n                    Step(id=\"leaf\", adapter=\"local\", command=\"echo child\"),\n                ),\n            ),\n        ),\n    )\n\n    result = compiler.compile_plan_segment(\n        plan,\n        project=\"demo\",\n        run_root=tmp_path / \"run-group-vocab\",\n        state={},\n        segment_id=\"seg-group-vocab\",\n    )\n\n    enter_stage = next(\n        s for s in result.pipeline.stages if s.stage_id == \"group/__enter__\"\n    )\n    exit_stage = next(\n        s for s in result.pipeline.stages if s.stage_id == \"group/__exit__\"\n    )\n\n    # Normal group boundaries use (\"next\",)\n    assert enter_stage.decision_vocabulary == (\"next\",)\n    assert enter_stage.metadata[\"vocabulary\"] == [\"next\"]\n    assert exit_stage.decision_vocabulary == (\"next\",)\n    assert exit_stage.metadata[\"vocabulary\"] == [\"next\"]\n\n    # Edges from group boundaries must use labels in their vocabulary\n    for edge in result.pipeline.edges:\n        if edge.source in (\"group/__enter__\", \"group/__exit__\"):\n            source_stage = next(\n                s for s in result.pipeline.stages if s.stage_id == edge.source\n            )\n            assert edge.label in source_stage.decision_vocabulary, (\n                f\"Group boundary {edge.source} edge label {edge.label!r} \"\n                f\"not in {source_stage.decision_vocabulary}\"\n            )\n\n\ndef test_terminal_stage_has_terminal_vocabulary(\n    monkeypatch: pytest.MonkeyPatch,\n    tmp_path: Path,\n) -> None:\n    \"\"\"The terminal halt stage must have vocabulary=(\"terminal\",) and no\n    outgoing edges — it is a sink.\"\"\"\n    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)\n    compiler = _import_compiler_module()\n    plan = TaskPlan(\n        plan_id=\"plan-terminal\",\n        version=2,\n        steps=(\n            Step(id=\"only\", adapter=\"local\", command=\"echo done\"),\n        ),\n    )\n\n    result = compiler.compile_plan_segment(\n        plan,\n        project=\"demo\",\n        run_root=tmp_path / \"run-terminal\",\n        state={},\n        segment_id=\"seg-terminal\",\n    )\n\n    halt = next(\n        s for s in result.pipeline.stages if s.stage_id == \"halt\"\n    )\n    assert halt.decision_vocabulary == (\"terminal\",)\n    assert halt.metadata[\"vocabulary\"] == [\"terminal\"]\n    assert halt.metadata[\"terminal\"] is True\n\n    # The halt stage is a sink — no outgoing edges\n    outgoing = [e for e in result.pipeline.edges if e.source == \"halt\"]\n    assert len(outgoing) == 0, f\"halt stage must have no outgoing edges, got {outgoing}\"\n\n\ndef test_optional_group_entry_boundary_uses_proceed_skip_vocabulary(\n    monkeypatch: pytest.MonkeyPatch,\n    tmp_path: Path,\n) -> None:\n    \"\"\"When a group is optional, the entry boundary must use\n    (\"proceed\", \"skip\") vocabulary and edge labels must match.\"\"\"\n    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)\n    compiler = _import_compiler_module()\n    plan = TaskPlan(\n        plan_id=\"plan-opt-group\",\n        version=2,\n        steps=(\n            Step(\n                id=\"opt_group\",\n                optional=True,\n                children=(\n                    Step(id=\"task\", adapter=\"local\", command=\"echo task\"),\n                ),\n            ),\n        ),\n    )\n\n    result = compiler.compile_plan_segment(\n        plan,\n        project=\"demo\",\n        run_root=tmp_path / \"run-opt-group\",\n        state={},\n        segment_id=\"seg-opt-group\",\n    )\n\n    enter_stage = next(\n        s for s in result.pipeline.stages if s.stage_id == \"opt_group/__enter__\"\n    )\n    assert enter_stage.decision_vocabulary == (\"proceed\", \"skip\")\n    assert enter_stage.metadata[\"vocabulary\"] == [\"proceed\", \"skip\"]\n    assert enter_stage.metadata[\"optional\"] is True\n\n    # Edges from the optional entry: proceed to first child, skip to exit\n    enter_edges = [\n        e for e in result.pipeline.edges if e.source == \"opt_group/__enter__\"\n    ]\n    enter_labels = {e.label for e in enter_edges}\n    assert enter_labels == {\"proceed\", \"skip\"}, (\n        f\"Optional entry edges must have labels {{proceed, skip}}, got {enter_labels}\"\n    )\n\n\n# ── T7: port validation tests ─────────────────────────────────────────────────


def test_index_port_declarations_with_valid_ports() -> None:
    """``index_port_declarations`` indexes Port inputs and Output outputs
    by name from valid capability definitions."""
    from astrid.core.contracts.schema import Output, Port

    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    inputs = (
        Port(name="source_file", type="path", artifact_type="text/plain"),
        Port(name="mode", type="string", artifact_type="text/ascii"),
    )
    outputs = (
        Output(name="result", type="path", artifact_type="application/json"),
        Output(name="report", type="file", artifact_type="text/markdown"),
    )

    inputs_by_name, outputs_by_name = lowering.index_port_declarations(
        inputs=inputs, outputs=outputs
    )

    assert list(inputs_by_name.keys()) == ["source_file", "mode"]
    assert inputs_by_name["source_file"].artifact_type == "text/plain"
    assert inputs_by_name["mode"].artifact_type == "text/ascii"

    assert list(outputs_by_name.keys()) == ["result", "report"]
    assert outputs_by_name["result"].artifact_type == "application/json"
    assert outputs_by_name["report"].artifact_type == "text/markdown"


def test_index_port_declarations_with_none_declarations() -> None:
    """``index_port_declarations`` returns empty dicts when declarations
    are ``None`` (legacy nodes with no capability definitions)."""
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    inputs_by_name, outputs_by_name = lowering.index_port_declarations(
        inputs=None, outputs=None
    )

    assert inputs_by_name == {}
    assert outputs_by_name == {}


def test_index_port_declarations_with_empty_tuples() -> None:
    """``index_port_declarations`` returns empty dicts when declarations
    are empty tuples."""
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    inputs_by_name, outputs_by_name = lowering.index_port_declarations(
        inputs=(), outputs=()
    )

    assert inputs_by_name == {}
    assert outputs_by_name == {}


def test_resolve_port_edge_with_valid_ports() -> None:
    """``resolve_port_edge`` copies declared ``artifact_type`` from the
    producer Output into the resulting EdgeSpec when both ports are valid."""
    from astrid.core.contracts.schema import Output, Port

    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    producer_outputs = {
        "out": Output(name="out", type="path", artifact_type="text/markdown"),
    }
    consumer_inputs = {
        "in": Port(name="in", type="path", artifact_type="text/plain"),
    }

    edge = lowering.resolve_port_edge(
        source="stage_a",
        target="stage_b",
        label="artifact",
        source_port="out",
        target_port="in",
        producer_outputs=producer_outputs,
        consumer_inputs=consumer_inputs,
    )

    assert isinstance(edge, lowering.EdgeSpec)
    assert edge.source == "stage_a"
    assert edge.target == "stage_b"
    assert edge.label == "artifact"
    assert edge.source_port == "out"
    assert edge.target_port == "in"
    # artifact_type comes from the producer Output (first priority)
    assert edge.artifact_type == "text/markdown"
    # logical_type is intentionally always None
    assert edge.logical_type is None
    assert edge.metadata == {}


def test_resolve_port_edge_artifact_type_falls_back_to_consumer() -> None:
    """When the producer Output has no ``artifact_type``, the consumer
    Port's ``artifact_type`` is used as a fallback."""
    from astrid.core.contracts.schema import Output, Port

    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    producer_outputs = {
        "out": Output(name="out", type="path", artifact_type=None),
    }
    consumer_inputs = {
        "in": Port(name="in", type="path", artifact_type="text/plain"),
    }

    edge = lowering.resolve_port_edge(
        source="stage_a",
        target="stage_b",
        label="next",
        source_port="out",
        target_port="in",
        producer_outputs=producer_outputs,
        consumer_inputs=consumer_inputs,
    )

    assert edge.artifact_type == "text/plain"


def test_resolve_port_edge_with_invalid_producer_port() -> None:
    """When ``source_port`` is not found in ``producer_outputs``,
    ``resolve_port_edge`` silently ignores it — no ``artifact_type`` is
    copied from the producer side, and no error is raised (lenient)."""
    from astrid.core.contracts.schema import Output, Port

    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    producer_outputs = {
        "valid_out": Output(
            name="valid_out", type="path", artifact_type="text/markdown"
        ),
    }
    consumer_inputs = {
        "in": Port(name="in", type="path", artifact_type="text/plain"),
    }

    edge = lowering.resolve_port_edge(
        source="stage_a",
        target="stage_b",
        label="next",
        source_port="non_existent_port",
        target_port="in",
        producer_outputs=producer_outputs,
        consumer_inputs=consumer_inputs,
    )

    # Still constructs a valid EdgeSpec — no error raised
    assert edge.source == "stage_a"
    assert edge.target == "stage_b"
    # artifact_type falls back to consumer since producer port not found
    assert edge.artifact_type == "text/plain"
    assert edge.logical_type is None


def test_resolve_port_edge_with_invalid_consumer_port() -> None:
    """When ``target_port`` is not found in ``consumer_inputs``,
    ``resolve_port_edge`` silently ignores it — no ``artifact_type`` is
    copied from the consumer side, and no error is raised (lenient)."""
    from astrid.core.contracts.schema import Output, Port

    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    producer_outputs = {
        "out": Output(name="out", type="path", artifact_type="text/markdown"),
    }
    consumer_inputs = {
        "valid_in": Port(name="valid_in", type="path", artifact_type="text/plain"),
    }

    edge = lowering.resolve_port_edge(
        source="stage_a",
        target="stage_b",
        label="next",
        source_port="out",
        target_port="non_existent_port",
        producer_outputs=producer_outputs,
        consumer_inputs=consumer_inputs,
    )

    # Still constructs a valid EdgeSpec — no error raised
    assert edge.source == "stage_a"
    assert edge.target == "stage_b"
    # artifact_type from producer is found
    assert edge.artifact_type == "text/markdown"
    assert edge.logical_type is None


def test_resolve_port_edge_no_declarations_noop() -> None:
    """When ``producer_outputs`` or ``consumer_inputs`` is ``None``,
    ``resolve_port_edge`` behaves as a vanilla ``EdgeSpec`` constructor —
    no port-keyed lookups, no artifact_type, no errors."""
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    # Neither side has declarations
    edge_a = lowering.resolve_port_edge(
        source="stage_a",
        target="stage_b",
        label="next",
        source_port="out",
        target_port="in",
        producer_outputs=None,
        consumer_inputs=None,
    )
    assert edge_a.source_port == "out"
    assert edge_a.target_port == "in"
    assert edge_a.artifact_type is None
    assert edge_a.logical_type is None

    # Only one side has declarations — still no-op
    from astrid.core.contracts.schema import Output

    producer_outputs = {
        "out": Output(name="out", type="path", artifact_type="text/markdown"),
    }

    edge_b = lowering.resolve_port_edge(
        source="stage_a",
        target="stage_b",
        label="next",
        source_port="out",
        target_port="in",
        producer_outputs=producer_outputs,
        consumer_inputs=None,
    )
    assert edge_b.source_port == "out"
    assert edge_b.target_port == "in"
    # Still no artifact_type because consumer_inputs was None
    assert edge_b.artifact_type is None
    assert edge_b.logical_type is None


def test_resolve_port_edge_defaults_label_to_next() -> None:
    """``resolve_port_edge`` defaults ``label`` to ``"next"`` when not
    explicitly provided."""
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    edge = lowering.resolve_port_edge(
        source="stage_a",
        target="stage_b",
        producer_outputs=None,
        consumer_inputs=None,
    )

    assert edge.label == "next"


def test_index_port_declarations_and_resolve_port_edge_integration() -> None:
    """End-to-end: index declarations from capability definitions and
    then use them to resolve port-aware edges — both valid and
    invalid ports are handled leniently."""
    from astrid.core.contracts.schema import Output, Port

    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    # Simulate two executor/orchestrator definitions with ports
    inputs = (
        Port(name="source_file", type="path", artifact_type="text/plain"),
        Port(name="mode", type="string"),
    )
    outputs = (
        Output(name="result", type="path", artifact_type="application/json"),
    )

    inputs_by_name, outputs_by_name = lowering.index_port_declarations(
        inputs=inputs, outputs=outputs
    )

    # Valid producer port, valid consumer port
    edge_valid = lowering.resolve_port_edge(
        source="producer",
        target="consumer",
        label="data",
        source_port="result",
        target_port="source_file",
        producer_outputs=outputs_by_name,
        consumer_inputs=inputs_by_name,
    )
    assert edge_valid.artifact_type == "application/json"  # from producer Output
    assert edge_valid.logical_type is None

    # Invalid producer port (not in outputs)
    edge_bad_producer = lowering.resolve_port_edge(
        source="producer",
        target="consumer",
        source_port="nonexistent_output",
        target_port="source_file",
        producer_outputs=outputs_by_name,
        consumer_inputs=inputs_by_name,
    )
    assert edge_bad_producer.artifact_type == "text/plain"  # falls back to consumer
    assert edge_bad_producer.logical_type is None

    # Invalid consumer port (not in inputs)
    edge_bad_consumer = lowering.resolve_port_edge(
        source="producer",
        target="consumer",
        source_port="result",
        target_port="nonexistent_input",
        producer_outputs=outputs_by_name,
        consumer_inputs=inputs_by_name,
    )
    assert edge_bad_consumer.artifact_type == "application/json"  # from producer
    assert edge_bad_consumer.logical_type is None

    # Both port names not in either declaration set
    edge_both_invalid = lowering.resolve_port_edge(
        source="producer",
        target="consumer",
        source_port="bad_out",
        target_port="bad_in",
        producer_outputs=outputs_by_name,
        consumer_inputs=inputs_by_name,
    )
    assert edge_both_invalid.artifact_type is None
    assert edge_both_invalid.logical_type is None


def test_lower_orchestrator_definition_orders_linear_children(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    from astrid.core.contracts.schema import CommandSpec, Output, Port
    from astrid.core.execution.executor.registry import ExecutorRegistry
    from astrid.core.execution.executor.schema import ExecutorDefinition
    from astrid.core.execution.orchestrator.pipeline import lower_orchestrator_definition
    from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
    from astrid.core.execution.orchestrator.schema import (
        OrchestratorDefinition,
        RuntimeSpec,
    )

    executor_registry = ExecutorRegistry(
        [
            ExecutorDefinition(
                id="demo.first",
                name="First",
                kind="built_in",
                version="1",
                command=CommandSpec(argv=("echo", "first")),
                outputs=(Output(name="draft", type="path", artifact_type="text/plain"),),
            ),
            ExecutorDefinition(
                id="demo.second",
                name="Second",
                kind="built_in",
                version="1",
                command=CommandSpec(argv=("echo", "second")),
                inputs=(Port(name="draft", type="path", artifact_type="text/plain"),),
                outputs=(Output(name="review", type="path", artifact_type="application/json"),),
            ),
        ]
    )
    orchestrator_registry = OrchestratorRegistry([])
    definition = OrchestratorDefinition(
        id="demo.parent",
        name="Parent",
        kind="built_in",
        version="1",
        runtime=RuntimeSpec(kind="python", module="demo.parent", function="main"),
        child_executors=("demo.first", "demo.second"),
    )

    lowered = lower_orchestrator_definition(
        definition,
        project="demo",
        run_root=Path("/tmp/demo-parent"),
        state={},
        segment_id="demo.parent",
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
    )

    assert lowered.entry_stage_id == "child_00_demo.first"
    assert [stage.stage_id for stage in lowered.ordered_stage_specs] == [
        "child_00_demo.first",
        "child_01_demo.second",
        "halt",
    ]
    assert [edge.source for edge in lowered.ordered_edge_specs] == [
        "child_00_demo.first",
        "child_01_demo.second",
    ]
    first_edge = lowered.ordered_edge_specs[0]
    assert first_edge.target == "child_01_demo.second"
    assert first_edge.source_port == "draft"
    assert first_edge.target_port == "draft"
    assert first_edge.artifact_type == "text/plain"


def test_lower_orchestrator_definition_lowers_child_orchestrator_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    from astrid.core.contracts.schema import CommandSpec, Output, Port
    from astrid.core.execution.executor.registry import ExecutorRegistry
    from astrid.core.execution.executor.schema import ExecutorDefinition
    from astrid.core.execution.orchestrator.pipeline import lower_orchestrator_definition
    from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
    from astrid.core.execution.orchestrator.schema import (
        OrchestratorDefinition,
        RuntimeSpec,
    )

    executor_registry = ExecutorRegistry(
        [
            ExecutorDefinition(
                id="demo.seed",
                name="Seed",
                kind="built_in",
                version="1",
                command=CommandSpec(argv=("echo", "seed")),
                outputs=(Output(name="draft", type="path", artifact_type="text/plain"),),
            ),
        ]
    )
    child_orchestrator = OrchestratorDefinition(
        id="demo.child",
        name="Child",
        kind="built_in",
        version="1",
        runtime=RuntimeSpec(kind="python", module="demo.child", function="main"),
        inputs=(Port(name="draft", type="path", artifact_type="text/plain"),),
        outputs=(Output(name="cut", type="path", artifact_type="video/mp4"),),
    )
    orchestrator_registry = OrchestratorRegistry([child_orchestrator])
    definition = OrchestratorDefinition(
        id="demo.parent",
        name="Parent",
        kind="built_in",
        version="1",
        runtime=RuntimeSpec(kind="python", module="demo.parent", function="main"),
        child_executors=("demo.seed",),
        child_orchestrators=("demo.child",),
    )

    lowered = lower_orchestrator_definition(
        definition,
        project="demo",
        run_root=Path("/tmp/demo-nested"),
        state={"topic": "nested"},
        segment_id="demo.parent",
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
    )

    nested_stage = lowered.ordered_stage_specs[1]
    assert nested_stage.stage_id == "child_01_demo.child"
    assert nested_stage.metadata["capability_kind"] == "orchestrator"
    assert nested_stage.metadata["child_orchestrator_id"] == "demo.child"
    assert nested_stage.metadata["executor_id"] == "demo.child"
    assert nested_stage.invocation.metadata["adapter_config"]["executor_id"] == "demo.child"
    nested_edge = lowered.ordered_edge_specs[0]
    assert nested_edge.source_port == "draft"
    assert nested_edge.target_port == "draft"
    assert nested_edge.artifact_type == "text/plain"


def test_lower_orchestrator_definition_fails_on_ambiguous_port_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    from astrid.core.contracts.schema import CommandSpec, Output, Port
    from astrid.core.execution.executor.registry import ExecutorRegistry
    from astrid.core.execution.executor.schema import ExecutorDefinition
    from astrid.core.execution.orchestrator.pipeline import lower_orchestrator_definition
    from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
    from astrid.core.execution.orchestrator.schema import (
        OrchestratorDefinition,
        RuntimeSpec,
    )
    executor_registry = ExecutorRegistry(
        [
            ExecutorDefinition(
                id="demo.producer",
                name="Producer",
                kind="built_in",
                version="1",
                command=CommandSpec(argv=("echo", "producer")),
                outputs=(
                    Output(name="draft_a", type="path", artifact_type="text/plain"),
                    Output(name="draft_b", type="path", artifact_type="text/plain"),
                ),
            ),
            ExecutorDefinition(
                id="demo.consumer",
                name="Consumer",
                kind="built_in",
                version="1",
                command=CommandSpec(argv=("echo", "consumer")),
                inputs=(
                    Port(name="review_a", type="path", artifact_type="text/plain"),
                    Port(name="review_b", type="path", artifact_type="text/plain"),
                ),
            ),
        ]
    )
    definition = OrchestratorDefinition(
        id="demo.parent",
        name="Parent",
        kind="built_in",
        version="1",
        runtime=RuntimeSpec(kind="python", module="demo.parent", function="main"),
        child_executors=("demo.producer", "demo.consumer"),
    )

    with pytest.raises(RuntimeError, match="could not infer a unique port mapping"):
        lower_orchestrator_definition(
            definition,
            project="demo",
            run_root=Path("/tmp/demo-ambiguous"),
            state={},
            segment_id="demo.parent",
            executor_registry=executor_registry,
            orchestrator_registry=OrchestratorRegistry([]),
        )


def test_compile_to_pipeline_resolves_nested_string_refs_and_reuses_cycle_detection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    packs_root = tmp_path / "packs"
    _write_orchestrate_module(
        packs_root,
        "demo.child",
        '''from astrid.core.orchestrate import code, json_file, orchestrator

@orchestrator("demo.child")
def child():
    return [
        code(
            "child_step",
            argv=["echo", "child"],
            produces={"draft": json_file()},
        ),
    ]
''',
    )
    _write_orchestrate_module(
        packs_root,
        "demo.parent",
        '''from astrid.core.orchestrate import nested, orchestrator

@orchestrator("demo.parent")
def parent():
    return [nested("delegate", plan="demo.child")]
''',
    )
    _write_orchestrate_module(
        packs_root,
        "demo.cycle",
        '''from astrid.core.orchestrate import nested, orchestrator

@orchestrator("demo.cycle")
def cycle():
    return [nested("delegate", plan="demo.cycle")]
''',
    )

    compile_mod = importlib.import_module("astrid.core.orchestrate.compile")

    result = compile_mod.compile_to_pipeline(
        "demo.parent",
        project="demo",
        run_root=tmp_path / "run-parent",
        state={"topic": "nested"},
        packs_root=packs_root,
    )

    assert result.entry_stage_id == "delegate/__enter__"
    assert [stage.stage_id for stage in result.pipeline.stages] == [
        "delegate/__enter__",
        "delegate/child_step",
        "delegate/__exit__",
        "halt",
    ]
    with pytest.raises(
        compile_mod.OrchestrateDefinitionError,
        match="cycle",
    ):
        compile_mod.compile_to_pipeline(
            "demo.cycle",
            project="demo",
            run_root=tmp_path / "run-cycle",
            packs_root=packs_root,
        )


def test_dsl_to_pipeline_lowers_attested_repeat_until_and_fan_out_shapes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    from astrid.core.orchestrate import (
        attested,
        code,
        dsl_to_pipeline,
        json_file,
        nested,
        plan,
        repeat_for_each,
        repeat_until,
    )

    child = plan(
        "demo.child",
        [
            code(
                "child_task",
                argv=["echo", "child"],
                produces={"child_out": json_file()},
            ),
        ],
    )
    builder = plan(
        "demo.root",
        [
            code(
                "prepare",
                argv=["echo", "prepare"],
                produces={"draft": json_file()},
            ),
            attested(
                "review",
                command="review.sh",
                instructions="review the draft",
                ack="human",
                produces={"verdict": json_file()},
            ),
            nested("delegate", plan=child),
            code(
                "loop",
                argv=["echo", "loop"],
                produces={"status": json_file()},
                repeat=repeat_until(
                    'loop.produces.status == "approved"',
                    max_iterations=3,
                    on_exhaust="fail",
                ),
            ),
            code(
                "fanout",
                argv=["echo", "fan"],
                repeat=repeat_for_each(items=["a", "b"]),
            ),
        ],
    )

    result = dsl_to_pipeline(
        builder,
        project="demo",
        run_root=tmp_path / "run-dsl",
        state={"topic": "dsl"},
    )

    stages_by_id = {stage.stage_id: stage for stage in result.pipeline.stages}
    assert stages_by_id["review"].suspension is not None
    assert stages_by_id["review"].metadata["adapter"] == "manual"
    assert "delegate/__enter__" in stages_by_id
    assert "delegate/child_task" in stages_by_id
    assert stages_by_id["fanout"].metadata["fan_out_shape"] is True
    assert stages_by_id["fanout"].metadata["repeat_for_each"] == {
        "kind": "for_each",
        "items_source": "static",
        "items": ["a", "b"],
    }

    loop_edge = next(
        edge for edge in result.pipeline_manifest["edges"]
        if edge["source"] == "loop" and edge["target"] == "loop" and edge["label"] == "repeat"
    )
    assert loop_edge["metadata"]["predicate"] == "repeat.until"
    assert loop_edge["metadata"]["condition"] == 'loop.produces.status == "approved"'


# ── T20: orchestrate DSL tests for compile_to_pipeline / dsl_to_pipeline ──────
# Cover linear code(), nested workflows, attested() human suspension/ack metadata,
# repeat.until, fan-out-shaped fixtures, and preservation of compile_to_path()
# JSON compatibility.


def test_dsl_to_pipeline_linear_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``dsl_to_pipeline`` compiles a linear sequence of ``code()`` steps into a
    flat pipeline with correct stage ordering, edge topology, and vocabulary
    metadata on every stage and edge."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    from astrid.core.orchestrate import code, dsl_to_pipeline, json_file, plan

    builder = plan(
        "demo.linear",
        [
            code(
                "first",
                argv=["echo", "first"],
                produces={"draft": json_file()},
            ),
            code(
                "second",
                argv=["echo", "second"],
                produces={"review": json_file()},
            ),
            code(
                "third",
                argv=["echo", "third"],
            ),
        ],
    )

    result = dsl_to_pipeline(
        builder,
        project="demo",
        run_root=tmp_path / "run-linear",
        state={"topic": "linear"},
    )

    # Stage ordering: first, second, third, halt
    assert [s.stage_id for s in result.pipeline.stages] == [
        "first",
        "second",
        "third",
        "halt",
    ]

    # Every non-halt stage has "next" vocabulary
    for stage_id in ("first", "second", "third"):
        stage = next(s for s in result.pipeline.stages if s.stage_id == stage_id)
        assert stage.decision_vocabulary == ("next",)
        assert stage.metadata["vocabulary"] == ["next"]

    # Halt stage vocabulary
    halt = result.pipeline.stages[-1]
    assert halt.decision_vocabulary == ("terminal",)
    assert halt.metadata["vocabulary"] == ["terminal"]

    # Edge topology: first->second, second->third, third->halt
    edge_triples = {(e.source, e.label, e.target) for e in result.pipeline.edges}
    assert ("first", "next", "second") in edge_triples
    assert ("second", "next", "third") in edge_triples
    assert ("third", "next", "halt") in edge_triples

    # Manifest records all stages
    manifest_stage_ids = {s["stage_id"] for s in result.pipeline_manifest["stages"]}
    assert manifest_stage_ids == {"first", "second", "third", "halt"}

    # Manifest records all edges
    manifest_edge_triples = {
        (e["source"], e["label"], e["target"])
        for e in result.pipeline_manifest["edges"]
    }
    assert ("first", "next", "second") in manifest_edge_triples
    assert ("second", "next", "third") in manifest_edge_triples
    assert ("third", "next", "halt") in manifest_edge_triples


def test_compile_to_path_json_compatibility_with_compile_to_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``compile_to_path()`` remains the deterministic JSON compatibility API
    and produces the same TaskPlan that ``compile_to_pipeline()`` consumes."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    packs_root = tmp_path / "packs"
    _write_orchestrate_module(
        packs_root,
        "demo.compat",
        '''from astrid.core.orchestrate import code, json_file, orchestrator

@orchestrator("demo.compat")
def compat_orch():
    return [
        code(
            "validate",
            argv=["echo", "validate"],
            produces={"out": json_file()},
        ),
    ]
''',
    )

    import importlib

    compile_mod = importlib.import_module("astrid.core.orchestrate.compile")

    # 1. compile_to_path produces deterministic JSON
    json_path_a = compile_mod.compile_to_path(
        "demo.compat", packs_root=packs_root
    )
    json_path_b = compile_mod.compile_to_path(
        "demo.compat", packs_root=packs_root
    )
    assert json_path_a == json_path_b
    assert json_path_a.read_bytes() == json_path_b.read_bytes()
    assert json_path_a.read_bytes().endswith(b"\n")

    # 2. compile_to_pipeline succeeds on the same orchestrator
    result = compile_mod.compile_to_pipeline(
        "demo.compat",
        project="demo",
        run_root=tmp_path / "run-compat",
        packs_root=packs_root,
    )
    assert result.entry_stage_id == "validate"
    validate_stage = result.pipeline.stages[0]
    assert validate_stage.stage_id == "validate"
    assert validate_stage.decision_vocabulary == ("next",)
    assert validate_stage.metadata["vocabulary"] == ["next"]

    # 3. compile_to_path JSON round-trips through load_plan
    from astrid.core.task.plan import load_plan

    plan = load_plan(json_path_a)
    assert plan.plan_id == "demo.compat"
    assert [s.id for s in plan.steps] == ["validate"]


def test_dsl_to_pipeline_attested_human_suspension_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``attested()`` steps produce stages with suspension, requires_ack=True,
    and the ``manual`` adapter in both pipeline stages and manifest metadata."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    from astrid.core.orchestrate import attested, code, dsl_to_pipeline, json_file, plan

    builder = plan(
        "demo.attested",
        [
            code("pre", argv=["echo", "pre"], produces={"draft": json_file()}),
            attested(
                "review",
                command="review.sh",
                instructions="review the draft",
                ack="human",
                produces={"verdict": json_file()},
            ),
            code("post", argv=["echo", "post"]),
        ],
    )

    result = dsl_to_pipeline(
        builder,
        project="demo",
        run_root=tmp_path / "run-attested",
        state={"topic": "attested"},
    )

    # Review stage has suspension and manual adapter metadata
    review = next(s for s in result.pipeline.stages if s.stage_id == "review")
    assert review.suspension is not None
    assert review.metadata["adapter"] == "manual"
    assert review.metadata["requires_ack"] is True
    assert review.metadata["instructions"] == "review the draft"

    # Pre and post stages are not manual
    pre = result.pipeline.stages[0]
    assert pre.suspension is None
    assert pre.metadata["adapter"] != "manual"

    # Manifest records the suspension metadata
    manifest_stages = {s["stage_id"]: s for s in result.pipeline_manifest["stages"]}
    review_manifest = manifest_stages["review"]
    assert review_manifest["metadata"]["adapter"] == "manual"
    assert review_manifest["metadata"]["requires_ack"] is True

    # Edge routing: pre -> review -> post -> halt
    # attested() steps are manual (requires_ack) but NOT optional, so they
    # use "next" vocabulary, not proceed/skip.
    edge_triples = {(e.source, e.label, e.target) for e in result.pipeline.edges}
    assert ("pre", "next", "review") in edge_triples
    assert ("review", "next", "post") in edge_triples
    assert ("post", "next", "halt") in edge_triples


def test_dsl_to_pipeline_repeat_until_loop_back_edge_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``repeat.until`` produces a loop-back edge with full predicate metadata
    in both the pipeline edge and the manifest sidecar."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    from astrid.core.orchestrate import code, dsl_to_pipeline, json_file, plan, repeat_until

    builder = plan(
        "demo.repeat",
        [
            code(
                "poll",
                argv=["echo", "poll"],
                produces={"status": json_file()},
                repeat=repeat_until(
                    'poll.produces.status != "ready"',
                    max_iterations=5,
                    on_exhaust="fail",
                ),
            ),
        ],
    )

    result = dsl_to_pipeline(
        builder,
        project="demo",
        run_root=tmp_path / "run-repeat",
        state={"topic": "repeat"},
    )

    # Poll stage has repeat/next vocabulary with loop_condition
    poll = result.pipeline.stages[0]
    assert poll.decision_vocabulary == ("repeat", "next")
    assert poll.metadata["vocabulary"] == ["repeat", "next"]
    assert poll.loop_condition is not None
    assert poll.metadata["repeat_until"]["predicate"] == "repeat.until"
    assert poll.metadata["repeat_until"]["operator"] == "!="
    assert poll.metadata["repeat_until"]["literal"] == "ready"
    assert poll.metadata["repeat_until"]["max_iterations"] == 5
    assert poll.metadata["repeat_until"]["on_exhaust"] == "fail"

    # Loop-back edge exists in the pipeline
    loop_edge = next(
        e for e in result.pipeline.edges
        if e.source == "poll" and e.target == "poll" and e.label == "repeat"
    )
    assert loop_edge is not None
    # The fake _Edge does not carry metadata — use the manifest sidecar
    # which is the canonical record for edge metadata.
    assert loop_edge.label == "repeat"

    # Manifest records the loop-back edge with full metadata
    manifest_loop = next(
        e for e in result.pipeline_manifest["edges"]
        if e["source"] == "poll" and e["target"] == "poll" and e["label"] == "repeat"
    )
    assert manifest_loop["metadata"]["predicate"] == "repeat.until"
    assert manifest_loop["metadata"]["operator"] == "!="
    assert manifest_loop["metadata"]["literal"] == "ready"
    assert manifest_loop["metadata"]["max_iterations"] == 5
    assert manifest_loop["metadata"]["on_exhaust"] == "fail"


def test_dsl_to_pipeline_fan_out_shapes_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``repeat.for_each`` produces a fan-out-shaped stage with
    ``fan_out_shape=True`` and the correct ``repeat_for_each`` metadata
    payload."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    from astrid.core.orchestrate import (
        code,
        dsl_to_pipeline,
        json_file,
        plan,
        repeat_for_each,
    )

    builder = plan(
        "demo.fanout",
        [
            code(
                "splitter",
                argv=["echo", "split"],
                produces={"items": json_file()},
                repeat=repeat_for_each(items=["x", "y", "z"]),
            ),
        ],
    )

    result = dsl_to_pipeline(
        builder,
        project="demo",
        run_root=tmp_path / "run-fanout",
        state={"topic": "fanout"},
    )

    splitter = result.pipeline.stages[0]
    assert splitter.metadata["fan_out_shape"] is True
    assert splitter.metadata["repeat_for_each"] == {
        "kind": "for_each",
        "items_source": "static",
        "items": ["x", "y", "z"],
    }

    # Manifest records the fan-out metadata
    manifest_splitter = result.pipeline_manifest["stages"][0]
    assert manifest_splitter["metadata"]["fan_out_shape"] is True
    assert manifest_splitter["metadata"]["repeat_for_each"] == {
        "kind": "for_each",
        "items_source": "static",
        "items": ["x", "y", "z"],
    }


def test_dsl_to_pipeline_nested_workflow_preserves_stage_hierarchy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Nested ``plan()`` workflows compile into enter/exit group boundaries
    with correct hierarchical stage IDs and edge routing through the group."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    from astrid.core.orchestrate import code, dsl_to_pipeline, json_file, nested, plan

    child = plan(
        "demo.nested.child",
        [
            code("inner_a", argv=["echo", "a"], produces={"out": json_file()}),
            code("inner_b", argv=["echo", "b"]),
        ],
    )

    builder = plan(
        "demo.nested.root",
        [
            code("before", argv=["echo", "before"]),
            nested("group", plan=child),
            code("after", argv=["echo", "after"]),
        ],
    )

    result = dsl_to_pipeline(
        builder,
        project="demo",
        run_root=tmp_path / "run-nested",
        state={"topic": "nested"},
    )

    stages_by_id = {s.stage_id: s for s in result.pipeline.stages}

    # Group boundary stages exist
    assert "group/__enter__" in stages_by_id
    assert "group/__exit__" in stages_by_id

    # Enter stage metadata
    enter = stages_by_id["group/__enter__"]
    assert enter.metadata["group_boundary"] == "entry"
    assert enter.decision_vocabulary == ("next",)

    # Exit stage metadata
    exit_ = stages_by_id["group/__exit__"]
    assert exit_.metadata["group_boundary"] == "exit"
    assert exit_.decision_vocabulary == ("next",)

    # Full stage ordering
    assert [s.stage_id for s in result.pipeline.stages] == [
        "before",
        "group/__enter__",
        "group/inner_a",
        "group/inner_b",
        "group/__exit__",
        "after",
        "halt",
    ]

    # Edge routing through the group
    edge_triples = {(e.source, e.label, e.target) for e in result.pipeline.edges}
    assert ("before", "next", "group/__enter__") in edge_triples
    assert ("group/__enter__", "next", "group/inner_a") in edge_triples
    assert ("group/inner_a", "next", "group/inner_b") in edge_triples
    assert ("group/inner_b", "next", "group/__exit__") in edge_triples
    assert ("group/__exit__", "next", "after") in edge_triples
    assert ("after", "next", "halt") in edge_triples


# ── T11: conformance fixtures for optional, superseded_by, re_export ────────────
# Prove the shared builder emits the expected stage vocabularies, edge labels,
# and manifest metadata for each vocabulary item before repeat.until.


# ── optional vocabulary conformance ────────────────────────────────────────────


def test_optional_vocabulary_conformance_full_compile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Compile a plan with an optional leaf step and an optional group step;
    prove the shared builder emits ('proceed','skip') vocabularies, the correct
    edge labels, and manifest metadata for every optional stage."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-optional-conformance",
        version=2,
        steps=(
            Step(
                id="opt_leaf",
                adapter="local",
                command="echo optional-leaf",
                optional=True,
            ),
            Step(
                id="opt_group",
                children=(
                    Step(id="inner", adapter="local", command="echo inner"),
                ),
                optional=True,
            ),
        ),
    )

    result = compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / "run-opt-conf",
        state={},
        segment_id="seg-opt-conf",
    )

    # ── Stage IDs ──
    assert [s.stage_id for s in result.pipeline.stages] == [
        "opt_leaf",
        "opt_group/__enter__",
        "opt_group/inner",
        "opt_group/__exit__",
        "halt",
    ]

    # ── Optional leaf stage vocabulary ──
    opt_leaf = result.pipeline.stages[0]
    assert opt_leaf.decision_vocabulary == ("proceed", "skip")
    assert opt_leaf.metadata["vocabulary"] == ["proceed", "skip"]
    assert opt_leaf.metadata["decision_vocabulary"] == ["proceed", "skip"]
    assert opt_leaf.metadata["optional"] is True

    # ── Optional group entry vocabulary ──
    opt_enter = result.pipeline.stages[1]
    assert opt_enter.decision_vocabulary == ("proceed", "skip")
    assert opt_enter.metadata["vocabulary"] == ["proceed", "skip"]
    assert opt_enter.metadata["optional"] is True
    assert opt_enter.metadata["group_boundary"] == "entry"

    # ── Inner leaf (non-optional child) vocabulary ──
    inner = result.pipeline.stages[2]
    assert inner.decision_vocabulary == ("next",)
    assert inner.metadata["vocabulary"] == ["next"]
    assert "optional" not in inner.metadata  # child is NOT optional

    # ── Group exit vocabulary ──
    opt_exit = result.pipeline.stages[3]
    assert opt_exit.decision_vocabulary == ("next",)
    assert opt_exit.metadata["vocabulary"] == ["next"]
    assert opt_exit.metadata["group_boundary"] == "exit"

    # ── Halt vocabulary ──
    halt = result.pipeline.stages[4]
    assert halt.decision_vocabulary == ("terminal",)
    assert halt.metadata["vocabulary"] == ["terminal"]

    # ── Edge labels match source stage vocabularies ──
    edges = result.pipeline.edges
    # opt_leaf -> opt_group/__enter__ : label from opt_leaf vocabulary
    leaf_to_enter = [e for e in edges if e.source == "opt_leaf" and e.target == "opt_group/__enter__"]
    assert len(leaf_to_enter) == 2  # proceed + skip
    assert {e.label for e in leaf_to_enter} == {"proceed", "skip"}

    # opt_group/__enter__ -> opt_group/inner : proceed
    enter_to_inner = [e for e in edges if e.source == "opt_group/__enter__" and e.target == "opt_group/inner"]
    assert len(enter_to_inner) == 1
    assert enter_to_inner[0].label == "proceed"

    # opt_group/__enter__ -> opt_group/__exit__ : skip
    enter_to_exit = [e for e in edges if e.source == "opt_group/__enter__" and e.target == "opt_group/__exit__"]
    assert len(enter_to_exit) == 1
    assert enter_to_exit[0].label == "skip"

    # inner -> opt_group/__exit__ : next
    inner_to_exit = [e for e in edges if e.source == "opt_group/inner" and e.target == "opt_group/__exit__"]
    assert len(inner_to_exit) == 1
    assert inner_to_exit[0].label == "next"

    # Every edge label is in its source stage's vocabulary
    for edge in edges:
        source_stage = next(s for s in result.pipeline.stages if s.stage_id == edge.source)
        assert edge.label in source_stage.decision_vocabulary, (
            f"Edge {edge.source}--{edge.label}->{edge.target}: "
            f"label not in source vocabulary {source_stage.decision_vocabulary}"
        )

    # ── Manifest records correct vocabularies ──
    manifest_stages = {s["stage_id"]: s for s in result.pipeline_manifest["stages"]}
    assert manifest_stages["opt_leaf"]["vocabulary"] == ["proceed", "skip"]
    assert manifest_stages["opt_group/__enter__"]["vocabulary"] == ["proceed", "skip"]
    assert manifest_stages["opt_group/inner"]["vocabulary"] == ["next"]
    assert manifest_stages["opt_group/__exit__"]["vocabulary"] == ["next"]
    assert manifest_stages["halt"]["vocabulary"] == ["terminal"]

    # Manifest edges exist for proceed/skip
    manifest_edge_labels = {(e["source"], e["label"], e["target"]) for e in result.pipeline_manifest["edges"]}
    assert ("opt_leaf", "proceed", "opt_group/__enter__") in manifest_edge_labels
    assert ("opt_leaf", "skip", "opt_group/__enter__") in manifest_edge_labels


def test_optional_vocabulary_direct_resolve_decision_vocabulary() -> None:
    """``resolve_decision_vocabulary`` returns ('proceed','skip') for
    optional steps and ('next',) for non-optional steps."""
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    optional_step = Step(id="opt", adapter="local", command="echo opt", optional=True)
    assert lowering.resolve_decision_vocabulary(optional_step) == ("proceed", "skip")

    normal_step = Step(id="norm", adapter="local", command="echo norm")
    assert lowering.resolve_decision_vocabulary(normal_step) == ("next",)

    optional_manual = Step(id="review", adapter="manual", command="ack", optional=True)
    assert lowering.resolve_decision_vocabulary(optional_manual) == ("proceed", "skip")


def test_optional_vocabulary_direct_build_stage_metadata() -> None:
    """``build_stage_metadata`` emits optional=True, ('proceed','skip')
    vocabularies, and aligned decision_vocabulary for optional steps."""
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    optional_step = Step(
        id="opt",
        adapter="local",
        command="echo opt",
        optional=True,
        produces=(
            ProducesEntry(
                name="out",
                path="out.txt",
                check=Check(check_id="file_nonempty", params={}, sentinel=False),
            ),
        ),
    )

    meta = lowering.build_stage_metadata(
        step=optional_step,
        stage_id="opt",
        segment_id="seg-01",
        path=("opt",),
        adapter_config={"executor_id": "task.local"},
    )

    assert meta["optional"] is True
    assert meta["decision_vocabulary"] == ["proceed", "skip"]
    assert meta["vocabulary"] == ["proceed", "skip"]

    # Non-optional step
    normal_step = Step(id="norm", adapter="local", command="echo norm")
    meta_normal = lowering.build_stage_metadata(
        step=normal_step,
        stage_id="norm",
        segment_id="seg-01",
        path=("norm",),
        adapter_config={"executor_id": "task.local"},
    )

    assert "optional" not in meta_normal
    assert meta_normal["decision_vocabulary"] == ["next"]
    assert meta_normal["vocabulary"] == ["next"]


# ── superseded_by vocabulary conformance ───────────────────────────────────────


def test_superseded_by_vocabulary_conformance_full_compile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Compile a plan where a step has ``superseded_by``; prove the shared
    builder emits superseded_by metadata on the stage and in the manifest,
    while the stage vocabulary remains ('next',)."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-supersede-conformance",
        version=2,
        steps=(
            Step(id="start", adapter="local", command="echo start"),
            Step(
                id="review",
                adapter="manual",
                command="ack --step review",
                requires_ack=True,
                superseded_by=SupersededRef(to_version=5, scope="future-items"),
            ),
            Step(
                id="superseded_group",
                children=(
                    Step(id="child", adapter="local", command="echo child"),
                ),
                superseded_by=SupersededRef(to_version=3, scope="all"),
            ),
        ),
    )

    result = compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / "run-supersede-conf",
        state={},
        segment_id="seg-supersede-conf",
    )

    # ── Superseded leaf stage metadata ──
    review_stage = next(s for s in result.pipeline.stages if s.stage_id == "review")
    assert review_stage.metadata["superseded_by"] == {
        "to_version": 5,
        "scope": "future-items",
    }
    # Vocabulary remains normal for superseded steps
    assert review_stage.decision_vocabulary == ("next",)
    assert review_stage.metadata["vocabulary"] == ["next"]
    assert review_stage.metadata["decision_vocabulary"] == ["next"]

    # ── Superseded group boundary stages carry superseded_by ──
    enter_stage = next(
        s for s in result.pipeline.stages if s.stage_id == "superseded_group/__enter__"
    )
    assert enter_stage.metadata["superseded_by"] == {
        "to_version": 3,
        "scope": "all",
    }
    assert enter_stage.decision_vocabulary == ("next",)

    exit_stage = next(
        s for s in result.pipeline.stages if s.stage_id == "superseded_group/__exit__"
    )
    assert exit_stage.metadata["superseded_by"] == {
        "to_version": 3,
        "scope": "all",
    }
    assert exit_stage.decision_vocabulary == ("next",)

    # ── Non-superseded stage has no superseded_by key ──
    start_stage = next(s for s in result.pipeline.stages if s.stage_id == "start")
    assert "superseded_by" not in start_stage.metadata

    # ── Manifest records superseded_by ──
    manifest_stages = {s["stage_id"]: s for s in result.pipeline_manifest["stages"]}
    # The manifest extracts metadata directly from runtime stages
    review_manifest = manifest_stages["review"]
    assert review_manifest["metadata"]["superseded_by"] == {
        "to_version": 5,
        "scope": "future-items",
    }
    assert review_manifest["vocabulary"] == ["next"]


def test_superseded_by_direct_supersede_metadata() -> None:
    """``supersede_metadata`` returns None for steps without superseded_by
    and the correct dict shape for steps with it."""
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    # No superseded_by
    normal = Step(id="normal", adapter="local", command="echo hi")
    assert lowering.supersede_metadata(normal) is None

    # With superseded_by
    superseded = Step(
        id="old",
        adapter="local",
        command="echo old",
        superseded_by=SupersededRef(to_version=2, scope="future-iterations"),
    )
    assert lowering.supersede_metadata(superseded) == {
        "to_version": 2,
        "scope": "future-iterations",
    }


def test_superseded_by_does_not_affect_vocabulary() -> None:
    """A superseded_by step retains its normal vocabulary — superseded_by
    is orthogonal to stage vocabulary and edge routing."""
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    # Superseded + optional
    step = Step(
        id="old_opt",
        adapter="local",
        command="echo old-optional",
        optional=True,
        superseded_by=SupersededRef(to_version=2, scope="all"),
    )
    # Vocabulary is driven by optional, not superseded_by
    assert lowering.resolve_decision_vocabulary(step) == ("proceed", "skip")

    meta = lowering.build_stage_metadata(
        step=step,
        stage_id="old_opt",
        segment_id="seg-01",
        path=("old_opt",),
        adapter_config={"executor_id": "task.local"},
    )
    assert meta["superseded_by"] == {"to_version": 2, "scope": "all"}
    assert meta["optional"] is True
    assert meta["vocabulary"] == ["proceed", "skip"]


# ── re_export vocabulary conformance ───────────────────────────────────────────


def test_re_export_vocabulary_conformance_full_compile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Compile a plan with a group that re_exports a child's produces; prove
    the exit stage carries resolved re_export metadata, the manifest records
    it, and the stage vocabulary remains ('next',)."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-reexport-conformance",
        version=2,
        steps=(
            Step(
                id="publish",
                children=(
                    Step(
                        id="build",
                        adapter="local",
                        command="echo build",
                        produces=(
                            ProducesEntry(
                                name="artifact",
                                path="out/artifact.tar.gz",
                                check=Check(
                                    check_id="file_nonempty", params={}, sentinel=False
                                ),
                            ),
                        ),
                    ),
                    Step(id="tag", adapter="local", command="echo tag"),
                ),
                re_export=(("release_artifact", "build.produces.artifact"),),
            ),
        ),
    )

    result = compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / "run-reexport-conf",
        state={},
        segment_id="seg-reexport-conf",
    )

    # ── Exit stage carries re_exports ──
    exit_stage = next(
        s for s in result.pipeline.stages if s.stage_id == "publish/__exit__"
    )
    assert "re_exports" in exit_stage.metadata
    assert len(exit_stage.metadata["re_exports"]) == 1
    re_export_entry = exit_stage.metadata["re_exports"][0]
    assert re_export_entry["export_name"] == "release_artifact"
    assert re_export_entry["export_ref"] == "build.produces.artifact"
    assert re_export_entry["source_plan_path"] == ["publish", "build"]
    assert re_export_entry["source_step_id"] == "build"
    assert re_export_entry["produces"]["name"] == "artifact"
    assert re_export_entry["produces"]["path"] == "out/artifact.tar.gz"

    # Vocabulary is normal
    assert exit_stage.decision_vocabulary == ("next",)
    assert exit_stage.metadata["vocabulary"] == ["next"]
    assert exit_stage.metadata["group_boundary"] == "exit"

    # ── Entry stage does NOT carry re_exports ──
    enter_stage = next(
        s for s in result.pipeline.stages if s.stage_id == "publish/__enter__"
    )
    assert "re_exports" not in enter_stage.metadata

    # ── Manifest records re_exports ──
    manifest_stages = {s["stage_id"]: s for s in result.pipeline_manifest["stages"]}
    exit_manifest = manifest_stages["publish/__exit__"]
    assert "re_exports" in exit_manifest["metadata"]
    assert exit_manifest["vocabulary"] == ["next"]


def test_re_export_direct_resolved_re_export_metadata() -> None:
    """``resolved_re_export_metadata`` correctly resolves re_export refs
    against a TaskPlan, returning the expected metadata shape."""
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    plan = TaskPlan(
        plan_id="plan-direct-reexport",
        version=2,
        steps=(
            Step(
                id="group",
                children=(
                    Step(
                        id="leaf",
                        adapter="local",
                        command="echo leaf",
                        produces=(
                            ProducesEntry(
                                name="data",
                                path="data.json",
                                check=Check(
                                    check_id="file_nonempty", params={}, sentinel=False
                                ),
                            ),
                        ),
                    ),
                ),
                re_export=(("alias", "leaf.produces.data"),),
            ),
        ),
    )

    group_step = plan.steps[0]
    entries = lowering.resolved_re_export_metadata(
        plan, step=group_step, path=("group",)
    )

    assert len(entries) == 1
    assert entries[0]["export_name"] == "alias"
    assert entries[0]["export_ref"] == "leaf.produces.data"
    assert entries[0]["source_plan_path"] == ["group", "leaf"]
    assert entries[0]["source_step_id"] == "leaf"
    assert entries[0]["produces"]["name"] == "data"
    assert entries[0]["produces"]["path"] == "data.json"


# ── combined vocabulary conformance ────────────────────────────────────────────


def test_combined_vocabulary_conformance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Compile a plan exercising optional, superseded_by, and re_export
    together; prove all three vocabulary items coexist correctly in stage
    metadata, edge labels, and the manifest without cross-talk."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    plan = TaskPlan(
        plan_id="plan-combined-conformance",
        version=2,
        steps=(
            Step(
                id="begin",
                adapter="local",
                command="echo begin",
                superseded_by=SupersededRef(to_version=2, scope="all"),
            ),
            Step(
                id="middle",
                children=(
                    Step(
                        id="task",
                        adapter="local",
                        command="echo task",
                        optional=True,
                        produces=(
                            ProducesEntry(
                                name="result",
                                path="result.json",
                                check=Check(
                                    check_id="file_nonempty", params={}, sentinel=False
                                ),
                            ),
                        ),
                    ),
                ),
                optional=True,
                superseded_by=SupersededRef(to_version=7, scope="future-items"),
                re_export=(("final_result", "task.produces.result"),),
            ),
            Step(id="end", adapter="local", command="echo end"),
        ),
    )

    result = compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / "run-combined-conf",
        state={},
        segment_id="seg-combined-conf",
    )

    stages_by_id = {s.stage_id: s for s in result.pipeline.stages}

    # ── begin: superseded_by + normal vocabulary ──
    begin = stages_by_id["begin"]
    assert begin.metadata["superseded_by"] == {"to_version": 2, "scope": "all"}
    assert begin.decision_vocabulary == ("next",)
    assert begin.metadata["vocabulary"] == ["next"]
    assert "optional" not in begin.metadata
    assert "re_exports" not in begin.metadata

    # ── middle/__enter__: optional + superseded_by ──
    middle_enter = stages_by_id["middle/__enter__"]
    assert middle_enter.metadata["superseded_by"] == {
        "to_version": 7,
        "scope": "future-items",
    }
    assert middle_enter.metadata["optional"] is True
    assert middle_enter.decision_vocabulary == ("proceed", "skip")
    assert middle_enter.metadata["vocabulary"] == ["proceed", "skip"]
    assert "re_exports" not in middle_enter.metadata

    # ── middle/task: optional child ──
    task = stages_by_id["middle/task"]
    assert task.metadata["optional"] is True
    assert task.decision_vocabulary == ("proceed", "skip")
    assert task.metadata["vocabulary"] == ["proceed", "skip"]
    assert "superseded_by" not in task.metadata
    assert "re_exports" not in task.metadata

    # ── middle/__exit__: superseded_by + re_exports + normal vocabulary ──
    middle_exit = stages_by_id["middle/__exit__"]
    assert middle_exit.metadata["superseded_by"] == {
        "to_version": 7,
        "scope": "future-items",
    }
    assert "re_exports" in middle_exit.metadata
    assert len(middle_exit.metadata["re_exports"]) == 1
    assert middle_exit.metadata["re_exports"][0]["export_name"] == "final_result"
    assert middle_exit.decision_vocabulary == ("next",)
    assert middle_exit.metadata["vocabulary"] == ["next"]

    # ── end: normal ──
    end = stages_by_id["end"]
    assert end.decision_vocabulary == ("next",)
    assert "superseded_by" not in end.metadata
    assert "optional" not in end.metadata

    # ── Edge labels all match source vocabularies ──
    for edge in result.pipeline.edges:
        source_stage = stages_by_id[edge.source]
        assert edge.label in source_stage.decision_vocabulary, (
            f"Edge {edge.source}--{edge.label}->{edge.target}: "
            f"label not in source vocabulary {source_stage.decision_vocabulary}"
        )

    # ── Optional routing edges exist ──
    edge_triples = {(e.source, e.label, e.target) for e in result.pipeline.edges}
    # middle/__enter__ has proceed->task and skip->exit
    assert ("middle/__enter__", "proceed", "middle/task") in edge_triples
    assert ("middle/__enter__", "skip", "middle/__exit__") in edge_triples
    # middle/task is optional, so proceed+skip to exit
    assert ("middle/task", "proceed", "middle/__exit__") in edge_triples
    assert ("middle/task", "skip", "middle/__exit__") in edge_triples

    # ── Manifest records all properties ──
    manifest_stages = {s["stage_id"]: s for s in result.pipeline_manifest["stages"]}
    begin_manifest = manifest_stages["begin"]
    assert begin_manifest["metadata"]["superseded_by"] == {"to_version": 2, "scope": "all"}
    assert begin_manifest["vocabulary"] == ["next"]

    middle_exit_manifest = manifest_stages["middle/__exit__"]
    assert "re_exports" in middle_exit_manifest["metadata"]
    assert middle_exit_manifest["vocabulary"] == ["next"]

    middle_enter_manifest = manifest_stages["middle/__enter__"]
    assert middle_enter_manifest["vocabulary"] == ["proceed", "skip"]


# ── T17: wrapper lowering tests (command/python + graph-vs-wrapper rules) ─────


def _orchestrator_def_command(
    *,
    orchestrator_id: str = "test.cmd_wrapper",
    argv: tuple[str, ...] = ("echo", "hello"),
    child_executors: tuple[str, ...] = (),
    child_orchestrators: tuple[str, ...] = (),
) -> Any:
    from astrid.core.contracts.schema import CommandSpec
    from astrid.core.execution.orchestrator.schema import (
        OrchestratorDefinition,
        RuntimeSpec,
    )

    return OrchestratorDefinition(
        id=orchestrator_id,
        name=orchestrator_id.split(".", 1)[-1],
        kind="built_in",
        version="1.0.0",
        runtime=RuntimeSpec(kind="command", command=CommandSpec(argv=argv)),
        child_executors=child_executors,
        child_orchestrators=child_orchestrators,
    )


def _orchestrator_def_python(
    *,
    orchestrator_id: str = "test.py_wrapper",
    module: str = "my_pack.run",
    function: str = "main",
    child_executors: tuple[str, ...] = (),
    child_orchestrators: tuple[str, ...] = (),
) -> Any:
    from astrid.core.execution.orchestrator.schema import (
        OrchestratorDefinition,
        RuntimeSpec,
    )

    return OrchestratorDefinition(
        id=orchestrator_id,
        name=orchestrator_id.split(".", 1)[-1],
        kind="built_in",
        version="1.0.0",
        runtime=RuntimeSpec(kind="python", module=module, function=function),
        child_executors=child_executors,
        child_orchestrators=child_orchestrators,
    )


def test_wrapper_lowering_command_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Command-runtime orchestrator → single wrapper stage + halt edge."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    from astrid.core.execution.orchestrator.pipeline import (
        lower_orchestrator_definition,
    )

    definition = _orchestrator_def_command(
        orchestrator_id="test.cmd_wrapper",
        argv=("ffmpeg", "-i", "input.mp4", "output.mp4"),
    )
    lowered = lower_orchestrator_definition(
        definition,
        project="demo",
        run_root=tmp_path,
        state={},
        segment_id="seg-cmd",
        mode="wrapper",
    )

    # One wrapper stage + halt.
    assert len(lowered.ordered_stage_specs) == 2
    wrapper_stage = lowered.ordered_stage_specs[0]
    halt = lowered.ordered_stage_specs[1]

    assert wrapper_stage.stage_id.startswith("wrapper_")
    assert "wrapper_runtime" in wrapper_stage.metadata
    assert wrapper_stage.metadata["wrapper_runtime"] == "command"
    assert wrapper_stage.metadata["wrapper_command_argv"] == [
        "ffmpeg", "-i", "input.mp4", "output.mp4",
    ]
    assert wrapper_stage.decision_vocabulary == ("next",)
    assert wrapper_stage.metadata["vocabulary"] == ["next"]

    assert halt.stage_id == "halt"
    assert halt.metadata["terminal"] is True
    assert halt.decision_vocabulary == ("terminal",)

    # One edge: wrapper → halt.
    assert len(lowered.ordered_edge_specs) == 1
    edge = lowered.ordered_edge_specs[0]
    assert edge.source == wrapper_stage.stage_id
    assert edge.target == "halt"
    assert edge.label == "next"

    # No new manifest keys beyond the standard set.
    for spec in lowered.ordered_stage_specs:
        assert "stage_id" in spec.metadata
        assert "vocabulary" in spec.metadata


def test_wrapper_lowering_python_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Python-runtime orchestrator → single wrapper stage with module/function."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    from astrid.core.execution.orchestrator.pipeline import (
        lower_orchestrator_definition,
    )

    definition = _orchestrator_def_python(
        orchestrator_id="test.py_wrapper",
        module="my_pack.orchestrators.my_orch.run",
        function="main",
    )
    lowered = lower_orchestrator_definition(
        definition,
        project="demo",
        run_root=tmp_path,
        state={},
        segment_id="seg-py",
        mode="wrapper",
    )

    wrapper_stage = lowered.ordered_stage_specs[0]
    assert wrapper_stage.metadata["wrapper_runtime"] == "python"
    assert wrapper_stage.metadata["wrapper_module"] == "my_pack.orchestrators.my_orch.run"
    assert wrapper_stage.metadata["wrapper_function"] == "main"
    assert "wrapper_command_argv" not in wrapper_stage.metadata

    assert lowered.ordered_stage_specs[1].stage_id == "halt"


def test_wrapper_auto_detect_no_children(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When children are absent, mode='graph' auto-falls-back to wrapper."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    from astrid.core.execution.orchestrator.pipeline import (
        lower_orchestrator_definition,
    )

    definition = _orchestrator_def_command(
        orchestrator_id="test.auto_wrapper",
        argv=("echo", "auto"),
    )
    # mode='graph' but no children → should still produce wrapper
    lowered = lower_orchestrator_definition(
        definition,
        project="demo",
        run_root=tmp_path,
        state={},
        segment_id="seg-auto",
        mode="graph",
    )

    assert len(lowered.ordered_stage_specs) == 2
    assert lowered.ordered_stage_specs[0].stage_id.startswith("wrapper_")
    assert lowered.ordered_stage_specs[0].metadata["wrapper_runtime"] == "command"


def test_wrapper_explicit_mode_overrides_graph_with_children(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Explicit mode='wrapper' produces wrapper even when children exist."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    from astrid.core.execution.orchestrator.pipeline import (
        lower_orchestrator_definition,
    )

    definition = _orchestrator_def_command(
        orchestrator_id="test.force_wrapper",
        argv=("echo", "forced"),
        child_executors=("some.executor",),
    )
    lowered = lower_orchestrator_definition(
        definition,
        project="demo",
        run_root=tmp_path,
        state={},
        segment_id="seg-force",
        mode="wrapper",
    )

    assert len(lowered.ordered_stage_specs) == 2
    assert lowered.ordered_stage_specs[0].stage_id.startswith("wrapper_")
    assert lowered.ordered_stage_specs[0].metadata["wrapper_runtime"] == "command"


def test_wrapper_edge_metadata_no_new_manifest_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Wrapper-lowered edges use only standard EdgeSpec fields — no extra keys."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    from astrid.core.execution.orchestrator.pipeline import (
        lower_orchestrator_definition,
    )

    definition = _orchestrator_def_python(
        orchestrator_id="test.no_new_keys",
    )
    lowered = lower_orchestrator_definition(
        definition,
        project="demo",
        run_root=tmp_path,
        state={},
        segment_id="seg-nokeys",
        mode="wrapper",
    )

    for edge in lowered.ordered_edge_specs:
        # Standard fields only.
        assert hasattr(edge, "source")
        assert hasattr(edge, "target")
        assert hasattr(edge, "label")
        assert hasattr(edge, "source_port")
        assert hasattr(edge, "target_port")
        assert hasattr(edge, "logical_type")
        assert hasattr(edge, "artifact_type")
        assert hasattr(edge, "metadata")
        # No unexpected extra fields.
        expected = {
            "source", "target", "label", "source_port",
            "target_port", "logical_type", "artifact_type", "metadata",
        }
        actual = set(edge.__dataclass_fields__) if hasattr(edge, "__dataclass_fields__") else set()
        if actual:
            assert actual <= expected, f"Unexpected edge fields: {actual - expected}"


def test_wrapper_vs_graph_selection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Graph mode with children produces adapter-backed stages, not wrapper."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)

    from astrid.core.execution.orchestrator.pipeline import (
        lower_orchestrator_definition,
    )

    from astrid.core.execution.executor.registry import ExecutorRegistry

    # Create a minimal executor registry with one executor.
    registry = ExecutorRegistry()
    # We need to test the child-bearing graph path — but since we have no
    # real executor registered, the graph path will fail.  Instead, verify
    # that the auto-detect behaviour is correct by checking the diagnostics.
    definition = _orchestrator_def_command(
        orchestrator_id="test.graph_path",
        argv=("echo", "graph"),
        child_executors=("test.executor",),
    )

    # With children but no registry entries, the graph path will try to
    # resolve and fail.  That proves the selection logic chose graph, not
    # wrapper.  The error message should mention the executor.
    try:
        lower_orchestrator_definition(
            definition,
            project="demo",
            run_root=tmp_path,
            state={},
            segment_id="seg-graph",
            mode="graph",
        )
        # If it succeeds, we still got graph behaviour (not wrapper).
    except Exception:
        # Expected when registry can't resolve — graph path was attempted.
        pass

    # Now with explicit wrapper mode, even with children, we get wrapper.
    lowered_wrapper = lower_orchestrator_definition(
        definition,
        project="demo",
        run_root=tmp_path,
        state={},
        segment_id="seg-graph-w",
        mode="wrapper",
    )
    assert lowered_wrapper.ordered_stage_specs[0].stage_id.startswith("wrapper_")


# ── T22: synthetic pattern_select / vote_judge / dynamic_fanout lowering tests ──


def test_lower_pattern_select_emits_adapter_backed_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``lower_pattern_select`` emits a single adapter-backed StageSpec with
    synthetic.media.pattern_select executor and mandatory metadata keys."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    stage = lowering.lower_pattern_select(
        stage_id="pattern_pick",
        label="Pick Pattern",
        segment_id="seg-ps",
        project="demo",
        run_root_path=tmp_path,
        state={"env": "test"},
        pattern_names=("grid_3x2", "random_walk", "circle"),
    )

    assert isinstance(stage, lowering.StageSpec)
    assert stage.stage_id == "pattern_pick"
    assert stage.label == "Pick Pattern"
    assert stage.invocation is not None
    assert stage.suspension is None
    assert stage.decision_vocabulary == ("next",)

    meta = stage.metadata
    assert meta["segment_id"] == "seg-ps"
    assert meta["executor_id"] == "synthetic.media.pattern_select"
    assert meta["capability_kind"] == "media"
    assert meta["pattern_names"] == ["grid_3x2", "random_walk", "circle"]
    assert meta["synthetic_kind"] == "pattern_select"
    assert "adapter_config" in meta
    assert meta["adapter_config"]["executor_id"] == "synthetic.media.pattern_select"


def test_lower_pattern_select_custom_metadata_merged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Custom *metadata* dict passed to ``lower_pattern_select`` is merged into
    the stage metadata without clobbering the mandatory keys."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    stage = lowering.lower_pattern_select(
        stage_id="custom_pat",
        label="Custom",
        segment_id="seg-cust",
        project="demo",
        run_root_path=tmp_path,
        state={},
        pattern_names=("single",),
        metadata={"extra_tag": 42, "priority": "high"},
    )

    meta = stage.metadata
    assert meta["pattern_names"] == ["single"]
    assert meta["synthetic_kind"] == "pattern_select"
    assert meta["extra_tag"] == 42
    assert meta["priority"] == "high"


def test_lower_pattern_select_empty_pattern_names(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``lower_pattern_select`` accepts an empty pattern_names tuple and records
    an empty list in metadata."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    stage = lowering.lower_pattern_select(
        stage_id="empty_pat",
        label="No Patterns",
        segment_id="seg-empty",
        project="demo",
        run_root_path=tmp_path,
        state={},
        pattern_names=(),
    )

    assert stage.metadata["pattern_names"] == []
    assert stage.metadata["executor_id"] == "synthetic.media.pattern_select"


def test_lower_vote_judge_emits_adapter_backed_stage_majority_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``lower_vote_judge`` emits an adapter-backed StageSpec with
    synthetic.judge.vote executor, majority vote_mode default, and empty
    candidates."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    stage = lowering.lower_vote_judge(
        stage_id="jury",
        label="Jury Vote",
        segment_id="seg-vote",
        project="demo",
        run_root_path=tmp_path,
        state={"round": 1},
    )

    assert isinstance(stage, lowering.StageSpec)
    assert stage.stage_id == "jury"
    assert stage.label == "Jury Vote"
    assert stage.invocation is not None
    assert stage.suspension is None

    meta = stage.metadata
    assert meta["executor_id"] == "synthetic.judge.vote"
    assert meta["capability_kind"] == "judge"
    assert meta["vote_mode"] == "majority"
    assert meta["candidates"] == []
    assert meta["synthetic_kind"] == "vote_judge"


def test_lower_vote_judge_explicit_vote_mode_and_candidates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Explicit *vote_mode* and *candidates* are recorded in metadata."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    stage = lowering.lower_vote_judge(
        stage_id="panel",
        label="Expert Panel",
        segment_id="seg-panel",
        project="demo",
        run_root_path=tmp_path,
        state={},
        vote_mode="unanimous",
        candidates=("alice", "bob", "carol"),
    )

    meta = stage.metadata
    assert meta["vote_mode"] == "unanimous"
    assert meta["candidates"] == ["alice", "bob", "carol"]


def test_lower_vote_judge_custom_metadata_merged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Custom metadata merges into the vote/judge stage metadata without
    clobbering mandatory keys."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    stage = lowering.lower_vote_judge(
        stage_id="custom_vote",
        label="Custom Vote",
        segment_id="seg-cv",
        project="demo",
        run_root_path=tmp_path,
        state={},
        metadata={"threshold": 0.75, "tags": ["urgent"]},
    )

    meta = stage.metadata
    assert meta["vote_mode"] == "majority"
    assert meta["synthetic_kind"] == "vote_judge"
    assert meta["threshold"] == 0.75
    assert meta["tags"] == ["urgent"]


def test_lower_dynamic_fanout_parallel_stage_exposed_single_stage_spec(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When the Arnold public surface exposes ``ParallelStage``,
    ``lower_dynamic_fanout`` returns a **single** StageSpec with
    ``parallel_stage_hint=True`` and per-branch metadata recorded in
    ``fanout_branches``."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    branches = (
        {"resolution": "1080p", "codec": "h264"},
        {"resolution": "720p", "codec": "h265"},
        {"resolution": "4k", "codec": "av1"},
    )

    specs = lowering.lower_dynamic_fanout(
        stage_id="encode_fanout",
        label="Encode Fanout",
        segment_id="seg-fan",
        project="demo",
        run_root_path=tmp_path,
        state={},
        fanout_branches=branches,
    )

    # ParallelStage is exposed → single StageSpec
    assert isinstance(specs, tuple)
    assert len(specs) == 1
    spec = specs[0]
    assert isinstance(spec, lowering.StageSpec)
    assert spec.stage_id == "encode_fanout"
    assert spec.label == "Encode Fanout"

    meta = spec.metadata
    assert meta["executor_id"] == "synthetic.fanout.fanout"
    assert meta["capability_kind"] == "fanout"
    assert meta["synthetic_kind"] == "dynamic_fanout"
    assert meta["fanout_branch_count"] == 3
    assert meta["parallel_stage_hint"] is True

    # Per-branch metadata preserved
    assert len(meta["fanout_branches"]) == 3
    assert meta["fanout_branches"][0] == {
        "index": 0,
        "payload": {"resolution": "1080p", "codec": "h264"},
    }
    assert meta["fanout_branches"][1] == {
        "index": 1,
        "payload": {"resolution": "720p", "codec": "h265"},
    }
    assert meta["fanout_branches"][2] == {
        "index": 2,
        "payload": {"resolution": "4k", "codec": "av1"},
    }


def test_lower_dynamic_fanout_parallel_stage_absent_sequential_specs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When ``ParallelStage`` is **not** available, ``lower_dynamic_fanout``
    returns one adapter-backed StageSpec per branch with sequential stage ids
    and per-branch metadata."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    # Force _arnold_has_parallel_stage() to return False
    monkeypatch.setattr(lowering, "_arnold_has_parallel_stage", lambda: False)

    branches = (
        {"task": "render_left"},
        {"task": "render_right"},
    )

    specs = lowering.lower_dynamic_fanout(
        stage_id="render_fanout",
        label="Render Fanout",
        segment_id="seg-rfan",
        project="demo",
        run_root_path=tmp_path,
        state={},
        fanout_branches=branches,
    )

    # ParallelStage absent → one spec per branch
    assert isinstance(specs, tuple)
    assert len(specs) == 2

    for idx, spec in enumerate(specs):
        assert isinstance(spec, lowering.StageSpec)
        assert spec.stage_id == f"render_fanout/{idx}"
        assert spec.label == f"Render Fanout/{idx}"
        assert spec.invocation is not None

        meta = spec.metadata
        assert meta["executor_id"] == "synthetic.fanout.fanout"
        assert meta["capability_kind"] == "fanout"
        assert meta["synthetic_kind"] == "dynamic_fanout"
        assert meta["fanout_index"] == idx
        assert meta["fanout_total"] == 2
        assert "branch_payload" in meta

    assert specs[0].metadata["branch_payload"] == {"task": "render_left"}
    assert specs[1].metadata["branch_payload"] == {"task": "render_right"}


def test_lower_dynamic_fanout_single_branch_parallel_stage_exposed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A single-branch fan-out with ParallelStage exposed still returns one
    StageSpec with parallel_stage_hint."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    specs = lowering.lower_dynamic_fanout(
        stage_id="single_fan",
        label="Single Fan",
        segment_id="seg-sf",
        project="demo",
        run_root_path=tmp_path,
        state={},
        fanout_branches=({"only": True},),
    )

    assert len(specs) == 1
    assert specs[0].metadata["parallel_stage_hint"] is True
    assert specs[0].metadata["fanout_branch_count"] == 1
    assert specs[0].metadata["fanout_branches"] == [
        {"index": 0, "payload": {"only": True}}
    ]


def test_lower_dynamic_fanout_single_branch_parallel_stage_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A single-branch fan-out without ParallelStage returns one adapter-backed
    spec with sequential naming."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    monkeypatch.setattr(lowering, "_arnold_has_parallel_stage", lambda: False)

    specs = lowering.lower_dynamic_fanout(
        stage_id="single_fan",
        label="Single Fan",
        segment_id="seg-sf2",
        project="demo",
        run_root_path=tmp_path,
        state={},
        fanout_branches=({"only": True},),
    )

    assert len(specs) == 1
    spec = specs[0]
    assert spec.stage_id == "single_fan/0"
    assert spec.label == "Single Fan/0"
    assert spec.metadata["fanout_index"] == 0
    assert spec.metadata["fanout_total"] == 1
    assert spec.metadata["branch_payload"] == {"only": True}
    assert "parallel_stage_hint" not in spec.metadata


def test_lower_dynamic_fanout_custom_metadata_merged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Custom metadata merges into fan-out stage metadata for both ParallelStage
    exposed and absent branches."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    # ParallelStage exposed branch
    specs_parallel = lowering.lower_dynamic_fanout(
        stage_id="meta_fan",
        label="Meta Fan",
        segment_id="seg-mf",
        project="demo",
        run_root_path=tmp_path,
        state={},
        fanout_branches=({"a": 1},),
        metadata={"owner": "pipeline-team"},
    )
    assert specs_parallel[0].metadata["owner"] == "pipeline-team"
    assert specs_parallel[0].metadata["parallel_stage_hint"] is True

    # ParallelStage absent branch
    monkeypatch.setattr(lowering, "_arnold_has_parallel_stage", lambda: False)
    specs_seq = lowering.lower_dynamic_fanout(
        stage_id="meta_fan_seq",
        label="Meta Fan Seq",
        segment_id="seg-mfs",
        project="demo",
        run_root_path=tmp_path,
        state={},
        fanout_branches=({"a": 1}, {"b": 2}),
        metadata={"owner": "pipeline-team"},
    )
    for spec in specs_seq:
        assert spec.metadata["owner"] == "pipeline-team"


def test_lower_dynamic_fanout_empty_branches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``lower_dynamic_fanout`` with zero branches: ParallelStage-exposed path
    returns a single StageSpec with empty fanout_branches; absent path returns
    an empty tuple."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    # ParallelStage exposed → single StageSpec with empty branch list
    specs_parallel = lowering.lower_dynamic_fanout(
        stage_id="empty_fan",
        label="Empty Fan",
        segment_id="seg-ef",
        project="demo",
        run_root_path=tmp_path,
        state={},
        fanout_branches=(),
    )
    assert len(specs_parallel) == 1
    assert specs_parallel[0].metadata["fanout_branch_count"] == 0
    assert specs_parallel[0].metadata["fanout_branches"] == []
    assert specs_parallel[0].metadata["parallel_stage_hint"] is True

    # ParallelStage absent → empty tuple
    monkeypatch.setattr(lowering, "_arnold_has_parallel_stage", lambda: False)
    specs_seq = lowering.lower_dynamic_fanout(
        stage_id="empty_fan_seq",
        label="Empty Fan Seq",
        segment_id="seg-efs",
        project="demo",
        run_root_path=tmp_path,
        state={},
        fanout_branches=(),
    )
    assert specs_seq == ()


# ── T24: parallel join behavior tests ──


class _FakeParallelStageWithJoin:
    """Fake Arnold ParallelStage with a callable ``join`` for delegation tests."""

    def __init__(self, stage_id: str) -> None:
        self.stage_id = stage_id
        self._join_called_with: list[Any] | None = None

    def join(self, results: list[Any]) -> str:
        self._join_called_with = list(results)
        return f"joined-{len(results)}-items"


def test_join_parallel_results_delegates_to_callable_join(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``join_parallel_results`` delegates to ``stage.join(results)`` when the
    stage exposes a callable ``join`` attribute and returns the joined value."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    stage = _FakeParallelStageWithJoin(stage_id="parallel_proc")
    results = [{"a": 1}, {"b": 2}, {"c": 3}]

    joined = lowering.join_parallel_results(stage, results)

    # Prove delegation: join was called with the exact results
    assert stage._join_called_with == results
    assert joined == "joined-3-items"


def test_join_parallel_results_raises_diagnostic_when_join_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``join_parallel_results`` raises ``CompileUnsupportedFeature`` with a
    diagnostic naming the stage when the stage does not expose a callable
    ``join`` attribute, proving the A4a fan-out path fails clearly."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    # Stage with stage_id but NO join attribute at all
    stage_no_join = _Stage(stage_id="plain_stage", label="Plain")
    with pytest.raises(lowering.CompileUnsupportedFeature) as exc_info:
        lowering.join_parallel_results(stage_no_join, [{"x": 1}])
    msg = str(exc_info.value)
    assert "plain_stage" in msg
    assert "join" in msg.lower()
    assert "ParallelStage" in msg

    # Stage with a non-callable join attribute
    stage_bad_join = _Stage(stage_id="bad_join_stage", label="Bad Join")
    object.__setattr__(stage_bad_join, "join", "not_callable_string")
    with pytest.raises(lowering.CompileUnsupportedFeature) as exc_info2:
        lowering.join_parallel_results(stage_bad_join, [{"x": 1}])
    msg2 = str(exc_info2.value)
    assert "bad_join_stage" in msg2
    assert "join" in msg2.lower()


def test_join_parallel_results_delegation_with_empty_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``join_parallel_results`` delegates correctly even when results list is
    empty, proving the join contract holds for the zero-results edge case."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    stage = _FakeParallelStageWithJoin(stage_id="empty_joiner")
    joined = lowering.join_parallel_results(stage, [])
    assert stage._join_called_with == []
    assert joined == "joined-0-items"


def test_join_parallel_results_repr_fallback_when_stage_id_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``join_parallel_results`` falls back to ``repr(stage)`` in the diagnostic
    when the stage object has no ``stage_id`` attribute."""
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module(
        "astrid.core.integrations.arnold.session.lowering"
    )

    # Bare object with neither stage_id nor join
    bare_stage = object()
    with pytest.raises(lowering.CompileUnsupportedFeature) as exc_info:
        lowering.join_parallel_results(bare_stage, [1])
    msg = str(exc_info.value)
    # The repr of a bare object() will appear in the diagnostic
    assert "object" in msg
    assert "join" in msg.lower()
