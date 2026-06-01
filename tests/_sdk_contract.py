from __future__ import annotations

EXPECTED_PUBLIC_NAMES = (
    "discover",
    "get_capability",
    "invoke",
    "read_events",
    "subscribe_events",
    "Capability",
    "DiscoveryResult",
    "EventStreamRecord",
    "InvocationResult",
    "AstridSDKError",
    "CapabilityNotFoundError",
    "CapabilityAmbiguousError",
    "CapabilityValidationError",
    "CapabilityMissingInputError",
    "CapabilityPreconditionError",
    "CapabilityRuntimeError",
    "CapabilityLeaseError",
    "CapabilityEventLogError",
    "UnsupportedCapabilityError",
    "CapabilityInvocationError",
    "CapabilityHandle",
    "Port",
    "Output",
    "AliasRecord",
    "Provenance",
    "SafetyDeclaration",
    "ExecError",
)

HEAVY_MODULES = (
    "astrid.sdk",
    "astrid.core.executor.registry",
    "astrid.core.executor.runner",
    "astrid.core.orchestrator.registry",
    "astrid.core.orchestrator.runner",
)
