"""Run fan-out tests: bounded direct-child fan-out, continuation validation,
and derived group operations (m2 plan steps 12 and 13, T21_impl and T22).

T21_impl scope proves the implementation half of plan step 12 before the
T21_proof audit:

- ``create`` commits one run stream/row plus at most 256 direct child task
  streams/rows with stable ``run_ordinal`` values, resolved same-project
  acyclic dependency edges, ordered events (``core.run.created`` first,
  then each ``core.task.created`` in ordinal order), both heads, and one
  receipt carrying every ordered event id;
- child 257 is rejected **before** any mutation; the result returns the run
  id, ordered task ids, ordinal range, and an empty evidence-id list, and
  no parent task or step record is ever created;
- replay returns the stored fan-out result with zero new rows and mismatch
  fails before any mutation;
- ``validate_continuation_envelope`` is a pure validator of the frozen
  envelope fields and ordinal/maximum rules — it never executes the
  envelope and performs no writes.

T22 scope (plan step 13) proves the group surface:

- ``derive_progress`` derives ordered progress from the child task rows by
  ``run_ordinal`` — no cursor, no persisted mutable progress aggregate;
- receipt-protected ``cancel`` drives eligible queued/blocked/running children
  to the terminal ``cancelled`` state through the shared task-cancel
  predicate (running children cooperatively, skipping already-terminal
  children), recomputes the run projection
  (``succeeded``/``failed``/``cancelled`` when every child is terminal),
  appends ``core.run.cancelled``, and records one run-level receipt;
- receipt-protected ``retry`` restarts all eligible children (or an
  explicit subset) through the shared task-retry predicate and the shared
  retry-eligibility check, recomputes the projection, appends
  ``core.run.retried``, and records one run-level receipt;
- both group commands reject continuation of a terminal run
  (``RunTerminalError``) before any mutation.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from astrid.core.ids import generate_lowercase_ulid
from astrid.core.migrations.catalog import FORBIDDEN_TABLES
from astrid.core.receipts import ReceiptMismatchError
from astrid.core.repositories import (
    RunAlreadyExistsError,
    RunFanOutReadModel,
    RunNotFoundError,
    RunRepositoryError,
    RunValidationError,
)
from astrid.core.repositories.runs import (
    CORE_RUN_CANCEL_COMMAND_KIND,
    CORE_RUN_CANCELLED_EVENT_KIND,
    CORE_RUN_CONTINUE_COMMAND_KIND,
    CORE_RUN_CONTINUED_EVENT_KIND,
    CORE_RUN_CREATE_COMMAND_KIND,
    CORE_RUN_CREATED_EVENT_KIND,
    CORE_RUN_RETRY_COMMAND_KIND,
    CORE_RUN_RETRIED_EVENT_KIND,
    CORE_RUN_STREAM_TYPE,
    CORE_TASK_CREATED_EVENT_KIND,
    CORE_TASK_STREAM_TYPE,
    FROZEN_MAX_DIRECT_CHILDREN,
    ContinuationEnvelope,
    ContinuationValidationError,
    RunCancelReadModel,
    RunContinuationReadModel,
    RunProgressReadModel,
    RunReadModel,
    RunRepository,
    RunRetryReadModel,
    RunStaleHeadError,
    RunTerminalError,
)
from astrid.core.repositories.tasks import (
    CORE_TASK_CANCEL_COMMAND_KIND,
    CORE_TASK_CANCELLED_EVENT_KIND,
    CORE_TASK_RETRY_COMMAND_KIND,
    CORE_TASK_RETRIED_EVENT_KIND,
    TaskDependencyError,
    TaskRepository,
    TaskTransitionError,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter

TS = "2026-08-16T00:00:00.000000+00:00"

SPEC_A = {"backend": "remotion", "composition": "main", "fps": 24}
MANIFEST_A = ["media_1"]


@pytest.fixture
def run_env(tmp_path, core_registry):
    """Fresh kernel writer plus project and run repositories."""
    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.core.store.writer import DatabaseWriter

    db_path = tmp_path / "fanout_env.sqlite3"
    writer = DatabaseWriter(db_path, core_registry)
    try:
        events = EventAppendService(core_registry)
        receipts = ReceiptService()
        yield SimpleNamespace(
            writer=writer,
            project_repo=ProjectRepository(events=events, receipts=receipts),
            run_repo=RunRepository(events=events, receipts=receipts),
        )
    finally:
        writer.close()


def _create_project(env, *, slug: str = "pilot", project_id: str | None = None):
    args = {
        "slug": slug,
        "name": slug.title(),
        "settings": {"fps": 24},
        "idempotency_key": f"create-{slug}-k",
        "project_id": project_id or generate_lowercase_ulid(),
        "created_at": TS,
    }
    return UnitOfWork(env.writer).run(lambda u: env.project_repo.create(u, **args))


def _child(
    *,
    task_id: str | None = None,
    capability: str = "rendering.timeline_visualize",
    spec=None,
    input_manifest=None,
    dependencies=None,
    **overrides,
):
    entry = {
        "capability": capability,
        "spec": spec if spec is not None else dict(SPEC_A),
        "input_manifest": input_manifest if input_manifest is not None else list(MANIFEST_A),
    }
    if task_id is not None:
        entry["task_id"] = task_id
    if dependencies is not None:
        entry["dependencies"] = dependencies
    entry.update(overrides)
    return entry


def _fanout(
    env,
    *,
    project_id: str,
    children,
    idempotency_key: str = "fanout-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "children": children,
        "idempotency_key": idempotency_key,
        "run_id": generate_lowercase_ulid(),
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.run_repo.create(u, **args))


def _counts(writer: DatabaseWriter) -> tuple[int, int, int, int, int, int, int]:
    """(projects, event_streams, events, command_receipts, runs, tasks,
    evidence_items)."""
    return writer.submit(
        lambda session: (
            session.query_one("SELECT count(*) FROM projects")[0],
            session.query_one("SELECT count(*) FROM event_streams")[0],
            session.query_one("SELECT count(*) FROM events")[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
            session.query_one("SELECT count(*) FROM runs")[0],
            session.query_one("SELECT count(*) FROM tasks")[0],
            session.query_one("SELECT count(*) FROM evidence_items")[0],
        )
    )


def _run_row(writer: DatabaseWriter, run_id: str):
    return writer.submit(
        lambda session: session.query_one("SELECT * FROM runs WHERE id = ?", (run_id,))
    )


def _task_row(writer: DatabaseWriter, task_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
    )


def _stream_row(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM event_streams WHERE id = ?", (stream_id,)
        )
    )


def _receipt_row(writer: DatabaseWriter, project_id: str, key: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM command_receipts WHERE project_id = ? "
            "AND idempotency_key = ?",
            (project_id, key),
        )
    )


def _event_rows(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM events WHERE stream_id = ? ORDER BY seq ASC",
            (stream_id,),
        )
    )


# ---------------------------------------------------------------------------
# One-transaction fan-out
# ---------------------------------------------------------------------------


def test_fanout_creates_run_and_children_atomically(run_env) -> None:
    project = _create_project(run_env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    counts_before = _counts(run_env.writer)

    result = _fanout(
        run_env,
        project_id=project.id,
        children=[
            _child(task_id=child_a, priority=3),
            _child(task_id=child_b, priority=1),
        ],
    )
    assert result.run_id is not None
    assert result.project_id == project.id
    assert result.task_ids == (child_a, child_b)
    assert result.first_ordinal == 0
    assert result.last_ordinal == 1
    assert result.evidence_ids == ()

    counts_after = _counts(run_env.writer)
    # One run + two child task streams, three events, one receipt, one run
    # row, two task rows, and zero evidence rows.
    assert counts_after == (
        counts_before[0],
        counts_before[1] + 3,
        counts_before[2] + 3,
        counts_before[3] + 1,
        counts_before[4] + 1,
        counts_before[5] + 2,
        counts_before[6],
    )

    run_row = _run_row(run_env.writer, result.run_id)
    assert run_row is not None
    assert run_row["project_id"] == project.id
    assert run_row["kind"] == "group"
    assert run_row["status"] == "running"
    assert run_row["event_stream_id"] == f"{result.run_id}:{CORE_RUN_STREAM_TYPE}"
    assert run_row["started_at"] == TS
    assert run_row["finished_at"] is None

    # No parent task: the run id never appears in tasks.
    assert _task_row(run_env.writer, result.run_id) is None
    assert _task_row(run_env.writer, child_a) is not None

    # Stable ordinals and run membership on the child rows.
    row_a = _task_row(run_env.writer, child_a)
    row_b = _task_row(run_env.writer, child_b)
    assert row_a["run_id"] == result.run_id and row_a["run_ordinal"] == 0
    assert row_b["run_id"] == result.run_id and row_b["run_ordinal"] == 1
    assert row_a["status"] == "queued" and row_b["status"] == "queued"


def test_fanout_event_order_and_one_receipt(run_env) -> None:
    project = _create_project(run_env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[_child(task_id=child_a), _child(task_id=child_b)],
        idempotency_key="fanout-order",
    )
    run_stream = f"{result.run_id}:{CORE_RUN_STREAM_TYPE}"
    run_events = _event_rows(run_env.writer, run_stream)
    assert len(run_events) == 1
    assert run_events[0]["kind"] == CORE_RUN_CREATED_EVENT_KIND
    assert run_events[0]["subject_type"] == "run"
    assert run_events[0]["subject_id"] == result.run_id
    data = json.loads(run_events[0]["payload_json"])["data"]
    assert data["child_count"] == 2
    assert data["first_ordinal"] == 0 and data["last_ordinal"] == 1

    # Child streams carry exactly the created event, in ordinal order of
    # project sequence (run.created first, then children in order).
    stream_a = f"{child_a}:{CORE_TASK_STREAM_TYPE}"
    stream_b = f"{child_b}:{CORE_TASK_STREAM_TYPE}"
    assert [_e["kind"] for _e in _event_rows(run_env.writer, stream_a)] == [
        CORE_TASK_CREATED_EVENT_KIND
    ]
    assert [_e["kind"] for _e in _event_rows(run_env.writer, stream_b)] == [
        CORE_TASK_CREATED_EVENT_KIND
    ]
    created_a = _event_rows(run_env.writer, stream_a)[0]
    created_b = _event_rows(run_env.writer, stream_b)[0]
    assert created_a["project_seq"] == run_events[0]["project_seq"] + 1
    assert created_b["project_seq"] == created_a["project_seq"] + 1
    assert json.loads(created_a["payload_json"])["data"]["run_ordinal"] == 0
    assert json.loads(created_b["payload_json"])["data"]["run_ordinal"] == 1

    # One receipt with every ordered event id.
    receipt = _receipt_row(run_env.writer, project.id, "fanout-order")
    assert receipt is not None
    assert receipt["command_kind"] == CORE_RUN_CREATE_COMMAND_KIND
    assert receipt["primary_stream_id"] == run_stream
    event_ids = json.loads(receipt["event_ids_json"])
    assert event_ids == [
        run_events[0]["event_id"],
        created_a["event_id"],
        created_b["event_id"],
    ]
    assert receipt["first_project_seq"] == run_events[0]["project_seq"]
    assert receipt["last_project_seq"] == created_b["project_seq"]
    # The run stream head advanced by one (only the run.created event).
    assert _stream_row(run_env.writer, run_stream)["head_seq"] == 1


def test_fanout_child_257_rejected_before_mutation(run_env) -> None:
    project = _create_project(run_env)
    counts = _counts(run_env.writer)
    children = [_child(task_id=generate_lowercase_ulid()) for _ in range(FROZEN_MAX_DIRECT_CHILDREN + 1)]
    assert len(children) == 257
    with pytest.raises(RunValidationError) as excinfo:
        _fanout(run_env, project_id=project.id, children=children)
    assert "256" in str(excinfo.value)
    assert _counts(run_env.writer) == counts


def test_fanout_resolves_same_project_child_dependencies(run_env) -> None:
    project = _create_project(run_env)
    parent = generate_lowercase_ulid()
    dependent = generate_lowercase_ulid()
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[
            _child(task_id=parent),
            _child(
                task_id=dependent,
                dependencies=[{"task_id": parent, "kind": "hard", "ordinal": 0}],
            ),
        ],
        idempotency_key="fanout-deps",
    )
    # The dependency edge was materialized.
    edge = run_env.writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM task_dependencies WHERE task_id = ? "
            "AND depends_on_task_id = ?",
            (dependent, parent),
        )
    )
    assert edge is not None
    assert edge["kind"] == "hard"
    # The parent child is queued (not yet succeeded), so the dependent child
    # starts blocked — same hard/soft gating as task admission.
    assert _task_row(run_env.writer, parent)["status"] == "queued"
    assert _task_row(run_env.writer, dependent)["status"] == "blocked"
    # A soft dependency never blocks.
    soft = generate_lowercase_ulid()
    _fanout(
        run_env,
        project_id=project.id,
        children=[
            _child(
                task_id=soft,
                dependencies=[{"task_id": parent, "kind": "soft", "ordinal": 0}],
            )
        ],
        idempotency_key="fanout-soft",
        run_id=generate_lowercase_ulid(),
    )
    assert _task_row(run_env.writer, soft)["status"] == "queued"
    assert result.evidence_ids == ()


def test_fanout_rejects_cross_project_and_later_child_dependencies(run_env) -> None:
    project_a = _create_project(run_env, slug="alpha")
    project_b = _create_project(run_env, slug="beta")
    foreign_task = generate_lowercase_ulid()
    # A task in project B.
    UnitOfWork(run_env.writer).run(
        lambda u: (
            u.execute(
                "INSERT INTO event_streams "
                "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
                "VALUES (?, ?, 'core.task', ?, 0, ?)",
                (f"{foreign_task}:{CORE_TASK_STREAM_TYPE}", project_b.id, foreign_task, TS),
            ),
            u.execute(
                "INSERT INTO tasks "
                "(id, project_id, event_stream_id, capability, spec_json, "
                "spec_hash, input_manifest_json, status, priority, available_at, "
                "max_attempts, created_at, updated_at) "
                "VALUES (?, ?, ?, 'foreign.capability', '{}', ?, '[]', 'queued', "
                "0, ?, 1, ?, ?)",
                (foreign_task, project_b.id, f"{foreign_task}:{CORE_TASK_STREAM_TYPE}",
                 "x" * 64, TS, TS, TS),
            ),
        )
    )
    counts = _counts(run_env.writer)
    # Cross-project dependency -> typed TaskDependencyError, zero mutation.
    with pytest.raises(TaskDependencyError) as excinfo:
        _fanout(
            run_env,
            project_id=project_a.id,
            children=[
                _child(
                    dependencies=[{"task_id": foreign_task, "kind": "hard", "ordinal": 0}]
                )
            ],
            idempotency_key="fanout-cross",
        )
    assert excinfo.value.reason == "cross_project"
    assert _counts(run_env.writer) == counts
    # A dependency on a later child (not yet created) is a typed missing
    # dependency; the child graph stays acyclic by construction.
    later = generate_lowercase_ulid()
    with pytest.raises(TaskDependencyError) as excinfo:
        _fanout(
            run_env,
            project_id=project_a.id,
            children=[
                _child(
                    task_id=generate_lowercase_ulid(),
                    dependencies=[{"task_id": later, "kind": "hard", "ordinal": 0}],
                ),
                _child(task_id=later),
            ],
            idempotency_key="fanout-backward",
        )
    assert excinfo.value.reason == "missing"
    assert _counts(run_env.writer) == counts


def test_fanout_replay_returns_stored_result_with_zero_new_rows(run_env) -> None:
    project = _create_project(run_env)
    child = generate_lowercase_ulid()
    run_id = generate_lowercase_ulid()
    first = _fanout(
        run_env,
        project_id=project.id,
        children=[_child(task_id=child)],
        idempotency_key="fanout-replay",
        run_id=run_id,
    )
    counts = _counts(run_env.writer)
    second = _fanout(
        run_env,
        project_id=project.id,
        children=[_child(task_id=child)],
        idempotency_key="fanout-replay",
        run_id=run_id,
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(run_env.writer) == counts


def test_fanout_mismatch_fails_before_any_mutation(run_env) -> None:
    project = _create_project(run_env)
    child = generate_lowercase_ulid()
    _fanout(
        run_env,
        project_id=project.id,
        children=[_child(task_id=child)],
        idempotency_key="fanout-mismatch",
    )
    counts = _counts(run_env.writer)
    with pytest.raises(ReceiptMismatchError):
        _fanout(
            run_env,
            project_id=project.id,
            children=[_child(task_id=generate_lowercase_ulid())],
            idempotency_key="fanout-mismatch",
        )
    assert _counts(run_env.writer) == counts


def test_fanout_requires_validation(run_env) -> None:
    project = _create_project(run_env)
    with pytest.raises(RunValidationError):
        _fanout(run_env, project_id="", children=[_child()])
    with pytest.raises(RunValidationError):
        _fanout(run_env, project_id=project.id, children="not-an-array")
    with pytest.raises(RunValidationError):
        _fanout(run_env, project_id=project.id, children=[_child(capability="")])
    with pytest.raises(RunValidationError):
        _fanout(
            run_env,
            project_id=project.id,
            children=[_child(spec="not-an-object")],
        )
    with pytest.raises(RunValidationError):
        _fanout(run_env, project_id=project.id, children=[_child()], actor_kind="scheduler")
    # A duplicate run id is typed before any stream/row insert.
    run_id = generate_lowercase_ulid()
    _fanout(
        run_env,
        project_id=project.id,
        children=[_child()],
        run_id=run_id,
        idempotency_key="fanout-dup-1",
    )
    with pytest.raises(RunAlreadyExistsError):
        _fanout(
            run_env,
            project_id=project.id,
            children=[_child()],
            run_id=run_id,
            idempotency_key="fanout-dup-2",
        )
    with pytest.raises(RunRepositoryError):
        _fanout(run_env, project_id=project.id, children="bad")


def test_fanout_no_evidence_or_parent_task(run_env) -> None:
    project = _create_project(run_env)
    child = generate_lowercase_ulid()
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[_child(task_id=child)],
        idempotency_key="fanout-evidence",
    )
    # Zero evidence rows, empty evidence id list, no task named after the run.
    assert _counts(run_env.writer)[6] == 0
    assert result.evidence_ids == ()
    assert _task_row(run_env.writer, result.run_id) is None
    # The run read model round-trips the stored projection.
    run_row = _run_row(run_env.writer, result.run_id)
    model = RunReadModel.from_mapping(
        {
            **{k: run_row[k] for k in ("id", "project_id", "kind", "status", "title", "started_at", "finished_at")},
            "input": json.loads(run_row["input_json"]),
            "result": json.loads(run_row["result_json"]),
            "event_head_seq": 1,
        }
    )
    assert model.id == result.run_id
    assert model.status == "running"
    assert model.event_head_seq == 1


# ---------------------------------------------------------------------------
# Pure continuation-envelope validation
# ---------------------------------------------------------------------------


def test_validate_continuation_envelope_accepts_valid_envelope(run_env) -> None:
    project = _create_project(run_env)
    run_id = generate_lowercase_ulid()
    counts = _counts(run_env.writer)
    envelope = RunRepository.validate_continuation_envelope(
        {
            "run_id": run_id,
            "project_id": project.id,
            "start_ordinal": 0,
            "end_ordinal": 255,
            "max_children": 256,
        }
    )
    assert isinstance(envelope, ContinuationEnvelope)
    assert envelope.run_id == run_id
    assert envelope.start_ordinal == 0
    assert envelope.end_ordinal == 255
    assert envelope.max_children == 256
    # Validation is pure: zero rows written.
    assert _counts(run_env.writer) == counts


def test_validate_continuation_envelope_rejects_violations(run_env) -> None:
    project = _create_project(run_env)
    base = {
        "run_id": generate_lowercase_ulid(),
        "project_id": project.id,
        "start_ordinal": 0,
        "end_ordinal": 3,
        "max_children": 4,
    }
    counts = _counts(run_env.writer)

    with pytest.raises(ContinuationValidationError) as excinfo:
        RunRepository.validate_continuation_envelope("not-an-object")
    assert excinfo.value.field is None

    with pytest.raises(ContinuationValidationError) as excinfo:
        RunRepository.validate_continuation_envelope({k: v for k, v in base.items() if k != "run_id"})
    assert excinfo.value.field == "run_id"

    with pytest.raises(ContinuationValidationError) as excinfo:
        RunRepository.validate_continuation_envelope({**base, "start_ordinal": -1})
    assert excinfo.value.field == "start_ordinal"

    with pytest.raises(ContinuationValidationError) as excinfo:
        RunRepository.validate_continuation_envelope({**base, "end_ordinal": 256})
    assert excinfo.value.field == "end_ordinal"

    with pytest.raises(ContinuationValidationError) as excinfo:
        RunRepository.validate_continuation_envelope({**base, "end_ordinal": 2, "start_ordinal": 5})
    assert excinfo.value.field == "end_ordinal"

    with pytest.raises(ContinuationValidationError) as excinfo:
        RunRepository.validate_continuation_envelope({**base, "max_children": 0})
    assert excinfo.value.field == "max_children"

    with pytest.raises(ContinuationValidationError) as excinfo:
        RunRepository.validate_continuation_envelope({**base, "max_children": 3})
    assert excinfo.value.field == "max_children"

    with pytest.raises(ContinuationValidationError) as excinfo:
        RunRepository.validate_continuation_envelope({**base, "start_ordinal": True})
    assert excinfo.value.field == "start_ordinal"

    assert _counts(run_env.writer) == counts


# ---------------------------------------------------------------------------
# Receipt-linked continuation command (m3 plan step 2, T2_impl)
# ---------------------------------------------------------------------------


def _continue_run(
    env,
    *,
    project_id: str,
    run_id: str,
    expected_version: int,
    start_ordinal: int,
    children,
    idempotency_key: str = "continue-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "run_id": run_id,
        "expected_version": expected_version,
        "start_ordinal": start_ordinal,
        "children": children,
        "idempotency_key": idempotency_key,
        "now": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.run_repo.continue_run(u, **args)
    )


def _run_stream_head(writer: DatabaseWriter, run_id: str) -> int:
    return int(
        _stream_row(writer, f"{run_id}:{CORE_RUN_STREAM_TYPE}")["head_seq"]
    )


def _project_events(writer: DatabaseWriter, project_id: str):
    """Every project event ordered by project_seq (kind, event_id, stream)."""
    return writer.submit(
        lambda session: session.query(
            "SELECT e.kind, e.event_id, e.project_seq, s.stream_type, "
            "s.aggregate_id FROM events e "
            "JOIN event_streams s ON s.id = e.stream_id "
            "WHERE e.project_id = ? ORDER BY e.project_seq ASC",
            (project_id,),
        )
    )


def test_continue_run_extends_run_with_contiguous_ordinals(run_env) -> None:
    project = _create_project(run_env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    child_c = generate_lowercase_ulid()
    child_d = generate_lowercase_ulid()
    fanout = _fanout(
        run_env,
        project_id=project.id,
        children=[_child(task_id=child_a), _child(task_id=child_b)],
        idempotency_key="continue-fanout",
    )
    expected_version = _run_stream_head(run_env.writer, fanout.run_id)
    assert expected_version == 1

    result = _continue_run(
        run_env,
        project_id=project.id,
        run_id=fanout.run_id,
        expected_version=expected_version,
        start_ordinal=2,
        children=[_child(task_id=child_c), _child(task_id=child_d)],
        idempotency_key="continue-1",
    )
    assert result.run_id == fanout.run_id
    assert result.project_id == project.id
    assert result.task_ids == (child_c, child_d)
    assert result.first_ordinal == 2
    assert result.last_ordinal == 3
    assert result.expected_version == 1
    assert result.next_version == 2

    # The continuation advanced the run stream head by exactly one and the
    # children carry stable contiguous ordinals after the original chunk.
    assert _run_stream_head(run_env.writer, fanout.run_id) == 2
    assert _task_row(run_env.writer, child_a)["run_ordinal"] == 0
    assert _task_row(run_env.writer, child_b)["run_ordinal"] == 1
    assert _task_row(run_env.writer, child_c)["run_ordinal"] == 2
    assert _task_row(run_env.writer, child_d)["run_ordinal"] == 3
    assert _task_row(run_env.writer, child_c)["run_id"] == fanout.run_id
    assert _task_row(run_env.writer, child_d)["run_id"] == fanout.run_id
    # The read model round-trips from its stored receipt result.
    assert RunContinuationReadModel.from_mapping(result.to_dict()) == result


def test_continue_run_emits_continuation_event_before_child_events(run_env) -> None:
    project = _create_project(run_env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    child_c = generate_lowercase_ulid()
    child_d = generate_lowercase_ulid()
    fanout = _fanout(
        run_env,
        project_id=project.id,
        children=[_child(task_id=child_a), _child(task_id=child_b)],
        idempotency_key="continue-order-fanout",
    )
    run_stream = f"{fanout.run_id}:{CORE_RUN_STREAM_TYPE}"
    result = _continue_run(
        run_env,
        project_id=project.id,
        run_id=fanout.run_id,
        expected_version=1,
        start_ordinal=2,
        children=[_child(task_id=child_c), _child(task_id=child_d)],
        idempotency_key="continue-order",
    )

    # Project event order (project.created aside): run.created, child_a,
    # child_b, then the continuation event, then child_c, child_d.
    events = [
        e
        for e in _project_events(run_env.writer, project.id)
        if e["kind"] != "core.project.created"
    ]
    assert [e["kind"] for e in events] == [
        CORE_RUN_CREATED_EVENT_KIND,
        CORE_TASK_CREATED_EVENT_KIND,
        CORE_TASK_CREATED_EVENT_KIND,
        CORE_RUN_CONTINUED_EVENT_KIND,
        CORE_TASK_CREATED_EVENT_KIND,
        CORE_TASK_CREATED_EVENT_KIND,
    ]
    continued = events[3]
    assert continued["stream_type"] == CORE_RUN_STREAM_TYPE
    assert continued["aggregate_id"] == fanout.run_id
    assert json.loads(
        _event_rows(run_env.writer, run_stream)[1]["payload_json"]
    )["data"] == {
        "run_id": fanout.run_id,
        "expected_version": 1,
        "start_ordinal": 2,
        "child_count": 2,
        "first_ordinal": 2,
        "last_ordinal": 3,
        "next_version": 2,
    }

    # One complete receipt: continuation event first, then ordered child
    # events, spanning the exact project-seq range, with the full result.
    receipt = _receipt_row(run_env.writer, project.id, "continue-order")
    assert receipt is not None
    assert receipt["command_kind"] == CORE_RUN_CONTINUE_COMMAND_KIND
    assert receipt["primary_stream_id"] == run_stream
    assert receipt["resulting_stream_seq"] == 2
    event_ids = json.loads(receipt["event_ids_json"])
    assert event_ids == [e["event_id"] for e in events[3:]]
    assert receipt["first_project_seq"] == events[3]["project_seq"]
    assert receipt["last_project_seq"] == events[5]["project_seq"]
    stored = json.loads(receipt["result_json"])
    assert stored == result.to_dict()
    assert stored["task_ids"] == [child_c, child_d]
    assert stored["first_ordinal"] == 2 and stored["last_ordinal"] == 3
    assert stored["next_version"] == 2
    # The continuation event chains on the run stream after run.created.
    run_events = _event_rows(run_env.writer, run_stream)
    assert [e["kind"] for e in run_events] == [
        CORE_RUN_CREATED_EVENT_KIND,
        CORE_RUN_CONTINUED_EVENT_KIND,
    ]
    assert run_events[0]["seq"] == 1 and run_events[1]["seq"] == 2


def test_continue_run_rejects_missing_and_foreign_runs(run_env) -> None:
    project = _create_project(run_env)
    counts = _counts(run_env.writer)
    missing = generate_lowercase_ulid()
    with pytest.raises(RunNotFoundError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=missing,
            expected_version=0,
            start_ordinal=0,
            children=[_child()],
            idempotency_key="continue-missing",
        )
    assert _counts(run_env.writer) == counts
    # A run that belongs to another project is foreign: never visible.
    other = _create_project(run_env, slug="beta")
    foreign_run = _fanout(
        run_env,
        project_id=other.id,
        children=[_child()],
        idempotency_key="continue-foreign-fanout",
    )
    counts = _counts(run_env.writer)
    with pytest.raises(RunNotFoundError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=foreign_run.run_id,
            expected_version=1,
            start_ordinal=0,
            children=[_child()],
            idempotency_key="continue-foreign",
        )
    assert _counts(run_env.writer) == counts


def test_continue_run_rejects_terminal_run(run_env) -> None:
    project = _create_project(run_env)
    child = generate_lowercase_ulid()
    fanout = _fanout(
        run_env,
        project_id=project.id,
        children=[_child(task_id=child)],
        idempotency_key="continue-terminal-fanout",
    )
    # Drive the run terminal via group cancel (the only child is queued).
    UnitOfWork(run_env.writer).run(
        lambda u: run_env.run_repo.cancel(
            u,
            project_id=project.id,
            run_id=fanout.run_id,
            idempotency_key="continue-terminal-cancel",
            now=TS,
        )
    )
    assert _run_row(run_env.writer, fanout.run_id)["status"] == "cancelled"
    counts = _counts(run_env.writer)
    with pytest.raises(RunTerminalError) as excinfo:
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=2,
            start_ordinal=1,
            children=[_child()],
            idempotency_key="continue-terminal",
        )
    assert excinfo.value.status == "cancelled"
    assert _counts(run_env.writer) == counts


def test_continue_run_rejects_stale_head_before_mutation(run_env) -> None:
    project = _create_project(run_env)
    child = generate_lowercase_ulid()
    fanout = _fanout(
        run_env,
        project_id=project.id,
        children=[_child(task_id=child)],
        idempotency_key="continue-stale-fanout",
    )
    counts = _counts(run_env.writer)
    # A stale (behind) head and an ahead-of-head CAS both change zero rows.
    with pytest.raises(RunStaleHeadError) as excinfo:
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=0,
            start_ordinal=1,
            children=[_child()],
            idempotency_key="continue-stale",
        )
    assert excinfo.value.expected_version == 0
    assert excinfo.value.current_version == 1
    with pytest.raises(RunStaleHeadError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=5,
            start_ordinal=1,
            children=[_child()],
            idempotency_key="continue-ahead",
        )
    assert _counts(run_env.writer) == counts


def test_continue_run_rejects_gap_and_overlap_ordinals(run_env) -> None:
    project = _create_project(run_env)
    child = generate_lowercase_ulid()
    fanout = _fanout(
        run_env,
        project_id=project.id,
        children=[_child(task_id=child)],
        idempotency_key="continue-ordinal-fanout",
    )
    counts = _counts(run_env.writer)
    # A gap (next free ordinal is 1, caller says 5) is rejected.
    with pytest.raises(RunValidationError) as excinfo:
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=5,
            children=[_child()],
            idempotency_key="continue-gap",
        )
    assert "contiguous" in str(excinfo.value)
    # An overlap (ordinal 1 already... ordinal 0 exists, so 0 overlaps).
    with pytest.raises(RunValidationError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=0,
            children=[_child()],
            idempotency_key="continue-overlap",
        )
    assert _counts(run_env.writer) == counts


def test_continue_run_rejects_later_child_and_cross_project_dependencies(
    run_env,
) -> None:
    project_a = _create_project(run_env, slug="alpha")
    project_b = _create_project(run_env, slug="beta")
    earlier = generate_lowercase_ulid()
    fanout = _fanout(
        run_env,
        project_id=project_a.id,
        children=[_child(task_id=earlier)],
        idempotency_key="continue-dep-fanout",
    )
    foreign_task = generate_lowercase_ulid()
    UnitOfWork(run_env.writer).run(
        lambda u: (
            u.execute(
                "INSERT INTO event_streams "
                "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
                "VALUES (?, ?, 'core.task', ?, 0, ?)",
                (
                    f"{foreign_task}:{CORE_TASK_STREAM_TYPE}",
                    project_b.id,
                    foreign_task,
                    TS,
                ),
            ),
            u.execute(
                "INSERT INTO tasks "
                "(id, project_id, event_stream_id, capability, spec_json, "
                "spec_hash, input_manifest_json, status, priority, available_at, "
                "max_attempts, created_at, updated_at) "
                "VALUES (?, ?, ?, 'foreign.capability', '{}', ?, '[]', 'queued', "
                "0, ?, 1, ?, ?)",
                (
                    foreign_task,
                    project_b.id,
                    f"{foreign_task}:{CORE_TASK_STREAM_TYPE}",
                    "x" * 64,
                    TS,
                    TS,
                    TS,
                ),
            ),
        )
    )
    counts = _counts(run_env.writer)
    # Cross-project dependency in a continuation chunk -> typed error.
    with pytest.raises(TaskDependencyError) as excinfo:
        _continue_run(
            run_env,
            project_id=project_a.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=1,
            children=[
                _child(
                    dependencies=[
                        {"task_id": foreign_task, "kind": "hard", "ordinal": 0}
                    ]
                )
            ],
            idempotency_key="continue-cross",
        )
    assert excinfo.value.reason == "cross_project"
    # A dependency on a later child of the same chunk is typed missing: the
    # later child does not exist yet when the earlier one is created.
    later = generate_lowercase_ulid()
    with pytest.raises(TaskDependencyError) as excinfo:
        _continue_run(
            run_env,
            project_id=project_a.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=1,
            children=[
                _child(
                    task_id=generate_lowercase_ulid(),
                    dependencies=[
                        {"task_id": later, "kind": "hard", "ordinal": 0}
                    ],
                ),
                _child(task_id=later),
            ],
            idempotency_key="continue-later-child",
        )
    assert excinfo.value.reason == "missing"
    # A dependency on an earlier child of the same chunk resolves fine.
    resolved = _continue_run(
        run_env,
        project_id=project_a.id,
        run_id=fanout.run_id,
        expected_version=1,
        start_ordinal=1,
        children=[
            _child(
                task_id=generate_lowercase_ulid(),
                dependencies=[
                    {"task_id": earlier, "kind": "hard", "ordinal": 0}
                ],
            )
        ],
        idempotency_key="continue-early-dep",
    )
    assert len(resolved.task_ids) == 1
    assert _counts(run_env.writer) != counts


def test_continue_run_rejects_chunk_bound_violations(run_env) -> None:
    project = _create_project(run_env)
    # A 257-child chunk is rejected before any mutation.
    counts = _counts(run_env.writer)
    with pytest.raises(RunValidationError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=generate_lowercase_ulid(),
            expected_version=0,
            start_ordinal=0,
            children=[_child() for _ in range(FROZEN_MAX_DIRECT_CHILDREN + 1)],
            idempotency_key="continue-257",
        )
    assert _counts(run_env.writer) == counts
    # A chunk that would push ordinals past 255 is rejected even though the
    # chunk itself is at most 256 children.
    fanout = _fanout(
        run_env,
        project_id=project.id,
        children=[_child() for _ in range(255)],
        idempotency_key="continue-bound-fanout",
    )
    counts = _counts(run_env.writer)
    with pytest.raises(RunValidationError) as excinfo:
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=255,
            children=[_child(), _child()],
            idempotency_key="continue-bound",
        )
    assert "ordinal bound" in str(excinfo.value)
    assert _counts(run_env.writer) == counts


def test_continue_run_replay_returns_stored_result_with_zero_new_rows(
    run_env,
) -> None:
    project = _create_project(run_env)
    child = generate_lowercase_ulid()
    fanout = _fanout(
        run_env,
        project_id=project.id,
        children=[_child()],
        idempotency_key="continue-replay-fanout",
    )
    first = _continue_run(
        run_env,
        project_id=project.id,
        run_id=fanout.run_id,
        expected_version=1,
        start_ordinal=1,
        children=[_child(task_id=child)],
        idempotency_key="continue-replay",
    )
    counts = _counts(run_env.writer)
    second = _continue_run(
        run_env,
        project_id=project.id,
        run_id=fanout.run_id,
        expected_version=1,
        start_ordinal=1,
        children=[_child(task_id=child)],
        idempotency_key="continue-replay",
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(run_env.writer) == counts


def test_continue_run_mismatch_fails_before_any_mutation(run_env) -> None:
    project = _create_project(run_env)
    fanout = _fanout(
        run_env,
        project_id=project.id,
        children=[_child()],
        idempotency_key="continue-mismatch-fanout",
    )
    _continue_run(
        run_env,
        project_id=project.id,
        run_id=fanout.run_id,
        expected_version=1,
        start_ordinal=1,
        children=[_child(task_id=generate_lowercase_ulid())],
        idempotency_key="continue-mismatch",
    )
    counts = _counts(run_env.writer)
    with pytest.raises(ReceiptMismatchError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=1,
            children=[_child(task_id=generate_lowercase_ulid())],
            idempotency_key="continue-mismatch",
        )
    assert _counts(run_env.writer) == counts


def test_continue_run_validation(run_env) -> None:
    project = _create_project(run_env)
    fanout = _fanout(
        run_env,
        project_id=project.id,
        children=[_child()],
        idempotency_key="continue-validate-fanout",
    )
    counts = _counts(run_env.writer)
    with pytest.raises(RunValidationError):
        _continue_run(
            run_env,
            project_id="",
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=1,
            children=[_child()],
        )
    with pytest.raises(RunValidationError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=-1,
            start_ordinal=1,
            children=[_child()],
        )
    with pytest.raises(RunValidationError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=True,
            start_ordinal=1,
            children=[_child()],
        )
    with pytest.raises(RunValidationError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=-1,
            children=[_child()],
        )
    with pytest.raises(RunValidationError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=256,
            children=[_child()],
        )
    with pytest.raises(RunValidationError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=1,
            children=[],
        )
    with pytest.raises(RunValidationError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=1,
            children="not-an-array",
        )
    with pytest.raises(RunValidationError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=1,
            children=[_child(capability="")],
        )
    with pytest.raises(RunRepositoryError):
        _continue_run(
            run_env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=1,
            children="bad",
        )
    assert _counts(run_env.writer) == counts


def test_continue_run_keeps_plan_and_step_tables_absent(run_env) -> None:
    project = _create_project(run_env)
    fanout = _fanout(
        run_env,
        project_id=project.id,
        children=[_child()],
        idempotency_key="continue-forbidden-fanout",
    )
    _continue_run(
        run_env,
        project_id=project.id,
        run_id=fanout.run_id,
        expected_version=1,
        start_ordinal=1,
        children=[_child()],
        idempotency_key="continue-forbidden",
    )
    present = run_env.writer.submit(
        lambda session: {
            row[0]
            for row in session.query(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    )
    for forbidden in FORBIDDEN_TABLES:
        assert forbidden not in present


# ---------------------------------------------------------------------------
# Derived group progress, cancel, and retry (m2 plan step 13, T22)
# ---------------------------------------------------------------------------


def _task_repo(env):
    """A task repository over the run environment's event/receipt services.

    The run repository builds its own stateless task repository for group
    operations; tests build one the same way to drive child transitions.
    """
    return TaskRepository(
        events=env.run_repo._events, receipts=env.run_repo._receipts
    )


def _claim_child(env, *, project_id: str, idempotency_key: str):
    return UnitOfWork(env.writer).run(
        lambda u: _task_repo(env).claim(
            u,
            project_id=project_id,
            idempotency_key=idempotency_key,
            executor_id="executor-1",
            now=TS,
        )
    )


def _start_child(env, *, project_id: str, claim, idempotency_key: str):
    return UnitOfWork(env.writer).run(
        lambda u: _task_repo(env).start(
            u,
            project_id=project_id,
            task_id=claim.task.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=1,
            idempotency_key=idempotency_key,
            now=TS,
        )
    )


def _fail_child(
    env,
    *,
    project_id: str,
    task_id: str,
    attempt_id: str,
    lease_id: str,
    status_version: int,
    idempotency_key: str,
):
    def run(u):
        return _task_repo(env).fail(
            u,
            project_id=project_id,
            task_id=task_id,
            attempt_id=attempt_id,
            lease_id=lease_id,
            expected_status_version=status_version,
            idempotency_key=idempotency_key,
            now=TS,
            error={"kind": "group.fixture", "message": "intentional failure"},
        )

    return UnitOfWork(env.writer).run(run)


def _fail_started_child(env, *, project_id: str, claim, idempotency_key: str):
    """Start the claimed child and fail its owned attempt in one cycle.

    The task requeues when ``max_attempts`` budget remains and fails
    terminally when exhausted (the shared budget rule).
    """
    started = _start_child(
        env,
        project_id=project_id,
        claim=claim,
        idempotency_key=f"{idempotency_key}:start",
    )
    return _fail_child(
        env,
        project_id=project_id,
        task_id=claim.task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        status_version=started.status_version,
        idempotency_key=f"{idempotency_key}:fail",
    )


def _group_cancel(
    env, *, project_id: str, run_id: str, idempotency_key: str = "group-cancel-k", **overrides
):
    args = {
        "project_id": project_id,
        "run_id": run_id,
        "idempotency_key": idempotency_key,
        "now": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.run_repo.cancel(u, **args))


def _group_retry(
    env, *, project_id: str, run_id: str, idempotency_key: str = "group-retry-k", **overrides
):
    args = {
        "project_id": project_id,
        "run_id": run_id,
        "idempotency_key": idempotency_key,
        "now": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.run_repo.retry(u, **args))


def _run_result_json(writer: DatabaseWriter, run_id: str) -> dict:
    return json.loads(_run_row(writer, run_id)["result_json"])


def _attempt_rows(writer: DatabaseWriter, task_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM execution_attempts WHERE task_id = ? "
            "ORDER BY attempt_no ASC",
            (task_id,),
        )
    )


def test_group_cancel_cancels_eligible_children_and_recomputes_projection(run_env) -> None:
    project = _create_project(run_env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    child_c = generate_lowercase_ulid()
    child_d = generate_lowercase_ulid()
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[
            _child(task_id=child_a, priority=3),
            _child(
                task_id=child_b,
                priority=2,
                dependencies=[{"task_id": child_a, "kind": "hard", "ordinal": 0}],
            ),
            _child(
                task_id=child_c,
                priority=1,
                dependencies=[{"task_id": child_a, "kind": "soft", "ordinal": 0}],
            ),
            _child(task_id=child_d, priority=0),
        ],
        idempotency_key="group-cancel-setup",
    )
    # Hard/soft dependency gating: the hard-dependent child is blocked and
    # the soft-dependent child queued; the group cancel must reach both.
    assert _task_row(run_env.writer, child_a)["status"] == "queued"
    assert _task_row(run_env.writer, child_b)["status"] == "blocked"
    assert _task_row(run_env.writer, child_c)["status"] == "queued"

    counts_before = _counts(run_env.writer)
    cancelled = _group_cancel(
        run_env,
        project_id=project.id,
        run_id=result.run_id,
        idempotency_key="group-cancel-k",
        cancel_request_id="req-cancel-1",
    )
    assert isinstance(cancelled, RunCancelReadModel)
    assert cancelled.cancelled_task_ids == (child_a, child_b, child_c, child_d)
    assert cancelled.skipped_task_ids == ()
    assert cancelled.cancel_request_id == "req-cancel-1"
    # The recomputed projection: every child terminal -> cancelled.
    assert cancelled.run["status"] == "cancelled"
    assert cancelled.run["total_children"] == 4
    assert cancelled.run["succeeded"] == 0
    assert cancelled.run["failed"] == 0
    assert cancelled.run["cancelled"] == 4

    # Children reached the terminal cancelled state with the shared group
    # request id; their streams carry created then cancelled.
    for child_id in (child_a, child_b, child_c, child_d):
        row = _task_row(run_env.writer, child_id)
        assert row["status"] == "cancelled"
        assert row["cancel_request_id"] == "req-cancel-1"
        assert row["finished_at"] == TS
        assert [
            event["kind"]
            for event in _event_rows(run_env.writer, f"{child_id}:{CORE_TASK_STREAM_TYPE}")
        ] == [CORE_TASK_CREATED_EVENT_KIND, CORE_TASK_CANCELLED_EVENT_KIND]

    # The run row: cancelled with finished_at stamped and the derived
    # projection persisted.
    run_row = _run_row(run_env.writer, result.run_id)
    assert run_row["status"] == "cancelled"
    assert run_row["finished_at"] == TS
    assert _run_result_json(run_env.writer, result.run_id) == {
        "total_children": 4,
        "succeeded": 0,
        "failed": 0,
        "cancelled": 4,
        "status": "cancelled",
    }

    # The run stream carries created then cancelled; the run event records
    # the group request id, the cancelled/skipped ids, and the projection.
    run_stream = f"{result.run_id}:{CORE_RUN_STREAM_TYPE}"
    run_events = _event_rows(run_env.writer, run_stream)
    assert [event["kind"] for event in run_events] == [
        CORE_RUN_CREATED_EVENT_KIND,
        CORE_RUN_CANCELLED_EVENT_KIND,
    ]
    cancelled_event = json.loads(run_events[1]["payload_json"])["data"]
    assert cancelled_event["cancel_request_id"] == "req-cancel-1"
    assert cancelled_event["cancelled_task_ids"] == [child_a, child_b, child_c, child_d]
    assert cancelled_event["skipped_task_ids"] == []
    assert cancelled_event["status"] == "cancelled"

    # One run-level receipt (core.run.cancel) whose ordered event ids end
    # with the run event and span the exact project-seq range.
    receipt = _receipt_row(run_env.writer, project.id, "group-cancel-k")
    assert receipt is not None
    assert receipt["command_kind"] == CORE_RUN_CANCEL_COMMAND_KIND
    assert receipt["primary_stream_id"] == run_stream
    event_ids = json.loads(receipt["event_ids_json"])
    assert len(event_ids) == 5
    assert event_ids[-1] == run_events[1]["event_id"]
    assert receipt["first_project_seq"] == run_events[1]["project_seq"] - 4
    assert receipt["last_project_seq"] == run_events[1]["project_seq"]
    # Per-child receipts exist with the derived keys (shared predicate).
    for ordinal in range(4):
        child_receipt = _receipt_row(
            run_env.writer, project.id, f"group-cancel-k:child:{ordinal}"
        )
        assert child_receipt is not None
        assert child_receipt["command_kind"] == CORE_TASK_CANCEL_COMMAND_KIND

    # Counts: +5 events (four child cancelled + one run cancelled), +5
    # receipts (four child + one run). No parent task or evidence rows were
    # created.
    counts_after = _counts(run_env.writer)
    assert counts_after[2] == counts_before[2] + 5
    assert counts_after[3] == counts_before[3] + 5
    assert _task_row(run_env.writer, result.run_id) is None
    assert counts_after[6] == counts_before[6]


def test_group_cancel_skips_terminal_and_cooperatively_cancels_running_children(run_env) -> None:
    project = _create_project(run_env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[
            _child(task_id=child_a, priority=3, max_attempts=1),
            _child(task_id=child_b, priority=2),
            _child(task_id=generate_lowercase_ulid(), priority=1),
        ],
        idempotency_key="group-cancel-partial-setup",
    )
    child_c = result.task_ids[2]
    # Child A fails terminally (max_attempts 1); child B runs (claimed and
    # started) — claims proceed in priority order.
    claim_a = _claim_child(run_env, project_id=project.id, idempotency_key="partial-claim-a")
    assert claim_a is not None and claim_a.task.id == child_a
    _fail_started_child(run_env, project_id=project.id, claim=claim_a, idempotency_key="partial-fail-a")
    claim_b = _claim_child(run_env, project_id=project.id, idempotency_key="partial-claim-b")
    assert claim_b is not None and claim_b.task.id == child_b
    _start_child(run_env, project_id=project.id, claim=claim_b, idempotency_key="partial-start-b")
    assert _task_row(run_env.writer, child_a)["status"] == "failed"
    assert _task_row(run_env.writer, child_b)["status"] == "running"

    cancelled = _group_cancel(
        run_env, project_id=project.id, run_id=result.run_id,
        idempotency_key="group-cancel-partial-k",
    )
    # C is queued and B is running; both are group-cancellable. A is already
    # terminal and is the only skipped child. Running cancellation is
    # cooperative and reports B explicitly.
    assert cancelled.cancelled_task_ids == (child_b, child_c)
    assert cancelled.skipped_task_ids == (child_a,)
    assert cancelled.cooperative_task_ids == (child_b,)
    # Every child is terminal, so the failed child determines the run status.
    assert cancelled.run["status"] == "failed"
    assert cancelled.run["failed"] == 1
    assert cancelled.run["cancelled"] == 2
    run_row = _run_row(run_env.writer, result.run_id)
    assert run_row["status"] == "failed"
    assert run_row["finished_at"] == TS
    assert _task_row(run_env.writer, child_b)["status"] == "cancelled"


def test_group_cancel_and_retry_reject_terminal_run_before_mutation(run_env) -> None:
    project = _create_project(run_env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[
            _child(task_id=child_a, priority=3, max_attempts=1),
            _child(task_id=child_b, priority=2),
        ],
        idempotency_key="group-terminal-setup",
    )
    claim_a = _claim_child(run_env, project_id=project.id, idempotency_key="term-claim-a")
    assert claim_a is not None and claim_a.task.id == child_a
    _fail_started_child(run_env, project_id=project.id, claim=claim_a, idempotency_key="term-fail-a")
    # After the group cancel every child is terminal; child A failed first,
    # so the derived run status is failed.
    cancelled = _group_cancel(run_env, project_id=project.id, run_id=result.run_id, idempotency_key="term-cancel-k")
    assert cancelled.run["status"] == "failed"
    assert _run_row(run_env.writer, result.run_id)["status"] == "failed"

    # A terminal run never continues: both group commands reject it before
    # any mutation, with zero new rows.
    counts = _counts(run_env.writer)
    with pytest.raises(RunTerminalError) as excinfo:
        _group_cancel(run_env, project_id=project.id, run_id=result.run_id, idempotency_key="term-cancel-2")
    assert excinfo.value.run_id == result.run_id
    assert excinfo.value.status == "failed"
    # Failed invocation runs are deliberately recoverable once; selecting an
    # already-cancelled child still fails before mutation through the shared
    # task terminal fence.
    with pytest.raises(TaskTransitionError) as excinfo:
        _group_retry(
            run_env,
            project_id=project.id,
            run_id=result.run_id,
            idempotency_key="term-retry-k",
            selected_task_ids=[child_b],
        )
    assert excinfo.value.reason == "task_terminal"
    assert _counts(run_env.writer) == counts

    # A fully-cancelled run is equally terminal for retry.
    result2 = _fanout(
        run_env,
        project_id=project.id,
        children=[_child()],
        idempotency_key="group-terminal-setup-2",
        run_id=generate_lowercase_ulid(),
    )
    _group_cancel(run_env, project_id=project.id, run_id=result2.run_id, idempotency_key="term-cancel-3")
    assert _run_row(run_env.writer, result2.run_id)["status"] == "cancelled"
    with pytest.raises(RunTerminalError) as excinfo:
        _group_retry(run_env, project_id=project.id, run_id=result2.run_id, idempotency_key="term-retry-2")
    assert excinfo.value.status == "cancelled"


def test_group_cancel_replay_and_mismatch(run_env) -> None:
    project = _create_project(run_env)
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[
            _child(task_id=generate_lowercase_ulid()),
            _child(task_id=generate_lowercase_ulid()),
        ],
        idempotency_key="group-cancel-replay-setup",
    )
    first = _group_cancel(
        run_env,
        project_id=project.id,
        run_id=result.run_id,
        idempotency_key="group-cancel-replay-k",
        cancel_request_id="req-1",
    )
    counts = _counts(run_env.writer)
    second = _group_cancel(
        run_env,
        project_id=project.id,
        run_id=result.run_id,
        idempotency_key="group-cancel-replay-k",
        cancel_request_id="req-1",
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(run_env.writer) == counts
    # A changed request under the same key is a mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _group_cancel(
            run_env,
            project_id=project.id,
            run_id=result.run_id,
            idempotency_key="group-cancel-replay-k",
            cancel_request_id="req-2",
        )
    assert _counts(run_env.writer) == counts


def test_group_cancel_with_no_cancellable_children_raises(run_env) -> None:
    project = _create_project(run_env)
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[],
        idempotency_key="group-cancel-none-setup",
    )
    counts = _counts(run_env.writer)
    with pytest.raises(RunValidationError) as excinfo:
        _group_cancel(run_env, project_id=project.id, run_id=result.run_id, idempotency_key="group-cancel-none-k")
    assert "no cancellable children" in str(excinfo.value)
    assert _counts(run_env.writer) == counts


def test_group_retry_all_eligible_restarts_failed_children(run_env) -> None:
    project = _create_project(run_env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    child_c = generate_lowercase_ulid()
    child_d = generate_lowercase_ulid()
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[
            _child(task_id=child_a, priority=3, max_attempts=2),
            _child(task_id=child_b, priority=2, max_attempts=2),
            _child(task_id=child_c, priority=1, max_attempts=2),
            _child(task_id=child_d, priority=0, max_attempts=1),
        ],
        idempotency_key="group-retry-setup",
    )
    # Claims proceed in priority order while higher-priority children run;
    # fails happen in reverse order so a requeued child is never re-claimed.
    claim_a = _claim_child(run_env, project_id=project.id, idempotency_key="retry-claim-a")
    assert claim_a is not None and claim_a.task.id == child_a
    _start_child(run_env, project_id=project.id, claim=claim_a, idempotency_key="retry-start-a")
    claim_b = _claim_child(run_env, project_id=project.id, idempotency_key="retry-claim-b")
    assert claim_b is not None and claim_b.task.id == child_b
    _start_child(run_env, project_id=project.id, claim=claim_b, idempotency_key="retry-start-b")
    claim_c = _claim_child(run_env, project_id=project.id, idempotency_key="retry-claim-c")
    assert claim_c is not None and claim_c.task.id == child_c
    _start_child(run_env, project_id=project.id, claim=claim_c, idempotency_key="retry-start-c")
    claim_d = _claim_child(run_env, project_id=project.id, idempotency_key="retry-claim-d")
    assert claim_d is not None and claim_d.task.id == child_d
    _fail_started_child(run_env, project_id=project.id, claim=claim_d, idempotency_key="retry-fail-d")
    _fail_child(
        run_env,
        project_id=project.id,
        task_id=child_c,
        attempt_id=claim_c.attempt.id,
        lease_id=claim_c.attempt.lease_id,
        status_version=2,
        idempotency_key="retry-fail-c",
    )
    _fail_child(
        run_env,
        project_id=project.id,
        task_id=child_b,
        attempt_id=claim_b.attempt.id,
        lease_id=claim_b.attempt.lease_id,
        status_version=2,
        idempotency_key="retry-fail-b",
    )

    # B and C are queued with one failed attempt each; A runs; D failed
    # terminally (its only attempt exhausted the budget).
    assert _task_row(run_env.writer, child_a)["status"] == "running"
    assert _task_row(run_env.writer, child_b)["status"] == "queued"
    assert _task_row(run_env.writer, child_c)["status"] == "queued"
    assert _task_row(run_env.writer, child_d)["status"] == "failed"

    counts_before = _counts(run_env.writer)
    retried = _group_retry(
        run_env, project_id=project.id, run_id=result.run_id,
        idempotency_key="group-retry-all-k",
    )
    assert isinstance(retried, RunRetryReadModel)
    # Only B and C are eligible; the running child and the terminal child
    # are skipped.
    assert retried.retried_task_ids == (child_b, child_c)
    assert retried.skipped_task_ids == (child_a, child_d)
    assert retried.run["status"] == "running"
    assert retried.run["failed"] == 1
    # Retried children are running again with a brand-new fenced attempt.
    for child_id in (child_b, child_c):
        row = _task_row(run_env.writer, child_id)
        assert row["status"] == "running"
        attempts = _attempt_rows(run_env.writer, child_id)
        assert [attempt["attempt_no"] for attempt in attempts] == [1, 2]
        assert attempts[1]["status"] == "claimed"
        assert attempts[1]["status_version"] == 1
    # A untouched; D still terminal failed.
    assert _task_row(run_env.writer, child_a)["status"] == "running"
    assert _task_row(run_env.writer, child_d)["status"] == "failed"
    # Run projection persisted: still running (nonterminal children exist).
    run_row = _run_row(run_env.writer, result.run_id)
    assert run_row["status"] == "running"
    assert run_row["finished_at"] is None
    assert _run_result_json(run_env.writer, result.run_id) == {
        "total_children": 4,
        "succeeded": 0,
        "failed": 1,
        "cancelled": 0,
        "status": "running",
    }
    # The run stream: created then retried, with the retried/skipped ids.
    run_events = _event_rows(run_env.writer, f"{result.run_id}:{CORE_RUN_STREAM_TYPE}")
    assert [event["kind"] for event in run_events] == [
        CORE_RUN_CREATED_EVENT_KIND,
        CORE_RUN_RETRIED_EVENT_KIND,
    ]
    retried_event = json.loads(run_events[1]["payload_json"])["data"]
    assert retried_event["retried_task_ids"] == [child_b, child_c]
    assert retried_event["skipped_task_ids"] == [child_a, child_d]
    assert retried_event["selected_task_ids"] is None
    assert retried_event["status"] == "running"
    # One run-level receipt keyed core.run.retry; per-child retry receipts
    # exist for the retried ordinals only.
    receipt = _receipt_row(run_env.writer, project.id, "group-retry-all-k")
    assert receipt is not None
    assert receipt["command_kind"] == CORE_RUN_RETRY_COMMAND_KIND
    for ordinal in (1, 2):
        child_receipt = _receipt_row(
            run_env.writer, project.id, f"group-retry-all-k:child:{ordinal}"
        )
        assert child_receipt is not None
        assert child_receipt["command_kind"] == CORE_TASK_RETRY_COMMAND_KIND
    # Counts: +3 events (two child retried + one run retried), +3 receipts.
    counts_after = _counts(run_env.writer)
    assert counts_after[2] == counts_before[2] + 3
    assert counts_after[3] == counts_before[3] + 3


def test_group_retry_selected_subset(run_env) -> None:
    project = _create_project(run_env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    child_c = generate_lowercase_ulid()
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[
            _child(task_id=child_a, priority=3, max_attempts=2),
            _child(task_id=child_b, priority=2, max_attempts=2),
            _child(task_id=child_c, priority=1, max_attempts=1),
        ],
        idempotency_key="group-retry-subset-setup",
    )
    claim_a = _claim_child(run_env, project_id=project.id, idempotency_key="subset-claim-a")
    assert claim_a is not None and claim_a.task.id == child_a
    _start_child(run_env, project_id=project.id, claim=claim_a, idempotency_key="subset-start-a")
    claim_b = _claim_child(run_env, project_id=project.id, idempotency_key="subset-claim-b")
    assert claim_b is not None and claim_b.task.id == child_b
    started_b = _start_child(run_env, project_id=project.id, claim=claim_b, idempotency_key="subset-start-b")
    claim_c = _claim_child(run_env, project_id=project.id, idempotency_key="subset-claim-c")
    assert claim_c is not None and claim_c.task.id == child_c
    _fail_started_child(run_env, project_id=project.id, claim=claim_c, idempotency_key="subset-fail-c")
    _fail_child(
        run_env,
        project_id=project.id,
        task_id=child_b,
        attempt_id=claim_b.attempt.id,
        lease_id=claim_b.attempt.lease_id,
        status_version=started_b.status_version,
        idempotency_key="subset-fail-b",
    )
    assert _task_row(run_env.writer, child_a)["status"] == "running"
    assert _task_row(run_env.writer, child_b)["status"] == "queued"
    assert _task_row(run_env.writer, child_c)["status"] == "failed"

    # Explicit subset: exactly the selected child is retried; unselected
    # children are untouched.
    retried = _group_retry(
        run_env,
        project_id=project.id,
        run_id=result.run_id,
        idempotency_key="group-retry-subset-k",
        selected_task_ids=[child_b],
    )
    assert retried.retried_task_ids == (child_b,)
    assert retried.skipped_task_ids == ()
    assert _task_row(run_env.writer, child_a)["status"] == "running"
    assert _task_row(run_env.writer, child_b)["status"] == "running"
    assert _task_row(run_env.writer, child_c)["status"] == "failed"
    attempts_b = _attempt_rows(run_env.writer, child_b)
    assert [attempt["attempt_no"] for attempt in attempts_b] == [1, 2]
    assert attempts_b[1]["status"] == "claimed"
    run_row = _run_row(run_env.writer, result.run_id)
    assert run_row["status"] == "running"

    # An ineligible selected child (terminal) raises the shared predicate's
    # typed outcome; one transaction, so nothing is half-retried.
    counts = _counts(run_env.writer)
    with pytest.raises(TaskTransitionError) as excinfo:
        _group_retry(
            run_env,
            project_id=project.id,
            run_id=result.run_id,
            idempotency_key="group-retry-subset-ineligible",
            selected_task_ids=[child_c],
        )
    assert excinfo.value.reason == "task_terminal"
    assert _counts(run_env.writer) == counts

    # A selection that names a non-child is rejected before any mutation.
    with pytest.raises(RunValidationError) as excinfo:
        _group_retry(
            run_env,
            project_id=project.id,
            run_id=result.run_id,
            idempotency_key="group-retry-subset-foreign",
            selected_task_ids=["not-a-child"],
        )
    assert "not direct children" in str(excinfo.value)
    assert _counts(run_env.writer) == counts


def test_group_retry_replay_and_mismatch(run_env) -> None:
    project = _create_project(run_env)
    child = generate_lowercase_ulid()
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[_child(task_id=child, priority=0, max_attempts=2)],
        idempotency_key="group-retry-replay-setup",
    )
    claim = _claim_child(run_env, project_id=project.id, idempotency_key="replay-claim")
    assert claim is not None and claim.task.id == child
    _fail_started_child(run_env, project_id=project.id, claim=claim, idempotency_key="replay-fail")

    first = _group_retry(run_env, project_id=project.id, run_id=result.run_id, idempotency_key="group-retry-replay-k")
    assert first.retried_task_ids == (child,)
    counts = _counts(run_env.writer)
    second = _group_retry(run_env, project_id=project.id, run_id=result.run_id, idempotency_key="group-retry-replay-k")
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(run_env.writer) == counts
    # The same key with a selection set is a different request: mismatch
    # before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _group_retry(
            run_env,
            project_id=project.id,
            run_id=result.run_id,
            idempotency_key="group-retry-replay-k",
            selected_task_ids=[child],
        )
    assert _counts(run_env.writer) == counts


def test_derive_progress_is_ordered_and_pure(run_env) -> None:
    project = _create_project(run_env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[
            _child(task_id=child_a, priority=3, max_attempts=1),
            _child(task_id=child_b, priority=2),
        ],
        idempotency_key="derive-progress-setup",
    )
    claim_a = _claim_child(run_env, project_id=project.id, idempotency_key="derive-claim-a")
    assert claim_a is not None and claim_a.task.id == child_a
    _fail_started_child(run_env, project_id=project.id, claim=claim_a, idempotency_key="derive-fail-a")

    progress = UnitOfWork(run_env.writer).run(
        lambda u: run_env.run_repo.derive_progress(
            u, project_id=project.id, run_id=result.run_id
        )
    )
    assert isinstance(progress, RunProgressReadModel)
    # Child rows are the sole source, ordered by stable run_ordinal.
    assert progress.run_id == result.run_id
    assert progress.project_id == project.id
    assert progress.status == "running"  # child B is still queued
    assert progress.total_children == 2
    assert progress.failed == 1
    assert progress.succeeded == 0
    assert progress.cancelled == 0
    assert progress.ordered == ((0, child_a, "failed"), (1, child_b, "queued"))
    # The read is pure: the stored projection is untouched (no persisted
    # cursor or mutable progress aggregate).
    assert _run_result_json(run_env.writer, result.run_id) == {}
    # Round-trips through the frozen model.
    assert RunProgressReadModel.from_mapping(progress.to_dict()) == progress

    # After a group cancel the derivation reflects the recomputed terminal
    # run: any failed child wins over cancelled.
    cancelled = _group_cancel(run_env, project_id=project.id, run_id=result.run_id, idempotency_key="derive-cancel-k")
    assert cancelled.progress.status == "failed"
    assert cancelled.progress.ordered == ((0, child_a, "failed"), (1, child_b, "cancelled"))
    later = UnitOfWork(run_env.writer).run(
        lambda u: run_env.run_repo.derive_progress(
            u, project_id=project.id, run_id=result.run_id
        )
    )
    assert later.status == "failed"
    assert later.failed == 1 and later.cancelled == 1


def test_group_operations_create_no_forbidden_tables(run_env) -> None:
    project = _create_project(run_env)
    child_a = generate_lowercase_ulid()
    result = _fanout(
        run_env,
        project_id=project.id,
        children=[
            _child(task_id=child_a, priority=3, max_attempts=1),
            _child(task_id=generate_lowercase_ulid(), priority=2),
        ],
        idempotency_key="forbidden-setup",
    )
    claim_a = _claim_child(run_env, project_id=project.id, idempotency_key="forbidden-claim")
    assert claim_a is not None and claim_a.task.id == child_a
    _fail_started_child(run_env, project_id=project.id, claim=claim_a, idempotency_key="forbidden-fail")
    _group_cancel(run_env, project_id=project.id, run_id=result.run_id, idempotency_key="forbidden-cancel-k")

    # A second run exercises the group-retry surface too.
    result2 = _fanout(
        run_env,
        project_id=project.id,
        children=[_child(task_id=generate_lowercase_ulid(), priority=0, max_attempts=2)],
        idempotency_key="forbidden-setup-2",
        run_id=generate_lowercase_ulid(),
    )
    claim = _claim_child(run_env, project_id=project.id, idempotency_key="forbidden-claim-2")
    assert claim is not None
    _fail_started_child(run_env, project_id=project.id, claim=claim, idempotency_key="forbidden-fail-2")
    _group_retry(run_env, project_id=project.id, run_id=result2.run_id, idempotency_key="forbidden-retry-k")

    # The schema stays free of every forbidden table name (plan/step,
    # cursor, session, and speculative vocabulary) after the full group
    # lifecycle; progress lives only in the child task rows.
    tables = run_env.writer.submit(
        lambda session: [
            row["name"]
            for row in session.query("SELECT name FROM sqlite_master WHERE type = 'table'")
        ]
    )
    assert not set(tables).intersection(FORBIDDEN_TABLES)
    assert "run_progress" not in tables
    assert "change_cursor" not in tables
    # No parent task and no evidence rows appeared either.
    assert _task_row(run_env.writer, result.run_id) is None
    assert _counts(run_env.writer)[6] == 0
