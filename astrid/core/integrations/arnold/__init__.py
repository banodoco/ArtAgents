"""Optional Arnold integration for Astrid.

This package provides a generic :class:`AstridStepInvocationAdapter` that wraps
Astrid's ``run_executor`` and registers with Arnold's
``StepInvocationAdapterRegistry``.  It is the sole integration surface between
Astrid and Arnold — Arnold is imported *only* inside this package, and normal
Astrid CLI / core startup paths never trigger an Arnold import.

If Arnold is not installed, importing this package raises an ``ImportError``
with installation instructions.  The rest of Astrid remains fully functional
without Arnold.
"""

from astrid.core.integrations.arnold.step_adapter import (  # noqa: F401
    AstridStepInvocationAdapter,
    install_astrid_step_adapter,
)

__all__ = [
    "AstridStepInvocationAdapter",
    "install_astrid_step_adapter",
]
