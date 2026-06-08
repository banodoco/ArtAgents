"""Public SDK DTOs and JSON-safe result helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Literal

from astrid.core.contracts.exec_error import ExecError
from astrid.core.contracts.schema import CapabilityHandle, Output, Port

from .exceptions import (
    AstridSDKError,
    CapabilityEventLogError,
    CapabilityInvocationError,
    CapabilityLeaseError,
    CapabilityMissingInputError,
    CapabilityPreconditionError,
    CapabilityRuntimeError,
    CapabilityValidationError,
)

CapabilityType = Literal["executor", "orchestrator", "element"]


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
