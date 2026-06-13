from __future__ import annotations

import importlib
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from astrid.core.project import create_project
from astrid.core.project.current_run import read_current_run


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
    cursor: str = "cursor"


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
class _BuiltPipeline:
    entry_stage_id: str
    stages: tuple[Any, ...]
    edges: tuple[Any, ...]


class _PipelineBuilder:
    def __init__(self) -> None:
        self.entry_stage_id: str | None = None
        self.stages: list[Any] = []
        self.edges: list[Any] = []

    def add_stage(self, stage: Any) -> None:
        self.stages.append(stage)

    def add_edge(self, edge: Any) -> None:
        self.edges.append(edge)

    def set_entry_stage(self, stage_id: str) -> None:
        self.entry_stage_id = stage_id

    def build(self) -> _BuiltPipeline:
        assert self.entry_stage_id is not None
        return _BuiltPipeline(self.entry_stage_id, tuple(self.stages), tuple(self.edges))


def _install_fake_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    checkpoint_error: Exception | None = None,
    cursor_stage: str | None = None,
    resume_cursors: list[Any] | None = None,
    persisted_cursors: list[Any] | None = None,
    dynamic_cursor_progression: bool = False,
) -> list[str]:
    calls: list[str] = []
    cursor_store: dict[str, _ResumeCursorRef] = {}

    def _cursor_for_stage(
        *,
        run_id: str,
        stage: str,
        previous_stage: str | None = None,
        iteration: int | None = None,
        human_input: dict[str, Any] | None = None,
        artifact: str | None = None,
    ) -> _ResumeCursorRef:
        cursor: dict[str, Any] = {"stage": stage}
        if previous_stage is not None:
            cursor["previous_stage"] = previous_stage
        if iteration is not None:
            cursor["iteration"] = iteration
        if human_input is not None:
            cursor["human_input"] = human_input
            cursor["feedback_notes"] = human_input["decision"].get("notes", "")
        if artifact is not None:
            cursor["artifact"] = artifact
        return _ResumeCursorRef(
            plugin_id="astrid.arnold.host",
            run_id=run_id,
            cursor=cursor,
        )

    class _StepwiseDriver:
        def advance(self, envelope: object) -> _AdvanceOutcome:
            calls.append("advance")
            if dynamic_cursor_progression:
                current = getattr(envelope, "resume_cursor", None)
                current_cursor = getattr(current, "cursor", None)
                if isinstance(current_cursor, dict):
                    stage = current_cursor.get("stage")
                    run_id = getattr(envelope, "run_id", "")
                    if stage == "generate":
                        iteration = int(current_cursor.get("iteration", 1)) + 1
                        envelope.resume_cursor = _cursor_for_stage(
                            run_id=run_id,
                            stage="review",
                            previous_stage="generate",
                            iteration=iteration,
                            human_input=current_cursor.get("human_input"),
                            artifact=f"candidate-v{iteration}.png",
                        )
                    elif stage == "halt":
                        envelope.resume_cursor = _cursor_for_stage(
                            run_id=run_id,
                            stage="halt",
                            previous_stage=str(current_cursor.get("previous_stage", "review")),
                            iteration=int(current_cursor.get("iteration", 2)),
                            human_input=current_cursor.get("human_input"),
                            artifact=current_cursor.get("artifact"),
                        )
            return _AdvanceOutcome()

        def checkpoint(self, envelope: object) -> _CheckpointOutcome:
            calls.append("checkpoint")
            if checkpoint_error is not None:
                raise checkpoint_error
            if dynamic_cursor_progression:
                run_id = getattr(envelope, "run_id", "")
                artifact_root = getattr(envelope, "artifact_root", "")
                if artifact_root and getattr(envelope, "resume_cursor", None) is not None:
                    cursor_store[str(artifact_root)] = getattr(envelope, "resume_cursor")
                elif artifact_root and artifact_root not in cursor_store:
                    cursor_store[str(artifact_root)] = _cursor_for_stage(
                        run_id=run_id,
                        stage="review",
                        previous_stage="generate",
                        iteration=1,
                        artifact="candidate-v1.png",
                    )
            return _CheckpointOutcome()

        def resume(self, envelope: object, cursor: object) -> _RuntimeEnvelope:
            calls.append("resume")
            if resume_cursors is not None:
                resume_cursors.append(cursor)
            if dynamic_cursor_progression and isinstance(cursor, _ResumeCursorRef):
                cursor_payload = dict(cursor.cursor)
                stage = str(cursor_payload.get("stage"))
                previous_stage = str(cursor_payload.get("previous_stage", "review"))
                human_input = cursor_payload.get("human_input")
                iteration = int(cursor_payload.get("iteration", 1))
                artifact = cursor_payload.get("artifact")
                envelope.resume_cursor = _cursor_for_stage(
                    run_id=getattr(envelope, "run_id", ""),
                    stage=stage,
                    previous_stage=previous_stage,
                    iteration=iteration,
                    human_input=human_input if isinstance(human_input, dict) else None,
                    artifact=artifact if isinstance(artifact, str) else None,
                )
            return envelope  # type: ignore[return-value]

    pipeline = types.ModuleType("arnold.pipeline")
    def _persist_resume_cursor(_artifact_root: object, cursor: object, *args: object, **kwargs: object) -> None:
        del args, kwargs
        calls.append("persist_resume_cursor")
        if persisted_cursors is not None:
            persisted_cursors.append(cursor)

    def _read_resume_cursor(*args: object, **kwargs: object) -> _ResumeCursorRef | None:
        calls.append("read_resume_cursor")
        if dynamic_cursor_progression and args:
            stored = cursor_store.get(str(args[0]))
            if stored is not None:
                return stored
        if cursor_stage is None:
            return None
        run_id = ""
        if args:
            run_id = Path(str(args[0])).name
        return _ResumeCursorRef(
            plugin_id="astrid.arnold.host",
            run_id=run_id,
            cursor={"stage": cursor_stage},
        )

    exports = {
        "RuntimeEnvelope": _RuntimeEnvelope,
        "ResumeCursorRef": _ResumeCursorRef,
        "AdvanceOutcome": _AdvanceOutcome,
        "CheckpointOutcome": _CheckpointOutcome,
        "StepwiseDriver": _StepwiseDriver,
        "PipelineBuilder": _PipelineBuilder,
        "Stage": _Stage,
        "ParallelStage": type("ParallelStage", (), {}),
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
    return calls


@pytest.fixture(autouse=True)
def _clean_modules_fixture() -> None:
    _clear_host_modules()
    yield
    _clear_host_modules()


def test_arnold_start_writes_current_run_last_after_validated_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_path / "projects"))
    create_project("demo")
    calls = _install_fake_pipeline(monkeypatch)
    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")

    rc = cli.cmd_start(
        [
            "we.refine_image",
            "--project",
            "demo",
            "--name",
            "run-arnold",
            "--state",
            '{"prompt":"draw"}',
            "--input",
            "seed=42",
        ]
    )

    run_root = tmp_path / "projects" / "demo" / "runs" / "run-arnold"
    assert rc == 0
    assert read_current_run("demo") == "run-arnold"
    assert (run_root / "lease.json").is_file()
    assert (run_root / "events.jsonl").is_file()
    assert json.loads((run_root / "arnold_run.json").read_text())["workflow_id"] == (
        "we.refine_image"
    )
    _assert_no_execution_or_cursor_writes(calls)
    assert calls[-1] == "checkpoint"


