"""Schema-validated runtime theme documents and the built-in default."""

from __future__ import annotations

from ._schema import (  # noqa: F401 — re-export for public consumers
    BUILTIN_DEFAULT_THEME,
    THEME_SCHEMA,
    ThemeValidationError,
    builtin_theme,
    load_theme,
    load_runtime_theme,
    resolve_theme_asset,
    theme_root,
    validate_theme_document,
)
