"""Compatibility shim — re-exports from astrid.core.pack.override.

After M2, the canonical location for the override store is
``astrid.core.pack.override``.  This module exists so existing
``from astrid.core.override import ...`` statements continue
to work without changes.
"""

from astrid.core.pack.override import (  # noqa: F401
    OverrideStore,
    OverrideStoreError,
)

__all__ = [
    "OverrideStore",
    "OverrideStoreError",
]
