"""Regression rails for the zero-shim execution and source-pack cutover."""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_in_process_runtime_and_pack_install_authority_are_absent() -> None:
    assert not (ROOT / "astrid/core/runtime/in_process.py").exists()
    for path in (
        "astrid/core/pack/store.py",
        "astrid/core/pack/install.py",
        "astrid/core/pack/install_cli.py",
        "astrid/core/pack/install_git.py",
        "astrid/core/pack/install_local.py",
        "astrid/core/pack/install_trust.py",
    ):
        assert not (ROOT / path).exists()

    import astrid.core.runtime as runtime

    assert not hasattr(runtime, "invoke_in_process_command")
    assert not hasattr(runtime, "InProcessResult")


def test_run_requests_have_no_mutable_execution_mode() -> None:
    from astrid.core.execution.executor.runner import ExecutorRunRequest
    from astrid.core.execution.orchestrator.runner import OrchestratorRunRequest

    assert "execution_mode" not in ExecutorRunRequest.__dataclass_fields__
    assert "execution_mode" not in OrchestratorRunRequest.__dataclass_fields__

    with pytest.raises(TypeError):
        ExecutorRunRequest(executor_id="x", out=None, execution_mode="in_process")


def test_public_discovery_has_no_installed_switch() -> None:
    import astrid
    from astrid.core.pack.discovery import discover_pack_metadata

    assert "include_installed" not in inspect.signature(astrid.discover).parameters
    assert "include_installed" not in inspect.signature(discover_pack_metadata).parameters


def test_source_discovery_ignores_user_pack_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astrid.core.pack.discovery import discover_pack_metadata

    user_store = tmp_path / ".astrid" / "packs"
    pack = user_store / "shadow"
    pack.mkdir(parents=True)
    (pack / "pack.yaml").write_text(
        "id: shadow\nname: Shadow\nversion: 1.0.0\n", encoding="utf-8"
    )
    monkeypatch.setenv("ASTRID_HOME", str(tmp_path / ".astrid"))
    discovered = discover_pack_metadata(project_root=tmp_path)
    assert all(item.id != "shadow" for item in discovered)


def test_schema_rejects_in_process_isolation_mode() -> None:
    from astrid.core.execution.executor.schema import ExecutorValidationError, validate_executor_definition

    with pytest.raises(ExecutorValidationError):
        validate_executor_definition(
            {
                "id": "demo.run",
                "name": "Demo",
                "kind": "external",
                "version": "1.0.0",
                "command": ["python3", "-c", "pass"],
                "isolation": {"mode": "in_process"},
            }
        )


def test_external_executor_command_always_crosses_subprocess_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astrid.core.contracts.schema import CommandSpec
    from astrid.core.execution.executor import runner
    from astrid.core.execution.executor.schema import ExecutorDefinition

    definition = ExecutorDefinition(
        id="demo.executor",
        name="Demo",
        kind="external",
        version="1.0.0",
        command=CommandSpec(argv=("python3", "-c", "pass")),
    )
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[object]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0] if args else [], 0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    result = runner._run_explicit_command_executor(
        definition,
        runner.ExecutorRunRequest(executor_id=definition.id, out=tmp_path),
        {},
    )

    assert result.returncode == 0
    assert calls and calls[0][0][0] == ["python3", "-c", "pass"]


def test_python_orchestrator_always_uses_subprocess_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astrid.core.execution.orchestrator import runner
    from astrid.core.execution.orchestrator.schema import (
        OrchestratorDefinition,
        RuntimeSpec,
    )

    definition = OrchestratorDefinition(
        id="demo.orchestrator",
        name="Demo",
        kind="external",
        version="1.0.0",
        runtime=RuntimeSpec(kind="python", module="demo.module", function="run"),
    )
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[object]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0] if args else [], 1, stderr="worker failed")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    with pytest.raises(runner.OrchestratorRunnerError, match="failed in subprocess"):
        runner._run_python_orchestrator_subprocess(
            definition,
            runner.OrchestratorRunRequest(
                orchestrator_id=definition.id,
                out=tmp_path,
                run_root=tmp_path,
            ),
        )

    assert calls
    assert calls[0][0][0][0:3] == [runner.sys.executable, "-m", "astrid.core.execution.python_runtime_worker"]
