"""Contracts shared by the ``rendering.timeline_visualize`` executor.

R9+ consumers can call :func:`validate_structural` before deriving a view to
collect duplicate-ID, dangling-track, and compositor timing errors.
"""

from .validate import validate_structural

__all__ = ["validate_structural"]
