from __future__ import annotations

import ast
from pathlib import Path

from astrid.core.contracts.run_status import STEP_TERMINAL_KINDS, TASK_FINALIZABLE_EVENT_KINDS
from astrid.core.task import gate as task_gate
from astrid.core.task import gate_cursor, operator_view, run_state
from astrid.core.task.plan import Step, TaskPlan, _validate_plan
from astrid.core.task.run_state import _run_is_complete


def test_step_terminal_consumers_derive_from_canonical_contract() -> None:
    assert run_state._RUN_STATE_TERMINAL_KINDS is STEP_TERMINAL_KINDS
    assert gate_cursor._CURSOR_ADVANCE_KINDS is STEP_TERMINAL_KINDS
    assert operator_view._PROGRESS_TERMINAL_KINDS is STEP_TERMINAL_KINDS
    assert task_gate._GATE_FINALIZABLE_EVENT_KINDS is TASK_FINALIZABLE_EVENT_KINDS
    assert STEP_TERMINAL_KINDS <= task_gate._GATE_FINALIZABLE_EVENT_KINDS
    assert "step_awaiting_fetch" in task_gate._GATE_FINALIZABLE_EVENT_KINDS
    assert "step_dispatched" not in task_gate._GATE_FINALIZABLE_EVENT_KINDS


def test_step_terminal_consumers_do_not_hand_roll_terminal_sets() -> None:
    module_paths = (
        Path(run_state.__file__),
        Path(gate_cursor.__file__),
        Path(operator_view.__file__),
        Path(task_gate.__file__),
    )
    for module_path in module_paths:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Set):
                continue
            literals = {
                elt.value
                for elt in node.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            }
            hand_rolled_terminal = literals & STEP_TERMINAL_KINDS
            assert len(hand_rolled_terminal) < 3, (
                f"{module_path} hand-rolls step terminal kinds: "
                f"{sorted(hand_rolled_terminal)!r}"
            )


def test_step_failed_terminal_state_is_consistent_across_readers() -> None:
    plan = TaskPlan(
        plan_id="terminal-failed",
        version=2,
        steps=(Step(id="render", adapter="local", command="false"),),
    )
    events = [
        {"kind": "run_started", "run_id": "run-1"},
        {
            "kind": "step_dispatched",
            "plan_step_path": ["render"],
            "command": "false",
            "step_version": 1,
            "hash": "sha256:dispatch",
        },
        {
            "kind": "step_failed",
            "plan_step_path": ["render"],
            "returncode": 1,
            "reason": "nonzero exit",
            "step_version": 1,
            "dispatch_event_hash": "sha256:dispatch",
        },
    ]

    assert _run_is_complete(plan, events) is True
    assert gate_cursor.derive_cursor(plan, events).at_root_done is True
    assert operator_view._leaf_progress(plan, events) == (1, 1)


def test_step_failed_with_produces_does_not_wait_for_successful_produces_checks() -> None:
    plan = _validate_plan(
        {
            "plan_id": "terminal-failed-produces",
            "version": 2,
            "steps": [
                {
                    "id": "render",
                    "adapter": "local",
                    "command": "false",
                    "produces": {
                        "output": {
                            "path": "out.txt",
                            "check": {"check_id": "file_nonempty", "params": {}},
                        }
                    },
                }
            ],
        }
    )
    events = [
        {"kind": "run_started", "run_id": "run-1"},
        {"kind": "step_dispatched", "plan_step_path": ["render"], "step_version": 1},
        {"kind": "step_failed", "plan_step_path": ["render"], "returncode": 1, "step_version": 1},
    ]

    assert _run_is_complete(plan, events) is True
    assert gate_cursor.derive_cursor(plan, events).at_root_done is True
    assert operator_view._leaf_progress(plan, events) == (1, 1)
