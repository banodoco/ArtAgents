"""Run repository ``close``: the receipt-protected terminal transition for
runs that own no non-terminal child work.

``core.run.close`` is the terminal transition zero-child runs can never
reach through a child transition (``total==0`` derives ``running`` forever
under the shared derivation rule). It writes the terminal status and
``finished_at``, folds the declared outcome into ``result_json``, appends
the hash-chained ``core.run.closed`` event, and records one run-level
receipt. A run that still owns a queued/blocked/running child is refused
(``RunValidationError``) and an already-terminal run raises
``RunTerminalError`` before any mutation.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts.service import ReceiptMismatchError
from astrid.core.repositories.runs import (
    CORE_RUN_CLOSE_COMMAND_KIND,
    CORE_RUN_CLOSED_EVENT_KIND,
    CORE_RUN_CREATED_EVENT_KIND,
    CORE_RUN_STREAM_TYPE,
    RunNotFoundError,
    RunRepository,
    RunTerminalError,
    RunValidationError,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter

TS = "2026-08-16T00:00:00.000000+00:00"

SPEC_A = {"backend": "rendering.remotion", "composition": "main", "fps": 24}
MANIFEST_A = ["media_1"]


@pytest.fixture
def run_env(tmp_path, core_registry):
    """Fresh kernel writer plus project and run repositories."""
    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.core.store.writer import DatabaseWriter

    db_path = tmp_path / "run_close_env.sqlite3"
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


def _child(*, task_id: str | None = None):
    entry = {
        "capability": "rendering.timeline_visualize",
        "spec": dict(SPEC_A),
        "input_manifest": list(MANIFEST_A),
    }
    if task_id is not None:
        entry["task_id"] = task_id
    return entry


def _create_run(env, *, project_id: str, children, idempotency_key: str):
    return UnitOfWork(env.writer).run(
        lambda u: env.run_repo.create(
            u,
            project_id=project_id,
            children=children,
            idempotency_key=idempotency_key,
            run_id=generate_lowercase_ulid(),
            created_at=TS,
        )
    )


def _close(
    env,
    *,
    project_id: str,
    run_id: str,
    outcome: str | None = None,
    idempotency_key: str,
    now: str | None = "2026-08-16T01:00:00.000000+00:00",
):
    return UnitOfWork(env.writer).run(
        lambda u: env.run_repo.close(
            u,
            project_id=project_id,
            run_id=run_id,
            outcome=outcome,
            idempotency_key=idempotency_key,
            now=now,
        )
    )


def _run_row(writer: DatabaseWriter, run_id: str):
    return writer.submit(
        lambda session: session.query_one("SELECT * FROM runs WHERE id = ?", (run_id,))
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


def test_close_zero_child_run_succeeds(run_env) -> None:
    """Closing a zero-child run terminalizes it with event + receipt."""
    project = _create_project(run_env)
    created = _create_run(
        run_env,
        project_id=project.id,
        children=[],
        idempotency_key="zero-child-k",
    )
    run_id = created.run_id
    run_stream = f"{run_id}:{CORE_RUN_STREAM_TYPE}"
    close_key = f"core.run.close:{project.id}:{run_id}"

    result = _close(
        run_env,
        project_id=project.id,
        run_id=run_id,
        outcome="succeeded",
        idempotency_key=close_key,
    )

    # Result model: terminal projection with the outcome folded in.
    assert result.outcome == "succeeded"
    assert result.run["status"] == "succeeded"
    assert result.run["outcome"] == "succeeded"
    assert result.run["total_children"] == 0
    assert result.run["succeeded"] == 0

    # Run row: status + finished_at written.
    run_row = _run_row(run_env.writer, run_id)
    assert run_row["status"] == "succeeded"
    assert run_row["finished_at"] == "2026-08-16T01:00:00.000000+00:00"
    stored = json.loads(run_row["result_json"])
    assert stored["status"] == "succeeded"
    assert stored["outcome"] == "succeeded"
    assert stored["total_children"] == 0

    # Stream head advanced by exactly one (created + closed events).
    assert _stream_row(run_env.writer, run_stream)["head_seq"] == 2

    # The hash-chained core.run.closed event mirrors the cancelled payload
    # shape: run_id, outcome, status, progress.
    events = _event_rows(run_env.writer, run_stream)
    assert [e["kind"] for e in events] == [
        CORE_RUN_CREATED_EVENT_KIND,
        CORE_RUN_CLOSED_EVENT_KIND,
    ]
    closed = events[1]
    data = json.loads(closed["payload_json"])["data"]
    assert data["run_id"] == run_id
    assert data["outcome"] == "succeeded"
    assert data["status"] == "succeeded"
    assert data["progress"]["total_children"] == 0
    assert data["progress"]["outcome"] == "succeeded"

    # One complete run-level receipt under the close key.
    receipt = _receipt_row(run_env.writer, project.id, close_key)
    assert receipt is not None
    assert receipt["command_kind"] == CORE_RUN_CLOSE_COMMAND_KIND
    assert receipt["primary_stream_id"] == run_stream
    assert receipt["resulting_stream_seq"] == 2
    assert receipt["first_project_seq"] == receipt["last_project_seq"]
    assert json.loads(receipt["event_ids_json"]) == [closed["event_id"]]
    assert json.loads(receipt["result_json"]) == result.to_dict()


def test_close_with_non_terminal_child_refuses(run_env) -> None:
    """A run that still owns queued work cannot be closed."""
    project = _create_project(run_env)
    created = _create_run(
        run_env,
        project_id=project.id,
        children=[_child(task_id=generate_lowercase_ulid())],
        idempotency_key="with-child-k",
    )
    run_id = created.run_id
    run_stream = f"{run_id}:{CORE_RUN_STREAM_TYPE}"
    close_key = f"core.run.close:{project.id}:{run_id}"

    with pytest.raises(RunValidationError, match="non-terminal child task"):
        _close(
            run_env,
            project_id=project.id,
            run_id=run_id,
            outcome="succeeded",
            idempotency_key=close_key,
        )

    # Zero mutation: run still running, no closed event, no receipt.
    assert _run_row(run_env.writer, run_id)["status"] == "running"
    assert [e["kind"] for e in _event_rows(run_env.writer, run_stream)] == [
        "core.run.created"
    ]
    assert _receipt_row(run_env.writer, project.id, close_key) is None


def test_close_terminal_run_raises_run_terminal_error(run_env) -> None:
    """A second close (and any close of a terminal run) is refused."""
    project = _create_project(run_env)
    created = _create_run(
        run_env,
        project_id=project.id,
        children=[],
        idempotency_key="twice-k",
    )
    run_id = created.run_id
    _close(
        run_env,
        project_id=project.id,
        run_id=run_id,
        outcome="succeeded",
        idempotency_key=f"core.run.close:{project.id}:{run_id}",
    )

    with pytest.raises(RunTerminalError) as excinfo:
        _close(
            run_env,
            project_id=project.id,
            run_id=run_id,
            outcome="succeeded",
            idempotency_key=f"core.run.close:{project.id}:{run_id}:again",
        )
    assert excinfo.value.status == "succeeded"


def test_close_outcome_variants(run_env) -> None:
    """failed and cancelled outcomes write through status/result/event."""
    project = _create_project(run_env)
    outcomes = ("failed", "cancelled")
    for index, outcome in enumerate(outcomes):
        created = _create_run(
            run_env,
            project_id=project.id,
            children=[],
            idempotency_key=f"variant-{index}-k",
        )
        run_id = created.run_id
        result = _close(
            run_env,
            project_id=project.id,
            run_id=run_id,
            outcome=outcome,
            idempotency_key=f"core.run.close:{project.id}:{run_id}",
        )
        assert result.outcome == outcome
        run_row = _run_row(run_env.writer, run_id)
        assert run_row["status"] == outcome
        stored = json.loads(run_row["result_json"])
        assert stored["status"] == outcome
        assert stored["outcome"] == outcome
        events = _event_rows(
            run_env.writer, f"{run_id}:{CORE_RUN_STREAM_TYPE}"
        )
        closed_data = json.loads(events[1]["payload_json"])["data"]
        assert closed_data["outcome"] == outcome
        assert closed_data["status"] == outcome


def test_close_default_derives_failed_child_outcome(run_env) -> None:
    """Omitted close outcome cannot relabel a terminal failed child."""
    project = _create_project(run_env)
    child_id = generate_lowercase_ulid()
    created = _create_run(
        run_env,
        project_id=project.id,
        children=[_child(task_id=child_id)],
        idempotency_key="stale-failed-run-k",
    )
    # Reproduce a legacy/stale parent row: the child is terminal but the run
    # projection has not yet been recomputed.
    UnitOfWork(run_env.writer).run(
        lambda u: u.execute(
            "UPDATE tasks SET status = 'failed', finished_at = ? WHERE id = ?",
            ("2026-08-16T01:00:00.000000+00:00", child_id),
        )
    )

    result = _close(
        run_env,
        project_id=project.id,
        run_id=created.run_id,
        idempotency_key=f"core.run.close:{project.id}:{created.run_id}",
    )
    assert result.outcome == "failed"
    assert result.run["status"] == "failed"
    assert _run_row(run_env.writer, created.run_id)["status"] == "failed"

    # Even an explicitly-successful close cannot contradict terminal child
    # outcomes on a still-running legacy row.
    project2 = _create_project(run_env, slug="pilot-two")
    child2 = generate_lowercase_ulid()
    created2 = _create_run(
        run_env,
        project_id=project2.id,
        children=[_child(task_id=child2)],
        idempotency_key="stale-failed-run-explicit-k",
    )
    UnitOfWork(run_env.writer).run(
        lambda u: u.execute(
            "UPDATE tasks SET status = 'failed', finished_at = ? WHERE id = ?",
            ("2026-08-16T01:00:00.000000+00:00", child2),
        )
    )
    with pytest.raises(RunValidationError, match="cannot close it as 'succeeded'"):
        _close(
            run_env,
            project_id=project2.id,
            run_id=created2.run_id,
            outcome="succeeded",
            idempotency_key=f"core.run.close:{project2.id}:{created2.run_id}",
        )


def test_close_replay_under_same_key(run_env) -> None:
    """An identical retry replays the stored result with zero new rows."""
    project = _create_project(run_env)
    created = _create_run(
        run_env,
        project_id=project.id,
        children=[],
        idempotency_key="replay-k",
    )
    run_id = created.run_id
    run_stream = f"{run_id}:{CORE_RUN_STREAM_TYPE}"
    close_key = f"core.run.close:{project.id}:{run_id}"

    first = _close(
        run_env,
        project_id=project.id,
        run_id=run_id,
        outcome="succeeded",
        idempotency_key=close_key,
    )
    events_after_first = len(_event_rows(run_env.writer, run_stream))

    replayed = _close(
        run_env,
        project_id=project.id,
        run_id=run_id,
        outcome="succeeded",
        idempotency_key=close_key,
    )
    assert replayed.to_dict() == first.to_dict()
    assert len(_event_rows(run_env.writer, run_stream)) == events_after_first
    assert _receipt_row(run_env.writer, project.id, close_key) is not None


def test_close_mismatch_under_same_key(run_env) -> None:
    """A different outcome under the same key is a receipt mismatch."""
    project = _create_project(run_env)
    created = _create_run(
        run_env,
        project_id=project.id,
        children=[],
        idempotency_key="mismatch-k",
    )
    run_id = created.run_id
    close_key = f"core.run.close:{project.id}:{run_id}"

    _close(
        run_env,
        project_id=project.id,
        run_id=run_id,
        outcome="succeeded",
        idempotency_key=close_key,
    )
    with pytest.raises(ReceiptMismatchError):
        _close(
            run_env,
            project_id=project.id,
            run_id=run_id,
            outcome="cancelled",
            idempotency_key=close_key,
        )


def test_close_missing_run_raises_not_found(run_env) -> None:
    """Closing an unknown run is a typed not-found before any mutation."""
    project = _create_project(run_env)
    with pytest.raises(RunNotFoundError):
        _close(
            run_env,
            project_id=project.id,
            run_id=generate_lowercase_ulid(),
            outcome="succeeded",
            idempotency_key=f"core.run.close:{project.id}:missing",
        )
