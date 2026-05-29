from __future__ import annotations

import atexit
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from astrid.core.project import paths
from astrid.core.task.env import (
    TASK_ITEM_ID_ENV,
    TASK_ITERATION_ENV,
    TASK_PROJECT_ENV,
    TASK_RUN_ID_ENV,
    TASK_STEP_ID_ENV,
)

if "ASTRID_TIMELINE_COMPOSITION_SRC" not in os.environ:
    _package_src = Path(tempfile.mkdtemp(prefix="astrid-timeline-composition-src-"))
    os.environ["ASTRID_TIMELINE_COMPOSITION_SRC"] = str(_package_src)
    atexit.register(lambda: shutil.rmtree(_package_src, ignore_errors=True))


# v10 prep (Fix #1, brief caveat): each pack's ``run.py`` now calls
# ``guard_canonical_entrypoint()`` at module-top, so any test that imports
# ``astrid.packs.<X>.run`` would otherwise exit with code 2. Set the marker
# env var once at conftest load so test collection (and any internal
# import chain that brushes a pack's run module) flows through cleanly.
# Production callers continue to set this in the subprocess env via the
# canonical runners.
os.environ.setdefault("ASTRID_INTERNAL_INVOCATION", "1")


def make_session(**overrides: Any) -> Any:
    """Create a :class:`Session` dataclass with sensible test defaults.

    Use ``**overrides`` to customize any field. The defaults produce::

        id="S-TEST", project="demo", agent_id="claude-1",
        attached_at="2026-05-11T00:00:00Z", last_used_at="2026-05-11T00:00:00Z",
        role="writer", timeline=None, timeline_id=None, run_id=None

    Callers that also need on-disk persistence typically follow with
    ``sess.to_json(session_path(sess.id))`` or use the ``mint_session``
    fixture which writes the session file for you.
    """
    from astrid.core.session.model import Session

    defaults: dict[str, Any] = dict(
        id="S-TEST",
        project="demo",
        agent_id="claude-1",
        attached_at="2026-05-11T00:00:00Z",
        last_used_at="2026-05-11T00:00:00Z",
        role="writer",
        timeline=None,
        timeline_id=None,
        run_id=None,
    )
    defaults.update(overrides)
    return Session(**defaults)


@pytest.fixture
def mint_session() -> Callable[..., Any]:
    """Return a callable that writes an explicit session fixture to disk."""

    def _mint_session(
        astrid_home: Path,
        sid: str = "S-TEST",
        *,
        project: str = "demo",
        run_id: str | None = None,
        role: str = "writer",
        timeline: str | None = None,
        agent_id: str = "claude-1",
    ) -> Any:
        sessions = astrid_home / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        sess = make_session(
            id=sid,
            project=project,
            run_id=run_id,
            agent_id=agent_id,
            timeline=timeline,
            role=role,
        )
        sess.to_json(sessions / f"{sid}.json")
        return sess

    return _mint_session


@pytest.fixture
def seed_project() -> Callable[[Path, str], Path]:
    """Return a callable that seeds the shared session project fixture shape."""

    def _seed_project(projects_root: Path, slug: str) -> Path:
        from astrid import timeline as timeline_contract
        from astrid.core.session.ulid import generate_ulid

        pdir = projects_root / slug
        pdir.mkdir(parents=True, exist_ok=True)

        timeline_ulid = generate_ulid()
        tdir = pdir / "timelines" / timeline_ulid
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "assembly.json").write_text(
            json.dumps(timeline_contract.canonical_empty_timeline()), encoding="utf-8"
        )
        (tdir / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "contributing_runs": [],
                    "final_outputs": [],
                    "tombstoned_at": None,
                }
            ),
            encoding="utf-8",
        )
        (tdir / "display.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "slug": "primary",
                    "name": "Primary",
                    "is_default": True,
                }
            ),
            encoding="utf-8",
        )
        (pdir / "project.json").write_text(
            json.dumps(
                {
                    "created_at": "2026-05-11T00:00:00Z",
                    "name": slug,
                    "schema_version": 1,
                    "slug": slug,
                    "updated_at": "2026-05-11T00:00:00Z",
                    "default_timeline_id": timeline_ulid,
                }
            ),
            encoding="utf-8",
        )
        return pdir

    return _seed_project


@pytest.fixture
def seed_project_run(seed_project: Callable[[Path, str], Path]) -> Callable[..., Path]:
    """Return a callable that seeds a project run with writer lease state."""

    def _seed_project_run(
        projects_root: Path,
        slug: str = "demo",
        run_id: str = "01RUN",
        *,
        writer_session_id: str,
    ) -> Path:
        from astrid.core.project.current_run import write_current_run
        from astrid.core.session.lease import write_lease_init

        project = seed_project(projects_root, slug)
        run_dir = project / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "events.jsonl").touch()
        write_lease_init(run_dir, session_id=writer_session_id, plan_hash="")
        write_current_run(slug, run_id)
        return run_dir

    return _seed_project_run


