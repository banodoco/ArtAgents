"""T10: Gateway status routing tests.

Verifies:
- ``astrid status --json`` without ``--project`` routes to session status JSON.
- ``astrid status --project X --json`` routes to task status JSON.
- ``astrid status`` without ``--project`` routes to session status (default prose).
- ``astrid status --project X`` routes to task status (default prose).
- ``--json`` is preserved through the gateway's arg filter.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest

from astrid.core import gateway
from astrid.core.foundation import project_paths
from astrid.core.project.project import create_project
from astrid.core.session import paths as session_paths
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.session.identity import Identity, write_identity

from contextlib import redirect_stderr, redirect_stdout


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    (tmp_path / "home").mkdir()
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    return {"home": tmp_path / "home", "projects": tmp_path / "projects"}


def _run_pipeline(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    rc = -1
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = gateway.main(argv)
        except SystemExit as exc:
            rc = int(exc.code) if isinstance(exc.code, int) else 2
    return rc, out.getvalue(), err.getvalue()


def _load_json(stdout: str) -> dict[str, object]:
    """Parse exactly one JSON object from stdout."""
    stripped = stdout.strip()
    assert stripped, f"empty stdout"
    obj = json.loads(stripped)
    assert isinstance(obj, dict)
    return obj


# ---------------------------------------------------------------------------
# Dispatch-level: _dispatch_status route selection
# ---------------------------------------------------------------------------


def test_dispatch_status_json_without_project_routes_to_session_status(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``astrid status --json`` (no --project) must hit session status JSON."""
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    create_project("demo")

    rc, stdout, stderr = _run_pipeline(["status", "--json"])

    assert rc == 0
    payload = _load_json(stdout)
    # Session status JSON uses state="no_session_bound" when unbound.
    assert payload["state"] == "no_session_bound"
    assert payload["project"] is None
    assert payload["session_id"] is None
    assert "discovered_projects" in payload
    assert "next_command" in payload


def test_dispatch_status_json_with_project_routes_to_task_status(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``astrid status --project X --json`` must hit task status JSON."""
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    # Task status with a nonexistent project should still return task-status
    # shaped JSON (state="no_active_run") with exit code 0.
    rc, stdout, stderr = _run_pipeline(["status", "--project", "missing", "--json"])

    assert rc == 0
    payload = _load_json(stdout)
    # Task status JSON for no-active-run reports state="no_active_run".
    assert payload["state"] == "no_active_run"
    assert payload["project"] == "missing"
    assert payload["run_id"] is None
    # Task status shape: has shared lifecycle fields.
    assert "schema_version" in payload


def test_dispatch_status_default_without_project_routes_to_session_prose(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``astrid status`` (no --project, no --json) hits session status prose."""
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    create_project("demo")

    rc, stdout, stderr = _run_pipeline(["status"])

    assert rc == 0
    # Session status default prose contains the unbound header.
    assert "no session bound" in stdout
    assert "recent projects:" in stdout
    assert "astrid projects select demo" in stdout


def test_dispatch_status_default_with_project_routes_to_task_prose(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``astrid status --project X`` (no --json) hits task status prose."""
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    rc, stdout, stderr = _run_pipeline(["status", "--project", "missing"])

    # Task status for no-active-run returns 1 in default mode (pre-existing
    # lifecycle behavior). The routing is correct: the output is from the
    # task status path, not session status.
    assert rc == 1
    assert "no active run" in stderr


def test_dispatch_status_project_equals_syntax_works(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``astrid status --project=missing --json`` uses = syntax for project."""
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    rc, stdout, stderr = _run_pipeline(["status", "--project=missing", "--json"])

    assert rc == 0
    payload = _load_json(stdout)
    assert payload["state"] == "no_active_run"
    assert payload["project"] == "missing"


def test_dispatch_status_help_flag_preserved(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``astrid status --help`` still prints help text via session status parser."""
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    rc, stdout, stderr = _run_pipeline(["status", "--help"])

    assert rc == 0
    assert "show this help message" in stdout.lower() or "usage:" in stdout.lower()


def test_dispatch_status_json_and_help_together(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--json`` and ``--help`` together: help wins (argparse behavior)."""
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    rc, stdout, stderr = _run_pipeline(["status", "--json", "--help"])

    # argparse prints help and exits 0 when --help is present.
    assert rc == 0
    assert "usage:" in stdout.lower() or "show this help message" in stdout.lower()
