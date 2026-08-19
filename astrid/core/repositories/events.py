"""Read-only ordered event repository (m4 plan step 4, task T4).

The event log is the single ordered record of every committed command.
:class:`EventRepository` exposes **read-only, transaction-free** reads over
the caller's one :class:`~astrid.core.store.writer.DatabaseWriter`:

- reads run on the writer's separate read-only connection (never the write
  connection, never inside a transaction), so the repository can never
  mutate state and never contends with the writer queue;
- events are returned in deterministic order — global ``project_seq`` order
  (with ``seq`` as the tie-breaker), or ``seq`` order within one stream;
- every event is unwrapped from its canonical SD2 integrity envelope into
  the immutable :class:`EventReadModel`: domain ``data`` plus the
  ``event_hash`` / ``previous_event_hash`` chain fields.

The repository adds **no table and no column**: it issues ``SELECT`` only
against the frozen v10 ``events`` table, and it never imports a pack, so
the kernel composition it serves stays pack-independent. Dynamic discovery
is prohibited by construction — the module imports exactly the kernel
modules it reads.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Mapping

from astrid.core.events.service import (
    DATA_KEY,
    EVENT_HASH_KEY,
    INTEGRITY_KEY,
    PREVIOUS_EVENT_HASH_KEY,
)
from astrid.core.receipts.canonical import CanonicalizationError, parse_json
from astrid.core.repositories.errors import RepositoryError
from astrid.core.store.writer import DatabaseWriter

MAX_EVENT_READ_LIMIT = 10_000
"""Upper bound for one ordered event read (bounded reads, no unbounded scans)."""

DEFAULT_EVENT_READ_LIMIT = 1_000
"""Default row limit for :meth:`EventRepository.list_events`."""

_EVENT_SELECT = (
    "SELECT event_id, project_id, project_seq, stream_id, seq, subject_type, "
    "subject_id, changes_json, kind, schema_version, idempotency_key, txn_id, "
    "actor_kind, payload_json, created_at FROM events"
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EventRepositoryError(RepositoryError):
    """Base error for read-only event-log reads."""


class EventNotFoundError(EventRepositoryError):
    """Raised when a read targets an event id with no ``events`` row."""

    def __init__(self, *, event_id: str) -> None:
        self.event_id: str = event_id
        super().__init__(f"unknown event: {event_id!r}")


class EventReadError(EventRepositoryError):
    """Raised when a stored event cannot be parsed into a read model.

    Covers malformed ``changes_json``/``payload_json`` and payloads missing
    the canonical SD2 integrity envelope. Read-only: a corrupt row surfaces
    as a typed error and is never silently half-parsed.
    """


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise EventReadError(f"{name} must be a non-empty string")
    return value


def _require_limit(limit: Any) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise EventReadError("limit must be a positive integer")
    return min(limit, MAX_EVENT_READ_LIMIT)


# ---------------------------------------------------------------------------
# Read model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EventReadModel:
    """Immutable read-only view of one committed event.

    ``data`` is the domain payload unwrapped from the canonical SD2
    integrity envelope; ``event_hash`` and ``previous_event_hash`` are the
    chain fields from the same envelope. Every field is frozen, so the
    model is safe to share and serialize.
    """

    event_id: str
    project_id: str
    project_seq: int
    stream_id: str
    seq: int
    subject_type: str
    subject_id: str
    changes: tuple[str, ...]
    kind: str
    schema_version: int
    idempotency_key: str
    txn_id: str
    actor_kind: str
    data: Mapping[str, Any]
    event_hash: str
    previous_event_hash: str | None
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        """Return the read model as a plain JSON-ready mapping."""
        return {
            "event_id": self.event_id,
            "project_id": self.project_id,
            "project_seq": self.project_seq,
            "stream_id": self.stream_id,
            "seq": self.seq,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "changes": list(self.changes),
            "kind": self.kind,
            "schema_version": self.schema_version,
            "idempotency_key": self.idempotency_key,
            "txn_id": self.txn_id,
            "actor_kind": self.actor_kind,
            "data": dict(self.data),
            "event_hash": self.event_hash,
            "previous_event_hash": self.previous_event_hash,
            "created_at": self.created_at,
        }


def _read_model_from_row(row: Mapping[str, Any]) -> EventReadModel:
    """Build one immutable read model from an ``events`` row.

    Parses the canonical JSON columns and unwraps the SD2 envelope; any
    malformed stored value raises :class:`EventReadError`.
    """
    try:
        changes = parse_json(row["changes_json"])
        payload = parse_json(row["payload_json"])
    except CanonicalizationError as exc:
        raise EventReadError(f"corrupt event row {row['event_id']!r}: {exc}") from exc
    if not isinstance(changes, (list, tuple)):
        raise EventReadError(
            f"event {row['event_id']!r} changes_json is not a JSON array"
        )
    if not isinstance(payload, Mapping):
        raise EventReadError(
            f"event {row['event_id']!r} payload_json is not a JSON object"
        )
    if not isinstance(payload.get(DATA_KEY), Mapping):
        raise EventReadError(
            f"event {row['event_id']!r} payload is missing the {DATA_KEY!r} envelope"
        )
    integrity = payload.get(INTEGRITY_KEY)
    if not isinstance(integrity, Mapping):
        raise EventReadError(
            f"event {row['event_id']!r} payload is missing the "
            f"{INTEGRITY_KEY!r} envelope"
        )
    event_hash = integrity.get(EVENT_HASH_KEY)
    if not isinstance(event_hash, str) or not event_hash:
        raise EventReadError(
            f"event {row['event_id']!r} payload is missing {EVENT_HASH_KEY!r}"
        )
    previous_event_hash = integrity.get(PREVIOUS_EVENT_HASH_KEY)
    if previous_event_hash is not None and not isinstance(previous_event_hash, str):
        raise EventReadError(
            f"event {row['event_id']!r} {PREVIOUS_EVENT_HASH_KEY!r} is not a string"
        )
    return EventReadModel(
        event_id=row["event_id"],
        project_id=row["project_id"],
        project_seq=int(row["project_seq"]),
        stream_id=row["stream_id"],
        seq=int(row["seq"]),
        subject_type=row["subject_type"],
        subject_id=row["subject_id"],
        changes=tuple(changes),
        kind=row["kind"],
        schema_version=int(row["schema_version"]),
        idempotency_key=row["idempotency_key"],
        txn_id=row["txn_id"],
        actor_kind=row["actor_kind"],
        data=dict(payload[DATA_KEY]),
        event_hash=event_hash,
        previous_event_hash=previous_event_hash,
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# The read-only event repository
# ---------------------------------------------------------------------------


class EventRepository:
    """Read-only, transaction-free ordered event reads over one writer.

    Stateless apart from the single :class:`DatabaseWriter` it reads
    through; one instance is safe to share across callers. Every read runs
    on the writer's separate read-only connection — no transaction is
    opened and no row is written — so the repository never mutates state
    and never needs a unit of work.
    """

    def __init__(self, writer: DatabaseWriter) -> None:
        self._writer = writer

    def get_event(self, event_id: str) -> EventReadModel | None:
        """Return one event by its event id, or ``None`` when unknown."""
        _require_non_empty_string("event_id", event_id)
        with self._writer.read_only_connection() as conn:
            conn.row_factory = _row_factory
            row = conn.execute(
                _EVENT_SELECT + " WHERE event_id = ?", (event_id,)
            ).fetchone()
        return _read_model_from_row(row) if row is not None else None

    def list_events(
        self,
        *,
        project_id: str | None = None,
        stream_id: str | None = None,
        after_project_seq: int | None = None,
        limit: int = DEFAULT_EVENT_READ_LIMIT,
    ) -> tuple[EventReadModel, ...]:
        """Return committed events in deterministic order.

        Global reads (no filters) and project reads order by
        ``project_seq`` (ascending, ``seq`` as tie-breaker); stream reads
        order by ``seq`` ascending. ``after_project_seq`` resumes a global
        or project read strictly after one sequence; ``limit`` bounds the
        result and is capped at :data:`MAX_EVENT_READ_LIMIT`. A
        ``stream_id`` read ignores ``after_project_seq``.
        """
        bound = _require_limit(limit)
        clauses: list[str] = []
        parameters: list[Any] = []
        if project_id is not None:
            _require_non_empty_string("project_id", project_id)
            clauses.append("project_id = ?")
            parameters.append(project_id)
        if stream_id is not None:
            _require_non_empty_string("stream_id", stream_id)
            clauses.append("stream_id = ?")
            parameters.append(stream_id)
        if after_project_seq is not None:
            if isinstance(after_project_seq, bool) or not isinstance(
                after_project_seq, int
            ):
                raise EventReadError("after_project_seq must be an integer")
            clauses.append("project_seq > ?")
            parameters.append(after_project_seq)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        order = (
            " ORDER BY seq ASC"
            if stream_id is not None
            else " ORDER BY project_seq ASC, seq ASC"
        )
        parameters.append(bound)
        sql = f"{_EVENT_SELECT}{where}{order} LIMIT ?"
        with self._writer.read_only_connection() as conn:
            conn.row_factory = _row_factory
            rows = conn.execute(sql, tuple(parameters)).fetchall()
        return tuple(_read_model_from_row(row) for row in rows)


def _row_factory(cursor: Any, row: tuple[Any, ...]) -> sqlite3.Row:
    """sqlite3.Row factory: address columns by name in read models."""
    return sqlite3.Row(cursor, row)


__all__ = [
    "DEFAULT_EVENT_READ_LIMIT",
    "EventNotFoundError",
    "EventReadError",
    "EventReadModel",
    "EventRepository",
    "EventRepositoryError",
    "MAX_EVENT_READ_LIMIT",
]
