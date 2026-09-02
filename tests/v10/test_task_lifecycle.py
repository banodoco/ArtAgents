"""Task lifecycle tests: FIFO claim and version-fenced start (m2 plan step 7, T11).

T11 scope proves the first half of plan step 7 — exclusive claim and
receipt-protected start — before heartbeat (T12) and the cancel/fail/retry
commands (T13/T14) exist:

- ``claim`` creates exactly one local ``claimed`` attempt (``status_version``
  1, leased) for the first eligibility-ordered task (priority descending,
  then availability, then id), transitions the task ``queued``/``blocked`` →
  ``running``, appends the hash-chained ``core.task.claimed`` event, and
  records one complete receipt; a second claim can never double-claim the
  same task;
- claim is receipt-first: an identical retry returns the stored claim result
  with zero new rows, and a changed request under the same key fails before
  any mutation;
- ``start`` advances only the matching attempt/status_version (and lease)
  through a receipt-protected ``core.task.started`` event with correct
  project ordering, advancing ``status_version`` by one and recording one
  receipt; stale versions, foreign attempts, unknown attempts, and
  non-running tasks raise typed outcomes and change zero rows.
"""

from __future__ import annotations

import json

import pytest

from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts import ReceiptMismatchError
from astrid.core.repositories import (
    TaskNotFoundError,
    TaskRepositoryError,
    TaskValidationError,
)
from astrid.core.repositories.tasks import (
    CORE_TASK_CANCEL_COMMAND_KIND,
    CORE_TASK_CANCELLED_EVENT_KIND,
    CORE_TASK_CLAIM_COMMAND_KIND,
    CORE_TASK_CLAIMED_EVENT_KIND,
    CORE_TASK_CREATED_EVENT_KIND,
    CORE_TASK_EXPIRE_COMMAND_KIND,
    CORE_TASK_EXPIRED_EVENT_KIND,
    CORE_TASK_FAIL_COMMAND_KIND,
    CORE_TASK_FAILED_EVENT_KIND,
    CORE_TASK_RETRY_COMMAND_KIND,
    CORE_TASK_RETRIED_EVENT_KIND,
    CORE_TASK_START_COMMAND_KIND,
    CORE_TASK_STARTED_EVENT_KIND,
    CORE_TASK_STREAM_TYPE,
    DEFAULT_LEASE_SECONDS,
    TaskAttemptNotFoundError,
    TaskCancelReadModel,
    TaskClaimReadModel,
    TaskExpiryReadModel,
    TaskFailReadModel,
    TaskRetryReadModel,
    TaskTransitionError,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter

TS = "2026-08-16T00:00:00.000000+00:00"
TS2 = "2026-08-16T01:00:00.000000+00:00"

SPEC_A = {"backend": "rendering.remotion", "composition": "main", "fps": 24}
MANIFEST_A = ["media_1", "media_2"]


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
    idempotency_key: str | None = None,
    task_id: str | None = None,
    **overrides,
):
    """Run one task-admission command inside its own unit of work."""
    task_id = task_id or generate_lowercase_ulid()
    args = {
        "project_id": project_id,
        "capability": capability,
        "spec": spec if spec is not None else dict(SPEC_A),
        "input_manifest": input_manifest if input_manifest is not None else list(MANIFEST_A),
        "idempotency_key": idempotency_key or f"admit-{task_id}-k",
        "task_id": task_id,
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.create(u, **args))


def _claim(
    env,
    *,
    project_id: str,
    idempotency_key: str = "claim-k-1",
    **overrides,
):
    """Run one claim command inside its own unit of work."""
    args = {
        "project_id": project_id,
        "idempotency_key": idempotency_key,
        "executor_id": "executor-1",
        "now": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.claim(u, **args))


def _start(
    env,
    *,
    project_id: str,
    task_id: str,
    attempt_id: str,
    expected_status_version: int,
    idempotency_key: str = "start-k-1",
    **overrides,
):
    """Run one start command inside its own unit of work."""
    args = {
        "project_id": project_id,
        "task_id": task_id,
        "attempt_id": attempt_id,
        "expected_status_version": expected_status_version,
        "idempotency_key": idempotency_key,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.start(u, **args))


def _counts(writer: DatabaseWriter) -> tuple[int, int, int, int, int]:
    """(projects, event_streams, events, command_receipts, execution_attempts)."""
    return writer.submit(
        lambda session: (
            session.query_one("SELECT count(*) FROM projects")[0],
            session.query_one("SELECT count(*) FROM event_streams")[0],
            session.query_one("SELECT count(*) FROM events")[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
            session.query_one("SELECT count(*) FROM execution_attempts")[0],
        )
    )


def _task_row(writer: DatabaseWriter, task_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
    )


def _attempt_rows(writer: DatabaseWriter, task_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM execution_attempts WHERE task_id = ? "
            "ORDER BY attempt_no ASC",
            (task_id,),
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


def _project_head(writer: DatabaseWriter, project_id: str) -> int:
    return writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = ?", (project_id,)
        )[0]
    )


# ---------------------------------------------------------------------------
# Claim: one leased attempt, FIFO order, atomic state
# ---------------------------------------------------------------------------


