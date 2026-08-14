"""Layer-stack planner: registry support() routing into renderer-owned z-layers."""

from __future__ import annotations

from typing import Any


def plan(*args: Any, **kwargs: Any) -> Any:
    """Lazily enter the planner implementation."""

    from .run import plan as implementation

    return implementation(*args, **kwargs)


def support(*args: Any, **kwargs: Any) -> Any:
    """Lazily enter the planner support implementation."""

    from .run import support as implementation

    return implementation(*args, **kwargs)


__all__ = ["plan", "support"]
