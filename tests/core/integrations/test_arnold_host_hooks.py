from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from astrid.core.session.lease import write_lease_init
from astrid.core.task.plan import ProducesEntry
from astrid.core.verify import file_nonempty, json_file


def _clear_modules() -> None:
    for name in (
        "astrid.core.integrations.arnold.host.hooks",
        "astrid.core.integrations.arnold.host.compat",
        "astrid.core.integrations.arnold.host",
        "astrid.core.integrations.arnold",
    ):
        sys.modules.pop(name, None)


@dataclass(frozen=True)
class _ResumeCursorRef:
    plugin_id: str = ""
    run_id: str = ""
    cursor: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _CrossCuttingEnvelope:
    cost: dict[str, Any] = field(default_factory=dict)
    lineage: tuple[str, ...] = ()


class _RuntimeEnvelope:
    run_id = ""
    artifact_root = ""
    resume_cursor = None
    cross_cutting = _CrossCuttingEnvelope()


@dataclass(frozen=True)
class _AdvanceOutcome:
    kind: str = "advanced"


@dataclass(frozen=True)
class _CheckpointOutcome:
    cursor: str = "cursor.json"


@dataclass(frozen=True)
class _Suspension:
    kind: str = "human"
    resume_input_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class _StepContext:
    artifact_root: str
    state: Any
    inputs: dict[str, Any] = field(default_factory=dict)
    hook_extensions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Provenance:
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Freshness:
    payload: dict[str, Any] = field(default_factory=dict)


class _ContractStatus:
    COMPLETED = "completed"
    FAILED = "failed"
    SUSPENDED = "suspended"


@dataclass(frozen=True)
class _ContractResult:
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = _ContractStatus.COMPLETED
    suspension: _Suspension | None = None
    evidence_refs: tuple[Any, ...] = ()
    authority_level: str = ""
    provenance: _Provenance = field(default_factory=_Provenance)
    freshness: _Freshness = field(default_factory=_Freshness)


@dataclass(frozen=True)
class _StepInvocation:
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _StepResult:
    outputs: dict[str, Any] = field(default_factory=dict)
    verdict: Any | None = None
    next: str = "halt"
    state_patch: dict[str, Any] = field(default_factory=dict)
    contract_result: _ContractResult | None = None
    hook_metadata: dict[str, Any] = field(default_factory=dict)


class _StepwiseDriver:
    def advance(self, envelope: object) -> _AdvanceOutcome:
        return _AdvanceOutcome()

    def checkpoint(self, envelope: object) -> _CheckpointOutcome:
        return _CheckpointOutcome()

    def resume(self, envelope: object, cursor: object) -> _RuntimeEnvelope:
        return _RuntimeEnvelope()


def _install_fake_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = types.ModuleType("arnold.pipeline")
    exports = {
        "RuntimeEnvelope": _RuntimeEnvelope,
        "ResumeCursorRef": _ResumeCursorRef,
        "AdvanceOutcome": _AdvanceOutcome,
        "CheckpointOutcome": _CheckpointOutcome,
        "StepwiseDriver": _StepwiseDriver,
        "PipelineBuilder": type("PipelineBuilder", (), {}),
        "Stage": type("Stage", (), {}),
        "ParallelStage": type("ParallelStage", (), {}),
        "Edge": type("Edge", (), {}),
        "Suspension": _Suspension,
        "StepContext": _StepContext,
        "ExecutorHooks": type("ExecutorHooks", (), {}),
        "StepInvocation": _StepInvocation,
        "ContractResult": _ContractResult,
        "ContractStatus": _ContractStatus,
        "PipelineVerdict": type("PipelineVerdict", (), {}),
        "persist_resume_cursor": lambda *args, **kwargs: None,
        "read_resume_cursor": lambda *args, **kwargs: None,
        "EvidenceArtifactRef": type("EvidenceArtifactRef", (), {}),
        "Provenance": _Provenance,
        "Freshness": _Freshness,
        "StepResult": _StepResult,
        "StepInvocationAdapter": type("StepInvocationAdapter", (), {}),
        "StepInvocationAdapterRegistry": type("StepInvocationAdapterRegistry", (), {}),
        "ContentValidatorRegistry": type("ContentValidatorRegistry", (), {}),
        "no_op_content_validator": lambda *args, **kwargs: None,
    }
    for name, value in exports.items():
        setattr(pipeline, name, value)

    fake_arnold = types.ModuleType("arnold")
    fake_arnold.pipeline = pipeline
    monkeypatch.setitem(sys.modules, "arnold", fake_arnold)
    monkeypatch.setitem(sys.modules, "arnold.pipeline", pipeline)


@pytest.fixture(autouse=True)
def _clean_modules_fixture() -> None:
    _clear_modules()
    yield
    _clear_modules()


