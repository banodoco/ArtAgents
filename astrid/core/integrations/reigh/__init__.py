"""Shared Reigh integration helpers for Astrid.

The package root is deliberately transport/storage-free.  Binding modules
are runtime implementations: importing either one loads the task executor,
its repositories, and (for WGP) the in-process runtime boundary.  Keeping
those imports out of this package's normal namespace means lightweight Reigh
helpers such as :mod:`env` and :mod:`task_client` remain usable by workers
without opening the local task authority.

Runtime bootstraps call :func:`register_bindings` for the bindings they will
execute.  The legacy public class imports remain compatible through
``__getattr__`` and load only the requested binding.
"""

from __future__ import annotations

from importlib import import_module
from typing import Iterable

_BINDING_MODULES: dict[str, str] = {
    "vibecomfy": "vibecomfy_binding",
    "wgp": "wgp_binding",
}
_BINDING_EXPORTS: dict[str, tuple[str, str]] = {
    "VibeComfyTaskHandler": ("vibecomfy", "VibeComfyTaskHandler"),
    "WgpTaskHandler": ("wgp", "WgpTaskHandler"),
}


def register_bindings(bindings: Iterable[str] | str | None = None) -> None:
    """Explicitly import and register the requested runtime bindings.

    ``None`` registers every declared Reigh runtime binding.  A worker or
    runtime bootstrap should pass the binding(s) it actually executes; this
    keeps unrelated WGP/Vibe dependencies out of lightweight imports while
    retaining one code-declared registration path.
    """

    if bindings is None:
        requested = tuple(_BINDING_MODULES)
    elif isinstance(bindings, str):
        requested = (bindings,)
    else:
        requested = tuple(bindings)
    unknown = [binding for binding in requested if binding not in _BINDING_MODULES]
    if unknown:
        raise ValueError(f"unknown Reigh task binding(s): {', '.join(unknown)}")
    for binding in requested:
        import_module(f"{__name__}.{_BINDING_MODULES[binding]}")


def __getattr__(name: str):
    """Lazily preserve the historical handler class exports."""

    export = _BINDING_EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    binding, attribute = export
    module = import_module(f"{__name__}.{_BINDING_MODULES[binding]}")
    value = getattr(module, attribute)
    globals()[name] = value
    return value


__all__ = ["VibeComfyTaskHandler", "WgpTaskHandler", "register_bindings"]
