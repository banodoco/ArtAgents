"""Path helpers shared by the preference and session compatibility layers."""

from __future__ import annotations

import os
from pathlib import Path

ASTRID_HOME_ENV = "ASTRID_HOME"
ASTRID_WORKSPACE_CONFIG_DIR_ENV = "ASTRID_WORKSPACE_CONFIG_DIR"
_DEFAULT_ASTRID_HOME = Path("~/.astrid")


def astrid_home() -> Path:
    raw = os.environ.get(ASTRID_HOME_ENV)
    base = Path(raw) if raw else _DEFAULT_ASTRID_HOME
    return base.expanduser().resolve()


def user_config_path() -> Path:
    return astrid_home() / "config.json"


def workspace_config_path(cwd: str | Path | None = None) -> Path:
    override = os.environ.get(ASTRID_WORKSPACE_CONFIG_DIR_ENV)
    if override and cwd is None:
        return Path(override).expanduser().resolve() / "config.json"
    base = Path(cwd) if cwd is not None else Path.cwd()
    return base / ".astrid" / "config.json"


__all__ = ["astrid_home", "user_config_path", "workspace_config_path"]
