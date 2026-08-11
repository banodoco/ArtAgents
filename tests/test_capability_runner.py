from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from astrid.core.contracts.capability_runner import CapabilityRunner
from astrid.core.contracts.run_status import RunStatus


class _Registry:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, capability_id: str) -> str:
        self.calls.append(capability_id)
        return f"definition:{capability_id}"


@dataclass(frozen=True)
class _Request:
    capability_id: str
    dry_run: bool = False
    resolved: bool = False
    prepared: bool = False


@dataclass
class _ProbeRunner(CapabilityRunner[_Request, str, str]):
    events: list[str] = field(default_factory=list)
    execute_error: BaseException | None = None
    finalize_error: BaseException | None = None
    mark_error: BaseException | None = None
    mark_calls: int = 0
    registry: _Registry = field(default_factory=_Registry)
    prepare_returns_none: bool = False

    def load_default_registry(self) -> _Registry:
        self.events.append("load_default_registry")
        return self.registry

    def request_id(self, request: _Request) -> str:
        self.events.append("request_id")
        return request.capability_id

    def maybe_gate(self, request: _Request) -> None:
        self.events.append("maybe_gate")

    def is_dry_run(self, request: _Request, definition: str) -> bool:
        self.events.append(f"is_dry_run:{definition}")
        return request.dry_run

    def prepare_dry_run_request(self, request: _Request, definition: str) -> _Request:
        self.events.append(f"prepare_dry_run_request:{definition}")
        return _Request(
            capability_id=request.capability_id,
            dry_run=request.dry_run,
            resolved=request.resolved,
            prepared=request.prepared,
        )

    def resolve_project_request(self, request: _Request, definition: str) -> _Request:
        self.events.append(f"resolve_project_request:{definition}")
        return _Request(
            capability_id=request.capability_id,
            dry_run=request.dry_run,
            resolved=True,
            prepared=request.prepared,
        )

    def prepare_project(self, request: _Request, definition: str) -> tuple[object | None, _Request]:
        self.events.append(f"prepare_project:{request.resolved}")
        if self.prepare_returns_none:
            return (
                None,
                _Request(
                    capability_id=request.capability_id,
                    dry_run=request.dry_run,
                    resolved=request.resolved,
                    prepared=True,
                ),
            )
        return (
            object(),
            _Request(
                capability_id=request.capability_id,
                dry_run=request.dry_run,
                resolved=request.resolved,
                prepared=True,
            ),
        )

    def run_inner(self, request: _Request, definition: str) -> str:
        self.events.append(f"run_inner:resolved={request.resolved}:prepared={request.prepared}")
        if self.execute_error is not None:
            raise self.execute_error
        return "ok"

    def finalize_project(
        self,
        context: object,
        request: _Request,
        *,
        status: RunStatus,
        returncode: int | None,
        error: BaseException | str | None = None,
    ) -> None:
        self.events.append(
            f"finalize_project:{status.value}:returncode={returncode}:error={type(error).__name__ if error else 'None'}"
        )
        if self.finalize_error is not None:
            raise self.finalize_error

    def status_for_result(self, result: str) -> RunStatus:
        self.events.append("status_for_result")
        return RunStatus.COMPLETED

    def result_returncode(self, result: str) -> int | None:
        self.events.append("result_returncode")
        return 0

    def mark_finalize_failed(
        self, context: object, request: _Request, finalize_error: BaseException
    ) -> None:
        self.mark_calls += 1
        self.events.append(f"mark_finalize_failed:{type(finalize_error).__name__}")
        if self.mark_error is not None:
            raise self.mark_error


def test_capability_runner_orders_normal_lifecycle_and_threads_resolved_request() -> None:
    runner = _ProbeRunner()

    result = runner.run(_Request("demo"))

    assert result == "ok"
    assert runner.events == [
        "maybe_gate",
        "load_default_registry",
        "request_id",
        "resolve_project_request:definition:demo",
        "is_dry_run:definition:demo",
        "prepare_project:True",
        "run_inner:resolved=True:prepared=True",
        "status_for_result",
        "result_returncode",
        "finalize_project:completed:returncode=0:error=None",
    ]
    assert runner.mark_calls == 0


def test_capability_runner_requires_project_resolution_before_dry_run() -> None:
    runner = _ProbeRunner()

    result = runner.run(_Request("demo", dry_run=True))

    assert result == "ok"
    assert runner.events == [
        "maybe_gate",
        "load_default_registry",
        "request_id",
        "resolve_project_request:definition:demo",
        "is_dry_run:definition:demo",
        "prepare_dry_run_request:definition:demo",
        "run_inner:resolved=True:prepared=False",
    ]
    assert runner.mark_calls == 0


def test_capability_runner_preserves_execution_exception_when_failed_finalize_also_fails() -> None:
    execute_error = RuntimeError("boom")
    finalize_error = ValueError("could not finalize")
    runner = _ProbeRunner(execute_error=execute_error, finalize_error=finalize_error)

    with pytest.raises(RuntimeError, match="boom") as excinfo:
        runner.run(_Request("demo"))

    assert excinfo.value is execute_error
    assert runner.mark_calls == 0
    notes = list(getattr(excinfo.value, "__notes__", []))
    assert any("ValueError: could not finalize" in note for note in notes)
    assert runner.events[-1] == "finalize_project:failed:returncode=-1:error=RuntimeError"


