"""Centralized in-process invocation for pack Python-module runtimes."""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from contextlib import contextmanager, nullcontext, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Callable, Iterator, Mapping

from astrid.core.pack.entrypoint import canonical_runtime_entrypoint
from astrid.core.pack.resolver import (
    CallableNotFoundError,
    PackResolverError,
    resolve_callable_from_metadata,
)
from astrid.core.subprocess_env import ASTRID_INTERNAL_INVOCATION, build_child_subprocess_env

from ._normalize import _system_exit_code, normalize_python_runtime_result
from .log_capture import TeeWriter


class InProcessInvocationError(RuntimeError):
    """Raised when in-process runtime execution cannot be completed."""


class InProcessExecutionPreconditionError(InProcessInvocationError):
    """Raised when a command cannot legally run in-process."""


@dataclass(frozen=True)
class InProcessCommand:
    """Classified `python -m astrid.packs...` command for local execution."""

    argv: tuple[str, ...]
    python_exec: str
    module: str
    module_argv: tuple[str, ...]


@dataclass(frozen=True)
class InProcessResult:
    """Normalized process-like result for in-process pack execution."""

    argv: tuple[str, ...]
    cwd: str | None
    env: Mapping[str, str]
    returncode: int
    payload: Mapping[str, Any]
    raw_result: Any = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def classify_in_process_command(
    argv: tuple[str, ...] | list[str],
    *,
    metadata: Mapping[str, Any],
    owner_id: str,
) -> InProcessCommand:
    """Validate and classify a pack command that is eligible for in-process execution."""

    command = tuple(str(token) for token in argv)
    if len(command) < 3:
        raise InProcessExecutionPreconditionError(
            f"{owner_id} requires a python -m astrid.packs... command for in-process execution"
        )
    python_exec, flag, module, *module_argv = command
    if flag != "-m" or not module.startswith("astrid.packs."):
        raise InProcessExecutionPreconditionError(
            f"{owner_id} only supports in-process pack module commands; got {command!r}"
        )
    runtime_module = metadata.get("runtime_module")
    if not isinstance(runtime_module, str) or not runtime_module:
        raise InProcessExecutionPreconditionError(
            f"{owner_id} manifest is missing metadata.runtime_module"
        )
    if runtime_module != module:
        raise InProcessExecutionPreconditionError(
            f"{owner_id} in-process command must target metadata.runtime_module {runtime_module!r}; got {module!r}"
        )
    if _resolve_executable(python_exec) != _resolve_executable(sys.executable):
        raise InProcessExecutionPreconditionError(
            f"{owner_id} in-process execution requires interpreter {sys.executable!r}; got {python_exec!r}"
        )
    return InProcessCommand(
        argv=command,
        python_exec=python_exec,
        module=module,
        module_argv=tuple(module_argv),
    )


def invoke_in_process_command(
    argv: tuple[str, ...] | list[str],
    *,
    metadata: Mapping[str, Any],
    owner_id: str,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    base_env: Mapping[str, str] | None = None,
    parent_env: Mapping[str, str] | None = None,
    stdout_log: IO[str] | None = None,
    stderr_log: IO[str] | None = None,
) -> InProcessResult:
    """Execute a pack runtime command in-process under scoped argv/cwd/env overlays.

    When log streams are supplied, stdout/stderr are tee'd only around the
    runtime entrypoint call. This uses process-global Python redirection, so it
    is intended for Astrid's serialized in-process execution paths.
    """

    command = classify_in_process_command(argv, metadata=metadata, owner_id=owner_id)
    base = os.environ if base_env is None else base_env
    parent = os.environ if parent_env is None else parent_env
    effective_env = build_child_subprocess_env(
        base=base,
        parent=parent,
        explicit_env={
            **dict(env or {}),
            ASTRID_INTERNAL_INVOCATION: "1",
        },
    )
    target = _resolve_in_process_callable(metadata, owner_id=owner_id)
    try:
        with canonical_runtime_entrypoint(owner_id), _scoped_cwd(cwd), _scoped_environ(
            effective_env
        ), _scoped_argv((command.module, *command.module_argv)):
            with _scoped_stdio_capture(stdout_log=stdout_log, stderr_log=stderr_log):
                raw_result = target(list(command.module_argv))
    except SystemExit as exc:
        raw_result = exc
    return normalize_in_process_result(
        raw_result,
        argv=command.argv,
        cwd=cwd,
        env=effective_env,
    )


