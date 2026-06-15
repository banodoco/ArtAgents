"""Optional Arnold integration for Astrid.

This package provides a generic :class:`AstridStepInvocationAdapter` that wraps
Astrid's ``run_executor`` and registers with Arnold's
``StepInvocationAdapterRegistry``.  It is the sole integration surface between
Astrid and Arnold — Arnold is imported *only* inside this package, and normal
Astrid CLI / core startup paths never trigger an Arnold import.

If Arnold is not installed, importing this package raises an ``ImportError``
with installation instructions.  The rest of Astrid remains fully functional
without Arnold.

**Import boundary (settled):** The ``host/`` subpackage must be importable
without triggering an Arnold import.  To support this, the top-level
``arnold/__init__.py`` uses lazy imports via ``__getattr__``.  Importing the
package (e.g. as a side-effect of importing a subpackage) no longer triggers
an Arnold import.  The step-adapter symbols are only resolved when accessed
by name.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "AstridStepInvocationAdapter",
    "install_astrid_step_adapter",
]

_LAZY_SYMBOLS: dict[str, str] = {
    "AstridStepInvocationAdapter": "astrid.core.integrations.arnold.step_adapter",
    "install_astrid_step_adapter": "astrid.core.integrations.arnold.step_adapter",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_SYMBOLS:
        module_name = _LAZY_SYMBOLS[name]
        mod = importlib.import_module(module_name)
        attr = getattr(mod, name)
        # Cache on the module so subsequent access doesn't re-import
        globals()[name] = attr
        return attr
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )
