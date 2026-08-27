"""Generation repository: receipt-free generation/variant commands and
transaction-free gallery reads (27-build-spec section 2.3).

The v1 shots pack owns relational generation identity (``generations``)
and exact media membership (``generation_variants``) but deliberately has
NO per-generation event stream, no generation command vocabulary, and no
generation receipts: the task completion unit of work is the atomicity
record for :meth:`GenerationRepository.record_completion` (build spec
section 5 step 6), and star / set-primary / soft-delete / viewed are small
writer-serialized commands whose DDL constraints — unique media
membership, the ``generation_one_primary`` partial unique index, and
``media_id ... ON DELETE RESTRICT`` — are the surviving invariants. The
shape follows the heartbeat precedent (``core/repositories/tasks.py``):
every fence is evaluated before any statement inside the caller's one
``BEGIN IMMEDIATE`` unit of work, a rejected command changes zero rows,
and no event or receipt row is ever written.

Reads run transaction-free on a separate read-only connection opened via
:meth:`astrid.core.store.writer.DatabaseWriter.read_only_connection`.
Soft-deleted generations disappear from the default gallery surfaces;
their rows and variants survive every command.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
    parse_json,
)
from astrid.core.repositories.errors import RepositoryError
from astrid.core.repositories.projects import ProjectNotFoundError
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.util.paging import decode_keyset_cursor, encode_keyset_cursor
from astrid.core.util.time import utc_now_iso

GENERATION_TYPES: tuple[str, ...] = ("image", "video", "audio", "other")
"""The closed generation type vocabulary (repo-enforced, not DDL-CHECKed)."""

ORIGINAL_VARIANT_TYPE = "original"
"""The variant_type recorded for the initial completion output."""

DEFAULT_LIST_LIMIT = 1000
"""The bounded default page size for the gallery list read."""

DEFAULT_PAGE_LIMIT = 50
"""The gallery route's default page size (doc 27 §4.1)."""

MAX_PAGE_LIMIT = 200
"""The gallery route's hard upper bound on one page."""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GenerationRepositoryError(RepositoryError):
    """Base error for the generation repository family.

    Subclasses :class:`astrid.core.repositories.errors.RepositoryError`
    (and therefore the kernel store error family), so callers catch pack
    contract violations with the kernel error hierarchy.
    """


class GenerationValidationError(GenerationRepositoryError):
    """Raised when a generation argument violates a frozen contract."""


class GenerationAlreadyExistsError(GenerationRepositoryError):
    """Raised when record_completion targets an already-existing id."""

    def __init__(self, generation_id: str) -> None:
        self.generation_id: str = generation_id
        super().__init__(f"generation already exists: {generation_id!r}")


class GenerationNotFoundError(GenerationRepositoryError):
    """Raised when a read or command targets an unknown/foreign generation."""

    def __init__(self, *, generation_id: str, project_id: str) -> None:
        self.generation_id: str = generation_id
        self.project_id: str = project_id
        super().__init__(
            f"unknown or foreign generation {generation_id!r} "
            f"in project {project_id!r}"
        )


class GenerationDeletedError(GenerationRepositoryError):
    """Raised when a mutating command targets a soft-deleted generation."""

    def __init__(self, generation_id: str) -> None:
        self.generation_id: str = generation_id
        super().__init__(
            f"generation {generation_id!r} is deleted and cannot be mutated"
        )


class GenerationMediaError(GenerationRepositoryError):
    """Raised when a variant names missing or foreign media."""

    def __init__(
        self, *, media_id: str, project_id: str, detail: str
    ) -> None:
        self.media_id: str = media_id
        self.project_id: str = project_id
        self.detail: str = detail
        super().__init__(
            f"media {media_id!r} is {detail} for project {project_id!r}"
        )


class GenerationPrimaryError(GenerationRepositoryError):
    """Raised when a primary change cannot be applied."""

    def __init__(self, *, detail: str) -> None:
        self.detail: str = detail
        super().__init__(f"primary change rejected: {detail}")


