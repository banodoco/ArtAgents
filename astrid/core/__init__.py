"""Core Astrid framework modules.

The package root is intentionally lazy.  Importing a transport-facing module
such as :mod:`astrid.core.gateway` must not pull the retired installed-pack
store (and therefore ``sqlite3``) into the normal Astrid process graph.
"""

from __future__ import annotations

import importlib

_EXPORTS = {
    "AliasResolutionError": ("astrid.core.pack.alias_resolver", "AliasResolutionError"),
    "AliasResolver": ("astrid.core.pack.alias_resolver", "AliasResolver"),
    "create_shared_alias_resolver": (
        "astrid.core.pack.alias_resolver",
        "create_shared_alias_resolver",
    ),
    # Retained as lazy migration/compatibility seams until the installed-pack
    # store is deleted from the tree.  They are never imported by the runtime
    # client, gateway, or generic host.
    "InstalledPackStore": ("astrid.core.pack.store", "InstalledPackStore"),
    "InstallRecord": ("astrid.core.pack.store", "InstallRecord"),
    "installed_pack_roots": ("astrid.core.pack.store", "installed_pack_roots"),
}

__all__ = [
    "AliasResolutionError",
    "AliasResolver",
    "InstallRecord",
    "InstalledPackStore",
    "create_shared_alias_resolver",
    "installed_pack_roots",
]


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    return getattr(importlib.import_module(module_name), attribute)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))
