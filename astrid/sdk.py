"""Public SDK DTOs, exceptions, and serialization helpers.

This module is intentionally lightweight. Registry and runner imports belong in
call sites so ``import astrid`` can expose the SDK surface without eagerly
loading execution machinery.

Public exception taxonomy:

* validation failures: malformed capability definitions or invalid request
  shape.
* missing input failures: required user-supplied invocation inputs are absent.
* precondition failures: the capability cannot run in the requested execution
  mode or environment.
* process/runtime failures: the capability ran and failed, or its runtime entry
  could not complete.
* lease failures: the caller is not the active task-run writer or the canonical
  lease is unreadable/inconsistent.
* event-log failures: task/timeline append or verification transport errors
  outside the lease-specific writer boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from astrid.contracts.exec_error import ExecError
from astrid.contracts.schema import (
    AliasRecord,
    CapabilityHandle,
    Output,
    Port,
    Provenance,
    SafetyDeclaration,
)
from astrid.core.project.paths import validate_project_slug
from astrid.core.project.paths import run_dir as project_run_dir
from astrid.sdk_errors import (
    AstridSDKError,
    CapabilityAmbiguousError,
    CapabilityEventLogError,
    CapabilityInvocationError,
    CapabilityLeaseError,
    CapabilityMissingInputError,
    CapabilityNotFoundError,
    CapabilityPreconditionError,
    CapabilityRuntimeError,
    CapabilityValidationError,
    UnsupportedCapabilityError,
    _error_payload_from_internal_error,
    _internal_error_from_result,
    _sdk_error_from_event_exception,
    _sdk_error_from_exception,
)
from astrid.sdk_generation import GenerationFacade, generate
from astrid.sdk_generation import _EXPLICIT_ONLY_IMAGE_MODES
from astrid.sdk_generation import _infer_image_mode, _infer_video_mode
from astrid.sdk_generation import _load_model_registry, _resolve_execution
from astrid.sdk_invocation import _discover_invocation_manifest_path as _sdk_discover_invocation_manifest_path
from astrid.sdk_invocation import _normalize_executor_result as _sdk_normalize_executor_result
from astrid.sdk_invocation import _normalize_orchestrator_result as _sdk_normalize_orchestrator_result
from astrid.sdk_invocation import _payload_manifest_path as _sdk_payload_manifest_path
from astrid.sdk_invocation import discover as _sdk_discover
from astrid.sdk_invocation import get_capability as _sdk_get_capability
from astrid.sdk_invocation import invoke as _sdk_invoke
from astrid.sdk_discovery import _apply_pack_permission_ids as _sdk_apply_pack_permission_ids
from astrid.sdk_discovery import _build_discovery_metadata as _sdk_build_discovery_metadata
from astrid.sdk_discovery import _candidate_label as _sdk_candidate_label
from astrid.sdk_discovery import _capability_from_element as _sdk_capability_from_element
from astrid.sdk_discovery import _capability_from_executor as _sdk_capability_from_executor
from astrid.sdk_discovery import _capability_from_orchestrator as _sdk_capability_from_orchestrator
from astrid.sdk_discovery import _discover_pack_inventory as _sdk_discover_pack_inventory
from astrid.sdk_discovery import _element_kind_record as _sdk_element_kind_record
from astrid.sdk_discovery import _format_candidates as _sdk_format_candidates
from astrid.sdk_discovery import _generation_backend_record as _sdk_generation_backend_record
from astrid.sdk_discovery import _generation_feature_record as _sdk_generation_feature_record
from astrid.sdk_discovery import _generation_mode_record as _sdk_generation_mode_record
from astrid.sdk_discovery import _is_qualified_capability_id as _sdk_is_qualified_capability_id
from astrid.sdk_discovery import _load_element_registry as _sdk_load_element_registry
from astrid.sdk_discovery import _load_executor_registry as _sdk_load_executor_registry
from astrid.sdk_discovery import _load_orchestrator_registry as _sdk_load_orchestrator_registry
from astrid.sdk_discovery import _load_registries as _sdk_load_registries
from astrid.sdk_discovery import _pack_permission_ids_by_pack_id as _sdk_pack_permission_ids_by_pack_id
from astrid.sdk_discovery import _pack_record as _sdk_pack_record
from astrid.sdk_discovery import _registry_load_kwargs as _sdk_registry_load_kwargs
from astrid.sdk_discovery import _resolve_capability as _sdk_resolve_capability
from astrid.sdk_discovery import _resolve_capability_kindless as _sdk_resolve_capability_kindless
from astrid.sdk_discovery import _resolve_element_capability as _sdk_resolve_element_capability
from astrid.sdk_discovery import _resolve_executor_capability as _sdk_resolve_executor_capability
from astrid.sdk_discovery import _resolve_orchestrator_capability as _sdk_resolve_orchestrator_capability
from astrid.sdk_discovery import _split_canonical_element_id as _sdk_split_canonical_element_id
from astrid.sdk_results import (
    Capability,
    CapabilityType,
    DiscoveryResult,
    InvocationResult,
    _json_safe,
    _json_safe_mapping,
)
from astrid.core.task.event_stream import (
    EventStreamRecord,
)
from astrid.core.task.event_stream import (
    read_event_stream as _read_task_event_stream,
)
from astrid.core.task.event_stream import (
    subscribe_event_stream as _subscribe_task_event_stream,
)
from astrid.core.task.events import EVENTS_FILENAME


def _resolve_event_stream_run_dir(
    project: str,
    run_id: str,
    *,
    projects_root: str | Path | None = None,
) -> Path:
    slug = validate_project_slug(project)
    run_path = project_run_dir(slug, run_id, root=projects_root)
    if not run_path.is_dir():
        raise FileNotFoundError(f"run {run_id!r} not found in project {slug!r}")
    events_path = run_path / EVENTS_FILENAME
    if not events_path.is_file():
        raise FileNotFoundError(
            f"run {run_id!r} in project {slug!r} has no {EVENTS_FILENAME}"
        )
    return run_path


def read_events(
    project: str,
    run_id: str,
    *,
    projects_root: str | Path | None = None,
    include_audit: bool = True,
    verify: bool = True,
) -> tuple[EventStreamRecord, ...]:
    """Return a verified read-only task/audit event snapshot for one run."""

    try:
        run_path = _resolve_event_stream_run_dir(project, run_id, projects_root=projects_root)
        return tuple(
            _read_task_event_stream(
                run_path,
                include_audit=include_audit,
                verify=verify,
            )
        )
    except AstridSDKError:
        raise
    except Exception as exc:
        mapped = _sdk_error_from_event_exception(exc)
        if mapped is not None:
            raise mapped from exc
        raise CapabilityInvocationError(
            f"failed to read events for project {project!r} run {run_id!r}"
        ) from exc


def subscribe_events(
    project: str,
    run_id: str,
    *,
    projects_root: str | Path | None = None,
    include_audit: bool = True,
    verify: bool = True,
    follow: bool = False,
    poll_interval: float = 0.1,
    idle_polls: int | None = None,
):
    """Yield a verified read-only task/audit event stream for one run."""

    try:
        run_path = _resolve_event_stream_run_dir(project, run_id, projects_root=projects_root)
    except AstridSDKError:
        raise
    except Exception as exc:
        mapped = _sdk_error_from_event_exception(exc)
        if mapped is not None:
            raise mapped from exc
        raise CapabilityInvocationError(
            f"failed to subscribe to events for project {project!r} run {run_id!r}"
        ) from exc

    def _iter():
        try:
            yield from _subscribe_task_event_stream(
                run_path,
                include_audit=include_audit,
                verify=verify,
                follow=follow,
                poll_interval=poll_interval,
                idle_polls=idle_polls,
            )
        except AstridSDKError:
            raise
        except Exception as exc:
            mapped = _sdk_error_from_event_exception(exc)
            if mapped is not None:
                raise mapped from exc
            raise CapabilityInvocationError(
                f"failed to subscribe to events for project {project!r} run {run_id!r}"
            ) from exc

    return _iter()


def run_executor(request: Any, registry: Any) -> Any:
    from astrid.core.executor.runner import run_executor as _run_executor

    return _run_executor(request, registry)


def run_orchestrator(request: Any, registry: Any) -> Any:
    from astrid.core.orchestrator.runner import run_orchestrator as _run_orchestrator

    return _run_orchestrator(request, registry)


def _registry_load_kwargs(
    *,
    project_root: str | Path | None,
    extra_pack_roots: tuple[str, ...],
    include_installed: bool,
) -> dict[str, Any]:
    return _sdk_registry_load_kwargs(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    )


def _load_executor_registry(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
) -> Any:
    return _sdk_load_executor_registry(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
    )


def _load_orchestrator_registry(
    *,
    executor_registry: Any | None = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
) -> Any:
    return _sdk_load_orchestrator_registry(
        executor_registry=executor_registry,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
    )


def _load_element_registry(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
) -> Any:
    return _sdk_load_element_registry(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
    )


def _load_registries(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
    include_elements: bool = False,
) -> tuple[Any, Any, Any | None]:
    executor_registry = _load_executor_registry(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
    )
    orchestrator_registry = _load_orchestrator_registry(
        executor_registry=executor_registry,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
    )
    element_registry = None
    if include_elements:
        element_registry = _load_element_registry(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
            active_theme=active_theme,
            include_missing_roots=include_missing_roots,
        )
    return executor_registry, orchestrator_registry, element_registry


def _discover_pack_inventory(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> tuple[Any, ...]:
    return _sdk_discover_pack_inventory(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    )


def _pack_record(discovered_pack: Any) -> dict[str, Any]:
    return _sdk_pack_record(discovered_pack)


def _pack_permission_ids_by_pack_id(discovered_packs: tuple[Any, ...]) -> dict[str, tuple[str, ...]]:
    return _sdk_pack_permission_ids_by_pack_id(discovered_packs)


def _apply_pack_permission_ids(
    capability: Capability,
    *,
    pack_permission_ids_by_pack_id: dict[str, tuple[str, ...]] | None = None,
) -> Capability:
    return _sdk_apply_pack_permission_ids(
        capability,
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _generation_backend_record(descriptor: Any) -> dict[str, Any]:
    return _sdk_generation_backend_record(descriptor)


def _element_kind_record(descriptor: Any) -> dict[str, Any]:
    return _sdk_element_kind_record(descriptor)


def _generation_feature_record(descriptor: Any) -> dict[str, Any]:
    return _sdk_generation_feature_record(descriptor)


def _generation_mode_record(descriptor: Any) -> dict[str, Any]:
    return _sdk_generation_mode_record(descriptor)


def _build_discovery_metadata(
    discovered_packs: tuple[Any, ...],
    *,
    element_registry: Any,
) -> tuple[
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    return _sdk_build_discovery_metadata(
        discovered_packs,
        element_registry=element_registry,
    )


def _capability_from_executor(
    definition: Any,
    registry: Any,
    *,
    requested_id: str | None = None,
    pack_permission_ids_by_pack_id: dict[str, tuple[str, ...]] | None = None,
) -> Capability:
    return _sdk_capability_from_executor(
        definition,
        registry,
        requested_id=requested_id,
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _capability_from_orchestrator(
    definition: Any,
    registry: Any,
    *,
    requested_id: str | None = None,
    pack_permission_ids_by_pack_id: dict[str, tuple[str, ...]] | None = None,
) -> Capability:
    return _sdk_capability_from_orchestrator(
        definition,
        registry,
        requested_id=requested_id,
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _capability_from_element(
    definition: Any,
    *,
    pack_permission_ids_by_pack_id: dict[str, tuple[str, ...]] | None = None,
) -> Capability:
    return _sdk_capability_from_element(
        definition,
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _is_qualified_capability_id(capability_id: str) -> bool:
    return _sdk_is_qualified_capability_id(capability_id)


def _split_canonical_element_id(
    capability_id: str,
    *,
    registry: Any,
    strict: bool = False,
) -> tuple[str, str] | None:
    return _sdk_split_canonical_element_id(
        capability_id,
        registry=registry,
        strict=strict,
    )


def _candidate_label(kind: str, capability_id: str) -> str:
    return _sdk_candidate_label(kind, capability_id)


def _format_candidates(candidates: tuple[str, ...]) -> str:
    return _sdk_format_candidates(candidates)


def _resolve_executor_capability(capability_id: str, registry: Any) -> Capability:
    return _sdk_resolve_executor_capability(capability_id, registry)


def _resolve_orchestrator_capability(capability_id: str, registry: Any) -> Capability:
    return _sdk_resolve_orchestrator_capability(capability_id, registry)


def _resolve_element_capability(
    capability_id: str,
    registry: Any,
    *,
    element_kind: str | None,
) -> Capability:
    return _sdk_resolve_element_capability(
        capability_id,
        registry,
        element_kind=element_kind,
    )


def _resolve_capability_kindless(
    capability_id: str,
    *,
    executor_registry: Any,
    orchestrator_registry: Any,
    element_registry: Any | None,
) -> Capability:
    return _sdk_resolve_capability_kindless(
        capability_id,
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
        element_registry=element_registry,
    )


def _resolve_capability(
    capability_id: str,
    *,
    kind: CapabilityType | None,
    element_kind: str | None,
    executor_registry: Any,
    orchestrator_registry: Any,
    element_registry: Any | None,
) -> Capability:
    return _sdk_resolve_capability(
        capability_id,
        kind=kind,
        element_kind=element_kind,
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
        element_registry=element_registry,
    )


def discover(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
) -> DiscoveryResult:
    return _sdk_discover(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
    )


def get_capability(
    capability_id: str,
    *,
    kind: CapabilityType | None = None,
    element_kind: str | None = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    include_elements: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
    _registries: tuple[Any, Any, Any | None] | None = None,
) -> Capability:
    return _sdk_get_capability(
        capability_id,
        kind=kind,
        element_kind=element_kind,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        include_elements=include_elements,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        _registries=_registries,
    )


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
    "AliasRecord",
    "AstridSDKError",
    "Capability",
    "CapabilityAmbiguousError",
    "CapabilityHandle",
    "CapabilityInvocationError",
    "CapabilityNotFoundError",
    "CapabilityType",
    "CapabilityValidationError",
    "CapabilityMissingInputError",
    "CapabilityPreconditionError",
    "CapabilityRuntimeError",
    "CapabilityLeaseError",
    "CapabilityEventLogError",
    "DiscoveryResult",
    "EventStreamRecord",
    "ExecError",
    "InvocationResult",
    "Output",
    "Port",
    "Provenance",
    "SafetyDeclaration",
    "UnsupportedCapabilityError",
    "discover",
    "generate",
    "get_capability",
    "invoke",
    "read_events",
    "run_executor",
    "run_orchestrator",
    "subscribe_events",
]
