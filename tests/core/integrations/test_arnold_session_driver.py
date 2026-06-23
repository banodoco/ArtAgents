from __future__ import annotations

import importlib
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from astrid.core._shared.jsonio import write_json_atomic
from astrid.core.integrations.arnold.session.manifest import (
    EventLineageHashes,
    SegmentRecord,
    SessionManifest,
    write_manifest_file,
)
from astrid.core.integrations.arnold.session.records import (
    ARNOLD_RUN_FILENAME,
    SESSION_SUCCESSION_WORKFLOW_ID,
)
from astrid.core.integrations.arnold.session.state import StateRef, write_state_file
from astrid.core.project.current_run import write_current_run
from astrid.core.session.lease import write_lease_init
from astrid.core.task.events import (
    EVENTS_FILENAME,
    ZERO_HASH,
    append_event_locked,
    make_plan_initialized_event,
    verify_chain,
)
from astrid.core.task.plan import Step, TaskPlan
from astrid.core.task.plan.verbs import _make_plan_mutated_event


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
class _CrossCutting:
    taint: tuple[str, ...] = ()
    cost: dict[str, Any] = field(default_factory=dict)
    lineage: tuple[str, ...] = ()
    deadline: Any | None = None
    cancellation: Any | None = None
    retry_budget: dict[str, Any] = field(default_factory=dict)
    error_class: Any | None = None


class _RuntimeEnvelope:
    run_id = ""
    artifact_root = ""
    resume_cursor = None
    cross_cutting = _CrossCutting()

    def __init__(
        self,
        run_id: str = "",
        artifact_root: str = "",
        resume_cursor: Any | None = None,
        **_: Any,
    ) -> None:
        self.run_id = run_id
        self.artifact_root = artifact_root
        self.resume_cursor = resume_cursor
        self.cross_cutting = _CrossCutting()


@dataclass(frozen=True)
class _AdvanceOutcome:
    kind: str = "advanced"


@dataclass(frozen=True)
class _CheckpointOutcome:
    cursor: Any | None = None


@dataclass(frozen=True)
class _Suspension:
    kind: str = "human"
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
    name: str
    step: Any | None = None
    edges: tuple[Any, ...] = ()
    decision_vocabulary: Any = frozenset()
    decision_routes: dict[str, str | None] = field(default_factory=dict)
    suspension_schema: dict[str, Any] | None = None
    invocation: Any | None = None
    loop_condition: Any | None = None
    # Aliases / backward-compat for duck-typed access
    stage_id: str | None = None
    label: str | None = None
    suspension: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.stage_id is None:
            object.__setattr__(self, "stage_id", self.name)
        if self.label is None:
            object.__setattr__(self, "label", self.name)
        if self.suspension is None and self.suspension_schema is not None:
            object.__setattr__(
                self,
                "suspension",
                _Suspension(
                    resume_input_schema=self.suspension_schema.get("resume_input_schema")
                ),
            )


@dataclass(frozen=True)
class _ParallelStage:
    name: str
    steps: tuple[Any, ...] = field(default_factory=tuple)
    join: Any | None = None
    edges: tuple[Any, ...] = ()
    # Aliases / backward-compat for duck-typed access
    stage_id: str | None = None
    label: str | None = None
    stages: tuple[Any, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.stage_id is None:
            object.__setattr__(self, "stage_id", self.name)
        if self.label is None:
            object.__setattr__(self, "label", self.name)
        if not self.stages:
            object.__setattr__(self, "stages", self.steps)


@dataclass(frozen=True)
class _Edge:
    label: str
    target: str
    kind: str = "normal"
    recommendation: Any | None = None
    # Backward-compat for duck-typed / manifest access
    source: str | None = None
    source_port: str | None = None
    target_port: str | None = None
    logical_type: str | None = None
    artifact_type: str | None = None
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


class _FakeDriver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, Any | None]] = []

    def resume(self, envelope: _RuntimeEnvelope, cursor: Any) -> _RuntimeEnvelope:
        self.calls.append(("resume", envelope, cursor))
        envelope.resume_cursor = cursor
        return envelope

    def advance(self, envelope: _RuntimeEnvelope) -> _AdvanceOutcome:
        self.calls.append(("advance", envelope, None))
        return _AdvanceOutcome()

    def checkpoint(self, envelope: _RuntimeEnvelope) -> _CheckpointOutcome:
        self.calls.append(("checkpoint", envelope, None))
        return _CheckpointOutcome(cursor=envelope.resume_cursor)


class _StepwiseDriver(_FakeDriver):
    pass


