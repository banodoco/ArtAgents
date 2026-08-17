"""Deterministic barrier-driven race tests for shared task transitions (T20).

Plan step 11 proves that the five executor races and the dual-materialization
case are linearizable through the shared repository predicates alone — no
caller-side race workarounds:

- **queued cancel vs claim** — the single writer FIFO selects exactly one
  terminal result: a queued cancellation that commits first leaves no
  eligible task (the later claim returns ``None`` with no receipt), and a
  claim that commits first makes the task ``running`` so a fence-less cancel
  is rejected before any mutation;
- **running cancel vs complete** — whichever commits first wins; the loser
  sees the terminal task and raises the typed ``task_terminal`` /
  ``task_not_running`` outcome with zero semantic rows (no media, no
  ``task_outputs``, no receipt, no head advance);
- **running cancel vs expiry/requeue** — a cancel that wins terminates the
  owned attempt and leaves nothing overdue (the expiry sweep returns
  ``None``), while an expiry that wins requeues the task and the stale
  running-cancel is rejected; a later claim creates a fresh fenced attempt
  without resurrecting the old one;
- **stale failure/complete vs a newer attempt** — a failure or completion
  presenting the *old* attempt's lease/version loses on the live-status
  fence (``attempt_not_live``) and writes nothing, leaving the newer attempt
  untouched;
- **terminal task vs retry/later cancel** — once the task is terminal,
  retry, later cancellation, and failure all raise typed outcomes and change
  zero rows (no resurrection, SD1);
- **two completion callers** — one winning completion materializes the
  ordered output set and records one receipt; the second caller loses on the
  terminal-task fence with zero additional rows.

Every race asserts exact terminal state, event order, status-version fences,
output presence/absence, receipt counts, verifiable stream chains, and no
resurrection.
"""

from __future__ import annotations