def test_arnold_start_rolls_back_run_dir_and_pointer_on_post_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_path / "projects"))
    create_project("demo")
    _install_fake_pipeline(monkeypatch, checkpoint_error=RuntimeError("boom"))
    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")

    rc = cli.cmd_start(["we.refine_image", "--project", "demo", "--name", "run-fail"])

    assert rc == 1
    assert read_current_run("demo") is None
    assert not (tmp_path / "projects" / "demo" / "runs" / "run-fail").exists()


def _seed_active_arnold_run(tmp_path: Path) -> Path:
    create_project("demo")
    project_root = tmp_path / "projects" / "demo"
    run_root = project_root / "runs" / "run-arnold"
    run_root.mkdir(parents=True)
    (project_root / "current_run.json").write_text(
        json.dumps({"run_id": "run-arnold"}),
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
                        "kind": "human_feedback",
                        "ts": "2026-06-13T03:44:00Z",
                        "hash": "sha256:222",
                        "stage_id": "review",
                        "action": "reject",
                        "notes": "too soft",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (run_root / "arnold_run.json").write_text(
        json.dumps(
            {
                "engine": "arnold",
                "workflow_id": "we.refine_image",
                "run_id": "run-arnold",
            }
        ),
        encoding="utf-8",
    )
    (run_root / "pipeline.json").write_text(
        json.dumps(
            {
                "entry_stage_id": "generate",
                "stages": [
                    {"stage_id": "generate", "label": "Generate", "metadata": {}},
                    {"stage_id": "review", "label": "Review", "metadata": {}},
                    {"stage_id": "halt", "label": "Halt", "metadata": {}},
                ],
                "edges": [
                    {"source": "generate", "target": "review", "label": "next"},
                    {"source": "review", "target": "halt", "label": "approve"},
                    {"source": "review", "target": "generate", "label": "reject"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return run_root


def _assert_no_execution_or_cursor_writes(calls: list[str]) -> None:
    assert "advance" not in calls
    assert "resume" not in calls
    assert "persist_resume_cursor" not in calls


def test_arnold_next_renders_projection_without_execution_or_state_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_path / "projects"))
    run_root = _seed_active_arnold_run(tmp_path)
    calls = _install_fake_pipeline(monkeypatch, cursor_stage="review")
    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")

    before_files = {
        path.name: path.read_bytes()
        for path in (
            tmp_path / "projects" / "demo" / "current_run.json",
            run_root / "lease.json",
            run_root / "events.jsonl",
            run_root / "arnold_run.json",
        )
    }

    rc = cli.cmd_next(["--project", "demo"])

    stdout = capsys.readouterr().out
    assert rc == 0
    assert "Arnold workflow we.refine_image" in stdout
    assert "stage: Review (review)" in stdout
    assert "ready for acknowledgement:" in stdout
    _assert_no_execution_or_cursor_writes(calls)
    assert calls == ["read_resume_cursor", "read_resume_cursor", "read_resume_cursor"]
    for path in (
        tmp_path / "projects" / "demo" / "current_run.json",
        run_root / "lease.json",
        run_root / "events.jsonl",
        run_root / "arnold_run.json",
    ):
        assert path.read_bytes() == before_files[path.name]


def test_arnold_ack_normalizes_payload_resumes_advances_once_and_persists_cursor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_path / "projects"))
    run_root = _seed_active_arnold_run(tmp_path)
    resume_cursors: list[Any] = []
    persisted_cursors: list[Any] = []
    calls = _install_fake_pipeline(
        monkeypatch,
        cursor_stage="review",
        resume_cursors=resume_cursors,
        persisted_cursors=persisted_cursors,
    )
    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")

    rc = cli.cmd_ack(
        [
            "--project",
            "demo",
            "--stage",
            "review",
            "--decision",
            "reject",
            "--notes",
            "make it sharper",
            "--state-patch",
            '{"prompt":"sharper"}',
            "--produces-artifact",
            "candidate.png",
            "--produces-input",
            "threshold=ok",
        ]
    )

    stdout = capsys.readouterr().out
    assert rc == 0
    assert "acknowledged Arnold stage" in stdout
    assert calls.count("advance") == 1
    assert calls.count("resume") == 1
    assert calls.count("checkpoint") == 1
    assert calls.count("persist_resume_cursor") == 1
    assert resume_cursors == persisted_cursors
    cursor_ref = resume_cursors[0]
    cursor = cursor_ref.cursor
    assert cursor["stage"] == "generate"
    assert cursor["previous_stage"] == "review"
    assert cursor["human_input"] == {
        "decision": {
            "action": "reject",
            "notes": "make it sharper",
            "state_patch": {"prompt": "sharper"},
        },
        "produces_reverify": {
            "artifacts": ["candidate.png"],
            "inputs": {"threshold": "ok"},
        },
    }
    assert cursor["ctx"].inputs["human_input"] == cursor["human_input"]
    assert json.loads((run_root / "state.json").read_text()) == {"prompt": "sharper"}
    events = [
        json.loads(line)
        for line in (run_root / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events[-1]["kind"] == "human_feedback"
    assert events[-1]["action"] == "reject"
    assert events[-1]["next_stage_id"] == "generate"


def test_arnold_ack_accepts_composite_payload_and_approve_routes_to_halt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_path / "projects"))
    run_root = _seed_active_arnold_run(tmp_path)
    resume_cursors: list[Any] = []
    _install_fake_pipeline(monkeypatch, cursor_stage="review", resume_cursors=resume_cursors)
    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")

    rc = cli.cmd_ack(
        [
            "--project",
            "demo",
            "--payload",
            json.dumps(
                {
                    "decision": {
                        "action": "approve",
                        "notes": "ship it",
                        "state_patch": {"approved": True},
                    },
                    "produces_reverify": {"artifacts": [], "inputs": {"manual": True}},
                }
            ),
        ]
    )

    assert rc == 0
    assert resume_cursors[0].cursor["stage"] == "halt"
    record = json.loads((run_root / "arnold_run.json").read_text())
    assert record["status"] == "completed"
    assert record["last_ack"]["decision"]["action"] == "approve"


def test_arnold_ack_rejects_malformed_payload_before_driver_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_path / "projects"))
    _seed_active_arnold_run(tmp_path)
    calls = _install_fake_pipeline(monkeypatch, cursor_stage="review")
    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")

    rc = cli.cmd_ack(["--project", "demo", "--payload", '{"decision":{"action":"maybe"}}'])

    stderr = capsys.readouterr().err
    assert rc == 2
    assert "invalid Arnold ack payload" in stderr
    assert "advance" not in calls
    assert "resume" not in calls
    assert "persist_resume_cursor" not in calls


