"""Execution helpers for Astrid orchestrator definitions."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, Mapping

from astrid.core._shared.capability_common import (
    _PLACEHOLDER_RE,
    _expand_placeholders,
    _has_cli_option,
    _output_value,
    _stringify_value,
    _validate_required_inputs,
)
from astrid.core.contracts.capability_runner import CapabilityRunner
from astrid.core.contracts.run_status import RunStatus
from astrid.core.project.run import (
    ProjectRunContext,
    _project_subprocess_env,
    finalize_project_run,
    prepare_project_run,
    project_run_env,
    reject_project_with_out,
)
from astrid.core.project.guidance import (
    format_project_required_guidance,
    selected_project,
)
from astrid.core.runtime import (
    InProcessExecutionPreconditionError,
    InProcessInvocationError,
    invoke_in_process_command,
)
from astrid.core.runtime._normalize import normalize_python_runtime_result
from astrid.core.runtime.log_capture import (
    open_run_log_capture,
    run_subprocess_with_capture,
)
from astrid.core.subprocess_env import build_child_subprocess_env

from .registry import OrchestratorRegistry, load_default_registry
from .schema import (
    OrchestratorDefinition,
    OrchestratorKind,
    OrchestratorValidationError,
    RuntimeKind,
)


class OrchestratorRunnerError(OrchestratorValidationError):
    """Raised when a orchestrator cannot be prepared or executed."""


@dataclass(frozen=True)
class OrchestratorRunRequest:
    orchestrator_id: str
    out: Path | str | None = None
    project: str | None = None
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    brief: Path | str | None = None
    orchestrator_args: tuple[str, ...] = ()
    dry_run: bool = False
    python_exec: str | None = None
    verbose: bool = False
    execution_mode: Literal["subprocess", "in_process"] = "subprocess"
    project_was_auto_resolved: bool = False
    invocation: str = "cli"
    run_root: Path | str | None = None


@dataclass(frozen=True)
class OrchestratorRunError:
    message: str
    kind: str = "runtime"

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "message": self.message}


@dataclass(frozen=True)
class OrchestratorPlanStep:
    id: str
    kind: str = "command"
    command: tuple[str, ...] = ()
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "command": list(self.command),
        }
        if self.description:
            payload["description"] = self.description
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True)
class OrchestratorPlan:
    steps: tuple[OrchestratorPlanStep, ...] = ()
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"steps": [step.to_dict() for step in self.steps]}
        if self.summary:
            payload["summary"] = self.summary
        return payload


@dataclass(frozen=True)
class OrchestratorRunResult:
    orchestrator_id: str
    kind: OrchestratorKind
    runtime_kind: RuntimeKind
    command: tuple[str, ...] = ()
    planned_commands: tuple[tuple[str, ...], ...] = ()
    cwd: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    returncode: int | None = None
    dry_run: bool = False
    outputs: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[OrchestratorRunError, ...] = ()
    plan: OrchestratorPlan | None = None

    @property
    def ok(self) -> bool:
        return not self.errors and (self.returncode is None or self.returncode == 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "orchestrator_id": self.orchestrator_id,
            "kind": self.kind,
            "runtime_kind": self.runtime_kind,
            "command": list(self.command),
            "planned_commands": [list(command) for command in self.planned_commands],
            "cwd": self.cwd,
            "env": dict(self.env),
            "returncode": self.returncode,
            "dry_run": self.dry_run,
            "outputs": dict(self.outputs),
            "errors": [error.to_dict() for error in self.errors],
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "ok": self.ok,
        }


class OrchestratorCapabilityRunner(CapabilityRunner[OrchestratorRunRequest, OrchestratorRunResult, OrchestratorDefinition]):
    """Orchestrator binding of the shared :class:`CapabilityRunner` skeleton."""

    def load_default_registry(self) -> OrchestratorRegistry:
        return load_default_registry()

    def request_id(self, request: OrchestratorRunRequest) -> str:
        return request.orchestrator_id

    def build_command(
        self, request: OrchestratorRunRequest, registry: object | None = None
    ) -> tuple[str, ...]:
        active_registry = registry if isinstance(registry, OrchestratorRegistry) else self.load_default_registry()
        return build_orchestrator_command(request, active_registry)

    def prepare_project(
        self, request: OrchestratorRunRequest, definition: OrchestratorDefinition
    ) -> tuple[ProjectRunContext | None, OrchestratorRunRequest]:
        return _prepare_project_request(request, definition)

    def resolve_project_request(
        self, request: OrchestratorRunRequest, definition: OrchestratorDefinition
    ) -> OrchestratorRunRequest:
        return _resolve_project_request(request, definition)

    def is_dry_run(self, request: OrchestratorRunRequest, definition: OrchestratorDefinition) -> bool:
        return bool(request.dry_run)

    def prepare_dry_run_request(
        self, request: OrchestratorRunRequest, definition: OrchestratorDefinition
    ) -> OrchestratorRunRequest:
        return _prepare_dry_run_request(request, definition)

    def run_inner(self, request: OrchestratorRunRequest, definition: OrchestratorDefinition) -> OrchestratorRunResult:
        return _run_orchestrator_inner(request, definition)

    def finalize_project(
        self,
        context: ProjectRunContext,
        request: OrchestratorRunRequest,
        *,
        status: RunStatus,
        returncode: int | None,
        error: BaseException | str | None = None,
    ) -> None:
        _finalize_project_orchestrator(context, request, status=status, returncode=returncode, error=error)

    def status_for_result(self, result: OrchestratorRunResult) -> RunStatus:
        return _project_status_for_result(result)

    def result_returncode(self, result: OrchestratorRunResult) -> int | None:
        return result.returncode


_ORCHESTRATOR_RUNNER = OrchestratorCapabilityRunner()


def run_orchestrator(request: OrchestratorRunRequest, registry: OrchestratorRegistry | None = None) -> OrchestratorRunResult:
    return _ORCHESTRATOR_RUNNER.run(request, registry)



def _run_orchestrator_inner(request: OrchestratorRunRequest, orchestrator: OrchestratorDefinition) -> OrchestratorRunResult:
    values = _request_values(request, orchestrator)
    _validate_out_requirement(orchestrator, request)
    _validate_required_inputs(
        orchestrator.id, orchestrator.inputs, values, noun="orchestrator", error_cls=OrchestratorRunnerError
    )
    if orchestrator.runtime.kind == "python":
        return _ensure_dry_run_plan(_run_python_orchestrator(orchestrator, request))
    if orchestrator.runtime.kind == "command":
        return _ensure_dry_run_plan(_run_command_orchestrator(orchestrator, request, values))
    raise OrchestratorRunnerError(f"unsupported orchestrator runtime kind {orchestrator.runtime.kind!r}")


def build_orchestrator_command(request: OrchestratorRunRequest, registry: OrchestratorRegistry | None = None) -> tuple[str, ...]:
    active_registry = registry or load_default_registry()
    orchestrator = active_registry.get(request.orchestrator_id)
    values = _request_values(request, orchestrator)
    _validate_out_requirement(orchestrator, request)
    _validate_required_inputs(
        orchestrator.id, orchestrator.inputs, values, noun="orchestrator", error_cls=OrchestratorRunnerError
    )
    if orchestrator.runtime.kind != "command":
        raise OrchestratorRunnerError(f"orchestrator {orchestrator.id!r} does not use a command runtime")
    command, _, _ = _expand_command_runtime(orchestrator, request, values)
    return command


def _run_python_orchestrator(orchestrator: OrchestratorDefinition, request: OrchestratorRunRequest) -> OrchestratorRunResult:
    runtime = orchestrator.runtime
    if not runtime.module or not runtime.function:
        raise OrchestratorRunnerError(f"orchestrator {orchestrator.id!r} has an invalid Python runtime")
    try:
        module = importlib.import_module(runtime.module)
    except Exception as exc:
        raise OrchestratorRunnerError(f"failed to import orchestrator runtime module {runtime.module!r}: {exc}") from exc
    target = getattr(module, runtime.function, None)
    if not callable(target):
        raise OrchestratorRunnerError(f"orchestrator runtime target {runtime.module}.{runtime.function} is not callable")
    try:
        raw_result = target(request, orchestrator)
    except OrchestratorRunnerError:
        raise
    except Exception as exc:
        raise OrchestratorRunnerError(f"orchestrator {orchestrator.id!r} Python runtime failed: {exc}") from exc
    return _normalize_python_result(orchestrator, request, raw_result)


def _run_command_orchestrator(
    orchestrator: OrchestratorDefinition,
    request: OrchestratorRunRequest,
    values: Mapping[str, Any],
) -> OrchestratorRunResult:
    command, cwd, env = _expand_command_runtime(orchestrator, request, values)
    if request.dry_run:
        planned_commands = (command,)
        return OrchestratorRunResult(
            orchestrator_id=orchestrator.id,
            kind=orchestrator.kind,
            runtime_kind="command",
            command=command,
            planned_commands=planned_commands,
            cwd=cwd,
            env=env,
            returncode=None,
            dry_run=True,
            plan=_plan_from_commands(planned_commands, prefix=orchestrator.id),
        )
    if request.execution_mode == "in_process":
        return _run_in_process_command_orchestrator(
            orchestrator,
            request,
            command=command,
            cwd=cwd,
            env=env,
        )
    effective_env = _command_subprocess_env(orchestrator, request, env)
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
    return OrchestratorRunResult(
        orchestrator_id=orchestrator.id,
        kind=orchestrator.kind,
        runtime_kind="command",
        command=command,
        planned_commands=(command,),
        cwd=cwd,
        env=env,
        returncode=returncode,
    )


def _run_in_process_command_orchestrator(
    orchestrator: OrchestratorDefinition,
    request: OrchestratorRunRequest,
    *,
    command: tuple[str, ...],
    cwd: str | None,
    env: Mapping[str, str],
) -> OrchestratorRunResult:
    effective_env = _command_subprocess_env(orchestrator, request, env)
    log_capture = (
        open_run_log_capture(request.run_root)
        if request.run_root is not None and not request.project_was_auto_resolved
        else None
    )
    try:
        with log_capture or nullcontext():
            result = invoke_in_process_command(
                command,
                metadata=orchestrator.metadata,
                owner_id=orchestrator.id,
                cwd=cwd,
                env=effective_env,
                parent_env=os.environ,
                stdout_log=None if log_capture is None else log_capture.stdout,
                stderr_log=None if log_capture is None else log_capture.stderr,
            )
    except InProcessExecutionPreconditionError as exc:
        return _in_process_orchestrator_error_result(
            orchestrator,
            command=command,
            cwd=cwd,
            env=env,
            error=OrchestratorRunError(
                message=str(exc),
                kind="precondition",
            ),
        )
    except InProcessInvocationError as exc:
        return _in_process_orchestrator_error_result(
            orchestrator,
            command=command,
            cwd=cwd,
            env=env,
            error=OrchestratorRunError(
                message=str(exc),
                kind="runtime",
            ),
        )
    return OrchestratorRunResult(
        orchestrator_id=orchestrator.id,
        kind=orchestrator.kind,
        runtime_kind="command",
        command=command,
        planned_commands=(command,),
        cwd=cwd,
        env=dict(env),
        returncode=result.returncode,
    )


def _in_process_orchestrator_error_result(
    orchestrator: OrchestratorDefinition,
    *,
    command: tuple[str, ...],
    cwd: str | None,
    env: Mapping[str, str],
    error: OrchestratorRunError,
) -> OrchestratorRunResult:
    return OrchestratorRunResult(
        orchestrator_id=orchestrator.id,
        kind=orchestrator.kind,
        runtime_kind="command",
        command=command,
        planned_commands=(command,),
        cwd=cwd,
        env=dict(env),
        returncode=1,
        errors=(error,),
    )


def _expand_command_runtime(
    orchestrator: OrchestratorDefinition,
    request: OrchestratorRunRequest,
    values: Mapping[str, Any],
) -> tuple[tuple[str, ...], str | None, dict[str, str]]:
    command_spec = orchestrator.runtime.command
    if command_spec is None:
        raise OrchestratorRunnerError(f"orchestrator {orchestrator.id!r} has no command runtime")
    placeholders = _placeholder_values(orchestrator, request, values)
    argv: list[str] = []
    for part in command_spec.argv:
        if part == "{orchestrator_args}":
            argv.extend(request.orchestrator_args)
        else:
            argv.append(
                _expand_placeholders(part, placeholders, error_cls=OrchestratorRunnerError)
            )
    cwd = (
        _expand_placeholders(command_spec.cwd, placeholders, error_cls=OrchestratorRunnerError)
        if command_spec.cwd
        else None
    )
    env = {
        key: _expand_placeholders(value, placeholders, error_cls=OrchestratorRunnerError)
        for key, value in command_spec.env.items()
    }
    return tuple(argv), cwd, env


def _normalize_python_result(
    orchestrator: OrchestratorDefinition,
    request: OrchestratorRunRequest,
    raw_result: Any,
) -> OrchestratorRunResult:
    # Already a result — pass through with dry-run plan if needed.
    if isinstance(raw_result, OrchestratorRunResult):
        return _ensure_dry_run_plan(raw_result)

    # Rich dict normalisation (planned_commands, errors, plan, etc.).
    if isinstance(raw_result, dict):
        return _result_from_mapping(orchestrator, request, raw_result)

    # Delegate the remaining patterns (None, int, SystemExit, Mapping,
    # objects with a returncode attribute) to the shared helper.
    try:
        normalized = normalize_python_runtime_result(raw_result)
    except ValueError as exc:
        raise OrchestratorRunnerError(
            f"orchestrator {orchestrator.id!r} returned unsupported result "
            f"type {type(raw_result).__name__}; "
            "expected OrchestratorRunResult, dict, int, or None"
        ) from exc

    return _ensure_dry_run_plan(OrchestratorRunResult(
        orchestrator_id=orchestrator.id,
        kind=orchestrator.kind,
        runtime_kind="python",
        returncode=None if request.dry_run else normalized.returncode,
        dry_run=request.dry_run,
    ))


def _result_from_mapping(
    orchestrator: OrchestratorDefinition,
    request: OrchestratorRunRequest,
    raw: Mapping[str, Any],
) -> OrchestratorRunResult:
    command = _tuple_of_strings(raw.get("command", ()), "command")
    planned_commands = _planned_commands(raw.get("planned_commands", (command,) if command else ()))
    errors = tuple(
        error if isinstance(error, OrchestratorRunError) else OrchestratorRunError(str(error))
        for error in raw.get("errors", ())
    )
    returncode = raw.get("returncode")
    if request.dry_run and returncode is not None:
        returncode = None
    elif returncode is not None:
        returncode = int(returncode)
    plan = _plan_from_raw(raw.get("plan")) if "plan" in raw else None
    return _ensure_dry_run_plan(OrchestratorRunResult(
        orchestrator_id=str(raw.get("orchestrator_id") or orchestrator.id),
        kind=str(raw.get("kind") or orchestrator.kind),
        runtime_kind=str(raw.get("runtime_kind") or "python"),
        command=command,
        planned_commands=planned_commands,
        cwd=_optional_string(raw.get("cwd")),
        env={str(key): str(value) for key, value in dict(raw.get("env", {})).items()},
        returncode=returncode,
        dry_run=bool(raw.get("dry_run", request.dry_run)),
        outputs=dict(raw.get("outputs", {})),
        errors=errors,
        plan=plan,
    ))


def _ensure_dry_run_plan(result: OrchestratorRunResult) -> OrchestratorRunResult:
    if not result.dry_run or result.plan is not None:
        return result
    return replace(result, plan=_plan_from_commands(result.planned_commands, prefix=result.orchestrator_id))


def _plan_from_commands(commands: tuple[tuple[str, ...], ...], *, prefix: str) -> OrchestratorPlan:
    steps = tuple(
        OrchestratorPlanStep(
            id=f"{prefix}.step_{index + 1}",
            kind="command",
            command=command,
        )
        for index, command in enumerate(commands)
    )
    return OrchestratorPlan(steps=steps)


def _plan_from_raw(raw: Any) -> OrchestratorPlan | None:
    if raw is None:
        return None
    if isinstance(raw, OrchestratorPlan):
        return raw
    if not isinstance(raw, Mapping):
        raise OrchestratorRunnerError("plan must be an object")
    raw_steps = raw.get("steps", ())
    if not isinstance(raw_steps, (list, tuple)):
        raise OrchestratorRunnerError("plan.steps must be a list")
    return OrchestratorPlan(
        steps=tuple(_plan_step_from_raw(item, f"plan.steps[{index}]") for index, item in enumerate(raw_steps)),
        summary=str(raw.get("summary") or ""),
    )


def _plan_step_from_raw(raw: Any, path: str) -> OrchestratorPlanStep:
    if isinstance(raw, OrchestratorPlanStep):
        return raw
    if not isinstance(raw, Mapping):
        raise OrchestratorRunnerError(f"{path} must be an object")
    step_id = raw.get("id")
    if not isinstance(step_id, str) or not step_id.strip():
        raise OrchestratorRunnerError(f"{path}.id must be a non-empty string")
    return OrchestratorPlanStep(
        id=step_id,
        kind=str(raw.get("kind") or "command"),
        command=_tuple_of_strings(raw.get("command", ()), f"{path}.command"),
        description=str(raw.get("description") or ""),
        metadata=dict(raw.get("metadata", {})),
    )


def _placeholder_values(orchestrator: OrchestratorDefinition, request: OrchestratorRunRequest, values: Mapping[str, Any]) -> dict[str, str]:
    placeholders: dict[str, str] = {
        "python_exec": str(values.get("python_exec") or request.python_exec or sys.executable),
        "orchestrator_args": " ".join(request.orchestrator_args),
        "verbose": str(bool(values.get("verbose", request.verbose))).lower(),
    }
    if request.out is not None:
        placeholders["out"] = str(Path(request.out).expanduser().resolve())
    brief = values.get("brief") or request.brief
    if brief is not None:
        placeholders["brief"] = str(Path(str(brief)).expanduser().resolve())
    for key, value in values.items():
        if value is None:
            continue
        if key == "verbose":
            placeholders[key] = str(bool(value)).lower()
        else:
            placeholders[key] = _stringify_value(value)
    for output in orchestrator.outputs:
        output_path = _output_value(output, request, placeholders, error_cls=OrchestratorRunnerError)
        placeholders[output.name] = output_path
        if output.placeholder:
            placeholders[output.placeholder] = output_path
    return placeholders


def _prepare_project_request(
    request: OrchestratorRunRequest,
    orchestrator: OrchestratorDefinition,
) -> tuple[ProjectRunContext | None, OrchestratorRunRequest]:
    if not request.project:
        return None, request
    if not request.project_was_auto_resolved:
        reject_project_with_out(request.project, request.out)
    if _orchestrator_requires_output_path(orchestrator) and _has_cli_option(tuple(request.orchestrator_args), "--out"):
        raise OrchestratorRunnerError(
            f"--project cannot be combined with passthrough --out for {orchestrator.id}"
        )
    record_out = request.out if request.out not in (None, "") else None
    context = prepare_project_run(
        request.project,
        tool_id=orchestrator.id,
        kind="orchestrator",
        argv=_project_argv(request),
        metadata={
            "dry_run": bool(request.dry_run),
            "project_resolution": (
                "attached" if request.project_was_auto_resolved else "explicit"
            ),
        },
        auto_bound=False,
        record_out=record_out,
        requires_timeline=False if request.project_was_auto_resolved else None,
        invocation=request.invocation,
    )
    effective_out = request.out if record_out is not None else context.run_root
    updated = _request_with_effective_out(request, orchestrator, effective_out)
    return context, replace(updated, run_root=context.run_root)


def _orchestrator_requires_output_path(orchestrator: OrchestratorDefinition) -> bool:
    return bool(orchestrator.metadata.get("requires_output_path"))


def _request_with_effective_out(
    request: OrchestratorRunRequest,
    orchestrator: OrchestratorDefinition,
    out: str | Path,
) -> OrchestratorRunRequest:
    effective_out = Path(out).expanduser().resolve()
    args = tuple(request.orchestrator_args)
    if _orchestrator_requires_output_path(orchestrator) and not _has_cli_option(args, "--out"):
        args = (*args, "--out", str(effective_out))
    return replace(request, out=effective_out, orchestrator_args=args)


def _project_argv(request: OrchestratorRunRequest) -> list[str]:
    argv = ["orchestrators", "run", request.orchestrator_id]
    if request.project:
        argv.extend(["--project", request.project])
    if request.brief:
        argv.extend(["--brief", str(request.brief)])
    for key, value in request.inputs.items():
        argv.extend(["--input", f"{key}={_stringify_value(value)}"])
    if request.dry_run:
        argv.append("--dry-run")
    if request.python_exec:
        argv.extend(["--python-exec", request.python_exec])
    if request.verbose:
        argv.append("--verbose")
    if request.orchestrator_args:
        argv.append("--")
        argv.extend(request.orchestrator_args)
    return argv


def _project_status_for_result(result: OrchestratorRunResult) -> RunStatus:
    if result.dry_run:
        return RunStatus.SKIPPED
    if not result.ok:
        return RunStatus.FAILED
    return RunStatus.COMPLETED


def _finalize_project_orchestrator(
    context: ProjectRunContext,
    request: OrchestratorRunRequest,
    *,
    status: RunStatus,
    returncode: int | None,
    error: BaseException | str | None = None,
) -> None:
    metadata = {"dry_run": bool(request.dry_run)}
    finalize_project_run(
        context,
        status=status,
        returncode=returncode,
        error=error,
        metadata=metadata,
        artifact_roots=[context.run_root],
    )


def _resolve_project_request(
    request: OrchestratorRunRequest,
    orchestrator: OrchestratorDefinition,
) -> OrchestratorRunRequest:
    project, source = selected_project(request.project)
    if source == "explicit":
        return request
    if project is not None:
        return replace(
            request,
            project=project,
            project_was_auto_resolved=True,
        )
    raise OrchestratorRunnerError(
        format_project_required_guidance(operation="orchestrator run")
    )


def _prepare_dry_run_request(
    request: OrchestratorRunRequest,
    orchestrator: OrchestratorDefinition,
) -> OrchestratorRunRequest:
    if request.out not in (None, ""):
        return _request_with_effective_out(request, orchestrator, request.out)
    placeholder = (
        Path.cwd() / ".astrid-dry-run" / request.orchestrator_id.replace(".", "-")
    ).resolve()
    return _request_with_effective_out(request, orchestrator, placeholder)


def _command_subprocess_env(
    orchestrator: OrchestratorDefinition,
    request: OrchestratorRunRequest,
    command_env: Mapping[str, str],
) -> dict[str, str]:
    return build_child_subprocess_env(
        explicit_env={
            **command_env,
            **_project_subprocess_env(request),
            "ASTRID_INTERNAL_INVOCATION": "1",
        },
        passthrough=orchestrator.isolation.env_passthrough,
        declared_passthrough=orchestrator.isolation.env_passthrough,
    )


def _validate_out_requirement(orchestrator: OrchestratorDefinition, request: OrchestratorRunRequest) -> None:
    if request.out is not None:
        return
    if _orchestrator_requires_output_path(orchestrator):
        raise OrchestratorRunnerError(f"--out is required for {orchestrator.id}")
    if request.dry_run:
        return
    if orchestrator.runtime.kind == "command" and _command_runtime_requires_out(orchestrator, request):
        raise OrchestratorRunnerError("--out is required for command runtime placeholders")
    raise OrchestratorRunnerError("--out is required for orchestrator execution")


def _command_runtime_requires_out(orchestrator: OrchestratorDefinition, request: OrchestratorRunRequest) -> bool:
    command = orchestrator.runtime.command
    if command is None:
        return False
    values = [*command.argv]
    if command.cwd:
        values.append(command.cwd)
    values.extend(command.env.values())
    if any(_uses_placeholder(value, "out") for value in values):
        return True
    for output in orchestrator.outputs:
        if output.name in request.outputs or (output.placeholder and output.placeholder in request.outputs):
            continue
        if output.path_template is None or _uses_placeholder(output.path_template, "out"):
            return True
    return False


def _uses_placeholder(value: str, placeholder: str) -> bool:
    return placeholder in _PLACEHOLDER_RE.findall(value)


def _request_values(request: OrchestratorRunRequest, orchestrator: OrchestratorDefinition) -> dict[str, Any]:
    values = dict(request.inputs)
    for port in orchestrator.inputs:
        if port.default is not None and port.name not in values:
            values[port.name] = port.default
    if request.brief is not None and "brief" not in values:
        values["brief"] = request.brief
    if request.python_exec is not None and "python_exec" not in values:
        values["python_exec"] = request.python_exec
    values.setdefault("verbose", request.verbose)
    return values


def _planned_commands(raw: Any) -> tuple[tuple[str, ...], ...]:
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise OrchestratorRunnerError("planned_commands must be a list of command lists")
    commands: list[tuple[str, ...]] = []
    for index, item in enumerate(raw):
        commands.append(_tuple_of_strings(item, f"planned_commands[{index}]"))
    return tuple(commands)


def _tuple_of_strings(raw: Any, path: str) -> tuple[str, ...]:
    if raw is None or raw == ():
        return ()
    if not isinstance(raw, (list, tuple)):
        raise OrchestratorRunnerError(f"{path} must be a list")
    result: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str):
            raise OrchestratorRunnerError(f"{path}[{index}] must be a string")
        result.append(item)
    return tuple(result)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "OrchestratorCapabilityRunner",
    "OrchestratorRunError",
    "OrchestratorRunRequest",
    "OrchestratorRunResult",
    "OrchestratorRunnerError",
    "build_orchestrator_command",
    "run_orchestrator",
]
