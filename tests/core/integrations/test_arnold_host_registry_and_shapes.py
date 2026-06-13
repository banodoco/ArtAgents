from __future__ import annotations

import ast
import importlib
import inspect
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest


def _clear_host_modules() -> None:
    for name in tuple(sys.modules):
        if name.startswith("astrid.core.integrations.arnold.host"):
            sys.modules.pop(name, None)
    sys.modules.pop("astrid.core.integrations.arnold", None)


@dataclass(frozen=True)
class _ResumeCursorRef:
    plugin_id: str
    run_id: str
    cursor: dict[str, Any]


@dataclass(frozen=True)
class _CrossCuttingEnvelope:
    taint: tuple[str, ...] = ()
    cost: dict[str, Any] = field(default_factory=dict)
    lineage: tuple[str, ...] = ()
    deadline: str | None = None
    cancellation: str | None = None
    retry_budget: dict[str, Any] = field(default_factory=dict)
    error_class: str | None = None


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
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Stage:
    stage_id: str
    label: str
    invocation: Any | None = None
    suspension: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Edge:
    source: str
    target: str
    label: str


@dataclass(frozen=True)
class _ParallelStage:
    stage_id: str
    label: str
    stages: tuple[Any, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _BuiltPipeline:
    entry_stage_id: str
    stages: tuple[_Stage, ...]
    edges: tuple[_Edge, ...]


class _PipelineBuilder:
    def __init__(self) -> None:
        self.entry_stage_id: str | None = None
        self.stages: list[_Stage] = []
        self.edges: list[_Edge] = []

    def add_stage(self, stage: _Stage) -> None:
        self.stages.append(stage)

    def add_edge(self, edge: _Edge) -> None:
        self.edges.append(edge)

    def set_entry_stage(self, stage_id: str) -> None:
        self.entry_stage_id = stage_id

    def build(self) -> _BuiltPipeline:
        assert self.entry_stage_id is not None
        return _BuiltPipeline(
            entry_stage_id=self.entry_stage_id,
            stages=tuple(self.stages),
            edges=tuple(self.edges),
        )


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
    cursor_stage: str = "review",
) -> None:
    pipeline = types.ModuleType("arnold.pipeline")
    exports = {
        "RuntimeEnvelope": _RuntimeEnvelope,
        "ResumeCursorRef": _ResumeCursorRef,
        "AdvanceOutcome": _AdvanceOutcome,
        "CheckpointOutcome": _CheckpointOutcome,
        "StepwiseDriver": _StepwiseDriver,
        "PipelineBuilder": _PipelineBuilder,
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
        "read_resume_cursor": lambda artifact_root: _ResumeCursorRef(
            plugin_id="astrid.arnold.host",
            run_id=Path(artifact_root).name,
            cursor={"stage": cursor_stage},
        ),
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
    _clear_host_modules()
    yield
    _clear_host_modules()


def _seed_project(root: Path) -> tuple[Path, Path]:
    project_root = root / "demo"
    run_root = project_root / "runs" / "run-123"
    run_root.mkdir(parents=True)
    (project_root / "current_run.json").write_text(
        json.dumps({"run_id": "run-123"}),
        encoding="utf-8",
    )
    (run_root / "lease.json").write_text(
        json.dumps(
            {
                "writer_epoch": 7,
                "attached_session_id": "session-1",
                "plan_hash": "plan-abc",
            }
        ),
        encoding="utf-8",
    )
    (run_root / "events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "kind": "run_started",
                        "ts": "2026-06-13T03:43:00Z",
                        "hash": "sha256:111",
                    }
                ),
                json.dumps(
                    {
                        "kind": "step_completed",
                        "ts": "2026-06-13T03:44:00Z",
                        "hash": "sha256:222",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return project_root, run_root


def test_registry_snapshot_reads_only_arnold_projection_without_task_cursor_helpers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_pipeline(monkeypatch, cursor_stage="review")
    project_root, run_root = _seed_project(tmp_path / "projects")

    monkeypatch.setattr(
        "astrid.core.task.gate.peek_current_step",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("peek_current_step must not be used by Arnold registry")
        ),
    )
    monkeypatch.setattr(
        "astrid.core.task.gate.cursor.derive_cursor",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("derive_cursor must not be used by Arnold registry")
        ),
        raising=False,
    )

    registry_module = importlib.import_module(
        "astrid.core.integrations.arnold.host.registry"
    )
    registry = registry_module.get_host_shape_registry()

    before_current_run = (project_root / "current_run.json").read_bytes()
    before_lease = (run_root / "lease.json").read_bytes()
    before_events = (run_root / "events.jsonl").read_bytes()

    snapshot = registry.snapshot_operation(
        project_slug="demo",
        workflow_id="we.refine_image",
        root=tmp_path / "projects",
    )

    assert snapshot.run_id == "run-123"
    assert snapshot.next_stage_id == "review"
    assert snapshot.next_stage_label == "Review"
    assert snapshot.cursor == {"stage": "review"}
    assert snapshot.lease["writer_epoch"] == 7
    assert [event["hash"] for event in snapshot.events_tail] == [
        "sha256:111",
        "sha256:222",
    ]
    assert (project_root / "current_run.json").read_bytes() == before_current_run
    assert (run_root / "lease.json").read_bytes() == before_lease
    assert (run_root / "events.jsonl").read_bytes() == before_events


def test_registry_defaults_to_shape_entry_stage_when_resume_cursor_is_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_pipeline(monkeypatch, cursor_stage="")
    _seed_project(tmp_path / "projects")

    registry_module = importlib.import_module(
        "astrid.core.integrations.arnold.host.registry"
    )
    registry = registry_module.get_host_shape_registry()

    stage_id, stage_label = registry.get_next_step(
        project_slug="demo",
        workflow_id="we.refine_image",
        root=tmp_path / "projects",
    )

    assert stage_id == "generate"
    assert stage_label == "Generate"


def test_build_refine_image_pipeline_has_expected_topology_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_refine_image_pipeline(
        state={"prompt": "refine this", "candidate": "produces/draft.png"},
        project="demo",
        run_root="/tmp/run-123",
        artifact_root="/tmp/run-123",
        cas_project_dir="/tmp/projects/demo",
    )

    assert pipeline.entry_stage_id == "generate"
    assert [stage.stage_id for stage in pipeline.stages] == ["generate", "review", "halt"]
    assert [stage.label for stage in pipeline.stages] == ["Generate", "Review", "Halt"]
    assert [(edge.source, edge.target, edge.label) for edge in pipeline.edges] == [
        ("generate", "review", "next"),
        ("review", "halt", "approve"),
        ("review", "generate", "reject"),
    ]

    generate_stage = next(stage for stage in pipeline.stages if stage.stage_id == "generate")
    review_stage = next(stage for stage in pipeline.stages if stage.stage_id == "review")

    assert generate_stage.invocation.metadata["adapter_config"]["workflow_id"] == "we.refine_image"
    assert generate_stage.invocation.metadata["adapter_config"]["stage_id"] == "generate"
    assert review_stage.invocation.metadata["adapter_config"]["workflow_id"] == "we.refine_image"
    assert review_stage.invocation.metadata["adapter_config"]["stage_id"] == "review"
    assert review_stage.invocation.metadata["adapter_config"]["requires_ack"] is True
    assert review_stage.suspension.resume_input_schema == {
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


def test_build_refine_image_pipeline_contains_no_host_side_while_loop() -> None:
    source = inspect.getsource(
        importlib.import_module("astrid.core.integrations.arnold.host.shapes").build_refine_image_pipeline
    )
    tree = ast.parse(source)

    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))


