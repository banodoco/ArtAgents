"""Executable task SDK service tests (m4 plan step 12, task T13).

Proves ``astrid.sdk.tasks.TasksService`` exposes repository-backed,
envelope-shaped ``create``/``list``/``show``/``cancel``/``retry``/``events``
over the kernel :class:`~astrid.core.repositories.tasks.TaskRepository`:

- the five-key envelope shape with the committed nine-key receipt on
  mutations and a null receipt on pure reads;
- caller keys preserved, generated keys returned and fresh, empty keys
  rejected as ``validation_error``;
- deterministic task ids derived from the idempotency key, so an identical
  retry replays the committed result with zero new rows and a changed
  request under the same key returns ``idempotency_mismatch``;
- typed ``not_found`` for a missing task, ``terminal_state`` for a terminal
  cancel/retry, and ``validation_error`` for a missing project;
- ordered ``core.task`` stream events, and cancel/retry behavior that
  reuses the repository's fencing, cancellation, and retry logic.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.registry import core_only_registry
from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.events import EventRepository
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.repositories.tasks import (
    CORE_TASK_CREATE_COMMAND_KIND,
    CORE_TASK_STREAM_TYPE,
    TaskRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.sdk.contracts import derive_stable_id
from astrid.sdk.tasks import TasksService

ENVELOPE_KEYS = {"ok", "data", "error", "receipt", "idempotency_key"}
RECEIPT_KEYS = {
    "receipt_id",
    "command_kind",
    "idempotency_key",
    "request_hash",
    "project_id",
    "project_seq",
    "event_ids",
    "result",
    "created_at",
}

TS = "2026-08-18T00:00:00.000000+00:00"


@pytest.fixture
def env(tmp_path: Path):
    """A fresh kernel writer, project/task repos, event log, and task service."""
    registry = core_only_registry()
    writer = DatabaseWriter(tmp_path / "tasks.sqlite3", registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        tasks = TaskRepository(events=events, receipts=receipts)
        event_log = EventRepository(writer)
        yield SimpleNamespace(
            writer=writer,
            projects=projects,
            tasks=tasks,
            receipts=receipts,
            event_log=event_log,
            service=TasksService(writer, tasks, receipts, event_log),
        )
    finally:
        writer.close()


def _create_project(env: SimpleNamespace, *, slug: str = "demo") -> str:
    project_id = generate_lowercase_ulid()
    UnitOfWork(env.writer).run(
        lambda u: env.projects.create(
            u,
            slug=slug,
            name=slug.title(),
            settings={},
            idempotency_key=f"create-{slug}-k",
            project_id=project_id,
        )
    )
    return project_id


def _fail_task(env: SimpleNamespace, *, project_id: str, task_id: str) -> None:
    """Drive one queued task to a failed attempt via the internal executor verbs."""
    claim = UnitOfWork(env.writer).run(
        lambda u: env.tasks.claim(
            u,
            project_id=project_id,
            idempotency_key="claim-k",
            executor_id="executor-test",
            now=TS,
        )
    )
    assert claim is not None
    started = UnitOfWork(env.writer).run(
        lambda u: env.tasks.start(
            u,
            project_id=project_id,
            task_id=task_id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=claim.attempt.status_version,
            idempotency_key="start-k",
            now=TS,
        )
    )
    UnitOfWork(env.writer).run(
        lambda u: env.tasks.fail(
            u,
            project_id=project_id,
            task_id=task_id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=started.status_version,
            idempotency_key="fail-k",
            now=TS,
            error={"kind": "test.fixture", "message": "intentional failure"},
        )
    )


def _task_count(env: SimpleNamespace) -> int:
    return env.writer.submit(
        lambda s: s.query_one("SELECT COUNT(*) FROM tasks")[0]
    )


# ---------------------------------------------------------------------------
# Envelope and receipt shape
# ---------------------------------------------------------------------------


def test_create_envelope_has_exactly_five_keys(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    result = env.service.create(
        project_id=project_id, capability="cap.a", spec={"x": 1}
    )
    assert result.ok is True
    assert set(result.as_dict().keys()) == ENVELOPE_KEYS
    assert result.error is None
    assert result.receipt is not None
    assert set(result.receipt.as_dict().keys()) == RECEIPT_KEYS
    assert result.receipt.command_kind == CORE_TASK_CREATE_COMMAND_KIND


def test_read_envelopes_carry_null_receipt_and_empty_key(
    env: SimpleNamespace,
) -> None:
    project_id = _create_project(env)
    created = env.service.create(
        project_id=project_id, capability="cap.a", spec={"x": 1}
    )
    listed = env.service.list(project_id)
    shown = env.service.show(created.data["id"])
    events = env.service.events(created.data["id"])
    for result in (listed, shown, events):
        assert result.ok is True
        assert result.receipt is None
        assert result.idempotency_key == ""


# ---------------------------------------------------------------------------
# Idempotency keys and deterministic ids
# ---------------------------------------------------------------------------


def test_caller_key_preserved_and_generated_key_fresh(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    first = env.service.create(
        project_id=project_id,
        capability="cap.a",
        spec={"x": 1},
        idempotency_key="caller-1",
    )
    second = env.service.create(
        project_id=project_id, capability="cap.b", spec={"x": 2}
    )
    assert first.idempotency_key == "caller-1"
    assert second.ok is True
    assert second.idempotency_key
    assert second.idempotency_key != first.idempotency_key


def test_empty_key_returns_validation_error_before_mutation(
    env: SimpleNamespace,
) -> None:
    project_id = _create_project(env)
    result = env.service.create(
        project_id=project_id,
        capability="cap.a",
        spec={"x": 1},
        idempotency_key="",
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "validation_error"
    assert _task_count(env) == 0


def test_create_derives_deterministic_id_from_key(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    expected = derive_stable_id(
        command_kind=CORE_TASK_CREATE_COMMAND_KIND,
        scope=project_id,
        idempotency_key="k-deterministic",
        ordinal=0,
    )
    result = env.service.create(
        project_id=project_id,
        capability="cap.a",
        spec={"x": 1},
        idempotency_key="k-deterministic",
    )
    assert result.ok is True
    assert result.data["id"] == expected


# ---------------------------------------------------------------------------
# Replay and mismatch-before-mutation
# ---------------------------------------------------------------------------


def test_identical_retry_replays_with_zero_new_rows(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    first = env.service.create(
        project_id=project_id,
        capability="cap.a",
        spec={"x": 1},
        idempotency_key="k1",
    )
    first_receipt_id = first.receipt.receipt_id
    assert _task_count(env) == 1

    second = env.service.create(
        project_id=project_id,
        capability="cap.a",
        spec={"x": 1},
        idempotency_key="k1",
    )
    assert second.ok is True
    assert second.data["id"] == first.data["id"]
    assert second.receipt.receipt_id == first_receipt_id
    assert second.receipt == first.receipt
    assert _task_count(env) == 1


def test_mismatch_returns_idempotency_mismatch_before_mutation(
    env: SimpleNamespace,
) -> None:
    project_id = _create_project(env)
    first = env.service.create(
        project_id=project_id,
        capability="cap.a",
        spec={"x": 1},
        idempotency_key="k1",
    )
    assert first.ok is True

    changed = env.service.create(
        project_id=project_id,
        capability="cap.a",
        spec={"x": 2},
        idempotency_key="k1",
    )
    assert changed.ok is False
    assert changed.error is not None
    assert changed.error.code == "idempotency_mismatch"
    assert changed.idempotency_key == "k1"
    assert _task_count(env) == 1


# ---------------------------------------------------------------------------
# List and show
# ---------------------------------------------------------------------------


def test_list_returns_created_at_sorted_rows(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    a = env.service.create(project_id=project_id, capability="cap.a", spec={"x": 1})
    b = env.service.create(project_id=project_id, capability="cap.b", spec={"x": 2})
    result = env.service.list(project_id)
    assert result.ok is True
    ids = [row["id"] for row in result.data]
    assert ids == [a.data["id"], b.data["id"]]


def test_show_resolves_by_id(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    created = env.service.create(project_id=project_id, capability="cap.a", spec={"x": 1})
    shown = env.service.show(created.data["id"])
    assert shown.ok is True
    assert shown.data == created.data


def test_show_missing_returns_not_found(env: SimpleNamespace) -> None:
    result = env.service.show("missing-task")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"


def test_create_requires_existing_project_returns_validation_error(
    env: SimpleNamespace,
) -> None:
    result = env.service.create(
        project_id="missing-project", capability="cap.a", spec={"x": 1}
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "validation_error"


# ---------------------------------------------------------------------------
# Cancel: terminal immutability and receipts
# ---------------------------------------------------------------------------


def test_cancel_queued_task_returns_receipt_and_cancelled_state(
    env: SimpleNamespace,
) -> None:
    project_id = _create_project(env)
    created = env.service.create(
        project_id=project_id,
        capability="cap.a",
        spec={"x": 1},
        idempotency_key="create-k",
    )
    task_id = created.data["id"]

    cancelled = env.service.cancel(project_id, task_id, idempotency_key="cancel-k")
    assert cancelled.ok is True
    assert cancelled.receipt is not None
    assert cancelled.receipt.command_kind == "core.task.cancel"
    assert cancelled.data["task"]["status"] == "cancelled"
    assert cancelled.data["task"]["id"] == task_id

    shown = env.service.show(task_id)
    assert shown.data["status"] == "cancelled"


def test_cancel_terminal_task_returns_terminal_state(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    created = env.service.create(project_id=project_id, capability="cap.a", spec={"x": 1})
    task_id = created.data["id"]
    assert env.service.cancel(project_id, task_id).ok is True

    second = env.service.cancel(project_id, task_id, idempotency_key="cancel-2")
    assert second.ok is False
    assert second.error is not None
    assert second.error.code == "terminal_state"


def test_cancel_replay_returns_same_receipt(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    created = env.service.create(project_id=project_id, capability="cap.a", spec={"x": 1})
    task_id = created.data["id"]

    first = env.service.cancel(project_id, task_id, idempotency_key="cancel-k")
    replay = env.service.cancel(project_id, task_id, idempotency_key="cancel-k")
    assert first.ok is True
    assert replay.ok is True
    assert replay.receipt.receipt_id == first.receipt.receipt_id
    assert replay.data == first.data


def test_cancel_missing_returns_not_found(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    result = env.service.cancel(project_id, "missing-task")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"


# ---------------------------------------------------------------------------
# Retry: reuse repository eligibility and retry selection
# ---------------------------------------------------------------------------


def test_retry_restarts_failed_task(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    created = env.service.create(
        project_id=project_id,
        capability="cap.a",
        spec={"x": 1},
        available_at=TS,
        max_attempts=2,
    )
    task_id = created.data["id"]
    _fail_task(env, project_id=project_id, task_id=task_id)

    # The failed attempt requeued the task; the service retry restarts it.
    retried = env.service.retry(project_id, task_id, idempotency_key="retry-k")
    assert retried.ok is True
    assert retried.receipt is not None
    assert retried.receipt.command_kind == "core.task.retry"
    assert retried.data["task"]["status"] == "running"
    assert retried.data["attempt"]["status"] == "claimed"
    assert retried.data["prior_attempt_status"] == "failed"


def test_retry_ineligible_task_returns_typed_error(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    created = env.service.create(project_id=project_id, capability="cap.a", spec={"x": 1})
    # A never-claimed queued task is not retryable.
    result = env.service.retry(project_id, created.data["id"])
    assert result.ok is False
    assert result.error is not None
    assert result.error.code in ("terminal_state", "validation_error")


# ---------------------------------------------------------------------------
# Ordered events
# ---------------------------------------------------------------------------


def test_events_returns_ordered_stream_events(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    created = env.service.create(project_id=project_id, capability="cap.a", spec={"x": 1})
    task_id = created.data["id"]

    events = env.service.events(task_id)
    assert events.ok is True
    assert [event["kind"] for event in events.data] == ["core.task.created"]
    assert events.data[0]["stream_id"] == f"{task_id}:{CORE_TASK_STREAM_TYPE}"

    env.service.cancel(project_id, task_id)
    after = env.service.events(task_id)
    assert [event["kind"] for event in after.data] == [
        "core.task.created",
        "core.task.cancelled",
    ]
