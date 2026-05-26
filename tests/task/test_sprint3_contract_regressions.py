from __future__ import annotations

import ast
import io
import inspect
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from _lifecycle_fixtures import bind_writer_session, setup_packs_and_compile, setup_run  # noqa: E402

from astrid.core.project.project import create_project
from astrid.core.task.active_run import write_active_run
from astrid.core.task import gate as task_gate
from astrid.core.task.events import (
    append_event,
    make_for_each_expanded_event,
    make_item_attested_event,
    make_item_started_event,
    make_iteration_failed_event,
    make_produces_check_failed_event,
    read_events,
)
from astrid.core.task.plan import (
    Check,
    ProducesEntry,
    compute_plan_hash,
    _validate_plan,
    step_dir_for_path,
)
from astrid.core.task.plan_verbs import apply_mutations
from astrid.core.task.lifecycle import cmd_ack, cmd_next, cmd_start, cmd_status
from astrid.core.timeline.crud import create_timeline


_BODY_CODE = """from astrid.orchestrate import orchestrator, code
@orchestrator("demo.app")
def app(): return [code("step_a", argv=["echo", "x"])]
"""

_BODY_FOREACH_ATTESTED_PRODUCES = '''from astrid.orchestrate import orchestrator, attested, repeat_for_each
from astrid.verify import json_file
@orchestrator("demo.fe_produces")
def main(): return [attested("review_each", command="review.sh", instructions="check", ack="human",
    repeat=repeat_for_each(items=["a", "b"]), produces={"out": json_file()})]
'''


def _capture_call(fn, argv: list[str], *, projects_root: Path) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = fn(argv, projects_root=projects_root)
    return rc, out.getvalue(), err.getvalue()


def _write_project_plan(projects_root: Path, plan: dict, *, slug: str = "demo", run_id: str = "run-1") -> Path:
    create_project(slug, root=projects_root, exist_ok=True)
    project_root = projects_root / slug
    plan_path = project_root / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    bind_writer_session(projects_root, slug, run_id=run_id)
    write_active_run(slug, run_id=run_id, plan_hash=compute_plan_hash(plan_path), root=projects_root)
    return project_root / "runs" / run_id / "events.jsonl"


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

    result = task_gate._run_inline_checks(decision, produces, append_fn=appended.append)
    assert result.ok is True
    assert [event["kind"] for event in appended] == ["produces_check_passed"]
    assert appended[0]["plan_step_path"] == ["render"]
    assert appended[0]["step_version"] == 2
    assert appended[0]["dispatch_event_hash"] == "sha256:dispatch-v2"


def test_gate_exports_inline_check_result_and_finalize_step_contract() -> None:
    assert hasattr(task_gate, "InlineCheckResult")
    result = task_gate.InlineCheckResult(ok=False, name="out", reason="missing")
    assert result.ok is False
    assert result.name == "out"
    assert result.reason == "missing"

    sig = inspect.signature(task_gate._finalize_step)
    assert list(sig.parameters) == [
        "decision",
        "terminal_event",
        "append_mode",
        "inline_check_result",
        "cost",
    ]
    assert sig.parameters["append_mode"].default is inspect.Signature.empty
    assert sig.parameters["inline_check_result"].default is None
    assert sig.parameters["cost"].default is None


def test_run_inline_checks_accepts_injected_append_and_returns_result() -> None:
    sig = inspect.signature(task_gate._run_inline_checks)
    assert list(sig.parameters) == ["decision", "produces", "append_fn"]

    project_root = Path("/tmp/project")
    decision = task_gate.GateDecision(
        active=True,
        run_id="run-1",
        plan_step_id="render",
        plan_step_path=("render",),
        events_path=project_root / "runs" / "run-1" / "events.jsonl",
        slug="demo",
        project_root=project_root,
    )
    appended: list[dict] = []
    result = task_gate._run_inline_checks(decision, (), append_fn=appended.append)

    assert isinstance(result, task_gate.InlineCheckResult)
    assert result.ok is True
    assert result.name is None
    assert result.reason is None
    assert appended == []


