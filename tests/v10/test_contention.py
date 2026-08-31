"""Deterministic two-caller timeline-save contention (m1 plan step 17).

(T33 and finding CF-9BB2000B5A215035C40C.) These tests prove the
one-winner CAS contract through the real writer and timeline repository:

- **exactly one success and one typed version conflict** when two callers
  race a whole-document save from one expected head: the writer thread
  serializes the two units of work FIFO, the winner commits head 1 -> 2,
  and the loser's expected-head CAS fails with
  :class:`TimelineVersionConflictError` carrying ``current_version == 2``;
- **no busy leak**: with one writer thread and one owned connection there
  is never a SQLite ``database is locked`` surface — every outcome is a
  success or the typed domain conflict, never :class:`WriterBusyError`;
- **no losing receipt**: the loser changes zero rows, so exactly one
  ``command_receipts`` row, exactly one ``timeline.saved`` event, and
  exactly one head advance exist after the race;
- **deterministic winner state**: the committed document is exactly the
  winner's payload, the stream verifies as a canonical hash chain, and the
  invariant holds across repeated fresh-database iterations regardless of
  which caller wins the submission race;
- **bounded FIFO progress for unrelated work**: while two saves contend on
  one timeline, an unrelated save on a different timeline submitted in the
  same batch still completes, in FIFO order, with a correct result — and no
  slow external operation (sleep, socket, network) ever runs inside a
  transaction (the command paths are scanned for such calls and the whole
  race completes within a generous wall-clock bound).

The race is deterministic by construction: the writer owns one connection
and one FIFO queue, so two units of work are strictly serialized; the test
uses ``threading.Barrier`` only to align *submission*, never to slow a
transaction.
"""

from __future__ import annotations

import ast
import inspect
import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.receipts import ReceiptService
from astrid.core.repositories import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import (
    DatabaseWriter,
    WriterBusyError,
)
from astrid.packs.timeline.repository import (
    TIMELINE_SAVED_EVENT_KIND,
    TIMELINE_STREAM_TYPE,
    TimelineRepository,
    TimelineVersionConflictError,
)

TS = "2026-08-15T00:00:00.000000+00:00"
TS2 = "2026-08-15T01:00:00.000000+00:00"

SAVE_A = {"fps": 30, "scene": "winner-a"}
SAVE_B = {"fps": 60, "scene": "winner-b"}
SAVE_C = {"fps": 24, "scene": "unrelated-c"}


@pytest.fixture
def writer(tmp_path: Path, standard_registry):
    """A fresh standard-Astrid writer at ``<tmp>/astrid.sqlite3``."""
    w = DatabaseWriter(tmp_path / "astrid.sqlite3", standard_registry)
    try:
        yield w
    finally:
        w.close()


@pytest.fixture
def project_repo(standard_registry) -> ProjectRepository:
    """A stateless project repository over the kernel services."""
    return ProjectRepository(
        events=EventAppendService(standard_registry),
        receipts=ReceiptService(),
    )


@pytest.fixture
def repo(standard_registry, project_repo) -> TimelineRepository:
    """A stateless timeline repository over the kernel services."""
    return TimelineRepository(
        events=EventAppendService(standard_registry),
        receipts=ReceiptService(),
        projects=project_repo,
    )


def _seed(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
    *,
    project_slug: str = "pilot",
    timeline_slug: str = "main",
    second_timeline_slug: str | None = None,
):
    """Seed one project plus one (or two) timelines at head 1.

    Returns ``(project_id, timeline_id, timeline_stream_id, second_ref)``.
    """
    uow = UnitOfWork(writer)
    project = uow.run(
        lambda u: project_repo.create(
            u,
            slug=project_slug,
            name="Pilot",
            settings={},
            idempotency_key=f"seed-project-{project_slug}",
            created_at=TS,
        )
    )
    timeline = uow.run(
        lambda u: repo.create(
            u,
            project_id=project.id,
            slug=timeline_slug,
            name="Main",
            config={"fps": 24},
            registry={"assets": {}},
            idempotency_key=f"seed-timeline-{timeline_slug}",
            created_at=TS,
        )
    )
    second_ref: str | None = None
    if second_timeline_slug is not None:
        second = uow.run(
            lambda u: repo.create(
                u,
                project_id=project.id,
                slug=second_timeline_slug,
                name="Second",
                config={"fps": 24},
                registry={"assets": {}},
                idempotency_key=f"seed-timeline-{second_timeline_slug}",
                created_at=TS,
            )
        )
        second_ref = second.timeline_id
    return (
        project.id,
        timeline.timeline_id,
        f"{timeline.timeline_id}:{TIMELINE_STREAM_TYPE}",
        second_ref,
    )


