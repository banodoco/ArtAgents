"""Shared fixtures for v10 catalog and migration tests.

Every fixture builds a fresh on-disk SQLite database through the migration
runner (``open_database``), so the databases under test are exactly what a
fresh Astrid open produces: manifest-derived, dependency-ordered, and
recorded in ``schema_migrations`` with exact-byte SHA-256 checksums.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from astrid.core.events.registry import core_only_registry
from astrid.core.store.database import open_database



def canonical_database_registry():
    """Compose the canonical bundled default database projection."""
    from astrid.packs import compose_standard_pack_database

    return compose_standard_pack_database().registry


@pytest.fixture
def core_registry():
    """Frozen kernel-only registry (no Astrid packs)."""
    return core_only_registry()


@pytest.fixture
def standard_registry():
    """Frozen standard-Astrid registry (core + the three in-tree packs)."""
    return canonical_database_registry()


@pytest.fixture
def core_database(tmp_path: Path, core_registry):
    """A fresh kernel-only database at ``<tmp>/core.sqlite3``.

    Yields ``(connection, path)``; the connection is closed afterwards.
    """
    path = tmp_path / "core.sqlite3"
    conn = open_database(path, core_registry)
    try:
        yield conn, path
    finally:
        conn.close()


@pytest.fixture
def standard_database(tmp_path: Path, standard_registry):
    """A fresh standard-Astrid database at ``<tmp>/astrid.sqlite3``.

    Yields ``(connection, path)``; the connection is closed afterwards.
    """
    path = tmp_path / "astrid.sqlite3"
    conn = open_database(path, standard_registry)
    try:
        yield conn, path
    finally:
        conn.close()


@pytest.fixture
def task_env(tmp_path: Path, core_registry):
    """Fresh kernel writer plus project and task repositories (m2 plan step 6).

    Yields a small namespace with ``writer`` (a kernel
    :class:`~astrid.core.store.writer.DatabaseWriter` over a fresh
    database), ``project_repo`` (the m1 project vertical), and ``task_repo``
    (the m2 task admission surface). Task tests create a project through
    ``project_repo`` and then admit tasks under that project id; the writer
    is closed on teardown.
    """
    from types import SimpleNamespace

    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.core.repositories.tasks import TaskRepository
    from astrid.core.store.writer import DatabaseWriter

    db_path = tmp_path / "task_env.sqlite3"
    writer = DatabaseWriter(db_path, core_registry)
    try:
        events = EventAppendService(core_registry)
        receipts = ReceiptService()
        yield SimpleNamespace(
            writer=writer,
            project_repo=ProjectRepository(events=events, receipts=receipts),
            task_repo=TaskRepository(events=events, receipts=receipts),
        )
    finally:
        writer.close()


@pytest.fixture
def media_env(tmp_path: Path, core_registry):
    """Fresh kernel writer plus project and media repositories (m2 plan step 4).

    Yields a small namespace with ``writer`` (a kernel
    :class:`~astrid.core.store.writer.DatabaseWriter` over a fresh
    database), ``project_repo`` (the m1 project vertical), ``media_repo``
    (the m2 prepared-media import surface bound to ``tmp_path`` as the
    projects root so managed publication lands under
    ``tmp_path/.astrid/media/sha256/...``), and ``projects_root`` (the
    resolved root). The writer is closed on teardown.
    """
    from types import SimpleNamespace

    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.media import MediaRepository
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.core.store.writer import DatabaseWriter

    db_path = tmp_path / "media_env.sqlite3"
    writer = DatabaseWriter(db_path, core_registry)
    try:
        events = EventAppendService(core_registry)
        receipts = ReceiptService()
        yield SimpleNamespace(
            writer=writer,
            projects_root=tmp_path,
            project_repo=ProjectRepository(events=events, receipts=receipts),
            media_repo=MediaRepository(
                events=events, receipts=receipts, projects_root=tmp_path
            ),
        )
    finally:
        writer.close()


@pytest.fixture
def evidence_env(tmp_path: Path, core_registry):
    """Fresh kernel writer plus project/media/task/run/evidence repositories.

    Yields a small namespace with ``writer``, ``project_repo``, ``media_repo``
    (bound to ``tmp_path`` as the projects root), ``task_repo``, ``run_repo``,
    and the m3 ``evidence_repo`` (the kernel evidence vertical). The writer is
    closed on teardown.
    """
    from types import SimpleNamespace

    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.evidence import EvidenceRepository
    from astrid.core.repositories.media import MediaRepository
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.core.repositories.runs import RunRepository
    from astrid.core.repositories.tasks import TaskRepository
    from astrid.core.store.writer import DatabaseWriter

    db_path = tmp_path / "evidence_env.sqlite3"
    writer = DatabaseWriter(db_path, core_registry)
    try:
        events = EventAppendService(core_registry)
        receipts = ReceiptService()
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


@pytest.fixture
def conformance_context(tmp_path: Path, standard_registry):
    """Fresh standard-Astrid conformance context (m2 plan step 15, T24_impl).

    Builds a :class:`~astrid.core.conformance.kit.ConformanceContext` over
    one fresh database with the m1 project/timeline verticals **and** the
    m2 kernel task/media/run repositories injected, plus a temporary
    managed root under ``tmp_path`` that the kernel media spec's prepared
    filesystem fixtures and managed publication share — without importing
    any pack implementation into kernel code. Yields the context; the
    writer is closed on teardown.
    """
    from astrid.core.conformance.kit import ConformanceContext
    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.media import MediaRepository
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.core.repositories.runs import RunRepository
    from astrid.core.repositories.tasks import TaskRepository
    from astrid.core.store.writer import DatabaseWriter
    from astrid.packs.references.repository import ReferenceRepository
    from astrid.packs.shots.repository import ShotRepository
    from astrid.packs.timeline.repository import TimelineRepository

    db_path = tmp_path / "conformance.sqlite3"
    writer = DatabaseWriter(db_path, standard_registry)
    try:
        events = EventAppendService(standard_registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        managed_root = tmp_path / "managed"
        context = ConformanceContext(
            db_path=db_path,
            writer=writer,
            registry=standard_registry,
            events=events,
            receipts=receipts,
            projects=projects,
            timelines=TimelineRepository(
                events=events, receipts=receipts, projects=projects
            ),
            tasks=TaskRepository(events=events, receipts=receipts),
            media=MediaRepository(
                events=events, receipts=receipts, projects_root=managed_root
            ),
            runs=RunRepository(events=events, receipts=receipts),
            managed_root=managed_root,
        )
        # The references pack repository is injected duck-typed (m3 T13):
        # the kernel kit never imports a pack, so the context carries the
        # pack-owned conformance factories' repository as a plain attribute.
        context.references = ReferenceRepository(events=events, receipts=receipts)
        # The shots pack repository is injected duck-typed (m3 T14) the same
        # way, so the shot conformance factories drive the real repository.
        context.shots = ShotRepository(events=events, receipts=receipts)
        yield context
    finally:
        writer.close()