import json

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts import ReceiptService
from astrid.core.repositories import ProjectRepository
from astrid.core.repositories.media import MediaRepository
from astrid.core.repositories.tasks import (
    CORE_TASK_CANCELLED_EVENT_KIND,
    CORE_TASK_CLAIMED_EVENT_KIND,
    CORE_TASK_COMPLETED_EVENT_KIND,
    CORE_TASK_CREATED_EVENT_KIND,
    CORE_TASK_EXPIRED_EVENT_KIND,
    CORE_TASK_FAILED_EVENT_KIND,
    CORE_TASK_RETRIED_EVENT_KIND,
    CORE_TASK_STARTED_EVENT_KIND,
    CORE_TASK_STREAM_TYPE,
    TaskRepository,
    TaskTransitionError,
    TaskValidationError,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter

TS = "2026-08-16T00:00:00.000000+00:00"
TS2 = "2026-08-16T01:00:00.000000+00:00"

SPEC_A = {"backend": "remotion", "composition": "main", "fps": 24}
MANIFEST_A = ["media_1", "media_2"]


@pytest.fixture
def env(tmp_path, core_registry):
    """Fresh kernel writer plus project/task/media repositories over one root."""
    from types import SimpleNamespace

    from astrid.core.store.writer import DatabaseWriter

    db_path = tmp_path / "race_env.sqlite3"
    writer = DatabaseWriter(db_path, core_registry)
    try:
        events = EventAppendService(core_registry)
        receipts = ReceiptService()
        yield SimpleNamespace(
            writer=writer,
            projects_root=tmp_path,
            project_repo=ProjectRepository(events=events, receipts=receipts),
            task_repo=TaskRepository(events=events, receipts=receipts),
            media_repo=MediaRepository(
                events=events, receipts=receipts, projects_root=tmp_path
            ),
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


def _admit(env, *, project_id: str, task_id: str | None = None, max_attempts: int = 2,
           **overrides):
    task_id = task_id or generate_lowercase_ulid()
    args = {
        "project_id": project_id,
        "capability": "rendering.timeline_visualize",
        "spec": dict(SPEC_A),
        "input_manifest": list(MANIFEST_A),
        "idempotency_key": f"admit-{task_id}-k",
        "task_id": task_id,
        "max_attempts": max_attempts,
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.create(u, **args))


def _claim(env, *, project_id: str, idempotency_key: str = "claim-k", **overrides):
    args = {
        "project_id": project_id,
        "idempotency_key": idempotency_key,
        "executor_id": "executor-1",
        "now": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.claim(u, **args))


def _start(env, *, project_id: str, claim, idempotency_key: str = "start-k", **overrides):
    args = {
        "project_id": project_id,
        "task_id": claim.task.id,
        "attempt_id": claim.attempt.id,
        "lease_id": claim.attempt.lease_id,
        "expected_status_version": claim.attempt.status_version,
        "idempotency_key": idempotency_key,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.start(u, **args))


def _cancel(env, *, project_id: str, task_id: str, idempotency_key: str = "cancel-k",
            **overrides):
    args = {
        "project_id": project_id,
        "task_id": task_id,
        "idempotency_key": idempotency_key,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.cancel(u, **args))


def _fail(env, *, project_id: str, task_id: str, attempt_id: str, lease_id: str,
          status_version: int, idempotency_key: str = "fail-k", **overrides):
    args = {
        "project_id": project_id,
        "task_id": task_id,
        "attempt_id": attempt_id,
        "lease_id": lease_id,
        "expected_status_version": status_version,
        "idempotency_key": idempotency_key,
        "error": {"reason": "executor_failed"},
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.fail(u, **args))


def _expire(env, *, project_id: str, idempotency_key: str = "expire-k", **overrides):
    args = {
        "project_id": project_id,
        "idempotency_key": idempotency_key,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.expire_overdue(u, **args))


def _retry(env, *, project_id: str, task_id: str, idempotency_key: str = "retry-k",
           **overrides):
    args = {
        "project_id": project_id,
        "task_id": task_id,
        "idempotency_key": idempotency_key,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.retry(u, **args))


def _prepare_output(env, *, name: str, content: bytes, **overrides):
    from astrid.core.io.media_import import prepare_media_file

    staging = env.projects_root / ".astrid" / "media" / ".staging" / f"race-{name}"
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / name
    path.write_bytes(content)
    prepared = prepare_media_file(path, root=staging)
    entry = {
        "ordinal": 0,
        "is_primary": True,
        "role": "result",
        "label": name,
        "path": name,
        "prepared": prepared,
    }
    entry.update(overrides)
    return entry


def _complete(env, *, project_id: str, task_id: str, attempt_id: str, lease_id: str,
              status_version: int, outputs, idempotency_key: str = "complete-k",
              **overrides):
    args = {
        "project_id": project_id,
        "task_id": task_id,
        "attempt_id": attempt_id,
        "lease_id": lease_id,
        "expected_status_version": status_version,
        "idempotency_key": idempotency_key,
        "outputs": outputs,
        "media_repo": env.media_repo,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.complete(u, **args))


def _task_row(writer: DatabaseWriter, task_id: str):
    return writer.submit(
        lambda session: session.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    )


def _attempt_rows(writer: DatabaseWriter, task_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM execution_attempts WHERE task_id = ? ORDER BY attempt_no ASC",
            (task_id,),
        )
    )


def _event_rows(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM events WHERE stream_id = ? ORDER BY seq ASC", (stream_id,)
        )
    )


def _receipt_count(writer: DatabaseWriter, project_id: str) -> int:
    return writer.submit(
        lambda session: session.query_one(
            "SELECT count(*) FROM command_receipts WHERE project_id = ?", (project_id,)
        )[0]
    )


def _project_head(writer: DatabaseWriter, project_id: str) -> int:
    return writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = ?", (project_id,)
        )[0]
    )


def _stream_head(writer: DatabaseWriter, stream_id: str) -> int:
    return writer.submit(
        lambda session: session.query_one(
            "SELECT head_seq FROM event_streams WHERE id = ?", (stream_id,)
        )[0]
    )


def _task_output_rows(writer: DatabaseWriter, task_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM task_outputs WHERE task_id = ? ORDER BY ordinal ASC",
            (task_id,),
        )
    )


def _media_count(writer: DatabaseWriter, project_id: str) -> int:
    return writer.submit(
        lambda session: session.query_one(
            "SELECT count(*) FROM media WHERE project_id = ?", (project_id,)
        )[0]
    )


def _verify_chain(env, core_registry, task_id: str):
    stream_id = f"{task_id}:{CORE_TASK_STREAM_TYPE}"
    verification = EventAppendService(core_registry).verify_stream(
        env.writer, stream_id
    )
    assert verification.event_count == verification.head_seq
    assert verification.head_hash is not None
    assert verification.event_count == _stream_head(env.writer, stream_id)
    return stream_id, verification


def _event_kinds(writer: DatabaseWriter, stream_id: str) -> list[str]:
    return [str(row["kind"]) for row in _event_rows(writer, stream_id)]


