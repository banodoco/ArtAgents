"""Shots repository: immutable shot/item read models and UoW-only shot
container commands (m3 plan step 10, T11).

The shots pack's executable repository lives in this module
(``astrid/packs/shots/repository.py``). It follows the kernel, timeline, and
references repository shape — one writer transaction per command, typed
errors, frozen read models, transaction-free reads — over the frozen
two-table schema (``shots``, ``shot_items``) with **exact kernel media ids
only** (plugin law 2: the only cross-pack currency is ``media_id``, and the
pack never FK's to or imports the timeline pack).

:meth:`ShotRepository.create` is one complete command inside the caller's
single ``BEGIN IMMEDIATE`` unit of work:

1. validates the frozen shot facts (non-empty trimmed ``name``, object
   ``metadata``) and runs the receipt idempotency gate first;
2. rejects a duplicate shot identity before any allocation
   (:class:`ShotAlreadyExistsError`) and a missing project
   (:class:`ProjectNotFoundError`);
3. atomically inserts the pack-owned ``shot.shot`` event stream, the
   ``shots`` row with a deterministic normalized ``sort_key`` derived from
   stable facts (``created_at|id`` — never a caller-supplied floating
   rank), appends the hash-chained ``shot.created`` event, and records the
   complete receipt — returning the immutable :class:`ShotReadModel` with
   zero items.

:meth:`ShotRepository.add_item` and :meth:`ShotRepository.remove_item` are
the receipt-backed position-aware item mutations:

- ``add_item`` validates the insertion position (``0 .. current count``),
  exact same-project kernel media, a non-negative ``source_frame``, object
  ``metadata``, and unique item identity **before any write**, then inserts
  the ``shot_items`` row and renormalizes every item of the shot to the
  deterministic zero-padded position keys ``000000000000``..``n-1`` using
  collision-safe temporary keys inside the same transaction;
- ``remove_item`` validates the exact item identity (missing or foreign
  items change zero rows), deletes **only** the ``shot_items`` row — the
  kernel media row and its bytes are preserved (the DDL
  ``ON DELETE RESTRICT`` pins the media row; this command never touches
  media) — and renormalizes the remaining items the same way;
- each mutation refreshes ``shots.updated_at``, appends one hash-chained
  ``shot.item_added`` / ``shot.item_removed`` event on the shot's own
  stream, and records the complete receipt whose bounded result carries the
  affected item facts (for removal: the preserved ``media_id``), the shot's
  ordered item ids after the mutation, and the new stream head.

:meth:`ShotRepository.reorder` is the atomic whole-shot reorder (plan step
11): it validates that the request is **exactly** the shot's current item
ids — rejecting omissions, duplicates, extras, and foreign-shot items
before any write — then renumbers every item with the same
collision-safe temporary-key pass followed by normalized zero-padded final
keys inside the caller's one transaction, refreshes ``shots.updated_at``,
appends the single hash-chained ``shot.reordered`` event carrying the
exact ordered item ids and matching kernel media ids, and records the
complete receipt whose result carries both the exact item order and the
exact media order.

Reads are transaction-free on a separate read-only connection:
:meth:`show` returns the immutable shot with its items in stable
``sort_key``/``id`` order, and :meth:`list` returns the project's shots in
stable ``sort_key``/``id`` order.

The repository is stateless apart from the kernel event append and receipt
services; every command must run inside the caller's
:class:`astrid.core.store.uow.UnitOfWork`, and it never constructs a writer
or opens a transaction.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from astrid.core.events.service import (
    ACTOR_KINDS,
    EventAppendService,
    EventHeadConflictError,
)
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

SHOT_STREAM_TYPE = "shot.shot"
"""The pack stream type every shot aggregate owns (one per shot)."""

SHOT_CREATED_EVENT_KIND = "shot.created"
"""The m3 event kind emitted by shot creation.

Carries the frozen shot facts (id, name, metadata) plus the deterministic
normalized ``sort_key``, so the event log alone reconstructs the shot's
identity and its stable list position.
"""

SHOT_ITEM_ADDED_EVENT_KIND = "shot.item_added"
"""The m3 event kind emitted by a receipt-backed item insertion.

Carries the exact kernel ``media_id``, the optional ``source_frame`` and
``metadata``, and the item's resolved normalized position.
"""

SHOT_ITEM_REMOVED_EVENT_KIND = "shot.item_removed"
"""The m3 event kind emitted by a receipt-backed item removal.

Carries the removed item's facts — including the exact kernel ``media_id``
— so the log alone proves which media identity was preserved on removal.
"""
SHOT_REORDERED_EVENT_KIND = "shot.reordered"
"""The m3 event kind emitted by a receipt-backed whole-shot reorder."""

SHOT_CANDIDATE_PROMOTED_EVENT_KIND = "shot.candidate_promoted"
"""The event emitted when a candidate becomes the primary visual."""

SHOT_CREATE_COMMAND_KIND = "shot.create"
"""The m3 command kind that shot-create receipts are keyed on."""

SHOT_ADD_ITEM_COMMAND_KIND = "shot.add_item"
"""The m3 command kind that item-insertion receipts are keyed on."""

SHOT_REMOVE_ITEM_COMMAND_KIND = "shot.remove_item"
"""The m3 command kind that item-removal receipts are keyed on."""

SHOT_REORDER_COMMAND_KIND = "shot.reorder"
"""The m3 command kind that whole-shot reorder receipts are keyed on."""

SHOT_PROMOTE_CANDIDATE_COMMAND_KIND = "shot.promote_candidate"
"""The command kind that candidate-promotion receipts are keyed on."""

SHOT_SORT_KEY_WIDTH = 12
"""The fixed zero-padded width of normalized item sort keys.

Item sort keys are deterministic normalized positions
(``000000000000``..``n-1``) so lexicographic order equals numeric order and
no caller-dependent floating rank ever reaches the table.
"""

_TMP_SORT_KEY_PREFIX = "tmp:"
"""Collision-safe temporary-key prefix used while renormalizing.

