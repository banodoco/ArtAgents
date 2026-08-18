"""Evidence repository: immutable evidence read models and UoW-only
insertion/listing (m3 plan step 4, T4).

:class:`EvidenceRepository` is the kernel evidence vertical over the frozen
``evidence_items`` table (``id``, ``run_id``, optional ``task_id``, ``kind``,
``summary``, ``data_json``, optional ``media_id``, ``created_at``). The five
evidence kinds are **closed** in m3 as ``observation``, ``measurement``,
``validation``, ``decision``, and ``error`` (decision artifact section 8);
``evidence_items.kind`` has no DDL CHECK, so the closed vocabulary is
enforced here, by the repository, before any write.

:meth:`EvidenceRepository.record` is one complete receipt-backed command
inside the caller's single ``BEGIN IMMEDIATE`` unit of work:

1. validates the frozen evidence facts — a closed ``kind``, a non-empty
   ``summary``, and object ``data`` that canonicalizes — and runs the
   receipt idempotency gate first;
2. validates the cross-row relationships the DDL cannot express, all
   **before any write**:

   - **project/run agreement** — the run row exists and belongs to the
     project (:class:`EvidenceValidationError` ``missing_run`` /
     ``foreign_run``), and its ``core.run`` stream exists
     (``run_stream_missing``);
   - **direct-child task membership** — an optional ``task_id`` exists,
     shares the project, and is a direct child of that run (``missing_task``
     / ``foreign_task`` / ``not_direct_child``);
   - **same-project media** — an optional ``media_id`` exists and shares
     the run project (``missing_media`` / ``foreign_media``);

3. atomically inserts the ``evidence_items`` row, appends one hash-chained
   ``core.evidence.recorded`` event on the run stream (the evidence
   repository is kernel-owned; the run stream carries the subject and the
   evidence rows are kernel tables), and records the complete receipt —
   returning the immutable :class:`EvidenceReadModel` carrying the ordered
   event head (the run-stream sequence of the recorded event).

:meth:`EvidenceRepository.list` is a transaction-free read on a separate
read-only connection: it lists evidence for a project (optionally filtered
by run and/or task) in deterministic immutable order (``run_id``, then
``created_at``, then ``id`` — the ``evidence_run_time`` index shape), with
each row's recorded event sequence resolved from the run stream so the
receipt/event order is provable from the list alone.

The repository is stateless apart from the kernel event append and receipt
services; every command must run inside the caller's
:class:`astrid.core.store.uow.UnitOfWork`.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from astrid.core.events.service import ACTOR_KINDS, EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
    parse_json,
    request_hash,
)
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.errors import RepositoryError
from astrid.core.repositories.projects import ProjectNotFoundError
from astrid.core.repositories.runs import CORE_RUN_STREAM_TYPE
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.util.time import utc_now_iso

CORE_EVIDENCE_RECORDED_EVENT_KIND = "core.evidence.recorded"
"""The m3 event kind emitted for one recorded evidence item.

Appended on the run stream (the evidence repository is kernel-owned; the
run stream carries the subject and the evidence rows are kernel tables),
carrying the evidence id, the run id, the optional task and media ids, the
kind, the summary, and the canonical data payload.
"""

CORE_EVIDENCE_RECORD_COMMAND_KIND = "core.evidence.record"
"""The m3 command kind that evidence-record receipts are keyed on."""

EVIDENCE_KINDS: tuple[str, ...] = (
    "observation",
    "measurement",
    "validation",
    "decision",
    "error",
)
"""The closed m3 evidence kinds, in decision-artifact order.

