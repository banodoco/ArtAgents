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


def test_build_text_analysis_summarize_pipeline_has_linear_topology_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entry stage is summarize; single edge summarize -> halt; no back-edges."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_text_analysis_summarize_pipeline(
        state={"text": "sample input"},
        project="demo",
        run_root="/tmp/run-789",
        artifact_root="/tmp/run-789",
        cas_project_dir="/tmp/projects/demo",
    )

    assert pipeline.entry_stage_id == "summarize"
    assert [stage.stage_id for stage in pipeline.stages] == ["summarize", "halt"]
    assert [stage.label for stage in pipeline.stages] == ["Summarize", "Halt"]
    assert [(edge.source, edge.target, edge.label) for edge in pipeline.edges] == [
        ("summarize", "halt", "next"),
    ]

    # No back-edges (compare WE-1 which has review -> generate)
    edge_targets = {edge.target for edge in pipeline.edges}
    assert "generate" not in edge_targets
    assert "summarize" not in edge_targets  # no self-loops or back-edges

    summarize_stage = next(stage for stage in pipeline.stages if stage.stage_id == "summarize")
    halt_stage = next(stage for stage in pipeline.stages if stage.stage_id == "halt")

    assert summarize_stage.invocation is not None
    assert halt_stage.invocation is None  # terminal has no invocation

    # summarise stage metadata
    summarize_meta = getattr(summarize_stage, "metadata", {})
    assert summarize_meta.get("entry") is True
    assert summarize_meta.get("linear") is True
    assert summarize_meta.get("workflow_id") == "text_analysis.summarize"
    assert summarize_meta.get("stage_id") == "summarize"

    halt_meta = getattr(halt_stage, "metadata", {})
    assert halt_meta.get("terminal") is True


def test_build_text_analysis_summarize_pipeline_uses_valid_adapter_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Summarize stage invocation carries executor_id=text.summarize via allowlist."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")
    pipeline = shapes_module.build_text_analysis_summarize_pipeline(
        state={"text": "hello"},
        project="demo",
        run_root="/tmp/run-789",
        artifact_root="/tmp/run-789",
        cas_project_dir="/tmp/projects/demo",
    )

    summarize_stage = next(stage for stage in pipeline.stages if stage.stage_id == "summarize")
    inv_metadata = getattr(summarize_stage.invocation, "metadata", {})
    adapter_cfg = inv_metadata.get("adapter_config", {})

    assert adapter_cfg.get("executor_id") == "text.summarize"
    assert adapter_cfg.get("workflow_id") == "text_analysis.summarize"
    assert adapter_cfg.get("stage_id") == "summarize"
    assert adapter_cfg.get("input_map", {}).get("text") == "text"
    assert adapter_cfg.get("mode") == "inline"
    assert adapter_cfg.get("requires_ack") is False


def test_build_text_analysis_summarize_pipeline_contains_no_host_side_while_loop() -> None:
    source = inspect.getsource(
        importlib.import_module(
            "astrid.core.integrations.arnold.host.shapes"
        ).build_text_analysis_summarize_pipeline
    )
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))


def test_text_analysis_summarize_unsupported_step_raises_before_state_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passing an unknown executor leaf must fail with UnsupportedStepError."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")

    # Temporarily remove the known template to simulate an unsupported leaf
    from astrid.core.integrations.arnold.host import invocation as inv_module

    original = dict(inv_module.ALLOWLISTED_INVOCATION_TEMPLATES)
    try:
        stripped = dict(original)
        stripped.pop("text_analysis.summarize", None)
        monkeypatch.setattr(inv_module, "ALLOWLISTED_INVOCATION_TEMPLATES", stripped)
        # Also patch the shapes module's reference (it imports at module level)
        monkeypatch.setattr(
            shapes_module,
            "ALLOWLISTED_INVOCATION_TEMPLATES",
            stripped,
        )

        with pytest.raises(shapes_module.UnsupportedStepError) as exc_info:
            shapes_module.build_text_analysis_summarize_pipeline(
                state={"text": "test"},
                project="demo",
                run_root="/tmp/run-789",
                artifact_root="/tmp/run-789",
            )
        assert "unsupported step" in str(exc_info.value).lower()
        assert "summarize" in str(exc_info.value)
        assert "text_analysis.summarize" in str(exc_info.value)
    finally:
        monkeypatch.setattr(inv_module, "ALLOWLISTED_INVOCATION_TEMPLATES", original)
        monkeypatch.setattr(shapes_module, "ALLOWLISTED_INVOCATION_TEMPLATES", original)


def test_text_analysis_summarize_is_not_a_generic_orchestrator_migration_compiler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove the summarize shape is a single linear hand-authored path, not a compiler."""
    _install_fake_pipeline(monkeypatch)

    shapes_module = importlib.import_module("astrid.core.integrations.arnold.host.shapes")

    source = inspect.getsource(shapes_module.build_text_analysis_summarize_pipeline)
    tree = ast.parse(source)

    # No while/for loops at host level
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))
    # The only for-loops should be the stage/edge registration iterators
    for_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.For)]
    # Allow for _ in (summarize_stage, halt_stage) and for _ in (edge, )
    # but no dynamic iteration over unknown lists
    for for_node in for_nodes:
        if isinstance(for_node.iter, ast.Tuple):
            continue  # static tuple iteration is fine
        # If iter is a Call, check it's not some dynamic compilation
        if isinstance(for_node.iter, ast.Call):
            pytest.fail("summarize pipeline must not use dynamic iteration / compilation")

    # No exec/eval/compile calls
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("exec", "eval", "compile")
        for node in ast.walk(tree)
    )

    # The pipeline builder must be used directly (one PipelineBuilder instantiation)
    builder_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "PipelineBuilder"
    ]
    assert len(builder_calls) == 1, "summarize shape must use exactly one PipelineBuilder"


def test_text_analysis_summarize_shape_entry_in_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Registry exposes the text_analysis.summarize shape with correct metadata."""
    _install_fake_pipeline(monkeypatch, cursor_stage="summarize")
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
    assert entry.entry_stage_id == "summarize"
    assert entry.stage_labels == {"summarize": "Summarize", "halt": "Halt"}
    assert entry.metadata["kind"] == "analysis"
    assert entry.metadata["parallel_fan_out"] == 1
    assert entry.metadata["judge_required"] is False
    assert callable(entry.pipeline_builder)

    # Alias resolution
    assert registry.resolve_alias("summarize") == "text_analysis.summarize"
    assert registry.is_allowlisted("text_analysis.summarize") is True
