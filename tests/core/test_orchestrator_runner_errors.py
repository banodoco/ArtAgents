"""Parametrized error-path tests for ``astrid.core.execution.orchestrator.runner``.

The happy paths for the orchestrator runner are covered by
``tests/core/test_project_runs.py`` and ``tests/test_task_kernel_dispatch.py``.
This module exercises every ``raise OrchestratorRunnerError(...)`` site
in ``astrid/core/orchestrator/runner.py`` with a minimal direct call.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from astrid.core.contracts.schema import CommandSpec, IsolationMetadata, Output, Port
from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
from astrid.core.execution.orchestrator.runner import (
    OrchestratorRunnerError,
    OrchestratorRunRequest,
    build_orchestrator_command,
    run_orchestrator,
)
from astrid.core.execution.orchestrator.schema import OrchestratorDefinition, RuntimeSpec
from astrid.core.foundation import project_paths


@pytest.fixture(autouse=True)
def _isolate_non_project_runner_error_paths(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Keep this module focused on non-project runner branches.

    Project enforcement has dedicated conformance tests. The legacy tests in
    this module intentionally construct minimal projectless requests to reach
    lower-level runtime validation branches.
    """

    if request.node.name == "test_orchestrator_out_only_requires_project":
        return
    from astrid.core.execution.orchestrator import runner as runner_module

    monkeypatch.setattr(
        runner_module,
        "_resolve_project_request",
        lambda run_request, _definition: run_request,
    )


# ---------------------------------------------------------------------------
# Factory helpers — keep orchestrators in-memory so tests stay hermetic.
# ---------------------------------------------------------------------------


def _command_orchestrator(
    *,
    orchestrator_id: str = "test.command",
    argv: tuple[str, ...] = (sys.executable, "-c", "pass"),
    inputs: tuple[Port, ...] = (),
    outputs: tuple[Output, ...] = (),
    metadata: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
    isolation: IsolationMetadata | None = None,
) -> OrchestratorDefinition:
    return OrchestratorDefinition(
        id=orchestrator_id,
        name="Command Orchestrator",
        kind="built_in",
        version="1.0",
        runtime=RuntimeSpec(kind="command", command=CommandSpec(argv=argv, env=env or {})),
        inputs=inputs,
        outputs=outputs,
        isolation=isolation or IsolationMetadata(),
        metadata=metadata or {},
    )


def _python_orchestrator(
    *,
    orchestrator_id: str = "test.python",
    module: str | None = "astrid.core.execution.orchestrator.runner",
    function: str | None = "_request_argv_for_gate",
) -> OrchestratorDefinition:
    return OrchestratorDefinition(
        id=orchestrator_id,
        name="Python Orchestrator",
        kind="built_in",
        version="1.0",
        runtime=RuntimeSpec(kind="python", module=module, function=function),
    )


def _registry(definition: OrchestratorDefinition) -> OrchestratorRegistry:
    return OrchestratorRegistry([definition])


def _unvalidated_registry(definition: OrchestratorDefinition) -> OrchestratorRegistry:
    """Insert an intentionally-malformed definition without going through schema validation.

    Several error-path tests need to exercise branches that the public
    OrchestratorRegistry constructor would reject up front (e.g. command=None,
    unknown runtime kinds). Mutating the private dict is the cleanest way to
    reach those branches; centralising the type-ignore keeps the call sites tidy.
    """

    registry = OrchestratorRegistry()
    registry._orchestrators[definition.id] = definition  # type: ignore[attr-defined]
    return registry


def _require_timeline_schema() -> None:
    """Skip project/timeline fixtures when the optional shared schema is absent."""
    pytest.importorskip("banodoco_timeline_schema")


# ---------------------------------------------------------------------------
# build_orchestrator_command — error paths
# ---------------------------------------------------------------------------


def test_build_orchestrator_command_rejects_non_command_runtime(tmp_path: Path) -> None:
    orch = _python_orchestrator()
    registry = _registry(orch)
    request = OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path)

    with pytest.raises(OrchestratorRunnerError, match="does not use a command runtime"):
        build_orchestrator_command(request, registry)


# ---------------------------------------------------------------------------
# _validate_out_requirement — three distinct error messages
# ---------------------------------------------------------------------------


def test_run_orchestrator_requires_out_when_metadata_demands_output_path() -> None:
    orch = _command_orchestrator(metadata={"requires_output_path": True})
    registry = _registry(orch)

    with pytest.raises(OrchestratorRunnerError, match=r"--out is required for test\.command"):
        run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id), registry)


