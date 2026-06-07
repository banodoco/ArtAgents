"""Stale-pointer fixture tests for ``_most_recent_session_slug`` default-project
disambiguation (M2 / T15)."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from astrid.core.task.session_discovery import _most_recent_session_slug
from astrid.core.session import config, paths as session_paths


def _make_project(projects_root: Path, slug: str, session_id: str) -> None:
    """Create a minimal project directory with project.json and .astrid-session."""
    proj_dir = projects_root / slug
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "project.json").write_text(json.dumps({"slug": slug}), encoding="utf-8")
    (proj_dir / ".astrid-session").write_text(f"{session_id}\n", encoding="utf-8")


def _stderr_of(func, *args, **kwargs):
    """Call func, capture stderr, return (result, stderr_string)."""
    buf = StringIO()
    old = sys.stderr
    sys.stderr = buf
    try:
        result = func(*args, **kwargs)
    finally:
        sys.stderr = old
    return result, buf.getvalue()


# ---------------------------------------------------------------------------
# Single-candidate (unchanged) — baseline
# ---------------------------------------------------------------------------


def test_single_candidate_resolves_without_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    _make_project(projects_root, "demo", "S-DEMO")

    result, stderr = _stderr_of(_most_recent_session_slug, projects_root)
    assert result == "demo"
    assert stderr == ""


# ---------------------------------------------------------------------------
# Multiple candidates WITH a matching default project
# ---------------------------------------------------------------------------


def test_multiple_candidates_default_present_resolves_to_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.delenv(session_paths.ASTRID_WORKSPACE_CONFIG_DIR_ENV, raising=False)

    projects_root = tmp_path / "projects"
    _make_project(projects_root, "alpha", "S-ALPHA")
    _make_project(projects_root, "default-project", "S-DEF")
    _make_project(projects_root, "zulu", "S-ZULU")

    # Configure default project via workspace config
    ws = tmp_path / "ws"
    config.set_default_project("default-project", cwd=ws)
    monkeypatch.chdir(str(ws))

    result, stderr = _stderr_of(_most_recent_session_slug, projects_root)
    assert result == "default-project"
    assert "3 projects have a bound session on disk" in stderr
    assert "preferring configured default project 'default-project'" in stderr


def test_multiple_candidates_default_present_via_user_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    session_paths.astrid_home().mkdir(parents=True, exist_ok=True)
    session_paths.user_config_path().write_text(
        json.dumps({"default_project": "beta"}), encoding="utf-8"
    )

    projects_root = tmp_path / "projects"
    _make_project(projects_root, "alpha", "S-ALPHA")
    _make_project(projects_root, "beta", "S-BETA")
    _make_project(projects_root, "zulu", "S-ZULU")

    result, stderr = _stderr_of(_most_recent_session_slug, projects_root)
    assert result == "beta"
    assert "3 projects have a bound session on disk" in stderr
    assert "preferring configured default project 'beta'" in stderr


def test_multiple_candidates_only_two_default_among_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.delenv(session_paths.ASTRID_WORKSPACE_CONFIG_DIR_ENV, raising=False)

    projects_root = tmp_path / "projects"
    _make_project(projects_root, "alpha", "S-ALPHA")
    _make_project(projects_root, "beta", "S-BETA")

    ws = tmp_path / "ws"
    config.set_default_project("beta", cwd=ws)
    monkeypatch.chdir(str(ws))

    result, stderr = _stderr_of(_most_recent_session_slug, projects_root)
    assert result == "beta"
    assert "2 projects have a bound session on disk" in stderr
    assert "preferring configured default project 'beta'" in stderr


# ---------------------------------------------------------------------------
# Multiple candidates WITHOUT a matching default project — fail-closed
# ---------------------------------------------------------------------------


def test_multiple_candidates_no_default_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))

    projects_root = tmp_path / "projects"
    _make_project(projects_root, "alpha", "S-ALPHA")
    _make_project(projects_root, "beta", "S-BETA")
    _make_project(projects_root, "zulu", "S-ZULU")

    # No default configured
    result, stderr = _stderr_of(_most_recent_session_slug, projects_root)
    assert result is None
    assert "3 projects have a bound session on disk" in stderr
    assert "refusing to guess" in stderr
    assert "--project alpha" in stderr
    assert "--project beta" in stderr
    assert "--project zulu" in stderr


def test_multiple_candidates_default_not_among_candidates_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.delenv(session_paths.ASTRID_WORKSPACE_CONFIG_DIR_ENV, raising=False)

    projects_root = tmp_path / "projects"
    _make_project(projects_root, "alpha", "S-ALPHA")
    _make_project(projects_root, "beta", "S-BETA")

    # Default is configured but not among the candidates
    ws = tmp_path / "ws"
    config.set_default_project("gamma", cwd=ws)
    monkeypatch.chdir(str(ws))

    result, stderr = _stderr_of(_most_recent_session_slug, projects_root)
    assert result is None
    assert "2 projects have a bound session on disk" in stderr
    assert "refusing to guess" in stderr
    assert "--project alpha" in stderr
    assert "--project beta" in stderr


def test_multiple_candidates_default_present_but_no_project_json_in_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Edge case: only one valid project-dir candidate among multiple
    directories, so len(candidates) == 1 — should resolve normally."""
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))

    projects_root = tmp_path / "projects"
    _make_project(projects_root, "alpha", "S-ALPHA")
    # beta has .astrid-session but no project.json — skipped by _make_project
    # Actually, _make_project creates project.json. Let's make a directory
    # without project.json manually.
    beta_dir = projects_root / "beta"
    beta_dir.mkdir(parents=True, exist_ok=True)
    (beta_dir / ".astrid-session").write_text("S-BETA\n", encoding="utf-8")
    # No project.json for beta — it should be excluded by the walk

    result, stderr = _stderr_of(_most_recent_session_slug, projects_root)
    # Only alpha is a valid candidate (has project.json + .astrid-session)
    assert result == "alpha"
    assert stderr == ""


# ---------------------------------------------------------------------------
# Zero candidates
# ---------------------------------------------------------------------------


def test_no_candidates_returns_none(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    result, stderr = _stderr_of(_most_recent_session_slug, projects_root)
    assert result is None
    assert stderr == ""
