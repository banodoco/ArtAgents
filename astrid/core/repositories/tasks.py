"""Task repository: immutable task admission with canonical spec hashing (m2 plan step 6).

:class:`TaskRepository.create` is the task vertical's admission root: one
writer transaction commits the ``tasks`` read-model row, the ``core.task``
event stream, the ``core.task.created`` event (canonical SD2 envelope,
hash-chained from genesis), both heads (``projects.event_head_seq`` and
``event_streams.head_seq``), and one complete ``command_receipts`` row.

Contracts kept here (v10 section 5.1; m2 plan step 6):

- **Immutable executable spec.** The caller's *spec* (a bounded JSON
  object) and *input_manifest* (a bounded JSON array) are canonicalized at
  admission and stored verbatim; no later command may mutate them.
- **Byte-stable ``spec_hash``.** :func:`compute_spec_hash` digests one
  canonical representation (sorted keys, compact separators, bounded
  depth/size) of ``{"spec": ..., "input_manifest": ...}``, so equivalent
  spellings of the same spec hash identically and any semantic change
  changes the hash.
- **Receipt-first creation.** The receipt idempotency gate runs before any
  sequence allocation, stream creation, or projection write: an identical
  retry under the same stable ``task_id`` and idempotency key returns
  exactly the stored complete result with zero new rows, and a changed
  request under the same key raises :class:`ReceiptMismatchError` before
  any mutation.
- **Frozen state machine.** Admission creates the task in ``queued``
  status with ``winning_attempt_id``/``cancel_request_*`` null; dependency
  satisfaction (``blocked``) is plan step 6's second half (T10), and every
  later transition is receipt-protected and version-fenced.

The repository is stateless apart from the event append and receipt
services; a single instance is safe to share across command callers, and
every command must run inside the caller's
:class:`astrid.core.store.uow.UnitOfWork` so all writes share one
``BEGIN IMMEDIATE`` transaction.
"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from astrid.core.ids import generate_lowercase_ulid
from astrid.core.io.media_import import PreparedMedia, PublishedMedia
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_bytes,
    canonical_json,
    parse_json,
    request_hash,
)
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.errors import ACTOR_KINDS, RepositoryError
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.util.time import utc_now_iso

CORE_TASK_STREAM_TYPE = "core.task"
"""The kernel stream type every task aggregate owns (one per task)."""

CORE_TASK_CREATED_EVENT_KIND = "core.task.created"
"""The m2 event kind emitted by task admission."""

CORE_TASK_CREATE_COMMAND_KIND = "core.task.create"
"""The m2 command kind that task admission receipts are keyed on."""

CORE_TASK_CLAIM_COMMAND_KIND = "core.task.claim"
"""The m2 command kind that claim receipts are keyed on (plan step 7, T11)."""

CORE_TASK_START_COMMAND_KIND = "core.task.start"
"""The m2 command kind that start receipts are keyed on (plan step 7, T11)."""

CORE_TASK_CLAIMED_EVENT_KIND = "core.task.claimed"
"""The m2 event kind emitted when one task is claimed (plan step 7, T11)."""

CORE_TASK_STARTED_EVENT_KIND = "core.task.started"
"""The m2 event kind emitted when one claimed attempt starts (plan step 7, T11)."""

CORE_TASK_EXPIRE_COMMAND_KIND = "core.task.expire"
"""The m2 command kind that expiry receipts are keyed on (plan step 7, T12)."""

CORE_TASK_EXPIRED_EVENT_KIND = "core.task.expired"
"""The m2 event kind emitted when one overdue attempt expires (plan step 7, T12)."""

CORE_TASK_CANCEL_COMMAND_KIND = "core.task.cancel"
"""The m2 command kind that cancellation receipts are keyed on (plan step 8, T13)."""

CORE_TASK_CANCELLED_EVENT_KIND = "core.task.cancelled"
"""The m2 event kind emitted when a queued/blocked/running task is cancelled
(plan step 8, T13)."""

CORE_TASK_FAIL_COMMAND_KIND = "core.task.fail"
"""The m2 command kind that fenced-failure receipts are keyed on (plan step 8, T13)."""

CORE_TASK_FAILED_EVENT_KIND = "core.task.failed"
"""The m2 event kind emitted when an owned attempt fails, requeueing the
task within budget or failing it terminally when exhausted (plan step 8, T13)."""

CORE_TASK_RETRY_COMMAND_KIND = "core.task.retry"
"""The m2 command kind that retry receipts are keyed on (plan step 8, T14)."""

CORE_TASK_RETRIED_EVENT_KIND = "core.task.retried"
"""The m2 event kind emitted when eligible failed/expired work is retried,
creating a new fenced attempt (plan step 8, T14)."""

CORE_TASK_COMPLETE_COMMAND_KIND = "core.task.complete"
"""The m2 command kind that completion receipts are keyed on (plan step 10,
T18)."""

CORE_TASK_COMPLETED_EVENT_KIND = "core.task.completed"
"""The m2 event kind emitted when one owned attempt completes successfully
and the task reaches the terminal ``succeeded`` state (plan step 10, T18)."""

DEFAULT_LEASE_SECONDS = 300
"""The default claim lease duration in seconds (plan step 7, T11).

The lease fences the claimed attempt: heartbeat (plan step 7, T12) extends
only a live lease, and expiry reclaims an overdue attempt. ``claim``
derives ``lease_expires_at = now + lease_seconds``; the value is generated
state and never participates in the claim request identity.
"""

TASK_STATUSES: tuple[str, ...] = (
    "queued",
    "blocked",
    "running",
    "succeeded",
    "failed",
    "cancelled",
)
"""The frozen ``tasks.status`` DDL CHECK vocabulary (decision artifact
section 7), in DDL transcription order."""

ATTEMPT_STATUSES: tuple[str, ...] = (
    "claimed",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "expired",
)
"""The frozen ``execution_attempts.status`` DDL CHECK vocabulary."""

DEPENDENCY_KINDS: tuple[str, ...] = ("hard", "soft")
"""The frozen ``task_dependencies.kind`` DDL CHECK vocabulary (v10 decision
artifact section 7), in DDL transcription order. Hard dependencies gate
eligibility (``blocked`` until satisfied); soft dependencies never block."""

HARD_DEPENDENCY_SATISFIED_STATUS = "succeeded"
"""The terminal task status that satisfies a hard dependency.

A hard dependency is satisfied exactly when its task has reached this
terminal state; queued/blocked/running/failed/cancelled dependency tasks
leave the dependent task ``blocked`` (soft dependencies never block).
"""


class EventAppendPort(Protocol):
    def append(self, uow: UnitOfWork, **kwargs: object) -> Any:
        ...


# ---------------------------------------------------------------------------
# Lifecycle errors
# ---------------------------------------------------------------------------


class TaskRepositoryError(RepositoryError):
    """Base error for the task repository family.

    Subclasses :class:`astrid.core.repositories.errors.RepositoryError`
    (and therefore :class:`astrid.core.store.writer.WriterError`), so the
    kernel store error family catches task contract violations too.
    """


class TaskValidationError(TaskRepositoryError):
    """Raised when a task admission argument is invalid."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        # The repository keeps the exception human-readable for direct SDK
        # callers, while the service mapper can expose bounded, structured
        # guidance for malformed dependency payloads.
        self.details: dict[str, Any] = dict(details or {})
        super().__init__(message)


class TaskAlreadyExistsError(TaskRepositoryError):
    """Raised when admission targets an already-existing task id."""

    def __init__(self, *, task_id: str) -> None:
        self.task_id: str = task_id
        super().__init__(f"task already exists: {task_id!r}")


class TaskNotFoundError(TaskRepositoryError):
    """Raised when a read targets a task id with no tasks row."""

    def __init__(self, *, task_id: str) -> None:
        self.task_id: str = task_id
        super().__init__(f"unknown task: {task_id!r}")


class TaskDependencyError(TaskValidationError):
    """Raised when an admission dependency edge violates a task-graph rule.

    ``reason`` is one of ``"missing"`` (the dependency task does not exist),
    ``"cross_project"`` (the dependency belongs to another project),
    ``"self"`` (a task cannot depend on itself), ``"duplicate"`` (the same
    dependency edge declared twice), or ``"cycle"`` (the declared or
    existing graph contains a cycle through the new task).
    """

    def __init__(
        self,
        *,
        task_id: str,
        depends_on_task_id: str | None = None,
        reason: str,
    ) -> None:
        if reason not in ("missing", "cross_project", "self", "duplicate", "cycle"):
            raise ValueError(f"unknown dependency reason {reason!r}")
        self.task_id: str = task_id
        self.depends_on_task_id: str | None = depends_on_task_id
        self.reason: str = reason
        if depends_on_task_id is None:
            detail = f"task {task_id!r} dependency violation: {reason}"
        else:
            detail = (
                f"task {task_id!r} dependency on {depends_on_task_id!r} "
                f"violation: {reason}"
            )
        super().__init__(detail)


class TaskAttemptNotFoundError(TaskRepositoryError):
    """Raised when a lifecycle command targets an unknown execution attempt.

    The attempt id has no ``execution_attempts`` row (or the row belongs to
    another task), so the transition cannot be fenced. No row is mutated.
    """

    def __init__(self, *, attempt_id: str) -> None:
        self.attempt_id: str = attempt_id
        super().__init__(f"unknown execution attempt: {attempt_id!r}")


class TaskTransitionError(TaskRepositoryError):
    """Raised when a version-fenced lifecycle transition is rejected.

    ``reason`` is one of:

    - ``"task_not_running"`` — the task row is not in ``running`` status
      (it may still be queued/blocked, or already terminal), so no claimed
      attempt of it can start;
    - ``"attempt_task_mismatch"`` — the attempt row belongs to a different
      task than the one named by the command;
    - ``"attempt_not_claimed"`` — the attempt is not in ``claimed`` status
      (it already started, succeeded, failed, expired, or was cancelled);
    - ``"stale_status_version"`` — the caller's ``expected_status_version``
      does not match the attempt's current version (a stale or reordered
      command);
    - ``"lease_mismatch"`` — the caller's lease id does not match the
      attempt's lease (the caller does not own the attempt);
    - ``"attempt_not_live"`` — the attempt is not in ``claimed`` or
      ``running`` status (it already started, succeeded, failed, expired, or
      was cancelled), so a heartbeat cannot extend it (plan step 7, T12);
    - ``\"lease_expired\"`` — the attempt is live but its lease has already
      passed, so a heartbeat must not extend stale ownership (plan step 7,
      T12);
    - ``\"task_terminal\"`` — the task is already in a terminal status
      (``succeeded``, ``failed``, or ``cancelled``), so a cancel or fail
      command cannot act on it (plan step 8, T13): writer order already
      chose the terminal result and the task never resurrects.
    - ``\"not_retryable\"`` — the task is not in a retryable state: it is
      not ``queued`` with a prior ``failed`` or ``expired`` attempt, so
      ``retry`` cannot create a new fenced attempt (plan step 8, T14);
    - ``\"attempt_budget_exhausted\"`` — the prior failed/expired attempt
      already consumed the whole ``max_attempts`` budget, so ``retry`` is
      rejected (the task is terminal and never resurrects; plan step 8,
      T14).

    The attempt and task rows are left unchanged; the typed outcome lets
    callers distinguish a stale reorder from a genuine ownership error.
    """

    _REASONS = frozenset(
        {
            "task_not_running",
            "attempt_task_mismatch",
            "attempt_not_claimed",
            "stale_status_version",
            "lease_mismatch",
            "attempt_not_live",
            "lease_expired",
            "task_terminal",
            "not_retryable",
            "attempt_budget_exhausted",
        }
    )

    def __init__(
        self,
        *,
        task_id: str,
        attempt_id: str | None = None,
        reason: str,
        detail: str | None = None,
    ) -> None:
        if reason not in self._REASONS:
            raise ValueError(f"unknown transition reason {reason!r}")
        self.task_id: str = task_id
        self.attempt_id: str | None = attempt_id
        self.reason: str = reason
        self.detail: str | None = detail
        message = f"task {task_id!r} transition rejected: {reason}"
        if attempt_id is not None:
            message = f"{message} (attempt {attempt_id!r})"
        if detail is not None:
            message = f"{message}: {detail}"
        super().__init__(message)