def test_run_orchestrator_requires_out_for_command_runtime_placeholders() -> None:
    orch = _command_orchestrator(argv=(sys.executable, "-c", "pass", "{out}"))
    registry = _registry(orch)

    with pytest.raises(OrchestratorRunnerError, match="--out is required for command runtime placeholders"):
        run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id), registry)


def test_run_orchestrator_requires_out_for_execution() -> None:
    # A python orchestrator with no out and not dry_run hits the generic
    # "--out is required for orchestrator execution" branch.
    orch = _python_orchestrator()
    registry = _registry(orch)

    with pytest.raises(OrchestratorRunnerError, match="--out is required for orchestrator execution"):
        run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id), registry)


# ---------------------------------------------------------------------------
# _validate_required_inputs
# ---------------------------------------------------------------------------


def test_run_orchestrator_rejects_missing_required_input(tmp_path: Path) -> None:
    orch = _command_orchestrator(
        inputs=(Port(name="needed", type="string", required=True),),
    )
    registry = _registry(orch)
    request = OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path)

    with pytest.raises(OrchestratorRunnerError, match="missing required input"):
        run_orchestrator(request, registry)


def test_command_orchestrator_preserves_declared_passthrough_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASTRID_TEST_ORCH_PUBLIC", "from-parent")
    out_file = tmp_path / "passthrough.txt"
    script = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "Path(sys.argv[1]).write_text(os.environ.get('ASTRID_TEST_ORCH_PUBLIC', ''), encoding='utf-8')\n"
    )
    orch = _command_orchestrator(
        argv=(sys.executable, "-c", script, str(out_file)),
        isolation=IsolationMetadata(env_passthrough=("ASTRID_TEST_ORCH_PUBLIC",)),
    )
    registry = _registry(orch)

    result = run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path), registry)

    assert result.returncode == 0
    assert out_file.read_text(encoding="utf-8") == "from-parent"


def test_command_orchestrator_does_not_spread_undeclared_host_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASTRID_TEST_ORCH_UNDECLARED", "from-parent")
    out_file = tmp_path / "undeclared.txt"
    script = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "Path(sys.argv[1]).write_text(os.environ.get('ASTRID_TEST_ORCH_UNDECLARED', ''), encoding='utf-8')\n"
    )
    orch = _command_orchestrator(argv=(sys.executable, "-c", script, str(out_file)))
    registry = _registry(orch)

    result = run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path), registry)

    assert result.returncode == 0
    assert out_file.read_text(encoding="utf-8") == ""


def test_command_orchestrator_explicit_env_overrides_passthrough(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASTRID_TEST_ORCH_OVERRIDE", "from-parent")
    out_file = tmp_path / "override.txt"
    script = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "Path(sys.argv[1]).write_text(os.environ.get('ASTRID_TEST_ORCH_OVERRIDE', ''), encoding='utf-8')\n"
    )
    orch = _command_orchestrator(
        argv=(sys.executable, "-c", script, str(out_file)),
        env={"ASTRID_TEST_ORCH_OVERRIDE": "from-orchestrator"},
        isolation=IsolationMetadata(env_passthrough=("ASTRID_TEST_ORCH_OVERRIDE",)),
    )
    registry = _registry(orch)

    result = run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path), registry)

    assert result.returncode == 0
    assert out_file.read_text(encoding="utf-8") == "from-orchestrator"



def test_command_orchestrator_default_mode_remains_subprocess_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch = _command_orchestrator(
        orchestrator_id="test.subprocess_default",
        argv=(sys.executable, "-c", "pass"),
    )
    registry = _registry(orch)
    seen: dict[str, Any] = {}

    def _fake_subprocess_run(
        argv: list[str],
        *,
        cwd: str | None,
        env: dict[str, str],
        check: bool,
    ) -> types.SimpleNamespace:
        seen["argv"] = tuple(argv)
        seen["cwd"] = cwd
        seen["env"] = env
        seen["check"] = check
        return types.SimpleNamespace(returncode=0)

    import astrid.core.execution.orchestrator.runner as runner_mod

    monkeypatch.setattr(runner_mod.subprocess, "run", _fake_subprocess_run)

    result = run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path), registry)

    assert seen["argv"] == orch.runtime.command.argv
    assert seen["cwd"] is None
    assert seen["check"] is False
    assert result.returncode == 0
    assert result.ok is True



# Python runtime — every raise site in _run_python_orchestrator
# ---------------------------------------------------------------------------


