"""T13: cmd_next prints PROHIBITION_PREAMBLE byte-for-byte every call (SD-023);
code-step prints `run: <command>`; attested-step prints instructions + ack
template with --agent or --human based on ack.kind; iter>=2 ledger and
for_each item ledger render correctly.
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import setup_run  # noqa: E402

from astrid.core.task import write_iteration_feedback
from astrid.core.task.claim import _make_claim_event
from astrid.core.task.events import (
    append_event,
    make_iteration_failed_event,
    make_iteration_started_event,
    read_events,
)
from astrid.core.task.gate import GateDecision, TaskRunGateError, gate_command
from astrid.core.task.lifecycle import cmd_next
from astrid.core.task.preamble import PROHIBITION_PREAMBLE

_BODY_CODE = '''from astrid.orchestrate import orchestrator, code
@orchestrator("demo.code")
def main(): return [code("step_a", argv=["echo", "alpha"])]
'''

_BODY_AGENT = '''from astrid.orchestrate import orchestrator, attested
@orchestrator("demo.review_agent")
def main(): return [attested("review", command="review.sh", instructions="please review", ack="agent")]
'''

_BODY_HUMAN = '''from astrid.orchestrate import orchestrator, attested
@orchestrator("demo.review_human")
def main(): return [attested("review", command="ok.sh", instructions="confirm", ack="human")]
'''

_BODY_ITER = '''from astrid.orchestrate import orchestrator, attested, repeat_until
@orchestrator("demo.iter")
def main(): return [attested("review", command="r.sh", instructions="ok", ack="human",
    repeat=repeat_until(condition="user_approves", max_iterations=3, on_exhaust="fail"))]
'''

_BODY_FE = '''from astrid.orchestrate import orchestrator, attested, repeat_for_each
@orchestrator("demo.fe")
def main(): return [attested("review_each", command="r.sh", instructions="check", ack="human",
    repeat=repeat_for_each(items=["a","b","c"]))]
'''


def _capture_next(packs: Path, projects: Path) -> str:
    buf = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        cmd_next(["--project", "p"], projects_root=projects)
    return buf.getvalue()


def _set_step_assignee(projects: Path, run_id: str, step: str, assignee: str) -> None:
    events_path = projects / "p" / "runs" / run_id / "events.jsonl"
    append_event(
        events_path,
        {
            "kind": "plan_mutated",
            "diff": {"op": "edit", "path": step, "fields": {"assignee": assignee}},
        },
    )


def test_preamble_byte_identical_across_two_calls(tmp_path: Path) -> None:
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r1")
    out1 = _capture_next(packs, projects)
    out2 = _capture_next(packs, projects)
    # SD-023: preamble is verbatim every call so Stop-hook re-injection sees stable bytes.
    assert PROHIBITION_PREAMBLE in out1
    assert PROHIBITION_PREAMBLE in out2
    assert out1 == out2, "cmd_next must produce byte-identical output across calls"


def test_code_step_prints_command(tmp_path: Path) -> None:
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r2")
    out = _capture_next(packs, projects)
    assert "run: ASTRID_INTERNAL_INVOCATION=1" in out
    assert "ASTRID_TASK_PROJECT=p" in out
    assert "ASTRID_TASK_RUN_ID=r2" in out
    assert "ASTRID_TASK_STEP_ID=step_a" in out
    assert "echo alpha" in out
    assert "warning: this code-step command uses task env instead of a local --project argument" in out
    assert "add --project" not in out


def test_env_prefixed_cmd_next_command_is_the_only_gate_wrapper_normalization(tmp_path: Path) -> None:
    _packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r2b")
    out = _capture_next(_packs, projects)
    displayed = next(line.removeprefix("run: ") for line in out.splitlines() if line.startswith("run: "))

    decision = gate_command("p", displayed, [])
    assert decision.active is True

    events = read_events(projects / "p" / "runs" / "r2b" / "events.jsonl")
    dispatched = [event for event in events if event.get("kind") == "step_dispatched"]
    assert dispatched[-1]["command"] == "echo alpha"

    with pytest.raises(TaskRunGateError):
        gate_command("p", f"OTHER_ENV=1 {displayed}", [])


def test_cmd_next_renders_no_task_placeholders_in_code_step(tmp_path: Path) -> None:
    _packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r2c")
    out = _capture_next(_packs, projects)
    assert "$ASTRID_" not in out
    assert "{{" not in next(line for line in out.splitlines() if line.startswith("run: "))


def test_attested_agent_template(tmp_path: Path) -> None:
    packs, projects = setup_run(
        tmp_path, "demo", "review_agent", _BODY_AGENT, "demo.review_agent", run_id="r3"
    )
    out = _capture_next(packs, projects)
    assert "please review" in out
    assert "--decision approve --agent <id>" in out
    # No --human token in template since ack.kind=agent
    template_line = next(line for line in out.splitlines() if "astrid ack review" in line)
    assert "--human" not in template_line


def test_attested_human_template(tmp_path: Path) -> None:
    packs, projects = setup_run(
        tmp_path, "demo", "review_human", _BODY_HUMAN, "demo.review_human", run_id="r4"
    )
    out = _capture_next(packs, projects)
    assert "confirm" in out
    assert "--decision approve --human <name>" in out


def test_any_human_claim_fills_next_human_template(tmp_path: Path) -> None:
    packs, projects = setup_run(
        tmp_path, "demo", "review_human", _BODY_HUMAN, "demo.review_human", run_id="r4c"
    )
    _set_step_assignee(projects, "r4c", "review", "any-human")
    events_path = projects / "p" / "runs" / "r4c" / "events.jsonl"
    append_event(
        events_path,
        _make_claim_event(
            "review", claimed_by="human:Alice", claimed_by_kind="human", writer_epoch=1
        ),
    )
    out = _capture_next(packs, projects)
    assert "assignee: any-human  claimed: human:Alice" in out
    assert "--decision approve --human Alice" in out


def test_concrete_agent_assignee_fills_next_agent_template(tmp_path: Path) -> None:
    packs, projects = setup_run(
        tmp_path, "demo", "review_agent", _BODY_AGENT, "demo.review_agent", run_id="r4d"
    )
    _set_step_assignee(projects, "r4d", "review", "agent:gpt-5")
    out = _capture_next(packs, projects)
    assert "assignee: agent:gpt-5" in out
    assert "--decision approve --agent gpt-5" in out


def test_iteration_ledger_at_iter_2(tmp_path: Path) -> None:
    packs, projects = setup_run(tmp_path, "demo", "iter", _BODY_ITER, "demo.iter", run_id="r5")
    events_path = projects / "p" / "runs" / "r5" / "events.jsonl"
    # Simulate iteration 1 attempted+failed; write iter-1 cumulative feedback.
    append_event(events_path, make_iteration_started_event(("review",), 1))
    decision = GateDecision(
        active=True, run_id="r5", slug="p", project_root=projects / "p",
        plan_step_path=("review",), iteration=1, events_path=events_path,
    )
    write_iteration_feedback(decision, "be more concise")
    append_event(events_path, make_iteration_failed_event(("review",), 1, reason="iterate_feedback"))
    out = _capture_next(packs, projects)
    assert "feedback ledger (through iteration 1)" in out
    assert "be more concise" in out


def test_for_each_item_ledger(tmp_path: Path) -> None:
    packs, projects = setup_run(tmp_path, "demo", "fe", _BODY_FE, "demo.fe", run_id="r6")
    out = _capture_next(packs, projects)
    assert "for_each items" in out
    assert "[ ] a" in out
    assert "[ ] b" in out
    assert "[ ] c" in out
    assert "<- next" in out
    # ack template gets the [--item <id>] hint when host is for_each.
    assert "[--item <id>]" in out
