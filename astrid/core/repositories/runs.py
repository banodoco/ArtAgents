"""Run repository: one-transaction bounded direct-child fan-out and derived
group operations (m2 plan steps 12 and 13).

:class:`RunRepository.create` is the run vertical's fan-out root: one writer
transaction commits the ``core.run`` event stream and ``runs`` row, then up
to ``FROZEN_MAX_DIRECT_CHILDREN`` (256) direct child ``core.task`` streams and
``tasks`` rows with stable ``run_ordinal`` values, the resolved same-project
acyclic dependency edges, ordered events (the ``core.run.created`` event
first, then each child's ``core.task.created`` event in ordinal order), both
heads, and **one** complete receipt carrying every ordered event id.

Plan step 13 (T22) adds the group surface on top of that fan-out:

- :meth:`RunRepository.derive_progress` derives ordered group progress from
  the child ``tasks`` rows by ``run_ordinal`` — no cursor, no parent task,
  and no persisted mutable progress aggregate (the single shared derivation
  ``derive_run_progress_counts`` in the task repository also backs task
  completion's parent-run recompute);
- :meth:`RunRepository.cancel` is a receipt-protected group cancel that
  drives every eligible queued/blocked child to the terminal ``cancelled``
  state through the **shared task-cancel predicate**
  (:meth:`TaskRepository.cancel`), skips already-terminal and running
  children (a running child's owned attempt needs its executor's fence),
  recomputes the run projection, appends ``core.run.cancelled``, and
  records one run-level receipt;
- :meth:`RunRepository.retry` is a receipt-protected group retry that
  restarts all eligible children — or an explicit subset — through the
  **shared task-retry predicate** (:meth:`TaskRepository.retry`) with the
  shared read-only eligibility check (:meth:`TaskRepository.is_retry_eligible`),
  recomputes the run projection, appends ``core.run.retried``, and records
  one run-level receipt;
- both group commands reject continuation of a terminal run
  (:class:`RunTerminalError`) before any mutation.

Contracts kept here (v10 section 5.2; m2 plan steps 12 and 13):

- **Bounded fan-out.** ``children`` with more than 256 entries is rejected
  before any mutation (``RunValidationError``), so a child 257 can never
  consume a sequence or create a row. The result's ``evidence_ids`` is the
  empty tuple: fan-out creates no evidence, no parent task, and no step
  record (there is no step table at all).
- **Stable ordinals.** Each child's ``run_ordinal`` is its index in the
  submitted set (``0..len(children)-1``), backed by the unique
  ``tasks_run_ordinal`` index; the result returns the ordered task ids and
  the ``[first_ordinal, last_ordinal]`` range.
- **Same-project acyclic dependencies.** Children reuse the task repository's
  frozen dependency rules: each child's declared edges are normalized and
  validated (existence, same-project ownership, no self or duplicate edges,
  and cycle detection) against the tasks visible at that child's creation —
  the earlier children of the same fan-out plus pre-existing project tasks.
  Because children are created in ordinal order, a dependency may reference
  any earlier child or any pre-existing task; a reference to a later child
  is a typed ``TaskDependencyError`` (``missing``), which keeps the resolved
  child graph acyclic by construction.
- **Pure continuation validation.** :meth:`RunRepository.validate_continuation_envelope`
  validates the frozen continuation-envelope fields and ordinal/maximum
  rules **without any transaction, run-head CAS allocation, or terminal
  extension logic** — m2 validates but never executes continuation chunks
  (plan step 12 item 4; the m3 bridge).

The repository is stateless apart from the event append and receipt
services; every command must run inside the caller's
:class:`astrid.core.store.uow.UnitOfWork`.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
    parse_json,
    request_hash,
)
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.errors import ACTOR_KINDS, RepositoryError
from astrid.core.repositories.tasks import (
    CORE_TASK_CANCEL_COMMAND_KIND,
    CORE_TASK_CREATE_COMMAND_KIND,
    CORE_TASK_CREATED_EVENT_KIND,
    CORE_TASK_RETRY_COMMAND_KIND,
    CORE_TASK_STREAM_TYPE,
    DEFAULT_LEASE_SECONDS,
    TaskDependencyReadModel,
    TaskRepository,
    _initial_status_from_dependencies,
    _normalize_dependencies,
    _validate_dependency_graph,
    compute_spec_hash,
    derive_run_progress_counts,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.util.time import utc_now_iso

CORE_RUN_STREAM_TYPE = "core.run"
"""The kernel stream type every run aggregate owns (one per run row)."""

CORE_RUN_CREATED_EVENT_KIND = "core.run.created"
"""The m2 event kind emitted by one-transaction fan-out creation."""

CORE_RUN_CREATE_COMMAND_KIND = "core.run.create"
"""The m2 command kind that fan-out receipts are keyed on."""

CORE_RUN_CANCELLED_EVENT_KIND = "core.run.cancelled"
"""The m2 event kind emitted by receipt-protected group cancellation."""

CORE_RUN_CANCEL_COMMAND_KIND = "core.run.cancel"
"""The m2 command kind that group-cancel receipts are keyed on."""

CORE_RUN_RETRIED_EVENT_KIND = "core.run.retried"
"""The m2 event kind emitted by receipt-protected group retry."""

CORE_RUN_RETRY_COMMAND_KIND = "core.run.retry"
"""The m2 command kind that group-retry receipts are keyed on."""

RUN_STATUSES: tuple[str, ...] = ("running", "succeeded", "failed", "cancelled")
"""The frozen ``runs.status`` DDL CHECK vocabulary, in DDL order."""

FROZEN_MAX_DIRECT_CHILDREN = 256
"""The frozen at-most-256 direct-child bound (m2 plan step 12).

A fan-out with 257 children is rejected before any mutation, and a
continuation envelope's ordinal range must fit within ``0 .. 255`` with a
declared ``max_children`` of at most this bound.
"""

FROZEN_CONTINUATION_ENVELOPE_FIELDS: tuple[str, ...] = (
    "run_id",
    "project_id",
    "start_ordinal",
    "end_ordinal",
    "max_children",
)
"""The frozen continuation-envelope field set (m2 plan step 12 item 4).

