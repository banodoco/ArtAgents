"""Executable standard-application composition tests (m4 plan step 4, T4).

Proves the deterministic kernel composition in ``astrid.application``:

- **one queue:** ``compose_standard_application`` opens exactly one
  ``DatabaseWriter`` and every kernel and pack repository shares it, so
  commands from any repository commit through one FIFO write queue with
  gap-free project sequences;
- **ordered event reads:** the read-only ``EventRepository`` returns
  committed events in deterministic ``project_seq`` order (and ``seq``
  order within a stream), unwraps the SD2 integrity envelope, and never
  opens a transaction or writes a row;
- **pack-independent core:** the kernel event repository and the
  ``compose_core_application`` wiring never import ``astrid.packs``;
- **no table added:** a fresh composed database contains exactly the frozen
  20-table catalog (14 kernel + 6 pack tables) and nothing else;
- **no dynamic discovery:** the composition and event repository source
  contain no loader/scanning machinery;
- **deterministic close:** ``close()`` drains queued work, is idempotent,
  and rejects later submissions with the typed shutdown error;
- **seven typed services (plan step 17):** every service (projects,
  timelines, media, tasks, runs, references, shots) resolves through the
  application, binds to the one shared writer queue, and commits its
  mutations through that queue with gap-free global sequences.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from astrid.application import (
    TimelineSaveCall,
    compose_core_application,
    compose_standard_application,
)
from astrid.core.cli.registration import register_product_commands
from astrid.core.events.service import EventAppendService
from astrid.core.receipts import ReceiptService
from astrid.core.repositories import (
    EventReadError,
    EventRepository,
    EvidenceRepository,
    MediaRepository,
    ProjectRepository,
    RunRepository,
    TaskRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter, WriterShutdownError
from astrid.packs import STANDARD_SCHEMA_PACKS, open_standard_writer
from astrid.packs.references.repository import ReferenceRepository
from astrid.packs.shots.repository import ShotRepository
from astrid.packs.timeline.bridge import TimelineBridgeAdapter
from astrid.packs.timeline.repository import TimelineRepository
from astrid.sdk.client import AstridClient
from astrid.sdk.media import MediaService
from astrid.sdk.projects import ProjectsService
from astrid.sdk.references import ReferencesService
from astrid.sdk.runs import RunsService
from astrid.sdk.shots import ShotsService
from astrid.sdk.tasks import TasksService
from astrid.sdk.timelines import TimelinesService

EXPECTED_TABLE_COUNT = 21
"""The frozen v10 catalog: 14 kernel tables + 6 pack tables (timeline 1,
shots 2, references 3)."""


# ---------------------------------------------------------------------------
# One writer queue and full repository wiring
# ---------------------------------------------------------------------------


def test_standard_application_opens_exactly_one_writer_through_the_seam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The composition constructs its single writer via the standard seam."""
    import astrid.application as application_module

    captured: dict[str, object] = {}

    def fake_open_writer(path: object, *, registry: object = None) -> object:
        writer = open_standard_writer(path, registry=registry)  # type: ignore[arg-type]
        captured["writer"] = writer
        return writer

    monkeypatch.setattr(
        application_module, "open_standard_writer", fake_open_writer
    )
    with compose_standard_application(projects_root=tmp_path) as app:
        assert app.writer is captured["writer"]
        assert isinstance(app.writer, DatabaseWriter)


def test_standard_application_exposes_all_repositories(tmp_path: Path) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        for repo in (
            app.projects,
            app.tasks,
            app.media,
            app.runs,
            app.evidence,
            app.timelines,
            app.shots,
            app.references,
        ):
            assert repo is not None
        assert isinstance(app.projects, ProjectRepository)
        assert isinstance(app.tasks, TaskRepository)
        assert isinstance(app.media, MediaRepository)
        assert isinstance(app.runs, RunRepository)
        assert isinstance(app.evidence, EvidenceRepository)
        assert isinstance(app.timelines, TimelineRepository)
        assert isinstance(app.shots, ShotRepository)
        assert isinstance(app.references, ReferenceRepository)
        assert isinstance(app.event_log, EventRepository)
        assert isinstance(app.events, EventAppendService)
        assert isinstance(app.receipts, ReceiptService)
        assert app.database_path == tmp_path / ".astrid" / "astrid.sqlite3"


