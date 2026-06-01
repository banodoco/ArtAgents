"""Astrid: a harness toolkit for agents and humans to make art."""

from __future__ import annotations

import importlib

_SDK_EXPORTS = (
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

__all__ = _SDK_EXPORTS


def __getattr__(name: str):
    if name not in _SDK_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(".sdk", __name__)
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_SDK_EXPORTS))
