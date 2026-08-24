"""Filesystem path helpers for the session layer.

``ASTRID_HOME`` env var overrides the default ``~/.astrid`` root so tests can
sandbox session/identity state without touching the real home directory.
"""

from __future__ import annotations

from pathlib import Path

from astrid.core.foundation.user_paths import (
    ASTRID_HOME_ENV,
    ASTRID_PROJECTS_ROOT_ENV,
    ASTRID_WORKSPACE_CONFIG_DIR_ENV,
    USER_CONFIG_FILENAME,
    WORKSPACE_CONFIG_DIRNAME,
    WORKSPACE_CONFIG_FILENAME,
    astrid_home,
    user_config_path,
    workspace_config_path,
)

SESSIONS_DIRNAME = "sessions"
IDENTITY_FILENAME = "identity.json"
PACKS_DIRNAME = "packs"

__all__ = [
    "ASTRID_HOME_ENV",
    "ASTRID_PROJECTS_ROOT_ENV",
    "ASTRID_WORKSPACE_CONFIG_DIR_ENV",
    "IDENTITY_FILENAME",
    "PACKS_DIRNAME",
    "SESSIONS_DIRNAME",
    "USER_CONFIG_FILENAME",
    "WORKSPACE_CONFIG_DIRNAME",
    "WORKSPACE_CONFIG_FILENAME",
    "astrid_home",
    "identity_path",
    "installed_packs_root",
    "session_path",
    "sessions_dir",
    "user_config_path",
    "workspace_config_path",
]


def sessions_dir() -> Path:
    return astrid_home() / SESSIONS_DIRNAME


def session_path(session_id: str) -> Path:
    return sessions_dir() / f"{session_id}.json"


def identity_path() -> Path:
    return astrid_home() / IDENTITY_FILENAME


def installed_packs_root() -> Path:
    """Return the per-user installed packs directory (honors ``ASTRID_HOME``)."""
    return astrid_home() / PACKS_DIRNAME
