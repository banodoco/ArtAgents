"""Typed run SDK service (m4 plan step 13, task T14).

Exposes repository-backed run ``list``, ``show`` (with optional evidence and
derived child progress), ``cancel``, ``retry_failed``, ``close``, and ordered
``events`` over the kernel
:class:`~astrid.core.repositories.runs.RunRepository` with the frozen SDK
envelope (``docs/contracts/astrid-sdk-v10.md`` section 1).

The service is a thin adapter over the repository's existing grouping,
cancellation, retry-selection, and close logic (m2 plan steps 12-13):

- **list** returns one lightweight read model per run in a project, ordered
  by ``started_at`` then id;
- **show** returns the run read model plus the **derived child progress**
  (``RunRepository.derive_progress`` — always a function of the child task
  rows, never a persisted cursor), and optionally the run's ordered evidence
  items (``EvidenceRepository.list`` filtered to the run) plus bounded
  ``child_outputs`` read from the authoritative winning-task completion
  projection;
- **cancel** drives every eligible child to the terminal ``cancelled`` state
  through the shared task-cancel predicate, recomputes the run projection,
  and returns one complete run-level receipt;
- **retry_failed** restarts the run's eligible failed/expired children (or an
  explicit ``selected_task_ids`` subset) through the shared task-retry
  predicate, preserving attempt-budget and terminal-immutability rules;
- **close** terminally closes a run that owns no non-terminal child work
  (zero-child runs, whose derived status can never leave ``running``, and
  runs whose every child is already terminal), deriving an omitted outcome
  from terminal children and returning one complete run-level receipt;
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
and read; it never opens its own writer or connection. Its additional
completion-evidence query is read-only and bounded to direct child tasks and
their committed ``task_outputs`` rows (no mutation logic, hashing, or
lifecycle arbitration lives here).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any

from astrid.core.receipts.canonical import parse_json
from astrid.core.receipts.service import CommandReceipt, ReceiptService
from astrid.core.repositories.events import EventRepository
from astrid.core.repositories.evidence import EvidenceRepository
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.repositories.runs import (
    CORE_RUN_STREAM_TYPE,
    RunNotFoundError,
    RunRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry
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
    queue), the project repository (for project id/slug resolution), the run
    repository, the receipt service, the evidence repository, and the
    read-only ordered event repository.
    """

    def __init__(
        self,
        writer: DatabaseWriter,
        projects: ProjectRepository,
        runs: RunRepository,
        receipts: ReceiptService,
        evidence: EvidenceRepository,
        event_log: EventRepository,
        tasks: Any | None = None,
        media: Any | None = None,
        projects_root: str | None = None,
        registry: FrozenSchemaPackRegistry | None = None,
    ) -> None:
        self._writer = writer
        self._projects = projects
        self._runs = runs
        self._receipts = receipts
        self._evidence = evidence
        self._event_log = event_log
        self._tasks = tasks
        self._media = media
        self._projects_root = projects_root
        self._registry = registry

    # -- list --------------------------------------------------------------

    def list(self, project_id: str) -> DomainResult[list[dict[str, Any]]]:
        """Return one lightweight read model per run in a project.

        ``project_id`` accepts the canonical project id or the immutable
        slug; an unknown address is a typed ``not_found`` (never a silently
        empty list). Ordered by ``started_at`` then id (deterministic).
        """
        try:
            project_id = self._projects.resolve(self._writer, project_id)
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

        ``project_id`` accepts the canonical project id or the immutable
        slug; an unknown address is a typed ``not_found``. Progress is
        derived fresh from the child task rows (never a cursor); when
        ``include_evidence`` is true the run's ordered evidence items are
        appended under the ``evidence`` key. A missing or foreign run is a
        typed ``not_found``.
        """
        try:
            project_id = self._projects.resolve(self._writer, project_id)
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
            data["child_outputs"] = self._child_output_evidence(
                project_id=project_id, run_id=run_id
            )
        return DomainResult.success(data)

    def _child_output_evidence(
        self, *, project_id: str, run_id: str
    ) -> list[dict[str, Any]]:
        """Return bounded completion facts for a run's direct children.

        ``task_outputs`` is the authoritative completion projection: unlike
        executor stdout or the transient invocation manifest it is committed
        in the same fenced transaction as the winning task completion. Keep
        this read model deliberately small and safe for operator/agent use:
        ids, roles, labels, content hashes, byte sizes, and staging-relative
        paths only. Failed children remain represented by the existing
        ``failures`` read model and simply have no completion outputs.
        """
        with self._writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            children = conn.execute(
                "SELECT id, run_ordinal, status FROM tasks "
                "WHERE run_id = ? AND project_id = ? "
                "ORDER BY run_ordinal ASC, id ASC LIMIT 256",
                (run_id, project_id),
            ).fetchall()
            if not children:
                return []
            child_ids = [str(row["id"]) for row in children]
            placeholders = ",".join("?" for _ in child_ids)
            outputs = conn.execute(
                "SELECT task_id, ordinal, role, media_id, is_primary, "
                "params_json, created_at FROM task_outputs "
                f"WHERE task_id IN ({placeholders}) "
                "ORDER BY task_id ASC, ordinal ASC LIMIT 8192",
                child_ids,
            ).fetchall()

        by_task: dict[str, list[dict[str, Any]]] = {
            task_id: [] for task_id in child_ids
        }
        for row in outputs:
            params = parse_json(str(row["params_json"]))
            if not isinstance(params, Mapping):
                params = {}
            item: dict[str, Any] = {
                "ordinal": int(row["ordinal"]),
                "role": str(row["role"]),
                "is_primary": bool(row["is_primary"]),
                "media_id": (
                    None if row["media_id"] is None else str(row["media_id"])
                ),
            }
            for key in ("label", "content_hash", "byte_size"):
                value = params.get(key)
                if value is not None:
                    item[key] = value
            path = params.get("path")
            if isinstance(path, str) and path:
                candidate = PurePosixPath(path)
                if not candidate.is_absolute() and ".." not in candidate.parts:
                    item["path"] = candidate.as_posix()
            by_task[str(row["task_id"])].append(item)

        return [
            {
                "task_id": str(row["id"]),
                "ordinal": (
                    None if row["run_ordinal"] is None else int(row["run_ordinal"])
                ),
                "status": str(row["status"]),
                "outputs": by_task[str(row["id"])][:32],
            }
            for row in children
        ]

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
        failures = uow.query(
            "SELECT t.id AS task_id, a.id AS attempt_id, a.error_json "
            "FROM tasks t JOIN execution_attempts a ON a.task_id = t.id "
            "WHERE t.run_id = ? AND t.project_id = ? AND t.status = 'failed' "
            "AND a.attempt_no = (SELECT MAX(a2.attempt_no) FROM execution_attempts a2 WHERE a2.task_id = t.id) "
            "ORDER BY t.run_ordinal ASC",
            (run_id, project_id),
        )
        if failures:
            data["failures"] = [
                {
                    "task_id": str(row["task_id"]),
                    "attempt_id": str(row["attempt_id"]),
                    "error": parse_json(str(row["error_json"])),
                }
                for row in failures
            ]
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

        ``project_id`` accepts the canonical project id or the immutable
        slug; an unknown address is a typed ``not_found``. Reuses the
        repository's shared task-cancel predicate and recomputed run
        projection; running children are cooperatively fenced (their handler
        may finish, but completion cannot publish), and a terminal run is a
        typed ``terminal_state``.
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
            project_id = self._projects.resolve(self._writer, project_id)
        except ServiceValidationError as exc:
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        except Exception as exc:  # noqa: BLE001 - centralized bounded mapping
            return DomainResult.failure(
                map_error(exc), idempotency_key=idempotency_key or ""
            )
        was_replay = self._committed_receipt(project_id, key) is not None
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
        result_data = model.to_dict()
        if (
            not was_replay
            and self._tasks is not None
            and self._media is not None
            and self._projects_root is not None
        ):
            try:
                from astrid.sdk.invocation import dispatch_retried_task
                from astrid.core.repositories.tasks import TaskAttemptReadModel

                for task_id in model.retried_task_ids:
                    task = self._tasks.show(self._writer, task_id)
                    with self._writer.read_only_connection() as conn:
                        conn.row_factory = sqlite3.Row
                        row = conn.execute(
                            "SELECT * FROM execution_attempts WHERE task_id = ? "
                            "ORDER BY attempt_no DESC LIMIT 1",
                            (task_id,),
                        ).fetchone()
                    if row is None:
                        raise RuntimeError(
                            f"retried task {task_id!r} has no execution attempt"
                        )
                    dispatch_retried_task(
                        writer=self._writer,
                        task_repo=self._tasks,
                        media_repo=self._media,
                        projects_root=self._projects_root,
                        task=task,
                        attempt=TaskAttemptReadModel.from_mapping(dict(row)),
                        idempotency_key=f"{key}:child:{task_id}",
                        registry=self._registry,
                    )
                refreshed = UnitOfWork(self._writer).run(
                    lambda uow: self._show_read(uow, project_id, run_id)
                )
                result_data["run"] = {
                    **result_data["run"],
                    "total_children": refreshed["progress"]["total_children"],
                    "succeeded": refreshed["progress"]["succeeded"],
                    "failed": refreshed["progress"]["failed"],
                    "cancelled": refreshed["progress"]["cancelled"],
                    "status": refreshed["status"],
                    "result": refreshed["result"],
                    "finished_at": refreshed["finished_at"],
                }
                result_data["progress"] = refreshed["progress"]
            except Exception as exc:  # noqa: BLE001 - typed retry execution failure
                return DomainResult.failure(map_error(exc), idempotency_key=key)
        elif self._tasks is not None:
            try:
                # Exact-key replay is read-only but the receipt stores the
                # admission snapshot. Refresh the current run projection so
                # a synchronous retry replay cannot lie about its terminal
                # status or retain a stale finished_at/result.
                refreshed = UnitOfWork(self._writer).run(
                    lambda uow: self._show_read(uow, project_id, run_id)
                )
                result_data["run"] = {
                    **result_data["run"],
                    "total_children": refreshed["progress"]["total_children"],
                    "succeeded": refreshed["progress"]["succeeded"],
                    "failed": refreshed["progress"]["failed"],
                    "cancelled": refreshed["progress"]["cancelled"],
                    "status": refreshed["status"],
                    "result": refreshed["result"],
                    "finished_at": refreshed["finished_at"],
                }
                result_data["progress"] = refreshed["progress"]
            except Exception as exc:  # noqa: BLE001 - typed retry execution failure
                return DomainResult.failure(map_error(exc), idempotency_key=key)
        return DomainResult.success(
            result_data,
            receipt=self._committed_receipt(project_id, key),
            idempotency_key=key,
        )

    # -- close -------------------------------------------------------------

    def close(
        self,
        project_id: str,
        run_id: str,
        *,
        outcome: str | None = None,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        """Terminally close a run that owns no non-terminal child work.

        The terminal transition for zero-child runs (whose derived status
        can never leave ``running``) and any run whose every child is
        already terminal: writes the child-derived (or explicit) terminal
        ``status`` and ``finished_at``, folds *outcome* (``succeeded``/
        ``failed``/``cancelled``) into ``result_json``, emits
        ``core.run.closed``, and
        returns one complete run-level receipt. A run that still owns a
        queued/blocked/running child is a typed ``validation_error`` and a
        terminal run a typed ``terminal_state``.
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
                lambda uow: self._runs.close(
                    uow,
                    project_id=project_id,
                    run_id=run_id,
                    outcome=outcome,
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

    def events(
        self, project_id: str, run_id: str
    ) -> DomainResult[list[dict[str, Any]]]:
        """Return the run's ordered ``core.run`` stream events.

        ``project_id`` accepts the canonical project id or the immutable
        slug; an unknown address is a typed ``not_found``. Verifies the run
        exists and belongs to the project (typed ``not_found`` otherwise),
        then returns the ordered stream events.
        """
        try:
            project_id = self._projects.resolve(self._writer, project_id)
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
