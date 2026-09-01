"""Shots schema pack (in-tree, explicitly registered).

The shots pack owns the normative ``shots`` and ``shot_items`` tables plus
``shot.*`` vocabulary declared by the canonical ``pack.yaml`` database
projection. Every locked shot enum/check/index and kernel-currency association
(``media_id``) is preserved verbatim; the pack never FK's to or imports the
timeline pack.

m3 (plan step 10) ships the executable :class:`ShotRepository` in
``repository.py``: immutable shot/item read models, UoW-only
``create``/``add_item``/``remove_item`` commands, and transaction-free
``show``/``list`` reads over the frozen two-table schema. The repository is
kernel-writer backed (it receives the caller's kernel
:class:`~astrid.core.store.uow.UnitOfWork` and never opens its own writer or
transaction), and the composed registry owns every declared
stream/event/command name through the single explicit ``register_pack()``
path — never through discovery or the capability-pack loader.
"""

from __future__ import annotations

from astrid.packs.shots.repository import (
    SHOT_ADD_ITEM_COMMAND_KIND,
    SHOT_CREATE_COMMAND_KIND,
    SHOT_CREATED_EVENT_KIND,
    SHOT_ITEM_ADDED_EVENT_KIND,
    SHOT_ITEM_REMOVED_EVENT_KIND,
    SHOT_REMOVE_ITEM_COMMAND_KIND,
    SHOT_STREAM_TYPE,
    ShotAlreadyExistsError,
    ShotItemMutationReadModel,
    ShotItemNotFoundError,
    ShotItemReadModel,
    ShotListRow,
    ShotMediaError,
    ShotNotFoundError,
    ShotReadModel,
    ShotRepository,
    ShotRepositoryError,
    ShotValidationError,
)

__all__ = [
    "SHOT_ADD_ITEM_COMMAND_KIND",
    "SHOT_CREATE_COMMAND_KIND",
    "SHOT_CREATED_EVENT_KIND",
    "SHOT_ITEM_ADDED_EVENT_KIND",
    "SHOT_ITEM_REMOVED_EVENT_KIND",
    "SHOT_REMOVE_ITEM_COMMAND_KIND",
    "SHOT_STREAM_TYPE",
    "ShotAlreadyExistsError",
    "ShotItemMutationReadModel",
    "ShotItemNotFoundError",
    "ShotItemReadModel",
    "ShotListRow",
    "ShotMediaError",
    "ShotNotFoundError",
    "ShotReadModel",
    "ShotRepository",
    "ShotRepositoryError",
    "ShotValidationError",
]
