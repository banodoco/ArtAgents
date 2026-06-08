"""Public SDK invocation entry points and result normalization helpers.

Re-exports from ``astrid.sdk_invocation`` and provides the ``invoke`` public
function plus ``run_executor`` / ``run_orchestrator`` runner bridges.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from astrid.sdk_invocation import _discover_invocation_manifest_path as _sdk_discover_invocation_manifest_path
from astrid.sdk_invocation import _normalize_executor_result as _sdk_normalize_executor_result
from astrid.sdk_invocation import _normalize_orchestrator_result as _sdk_normalize_orchestrator_result
from astrid.sdk_invocation import _payload_manifest_path as _sdk_payload_manifest_path
from astrid.sdk_invocation import invoke as _sdk_invoke

from .dto import CapabilityType, InvocationResult


def run_executor(request: Any, registry: Any) -> Any:
    from astrid.core.executor.runner import run_executor as _run_executor

    return _run_executor(request, registry)


def run_orchestrator(request: Any, registry: Any) -> Any:
    from astrid.core.orchestrator.runner import run_orchestrator as _run_orchestrator

    return _run_orchestrator(request, registry)


def _normalize_executor_result(result: Any) -> dict[str, Any]:
    return _sdk_normalize_executor_result(result)


def _normalize_orchestrator_result(result: Any) -> dict[str, Any]:
    return _sdk_normalize_orchestrator_result(result)


def _payload_manifest_path(raw_result: Mapping[str, Any]) -> str | None:
    return _sdk_payload_manifest_path(raw_result)


def _discover_invocation_manifest_path(
    raw_result: Mapping[str, Any],
    *,
    out: Path | str | None,
) -> str | None:
    return _sdk_discover_invocation_manifest_path(raw_result, out=out)


def invoke(
    capability_id: str,
    *,
    kind: CapabilityType,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
    out: Path | str | None = None,
    project: str | None = None,
    inputs: Mapping[str, Any] | None = None,
    outputs: Mapping[str, Any] | None = None,
    brief: Path | str | None = None,
    dry_run: bool = False,
    check_binaries: bool = False,
    python_exec: str | None = None,
    verbose: bool = False,
    execution_mode: Literal["subprocess", "in_process"] = "subprocess",
    argv: tuple[str, ...] = (),
    orchestrator_args: tuple[str, ...] = (),
) -> InvocationResult:
    return _sdk_invoke(
        capability_id,
        kind=kind,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        out=out,
        project=project,
        inputs=inputs,
        outputs=outputs,
        brief=brief,
        dry_run=dry_run,
        check_binaries=check_binaries,
        python_exec=python_exec,
        verbose=verbose,
        execution_mode=execution_mode,
        argv=argv,
        orchestrator_args=orchestrator_args,
    )


__all__ = [
    "invoke",
    "run_executor",
    "run_orchestrator",
    "_discover_invocation_manifest_path",
    "_normalize_executor_result",
    "_normalize_orchestrator_result",
    "_payload_manifest_path",
]
