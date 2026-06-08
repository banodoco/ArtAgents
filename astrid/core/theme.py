"""Theme root and styledoc validation helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from astrid.core.env_vars import ASTRID_THEMES_ROOT as THEMES_ROOT_ENV
from astrid.core.env_vars import HYPE_ACTIVE_THEME
from astrid.core.theme_schema import ThemeValidationError, load_theme

ACTIVE_THEME_ENV = HYPE_ACTIVE_THEME


def _default_themes_root() -> Path:
    # theme.py lives at astrid/core/theme.py -> parents[2] is the repo root.
    repo_root = Path(__file__).resolve().parents[2]
    if (repo_root / "pyproject.toml").is_file() or (repo_root / ".git").exists():
        return repo_root / "themes"
    return Path("~/.astrid/themes").expanduser()


DEFAULT_THEMES_ROOT = _default_themes_root()


def resolve_themes_root(root: str | Path | None = None) -> Path:
    raw = root if root is not None else os.environ.get(THEMES_ROOT_ENV)
    path = Path(raw) if raw else DEFAULT_THEMES_ROOT
    return path.expanduser().resolve()


def resolve_theme_dir(theme: str | Path | None, *, root: str | Path | None = None) -> Path | None:
    if theme is None:
        return None
    if isinstance(theme, str) and not theme:
        return None
    candidate = Path(theme).expanduser()
    if candidate.name == "theme.json":
        return candidate.parent.resolve()
    if candidate.exists():
        return (candidate if candidate.is_dir() else candidate.parent).resolve()
    return (resolve_themes_root(root) / str(theme)).resolve()


def load_theme_by_id(theme: str | Path, *, root: str | Path | None = None) -> dict[str, Any]:
    theme_dir = resolve_theme_dir(theme, root=root)
    if theme_dir is None:
        raise ThemeValidationError("theme is required")
    if not theme_dir.is_dir():
        raise ThemeValidationError(f"theme not found: {theme}")
    return load_theme(theme_dir / "theme.json")


def list_themes(*, root: str | Path | None = None) -> list[dict[str, Any]]:
    themes_root = resolve_themes_root(root)
    if not themes_root.exists():
        return []
    entries: list[dict[str, Any]] = []
    for child in sorted(themes_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        entry: dict[str, Any] = {"id": child.name, "path": str(child), "valid": False}
        try:
            theme = load_theme(child / "theme.json")
        except Exception as exc:  # noqa: BLE001
            entry["validation_error"] = str(exc)
        else:
            entry["valid"] = True
            entry["theme_id"] = theme["id"]
        entries.append(entry)
    return entries
