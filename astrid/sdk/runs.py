"""Typed run SDK service (m4 plan step 13, task T14).

Exposes repository-backed run ``list``, ``show`` (with optional evidence and
derived child progress), ``cancel``, ``retry_failed``, and ordered ``events``
over the kernel :class:`~astrid.core.repositories.runs.RunRepository` with the
frozen SDK envelope (``docs/contracts/astrid-sdk-v10.md`` section 1).

The service is a thin adapter over the repository's existing grouping,
cancellation, and retry-selection logic (m2 plan steps 12-13):

- **list** returns one lightweight read model per run in a project, ordered
  by ``started_at`` then id;
- **show** returns the run read model plus the **derived child progress**
  (``RunRepository.derive_progress`` — always a function of the child task
  rows, never a persisted cursor), and optionally the run's ordered evidence
  items (``EvidenceRepository.list`` filtered to the run);
- **cancel** drives every eligible child to the terminal ``cancelled`` state
  through the shared task-cancel predicate, recomputes the run projection,
  and returns one complete run-level receipt;
- **retry_failed** restarts the run's eligible failed/expired children (or an
  explicit ``selected_task_ids`` subset) through the shared task-retry
  predicate, preserving attempt-budget and terminal-immutability rules;
- **events** returns the run's ordered ``core.run`` stream events through the
  read-only :class:`~astrid.core.repositories.events.EventRepository`.

Every mutation returns exactly one :class:`DomainResult` envelope with the
five frozen keys, the committed :class:`CommandReceipt`, and the key used;
every failure returns the frozen three-key error object via the centralized
:func:`map_error` (not-found → ``not_found``, terminal run →
``terminal_state``, stale head → ``stale_version``, validation →
``validation_error``, mismatch → ``idempotency_mismatch``).

The run read model and derived progress are assembled here from the kernel
``runs`` row and the run repository's public read surface. The service holds
a reference to the shared writer solely to open one unit of work per mutation
and read; it never opens its own writer or connection, and its SQL is limited
to read-only projection queries against the frozen ``runs`` table (no
mutation logic, hashing, or lifecycle arbitration lives here).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from astrid.core.receipts.canonical import parse_json
from astrid.core.receipts.service import CommandReceipt, ReceiptService
from astrid.core.repositories.events import EventRepository
from astrid.core.repositories.evidence import EvidenceRepository
from astrid.core.repositories.runs import (
    CORE_RUN_STREAM_TYPE,
    RunNotFoundError,
    RunRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.sdk.contracts import DomainResult, resolve_idempotency_key
from astrid.sdk.exceptions import ServiceValidationError, map_error

__all__ = ["RunsService"]

# The runs row columns this service projects into its read model. The kernel
# run repository exposes no dedicated read command in this milestone, so the
# service reads the frozen projection row through one unit of work and pairs
# it with ``RunRepository.derive_progress`` (the shared derived-progress
# read). The read is transaction-scoped but performs zero writes.
_RUN_ROW_SELECT = (
    "SELECT id, project_id, kind, status, title, input_json, result_json, "
    "started_at, finished_at FROM runs"
)


def _run_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    """Build the JSON-safe run read model from one ``runs`` row."""
    input_value = parse_json(str(row["input_json"]))
    result_value = parse_json(str(row["result_json"]))
    return {
        "id": str(row["id"]),
        "project_id": str(row["project_id"]),
        "kind": str(row["kind"]),
        "status": str(row["status"]),
        "title": row["title"],
        "input": input_value,
        "result": result_value,
        "started_at": str(row["started_at"]),
        "finished_at": row["finished_at"],
    }


class RunsService:
    """Repository-backed run list/show/cancel/retry_failed/events surface.

    Stateless: a single instance is safe to share across concurrent callers.
    The constructor receives the shared :class:`DatabaseWriter` (one writer
    queue), the run repository, the receipt service, the evidence repository,
    and the read-only ordered event repository.
    """

    def __init__(
        self,
        writer: DatabaseWriter,
        runs: RunRepository,
        receipts: ReceiptService,
        evidence: EvidenceRepository,
        event_log: EventRepository,
    ) -> None:
        self._writer = writer
        self._runs = runs
        self._receipts = receipts
        self._evidence = evidence
        self._event_log = event_log

    # -- list --------------------------------------------------------------

    def list(self, project_id: str) -> DomainResult[list[dict[str, Any]]]:
        """Return one lightweight read model per run in a project.

        Ordered by ``started_at`` then id (deterministic, stable).
        """
        try:
            rows = UnitOfWork(self._writer).run(
                lambda uow: uow.query(
                    _RUN_ROW_SELECT + " WHERE project_id = ? "
                    "ORDER BY started_at ASC, id ASC",
                    (project_id,),
                )
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success([_run_dict(row) for row in rows])

    # -- show --------------------------------------------------------------

    def show(
        self,
        project_id: str,
        run_id: str,
        *,
        include_evidence: bool = False,
    ) -> DomainResult[dict[str, Any]]:
        """Return one run's read model, derived child progress, and evidence.

        Progress is derived fresh from the child task rows (never a cursor);
        when ``include_evidence`` is true the run's ordered evidence items
        are appended under the ``evidence`` key. A missing or foreign run is
        a typed ``not_found``.
        """
        try:
            data = UnitOfWork(self._writer).run(
                lambda uow: self._show_read(uow, project_id, run_id)
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        if include_evidence:
            try:
                evidence_rows = self._evidence.list(
                    self._writer, project_id, run_id=run_id
                )
            except Exception as exc:  # noqa: BLE001 - centralized mapping
                return DomainResult.failure(map_error(exc))
            data["evidence"] = [row.to_dict() for row in evidence_rows]
        return DomainResult.success(data)

    def _show_read(
        self, uow: UnitOfWork, project_id: str, run_id: str
    ) -> dict[str, Any]:
        """Read one run row plus derived progress inside one unit of work."""
        row = uow.query_one(
            _RUN_ROW_SELECT + " WHERE id = ? AND project_id = ?",
            (run_id, project_id),
        )
        if row is None:
            raise RunNotFoundError(run_id=run_id)
        progress = self._runs.derive_progress(
            uow, project_id=project_id, run_id=run_id
        )
        data = _run_dict(row)
        data["progress"] = progress.to_dict()
        return data

    # -- cancel ------------------------------------------------------------

    def cancel(
        self,
        project_id: str,
        run_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Cancel every eligible child of one running run and return receipt.

        Reuses the repository's shared task-cancel predicate and recomputed
        run projection; running children (whose owned attempt fence a group
        command cannot present) and already-terminal children are skipped
        untouched, and a terminal run is a typed ``terminal_state``.
        """
        try:
            key = self._resolve_key(idempotency_key)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._runs.cancel(
                    uow,
                    project_id=project_id,
                    run_id=run_id,
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

    # -- retry_failed ------------------------------------------------------

    def retry_failed(
        self,
        project_id: str,
        run_id: str,
        *,
        selected_task_ids: Sequence[str] | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Retry the run's eligible failed/expired children (or a subset).

        ``selected_task_ids`` optionally restricts the retry to an explicit
        ordinal-order subset; when omitted every eligible child is retried.
        Ineligible children (terminal, never-claimed, running, or exhausted
        budget) are skipped untouched, and a terminal run is a typed
        ``terminal_state``.
        """
        try:
            key = self._resolve_key(idempotency_key)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        try:
            model = UnitOfWork(self._writer).run(
                lambda uow: self._runs.retry(
                    uow,
                    project_id=project_id,
                    run_id=run_id,
                    idempotency_key=key,
                    selected_task_ids=selected_task_ids,
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

    def events(
        self, project_id: str, run_id: str
    ) -> DomainResult[list[dict[str, Any]]]:
        """Return the run's ordered ``core.run`` stream events.

        Verifies the run exists and belongs to ``project_id`` (typed
        ``not_found`` otherwise), then returns the ordered stream events.
        """
        try:
            row = UnitOfWork(self._writer).run(
                lambda uow: uow.query_one(
                    "SELECT id FROM runs WHERE id = ? AND project_id = ?",
                    (run_id, project_id),
                )
            )
            if row is None:
                raise RunNotFoundError(run_id=run_id)
            models = self._event_log.list_events(
                stream_id=f"{run_id}:{CORE_RUN_STREAM_TYPE}"
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(map_error(exc))
        return DomainResult.success([model.as_dict() for model in models])

    # -- private helpers ---------------------------------------------------

    @staticmethod
    def _resolve_key(idempotency_key: str | None) -> str:
        """Return the caller key or a fresh generated key."""
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