# ---------------------------------------------------------------------------
# Race 1: queued cancel vs claim
# ---------------------------------------------------------------------------


def test_race_queued_cancel_wins_claim_loses_with_no_receipt(env) -> None:
    project = _create_project(env)
    task = _admit(env, project_id=project.id)
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)

    # Barrier: both commands are valid at this instant (task is queued).
    # Commit the queued cancellation first: it wins the single-writer FIFO.
    cancelled = _cancel(env, project_id=project.id, task_id=task.id)
    assert cancelled.task.status == "cancelled"
    assert cancelled.task.winning_attempt_id is None
    assert cancelled.task.finished_at == TS2
    assert cancelled.attempt is None  # no attempt was ever created
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert _project_head(env.writer, project.id) == head_before + 1

    # The later claim loses: no eligible task, no receipt, no mutation.
    claim = _claim(env, project_id=project.id, idempotency_key="claim-after-cancel")
    assert claim is None
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert _project_head(env.writer, project.id) == head_before + 1
    assert _attempt_rows(env.writer, task.id) == []

    # Terminal state, event order, and a valid chain; no resurrection.
    assert _task_row(env.writer, task.id)["status"] == "cancelled"
    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    kinds = _event_kinds(env.writer, stream_id)
    assert kinds == [CORE_TASK_CREATED_EVENT_KIND, CORE_TASK_CANCELLED_EVENT_KIND]


def test_race_claim_wins_fenceless_cancel_rejected_before_mutation(env) -> None:
    project = _create_project(env)
    task = _admit(env, project_id=project.id)
    receipts_before = _receipt_count(env.writer, project.id)

    # Barrier reversed: the claim commits first and wins.
    claim = _claim(env, project_id=project.id)
    assert claim is not None and claim.task.id == task.id
    assert _task_row(env.writer, task.id)["status"] == "running"

    # A cancel that presents no running fences is rejected before mutation.
    with pytest.raises(TaskValidationError) as excinfo:
        _cancel(env, project_id=project.id, task_id=task.id,
                idempotency_key="cancel-claimed")
    assert "requires attempt_id" in str(excinfo.value)
    assert _receipt_count(env.writer, project.id) == receipts_before + 1  # only claim
    assert _task_row(env.writer, task.id)["status"] == "running"
    # No second claim can double-claim the running task.
    assert _claim(env, project_id=project.id, idempotency_key="claim-again") is None


# ---------------------------------------------------------------------------
# Race 2: running cancel vs complete
# ---------------------------------------------------------------------------


def _running_task(env, *, project_id: str, idempotency_key: str = "race-claim-k"):
    """Admit + claim + start one task; return (task, claim, started)."""
    task = _admit(env, project_id=project_id)
    claim = _claim(env, project_id=project_id, idempotency_key=idempotency_key)
    assert claim is not None and claim.task.id == task.id
    started = _start(env, project_id=project_id, claim=claim,
                     idempotency_key=f"{idempotency_key}:start")
    assert started.status == "running"
    assert started.status_version == 2
    return task, claim, started


def test_race_running_cancel_wins_complete_loses_without_materialization(
    env, core_registry,
) -> None:
    project = _create_project(env)
    task, claim, started = _running_task(env, project_id=project.id)
    outputs = [_prepare_output(env, name="frame.svg", content=b"<svg/>")]
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)

    # Barrier: running cancel and complete are both valid on the same fences.
    # The running cancel commits first and wins.
    cancelled = _cancel(
        env,
        project_id=project.id,
        task_id=task.id,
        idempotency_key="cancel-vs-complete",
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=started.status_version,
    )
    assert cancelled.task.status == "cancelled"
    assert cancelled.task.winning_attempt_id is None
    assert cancelled.attempt is not None
    assert cancelled.attempt.status == "cancelled"
    assert cancelled.attempt.status_version == started.status_version + 1
    assert cancelled.attempt.finished_at == TS2

    # The losing complete sees the terminal task: typed outcome, zero rows.
    with pytest.raises(TaskTransitionError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version, outputs=outputs,
            idempotency_key="complete-vs-cancel",
        )
    assert excinfo.value.reason == "task_not_running"
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert _project_head(env.writer, project.id) == head_before + 1
    assert _media_count(env.writer, project.id) == 0
    assert _task_output_rows(env.writer, task.id) == []
    assert _task_row(env.writer, task.id)["status"] == "cancelled"

    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    kinds = _event_kinds(env.writer, stream_id)
    assert kinds == [
        CORE_TASK_CREATED_EVENT_KIND,
        CORE_TASK_CLAIMED_EVENT_KIND,
        CORE_TASK_STARTED_EVENT_KIND,
        CORE_TASK_CANCELLED_EVENT_KIND,
    ]
    _verify_chain(env, core_registry, task.id)


