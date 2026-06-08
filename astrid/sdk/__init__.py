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

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
from .exceptions import (
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

# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------
from .dto import (
    AliasRecord,
    Capability,
    CapabilityHandle,
    CapabilityType,
    DiscoveryResult,
    EventStreamRecord,
    ExecError,
    InvocationResult,
    Output,
    Port,
    Provenance,
    SafetyDeclaration,
    _json_safe,
    _json_safe_mapping,
)

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
from astrid.core.task.event_stream import (
    read_event_stream as _read_task_event_stream,
    subscribe_event_stream as _subscribe_task_event_stream,
)
from .events import (
    _resolve_event_stream_run_dir,
    read_events,
    subscribe_events,
)

# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
from .generation import (
    GenerationFacade,
    _EXPLICIT_ONLY_IMAGE_MODES,
    _infer_image_mode,
    _infer_video_mode,
    _load_model_registry,
    _resolve_execution,
    generate,
)

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
from .discovery import (
    discover,
    get_capability,
    _apply_pack_permission_ids,
    _build_discovery_metadata,
    _candidate_label,
    _capability_from_element,
    _capability_from_executor,
    _capability_from_orchestrator,
    _discover_pack_inventory,
    _element_kind_record,
    _format_candidates,
    _generation_backend_record,
    _generation_feature_record,
    _generation_mode_record,
    _is_qualified_capability_id,
    _load_element_registry,
    _load_executor_registry,
    _load_orchestrator_registry,
    _load_registries,
    _pack_permission_ids_by_pack_id,
    _pack_record,
    _registry_load_kwargs,
    _resolve_capability,
    _resolve_capability_kindless,
    _resolve_element_capability,
    _resolve_executor_capability,
    _resolve_orchestrator_capability,
    _split_canonical_element_id,
)

# ---------------------------------------------------------------------------
# Invocation
# ---------------------------------------------------------------------------
from .invocation import (
    invoke,
    run_executor,
    run_orchestrator,
    _discover_invocation_manifest_path,
    _normalize_executor_result,
    _normalize_orchestrator_result,
    _payload_manifest_path,
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
