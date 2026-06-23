from __future__ import annotations

import importlib
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from astrid.core.io.cas import canonical_json_digest


def _clear_host_modules() -> None:
    for name in (
        "astrid.core.integrations.arnold.host.envelope",
        "astrid.core.integrations.arnold.host.compat",
        "astrid.core.integrations.arnold.host",
        "astrid.core.integrations.arnold",
    ):
        sys.modules.pop(name, None)


@dataclass(frozen=True)
class _ResumeCursorRef:
    plugin_id: str
    run_id: str
    cursor: dict[str, Any]


@dataclass(frozen=True)
class _CrossCuttingEnvelope:
    taint: tuple[str, ...] = ()
    cost: dict[str, Any] = field(default_factory=dict)
    lineage: tuple[str, ...] = ()
    deadline: str | None = None
    cancellation: str | None = None
    retry_budget: dict[str, Any] = field(default_factory=dict)
    error_class: str | None = None


class _RuntimeEnvelope:
    run_id = ""
    artifact_root = ""
    resume_cursor = None
    cross_cutting = _CrossCuttingEnvelope()

    def __init__(
        self,
        *,
        plugin_id: str = "",
        manifest_hash: str = "",
        plugin_state_schema_version: int = 0,
        run_id: str = "",
        artifact_root: str = "",
        resume_cursor: _ResumeCursorRef | None = None,
        trust_state: str = "unknown",
        created_at: str = "",
        cross_cutting: _CrossCuttingEnvelope | None = None,
    ) -> None:
        self.plugin_id = plugin_id
        self.manifest_hash = manifest_hash
        self.plugin_state_schema_version = plugin_state_schema_version
        self.run_id = run_id
        self.artifact_root = artifact_root
        self.resume_cursor = resume_cursor
        self.trust_state = trust_state
        self.created_at = created_at
        self.cross_cutting = cross_cutting or _CrossCuttingEnvelope()


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
    inputs: dict[str, Any] | None = None
    hook_extensions: dict[str, Any] | None = None


@dataclass(frozen=True)
class _ContractResult:
    suspension: _Suspension | None = None


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
        "StepInvocation": type("StepInvocation", (), {}),
        "ContractResult": _ContractResult,
        "ContractStatus": type("ContractStatus", (), {}),
        "PipelineVerdict": type("PipelineVerdict", (), {}),
        "persist_resume_cursor": lambda *args, **kwargs: None,
        "read_resume_cursor": lambda artifact_root: _ResumeCursorRef(
            plugin_id="astrid.arnold.host",
            run_id=Path(artifact_root).name,
            cursor={"stage": "review"},
        ),
    }
    for name, value in exports.items():
        setattr(pipeline, name, value)

    fake_arnold = types.ModuleType("arnold")
    fake_arnold.pipeline = pipeline
    monkeypatch.setitem(sys.modules, "arnold", fake_arnold)
    monkeypatch.setitem(sys.modules, "arnold.pipeline", pipeline)


@pytest.fixture(autouse=True)
def _clean_host_modules_fixture() -> None:
    _clear_host_modules()
    yield
    _clear_host_modules()


def _seed_run(root: Path) -> Path:
    project_root = root / "demo"
    run_root = project_root / "runs" / "run-123"
    run_root.mkdir(parents=True)
    (project_root / "current_run.json").write_text(
        json.dumps({"run_id": "run-123"}),
        encoding="utf-8",
    )
    (run_root / "lease.json").write_text(
        json.dumps(
            {
                "writer_epoch": 7,
                "attached_session_id": "session-1",
                "plan_hash": "plan-abc",
                "timeline_id": "primary",
            }
        ),
        encoding="utf-8",
    )
    (run_root / "events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "kind": "run_started",
                        "ts": "2026-06-13T03:43:00Z",
                        "hash": "sha256:111",
                    }
                ),
                json.dumps(
                    {
                        "kind": "plan_initialized",
                        "ts": "2026-06-13T03:43:01Z",
                        "hash": "sha256:222",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return run_root


def test_project_runtime_envelope_reuses_astrid_run_identity_and_projects_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_host_modules()
    _install_fake_pipeline(monkeypatch)
    root = tmp_path / "projects"
    run_root = _seed_run(root)

    envelope_module = importlib.import_module("astrid.core.integrations.arnold.host.envelope")
    envelope = envelope_module.project_runtime_envelope(
        "demo",
        workflow_id="we.refine_image",
        root=root,
    )

    assert envelope.run_id == "run-123"
    assert envelope.artifact_root == str(run_root)
    assert envelope.resume_cursor == _ResumeCursorRef(
        plugin_id="astrid.arnold.host",
        run_id="run-123",
        cursor={"stage": "review"},
    )
    assert envelope.created_at == "2026-06-13T03:43:00Z"
    assert envelope.cross_cutting.lineage == ("sha256:111", "sha256:222")
    assert envelope.cross_cutting.cost == {
        "astrid": {
            "attached_session_id": "session-1",
            "plan_hash": "plan-abc",
            "writer_epoch": 7,
            "timeline_id": "primary",
        }
    }


def test_project_runtime_envelope_manifest_hash_is_deterministic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_host_modules()
    _install_fake_pipeline(monkeypatch)
    root = tmp_path / "projects"
    run_root = _seed_run(root)

    envelope_module = importlib.import_module("astrid.core.integrations.arnold.host.envelope")
    manifest = envelope_module.project_envelope_manifest(
        "demo",
        workflow_id="we.refine_image",
        root=root,
    )
    envelope_a = envelope_module.project_runtime_envelope(
        "demo",
        workflow_id="we.refine_image",
        root=root,
    )
    envelope_b = envelope_module.project_runtime_envelope(
        "demo",
        workflow_id="we.refine_image",
        root=root,
    )

    assert manifest == {
        "artifact_root": str(run_root),
        "lease": {
            "attached_session_id": "session-1",
            "plan_hash": "plan-abc",
            "writer_epoch": 7,
            "timeline_id": "primary",
        },
        "lineage": ["sha256:111", "sha256:222"],
        "plugin_id": "astrid.arnold.host",
        "plugin_state_schema_version": 1,
        "project_slug": "demo",
        "run_id": "run-123",
        "workflow_id": "we.refine_image",
    }
    assert envelope_a.manifest_hash == canonical_json_digest(manifest)
    assert envelope_b.manifest_hash == envelope_a.manifest_hash