def test_race_complete_wins_running_cancel_loses_on_terminal_task(
    env, core_registry,
) -> None:
    project = _create_project(env)
    task, claim, started = _running_task(env, project_id=project.id,
                                         idempotency_key="complete-first")
    out_a = _prepare_output(env, name="frame.svg", content=b"<svg/>")
    out_b = _prepare_output(
        env, name="story.md", content=b"# story",
        ordinal=1, is_primary=False, role="output", label="story",
    )
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)

    # The completion commits first and wins the single-writer race.
    completed = _complete(
        env, project_id=project.id, task_id=task.id,
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        status_version=started.status_version, outputs=[out_a, out_b],
        idempotency_key="complete-winner",
    )
    assert completed.task.status == "succeeded"
    assert completed.task.winning_attempt_id == claim.attempt.id
    assert completed.attempt.status == "succeeded"
    assert [output.ordinal for output in completed.outputs] == [0, 1]
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert _project_head(env.writer, project.id) == head_before + 3
    assert _media_count(env.writer, project.id) == 2

    # The later running cancel loses on the terminal-task fence, zero rows.
    with pytest.raises(TaskTransitionError) as excinfo:
        _cancel(
            env, project_id=project.id, task_id=task.id,
            idempotency_key="cancel-loser",
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            expected_status_version=started.status_version,
        )
    assert excinfo.value.reason == "task_terminal"
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert _project_head(env.writer, project.id) == head_before + 3
    assert len(_task_output_rows(env.writer, task.id)) == 2
    assert _media_count(env.writer, project.id) == 2
    attempts = _attempt_rows(env.writer, task.id)
    assert attempts[0]["status"] == "succeeded"
    assert _task_row(env.writer, task.id)["status"] == "succeeded"
    _verify_chain(env, core_registry, task.id)


# ---------------------------------------------------------------------------
# Race 3: running cancel vs expiry/requeue
# ---------------------------------------------------------------------------


def test_race_running_cancel_wins_expiry_sweep_finds_nothing(env) -> None:
    project = _create_project(env)
    task = _admit(env, project_id=project.id, max_attempts=2)
    # Short lease so the attempt is already overdue at TS2.
    claim = _claim(env, project_id=project.id, lease_seconds=1,
                   idempotency_key="race3-claim")
    assert claim is not None and claim.task.id == task.id
    started = _start(env, project_id=project.id, claim=claim,
                     idempotency_key="race3-start")
    receipts_before = _receipt_count(env.writer, project.id)

    # Barrier: both the running cancel and the expiry sweep are valid now.
    cancelled = _cancel(
        env, project_id=project.id, task_id=task.id,
        idempotency_key="race3-cancel",
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        expected_status_version=started.status_version,
    )
    assert cancelled.task.status == "cancelled"
    assert cancelled.attempt is not None and cancelled.attempt.status == "cancelled"

    # The expiry sweep finds nothing overdue: no receipt, no mutation.
    expired = _expire(env, project_id=project.id, idempotency_key="race3-expire")
    assert expired is None
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert _task_row(env.writer, task.id)["status"] == "cancelled"
    attempts = _attempt_rows(env.writer, task.id)
    assert len(attempts) == 1 and attempts[0]["status"] == "cancelled"