def test_build_best_of_4_pipeline_has_expected_topology_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_best_of_4_pipeline(
        state={"prompt": "best of 4", "candidate": "produces/draft.png"},
        project="demo",
        run_root="/tmp/run-456",
        artifact_root="/tmp/run-456",
        cas_project_dir="/tmp/projects/demo",
    )

    assert pipeline.entry_stage_id == "generate"

    stage_ids = [stage.stage_id for stage in pipeline.stages]
    assert stage_ids == ["generate", "judge", "review", "halt"]

    labels = [stage.label for stage in pipeline.stages]
    assert labels == ["Generate", "Judge", "Review", "Halt"]

    assert [(edge.source, edge.target, edge.label) for edge in pipeline.edges] == [
        ("generate", "judge", "next"),
        ("judge", "review", "next"),
        ("review", "halt", "approve"),
        ("review", "generate", "reject"),
    ]

    # Four parallel generate sub-stages
    generate_stage = next(stage for stage in pipeline.stages if stage.stage_id == "generate")
    sub_stages = getattr(generate_stage, "stages", None) or getattr(generate_stage, "sub_stages", None) or getattr(
        generate_stage, "children", None
    )
    assert sub_stages is not None, "ParallelStage must expose sub-stages via stages/sub_stages/children"
    assert len(sub_stages) == 4

    sub_stage_ids = [
        getattr(s, "stage_id", None) or getattr(s, "id", None) or getattr(s, "name", None)
        for s in sub_stages
    ]
    assert sub_stage_ids == ["gen_0", "gen_1", "gen_2", "gen_3"]

    # Each gen branch has a deterministic invocation
    for idx, sub_stage in enumerate(sub_stages):
        invocation = getattr(sub_stage, "invocation", None)
        assert invocation is not None, f"gen_{idx} missing invocation"
        inv_metadata = getattr(invocation, "metadata", {})
        adapter_cfg = inv_metadata.get("adapter_config", {})
        assert adapter_cfg.get("workflow_id") == "we.best_of_4"
        assert adapter_cfg.get("stage_id") == f"gen_{idx}"
        assert adapter_cfg.get("inputs", {}).get("variant") == f"branch_{idx}"

    # Judge stage
    judge_stage = next(stage for stage in pipeline.stages if stage.stage_id == "judge")
    assert judge_stage.invocation.metadata["adapter_config"]["workflow_id"] == "we.best_of_4"
    assert judge_stage.invocation.metadata["adapter_config"]["stage_id"] == "judge"
    assert judge_stage.invocation.metadata["adapter_config"]["inputs"]["strategy"] == "best_of_4"

    # Review stage — human gate
    review_stage = next(stage for stage in pipeline.stages if stage.stage_id == "review")
    assert review_stage.invocation.metadata["adapter_config"]["workflow_id"] == "we.best_of_4"
    assert review_stage.invocation.metadata["adapter_config"]["stage_id"] == "review"
    assert review_stage.invocation.metadata["adapter_config"]["requires_ack"] is True
    assert review_stage.suspension.resume_input_schema == {
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

    # Judge metadata lowering: judge stage metadata declares lowers_verdict
    judge_metadata = getattr(judge_stage, "metadata", {})
    assert judge_metadata.get("judge_required") is True
    assert judge_metadata.get("lowers_verdict") is True

    # Generate stage metadata declares parallel fan-out
    generate_metadata = getattr(generate_stage, "metadata", {})
    assert generate_metadata.get("parallel_fan_out") == 4
    assert generate_metadata.get("entry") is True


def test_build_best_of_4_pipeline_contains_no_host_side_while_loop() -> None:
    source = inspect.getsource(
        importlib.import_module("astrid.core.integrations.arnold.host.shapes").build_best_of_4_pipeline
    )
    tree = ast.parse(source)

    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))


# ── T9: text_analysis.summarize linear shape tests ────────────────────────
# ── T9: text_analysis.summarize DSL-compiled 3-stage shape tests ───────────
# SD1: The single canonical Arnold shape is the DSL-compiler-generated
# 3-stage pipeline (read_input -> write_summary -> write_verdict -> halt).
# No hand-authored single-stage wrapper remains.


def test_build_text_analysis_summarize_pipeline_produces_dsl_compiled_3_stage_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The built pipeline is DSL-compiled with 3 stages: read_input,
    write_summary, write_verdict (+ halt)."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_text_analysis_summarize_pipeline(
        state={"text": "sample input"},
        project="demo",
        run_root=str(tmp_path / "run-789"),
        artifact_root=str(tmp_path / "run-789"),
        cas_project_dir=str(tmp_path / "projects" / "demo"),
    )

    # The DSL compiler always appends halt, so we expect 4 stages total
    stage_ids = [stage.stage_id for stage in pipeline.stages]
    assert stage_ids[0] == "read_input"
    assert stage_ids[1] == "write_summary"
    assert stage_ids[2] == "write_verdict"
    assert stage_ids[3] == "halt"
    assert len(stage_ids) == 4

    # Entry stage must be read_input (the first DSL step)
    assert pipeline.entry_stage_id == "read_input"

    # Edge topology: read_input -> write_summary -> write_verdict -> halt
    edge_triples = {(e.source, e.target, e.label) for e in pipeline.edges}
    assert ("read_input", "write_summary", "next") in edge_triples
    assert ("write_summary", "write_verdict", "next") in edge_triples
    assert ("write_verdict", "halt", "next") in edge_triples

    # No back-edges: the entry stage read_input should never be a target
    edge_targets = {edge.target for edge in pipeline.edges}
    assert "read_input" not in edge_targets

    # Terminal halt has no invocation
    halt_stage = next(stage for stage in pipeline.stages if stage.stage_id == "halt")
    assert getattr(halt_stage, "invocation", None) is None


def test_build_text_analysis_summarize_pipeline_stages_have_invocations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Each of the 3 work stages carries a task.local StepInvocation."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_text_analysis_summarize_pipeline(
        state={"text": "hello"},
        project="demo",
        run_root=str(tmp_path / "run-790"),
        artifact_root=str(tmp_path / "run-790"),
        cas_project_dir=str(tmp_path / "projects" / "demo"),
    )

    for stage_id in ("read_input", "write_summary", "write_verdict"):
        stage = next(s for s in pipeline.stages if s.stage_id == stage_id)
        assert stage.invocation is not None, f"{stage_id} missing invocation"
        inv_metadata = getattr(stage.invocation, "metadata", {})
        adapter_cfg = inv_metadata.get("adapter_config", {})
        assert adapter_cfg.get("executor_id") == "task.local", \
            f"{stage_id} executor_id mismatch: {adapter_cfg.get('executor_id')}"
        assert adapter_cfg.get("mode") == "inline"
        assert adapter_cfg.get("requires_ack") is False


