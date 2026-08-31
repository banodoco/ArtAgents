"""Parametrized error-path tests for ``astrid.core.execution.executor.runner``.

The happy paths for the executor runner are covered by
``tests/core/test_project_runs.py`` and ``tests/test_task_kernel_dispatch.py``.
This module exercises every ``raise ExecutorRunnerError(...)`` site in
``astrid/core/executor/runner.py`` plus the real subprocess failure modes
of ``_run_external_executor`` (nonzero exit, missing executable, env-var
propagation, cwd propagation).
"""

from __future__ import annotations

import sys
import textwrap
import types
from pathlib import Path
from typing import Any, Mapping

import pytest

import astrid.packs
from astrid.core.contracts.schema import (
    CommandInputArg,
    CommandSpec,
    IsolationMetadata,
    Output,
    Port,
)
from astrid.core.execution.executor import runner as executor_runner
from astrid.core.execution.executor.argv import executor_argv
from astrid.core.execution.executor.registry import ExecutorRegistry, load_default_registry
from astrid.core.execution.executor.runner import (
    ExecutorRunnerError,
    ExecutorRunRequest,
    build_executor_command,
    evaluate_conditions,
    run_executor,
)
from astrid.core.execution.executor.schema import (
    ConditionSpec,
    ExecutorDefinition,
    ExecutorValidationError,
)
from astrid.core.io.cas import executor_definition_digest


