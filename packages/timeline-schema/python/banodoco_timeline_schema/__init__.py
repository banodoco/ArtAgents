"""Canonical TimelineConfig schema (Python).

`timeline.schema.json` is the single source of truth (plan-v5 B2). Python
TypedDicts in `generated.py` are a committed mirror, kept consistent by
`scripts/gen_python_types.py`; runtime validation always uses jsonschema
against the artifact via `validate.py`. There is intentionally no silent
fallback mirror — if `generated.py` is missing, importing fails loudly.
"""

from __future__ import annotations

from .generated import (
    AssetEntry,
    Theme,
    ThemeOverrides,
    TimelineClip,
    TimelineConfig,
    TimelineOutput,
)
from .materialize import OUTPUT_FILE_DEFAULT, materialize_output
from .theme import deep_merge_theme, merge_generation, resolve_theme
from .validate import load_schema, validate_timeline

__all__ = [
    "AssetEntry",
    "OUTPUT_FILE_DEFAULT",
    "Theme",
    "ThemeOverrides",
    "TimelineClip",
    "TimelineConfig",
    "TimelineOutput",
    "deep_merge_theme",
    "load_schema",
    "materialize_output",
    "merge_generation",
    "resolve_theme",
    "validate_timeline",
]