def test_build_text_analysis_summarize_pipeline_contains_no_host_side_while_loop() -> None:
    """The shape builder itself has no host-side while/for loops — it delegates
    to the DSL compiler which is tested separately."""
    source = inspect.getsource(
        importlib.import_module(
            "astrid.core.integrations.arnold.host.shapes"
        ).build_text_analysis_summarize_pipeline
    )
    tree = ast.parse(source)
    # The builder now delegates to compile_to_pipeline; it should not have
    # any while loops at this level.
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))


def test_text_analysis_summarize_shape_entry_in_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Registry exposes the text_analysis.summarize shape with DSL-compiled
    metadata: entry_stage_id=read_input, 3-stage labels, compiled=True."""
    _install_fake_pipeline(monkeypatch, cursor_stage="read_input")
    _seed_project(tmp_path / "projects")

    monkeypatch.setattr(
        "astrid.core.task.gate.peek_current_step",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("peek_current_step must not be used by Arnold registry")
        ),
    )

    registry_module = importlib.import_module(
        "astrid.core.integrations.arnold.host.registry"
    )
    registry = registry_module.get_host_shape_registry()

    entry = registry.get("text_analysis.summarize")
    assert entry is not None
    assert entry.workflow_id == "text_analysis.summarize"
    assert entry.cli_alias == "summarize"
    assert entry.accepts_human_input is False
    assert entry.entry_stage_id == "read_input", \
        f"expected read_input, got {entry.entry_stage_id}"
    assert entry.stage_labels == {
        "read_input": "Read Input",
        "write_summary": "Write Summary",
        "write_verdict": "Write Verdict",
        "halt": "Halt",
    }, f"stage_labels mismatch: {entry.stage_labels}"
    assert entry.metadata["kind"] == "analysis"
    assert entry.metadata["parallel_fan_out"] == 1
    assert entry.metadata["judge_required"] is False
    assert entry.metadata.get("compiled") is True, \
        "summarize shape must be marked compiled=True"
    assert callable(entry.pipeline_builder)

    # Alias resolution
    assert registry.resolve_alias("summarize") == "text_analysis.summarize"
    assert registry.is_allowlisted("text_analysis.summarize") is True


# ── T5: builtin.agent_probe repeat-for-each DSL-compiled shape tests ──────
# The single canonical Arnold shape is the DSL-compiler-generated
# repeat-for-each pipeline (per_item (fan_out_shape) -> halt).


def test_build_builtin_agent_probe_pipeline_produces_dsl_compiled_repeat_for_each_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The built pipeline is DSL-compiled with repeat_for_each: per_item
    (fan_out_shape, items=[alpha,beta,gamma]) -> halt."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_builtin_agent_probe_pipeline(
        state={},
        project="demo",
        run_root=str(tmp_path / "run-ap"),
        artifact_root=str(tmp_path / "run-ap"),
        cas_project_dir=str(tmp_path / "projects" / "demo"),
    )

    # The DSL compiler always appends halt, so we expect 2 stages total
    stage_ids = [stage.stage_id for stage in pipeline.stages]
    assert stage_ids[0] == "per_item"
    assert stage_ids[1] == "halt"
    assert len(stage_ids) == 2

    # Entry stage must be per_item (the attested step)
    assert pipeline.entry_stage_id == "per_item"

    # Edge topology: per_item -> halt
    edge_triples = {(e.source, e.target, e.label) for e in pipeline.edges}
    assert ("per_item", "halt", "next") in edge_triples

    # Terminal halt has no invocation
    halt_stage = next(stage for stage in pipeline.stages if stage.stage_id == "halt")
    assert getattr(halt_stage, "invocation", None) is None

    # per_item stage has invocation with task.local executor
    per_item = next(s for s in pipeline.stages if s.stage_id == "per_item")
    assert per_item.invocation is not None, "per_item missing invocation"
    inv_metadata = getattr(per_item.invocation, "metadata", {})
    adapter_cfg = inv_metadata.get("adapter_config", {})
    assert adapter_cfg.get("executor_id") == "task.manual", \
        f"per_item executor_id mismatch: {adapter_cfg.get('executor_id')}"
    assert adapter_cfg.get("mode") == "inline"
    assert adapter_cfg.get("requires_ack") is True

    # per_item stage has repeat_for_each and fan_out_shape metadata
    stage_meta = getattr(per_item, "metadata", {})
    assert stage_meta.get("fan_out_shape") is True, \
        "per_item must have fan_out_shape=True"
    assert stage_meta.get("repeat_for_each") == {
        "kind": "for_each",
        "items_source": "static",
        "items": ["alpha", "beta", "gamma"],
    }, f"repeat_for_each metadata mismatch: {stage_meta.get('repeat_for_each')}"


def test_build_builtin_agent_probe_pipeline_contains_no_host_side_while_loop() -> None:
    """The shape builder itself has no host-side while/for loops — it delegates
    to the DSL compiler which is tested separately."""
    source = inspect.getsource(
        importlib.import_module(
            "astrid.core.integrations.arnold.host.shapes"
        ).build_builtin_agent_probe_pipeline
    )
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))


def test_builtin_agent_probe_shape_entry_in_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Registry exposes the builtin.agent_probe shape with DSL-compiled
    metadata: entry_stage_id=per_item, repeat-for-each labels, compiled=True."""
    _install_fake_pipeline(monkeypatch, cursor_stage="per_item")
    _seed_project(tmp_path / "projects")

    monkeypatch.setattr(
        "astrid.core.task.gate.peek_current_step",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("peek_current_step must not be used by Arnold registry")
        ),
    )

    registry_module = importlib.import_module(
        "astrid.core.integrations.arnold.host.registry"
    )
    registry = registry_module.get_host_shape_registry()

    entry = registry.get("builtin.agent_probe")
    assert entry is not None
    assert entry.workflow_id == "builtin.agent_probe"
    assert entry.cli_alias == "agent-probe"
    assert entry.accepts_human_input is False
    assert entry.entry_stage_id == "per_item", \
        f"expected per_item, got {entry.entry_stage_id}"
    assert entry.stage_labels == {
        "per_item": "Per Item",
        "halt": "Halt",
    }, f"stage_labels mismatch: {entry.stage_labels}"
    assert entry.metadata["kind"] == "probe"
    assert entry.metadata["parallel_fan_out"] == 3
    assert entry.metadata["judge_required"] is False
    assert entry.metadata.get("compiled") is True, \
        "agent_probe shape must be marked compiled=True"
    assert callable(entry.pipeline_builder)

    # Alias resolution
    assert registry.resolve_alias("agent-probe") == "builtin.agent_probe"
    assert registry.is_allowlisted("builtin.agent_probe") is True


