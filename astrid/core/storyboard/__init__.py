"""Storyboard v1 data layer: loader + validator (one schema authority).

North Star (ONE store / KISS): the storyboard is authored source content and
this package is the single in-repo validator shared by every consumer —
loader, compiler (``scripts/build_storyboard.py``), and CLI. No second
schema, no external dependency: plain dicts and pure-Python checks.
"""

from __future__ import annotations

from astrid.core.storyboard.loader import (
    StoryboardError,
    load_storyboard,
    validate_storyboard,
)

__all__ = [
    "StoryboardError",
    "load_storyboard",
    "validate_storyboard",
]
