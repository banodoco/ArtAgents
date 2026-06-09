"""Parametrized error-path tests for ``astrid.core.executor.runner``.

The happy paths for the executor runner are covered by
``tests/core/test_project_runs.py`` and ``tests/test_task_kernel_dispatch.py``.
This module exercises every ``raise ExecutorRunnerError(...)`` site in
``astrid/core/executor/runner.py`` plus the real subprocess failure modes
of ``_run_external_executor`` (nonzero exit, missing executable, env-var
propagation, cwd propagation).
"""

from __future__ import annotations

import importlib
import io
import sys
import textwrap
import types
from pathlib import Path
from typing import Any, Mapping

import pytest

import astrid.packs
from astrid.core.contracts.schema import CommandInputArg, CommandSpec, IsolationMetadata, Output, Port
from astrid.core.executor import runner as executor_runner
from astrid.core.executor.cli import main as executor_cli_main
from astrid.core.executor.registry import ExecutorRegistry, load_default_registry
from astrid.core.executor.runner import (
    ExecutorRunnerError,
    ExecutorRunRequest,
    build_executor_command,
    evaluate_conditions,
    run_executor,
)
from astrid.core.executor.schema import ConditionSpec, ExecutorDefinition
from astrid.core.pack.resolver import PackResolverError
from astrid.core.executor.argv import executor_argv, resolve_executor_runtime_module

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


def test_builtin_render_rejects_legacy_assets_input_name(tmp_path: Path) -> None:
    with pytest.raises(ExecutorRunnerError, match="missing required input\\(s\\): assets_registry"):
        build_executor_command(
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


def test_reigh_open_in_reigh_does_not_forward_unsupported_assets_flag(
    tmp_path: Path,
) -> None:
    """`reigh.open_in_reigh` opts out: its run.py argparse has no `--assets`."""
    command = build_executor_command(
        ExecutorRunRequest(
            executor_id="reigh.open_in_reigh",
            out=tmp_path,
            inputs={"timeline": "/tmp/t.json", "assets": "/tmp/a.json"},
            python_exec="/opt/python",
        ),
        load_default_registry(),
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
    assert resolve_executor_runtime_module("upload.youtube") == "astrid.packs.youtube.executors.upload.run"


def test_executor_argv_rejects_non_pipeline_bare_name() -> None:
    with pytest.raises(ValueError, match="could not resolve executor step 'upload'"):
        executor_argv("upload", "/opt/python")


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
        metadata={
            "pipeline_module": "astrid.packs.video_editing.orchestrators.hype.run",
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
            "pipeline_module": "astrid.packs.video_editing.orchestrators.hype.run",
            "pipeline_step": "definitely_not_a_real_step",
        },
    )
    registry = _registry(executor)

    with pytest.raises(ExecutorRunnerError, match="unknown pipeline step"):
        run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)


# ---------------------------------------------------------------------------
# youtube.upload built-in — required input
# ---------------------------------------------------------------------------


def test_upload_youtube_requires_video_url(tmp_path: Path) -> None:
    executor = _executor(
        executor_id="youtube.upload",
        argv=None,
        metadata={
            "callable_module": "astrid.packs.youtube.executors.upload.src.social_publish",
            "callable_name": "publish_youtube_video",
        },
    )
    registry = _registry(executor)

    with pytest.raises(ExecutorRunnerError, match="video_url is required"):
        run_executor(ExecutorRunRequest(executor_id="youtube.upload", out=tmp_path), registry)


def test_upload_youtube_alias_dispatches_through_canonical_special_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from astrid.packs.youtube.executors.upload.src import social_publish

    called: dict[str, Any] = {}

    def _fake_publish(**kwargs: Any) -> dict[str, Any]:
        called.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(social_publish, "publish_youtube_video", _fake_publish)

    result = run_executor(
        ExecutorRunRequest(
            executor_id="upload.youtube",
            out=tmp_path,
            inputs={
                "video_url": "https://example.com/video.mp4",
                "title": "Title",
                "description": "Desc",
            },
        ),
        load_default_registry(),
    )

    assert result.executor_id == "youtube.upload"
    assert result.payload == {"ok": True}
    assert called == {
        "video_url": "https://example.com/video.mp4",
        "title": "Title",
        "description": "Desc",
        "tags": None,
        "privacy_status": "private",
        "playlist_id": None,
        "made_for_kids": False,
    }


