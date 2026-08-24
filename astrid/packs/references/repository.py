"""References repository: immutable reference lifecycle reads, create, and
soft archive (m3 plan step 7, T8).

The references pack's first complete repository vertical lives in this module
(``astrid/packs/references/repository.py``). It follows the kernel and
timeline repository shape — one writer transaction per command, typed errors,
frozen read models, transaction-free reads — over the frozen three-table
schema (``project_references``, ``media_references``, ``reference_links``).

:meth:`ReferenceRepository.create` is one complete command inside the
caller's single ``BEGIN IMMEDIATE`` unit of work:

1. validates the frozen reference facts (closed ``kind`` vocabulary,
   non-empty trimmed ``name``, object ``metadata``, same-project primary
   canonical media id) and runs the receipt idempotency gate first;
2. rejects a duplicate reference identity before any allocation
   (:class:`ReferenceAlreadyExistsError`) and rejects missing or foreign
   media before any allocation (:class:`ReferenceMediaError`);
3. atomically inserts the pack-owned ``reference.reference`` event stream,
   the ``project_references`` row (active: ``archived_at`` NULL), the exact
   ``media_references`` row (role ``canonical``, ordinal 0, ``is_primary``
   1), appends the hash-chained ``reference.created`` event, and records the
   complete receipt — returning the immutable :class:`ReferenceReadModel`
   carrying the primary canonical media association.

:meth:`ReferenceRepository.archive` is the receipt-backed soft archive: it
sets ``archived_at`` (and refreshes ``updated_at``), appends one
``reference.archived`` event, and records the complete receipt **without**
deleting or cascading any association, link, event, media row, or byte. The
result carries the preserved row counts so callers can prove non-cascading
archive. An already-archived reference rejects further mutation with
:class:`ReferenceArchivedError`, and a missing/foreign reference raises
:class:`ReferenceNotFoundError` — both before any write.

Reads are transaction-free on a separate read-only connection: :meth:`show`
is the direct historical lookup that **always** returns archived references
(SD1 — archive hides rows only from ordinary lists), and :meth:`list` hides
archived rows by default while ``include_archived=True`` is the explicit
inclusive list that preserves history.

The repository is stateless apart from the kernel event append and receipt
services; every command must run inside the caller's
:class:`astrid.core.store.uow.UnitOfWork`.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from astrid.core.events.service import ACTOR_KINDS, EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
    parse_json,
    request_hash,
)
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.errors import RepositoryError
from astrid.core.repositories.projects import ProjectNotFoundError
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.util.time import utc_now_iso

REFERENCE_STREAM_TYPE = "reference.reference"
"""The pack stream type every reference aggregate owns (one per reference)."""

REFERENCE_CREATED_EVENT_KIND = "reference.created"
"""The m3 event kind emitted by reference creation.

Carries the frozen reference facts plus the exact primary canonical media
association (``media_reference_id``, ``media_id``, role ``canonical``,
ordinal 0, ``is_primary`` true), so the event log alone reconstructs the
reference's identity and its initial media association.
"""

REFERENCE_ARCHIVED_EVENT_KIND = "reference.archived"
"""The m3 event kind emitted by the receipt-backed soft archive."""

REFERENCE_UNARCHIVED_EVENT_KIND = "reference.unarchived"
"""The recovery event emitted when an archived reference becomes active."""

REFERENCE_UPDATED_EVENT_KIND = "reference.updated"
"""The m4 event kind emitted by the receipt-backed mutable update (plan step 14).

Carries only the mutable semantic fields that changed (``name``,
``description``, ``metadata``) plus the refreshed ``updated_at``. ``kind``
and ``project_id`` are immutable and never appear in the payload; the
receipt's request hash binds the exact requested delta so replay and
mismatch-before-mutation hold across identical and changed updates.
"""

REFERENCE_CREATE_COMMAND_KIND = "reference.create"
"""The m3 command kind that reference-create receipts are keyed on."""

REFERENCE_ARCHIVE_COMMAND_KIND = "reference.archive"
"""The m3 command kind that reference-archive receipts are keyed on."""

REFERENCE_UNARCHIVE_COMMAND_KIND = "reference.unarchive"
"""The recovery command that makes an archived reference active again."""

REFERENCE_UPDATE_COMMAND_KIND = "reference.update"
"""The m4 command kind that reference-update receipts are keyed on (plan
step 14): mutable name/description/metadata updates while project and kind
stay immutable."""

REFERENCE_ASSOCIATE_COMMAND_KIND = "reference.associate"
"""The m3 command kind that single and bulk media-association receipts are
keyed on (one receipt-backed command kind for both shapes)."""

REFERENCE_SET_PRIMARY_COMMAND_KIND = "reference.set_primary"
"""The m3 command kind that reference primary-replacement receipts are keyed
on."""

REFERENCE_LINK_COMMAND_KIND = "reference.link"
"""The m3 command kind that reference-link receipts are keyed on."""

REFERENCE_LINKED_EVENT_KIND = "reference.linked"
"""The m3 event kind emitted by a typed reference-link command.

Appended on the *from* reference's own stream (for ``related_to`` the
canonical ``min(id)`` side), carrying the stored row facts — both affected
reference ids, the kind, and the metadata — so the exact edge is
reconstructable from the log alone.
"""

REFERENCE_MEDIA_ASSOCIATED_EVENT_KIND = "reference.media_associated"
"""The m3 event kind emitted by a media association command.

Carries every expanded association (``media_reference_id``, ``media_id``,
``role``, ``context_task_id``, ``ordinal``, ``is_primary``) so no
association is ever inherited invisibly by variants or later outputs.
"""

REFERENCE_PRIMARY_CHANGED_EVENT_KIND = "reference.primary_changed"
"""The m3 event kind emitted by a primary-replacement command.

Carries the previous and new primary canonical identities (association id
plus media id) so the replacement is fully reconstructable from the log.
"""

REFERENCE_KINDS: tuple[str, ...] = (
    "character",
    "place",
    "object",
    "clothing",
    "other",
)
"""The frozen ``project_references.kind`` DDL CHECK vocabulary, in DDL order."""

MEDIA_REFERENCE_ROLES: tuple[str, ...] = (
    "canonical",
    "used_as_input",
    "depicts",
    "inspired_by",
)
"""The frozen ``media_references.role`` DDL CHECK vocabulary, in DDL order."""

PRIMARY_CANONICAL_ROLE = "canonical"
"""The only role that may carry ``is_primary = 1`` (DDL CHECK)."""

CONTEXT_ROLES: tuple[str, ...] = ("used_as_input", "inspired_by")
"""The only roles that may carry a ``context_task_id`` (DDL CHECK)."""

CONTEXT_REQUIRED_ROLE = "used_as_input"
"""The only role that **must** carry a ``context_task_id`` (DDL CHECK)."""

REFERENCE_LINK_KINDS: tuple[str, ...] = (
    "belongs_to",
    "wears",
    "located_in",
    "associated_with",
    "related_to",
)
"""The frozen ``reference_links.kind`` DDL CHECK vocabulary, in DDL order."""

REFERENCE_SYMMETRIC_LINK_KIND = "related_to"
"""The only symmetric reference link kind (SD2).

