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
from dataclasses import dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any, Literal

from astrid.contracts.exec_error import ExecError
from astrid.contracts.schema import (
    AliasRecord,
    CapabilityHandle,
    Output,
    Port,
    Provenance,
    SafetyDeclaration,
)
from astrid.core.project.paths import ProjectPathError, validate_project_slug
from astrid.core.project.paths import run_dir as project_run_dir
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
    packs: tuple[Mapping[str, Any], ...] = ()
    generation_backends: tuple[Mapping[str, Any], ...] = ()
    element_kinds: tuple[Mapping[str, Any], ...] = ()
    generation_features: tuple[Mapping[str, Any], ...] = ()
    generation_modes: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "executors": self.executors,
                "orchestrators": self.orchestrators,
                "elements": self.elements,
                "capabilities": self.capabilities,
                "packs": self.packs,
                "generation_backends": self.generation_backends,
                "element_kinds": self.element_kinds,
                "generation_features": self.generation_features,
                "generation_modes": self.generation_modes,
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
    manifest_path: str | None = None
    raw_result: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "capability_id": self.capability_id,
                "capability_type": self.capability_type,
                "native_kind": self.native_kind,
                "ok": self.ok,
                "error": self.error,
                "manifest_path": self.manifest_path,
                "raw_result": self.raw_result,
            }
        )


def _sdk_exception_from_payload(error: Mapping[str, Any] | None) -> AstridSDKError:
    message = "generation invocation failed"
    if error:
        raw_message = error.get("message")
        if isinstance(raw_message, str) and raw_message:
            message = raw_message
    sdk_error_name = error.get("sdk_error") if error else None
    if isinstance(sdk_error_name, str):
        exc_type = globals().get(sdk_error_name)
        if isinstance(exc_type, type) and issubclass(exc_type, AstridSDKError):
            return exc_type(message)
    sdk_category = error.get("sdk_category") if error else None
    if sdk_category == "validation":
        return CapabilityValidationError(message)
    if sdk_category == "missing_input":
        return CapabilityMissingInputError(message)
    if sdk_category == "precondition":
        return CapabilityPreconditionError(message)
    if sdk_category == "runtime":
        return CapabilityRuntimeError(message)
    if sdk_category == "lease":
        return CapabilityLeaseError(message)
    if sdk_category == "event_log":
        return CapabilityEventLogError(message)
    return CapabilityInvocationError(message)


def _load_generation_result_type() -> tuple[str, Any]:
    from astrid.core.generation import GENERATION_RESULT_KEY
    from astrid.core.generation.backends.base import GenerationResult

    return GENERATION_RESULT_KEY, GenerationResult


def _reconstruct_generation_result(result: InvocationResult) -> Any:
    generation_result_key, generation_result_type = _load_generation_result_type()

    if not result.ok:
        raise _sdk_exception_from_payload(result.error)

    raw_result = result.raw_result
    if not isinstance(raw_result, Mapping):
        raise CapabilityRuntimeError("generation executor returned a non-mapping raw_result")

    payload = raw_result.get("payload")
    if not isinstance(payload, Mapping):
        raise CapabilityRuntimeError("generation executor returned a non-mapping payload")

    if generation_result_key not in payload:
        raise CapabilityRuntimeError(
            f"generation executor payload is missing {generation_result_key!r}"
        )

    generation_payload = payload[generation_result_key]
    if isinstance(generation_payload, generation_result_type):
        return generation_payload
    if not isinstance(generation_payload, Mapping):
        raise CapabilityRuntimeError(
            f"generation executor payload {generation_result_key!r} must be a mapping or GenerationResult"
        )

    from_dict = getattr(generation_result_type, "from_dict", None)
    if not callable(from_dict):
        raise CapabilityRuntimeError("GenerationResult.from_dict is unavailable")

    reconstructed = from_dict(dict(generation_payload))
    if not isinstance(reconstructed, generation_result_type):
        raise CapabilityRuntimeError("GenerationResult.from_dict returned an unexpected type")
    return reconstructed