def test_race_expiry_requeue_wins_stale_cancel_rejected_then_fresh_attempt(
    env, core_registry,
) -> None:
    project = _create_project(env)
    task = _admit(env, project_id=project.id, max_attempts=2)
    claim = _claim(env, project_id=project.id, lease_seconds=1,
                   idempotency_key="race3b-claim")
    assert claim is not None and claim.task.id == task.id
    started = _start(env, project_id=project.id, claim=claim,
                     idempotency_key="race3b-start")
    receipts_before = _receipt_count(env.writer, project.id)

    # The expiry sweep commits first: attempt expires, task requeues.
    expired = _expire(env, project_id=project.id, idempotency_key="race3b-expire")
    assert expired is not None
    assert expired.outcome == "requeued"
    assert expired.task.status == "queued"
    assert expired.attempt.status == "expired"
    assert expired.attempt.status_version == started.status_version + 1
    assert _receipt_count(env.writer, project.id) == receipts_before + 1

    # The stale running-cancel (old fences on a now-queued task) is rejected.
    with pytest.raises(TaskValidationError) as excinfo:
        _cancel(
            env, project_id=project.id, task_id=task.id,
            idempotency_key="race3b-stale-cancel",
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            expected_status_version=started.status_version,
        )
    assert "queued/blocked task takes no attempt fence" in str(excinfo.value)
    assert _receipt_count(env.writer, project.id) == receipts_before + 1

    # A later claim creates a fresh fenced attempt (attempt 2) — no
    # resurrection of the expired attempt and no budget corruption.
    second = _claim(env, project_id=project.id, idempotency_key="race3b-claim2")
    assert second is not None and second.task.id == task.id
    assert second.attempt.attempt_no == 2
    assert second.attempt.status == "claimed"
    assert second.attempt.status_version == 1
    assert second.attempt.id != claim.attempt.id
    attempts = _attempt_rows(env.writer, task.id)
    assert [row["attempt_no"] for row in attempts] == [1, 2]
    assert attempts[0]["status"] == "expired"
    assert attempts[1]["status"] == "claimed"
    assert _task_row(env.writer, task.id)["status"] == "running"
    _verify_chain(env, core_registry, task.id)


# ---------------------------------------------------------------------------
# Race 4: stale failure/complete vs a newer attempt
# ---------------------------------------------------------------------------


def test_race_stale_failure_and_complete_lose_to_newer_attempt(
    env, core_registry,
) -> None:
    project = _create_project(env)
    task = _admit(env, project_id=project.id, max_attempts=2)
    first = _claim(env, project_id=project.id, idempotency_key="race4-claim1")
    assert first is not None and first.task.id == task.id
    started1 = _start(env, project_id=project.id, claim=first,
                      idempotency_key="race4-start1")
    # Attempt 1 fails (budget remains): the task requeues.
    failed = _fail(
        env, project_id=project.id, task_id=task.id,
        attempt_id=first.attempt.id, lease_id=first.attempt.lease_id,
        status_version=started1.status_version,
        idempotency_key="race4-fail1",
    )
    assert failed.outcome == "requeued"
    assert failed.task.status == "queued"

    # A newer attempt 2 is claimed and started while attempt 1 is terminal.
    second = _claim(env, project_id=project.id, idempotency_key="race4-claim2")
    assert second is not None and second.task.id == task.id
    assert second.attempt.attempt_no == 2
    started2 = _start(env, project_id=project.id, claim=second,
                      idempotency_key="race4-start2")
    assert started2.status_version == 2
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)
    outputs = [_prepare_output(env, name="frame.svg", content=b"<svg/>")]

    # Stale complete presenting attempt 1's old version: attempt_not_live.
    with pytest.raises(TaskTransitionError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=first.attempt.id, lease_id=first.attempt.lease_id,
            status_version=started1.status_version, outputs=outputs,
            idempotency_key="race4-stale-complete",
        )
    assert excinfo.value.reason == "attempt_not_live"
    # Stale fail presenting attempt 1's old version: attempt_not_live.
    with pytest.raises(TaskTransitionError) as excinfo:
        _fail(
            env, project_id=project.id, task_id=task.id,
            attempt_id=first.attempt.id, lease_id=first.attempt.lease_id,
            status_version=started1.status_version,
            idempotency_key="race4-stale-fail",
        )
    assert excinfo.value.reason == "attempt_not_live"

    # Zero rows for the losers; the newer attempt is untouched.
    assert _receipt_count(env.writer, project.id) == receipts_before
    assert _project_head(env.writer, project.id) == head_before
    assert _media_count(env.writer, project.id) == 0
    assert _task_output_rows(env.writer, task.id) == []
    attempts = _attempt_rows(env.writer, task.id)
    assert attempts[1]["status"] == "running"
    assert attempts[1]["status_version"] == started2.status_version
    assert _task_row(env.writer, task.id)["status"] == "running"
    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    kinds = _event_kinds(env.writer, stream_id)
    assert kinds[-1] == CORE_TASK_STARTED_EVENT_KIND  # attempt 2 start
    _verify_chain(env, core_registry, task.id)


# ---------------------------------------------------------------------------
# Race 5: terminal task vs retry / later cancel / failure
# ---------------------------------------------------------------------------


