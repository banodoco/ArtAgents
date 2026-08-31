"""End-to-end multi-task journey across initial and continuation chunks (T3).

Plan step 2 + step 13's interaction, proven as one journey (m3 plan step 4,
task T3): an initial fan-out chunk and a continuation chunk share one run,
with hard and soft dependencies, claims, starts, successes, and failures
driven through the shared task repository predicates, and derived run
progress/status read through the single shared derivation
(``derive_run_progress_counts`` in the task repository, exposed by
``RunRepository.derive_progress`` and recomputed by the completion, group
cancel, and group retry paths).

The journey asserts, in order:

- **Hard/soft gating.** A hard-dependent child starts ``blocked`` and is
  only unblocked when its dependency reaches the terminal ``succeeded``
  state (the completing command's ``_unblock_eligible_dependents``); a
  soft-dependent child starts ``queued`` and never blocks.
- **Stable ordinal progress.** Children of both chunks carry stable
  contiguous ``run_ordinal`` values ``0..6``; the continuation allocates
  exactly the next free ordinals under an expected-head CAS.
- **Derived running and failed states.** ``derive_progress`` is a pure read
  over the child task rows: it reports the exact ordered ``(ordinal,
  task_id, status)`` tuples and the derived run status at every phase,
  without any persisted cursor or mutable progress aggregate.
- **Selective retry.** ``RunRepository.retry(selected_task_ids=...)``
  restarts exactly the selected failed work with a brand-new fenced
  attempt; unselected children are untouched.
- **Cooperative running-child cancellation + eligible group cancel.** A
  group cancel drives every eligible queued/blocked/running child to
  terminal ``cancelled`` with one shared ``cancel_request_id``. Running
  children do not expose executor-private fences; already-terminal children
  are skipped untouched.
- **Stale-attempt fencing.** A fail or complete presenting the *old*
  attempt's lease/version loses on the live-status fence
  (``attempt_not_live``) with zero rows, media, outputs, or receipts,
  leaving the newer attempt the winner.
- **Terminal immutability.** Once every child is terminal the derived run
  status is persisted (``failed`` here, any failed child winning), and
  continuation/group cancel reject the terminal run before any mutation.
  A failed invocation run may enter its deliberate one-shot retry path, but
  a selected terminal child still fails through the shared task fence.
- **No plan/step record or cursor.** The journey creates no parent task,
  no step/plan table, no progress-cursor table, and no evidence rows; the
  only persisted progress is the derived projection in ``runs.result_json``
  (recomputed by the shared derivation), which equals a fresh
  ``derive_progress`` read at the end.

Only the shared run/task projection logic exposed by the journey is
touched; no new schema, command, or event vocabulary is introduced.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.ids import generate_lowercase_ulid
from astrid.core.migrations.catalog import FORBIDDEN_TABLES
from astrid.core.receipts import ReceiptMismatchError
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
    RunCancelReadModel,
    RunContinuationReadModel,
    RunProgressReadModel,
    RunRepository,
    RunRetryReadModel,
    RunStaleHeadError,
    RunTerminalError,
    RunValidationError,
)
from astrid.core.repositories.tasks import (
    CORE_TASK_CANCEL_COMMAND_KIND,
    CORE_TASK_CANCELLED_EVENT_KIND,
    CORE_TASK_RETRY_COMMAND_KIND,
    CORE_TASK_RETRIED_EVENT_KIND,
    TaskRepository,
    TaskTransitionError,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter

TS = "2026-08-17T00:00:00.000000+00:00"
TS2 = "2026-08-17T01:00:00.000000+00:00"

SPEC_A = {"backend": "remotion", "composition": "main", "fps": 24}
MANIFEST_A = ["media_1"]


@pytest.fixture
def journey_env(tmp_path, core_registry):
    """Fresh kernel writer plus project, run, task, and media repositories."""
    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.media import MediaRepository
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.core.store.writer import DatabaseWriter

    db_path = tmp_path / "journey_env.sqlite3"
    writer = DatabaseWriter(db_path, core_registry)
    try:
        events = EventAppendService(core_registry)
        receipts = ReceiptService()
        yield SimpleNamespace(
            writer=writer,
            projects_root=tmp_path,
            project_repo=ProjectRepository(events=events, receipts=receipts),
            run_repo=RunRepository(events=events, receipts=receipts),
            task_repo=TaskRepository(events=events, receipts=receipts),
            media_repo=MediaRepository(
                events=events, receipts=receipts, projects_root=tmp_path
            ),
        )
    finally:
        writer.close()


def _create_project(env, *, slug: str = "journey"):
    args = {
        "slug": slug,
        "name": slug.title(),
        "settings": {"fps": 24},
        "idempotency_key": f"create-{slug}-k",
        "project_id": generate_lowercase_ulid(),
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
        "input_manifest": (
            input_manifest if input_manifest is not None else list(MANIFEST_A)
        ),
    }
    if task_id is not None:
        entry["task_id"] = task_id
    if dependencies is not None:
        entry["dependencies"] = dependencies
    entry.update(overrides)
    return entry


def _fanout(env, *, project_id: str, children, idempotency_key: str, **overrides):
    args = {
        "project_id": project_id,
        "children": children,
        "idempotency_key": idempotency_key,
        "run_id": generate_lowercase_ulid(),
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.run_repo.create(u, **args))


def _continue_run(
    env,
    *,
    project_id: str,
    run_id: str,
    expected_version: int,
    start_ordinal: int,
    children,
    idempotency_key: str,
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


def _claim(env, *, project_id: str, idempotency_key: str, now: str = TS):
    return UnitOfWork(env.writer).run(
        lambda u: env.task_repo.claim(
            u,
            project_id=project_id,
            idempotency_key=idempotency_key,
            executor_id="executor-journey",
            now=now,
        )
    )


def _start(env, *, project_id: str, claim, idempotency_key: str, now: str = TS):
    return UnitOfWork(env.writer).run(
        lambda u: env.task_repo.start(
            u,
            project_id=project_id,
            task_id=claim.task.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=claim.attempt.status_version,
            idempotency_key=idempotency_key,
            now=now,
        )
    )


def _fail(
    env,
    *,
    project_id: str,
    task_id: str,
    attempt_id: str,
    lease_id: str,
    status_version: int,
    idempotency_key: str,
    now: str = TS2,
):
    return UnitOfWork(env.writer).run(
        lambda u: env.task_repo.fail(
            u,
            project_id=project_id,
            task_id=task_id,
            attempt_id=attempt_id,
            lease_id=lease_id,
            expected_status_version=status_version,
            idempotency_key=idempotency_key,
            now=now,
            error={"kind": "journey.fixture", "message": "intentional failure"},
        )
    )


def _prepare_output(env, *, name: str, content: bytes):
    """One prepared primary output entry for a fenced completion."""
    from astrid.core.io.media_import import prepare_media_file

    staging = env.projects_root / ".astrid" / "media" / ".staging" / f"journey-{name}"
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / name
    path.write_bytes(content)
    prepared = prepare_media_file(path, root=staging)
    return {
        "ordinal": 0,
        "is_primary": True,
        "role": "result",
        "label": name,
        "path": name,
        "prepared": prepared,
    }


def _complete(
    env,
    *,
    project_id: str,
    task_id: str,
    attempt_id: str,
    lease_id: str,
    status_version: int,
    outputs,
    idempotency_key: str,
    now: str = TS2,
):
    return UnitOfWork(env.writer).run(
        lambda u: env.task_repo.complete(
            u,
            project_id=project_id,
            task_id=task_id,
            attempt_id=attempt_id,
            lease_id=lease_id,
            expected_status_version=status_version,
            idempotency_key=idempotency_key,
            outputs=outputs,
            media_repo=env.media_repo,
            now=now,
        )
    )


def _group_cancel(
    env, *, project_id: str, run_id: str, idempotency_key: str, **overrides
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
    env, *, project_id: str, run_id: str, idempotency_key: str, **overrides
):
    args = {
        "project_id": project_id,
        "run_id": run_id,
        "idempotency_key": idempotency_key,
        "now": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.run_repo.retry(u, **args))


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
def _task_rows(writer: DatabaseWriter, run_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT id, run_ordinal, status FROM tasks "
            "WHERE run_id = ? ORDER BY run_ordinal ASC",
            (run_id,),
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


def _event_rows(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM events WHERE stream_id = ? ORDER BY seq ASC",
            (stream_id,),
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


def _run_stream_head(writer: DatabaseWriter, run_id: str) -> int:
    return int(
        writer.submit(
            lambda session: session.query_one(
                "SELECT head_seq FROM event_streams WHERE id = ?",
                (f"{run_id}:{CORE_RUN_STREAM_TYPE}",),
            )
        )["head_seq"]
    )


def _derive(env, *, project_id: str, run_id: str) -> RunProgressReadModel:
    return UnitOfWork(env.writer).run(
        lambda u: env.run_repo.derive_progress(
            u, project_id=project_id, run_id=run_id
        )
    )


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


def _tables(writer: DatabaseWriter) -> set[str]:
    return writer.submit(
        lambda session: {
            str(row["name"])
            for row in session.query(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    )


def test_multi_task_journey_spans_chunks_and_derives_run_state(journey_env) -> None:
    env = journey_env
    project = _create_project(env)
    t0 = generate_lowercase_ulid()
    t1 = generate_lowercase_ulid()
    t2 = generate_lowercase_ulid()
    t3 = generate_lowercase_ulid()
    t4 = generate_lowercase_ulid()
    t5 = generate_lowercase_ulid()
    t6 = generate_lowercase_ulid()

    # ------------------------------------------------------------------
    # Phase A — initial chunk: successes, soft failure, requeue, gating.
    # ------------------------------------------------------------------
    fanout = _fanout(
        env,
        project_id=project.id,
        idempotency_key="journey-fanout",
        children=[
            _child(task_id=t0, priority=10, max_attempts=1),
            _child(
                task_id=t1,
                priority=8,
                max_attempts=1,
                dependencies=[{"task_id": t0, "kind": "hard", "ordinal": 0}],
            ),
            _child(
                task_id=t2,
                priority=6,
                max_attempts=1,
                dependencies=[{"task_id": t0, "kind": "soft", "ordinal": 0}],
            ),
            _child(task_id=t3, priority=4, max_attempts=2),
        ],
    )
    assert fanout.task_ids == (t0, t1, t2, t3)
    assert fanout.first_ordinal == 0 and fanout.last_ordinal == 3

    # Hard/soft gating at admission: t1 blocked on hard dep t0; t2 queued
    # despite its soft dep on the same not-yet-succeeded task.
    assert _task_row(env.writer, t0)["status"] == "queued"
    assert _task_row(env.writer, t1)["status"] == "blocked"
    assert _task_row(env.writer, t2)["status"] == "queued"
    assert _task_row(env.writer, t3)["status"] == "queued"

    # t0 succeeds (claim -> start -> complete); t1 is unblocked by the
    # completing command and then succeeds too.
    claim = _claim(env, project_id=project.id, idempotency_key="journey-claim-t0")
    assert claim is not None and claim.task.id == t0
    started = _start(env, project_id=project.id, claim=claim, idempotency_key="journey-start-t0")
    _complete(
        env,
        project_id=project.id,
        task_id=t0,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        status_version=started.status_version,
        outputs=[_prepare_output(env, name="t0.png", content=b"t0-bytes")],
        idempotency_key="journey-complete-t0",
    )
    assert _task_row(env.writer, t0)["status"] == "succeeded"
    assert _task_row(env.writer, t1)["status"] == "queued"  # unblocked

    claim = _claim(env, project_id=project.id, idempotency_key="journey-claim-t1")
    assert claim is not None and claim.task.id == t1
    started = _start(env, project_id=project.id, claim=claim, idempotency_key="journey-start-t1")
    _complete(
        env,
        project_id=project.id,
        task_id=t1,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        status_version=started.status_version,
        outputs=[_prepare_output(env, name="t1.png", content=b"t1-bytes")],
        idempotency_key="journey-complete-t1",
    )
    assert _task_row(env.writer, t1)["status"] == "succeeded"

    # t2 fails terminally (max_attempts 1): a partial failure in the chunk.
    claim = _claim(env, project_id=project.id, idempotency_key="journey-claim-t2")
    assert claim is not None and claim.task.id == t2
    started = _start(env, project_id=project.id, claim=claim, idempotency_key="journey-start-t2")
    _fail(
        env,
        project_id=project.id,
        task_id=t2,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        status_version=started.status_version,
        idempotency_key="journey-fail-t2",
    )
    assert _task_row(env.writer, t2)["status"] == "failed"

    # t3 fails within budget: requeued, retry-eligible, never terminal.
    claim = _claim(env, project_id=project.id, idempotency_key="journey-claim-t3")
    assert claim is not None and claim.task.id == t3
    started = _start(env, project_id=project.id, claim=claim, idempotency_key="journey-start-t3")
    _fail(
        env,
        project_id=project.id,
        task_id=t3,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        status_version=started.status_version,
        idempotency_key="journey-fail-t3",
    )
    assert _task_row(env.writer, t3)["status"] == "queued"
    assert [a["status"] for a in _attempt_rows(env.writer, t3)] == ["failed"]

    # Derived running state, purely from the child rows, in ordinal order.
    progress = _derive(env, project_id=project.id, run_id=fanout.run_id)
    assert progress.status == "running"
    assert progress.total_children == 4
    assert progress.succeeded == 2 and progress.failed == 1
    assert progress.ordered == (
        (0, t0, "succeeded"),
        (1, t1, "succeeded"),
        (2, t2, "failed"),
        (3, t3, "queued"),
    )
    assert RunProgressReadModel.from_mapping(progress.to_dict()) == progress

    # ------------------------------------------------------------------
    # Phase B — continuation chunk under expected-head CAS.
    # ------------------------------------------------------------------
    assert _run_stream_head(env.writer, fanout.run_id) == 1
    continued = _continue_run(
        env,
        project_id=project.id,
        run_id=fanout.run_id,
        expected_version=1,
        start_ordinal=4,
        idempotency_key="journey-continue",
        children=[
            _child(
                task_id=t4,
                priority=8,
                max_attempts=1,
                dependencies=[{"task_id": t3, "kind": "hard", "ordinal": 0}],
            ),
            _child(task_id=t5, priority=5, max_attempts=1),
            _child(task_id=t6, priority=2, max_attempts=1),
        ],
    )
    assert isinstance(continued, RunContinuationReadModel)
    assert continued.task_ids == (t4, t5, t6)
    assert continued.first_ordinal == 4 and continued.last_ordinal == 6
    assert continued.expected_version == 1 and continued.next_version == 2
    assert _run_stream_head(env.writer, fanout.run_id) == 2
    # t4 hard-depends on t3 (queued, not succeeded) -> blocked; t5/t6 queued.
    assert _task_row(env.writer, t4)["status"] == "blocked"
    assert _task_row(env.writer, t5)["status"] == "queued"
    assert _task_row(env.writer, t6)["status"] == "queued"
    # The run stream: created, then continued, then the chunk's children.
    run_stream = f"{fanout.run_id}:{CORE_RUN_STREAM_TYPE}"
    run_events = _event_rows(env.writer, run_stream)
    assert [e["kind"] for e in run_events] == [
        CORE_RUN_CREATED_EVENT_KIND,
        CORE_RUN_CONTINUED_EVENT_KIND,
    ]
    continued_data = json.loads(run_events[1]["payload_json"])["data"]
    assert continued_data["expected_version"] == 1
    assert continued_data["first_ordinal"] == 4
    assert continued_data["last_ordinal"] == 6
    assert continued_data["next_version"] == 2
    # One complete continuation receipt with the frozen result.
    receipt = _receipt_row(env.writer, project.id, "journey-continue")
    assert receipt is not None
    assert receipt["command_kind"] == CORE_RUN_CONTINUE_COMMAND_KIND
    assert json.loads(receipt["result_json"]) == continued.to_dict()
    assert receipt["resulting_stream_seq"] == 2

    # A stale (or ahead-of-head) continuation changes zero rows.
    counts_before = _counts(env.writer)
    with pytest.raises(RunStaleHeadError):
        _continue_run(
            env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=7,
            idempotency_key="journey-continue-stale",
            children=[_child(task_id=generate_lowercase_ulid())],
        )
    assert _counts(env.writer) == counts_before

    # t5 runs (its priority beats t3's), so the group cancel later cannot
    # invent an attempt fence for it; t3 stays queued for the selective retry.
    claim = _claim(env, project_id=project.id, idempotency_key="journey-claim-t5")
    assert claim is not None and claim.task.id == t5
    _start(env, project_id=project.id, claim=claim, idempotency_key="journey-start-t5")
    assert _task_row(env.writer, t5)["status"] == "running"
    assert _task_row(env.writer, t3)["status"] == "queued"

    # ------------------------------------------------------------------
    # Phase C — selective retry and stale-attempt fencing.
    # ------------------------------------------------------------------
    retried = _group_retry(
        env,
        project_id=project.id,
        run_id=fanout.run_id,
        idempotency_key="journey-retry",
        selected_task_ids=[t3],
        executor_id="executor-journey",
    )
    assert isinstance(retried, RunRetryReadModel)
    assert retried.retried_task_ids == (t3,)
    assert retried.skipped_task_ids == ()
    assert retried.run["status"] == "running"
    attempts_t3 = _attempt_rows(env.writer, t3)
    assert [a["attempt_no"] for a in attempts_t3] == [1, 2]
    assert attempts_t3[1]["status"] == "claimed"
    assert attempts_t3[1]["status_version"] == 1
    assert _task_row(env.writer, t3)["status"] == "running"
    # Unselected children untouched: t4 still blocked, t5 running, t6 queued.
    assert _task_row(env.writer, t4)["status"] == "blocked"
    assert _task_row(env.writer, t5)["status"] == "running"
    assert _task_row(env.writer, t6)["status"] == "queued"
    # A task-level retry of a terminal child is rejected before mutation.
    counts_before = _counts(env.writer)
    with pytest.raises(TaskTransitionError) as excinfo:
        UnitOfWork(env.writer).run(
            lambda u: env.task_repo.retry(
                u,
                project_id=project.id,
                task_id=t1,
                idempotency_key="journey-retry-terminal",
                now=TS2,
            )
        )
    assert excinfo.value.reason == "task_terminal"
    assert _counts(env.writer) == counts_before

    # Stale-attempt fencing: a fail presenting t3's *old* attempt (attempt
    # 1, already failed) loses on the live-status fence; zero rows.
    old_attempt = attempts_t3[0]
    counts_before = _counts(env.writer)
    with pytest.raises(TaskTransitionError) as excinfo:
        _fail(
            env,
            project_id=project.id,
            task_id=t3,
            attempt_id=old_attempt["id"],
            lease_id=old_attempt["lease_id"],
            status_version=old_attempt["status_version"],
            idempotency_key="journey-stale-fail",
        )
    assert excinfo.value.reason == "attempt_not_live"
    assert _counts(env.writer) == counts_before
    # A stale completion presenting the old attempt loses identically and
    # materializes no media, no output, and no receipt.
    media_before = env.writer.submit(
        lambda session: session.query_one(
            "SELECT count(*) FROM media WHERE project_id = ?", (project.id,)
        )[0]
    )
    with pytest.raises(TaskTransitionError) as excinfo:
        _complete(
            env,
            project_id=project.id,
            task_id=t3,
            attempt_id=old_attempt["id"],
            lease_id=old_attempt["lease_id"],
            status_version=old_attempt["status_version"],
            outputs=[_prepare_output(env, name="stale.png", content=b"stale-bytes")],
            idempotency_key="journey-stale-complete",
        )
    assert excinfo.value.reason == "attempt_not_live"
    assert _counts(env.writer) == counts_before
    media_after = env.writer.submit(
        lambda session: session.query_one(
            "SELECT count(*) FROM media WHERE project_id = ?", (project.id,)
        )[0]
    )
    assert media_after == media_before
    assert _receipt_row(env.writer, project.id, "journey-stale-complete") is None
    # The newer attempt remains the live owner, untouched.
    assert [a["status"] for a in _attempt_rows(env.writer, t3)] == [
        "failed",
        "claimed",
    ]

    # ------------------------------------------------------------------
    # Phase D — eligible group cancel with cooperative running cancellation.
    # ------------------------------------------------------------------
    cancelled = _group_cancel(
        env,
        project_id=project.id,
        run_id=fanout.run_id,
        idempotency_key="journey-cancel",
        cancel_request_id="journey-cancel-req-1",
    )
    assert isinstance(cancelled, RunCancelReadModel)
    # t3/t5 (running), t4 (blocked), and t6 (queued) are eligible; only
    # t0/t1/t2 are already terminal and skipped.
    assert cancelled.cancelled_task_ids == (t3, t4, t5, t6)
    assert cancelled.skipped_task_ids == (t0, t1, t2)
    assert cancelled.cooperative_task_ids == (t3, t5)
    assert cancelled.cancel_request_id == "journey-cancel-req-1"
    assert cancelled.run["status"] == "failed"
    assert cancelled.run["total_children"] == 7
    assert cancelled.run["succeeded"] == 2
    assert cancelled.run["failed"] == 1
    assert cancelled.run["cancelled"] == 4
    for task_id in (t3, t4, t5, t6):
        row = _task_row(env.writer, task_id)
        assert row["status"] == "cancelled"
        assert row["cancel_request_id"] == "journey-cancel-req-1"
        assert row["finished_at"] == TS
        assert _event_rows(
            env.writer, f"{task_id}:{CORE_TASK_STREAM_TYPE}"
        )[-1]["kind"] == CORE_TASK_CANCELLED_EVENT_KIND
    assert [e["kind"] for e in _event_rows(env.writer, run_stream)] == [
        CORE_RUN_CREATED_EVENT_KIND,
        CORE_RUN_CONTINUED_EVENT_KIND,
        CORE_RUN_RETRIED_EVENT_KIND,
        CORE_RUN_CANCELLED_EVENT_KIND,
    ]
    cancelled_event = json.loads(_event_rows(env.writer, run_stream)[3]["payload_json"])["data"]
    assert cancelled_event["cancelled_task_ids"] == [t3, t4, t5, t6]
    assert cancelled_event["skipped_task_ids"] == [t0, t1, t2]
    assert cancelled_event["status"] == "failed"

    # ------------------------------------------------------------------
    # Phase E — every child is terminal after cooperative group cancel.
    # ------------------------------------------------------------------
    progress = _derive(env, project_id=project.id, run_id=fanout.run_id)
    assert progress.status == "failed"
    assert progress.total_children == 7
    assert progress.succeeded == 2 and progress.failed == 1 and progress.cancelled == 4
    assert progress.ordered == (
        (0, t0, "succeeded"),
        (1, t1, "succeeded"),
        (2, t2, "failed"),
        (3, t3, "cancelled"),
        (4, t4, "cancelled"),
        (5, t5, "cancelled"),
        (6, t6, "cancelled"),
    )
    run_row = _run_row(env.writer, fanout.run_id)
    assert run_row["status"] == "failed"
    assert run_row["finished_at"] == TS
    # The persisted projection is exactly the shared derivation's output —
    # the only progress storage; no cursor or mutable aggregate exists.
    assert json.loads(run_row["result_json"]) == {
        "total_children": 7,
        "succeeded": 2,
        "failed": 1,
        "cancelled": 4,
        "status": "failed",
    }
    # Stable ordinal progress across both chunks, unchanged by every phase.
    rows = _task_rows(env.writer, fanout.run_id)
    assert [int(r["run_ordinal"]) for r in rows] == [0, 1, 2, 3, 4, 5, 6]
    assert [str(r["id"]) for r in rows] == [t0, t1, t2, t3, t4, t5, t6]

    # ------------------------------------------------------------------
    # Phase G — terminal immutability: no command may continue a terminal run.
    # ------------------------------------------------------------------
    counts_before = _counts(env.writer)
    with pytest.raises(RunTerminalError) as excinfo:
        _continue_run(
            env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=4,
            start_ordinal=7,
            idempotency_key="journey-continue-terminal",
            children=[_child(task_id=generate_lowercase_ulid())],
        )
    assert excinfo.value.status == "failed"
    with pytest.raises(RunTerminalError) as excinfo:
        _group_cancel(
            env,
            project_id=project.id,
            run_id=fanout.run_id,
            idempotency_key="journey-cancel-terminal",
        )
    assert excinfo.value.status == "failed"
    with pytest.raises(TaskTransitionError) as excinfo:
        _group_retry(
            env,
            project_id=project.id,
            run_id=fanout.run_id,
            idempotency_key="journey-retry-terminal-run",
            selected_task_ids=[t0],
        )
    assert excinfo.value.reason == "task_terminal"
    assert _counts(env.writer) == counts_before

    # ------------------------------------------------------------------
    # No plan/step record, no persisted cursor, no evidence, no parent task.
    # ------------------------------------------------------------------
    tables = _tables(env.writer)
    assert not tables.intersection(FORBIDDEN_TABLES)
    assert "run_progress" not in tables
    assert "change_cursor" not in tables
    assert _task_row(env.writer, fanout.run_id) is None
    assert _counts(env.writer)[6] == 0
    # Cancellation never declares a winning attempt; both t3 attempts are
    # preserved as history and the live attempt is terminally cancelled.
    assert _task_row(env.writer, t3)["winning_attempt_id"] is None
    assert [row["status"] for row in _attempt_rows(env.writer, t3)] == [
        "failed",
        "cancelled",
    ]


def test_multi_task_journey_continuation_replay_and_mismatch(journey_env) -> None:
    """The continuation receipt gate replays or mismatches before mutation."""
    env = journey_env
    project = _create_project(env)
    fanout = _fanout(
        env,
        project_id=project.id,
        idempotency_key="journey-replay-fanout",
        children=[_child(task_id=generate_lowercase_ulid(), priority=0)],
    )
    child = generate_lowercase_ulid()
    first = _continue_run(
        env,
        project_id=project.id,
        run_id=fanout.run_id,
        expected_version=1,
        start_ordinal=1,
        idempotency_key="journey-replay-continue",
        children=[_child(task_id=child)],
    )
    counts = _counts(env.writer)
    second = _continue_run(
        env,
        project_id=project.id,
        run_id=fanout.run_id,
        expected_version=1,
        start_ordinal=1,
        idempotency_key="journey-replay-continue",
        children=[_child(task_id=child)],
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(env.writer) == counts
    # A changed request under the same key mismatches before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _continue_run(
            env,
            project_id=project.id,
            run_id=fanout.run_id,
            expected_version=1,
            start_ordinal=1,
            idempotency_key="journey-replay-continue",
            children=[_child(task_id=generate_lowercase_ulid())],
        )
    assert _counts(env.writer) == counts
    # The continuation receipt carries the ordered chunk result.
    receipt = _receipt_row(env.writer, project.id, "journey-replay-continue")
    assert receipt["command_kind"] == CORE_RUN_CONTINUE_COMMAND_KIND
    assert json.loads(receipt["result_json"]) == first.to_dict()


# ---------------------------------------------------------------------------
