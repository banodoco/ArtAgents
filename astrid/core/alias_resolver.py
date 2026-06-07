"""Compatibility shim — re-exports from astrid.core.pack.alias_resolver.

After M2, the canonical location for the capability alias resolver is
``astrid.core.pack.alias_resolver``.  This module exists so existing
``from astrid.core.alias_resolver import ...`` statements continue
to work without changes.
"""

from astrid.core.pack.alias_resolver import (  # noqa: F401
    AliasResolutionError,
    AliasResolver,
    _register_pack_aliases,
    create_shared_alias_resolver,
    extract_pack_aliases,
)

__all__ = [
    "AliasResolutionError",
    "AliasResolver",
    "_register_pack_aliases",
    "create_shared_alias_resolver",
    "extract_pack_aliases",
]
