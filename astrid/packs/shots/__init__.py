"""Shots schema pack (in-tree, explicitly registered).

The shots pack owns the normative ``shots``, ``shot_items``, and
``shot_text_bindings`` tables plus
the namespaced ``shot.*`` vocabulary declared in ``schema-pack.yaml`` next
to this module. Every locked shot enum/check/index and kernel-currency
association (``media_id``) is preserved verbatim; the pack never FK's to or
imports the timeline pack.

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

from astrid.packs.shots.dependencies import analyze_invalidation
from astrid.packs.shots.repository import (
    SHOT_ADD_ITEM_COMMAND_KIND,
    SHOT_CANDIDATE_PROMOTED_EVENT_KIND,
    SHOT_CREATE_COMMAND_KIND,
    SHOT_CREATED_EVENT_KIND,
    SHOT_ITEM_ADDED_EVENT_KIND,
    SHOT_ITEM_REMOVED_EVENT_KIND,
    SHOT_PROMOTE_CANDIDATE_COMMAND_KIND,
    SHOT_REMOVE_ITEM_COMMAND_KIND,
    SHOT_STREAM_TYPE,
    ShotAlreadyExistsError,
    ShotCandidatePromotionReadModel,
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
from astrid.packs.shots.text_bindings import (
    MAX_SHOT_TEXT_BYTES,
    SHOT_TEXT_BINDING_APPLY_COMMAND_KIND,
    SHOT_TEXT_BINDING_CREATED_EVENT_KIND,
    SHOT_TEXT_BINDING_REBIND_COMMAND_KIND,
    SHOT_TEXT_BINDING_REBOUND_EVENT_KIND,
    SHOT_TEXT_BINDING_SET_COMMAND_KIND,
    SHOT_TEXT_BINDING_STREAM_TYPE,
    TEXT_BINDING_KINDS,
    ShotTextBinding,
    ShotTextBindingAmbiguousError,
    ShotTextBindingConflictError,
    ShotTextBindingError,
    ShotTextBindingIntegrityError,
    ShotTextBindingMediaCandidateError,
    ShotTextBindingMutation,
    ShotTextBindingNotFoundError,
    ShotTextBindingRepository,
    ShotTextBindingStaleError,
    ShotTextBindingValidationError,
    derive_text_binding_id,
    derive_text_binding_stream_id,
    freeze_text_bytes,
)

__all__ = [
    "analyze_invalidation",
    "SHOT_ADD_ITEM_COMMAND_KIND",
    "SHOT_CANDIDATE_PROMOTED_EVENT_KIND",
    "SHOT_CREATE_COMMAND_KIND",
    "SHOT_CREATED_EVENT_KIND",
    "SHOT_ITEM_ADDED_EVENT_KIND",
    "SHOT_ITEM_REMOVED_EVENT_KIND",
    "SHOT_PROMOTE_CANDIDATE_COMMAND_KIND",
    "SHOT_REMOVE_ITEM_COMMAND_KIND",
    "SHOT_STREAM_TYPE",
    "ShotAlreadyExistsError",
    "ShotCandidatePromotionReadModel",
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
    "MAX_SHOT_TEXT_BYTES",
    "SHOT_TEXT_BINDING_APPLY_COMMAND_KIND",
    "SHOT_TEXT_BINDING_CREATED_EVENT_KIND",
    "SHOT_TEXT_BINDING_REBIND_COMMAND_KIND",
    "SHOT_TEXT_BINDING_REBOUND_EVENT_KIND",
    "SHOT_TEXT_BINDING_SET_COMMAND_KIND",
    "SHOT_TEXT_BINDING_STREAM_TYPE",
    "TEXT_BINDING_KINDS",
    "ShotTextBinding",
    "ShotTextBindingAmbiguousError",
    "ShotTextBindingConflictError",
    "ShotTextBindingError",
    "ShotTextBindingIntegrityError",
    "ShotTextBindingMediaCandidateError",
    "ShotTextBindingMutation",
    "ShotTextBindingNotFoundError",
    "ShotTextBindingRepository",
    "ShotTextBindingStaleError",
    "ShotTextBindingValidationError",
    "derive_text_binding_id",
    "derive_text_binding_stream_id",
    "freeze_text_bytes",
]
