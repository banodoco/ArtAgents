"""Media repository: atomic receipt-first prepared-media import (m2 plan step 4).

:class:`MediaRepository.import_prepared` is the media vertical's import root:
one writer transaction commits the ``media`` read model (created once per
``(project_id, content_hash)`` — project-scoped byte dedupe), the
``media_locations`` projection, the ``core.media`` event stream (created on
first import, reused on dedupe), the ``core.media.imported`` event (canonical
SD2 envelope, hash-chained), both heads, and one complete
``command_receipts`` row. The caller supplies an already-prepared
:class:`~astrid.core.io.media_import.PreparedMedia` record whose hashing,
probing, and (for managed realms) publication happen through the in-UoW media
helper at the short materialization boundary — never as slow preparation
inside ``BEGIN IMMEDIATE`` (m2 watch item; v10 section 5.3).

Contracts kept here (SD2; success criterion 2):

- **Byte SHA-256 is the sole identity.** ``media.content_hash`` is the
  lowercase SHA-256 of the file's bytes; paths, URLs, and locators never
  participate in identity, so identical bytes at different paths resolve to
  one media row per project and changed bytes change the hash.
- **Dedupe is project-scoped.** The ``UNIQUE (project_id, content_hash)``
  constraint backs the dedupe: the same digest imported twice in one project
  reuses the media row and stream and adds only a new location, while the
  same digest in another project creates its own media row.
- **Receipt-first import.** The receipt idempotency gate runs before any
  sequence allocation, stream creation, or projection write: an identical
  retry under the same stable ``media_id`` and idempotency key returns
  exactly the stored complete result with zero new rows, and a changed
  request under the same key raises :class:`ReceiptMismatchError` before any
  mutation.
- **Typed conflicts.** A second import of identical bytes with the same
  ``(realm, locator)`` (an exact duplicate location) raises
  :class:`MediaConflictError` instead of violating the
  ``UNIQUE (media_id, realm, locator)`` constraint; missing media raises
  :class:`MediaNotFoundError`; malformed arguments raise
  :class:`MediaValidationError`.

The repository is stateless apart from the event append, receipt services,
and the resolved projects root; a single instance is safe to share across
command callers, and every command must run inside the caller's
:class:`astrid.core.store.uow.UnitOfWork` so all writes share one
``BEGIN IMMEDIATE`` transaction.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from astrid.core.ids import generate_lowercase_ulid
from astrid.core.io.media_import import (
    MEDIA_LOCATION_REALMS,
    MediaPathError,
    PreparedMedia,
    managed_media_path,
    media_crash_point,
    publish_prepared_media,
    sha256_file_bytes,
    validate_digest,
    validate_media_kind,
)
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
    parse_json,
    request_hash,
)
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.errors import ACTOR_KINDS, RepositoryError
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.util.time import utc_now_iso

CORE_MEDIA_STREAM_TYPE = "core.media"
"""The kernel stream type every media aggregate owns (one per media row)."""

CORE_MEDIA_IMPORTED_EVENT_KIND = "core.media.imported"
"""The m2 event kind emitted by every prepared-media import."""

CORE_MEDIA_IMPORT_COMMAND_KIND = "core.media.import"
"""The m2 command kind that media import receipts are keyed on."""

CORE_MEDIA_REPLACE_LOCATION_COMMAND_KIND = "core.media.replace_location"
"""The m2 command kind that location-replacement receipts are keyed on
(plan step 5, T7)."""

CORE_MEDIA_LOCATION_REPLACED_EVENT_KIND = "core.media.location_replaced"
"""The m2 event kind emitted by every locator replacement (plan step 5, T7)."""

CORE_MEDIA_RELATE_COMMAND_KIND = "core.media.relate"
"""The m2 command kind that relation receipts are keyed on (plan step 5, T8)."""

CORE_MEDIA_RELATED_EVENT_KIND = "core.media.related"
"""The m2 event kind emitted for every materialized media relation (plan
step 5, T8): one hash-chained event per relation, on the from-media's
stream, in ordinal order."""

CORE_MEDIA_VERIFY_COMMAND_KIND = "core.media.verify"
"""The m4 command kind that media verification receipts are keyed on (plan
step 10)."""

CORE_MEDIA_VERIFIED_EVENT_KIND = "core.media.verified"
"""The m4 event kind emitted by every stable fingerprint-verified
verification (plan step 10)."""

MEDIA_RELATION_KINDS: tuple[str, ...] = (
    "derived_from",
    "variant_of",
    "uses_as_input",
    "mask_for",
    "audio_for",
)
"""The frozen five ``media_relations.kind`` values (m1 decision artifact
section 7, transcribed verbatim in the v10 DDL CHECK). Any other kind is
rejected before SQL (plan step 5, T8)."""

MANAGED_LOCAL_REALM = "managed_local"
"""The default realm: bytes are copied into the managed sha256 digest tree."""

EXTERNAL_LOCAL_REALM = "external_local"
"""The explicit reference-in-place realm (never a silent default; SD2)."""


class EventAppendPort(Protocol):
    def append(self, uow: UnitOfWork, **kwargs: object) -> Any:
        ...


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class MediaRepositoryError(RepositoryError):
    """Base error for the media repository family.

    Subclasses :class:`astrid.core.repositories.errors.RepositoryError`
    (and therefore :class:`astrid.core.store.writer.WriterError`), so the
    kernel store error family catches media contract violations too.
    """


class MediaValidationError(MediaRepositoryError):
    """Raised when a media import argument is invalid."""


class MediaAlreadyExistsError(MediaRepositoryError):
    """Raised when an import targets an already-existing media id."""

    def __init__(self, *, media_id: str) -> None:
        self.media_id: str = media_id
        super().__init__(f"media already exists: {media_id!r}")


class MediaNotFoundError(MediaRepositoryError):
    """Raised when a read targets a media id with no media row."""

    def __init__(self, *, media_id: str) -> None:
        self.media_id: str = media_id
        super().__init__(f"unknown media: {media_id!r}")


class MediaConflictError(MediaRepositoryError):
    """Raised when a media write conflicts with an existing projection.

    ``reason`` is one of ``\"duplicate_location\"`` (the exact same
    ``(realm, locator)`` already exists for this media row — replay with the
    same idempotency key instead), ``\"realm\"`` (the requested realm is not
    one of the frozen three values), ``\"multiple_locations\"`` (a
    replacement targets a realm with more than one location row, so which
    locator to replace is ambiguous), or ``\"media_already_exists\"`` (an
    explicit ``media_id`` is reused across projects).
    """

    def __init__(
        self,
        *,
        media_id: str,
        reason: str,
        detail: str | None = None,
    ) -> None:
        if reason not in (
            "duplicate_location",
            "realm",
            "multiple_locations",
            "media_already_exists",
        ):
            raise ValueError(f"unknown media conflict reason {reason!r}")
        self.media_id: str = media_id
        self.reason: str = reason
        message = f"media conflict for {media_id!r}: {reason}"
        if detail is not None:
            message = f"{message} ({detail})"
        super().__init__(message)


class MediaLocationNotFoundError(MediaRepositoryError):
    """Raised when a replacement targets a realm with no location row.

    The media row exists but has no ``media_locations`` projection for the
    requested realm (e.g. replacing the external location of a media that
    was only ever imported as ``managed_local``). No row is mutated.
    """

    def __init__(self, *, media_id: str, realm: str) -> None:
        self.media_id: str = media_id
        self.realm: str = realm
        super().__init__(f"media {media_id!r} has no {realm!r} location")


class MediaRelationError(MediaRepositoryError):
    """Raised when a media relation edge violates a domain rule.

    ``reason`` is one of:

    - ``\"kind\"`` — the relation kind is not one of the frozen five
      :data:`MEDIA_RELATION_KINDS` (validated before any SQL);
    - ``\"self\"`` — a media cannot relate to itself;
    - ``\"duplicate\"`` — the exact ``(from_media_id, to_media_id, kind,
      ordinal)`` edge already exists or is declared twice in one command;
    - ``\"single_parent\"`` — the from-media already has its one
      ``variant_of`` parent (the ``media_one_variant_parent`` index would
      reject a second parent at commit, so the rule is enforced first);
    - ``\"cycle\"`` — the new ``variant_of`` edge would close a cycle in the
      project's variant graph (variant edges must stay acyclic, v10 §5.1).

    No row is mutated: every relation-domain rule is evaluated before the
    first ``media_relations`` insert or event append, so a violation can
    never leave a partial relation state committed.
    """

    def __init__(
        self,
        *,
        from_media_id: str,
        to_media_id: str | None = None,
        kind: str | None = None,
        reason: str,
        detail: str | None = None,
    ) -> None:
        if reason not in ("kind", "self", "duplicate", "single_parent", "cycle"):
            raise ValueError(f"unknown media relation reason {reason!r}")
        self.from_media_id: str = from_media_id
        self.to_media_id: str | None = to_media_id
        self.kind: str | None = kind
        self.reason: str = reason
        message = f"media relation from {from_media_id!r}"
        if to_media_id is not None:
            message = f"{message} to {to_media_id!r}"
        if kind is not None:
            message = f"{message} ({kind!r})"
        message = f"{message} rejected: {reason}"
        if detail is not None:
            message = f"{message} ({detail})"
        super().__init__(message)


class MediaVerificationError(MediaRepositoryError):
    """Raised when a verified location's bytes changed or mismatch identity.

    The stable-verification command (plan step 10) prepares a fingerprint of
    the location's bytes outside the transaction and re-stats plus re-hashes
    them inside the unit of work. Any mismatch — a changed size/mtime, a
    changed byte digest, or bytes that no longer hash to the media's
    immutable ``content_hash`` — raises this before any event append,
    projection change, head advance, or receipt write, so a mutated or
    replaced location can never reach a verification stamp (zero mutation).
    """

    def __init__(
        self,
        *,
        media_id: str,
        reason: str,
        detail: str | None = None,
    ) -> None:
        if reason not in ("changed",):
            raise ValueError(f"unknown media verification reason {reason!r}")
        self.media_id: str = media_id
        self.reason: str = reason
        message = f"media {media_id!r} verification rejected: {reason}"
        if detail is not None:
            message = f"{message} ({detail})"
        super().__init__(message)


# ---------------------------------------------------------------------------
# Frozen read models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MediaLocationReadModel:
    """One immutable ``media_locations`` projection (m2 plan step 4).

    A location is a replaceable pointer to the media bytes — the managed
    path for ``managed_local`` or an explicit external path for
    ``external_local``. It never participates in media identity (SD2).
    ``verified_at`` records when the location's bytes were last verified
    against the media digest.
    """

    id: str
    media_id: str
    realm: str
    locator: str
    verified_at: str | None
    created_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise MediaValidationError("location id must be a non-empty string")
        if not isinstance(self.media_id, str) or not self.media_id:
            raise MediaValidationError("media_id must be a non-empty string")
        if self.realm not in MEDIA_LOCATION_REALMS:
            raise MediaValidationError(
                f"realm must be one of {MEDIA_LOCATION_REALMS}, got {self.realm!r}"
            )
        if not isinstance(self.locator, str) or not self.locator:
            raise MediaValidationError("locator must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe mapping persisted in results and events."""
        return {
            "id": self.id,
            "media_id": self.media_id,
            "realm": self.realm,
            "locator": self.locator,
            "verified_at": self.verified_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> MediaLocationReadModel:
        """Rebuild the frozen location read model from a stored mapping."""
        return cls(
            id=str(value["id"]),
            media_id=str(value["media_id"]),
            realm=str(value["realm"]),
            locator=str(value["locator"]),
            verified_at=value.get("verified_at"),
            created_at=str(value["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class MediaReadModel:
    """Immutable media read model (m2 plan step 4).

    A frozen projection of one ``media`` row plus its parsed
    ``metadata_json`` and the ordered ``media_locations`` projections.
    ``content_hash`` is the byte SHA-256 — the sole identity. Read models
    are never mutated in place; repository commands return new instances.
    """

    id: str
    project_id: str
    media_kind: str
    mime_type: str
    byte_size: int
    content_hash: str
    metadata: Mapping[str, Any]
    created_at: str
    locations: tuple[MediaLocationReadModel, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "media_kind": self.media_kind,
            "mime_type": self.mime_type,
            "byte_size": self.byte_size,
            "content_hash": self.content_hash,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "locations": [location.to_dict() for location in self.locations],
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> MediaReadModel:
        """Rebuild the frozen read model from a stored result mapping."""
        return cls(
            id=str(value["id"]),
            project_id=str(value["project_id"]),
            media_kind=str(value["media_kind"]),
            mime_type=str(value["mime_type"]),
            byte_size=int(value["byte_size"]),
            content_hash=str(value["content_hash"]),
            metadata=dict(value.get("metadata") or {}),
            created_at=str(value["created_at"]),
            locations=tuple(
                MediaLocationReadModel.from_mapping(loc)
                for loc in (value.get("locations") or [])
            ),
        )


@dataclass(frozen=True, slots=True)
class MediaRelationReadModel:
    """One immutable ``media_relations`` edge (m2 plan step 5, T8).

    A relation is a directed edge ``from_media_id → to_media_id`` with one
    of the frozen five :data:`MEDIA_RELATION_KINDS`, a stable ``ordinal``
    (the edge's position in the from-media's ordered relation list), and
    bounded JSON ``metadata``. Edges are immutable: ``relate`` writes them
    once per command and no later command mutates the graph.
    """

    from_media_id: str
    to_media_id: str
    kind: str
    ordinal: int
    metadata: Mapping[str, Any]
    created_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.from_media_id, str) or not self.from_media_id:
            raise MediaValidationError("from_media_id must be a non-empty string")
        if not isinstance(self.to_media_id, str) or not self.to_media_id:
            raise MediaValidationError("to_media_id must be a non-empty string")
        if self.from_media_id == self.to_media_id:
            raise MediaValidationError("a media cannot relate to itself")
        if self.kind not in MEDIA_RELATION_KINDS:
            raise MediaValidationError(
                f"relation kind must be one of {MEDIA_RELATION_KINDS}, "
                f"got {self.kind!r}"
            )
        if isinstance(self.ordinal, bool) or not isinstance(
            self.ordinal, int
        ) or self.ordinal < 0:
            raise MediaValidationError(
                f"relation ordinal must be a non-negative integer, "
                f"got {self.ordinal!r}"
            )
        if not isinstance(self.metadata, Mapping):
            raise MediaValidationError("relation metadata must be a JSON object")

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe mapping persisted in events and receipts."""
        return {
            "from_media_id": self.from_media_id,
            "to_media_id": self.to_media_id,
            "kind": self.kind,
            "ordinal": self.ordinal,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> MediaRelationReadModel:
        """Rebuild the frozen relation read model from a stored mapping."""
        return cls(
            from_media_id=str(value["from_media_id"]),
            to_media_id=str(value["to_media_id"]),
            kind=str(value["kind"]),
            ordinal=int(value["ordinal"]),
            metadata=dict(value.get("metadata") or {}),
            created_at=str(value.get("created_at") or ""),
        )


@dataclass(frozen=True, slots=True)
class MediaRelateReadModel:
    """The immutable result of one :meth:`MediaRepository.relate` command.

    Carries the materialized ``media_relations`` edges in materialization
    order (ordinal ascending, deterministic tiebreak). ``to_dict`` is the
    JSON-safe persisted receipt shape and ``from_mapping`` rebuilds it for
    exact replay, so an identical retry under the same idempotency key
    returns exactly the stored relate result.
    """

    relations: tuple[MediaRelationReadModel, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.relations, tuple) or not self.relations:
            raise MediaValidationError(
                "a relate result must carry at least one relation"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the relate receipt result."""
        return {
            "relations": [relation.to_dict() for relation in self.relations],
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> MediaRelateReadModel:
        """Rebuild the frozen relate read model from a stored mapping."""
        return cls(
            relations=tuple(
                MediaRelationReadModel.from_mapping(rel)
                for rel in (value.get("relations") or [])
            )
        )


@dataclass(frozen=True, slots=True)
class MaterializedMedia:
    """One receipt-less in-UoW media materialization (m2 plan step 10, T17).

    The result of :meth:`MediaRepository.materialize_prepared`: the media id
    (created or project-scoped dedupe), the appended ``core.media.imported``
    event evidence (event id, stream id, exact project/stream sequences),
    the location row, the managed publication reuse flag, and — when the
    caller supplied relations — the materialized relation edges. No receipt
    is written by the helper: the caller's completion command records the
    one complete receipt covering every ordered event id.
    """

    media_id: str
    event_id: str
    stream_id: str
    project_seq: int
    stream_seq: int
    location_id: str
    reused: bool | None
    relations: tuple[MediaRelationReadModel, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe mapping for completion receipts."""
        return {
            "media_id": self.media_id,
            "event_id": self.event_id,
            "stream_id": self.stream_id,
            "project_seq": self.project_seq,
            "stream_seq": self.stream_seq,
            "location_id": self.location_id,
            "reused": self.reused,
            "relations": [rel.to_dict() for rel in self.relations],
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> MaterializedMedia:
        """Rebuild the frozen materialization result from a mapping."""
        return cls(
            media_id=str(value["media_id"]),
            event_id=str(value["event_id"]),
            stream_id=str(value["stream_id"]),
            project_seq=int(value["project_seq"]),
            stream_seq=int(value["stream_seq"]),
            location_id=str(value["location_id"]),
            reused=value.get("reused"),
            relations=tuple(
                MediaRelationReadModel.from_mapping(rel)
                for rel in (value.get("relations") or [])
            ),
        )


# ---------------------------------------------------------------------------
# Prepared verification fingerprint (m4 plan step 10)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MediaFingerprint:
    """One prepared location fingerprint for stable verification.

    Captures, **outside any transaction**, the byte size, nanosecond mtime,
    and lowercase SHA-256 digest of a location's bytes. The verify command
    re-stats and re-hashes the same path inside the unit of work and compares
    against this record, so any change between preparation and commit — a
    byte mutation, a replacement, or a missing file — is detected before any
    event, head, projection, or receipt write (the time-of-check/time-of-use
    race is closed).
    """

    path: str
    byte_size: int
    mtime_ns: int
    digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path:
            raise MediaValidationError("fingerprint path must be a non-empty string")
        if isinstance(self.byte_size, bool) or not isinstance(
            self.byte_size, int
        ) or self.byte_size < 0:
            raise MediaValidationError(
                "fingerprint byte_size must be a non-negative integer"
            )
        if isinstance(self.mtime_ns, bool) or not isinstance(self.mtime_ns, int):
            raise MediaValidationError("fingerprint mtime_ns must be an integer")
        validate_digest(self.digest)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe mapping (not persisted, used for inspection)."""
        return {
            "path": self.path,
            "byte_size": self.byte_size,
            "mtime_ns": self.mtime_ns,
            "digest": self.digest,
        }


def prepare_media_fingerprint(path: str | Path) -> MediaFingerprint:
    """Hash one location outside any transaction (m4 plan step 10).

    Stats and hashes *path* to produce the immutable :class:`MediaFingerprint`
    a caller passes into :meth:`MediaRepository.verify`. A missing, symlink,
    or non-regular path raises :class:`MediaPathError` before any SQL, exactly
    like the other preparation entry points in ``astrid.core.io.media_import``.
    """
    file_path = Path(path)
    if file_path.is_symlink() or not file_path.is_file():
        raise MediaPathError(f"prepared file must be a regular file: {file_path!s}")
    stat = file_path.stat()
    return MediaFingerprint(
        path=str(file_path),
        byte_size=int(stat.st_size),
        mtime_ns=int(stat.st_mtime_ns),
        digest=sha256_file_bytes(file_path),
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise MediaValidationError(f"{name} must be a non-empty string")
    return value


def _query_one(reader: Any, sql: str, parameters: Sequence[Any] = ()) -> Any:
    """Run one read on a UoW/WriterSession reader or a raw connection.

    The unit of work and the writer session expose ``query_one(sql, params)``;
    a ``sqlite3.Connection`` exposes ``execute(...).fetchone()``. Both shapes
    are accepted so the project-scoped media resolution helper works both
    transaction-free on a read-only connection and inside a ``BEGIN
    IMMEDIATE`` unit of work.
    """
    query_one = getattr(reader, "query_one", None)
    if query_one is not None:
        return query_one(sql, parameters)
    cursor = reader.execute(sql, parameters)
    return cursor.fetchone()


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class MediaRepository:
    """Stateless media command surface over the kernel unit of work."""

    def __init__(
        self,
        events: EventAppendPort,
        receipts: ReceiptService,
        projects_root: str | Path,
    ) -> None:
        self._events = events
        self._receipts = receipts
        self._projects_root = Path(projects_root)

    # -- project-scoped resolution (m4 plan step 9) ------------------------

    def resolve_media(
        self,
        reader: Any,
        *,
        project_id: str,
        media_id: str | None = None,
        realm: str | None = None,
        locator: str | None = None,
    ) -> str:
        """Resolve an explicit media id or locator alias within one project.

        Every media reference is project-scoped (m4 plan step 9): the lookup
        joins to ``media.project_id`` equal to the route *project_id*, so a
        media id — or a ``(realm, locator)`` alias — that belongs to another
        project is indistinguishable from an unknown one and raises
        :class:`MediaNotFoundError` (no existence leak across projects).
        Locators are never globally unique in the frozen schema and are
        replaceable aliases, never media identity (SD2).

        Exactly one of ``media_id`` or the ``realm``/``locator`` alias pair
        must be supplied. Accepts a unit of work (in-UoW resolution inside a
        command) or a read-only ``sqlite3.Connection`` (transaction-free
        lookup), and returns the canonical media id on success.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        has_id = media_id is not None
        has_locator = realm is not None or locator is not None
        if has_id == has_locator:
            raise MediaValidationError(
                "resolve_media requires exactly one of media_id or the "
                "(realm, locator) alias pair"
            )
        if has_id:
            media_id = _require_non_empty_string("media_id", media_id)
            row = _query_one(
                reader,
                "SELECT id FROM media WHERE id = ? AND project_id = ?",
                (media_id, project_id),
            )
            if row is None:
                raise MediaNotFoundError(media_id=media_id)
            return str(row["id"])
        realm = _require_non_empty_string("realm", realm)
        locator = _require_non_empty_string("locator", locator)
        row = _query_one(
            reader,
            "SELECT m.id AS media_id FROM media_locations l "
            "JOIN media m ON m.id = l.media_id "
            "WHERE l.realm = ? AND l.locator = ? AND m.project_id = ? "
            "LIMIT 1",
            (realm, locator, project_id),
        )
        if row is None:
            raise MediaNotFoundError(media_id=f"{realm}:{locator}")
        return str(row["media_id"])

    # -- prepared import ---------------------------------------------------

    def import_prepared(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        prepared: PreparedMedia,
        idempotency_key: str,
        actor_kind: str = "local",
        media_id: str | None = None,
        realm: str = MANAGED_LOCAL_REALM,
        locator: str | None = None,
        created_at: str | None = None,
        command_kind: str = CORE_MEDIA_IMPORT_COMMAND_KIND,
    ) -> MediaReadModel:
        """Import one already-prepared media file atomically and idempotently.

        Inside the caller's active unit of work this persists, in one
        ``BEGIN IMMEDIATE`` transaction: the ``media`` read model (created
        only when this ``(project_id, content_hash)`` pair is new —
        project-scoped byte dedupe), the ``media_locations`` projection, the
        ``core.media`` stream (created on first import, reused on dedupe),
        the ``core.media.imported`` event (canonical envelope, chained from
        genesis), both heads, and one complete receipt. For the default
        ``managed_local`` realm the prepared bytes are published through the
        in-UoW media helper (atomic rename + fsync + verified reuse) at the
        short materialization boundary; ``external_local`` is the explicit
        reference-in-place realm and never silently falls back (SD2).

        *prepared* is an immutable :class:`PreparedMedia` record whose
        hashing/probing already ran outside the transaction. The identical
        retry contract (same stable *media_id* and *idempotency_key*) returns
        the stored result with zero new rows; a changed request under the
        same key raises :class:`ReceiptMismatchError` before any mutation.
        Two different paths with identical bytes in the same project produce
        one media row and one location each; the exact duplicate location
        (same realm and locator) under a different key raises
        :class:`MediaConflictError`.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if not isinstance(prepared, PreparedMedia):
            raise MediaValidationError(
                "prepared must be a PreparedMedia record, got "
                f"{type(prepared).__name__}"
            )
        if realm not in MEDIA_LOCATION_REALMS:
            raise MediaConflictError(
                media_id=media_id or "",
                reason="realm",
                detail=f"expected one of {MEDIA_LOCATION_REALMS}, got {realm!r}",
            )
        if actor_kind not in ACTOR_KINDS:
            raise MediaValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if media_id is None:
            media_id = generate_lowercase_ulid()
        else:
            _require_non_empty_string("media_id", media_id)

        # The location is part of the request identity: a different locator
        # under the same key is a mismatch, not a silent dedupe.
        if locator is None:
            if realm == MANAGED_LOCAL_REALM:
                locator = str(managed_media_path(self._projects_root, prepared.digest))
            else:
                locator = str(prepared.source_path)
        else:
            locator = _require_non_empty_string("locator", locator)

        # Semantic request identity: stable media id, byte digest, derived
        # facts, and the location all participate; generated values (the
        # location row id, timestamps) are excluded.
        request = {
            "media_id": media_id,
            "content_hash": prepared.digest,
            "media_kind": prepared.media_kind,
            "mime_type": prepared.mime_type,
            "byte_size": prepared.byte_size,
            "realm": realm,
            "locator": locator,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise MediaValidationError(
                f"cannot hash media import request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch happens before any
        # sequence allocation, event append, or projection change.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return MediaReadModel.from_mapping(replayed)

        # The project must exist before any media/stream row is inserted.
        if uow.query_one("SELECT id FROM projects WHERE id = ?", (project_id,)) is None:
            raise MediaValidationError(
                f"media import requires an existing project: {project_id!r}"
            )

        # Project-scoped content-hash dedupe (SD2): identical bytes in the
        # same project reuse the media row and its stream. The managed
        # locator is digest-derived, so a managed dedupe shares the existing
        # location; only an exact external duplicate (same realm and
        # locator) is a typed conflict.
        existing = uow.query_one(
            "SELECT id FROM media WHERE project_id = ? AND content_hash = ?",
            (project_id, prepared.digest),
        )
        if existing is not None:
            media_id = str(existing["id"])
            duplicate = uow.query_one(
                "SELECT id FROM media_locations "
                "WHERE media_id = ? AND realm = ? AND locator = ?",
                (media_id, realm, locator),
            )
            if duplicate is not None and realm == EXTERNAL_LOCAL_REALM:
                raise MediaConflictError(
                    media_id=media_id,
                    reason="duplicate_location",
                    detail=f"realm={realm!r} locator={locator!r} already exists",
                )
        else:
            duplicate_media = uow.query_one(
                "SELECT id FROM media WHERE id = ?", (media_id,)
            )
            if duplicate_media is not None:
                raise MediaAlreadyExistsError(media_id=media_id)

        return self._insert(
            uow,
            project_id=project_id,
            prepared=prepared,
            media_id=media_id,
            realm=realm,
            locator=locator,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            command_kind=command_kind,
            actor_kind=actor_kind,
            created_at=created_at,
        )

    # -- location replacement (m2 plan step 5, T7) ------------------------

    def replace_location(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        media_id: str,
        idempotency_key: str,
        realm: str,
        locator: str,
        actor_kind: str = "local",
        created_at: str | None = None,
        command_kind: str = CORE_MEDIA_REPLACE_LOCATION_COMMAND_KIND,
    ) -> MediaReadModel:
        """Replace one locator projection atomically without changing identity.

        Inside the caller's active unit of work this re-points exactly the
        media's single ``realm`` location. Only the ``media_locations``
        projection changes: the ``media`` row (``content_hash`` and every
        derived fact) is untouched, and the immutable stream history grows by
        exactly one hash-chained ``core.media.location_replaced`` event plus
        one complete receipt (SD2: paths and locators are replaceable
        aliases, never identity).

        - ``managed_local`` — the new locator must be the digest-derived
          managed path (the canonical pointer), so the replacement is a
          verified refresh that stamps ``verified_at`` with the command
          instant.
        - ``external_local`` — the new locator is the explicit external path
          (reference-in-place, never verified; ``verified_at`` stays
          ``NULL``, exactly as at import).
        - ``remote`` is rejected: m2 replaces only local locators.

        Ownership: the media row must exist and belong to *project_id*
        (:class:`MediaNotFoundError` otherwise), and exactly one location of
        *realm* must exist for that media (:class:`MediaLocationNotFoundError`
        when none, :class:`MediaConflictError` with reason
        ``multiple_locations`` when several make the target ambiguous).

        Idempotency: the receipt gate runs first. An identical retry under
        the same key returns the stored result with zero new rows; a changed
        request under the same key raises :class:`ReceiptMismatchError`
        before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        media_id = _require_non_empty_string("media_id", media_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if realm not in (MANAGED_LOCAL_REALM, EXTERNAL_LOCAL_REALM):
            raise MediaValidationError(
                "replace_location supports only the local realms "
                f"{MANAGED_LOCAL_REALM!r} and {EXTERNAL_LOCAL_REALM!r}, "
                f"got {realm!r}"
            )
        locator = _require_non_empty_string("locator", locator)
        if actor_kind not in ACTOR_KINDS:
            raise MediaValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )

        # Semantic request identity: the target media, realm, and the new
        # locator. The media digest and every derived fact are excluded —
        # replacement never changes identity.
        request = {
            "media_id": media_id,
            "realm": realm,
            "locator": locator,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise MediaValidationError(
                f"cannot hash replace_location request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch happens before any
        # sequence allocation, event append, or projection change.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return MediaReadModel.from_mapping(replayed)

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise MediaValidationError("created_at must be a non-empty string")

        # Project ownership: the media row must exist in this project. A
        # media id that exists in another project is indistinguishable from
        # an unknown one (no existence leak across projects).
        media_row = uow.query_one(
            "SELECT * FROM media WHERE id = ? AND project_id = ?",
            (media_id, project_id),
        )
        if media_row is None:
            raise MediaNotFoundError(media_id=media_id)
        content_hash = str(media_row["content_hash"])

        # The target location: exactly one row for (media_id, realm). The
        # realm discriminator is deterministic only when the projection is
        # unambiguous, so a second row is a typed conflict, never a guess.
        location_rows = uow.query(
            "SELECT id, realm, locator, verified_at, created_at "
            "FROM media_locations WHERE media_id = ? AND realm = ? "
            "ORDER BY created_at ASC, id ASC",
            (media_id, realm),
        )
        if not location_rows:
            raise MediaLocationNotFoundError(media_id=media_id, realm=realm)
        if len(location_rows) > 1:
            raise MediaConflictError(
                media_id=media_id,
                reason="multiple_locations",
                detail=(
                    f"realm={realm!r} has {len(location_rows)} locations; "
                    "replacement requires an unambiguous single location"
                ),
            )
        location_row = location_rows[0]
        location_id = str(location_row["id"])
        previous_locator = str(location_row["locator"])

        if realm == MANAGED_LOCAL_REALM:
            # The managed locator is digest-derived by construction; an
            # arbitrary managed locator would break the sha256 tree layout.
            canonical = str(managed_media_path(self._projects_root, content_hash))
            if locator != canonical:
                raise MediaValidationError(
                    "managed_local replacement requires the digest-derived "
                    f"managed path, got {locator!r} (expected {canonical!r})"
                )
            new_verified_at = stamp
        else:
            # external_local: reference-in-place, never verified.
            new_verified_at = None

        # Defensive duplicate check: another location of the same media and
        # realm must not already hold the target locator (the UNIQUE
        # constraint would reject the UPDATE at commit).
        if (
            str(location_row["locator"]) != locator
            and uow.query_one(
                "SELECT 1 FROM media_locations "
                "WHERE media_id = ? AND realm = ? AND locator = ? "
                "AND id <> ?",
                (media_id, realm, locator, location_id),
            )
            is not None
        ):
            raise MediaConflictError(
                media_id=media_id,
                reason="duplicate_location",
                detail=f"realm={realm!r} locator={locator!r} already exists",
            )

        # 1. The only projection change: locator (and, for the managed
        #    realm, the verified-at stamp). The media row never changes.
        uow.execute(
            "UPDATE media_locations SET locator = ?, verified_at = ? "
            "WHERE id = ?",
            (locator, new_verified_at, location_id),
        )

        # 2. The hash-chained core.media.location_replaced event on the
        #    media stream; the append advances both heads atomically.
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stream_id = f"{media_id}:{CORE_MEDIA_STREAM_TYPE}"
        event_data: dict[str, Any] = {
            "media_id": media_id,
            "content_hash": content_hash,
            "realm": realm,
            "locator": locator,
            "previous_locator": previous_locator,
            "location_id": location_id,
            "verified_at": new_verified_at,
        }
        changes: list[str] = ["realm", "locator", "previous_locator", "verified_at"]
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_MEDIA_LOCATION_REPLACED_EVENT_KIND,
            data=event_data,
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )

        # 3. The complete receipt: the refreshed media read model.
        read_model = self._media_read_model(uow, media_id=media_id, project_id=project_id)
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

    # -- media relations (m2 plan step 5, T8) -----------------------------

    def relate(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        relations: Sequence[Mapping[str, Any]],
        idempotency_key: str,
        actor_kind: str = "local",
        created_at: str | None = None,
        command_kind: str = CORE_MEDIA_RELATE_COMMAND_KIND,
    ) -> MediaRelateReadModel:
        """Materialize media relation edges atomically and idempotently.

        Inside the caller's active unit of work this persists, in one
        ``BEGIN IMMEDIATE`` transaction: one ``media_relations`` row per
        requested edge in ordinal order, one hash-chained
        ``core.media.related`` event per edge on the from-media's stream
        (so every affected media stream head advances), the project head,
        and one complete receipt spanning the whole event range.

        Every invariant is evaluated **before** the first SQL write, so a
        rejected command changes zero rows (no partial relation state):

        - **Frozen vocabulary.** ``kind`` must be one of the frozen five
          :data:`MEDIA_RELATION_KINDS` (m1 decision artifact section 7),
          validated before hashing or any SQL;
        - **No self-links.** ``from_media_id`` and ``to_media_id`` must
          differ (the DDL CHECK backs this too);
        - **Same project.** every endpoint must name a ``media`` row in
          *project_id*; unknown and cross-project endpoints are
          indistinguishable (:class:`MediaNotFoundError`, no existence
          leak);
        - **No duplicates.** the exact ``(from, to, kind, ordinal)`` edge
          may not already exist nor be declared twice in one command
          (the table's primary key backs this);
        - **One variant parent.** each media has at most one
          ``variant_of`` parent — one per ``from_media_id`` in the whole
          project (the ``media_one_variant_parent`` index backs this);
        - **Acyclic variants.** the new ``variant_of`` edges must not close
          a cycle in the project's variant graph (v10 §5.1), including
          cycles that span several new edges or existing ones.

        *relations* is a non-empty sequence of mappings, each with
        ``from_media_id``, ``to_media_id``, ``kind``, an optional
        ``ordinal`` (default 0) and optional ``metadata`` (default ``{}``).
        Edges materialize in ordinal order with a deterministic tiebreak
        (ordinal, then from id, then to id, then kind), and the events
        follow the same order, so the receipt's ``event_ids`` and the
        ``first_project_seq``…``last_project_seq`` range prove one atomic
        contiguous commit.

        Idempotency: the receipt gate runs first. An identical retry under
        the same key returns exactly the stored relate result with zero new
        rows; a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise MediaValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if (
            isinstance(relations, (str, bytes))
            or not isinstance(relations, Sequence)
            or not relations
        ):
            raise MediaValidationError(
                "relations must be a non-empty sequence of relation mappings"
            )

        # 1. Normalize and validate every edge (frozen kinds, self-links,
        #    ordinals, metadata, in-command duplicates) BEFORE SQL, and
        #    order the edges for materialization.
        normalized = self._normalize_relations(relations)

        # Semantic request identity: exactly the caller-supplied relation
        # set (normalized, so equivalent spellings hash identically); the
        # created-at stamp is generated state and never participates.
        request = {
            "relations": [
                {
                    "from_media_id": rel.from_media_id,
                    "to_media_id": rel.to_media_id,
                    "kind": rel.kind,
                    "ordinal": rel.ordinal,
                    "metadata": dict(rel.metadata),
                }
                for rel in normalized
            ]
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise MediaValidationError(
                f"cannot hash media relate request: {exc}"
            ) from exc

        # Idempotency gate first: replay or mismatch before any query or
        # sequence allocation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return MediaRelateReadModel.from_mapping(replayed)

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise MediaValidationError("created_at must be a non-empty string")

        # 2. Same-project endpoints: every from/to id must name a media row
        #    in this project. Unknown and foreign ids are indistinguishable
        #    (no existence leak across projects).
        endpoint_ids = {
            rel.from_media_id for rel in normalized
        } | {rel.to_media_id for rel in normalized}
        placeholders = ", ".join("?" * len(endpoint_ids))
        media_rows = uow.query(
            "SELECT id FROM media WHERE project_id = ? AND id IN ("
            + placeholders
            + ")",
            (project_id, *sorted(endpoint_ids)),
        )
        existing_ids = {str(row["id"]) for row in media_rows}
        missing = sorted(endpoint_ids - existing_ids)
        if missing:
            raise MediaNotFoundError(media_id=missing[0])

        # 3. No exact duplicates against committed edges (the PK would
        #    reject them at commit; the rule runs first).
        edge_placeholders = ", ".join("?" * len(endpoint_ids))
        existing_edges = uow.query(
            "SELECT from_media_id, to_media_id, kind, ordinal "
            "FROM media_relations "
            "WHERE from_media_id IN (" + edge_placeholders + ") "
            "AND to_media_id IN (" + edge_placeholders + ")",
            (*sorted(endpoint_ids), *sorted(endpoint_ids)),
        )
        existing_edge_keys = {
            (
                str(row["from_media_id"]),
                str(row["to_media_id"]),
                str(row["kind"]),
                int(row["ordinal"]),
            )
            for row in existing_edges
        }
        for rel in normalized:
            key = (rel.from_media_id, rel.to_media_id, rel.kind, rel.ordinal)
            if key in existing_edge_keys:
                raise MediaRelationError(
                    from_media_id=rel.from_media_id,
                    to_media_id=rel.to_media_id,
                    kind=rel.kind,
                    reason="duplicate",
                    detail="the exact edge already exists",
                )

        # 4. One variant_of parent per media: load the project's committed
        #    variant edges and reject any new edge whose from-media already
        #    has a parent (or would get two in this command).
        variant_rows = uow.query(
            "SELECT r.from_media_id, r.to_media_id FROM media_relations r "
            "JOIN media m ON m.id = r.from_media_id "
            "WHERE m.project_id = ? AND r.kind = 'variant_of'",
            (project_id,),
        )
        variant_graph = [
            (str(row["from_media_id"]), str(row["to_media_id"]))
            for row in variant_rows
        ]
        variant_parents = {edge[0] for edge in variant_graph}
        for rel in normalized:
            if rel.kind != "variant_of":
                continue
            if rel.from_media_id in variant_parents:
                raise MediaRelationError(
                    from_media_id=rel.from_media_id,
                    to_media_id=rel.to_media_id,
                    kind=rel.kind,
                    reason="single_parent",
                    detail="media already has its one variant_of parent",
                )
            variant_parents.add(rel.from_media_id)

        # 5. Acyclic variants: add the new variant edges one at a time and
        #    reject the first edge that would close a cycle (this also
        #    catches cycles that span several new edges). Edge u->v ("u is
        #    variant_of v") closes a cycle exactly when v already reaches u,
        #    because then u->v->...->u is a closed variant chain.
        for edge in (
            (rel.from_media_id, rel.to_media_id)
            for rel in normalized
            if rel.kind == "variant_of"
        ):
            if self._variant_reaches(variant_graph, edge[1], edge[0]):
                raise MediaRelationError(
                    from_media_id=edge[0],
                    to_media_id=edge[1],
                    kind="variant_of",
                    reason="cycle",
                    detail="the new edge would close a cycle in the variant graph",
                )
            variant_graph.append(edge)

        # 6. Materialize in ordinal order: one relation row and one
        #    hash-chained core.media.related event per edge, on the
        #    from-media's stream. Derived per-event idempotency keys keep
        #    the command's single key unique per stream.
        txn_id = uuid.uuid4().hex
        primary_stream_id = f"{normalized[0].from_media_id}:{CORE_MEDIA_STREAM_TYPE}"
        primary_stream_seq: int | None = None
        appends: list[Any] = []
        for index, rel in enumerate(normalized):
            try:
                metadata_json = canonical_json(dict(rel.metadata))
            except CanonicalizationError as exc:
                raise MediaValidationError(
                    f"cannot serialize relation metadata: {exc}"
                ) from exc
            uow.execute(
                "INSERT INTO media_relations "
                "(from_media_id, to_media_id, kind, ordinal, metadata_json, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    rel.from_media_id,
                    rel.to_media_id,
                    rel.kind,
                    rel.ordinal,
                    metadata_json,
                    stamp,
                ),
            )
            event_data: dict[str, Any] = {
                "from_media_id": rel.from_media_id,
                "to_media_id": rel.to_media_id,
                "kind": rel.kind,
                "ordinal": rel.ordinal,
                "metadata": dict(rel.metadata),
            }
            append = self._events.append(
                uow,
                stream_id=f"{rel.from_media_id}:{CORE_MEDIA_STREAM_TYPE}",
                project_id=project_id,
                event_kind=CORE_MEDIA_RELATED_EVENT_KIND,
                data=event_data,
                changes=[
                    "from_media_id",
                    "to_media_id",
                    "kind",
                    "ordinal",
                    "metadata",
                ],
                idempotency_key=f"{idempotency_key}#{index}",
                txn_id=txn_id,
                actor_kind=actor_kind,
                command_kind=command_kind,
                event_id=uuid.uuid4().hex,
                created_at=stamp,
            )
            appends.append(append)
            if rel.from_media_id == normalized[0].from_media_id:
                primary_stream_seq = append.stream_seq

        # 7. The complete receipt: the materialized edges, the exact
        #    contiguous project-sequence range, and the ordered event ids.
        read_model = MediaRelateReadModel(
            relations=tuple(
                MediaRelationReadModel(
                    from_media_id=rel.from_media_id,
                    to_media_id=rel.to_media_id,
                    kind=rel.kind,
                    ordinal=rel.ordinal,
                    metadata=dict(rel.metadata),
                    created_at=stamp,
                )
                for rel in normalized
            )
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=appends[0].project_seq,
            last_project_seq=appends[-1].project_seq,
            event_ids=[append.event_id for append in appends],
            result=read_model.to_dict(),
            primary_stream_id=primary_stream_id,
            resulting_stream_seq=primary_stream_seq,
            created_at=stamp,
        )
        return read_model

    # -- stable verification (m4 plan step 10) ----------------------------

    def verify(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        media_id: str,
        realm: str,
        idempotency_key: str,
        fingerprint: MediaFingerprint,
        actor_kind: str = "local",
        created_at: str | None = None,
        command_kind: str = CORE_MEDIA_VERIFY_COMMAND_KIND,
    ) -> MediaReadModel:
        """Race-safe fingerprint-verified verification of one local location.

        The caller hashes the selected local location **outside** the
        transaction (:func:`prepare_media_fingerprint`), producing a
        :class:`MediaFingerprint` of ``(path, byte_size, mtime_ns, digest)``.
        Inside the caller's unit of work this then:

        1. resolves *media_id* project-scoped and loads the single
           ``realm`` location (a cross-project id is indistinguishable from
           an unknown one — :class:`MediaNotFoundError`, no existence leak);
        2. **re-stats** the fingerprint path (missing → ``not_found``;
           changed size/mtime → :class:`MediaVerificationError`) and
           **re-hashes** it (changed bytes → :class:`MediaVerificationError`),
           and requires the prepared digest to equal the media's immutable
           ``content_hash``;
        3. only an unchanged fingerprint proceeds: the
           ``core.media.verified`` event is appended, the location's
           ``verified_at`` stamp advances, both heads move, and one complete
           receipt is written.

        A missing, mutated, or replaced location therefore causes **zero**
        mutation — no event, head, projection, or receipt change — because
        every integrity fence runs before the first write. Idempotency: an
        identical retry replays the stored result with zero new rows; a
        changed request under the same key raises :class:`ReceiptMismatchError`
        before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        media_id = _require_non_empty_string("media_id", media_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if realm not in (MANAGED_LOCAL_REALM, EXTERNAL_LOCAL_REALM):
            raise MediaValidationError(
                "verify supports only the local realms "
                f"{MANAGED_LOCAL_REALM!r} and {EXTERNAL_LOCAL_REALM!r}, "
                f"got {realm!r}"
            )
        if actor_kind not in ACTOR_KINDS:
            raise MediaValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if not isinstance(fingerprint, MediaFingerprint):
            raise MediaValidationError(
                "fingerprint must be a MediaFingerprint record, got "
                f"{type(fingerprint).__name__}"
            )

        # Project-scoped resolution (plan step 9): a media id in another
        # project is indistinguishable from an unknown one.
        media_id = self.resolve_media(uow, project_id=project_id, media_id=media_id)

        # The media row and its single realm location are the authority.
        media_row = uow.query_one(
            "SELECT content_hash FROM media WHERE id = ? AND project_id = ?",
            (media_id, project_id),
        )
        if media_row is None:
            raise MediaNotFoundError(media_id=media_id)
        content_hash = str(media_row["content_hash"])

        location_rows = uow.query(
            "SELECT id, realm, locator, verified_at FROM media_locations "
            "WHERE media_id = ? AND realm = ? ORDER BY created_at ASC, id ASC",
            (media_id, realm),
        )
        if not location_rows:
            raise MediaLocationNotFoundError(media_id=media_id, realm=realm)
        if len(location_rows) > 1:
            raise MediaConflictError(
                media_id=media_id,
                reason="multiple_locations",
                detail=(
                    f"realm={realm!r} has {len(location_rows)} locations; "
                    "verification requires an unambiguous single location"
                ),
            )
        location_row = location_rows[0]
        location_id = str(location_row["id"])
        locator = str(location_row["locator"])

        # The fingerprint must have been prepared from this exact location.
        if os.path.abspath(fingerprint.path) != os.path.abspath(locator):
            raise MediaValidationError(
                "fingerprint path does not match the location locator "
                f"for realm={realm!r}"
            )

        # Integrity fence FIRST (before the receipt gate and before any
        # write): a missing, mutated, or replaced location can never replay
        # a stale stamp nor mutate a single row.
        self._recheck_fingerprint(
            fingerprint, content_hash=content_hash, media_id=media_id
        )

        # Semantic request identity: the addressed media, realm, and the
        # immutable content hash. The prepared fingerprint is an observation,
        # never part of request identity.
        request = {
            "media_id": media_id,
            "realm": realm,
            "content_hash": content_hash,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise MediaValidationError(
                f"cannot hash media verify request: {exc}"
            ) from exc

        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return MediaReadModel.from_mapping(replayed)

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise MediaValidationError("created_at must be a non-empty string")
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stream_id = f"{media_id}:{CORE_MEDIA_STREAM_TYPE}"

        # 1. The only projection change: the location's verification stamp.
        uow.execute(
            "UPDATE media_locations SET verified_at = ? WHERE id = ?",
            (stamp, location_id),
        )

        # 2. The hash-chained core.media.verified event on the media stream;
        #    the append advances both heads atomically.
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_MEDIA_VERIFIED_EVENT_KIND,
            data={
                "media_id": media_id,
                "content_hash": content_hash,
                "realm": realm,
                "locator": locator,
                "byte_size": fingerprint.byte_size,
                "verified_at": stamp,
            },
            changes=["verified_at"],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )

        # 3. The complete receipt: the refreshed media read model.
        read_model = self._media_read_model(
            uow, media_id=media_id, project_id=project_id
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

    def materialize_prepared(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        prepared: PreparedMedia,
        idempotency_key: str,
        actor_kind: str = "local",
        media_id: str | None = None,
        realm: str = MANAGED_LOCAL_REALM,
        locator: str | None = None,
        relations: Sequence[Mapping[str, Any]] | None = None,
        created_at: str | None = None,
        command_kind: str = CORE_MEDIA_IMPORT_COMMAND_KIND,
    ) -> MaterializedMedia:
        """Materialize verified prepared bytes inside the caller's UoW (T17).

        Receipt-less in-UoW media primitive for task completion: inside the
        caller's active unit of work this publishes (or byte-verifies and
        reuses) the prepared bytes and creates the media row, the
        ``media_locations`` projection, the ``core.media`` stream, the
        hash-chained ``core.media.imported`` event, and both heads — plus,
        when *relations* is supplied, one ``media_relations`` row and one
        ``core.media.related`` event per edge in deterministic ordinal
        order with the same same-project/self-link/duplicate/single-parent/
        acyclic invariants as :meth:`relate`. **No receipt is written**:
        the caller's completion command records the one complete receipt
        covering every ordered event id, so replay of the whole completion
        stays exactly-once. Same-project and deterministic ordering follow
        the shared media internals (:meth:`import_prepared`/:meth:`relate`).
        """
        project_id = _require_non_empty_string("project_id", project_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if not isinstance(prepared, PreparedMedia):
            raise MediaValidationError(
                "prepared must be a PreparedMedia record, got "
                f"{type(prepared).__name__}"
            )
        if realm not in MEDIA_LOCATION_REALMS:
            raise MediaConflictError(
                media_id=media_id or "",
                reason="realm",
                detail=f"expected one of {MEDIA_LOCATION_REALMS}, got {realm!r}",
            )
        if actor_kind not in ACTOR_KINDS:
            raise MediaValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if media_id is None:
            media_id = generate_lowercase_ulid()
        else:
            _require_non_empty_string("media_id", media_id)
        if locator is None:
            if realm == MANAGED_LOCAL_REALM:
                locator = str(managed_media_path(self._projects_root, prepared.digest))
            else:
                locator = str(prepared.source_path)
        else:
            locator = _require_non_empty_string("locator", locator)
        normalized_relations = (
            self._normalize_relations(relations) if relations is not None else []
        )

        # Same project before any mutation.
        if uow.query_one("SELECT id FROM projects WHERE id = ?", (project_id,)) is None:
            raise MediaValidationError(
                f"media materialization requires an existing project: {project_id!r}"
            )

        # Project-scoped byte dedupe (SD2).
        existing = uow.query_one(
            "SELECT id FROM media WHERE project_id = ? AND content_hash = ?",
            (project_id, prepared.digest),
        )
        if existing is not None:
            media_id = str(existing["id"])
            duplicate = uow.query_one(
                "SELECT id FROM media_locations "
                "WHERE media_id = ? AND realm = ? AND locator = ?",
                (media_id, realm, locator),
            )
            if duplicate is not None and realm == EXTERNAL_LOCAL_REALM:
                raise MediaConflictError(
                    media_id=media_id,
                    reason="duplicate_location",
                    detail=f"realm={realm!r} locator={locator!r} already exists",
                )
        else:
            if uow.query_one("SELECT id FROM media WHERE id = ?", (media_id,)) is not None:
                raise MediaConflictError(
                    media_id=media_id,
                    reason="media_already_exists",
                    detail=f"media id {media_id!r} already exists",
                )

        # Relation invariants before the first SQL write: same-project
        # endpoints, exact duplicates, one variant parent, acyclic variants.
        if normalized_relations:
            endpoint_ids = {
                rel.from_media_id for rel in normalized_relations
            } | {rel.to_media_id for rel in normalized_relations}
            placeholders = ", ".join("?" * len(endpoint_ids))
            media_rows = uow.query(
                "SELECT id FROM media WHERE project_id = ? AND id IN ("
                + placeholders
                + ")",
                (project_id, *sorted(endpoint_ids)),
            )
            existing_ids = {str(row["id"]) for row in media_rows}
            missing = sorted(endpoint_ids - existing_ids)
            if missing:
                raise MediaNotFoundError(media_id=missing[0])
            existing_edges = uow.query(
                "SELECT from_media_id, to_media_id, kind, ordinal "
                "FROM media_relations "
                "WHERE from_media_id IN (" + placeholders + ") "
                "AND to_media_id IN (" + placeholders + ")",
                (*sorted(endpoint_ids), *sorted(endpoint_ids)),
            )
            existing_edge_keys = {
                (
                    str(row["from_media_id"]),
                    str(row["to_media_id"]),
                    str(row["kind"]),
                    int(row["ordinal"]),
                )
                for row in existing_edges
            }
            for rel in normalized_relations:
                key = (rel.from_media_id, rel.to_media_id, rel.kind, rel.ordinal)
                if key in existing_edge_keys:
                    raise MediaRelationError(
                        from_media_id=rel.from_media_id,
                        to_media_id=rel.to_media_id,
                        kind=rel.kind,
                        reason="duplicate",
                        detail="the exact edge already exists",
                    )
            variant_rows = uow.query(
                "SELECT r.from_media_id, r.to_media_id FROM media_relations r "
                "JOIN media m ON m.id = r.from_media_id "
                "WHERE m.project_id = ? AND r.kind = 'variant_of'",
                (project_id,),
            )
            variant_graph = [
                (str(row["from_media_id"]), str(row["to_media_id"]))
                for row in variant_rows
            ]
            variant_parents = {edge[0] for edge in variant_graph}
            for rel in normalized_relations:
                if rel.kind != "variant_of":
                    continue
                if rel.from_media_id in variant_parents:
                    raise MediaRelationError(
                        from_media_id=rel.from_media_id,
                        to_media_id=rel.to_media_id,
                        kind=rel.kind,
                        reason="single_parent",
                        detail="media already has its one variant_of parent",
                    )
                variant_parents.add(rel.from_media_id)
            for edge in (
                (rel.from_media_id, rel.to_media_id)
                for rel in normalized_relations
                if rel.kind == "variant_of"
            ):
                if self._variant_reaches(variant_graph, edge[1], edge[0]):
                    raise MediaRelationError(
                        from_media_id=edge[0],
                        to_media_id=edge[1],
                        kind="variant_of",
                        reason="cycle",
                        detail="the new edge would close a cycle in the variant graph",
                    )
                variant_graph.append(edge)

        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        location_id = generate_lowercase_ulid()
        stream_id = f"{media_id}:{CORE_MEDIA_STREAM_TYPE}"
        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise MediaValidationError("created_at must be a non-empty string")

        # 1. The short materialization boundary: publish verified bytes (or
        #    verified-reuse the existing digest) before any semantic write.
        published_reused: bool | None = None
        if realm == MANAGED_LOCAL_REALM:
            published = publish_prepared_media(self._projects_root, txn_id, prepared)
            published_reused = published.reused
            # Repository-visible seam (plan step 16): the verified managed
            # digest exists (or was verified-reused) before any projection
            # write; a crash here leaves SQL old plus a reusable orphan.
            media_crash_point("repo.published")

        # 2. The media row, created only when this project+digest is new.
        media_row = uow.query_one(
            "SELECT id, project_id, metadata_json FROM media WHERE id = ?",
            (media_id,),
        )
        if media_row is None:
            metadata = {"rel_path": prepared.rel_path, "probe": dict(prepared.probe)}
            try:
                metadata_json = canonical_json(metadata)
            except CanonicalizationError as exc:
                raise MediaValidationError(
                    f"cannot serialize media metadata: {exc}"
                ) from exc
            uow.execute(
                "INSERT INTO media "
                "(id, project_id, media_kind, mime_type, byte_size, "
                "content_hash, metadata_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    media_id,
                    project_id,
                    validate_media_kind(prepared.media_kind),
                    prepared.mime_type,
                    prepared.byte_size,
                    prepared.digest,
                    metadata_json,
                    stamp,
                ),
            )
        else:
            if str(media_row["project_id"]) != project_id:
                raise MediaConflictError(
                    media_id=media_id,
                    reason="realm",
                    detail="media id already exists in another project",
                )

        # 3. The media_locations projection (one per distinct location).
        location_exists = uow.query_one(
            "SELECT 1 FROM media_locations "
            "WHERE media_id = ? AND realm = ? AND locator = ?",
            (media_id, realm, locator),
        )
        if location_exists is None:
            verified_at = stamp if realm == MANAGED_LOCAL_REALM else None
            uow.execute(
                "INSERT INTO media_locations "
                "(id, media_id, realm, locator, verified_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (location_id, media_id, realm, locator, verified_at, stamp),
            )

        # 4. The core.media stream (created on first import, reused on
        #    dedupe) and the hash-chained core.media.imported event.
        stream_exists = uow.query_one(
            "SELECT 1 FROM event_streams WHERE id = ?", (stream_id,)
        )
        if stream_exists is None:
            uow.execute(
                "INSERT INTO event_streams "
                "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (stream_id, project_id, CORE_MEDIA_STREAM_TYPE, media_id, stamp),
            )
        event_data: dict[str, Any] = {
            "media_id": media_id,
            "content_hash": prepared.digest,
            "media_kind": prepared.media_kind,
            "mime_type": prepared.mime_type,
            "byte_size": prepared.byte_size,
            "realm": realm,
            "locator": locator,
        }
        if published_reused is not None:
            event_data["reused"] = published_reused
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_MEDIA_IMPORTED_EVENT_KIND,
            data=event_data,
            changes=[
                "media_id",
                "content_hash",
                "media_kind",
                "mime_type",
                "byte_size",
                "realm",
                "locator",
            ],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )

        # 5. Optional relations in deterministic ordinal order: one row and
        #    one hash-chained core.media.related event per edge.
        materialized_relations: list[MediaRelationReadModel] = []
        for index, rel in enumerate(normalized_relations):
            try:
                metadata_json = canonical_json(dict(rel.metadata))
            except CanonicalizationError as exc:
                raise MediaValidationError(
                    f"cannot serialize relation metadata: {exc}"
                ) from exc
            uow.execute(
                "INSERT INTO media_relations "
                "(from_media_id, to_media_id, kind, ordinal, metadata_json, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    rel.from_media_id,
                    rel.to_media_id,
                    rel.kind,
                    rel.ordinal,
                    metadata_json,
                    stamp,
                ),
            )
            self._events.append(
                uow,
                stream_id=f"{rel.from_media_id}:{CORE_MEDIA_STREAM_TYPE}",
                project_id=project_id,
                event_kind=CORE_MEDIA_RELATED_EVENT_KIND,
                data={
                    "from_media_id": rel.from_media_id,
                    "to_media_id": rel.to_media_id,
                    "kind": rel.kind,
                    "ordinal": rel.ordinal,
                    "metadata": dict(rel.metadata),
                },
                changes=[
                    "from_media_id",
                    "to_media_id",
                    "kind",
                    "ordinal",
                    "metadata",
                ],
                idempotency_key=f"{idempotency_key}#rel:{index}",
                txn_id=txn_id,
                actor_kind=actor_kind,
                command_kind=CORE_MEDIA_RELATE_COMMAND_KIND,
                event_id=uuid.uuid4().hex,
                created_at=stamp,
            )
            materialized_relations.append(
                MediaRelationReadModel(
                    from_media_id=rel.from_media_id,
                    to_media_id=rel.to_media_id,
                    kind=rel.kind,
                    ordinal=rel.ordinal,
                    metadata=dict(rel.metadata),
                    created_at=stamp,
                )
            )

        return MaterializedMedia(
            media_id=media_id,
            event_id=append.event_id,
            stream_id=stream_id,
            project_seq=append.project_seq,
            stream_seq=append.stream_seq,
            location_id=location_id,
            reused=published_reused,
            relations=tuple(materialized_relations),
        )

    # -- internal helpers --------------------------------------------------

    @staticmethod
    def _variant_reaches(
        edges: Sequence[tuple[str, str]], start: str, target: str
    ) -> bool:
        """Return whether *target* is reachable from *start* in a variant graph.

        ``edges`` is a sequence of directed ``(from_media_id, to_media_id)``
        ``variant_of`` edges; reachability follows the edge direction (a
        media's parent, grandparent, …). Used by :meth:`relate` to prove
        that a proposed new edge cannot close a cycle before any SQL.
        """
        adjacency: dict[str, list[str]] = {}
        for source, destination in edges:
            adjacency.setdefault(source, []).append(destination)
        stack = [start]
        seen: set[str] = set()
        while stack:
            node = stack.pop()
            if node == target:
                return True
            if node in seen:
                continue
            seen.add(node)
            stack.extend(adjacency.get(node, ()))
        return False

    @staticmethod
    def _recheck_fingerprint(
        fingerprint: MediaFingerprint,
        *,
        content_hash: str,
        media_id: str,
    ) -> None:
        """Re-stat and re-hash a prepared fingerprint inside the UoW.

        This is the stable-verification integrity fence (plan step 10): it
        closes the hash-to-commit race by comparing the location's current
        ``(size, mtime_ns, digest)`` against the fingerprint prepared outside
        the transaction. A missing location raises :class:`MediaNotFoundError`
        (typed not-found), while a changed size/mtime, a changed digest, or a
        digest that does not equal the media's immutable ``content_hash``
        raises :class:`MediaVerificationError` (typed integrity) — all before
        any event, head, projection, or receipt write.
        """
        path = Path(fingerprint.path)
        if path.is_symlink() or not path.is_file():
            raise MediaNotFoundError(media_id=media_id)
        stat = path.stat()
        if (
            int(stat.st_size) != fingerprint.byte_size
            or int(stat.st_mtime_ns) != fingerprint.mtime_ns
        ):
            raise MediaVerificationError(
                media_id=media_id,
                reason="changed",
                detail="location size/mtime changed between hash and commit",
            )
        actual_digest = sha256_file_bytes(path)
        if actual_digest != fingerprint.digest:
            raise MediaVerificationError(
                media_id=media_id,
                reason="changed",
                detail="location bytes changed between hash and commit",
            )
        if fingerprint.digest != content_hash:
            raise MediaVerificationError(
                media_id=media_id,
                reason="changed",
                detail="location bytes do not match the media content hash",
            )

    def _normalize_relations(
        self, relations: Sequence[Mapping[str, Any]]
    ) -> list[MediaRelationReadModel]:
        """Validate and order one relate command's relation edges.

        Every domain rule that can be decided from the request alone runs
        here, before hashing and before any SQL: the frozen kind
        vocabulary, self-links, ordinal/metadata shapes, and exact
        in-command duplicates. Returns the edges ordered for materialization
        (ordinal ascending, then from id, then to id, then kind).
        """
        normalized: list[MediaRelationReadModel] = []
        seen: set[tuple[str, str, str, int]] = set()
        for index, raw in enumerate(relations):
            if not isinstance(raw, Mapping):
                raise MediaValidationError(
                    f"relations[{index}] must be a mapping, got "
                    f"{type(raw).__name__}"
                )
            from_media_id = _require_non_empty_string(
                "from_media_id", raw.get("from_media_id")
            )
            to_media_id = _require_non_empty_string(
                "to_media_id", raw.get("to_media_id")
            )
            kind = raw.get("kind")
            if kind not in MEDIA_RELATION_KINDS:
                raise MediaRelationError(
                    from_media_id=from_media_id,
                    to_media_id=to_media_id,
                    kind=str(kind),
                    reason="kind",
                    detail=f"expected one of {MEDIA_RELATION_KINDS}",
                )
            if from_media_id == to_media_id:
                raise MediaRelationError(
                    from_media_id=from_media_id,
                    to_media_id=to_media_id,
                    kind=kind,
                    reason="self",
                    detail="a media cannot relate to itself",
                )
            ordinal = raw.get("ordinal", 0)
            if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
                raise MediaValidationError(
                    f"relation ordinal must be a non-negative integer, "
                    f"got {ordinal!r}"
                )
            metadata = raw.get("metadata", {})
            if not isinstance(metadata, Mapping):
                raise MediaValidationError(
                    "relation metadata must be a JSON object, got "
                    f"{type(metadata).__name__}"
                )
            key = (from_media_id, to_media_id, kind, ordinal)
            if key in seen:
                raise MediaRelationError(
                    from_media_id=from_media_id,
                    to_media_id=to_media_id,
                    kind=kind,
                    reason="duplicate",
                    detail="the exact edge is declared twice in one command",
                )
            seen.add(key)
            normalized.append(
                MediaRelationReadModel(
                    from_media_id=from_media_id,
                    to_media_id=to_media_id,
                    kind=kind,
                    ordinal=ordinal,
                    metadata=dict(metadata),
                    created_at="",
                )
            )
        normalized.sort(
            key=lambda rel: (
                rel.ordinal,
                rel.from_media_id,
                rel.to_media_id,
                rel.kind,
            )
        )
        return normalized

    def _insert(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        prepared: PreparedMedia,
        media_id: str,
        realm: str,
        locator: str,
        idempotency_key: str,
        request_digest: str,
        command_kind: str,
        actor_kind: str,
        created_at: str | None,
    ) -> MediaReadModel:
        """Persist the import writes inside the caller's UoW."""
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        location_id = generate_lowercase_ulid()
        stream_id = f"{media_id}:{CORE_MEDIA_STREAM_TYPE}"
        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise MediaValidationError("created_at must be a non-empty string")

        # 1. The short materialization boundary: publish verified bytes (or
        #    verified-reuse the existing digest) before any semantic write.
        #    external_local is reference-in-place and publishes nothing.
        published_reused: bool | None = None
        if realm == MANAGED_LOCAL_REALM:
            published = publish_prepared_media(
                self._projects_root, txn_id, prepared
            )
            published_reused = published.reused
            # Repository-visible seam (plan step 16): the verified managed
            # digest exists (or was verified-reused) before any projection
            # write; a crash here leaves SQL old plus a reusable orphan.
            media_crash_point("repo.published")

        # 2. The media row, created only when this project+digest is new.
        media_row = uow.query_one(
            "SELECT id, project_id, metadata_json FROM media WHERE id = ?",
            (media_id,),
        )
        if media_row is None:
            metadata = {
                "rel_path": prepared.rel_path,
                "probe": dict(prepared.probe),
            }
            try:
                metadata_json = canonical_json(metadata)
            except CanonicalizationError as exc:
                raise MediaValidationError(
                    f"cannot serialize media metadata: {exc}"
                ) from exc
            uow.execute(
                "INSERT INTO media "
                "(id, project_id, media_kind, mime_type, byte_size, "
                "content_hash, metadata_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    media_id,
                    project_id,
                    validate_media_kind(prepared.media_kind),
                    prepared.mime_type,
                    prepared.byte_size,
                    prepared.digest,
                    metadata_json,
                    stamp,
                ),
            )
        else:
            if str(media_row["project_id"]) != project_id:
                raise MediaConflictError(
                    media_id=media_id,
                    reason="realm",
                    detail="media id already exists in another project",
                )
            metadata = parse_json(str(media_row["metadata_json"]))

        # 3. The media_locations projection (one per distinct location; a
        #    managed dedupe shares the digest-derived managed location).
        location_exists = uow.query_one(
            "SELECT 1 FROM media_locations "
            "WHERE media_id = ? AND realm = ? AND locator = ?",
            (media_id, realm, locator),
        )
        if location_exists is None:
            verified_at = stamp if realm == MANAGED_LOCAL_REALM else None
            uow.execute(
                "INSERT INTO media_locations "
                "(id, media_id, realm, locator, verified_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (location_id, media_id, realm, locator, verified_at, stamp),
            )
        else:
            location_row = uow.query_one(
                "SELECT id, verified_at, created_at FROM media_locations "
                "WHERE media_id = ? AND realm = ? AND locator = ?",
                (media_id, realm, locator),
            )
            location_id = str(location_row["id"])
            verified_at = location_row["verified_at"]
            location_created_at = str(location_row["created_at"])

        # 4. The core.media stream (created on first import, reused on
        #    dedupe) and the hash-chained core.media.imported event.
        stream_exists = uow.query_one(
            "SELECT 1 FROM event_streams WHERE id = ?", (stream_id,)
        )
        if stream_exists is None:
            uow.execute(
                "INSERT INTO event_streams "
                "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (stream_id, project_id, CORE_MEDIA_STREAM_TYPE, media_id, stamp),
            )
        event_data: dict[str, Any] = {
            "media_id": media_id,
            "content_hash": prepared.digest,
            "media_kind": prepared.media_kind,
            "mime_type": prepared.mime_type,
            "byte_size": prepared.byte_size,
            "realm": realm,
            "locator": locator,
        }
        if published_reused is not None:
            event_data["reused"] = published_reused
        changes: list[str] = [
            "media_id",
            "content_hash",
            "media_kind",
            "mime_type",
            "byte_size",
            "realm",
            "locator",
        ]
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_MEDIA_IMPORTED_EVENT_KIND,
            data=event_data,
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )

        # 5. The complete receipt: transaction id, stream association,
        #    exact project sequence, ordered event ids, and result.
        location_model = MediaLocationReadModel(
            id=location_id,
            media_id=media_id,
            realm=realm,
            locator=locator,
            verified_at=verified_at,
            created_at=location_created_at if location_exists is not None else stamp,
        )
        read_model = MediaReadModel(
            id=media_id,
            project_id=project_id,
            media_kind=prepared.media_kind,
            mime_type=prepared.mime_type,
            byte_size=prepared.byte_size,
            content_hash=prepared.digest,
            metadata=metadata,
            created_at=stamp,
            locations=(location_model,),
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

    # -- transaction-free reads (m2 plan step 4; T6 extends) ---------------

    def _media_read_model(
        self, uow: UnitOfWork, *, media_id: str, project_id: str
    ) -> MediaReadModel:
        """Rebuild the frozen media read model inside the active UoW.

        Joins the current ``media`` row and the ordered ``media_locations``
        projection, so the model reflects every change the caller's command
        just committed in this transaction (including the locator replaced
        by :meth:`replace_location`).
        """
        row = uow.query_one(
            "SELECT * FROM media WHERE id = ? AND project_id = ?",
            (media_id, project_id),
        )
        if row is None:
            raise MediaNotFoundError(media_id=media_id)
        location_rows = uow.query(
            "SELECT id, media_id, realm, locator, verified_at, created_at "
            "FROM media_locations WHERE media_id = ? "
            "ORDER BY created_at ASC, id ASC",
            (media_id,),
        )
        return self._row_to_read_model(
            row, [dict(loc) for loc in location_rows]
        )

    @staticmethod
    def _row_to_read_model(
        row: Mapping[str, Any],
        locations: Sequence[Mapping[str, Any]],
    ) -> MediaReadModel:
        """Build the frozen read model from one ``media`` join row."""
        return MediaReadModel(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            media_kind=str(row["media_kind"]),
            mime_type=str(row["mime_type"]),
            byte_size=int(row["byte_size"]),
            content_hash=str(row["content_hash"]),
            metadata=parse_json(str(row["metadata_json"])),
            created_at=str(row["created_at"]),
            locations=tuple(
                MediaLocationReadModel.from_mapping(loc) for loc in locations
            ),
        )

    def show(self, writer: DatabaseWriter, media_id: str) -> MediaReadModel:
        """Typed show query: one media's full immutable read model.

        A transaction-free read on a separate read-only connection (no
        writer transaction is opened and no row is mutated). Returns the
        frozen :class:`MediaReadModel` including the ordered locations;
        raises :class:`MediaNotFoundError` when no ``media`` row exists for
        *media_id*.
        """
        _require_non_empty_string("media_id", media_id)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM media WHERE id = ?", (media_id,)
            ).fetchone()
            if row is None:
                raise MediaNotFoundError(media_id=media_id)
            location_rows = conn.execute(
                "SELECT id, media_id, realm, locator, verified_at, created_at "
                "FROM media_locations WHERE media_id = ? "
                "ORDER BY created_at ASC, id ASC",
                (media_id,),
            ).fetchall()
        return self._row_to_read_model(row, [dict(loc) for loc in location_rows])

    def list(self, writer: DatabaseWriter, project_id: str) -> list[MediaReadModel]:
        """Sorted read-only list query: every media row in one project.

        A transaction-free read on a separate read-only connection, ordered
        by ``created_at`` then id (deterministic, stable). Returns one
        :class:`MediaReadModel` per media row including its locations; a
        project with no media returns ``[]``.
        """
        _require_non_empty_string("project_id", project_id)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM media WHERE project_id = ? "
                "ORDER BY created_at ASC, id ASC",
                (project_id,),
            ).fetchall()
            media_ids = [str(row["id"]) for row in rows]
            locations_by_media: dict[str, list[dict[str, Any]]] = {
                media_id: [] for media_id in media_ids
            }
            if media_ids:
                placeholders = ", ".join("?" * len(media_ids))
                location_rows = conn.execute(
                    "SELECT id, media_id, realm, locator, verified_at, created_at "
                    "FROM media_locations WHERE media_id IN (" + placeholders + ") "
                    "ORDER BY created_at ASC, id ASC",
                    media_ids,
                ).fetchall()
                for loc in location_rows:
                    locations_by_media[str(loc["media_id"])].append(dict(loc))
        return [
            self._row_to_read_model(row, locations_by_media[str(row["id"])])
            for row in rows
        ]


__all__ = [
    "CORE_MEDIA_IMPORTED_EVENT_KIND",
    "CORE_MEDIA_IMPORT_COMMAND_KIND",
    "CORE_MEDIA_LOCATION_REPLACED_EVENT_KIND",
    "CORE_MEDIA_RELATED_EVENT_KIND",
    "CORE_MEDIA_RELATE_COMMAND_KIND",
    "CORE_MEDIA_REPLACE_LOCATION_COMMAND_KIND",
    "CORE_MEDIA_STREAM_TYPE",
    "CORE_MEDIA_VERIFIED_EVENT_KIND",
    "CORE_MEDIA_VERIFY_COMMAND_KIND",
    "EXTERNAL_LOCAL_REALM",
    "MANAGED_LOCAL_REALM",
    "MEDIA_RELATION_KINDS",
    "MaterializedMedia",
    "MediaAlreadyExistsError",
    "MediaConflictError",
    "MediaFingerprint",
    "MediaLocationNotFoundError",
    "MediaNotFoundError",
    "MediaRelationError",
    "MediaRepository",
    "MediaValidationError",
    "MediaVerificationError",
    "prepare_media_fingerprint",
]