def test_build_stream_content_distill_pipeline_documents_wrapper_then_unroll_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Distill exposes the runtime segment loop as explicit wrapper-then-unroll
    metadata instead of collapsing to a plain one-stage-per-child graph."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_stream_content_distill_pipeline(
        state={},
        project="demo",
        run_root=str(tmp_path / "run-distill"),
        artifact_root=str(tmp_path / "run-distill"),
        cas_project_dir=str(tmp_path / "projects" / "demo"),
    )

    assert pipeline.entry_stage_id == "transcribe"
    assert [stage.stage_id for stage in pipeline.stages] == [
        "transcribe",
        "scenes",
        "segment-map",
        "extract-segments",
        "clip-candidates",
        "review",
        "halt",
    ]
    edge_triples = {(edge.source, edge.target, edge.label) for edge in pipeline.edges}
    assert edge_triples == {
        ("transcribe", "scenes", "next"),
        ("scenes", "segment-map", "next"),
        ("segment-map", "extract-segments", "next"),
        ("extract-segments", "clip-candidates", "next"),
        ("clip-candidates", "review", "next"),
        ("review", "halt", "next"),
    }

    transcribe = next(stage for stage in pipeline.stages if stage.stage_id == "transcribe")
    assert transcribe.invocation.metadata["adapter_config"]["executor_id"] == "editorial.transcribe"

    extract_segments = next(
        stage for stage in pipeline.stages if stage.stage_id == "extract-segments"
    )
    wrapper = extract_segments.metadata["wrapper_then_unroll"]
    assert extract_segments.invocation is None
    assert extract_segments.metadata["fan_out_shape"] is True
    assert wrapper == {
        "kind": "segment_extract",
        "fanout_source_stage_id": "segment-map",
        "fanout_source_artifact": "segment_map",
        "segment_kinds": ["content", "screening"],
        "child_executor_id": "media.clip_extract",
        "manifest_artifact": "segments/segments.json",
        "output_directory": "segments/",
    }

    clip_candidates = next(
        stage for stage in pipeline.stages if stage.stage_id == "clip-candidates"
    )
    assert (
        clip_candidates.invocation.metadata["adapter_config"]["executor_id"]
        == "stream_content.clip_candidates"
    )

    review = next(stage for stage in pipeline.stages if stage.stage_id == "review")
    assert review.invocation is None
    assert review.metadata["wrapper_subcommand"] == "review"
    assert review.metadata["produces"] == ["review.html"]


def test_stream_content_distill_shape_entry_in_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Registry exposes distill with compiled wrapper-then-unroll metadata."""
    _install_fake_pipeline(monkeypatch, cursor_stage="transcribe")
    _seed_project(tmp_path / "projects")

    monkeypatch.setattr(
        "astrid.core.task.gate.peek_current_step",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("peek_current_step must not be used by Arnold registry")
        ),
    )

    registry_module = importlib.import_module(
        "astrid.core.integrations.arnold.host.registry"
    )
    registry = registry_module.get_host_shape_registry()

    entry = registry.get("stream_content.distill")
    assert entry is not None
    assert entry.workflow_id == "stream_content.distill"
    assert entry.cli_alias == "distill"
    assert entry.accepts_human_input is False
    assert entry.entry_stage_id == "transcribe"
    assert entry.stage_labels == {
        "transcribe": "Transcribe",
        "scenes": "Scenes",
        "segment-map": "Segment Map",
        "extract-segments": "Extract Segments",
        "clip-candidates": "Clip Candidates",
        "review": "Review",
        "halt": "Halt",
    }
    assert entry.metadata["kind"] == "stream_content"
    assert entry.metadata["parallel_fan_out"] == "dynamic"
    assert entry.metadata["judge_required"] is False
    assert entry.metadata["compiled"] is True
    assert entry.metadata["loop_lowering"] == "wrapper_then_unroll"
    assert callable(entry.pipeline_builder)
    assert registry.resolve_alias("distill") == "stream_content.distill"
    assert registry.is_allowlisted("stream_content.distill") is True


def test_stream_content_distill_child_executors_resolve_from_registry() -> None:
    """Distill's declared executor tier remains real registry-backed tools."""
    from astrid.core.execution.executor.registry import load_default_registry

    registry = load_default_registry()
    declared = (
        "editorial.transcribe",
        "editorial.scenes",
        "stream_content.segment_map",
        "media.clip_extract",
        "stream_content.clip_candidates",
    )
    resolved = tuple(registry.get(executor_id).id for executor_id in declared)
    assert resolved == declared


def test_build_foley_map_pipeline_exposes_tile_fanout_and_bounded_parallel_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Foley Map must expose tile fanout plus per-tile VLM/Foley loop metadata."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_foley_map_pipeline(
        state={},
        project="demo",
        run_root=str(tmp_path / "run-foley"),
        artifact_root=str(tmp_path / "run-foley"),
        cas_project_dir=str(tmp_path / "projects" / "demo"),
    )

    assert pipeline.entry_stage_id == "tile-video"
    assert [stage.stage_id for stage in pipeline.stages] == [
        "tile-video",
        "tile-fanout",
        "tile-prompts",
        "foley-audio",
        "review",
        "spatial-page",
        "halt",
    ]
    edge_triples = {(edge.source, edge.target, edge.label) for edge in pipeline.edges}
    assert edge_triples == {
        ("tile-video", "tile-fanout", "next"),
        ("tile-fanout", "tile-prompts", "next"),
        ("tile-prompts", "foley-audio", "next"),
        ("foley-audio", "review", "next"),
        ("review", "spatial-page", "next"),
        ("spatial-page", "halt", "next"),
    }

    tile_video = next(stage for stage in pipeline.stages if stage.stage_id == "tile-video")
    assert tile_video.invocation.metadata["adapter_config"]["executor_id"] == "foley.tile_video"
    assert tile_video.metadata["stop_after_value"] == "tile"

    tile_fanout = next(stage for stage in pipeline.stages if stage.stage_id == "tile-fanout")
    assert tile_fanout.invocation.metadata["adapter_config"]["executor_id"] == "synthetic.fanout.fanout"
    assert tile_fanout.metadata["fan_out_shape"] is True
    assert tile_fanout.metadata["synthetic_kind"] == "dynamic_fanout"
    assert tile_fanout.metadata["fanout_source_stage_id"] == "tile-video"
    assert tile_fanout.metadata["fanout_source_artifact"] == "tiles_manifest"
    assert tile_fanout.metadata["parallel_stage_hint"] is True
    assert tile_fanout.metadata["fanout_branch_count"] == "dynamic"

    tile_prompts = next(stage for stage in pipeline.stages if stage.stage_id == "tile-prompts")
    prompts_wrapper = tile_prompts.metadata["wrapper_then_unroll"]
    assert tile_prompts.invocation is None
    assert tile_prompts.metadata["fan_out_shape"] is True
    assert prompts_wrapper == {
        "kind": "tile_prompt_map",
        "fanout_source_stage_id": "tile-fanout",
        "fanout_source_artifact": "tiles_manifest",
        "global_executor_id": "understanding.visual_understand",
        "child_executor_id": "understanding.visual_understand",
        "manifest_artifact": "prompts.json",
        "output_directory": "_vlm_scratch/",
    }
    assert tile_prompts.metadata["runtime_flags"] == {
        "supports_dry_run": True,
        "dry_run_output_template": "[dry-run prompt for {tile_id}]",
        "stop_after_value": "prompts",
    }
    assert tile_prompts.metadata["bounded_parallelism"] == {
        "arg": "vlm_concurrency",
        "default": 4,
        "kind": "thread_pool",
    }

    foley_audio = next(stage for stage in pipeline.stages if stage.stage_id == "foley-audio")
    foley_wrapper = foley_audio.metadata["wrapper_then_unroll"]
    assert foley_audio.invocation is None
    assert foley_audio.metadata["fan_out_shape"] is True
    assert foley_wrapper == {
        "kind": "tile_foley_map",
        "fanout_source_stage_id": "tile-fanout",
        "fanout_source_artifact": "tiles_manifest",
        "child_executor_id": "fal.fal_foley",
        "manifest_artifact": "tiles.json",
        "output_directory": "audio/",
        "retry_manifest_artifact": "flagged.json",
    }
    assert foley_audio.metadata["runtime_flags"] == {
        "supports_dry_run": True,
        "stop_after_value": "foley",
        "preserves_partial_manifest": True,
    }
    assert foley_audio.metadata["bounded_parallelism"] == {
        "arg": "foley_concurrency",
        "default": 4,
        "kind": "thread_pool",
    }

    review = next(stage for stage in pipeline.stages if stage.stage_id == "review")
    assert review.invocation.metadata["adapter_config"]["executor_id"] == "foley.foley_review"
    assert review.metadata["stop_after_value"] == "review"
    assert review.metadata["produces"] == ["review.html", "flagged.json"]

    spatial_page = next(stage for stage in pipeline.stages if stage.stage_id == "spatial-page")
    assert (
        spatial_page.invocation.metadata["adapter_config"]["executor_id"]
        == "reigh.spatial_audio_page"
    )
    assert spatial_page.metadata["stop_after_value"] == "page"
    assert spatial_page.metadata["media_timeline_outputs"] == [
        "page/index.html",
        "page/manifest.json",
    ]


