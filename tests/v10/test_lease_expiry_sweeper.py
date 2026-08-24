"""Serve-owned lease expiry recovery tests."""

from __future__ import annotations

import time

from astrid.core.ids import generate_lowercase_ulid
from astrid.core.store.uow import UnitOfWork
from astrid.packs import LeaseExpirySweeper


def test_sweeper_requeues_expired_attempt_and_allows_reclaim(task_env) -> None:
    project = UnitOfWork(task_env.writer).run(
        lambda u: task_env.project_repo.create(
            u,
            slug="sweeper-project",
            name="Sweeper Project",
            settings={},
            idempotency_key="sweeper-project-create",
            project_id=generate_lowercase_ulid(),
            created_at="2026-08-16T00:00:00Z",
        )
    )
    task = UnitOfWork(task_env.writer).run(
        lambda u: task_env.task_repo.create(
            u,
            project_id=project.id,
            capability="reigh.image_upscale",
            spec={"schema_version": 1, "family": "image_upscale"},
            input_manifest=[],
            idempotency_key="sweeper-task-create",
            task_id=generate_lowercase_ulid(),
            max_attempts=2,
            created_at="2026-08-16T00:00:00Z",
        )
    )
    first = UnitOfWork(task_env.writer).run(
        lambda u: task_env.task_repo.claim(
            u,
            project_id=project.id,
            idempotency_key="sweeper-claim-one",
            executor_id="executor-one",
            lease_seconds=60,
            now="2026-08-16T00:00:00Z",
        )
    )
    assert first is not None

    sweeper = LeaseExpirySweeper(
        task_env.writer, task_env.task_repo, interval_seconds=0.02
    )
    try:
        deadline = time.monotonic() + 5
        status = ""
        while time.monotonic() < deadline:
            row = task_env.writer.submit(
                lambda session: session.query_one(
                    "SELECT status FROM tasks WHERE id = ?", (task.id,)
                )
            )
            status = str(row[0])
            if status == "queued":
                break
            time.sleep(0.02)
        assert status == "queued"
    finally:
        sweeper.stop()

    second = UnitOfWork(task_env.writer).run(
        lambda u: task_env.task_repo.claim(
            u,
            project_id=project.id,
            idempotency_key="sweeper-claim-two",
            executor_id="executor-two",
            lease_seconds=60,
            now="2026-08-24T00:00:00Z",
        )
    )
    assert second is not None
    assert second.task.id == task.id
    assert second.attempt.attempt_no == 2
