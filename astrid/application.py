"""Deterministic kernel application composition (m4 plan step 4, task T4).

This module is the shared application boundary the SDK services and the
bridge consume (SDK contract ``docs/contracts/astrid-sdk-v10.md`` section
6). It composes, **explicitly and deterministically**:

- exactly **one** :class:`~astrid.core.store.writer.DatabaseWriter` — the
  single write queue every repository submits through;
- the kernel repositories (projects, tasks, media, runs, evidence) and the
  kernel services (event append, receipts);
- a **read-only ordered** :class:`~astrid.core.repositories.EventRepository`
  over the same writer for ordered event reads;
- for the standard composition, the three explicitly registered in-tree
  pack repositories (timeline, shots, references);
- for the standard composition, all seven typed SDK services (projects,
  timelines, media, tasks, runs, references, shots) over those shared
  repositories — every service resolves through the application, holds no
  SQL, and never opens a writer of its own.

Rules enforced here:

- **No tables are added.** The composition only opens the database through
  the frozen migration catalog; the event repository issues ``SELECT``
  only.
- **No dynamic discovery.** Every repository and service is imported and
  constructed by name; there is no module scanning, no pack loader, and no
  install/uninstall path.
- **Pack-independent core.** :func:`compose_core_application` never
  imports ``astrid.packs``; the kernel repositories and the event
  repository compose without any pack. The seven typed services are wired
  only by the standard composition (Step 17), because the timeline service
  consumes the timeline pack repository.
- **Deterministic close.** :meth:`CoreApplication.close` drains the writer
  queue, stops the writer thread, and closes the owned connection
  (idempotent); the standard composition also closes the writer if any
  wiring step fails mid-construction.

- **Exclusive-owner lock (SD3-m4).** :func:`compose_standard_application`
  acquires a process-lifetime :class:`astrid.core.store.ownership.DatabaseOwnerLock`
  beside the database **before** opening the writer (so no second writable
  connection or queue can open), and releases it on every close path. A
  second owner fails closed with the SDK's typed ``unavailable`` contract
  instead of leaking an OS or database error.

Startup staging GC remains the serve composition root's concern
(``compose_standard_bridge``).
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from astrid.core.events.service import EventAppendService
from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.receipts import ReceiptService
from astrid.core.repositories import (
    EventRepository,
    EvidenceRepository,
    MediaRepository,
    ProjectRepository,
    RunRepository,
    TaskRepository,
)
from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry
from astrid.core.store.ownership import DatabaseOwnerLock, OwnerLockError
from astrid.core.store.writer import DatabaseWriter
from astrid.packs import build_standard_registry, open_standard_writer
from astrid.packs.references.repository import ReferenceRepository
from astrid.packs.shots.repository import ShotRepository
from astrid.packs.shots.text_bindings import ShotTextBindingRepository
from astrid.packs.timeline.repository import TimelineRepository
from astrid.sdk.contracts import DomainResult
from astrid.sdk.exceptions import ServiceUnavailableError
from astrid.sdk.media import MediaService
from astrid.sdk.projects import ProjectsService
from astrid.sdk.references import ReferencesService
from astrid.sdk.runs import RunsService
from astrid.sdk.shots import ShotsService
from astrid.sdk.tasks import TasksService
from astrid.sdk.timelines import TimelinesService

__all__ = [
    "CoreApplication",
    "StandardApplication",
    "TimelineSaveCall",
    "compose_core_application",
    "compose_standard_application",
]


@dataclass(frozen=True, slots=True)
class TimelineSaveCall:
    """One crossing of the shared timeline-save service command (plan step 30).

    Recorded once per invocation of :meth:`TimelinesService.save` on the
    standard application's single timeline service, regardless of which
    surface (bridge, SDK, or CLI) drove the call. This is the shared
    service-authority proof's single instrumentation point: bridge, SDK,
    and CLI timeline saves must all be observable here, over the one
    application writer, with equivalent committed receipts.
    """

    project: str
    ref: str
    idempotency_key: str | None
    expected_version: int


@dataclass(frozen=True, slots=True)
class CoreApplication:
    """Kernel-only application over exactly one writer queue.

    Pack-independent: this composition contains no pack repository and the
    wiring function that builds it never imports ``astrid.packs``. All
    repositories share the single :attr:`writer`; :attr:`event_log`
    provides read-only ordered event reads over the same writer.
    """

    projects_root: Path
    registry: FrozenSchemaPackRegistry
    writer: DatabaseWriter
    events: EventAppendService
    receipts: ReceiptService
    projects: ProjectRepository
    tasks: TaskRepository
    media: MediaRepository
    runs: RunRepository
    evidence: EvidenceRepository
    event_log: EventRepository
    owner_lock: DatabaseOwnerLock | None

    @property
    def database_path(self) -> Path:
        """The managed database path for this projects root (decision §5)."""
        return derive_database_path(self.projects_root)

    def close(self) -> None:
        """Drain the writer queue, stop the writer thread, close the database.

        Deterministic and idempotent: queued callbacks still execute, the
        owned connection is closed by the writer thread itself, and a
        second ``close()`` is a no-op (``DatabaseWriter.close`` contract).
        When the composition holds the exclusive-owner lock (the standard
        composition), it is released only after the writer is closed, so a
        second owner can never acquire the database while this process
        still holds an open writer.
        """
        self.writer.close()
        if self.owner_lock is not None:
            self.owner_lock.release()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class StandardApplication(CoreApplication):
    """Standard-Astrid application: kernel plus packs plus typed services.

    Extends :class:`CoreApplication` with the three explicitly registered
    pack repositories (timeline, shots, references) and the seven typed SDK
    services (projects, timelines, media, tasks, runs, references, shots),
    all sharing the same single writer queue, registry, kernel services,
    and read-only ordered event repository. The services hold no SQL and
    never open a writer of their own — each one opens a
    :class:`~astrid.core.store.uow.UnitOfWork` over the shared
    :attr:`~CoreApplication.writer` per mutation.

    Plan step 30 instruments exactly one service command —
    :attr:`timelines_service` ``save`` — so every bridge, SDK, or CLI
    timeline save is recorded in :attr:`timeline_save_calls` before it
    commits through the one writer queue (the shared service-authority
    proof's single instrumentation point).
    """

    timelines: TimelineRepository
    shots: ShotRepository
    text_bindings: ShotTextBindingRepository
    references: ReferenceRepository
    projects_service: ProjectsService
    timelines_service: TimelinesService
    media_service: MediaService
    tasks_service: TasksService
    runs_service: RunsService
    references_service: ReferencesService
    shots_service: ShotsService
    # The shared service-authority instrumentation (plan step 30): every
    # timeline save that crosses the application's single timeline service
    # — from the bridge, the SDK, or the CLI — is recorded here, so tests
    # can prove all three surfaces reach the same service command over the
    # one writer queue with equivalent committed receipts.
    timeline_save_calls: list[TimelineSaveCall]

    @property
    def shot_text_bindings(self) -> ShotTextBindingRepository:
        """Compatibility alias for the Shots-owned text-binding repository."""
        return self.text_bindings


def compose_core_application(
    writer: DatabaseWriter,
    *,
    registry: FrozenSchemaPackRegistry,
    projects_root: str | Path,
) -> CoreApplication:
    """Wire the kernel-only application over one already-open writer.

    The caller supplies the single writer (constructed through a store
    seam such as the standard writer opener, or directly in tests)
    together with the registry that writer's database was opened with and
    the managed projects root. This function adds no tables, performs no
    dynamic discovery, and never imports a pack, so the core composition
    stays pack-independent.
    """
    root = Path(projects_root)
    events = EventAppendService(registry)
    receipts = ReceiptService()
    projects = ProjectRepository(events=events, receipts=receipts)
    tasks = TaskRepository(events=events, receipts=receipts)
    media = MediaRepository(events=events, receipts=receipts, projects_root=root)
    runs = RunRepository(events=events, receipts=receipts)
    evidence = EvidenceRepository(events=events, receipts=receipts)
    return CoreApplication(
        projects_root=root,
        registry=registry,
        writer=writer,
        events=events,
        receipts=receipts,
        projects=projects,
        tasks=tasks,
        media=media,
        runs=runs,
        evidence=evidence,
        event_log=EventRepository(writer),
        owner_lock=None,
    )


def _instrument_timeline_save(service: TimelinesService) -> list[TimelineSaveCall]:
    """Install the one shared-service instrumentation point (plan step 30).

    Wraps the application's single timeline service ``save`` command so
    every bridge, SDK, or CLI timeline save is recorded once — before
    delegating to the original command — into the returned list (exposed
    as ``StandardApplication.timeline_save_calls``). The wrapper is
    installed exactly once per standard application and is safe for
    concurrent callers (the bridge serves requests on its own thread), so
    the recorded calls prove that all three surfaces resolve to the same
    service command over the one writer queue.
    """
    calls: list[TimelineSaveCall] = []
    lock = threading.Lock()
    original = service.save

    def recorded(
        project: str,
        ref: str,
        *,
        config: Mapping[str, Any],
        registry: Mapping[str, Any],
        expected_version: int,
        idempotency_key: str | None = None,
    ) -> DomainResult[dict[str, Any]]:
        with lock:
            calls.append(
                TimelineSaveCall(
                    project=project,
                    ref=ref,
                    idempotency_key=idempotency_key,
                    expected_version=expected_version,
                )
            )
        return original(
            project,
            ref,
            config=config,
            registry=registry,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
        )

    service.save = recorded  # type: ignore[method-assign]
    return calls


def compose_standard_application(
    projects_root: str | Path | None = None,
    *,
    registry: FrozenSchemaPackRegistry | None = None,
    database_path: str | Path | None = None,
) -> StandardApplication:
    """Compose the standard application: one writer, kernel + pack repos.

    Resolves the projects root (argument, ``ASTRID_PROJECTS_ROOT``, or the
    default), derives ``${root}/.astrid/astrid.sqlite3`` (unless a
    ``database_path`` is supplied), composes the standard registry (core +
    exactly timeline, shots, references) unless one is injected, acquires
    the exclusive-owner lock beside the database **before** opening the
    writer, opens exactly one ``DatabaseWriter`` through the standard writer
    seam, and wires every kernel and pack repository plus the read-only
    ordered event repository. If any wiring step fails, the writer is closed
    and the lock is released before the exception propagates, so composition
    never leaks an open writer or a held owner lock. A second owner (another
    process, or another composition in this process) fails closed with the
    SDK's typed ``unavailable`` error.
    """
    root = resolve_projects_root(projects_root)
    db_path = (
        Path(database_path)
        if database_path is not None
        else derive_database_path(root)
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if registry is None:
        registry = build_standard_registry()
    # Acquire the exclusive-owner lock before any writable connection or
    # writer queue can open (SD3-m4). A second owner fails closed with the
    # typed unavailable contract instead of leaking an OS/database error.
    try:
        owner_lock = DatabaseOwnerLock(db_path)
    except OwnerLockError as exc:
        raise ServiceUnavailableError(
            "the canonical store is owned by another Astrid process. When "
            "astrid serve is running, its bridge owns the store: use GET "
            "/routes and its HTTP routes while it is running, or wait for a "
            "clean shutdown. "
            "Reads may retry after release. For writes, preserve the exact "
            "payload and idempotency key, retry after release, and verify "
            "state.",
            details={
                "reason": "store_owned",
                "retryable": True,
            },
        ) from exc
    writer: DatabaseWriter | None = None
    try:
        writer = open_standard_writer(db_path, registry=registry)
        events = EventAppendService(registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        timelines = TimelineRepository(
            events=events, receipts=receipts, projects=projects
        )
        shots = ShotRepository(events=events, receipts=receipts)
        references = ReferenceRepository(events=events, receipts=receipts)
        tasks = TaskRepository(events=events, receipts=receipts)
        media = MediaRepository(
            events=events, receipts=receipts, projects_root=root
        )
        text_bindings = ShotTextBindingRepository(
            events=events,
            receipts=receipts,
            media=media,
            projects_root=root,
        )
        runs = RunRepository(events=events, receipts=receipts)
        evidence = EvidenceRepository(events=events, receipts=receipts)
        event_log = EventRepository(writer)
        # The seven typed services, wired over the shared repositories and
        # the single writer queue. Services contain no SQL and never open a
        # writer of their own (plan step 17).
        projects_service = ProjectsService(
            writer, projects, receipts, projects_root=root
        )
        timelines_service = TimelinesService(
            writer, projects, timelines, receipts
        )
        # One shared service-authority instrumentation point (plan step 30):
        # every timeline save — bridge, SDK, or CLI — is recorded on the
        # single timeline service before it commits through the one writer.
        timeline_save_calls = _instrument_timeline_save(timelines_service)
        media_service = MediaService(writer, projects, media, receipts)
        runs_service = RunsService(
            writer,
            projects,
            runs,
            receipts,
            evidence,
            event_log,
            tasks=tasks,
            media=media,
            projects_root=str(root),
            registry=registry,
        )
        tasks_service = TasksService(
            writer,
            projects,
            tasks,
            receipts,
            event_log,
            media=media,
            projects_root=str(root),
            runs=runs_service,
            registry=registry,
        )
        references_service = ReferencesService(
            writer, projects, references, receipts
        )
        shots_service = ShotsService(
            writer,
            projects,
            shots,
            receipts,
            media,
            text_bindings,
        )
        return StandardApplication(
            projects_root=root,
            registry=registry,
            writer=writer,
            events=events,
            receipts=receipts,
            projects=projects,
            timelines=timelines,
            shots=shots,
            text_bindings=text_bindings,
            references=references,
            tasks=tasks,
            media=media,
            runs=runs,
            evidence=evidence,
            event_log=event_log,
            owner_lock=owner_lock,
            projects_service=projects_service,
            timelines_service=timelines_service,
            media_service=media_service,
            tasks_service=tasks_service,
            runs_service=runs_service,
            references_service=references_service,
            shots_service=shots_service,
            timeline_save_calls=timeline_save_calls,
        )
    except BaseException:
        if writer is not None:
            writer.close()
        owner_lock.release()
        raise
