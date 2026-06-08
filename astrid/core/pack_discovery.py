"""Compatibility shim — re-exports from astrid.core.pack.discovery.

After M2, the canonical location for pack discovery machinery is
``astrid.core.pack.discovery``.  This module exists so existing
``from astrid.core.pack_discovery import ...`` statements continue
to work without changes.
"""

from astrid.core.pack.discovery import (  # noqa: F401
    ASTRID_PACKS_PATH_ENV,
    SOURCE_KINDS,
    DiscoveredPack,
    discover_packs,
    discover_pack_metadata,
    discover_packs_ordered,
)

__all__ = [
    "ASTRID_PACKS_PATH_ENV",
    "SOURCE_KINDS",
    "DiscoveredPack",
    "discover_packs",
    "discover_pack_metadata",
    "discover_packs_ordered",
]
