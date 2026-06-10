"""StyleScope — scoped theme resolution (tier-3).

Registers the ``"style"`` scope key against ``SCOPE_REGISTRY`` at import
time so the runner can resolve theme configuration without depending on
ambient global state.

Resolution precedence mirrors the S0 spike
(``astrid.core._spike.scoped_config_spike``):

1. ``scope.explicit`` — caller-supplied theme path/name (highest priority).
2. ``scope.env`` — the ``HYPE_ACTIVE_THEME`` environment variable.
3. ``scope.project_slug`` — project-binding via
   ``astrid.core.project.project.get_project_theme``.
4. ``None`` — no theme resolved.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.contracts.scoped_config import (
    SCOPE_REGISTRY,
    ScopedConfig,
    ScopeRequest,
)
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

    # 3. Project binding (lazy import to avoid tier-2 cycles).
    if request.project_slug:
        from astrid.core.project.project import get_project_theme

        theme = get_project_theme(request.project_slug)
        if theme:
            return StyleScope(theme_dir=_resolve_raw_theme_dir(theme))

    # 4. Nothing resolved.
    return StyleScope(theme_dir=None)


# Self-register at import time.
SCOPE_REGISTRY.register("style", resolve_style_scope)
