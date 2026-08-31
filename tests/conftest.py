from __future__ import annotations

import atexit
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
if sys.pycache_prefix is None:
    _pycache_prefix = Path(tempfile.mkdtemp(prefix="astrid-pycache-"))
    sys.pycache_prefix = str(_pycache_prefix)
    os.environ.setdefault("PYTHONPYCACHEPREFIX", str(_pycache_prefix))
    atexit.register(lambda: shutil.rmtree(_pycache_prefix, ignore_errors=True))

from astrid.core.foundation import project_paths as paths
from astrid.core.subprocess_env import (
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


@pytest.fixture
def seed_project() -> Callable[[Path, str], Path]:
    """Return a callable that seeds a filesystem project with a timeline."""

    def _seed_project(projects_root: Path, slug: str) -> Path:
        from astrid.core import timeline as timeline_contract
        from astrid.core.ids import generate_ulid

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


def _clear_task_env() -> None:
    """Scrub raw task-run env that tests may mutate outside monkeypatch."""

    for name in (
        TASK_RUN_ID_ENV,
        TASK_PROJECT_ENV,
        TASK_STEP_ID_ENV,
        TASK_ITEM_ID_ENV,
        TASK_ITERATION_ENV,
    ):
        os.environ.pop(name, None)


@pytest.fixture(autouse=True)
def _sandboxed_home_and_projects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Sandbox ``ASTRID_HOME``, workspace config, and the projects root.

    Every test gets tmp-backed state roots so no test writes into the real
    ``~/.astrid`` or the user's projects directory. The legacy session
    autouse seed (identity and session) was retired
    with the task-mode session layer.
    """

    _clear_task_env()
    # This fixture is function-scoped, so keep all three roots under the
    # function-scoped tmp_path. Using tmp_path_factory here retained three
    # roots for every test until session end and exhausted disk in the full
    # 7,000+ test suite before the installed-artifact lanes could start.
    astrid_home = tmp_path / "astrid-home"
    projects_root = tmp_path / "projects"
    workspace_config_dir = tmp_path / "workspace-config"
    for root in (astrid_home, projects_root, workspace_config_dir):
        root.mkdir()
    monkeypatch.setenv("ASTRID_HOME", str(astrid_home))
    monkeypatch.setenv("ASTRID_WORKSPACE_CONFIG_DIR", str(workspace_config_dir))
    # Seed PROJECTS_ROOT to a tmp dir so tests never touch the real
    # projects root. Tests that need their own projects-root (via
    # tmp_projects_root) override this with their own monkeypatch.setenv.
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    yield
    _clear_task_env()


@pytest.fixture
def tmp_projects_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
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
