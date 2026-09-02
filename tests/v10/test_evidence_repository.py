"""Evidence repository tests: immutable insertion and listing for the five
closed kinds (m3 plan step 4, T4).

This suite proves the kernel evidence vertical over the frozen
``evidence_items`` table:

- ``record`` inserts one row, appends one hash-chained
  ``core.evidence.recorded`` event on the run stream, and records one
  complete receipt keyed on ``core.evidence.record``, inside the caller's
  single ``BEGIN IMMEDIATE`` unit of work;
- the closed five-kind vocabulary (``observation``, ``measurement``,
  ``validation``, ``decision``, ``error``) is repository-enforced — the DDL
  has no CHECK on ``evidence_items.kind``;
- every cross-row rule is validated **before any write**: project/run
  agreement (``missing_run``/``foreign_run``/``run_stream_missing``),
  direct-child task membership (``missing_task``/``foreign_task``/
  ``not_direct_child``), same-project media (``missing_media``/
  ``foreign_media``), and canonical JSON payloads (``bad_data``);
- replay returns the stored result with zero new rows, mismatch fails
  before any mutation, and a crash at any statement boundary reopens to
  the old (zero-row) state;
- ``list`` is a transaction-free deterministic read ordered by
  ``run_id``, then ``created_at``, then ``id`` (the ``evidence_run_time``
  index shape), optionally filtered by run and/or task, with each row's
  recorded event sequence resolved from the run stream.

Every command runs inside the caller's one ``BEGIN IMMEDIATE`` unit of work
(:class:`astrid.core.store.uow.UnitOfWork`); every read runs on a separate
read-only connection.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.io.media_import import prepare_media_file
from astrid.core.receipts import ReceiptMismatchError, ReceiptService
from astrid.core.repositories import (
    MediaRepository,
    ProjectRepository,
)
from astrid.core.repositories.evidence import (
    CORE_EVIDENCE_RECORDED_EVENT_KIND,
    CORE_EVIDENCE_RECORD_COMMAND_KIND,
    EVIDENCE_KINDS,
    EvidenceReadModel,
    EvidenceRepository,
    EvidenceValidationError,
)
from astrid.core.repositories.media import EXTERNAL_LOCAL_REALM
from astrid.core.repositories.runs import (
    CORE_RUN_STREAM_TYPE,
    RunRepository,
    RunValidationError,
)
from astrid.core.repositories.tasks import TaskRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter

TS = "2026-08-17T00:00:00.000000+00:00"
TS2 = "2026-08-17T01:00:00.000000+00:00"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

SPEC_A = {"backend": "rendering.remotion", "composition": "main", "fps": 24}
MANIFEST_A = []


class _InjectedCrash(RuntimeError):
    """Sentinel raised at one statement boundary by the crash test."""


@pytest.fixture
def env(tmp_path: Path, core_registry):
    """Fresh kernel writer plus project/media/task/run/evidence repositories."""
    writer = DatabaseWriter(tmp_path / "evidence.sqlite3", core_registry)
    events = EventAppendService(core_registry)
    receipts = ReceiptService()
    try:
        yield SimpleNamespace(
            writer=writer,
            projects_root=tmp_path,
            project_repo=ProjectRepository(events=events, receipts=receipts),
            media_repo=MediaRepository(
                events=events, receipts=receipts, projects_root=tmp_path
            ),
            task_repo=TaskRepository(events=events, receipts=receipts),
            run_repo=RunRepository(events=events, receipts=receipts),
            evidence_repo=EvidenceRepository(events=events, receipts=receipts),
        )
    finally:
        writer.close()


def _fresh_namespace(root: Path, registry):
    """Build a fresh writer + repository namespace rooted at ``root``."""
    writer = DatabaseWriter(root / "scratch.sqlite3", registry)
    events = EventAppendService(registry)
    receipts = ReceiptService()
    return SimpleNamespace(
        writer=writer,
        projects_root=root,
        project_repo=ProjectRepository(events=events, receipts=receipts),
        media_repo=MediaRepository(
            events=events, receipts=receipts, projects_root=root
        ),
        task_repo=TaskRepository(events=events, receipts=receipts),
        run_repo=RunRepository(events=events, receipts=receipts),
        evidence_repo=EvidenceRepository(events=events, receipts=receipts),
    )


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


def _write_png(env, name: str, data: bytes = PNG_BYTES) -> Path:
    path = env.projects_root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _import_media(
    env,
    *,
    project_id: str,
    media_id: str | None = None,
    data: bytes = PNG_BYTES,
    realm: str = EXTERNAL_LOCAL_REALM,
    idempotency_key: str = "import-k-1",
):
    path = _write_png(env, f"media-{generate_lowercase_ulid()}.png", data)
    prepared = prepare_media_file(path)
    args = {
        "project_id": project_id,
        "prepared": prepared,
        "idempotency_key": idempotency_key,
        "media_id": media_id or generate_lowercase_ulid(),
        "realm": realm,
        "created_at": TS,
    }
    return UnitOfWork(env.writer).run(
        lambda u: env.media_repo.import_prepared(u, **args)
    )


def _child(*, task_id: str | None = None, **overrides):
    entry = {
        "capability": "rendering.timeline_visualize",
        "spec": dict(SPEC_A),
        "input_manifest": list(MANIFEST_A),
    }
    if task_id is not None:
        entry["task_id"] = task_id
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


def _record(
    env,
    *,
    project_id: str,
    run_id: str,
    kind: str = "observation",
    summary: str = "observed a thing",
    data=None,
    task_id: str | None = None,
    media_id: str | None = None,
    idempotency_key: str = "evidence-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "run_id": run_id,
        "kind": kind,
        "summary": summary,
        "data": data,
        "task_id": task_id,
        "media_id": media_id,
        "idempotency_key": idempotency_key,
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.evidence_repo.record(u, **args)
    )


def _counts(writer: DatabaseWriter) -> tuple[int, ...]:
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


def _evidence_row(writer: DatabaseWriter, evidence_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM evidence_items WHERE id = ?", (evidence_id,)
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


def _crash_run(writer: DatabaseWriter, *, kind: str | None, sql_sub: str | None, fn):
    """Run ``fn`` inside a UoW that raises :class:`_InjectedCrash` at the
    first boundary matching ``kind`` or ``sql_sub``."""
    state = {"crashed": False}

    def observer(k: str, sql: str, params: tuple) -> None:
        if (kind is not None and k == kind) or (sql_sub is not None and sql_sub in sql):
            state["crashed"] = True
            raise _InjectedCrash()

    try:
        UnitOfWork(writer, on_statement=observer).run(fn)
    except _InjectedCrash:
        return "crashed"
    return "completed"


# ---------------------------------------------------------------------------
# record: insertion, event, receipt
# ---------------------------------------------------------------------------


def test_record_observation_inserts_row_event_and_receipt(env) -> None:
    project = _create_project(env)
    run = _fanout(env, project_id=project.id, children=[])
    counts = _counts(env.writer)

    result = _record(
        env,
        project_id=project.id,
        run_id=run.run_id,
        kind="observation",
        summary="the render completed within budget",
        data={"latency_ms": 42, "frames": [1, 2, 3]},
        idempotency_key="evidence-c1",
    )
    assert isinstance(result, EvidenceReadModel)
    assert result.project_id == project.id
    assert result.run_id == run.run_id
    assert result.kind == "observation"
    assert result.summary == "the render completed within budget"
    assert result.data == {"latency_ms": 42, "frames": [1, 2, 3]}
    assert result.task_id is None
    assert result.media_id is None
    # The run stream carried the created event (seq 1); the evidence event
    # is the second event on the run stream.
    assert result.event_head_seq == 2

    # One row + one event + one receipt; nothing else changed.
    assert _counts(env.writer) == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4],
        counts[5],
        counts[6] + 1,
    )

    row = _evidence_row(env.writer, result.id)
    assert row is not None
    assert row["run_id"] == run.run_id
    assert row["kind"] == "observation"
    assert row["summary"] == "the render completed within budget"
    assert json.loads(row["data_json"]) == {"latency_ms": 42, "frames": [1, 2, 3]}
    assert row["task_id"] is None
    assert row["media_id"] is None

    # The registered event on the run stream carries the evidence id.
    run_stream_id = f"{run.run_id}:{CORE_RUN_STREAM_TYPE}"
    events = _event_rows(env.writer, run_stream_id)
    assert [e["kind"] for e in events] == ["core.run.created", CORE_EVIDENCE_RECORDED_EVENT_KIND]
    data = json.loads(events[-1]["payload_json"])["data"]
    assert data["evidence_id"] == result.id
    assert data["run_id"] == run.run_id
    assert data["kind"] == "observation"
    assert data["summary"] == "the render completed within budget"
    assert data["data"] == {"latency_ms": 42, "frames": [1, 2, 3]}
    assert data["task_id"] is None
    assert data["media_id"] is None

    # One complete receipt keyed on the frozen evidence command kind.
    receipt = _receipt_row(env.writer, project.id, "evidence-c1")
    assert receipt["command_kind"] == CORE_EVIDENCE_RECORD_COMMAND_KIND
    assert receipt["primary_stream_id"] == run_stream_id
    assert receipt["resulting_stream_seq"] == 2
    assert json.loads(receipt["result_json"])["id"] == result.id


def test_record_all_five_closed_kinds(env) -> None:
    project = _create_project(env)
    run = _fanout(env, project_id=project.id, children=[])
    recorded = []
    for index, kind in enumerate(EVIDENCE_KINDS):
        recorded.append(
            _record(
                env,
                project_id=project.id,
                run_id=run.run_id,
                kind=kind,
                summary=f"{kind} summary",
                data={"index": index},
                idempotency_key=f"evidence-kind-{index}",
            )
        )
    assert [r.kind for r in recorded] == list(EVIDENCE_KINDS)
    rows = env.evidence_repo.list(env.writer, project.id)
    assert [r.kind for r in rows] == list(EVIDENCE_KINDS)


def test_record_optional_task_and_media_links(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-e1")
    child_id = generate_lowercase_ulid()
    run = _fanout(
        env,
        project_id=project.id,
        children=[_child(task_id=child_id)],
    )
    assert run.task_ids == (child_id,)

    # A direct child task plus same-project media both resolve.
    linked = _record(
        env,
        project_id=project.id,
        run_id=run.run_id,
        kind="measurement",
        summary="measured the output",
        data={"px": 1920},
        task_id=child_id,
        media_id=media.id,
        idempotency_key="evidence-e1",
    )
    assert linked.task_id == child_id
    assert linked.media_id == media.id


# ---------------------------------------------------------------------------
# record: pre-write validation (zero rows changed)
# ---------------------------------------------------------------------------


def test_record_rejects_bad_kind_and_summary(env) -> None:
    project = _create_project(env)
    run = _fanout(env, project_id=project.id, children=[])
    counts = _counts(env.writer)

    with pytest.raises(EvidenceValidationError) as excinfo:
        _record(
            env,
            project_id=project.id,
            run_id=run.run_id,
            kind="opinion",
            idempotency_key="evidence-badkind",
        )
    assert excinfo.value.detail == "bad_kind"

    with pytest.raises(EvidenceValidationError) as excinfo:
        _record(
            env,
            project_id=project.id,
            run_id=run.run_id,
            summary="   ",
            idempotency_key="evidence-badsummary",
        )
    assert excinfo.value.detail == "bad_summary"

    assert _counts(env.writer) == counts


def test_record_rejects_missing_and_foreign_run(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    run_b = _fanout(env, project_id=project_b.id, children=[])
    counts = _counts(env.writer)

    with pytest.raises(EvidenceValidationError) as excinfo:
        _record(
            env,
            project_id=project_a.id,
            run_id=generate_lowercase_ulid(),
            idempotency_key="evidence-missingrun",
        )
    assert excinfo.value.detail == "missing_run"

    # The run exists but belongs to another project: foreign_run.
    with pytest.raises(EvidenceValidationError) as excinfo:
        _record(
            env,
            project_id=project_a.id,
            run_id=run_b.run_id,
            idempotency_key="evidence-foreignrun",
        )
    assert excinfo.value.detail == "foreign_run"

    assert _counts(env.writer) == counts


def test_record_rejects_task_not_direct_child(env) -> None:
    project = _create_project(env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    run_a = _fanout(
        env,
        project_id=project.id,
        children=[_child(task_id=child_a)],
        idempotency_key="fanout-ta",
    )
    run_b = _fanout(
        env,
        project_id=project.id,
        children=[_child(task_id=child_b)],
        idempotency_key="fanout-tb",
    )
    counts = _counts(env.writer)

    # Unknown task.
    with pytest.raises(EvidenceValidationError) as excinfo:
        _record(
            env,
            project_id=project.id,
            run_id=run_a.run_id,
            task_id=generate_lowercase_ulid(),
            idempotency_key="evidence-missingtask",
        )
    assert excinfo.value.detail == "missing_task"

    # A task that is a direct child of run_b, recorded against run_a.
    with pytest.raises(EvidenceValidationError) as excinfo:
        _record(
            env,
            project_id=project.id,
            run_id=run_a.run_id,
            task_id=child_b,
            idempotency_key="evidence-notchild",
        )
    assert excinfo.value.detail == "not_direct_child"

    # The direct child of run_a is accepted for run_a.
    ok = _record(
        env,
        project_id=project.id,
        run_id=run_a.run_id,
        task_id=child_a,
        idempotency_key="evidence-okchild",
    )
    assert ok.task_id == child_a
    assert run_b.run_id != run_a.run_id

    assert _counts(env.writer) == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4],
        counts[5],
        counts[6] + 1,
    )


def test_record_rejects_foreign_task(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    run_a = _fanout(
        env,
        project_id=project_a.id,
        children=[_child(task_id=child_a)],
        idempotency_key="fanout-fa",
    )
    run_b = _fanout(
        env,
        project_id=project_b.id,
        children=[_child(task_id=child_b)],
        idempotency_key="fanout-fb",
    )
    counts = _counts(env.writer)

    # The run belongs to the caller's project, but the task belongs to
    # another project: foreign_task (the run check passes first).
    with pytest.raises(EvidenceValidationError) as excinfo:
        _record(
            env,
            project_id=project_a.id,
            run_id=run_a.run_id,
            task_id=child_b,
            idempotency_key="evidence-foreigntask",
        )
    assert excinfo.value.detail == "foreign_task"
    assert _counts(env.writer) == counts


def test_record_rejects_missing_and_foreign_media(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    media_b = _import_media(
        env, project_id=project_b.id, idempotency_key="import-media-b"
    )
    run_a = _fanout(env, project_id=project_a.id, children=[])
    counts = _counts(env.writer)

    with pytest.raises(EvidenceValidationError) as excinfo:
        _record(
            env,
            project_id=project_a.id,
            run_id=run_a.run_id,
            media_id=generate_lowercase_ulid(),
            idempotency_key="evidence-missingmedia",
        )
    assert excinfo.value.detail == "missing_media"

    with pytest.raises(EvidenceValidationError) as excinfo:
        _record(
            env,
            project_id=project_a.id,
            run_id=run_a.run_id,
            media_id=media_b.id,
            idempotency_key="evidence-foreignmedia",
        )
    assert excinfo.value.detail == "foreign_media"

    assert _counts(env.writer) == counts


def test_record_rejects_non_canonical_data(env) -> None:
    project = _create_project(env)
    run = _fanout(env, project_id=project.id, children=[])
    counts = _counts(env.writer)

    # Not a JSON object at all.
    with pytest.raises(EvidenceValidationError) as excinfo:
        _record(
            env,
            project_id=project.id,
            run_id=run.run_id,
            data="not-an-object",
            idempotency_key="evidence-baddata1",
        )
    assert excinfo.value.detail == "bad_data"

    # A non-finite number cannot canonicalize.
    with pytest.raises(EvidenceValidationError) as excinfo:
        _record(
            env,
            project_id=project.id,
            run_id=run.run_id,
            data={"bad": float("nan")},
            idempotency_key="evidence-baddata2",
        )
    assert excinfo.value.detail == "bad_data"

    assert _counts(env.writer) == counts


# ---------------------------------------------------------------------------
# record: replay, mismatch, atomicity
# ---------------------------------------------------------------------------


def test_record_replay_and_mismatch(env) -> None:
    project = _create_project(env)
    run = _fanout(env, project_id=project.id, children=[])
    counts = _counts(env.writer)
    evidence_id = generate_lowercase_ulid()

    first = _record(
        env,
        project_id=project.id,
        run_id=run.run_id,
        summary="same summary",
        data={"a": 1},
        idempotency_key="evidence-replay",
        evidence_id=evidence_id,
    )
    # Identical retry (same stable evidence id): stored result, zero new rows.
    second = _record(
        env,
        project_id=project.id,
        run_id=run.run_id,
        summary="same summary",
        data={"a": 1},
        idempotency_key="evidence-replay",
        evidence_id=evidence_id,
    )
    assert second == first
    assert second.id == evidence_id
    assert _counts(env.writer) == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4],
        counts[5],
        counts[6] + 1,
    )

    # Changed request under the same key: mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _record(
            env,
            project_id=project.id,
            run_id=run.run_id,
            summary="a different summary",
            data={"a": 1},
            idempotency_key="evidence-replay",
        )
    assert _counts(env.writer) == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4],
        counts[5],
        counts[6] + 1,
    )


def test_record_statement_boundary_atomicity(tmp_path, core_registry) -> None:
    """Representative crash mid-record leaves the old (zero-row) state."""
    root = tmp_path / "evidence-crash"
    root.mkdir()
    env2 = _fresh_namespace(root, core_registry)
    try:
        project = _create_project(env2, project_id="crash-proj")
        run = _fanout(env2, project_id=project.id, children=[])
        counts_before = _counts(env2.writer)

        # Crash after the evidence_items INSERT; the whole command must
        # roll back (no row, no event, no receipt).
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="INSERT INTO evidence_items",
            fn=lambda u: env2.evidence_repo.record(
                u,
                project_id=project.id,
                run_id=run.run_id,
                kind="observation",
                summary="crashed mid-record",
                data={"x": 1},
                idempotency_key="evidence-crash-k",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == counts_before

        # Crash at commit: old-or-complete (never a half-committed row).
        outcome = _crash_run(
            env2.writer,
            kind="commit",
            sql_sub=None,
            fn=lambda u: env2.evidence_repo.record(
                u,
                project_id=project.id,
                run_id=run.run_id,
                kind="observation",
                summary="crashed at commit",
                data={"x": 2},
                idempotency_key="evidence-crash-k2",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        after = _counts(env2.writer)
        assert after in (counts_before, (counts_before[0], counts_before[1], counts_before[2] + 1, counts_before[3] + 1, counts_before[4], counts_before[5], counts_before[6] + 1))
    finally:
        env2.writer.close()


# ---------------------------------------------------------------------------
# list: immutable ordering and filters
# ---------------------------------------------------------------------------


def test_list_immutable_ordering_and_filters(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    child_a = generate_lowercase_ulid()
    run_a1 = _fanout(
        env,
        project_id=project_a.id,
        children=[_child(task_id=child_a)],
        idempotency_key="fanout-la1",
    )
    run_a2 = _fanout(
        env,
        project_id=project_a.id,
        children=[],
        idempotency_key="fanout-la2",
    )
    run_b = _fanout(
        env,
        project_id=project_b.id,
        children=[],
        idempotency_key="fanout-lb",
    )

    # run_a1: two observations at TS and TS+1 (both linked to the direct
    # child task); run_a2: one decision at TS.
    e_a1_1 = _record(
        env,
        project_id=project_a.id,
        run_id=run_a1.run_id,
        kind="observation",
        summary="first",
        data={"n": 1},
        task_id=child_a,
        idempotency_key="evidence-la1",
    )
    e_a1_2 = _record(
        env,
        project_id=project_a.id,
        run_id=run_a1.run_id,
        kind="observation",
        summary="second",
        data={"n": 2},
        task_id=child_a,
        idempotency_key="evidence-la2",
        created_at=TS2,
    )
    e_a2_1 = _record(
        env,
        project_id=project_a.id,
        run_id=run_a2.run_id,
        kind="decision",
        summary="decide",
        data={"n": 3},
        idempotency_key="evidence-la3",
    )
    _record(
        env,
        project_id=project_b.id,
        run_id=run_b.run_id,
        kind="error",
        summary="other project",
        data={"n": 4},
        idempotency_key="evidence-lb",
    )

    # Project-wide list: ordered by run_id, then created_at, then id.
    all_a = env.evidence_repo.list(env.writer, project_a.id)
    assert [r.id for r in all_a] == [e_a1_1.id, e_a1_2.id, e_a2_1.id]
    assert all(r.project_id == project_a.id for r in all_a)
    assert all(r.event_head_seq is not None for r in all_a)

    # Per-run filter: only run_a1's items, in created_at order.
    only_a1 = env.evidence_repo.list(env.writer, project_a.id, run_id=run_a1.run_id)
    assert [r.id for r in only_a1] == [e_a1_1.id, e_a1_2.id]

    # Per-task filter: only the item linked to the direct child.
    only_task = env.evidence_repo.list(
        env.writer, project_a.id, task_id=child_a
    )
    assert [r.id for r in only_task] == [e_a1_1.id, e_a1_2.id]

    # Other project stays isolated.
    only_b = env.evidence_repo.list(env.writer, project_b.id)
    assert len(only_b) == 1
    assert only_b[0].kind == "error"
    assert only_b[0].run_id == run_b.run_id


# ---------------------------------------------------------------------------
# run creation with ordered evidence (m3 plan step 4, T5)
# ---------------------------------------------------------------------------


def _receipt_events(writer: DatabaseWriter, project_id: str, key: str):
    """The ordered event ids stored on the run-create receipt."""
    receipt = _receipt_row(writer, project_id, key)
    assert receipt is not None
    return json.loads(receipt["event_ids_json"])


def test_run_create_with_ordered_evidence_zero_task_run(env) -> None:
    project = _create_project(env)
    counts = _counts(env.writer)

    result = _fanout(
        env,
        project_id=project.id,
        children=[],
        idempotency_key="run-ev-c1",
        evidence=[
            {
                "kind": "observation",
                "summary": "first observation",
                "data": {"n": 1},
            },
            {
                "kind": "measurement",
                "summary": "second measurement",
                "data": {"n": 2},
            },
            {
                "kind": "decision",
                "summary": "third decision",
                "data": {"n": 3},
            },
        ],
    )
    # Zero-task run: no task ids, ordered evidence ids in the receipt result.
    assert result.task_ids == ()
    assert result.first_ordinal == 0
    assert result.last_ordinal == -1
    assert len(result.evidence_ids) == 3
    assert result.evidence_ids[0] != result.evidence_ids[1]
    assert result.evidence_ids[1] != result.evidence_ids[2]

    # One run stream + one evidence row per entry; the run stream carried
    # the created event (seq 1) then the recorded events in submission
    # order (seqs 2..4).
    run_stream_id = f"{result.run_id}:{CORE_RUN_STREAM_TYPE}"
    events = _event_rows(env.writer, run_stream_id)
    assert [e["kind"] for e in events] == [
        "core.run.created",
        CORE_EVIDENCE_RECORDED_EVENT_KIND,
        CORE_EVIDENCE_RECORDED_EVENT_KIND,
        CORE_EVIDENCE_RECORDED_EVENT_KIND,
    ]
    for seq_index, evidence_id in enumerate(result.evidence_ids):
        data = json.loads(events[seq_index + 1]["payload_json"])["data"]
        assert data["evidence_id"] == evidence_id

    # The complete run receipt enumerates every ordered event id (created
    # first, then the recorded events in submission order) and returns the
    # ordered evidence ids.
    receipt = _receipt_row(env.writer, project.id, "run-ev-c1")
    assert receipt["command_kind"] == "core.run.create"
    assert receipt["resulting_stream_seq"] == 4
    stored_ids = json.loads(receipt["event_ids_json"])
    assert stored_ids[0] == events[0]["event_id"]
    assert [stored_ids[i] == events[i]["event_id"] for i in (1, 2, 3)]
    stored_result = json.loads(receipt["result_json"])
    assert stored_result["task_ids"] == []
    assert stored_result["evidence_ids"] == list(result.evidence_ids)

    # Every evidence entry also has its own core.evidence.record receipt.
    for index, evidence_id in enumerate(result.evidence_ids):
        ev_receipt = _receipt_row(
            env.writer, project.id, f"run-ev-c1:evidence:{index}"
        )
        assert ev_receipt["command_kind"] == CORE_EVIDENCE_RECORD_COMMAND_KIND
        assert json.loads(ev_receipt["result_json"])["id"] == evidence_id

    # Rows: +1 run, +0 tasks, +3 evidence; events: +4; receipts: +4
    # (one run create + three evidence records).
    assert _counts(env.writer) == (
        counts[0],
        counts[1] + 1,
        counts[2] + 4,
        counts[3] + 4,
        counts[4] + 1,
        counts[5],
        counts[6] + 3,
    )


def test_run_create_evidence_with_children_and_media(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-ev1")
    child_id = generate_lowercase_ulid()

    result = _fanout(
        env,
        project_id=project.id,
        children=[_child(task_id=child_id)],
        idempotency_key="run-ev-c2",
        evidence=[
            {
                "kind": "validation",
                "summary": "validated the child output",
                "data": {"ok": True},
                "task_id": child_id,
                "media_id": media.id,
            }
        ],
    )
    assert result.task_ids == (child_id,)
    assert len(result.evidence_ids) == 1

    # Receipt event order: run.created, child created, evidence recorded —
    # mirroring the write order (children first, then evidence) and the
    # project sequence range.
    stored_ids = _receipt_events(env.writer, project.id, "run-ev-c2")
    run_stream_id = f"{result.run_id}:{CORE_RUN_STREAM_TYPE}"
    run_events = _event_rows(env.writer, run_stream_id)
    child_stream_id = f"{child_id}:core.task"
    child_events = _event_rows(env.writer, child_stream_id)
    assert [e["kind"] for e in run_events] == [
        "core.run.created",
        CORE_EVIDENCE_RECORDED_EVENT_KIND,
    ]
    assert stored_ids == [
        run_events[0]["event_id"],
        child_events[0]["event_id"],
        run_events[1]["event_id"],
    ]
    # The evidence event's project sequence follows the child event.
    assert run_events[1]["project_seq"] > child_events[0]["project_seq"]

    row = _evidence_row(env.writer, result.evidence_ids[0])
    assert row["task_id"] == child_id
    assert row["media_id"] == media.id
    # The evidence vertical still validates the exact same-project media.
    listed = env.evidence_repo.list(
        env.writer, project.id, run_id=result.run_id, task_id=child_id
    )
    assert [r.id for r in listed] == [result.evidence_ids[0]]


def test_run_create_ordinary_fanout_preserves_empty_evidence_ids(env) -> None:
    project = _create_project(env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()

    result = _fanout(
        env,
        project_id=project.id,
        children=[_child(task_id=child_a), _child(task_id=child_b)],
        idempotency_key="run-ev-c3",
    )
    assert result.task_ids == (child_a, child_b)
    assert result.evidence_ids == ()

    receipt = _receipt_row(env.writer, project.id, "run-ev-c3")
    assert json.loads(receipt["result_json"])["evidence_ids"] == []
    assert receipt["resulting_stream_seq"] == 1
    # Only the created event: no evidence event on the run stream.
    run_stream_id = f"{result.run_id}:{CORE_RUN_STREAM_TYPE}"
    events = _event_rows(env.writer, run_stream_id)
    assert [e["kind"] for e in events] == ["core.run.created"]


def test_run_create_evidence_replay_and_mismatch(env) -> None:
    project = _create_project(env)
    counts = _counts(env.writer)
    evidence_id = generate_lowercase_ulid()
    run_id = generate_lowercase_ulid()
    entry = {
        "kind": "error",
        "summary": "the same error",
        "data": {"code": 42},
        "evidence_id": evidence_id,
    }

    first = _fanout(
        env,
        project_id=project.id,
        children=[],
        idempotency_key="run-ev-replay",
        run_id=run_id,
        evidence=[entry],
    )
    # Identical retry under the same run key and stable run id: stored
    # result, zero new rows.
    second = _fanout(
        env,
        project_id=project.id,
        children=[],
        idempotency_key="run-ev-replay",
        run_id=run_id,
        evidence=[entry],
    )
    assert second == first
    assert second.evidence_ids == (evidence_id,)
    assert _counts(env.writer) == (
        counts[0],
        counts[1] + 1,
        counts[2] + 2,
        counts[3] + 2,
        counts[4] + 1,
        counts[5],
        counts[6] + 1,
    )

    # Changed evidence under the same run key: mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _fanout(
            env,
            project_id=project.id,
            children=[],
            idempotency_key="run-ev-replay",
            run_id=run_id,
            evidence=[{**entry, "summary": "a different error"}],
        )
    assert _counts(env.writer) == (
        counts[0],
        counts[1] + 1,
        counts[2] + 2,
        counts[3] + 2,
        counts[4] + 1,
        counts[5],
        counts[6] + 1,
    )


def test_run_create_evidence_rejects_bad_entries_before_any_write(env) -> None:
    project = _create_project(env)
    counts = _counts(env.writer)

    with pytest.raises(RunValidationError):
        _fanout(
            env,
            project_id=project.id,
            children=[],
            idempotency_key="run-ev-badkind",
            evidence=[{"kind": "opinion", "summary": "nope"}],
        )
    with pytest.raises(RunValidationError):
        _fanout(
            env,
            project_id=project.id,
            children=[],
            idempotency_key="run-ev-badsummary",
            evidence=[{"kind": "error", "summary": "   "}],
        )
    with pytest.raises(RunValidationError):
        _fanout(
            env,
            project_id=project.id,
            children=[],
            idempotency_key="run-ev-baddata",
            evidence=[{"kind": "error", "summary": "s", "data": [1, 2]}],
        )
    with pytest.raises(RunValidationError):
        _fanout(
            env,
            project_id=project.id,
            children=[],
            idempotency_key="run-ev-notentry",
            evidence=["not-an-object"],
        )
    assert _counts(env.writer) == counts


def test_run_create_evidence_cross_row_validation_rolls_back(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    media_b = _import_media(
        env, project_id=project_b.id, idempotency_key="import-ev2"
    )
    counts = _counts(env.writer)

    # Foreign media for the run's project: the evidence vertical rejects it
    # inside the same transaction, so the whole run create rolls back.
    with pytest.raises(EvidenceValidationError) as excinfo:
        _fanout(
            env,
            project_id=project_a.id,
            children=[],
            idempotency_key="run-ev-foreignmedia",
            evidence=[
                {"kind": "observation", "summary": "s", "media_id": media_b.id}
            ],
        )
    assert excinfo.value.detail == "foreign_media"
    assert _counts(env.writer) == counts

    # A task that is not a direct child of the new run: not_direct_child,
    # and the run (plus its stream/event) rolls back too.
    other_run = _fanout(env, project_id=project_a.id, children=[])
    other_child = _fanout(
        env,
        project_id=project_a.id,
        children=[_child()],
        idempotency_key="fanout-ev3",
    )
    foreign_child_id = other_child.task_ids[0]
    before = _counts(env.writer)
    with pytest.raises(EvidenceValidationError) as excinfo:
        _fanout(
            env,
            project_id=project_a.id,
            children=[],
            idempotency_key="run-ev-notchild",
            evidence=[
                {
                    "kind": "observation",
                    "summary": "s",
                    "task_id": foreign_child_id,
                }
            ],
        )
    assert excinfo.value.detail == "not_direct_child"
    assert _counts(env.writer) == before
    assert other_run.run_id != foreign_child_id


def test_run_create_evidence_statement_boundary_rollback(
    tmp_path, core_registry
) -> None:
    """A crash at any statement boundary leaves the old (zero-row) state."""
    root = tmp_path / "run-ev-crash"
    root.mkdir()
    env2 = _fresh_namespace(root, core_registry)
    try:
        project = _create_project(env2)
        counts_before = _counts(env2.writer)
        entry = {"kind": "observation", "summary": "crashed", "data": {"x": 1}}

        # Crash right after the runs-row INSERT (the run stream exists in
        # the transaction but nothing may persist).
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="INSERT INTO runs",
            fn=lambda u: env2.run_repo.create(
                u,
                project_id=project.id,
                children=[],
                evidence=[entry],
                idempotency_key="run-ev-crash1",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == counts_before

        # Crash right after the evidence_items INSERT: the run row, stream,
        # events, and receipts must all roll back together.
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="INSERT INTO evidence_items",
            fn=lambda u: env2.run_repo.create(
                u,
                project_id=project.id,
                children=[],
                evidence=[entry],
                idempotency_key="run-ev-crash2",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == counts_before

        # Crash at commit: old-or-complete (either the old zero-row state or
        # the fully committed run + evidence, never a half-committed row).
        outcome = _crash_run(
            env2.writer,
            kind="commit",
            sql_sub=None,
            fn=lambda u: env2.run_repo.create(
                u,
                project_id=project.id,
                children=[],
                evidence=[entry],
                idempotency_key="run-ev-crash3",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        after = _counts(env2.writer)
        committed = (
            counts_before[0],
            counts_before[1] + 1,
            counts_before[2] + 2,
            counts_before[3] + 2,
            counts_before[4] + 1,
            counts_before[5],
            counts_before[6] + 1,
        )
        assert after in (counts_before, committed)
    finally:
        env2.writer.close()