def test_foley_map_shape_entry_in_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Registry exposes Foley Map with explicit tile fanout metadata."""
    _install_fake_pipeline(monkeypatch, cursor_stage="tile-video")
    _seed_project(tmp_path / "projects")

    monkeypatch.setattr(
        "astrid.core.task.gate.peek_current_step",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("peek_current_step must not be used by Arnold registry")
        ),
    )

    registry_module = importlib.import_module(
        "astrid.core.integrations.arnold.host.registry"
    )
    registry = registry_module.get_host_shape_registry()

    entry = registry.get("foley.foley_map")
    assert entry is not None
    assert entry.workflow_id == "foley.foley_map"
    assert entry.cli_alias == "foley-map"
    assert entry.accepts_human_input is False
    assert entry.entry_stage_id == "tile-video"
    assert entry.stage_labels == {
        "tile-video": "Tile Video",
        "tile-fanout": "Tile Fanout",
        "tile-prompts": "Tile Prompts",
        "foley-audio": "Foley Audio",
        "review": "Review",
        "spatial-page": "Spatial Page",
        "halt": "Halt",
    }
    assert entry.metadata["kind"] == "foley"
    assert entry.metadata["parallel_fan_out"] == "dynamic"
    assert entry.metadata["judge_required"] is False
    assert entry.metadata["compiled"] is True
    assert entry.metadata["loop_lowering"] == "wrapper_then_unroll"
    assert callable(entry.pipeline_builder)
    assert registry.resolve_alias("foley-map") == "foley.foley_map"
    assert registry.is_allowlisted("foley.foley_map") is True


def test_foley_map_child_executors_resolve_from_registry() -> None:
    """Foley Map's declared executor tier remains real registry-backed tools."""
    from astrid.core.execution.executor.registry import load_default_registry

    registry = load_default_registry()
    declared = (
        "foley.tile_video",
        "understanding.visual_understand",
        "fal.fal_foley",
        "foley.foley_review",
        "reigh.spatial_audio_page",
    )
    resolved = tuple(registry.get(executor_id).id for executor_id in declared)
    assert resolved == declared


def test_build_animate_image_pipeline_exposes_named_media_stages_and_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Animate Image must expose the planned six-stage decomposition."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_animate_image_pipeline(
        state={},
        project="demo",
        run_root=str(tmp_path / "run-animate-image"),
        artifact_root=str(tmp_path / "run-animate-image"),
        cas_project_dir=str(tmp_path / "projects" / "demo"),
    )

    assert pipeline.entry_stage_id == "validate-inputs"
    assert [stage.stage_id for stage in pipeline.stages] == [
        "validate-inputs",
        "prepare-source",
        "plan-commands",
        "edit-image",
        "animate-video",
        "write-artifacts",
        "halt",
    ]
    edge_triples = {(edge.source, edge.target, edge.label) for edge in pipeline.edges}
    assert edge_triples == {
        ("validate-inputs", "prepare-source", "next"),
        ("prepare-source", "plan-commands", "next"),
        ("plan-commands", "edit-image", "next"),
        ("edit-image", "animate-video", "next"),
        ("animate-video", "write-artifacts", "next"),
        ("write-artifacts", "halt", "next"),
    }

    validate = next(stage for stage in pipeline.stages if stage.stage_id == "validate-inputs")
    assert validate.invocation is None
    assert validate.metadata["scoped_configs"] == ["credentials.fal"]
    assert validate.metadata["runtime_flags"] == {
        "supports_dry_run": True,
        "preserves_scoped_credentials": True,
    }

    prepare_source = next(stage for stage in pipeline.stages if stage.stage_id == "prepare-source")
    assert prepare_source.invocation is None
    assert prepare_source.metadata["produces"] == ["first_frame.png"]
    assert prepare_source.metadata["video_probe_artifact"] == "plan.video_dimensions"
    assert prepare_source.metadata["target_size_artifact"] == "plan.gpt_image_2_size"

    plan_commands = next(stage for stage in pipeline.stages if stage.stage_id == "plan-commands")
    assert plan_commands.invocation is None
    assert plan_commands.metadata["produces"] == ["plan.json"]
    assert plan_commands.metadata["planned_command_artifacts"] == ["plan.json"]

    edit_image = next(stage for stage in pipeline.stages if stage.stage_id == "edit-image")
    assert edit_image.invocation is None
    assert edit_image.metadata["external_model_id"] == "openai/gpt-image-2/edit"
    assert edit_image.metadata["produces"] == ["generated.<output-format>"]
    assert edit_image.metadata["dry_run_outputs"] == ["generated.<output-format>"]
    assert edit_image.metadata["runtime_conditionals"] == [
        "copies $.use_image when $.skip_generate is true",
        "writes deterministic placeholder output when $.dry_run is true",
    ]

    animate_video = next(stage for stage in pipeline.stages if stage.stage_id == "animate-video")
    assert animate_video.invocation is None
    assert animate_video.metadata["external_model_id"] == "fal-ai/wan/v2.2-14b/animate/move"
    assert animate_video.metadata["produces"] == ["animation.mp4"]
    assert animate_video.metadata["runtime_conditionals"] == [
        "skipped when $.skip_animate is true",
        "records placeholder animation metadata when $.dry_run is true",
    ]

    write_artifacts = next(stage for stage in pipeline.stages if stage.stage_id == "write-artifacts")
    assert write_artifacts.invocation is None
    assert write_artifacts.metadata["produces"] == ["manifest.json"]
    assert write_artifacts.metadata["planned_command_artifacts"] == ["plan.json"]
    assert write_artifacts.metadata["dry_run_outputs"] == [
        "first_frame.png",
        "generated.<output-format>",
        "manifest.json",
    ]
    assert write_artifacts.metadata["final_sidecars"] == [
        "first_frame.png",
        "generated.<output-format>",
        "animation.mp4",
        "manifest.json",
    ]
    assert write_artifacts.metadata["media_timeline_outputs"] == [
        "timelines/<timeline-id>/assembly.jsonl",
    ]
    assert write_artifacts.metadata["ledger_outputs"] == ["events.jsonl"]