def _install_fake_pipeline(monkeypatch: pytest.MonkeyPatch, cursor_store: dict[str, Any]) -> None:
    pipeline = types.ModuleType("arnold.pipeline")

    def _persist_resume_cursor(artifact_root: object, cursor: object) -> None:
        cursor_store[str(artifact_root)] = cursor

    def _read_resume_cursor(artifact_root: object) -> object | None:
        return cursor_store.get(str(artifact_root))

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
        "persist_resume_cursor": _persist_resume_cursor,
        "read_resume_cursor": _read_resume_cursor,
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


class _WriterContext:
    def __init__(self, run_dir: Path, epoch: int) -> None:
        self.run_dir = run_dir
        self.expected_writer_epoch = epoch
        self.appended: list[dict[str, Any]] = []

    def __enter__(self) -> "_WriterContext":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        from astrid.core.task.events import _peek_tail_hash

        stored = append_event_locked(
            self.run_dir,
            event,
            expected_writer_epoch=self.expected_writer_epoch,
            expected_prev_hash=_peek_tail_hash(self.run_dir / EVENTS_FILENAME),
        )
        self.appended.append(stored)
        return stored


def _plan() -> TaskPlan:
    return TaskPlan(
        plan_id="plan-1",
        version=2,
        steps=(Step(id="review", adapter="manual", command="ack", requires_ack=True),),
    )


def _plan_hash(plan: TaskPlan) -> str:
    import hashlib

    from astrid.core.task.events import canonical_event_json

    return f"sha256:{hashlib.sha256(canonical_event_json(plan.to_dict()).encode('utf-8')).hexdigest()}"


def _setup_session_run(tmp_path: Path, *, project: str = "demo") -> Path:
    run_id = "run-session"
    projects_root = tmp_path / "projects"
    run_root = projects_root / project / "runs" / run_id
    run_root.mkdir(parents=True)
    write_current_run(project, run_id, root=projects_root)
    plan = _plan()
    plan_hash = _plan_hash(plan)
    write_json_atomic(run_root / "plan.json", plan.to_dict())
    write_json_atomic(
        run_root / ARNOLD_RUN_FILENAME,
        {
            "engine": "arnold",
            "workflow_id": SESSION_SUCCESSION_WORKFLOW_ID,
            "mode": "session-succession",
            "run_id": run_id,
            "status": "suspended",
            "current_segment": "seg-001",
            "plan_hash": plan_hash,
        },
    )
    state = {"approved": False}
    write_state_file(run_root, state)
    write_lease_init(run_root, session_id="session-1", plan_hash=plan_hash)
    started = append_event_locked(
        run_root,
        make_plan_initialized_event(run_id, plan.to_dict(), plan_hash),
        expected_writer_epoch=0,
        expected_prev_hash=ZERO_HASH,
    )
    write_manifest_file(
        run_root,
        SessionManifest(
            run_id=run_id,
            artifact_root=str(run_root),
            current_segment_id="seg-001",
            segments=(
                SegmentRecord(
                    segment_id="seg-001",
                    plan_hash=plan_hash,
                    state=StateRef.from_state(state),
                    status="running",
                    event_lineage=EventLineageHashes(
                        segment_start_hash=str(started["hash"]),
                    ),
                ),
            ),
        ),
    )
    return run_root


def _import_driver_module():
    return importlib.import_module("astrid.core.integrations.arnold.session.driver")


def test_pure_resume_delegates_to_stepwise_resume_without_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cursor_store: dict[str, Any] = {}
    _install_fake_pipeline(monkeypatch, cursor_store)
    run_root = _setup_session_run(tmp_path)
    cursor = _ResumeCursorRef(
        plugin_id="astrid.arnold.host",
        run_id="run-session",
        cursor={"stage": "review"},
    )
    cursor_store[str(run_root)] = cursor
    fake_driver = _FakeDriver()
    module = _import_driver_module()

    result = module.resume_session_run(
        "demo",
        run_id="run-session",
        root=tmp_path / "projects",
        human_input={"decision": {"action": "approve"}},
        driver=fake_driver,
    )

    assert result.to_segment_id == "seg-001"
    assert [call[0] for call in fake_driver.calls] == ["resume", "checkpoint"]
    events = [json.loads(line) for line in (run_root / EVENTS_FILENAME).read_text().splitlines()]
    assert [event["kind"] for event in events] == ["plan_initialized"]


