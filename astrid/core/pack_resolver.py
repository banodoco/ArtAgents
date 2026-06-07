"""Compatibility shim — re-exports from astrid.core.pack.resolver.

After M2, the canonical location for pack resolver machinery is
``astrid.core.pack.resolver``.  This module exists so existing
``from astrid.core.pack_resolver import ...`` statements continue
to work without changes.
"""

from astrid.core.pack.resolver import (  # noqa: F401
    CallableNotFoundError,
    PackResolver,
    PackResolverError,
    importlib_resolve,
    resolve_callable_from_metadata,
)

__all__ = [
    "CallableNotFoundError",
    "PackResolver",
    "PackResolverError",
    "importlib_resolve",
    "resolve_callable_from_metadata",
]
