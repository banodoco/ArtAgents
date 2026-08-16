"""Kernel-owned atomic unit of work (m1 plan step 7).

Every semantic command runs as one callback inside **exactly one**
``BEGIN IMMEDIATE`` transaction on the kernel writer's single owned
connection::

    uow = UnitOfWork(writer)
    result = uow.run(create_project_command)

The callback receives the :class:`UnitOfWork` itself and may use only the
typed operations it exposes — query, execute, sequence allocation, stream
CAS, event append (plus the event-append reads that back it: stream row,
tail payload, and idempotency pre-check), projection update, and receipt
operations. There is no
way to reach the ``sqlite3`` connection, start or end a transaction, or
nest a second unit of work from inside a callback:

- Nesting is rejected: :meth:`UnitOfWork.run` refuses to run while the
  writer session already has an active transaction, and the writer refuses
  to accept submissions from its own writer thread (which would deadlock
  the FIFO queue).
- Direct transaction control is rejected by the writer session
  (:class:`astrid.core.store.writer.TransactionControlError`).
- Outside :meth:`UnitOfWork.run`, every typed operation raises
  :class:`UoWError`.

Statement boundaries are observable through an **opt-in** observer passed
as ``on_statement``. The observer is invoked after every SQL statement the
unit of work executes (including ``BEGIN IMMEDIATE``, ``COMMIT``, and
``ROLLBACK``) with ``(kind, sql, parameters)``. No environment variable or
production switch controls this; the observer is a constructor parameter,
so crash/contention tests can record deterministic boundaries without any
alternate transaction path in production code.

The typed operations keep the exact v10 DDL: project sequences come from
``projects.event_head_seq``, stream sequences and heads from
``event_streams.head_seq``, and receipts from ``command_receipts``. No
convenience table or column is added.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Sequence
from typing import Any

from astrid.core.store.writer import DatabaseWriter, WriterError, WriterSession

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UoWError(WriterError):
    """Raised when a unit-of-work contract is violated.

    Covers nesting, using typed operations outside an active run, unknown
    projects/streams during sequence allocation, and invalid projection
    identifiers.
    """


# ---------------------------------------------------------------------------
# Unit of work
# ---------------------------------------------------------------------------

# Observer signature: (kind, sql, parameters). Kind is one of
# "begin_immediate", "statement", "commit", "rollback".
StatementObserver = Callable[[str, str, tuple[Any, ...]], None]

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_EVENT_COLUMNS = (
    "event_id",
    "project_id",
    "project_seq",
    "stream_id",
    "seq",
    "subject_type",
    "subject_id",
    "changes_json",
    "kind",
    "schema_version",
    "idempotency_key",
    "txn_id",
    "actor_kind",
    "payload_json",
    "created_at",
)

_RECEIPT_COLUMNS = (
    "project_id",
    "idempotency_key",
    "request_hash",
    "command_kind",
    "txn_id",
    "primary_stream_id",
    "resulting_stream_seq",
    "first_project_seq",
    "last_project_seq",
    "event_ids_json",
    "result_json",
    "created_at",
)


def _require_identifier(name: str) -> None:
    """Reject anything that is not a plain SQL identifier.

    Projection updates interpolate table and column names into SQL, so the
    identifiers are validated against a strict ``[A-Za-z_][A-Za-z0-9_]*``
    grammar before any statement is built.
    """
    if not _IDENTIFIER_RE.fullmatch(name):
        raise UoWError(f"invalid SQL identifier: {name!r}")


class UnitOfWork:
    """One command = one callback = one ``BEGIN IMMEDIATE`` transaction.

    ``run(callback)`` submits the callback to the writer's FIFO queue,
    wraps it in exactly one ``BEGIN IMMEDIATE`` transaction, commits on
    success, and rolls back when the callback raises. The callback receives
    this unit of work and must use only its typed operations.

    A single instance is safe for concurrent callers: the writer thread is
    the only executor, so the active-session bookkeeping is touched only on
    the writer thread.
    """

    def __init__(
        self,
        writer: DatabaseWriter,
        *,
        on_statement: StatementObserver | None = None,
    ) -> None:
        self._writer = writer
        self._on_statement = on_statement
        self._session: WriterSession | None = None

    # -- transaction envelope ---------------------------------------------

    def run(self, callback: Callable[[UnitOfWork], Any]) -> Any:
        """Run ``callback`` inside exactly one BEGIN IMMEDIATE transaction.

        The callback receives this unit of work and returns a result that
        ``run`` returns after commit. Any exception from the callback rolls
        the transaction back and propagates unchanged (SQLite busy errors
        surface as :class:`astrid.core.store.writer.WriterBusyError`).
        """
        if not callable(callback):
            raise TypeError("unit of work callback must be callable")
        return self._writer.submit(
            lambda session: self._execute(session, callback)
        )

    def _execute(
        self, session: WriterSession, callback: Callable[[UnitOfWork], Any]
    ) -> Any:
        if session.in_transaction:
            raise UoWError(
                "nested unit of work rejected: a transaction is already "
                "active on this writer session"
            )
        self._session = session
        if self._on_statement is not None:
            session._set_statement_observer(self._on_statement)
        try:
            session._begin_immediate()
            try:
                result = callback(self)
            except BaseException:
                session._rollback()
                raise
            session._commit()
            return result
        finally:
            session._clear_statement_observer()
            self._session = None

    # -- typed query / execute --------------------------------------------

    def query(
        self, sql: str, parameters: Sequence[Any] = ()
    ) -> list[sqlite3.Row]:
        """Run one read statement inside the active transaction."""
        return self._require_session().query(sql, parameters)

    def query_one(
        self, sql: str, parameters: Sequence[Any] = ()
    ) -> sqlite3.Row | None:
        """Run one read statement and return its first row or ``None``."""
        return self._require_session().query_one(sql, parameters)

    def execute(
        self, sql: str, parameters: Sequence[Any] = ()
    ) -> sqlite3.Cursor:
        """Run one write statement inside the active transaction."""
        return self._require_session().execute(sql, parameters)

    # -- sequence allocation ----------------------------------------------

    def next_project_seq(self, project_id: str) -> int:
        """Reserve the next gap-free project sequence.

        ``projects.event_head_seq`` is incremented inside the transaction
        and the new head is returned; a rollback reverts the increment, so
        sequences stay gap-free exactly when the command commits.
        """
        session = self._require_session()
        row = session.query_one(
            "UPDATE projects SET event_head_seq = event_head_seq + 1 "
            "WHERE id = ? RETURNING event_head_seq",
            (project_id,),
        )
        if row is None:
            raise UoWError(
                f"cannot allocate project sequence: unknown project "
                f"{project_id!r}"
            )
        return int(row[0])

    def next_stream_seq(self, stream_id: str) -> int:
        """Reserve the next gap-free sequence for one event stream."""
        session = self._require_session()
        row = session.query_one(
            "UPDATE event_streams SET head_seq = head_seq + 1 "
            "WHERE id = ? RETURNING head_seq",
            (stream_id,),
        )
        if row is None:
            raise UoWError(
                f"cannot allocate stream sequence: unknown stream "
                f"{stream_id!r}"
            )
        return int(row[0])

    # -- stream CAS --------------------------------------------------------

    def cas_stream_head(
        self, stream_id: str, expected_seq: int, new_seq: int
    ) -> bool:
        """Compare-and-set ``event_streams.head_seq``.

        Returns ``True`` only when the stream currently has exactly
        ``expected_seq`` and was advanced to ``new_seq``; otherwise no row
        changes and ``False`` is returned. Used by whole-document CAS saves
        (timeline save) against a client-supplied expected version.
        """
        cursor = self._require_session().execute(
            "UPDATE event_streams SET head_seq = ? "
            "WHERE id = ? AND head_seq = ?",
            (new_seq, stream_id, expected_seq),
        )
        return cursor.rowcount == 1

    # -- event append ------------------------------------------------------

    def append_event(
        self,
        *,
        stream_id: str,
        project_id: str,
        event_id: str,
        subject_type: str,
        subject_id: str,
        changes_json: str,
        kind: str,
        schema_version: int,
        idempotency_key: str,
        txn_id: str,
        actor_kind: str,
        payload_json: str,
        created_at: str,
    ) -> tuple[int, int]:
        """Append one event and advance the project and stream heads.

        Allocates the next project sequence and stream sequence, inserts
        the event row, and (through the allocations) advances
        ``projects.event_head_seq`` and ``event_streams.head_seq`` — all
        atomically in the active transaction. Returns
        ``(project_seq, stream_seq)``. A rollback reverts every change.
        """
        session = self._require_session()
        project_seq = self.next_project_seq(project_id)
        stream_seq = self.next_stream_seq(stream_id)
        session.execute(
            "INSERT INTO events ("
            + ", ".join(_EVENT_COLUMNS)
            + ") VALUES ("
            + ", ".join("?" for _ in _EVENT_COLUMNS)
            + ")",
            (
                event_id,
                project_id,
                project_seq,
                stream_id,
                stream_seq,
                subject_type,
                subject_id,
                changes_json,
                kind,
                schema_version,
                idempotency_key,
                txn_id,
                actor_kind,
                payload_json,
                created_at,
            ),
        )
        return project_seq, stream_seq

    # -- typed event-append reads (m1 plan step 10) -------------------------

    def _stream_row(self, stream_id: str) -> sqlite3.Row | None:
        """Return the ``event_streams`` row for one stream, or ``None``.

        The event append service reads the stream's project, type,
        aggregate, and head from this single row, so the stream row — not
        caller-supplied facts — is the authority for aggregate/project
        agreement.
        """
        return self._require_session().query_one(
            "SELECT * FROM event_streams WHERE id = ?", (stream_id,)
        )

    def _tail_event(self, stream_id: str) -> sqlite3.Row | None:
        """Return the most recent event row (highest ``seq``) for one stream.

        The hash-chain append derives the next ``previous_event_hash`` from
        the tail's ``payload_json`` inside the same transaction, so a
        multi-event command chains correctly without any read outside the
        unit of work.
        """
        return self._require_session().query_one(
            "SELECT payload_json FROM events "
            "WHERE stream_id = ? ORDER BY seq DESC LIMIT 1",
            (stream_id,),
        )

    def _has_event(self, stream_id: str, idempotency_key: str) -> bool:
        """Whether an event with this ``(stream_id, idempotency_key)`` exists.

        The ``UNIQUE (stream_id, idempotency_key)`` constraint is the final
        fence; this read lets the event service reject the duplicate with a
        typed error before any sequence allocation.
        """
        row = self._require_session().query_one(
            "SELECT 1 FROM events WHERE stream_id = ? AND idempotency_key = ?",
            (stream_id, idempotency_key),
        )
        return row is not None

    # -- projection update --------------------------------------------------

    def update_projection(
        self, table: str, values: dict[str, Any], where: dict[str, Any]
    ) -> int:
        """Typed projection update: ``UPDATE table SET ... WHERE ...``.

        ``values`` maps column names to new values and ``where`` maps
        column names to equality predicates. Both are required and every
        identifier is validated. Returns the number of rows changed.
        """
        session = self._require_session()
        _require_identifier(table)
        if not values:
            raise UoWError("projection update requires at least one assignment")
        if not where:
            raise UoWError("projection update requires at least one predicate")
        for key in values:
            _require_identifier(key)
        for key in where:
            _require_identifier(key)
        assignments = ", ".join(f"{key} = ?" for key in values)
        predicates = " AND ".join(f"{key} = ?" for key in where)
        cursor = session.execute(
            f"UPDATE {table} SET {assignments} WHERE {predicates}",
            (*values.values(), *where.values()),
        )
        return cursor.rowcount

    # -- receipt operations -------------------------------------------------

    def find_receipt(
        self, project_id: str, idempotency_key: str
    ) -> sqlite3.Row | None:
        """Return the stored receipt row for a project/key, or ``None``."""
        return self._require_session().query_one(
            "SELECT * FROM command_receipts "
            "WHERE project_id = ? AND idempotency_key = ?",
            (project_id, idempotency_key),
        )

    def insert_receipt(
        self,
        *,
        project_id: str,
        idempotency_key: str,
        request_hash: str,
        command_kind: str,
        txn_id: str,
        primary_stream_id: str | None,
        resulting_stream_seq: int | None,
        first_project_seq: int,
        last_project_seq: int,
        event_ids_json: str,
        result_json: str,
        created_at: str,
    ) -> None:
        """Persist one complete command receipt in the active transaction."""
        self._require_session().execute(
            "INSERT INTO command_receipts ("
            + ", ".join(_RECEIPT_COLUMNS)
            + ") VALUES ("
            + ", ".join("?" for _ in _RECEIPT_COLUMNS)
            + ")",
            (
                project_id,
                idempotency_key,
                request_hash,
                command_kind,
                txn_id,
                primary_stream_id,
                resulting_stream_seq,
                first_project_seq,
                last_project_seq,
                event_ids_json,
                result_json,
                created_at,
            ),
        )

    # -- private helpers -----------------------------------------------------

    def _require_session(self) -> WriterSession:
        session = self._session
        if session is None:
            raise UoWError(
                "unit of work is not active: typed operations require "
                "UnitOfWork.run()"
            )
        return session


__all__ = ["StatementObserver", "UnitOfWork", "UoWError"]
