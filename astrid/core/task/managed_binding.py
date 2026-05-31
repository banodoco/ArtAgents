"""Shared helpers for managed timeline binding."""

from __future__ import annotations

from typing import Any


def is_managed_mode(args: Any) -> bool:
    """Return True when both managed timeline binding flags are present."""

    return bool(getattr(args, "project", None) and getattr(args, "timeline_slug", None))


__all__ = ["is_managed_mode"]
