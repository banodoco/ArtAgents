"""Lazy public SDK facade.

Importing ``astrid.sdk`` is intentionally transport-only. Product clients
must not pull local repositories, SQLite, CAS, or the retired thread store
into the normal import graph. Capability and rendering APIs remain available
through lazy attribute resolution for pack authors and existing callers.
"""

from __future__ import annotations

import importlib

_EXPORTS = {
    "AstridClient": ("client", "AstridClient"),
    "AliasRecord": ("dto", "AliasRecord"),
    "Capability": ("dto", "Capability"),
    "CapabilityHandle": ("dto", "CapabilityHandle"),
    "CapabilityType": ("dto", "CapabilityType"),
    "DiscoveryResult": ("dto", "DiscoveryResult"),
    "EventStreamRecord": ("dto", "EventStreamRecord"),
    "ExecError": ("dto", "ExecError"),
    "InvocationResult": ("dto", "InvocationResult"),
    "Output": ("dto", "Output"),
    "Port": ("dto", "Port"),
    "Provenance": ("dto", "Provenance"),
    "SafetyDeclaration": ("dto", "SafetyDeclaration"),
    "AstridSDKError": ("exceptions", "AstridSDKError"),
    "CapabilityAmbiguousError": ("exceptions", "CapabilityAmbiguousError"),
    "CapabilityEventLogError": ("exceptions", "CapabilityEventLogError"),
    "CapabilityInvocationError": ("exceptions", "CapabilityInvocationError"),
    "CapabilityLeaseError": ("exceptions", "CapabilityLeaseError"),
    "CapabilityMissingInputError": ("exceptions", "CapabilityMissingInputError"),
    "CapabilityNotFoundError": ("exceptions", "CapabilityNotFoundError"),
    "CapabilityPreconditionError": ("exceptions", "CapabilityPreconditionError"),
    "CapabilityRuntimeError": ("exceptions", "CapabilityRuntimeError"),
    "CapabilityValidationError": ("exceptions", "CapabilityValidationError"),
    "UnsupportedCapabilityError": ("exceptions", "UnsupportedCapabilityError"),
    "RenderContext": ("rendering", "RenderContext"),
    "render": ("rendering", "render"),
    "renderer_main": ("rendering", "renderer_main"),
    "support": ("rendering", "support"),
    "GenerationFacade": ("generation", "GenerationFacade"),
    "generate": ("generation", "generate"),
    "discover": ("invocation", "discover"),
    "get_capability": ("invocation", "get_capability"),
    "invoke": ("invocation", "invoke"),
    "invoke_result": ("invocation", "invoke_result"),
    "read_events": ("events", "read_events"),
    "subscribe_events": ("events", "subscribe_events"),
}

_PRIVATE_EXPORTS = {
    "_apply_pack_permission_ids": ("discovery", "_apply_pack_permission_ids"),
    "_build_discovery_metadata": ("discovery", "_build_discovery_metadata"),
    "_capability_from_element": ("discovery", "_capability_from_element"),
    "_capability_from_executor": ("discovery", "_capability_from_executor"),
    "_capability_from_orchestrator": ("discovery", "_capability_from_orchestrator"),
    "_discover_pack_inventory": ("discovery", "_discover_pack_inventory"),
    "_element_kind_record": ("discovery", "_element_kind_record"),
    "_format_candidates": ("discovery", "_format_candidates"),
    "_generation_backend_record": ("discovery", "_generation_backend_record"),
    "_generation_feature_record": ("discovery", "_generation_feature_record"),
    "_generation_mode_record": ("discovery", "_generation_mode_record"),
    "_load_element_registry": ("discovery", "_load_element_registry"),
    "_load_executor_registry": ("discovery", "_load_executor_registry"),
    "_load_orchestrator_registry": ("discovery", "_load_orchestrator_registry"),
    "_load_registries": ("discovery", "_load_registries"),
    "_pack_permission_ids_by_pack_id": ("discovery", "_pack_permission_ids_by_pack_id"),
    "_pack_record": ("discovery", "_pack_record"),
    "_resolve_capability": ("discovery", "_resolve_capability"),
    "_resolve_capability_kindless": ("discovery", "_resolve_capability_kindless"),
    "_resolve_element_capability": ("discovery", "_resolve_element_capability"),
    "_resolve_executor_capability": ("discovery", "_resolve_executor_capability"),
    "_resolve_orchestrator_capability": ("discovery", "_resolve_orchestrator_capability"),
    "_split_canonical_element_id": ("discovery", "_split_canonical_element_id"),
    "_discover_invocation_manifest_path": ("invocation", "_discover_invocation_manifest_path"),
    "_normalize_executor_result": ("invocation", "_normalize_executor_result"),
    "_normalize_orchestrator_result": ("invocation", "_normalize_orchestrator_result"),
    "_payload_manifest_path": ("invocation", "_payload_manifest_path"),
    "_EXPLICIT_ONLY_IMAGE_MODES": ("generation", "_EXPLICIT_ONLY_IMAGE_MODES"),
    "_infer_image_mode": ("generation", "_infer_image_mode"),
    "_infer_video_mode": ("generation", "_infer_video_mode"),
    "_load_model_registry": ("generation", "_load_model_registry"),
    "_registry_load_kwargs": ("discovery", "_registry_load_kwargs"),
    "_resolve_execution": ("generation", "_resolve_execution"),
    "_json_safe": ("dto", "_json_safe"),
    "_json_safe_mapping": ("dto", "_json_safe_mapping"),
    "_error_payload_from_internal_error": ("exceptions", "_error_payload_from_internal_error"),
    "_internal_error_from_result": ("exceptions", "_internal_error_from_result"),
    "_sdk_error_from_event_exception": ("exceptions", "_sdk_error_from_event_exception"),
    "_sdk_error_from_exception": ("exceptions", "_sdk_error_from_exception"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    target = _EXPORTS.get(name) or _PRIVATE_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    return getattr(importlib.import_module(f".{module_name}", __name__), attribute)