``tmp:{item_id}`` is unique within a shot because item ids are the primary
key, so a renumbering pass can never collide with an existing ``sort_key``
(UNIQUE ``(shot_id, sort_key)``) — the same convention the m3 whole-shot
reorder command reuses (plan step 11).
"""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ShotRepositoryError(RepositoryError):
    """Base error for the shots repository family.

    Subclasses :class:`astrid.core.repositories.errors.RepositoryError`
    (and therefore :class:`astrid.core.store.writer.WriterError`), so the
    kernel store error family catches shot contract violations too.
    """


class ShotValidationError(ShotRepositoryError):
    """Raised when a shot argument violates a frozen contract."""


class ShotAlreadyExistsError(ShotRepositoryError):
    """Raised when create targets an already-existing shot id."""

    def __init__(self, *, shot_id: str) -> None:
        self.shot_id: str = shot_id
        super().__init__(f"shot already exists: {shot_id!r}")


class ShotNotFoundError(ShotRepositoryError):
    """Raised when a read or command targets an unknown/foreign shot."""

    def __init__(self, *, shot_id: str, project_id: str) -> None:
        self.shot_id: str = shot_id
        self.project_id: str = project_id
        super().__init__(
            f"unknown shot {shot_id!r} in project {project_id!r}"
        )


class ShotItemNotFoundError(ShotRepositoryError):
    """Raised when a removal targets an unknown or foreign-shot item."""

    def __init__(self, *, item_id: str, shot_id: str) -> None:
        self.item_id: str = item_id
        self.shot_id: str = shot_id
        super().__init__(
            f"unknown shot item {item_id!r} in shot {shot_id!r}"
        )


class ShotMediaError(ShotRepositoryError):
    """Raised when an item mutation names missing or foreign media.

    ``detail`` is one of ``"missing"`` (no media row) or ``"foreign"``
    (the media row belongs to another project). Rejected before any write.
    """

    def __init__(
        self,
        *,
        media_id: str,
        project_id: str,
        detail: str,
        shot_id: str | None = None,
    ) -> None:
        self.media_id: str = media_id
        self.project_id: str = project_id
        self.detail: str = detail
        self.shot_id: str | None = shot_id
        super().__init__(
            f"shot media {media_id!r} is {detail} for project "
            f"{project_id!r}"
        )


class ShotReorderError(ShotRepositoryError):
    """Raised when a reorder request is not an exact permutation.

    ``detail`` is one of ``"omission"`` (a current item id is missing),
    ``"duplicate"`` (an id appears more than once), ``"extra"`` (an id
    is not a shot item), or ``"foreign"`` (an id belongs to another
    shot). Rejected before any write.
    """

    def __init__(
        self,
        *,
        shot_id: str,
        detail: str,
        item_ids: Sequence[str] = (),
    ) -> None:
        self.shot_id: str = shot_id
        self.detail: str = detail
        self.item_ids: tuple[str, ...] = tuple(item_ids)
        if detail not in {"omission", "duplicate", "extra", "foreign"}:
            raise ValueError(f"unknown shot reorder detail {detail!r}")
        shown = ", ".join(self.item_ids) if self.item_ids else "(none)"
        super().__init__(
            f"shot reorder {detail} for shot {shot_id!r}: {shown}"
        )


# ---------------------------------------------------------------------------
# Frozen read models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ShotItemReadModel:
    """One immutable ``shot_items`` row (m3 plan step 10).

    ``sort_key`` is the deterministic normalized zero-padded position and
    ``position`` its integer projection (the item's 0-based index in the
    shot's stable ``sort_key``/``id`` order). ``source_frame`` is an
    optional non-negative frame index into the referenced media.
    """

    id: str
    shot_id: str
    media_id: str
    source_frame: int | None
    metadata: Mapping[str, Any]
    sort_key: str
    position: int
    created_at: str
    event_head_seq: int

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted in events and receipts."""
        return {
            "id": self.id,
            "shot_id": self.shot_id,
            "media_id": self.media_id,
            "source_frame": self.source_frame,
            "metadata": dict(self.metadata),
            "sort_key": self.sort_key,
            "position": self.position,
            "created_at": self.created_at,
            "event_head_seq": self.event_head_seq,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ShotItemReadModel:
        """Rebuild the frozen item read model from a stored mapping."""
        return cls(
            id=str(value["id"]),
            shot_id=str(value["shot_id"]),
            media_id=str(value["media_id"]),
            source_frame=value.get("source_frame"),
            metadata=dict(value.get("metadata") or {}),
            sort_key=str(value["sort_key"]),
            position=int(value["position"]),
            created_at=str(value["created_at"]),
            event_head_seq=int(value["event_head_seq"]),
        )


@dataclass(frozen=True, slots=True)
class ShotReadModel:
    """One immutable shot read model (m3 plan step 10).

    A frozen projection of one ``shots`` row plus the ordered ``items`` and
    the shot stream head. ``items`` is ordered by ``sort_key``, then ``id``
    (stable deterministic order); a freshly created shot carries zero items.
    """

    id: str
    project_id: str
    name: str
    sort_key: str
    metadata: Mapping[str, Any]
    created_at: str
    updated_at: str
    event_head_seq: int
    items: tuple[ShotItemReadModel, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "sort_key": self.sort_key,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "event_head_seq": self.event_head_seq,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ShotReadModel:
        """Rebuild the frozen shot read model from a stored mapping."""
        items = tuple(
            ShotItemReadModel.from_mapping(item)
            for item in (value.get("items") or [])
        )
        return cls(
            id=str(value["id"]),
            project_id=str(value["project_id"]),
            name=str(value["name"]),
            sort_key=str(value["sort_key"]),
            metadata=dict(value.get("metadata") or {}),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
            event_head_seq=int(value["event_head_seq"]),
            items=items,
        )


@dataclass(frozen=True, slots=True)
class ShotListRow:
    """One sorted shot list row (m3 plan step 10).

    Produced only by the transaction-free :meth:`ShotRepository.list` read
    in stable ``sort_key``/``id`` order.
    """

    id: str
    project_id: str
    name: str
    sort_key: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ShotItemMutationReadModel:
    """One immutable item-mutation result (m3 plan step 10).

    The receipt result of :meth:`ShotRepository.add_item` and
    :meth:`ShotRepository.remove_item`: ``item`` carries the affected item's
    facts (for removal the preserved ``media_id``/``source_frame``/
    ``metadata``), ``item_ids`` the shot's ordered item ids **after** the
    mutation (stable ``sort_key``/``id`` order), and ``event_head_seq`` the
    shot stream head after the mutation's event. Removal responses additionally
    expose ``removed_item`` and ``remaining_item_count`` so the legacy ``item``
    field cannot be mistaken for current shot membership.
    """

    shot_id: str
    project_id: str
    item: ShotItemReadModel
    item_ids: tuple[str, ...]
    event_head_seq: int
    removed_item: ShotItemReadModel | None = None
    remaining_item_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        result = {
            "shot_id": self.shot_id,
            "project_id": self.project_id,
            "item": self.item.to_dict(),
            "item_ids": list(self.item_ids),
            "event_head_seq": self.event_head_seq,
        }
        if self.removed_item is not None:
            result["removed_item"] = self.removed_item.to_dict()
        if self.remaining_item_count is not None:
            result["remaining_item_count"] = self.remaining_item_count
        return result

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any]
    ) -> ShotItemMutationReadModel:
        """Rebuild the frozen mutation result from a stored mapping."""
        return cls(
            shot_id=str(value["shot_id"]),
            project_id=str(value["project_id"]),
            item=ShotItemReadModel.from_mapping(value["item"]),
            item_ids=tuple(
                str(item_id) for item_id in (value.get("item_ids") or [])
            ),
            event_head_seq=int(value["event_head_seq"]),
            removed_item=(
                ShotItemReadModel.from_mapping(value["removed_item"])
                if value.get("removed_item") is not None
                else None
            ),
            remaining_item_count=(
                int(value["remaining_item_count"])
                if value.get("remaining_item_count") is not None
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class ShotReorderReadModel:
    """One immutable whole-shot reorder result (m3 plan step 11).

    The receipt result of :meth:`ShotRepository.reorder`: ``item_ids`` is
    the shot's exact new item order and ``media_ids`` the matching exact
    kernel media order **after** the mutation, plus the shot stream head
    after the single ``shot.reordered`` event.
    """

    shot_id: str
    project_id: str
    item_ids: tuple[str, ...]
    media_ids: tuple[str, ...]
    event_head_seq: int

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "shot_id": self.shot_id,
            "project_id": self.project_id,
            "item_ids": list(self.item_ids),
            "media_ids": list(self.media_ids),
            "event_head_seq": self.event_head_seq,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ShotReorderReadModel:
        """Rebuild the frozen reorder result from a stored mapping."""
        return cls(
            shot_id=str(value["shot_id"]),
            project_id=str(value["project_id"]),
            item_ids=tuple(
                str(item_id) for item_id in (value.get("item_ids") or [])
            ),
            media_ids=tuple(
                str(media_id) for media_id in (value.get("media_ids") or [])
            ),
            event_head_seq=int(value["event_head_seq"]),
        )

@dataclass(frozen=True, slots=True)
class ShotCandidatePromotionReadModel:
    """Receipt result for one atomic candidate-to-primary promotion."""

    shot_id: str
    project_id: str
    candidate_item_id: str
    primary_item_id: str
    superseded_item_id: str | None
    item_ids: tuple[str, ...]
    event_head_seq: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "project_id": self.project_id,
            "candidate_item_id": self.candidate_item_id,
            "primary_item_id": self.primary_item_id,
            "superseded_item_id": self.superseded_item_id,
            "item_ids": list(self.item_ids),
            "event_head_seq": self.event_head_seq,
        }

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any]
    ) -> ShotCandidatePromotionReadModel:
        return cls(
            shot_id=str(value["shot_id"]),
            project_id=str(value["project_id"]),
            candidate_item_id=str(value["candidate_item_id"]),
            primary_item_id=str(value["primary_item_id"]),
            superseded_item_id=(
                str(value["superseded_item_id"])
                if value.get("superseded_item_id") is not None
                else None
            ),
            item_ids=tuple(str(item_id) for item_id in (value.get("item_ids") or [])),
            event_head_seq=int(value["event_head_seq"]),
        )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ShotValidationError(f"{name} must be a non-empty string")
    return value


