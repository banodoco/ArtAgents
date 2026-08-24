"""Filesystem path helpers for the session layer.

``ASTRID_HOME`` env var overrides the default ``~/.astrid`` root so tests can
sandbox session/identity state without touching the real home directory.
"""

from __future__ import annotations

import os
from pathlib import Path

ASTRID_HOME_ENV = "ASTRID_HOME"
ASTRID_WORKSPACE_CONFIG_DIR_ENV = "ASTRID_WORKSPACE_CONFIG_DIR"
ASTRID_PROJECTS_ROOT_ENV = "ASTRID_PROJECTS_ROOT"
_DEFAULT_ASTRID_HOME = Path("~/.astrid")

SESSIONS_DIRNAME = "sessions"
IDENTITY_FILENAME = "identity.json"
USER_CONFIG_FILENAME = "config.json"
WORKSPACE_CONFIG_DIRNAME = ".astrid"
WORKSPACE_CONFIG_FILENAME = "config.json"
PACKS_DIRNAME = "packs"


def astrid_home() -> Path:
    """Return the per-user Astrid state directory (honors ``ASTRID_HOME``)."""

    raw = os.environ.get(ASTRID_HOME_ENV)
    base = Path(raw) if raw else _DEFAULT_ASTRID_HOME
    return base.expanduser().resolve()


def sessions_dir() -> Path:
    return astrid_home() / SESSIONS_DIRNAME


def session_path(session_id: str) -> Path:
    return sessions_dir() / f"{session_id}.json"


def identity_path() -> Path:
    return astrid_home() / IDENTITY_FILENAME


def user_config_path() -> Path:
    return astrid_home() / USER_CONFIG_FILENAME


def workspace_config_path(cwd: str | Path | None = None) -> Path:
    override = os.environ.get(ASTRID_WORKSPACE_CONFIG_DIR_ENV)
    if override and cwd is None:
        return Path(override).expanduser().resolve() / WORKSPACE_CONFIG_FILENAME
    if cwd is None:
        projects_root = os.environ.get(ASTRID_PROJECTS_ROOT_ENV)
        if projects_root:
            # A selected project is a workspace preference. When the caller
            # explicitly isolates the kernel with ASTRID_PROJECTS_ROOT, use
            # that root as the workspace boundary too; otherwise two roots
            # launched from one checkout would overwrite one another's
            # selection file.
            base = Path(projects_root).expanduser().resolve()
        else:
            base = Path.cwd()
    else:
        base = Path(cwd)
    return base / WORKSPACE_CONFIG_DIRNAME / WORKSPACE_CONFIG_FILENAME


def installed_packs_root() -> Path:
    """Return the per-user installed packs directory (honors ``ASTRID_HOME``)."""
    return astrid_home() / PACKS_DIRNAME
