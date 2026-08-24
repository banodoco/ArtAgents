"""Kernel-owned, file-side, non-authoritative user/workspace preferences.

(m4 plan step 5, task T6B.) This module is the canonical home for the
retained read/write of the per-user and per-workspace ``config.json``
preference files that previously lived in
:mod:`astrid.core.session.config`. The session module now delegates here
until its m6 teardown.

The store is deliberately **non-authoritative**: it persists only a
``default_project`` suggestion and is never consulted as identity or
authority. Resolution order is frozen as

    explicit option  >  workspace ``.astrid/config.json``  >  user ``~/.astrid/config.json``

so an explicit ``--project``/client selection always wins, a workspace
default wins over the user default, and a prior ``projects select`` (which
writes the workspace ``default_project``) is consumed by later invocations
that resolve through :func:`resolve_default_project`.

No database mutation, receipt, or sidecar authority exists here: these are
plain JSON files read and written atomically, and the kernel database is
never touched by any function in this module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import ProjectJsonError, read_json, write_json_atomic
from astrid.core.foundation.user_paths import user_config_path, workspace_config_path

__all__ = [
    "ConfigError",
    "load_user_config",
    "load_workspace_config",
    "resolve_default_project",
    "resolve_default_project_info",
    "resolve_default_timeline",
    "set_default_project",
]


class ConfigError(ValueError):
    """Raised when a preference file is malformed."""

    def __init__(
        self,
        message: str,
        *,
        scope: str | None = None,
        path: str | Path | None = None,
    ) -> None:
        self.scope = scope
        self.path = str(path) if path is not None else None
        super().__init__(message)


def _load(path: Path, *, scope: str) -> dict[str, Any]:
    try:
        raw = read_json(path)
    except FileNotFoundError:
        return {}
    except ProjectJsonError as exc:
        raise ConfigError(
            f"invalid {scope} preference JSON",
            scope=scope,
            path=path,
        ) from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must be a JSON object", scope=scope, path=path)
    return dict(raw)


def load_user_config() -> dict[str, Any]:
    """Return the parsed per-user preference object (``{}`` when absent)."""
    return _load(user_config_path(), scope="user")


def load_workspace_config(cwd: str | Path | None = None) -> dict[str, Any]:
    """Return the parsed per-workspace preference object (``{}`` when absent)."""
    return _load(workspace_config_path(cwd), scope="workspace")


def _require_default_project(
    value: Any,
    *,
    scope: str | None = None,
    path: str | Path | None = None,
) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError(
            "default_project must be a non-empty string",
            scope=scope,
            path=path,
        )
    return value


def resolve_default_project(
    cwd: str | Path | None = None,
    *,
    explicit: str | None = None,
) -> str | None:
    """Resolve the default project with explicit > workspace > user precedence.

    An explicit option (``--project`` or an explicit client selection) always
    wins; otherwise the workspace ``config.json`` overrides the user
    ``config.json``. Returns ``None`` when nothing is configured, and raises
    :class:`ConfigError` when a configured value is not a non-empty string.
    """
    if explicit is not None:
        return _require_default_project(explicit)
    info = resolve_default_project_info(cwd, explicit=explicit)
    return None if info is None else str(info["ref"])


def resolve_default_project_info(
    cwd: str | Path | None = None,
    *,
    explicit: str | None = None,
) -> dict[str, str] | None:
    """Return the selected project ref plus the scope that supplied it.

    Workspace preferences deterministically override user preferences. The
    returned ``path`` is the canonical preference file path, making selection
    provenance inspectable without exposing file contents as authority.
    """
    if explicit is not None:
        return {"ref": _require_default_project(explicit), "scope": "explicit"}
    workspace = load_workspace_config(cwd)
    value = workspace.get("default_project")
    if value is not None:
        preference_path = workspace_config_path(cwd).resolve()
        return {
            "ref": _require_default_project(
                value, scope="workspace", path=preference_path
            ),
            "scope": "workspace",
            "path": str(preference_path),
        }
    user = load_user_config()
    value = user.get("default_project")
    if value is not None:
        return {
            "ref": _require_default_project(
                value, scope="user", path=user_config_path()
            ),
            "scope": "user",
            "path": str(user_config_path()),
        }
    return None


def set_default_project(
    slug: str | None,
    *,
    scope: str = "workspace",
    cwd: str | Path | None = None,
) -> Path:
    """Set or clear the default project in user or workspace config.

    Persists **only** the ``default_project`` key (unknown keys are preserved,
    additive). ``scope`` is intentionally explicit at the write boundary —
    ``"workspace"`` (the ``select`` default) or ``"user"``. Returns the path
    written.
    """
    path = _config_path_for_scope(scope, cwd)
    try:
        payload = _load(path, scope=scope)
    except ConfigError:
        # An explicit select is the supported repair route for a corrupt
        # preference file.  The old bytes are not safely mergeable, so replace
        # them with a minimal valid config containing the requested selection.
        payload = {}
    if slug is None:
        payload.pop("default_project", None)
    else:
        payload["default_project"] = _require_default_project(slug)
    write_json_atomic(path, payload)
    return path


def resolve_default_timeline(cwd: str | Path | None = None) -> str | None:
    """Resolve the configured default timeline (workspace over user)."""
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