def normalize_in_process_result(
    raw_result: Any,
    *,
    argv: tuple[str, ...] | list[str],
    cwd: str | os.PathLike[str] | None,
    env: Mapping[str, str],
) -> InProcessResult:
    """Normalize common Python runtime return patterns into a process-like result.

    Delegates classification to the shared
    :func:`~astrid.core.runtime._normalize.normalize_python_runtime_result`
    helper so that the orchestrator runner and the in-process invoker stay
    consistent.
    """

    command = tuple(str(token) for token in argv)
    cwd_str = None if cwd is None else str(Path(cwd))

    try:
        normalized = normalize_python_runtime_result(
            raw_result, passthrough_type=InProcessResult
        )
    except ValueError as exc:
        raise InProcessInvocationError(str(exc)) from exc

    if normalized.is_passthrough:
        return normalized.raw_result

    return _result(
        argv=command,
        cwd=cwd_str,
        env=env,
        returncode=normalized.returncode,
        payload=normalized.payload,
        raw_result=normalized.raw_result,
    )


def _resolve_in_process_callable(
    metadata: Mapping[str, Any],
    *,
    owner_id: str,
) -> Callable[..., Any]:
    def _resolver(module_path: str, callable_name: str) -> Callable[..., Any]:
        importlib.invalidate_caches()
        spec = importlib.util.find_spec(module_path)
        if spec is None or spec.loader is None:
            raise PackResolverError(f"failed to import module {module_path!r}: module spec not found")
        if not spec.origin:
            raise PackResolverError(f"failed to import module {module_path!r}: module origin not found")
        sys.modules.pop(module_path, None)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_path] = module
        source = Path(spec.origin).read_text(encoding="utf-8")
        with canonical_runtime_entrypoint(owner_id):
            exec(compile(source, spec.origin, "exec"), module.__dict__)
        target = getattr(module, callable_name, None)
        if target is None or not callable(target):
            raise CallableNotFoundError(
                f"module {module_path!r} attribute {callable_name!r} is not callable"
            )
        return target

    try:
        return resolve_callable_from_metadata(
            metadata,
            owner_id=owner_id,
            resolver=_resolver,
        )
    except (CallableNotFoundError, PackResolverError) as exc:
        raise InProcessInvocationError(str(exc)) from exc
    except SystemExit as exc:
        # Guarded modules exit 2 on unsanctioned import; surface that as a typed runtime failure.
        if _system_exit_code(exc.code) == 2:
            raise InProcessInvocationError(
                f"{owner_id} refused in-process import with exit code 2"
            ) from exc
        raise


def _resolve_executable(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _result(
    *,
    argv: tuple[str, ...],
    cwd: str | None,
    env: Mapping[str, str],
    returncode: int,
    payload: Mapping[str, Any],
    raw_result: Any,
) -> InProcessResult:
    normalized_payload = dict(payload)
    normalized_payload.setdefault("returncode", returncode)
    return InProcessResult(
        argv=argv,
        cwd=cwd,
        env=dict(env),
        returncode=returncode,
        payload=normalized_payload,
        raw_result=raw_result,
    )


@contextmanager
def _scoped_cwd(cwd: str | os.PathLike[str] | None) -> Iterator[None]:
    if cwd is None:
        yield
        return
    previous = Path.cwd()
    os.chdir(cwd)
    try:
        yield
    finally:
        os.chdir(previous)


@contextmanager
def _scoped_environ(env: Mapping[str, str]) -> Iterator[None]:
    previous = os.environ.copy()
    os.environ.clear()
    os.environ.update({str(key): str(value) for key, value in env.items()})
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


@contextmanager
def _scoped_argv(argv: tuple[str, ...] | list[str]) -> Iterator[None]:
    previous = list(sys.argv)
    sys.argv = [str(token) for token in argv]
    try:
        yield
    finally:
        sys.argv = previous


@contextmanager
def _scoped_stdio_capture(
    *,
    stdout_log: IO[str] | None,
    stderr_log: IO[str] | None,
) -> Iterator[None]:
    """Mirror runtime output to logs without swallowing live terminal output.

    ``redirect_stdout``/``redirect_stderr`` mutate process-global state, so this
    helper is safe only for the current serialized in-process execution model.
    Keep the scope tight around the runtime entrypoint and do not widen it to
    module import or caller setup.
    """

    stdout_cm = (
        redirect_stdout(TeeWriter(sys.stdout, stdout_log))
        if stdout_log is not None
        else nullcontext()
    )
    stderr_cm = (
        redirect_stderr(TeeWriter(sys.stderr, stderr_log))
        if stderr_log is not None
        else nullcontext()
    )
    with stdout_cm, stderr_cm:
        yield


__all__ = [
    "InProcessCommand",
    "InProcessExecutionPreconditionError",
    "InProcessInvocationError",
    "InProcessResult",
    "classify_in_process_command",
    "invoke_in_process_command",
    "normalize_in_process_result",
]