def test_python_orchestrator_rejects_invalid_runtime_spec(tmp_path: Path) -> None:
    # Bypass validation by constructing OrchestratorDefinition directly with
    # an empty module to exercise the "invalid Python runtime" branch.
    orch = OrchestratorDefinition(
        id="test.invalid_python",
        name="Invalid Python",
        kind="built_in",
        version="1.0",
        runtime=RuntimeSpec(kind="python", module=None, function=None),
    )
    registry = _unvalidated_registry(orch)

    with pytest.raises(OrchestratorRunnerError, match="invalid Python runtime"):
        run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path), registry)


def test_python_orchestrator_reports_import_failure(tmp_path: Path) -> None:
    orch = _python_orchestrator(module="astrid.does_not_exist_definitely_xyz", function="run")
    registry = _registry(orch)

    with pytest.raises(OrchestratorRunnerError, match="Python runtime failed in subprocess"):
        run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path), registry)


def test_python_orchestrator_rejects_non_callable_target(tmp_path: Path) -> None:
    # __doc__ exists on every module but is a string — not callable.
    orch = _python_orchestrator(
        module="astrid.core.execution.orchestrator.runner",
        function="__doc__",
    )
    registry = _registry(orch)

    with pytest.raises(OrchestratorRunnerError, match="Python runtime failed in subprocess"):
        run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path), registry)


# ---------------------------------------------------------------------------
# _run_orchestrator_inner — unsupported runtime kind
# ---------------------------------------------------------------------------


def test_run_orchestrator_inner_rejects_unsupported_runtime_kind(tmp_path: Path) -> None:
    orch = OrchestratorDefinition(
        id="test.bogus_runtime",
        name="Bogus",
        kind="built_in",
        version="1.0",
        runtime=RuntimeSpec(kind="rust", module=None, function=None, command=None),
    )
    registry = _unvalidated_registry(orch)

    with pytest.raises(OrchestratorRunnerError, match="unsupported orchestrator runtime kind"):
        run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path), registry)


def test_command_runtime_with_none_command_raises(tmp_path: Path) -> None:
    # Construct a command-kind orchestrator with command=None to exercise the
    # "has no command runtime" branch in _expand_command_runtime.
    orch = OrchestratorDefinition(
        id="test.no_command",
        name="No Command",
        kind="built_in",
        version="1.0",
        runtime=RuntimeSpec(kind="command", command=None),
    )
    registry = _unvalidated_registry(orch)

    with pytest.raises(OrchestratorRunnerError, match="has no command runtime"):
        run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path), registry)


# ---------------------------------------------------------------------------
# Placeholder expansion
# ---------------------------------------------------------------------------


def test_command_orchestrator_rejects_unknown_placeholder(tmp_path: Path) -> None:
    orch = OrchestratorDefinition(
        id="test.unknown_placeholder",
        name="Unknown Placeholder",
        kind="built_in",
        version="1.0",
        runtime=RuntimeSpec(
            kind="command",
            command=CommandSpec(argv=(sys.executable, "-c", "pass", "{not_a_thing}")),
        ),
    )
    registry = _unvalidated_registry(orch)

    with pytest.raises(OrchestratorRunnerError, match=r"missing value for placeholder \{not_a_thing\}"):
        run_orchestrator(OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path), registry)


# ---------------------------------------------------------------------------
# Project + orchestrator combination rules
# ---------------------------------------------------------------------------


def test_project_orchestrator_rejects_passthrough_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    (tmp_path / "projects" / "demo").mkdir(parents=True, exist_ok=True)

    orch = _command_orchestrator(
        orchestrator_id="test.proj_passthrough",
        metadata={"requires_output_path": True},
    )
    registry = _registry(orch)

    with pytest.raises(
        OrchestratorRunnerError,
        match="--project cannot be combined with passthrough --out",
    ):
        run_orchestrator(
            OrchestratorRunRequest(
                orchestrator_id=orch.id,
                project="demo",
                orchestrator_args=("--out", "/tmp/manual"),
            ),
            registry,
        )


def test_command_orchestrator_dry_run_uses_placeholder_out_without_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require_timeline_schema()
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    (tmp_path / "projects" / "demo").mkdir(parents=True, exist_ok=True)

    orch = _command_orchestrator(
        orchestrator_id="video_editing.hype",
        argv=(sys.executable, "-c", "pass", "{orchestrator_args}"),
        metadata={"requires_output_path": True},
    )
    registry = _registry(orch)

    result = run_orchestrator(
        OrchestratorRunRequest(
            orchestrator_id=orch.id,
            project="demo",
            dry_run=True,
        ),
        registry,
    )

    assert result.dry_run is True
    assert "--out" in result.command
    assert str((Path.cwd() / ".astrid-dry-run" / "video_editing-hype").resolve()) in result.command
    assert list((tmp_path / "projects" / "demo" / "runs").glob("*")) == []