def test_mutation_resume_commits_one_boundary_then_launches_successor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cursor_store: dict[str, Any] = {}
    _install_fake_pipeline(monkeypatch, cursor_store)
    run_root = _setup_session_run(tmp_path)
    cursor = _ResumeCursorRef(
        plugin_id="astrid.arnold.host",
        run_id="run-session",
        cursor={"stage": "review"},
    )
    fake_driver = _FakeDriver()
    writer = _WriterContext(run_root, epoch=0)
    module = _import_driver_module()

    result = module.resume_session_run(
        "demo",
        run_id="run-session",
        root=tmp_path / "projects",
        human_input={"plan_mutation": {"plan_hash": "sha256:next"}},
        resume_cursor=cursor,
        driver=fake_driver,
        writer_context_factory=lambda *_args, **_kwargs: writer,
    )

    assert result.from_segment_id == "seg-001"
    assert result.to_segment_id == "seg-002"
    assert result.writer_epoch == 0
    assert len(writer.appended) == 1
    assert writer.appended[0]["kind"] == "segment_boundary"
    assert writer.appended[0]["from_segment_id"] == "seg-001"
    assert writer.appended[0]["to_segment_id"] == "seg-002"
    assert verify_chain(run_root / EVENTS_FILENAME)[0] is True
    assert cursor_store[str(run_root)] is cursor

    run_record = json.loads((run_root / ARNOLD_RUN_FILENAME).read_text())
    manifest = json.loads((run_root / "session-manifest.json").read_text())
    pipeline_manifest = json.loads((run_root / "pipeline.json").read_text())

    assert run_record["current_segment"] == "seg-002"
    assert run_record["status"] == "running"
    assert manifest["current_segment_id"] == "seg-002"
    assert [segment["status"] for segment in manifest["segments"]] == ["frozen", "running"]
    assert manifest["segments"][1]["event_lineage"]["segment_boundary_hash"] == result.boundary_hash
    assert pipeline_manifest["entry_stage_id"] == "review"
    assert [call[0] for call in fake_driver.calls] == ["advance", "checkpoint"]


def test_mutation_resume_compiles_successor_from_ledger_not_plan_projection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cursor_store: dict[str, Any] = {}
    _install_fake_pipeline(monkeypatch, cursor_store)
    run_root = _setup_session_run(tmp_path)
    write_json_atomic(
        run_root / "plan.json",
        TaskPlan(
            plan_id="poison-projection",
            version=2,
            steps=(Step(id="poison", adapter="local", command="echo poison"),),
        ).to_dict(),
    )
    events = [json.loads(line) for line in (run_root / EVENTS_FILENAME).read_text().splitlines()]
    append_event_locked(
        run_root,
        _make_plan_mutated_event(
            "agent:test",
            0,
            {
                "op": "add",
                "after": "review",
                "step": {"id": "ship", "adapter": "local", "command": "echo ship"},
            },
        ),
        expected_writer_epoch=0,
        expected_prev_hash=str(events[-1]["hash"]),
    )
    cursor = _ResumeCursorRef(
        plugin_id="astrid.arnold.host",
        run_id="run-session",
        cursor={"stage": "review"},
    )
    writer = _WriterContext(run_root, epoch=0)
    module = _import_driver_module()

    result = module.resume_session_run(
        "demo",
        run_id="run-session",
        root=tmp_path / "projects",
        human_input={"plan_mutation": {"op": "add"}},
        resume_cursor=cursor,
        driver=_FakeDriver(),
        writer_context_factory=lambda *_args, **_kwargs: writer,
    )

    pipeline_manifest = json.loads((run_root / "pipeline.json").read_text())
    assert result.to_segment_id == "seg-002"
    assert [stage["stage_id"] for stage in pipeline_manifest["stages"]] == [
        "review",
        "ship",
        "halt",
    ]
    assert "poison" not in {stage["stage_id"] for stage in pipeline_manifest["stages"]}


def test_mutation_resume_rejects_cursor_for_different_run_before_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cursor_store: dict[str, Any] = {}
    _install_fake_pipeline(monkeypatch, cursor_store)
    run_root = _setup_session_run(tmp_path)
    bad_cursor = _ResumeCursorRef(
        plugin_id="astrid.arnold.host",
        run_id="other-run",
        cursor={"stage": "review"},
    )
    writer = _WriterContext(run_root, epoch=0)
    module = _import_driver_module()

    with pytest.raises(module.SessionDriverError, match="does not match"):
        module.resume_session_run(
            "demo",
            run_id="run-session",
            root=tmp_path / "projects",
            human_input={"plan_mutation": {"plan_hash": "sha256:next"}},
            resume_cursor=bad_cursor,
            driver=_FakeDriver(),
            writer_context_factory=lambda *_args, **_kwargs: writer,
        )

    events = [json.loads(line) for line in (run_root / EVENTS_FILENAME).read_text().splitlines()]
    assert [event["kind"] for event in events] == ["plan_initialized"]
    assert writer.appended == []
