"""Implementation shared by canonical preferences and session compatibility."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core.preferences_paths import user_config_path, workspace_config_path


class ConfigError(ValueError):
    """Raised when a preference file is malformed."""


def _load(path: Path) -> dict[str, Any]:
    try:
        raw = read_json(path)
    except FileNotFoundError:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must be a JSON object")
    return dict(raw)


def load_user_config() -> dict[str, Any]:
    return _load(user_config_path())


def load_workspace_config(cwd: str | Path | None = None) -> dict[str, Any]:
    return _load(workspace_config_path(cwd))


def _require_default_project(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError("default_project must be a non-empty string")
    return value


def resolve_default_project(
    cwd: str | Path | None = None,
    *,
    explicit: str | None = None,
) -> str | None:
    if explicit is not None:
        return _require_default_project(explicit)
    merged: dict[str, Any] = {}
    merged.update(load_user_config())
    merged.update(load_workspace_config(cwd))
    value = merged.get("default_project")
    return None if value is None else _require_default_project(value)


def set_default_project(
    slug: str | None,
    *,
    scope: str = "workspace",
    cwd: str | Path | None = None,
) -> Path:
    path = _config_path_for_scope(scope, cwd)
    payload = _load(path)
    if slug is None:
        payload.pop("default_project", None)
    else:
        payload["default_project"] = _require_default_project(slug)
    write_json_atomic(path, payload)
    return path


def resolve_default_timeline(cwd: str | Path | None = None) -> str | None:
    merged: dict[str, Any] = {}
    merged.update(load_user_config())
    merged.update(load_workspace_config(cwd))
    value = merged.get("default_timeline")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ConfigError("default_timeline must be a non-empty string")
    return value


def _config_path_for_scope(scope: str, cwd: str | Path | None = None) -> Path:
    if scope == "workspace":
        return workspace_config_path(cwd)
    if scope == "user":
        return user_config_path()
    raise ConfigError("scope must be 'workspace' or 'user'")