# ---------------------------------------------------------------------------
# Frozen read models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TaskDependencyReadModel:
    """One immutable ``task_dependencies`` edge (m2 plan step 6, T10).

    ``task_id`` depends on ``depends_on_task_id`` with the frozen ``kind``
    (``hard`` or ``soft``) and a stable ``ordinal``. Edges are immutable:
    admission writes them once and no later command mutates the graph.
    """

    task_id: str
    depends_on_task_id: str
    kind: str
    ordinal: int

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id:
            raise TaskValidationError("dependency task_id must be a non-empty string")
        if not isinstance(self.depends_on_task_id, str) or not self.depends_on_task_id:
            raise TaskValidationError(
                "depends_on_task_id must be a non-empty string"
            )
        if self.kind not in DEPENDENCY_KINDS:
            raise TaskValidationError(
                f"dependency kind must be one of {DEPENDENCY_KINDS}, "
                f"got {self.kind!r}"
            )
        if isinstance(self.ordinal, bool) or not isinstance(
            self.ordinal, int
        ) or self.ordinal < 0:
            raise TaskValidationError(
                f"dependency ordinal must be a non-negative integer, "
                f"got {self.ordinal!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe mapping persisted in events and receipts."""
        return {
            "task_id": self.task_id,
            "depends_on_task_id": self.depends_on_task_id,
            "kind": self.kind,
            "ordinal": self.ordinal,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TaskDependencyReadModel:
        """Rebuild the frozen dependency read model from a stored mapping."""
        return cls(
            task_id=str(value["task_id"]),
            depends_on_task_id=str(value["depends_on_task_id"]),
            kind=str(value["kind"]),
            ordinal=int(value["ordinal"]),
        )


@dataclass(frozen=True, slots=True)
class TaskReadModel:
    """Immutable task read model (m2 plan step 6).

    A frozen projection of the ``tasks`` row plus the parsed
    ``spec_json`` and ``input_manifest_json``. Read models are never
    mutated in place; repository commands return new instances. The spec
    and input manifest are the immutable admission payload; every other
    field is transition state fenced by later commands.
    """

    id: str
    project_id: str
    capability: str
    spec: Mapping[str, Any]
    spec_hash: str
    input_manifest: Sequence[Any]
    status: str
    priority: int
    available_at: str
    max_attempts: int
    run_id: str | None
    run_ordinal: int | None
    winning_attempt_id: str | None
    cancel_request_id: str | None
    cancel_requested_at: str | None
    event_head_seq: int
    created_at: str
    updated_at: str
    finished_at: str | None
    dependencies: tuple[TaskDependencyReadModel, ...] = ()
    # These are read-time projections of the immutable dependency edges.  They
    # are deliberately excluded from equality: admission receipts contain the
    # immutable task shape, while show/list may add the latest prerequisite
    # statuses without making a formerly-created task compare unequal.
    hard_prerequisites: tuple[Mapping[str, Any], ...] = field(
        default=(), compare=False, repr=False
    )
    blocked_reason: str | None = field(default=None, compare=False)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        result = {
            "id": self.id,
            "project_id": self.project_id,
            "capability": self.capability,
            "spec": dict(self.spec),
            "spec_hash": self.spec_hash,
            "input_manifest": list(self.input_manifest),
            "status": self.status,
            "priority": self.priority,
            "available_at": self.available_at,
            "max_attempts": self.max_attempts,
            "run_id": self.run_id,
            "run_ordinal": self.run_ordinal,
            "winning_attempt_id": self.winning_attempt_id,
            "cancel_request_id": self.cancel_request_id,
            "cancel_requested_at": self.cancel_requested_at,
            "event_head_seq": self.event_head_seq,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
            "dependencies": [dep.to_dict() for dep in self.dependencies],
        }
        if self.hard_prerequisites:
            result["hard_prerequisites"] = [
                dict(prerequisite) for prerequisite in self.hard_prerequisites
            ]
        if self.blocked_reason:
            result["blocked_reason"] = self.blocked_reason
        return result

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TaskReadModel:
        """Rebuild the frozen read model from a stored result mapping."""
        return cls(
            id=str(value["id"]),
            project_id=str(value["project_id"]),
            capability=str(value["capability"]),
            spec=dict(value.get("spec") or {}),
            spec_hash=str(value["spec_hash"]),
            input_manifest=list(value.get("input_manifest") or []),
            status=str(value["status"]),
            priority=int(value["priority"]),
            available_at=str(value["available_at"]),
            max_attempts=int(value["max_attempts"]),
            run_id=value.get("run_id"),
            run_ordinal=value.get("run_ordinal"),
            winning_attempt_id=value.get("winning_attempt_id"),
            cancel_request_id=value.get("cancel_request_id"),
            cancel_requested_at=value.get("cancel_requested_at"),
            event_head_seq=int(value["event_head_seq"]),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
            finished_at=value.get("finished_at"),
            dependencies=tuple(
                TaskDependencyReadModel.from_mapping(dep)
                for dep in (value.get("dependencies") or [])
            ),
            hard_prerequisites=tuple(
                dict(prerequisite)
                for prerequisite in (value.get("hard_prerequisites") or [])
            ),
            blocked_reason=value.get("blocked_reason"),
        )


@dataclass(frozen=True, slots=True)
class TaskAttemptReadModel:
    """Immutable execution-attempt read model (m2 plan step 6).

    Frozen projection of one ``execution_attempts`` row. Admission creates
    no attempt; :meth:`TaskRepository.claim` (plan step 7, T11) creates the
    first one. The model is declared here so later lifecycle commands share
    one attempt shape and one ``to_dict``/``from_mapping`` round trip.
    """

    id: str
    task_id: str
    attempt_no: int
    executor_id: str | None
    status: str
    status_version: int
    lease_id: str | None
    lease_expires_at: str | None
    heartbeat_counter: int
    last_heartbeat_at: str | None
    progress: Mapping[str, Any]
    error: Mapping[str, Any]
    created_at: str
    updated_at: str
    finished_at: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as a receipt result."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "attempt_no": self.attempt_no,
            "executor_id": self.executor_id,
            "status": self.status,
            "status_version": self.status_version,
            "lease_id": self.lease_id,
            "lease_expires_at": self.lease_expires_at,
            "heartbeat_counter": self.heartbeat_counter,
            "last_heartbeat_at": self.last_heartbeat_at,
            "progress": dict(self.progress),
            "error": dict(self.error),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TaskAttemptReadModel:
        """Rebuild the frozen attempt read model from a stored mapping."""
        return cls(
            id=str(value["id"]),
            task_id=str(value["task_id"]),
            attempt_no=int(value["attempt_no"]),
            executor_id=value.get("executor_id"),
            status=str(value["status"]),
            status_version=int(value["status_version"]),
            lease_id=value.get("lease_id"),
            lease_expires_at=value.get("lease_expires_at"),
            heartbeat_counter=int(value.get("heartbeat_counter") or 0),
            last_heartbeat_at=value.get("last_heartbeat_at"),
            progress=dict(value.get("progress") or {}),
            error=dict(value.get("error") or {}),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
            finished_at=value.get("finished_at"),
        )


@dataclass(frozen=True, slots=True)
class TaskClaimReadModel:
    """One immutable claim result (m2 plan step 7, T11).

    The receipt result of :meth:`TaskRepository.claim`: the refreshed task
    read model (now ``running``) plus the one local claimed attempt
    (``status`` ``claimed``, ``status_version`` 1, leased). ``to_dict`` is
    the JSON-safe persisted shape and ``from_mapping`` rebuilds it for exact
    replay, so an identical retry under the same idempotency key returns
    exactly the stored claim.
    """

    task: TaskReadModel
    attempt: TaskAttemptReadModel

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the claim receipt result."""
        return {
            "task": self.task.to_dict(),
            "attempt": self.attempt.to_dict(),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TaskClaimReadModel:
        """Rebuild the frozen claim read model from a stored result mapping."""
        return cls(
            task=TaskReadModel.from_mapping(value["task"]),
            attempt=TaskAttemptReadModel.from_mapping(value["attempt"]),
        )


@dataclass(frozen=True, slots=True)
class TaskExpiryReadModel:
    """One immutable expiry result (m2 plan step 7, T12).

    The receipt result of :meth:`TaskRepository.expire_overdue`: the task
    read model after expiry (``queued`` when the attempt budget remains,
    ``failed`` — terminal — when it is exhausted), the one expired attempt
    (``status`` ``expired``, ``status_version`` advanced, ``finished_at``
    set), and the ``outcome`` (``\"requeued\"`` or ``\"failed\"``). ``to_dict``
    is the JSON-safe persisted shape and ``from_mapping`` rebuilds it for
    exact replay, so an identical retry under the same idempotency key
    returns exactly the stored expiry.
    """

    task: TaskReadModel
    attempt: TaskAttemptReadModel
    outcome: str

    def __post_init__(self) -> None:
        if self.outcome not in ("requeued", "failed"):
            raise TaskValidationError(
                f"expiry outcome must be 'requeued' or 'failed', "
                f"got {self.outcome!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the expiry receipt result."""
        return {
            "task": self.task.to_dict(),
            "attempt": self.attempt.to_dict(),
            "outcome": self.outcome,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TaskExpiryReadModel:
        """Rebuild the frozen expiry read model from a stored mapping."""
        return cls(
            task=TaskReadModel.from_mapping(value["task"]),
            attempt=TaskAttemptReadModel.from_mapping(value["attempt"]),
            outcome=str(value["outcome"]),
        )


@dataclass(frozen=True, slots=True)
class TaskCancelReadModel:
    """One immutable cancellation result (m2 plan step 8, T13).

    The receipt result of :meth:`TaskRepository.cancel`: the refreshed task
    read model (now ``cancelled`` — terminal, ``finished_at`` stamped, with
    ``cancel_request_id``/``cancel_requested_at`` recorded) and, for a
    running cancellation, the one terminated attempt (``status``
    ``cancelled``, ``status_version`` advanced, ``finished_at`` set);
    a queued/blocked cancellation has no attempt. ``to_dict`` is the
    JSON-safe persisted shape and ``from_mapping`` rebuilds it for exact
    replay, so an identical retry under the same idempotency key returns
    exactly the stored cancellation.
    """

    task: TaskReadModel
    attempt: TaskAttemptReadModel | None = None
    execution_guidance: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the cancel receipt result."""
        return {
            "task": self.task.to_dict(),
            "attempt": self.attempt.to_dict() if self.attempt is not None else None,
            "execution_guidance": self.execution_guidance,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TaskCancelReadModel:
        """Rebuild the frozen cancel read model from a stored mapping."""
        attempt = value.get("attempt")
        return cls(
            task=TaskReadModel.from_mapping(value["task"]),
            attempt=(
                TaskAttemptReadModel.from_mapping(attempt)
                if attempt is not None
                else None
            ),
            execution_guidance=value.get("execution_guidance"),
        )


@dataclass(frozen=True, slots=True)
class TaskFailReadModel:
    """One immutable fenced-failure result (m2 plan step 8, T13).

    The receipt result of :meth:`TaskRepository.fail`: the task read model
    after the owned attempt failed (``queued`` when the attempt budget
    remains, ``failed`` — terminal — when it is exhausted), the one failed
    attempt (``status`` ``failed``, ``status_version`` advanced,
    ``finished_at`` set), and the ``outcome`` (``\"requeued\"`` or
    ``\"failed\"``). ``to_dict`` is the JSON-safe persisted shape and
    ``from_mapping`` rebuilds it for exact replay, so an identical retry
    under the same idempotency key returns exactly the stored failure.
    """

    task: TaskReadModel
    attempt: TaskAttemptReadModel
    outcome: str

    def __post_init__(self) -> None:
        if self.outcome not in ("requeued", "failed"):
            raise TaskValidationError(
                f"fail outcome must be 'requeued' or 'failed', "
                f"got {self.outcome!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the fail receipt result."""
        return {
            "task": self.task.to_dict(),
            "attempt": self.attempt.to_dict(),
            "outcome": self.outcome,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TaskFailReadModel:
        """Rebuild the frozen fail read model from a stored mapping."""
        return cls(
            task=TaskReadModel.from_mapping(value["task"]),
            attempt=TaskAttemptReadModel.from_mapping(value["attempt"]),
            outcome=str(value["outcome"]),
        )


@dataclass(frozen=True, slots=True)
class TaskRetryReadModel:
    """One immutable retry result (m2 plan step 8, T14).

    The receipt result of :meth:`TaskRepository.retry`: the refreshed task
    read model (now ``running`` with a brand-new fenced attempt), the one
    new claimed attempt (``attempt_no`` one past the prior, ``status``
    ``claimed``, ``status_version`` 1, fresh lease), and the prior
    attempt's number and status (``failed`` or ``expired``) as evidence
    that the retry restarted exactly the failed/expired work. ``to_dict``
    is the JSON-safe persisted shape and ``from_mapping`` rebuilds it for
    exact replay, so an identical retry under the same idempotency key
    returns exactly the stored retry.
    """

    task: TaskReadModel
    attempt: TaskAttemptReadModel
    prior_attempt_no: int
    prior_attempt_status: str

    def __post_init__(self) -> None:
        if self.prior_attempt_status not in ("failed", "expired"):
            raise TaskValidationError(
                "retry prior_attempt_status must be 'failed' or 'expired', "
                f"got {self.prior_attempt_status!r}"
            )
        if isinstance(self.prior_attempt_no, bool) or not isinstance(
            self.prior_attempt_no, int
        ) or self.prior_attempt_no < 1:
            raise TaskValidationError(
                "retry prior_attempt_no must be a positive integer, "
                f"got {self.prior_attempt_no!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the retry receipt result."""
        return {
            "task": self.task.to_dict(),
            "attempt": self.attempt.to_dict(),
            "prior_attempt_no": self.prior_attempt_no,
            "prior_attempt_status": self.prior_attempt_status,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TaskRetryReadModel:
        """Rebuild the frozen retry read model from a stored mapping."""
        return cls(
            task=TaskReadModel.from_mapping(value["task"]),
            attempt=TaskAttemptReadModel.from_mapping(value["attempt"]),
            prior_attempt_no=int(value["prior_attempt_no"]),
            prior_attempt_status=str(value["prior_attempt_status"]),
        )


@dataclass(frozen=True, slots=True)
class TaskOutputReadModel:
    """One immutable ordered task output (m2 plan step 10, T18).

        A frozen projection of one ordered completion output: the deterministic
        ``ordinal`` within the completing task, the ``role`` (``"result"`` for
        the primary output), the materialized ``media_id`` (project-scoped
        byte-identity; ``None`` for an evidence output, which declares no
        media identity), the ``is_primary`` flag, and the caller-supplied
        output ``params`` (label, staging-relative path, digest evidence).
        ``to_dict`` is the JSON-safe persisted shape and ``from_mapping``
        rebuilds it for exact replay.
    """

    ordinal: int
    role: str
    media_id: str | None
    is_primary: bool
    params: Mapping[str, Any]
    created_at: str

    def __post_init__(self) -> None:
        if isinstance(self.ordinal, bool) or not isinstance(
            self.ordinal, int
        ) or self.ordinal < 0:
            raise TaskValidationError(
                f"output ordinal must be a non-negative integer, "
                f"got {self.ordinal!r}"
            )
        if not isinstance(self.role, str) or not self.role:
            raise TaskValidationError(
                f"output role must be a non-empty string, got {self.role!r}"
            )
        if self.media_id is not None and (
            not isinstance(self.media_id, str) or not self.media_id
        ):
            raise TaskValidationError(
                f"output media_id must be a non-empty string or None "
                f"(evidence output), got {self.media_id!r}"
            )
        if self.role != "result" and self.is_primary:
            raise TaskValidationError(
                "only a 'result' output may be primary (DDL CHECK "
                "role = 'result' OR is_primary = 0)"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "ordinal": self.ordinal,
            "role": self.role,
            "media_id": self.media_id,
            "is_primary": self.is_primary,
            "params": dict(self.params),
            "created_at": self.created_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TaskOutputReadModel:
        """Rebuild the frozen output read model from a stored mapping."""
        return cls(
            ordinal=int(value["ordinal"]),
            role=str(value["role"]),
            media_id=(
                None if value.get("media_id") is None
                else str(value["media_id"])
            ),
            is_primary=bool(value["is_primary"]),
            params=dict(value.get("params") or {}),
            created_at=str(value["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class TaskCompleteReadModel:
    """One immutable fenced-completion result (m2 plan step 10, T18).

    The receipt result of :meth:`TaskRepository.complete`: the refreshed
    task read model (terminal ``succeeded`` with ``winning_attempt_id``
    set), the one succeeded attempt (``status_version`` advanced,
    ``finished_at`` set), the ordered materialized outputs, every ordered
    event id the completion appended (media imported/related events in
    ordinal order followed by the ``core.task.completed`` event), and —
    when the task belongs to a run — the refreshed run projection mapping,
    plus the optional caller-supplied ``result`` summary when one rode with
    the completion.
    ``to_dict`` is the JSON-safe persisted shape and ``from_mapping``
    rebuilds it for exact replay.
    """

    task: TaskReadModel
    attempt: TaskAttemptReadModel
    outputs: tuple[TaskOutputReadModel, ...]
    event_ids: tuple[str, ...]
    run: Mapping[str, Any] | None
    result: Mapping[str, Any] | None = None
    #: Set when the completion created the generation (doc 27 §5 step 6).
    generation: Mapping[str, Any] | None = None
    #: New timeline stream head when completion performed the registry
    #: visibility merge (doc 27 §5 step 7); None when skipped.
    timeline_head: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "attempt": self.attempt.to_dict(),
            "outputs": [output.to_dict() for output in self.outputs],
            "event_ids": list(self.event_ids),
            "run": dict(self.run) if self.run is not None else None,
            "result": dict(self.result) if self.result is not None else None,
            "generation": dict(self.generation)
            if self.generation is not None
            else None,
            "timeline_head": self.timeline_head,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TaskCompleteReadModel:
        """Rebuild the frozen completion read model from a stored mapping."""
        return cls(
            task=TaskReadModel.from_mapping(value["task"]),
            attempt=TaskAttemptReadModel.from_mapping(value["attempt"]),
            outputs=tuple(
                TaskOutputReadModel.from_mapping(output)
                for output in (value.get("outputs") or [])
            ),
            event_ids=tuple(str(event_id) for event_id in (value.get("event_ids") or [])),
            run=dict(value["run"]) if value.get("run") is not None else None,
            result=(
                dict(value["result"]) if value.get("result") is not None
                else None
            ),
            generation=dict(value["generation"])
            if value.get("generation") is not None
            else None,
            timeline_head=(
                int(value["timeline_head"])
                if value.get("timeline_head") is not None
                else None
            ),
        )


# ---------------------------------------------------------------------------
# Canonical spec hashing
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TaskListRow:
    """One lightweight transaction-free task list row (m2 plan step 6, T10).

    The list surface returns only list-relevant projection fields — no spec or
    manifest — plus the small hard-prerequisite status projection needed to
    explain blocked work. ``list`` and ``list_eligible`` remain cheap
    read-only queries with no plan or step abstraction.
    """

    id: str
    project_id: str
    capability: str
    status: str
    priority: int
    available_at: str
    created_at: str
    hard_prerequisites: tuple[Mapping[str, Any], ...] = field(
        default=(), compare=False, repr=False
    )
    blocked_reason: str | None = field(default=None, compare=False)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict for callers and logs."""
        result = {
            "id": self.id,
            "project_id": self.project_id,
            "capability": self.capability,
            "status": self.status,
            "priority": self.priority,
            "available_at": self.available_at,
            "created_at": self.created_at,
        }
        if self.hard_prerequisites:
            result["hard_prerequisites"] = [
                dict(prerequisite) for prerequisite in self.hard_prerequisites
            ]
        if self.blocked_reason:
            result["blocked_reason"] = self.blocked_reason
        return result


def compute_spec_hash(
    spec: Mapping[str, Any], input_manifest: Sequence[Any]
) -> str:
    """Return the byte-stable SHA-256 spec hash for one task.

    The digest covers one canonical representation — ``{"spec": ...,
    "input_manifest": ...}`` with sorted keys, compact separators, and the
    canonical encoder's depth/size bounds — so equivalent spellings of the
    same executable spec hash identically and any semantic change changes
    the hash. This is the value stored on ``tasks.spec_hash`` and carried
    by the ``core.task.created`` event.
    """
    payload = {
        "spec": dict(spec),
        "input_manifest": list(input_manifest),
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise TaskValidationError(f"{name} must be a non-empty string")
    return value


def _require_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TaskValidationError(f"{name} must be an integer")
    return value


def _require_json_object(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TaskValidationError(f"{name} must be a JSON object")
    return dict(value)


def _require_json_array(name: str, value: Any) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TaskValidationError(f"{name} must be a JSON array")
    return list(value)


def _normalize_dependencies(
    task_id: str,
    dependencies: Sequence[Mapping[str, Any]] | None,
) -> tuple[TaskDependencyReadModel, ...]:
    """Validate the admission dependency shape and freeze it into read models.

    Each entry must be an object with a non-empty ``task_id`` (the task this
    admission depends on), a frozen ``kind`` (``hard``/``soft``), and a
    non-negative ``ordinal`` (defaulting to the entry index). Returns the
    immutable, insertion-ordered tuple used by validation, the receipt
    request hash, the event, and the read model, with ``task_id`` bound to
    the new task and ``depends_on_task_id`` to the declared dependency.
    """
    if dependencies is None:
        return ()
    if isinstance(dependencies, (str, bytes)) or not isinstance(
        dependencies, Sequence
    ):
        raise TaskValidationError(
            "dependencies must be a JSON array of objects like "
            '[{"task_id":"<task-id>","kind":"hard","ordinal":0}]',
            details={
                "field": "dependencies",
                "expected": "JSON array of dependency objects",
                "example": [{"task_id": "<task-id>", "kind": "hard", "ordinal": 0}],
            },
        )
    normalized: list[TaskDependencyReadModel] = []
    for index, entry in enumerate(dependencies):
        if not isinstance(entry, Mapping):
            raise TaskValidationError(
                f"dependency at ordinal {index} must be a JSON object with a "
                "non-empty task_id",
                details={
                    "field": f"dependencies[{index}]",
                    "expected": "JSON object with task_id, optional kind and ordinal",
                    "received_type": type(entry).__name__,
                    "example": {"task_id": "<task-id>", "kind": "hard", "ordinal": index},
                },
            )
        depends_on = entry.get("task_id")
        if not isinstance(depends_on, str) or not depends_on:
            raise TaskValidationError(
                f"dependency at ordinal {index} requires a non-empty task_id",
                details={
                    "field": f"dependencies[{index}].task_id",
                    "expected": "non-empty task id string",
                    "example": {"task_id": "<task-id>", "kind": "hard", "ordinal": index},
                },
            )
        kind = entry.get("kind", "hard")
        ordinal = entry.get("ordinal", index)
        if kind not in DEPENDENCY_KINDS:
            raise TaskValidationError(
                f"dependency at ordinal {index} kind must be one of "
                f"{DEPENDENCY_KINDS}, got {kind!r}",
                details={
                    "field": f"dependencies[{index}].kind",
                    "expected": list(DEPENDENCY_KINDS),
                    "received": kind,
                },
            )
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
            raise TaskValidationError(
                f"dependency at ordinal {index} ordinal must be a non-negative integer, "
                f"got {ordinal!r}",
                details={
                    "field": f"dependencies[{index}].ordinal",
                    "expected": "non-negative integer",
                    "received": ordinal,
                },
            )
        normalized.append(
            TaskDependencyReadModel(
                task_id=task_id,
                depends_on_task_id=depends_on,
                kind=kind,
                ordinal=ordinal,
            )
        )
    return tuple(normalized)


def _dependency_dicts(
    dependency_specs: Sequence[TaskDependencyReadModel],
) -> list[dict[str, Any]]:
    """JSON-safe dependency payload for requests, events, and receipts."""
    return [dep.to_dict() for dep in dependency_specs]


def _validate_dependency_graph(
    uow: UnitOfWork,
    *,
    task_id: str,
    project_id: str,
    dependency_specs: Sequence[TaskDependencyReadModel],
) -> None:
    """Enforce the acyclic same-project dependency rules (m2 plan step 6, T10).

    For every declared edge, rejects, in order, before any mutation:

    - ``self`` — a task cannot depend on itself (the DDL CHECK also guards);
    - ``duplicate`` — the same ``(task_id, depends_on_task_id)`` pair
      declared twice (the primary key also guards);
    - ``missing`` — the dependency task has no ``tasks`` row;
    - ``cross_project`` — the dependency task belongs to another project;
    - ``cycle`` — following existing dependency edges from a declared
      dependency reaches the new task (the new edges would close a cycle),
      or the reachable existing subgraph already contains a cycle (corrupt
      legacy data defense).

    All reads run inside the caller's active unit of work, so validation and
    the writes it guards observe one consistent transaction.
    """
    seen: set[str] = set()
    for dep in dependency_specs:
        if dep.depends_on_task_id == task_id:
            raise TaskDependencyError(
                task_id=task_id,
                depends_on_task_id=dep.depends_on_task_id,
                reason="self",
            )
        if dep.depends_on_task_id in seen:
            raise TaskDependencyError(
                task_id=task_id,
                depends_on_task_id=dep.depends_on_task_id,
                reason="duplicate",
            )
        seen.add(dep.depends_on_task_id)
    for dep in dependency_specs:
        dep_row = uow.query_one(
            "SELECT project_id FROM tasks WHERE id = ?",
            (dep.depends_on_task_id,),
        )
        if dep_row is None:
            raise TaskDependencyError(
                task_id=task_id,
                depends_on_task_id=dep.depends_on_task_id,
                reason="missing",
            )
        if str(dep_row["project_id"]) != project_id:
            raise TaskDependencyError(
                task_id=task_id,
                depends_on_task_id=dep.depends_on_task_id,
                reason="cross_project",
            )
        if _dependency_closure_contains_cycle(
            uow, start=dep.depends_on_task_id, new_task_id=task_id
        ):
            raise TaskDependencyError(
                task_id=task_id,
                depends_on_task_id=dep.depends_on_task_id,
                reason="cycle",
            )


def _dependency_closure_contains_cycle(
    uow: UnitOfWork, *, start: str, new_task_id: str
) -> bool:
    """Whether following existing dependency edges from *start* reaches a cycle.

    Depth-first walk over ``task_dependencies`` edges (``task_id`` depends on
    ``depends_on_task_id``). Returns ``True`` when the walk reaches
    *new_task_id* (the declared edges would close a cycle through the new
    task) or revisits a node on the current DFS path (a pre-existing cycle in
    the reachable subgraph, which must never be extended). The walk is
    bounded by the reachable subgraph size.
    """
    visited: set[str] = set()
    path: set[str] = set()

    def visit(node: str) -> bool:
        if node in path:
            return True
        if node in visited:
            return False
        visited.add(node)
        path.add(node)
        for row in uow.query(
            "SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ?",
            (node,),
        ):
            target = str(row["depends_on_task_id"])
            if target == new_task_id:
                return True
            if visit(target):
                return True
        path.remove(node)
        return False

    return visit(start)


def _initial_status_from_dependencies(
    uow: UnitOfWork,
    dependency_specs: Sequence[TaskDependencyReadModel],
) -> str:
    """Initialize ``blocked`` versus ``queued`` from hard/soft satisfaction.

    A task starts ``queued`` when every hard dependency is already satisfied
    (its task reached the frozen ``succeeded`` terminal state) — or when it
    has no hard dependencies at all. Any unsatisfied hard dependency starts
    the task ``blocked``; soft dependencies never block (v10 §2.2
    ``tasks.status``; Sprint 2 work item 1).
    """
    hard_deps = [dep for dep in dependency_specs if dep.kind == "hard"]
    if not hard_deps:
        return "queued"
    for dep in hard_deps:
        dep_row = uow.query_one(
            "SELECT status FROM tasks WHERE id = ?", (dep.depends_on_task_id,)
        )
        # Existence was validated; a vanished row would be a race only a
        # corrupt store could produce, so treat it as unsatisfied.
        if dep_row is None or str(dep_row["status"]) != HARD_DEPENDENCY_SATISFIED_STATUS:
            return "blocked"
    return "queued"


def derive_run_progress_counts(
    uow: UnitOfWork, *, run_id: str, project_id: str
) -> tuple[dict[str, int], str]:
    """Derive one run's progress from its child task rows (m2 plan step 13).

    The **single shared derivation** behind task completion's parent-run
    recompute (``_update_run_projection_on_child_terminal``) and the run
    repository's group cancel/retry and public ``derive_progress`` read. It
    is a pure read over the ``tasks`` projection: children are counted by
    ``status`` and the derived run status follows one rule everywhere —
    ``running`` until every child is terminal, then ``failed`` when any
    child failed, ``cancelled`` when any child was cancelled (and none
    failed), else ``succeeded``. No cursor and no persisted mutable progress
    aggregate ever exist; the caller may persist the returned projection
    into ``runs.result_json``/``status`` or return it transaction-free.

    Returns ``(counts, status)`` where ``counts`` maps each frozen task
    status to its child count (absent statuses are simply not present).
    """
    status_rows = uow.query(
        "SELECT status, COUNT(*) AS n FROM tasks "
        "WHERE run_id = ? AND project_id = ? GROUP BY status",
        (run_id, project_id),
    )
    counts = {str(row["status"]): int(row["n"]) for row in status_rows}
    total = sum(counts.values())
    succeeded = counts.get("succeeded", 0)
    failed = counts.get("failed", 0)
    cancelled = counts.get("cancelled", 0)
    terminal = succeeded + failed + cancelled
    if total > 0 and terminal == total:
        if failed > 0:
            status = "failed"
        elif cancelled > 0:
            status = "cancelled"
        else:
            status = "succeeded"
    else:
        status = "running"
    return counts, status


def _iso_le(left: str, right: str) -> bool:
    """Whether ISO 8601 *left* is at or before *right* (aware comparison).

    Normalizes the trailing ``Z`` (``utc_now_iso``) and ``+00:00`` (stored
    ``available_at``) spellings so eligibility compares instants, never
    strings.
    """

    def parse(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    return parse(left) <= parse(right)


def _add_seconds_iso(value: str, seconds: int) -> str:
    """Return ``value`` plus ``seconds`` as an ISO 8601 string.

    Used to derive ``lease_expires_at`` from the claim instant; the result
    is generated state (never part of a claim request identity).
    """
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed + timedelta(seconds=seconds)).isoformat()


def _iso_gt(left: str, right: str) -> bool:
    """Whether ISO 8601 *left* is strictly after *right* (aware comparison).

    The precise companion of :func:`_iso_le`: lease-expiry decisions parse
    both instants (plan step 7, T12) instead of comparing strings, so a
    sub-second precision difference between the stored ``lease_expires_at``
    and the heartbeat instant can never misclassify an expired lease as
    live.
    """

    def parse(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    return parse(left) > parse(right)


def _blocked_reason(
    *, task_status: str, hard_prerequisites: Sequence[Mapping[str, Any]]
) -> str | None:
    """Explain a blocked task from the current hard-edge read projection.

    Dependency edges are immutable, so this is intentionally derived at read
    time.  A failed or cancelled prerequisite is not merely delayed: because
    only ``succeeded`` satisfies a hard edge, the dependent can never become
    claimable under the current chain.
    """
    if task_status != "blocked" or not hard_prerequisites:
        return None
    unsatisfiable = [
        prerequisite
        for prerequisite in hard_prerequisites
        if str(prerequisite.get("status")) in {"failed", "cancelled"}
    ]
    if unsatisfiable:
        details = ", ".join(
            f"{item['depends_on_task_id']} ({item['status']})"
            for item in unsatisfiable
        )
        return (
            "unsatisfiable: hard prerequisite "
            f"{details} cannot satisfy this task; cancel this dependent and "
            "create a replacement prerequisite chain"
        )
    details = ", ".join(
        f"{item['depends_on_task_id']} ({item['status']})"
        for item in hard_prerequisites
        if str(item.get("status")) != HARD_DEPENDENCY_SATISFIED_STATUS
    )
    if not details:
        return None
    return f"blocked: waiting for hard prerequisite {details}"


def _hard_prerequisite_projection(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Normalize joined hard-prerequisite rows for public show/list reads."""
    return tuple(
        {
            "depends_on_task_id": str(row["depends_on_task_id"]),
            "kind": "hard",
            "ordinal": int(row["ordinal"]),
            "status": str(row["status"]),
        }
        for row in rows
    )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class TaskRepository:
    """Stateless task command surface over the kernel unit of work."""

    def __init__(
        self,
        events: EventAppendPort,
        receipts: ReceiptService,
    ) -> None:
        self._events = events
        self._receipts = receipts

    # -- admission --------------------------------------------------------

    def create(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        capability: str,
        spec: Mapping[str, Any],
        input_manifest: Sequence[Any],
        idempotency_key: str,
        actor_kind: str = "local",
        task_id: str | None = None,
        priority: int = 0,
        available_at: str | None = None,
        max_attempts: int = 1,
        command_kind: str = CORE_TASK_CREATE_COMMAND_KIND,
        created_at: str | None = None,
        dependencies: Sequence[Mapping[str, Any]] | None = None,
    ) -> TaskReadModel:
        """Admit one immutable task atomically and idempotently.

        Inside the caller's active unit of work this persists, in one
        ``BEGIN IMMEDIATE`` transaction: the ``tasks`` read model (status
        ``queued`` — or ``blocked`` when an unsatisfied hard dependency is
        declared), the ``core.task`` event stream, the
        ``core.task.created`` event (canonical envelope, chained from
        genesis), the declared ``task_dependencies`` edges, both heads, and
        one complete receipt.

        *project_id* is required and must reference an existing project:
        tasks are project-scoped rows, and the event append allocates its
        project sequence against that project's head.

        *dependencies* (m2 plan step 6, T10) declares the frozen
        ``task_dependencies`` edges: each entry is ``{"task_id": ...,
        "kind": "hard"|"soft", "ordinal": n}``. Every edge is validated —
        existence, same-project ownership, no self or duplicate edges, and
        no cycles — before any mutation, and the initial status is computed
        from hard/soft satisfaction: all hard dependencies already
        ``succeeded`` (or no hard dependencies) admits ``queued``; any
        unsatisfied hard dependency admits ``blocked``. Soft dependencies
        never block.

        Idempotency: the receipt gate runs before any mutation. When
        *task_id* is supplied (the stable-ID replay contract), an identical
        retry returns exactly the stored result with zero new rows, and a
        changed request under the same key raises
        :class:`ReceiptMismatchError` before any sequence allocation. When
        *task_id* is omitted a fresh lowercase Crockford ULID is generated;
        for replay, callers must supply the same stable *task_id*.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        capability = _require_non_empty_string("capability", capability)
        spec_dict = _require_json_object("spec", spec)
        manifest_list = _require_json_array("input_manifest", input_manifest)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        priority = _require_int("priority", priority)
        max_attempts = _require_int("max_attempts", max_attempts)
        if max_attempts <= 0:
            raise TaskValidationError("max_attempts must be a positive integer")
        if actor_kind not in ACTOR_KINDS:
            raise TaskValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if task_id is None:
            task_id = generate_lowercase_ulid()
        else:
            _require_non_empty_string("task_id", task_id)
        dependency_specs = _normalize_dependencies(task_id, dependencies)

        try:
            spec_json = canonical_json(spec_dict)
            input_manifest_json = canonical_json(manifest_list)
            spec_digest = compute_spec_hash(spec_dict, manifest_list)
        except CanonicalizationError as exc:
            raise TaskValidationError(
                f"cannot canonicalize task spec or input manifest: {exc}"
            ) from exc

        # Semantic request identity: stable task id, capability, immutable
        # spec, input manifest, scheduling fields, and (when declared) the
        # caller-provided dependency edges all participate; generated values
        # (including the new task's own id) are excluded.
        request = {
            "task_id": task_id,
            "capability": capability,
            "spec": spec_dict,
            "input_manifest": manifest_list,
            "priority": priority,
            "available_at": available_at,
            "max_attempts": max_attempts,
        }
        if dependency_specs:
            request["dependencies"] = [dict(entry) for entry in dependencies]
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise TaskValidationError(
                f"cannot hash task create request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch happens before any
        # sequence allocation, event append, or projection change.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return TaskReadModel.from_mapping(replayed)

        # The project must exist before any stream/task row is inserted;
        # typed rejection beats a raw FOREIGN KEY or sequence error.
        if uow.query_one("SELECT id FROM projects WHERE id = ?", (project_id,)) is None:
            raise TaskValidationError(
                f"task creation requires an existing project: {project_id!r}"
            )

        # Typed duplicate rejection before the UNIQUE constraints fire.
        existing = uow.query_one(
            "SELECT id FROM tasks WHERE id = ?", (task_id,)
        )
        if existing is not None:
            raise TaskAlreadyExistsError(task_id=task_id)

        # Dependency graph validation before any mutation, then the initial
        # blocked/queued status from hard/soft satisfaction (m2 plan step 6).
        _validate_dependency_graph(
            uow,
            task_id=task_id,
            project_id=project_id,
            dependency_specs=dependency_specs,
        )
        status = _initial_status_from_dependencies(uow, dependency_specs)

        return self._insert(
            uow,
            project_id=project_id,
            task_id=task_id,
            capability=capability,
            spec_json=spec_json,
            spec_digest=spec_digest,
            input_manifest_json=input_manifest_json,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            command_kind=command_kind,
            actor_kind=actor_kind,
            priority=priority,
            available_at=available_at,
            max_attempts=max_attempts,
            created_at=created_at,
            status=status,
            dependency_specs=dependency_specs,
        )

    # -- internal helpers -------------------------------------------------

    def _insert(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        task_id: str,
        capability: str,
        spec_json: str,
        spec_digest: str,
        input_manifest_json: str,
        idempotency_key: str,
        request_digest: str,
        command_kind: str,
        actor_kind: str,
        priority: int,
        available_at: str | None,
        max_attempts: int,
        created_at: str | None,
        status: str,
        dependency_specs: Sequence[TaskDependencyReadModel],
    ) -> TaskReadModel:
        """Persist the admission writes inside the caller's UoW."""
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stream_id = f"{task_id}:{CORE_TASK_STREAM_TYPE}"
        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TaskValidationError("created_at must be a non-empty string")
        available = available_at if available_at is not None else stamp
        if not isinstance(available, str) or not available:
            raise TaskValidationError("available_at must be a non-empty string")

        # 1. The core.task stream (head_seq starts at 0).
        uow.execute(
            "INSERT INTO event_streams "
            "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (stream_id, project_id, CORE_TASK_STREAM_TYPE, task_id, stamp),
        )
        # 2. The tasks read model (queued or blocked; no run membership yet).
        uow.execute(
            "INSERT INTO tasks "
            "(id, project_id, event_stream_id, run_id, run_ordinal, "
            "capability, spec_json, spec_hash, input_manifest_json, status, "
            "priority, available_at, max_attempts, winning_attempt_id, "
            "cancel_request_id, cancel_requested_at, created_at, updated_at, "
            "finished_at) VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, "
            "NULL, NULL, NULL, ?, ?, NULL)",
            (
                task_id,
                project_id,
                stream_id,
                capability,
                spec_json,
                spec_digest,
                input_manifest_json,
                status,
                priority,
                available,
                max_attempts,
                stamp,
                stamp,
            ),
        )
        # 3. The frozen task_dependencies edges (immutable; PK + DDL CHECK
        #    back the duplicate/self guards already validated above).
        for dep in dependency_specs:
            uow.execute(
                "INSERT INTO task_dependencies "
                "(task_id, depends_on_task_id, kind, ordinal) "
                "VALUES (?, ?, ?, ?)",
                (task_id, dep.depends_on_task_id, dep.kind, dep.ordinal),
            )
        # 4. The hash-chained core.task.created event; this advances
        #    projects.event_head_seq and event_streams.head_seq together.
        event_data: dict[str, Any] = {
            "capability": capability,
            "spec": parse_json(spec_json),
            "spec_hash": spec_digest,
            "input_manifest": parse_json(input_manifest_json),
            "priority": priority,
            "available_at": available,
            "max_attempts": max_attempts,
            "status": status,
        }
        changes: list[str] = [
            "capability",
            "spec",
            "spec_hash",
            "input_manifest",
            "priority",
            "available_at",
            "max_attempts",
            "status",
        ]
        if dependency_specs:
            event_data["dependencies"] = _dependency_dicts(dependency_specs)
            changes.append("dependencies")
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_TASK_CREATED_EVENT_KIND,
            data=event_data,
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 5. The complete receipt: transaction id, stream association,
        #    exact project sequence range, ordered event ids, and result.
        read_model = TaskReadModel(
            id=task_id,
            project_id=project_id,
            capability=capability,
            spec=parse_json(spec_json),
            spec_hash=spec_digest,
            input_manifest=parse_json(input_manifest_json),
            status=status,
            priority=priority,
            available_at=available,
            max_attempts=max_attempts,
            run_id=None,
            run_ordinal=None,
            winning_attempt_id=None,
            cancel_request_id=None,
            cancel_requested_at=None,
            event_head_seq=append.project_seq,
            created_at=stamp,
            updated_at=stamp,
            finished_at=None,
            dependencies=tuple(dependency_specs),
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=read_model.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return read_model

    # -- transaction-free reads (m2 plan step 6, T10) ----------------------

    @staticmethod
    def _row_to_read_model(
        row: Mapping[str, Any],
        dependencies: Sequence[Mapping[str, Any]],
        hard_prerequisites: Sequence[Mapping[str, Any]] = (),
    ) -> TaskReadModel:
        """Build the frozen read model from one ``tasks`` join row."""
        return TaskReadModel(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            capability=str(row["capability"]),
            spec=parse_json(str(row["spec_json"])),
            spec_hash=str(row["spec_hash"]),
            input_manifest=parse_json(str(row["input_manifest_json"])),
            status=str(row["status"]),
            priority=int(row["priority"]),
            available_at=str(row["available_at"]),
            max_attempts=int(row["max_attempts"]),
            run_id=row["run_id"],
            run_ordinal=row["run_ordinal"],
            winning_attempt_id=row["winning_attempt_id"],
            cancel_request_id=row["cancel_request_id"],
            cancel_requested_at=row["cancel_requested_at"],
            event_head_seq=int(row["event_head_seq"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            finished_at=row["finished_at"],
            dependencies=tuple(
                TaskDependencyReadModel.from_mapping(dep) for dep in dependencies
            ),
            hard_prerequisites=tuple(
                dict(prerequisite) for prerequisite in hard_prerequisites
            ),
            blocked_reason=_blocked_reason(
                task_status=str(row["status"]),
                hard_prerequisites=hard_prerequisites,
            ),
        )

    def show(self, writer: DatabaseWriter, task_id: str) -> TaskReadModel:
        """Typed show query: one task's full immutable read model.

        A transaction-free read on a separate read-only connection (no
        writer transaction is opened and no row is mutated). Returns the
        frozen :class:`TaskReadModel` including the immutable dependency
        edges; raises :class:`TaskNotFoundError` when no ``tasks`` row
        exists for *task_id* — the typed not-found contract, never an
        empty authority-dependent view.
        """
        _require_non_empty_string("task_id", task_id)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT t.*, p.event_head_seq AS event_head_seq FROM tasks t "
                "JOIN projects p ON p.id = t.project_id "
                "WHERE t.id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise TaskNotFoundError(task_id=task_id)
            dependency_rows = conn.execute(
                "SELECT task_id, depends_on_task_id, kind, ordinal "
                "FROM task_dependencies WHERE task_id = ? "
                "ORDER BY ordinal ASC, depends_on_task_id ASC",
                (task_id,),
            ).fetchall()
            prerequisite_rows = conn.execute(
                "SELECT d.depends_on_task_id, d.ordinal, dep.status "
                "FROM task_dependencies d "
                "JOIN tasks dep ON dep.id = d.depends_on_task_id "
                "WHERE d.task_id = ? AND d.kind = 'hard' "
                "ORDER BY d.ordinal ASC, d.depends_on_task_id ASC",
                (task_id,),
            ).fetchall()
        return self._row_to_read_model(
            row,
            [dict(dep) for dep in dependency_rows],
            _hard_prerequisite_projection(
                [dict(prerequisite) for prerequisite in prerequisite_rows]
            ),
        )

    def list(self, writer: DatabaseWriter, project_id: str) -> list[TaskListRow]:
        """Sorted read-only list query: every task in one project.

        A transaction-free read on a separate read-only connection, ordered
        by ``created_at`` then id (deterministic, stable). Returns one
        lightweight :class:`TaskListRow` per task; a project with no tasks
        returns ``[]``.
        """
        _require_non_empty_string("project_id", project_id)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, project_id, capability, status, priority, "
                "available_at, created_at FROM tasks "
                "WHERE project_id = ? ORDER BY created_at ASC, id ASC",
                (project_id,),
            ).fetchall()
            prerequisite_rows = conn.execute(
                "SELECT d.task_id, d.depends_on_task_id, d.ordinal, dep.status "
                "FROM task_dependencies d "
                "JOIN tasks dep ON dep.id = d.depends_on_task_id "
                "JOIN tasks task ON task.id = d.task_id "
                "WHERE task.project_id = ? AND d.kind = 'hard' "
                "ORDER BY d.task_id, d.ordinal, d.depends_on_task_id",
                (project_id,),
            ).fetchall()
        prerequisites_by_task: dict[str, list[dict[str, Any]]] = {}
        for prerequisite in prerequisite_rows:
            prerequisites_by_task.setdefault(
                str(prerequisite["task_id"]), []
            ).append(dict(prerequisite))
        return [
            TaskListRow(
                id=str(row["id"]),
                project_id=str(row["project_id"]),
                capability=str(row["capability"]),
                status=str(row["status"]),
                priority=int(row["priority"]),
                available_at=str(row["available_at"]),
                created_at=str(row["created_at"]),
                hard_prerequisites=_hard_prerequisite_projection(
                    prerequisites_by_task.get(str(row["id"]), [])
                ),
                blocked_reason=_blocked_reason(
                    task_status=str(row["status"]),
                    hard_prerequisites=prerequisites_by_task.get(
                        str(row["id"]), []
                    ),
                ),
            )
            for row in rows
        ]

    def is_eligible(
        self,
        writer: DatabaseWriter,
        task_id: str,
        *,
        now: str | None = None,
    ) -> bool:
        """Whether one task is claim-eligible right now (hard/soft gating).

        A transaction-free read. A task is eligible when it exists, is idle
        and nonterminal (``queued`` or ``blocked`` — never running or
        terminal), its ``available_at`` has passed, and every **hard**
        dependency task has reached the frozen ``succeeded`` state. A
        ``blocked`` row whose hard dependencies have all since succeeded is
        eligible even before the unblock projection updates it: eligibility
        is derived from the dependency graph, not the row label. Soft
        dependencies never gate eligibility, and an unknown task id is
        simply not eligible.
        """
        _require_non_empty_string("task_id", task_id)
        now_value = now if now is not None else utc_now_iso()
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT status, available_at FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None or str(row["status"]) not in ("queued", "blocked"):
                return False
            if not _iso_le(str(row["available_at"]), now_value):
                return False
            hard_ids = [
                str(dep["depends_on_task_id"])
                for dep in conn.execute(
                    "SELECT depends_on_task_id FROM task_dependencies "
                    "WHERE task_id = ? AND kind = 'hard'",
                    (task_id,),
                ).fetchall()
            ]
            if not hard_ids:
                return True
            placeholders = ",".join("?" * len(hard_ids))
            satisfied = conn.execute(
                "SELECT count(*) FROM tasks WHERE id IN ("
                + placeholders
                + ") AND status = 'succeeded'",
                hard_ids,
            ).fetchone()[0]
        return int(satisfied) == len(hard_ids)

    def list_eligible(
        self,
        writer: DatabaseWriter,
        project_id: str,
        *,
        now: str | None = None,
    ) -> list[TaskListRow]:
        """Read-only claim queue: every eligible task in one project.

        A transaction-free read returning the idle nonterminal tasks
        (``queued`` or ``blocked``) whose ``available_at`` has passed and
        whose every hard dependency is satisfied, in claim order (priority
        descending, then availability, then id — the ``tasks_claim_order``
        index semantics). A ``blocked`` row whose hard dependencies have all
        since succeeded joins the queue even before the unblock projection
        updates it. Soft dependencies never gate. No writer transaction is
        opened and no row is mutated.
        """
        _require_non_empty_string("project_id", project_id)
        now_value = now if now is not None else utc_now_iso()
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            candidates = conn.execute(
                "SELECT id, project_id, capability, status, priority, "
                "available_at, created_at FROM tasks "
                "WHERE project_id = ? AND status IN ('queued', 'blocked') "
                "ORDER BY priority DESC, available_at ASC, id ASC",
                (project_id,),
            ).fetchall()
            if not candidates:
                return []
            candidate_ids = [str(row["id"]) for row in candidates]
            placeholders = ",".join("?" * len(candidate_ids))
            # Every candidate with at least one hard dependency that has NOT
            # succeeded is not yet claimable and must be excluded.
            blocked_ids = {
                str(row["task_id"])
                for row in conn.execute(
                    "SELECT DISTINCT d.task_id FROM task_dependencies d "
                    "JOIN tasks dep ON dep.id = d.depends_on_task_id "
                    "WHERE d.kind = 'hard' AND dep.status <> 'succeeded' "
                    "AND d.task_id IN (" + placeholders + ")",
                    candidate_ids,
                ).fetchall()
            }
        rows: list[TaskListRow] = []
        for row in candidates:
            task_id = str(row["id"])
            if task_id in blocked_ids:
                continue
            if not _iso_le(str(row["available_at"]), now_value):
                continue
            rows.append(
                TaskListRow(
                    id=task_id,
                    project_id=str(row["project_id"]),
                    capability=str(row["capability"]),
                    status=str(row["status"]),
                    priority=int(row["priority"]),
                    available_at=str(row["available_at"]),
                    created_at=str(row["created_at"]),
                )
            )
        return rows

    # -- claim and start (m2 plan step 7, T11) ----------------------------

    def claim(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        idempotency_key: str,
        actor_kind: str = "local",
        executor_id: str | None = None,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        now: str | None = None,
        command_kind: str = CORE_TASK_CLAIM_COMMAND_KIND,
    ) -> TaskClaimReadModel | None:
        """Claim exactly one eligible task in FIFO order, atomically.

        Inside the caller's active unit of work this scans the project's
        idle nonterminal tasks (``queued`` or ``blocked`` — the same
        eligibility predicate as :meth:`list_eligible`: ``available_at``
        passed and every hard dependency satisfied), picks the first in
        claim order (priority descending, then availability, then id), and
        commits, in one ``BEGIN IMMEDIATE`` transaction: one local
        ``execution_attempts`` row (``status`` ``claimed``,
        ``status_version`` 1, a fresh ``lease_id`` and
        ``lease_expires_at = now + lease_seconds``), the task's
        ``queued``/``blocked`` → ``running`` transition, the hash-chained
        ``core.task.claimed`` event on the task stream, both heads, and one
        complete receipt whose result is the refreshed task read model plus
        the claimed attempt.

        Returns ``None`` — with no receipt and no mutation — when no task
        is eligible right now; the caller treats that as "no work". The
        writer's FIFO serialization guarantees a second claim (even under a
        different idempotency key) sees the claimed task as ``running`` and
        can never claim the same task twice.

        Idempotency: the receipt gate runs before the scan. An identical
        retry under the same key returns exactly the stored claim result
        with zero new rows; a changed request (e.g. a different
        ``executor_id``) under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if executor_id is not None:
            _require_non_empty_string("executor_id", executor_id)
        if isinstance(lease_seconds, bool) or not isinstance(
            lease_seconds, int
        ) or lease_seconds <= 0:
            raise TaskValidationError(
                "lease_seconds must be a positive integer, "
                f"got {lease_seconds!r}"
            )
        if actor_kind not in ACTOR_KINDS:
            raise TaskValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )

        # Semantic request identity: only caller-supplied facts participate;
        # the chosen task, attempt/lease ids, and timestamps are generated.
        request = {
            "executor_id": executor_id,
            "lease_seconds": lease_seconds,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise TaskValidationError(
                f"cannot hash claim request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before the scan or any
        # sequence allocation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return TaskClaimReadModel.from_mapping(replayed)

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TaskValidationError("now must be a non-empty string")

        # FIFO eligibility scan inside the transaction: the first idle
        # nonterminal task whose availability passed and whose every hard
        # dependency has succeeded, in claim order.
        candidates = uow.query(
            "SELECT id, project_id, capability, status, priority, "
            "available_at, created_at FROM tasks "
            "WHERE project_id = ? AND status IN ('queued', 'blocked') "
            "ORDER BY priority DESC, available_at ASC, id ASC",
            (project_id,),
        )
        task_row = None
        if candidates:
            candidate_ids = [str(row["id"]) for row in candidates]
            placeholders = ",".join("?" * len(candidate_ids))
            blocked_ids = {
                str(row["task_id"])
                for row in uow.query(
                    "SELECT DISTINCT d.task_id FROM task_dependencies d "
                    "JOIN tasks dep ON dep.id = d.depends_on_task_id "
                    "WHERE d.kind = 'hard' AND dep.status <> 'succeeded' "
                    "AND d.task_id IN (" + placeholders + ")",
                    candidate_ids,
                )
            }
            for row in candidates:
                task_id = str(row["id"])
                if task_id in blocked_ids:
                    continue
                if not _iso_le(str(row["available_at"]), stamp):
                    continue
                task_row = row
                break
        if task_row is None:
            return None

        task_id = str(task_row["id"])
        attempt_id = generate_lowercase_ulid()
        lease_id = generate_lowercase_ulid()
        lease_expires_at = _add_seconds_iso(stamp, lease_seconds)
        # The next attempt number: the first claim of a fresh task is 1;
        # later retry attempts (plan step 8) continue the sequence.
        attempt_no_row = uow.query_one(
            "SELECT COALESCE(MAX(attempt_no), 0) + 1 AS next_no "
            "FROM execution_attempts WHERE task_id = ?",
            (task_id,),
        )
        attempt_no = int(attempt_no_row["next_no"])
        stream_id = f"{task_id}:{CORE_TASK_STREAM_TYPE}"
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex

        # 1. One local claimed attempt: status_version 1, leased, no event
        #    history of its own yet.
        uow.execute(
            "INSERT INTO execution_attempts "
            "(id, task_id, attempt_no, executor_id, status, status_version, "
            "lease_id, lease_expires_at, heartbeat_counter, last_heartbeat_at, "
            "progress_json, error_json, created_at, updated_at, finished_at) "
            "VALUES (?, ?, ?, ?, 'claimed', 1, ?, ?, 0, NULL, '{}', '{}', "
            "?, ?, NULL)",
            (
                attempt_id,
                task_id,
                attempt_no,
                executor_id,
                lease_id,
                lease_expires_at,
                stamp,
                stamp,
            ),
        )
        # 2. The task leaves the claim queue (queued/blocked -> running);
        #    it can never be claimed again while this attempt lives.
        uow.execute(
            "UPDATE tasks SET status = 'running', updated_at = ? WHERE id = ?",
            (stamp, task_id),
        )
        # 3. The hash-chained core.task.claimed event on the task stream.
        event_data: dict[str, Any] = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "attempt_no": attempt_no,
            "status_version": 1,
            "executor_id": executor_id,
            "lease_id": lease_id,
            "lease_expires_at": lease_expires_at,
        }
        changes: list[str] = [
            "status",
            "attempt_id",
            "attempt_no",
            "status_version",
            "executor_id",
            "lease_id",
            "lease_expires_at",
        ]
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_TASK_CLAIMED_EVENT_KIND,
            data=event_data,
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 4. The complete receipt: the refreshed task model plus the one
        #    claimed attempt.
        task_model = self._task_model(uow, task_id=task_id, project_id=project_id)
        attempt_model = TaskAttemptReadModel(
            id=attempt_id,
            task_id=task_id,
            attempt_no=attempt_no,
            executor_id=executor_id,
            status="claimed",
            status_version=1,
            lease_id=lease_id,
            lease_expires_at=lease_expires_at,
            heartbeat_counter=0,
            last_heartbeat_at=None,
            progress={},
            error={},
            created_at=stamp,
            updated_at=stamp,
            finished_at=None,
        )
        result = TaskClaimReadModel(task=task_model, attempt=attempt_model)
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=result.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return result

    def start(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        task_id: str,
        attempt_id: str,
        expected_status_version: int,
        idempotency_key: str,
        actor_kind: str = "local",
        lease_id: str | None = None,
        now: str | None = None,
        command_kind: str = CORE_TASK_START_COMMAND_KIND,
    ) -> TaskAttemptReadModel:
        """Start one claimed attempt through a receipt-protected event.

        Inside the caller's active unit of work this advances exactly the
        matching attempt: the task must be ``running`` and belong to
        *project_id*, and the attempt must belong to that task, be in
        ``claimed`` status, carry the caller's ``expected_status_version``
        (and, when supplied, the same ``lease_id``). Every fence is checked
        **before** any mutation; a stale or foreign command raises the typed
        :class:`TaskTransitionError` / :class:`TaskAttemptNotFoundError`
        and changes zero rows.

        On success the command commits, in one ``BEGIN IMMEDIATE``
        transaction: the hash-chained ``core.task.started`` event on the
        task stream (next project sequence — project ordering is preserved),
        the attempt's ``claimed`` → ``running`` transition with
        ``status_version`` advanced by one, both heads, and one complete
        receipt whose result is the running attempt read model.

        Idempotency: the receipt gate runs before any fence. An identical
        retry under the same key returns exactly the stored running attempt
        with zero new rows; a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        task_id = _require_non_empty_string("task_id", task_id)
        attempt_id = _require_non_empty_string("attempt_id", attempt_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if isinstance(expected_status_version, bool) or not isinstance(
            expected_status_version, int
        ) or expected_status_version <= 0:
            raise TaskValidationError(
                "expected_status_version must be a positive integer, "
                f"got {expected_status_version!r}"
            )
        if lease_id is not None:
            _require_non_empty_string("lease_id", lease_id)
        if actor_kind not in ACTOR_KINDS:
            raise TaskValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )

        # Semantic request identity: the fenced transition the caller wants.
        request = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "expected_status_version": expected_status_version,
            "lease_id": lease_id,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise TaskValidationError(
                f"cannot hash start request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before any fence read
        # or sequence allocation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return TaskAttemptReadModel.from_mapping(replayed)

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TaskValidationError("now must be a non-empty string")

        # Fences, all before any mutation (typed stale outcomes).
        task_row = uow.query_one(
            "SELECT * FROM tasks WHERE id = ? AND project_id = ?",
            (task_id, project_id),
        )
        if task_row is None:
            raise TaskNotFoundError(task_id=task_id)
        if str(task_row["status"]) != "running":
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="task_not_running",
                detail=(
                    f"task status is {task_row['status']!r}, "
                    "expected 'running'"
                ),
            )
        attempt_row = uow.query_one(
            "SELECT * FROM execution_attempts WHERE id = ?", (attempt_id,)
        )
        if attempt_row is None:
            raise TaskAttemptNotFoundError(attempt_id=attempt_id)
        if str(attempt_row["task_id"]) != task_id:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="attempt_task_mismatch",
            )
        if str(attempt_row["status"]) != "claimed":
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="attempt_not_claimed",
                detail=(
                    f"attempt status is {attempt_row['status']!r}, "
                    "expected 'claimed'"
                ),
            )
        if int(attempt_row["status_version"]) != expected_status_version:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="stale_status_version",
                detail=(
                    f"attempt status_version is "
                    f"{attempt_row['status_version']}, expected "
                    f"{expected_status_version}"
                ),
            )
        if (
            lease_id is not None
            and str(attempt_row["lease_id"]) != lease_id
        ):
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="lease_mismatch",
            )

        next_version = expected_status_version + 1
        stream_id = f"{task_id}:{CORE_TASK_STREAM_TYPE}"
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        event_data: dict[str, Any] = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "attempt_no": int(attempt_row["attempt_no"]),
            "status_version": next_version,
            "lease_id": attempt_row["lease_id"],
            "lease_expires_at": attempt_row["lease_expires_at"],
        }
        changes: list[str] = [
            "attempt_status",
            "status_version",
            "lease_id",
            "lease_expires_at",
        ]
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_TASK_STARTED_EVENT_KIND,
            data=event_data,
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # The attempt advances: claimed -> running, status_version +1.
        uow.execute(
            "UPDATE execution_attempts SET status = 'running', "
            "status_version = ?, updated_at = ? WHERE id = ?",
            (next_version, stamp, attempt_id),
        )
        attempt_model = TaskAttemptReadModel(
            id=attempt_id,
            task_id=task_id,
            attempt_no=int(attempt_row["attempt_no"]),
            executor_id=attempt_row["executor_id"],
            status="running",
            status_version=next_version,
            lease_id=attempt_row["lease_id"],
            lease_expires_at=attempt_row["lease_expires_at"],
            heartbeat_counter=int(attempt_row["heartbeat_counter"]),
            last_heartbeat_at=attempt_row["last_heartbeat_at"],
            progress=parse_json(str(attempt_row["progress_json"])),
            error=parse_json(str(attempt_row["error_json"])),
            created_at=str(attempt_row["created_at"]),
            updated_at=stamp,
            finished_at=attempt_row["finished_at"],
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=attempt_model.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return attempt_model

    # -- heartbeat (sole non-event update, m2 plan step 7, T12) ------------

    def heartbeat(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        task_id: str,
        attempt_id: str,
        lease_id: str,
        expected_status_version: int,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        now: str | None = None,
    ) -> TaskAttemptReadModel:
        """Extend one live attempt's lease without an event or a receipt.

        Heartbeat is the deliberate non-event exception to the
        event/receipt rule (v10 §5.1): a live attempt (``claimed`` or
        ``running``) owned by *lease_id* at *expected_status_version* whose
        lease has not yet expired is refreshed by one exact-predicate UPDATE
        inside the caller's active unit of work — ``heartbeat_counter`` +1,
        ``last_heartbeat_at`` = now, ``lease_expires_at`` = now +
        ``lease_seconds``, and ``status_version`` +1. No event is appended
        and no receipt is recorded; the counter/version increments are the
        audit trail.

        Every fence is exact and evaluated before the UPDATE inside the one
        ``BEGIN IMMEDIATE`` transaction, so the command can never extend a
        stale or foreign attempt and can never extend an expired lease: the
        typed outcomes are ``task_not_running``, ``attempt_task_mismatch``,
        ``attempt_not_live``, ``stale_status_version``, ``lease_mismatch``,
        and ``lease_expired`` — all with zero rows changed.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        task_id = _require_non_empty_string("task_id", task_id)
        attempt_id = _require_non_empty_string("attempt_id", attempt_id)
        lease_id = _require_non_empty_string("lease_id", lease_id)
        if isinstance(expected_status_version, bool) or not isinstance(
            expected_status_version, int
        ) or expected_status_version <= 0:
            raise TaskValidationError(
                "expected_status_version must be a positive integer, "
                f"got {expected_status_version!r}"
            )
        if isinstance(lease_seconds, bool) or not isinstance(
            lease_seconds, int
        ) or lease_seconds <= 0:
            raise TaskValidationError(
                "lease_seconds must be a positive integer, "
                f"got {lease_seconds!r}"
            )
        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TaskValidationError("now must be a non-empty string")

        # Fences, all before the UPDATE (exact predicates; typed outcomes).
        task_row = uow.query_one(
            "SELECT status FROM tasks WHERE id = ? AND project_id = ?",
            (task_id, project_id),
        )
        if task_row is None:
            raise TaskNotFoundError(task_id=task_id)
        if str(task_row["status"]) != "running":
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="task_not_running",
                detail=(
                    f"task status is {task_row['status']!r}, expected 'running'"
                ),
            )
        attempt_row = uow.query_one(
            "SELECT * FROM execution_attempts WHERE id = ?", (attempt_id,)
        )
        if attempt_row is None:
            raise TaskAttemptNotFoundError(attempt_id=attempt_id)
        if str(attempt_row["task_id"]) != task_id:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="attempt_task_mismatch",
            )
        if str(attempt_row["status"]) not in ("claimed", "running"):
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="attempt_not_live",
                detail=(
                    f"attempt status is {attempt_row['status']!r}, "
                    "expected 'claimed' or 'running'"
                ),
            )
        if int(attempt_row["status_version"]) != expected_status_version:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="stale_status_version",
                detail=(
                    f"attempt status_version is "
                    f"{attempt_row['status_version']}, expected "
                    f"{expected_status_version}"
                ),
            )
        if str(attempt_row["lease_id"]) != lease_id:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="lease_mismatch",
            )
        if not _iso_gt(str(attempt_row["lease_expires_at"]), stamp):
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="lease_expired",
                detail=(
                    f"attempt lease expired at "
                    f"{attempt_row['lease_expires_at']}, before {stamp}"
                ),
            )

        # The one non-event write: exact predicates so a stale reorder can
        # never extend ownership, plus the counter/version increments.
        new_expiry = _add_seconds_iso(stamp, lease_seconds)
        cursor = uow.execute(
            "UPDATE execution_attempts SET "
            "heartbeat_counter = heartbeat_counter + 1, "
            "last_heartbeat_at = ?, lease_expires_at = ?, "
            "status_version = status_version + 1, updated_at = ? "
            "WHERE id = ? AND task_id = ? AND status IN ('claimed','running') "
            "AND lease_id = ? AND status_version = ?",
            (
                stamp,
                new_expiry,
                stamp,
                attempt_id,
                task_id,
                lease_id,
                expected_status_version,
            ),
        )
        if cursor.rowcount != 1:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="stale_status_version",
                detail="attempt changed between the fence check and the update",
            )
        fresh = uow.query_one(
            "SELECT * FROM execution_attempts WHERE id = ?", (attempt_id,)
        )
        if fresh is None:  # pragma: no cover - deleted rows cannot reappear
            raise TaskAttemptNotFoundError(attempt_id=attempt_id)
        return self._attempt_read_model(fresh)

    # -- orphan expiry (receipt-protected, m2 plan step 7, T12) ------------

    def expire_overdue(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        idempotency_key: str,
        actor_kind: str = "local",
        now: str | None = None,
        command_kind: str = CORE_TASK_EXPIRE_COMMAND_KIND,
    ) -> TaskExpiryReadModel | None:
        """Expire the first overdue attempt through a receipt-protected event.

        Inside the caller's active unit of work this scans the project's
        live attempts (``claimed`` or ``running``) whose lease has already
        passed (``lease_expires_at <= now``), picks the first in
        deterministic expiry order (lease expiry ascending, then task id,
        then attempt number — the ``attempts_lease_expiry`` order), and
        commits, in one ``BEGIN IMMEDIATE`` transaction: the attempt's
        ``expired`` transition (``status_version`` +1, ``finished_at`` set),
        the task's ``running`` exit, the hash-chained ``core.task.expired``
        event on the task stream, both heads, and one complete receipt.

        The task exit is budget-driven (SD1): when the attempt budget
        remains (``attempt_no < max_attempts``) the task is requeued
        (``queued`` — a later claim creates a fresh fenced attempt), and
        when it is exhausted the task fails terminally (``failed`` with
        ``finished_at`` set) and can never resurrect. Expiry never extends a
        lease and never races with heartbeat: both run through the writer
        FIFO, heartbeat's exact predicates reject an already-expired lease,
        and this command's attempt UPDATE is fenced on the exact
        ``status_version``.

        Returns ``None`` — with no receipt and no mutation — when nothing is
        overdue right now. Idempotency: the receipt gate runs first; an
        identical retry under the same key returns exactly the stored expiry
        result with zero new rows, and a changed request under the same key
        raises :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise TaskValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )

        # Semantic request identity: the sweep target is generated state, so
        # the request carries no caller-supplied facts beyond the command.
        request: dict[str, Any] = {}
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise TaskValidationError(
                f"cannot hash expire request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before the scan or any
        # sequence allocation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return TaskExpiryReadModel.from_mapping(replayed)

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TaskValidationError("now must be a non-empty string")

        # The overdue scan in deterministic expiry order. The instant
        # comparison is precise (parsed, not string-compared), so a
        # sub-second precision difference cannot misclassify an expired
        # lease as live.
        candidates = uow.query(
            "SELECT a.id AS attempt_id, a.task_id, a.attempt_no, a.status, "
            "a.status_version, a.lease_id, a.lease_expires_at, "
            "t.status AS task_status, t.max_attempts, t.run_id AS run_id "
            "FROM execution_attempts a JOIN tasks t ON t.id = a.task_id "
            "WHERE t.project_id = ? AND a.status IN ('claimed','running') "
            "ORDER BY a.lease_expires_at ASC, a.task_id ASC, a.attempt_no ASC",
            (project_id,),
        )
        overdue = [
            row for row in candidates if _iso_le(str(row["lease_expires_at"]), stamp)
        ]
        if not overdue:
            return None
        row = overdue[0]

        task_id = str(row["task_id"])
        attempt_id = str(row["attempt_id"])
        attempt_no = int(row["attempt_no"])
        status_version = int(row["status_version"])
        lease_id = row["lease_id"]
        lease_expires_at = row["lease_expires_at"]
        max_attempts = int(row["max_attempts"])
        if str(row["task_status"]) != "running":
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="task_not_running",
                detail=(
                    f"task status is {row['task_status']!r}, expected 'running'"
                ),
            )

        outcome = "requeued" if attempt_no < max_attempts else "failed"
        next_version = status_version + 1
        new_task_status = "queued" if outcome == "requeued" else "failed"
        stream_id = f"{task_id}:{CORE_TASK_STREAM_TYPE}"
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex

        # 1. The attempt expires, fenced on its exact version and live
        #    status so a concurrent transition can never be overwritten.
        cursor = uow.execute(
            "UPDATE execution_attempts SET status = 'expired', "
            "status_version = ?, updated_at = ?, finished_at = ? "
            "WHERE id = ? AND task_id = ? AND status IN ('claimed','running') "
            "AND status_version = ?",
            (next_version, stamp, stamp, attempt_id, task_id, status_version),
        )
        if cursor.rowcount != 1:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="stale_status_version",
                detail="attempt changed between the scan and the update",
            )
        # 2. The task leaves running: requeued (claimable again) or failed
        #    terminally (finished_at stamped; never resurrects).
        task_cursor = uow.execute(
            "UPDATE tasks SET status = ?, updated_at = ?, finished_at = ? "
            "WHERE id = ? AND status = 'running'",
            (
                new_task_status,
                stamp,
                stamp if outcome == "failed" else None,
                task_id,
            ),
        )
        if task_cursor.rowcount != 1:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="task_not_running",
                detail="task changed between the scan and the update",
            )
        if outcome == "failed" and row["run_id"] is not None:
            self._update_run_projection_on_child_terminal(
                uow,
                run_id=str(row["run_id"]),
                project_id=project_id,
                stamp=stamp,
            )
        # 3. The hash-chained core.task.expired event on the task stream.
        event_data: dict[str, Any] = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "attempt_no": attempt_no,
            "status_version": next_version,
            "outcome": outcome,
            "lease_id": lease_id,
            "lease_expires_at": lease_expires_at,
            "reason": "lease_expired",
        }
        changes: list[str] = [
            "attempt_status",
            "task_status",
            "status_version",
            "outcome",
            "finished_at",
        ]
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_TASK_EXPIRED_EVENT_KIND,
            data=event_data,
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 4. The complete receipt: refreshed task plus the expired attempt.
        task_model = self._task_model(uow, task_id=task_id, project_id=project_id)
        fresh = uow.query_one(
            "SELECT * FROM execution_attempts WHERE id = ?", (attempt_id,)
        )
        if fresh is None:  # pragma: no cover - deleted rows cannot reappear
            raise TaskAttemptNotFoundError(attempt_id=attempt_id)
        result = TaskExpiryReadModel(
            task=task_model,
            attempt=self._attempt_read_model(fresh),
            outcome=outcome,
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=result.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return result

    # -- cancellation (receipt-protected, m2 plan step 8, T13) -------------

    def cancel(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        task_id: str,
        idempotency_key: str,
        actor_kind: str = "local",
        cancel_request_id: str | None = None,
        attempt_id: str | None = None,
        lease_id: str | None = None,
        expected_status_version: int | None = None,
        now: str | None = None,
        command_kind: str = CORE_TASK_CANCEL_COMMAND_KIND,
    ) -> TaskCancelReadModel:
        """Cancel one nonterminal task through a receipt-protected event.

        Inside the caller's active unit of work this drives the task to the
        terminal ``cancelled`` state exactly once (SD1: a cancelled task
        never resurrects) and commits, in one ``BEGIN IMMEDIATE``
        transaction: the hash-chained ``core.task.cancelled`` event on the
        task stream, both heads, and one complete receipt.

        - **Queued/blocked cancellation.** The task has no live attempt:
          the task row moves directly to ``cancelled`` with
          ``finished_at`` stamped and the caller's (or a fresh generated)
          ``cancel_request_id``/``cancel_requested_at`` recorded. No
          attempt is touched.
        - **Running cancellation.** An operator may cancel a running task
          without executor-private fence facts. The single writer selects
          the terminal winner; it finds the live attempt, terminates it in
          the same command (``status`` ``cancelled``, ``status_version`` +1,
          ``finished_at`` stamped), and leaves the task ``cancelled`` with
          ``winning_attempt_id`` null. An executor may instead provide the
          complete *attempt_id*, *lease_id*, and *expected_status_version*
          fence; every fence is checked **before** mutation. Partial fences
          remain a validation error. A handler already outside SQLite may
          finish, but its later fenced completion cannot publish outputs.

        Writer order selects exactly one terminal result: both this command
        and completion run through the single writer FIFO, so whichever
        commits first wins and the second sees the task already terminal
        and raises the typed ``task_terminal`` outcome with zero rows
        changed — a cancelled task can never be completed, and a completed
        task can never be cancelled.

        Idempotency: the receipt gate runs first. An identical retry under
        the same key returns exactly the stored cancellation with zero new
        rows; a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        task_id = _require_non_empty_string("task_id", task_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise TaskValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if cancel_request_id is not None:
            _require_non_empty_string("cancel_request_id", cancel_request_id)
        if attempt_id is not None:
            _require_non_empty_string("attempt_id", attempt_id)
        if lease_id is not None:
            _require_non_empty_string("lease_id", lease_id)
        if expected_status_version is not None and (
            isinstance(expected_status_version, bool)
            or not isinstance(expected_status_version, int)
            or expected_status_version <= 0
        ):
            raise TaskValidationError(
                "expected_status_version must be a positive integer, "
                f"got {expected_status_version!r}"
            )

        # Semantic request identity: the fenced transition the caller wants
        # plus any caller-supplied cancel request id; generated state (the
        # effective cancel request id when none is supplied, timestamps)
        # never participates.
        request: dict[str, Any] = {"task_id": task_id}
        if cancel_request_id is not None:
            request["cancel_request_id"] = cancel_request_id
        if attempt_id is not None:
            request["attempt_id"] = attempt_id
        if lease_id is not None:
            request["lease_id"] = lease_id
        if expected_status_version is not None:
            request["expected_status_version"] = expected_status_version
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise TaskValidationError(
                f"cannot hash cancel request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before any fence read
        # or sequence allocation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return TaskCancelReadModel.from_mapping(replayed)

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TaskValidationError("now must be a non-empty string")

        # The task must exist, belong to this project, and be nonterminal.
        task_row = uow.query_one(
            "SELECT * FROM tasks WHERE id = ? AND project_id = ?",
            (task_id, project_id),
        )
        if task_row is None:
            raise TaskNotFoundError(task_id=task_id)
        prior_status = str(task_row["status"])
        if prior_status not in ("queued", "blocked", "running"):
            raise TaskTransitionError(
                task_id=task_id,
                reason="task_terminal",
                detail=(
                    f"task status is {prior_status!r}; writer order already "
                    "chose the terminal result"
                ),
            )

        effective_cancel_request_id = (
            cancel_request_id
            if cancel_request_id is not None
            else generate_lowercase_ulid()
        )
        stream_id = f"{task_id}:{CORE_TASK_STREAM_TYPE}"
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        attempt_model: TaskAttemptReadModel | None = None
        attempt_id_effective: str | None = None
        attempt_no: int | None = None
        next_version: int | None = None
        attempt_lease_id: Any = None
        attempt_lease_expires_at: Any = None

        if prior_status == "running":
            # A worker may provide its exact fence, but an operator has no
            # reason to know those internal values.  With no fence, the
            # single writer still gives cancellation a safe terminal winner:
            # a worker that is already outside SQLite may finish its handler,
            # but its later fenced completion cannot publish media.  Partial
            # fences remain a caller error rather than silently weakening the
            # race protection.
            cooperative = (
                attempt_id is None
                and lease_id is None
                and expected_status_version is None
            )
            if not cooperative and (
                attempt_id is None
                or lease_id is None
                or expected_status_version is None
            ):
                raise TaskValidationError(
                    "cancelling a running task takes either no attempt fence "
                    "(operator cooperative cancel) or all of attempt_id, "
                    "lease_id, and expected_status_version"
                )
            attempt_row = uow.query_one(
                "SELECT * FROM execution_attempts WHERE id = ?"
                if attempt_id is not None
                else "SELECT * FROM execution_attempts WHERE task_id = ? "
                "AND status IN ('claimed','running') ORDER BY attempt_no DESC LIMIT 1",
                (attempt_id,) if attempt_id is not None else (task_id,),
            )
            if attempt_row is None:
                raise TaskAttemptNotFoundError(attempt_id=attempt_id or task_id)
            if str(attempt_row["task_id"]) != task_id:
                raise TaskTransitionError(
                    task_id=task_id,
                    attempt_id=attempt_id_effective,
                    reason="attempt_task_mismatch",
                )
            if str(attempt_row["status"]) not in ("claimed", "running"):
                raise TaskTransitionError(
                    task_id=task_id,
                    attempt_id=attempt_id_effective,
                    reason="attempt_not_live",
                    detail=(
                        f"attempt status is {attempt_row['status']!r}, "
                        "expected 'claimed' or 'running'"
                    ),
                )
            if not cooperative and str(attempt_row["lease_id"]) != lease_id:
                raise TaskTransitionError(
                    task_id=task_id,
                    attempt_id=attempt_id_effective,
                    reason="lease_mismatch",
                )
            if not cooperative and int(attempt_row["status_version"]) != expected_status_version:
                raise TaskTransitionError(
                    task_id=task_id,
                    attempt_id=str(attempt_row["id"]),
                    reason="stale_status_version",
                    detail=(
                        f"attempt status_version is "
                        f"{attempt_row['status_version']}, expected "
                        f"{expected_status_version}"
                    ),
                )
            expected_status_version = int(attempt_row["status_version"])
            next_version = expected_status_version + 1
            attempt_id_effective = str(attempt_row["id"])
            attempt_no = int(attempt_row["attempt_no"])
            attempt_lease_id = attempt_row["lease_id"]
            attempt_lease_expires_at = attempt_row["lease_expires_at"]
            # 1. The owned attempt terminates in this same command.
            cursor = uow.execute(
                "UPDATE execution_attempts SET status = 'cancelled', "
                "status_version = ?, updated_at = ?, finished_at = ? "
                "WHERE id = ? AND task_id = ? AND status IN "
                "('claimed','running') AND status_version = ?",
                (
                    next_version,
                    stamp,
                    stamp,
                    attempt_id_effective,
                    task_id,
                    expected_status_version,
                ),
            )
            if cursor.rowcount != 1:
                raise TaskTransitionError(
                    task_id=task_id,
                    attempt_id=str(attempt_row["id"]),
                    reason="stale_status_version",
                    detail="attempt changed between the fence check and the update",
                )
            fresh = uow.query_one(
                "SELECT * FROM execution_attempts WHERE id = ?",
                (attempt_id_effective,),
            )
            if fresh is None:  # pragma: no cover - deleted rows cannot reappear
                raise TaskAttemptNotFoundError(attempt_id=attempt_id_effective)
            attempt_model = self._attempt_read_model(fresh)
        else:
            # Queued/blocked cancellation: no attempt exists to terminate;
            # any supplied attempt fence is a caller bug.
            if attempt_id is not None or lease_id is not None or expected_status_version is not None:
                raise TaskValidationError(
                    "cancelling a queued/blocked task takes no attempt fence"
                )

        # 2. The task leaves the claim queue terminally: cancelled with
        #    finished_at stamped; it can never be claimed or completed.
        task_cursor = uow.execute(
            "UPDATE tasks SET status = 'cancelled', "
            "cancel_request_id = ?, cancel_requested_at = ?, "
            "updated_at = ?, finished_at = ? "
            "WHERE id = ? AND status IN ('queued','blocked','running')",
            (
                effective_cancel_request_id,
                stamp,
                stamp,
                stamp,
                task_id,
            ),
        )
        if task_cursor.rowcount != 1:
            raise TaskTransitionError(
                task_id=task_id,
                reason="task_terminal",
                detail="task changed between the fence read and the update",
            )

        # 3. The hash-chained core.task.cancelled event on the task stream.
        event_data: dict[str, Any] = {
            "task_id": task_id,
            "attempt_id": attempt_id_effective,
            "attempt_no": attempt_no,
            "status_version": next_version,
            "cancel_request_id": effective_cancel_request_id,
            "cancel_requested_at": stamp,
            "reason": prior_status,
        }
        if attempt_lease_id is not None:
            event_data["lease_id"] = attempt_lease_id
            event_data["lease_expires_at"] = attempt_lease_expires_at
        changes: list[str] = [
            "task_status",
            "cancel_request_id",
            "cancel_requested_at",
            "finished_at",
            "reason",
        ]
        if attempt_id_effective is not None:
            changes.extend(["attempt_status", "status_version"])
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_TASK_CANCELLED_EVENT_KIND,
            data=event_data,
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )

        # 4. The complete receipt: the refreshed cancelled task plus the
        #    terminated attempt (running cancellation only).
        task_model = self._task_model(uow, task_id=task_id, project_id=project_id)
        result = TaskCancelReadModel(
            task=task_model,
            attempt=attempt_model,
            execution_guidance=(
                "the running handler may finish its current work, but its "
                "completion is fenced and no post-cancel artifact will be "
                "published"
                if prior_status == "running" and cooperative
                else None
            ),
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=result.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return result

    # -- fenced failure (receipt-protected, m2 plan step 8, T13) -----------

    def fail(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        task_id: str,
        attempt_id: str,
        lease_id: str,
        expected_status_version: int,
        idempotency_key: str,
        actor_kind: str = "local",
        error: Mapping[str, Any] | None = None,
        now: str | None = None,
        command_kind: str = CORE_TASK_FAIL_COMMAND_KIND,
        update_run_projection: bool = False,
    ) -> TaskFailReadModel:
        """Fail one owned attempt through a receipt-protected event.

        Inside the caller's active unit of work this records an executor
        failure of exactly the matching attempt and commits, in one
        ``BEGIN IMMEDIATE`` transaction: the attempt's ``failed``
        transition (``status_version`` +1, ``finished_at`` set, the
        caller's bounded *error* payload stored verbatim), the task's
        ``running`` exit, the hash-chained ``core.task.failed`` event on
        the task stream, both heads, and one complete receipt.

        The task exit is budget-driven (SD1): when the attempt budget
        remains (``attempt_no < max_attempts``) the task is requeued
        (``queued`` — a later claim creates a fresh fenced attempt), and
        when it is exhausted the task fails terminally (``failed`` with
        ``finished_at`` set) and can never resurrect.

        Every fence is checked **before** any mutation: the task must be
        ``running`` and belong to *project_id*, and the attempt must belong
        to that task, be live (``claimed`` or ``running``), carry the
        caller's ``lease_id``, and match ``expected_status_version``. A
        stale, foreign, or already-terminated attempt raises the typed
        :class:`TaskTransitionError` / :class:`TaskAttemptNotFoundError`
        and changes zero rows — so fail can never race heartbeat, expiry,
        cancellation, or completion into a double terminal outcome: the
        single writer FIFO plus the exact version/lease predicates select
        exactly one writer.

        Idempotency: the receipt gate runs first. An identical retry under
        the same key returns exactly the stored failure with zero new rows;
        a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        task_id = _require_non_empty_string("task_id", task_id)
        attempt_id = _require_non_empty_string("attempt_id", attempt_id)
        lease_id = _require_non_empty_string("lease_id", lease_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if isinstance(expected_status_version, bool) or not isinstance(
            expected_status_version, int
        ) or expected_status_version <= 0:
            raise TaskValidationError(
                "expected_status_version must be a positive integer, "
                f"got {expected_status_version!r}"
            )
        if actor_kind not in ACTOR_KINDS:
            raise TaskValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        error_payload = dict(error) if error is not None else {}

        # Semantic request identity: the fenced transition plus the failure
        # payload the caller reports; timestamps are generated state.
        request = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "lease_id": lease_id,
            "expected_status_version": expected_status_version,
            "error": error_payload,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise TaskValidationError(
                f"cannot hash fail request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before any fence read
        # or sequence allocation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return TaskFailReadModel.from_mapping(replayed)

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TaskValidationError("now must be a non-empty string")

        # Fences, all before any mutation (typed stale outcomes).
        task_row = uow.query_one(
            "SELECT * FROM tasks WHERE id = ? AND project_id = ?",
            (task_id, project_id),
        )
        if task_row is None:
            raise TaskNotFoundError(task_id=task_id)
        if str(task_row["status"]) != "running":
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="task_not_running",
                detail=(
                    f"task status is {task_row['status']!r}, expected 'running'"
                ),
            )
        attempt_row = uow.query_one(
            "SELECT * FROM execution_attempts WHERE id = ?", (attempt_id,)
        )
        if attempt_row is None:
            raise TaskAttemptNotFoundError(attempt_id=attempt_id)
        if str(attempt_row["task_id"]) != task_id:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="attempt_task_mismatch",
            )
        if str(attempt_row["status"]) not in ("claimed", "running"):
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="attempt_not_live",
                detail=(
                    f"attempt status is {attempt_row['status']!r}, "
                    "expected 'claimed' or 'running'"
                ),
            )
        if str(attempt_row["lease_id"]) != lease_id:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="lease_mismatch",
            )
        if int(attempt_row["status_version"]) != expected_status_version:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="stale_status_version",
                detail=(
                    f"attempt status_version is "
                    f"{attempt_row['status_version']}, expected "
                    f"{expected_status_version}"
                ),
            )

        attempt_no = int(attempt_row["attempt_no"])
        max_attempts = int(task_row["max_attempts"])
        outcome = "requeued" if attempt_no < max_attempts else "failed"
        next_version = expected_status_version + 1
        new_task_status = "queued" if outcome == "requeued" else "failed"
        stream_id = f"{task_id}:{CORE_TASK_STREAM_TYPE}"
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex

        # 1. The attempt fails, fenced on its exact version and live status
        #    so a concurrent transition can never be overwritten.
        try:
            error_json = canonical_json(error_payload)
        except CanonicalizationError as exc:
            raise TaskValidationError(
                f"cannot serialize fail error payload: {exc}"
            ) from exc
        cursor = uow.execute(
            "UPDATE execution_attempts SET status = 'failed', "
            "status_version = ?, updated_at = ?, finished_at = ?, "
            "error_json = ? "
            "WHERE id = ? AND task_id = ? AND status IN ('claimed','running') "
            "AND status_version = ?",
            (
                next_version,
                stamp,
                stamp,
                error_json,
                attempt_id,
                task_id,
                expected_status_version,
            ),
        )
        if cursor.rowcount != 1:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="stale_status_version",
                detail="attempt changed between the fence check and the update",
            )
        # 2. The task leaves running: requeued (claimable again) or failed
        #    terminally (finished_at stamped; never resurrects).
        task_cursor = uow.execute(
            "UPDATE tasks SET status = ?, updated_at = ?, finished_at = ? "
            "WHERE id = ? AND status = 'running'",
            (
                new_task_status,
                stamp,
                stamp if outcome == "failed" else None,
                task_id,
            ),
        )
        if task_cursor.rowcount != 1:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="task_not_running",
                detail="task changed between the fence read and the update",
            )
        # A terminal child failure is also a terminal parent outcome when it
        # exhausts this task's retry budget.  Keep the persisted run
        # projection in lock-step with the shared read-time derivation just
        # as completion already does.  Without this, a synchronous SDK
        # invocation can return a failed task while leaving its run row
        # ``running`` until a caller happens to close it.
        run_id = task_row["run_id"]
        if update_run_projection and outcome == "failed" and run_id is not None:
            self._update_run_projection_on_child_terminal(
                uow,
                run_id=str(run_id),
                project_id=project_id,
                stamp=stamp,
            )
        # 3. The hash-chained core.task.failed event on the task stream.
        event_data: dict[str, Any] = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "attempt_no": attempt_no,
            "status_version": next_version,
            "outcome": outcome,
            "lease_id": attempt_row["lease_id"],
            "lease_expires_at": attempt_row["lease_expires_at"],
            "reason": "executor_failed",
            "error": error_payload,
        }
        changes: list[str] = [
            "attempt_status",
            "task_status",
            "status_version",
            "outcome",
            "finished_at",
            "error",
        ]
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_TASK_FAILED_EVENT_KIND,
            data=event_data,
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 4. The complete receipt: refreshed task plus the failed attempt.
        task_model = self._task_model(uow, task_id=task_id, project_id=project_id)
        fresh = uow.query_one(
            "SELECT * FROM execution_attempts WHERE id = ?", (attempt_id,)
        )
        if fresh is None:  # pragma: no cover - deleted rows cannot reappear
            raise TaskAttemptNotFoundError(attempt_id=attempt_id)
        result = TaskFailReadModel(
            task=task_model,
            attempt=self._attempt_read_model(fresh),
            outcome=outcome,
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=result.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return result

    # -- eligible nonterminal retry (receipt-protected, m2 plan step 8, T14)

    def retry(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        task_id: str,
        idempotency_key: str,
        actor_kind: str = "local",
        executor_id: str | None = None,
        selected_task_ids: Sequence[str] | None = None,
        now: str | None = None,
        command_kind: str = CORE_TASK_RETRY_COMMAND_KIND,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        allow_one_shot_invocation_retry: bool = True,
    ) -> TaskRetryReadModel:
        """Retry one eligible nonterminal task through a receipt-protected event.

        Inside the caller's active unit of work this restarts exactly the
        failed/expired work (SD1): when the task is nonterminal, its latest
        attempt ``failed`` or ``expired``, and the ``max_attempts`` budget
        remains, ``retry`` creates a brand-new fenced attempt
        (``attempt_no`` one past the prior, ``status`` ``claimed``,
        ``status_version`` 1, a fresh lease) and transitions the task back
        to ``running`` in one ``BEGIN IMMEDIATE`` transaction together with
        the hash-chained ``core.task.retried`` event, both heads, and one
        complete receipt. The task never leaves the attempt-number
        sequence, so a later claim cannot create a competing attempt while
        the retried attempt is live, and a terminal task can never be
        retried (no replacement-task-ID semantics; SD1).

        Eligibility is decided **before** any mutation:

        - the task must exist and belong to *project_id*;
        - the task must be nonterminal — a ``succeeded``, ``failed``, or
          ``cancelled`` task raises the typed ``task_terminal`` outcome and
          changes zero rows;
        - the task must be ``queued`` with a prior ``failed`` or ``expired``
          attempt (fail/expire requeue within budget); anything else
          (``running`` work, a never-claimed task, a ``blocked`` task)
          raises the typed ``not_retryable`` outcome and changes zero rows;
        - the prior attempt must leave budget remaining
          (``attempt_no < max_attempts``); an exhausted budget raises the
          typed ``attempt_budget_exhausted`` outcome and changes zero rows.

        *selected_task_ids* is the optional selected-task set used by group
        retry (plan step 13, T22): when supplied it is a non-empty
        sequence of unique non-empty task ids, canonicalized (sorted) and
        included in the request identity, so a group retry of the same
        subset reuses the same per-task receipts and a different subset is
        a mismatch before any mutation.

        Idempotency: the receipt gate runs first. An identical retry under
        the same key returns exactly the stored retry with zero new rows; a
        changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        task_id = _require_non_empty_string("task_id", task_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise TaskValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if executor_id is not None:
            _require_non_empty_string("executor_id", executor_id)
        if isinstance(lease_seconds, bool) or not isinstance(
            lease_seconds, int
        ) or lease_seconds <= 0:
            raise TaskValidationError(
                "lease_seconds must be a positive integer, "
                f"got {lease_seconds!r}"
            )
        if selected_task_ids is not None:
            if (
                isinstance(selected_task_ids, (str, bytes))
                or not isinstance(selected_task_ids, Sequence)
                or not selected_task_ids
            ):
                raise TaskValidationError(
                    "selected_task_ids must be a non-empty sequence of "
                    "non-empty task ids"
                )
            for entry in selected_task_ids:
                _require_non_empty_string("selected_task_ids[]", entry)
            if len(set(selected_task_ids)) != len(selected_task_ids):
                raise TaskValidationError(
                    "selected_task_ids must not contain duplicates"
                )

        # Semantic request identity: the task plus the optional group
        # selection set (canonical sorted form); generated state (the new
        # attempt id, lease, timestamps) never participates.
        request: dict[str, Any] = {"task_id": task_id}
        if selected_task_ids is not None:
            request["selected_task_ids"] = sorted(selected_task_ids)
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise TaskValidationError(
                f"cannot hash retry request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before any fence read
        # or sequence allocation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return TaskRetryReadModel.from_mapping(replayed)

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TaskValidationError("now must be a non-empty string")

        # Fences, all before any mutation (typed stale outcomes).
        task_row = uow.query_one(
            "SELECT * FROM tasks WHERE id = ? AND project_id = ?",
            (task_id, project_id),
        )
        if task_row is None:
            raise TaskNotFoundError(task_id=task_id)
        prior_status = str(task_row["status"])
        if prior_status not in ("queued", "blocked", "running", "failed"):
            raise TaskTransitionError(
                task_id=task_id,
                reason="task_terminal",
                detail=(
                    f"task status is {prior_status!r}; a terminal task "
                    "never resurrects"
                ),
            )
        if prior_status not in ("queued", "failed"):
            if prior_status == "blocked":
                hard_prerequisite_rows = uow.query(
                    "SELECT d.depends_on_task_id, d.ordinal, dep.status "
                    "FROM task_dependencies d "
                    "JOIN tasks dep ON dep.id = d.depends_on_task_id "
                    "WHERE d.task_id = ? AND d.kind = 'hard' "
                    "ORDER BY d.ordinal ASC, d.depends_on_task_id ASC",
                    (task_id,),
                )
                prerequisites = _hard_prerequisite_projection(
                    [dict(row) for row in hard_prerequisite_rows]
                )
                blocked_reason = _blocked_reason(
                    task_status=prior_status,
                    hard_prerequisites=prerequisites,
                ) or (
                    "blocked: waiting for one or more hard prerequisites; "
                    "retry is only supported after a failed or expired attempt"
                )
                raise TaskTransitionError(
                    task_id=task_id,
                    reason="not_retryable",
                    detail=(
                        f"{blocked_reason}; retry is unavailable. "
                        "Wait for every hard prerequisite to succeed, or "
                        "cancel this dependent and create a replacement "
                        "prerequisite chain if any prerequisite is cancelled "
                        "or failed"
                    ),
                )
            if prior_status != "failed":
                raise TaskTransitionError(
                    task_id=task_id,
                    reason="not_retryable",
                    detail=(
                        f"task status is {prior_status!r}; retry requires a "
                        "queued task whose latest attempt failed or expired"
                    ),
                )
        # A standalone failed task is terminal: only invocation-created
        # children receive the deliberate one-shot retry exception below.
        # Keep this distinction observable so the operator/read contract does
        # not mislabel an already-terminal standalone task as merely budget
        # exhausted.  Invocation children retain the existing retry path,
        # which reopens their parent run and extends the one-shot budget.
        if prior_status == "failed" and task_row["run_id"] is None:
            raise TaskTransitionError(
                task_id=task_id,
                reason="task_terminal",
                detail=(
                    "task status is 'failed'; a standalone terminal task "
                    "never resurrects"
                ),
            )
        prior_attempt_row = uow.query_one(
            "SELECT * FROM execution_attempts WHERE task_id = ? "
            "ORDER BY attempt_no DESC LIMIT 1",
            (task_id,),
        )
        if prior_attempt_row is None:
            raise TaskTransitionError(
                task_id=task_id,
                reason="not_retryable",
                detail="task has no prior attempt; only failed or expired "
                "work is retryable",
            )
        prior_attempt_status = str(prior_attempt_row["status"])
        if prior_attempt_status not in ("failed", "expired"):
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=str(prior_attempt_row["id"]),
                reason="not_retryable",
                detail=(
                    f"latest attempt status is {prior_attempt_status!r}; "
                    "retry requires a failed or expired attempt"
                ),
            )
        max_attempts = int(task_row["max_attempts"])
        prior_attempt_no = int(prior_attempt_row["attempt_no"])
        retried_before = uow.query_one(
            "SELECT 1 FROM events WHERE stream_id = ? AND kind = ? LIMIT 1",
            (f"{task_id}:{CORE_TASK_STREAM_TYPE}", CORE_TASK_RETRIED_EVENT_KIND),
        ) is not None
        one_shot_invocation_retry = (
            prior_status == "failed"
            and task_row["run_id"] is not None
            and max_attempts == 1
            and prior_attempt_no == 1
            and not retried_before
            and allow_one_shot_invocation_retry
        )
        if prior_attempt_no >= max_attempts and not one_shot_invocation_retry:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=str(prior_attempt_row["id"]),
                reason="attempt_budget_exhausted",
                detail=(
                    f"attempt {prior_attempt_no} of {max_attempts} already "
                    "consumed the max_attempts budget"
                ),
            )

        # The new fenced attempt: next number in the task's attempt
        # sequence, status_version 1, a fresh lease. Generated state only.
        attempt_id = generate_lowercase_ulid()
        lease_id = generate_lowercase_ulid()
        lease_expires_at = _add_seconds_iso(stamp, lease_seconds)
        attempt_no = prior_attempt_no + 1
        stream_id = f"{task_id}:{CORE_TASK_STREAM_TYPE}"
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex

        # 1. One local claimed attempt: status_version 1, leased, no event
        #    history of its own yet.
        uow.execute(
            "INSERT INTO execution_attempts "
            "(id, task_id, attempt_no, executor_id, status, status_version, "
            "lease_id, lease_expires_at, heartbeat_counter, last_heartbeat_at, "
            "progress_json, error_json, created_at, updated_at, finished_at) "
            "VALUES (?, ?, ?, ?, 'claimed', 1, ?, ?, 0, NULL, '{}', '{}', "
            "?, ?, NULL)",
            (
                attempt_id,
                task_id,
                attempt_no,
                executor_id,
                lease_id,
                lease_expires_at,
                stamp,
                stamp,
            ),
        )

        # 2. The task leaves the queue: running, so no claim can create a
        #    competing attempt while this retried attempt is live.
        if one_shot_invocation_retry:
            task_cursor = uow.execute(
                "UPDATE tasks SET status = 'running', max_attempts = ?, "
                "updated_at = ? WHERE id = ? AND status = 'failed'",
                (prior_attempt_no + 1, stamp, task_id),
            )
        else:
            task_cursor = uow.execute(
                "UPDATE tasks SET status = 'running', updated_at = ? "
                "WHERE id = ? AND status = 'queued'",
                (stamp, task_id),
            )
        if task_cursor.rowcount != 1:
            raise TaskTransitionError(
                task_id=task_id,
                reason="task_terminal",
                detail="task changed between the fence read and the update",
            )
        if one_shot_invocation_retry and task_row["run_id"] is not None:
            # A direct ``tasks retry`` is a supported recovery surface for an
            # invocation-created child. Reopen the failed parent projection
            # before dispatch so the later fenced completion can terminalize
            # it again; otherwise the child would succeed while the run row
            # remained a contradictory terminal ``failed`` projection.
            counts, _derived_status = derive_run_progress_counts(
                uow,
                run_id=str(task_row["run_id"]),
                project_id=project_id,
            )
            projection = {
                "total_children": sum(counts.values()),
                "succeeded": counts.get("succeeded", 0),
                "failed": counts.get("failed", 0),
                "cancelled": counts.get("cancelled", 0),
                "status": "running",
            }
            uow.execute(
                "UPDATE runs SET result_json = ?, status = 'running', "
                "finished_at = NULL WHERE id = ? AND project_id = ? "
                "AND status = 'failed'",
                (
                    canonical_json(projection),
                    str(task_row["run_id"]),
                    project_id,
                ),
            )

        # 3. The hash-chained core.task.retried event on the task stream.
        event_data: dict[str, Any] = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "attempt_no": attempt_no,
            "status_version": 1,
            "prior_attempt_no": prior_attempt_no,
            "prior_attempt_status": prior_attempt_status,
            "lease_id": lease_id,
            "lease_expires_at": lease_expires_at,
            "reason": prior_attempt_status,
            "budget_extension": one_shot_invocation_retry,
        }
        changes: list[str] = [
            "task_status",
            "attempt_status",
            "status_version",
            "attempt_no",
            "prior_attempt_no",
            "prior_attempt_status",
            "lease_id",
            "lease_expires_at",
            "reason",
        ]
        if one_shot_invocation_retry:
            changes.append("max_attempts")
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_TASK_RETRIED_EVENT_KIND,
            data=event_data,
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )

        # 4. The complete receipt: refreshed task plus the new attempt.
        task_model = self._task_model(uow, task_id=task_id, project_id=project_id)
        fresh = uow.query_one(
            "SELECT * FROM execution_attempts WHERE id = ?", (attempt_id,)
        )
        if fresh is None:  # pragma: no cover - deleted rows cannot reappear
            raise TaskAttemptNotFoundError(attempt_id=attempt_id)
        result = TaskRetryReadModel(
            task=task_model,
            attempt=self._attempt_read_model(fresh),
            prior_attempt_no=prior_attempt_no,
            prior_attempt_status=prior_attempt_status,
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=result.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return result

    def is_retry_eligible(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        task_id: str,
        allow_one_shot_invocation_retry: bool = True,
    ) -> tuple[bool, str]:
        """Read-only retry-eligibility check shared with group retry (m2 step 13).

        Returns ``(True, "")`` when :meth:`retry` would accept the task
        right now, otherwise ``(False, reason)`` with ``reason`` one of
        ``"task_not_found"``, ``"task_terminal"``, ``"not_retryable"``, or
        ``"attempt_budget_exhausted"`` — exactly the same rules :meth:`retry`
        enforces before any mutation, applied read-only so the run
        repository's group retry can filter "all eligible" children without
        duplicating the race-hardened predicate. The check reads only; the
        actual transition always goes through :meth:`retry` (same UoW, so
        nothing can interleave between the check and the fenced transition).
        """
        _require_non_empty_string("task_id", task_id)
        task_row = uow.query_one(
            "SELECT * FROM tasks WHERE id = ? AND project_id = ?",
            (task_id, project_id),
        )
        if task_row is None:
            return False, "task_not_found"
        prior_status = str(task_row["status"])
        if prior_status not in ("queued", "blocked", "running", "failed"):
            return False, "task_terminal"
        if prior_status not in ("queued", "failed"):
            return False, "not_retryable"
        # Keep this read-only predicate aligned with retry(): a standalone
        # task whose terminal failure is recorded directly on the task has no
        # parent invocation lifecycle to reopen.
        if prior_status == "failed" and task_row["run_id"] is None:
            return False, "task_terminal"
        prior_attempt_row = uow.query_one(
            "SELECT * FROM execution_attempts WHERE task_id = ? "
            "ORDER BY attempt_no DESC LIMIT 1",
            (task_id,),
        )
        if prior_attempt_row is None:
            return False, "not_retryable"
        prior_attempt_status = str(prior_attempt_row["status"])
        if prior_attempt_status not in ("failed", "expired"):
            return False, "not_retryable"
        prior_attempt_no = int(prior_attempt_row["attempt_no"])
        max_attempts = int(task_row["max_attempts"])
        if (
            prior_attempt_no >= max_attempts
            and not (
                prior_status == "failed"
                and task_row["run_id"] is not None
                and max_attempts == 1
                and prior_attempt_no == 1
                and uow.query_one(
                    "SELECT 1 FROM events WHERE stream_id = ? AND kind = ? LIMIT 1",
                    (f"{task_id}:{CORE_TASK_STREAM_TYPE}", CORE_TASK_RETRIED_EVENT_KIND),
                ) is None
                and allow_one_shot_invocation_retry
            )
        ):
            return False, "attempt_budget_exhausted"
        return True, ""

    # -- fenced completion (receipt-protected, m2 plan step 10, T18) -------

    def complete(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        task_id: str,
        attempt_id: str,
        lease_id: str,
        expected_status_version: int,
        idempotency_key: str,
        outputs: Sequence[Mapping[str, Any]],
        result: Mapping[str, Any] | None = None,
        media_repo: Any,
        actor_kind: str = "local",
        now: str | None = None,
        command_kind: str = CORE_TASK_COMPLETE_COMMAND_KIND,
        generation_repo: Any = None,
        generation_request: Mapping[str, Any] | None = None,
        timeline_repo: Any = None,
        registry_merge: Mapping[str, Any] | None = None,
    ) -> TaskCompleteReadModel:
        """Complete one owned attempt atomically into media and outputs.

        Inside the caller's active unit of work this commits, in one
        ``BEGIN IMMEDIATE`` transaction: each prepared output is
        materialized through the injected ``media_repo``'s in-UoW primitive
        (T17, ``materialize_prepared`` — verified bytes published or reused,
        media/location/relation rows, hash-chained ``core.media.*`` events),
        the ordered ``task_outputs`` rows are inserted, the attempt
        terminates ``succeeded`` (``status_version`` +1, ``finished_at``
        set), the task reaches the terminal ``succeeded`` state with
        ``winning_attempt_id`` set, eligible hard dependents are unblocked,
        the parent run projection (when present) is recomputed, the
        hash-chained ``core.task.completed`` event is appended, and **one**
        complete receipt records every ordered event id.

        Every fence is rechecked **before** any semantic mutation: the task
        must be ``running`` and belong to *project_id*, and the attempt must
        belong to that task, be live (``claimed`` or ``running``), carry the
        caller's ``lease_id``, and match ``expected_status_version``. A
        stale, foreign, terminal, or already-losing attempt raises the typed
        :class:`TaskTransitionError` / :class:`TaskAttemptNotFoundError`
        and changes zero rows — so complete can never race heartbeat,
        expiry, cancellation, or another completion into a double terminal
        outcome: the single writer FIFO plus the exact version/lease
        predicates select exactly one winning attempt, and a losing or
        stale completion materializes no media, no output, and no receipt.

        *outputs* is the ordered list of validated outputs of two kinds.
        Prepared-media entries carry ``ordinal`` (non-negative int),
        ``is_primary`` (bool — exactly one across the whole list), ``role``
        (``"result"`` for the primary; the DDL CHECK forbids ``is_primary``
        on other roles), optional ``label``/``path`` metadata persisted in
        ``params_json``, and the immutable :class:`PreparedMedia` record
        (byte identity); optional ``media_id``/``realm``/``locator``/
        ``relations`` keys pass through to the media materialization.
        Evidence entries carry no ``prepared`` record — only optional
        ``path``/``label``/``digest`` facts and a ``byte_size`` count — and
        persist with a NULL ``media_id`` (their facts ride in the completed
        event payload and the receipt's result_json), because
        ``task_outputs.media_id`` stays NOT NULL. ``media_repo`` is the
        caller's media repository (duck-typed on ``materialize_prepared``);
        the kernel never constructs a second writer. *result* is an
        optional non-empty mapping of caller-supplied summary facts that
        rides in the ``core.task.completed`` event payload and the receipt's
        result_json; a completion needs at least one output or such a
        summary — zero-output completions without one stay rejected.

        Idempotency: the receipt gate runs first. An identical retry under
        the same key returns exactly the stored completion with zero new
        rows; a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        task_id = _require_non_empty_string("task_id", task_id)
        attempt_id = _require_non_empty_string("attempt_id", attempt_id)
        lease_id = _require_non_empty_string("lease_id", lease_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if isinstance(expected_status_version, bool) or not isinstance(
            expected_status_version, int
        ) or expected_status_version <= 0:
            raise TaskValidationError(
                "expected_status_version must be a positive integer, "
                f"got {expected_status_version!r}"
            )
        if actor_kind not in ACTOR_KINDS:
            raise TaskValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if not hasattr(media_repo, "materialize_prepared"):
            raise TaskValidationError(
                "media_repo must expose materialize_prepared for the "
                "in-UoW media primitive (T17), got "
                f"{type(media_repo).__name__}"
            )
        if result is not None and (
            isinstance(result, (str, bytes)) or not isinstance(result, Mapping)
        ):
            raise TaskValidationError(
                "result must be a mapping of JSON-safe summary facts when "
                f"provided, got {type(result).__name__}"
            )
        normalized_outputs = self._normalize_completion_outputs(outputs)
        result_summary = dict(result) if result else None
        if not normalized_outputs and result_summary is None:
            raise TaskValidationError(
                "complete requires at least one materialized output or a "
                "non-empty result summary"
            )

        # Semantic request identity: the fenced transition plus every
        # caller-supplied output fact. Generated state (media/location ids,
        # timestamps, publication reuse) never participates, and the
        # prepared record's filesystem source path is excluded — media
        # identity is byte SHA-256 alone (SD2), so a re-execution after a
        # crash that re-prepares identical bytes at a fresh staging path
        # replays instead of mismatching. A result summary joins the
        # identity only when present, so receipts recorded before summaries
        # existed still replay unchanged.
        request: dict[str, Any] = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "lease_id": lease_id,
            "expected_status_version": expected_status_version,
            "outputs": [
                self._output_request_identity(entry) for entry in normalized_outputs
            ],
        }
        if result_summary is not None:
            request["result"] = result_summary
        # Optional generation and registry writes are externally visible
        # completion side effects. Include them in request identity so a
        # changed retry under one idempotency key cannot replay the first
        # receipt while silently dropping the changed side effect.
        if generation_request is not None:
            if not isinstance(generation_request, Mapping):
                raise TaskValidationError(
                    "generation_request must be a mapping when supplied"
                )
            request["generation_request"] = dict(generation_request)
        if registry_merge is not None:
            if not isinstance(registry_merge, Mapping):
                raise TaskValidationError(
                    "registry_merge must be a mapping when supplied"
                )
            request["registry_merge"] = dict(registry_merge)
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise TaskValidationError(
                f"cannot hash complete request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before any fence read
        # or sequence allocation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return TaskCompleteReadModel.from_mapping(replayed)

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TaskValidationError("now must be a non-empty string")

        # Fences, all before any mutation (typed stale outcomes).
        task_row = uow.query_one(
            "SELECT * FROM tasks WHERE id = ? AND project_id = ?",
            (task_id, project_id),
        )
        if task_row is None:
            raise TaskNotFoundError(task_id=task_id)
        if str(task_row["status"]) != "running":
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="task_not_running",
                detail=(
                    f"task status is {task_row['status']!r}, expected 'running'"
                ),
            )
        attempt_row = uow.query_one(
            "SELECT * FROM execution_attempts WHERE id = ?", (attempt_id,)
        )
        if attempt_row is None:
            raise TaskAttemptNotFoundError(attempt_id=attempt_id)
        if str(attempt_row["task_id"]) != task_id:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="attempt_task_mismatch",
            )
        if str(attempt_row["status"]) not in ("claimed", "running"):
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="attempt_not_live",
                detail=(
                    f"attempt status is {attempt_row['status']!r}, "
                    "expected 'claimed' or 'running'"
                ),
            )
        if str(attempt_row["lease_id"]) != lease_id:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="lease_mismatch",
            )
        if int(attempt_row["status_version"]) != expected_status_version:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="stale_status_version",
                detail=(
                    f"attempt status_version is "
                    f"{attempt_row['status_version']}, expected "
                    f"{expected_status_version}"
                ),
            )

        next_version = expected_status_version + 1
        stream_id = f"{task_id}:{CORE_TASK_STREAM_TYPE}"
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        head_before = int(
            uow.query_one(
                "SELECT event_head_seq FROM projects WHERE id = ?",
                (project_id,),
            )["event_head_seq"]
        )

        # 1. Materialize every verified prepared output through the in-UoW
        #    media primitive (T17), in deterministic ordinal order. Each
        #    output appends its own hash-chained core.media event(s); no
        #    receipt is written by the primitive.
        materialized: list[dict[str, Any]] = []
        for index, entry in enumerate(normalized_outputs):
            if "prepared" not in entry:
                # Evidence output: no media identity exists, so nothing is
                # materialized; its declared facts ride in the completed
                # event payload and receipt below.
                continue
            materialize_args: dict[str, Any] = {
                "project_id": project_id,
                "prepared": entry["prepared"],
                "idempotency_key": f"{idempotency_key}#out:{index}",
                "actor_kind": actor_kind,
                "created_at": stamp,
            }
            if entry.get("media_id") is not None:
                materialize_args["media_id"] = entry["media_id"]
            if entry.get("realm") is not None:
                materialize_args["realm"] = entry["realm"]
            if entry.get("locator") is not None:
                materialize_args["locator"] = entry["locator"]
            if entry.get("relations") is not None:
                materialize_args["relations"] = entry["relations"]
            if entry.get("published") is not None:
                materialize_args["published"] = entry["published"]
            materialized_media = media_repo.materialize_prepared(
                uow, **materialize_args
            )
            materialized.append(
                {
                    "ordinal": entry["ordinal"],
                    "is_primary": entry["is_primary"],
                    "role": entry["role"],
                    "label": entry.get("label"),
                    "path": entry.get("path"),
                    "prepared": entry["prepared"],
                    "media_id": materialized_media.media_id,
                }
            )

        # 2. The ordered task_outputs projection (one row per output).
        output_models: list[TaskOutputReadModel] = []
        for entry in materialized:
            params: dict[str, Any] = {}
            if entry.get("label") is not None:
                params["label"] = entry["label"]
            if entry.get("path") is not None:
                params["path"] = entry["path"]
            params["content_hash"] = entry["prepared"].digest
            params["byte_size"] = entry["prepared"].byte_size
            try:
                params_json = canonical_json(params)
            except CanonicalizationError as exc:
                raise TaskValidationError(
                    f"cannot serialize output params: {exc}"
                ) from exc
            uow.execute(
                "INSERT INTO task_outputs "
                "(task_id, ordinal, role, media_id, is_primary, "
                "params_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    task_id,
                    entry["ordinal"],
                    entry["role"],
                    entry["media_id"],
                    1 if entry["is_primary"] else 0,
                    params_json,
                    stamp,
                ),
            )
            output_models.append(
                TaskOutputReadModel(
                    ordinal=entry["ordinal"],
                    role=entry["role"],
                    media_id=entry["media_id"],
                    is_primary=entry["is_primary"],
                    params=params,
                    created_at=stamp,
                )
            )

        # Evidence outputs persist outside task_outputs (its media_id stays
        # NOT NULL): read-model entries with a NULL media_id whose params
        # carry the declared facts, kept in one ordinal-ordered list.
        for entry in normalized_outputs:
            if "prepared" in entry:
                continue
            params = {
                key: entry[key]
                for key in ("path", "digest", "byte_size", "label")
                if key in entry
            }
            output_models.append(
                TaskOutputReadModel(
                    ordinal=entry["ordinal"],
                    role=entry["role"],
                    media_id=None,
                    is_primary=entry["is_primary"],
                    params=params,
                    created_at=stamp,
                )
            )
        output_models.sort(key=lambda model: model.ordinal)

        # 3. The attempt terminates succeeded: version +1, finished_at set,
        #    fenced on the exact live status and version so a concurrent
        #    transition can never be overwritten.
        attempt_cursor = uow.execute(
            "UPDATE execution_attempts SET status = 'succeeded', "
            "status_version = ?, updated_at = ?, finished_at = ? "
            "WHERE id = ? AND task_id = ? AND status IN ('claimed','running') "
            "AND status_version = ?",
            (
                next_version,
                stamp,
                stamp,
                attempt_id,
                task_id,
                expected_status_version,
            ),
        )
        if attempt_cursor.rowcount != 1:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="stale_status_version",
                detail="attempt changed between the fence check and the update",
            )
        # 4. The task reaches its terminal succeeded state: winning attempt
        #    recorded, finished_at stamped, never resurrects (SD1).
        task_cursor = uow.execute(
            "UPDATE tasks SET status = 'succeeded', winning_attempt_id = ?, "
            "updated_at = ?, finished_at = ? "
            "WHERE id = ? AND status = 'running'",
            (attempt_id, stamp, stamp, task_id),
        )
        if task_cursor.rowcount != 1:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="task_not_running",
                detail="task changed between the fence read and the update",
            )

        # 5. Unblock eligible hard dependents: a blocked dependent whose
        #    every hard dependency has now succeeded becomes queued (pure
        #    projection update — the vocabulary has no unblocked event).
        unblocked = self._unblock_eligible_dependents(
            uow, task_id=task_id, stamp=stamp
        )

        # 6. Recompute the parent run projection when the task belongs to a
        #    run (plan step 10: update any parent run projection).
        run_id = task_row["run_id"]
        run_projection: dict[str, Any] | None = None
        if run_id is not None:
            run_projection = self._update_run_projection_on_child_terminal(
                uow,
                run_id=str(run_id),
                project_id=project_id,
                stamp=stamp,
            )

        # 6.5 Generation creation when the completion requests it (doc 27
        #     §5 step 6): one generations row plus its initial original
        #     variant, receipt-free and event-free, inside this same unit
        #     of work. Requires the task transition above to have committed
        #     in-transaction (record_completion validates terminal state).
        generation_model: Any = None
        if generation_request is not None:
            if not isinstance(generation_request, Mapping):
                raise TaskValidationError(
                    "generation_request must be a mapping when supplied"
                )
            if not hasattr(generation_repo, "record_completion"):
                raise TaskValidationError(
                    "generation_request requires a repository exposing "
                    "record_completion"
                )
            gtype = generation_request.get("type")
            if not isinstance(gtype, str) or not gtype:
                raise TaskValidationError(
                    "generation_request.type must be a non-empty string"
                )
            primary_media_id = next(
                (
                    entry["media_id"]
                    for entry in materialized
                    if entry["is_primary"]
                ),
                None,
            )
            variant: dict[str, Any] = dict(
                generation_request.get("variant") or {}
            )
            variant.setdefault("media_id", primary_media_id)
            generation_model = generation_repo.record_completion(
                uow,
                project_id=project_id,
                task_id=task_id,
                type=gtype,
                params=generation_request.get("params"),
                variant=variant,
            )

        # 6.7 Registry visibility merge when the completion requires it
        #     (doc 27 §5 step 7): internal evented asset-registry merge
        #     against the current timeline head; skipping is legal and
        #     leaves the completion receipt valid (N1).
        registry_head: int | None = None
        if registry_merge is not None:
            if not isinstance(registry_merge, Mapping):
                raise TaskValidationError(
                    "registry_merge must be a mapping when supplied"
                )
            if not hasattr(timeline_repo, "merge_registry"):
                raise TaskValidationError(
                    "registry_merge requires a repository exposing "
                    "merge_registry"
                )
            timeline_id = registry_merge.get("timeline_id")
            entries_payload = registry_merge.get("entries")
            if not isinstance(timeline_id, str) or not timeline_id:
                raise TaskValidationError(
                    "registry_merge.timeline_id must be a non-empty string"
                )
            if not isinstance(entries_payload, Mapping):
                raise TaskValidationError(
                    "registry_merge.entries must be a JSON object"
                )
            registry_head = timeline_repo.merge_registry(
                uow,
                project_id=project_id,
                timeline_id=timeline_id,
                entries=entries_payload,
                actor_kind="system" if actor_kind == "local" else actor_kind,
            )

        # 7. The hash-chained core.task.completed event on the task stream.
        media_id_by_ordinal = {
            entry["ordinal"]: entry["media_id"] for entry in materialized
        }
        event_outputs: list[dict[str, Any]] = []
        for entry in normalized_outputs:
            item: dict[str, Any] = {
                "ordinal": entry["ordinal"],
                "role": entry["role"],
                "is_primary": entry["is_primary"],
            }
            if "prepared" in entry:
                item["media_id"] = media_id_by_ordinal[entry["ordinal"]]
                item["content_hash"] = entry["prepared"].digest
            else:
                item["media_id"] = None
                for key in ("path", "digest", "byte_size", "label"):
                    if key in entry:
                        item[key] = entry[key]
            event_outputs.append(item)
        event_data: dict[str, Any] = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "attempt_no": int(attempt_row["attempt_no"]),
            "status_version": next_version,
            "winning_attempt_id": attempt_id,
            "outputs": event_outputs,
            "unblocked_dependents": unblocked,
        }
        if result_summary is not None:
            event_data["result"] = dict(result_summary)
        changes: list[str] = [
            "attempt_status",
            "task_status",
            "status_version",
            "winning_attempt_id",
            "finished_at",
            "outputs",
            "unblocked_dependents",
        ]
        if result_summary is not None:
            changes.append("result")
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_TASK_COMPLETED_EVENT_KIND,
            data=event_data,
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )

        # 8. The one complete receipt covering every ordered event id the
        #    completion appended (media events in ordinal order, then the
        #    completed event), spanning the exact project-seq range.
        ordered_events = uow.query(
            "SELECT event_id, project_seq FROM events "
            "WHERE project_id = ? AND project_seq > ? "
            "ORDER BY project_seq ASC",
            (project_id, head_before),
        )
        event_ids = tuple(str(row["event_id"]) for row in ordered_events)
        if not event_ids:
            raise TaskTransitionError(
                task_id=task_id,
                attempt_id=attempt_id,
                reason="task_not_running",
                detail="completion appended no events; the transaction "
                "cannot be recorded",
            )
        first_seq = int(ordered_events[0]["project_seq"])
        last_seq = int(ordered_events[-1]["project_seq"])

        task_model = self._task_model(uow, task_id=task_id, project_id=project_id)
        fresh = uow.query_one(
            "SELECT * FROM execution_attempts WHERE id = ?", (attempt_id,)
        )
        if fresh is None:  # pragma: no cover - deleted rows cannot reappear
            raise TaskAttemptNotFoundError(attempt_id=attempt_id)
        completed = TaskCompleteReadModel(
            task=task_model,
            attempt=self._attempt_read_model(fresh),
            outputs=tuple(output_models),
            event_ids=event_ids,
            run=run_projection,
            result=result_summary,
            generation=(
                generation_model.to_dict()
                if generation_model is not None
                and hasattr(generation_model, "to_dict")
                else generation_model
            ),
            timeline_head=registry_head,
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=first_seq,
            last_project_seq=last_seq,
            event_ids=list(event_ids),
            result=completed.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return completed

    # -- completion helpers ------------------------------------------------

    @staticmethod
    def _normalize_completion_outputs(
        outputs: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Validate and order one completion command's output list.

        Every rule that can be decided from the request alone runs here,
        before hashing and before any SQL: each entry is a mapping with a
        unique non-negative ``ordinal``, a boolean ``is_primary`` (exactly
        one across the whole list), and a role string (``"result"`` for the
        primary; the DDL CHECK forbids primary on other roles). Two entry
        kinds are accepted: a prepared-media entry carries the immutable
        :class:`PreparedMedia` ``prepared`` record (byte identity) plus
        optional ``label``/``path`` metadata and optional
        ``media_id``/``realm``/``locator``/``relations`` passthrough keys;
        an evidence entry carries no ``prepared`` record — only optional
        ``path``/``label``/``digest`` strings and a non-negative
        ``byte_size`` — and must not declare media materialization keys. An
        empty list is legal here; whether a completion may ship zero
        outputs at all (at least one output or a non-empty result summary)
        is :meth:`complete`'s decision. Returns the entries ordered by
        ordinal (ties impossible after the uniqueness check).
        """
        if isinstance(outputs, (str, bytes)) or not isinstance(
            outputs, Sequence
        ):
            raise TaskValidationError(
                "outputs must be a sequence of output mappings"
            )
        normalized: list[dict[str, Any]] = []
        seen_ordinals: set[int] = set()
        for index, raw in enumerate(outputs):
            if not isinstance(raw, Mapping):
                raise TaskValidationError(
                    f"outputs[{index}] must be a mapping, got "
                    f"{type(raw).__name__}"
                )
            ordinal = raw.get("ordinal")
            if isinstance(ordinal, bool) or not isinstance(
                ordinal, int
            ) or ordinal < 0:
                raise TaskValidationError(
                    f"outputs[{index}].ordinal must be a non-negative "
                    f"integer, got {ordinal!r}"
                )
            if ordinal in seen_ordinals:
                raise TaskValidationError(
                    f"outputs[{index}].ordinal {ordinal!r} is duplicated"
                )
            seen_ordinals.add(ordinal)
            is_primary = raw.get("is_primary")
            if not isinstance(is_primary, bool):
                raise TaskValidationError(
                    f"outputs[{index}].is_primary must be a boolean, "
                    f"got {is_primary!r}"
                )
            role = raw.get("role")
            if role is None:
                role = "result" if is_primary else "output"
            if not isinstance(role, str) or not role:
                raise TaskValidationError(
                    f"outputs[{index}].role must be a non-empty string, "
                    f"got {role!r}"
                )
            if role != "result" and is_primary:
                raise TaskValidationError(
                    f"outputs[{index}]: only a 'result' output may be "
                    "primary (DDL CHECK role = 'result' OR is_primary = 0)"
                )
            prepared = raw.get("prepared")
            if prepared is not None:
                if not isinstance(prepared, PreparedMedia):
                    raise TaskValidationError(
                        f"outputs[{index}].prepared must be a PreparedMedia "
                        f"record, got {type(prepared).__name__}"
                    )
                entry: dict[str, Any] = {
                    "ordinal": ordinal,
                    "is_primary": is_primary,
                    "role": role,
                    "prepared": prepared,
                }
                for key in ("label", "path", "media_id", "realm", "locator"):
                    if raw.get(key) is not None:
                        value = raw[key]
                        if not isinstance(value, str) or not value:
                            raise TaskValidationError(
                                f"outputs[{index}].{key} must be a non-empty "
                                f"string, got {value!r}"
                            )
                        entry[key] = value
                if raw.get("relations") is not None:
                    relations = raw["relations"]
                    if not isinstance(relations, Sequence) or isinstance(
                        relations, (str, bytes)
                    ):
                        raise TaskValidationError(
                            f"outputs[{index}].relations must be a sequence"
                        )
                    entry["relations"] = list(relations)
                published = raw.get("published")
                if published is not None:
                    if not isinstance(published, PublishedMedia):
                        raise TaskValidationError(
                            f"outputs[{index}].published must be a "
                            f"PublishedMedia record, got "
                            f"{type(published).__name__}"
                        )
                    if published.digest != prepared.digest:
                        raise TaskValidationError(
                            f"outputs[{index}].published digest sha256:"
                            f"{published.digest} does not match prepared "
                            f"sha256:{prepared.digest}"
                        )
                    entry["published"] = published
            else:
                declared = [
                    key
                    for key in ("media_id", "realm", "locator", "relations")
                    if raw.get(key) is not None
                ]
                if declared:
                    raise TaskValidationError(
                        f"outputs[{index}]: an evidence output (no prepared "
                        "record) must not declare media materialization "
                        f"keys {declared}"
                    )
                entry = {
                    "ordinal": ordinal,
                    "is_primary": is_primary,
                    "role": role,
                }
                for key in ("label", "path", "digest"):
                    if raw.get(key) is not None:
                        value = raw[key]
                        if not isinstance(value, str) or not value:
                            raise TaskValidationError(
                                f"outputs[{index}].{key} must be a non-empty "
                                f"string, got {value!r}"
                            )
                        entry[key] = value
                byte_size = raw.get("byte_size")
                if byte_size is not None:
                    if isinstance(byte_size, bool) or not isinstance(
                        byte_size, int
                    ) or byte_size < 0:
                        raise TaskValidationError(
                            f"outputs[{index}].byte_size must be a "
                            f"non-negative integer, got {byte_size!r}"
                        )
                    entry["byte_size"] = byte_size
            normalized.append(entry)
        if normalized and sum(
            1 for entry in normalized if entry["is_primary"]
        ) != 1:
            raise TaskValidationError(
                "complete requires exactly one primary output "
                f"(got {sum(1 for e in normalized if e['is_primary'])})"
            )
        normalized.sort(key=lambda entry: entry["ordinal"])
        return normalized

    @staticmethod
    def _output_request_identity(entry: Mapping[str, Any]) -> dict[str, Any]:
        """The canonical request-identity mapping for one completion output.

        Media identity is byte SHA-256 alone (SD2): the filesystem
        ``source_path`` of the prepared record is excluded so a
        re-execution that re-prepares identical bytes under a fresh staging
        directory replays instead of mismatching. An evidence output (no
        ``prepared`` record) contributes its declared facts verbatim.
        """
        prepared = entry.get("prepared")
        if prepared is None:
            identity: dict[str, Any] = {
                "ordinal": entry["ordinal"],
                "is_primary": entry["is_primary"],
                "role": entry["role"],
            }
            for key in ("path", "digest", "byte_size", "label"):
                if key in entry:
                    identity[key] = entry[key]
            return identity
        identity = {
            "ordinal": entry["ordinal"],
            "is_primary": entry["is_primary"],
            "role": entry["role"],
            "prepared": {
                "digest": prepared.digest,
                "byte_size": prepared.byte_size,
                "media_kind": prepared.media_kind,
                "mime_type": prepared.mime_type,
                "rel_path": prepared.rel_path,
            },
        }
        for key in ("label", "path", "media_id", "realm", "locator"):
            if entry.get(key) is not None:
                identity[key] = entry[key]
        if entry.get("relations") is not None:
            identity["relations"] = list(entry["relations"])
        return identity

    def _unblock_eligible_dependents(
        self, uow: UnitOfWork, *, task_id: str, stamp: str
    ) -> list[str]:
        """Unblock blocked hard dependents whose every dependency satisfied.

        A blocked task that hard-depends on *task_id* becomes ``queued``
        exactly when all of its hard dependencies have reached the frozen
        ``succeeded`` terminal state — the same predicate claim eligibility
        uses. This is a pure projection update inside the completing
        command; the vocabulary has no unblocked event kind. Returns the
        unblocked task ids in deterministic order.
        """
        candidates = [
            str(row["task_id"])
            for row in uow.query(
                "SELECT DISTINCT d.task_id FROM task_dependencies d "
                "JOIN tasks t ON t.id = d.task_id "
                "WHERE d.depends_on_task_id = ? AND d.kind = 'hard' "
                "AND t.status = 'blocked'",
                (task_id,),
            )
        ]
        unblocked: list[str] = []
        for dependent_id in sorted(candidates):
            unsatisfied = uow.query_one(
                "SELECT COUNT(*) AS n FROM task_dependencies d "
                "JOIN tasks dep ON dep.id = d.depends_on_task_id "
                "WHERE d.task_id = ? AND d.kind = 'hard' "
                "AND dep.status <> 'succeeded'",
                (dependent_id,),
            )
            if int(unsatisfied["n"]) != 0:
                continue
            cursor = uow.execute(
                "UPDATE tasks SET status = 'queued', updated_at = ? "
                "WHERE id = ? AND status = 'blocked'",
                (stamp, dependent_id),
            )
            if cursor.rowcount == 1:
                unblocked.append(dependent_id)
        return unblocked

    def _update_run_projection_on_child_terminal(
        self,
        uow: UnitOfWork,
        *,
        run_id: str,
        project_id: str,
        stamp: str,
    ) -> dict[str, Any]:
        """Recompute the parent run projection after one child completes.

        Derives the group progress from the child task statuses ordered by
        ``run_ordinal`` (no persisted cursor or mutable aggregate — plan
        step 13's derivation rule, applied here at the completion path):
        the ``result_json`` progress counts are rewritten and, when every
        child is terminal, the run transitions to ``succeeded`` (all
        succeeded), ``failed`` (any failed), or ``cancelled`` (otherwise)
        with ``finished_at`` stamped. A run that is already terminal is
        left untouched. Returns the JSON-safe projection mapping persisted
        in ``result_json``.
        """
        run_row = uow.query_one(
            "SELECT * FROM runs WHERE id = ? AND project_id = ?",
            (run_id, project_id),
        )
        if run_row is None:  # pragma: no cover - FK guarantees existence
            raise TaskTransitionError(
                task_id="",
                attempt_id="",
                reason="task_not_running",
                detail=f"run {run_id!r} vanished from the project",
            )
        if str(run_row["status"]) != "running":
            # A terminal run is immutable for this path (group operations,
            # plan step 13, own terminal-run rejection); keep the projection
            # as it stands.
            return {"status": str(run_row["status"]), "terminal": True}
        counts, run_status = derive_run_progress_counts(
            uow, run_id=run_id, project_id=project_id
        )
        total = sum(counts.values())
        projection: dict[str, Any] = {
            "total_children": total,
            "succeeded": counts.get("succeeded", 0),
            "failed": counts.get("failed", 0),
            "cancelled": counts.get("cancelled", 0),
            "status": run_status,
        }
        try:
            result_json = canonical_json(projection)
        except CanonicalizationError as exc:  # pragma: no cover - ints only
            raise TaskValidationError(
                f"cannot serialize run projection: {exc}"
            ) from exc
        uow.execute(
            "UPDATE runs SET result_json = ?, status = ?, finished_at = ? "
            "WHERE id = ? AND status = 'running'",
            (
                result_json,
                run_status,
                stamp if run_status != "running" else None,
                run_id,
            ),
        )
        return projection

    # -- internal lifecycle helpers ----------------------------------------

    def _task_model(
        self, uow: UnitOfWork, *, task_id: str, project_id: str
    ) -> TaskReadModel:
        """Rebuild the frozen task read model inside the active UoW.

        Joins the current project head so ``event_head_seq`` reflects every
        event appended so far in this transaction (including the claim
        event just committed by the caller's command).
        """
        row = uow.query_one(
            "SELECT t.*, p.event_head_seq AS event_head_seq FROM tasks t "
            "JOIN projects p ON p.id = t.project_id "
            "WHERE t.id = ? AND t.project_id = ?",
            (task_id, project_id),
        )
        if row is None:
            raise TaskNotFoundError(task_id=task_id)
        dependency_rows = uow.query(
            "SELECT task_id, depends_on_task_id, kind, ordinal "
            "FROM task_dependencies WHERE task_id = ? "
            "ORDER BY ordinal ASC, depends_on_task_id ASC",
            (task_id,),
        )
        prerequisite_rows = uow.query(
            "SELECT d.depends_on_task_id, d.ordinal, dep.status "
            "FROM task_dependencies d "
            "JOIN tasks dep ON dep.id = d.depends_on_task_id "
            "WHERE d.task_id = ? AND d.kind = 'hard' "
            "ORDER BY d.ordinal ASC, d.depends_on_task_id ASC",
            (task_id,),
        )
        return self._row_to_read_model(
            row,
            [dict(dep) for dep in dependency_rows],
            _hard_prerequisite_projection(
                [dict(prerequisite) for prerequisite in prerequisite_rows]
            ),
        )

    @staticmethod
    def _attempt_read_model(row: Mapping[str, Any]) -> TaskAttemptReadModel:
        """Build the frozen attempt read model from one attempts row.

        Used by :meth:`heartbeat` and :meth:`expire_overdue` to return the
        refreshed attempt after the in-transaction write.
        """
        return TaskAttemptReadModel(
            id=str(row["id"]),
            task_id=str(row["task_id"]),
            attempt_no=int(row["attempt_no"]),
            executor_id=row["executor_id"],
            status=str(row["status"]),
            status_version=int(row["status_version"]),
            lease_id=row["lease_id"],
            lease_expires_at=row["lease_expires_at"],
            heartbeat_counter=int(row["heartbeat_counter"]),
            last_heartbeat_at=row["last_heartbeat_at"],
            progress=parse_json(str(row["progress_json"])),
            error=parse_json(str(row["error_json"])),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            finished_at=row["finished_at"],
        )


__all__ = [
    "ATTEMPT_STATUSES",
    "CORE_TASK_CANCEL_COMMAND_KIND",
    "CORE_TASK_CANCELLED_EVENT_KIND",
    "CORE_TASK_CLAIM_COMMAND_KIND",
    "CORE_TASK_CLAIMED_EVENT_KIND",
    "CORE_TASK_COMPLETE_COMMAND_KIND",
    "CORE_TASK_COMPLETED_EVENT_KIND",
    "CORE_TASK_CREATE_COMMAND_KIND",
    "CORE_TASK_CREATED_EVENT_KIND",
    "CORE_TASK_EXPIRE_COMMAND_KIND",
    "CORE_TASK_EXPIRED_EVENT_KIND",
    "CORE_TASK_FAIL_COMMAND_KIND",
    "CORE_TASK_FAILED_EVENT_KIND",
    "CORE_TASK_RETRY_COMMAND_KIND",
    "CORE_TASK_RETRIED_EVENT_KIND",
    "CORE_TASK_START_COMMAND_KIND",
    "CORE_TASK_STARTED_EVENT_KIND",
    "CORE_TASK_STREAM_TYPE",
    "DEFAULT_LEASE_SECONDS",
    "DEPENDENCY_KINDS",
    "HARD_DEPENDENCY_SATISFIED_STATUS",
    "TASK_STATUSES",
    "TaskAlreadyExistsError",
    "TaskAttemptNotFoundError",
    "TaskAttemptReadModel",
    "TaskCancelReadModel",
    "TaskClaimReadModel",
    "TaskCompleteReadModel",
    "TaskDependencyError",
    "TaskDependencyReadModel",
    "TaskExpiryReadModel",
    "TaskFailReadModel",
    "TaskListRow",
    "TaskNotFoundError",
    "TaskOutputReadModel",
    "TaskReadModel",
    "TaskRepository",
    "TaskRepositoryError",
    "TaskRetryReadModel",
    "TaskTransitionError",
    "TaskValidationError",
    "compute_spec_hash",
    "derive_run_progress_counts",
]
