"""User + workspace config readers.

Per-user config lives at ``~/.astrid/config.json``; the per-workspace
override lives at ``<cwd>/.astrid/config.json``. Workspace wins for
defaults that overlap (per the brief). Neither auto-attaches — they only
feed the suggestion shown by ``astrid status`` when unbound.

Schema (additive; unknown keys preserved): ``{"default_project": <slug>,
"default_timeline": <slug>}``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core.session.paths import user_config_path, workspace_config_path


class ConfigError(ValueError):
    """Raised when a config file is malformed."""


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


def resolve_default_project(cwd: str | Path | None = None) -> str | None:
    """Merge per-user and per-workspace defaults; workspace wins."""

    merged: dict[str, Any] = {}
    merged.update(load_user_config())
    merged.update(load_workspace_config(cwd))
    value = merged.get("default_project")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ConfigError("default_project must be a non-empty string")
    return value


def resolve_default_project_for_sdk(
    *,
    cwd: str | Path | None = None,
    projects_root: str | Path | None = None,
    fallback_slug: str = "default",
) -> str:
    """Return a runnable default project slug for SDK/CLI callers.

    This is the side-effect-controlled extraction of the gateway's stateless
    auto-bind project resolution. It may create the project directory on first
    use, but it never prints, binds a session, or mutates ``ASTRID_SESSION_ID``.
    """

    from astrid.core.foundation.project_paths import resolve_projects_root
    from astrid.core.project.project import create_project

    slug = resolve_default_project(cwd) or fallback_slug
    root = Path(projects_root) if projects_root is not None else resolve_projects_root()
    create_project(slug, exist_ok=True, root=root)
    return slug


def set_default_project(
    slug: str | None,
    *,
    scope: str = "workspace",
    cwd: str | Path | None = None,
) -> Path:
    """Set or clear the default project in user or workspace config.

    ``scope`` is intentionally explicit at the write boundary. Reads still use
    the merged user + workspace view where workspace wins.
    """

    path = _config_path_for_scope(scope, cwd)
    payload = _load(path)
    if slug is None:
        payload.pop("default_project", None)
    elif not isinstance(slug, str) or not slug:
        raise ConfigError("default_project must be a non-empty string")
    else:
        payload["default_project"] = slug
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
