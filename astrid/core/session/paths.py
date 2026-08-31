"""Filesystem path helpers for the session layer.

``ASTRID_HOME`` env var overrides the default ``~/.astrid`` root so tests can
sandbox session/identity state without touching the real home directory.
"""

from __future__ import annotations

from pathlib import Path

from astrid.core.foundation.user_paths import (
    ASTRID_HOME_ENV,
    ASTRID_PROJECTS_ROOT_ENV,
    astrid_home,
)

SESSIONS_DIRNAME = "sessions"
IDENTITY_FILENAME = "identity.json"

__all__ = [
    "ASTRID_HOME_ENV",
    "ASTRID_PROJECTS_ROOT_ENV",
    "IDENTITY_FILENAME",
    "SESSIONS_DIRNAME",
    "astrid_home",
    "identity_path",
    "session_path",
    "sessions_dir",
]


def sessions_dir() -> Path:
    return astrid_home() / SESSIONS_DIRNAME


def session_path(session_id: str) -> Path:
    return sessions_dir() / f"{session_id}.json"


def identity_path() -> Path:
    return astrid_home() / IDENTITY_FILENAME
