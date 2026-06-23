from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass

import pytest


def _clear_host_modules() -> None:
    for name in (
        "astrid.core.integrations.arnold.host.driver",
        "astrid.core.integrations.arnold.host.compat",
        "astrid.core.integrations.arnold.host",
        "astrid.core.integrations.arnold",
    ):
        sys.modules.pop(name, None)


def _install_fake_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    pipeline: types.ModuleType,
) -> None:
    fake_arnold = types.ModuleType("arnold")
    fake_arnold.pipeline = pipeline
    monkeypatch.setitem(sys.modules, "arnold", fake_arnold)
    monkeypatch.setitem(sys.modules, "arnold.pipeline", pipeline)


@pytest.fixture(autouse=True)
def _clean_modules_fixture() -> None:
    _clear_host_modules()
    yield
    _clear_host_modules()


class _CrossCutting:
    cost = {}
    lineage = []


class _RuntimeEnvelope:
    run_id = ""
    artifact_root = ""
    resume_cursor = ""
    cross_cutting = _CrossCutting()

    def __init__(self, run_id: str, artifact_root: str, resume_cursor: str):
        self.run_id = run_id
        self.artifact_root = artifact_root
        self.resume_cursor = resume_cursor
        self.cross_cutting = _CrossCutting()


@dataclass
class _AdvanceOutcome:
    kind: str = "advanced"


@dataclass
class _CheckpointOutcome:
    cursor: str = "cursor.json"


@dataclass
class _Suspension:
    kind: str = "human"
    resume_input_schema: dict[str, object] | None = None


@dataclass
class _StepContext:
    inputs: dict[str, object] | None = None
    hook_extensions: dict[str, object] | None = None


@dataclass
class _ContractResult:
    suspension: _Suspension | None = None


def _make_pipeline(stepwise_driver: type[object]) -> types.ModuleType:
    pipeline = types.ModuleType("arnold.pipeline")
    exports = {
        "RuntimeEnvelope": _RuntimeEnvelope,
        "ResumeCursorRef": type("ResumeCursorRef", (), {}),
        "AdvanceOutcome": _AdvanceOutcome,
        "CheckpointOutcome": _CheckpointOutcome,
        "StepwiseDriver": stepwise_driver,
        "PipelineBuilder": type("PipelineBuilder", (), {}),
        "Stage": type("Stage", (), {}),
        "ParallelStage": type("ParallelStage", (), {}),
        "Edge": type("Edge", (), {}),
        "Suspension": _Suspension,
        "StepContext": _StepContext,
        "ExecutorHooks": type("ExecutorHooks", (), {}),
        "StepInvocation": type("StepInvocation", (), {}),
        "ContractResult": _ContractResult,
        "ContractStatus": type("ContractStatus", (), {}),
        "PipelineVerdict": type("PipelineVerdict", (), {}),
        "persist_resume_cursor": lambda *args, **kwargs: None,
        "read_resume_cursor": lambda *args, **kwargs: None,
    }
    for name, value in exports.items():
        setattr(pipeline, name, value)
    return pipeline


def test_host_driver_rejects_protocol_only_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_host_modules()

    class ProtocolDriver:
        _is_protocol = True

        def advance(self, envelope: object) -> _AdvanceOutcome:
            return _AdvanceOutcome()

        def checkpoint(self, envelope: object) -> _CheckpointOutcome:
            return _CheckpointOutcome()

        def resume(self, envelope: object, cursor: object) -> _RuntimeEnvelope:
            return envelope  # type: ignore[return-value]

    _install_fake_pipeline(monkeypatch, _make_pipeline(ProtocolDriver))

    driver_module = importlib.import_module("astrid.core.integrations.arnold.host.driver")

    with pytest.raises(driver_module.StepwiseDriverContractError) as excinfo:
        driver_module.get_driver()

    assert "only exposes the protocol type" in str(excinfo.value)


def test_host_driver_forwards_exactly_one_underlying_call_per_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_host_modules()

    calls: list[tuple[str, object, object | None]] = []

    class ConcreteDriver:
        def advance(self, envelope: _RuntimeEnvelope) -> _AdvanceOutcome:
            calls.append(("advance", envelope, None))
            return _AdvanceOutcome(kind="awaiting")

        def checkpoint(self, envelope: _RuntimeEnvelope) -> _CheckpointOutcome:
            calls.append(("checkpoint", envelope, None))
            return _CheckpointOutcome(cursor=envelope.resume_cursor)

        def resume(self, envelope: _RuntimeEnvelope, cursor: object) -> _RuntimeEnvelope:
            calls.append(("resume", envelope, cursor))
            return envelope

    _install_fake_pipeline(monkeypatch, _make_pipeline(ConcreteDriver))

    driver_module = importlib.import_module("astrid.core.integrations.arnold.host.driver")
    host_driver = driver_module.get_driver()
    envelope = _RuntimeEnvelope(
        run_id="run-1",
        artifact_root="/tmp/run-1",
        resume_cursor="cursor.json",
    )
    cursor = object()

    advanced = host_driver.advance(envelope)
    checkpointed = host_driver.checkpoint(envelope)
    resumed = host_driver.resume(envelope, cursor)

    assert isinstance(advanced, _AdvanceOutcome)
    assert isinstance(checkpointed, _CheckpointOutcome)
    assert resumed is envelope
    assert resumed.run_id == "run-1"
    assert calls == [
        ("advance", envelope, None),
        ("checkpoint", envelope, None),
        ("resume", envelope, cursor),
    ]


def test_host_driver_rejects_incompatible_outcome_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_host_modules()

    class ConcreteDriver:
        def advance(self, envelope: _RuntimeEnvelope) -> object:
            return object()

        def checkpoint(self, envelope: _RuntimeEnvelope) -> _CheckpointOutcome:
            return _CheckpointOutcome()

        def resume(self, envelope: _RuntimeEnvelope, cursor: object) -> _RuntimeEnvelope:
            return envelope

    _install_fake_pipeline(monkeypatch, _make_pipeline(ConcreteDriver))

    driver_module = importlib.import_module("astrid.core.integrations.arnold.host.driver")
    host_driver = driver_module.get_driver()
    envelope = _RuntimeEnvelope(
        run_id="run-1",
        artifact_root="/tmp/run-1",
        resume_cursor="cursor.json",
    )

    with pytest.raises(driver_module.ArnoldHostDriverError) as excinfo:
        host_driver.advance(envelope)

    assert "expected AdvanceOutcome, got object" in str(excinfo.value)