def test_orchestrator_out_only_requires_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require_timeline_schema()
    projects_root = tmp_path / "projects"
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(projects_root))
    (projects_root / "default").mkdir(parents=True, exist_ok=True)

    out_dir = tmp_path / "auto-orch-out"
    orch = _command_orchestrator(
        orchestrator_id="video_editing.hype",
        argv=(sys.executable, "-c", "pass", "{orchestrator_args}"),
        metadata={"requires_output_path": True},
    )
    registry = _registry(orch)

    with pytest.raises(OrchestratorRunnerError, match="project is required"):
        run_orchestrator(
            OrchestratorRunRequest(orchestrator_id=orch.id, out=out_dir),
            registry,
        )

    records = sorted((projects_root / "default" / "runs").glob("*/run.json"))
    assert records == []

# ---------------------------------------------------------------------------
# _output_value — dry-run placeholder out covers derived outputs
# ---------------------------------------------------------------------------


def test_output_derivation_uses_dry_run_placeholder_out(tmp_path: Path) -> None:
    # Dry-run now synthesizes a placeholder out directory before command/output
    # expansion, so derived outputs no longer fail just because no explicit
    # --out was supplied.
    orch = OrchestratorDefinition(
        id="test.output_needs_out",
        name="Output Needs Out",
        kind="built_in",
        version="1.0",
        runtime=RuntimeSpec(
            kind="command",
            command=CommandSpec(argv=(sys.executable, "-c", "pass")),
        ),
        outputs=(Output(name="result", type="path", mode="create"),),
    )
    registry = _unvalidated_registry(orch)

    result = run_orchestrator(
        OrchestratorRunRequest(orchestrator_id=orch.id, dry_run=True),
        registry,
    )

    assert result.dry_run is True


# ---------------------------------------------------------------------------
# _normalize_python_result / _plan_from_raw / _plan_step_from_raw /
# _planned_commands / _tuple_of_strings — exercised by the python runtime
# returning a dict.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_result", "expected_match"),
    [
        pytest.param(
            {"plan": "not-a-mapping"},
            "plan must be an object",
            id="plan-not-object",
        ),
        pytest.param(
            {"plan": {"steps": "not-a-list"}},
            r"plan\.steps must be a list",
            id="plan-steps-not-list",
        ),
        pytest.param(
            {"plan": {"steps": ["not-a-mapping"]}},
            r"plan\.steps\[0\] must be an object",
            id="plan-step-not-object",
        ),
        pytest.param(
            {"plan": {"steps": [{"id": ""}]}},
            r"plan\.steps\[0\]\.id must be a non-empty string",
            id="plan-step-empty-id",
        ),
        pytest.param(
            {"planned_commands": "not-a-list"},
            "planned_commands must be a list of command lists",
            id="planned-commands-not-list",
        ),
        pytest.param(
            {"command": "not-a-list"},
            "command must be a list",
            id="command-not-list",
        ),
        pytest.param(
            {"command": [123]},
            r"command\[0\] must be a string",
            id="command-item-not-string",
        ),
    ],
)
def test_python_runtime_dict_result_validation_errors(
    raw_result: dict[str, Any],
    expected_match: str,
    tmp_path: Path,
) -> None:
    import astrid.core.execution.orchestrator.runner as runner_mod
    orch = _python_orchestrator(function="_test_python_target")
    request = OrchestratorRunRequest(orchestrator_id=orch.id, out=tmp_path)

    with pytest.raises(OrchestratorRunnerError, match=expected_match):
        runner_mod._normalize_python_result(orch, request, raw_result)


# ---------------------------------------------------------------------------
# Unknown orchestrator id — registry.get raises KeyError (NOT a runner error).
# Verify the contract.
# ---------------------------------------------------------------------------


def test_unknown_orchestrator_id_raises_key_error(tmp_path: Path) -> None:
    registry = OrchestratorRegistry()
    with pytest.raises(KeyError, match="unknown orchestrator id"):
        run_orchestrator(
            OrchestratorRunRequest(orchestrator_id="nope.nada", out=tmp_path),
            registry,
        )
