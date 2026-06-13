from __future__ import annotations

import importlib
import json
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
from astrid.core.integrations.arnold.session.state import ArtifactRef, StateRef, write_state_file
from astrid.core.project.current_run import write_current_run
from astrid.core.session.lease import write_lease_init
from astrid.core.task.events import (
    EVENTS_FILENAME,
    ZERO_HASH,
    append_event_locked,
    make_plan_initialized_event,
    read_events,
)
from astrid.core.task.plan import Step, TaskPlan
from astrid.core.task.plan.verbs import _make_plan_mutated_event
from tests.core.integrations.test_arnold_session_driver import (
    _FakeDriver,
    _ResumeCursorRef,
    _WriterContext,
    _clear_arnold_modules,
    _install_fake_pipeline,
)


@pytest.fixture(autouse=True)
def _clean_modules_fixture() -> None:
    _clear_arnold_modules()
    yield
    _clear_arnold_modules()


def _import_driver_module():
    return importlib.import_module("astrid.core.integrations.arnold.session.driver")


def _plan_hash(plan: TaskPlan) -> str:
    from astrid.core.task.events import canonical_event_json
    import hashlib

    return f"sha256:{hashlib.sha256(canonical_event_json(plan.to_dict()).encode('utf-8')).hexdigest()}"


def _initial_pipeline_manifest() -> dict[str, Any]:
    return {
        "entry_stage_id": "review",
        "stages": [
            {
                "stage_id": "review",
                "label": "review",
                "metadata": {"segment_id": "seg-001", "plan_step_path": ["review"]},
            },
            {"stage_id": "halt", "label": "Halt", "metadata": {"stage_id": "halt", "terminal": True}},
        ],
        "edges": [{"source": "review", "target": "halt", "label": "next", "source_port": None, "target_port": None, "logical_type": None, "artifact_type": None, "metadata": {}}],
    }


def _base_plan(*, include_draft: bool = False) -> TaskPlan:
    steps: list[Step] = [
        Step(id="review", adapter="manual", command="ack --project demo --step review"),
    ]
    if include_draft:
        steps.append(
            Step(
                id="draft",
                adapter="local",
                command="echo draft",
            )
        )
    return TaskPlan(plan_id="plan-1", version=2, steps=tuple(steps))


def _make_local_step_payload(step_id: str, *, command: str, version: int = 1) -> dict[str, Any]:
    return {
        "id": step_id,
        "adapter": "local",
        "version": version,
        "command": command,
    }


def _setup_session_run(
    tmp_path: Path,
    *,
    plan: TaskPlan,
    project: str = "demo",
    artifacts: tuple[ArtifactRef, ...] = (),
) -> tuple[Path, dict[str, Any]]:
    run_id = "run-session"
    projects_root = tmp_path / "projects"
    run_root = projects_root / project / "runs" / run_id
    run_root.mkdir(parents=True)
    write_current_run(project, run_id, root=projects_root)
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
                    artifacts=artifacts,
                    pipeline_ref="pipeline.json",
                    pipeline_hash="sha256:initial-pipeline",
                    event_lineage=EventLineageHashes(segment_start_hash=str(started["hash"])),
                ),
            ),
        ),
    )
    initial_pipeline = _initial_pipeline_manifest()
    write_json_atomic(run_root / "pipeline.json", initial_pipeline)
    return run_root, initial_pipeline


def _append_mutation(run_root: Path, diff: dict[str, Any]) -> None:
    events = read_events(run_root / EVENTS_FILENAME)
    append_event_locked(
        run_root,
        _make_plan_mutated_event("agent:test", 0, diff),
        expected_writer_epoch=0,
        expected_prev_hash=str(events[-1]["hash"]),
    )