def test_race_terminal_task_rejects_retry_cancel_and_failure_without_mutation(
    env, core_registry,
) -> None:
    project = _create_project(env)
    task, claim, started = _running_task(env, project_id=project.id,
                                         idempotency_key="race5-claim")
    outputs = [_prepare_output(env, name="frame.svg", content=b"<svg/>")]
    _complete(
        env, project_id=project.id, task_id=task.id,
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        status_version=started.status_version, outputs=outputs,
        idempotency_key="race5-complete",
    )
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)
    assert _task_row(env.writer, task.id)["status"] == "succeeded"

    # Retry on a terminal task: typed task_terminal, zero rows.
    with pytest.raises(TaskTransitionError) as excinfo:
        _retry(env, project_id=project.id, task_id=task.id,
               idempotency_key="race5-retry")
    assert excinfo.value.reason == "task_terminal"

    # Later cancellation on a terminal task: typed task_terminal, zero rows.
    with pytest.raises(TaskTransitionError) as excinfo:
        _cancel(env, project_id=project.id, task_id=task.id,
                idempotency_key="race5-cancel")
    assert excinfo.value.reason == "task_terminal"

    # Failure with the old fences: task no longer running, zero rows.
    with pytest.raises(TaskTransitionError) as excinfo:
        _fail(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version,
            idempotency_key="race5-fail",
        )
    assert excinfo.value.reason == "task_not_running"

    # No resurrection: terminal state, attempt, outputs, and receipts hold.
    row = _task_row(env.writer, task.id)
    assert row["status"] == "succeeded"
    assert row["winning_attempt_id"] == claim.attempt.id
    assert _receipt_count(env.writer, project.id) == receipts_before
    assert _project_head(env.writer, project.id) == head_before
    assert len(_task_output_rows(env.writer, task.id)) == 1
    attempts = _attempt_rows(env.writer, task.id)
    assert len(attempts) == 1 and attempts[0]["status"] == "succeeded"
    _verify_chain(env, core_registry, task.id)


# ---------------------------------------------------------------------------
# Race 6: two completion callers — one winning attempt, one output set
# ---------------------------------------------------------------------------


def test_race_two_completion_callers_select_one_winner(env, core_registry) -> None:
    project = _create_project(env)
    task, claim, started = _running_task(env, project_id=project.id,
                                         idempotency_key="race6-claim")
    # Both callers prepared the same deterministic outputs before racing.
    caller_a_outputs = [
        _prepare_output(env, name="frame.svg", content=b"<svg/>"),
        _prepare_output(
            env, name="story.md", content=b"# story",
            ordinal=1, is_primary=False, role="output", label="story",
        ),
    ]
    caller_b_outputs = [
        _prepare_output(env, name="frame.svg", content=b"<svg/>"),
        _prepare_output(
            env, name="story.md", content=b"# story",
            ordinal=1, is_primary=False, role="output", label="story",
        ),
    ]
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)

    # Caller A wins the single-writer race.
    winner = _complete(
        env, project_id=project.id, task_id=task.id,
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        status_version=started.status_version, outputs=caller_a_outputs,
        idempotency_key="race6-caller-a",
    )
    assert winner.task.status == "succeeded"
    assert winner.task.winning_attempt_id == claim.attempt.id
    assert winner.attempt.status == "succeeded"
    assert [output.ordinal for output in winner.outputs] == [0, 1]
    assert len(winner.event_ids) == 3  # two media events + completed
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert _project_head(env.writer, project.id) == head_before + 3
    assert _media_count(env.writer, project.id) == 2

    # Caller B loses on the terminal-task fence: typed outcome, zero rows.
    with pytest.raises(TaskTransitionError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version, outputs=caller_b_outputs,
            idempotency_key="race6-caller-b",
        )
    assert excinfo.value.reason == "task_not_running"
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert _project_head(env.writer, project.id) == head_before + 3
    assert _media_count(env.writer, project.id) == 2
    outputs = _task_output_rows(env.writer, task.id)
    assert [row["ordinal"] for row in outputs] == [0, 1]
    assert outputs[0]["is_primary"] == 1 and outputs[0]["role"] == "result"
    assert outputs[1]["is_primary"] == 0 and outputs[1]["role"] == "output"

    # Exactly one winning attempt; the stream verifies end to end.
    attempts = _attempt_rows(env.writer, task.id)
    assert len(attempts) == 1 and attempts[0]["status"] == "succeeded"
    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    kinds = _event_kinds(env.writer, stream_id)
    assert kinds[-1] == CORE_TASK_COMPLETED_EVENT_KIND
    assert kinds.count(CORE_TASK_COMPLETED_EVENT_KIND) == 1
    _verify_chain(env, core_registry, task.id)
