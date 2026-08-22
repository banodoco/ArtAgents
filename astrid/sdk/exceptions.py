"""Public SDK exception taxonomy and internal error mapping helpers.

The module carries two layers:

- the **legacy capability taxonomy** (:class:`AstridSDKError` and the
  ``Capability*`` subclasses) used by the reduced public SDK's lazy
  discovery/invoke/generate/render/event APIs; and
- the **frozen m4 service-error taxonomy** (SDK contract
  ``docs/contracts/astrid-sdk-v10.md`` section 2): :class:`ServiceError`
  and its nine exact-code subclasses, plus :func:`map_error`, the
  centralized bounded exception mapper that turns any exception — kernel
  repository errors, receipt mismatches, writer unavailability, or
  unexpected internals — into the frozen three-key error object with
  redaction (no SQL, filesystem paths, receipt internals, request bodies,
  or secrets may leak).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from astrid.core.audit.util import SECRET_VALUE_RE
from astrid.core.contracts.exec_error import ExecError
from astrid.core.foundation.project_paths import ProjectPathError

from .contracts import ErrorObject

MAX_ERROR_MESSAGE_LENGTH = 500
"""Upper bound for a redacted internal-error message."""

_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:/|[A-Za-z]:[\\/])"
    r"(?:[A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.-]*"
)
"""Matches absolute POSIX or Windows paths so they never leak in messages."""

_WHITESPACE_RE = re.compile(r"\s+")


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
    from astrid.core.events import NotWriterError, StaleEpochError, StaleTailError
    from astrid.core.execution.executor.runner import ExecutorRunnerError
    from astrid.core.execution.executor.schema import ExecutorValidationError
    from astrid.core.execution.orchestrator.runner import (
        OrchestratorRunError,
        OrchestratorRunnerError,
    )
    from astrid.core.execution.orchestrator.schema import OrchestratorValidationError

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
    # The legacy session/lease authority was removed in the m6 cutover and
    # its module must never be imported from a product path. Errors raised
    # by the in-tree legacy session code still surface through this mapper,
    # so they are classified by origin module path — never by import — and
    # map to the lease-error category alongside the kernel writer/epoch
    # errors (the SDK class stays for the public envelope surface).
    if isinstance(exc, (NotWriterError, StaleEpochError)):
        return CapabilityLeaseError(str(exc))
    if type(exc).__module__.startswith("astrid.core.session"):
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


# ---------------------------------------------------------------------------
# Frozen m4 service-error taxonomy (SDK contract v10 section 2)
# ---------------------------------------------------------------------------


class ServiceError(AstridSDKError):
    """Base for the frozen m4 service-error taxonomy (SDK contract §2).

    Every subclass carries exactly one machine ``code`` from the nine-code
    taxonomy, a stable human-readable message, and a **bounded** ``details``
    mapping. Details are redacted at construction time (secret-looking
    values become ``<redacted>``) and validated as bounded JSON, so a
    service error can never leak secrets or unbounded payloads downstream.
    """

    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        if not isinstance(message, str) or not message:
            raise TypeError("service error message must be a non-empty string")
        raw_details = dict(details or {})
        try:
            self.details: Mapping[str, Any] = MappingProxyType(
                _redact_details(raw_details)
            )
        except (TypeError, ValueError) as exc:
            raise TypeError(f"service error details must be JSON-safe: {exc}") from exc
        super().__init__(message)

    def to_error_object(self) -> ErrorObject:
        """Return the frozen three-key error object for this error."""
        return ErrorObject(
            code=self.code,
            message=str(self),
            details=dict(self.details),
        )


class ServiceValidationError(ServiceError):
    """Input failed schema/grammar validation (``validation_error``)."""

    code = "validation_error"


class ServiceNotFoundError(ServiceError):
    """The addressed record does not exist (``not_found``)."""

    code = "not_found"


class ServiceConflictError(ServiceError):
    """A write conflicted with current state (``conflict``)."""

    code = "conflict"


class ServiceStaleVersionError(ServiceError):
    """A CAS write supplied a stale expected version/head (``stale_version``)."""

    code = "stale_version"


class ServiceTerminalStateError(ServiceError):
    """A mutation targeted a terminal record (``terminal_state``)."""

    code = "terminal_state"


class ServiceIdempotencyMismatchError(ServiceError):
    """An idempotency key was reused with different canonical input.

    Raised (or mapped) **before any mutation**: no sequence allocation, no
    event append, no projection change, and no receipt write
    (``idempotency_mismatch``).
    """

    code = "idempotency_mismatch"


class ServiceIntegrityError(ServiceError):
    """Persisted bytes/state failed verification (``integrity_error``)."""

    code = "integrity_error"


class ServiceUnavailableError(ServiceError):
    """The writer/owner lock/service is unavailable (``unavailable``)."""

    code = "unavailable"


class ServiceInternalError(ServiceError):
    """Any unexpected exception, bounded without leaking internals.

    The message is redacted (paths, secrets, and excess length stripped) so
    an internal failure never surfaces SQL, filesystem paths, receipt
    internals, request bodies, or secrets (``internal_error``).
    """

    code = "internal_error"


# ---------------------------------------------------------------------------
# Redaction (SDK contract v10 sections 2.1/2.2: bounded, non-leaking)
# ---------------------------------------------------------------------------


def _redact_details(value: Any) -> Any:
    """Recursively redact secret-shaped values inside ``details``.

    The frozen contract forbids secrets in ``details``; values that look
    like provider/API tokens are replaced with ``<redacted>`` while every
    other JSON value passes through unchanged (typed fields such as
    ``project_id`` or ``valid_options`` are legitimate).
    """
    if isinstance(value, Mapping):
        return {
            str(key): _redact_details(item) for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_details(item) for item in value]
    if isinstance(value, str):
        return SECRET_VALUE_RE.sub("<redacted>", value)
    return value


def _redact_message(text: str) -> str:
    """Return *text* with paths, secrets, and excess length stripped.

    The result is a stable, bounded, human-readable message that cannot
    leak SQL text, absolute filesystem paths, or secret tokens.
    """
    scrubbed = _ABSOLUTE_PATH_RE.sub("<path>", text)
    scrubbed = SECRET_VALUE_RE.sub("<redacted>", scrubbed)
    scrubbed = _WHITESPACE_RE.sub(" ", scrubbed).strip()
    if len(scrubbed) > MAX_ERROR_MESSAGE_LENGTH:
        scrubbed = scrubbed[: MAX_ERROR_MESSAGE_LENGTH - 3].rstrip() + "..."
    return scrubbed


# ---------------------------------------------------------------------------
# Centralized bounded exception mapping (SDK contract v10 section 2)
# ---------------------------------------------------------------------------

_SERVICE_ERROR_MESSAGES: dict[str, str] = {
    "validation_error": "the request failed validation",
    "not_found": "the requested record does not exist",
    "conflict": "the write conflicts with current state",
    "stale_version": "the write supplied a stale expected version",
    "terminal_state": "the record is in a terminal state",
    "idempotency_mismatch": (
        "idempotency key reused with a different request"
    ),
    "integrity_error": "persisted data failed integrity verification",
    "unavailable": "the writer or service is unavailable",
}
"""Stable, non-leaking messages for mapped kernel errors."""

_SERVICE_ERROR_CLASSES: dict[str, type[ServiceError]] = {
    "validation_error": ServiceValidationError,
    "not_found": ServiceNotFoundError,
    "conflict": ServiceConflictError,
    "stale_version": ServiceStaleVersionError,
    "terminal_state": ServiceTerminalStateError,
    "idempotency_mismatch": ServiceIdempotencyMismatchError,
    "integrity_error": ServiceIntegrityError,
    "unavailable": ServiceUnavailableError,
    "internal_error": ServiceInternalError,
}
"""Exact code -> subclass map for the closed nine-code taxonomy."""


def _service_error_from_exception(exc: BaseException) -> ServiceError | None:
    """Map one kernel/known exception to its frozen service error.

    Imports are lazy so importing this module never pulls in repository or
    pack machinery. The mapping is category-based and closed: every
    concrete kernel error class belongs to exactly one taxonomy code, and
    anything not listed falls through to ``internal_error`` in
    :func:`map_error`.
    """
    from astrid.core.events import NotWriterError, StaleEpochError, StaleTailError
    from astrid.core.events.service import (
        EventChainError,
        EventHeadConflictError,
        EventIdempotencyError,
        EventStreamNotFoundError,
        EventValidationError,
    )
    from astrid.core.receipts.service import (
        ReceiptMismatchError,
        ReceiptValidationError,
    )
    from astrid.core.repositories.errors import (
        CommandVocabularyError,
        EventVocabularyError,
        StreamAgreementError,
        StreamVocabularyError,
    )
    from astrid.core.repositories.evidence import EvidenceValidationError
    from astrid.core.io.media_import import MediaIntegrityError
    from astrid.core.repositories.media import (
        MediaAlreadyExistsError,
        MediaConflictError,
        MediaLocationNotFoundError,
        MediaNotFoundError,
        MediaRelationError,
        MediaValidationError,
        MediaVerificationError,
    )
    from astrid.core.repositories.projects import (
        ProjectAlreadyExistsError,
        ProjectNotFoundError,
        ProjectSlugConflictError,
        ProjectValidationError,
    )
    from astrid.core.repositories.runs import (
        RunAlreadyExistsError,
        RunNotFoundError,
        RunStaleHeadError,
        RunTerminalError,
        RunValidationError,
    )
    from astrid.core.repositories.tasks import (
        TaskAlreadyExistsError,
        TaskAttemptNotFoundError,
        TaskDependencyError,
        TaskNotFoundError,
        TaskTransitionError,
        TaskValidationError,
    )
    from astrid.core.store.writer import (
        TransactionControlError,
        WriterBusyError,
        WriterShutdownError,
    )
    from astrid.packs.references.repository import (
        ReferenceAlreadyExistsError,
        ReferenceArchivedError,
        ReferenceAssociationError,
        ReferenceLinkError,
        ReferenceMediaError,
        ReferenceNotFoundError,
        ReferencePrimaryError,
        ReferenceValidationError,
    )
    from astrid.packs.shots.repository import (
        ShotAlreadyExistsError,
        ShotItemNotFoundError,
        ShotMediaError,
        ShotNotFoundError,
        ShotReorderError,
        ShotValidationError,
    )
    from astrid.packs.timeline.repository import (
        TimelineAlreadyExistsError,
        TimelineNotFoundError,
        TimelineSlugConflictError,
        TimelineUlidConflictError,
        TimelineValidationError,
        TimelineVersionConflictError,
    )

    if isinstance(exc, ReceiptMismatchError):
        return ServiceIdempotencyMismatchError(
            _SERVICE_ERROR_MESSAGES["idempotency_mismatch"],
            details={
                "project_id": exc.project_id,
                "idempotency_key": exc.idempotency_key,
            },
        )

    not_found = (
        ProjectNotFoundError,
        TimelineNotFoundError,
        TaskNotFoundError,
        TaskAttemptNotFoundError,
        MediaNotFoundError,
        MediaLocationNotFoundError,
        RunNotFoundError,
        ShotNotFoundError,
        ShotItemNotFoundError,
        ReferenceNotFoundError,
        EventStreamNotFoundError,
    )
    conflict = (
        ProjectAlreadyExistsError,
        ProjectSlugConflictError,
        TimelineAlreadyExistsError,
        TimelineSlugConflictError,
        TimelineUlidConflictError,
        TaskAlreadyExistsError,
        MediaAlreadyExistsError,
        MediaConflictError,
        RunAlreadyExistsError,
        ShotAlreadyExistsError,
        ReferenceAlreadyExistsError,
        EventIdempotencyError,
        StaleEpochError,
        StaleTailError,
    )
    stale_version = (
        TimelineVersionConflictError,
        RunStaleHeadError,
        EventHeadConflictError,
    )
    terminal_state = (
        RunTerminalError,
        TaskTransitionError,
        ReferenceArchivedError,
    )
    validation = (
        ProjectValidationError,
        TimelineValidationError,
        TaskValidationError,
        TaskDependencyError,
        MediaValidationError,
        MediaRelationError,
        RunValidationError,
        ShotValidationError,
        ShotMediaError,
        ShotReorderError,
        ReferenceValidationError,
        ReferenceAssociationError,
        ReferencePrimaryError,
        ReferenceLinkError,
        ReferenceMediaError,
        EvidenceValidationError,
        ReceiptValidationError,
        EventValidationError,
        StreamVocabularyError,
        EventVocabularyError,
        CommandVocabularyError,
        StreamAgreementError,
    )
    unavailable = (
        NotWriterError,
        WriterBusyError,
        WriterShutdownError,
        TransactionControlError,
    )
    integrity = (EventChainError, MediaVerificationError, MediaIntegrityError)

    for error_type, code in (
        (not_found, "not_found"),
        (conflict, "conflict"),
        (stale_version, "stale_version"),
        (terminal_state, "terminal_state"),
        (validation, "validation_error"),
        (unavailable, "unavailable"),
        (integrity, "integrity_error"),
    ):
        if isinstance(exc, error_type):
            return _SERVICE_ERROR_CLASSES[code](_SERVICE_ERROR_MESSAGES[code])

    return None


def map_error(exc: BaseException, *, redact: bool = True) -> ErrorObject:
    """Centralized bounded mapping of *any* exception to a frozen error object.

    - :class:`ServiceError` instances pass through unchanged;
    - known kernel errors (repository, receipt, event, writer) map to their
      frozen taxonomy code with a stable, non-leaking message;
    - anything else maps to ``internal_error`` with a redacted message
      (paths, secrets, and excess length stripped) and a bounded
      ``details`` carrying only the exception class name.

    The result is always a three-key :class:`ErrorObject`; ``redact=False``
    keeps the message verbatim (callers that already sanitized it).
    """
    if isinstance(exc, ServiceError):
        return exc.to_error_object()
    mapped = _service_error_from_exception(exc)
    if mapped is not None:
        return mapped.to_error_object()
    message = str(exc) if str(exc) else exc.__class__.__name__
    if redact:
        message = _redact_message(message)
    return ErrorObject(
        code="internal_error",
        message=message or "unexpected internal error",
        details={"error_type": exc.__class__.__name__},
    )