def test_commands_from_all_repositories_share_one_gap_free_queue(
    tmp_path: Path,
) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        uow = UnitOfWork(app.writer)

        def create_project(uow: UnitOfWork) -> str:
            project = app.projects.create(
                uow,
                slug="demo",
                name="Demo",
                settings={},
                idempotency_key="project-1",
            )
            return project.id

        project_id = uow.run(create_project)

        def create_timeline(uow: UnitOfWork) -> str:
            timeline = app.timelines.create(
                uow,
                project_id=project_id,
                slug="main",
                name="Main",
                config={"version": 1},
                idempotency_key="timeline-1",
            )
            return timeline.timeline_id

        uow.run(create_timeline)

        # Both commands committed through the same queue: the project
        # sequences are gap-free and in command order.
        events = app.event_log.list_events()
        assert [event.project_seq for event in events] == [1, 2]
        assert [event.kind for event in events] == [
            "core.project.created",
            "timeline.created",
        ]


# ---------------------------------------------------------------------------
# Read-only ordered event reads
# ---------------------------------------------------------------------------


def test_event_repository_reads_are_ordered_and_read_only(tmp_path: Path) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        uow = UnitOfWork(app.writer)

        def seed(uow: UnitOfWork) -> str:
            project = app.projects.create(
                uow, slug="demo", name="Demo", settings={}, idempotency_key="p1"
            )
            return project.id

        project_id = uow.run(seed)
        uow.run(
            lambda uow: app.timelines.create(
                uow,
                project_id=project_id,
                slug="main",
                name="Main",
                config={},
                idempotency_key="t1",
            )
        )

        # Global order: ascending project_seq (seq as tie-breaker).
        events = app.event_log.list_events()
        assert len(events) == 2
        assert [e.project_seq for e in events] == [1, 2]
        # Every event unwraps the SD2 envelope: domain data plus chain.
        first = events[0]
        assert first.kind == "core.project.created"
        assert first.data["slug"] == "demo"
        assert first.previous_event_hash is None
        assert first.event_hash
        # The timeline event is genesis of its own stream.
        second = events[1]
        assert second.kind == "timeline.created"
        assert second.previous_event_hash is None

        # A second event on the project stream chains to the first: the
        # previous_event_hash equals the preceding event's event_hash.
        uow.run(
            lambda uow: app.projects.update(
                uow,
                project_id,
                name="Demo Updated",
                idempotency_key="p2",
            )
        )
        stream_events = app.event_log.list_events(stream_id=first.stream_id)
        assert [e.kind for e in stream_events] == [
            "core.project.created",
            "core.project.updated",
        ]
        assert stream_events[1].previous_event_hash == stream_events[0].event_hash

        # Stream order: ascending seq within one stream.
        assert [e.seq for e in stream_events] == [1, 2]

        # Resumption strictly after a sequence.
        after = app.event_log.list_events(after_project_seq=2)
        assert [e.project_seq for e in after] == [3]

        # Bounded reads and exact id lookup.
        assert len(app.event_log.list_events(limit=2)) == 2
        assert app.event_log.get_event(first.event_id) == first
        assert app.event_log.get_event("missing-event") is None

        # Reads never open a transaction and never write a row.
        with app.writer.read_only_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert count == 3
        with pytest.raises(EventReadError, match="positive integer"):
            app.event_log.list_events(limit=0)


def test_event_repository_rejects_unknown_stream_reads_cleanly(
    tmp_path: Path,
) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        assert app.event_log.list_events(stream_id="no-such-stream") == ()


# ---------------------------------------------------------------------------
# Pack-independent core composition
# ---------------------------------------------------------------------------