``evidence_items.kind`` has no DDL CHECK, so this repository-enforced
closed vocabulary is the single gate before any evidence write.
"""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EvidenceRepositoryError(RepositoryError):
    """Base error for the kernel evidence repository family.

    Subclasses :class:`astrid.core.repositories.errors.RepositoryError`
    (and therefore :class:`astrid.core.store.writer.WriterError`), so the
    kernel store error family catches evidence contract violations too.
    """


class EvidenceValidationError(EvidenceRepositoryError):
    """Raised when an evidence argument violates a frozen contract.

    ``detail`` is a stable machine-readable code:

    - ``"bad_kind"`` — ``kind`` is outside the closed five-kind vocabulary;
    - ``"bad_summary"`` — ``summary`` is empty or not a string;
    - ``"bad_data"`` — ``data`` is not a JSON object or does not
      canonicalize (non-JSON values, non-finite numbers, over-deep or
      oversized payloads);
    - ``"bad_actor"`` — ``actor_kind`` is outside the frozen DDL vocabulary;
    - ``"missing_run"`` / ``"foreign_run"`` — the run row is absent or
      belongs to another project;
    - ``"run_stream_missing"`` — the run's ``core.run`` event stream row is
      absent (guarded corruption; the event append would fail otherwise);
    - ``"missing_task"`` / ``"foreign_task"`` — the optional task is absent
      or belongs to another project;
    - ``"not_direct_child"`` — the optional task exists and shares the
      project but belongs to a different run;
    - ``"missing_media"`` / ``"foreign_media"`` — the optional media row is
      absent or belongs to another project;
    - ``"corrupt_data"`` — a stored ``data_json`` cell is not a JSON object
      (raised by reads on corrupted rows).

    All command-side rejections happen **before any write**, so a failing
    record changes zero rows.
    """

    def __init__(
        self,
        *,
        detail: str,
        run_id: str | None = None,
        task_id: str | None = None,
        media_id: str | None = None,
        kind: str | None = None,
        project_id: str | None = None,
    ) -> None:
        self.detail: str = detail
        self.run_id: str | None = run_id
        self.task_id: str | None = task_id
        self.media_id: str | None = media_id
        self.kind: str | None = kind
        self.project_id: str | None = project_id
        super().__init__(f"evidence rejected: {detail}")


# ---------------------------------------------------------------------------
# Frozen read model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvidenceReadModel:
    """One immutable ``evidence_items`` row plus its recorded event head.

    ``event_head_seq`` is the run-stream sequence of the item's
    ``core.evidence.recorded`` event (``None`` only when a corrupted or
    raw-SQL row has no matching event). ``data`` is the parsed canonical
    payload object.
    """

    id: str
    run_id: str
    project_id: str
    kind: str
    summary: str
    data: Mapping[str, Any]
    task_id: str | None
    media_id: str | None
    created_at: str
    event_head_seq: int | None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "project_id": self.project_id,
            "kind": self.kind,
            "summary": self.summary,
            "data": dict(self.data),
            "task_id": self.task_id,
            "media_id": self.media_id,
            "created_at": self.created_at,
            "event_head_seq": self.event_head_seq,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EvidenceReadModel:
        """Rebuild the frozen evidence read model from a stored mapping."""
        head = value.get("event_head_seq")
        return cls(
            id=str(value["id"]),
            run_id=str(value["run_id"]),
            project_id=str(value["project_id"]),
            kind=str(value["kind"]),
            summary=str(value["summary"]),
            data=dict(value.get("data") or {}),
            task_id=value.get("task_id"),
            media_id=value.get("media_id"),
            created_at=str(value["created_at"]),
            event_head_seq=int(head) if head is not None else None,
        )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise EvidenceValidationError(detail=f"bad_{name}")
    return value


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class EvidenceRepository:
    """Stateless kernel evidence command/read surface over the unit of work.

    Composes the kernel event append and receipt services. A single
    instance is safe to share across command callers; every command must
    run inside the caller's :class:`astrid.core.store.uow.UnitOfWork` and
    every read runs transaction-free on a separate read-only connection.
    """

    def __init__(
        self,
        events: EventAppendService,
        receipts: ReceiptService,
    ) -> None:
        self._events = events
        self._receipts = receipts

    # -- record -----------------------------------------------------------

    def record(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        run_id: str,
        kind: str,
        summary: str,
        data: Mapping[str, Any] | None = None,
        task_id: str | None = None,
        media_id: str | None = None,
        idempotency_key: str,
        actor_kind: str = "local",
        evidence_id: str | None = None,
        created_at: str | None = None,
        command_kind: str = CORE_EVIDENCE_RECORD_COMMAND_KIND,
    ) -> EvidenceReadModel:
        """Record one evidence item atomically and idempotently.

        Inside the caller's active unit of work this commits, in one
        ``BEGIN IMMEDIATE`` transaction: the ``evidence_items`` row, the
        hash-chained ``core.evidence.recorded`` event on the run stream,
        both heads, and one complete receipt.

        Rejections happen **before any write**: a kind outside the closed
        vocabulary, an empty summary, non-canonical data, a missing or
        foreign run, a missing/foreign/non-direct-child task, or
        missing/foreign media all change zero rows. Idempotency mirrors the
        kernel commands: the receipt gate runs first, an identical retry
        returns exactly the stored result with zero new rows, and a changed
        request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        run_id = _require_non_empty_string("run_id", run_id)
        kind = _require_non_empty_string("kind", kind)
        summary = _require_non_empty_string("summary", summary)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if not summary.strip():
            raise EvidenceValidationError(detail="bad_summary")
        if kind not in EVIDENCE_KINDS:
            raise EvidenceValidationError(detail="bad_kind", kind=kind)
        if task_id is not None:
            _require_non_empty_string("task_id", task_id)
        if media_id is not None:
            _require_non_empty_string("media_id", media_id)
        if actor_kind not in ACTOR_KINDS:
            raise EvidenceValidationError(detail="bad_actor")
        if data is None:
            data_dict: dict[str, Any] = {}
        elif isinstance(data, Mapping):
            data_dict = dict(data)
        else:
            raise EvidenceValidationError(detail="bad_data")
        try:
            canonical_json(data_dict)
        except CanonicalizationError as exc:
            raise EvidenceValidationError(detail="bad_data") from exc

        if evidence_id is None:
            evidence_id = generate_lowercase_ulid()
        else:
            _require_non_empty_string("evidence_id", evidence_id)

        # Semantic request identity: the stable evidence id (resolved before
        # hashing), run, kind, summary, canonical data, and the optional
        # task/media links; generated values never participate.
        request: dict[str, Any] = {
            "project_id": project_id,
            "run_id": run_id,
            "evidence_id": evidence_id,
            "kind": kind,
            "summary": summary,
            "data": data_dict,
            "task_id": task_id,
            "media_id": media_id,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise EvidenceValidationError(detail="bad_data") from exc

        # Idempotency gate first: replay or mismatch before any mutation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return EvidenceReadModel.from_mapping(replayed)

        # Project/run agreement: the run row exists and shares the project.
        run_row = uow.query_one(
            "SELECT id, project_id, event_stream_id FROM runs WHERE id = ?",
            (run_id,),
        )
        if run_row is None:
            raise EvidenceValidationError(detail="missing_run", run_id=run_id)
        if str(run_row["project_id"]) != project_id:
            raise EvidenceValidationError(
                detail="foreign_run", run_id=run_id, project_id=project_id
            )
        run_stream_id = str(run_row["event_stream_id"])
        if (
            uow.query_one(
                "SELECT id FROM event_streams WHERE id = ? AND stream_type = ?",
                (run_stream_id, CORE_RUN_STREAM_TYPE),
            )
            is None
        ):
            raise EvidenceValidationError(
                detail="run_stream_missing", run_id=run_id
            )

        # Direct-child task membership: exists, shares the project, and is a
        # direct child of this run.
        if task_id is not None:
            task_row = uow.query_one(
                "SELECT id, project_id, run_id FROM tasks WHERE id = ?",
                (task_id,),
            )
            if task_row is None:
                raise EvidenceValidationError(
                    detail="missing_task", task_id=task_id
                )
            if str(task_row["project_id"]) != project_id:
                raise EvidenceValidationError(
                    detail="foreign_task", task_id=task_id
                )
            if str(task_row["run_id"]) != run_id:
                raise EvidenceValidationError(
                    detail="not_direct_child",
                    run_id=run_id,
                    task_id=task_id,
                )

        # Same-project media: exists and shares the run project.
        if media_id is not None:
            media_row = uow.query_one(
                "SELECT id, project_id FROM media WHERE id = ?", (media_id,)
            )
            if media_row is None:
                raise EvidenceValidationError(
                    detail="missing_media", media_id=media_id
                )
            if str(media_row["project_id"]) != project_id:
                raise EvidenceValidationError(
                    detail="foreign_media", media_id=media_id
                )

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise EvidenceValidationError(detail="bad_created_at")
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex

        # 1. The evidence_items row.
        try:
            data_json = canonical_json(data_dict)
        except CanonicalizationError as exc:
            raise EvidenceValidationError(detail="bad_data") from exc
        uow.execute(
            "INSERT INTO evidence_items "
            "(id, run_id, task_id, kind, summary, data_json, media_id, "
            "created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                evidence_id,
                run_id,
                task_id,
                kind,
                summary,
                data_json,
                media_id,
                stamp,
            ),
        )
        # 2. The hash-chained core.evidence.recorded event on the run stream.
        append = self._events.append(
            uow,
            stream_id=run_stream_id,
            project_id=project_id,
            event_kind=CORE_EVIDENCE_RECORDED_EVENT_KIND,
            data={
                "evidence_id": evidence_id,
                "run_id": run_id,
                "task_id": task_id,
                "kind": kind,
                "summary": summary,
                "data": data_dict,
                "media_id": media_id,
            },
            changes=[
                "evidence_id",
                "run_id",
                "task_id",
                "kind",
                "summary",
                "data",
                "media_id",
            ],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 3. The complete receipt with the full read model.
        read_model = EvidenceReadModel(
            id=evidence_id,
            run_id=run_id,
            project_id=project_id,
            kind=kind,
            summary=summary,
            data=data_dict,
            task_id=task_id,
            media_id=media_id,
            created_at=stamp,
            event_head_seq=append.stream_seq,
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
            primary_stream_id=run_stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return read_model

    # -- reads ------------------------------------------------------------

    def list(
        self,
        writer: DatabaseWriter,
        project_id: str,
        *,
        run_id: str | None = None,
        task_id: str | None = None,
    ) -> list[EvidenceReadModel]:
        """List evidence for a project in deterministic immutable order.

        A transaction-free read on a separate read-only connection. Rows
        are ordered by ``run_id``, then ``created_at``, then ``id`` (the
        ``evidence_run_time`` index shape), optionally filtered to one run
        and/or one task. Each row carries the run-stream sequence of its
        ``core.evidence.recorded`` event (``None`` for corrupted or raw-SQL
        rows without one), so event/receipt order is provable from the list.
        A missing project raises :class:`ProjectNotFoundError`.
        """
        _require_non_empty_string("project_id", project_id)
        if run_id is not None:
            _require_non_empty_string("run_id", run_id)
        if task_id is not None:
            _require_non_empty_string("task_id", task_id)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            project = conn.execute(
                "SELECT id FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)
            sql = (
                "SELECT e.*, r.project_id AS project_id, "
                "(SELECT ev.seq FROM events ev "
                " WHERE ev.stream_id = r.event_stream_id "
                " AND ev.kind = ? "
                " AND json_extract(ev.payload_json, '$.data.evidence_id') = e.id"
                ") AS event_head_seq "
                "FROM evidence_items e "
                "JOIN runs r ON r.id = e.run_id "
                "WHERE r.project_id = ?"
            )
            params: list[Any] = [CORE_EVIDENCE_RECORDED_EVENT_KIND, project_id]
            if run_id is not None:
                sql += " AND e.run_id = ?"
                params.append(run_id)
            if task_id is not None:
                sql += " AND e.task_id = ?"
                params.append(task_id)
            sql += " ORDER BY e.run_id ASC, e.created_at ASC, e.id ASC"
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_model(row) for row in rows]

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> EvidenceReadModel:
        try:
            parsed = parse_json(str(row["data_json"]))
        except CanonicalizationError as exc:
            raise EvidenceValidationError(
                detail="corrupt_data",
                run_id=str(row["run_id"]),
            ) from exc
        if not isinstance(parsed, Mapping):
            raise EvidenceValidationError(
                detail="corrupt_data",
                run_id=str(row["run_id"]),
            )
        head = row["event_head_seq"]
        return EvidenceReadModel(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            project_id=str(row["project_id"]),
            kind=str(row["kind"]),
            summary=str(row["summary"]),
            data=dict(parsed),
            task_id=row["task_id"],
            media_id=row["media_id"],
            created_at=str(row["created_at"]),
            event_head_seq=int(head) if head is not None else None,
        )


__all__ = [
    "CORE_EVIDENCE_RECORDED_EVENT_KIND",
    "CORE_EVIDENCE_RECORD_COMMAND_KIND",
    "EVIDENCE_KINDS",
    "EvidenceReadModel",
    "EvidenceRepository",
    "EvidenceRepositoryError",
    "EvidenceValidationError",
]
