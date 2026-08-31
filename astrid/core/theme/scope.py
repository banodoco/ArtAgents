"""StyleScope — scoped theme resolution (tier-3).

Registers the ``"style"`` scope key against ``SCOPE_REGISTRY`` at import
time so the runner can resolve theme configuration without depending on
ambient global state.

Resolution precedence mirrors the S0 spike
(``astrid.core._spike.scoped_config_spike``):

1. ``scope.explicit`` — caller-supplied theme path/name (highest priority).
2. ``scope.env`` — the ``HYPE_ACTIVE_THEME`` environment variable.
3. ``scope.project_style`` — runtime-provided project style snapshot.
4. ``None`` — no theme resolved.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from astrid.core.contracts.scoped_config import (
    SCOPE_REGISTRY,
    ScopedConfig,
    ScopeRequest,
)
from astrid.core.contracts.project_theme import ProjectStyleSnapshot, ProjectThemeBinding
from astrid.core.env_vars import HYPE_ACTIVE_THEME
from astrid.core.theme import resolve_theme_dir as _resolve_raw_theme_dir


@dataclass(frozen=True)
class StyleScope(ScopedConfig):
    """Resolved style-scope result.

    Carries the single resolved ``theme_dir`` (or ``None`` when no theme
    was resolved by any precedence rule).
    """

    theme_dir: Path | None = None


def resolve_style_scope(request: ScopeRequest) -> StyleScope:
    """Resolve a theme directory from a :class:`ScopeRequest`.

    Precedence: ``explicit['theme']`` > ``env['HYPE_ACTIVE_THEME']`` >
    project binding > ``None``.
    """
    # 1. Explicit caller-supplied theme.
    explicit = request.explicit
    if explicit is not None:
        theme = explicit.get("theme")
        if theme is not None:
            return StyleScope(theme_dir=_resolve_raw_theme_dir(theme))

    # 2. Environment variable (HYPE_ACTIVE_THEME).
    env = request.env
    if env is not None:
        theme = env.get(HYPE_ACTIVE_THEME)
        if theme:
            return StyleScope(theme_dir=_resolve_raw_theme_dir(theme))

    # 3. Runtime-provided project style data; project persistence is upstream.
    project_style = request.project_style
    if isinstance(project_style, ProjectThemeBinding):
        snapshot = ProjectStyleSnapshot(
            project_slug=project_style.project_slug,
            theme_id=project_style.theme_id,
        )
    elif isinstance(project_style, Mapping):
        snapshot = ProjectStyleSnapshot.from_mapping(
            project_style, project_slug=request.project_slug
        )
    else:
        snapshot = project_style
    if snapshot is not None:
        theme = snapshot.theme_dir or snapshot.theme_id
        if theme:
            return StyleScope(theme_dir=_resolve_raw_theme_dir(theme))

    # 4. Nothing resolved.
    return StyleScope(theme_dir=None)


# Self-register at import time.
SCOPE_REGISTRY.register("style", resolve_style_scope)
