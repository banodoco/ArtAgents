from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from _lifecycle_fixtures import bind_writer_session, setup_packs_and_compile  # noqa: E402

from astrid.core.project.project import create_project
from astrid.core.task import gate as task_gate
from astrid.core.task.events import read_events
from astrid.core.task.plan import (
    Check,
    ProducesEntry,
    _validate_plan,
    step_dir_for_path,
)
from astrid.core.task.plan_verbs import apply_mutations
from astrid.core.task.lifecycle import cmd_start
from astrid.core.timeline.crud import create_timeline


_BODY_CODE = """from astrid.orchestrate import orchestrator, code
@orchestrator("demo.app")
def app(): return [code("step_a", argv=["echo", "x"])]
"""


def test_start_event_zero_is_plan_initialized_with_initial_plan(
    tmp_path: Path,
) -> None:
    packs, projects = setup_packs_and_compile(
        tmp_path, "demo", "app", _BODY_CODE, "demo.app"
    )
    create_project("p", root=projects)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")

    assert (
        cmd_start(
            ["demo.app", "--project", "p", "--name", "r-plan-init"],
            packs_root=packs,
            projects_root=projects,
        )
        == 0
    )

    events = read_events(projects / "p" / "runs" / "r-plan-init" / "events.jsonl")
    assert events[0]["kind"] == "plan_initialized"
    assert events[0]["run_id"] == "r-plan-init"
    assert events[0]["plan"]["version"] == 2
    assert "plan_hash" in events[0]
    assert events[1]["kind"] == "run_started"


def test_projection_replay_uses_plan_initialized_as_source_of_truth() -> None:
    stale_cache = _validate_plan(
        {
            "plan_id": "stale",
            "version": 2,
            "steps": [{"id": "stale", "adapter": "local", "command": "echo stale"}],
        }
    )
    events = [
        {
            "kind": "plan_initialized",
            "run_id": "r1",
            "plan_hash": "sha256:" + "0" * 64,
            "plan": {
                "plan_id": "fresh",
                "version": 2,
                "steps": [
                    {"id": "first", "adapter": "local", "command": "echo first"}
                ],
            },
        },
        {
            "kind": "plan_mutated",
            "diff": {
                "op": "add",
                "step": {"id": "second", "adapter": "local", "command": "echo second"},
            },
        },
    ]

    projection = apply_mutations(stale_cache, events)

    assert projection.plan_id == "fresh"
    assert [step.id for step in projection.steps] == ["first", "second"]


def test_repeat_until_accepts_descendant_produces_expression() -> None:
    plan = _validate_plan(
        {
            "plan_id": "hype-editor-loop",
            "version": 2,
            "steps": [
                {
                    "id": "review_loop",
                    "adapter": "local",
                    "repeat": {
                        "until": "editor_review.produces.verdict.status == 'approved'",
                        "max_iterations": 3,
                        "on_exhaust": "fail",
                    },
                    "re_export": {
                        "verdict": "editor_review.produces.verdict",
                    },
                    "children": [
                        {
                            "id": "render",
                            "adapter": "local",
                            "command": "echo render",
                            "produces": {
                                "video": {
                                    "path": "hype.mp4",
                                    "check": {
                                        "check_id": "file_nonempty",
                                        "params": {},
                                        "sentinel": False,
                                    },
                                }
                            },
                        },
                        {
                            "id": "editor_review",
                            "adapter": "manual",
                            "command": "editor-review",
                            "produces": {
                                "verdict": {
                                    "path": "editor_review.json",
                                    "check": {
                                        "check_id": "json_file",
                                        "params": {},
                                        "sentinel": False,
                                    },
                                }
                            },
                        },
                    ],
                }
            ],
        }
    )

    assert plan.steps[0].repeat is not None
    assert (
        plan.steps[0].repeat.condition
        == "editor_review.produces.verdict.status == 'approved'"
    )


