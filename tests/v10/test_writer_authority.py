"""Executable exclusive-owner writer-authority tests (m4 plan step 4, T5).

Proves the process-lifetime owner lock in ``astrid.core.store.ownership``
and its integration in ``astrid.application.compose_standard_application``:

- **fail-closed second owner:** a second composition (same process or a
  separate process) targeting the same database is rejected with the SDK's
  typed ``unavailable`` error before any second writable connection or
  writer queue can open;
- **one shared in-process queue:** every repository in one composition
  commits through the single ``DatabaseWriter`` FIFO queue with gap-free
  project sequences;
- **reliable release:** every close path (``close()``, the context manager,
  and a failed wiring attempt) releases the lock, so a later composition on
  the same database succeeds.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from astrid.application import compose_standard_application
from astrid.core.store.ownership import (
    DatabaseOwnerLock,
    OwnerLockError,
    database_lock_path,
)
from astrid.core.store.uow import UnitOfWork
from astrid.sdk.exceptions import ServiceUnavailableError

# Project root (two parents above this test module: tests/v10 -> tests -> root).
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])

# ---------------------------------------------------------------------------
# Lock module: fail-closed acquisition and idempotent release
# ---------------------------------------------------------------------------


def test_lock_acquires_exclusive_and_fails_closed(tmp_path: Path) -> None:
    db_path = tmp_path / "authority.sqlite3"
    assert database_lock_path(db_path) == tmp_path / "authority.sqlite3.lock"
    first = DatabaseOwnerLock(db_path)
    try:
        assert first.held is True
        assert first.lock_path.exists()
        # A second owner in the same process fails closed (flock is per
        # open-file-description, so two separate opens conflict).
        with pytest.raises(OwnerLockError):
            DatabaseOwnerLock(db_path)
    finally:
        first.release()
    assert first.held is False
    # After release a new owner can acquire the same lock.
    second = DatabaseOwnerLock(db_path)
    second.release()


def test_lock_context_manager_releases(tmp_path: Path) -> None:
    db_path = tmp_path / "ctx.sqlite3"
    with DatabaseOwnerLock(db_path) as lock:
        assert lock.held is True
    assert lock.held is False
    # Idempotent release.
    lock.release()
    lock.close()
    assert lock.held is False


# ---------------------------------------------------------------------------
# Standard application: lock acquired before the writer, released on close
# ---------------------------------------------------------------------------


def test_composition_holds_lock_and_second_owner_is_typed_unavailable(
    tmp_path: Path,
) -> None:
    app = compose_standard_application(projects_root=tmp_path)
    try:
        assert app.owner_lock is not None
        assert app.owner_lock.held is True
        assert app.owner_lock.lock_path == database_lock_path(app.database_path)
        # A second owner (same process) fails closed with typed unavailable.
        with pytest.raises(ServiceUnavailableError):
            compose_standard_application(projects_root=tmp_path)
    finally:
        app.close()
    # Close released the lock.
    assert app.owner_lock.held is False
    # A later composition on the same root now succeeds.
    with compose_standard_application(projects_root=tmp_path) as app2:
        assert app2.owner_lock.held is True


def test_context_manager_closes_and_releases_lock(tmp_path: Path) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        assert app.owner_lock is not None
        assert app.owner_lock.held is True
        assert not app.writer.closed
    assert app.writer.closed
    assert app.owner_lock.held is False


def test_concurrent_process_gets_typed_unavailable(tmp_path: Path) -> None:
    """A genuinely separate process is rejected before opening a writer."""
    with compose_standard_application(projects_root=tmp_path) as app:
        assert app.owner_lock.held is True
        script = (
            "import sys\n"
            "from astrid.application import compose_standard_application\n"
            "from astrid.sdk.exceptions import ServiceUnavailableError\n"
            "root = sys.argv[1]\n"
            "try:\n"
            "    compose_standard_application(projects_root=root)\n"
            "except ServiceUnavailableError:\n"
            "    print('UNAVAILABLE')\n"
            "    raise SystemExit(0)\n"
            "print('NO_FAILURE')\n"
            "raise SystemExit(1)\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=60,
            # astrid is not installed in the runtime venv; the child resolves it
            # from the project root, which PYTHONSAFEPATH (canonical launch env)
            # removes from sys.path.  Pin PYTHONPATH so the subprocess can import
            # astrid regardless of the ambient safe-path policy.
            env={**os.environ, "PYTHONPATH": _PROJECT_ROOT},
        )
        assert proc.returncode == 0, proc.stderr
        assert "UNAVAILABLE" in proc.stdout


def test_failed_wiring_releases_lock(tmp_path: Path) -> None:
    """If wiring fails after the writer opens, the lock is still released."""
    import astrid.application as application_module

    def boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("wiring failure")

    from astrid.packs.timeline.repository import TimelineRepository

    application_module.TimelineRepository = boom  # type: ignore[assignment]
    try:
        with pytest.raises(RuntimeError, match="wiring failure"):
            compose_standard_application(projects_root=tmp_path)
    finally:
        application_module.TimelineRepository = TimelineRepository  # type: ignore[assignment]
    # The failed composition released the lock, so a fresh composition works.
    with compose_standard_application(projects_root=tmp_path) as app:
        assert app.owner_lock is not None
        assert app.owner_lock.held is True


# ---------------------------------------------------------------------------
# In-process single-writer queue is shared by every repository
# ---------------------------------------------------------------------------


def test_all_repositories_share_one_gap_free_queue(tmp_path: Path) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        uow = UnitOfWork(app.writer)

        def create_project(uow: UnitOfWork) -> str:
            return app.projects.create(
                uow,
                slug="demo",
                name="Demo",
                settings={},
                idempotency_key="project-1",
            ).id

        project_id = uow.run(create_project)

        uow.run(
            lambda uow: app.timelines.create(
                uow,
                project_id=project_id,
                slug="main",
                name="Main",
                config={},
                idempotency_key="timeline-1",
            )
        )

        events = app.event_log.list_events()
        assert [event.project_seq for event in events] == [1, 2]
        assert [event.kind for event in events] == [
            "core.project.created",
            "timeline.created",
        ]