m2 validates these fields and their ordinal/maximum rules; it never
executes the envelope (no continuation transaction, run-head CAS
allocation, or terminal extension logic — that is the m3 bridge).
"""


class EventAppendPort(Protocol):
    def append(self, uow: UnitOfWork, **kwargs: object) -> Any:
        ...


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class RunRepositoryError(RepositoryError):
    """Base error for the run repository family."""


class RunValidationError(RunRepositoryError):
    """Raised when a fan-out argument violates a run contract."""


class RunAlreadyExistsError(RunRepositoryError):
    """Raised when fan-out targets an already-existing run id."""

    def __init__(self, *, run_id: str) -> None:
        self.run_id: str = run_id
        super().__init__(f"run already exists: {run_id!r}")


class RunNotFoundError(RunRepositoryError):
    """Raised when a read targets a run id with no runs row."""

    def __init__(self, *, run_id: str) -> None:
        self.run_id: str = run_id
        super().__init__(f"unknown run: {run_id!r}")


class RunTerminalError(RunRepositoryError):
    """Raised when a group command targets a terminal run.

    Terminal runs are immutable for group continuation (m2 plan step 13):
    neither group cancel nor group retry may drive children of a run that
    already reached ``succeeded``, ``failed``, or ``cancelled``. ``status``
    carries the frozen terminal run status that rejected the command.
    """

    def __init__(self, *, run_id: str, status: str) -> None:
        self.run_id: str = run_id
        self.status: str = status
        super().__init__(
            f"cannot continue terminal run {run_id!r} in status {status!r}"
        )


class ContinuationValidationError(RunValidationError):
    """Raised when a continuation envelope violates the frozen rules.

    ``field`` names the offending envelope field (``None`` for structural
    violations such as a non-object envelope); no write is ever attempted.
    """

    def __init__(self, *, field: str | None = None, detail: str) -> None:
        self.field: str | None = field
        where = f" field {field!r}" if field is not None else ""
        super().__init__(f"invalid continuation envelope{where}: {detail}")


# ---------------------------------------------------------------------------
# Frozen read models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunReadModel:
    """Immutable run read model (m2 plan step 12).

    A frozen projection of one ``runs`` row plus the parsed
    ``input_json``/``result_json`` and the project head at read time.
    Fan-out creates the run in ``running`` status; group operations (plan
    step 13, T22) derive progress and transition it.
    """

    id: str
    project_id: str
    kind: str
    status: str
    title: str | None
    input: Mapping[str, Any]
    result: Mapping[str, Any]
    started_at: str
    finished_at: str | None
    event_head_seq: int

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted in events and receipts."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "kind": self.kind,
            "status": self.status,
            "title": self.title,
            "input": dict(self.input),
            "result": dict(self.result),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "event_head_seq": self.event_head_seq,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RunReadModel:
        """Rebuild the frozen run read model from a stored mapping."""
        return cls(
            id=str(value["id"]),
            project_id=str(value["project_id"]),
            kind=str(value["kind"]),
            status=str(value["status"]),
            title=value.get("title"),
            input=dict(value.get("input") or {}),
            result=dict(value.get("result") or {}),
            started_at=str(value["started_at"]),
            finished_at=value.get("finished_at"),
            event_head_seq=int(value["event_head_seq"]),
        )


@dataclass(frozen=True, slots=True)
class RunFanOutReadModel:
    """One immutable fan-out result (m2 plan step 12).

    The receipt result of :meth:`RunRepository.create`: the run id, the
    ordered direct-child task ids (ordinal order), the ordinal range, and
    the empty evidence-id list. ``evidence_ids`` is always empty — fan-out
    creates no evidence rows, no parent task, and no step record.
    """

    run_id: str
    project_id: str
    task_ids: tuple[str, ...]
    first_ordinal: int
    last_ordinal: int
    evidence_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "task_ids": list(self.task_ids),
            "first_ordinal": self.first_ordinal,
            "last_ordinal": self.last_ordinal,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RunFanOutReadModel:
        """Rebuild the frozen fan-out read model from a stored mapping."""
        return cls(
            run_id=str(value["run_id"]),
            project_id=str(value["project_id"]),
            task_ids=tuple(str(task_id) for task_id in value["task_ids"]),
            first_ordinal=int(value["first_ordinal"]),
            last_ordinal=int(value["last_ordinal"]),
            evidence_ids=tuple(
                str(evidence_id) for evidence_id in (value.get("evidence_ids") or [])
            ),
        )


@dataclass(frozen=True, slots=True)
class RunProgressReadModel:
    """One immutable derived group-progress read (m2 plan step 13, T22).

    The run repository never persists a cursor or a mutable progress
    aggregate: every progress value is derived fresh from the child
    ``tasks`` rows, ordered by ``run_ordinal``. ``status`` is the derived
    run status under the single shared rule (``running`` until every child
    is terminal, then ``failed``/``cancelled``/``succeeded``), and
    ``ordered`` carries each child's ``(ordinal, task_id, status)`` in
    ordinal order so callers can observe hard/soft gating and partial
    failure without any step or plan abstraction.
    """

    run_id: str
    project_id: str
    status: str
    total_children: int
    succeeded: int
    failed: int
    cancelled: int
    ordered: tuple[tuple[int, str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict for callers, events, and receipts."""
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "status": self.status,
            "total_children": self.total_children,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "ordered": [
                {"ordinal": ordinal, "task_id": task_id, "status": status}
                for ordinal, task_id, status in self.ordered
            ],
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RunProgressReadModel:
        """Rebuild the frozen progress read model from a stored mapping."""
        ordered: list[tuple[int, str, str]] = []
        for entry in value.get("ordered") or []:
            ordered.append(
                (int(entry["ordinal"]), str(entry["task_id"]), str(entry["status"]))
            )
        return cls(
            run_id=str(value["run_id"]),
            project_id=str(value["project_id"]),
            status=str(value["status"]),
            total_children=int(value["total_children"]),
            succeeded=int(value["succeeded"]),
            failed=int(value["failed"]),
            cancelled=int(value["cancelled"]),
            ordered=tuple(ordered),
        )


