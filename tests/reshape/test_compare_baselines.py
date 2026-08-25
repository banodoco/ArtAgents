"""Fail-closed execution checks for the Ruff and mypy baseline wrappers."""

from __future__ import annotations

import importlib
import subprocess

import pytest


@pytest.mark.parametrize(
    ("module_name", "stdout", "stderr", "returncode"),
    [
        ("scripts.reshape.compare_ruff_baseline", "", "No module named ruff", 1),
        ("scripts.reshape.compare_mypy_baseline", "", "No module named mypy", 1),
    ],
)
def test_missing_tool_is_not_treated_as_zero_findings(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    stdout: str,
    stderr: str,
    returncode: int,
) -> None:
    module = importlib.import_module(module_name)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], returncode, stdout=stdout, stderr=stderr
        ),
    )

    with pytest.raises(RuntimeError, match="failed to execute"):
        module._run()


def test_ruff_findings_exit_one_remains_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("scripts.reshape.compare_ruff_baseline")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, stdout='[{"code": "E501"}]', stderr=""
        ),
    )

    result = module._run()

    assert result["finding_count"] == 1


def test_mypy_findings_exit_one_remains_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("scripts.reshape.compare_mypy_baseline")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            stdout="astrid/example.py:7: error: Bad value  [assignment]\n",
            stderr="",
        ),
    )

    result = module._run()

    assert result["finding_count"] == 1
    assert result["code_counts"] == {"assignment": 1}
    assert "--no-pretty" in result["command"]