def _load_projection(run_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    events = read_events(run_root / EVENTS_FILENAME)
    manifest = json.loads((run_root / "session-manifest.json").read_text(encoding="utf-8"))
    run_record = json.loads((run_root / ARNOLD_RUN_FILENAME).read_text(encoding="utf-8"))
    pipeline = json.loads((run_root / "pipeline.json").read_text(encoding="utf-8"))
    return events, manifest, run_record, pipeline


def test_add_mutation_freezes_current_segment_and_launches_distinct_successor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cursor_store: dict[str, Any] = {}
    _install_fake_pipeline(monkeypatch, cursor_store)
    prior_artifact = ArtifactRef(
        path="artifacts/review.json",
        sha256="sha256:artifact-review",
        label="review-output",
        source_step_path=("review",),
    )
    run_root, initial_pipeline = _setup_session_run(
        tmp_path,
        plan=_base_plan(),
        artifacts=(prior_artifact,),
    )
    _append_mutation(
        run_root,
        {
            "op": "add",
            "after": "review",
            "step": _make_local_step_payload("ship", command="echo ship"),
        },
    )
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
        human_input={"plan_mutation": {"op": "add"}},
        resume_cursor=cursor,
        driver=fake_driver,
        writer_context_factory=lambda *_args, **_kwargs: writer,
    )

    events, manifest, run_record, pipeline = _load_projection(run_root)
    assert result.from_segment_id == "seg-001"
    assert result.to_segment_id == "seg-002"
    assert run_record["current_segment"] == "seg-002"
    assert [segment["status"] for segment in manifest["segments"]] == ["frozen", "running"]
    assert manifest["segments"][0]["artifacts"] == [prior_artifact.to_dict()]
    assert pipeline != initial_pipeline
    assert [stage["stage_id"] for stage in pipeline["stages"]] == ["review", "ship", "halt"]
    assert pipeline["edges"][-1] == {"source": "ship", "target": "halt", "label": "next", "source_port": None, "target_port": None, "logical_type": None, "artifact_type": None, "metadata": {}}
    assert pipeline["stages"][-1]["metadata"]["terminal"] is True
    assert [event["kind"] for event in events] == ["plan_initialized", "plan_mutated", "segment_boundary"]
    assert [call[0] for call in fake_driver.calls] == ["advance", "checkpoint"]


@pytest.mark.parametrize(
    ("op", "diff", "expected_stage_ids", "expected_review_command", "expected_draft_version"),
    [
        (
            "add",
            {
                "op": "add",
                "after": "draft",
                "step": _make_local_step_payload("publish", command="echo publish"),
            },
            ["review", "draft", "publish", "halt"],
            "ack --project demo --step review",
            1,
        ),
        (
            "edit",
            {
                "op": "edit",
                "path": "review",
                "fields": {"command": "ack --project demo --step review --edited"},
            },
            ["review", "draft", "halt"],
            "ack --project demo --step review --edited",
            1,
        ),
        (
            "remove",
            {"op": "remove", "path": "draft"},
            ["review", "halt"],
            "ack --project demo --step review",
            None,
        ),
        (
            "supersede",
            {
                "op": "supersede",
                "path": "draft",
                "to_version": 2,
                "scope": "all",
                "step": _make_local_step_payload("draft", command="echo draft v2", version=2),
            },
            ["review", "draft", "halt"],
            "ack --project demo --step review",
            2,
        ),
    ],
)
def test_supported_mutation_verbs_author_successor_segments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    op: str,
    diff: dict[str, Any],
    expected_stage_ids: list[str],
    expected_review_command: str,
    expected_draft_version: int | None,
) -> None:
    cursor_store: dict[str, Any] = {}
    _install_fake_pipeline(monkeypatch, cursor_store)
    run_root, initial_pipeline = _setup_session_run(tmp_path, plan=_base_plan(include_draft=True))
    _append_mutation(run_root, diff)
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
        human_input={"plan_mutation": {"op": op}},
        resume_cursor=cursor,
        driver=fake_driver,
        writer_context_factory=lambda *_args, **_kwargs: writer,
    )

    events, manifest, run_record, pipeline = _load_projection(run_root)
    assert result.to_segment_id == "seg-002"
    assert run_record["current_segment"] == "seg-002"
    assert [segment["status"] for segment in manifest["segments"]] == ["frozen", "running"]
    assert pipeline != initial_pipeline
    assert [stage["stage_id"] for stage in pipeline["stages"]] == expected_stage_ids
    assert pipeline["stages"][0]["metadata"]["command"] == expected_review_command
    if expected_draft_version is None:
        assert "draft" not in [stage["stage_id"] for stage in pipeline["stages"]]
    else:
        draft_stage = next(stage for stage in pipeline["stages"] if stage["stage_id"] == "draft")
        assert draft_stage["metadata"]["step_version"] == expected_draft_version
    assert [event["kind"] for event in events] == ["plan_initialized", "plan_mutated", "segment_boundary"]
    assert [call[0] for call in fake_driver.calls] == ["advance", "checkpoint"]


