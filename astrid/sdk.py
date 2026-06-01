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

from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Literal

from astrid.contracts.exec_error import ExecError
from astrid.core.project.paths import ProjectPathError, run_dir as project_run_dir, validate_project_slug
from astrid.core.task.event_stream import (
    EventStreamRecord,
    read_event_stream as _read_task_event_stream,
    subscribe_event_stream as _subscribe_task_event_stream,
)
from astrid.core.task.events import EVENTS_FILENAME
from astrid.contracts.schema import (
    AliasRecord,
    CapabilityHandle,
    Output,
    Port,
    Provenance,
    SafetyDeclaration,
)

CapabilityType = Literal["executor", "orchestrator", "element"]


class AstridSDKError(RuntimeError):
    """Base class for public SDK failures."""


class CapabilityNotFoundError(AstridSDKError):
    """Raised when a requested capability cannot be resolved."""


class CapabilityAmbiguousError(AstridSDKError):
    """Raised when a partial lookup matches more than one capability."""


class UnsupportedCapabilityError(AstridSDKError):
    """Raised when an operation is not supported for a capability kind."""


class CapabilityInvocationError(AstridSDKError):
    """Raised when the SDK cannot construct or execute an invocation."""


class CapabilityValidationError(AstridSDKError):
    """Raised when capability metadata or invocation arguments are invalid."""

    category = "validation"


class CapabilityMissingInputError(CapabilityValidationError):
    """Raised when a required invocation input is missing."""

    category = "missing_input"


class CapabilityPreconditionError(AstridSDKError):
    """Raised when capability execution preconditions are not satisfied."""

    category = "precondition"


class CapabilityRuntimeError(AstridSDKError):
    """Raised when capability execution fails at process/runtime time."""

    category = "runtime"


class CapabilityLeaseError(AstridSDKError):
    """Raised when task-run lease ownership or lease state rejects the call."""

    category = "lease"


class CapabilityEventLogError(AstridSDKError):
    """Raised when an event-log transport or verification operation fails."""

    category = "event_log"


