"""User + workspace config readers (delegate until m6).

Per-user config lives at ``~/.astrid/config.json``; the per-workspace
override lives at ``<cwd>/.astrid/config.json``. Workspace wins for
defaults that overlap (per the brief). Neither auto-attaches — they only
feed the suggestion shown by ``astrid status`` when unbound.

Schema (additive; unknown keys preserved): ``{"default_project": <slug>,
"default_timeline": <slug>}``.

The retained read/write logic now lives in :mod:`astrid.core.preferences`
(m4 plan step 5, task T6B). This module delegates to it so existing callers
keep their import paths until the m6 teardown removes this session-layer
module entirely.
"""

from __future__ import annotations

from pathlib import Path

from astrid.core.preferences import (
    ConfigError,
    load_user_config,
    load_workspace_config,
    resolve_default_project,
    resolve_default_timeline,
    set_default_project,
)

__all__ = [
    "ConfigError",
    "load_user_config",
    "load_workspace_config",
    "resolve_default_project",
    "resolve_default_project_for_sdk",
    "resolve_default_timeline",
    "set_default_project",
]


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
