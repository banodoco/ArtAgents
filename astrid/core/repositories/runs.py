"""Run repository: one-transaction bounded direct-child fan-out (m2 plan step 12).

:class:`RunRepository.create` is the run vertical's fan-out root: one writer
transaction commits the ``core.run`` event stream and ``runs`` row, then up
to ``FROZEN_MAX_DIRECT_CHILDREN`` (256) direct child ``core.task`` streams and
``tasks`` rows with stable ``run_ordinal`` values, the resolved same-project
acyclic dependency edges, ordered events (the ``core.run.created`` event
first, then each child's ``core.task.created`` event in ordinal order), both
heads, and **one** complete receipt carrying every ordered event id.

Contracts kept here (v10 section 5.2; m2 plan step 12):

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
    CORE_TASK_CREATE_COMMAND_KIND,
    CORE_TASK_CREATED_EVENT_KIND,
    CORE_TASK_STREAM_TYPE,
    TaskDependencyReadModel,
    _initial_status_from_dependencies,
    _normalize_dependencies,
    _validate_dependency_graph,
    compute_spec_hash,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.util.time import utc_now_iso

CORE_RUN_STREAM_TYPE = "core.run"
"""The kernel stream type every run aggregate owns (one per run row)."""

CORE_RUN_CREATED_EVENT_KIND = "core.run.created"
"""The m2 event kind emitted by one-transaction fan-out creation."""

CORE_RUN_CREATE_COMMAND_KIND = "core.run.create"
"""The m2 command kind that fan-out receipts are keyed on."""

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
    "CORE_RUN_CREATE_COMMAND_KIND",
    "CORE_RUN_CREATED_EVENT_KIND",
    "CORE_RUN_STREAM_TYPE",
    "ContinuationEnvelope",
    "ContinuationValidationError",
    "FROZEN_CONTINUATION_ENVELOPE_FIELDS",
    "FROZEN_MAX_DIRECT_CHILDREN",
    "RUN_STATUSES",
    "RunAlreadyExistsError",
    "RunFanOutReadModel",
    "RunNotFoundError",
    "RunReadModel",
    "RunRepository",
    "RunRepositoryError",
    "RunValidationError",
]
