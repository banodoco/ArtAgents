"""Tests for astrid.core.run_subprocess."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from astrid.core.contracts.errors import AstridError
from astrid.core.run_subprocess import run_subprocess


def test_returns_stdout_on_success() -> None:
    with patch("astrid.core.run_subprocess.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["echo", "hello"],
            returncode=0,
            stdout="hello world\n",
            stderr="",
        )
        result = run_subprocess(["echo", "hello"], label="echo-test")
        assert result == "hello world\n"
        mock_run.assert_called_once_with(
            ["echo", "hello"],
            capture_output=True,
            text=True,
        )


def test_raises_astrid_error_on_failure() -> None:
    with patch("astrid.core.run_subprocess.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["false"],
            returncode=1,
            stdout="",
            stderr="command not found",
        )
        try:
            run_subprocess(["false"], label="fail-test")
            assert False, "expected AstridError"
        except AstridError as exc:
            assert "fail-test" in exc.cause
            assert "exit 1" in exc.cause
            assert exc.recovery_command
            assert "false" in exc.recovery_command
            assert exc.state_snapshot["command"] == "false"
            assert exc.state_snapshot["stdout"] == ""
            assert exc.state_snapshot["stderr"] == "command not found"


def test_orchestrator_prefix_in_error_message() -> None:
    with patch("astrid.core.run_subprocess.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["bad"],
            returncode=2,
            stdout="",
            stderr="oops",
        )
        try:
            run_subprocess(
                ["bad"],
                label="boom",
                orchestrator="my.orchestrator",
            )
            assert False, "expected AstridError"
        except AstridError as exc:
            assert exc.cause.startswith("[my.orchestrator]")
            assert "boom" in exc.cause


def test_no_orchestrator_prefix_when_not_given() -> None:
    with patch("astrid.core.run_subprocess.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["bad"],
            returncode=2,
            stdout="",
            stderr="oops",
        )
        try:
            run_subprocess(["bad"], label="boom")
            assert False, "expected AstridError"
        except AstridError as exc:
            assert not exc.cause.startswith("[")


def test_extra_kwargs_forwarded_to_subprocess_run() -> None:
    with patch("astrid.core.run_subprocess.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ls"],
            returncode=0,
            stdout="ok\n",
            stderr="",
        )
        run_subprocess(
            ["ls"],
            label="ls-test",
            env={"HOME": "/tmp"},
            cwd="/tmp",
            timeout=30,
        )
        mock_run.assert_called_once_with(
            ["ls"],
            capture_output=True,
            text=True,
            env={"HOME": "/tmp"},
            cwd="/tmp",
            timeout=30,
        )


def test_state_snapshot_uses_json_safe_values() -> None:
    with patch("astrid.core.run_subprocess.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["boom"],
            returncode=3,
            stdout="line1\nline2\n",
            stderr="error\n",
        )
        try:
            run_subprocess(["boom", "--flag", "value"], label="test")
            assert False, "expected AstridError"
        except AstridError as exc:
            snapshot = exc.state_snapshot
            assert snapshot["command"] == "boom --flag value"
            assert snapshot["stdout"] == "line1\nline2\n"
            assert snapshot["stderr"] == "error\n"
            # Ensure snapshot is JSON-safe
            import json
            json.dumps(snapshot)
