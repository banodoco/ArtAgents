"""Tests for project slug uniqueness enforcement at create time."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def test_second_create_same_slug_exit_code_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Running `astrid projects create` with an existing slug returns exit code 1
    (product EXIT_FAILURE) and prints a typed conflict error to stderr."""
    from astrid.core.foundation import project_paths as paths

    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(tmp_path))

    # First create succeeds.
    result1 = subprocess.run(
        [sys.executable, "-m", "astrid", "projects", "create", "demo", "--name", "Demo"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
    )
    assert result1.returncode == 0, f"first create failed: {result1.stderr}"

    # Second create with the same slug fails (slug conflict, exit 1).
    result2 = subprocess.run(
        [sys.executable, "-m", "astrid", "projects", "create", "demo", "--name", "Demo"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
    )
    assert result2.returncode == 1, (
        f"Expected exit code 1, got {result2.returncode}\n"
        f"stdout: {result2.stdout}\nstderr: {result2.stderr}"
    )
    assert "error conflict" in result2.stderr.lower(), (
        f"Expected 'error conflict' in stderr, got: {result2.stderr}"
    )


def test_different_roots_are_independent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The same slug can exist under different ASTRID_PROJECTS_ROOT values."""
    from astrid.core.foundation import project_paths as paths

    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"

    # Create under root A.
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(root_a))
    result_a = subprocess.run(
        [sys.executable, "-m", "astrid", "projects", "create", "demo", "--name", "Demo"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
    )
    assert result_a.returncode == 0, f"first create failed: {result_a.stderr}"

    # Create under root B — should succeed since roots are independent.
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(root_b))
    result_b = subprocess.run(
        [sys.executable, "-m", "astrid", "projects", "create", "demo", "--name", "Demo"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
    )
    assert result_b.returncode == 0, f"second create under different root failed: {result_b.stderr}"


def test_create_project_unique_slug_direct(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the uniqueness check directly via create_project API."""
    from astrid.core.foundation import project_paths as paths
    from astrid.core.project.project import ProjectError, create_project

    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(tmp_path))

    # First create succeeds.
    p1 = create_project("demo")
    assert p1["slug"] == "demo"

    # Second create with same slug raises ProjectError.
    with pytest.raises(ProjectError, match="already exists"):
        create_project("demo")

    # exist_ok=True should allow re-entry.
    p2 = create_project("demo", exist_ok=True)
    assert p2["slug"] == "demo"


def test_projects_ls_and_default_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The projects family lists created projects and persists a default
    project preference (create/list/select over the SDK surface)."""
    from astrid.core import gateway
    from astrid.core.foundation import project_paths as paths
    from astrid.core.preferences import resolve_default_project

    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))

    for slug in ("demo", "other"):
        rc = gateway.main(["projects", "create", slug, "--name", slug.capitalize()])
        captured = capsys.readouterr()
        assert rc == 0, f"create {slug} failed: {captured.err}"

    rc = gateway.main(["projects", "list", "--json"])
    captured = capsys.readouterr()
    assert rc == 0
    assert '"slug":"demo"' in captured.out
    assert '"slug":"other"' in captured.out

    rc = gateway.main(["projects", "select", "demo"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "slug: demo" in captured.out
    assert resolve_default_project() == "demo"


def test_projects_select_missing_configured_default_fails_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A configured default project that does not exist surfaces a clear
    typed error when addressed through the projects CLI (select)."""
    from astrid.core import gateway
    from astrid.core.foundation import project_paths as paths
    from astrid.core.session import paths as session_paths

    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".astrid").mkdir()
    monkeypatch.setenv(session_paths.ASTRID_WORKSPACE_CONFIG_DIR_ENV, str(workspace / ".astrid"))
    (workspace / ".astrid" / "config.json").write_text('{"default_project": "missing"}', encoding="utf-8")

    rc = gateway.main(["projects", "select", "missing"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "error not_found" in captured.err
