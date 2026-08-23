"""Runaway repository: typed timing transitions FK-integrated with the run table.

The runaway pack's executable repository lives in this module
(``astrid/packs/runaway/repository.py``). It follows the kernel and
timeline/shots/reference shape — one writer transaction per command, typed
errors, frozen read models, transaction-free reads — over the frozen
one-table schema (``runaway_transitions``) FK-integrated with the kernel
``runs`` table.

``runaway_transitions`` schema (pack-owned migration 0001_initial):
  id TEXT PK, project_id TEXT FK CASCADE projects(id),
  run_id TEXT FK RESTRICT runs(id), task_id TEXT FK tasks(id) SET NULL,
  ordinal INT CHECK >=0, start_ms INT CHECK >=0, duration_ms INT CHECK >0,
  prompt TEXT CHECK length(trim(prompt))>0, metadata_json TEXT json_valid,
  created_at TEXT NOT NULL, UNIQUE(run_id,ordinal),
  UNIQUE(run_id,task_id) WHERE task_id NOT NULL,
  INDEX (project_id, run_id, ordinal).
  Composite FK (run_id, project_id) -> runs(id, project_id) RESTRICT
  reinforces same-project membership beyond the separate FKs.

Sharding: runs with >256 transitions use ``continue_run`` with globally
contiguous ordinals (run_id per shard). ``runaway_transitions`` handles
this by storing ``run_id`` per row; ordinals are globally contiguous
(e.g. 0..255 on run A, 256..299 on continuation run B), and the
repository validates per-run contiguity while allowing the first batch of a
new shard to start at any ordinal (so 256..299 is valid as the first batch
for the continuation run).

:meth:`RunawayRepository.create` inserts transitions in one UoW after the
run fan-out:

1. validates the frozen transition facts (non-empty trimmed prompt,
   ordinal/start/duration bounds, object metadata, same-project task
   membership) and runs the receipt idempotency gate first
   (key ``runaway:create:{run_id}``);
2. rejects missing project/run and overlapping or non-contiguous ordinals
   before any mutation;
3. atomically inserts the ``runaway_transitions`` rows (one ULID per row,
   canonical ``metadata_json``, normalized ``created_at``) and records the
   complete receipt — returning the immutable :class:`RunawayCreateReadModel`
   with ordered transition ids.

Reads are transaction-free on a separate read-only connection:
:meth:`list` returns the project's transitions in stable ordinal order
(optionally filtered to one run), and :meth:`show` returns one transition
by id. :meth:`get_by_ordinal` is the direct run+ordinal lookup.

The repository is stateless apart from the injected event and receipt services; every command
must run inside the caller's :class:`astrid.core.store.uow.UnitOfWork`,
and it never constructs a writer or opens a transaction.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
    parse_json,
    request_hash,
)
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.errors import RepositoryError
from astrid.core.store.uow import UnitOfWork
from astrid.core.util.time import utc_now_iso

RUNAWAY_CREATE_COMMAND_KIND = "runaway.create"
"""The runaway command kind that transition-create receipts are keyed on."""

RUNAWAY_CREATED_EVENT_KIND = "runaway.created"
"""Hash-chained event emitted for each atomically admitted transition batch."""

RUNAWAY_STREAM_TYPE = "runaway.transition_set"
"""One immutable transition-set stream per kernel run."""

MAX_RUNAWAY_PAGE_SIZE = 1_000
"""Hard upper bound for one editor-bridge transition page."""

# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class RunawayRepositoryError(RepositoryError):
    """Base error for the runaway repository family."""


class RunawayValidationError(RunawayRepositoryError):
    """Raised when a runaway argument violates a contract."""


class RunawayNotFoundError(RunawayRepositoryError):
    """Raised when a read targets a missing runaway transition or run."""

    def __init__(self, *, identifier: str, kind: str = "runaway") -> None:
        super().__init__(f"unknown {kind}: {identifier!r}")
        self.identifier = identifier
        self.kind = kind


class RunawayAlreadyExistsError(RunawayRepositoryError):
    """Raised when a transition identity collides within a run."""

    def __init__(self, *, run_id: str, ordinal: int | None = None, task_id: str | None = None) -> None:
        if task_id is not None:
            super().__init__(f"runaway transition task already exists: run {run_id!r} task {task_id!r}")
        elif ordinal is not None:
            super().__init__(f"runaway transition ordinal already exists: run {run_id!r} ordinal {ordinal}")
        else:
            super().__init__(f"runaway transition already exists for run {run_id!r}")
        self.run_id = run_id
        self.ordinal = ordinal
        self.task_id = task_id


# ---------------------------------------------------------------------------
# Frozen read models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunawayTransitionReadModel:
    """One immutable ``runaway_transitions`` row."""

    id: str
    project_id: str
    run_id: str
    task_id: str | None
    ordinal: int
    start_ms: int
    duration_ms: int
    prompt: str
    metadata: Mapping[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "ordinal": self.ordinal,
            "start_ms": self.start_ms,
            "duration_ms": self.duration_ms,
            "prompt": self.prompt,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RunawayTransitionReadModel:
        return cls(
            id=str(value["id"]),
            project_id=str(value["project_id"]),
            run_id=str(value["run_id"]),
            task_id=str(value["task_id"]) if value.get("task_id") is not None else None,
            ordinal=int(value["ordinal"]),
            start_ms=int(value["start_ms"]),
            duration_ms=int(value["duration_ms"]),
            prompt=str(value["prompt"]),
            metadata=dict(value.get("metadata") or {}),
            created_at=str(value["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class RunawayCreateReadModel:
    """One immutable runaway-create result (receipt-backed)."""

    run_id: str
    project_id: str
    transition_ids: tuple[str, ...]
    first_ordinal: int
    last_ordinal: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "transition_ids": list(self.transition_ids),
            "first_ordinal": self.first_ordinal,
            "last_ordinal": self.last_ordinal,
            "created_at": self.created_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RunawayCreateReadModel:
        return cls(
            run_id=str(value["run_id"]),
            project_id=str(value["project_id"]),
            transition_ids=tuple(str(x) for x in (value.get("transition_ids") or [])),
            first_ordinal=int(value["first_ordinal"]),
            last_ordinal=int(value["last_ordinal"]),
            created_at=str(value["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class RunawayTransitionPageReadModel:
    """One stable page from an insert-only Runaway snapshot.

    ``snapshot_rowid`` freezes the visible set across page requests. New rows
    admitted after the first page have larger SQLite rowids and therefore do
    not leak into the traversal. The opaque HTTP cursor is produced by the
    bridge adapter; the repository exposes only typed positioning facts.
    """

    transitions: tuple[RunawayTransitionReadModel, ...]
    snapshot_rowid: int
    total_count: int
    has_more: bool
    next_ordinal: int | None
    next_run_id: str | None
    next_id: str | None


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise RunawayValidationError(f"{name} must be a non-empty string")
    return value


def _require_non_negative_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RunawayValidationError(f"{name} must be a non-negative integer")
    return value




def _normalize_transition(index: int, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise RunawayValidationError(f"transitions[{index}] must be an object")
    # ordinal
    ordinal = raw.get("ordinal")
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
        raise RunawayValidationError(f"transitions[{index}].ordinal must be a non-negative integer")
    # start_ms
    start_ms = raw.get("start_ms")
    if isinstance(start_ms, bool) or not isinstance(start_ms, int) or start_ms < 0:
        raise RunawayValidationError(f"transitions[{index}].start_ms must be a non-negative integer")
    # duration_ms
    duration_ms = raw.get("duration_ms")
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or duration_ms <= 0:
        raise RunawayValidationError(f"transitions[{index}].duration_ms must be a positive integer")
    # prompt
    prompt = raw.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise RunawayValidationError(f"transitions[{index}].prompt must be a non-empty string")
    prompt = prompt.strip()
    # metadata
    metadata = raw.get("metadata", raw.get("metadata_json", {}))
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, Mapping):
        raise RunawayValidationError(f"transitions[{index}].metadata must be an object")
    metadata = dict(metadata)
    # task_id
    task_id = raw.get("task_id")
    if task_id is not None and (not isinstance(task_id, str) or not task_id):
        raise RunawayValidationError(f"transitions[{index}].task_id must be a non-empty string or null")
    # id (optional)
    tid = raw.get("id")
    if tid is not None and (not isinstance(tid, str) or not tid):
        raise RunawayValidationError(f"transitions[{index}].id must be a non-empty string when provided")
    return {
        "ordinal": ordinal,
        "start_ms": start_ms,
        "duration_ms": duration_ms,
        "prompt": prompt,
        "metadata": metadata,
        "task_id": task_id,
        "id": tid,
    }


def _request_transition(normalized: Mapping[str, Any]) -> dict[str, Any]:
    """Request-identity representation (excludes generated id/created_at)."""
    entry: dict[str, Any] = {
        "ordinal": normalized["ordinal"],
        "start_ms": normalized["start_ms"],
        "duration_ms": normalized["duration_ms"],
        "prompt": normalized["prompt"],
        "metadata": dict(normalized["metadata"]),
    }
    if normalized["task_id"] is not None:
        entry["task_id"] = normalized["task_id"]
    return entry


def _row_to_model(row: sqlite3.Row) -> RunawayTransitionReadModel:
    try:
        metadata = parse_json(row["metadata_json"]) if row["metadata_json"] else {}
    except CanonicalizationError:
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return RunawayTransitionReadModel(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        run_id=str(row["run_id"]),
        task_id=str(row["task_id"]) if row["task_id"] is not None else None,
        ordinal=int(row["ordinal"]),
        start_ms=int(row["start_ms"]),
        duration_ms=int(row["duration_ms"]),
        prompt=str(row["prompt"]),
        metadata=metadata,
        created_at=str(row["created_at"]),
    )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class RunawayRepository:
    """Stateless runaway command surface over the kernel unit of work."""

    def __init__(self, receipts: ReceiptService, events: EventAppendService) -> None:
        self._receipts = receipts
        self._events = events

    # -- create (one UoW after run fan-out) --------------------------------

    def create(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        run_id: str,
        transitions: Sequence[Mapping[str, Any]],
        idempotency_key: str | None = None,
        created_at: str | None = None,
        command_kind: str = RUNAWAY_CREATE_COMMAND_KIND,
    ) -> RunawayCreateReadModel:
        """Insert runaway transitions for one run in one UoW.

        Validates prompt non-empty, ordinal contiguous, start/duration
        positive, and receipt idempotency (key ``runaway:create:{run_id}``).
        Inserts transitions atomically after the run fan-out and records the
        complete receipt. Sharded runs (>256 transitions) are handled by
        storing ``run_id`` per shard with globally contiguous ordinals.

        *transitions* is a JSON array of ``{ordinal, start_ms, duration_ms,
        prompt, metadata?, task_id?, id?}``. Ordinals must be contiguous
        within the batch and, when the run already has stored transitions,
        must continue contiguously from the existing max (no gaps or
        overlaps). ``task_id`` when provided must be same-project and unique
        per run.

        Returns the :class:`RunawayCreateReadModel` with ordered transition
        ids. Idempotency: identical retry under the same key returns the
        stored result with zero new rows; changed request under the same key
        raises ``ReceiptMismatchError``.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        run_id = _require_non_empty_string("run_id", run_id)
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if idempotency_key is None:
            idempotency_key = f"runaway:create:{run_id}"
        else:
            _require_non_empty_string("idempotency_key", idempotency_key)
        if isinstance(transitions, (str, bytes)) or not isinstance(transitions, Sequence):
            raise RunawayValidationError("transitions must be a JSON array")
        if not transitions:
            raise RunawayValidationError("transitions must contain at least one entry")
        normalized = tuple(_normalize_transition(i, t) for i, t in enumerate(transitions))

        # Ordinal contiguous within batch (sorted unique step 1).
        ordinals = sorted(n["ordinal"] for n in normalized)
        if len(ordinals) != len(set(ordinals)):
            raise RunawayValidationError("transitions ordinals must be unique")
        for idx in range(1, len(ordinals)):
            if ordinals[idx] != ordinals[idx - 1] + 1:
                raise RunawayValidationError(
                    f"transitions ordinals must be contiguous: gap between {ordinals[idx-1]} and {ordinals[idx]}"
                )
        # task_id unique within batch where not null
        task_ids_in_batch = [n["task_id"] for n in normalized if n["task_id"] is not None]
        if len(task_ids_in_batch) != len(set(task_ids_in_batch)):
            raise RunawayValidationError("transitions task_id must be unique per run")

        # Validate metadata can be canonicalized early.
        for n in normalized:
            try:
                canonical_json(n["metadata"])
            except CanonicalizationError as exc:
                raise RunawayValidationError(f"cannot canonicalize metadata for ordinal {n['ordinal']}: {exc}") from exc

        # Semantic request identity (excludes generated id/created_at).
        request: dict[str, Any] = {
            "project_id": project_id,
            "run_id": run_id,
            "transitions": [_request_transition(n) for n in sorted(normalized, key=lambda x: x["ordinal"])],
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise RunawayValidationError(f"cannot hash runaway request: {exc}") from exc

        # Idempotency gate first.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return RunawayCreateReadModel.from_mapping(replayed)

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise RunawayValidationError("created_at must be a non-empty string")
        txn_id = uuid.uuid4().hex

        # Project must exist.
        if uow.query_one("SELECT id FROM projects WHERE id = ?", (project_id,)) is None:
            raise RunawayValidationError(f"runaway create requires an existing project: {project_id!r}")

        # Run must exist and belong to project (FK also enforces, but typed error first).
        run_row = uow.query_one("SELECT id, project_id FROM runs WHERE id = ?", (run_id,))
        if run_row is None:
            raise RunawayNotFoundError(identifier=run_id, kind="run")
        if str(run_row["project_id"]) != project_id:
            raise RunawayValidationError(f"run {run_id!r} does not belong to project {project_id!r}")

        # Existing max ordinal for this run (per-run contiguity).
        max_row = uow.query_one(
            "SELECT MAX(ordinal) AS max_ordinal FROM runaway_transitions WHERE run_id = ?",
            (run_id,),
        )
        existing_max = int(max_row["max_ordinal"]) if max_row is not None and max_row["max_ordinal"] is not None else None
        batch_min = min(ordinals)
        batch_max = max(ordinals)
        if existing_max is not None:
            if batch_min != existing_max + 1:
                raise RunawayValidationError(
                    f"transitions ordinals must be contiguous with existing run data: "
                    f"run {run_id!r} has transitions through ordinal {existing_max}, "
                    f"so the next batch must start at {existing_max + 1}, got {batch_min}"
                )
            # Also check no overlap (already covered by start check, but UNIQUE would fire anyway).
        # Check existing task_ids for this run to enforce UNIQUE(run_id,task_id) before INSERT.
        if task_ids_in_batch:
            placeholders = ",".join("?" for _ in task_ids_in_batch)
            existing_task_rows = uow.query(
                f"SELECT task_id FROM runaway_transitions WHERE run_id = ? AND task_id IN ({placeholders})",
                (run_id, *task_ids_in_batch),
            )
            if existing_task_rows:
                dup = str(existing_task_rows[0]["task_id"])
                raise RunawayAlreadyExistsError(run_id=run_id, task_id=dup)
            # Also verify each task_id exists and belongs to same project/run if provided.
            for tid in task_ids_in_batch:
                task_row = uow.query_one("SELECT id, project_id, run_id FROM tasks WHERE id = ?", (tid,))
                if task_row is None:
                    raise RunawayValidationError(f"transitions task_id {tid!r} does not exist")
                if str(task_row["project_id"]) != project_id:
                    raise RunawayValidationError(f"transitions task_id {tid!r} does not belong to project {project_id!r}")
                # Optionally enforce same run; relax if task run_id is null or different (allow cross-run task refs).
                # We keep it permissive: task must be same project, not necessarily same run.

        # Insert rows in ordinal order.
        sorted_normalized = sorted(normalized, key=lambda x: x["ordinal"])
        inserted_ids: list[str] = []
        for n in sorted_normalized:
            tid = n["id"] if n["id"] is not None else generate_lowercase_ulid()
            # Duplicate id check before INSERT.
            if uow.query_one("SELECT id FROM runaway_transitions WHERE id = ?", (tid,)) is not None:
                raise RunawayAlreadyExistsError(run_id=run_id, ordinal=n["ordinal"])
            try:
                metadata_json = canonical_json(n["metadata"])
            except CanonicalizationError as exc:
                raise RunawayValidationError(f"cannot canonicalize metadata for ordinal {n['ordinal']}: {exc}") from exc
            try:
                uow.execute(
                    "INSERT INTO runaway_transitions "
                    "(id, project_id, run_id, task_id, ordinal, start_ms, duration_ms, prompt, metadata_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        tid,
                        project_id,
                        run_id,
                        n["task_id"],
                        n["ordinal"],
                        n["start_ms"],
                        n["duration_ms"],
                        n["prompt"],
                        metadata_json,
                        stamp,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                msg = str(exc).lower()
                if "unique" in msg and "ordinal" in msg:
                    raise RunawayAlreadyExistsError(run_id=run_id, ordinal=n["ordinal"]) from exc
                if "unique" in msg and "task_id" in msg:
                    raise RunawayAlreadyExistsError(run_id=run_id, task_id=str(n["task_id"])) from exc
                if "foreign key" in msg:
                    raise RunawayValidationError(f"foreign key violation for ordinal {n['ordinal']}: {exc}") from exc
                if "check" in msg:
                    raise RunawayValidationError(f"check constraint failed for ordinal {n['ordinal']}: {exc}") from exc
                raise
            inserted_ids.append(tid)

        result = RunawayCreateReadModel(
            run_id=run_id,
            project_id=project_id,
            transition_ids=tuple(inserted_ids),
            first_ordinal=batch_min,
            last_ordinal=batch_max,
            created_at=stamp,
        )
        stream_id = f"{run_id}:{RUNAWAY_STREAM_TYPE}"
        stream_row = uow.query_one(
            "SELECT id FROM event_streams WHERE id = ?", (stream_id,)
        )
        if stream_row is None:
            uow.execute(
                "INSERT INTO event_streams "
                "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (stream_id, project_id, RUNAWAY_STREAM_TYPE, run_id, stamp),
            )
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=RUNAWAY_CREATED_EVENT_KIND,
            data={
                "run_id": run_id,
                "transition_ids": list(inserted_ids),
                "first_ordinal": batch_min,
                "last_ordinal": batch_max,
            },
            changes=["transition_ids", "first_ordinal", "last_ordinal"],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind="local",
            command_kind=command_kind,
            created_at=stamp,
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

    # -- transaction-free reads --------------------------------------------

    def list(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        run_id: str | None = None,
    ) -> tuple[RunawayTransitionReadModel, ...]:
        """List transitions for a project, optionally filtered to one run.

        Results are ordered by ``ordinal`` then ``id`` (stable contiguous
        order). This is the transaction-free read used after the UoW commit.
        """
        _require_non_empty_string("project_id", project_id)
        if run_id is not None:
            _require_non_empty_string("run_id", run_id)
            rows = conn.execute(
                "SELECT * FROM runaway_transitions WHERE project_id = ? AND run_id = ? ORDER BY ordinal ASC, id ASC",
                (project_id, run_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM runaway_transitions WHERE project_id = ? ORDER BY ordinal ASC, id ASC",
                (project_id,),
            ).fetchall()
        return tuple(_row_to_model(row) for row in rows)

    def list_page(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        run_id: str | None = None,
        limit: int = 250,
        snapshot_rowid: int | None = None,
        after_ordinal: int | None = None,
        after_run_id: str | None = None,
        after_id: str | None = None,
    ) -> RunawayTransitionPageReadModel:
        """List one bounded, repeatable page in ``ordinal/run/id`` order.

        The first call captures the maximum visible SQLite rowid. Subsequent
        calls pass that value back from their cursor, so concurrent appends do
        not change the result set mid-traversal. All cursor position fields
        are either present together or absent together.
        """

        project_id = _require_non_empty_string("project_id", project_id)
        if run_id is not None:
            run_id = _require_non_empty_string("run_id", run_id)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_RUNAWAY_PAGE_SIZE:
            raise RunawayValidationError(
                f"limit must be an integer between 1 and {MAX_RUNAWAY_PAGE_SIZE}"
            )
        if snapshot_rowid is not None and (
            isinstance(snapshot_rowid, bool)
            or not isinstance(snapshot_rowid, int)
            or snapshot_rowid < 0
        ):
            raise RunawayValidationError("snapshot_rowid must be a non-negative integer")
        position = (after_ordinal, after_run_id, after_id)
        if any(value is not None for value in position) and not all(
            value is not None for value in position
        ):
            raise RunawayValidationError("page cursor position is incomplete")
        if after_ordinal is not None:
            _require_non_negative_int("after_ordinal", after_ordinal)
            _require_non_empty_string("after_run_id", after_run_id)
            _require_non_empty_string("after_id", after_id)

        scope_sql = "project_id = ?"
        scope_params: list[Any] = [project_id]
        if run_id is not None:
            scope_sql += " AND run_id = ?"
            scope_params.append(run_id)

        if snapshot_rowid is None:
            snapshot = conn.execute(
                f"SELECT COALESCE(MAX(rowid), 0) AS snapshot_rowid "
                f"FROM runaway_transitions WHERE {scope_sql}",
                tuple(scope_params),
            ).fetchone()
            snapshot_rowid = int(snapshot["snapshot_rowid"] if isinstance(snapshot, sqlite3.Row) else snapshot[0])

        where_sql = f"{scope_sql} AND rowid <= ?"
        params: list[Any] = [*scope_params, snapshot_rowid]
        if after_ordinal is not None:
            where_sql += (
                " AND (ordinal > ? OR (ordinal = ? AND run_id > ?) "
                "OR (ordinal = ? AND run_id = ? AND id > ?))"
            )
            params.extend(
                [
                    after_ordinal,
                    after_ordinal,
                    after_run_id,
                    after_ordinal,
                    after_run_id,
                    after_id,
                ]
            )

        rows = conn.execute(
            f"SELECT * FROM runaway_transitions WHERE {where_sql} "
            "ORDER BY ordinal ASC, run_id ASC, id ASC LIMIT ?",
            (*params, limit + 1),
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) AS total_count FROM runaway_transitions "
            f"WHERE {scope_sql} AND rowid <= ?",
            (*scope_params, snapshot_rowid),
        ).fetchone()
        total_count = int(total["total_count"] if isinstance(total, sqlite3.Row) else total[0])
        has_more = len(rows) > limit
        visible = rows[:limit]
        models = tuple(_row_to_model(row) for row in visible)
        if has_more and models:
            last = models[-1]
            next_ordinal = last.ordinal
            next_run_id = last.run_id
            next_id = last.id
        else:
            next_ordinal = next_run_id = next_id = None
        return RunawayTransitionPageReadModel(
            transitions=models,
            snapshot_rowid=snapshot_rowid,
            total_count=total_count,
            has_more=has_more,
            next_ordinal=next_ordinal,
            next_run_id=next_run_id,
            next_id=next_id,
        )

    def show(
        self,
        conn: sqlite3.Connection,
        *,
        id: str,
    ) -> RunawayTransitionReadModel:
        """Return one transition by its ``id`` or raise."""
        _require_non_empty_string("id", id)
        row = conn.execute("SELECT * FROM runaway_transitions WHERE id = ?", (id,)).fetchone()
        if row is None:
            raise RunawayNotFoundError(identifier=id, kind="runaway_transition")
        return _row_to_model(row)

    def get_by_ordinal(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: str,
        ordinal: int,
    ) -> RunawayTransitionReadModel:
        """Return one transition by ``(run_id, ordinal)`` or raise."""
        _require_non_empty_string("run_id", run_id)
        _require_non_negative_int("ordinal", ordinal)
        row = conn.execute(
            "SELECT * FROM runaway_transitions WHERE run_id = ? AND ordinal = ?",
            (run_id, ordinal),
        ).fetchone()
        if row is None:
            raise RunawayNotFoundError(identifier=f"{run_id}:{ordinal}", kind="runaway_transition")
        return _row_to_model(row)

    def get_by_task(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: str,
        task_id: str,
    ) -> RunawayTransitionReadModel:
        """Return one transition by ``(run_id, task_id)`` or raise."""
        _require_non_empty_string("run_id", run_id)
        _require_non_empty_string("task_id", task_id)
        row = conn.execute(
            "SELECT * FROM runaway_transitions WHERE run_id = ? AND task_id = ?",
            (run_id, task_id),
        ).fetchone()
        if row is None:
            raise RunawayNotFoundError(identifier=task_id, kind="runaway_transition")
        return _row_to_model(row)


__all__ = [
    "RUNAWAY_CREATE_COMMAND_KIND",
    "RUNAWAY_CREATED_EVENT_KIND",
    "RUNAWAY_STREAM_TYPE",
    "RunawayAlreadyExistsError",
    "RunawayCreateReadModel",
    "RunawayNotFoundError",
    "RunawayRepository",
    "RunawayRepositoryError",
    "RunawayTransitionPageReadModel",
    "RunawayTransitionReadModel",
    "RunawayValidationError",
    "MAX_RUNAWAY_PAGE_SIZE",
]