def test_repeat_for_each_mutation_fails_closed_before_boundary_or_pipeline_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cursor_store: dict[str, Any] = {}
    _install_fake_pipeline(monkeypatch, cursor_store)
    run_root, initial_pipeline = _setup_session_run(tmp_path, plan=_base_plan())
    _append_mutation(
        run_root,
        {
            "op": "add",
            "after": "review",
            "step": {
                "id": "fanout",
                "adapter": "local",
                "command": "echo fanout",
                "repeat": {"for_each": {"items": ["a", "b"]}},
            },
        },
    )
    cursor = _ResumeCursorRef(
        plugin_id="astrid.arnold.host",
        run_id="run-session",
        cursor={"stage": "review"},
    )
    fake_driver = _FakeDriver()
    writer = _WriterContext(run_root, epoch=0)
    module = _import_driver_module()

    with pytest.raises(RuntimeError, match="repeat.for_each is not supported"):
        module.resume_session_run(
            "demo",
            run_id="run-session",
            root=tmp_path / "projects",
            human_input={"plan_mutation": {"op": "add"}},
            resume_cursor=cursor,
            driver=fake_driver,
            writer_context_factory=lambda *_args, **_kwargs: writer,
        )

    events, manifest, run_record, pipeline = _load_projection(run_root)
    assert [event["kind"] for event in events] == ["plan_initialized", "plan_mutated"]
    assert manifest["current_segment_id"] == "seg-001"
    assert [segment["status"] for segment in manifest["segments"]] == ["running"]
    assert run_record["current_segment"] == "seg-001"
    assert pipeline == initial_pipeline
    assert writer.appended == []
    assert fake_driver.calls == []


@pytest.mark.parametrize(
    ("persist_impl", "read_impl", "message"),
    [
        (
            lambda *_args, **_kwargs: None,
            lambda *_args, **_kwargs: None,
            "persisted resume cursor could not be read back",
        ),
        (
            lambda *_args, **_kwargs: None,
            lambda *_args, **_kwargs: _ResumeCursorRef(
                plugin_id="astrid.arnold.host",
                run_id="run-session",
                cursor={},
            ),
            "resume cursor payload must include non-empty stage",
        ),
    ],
)
def test_cursor_persistence_failures_abort_before_commit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    persist_impl: Any,
    read_impl: Any,
    message: str,
) -> None:
    cursor_store: dict[str, Any] = {}
    _install_fake_pipeline(monkeypatch, cursor_store)
    run_root, initial_pipeline = _setup_session_run(tmp_path, plan=_base_plan())
    _append_mutation(
        run_root,
        {
            "op": "add",
            "after": "review",
            "step": _make_local_step_payload("ship", command="echo ship"),
        },
    )
    cursor = _ResumeCursorRef(
        plugin_id="astrid.arnold.host",
        run_id="run-session",
        cursor={"stage": "review"},
    )
    fake_driver = _FakeDriver()
    writer = _WriterContext(run_root, epoch=0)
    module = _import_driver_module()
    compat_module = importlib.import_module("astrid.core.integrations.arnold.host.compat")
    monkeypatch.setattr(compat_module, "persist_resume_cursor", persist_impl)
    monkeypatch.setattr(compat_module, "read_resume_cursor", read_impl)

    with pytest.raises(module.SessionDriverError, match=message):
        module.resume_session_run(
            "demo",
            run_id="run-session",
            root=tmp_path / "projects",
            human_input={"plan_mutation": {"op": "add"}},
            resume_cursor=cursor,
            driver=fake_driver,
            writer_context_factory=lambda *_args, **_kwargs: writer,
        )

    events, manifest, run_record, pipeline = _load_projection(run_root)
    assert [event["kind"] for event in events] == ["plan_initialized", "plan_mutated"]
    assert manifest["current_segment_id"] == "seg-001"
    assert [segment["status"] for segment in manifest["segments"]] == ["running"]
    assert run_record["current_segment"] == "seg-001"
    assert pipeline == initial_pipeline
    assert writer.appended == []
    assert fake_driver.calls == []