def test_arnold_status_json_renders_projection_without_execution_or_state_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_path / "projects"))
    run_root = _seed_active_arnold_run(tmp_path)
    calls = _install_fake_pipeline(monkeypatch, cursor_stage="review")
    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")

    before_files = {
        path.name: path.read_bytes()
        for path in (
            tmp_path / "projects" / "demo" / "current_run.json",
            run_root / "lease.json",
            run_root / "events.jsonl",
            run_root / "arnold_run.json",
        )
    }

    rc = cli.cmd_status(["--project", "demo", "--json"])

    stdout = capsys.readouterr().out
    assert rc == 0
    assert json.loads(stdout) == {
        "action": "ack",
        "blocked": False,
        "command": (
            "astrid ack --engine arnold --project demo --stage review "
            "--decision approve|reject --notes <notes>"
        ),
        "project": "demo",
        "reason": None,
        "run_id": "run-arnold",
        "schema_version": 1,
        "state": "ready",
        "step": "review",
    }
    _assert_no_execution_or_cursor_writes(calls)
    assert calls == ["read_resume_cursor", "read_resume_cursor", "read_resume_cursor"]
    for path in (
        tmp_path / "projects" / "demo" / "current_run.json",
        run_root / "lease.json",
        run_root / "events.jsonl",
        run_root / "arnold_run.json",
    ):
        assert path.read_bytes() == before_files[path.name]


