"""Task admission tests: canonical spec hashing and atomic creation (m2 plan step 6).

T9 scope proves the immutable admission root before any lifecycle command
exists:

- ``spec_hash`` is derived from one byte-stable canonical representation of
  the spec plus input manifest: equivalent spellings hash identically,
  semantic changes change the hash, and the stored hash matches a
  recomputation;
- admission atomically commits the task row (``queued``), the ``core.task``
  stream, the ``core.task.created`` event (hash-chained from genesis), both
  heads, and one complete receipt — replay returns the stored result with
  zero new rows and mismatch fails before any mutation;
- frozen task/attempt read models round-trip and lifecycle validation is
  typed (capability, spec/input-manifest shape, project existence, attempt
  budget, actor kind, duplicate ids).

Later plan steps extend this module with dependency validation (T10) and
the claim/start lifecycle (T11+).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from astrid.core.events.service import EventAppendService, payload_event_hash
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts import ReceiptMismatchError, ReceiptService, request_hash
from astrid.core.repositories import (
    TaskAlreadyExistsError,
    TaskAttemptReadModel,
    TaskNotFoundError,
    TaskReadModel,
    TaskRepository,
    TaskRepositoryError,
    TaskValidationError,
)
from astrid.core.repositories.tasks import (
    CORE_TASK_CREATE_COMMAND_KIND,
    CORE_TASK_CREATED_EVENT_KIND,
    CORE_TASK_STREAM_TYPE,
    DEPENDENCY_KINDS,
    HARD_DEPENDENCY_SATISFIED_STATUS,
    TaskDependencyError,
    TaskDependencyReadModel,
    TaskListRow,
    compute_spec_hash,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter

TS = "2026-08-16T00:00:00.000000+00:00"
TS2 = "2026-08-16T01:00:00.000000+00:00"

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_UUID4_HEX_RE = re.compile(r"^[0-9a-f]{32}$")

SPEC_A = {"backend": "rendering.remotion", "composition": "main", "fps": 24}
SPEC_A_RENAMED_KEYS = {"composition": "main", "fps": 24, "backend": "rendering.remotion"}
SPEC_B = {"backend": "rendering.remotion", "composition": "main", "fps": 30}
MANIFEST_A = ["media_1", "media_2"]
MANIFEST_B = ["media_1"]


def _create_project(env, *, slug: str = "pilot", project_id: str | None = None):
    """Create one project through the m1 project vertical."""
    args = {
        "slug": slug,
        "name": slug.title(),
        "settings": {"fps": 24},
        "idempotency_key": f"create-{slug}-k",
        "project_id": project_id or generate_lowercase_ulid(),
        "created_at": TS,
    }
    return UnitOfWork(env.writer).run(lambda u: env.project_repo.create(u, **args))


def _admit(
    env,
    *,
    project_id: str,
    capability: str = "rendering.timeline_visualize",
    spec=None,
    input_manifest=None,
    idempotency_key: str = "admit-k-1",
    task_id: str | None = None,
    **overrides,
):
    """Run one task-admission command inside its own unit of work."""
    args = {
        "project_id": project_id,
        "capability": capability,
        "spec": spec if spec is not None else dict(SPEC_A),
        "input_manifest": input_manifest if input_manifest is not None else list(MANIFEST_A),
        "idempotency_key": idempotency_key,
        "task_id": task_id or generate_lowercase_ulid(),
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.create(u, **args))


def _counts(writer: DatabaseWriter) -> tuple[int, int, int, int]:
    """(projects, event_streams, events, command_receipts) row counts."""
    return writer.submit(
        lambda session: (
            session.query_one("SELECT count(*) FROM projects")[0],
            session.query_one("SELECT count(*) FROM event_streams")[0],
            session.query_one("SELECT count(*) FROM events")[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
        )
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
# Canonical spec hashing
# ---------------------------------------------------------------------------


def test_spec_hash_is_byte_stable_across_key_order() -> None:
    assert compute_spec_hash(SPEC_A, MANIFEST_A) == compute_spec_hash(
        SPEC_A_RENAMED_KEYS, MANIFEST_A
    )
    assert compute_spec_hash(SPEC_A, MANIFEST_A) == compute_spec_hash(
        dict(SPEC_A), list(MANIFEST_A)
    )


def test_spec_hash_changes_on_semantic_change() -> None:
    base = compute_spec_hash(SPEC_A, MANIFEST_A)
    assert compute_spec_hash(SPEC_B, MANIFEST_A) != base
    assert compute_spec_hash(SPEC_A, MANIFEST_B) != base
    assert compute_spec_hash(SPEC_A, []) != base


def test_spec_hash_is_lowercase_sha256() -> None:
    digest = compute_spec_hash(SPEC_A, MANIFEST_A)
    assert _SHA256_HEX_RE.fullmatch(digest) is not None


# ---------------------------------------------------------------------------
# Atomic admission state
# ---------------------------------------------------------------------------


def test_admission_creates_atomic_task_state(task_env) -> None:
    project = _create_project(task_env)
    counts_before = _counts(task_env.writer)
    task = _admit(task_env, project_id=project.id)
    counts_after = _counts(task_env.writer)
    # event_streams, events, command_receipts each +1; the project row
    # already exists (its event_head_seq advances instead).
    assert counts_after == (
        counts_before[0],
        counts_before[1] + 1,
        counts_before[2] + 1,
        counts_before[3] + 1,
    )

    row = _task_row(task_env.writer, task.id)
    assert row is not None
    assert row["project_id"] == project.id
    assert row["event_stream_id"] == f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    assert row["capability"] == "rendering.timeline_visualize"
    assert row["status"] == "queued"
    assert row["priority"] == 0
    assert row["max_attempts"] == 1
    assert row["run_id"] is None and row["run_ordinal"] is None
    assert row["winning_attempt_id"] is None
    assert row["cancel_request_id"] is None
    assert row["spec_hash"] == compute_spec_hash(SPEC_A, MANIFEST_A)
    assert json.loads(row["spec_json"]) == SPEC_A
    assert json.loads(row["input_manifest_json"]) == MANIFEST_A

    stream = _stream_row(task_env.writer, f"{task.id}:{CORE_TASK_STREAM_TYPE}")
    assert stream["stream_type"] == CORE_TASK_STREAM_TYPE
    assert stream["aggregate_id"] == task.id
    assert stream["head_seq"] == 1
    assert stream["project_id"] == project.id

    # Both heads advanced: the project head counts the project-created event
    # plus this task-created event; the task stream head counts one event.
    project_row = task_env.writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = ?", (project.id,)
        )
    )
    assert project_row["event_head_seq"] == 2
    assert task.event_head_seq == 2


def test_created_event_is_registered_and_hash_chained(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    events = _event_rows(task_env.writer, stream_id)
    assert len(events) == 1
    event = events[0]
    assert event["kind"] == CORE_TASK_CREATED_EVENT_KIND
    assert event["subject_type"] == "task"
    assert event["subject_id"] == task.id
    assert event["project_seq"] == 2
    assert event["seq"] == 1
    payload = json.loads(event["payload_json"])
    # Canonical SD2 integrity envelope with a genesis previous hash.
    integrity = payload["_integrity"]
    assert integrity["previous_event_hash"] is None
    assert payload_event_hash(payload) == integrity["event_hash"]
    data = payload["data"]
    assert data["capability"] == "rendering.timeline_visualize"
    assert data["spec"] == SPEC_A
    assert data["spec_hash"] == task.spec_hash
    assert data["input_manifest"] == MANIFEST_A
    assert data["status"] == "queued"
    assert data["max_attempts"] == 1
    assert json.loads(event["changes_json"]) == [
        "capability",
        "spec",
        "spec_hash",
        "input_manifest",
        "priority",
        "available_at",
        "max_attempts",
        "status",
    ]


def test_receipt_contents_are_complete(task_env) -> None:
    project = _create_project(task_env)
    task_id = generate_lowercase_ulid()
    key = "admit-receipt-k"
    task = _admit(
        task_env, project_id=project.id, task_id=task_id, idempotency_key=key
    )
    receipt = _receipt_row(task_env.writer, project.id, key)
    assert receipt is not None
    assert receipt["command_kind"] == CORE_TASK_CREATE_COMMAND_KIND
    expected_hash = request_hash(
        CORE_TASK_CREATE_COMMAND_KIND,
        {
            "task_id": task_id,
            "capability": "rendering.timeline_visualize",
            "spec": SPEC_A,
            "input_manifest": MANIFEST_A,
            "priority": 0,
            "available_at": None,
            "max_attempts": 1,
        },
    )
    assert receipt["request_hash"] == expected_hash
    assert receipt["primary_stream_id"] == f"{task_id}:{CORE_TASK_STREAM_TYPE}"
    assert receipt["resulting_stream_seq"] == 1
    assert receipt["first_project_seq"] == 2
    assert receipt["last_project_seq"] == 2
    event_ids = json.loads(receipt["event_ids_json"])
    assert len(event_ids) == 1
    assert _UUID4_HEX_RE.fullmatch(event_ids[0]) is not None
    result = json.loads(receipt["result_json"])
    assert result["id"] == task_id
    assert result["status"] == "queued"
    assert result["spec_hash"] == task.spec_hash


# ---------------------------------------------------------------------------
# Replay and mismatch
# ---------------------------------------------------------------------------


def test_identical_replay_returns_stored_result_with_zero_new_rows(task_env) -> None:
    project = _create_project(task_env)
    task_id = generate_lowercase_ulid()
    key = "admit-replay-k"
    first = _admit(
        task_env, project_id=project.id, task_id=task_id, idempotency_key=key
    )
    counts_after_first = _counts(task_env.writer)
    second = _admit(
        task_env, project_id=project.id, task_id=task_id, idempotency_key=key
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(task_env.writer) == counts_after_first


def test_mismatch_fails_before_any_mutation(task_env) -> None:
    project = _create_project(task_env)
    task_id = generate_lowercase_ulid()
    key = "admit-mismatch-k"
    _admit(task_env, project_id=project.id, task_id=task_id, idempotency_key=key)
    counts = _counts(task_env.writer)
    with pytest.raises(ReceiptMismatchError):
        _admit(
            task_env,
            project_id=project.id,
            task_id=task_id,
            idempotency_key=key,
            spec=SPEC_B,
        )
    assert _counts(task_env.writer) == counts
    # The stored task and its stream are unchanged.
    row = _task_row(task_env.writer, task_id)
    assert json.loads(row["spec_json"]) == SPEC_A
    stream = _stream_row(task_env.writer, f"{task_id}:{CORE_TASK_STREAM_TYPE}")
    assert stream["head_seq"] == 1


def test_same_key_under_different_project_creates_new_task(task_env) -> None:
    project_a = _create_project(task_env, slug="alpha")
    project_b = _create_project(task_env, slug="beta")
    key = "shared-key"
    task_a = _admit(task_env, project_id=project_a.id, idempotency_key=key)
    task_b = _admit(task_env, project_id=project_b.id, idempotency_key=key)
    assert task_a.id != task_b.id
    assert task_a.project_id == project_a.id
    assert task_b.project_id == project_b.id
    assert _counts(task_env.writer)[0] == 2


# ---------------------------------------------------------------------------
# Typed validation
# ---------------------------------------------------------------------------


def test_validation_rejects_malformed_admission(task_env) -> None:
    project = _create_project(task_env)

    def admit(**overrides):
        return _admit(task_env, project_id=project.id, **overrides)

    with pytest.raises(TaskValidationError):
        admit(capability="")
    with pytest.raises(TaskValidationError):
        admit(spec="not-an-object")
    with pytest.raises(TaskValidationError):
        admit(spec=["list"])
    with pytest.raises(TaskValidationError):
        admit(input_manifest="not-an-array")
    with pytest.raises(TaskValidationError):
        admit(input_manifest={"a": 1})
    with pytest.raises(TaskValidationError):
        admit(max_attempts=0)
    with pytest.raises(TaskValidationError):
        admit(max_attempts=-2)
    with pytest.raises(TaskValidationError):
        admit(actor_kind="scheduler")
    with pytest.raises(TaskValidationError):
        _admit(task_env, project_id="")


def test_unknown_project_is_rejected_before_mutation(task_env) -> None:
    counts = _counts(task_env.writer)
    with pytest.raises(TaskValidationError):
        _admit(task_env, project_id=generate_lowercase_ulid())
    assert _counts(task_env.writer) == counts


def test_duplicate_task_id_rejected(task_env) -> None:
    project = _create_project(task_env)
    task_id = generate_lowercase_ulid()
    _admit(task_env, project_id=project.id, task_id=task_id)
    counts = _counts(task_env.writer)
    with pytest.raises(TaskAlreadyExistsError):
        _admit(
            task_env,
            project_id=project.id,
            task_id=task_id,
            idempotency_key="different-key",
            spec=SPEC_B,
        )
    assert _counts(task_env.writer) == counts


def test_error_family_is_repository_typed(task_env) -> None:
    project = _create_project(task_env)
    with pytest.raises(TaskRepositoryError):
        _admit(task_env, project_id=project.id, capability="")
    # Validation errors are catchable as the base repository error family.
    with pytest.raises(TaskRepositoryError):
        _admit(task_env, project_id=project.id, spec="nope")


# ---------------------------------------------------------------------------
# Frozen read models
# ---------------------------------------------------------------------------


def test_task_read_model_frozen_roundtrip(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    rebuilt = TaskReadModel.from_mapping(task.to_dict())
    assert rebuilt == task
    assert rebuilt.spec == SPEC_A
    assert rebuilt.input_manifest == MANIFEST_A
    assert rebuilt.status == "queued"
    assert rebuilt.finished_at is None


def test_attempt_read_model_frozen_roundtrip() -> None:
    model = TaskAttemptReadModel(
        id="attempt-1",
        task_id="task-1",
        attempt_no=1,
        executor_id="exec-1",
        status="running",
        status_version=3,
        lease_id="lease-1",
        lease_expires_at=TS2,
        heartbeat_counter=2,
        last_heartbeat_at=TS2,
        progress={"pct": 50},
        error={},
        created_at=TS,
        updated_at=TS2,
        finished_at=None,
    )
    rebuilt = TaskAttemptReadModel.from_mapping(model.to_dict())
    assert rebuilt == model
    assert rebuilt.status_version == 3
    assert rebuilt.heartbeat_counter == 2


# ---------------------------------------------------------------------------
# Dependency validation, blocked/queued initialization, and reads (T10)
# ---------------------------------------------------------------------------


def _dep(task_id: str, kind: str = "hard", ordinal: int = 0) -> dict:
    return {"task_id": task_id, "kind": kind, "ordinal": ordinal}


def _set_status(writer: DatabaseWriter, task_id: str, status: str) -> None:
    """Force a task status directly (stand-in for later lifecycle commands)."""
    writer.submit(
        lambda session: session.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, TS2, task_id),
        )
    )


def _dep_rows(writer: DatabaseWriter, task_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT task_id, depends_on_task_id, kind, ordinal "
            "FROM task_dependencies WHERE task_id = ? "
            "ORDER BY ordinal ASC, depends_on_task_id ASC",
            (task_id,),
        )
    )


def test_dependency_kind_vocabulary_is_frozen() -> None:
    assert DEPENDENCY_KINDS == ("hard", "soft")
    assert HARD_DEPENDENCY_SATISFIED_STATUS == "succeeded"


def test_dependency_error_family_is_typed(task_env) -> None:
    project = _create_project(task_env)
    with pytest.raises(TaskDependencyError):
        _admit(
            task_env,
            project_id=project.id,
            dependencies=[_dep(generate_lowercase_ulid())],
        )
    # Catchable as the repository error family.
    with pytest.raises(TaskRepositoryError):
        _admit(
            task_env,
            project_id=project.id,
            dependencies=[_dep(generate_lowercase_ulid())],
        )
    with pytest.raises(TaskValidationError):
        _admit(
            task_env,
            project_id=project.id,
            dependencies=[{"task_id": "", "kind": "hard"}],
        )


def test_dependency_missing_task_rejected_before_mutation(task_env) -> None:
    project = _create_project(task_env)
    counts = _counts(task_env.writer)
    with pytest.raises(TaskDependencyError) as excinfo:
        _admit(
            task_env,
            project_id=project.id,
            dependencies=[_dep(generate_lowercase_ulid())],
        )
    assert excinfo.value.reason == "missing"
    assert _counts(task_env.writer) == counts


def test_dependency_cross_project_rejected(task_env) -> None:
    project_a = _create_project(task_env, slug="alpha")
    project_b = _create_project(task_env, slug="beta")
    dep_task = _admit(task_env, project_id=project_b.id, idempotency_key="dep-k")
    with pytest.raises(TaskDependencyError) as excinfo:
        _admit(
            task_env,
            project_id=project_a.id,
            idempotency_key="cross-k",
            dependencies=[_dep(dep_task.id)],
        )
    assert excinfo.value.reason == "cross_project"


def test_dependency_self_edge_rejected(task_env) -> None:
    project = _create_project(task_env)
    task_id = generate_lowercase_ulid()
    with pytest.raises(TaskDependencyError) as excinfo:
        _admit(
            task_env,
            project_id=project.id,
            task_id=task_id,
            idempotency_key="self-k",
            dependencies=[_dep(task_id)],
        )
    assert excinfo.value.reason == "self"


def test_dependency_duplicate_edge_rejected(task_env) -> None:
    project = _create_project(task_env)
    dep_task = _admit(task_env, project_id=project.id, idempotency_key="dup-dep-k")
    with pytest.raises(TaskDependencyError) as excinfo:
        _admit(
            task_env,
            project_id=project.id,
            idempotency_key="dup-k",
            dependencies=[_dep(dep_task.id), _dep(dep_task.id, kind="soft")],
        )
    assert excinfo.value.reason == "duplicate"


def test_dependency_cycle_in_existing_closure_rejected(task_env) -> None:
    project = _create_project(task_env)
    task_a = _admit(task_env, project_id=project.id, idempotency_key="cyc-a")
    task_b = _admit(task_env, project_id=project.id, idempotency_key="cyc-b")
    # Simulate corrupt legacy data: A depends on B and B depends on A.
    task_env.writer.submit(
        lambda session: session.execute(
            "INSERT INTO task_dependencies "
            "(task_id, depends_on_task_id, kind, ordinal) VALUES (?, ?, 'hard', 0)",
            (task_a.id, task_b.id),
        )
    )
    task_env.writer.submit(
        lambda session: session.execute(
            "INSERT INTO task_dependencies "
            "(task_id, depends_on_task_id, kind, ordinal) VALUES (?, ?, 'hard', 0)",
            (task_b.id, task_a.id),
        )
    )
    counts = _counts(task_env.writer)
    with pytest.raises(TaskDependencyError) as excinfo:
        _admit(
            task_env,
            project_id=project.id,
            idempotency_key="cyc-new",
            dependencies=[_dep(task_a.id)],
        )
    assert excinfo.value.reason == "cycle"
    assert _counts(task_env.writer) == counts


def test_initial_status_queued_without_dependencies(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    assert task.status == "queued"
    assert task.dependencies == ()


def test_initial_status_queued_when_hard_dependency_satisfied(task_env) -> None:
    project = _create_project(task_env)
    dep_task = _admit(task_env, project_id=project.id, idempotency_key="sat-dep")
    _set_status(task_env.writer, dep_task.id, "succeeded")
    task = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="sat-child",
        dependencies=[_dep(dep_task.id)],
    )
    assert task.status == "queued"


def test_initial_status_blocked_when_hard_dependency_unsatisfied(task_env) -> None:
    project = _create_project(task_env)
    dep_task = _admit(task_env, project_id=project.id, idempotency_key="unsat-dep")
    for dep_status in ("queued", "blocked", "running", "failed", "cancelled"):
        _set_status(task_env.writer, dep_task.id, dep_status)
        task = _admit(
            task_env,
            project_id=project.id,
            idempotency_key=f"unsat-child-{dep_status}",
            dependencies=[_dep(dep_task.id)],
        )
        assert task.status == "blocked", dep_status


def test_soft_dependencies_never_block(task_env) -> None:
    project = _create_project(task_env)
    dep_task = _admit(task_env, project_id=project.id, idempotency_key="soft-dep")
    # The soft dependency is queued (unsatisfied) yet the child stays queued.
    task = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="soft-child",
        dependencies=[_dep(dep_task.id, kind="soft")],
    )
    assert task.status == "queued"
    assert task.dependencies == (
        TaskDependencyReadModel(
            task_id=task.id,
            depends_on_task_id=dep_task.id,
            kind="soft",
            ordinal=0,
        ),
    )


def test_mixed_hard_and_soft_initial_status(task_env) -> None:
    project = _create_project(task_env)
    satisfied = _admit(task_env, project_id=project.id, idempotency_key="mix-ok")
    _set_status(task_env.writer, satisfied.id, "succeeded")
    unsatisfied = _admit(task_env, project_id=project.id, idempotency_key="mix-wait")
    # All hard satisfied + soft unsatisfied -> queued.
    queued = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="mix-child-1",
        dependencies=[
            _dep(satisfied.id, kind="hard", ordinal=0),
            _dep(unsatisfied.id, kind="soft", ordinal=1),
        ],
    )
    assert queued.status == "queued"
    # One hard unsatisfied -> blocked even with a satisfied hard sibling.
    blocked = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="mix-child-2",
        dependencies=[
            _dep(satisfied.id, kind="hard", ordinal=0),
            _dep(unsatisfied.id, kind="hard", ordinal=1),
        ],
    )
    assert blocked.status == "blocked"


def test_dependency_edges_persisted_and_ordered(task_env) -> None:
    project = _create_project(task_env)
    first = _admit(task_env, project_id=project.id, idempotency_key="edge-1")
    second = _admit(task_env, project_id=project.id, idempotency_key="edge-2")
    task = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="edge-child",
        dependencies=[
            _dep(second.id, kind="soft", ordinal=1),
            _dep(first.id, kind="hard", ordinal=0),
        ],
    )
    rows = _dep_rows(task_env.writer, task.id)
    assert [(r["depends_on_task_id"], r["kind"], r["ordinal"]) for r in rows] == [
        (first.id, "hard", 0),
        (second.id, "soft", 1),
    ]
    # The task row carries the initialized status: the hard dependency is
    # still queued (not succeeded), so the child starts blocked.
    row = _task_row(task_env.writer, task.id)
    assert row["status"] == "blocked"


def test_created_event_records_dependencies_and_status(task_env) -> None:
    project = _create_project(task_env)
    dep_task = _admit(task_env, project_id=project.id, idempotency_key="ev-dep")
    task = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="ev-child",
        dependencies=[_dep(dep_task.id)],
    )
    events = _event_rows(task_env.writer, f"{task.id}:{CORE_TASK_STREAM_TYPE}")
    payload = json.loads(events[0]["payload_json"])
    data = payload["data"]
    assert data["status"] == "blocked"
    assert data["dependencies"] == [
        {"task_id": task.id, "depends_on_task_id": dep_task.id, "kind": "hard", "ordinal": 0}
    ]
    assert json.loads(events[0]["changes_json"]) == [
        "capability",
        "spec",
        "spec_hash",
        "input_manifest",
        "priority",
        "available_at",
        "max_attempts",
        "status",
        "dependencies",
    ]


def test_receipt_result_includes_dependencies(task_env) -> None:
    project = _create_project(task_env)
    dep_task = _admit(task_env, project_id=project.id, idempotency_key="rc-dep")
    task = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="rc-child",
        dependencies=[_dep(dep_task.id, kind="soft", ordinal=3)],
    )
    receipt = _receipt_row(task_env.writer, project.id, "rc-child")
    result = json.loads(receipt["result_json"])
    assert result["status"] == "queued"
    assert result["dependencies"] == [
        {
            "task_id": task.id,
            "depends_on_task_id": dep_task.id,
            "kind": "soft",
            "ordinal": 3,
        }
    ]
    assert task.to_dict()["dependencies"] == result["dependencies"]


def test_dependency_replay_is_stable_and_mismatch_fails_before_mutation(
    task_env,
) -> None:
    project = _create_project(task_env)
    dep_task = _admit(task_env, project_id=project.id, idempotency_key="rep-dep")
    key = "rep-child"
    task_id = generate_lowercase_ulid()
    first = _admit(
        task_env,
        project_id=project.id,
        task_id=task_id,
        idempotency_key=key,
        dependencies=[_dep(dep_task.id, kind="soft")],
    )
    counts_after_first = _counts(task_env.writer)
    second = _admit(
        task_env,
        project_id=project.id,
        task_id=task_id,
        idempotency_key=key,
        dependencies=[_dep(dep_task.id, kind="soft")],
    )
    assert second == first
    assert _counts(task_env.writer) == counts_after_first
    # A changed dependency set under the same key is a mismatch before mutation.
    with pytest.raises(ReceiptMismatchError):
        _admit(
            task_env,
            project_id=project.id,
            task_id=task_id,
            idempotency_key=key,
            dependencies=[_dep(dep_task.id, kind="hard")],
        )
    assert _counts(task_env.writer) == counts_after_first


def test_dependency_read_model_roundtrip() -> None:
    model = TaskDependencyReadModel(
        task_id="t-1", depends_on_task_id="t-2", kind="hard", ordinal=4
    )
    rebuilt = TaskDependencyReadModel.from_mapping(model.to_dict())
    assert rebuilt == model


def test_show_returns_full_read_model_with_dependencies(task_env) -> None:
    project = _create_project(task_env)
    dep_task = _admit(task_env, project_id=project.id, idempotency_key="show-dep")
    task = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="show-child",
        dependencies=[_dep(dep_task.id, kind="soft", ordinal=2)],
    )
    shown = task_env.task_repo.show(task_env.writer, task.id)
    assert shown == task
    assert shown.status == "queued"
    assert shown.spec == SPEC_A
    assert shown.dependencies == (
        TaskDependencyReadModel(
            task_id=task.id, depends_on_task_id=dep_task.id, kind="soft", ordinal=2
        ),
    )
    assert shown.event_head_seq == task.event_head_seq


def test_show_unknown_task_raises_typed_not_found(task_env) -> None:
    project = _create_project(task_env)
    with pytest.raises(TaskNotFoundError):
        task_env.task_repo.show(task_env.writer, generate_lowercase_ulid())


def test_list_returns_sorted_tasks_and_empty_project(task_env) -> None:
    project = _create_project(task_env)
    other = _create_project(task_env, slug="other")
    first = _admit(task_env, project_id=project.id, idempotency_key="list-1")
    second = _admit(task_env, project_id=project.id, idempotency_key="list-2")
    rows = task_env.task_repo.list(task_env.writer, project.id)
    assert [row.id for row in rows] == [first.id, second.id]
    assert all(isinstance(row, TaskListRow) for row in rows)
    assert rows[0].status == "queued"
    assert rows[0].project_id == project.id
    # The other project's task is not visible.
    assert task_env.task_repo.list(task_env.writer, other.id) == []


def test_is_eligible_honors_status_availability_and_hard_gating(task_env) -> None:
    project = _create_project(task_env)
    plain = _admit(task_env, project_id=project.id, idempotency_key="el-plain")
    assert task_env.task_repo.is_eligible(task_env.writer, plain.id, now=TS) is True
    # Future available_at is not yet eligible.
    future = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="el-future",
        available_at=TS2,
    )
    assert task_env.task_repo.is_eligible(task_env.writer, future.id, now=TS) is False
    assert task_env.task_repo.is_eligible(task_env.writer, future.id, now=TS2) is True
    # Terminal tasks are never eligible.
    _set_status(task_env.writer, plain.id, "succeeded")
    assert task_env.task_repo.is_eligible(task_env.writer, plain.id, now=TS) is False
    # Unknown tasks are simply not eligible.
    assert (
        task_env.task_repo.is_eligible(task_env.writer, generate_lowercase_ulid(), now=TS)
        is False
    )


def test_is_eligible_blocks_on_unsatisfied_hard_dependency(task_env) -> None:
    project = _create_project(task_env)
    dep_task = _admit(task_env, project_id=project.id, idempotency_key="elg-dep")
    child = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="elg-child",
        dependencies=[_dep(dep_task.id)],
    )
    assert child.status == "blocked"
    assert task_env.task_repo.is_eligible(task_env.writer, child.id, now=TS) is False
    # Once the hard dependency succeeds, the child becomes eligible even
    # though its row still says blocked (the unblock transition is a later
    # lifecycle command; eligibility reads report the truth).
    _set_status(task_env.writer, dep_task.id, "succeeded")
    assert task_env.task_repo.is_eligible(task_env.writer, child.id, now=TS) is True


def test_is_eligible_ignores_soft_dependencies(task_env) -> None:
    project = _create_project(task_env)
    soft_dep = _admit(task_env, project_id=project.id, idempotency_key="elg-soft")
    child = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="elg-soft-child",
        dependencies=[_dep(soft_dep.id, kind="soft")],
    )
    assert child.status == "queued"
    assert task_env.task_repo.is_eligible(task_env.writer, child.id, now=TS) is True


def test_list_eligible_returns_claim_order_queue(task_env) -> None:
    project = _create_project(task_env)
    # The dependency task itself is claimable too, so pin it to a future
    # available_at to keep it out of the current queue.
    dep_task = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="q-dep",
        available_at=TS2,
    )
    blocked = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="q-blocked",
        dependencies=[_dep(dep_task.id)],
    )
    low_prio = _admit(task_env, project_id=project.id, idempotency_key="q-low", priority=1)
    high_prio = _admit(task_env, project_id=project.id, idempotency_key="q-high", priority=9)
    soft_child = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="q-soft",
        dependencies=[_dep(dep_task.id, kind="soft")],
    )
    rows = task_env.task_repo.list_eligible(task_env.writer, project.id, now=TS)
    # Claim order: priority DESC, available_at ASC, id ASC. The blocked hard
    # dependency child is excluded; the soft child is included.
    assert [row.id for row in rows] == [high_prio.id, low_prio.id, soft_child.id]
    # Once the hard dependency succeeds the blocked child joins the queue.
    _set_status(task_env.writer, dep_task.id, "succeeded")
    rows = task_env.task_repo.list_eligible(task_env.writer, project.id, now=TS)
    assert [row.id for row in rows] == [
        high_prio.id,
        low_prio.id,
        blocked.id,
        soft_child.id,
    ]


def test_list_eligible_respects_availability(task_env) -> None:
    project = _create_project(task_env)
    now_task = _admit(task_env, project_id=project.id, idempotency_key="av-now")
    later = _admit(
        task_env,
        project_id=project.id,
        idempotency_key="av-later",
        available_at=TS2,
    )
    assert [row.id for row in task_env.task_repo.list_eligible(task_env.writer, project.id, now=TS)] == [now_task.id]
    assert {row.id for row in task_env.task_repo.list_eligible(task_env.writer, project.id, now=TS2)} == {now_task.id, later.id}
