"""Executable run SDK service tests (m4 plan step 13, task T14).

Proves ``astrid.sdk.runs.RunsService`` exposes repository-backed,
envelope-shaped ``list``/``show``/``cancel``/``retry_failed``/``events`` over
the kernel :class:`~astrid.core.repositories.runs.RunRepository`:

- ``show`` assembles the run read model plus derived child progress (a pure
  function of the child task rows) and, when requested, the run's ordered
  evidence items;
- partial progress (some children terminal, some still running) and failures
  are reported accurately by the shared derivation;
- ``cancel`` drives eligible children to ``cancelled`` and ``retry_failed``
  restarts eligible failed/expired children, both returning one complete
  run-level receipt with replay and mismatch behavior preserved;
- typed ``not_found`` for a missing run and ``terminal_state`` for a
  terminal run; ordered ``core.run`` stream events through the read-only
  event repository.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.registry import core_only_registry
from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.events import EventRepository
from astrid.core.repositories.evidence import EvidenceRepository
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.repositories.runs import (
    CORE_RUN_STREAM_TYPE,
    RunRepository,
)
from astrid.core.repositories.tasks import TaskRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.sdk.runs import RunsService

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
    """Fresh kernel writer, project/task/run/evidence repos, event log, service."""
    registry = core_only_registry()
    writer = DatabaseWriter(tmp_path / "runs.sqlite3", registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        tasks = TaskRepository(events=events, receipts=receipts)
        runs = RunRepository(events=events, receipts=receipts)
        evidence = EvidenceRepository(events=events, receipts=receipts)
        event_log = EventRepository(writer)
        yield SimpleNamespace(
            writer=writer,
            projects=projects,
            tasks=tasks,
            runs=runs,
            evidence=evidence,
            event_log=event_log,
            service=RunsService(
                writer, projects, runs, receipts, evidence, event_log
            ),
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


def _child(*, task_id: str, capability: str = "cap.child", **overrides):
    entry = {
        "capability": capability,
        "spec": {"n": 1},
        "input_manifest": [],
        "task_id": task_id,
    }
    entry.update(overrides)
    return entry


def _create_run(
    env: SimpleNamespace,
    *,
    project_id: str,
    children,
    evidence=(),
    idempotency_key: str = "run-k",
    kind: str = "group",
    title: str | None = "Test run",
):
    run_id = generate_lowercase_ulid()
    result = UnitOfWork(env.writer).run(
        lambda u: env.runs.create(
            u,
            project_id=project_id,
            children=children,
            evidence=evidence,
            idempotency_key=idempotency_key,
            run_id=run_id,
            kind=kind,
            title=title,
            created_at=TS,
        )
    )
    return run_id, result


def _fail_child(env: SimpleNamespace, *, project_id: str, task_id: str) -> None:
    claim = UnitOfWork(env.writer).run(
        lambda u: env.tasks.claim(
            u,
            project_id=project_id,
            idempotency_key=f"claim-{task_id}",
            executor_id="executor-test",
            now=TS,
        )
    )
    assert claim is not None
    assert claim.task.id == task_id, "claim picked the wrong task; set priority/available_at"
    started = UnitOfWork(env.writer).run(
        lambda u: env.tasks.start(
            u,
            project_id=project_id,
            task_id=task_id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=claim.attempt.status_version,
            idempotency_key=f"start-{task_id}",
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
            idempotency_key=f"fail-{task_id}",
            now=TS,
            error={"kind": "test.fixture", "message": "intentional failure"},
        )
    )


# ---------------------------------------------------------------------------
# Envelope and receipt shape
# ---------------------------------------------------------------------------


def test_show_and_list_envelopes_have_five_keys(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    t0 = generate_lowercase_ulid()
    run_id, _ = _create_run(
        env, project_id=project_id, children=[_child(task_id=t0)]
    )

    shown = env.service.show(project_id, run_id)
    assert shown.ok is True
    assert set(shown.as_dict().keys()) == ENVELOPE_KEYS
    assert shown.receipt is None
    assert shown.idempotency_key == ""

    listed = env.service.list(project_id)
    assert listed.ok is True
    assert listed.receipt is None


# ---------------------------------------------------------------------------
# List and show with derived child progress
# ---------------------------------------------------------------------------


def test_list_returns_run_read_models(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    run_id, _ = _create_run(
        env, project_id=project_id, children=[_child(task_id=generate_lowercase_ulid())]
    )
    listed = env.service.list(project_id)
    assert listed.ok is True
    assert [row["id"] for row in listed.data] == [run_id]
    assert listed.data[0]["status"] == "running"


def test_show_returns_run_model_and_derived_progress(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    t0 = generate_lowercase_ulid()
    t1 = generate_lowercase_ulid()
    run_id, _ = _create_run(
        env, project_id=project_id, children=[_child(task_id=t0), _child(task_id=t1)]
    )

    shown = env.service.show(project_id, run_id)
    assert shown.ok is True
    assert shown.data["id"] == run_id
    assert shown.data["project_id"] == project_id
    assert shown.data["kind"] == "group"
    assert shown.data["title"] == "Test run"
    assert shown.data["progress"]["status"] == "running"
    assert shown.data["progress"]["total_children"] == 2
    assert shown.data["progress"]["succeeded"] == 0
    assert shown.data["progress"]["failed"] == 0
    assert [entry["task_id"] for entry in shown.data["progress"]["ordered"]] == [
        t0,
        t1,
    ]


def test_show_reports_partial_progress_and_failure(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    t0 = generate_lowercase_ulid()
    t1 = generate_lowercase_ulid()
    run_id, _ = _create_run(
        env,
        project_id=project_id,
        children=[
            _child(task_id=t0, max_attempts=1, priority=10),
            _child(task_id=t1, priority=0),
        ],
    )
    # t0 terminally fails (budget exhausted); t1 stays queued.
    _fail_child(env, project_id=project_id, task_id=t0)

    shown = env.service.show(project_id, run_id)
    assert shown.ok is True
    # One terminally-failed child, one still-queued child: the run is still
    # running (not all children terminal) with the failure reported.
    assert shown.data["progress"]["failed"] == 1
    assert shown.data["progress"]["status"] == "running"
    assert [entry["task_id"] for entry in shown.data["progress"]["ordered"]] == [
        t0,
        t1,
    ]
    assert shown.data["progress"]["ordered"][0]["status"] == "failed"
    assert shown.data["progress"]["ordered"][1]["status"] == "queued"


def test_show_missing_returns_not_found(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    result = env.service.show(project_id, "missing-run")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"


# ---------------------------------------------------------------------------
# Optional evidence
# ---------------------------------------------------------------------------


def test_show_with_evidence_returns_run_evidence(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    run_id, _ = _create_run(
        env,
        project_id=project_id,
        children=[_child(task_id=generate_lowercase_ulid())],
        evidence=[
            {"kind": "observation", "summary": "first", "data": {"n": 1}},
            {"kind": "validation", "summary": "second", "data": {"ok": True}},
        ],
    )

    plain = env.service.show(project_id, run_id)
    assert plain.ok is True
    assert "evidence" not in plain.data

    with_evidence = env.service.show(project_id, run_id, include_evidence=True)
    assert with_evidence.ok is True
    assert len(with_evidence.data["evidence"]) == 2
    assert with_evidence.data["evidence"][0]["summary"] == "first"
    assert with_evidence.data["evidence"][1]["summary"] == "second"


def test_show_with_evidence_includes_bounded_child_completion_outputs(
    env: SimpleNamespace,
) -> None:
    project_id = _create_project(env)
    task_id = generate_lowercase_ulid()
    run_id, _ = _create_run(
        env,
        project_id=project_id,
        children=[_child(task_id=task_id)],
        idempotency_key="run-output-evidence-k",
    )
    media_id = generate_lowercase_ulid()
    def _insert_output(session):
        session.execute(
            "INSERT INTO media "
            "(id, project_id, media_kind, mime_type, byte_size, content_hash, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (media_id, project_id, "video", "video/mp4", 12, "b" * 64, "{}", TS),
        )
        session.execute(
            "INSERT INTO task_outputs "
            "(task_id, ordinal, role, media_id, is_primary, params_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                task_id,
                0,
                "result",
                media_id,
                1,
                json.dumps(
                    {
                        "label": "rendered video",
                        "path": "rendered.mp4",
                        "content_hash": "a" * 64,
                        "byte_size": 12,
                    },
                    separators=(",", ":"),
                ),
                TS,
            ),
        )
    env.writer.submit(_insert_output)

    shown = env.service.show(project_id, run_id, include_evidence=True)
    assert shown.ok is True
    child = shown.data["child_outputs"][0]
    assert child["task_id"] == task_id
    assert child["outputs"] == [
        {
            "ordinal": 0,
            "role": "result",
            "is_primary": True,
            "media_id": media_id,
            "label": "rendered video",
            "path": "rendered.mp4",
            "content_hash": "a" * 64,
            "byte_size": 12,
        }
    ]


# ---------------------------------------------------------------------------
# Cancel: repository selection, terminal immutability, receipts
# ---------------------------------------------------------------------------


def test_cancel_drives_children_to_cancelled_with_receipt(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    t0 = generate_lowercase_ulid()
    t1 = generate_lowercase_ulid()
    run_id, _ = _create_run(
        env, project_id=project_id, children=[_child(task_id=t0), _child(task_id=t1)]
    )

    cancelled = env.service.cancel(project_id, run_id, idempotency_key="cancel-k")
    assert cancelled.ok is True
    assert cancelled.receipt is not None
    assert cancelled.receipt.command_kind == "core.run.cancel"
    assert set(cancelled.data["cancelled_task_ids"]) == {t0, t1}
    assert cancelled.data["progress"]["status"] == "cancelled"
    assert cancelled.data["progress"]["cancelled"] == 2

    shown = env.service.show(project_id, run_id)
    assert shown.data["progress"]["status"] == "cancelled"


def test_cancel_terminal_run_returns_terminal_state(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    run_id, _ = _create_run(
        env, project_id=project_id, children=[_child(task_id=generate_lowercase_ulid())]
    )
    assert env.service.cancel(project_id, run_id).ok is True

    second = env.service.cancel(project_id, run_id, idempotency_key="cancel-2")
    assert second.ok is False
    assert second.error is not None
    assert second.error.code == "terminal_state"


def test_cancel_replay_returns_same_receipt(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    run_id, _ = _create_run(
        env, project_id=project_id, children=[_child(task_id=generate_lowercase_ulid())]
    )

    first = env.service.cancel(project_id, run_id, idempotency_key="cancel-k")
    replay = env.service.cancel(project_id, run_id, idempotency_key="cancel-k")
    assert first.ok is True
    assert replay.ok is True
    assert replay.receipt.receipt_id == first.receipt.receipt_id
    assert replay.data == first.data


# ---------------------------------------------------------------------------
# Retry failed: repository selection, receipts
# ---------------------------------------------------------------------------


def test_retry_failed_restarts_failed_children(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    t0 = generate_lowercase_ulid()
    t1 = generate_lowercase_ulid()
    run_id, _ = _create_run(
        env,
        project_id=project_id,
        children=[
            _child(task_id=t0, max_attempts=2, priority=10),
            _child(task_id=t1, priority=0),
        ],
    )
    _fail_child(env, project_id=project_id, task_id=t0)

    retried = env.service.retry_failed(
        project_id, run_id, idempotency_key="retry-k"
    )
    assert retried.ok is True
    assert retried.receipt is not None
    assert retried.receipt.command_kind == "core.run.retry"
    assert retried.data["retried_task_ids"] == [t0]
    assert retried.data["skipped_task_ids"] == [t1]


def test_retry_failed_response_refreshes_synchronous_completion_and_replay(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A batch retry response reflects the terminal run read immediately."""
    project_id = _create_project(env)
    task_id = generate_lowercase_ulid()
    run_id, _ = _create_run(
        env,
        project_id=project_id,
        children=[_child(task_id=task_id, max_attempts=2)],
    )
    _fail_child(env, project_id=project_id, task_id=task_id)

    class _NoopMedia:
        def materialize_prepared(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("summary-only test must not materialize media")

    env.service._tasks = env.tasks
    env.service._media = _NoopMedia()
    env.service._projects_root = "/tmp"

    def _synchronous_dispatch(**kwargs):
        attempt = kwargs["attempt"]
        return UnitOfWork(env.writer).run(
            lambda u: (
                env.tasks.complete(
                    u,
                    project_id=project_id,
                    task_id=task_id,
                    attempt_id=attempt.id,
                    lease_id=attempt.lease_id,
                    expected_status_version=attempt.status_version,
                    idempotency_key="fake-run-dispatch-complete",
                    outputs=[],
                    result={"recovered": True},
                    media_repo=_NoopMedia(),
                    now=TS,
                ),
                None,
            )[-1]
        )

    monkeypatch.setattr(
        "astrid.sdk.invocation.dispatch_retried_task", _synchronous_dispatch
    )
    first = env.service.retry_failed(
        project_id, run_id, idempotency_key="retry-run-response-k"
    )
    assert first.ok is True
    shown = env.service.show(project_id, run_id).data
    assert first.data["run"]["status"] == shown["status"] == "succeeded"
    assert first.data["run"]["finished_at"] == shown["finished_at"]
    assert first.data["progress"] == shown["progress"]

    replay = env.service.retry_failed(
        project_id, run_id, idempotency_key="retry-run-response-k"
    )
    assert replay.ok is True
    assert replay.data == first.data
    assert replay.receipt.receipt_id == first.receipt.receipt_id


def test_retry_failed_selects_explicit_subset(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    t0 = generate_lowercase_ulid()
    run_id, _ = _create_run(
        env,
        project_id=project_id,
        children=[_child(task_id=t0, max_attempts=2)],
    )
    _fail_child(env, project_id=project_id, task_id=t0)

    retried = env.service.retry_failed(
        project_id, run_id, selected_task_ids=[t0], idempotency_key="retry-sub"
    )
    assert retried.ok is True
    assert retried.data["retried_task_ids"] == [t0]
    assert retried.data["skipped_task_ids"] == []

    # Selecting an id that is not a direct child is a typed validation error
    # before any mutation.
    foreign = generate_lowercase_ulid()
    bad = env.service.retry_failed(
        project_id, run_id, selected_task_ids=[foreign], idempotency_key="retry-bad"
    )
    assert bad.ok is False
    assert bad.error is not None
    assert bad.error.code == "validation_error"


def test_retry_failed_terminal_run_returns_terminal_state(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    run_id, _ = _create_run(
        env, project_id=project_id, children=[_child(task_id=generate_lowercase_ulid())]
    )
    assert env.service.cancel(project_id, run_id).ok is True

    retried = env.service.retry_failed(project_id, run_id)
    assert retried.ok is False
    assert retried.error is not None
    assert retried.error.code == "terminal_state"


def test_retry_failed_without_eligible_children_returns_actionable_details(
    env: SimpleNamespace,
) -> None:
    project_id = _create_project(env)
    task_id = generate_lowercase_ulid()
    run_id, _ = _create_run(
        env,
        project_id=project_id,
        children=[_child(task_id=task_id, max_attempts=1)],
    )
    _fail_child(env, project_id=project_id, task_id=task_id)

    retried = env.service.retry_failed(project_id, run_id)

    assert retried.ok is False
    assert retried.error is not None
    assert retried.error.code == "validation_error"
    assert retried.error.message.startswith("run retry found no eligible")
    assert retried.error.details == {
        "entity": "run_retry",
        "run_id": run_id,
        "reason": "no_eligible_children",
        "skipped_task_ids": [task_id],
        "recovery": (
            "run `astrid runs show <run> --project <project>` to inspect child "
            "progress, then retry only after a child is failed or expired and "
            "still within its attempt budget"
        ),
    }


# ---------------------------------------------------------------------------
# Ordered events
# ---------------------------------------------------------------------------


def test_events_returns_ordered_stream_events(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    run_id, _ = _create_run(
        env, project_id=project_id, children=[_child(task_id=generate_lowercase_ulid())]
    )

    events = env.service.events(project_id, run_id)
    assert events.ok is True
    assert [event["kind"] for event in events.data] == ["core.run.created"]
    assert events.data[0]["stream_id"] == f"{run_id}:{CORE_RUN_STREAM_TYPE}"

    env.service.cancel(project_id, run_id)
    after = env.service.events(project_id, run_id)
    assert [event["kind"] for event in after.data] == [
        "core.run.created",
        "core.run.cancelled",
    ]


def test_events_missing_returns_not_found(env: SimpleNamespace) -> None:
    project_id = _create_project(env)
    result = env.service.events(project_id, "missing-run")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"


# ---------------------------------------------------------------------------
# Project slug resolution (CLI parity with projects/media families)
# ---------------------------------------------------------------------------


def test_list_show_events_accept_project_slug(env: SimpleNamespace) -> None:
    project_id = _create_project(env, slug="runproj")
    run_id, _ = _create_run(
        env, project_id=project_id, children=[_child(task_id=generate_lowercase_ulid())]
    )

    listed = env.service.list("runproj")
    assert listed.ok is True
    assert [row["id"] for row in listed.data] == [run_id]
    shown = env.service.show("runproj", run_id)
    assert shown.ok is True
    assert shown.data["id"] == run_id
    events = env.service.events("runproj", run_id)
    assert events.ok is True
    assert events.data[0]["kind"] == "core.run.created"


def test_unknown_project_slug_fails_loudly_not_silently_empty(
    env: SimpleNamespace,
) -> None:
    listed = env.service.list("nope")
    assert listed.ok is False
    assert listed.error is not None
    assert listed.error.code in ("not_found", "validation_error")