@dataclass(frozen=True, slots=True)
class RunCancelReadModel:
    """One immutable group-cancel result (m2 plan step 13, T22).

    ``run`` is the recomputed ``runs.result_json`` projection
    (``total_children``/``succeeded``/``failed``/``cancelled``/``status``)
    persisted by the command, ``progress`` the full derived read,
    ``cancelled_task_ids`` the children the shared task-cancel predicate
    drove to the terminal ``cancelled`` state (ordinal order), and
    ``skipped_task_ids`` the children left untouched (already-terminal
    children, and running children whose owned attempt fence a group
    command cannot present). ``cancel_request_id`` is the one group-level
    request id shared by every cancelled child.
    """

    run: Mapping[str, Any]
    progress: RunProgressReadModel
    cancelled_task_ids: tuple[str, ...]
    skipped_task_ids: tuple[str, ...]
    cancel_request_id: str

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "run": dict(self.run),
            "progress": self.progress.to_dict(),
            "cancelled_task_ids": list(self.cancelled_task_ids),
            "skipped_task_ids": list(self.skipped_task_ids),
            "cancel_request_id": self.cancel_request_id,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RunCancelReadModel:
        """Rebuild the frozen cancel read model from a stored mapping."""
        return cls(
            run=dict(value["run"]),
            progress=RunProgressReadModel.from_mapping(value["progress"]),
            cancelled_task_ids=tuple(
                str(task_id) for task_id in value["cancelled_task_ids"]
            ),
            skipped_task_ids=tuple(
                str(task_id) for task_id in value["skipped_task_ids"]
            ),
            cancel_request_id=str(value["cancel_request_id"]),
        )


@dataclass(frozen=True, slots=True)
class RunRetryReadModel:
    """One immutable group-retry result (m2 plan step 13, T22).

    ``run`` is the recomputed ``runs.result_json`` projection persisted by
    the command, ``progress`` the full derived read, ``retried_task_ids``
    the children the shared task-retry predicate restarted (a brand-new
    fenced attempt each, ordinal order), and ``skipped_task_ids`` the
    ineligible children left untouched (terminal tasks, never-claimed
    work, running work, or exhausted attempt budgets — the same rules the
    shared predicate enforces, applied read-only before any transition).
    """

    run: Mapping[str, Any]
    progress: RunProgressReadModel
    retried_task_ids: tuple[str, ...]
    skipped_task_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "run": dict(self.run),
            "progress": self.progress.to_dict(),
            "retried_task_ids": list(self.retried_task_ids),
            "skipped_task_ids": list(self.skipped_task_ids),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RunRetryReadModel:
        """Rebuild the frozen retry read model from a stored mapping."""
        return cls(
            run=dict(value["run"]),
            progress=RunProgressReadModel.from_mapping(value["progress"]),
            retried_task_ids=tuple(
                str(task_id) for task_id in value["retried_task_ids"]
            ),
            skipped_task_ids=tuple(
                str(task_id) for task_id in value["skipped_task_ids"]
            ),
        )


@dataclass(frozen=True, slots=True)
class ContinuationEnvelope:
    """One validated, frozen continuation envelope (m2 plan step 12 item 4).

    The pure validator returns this immutable record; nothing executes it.
    ``start_ordinal``/``end_ordinal`` name the inclusive child-ordinal range
    of the next continuation chunk (within ``0 .. 255``) and
    ``max_children`` the chunk's declared bound (``1 .. 256``).
    """

    run_id: str
    project_id: str
    start_ordinal: int
    end_ordinal: int
    max_children: int


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise RunValidationError(f"{name} must be a non-empty string")
    return value