def test_gate_source_centralizes_six_terminal_event_constructors() -> None:
    source = inspect.getsource(task_gate)
    tree = ast.parse(source)
    terminal_names = {
        "make_step_completed_event",
        "make_step_failed_event",
        "make_step_attested_event",
        "make_item_completed_event",
        "make_item_attested_event",
        "make_step_awaiting_fetch_event",
    }
    calls_by_function: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        seen: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                if child.func.id in terminal_names:
                    seen.add(child.func.id)
        if seen:
            calls_by_function[node.name] = seen

    assert calls_by_function == {"_finalize_step": terminal_names}


def test_gate_command_routes_terminal_appenders_through_gate_append() -> None:
    source = inspect.getsource(task_gate.gate_command)
    tree = ast.parse(source)
    terminal_dispatchers = {"_dispatch_code", "_dispatch_attested"}
    append_keywords: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in terminal_dispatchers:
            continue
        for keyword in node.keywords:
            if keyword.arg == "append_fn":
                assert isinstance(keyword.value, ast.Name)
                append_keywords[node.func.id] = keyword.value.id

    assert append_keywords == {
        "_dispatch_code": "_gate_append",
        "_dispatch_attested": "_gate_append",
    }


def test_dispatch_attested_has_no_tail_scan_and_uses_inline_result() -> None:
    source = inspect.getsource(task_gate._dispatch_attested)
    tree = ast.parse(source)

    forbidden_calls = {"read_events"}
    seen_forbidden = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in forbidden_calls
    }
    assert seen_forbidden == set()
    assert "inline_check_result" in source
    assert "InlineCheckResult" in source


