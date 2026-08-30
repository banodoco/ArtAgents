"""Core Astrid framework modules.

The package root is intentionally lazy.  Importing a transport-facing module
such as :mod:`astrid.core.gateway` must not pull the retired installed-pack
store (and therefore ``sqlite3``) into the normal Astrid process graph.
"""

from __future__ import annotations

_EXPORTS = {
    "AliasResolutionError": ("astrid.core.pack.alias_resolver", "AliasResolutionError"),
    "AliasResolver": ("astrid.core.pack.alias_resolver", "AliasResolver"),
    "create_shared_alias_resolver": (
        "astrid.core.pack.alias_resolver",
        "create_shared_alias_resolver",
    ),
}

__all__ = [
    "AliasResolutionError",
    "AliasResolver",
    "create_shared_alias_resolver",
]


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    import importlib

    return getattr(importlib.import_module(module_name), attribute)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))
