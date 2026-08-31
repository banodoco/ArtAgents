"""Command receipt replay and persistence (m1 plan step 9, T19).

The receipt service runs **inside** the kernel unit of work — the same
``BEGIN IMMEDIATE`` transaction as the command's events, stream/project
heads, and projections — so replay and persistence are atomic with the
mutation they describe (v10 section 2.3 atomic receipts).

- :meth:`ReceiptService.check` is the command-start idempotency gate. For
  the same ``project_id`` / ``idempotency_key`` it returns the stored
  complete result when the stored request hash and command kind match;
  it raises :class:`ReceiptMismatchError` when the key is reused with a
  different hash or kind; and it returns ``None`` when no receipt exists
  yet. ``check`` performs only a read, so a mismatch fails **before** any
  sequence allocation, stream CAS, event append, or projection change.
- :meth:`ReceiptService.record` persists the complete receipt — transaction
  ID, primary stream and resulting sequence, exact project sequence range,
  ordered event IDs, and complete result JSON — in the same transaction, so
  an identical retry later returns exactly the stored result.

The service never exposes receipts to bridge DTOs; it only reads and writes
``command_receipts`` rows through the typed unit-of-work operations.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Any

from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
    parse_json,
)
from astrid.core.receipts.contract import (
    RECEIPT_SHAPE_KEYS,
    CommandReceipt as _CommandReceipt,
    ReceiptValidationError,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import WriterError
from astrid.core.util.time import utc_now_iso

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ReceiptError(WriterError):
    """Base error for receipt replay and persistence.

    Subclasses :class:`astrid.core.store.writer.WriterError` so callers
    that already handle writer errors (busy, shutdown, transaction control)
    also catch receipt contract violations.
    """


class ReceiptMismatchError(ReceiptError):
    """Raised when an idempotency key is reused with a different request.

    The stored receipt matched the ``(project_id, idempotency_key)`` pair
    but the attempted request hash or command kind differs, so replaying
    would return a result for a *different* command. Raised by
    :meth:`ReceiptService.check` before any mutation happens.
    """

    def __init__(
        self,
        *,
        project_id: str,
        idempotency_key: str,
        stored_request_hash: str,
        attempted_request_hash: str,
        stored_command_kind: str,
        attempted_command_kind: str,
    ) -> None:
        self.project_id = project_id
        self.idempotency_key = idempotency_key
        self.stored_request_hash = stored_request_hash
        self.attempted_request_hash = attempted_request_hash
        self.stored_command_kind = stored_command_kind
        self.attempted_command_kind = attempted_command_kind
        message = (
            "idempotency key reused with a different request: "
            f"project {project_id!r} key {idempotency_key!r} "
            f"stored (hash={stored_request_hash!r}, kind={stored_command_kind!r}) "
            f"attempted (hash={attempted_request_hash!r}, kind={attempted_command_kind!r})"
        )
        super().__init__(message)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ReceiptValidationError(f"{name} must be a non-empty string")
    return value


def _require_positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ReceiptValidationError(f"{name} must be a positive integer")
    return value


def _require_non_negative_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReceiptValidationError(f"{name} must be a non-negative integer")
    return value


def _receipt_from_row(row: Sequence[Any]) -> _CommandReceipt:
    """Build the immutable receipt from one ``command_receipts`` row.

    The caller's SELECT defines the column order (txn_id, command_kind,
    idempotency_key, request_hash, project_id, first_project_seq,
    last_project_seq, event_ids_json, result_json, created_at). Corrupt
    stored JSON surfaces as a typed :class:`ReceiptValidationError` so a
    broken row can never produce a partially valid receipt.
    """
    try:
        event_ids = parse_json(row[7])
        result = parse_json(row[8])
    except CanonicalizationError as exc:
        raise ReceiptValidationError(f"corrupt stored receipt row: {exc}") from exc
    if not isinstance(event_ids, (list, tuple)):
        raise ReceiptValidationError("stored event_ids_json is not a JSON array")
    return _CommandReceipt(
        receipt_id=row[0],
        command_kind=row[1],
        idempotency_key=row[2],
        request_hash=row[3],
        project_id=row[4],
        project_seq=(int(row[5]), int(row[6])),
        event_ids=tuple(event_ids),
        result=result,
        created_at=row[9],
    )


# ---------------------------------------------------------------------------
# Receipt service
# ---------------------------------------------------------------------------


class ReceiptService:
    """Idempotency gate and persistence for ``command_receipts`` rows.

    Stateless: every operation receives the active
    :class:`astrid.core.store.uow.UnitOfWork` and runs inside its
    transaction. A single service instance is safe to share across
    concurrent command callers.
    """

    def check(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        idempotency_key: str,
        request_hash: str,
        command_kind: str,
    ) -> Any | None:
        """Command-start idempotency check inside the active unit of work.

        Returns the stored complete result (parsed from ``result_json``)
        when a receipt exists for the same project/key/hash/kind; raises
        :class:`ReceiptMismatchError` when the key exists but the hash or
        kind differs; and returns ``None`` when no receipt exists yet.

        This method performs only a read, so the caller can rely on it as
        the first step of a command: a mismatch or replay decision happens
        before any sequence allocation or projection change.
        """
        _require_non_empty_string("project_id", project_id)
        _require_non_empty_string("idempotency_key", idempotency_key)
        _require_non_empty_string("request_hash", request_hash)
        _require_non_empty_string("command_kind", command_kind)
        receipt = uow.find_receipt(project_id, idempotency_key)
        if receipt is None:
            return None
        stored_hash = receipt["request_hash"]
        stored_kind = receipt["command_kind"]
        if stored_hash != request_hash or stored_kind != command_kind:
            raise ReceiptMismatchError(
                project_id=project_id,
                idempotency_key=idempotency_key,
                stored_request_hash=stored_hash,
                attempted_request_hash=request_hash,
                stored_command_kind=stored_kind,
                attempted_command_kind=command_kind,
            )
        return parse_json(receipt["result_json"])

    def record(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        idempotency_key: str,
        request_hash: str,
        command_kind: str,
        txn_id: str,
        first_project_seq: int,
        last_project_seq: int,
        event_ids: Sequence[str],
        result: Any,
        primary_stream_id: str | None = None,
        resulting_stream_seq: int | None = None,
        created_at: str | None = None,
    ) -> None:
        """Persist one complete command receipt in the active transaction.

        Stores the transaction ID, primary stream and resulting sequence,
        the exact ``[first_project_seq, last_project_seq]`` range, the
        ordered event IDs, and the complete result JSON. All values are
        serialized canonically and validated before the insert, so a bad
        receipt can never be half-written.
        """
        _require_non_empty_string("project_id", project_id)
        _require_non_empty_string("idempotency_key", idempotency_key)
        _require_non_empty_string("request_hash", request_hash)
        _require_non_empty_string("command_kind", command_kind)
        _require_non_empty_string("txn_id", txn_id)
        first_seq = _require_positive_int("first_project_seq", first_project_seq)
        last_seq = _require_positive_int("last_project_seq", last_project_seq)
        if last_seq < first_seq:
            raise ReceiptValidationError(
                "last_project_seq must be >= first_project_seq "
                f"({first_seq} vs {last_seq})"
            )
        if primary_stream_id is not None:
            _require_non_empty_string("primary_stream_id", primary_stream_id)
        if resulting_stream_seq is not None:
            _require_non_negative_int(
                "resulting_stream_seq", resulting_stream_seq
            )
        for event_id in event_ids:
            _require_non_empty_string("event_ids entry", event_id)
        if created_at is None:
            created_at = utc_now_iso()
        else:
            _require_non_empty_string("created_at", created_at)
        try:
            event_ids_json = canonical_json(list(event_ids))
            result_json = canonical_json(result)
        except CanonicalizationError as exc:
            raise ReceiptValidationError(
                f"cannot serialize receipt payload: {exc}"
            ) from exc
        uow.insert_receipt(
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            command_kind=command_kind,
            txn_id=txn_id,
            primary_stream_id=primary_stream_id,
            resulting_stream_seq=resulting_stream_seq,
            first_project_seq=first_seq,
            last_project_seq=last_seq,
            event_ids_json=event_ids_json,
            result_json=result_json,
            created_at=created_at,
        )

    # -- read-only committed-receipt lookup (m4 plan step 3, task T3) -----

    def lookup_committed(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        idempotency_key: str,
    ) -> _CommandReceipt | None:
        """Read-only committed-receipt lookup by ``(project_id, key)``.

        Runs exactly one SELECT on the caller's **read-only** connection
        (for example from :meth:`DatabaseWriter.read_only_connection`); no
        transaction is opened and no row is written, so the lookup is safe
        outside any unit of work and never mutates state. Returns the
        complete immutable :class:`CommandReceipt`, or ``None`` when no
        receipt is committed for the project/key pair.
        """
        _require_non_empty_string("project_id", project_id)
        _require_non_empty_string("idempotency_key", idempotency_key)
        row = conn.execute(
            "SELECT txn_id, command_kind, idempotency_key, request_hash, "
            "project_id, first_project_seq, last_project_seq, event_ids_json, "
            "result_json, created_at FROM command_receipts "
            "WHERE project_id = ? AND idempotency_key = ?",
            (project_id, idempotency_key),
        ).fetchone()
        return _receipt_from_row(row) if row is not None else None

    def finalize_result(
        self,
        writer: Any,
        *,
        project_id: str,
        idempotency_key: str,
        result: Any,
    ) -> None:
        """Finalize a synchronous command's result without new identity.

        Some SDK mutations commit an admission receipt before running a
        fenced local handler.  Once that handler completes synchronously,
        replace only ``result_json`` so the immutable receipt identity,
        request hash, event ids, and project sequence remain unchanged while
        replay exposes the terminal response rather than the admission
        snapshot.  This is deliberately not a new receipt or event.
        """
        _require_non_empty_string("project_id", project_id)
        _require_non_empty_string("idempotency_key", idempotency_key)
        try:
            encoded = canonical_json(result)
        except CanonicalizationError as exc:
            raise ReceiptValidationError(
                f"final receipt result must be bounded JSON: {exc}"
            ) from exc

        def _update(session: Any) -> None:
            cursor = session.execute(
                "UPDATE command_receipts SET result_json = ? "
                "WHERE project_id = ? AND idempotency_key = ?",
                (encoded, project_id, idempotency_key),
            )
            if cursor.rowcount != 1:
                raise ReceiptError(
                    f"cannot finalize missing receipt {idempotency_key!r}"
                )

        writer.submit(_update)

    def get_committed(
        self, conn: sqlite3.Connection, *, receipt_id: str
    ) -> _CommandReceipt | None:
        """Read-only lookup of one committed receipt by its receipt (txn) id.

        Same read-only contract as :meth:`lookup_committed`; returns the
        complete immutable receipt or ``None``.
        """
        _require_non_empty_string("receipt_id", receipt_id)
        row = conn.execute(
            "SELECT txn_id, command_kind, idempotency_key, request_hash, "
            "project_id, first_project_seq, last_project_seq, event_ids_json, "
            "result_json, created_at FROM command_receipts WHERE txn_id = ?",
            (receipt_id,),
        ).fetchone()
        return _receipt_from_row(row) if row is not None else None


__all__ = [
    "RECEIPT_SHAPE_KEYS",
    "ReceiptError",
    "ReceiptMismatchError",
    "ReceiptService",
    "ReceiptValidationError",
]