# ---------------------------------------------------------------------------
# Sprint 1 / T10: session-bootstrap autouse + attached_session fixture
# ---------------------------------------------------------------------------
#
# The CLI gate (T8) rejects every non-allowlisted verb when
# ``ASTRID_SESSION_ID`` is unset. Pre-Sprint-1 tests that exercise
# ``pipeline.main`` did not know to seed a session — this autouse fixture
# mints a tmp ASTRID_HOME with an identity + a default Session and exports
# ``ASTRID_SESSION_ID`` so the gate passes for tests that don't care about
# the session layer. Tests that need to assert the unbound path (the gate
# tests themselves) call ``monkeypatch.delenv('ASTRID_SESSION_ID')`` to
# re-enter the unbound state.


@dataclass
class SessionContext:
    """Returned by the ``attached_session`` fixture."""

    session: Any  # astrid.core.session.model.Session
    project_root: Path
    run_dir: Path | None

    def refresh(self) -> Any:
        """Re-load the session from disk after a potential auto-rebind."""

        from astrid.core.session.model import Session
        from astrid.core.session.paths import session_path

        self.session = Session.from_json(session_path(self.session.id))
        return self.session


def _seed_identity_and_session(
    astrid_home: Path,
    *,
    project: str = "autouse-session-demo",
    run_id: str | None = None,
) -> tuple[Any, Path]:
    """Mint identity + session + project. Returns (Session, project_root)."""

    from astrid.core.project.current_run import write_current_run
    from astrid.core.project.paths import project_dir
    from astrid.core.session.identity import Identity, write_identity
    from astrid.core.session.lease import write_lease_init
    from astrid.core.session.paths import session_path
    from astrid.core.session.ulid import generate_ulid

    astrid_home.mkdir(parents=True, exist_ok=True)
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))

    sid = generate_ulid()
    proj_root = project_dir(project)
    proj_root.mkdir(parents=True, exist_ok=True)
    (proj_root / "project.json").write_text(
        json.dumps(
            {
                "created_at": "2026-05-11T00:00:00Z",
                "name": project,
                "schema_version": 1,
                "slug": project,
                "updated_at": "2026-05-11T00:00:00Z",
                "default_timeline_id": None,
            }
        ),
        encoding="utf-8",
    )

    run_path: Path | None = None
    if run_id is not None:
        run_path = proj_root / "runs" / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        (run_path / "events.jsonl").touch()
        # Seed the lease with the session id so the legacy append_event
        # wrapper sees a matching attached_session_id (the wrapper itself
        # doesn't do writer-auth, but WriterContext-aware callers do).
        write_lease_init(run_path, session_id=sid, plan_hash="")
        write_current_run(project, run_id)

    sess = make_session(
        id=sid,
        project=project,
        run_id=run_id,
    )
    sess.to_json(session_path(sid))
    return sess, proj_root


@pytest.fixture(autouse=True)
def _autouse_session_seed(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Seed ASTRID_HOME + identity + a default Session for every test.

    Tests that explicitly need the unbound state should
    ``monkeypatch.delenv('ASTRID_SESSION_ID')`` (and optionally also delete
    the identity / sessions dir). This fixture is autouse so legacy
    pipeline-dispatch tests pass the CLI gate without per-file migration.
    """

    astrid_home = tmp_path_factory.mktemp("astrid_home_autouse")
    projects_root = tmp_path_factory.mktemp("astrid_projects_autouse")
    monkeypatch.setenv("ASTRID_HOME", str(astrid_home))
    # Seed PROJECTS_ROOT to a tmp dir so the autouse seed-project does NOT
    # write into the user's real ~/Documents/.../astrid-projects/. Tests
    # that need their own projects-root (via tmp_projects_root) override
    # this with their own monkeypatch.setenv on the same env var.
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    sess, _ = _seed_identity_and_session(astrid_home)
    monkeypatch.setenv("ASTRID_SESSION_ID", sess.id)
    return astrid_home


@pytest.fixture
def attached_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> SessionContext:
    """Explicit fixture for tests that need full control over the session.

    Re-seeds ASTRID_HOME under ``tmp_path`` (overriding the autouse seed),
    mints identity + a Session bound to a fresh ``demo`` project + run,
    and seeds ``runs/<run_id>/lease.json`` with the session id so legacy
    append_event wrappers don't trip ``NotWriterError``. The returned
    :class:`SessionContext` exposes ``refresh()`` to re-read the session
    file after a potential WriterContext auto-rebind.
    """

    from astrid.core.session.ulid import generate_ulid

    astrid_home = tmp_path / "astrid_home"
    monkeypatch.setenv("ASTRID_HOME", str(astrid_home))
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    run_id = generate_ulid()
    sess, proj_root = _seed_identity_and_session(
        astrid_home, project="demo", run_id=run_id
    )
    monkeypatch.setenv("ASTRID_SESSION_ID", sess.id)
    return SessionContext(
        session=sess,
        project_root=proj_root,
        run_dir=proj_root / "runs" / run_id,
    )


@pytest.fixture
def tmp_projects_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(tmp_path))
    for name in (
        TASK_RUN_ID_ENV,
        TASK_PROJECT_ENV,
        TASK_STEP_ID_ENV,
        TASK_ITEM_ID_ENV,
        TASK_ITERATION_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    yield tmp_path
    for name in (
        TASK_RUN_ID_ENV,
        TASK_PROJECT_ENV,
        TASK_STEP_ID_ENV,
        TASK_ITEM_ID_ENV,
        TASK_ITERATION_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