``related_to`` links are stored in canonical ``min(id)``/``max(id)`` order
so reversed requests converge on the same row; every other frozen kind
preserves its submitted direction.
"""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ReferenceRepositoryError(RepositoryError):
    """Base error for the reference repository family.

    Subclasses :class:`astrid.core.repositories.errors.RepositoryError`
    (and therefore :class:`astrid.core.store.writer.WriterError`), so the
    kernel store error family catches reference contract violations too.
    """


class ReferenceValidationError(ReferenceRepositoryError):
    """Raised when a reference argument violates a frozen contract."""


class ReferenceAlreadyExistsError(ReferenceRepositoryError):
    """Raised when create targets an already-existing reference id."""

    def __init__(self, *, reference_id: str) -> None:
        self.reference_id: str = reference_id
        super().__init__(f"reference already exists: {reference_id!r}")


class ReferenceNotFoundError(ReferenceRepositoryError):
    """Raised when a read or command targets an unknown/foreign reference."""

    def __init__(self, *, reference_id: str, project_id: str, detail: str = "missing") -> None:
        self.reference_id: str = reference_id
        self.project_id: str = project_id
        self.detail: str = detail
        super().__init__(f"unknown reference {reference_id!r} in project {project_id!r}")


class ReferenceAmbiguousError(ReferenceRepositoryError):
    """Raised when a project-local recovery name matches multiple references."""

    def __init__(self, *, ref: str, candidate_ids: Sequence[str]) -> None:
        self.ref = ref
        self.candidate_ids = tuple(str(value) for value in candidate_ids)
        super().__init__(
            f"reference name {ref!r} is ambiguous; use one of these ids: "
            + ", ".join(self.candidate_ids)
        )


class ReferenceArchivedError(ReferenceRepositoryError):
    """Raised when a command mutates an already-archived reference.

    Archive is soft: while ``archived_at`` is set, no active mutation may
    touch the reference. Explicit unarchive restores the mutable state.
    """

    def __init__(self, *, reference_id: str) -> None:
        self.reference_id: str = reference_id
        super().__init__(f"reference is archived and cannot be mutated: {reference_id!r}")


class ReferenceMediaError(ReferenceRepositoryError):
    """Raised when a create names missing or foreign media.

    ``detail`` is one of ``"missing"`` (no media row) or ``"foreign"`` (the
    media row belongs to another project). Rejected before any allocation.
    """

    def __init__(self, *, media_id: str, project_id: str, detail: str) -> None:
        self.media_id: str = media_id
        self.project_id: str = project_id
        self.detail: str = detail
        super().__init__(f"reference media {media_id!r} is {detail} for project {project_id!r}")


class ReferenceAssociationError(ReferenceRepositoryError):
    """Raised when an association command violates a frozen cross-table rule.

    ``detail`` is a stable machine-readable code:

    - ``"bad_role"`` — ``role`` is outside the frozen DDL vocabulary;
    - ``"bad_ordinal"`` — a non-canonical ordinal is not a non-negative int;
    - ``"context_not_permitted"`` — a ``context_task_id`` was supplied for a
      role outside the DDL-approved ``used_as_input``/``inspired_by`` pair;
    - ``"missing_context"`` — ``used_as_input`` named no context task;
    - ``"missing_media"`` / ``"foreign_media"`` — the media row is absent or
      belongs to another project;
    - ``"missing_task"`` / ``"foreign_task"`` — the context task is absent or
      belongs to another project;
    - ``"task_did_not_produce_media"`` — the context task did not produce the
      exact associated media through ``task_outputs``;
    - ``"duplicate"`` — the same (media, role[, context]) association already
      exists for the reference.

    All of these are rejected **before any write**, so a failing association
    changes zero rows.
    """

    def __init__(
        self,
        *,
        detail: str,
        reference_id: str | None = None,
        project_id: str | None = None,
        media_id: str | None = None,
        role: str | None = None,
        context_task_id: str | None = None,
    ) -> None:
        self.detail: str = detail
        self.reference_id: str | None = reference_id
        self.project_id: str | None = project_id
        self.media_id: str | None = media_id
        self.role: str | None = role
        self.context_task_id: str | None = context_task_id
        super().__init__(f"reference association rejected: {detail}")


class ReferencePrimaryError(ReferenceRepositoryError):
    """Raised when ``set_primary`` targets an invalid primary candidate.

    ``detail`` is one of ``"missing_primary"`` (the reference has no primary
    canonical — an impossible-but-guarded corruption), ``"not_found"`` (the
    association id does not exist), ``"foreign"`` (the association belongs to
    another reference), or ``"not_canonical"`` (the association's role is not
    ``canonical``, so it can never carry ``is_primary``). Rejected before any
    write.
    """

    def __init__(
        self,
        *,
        detail: str,
        reference_id: str | None = None,
        media_reference_id: str | None = None,
        role: str | None = None,
    ) -> None:
        self.detail: str = detail
        self.reference_id: str | None = reference_id
        self.media_reference_id: str | None = media_reference_id
        self.role: str | None = role
        super().__init__(f"reference primary change rejected: {detail}")


class ReferenceLinkError(ReferenceRepositoryError):
    """Raised when a link command violates a frozen cross-reference rule.

    ``detail`` is a stable machine-readable code:

    - ``"bad_kind"`` — ``kind`` is outside the frozen five-kind vocabulary;
    - ``"self_link"`` — ``from_reference_id`` equals ``to_reference_id``
      (the DDL ``from_reference_id <> to_reference_id`` CHECK);
    - ``"missing_from"`` / ``"missing_to"`` — an endpoint reference row is
      absent;
    - ``"foreign_from"`` / ``"foreign_to"`` — an endpoint reference belongs
      to another project (cross-project pair);
    - ``"archived_from"`` / ``"archived_to"`` — an endpoint reference is
      archived (archive blocks new active mutations, SD1);
    - ``"duplicate"`` — the exact stored edge (canonical pair for
      ``related_to``, directional pair otherwise) already exists;
    - ``"bad_metadata"`` — ``metadata`` is not a JSON object.

    All of these are rejected **before any write**, so a failing link
    changes zero rows.
    """

    def __init__(
        self,
        *,
        detail: str,
        from_reference_id: str | None = None,
        to_reference_id: str | None = None,
        kind: str | None = None,
    ) -> None:
        self.detail: str = detail
        self.from_reference_id: str | None = from_reference_id
        self.to_reference_id: str | None = to_reference_id
        self.kind: str | None = kind
        super().__init__(f"reference link rejected: {detail}")


# ---------------------------------------------------------------------------
# Frozen read models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReferenceMediaReadModel:
    """One immutable ``media_references`` association (m3 plan step 7).

    ``is_primary`` is a boolean projection of the DDL integer flag; exactly
    one canonical association per active reference carries it.
    """

    id: str
    media_id: str
    role: str
    context_task_id: str | None
    ordinal: int
    is_primary: bool
    metadata: Mapping[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted in events and receipts."""
        return {
            "id": self.id,
            "media_id": self.media_id,
            "role": self.role,
            "context_task_id": self.context_task_id,
            "ordinal": self.ordinal,
            "is_primary": self.is_primary,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReferenceMediaReadModel:
        """Rebuild the frozen media association from a stored mapping."""
        return cls(
            id=str(value["id"]),
            media_id=str(value["media_id"]),
            role=str(value["role"]),
            context_task_id=value.get("context_task_id"),
            ordinal=int(value["ordinal"]),
            is_primary=bool(value.get("is_primary", False)),
            metadata=dict(value.get("metadata") or {}),
            created_at=str(value["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class ReferenceReadModel:
    """One immutable reference read model (m3 plan step 7).

    A frozen projection of one ``project_references`` row plus the ordered
    ``media_references`` associations and the reference stream head.
    ``media`` is ordered by role, then ordinal, then id; a freshly created
    reference carries exactly one primary canonical association.
    """

    id: str
    project_id: str
    kind: str
    name: str
    description: str
    metadata: Mapping[str, Any]
    created_at: str
    updated_at: str
    archived_at: str | None
    event_head_seq: int
    media: tuple[ReferenceMediaReadModel, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "kind": self.kind,
            "name": self.name,
            "description": self.description,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived_at": self.archived_at,
            "event_head_seq": self.event_head_seq,
            "media": [entry.to_dict() for entry in self.media],
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReferenceReadModel:
        """Rebuild the frozen reference read model from a stored mapping."""
        return cls(
            id=str(value["id"]),
            project_id=str(value["project_id"]),
            kind=str(value["kind"]),
            name=str(value["name"]),
            description=str(value.get("description") or ""),
            metadata=dict(value.get("metadata") or {}),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
            archived_at=value.get("archived_at"),
            event_head_seq=int(value["event_head_seq"]),
            media=tuple(
                ReferenceMediaReadModel.from_mapping(entry) for entry in (value.get("media") or [])
            ),
        )


@dataclass(frozen=True, slots=True)
class ReferenceListRow:
    """One sorted reference list row (m3 plan step 7).

    The default list hides archived references (``archived_at`` NULL only);
    ``include_archived=True`` is the explicit inclusive list that preserves
    history. Rows are ordered by kind, then name, then id (the frozen
    ``references_project_kind`` index shape).
    """

    id: str
    project_id: str
    kind: str
    name: str
    archived_at: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict for callers."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "kind": self.kind,
            "name": self.name,
            "archived_at": self.archived_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReferenceListRow:
        """Rebuild the frozen list row from a stored mapping."""
        return cls(
            id=str(value["id"]),
            project_id=str(value["project_id"]),
            kind=str(value["kind"]),
            name=str(value["name"]),
            archived_at=value.get("archived_at"),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
        )


@dataclass(frozen=True, slots=True)
class ReferenceArchiveReadModel:
    """One immutable soft-archive result (m3 plan step 7).

    ``preserved`` carries the exact counts of the rows the archive left
    untouched — ``media_references`` associations, ``reference_links``
    edges, and ``events`` on the reference's own stream — so non-cascading
    archive is provable from the receipt alone.
    """

    reference_id: str
    project_id: str
    archived_at: str
    preserved: Mapping[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "reference_id": self.reference_id,
            "project_id": self.project_id,
            "archived_at": self.archived_at,
            "preserved": dict(self.preserved),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReferenceArchiveReadModel:
        """Rebuild the frozen archive result from a stored mapping."""
        return cls(
            reference_id=str(value["reference_id"]),
            project_id=str(value["project_id"]),
            archived_at=str(value["archived_at"]),
            preserved={
                str(key): int(count) for key, count in (value.get("preserved") or {}).items()
            },
        )


@dataclass(frozen=True, slots=True)
class ReferenceUnarchiveReadModel:
    """Recovery result with explicit safe repeat-call status."""

    reference_id: str
    project_id: str
    status: str
    changed: bool
    unarchived_at: str | None
    preserved: Mapping[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "project_id": self.project_id,
            "status": self.status,
            "changed": self.changed,
            "unarchived_at": self.unarchived_at,
            "preserved": dict(self.preserved),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReferenceUnarchiveReadModel:
        return cls(
            reference_id=str(value["reference_id"]),
            project_id=str(value["project_id"]),
            status=str(value.get("status") or "active"),
            changed=bool(value.get("changed", True)),
            unarchived_at=value.get("unarchived_at"),
            preserved={
                str(key): int(count) for key, count in (value.get("preserved") or {}).items()
            },
        )


@dataclass(frozen=True, slots=True)
class ReferenceAssociateReadModel:
    """One immutable association-command result (m3 plan step 8).

    ``associations`` carries every expanded association — one entry for a
    single ``associate``, all entries for an explicit bulk associate — each
    with its allocated ``media_reference_id``, media id, role, context task,
    ordinal, and primary flag, so no association is ever inherited invisibly.
    """

    reference_id: str
    project_id: str
    associations: tuple[ReferenceMediaReadModel, ...]
    event_head_seq: int

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "reference_id": self.reference_id,
            "project_id": self.project_id,
            "associations": [entry.to_dict() for entry in self.associations],
            "event_head_seq": self.event_head_seq,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReferenceAssociateReadModel:
        """Rebuild the frozen association result from a stored mapping."""
        return cls(
            reference_id=str(value["reference_id"]),
            project_id=str(value["project_id"]),
            associations=tuple(
                ReferenceMediaReadModel.from_mapping(entry)
                for entry in (value.get("associations") or [])
            ),
            event_head_seq=int(value["event_head_seq"]),
        )


@dataclass(frozen=True, slots=True)
class ReferencePrimaryChangeReadModel:
    """One immutable primary-replacement result (m3 plan step 8).

    ``previous_primary`` and ``new_primary`` each carry the canonical
    association id plus its media id, so the exact replacement is provable
    from the receipt without re-reading the projection.
    """

    reference_id: str
    project_id: str
    previous_primary: Mapping[str, Any]
    new_primary: Mapping[str, Any]
    event_head_seq: int

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "reference_id": self.reference_id,
            "project_id": self.project_id,
            "previous_primary": dict(self.previous_primary),
            "new_primary": dict(self.new_primary),
            "event_head_seq": self.event_head_seq,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReferencePrimaryChangeReadModel:
        """Rebuild the frozen primary-change result from a stored mapping."""
        return cls(
            reference_id=str(value["reference_id"]),
            project_id=str(value["project_id"]),
            previous_primary=dict(value.get("previous_primary") or {}),
            new_primary=dict(value.get("new_primary") or {}),
            event_head_seq=int(value["event_head_seq"]),
        )


@dataclass(frozen=True, slots=True)
class ReferenceLinkReadModel:
    """One immutable typed-link result (m3 plan step 9).

    Carries the **stored** row facts: for ``related_to`` the pair is the
    canonical ``min(id)``/``max(id)`` order (SD2), so reversed requests
    converge on one result; for every other kind the submitted direction is
    preserved. ``event_head_seq`` is the from-reference stream head after the
    ``reference.linked`` event.
    """

    from_reference_id: str
    to_reference_id: str
    kind: str
    metadata: Mapping[str, Any]
    created_at: str
    event_head_seq: int

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "from_reference_id": self.from_reference_id,
            "to_reference_id": self.to_reference_id,
            "kind": self.kind,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "event_head_seq": self.event_head_seq,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReferenceLinkReadModel:
        """Rebuild the frozen link result from a stored mapping."""
        return cls(
            from_reference_id=str(value["from_reference_id"]),
            to_reference_id=str(value["to_reference_id"]),
            kind=str(value["kind"]),
            metadata=dict(value.get("metadata") or {}),
            created_at=str(value["created_at"]),
            event_head_seq=int(value["event_head_seq"]),
        )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ReferenceValidationError(f"{name} must be a non-empty string")
    return value


def _resolve_reference_id(uow: UnitOfWork, *, project_id: str, ref: str) -> str:
    """Resolve an exact id first, then one exact project-local name.

    Mutations use the same addressing contract as ``show`` and ``unarchive``:
    a name is only a convenience when it identifies exactly one row.  The
    lookup is deliberately completed before request hashing or any write so a
    foreign/missing ref or an ambiguous name cannot partially mutate state.
    """
    ref = _require_non_empty_string("reference_id", ref)
    row = uow.query_one(
        "SELECT id FROM project_references WHERE id = ? AND project_id = ?",
        (ref, project_id),
    )
    if row is not None:
        return str(row["id"])
    foreign = uow.query_one("SELECT id FROM project_references WHERE id = ?", (ref,))
    if foreign is not None:
        raise ReferenceNotFoundError(
            reference_id=ref, project_id=project_id, detail="foreign"
        )
    matches = uow.query(
        "SELECT id FROM project_references WHERE project_id = ? AND name = ? ORDER BY id ASC",
        (project_id, ref),
    )
    if len(matches) > 1:
        raise ReferenceAmbiguousError(
            ref=ref, candidate_ids=[str(match["id"]) for match in matches]
        )
    if not matches:
        raise ReferenceNotFoundError(
            reference_id=ref, project_id=project_id, detail="missing"
        )
    return str(matches[0]["id"])


def _resolve_reference_id_if_present(
    uow: UnitOfWork, *, project_id: str, ref: str
) -> str:
    """Resolve a present reference without turning a missing target into an error.

    Receipt-backed mutations must be able to compute their request identity
    before enforcing target existence: a changed request under an existing
    idempotency key must fail with ``ReceiptMismatchError`` even when the new
    target does not exist.  The command's normal pre-write fence calls
    :func:`_resolve_reference_id` afterwards and therefore retains the typed
    missing/foreign/ambiguous errors for a fresh key.
    """
    row = uow.query_one(
        "SELECT id FROM project_references WHERE id = ? AND project_id = ?",
        (ref, project_id),
    )
    if row is not None:
        return str(row["id"])
    matches = uow.query(
        "SELECT id FROM project_references WHERE project_id = ? AND name = ? ORDER BY id ASC",
        (project_id, ref),
    )
    if len(matches) == 1:
        return str(matches[0]["id"])
    # Keep an absent, foreign, or ambiguous address in the request identity;
    # the normal command fence will issue the precise typed rejection after
    # the receipt gate.
    return ref


def _parse_object(raw: str, *, label: str, subject: str) -> dict[str, Any]:
    """Parse one stored JSON object canonically, rejecting non-objects."""
    try:
        parsed = parse_json(raw)
    except CanonicalizationError as exc:
        raise ReferenceRepositoryError(
            f"{label} {subject!r} has invalid stored JSON: {exc}"
        ) from exc
    if not isinstance(parsed, Mapping):
        raise ReferenceRepositoryError(f"{label} {subject!r} stored JSON is not an object")
    return dict(parsed)


def _normalize_association_entry(entry: Any) -> dict[str, Any]:
    """Validate and normalize one association spec before any write.

    Returns a dict with keys ``media_id``, ``role``, ``context_task_id``,
    ``ordinal``, and ``metadata``. Canonical entries carry ``ordinal=None``
    (the deterministic canonical ordinal is derived later, from the current
    canonical max); every other role carries a resolved non-negative int.
    Role/context interaction is enforced here (``context_task_id`` only for
    the DDL-approved ``used_as_input``/``inspired_by`` pair, and required for
    ``used_as_input``), matching the frozen DDL CHECKs.
    """
    if not isinstance(entry, Mapping):
        raise ReferenceValidationError("association must be a JSON object")
    media_id = _require_non_empty_string("association.media_id", entry.get("media_id"))
    role = _require_non_empty_string("association.role", entry.get("role"))
    if role not in MEDIA_REFERENCE_ROLES:
        raise ReferenceAssociationError(detail="bad_role", role=role)
    context_task_id = entry.get("context_task_id")
    if context_task_id is not None:
        context_task_id = _require_non_empty_string("association.context_task_id", context_task_id)
    if context_task_id is not None and role not in CONTEXT_ROLES:
        raise ReferenceAssociationError(
            detail="context_not_permitted", role=role, context_task_id=context_task_id
        )
    if role == CONTEXT_REQUIRED_ROLE and context_task_id is None:
        raise ReferenceAssociationError(detail="missing_context", role=role)
    metadata = entry.get("metadata")
    if metadata is None:
        metadata_dict: dict[str, Any] = {}
    elif isinstance(metadata, Mapping):
        metadata_dict = dict(metadata)
    else:
        raise ReferenceValidationError("association.metadata must be a JSON object")
    ordinal = entry.get("ordinal")
    if role == PRIMARY_CANONICAL_ROLE:
        resolved_ordinal: int | None = None
    elif ordinal is None:
        resolved_ordinal = 0
    elif isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
        raise ReferenceAssociationError(detail="bad_ordinal", role=role)
    else:
        resolved_ordinal = ordinal
    return {
        "media_id": media_id,
        "role": role,
        "context_task_id": context_task_id,
        "ordinal": resolved_ordinal,
        "metadata": metadata_dict,
    }


def _next_canonical_ordinal(uow: UnitOfWork, reference_id: str) -> int:
    """Return the next deterministic canonical ordinal for a reference.

    The first canonical (created with the reference) holds ordinal 0; each
    subsequent canonical association takes ``max(ordinal) + 1``, which the
    ``reference_canonical_ordinal`` partial unique index guarantees stays
    collision-free.
    """
    row = uow.query_one(
        "SELECT COALESCE(MAX(ordinal), -1) + 1 AS nxt FROM media_references "
        "WHERE reference_id = ? AND role = ?",
        (reference_id, PRIMARY_CANONICAL_ROLE),
    )
    return int(row["nxt"])


def _build_reference_read_model(
    uow: UnitOfWork, *, project_id: str, reference_id: str
) -> ReferenceReadModel:
    """Rebuild the frozen reference read model inside the active UoW.

    Joins the current ``project_references`` row, the reference stream head,
    and the ordered ``media_references`` associations (role, then ordinal,
    then id), so the model reflects every change the caller's command just
    committed in this transaction. Raises :class:`ReferenceNotFoundError`
    for a missing or foreign reference.
    """
    row = uow.query_one(
        "SELECT r.*, s.head_seq FROM project_references r "
        "JOIN event_streams s ON s.id = ? "
        "WHERE r.id = ? AND r.project_id = ?",
        (f"{reference_id}:{REFERENCE_STREAM_TYPE}", reference_id, project_id),
    )
    if row is None:
        raise ReferenceNotFoundError(reference_id=reference_id, project_id=project_id)
    media_rows = uow.query(
        "SELECT * FROM media_references WHERE reference_id = ? "
        "ORDER BY role ASC, ordinal ASC, id ASC",
        (reference_id,),
    )
    media = tuple(
        ReferenceMediaReadModel(
            id=str(m["id"]),
            media_id=str(m["media_id"]),
            role=str(m["role"]),
            context_task_id=m["context_task_id"],
            ordinal=int(m["ordinal"]),
            is_primary=bool(m["is_primary"]),
            metadata=_parse_object(
                str(m["metadata_json"]),
                label="media association",
                subject=str(m["id"]),
            ),
            created_at=str(m["created_at"]),
        )
        for m in media_rows
    )
    return ReferenceReadModel(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        kind=str(row["kind"]),
        name=str(row["name"]),
        description=str(row["description"]),
        metadata=_parse_object(
            str(row["metadata_json"]),
            label="reference",
            subject=str(row["id"]),
        ),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        archived_at=row["archived_at"],
        event_head_seq=int(row["head_seq"]),
        media=media,
    )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class ReferenceRepository:
    """Stateless reference command/read surface over the kernel unit of work.

    Composes the kernel event append and receipt services. A single instance
    is safe to share across command callers; every command must run inside
    the caller's :class:`astrid.core.store.uow.UnitOfWork` and every read
    runs transaction-free on a separate read-only connection.
    """

    def __init__(
        self,
        events: EventAppendService,
        receipts: ReceiptService,
    ) -> None:
        self._events = events
        self._receipts = receipts

    # -- create ------------------------------------------------------------

    def create(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        kind: str,
        name: str,
        media_id: str,
        description: str = "",
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str,
        actor_kind: str = "local",
        reference_id: str | None = None,
        created_at: str | None = None,
        command_kind: str = REFERENCE_CREATE_COMMAND_KIND,
    ) -> ReferenceReadModel:
        """Create one active reference with its primary canonical media atomically.

        Inside the caller's active unit of work this commits, in one
        ``BEGIN IMMEDIATE`` transaction: the ``reference.reference`` event
        stream, the ``project_references`` row (active, ``archived_at``
        NULL), the exact primary canonical ``media_references`` row (role
        ``canonical``, ordinal 0, ``is_primary`` 1) for the same-project
        media id, the hash-chained ``reference.created`` event, both heads,
        and one complete receipt.

        Rejections happen **before any allocation**: an empty or whitespace
        name, a kind outside the frozen vocabulary, non-object metadata, a
        missing project (:class:`ProjectNotFoundError`), a duplicate
        reference identity (:class:`ReferenceAlreadyExistsError`), and
        missing or foreign media (:class:`ReferenceMediaError`) all change
        zero rows. Idempotency mirrors the kernel commands: the receipt gate
        runs first, an identical retry returns exactly the stored result
        with zero new rows, and a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        kind = _require_non_empty_string("kind", kind)
        name = _require_non_empty_string("name", name)
        media_id = _require_non_empty_string("media_id", media_id)
        idempotency_key = _require_non_empty_string("idempotency_key", idempotency_key)
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if kind not in REFERENCE_KINDS:
            raise ReferenceValidationError(
                f"kind must be one of {sorted(REFERENCE_KINDS)}, got {kind!r}"
            )
        if not name.strip():
            raise ReferenceValidationError(
                "name must contain at least one non-whitespace character"
            )
        if not isinstance(description, str):
            raise ReferenceValidationError("description must be a string")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ReferenceValidationError("metadata must be a JSON object")
        if actor_kind not in ACTOR_KINDS:
            raise ReferenceValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, got {actor_kind!r}"
            )
        if reference_id is None:
            reference_id = generate_lowercase_ulid()
        else:
            _require_non_empty_string("reference_id", reference_id)
        metadata_dict = dict(metadata) if metadata is not None else {}

        # Semantic request identity: stable id, kind, name, description,
        # metadata, and the exact primary canonical media all participate;
        # generated values (timestamps, transaction ids) are excluded.
        request: dict[str, Any] = {
            "project_id": project_id,
            "reference_id": reference_id,
            "kind": kind,
            "name": name,
            "description": description,
            "metadata": metadata_dict,
            "media_id": media_id,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ReferenceValidationError(f"cannot hash reference create request: {exc}") from exc

        # Idempotency gate first: replay or mismatch before any mutation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return ReferenceReadModel.from_mapping(replayed)

        # The project must exist before any stream/row insert.
        if uow.query_one("SELECT id FROM projects WHERE id = ?", (project_id,)) is None:
            raise ProjectNotFoundError(project_id=project_id)

        # Duplicate identity rejection before allocation.
        if (
            uow.query_one(
                "SELECT id FROM project_references WHERE id = ?",
                (reference_id,),
            )
            is not None
        ):
            raise ReferenceAlreadyExistsError(reference_id=reference_id)

        # Same-project media: missing and foreign media change zero rows.
        media_row = uow.query_one(
            "SELECT id, project_id FROM media WHERE id = ?",
            (media_id,),
        )
        if media_row is None:
            raise ReferenceMediaError(media_id=media_id, project_id=project_id, detail="missing")
        if str(media_row["project_id"]) != project_id:
            raise ReferenceMediaError(media_id=media_id, project_id=project_id, detail="foreign")

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ReferenceValidationError("created_at must be a non-empty string")
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        media_reference_id = generate_lowercase_ulid()
        stream_id = f"{reference_id}:{REFERENCE_STREAM_TYPE}"

        try:
            metadata_json = canonical_json(metadata_dict)
        except CanonicalizationError as exc:
            raise ReferenceValidationError(
                f"cannot canonicalize reference metadata: {exc}"
            ) from exc

        # 1. The reference.reference stream (head_seq 0; the append advances
        #    it to 1 in the same transaction).
        uow.execute(
            "INSERT INTO event_streams "
            "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (stream_id, project_id, REFERENCE_STREAM_TYPE, reference_id, stamp),
        )
        # 2. The active project_references projection.
        uow.execute(
            "INSERT INTO project_references "
            "(id, project_id, kind, name, description, metadata_json, "
            "created_at, updated_at, archived_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                reference_id,
                project_id,
                kind,
                name,
                description,
                metadata_json,
                stamp,
                stamp,
            ),
        )
        # 3. The exact primary canonical media association.
        uow.execute(
            "INSERT INTO media_references "
            "(id, reference_id, media_id, role, context_task_id, ordinal, "
            "is_primary, metadata_json, created_at) "
            "VALUES (?, ?, ?, 'canonical', NULL, 0, 1, '{}', ?)",
            (media_reference_id, reference_id, media_id, stamp),
        )
        # 4. The hash-chained reference.created event carrying the frozen
        #    facts and the exact primary canonical association.
        media_entry: dict[str, Any] = {
            "media_reference_id": media_reference_id,
            "media_id": media_id,
            "role": PRIMARY_CANONICAL_ROLE,
            "context_task_id": None,
            "ordinal": 0,
            "is_primary": True,
        }
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=REFERENCE_CREATED_EVENT_KIND,
            data={
                "reference_id": reference_id,
                "kind": kind,
                "name": name,
                "description": description,
                "metadata": metadata_dict,
                "media": media_entry,
            },
            changes=[
                "reference_id",
                "kind",
                "name",
                "description",
                "metadata",
                "media",
            ],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 5. The complete receipt with the full read model.
        read_model = ReferenceReadModel(
            id=reference_id,
            project_id=project_id,
            kind=kind,
            name=name,
            description=description,
            metadata=metadata_dict,
            created_at=stamp,
            updated_at=stamp,
            archived_at=None,
            event_head_seq=append.stream_seq,
            media=(
                ReferenceMediaReadModel(
                    id=media_reference_id,
                    media_id=media_id,
                    role=PRIMARY_CANONICAL_ROLE,
                    context_task_id=None,
                    ordinal=0,
                    is_primary=True,
                    metadata={},
                    created_at=stamp,
                ),
            ),
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=read_model.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return read_model

    # -- soft archive ------------------------------------------------------

    def archive(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        reference_id: str,
        idempotency_key: str,
        actor_kind: str = "local",
        now: str | None = None,
        command_kind: str = REFERENCE_ARCHIVE_COMMAND_KIND,
    ) -> ReferenceArchiveReadModel:
        """Soft-archive one reference atomically, preserving every byte.

        Inside the caller's active unit of work this sets ``archived_at``
        (and refreshes ``updated_at``) on the ``project_references`` row,
        appends the hash-chained ``reference.archived`` event on the
        reference's own stream, and records one complete receipt carrying
        the preserved association/link/event counts. No association, link,
        event, media row, or byte is deleted or cascaded (SD1).

        Rejections happen **before any write**: a missing or foreign
        reference raises :class:`ReferenceNotFoundError`, and an
        already-archived reference raises :class:`ReferenceArchivedError`
        until it is explicitly unarchived. Idempotency mirrors the kernel
        commands: the receipt gate
        runs first, an identical retry returns exactly the stored archive
        result with zero new rows, and a changed request under the same key
        raises :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        reference_id = _require_non_empty_string("reference_id", reference_id)
        idempotency_key = _require_non_empty_string("idempotency_key", idempotency_key)
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise ReferenceValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, got {actor_kind!r}"
            )
        reference_id = _resolve_reference_id_if_present(
            uow, project_id=project_id, ref=reference_id
        )

        # Semantic request identity: reference/project only; generated
        # values never participate.
        request: dict[str, Any] = {
            "project_id": project_id,
            "reference_id": reference_id,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ReferenceValidationError(f"cannot hash reference archive request: {exc}") from exc

        # Idempotency gate first: replay or mismatch before any mutation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return ReferenceArchiveReadModel.from_mapping(replayed)

        # Resolve the public address only after the idempotency gate.  This
        # preserves mismatch-before-mutation for a changed target, including
        # a target that is missing or foreign in the current project.
        reference_id = _resolve_reference_id(
            uow, project_id=project_id, ref=reference_id
        )

        # Fences before any write: the reference exists in the project and
        # is still active.
        row = uow.query_one(
            "SELECT * FROM project_references WHERE id = ? AND project_id = ?",
            (reference_id, project_id),
        )
        if row is None:
            raise ReferenceNotFoundError(reference_id=reference_id, project_id=project_id)
        if row["archived_at"] is not None:
            raise ReferenceArchivedError(reference_id=reference_id)

        # Preserved counts prove non-cascading archive from the receipt.
        preserved = {
            "media_references": int(
                uow.query_one(
                    "SELECT count(*) AS n FROM media_references WHERE reference_id = ?",
                    (reference_id,),
                )["n"]
            ),
            "reference_links": int(
                uow.query_one(
                    "SELECT count(*) AS n FROM reference_links "
                    "WHERE from_reference_id = ? OR to_reference_id = ?",
                    (reference_id, reference_id),
                )["n"]
            ),
            "events": int(
                uow.query_one(
                    "SELECT count(*) AS n FROM events e "
                    "JOIN event_streams s ON s.id = e.stream_id "
                    "WHERE s.aggregate_id = ? AND s.stream_type = ?",
                    (reference_id, REFERENCE_STREAM_TYPE),
                )["n"]
            ),
        }

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ReferenceValidationError("now must be a non-empty string")
        txn_id = uuid.uuid4().hex
        stream_id = f"{reference_id}:{REFERENCE_STREAM_TYPE}"

        # 1. The soft-archive projection write (archived_at + updated_at).
        uow.execute(
            "UPDATE project_references SET archived_at = ?, updated_at = ? "
            "WHERE id = ? AND project_id = ? AND archived_at IS NULL",
            (stamp, stamp, reference_id, project_id),
        )
        # 2. The hash-chained reference.archived event on the own stream.
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=REFERENCE_ARCHIVED_EVENT_KIND,
            data={
                "reference_id": reference_id,
                "archived_at": stamp,
                "preserved": preserved,
            },
            changes=["reference_id", "archived_at", "preserved"],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=uuid.uuid4().hex,
            created_at=stamp,
        )
        # 3. The complete receipt.
        result = ReferenceArchiveReadModel(
            reference_id=reference_id,
            project_id=project_id,
            archived_at=stamp,
            preserved=preserved,
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=result.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return result

    def unarchive(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        ref: str,
        idempotency_key: str,
        actor_kind: str = "local",
        now: str | None = None,
        command_kind: str = REFERENCE_UNARCHIVE_COMMAND_KIND,
    ) -> ReferenceUnarchiveReadModel:
        """Restore an archived reference without changing identity or links.

        ``ref`` prefers an exact id, then an exact project-local display name.
        A duplicate name fails with explicit candidate ids. Repeating the
        command on an active reference succeeds as a ``changed=false`` no-op.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        ref = _require_non_empty_string("ref", ref)
        idempotency_key = _require_non_empty_string("idempotency_key", idempotency_key)
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise ReferenceValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, got {actor_kind!r}"
            )

        row = uow.query_one(
            "SELECT * FROM project_references WHERE id = ? AND project_id = ?",
            (ref, project_id),
        )
        if row is None:
            matches = uow.query(
                "SELECT * FROM project_references "
                "WHERE project_id = ? AND name = ? ORDER BY id ASC",
                (project_id, ref),
            )
            if len(matches) > 1:
                raise ReferenceAmbiguousError(
                    ref=ref, candidate_ids=[str(match["id"]) for match in matches]
                )
            if not matches:
                raise ReferenceNotFoundError(reference_id=ref, project_id=project_id)
            row = matches[0]
        reference_id = str(row["id"])

        request = {"project_id": project_id, "reference_id": reference_id}
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ReferenceValidationError(
                f"cannot hash reference unarchive request: {exc}"
            ) from exc
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return ReferenceUnarchiveReadModel.from_mapping(replayed)

        stream_id = f"{reference_id}:{REFERENCE_STREAM_TYPE}"
        event_count = int(
            uow.query_one(
                "SELECT count(*) AS n FROM events WHERE stream_id = ?",
                (stream_id,),
            )["n"]
        )
        preserved = {
            "media_references": int(
                uow.query_one(
                    "SELECT count(*) AS n FROM media_references WHERE reference_id = ?",
                    (reference_id,),
                )["n"]
            ),
            "reference_links": int(
                uow.query_one(
                    "SELECT count(*) AS n FROM reference_links "
                    "WHERE from_reference_id = ? OR to_reference_id = ?",
                    (reference_id, reference_id),
                )["n"]
            ),
            "events": event_count,
        }

        if row["archived_at"] is None:
            last = uow.query_one(
                "SELECT created_at FROM events WHERE stream_id = ? AND kind = ? "
                "ORDER BY seq DESC LIMIT 1",
                (stream_id, REFERENCE_UNARCHIVED_EVENT_KIND),
            )
            return ReferenceUnarchiveReadModel(
                reference_id=reference_id,
                project_id=project_id,
                status="active",
                changed=False,
                unarchived_at=str(last["created_at"]) if last is not None else None,
                preserved=preserved,
            )

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ReferenceValidationError("now must be a non-empty string")
        changed = uow.execute(
            "UPDATE project_references SET archived_at = NULL, updated_at = ? "
            "WHERE id = ? AND project_id = ? AND archived_at IS NOT NULL",
            (stamp, reference_id, project_id),
        ).rowcount
        if changed != 1:
            raise ReferenceRepositoryError(f"reference {reference_id!r} changed during unarchive")
        txn_id = uuid.uuid4().hex
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=REFERENCE_UNARCHIVED_EVENT_KIND,
            data={
                "reference_id": reference_id,
                "unarchived_at": stamp,
                "preserved": {**preserved, "events": event_count + 1},
            },
            changes=["reference_id", "unarchived_at", "preserved"],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=uuid.uuid4().hex,
            created_at=stamp,
        )
        result = ReferenceUnarchiveReadModel(
            reference_id=reference_id,
            project_id=project_id,
            status="active",
            changed=True,
            unarchived_at=stamp,
            preserved={**preserved, "events": event_count + 1},
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=result.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return result

    # -- mutable update (m4 plan step 14) -----------------------------------

    def update(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        reference_id: str,
        name: str | None = None,
        description: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str,
        actor_kind: str = "local",
        now: str | None = None,
        command_kind: str = REFERENCE_UPDATE_COMMAND_KIND,
    ) -> ReferenceReadModel:
        """Mutate a reference's name/description/metadata atomically.

        Inside the caller's active unit of work this refreshes only the
        **mutable** semantic fields on the ``project_references`` row
        (``name``, ``description``, ``metadata_json``) and ``updated_at``,
        appends one hash-chained ``reference.updated`` event on the
        reference's own stream, advances both heads, and records one
        complete receipt carrying the refreshed read model. ``kind`` and
        ``project_id`` are immutable and never change; a supplied ``kind``
        is not even an accepted argument, so the frozen DDL CHECK vocabulary
        is preserved by construction.

        Each of ``name``/``description``/``metadata`` is an optional delta:
        ``None`` means "leave unchanged", and a provided metadata mapping is
        shallow-merged into the current object (an explicit empty
        ``metadata`` mapping clears it). An empty/whitespace ``name`` is
        rejected (as at create).

        Rejections happen **before any write**: a missing or foreign
        reference raises :class:`ReferenceNotFoundError`, and an archived
        reference raises :class:`ReferenceArchivedError` until explicit
        recovery. Idempotency mirrors the other commands: the
        receipt gate runs first, an identical retry returns exactly the
        stored result with zero new rows, and a changed delta under the same
        key raises :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        reference_id = _require_non_empty_string("reference_id", reference_id)
        idempotency_key = _require_non_empty_string("idempotency_key", idempotency_key)
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise ReferenceValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, got {actor_kind!r}"
            )
        reference_id = _resolve_reference_id(
            uow, project_id=project_id, ref=reference_id
        )
        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise ReferenceValidationError(
                    "name must contain at least one non-whitespace character"
                )
        if description is not None and not isinstance(description, str):
            raise ReferenceValidationError("description must be a string")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ReferenceValidationError("metadata must be a JSON object")
        metadata_delta = dict(metadata) if metadata is not None else None

        # Semantic request identity: the exact requested delta. None fields
        # mean "unchanged", so an identical retry replays and any changed
        # delta under the same key mismatches before mutation.
        request: dict[str, Any] = {
            "project_id": project_id,
            "reference_id": reference_id,
            "name": name,
            "description": description,
            "metadata": metadata_delta,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ReferenceValidationError(f"cannot hash reference update request: {exc}") from exc

        # Idempotency gate first: replay or mismatch before any mutation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return ReferenceReadModel.from_mapping(replayed)

        # Fences before any write: the reference exists in the project and
        # is still active.
        row = uow.query_one(
            "SELECT name, description, metadata_json, archived_at "
            "FROM project_references WHERE id = ? AND project_id = ?",
            (reference_id, project_id),
        )
        if row is None:
            raise ReferenceNotFoundError(reference_id=reference_id, project_id=project_id)
        if row["archived_at"] is not None:
            raise ReferenceArchivedError(reference_id=reference_id)

        current_metadata = _parse_object(
            str(row["metadata_json"]),
            label="reference",
            subject=reference_id,
        )
        new_name = name if name is not None else str(row["name"])
        new_description = description if description is not None else str(row["description"])
        if metadata_delta is None:
            new_metadata = current_metadata
        elif not metadata_delta:
            # An explicit empty object is the documented clear operation;
            # non-empty objects are a shallow delta over existing metadata.
            new_metadata = {}
        else:
            new_metadata = {**current_metadata, **metadata_delta}

        try:
            metadata_json = canonical_json(new_metadata)
        except CanonicalizationError as exc:
            raise ReferenceValidationError(
                f"cannot canonicalize reference metadata: {exc}"
            ) from exc

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ReferenceValidationError("now must be a non-empty string")
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stream_id = f"{reference_id}:{REFERENCE_STREAM_TYPE}"

        # 1. The only projection change: mutable fields plus updated_at.
        uow.execute(
            "UPDATE project_references SET name = ?, description = ?, "
            "metadata_json = ?, updated_at = ? "
            "WHERE id = ? AND project_id = ? AND archived_at IS NULL",
            (
                new_name,
                new_description,
                metadata_json,
                stamp,
                reference_id,
                project_id,
            ),
        )
        # 2. The hash-chained reference.updated event on the own stream;
        #    the append advances both heads atomically.
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=REFERENCE_UPDATED_EVENT_KIND,
            data={
                "reference_id": reference_id,
                "name": new_name,
                "description": new_description,
                "metadata": new_metadata,
                "updated_at": stamp,
            },
            changes=["name", "description", "metadata", "updated_at"],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 3. The complete receipt with the refreshed read model.
        read_model = _build_reference_read_model(
            uow, project_id=project_id, reference_id=reference_id
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=read_model.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return read_model

    # -- media association --------------------------------------------------

    def associate(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        reference_id: str,
        media_id: str,
        role: str,
        context_task_id: str | None = None,
        ordinal: int | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str,
        actor_kind: str = "local",
        created_at: str | None = None,
        command_kind: str = REFERENCE_ASSOCIATE_COMMAND_KIND,
    ) -> ReferenceAssociateReadModel:
        """Associate one exact media row with an active reference atomically.

        A convenience wrapper over :meth:`associate_many` with a single
        association spec. Returns the immutable
        :class:`ReferenceAssociateReadModel` carrying the one expanded
        association (allocated ``media_reference_id``, media id, role,
        context task, ordinal, and primary flag).
        """
        entry: dict[str, Any] = {
            "media_id": media_id,
            "role": role,
            "context_task_id": context_task_id,
            "ordinal": ordinal,
            "metadata": metadata,
        }
        return self.associate_many(
            uow,
            project_id=project_id,
            reference_id=reference_id,
            associations=[entry],
            idempotency_key=idempotency_key,
            actor_kind=actor_kind,
            created_at=created_at,
            command_kind=command_kind,
        )

    def associate_many(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        reference_id: str,
        associations: Sequence[Mapping[str, Any]],
        idempotency_key: str,
        actor_kind: str = "local",
        created_at: str | None = None,
        command_kind: str = REFERENCE_ASSOCIATE_COMMAND_KIND,
    ) -> ReferenceAssociateReadModel:
        """Associate several exact media rows with an active reference atomically.

        Inside the caller's active unit of work this validates **every**
        association spec before any write, then inserts each
        ``media_references`` row, bumps the reference ``updated_at``, appends
        one hash-chained ``reference.media_associated`` event carrying every
        expanded association, and records one complete receipt whose result
        enumerates every expanded association/media id — so variants never
        inherit associations invisibly.

        Validation (all pre-write, zero rows changed on failure):

        - the reference exists, is active, and belongs to the project;
        - every media row exists and shares the project (same-project pair);
        - ``context_task_id`` is only permitted on ``used_as_input`` /
          ``inspired_by`` and is required for ``used_as_input``;
        - every context task exists, shares the project, and produced the
          exact media through ``task_outputs`` (exact provenance);
        - canonical ordinals are derived deterministically (``max + 1``) and
          no (media, role[, context]) association already exists.

        Idempotency mirrors the kernel commands: the receipt gate runs first,
        an identical retry returns the stored result with zero new rows, and
        a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        reference_id = _require_non_empty_string("reference_id", reference_id)
        idempotency_key = _require_non_empty_string("idempotency_key", idempotency_key)
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise ReferenceValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, got {actor_kind!r}"
            )
        reference_id = _resolve_reference_id(
            uow, project_id=project_id, ref=reference_id
        )
        if isinstance(associations, (str, bytes)) or not isinstance(associations, Sequence):
            raise ReferenceValidationError("associations must be a JSON array")
        entries = [_normalize_association_entry(entry) for entry in associations]
        if not entries:
            raise ReferenceValidationError("associations must not be empty")

        # Semantic request identity: project, reference, and the normalized
        # association specs. Canonical ordinals are derived and therefore
        # carry ``None`` here (excluded from identity); generated association
        # ids and timestamps never participate.
        request: dict[str, Any] = {
            "project_id": project_id,
            "reference_id": reference_id,
            "associations": [dict(entry) for entry in entries],
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ReferenceValidationError(
                f"cannot hash reference association request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before any mutation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return ReferenceAssociateReadModel.from_mapping(replayed)

        # The reference must exist in the project and stay active.
        ref_row = uow.query_one(
            "SELECT * FROM project_references WHERE id = ? AND project_id = ?",
            (reference_id, project_id),
        )
        if ref_row is None:
            raise ReferenceNotFoundError(reference_id=reference_id, project_id=project_id)
        if ref_row["archived_at"] is not None:
            raise ReferenceArchivedError(reference_id=reference_id)

        # Pre-write validation for every entry, resolving canonical ordinals
        # deterministically before any INSERT.
        next_canonical = _next_canonical_ordinal(uow, reference_id)
        resolved: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str, str | None]] = set()
        for entry in entries:
            media_id = entry["media_id"]
            role = entry["role"]
            context_task_id = entry["context_task_id"]

            # Within-batch duplicate detection: the DDL unique indexes
            # (media_reference_global_unique / media_reference_context_unique)
            # would reject a repeated (media, role[, context]) pair, but the
            # typed pre-write gate must catch it before any INSERT so an
            # explicit bulk command never surfaces a raw IntegrityError.
            key = (media_id, role, context_task_id)
            if key in seen_keys:
                raise ReferenceAssociationError(
                    detail="duplicate",
                    reference_id=reference_id,
                    media_id=media_id,
                    role=role,
                    context_task_id=context_task_id,
                )
            seen_keys.add(key)

            media_row = uow.query_one("SELECT id, project_id FROM media WHERE id = ?", (media_id,))
            if media_row is None:
                raise ReferenceAssociationError(
                    detail="missing_media",
                    reference_id=reference_id,
                    media_id=media_id,
                    role=role,
                )
            if str(media_row["project_id"]) != project_id:
                raise ReferenceAssociationError(
                    detail="foreign_media",
                    reference_id=reference_id,
                    media_id=media_id,
                    role=role,
                    project_id=project_id,
                )

            if context_task_id is not None:
                task_row = uow.query_one(
                    "SELECT id, project_id FROM tasks WHERE id = ?",
                    (context_task_id,),
                )
                if task_row is None:
                    raise ReferenceAssociationError(
                        detail="missing_task",
                        reference_id=reference_id,
                        context_task_id=context_task_id,
                    )
                if str(task_row["project_id"]) != project_id:
                    raise ReferenceAssociationError(
                        detail="foreign_task",
                        reference_id=reference_id,
                        context_task_id=context_task_id,
                        project_id=project_id,
                    )
                produced = uow.query_one(
                    "SELECT 1 AS ok FROM task_outputs WHERE task_id = ? AND media_id = ?",
                    (context_task_id, media_id),
                )
                if produced is None:
                    raise ReferenceAssociationError(
                        detail="task_did_not_produce_media",
                        reference_id=reference_id,
                        context_task_id=context_task_id,
                        media_id=media_id,
                    )

            if context_task_id is None:
                duplicate = uow.query_one(
                    "SELECT id FROM media_references WHERE reference_id = ? "
                    "AND media_id = ? AND role = ? AND context_task_id IS NULL",
                    (reference_id, media_id, role),
                )
            else:
                duplicate = uow.query_one(
                    "SELECT id FROM media_references WHERE reference_id = ? "
                    "AND media_id = ? AND role = ? AND context_task_id = ?",
                    (reference_id, media_id, role, context_task_id),
                )
            if duplicate is not None:
                raise ReferenceAssociationError(
                    detail="duplicate",
                    reference_id=reference_id,
                    media_id=media_id,
                    role=role,
                    context_task_id=context_task_id,
                )

            if role == PRIMARY_CANONICAL_ROLE:
                resolved_ordinal = next_canonical
                next_canonical += 1
            else:
                resolved_ordinal = entry["ordinal"]
            resolved.append(
                {
                    "media_id": media_id,
                    "role": role,
                    "context_task_id": context_task_id,
                    "ordinal": resolved_ordinal,
                    "metadata": entry["metadata"],
                }
            )

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ReferenceValidationError("created_at must be a non-empty string")
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stream_id = f"{reference_id}:{REFERENCE_STREAM_TYPE}"

        # The writes: one media_references row per expanded association plus
        # the reference updated_at refresh.
        association_models: list[ReferenceMediaReadModel] = []
        expanded: list[dict[str, Any]] = []
        for item in resolved:
            media_reference_id = generate_lowercase_ulid()
            try:
                metadata_json = canonical_json(item["metadata"])
            except CanonicalizationError as exc:
                raise ReferenceValidationError(
                    f"cannot canonicalize association metadata: {exc}"
                ) from exc
            uow.execute(
                "INSERT INTO media_references "
                "(id, reference_id, media_id, role, context_task_id, ordinal, "
                "is_primary, metadata_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
                (
                    media_reference_id,
                    reference_id,
                    item["media_id"],
                    item["role"],
                    item["context_task_id"],
                    item["ordinal"],
                    metadata_json,
                    stamp,
                ),
            )
            association_models.append(
                ReferenceMediaReadModel(
                    id=media_reference_id,
                    media_id=item["media_id"],
                    role=item["role"],
                    context_task_id=item["context_task_id"],
                    ordinal=item["ordinal"],
                    is_primary=False,
                    metadata=item["metadata"],
                    created_at=stamp,
                )
            )
            expanded.append(
                {
                    "media_reference_id": media_reference_id,
                    "media_id": item["media_id"],
                    "role": item["role"],
                    "context_task_id": item["context_task_id"],
                    "ordinal": item["ordinal"],
                    "is_primary": False,
                }
            )
        uow.execute(
            "UPDATE project_references SET updated_at = ? WHERE id = ?",
            (stamp, reference_id),
        )

        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=REFERENCE_MEDIA_ASSOCIATED_EVENT_KIND,
            data={"reference_id": reference_id, "media": expanded},
            changes=["reference_id", "media"],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        result = ReferenceAssociateReadModel(
            reference_id=reference_id,
            project_id=project_id,
            associations=tuple(association_models),
            event_head_seq=append.stream_seq,
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=result.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return result

    # -- primary replacement ------------------------------------------------

    def set_primary(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        reference_id: str,
        media_reference_id: str,
        idempotency_key: str,
        actor_kind: str = "local",
        now: str | None = None,
        command_kind: str = REFERENCE_SET_PRIMARY_COMMAND_KIND,
    ) -> ReferencePrimaryChangeReadModel:
        """Replace the primary canonical media atomically, collision-safely.

        Inside the caller's active unit of work this clears the current
        primary canonical's ``is_primary`` **before** setting the new one, so
        the ``reference_one_primary_canonical`` partial unique index never
        sees two primaries at a statement boundary. It then refreshes the
        reference ``updated_at``, appends one hash-chained
        ``reference.primary_changed`` event carrying the previous and new
        primary identities (association id plus media id), and records one
        complete receipt.

        Rejections happen **before any write**: a missing/foreign reference
        (:class:`ReferenceNotFoundError`), an archived reference
        (:class:`ReferenceArchivedError`), a missing/foreign/non-canonical
        target association (:class:`ReferencePrimaryError`), or a reference
        with no primary canonical (guarded corruption). Idempotency mirrors
        the kernel commands: the receipt gate runs first, an identical retry
        returns the stored result with zero new rows, and a changed request
        under the same key raises :class:`ReceiptMismatchError`.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        reference_id = _require_non_empty_string("reference_id", reference_id)
        media_reference_id = _require_non_empty_string("media_reference_id", media_reference_id)
        idempotency_key = _require_non_empty_string("idempotency_key", idempotency_key)
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise ReferenceValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, got {actor_kind!r}"
            )
        reference_id = _resolve_reference_id(
            uow, project_id=project_id, ref=reference_id
        )

        request: dict[str, Any] = {
            "project_id": project_id,
            "reference_id": reference_id,
            "media_reference_id": media_reference_id,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ReferenceValidationError(
                f"cannot hash reference set_primary request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before any mutation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return ReferencePrimaryChangeReadModel.from_mapping(replayed)

        ref_row = uow.query_one(
            "SELECT * FROM project_references WHERE id = ? AND project_id = ?",
            (reference_id, project_id),
        )
        if ref_row is None:
            raise ReferenceNotFoundError(reference_id=reference_id, project_id=project_id)
        if ref_row["archived_at"] is not None:
            raise ReferenceArchivedError(reference_id=reference_id)

        current = uow.query_one(
            "SELECT id, media_id FROM media_references "
            "WHERE reference_id = ? AND role = ? AND is_primary = 1",
            (reference_id, PRIMARY_CANONICAL_ROLE),
        )
        if current is None:
            raise ReferencePrimaryError(detail="missing_primary", reference_id=reference_id)

        target = uow.query_one(
            "SELECT id, reference_id, media_id, role FROM media_references WHERE id = ?",
            (media_reference_id,),
        )
        if target is None:
            raise ReferencePrimaryError(detail="not_found", media_reference_id=media_reference_id)
        if str(target["reference_id"]) != reference_id:
            raise ReferencePrimaryError(
                detail="foreign",
                reference_id=reference_id,
                media_reference_id=media_reference_id,
            )
        if str(target["role"]) != PRIMARY_CANONICAL_ROLE:
            raise ReferencePrimaryError(
                detail="not_canonical",
                reference_id=reference_id,
                media_reference_id=media_reference_id,
                role=str(target["role"]),
            )

        stamp = now if now is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ReferenceValidationError("now must be a non-empty string")
        txn_id = uuid.uuid4().hex
        stream_id = f"{reference_id}:{REFERENCE_STREAM_TYPE}"

        previous_primary: dict[str, Any] = {
            "media_reference_id": str(current["id"]),
            "media_id": str(current["media_id"]),
        }
        new_primary: dict[str, Any] = {
            "media_reference_id": media_reference_id,
            "media_id": str(target["media_id"]),
        }

        # Collision-safe replacement: clear the old primary first so the
        # partial unique index never observes two canonical primaries.
        uow.execute(
            "UPDATE media_references SET is_primary = 0 "
            "WHERE reference_id = ? AND role = ? AND is_primary = 1",
            (reference_id, PRIMARY_CANONICAL_ROLE),
        )
        uow.execute(
            "UPDATE media_references SET is_primary = 1 "
            "WHERE id = ? AND reference_id = ? AND role = ?",
            (media_reference_id, reference_id, PRIMARY_CANONICAL_ROLE),
        )
        uow.execute(
            "UPDATE project_references SET updated_at = ? WHERE id = ?",
            (stamp, reference_id),
        )

        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=REFERENCE_PRIMARY_CHANGED_EVENT_KIND,
            data={
                "reference_id": reference_id,
                "previous_primary": previous_primary,
                "new_primary": new_primary,
            },
            changes=["reference_id", "previous_primary", "new_primary"],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=uuid.uuid4().hex,
            created_at=stamp,
        )
        result = ReferencePrimaryChangeReadModel(
            reference_id=reference_id,
            project_id=project_id,
            previous_primary=previous_primary,
            new_primary=new_primary,
            event_head_seq=append.stream_seq,
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=result.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return result

    # -- typed links ------------------------------------------------------

    def link(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        from_reference_id: str,
        to_reference_id: str,
        kind: str,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str,
        actor_kind: str = "local",
        created_at: str | None = None,
        command_kind: str = REFERENCE_LINK_COMMAND_KIND,
    ) -> ReferenceLinkReadModel:
        """Create one typed reference link atomically and idempotently.

        Inside the caller's active unit of work this commits, in one
        ``BEGIN IMMEDIATE`` transaction: the ``reference_links`` row, one
        hash-chained ``reference.linked`` event on the *from* reference's
        own stream, both heads, and one complete receipt whose bounded
        result carries both affected reference ids plus the kind, metadata,
        timestamp, and stream head.

        Symmetry (SD2): only ``related_to`` is symmetric. For that kind the
        stored pair is canonicalized to ``min(id)``/``max(id)`` **before**
        the request is hashed, so a reversed retry under the same
        idempotency key replays the stored result with zero new rows; a
        reversed request under a new key is a typed duplicate. The other
        four kinds (``belongs_to``, ``wears``, ``located_in``,
        ``associated_with``) preserve their submitted direction in the
        stored row, the event, the receipt, and the request identity — a
        reversed retry under the same key is a :class:`ReceiptMismatchError`
        before any mutation.

        Rejections happen **before any write**: a kind outside the frozen
        vocabulary (``bad_kind``), a self-link (``self_link``), a missing
        endpoint (``missing_from``/``missing_to``), a cross-project pair
        (``foreign_from``/``foreign_to``), an archived endpoint
        (``archived_from``/``archived_to``), non-object metadata
        (``bad_metadata``), and an already-existing exact edge
        (``duplicate``) all change zero rows.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        from_reference_id = _require_non_empty_string("from_reference_id", from_reference_id)
        to_reference_id = _require_non_empty_string("to_reference_id", to_reference_id)
        kind = _require_non_empty_string("kind", kind)
        idempotency_key = _require_non_empty_string("idempotency_key", idempotency_key)
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise ReferenceValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, got {actor_kind!r}"
            )
        # Keep absent/foreign endpoint addresses intact so the link-specific
        # endpoint fences below can return ``missing_*``/``foreign_*`` typed
        # errors instead of leaking the generic reference-not-found error.
        from_reference_id = _resolve_reference_id_if_present(
            uow, project_id=project_id, ref=from_reference_id
        )
        to_reference_id = _resolve_reference_id_if_present(
            uow, project_id=project_id, ref=to_reference_id
        )
        if kind not in REFERENCE_LINK_KINDS:
            raise ReferenceLinkError(
                detail="bad_kind",
                from_reference_id=from_reference_id,
                to_reference_id=to_reference_id,
                kind=kind,
            )
        if from_reference_id == to_reference_id:
            raise ReferenceLinkError(
                detail="self_link",
                from_reference_id=from_reference_id,
                to_reference_id=to_reference_id,
                kind=kind,
            )
        if metadata is None:
            metadata_dict: dict[str, Any] = {}
        elif isinstance(metadata, Mapping):
            metadata_dict = dict(metadata)
        else:
            raise ReferenceLinkError(
                detail="bad_metadata",
                from_reference_id=from_reference_id,
                to_reference_id=to_reference_id,
                kind=kind,
            )

        # Symmetry (SD2): only related_to canonicalizes the stored pair, and
        # it canonicalizes *before* the request hash so reversed retries
        # under one idempotency key converge on the stored result.
        if kind == REFERENCE_SYMMETRIC_LINK_KIND:
            stored_from, stored_to = sorted((from_reference_id, to_reference_id))
        else:
            stored_from, stored_to = from_reference_id, to_reference_id

        # Semantic request identity: the canonical stored pair, the kind,
        # and the metadata; generated timestamps never participate.
        request: dict[str, Any] = {
            "project_id": project_id,
            "from_reference_id": stored_from,
            "to_reference_id": stored_to,
            "kind": kind,
            "metadata": metadata_dict,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ReferenceValidationError(f"cannot hash reference link request: {exc}") from exc

        # Idempotency gate first: replay or mismatch before any mutation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return ReferenceLinkReadModel.from_mapping(replayed)

        # Endpoint fences before any write: both references exist, share
        # the project, and are still active (SD1 archive blocks mutations).
        from_row = uow.query_one(
            "SELECT id, project_id, archived_at FROM project_references WHERE id = ?",
            (from_reference_id,),
        )
        if from_row is None:
            raise ReferenceLinkError(
                detail="missing_from",
                from_reference_id=from_reference_id,
                to_reference_id=to_reference_id,
                kind=kind,
            )
        if str(from_row["project_id"]) != project_id:
            raise ReferenceLinkError(
                detail="foreign_from",
                from_reference_id=from_reference_id,
                to_reference_id=to_reference_id,
                kind=kind,
            )
        if from_row["archived_at"] is not None:
            raise ReferenceLinkError(
                detail="archived_from",
                from_reference_id=from_reference_id,
                to_reference_id=to_reference_id,
                kind=kind,
            )
        to_row = uow.query_one(
            "SELECT id, project_id, archived_at FROM project_references WHERE id = ?",
            (to_reference_id,),
        )
        if to_row is None:
            raise ReferenceLinkError(
                detail="missing_to",
                from_reference_id=from_reference_id,
                to_reference_id=to_reference_id,
                kind=kind,
            )
        if str(to_row["project_id"]) != project_id:
            raise ReferenceLinkError(
                detail="foreign_to",
                from_reference_id=from_reference_id,
                to_reference_id=to_reference_id,
                kind=kind,
            )
        if to_row["archived_at"] is not None:
            raise ReferenceLinkError(
                detail="archived_to",
                from_reference_id=from_reference_id,
                to_reference_id=to_reference_id,
                kind=kind,
            )

        # Duplicate rejection before any write: the exact stored edge — the
        # canonical pair for related_to, the directional pair otherwise.
        if (
            uow.query_one(
                "SELECT 1 AS ok FROM reference_links "
                "WHERE from_reference_id = ? AND to_reference_id = ? "
                "AND kind = ?",
                (stored_from, stored_to, kind),
            )
            is not None
        ):
            raise ReferenceLinkError(
                detail="duplicate",
                from_reference_id=stored_from,
                to_reference_id=stored_to,
                kind=kind,
            )

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ReferenceValidationError("created_at must be a non-empty string")
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stream_id = f"{stored_from}:{REFERENCE_STREAM_TYPE}"

        try:
            metadata_json = canonical_json(metadata_dict)
        except CanonicalizationError as exc:
            raise ReferenceValidationError(f"cannot canonicalize link metadata: {exc}") from exc

        # 1. The reference_links row (stored pair; DDL CHECK enforces
        #    from <> to, which the self-link fence already rejected).
        uow.execute(
            "INSERT INTO reference_links "
            "(from_reference_id, to_reference_id, kind, metadata_json, "
            "created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (stored_from, stored_to, kind, metadata_json, stamp),
        )
        # 2. The hash-chained reference.linked event on the from stream,
        #    carrying both affected reference ids (bounded changes).
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=REFERENCE_LINKED_EVENT_KIND,
            data={
                "from_reference_id": stored_from,
                "to_reference_id": stored_to,
                "kind": kind,
                "metadata": metadata_dict,
            },
            changes=[
                "from_reference_id",
                "to_reference_id",
                "kind",
                "metadata",
            ],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 3. The complete receipt with the bounded link result.
        result = ReferenceLinkReadModel(
            from_reference_id=stored_from,
            to_reference_id=stored_to,
            kind=kind,
            metadata=metadata_dict,
            created_at=stamp,
            event_head_seq=append.stream_seq,
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=result.to_dict(),
            primary_stream_id=stream_id,
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return result

    # -- reads -------------------------------------------------------------

    def show(
        self,
        writer: DatabaseWriter,
        project_id: str,
        reference_id: str,
    ) -> ReferenceReadModel:
        """Direct historical lookup of one reference (always includes archived).

        A transaction-free read on a separate read-only connection. ``show``
        is the direct lookup that archive never hides (SD1): an archived
        reference's associations, links, events, media rows, and bytes stay
        visible here. ``reference_id`` is the public ``ref`` address: an
        exact id wins first, otherwise an exact project-local name is used.
        A duplicate name fails closed with candidate ids, so a human-readable
        address can never silently select the wrong reference. Returns the
        immutable :class:`ReferenceReadModel` with the ordered media
        associations and the reference stream head. A missing project raises
        :class:`ProjectNotFoundError`; a missing or foreign reference raises
        :class:`ReferenceNotFoundError`.
        """
        _require_non_empty_string("project_id", project_id)
        _require_non_empty_string("reference_id", reference_id)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            project = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)
            row = conn.execute(
                "SELECT r.*, s.head_seq FROM project_references r "
                "JOIN event_streams s ON s.id = ? "
                "WHERE r.id = ? AND r.project_id = ?",
                (f"{reference_id}:{REFERENCE_STREAM_TYPE}", reference_id, project_id),
            ).fetchone()
            if row is None:
                matches = conn.execute(
                    "SELECT r.*, s.head_seq FROM project_references r "
                    "JOIN event_streams s ON s.id = r.id || ':" + REFERENCE_STREAM_TYPE + "' "
                    "WHERE r.project_id = ? AND r.name = ? ORDER BY r.id ASC",
                    (project_id, reference_id),
                ).fetchall()
                if len(matches) > 1:
                    raise ReferenceAmbiguousError(
                        ref=reference_id,
                        candidate_ids=[str(match["id"]) for match in matches],
                    )
                if matches:
                    row = matches[0]
            if row is None:
                raise ReferenceNotFoundError(reference_id=reference_id, project_id=project_id)
            # Name addressing is only an input convenience. Once resolved,
            # all enrichment must use the canonical aggregate id so name and
            # exact-id reads are byte-for-byte equivalent.
            resolved_reference_id = str(row["id"])
            media_rows = conn.execute(
                "SELECT * FROM media_references WHERE reference_id = ? "
                "ORDER BY role ASC, ordinal ASC, id ASC",
                (resolved_reference_id,),
            ).fetchall()
        media = tuple(
            ReferenceMediaReadModel(
                id=str(m["id"]),
                media_id=str(m["media_id"]),
                role=str(m["role"]),
                context_task_id=m["context_task_id"],
                ordinal=int(m["ordinal"]),
                is_primary=bool(m["is_primary"]),
                metadata=_parse_object(
                    str(m["metadata_json"]),
                    label="media association",
                    subject=str(m["id"]),
                ),
                created_at=str(m["created_at"]),
            )
            for m in media_rows
        )
        return ReferenceReadModel(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            kind=str(row["kind"]),
            name=str(row["name"]),
            description=str(row["description"]),
            metadata=_parse_object(
                str(row["metadata_json"]),
                label="reference",
                subject=str(row["id"]),
            ),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            archived_at=row["archived_at"],
            event_head_seq=int(row["head_seq"]),
            media=media,
        )

    def list(
        self,
        writer: DatabaseWriter,
        project_id: str,
        *,
        include_archived: bool = False,
    ) -> list[ReferenceListRow]:
        """Sorted reference list; archived rows are hidden by default.

        A transaction-free read on a separate read-only connection. The
        default list excludes archived references (``archived_at`` NULL
        only); ``include_archived=True`` is the explicit inclusive list that
        preserves history (SD1). Rows are ordered by kind, then name, then
        id. A missing project raises :class:`ProjectNotFoundError` — never
        an empty authority-dependent view.
        """
        _require_non_empty_string("project_id", project_id)
        if not isinstance(include_archived, bool):
            raise ReferenceValidationError("include_archived must be a boolean")
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            project = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)
            if include_archived:
                rows = conn.execute(
                    "SELECT id, project_id, kind, name, archived_at, "
                    "created_at, updated_at FROM project_references "
                    "WHERE project_id = ? "
                    "ORDER BY kind ASC, name ASC, id ASC",
                    (project_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, project_id, kind, name, archived_at, "
                    "created_at, updated_at FROM project_references "
                    "WHERE project_id = ? AND archived_at IS NULL "
                    "ORDER BY kind ASC, name ASC, id ASC",
                    (project_id,),
                ).fetchall()
        return [
            ReferenceListRow(
                id=str(row["id"]),
                project_id=str(row["project_id"]),
                kind=str(row["kind"]),
                name=str(row["name"]),
                archived_at=row["archived_at"],
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]


__all__ = [
    "CONTEXT_REQUIRED_ROLE",
    "CONTEXT_ROLES",
    "MEDIA_REFERENCE_ROLES",
    "PRIMARY_CANONICAL_ROLE",
    "REFERENCE_ARCHIVE_COMMAND_KIND",
    "REFERENCE_ARCHIVED_EVENT_KIND",
    "REFERENCE_UNARCHIVE_COMMAND_KIND",
    "REFERENCE_UNARCHIVED_EVENT_KIND",
    "REFERENCE_ASSOCIATE_COMMAND_KIND",
    "REFERENCE_CREATE_COMMAND_KIND",
    "REFERENCE_CREATED_EVENT_KIND",
    "REFERENCE_KINDS",
    "REFERENCE_LINK_COMMAND_KIND",
    "REFERENCE_LINK_KINDS",
    "REFERENCE_LINKED_EVENT_KIND",
    "REFERENCE_MEDIA_ASSOCIATED_EVENT_KIND",
    "REFERENCE_PRIMARY_CHANGED_EVENT_KIND",
    "REFERENCE_SET_PRIMARY_COMMAND_KIND",
    "REFERENCE_STREAM_TYPE",
    "REFERENCE_SYMMETRIC_LINK_KIND",
    "REFERENCE_UPDATE_COMMAND_KIND",
    "REFERENCE_UPDATED_EVENT_KIND",
    "ReferenceAlreadyExistsError",
    "ReferenceAmbiguousError",
    "ReferenceArchiveReadModel",
    "ReferenceArchivedError",
    "ReferenceAssociateReadModel",
    "ReferenceAssociationError",
    "ReferenceLinkError",
    "ReferenceLinkReadModel",
    "ReferenceListRow",
    "ReferenceMediaError",
    "ReferenceMediaReadModel",
    "ReferenceNotFoundError",
    "ReferencePrimaryChangeReadModel",
    "ReferencePrimaryError",
    "ReferenceReadModel",
    "ReferenceRepository",
    "ReferenceRepositoryError",
    "ReferenceUnarchiveReadModel",
    "ReferenceValidationError",
]
