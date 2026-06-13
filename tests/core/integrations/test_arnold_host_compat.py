from __future__ import annotations

import importlib
import sys
import types

import pytest


def _clear_host_modules() -> None:
    for name in (
        "astrid.core.integrations.arnold.host.compat",
        "astrid.core.integrations.arnold.host",
        "astrid.core.integrations.arnold",
    ):
        sys.modules.pop(name, None)


def _install_fake_pipeline(monkeypatch: pytest.MonkeyPatch, pipeline: types.ModuleType) -> None:
    fake_arnold = types.ModuleType("arnold")
    fake_arnold.pipeline = pipeline
    monkeypatch.setitem(sys.modules, "arnold", fake_arnold)
    monkeypatch.setitem(sys.modules, "arnold.pipeline", pipeline)


@pytest.fixture(autouse=True)
def _clean_modules_fixture() -> None:
    _clear_host_modules()
    yield
    _clear_host_modules()


def test_host_package_import_stays_lazy_when_arnold_contract_is_broken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_host_modules()

    broken_pipeline = types.ModuleType("arnold.pipeline")
    _install_fake_pipeline(monkeypatch, broken_pipeline)

    host_pkg = importlib.import_module("astrid.core.integrations.arnold.host")

    assert host_pkg is not None
    assert "astrid.core.integrations.arnold.host.compat" not in sys.modules


def test_compat_reports_missing_symbols_and_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_host_modules()

    class CrossCutting:
        cost = 0

    class RuntimeEnvelope:
        artifact_root = ""
        resume_cursor = ""
        cross_cutting = CrossCutting()

    class StepContext:
        inputs = None

    class ContractResult:
        status = "ok"

    class Suspension:
        reason = "wait"

    class StepwiseDriver:
        def advance(self, envelope: object) -> object:
            return object()

        def checkpoint(self) -> object:
            return object()

        def resume(self, envelope: object) -> object:
            return object()

    pipeline = types.ModuleType("arnold.pipeline")
    pipeline.RuntimeEnvelope = RuntimeEnvelope
    pipeline.StepContext = StepContext
    pipeline.ContractResult = ContractResult
    pipeline.Suspension = Suspension
    pipeline.StepwiseDriver = StepwiseDriver
    pipeline.PipelineBuilder = type("PipelineBuilder", (), {})
    pipeline.Stage = type("Stage", (), {})
    pipeline.ParallelStage = type("ParallelStage", (), {})
    pipeline.Edge = type("Edge", (), {})
    pipeline.ExecutorHooks = type("ExecutorHooks", (), {})
    pipeline.StepInvocation = type("StepInvocation", (), {})
    pipeline.ContractStatus = type("ContractStatus", (), {})
    pipeline.PipelineVerdict = type("PipelineVerdict", (), {})
    pipeline.persist_resume_cursor = lambda *args, **kwargs: None

    _install_fake_pipeline(monkeypatch, pipeline)

    with pytest.raises(ImportError) as excinfo:
        importlib.import_module("astrid.core.integrations.arnold.host.compat")

    message = str(excinfo.value)
    assert "missing symbol arnold.pipeline.ResumeCursorRef" in message
    assert "missing symbol arnold.pipeline.AdvanceOutcome" in message
    assert "missing symbol arnold.pipeline.read_resume_cursor" in message
    assert "RuntimeEnvelope missing field(s): run_id" in message
    assert "RuntimeEnvelope.cross_cutting missing field(s): lineage" in message
    assert "StepContext missing field(s): hook_extensions" in message
    assert "ContractResult missing field(s): suspension" in message
    assert "Suspension missing field(s): resume_input_schema" in message
    assert "StepwiseDriver.checkpoint signature starts with ('self',)" in message
    assert "StepwiseDriver.resume signature starts with ('self', 'envelope')" in message


def test_compat_exports_validated_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_host_modules()

    class CrossCutting:
        cost = 0
        lineage = None

    class RuntimeEnvelope:
        run_id = "run-1"
        artifact_root = "/tmp/run-1"
        resume_cursor = "cursor.json"
        cross_cutting = CrossCutting()

    class StepContext:
        inputs = None
        hook_extensions = None

    class ContractResult:
        suspension = None

    class Suspension:
        resume_input_schema = None

    class StepwiseDriver:
        def advance(self, envelope: object) -> object:
            return object()

        def checkpoint(self, envelope: object) -> object:
            return object()

        def resume(self, envelope: object, cursor: object) -> object:
            return object()

    pipeline = types.ModuleType("arnold.pipeline")
    required_symbols = {
        "RuntimeEnvelope": RuntimeEnvelope,
        "ResumeCursorRef": type("ResumeCursorRef", (), {}),
        "AdvanceOutcome": type("AdvanceOutcome", (), {}),
        "CheckpointOutcome": type("CheckpointOutcome", (), {}),
        "StepwiseDriver": StepwiseDriver,
        "PipelineBuilder": type("PipelineBuilder", (), {}),
        "Stage": type("Stage", (), {}),
        "ParallelStage": type("ParallelStage", (), {}),
        "Edge": type("Edge", (), {}),
        "Suspension": Suspension,
        "StepContext": StepContext,
        "ExecutorHooks": type("ExecutorHooks", (), {}),
        "StepInvocation": type("StepInvocation", (), {}),
        "ContractResult": ContractResult,
        "ContractStatus": type("ContractStatus", (), {}),
        "PipelineVerdict": type("PipelineVerdict", (), {}),
        "persist_resume_cursor": lambda *args, **kwargs: None,
        "read_resume_cursor": lambda *args, **kwargs: None,
        "EvidenceArtifactRef": type("EvidenceArtifactRef", (), {}),
        "Provenance": type("Provenance", (), {}),
        "StepResult": type("StepResult", (), {}),
        "StepInvocationAdapter": type("StepInvocationAdapter", (), {}),
        "StepInvocationAdapterRegistry": type("StepInvocationAdapterRegistry", (), {}),
        "ContentValidatorRegistry": type("ContentValidatorRegistry", (), {}),
        "no_op_content_validator": lambda *args, **kwargs: None,
    }
    for name, value in required_symbols.items():
        setattr(pipeline, name, value)

    _install_fake_pipeline(monkeypatch, pipeline)

    compat_module = importlib.import_module("astrid.core.integrations.arnold.host.compat")

    assert compat_module.compat.RuntimeEnvelope is RuntimeEnvelope
    assert compat_module.compat.StepwiseDriver is StepwiseDriver
    assert compat_module.read_resume_cursor is required_symbols["read_resume_cursor"]
