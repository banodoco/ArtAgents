"""Lease-expiry sweeper tests (BC3 ops-lens gap 1).

Proves the serve-boot sweeper closes the crashed-executor wedge: an executor
that dies mid-attempt (claim committed, then no heartbeat and no completion)
would otherwise stay live forever — heartbeat rejects the expired lease
without transitioning it, and retry predicates require a prior expired
attempt. One sweep of :class:`astrid.packs.LeaseExpirySweeper` expires the
orphan attempt through the receipt-protected ``core.task.expire`` command,
the budget-driven requeue puts the task back to ``queued``, and the next
claim succeeds with a fresh fenced attempt.
"""

from __future__ import annotations

import time

from astrid.core.ids import generate_lowercase_ulid
from astrid.core.store.uow import UnitOfWork
from astrid.packs import LeaseExpirySweeper

TS = "2026-08-16T00:00:00.000000+00:00"
TS2 = "2026-08-16T01:00:00.000000+00:00"

_SPEC = {"backend": "remotion", "composition": "main", "fps": 24}


def _create_project(env, *, slug: str = "sweep"):
    return UnitOfWork(env.writer).run(
        lambda u: env.project_repo.create(
            u,
            slug=slug,
            name=slug.title(),
            settings={"fps": 24},
            idempotency_key=f"create-{slug}-k",
            project_id=generate_lowercase_ulid(),
            created_at=TS,
        )
    )


def _admit(env, *, project_id: str, max_attempts: int):
    task_id = generate_lowercase_ulid()
    return UnitOfWork(env.writer).run(
        lambda u: env.task_repo.create(
            u,
            project_id=project_id,
            capability="rendering.timeline_visualize",
            spec=dict(_SPEC),
            input_manifest=["media_1"],
            idempotency_key=f"admit-{task_id}-k",
            task_id=task_id,
            max_attempts=max_attempts,
            created_at=TS,
        )
    )


def _claim(env, *, project_id: str, lease_seconds: int, now: str, key: str):
    return UnitOfWork(env.writer).run(
        lambda u: env.task_repo.claim(
            u,
            project_id=project_id,
            idempotency_key=key,
            executor_id="executor-1",
            lease_seconds=lease_seconds,
            now=now,
        )
    )


def _task_status(env, task_id: str) -> str:
    row = env.writer.submit(
        lambda session: session.query_one(
            "SELECT status FROM tasks WHERE id = ?", (task_id,)
        )
    )
    assert row is not None
    return str(row["status"])


def test_sweeper_expires_crashed_attempt_and_requeue_allows_claim(task_env) -> None:
    project = _create_project(task_env)
    task = _admit(task_env, project_id=project.id, max_attempts=2)
    # The "executor" claims and then crashes: no start, no heartbeat, no
    # completion. The lease is stamped in the past, so wall-clock time has
    # already advanced past its expiry when the sweeper ticks.
    claim = _claim(
        task_env,
        project_id=project.id,
        lease_seconds=60,
        now=TS,
        key="sweep-claim-crashed",
    )
    assert claim is not None
    assert _task_status(task_env, task.id) == "running"

    sweeper = LeaseExpirySweeper(
        task_env.writer, task_env.task_repo, interval_seconds=0.05
    )
    try:
        deadline = time.monotonic() + 10.0
        status = ""
        while time.monotonic() < deadline:
            status = _task_status(task_env, task.id)
            if status == "queued":
                break
            time.sleep(0.05)
        assert status == "queued"
    finally:
        sweeper.stop()

    # The requeued task is claimable again: the next claim succeeds with a
    # fresh fenced attempt (attempt_no 2), proving the wedge is closed.
    second = _claim(
        task_env,
        project_id=project.id,
        lease_seconds=60,
        now=TS2,
        key="sweep-claim-after-sweep",
    )
    assert second is not None
    assert second.task.id == task.id
    assert second.attempt.attempt_no == 2


def test_writer_close_joins_sweeper_before_database_teardown(task_env) -> None:
    """Closing a shared writer must not leave a daemon probing its DB."""
    sweeper = LeaseExpirySweeper(
        task_env.writer, task_env.task_repo, interval_seconds=60
    )
    task_env.writer.close()
    assert not sweeper._thread.is_alive()