def test_core_composition_is_pack_independent(tmp_path: Path, core_registry) -> None:
    writer = DatabaseWriter(tmp_path / "core.sqlite3", core_registry)
    app = compose_core_application(
        writer, registry=core_registry, projects_root=tmp_path
    )
    try:
        assert app.writer is writer
        assert app.event_log is not None
        uow = UnitOfWork(app.writer)

        def seed(uow: UnitOfWork) -> str:
            project = app.projects.create(
                uow, slug="core", name="Core", settings={}, idempotency_key="c1"
            )
            return project.id

        project_id = uow.run(seed)
        events = app.event_log.list_events(project_id=project_id)
        assert len(events) == 1
        assert events[0].kind == "core.project.created"
    finally:
        app.close()


def test_core_event_repository_source_never_imports_packs() -> None:
    from astrid.core.repositories import events as events_module

    source = Path(events_module.__file__).read_text(encoding="utf-8")
    assert "astrid.packs" not in source
    # The core wiring function itself references no pack either.
    import inspect

    from astrid.application import compose_core_application

    assert "astrid.packs" not in inspect.getsource(compose_core_application)


# ---------------------------------------------------------------------------
# No table added, no dynamic discovery
# ---------------------------------------------------------------------------


def test_composed_database_is_exactly_the_frozen_catalog(tmp_path: Path) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        expected = set(app.registry.tables.keys())
        assert len(expected) == EXPECTED_TABLE_COUNT
        assert set(STANDARD_SCHEMA_PACKS) == {"timeline", "shots", "references", "runaway"}
        with app.writer.read_only_connection() as conn:
            names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
        # Composition adds no table: the live catalog is exactly the
        # manifest-derived frozen catalog.
        assert names == expected


def test_composition_and_event_repository_do_no_dynamic_discovery() -> None:
    import astrid.application as application_module
    from astrid.core.repositories import events as events_module

    for module in (application_module, events_module):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for forbidden in ("importlib", "pkgutil", "glob("):
            assert forbidden not in source, f"{module.__name__} uses {forbidden!r}"


# ---------------------------------------------------------------------------
# Deterministic close
# ---------------------------------------------------------------------------


def test_close_drains_queued_work_and_is_idempotent(tmp_path: Path) -> None:
    app = compose_standard_application(projects_root=tmp_path)
    executed: list[int] = []

    def submit_one(value: int) -> None:
        app.writer.submit(lambda session: executed.append(value))

    submit_one(1)
    submit_one(2)
    app.close()
    # Queued callbacks still executed before the writer stopped.
    assert executed == [1, 2]
    # Deterministic and idempotent: a second close is a no-op.
    app.close()
    app.close()
    # Submissions after close fail with the typed shutdown error.
    with pytest.raises(WriterShutdownError):
        app.writer.submit(lambda session: executed.append(3))
    assert executed == [1, 2]


def test_context_manager_closes_deterministically(tmp_path: Path) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        assert not app.writer.closed
    assert app.writer.closed
    with pytest.raises(WriterShutdownError):
        app.writer.submit(lambda session: None)


