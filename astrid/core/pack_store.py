"""Compatibility shim — re-exports from astrid.core.pack.store.

After M2, the canonical location for pack store machinery is
``astrid.core.pack.store``.  This module exists so existing
``from astrid.core.pack_store import ...`` statements continue
to work without changes.
"""

from astrid.core.pack.store import (  # noqa: F401
    InstallRecord,
    InstalledPackStore,
    _revision_timestamp,
    installed_pack_roots,
)

__all__ = [
    "InstallRecord",
    "InstalledPackStore",
    "_revision_timestamp",
    "installed_pack_roots",
]