def test_capability_runner_marks_finalize_failure_once_and_reraises_finalize_error() -> None:
    finalize_error = RuntimeError("finalize broke")
    mark_error = ValueError("secondary write broke")
    runner = _ProbeRunner(finalize_error=finalize_error, mark_error=mark_error)

    with pytest.raises(RuntimeError, match="finalize broke") as excinfo:
        runner.run(_Request("demo"))

    assert excinfo.value is finalize_error
    assert runner.mark_calls == 1
    notes = list(getattr(excinfo.value, "__notes__", []))
    assert any("ValueError: secondary write broke" in note for note in notes)
    assert runner.events[-1] == "mark_finalize_failed:RuntimeError"


def test_capability_runner_execution_failure_with_successful_finalize_preserves_original_exception() -> None:
    """When execution fails but finalize succeeds, the original execution
    exception is re-raised without notes or mark calls."""
    execute_error = RuntimeError("boom")
    runner = _ProbeRunner(execute_error=execute_error)

    with pytest.raises(RuntimeError, match="boom") as excinfo:
        runner.run(_Request("demo"))

    assert excinfo.value is execute_error
    assert runner.mark_calls == 0
    notes = list(getattr(excinfo.value, "__notes__", []))
    assert notes == []
    # Verify finalize was called with FAILED status
    assert "finalize_project:failed:returncode=-1:error=RuntimeError" in runner.events


def test_capability_runner_success_path_finalize_failure_with_successful_mark() -> None:
    """When execution succeeds but finalize fails, mark_finalize_failed is
    called exactly once, and the finalize error is re-raised."""
    finalize_error = RuntimeError("finalize broke")
    runner = _ProbeRunner(finalize_error=finalize_error)

    with pytest.raises(RuntimeError, match="finalize broke") as excinfo:
        runner.run(_Request("demo"))

    assert excinfo.value is finalize_error
    assert runner.mark_calls == 1
    notes = list(getattr(excinfo.value, "__notes__", []))
    assert notes == []
    # Verify both finalize and mark were called in order
    assert "finalize_project:completed:returncode=0:error=None" in runner.events
    assert "mark_finalize_failed:RuntimeError" in runner.events


def test_capability_runner_skips_finalize_when_project_context_is_none_on_success() -> None:
    """When prepare_project returns a None context, finalize is never called
    on the success path."""
    runner = _ProbeRunner(prepare_returns_none=True)

    result = runner.run(_Request("demo"))

    assert result == "ok"
    assert runner.mark_calls == 0
    assert "finalize_project" not in runner.events
    assert runner.events == [
        "maybe_gate",
        "load_default_registry",
        "request_id",
        "resolve_project_request:definition:demo",
        "is_dry_run:definition:demo",
        "prepare_project:True",
        "run_inner:resolved=True:prepared=True",
    ]


def test_capability_runner_skips_finalize_when_project_context_is_none_on_failure() -> None:
    """When prepare_project returns a None context and execution fails,
    finalize is never called, and the original exception is re-raised."""
    execute_error = RuntimeError("boom")
    runner = _ProbeRunner(execute_error=execute_error, prepare_returns_none=True)

    with pytest.raises(RuntimeError, match="boom") as excinfo:
        runner.run(_Request("demo"))

    assert excinfo.value is execute_error
    assert runner.mark_calls == 0
    notes = list(getattr(excinfo.value, "__notes__", []))
    assert notes == []
    assert "finalize_project" not in runner.events


def test_capability_runner_uses_provided_registry_instead_of_loading_default() -> None:
    """When an explicit registry is passed to run(), load_default_registry is
    skipped and the provided registry is used for definition lookup."""
    provided_registry = _Registry()
    runner = _ProbeRunner()

    result = runner.run(_Request("custom"), registry=provided_registry)

    assert result == "ok"
    assert "load_default_registry" not in runner.events
    assert provided_registry.calls == ["custom"]
    # The default registry was never touched
    assert runner.registry.calls == []


def test_capability_runner_full_event_order_on_execution_failure_path() -> None:
    """Verify the complete hook order when execution fails and finalize succeeds."""
    execute_error = RuntimeError("boom")
    runner = _ProbeRunner(execute_error=execute_error)

    with pytest.raises(RuntimeError):
        runner.run(_Request("demo"))

    assert runner.events == [
        "maybe_gate",
        "load_default_registry",
        "request_id",
        "resolve_project_request:definition:demo",
        "is_dry_run:definition:demo",
        "prepare_project:True",
        "run_inner:resolved=True:prepared=True",
        "finalize_project:failed:returncode=-1:error=RuntimeError",
    ]


def test_capability_runner_full_event_order_on_success_path_finalize_failure() -> None:
    """Verify the complete hook order when execution succeeds but finalize fails
    (with successful mark)."""
    finalize_error = RuntimeError("finalize broke")
    runner = _ProbeRunner(finalize_error=finalize_error)

    with pytest.raises(RuntimeError):
        runner.run(_Request("demo"))

    assert runner.events == [
        "maybe_gate",
        "load_default_registry",
        "request_id",
        "resolve_project_request:definition:demo",
        "is_dry_run:definition:demo",
        "prepare_project:True",
        "run_inner:resolved=True:prepared=True",
        "status_for_result",
        "result_returncode",
        "finalize_project:completed:returncode=0:error=None",
        "mark_finalize_failed:RuntimeError",
    ]