def test_upload_youtube_reports_missing_callable_metadata(tmp_path: Path) -> None:
    executor = _executor(executor_id="youtube.upload", argv=None, metadata={})
    registry = _registry(executor)

    with pytest.raises(PackResolverError, match=r"youtube\.upload manifest is missing metadata\.callable_module"):
        run_executor(ExecutorRunRequest(executor_id="youtube.upload", out=tmp_path), registry)


def test_pipeline_module_imports_metadata_pipeline_module(
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
        metadata={"pipeline_module": "fake.pipeline"},
    )

    executor_runner._pipeline_module.cache_clear()
    try:
        # Resolved from the executor manifest — no orchestrator registry lookup.
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


def test_external_executor_in_process_mode_avoids_subprocess_and_returns_executor_result_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _executor(
        executor_id="test.in_process_help",
        argv=(sys.executable, "-m", "astrid.packs.youtube.executors.upload.run", "--help"),
        metadata={
            "runtime_module": "astrid.packs.youtube.executors.upload.run",
            "runtime_entrypoint": "main",
        },
    )
    registry = _registry(executor)

    def _fail_subprocess(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("subprocess.run should not be used in in_process mode")

    monkeypatch.setattr(executor_runner.subprocess, "run", _fail_subprocess)

    result = run_executor(
        ExecutorRunRequest(
            executor_id=executor.id,
            out=tmp_path,
            execution_mode="in_process",
        ),
        registry,
    )

    assert result.command == executor.command.argv
    assert result.cwd is None
    assert result.env == {}
    assert result.returncode == 0
    assert result.ok is True
    assert result.error is None
    assert result.payload == {
        "executor_id": executor.id,
        "missing_binaries": [],
        "returncode": 0,
        "skipped": False,
        "skipped_reason": "",
    }


def test_external_executor_in_process_mode_shallow_merges_runtime_payload_with_runner_keys_authoritative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _executor(
        executor_id="test.in_process_payload_merge",
        argv=(sys.executable, "-m", "astrid.packs.youtube.executors.upload.run", "--help"),
        metadata={
            "runtime_module": "astrid.packs.youtube.executors.upload.run",
            "runtime_entrypoint": "main",
        },
    )
    registry = _registry(executor)

    def _fake_in_process(*args: Any, **kwargs: Any) -> Any:
        return types.SimpleNamespace(
            returncode=7,
            payload={
                "artifact": str(tmp_path / "artifact.json"),
                "returncode": 99,
                "executor_id": "runtime.executor",
                "missing_binaries": ["runtime-bin"],
                "skipped": True,
                "skipped_reason": "runtime value",
            },
        )

    monkeypatch.setattr(executor_runner, "invoke_in_process_command", _fake_in_process)

    result = run_executor(
        ExecutorRunRequest(
            executor_id=executor.id,
            out=tmp_path,
            execution_mode="in_process",
        ),
        registry,
    )

    assert result.returncode == 7
    assert result.payload == {
        "artifact": str(tmp_path / "artifact.json"),
        "executor_id": executor.id,
        "missing_binaries": [],
        "returncode": 7,
        "skipped": False,
        "skipped_reason": "",
    }


def test_external_executor_default_mode_remains_subprocess_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _executor(
        executor_id="test.subprocess_default",
        argv=(sys.executable, "-c", "pass"),
        metadata={
            "runtime_module": "astrid.packs.youtube.executors.upload.run",
            "runtime_entrypoint": "main",
        },
    )
    registry = _registry(executor)
    seen: dict[str, Any] = {}

    def _fake_subprocess_run(
        argv: list[str],
        *,
        cwd: str | None,
        env: Mapping[str, str],
        check: bool,
    ) -> types.SimpleNamespace:
        seen["argv"] = tuple(argv)
        seen["cwd"] = cwd
        seen["check"] = check
        seen["env"] = env
        return types.SimpleNamespace(returncode=0)

    def _fail_in_process(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("invoke_in_process_command should not be used by default")

    monkeypatch.setattr(executor_runner.subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(executor_runner, "invoke_in_process_command", _fail_in_process)

    result = run_executor(ExecutorRunRequest(executor_id=executor.id, out=tmp_path), registry)

    assert seen["argv"] == executor.command.argv
    assert seen["cwd"] is None
    assert seen["check"] is False
    assert result.returncode == 0
    assert result.ok is True


def test_external_executor_in_process_mode_rejects_different_python_interpreter(
    tmp_path: Path,
) -> None:
    foreign_python = tmp_path / "venv" / "bin" / "python"
    executor = _executor(
        executor_id="test.in_process_wrong_python",
        argv=(
            str(foreign_python),
            "-m",
            "astrid.packs.youtube.executors.upload.run",
            "--help",
        ),
        metadata={
            "runtime_module": "astrid.packs.youtube.executors.upload.run",
            "runtime_entrypoint": "main",
        },
    )
    registry = _registry(executor)

    result = run_executor(
        ExecutorRunRequest(
            executor_id=executor.id,
            out=tmp_path,
            execution_mode="in_process",
        ),
        registry,
    )

    assert result.returncode == 1
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "in_process_precondition"
    assert result.error.type == "precondition"
    assert "requires interpreter" in result.error.message


def test_external_executor_in_process_mode_captures_logs_and_preserves_terminal_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SC13: the supported path is serialized execution, so stdout/stderr are
    monkeypatched once at the process level and must still receive live output
    while run logs are written."""

    pack_root = _extend_packs_path(monkeypatch, tmp_path)
    module_path = pack_root / "chatty_runtime_test.py"
    module_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import sys",
                "from astrid.core.pack.entrypoint import guard_canonical_entrypoint",
                "guard_canonical_entrypoint('test.in_process_chatty')",
                "",
                "def main(argv=None):",
                "    print('chatty stdout line')",
                "    print('chatty stderr line', file=sys.stderr)",
                "    return {'artifact': 'ok'}",
            ]
        ),
        encoding='utf-8',
    )
    importlib.invalidate_caches()
    sys.modules.pop("astrid.packs.chatty_runtime_test", None)

    executor = _executor(
        executor_id="test.in_process_chatty",
        argv=(sys.executable, "-m", "astrid.packs.chatty_runtime_test"),
        metadata={
            "runtime_module": "astrid.packs.chatty_runtime_test",
            "runtime_entrypoint": "main",
        },
    )
    live_stdout = io.StringIO()
    live_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stdout", live_stdout)
    monkeypatch.setattr(sys, "stderr", live_stderr)

    request = ExecutorRunRequest(
        executor_id=executor.id,
        out=tmp_path,
        execution_mode="in_process",
        run_root=tmp_path / "run",
    )
    result = executor_runner._run_in_process_executor_command(
        executor,
        request,
        command=executor.command.argv,
        cwd=None,
        env={},
    )

    assert result.returncode == 0
    assert result.payload["artifact"] == "ok"
    assert live_stdout.getvalue().splitlines() == ["chatty stdout line"]
    assert live_stderr.getvalue().splitlines() == ["chatty stderr line"]
    assert (tmp_path / "run" / "logs" / "stdout.log").read_text(encoding="utf-8").splitlines() == [
        "chatty stdout line"
    ]
    assert (tmp_path / "run" / "logs" / "stderr.log").read_text(encoding="utf-8").splitlines() == [
        "chatty stderr line"
    ]


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
# Generation facade contract tests — GENERATION_RESULT_KEY passthrough
# and runner-authoritative collision precedence
# ---------------------------------------------------------------------------


def test_in_process_generation_result_key_passthrough_preserves_dict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime payload keys outside the runner-authoritative set are preserved.

    When an in-process executor returns a payload containing
    ``GENERATION_RESULT_KEY``, the generation result dict must survive the
    ``_merge_runner_payload`` shallow merge so facade code (T6+) can
    reconstruct a ``GenerationResult`` later.
    """
    from astrid.core.generation import GENERATION_RESULT_KEY

    executor = _executor(
        executor_id="test.gen_result_passthrough",
        argv=(sys.executable, "-m", "astrid.packs.youtube.executors.upload.run", "--help"),
        metadata={
            "runtime_module": "astrid.packs.youtube.executors.upload.run",
            "runtime_entrypoint": "main",
        },
    )
    registry = _registry(executor)

    gen_result = {
        "mode": "t2i",
        "backend": "local",
        "model": "z-image",
        "image_paths": ["/tmp/img_01.png", "/tmp/img_02.png"],
        "ok": True,
        "error": None,
        "manifest": {"prompt": "a red bicycle"},
        "run_dir": "/tmp/run_abc",
    }

    def _fake_in_process(*args: Any, **kwargs: Any) -> Any:
        return types.SimpleNamespace(
            returncode=0,
            payload={
                "custom_artifact": str(tmp_path / "out.json"),
                GENERATION_RESULT_KEY: gen_result,
            },
        )

    monkeypatch.setattr(executor_runner, "invoke_in_process_command", _fake_in_process)

    result = run_executor(
        ExecutorRunRequest(
            executor_id=executor.id,
            out=tmp_path,
            execution_mode="in_process",
        ),
        registry,
    )

    # Runner-authoritative keys are set.
    assert result.payload["executor_id"] == executor.id
    assert result.payload["returncode"] == 0
    assert result.payload["missing_binaries"] == []
    assert result.payload["skipped"] is False
    assert result.payload["skipped_reason"] == ""

    # Runtime-only key is preserved.
    assert result.payload["custom_artifact"] == str(tmp_path / "out.json")

    # GENERATION_RESULT_KEY is preserved intact.
    assert result.payload[GENERATION_RESULT_KEY] == gen_result
    assert result.payload[GENERATION_RESULT_KEY]["mode"] == "t2i"
    assert result.payload[GENERATION_RESULT_KEY]["image_paths"] == [
        "/tmp/img_01.png",
        "/tmp/img_02.png",
    ]


def test_in_process_returncode_collision_runner_wins_and_generation_result_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SC5: runtime ``returncode`` is overwritten by the runner's authoritative value.

    A synthetic in-process executor returning
    ``{GENERATION_RESULT_KEY: {...}, "returncode": 99}`` must yield:
    * preserved ``generation_result`` in the payload
    * runner-level ``returncode`` (7, not 99) in both ``result.returncode``
      and ``result.payload["returncode"]``
    """
    from astrid.core.generation import GENERATION_RESULT_KEY

    executor = _executor(
        executor_id="test.returncode_collision",
        argv=(sys.executable, "-m", "astrid.packs.youtube.executors.upload.run", "--help"),
        metadata={
            "runtime_module": "astrid.packs.youtube.executors.upload.run",
            "runtime_entrypoint": "main",
        },
    )
    registry = _registry(executor)

    gen_result = {
        "mode": "t2v",
        "backend": "local",
        "model": "wan-2.2",
        "video_paths": ["/tmp/vid_01.mp4"],
        "ok": True,
        "error": None,
        "manifest": {"prompt": "a cat walking"},
        "run_dir": "/tmp/run_def",
    }

    def _fake_in_process(*args: Any, **kwargs: Any) -> Any:
        return types.SimpleNamespace(
            returncode=7,
            payload={
                GENERATION_RESULT_KEY: gen_result,
                "returncode": 99,
                "executor_id": "runtime.executor",
                "missing_binaries": ["runtime-bin"],
                "skipped": True,
                "skipped_reason": "runtime value",
            },
        )

    monkeypatch.setattr(executor_runner, "invoke_in_process_command", _fake_in_process)

    result = run_executor(
        ExecutorRunRequest(
            executor_id=executor.id,
            out=tmp_path,
            execution_mode="in_process",
        ),
        registry,
    )

    # Runner returncode is authoritative on the result struct.
    assert result.returncode == 7

    # Runner returncode is authoritative in the payload — runtime's 99 is
    # overwritten during _merge_runner_payload.
    assert result.payload["returncode"] == 7

    # Other runner-authoritative keys also overwrite runtime values.
    assert result.payload["executor_id"] == executor.id
    assert result.payload["missing_binaries"] == []
    assert result.payload["skipped"] is False
    assert result.payload["skipped_reason"] == ""

    # GENERATION_RESULT_KEY is preserved intact alongside runner keys.
    assert result.payload[GENERATION_RESULT_KEY] == gen_result
    assert result.payload[GENERATION_RESULT_KEY]["mode"] == "t2v"
    assert result.payload[GENERATION_RESULT_KEY]["video_paths"] == ["/tmp/vid_01.mp4"]
