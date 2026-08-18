"""References schema pack (in-tree, explicitly registered).

The references pack owns the normative ``project_references``,
``media_references``, and ``reference_links`` tables plus the namespaced
``reference.*`` vocabulary declared in ``schema-pack.yaml`` next to this
module. Every locked reference enum/check/index and kernel-currency
association (``media_id``, ``context_task_id``) is preserved verbatim.

m3 (plan step 7) ships the executable :class:`ReferenceRepository` in
``repository.py``: immutable read models, UoW-only ``create``/``archive``
commands, and transaction-free ``show``/``list`` reads over the frozen
three-table schema. The repository is kernel-writer backed (it receives the
caller's kernel :class:`~astrid.core.store.uow.UnitOfWork` and never opens
its own writer or transaction), and the composed registry owns every
declared stream/event/command name through the single explicit
``register_pack()`` path — never through discovery or the capability-pack
loader.
"""

from __future__ import annotations

from astrid.packs.references.repository import (
    MEDIA_REFERENCE_ROLES,
    PRIMARY_CANONICAL_ROLE,
    REFERENCE_ARCHIVE_COMMAND_KIND,
    REFERENCE_ARCHIVED_EVENT_KIND,
    REFERENCE_CREATE_COMMAND_KIND,
    REFERENCE_CREATED_EVENT_KIND,
    REFERENCE_KINDS,
    REFERENCE_STREAM_TYPE,
    ReferenceAlreadyExistsError,
    ReferenceArchiveReadModel,
    ReferenceArchivedError,
    ReferenceListRow,
    ReferenceMediaError,
    ReferenceMediaReadModel,
    ReferenceNotFoundError,
    ReferenceReadModel,
    ReferenceRepository,
    ReferenceRepositoryError,
    ReferenceValidationError,
)

__all__ = [
    "MEDIA_REFERENCE_ROLES",
    "PRIMARY_CANONICAL_ROLE",
    "REFERENCE_ARCHIVE_COMMAND_KIND",
    "REFERENCE_ARCHIVED_EVENT_KIND",
    "REFERENCE_CREATE_COMMAND_KIND",
    "REFERENCE_CREATED_EVENT_KIND",
    "REFERENCE_KINDS",
    "REFERENCE_STREAM_TYPE",
    "ReferenceAlreadyExistsError",
    "ReferenceArchiveReadModel",
    "ReferenceArchivedError",
    "ReferenceListRow",
    "ReferenceMediaError",
    "ReferenceMediaReadModel",
    "ReferenceNotFoundError",
    "ReferenceReadModel",
    "ReferenceRepository",
    "ReferenceRepositoryError",
    "ReferenceValidationError",
]