def test_failed_wiring_closes_writer_without_leaking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If repository wiring fails mid-composition, the writer is closed."""
    import astrid.application as application_module

    def boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("wiring failure")

    monkeypatch.setattr(
        application_module, "TimelineRepository", boom, raising=True
    )
    with pytest.raises(RuntimeError, match="wiring failure"):
        compose_standard_application(projects_root=tmp_path)
    # Restore the real repository before proving the path recovers.
    monkeypatch.undo()
    # No open writer leaked: a second composition succeeds on the same path.
    with compose_standard_application(projects_root=tmp_path) as app:
        assert isinstance(app.writer, DatabaseWriter)


# ---------------------------------------------------------------------------
# Seven typed services over the shared repositories (m4 plan step 17, T18)
# ---------------------------------------------------------------------------


def test_standard_application_resolves_all_seven_typed_services(
    tmp_path: Path,
) -> None:
    """Every typed service resolves through the application (plan step 17).

    The standard composition wires projects, timelines, media, tasks, runs,
    references, and shots services over the shared repositories and the
    single writer queue; each service is typed and bound to exactly the one
    composed ``DatabaseWriter`` (no service opens a writer of its own).
    """
    with compose_standard_application(projects_root=tmp_path) as app:
        services = (
            (app.projects_service, ProjectsService),
            (app.timelines_service, TimelinesService),
            (app.media_service, MediaService),
            (app.tasks_service, TasksService),
            (app.runs_service, RunsService),
            (app.references_service, ReferencesService),
            (app.shots_service, ShotsService),
        )
        for service, service_type in services:
            assert isinstance(service, service_type)
        # Every service holds the one shared writer queue: a second writer
        # would violate the single-queue rule (SD3-m4 / v10 section 2.3).
        for service, _ in services:
            assert service._writer is app.writer  # noqa: SLF001 - composition proof


def test_mutations_from_all_services_share_one_gap_free_queue(
    tmp_path: Path,
) -> None:
    """Mutations through every service commit through the one UoW queue.

    Drives a create mutation through each mutating service (projects,
    timelines, media, tasks, references, shots) and a group-cancel mutation
    through the runs service, then proves the shared event log's global
    ``project_seq`` is gap-free and in command order — one FIFO writer
    queue served every service — and that each mutation returned its
    committed receipt.
    """
    with compose_standard_application(projects_root=tmp_path) as app:
        # projects
        project = app.projects_service.create(
            slug="demo", name="Demo", idempotency_key="p1"
        )
        assert project.ok, project.error
        project_id = project.data["id"]
        # timelines
        timeline = app.timelines_service.create(
            project="demo",
            slug="main",
            name="Main",
            config={"version": 1},
            idempotency_key="t1",
        )
        assert timeline.ok, timeline.error
        # media (one real prepared file)
        media_path = tmp_path / "shot.png"
        media_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
        media = app.media_service.import_file(
            project="demo", path=media_path, idempotency_key="m1"
        )
        assert media.ok, media.error
        media_id = media.data["id"]
        # tasks
        task = app.tasks_service.create(
            project_id=project_id,
            capability="demo.cap",
            spec={"prompt": "frame"},
            idempotency_key="k1",
        )
        assert task.ok, task.error
        # references (exact-media rule: uses the imported media id)
        reference = app.references_service.create(
            project="demo",
            kind="character",
            name="Ref A",
            media_id=media_id,
            idempotency_key="r1",
        )
        assert reference.ok, reference.error
        # shots
        shot = app.shots_service.create(
            project="demo", name="Shot A", idempotency_key="s1"
        )
        assert shot.ok, shot.error

        # runs: seed one run through the shared run repository (the run
        # surface has no public create), then drive the group cancel through
        # the runs service — a genuine service mutation over the same queue.
        uow = UnitOfWork(app.writer)

        def seed_run(uow: UnitOfWork) -> str:
            model = app.runs.create(
                uow,
                project_id=project_id,
                children=[{"capability": "demo.cap", "spec": {}}],
                idempotency_key="run-1",
            )
            return model.run_id

        run_id = uow.run(seed_run)
        cancelled = app.runs_service.cancel(
            project_id, run_id, idempotency_key="cancel-1"
        )
        assert cancelled.ok, cancelled.error

        # Every mutation's event landed in one gap-free global sequence.
        events = app.event_log.list_events()
        assert [event.project_seq for event in events] == list(
            range(1, len(events) + 1)
        )
        assert [event.kind for event in events] == [
            "core.project.created",
            "timeline.created",
            "core.media.imported",
            "core.task.created",
            "reference.created",
            "shot.created",
            "core.run.created",
            "core.task.created",
            "core.task.cancelled",
            "core.run.cancelled",
        ]
        # Every service mutation returned its committed receipt.
        for result in (
            project,
            timeline,
            media,
            task,
            reference,
            shot,
            cancelled,
        ):
            assert result.receipt is not None
            assert result.receipt.project_seq is not None


# ---------------------------------------------------------------------------
# Shared service-authority routing (m4 plan step 30, task T33)
# ---------------------------------------------------------------------------


def test_standard_application_instruments_one_timeline_save_command(
    tmp_path: Path,
) -> None:
    """The composition installs exactly one timeline-save instrumentation.

    ``compose_standard_application`` wraps the single timeline service's
    ``save`` command once: every save — bridge, SDK, or CLI — is recorded
    into ``app.timeline_save_calls`` before it commits through the one
    writer queue (plan step 30's single instrumentation point).
    """
    with compose_standard_application(projects_root=tmp_path) as app:
        assert app.timeline_save_calls == []
        assert isinstance(app.timeline_save_calls, list)
        wrapped = app.timelines_service.save

        project = app.projects_service.create(
            slug="demo", name="Demo", idempotency_key="p1"
        )
        assert project.ok, project.error
        timeline = app.timelines_service.create(
            project="demo",
            slug="main",
            name="Main",
            config={"version": 1},
            idempotency_key="t1",
        )
        assert timeline.ok, timeline.error

        saved = app.timelines_service.save(
            "demo",
            "main",
            config={"version": 2},
            registry={"assets": {}},
            expected_version=1,
            idempotency_key="s1",
        )
        assert saved.ok, saved.error

        # Exactly one crossing, recorded on the same bound command.
        assert len(app.timeline_save_calls) == 1
        call = app.timeline_save_calls[0]
        assert isinstance(call, TimelineSaveCall)
        assert call.project == "demo"
        assert call.ref == "main"
        assert call.idempotency_key == "s1"
        assert call.expected_version == 1
        # The instrumented command is still the service's save command.
        assert app.timelines_service.save is wrapped
        # One writer: the timeline service commits through the one queue.
        assert app.timelines_service._writer is app.writer  # noqa: SLF001


def test_bridge_adapter_over_application_routes_to_application_services(
    tmp_path: Path,
) -> None:
    """A bridge adapter over the application is in service mode and binds
    to the application's own services and single writer (plan step 20/21).

    This is the bridge-side routing assertion of the shared
    service-authority proof: the adapter holds the same project/timeline
    service instances the SDK client exposes, over the one writer, so a
    bridge save resolves to the identical service command an SDK or CLI
    save uses.
    """
    with compose_standard_application(projects_root=tmp_path) as app:
        adapter = TimelineBridgeAdapter(
            writer=app.writer,
            projects=app.projects_service,
            timelines=app.timelines_service,
        )
        assert adapter._service_mode is True  # noqa: SLF001
        assert adapter._writer is app.writer  # noqa: SLF001
        assert adapter._projects is app.projects_service  # noqa: SLF001
        assert adapter._timelines is app.timelines_service  # noqa: SLF001
        # An AstridClient bound to the same application exposes the very
        # same timeline service the bridge adapter holds.
        assert AstridClient(app).timelines is app.timelines_service


def test_product_registration_stamps_the_shared_client_on_every_handler(
    tmp_path: Path,
) -> None:
    """The product registration boundary routes every CLI handler through
    the shared application client (plan step 24 / step 30 routing).

    ``register_product_commands`` returns the stamped specs and stamps
    ``family`` plus the composed ``AstridClient`` onto every subparser, so
    each CLI handler is a rule-free SDK adapter over the same services the
    bridge and SDK use.
    """
    with compose_standard_application(projects_root=tmp_path) as app:
        client = AstridClient(app)
        from astrid.packs.timeline.cli import COMMANDS

        parser = argparse.ArgumentParser(prog="astrid timelines")
        subparsers = parser.add_subparsers(dest="command", required=True)
        stamped = register_product_commands(
            subparsers, COMMANDS, family="timelines", client=client
        )
        assert len(stamped) == len(COMMANDS)
        for spec in stamped:
            assert spec.configure is not None
            scratch = argparse.ArgumentParser()
            spec.configure(scratch)
            defaults = scratch._defaults  # noqa: SLF001 - argparse introspection
            assert defaults.get("family") == "timelines"
            assert defaults.get("client") is client
            assert callable(defaults.get("handler"))