def _load_model_registry(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> Any:
    """Lazily load the generation model registry.

    Imported inside the call so ``import astrid`` does not pull in the
    model catalog, YAML parser, or backend registry until a facade method
    is actually invoked.
    """
    from astrid.core.model_catalog.registry import ModelRegistry

    return ModelRegistry.load_default(
        **_registry_load_kwargs(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        ),
    )


def _infer_image_mode(
    explicit_mode: str | None,
    inputs: dict[str, Any],
) -> str:
    """Infer the image generation mode.

    Inference rules (deliberately narrow):
    * ``image_ref`` present  → ``"i2i"``
    * ``image_ref`` absent   → ``"t2i"``
    * ``edit`` / ``inpaint`` / ``outpaint`` / ``upscale`` require an
      explicit *mode* argument — they cannot be inferred.
    """
    if explicit_mode is not None:
        return explicit_mode

    if inputs.get("image_ref"):
        return "i2i"
    return "t2i"


_EXPLICIT_ONLY_IMAGE_MODES: frozenset[str] = frozenset(
    {"edit", "inpaint", "outpaint", "upscale"}
)


def _infer_video_mode(
    explicit_mode: str | None,
    inputs: dict[str, Any],
) -> str:
    """Infer the video generation mode.

    Inference rules:
    * ``image_ref`` + ``image_end_ref`` present  → ``"flf"``
    * ``image_ref`` present only                  → ``"i2v"``
    * neither                                    → ``"t2v"``
    """
    if explicit_mode is not None:
        return explicit_mode

    has_image_ref = bool(inputs.get("image_ref"))
    has_image_end_ref = bool(inputs.get("image_end_ref"))

    if has_image_ref and has_image_end_ref:
        return "flf"
    if has_image_ref:
        return "i2v"
    return "t2v"


def _resolve_execution(
    model_entry: Any,
    mode: str,
    explicit_execution: str | None,
    *,
    model: str,
) -> str:
    """Validate or infer the execution backend for *(model, mode)*.

    * If *explicit_execution* is given it is validated against the
      backends declared for the mode.
    * If *explicit_execution* is ``None`` it is inferred **only** when
      exactly one non-Codex backend is declared; Codex is explicit-only for
      automatic inference so adding it does not change existing cloud/local
      defaults. Otherwise a clear diagnostic asks the caller to choose.
    """
    mode_spec = model_entry.modes.get(mode)
    if mode_spec is None:
        available_modes = ", ".join(sorted(model_entry.modes))
        raise CapabilityValidationError(
            f"Model {model!r} does not support mode {mode!r}. "
            f"Available modes: {available_modes}"
        )

    backend_ids = list(mode_spec.backends.keys())
    if not backend_ids:
        raise CapabilityValidationError(
            f"Model {model!r} mode {mode!r} has no configured backends"
        )

    if explicit_execution is not None:
        if explicit_execution not in backend_ids:
            raise CapabilityValidationError(
                f"Execution {explicit_execution!r} is not available for "
                f"model {model!r} mode {mode!r}. "
                f"Available: {', '.join(sorted(backend_ids))}"
            )
        return explicit_execution

    inference_backend_ids = [
        backend_id for backend_id in backend_ids if backend_id != "codex"
    ] or backend_ids
    if len(inference_backend_ids) == 1:
        return inference_backend_ids[0]

    raise CapabilityValidationError(
        f"Ambiguous execution for model {model!r} mode {mode!r}. "
        f"Available backends: {', '.join(sorted(backend_ids))}. "
        f"Please specify one explicitly via the 'execution' parameter."
    )


@dataclass(frozen=True)
class GenerationFacade:
    """Public typed facade for generation executors.

    Built-in ``image`` and ``video`` are first-class methods.  Plugin
    verbs registered via :func:`astrid.core.generation.verbs.register_verb`
    are resolved through ``__getattr__`` so that ``astrid.generate.<name>``
    works for third-party generation verbs without the facade importing
    plugin registration modules.

    .. note::

       **M1 static coverage gap — plugin-loaded generation verbs.**
       Only the built-in ``image`` and ``video`` methods are covered by the
       M1 ledger contract.  Plugin verbs registered via ``register_verb``
       and dispatched through ``__getattr__`` are intentionally out of scope
       for M1.  See ``docs/run-ledger-contract.md`` limits table.
    """

    def __getattr__(self, name: str) -> Any:
        """Resolve a plugin-registered generation verb by *name*.

        Called only when normal attribute lookup fails, so built-in
        ``image`` and ``video`` always take priority.

        .. note::

           Plugin-loaded generation verbs are an **M1 static coverage gap**.
           They are not subject to the M1 ledger contract and are
           intentionally excluded from conformance testing (see
           ``tests/test_run_ledger_conformance.py`` module docstring).
        """
        # Lazy-import the verb registry — do NOT import astrid.sdk from
        # the verbs module.
        from astrid.core.generation.verbs import (
            get_verb,
            list_verbs,
            load_generation_verb_plugins,
        )

        # Ensure plugin verbs are loaded (idempotent).
        load_generation_verb_plugins()

        try:
            return get_verb(name)
        except KeyError:
            known = list_verbs()
            hint = f" Available plugin verbs: {', '.join(known)}." if known else ""
            raise AttributeError(
                f"'GenerationFacade' has no attribute {name!r}. "
                f"Built-in methods: image, video.{hint}"
            ) from None

    def image(
        self,
        *,
        model: str,
        mode: str | None = None,
        execution: str | None = None,
        out: Path | str | None = None,
        project: str | None = None,
        project_root: str | Path | None = None,
        extra_pack_roots: tuple[str, ...] = (),
        include_installed: bool = True,
        banodoco_config: Any | None = None,
        active_theme: str | Path | None = None,
        include_missing_roots: bool = False,
        brief: Path | str | None = None,
        dry_run: bool = False,
        check_binaries: bool = False,
        python_exec: str | None = None,
        verbose: bool = False,
        argv: tuple[str, ...] = (),
        **inputs: Any,
    ) -> Any:
        # --- openai guard (SD-005) ---------------------------------------
        if execution == "openai":
            raise CapabilityPreconditionError(
                "astrid.generate.image does not support execution='openai'; use executor "
                "'generation.generate_image_openai' directly"
            )

        # --- mode inference / validation ---------------------------------
        resolved_mode = _infer_image_mode(mode, inputs)

        # --- model catalog validation ------------------------------------
        registry = _load_model_registry(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        )
        try:
            model_entry = registry.get(model)
        except KeyError as exc:
            raise CapabilityValidationError(str(exc)) from exc

        # Reject inference-only modes when they slip through
        if mode is None and resolved_mode in _EXPLICIT_ONLY_IMAGE_MODES:
            raise CapabilityValidationError(
                f"Mode {resolved_mode!r} requires an explicit 'mode' argument"
            )

        # --- execution inference / validation ----------------------------
        resolved_execution = _resolve_execution(
            model_entry,
            resolved_mode,
            execution,
            model=model,
        )

        # --- output routing -------------------------------------------------
        # The generate facade intentionally bypasses invoke()'s both-None
        # guard (see invoke() L1665) by always ensuring at least one of
        # ``out`` or ``project`` is set, or by auto-resolving a default
        # project when neither is supplied.
        if out is not None:
            # External out= path → thread into executor request so the
            # output lands at the caller-chosen location.  When project is
            # also explicitly supplied we pass both through — the runner
            # will enforce the strict project+out rejection (SD1).
            invoke_out = out
            invoke_project = project  # may be None → runner auto-resolves
        elif project is not None:
            invoke_out = None
            invoke_project = project
        else:
            from astrid.core.session.config import resolve_default_project_for_sdk

            invoke_out = None
            invoke_project = resolve_default_project_for_sdk(
                projects_root=project_root,
            )

        # --- invoke ------------------------------------------------------
        result = invoke(
            "generation.generate_image",
            kind="executor",
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
            banodoco_config=banodoco_config,
            active_theme=active_theme,
            include_missing_roots=include_missing_roots,
            out=invoke_out,
            project=invoke_project,
            inputs={
                "model": model,
                "mode": resolved_mode,
                "execution": resolved_execution,
                **inputs,
            },
            brief=brief,
            dry_run=dry_run,
            check_binaries=check_binaries,
            python_exec=python_exec,
            verbose=verbose,
            execution_mode="in_process",
            argv=argv,
        )
        if dry_run:
            # A dry run builds the command but does not generate, so there is no
            # GenerationResult to reconstruct — return the raw InvocationResult
            # (which carries the previewed command).
            return result
        return _reconstruct_generation_result(result)

    def video(
        self,
        *,
        model: str,
        mode: str | None = None,
        execution: str | None = None,
        out: Path | str | None = None,
        project: str | None = None,
        project_root: str | Path | None = None,
        extra_pack_roots: tuple[str, ...] = (),
        include_installed: bool = True,
        banodoco_config: Any | None = None,
        active_theme: str | Path | None = None,
        include_missing_roots: bool = False,
        brief: Path | str | None = None,
        dry_run: bool = False,
        check_binaries: bool = False,
        python_exec: str | None = None,
        verbose: bool = False,
        argv: tuple[str, ...] = (),
        **inputs: Any,
    ) -> Any:
        # --- mode inference / validation ---------------------------------
        resolved_mode = _infer_video_mode(mode, inputs)

        # --- model catalog validation ------------------------------------
        registry = _load_model_registry(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        )
        try:
            model_entry = registry.get(model)
        except KeyError as exc:
            raise CapabilityValidationError(str(exc)) from exc

        # --- execution inference / validation ----------------------------
        resolved_execution = _resolve_execution(
            model_entry,
            resolved_mode,
            execution,
            model=model,
        )

        # --- output routing -------------------------------------------------
        # The generate facade intentionally bypasses invoke()'s both-None
        # guard (see invoke() L1665) by always ensuring at least one of
        # ``out`` or ``project`` is set, or by auto-resolving a default
        # project when neither is supplied.
        if out is not None:
            # External out= path → thread into executor request so the
            # output lands at the caller-chosen location.  When project is
            # also explicitly supplied we pass both through — the runner
            # will enforce the strict project+out rejection (SD1).
            invoke_out = out
            invoke_project = project  # may be None → runner auto-resolves
        elif project is not None:
            invoke_out = None
            invoke_project = project
        else:
            from astrid.core.session.config import resolve_default_project_for_sdk

            invoke_out = None
            invoke_project = resolve_default_project_for_sdk(
                projects_root=project_root,
            )

        # --- invoke ------------------------------------------------------
        result = invoke(
            "generation.generate_video",
            kind="executor",
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
            banodoco_config=banodoco_config,
            active_theme=active_theme,
            include_missing_roots=include_missing_roots,
            out=invoke_out,
            project=invoke_project,
            inputs={
                "model": model,
                "mode": resolved_mode,
                "execution": resolved_execution,
                **inputs,
            },
            brief=brief,
            dry_run=dry_run,
            check_binaries=check_binaries,
            python_exec=python_exec,
            verbose=verbose,
            execution_mode="in_process",
            argv=argv,
        )
        if dry_run:
            # A dry run builds the command but does not generate, so there is no
            # GenerationResult to reconstruct — return the raw InvocationResult.
            return result
        return _reconstruct_generation_result(result)


generate = GenerationFacade()


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


def _discover_pack_inventory(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> tuple[Any, ...]:
    from astrid.core.pack.discovery import discover_pack_metadata

    return discover_pack_metadata(
        **_registry_load_kwargs(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        ),
    )


def _pack_record(discovered_pack: Any) -> dict[str, Any]:
    payload = discovered_pack.pack.to_dict()
    from astrid.core.pack.validate import extract_trust_summary

    trust_summary = extract_trust_summary(discovered_pack.pack.root)
    if "permissions" in trust_summary:
        payload["permissions"] = trust_summary["permissions"]
    if "permission_ids" in trust_summary:
        payload["permission_ids"] = trust_summary["permission_ids"]
    if "trust" in trust_summary:
        payload["trust"] = trust_summary["trust"]
    payload["source_kind"] = discovered_pack.source_kind
    payload["priority_index"] = discovered_pack.priority_index
    return _json_safe_mapping(payload)


def _pack_permission_ids_by_pack_id(discovered_packs: tuple[Any, ...]) -> dict[str, tuple[str, ...]]:
    permission_ids_by_pack_id: dict[str, tuple[str, ...]] = {}
    for discovered_pack in discovered_packs:
        pack = getattr(discovered_pack, "pack", None)
        if pack is None:
            continue
        permissions = getattr(pack, "permissions", ())
        permission_ids_by_pack_id[pack.id] = tuple(
            permission.id for permission in permissions
        )
    return permission_ids_by_pack_id


def _apply_pack_permission_ids(
    capability: Capability,
    *,
    pack_permission_ids_by_pack_id: Mapping[str, tuple[str, ...]] | None = None,
) -> Capability:
    if not pack_permission_ids_by_pack_id:
        return capability
    permission_ids = pack_permission_ids_by_pack_id.get(capability.handle.pack_id, ())
    if not permission_ids:
        return capability
    if capability.handle.safety.permissions == permission_ids:
        return capability
    return replace(
        capability,
        handle=replace(
            capability.handle,
            safety=replace(capability.handle.safety, permissions=permission_ids),
        ),
    )


def _generation_backend_record(descriptor: Any) -> dict[str, Any]:
    return _json_safe_mapping(
        {
            "id": descriptor.backend_id,
            "label": descriptor.label,
            "module": descriptor.module,
            "class": descriptor.class_name,
            "init_kwargs": descriptor.init_kwargs,
        }
    )


def _element_kind_record(descriptor: Any) -> dict[str, Any]:
    return _json_safe_mapping(
        {
            "id": descriptor.id,
            "singular": descriptor.singular,
            "plural": descriptor.plural,
            "canonical_kind": descriptor.canonical_kind,
            "aliases": descriptor.aliases,
            "label": descriptor.label,
            "description": descriptor.description,
        }
    )


def _generation_feature_record(descriptor: Any) -> dict[str, Any]:
    return _json_safe_mapping(
        {
            "id": descriptor.id,
            "label": descriptor.label,
            "description": descriptor.description,
        }
    )


def _generation_mode_record(descriptor: Any) -> dict[str, Any]:
    return _json_safe_mapping(
        {
            "id": descriptor.id,
            "modalities": descriptor.modalities,
            "label": descriptor.label,
            "description": descriptor.description,
        }
    )


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
    from astrid.core.generation.backends.registry import (
        GenerationBackendRegistry,
        descriptors_from_pack,
    )
    from astrid.core.generation.features import (
        GenerationTaxonomyRegistry,
        backend_descriptors_from_pack,
        feature_descriptors_from_pack,
        mode_descriptors_from_pack,
    )

    packs = tuple(_pack_record(discovered_pack) for discovered_pack in discovered_packs)

    backend_registry = GenerationBackendRegistry(
        descriptors=tuple(
            descriptor
            for discovered_pack in discovered_packs
            for descriptor in descriptors_from_pack(discovered_pack.pack)
        )
    )
    taxonomy_registry = GenerationTaxonomyRegistry(
        feature_descriptors=tuple(
            descriptor
            for discovered_pack in discovered_packs
            for descriptor in feature_descriptors_from_pack(discovered_pack.pack)
        ),
        mode_descriptors=tuple(
            descriptor
            for discovered_pack in discovered_packs
            for descriptor in mode_descriptors_from_pack(discovered_pack.pack)
        ),
        backend_descriptors=tuple(
            descriptor
            for discovered_pack in discovered_packs
            for descriptor in backend_descriptors_from_pack(discovered_pack.pack)
        ),
    )

    generation_backends = tuple(
        _generation_backend_record(descriptor)
        for descriptor in backend_registry.descriptors()
    )
    element_kinds = tuple(
        _element_kind_record(descriptor)
        for descriptor in element_registry.element_kind_registry.descriptors()
    )
    generation_features = tuple(
        _generation_feature_record(descriptor)
        for descriptor in taxonomy_registry.feature_descriptors()
    )
    generation_modes = tuple(
        _generation_mode_record(descriptor)
        for descriptor in taxonomy_registry.mode_descriptors()
    )
    return (
        packs,
        generation_backends,
        element_kinds,
        generation_features,
        generation_modes,
    )


def _capability_from_executor(
    definition: Any,
    registry: Any,
    *,
    requested_id: str | None = None,
    pack_permission_ids_by_pack_id: Mapping[str, tuple[str, ...]] | None = None,
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
    return _apply_pack_permission_ids(
        Capability(
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
        ),
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _capability_from_orchestrator(
    definition: Any,
    registry: Any,
    *,
    requested_id: str | None = None,
    pack_permission_ids_by_pack_id: Mapping[str, tuple[str, ...]] | None = None,
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
    return _apply_pack_permission_ids(
        Capability(
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
        ),
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _capability_from_element(
    definition: Any,
    *,
    pack_permission_ids_by_pack_id: Mapping[str, tuple[str, ...]] | None = None,
) -> Capability:
    from astrid.core.element.schema import to_capability_handle

    return _apply_pack_permission_ids(
        Capability(
        id=f"{definition.kind}/{definition.id}",
        capability_type="element",
        native_kind=definition.kind,
        handle=to_capability_handle(definition),
        schema=_json_safe_mapping(definition.schema),
        defaults=_json_safe_mapping(definition.defaults),
        definition=_json_safe_mapping(definition.to_dict()),
        ),
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _is_qualified_capability_id(capability_id: str) -> bool:
    return "." in capability_id


def _split_canonical_element_id(
    capability_id: str,
    *,
    registry: Any,
    strict: bool = False,
) -> tuple[str, str] | None:
    kind, sep, local_id = capability_id.partition("/")
    if not (sep and local_id):
        return None
    try:
        canonical_kind = registry.element_kind_registry.normalize(kind)
    except ValueError as exc:
        if strict:
            raise CapabilityValidationError(str(exc)) from exc
        return None
    return canonical_kind, local_id


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
        try:
            normalized_kind = registry.element_kind_registry.normalize(element_kind)
        except ValueError as exc:
            raise CapabilityValidationError(str(exc)) from exc
        canonical = _split_canonical_element_id(
            capability_id,
            registry=registry,
            strict=True,
        )
        if canonical is not None:
            requested_kind, requested_local_id = canonical
            if requested_kind != normalized_kind:
                raise CapabilityNotFoundError(
                    f"unknown element {capability_id!r} for explicit element_kind={normalized_kind!r}"
                )
            lookup_id = requested_local_id
        try:
            definition = registry.get(normalized_kind, lookup_id)
        except KeyError as exc:
            raise CapabilityNotFoundError(
                f"unknown element {capability_id!r} for explicit element_kind={normalized_kind!r}"
            ) from exc
        return _capability_from_element(definition)

    canonical = _split_canonical_element_id(
        capability_id,
        registry=registry,
        strict=True,
    )
    if canonical is not None:
        requested_kind, requested_local_id = canonical
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
    discovered_packs = _discover_pack_inventory(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    )
    pack_permission_ids_by_pack_id = _pack_permission_ids_by_pack_id(discovered_packs)
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
    (
        packs,
        generation_backends,
        element_kinds,
        generation_features,
        generation_modes,
    ) = _build_discovery_metadata(
        discovered_packs,
        element_registry=element_registry,
    )

    if pack_permission_ids_by_pack_id:
        executors = tuple(
            _capability_from_executor(
                definition,
                executor_registry,
                pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
            )
            for definition in executor_registry.list()
        )
        orchestrators = tuple(
            _capability_from_orchestrator(
                definition,
                orchestrator_registry,
                pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
            )
            for definition in orchestrator_registry.list()
        )
        elements = tuple(
            _capability_from_element(
                definition,
                pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
            )
            for definition in element_registry.list()
        )
    else:
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
        packs=packs,
        generation_backends=generation_backends,
        element_kinds=element_kinds,
        generation_features=generation_features,
        generation_modes=generation_modes,
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


def _payload_manifest_path(raw_result: Mapping[str, Any]) -> str | None:
    payload = raw_result.get("payload")
    if not isinstance(payload, Mapping):
        return None
    for key in ("manifest_path", "manifest"):
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        path = Path(value).expanduser().resolve()
        if path.name == "manifest.json":
            return str(path)
    return None


def _discover_invocation_manifest_path(
    raw_result: Mapping[str, Any],
    *,
    out: Path | str | None,
) -> str | None:
    manifest_path = _payload_manifest_path(raw_result)
    if manifest_path is not None:
        return manifest_path
    if out in (None, ""):
        return None
    candidate = Path(out).expanduser().resolve() / "manifest.json"
    return str(candidate) if candidate.is_file() else None


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
            # Both-None guard: executor invocations need at least one of
            # ``out`` (external output path) or ``project`` (ledgered run).
            # The generate facade (generate.image / generate.video)
            # intentionally bypasses this guard by always resolving a
            # project or threading an external out= path.
            if out is None and project is None:
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
                invocation="sdk",
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
                invocation="sdk",
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
    manifest_path = _discover_invocation_manifest_path(raw_result, out=out)
    return InvocationResult(
        capability_id=capability.id,
        capability_type=capability.capability_type,
        native_kind=capability.native_kind,
        ok=bool(getattr(result, "ok", False)),
        error=error,
        manifest_path=manifest_path,
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
    "generate",
    "get_capability",
    "invoke",
    "read_events",
    "run_executor",
    "run_orchestrator",
    "subscribe_events",
]
