"""Public SDK exception taxonomy and internal error mapping helpers.

The module carries two layers:

- the **legacy capability taxonomy** (:class:`AstridSDKError` and the
  ``Capability*`` subclasses) used by the reduced public SDK's lazy
  discovery/invoke/generate/render/event APIs; and
- the **frozen m4 service-error taxonomy** (SDK contract
  ``docs/contracts/platform-contract.md``): :class:`ServiceError`
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

    def __init__(
        self, message: str, *, details: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.details = dict(details or {})


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
    if isinstance(exc, ProjectPathError):
        return CapabilityValidationError(str(exc))

    error_name = type(exc).__name__

    if error_name in {"ExecutorRunnerError", "OrchestratorRunnerError"}:
        if _looks_like_missing_input(str(exc)):
            return CapabilityMissingInputError(str(exc))
        return CapabilityValidationError(str(exc))
    if error_name in {"ExecutorValidationError", "OrchestratorValidationError"}:
        return CapabilityValidationError(str(exc))
    if isinstance(exc, ExecError):
        if exc.type == "precondition":
            return CapabilityPreconditionError(exc.message)
        if exc.type == "process":
            return CapabilityRuntimeError(exc.message)
        return CapabilityInvocationError(exc.message)
    if error_name == "OrchestratorRunError":
        if exc.kind == "precondition":
            return CapabilityPreconditionError(exc.message)
        return CapabilityRuntimeError(exc.message)
    if error_name in {"NotWriterError", "StaleEpochError"}:
        return CapabilityLeaseError(str(exc))
    if error_name in {"StaleTailError", "EventLogError"}:
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


def _stale_version_error(
    exc: BaseException,
    *,
    timeline_error: bool = False,
) -> ServiceStaleVersionError:
    """Map a stale CAS error with actionable, bounded recovery guidance.

    The kernel CAS exceptions carry the two values an editor needs to recover,
    but the old mapper discarded them.  Keep the error object shape frozen and
    expose only the typed version fields in ``details``; the human message is
    deliberately concise and contains the public show -> merge -> save rule.
    """
    details: dict[str, Any] = {}
    expected_version = getattr(exc, "expected_version", None)
    current_version = getattr(exc, "current_version", None)
    if expected_version is None:
        expected_version = getattr(exc, "expected_head_seq", None)
    if current_version is None:
        current_version = getattr(exc, "actual_head_seq", None)
    if isinstance(expected_version, int) and not isinstance(expected_version, bool):
        details["expected_version"] = expected_version
    if isinstance(current_version, int) and not isinstance(current_version, bool):
        details["current_version"] = current_version

    if timeline_error and {
        "expected_version",
        "current_version",
    } <= details.keys():
        message = (
            "timeline save rejected: expected version "
            f"{details['expected_version']}, current version "
            f"{details['current_version']}; no write occurred. "
            "Recovery: show the current timeline, merge your changes into "
            "it, then save with its config_version as --expected-version. "
            "Reuse the same idempotency key only for the same request; use a "
            "fresh key for the merged save."
        )
    else:
        message = (
            "stale CAS write rejected; no write occurred. Re-read the current "
            "record, merge your changes, then save against its current "
            "version. Reuse the same idempotency key only for the same "
            "request; use a fresh key for a new merged save."
        )
    return ServiceStaleVersionError(message, details=details)


def _task_dependency_error(exc: BaseException) -> ServiceValidationError:
    """Map task graph/input failures to bounded, agent-actionable details."""
    details: dict[str, Any] = {
        "field": "dependencies",
        "recovery": (
            "Pass dependency objects, for example "
            '[{"task_id":"<task-id>","kind":"hard","ordinal":0}]'
        ),
    }
    raw_details = getattr(exc, "details", None)
    if isinstance(raw_details, Mapping):
        details.update(dict(raw_details))
    for name in ("task_id", "depends_on_task_id", "reason"):
        value = getattr(exc, name, None)
        if value is not None:
            details[name] = value
    return ServiceValidationError(
        "task dependency input was rejected; see details for the expected "
        "object shape and recovery",
        details=details,
    )


def _blocked_task_retry_error(exc: BaseException) -> ServiceValidationError:
    """Map blocked-task retry attempts to truthful recovery guidance."""
    detail = str(getattr(exc, "detail", None) or exc)
    return ServiceValidationError(
        "task retry is unavailable while the task is blocked by hard "
        "prerequisites; see details for recovery",
        details={
            "task_id": getattr(exc, "task_id", None),
            "reason": "dependency_unsatisfied",
            "detail": detail,
            "recovery": (
                "Wait for every hard prerequisite to succeed. If any hard "
                "prerequisite is failed or cancelled, cancel this dependent "
                "and create a replacement prerequisite chain."
            ),
        },
    )

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
    # Do not import local repositories, receipts, events, or the SQLite writer
    # here.  SDK errors can be raised while the runtime is unavailable, and
    # mapping those errors must not re-enter the retired local authority.
    error_name = type(exc).__name__

    def is_error(*names: str) -> bool:
        return error_name in names

    if is_error("MediaDecodabilityError"):
        recovery = (
            "install ffprobe (from the ffmpeg package) and retry"
            if exc.probe_reason == "ffprobe_unavailable"
            else "replace the file with a valid decodable media file and retry"
        )
        return ServiceValidationError(
            "media import rejected an undecodable container before admission",
            details={
                "entity": "media",
                "reason": exc.probe_reason,
                "media_kind": exc.media_kind,
                "mime_type": exc.mime_type,
                "extension": exc.extension,
                "recovery": recovery,
            },
        )

    if is_error("TimelineNotFoundError"):
        return ServiceNotFoundError(
            "the requested timeline does not exist in this project; verify the project and timeline ref",
            details={
                "entity": "timeline",
                "ref": exc.ref,
                "project_id": exc.project_id,
                "recovery": "run `astrid timelines list --project <project>` and retry with a listed slug or id",
            },
        )
    if is_error("TimelineSlugConflictError"):
        return ServiceConflictError(
            "timeline slug is already in use in this project; choose a different slug",
            details={
                "entity": "timeline",
                "field": "slug",
                "slug": exc.slug,
                "project_id": exc.project_id,
                "recovery": "run `astrid timelines list --project <project>` and retry with a new slug",
            },
        )
    if is_error("TimelineAmbiguousError"):
        return ServiceValidationError(
            "timeline display name is ambiguous; retry with one candidate id, ULID, or slug",
            details={
                "entity": "timeline",
                "field": "ref",
                "reason": "ambiguous_display_name",
                "name": exc.name,
                "candidates": exc.candidates,
                "recovery": "retry with candidates[].id, candidates[].timeline_ulid, or candidates[].slug",
            },
        )

    # Pack ownership guards already know which endpoint was foreign. Preserve
    # those facts in the public error details instead of collapsing an
    # actionable cross-project rejection into the generic validation message.
    if is_error("ShotMediaError"):
        details = {
            "entity": "shot_media",
            "reason": exc.detail,
            "media_id": exc.media_id,
            "project_id": exc.project_id,
            "recovery": (
                "run `astrid media list --project <project>` to choose a media "
                "id owned by the target project, then retry the shot command"
            ),
        }
        if exc.shot_id is not None:
            details["shot_id"] = exc.shot_id
        return ServiceValidationError(
            "shot media must belong to the target project; see details for the offending id",
            details=details,
        )
    if is_error("ShotReorderError"):
        return ServiceValidationError(
            "shot reorder rejected; supply the complete current item permutation",
            details={
                "entity": "shot_items",
                "shot_id": exc.shot_id,
                "reason": exc.detail,
                "item_ids": list(exc.item_ids),
                "recovery": (
                    "run `astrid timelines shots show <shot> --project <project>` "
                    "and retry with its complete current item ids exactly once"
                ),
            },
        )
    if is_error("ReferenceMediaError"):
        return ServiceValidationError(
            "reference media must belong to the target project; see details for the offending id",
            details={
                "entity": "reference_media",
                "reason": exc.detail,
                "media_id": exc.media_id,
                "project_id": exc.project_id,
                "recovery": (
                    "run `astrid media list --project <project>` and retry with "
                    "a media id owned by that project"
                ),
            },
        )
    if is_error("ReferenceAssociationError"):
        details = {
            "entity": "reference_association",
            "reason": exc.detail,
            "recovery": (
                "run `astrid media references show <reference> --project <project>` "
                "and `astrid media list --project <project>`, then retry with "
                "same-project ids"
            ),
        }
        for name in (
            "reference_id",
            "project_id",
            "media_id",
            "role",
            "context_task_id",
        ):
            value = getattr(exc, name, None)
            if value is not None:
                details[name] = value
        return ServiceValidationError(
            "reference association rejected; see details for the offending ownership or role",
            details=details,
        )
    if is_error("ReferenceArchivedError"):
        return ServiceTerminalStateError(
            "reference is archived; unarchive it before adding an association",
            details={
                "entity": "reference",
                "reference_id": exc.reference_id,
                "recovery": (
                    "run `astrid media references recover <ref> --project <project>` "
                    "then retry the association"
                ),
            },
        )
    if is_error("ReferencePrimaryError"):
        details = {
            "entity": "reference_primary",
            "reason": exc.detail,
            "recovery": (
                "run `astrid media references show <reference> --project <project>` "
                "and retry with one canonical association id"
            ),
        }
        for name in ("reference_id", "media_reference_id", "role"):
            value = getattr(exc, name, None)
            if value is not None:
                details[name] = value
        return ServiceValidationError(
            "reference primary change rejected; see details for the offending association",
            details=details,
        )
    if is_error("ReferenceLinkError"):
        details = {
            "entity": "reference_link",
            "reason": exc.detail,
            "recovery": (
                "run `astrid media references list --project <project> --include-archived` "
                "and retry with two active references from that project"
            ),
        }
        for name in ("from_reference_id", "to_reference_id", "kind"):
            value = getattr(exc, name, None)
            if value is not None:
                details[name] = value
        return ServiceValidationError(
            "reference link rejected; see details for the offending endpoint",
            details=details,
        )

    if is_error("ReceiptMismatchError"):
        return ServiceIdempotencyMismatchError(
            _SERVICE_ERROR_MESSAGES["idempotency_mismatch"],
            details={
                "project_id": exc.project_id,
                "idempotency_key": exc.idempotency_key,
            },
        )

    not_found = {
        "ProjectNotFoundError", "TimelineNotFoundError", "TaskNotFoundError",
        "TaskAttemptNotFoundError", "MediaNotFoundError", "MediaLocationNotFoundError",
        "RunNotFoundError", "ShotNotFoundError", "ShotItemNotFoundError",
        "ReferenceNotFoundError", "EventStreamNotFoundError",
    }
    conflict = {
        "ProjectAlreadyExistsError", "ProjectSlugConflictError", "TimelineAlreadyExistsError",
        "TimelineSlugConflictError", "TimelineUlidConflictError", "TaskAlreadyExistsError",
        "MediaAlreadyExistsError", "MediaConflictError", "RunAlreadyExistsError",
        "ShotAlreadyExistsError", "ReferenceAlreadyExistsError", "EventIdempotencyError",
        "StaleEpochError", "StaleTailError",
    }
    stale_version = {"TimelineVersionConflictError", "RunStaleHeadError", "EventHeadConflictError"}
    terminal_state = {"RunTerminalError", "TaskTransitionError", "ReferenceArchivedError"}
    validation = {
        "ProjectAmbiguousError", "ProjectValidationError", "TimelineValidationError",
        "TaskValidationError", "TaskDependencyError", "MediaValidationError",
        "MediaRelationError", "RunValidationError", "ShotValidationError", "ShotMediaError",
        "ShotReorderError", "ReferenceValidationError", "ReferenceAssociationError",
        "ReferencePrimaryError", "ReferenceLinkError", "ReferenceMediaError",
        "EvidenceValidationError", "ReceiptValidationError", "EventValidationError",
        "StreamVocabularyError", "EventVocabularyError", "CommandVocabularyError",
        "StreamAgreementError",
    }
    unavailable = {
        "NotWriterError", "WriterBusyError", "WriterShutdownError",
        "TransactionControlError", "WriterSidecarError",
    }
    integrity = {"EventChainError", "MediaVerificationError", "MediaIntegrityError"}

    # Dependency admission and blocked-task retry need their typed context;
    # flattening either to the generic validation/terminal message forces an
    # agent to guess the accepted schema or recovery action.
    if error_name == "TaskDependencyError":
        return _task_dependency_error(exc)
    if error_name == "TaskValidationError" and getattr(exc, "details", None):
        return _task_dependency_error(exc)
    if (
        error_name == "TaskTransitionError"
        and exc.reason == "not_retryable"
        and "hard prerequisite" in str(getattr(exc, "detail", ""))
    ):
        return _blocked_task_retry_error(exc)

    if error_name == "ProjectNotFoundError":
        return ServiceNotFoundError(
            "the requested project does not exist; use its canonical id or slug",
            details={
                "entity": "project",
                "ref": exc.project_id,
                "recovery": "run `astrid projects list --json`, then retry with a listed slug or id",
            },
        )
    if error_name == "ProjectSlugConflictError":
        return ServiceConflictError(
            "project slug is already in use; choose a different immutable slug",
            details={
                "entity": "project",
                "field": "slug",
                "slug": exc.slug,
                "recovery": "run `astrid projects list --json`, then retry with a new slug",
            },
        )
    if error_name == "ProjectAlreadyExistsError":
        return ServiceConflictError(
            "project already exists for this idempotency request",
            details={
                "entity": "project",
                "field": "id",
                "project_id": exc.project_id,
                "recovery": "reuse the same request/key to replay, or use a fresh key for a new project",
            },
        )
    if error_name == "ProjectAmbiguousError":
        return ServiceValidationError(
            "project display name is ambiguous; retry with one candidate id or slug",
            details={
                "entity": "project",
                "field": "ref",
                "reason": "ambiguous_display_name",
                "name": exc.name,
                "candidates": exc.candidates,
                "recovery": "retry with candidates[].slug or candidates[].id",
            },
        )
    if error_name == "ProjectValidationError" and getattr(exc, "details", None):
        return ServiceValidationError(str(exc), details=dict(exc.details))
    if error_name == "TimelineValidationError" and getattr(exc, "details", None):
        return ServiceValidationError(str(exc), details=dict(exc.details))

    if error_name == "RunRetryIneligibleError":
        return ServiceValidationError(
            "run retry found no eligible failed or expired children; inspect child task state before retrying",
            details={
                "entity": "run_retry",
                "run_id": exc.run_id,
                "reason": "no_eligible_children",
                "skipped_task_ids": list(exc.skipped_task_ids),
                "recovery": (
                    "run `astrid runs show <run> --project <project>` to inspect "
                    "child progress, then retry only after a child is failed or expired "
                    "and still within its attempt budget"
                ),
            },
        )

    for error_type, code in (
        (not_found, "not_found"),
        (conflict, "conflict"),
        (terminal_state, "terminal_state"),
        (validation, "validation_error"),
        (unavailable, "unavailable"),
        (integrity, "integrity_error"),
    ):
        if error_name in error_type:
            return _SERVICE_ERROR_CLASSES[code](_SERVICE_ERROR_MESSAGES[code])

    if error_name in stale_version:
        return _stale_version_error(
            exc,
            timeline_error=error_name == "TimelineVersionConflictError",
        )

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