def _parse_object(
    raw: str, *, label: str, subject: str
) -> dict[str, Any]:
    """Parse one stored JSON object canonically, rejecting non-objects."""
    try:
        parsed = parse_json(raw)
    except CanonicalizationError as exc:
        raise ShotRepositoryError(
            f"{label} {subject!r} has invalid stored JSON: {exc}"
        ) from exc
    if not isinstance(parsed, Mapping):
        raise ShotRepositoryError(
            f"{label} {subject!r} stored JSON is not an object"
        )
    return dict(parsed)


def _normalized_item_sort_key(position: int) -> str:
    """The deterministic zero-padded sort key for one normalized position."""
    return f"{position:0{SHOT_SORT_KEY_WIDTH}d}"


def _shot_sort_key(stamp: str, shot_id: str) -> str:
    """The deterministic normalized shot sort key from stable facts.

    ``created_at|id`` is fully deterministic (both facts are stable once
    the shot exists), unique within a project (the id suffix breaks ties),
    and never depends on a caller-supplied floating rank. Lexicographic
    order equals creation order, then id.
    """
    return f"{stamp}|{shot_id}"


def _ordered_item_rows(uow: UnitOfWork, shot_id: str) -> list[Any]:
    """All item rows of one shot in stable sort_key/id order."""
    return uow.query(
        "SELECT * FROM shot_items WHERE shot_id = ? "
        "ORDER BY sort_key ASC, id ASC",
        (shot_id,),
    )


