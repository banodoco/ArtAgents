"""T13: ExecError contract on ExecutorRunResult and GenerationResult.

``ok`` derives from ``error is None`` on both result types; a blocked run and
a missing-binary run each surface ``ok=False`` with a populated ``ExecError``.
"""

from __future__ import annotations

from astrid.contracts.exec_error import (
    ExecError,
    error_from_missing_binaries,
    error_from_returncode,
)
from astrid.core.executor.runner import ExecutorRunResult
from astrid.core.generation.backends.base import GenerationResult


def test_error_from_returncode_derivation() -> None:
    assert error_from_returncode(None) is None
    assert error_from_returncode(0) is None
    derived = error_from_returncode(2)
    assert derived is not None
    assert derived.code == "nonzero_exit"


def test_error_from_missing_binaries_derivation() -> None:
    assert error_from_missing_binaries(()) is None
    derived = error_from_missing_binaries(("ffmpeg",))
    assert derived is not None
    assert derived.code == "missing_binaries"
    assert "ffmpeg" in derived.message


def test_executor_run_result_ok_derives_from_error() -> None:
    success = ExecutorRunResult(executor_id="x", kind="external", returncode=0)
    assert success.ok is True
    assert success.error is None


def test_executor_run_result_dry_run_and_skip_are_ok() -> None:
    dry = ExecutorRunResult(executor_id="x", kind="external", dry_run=True)
    skip = ExecutorRunResult(
        executor_id="x", kind="external", skipped=True, skipped_reason="cond"
    )
    assert dry.ok is True
    assert skip.ok is True


def test_executor_run_result_missing_binaries_surfaces_error() -> None:
    result = ExecutorRunResult(
        executor_id="x", kind="external", missing_binaries=("ffmpeg",)
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "missing_binaries"


def test_executor_run_result_blocked_surfaces_error() -> None:
    blocked = ExecutorRunResult(
        executor_id="x",
        kind="external",
        error=ExecError(
            code="blocked",
            type="gate",
            message="run rejected by gate",
            recovery="resolve the gate and retry",
        ),
    )
    assert blocked.ok is False
    assert blocked.error is not None
    assert blocked.error.code == "blocked"


def test_executor_run_result_explicit_error_not_overwritten() -> None:
    # An explicit error survives even when returncode is 0.
    result = ExecutorRunResult(
        executor_id="x",
        kind="external",
        returncode=0,
        error=ExecError(code="blocked", type="gate", message="blocked"),
    )
    assert result.ok is False
    assert result.error.code == "blocked"


def test_generation_result_ok_derives_from_error() -> None:
    success = GenerationResult(model_actual="image/z_image")
    assert success.ok is True
    assert success.error is None

    failed = GenerationResult(
        error=ExecError(code="backend_error", type="process", message="boom")
    )
    assert failed.ok is False
    assert failed.error is not None
    assert failed.error.code == "backend_error"
