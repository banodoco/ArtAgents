"""Low-level user and workspace configuration paths.

Preference resolution and the legacy session compatibility facade both use
these pure path helpers. Keeping them below both layers prevents the
preference/session import cycle while preserving the existing environment
variables and path rules.
"""

from __future__ import annotations

import os
from pathlib import Path

ASTRID_HOME_ENV = "ASTRID_HOME"
ASTRID_WORKSPACE_CONFIG_DIR_ENV = "ASTRID_WORKSPACE_CONFIG_DIR"
ASTRID_PROJECTS_ROOT_ENV = "ASTRID_PROJECTS_ROOT"
_DEFAULT_ASTRID_HOME = Path("~/.astrid")

USER_CONFIG_FILENAME = "config.json"
WORKSPACE_CONFIG_DIRNAME = ".astrid"
WORKSPACE_CONFIG_FILENAME = "config.json"


def astrid_home() -> Path:
    """Return the per-user Astrid state directory."""

    raw = os.environ.get(ASTRID_HOME_ENV)
    base = Path(raw) if raw else _DEFAULT_ASTRID_HOME
    return base.expanduser().resolve()


def user_config_path() -> Path:
    """Return the per-user preference file path."""

    return astrid_home() / USER_CONFIG_FILENAME


def workspace_config_path(cwd: str | Path | None = None) -> Path:
    """Return the workspace preference path using the frozen boundary rules."""

    override = os.environ.get(ASTRID_WORKSPACE_CONFIG_DIR_ENV)
    if override and cwd is None:
        return Path(override).expanduser().resolve() / WORKSPACE_CONFIG_FILENAME
    if cwd is None:
        projects_root = os.environ.get(ASTRID_PROJECTS_ROOT_ENV)
        if projects_root:
            base = Path(projects_root).expanduser().resolve()
        else:
            base = Path.cwd()
    else:
        base = Path(cwd)
    return base / WORKSPACE_CONFIG_DIRNAME / WORKSPACE_CONFIG_FILENAME


__all__ = [
    "ASTRID_HOME_ENV",
    "ASTRID_PROJECTS_ROOT_ENV",
    "ASTRID_WORKSPACE_CONFIG_DIR_ENV",
    "USER_CONFIG_FILENAME",
    "WORKSPACE_CONFIG_DIRNAME",
    "WORKSPACE_CONFIG_FILENAME",
    "astrid_home",
    "user_config_path",
    "workspace_config_path",
]
