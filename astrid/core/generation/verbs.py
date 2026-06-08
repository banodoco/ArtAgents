"""Lightweight generation verb registry for plugin-extensible facade verbs.

This module is intentionally import-light.  It does **not** import
``astrid.sdk`` so that plugin registration modules can call
:func:`register_verb` without creating import cycles.  The public
``GenerationFacade.__getattr__`` in ``astrid/sdk.py`` lazily imports
this module when a non-builtin verb is accessed.
"""

from __future__ import annotations

from typing import Any, Callable

_verbs: dict[str, Callable[..., Any]] = {}
_plugins_loaded: bool = False


def register_verb(name: str, handler: Callable[..., Any]) -> None:
    """Register a generation verb *handler* under *name*.

    Plugin modules call this during their registration phase.  The
    handler will be returned when a user accesses
    ``astrid.generate.<name>`` (via the facade's ``__getattr__``).

    Raises :exc:`ValueError` for reserved names (``image``, ``video``)
    and :exc:`TypeError` if *handler* is not callable.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("verb name must be a non-empty string")
    name = name.strip()
    if name in ("image", "video"):
        raise ValueError(
            f"verb name {name!r} is reserved for built-in generation methods"
        )
    if not callable(handler):
        raise TypeError(
            f"verb handler must be callable, got {type(handler).__name__}"
        )
    _verbs[name] = handler


def get_verb(name: str) -> Callable[..., Any]:
    """Retrieve a registered generation verb handler.

    Raises :exc:`KeyError` if *name* is not registered.
    """
    try:
        return _verbs[name]
    except KeyError:
        raise KeyError(
            f"generation verb {name!r} is not registered"
        ) from None


def list_verbs() -> tuple[str, ...]:
    """Return a sorted tuple of registered verb names."""
    return tuple(sorted(_verbs))


def load_generation_verb_plugins() -> None:
    """Discover and register generation verbs from pack extension metadata.

    Packs may declare verb entrypoints in their manifest under
    ``extensions.generation.verbs``.  Each entry is a mapping with
    ``name``, ``module``, and ``handler`` keys.  This function discovers
    such entries and calls :func:`register_verb` for each one whose
    handler can be imported.

    This is a no-op when called more than once (idempotent).
    """
    global _plugins_loaded
    if _plugins_loaded:
        return
    _plugins_loaded = True

    # Lazy-import pack discovery so the module is importable without
    # pulling in the full pack machinery at module level.
    from astrid.core.pack import discover_packs
    from astrid.core.pack.discovery import discover_pack_metadata
    from astrid.paths import REPO_ROOT

    for discovered in discover_pack_metadata(
        project_root=REPO_ROOT,
        discover_packs_fn=discover_packs,
    ):
        pack = discovered.pack
        generation = pack.extensions.get("generation")
        if not isinstance(generation, dict):
            continue
        verbs_entries = generation.get("verbs")
        if not isinstance(verbs_entries, list):
            continue
        for entry in verbs_entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            module_name = entry.get("module")
            handler_name = entry.get("handler")
            if not (name and module_name and handler_name):
                continue
            # Avoid re-registering already-known verbs
            if name in _verbs:
                continue
            try:
                import importlib

                mod = importlib.import_module(str(module_name))
                handler = getattr(mod, str(handler_name))
            except (ImportError, AttributeError):
                continue
            if callable(handler):
                register_verb(str(name), handler)
