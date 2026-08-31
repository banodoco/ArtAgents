"""Execution helpers for Astrid executor definitions."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, replace
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from astrid.core._shared.capability_common import (
    _PLACEHOLDER_RE,
    _expand_placeholders,
    _has_value,
    _output_value,
    _stringify_value,
    _validate_required_inputs,
)
from astrid.core.contracts.capability_runner import CapabilityRunner
from astrid.core.contracts.exec_error import (
    ExecError,
    error_from_missing_binaries,
    error_from_returncode,
)
from astrid.core.contracts.project_theme import ProjectStyleSnapshot
from astrid.core.contracts.run_status import RunStatus
from astrid.core.contracts.scoped_config import SCOPE_REGISTRY, ScopeRequest
from astrid.core.env_vars import ASTRID_INTERNAL_INVOCATION, HYPE_ACTIVE_THEME
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.io.cas import executor_definition_digest
from astrid.core.project.guidance import (
    format_project_required_guidance,
    selected_project,
)
from astrid.core.project.ownership import require_project_owned_artifact
from astrid.core.project.runtime import (
    _project_subprocess_env,
    reject_project_with_out,
)
from astrid.core.runtime.log_capture import (
    open_run_log_capture,
    run_subprocess_with_capture,
)
from astrid.core.subprocess_env import build_child_subprocess_env

from .registry import ExecutorRegistry, load_default_registry
from .schema import (
    ConditionSpec,
    ExecutorDefinition,
    ExecutorKind,
    ExecutorValidationError,
)


class ExecutorRunnerError(ExecutorValidationError):
    """Raised when a executor cannot be prepared or executed."""


#: Module path of the asset cache helper re-exported by every pipeline driver as
#: ``<pipeline_module>.asset_cache``. Imported directly (a sibling pack executor,
#: not the orchestrator tier) by request-free helpers that only need ``is_url``.
_ASSET_CACHE_MODULE = "astrid.packs.training.executors.asset_cache.run"


@lru_cache(maxsize=None)
def _pipeline_module(runtime_module: str):
    """Import a pipeline driver module by its dotted path.

    The path is supplied by the orchestrator-tier caller via the executor
    manifest (``metadata.pipeline_module``); the executor never reaches up into
    ``astrid.core.execution.orchestrator`` to discover it.
    """
    if not isinstance(runtime_module, str) or not runtime_module:
        raise ExecutorRunnerError("pipeline executor manifest is missing metadata.pipeline_module")
    # Pipeline drivers are implementation modules shared by the canonical
    # runner and the lower-level orchestrator.  Their module files retain the
    # public-entrypoint guard, so importing one for SDK dispatch must carry the
    # same internal marker as the runner's subprocess command without leaking
    # that marker into the caller's environment.
    previous = os.environ.get(ASTRID_INTERNAL_INVOCATION)
    os.environ[ASTRID_INTERNAL_INVOCATION] = "1"
    try:
        return import_module(runtime_module)
    finally:
        if previous is None:
            os.environ.pop(ASTRID_INTERNAL_INVOCATION, None)
        else:
            os.environ[ASTRID_INTERNAL_INVOCATION] = previous


@lru_cache(maxsize=1)
def _asset_cache_module():
    return import_module(_ASSET_CACHE_MODULE)


def _pipeline_module_for_executor(executor: ExecutorDefinition):
    """Resolve the pipeline driver module hosting this executor's steps.

    A pipeline-step executor declares ``metadata.command_builder`` as
    ``<pipeline_module>.build_pool_steps``; the driver module (which also owns
    ``STEP_ORDER``) is that path minus the trailing function name. Deriving it
    from ``command_builder`` keeps a single source of truth — every pipeline-step
    executor already declares it, so a new one needs no extra field — and keeps
    the executor decoupled from ``astrid.core.execution.orchestrator``.
    """
    command_builder = executor.metadata.get("command_builder")
    if not isinstance(command_builder, str) or "." not in command_builder:
        raise ExecutorRunnerError(
            f"built-in executor {executor.id!r} is missing metadata.command_builder"
        )
    return _pipeline_module(command_builder.rsplit(".", 1)[0])


def _pipeline_steps_by_name(executor: ExecutorDefinition) -> Mapping[str, Any]:
    pipeline = _pipeline_module_for_executor(executor)
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
    project_style: ProjectStyleSnapshot | Mapping[str, Any] | None = None
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    brief: Path | str | None = None
    dry_run: bool = False
    check_binaries: bool = False
    python_exec: str | None = None
    verbose: bool = False
    argv: tuple[str, ...] = ()
    project_was_auto_resolved: bool = False
    invocation: str = "cli"
    projects_root: Path | str | None = None
    run_root: Path | str | None = None
    run_id: str | None = None
    project_run_metadata: Mapping[str, Any] = field(default_factory=dict)
    expected_executor_version: str | None = None


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
    # ── A1 identity fields (backward-compatible defaults) ─────────────────
    run_root: Path | str | None = None
    outputs: Mapping[str, Any] = field(default_factory=dict)
    executor_version: str = ""  # derived from executor_definition_digest
    run_id: str | None = None

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

    def validate_definition(
        self, request: ExecutorRunRequest, definition: ExecutorDefinition
    ) -> None:
        expected = request.expected_executor_version
        actual = executor_definition_digest(definition)
        if expected is not None and expected != actual:
            raise ExecutorRunnerError(
                f"executor definition changed after admission for {definition.id!r}; retry the invocation"
            )

    def build_command(
        self, request: ExecutorRunRequest, registry: ExecutorRegistry | None = None
    ) -> tuple[str, ...]:
        active_registry = registry or self.load_default_registry()
        executor = active_registry.get(request.executor_id)
        values = _request_values(request, executor)
        _validate_declared_input_choices(executor, values)
        _validate_required_inputs(
            executor.id, executor.inputs, values, noun="executor", error_cls=ExecutorRunnerError
        )
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

    def prepare_project(
        self, request: ExecutorRunRequest, definition: ExecutorDefinition
    ) -> tuple[object | None, ExecutorRunRequest]:
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
        context: object,
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


def _run_executor_inner(request: ExecutorRunRequest, executor: ExecutorDefinition) -> ExecutorRunResult:
    _validate_scoped_configs_at_dispatch(executor)
    values = _request_values(request, executor)
    _validate_declared_input_choices(executor, values)
    _validate_required_inputs(
        executor.id, executor.inputs, values, noun="executor", error_cls=ExecutorRunnerError
    )
    condition_result = evaluate_conditions(executor, values)
    if condition_result.skipped:
        return ExecutorRunResult(
            executor_id=executor.id,
            kind=executor.kind,
            payload={"executor_id": executor.id, "skipped": True, "skipped_reason": condition_result.reason},
            dry_run=request.dry_run,
            skipped=True,
            skipped_reason=condition_result.reason,
            run_id=request.run_id,
            run_root=request.run_root,
            executor_version=executor_definition_digest(executor),
        )

    missing_binaries = check_executor_binaries(executor) if request.check_binaries else ()
    if missing_binaries:
        return ExecutorRunResult(
            executor_id=executor.id,
            kind=executor.kind,
            payload={"executor_id": executor.id, "missing_binaries": list(missing_binaries)},
            dry_run=request.dry_run,
            missing_binaries=missing_binaries,
            run_id=request.run_id,
            run_root=request.run_root,
            executor_version=executor_definition_digest(executor),
        )

    if executor.kind == "built_in" and "pipeline_step" in executor.metadata:
        return _run_builtin_executor(executor, request)
    return _run_external_executor(executor, request, values)


def _resolve_declared_outputs(
    executor: ExecutorDefinition,
    request: ExecutorRunRequest,
) -> dict[str, str]:
    """Resolve declared-output paths and return only those that exist on disk.

    Uses only the ``executor.outputs`` declaration — never scans directories.
    Expected paths are derived from ``request.out`` (falling back to
    ``request.run_root``) via the same ``_placeholder_values`` pipeline that
    the executor command expansion uses.

    Returns an empty mapping when there are no declared outputs or when no
    base output directory (``out`` / ``run_root``) is available.
    """
    if not executor.outputs:
        return {}
    effective_out = request.out if request.out not in (None, "") else request.run_root
    if effective_out is None or effective_out == "":
        return {}
    try:
        temp_request = replace(request, out=effective_out)
        values = _request_values(temp_request)
        placeholders = _placeholder_values(executor, temp_request, values)
    except ExecutorRunnerError:
        return {}
    resolved: dict[str, str] = {}
    for output in executor.outputs:
        output_path_str = placeholders.get(output.name)
        if output_path_str and Path(output_path_str).exists():
            resolved[output.name] = output_path_str
    return resolved


def resolve_declared_output_paths(
    executor: ExecutorDefinition,
    request: ExecutorRunRequest,
) -> dict[str, str]:
    """Resolve declared-output paths *without* requiring files to exist on disk.

    This is the non-existence-filtering companion to
    :func:`_resolve_declared_outputs`.  It uses the same placeholder-resolution
    pipeline so callers can learn which paths *would* be produced by a run
    (e.g. for CAS cache-hit checks) before the run has executed and before
    those files have been written to disk.

    Returns an empty mapping when there are no declared outputs or when no
    base output directory (``out`` / ``run_root``) is available.
    """
    if not executor.outputs:
        return {}
    effective_out = request.out if request.out not in (None, "") else request.run_root
    if effective_out is None or effective_out == "":
        return {}
    try:
        temp_request = replace(request, out=effective_out)
        values = _request_values(temp_request)
        placeholders = _placeholder_values(executor, temp_request, values)
    except ExecutorRunnerError:
        return {}
    resolved: dict[str, str] = {}
    for output in executor.outputs:
        output_path_str = placeholders.get(output.name)
        if output_path_str:
            resolved[output.name] = output_path_str
    return resolved


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
    from astrid.core.theme import resolve_theme_dir, resolve_themes_root
    from astrid.core.theme.scope import resolve_style_scope

    values = _request_values(request, executor)
    effective_out = request.out if request.out not in (None, "") else request.run_root
    if effective_out in (None, ""):
        raise ExecutorRunnerError(
            f"executor {request.executor_id!r} requires an output or staging path"
        )
    out = Path(effective_out).expanduser().resolve()
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
    theme_val = values.get('theme')
    active_theme_scope = resolve_style_scope(ScopeRequest(
        explicit={'theme': theme_val} if theme_val is not None else None,
        project_slug=request.project,
        env=dict(os.environ),
        project_style=request.project_style,
    ))
    active_theme = active_theme_scope.theme_dir
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
        return _run_explicit_command_executor(executor, request, _request_values(request, executor))
    pipeline = _pipeline_module_for_executor(executor)
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
            run_id=request.run_id,
            run_root=request.run_root,
            executor_version=executor_definition_digest(executor),
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
        run_id=request.run_id,
        run_root=request.run_root,
        executor_version=executor_definition_digest(executor),
        outputs=_resolve_declared_outputs(executor, request) if returncode == 0 else {},
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
            run_id=request.run_id,
            run_root=request.run_root,
            executor_version=executor_definition_digest(executor),
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
        run_id=request.run_id,
        run_root=request.run_root,
        executor_version=executor_definition_digest(executor),
        outputs=_resolve_declared_outputs(executor, request) if returncode == 0 else {},
    )


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
    argv = tuple(
        _expand_placeholders(part, placeholders, error_cls=ExecutorRunnerError)
        for part in executor.command.argv
    )
    consumed = _consumed_input_names(executor)
    argv = _insert_input_arg_mappings(argv, executor, values)
    argv = (*argv, *_auto_forward_untemplated_inputs(executor, values, consumed))
    cwd = (
        _expand_placeholders(executor.command.cwd, placeholders, error_cls=ExecutorRunnerError)
        if executor.command.cwd
        else None
    )
    env = {
        key: _expand_placeholders(value, placeholders, error_cls=ExecutorRunnerError)
        for key, value in executor.command.env.items()
    }
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
    ) -> tuple[object | None, ExecutorRunRequest]:
    # Single-ledger cut: project runs are kernel-owned (RunRepository fan-out).
    # The runner retains the output directory as staging only; no run.json is
    # written here. The kernel admission path (sdk.invoke / CapabilityTaskHandler)
    # owns the authoritative run/task ledger. Preserve out as staging.
    if not request.project:
        return None, request
    _validate_project_owned_inputs(request, executor)
    if request.out in (None, ""):
        raise ExecutorRunnerError(
            "project-scoped executor execution requires kernel admission to "
            "supply a staging output directory"
        )
    if not request.project_was_auto_resolved:
        reject_project_with_out(request.project, request.out)
    # A project-scoped lower-level call may use caller output or a kernel-owned
    # staging root, but it must never mint a project run directory itself. The
    # SDK/kernel admission path supplies ``run_root`` before reaching here;
    # without either path, fail closed rather than creating an orphaned second
    # ledger surface under ``project/runs``.
    if request.out in (None, "") and request.run_root in (None, ""):
        raise ExecutorRunnerError(
            f"executor {request.executor_id!r} requires an output or staging path"
        )
    # Keep out unchanged as staging/output; run dir is output/staging only.
    return None, request


def _project_run_metadata(
    request: ExecutorRunRequest,
    executor: ExecutorDefinition,
) -> dict[str, Any]:
    declared = executor.metadata.get("run_metadata")
    if declared is not None and not isinstance(declared, Mapping):
        raise ExecutorRunnerError(
            f"executor {executor.id!r} metadata.run_metadata must be an object"
        )
    metadata = dict(declared or {})
    metadata.update(
        {
            "dry_run": bool(request.dry_run),
            "executor_version": executor_definition_digest(executor),
            "project_resolution": (
                "attached" if request.project_was_auto_resolved else "explicit"
            ),
        }
    )
    return metadata


def _validate_project_owned_inputs(
    request: ExecutorRunRequest,
    executor: ExecutorDefinition,
) -> None:
    """Fail closed for declared timeline/experiment inputs outside the project."""

    if not request.project:
        return
    for port in getattr(executor, "inputs", ()):
        artifact_type = port.artifact_type
        if not isinstance(artifact_type, str):
            continue
        normalized = artifact_type.strip().lower().replace("-", "_")
        if not (
            normalized == "timeline"
            or normalized.startswith("timeline/")
            or normalized == "experiment"
            or normalized.startswith("experiment/")
            or normalized in {"project_runs", "experiment_runs"}
        ):
            continue
        value = request.inputs.get(port.name)
        if not _has_value(value):
            continue
        for item in _iter_input_values(value):
            require_project_owned_artifact(
                request.project,
                normalized,
                _stringify_value(item),
                root=request.projects_root,
            )




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
    context: object,
    request: ExecutorRunRequest,
    *,
    status: RunStatus,
    returncode: int | None,
    error: BaseException | str | None = None,
) -> None:
    # Single-ledger cut: no authoritative run.json finalize here. The kernel
    # owns terminal status; this remains as a derived-projection hook (no-op
    # when called with a None context, which is the normal path). Run
    # directories are storage only.
    return


def _resolve_project_request(request: ExecutorRunRequest) -> ExecutorRunRequest:
    project, source = selected_project(request.project)
    if source == "explicit":
        return request
    if project is not None:
        return replace(
            request,
            project=project,
            project_was_auto_resolved=True,
        )
    raise ExecutorRunnerError(format_project_required_guidance(operation="executor run"))

def _prepare_dry_run_request(request: ExecutorRunRequest) -> ExecutorRunRequest:
    if request.out not in (None, ""):
        return request
    placeholder = (Path.cwd() / ".astrid-dry-run" / request.executor_id.replace(".", "-")).resolve()
    return replace(request, out=placeholder)


def _validate_scoped_configs_at_dispatch(executor: ExecutorDefinition) -> None:
    """Validate declared scoped_configs keys against SCOPE_REGISTRY at dispatch time.

    Called by _run_executor_inner before execution. Raises ExecutorValidationError for
    any key that has no registered resolver — shape-only validation at parse time means
    this is the first point where tier-3 registry state is consulted.
    """
    if not executor.scoped_configs:
        return
    import astrid.core.theme.scope  # noqa: F401 — side-effect: registers 'style'
    import astrid.core.util.credentials_scope  # noqa: F401 — side-effect: registers 'credentials.*'
    for key in executor.scoped_configs:
        if not SCOPE_REGISTRY.is_registered(key):
            raise ExecutorValidationError(
                f"executor {executor.id!r} declares unknown scoped_config key {key!r}"
            )


def _validate_declared_input_choices(
    executor: ExecutorDefinition, values: Mapping[str, Any]
) -> None:
    """Validate manifest-declared input enums before command construction.

    Most constrained inputs are enforced by a capability's own argparse
    parser.  Dry-run intentionally does not start that subprocess, however,
    so small dispatcher capabilities can declare their enum in metadata and
    receive the same typed validation before a command is admitted or built.
    """
    choices = executor.metadata.get("input_choices")
    if isinstance(choices, Mapping):
        for input_name, raw_options in choices.items():
            if not isinstance(input_name, str) or not isinstance(raw_options, (list, tuple)):
                continue
            value = values.get(input_name)
            if value is None:
                continue
            options = tuple(str(option) for option in raw_options)
            if str(value) in options:
                continue
            rendered = ", ".join(options)
            raise ExecutorRunnerError(
                f"invalid {input_name} {value!r} for executor {executor.id!r}; "
                f"valid options: {rendered}; "
                f"recovery: retry with --{input_name.replace('_', '-')} "
                f"<one of: {rendered}>"
            )

    requirements = executor.metadata.get("input_requirements_by_choice")
    if not isinstance(requirements, Mapping):
        return
    for selector, raw_requirements in requirements.items():
        selected = values.get(str(selector))
        if selected is None or not isinstance(raw_requirements, Mapping):
            continue
        required_inputs = raw_requirements.get(str(selected))
        if not isinstance(required_inputs, (list, tuple)):
            continue
        missing = [
            str(name) for name in required_inputs
            if not _has_value(values.get(str(name)))
        ]
        if missing:
            names = ", ".join(missing)
            raise ExecutorRunnerError(
                f"missing required input(s) for {selector} {selected!r}: {names}; "
                f"recovery: provide --{missing[0].replace('_', '-')} and retry"
            )


def _emit_scoped_config_env(
    executor: ExecutorDefinition, request: ExecutorRunRequest
) -> dict[str, str]:
    """Resolve declared scoped_configs and return their subprocess env contributions.

    This is the SINGLE source of HYPE_ACTIVE_THEME emission for executor subprocesses.
    Concrete scope modules are guaranteed imported by _validate_scoped_configs_at_dispatch.
    """
    if not executor.scoped_configs:
        return {}
    import astrid.core.theme.scope  # noqa: F401 — ensure registration if called standalone
    import astrid.core.util.credentials_scope  # noqa: F401
    values = _request_values(request, executor)
    explicit: dict[str, Any] = {}
    theme_val = values.get("theme")
    if theme_val is not None:
        explicit["theme"] = theme_val
    scope_request = ScopeRequest(
        project_slug=request.project,
        env=dict(os.environ),
        explicit=explicit or None,
        project_style=request.project_style,
    )
    env: dict[str, str] = {}
    for key in executor.scoped_configs:
        if key == "style":
            from astrid.core.theme.scope import StyleScope
            result = SCOPE_REGISTRY.resolve("style", scope_request)
            if isinstance(result, StyleScope) and result.theme_dir is not None:
                env[HYPE_ACTIVE_THEME] = str(result.theme_dir)  # scoped-config emit
        elif key.startswith("credentials."):
            from astrid.core.util.credentials_scope import _PROVIDER_ENV, CredentialsScope
            result = SCOPE_REGISTRY.resolve(key, scope_request)
            if isinstance(result, CredentialsScope):
                provider_env = _PROVIDER_ENV.get(result.provider)
                if provider_env:
                    env[provider_env] = result.value  # scoped-config emit
    return env


def _command_subprocess_env(
    executor: ExecutorDefinition,
    request: ExecutorRunRequest,
    command_env: Mapping[str, str],
) -> dict[str, str]:
    external_pack_env = _external_pack_pythonpath_env(executor, command_env)
    project_env = _project_subprocess_env(request)
    scoped_env = _emit_scoped_config_env(executor, request)
    declared_secret_env = tuple(dict.fromkeys(
        str(name) for name in (
            *(executor.isolation.secrets_required or ()),
            *(executor.metadata.get("secrets_required") or ()),
            *(executor.metadata.get("required_env") or ()),
            *(executor.metadata.get("env") or ()),
        )
    ))
    explicit_env = {
        **command_env,
        **external_pack_env,
        **project_env,
        **scoped_env,
        "ASTRID_INTERNAL_INVOCATION": "1",
    }
    # Scoped credential resolution is the only allowed source for secret
    # values.  Pass them through the dedicated in-memory secret channel rather
    # than the ordinary explicit environment map.
    secret_values = {
        key: value for key, value in scoped_env.items() if key in declared_secret_env
    }
    for key in secret_values:
        explicit_env.pop(key, None)
    return build_child_subprocess_env(
        # Project routing attached to the admitted request is authoritative.
        # Overlay it onto the parent invariants as well as the explicit child
        # environment so an unrelated ambient ASTRID_PROJECTS_ROOT cannot
        # redirect execution after the request has been bound.
        parent={**os.environ, **project_env},
        explicit_env=explicit_env,
        passthrough=executor.isolation.env_passthrough,
        declared_passthrough=executor.isolation.env_passthrough,
        secret_values=secret_values,
        declared_secrets=declared_secret_env,
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
    effective_out = request.out if request.out not in (None, "") else request.run_root
    if effective_out in (None, ""):
        raise ExecutorRunnerError(
            f"executor {executor.id!r} requires an output or staging path"
        )
    out = Path(effective_out).expanduser().resolve()
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
        output_path = _output_value(output, request, placeholders, error_cls=ExecutorRunnerError)
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


def _insert_input_arg_mappings(
    argv: tuple[str, ...],
    executor: ExecutorDefinition,
    values: Mapping[str, Any],
) -> tuple[str, ...]:
    if executor.command is None or not executor.command.input_args:
        return argv
    result = list(argv)
    appended: list[str] = []
    for mapping in executor.command.input_args:
        expanded = _expand_one_input_arg_mapping(executor, values, mapping)
        if not expanded:
            continue
        if mapping.before is None:
            appended.extend(expanded)
            continue
        try:
            index = result.index(mapping.before)
        except ValueError:
            appended.extend(expanded)
            continue
        result[index:index] = expanded
    result.extend(appended)
    return tuple(result)


def _expand_one_input_arg_mapping(
    executor: ExecutorDefinition,
    values: Mapping[str, Any],
    mapping: Any,
) -> list[str]:
    value = values.get(mapping.input)
    if not _has_value(value):
        if mapping.optional:
            return []
        raise ExecutorRunnerError(f"executor {executor.id!r} missing mapped input {mapping.input!r}")
    items = list(_iter_input_values(value))
    if len(items) > 1 and not mapping.repeatable:
        raise ExecutorRunnerError(f"executor {executor.id!r} input {mapping.input!r} is not repeatable")
    argv: list[str] = []
    for item in items:
        if mapping.flag:
            argv.append(mapping.flag)
        argv.append(_stringify_value(item))
    return argv


def _resolve_python_exec(executor: ExecutorDefinition, request: ExecutorRunRequest, values: Mapping[str, Any]) -> str | None:
    input_override = values.get("python_exec")
    if _has_value(input_override):
        return str(input_override)
    if _has_value(request.python_exec):
        return str(request.python_exec)
    if not _executor_uses_placeholder(executor, "python_exec"):
        return None
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
    steps = _pipeline_steps_by_name(executor)
    if step_name not in steps:
        raise ExecutorRunnerError(f"built-in executor {executor.id!r} references unknown pipeline step {step_name!r}")
    return steps[step_name]


def _request_values(request: ExecutorRunRequest, executor: ExecutorDefinition | None = None) -> dict[str, Any]:
    values = dict(request.inputs)
    if request.brief is not None and "brief" not in values:
        values["brief"] = request.brief
    if request.python_exec is not None and "python_exec" not in values:
        values["python_exec"] = request.python_exec
    # A managed executor may expose its owning project as an explicit input
    # (for example timeline visualization's ``project_slug``) while the
    # public SDK carries the same identity in ``project=``.  Derive the
    # declared field before command expansion so in-process and subprocess
    # runners receive identical argv; callers can still override it when the
    # manifest deliberately allows a different standalone value.
    if (
        executor is not None
        and request.project
        and "project_slug" in {port.name for port in executor.inputs}
        and "project_slug" not in values
    ):
        values["project_slug"] = request.project
    values.setdefault("verbose", request.verbose)
    return values


def _optional_path(value: Any) -> Path | None:
    if value is None or value == "":
        return None
    return Path(str(value)).expanduser().resolve()


def _optional_asset_path(value: Any) -> Path | str | None:
    if value is None or value == "":
        return None
    text = str(value)
    if _asset_cache_module().is_url(text):
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
        if _asset_cache_module().is_url(path_text):
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


def _iter_input_values(value: Any) -> tuple[Any, ...]:
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, tuple):
        return value
    return (value,)


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