def _json_safe(value: Any) -> Any:
    """Return a recursively JSON-safe copy of *value*."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, ExecError):
        return {
            "code": value.code,
            "type": value.type,
            "message": value.message,
            "recovery": value.recovery,
        }
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_safe(to_dict())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if is_dataclass(value):
        return {field.name: _json_safe(getattr(value, field.name)) for field in fields(value)}
    return value


def _json_safe_mapping(value: Any) -> dict[str, Any]:
    payload = _json_safe(value)
    if not isinstance(payload, dict):
        raise TypeError(f"expected mapping payload, got {type(payload).__name__}")
    return payload


def _looks_like_missing_input(message: str) -> bool:
    lowered = message.lower()
    return (
        "missing required input" in lowered
        or "missing mapped input" in lowered
        or "missing value for placeholder" in lowered
        or "--out is required" in lowered
    )


def _sdk_error_from_exception(exc: Any) -> AstridSDKError | None:
    if isinstance(exc, AstridSDKError):
        return exc

    from astrid.contracts.event_log_error import EventLogError
    from astrid.core.executor.runner import ExecutorRunnerError
    from astrid.core.executor.schema import ExecutorValidationError
    from astrid.core.orchestrator.runner import OrchestratorRunError, OrchestratorRunnerError
    from astrid.core.orchestrator.schema import OrchestratorValidationError
    from astrid.core.session.lease import LeaseError
    from astrid.core.task.events import NotWriterError, StaleEpochError, StaleTailError

    if isinstance(exc, (ExecutorRunnerError, OrchestratorRunnerError)):
        if _looks_like_missing_input(str(exc)):
            return CapabilityMissingInputError(str(exc))
        return CapabilityValidationError(str(exc))
    if isinstance(exc, (ExecutorValidationError, OrchestratorValidationError)):
        return CapabilityValidationError(str(exc))
    if isinstance(exc, ExecError):
        if exc.type == "precondition":
            return CapabilityPreconditionError(exc.message)
        if exc.type == "process":
            return CapabilityRuntimeError(exc.message)
        return CapabilityInvocationError(exc.message)
    if isinstance(exc, OrchestratorRunError):
        if exc.kind == "precondition":
            return CapabilityPreconditionError(exc.message)
        return CapabilityRuntimeError(exc.message)
    if isinstance(exc, (LeaseError, NotWriterError, StaleEpochError)):
        return CapabilityLeaseError(str(exc))
    if isinstance(exc, StaleTailError):
        return CapabilityEventLogError(str(exc))
    if isinstance(exc, EventLogError):
        return CapabilityEventLogError(str(exc))
    return None


def _error_payload_from_internal_error(error: Any) -> dict[str, Any]:
    payload = _json_safe(error)
    if isinstance(payload, dict):
        result = dict(payload)
    else:
        result = {"message": str(error)}

    mapped = _sdk_error_from_exception(error)
    if mapped is not None:
        result.setdefault("message", str(error))
        result["sdk_error"] = mapped.__class__.__name__
        result["sdk_category"] = getattr(mapped, "category", "invocation")
    return result


def _internal_error_from_result(result: Any) -> Any:
    direct = getattr(result, "error", None)
    if direct is not None:
        return direct
    errors = getattr(result, "errors", ())
    if isinstance(errors, tuple) and errors:
        return errors[0]
    if isinstance(errors, list) and errors:
        return errors[0]
    return None


def _sdk_error_from_event_exception(exc: Any) -> AstridSDKError | None:
    mapped = _sdk_error_from_exception(exc)
    if mapped is not None:
        return mapped
    if isinstance(exc, ProjectPathError):
        return CapabilityValidationError(str(exc))
    if isinstance(exc, FileNotFoundError):
        return CapabilityPreconditionError(str(exc))
    return None


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


@dataclass(frozen=True)
class Capability:
    """Public inspectable capability DTO."""

    id: str
    capability_type: CapabilityType
    native_kind: str
    handle: CapabilityHandle
    inputs: tuple[Port, ...] = ()
    outputs: tuple[Output, ...] = ()
    schema: Mapping[str, Any] = field(default_factory=dict)
    defaults: Mapping[str, Any] = field(default_factory=dict)
    definition: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "id": self.id,
                "capability_type": self.capability_type,
                "native_kind": self.native_kind,
                "handle": self.handle,
                "inputs": self.inputs,
                "outputs": self.outputs,
                "schema": self.schema,
                "defaults": self.defaults,
                "definition": self.definition,
            }
        )


@dataclass(frozen=True)
class DiscoveryResult:
    """Grouped public capability inventory."""

    executors: tuple[Capability, ...] = ()
    orchestrators: tuple[Capability, ...] = ()
    elements: tuple[Capability, ...] = ()
    capabilities: tuple[Capability, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "executors": self.executors,
                "orchestrators": self.orchestrators,
                "elements": self.elements,
                "capabilities": self.capabilities,
            }
        )


@dataclass(frozen=True)
class InvocationResult:
    """Public normalized execution result DTO."""

    capability_id: str
    capability_type: CapabilityType
    native_kind: str
    ok: bool
    error: Mapping[str, Any] | None = None
    raw_result: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "capability_id": self.capability_id,
                "capability_type": self.capability_type,
                "native_kind": self.native_kind,
                "ok": self.ok,
                "error": self.error,
                "raw_result": self.raw_result,
            }
        )


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
    kwargs: dict[str, Any] = {
        "extra_pack_roots": extra_pack_roots,
        "include_installed": include_installed,
    }
    if project_root is not None:
        kwargs["project_root"] = project_root
    return kwargs


def _load_executor_registry(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
) -> Any:
    from astrid.core.executor.registry import load_default_registry

    return load_default_registry(
        banodoco_config=banodoco_config,
        **_registry_load_kwargs(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        ),
    )


def _load_orchestrator_registry(
    *,
    executor_registry: Any | None = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
) -> Any:
    from astrid.core.orchestrator.registry import load_default_registry

    return load_default_registry(
        executor_registry=executor_registry,
        banodoco_config=banodoco_config,
        **_registry_load_kwargs(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        ),
    )


def _load_element_registry(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
) -> Any:
    from astrid.core.element.registry import load_default_registry

    return load_default_registry(
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        **_registry_load_kwargs(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        ),
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


def _capability_from_executor(
    definition: Any,
    registry: Any,
    *,
    requested_id: str | None = None,
) -> Capability:
    from astrid.core.executor.schema import to_capability_handle

    resolved_alias = None
    deprecated = False
    deprecation_message = ""
    aliases = ()
    if registry.alias_resolver is not None:
        aliases = tuple(registry.alias_resolver.get_aliases_for(definition.id))
        if requested_id is not None and registry.alias_resolver.is_alias(requested_id):
            alias_record = registry.alias_resolver.get_record(requested_id)
            if alias_record is not None:
                resolved_alias = requested_id
                deprecated = alias_record.deprecated
                deprecation_message = alias_record.deprecation_message
    definition_mapping = _json_safe_mapping(definition.to_dict())
    return Capability(
        id=definition.id,
        capability_type="executor",
        native_kind=definition.kind,
        handle=to_capability_handle(
            definition,
            aliases=aliases,
            resolved_alias=resolved_alias,
            deprecated=deprecated,
            deprecation_message=deprecation_message,
        ),
        inputs=tuple(definition.inputs),
        outputs=tuple(definition.outputs),
        schema=definition_mapping,
        defaults={},
        definition=definition_mapping,
    )


def _capability_from_orchestrator(
    definition: Any,
    registry: Any,
    *,
    requested_id: str | None = None,
) -> Capability:
    from astrid.core.orchestrator.schema import to_capability_handle

    resolved_alias = None
    deprecated = False
    deprecation_message = ""
    aliases = ()
    if registry.alias_resolver is not None:
        aliases = tuple(registry.alias_resolver.get_aliases_for(definition.id))
        if requested_id is not None and registry.alias_resolver.is_alias(requested_id):
            alias_record = registry.alias_resolver.get_record(requested_id)
            if alias_record is not None:
                resolved_alias = requested_id
                deprecated = alias_record.deprecated
                deprecation_message = alias_record.deprecation_message
    definition_mapping = _json_safe_mapping(definition.to_dict())
    return Capability(
        id=definition.id,
        capability_type="orchestrator",
        native_kind=definition.kind,
        handle=to_capability_handle(
            definition,
            aliases=aliases,
            resolved_alias=resolved_alias,
            deprecated=deprecated,
            deprecation_message=deprecation_message,
        ),
        inputs=tuple(definition.inputs),
        outputs=tuple(definition.outputs),
        schema=definition_mapping,
        defaults={},
        definition=definition_mapping,
    )


def _capability_from_element(definition: Any) -> Capability:
    from astrid.core.element.schema import to_capability_handle

    return Capability(
        id=f"{definition.kind}/{definition.id}",
        capability_type="element",
        native_kind=definition.kind,
        handle=to_capability_handle(definition),
        schema=_json_safe_mapping(definition.schema),
        defaults=_json_safe_mapping(definition.defaults),
        definition=_json_safe_mapping(definition.to_dict()),
    )


def _is_qualified_capability_id(capability_id: str) -> bool:
    return "." in capability_id


def _is_canonical_element_id(capability_id: str) -> bool:
    from astrid.core.element.schema import ELEMENT_KINDS

    kind, sep, local_id = capability_id.partition("/")
    return bool(sep and local_id and kind in ELEMENT_KINDS)


def _candidate_label(kind: str, capability_id: str) -> str:
    return f"{kind}:{capability_id}"


def _format_candidates(candidates: tuple[str, ...]) -> str:
    return ", ".join(sorted(candidates))


def _resolve_executor_capability(capability_id: str, registry: Any) -> Capability:
    resolver = registry.alias_resolver
    alias_requested = resolver is not None and resolver.is_alias(capability_id)
    if alias_requested or _is_qualified_capability_id(capability_id):
        try:
            definition = registry.get(capability_id)
        except KeyError as exc:
            raise CapabilityNotFoundError(f"unknown executor {capability_id!r}") from exc
        return _capability_from_executor(definition, registry, requested_id=capability_id)

    matches = [
        definition
        for definition in registry.list()
        if definition.id.rsplit(".", 1)[-1] == capability_id
    ]
    if not matches:
        raise CapabilityNotFoundError(f"unknown executor {capability_id!r}")
    if len(matches) > 1:
        candidates = tuple(_candidate_label("executor", definition.id) for definition in matches)
        raise CapabilityAmbiguousError(
            f"ambiguous executor {capability_id!r}; candidates: {_format_candidates(candidates)}"
        )
    return _capability_from_executor(matches[0], registry, requested_id=capability_id)


def _resolve_orchestrator_capability(capability_id: str, registry: Any) -> Capability:
    resolver = registry.alias_resolver
    alias_requested = resolver is not None and resolver.is_alias(capability_id)
    if alias_requested or _is_qualified_capability_id(capability_id):
        try:
            definition = registry.get(capability_id)
        except KeyError as exc:
            raise CapabilityNotFoundError(f"unknown orchestrator {capability_id!r}") from exc
        return _capability_from_orchestrator(definition, registry, requested_id=capability_id)

    matches = [
        definition
        for definition in registry.list()
        if definition.id.rsplit(".", 1)[-1] == capability_id
    ]
    if not matches:
        raise CapabilityNotFoundError(f"unknown orchestrator {capability_id!r}")
    if len(matches) > 1:
        candidates = tuple(_candidate_label("orchestrator", definition.id) for definition in matches)
        raise CapabilityAmbiguousError(
            f"ambiguous orchestrator {capability_id!r}; candidates: {_format_candidates(candidates)}"
        )
    return _capability_from_orchestrator(matches[0], registry, requested_id=capability_id)


def _resolve_element_capability(
    capability_id: str,
    registry: Any,
    *,
    element_kind: str | None,
) -> Capability:
    lookup_id = capability_id
    if element_kind is not None:
        if _is_canonical_element_id(capability_id):
            requested_kind, _, requested_local_id = capability_id.partition("/")
            if requested_kind != element_kind:
                raise CapabilityNotFoundError(
                    f"unknown element {capability_id!r} for explicit element_kind={element_kind!r}"
                )
            lookup_id = requested_local_id
        try:
            definition = registry.get(element_kind, lookup_id)
        except KeyError as exc:
            raise CapabilityNotFoundError(
                f"unknown element {capability_id!r} for explicit element_kind={element_kind!r}"
            ) from exc
        return _capability_from_element(definition)

    if _is_canonical_element_id(capability_id):
        requested_kind, _, requested_local_id = capability_id.partition("/")
        try:
            definition = registry.get(requested_kind, requested_local_id)
        except KeyError as exc:
            raise CapabilityNotFoundError(f"unknown element {capability_id!r}") from exc
        return _capability_from_element(definition)

    matches = [definition for definition in registry.list() if definition.id == capability_id]
    if not matches:
        raise CapabilityNotFoundError(f"unknown element {capability_id!r}")
    if len(matches) > 1:
        candidates = tuple(
            _candidate_label("element", f"{definition.kind}/{definition.id}") for definition in matches
        )
        raise CapabilityAmbiguousError(
            f"ambiguous element {capability_id!r}; candidates: {_format_candidates(candidates)}"
        )
    return _capability_from_element(matches[0])


def _resolve_capability_kindless(
    capability_id: str,
    *,
    executor_registry: Any,
    orchestrator_registry: Any,
    element_registry: Any | None,
) -> Capability:
    matches: list[Capability] = []

    try:
        matches.append(_resolve_executor_capability(capability_id, executor_registry))
    except CapabilityNotFoundError:
        pass
    try:
        matches.append(_resolve_orchestrator_capability(capability_id, orchestrator_registry))
    except CapabilityNotFoundError:
        pass
    if element_registry is not None:
        try:
            matches.append(
                _resolve_element_capability(
                    capability_id,
                    element_registry,
                    element_kind=None,
                )
            )
        except CapabilityNotFoundError:
            pass

    if not matches:
        raise CapabilityNotFoundError(f"unknown capability {capability_id!r}")
    if len(matches) > 1:
        candidates = tuple(
            _candidate_label(match.capability_type, match.id)
            for match in matches
        )
        raise CapabilityAmbiguousError(
            f"ambiguous capability {capability_id!r}; candidates: {_format_candidates(candidates)}"
        )
    return matches[0]


def _resolve_capability(
    capability_id: str,
    *,
    kind: CapabilityType | None,
    element_kind: str | None,
    executor_registry: Any,
    orchestrator_registry: Any,
    element_registry: Any | None,
) -> Capability:
    if kind == "executor":
        return _resolve_executor_capability(capability_id, executor_registry)
    if kind == "orchestrator":
        return _resolve_orchestrator_capability(capability_id, orchestrator_registry)
    if kind == "element":
        if element_registry is None:
            raise CapabilityNotFoundError("element registry was not loaded")
        return _resolve_element_capability(
            capability_id,
            element_registry,
            element_kind=element_kind,
        )
    if kind is None:
        return _resolve_capability_kindless(
            capability_id,
            executor_registry=executor_registry,
            orchestrator_registry=orchestrator_registry,
            element_registry=element_registry,
        )
    raise CapabilityNotFoundError(
        f"unsupported capability kind {kind!r}; expected 'executor', 'orchestrator', 'element', or None"
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
    executor_registry, orchestrator_registry, element_registry = _load_registries(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        include_elements=True,
    )
    if element_registry is None:
        raise CapabilityInvocationError("element registry was not loaded")

    executors = tuple(
        _capability_from_executor(definition, executor_registry)
        for definition in executor_registry.list()
    )
    orchestrators = tuple(
        _capability_from_orchestrator(definition, orchestrator_registry)
        for definition in orchestrator_registry.list()
    )
    elements = tuple(
        _capability_from_element(definition)
        for definition in element_registry.list()
    )
    return DiscoveryResult(
        executors=executors,
        orchestrators=orchestrators,
        elements=elements,
        capabilities=executors + orchestrators + elements,
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
    if _registries is None:
        executor_registry, orchestrator_registry, element_registry = _load_registries(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
            banodoco_config=banodoco_config,
            active_theme=active_theme,
            include_missing_roots=include_missing_roots,
            include_elements=include_elements or kind == "element" or kind is None,
        )
    else:
        executor_registry, orchestrator_registry, element_registry = _registries

    return _resolve_capability(
        capability_id,
        kind=kind,
        element_kind=element_kind,
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
        element_registry=element_registry,
    )


def _normalize_executor_result(result: Any) -> dict[str, Any]:
    payload = {
        "executor_id": result.executor_id,
        "kind": result.kind,
        "command": result.command,
        "cwd": result.cwd,
        "env": result.env,
        "payload": result.payload,
        "returncode": result.returncode,
        "dry_run": result.dry_run,
        "skipped": result.skipped,
        "skipped_reason": result.skipped_reason,
        "missing_binaries": result.missing_binaries,
        "error": result.error,
        "ok": result.ok,
    }
    return _json_safe_mapping(payload)


def _normalize_orchestrator_result(result: Any) -> dict[str, Any]:
    return _json_safe_mapping(result.to_dict())


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
    include_elements = kind == "element"
    registries = _load_registries(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        include_elements=include_elements,
    )
    capability = get_capability(
        capability_id,
        kind=kind,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        _registries=registries,
    )
    if capability.capability_type == "element":
        raise UnsupportedCapabilityError(f"elements are not invokable via the SDK: {capability.id}")

    try:
        if capability.capability_type == "executor":
            if out is None:
                raise CapabilityInvocationError("executor invocations require an out path")
            from astrid.core.executor.runner import ExecutorRunRequest

            executor_registry, _, _ = registries
            request = ExecutorRunRequest(
                executor_id=capability.id,
                out=out,
                project=project,
                inputs=dict(inputs or {}),
                outputs=dict(outputs or {}),
                brief=brief,
                dry_run=dry_run,
                check_binaries=check_binaries,
                python_exec=python_exec,
                verbose=verbose,
                execution_mode=execution_mode,
                argv=tuple(argv),
            )
            result = run_executor(request, executor_registry)
            raw_result = _normalize_executor_result(result)
        else:
            from astrid.core.orchestrator.runner import OrchestratorRunRequest

            _, orchestrator_registry, _ = registries
            request = OrchestratorRunRequest(
                orchestrator_id=capability.id,
                out=out,
                project=project,
                inputs=dict(inputs or {}),
                outputs=dict(outputs or {}),
                brief=brief,
                orchestrator_args=tuple(orchestrator_args),
                dry_run=dry_run,
                python_exec=python_exec,
                verbose=verbose,
                execution_mode=execution_mode,
            )
            result = run_orchestrator(request, orchestrator_registry)
            raw_result = _normalize_orchestrator_result(result)
    except AstridSDKError:
        raise
    except Exception as exc:
        mapped = _sdk_error_from_exception(exc)
        if mapped is not None:
            raise mapped from exc
        raise CapabilityInvocationError(
            f"failed to invoke {capability.capability_type} {capability.id!r}"
        ) from exc

    internal_error = _internal_error_from_result(result)
    error = _error_payload_from_internal_error(internal_error) if internal_error is not None else None
    return InvocationResult(
        capability_id=capability.id,
        capability_type=capability.capability_type,
        native_kind=capability.native_kind,
        ok=bool(getattr(result, "ok", False)),
        error=error,
        raw_result=raw_result,
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
    "get_capability",
    "invoke",
    "read_events",
    "run_executor",
    "run_orchestrator",
    "subscribe_events",
]
