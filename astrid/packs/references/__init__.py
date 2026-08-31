"""References schema pack (in-tree, explicitly registered).

The references pack owns the normative ``project_references``,
``media_references``, and ``reference_links`` tables plus the namespaced
``reference.*`` vocabulary declared in ``schema-pack.yaml`` next to this
module. Every locked reference enum/check/index and kernel-currency
association (``media_id``, ``context_task_id``) is preserved verbatim.

The generated-client ``media references`` product surface owns reference
commands. The historical repository implementation remains available only
through an explicit legacy/migration import; importing this package for
product discovery never loads its kernel-writer dependencies.
"""

from __future__ import annotations

from importlib import import_module

# The generated-client product surface uses ``references.cli`` and must not
# import this retired kernel-writer repository at parser import time.  The
# repository remains an explicit legacy/migration module for old fixtures;
# this package marker is intentionally authority-free until a caller asks for
# one of those legacy symbols explicitly.
_LEGACY_EXPORTS = {
    name: name
    for name in (
        "MEDIA_REFERENCE_ROLES", "PRIMARY_CANONICAL_ROLE",
        "REFERENCE_ARCHIVE_COMMAND_KIND", "REFERENCE_ARCHIVED_EVENT_KIND",
        "REFERENCE_UNARCHIVE_COMMAND_KIND", "REFERENCE_UNARCHIVED_EVENT_KIND",
        "REFERENCE_CREATE_COMMAND_KIND", "REFERENCE_CREATED_EVENT_KIND",
        "REFERENCE_KINDS", "REFERENCE_STREAM_TYPE",
        "ReferenceAlreadyExistsError", "ReferenceAmbiguousError",
        "ReferenceArchiveReadModel", "ReferenceArchivedError",
        "ReferenceListRow", "ReferenceMediaError", "ReferenceMediaReadModel",
        "ReferenceNotFoundError", "ReferenceReadModel", "ReferenceRepository",
        "ReferenceRepositoryError", "ReferenceUnarchiveReadModel",
        "ReferenceValidationError",
    )
}


def __getattr__(name: str):
    """Load legacy repository symbols only after an explicit opt-in."""
    if name not in _LEGACY_EXPORTS:
        raise AttributeError(name)
    module = import_module("astrid.packs.references.repository")
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = tuple(_LEGACY_EXPORTS)