def test_animate_image_shape_entry_in_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Registry exposes Animate Image with staged wrapper metadata."""
    _install_fake_pipeline(monkeypatch, cursor_stage="validate-inputs")
    _seed_project(tmp_path / "projects")

    monkeypatch.setattr(
        "astrid.core.task.gate.peek_current_step",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("peek_current_step must not be used by Arnold registry")
        ),
    )

    registry_module = importlib.import_module(
        "astrid.core.integrations.arnold.host.registry"
    )
    registry = registry_module.get_host_shape_registry()

    entry = registry.get("video_editing.animate_image")
    assert entry is not None
    assert entry.workflow_id == "video_editing.animate_image"
    assert entry.cli_alias == "animate-image"
    assert entry.accepts_human_input is False
    assert entry.entry_stage_id == "validate-inputs"
    assert entry.stage_labels == {
        "validate-inputs": "Validate Inputs",
        "prepare-source": "Prepare Source",
        "plan-commands": "Plan Commands",
        "edit-image": "Edit Image",
        "animate-video": "Animate Video",
        "write-artifacts": "Write Artifacts",
        "halt": "Halt",
    }
    assert entry.metadata["kind"] == "video_editing"
    assert entry.metadata["parallel_fan_out"] == 1
    assert entry.metadata["judge_required"] is False
    assert entry.metadata["compiled"] is True
    assert entry.metadata["loop_lowering"] == "staged_wrapper"
    assert entry.metadata["scoped_configs"] == ["credentials.fal"]
    assert callable(entry.pipeline_builder)
    assert registry.resolve_alias("animate-image") == "video_editing.animate_image"
    assert registry.is_allowlisted("video_editing.animate_image") is True


def test_build_logo_ideas_pipeline_exposes_prompt_render_finalize_stages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Logo Ideas must expose staged brief/concepts/render/finalize phases."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_logo_ideas_pipeline(
        state={},
        project="demo",
        run_root=str(tmp_path / "run-logo-ideas"),
        artifact_root=str(tmp_path / "run-logo-ideas"),
        cas_project_dir=str(tmp_path / "projects" / "demo"),
    )

    assert pipeline.entry_stage_id == "normalize-brief"
    assert [stage.stage_id for stage in pipeline.stages] == [
        "normalize-brief",
        "draft-concepts",
        "render-candidates",
        "write-artifacts",
        "halt",
    ]
    edge_triples = {(edge.source, edge.target, edge.label) for edge in pipeline.edges}
    assert edge_triples == {
        ("normalize-brief", "draft-concepts", "next"),
        ("draft-concepts", "render-candidates", "next"),
        ("render-candidates", "write-artifacts", "next"),
        ("write-artifacts", "halt", "next"),
    }

    normalize = next(stage for stage in pipeline.stages if stage.stage_id == "normalize-brief")
    assert normalize.invocation is None
    assert normalize.metadata["produces"] == ["logo-plan.json"]
    assert normalize.metadata["planned_command_artifacts"] == ["logo-plan.json"]

    draft_concepts = next(stage for stage in pipeline.stages if stage.stage_id == "draft-concepts")
    assert draft_concepts.invocation is None
    assert draft_concepts.metadata["external_model_id"] == "accounts/fireworks/models/kimi-k2p5"
    assert draft_concepts.metadata["credential_env"] == ["FIREWORKS_API_KEY"]
    assert draft_concepts.metadata["produces"] == ["concepts.json", "prompts.json"]
    assert draft_concepts.metadata["runtime_flags"] == {
        "supports_dry_run": True,
        "writes_prompt_manifest": True,
    }

    render = next(stage for stage in pipeline.stages if stage.stage_id == "render-candidates")
    assert render.invocation is None
    assert render.metadata["external_model_ids"] == {
        "gpt-image": "openai/gpt-image-2",
        "z-image": "fal-ai/z-image/turbo",
    }
    assert render.metadata["credential_env"] == ["FAL_KEY"]
    assert render.metadata["runtime_flags"] == {
        "supports_dry_run": True,
        "provider_branching": True,
    }
    assert render.metadata["candidate_artifacts"] == [
        "grid.<output-format>",
        "images/logo-<nnn>.<output-format>",
    ]
    assert render.metadata["runtime_conditionals"] == [
        "provider=gpt-image performs a single grid render and mirrors that artifact across candidate records",
        "provider=z-image renders one image per concept and leaves contact-sheet assembly to the final stage",
        "dry_run writes deterministic placeholder image artifacts for whichever provider branch is selected",
    ]

    write_artifacts = next(stage for stage in pipeline.stages if stage.stage_id == "write-artifacts")
    assert write_artifacts.invocation is None
    assert write_artifacts.metadata["produces"] == [
        "logo-manifest.json",
        ".astrid.variants.json",
    ]
    assert write_artifacts.metadata["contact_sheet_outputs"] == [
        "grid.<output-format>",
        "grid.jpg",
    ]
    assert write_artifacts.metadata["final_sidecars"] == [
        "concepts.json",
        "prompts.json",
        "logo-manifest.json",
        ".astrid.variants.json",
    ]
    assert write_artifacts.metadata["ledger_outputs"] == ["events.jsonl"]


def test_logo_ideas_shape_entry_in_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Registry exposes Logo Ideas with staged wrapper metadata."""
    _install_fake_pipeline(monkeypatch, cursor_stage="normalize-brief")
    _seed_project(tmp_path / "projects")

    monkeypatch.setattr(
        "astrid.core.task.gate.peek_current_step",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("peek_current_step must not be used by Arnold registry")
        ),
    )

    registry_module = importlib.import_module(
        "astrid.core.integrations.arnold.host.registry"
    )
    registry = registry_module.get_host_shape_registry()

    entry = registry.get("video_editing.logo_ideas")
    assert entry is not None
    assert entry.workflow_id == "video_editing.logo_ideas"
    assert entry.cli_alias == "logo-ideas"
    assert entry.accepts_human_input is False
    assert entry.entry_stage_id == "normalize-brief"
    assert entry.stage_labels == {
        "normalize-brief": "Normalize Brief",
        "draft-concepts": "Draft Concepts",
        "render-candidates": "Render Candidates",
        "write-artifacts": "Write Artifacts",
        "halt": "Halt",
    }
    assert entry.metadata["kind"] == "video_editing"
    assert entry.metadata["parallel_fan_out"] == 1
    assert entry.metadata["judge_required"] is False
    assert entry.metadata["compiled"] is True
    assert entry.metadata["loop_lowering"] == "staged_wrapper"
    assert entry.metadata["scoped_configs"] == ["credentials.fal"]
    assert entry.metadata["credential_env"] == ["FIREWORKS_API_KEY", "FAL_KEY"]
    assert callable(entry.pipeline_builder)
    assert registry.resolve_alias("logo-ideas") == "video_editing.logo_ideas"
    assert registry.is_allowlisted("video_editing.logo_ideas") is True