def test_for_each_autoclose_counts_unique_items_only(tmp_path: Path) -> None:
    project_root = tmp_path / "demo"
    run_dir = project_root / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (project_root / "plan.json").write_text(
        json.dumps(
            {
                "plan_id": "p",
                "version": 2,
                "steps": [
                    {
                        "id": "host",
                        "adapter": "manual",
                        "command": "review",
                        "repeat": {"for_each": {"items": ["alpha", "beta"]}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    events_path = run_dir / "events.jsonl"
    events_path.write_text(
        "\n".join(
            json.dumps(event)
            for event in [
                {
                    "kind": "for_each_expanded",
                    "plan_step_path": ["host"],
                    "item_ids": ["alpha", "beta"],
                },
                {
                    "kind": "item_attested",
                    "plan_step_path": ["host"],
                    "item_id": "alpha",
                    "attestor_kind": "agent",
                    "attestor_id": "a1",
                },
                {
                    "kind": "item_attested",
                    "plan_step_path": ["host"],
                    "item_id": "alpha",
                    "attestor_kind": "agent",
                    "attestor_id": "a1",
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    appended: list[dict] = []

    task_gate._maybe_autoclose_for_each_host(
        events_path=events_path,
        path_tuple=("host",),
        project_root=project_root,
        slug="demo",
        run_id="run-1",
        append_fn=appended.append,
    )

    assert appended == []


def test_inline_checks_use_decision_step_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "demo"
    (project_root / "runs" / "run-1").mkdir(parents=True)
    events_path = project_root / "runs" / "run-1" / "events.jsonl"
    events_path.write_text("", encoding="utf-8")
    step_dir_v2 = step_dir_for_path(
        "demo",
        "run-1",
        ("render",),
        step_version=2,
        root=tmp_path,
    )
    (step_dir_v2 / "produces").mkdir(parents=True)
    (step_dir_v2 / "produces" / "out.json").write_text("{}", encoding="utf-8")
    appended: list[dict] = []
    monkeypatch.setattr(task_gate, "_append_via_decision", lambda _d, e: appended.append(e))

    decision = task_gate.GateDecision(
        active=True,
        run_id="run-1",
        plan_step_id="render",
        plan_step_path=("render",),
        events_path=events_path,
        slug="demo",
        project_root=project_root,
        step_version=2,
        dispatch_event_hash="sha256:dispatch-v2",
    )
    produces = (
        ProducesEntry(
            name="out",
            path="out.json",
            check=Check(check_id="file_nonempty", params={}, sentinel=False),
        ),
    )

    assert task_gate._run_inline_checks(decision, produces) is True
    assert [event["kind"] for event in appended] == ["produces_check_passed"]
    assert appended[0]["plan_step_path"] == ["render"]
    assert appended[0]["step_version"] == 2
    assert appended[0]["dispatch_event_hash"] == "sha256:dispatch-v2"


def test_cursor_ignores_superseded_v1_completion_for_v2_step(tmp_path: Path) -> None:
    plan = _validate_plan(
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {
                    "id": "render",
                    "adapter": "local",
                    "command": "echo v2",
                    "version": 2,
                }
            ],
        }
    )
    events = [
        {
            "kind": "step_dispatched",
            "plan_step_path": ["render"],
            "command": "echo v1",
            "step_version": 1,
            "hash": "sha256:v1-dispatch",
        },
        {
            "kind": "step_completed",
            "plan_step_path": ["render"],
            "returncode": 0,
            "step_version": 1,
            "dispatch_event_hash": "sha256:v1-dispatch",
        },
    ]

    peek = task_gate.peek_current_step(
        plan,
        events,
        "demo",
        project_root=tmp_path / "demo",
        run_id="run-1",
    )

    assert peek.exhausted is False
    assert peek.path_tuple == ("render",)
    assert peek.step.version == 2


def test_record_dispatch_complete_emits_version_and_dispatch_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "demo"
    run_dir = project_root / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    events_path = run_dir / "events.jsonl"
    events_path.write_text("", encoding="utf-8")
    appended: list[dict] = []
    monkeypatch.setattr(task_gate, "_load_step_for_decision", lambda _d: None)
    monkeypatch.setattr(task_gate, "_append_via_decision", lambda _d, e: appended.append(e))

    decision = task_gate.GateDecision(
        active=True,
        run_id="run-1",
        plan_step_id="render",
        plan_step_path=("render",),
        events_path=events_path,
        slug="demo",
        project_root=project_root,
        step_kind="code",
        step_version=2,
        dispatch_event_hash="sha256:dispatch-v2",
    )

    task_gate.record_dispatch_complete(decision, 0)

    assert [event["kind"] for event in appended] == ["step_completed"]
    assert appended[0]["step_version"] == 2
    assert appended[0]["dispatch_event_hash"] == "sha256:dispatch-v2"


def test_gate_completion_path_writes_returncode_sidecar_atomically() -> None:
    source = inspect.getsource(task_gate.record_dispatch_complete)
    assert "write_text_sidecar" in source
    assert "returncode" in source


def test_iteration_feedback_is_written_atomically() -> None:
    source = inspect.getsource(task_gate.write_iteration_feedback)
    assert "write_json_sidecar" in source
    assert ".write_text(" not in source


def test_lifecycle_feedback_display_uses_cursor_step_version() -> None:
    from astrid.core.task import lifecycle

    source = inspect.getsource(lifecycle.cmd_next)

    assert "step_version=peek.step.version" in source
    assert "step_version=1" not in source