def test_finalize_skips_parent_completion_after_inline_check_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
                        "adapter": "local",
                        "command": "echo x",
                        "repeat": {"for_each": {"items": ["a"]}},
                        "produces": {
                            "out": {
                                "path": "out.json",
                                "check": {
                                    "check_id": "json_file",
                                    "params": {},
                                    "sentinel": False,
                                },
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    events_path = run_dir / "events.jsonl"
    decision = task_gate.GateDecision(
        active=True,
        run_id="run-1",
        plan_step_id="host",
        plan_step_path=("host",),
        events_path=events_path,
        slug="demo",
        project_root=project_root,
        item_id="a",
        adapter="local",
        step_version=1,
    )
    appended: list[dict] = []
    monkeypatch.setattr(task_gate, "_append_via_decision", lambda _d, e: appended.append(e))

    terminal = task_gate.make_item_completed_event(("host",), "a", 7, step_version=1)
    failed = task_gate.InlineCheckResult(ok=False, name="out", reason="missing")
    task_gate._finalize_step(
        decision,
        terminal,
        append_mode="decision",
        inline_check_result=failed,
    )

    assert [event["kind"] for event in appended] == [
        "item_completed",
        "produces_check_failed",
        "cursor_rewind",
    ]
    assert not any(event["kind"] == "step_completed" for event in appended)


def test_finalize_autocomplete_preserves_returncode_cost_and_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
                        "adapter": "local",
                        "command": "echo x",
                        "repeat": {"for_each": {"items": ["a"]}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    events_path = run_dir / "events.jsonl"
    events_path.write_text(
        json.dumps(
            {
                "kind": "for_each_expanded",
                "plan_step_path": ["host"],
                "item_ids": ["a"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    decision = task_gate.GateDecision(
        active=True,
        run_id="run-1",
        plan_step_id="host",
        plan_step_path=("host",),
        events_path=events_path,
        slug="demo",
        project_root=project_root,
        item_id="a",
        adapter="local",
        step_version=1,
    )
    appended: list[dict] = []
    monkeypatch.setattr(task_gate, "_append_via_decision", lambda _d, e: appended.append(e))

    cost = {"amount": 0.25, "currency": "USD", "source": "runpod"}
    terminal = task_gate.make_item_completed_event(("host",), "a", 23, step_version=1)
    task_gate._finalize_step(
        decision,
        terminal,
        append_mode="decision",
        inline_check_result=task_gate.InlineCheckResult(ok=True),
        cost=cost,
    )

    assert [event["kind"] for event in appended] == ["item_completed", "step_completed"]
    host = appended[-1]
    assert host["returncode"] == 23
    assert host["cost"] == cost
    assert host["adapter"] == "local"


def test_for_each_parent_context_builders_do_not_emit_and_preserve_payload(
    tmp_path: Path,
) -> None:
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
                        "adapter": "local",
                        "command": "echo x",
                        "repeat": {"for_each": {"items": ["a"]}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    events_path = run_dir / "events.jsonl"
    events_path.write_text(
        json.dumps(
            {
                "kind": "for_each_expanded",
                "plan_step_path": ["host"],
                "item_ids": ["a"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    autoclose = task_gate._build_autoclose_for_each_host_context(
        events_path=events_path,
        path_tuple=("host",),
        project_root=project_root,
        slug="demo",
        run_id="run-1",
        current_item_id="a",
    )
    assert autoclose is not None
    assert autoclose.terminal_event.kind == "step_attested"
    assert autoclose.terminal_event.payload["attestor_id"] == "gate.autoclose"

    decision = task_gate.GateDecision(
        active=True,
        run_id="run-1",
        plan_step_id="host",
        plan_step_path=("host",),
        events_path=events_path,
        slug="demo",
        project_root=project_root,
        item_id="a",
        adapter="local",
        step_version=1,
    )
    cost = {"amount": 0.25, "currency": "USD", "source": "runpod"}
    autocomplete = task_gate._build_autocomplete_for_each_host_context(
        decision=decision,
        returncode=23,
        cost=cost,
    )
    assert autocomplete is not None
    assert autocomplete.terminal_event.kind == "step_completed"
    assert autocomplete.terminal_event.payload["returncode"] == 23
    assert autocomplete.terminal_event.payload["cost"] == cost
    assert autocomplete.terminal_event.payload["adapter"] == "local"
    assert autocomplete.decision.item_id is None

    events_after = task_gate.read_events(events_path)
    assert [event["kind"] for event in events_after] == ["for_each_expanded"]


def test_derive_cursor_replays_item_terminal_before_inline_failure_marker() -> None:
    plan = _validate_plan(
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {
                    "id": "host",
                    "adapter": "manual",
                    "command": "review",
                    "repeat": {"for_each": {"items": ["a"]}},
                    "produces": {
                        "out": {
                            "path": "out.json",
                            "check": {
                                "check_id": "json_file",
                                "params": {},
                                "sentinel": False,
                            },
                        }
                    },
                }
            ],
        }
    )
    events = [
        {"kind": "for_each_expanded", "plan_step_path": ["host"], "item_ids": ["a"]},
        {"kind": "item_started", "plan_step_path": ["host"], "item_id": "a"},
        {
            "kind": "item_attested",
            "plan_step_path": ["host"],
            "item_id": "a",
            "attestor_kind": "agent",
            "attestor_id": "worker",
        },
        {
            "kind": "produces_check_failed",
            "plan_step_path": ["host"],
            "produces_name": "out",
            "check_id": "json_file",
            "reason": "missing",
        },
        {"kind": "cursor_rewind", "plan_step_path": ["host"], "reason": "retry"},
    ]

    cursor = task_gate.derive_cursor(plan, events, slug="demo")
    top = cursor.frames[-1]
    assert top.path_prefix == ()
    assert top.child_index == 0
    assert top.item_id == "a"
    assert len(cursor.frames) == 2


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


def test_produces_check_failure_surfaces_to_main_for_code_and_attested_leaves(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "demo"
    events_path = project_root / "runs" / "run-1" / "events.jsonl"
    events_path.parent.mkdir(parents=True)
    (project_root / "plan.json").write_text(
        json.dumps(
            {
                "plan_id": "p",
                "version": 2,
                "steps": [
                    {
                        "id": "render",
                        "adapter": "local",
                        "command": "echo render",
                        "produces": {
                            "out": {
                                "path": "out.json",
                                "check": {
                                    "check_id": "json_file",
                                    "params": {},
                                    "sentinel": False,
                                },
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    produces = (
        ProducesEntry(
            name="out",
            path="out.json",
            check=Check(check_id="json_file", params={}, sentinel=False),
        ),
    )

    code_decision = task_gate.GateDecision(
        active=True,
        run_id="run-1",
        plan_step_id="render",
        plan_step_path=("render",),
        events_path=events_path,
        slug="demo",
        project_root=project_root,
        step_kind="code",
        dispatch_event_hash="sha256:dispatch-code",
    )
    code_appended: list[dict] = []
    code_result = task_gate._run_inline_checks(
        code_decision,
        produces,
        append_fn=code_appended.append,
    )

    assert code_result == task_gate.InlineCheckResult(
        ok=False,
        name="out",
        reason=code_result.reason,
    )
    assert code_result.reason
    assert [event["kind"] for event in code_appended] == [
        "produces_check_failed",
        "cursor_rewind",
    ]
    assert code_appended[0]["produces_name"] == "out"
    assert code_appended[1]["dispatch_event_hash"] == "sha256:dispatch-code"

    attested_decision = task_gate.GateDecision(
        active=True,
        run_id="run-1",
        plan_step_id="review_each",
        plan_step_path=("review_each",),
        events_path=events_path,
        slug="demo",
        project_root=project_root,
        step_kind="attested",
        iteration=3,
        item_id="a",
    )
    attested_appended: list[dict] = []
    attested_result = task_gate._run_inline_checks(
        attested_decision,
        produces,
        append_fn=attested_appended.append,
    )

    assert isinstance(attested_result, task_gate.InlineCheckResult)
    assert attested_result.ok is False
    assert attested_result.name == "out"
    assert [event["kind"] for event in attested_appended] == [
        "produces_check_failed",
        "iteration_failed",
    ]
    assert attested_appended[-1]["iteration"] == 3


def test_attested_per_item_inline_check_failure_cmd_ack_exits_2_and_marks_iteration(
    tmp_path: Path,
) -> None:
    _packs, projects = setup_run(
        tmp_path,
        "demo",
        "fe_produces",
        _BODY_FOREACH_ATTESTED_PRODUCES,
        "demo.fe_produces",
        run_id="run-inline",
    )
    os.environ["ASTRID_ACTOR"] = "alice"

    rc, out, err = _capture_call(
        cmd_ack,
        [
            "review_each",
            "--project",
            "p",
            "--decision",
            "approve",
            "--human",
            "alice",
            "--item",
            "a",
        ],
        projects_root=projects,
    )

    assert rc == 2, f"out={out!r} err={err!r}"
    assert "out" in err
    assert "produces check failed" in err
    events = read_events(projects / "p" / "runs" / "run-inline" / "events.jsonl")
    kinds = [event["kind"] for event in events]
    assert "item_attested" in kinds
    assert "produces_check_failed" in kinds
    assert "iteration_failed" in kinds
    failure = next(event for event in events if event["kind"] == "produces_check_failed")
    assert failure["produces_name"] == "out"


def test_lifecycle_next_and_status_surface_cursor_rewind_and_iteration_failed_reasons(
    tmp_path: Path,
) -> None:
    plan = {
        "plan_id": "p",
        "version": 2,
        "steps": [
            {
                "id": "review",
                "requires_ack": True,
                "adapter": "manual",
                "command": "review.sh",
                "instructions": "review",
                "ack": {"kind": "human"},
            }
        ],
    }
    events_path = _write_project_plan(tmp_path, plan)
    append_event(
        events_path,
        make_produces_check_failed_event(
            ("review",),
            "out",
            check_id="json_file",
            reason="missing verdict key",
        ),
    )
    append_event(
        events_path,
        task_gate.make_cursor_rewind_event(
            ("review",),
            reason="produces check failed: out",
        ),
    )

    next_rc, next_out, next_err = _capture_call(
        cmd_next,
        ["--project", "demo"],
        projects_root=tmp_path,
    )
    status_rc, status_out, status_err = _capture_call(
        cmd_status,
        ["--project", "demo"],
        projects_root=tmp_path,
    )

    assert next_rc == 0, next_err
    assert "missing verdict key" in next_out
    assert status_rc == 0, status_err
    assert "missing verdict key" in status_out

    events_path.write_text("", encoding="utf-8")
    append_event(
        events_path,
        make_iteration_failed_event(
            ("review",),
            2,
            reason="repeat.until unresolved: invalid JSON",
        ),
    )

    next_rc, next_out, next_err = _capture_call(
        cmd_next,
        ["--project", "demo"],
        projects_root=tmp_path,
    )
    status_rc, status_out, status_err = _capture_call(
        cmd_status,
        ["--project", "demo"],
        projects_root=tmp_path,
    )

    assert next_rc == 0, next_err
    assert "repeat.until unresolved: invalid JSON" in next_out
    assert status_rc == 0, status_err
    assert "repeat.until unresolved: invalid JSON" in status_out


def test_repeat_until_gate_error_propagates_and_preserves_mutation_order(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "demo"
    events_path = project_root / "runs" / "run-1" / "events.jsonl"
    events_path.parent.mkdir(parents=True)
    plan = _validate_plan(
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {
                    "id": "review",
                    "adapter": "local",
                    "command": "echo review",
                    "produces": {
                        "verdict": {
                            "path": "review.json",
                            "check": {
                                "check_id": "file_nonempty",
                                "params": {},
                                "sentinel": False,
                            },
                        }
                    },
                    "repeat": {
                        "until": 'review.produces.verdict.status == "approved"',
                        "max_iterations": 2,
                        "on_exhaust": "fail",
                    },
                }
            ],
        }
    )
    (project_root / "plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
    iteration_dir = step_dir_for_path(
        "demo",
        "run-1",
        ("review",),
        iteration=1,
        root=tmp_path,
    )
    (iteration_dir / "produces").mkdir(parents=True)
    (iteration_dir / "produces" / "review.json").write_text("{bad json", encoding="utf-8")
    cursor = task_gate.derive_cursor(
        plan,
        [
            {"kind": "iteration_started", "plan_step_path": ["review"], "iteration": 1},
            {
                "kind": "step_completed",
                "plan_step_path": ["review"],
                "returncode": 0,
            },
        ],
        slug="demo",
    )
    parent_before = cursor.frames[-2].child_index
    appended: list[dict] = []

    task_gate._evaluate_exhausted_repeat_until_frame(
        slug="demo",
        cursor=cursor,
        project_root=project_root,
        run_id="run-1",
        append_fn=appended.append,
    )

    assert [event["kind"] for event in appended] == ["iteration_failed"]
    assert "repeat.until unresolved" in appended[0]["reason"]
    assert cursor.frames[-1].child_index == parent_before


def test_repeat_until_typed_errors_propagate_without_mutation(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "demo"
    events_path = project_root / "runs" / "run-1" / "events.jsonl"
    events_path.parent.mkdir(parents=True)
    plan = _validate_plan(
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {
                    "id": "review",
                    "adapter": "local",
                    "command": "echo review",
                    "produces": {
                        "verdict": {
                            "path": "review.json",
                            "check": {
                                "check_id": "file_nonempty",
                                "params": {},
                                "sentinel": False,
                            },
                        }
                    },
                    "repeat": {
                        "until": 'review.produces.verdict.status == "approved"',
                        "max_iterations": 2,
                        "on_exhaust": "fail",
                    },
                }
            ],
        }
    )
    (project_root / "plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
    iteration_dir = step_dir_for_path(
        "demo",
        "run-1",
        ("review",),
        iteration=1,
        root=tmp_path,
    )
    (iteration_dir / "produces").mkdir(parents=True)
    (iteration_dir / "produces" / "review.json").write_text("{}", encoding="utf-8")
    cursor = task_gate.derive_cursor(
        plan,
        [
            {"kind": "iteration_started", "plan_step_path": ["review"], "iteration": 1},
            {
                "kind": "step_completed",
                "plan_step_path": ["review"],
                "returncode": 0,
            },
        ],
        slug="demo",
    )
    parent_before = cursor.frames[-2].child_index
    frame_count_before = len(cursor.frames)
    appended: list[dict] = []

    with pytest.raises(task_gate.TaskRunGateError, match="cannot read JSON field"):
        task_gate._evaluate_exhausted_repeat_until_frame(
            slug="demo",
            cursor=cursor,
            project_root=project_root,
            run_id="run-1",
            append_fn=appended.append,
        )

    assert appended == []
    assert len(cursor.frames) == frame_count_before
    assert cursor.frames[-2].child_index == parent_before


def test_for_each_advances_after_non_abort_explicit_item_reject(tmp_path: Path) -> None:
    plan = {
        "plan_id": "p",
        "version": 2,
        "steps": [
            {
                "id": "review_each",
                "requires_ack": True,
                "adapter": "manual",
                "command": "review.sh",
                "instructions": "review",
                "ack": {"kind": "human"},
                "repeat": {"for_each": {"items": ["a", "b"]}},
            }
        ],
    }
    events_path = _write_project_plan(tmp_path, plan)
    append_event(events_path, make_for_each_expanded_event(("review_each",), ("a", "b")))
    append_event(events_path, make_item_started_event(("review_each",), "a"))
    append_event(
        events_path,
        make_item_attested_event(
            ("review_each",),
            "a",
            attestor_kind="human",
            attestor_id="alice",
        ),
    )

    next_decision = task_gate.gate_command(
        "demo",
        "review.sh --human alice --item a",
        ["review.sh", "--human", "alice", "--item", "a"],
        root=tmp_path,
    )
    assert next_decision.item_id == "b"
    assert not any(event.get("kind") == "item_skipped" for event in read_events(events_path))


def test_for_each_replay_ignores_invalid_and_completed_explicit_item_selection(
    tmp_path: Path,
) -> None:
    plan = _validate_plan(
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {
                    "id": "review_each",
                    "requires_ack": True,
                    "adapter": "manual",
                    "command": "review.sh",
                    "instructions": "review",
                    "ack": {"kind": "human"},
                    "repeat": {"for_each": {"items": ["a", "b"]}},
                }
            ],
        }
    )
    events = [
        {"kind": "for_each_expanded", "plan_step_path": ["review_each"], "item_ids": ["a", "b"]},
        {"kind": "item_started", "plan_step_path": ["review_each"], "item_id": "invalid"},
        {
            "kind": "item_attested",
            "plan_step_path": ["review_each"],
            "item_id": "invalid",
            "attestor_kind": "human",
            "attestor_id": "alice",
        },
        {"kind": "item_started", "plan_step_path": ["review_each"], "item_id": "a"},
        {
            "kind": "item_attested",
            "plan_step_path": ["review_each"],
            "item_id": "a",
            "attestor_kind": "human",
            "attestor_id": "alice",
        },
    ]

    peek = task_gate.peek_current_step(
        plan,
        events,
        "demo",
        project_root=tmp_path / "demo",
        run_id="run-1",
    )

    assert peek.path_tuple == ("review_each",)
    assert peek.item_id == "b"


def test_for_each_explicit_invalid_item_exhausts_when_no_pending_without_progress(
    tmp_path: Path,
) -> None:
    plan = _validate_plan(
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {
                    "id": "review_each",
                    "requires_ack": True,
                    "adapter": "manual",
                    "command": "review.sh",
                    "instructions": "review",
                    "ack": {"kind": "human"},
                    "repeat": {"for_each": {"items": ["a"]}},
                }
            ],
        }
    )
    events = [
        {"kind": "for_each_expanded", "plan_step_path": ["review_each"], "item_ids": ["a"]},
        {"kind": "item_started", "plan_step_path": ["review_each"], "item_id": "a"},
        {
            "kind": "item_attested",
            "plan_step_path": ["review_each"],
            "item_id": "a",
            "attestor_kind": "human",
            "attestor_id": "alice",
        },
    ]

    peek = task_gate.peek_current_step(
        plan,
        events,
        "demo",
        project_root=tmp_path / "demo",
        run_id="run-1",
    )

    assert peek.exhausted is True
    assert peek.step is None
    assert not any(event.get("kind") == "item_skipped" for event in events)