def _require_json_object(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RunValidationError(f"{name} must be a JSON object")
    return dict(value)


def _require_json_array(name: str, value: Any) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RunValidationError(f"{name} must be a JSON array")
    return list(value)


def _require_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RunValidationError(f"{name} must be an integer")
    return value


def _normalize_child(index: int, child: Any) -> dict[str, Any]:
    """Validate one child task definition and freeze it into a plain dict.

    The frozen child shape mirrors task admission (capability, spec,
    input_manifest, priority, available_at, max_attempts, optional stable
    task_id) plus the optional dependency edges. Generated values (a missing
    ``task_id``) are excluded from the request identity.
    """
    if not isinstance(child, Mapping):
        raise RunValidationError(
            f"child at ordinal {index} must be a JSON object, "
            f"got {type(child).__name__}"
        )
    capability = child.get("capability")
    if not isinstance(capability, str) or not capability:
        raise RunValidationError(
            f"child at ordinal {index} requires a non-empty capability"
        )
    spec = child.get("spec")
    if not isinstance(spec, Mapping):
        raise RunValidationError(
            f"child at ordinal {index} requires a JSON-object spec"
        )
    input_manifest = child.get("input_manifest", [])
    if isinstance(input_manifest, (str, bytes)) or not isinstance(
        input_manifest, Sequence
    ):
        raise RunValidationError(
            f"child at ordinal {index} requires a JSON-array input_manifest"
        )
    task_id = child.get("task_id")
    if task_id is not None and (not isinstance(task_id, str) or not task_id):
        raise RunValidationError(
            f"child at ordinal {index} task_id must be a non-empty string"
        )
    priority = child.get("priority", 0)
    _require_int(f"child at ordinal {index} priority", priority)
    available_at = child.get("available_at")
    if available_at is not None and (
        not isinstance(available_at, str) or not available_at
    ):
        raise RunValidationError(
            f"child at ordinal {index} available_at must be a non-empty string"
        )
    max_attempts = child.get("max_attempts", 1)
    if (
        isinstance(max_attempts, bool)
        or not isinstance(max_attempts, int)
        or max_attempts <= 0
    ):
        raise RunValidationError(
            f"child at ordinal {index} max_attempts must be a positive integer"
        )
    dependencies = child.get("dependencies")
    if dependencies is not None and (
        isinstance(dependencies, (str, bytes))
        or not isinstance(dependencies, Sequence)
    ):
        raise RunValidationError(
            f"child at ordinal {index} dependencies must be a JSON array"
        )
    return {
        "task_id": task_id,
        "capability": capability,
        "spec": dict(spec),
        "input_manifest": list(input_manifest),
        "priority": priority,
        "available_at": available_at,
        "max_attempts": max_attempts,
        "dependencies": dependencies,
    }


def _request_child(child: Mapping[str, Any]) -> dict[str, Any]:
    """The request-identity representation of one child.

    Includes every caller-supplied fact (and the stable ``task_id`` only
    when the caller supplied it); generated values are excluded so an
    identical retry under the same key hashes identically.
    """
    entry: dict[str, Any] = {
        "capability": child["capability"],
        "spec": child["spec"],
        "input_manifest": child["input_manifest"],
        "priority": child["priority"],
        "available_at": child["available_at"],
        "max_attempts": child["max_attempts"],
    }
    if child["task_id"] is not None:
        entry["task_id"] = child["task_id"]
    if child["dependencies"] is not None:
        entry["dependencies"] = [dict(dep) for dep in child["dependencies"]]
    return entry


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class RunRepository:
    """Stateless run command surface over the kernel unit of work."""

    def __init__(
        self,
        events: EventAppendPort,
        receipts: ReceiptService,
    ) -> None:
        self._events = events
        self._receipts = receipts

    # -- fan-out (m2 plan step 12) -----------------------------------------

    def create(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        children: Sequence[Mapping[str, Any]],
        idempotency_key: str,
        actor_kind: str = "local",
        run_id: str | None = None,
        kind: str = "group",
        title: str | None = None,
        input: Mapping[str, Any] | None = None,
        created_at: str | None = None,
        command_kind: str = CORE_RUN_CREATE_COMMAND_KIND,
    ) -> RunFanOutReadModel:
        """Create one run and its direct children atomically and idempotently.

        Inside the caller's active unit of work this commits, in one
        ``BEGIN IMMEDIATE`` transaction: the ``core.run`` event stream and
        ``runs`` row (``status`` ``running``), the ``core.run.created``
        event, then each direct child's ``core.task`` stream, ``tasks`` row
        (stable ``run_ordinal`` = child index), resolved dependency edges,
        and ``core.task.created`` event — followed by both heads and one
        complete receipt carrying every ordered event id.

        *children* is a JSON array of at most
        :data:`FROZEN_MAX_DIRECT_CHILDREN` child definitions; a 257th child
        is rejected **before** any mutation. Each child is ``{capability,
        spec, input_manifest?, priority?, available_at?, max_attempts?,
        task_id?, dependencies?}``; ``task_id`` (when supplied) is the
        stable id for replay and dependency references, and dependencies
        follow the frozen task rules (validated same-project and acyclic at
        each child's creation, so a dependency may reference an earlier
        child of this fan-out or any pre-existing project task).

        Returns the :class:`RunFanOutReadModel` — run id, ordered task ids,
        ordinal range, and an empty evidence-id list. No parent task, no
        step record, and no evidence rows are ever created.

        Idempotency: the receipt gate runs before any mutation. An identical
        retry under the same key returns exactly the stored fan-out result
        with zero new rows; a changed request under the same key raises
        :class:`ReceiptMismatchError`.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        kind = _require_non_empty_string("kind", kind)
        if title is not None:
            _require_non_empty_string("title", title)
        if actor_kind not in ACTOR_KINDS:
            raise RunValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if run_id is None:
            run_id = generate_lowercase_ulid()
        else:
            _require_non_empty_string("run_id", run_id)
        if isinstance(children, (str, bytes)) or not isinstance(
            children, Sequence
        ):
            raise RunValidationError("children must be a JSON array")
        if len(children) > FROZEN_MAX_DIRECT_CHILDREN:
            raise RunValidationError(
                "fan-out admits at most "
                f"{FROZEN_MAX_DIRECT_CHILDREN} direct children, got "
                f"{len(children)}"
            )
        normalized = tuple(_normalize_child(index, child) for index, child in enumerate(children))
        input_dict = _require_json_object("input", input if input is not None else {})

        # Semantic request identity: the stable run id (when supplied), run
        # facts, and every caller-supplied child fact participate.
        request: dict[str, Any] = {
            "run_id": run_id,
            "kind": kind,
            "title": title,
            "input": input_dict,
            "children": [_request_child(child) for child in normalized],
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise RunValidationError(
                f"cannot hash fan-out request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before any sequence
        # allocation, stream creation, or projection write.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return RunFanOutReadModel.from_mapping(replayed)

        # The project must exist before any run/task stream is inserted.
        if uow.query_one("SELECT id FROM projects WHERE id = ?", (project_id,)) is None:
            raise RunValidationError(
                f"fan-out requires an existing project: {project_id!r}"
            )

        # Typed duplicate rejection before the UNIQUE constraints fire.
        if uow.query_one("SELECT id FROM runs WHERE id = ?", (run_id,)) is not None:
            raise RunAlreadyExistsError(run_id=run_id)

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise RunValidationError("created_at must be a non-empty string")
        txn_id = uuid.uuid4().hex

        # 1. The core.run stream and runs row (status running).
        run_stream_id = f"{run_id}:{CORE_RUN_STREAM_TYPE}"
        uow.execute(
            "INSERT INTO event_streams "
            "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (run_stream_id, project_id, CORE_RUN_STREAM_TYPE, run_id, stamp),
        )
        input_json = canonical_json(input_dict)
        uow.execute(
            "INSERT INTO runs "
            "(id, project_id, event_stream_id, kind, status, title, "
            "input_json, result_json, started_at, finished_at) "
            "VALUES (?, ?, ?, ?, 'running', ?, ?, '{}', ?, NULL)",
            (run_id, project_id, run_stream_id, kind, title, input_json, stamp),
        )
        # 2. The core.run.created event (the command's first project event).
        run_event_data: dict[str, Any] = {
            "run_id": run_id,
            "kind": kind,
            "title": title,
            "input": input_dict,
            "child_count": len(normalized),
            "first_ordinal": 0,
            "last_ordinal": len(normalized) - 1,
        }
        run_changes: list[str] = [
            "run_id",
            "kind",
            "title",
            "input",
            "child_count",
            "first_ordinal",
            "last_ordinal",
        ]
        run_append = self._events.append(
            uow,
            stream_id=run_stream_id,
            project_id=project_id,
            event_kind=CORE_RUN_CREATED_EVENT_KIND,
            data=run_event_data,
            changes=run_changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=uuid.uuid4().hex,
            created_at=stamp,
        )

        # 3. Direct children in ordinal order: task stream, task row (stable
        #    run_ordinal), resolved dependency edges, created event. Each
        #    child's dependency graph is validated at its creation against
        #    the tasks visible then (earlier children plus pre-existing
        #    project tasks); a reference to a later child is a typed
        #    missing-dependency error, which keeps the child graph acyclic.
        task_ids: list[str] = []
        event_ids: list[str] = [run_append.event_id]
        first_project_seq = run_append.project_seq
        last_project_seq = run_append.project_seq
        for ordinal, child in enumerate(normalized):
            child_id = child["task_id"] if child["task_id"] is not None else generate_lowercase_ulid()
            available = child["available_at"] if child["available_at"] is not None else stamp
            dependency_specs = _normalize_dependencies(child_id, child["dependencies"])
            _validate_dependency_graph(
                uow,
                task_id=child_id,
                project_id=project_id,
                dependency_specs=dependency_specs,
            )
            status = _initial_status_from_dependencies(uow, dependency_specs)
            try:
                spec_json = canonical_json(child["spec"])
                input_manifest_json = canonical_json(child["input_manifest"])
                spec_digest = compute_spec_hash(child["spec"], child["input_manifest"])
            except CanonicalizationError as exc:
                raise RunValidationError(
                    f"cannot canonicalize child at ordinal {ordinal}: {exc}"
                ) from exc

            task_stream_id = f"{child_id}:{CORE_TASK_STREAM_TYPE}"
            uow.execute(
                "INSERT INTO event_streams "
                "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (task_stream_id, project_id, CORE_TASK_STREAM_TYPE, child_id, stamp),
            )
            uow.execute(
                "INSERT INTO tasks "
                "(id, project_id, event_stream_id, run_id, run_ordinal, "
                "capability, spec_json, spec_hash, input_manifest_json, status, "
                "priority, available_at, max_attempts, winning_attempt_id, "
                "cancel_request_id, cancel_requested_at, created_at, updated_at, "
                "finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "NULL, NULL, NULL, ?, ?, NULL)",
                (
                    child_id,
                    project_id,
                    task_stream_id,
                    run_id,
                    ordinal,
                    child["capability"],
                    spec_json,
                    spec_digest,
                    input_manifest_json,
                    status,
                    child["priority"],
                    available,
                    child["max_attempts"],
                    stamp,
                    stamp,
                ),
            )
            for dep in dependency_specs:
                uow.execute(
                    "INSERT INTO task_dependencies "
                    "(task_id, depends_on_task_id, kind, ordinal) "
                    "VALUES (?, ?, ?, ?)",
                    (child_id, dep.depends_on_task_id, dep.kind, dep.ordinal),
                )
            event_data: dict[str, Any] = {
                "capability": child["capability"],
                "spec": child["spec"],
                "spec_hash": spec_digest,
                "input_manifest": child["input_manifest"],
                "priority": child["priority"],
                "available_at": available,
                "max_attempts": child["max_attempts"],
                "status": status,
                "run_id": run_id,
                "run_ordinal": ordinal,
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
                "run_id",
                "run_ordinal",
            ]
            if dependency_specs:
                event_data["dependencies"] = [
                    dep.to_dict() for dep in dependency_specs
                ]
                changes.append("dependencies")
            append = self._events.append(
                uow,
                stream_id=task_stream_id,
                project_id=project_id,
                event_kind=CORE_TASK_CREATED_EVENT_KIND,
                data=event_data,
                changes=changes,
                idempotency_key=f"{idempotency_key}:child:{ordinal}",
                txn_id=txn_id,
                actor_kind=actor_kind,
                command_kind=CORE_TASK_CREATE_COMMAND_KIND,
                event_id=uuid.uuid4().hex,
                created_at=stamp,
            )
            task_ids.append(child_id)
            event_ids.append(append.event_id)
            last_project_seq = append.project_seq

        # 4. The single complete receipt: every ordered event id, the exact
        #    project sequence range, and the fan-out result.
        result = RunFanOutReadModel(
            run_id=run_id,
            project_id=project_id,
            task_ids=tuple(task_ids),
            first_ordinal=0,
            last_ordinal=len(task_ids) - 1,
            evidence_ids=(),
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=first_project_seq,
            last_project_seq=last_project_seq,
            event_ids=event_ids,
            result=result.to_dict(),
            primary_stream_id=run_stream_id,
            resulting_stream_seq=run_append.stream_seq,
            created_at=stamp,
        )
        return result

    # -- derived group progress (m2 plan step 13, T22) ---------------------

    def derive_progress(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        run_id: str,
    ) -> RunProgressReadModel:
        """Derive one run's ordered group progress transaction-free.

        A pure read: child task statuses are queried ordered by
        ``run_ordinal`` and the run status is derived under the single
        shared rule (``derive_run_progress_counts`` in the task
        repository). No cursor and no persisted mutable progress aggregate
        ever exist — the projection is always a function of the child
        ``tasks`` rows at read time. Raises :class:`RunNotFoundError` for
        an unknown or foreign run.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        run_id = _require_non_empty_string("run_id", run_id)
        run_row = uow.query_one(
            "SELECT id FROM runs WHERE id = ? AND project_id = ?",
            (run_id, project_id),
        )
        if run_row is None:
            raise RunNotFoundError(run_id=run_id)
        return self._derive_progress(uow, project_id=project_id, run_id=run_id)

    def _derive_progress(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        run_id: str,
    ) -> RunProgressReadModel:
        """Internal derivation used by the public read and group commands."""
        counts, status = derive_run_progress_counts(
            uow, run_id=run_id, project_id=project_id
        )
        children = uow.query(
            "SELECT id, run_ordinal, status FROM tasks "
            "WHERE run_id = ? AND project_id = ? ORDER BY run_ordinal ASC",
            (run_id, project_id),
        )
        ordered = tuple(
            (int(row["run_ordinal"]), str(row["id"]), str(row["status"]))
            for row in children
        )
        return RunProgressReadModel(
            run_id=run_id,
            project_id=project_id,
            status=status,
            total_children=sum(counts.values()),
            succeeded=counts.get("succeeded", 0),
            failed=counts.get("failed", 0),
            cancelled=counts.get("cancelled", 0),
            ordered=ordered,
        )

    @staticmethod
    def _recompute_run_projection(
        uow: UnitOfWork,
        *,
        run_id: str,
        project_id: str,
        stamp: str,
    ) -> dict[str, Any]:
        """Recompute and persist one running run's derived projection.

        Uses the single shared derivation (``derive_run_progress_counts``),
        persists ``runs.result_json``/``status``/``finished_at`` inside the
        caller's UoW, and returns the JSON-safe projection mapping. The
        ``WHERE status = 'running'`` predicate makes the write a no-op for
        a run that became terminal mid-command (impossible inside one
        ``BEGIN IMMEDIATE`` transaction, but the fence keeps the projection
        immutable for terminal runs — the same rule task completion
        enforces).
        """
        counts, run_status = derive_run_progress_counts(
            uow, run_id=run_id, project_id=project_id
        )
        projection: dict[str, Any] = {
            "total_children": sum(counts.values()),
            "succeeded": counts.get("succeeded", 0),
            "failed": counts.get("failed", 0),
            "cancelled": counts.get("cancelled", 0),
            "status": run_status,
        }
        try:
            result_json = canonical_json(projection)
        except CanonicalizationError as exc:  # pragma: no cover - ints only
            raise RunValidationError(
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

    # -- receipt-protected group cancel (m2 plan step 13, T22) -------------

    def cancel(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        run_id: str,
        idempotency_key: str,
        actor_kind: str = "local",
        cancel_request_id: str | None = None,
        now: str | None = None,
        command_kind: str = CORE_RUN_CANCEL_COMMAND_KIND,
    ) -> RunCancelReadModel:
        """Cancel every eligible child of one running run atomically.

        Inside the caller's active unit of work this drives each eligible
        **queued/blocked** direct child to the terminal ``cancelled`` state
        through the shared task-cancel predicate (:meth:`TaskRepository.cancel`
        — the same race-hardened transition, receipt and event included),
        in ordinal order, then recomputes the run projection, appends the
        hash-chained ``core.run.cancelled`` event on the run stream, and
        records **one** complete run-level receipt carrying every ordered
        event id.

        - **Eligibility.** A child is group-cancellable when it is
          ``queued`` or ``blocked`` (no live attempt): the shared predicate
          needs no attempt fence there. Already-terminal children
          (``succeeded``/``failed``/``cancelled``) and ``running`` children
          are skipped — a running child's owned attempt requires its
          executor's exact ``attempt_id``/``lease_id``/``status_version``
          fence, which a group signal cannot present, so the group command
          never invents one.
        - **Terminal-run rejection.** A run that already reached
          ``succeeded``/``failed``/``cancelled`` raises
          :class:`RunTerminalError` before any child is touched: terminal
          runs never continue (m2 plan step 13).
        - **Projection.** After the child transitions the run projection is
          recomputed from the child rows (shared derivation): when every
          child is terminal the run transitions to ``failed`` (any child
          failed), ``cancelled`` (any child cancelled, none failed), or
          ``succeeded``, stamping ``finished_at``; otherwise it stays
          ``running``.
        - **One group request id.** The effective ``cancel_request_id``
          (the caller's or a fresh generated one) is shared by every
          cancelled child and recorded on the run event.

        Idempotency: the receipt gate runs first. An identical retry under
        the same key returns exactly the stored group-cancel result with
        zero new rows; a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        run_id = _require_non_empty_string("run_id", run_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise RunValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if cancel_request_id is not None:
            _require_non_empty_string("cancel_request_id", cancel_request_id)

        # Semantic request identity: the run plus any caller-supplied group
        # cancel request id; generated state never participates.
        request: dict[str, Any] = {"run_id": run_id}
        if cancel_request_id is not None:
            request["cancel_request_id"] = cancel_request_id
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise RunValidationError(
                f"cannot hash group-cancel request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before any mutation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return RunCancelReadModel.from_mapping(replayed)

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise RunValidationError("now must be a non-empty string")

        # Fences before any mutation: the run exists, belongs to the
        # project, and is nonterminal (terminal runs never continue).
        run_row = uow.query_one(
            "SELECT * FROM runs WHERE id = ? AND project_id = ?",
            (run_id, project_id),
        )
        if run_row is None:
            raise RunNotFoundError(run_id=run_id)
        if str(run_row["status"]) != "running":
            raise RunTerminalError(run_id=run_id, status=str(run_row["status"]))

        children = uow.query(
            "SELECT id, run_ordinal, status FROM tasks "
            "WHERE run_id = ? AND project_id = ? ORDER BY run_ordinal ASC",
            (run_id, project_id),
        )

        task_repo = TaskRepository(events=self._events, receipts=self._receipts)
        effective_cancel_request_id = (
            cancel_request_id
            if cancel_request_id is not None
            else generate_lowercase_ulid()
        )
        cancelled: list[str] = []
        skipped: list[str] = []
        txn_id = uuid.uuid4().hex
        head_before = int(
            uow.query_one(
                "SELECT event_head_seq FROM projects WHERE id = ?",
                (project_id,),
            )["event_head_seq"]
        )

        # 1. Shared task-cancel predicate per eligible child, ordinal order.
        for ordinal, child in enumerate(children):
            child_id = str(child["id"])
            if str(child["status"]) in ("queued", "blocked"):
                task_repo.cancel(
                    uow,
                    project_id=project_id,
                    task_id=child_id,
                    idempotency_key=f"{idempotency_key}:child:{ordinal}",
                    actor_kind=actor_kind,
                    cancel_request_id=effective_cancel_request_id,
                    now=stamp,
                    command_kind=CORE_TASK_CANCEL_COMMAND_KIND,
                )
                cancelled.append(child_id)
            else:
                skipped.append(child_id)
        if not cancelled:
            raise RunValidationError(
                f"run {run_id!r} has no cancellable children (queued/blocked); "
                "terminal and running children need no group cancel"
            )

        # 2. Recompute the run projection from the child rows.
        projection = self._recompute_run_projection(
            uow, run_id=run_id, project_id=project_id, stamp=stamp
        )

        # 3. The hash-chained core.run.cancelled event on the run stream.
        run_stream_id = f"{run_id}:{CORE_RUN_STREAM_TYPE}"
        event_data: dict[str, Any] = {
            "run_id": run_id,
            "cancel_request_id": effective_cancel_request_id,
            "cancelled_task_ids": cancelled,
            "skipped_task_ids": skipped,
            "status": projection["status"],
            "progress": projection,
        }
        changes: list[str] = [
            "run_status",
            "cancel_request_id",
            "cancelled_task_ids",
            "skipped_task_ids",
            "progress",
        ]
        append = self._events.append(
            uow,
            stream_id=run_stream_id,
            project_id=project_id,
            event_kind=CORE_RUN_CANCELLED_EVENT_KIND,
            data=event_data,
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=uuid.uuid4().hex,
            created_at=stamp,
        )

        # 4. The one complete run-level receipt: every ordered event id the
        #    group command appended (child cancelled events, then the run
        #    event), spanning the exact project-seq range.
        ordered_events = uow.query(
            "SELECT event_id, project_seq FROM events "
            "WHERE project_id = ? AND project_seq > ? "
            "ORDER BY project_seq ASC",
            (project_id, head_before),
        )
        event_ids = tuple(str(row["event_id"]) for row in ordered_events)
        if not event_ids:  # pragma: no cover - children append events first
            raise RunValidationError(
                "group cancel appended no events; cannot record a receipt"
            )
        first_seq = int(ordered_events[0]["project_seq"])
        last_seq = int(ordered_events[-1]["project_seq"])

        result = RunCancelReadModel(
            run=projection,
            progress=self._derive_progress(
                uow, project_id=project_id, run_id=run_id
            ),
            cancelled_task_ids=tuple(cancelled),
            skipped_task_ids=tuple(skipped),
            cancel_request_id=effective_cancel_request_id,
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
            event_ids=event_ids,
            result=result.to_dict(),
            primary_stream_id=run_stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return result

    # -- receipt-protected group retry (m2 plan step 13, T22) --------------

    def retry(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        run_id: str,
        idempotency_key: str,
        actor_kind: str = "local",
        executor_id: str | None = None,
        selected_task_ids: Sequence[str] | None = None,
        now: str | None = None,
        command_kind: str = CORE_RUN_RETRY_COMMAND_KIND,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> RunRetryReadModel:
        """Retry every eligible child — or an explicit subset — atomically.

        Inside the caller's active unit of work this restarts the run's
        failed/expired work through the shared task-retry predicate
        (:meth:`TaskRepository.retry` — the same attempt-budget and
        terminal-immutability rules, receipt and event included), in
        ordinal order, then recomputes the run projection, appends the
        hash-chained ``core.run.retried`` event on the run stream, and
        records **one** complete run-level receipt carrying every ordered
        event id.

        - **Retry all eligible.** Without *selected_task_ids* every child
          that satisfies the shared retry eligibility (read through
          :meth:`TaskRepository.is_retry_eligible`, then transitioned by the
          shared predicate) is retried; ineligible children — terminal
          tasks, never-claimed work, running work, blocked work, or
          exhausted attempt budgets — are skipped and reported.
        - **Explicit subset.** With *selected_task_ids* (a non-empty unique
          sequence of direct children of this run) exactly those children
          are retried in ordinal order; an id that is not a direct child
          raises :class:`RunValidationError` before any mutation, and an
          ineligible selected child raises the shared predicate's typed
          :class:`TaskTransitionError` — one transaction, so nothing is
          half-retried. The canonical sorted subset participates in the
          request identity, so retrying a different subset under the same
          key is a mismatch before any mutation.
        - **Terminal-run rejection.** A run that already reached
          ``succeeded``/``failed``/``cancelled`` raises
          :class:`RunTerminalError` before any child is touched: terminal
          runs never continue (m2 plan step 13).
        - **Projection.** After the transitions the run projection is
          recomputed from the child rows (shared derivation): retried
          children are ``running`` again, so the run stays ``running`` with
          refreshed counts.

        Idempotency: the receipt gate runs first. An identical retry under
        the same key returns exactly the stored group-retry result with
        zero new rows; a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        run_id = _require_non_empty_string("run_id", run_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise RunValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if executor_id is not None:
            _require_non_empty_string("executor_id", executor_id)
        if isinstance(lease_seconds, bool) or not isinstance(
            lease_seconds, int
        ) or lease_seconds <= 0:
            raise RunValidationError(
                "lease_seconds must be a positive integer, "
                f"got {lease_seconds!r}"
            )
        if selected_task_ids is not None:
            if (
                isinstance(selected_task_ids, (str, bytes))
                or not isinstance(selected_task_ids, Sequence)
                or not selected_task_ids
            ):
                raise RunValidationError(
                    "selected_task_ids must be a non-empty sequence of "
                    "non-empty task ids"
                )
            for entry in selected_task_ids:
                _require_non_empty_string("selected_task_ids[]", entry)
            if len(set(selected_task_ids)) != len(selected_task_ids):
                raise RunValidationError(
                    "selected_task_ids must not contain duplicates"
                )

        # Semantic request identity: the run plus the canonical sorted
        # selection set (when supplied); generated state never participates.
        request: dict[str, Any] = {"run_id": run_id}
        if selected_task_ids is not None:
            request["selected_task_ids"] = sorted(selected_task_ids)
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise RunValidationError(
                f"cannot hash group-retry request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before any mutation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return RunRetryReadModel.from_mapping(replayed)

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise RunValidationError("now must be a non-empty string")

        # Fences before any mutation: the run exists, belongs to the
        # project, and is nonterminal (terminal runs never continue).
        run_row = uow.query_one(
            "SELECT * FROM runs WHERE id = ? AND project_id = ?",
            (run_id, project_id),
        )
        if run_row is None:
            raise RunNotFoundError(run_id=run_id)
        if str(run_row["status"]) != "running":
            raise RunTerminalError(run_id=run_id, status=str(run_row["status"]))

        children = uow.query(
            "SELECT id, run_ordinal, status FROM tasks "
            "WHERE run_id = ? AND project_id = ? ORDER BY run_ordinal ASC",
            (run_id, project_id),
        )

        task_repo = TaskRepository(events=self._events, receipts=self._receipts)
        selected: set[str] | None = (
            set(selected_task_ids) if selected_task_ids is not None else None
        )
        if selected is not None:
            child_ids = {str(child["id"]) for child in children}
            unknown = sorted(selected - child_ids)
            if unknown:
                raise RunValidationError(
                    "selected task ids are not direct children of run "
                    f"{run_id!r}: {unknown}"
                )
        retried: list[str] = []
        skipped: list[str] = []
        txn_id = uuid.uuid4().hex
        head_before = int(
            uow.query_one(
                "SELECT event_head_seq FROM projects WHERE id = ?",
                (project_id,),
            )["event_head_seq"]
        )

        # 1. Shared task-retry predicate per eligible child, ordinal order.
        for ordinal, child in enumerate(children):
            child_id = str(child["id"])
            if selected is not None and child_id not in selected:
                continue  # explicit subset: unselected children untouched
            if selected is None:
                eligible, _reason = task_repo.is_retry_eligible(
                    uow, project_id=project_id, task_id=child_id
                )
                if not eligible:
                    skipped.append(child_id)
                    continue
            task_repo.retry(
                uow,
                project_id=project_id,
                task_id=child_id,
                idempotency_key=f"{idempotency_key}:child:{ordinal}",
                actor_kind=actor_kind,
                executor_id=executor_id,
                selected_task_ids=(
                    sorted(selected) if selected is not None else None
                ),
                now=stamp,
                command_kind=CORE_TASK_RETRY_COMMAND_KIND,
                lease_seconds=lease_seconds,
            )
            retried.append(child_id)
        if not retried:
            raise RunValidationError(
                f"run {run_id!r} has no eligible children to retry"
            )

        # 2. Recompute the run projection from the child rows.
        projection = self._recompute_run_projection(
            uow, run_id=run_id, project_id=project_id, stamp=stamp
        )

        # 3. The hash-chained core.run.retried event on the run stream.
        run_stream_id = f"{run_id}:{CORE_RUN_STREAM_TYPE}"
        event_data: dict[str, Any] = {
            "run_id": run_id,
            "executor_id": executor_id,
            "retried_task_ids": retried,
            "skipped_task_ids": skipped,
            "selected_task_ids": (
                sorted(selected) if selected is not None else None
            ),
            "status": projection["status"],
            "progress": projection,
        }
        changes: list[str] = [
            "run_status",
            "executor_id",
            "retried_task_ids",
            "skipped_task_ids",
            "selected_task_ids",
            "progress",
        ]
        append = self._events.append(
            uow,
            stream_id=run_stream_id,
            project_id=project_id,
            event_kind=CORE_RUN_RETRIED_EVENT_KIND,
            data=event_data,
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=uuid.uuid4().hex,
            created_at=stamp,
        )

        # 4. The one complete run-level receipt: every ordered event id the
        #    group command appended (child retried events, then the run
        #    event), spanning the exact project-seq range.
        ordered_events = uow.query(
            "SELECT event_id, project_seq FROM events "
            "WHERE project_id = ? AND project_seq > ? "
            "ORDER BY project_seq ASC",
            (project_id, head_before),
        )
        event_ids = tuple(str(row["event_id"]) for row in ordered_events)
        if not event_ids:  # pragma: no cover - children append events first
            raise RunValidationError(
                "group retry appended no events; cannot record a receipt"
            )
        first_seq = int(ordered_events[0]["project_seq"])
        last_seq = int(ordered_events[-1]["project_seq"])

        result = RunRetryReadModel(
            run=projection,
            progress=self._derive_progress(
                uow, project_id=project_id, run_id=run_id
            ),
            retried_task_ids=tuple(retried),
            skipped_task_ids=tuple(skipped),
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
            event_ids=event_ids,
            result=result.to_dict(),
            primary_stream_id=run_stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return result

    # -- pure continuation-envelope validation (m2 plan step 12 item 4) ----

    @staticmethod
    def validate_continuation_envelope(
        envelope: Mapping[str, Any],
    ) -> ContinuationEnvelope:
        """Validate a frozen continuation envelope without executing it.

        A pure validator: it reads no database, opens no transaction,
        allocates no run-head CAS, and performs no writes. The frozen field
        set is :data:`FROZEN_CONTINUATION_ENVELOPE_FIELDS`; the rules are

        - ``run_id``/``project_id`` are non-empty strings;
        - ``start_ordinal``/``end_ordinal`` are non-negative integers within
          ``0 .. FROZEN_MAX_DIRECT_CHILDREN - 1`` with
          ``start_ordinal <= end_ordinal``;
        - ``max_children`` is an integer within
          ``1 .. FROZEN_MAX_DIRECT_CHILDREN`` and the envelope's ordinal
          span (``end_ordinal - start_ordinal + 1``) does not exceed it.

        Returns the immutable :class:`ContinuationEnvelope`; any violation
        raises :class:`ContinuationValidationError` before anything is
        touched. m2 validates these envelopes but never executes them.
        """
        if not isinstance(envelope, Mapping):
            raise ContinuationValidationError(
                detail=f"envelope must be a JSON object, got {type(envelope).__name__}"
            )
        for field in FROZEN_CONTINUATION_ENVELOPE_FIELDS:
            if field not in envelope:
                raise ContinuationValidationError(
                    field=field, detail="required field is missing"
                )
        run_id = envelope["run_id"]
        if not isinstance(run_id, str) or not run_id:
            raise ContinuationValidationError(
                field="run_id", detail="must be a non-empty string"
            )
        project_id = envelope["project_id"]
        if not isinstance(project_id, str) or not project_id:
            raise ContinuationValidationError(
                field="project_id", detail="must be a non-empty string"
            )
        start_ordinal = envelope["start_ordinal"]
        end_ordinal = envelope["end_ordinal"]
        for field, value in (
            ("start_ordinal", start_ordinal),
            ("end_ordinal", end_ordinal),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ContinuationValidationError(
                    field=field, detail=f"must be an integer, got {value!r}"
                )
            if value < 0 or value >= FROZEN_MAX_DIRECT_CHILDREN:
                raise ContinuationValidationError(
                    field=field,
                    detail=(
                        f"must be within 0 .. "
                        f"{FROZEN_MAX_DIRECT_CHILDREN - 1}, got {value}"
                    ),
                )
        if start_ordinal > end_ordinal:
            raise ContinuationValidationError(
                field="end_ordinal",
                detail=(
                    f"end_ordinal {end_ordinal} must be >= "
                    f"start_ordinal {start_ordinal}"
                ),
            )
        max_children = envelope["max_children"]
        if (
            isinstance(max_children, bool)
            or not isinstance(max_children, int)
            or max_children < 1
            or max_children > FROZEN_MAX_DIRECT_CHILDREN
        ):
            raise ContinuationValidationError(
                field="max_children",
                detail=(
                    f"must be an integer within 1 .. "
                    f"{FROZEN_MAX_DIRECT_CHILDREN}, got {max_children!r}"
                ),
            )
        span = end_ordinal - start_ordinal + 1
        if span > max_children:
            raise ContinuationValidationError(
                field="max_children",
                detail=(
                    f"ordinal span {span} exceeds declared max_children "
                    f"{max_children}"
                ),
            )
        return ContinuationEnvelope(
            run_id=run_id,
            project_id=project_id,
            start_ordinal=start_ordinal,
            end_ordinal=end_ordinal,
            max_children=max_children,
        )


__all__ = [
    "CORE_RUN_CANCEL_COMMAND_KIND",
    "CORE_RUN_CANCELLED_EVENT_KIND",
    "CORE_RUN_CREATE_COMMAND_KIND",
    "CORE_RUN_CREATED_EVENT_KIND",
    "CORE_RUN_RETRY_COMMAND_KIND",
    "CORE_RUN_RETRIED_EVENT_KIND",
    "CORE_RUN_STREAM_TYPE",
    "ContinuationEnvelope",
    "ContinuationValidationError",
    "FROZEN_CONTINUATION_ENVELOPE_FIELDS",
    "FROZEN_MAX_DIRECT_CHILDREN",
    "RUN_STATUSES",
    "RunAlreadyExistsError",
    "RunCancelReadModel",
    "RunFanOutReadModel",
    "RunNotFoundError",
    "RunProgressReadModel",
    "RunReadModel",
    "RunRepository",
    "RunRepositoryError",
    "RunRetryReadModel",
    "RunTerminalError",
    "RunValidationError",
]