def test_claim_creates_exactly_one_leased_attempt(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    counts_before = _counts(task_env.writer)

    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    assert claim.task.id == task.id
    assert claim.task.status == "running"
    assert claim.task.updated_at == TS
    assert claim.attempt.task_id == task.id
    assert claim.attempt.attempt_no == 1
    assert claim.attempt.status == "claimed"
    assert claim.attempt.status_version == 1
    assert claim.attempt.lease_id is not None
    assert claim.attempt.lease_expires_at is not None
    assert claim.attempt.heartbeat_counter == 0
    assert claim.attempt.executor_id == "executor-1"
    assert claim.attempt.created_at == TS

    counts_after = _counts(task_env.writer)
    # No new stream (the task stream exists) or project; exactly one event,
    # one receipt, one attempt.
    assert counts_after == (
        counts_before[0],
        counts_before[1],
        counts_before[2] + 1,
        counts_before[3] + 1,
        counts_before[4] + 1,
    )

    attempts = _attempt_rows(task_env.writer, task.id)
    assert len(attempts) == 1
    row = attempts[0]
    assert row["status"] == "claimed"
    assert row["status_version"] == 1
    assert row["lease_id"] == claim.attempt.lease_id
    assert row["lease_expires_at"] == claim.attempt.lease_expires_at

    # The task row leaves the claim queue.
    task_row = _task_row(task_env.writer, task.id)
    assert task_row["status"] == "running"
    assert task_row["updated_at"] == TS


def test_claim_picks_first_fifo_eligible_task(task_env) -> None:
    project = _create_project(task_env)
    low = _admit(task_env, project_id=project.id, priority=0, task_id=generate_lowercase_ulid())
    high = _admit(task_env, project_id=project.id, priority=5, task_id=generate_lowercase_ulid())
    # High priority wins the first claim.
    first = _claim(task_env, project_id=project.id, idempotency_key="claim-1")
    assert first is not None
    assert first.task.id == high.id
    # The next claim (new key) takes the remaining eligible task.
    second = _claim(task_env, project_id=project.id, idempotency_key="claim-2")
    assert second is not None
    assert second.task.id == low.id
    # Nothing eligible remains.
    third = _claim(task_env, project_id=project.id, idempotency_key="claim-3")
    assert third is None


def test_claim_never_double_claims_one_task(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    first = _claim(task_env, project_id=project.id, idempotency_key="claim-a")
    assert first is not None and first.task.id == task.id
    # A different key sees the task as running and claims nothing.
    second = _claim(task_env, project_id=project.id, idempotency_key="claim-b")
    assert second is None
    assert len(_attempt_rows(task_env.writer, task.id)) == 1


def test_claim_replay_returns_stored_result_with_zero_new_rows(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    first = _claim(task_env, project_id=project.id, idempotency_key="claim-replay")
    assert first is not None
    counts = _counts(task_env.writer)

    second = _claim(task_env, project_id=project.id, idempotency_key="claim-replay")
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(task_env.writer) == counts
    assert len(_attempt_rows(task_env.writer, task.id)) == 1


def test_claim_mismatch_fails_before_any_mutation(task_env) -> None:
    project = _create_project(task_env)
    _admit(task_env, project_id=project.id)
    _claim(task_env, project_id=project.id, idempotency_key="claim-mismatch")
    counts = _counts(task_env.writer)
    with pytest.raises(ReceiptMismatchError):
        _claim(
            task_env,
            project_id=project.id,
            idempotency_key="claim-mismatch",
            executor_id="another-executor",
        )
    assert _counts(task_env.writer) == counts


def test_claim_returns_none_without_receipt_when_nothing_eligible(task_env) -> None:
    project = _create_project(task_env)
    counts = _counts(task_env.writer)
    # No tasks at all.
    assert _claim(task_env, project_id=project.id) is None
    assert _counts(task_env.writer) == counts
    # A running task plus a blocked dependent leave nothing eligible.
    dep = _admit(task_env, project_id=project.id, task_id=generate_lowercase_ulid())
    _claim(task_env, project_id=project.id, idempotency_key="claim-dep")
    dependent = _admit(
        task_env,
        project_id=project.id,
        task_id=generate_lowercase_ulid(),
        dependencies=[{"task_id": dep.id, "kind": "hard", "ordinal": 0}],
    )
    assert _task_row(task_env.writer, dep.id)["status"] == "running"
    assert _task_row(task_env.writer, dependent.id)["status"] == "blocked"
    counts = _counts(task_env.writer)
    assert _claim(task_env, project_id=project.id, idempotency_key="claim-none") is None
    assert _counts(task_env.writer) == counts


def test_claim_skips_future_available_at(task_env) -> None:
    project = _create_project(task_env)
    later = _admit(
        task_env,
        project_id=project.id,
        available_at=TS2,
        task_id=generate_lowercase_ulid(),
    )
    now_task = _admit(
        task_env,
        project_id=project.id,
        available_at=TS,
        task_id=generate_lowercase_ulid(),
    )
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    assert claim.task.id == now_task.id
    assert later.id != claim.task.id


def test_claim_requires_validation(task_env) -> None:
    project = _create_project(task_env)
    with pytest.raises(TaskValidationError):
        _claim(task_env, project_id="")
    with pytest.raises(TaskValidationError):
        _claim(task_env, project_id=project.id, lease_seconds=0)
    with pytest.raises(TaskValidationError):
        _claim(task_env, project_id=project.id, executor_id="")
    with pytest.raises(TaskValidationError):
        _claim(task_env, project_id=project.id, actor_kind="scheduler")


def test_claim_event_is_registered_and_hash_chained(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    events = _event_rows(task_env.writer, stream_id)
    assert [e["kind"] for e in events] == [
        CORE_TASK_CREATED_EVENT_KIND,
        CORE_TASK_CLAIMED_EVENT_KIND,
    ]
    claimed = events[1]
    assert claimed["kind"] == CORE_TASK_CLAIMED_EVENT_KIND
    assert claimed["subject_type"] == "task"
    assert claimed["subject_id"] == task.id
    data = json.loads(claimed["payload_json"])["data"]
    assert data["attempt_id"] == claim.attempt.id
    assert data["attempt_no"] == 1
    assert data["status_version"] == 1
    assert data["lease_id"] == claim.attempt.lease_id
    assert data["executor_id"] == "executor-1"
    # The claimed event advanced the project head (created + claimed).
    assert _project_head(task_env.writer, project.id) == 3
    stream = _stream_row(task_env.writer, stream_id)
    assert stream["head_seq"] == 2
    assert claim.task.event_head_seq == 3


def test_claim_receipt_is_complete(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    receipt = _receipt_row(task_env.writer, project.id, "claim-k-1")
    assert receipt is not None
    assert receipt["command_kind"] == CORE_TASK_CLAIM_COMMAND_KIND
    assert receipt["primary_stream_id"] == f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    assert receipt["resulting_stream_seq"] == 2
    result = json.loads(receipt["result_json"])
    assert result["task"]["id"] == task.id
    assert result["task"]["status"] == "running"
    assert result["attempt"]["id"] == claim.attempt.id
    assert result["attempt"]["status"] == "claimed"
    assert result["attempt"]["status_version"] == 1
    # Rebuild the read model from the stored receipt exactly.
    rebuilt = TaskClaimReadModel.from_mapping(result)
    assert rebuilt == claim


# ---------------------------------------------------------------------------
# Start: version-fenced, receipt-protected, project ordering
# ---------------------------------------------------------------------------


def test_start_advances_matching_attempt_version(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    counts_before = _counts(task_env.writer)

    started = _start(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        expected_status_version=1,
        lease_id=claim.attempt.lease_id,
    )
    assert started.status == "running"
    assert started.status_version == 2
    assert started.lease_id == claim.attempt.lease_id
    assert started.updated_at == TS2

    counts_after = _counts(task_env.writer)
    assert counts_after == (
        counts_before[0],
        counts_before[1],
        counts_before[2] + 1,
        counts_before[3] + 1,
        counts_before[4],
    )

    attempts = _attempt_rows(task_env.writer, task.id)
    assert len(attempts) == 1
    assert attempts[0]["status"] == "running"
    assert attempts[0]["status_version"] == 2
    # The task row stays running.
    assert _task_row(task_env.writer, task.id)["status"] == "running"


def test_start_event_has_project_ordering_and_chain(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    project_head_before = _project_head(task_env.writer, project.id)
    started = _start(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        expected_status_version=1,
        lease_id=claim.attempt.lease_id,
    )
    # Project ordering: the started event is the next project sequence.
    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    events = _event_rows(task_env.writer, stream_id)
    assert [e["kind"] for e in events] == [
        CORE_TASK_CREATED_EVENT_KIND,
        CORE_TASK_CLAIMED_EVENT_KIND,
        CORE_TASK_STARTED_EVENT_KIND,
    ]
    started_event = events[2]
    assert started_event["project_seq"] == project_head_before + 1
    data = json.loads(started_event["payload_json"])["data"]
    assert data["attempt_id"] == claim.attempt.id
    assert data["status_version"] == 2
    assert data["lease_id"] == claim.attempt.lease_id
    assert _project_head(task_env.writer, project.id) == project_head_before + 1
    assert _stream_row(task_env.writer, stream_id)["head_seq"] == 3
    # The start receipt carries the exact project sequence and stream seq.
    receipt = _receipt_row(task_env.writer, project.id, "start-k-1")
    assert receipt["first_project_seq"] == project_head_before + 1
    assert receipt["last_project_seq"] == project_head_before + 1
    assert receipt["resulting_stream_seq"] == 3


def test_start_replay_returns_stored_result(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    first = _start(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        expected_status_version=1,
        lease_id=claim.attempt.lease_id,
        idempotency_key="start-replay",
    )
    counts = _counts(task_env.writer)
    second = _start(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        expected_status_version=1,
        lease_id=claim.attempt.lease_id,
        idempotency_key="start-replay",
    )
    assert second == first
    assert _counts(task_env.writer) == counts


def test_start_stale_version_is_typed_outcome_no_mutation(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    counts = _counts(task_env.writer)
    with pytest.raises(TaskTransitionError) as excinfo:
        _start(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            expected_status_version=99,
            lease_id=claim.attempt.lease_id,
            idempotency_key="start-stale",
        )
    assert excinfo.value.reason == "stale_status_version"
    assert _counts(task_env.writer) == counts
    attempts = _attempt_rows(task_env.writer, task.id)
    assert attempts[0]["status"] == "claimed"
    assert attempts[0]["status_version"] == 1
    # The task stream head is unchanged (no started event).
    assert _stream_row(task_env.writer, f"{task.id}:{CORE_TASK_STREAM_TYPE}")["head_seq"] == 2


def test_start_after_start_is_typed_outcome(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    _start(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        expected_status_version=1,
        lease_id=claim.attempt.lease_id,
    )
    counts = _counts(task_env.writer)
    # A new command (new key) cannot start the already-running attempt.
    with pytest.raises(TaskTransitionError) as excinfo:
        _start(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            expected_status_version=2,
            lease_id=claim.attempt.lease_id,
            idempotency_key="start-twice",
        )
    assert excinfo.value.reason == "attempt_not_claimed"
    assert _counts(task_env.writer) == counts


def test_start_rejects_foreign_lease_and_attempt(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id, task_id=generate_lowercase_ulid())
    other = _admit(task_env, project_id=project.id, task_id=generate_lowercase_ulid())
    claim = _claim(task_env, project_id=project.id, idempotency_key="claim-1")
    assert claim is not None and claim.task.id == task.id
    claim_other = _claim(task_env, project_id=project.id, idempotency_key="claim-2")
    assert claim_other is not None and claim_other.task.id == other.id
    counts = _counts(task_env.writer)

    with pytest.raises(TaskTransitionError) as excinfo:
        _start(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            expected_status_version=1,
            lease_id="not-the-lease",
            idempotency_key="start-lease",
        )
    assert excinfo.value.reason == "lease_mismatch"

    # An attempt of a different (running) task cannot start this task.
    with pytest.raises(TaskTransitionError) as excinfo:
        _start(
            task_env,
            project_id=project.id,
            task_id=other.id,
            attempt_id=claim.attempt.id,
            expected_status_version=1,
            lease_id=claim.attempt.lease_id,
            idempotency_key="start-foreign",
        )
    assert excinfo.value.reason == "attempt_task_mismatch"

    # An unknown attempt id is typed.
    with pytest.raises(TaskAttemptNotFoundError):
        _start(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=generate_lowercase_ulid(),
            expected_status_version=1,
            lease_id=claim.attempt.lease_id,
            idempotency_key="start-unknown-attempt",
        )
    assert _counts(task_env.writer) == counts


def test_start_rejects_unknown_task_and_non_running_task(task_env) -> None:
    project = _create_project(task_env)
    idle = _admit(task_env, project_id=project.id, task_id=generate_lowercase_ulid())
    # An unknown task id is typed and project-scoped.
    with pytest.raises(TaskNotFoundError):
        _start(
            task_env,
            project_id=project.id,
            task_id=generate_lowercase_ulid(),
            attempt_id=generate_lowercase_ulid(),
            expected_status_version=1,
            idempotency_key="start-unknown-task",
        )
    # A never-claimed (queued) task cannot start an attempt.
    with pytest.raises(TaskTransitionError) as excinfo:
        _start(
            task_env,
            project_id=project.id,
            task_id=idle.id,
            attempt_id=generate_lowercase_ulid(),
            expected_status_version=1,
            idempotency_key="start-idle",
        )
    assert excinfo.value.reason == "task_not_running"


def test_start_requires_validation(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    with pytest.raises(TaskValidationError):
        _start(
            task_env,
            project_id=project.id,
            task_id="",
            attempt_id=claim.attempt.id,
            expected_status_version=1,
        )
    with pytest.raises(TaskValidationError):
        _start(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            expected_status_version=0,
        )
    with pytest.raises(TaskValidationError):
        _start(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            expected_status_version=1,
            lease_id="",
        )


def test_claim_blocked_task_with_satisfied_hard_dependency(task_env) -> None:
    project = _create_project(task_env)
    # Simulate a hard dependency that is already satisfied by injecting a
    # succeeded task row directly (no completion command exists yet in T11).
    dep_id = generate_lowercase_ulid()
    dep_stream = f"{dep_id}:{CORE_TASK_STREAM_TYPE}"
    UnitOfWork(task_env.writer).run(
        lambda u: (
            u.execute(
                "INSERT INTO event_streams "
                "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
                "VALUES (?, ?, 'core.task', ?, 0, ?)",
                (dep_stream, project.id, dep_id, TS),
            ),
            u.execute(
                "INSERT INTO tasks "
                "(id, project_id, event_stream_id, capability, spec_json, "
                "spec_hash, input_manifest_json, status, priority, available_at, "
                "max_attempts, created_at, updated_at) "
                "VALUES (?, ?, ?, 'fake.capability', '{}', ?, '[]', 'succeeded', "
                "0, ?, 1, ?, ?)",
                (dep_id, project.id, dep_stream, "x" * 64, TS, TS, TS),
            ),
        )
    )
    dependent = _admit(
        task_env,
        project_id=project.id,
        task_id=generate_lowercase_ulid(),
        dependencies=[{"task_id": dep_id, "kind": "hard", "ordinal": 0}],
    )
    # Hard dependency satisfied -> queued and claimable.
    assert _task_row(task_env.writer, dependent.id)["status"] == "queued"
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    assert claim.task.id == dependent.id
    assert claim.task.status == "running"


def test_error_family_is_repository_typed(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    with pytest.raises(TaskRepositoryError):
        _start(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=generate_lowercase_ulid(),
            expected_status_version=1,
        )
    with pytest.raises(TaskRepositoryError):
        _claim(task_env, project_id=project.id, executor_id="")


# ---------------------------------------------------------------------------
# Heartbeat (sole non-event update, m2 plan step 7, T12)
# ---------------------------------------------------------------------------


def _heartbeat(
    env,
    *,
    project_id: str,
    task_id: str,
    attempt_id: str,
    lease_id: str,
    expected_status_version: int,
    **overrides,
):
    """Run one heartbeat update inside its own unit of work."""
    args = {
        "project_id": project_id,
        "task_id": task_id,
        "attempt_id": attempt_id,
        "lease_id": lease_id,
        "expected_status_version": expected_status_version,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.task_repo.heartbeat(u, **args)
    )


def _expire(
    env,
    *,
    project_id: str,
    idempotency_key: str,
    **overrides,
):
    """Run one expire_overdue command inside its own unit of work."""
    args = {
        "project_id": project_id,
        "idempotency_key": idempotency_key,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.task_repo.expire_overdue(u, **args)
    )


def test_heartbeat_extends_lease_with_counter_and_version(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id, lease_seconds=300, now=TS)
    assert claim is not None
    counts = _counts(task_env.writer)

    heart = _heartbeat(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=1,
        lease_seconds=300,
        now="2026-08-16T00:02:00+00:00",  # inside the 00:00..00:05 lease
    )
    # Counter and version increments, lease extended to now + 300s.
    assert heart.status == "claimed"
    assert heart.status_version == 2
    assert heart.heartbeat_counter == 1
    assert heart.last_heartbeat_at == "2026-08-16T00:02:00+00:00"
    assert heart.lease_id == claim.attempt.lease_id
    assert heart.lease_expires_at == "2026-08-16T00:07:00+00:00"
    row = _attempt_rows(task_env.writer, task.id)[0]
    assert row["heartbeat_counter"] == 1
    assert row["status_version"] == 2

    # Heartbeat is the sole non-event update: zero new events, receipts,
    # streams, or attempts (the counts tuple covers all four).
    assert _counts(task_env.writer) == counts


def test_heartbeat_works_after_start(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id, now=TS)
    assert claim is not None
    started = _start(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        expected_status_version=1,
        lease_id=claim.attempt.lease_id,
        now=TS,
    )
    assert started.status == "running"

    heart = _heartbeat(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=2,
        now="2026-08-16T00:02:00+00:00",  # inside the 00:00..00:05 lease
    )
    assert heart.status == "running"
    assert heart.status_version == 3
    assert heart.heartbeat_counter == 1


def test_heartbeat_rejects_stale_version_and_foreign_lease(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id, now=TS)
    assert claim is not None
    counts = _counts(task_env.writer)
    attempt_row_before = _attempt_rows(task_env.writer, task.id)[0]

    with pytest.raises(TaskTransitionError) as excinfo:
        _heartbeat(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=9,  # stale
        )
    assert excinfo.value.reason == "stale_status_version"

    with pytest.raises(TaskTransitionError) as excinfo:
        _heartbeat(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            lease_id=generate_lowercase_ulid(),  # foreign lease
            expected_status_version=1,
        )
    assert excinfo.value.reason == "lease_mismatch"

    with pytest.raises(TaskAttemptNotFoundError):
        _heartbeat(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=generate_lowercase_ulid(),
            lease_id=claim.attempt.lease_id,
            expected_status_version=1,
        )
    # Zero mutation on every rejection.
    assert _counts(task_env.writer) == counts
    assert _attempt_rows(task_env.writer, task.id)[0] == attempt_row_before


def test_heartbeat_rejects_expired_lease_and_non_live_attempt(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    # Short lease: expires 60s after the claim instant (00:00).
    claim = _claim(task_env, project_id=project.id, lease_seconds=60, now=TS)
    assert claim is not None
    counts = _counts(task_env.writer)

    # Heartbeat at 01:00 — the lease (00:01:00) already passed: rejected.
    with pytest.raises(TaskTransitionError) as excinfo:
        _heartbeat(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=1,
        )
    assert excinfo.value.reason == "lease_expired"
    row = _attempt_rows(task_env.writer, task.id)[0]
    assert row["status_version"] == 1  # never extended
    assert row["heartbeat_counter"] == 0
    assert _counts(task_env.writer) == counts

    # A terminal attempt is not live: heartbeat is rejected.
    UnitOfWork(task_env.writer).run(
        lambda u: u.execute(
            "UPDATE execution_attempts SET status = 'expired', "
            "status_version = 2, updated_at = ? WHERE id = ?",
            (TS, claim.attempt.id),
        )
    )
    with pytest.raises(TaskTransitionError) as excinfo:
        _heartbeat(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=2,
        )
    assert excinfo.value.reason == "attempt_not_live"


# ---------------------------------------------------------------------------
# Orphan expiry (receipt-protected, m2 plan step 7, T12)
# ---------------------------------------------------------------------------


def test_expire_overdue_requeues_when_budget_remains(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id, max_attempts=2)
    claim = _claim(task_env, project_id=project.id, lease_seconds=60, now=TS)
    assert claim is not None
    started = _start(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        expected_status_version=1,
        lease_id=claim.attempt.lease_id,
        now=TS,
    )
    assert started.status == "running"
    counts_before = _counts(task_env.writer)

    result = _expire(task_env, project_id=project.id, idempotency_key="exp-req-k")
    assert result is not None
    assert result.outcome == "requeued"
    assert result.task.id == task.id
    assert result.task.status == "queued"
    assert result.task.finished_at is None
    assert result.attempt.id == claim.attempt.id
    assert result.attempt.status == "expired"
    assert result.attempt.status_version == 3  # claimed(1) -> running(2) -> expired(3)
    assert result.attempt.finished_at == TS2

    # One expired event and one complete receipt; the task is claimable again.
    counts_after = _counts(task_env.writer)
    assert counts_after == (
        counts_before[0],
        counts_before[1],
        counts_before[2] + 1,
        counts_before[3] + 1,
        counts_before[4],
    )
    events = _event_rows(task_env.writer, f"{task.id}:{CORE_TASK_STREAM_TYPE}")
    assert events[-1]["kind"] == CORE_TASK_EXPIRED_EVENT_KIND
    data = json.loads(events[-1]["payload_json"])["data"]
    assert data["outcome"] == "requeued"
    assert data["reason"] == "lease_expired"
    receipt = _receipt_row(task_env.writer, project.id, "exp-req-k")
    assert receipt["command_kind"] == CORE_TASK_EXPIRE_COMMAND_KIND

    # The requeued task gets a fresh fenced attempt on the next claim.
    second = _claim(task_env, project_id=project.id, idempotency_key="exp-claim-2", now=TS2)
    assert second is not None
    assert second.task.id == task.id
    assert second.attempt.attempt_no == 2


def test_expire_overdue_fails_terminally_when_budget_exhausted(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id, max_attempts=1)
    claim = _claim(task_env, project_id=project.id, lease_seconds=60, now=TS)
    assert claim is not None

    result = _expire(task_env, project_id=project.id, idempotency_key="exp-fail-k")
    assert result is not None
    assert result.outcome == "failed"
    assert result.task.status == "failed"
    assert result.task.finished_at == TS2
    assert result.task.winning_attempt_id is None
    assert result.attempt.status == "expired"
    assert result.attempt.finished_at == TS2

    events = _event_rows(task_env.writer, f"{task.id}:{CORE_TASK_STREAM_TYPE}")
    assert json.loads(events[-1]["payload_json"])["data"]["outcome"] == "failed"
    # Terminal tasks never resurrect: no claim can ever pick it up again.
    assert _claim(task_env, project_id=project.id, idempotency_key="exp-claim-3") is None


def test_expire_overdue_returns_none_when_nothing_overdue(task_env) -> None:
    project = _create_project(task_env)
    _admit(task_env, project_id=project.id)
    # Lease of 300s expires at 00:05; the first sweep instant is 00:00.
    _claim(task_env, project_id=project.id, lease_seconds=300, now=TS)
    counts = _counts(task_env.writer)
    assert (
        _expire(task_env, project_id=project.id, idempotency_key="exp-none-k", now=TS)
        is None
    )
    assert _counts(task_env.writer) == counts
    # A later sweep (00:10, past the lease) finds the attempt overdue.
    result = _expire(
        task_env, project_id=project.id, idempotency_key="exp-none-2", now="2026-08-16T00:10:00+00:00"
    )
    assert result is not None
    assert result.outcome == "failed"  # max_attempts default is 1


def test_expire_overdue_is_deterministic_fifo_by_lease_expiry(task_env) -> None:
    project = _create_project(task_env)
    first = _admit(task_env, project_id=project.id, task_id=generate_lowercase_ulid())
    second = _admit(task_env, project_id=project.id, task_id=generate_lowercase_ulid())
    # First claim at 00:00 with a 60s lease; second at 00:00:30 with a 60s
    # lease. Both overdue at 01:00; expiry order is lease-expiry ascending.
    claim_a = _claim(task_env, project_id=project.id, idempotency_key="fifo-1", lease_seconds=60, now=TS)
    assert claim_a is not None and claim_a.task.id == first.id
    claim_b = _claim(
        task_env,
        project_id=project.id,
        idempotency_key="fifo-2",
        lease_seconds=60,
        now="2026-08-16T00:00:30+00:00",
    )
    assert claim_b is not None and claim_b.task.id == second.id

    first_expiry = _expire(task_env, project_id=project.id, idempotency_key="fifo-exp-1")
    assert first_expiry is not None
    assert first_expiry.task.id == first.id  # earliest lease expiry first
    second_expiry = _expire(task_env, project_id=project.id, idempotency_key="fifo-exp-2")
    assert second_expiry is not None
    assert second_expiry.task.id == second.id
    assert _expire(task_env, project_id=project.id, idempotency_key="fifo-exp-3") is None


def test_expire_overdue_replay_and_mismatch(task_env) -> None:
    project = _create_project(task_env)
    _admit(task_env, project_id=project.id, max_attempts=2)
    _claim(task_env, project_id=project.id, lease_seconds=60, now=TS)
    key = "exp-replay-k"

    first = _expire(task_env, project_id=project.id, idempotency_key=key)
    assert first is not None
    counts = _counts(task_env.writer)
    second = _expire(task_env, project_id=project.id, idempotency_key=key)
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(task_env.writer) == counts

    # Same key with a different command kind: mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _expire(
            task_env,
            project_id=project.id,
            idempotency_key=key,
            command_kind="core.task.cancel",
        )
    assert _counts(task_env.writer) == counts
    # The expiry read model round-trips through the stored receipt result.
    rebuilt = TaskExpiryReadModel.from_mapping(first.to_dict())
    assert rebuilt == first


def test_expired_attempt_cannot_be_heartbeated(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id, max_attempts=2)
    claim = _claim(task_env, project_id=project.id, lease_seconds=60, now=TS)
    assert claim is not None
    _expire(task_env, project_id=project.id, idempotency_key="exp-heart-k")
    counts = _counts(task_env.writer)

    # After expiry (task requeued, attempt expired) nothing can extend it:
    # the task is no longer running, so the typed outcome fires first.
    with pytest.raises(TaskTransitionError) as excinfo:
        _heartbeat(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=1,
        )
    assert excinfo.value.reason == "task_not_running"
    row = _attempt_rows(task_env.writer, task.id)[0]
    assert row["status"] == "expired"
    assert row["status_version"] == 2  # claimed(1) -> expired(2)
    assert _counts(task_env.writer) == counts


# ---------------------------------------------------------------------------
# Cancellation and fenced failure (m2 plan step 8, T13)
# ---------------------------------------------------------------------------


def _cancel(
    env,
    *,
    project_id: str,
    task_id: str,
    idempotency_key: str,
    **overrides,
):
    """Run one cancel command inside its own unit of work."""
    args = {
        "project_id": project_id,
        "task_id": task_id,
        "idempotency_key": idempotency_key,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.cancel(u, **args))


def _fail(
    env,
    *,
    project_id: str,
    task_id: str,
    attempt_id: str,
    lease_id: str,
    expected_status_version: int,
    idempotency_key: str,
    **overrides,
):
    """Run one fail command inside its own unit of work."""
    args = {
        "project_id": project_id,
        "task_id": task_id,
        "attempt_id": attempt_id,
        "lease_id": lease_id,
        "expected_status_version": expected_status_version,
        "idempotency_key": idempotency_key,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.fail(u, **args))


def _retry(
    env,
    *,
    project_id: str,
    task_id: str,
    idempotency_key: str,
    **overrides,
):
    """Run one retry command inside its own unit of work."""
    args = {
        "project_id": project_id,
        "task_id": task_id,
        "idempotency_key": idempotency_key,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.retry(u, **args))


def test_cancel_queued_task_is_terminal_without_attempt(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    counts = _counts(task_env.writer)

    result = _cancel(
        task_env,
        project_id=project.id,
        task_id=task.id,
        idempotency_key="cancel-queued-k",
        cancel_request_id="req-1",
    )
    assert result.task.status == "cancelled"
    assert result.task.finished_at == TS2
    assert result.task.cancel_request_id == "req-1"
    assert result.task.cancel_requested_at == TS2
    assert result.task.winning_attempt_id is None
    assert result.attempt is None

    counts_after = _counts(task_env.writer)
    assert counts_after == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4],
    )
    row = _task_row(task_env.writer, task.id)
    assert row["status"] == "cancelled"
    assert row["cancel_request_id"] == "req-1"
    assert row["finished_at"] == TS2
    assert _attempt_rows(task_env.writer, task.id) == []

    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    events = _event_rows(task_env.writer, stream_id)
    assert events[-1]["kind"] == CORE_TASK_CANCELLED_EVENT_KIND
    data = json.loads(events[-1]["payload_json"])["data"]
    assert data["task_id"] == task.id
    assert data["attempt_id"] is None
    assert data["cancel_request_id"] == "req-1"
    assert data["reason"] == "queued"
    assert _project_head(task_env.writer, project.id) == 3  # created + cancelled

    # Terminal tasks never resurrect: no claim can ever pick it up again.
    assert _claim(task_env, project_id=project.id, idempotency_key="cancel-claim") is None

    receipt = _receipt_row(task_env.writer, project.id, "cancel-queued-k")
    assert receipt["command_kind"] == CORE_TASK_CANCEL_COMMAND_KIND
    rebuilt = TaskCancelReadModel.from_mapping(json.loads(receipt["result_json"]))
    assert rebuilt == result


def test_cancel_running_task_terminates_owned_attempt(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    counts = _counts(task_env.writer)

    result = _cancel(
        task_env,
        project_id=project.id,
        task_id=task.id,
        idempotency_key="cancel-running-k",
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=1,
    )
    assert result.task.status == "cancelled"
    assert result.task.finished_at == TS2
    assert result.task.winning_attempt_id is None
    assert result.attempt is not None
    assert result.attempt.id == claim.attempt.id
    assert result.attempt.status == "cancelled"
    assert result.attempt.status_version == 2
    assert result.attempt.finished_at == TS2

    counts_after = _counts(task_env.writer)
    assert counts_after == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4],
    )
    attempts = _attempt_rows(task_env.writer, task.id)
    assert len(attempts) == 1
    assert attempts[0]["status"] == "cancelled"
    assert attempts[0]["status_version"] == 2
    assert attempts[0]["finished_at"] == TS2

    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    events = _event_rows(task_env.writer, stream_id)
    assert events[-1]["kind"] == CORE_TASK_CANCELLED_EVENT_KIND
    data = json.loads(events[-1]["payload_json"])["data"]
    assert data["attempt_id"] == claim.attempt.id
    assert data["attempt_no"] == 1
    assert data["status_version"] == 2
    assert data["lease_id"] == claim.attempt.lease_id
    assert data["reason"] == "running"
    # created, claimed, cancelled.
    assert _project_head(task_env.writer, project.id) == 4

    receipt = _receipt_row(task_env.writer, project.id, "cancel-running-k")
    assert receipt["resulting_stream_seq"] == 3
    rebuilt = TaskCancelReadModel.from_mapping(json.loads(receipt["result_json"]))
    assert rebuilt == result
    assert _claim(task_env, project_id=project.id, idempotency_key="cancel-claim-2") is None


def test_cancel_fences_running_attempt(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    counts = _counts(task_env.writer)

    # Running cancellation without the fence facts is a validation error.
    with pytest.raises(TaskValidationError):
        _cancel(
            task_env,
            project_id=project.id,
            task_id=task.id,
            idempotency_key="cancel-no-fence-k",
        )
    # Wrong lease: the caller does not own the attempt.
    with pytest.raises(TaskTransitionError) as excinfo:
        _cancel(
            task_env,
            project_id=project.id,
            task_id=task.id,
            idempotency_key="cancel-lease-k",
            attempt_id=claim.attempt.id,
            lease_id="not-the-lease",
            expected_status_version=1,
        )
    assert excinfo.value.reason == "lease_mismatch"
    # Stale version.
    with pytest.raises(TaskTransitionError) as excinfo:
        _cancel(
            task_env,
            project_id=project.id,
            task_id=task.id,
            idempotency_key="cancel-version-k",
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=9,
        )
    assert excinfo.value.reason == "stale_status_version"
    # A foreign attempt id.
    with pytest.raises(TaskAttemptNotFoundError):
        _cancel(
            task_env,
            project_id=project.id,
            task_id=task.id,
            idempotency_key="cancel-attempt-k",
            attempt_id=generate_lowercase_ulid(),
            lease_id=claim.attempt.lease_id,
            expected_status_version=1,
        )
    assert _counts(task_env.writer) == counts
    assert _task_row(task_env.writer, task.id)["status"] == "running"
    assert _attempt_rows(task_env.writer, task.id)[0]["status"] == "claimed"


def test_cancel_terminal_task_is_typed_outcome_and_writer_order_wins(task_env) -> None:
    project = _create_project(task_env)
    first = _admit(task_env, project_id=project.id, max_attempts=1)
    second = _admit(task_env, project_id=project.id, max_attempts=1)
    claim_a = _claim(task_env, project_id=project.id, idempotency_key="co-1")
    assert claim_a is not None and claim_a.task.id == first.id
    claim_b = _claim(task_env, project_id=project.id, idempotency_key="co-2")
    assert claim_b is not None and claim_b.task.id == second.id

    # Writer order: fail commits first -> task failed terminally; a later
    # cancel sees the terminal task and changes zero rows.
    _fail(
        task_env,
        project_id=project.id,
        task_id=first.id,
        attempt_id=claim_a.attempt.id,
        lease_id=claim_a.attempt.lease_id,
        expected_status_version=1,
        idempotency_key="co-fail-1",
    )
    counts = _counts(task_env.writer)
    with pytest.raises(TaskTransitionError) as excinfo:
        _cancel(
            task_env,
            project_id=project.id,
            task_id=first.id,
            idempotency_key="co-cancel-1",
            attempt_id=claim_a.attempt.id,
            lease_id=claim_a.attempt.lease_id,
            expected_status_version=2,
        )
    assert excinfo.value.reason == "task_terminal"
    assert _counts(task_env.writer) == counts
    assert _task_row(task_env.writer, first.id)["status"] == "failed"

    # Writer order: cancel commits first -> task cancelled terminally; a
    # later fail sees the terminal task and changes zero rows.
    _cancel(
        task_env,
        project_id=project.id,
        task_id=second.id,
        idempotency_key="co-cancel-2",
        attempt_id=claim_b.attempt.id,
        lease_id=claim_b.attempt.lease_id,
        expected_status_version=1,
    )
    counts = _counts(task_env.writer)
    with pytest.raises(TaskTransitionError) as excinfo:
        _fail(
            task_env,
            project_id=project.id,
            task_id=second.id,
            attempt_id=claim_b.attempt.id,
            lease_id=claim_b.attempt.lease_id,
            expected_status_version=2,
            idempotency_key="co-fail-2",
        )
    assert excinfo.value.reason == "task_not_running"
    assert _counts(task_env.writer) == counts
    assert _task_row(task_env.writer, second.id)["status"] == "cancelled"
    # Neither terminal task resurrects.
    assert _claim(task_env, project_id=project.id, idempotency_key="co-3") is None


def test_cancel_replay_and_mismatch(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    key = "cancel-replay-k"
    first = _cancel(
        task_env, project_id=project.id, task_id=task.id, idempotency_key=key
    )
    counts = _counts(task_env.writer)

    second = _cancel(
        task_env, project_id=project.id, task_id=task.id, idempotency_key=key
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(task_env.writer) == counts

    # Same key with a different command kind: mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _cancel(
            task_env,
            project_id=project.id,
            task_id=task.id,
            idempotency_key=key,
            command_kind=CORE_TASK_FAIL_COMMAND_KIND,
        )
    assert _counts(task_env.writer) == counts


def test_fail_requeues_within_budget_and_fences(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id, max_attempts=2)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    counts = _counts(task_env.writer)

    result = _fail(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=1,
        idempotency_key="fail-requeue-k",
        error={"message": "renderer blew up", "code": 7},
    )
    assert result.outcome == "requeued"
    assert result.task.status == "queued"
    assert result.task.finished_at is None
    assert result.task.winning_attempt_id is None
    assert result.attempt.status == "failed"
    assert result.attempt.status_version == 2
    assert result.attempt.finished_at == TS2
    assert result.attempt.error == {"message": "renderer blew up", "code": 7}

    counts_after = _counts(task_env.writer)
    assert counts_after == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4],
    )
    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    events = _event_rows(task_env.writer, stream_id)
    assert events[-1]["kind"] == CORE_TASK_FAILED_EVENT_KIND
    data = json.loads(events[-1]["payload_json"])["data"]
    assert data["outcome"] == "requeued"
    assert data["reason"] == "executor_failed"
    assert data["error"] == {"message": "renderer blew up", "code": 7}

    # A fresh claim creates attempt_no 2 (the budget remains).
    second = _claim(task_env, project_id=project.id, idempotency_key="fail-claim-2")
    assert second is not None
    assert second.task.id == task.id
    assert second.attempt.attempt_no == 2
    assert second.attempt.status_version == 1

    # Fences: stale version and wrong lease change zero rows.
    counts = _counts(task_env.writer)
    with pytest.raises(TaskTransitionError) as excinfo:
        _fail(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=second.attempt.id,
            lease_id=second.attempt.lease_id,
            expected_status_version=7,
            idempotency_key="fail-stale-k",
        )
    assert excinfo.value.reason == "stale_status_version"
    with pytest.raises(TaskTransitionError) as excinfo:
        _fail(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=second.attempt.id,
            lease_id="wrong-lease",
            expected_status_version=1,
            idempotency_key="fail-lease-k",
        )
    assert excinfo.value.reason == "lease_mismatch"
    assert _counts(task_env.writer) == counts
    assert _task_row(task_env.writer, task.id)["status"] == "running"


def test_fail_terminally_fails_when_budget_exhausted(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id, max_attempts=1)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None

    result = _fail(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=1,
        idempotency_key="fail-terminal-k",
    )
    assert result.outcome == "failed"
    assert result.task.status == "failed"
    assert result.task.finished_at == TS2
    assert result.task.winning_attempt_id is None
    assert result.attempt.status == "failed"
    assert result.attempt.status_version == 2

    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    events = _event_rows(task_env.writer, stream_id)
    assert json.loads(events[-1]["payload_json"])["data"]["outcome"] == "failed"
    receipt = _receipt_row(task_env.writer, project.id, "fail-terminal-k")
    assert receipt["command_kind"] == CORE_TASK_FAIL_COMMAND_KIND
    assert receipt["resulting_stream_seq"] == 3
    rebuilt = TaskFailReadModel.from_mapping(json.loads(receipt["result_json"]))
    assert rebuilt == result
    # Terminal tasks never resurrect.
    assert _claim(task_env, project_id=project.id, idempotency_key="fail-claim-3") is None


def test_fail_replay_and_mismatch(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    key = "fail-replay-k"
    first = _fail(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=1,
        idempotency_key=key,
    )
    counts = _counts(task_env.writer)
    second = _fail(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=1,
        idempotency_key=key,
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(task_env.writer) == counts

    # Same key with a different error payload: mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _fail(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=1,
            idempotency_key=key,
            error={"different": True},
        )
    assert _counts(task_env.writer) == counts


# ---------------------------------------------------------------------------
# Eligible nonterminal retry (m2 plan step 8, T14)
# ---------------------------------------------------------------------------


def test_retry_creates_new_fenced_attempt_for_failed_work(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id, max_attempts=3)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    counts = _counts(task_env.writer)

    # Fail with budget remaining: the task requeues (attempt 1 failed).
    _fail(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=1,
        idempotency_key="retry-fail-1",
        error={"message": "transient"},
    )

    result = _retry(
        task_env,
        project_id=project.id,
        task_id=task.id,
        idempotency_key="retry-k-1",
        executor_id="executor-retry",
    )
    assert result.task.id == task.id
    assert result.task.status == "running"
    assert result.task.finished_at is None
    assert result.task.winning_attempt_id is None
    assert result.attempt.attempt_no == 2
    assert result.attempt.status == "claimed"
    assert result.attempt.status_version == 1
    assert result.attempt.executor_id == "executor-retry"
    assert result.attempt.lease_id is not None
    assert result.attempt.finished_at is None
    assert result.prior_attempt_no == 1
    assert result.prior_attempt_status == "failed"

    counts_after = _counts(task_env.writer)
    assert counts_after == (
        counts[0],
        counts[1],
        counts[2] + 2,  # failed + retried
        counts[3] + 2,  # fail receipt + retry receipt
        counts[4] + 1,  # the new fenced attempt
    )

    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    events = _event_rows(task_env.writer, stream_id)
    assert events[-1]["kind"] == CORE_TASK_RETRIED_EVENT_KIND
    data = json.loads(events[-1]["payload_json"])["data"]
    assert data["task_id"] == task.id
    assert data["attempt_id"] == result.attempt.id
    assert data["attempt_no"] == 2
    assert data["status_version"] == 1
    assert data["prior_attempt_no"] == 1
    assert data["prior_attempt_status"] == "failed"
    assert data["reason"] == "failed"

    receipt = _receipt_row(task_env.writer, project.id, "retry-k-1")
    assert receipt["command_kind"] == CORE_TASK_RETRY_COMMAND_KIND
    rebuilt = TaskRetryReadModel.from_mapping(json.loads(receipt["result_json"]))
    assert rebuilt == result

    # The task is running with a live attempt: a claim can never create a
    # competing attempt, and the retried attempt can start normally.
    started = _start(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=result.attempt.id,
        expected_status_version=1,
        idempotency_key="retry-start",
        lease_id=result.attempt.lease_id,
    )
    assert started.status == "running"
    assert started.status_version == 2


def test_retry_after_expired_work_creates_new_fenced_attempt(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id, max_attempts=2)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None

    # Expire the live attempt with budget remaining: task requeues.
    expiry = _expire(
        task_env,
        project_id=project.id,
        idempotency_key="retry-expire-k",
        now="2026-08-16T02:00:00.000000+00:00",
    )
    assert expiry is not None
    assert expiry.task.id == task.id
    assert expiry.outcome == "requeued"
    assert _task_row(task_env.writer, task.id)["status"] == "queued"

    result = _retry(
        task_env,
        project_id=project.id,
        task_id=task.id,
        idempotency_key="retry-expired-k",
    )
    assert result.task.status == "running"
    assert result.attempt.attempt_no == 2
    assert result.attempt.status == "claimed"
    assert result.prior_attempt_no == 1
    assert result.prior_attempt_status == "expired"

    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    events = _event_rows(task_env.writer, stream_id)
    assert events[-1]["kind"] == CORE_TASK_RETRIED_EVENT_KIND
    data = json.loads(events[-1]["payload_json"])["data"]
    assert data["prior_attempt_status"] == "expired"


def test_retry_rejects_terminal_task_without_changing_evidence(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id, max_attempts=1)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    _fail(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=1,
        idempotency_key="retry-terminal-fail",
    )
    assert _task_row(task_env.writer, task.id)["status"] == "failed"

    counts = _counts(task_env.writer)
    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    events_before = _event_rows(task_env.writer, stream_id)
    head_before = _project_head(task_env.writer, project.id)

    with pytest.raises(TaskTransitionError) as excinfo:
        _retry(
            task_env,
            project_id=project.id,
            task_id=task.id,
            idempotency_key="retry-terminal-k",
        )
    assert excinfo.value.reason == "task_terminal"

    # Every command against the terminal task is a typed rejection that
    # leaves events, heads, and receipts byte-identical.
    with pytest.raises(TaskTransitionError) as excinfo:
        _cancel(
            task_env,
            project_id=project.id,
            task_id=task.id,
            idempotency_key="retry-terminal-cancel",
        )
    assert excinfo.value.reason == "task_terminal"
    with pytest.raises(TaskTransitionError) as excinfo:
        _fail(
            task_env,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=2,
            idempotency_key="retry-terminal-fail2",
        )
    assert excinfo.value.reason == "task_not_running"

    assert _counts(task_env.writer) == counts
    assert _event_rows(task_env.writer, stream_id) == events_before
    assert _project_head(task_env.writer, project.id) == head_before
    assert _task_row(task_env.writer, task.id)["status"] == "failed"
    assert _attempt_rows(task_env.writer, task.id)[0]["status"] == "failed"
    # The terminal task never resurrects: no claim, no retry.
    assert _claim(task_env, project_id=project.id, idempotency_key="retry-claim") is None


def test_retry_rejects_never_claimed_and_running_tasks(task_env) -> None:
    project = _create_project(task_env)
    queued = _admit(task_env, project_id=project.id, max_attempts=2)
    counts = _counts(task_env.writer)

    # A never-claimed queued task has no failed/expired work to retry.
    with pytest.raises(TaskTransitionError) as excinfo:
        _retry(
            task_env,
            project_id=project.id,
            task_id=queued.id,
            idempotency_key="retry-never-claimed",
        )
    assert excinfo.value.reason == "not_retryable"
    assert _counts(task_env.writer) == counts
    assert _task_row(task_env.writer, queued.id)["status"] == "queued"

    # A running task with a live attempt is not retryable either.
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    with pytest.raises(TaskTransitionError) as excinfo:
        _retry(
            task_env,
            project_id=project.id,
            task_id=claim.task.id,
            idempotency_key="retry-running",
        )
    assert excinfo.value.reason == "not_retryable"
    assert _task_row(task_env.writer, claim.task.id)["status"] == "running"
    assert _attempt_rows(task_env.writer, claim.task.id)[0]["status"] == "claimed"


def test_retry_rejects_exhausted_budget_as_typed_outcome(task_env) -> None:
    """The defensive budget fence: even a queued task whose latest attempt
    consumed the whole budget is a typed rejection, never a retry."""
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id, max_attempts=1)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    _fail(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=1,
        idempotency_key="retry-budget-fail",
    )
    assert _task_row(task_env.writer, task.id)["status"] == "failed"

    # White-box: force the impossible-looking state (queued task whose only
    # attempt consumed the budget) to prove the fence runs before mutation.
    def _force_state(session):
        session.execute(
            "UPDATE tasks SET status = 'queued', finished_at = NULL "
            "WHERE id = ?",
            (task.id,),
        )
        session.execute(
            "UPDATE execution_attempts SET attempt_no = 1 "
            "WHERE id = ?",
            (claim.attempt.id,),
        )

    task_env.writer.submit(_force_state)
    counts = _counts(task_env.writer)
    with pytest.raises(TaskTransitionError) as excinfo:
        _retry(
            task_env,
            project_id=project.id,
            task_id=task.id,
            idempotency_key="retry-budget-k",
        )
    assert excinfo.value.reason == "attempt_budget_exhausted"
    assert _counts(task_env.writer) == counts


def test_retry_replay_and_mismatch_with_selected_task_set(task_env) -> None:
    project = _create_project(task_env)
    first = _admit(task_env, project_id=project.id, max_attempts=2)
    second = _admit(task_env, project_id=project.id, max_attempts=2)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    _fail(
        task_env,
        project_id=project.id,
        task_id=first.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=1,
        idempotency_key="retry-replay-fail",
    )
    selection = [second.id, first.id]  # unordered: canonicalized to sorted

    key = "retry-replay-k"
    first_result = _retry(
        task_env,
        project_id=project.id,
        task_id=first.id,
        idempotency_key=key,
        selected_task_ids=selection,
    )
    counts = _counts(task_env.writer)
    replayed = _retry(
        task_env,
        project_id=project.id,
        task_id=first.id,
        idempotency_key=key,
        selected_task_ids=[first.id, second.id],  # same set, other order
    )
    assert replayed == first_result
    assert replayed.to_dict() == first_result.to_dict()
    assert _counts(task_env.writer) == counts

    # The same key with a different selection set is a mismatch before any
    # mutation.
    with pytest.raises(ReceiptMismatchError):
        _retry(
            task_env,
            project_id=project.id,
            task_id=first.id,
            idempotency_key=key,
            selected_task_ids=[first.id],
        )
    assert _counts(task_env.writer) == counts


def test_retry_validates_selected_task_set_shape(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id, max_attempts=2)
    claim = _claim(task_env, project_id=project.id)
    assert claim is not None
    _fail(
        task_env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=1,
        idempotency_key="retry-shape-fail",
    )
    with pytest.raises(TaskValidationError):
        _retry(
            task_env,
            project_id=project.id,
            task_id=task.id,
            idempotency_key="retry-shape-1",
            selected_task_ids=[],
        )
    with pytest.raises(TaskValidationError):
        _retry(
            task_env,
            project_id=project.id,
            task_id=task.id,
            idempotency_key="retry-shape-2",
            selected_task_ids=[task.id, task.id],
        )
    with pytest.raises(TaskValidationError):
        _retry(
            task_env,
            project_id=project.id,
            task_id=task.id,
            idempotency_key="retry-shape-3",
            selected_task_ids=[""],
        )