@pytest.fixture(autouse=True)
def _isolate_non_project_runner_error_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep this module focused on non-project runner branches.

    Project enforcement has dedicated conformance tests. The legacy tests in
    this module intentionally construct minimal projectless requests to reach
    lower-level runtime validation branches, so the project-required gate is
    neutralized exactly as in ``test_orchestrator_runner_errors.py``.
    """

    monkeypatch.setattr(
        executor_runner,
        "_resolve_project_request",
        lambda run_request: run_request,
    )


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
    isolation: IsolationMetadata | None = None,
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
        isolation=isolation or IsolationMetadata(),
        metadata=metadata or {},
    )


def _registry(executor: ExecutorDefinition) -> ExecutorRegistry:
    registry = ExecutorRegistry()
    # Bypass full validation for some intentionally malformed fixtures.
    registry._executors[executor.id] = executor  # type: ignore[attr-defined]
    return registry


def _extend_packs_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    pack_root = tmp_path / "astrid" / "packs"
    pack_root.mkdir(parents=True)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(
        astrid.packs,
        "__path__",
        [str(pack_root), *list(astrid.packs.__path__)],
    )
    return pack_root


def test_admitted_executor_version_is_fenced_before_execution(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-run"
    executor = _executor(
        argv=(sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"),
    )
    actual = executor_definition_digest(executor)
    assert actual != "0" * 64

    with pytest.raises(ExecutorRunnerError, match="changed after admission"):
        run_executor(
            ExecutorRunRequest(
                executor_id=executor.id,
                out=tmp_path / "out",
                expected_executor_version="0" * 64,
            ),
            _registry(executor),
        )

    assert not marker.exists()


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
            executor_id="rendering.render",
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
        "astrid.packs.rendering.executors.render.run",
        "--timeline",
        str(tmp_path / "hype.timeline.json"),
        "--assets",
        str(tmp_path / "hype.assets.json"),
        "--out",
        str((tmp_path / "render").resolve() / "hype.mp4"),
    )


def test_builtin_render_omits_optional_assets_registry_when_absent(tmp_path: Path) -> None:
    command = build_executor_command(
        ExecutorRunRequest(
            executor_id="rendering.render",
            out=tmp_path / "render",
            inputs={
                "timeline": tmp_path / "hype.timeline.json",
            },
            python_exec="/opt/python",
        ),
        load_default_registry(),
    )

    assert command == (
        "/opt/python",
        "-m",
        "astrid.packs.rendering.executors.render.run",
        "--timeline",
        str(tmp_path / "hype.timeline.json"),
        "--out",
        str((tmp_path / "render").resolve() / "hype.mp4"),
    )


def test_builtin_render_does_not_treat_legacy_assets_input_as_assets_registry(tmp_path: Path) -> None:
    command = build_executor_command(
        ExecutorRunRequest(
            executor_id="rendering.render",
            out=tmp_path / "render",
            inputs={
                "timeline": tmp_path / "hype.timeline.json",
                "assets": tmp_path / "hype.assets.json",
            },
            python_exec="/opt/python",
        ),
        load_default_registry(),
    )

    assert "--assets" not in command


def test_builtin_render_omits_optional_theme_when_not_supplied_and_forwards_when_supplied(
    tmp_path: Path,
) -> None:
    registry = load_default_registry()
    base_request = ExecutorRunRequest(
        executor_id="rendering.render",
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
            executor_id="rendering.render",
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


# ---------------------------------------------------------------------------
# Auto-forward of untemplated declared inputs (the dropped-prompt bug fix)
# ---------------------------------------------------------------------------


def test_generate_image_auto_forwards_prompt_and_numeric_inputs(tmp_path: Path) -> None:
    """`--input prompt=...` reaches generate_image's run.py as `--prompt ...`.

    Regression for the bug where declared inputs that are neither a
    `{placeholder}` token nor an `input_args` mapping were silently dropped.
    """
    command = build_executor_command(
        ExecutorRunRequest(
            executor_id="generation.generate_image",
            out=tmp_path / "img",
            inputs={
                "model": "z-image",
                "mode": "t2i",
                "execution": "local",
                "prompt": "a red bicycle",
                "seed": "42",
                "steps": "30",
                "negative_prompt": "blurry",
                "guidance_scale": "7.5",
                "quality": "low",
                "background": "transparent",
                "timeout": "123",
            },
            python_exec="/opt/python",
        ),
        load_default_registry(),
    )

    # Forwarded value flags use kebab-cased input names.
    assert "--prompt" in command
    assert command[command.index("--prompt") + 1] == "a red bicycle"
    assert command[command.index("--seed") + 1] == "42"
    assert command[command.index("--steps") + 1] == "30"
    assert command[command.index("--negative-prompt") + 1] == "blurry"
    assert command[command.index("--guidance-scale") + 1] == "7.5"
    assert command[command.index("--quality") + 1] == "low"
    assert command[command.index("--background") + 1] == "transparent"
    assert command[command.index("--timeout") + 1] == "123"
    # Templated inputs are passed exactly once (not double-forwarded).
    for flag in ("--model", "--mode", "--execution", "--out"):
        assert command.count(flag) == 1
    # Untemplated inputs that were not supplied are omitted entirely.
    assert "--size" not in command
    assert "--strength" not in command


def test_generate_video_auto_forwards_prompt_and_frame_inputs(tmp_path: Path) -> None:
    command = build_executor_command(
        ExecutorRunRequest(
            executor_id="generation.generate_video",
            out=tmp_path / "vid",
            inputs={
                "model": "wan-2.2",
                "mode": "t2v",
                "execution": "local",
                "prompt": "a cat walking",
                "frames": "81",
                "fps": "16",
            },
            python_exec="/opt/python",
        ),
        load_default_registry(),
    )

    assert command[command.index("--prompt") + 1] == "a cat walking"
    assert command[command.index("--frames") + 1] == "81"
    assert command[command.index("--fps") + 1] == "16"
    for flag in ("--model", "--mode", "--execution", "--out"):
        assert command.count(flag) == 1


def test_auto_forward_does_not_double_pass_placeholder_or_input_arg_inputs(
    tmp_path: Path,
) -> None:
    """Inputs consumed by a placeholder or input_args mapping are not re-appended."""
    executor = _executor(
        executor_id="test.no_double",
        inputs=(
            Port(name="model", required=True, type="string"),
            Port(name="item", required=False, type="string"),
            Port(name="prompt", required=False, type="string"),
        ),
        argv=("run", "--model", "{model}"),
    )
    executor = ExecutorDefinition(
        **{
            **executor.__dict__,
            "command": CommandSpec(
                argv=("run", "--model", "{model}"),
                input_args=(CommandInputArg(input="item", flag="--item"),),
            ),
        }
    )

    command = build_executor_command(
        ExecutorRunRequest(
            executor_id=executor.id,
            out=tmp_path,
            inputs={"model": "z", "item": "thing", "prompt": "hi"},
        ),
        _registry(executor),
    )

    # `model` consumed by placeholder, `item` by input_args -> each once.
    assert command.count("--model") == 1
    assert command.count("--item") == 1
    # `prompt` is untemplated -> auto-forwarded once.
    assert command.count("--prompt") == 1
    assert command[command.index("--prompt") + 1] == "hi"


def test_auto_forward_boolean_input_emits_bare_flag_only_when_truthy(
    tmp_path: Path,
) -> None:
    def _build(value: str) -> tuple[str, ...]:
        executor = _executor(
            executor_id="test.boolflag",
            inputs=(Port(name="fake", required=False, type="boolean"),),
            argv=("run",),
        )
        return build_executor_command(
            ExecutorRunRequest(
                executor_id=executor.id,
                out=tmp_path,
                inputs={"fake": value},
            ),
            _registry(executor),
        )

    truthy = _build("true")
    assert "--fake" in truthy
    # Boolean flags never carry a value argument.
    assert truthy[-1] == "--fake"

    falsey = _build("false")
    assert "--fake" not in falsey


def test_auto_forward_respects_executor_metadata_opt_out(tmp_path: Path) -> None:
    executor = _executor(
        executor_id="test.optout",
        inputs=(Port(name="assets", required=False, type="file"),),
        argv=("run",),
        metadata={"auto_forward_inputs": False},
    )
    command = build_executor_command(
        ExecutorRunRequest(
            executor_id=executor.id,
            out=tmp_path,
            inputs={"assets": "/tmp/a.json"},
        ),
        _registry(executor),
    )
    assert "--assets" not in command


def test_executor_argv_resolves_canonical_id_and_bare_pipeline_step() -> None:
    assert executor_argv("rendering.render", "/opt/python") == [
        "/opt/python",
        "-m",
        "astrid.packs.rendering.executors.render.run",
    ]
    assert executor_argv("render", "/opt/python") == [
        "/opt/python",
        "-m",
        "astrid.packs.rendering.executors.render.run",
    ]
def test_executor_argv_rejects_non_pipeline_bare_name() -> None:
    with pytest.raises(ValueError, match="could not resolve executor step 'upload'"):
        executor_argv("upload", "/opt/python")


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
        metadata={
            "command_builder": "astrid.packs.video_editing.orchestrators.hype.run.build_pool_steps",
            "pipeline_step": 12345,  # not a string
        },
    )
    registry = _registry(executor)

    with pytest.raises(ExecutorRunnerError, match="missing metadata.pipeline_step"):
        run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)


def test_builtin_executor_unknown_pipeline_step(tmp_path: Path) -> None:
    executor = _executor(
        executor_id="test.builtin_unknown_step",
        argv=None,
        kind="built_in",
        metadata={
            "command_builder": "astrid.packs.video_editing.orchestrators.hype.run.build_pool_steps",
            "pipeline_step": "definitely_not_a_real_step",
        },
    )
    registry = _registry(executor)

    with pytest.raises(ExecutorRunnerError, match="unknown pipeline step"):
        run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)


# ---------------------------------------------------------------------------
def test_pipeline_module_derived_from_command_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_pipeline = types.SimpleNamespace()

    monkeypatch.setattr(
        executor_runner,
        "import_module",
        lambda name: fake_pipeline if name == "fake.pipeline" else None,
    )

    executor = types.SimpleNamespace(
        id="video_editing.cut",
        metadata={"command_builder": "fake.pipeline.build_pool_steps"},
    )

    executor_runner._pipeline_module.cache_clear()
    try:
        # Driver module derived from command_builder — no orchestrator registry lookup.
        assert executor_runner._pipeline_module_for_executor(executor) is fake_pipeline
        assert executor_runner._pipeline_module("fake.pipeline") is fake_pipeline
    finally:
        executor_runner._pipeline_module.cache_clear()


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


def test_nonzero_returncode_populates_exec_error(tmp_path: Path) -> None:
    executor = _executor(
        executor_id="test.exit_3_error",
        argv=(sys.executable, "-c", "import sys; sys.exit(3)"),
    )
    registry = _registry(executor)

    result = run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "nonzero_exit"
    assert result.error.type == "process"
    assert "3" in result.error.message


def test_missing_binary_run_surfaces_exec_error(tmp_path: Path) -> None:
    executor = _executor(
        executor_id="test.missing_binary_error",
        isolation=IsolationMetadata(binaries=("definitely-not-a-real-binary-12345",)),
    )
    registry = _registry(executor)

    result = run_executor(
        ExecutorRunRequest(executor_id=executor.id, out=tmp_path, check_binaries=True),
        registry,
    )

    assert result.ok is False
    assert result.missing_binaries == ("definitely-not-a-real-binary-12345",)
    assert result.error is not None
    assert result.error.code == "missing_binaries"
    assert result.error.type == "precondition"


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
        isolation=IsolationMetadata(env_passthrough=("ASTRID_TEST_RUNNER_INHERITED",)),
    )
    registry = _registry(executor)

    result = run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)

    assert result.returncode == 0
    assert out_file.read_text(encoding="utf-8") == "from-parent"


def test_external_executor_does_not_inherit_undeclared_host_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASTRID_TEST_RUNNER_UNDECLARED", "from-parent")
    out_file = tmp_path / "undeclared.txt"
    script = textwrap.dedent(
        """
        import os, sys
        from pathlib import Path
        Path(sys.argv[1]).write_text(os.environ.get('ASTRID_TEST_RUNNER_UNDECLARED', ''), encoding='utf-8')
        """
    )
    executor = _executor(
        executor_id="test.env_no_host_spread",
        argv=(sys.executable, "-c", script, str(out_file)),
    )
    registry = _registry(executor)

    result = run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)

    assert result.returncode == 0
    assert out_file.read_text(encoding="utf-8") == ""


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


# ---------------------------------------------------------------------------

# SC4: scoped_configs dispatch-time validation (T4)
# ---------------------------------------------------------------------------


def test_unknown_scoped_config_key_raises_executor_validation_error_at_dispatch(
    tmp_path: Path,
) -> None:
    """Unknown scoped_config key must raise ExecutorValidationError at dispatch, not at parse.

    Shape-only validation at parse time means the key regex passes; runner-time
    validation against SCOPE_REGISTRY catches unregistered keys.
    """
    executor = ExecutorDefinition(
        **{
            **_executor(executor_id="test.unknown_scope").__dict__,
            "scoped_configs": ("definitely.not.registered.xyz",),
        }
    )
    registry = _registry(executor)

    with pytest.raises(ExecutorValidationError, match="unknown scoped_config key"):
        run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)


def test_known_scoped_config_key_style_does_not_raise_at_dispatch(
    tmp_path: Path,
) -> None:
    """'style' is a registered key — dispatch must NOT raise."""
    executor = ExecutorDefinition(
        **{
            **_executor(executor_id="test.style_scope").__dict__,
            "scoped_configs": ("style",),
        }
    )
    registry = _registry(executor)

    result = run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)

    assert result.returncode == 0
    assert result.ok is True


def test_scoped_config_style_emits_hype_active_theme_in_subprocess_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When scoped_configs includes 'style' and a theme is resolved, HYPE_ACTIVE_THEME
    is emitted into the subprocess env (SINGLE source, tagged # scoped-config emit)."""
    from astrid.core.env_vars import HYPE_ACTIVE_THEME

    # Create a fake theme directory so resolve_theme_dir returns a real Path.
    fake_theme = tmp_path / "my-theme"
    fake_theme.mkdir()

    captured_env: dict[str, Any] = {}

    def _fake_subprocess_run(
        argv: list[str],
        *,
        cwd: str | None,
        env: Mapping[str, str],
        check: bool,
    ) -> types.SimpleNamespace:
        captured_env.update(env)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(executor_runner.subprocess, "run", _fake_subprocess_run)

    executor = ExecutorDefinition(
        **{
            **_executor(
                executor_id="test.style_emit",
                argv=(sys.executable, "-c", "pass"),
            ).__dict__,
            "scoped_configs": ("style",),
        }
    )
    registry = _registry(executor)

    result = run_executor(
        ExecutorRunRequest(
            executor_id=executor.id,
            out=tmp_path,
            inputs={"theme": str(fake_theme)},
        ),
        registry,
    )

    assert result.ok is True
    assert HYPE_ACTIVE_THEME in captured_env
    assert captured_env[HYPE_ACTIVE_THEME] == str(fake_theme)
