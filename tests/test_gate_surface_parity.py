from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from astrid.core import gate as stable_gate
from astrid.core.gate.base import TaskRunGateError as stable_gate_error
from astrid.core.gateway import _main_impl
from astrid.core.task import gate as legacy_gate
from astrid.core.task.gate.base import TaskRunGateError as legacy_gate_error


def test_stable_gate_home_reexports_legacy_gate_primitives_by_identity() -> None:
    assert stable_gate.TaskRunGateError is legacy_gate.TaskRunGateError
    assert stable_gate.command_for_argv is legacy_gate.command_for_argv
    assert stable_gate.gate_command is legacy_gate.gate_command
    assert stable_gate.peek_current_step is legacy_gate.peek_current_step
    assert stable_gate.record_dispatch_complete is legacy_gate.record_dispatch_complete
    assert stable_gate_error is legacy_gate_error


def test_stable_gate_home_preserves_inactive_gate_behavior(tmp_path: Path) -> None:
    stable_decision = stable_gate.gate_command("demo", "echo one", [], root=tmp_path)
    legacy_decision = legacy_gate.gate_command("demo", "echo one", [], root=tmp_path)

    assert stable_decision == legacy_decision
    assert stable_decision.active is False
    assert stable_gate.command_for_argv(["astrid", "done", "--agent", "a 1"]) == (
        legacy_gate.command_for_argv(["astrid", "done", "--agent", "a 1"])
    )


def test_gateway_entrypoint_uses_stable_gate_home() -> None:
    with patch("astrid.core.gateway._verb_is_unbound_allowlisted", return_value=True):
        with patch("astrid.core.gate.gate_command", return_value=stable_gate.GateDecision(active=False)) as gate_mock:
            with patch("astrid.core.gateway._dispatch", return_value=123) as dispatch_mock:
                result = _main_impl(["orchestrate", "run", "--project", "demo"])

    assert result == 123
    gate_mock.assert_called_once_with(
        "demo",
        stable_gate.command_for_argv(["orchestrate", "run", "--project", "demo"]),
        ["orchestrate", "run", "--project", "demo"],
    )
    dispatch_mock.assert_called_once_with(["orchestrate", "run", "--project", "demo"])
