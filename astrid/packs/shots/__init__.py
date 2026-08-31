"""Shots schema pack (in-tree, explicitly registered).

The shots pack owns the normative ``shots`` and ``shot_items`` tables plus
the namespaced ``shot.*`` vocabulary declared in ``schema-pack.yaml`` next
to this module. Every locked shot enum/check/index and kernel-currency
association (``media_id``) is preserved verbatim; the pack never FK's to or
imports the timeline pack.

The generated-client ``timelines shots`` product surface owns shot commands.
The historical repository implementation remains available only through an
explicit legacy/migration import; importing this package for product
discovery never loads its kernel-writer dependencies.
"""

from __future__ import annotations

from importlib import import_module

# Repository symbols remain available only for explicit legacy/migration
# callers.  Lazy loading is essential: the supported product parser and pack
# discovery must not import the retired kernel-writer repository (and hence
# SQLite) just by importing this schema-pack package.
_LEGACY_EXPORTS = {
    name: name
    for name in (
        "SHOT_ADD_ITEM_COMMAND_KIND", "SHOT_CREATE_COMMAND_KIND",
        "SHOT_CREATED_EVENT_KIND", "SHOT_ITEM_ADDED_EVENT_KIND",
        "SHOT_ITEM_REMOVED_EVENT_KIND", "SHOT_REMOVE_ITEM_COMMAND_KIND",
        "SHOT_STREAM_TYPE", "ShotAlreadyExistsError",
        "ShotItemMutationReadModel", "ShotItemNotFoundError",
        "ShotItemReadModel", "ShotListRow", "ShotMediaError",
        "ShotNotFoundError", "ShotReadModel", "ShotRepository",
        "ShotRepositoryError", "ShotValidationError",
    )
}


def __getattr__(name: str):
    """Load legacy repository symbols only after an explicit opt-in."""
    if name not in _LEGACY_EXPORTS:
        raise AttributeError(name)
    module = import_module("astrid.packs.shots.repository")
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = tuple(_LEGACY_EXPORTS)
