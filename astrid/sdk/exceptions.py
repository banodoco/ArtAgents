"""Public SDK exception taxonomy and internal error mapping helpers.

These are re-exported from ``astrid.sdk_errors`` so the ``astrid.sdk`` package
presents a coherent public surface without exposing the internal module layout.
"""

from __future__ import annotations

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

__all__ = [
    "AstridSDKError",
    "CapabilityAmbiguousError",
    "CapabilityEventLogError",
    "CapabilityInvocationError",
    "CapabilityLeaseError",
    "CapabilityMissingInputError",
    "CapabilityNotFoundError",
    "CapabilityPreconditionError",
    "CapabilityRuntimeError",
    "CapabilityValidationError",
    "UnsupportedCapabilityError",
    "_error_payload_from_internal_error",
    "_internal_error_from_result",
    "_sdk_error_from_event_exception",
    "_sdk_error_from_exception",
]