def test_build_vary_grid_pipeline_exposes_pattern_select_and_dynamic_fanout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Vary Grid must expose prompt selection and selected-cell fanout metadata."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_vary_grid_pipeline(
        state={},
        project="demo",
        run_root=str(tmp_path / "run-vary-grid"),
        artifact_root=str(tmp_path / "run-vary-grid"),
        cas_project_dir=str(tmp_path / "projects" / "demo"),
    )

    assert pipeline.entry_stage_id == "inspect-source"
    assert [stage.stage_id for stage in pipeline.stages] == [
        "inspect-source",
        "slice-source-grid",
        "select-prompt-pattern",
        "reference-fanout",
        "draft-variations",
        "render-grid",
        "write-artifacts",
        "halt",
    ]
    edge_triples = {(edge.source, edge.target, edge.label) for edge in pipeline.edges}
    assert edge_triples == {
        ("inspect-source", "slice-source-grid", "next"),
        ("slice-source-grid", "select-prompt-pattern", "next"),
        ("select-prompt-pattern", "reference-fanout", "next"),
        ("reference-fanout", "draft-variations", "next"),
        ("draft-variations", "render-grid", "next"),
        ("render-grid", "write-artifacts", "next"),
        ("write-artifacts", "halt", "next"),
    }

    inspect_source = next(stage for stage in pipeline.stages if stage.stage_id == "inspect-source")
    assert inspect_source.invocation is None
    assert inspect_source.metadata["produces"] == ["vary-plan.json"]
    assert inspect_source.metadata["planned_command_artifacts"] == ["vary-plan.json"]

    slice_source = next(stage for stage in pipeline.stages if stage.stage_id == "slice-source-grid")
    assert slice_source.invocation is None
    assert slice_source.metadata["produces"] == ["source_cells/cell-<nnn>.png"]

    pattern_select = next(
        stage for stage in pipeline.stages if stage.stage_id == "select-prompt-pattern"
    )
    assert (
        pattern_select.invocation.metadata["adapter_config"]["executor_id"]
        == "synthetic.media.pattern_select"
    )
    assert pattern_select.metadata["synthetic_kind"] == "pattern_select"
    assert pattern_select.metadata["pattern_names"] == [
        "kimi_variations",
        "no_kimi_direct",
        "dry_run_placeholders",
    ]
    assert [branch["branch_id"] for branch in pattern_select.metadata["branch_metadata"]] == [
        "kimi_variations",
        "no_kimi_direct",
        "dry_run_placeholders",
    ]

    reference_fanout = next(
        stage for stage in pipeline.stages if stage.stage_id == "reference-fanout"
    )
    assert (
        reference_fanout.invocation.metadata["adapter_config"]["executor_id"]
        == "synthetic.fanout.fanout"
    )
    assert reference_fanout.metadata["fan_out_shape"] is True
    assert reference_fanout.metadata["synthetic_kind"] == "dynamic_fanout"
    assert reference_fanout.metadata["fanout_source_stage_id"] == "slice-source-grid"
    assert reference_fanout.metadata["fanout_source_artifact"] == "source_cells"
    assert reference_fanout.metadata["fanout_selector"] == "$.cells"
    assert reference_fanout.metadata["fanout_branch_count"] == "dynamic"
    assert reference_fanout.metadata["parallel_stage_hint"] is True
    assert reference_fanout.metadata["fanout_branches"] == [
        {
            "index": 0,
            "payload": {
                "branch_id": "selected-reference-cell",
                "source_artifact": "source_cells/cell-<nnn>.png",
                "selector": "$.cells",
                "output_artifact": "refs/ref-<nnn>.png",
            },
        }
    ]

    draft = next(stage for stage in pipeline.stages if stage.stage_id == "draft-variations")
    assert draft.invocation is None
    assert draft.metadata["selected_pattern_stage_id"] == "select-prompt-pattern"
    assert draft.metadata["external_model_id"] == "accounts/fireworks/models/kimi-k2p5"
    assert draft.metadata["credential_env"] == ["FIREWORKS_API_KEY"]
    assert draft.metadata["produces"] == ["concepts.json", "prompts.json"]
    assert draft.metadata["runtime_conditionals"] == [
        "skips Fireworks when $.no_kimi is true",
        "writes deterministic planned concepts when $.dry_run is true",
    ]

    render = next(stage for stage in pipeline.stages if stage.stage_id == "render-grid")
    assert render.invocation is None
    assert render.metadata["external_model_id"] == "openai/gpt-image-2/edit"
    assert render.metadata["credential_env"] == ["FAL_KEY"]
    assert render.metadata["produces"] == ["grid.<output-format>"]
    assert render.metadata["dry_run_outputs"] == ["grid.<output-format>"]

    write_artifacts = next(stage for stage in pipeline.stages if stage.stage_id == "write-artifacts")
    assert write_artifacts.invocation is None
    assert write_artifacts.metadata["produces"] == ["vary-manifest.json"]
    assert write_artifacts.metadata["final_sidecars"] == [
        "vary-plan.json",
        "concepts.json",
        "prompts.json",
        "vary-manifest.json",
        "grid.<output-format>",
        "favicons.png",
    ]
    assert write_artifacts.metadata["ledger_outputs"] == ["events.jsonl"]