def test_on_step_start_rejects_stale_or_wrong_writer_and_projects_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch)
    hooks_module = importlib.import_module("astrid.core.integrations.arnold.host.hooks")

    run_root = tmp_path / "run-1"
    run_root.mkdir()
    write_lease_init(run_root, session_id="session-1", plan_hash="plan-123")

    hooks = hooks_module.ArnoldExecutorHooks()
    original_extensions = {
        "existing": {"keep": True},
        hooks_module.ASTRID_HOOK_NAMESPACE: {
            hooks_module.LEASE_EXTENSION_KEY: {
                "attached_session_id": "session-1",
                "writer_epoch": 0,
            }
        },
    }
    ctx = _StepContext(
        artifact_root=str(run_root),
        state={},
        inputs={"prompt": "hello"},
        hook_extensions=original_extensions,
    )

    rewritten = hooks.on_step_start(stage=object(), ctx=ctx)

    assert rewritten is not ctx
    assert rewritten.inputs == ctx.inputs
    assert ctx.hook_extensions == original_extensions
    assert rewritten.hook_extensions["existing"] == {"keep": True}
    assert rewritten.hook_extensions["astrid"]["lease"] == {
        "attached_session_id": "session-1",
        "plan_hash": "plan-123",
        "writer_epoch": 0,
    }

    stale_ctx = _StepContext(
        artifact_root=str(run_root),
        state={},
        hook_extensions={
            hooks_module.ASTRID_HOOK_NAMESPACE: {
                hooks_module.LEASE_EXTENSION_KEY: {
                    "attached_session_id": "session-1",
                    "writer_epoch": 1,
                }
            }
        },
    )
    with pytest.raises(hooks_module.ArnoldLeaseContractError, match="writer_epoch"):
        hooks.on_step_start(stage=object(), ctx=stale_ctx)

    wrong_writer_ctx = _StepContext(
        artifact_root=str(run_root),
        state={},
        hook_extensions={
            hooks_module.ASTRID_HOOK_NAMESPACE: {
                hooks_module.LEASE_EXTENSION_KEY: {
                    "attached_session_id": "session-2",
                    "writer_epoch": 0,
                }
            }
        },
    )
    with pytest.raises(hooks_module.ArnoldLeaseContractError, match="attached_session_id"):
        hooks.on_step_start(stage=object(), ctx=wrong_writer_ctx)


def test_on_step_end_maps_produces_failure_to_failed_contract_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch)
    hooks_module = importlib.import_module("astrid.core.integrations.arnold.host.hooks")

    run_root = tmp_path / "run-2"
    run_root.mkdir()
    hooks = hooks_module.ArnoldExecutorHooks()
    ctx = _StepContext(
        artifact_root=str(run_root),
        state={},
        hook_extensions={
            hooks_module.ASTRID_HOOK_NAMESPACE: {
                hooks_module.PRODUCES_EXTENSION_KEY: (
                    ProducesEntry(name="summary", path="summary.json", check=json_file()),
                )
            }
        },
    )
    result = _StepResult(
        outputs={"summary": "summary.json"},
        contract_result=_ContractResult(payload={"preexisting": True}),
    )

    rewritten = hooks.on_step_end(stage=object(), ctx=ctx, result=result)

    assert rewritten.contract_result is not None
    assert rewritten.contract_result.status == _ContractStatus.FAILED
    assert rewritten.contract_result.payload["preexisting"] is True
    assert rewritten.contract_result.payload["kind"] == "produces_check_failed"
    assert rewritten.contract_result.payload["produces_name"] == "summary"
    assert rewritten.contract_result.payload["check_id"] == "json_file"
    assert "does not exist" in rewritten.contract_result.payload["reason"]
    assert rewritten.contract_result.authority_level == "verified"


def test_on_step_end_maps_produces_pass_to_completed_contract_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch)
    hooks_module = importlib.import_module("astrid.core.integrations.arnold.host.hooks")

    run_root = tmp_path / "run-3"
    run_root.mkdir()
    artifact = run_root / "artifact.txt"
    artifact.write_text("ready\n", encoding="utf-8")

    hooks = hooks_module.ArnoldExecutorHooks()
    ctx = _StepContext(
        artifact_root=str(run_root),
        state={},
        hook_extensions={
            hooks_module.ASTRID_HOOK_NAMESPACE: {
                hooks_module.PRODUCES_EXTENSION_KEY: (
                    ProducesEntry(name="artifact", path="artifact.txt", check=file_nonempty()),
                )
            }
        },
    )
    result = _StepResult(outputs={"artifact": "artifact.txt"})

    rewritten = hooks.on_step_end(stage=object(), ctx=ctx, result=result)

    assert rewritten.contract_result is not None
    assert rewritten.contract_result.status == _ContractStatus.COMPLETED
    assert rewritten.contract_result.payload["kind"] == "produces_check_passed"
    assert rewritten.contract_result.payload["produces"] == [
        {
            "artifact_path": str(artifact),
            "check_id": "file_nonempty",
            "produces_name": "artifact",
        }
    ]


def test_should_suspend_returns_arnold_hook_tuple_when_contract_has_suspension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch)
    hooks_module = importlib.import_module("astrid.core.integrations.arnold.host.hooks")

    hooks = hooks_module.ArnoldExecutorHooks()
    result = _StepResult(
        contract_result=_ContractResult(
            status=_ContractStatus.SUSPENDED,
            suspension=_Suspension(
                resume_input_schema={
                    "type": "object",
                    "required": ["decision"],
                }
            ),
        )
    )

    assert hooks.should_suspend(stage=object(), state={"decision": {}}, result=result) == (
        True,
        "contract_result.suspension",
    )
    assert hooks.should_suspend(
        stage=object(),
        state={},
        result=_StepResult(contract_result=_ContractResult()),
    ) == (False, None)


@pytest.mark.parametrize(
    ("action", "expected_next"),
    [
        ("approve", "halt"),
        ("reject", "generate"),
    ],
)
def test_should_halt_loop_does_not_implement_approve_reject_routing(
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    expected_next: str,
) -> None:
    _install_fake_pipeline(monkeypatch)
    hooks_module = importlib.import_module("astrid.core.integrations.arnold.host.hooks")

    hooks = hooks_module.ArnoldExecutorHooks()
    state = {
        "human_input": {
            "decision": {
                "action": action,
                "notes": f"route via {expected_next}",
                "state_patch": {},
            }
        },
        "expected_next": expected_next,
    }

    assert hooks.should_halt_loop(stage=object(), state=state, iteration=3) == (False, None)