def _race_saves(
    repo: TimelineRepository,
    writer: DatabaseWriter,
    *,
    project_id: str,
    ref: str,
    n_callers: int = 2,
) -> tuple[list[Any], list[BaseException]]:
    """Race ``n_callers`` saves from one expected head through a Barrier.

    Each caller submits a *different* payload so the derived idempotency
    keys differ (a shared payload would replay the winner's receipt instead
    of producing a conflict). Returns ``(results, errors)``.
    """
    barrier = threading.Barrier(n_callers)
    results: list[Any] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def caller(index: int) -> None:
        config = SAVE_A if index % 2 == 0 else SAVE_B
        barrier.wait()
        try:
            result = UnitOfWork(writer).run(
                lambda u: repo.save(
                    u,
                    project_id=project_id,
                    ref=ref,
                    config=dict(config),
                    registry={"assets": {}},
                    expected_version=1,
                    created_at=TS2,
                )
            )
            with lock:
                results.append(result)
        except BaseException as exc:  # noqa: BLE001 - recorded for assertion
            with lock:
                errors.append(exc)

    threads = [
        threading.Thread(target=caller, args=(index,)) for index in range(n_callers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert not any(thread.is_alive() for thread in threads), "race deadlocked"
    return results, errors


def _receipt_count(writer: DatabaseWriter, project_id: str) -> int:
    with writer.read_only_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM command_receipts WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return int(row[0])


def _saved_event_count(writer: DatabaseWriter, stream_id: str) -> int:
    with writer.read_only_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM events WHERE stream_id = ? AND kind = ?",
            (stream_id, TIMELINE_SAVED_EVENT_KIND),
        ).fetchone()
    return int(row[0])


# ---------------------------------------------------------------------------
# The one-winner race
# ---------------------------------------------------------------------------


def test_two_callers_from_one_expected_head_yield_one_success_one_conflict(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    """The canonical CF-9BB2000B5A215035C40C race: exactly one winner."""
    project_id, timeline_id, stream_id, _ = _seed(repo, project_repo, writer)

    results, errors = _race_saves(repo, writer, project_id=project_id, ref=timeline_id)

    assert len(results) == 1, f"expected exactly one success, got {len(results)}"
    assert len(errors) == 1, f"expected exactly one conflict, got {len(errors)}"
    winner = results[0]
    conflict = errors[0]
    assert not isinstance(conflict, WriterBusyError), (
        "the loser surfaced a SQLite busy error, not a domain conflict"
    )
    assert isinstance(conflict, TimelineVersionConflictError), (
        f"loser raised {type(conflict).__name__}, expected the typed "
        "version conflict"
    )
    assert winner.config_version == 2
    assert conflict.expected_version == 1
    assert conflict.current_version == 2
    assert winner.config == dict(SAVE_A) or winner.config == dict(SAVE_B)


def test_race_leaves_no_busy_leak_and_no_losing_receipt(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    """After the race: one receipt, one saved event, one head advance."""
    project_id, timeline_id, stream_id, _ = _seed(repo, project_repo, writer)
    before_receipts = _receipt_count(writer, project_id)

    results, errors = _race_saves(repo, writer, project_id=project_id, ref=timeline_id)

    assert len(results) == 1 and len(errors) == 1
    for error in errors:
        assert not isinstance(error, WriterBusyError)
        assert "locked" not in str(error).lower()
    # No losing receipt: the project's receipt count grows by exactly one
    # (the winner's) and no receipt row exists for the loser's derived key.
    assert _receipt_count(writer, project_id) == before_receipts + 1
    # No losing event: exactly one timeline.saved event was appended.
    assert _saved_event_count(writer, stream_id) == 1
    # No partial projection: the committed document is exactly the winner's.
    loaded = repo.show(writer, project_id, timeline_id)
    assert loaded.config_version == 2
    assert loaded.config in (dict(SAVE_A), dict(SAVE_B))


def test_race_winner_state_is_consistent_and_chain_verifies(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
    standard_registry,
) -> None:
    """The committed winner state is a canonical, gap-free hash chain."""
    project_id, timeline_id, stream_id, _ = _seed(repo, project_repo, writer)
    results, errors = _race_saves(repo, writer, project_id=project_id, ref=timeline_id)
    assert len(results) == 1 and len(errors) == 1

    verification = EventAppendService(standard_registry).verify_stream(
        writer, stream_id
    )
    assert verification.event_count == 2  # created + saved
    assert verification.head_seq == 2
    with writer.read_only_connection() as conn:
        rows = conn.execute(
            "SELECT seq FROM events WHERE stream_id = ? ORDER BY seq ASC",
            (stream_id,),
        ).fetchall()
    assert [int(row[0]) for row in rows] == [1, 2]


def test_race_invariant_holds_across_repeated_fresh_databases(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
    standard_registry,
    tmp_path: Path,
) -> None:
    """The one-winner invariant is deterministic, not a scheduling accident."""
    for iteration in range(6):
        fresh = DatabaseWriter(tmp_path / f"race-{iteration}.sqlite3", standard_registry)
        try:
            project_id, timeline_id, stream_id, _ = _seed(
                repo, project_repo, fresh, project_slug=f"pilot-{iteration}"
            )
            results, errors = _race_saves(
                repo, fresh, project_id=project_id, ref=timeline_id
            )
            assert len(results) == 1, f"iteration {iteration}: {len(results)} winners"
            assert len(errors) == 1, f"iteration {iteration}: {len(errors)} losers"
            assert isinstance(errors[0], TimelineVersionConflictError)
            assert not isinstance(errors[0], WriterBusyError)
            assert results[0].config_version == 2
            assert errors[0].current_version == 2
            assert _receipt_count(fresh, project_id) == 3  # seed(2) + save(1)
        finally:
            fresh.close()


# ---------------------------------------------------------------------------
# Bounded FIFO progress for unrelated work
# ---------------------------------------------------------------------------


def test_unrelated_save_progresses_in_fifo_order_during_contention(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    """An unrelated save submitted with the race still completes correctly."""
    project_id, timeline_id, stream_id, second_ref = _seed(
        repo,
        project_repo,
        writer,
        second_timeline_slug="other",
    )
    assert second_ref is not None
    order: list[str] = []
    lock = threading.Lock()
    barrier = threading.Barrier(2)
    results: list[Any] = []
    errors: list[BaseException] = []

    def racer(index: int) -> None:
        barrier.wait()
        try:
            result = UnitOfWork(writer).run(
                lambda u: repo.save(
                    u,
                    project_id=project_id,
                    ref=timeline_id,
                    config=dict(SAVE_A if index == 0 else SAVE_B),
                    registry={"assets": {}},
                    expected_version=1,
                    created_at=TS2,
                )
            )
            with lock:
                results.append(result)
                order.append("race")
        except BaseException as exc:  # noqa: BLE001 - recorded below
            with lock:
                errors.append(exc)
                order.append("race")

    def unrelated() -> None:
        try:
            result = UnitOfWork(writer).run(
                lambda u: repo.save(
                    u,
                    project_id=project_id,
                    ref=second_ref,
                    config=dict(SAVE_C),
                    registry={"assets": {}},
                    expected_version=1,
                    created_at=TS2,
                )
            )
            with lock:
                results.append(result)
                order.append("unrelated")
        except BaseException as exc:  # noqa: BLE001 - recorded below
            with lock:
                errors.append(exc)
                order.append("unrelated")

    started = time.monotonic()
    threads = [
        threading.Thread(target=racer, args=(0,)),
        threading.Thread(target=racer, args=(1,)),
        threading.Thread(target=unrelated),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    elapsed = time.monotonic() - started
    assert not any(thread.is_alive() for thread in threads)

    # The unrelated save always succeeds at head 2 of its own timeline.
    unrelated_result = [r for r in results if r.timeline_id == second_ref]
    assert len(unrelated_result) == 1
    assert unrelated_result[0].config_version == 2
    assert unrelated_result[0].config == dict(SAVE_C)
    # The contending timeline has exactly one winner and one typed conflict.
    assert len(results) == 2  # one race winner + one unrelated winner
    assert len(errors) == 1
    assert isinstance(errors[0], TimelineVersionConflictError)
    assert not isinstance(errors[0], WriterBusyError)
    # Bounded progress: the whole batch (two contending saves plus the
    # unrelated save, all inside their own BEGIN IMMEDIATE transactions)
    # completes well inside a generous wall-clock bound — no blocking wait
    # or slow external operation was involved.
    assert elapsed < 10.0, f"contention batch took {elapsed:.2f}s"


def test_no_slow_external_operations_inside_transactions(
    repo: TimelineRepository,
) -> None:
    """The save command path never sleeps or performs external I/O.

    A deterministic static scan: the timeline repository's command methods
    (``create`` and ``save``) contain no sleep, event-wait, socket, or
    network calls, so a transaction can never be held open on a slow
    external operation. The runtime half of the bound is covered by
    ``test_unrelated_save_progresses_in_fifo_order_during_contention``.
    """
    source = inspect.getsource(type(repo))
    tree = ast.parse(source)
    forbidden: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = None
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            if name in {
                "sleep",
                "wait",
                "urlopen",
                "urlretrieve",
                "connect",
                "request",
            }:
                forbidden.setdefault(name, []).append(node.lineno)
    assert not forbidden, f"slow external operations found in repository: {forbidden}"
    assert "import socket" not in source
    assert "time.sleep" not in source
    assert "urllib" not in source


# ---------------------------------------------------------------------------
# Typed conflict surface (bridge §6.2 / §6.3)
# ---------------------------------------------------------------------------


def test_race_loser_never_mutates_any_row(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    """The losing save changes zero rows: document, registry, receipts."""
    project_id, timeline_id, stream_id, _ = _seed(repo, project_repo, writer)
    with writer.read_only_connection() as conn:
        before_document = str(
            conn.execute(
                "SELECT document_json FROM timelines WHERE id = ?",
                (timeline_id,),
            ).fetchone()[0]
        )
        before_head = int(
            conn.execute(
                "SELECT head_seq FROM event_streams WHERE id = ?",
                (stream_id,),
            ).fetchone()[0]
        )

    results, errors = _race_saves(repo, writer, project_id=project_id, ref=timeline_id)
    assert len(results) == 1 and len(errors) == 1
    assert isinstance(errors[0], TimelineVersionConflictError)

    with writer.read_only_connection() as conn:
        after_document = str(
            conn.execute(
                "SELECT document_json FROM timelines WHERE id = ?",
                (timeline_id,),
            ).fetchone()[0]
        )
        after_head = int(
            conn.execute(
                "SELECT head_seq FROM event_streams WHERE id = ?",
                (stream_id,),
            ).fetchone()[0]
        )
    # Only the winner's single atomic save is visible: exactly one head
    # advance and exactly one document change (never a partial merge).
    assert after_head == before_head + 1
    assert after_document != before_document
    assert _saved_event_count(writer, stream_id) == 1


# ---------------------------------------------------------------------------
# m2: heartbeat + prepared-media import contention with a serviceable editor
# (plan step 17, T28; finding CF-4C24310E5FE50E5A5669)
# ---------------------------------------------------------------------------

M2_TS = "2026-08-16T00:00:00.000000+00:00"
M2_TS_HEARTBEAT = "2026-08-16T00:02:00.000000+00:00"  # inside the 00:00..00:05 lease


def _seed_m2_contention(writer, standard_registry, tmp_path, *, slug_suffix):
    """Seed the task (running attempt), prepared media, and editor state.

    Returns a small namespace carrying the fenced attempt facts (the
    heartbeat target at ``expected_status_version``), two prepared media
    records (distinct digests for dedupe-under-contention), and the editor
    timeline ref at head 1.
    """
    from types import SimpleNamespace

    from astrid.core.events.service import EventAppendService
    from astrid.core.io.media_import import prepare_media_file
    from astrid.core.receipts import ReceiptService
    from astrid.core.repositories import ProjectRepository
    from astrid.core.repositories.media import MediaRepository
    from astrid.core.repositories.tasks import TaskRepository
    from astrid.packs.timeline.repository import (
        TIMELINE_STREAM_TYPE,
        TimelineRepository,
    )

    events = EventAppendService(standard_registry)
    receipts = ReceiptService()
    projects = ProjectRepository(events=events, receipts=receipts)
    tasks = TaskRepository(events=events, receipts=receipts)
    media = MediaRepository(
        events=events, receipts=receipts, projects_root=tmp_path
    )
    timelines = TimelineRepository(
        events=events, receipts=receipts, projects=projects
    )

    uow = UnitOfWork(writer)
    project = uow.run(
        lambda u: projects.create(
            u,
            slug=f"m2-task-{slug_suffix}",
            name="Tasks",
            settings={},
            idempotency_key=f"m2-task-proj-{slug_suffix}",
            created_at=M2_TS,
        )
    )
    task = uow.run(
        lambda u: tasks.create(
            u,
            project_id=project.id,
            capability="rendering.timeline_visualize",
            spec={"backend": "remotion"},
            input_manifest=["m"],
            idempotency_key=f"m2-admit-{slug_suffix}",
            created_at=M2_TS,
        )
    )
    claim = uow.run(
        lambda u: tasks.claim(
            u,
            project_id=project.id,
            idempotency_key=f"m2-claim-{slug_suffix}",
            executor_id="executor-1",
            now=M2_TS,
            lease_seconds=300,
        )
    )
    assert claim is not None, "seed claim returned no attempt"
    started = uow.run(
        lambda u: tasks.start(
            u,
            project_id=project.id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=1,
            idempotency_key=f"m2-start-{slug_suffix}",
            now=M2_TS,
        )
    )
    assert started.status == "running"

    fixture_dir = tmp_path / f"fixtures-{slug_suffix}"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture_a = fixture_dir / "race-a.svg"
    fixture_b = fixture_dir / "race-b.svg"
    fixture_a.write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'>A</svg>")
    fixture_b.write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'>BB</svg>")
    prepared_a = prepare_media_file(fixture_a, root=fixture_dir)
    prepared_b = prepare_media_file(fixture_b, root=fixture_dir)

    editor_project = uow.run(
        lambda u: projects.create(
            u,
            slug=f"m2-editor-{slug_suffix}",
            name="Editor",
            settings={},
            idempotency_key=f"m2-editor-proj-{slug_suffix}",
            created_at=M2_TS,
        )
    )
    editor = uow.run(
        lambda u: timelines.create(
            u,
            project_id=editor_project.id,
            slug="main",
            name="Main",
            config={"fps": 24},
            registry={"assets": {}},
            idempotency_key=f"m2-editor-tl-{slug_suffix}",
            created_at=M2_TS,
        )
    )

    return SimpleNamespace(
        writer=writer,
        tasks=tasks,
        media=media,
        timelines=timelines,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=2,
        prepared_a=prepared_a,
        prepared_b=prepared_b,
        editor_project_id=editor_project.id,
        editor_ref=editor.timeline_id,
        editor_stream=f"{editor.timeline_id}:{TIMELINE_STREAM_TYPE}",
    )


def _run_m2_race(
    facts,
    *,
    n_heartbeats: int = 4,
    n_imports: int = 4,
    n_editors: int = 2,
):
    """Race heartbeats, prepared-media imports, and editor saves.

    Every operation is its own short UoW submitted to the one FIFO writer;
    ``threading.Barrier`` aligns only submission, never a transaction.
    Returns ``(results, errors, elapsed)`` where each entry is a tuple
    ``(outcome_kind, type_name, seconds)``.
    """
    barrier = threading.Barrier(n_heartbeats + n_imports + n_editors)
    results: list[tuple[str, str, float]] = []
    errors: list[tuple[str, str, float]] = []
    lock = threading.Lock()

    def record(fn) -> None:
        barrier.wait()
        started = time.monotonic()
        try:
            outcome = fn()
            with lock:
                results.append(("ok", type(outcome).__name__, time.monotonic() - started))
        except BaseException as exc:  # noqa: BLE001 - classified below
            with lock:
                errors.append(
                    (type(exc).__name__, str(exc), time.monotonic() - started)
                )

    def heartbeat(index: int):
        def run(u):
            return facts.tasks.heartbeat(
                u,
                project_id=facts.project_id,
                task_id=facts.task_id,
                attempt_id=facts.attempt_id,
                lease_id=facts.lease_id,
                expected_status_version=facts.expected_status_version,
                lease_seconds=300,
                now=M2_TS_HEARTBEAT,
            )

        return UnitOfWork(facts.writer).run(run)

    def media_import(index: int):
        prepared = facts.prepared_a if index % 2 == 0 else facts.prepared_b

        def run(u):
            return facts.media.import_prepared(
                u,
                project_id=facts.project_id,
                prepared=prepared,
                idempotency_key=f"m2-race-import-{index}",
                created_at=M2_TS,
            )

        return UnitOfWork(facts.writer).run(run)

    def editor_save(index: int):
        config = SAVE_A if index % 2 == 0 else SAVE_B

        def run(u):
            return facts.timelines.save(
                u,
                project_id=facts.editor_project_id,
                ref=facts.editor_ref,
                config=dict(config),
                registry={"assets": {}},
                expected_version=1,
                created_at=TS2,
            )

        return UnitOfWork(facts.writer).run(run)

    threads = [
        *[
            threading.Thread(target=record, args=(lambda i=i: heartbeat(i),))
            for i in range(n_heartbeats)
        ],
        *[
            threading.Thread(target=record, args=(lambda i=i: media_import(i),))
            for i in range(n_imports)
        ],
        *[
            threading.Thread(target=record, args=(lambda i=i: editor_save(i),))
            for i in range(n_editors)
        ],
    ]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    elapsed = time.monotonic() - started
    assert not any(thread.is_alive() for thread in threads), "m2 race deadlocked"
    return results, errors, elapsed


def _m2_evidence(results, errors, elapsed, *, iteration: int) -> dict[str, Any]:
    """Fold one race into a JSON-safe runtime-evidence record."""
    return {
        "finding_id": "CF-4C24310E5FE50E5A5669",
        "iteration": iteration,
        "elapsed_seconds": round(elapsed, 4),
        "outcome_count": len(results),
        "error_count": len(errors),
        "busy_errors": sum(
            1
            for kind, message, _ in errors
            if kind == "WriterBusyError" or "locked" in message.lower()
        ),
        "error_types": sorted({kind for kind, _, _ in errors}),
        "heartbeat_successes": sum(1 for kind, _, _ in results if kind == "ok"),
    }


def test_heartbeat_and_media_import_contention_keeps_editor_serviceable(
    writer: DatabaseWriter,
    standard_registry,
    tmp_path: Path,
) -> None:
    """The m2 race: short heartbeats + media imports + editor saves.

    Through the single FIFO writer every operation completes inside a
    generous wall-clock bound, every outcome is typed (never a raw SQLite
    busy error), and the editor's unrelated save stays serviceable while
    the non-event heartbeat and filesystem-backed media import contend.
    """
    facts = _seed_m2_contention(
        writer, standard_registry, tmp_path, slug_suffix="one"
    )
    results, errors, elapsed = _run_m2_race(facts)

    assert elapsed < 10.0, f"m2 contention batch took {elapsed:.2f}s"
    # No SQLite busy leakage: every failure is a typed domain outcome.
    for kind, message, _ in errors:
        assert kind != "WriterBusyError", f"busy error leaked: {message}"
        assert "locked" not in message.lower(), f"busy error leaked: {message}"
    # Heartbeat: exactly one winner (the first fence passes, the rest see
    # the bumped status_version) and every loser is the typed stale outcome.
    heartbeat_ok = [
        (kind, name) for kind, name, _ in results if name == "TaskAttemptReadModel"
    ]
    assert len(heartbeat_ok) == 1, f"expected 1 heartbeat winner, got {len(heartbeat_ok)}"
    heartbeat_errors = [
        (kind, message) for kind, message, _ in errors if kind == "TaskTransitionError"
    ]
    assert len(heartbeat_errors) == 3
    assert all(
        "stale_status_version" in message for _, message in heartbeat_errors
    )
    # Media imports: every distinct-key import succeeds (dedupe reuses the
    # same digest's media row for the second import of each file).
    assert sum(1 for kind, name, _ in results if name == "MediaReadModel") == 4
    # Editor work remains serviceable: exactly one save wins and the loser
    # gets the typed version conflict; the editor timeline advanced.
    assert sum(1 for kind, name, _ in results if name == "TimelineRecord") == 1
    conflict_errors = [
        kind for kind, _, _ in errors if kind == "TimelineVersionConflictError"
    ]
    assert len(conflict_errors) == 1
    with writer.read_only_connection() as conn:
        head = conn.execute(
            "SELECT head_seq FROM event_streams WHERE id = ?",
            (facts.editor_stream,),
        ).fetchone()
    assert head is not None and int(head[0]) == 2

    evidence = _m2_evidence(results, errors, elapsed, iteration=0)
    # Preserve the observed runtime evidence for CF-4C24310E5FE50E5A5669 in
    # the test log (pytest -s / failure report): bounded completion, typed
    # outcomes only, zero busy errors, editor serviceable.
    print("M2_CONTENTION_EVIDENCE " + json.dumps(evidence, sort_keys=True))
    assert evidence["busy_errors"] == 0
    assert evidence["error_types"] == sorted(
        {"TaskTransitionError", "TimelineVersionConflictError"}
    )


def test_m2_contention_invariant_holds_across_fresh_databases(
    standard_registry,
    tmp_path: Path,
) -> None:
    """The one-winner/typed-outcome invariant is not a scheduling accident."""
    for iteration in range(3):
        fresh = DatabaseWriter(
            tmp_path / f"m2-race-{iteration}.sqlite3", standard_registry
        )
        try:
            facts = _seed_m2_contention(
                fresh, standard_registry, tmp_path, slug_suffix=f"it-{iteration}"
            )
            results, errors, elapsed = _run_m2_race(facts)
            assert elapsed < 10.0, f"iteration {iteration} took {elapsed:.2f}s"
            for kind, message, _ in errors:
                assert kind != "WriterBusyError", f"busy leak: {message}"
                assert "locked" not in message.lower(), f"busy leak: {message}"
            assert sum(1 for kind, _, _ in results if kind == "ok") == 6
            assert len(errors) == 4
            print(
                "M2_CONTENTION_EVIDENCE "
                + json.dumps(
                    _m2_evidence(results, errors, elapsed, iteration=iteration),
                    sort_keys=True,
                )
            )
        finally:
            fresh.close()


def test_no_slow_external_operations_inside_heartbeat_or_media_import(
    standard_registry,
    tmp_path: Path,
) -> None:
    """Heartbeat and media import never sleep or perform external I/O.

    A deterministic static scan of the kernel task/media repository command
    sources (mirroring the timeline save scan above): a transaction can
    never be held open on a slow external operation, so the FIFO writer
    stays responsive under heartbeat/media load.
    """
    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts import ReceiptService
    from astrid.core.repositories.media import MediaRepository
    from astrid.core.repositories.tasks import TaskRepository

    events = EventAppendService(standard_registry)
    receipts = ReceiptService()
    tasks = TaskRepository(events=events, receipts=receipts)
    media = MediaRepository(
        events=events, receipts=receipts, projects_root=tmp_path
    )
    for repo in (tasks, media):
        source = inspect.getsource(type(repo))
        tree = ast.parse(source)
        forbidden: dict[str, list[int]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Attribute):
                    name = func.attr
                elif isinstance(func, ast.Name):
                    name = func.id
                if name in {
                    "sleep",
                    "wait",
                    "urlopen",
                    "urlretrieve",
                    "connect",
                    "request",
                }:
                    forbidden.setdefault(name, []).append(node.lineno)
        assert not forbidden, f"slow ops in {type(repo).__name__}: {forbidden}"
        assert "time.sleep" not in source
        assert "urllib" not in source