def test_we1_acceptance_rejects_regenerates_and_approves_with_distinct_iterations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from astrid.core.task.events import verify_chain

    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_path / "projects"))
    create_project("demo")
    resume_cursors: list[Any] = []
    persisted_cursors: list[Any] = []
    _install_fake_pipeline(
        monkeypatch,
        resume_cursors=resume_cursors,
        persisted_cursors=persisted_cursors,
        dynamic_cursor_progression=True,
    )
    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")

    assert (
        cli.cmd_start(
            [
                "we.refine_image",
                "--project",
                "demo",
                "--name",
                "run-we1",
                "--state",
                '{"prompt":"soft portrait"}',
            ]
        )
        == 0
    )

    assert cli.cmd_next(["--project", "demo"]) == 0
    first_render = capsys.readouterr().out
    assert "stage: Review (review)" in first_render
    assert "feedback ledger:\n  (no feedback yet)" in first_render

    assert (
        cli.cmd_ack(
            [
                "--project",
                "demo",
                "--stage",
                "review",
                "--decision",
                "reject",
                "--notes",
                "push contrast",
                "--state-patch",
                '{"prompt":"high contrast portrait"}',
                "--produces-artifact",
                "candidate-v1.png",
                "--produces-input",
                "grader=simulated",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert cli.cmd_next(["--project", "demo"]) == 0
    second_render = capsys.readouterr().out
    assert "stage: Review (review)" in second_render
    assert "push contrast" in second_render

    assert (
        cli.cmd_ack(
            [
                "--project",
                "demo",
                "--stage",
                "review",
                "--payload",
                json.dumps(
                    {
                        "decision": {
                            "action": "approve",
                            "notes": "iteration two works",
                            "state_patch": {"approved": True},
                        },
                        "produces_reverify": {
                            "artifacts": ["candidate-v2.png"],
                            "inputs": {"grader": "simulated"},
                        },
                    }
                ),
            ]
        )
        == 0
    )

    run_root = tmp_path / "projects" / "demo" / "runs" / "run-we1"
    final_record = json.loads((run_root / "arnold_run.json").read_text(encoding="utf-8"))
    state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (run_root / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert final_record["status"] == "completed"
    assert state == {"prompt": "high contrast portrait", "approved": True}
    assert [event["action"] for event in events if event["kind"] == "human_feedback"] == [
        "reject",
        "approve",
    ]
    assert events[-2]["notes"] == "push contrast"
    assert events[-1]["notes"] == "iteration two works"
    assert events[-1]["hash"] != events[-2]["hash"]
    assert verify_chain(run_root / "events.jsonl") == (True, len(events) - 1, None)

    assert resume_cursors[0].cursor["human_input"]["produces_reverify"] == {
        "artifacts": ["candidate-v1.png"],
        "inputs": {"grader": "simulated"},
    }
    assert resume_cursors[1].cursor["human_input"]["produces_reverify"] == {
        "artifacts": ["candidate-v2.png"],
        "inputs": {"grader": "simulated"},
    }
    assert persisted_cursors[0].cursor["stage"] == "review"
    assert persisted_cursors[0].cursor["iteration"] == 2
    assert persisted_cursors[0].cursor["artifact"] == "candidate-v2.png"
    assert persisted_cursors[1].cursor["stage"] == "halt"
