"""Public SDK exception taxonomy and internal error mapping helpers."""

from __future__ import annotations

from typing import Any

from astrid.core.contracts.exec_error import ExecError
from astrid.core.foundation.project_paths import ProjectPathError


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

    from astrid.core.contracts.event_log_error import EventLogError
    from astrid.core.execution.executor.runner import ExecutorRunnerError
    from astrid.core.execution.executor.schema import ExecutorValidationError
    from astrid.core.execution.orchestrator.runner import (
        OrchestratorRunError,
        OrchestratorRunnerError,
    )
    from astrid.core.execution.orchestrator.schema import OrchestratorValidationError
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
    if isinstance(exc, (StaleTailError, EventLogError)):
        return CapabilityEventLogError(str(exc))
    return None


def _error_payload_from_internal_error(error: Any, *, json_safe: Any) -> dict[str, Any]:
    payload = json_safe(error)
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
