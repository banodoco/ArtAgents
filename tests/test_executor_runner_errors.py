"""Parametrized error-path tests for ``astrid.core.executor.runner``.

The happy paths for the executor runner are covered by
``tests/test_project_runs.py`` and ``tests/test_task_kernel_dispatch.py``.
This module exercises every ``raise ExecutorRunnerError(...)`` site in
``astrid/core/executor/runner.py`` plus the real subprocess failure modes
of ``_run_external_executor`` (nonzero exit, missing executable, env-var
propagation, cwd propagation).
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from astrid.contracts.schema import CommandInputArg, CommandSpec, Output, Port
from astrid.core.executor.cli import main as executor_cli_main
from astrid.core.executor.registry import ExecutorRegistry
from astrid.core.executor.runner import (
    ExecutorRunRequest,
    ExecutorRunnerError,
    build_executor_command,
    evaluate_conditions,
    run_executor,
)
from astrid.core.executor.registry import load_default_registry
from astrid.core.executor.schema import ConditionSpec, ExecutorDefinition


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _executor(
    *,
    executor_id: str = "test.exec",
    argv: tuple[str, ...] | None = (sys.executable, "-c", "pass"),
    inputs: tuple[Port, ...] = (),
    outputs: tuple[Output, ...] = (),
    conditions: tuple[ConditionSpec, ...] = (),
    metadata: dict[str, Any] | None = None,
    kind: str = "external",
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> ExecutorDefinition:
    command: CommandSpec | None
    if argv is None:
        command = None
    else:
        command = CommandSpec(argv=argv, cwd=cwd, env=env or {})
    return ExecutorDefinition(
        id=executor_id,
        name="Test Executor",
        kind=kind,
        version="1.0",
        inputs=inputs,
        outputs=outputs,
        command=command,
        conditions=conditions,
        metadata=metadata or {},
    )


def _registry(executor: ExecutorDefinition) -> ExecutorRegistry:
    registry = ExecutorRegistry()
    # Bypass full validation for some intentionally malformed fixtures.
    registry._executors[executor.id] = executor  # type: ignore[attr-defined]
    return registry


def test_command_input_args_expand_repeated_and_optional_values_in_order(tmp_path: Path) -> None:
    executor = _executor(
        inputs=(Port(name="item", required=True), Port(name="note", required=False)),
        argv=("echo", "fixed"),
    )
    executor = ExecutorDefinition(
        **{
            **executor.__dict__,
            "command": CommandSpec(
                argv=("echo", "fixed"),
                input_args=(
                    CommandInputArg(input="item", flag="--item", repeatable=True),
                    CommandInputArg(input="note", flag="--note", optional=True),
                ),
            ),
        }
    )

    command = build_executor_command(
        ExecutorRunRequest(
            executor_id=executor.id,
            out=tmp_path,
            inputs={"item": ["one", "two"]},
        ),
        _registry(executor),
    )

    assert command == ("echo", "fixed", "--item", "one", "--item", "two")


def test_command_input_args_reject_duplicate_values_without_repeatability(tmp_path: Path) -> None:
    executor = _executor(
        inputs=(Port(name="item", required=True),),
        argv=("echo",),
    )
    executor = ExecutorDefinition(
        **{
            **executor.__dict__,
            "command": CommandSpec(
                argv=("echo",),
                input_args=(CommandInputArg(input="item", flag="--item"),),
            ),
        }
    )

    with pytest.raises(ExecutorRunnerError, match="not repeatable"):
        build_executor_command(
            ExecutorRunRequest(executor_id=executor.id, out=tmp_path, inputs={"item": ["one", "two"]}),
            _registry(executor),
        )


def test_builtin_render_expands_semantic_timeline_assets_and_out_argv(tmp_path: Path) -> None:
    command = build_executor_command(
        ExecutorRunRequest(
            executor_id="builtin.render",
            out=tmp_path / "render",
            inputs={
                "timeline": tmp_path / "hype.timeline.json",
                "assets_registry": tmp_path / "hype.assets.json",
            },
            python_exec="/opt/python",
        ),
        load_default_registry(),
    )

    assert command == (
        "/opt/python",
        "-m",
        "astrid.packs.builtin.executors.render.run",
        "--timeline",
        str(tmp_path / "hype.timeline.json"),
        "--assets",
        str(tmp_path / "hype.assets.json"),
        "--out",
        str((tmp_path / "render").resolve() / "hype.mp4"),
    )


def test_builtin_render_rejects_legacy_assets_input_name(tmp_path: Path) -> None:
    with pytest.raises(ExecutorRunnerError, match="missing required input\\(s\\): assets_registry"):
        build_executor_command(
            ExecutorRunRequest(
                executor_id="builtin.render",
                out=tmp_path / "render",
                inputs={
                    "timeline": tmp_path / "hype.timeline.json",
                    "assets": tmp_path / "hype.assets.json",
                },
                python_exec="/opt/python",
            ),
            load_default_registry(),
        )


def test_builtin_render_omits_optional_theme_when_not_supplied_and_forwards_when_supplied(
    tmp_path: Path,
) -> None:
    registry = load_default_registry()
    base_request = ExecutorRunRequest(
        executor_id="builtin.render",
        out=tmp_path / "render",
        inputs={
            "timeline": "timeline.json",
            "assets_registry": "assets.json",
        },
        python_exec="/opt/python",
    )
    assert "--theme" not in build_executor_command(base_request, registry)

    themed = build_executor_command(
        ExecutorRunRequest(
            executor_id="builtin.render",
            out=tmp_path / "render",
            inputs={
                "timeline": "timeline.json",
                "assets_registry": "assets.json",
                "theme": "theme.json",
            },
            python_exec="/opt/python",
        ),
        registry,
    )
    assert themed[-2:] == ("--theme", "theme.json")


def test_executors_run_rejects_arbitrary_passthrough_after_double_dash() -> None:
    with pytest.raises(SystemExit):
        executor_cli_main(["run", "local.echo", "--", "--surprise"])


# ---------------------------------------------------------------------------
# Required-inputs / placeholders / no-command branches
# ---------------------------------------------------------------------------


def test_run_executor_rejects_missing_required_input(tmp_path: Path) -> None:
    executor = _executor(
        executor_id="test.requires_input",
        inputs=(Port(name="needed", type="string", required=True),),
    )
    registry = _registry(executor)

    with pytest.raises(ExecutorRunnerError, match="missing required input"):
        run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)


def test_run_executor_rejects_unknown_placeholder(tmp_path: Path) -> None:
    executor = _executor(
        executor_id="test.bad_placeholder",
        argv=(sys.executable, "-c", "pass", "{nope}"),
    )
    registry = _registry(executor)

    with pytest.raises(ExecutorRunnerError, match=r"missing value for placeholder \{nope\}"):
        run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)


def test_run_executor_rejects_missing_command_spec(tmp_path: Path) -> None:
    executor = _executor(executor_id="test.no_command", argv=None)
    registry = _registry(executor)

    with pytest.raises(ExecutorRunnerError, match="has no command"):
        run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)


# ---------------------------------------------------------------------------
# Conditions — every branch in _evaluate_condition
# ---------------------------------------------------------------------------


def test_condition_requires_input_when_absent() -> None:
    executor = _executor(
        executor_id="test.cond_requires_input",
        conditions=(ConditionSpec(kind="requires_input", input="needed"),),
    )
    with pytest.raises(ExecutorRunnerError, match="condition requires input 'needed'"):
        evaluate_conditions(executor, {})


def test_condition_requires_file_without_candidate() -> None:
    executor = _executor(
        executor_id="test.cond_requires_file_no_path",
        conditions=(ConditionSpec(kind="requires_file", input=None, path=None),),
    )
    with pytest.raises(ExecutorRunnerError, match="condition requires a file path"):
        evaluate_conditions(executor, {})


def test_condition_requires_file_when_path_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.txt"
    executor = _executor(
        executor_id="test.cond_requires_file_missing",
        conditions=(ConditionSpec(kind="requires_file", path=str(missing)),),
    )
    with pytest.raises(ExecutorRunnerError, match="condition requires file:"):
        evaluate_conditions(executor, {})


def test_condition_unsupported_kind() -> None:
    executor = _executor(
        executor_id="test.cond_unknown",
        conditions=(ConditionSpec(kind="bogus_kind"),),
    )
    with pytest.raises(ExecutorRunnerError, match="unsupported condition kind 'bogus_kind'"):
        evaluate_conditions(executor, {})


# ---------------------------------------------------------------------------
# Built-in / pipeline_step metadata errors
# ---------------------------------------------------------------------------


def test_builtin_executor_missing_pipeline_step_metadata(tmp_path: Path) -> None:
    executor = _executor(
        executor_id="test.builtin_no_step",
        argv=None,
        kind="built_in",
        metadata={"pipeline_step": 12345},  # not a string
    )
    registry = _registry(executor)

    with pytest.raises(ExecutorRunnerError, match="missing metadata.pipeline_step"):
        run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)


def test_builtin_executor_unknown_pipeline_step(tmp_path: Path) -> None:
    executor = _executor(
        executor_id="test.builtin_unknown_step",
        argv=None,
        kind="built_in",
        metadata={"pipeline_step": "definitely_not_a_real_step"},
    )
    registry = _registry(executor)

    with pytest.raises(ExecutorRunnerError, match="unknown pipeline step"):
        run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)


# ---------------------------------------------------------------------------
# upload.youtube built-in — required input
# ---------------------------------------------------------------------------


def test_upload_youtube_requires_video_url(tmp_path: Path) -> None:
    executor = _executor(executor_id="upload.youtube", argv=None)
    registry = _registry(executor)

    with pytest.raises(ExecutorRunnerError, match="video_url is required"):
        run_executor(ExecutorRunRequest(executor_id="upload.youtube", out=tmp_path), registry)


# ---------------------------------------------------------------------------
# build_executor_command — exercises some of the same error paths
# ---------------------------------------------------------------------------


def test_build_executor_command_rejects_missing_required_input(tmp_path: Path) -> None:
    executor = _executor(
        executor_id="test.bec_missing",
        inputs=(Port(name="needed", type="string", required=True),),
    )
    registry = _registry(executor)
    with pytest.raises(ExecutorRunnerError, match="missing required input"):
        build_executor_command(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)


# ---------------------------------------------------------------------------
# _run_external_executor — REAL subprocess invocations (no mocking).
# ---------------------------------------------------------------------------


def test_external_executor_captures_nonzero_returncode(tmp_path: Path) -> None:
    executor = _executor(
        executor_id="test.subprocess_exit_2",
        argv=(sys.executable, "-c", "import sys; sys.exit(2)"),
    )
    registry = _registry(executor)

    result = run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)

    assert result.returncode == 2
    assert result.ok is False
    assert result.payload["returncode"] == 2


def test_external_executor_returncode_zero_is_ok(tmp_path: Path) -> None:
    executor = _executor(
        executor_id="test.subprocess_exit_0",
        argv=(sys.executable, "-c", "pass"),
    )
    registry = _registry(executor)

    result = run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)

    assert result.returncode == 0
    assert result.ok is True


def test_external_executor_missing_executable_raises_oserror(tmp_path: Path) -> None:
    # subprocess.run with check=False still raises FileNotFoundError / OSError
    # when the executable cannot be located.
    executor = _executor(
        executor_id="test.missing_binary",
        argv=("definitely-not-a-real-binary-12345",),
    )
    registry = _registry(executor)

    with pytest.raises(FileNotFoundError):
        run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)


def test_external_executor_env_includes_definition_env(tmp_path: Path) -> None:
    # The runner merges os.environ with executor.command.env. Verify a custom
    # env entry actually reaches the subprocess.
    out_file = tmp_path / "env.txt"
    script = textwrap.dedent(
        """
        import os, sys
        from pathlib import Path
        Path(sys.argv[1]).write_text(os.environ.get('ASTRID_TEST_RUNNER_ENV', ''), encoding='utf-8')
        """
    )
    executor = _executor(
        executor_id="test.env_passthrough",
        argv=(sys.executable, "-c", script, str(out_file)),
        env={"ASTRID_TEST_RUNNER_ENV": "from-executor"},
    )
    registry = _registry(executor)

    result = run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)

    assert result.returncode == 0
    assert out_file.read_text(encoding="utf-8") == "from-executor"


def test_external_executor_env_inherits_os_environ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASTRID_TEST_RUNNER_INHERITED", "from-parent")
    out_file = tmp_path / "inherited.txt"
    script = textwrap.dedent(
        """
        import os, sys
        from pathlib import Path
        Path(sys.argv[1]).write_text(os.environ.get('ASTRID_TEST_RUNNER_INHERITED', ''), encoding='utf-8')
        """
    )
    executor = _executor(
        executor_id="test.env_inherits",
        argv=(sys.executable, "-c", script, str(out_file)),
    )
    registry = _registry(executor)

    result = run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)

    assert result.returncode == 0
    assert out_file.read_text(encoding="utf-8") == "from-parent"


def test_external_executor_definition_env_overrides_os_environ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The runner spreads os.environ then executor env: dict literal ordering
    # means executor env wins.
    monkeypatch.setenv("ASTRID_TEST_RUNNER_OVERRIDE", "from-parent")
    out_file = tmp_path / "override.txt"
    script = textwrap.dedent(
        """
        import os, sys
        from pathlib import Path
        Path(sys.argv[1]).write_text(os.environ.get('ASTRID_TEST_RUNNER_OVERRIDE', ''), encoding='utf-8')
        """
    )
    executor = _executor(
        executor_id="test.env_override",
        argv=(sys.executable, "-c", script, str(out_file)),
        env={"ASTRID_TEST_RUNNER_OVERRIDE": "from-executor"},
    )
    registry = _registry(executor)

    result = run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)

    assert result.returncode == 0
    assert out_file.read_text(encoding="utf-8") == "from-executor"


def test_external_executor_uses_command_cwd(tmp_path: Path) -> None:
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    out_file = tmp_path / "cwd.txt"
    script = textwrap.dedent(
        """
        import os, sys
        from pathlib import Path
        Path(sys.argv[1]).write_text(os.getcwd(), encoding='utf-8')
        """
    )
    executor = _executor(
        executor_id="test.cwd_propagation",
        argv=(sys.executable, "-c", script, str(out_file)),
        cwd=str(workdir),
    )
    registry = _registry(executor)

    result = run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)

    assert result.returncode == 0
    assert Path(out_file.read_text(encoding="utf-8")) == workdir.resolve()


# ---------------------------------------------------------------------------
# Unknown executor id — registry contract
# ---------------------------------------------------------------------------


def test_unknown_executor_id_raises_key_error(tmp_path: Path) -> None:
    registry = ExecutorRegistry()
    with pytest.raises(KeyError, match="unknown executor id"):
        run_executor(ExecutorRunRequest(executor_id="nope.nada", out=tmp_path), registry)
