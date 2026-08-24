"""Focused routing-preference isolation checks for disposable projects roots."""

from __future__ import annotations

from pathlib import Path

from astrid.core import preferences
from astrid.core.session import paths


def test_projects_root_is_the_default_workspace_boundary(
    tmp_path: Path, monkeypatch
) -> None:
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    monkeypatch.delenv(paths.ASTRID_WORKSPACE_CONFIG_DIR_ENV, raising=False)
    monkeypatch.setenv(paths.ASTRID_PROJECTS_ROOT_ENV, str(root_a))

    preferences.set_default_project("alpha")
    assert paths.workspace_config_path() == root_a / ".astrid" / "config.json"
    assert preferences.resolve_default_project() == "alpha"

    monkeypatch.setenv(paths.ASTRID_PROJECTS_ROOT_ENV, str(root_b))
    assert preferences.resolve_default_project() is None
    preferences.set_default_project("beta")
    assert paths.workspace_config_path() == root_b / ".astrid" / "config.json"
    assert preferences.resolve_default_project() == "beta"

    monkeypatch.setenv(paths.ASTRID_PROJECTS_ROOT_ENV, str(root_a))
    assert preferences.resolve_default_project() == "alpha"