def test_vary_grid_shape_entry_in_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Registry exposes Vary Grid with pattern-select dynamic fanout metadata."""
    _install_fake_pipeline(monkeypatch, cursor_stage="inspect-source")
    _seed_project(tmp_path / "projects")

    monkeypatch.setattr(
        "astrid.core.task.gate.peek_current_step",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("peek_current_step must not be used by Arnold registry")
        ),
    )

    registry_module = importlib.import_module(
        "astrid.core.integrations.arnold.host.registry"
    )
    registry = registry_module.get_host_shape_registry()

    entry = registry.get("video_editing.vary_grid")
    assert entry is not None
    assert entry.workflow_id == "video_editing.vary_grid"
    assert entry.cli_alias == "vary-grid"
    assert entry.accepts_human_input is False
    assert entry.entry_stage_id == "inspect-source"
    assert entry.stage_labels == {
        "inspect-source": "Inspect Source",
        "slice-source-grid": "Slice Source Grid",
        "select-prompt-pattern": "Select Prompt Pattern",
        "reference-fanout": "Reference Fanout",
        "draft-variations": "Draft Variations",
        "render-grid": "Render Grid",
        "write-artifacts": "Write Artifacts",
        "halt": "Halt",
    }
    assert entry.metadata["kind"] == "video_editing"
    assert entry.metadata["parallel_fan_out"] == "dynamic"
    assert entry.metadata["judge_required"] is False
    assert entry.metadata["compiled"] is True
    assert entry.metadata["loop_lowering"] == "pattern_select_dynamic_fanout"
    assert entry.metadata["scoped_configs"] == ["credentials.fal"]
    assert entry.metadata["credential_env"] == ["FIREWORKS_API_KEY", "FAL_KEY"]
    assert callable(entry.pipeline_builder)
    assert registry.resolve_alias("vary-grid") == "video_editing.vary_grid"
    assert registry.is_allowlisted("video_editing.vary_grid") is True


def test_build_iteration_video_pipeline_exposes_renderer_selection_and_explicit_finalization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Iteration Video must expose child phases and final artifact writes."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_iteration_video_pipeline(
        state={},
        project="demo",
        run_root=str(tmp_path / "run-iteration-video"),
        artifact_root=str(tmp_path / "run-iteration-video"),
        cas_project_dir=str(tmp_path / "projects" / "demo"),
    )

    assert pipeline.entry_stage_id == "resolve-thread"
    assert [stage.stage_id for stage in pipeline.stages] == [
        "resolve-thread",
        "prepare-iteration",
        "select-renderers",
        "assemble-brief",
        "render-video",
        "finalize-iteration",
        "halt",
    ]
    edge_triples = {(edge.source, edge.target, edge.label) for edge in pipeline.edges}
    assert edge_triples == {
        ("resolve-thread", "prepare-iteration", "next"),
        ("prepare-iteration", "select-renderers", "next"),
        ("select-renderers", "assemble-brief", "next"),
        ("assemble-brief", "render-video", "next"),
        ("render-video", "finalize-iteration", "next"),
        ("finalize-iteration", "halt", "next"),
    }

    resolve = next(stage for stage in pipeline.stages if stage.stage_id == "resolve-thread")
    assert resolve.invocation is None
    assert resolve.metadata["produces"] == ["target.json"]
    assert resolve.metadata["runtime_flags"] == {
        "supports_active_thread_ref": True,
        "validates_ulid_thread": True,
    }

    prepare = next(stage for stage in pipeline.stages if stage.stage_id == "prepare-iteration")
    assert prepare.invocation is None
    assert prepare.metadata["executor_id"] == "iteration.prepare"
    assert prepare.metadata["cache_model_id"] == "understanding.understand.v1"
    assert prepare.metadata["produces"] == [
        ".<out>.prepare/iteration.manifest.json",
        ".<out>.prepare/iteration.quality.json",
    ]

    renderer_select = next(stage for stage in pipeline.stages if stage.stage_id == "select-renderers")
    assert (
        renderer_select.invocation.metadata["adapter_config"]["executor_id"]
        == "synthetic.media.pattern_select"
    )
    assert renderer_select.metadata["synthetic_kind"] == "pattern_select"
    assert renderer_select.metadata["pattern_names"] == [
        "image_grid",
        "audio_waveform",
        "generic_card",
    ]
    assert [branch["branch_id"] for branch in renderer_select.metadata["branch_metadata"]] == [
        "image_grid",
        "audio_waveform",
        "generic_card",
    ]

    assemble = next(stage for stage in pipeline.stages if stage.stage_id == "assemble-brief")
    assert assemble.invocation is None
    assert assemble.metadata["executor_id"] == "iteration.assemble"
    assert assemble.metadata["produces"] == [
        "hype.timeline.json",
        "hype.assets.json",
        "iteration.timeline.json",
        "iteration.manifest.json",
        "iteration.report.html",
        "iteration.quality.json",
    ]

    render = next(stage for stage in pipeline.stages if stage.stage_id == "render-video")
    assert render.invocation is None
    assert render.metadata["executor_id"] == "rendering.render"
    assert render.metadata["produces"] == ["hype.mp4"]

    finalize = next(stage for stage in pipeline.stages if stage.stage_id == "finalize-iteration")
    assert finalize.invocation is None
    assert finalize.metadata["produces"] == [
        "iteration.mp4",
        "iteration.timeline.json",
        "iteration.manifest.json",
        "iteration.report.html",
        "iteration.quality.json",
        ".astrid.variants.json",
        ".astrid/threads/<thread-id>/groups.json",
    ]
    assert finalize.metadata["final_media_outputs"] == ["iteration.mp4"]
    assert finalize.metadata["final_report_outputs"] == ["iteration.report.html"]
    assert finalize.metadata["final_quality_outputs"] == ["iteration.quality.json"]
    assert finalize.metadata["final_manifest_outputs"] == ["iteration.manifest.json"]
    assert finalize.metadata["final_thread_group_outputs"] == [
        ".astrid.variants.json",
        ".astrid/threads/<thread-id>/groups.json",
    ]
    assert finalize.metadata["final_sidecars"] == [
        "iteration.timeline.json",
        "iteration.manifest.json",
        "iteration.report.html",
        "iteration.quality.json",
        ".astrid.variants.json",
        ".astrid/threads/<thread-id>/groups.json",
    ]
    assert finalize.metadata["ledger_outputs"] == ["events.jsonl"]


def test_iteration_video_shape_entry_in_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Registry exposes Iteration Video with explicit finalization metadata."""
    _install_fake_pipeline(monkeypatch, cursor_stage="resolve-thread")
    _seed_project(tmp_path / "projects")

    monkeypatch.setattr(
        "astrid.core.task.gate.peek_current_step",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("peek_current_step must not be used by Arnold registry")
        ),
    )

    registry_module = importlib.import_module(
        "astrid.core.integrations.arnold.host.registry"
    )
    registry = registry_module.get_host_shape_registry()

    entry = registry.get("video_editing.iteration_video")
    assert entry is not None
    assert entry.workflow_id == "video_editing.iteration_video"
    assert entry.cli_alias == "iteration-video"
    assert entry.accepts_human_input is False
    assert entry.entry_stage_id == "resolve-thread"
    assert entry.stage_labels == {
        "resolve-thread": "Resolve Thread",
        "prepare-iteration": "Prepare Iteration",
        "select-renderers": "Select Renderers",
        "assemble-brief": "Assemble Brief",
        "render-video": "Render Video",
        "finalize-iteration": "Finalize Iteration",
        "halt": "Halt",
    }
    assert entry.metadata["kind"] == "video_editing"
    assert entry.metadata["parallel_fan_out"] == 1
    assert entry.metadata["judge_required"] is False
    assert entry.metadata["compiled"] is True
    assert entry.metadata["loop_lowering"] == "pattern_select_explicit_finalization"
    assert entry.metadata["child_executors"] == [
        "iteration.prepare",
        "iteration.assemble",
        "rendering.render",
    ]
    assert callable(entry.pipeline_builder)
    assert registry.resolve_alias("iteration-video") == "video_editing.iteration_video"
    assert registry.is_allowlisted("video_editing.iteration_video") is True
