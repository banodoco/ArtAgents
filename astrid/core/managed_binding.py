"""Managed timeline binding helpers for pack entrypoints.

The former task-mode implementation lived in the retired task runtime's
managed-binding module; the single helper is inlined here for the pack
executors that still honor managed timeline binding.
"""

from __future__ import annotations

from typing import Any


def is_managed_mode(args: Any) -> bool:
    """Return True when both managed timeline binding flags are present."""

    return bool(getattr(args, "project", None) and getattr(args, "timeline_slug", None))


__all__ = ["is_managed_mode"]
