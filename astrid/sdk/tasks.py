"""Typed task SDK service (m4 plan step 12, task T13).

Exposes repository-backed ``create``, ``list``, ``show``, ``cancel``,
``retry``, and ordered ``events`` over the kernel
:class:`~astrid.core.repositories.tasks.TaskRepository` with the frozen SDK
envelope (``docs/contracts/astrid-sdk-v10.md`` section 1). Claim, start, and
heartbeat remain **internal**: they are executor-owned lifecycle transitions
and are never surfaced as public service verbs.

The service is a thin adapter over the repository's existing eligibility,
fencing, cancellation, and retry logic (m2 plan steps 6-8):

- **create** accepts an optional caller idempotency key (a fresh key is
  generated before mutation when absent) and derives a **deterministic**
  task id from ``(command kind, project scope, key)`` so a retry under the
  same key derives the same id and replays with zero new rows;
- **cancel** drives a nonterminal task to the terminal ``cancelled`` state
  through the repository's receipt-protected, version-fenced transition; a
  running task's cancellation requires the executor's attempt fence
  (``attempt_id``/``lease_id``/``expected_status_version``) because claim
  and lease ownership stay internal to the executor;
- **retry** restarts eligible failed/expired work through the repository's
  shared retry predicate (budget and terminal-immutability rules included);
- **list** and **show** are transaction-free reads; ``show`` returns the
  full immutable read model and raises a typed ``not_found`` for a missing
  task;
- **events** returns the task's ordered ``core.task`` stream events through
  the read-only :class:`~astrid.core.repositories.events.EventRepository`.

Every mutation returns exactly one :class:`DomainResult` envelope with the
five frozen keys, the committed :class:`CommandReceipt`, and the key used;
every failure returns the frozen three-key error object via the centralized
:func:`map_error` (not-found → ``not_found``, terminal transition →
``terminal_state``, validation → ``validation_error``, mismatch →
``idempotency_mismatch``).

This module contains **no SQL** and performs no filesystem writes; every
read and mutation is delegated to the task repository and the read-only
event repository. The service holds a reference to the shared writer solely
to open one unit of work per mutation and to run transaction-free reads; it
never opens its own writer or connection.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from astrid.core.receipts.service import CommandReceipt, ReceiptService
from astrid.core.repositories.events import EventRepository
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.repositories.tasks import (
    CORE_TASK_CREATE_COMMAND_KIND,
    CORE_TASK_STREAM_TYPE,
    TaskRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.sdk.contracts import (
    DomainResult,
    derive_stable_id,
    resolve_idempotency_key,
)
from astrid.sdk.exceptions import ServiceValidationError, map_error

__all__ = ["TasksService"]


class TasksService:
    """Repository-backed task create/list/show/cancel/retry/events surface.

    Stateless: a single instance is safe to share across concurrent callers.
    The constructor receives the shared :class:`DatabaseWriter` (one writer
    queue), the project repository (for project id/slug resolution), the
    task repository, the receipt service, and the read-only ordered event
    repository; it holds no SQL and opens no writer of its own.
    """

    def __init__(
        self,
        writer: DatabaseWriter,
        projects: ProjectRepository,
        tasks: TaskRepository,
        receipts: ReceiptService,
        event_log: EventRepository,
    ) -> None:
        self._writer = writer
        self._projects = projects
        self._tasks = tasks
        self._receipts = receipts
        self._event_log = event_log

    # -- create ------------------------------------------------------------

    def create(
        self,
        *,
        project_id: str,
        capability: str,
        spec: Mapping[str, Any],
        input_manifest: Sequence[Any] | None = None,
        priority: int = 0,
        available_at: str | None = None,
        max_attempts: int = 1,
        dependencies: Sequence[Mapping[str, Any]] | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Admit one immutable task and return its committed receipt envelope.

        ``project_id`` accepts the canonical project id **or** the project's
        immutable slug; it is resolved through the project repository before
        the id is derived, and an unknown address is a typed
        ``not_found``/``validation_error`` with zero mutation.

        The idempotency key is the caller's when supplied, otherwise a fresh
        key generated before mutation. The task id is derived
        deterministically from the key (project-scoped), so an identical
        retry replays the committed result with zero new rows and a changed
        request under the same key returns ``idempotency_mismatch`` before
        any mutation.
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project_id)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        task_id = derive_stable_id(
            command_kind=CORE_TASK_CREATE_COMMAND_KIND,
            scope=project_id,
            idempotency_key=key,
            ordinal=0,
        )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._tasks.create(
                    uow,
                    project_id=project_id,
                    capability=capability,
                    spec=spec,
                    input_manifest=input_manifest if input_manifest is not None else [],
                    idempotency_key=key,
                    task_id=task_id,
                    priority=priority,
                    available_at=available_at,
                    max_attempts=max_attempts,
                    dependencies=dependencies,
                )
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    # -- list --------------------------------------------------------------

    def list(self, project_id: str) -> DomainResult[list[dict[str, Any]]]:
        """Return every task in one project (created_at, then id order).

        ``project_id`` accepts the canonical project id or the immutable
        slug; an unknown address is a typed ``not_found``.
        """
        try:
            project_id = self._projects.resolve(self._writer, project_id)
            rows = self._tasks.list(self._writer, project_id)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success([row.to_dict() for row in rows])

    # -- show --------------------------------------------------------------

    def show(self, task_id: str) -> DomainResult[dict[str, Any]]:
        """Return one task's full immutable read model by id.

        A missing task is a typed ``not_found``.
        """
        try:
            model = self._tasks.show(self._writer, task_id)
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success(model.to_dict())

    # -- cancel ------------------------------------------------------------

    def cancel(
        self,
        project_id: str,
        task_id: str,
        *,
        attempt_id: str | None = None,
        lease_id: str | None = None,
        expected_status_version: int | None = None,
        cancel_request_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Cancel one nonterminal task and return its committed receipt.

        A queued/blocked task is cancelled directly. A running task requires
        the executor-owned attempt fence (``attempt_id``/``lease_id``/
        ``expected_status_version``); presenting none against a running task
        is a typed ``validation_error``, and a terminal task is a typed
        ``terminal_state`` — the repository's writer-order terminal
        immutability (SD1) is preserved unchanged.
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project_id)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._tasks.cancel(
                    uow,
                    project_id=project_id,
                    task_id=task_id,
                    idempotency_key=key,
                    attempt_id=attempt_id,
                    lease_id=lease_id,
                    expected_status_version=expected_status_version,
                    cancel_request_id=cancel_request_id,
                )
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    # -- retry -------------------------------------------------------------

    def retry(
        self,
        project_id: str,
        task_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Retry one eligible failed/expired task and return its receipt.

        Delegates the whole eligibility decision (nonterminal, queued with a
        prior failed/expired attempt, budget remaining) to the repository's
        shared retry predicate; an ineligible task is a typed
        ``terminal_state``/``validation_error`` with zero mutation.
        """
        try:
            key = self._resolve_key(idempotency_key)
            project_id = self._projects.resolve(self._writer, project_id)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._tasks.retry(
                    uow,
                    project_id=project_id,
                    task_id=task_id,
                    idempotency_key=key,
                )
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            model.to_dict(),
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    # -- events ------------------------------------------------------------

    def events(self, task_id: str) -> DomainResult[list[dict[str, Any]]]:
        """Return the task's ordered ``core.task`` stream events.

        A read-only, transaction-free read through the ordered event
        repository (``seq`` order within the task stream).
        """
        try:
            models = self._event_log.list_events(
                stream_id=f"{task_id}:{CORE_TASK_STREAM_TYPE}"
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success([model.as_dict() for model in models])

    # -- private helpers ---------------------------------------------------

    @staticmethod
    def _resolve_key(idempotency_key: str | None) -> str:
        """Return the caller key or a fresh generated key.

        An empty or non-string caller key is a typed validation error (SDK
        contract section 4.2), raised before any mutation.
        """
        try:
            return resolve_idempotency_key(idempotency_key)
        except ValueError as exc:
            raise ServiceValidationError(str(exc)) from exc

    def _committed_receipt(
        self, project_id: str, idempotency_key: str
    ) -> CommandReceipt | None:
        """Read-only lookup of the committed receipt for a mutation."""
        with self._writer.read_only_connection() as conn:
            return self._receipts.lookup_committed(
                conn, project_id=project_id, idempotency_key=idempotency_key
            )