def _renormalize_items(
    uow: UnitOfWork, shot_id: str, ordered_ids: Sequence[str]
) -> None:
    """Renumber a shot's items to deterministic 0..n-1 position keys.

    Collision-safe two-phase renumber inside the caller's transaction:
    every existing item first moves to a temporary key derived from its
    primary key (``tmp:{id}`` — unique by construction), then each item in
    ``ordered_ids`` receives its final zero-padded position key. This is
    the same temporary-key convention the m3 whole-shot reorder command
    reuses (plan step 11).
    """
    uow.execute(
        "UPDATE shot_items SET sort_key = ? || id WHERE shot_id = ?",
        (_TMP_SORT_KEY_PREFIX, shot_id),
    )
    for position, item_id in enumerate(ordered_ids):
        uow.execute(
            "UPDATE shot_items SET sort_key = ? WHERE id = ? AND shot_id = ?",
            (_normalized_item_sort_key(position), item_id, shot_id),
        )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class ShotRepository:
    """Stateless shot command/read surface over the kernel unit of work.

    Composes the kernel event append and receipt services. A single
    instance is safe to share across command callers; every command must run
    inside the caller's :class:`astrid.core.store.uow.UnitOfWork` and every
    read runs transaction-free on a separate read-only connection. The
    repository never constructs a writer and never imports the timeline
    pack.
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
        name: str,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str,
        actor_kind: str = "local",
        shot_id: str | None = None,
        created_at: str | None = None,
        command_kind: str = SHOT_CREATE_COMMAND_KIND,
    ) -> ShotReadModel:
        """Create one empty shot atomically and idempotently.

        Inside the caller's active unit of work this commits, in one
        ``BEGIN IMMEDIATE`` transaction: the ``shot.shot`` event stream, the
        ``shots`` row (active, deterministic normalized ``sort_key``), the
        hash-chained ``shot.created`` event, both heads, and one complete
        receipt.

        Rejections happen **before any allocation**: an empty or whitespace
        name, non-object metadata, a missing project
        (:class:`ProjectNotFoundError`), and a duplicate shot identity
        (:class:`ShotAlreadyExistsError`) all change zero rows. Idempotency
        mirrors the kernel commands: the receipt gate runs first, an
        identical retry returns exactly the stored result with zero new
        rows, and a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        name = _require_non_empty_string("name", name)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if not name.strip():
            raise ShotValidationError(
                "name must contain at least one non-whitespace character"
            )
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ShotValidationError("metadata must be a JSON object")
        if actor_kind not in ACTOR_KINDS:
            raise ShotValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if shot_id is None:
            shot_id = generate_lowercase_ulid()
        else:
            _require_non_empty_string("shot_id", shot_id)
        metadata_dict = dict(metadata) if metadata is not None else {}

        # Semantic request identity: stable id, name, and metadata all
        # participate; generated values (timestamps, sort keys) are
        # excluded.
        request: dict[str, Any] = {
            "project_id": project_id,
            "shot_id": shot_id,
            "name": name,
            "metadata": metadata_dict,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ShotValidationError(
                f"cannot hash shot create request: {exc}"
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
            return ShotReadModel.from_mapping(replayed)

        # The project must exist before any stream/row insert.
        if uow.query_one("SELECT id FROM projects WHERE id = ?", (project_id,)) is None:
            raise ProjectNotFoundError(project_id=project_id)

        # Duplicate identity rejection before allocation.
        if (
            uow.query_one(
                "SELECT id FROM shots WHERE id = ?",
                (shot_id,),
            )
            is not None
        ):
            raise ShotAlreadyExistsError(shot_id=shot_id)

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ShotValidationError("created_at must be a non-empty string")
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stream_id = f"{shot_id}:{SHOT_STREAM_TYPE}"
        sort_key = _shot_sort_key(stamp, shot_id)

        try:
            metadata_json = canonical_json(metadata_dict)
        except CanonicalizationError as exc:
            raise ShotValidationError(
                f"cannot canonicalize shot metadata: {exc}"
            ) from exc

        # 1. The shot.shot stream (head_seq 0; the append advances it to 1
        #    in the same transaction).
        uow.execute(
            "INSERT INTO event_streams "
            "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (stream_id, project_id, SHOT_STREAM_TYPE, shot_id, stamp),
        )
        # 2. The shots projection with the deterministic normalized sort key.
        uow.execute(
            "INSERT INTO shots "
            "(id, project_id, name, sort_key, metadata_json, created_at, "
            "updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                shot_id,
                project_id,
                name,
                sort_key,
                metadata_json,
                stamp,
                stamp,
            ),
        )
        # 3. The hash-chained shot.created event.
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=SHOT_CREATED_EVENT_KIND,
            data={
                "shot_id": shot_id,
                "name": name,
                "metadata": metadata_dict,
                "sort_key": sort_key,
            },
            changes=[
                "shot_id",
                "name",
                "metadata",
                "sort_key",
            ],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 4. The complete receipt with the empty-shot read model.
        read_model = ShotReadModel(
            id=shot_id,
            project_id=project_id,
            name=name,
            sort_key=sort_key,
            metadata=metadata_dict,
            created_at=stamp,
            updated_at=stamp,
            event_head_seq=append.stream_seq,
            items=(),
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

    # -- add_item ----------------------------------------------------------

    def add_item(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        shot_id: str,
        media_id: str,
        position: int | None = None,
        source_frame: int | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str,
        actor_kind: str = "local",
        item_id: str | None = None,
        created_at: str | None = None,
        command_kind: str = SHOT_ADD_ITEM_COMMAND_KIND,
    ) -> ShotItemMutationReadModel:
        """Insert one exact-media item at a validated position atomically.

        Inside the caller's active unit of work this commits, in one
        ``BEGIN IMMEDIATE`` transaction: the ``shot_items`` row (exact
        same-project kernel ``media_id``), the deterministic renormalization
        of every item to zero-padded position keys, the refreshed
        ``shots.updated_at``, the hash-chained ``shot.item_added`` event on
        the shot's own stream, both heads, and one complete receipt.

        Rejections happen **before any write**: a missing or foreign shot
        (:class:`ShotNotFoundError`), missing or foreign media
        (:class:`ShotMediaError``), an out-of-range insertion position, a
        negative ``source_frame``, non-object metadata, and an invalid
        ``item_id`` all change zero rows. Idempotency mirrors the kernel
        commands: the receipt gate runs first, an identical retry returns
        exactly the stored result with zero new rows, and a changed request
        under the same key raises :class:`ReceiptMismatchError` before any
        mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        shot_id = _require_non_empty_string("shot_id", shot_id)
        media_id = _require_non_empty_string("media_id", media_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise ShotValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if position is not None and (
            isinstance(position, bool) or not isinstance(position, int)
        ):
            raise ShotValidationError("position must be an integer")
        if position is not None and position < 0:
            raise ShotValidationError("position must be non-negative")
        if source_frame is not None and (
            isinstance(source_frame, bool)
            or not isinstance(source_frame, int)
            or source_frame < 0
        ):
            raise ShotValidationError(
                "source_frame must be a non-negative integer or null"
            )
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ShotValidationError("metadata must be a JSON object")
        if item_id is None:
            item_id = generate_lowercase_ulid()
        else:
            _require_non_empty_string("item_id", item_id)
        metadata_dict = dict(metadata) if metadata is not None else {}

        # Semantic request identity: the shot, the exact media id, the
        # optional source frame/metadata, and the caller-supplied position
        # participate; generated values never do.
        request: dict[str, Any] = {
            "project_id": project_id,
            "shot_id": shot_id,
            "media_id": media_id,
            "source_frame": source_frame,
            "metadata": metadata_dict,
        }
        if position is not None:
            request["position"] = position
        if item_id is not None:
            request["item_id"] = item_id
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ShotValidationError(
                f"cannot hash shot add_item request: {exc}"
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
            return ShotItemMutationReadModel.from_mapping(replayed)

        # Shot/project agreement before any write.
        shot_row = uow.query_one(
            "SELECT id, project_id FROM shots WHERE id = ?",
            (shot_id,),
        )
        if shot_row is None:
            raise ShotNotFoundError(shot_id=shot_id, project_id=project_id)
        if str(shot_row["project_id"]) != project_id:
            raise ShotNotFoundError(shot_id=shot_id, project_id=project_id)

        # Exact same-project kernel media before any write.
        media_row = uow.query_one(
            "SELECT id, project_id FROM media WHERE id = ?",
            (media_id,),
        )
        if media_row is None:
            raise ShotMediaError(
                media_id=media_id,
                project_id=project_id,
                detail="missing",
                shot_id=shot_id,
            )
        if str(media_row["project_id"]) != project_id:
            raise ShotMediaError(
                media_id=media_id,
                project_id=project_id,
                detail="foreign",
                shot_id=shot_id,
            )

        # Unique item identity before any write.
        if (
            uow.query_one(
                "SELECT id FROM shot_items WHERE id = ?", (item_id,)
            )
            is not None
        ):
            raise ShotValidationError(
                f"shot item already exists: {item_id!r}"
            )

        current = _ordered_item_rows(uow, shot_id)
        current_ids = [str(row["id"]) for row in current]
        if position is None:
            resolved_position = len(current_ids)
        else:
            resolved_position = position
        if resolved_position < 0 or resolved_position > len(current_ids):
            raise ShotValidationError(
                f"insertion position must be within 0 .. {len(current_ids)} "
                f"for shot {shot_id!r}, got {resolved_position}"
            )

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ShotValidationError("created_at must be a non-empty string")
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stream_id = f"{shot_id}:{SHOT_STREAM_TYPE}"

        try:
            metadata_json = canonical_json(metadata_dict)
        except CanonicalizationError as exc:
            raise ShotValidationError(
                f"cannot canonicalize shot item metadata: {exc}"
            ) from exc

        # 1. The new ordered id list with the inserted item at the resolved
        #    position, then the collision-safe renormalization to
        #    deterministic zero-padded position keys.
        new_ids = list(current_ids)
        new_ids.insert(resolved_position, item_id)
        _renormalize_items(uow, shot_id, new_ids)
        uow.execute(
            "INSERT INTO shot_items "
            "(id, shot_id, media_id, sort_key, source_frame, metadata_json, "
            "created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                item_id,
                shot_id,
                media_id,
                _normalized_item_sort_key(resolved_position),
                source_frame,
                metadata_json,
                stamp,
            ),
        )
        # 2. The refreshed shot row (the container changed).
        uow.execute(
            "UPDATE shots SET updated_at = ? WHERE id = ?",
            (stamp, shot_id),
        )
        # 3. The hash-chained shot.item_added event on the shot stream.
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=SHOT_ITEM_ADDED_EVENT_KIND,
            data={
                "shot_id": shot_id,
                "item_id": item_id,
                "media_id": media_id,
                "source_frame": source_frame,
                "metadata": metadata_dict,
                "position": resolved_position,
            },
            changes=[
                "shot_id",
                "item_id",
                "media_id",
                "source_frame",
                "metadata",
                "position",
            ],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 4. The complete receipt with the mutation result (the added item
        #    plus the shot's ordered item ids after the mutation).
        item_model = ShotItemReadModel(
            id=item_id,
            shot_id=shot_id,
            media_id=media_id,
            source_frame=source_frame,
            metadata=metadata_dict,
            sort_key=_normalized_item_sort_key(resolved_position),
            position=resolved_position,
            created_at=stamp,
            event_head_seq=append.stream_seq,
        )
        result = ShotItemMutationReadModel(
            shot_id=shot_id,
            project_id=project_id,
            item=item_model,
            item_ids=tuple(new_ids),
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

    # -- remove_item -------------------------------------------------------

    def remove_item(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        shot_id: str,
        item_id: str,
        idempotency_key: str,
        actor_kind: str = "local",
        created_at: str | None = None,
        command_kind: str = SHOT_REMOVE_ITEM_COMMAND_KIND,
    ) -> ShotItemMutationReadModel:
        """Remove one exact item, preserving its kernel media, atomically.

        Inside the caller's active unit of work this commits, in one
        ``BEGIN IMMEDIATE`` transaction: the ``shot_items`` row delete (the
        kernel media row and its bytes are **preserved** — the DDL
        ``ON DELETE RESTRICT`` pins the media row and this command never
        touches media), the deterministic renormalization of the remaining
        items to zero-padded position keys, the refreshed
        ``shots.updated_at``, the hash-chained ``shot.item_removed`` event
        on the shot's own stream, both heads, and one complete receipt whose
        result carries the removed item's facts (including the preserved
        ``media_id``) and the remaining ordered item ids.

        Rejections happen **before any write**: a missing or foreign shot
        (:class:`ShotNotFoundError`) and a missing or foreign-shot item
        (:class:`ShotItemNotFoundError`) change zero rows. Idempotency
        mirrors the kernel commands: the receipt gate runs first, an
        identical retry returns exactly the stored result with zero new
        rows, and a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        shot_id = _require_non_empty_string("shot_id", shot_id)
        item_id = _require_non_empty_string("item_id", item_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise ShotValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )

        # Semantic request identity: the shot and the exact item identity.
        request: dict[str, Any] = {
            "project_id": project_id,
            "shot_id": shot_id,
            "item_id": item_id,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ShotValidationError(
                f"cannot hash shot remove_item request: {exc}"
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
            return ShotItemMutationReadModel.from_mapping(replayed)

        # Shot/project agreement before any write.
        shot_row = uow.query_one(
            "SELECT id, project_id FROM shots WHERE id = ?",
            (shot_id,),
        )
        if shot_row is None:
            raise ShotNotFoundError(shot_id=shot_id, project_id=project_id)
        if str(shot_row["project_id"]) != project_id:
            raise ShotNotFoundError(shot_id=shot_id, project_id=project_id)

        # Unique item identity before any write: the item must exist and
        # belong to this shot.
        item_row = uow.query_one(
            "SELECT * FROM shot_items WHERE id = ? AND shot_id = ?",
            (item_id, shot_id),
        )
        if item_row is None:
            raise ShotItemNotFoundError(item_id=item_id, shot_id=shot_id)

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ShotValidationError("created_at must be a non-empty string")
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stream_id = f"{shot_id}:{SHOT_STREAM_TYPE}"

        # The removed item's facts (including its preserved media identity)
        # are captured from the row before the delete; the reported position
        # is its normalized position resolved from the stored sort key.
        try:
            removed_position = int(str(item_row["sort_key"]))
        except ValueError:
            removed_position = 0

        # 1. Delete only the shot_items row; the kernel media row and its
        #    bytes are preserved.
        uow.execute(
            "DELETE FROM shot_items WHERE id = ? AND shot_id = ?",
            (item_id, shot_id),
        )
        # 2. Renormalize the remaining items to deterministic positions and
        #    refresh the container row.
        remaining_ids = [
            str(row["id"])
            for row in _ordered_item_rows(uow, shot_id)
            if str(row["id"]) != item_id
        ]
        _renormalize_items(uow, shot_id, remaining_ids)
        uow.execute(
            "UPDATE shots SET updated_at = ? WHERE id = ?",
            (stamp, shot_id),
        )
        # 3. The hash-chained shot.item_removed event carrying the removed
        #    item's facts (preserved media identity).
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=SHOT_ITEM_REMOVED_EVENT_KIND,
            data={
                "shot_id": shot_id,
                "item_id": item_id,
                "media_id": str(item_row["media_id"]),
                "source_frame": item_row["source_frame"],
                "metadata": _parse_object(
                    str(item_row["metadata_json"]),
                    label="shot item",
                    subject=str(item_row["id"]),
                ),
                "removed_position": removed_position,
            },
            changes=[
                "shot_id",
                "item_id",
                "media_id",
                "source_frame",
                "metadata",
                "removed_position",
            ],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        removed = ShotItemReadModel(
            id=str(item_row["id"]),
            shot_id=shot_id,
            media_id=str(item_row["media_id"]),
            source_frame=item_row["source_frame"],
            metadata=_parse_object(
                str(item_row["metadata_json"]),
                label="shot item",
                subject=str(item_row["id"]),
            ),
            sort_key=str(item_row["sort_key"]),
            position=removed_position,
            created_at=str(item_row["created_at"]),
            event_head_seq=append.stream_seq,
        )
        result = ShotItemMutationReadModel(
            shot_id=shot_id,
            project_id=project_id,
            item=removed,
            item_ids=tuple(remaining_ids),
            event_head_seq=append.stream_seq,
            removed_item=removed,
            remaining_item_count=len(remaining_ids),
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

    # -- reorder ----------------------------------------------------------

    def reorder(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        shot_id: str,
        item_ids: Sequence[str],
        idempotency_key: str,
        actor_kind: str = "local",
        created_at: str | None = None,
        command_kind: str = SHOT_REORDER_COMMAND_KIND,
    ) -> ShotReorderReadModel:
        """Reorder a whole shot to one exact permutation of its item ids.

        Inside the caller's active unit of work this commits, in one
        ``BEGIN IMMEDIATE`` transaction: the collision-safe temporary-key
        pass followed by the normalized zero-padded final keys in the
        exact requested order, the refreshed ``shots.updated_at``, the
        single hash-chained ``shot.reordered`` event on the shot's own
        stream, both heads, and one complete receipt whose result carries
        the exact ordered item ids **and** the matching ordered kernel
        media ids.

        Rejections happen **before any write**: a missing or foreign shot
        (:class:`ShotNotFoundError`) and any request that is not an exact
        permutation of the shot's current item ids — omissions,
        duplicates, extras, and foreign-shot items
        (:class:`ShotReorderError`) — all change zero rows. Idempotency
        mirrors the other commands: the receipt gate runs first, an
        identical retry returns exactly the stored result with zero new
        rows, and a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        shot_id = _require_non_empty_string("shot_id", shot_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise ShotValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if isinstance(item_ids, (str, bytes)) or not isinstance(
            item_ids, Sequence
        ):
            raise ShotValidationError(
                "item_ids must be a sequence of item ids"
            )
        requested_ids = list(item_ids)
        for item_id in requested_ids:
            _require_non_empty_string("item_ids element", item_id)

        # Semantic request identity: the shot and the exact ordered item
        # ids participate; generated values never do.
        request: dict[str, Any] = {
            "project_id": project_id,
            "shot_id": shot_id,
            "item_ids": requested_ids,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ShotValidationError(
                f"cannot hash shot reorder request: {exc}"
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
            return ShotReorderReadModel.from_mapping(replayed)

        # Shot/project agreement before any write.
        shot_row = uow.query_one(
            "SELECT id, project_id FROM shots WHERE id = ?",
            (shot_id,),
        )
        if shot_row is None:
            raise ShotNotFoundError(shot_id=shot_id, project_id=project_id)
        if str(shot_row["project_id"]) != project_id:
            raise ShotNotFoundError(shot_id=shot_id, project_id=project_id)

        # Exact-permutation validation before any write: the request must
        # be exactly the shot's current item ids — no omissions, no
        # duplicates, no extras, and no foreign-shot items.
        if len(set(requested_ids)) != len(requested_ids):
            raise ShotReorderError(
                shot_id=shot_id, detail="duplicate", item_ids=requested_ids
            )
        current = _ordered_item_rows(uow, shot_id)
        current_ids = [str(row["id"]) for row in current]
        current_set = set(current_ids)
        requested_set = set(requested_ids)
        if requested_set != current_set:
            missing = sorted(current_set - requested_set)
            if missing:
                raise ShotReorderError(
                    shot_id=shot_id, detail="omission", item_ids=missing
                )
            for item_id in requested_ids:
                if item_id in current_set:
                    continue
                foreign = uow.query_one(
                    "SELECT id, shot_id FROM shot_items WHERE id = ?",
                    (item_id,),
                )
                if (
                    foreign is not None
                    and str(foreign["shot_id"]) != shot_id
                ):
                    raise ShotReorderError(
                        shot_id=shot_id,
                        detail="foreign",
                        item_ids=[item_id],
                    )
                raise ShotReorderError(
                    shot_id=shot_id, detail="extra", item_ids=[item_id]
                )

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ShotValidationError("created_at must be a non-empty string")
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stream_id = f"{shot_id}:{SHOT_STREAM_TYPE}"
        media_by_id = {
            str(row["id"]): str(row["media_id"]) for row in current
        }
        ordered_media_ids = [media_by_id[item_id] for item_id in requested_ids]

        # 1. Collision-safe temporary keys followed by normalized final
        #    keys in the same transaction.
        _renormalize_items(uow, shot_id, requested_ids)
        # 2. The refreshed shot row (the container changed).
        uow.execute(
            "UPDATE shots SET updated_at = ? WHERE id = ?",
            (stamp, shot_id),
        )
        # 3. The single hash-chained shot.reordered event on the shot
        #    stream, carrying the exact ordered item and media ids.
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=SHOT_REORDERED_EVENT_KIND,
            data={
                "shot_id": shot_id,
                "item_ids": requested_ids,
                "media_ids": ordered_media_ids,
            },
            changes=[
                "shot_id",
                "item_ids",
                "media_ids",
            ],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 4. The complete receipt with the exact item and media order.
        result = ShotReorderReadModel(
            shot_id=shot_id,
            project_id=project_id,
            item_ids=tuple(requested_ids),
            media_ids=tuple(ordered_media_ids),
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

    # -- promote_candidate -------------------------------------------------

    def promote_candidate(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        shot_id: str,
        candidate_item_id: str,
        expected_head_seq: int,
        idempotency_key: str,
        actor_kind: str = "local",
        created_at: str | None = None,
        command_kind: str = SHOT_PROMOTE_CANDIDATE_COMMAND_KIND,
    ) -> ShotCandidatePromotionReadModel:
        """Promote one candidate while retaining the previous primary.

        The receipt gate and shot-head CAS both run before projection writes.
        Status lives in the existing item metadata: no promotion table or
        second ledger is introduced.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        shot_id = _require_non_empty_string("shot_id", shot_id)
        candidate_item_id = _require_non_empty_string(
            "candidate_item_id", candidate_item_id
        )
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if (
            isinstance(expected_head_seq, bool)
            or not isinstance(expected_head_seq, int)
            or expected_head_seq < 0
        ):
            raise ShotValidationError(
                "expected_head_seq must be a non-negative integer"
            )
        if actor_kind not in ACTOR_KINDS:
            raise ShotValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )

        request = {
            "project_id": project_id,
            "shot_id": shot_id,
            "candidate_item_id": candidate_item_id,
            "expected_head_seq": expected_head_seq,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ShotValidationError(
                f"cannot hash shot candidate promotion request: {exc}"
            ) from exc

        # Receipt-first: retries never inspect or mutate current shot state.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return ShotCandidatePromotionReadModel.from_mapping(replayed)

        shot_row = uow.query_one(
            "SELECT id, project_id FROM shots WHERE id = ?", (shot_id,)
        )
        if shot_row is None or str(shot_row["project_id"]) != project_id:
            raise ShotNotFoundError(shot_id=shot_id, project_id=project_id)
        stream_id = f"{shot_id}:{SHOT_STREAM_TYPE}"
        stream_row = uow.query_one(
            "SELECT head_seq FROM event_streams WHERE id = ?", (stream_id,)
        )
        if stream_row is None:
            raise ShotNotFoundError(shot_id=shot_id, project_id=project_id)
        actual_head = int(stream_row["head_seq"])
        if actual_head != expected_head_seq:
            raise EventHeadConflictError(
                stream_id=stream_id,
                expected_head_seq=expected_head_seq,
                actual_head_seq=actual_head,
            )

        item_rows = _ordered_item_rows(uow, shot_id)
        candidate_row = next(
            (row for row in item_rows if str(row["id"]) == candidate_item_id),
            None,
        )
        if candidate_row is None:
            raise ShotItemNotFoundError(
                item_id=candidate_item_id, shot_id=shot_id
            )
        candidate_metadata = _parse_object(
            str(candidate_row["metadata_json"]),
            label="shot item",
            subject=candidate_item_id,
        )
        if (
            candidate_metadata.get("role") != "primary_visual"
            or candidate_metadata.get("status") != "candidate"
        ):
            raise ShotValidationError(
                "candidate item must have role='primary_visual' and "
                "status='candidate'"
            )

        primary_rows: list[tuple[Any, dict[str, Any]]] = []
        for row in item_rows:
            metadata = _parse_object(
                str(row["metadata_json"]),
                label="shot item",
                subject=str(row["id"]),
            )
            if (
                metadata.get("role") == "primary_visual"
                and metadata.get("status") == "primary"
            ):
                primary_rows.append((row, metadata))
        if len(primary_rows) > 1:
            raise ShotValidationError(
                "shot must contain at most one primary_visual item"
            )
        previous = primary_rows[0] if primary_rows else None
        if previous is not None and str(previous[0]["id"]) == candidate_item_id:
            raise ShotValidationError("candidate item is already the primary")

        for field, expected in (("project_id", project_id), ("shot_id", shot_id)):
            supplied = candidate_metadata.get(field)
            if supplied is not None and supplied != expected:
                raise ShotValidationError(
                    f"candidate metadata {field!r} does not match the target"
                )
        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ShotValidationError("created_at must be a non-empty string")
        candidate_metadata["status"] = "primary"
        updates = [(candidate_item_id, candidate_metadata)]
        superseded_id: str | None = None
        if previous is not None:
            superseded_id = str(previous[0]["id"])
            previous_metadata = dict(previous[1])
            previous_metadata["status"] = "superseded"
            updates.insert(0, (superseded_id, previous_metadata))
        for item_id, metadata in updates:
            try:
                metadata_json = canonical_json(metadata)
            except CanonicalizationError as exc:
                raise ShotValidationError(
                    f"cannot canonicalize promoted item metadata: {exc}"
                ) from exc
            uow.execute(
                "UPDATE shot_items SET metadata_json = ? WHERE id = ? AND shot_id = ?",
                (metadata_json, item_id, shot_id),
            )
        uow.execute("UPDATE shots SET updated_at = ? WHERE id = ?", (stamp, shot_id))

        txn_id = uuid.uuid4().hex
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=SHOT_CANDIDATE_PROMOTED_EVENT_KIND,
            data={
                "shot_id": shot_id,
                "candidate_item_id": candidate_item_id,
                "primary_item_id": candidate_item_id,
                "superseded_item_id": superseded_id,
                "target_role": "primary_visual",
            },
            changes=[
                "candidate_item_id",
                "primary_item_id",
                "superseded_item_id",
                "target_role",
            ],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            expected_head_seq=expected_head_seq,
            event_id=uuid.uuid4().hex,
            created_at=stamp,
        )
        result = ShotCandidatePromotionReadModel(
            shot_id=shot_id,
            project_id=project_id,
            candidate_item_id=candidate_item_id,
            primary_item_id=candidate_item_id,
            superseded_item_id=superseded_id,
            item_ids=tuple(str(row["id"]) for row in item_rows),
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
        shot_id: str,
    ) -> ShotReadModel:
        """Show one shot with its items in stable sort-key/id order.

        A transaction-free read on a separate read-only connection. A
        missing project raises :class:`ProjectNotFoundError`; a missing or
        foreign shot raises :class:`ShotNotFoundError`. ``items`` is
        ordered by ``sort_key``, then ``id``.
        """
        _require_non_empty_string("project_id", project_id)
        _require_non_empty_string("shot_id", shot_id)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            project = conn.execute(
                "SELECT id FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)
            row = conn.execute(
                "SELECT s.*, st.head_seq FROM shots s "
                "JOIN event_streams st ON st.id = ? "
                "WHERE s.id = ? AND s.project_id = ?",
                (f"{shot_id}:{SHOT_STREAM_TYPE}", shot_id, project_id),
            ).fetchone()
            if row is None:
                raise ShotNotFoundError(shot_id=shot_id, project_id=project_id)
            item_rows = conn.execute(
                "SELECT * FROM shot_items WHERE shot_id = ? "
                "ORDER BY sort_key ASC, id ASC",
                (shot_id,),
            ).fetchall()
        items = tuple(
            ShotItemReadModel(
                id=str(item["id"]),
                shot_id=shot_id,
                media_id=str(item["media_id"]),
                source_frame=item["source_frame"],
                metadata=_parse_object(
                    str(item["metadata_json"]),
                    label="shot item",
                    subject=str(item["id"]),
                ),
                sort_key=str(item["sort_key"]),
                position=position,
                created_at=str(item["created_at"]),
                event_head_seq=int(row["head_seq"]),
            )
            for position, item in enumerate(item_rows)
        )
        return ShotReadModel(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            name=str(row["name"]),
            sort_key=str(row["sort_key"]),
            metadata=_parse_object(
                str(row["metadata_json"]),
                label="shot",
                subject=str(row["id"]),
            ),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            event_head_seq=int(row["head_seq"]),
            items=items,
        )

    def list(
        self,
        writer: DatabaseWriter,
        project_id: str,
    ) -> list[ShotListRow]:
        """Sorted shot list in stable sort-key/id order.

        A transaction-free read on a separate read-only connection. Rows
        are ordered by ``sort_key``, then ``id``. A missing project raises
        :class:`ProjectNotFoundError` — never an empty
        authority-dependent view.
        """
        _require_non_empty_string("project_id", project_id)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            project = conn.execute(
                "SELECT id FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)
            rows = conn.execute(
                "SELECT id, project_id, name, sort_key, created_at, "
                "updated_at FROM shots WHERE project_id = ? "
                "ORDER BY sort_key ASC, id ASC",
                (project_id,),
            ).fetchall()
        return [
            ShotListRow(
                id=str(row["id"]),
                project_id=str(row["project_id"]),
                name=str(row["name"]),
                sort_key=str(row["sort_key"]),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]


__all__ = [
    "SHOT_ADD_ITEM_COMMAND_KIND",
    "SHOT_CANDIDATE_PROMOTED_EVENT_KIND",
    "SHOT_CREATE_COMMAND_KIND",
    "SHOT_CREATED_EVENT_KIND",
    "SHOT_ITEM_ADDED_EVENT_KIND",
    "SHOT_ITEM_REMOVED_EVENT_KIND",
    "SHOT_PROMOTE_CANDIDATE_COMMAND_KIND",
    "SHOT_REMOVE_ITEM_COMMAND_KIND",
    "SHOT_REORDER_COMMAND_KIND",
    "SHOT_REORDERED_EVENT_KIND",
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
    "ShotReorderError",
    "ShotReorderReadModel",
    "ShotRepository",
    "ShotRepositoryError",
    "ShotValidationError",
]