class VariantNotFoundError(GenerationRepositoryError):
    """Raised when a variant command targets an unknown/foreign variant."""

    def __init__(self, *, generation_id: str, variant_id: str) -> None:
        self.generation_id: str = generation_id
        self.variant_id: str = variant_id
        super().__init__(
            f"unknown or foreign variant {variant_id!r} on generation "
            f"{generation_id!r}"
        )


# ---------------------------------------------------------------------------
# Frozen read models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GenerationVariantReadModel:
    """One immutable ``generation_variants`` row."""

    id: str
    generation_id: str
    media_id: str
    variant_type: str | None
    name: str | None
    params: dict[str, Any]
    is_primary: bool
    starred: bool
    viewed_at: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict for callers."""
        return {
            "id": self.id,
            "generation_id": self.generation_id,
            "media_id": self.media_id,
            "variant_type": self.variant_type,
            "name": self.name,
            "params": dict(self.params),
            "is_primary": self.is_primary,
            "starred": self.starred,
            "viewed_at": self.viewed_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> GenerationVariantReadModel:
        """Rebuild one variant read model from a stored/caller mapping."""
        return cls(
            id=str(value["id"]),
            generation_id=str(value["generation_id"]),
            media_id=str(value["media_id"]),
            variant_type=value.get("variant_type"),
            name=value.get("name"),
            params=dict(value.get("params") or {}),
            is_primary=bool(value.get("is_primary")),
            starred=bool(value.get("starred")),
            viewed_at=value.get("viewed_at"),
            created_at=str(value["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class GenerationReadModel:
    """One immutable generation read model with its ordered variants.

    ``variants`` is ordered primary-first, then by ``created_at``/``id``.
    """

    id: str
    project_id: str
    task_id: str | None
    type: str
    name: str | None
    based_on_generation_id: str | None
    parent_generation_id: str | None
    child_order: int | None
    params: dict[str, Any]
    starred: bool
    deleted_at: str | None
    created_at: str
    updated_at: str
    variants: tuple[GenerationVariantReadModel, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict for callers."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "type": self.type,
            "name": self.name,
            "based_on_generation_id": self.based_on_generation_id,
            "parent_generation_id": self.parent_generation_id,
            "child_order": self.child_order,
            "params": dict(self.params),
            "starred": self.starred,
            "deleted_at": self.deleted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "variants": [variant.to_dict() for variant in self.variants],
        }


@dataclass(frozen=True, slots=True)
class GenerationListRow:
    """One bounded gallery page row with its primary-variant summary."""

    id: str
    project_id: str
    task_id: str | None
    type: str
    name: str | None
    starred: bool
    created_at: str
    updated_at: str
    primary_media_id: str | None
    primary_variant_type: str | None
    variant_count: int


@dataclass(frozen=True, slots=True)
class GenerationPage:
    """One bounded gallery page plus its opaque next-page cursor."""

    rows: tuple[GenerationListRow, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class GenerationPrimaryChangeReadModel:
    """One immutable demote/promote result."""

    generation_id: str
    previous_variant_id: str | None
    variant_id: str


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise GenerationValidationError(f"{name} must be a non-empty string")
    return value


def _decode_generation_cursor(cursor: str) -> tuple[str, str]:
    """Decode one opaque page cursor, or raise the typed validation error."""
    created_at, generation_id = decode_keyset_cursor(cursor, width=2)
    return created_at, generation_id


def _canonical_params(params: Mapping[str, Any] | None, label: str) -> str:
    if params is not None and not isinstance(params, Mapping):
        raise GenerationValidationError(f"{label} must be a JSON object")
    try:
        return canonical_json(dict(params or {}))
    except CanonicalizationError as exc:
        raise GenerationValidationError(
            f"cannot canonicalize {label}: {exc}"
        ) from exc


def _parse_params(raw: str, *, label: str, subject: str) -> dict[str, Any]:
    try:
        parsed = parse_json(raw)
    except CanonicalizationError as exc:
        raise GenerationRepositoryError(
            f"stored {label} for {subject!r} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise GenerationRepositoryError(
            f"stored {label} for {subject!r} is not a JSON object"
        )
    return parsed


def _live_generation_row(uow: UnitOfWork, project_id: str, generation_id: str):
    """The live (non-deleted) generation row, or the typed miss."""
    row = uow.query_one(
        "SELECT * FROM generations WHERE id = ? AND project_id = ?",
        (generation_id, project_id),
    )
    if row is None:
        raise GenerationNotFoundError(
            generation_id=generation_id, project_id=project_id
        )
    if row["deleted_at"] is not None:
        raise GenerationDeletedError(generation_id)
    return row


def _variant_model(row: Any) -> GenerationVariantReadModel:
    """One frozen variant read model from a ``generation_variants`` row."""
    return GenerationVariantReadModel(
        id=str(row["id"]),
        generation_id=str(row["generation_id"]),
        media_id=str(row["media_id"]),
        variant_type=row["variant_type"],
        name=row["name"],
        params=_parse_params(
            str(row["params_json"]), label="params_json", subject=str(row["id"])
        ),
        is_primary=bool(row["is_primary"]),
        starred=bool(row["starred"]),
        viewed_at=row["viewed_at"],
        created_at=str(row["created_at"]),
    )


def _generation_models(rows: list[Any], variants_by_generation: dict[str, tuple[GenerationVariantReadModel, ...]]) -> list[GenerationReadModel]:
    """Frozen generation read models joined with their ordered variants."""
    return [
        GenerationReadModel(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            task_id=row["task_id"],
            type=str(row["type"]),
            name=row["name"],
            based_on_generation_id=row["based_on_generation_id"],
            parent_generation_id=row["parent_generation_id"],
            child_order=row["child_order"],
            params=_parse_params(
                str(row["params_json"]),
                label="params_json",
                subject=str(row["id"]),
            ),
            starred=bool(row["starred"]),
            deleted_at=row["deleted_at"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            variants=variants_by_generation.get(str(row["id"]), ()),
        )
        for row in rows
    ]


_VARIANT_ORDER = (
    # Completion inserts all variants at one timestamp.  ULIDs contain a
    # random component, so use SQLite insertion order as the stable tie-break
    # rather than allowing alternatives to reshuffle in the gallery.
    "ORDER BY is_primary DESC, created_at ASC, rowid ASC, id ASC"
)
"""Primary-first deterministic variant ordering shared by all reads."""


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class GenerationRepository:
    """Stateless generation command/read surface over the kernel unit of work.

    Receipt-free and event-free by design (build spec 2.3): every command
    must run inside the caller's :class:`UnitOfWork` and enforces the DDL
    invariants directly; every read runs transaction-free on a separate
    read-only connection. The repository never constructs a writer and
    never imports another pack.
    """

    # -- record_completion (the completion-UoW creation path) ---------------

    def record_completion(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        task_id: str,
        type: str,
        params: Mapping[str, Any] | None = None,
        variant: Mapping[str, Any] | None = None,
        variants: Sequence[Mapping[str, Any]] | None = None,
        generation_id: str | None = None,
        variant_id: str | None = None,
        created_at: str | None = None,
    ) -> GenerationReadModel:
        """Create one generation plus all materialized variants atomically.

        Runs inside the caller's task-completion unit of work (build spec
        section 5 step 6): one ``generations`` row plus one
        ``generation_variants`` row for each distinct materialized output.
        Exactly one row is primary and always has ``variant_type =
        'original'``. No event stream and no receipt exist for generations;
        the surrounding completion commit is the atomicity record.

        Rejections happen **before any write**: an unknown project, a
        missing/foreign/not-yet-succeeded task, a type outside
        :data:`GENERATION_TYPES`, non-object params, missing or foreign
        media, and a duplicate generation identity all change zero rows.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        task_id = _require_non_empty_string("task_id", task_id)
        _require_non_empty_string("type", type)
        if variant is not None and variants is not None:
            raise GenerationValidationError(
                "provide either variant or variants, not both"
            )
        if variants is None:
            variants = [variant] if variant is not None else []
        if isinstance(variants, (str, bytes)) or not isinstance(variants, Sequence):
            raise GenerationValidationError("variants must be a sequence")
        if not variants:
            raise GenerationValidationError("variants must not be empty")
        normalized_variants: list[dict[str, Any]] = []
        seen_media: set[str] = set()
        seen_variant_ids: set[str] = set()
        primary_count = 0
        for index, raw_variant in enumerate(variants):
            if not isinstance(raw_variant, Mapping):
                raise GenerationValidationError(
                    f"variants[{index}] must be a JSON object"
                )
            media_id = _require_non_empty_string(
                f"variants[{index}].media_id", raw_variant.get("media_id")
            )
            if media_id in seen_media:
                raise GenerationValidationError(
                    f"variant media already member: {media_id!r}"
                )
            seen_media.add(media_id)
            is_primary = raw_variant.get("is_primary", index == 0)
            if not isinstance(is_primary, bool):
                raise GenerationValidationError(
                    f"variants[{index}].is_primary must be a boolean"
                )
            primary_count += int(is_primary)
            variant_name = raw_variant.get("name")
            if variant_name is not None and not isinstance(variant_name, str):
                raise GenerationValidationError(
                    f"variants[{index}].name must be a string"
                )
            variant_type = raw_variant.get("variant_type")
            if variant_type is not None and not isinstance(variant_type, str):
                raise GenerationValidationError(
                    f"variants[{index}].variant_type must be a string"
                )
            normalized_variants.append(
                {
                    "media_id": media_id,
                    "is_primary": is_primary,
                    "variant_type": (
                        ORIGINAL_VARIANT_TYPE
                        if is_primary
                        else (variant_type or "variant")
                    ),
                    "name": variant_name,
                    "params": raw_variant.get("params"),
                    "id": raw_variant.get("id"),
                }
            )
        if primary_count != 1:
            raise GenerationValidationError(
                f"variants must contain exactly one primary (got {primary_count})"
            )
        # Validate/canonicalize every variant before the first INSERT so a
        # malformed later alternative cannot leave a generation behind.
        for index, item in enumerate(normalized_variants):
            item["params_json"] = _canonical_params(
                item.pop("params"), f"variants[{index}].params"
            )
            if item["id"] is not None:
                _require_non_empty_string(f"variants[{index}].id", item["id"])
                if item["id"] in seen_variant_ids:
                    raise GenerationValidationError(
                        f"variant id already supplied: {item['id']!r}"
                    )
                seen_variant_ids.add(item["id"])
        if generation_id is None:
            generation_id = generate_lowercase_ulid()
        else:
            _require_non_empty_string("generation_id", generation_id)
        if variant_id is not None:
            _require_non_empty_string("variant_id", variant_id)

        # The project must exist before any insert.
        if uow.query_one("SELECT id FROM projects WHERE id = ?", (project_id,)) is None:
            raise ProjectNotFoundError(project_id=project_id)

        # Task lineage: same-project and terminal-with-winner only. The
        # completion UoW transitions the attempt before calling this, so a
        # failure here means a caller-ordering bug, never a partial write.
        task = uow.query_one(
            "SELECT id FROM tasks WHERE id = ? AND project_id = ? "
            "AND status = 'succeeded' AND winning_attempt_id IS NOT NULL",
            (task_id, project_id),
        )
        if task is None:
            raise GenerationValidationError(
                f"task {task_id!r} is not a succeeded same-project task "
                "with a winning attempt"
            )

        if type not in GENERATION_TYPES:
            raise GenerationValidationError(
                f"type must be one of {sorted(GENERATION_TYPES)}, got {type!r}"
            )

        # Media agreement: every kernel currency pins to this project.
        for item in normalized_variants:
            item_media_id = str(item["media_id"])
            media = uow.query_one(
                "SELECT id, project_id FROM media WHERE id = ?", (item_media_id,)
            )
            if media is None:
                raise GenerationMediaError(
                    media_id=item_media_id, project_id=project_id, detail="missing"
                )
            if str(media["project_id"]) != project_id:
                raise GenerationMediaError(
                    media_id=item_media_id, project_id=project_id, detail="foreign"
                )

        # Duplicate identity rejection before allocation.
        if (
            uow.query_one(
                "SELECT id FROM generations WHERE id = ?", (generation_id,)
            )
            is not None
        ):
            raise GenerationAlreadyExistsError(generation_id)

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise GenerationValidationError("created_at must be a non-empty string")

        params_json = _canonical_params(params, "generation params")

        # 1. The generation row.
        uow.execute(
            "INSERT INTO generations "
            "(id, project_id, task_id, type, name, params_json, starred, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
            (
                generation_id,
                project_id,
                task_id,
                type,
                None,
                params_json,
                stamp,
                stamp,
            ),
        )
        # 2. Materialize all distinct outputs in caller order.  The unique
        # media membership guard above ensures one row per exact media.
        for index, item in enumerate(normalized_variants):
            item_id = item["id"]
            if item_id is None:
                item_id = (
                    variant_id
                    if item["is_primary"] and variant_id is not None
                    else generate_lowercase_ulid()
                )
            uow.execute(
                "INSERT INTO generation_variants "
                "(id, generation_id, media_id, variant_type, name, params_json, "
                "is_primary, starred, viewed_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)",
                (
                    item_id,
                    generation_id,
                    item["media_id"],
                    item["variant_type"],
                    item["name"],
                    item["params_json"],
                    int(item["is_primary"]),
                    stamp,
                ),
            )
        return self._read_generation(
            uow, project_id, generation_id, include_deleted=False
        )

    # -- small writer-serialized commands ------------------------------------

    def set_starred(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        generation_id: str,
        starred: bool,
        updated_at: str | None = None,
    ) -> GenerationReadModel:
        """Star or unstar one live generation (idempotent).

        A same-state request changes zero rows and keeps ``updated_at``;
        only a real toggle updates the row. No event, no receipt.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        generation_id = _require_non_empty_string("generation_id", generation_id)
        if not isinstance(starred, bool):
            raise GenerationValidationError("starred must be a boolean")
        row = _live_generation_row(uow, project_id, generation_id)
        current = bool(row["starred"])
        if current != starred:
            stamp = updated_at if updated_at is not None else utc_now_iso()
            uow.execute(
                "UPDATE generations SET starred = ?, updated_at = ? "
                "WHERE id = ?",
                (int(starred), stamp, generation_id),
            )
        return self._read_generation(
            uow, project_id, generation_id, include_deleted=False
        )

    def set_primary(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        generation_id: str,
        variant_id: str,
        updated_at: str | None = None,
    ) -> GenerationPrimaryChangeReadModel:
        """Atomically move the one-primary flag to *variant_id*.

        Demotes the current primary and promotes the target inside the one
        unit of work; the ``generation_one_primary`` partial unique index
        would reject any other interleaving. Already-primary is a typed
        rejection (:class:`GenerationPrimaryError` with detail
        ``already_primary``), not a silent rewrite.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        generation_id = _require_non_empty_string("generation_id", generation_id)
        variant_id = _require_non_empty_string("variant_id", variant_id)
        _live_generation_row(uow, project_id, generation_id)

        target = uow.query_one(
            "SELECT id, is_primary FROM generation_variants "
            "WHERE id = ? AND generation_id = ?",
            (variant_id, generation_id),
        )
        if target is None:
            raise VariantNotFoundError(
                generation_id=generation_id, variant_id=variant_id
            )
        if bool(target["is_primary"]):
            raise GenerationPrimaryError(detail="already_primary")

        previous = uow.query_one(
            "SELECT id FROM generation_variants "
            "WHERE generation_id = ? AND is_primary = 1",
            (generation_id,),
        )
        previous_id = str(previous["id"]) if previous is not None else None
        stamp = updated_at if updated_at is not None else utc_now_iso()
        if previous_id is not None:
            uow.execute(
                "UPDATE generation_variants SET is_primary = 0 WHERE id = ?",
                (previous_id,),
            )
        uow.execute(
            "UPDATE generation_variants SET is_primary = 1 WHERE id = ?",
            (variant_id,),
        )
        uow.execute(
            "UPDATE generations SET updated_at = ? WHERE id = ?",
            (stamp, generation_id),
        )
        return GenerationPrimaryChangeReadModel(
            generation_id=generation_id,
            previous_variant_id=previous_id,
            variant_id=variant_id,
        )

    def mark_viewed(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        generation_id: str,
        variant_id: str,
        viewed_at: str | None = None,
    ) -> GenerationVariantReadModel:
        """Stamp one variant's ``viewed_at`` (the last-opened fact)."""
        project_id = _require_non_empty_string("project_id", project_id)
        generation_id = _require_non_empty_string("generation_id", generation_id)
        variant_id = _require_non_empty_string("variant_id", variant_id)
        _live_generation_row(uow, project_id, generation_id)
        if (
            uow.query_one(
                "SELECT id FROM generation_variants "
                "WHERE id = ? AND generation_id = ?",
                (variant_id, generation_id),
            )
            is None
        ):
            raise VariantNotFoundError(
                generation_id=generation_id, variant_id=variant_id
            )
        stamp = viewed_at if viewed_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise GenerationValidationError("viewed_at must be a non-empty string")
        row = uow.query_one(
            "SELECT * FROM generation_variants WHERE id = ?", (variant_id,)
        )
        assert row is not None  # just verified above inside the same txn
        # Viewing is an idempotent transition.  In particular, a retry must
        # not move the stored timestamp forward (the cloud mutation has the
        # same NULL-only predicate).
        if row["viewed_at"] is None:
            uow.execute(
                "UPDATE generation_variants SET viewed_at = ? WHERE id = ? "
                "AND viewed_at IS NULL",
                (stamp, variant_id),
            )
            row = uow.query_one(
                "SELECT * FROM generation_variants WHERE id = ?", (variant_id,)
            )
            assert row is not None
        return _variant_model(row)

    def mark_all_viewed(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        generation_id: str,
        viewed_at: str | None = None,
    ) -> int:
        """Stamp every unviewed variant on one live generation.

        The NULL-only update makes retries safe and keeps the operation scoped
        to the project-owned, non-deleted generation checked above.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        generation_id = _require_non_empty_string("generation_id", generation_id)
        _live_generation_row(uow, project_id, generation_id)
        stamp = viewed_at if viewed_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise GenerationValidationError("viewed_at must be a non-empty string")
        result = uow.execute(
            "UPDATE generation_variants SET viewed_at = ? "
            "WHERE generation_id = ? AND viewed_at IS NULL",
            (stamp, generation_id),
        )
        return max(0, int(result.rowcount))

    def delete(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        generation_id: str,
        deleted_at: str | None = None,
    ) -> GenerationReadModel:
        """Soft-delete one live generation (idempotent).

        Sets ``deleted_at`` and ``updated_at``; variants, media rows, and
        bytes survive. A repeat delete of an already-deleted generation
        changes zero rows and returns the stored state.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        generation_id = _require_non_empty_string("generation_id", generation_id)
        row = uow.query_one(
            "SELECT * FROM generations WHERE id = ? AND project_id = ?",
            (generation_id, project_id),
        )
        if row is None:
            raise GenerationNotFoundError(
                generation_id=generation_id, project_id=project_id
            )
        if row["deleted_at"] is None:
            stamp = deleted_at if deleted_at is not None else utc_now_iso()
            if not isinstance(stamp, str) or not stamp:
                raise GenerationValidationError("deleted_at must be a non-empty string")
            uow.execute(
                "UPDATE generations SET deleted_at = ?, updated_at = ? "
                "WHERE id = ?",
                (stamp, stamp, generation_id),
            )
        return self._read_generation(
            uow, project_id, generation_id, include_deleted=True
        )

    # -- reads (transaction-free, read-only connection) ----------------------

    def show(
        self,
        writer: DatabaseWriter,
        project_id: str,
        generation_id: str,
        *,
        include_deleted: bool = False,
    ) -> GenerationReadModel:
        """Show one generation with its variants, primary first.

        A missing project raises :class:`ProjectNotFoundError`; a missing
        or foreign generation raises :class:`GenerationNotFoundError`; a
        soft-deleted generation raises :class:`GenerationDeletedError`
        unless *include_deleted* is set.
        """
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            self._require_project(conn, project_id)
            row = conn.execute(
                "SELECT * FROM generations WHERE id = ? AND project_id = ?",
                (generation_id, project_id),
            ).fetchone()
            if row is None:
                raise GenerationNotFoundError(
                    generation_id=generation_id, project_id=project_id
                )
            if row["deleted_at"] is not None and not include_deleted:
                raise GenerationDeletedError(generation_id)
            variant_rows = conn.execute(
                f"SELECT * FROM generation_variants WHERE generation_id = ? {_VARIANT_ORDER}",
                (generation_id,),
            ).fetchall()
        variants = tuple(_variant_model(item) for item in variant_rows)
        return _generation_models([row], {str(row["id"]): variants})[0]

    def list(
        self,
        writer: DatabaseWriter,
        project_id: str,
        *,
        type: str | None = None,
        starred_only: bool = False,
        include_deleted: bool = False,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> list[GenerationListRow]:
        """Bounded gallery page in stable ``created_at DESC, id`` order.

        Deleted generations are hidden unless *include_deleted* is set.
        Each row carries the primary variant's ``media_id`` (or ``None``
        when the generation has zero primaries) and its variant count. A
        missing project raises :class:`ProjectNotFoundError`.
        """
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise GenerationValidationError("limit must be a positive integer")
        filters = ["g.project_id = ?"]
        parameters: list[Any] = [project_id]
        if not include_deleted:
            filters.append("g.deleted_at IS NULL")
        if type is not None:
            filters.append("g.type = ?")
            parameters.append(_require_non_empty_string("type", type))
        if starred_only:
            filters.append("g.starred = 1")
        where = " AND ".join(filters)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            self._require_project(conn, project_id)
            rows = conn.execute(
                "SELECT g.*, "
                "(SELECT v.media_id FROM generation_variants v "
                " WHERE v.generation_id = g.id AND v.is_primary = 1 "
                " ORDER BY v.created_at ASC, v.id ASC LIMIT 1) "
                "AS primary_media_id, "
                "(SELECT v.variant_type FROM generation_variants v "
                " WHERE v.generation_id = g.id AND v.is_primary = 1 "
                " ORDER BY v.created_at ASC, v.id ASC LIMIT 1) "
                "AS primary_variant_type, "
                "(SELECT COUNT(*) FROM generation_variants v "
                " WHERE v.generation_id = g.id) AS variant_count "
                f"FROM generations g WHERE {where} "
                "ORDER BY g.created_at DESC, g.id ASC LIMIT ?",
                (*parameters, limit),
            ).fetchall()
        return [
            GenerationListRow(
                id=str(row["id"]),
                project_id=str(row["project_id"]),
                task_id=row["task_id"],
                type=str(row["type"]),
                name=row["name"],
                starred=bool(row["starred"]),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
                primary_media_id=(
                    str(row["primary_media_id"])
                    if row["primary_media_id"] is not None
                    else None
                ),
                variant_count=int(row["variant_count"]),
                primary_variant_type=(
                    str(row["primary_variant_type"])
                    if row["primary_variant_type"] is not None
                    else None
                ),
            )
            for row in rows
        ]

    def page(
        self,
        writer: DatabaseWriter,
        project_id: str,
        *,
        limit: int = DEFAULT_PAGE_LIMIT,
        cursor: str | None = None,
        starred_only: bool = False,
    ) -> GenerationPage:
        """One keyset-paged gallery slice, ``created_at DESC, id ASC``.

        Deleted generations are always hidden. Each row carries the
        primary variant's ``media_id``/``variant_type`` (or ``None``
        when the generation has no primary) and its variant head-count.
        The opaque *cursor* anchors the next slice after the previous
        page's last row; an invalid cursor raises
        :class:`GenerationValidationError`. A missing project raises
        :class:`ProjectNotFoundError`.
        """
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise GenerationValidationError("limit must be an integer")
        if limit < 1 or limit > MAX_PAGE_LIMIT:
            raise GenerationValidationError(
                f"limit must be between 1 and {MAX_PAGE_LIMIT}"
            )
        if cursor is not None and (not isinstance(cursor, str) or not cursor):
            raise GenerationValidationError("cursor must be a non-empty string")
        filters = ["g.project_id = ?", "g.deleted_at IS NULL"]
        parameters: list[Any] = [project_id]
        if starred_only:
            filters.append("g.starred = 1")
        if cursor is not None:
            cursor_created_at, cursor_id = _decode_generation_cursor(cursor)
            filters.append(
                "(g.created_at < ? OR (g.created_at = ? AND g.id > ?))"
            )
            parameters.extend([cursor_created_at, cursor_created_at, cursor_id])
        where = " AND ".join(filters)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            self._require_project(conn, project_id)
            rows = conn.execute(
                "SELECT g.*, "
                "(SELECT v.media_id FROM generation_variants v "
                " WHERE v.generation_id = g.id AND v.is_primary = 1 "
                " ORDER BY v.created_at ASC, v.id ASC LIMIT 1) "
                "AS primary_media_id, "
                "(SELECT v.variant_type FROM generation_variants v "
                " WHERE v.generation_id = g.id AND v.is_primary = 1 "
                " ORDER BY v.created_at ASC, v.id ASC LIMIT 1) "
                "AS primary_variant_type, "
                "(SELECT COUNT(*) FROM generation_variants v "
                " WHERE v.generation_id = g.id) AS variant_count "
                f"FROM generations g WHERE {where} "
                "ORDER BY g.created_at DESC, g.id ASC LIMIT ?",
                (*parameters, limit + 1),
            ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = (
            encode_keyset_cursor(
                str(rows[-1]["created_at"]), str(rows[-1]["id"])
            )
            if has_more
            else None
        )
        return GenerationPage(
            rows=tuple(
                GenerationListRow(
                    id=str(row["id"]),
                    project_id=str(row["project_id"]),
                    task_id=row["task_id"],
                    type=str(row["type"]),
                    name=row["name"],
                    starred=bool(row["starred"]),
                    created_at=str(row["created_at"]),
                    updated_at=str(row["updated_at"]),
                    primary_media_id=(
                        str(row["primary_media_id"])
                        if row["primary_media_id"] is not None
                        else None
                    ),
                    variant_count=int(row["variant_count"]),
                    primary_variant_type=(
                        str(row["primary_variant_type"])
                        if row["primary_variant_type"] is not None
                        else None
                    ),
                )
                for row in rows
            ),
            next_cursor=next_cursor,
        )

    # -- internal -------------------------------------------------------------

    @staticmethod
    def _require_project(conn: sqlite3.Connection, project_id: str) -> None:
        if conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone() is None:
            raise ProjectNotFoundError(project_id=project_id)

    @staticmethod
    def _read_generation(
        uow: UnitOfWork,
        project_id: str,
        generation_id: str,
        *,
        include_deleted: bool,
    ) -> GenerationReadModel:
        """Re-read one generation plus ordered variants inside the txn."""
        row = uow.query_one(
            "SELECT * FROM generations WHERE id = ? AND project_id = ?",
            (generation_id, project_id),
        )
        if row is None:
            raise GenerationNotFoundError(
                generation_id=generation_id, project_id=project_id
            )
        if row["deleted_at"] is not None and not include_deleted:
            raise GenerationDeletedError(generation_id)
        variant_rows = uow.query(
            "SELECT * FROM generation_variants WHERE generation_id = ? "
            + _VARIANT_ORDER,
            (generation_id,),
        )
        variants = tuple(_variant_model(item) for item in variant_rows)
        return _generation_models([row], {str(row["id"]): variants})[0]


__all__ = [
    "DEFAULT_LIST_LIMIT",
    "DEFAULT_PAGE_LIMIT",
    "GENERATION_TYPES",
    "MAX_PAGE_LIMIT",
    "ORIGINAL_VARIANT_TYPE",
    "GenerationAlreadyExistsError",
    "GenerationDeletedError",
    "GenerationListRow",
    "GenerationMediaError",
    "GenerationNotFoundError",
    "GenerationPage",
    "GenerationPrimaryChangeReadModel",
    "GenerationPrimaryError",
    "GenerationReadModel",
    "GenerationRepository",
    "GenerationRepositoryError",
    "GenerationValidationError",
    "GenerationVariantReadModel",
    "VariantNotFoundError",
]
