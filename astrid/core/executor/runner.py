"""Execution helpers for Astrid executor definitions."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping, Sequence

from astrid.core.contracts.capability_runner import CapabilityRunner
from astrid.core.contracts.exec_error import (
    ExecError,
    error_from_missing_binaries,
    error_from_returncode,
)
from astrid.core.contracts.run_status import RunStatus
from astrid.core.env_vars import ASTRID_INTERNAL_INVOCATION
from astrid.core.pack.resolver import resolve_callable_from_metadata
from astrid.core.project.run import (
    ProjectRunContext,
    finalize_project_run,
    prepare_project_run,
    project_run_env,
    reject_project_with_out,
)
from astrid.core.runtime import (
    InProcessExecutionPreconditionError,
    InProcessInvocationError,
    invoke_in_process_command,
)
from astrid.core.runtime.log_capture import (
    open_run_log_capture,
    run_subprocess_with_capture,
)
from astrid.core.session.config import resolve_default_project_for_sdk
from astrid.core.subprocess_env import build_child_subprocess_env
from astrid.core.task import env as task_env
from astrid.core.task import gate as task_gate
from astrid.core.paths import REPO_ROOT

from .install import executor_python_path
from .registry import ExecutorRegistry, load_default_registry
from .schema import (
    ConditionSpec,
    ExecutorDefinition,
    ExecutorKind,
    ExecutorOutput,
    ExecutorValidationError,
)

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ExecutorRunnerError(ExecutorValidationError):
    """Raised when a executor cannot be prepared or executed."""


@lru_cache(maxsize=1)
def _pipeline_module():
    from astrid.core.orchestrator.registry import (
        load_default_registry as load_default_orchestrator_registry,
    )

    registry = load_default_orchestrator_registry()
    orchestrator = registry.get("video_editing.hype")
    runtime_module = orchestrator.metadata.get("runtime_module")
    if not isinstance(runtime_module, str) or not runtime_module:
        raise ExecutorRunnerError("video_editing.hype manifest is missing metadata.runtime_module")
    pipeline = import_module(runtime_module)

    return pipeline


def _pipeline_steps_by_name() -> Mapping[str, Any]:
    pipeline = _pipeline_module()
    steps = {step.name: step for step in pipeline.build_pool_steps()}
    missing = [name for name in pipeline.STEP_ORDER if name not in steps]
    if missing:
        raise ValueError(f"build_pool_steps() is missing STEP_ORDER entries: {', '.join(missing)}")
    return MappingProxyType(steps)


@dataclass(frozen=True)
class ExecutorRunRequest:
    executor_id: str
    out: Path | str | None
    project: str | None = None
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    brief: Path | str | None = None
    dry_run: bool = False
    check_binaries: bool = False
    python_exec: str | None = None
    verbose: bool = False
    argv: tuple[str, ...] = ()
    execution_mode: Literal["subprocess", "in_process"] = "subprocess"
    project_was_auto_resolved: bool = False
    invocation: str = "cli"
    run_root: Path | str | None = None


@dataclass(frozen=True)
class ExecutorRunResult:
    executor_id: str
    kind: ExecutorKind
    command: tuple[str, ...] = ()
    cwd: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)
    returncode: int | None = None
    dry_run: bool = False
    skipped: bool = False
    skipped_reason: str = ""
    missing_binaries: tuple[str, ...] = ()
    error: ExecError | None = None

    def __post_init__(self) -> None:
        if self.error is None:
            derived = error_from_missing_binaries(self.missing_binaries) or error_from_returncode(
                self.returncode
            )
            if derived is not None:
                object.__setattr__(self, "error", derived)

    @property
    def ok(self) -> bool:
        return self.error is None


class ExecutorCapabilityRunner(CapabilityRunner[ExecutorRunRequest, ExecutorRunResult, ExecutorDefinition]):
    """Executor binding of the shared :class:`CapabilityRunner` skeleton."""

    def load_default_registry(self) -> ExecutorRegistry:
        return load_default_registry()

    def request_id(self, request: ExecutorRunRequest) -> str:
        return request.executor_id

    def build_command(
        self, request: ExecutorRunRequest, registry: ExecutorRegistry | None = None
    ) -> tuple[str, ...]:
        active_registry = registry or self.load_default_registry()
        executor = active_registry.get(request.executor_id)
        values = _request_values(request)
        _validate_required_inputs(executor, values)
        condition_result = evaluate_conditions(executor, values)
        if condition_result.skipped:
            return ()
        if executor.command is not None:
            return _expand_external_command(executor, request, values)[0]
        if executor.kind == "built_in" and "pipeline_step" in executor.metadata:
            step = _step_for_executor(executor)
            args = build_pipeline_context(request, executor)
            return tuple(step.build_cmd(args))
        return _expand_external_command(executor, request, values)[0]

    def maybe_gate(self, request: ExecutorRunRequest) -> None:
        task_project = task_env.task_project_env()
        task_run_id = task_env.task_run_id_env()
        task_step_id = task_env.task_step_id_env()
        env_task_context = bool(task_project and task_run_id and task_step_id)
        project_task_context = bool(request.project and task_env.is_in_task_run(request.project))
        if not (env_task_context or project_task_context):
            return
        gate_project = task_project or request.project
        if gate_project is None:
            raise ExecutorRunnerError("task project is missing")
        if task_project and request.project and request.project != task_project:
            raise ExecutorRunnerError(
                f"task run is bound to project {task_project!r}, refusing executor project {request.project!r}"
            )
        try:
            task_gate.gate_command(
                gate_project,
                task_gate.command_for_argv(_request_argv_for_gate(request)),
                [],
                reentry=True,
            )
        except task_gate.TaskRunGateError as exc:
            if env_task_context and not project_task_context and exc.reason == "active_run.json is missing":
                return
            raise ExecutorRunnerError(f"{exc.reason}; recovery: {exc.recovery}") from exc

    def prepare_project(
        self, request: ExecutorRunRequest, definition: ExecutorDefinition
    ) -> tuple[ProjectRunContext | None, ExecutorRunRequest]:
        return _prepare_project_request(request, definition)

    def resolve_project_request(
        self, request: ExecutorRunRequest, definition: ExecutorDefinition
    ) -> ExecutorRunRequest:
        return _resolve_project_request(request)

    def is_dry_run(self, request: ExecutorRunRequest, definition: ExecutorDefinition) -> bool:
        return bool(request.dry_run)

    def prepare_dry_run_request(
        self, request: ExecutorRunRequest, definition: ExecutorDefinition
    ) -> ExecutorRunRequest:
        return _prepare_dry_run_request(request)

    def run_inner(self, request: ExecutorRunRequest, definition: ExecutorDefinition) -> ExecutorRunResult:
        return _run_executor_inner(request, definition)

    def finalize_project(
        self,
        context: ProjectRunContext,
        request: ExecutorRunRequest,
        *,
        status: RunStatus,
        returncode: int | None,
        error: BaseException | str | None = None,
    ) -> None:
        _finalize_project_executor(
            context, request, status=status, returncode=returncode, error=error
        )

    def status_for_result(self, result: ExecutorRunResult) -> RunStatus:
        return _project_status_for_result(result)

    def result_returncode(self, result: ExecutorRunResult) -> int | None:
        return result.returncode


_EXECUTOR_RUNNER = ExecutorCapabilityRunner()


def run_executor(request: ExecutorRunRequest, registry: ExecutorRegistry | None = None) -> ExecutorRunResult:
    return _EXECUTOR_RUNNER.run(request, registry)


def _request_argv_for_gate(request: ExecutorRunRequest) -> tuple[str, ...]:
    if request.argv:
        if request.argv[0] == "executors":
            return request.argv
        if request.argv[0] == "run":
            argv = _canonicalize_runner_argv_paths(request.argv)
            if request.project or os.environ.get(ASTRID_INTERNAL_INVOCATION) != "1":
                return ("executors", *argv)
            return ("python3", "-m", "astrid", "executors", *argv)
        return ("executors", *request.argv)
    argv = ["executors", "run", request.executor_id]
    if request.project:
        argv.extend(["--project", request.project])
    if request.out not in (None, ""):
        argv.extend(["--out", str(request.out)])
    if request.brief:
        argv.extend(["--brief", str(request.brief)])
    for key, value in request.inputs.items():
        for item in _iter_input_values(value):
            argv.extend(["--input", f"{key}={_stringify_value(item)}"])
    if request.dry_run:
        argv.append("--dry-run")
    if request.check_binaries:
        argv.append("--check-binaries")
    if request.python_exec:
        argv.extend(["--python-exec", request.python_exec])
    if request.verbose:
        argv.append("--verbose")
    return tuple(argv)


def _canonicalize_runner_argv_paths(argv: Sequence[str]) -> tuple[str, ...]:
    tokens = [str(token) for token in argv]
    canonical: list[str] = []
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        canonical.append(token)
        if token == "--out" and idx + 1 < len(tokens):
            idx += 1
            canonical.append(str(Path(tokens[idx]).resolve()))
        idx += 1
    return tuple(canonical)


def _run_executor_inner(request: ExecutorRunRequest, executor: ExecutorDefinition) -> ExecutorRunResult:
    if executor.id == "youtube.upload":
        return _run_upload_youtube(request, executor)
    values = _request_values(request)
    _validate_required_inputs(executor, values)
    condition_result = evaluate_conditions(executor, values)
    if condition_result.skipped:
        return ExecutorRunResult(
            executor_id=executor.id,
            kind=executor.kind,
            payload={"executor_id": executor.id, "skipped": True, "skipped_reason": condition_result.reason},
            dry_run=request.dry_run,
            skipped=True,
            skipped_reason=condition_result.reason,
        )

    missing_binaries = check_executor_binaries(executor) if request.check_binaries else ()
    if missing_binaries:
        return ExecutorRunResult(
            executor_id=executor.id,
            kind=executor.kind,
            payload={"executor_id": executor.id, "missing_binaries": list(missing_binaries)},
            dry_run=request.dry_run,
            missing_binaries=missing_binaries,
        )

    if executor.kind == "built_in" and "pipeline_step" in executor.metadata:
        return _run_builtin_executor(executor, request)
    return _run_external_executor(executor, request, values)


def _run_upload_youtube(request: ExecutorRunRequest, executor: ExecutorDefinition) -> ExecutorRunResult:
    inputs = dict(request.inputs)
    if request.dry_run:
        return ExecutorRunResult(
            executor_id=executor.id,
            kind="built_in",
            dry_run=True,
            payload={"would_run": "youtube.upload", "inputs": inputs},
        )

    publish_youtube_video = resolve_callable_from_metadata(
        executor.metadata,
        owner_id=executor.id,
        module_key="callable_module",
        callable_key="callable_name",
    )

    result = publish_youtube_video(
        video_url=_required_input(inputs, "video_url"),
        title=_required_input(inputs, "title"),
        description=_required_input(inputs, "description"),
        tags=_optional_input(inputs, "tags") or _optional_input(inputs, "tag"),
        privacy_status=str(_optional_input(inputs, "privacy_status") or "private"),
        playlist_id=_optional_input(inputs, "playlist_id"),
        made_for_kids=bool(_optional_input(inputs, "made_for_kids") or False),
    )
    return ExecutorRunResult(executor_id=executor.id, kind="built_in", payload=result)


@dataclass(frozen=True)
class ConditionResult:
    skipped: bool = False
    reason: str = ""


def evaluate_conditions(executor: ExecutorDefinition, values: Mapping[str, Any]) -> ConditionResult:
    for condition in executor.conditions:
        result = _evaluate_condition(condition, values)
        if result.skipped:
            return result
    return ConditionResult()


def check_executor_binaries(executor: ExecutorDefinition) -> tuple[str, ...]:
    return tuple(binary for binary in executor.isolation.binaries if shutil.which(binary) is None)


def build_pipeline_context(request: ExecutorRunRequest, executor: ExecutorDefinition | None = None) -> argparse.Namespace:
    from astrid.core.element.catalog import resolve_active_theme
    from astrid.core.theme import resolve_theme_dir, resolve_themes_root

    values = _request_values(request)
    out = Path(request.out).expanduser().resolve()
    brief = _optional_path(values.get("brief") or request.brief)
    if brief is None:
        brief = (out / "brief.txt").resolve()
    audio_value = values.get("audio")
    video_value = values.get("video")
    video = _optional_asset_path(video_value)
    audio = _optional_asset_path(audio_value if audio_value is not None else video_value)
    env_file = _optional_path(values.get("env_file"))
    theme_raw = values.get("theme")
    theme_explicit = theme_raw is not None
    active_theme = resolve_active_theme(project_slug=request.project)
    if theme_explicit:
        theme_dir = resolve_theme_dir(theme_raw)
        if theme_dir is None:
            theme = (resolve_themes_root() / "banodoco-default" / "theme.json").resolve()
        else:
            candidate = Path(theme_raw).expanduser()
            if candidate.name == "theme.json" or (candidate.exists() and candidate.is_file()):
                theme = candidate.resolve()
            else:
                theme = (theme_dir / "theme.json").resolve()
    else:
        theme = active_theme
    brief_slug = str(values.get("brief_slug") or _default_brief_slug(brief, out))
    brief_out = (out / "briefs" / brief_slug).resolve()
    skip = _as_string_list(values.get("skip"))
    asset_values = _as_string_list(values.get("asset") or values.get("assets"))
    args = argparse.Namespace(
        audio=audio,
        video=video,
        out=out,
        brief=brief,
        brief_out=brief_out,
        brief_copy=brief_out / "brief.txt",
        skip=skip,
        asset=asset_values,
        asset_pairs=_parse_asset_pairs(asset_values),
        primary_asset=values.get("primary_asset"),
        theme=theme,
        theme_explicit=theme_explicit,
        source_slug=str(values.get("source_slug") or out.name),
        brief_slug=brief_slug,
        env_file=env_file,
        extra_args=_normalize_extra_args(values.get("extra_args")),
        target_duration=_optional_float(values.get("target_duration")),
        python_exec=str(values.get("python_exec") or request.python_exec or sys.executable),
        render=bool(values.get("render", False)),
        verbose=bool(values.get("verbose", request.verbose)),
        no_prefetch=bool(values.get("no_prefetch", False)),
        keep_downloads=bool(values.get("keep_downloads", False)),
        cache_dir=_optional_path(values.get("cache_dir")),
        drift=str(values.get("drift") or "strict"),
        from_step=values.get("from_step"),
        max_editor_passes=int(values.get("max_editor_passes", 2)),
        editor_iteration=int(values.get("editor_iteration", 1)),
    )
    if executor is not None:
        args.executor_id = executor.id
    return args


def build_executor_command(request: ExecutorRunRequest, registry: ExecutorRegistry | None = None) -> tuple[str, ...]:
    return _EXECUTOR_RUNNER.build_command(request, registry)


def _run_builtin_executor(executor: ExecutorDefinition, request: ExecutorRunRequest) -> ExecutorRunResult:
    if executor.command is not None:
        return _run_explicit_command_executor(executor, request, _request_values(request))
    pipeline = _pipeline_module()
    step = _step_for_executor(executor)
    args = build_pipeline_context(request, executor)
    command = tuple(step.build_cmd(args))
    if request.dry_run:
        return ExecutorRunResult(
            executor_id=executor.id,
            kind=executor.kind,
            command=command,
            payload={"executor_id": executor.id, "missing_binaries": [], "returncode": None, "skipped": False, "skipped_reason": ""},
            dry_run=True,
        )
    if args.brief.exists():
        pipeline.prepare_brief_artifacts(args)
    returncode = pipeline.run_step(step, list(command), args)
    return ExecutorRunResult(
        executor_id=executor.id,
        kind=executor.kind,
        command=command,
        payload={"executor_id": executor.id, "missing_binaries": [], "returncode": returncode, "skipped": False, "skipped_reason": ""},
        returncode=returncode,
    )


def _run_explicit_command_executor(
    executor: ExecutorDefinition,
    request: ExecutorRunRequest,
    values: Mapping[str, Any],
) -> ExecutorRunResult:
    command, cwd, env = _expand_external_command(executor, request, values)
    if request.dry_run:
        return ExecutorRunResult(
            executor_id=executor.id,
            kind=executor.kind,
            command=command,
            cwd=cwd,
            env=env,
            payload={"executor_id": executor.id, "missing_binaries": [], "returncode": None, "skipped": False, "skipped_reason": ""},
            dry_run=True,
        )
    if request.execution_mode == "in_process":
        return _run_in_process_executor_command(
            executor,
            request,
            command=command,
            cwd=cwd,
            env=env,
        )
    effective_env = _command_subprocess_env(executor, request, env)
    run_root = request.run_root
    if run_root is not None and not request.project_was_auto_resolved:
        with open_run_log_capture(run_root) as logs:
            returncode = run_subprocess_with_capture(
                list(command),
                cwd=cwd,
                env=effective_env,
                stdout_log=logs.stdout,
                stderr_log=logs.stderr,
            )
    else:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            env=effective_env,
            check=False,
        )
        returncode = completed.returncode
    return ExecutorRunResult(
        executor_id=executor.id,
        kind=executor.kind,
        command=command,
        cwd=cwd,
        env=env,
        payload={
            "executor_id": executor.id,
            "missing_binaries": [],
            "returncode": returncode,
            "skipped": False,
            "skipped_reason": "",
        },
        returncode=returncode,
    )


def _run_in_process_executor_command(
    executor: ExecutorDefinition,
    request: ExecutorRunRequest,
    *,
    command: tuple[str, ...],
    cwd: str | None,
    env: Mapping[str, str],
) -> ExecutorRunResult:
    log_capture = (
        open_run_log_capture(request.run_root)
        if request.run_root is not None and not request.project_was_auto_resolved
        else None
    )
    try:
        with log_capture or nullcontext():
            result = invoke_in_process_command(
                command,
                metadata=executor.metadata,
                owner_id=executor.id,
                cwd=cwd,
                env=env,
                parent_env=os.environ,
                stdout_log=None if log_capture is None else log_capture.stdout,
                stderr_log=None if log_capture is None else log_capture.stderr,
            )
    except InProcessExecutionPreconditionError as exc:
        return _in_process_executor_error_result(
            executor,
            command=command,
            cwd=cwd,
            env=env,
            error=ExecError(
                code="in_process_precondition",
                type="precondition",
                message=str(exc),
                recovery="use subprocess mode or make the executor command match the current interpreter/runtime module",
            ),
        )
    except InProcessInvocationError as exc:
        return _in_process_executor_error_result(
            executor,
            command=command,
            cwd=cwd,
            env=env,
            error=ExecError(
                code="in_process_runtime",
                type="process",
                message=str(exc),
                recovery="fix the executor runtime import/entrypoint or run it in subprocess mode",
            ),
        )
    return ExecutorRunResult(
        executor_id=executor.id,
        kind=executor.kind,
        command=command,
        cwd=cwd,
        env=dict(env),
        payload=_merge_runner_payload(
            result.payload,
            executor_id=executor.id,
            returncode=result.returncode,
        ),
        returncode=result.returncode,
    )


def _in_process_executor_error_result(
    executor: ExecutorDefinition,
    *,
    command: tuple[str, ...],
    cwd: str | None,
    env: Mapping[str, str],
    error: ExecError,
) -> ExecutorRunResult:
    return ExecutorRunResult(
        executor_id=executor.id,
        kind=executor.kind,
        command=command,
        cwd=cwd,
        env=dict(env),
        payload={
            "executor_id": executor.id,
            "missing_binaries": [],
            "returncode": 1,
            "skipped": False,
            "skipped_reason": "",
        },
        returncode=1,
        error=error,
    )


def _merge_runner_payload(
    payload: Mapping[str, Any],
    *,
    executor_id: str,
    returncode: int | None,
) -> dict[str, Any]:
    merged = dict(payload)
    merged.update(
        {
            "executor_id": executor_id,
            "missing_binaries": [],
            "returncode": returncode,
            "skipped": False,
            "skipped_reason": "",
        }
    )
    return merged


def _run_external_executor(executor: ExecutorDefinition, request: ExecutorRunRequest, values: Mapping[str, Any]) -> ExecutorRunResult:
    return _run_explicit_command_executor(executor, request, values)


def _expand_external_command(
    executor: ExecutorDefinition,
    request: ExecutorRunRequest,
    values: Mapping[str, Any],
) -> tuple[tuple[str, ...], str | None, dict[str, str]]:
    if executor.command is None:
        raise ExecutorRunnerError(f"executor {executor.id!r} has no command")
    placeholders = _placeholder_values(executor, request, values)
    argv = tuple(_expand_placeholders(part, placeholders) for part in executor.command.argv)
    consumed = _consumed_input_names(executor)
    argv = (*argv, *_expand_input_arg_mappings(executor, values))
    argv = (*argv, *_auto_forward_untemplated_inputs(executor, values, consumed))
    cwd = _expand_placeholders(executor.command.cwd, placeholders) if executor.command.cwd else None
    env = {key: _expand_placeholders(value, placeholders) for key, value in executor.command.env.items()}
    return argv, cwd, env


# Truthy/falsey string forms used when an `--input name=value` boolean reaches
# the runner (CLI inputs arrive as strings, so a declared boolean port is a
# string like "true"/"false").
_BOOLEAN_TRUE = frozenset({"1", "true", "yes", "on"})
_BOOLEAN_FALSE = frozenset({"", "0", "false", "no", "off"})


def _consumed_input_names(executor: ExecutorDefinition) -> set[str]:
    """Names already routed into the command by a placeholder or input_arg mapping.

    An input is "consumed" when its ``name`` (or its declared ``placeholder``
    alias) appears as a ``{token}`` anywhere in ``command.argv``/``cwd``/``env``,
    or when it is the target of a ``command.input_args`` mapping. Auto-forwarding
    skips consumed inputs so they are never double-passed.
    """
    consumed: set[str] = set()
    if executor.command is None:
        return consumed
    tokens: set[str] = set()
    for part in executor.command.argv:
        tokens.update(_PLACEHOLDER_RE.findall(part))
    if executor.command.cwd:
        tokens.update(_PLACEHOLDER_RE.findall(executor.command.cwd))
    for value in executor.command.env.values():
        tokens.update(_PLACEHOLDER_RE.findall(value))
    for mapping in executor.command.input_args:
        consumed.add(mapping.input)
    for port in executor.inputs:
        if port.name in tokens:
            consumed.add(port.name)
        if port.placeholder and port.placeholder in tokens:
            consumed.add(port.name)
    return consumed


def _input_flag(name: str) -> str:
    """Convert a snake_case input name to its ``--kebab-case`` CLI flag."""
    return "--" + name.replace("_", "-")


def _auto_forward_untemplated_inputs(
    executor: ExecutorDefinition,
    values: Mapping[str, Any],
    consumed: set[str],
) -> tuple[str, ...]:
    """Forward declared inputs that were not templated into the command.

    For every declared input that (a) has a non-empty provided value, (b) was
    not already consumed by a ``{placeholder}`` token, and (c) is not covered by
    a ``command.input_args`` mapping, append it as ``--<kebab-name> <value>``
    (or just ``--<kebab-name>`` for a truthy boolean port). This makes inputs
    like ``--input prompt=hello`` reach the executor's ``run.py`` argparse, which
    were otherwise silently dropped.

    Opt-out via metadata for executors whose ``run.py`` does not accept the
    derived flags:

    * ``metadata.auto_forward_inputs: false`` disables forwarding entirely.
    * ``metadata.auto_forward_skip: [name, ...]`` skips specific input names.
    """
    if executor.command is None:
        return ()
    metadata = executor.metadata or {}
    if metadata.get("auto_forward_inputs") is False:
        return ()
    skip = set(metadata.get("auto_forward_skip") or ())
    argv: list[str] = []
    for port in executor.inputs:
        if port.name in consumed or port.name in skip:
            continue
        value = values.get(port.name)
        if not _has_value(value):
            continue
        if port.type == "boolean":
            if _is_truthy_flag(value):
                argv.append(_input_flag(port.name))
            continue
        for item in _iter_input_values(value):
            if not _has_value(item):
                continue
            argv.append(_input_flag(port.name))
            argv.append(_stringify_value(item))
    return tuple(argv)


def _is_truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _BOOLEAN_TRUE:
        return True
    if text in _BOOLEAN_FALSE:
        return False
    # Unknown non-empty string: treat as truthy so an explicitly-provided flag
    # is not silently dropped.
    return bool(text)


def _prepare_project_request(
    request: ExecutorRunRequest,
    executor: ExecutorDefinition,
) -> tuple[ProjectRunContext | None, ExecutorRunRequest]:
    if not request.project:
        return None, request
    if not request.project_was_auto_resolved:
        reject_project_with_out(request.project, request.out)
    record_out = request.out if request.out not in (None, "") else None
    context = prepare_project_run(
        request.project,
        tool_id=executor.id,
        kind="executor",
        argv=_project_argv(request),
        metadata={
            "dry_run": bool(request.dry_run),
            "project_was_auto_resolved": bool(request.project_was_auto_resolved),
        },
        record_out=record_out,
        requires_timeline=False if request.project_was_auto_resolved else None,
        invocation=request.invocation,
    )
    effective_out = request.out if record_out is not None else context.run_root
    return context, replace(request, out=effective_out, run_root=context.run_root)


def _project_argv(request: ExecutorRunRequest) -> list[str]:
    argv = ["executors", "run", request.executor_id]
    if request.project:
        argv.extend(["--project", request.project])
    if request.brief:
        argv.extend(["--brief", str(request.brief)])
    for key, value in request.inputs.items():
        for item in _iter_input_values(value):
            argv.extend(["--input", f"{key}={_stringify_value(item)}"])
    if request.dry_run:
        argv.append("--dry-run")
    if request.check_binaries:
        argv.append("--check-binaries")
    if request.python_exec:
        argv.extend(["--python-exec", request.python_exec])
    if request.verbose:
        argv.append("--verbose")
    return argv


def _project_status_for_result(result: ExecutorRunResult) -> RunStatus:
    if result.skipped or result.dry_run:
        return RunStatus.SKIPPED
    if not result.ok:
        return RunStatus.FAILED
    return RunStatus.COMPLETED


def _finalize_project_executor(
    context: ProjectRunContext,
    request: ExecutorRunRequest,
    *,
    status: RunStatus,
    returncode: int | None,
    error: BaseException | str | None = None,
) -> None:
    artifact_roots = [request.out, context.run_root] if request.out not in (None, "") else [context.run_root]
    metadata = {
        "dry_run": bool(request.dry_run),
        "project_was_auto_resolved": bool(request.project_was_auto_resolved),
    }
    finalize_project_run(
        context,
        status=status,
        returncode=returncode,
        error=error,
        metadata=metadata,
        artifact_roots=artifact_roots,
    )


def _resolve_project_request(request: ExecutorRunRequest) -> ExecutorRunRequest:
    if request.project:
        return request
    return replace(
        request,
        project=resolve_default_project_for_sdk(),
        project_was_auto_resolved=True,
    )


def _prepare_dry_run_request(request: ExecutorRunRequest) -> ExecutorRunRequest:
    if request.out not in (None, ""):
        return request
    placeholder = (Path.cwd() / ".astrid-dry-run" / request.executor_id.replace(".", "-")).resolve()
    return replace(request, out=placeholder)


def _project_subprocess_env(request: ExecutorRunRequest) -> dict[str, str]:
    return project_run_env(request.project) if request.project else {}


def _command_subprocess_env(
    executor: ExecutorDefinition,
    request: ExecutorRunRequest,
    command_env: Mapping[str, str],
) -> dict[str, str]:
    external_pack_env = _external_pack_pythonpath_env(executor, command_env)
    return build_child_subprocess_env(
        explicit_env={
            **command_env,
            **external_pack_env,
            **_project_subprocess_env(request),
            "ASTRID_INTERNAL_INVOCATION": "1",
        },
        passthrough=executor.isolation.env_passthrough,
        declared_passthrough=executor.isolation.env_passthrough,
    )


def _external_pack_pythonpath_env(
    executor: ExecutorDefinition,
    command_env: Mapping[str, str],
) -> dict[str, str]:
    if executor.command is None:
        return {}
    argv = tuple(executor.command.argv)
    if len(argv) < 3 or argv[1] != "-m":
        return {}
    pack_id = str(executor.metadata.get("source_pack") or "")
    module = argv[2]
    if not pack_id or not module.startswith(f"{pack_id}."):
        return {}
    pack_root_raw = executor.metadata.get("pack_root")
    if not isinstance(pack_root_raw, str) or not pack_root_raw:
        return {}
    pack_root = Path(pack_root_raw).expanduser().resolve()
    builtin_root = (REPO_ROOT / "astrid" / "packs" / pack_id).resolve()
    if pack_root == builtin_root:
        return {}
    pack_parent = str(pack_root.parent)
    existing = command_env.get("PYTHONPATH") or os.environ.get("PYTHONPATH")
    return {"PYTHONPATH": pack_parent if not existing else os.pathsep.join((pack_parent, existing))}


def _placeholder_values(executor: ExecutorDefinition, request: ExecutorRunRequest, values: Mapping[str, Any]) -> dict[str, str]:
    out = Path(request.out).expanduser().resolve()
    placeholders: dict[str, str] = {
        "out": str(out),
    }
    python_exec = _resolve_python_exec(executor, request, values)
    if python_exec is not None:
        placeholders["python_exec"] = python_exec
    brief = values.get("brief") or request.brief
    if brief is not None:
        brief_path = Path(str(brief)).expanduser().resolve()
        placeholders["brief"] = str(brief_path)
        brief_slug = str(values.get("brief_slug") or _default_brief_slug(brief_path, out))
        brief_out = out / "briefs" / brief_slug
        placeholders["brief_slug"] = brief_slug
        placeholders["brief_out"] = str(brief_out)
        placeholders["brief_copy"] = str(brief_out / "brief.txt")
    for port in executor.inputs:
        if port.default is not None and port.name not in values:
            placeholders[port.name] = _stringify_value(port.default)
    for key, value in values.items():
        if value is None:
            continue
        placeholders[key] = _stringify_value(value)
    for output in executor.outputs:
        output_path = _output_value(output, request, placeholders)
        placeholders[output.name] = output_path
        if output.placeholder:
            placeholders[output.placeholder] = output_path
    return placeholders


def _expand_input_arg_mappings(executor: ExecutorDefinition, values: Mapping[str, Any]) -> tuple[str, ...]:
    if executor.command is None or not executor.command.input_args:
        return ()
    argv: list[str] = []
    for mapping in executor.command.input_args:
        value = values.get(mapping.input)
        if not _has_value(value):
            if mapping.optional:
                continue
            raise ExecutorRunnerError(f"executor {executor.id!r} missing mapped input {mapping.input!r}")
        items = list(_iter_input_values(value))
        if len(items) > 1 and not mapping.repeatable:
            raise ExecutorRunnerError(f"executor {executor.id!r} input {mapping.input!r} is not repeatable")
        for item in items:
            if mapping.flag:
                argv.append(mapping.flag)
            argv.append(_stringify_value(item))
    return tuple(argv)


def _output_value(output: ExecutorOutput, request: ExecutorRunRequest, placeholders: Mapping[str, str]) -> str:
    if output.name in request.outputs:
        return _stringify_value(request.outputs[output.name])
    if output.placeholder and output.placeholder in request.outputs:
        return _stringify_value(request.outputs[output.placeholder])
    if output.path_template:
        return _expand_placeholders(output.path_template, placeholders)
    return str((Path(request.out).expanduser().resolve() / output.name).resolve())


def _resolve_python_exec(executor: ExecutorDefinition, request: ExecutorRunRequest, values: Mapping[str, Any]) -> str | None:
    input_override = values.get("python_exec")
    if _has_value(input_override):
        return str(input_override)
    if _has_value(request.python_exec):
        return str(request.python_exec)
    if not _executor_uses_placeholder(executor, "python_exec"):
        return None
    if executor.kind == "external" and executor.isolation.mode == "subprocess":
        installed_python = executor_python_path(executor)
        if installed_python.is_file():
            return str(installed_python)
        raise ExecutorRunnerError(
            f"executor {executor.id!r} requires an installed Python environment; "
            f"run `python3 -m astrid executors install {executor.id}` or pass python_exec as an input override"
        )
    return sys.executable


def _executor_uses_placeholder(executor: ExecutorDefinition, placeholder: str) -> bool:
    if executor.command is None:
        return False
    needle = f"{{{placeholder}}}"
    if any(needle in part for part in executor.command.argv):
        return True
    if executor.command.cwd and needle in executor.command.cwd:
        return True
    return any(needle in value for value in executor.command.env.values())


def _expand_placeholders(value: str, placeholders: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in placeholders:
            raise ExecutorRunnerError(f"missing value for placeholder {{{key}}}")
        return placeholders[key]

    return _PLACEHOLDER_RE.sub(replace, value)


def _validate_required_inputs(executor: ExecutorDefinition, values: Mapping[str, Any]) -> None:
    missing = [
        port.name
        for port in executor.inputs
        if port.required and port.default is None and not _has_value(values.get(port.name))
    ]
    if missing:
        raise ExecutorRunnerError(f"executor {executor.id!r} missing required input(s): {', '.join(missing)}")


def _evaluate_condition(condition: ConditionSpec, values: Mapping[str, Any]) -> ConditionResult:
    if condition.kind == "always":
        return ConditionResult()
    if condition.kind == "requires_input":
        if not condition.input or not _has_value(values.get(condition.input)):
            raise ExecutorRunnerError(f"condition requires input {condition.input!r}")
        return ConditionResult()
    if condition.kind == "requires_file":
        candidate = values.get(condition.input) if condition.input else condition.path
        if not _has_value(candidate):
            raise ExecutorRunnerError("condition requires a file path")
        path = Path(str(candidate)).expanduser()
        if not path.is_file():
            raise ExecutorRunnerError(f"condition requires file: {path}")
        return ConditionResult()
    if condition.kind == "skip_if_input" and condition.input and _has_value(values.get(condition.input)):
        return ConditionResult(skipped=True, reason=f"input {condition.input!r} is set")
    raise ExecutorRunnerError(f"unsupported condition kind {condition.kind!r}")


def _step_for_executor(executor: ExecutorDefinition) -> Any:
    step_name = executor.metadata.get("pipeline_step")
    if not isinstance(step_name, str):
        raise ExecutorRunnerError(f"built-in executor {executor.id!r} is missing metadata.pipeline_step")
    steps = _pipeline_steps_by_name()
    if step_name not in steps:
        raise ExecutorRunnerError(f"built-in executor {executor.id!r} references unknown pipeline step {step_name!r}")
    return steps[step_name]


def _request_values(request: ExecutorRunRequest) -> dict[str, Any]:
    values = dict(request.inputs)
    if request.brief is not None and "brief" not in values:
        values["brief"] = request.brief
    if request.python_exec is not None and "python_exec" not in values:
        values["python_exec"] = request.python_exec
    values.setdefault("verbose", request.verbose)
    return values


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _optional_path(value: Any) -> Path | None:
    if value is None or value == "":
        return None
    return Path(str(value)).expanduser().resolve()


def _optional_asset_path(value: Any) -> Path | str | None:
    if value is None or value == "":
        return None
    text = str(value)
    pipeline = _pipeline_module()
    if pipeline.asset_cache.is_url(text):
        return text
    return Path(text).expanduser().resolve()


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _as_string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def _parse_asset_pairs(values: list[str]) -> list[tuple[str, Path | str]]:
    pairs: list[tuple[str, Path | str]] = []
    for raw in values:
        if "=" not in raw:
            raise ExecutorRunnerError(f"invalid asset value {raw!r}; expected KEY=PATH")
        key, path_text = raw.split("=", 1)
        key = key.strip()
        path_text = path_text.strip()
        if not key or not path_text:
            raise ExecutorRunnerError(f"invalid asset value {raw!r}; expected KEY=PATH")
        pipeline = _pipeline_module()
        if pipeline.asset_cache.is_url(path_text):
            pairs.append((key, path_text))
        else:
            pairs.append((key, Path(path_text).expanduser().resolve()))
    return pairs


def _normalize_extra_args(value: Any) -> dict[str, list[str]]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ExecutorRunnerError("extra_args must be an object keyed by step name")
    return {str(key): _as_string_list(raw_values) for key, raw_values in value.items()}


def _default_brief_slug(brief: Path, out: Path) -> str:
    generic_brief_names = {"brief", "plan", "prompt"}
    return out.name if brief.stem.lower() in generic_brief_names else brief.stem


def _stringify_value(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


def _iter_input_values(value: Any) -> tuple[Any, ...]:
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, tuple):
        return value
    return (value,)


def _required_input(inputs: Mapping[str, Any], key: str) -> str:
    value = inputs.get(key)
    if value in (None, ""):
        raise ExecutorRunnerError(f"{key} is required")
    return str(value)


def _optional_input(inputs: Mapping[str, Any], key: str) -> Any:
    value = inputs.get(key)
    if value in (None, ""):
        return None
    return value


__all__ = [
    "ConditionResult",
    "ExecutorCapabilityRunner",
    "ExecutorRunRequest",
    "ExecutorRunResult",
    "ExecutorRunnerError",
    "build_pipeline_context",
    "build_executor_command",
    "check_executor_binaries",
    "evaluate_conditions",
    "run_executor",
]
