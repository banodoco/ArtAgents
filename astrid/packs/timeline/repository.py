"""Timeline repository: create, address resolution, list, and show (m1 plan step 13).

The timeline pack's first complete repository vertical lives in this module
(``astrid/packs/timeline/repository.py``). It mirrors the kernel project
vertical's shape — one writer transaction per command, typed errors, frozen
read models, transaction-free reads — while honoring the frozen v10 DDL
(SD1): the ``timelines`` table has **no** slug, ULID, or default columns.

:meth:`TimelineRepository.create` is one complete command inside the caller's
single ``BEGIN IMMEDIATE`` unit of work:

1. validates the immutable slug grammar and the loose config/registry shapes;
2. runs the receipt idempotency gate (stable-ID replay or mismatch-before-
   mutation, exactly like project create);
3. enforces **alias uniqueness under ``BEGIN IMMEDIATE``** — the slug and
   lowercase ULID live only inside ``timeline.created`` event envelopes, so
   uniqueness is a transactional query over the project's created events,
   never a convenience column;
4. inserts the ``timeline.timeline`` event stream and the whole-document
   ``timelines`` projection, appends the hash-chained ``timeline.created``
   event (canonical SD2 envelope), optionally sets the repository-owned
   default timeline id in ``projects.settings_json`` through
   :meth:`ProjectRepository.set_default_timeline` (the only writer of that
   key), and records the complete receipt — all atomically.

Reads (:meth:`resolve`, :meth:`list`, :meth:`show`) are transaction-free
queries on a separate read-only connection (the established T14/T15 path).
``resolve`` resolves a canonical UUID, lowercase 26-character Crockford ULID,
or immutable project-scoped slug **within one project** (bridge §8 order:
UUID, then ULID, then slug). ``list`` returns frozen bridge-shaped rows
``{timeline_id, timeline_ulid, slug, name, is_default}`` sorted by slug, and
``show`` returns the frozen load shape with loose ``config``,
``registry.assets``, and ``config_version`` equal to the numeric timeline
stream head. Default-timeline state is projected from
``projects.settings_json`` only — never a second authority.

:meth:`TimelineRepository.save` (plan step 14) is the whole-document CAS
command: it canonicalizes only the frozen bridge top keys, derives the
internal idempotency key from project/timeline identity, the integer
expected head, and the canonical payload, CAS-checks the expected head
*before* any mutation (a stale save raises
:class:`TimelineVersionConflictError` carrying the current head and changes
zero rows), and atomically updates ``document_json`` +
``asset_registry_json``, appends one ``timeline.saved`` event, advances
both heads, and records the receipt — returning the committed load shape
with the new ``config_version``.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, List

from astrid.core.events.service import ACTOR_KINDS, EventAppendService
from astrid.core.ids import generate_lowercase_ulid, is_lowercase_ulid
from astrid.core.integrations.reigh.timeline_bundle import (
    BUNDLE_MISSING,
    validate_timeline_bundle,
)
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
    parse_json,
    request_hash,
)
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.errors import RepositoryError
from astrid.core.repositories.projects import (
    DEFAULT_TIMELINE_SETTINGS_KEY,
    ProjectNotFoundError,
    ProjectRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.util.time import utc_now_iso

TIMELINE_STREAM_TYPE = "timeline.timeline"
"""The pack stream type every timeline aggregate owns (one per timeline)."""

TIMELINE_CREATED_EVENT_KIND = "timeline.created"
"""The m1 event kind emitted by timeline creation (carries the alias metadata)."""

TIMELINE_CREATE_COMMAND_KIND = "timeline.create"
"""The m1 command kind that timeline-create receipts are keyed on."""

TIMELINE_SAVED_EVENT_KIND = "timeline.saved"
"""The m1 event kind appended by every whole-document CAS save.

The event carries the command delta (the newly committed ``config`` and
``registry`` plus the ``expected_version`` that was CAS-checked), so the
event log alone can reconstruct every save that advanced the stream head.
"""
_BUNDLE_MISSING = BUNDLE_MISSING

TIMELINE_SAVE_COMMAND_KIND = "timeline.save"
"""The m1 command kind that timeline-save receipts are keyed on."""

TIMELINE_CONFIG_REPLACED_EVENT_KIND = "timeline.config_replaced"
"""The m2 event kind appended by the whole-config replacement command.

``timeline.config_replaced`` is the lossless runtime full-replacement
surface (projection/reset path): the event carries the newly committed
``config`` and ``registry`` plus the ``expected_version`` that was
CAS-checked, exactly like ``timeline.saved`` — the two event kinds differ
only in meaning (whole-document CAS save vs. full-config replacement), not
in payload shape.
"""

TIMELINE_REPLACE_CONFIG_COMMAND_KIND = "timeline.replace_config"
"""The m2 command kind that timeline-replace_config receipts are keyed on.

Declared by the timeline pack manifest; implemented by
:meth:`TimelineRepository.replace_config`. Receipt keys follow the save
convention — ``timeline.replace_config:{timeline_id}:{expected_version}``
when the caller supplies the key, or the derived bridge key
``{command_kind}:{project_id}:{timeline_id}:{expected_version}:{digest}``
when it does not.
"""

TIMELINE_ARCHIVE_COMMAND_KIND = "timeline.archive"
"""The m4 command kind that timeline-archive receipts are keyed on (plan
step 7). Archive is event-backed (SD1): the frozen ``timelines`` table has
no ``archived_at`` column, so the archived state is derived from the
presence of a ``timeline.archived`` event on the timeline stream."""

TIMELINE_ARCHIVED_EVENT_KIND = "timeline.archived"
"""The m4 event kind appended by the archive command (plan step 7).

The event carries the archived timestamp and advances the timeline stream
head exactly once; its presence on the stream is the single event-backed
authority for archived state (there is no column and no second authority).
Archived timelines disappear from ordinary lists and reject further saves,
while direct historical lookup (show/history/diff) keeps working."""

TIMELINE_REGISTRY_MERGED_EVENT_KIND = "timeline.registry_merged"
"""Completion-time additive registry merge event.

Worker completion may add managed-media entries without replacing the
editor-owned document. Existing registry keys are never overwritten; this
event advances the same timeline stream head and therefore participates in
the next whole-document CAS version.
"""

_TIMELINE_HISTORY_KINDS: tuple[str, ...] = (
    TIMELINE_CREATED_EVENT_KIND,
    TIMELINE_SAVED_EVENT_KIND,
    TIMELINE_ARCHIVED_EVENT_KIND,
)
"""The ordered timeline lifecycle event kinds history/diff read, in stream
order (created first, then saves, then archive). Archive never changes
document/registry, so the version content used by ``diff`` is carried by
``timeline.created`` and ``timeline.saved`` only."""

_BRIDGE_CANONICAL_TOP_KEYS: tuple[str, ...] = (
    "config",
    "registry",
    "expected_version",
)
"""The frozen bridge save-request top keys (contract §6.1).

Whole-document saves canonicalize exactly these three keys — the bridge body
has no other fields. ``config`` and ``registry`` are loose editor objects;
``expected_version`` is the integer CAS version. Timeline/project identity
enters the derived idempotency key separately, never the canonical payload.
"""

DEFAULT_TIMELINE_KEY_SUFFIX = ":set-default"
"""Suffix deriving the nested default-update idempotency key from the create key.

Setting the project default goes through
:meth:`ProjectRepository.set_default_timeline`, which runs its own receipt
gate on ``(project_id, idempotency_key)``. Because ``command_receipts`` keys
on that pair and the create receipt occupies the create's key, the nested
default update uses this derived key so both receipts commit atomically in
the same ``BEGIN IMMEDIATE`` without colliding.
"""

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
"""Immutable slug grammar (same as projects): lowercase letters/digits."""

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
"""Canonical lowercase UUID grammar (8-4-4-4-12 hex groups, bridge §8)."""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TimelineRepositoryError(RepositoryError):
    """Base error for the timeline repository family.

    Subclasses :class:`astrid.core.repositories.errors.RepositoryError`
    (and therefore :class:`astrid.core.store.writer.WriterError`), so the
    kernel store error family catches timeline contract violations too.
    """


class TimelineValidationError(TimelineRepositoryError):
    """Raised when a timeline create/address argument is invalid.

    Covers invalid slugs, non-object config/registry, invalid addresses
    (a ``:ref`` that is not a UUID, ULID, or slug), and invalid command
    arguments — the bridge ``400 invalid_timeline`` surface.
    """


class TimelineAlreadyExistsError(TimelineRepositoryError):
    """Raised when a create targets an already-existing timeline id."""

    def __init__(self, *, timeline_id: str) -> None:
        self.timeline_id: str = timeline_id
        super().__init__(f"timeline already exists: {timeline_id!r}")


class TimelineSlugConflictError(TimelineRepositoryError):
    """Raised when a create targets an already-used slug in the project.

    The slug lives only in ``timeline.created`` event envelopes (SD1), so
    uniqueness is enforced transactionally inside the command's ``BEGIN
    IMMEDIATE``; a conflicting slug changes zero rows.
    """

    def __init__(self, *, slug: str, project_id: str) -> None:
        self.slug: str = slug
        self.project_id: str = project_id
        super().__init__(
            f"timeline slug already in use in project {project_id!r}: {slug!r}"
        )


class TimelineUlidConflictError(TimelineRepositoryError):
    """Raised when a create targets an already-used ULID alias in the project.

    Like the slug, the lowercase ULID alias lives only in ``timeline.created``
    envelopes and its uniqueness is enforced inside the same ``BEGIN
    IMMEDIATE`` transaction.
    """

    def __init__(self, *, timeline_ulid: str, project_id: str) -> None:
        self.timeline_ulid: str = timeline_ulid
        self.project_id: str = project_id
        super().__init__(
            "timeline ULID alias already in use in project "
            f"{project_id!r}: {timeline_ulid!r}"
        )


class TimelineVersionConflictError(TimelineRepositoryError):
    """Raised when a whole-document save targets a stale expected head.

    The CAS check runs before any sequence allocation or projection change,
    so a stale save leaves document, registry, events, both heads, and
    receipts unchanged. Carries the current head as ``current_version`` —
    the bridge ``409 timeline_version_conflict`` body adds exactly this as
    ``config_version`` (contract §6.2).
    """

    def __init__(
        self,
        *,
        project_id: str,
        timeline_id: str,
        expected_version: int,
        current_version: int,
    ) -> None:
        self.project_id: str = project_id
        self.timeline_id: str = timeline_id
        self.expected_version: int = expected_version
        self.current_version: int = current_version
        super().__init__(
            f"timeline save version conflict: timeline {timeline_id!r} in "
            f"project {project_id!r} has head {current_version}, expected "
            f"{expected_version}"
        )


class TimelineNotFoundError(TimelineRepositoryError):
    """Raised when a read targets an address with no timeline in the project.

    Resolution is project-scoped: the same slug/ULID in another project is
    a different timeline, and a missing project raises
    :class:`ProjectNotFoundError` first (never an empty authority-dependent
    view).
    """

    def __init__(self, *, ref: str, project_id: str) -> None:
        self.ref: str = ref
        self.project_id: str = project_id
        super().__init__(
            f"unknown timeline {ref!r} in project {project_id!r}"
        )


class TimelineArchivedError(TimelineRepositoryError):
    """Raised when a command mutates an already-archived timeline.

    Archive is final for mutations (SD1): once a ``timeline.archived``
    event is committed on the stream, a whole-document save or a second
    archive raises this before any allocation or projection change, so the
    archived timeline, its events, both heads, and every receipt stay
    unchanged. Direct historical lookup (show/history/diff) still works.
    """

    def __init__(self, *, timeline_id: str, project_id: str) -> None:
        self.timeline_id: str = timeline_id
        self.project_id: str = project_id
        super().__init__(
            f"timeline is archived and cannot be mutated: {timeline_id!r} "
            f"in project {project_id!r}"
        )


# ---------------------------------------------------------------------------
# Frozen read models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TimelineReadModel:
    """Immutable timeline read model (frozen bridge load shape, §5.2).

    ``config`` is the loose editor document, ``registry`` is the full
    ``{"assets": {...}}`` wire shape, and ``config_version`` is the numeric
    timeline stream head (``event_streams.head_seq``). Read models are never
    mutated in place; repository commands return new instances.
    """

    timeline_id: str
    timeline_ulid: str
    slug: str
    name: str
    is_default: bool
    config: Mapping[str, Any]
    registry: Mapping[str, Any]
    config_version: int
    bundle: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        result = {
            "timeline_id": self.timeline_id,
            "timeline_ulid": self.timeline_ulid,
            "slug": self.slug,
            "name": self.name,
            "is_default": self.is_default,
            "config": dict(self.config),
            "registry": dict(self.registry),
            "config_version": self.config_version,
        }
        if self.bundle is not None:
            result["bundle"] = dict(self.bundle)
        return result

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TimelineReadModel:
        """Rebuild the frozen read model from a stored result mapping."""
        return cls(
            timeline_id=str(value["timeline_id"]),
            timeline_ulid=str(value["timeline_ulid"]),
            slug=str(value["slug"]),
            name=str(value["name"]),
            is_default=bool(value.get("is_default", False)),
            config=dict(value.get("config") or {}),
            registry=dict(value.get("registry") or {}),
            config_version=int(value["config_version"]),
            bundle=(dict(value["bundle"]) if isinstance(value.get("bundle"), Mapping) else None),
        )


@dataclass(frozen=True, slots=True)
class TimelineListRow:
    """One sorted timeline list row (frozen bridge ``GET /timelines`` shape).

    Exactly the five fields the frozen list contract exposes
    (``timeline_id``, ``timeline_ulid``, ``slug``, ``name``, ``is_default``),
    ordered by ``slug`` ascending. Never mutated; produced only by the
    transaction-free :meth:`TimelineRepository.list` read.
    """

    timeline_id: str
    timeline_ulid: str
    slug: str
    name: str
    is_default: bool

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict serialized by the bridge list route."""
        return {
            "timeline_id": self.timeline_id,
            "timeline_ulid": self.timeline_ulid,
            "slug": self.slug,
            "name": self.name,
            "is_default": self.is_default,
        }


@dataclass(frozen=True, slots=True)
class TimelineArchiveReadModel:
    """The immutable result of one :meth:`TimelineRepository.archive` command.

    ``config_version`` is the timeline stream head after the archive event
    was appended (exactly one greater than the head before archive).
    ``to_dict`` is the JSON-safe persisted receipt shape and
    ``from_mapping`` rebuilds it for exact replay, so an identical retry
    under the same idempotency key returns exactly the stored result.
    """

    timeline_id: str
    project_id: str
    archived_at: str
    config_version: int

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the archive receipt result."""
        return {
            "timeline_id": self.timeline_id,
            "project_id": self.project_id,
            "archived_at": self.archived_at,
            "config_version": self.config_version,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TimelineArchiveReadModel:
        """Rebuild the frozen archive read model from a stored mapping."""
        return cls(
            timeline_id=str(value["timeline_id"]),
            project_id=str(value["project_id"]),
            archived_at=str(value["archived_at"]),
            config_version=int(value["config_version"]),
        )


@dataclass(frozen=True, slots=True)
class TimelineHistoryEntry:
    """One ordered timeline lifecycle event (history read, plan step 7).

    ``version`` is the event's stream ``seq`` (1 for ``timeline.created``,
    then one per save/archive). ``kind`` is one of
    :data:`_TIMELINE_HISTORY_KINDS`. ``config`` and ``registry`` carry the
    document/registry content for created/saved entries and ``None`` for
    archive entries (archive never changes content); ``archived_at`` is set
    only on the archive entry.
    """

    version: int
    kind: str
    created_at: str
    config: Mapping[str, Any] | None
    registry: Mapping[str, Any] | None
    archived_at: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict exposed by the history read."""
        return {
            "version": self.version,
            "kind": self.kind,
            "created_at": self.created_at,
            "config": dict(self.config) if self.config is not None else None,
            "registry": dict(self.registry) if self.registry is not None else None,
            "archived_at": self.archived_at,
        }


@dataclass(frozen=True, slots=True)
class TimelineDiffEntry:
    """One deterministic adjacent-version diff (diff read, plan step 7).

    Compares two adjacent content versions (``from_version`` to
    ``to_version``) over the document and registry keys. ``document`` and
    ``registry`` each carry ``added``/``removed``/``changed`` key lists
    (deterministically sorted). Registry keys are the asset keys under
    ``registry.assets`` (the editor-visible registry vocabulary).
    """

    from_version: int
    to_version: int
    from_kind: str
    to_kind: str
    document: Mapping[str, list[str]]
    registry: Mapping[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict exposed by the diff read."""
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "from_kind": self.from_kind,
            "to_kind": self.to_kind,
            "document": {
                "added": list(self.document["added"]),
                "removed": list(self.document["removed"]),
                "changed": list(self.document["changed"]),
            },
            "registry": {
                "added": list(self.registry["added"]),
                "removed": list(self.registry["removed"]),
                "changed": list(self.registry["changed"]),
            },
        }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise TimelineValidationError(f"{name} must be a non-empty string")
    return value


def _query_one(reader: Any, sql: str, parameters: Sequence[Any] = ()) -> Any:
    """Run one read on a UoW/WriterSession reader or a raw connection.

    The unit of work and the writer session expose ``query_one(sql, params)``;
    a ``sqlite3.Connection`` exposes ``execute(...).fetchone()``. Both shapes
    are accepted so the same address-resolution helper works transaction-free
    on a read-only connection and (for later whole-document saves) inside a
    ``BEGIN IMMEDIATE`` unit of work.
    """
    query_one = getattr(reader, "query_one", None)
    if query_one is not None:
        return query_one(sql, parameters)
    cursor = reader.execute(sql, parameters)
    return cursor.fetchone()


def _query_all(reader: Any, sql: str, parameters: Sequence[Any] = ()) -> list[Any]:
    """Run one multi-row read on a UoW/WriterSession reader or a connection.

    Mirrors :func:`_query_one`: a unit of work / writer session exposes
    ``query(sql, params)`` returning a list of rows, while a raw
    ``sqlite3.Connection`` exposes ``execute(...).fetchall()``. Used by the
    history/diff reads and the archive state probe.
    """
    query = getattr(reader, "query", None)
    if query is not None:
        return list(query(sql, parameters))
    cursor = reader.execute(sql, parameters)
    return list(cursor.fetchall())


def _key_diff(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, list[str]]:
    """Deterministic top-level key diff between two JSON objects.

    Returns ``{"added": [...], "removed": [...], "changed": [...]}`` where
    each list is sorted lexicographically: ``added`` keys exist only in
    *after*, ``removed`` only in *before*, and ``changed`` exist in both but
    compare unequal.
    """
    before_keys = set(before)
    after_keys = set(after)
    added = sorted(after_keys - before_keys)
    removed = sorted(before_keys - after_keys)
    changed = sorted(
        key for key in (before_keys & after_keys) if before[key] != after[key]
    )
    return {"added": added, "removed": removed, "changed": changed}


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class TimelineRepository:
    """Stateless timeline command/read surface over the kernel unit of work.

    Composes the kernel event append and receipt services plus the project
    repository (for the repository-owned default-timeline key). A single
    instance is safe to share across command callers.
    """

    def __init__(
        self,
        events: EventAppendService,
        receipts: ReceiptService,
        projects: ProjectRepository,
    ) -> None:
        self._events = events
        self._receipts = receipts
        self._projects = projects

    # -- create ------------------------------------------------------------

    def create(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        slug: str,
        name: str,
        config: Mapping[str, Any],
        registry: Mapping[str, Any] | None = None,
        idempotency_key: str,
        actor_kind: str = "local",
        timeline_id: str | None = None,
        timeline_ulid: str | None = None,
        set_default: bool = False,
        command_kind: str = TIMELINE_CREATE_COMMAND_KIND,
        created_at: str | None = None,
    ) -> TimelineReadModel:
        """Create a timeline atomically and idempotently.

        Inside the caller's active unit of work this persists, in one
        ``BEGIN IMMEDIATE`` transaction: the ``timeline.timeline`` event
        stream, the whole-document ``timelines`` projection, the hash-chained
        ``timeline.created`` event (canonical SD2 envelope carrying the slug
        and lowercase ULID alias metadata), both heads, the optional
        repository-owned default-timeline update in ``settings_json``, and one
        complete receipt.

        Alias uniqueness (slug and ULID, project-scoped) is enforced by
        transactional queries over the project's ``timeline.created`` events
        inside this same transaction — the frozen DDL has no alias columns
        (SD1). Idempotency mirrors project create: the receipt gate runs
        first, an identical retry (same stable ``timeline_id``) returns
        exactly the stored result with zero new rows, and a changed request
        under the same key raises :class:`ReceiptMismatchError` before any
        mutation.

        ``config`` is the loose editor document object. ``registry`` is the
        full bridge registry object (``{"assets": {...}}``); only its
        ``assets`` object is persisted in ``asset_registry_json``. When
        ``set_default`` is true the created timeline becomes the project's
        repository-owned default (``settings_json``).
        """
        project_id = _require_non_empty_string("project_id", project_id)
        slug = _require_non_empty_string("slug", slug)
        name = _require_non_empty_string("name", name)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if _SLUG_RE.fullmatch(slug) is None:
            raise TimelineValidationError(
                "slug must be lowercase letters/digits joined by single "
                f"hyphens, got {slug!r}"
            )
        if not isinstance(config, Mapping):
            raise TimelineValidationError("config must be a JSON object")
        if registry is not None and not isinstance(registry, Mapping):
            raise TimelineValidationError("registry must be a JSON object")
        if not isinstance(set_default, bool):
            raise TimelineValidationError("set_default must be a boolean")
        if actor_kind not in ACTOR_KINDS:
            raise TimelineValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if timeline_id is None:
            timeline_id = str(uuid.uuid4())
        else:
            _require_non_empty_string("timeline_id", timeline_id)
        if timeline_ulid is None:
            timeline_ulid = generate_lowercase_ulid()
        else:
            _require_non_empty_string("timeline_ulid", timeline_ulid)

        assets = registry.get("assets", {}) if registry is not None else {}
        if not isinstance(assets, Mapping):
            raise TimelineValidationError("registry.assets must be a JSON object")
        registry_shape = {"assets": dict(assets)}
        try:
            config_json = canonical_json(dict(config))
            assets_json = canonical_json(dict(assets))
        except CanonicalizationError as exc:
            raise TimelineValidationError(
                f"cannot canonicalize timeline payload: {exc}"
            ) from exc

        # Semantic request identity: stable ids, slug, name, config,
        # registry, and the default flag all participate; generated
        # timestamps/transaction ids are excluded.
        request = {
            "project_id": project_id,
            "timeline_id": timeline_id,
            "timeline_ulid": timeline_ulid,
            "slug": slug,
            "name": name,
            "config": dict(config),
            "registry": registry_shape,
            "set_default": bool(set_default),
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise TimelineValidationError(
                f"cannot hash timeline create request: {exc}"
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
            return TimelineReadModel.from_mapping(replayed)

        # Typed not-found before any mutation.
        project = uow.query_one(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        )
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)

        # Alias uniqueness under BEGIN IMMEDIATE: the slug and ULID live only
        # in timeline.created envelopes, so uniqueness is a transactional
        # query over the project's created events (SD1 — no convenience
        # columns).
        existing = uow.query_one(
            "SELECT id FROM timelines WHERE id = ?", (timeline_id,)
        )
        if existing is not None:
            raise TimelineAlreadyExistsError(timeline_id=timeline_id)
        dup_slug = uow.query_one(
            "SELECT 1 FROM events e JOIN event_streams s ON s.id = e.stream_id "
            "WHERE s.project_id = ? AND e.kind = ? "
            "AND json_extract(e.payload_json, '$.data.slug') = ? LIMIT 1",
            (project_id, TIMELINE_CREATED_EVENT_KIND, slug),
        )
        if dup_slug is not None:
            raise TimelineSlugConflictError(slug=slug, project_id=project_id)
        dup_ulid = uow.query_one(
            "SELECT 1 FROM events e JOIN event_streams s ON s.id = e.stream_id "
            "WHERE s.project_id = ? AND e.kind = ? "
            "AND json_extract(e.payload_json, '$.data.timeline_ulid') = ? "
            "LIMIT 1",
            (project_id, TIMELINE_CREATED_EVENT_KIND, timeline_ulid),
        )
        if dup_ulid is not None:
            raise TimelineUlidConflictError(
                timeline_ulid=timeline_ulid, project_id=project_id
            )

        # Generated values for this attempt (excluded from request identity).
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stream_id = f"{timeline_id}:{TIMELINE_STREAM_TYPE}"
        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TimelineValidationError("created_at must be a non-empty string")

        # 1. The timeline.timeline stream (head_seq starts at 0; the append
        #    below advances it to 1 in the same transaction). Inserted before
        #    the timelines projection because timelines.event_stream_id is an
        #    immediate foreign key into event_streams.
        uow.execute(
            "INSERT INTO event_streams "
            "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (stream_id, project_id, TIMELINE_STREAM_TYPE, timeline_id, stamp),
        )
        # 2. The whole-document timelines projection.
        uow.execute(
            "INSERT INTO timelines "
            "(id, project_id, event_stream_id, name, document_json, "
            "asset_registry_json, project_data_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'null', ?, ?)",
            (
                timeline_id,
                project_id,
                stream_id,
                name,
                config_json,
                assets_json,
                stamp,
                stamp,
            ),
        )
        # 3. The hash-chained timeline.created event; this advances
        #    projects.event_head_seq and event_streams.head_seq together.
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=TIMELINE_CREATED_EVENT_KIND,
            data={
                "timeline_id": timeline_id,
                "timeline_ulid": timeline_ulid,
                "slug": slug,
                "name": name,
                "config": dict(config),
                "registry": registry_shape,
            },
            changes=[
                "timeline_id",
                "timeline_ulid",
                "slug",
                "name",
                "config",
                "registry",
            ],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 4. Optionally make this timeline the repository-owned default via
        #    the only writer of that settings_json key. A derived idempotency
        #    key keeps the nested default receipt from colliding with the
        #    create receipt in the same transaction.
        if set_default:
            self._projects.set_default_timeline(
                uow,
                project_id,
                timeline_id,
                idempotency_key=idempotency_key + DEFAULT_TIMELINE_KEY_SUFFIX,
                actor_kind="system",
                created_at=stamp,
            )
        # 5. The complete receipt: transaction id, stream association, exact
        #    project sequence, ordered event ids, and result.
        read_model = TimelineReadModel(
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            slug=slug,
            name=name,
            is_default=bool(set_default),
            config=dict(config),
            registry=registry_shape,
            config_version=append.stream_seq,
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

    # -- whole-document CAS save (m1 plan step 14) -------------------------

    def save(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        ref: str,
        config: Mapping[str, Any],
        registry: Mapping[str, Any],
        expected_version: int,
        bundle: Mapping[str, Any] | None | object = _BUNDLE_MISSING,
        actor_kind: str = "local",
        command_kind: str = TIMELINE_SAVE_COMMAND_KIND,
        idempotency_key: str | None = None,
        created_at: str | None = None,
    ) -> TimelineReadModel:
        """Whole-document CAS save: one atomic, idempotent commit (§6).

        Inside the caller's single ``BEGIN IMMEDIATE`` unit of work this
        resolves *ref* (UUID, ULID, or slug) within *project_id*, validates
        the loose ``config``/``registry`` object shapes and the integer
        ``expected_version`` (booleans are rejected — a boolean is not a
        version, bridge §6.1), canonicalizes **only** the frozen bridge top
        keys (:data:`_BRIDGE_CANONICAL_TOP_KEYS`), and resolves the effective
        idempotency key:

        - when *idempotency_key* is supplied, it is the caller's key, used
          verbatim (a non-empty string, validated before any mutation);
        - when absent, the repository derives the frozen bridge key from
          project/timeline identity, the integer expected head, and the
          canonical payload — the bridge route has no ``idempotency_key``
          field, so the repository derives one (receipt secrecy, §7).

        Both paths then share the exact same atomic command: the receipt
        gate runs first (an identical retry replays exactly the stored
        result with zero new rows; a changed request under the same key —
        caller or derived — raises :class:`ReceiptMismatchError` before any
        mutation), the expected head is CAS-checked **before** any
        allocation (a stale save raises :class:`TimelineVersionConflictError`
        carrying the current head and changes zero rows), ``document_json``
        and ``asset_registry_json`` are updated, one hash-chained
        ``timeline.saved`` event carrying the command delta is appended
        (advancing stream and project heads), and the complete receipt is
        written. Returns the frozen load shape (§5.2) with the new
        ``config_version`` — the stream head after the save, exactly one
        greater than ``expected_version``.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        ref = _require_non_empty_string("ref", ref)
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if idempotency_key is not None:
            idempotency_key = _require_non_empty_string(
                "idempotency_key", idempotency_key
            )
        if actor_kind not in ACTOR_KINDS:
            raise TimelineValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if not isinstance(config, Mapping):
            raise TimelineValidationError("config must be a JSON object")
        if not isinstance(registry, Mapping):
            raise TimelineValidationError("registry must be a JSON object")
        if bundle is not _BUNDLE_MISSING and bundle is not None:
            try:
                bundle = validate_timeline_bundle(bundle)
            except ValueError as exc:
                raise TimelineValidationError(str(exc)) from exc
        if isinstance(expected_version, bool) or not isinstance(
            expected_version, int
        ):
            raise TimelineValidationError(
                "expected_version must be an integer (a boolean is not a "
                "version), got "
                f"{type(expected_version).__name__}"
            )

        assets = registry.get("assets", {})
        if not isinstance(assets, Mapping):
            raise TimelineValidationError("registry.assets must be a JSON object")
        registry_shape = {"assets": dict(assets)}
        # Canonicalize only the frozen bridge top keys; timeline/project
        # identity stays out of the payload and enters the derived key.
        try:
            config_json = canonical_json(dict(config))
            assets_json = canonical_json(dict(assets))
        except CanonicalizationError as exc:
            raise TimelineValidationError(
                f"cannot canonicalize timeline save payload: {exc}"
            ) from exc
        payload = {
            "config": dict(config),
            "registry": registry_shape,
            "expected_version": expected_version,
            "bundle": "__omitted__" if bundle is _BUNDLE_MISSING else bundle,
        }
        try:
            bridge_request_digest = request_hash(command_kind, payload)
        except CanonicalizationError as exc:
            raise TimelineValidationError(
                f"cannot hash timeline save request: {exc}"
            ) from exc

        # Resolve the address to the canonical timeline id inside the same
        # transaction (project-scoped: UUID, then ULID, then slug).
        timeline_id = self._resolve_id(uow, project_id, ref)

        # Effective idempotency key: the caller's key when supplied,
        # otherwise the frozen bridge-derived key from project/timeline
        # identity + integer expected head + canonical payload (bridge §6.1
        # derivation rule). Both paths share the receipt gate below.
        derived_key = (
            f"{command_kind}:{project_id}:{timeline_id}:"
            f"{expected_version}:{bridge_request_digest}"
        )
        if idempotency_key is None:
            # Preserve the frozen bridge-derived key and its persisted
            # request hash exactly: bridge identity already lives in the
            # derived key, while its canonical payload remains the receipt
            # hash used by earlier bridge saves.
            effective_key = derived_key
            request_digest = bridge_request_digest
        else:
            # A caller key is scoped only by project in command_receipts, so
            # the resolved timeline target must participate in semantic
            # request identity. Otherwise the same key and payload aimed at
            # another timeline could replay the first timeline's result.
            caller_request = {
                "project_id": project_id,
                "timeline_id": timeline_id,
                **payload,
            }
            try:
                request_digest = request_hash(command_kind, caller_request)
            except CanonicalizationError as exc:  # pragma: no cover - payload hashed above
                raise TimelineValidationError(
                    f"cannot hash timeline save request: {exc}"
                ) from exc
            effective_key = idempotency_key

        # Idempotency gate first: replay or mismatch before any mutation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=effective_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return TimelineReadModel.from_mapping(replayed)

        row = uow.query_one(
            "SELECT t.id, t.project_id, t.event_stream_id, t.name, "
            "t.project_data_json "
            "FROM timelines t WHERE t.id = ? AND t.project_id = ?",
            (timeline_id, project_id),
        )
        if row is None:
            raise TimelineNotFoundError(ref=ref, project_id=project_id)
        stream = uow._stream_row(str(row["event_stream_id"]))
        if stream is None:
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} is missing its event stream"
            )
        current_head = int(stream["head_seq"])
        current_bundle = self._parse_project_data(
            str(row["project_data_json"]), timeline_id
        )
        committed_bundle = current_bundle if bundle is _BUNDLE_MISSING else bundle

        # Event-backed archive fence (SD1): an archived timeline rejects a
        # later save before any allocation or projection change. The archived
        # state is derived from the stream's ordered events, never a column.
        if (
            uow.query_one(
                "SELECT 1 FROM events WHERE stream_id = ? AND kind = ? LIMIT 1",
                (row["event_stream_id"], TIMELINE_ARCHIVED_EVENT_KIND),
            )
            is not None
        ):
            raise TimelineArchivedError(
                timeline_id=timeline_id, project_id=project_id
            )

        # Expected-head CAS before any allocation or projection change; a
        # stale save changes zero rows and carries the current head.
        if current_head != expected_version:
            raise TimelineVersionConflictError(
                project_id=project_id,
                timeline_id=timeline_id,
                expected_version=expected_version,
                current_version=current_head,
            )

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TimelineValidationError("created_at must be a non-empty string")

        # 1. Whole-document projection update: document plus registry.
        changed = uow.update_projection(
            "timelines",
            {
                "document_json": config_json,
                "asset_registry_json": assets_json,
                "project_data_json": canonical_json(committed_bundle),
                "updated_at": stamp,
            },
            {"id": timeline_id, "project_id": project_id},
        )
        if changed != 1:
            raise TimelineNotFoundError(ref=ref, project_id=project_id)

        # 2. The timeline.saved event: the command delta, hash-chained, with
        #    the same effective key and a defense-in-depth expected-head CAS.
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        event_data = {
            "timeline_id": timeline_id,
            "config": dict(config),
            "registry": registry_shape,
            "expected_version": expected_version,
        }
        if bundle is not _BUNDLE_MISSING:
            event_data["bundle"] = committed_bundle
        append = self._events.append(
            uow,
            stream_id=str(row["event_stream_id"]),
            project_id=project_id,
            event_kind=TIMELINE_SAVED_EVENT_KIND,
            data=event_data,
            changes=["config", "registry"]
            + ([] if bundle is _BUNDLE_MISSING else ["bundle"]),
            idempotency_key=effective_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            expected_head_seq=expected_version,
            created_at=stamp,
        )

        # 3. Aliases and default projection for the frozen read model — the
        #    timeline.created envelope and settings_json are the only
        #    authorities (SD1), never convenience columns.
        alias = uow.query_one(
            "SELECT json_extract(payload_json, '$.data.timeline_ulid') "
            "AS timeline_ulid, json_extract(payload_json, '$.data.slug') "
            "AS slug FROM events WHERE stream_id = ? AND kind = ? "
            "ORDER BY seq ASC LIMIT 1",
            (row["event_stream_id"], TIMELINE_CREATED_EVENT_KIND),
        )
        if alias is None:
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} is missing its timeline.created "
                "alias metadata"
            )
        timeline_ulid = alias["timeline_ulid"]
        slug = alias["slug"]
        if not isinstance(timeline_ulid, str) or not isinstance(slug, str):
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} has malformed timeline.created "
                "alias metadata"
            )
        project_row = uow.query_one(
            "SELECT settings_json FROM projects WHERE id = ?", (project_id,)
        )
        if project_row is None:
            raise ProjectNotFoundError(project_id=project_id)
        default_id = self._default_timeline_id(
            str(project_row["settings_json"]), project_id
        )

        # 4. The complete receipt and the committed frozen load shape.
        read_model = TimelineReadModel(
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            slug=slug,
            name=str(row["name"]),
            is_default=default_id == timeline_id,
            config=dict(config),
            registry=registry_shape,
            config_version=append.stream_seq,
            bundle=committed_bundle,
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=effective_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=read_model.to_dict(),
            primary_stream_id=str(row["event_stream_id"]),
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return read_model

    # -- internal asset-registry merge (completion UoW; no receipt) ---------

    def merge_registry(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        timeline_id: str,
        entries: Mapping[str, Any],
        actor_kind: str = "system",
        created_at: str | None = None,
    ) -> int:
        """Add missing registry entries inside a task-completion UoW.

        The current stream head is read and fenced inside the caller's one
        transaction. Existing keys remain editor authority, document JSON is
        untouched, archived timelines reject the merge, and a fully
        redundant merge is a no-op. The surrounding completion receipt is
        the atomicity record, so this internal helper creates no receipt.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        timeline_id = _require_non_empty_string("timeline_id", timeline_id)
        if not isinstance(entries, Mapping):
            raise TimelineValidationError("entries must be a JSON object")
        for key in entries:
            _require_non_empty_string("entry key", key)

        row = uow.query_one(
            "SELECT t.id, t.project_id, t.event_stream_id "
            "FROM timelines t WHERE t.id = ? AND t.project_id = ?",
            (timeline_id, project_id),
        )
        if row is None:
            raise TimelineNotFoundError(ref=timeline_id, project_id=project_id)
        stream = uow._stream_row(str(row["event_stream_id"]))
        if stream is None:
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} is missing its event stream"
            )
        base_head = int(stream["head_seq"])

        if (
            uow.query_one(
                "SELECT 1 FROM events WHERE stream_id = ? AND kind = ? LIMIT 1",
                (row["event_stream_id"], TIMELINE_ARCHIVED_EVENT_KIND),
            )
            is not None
        ):
            raise TimelineArchivedError(
                timeline_id=timeline_id, project_id=project_id
            )

        registry_row = uow.query_one(
            "SELECT asset_registry_json FROM timelines WHERE id = ?",
            (timeline_id,),
        )
        if registry_row is None:
            raise TimelineNotFoundError(ref=timeline_id, project_id=project_id)
        existing = self._parse_document(
            str(registry_row["asset_registry_json"]), timeline_id
        )
        added_keys = sorted(key for key in entries if key not in existing)
        if not added_keys:
            return base_head

        merged_assets = {
            **existing,
            **{key: entries[key] for key in added_keys},
        }
        try:
            assets_json = canonical_json(merged_assets)
        except CanonicalizationError as exc:
            raise TimelineValidationError(
                f"cannot canonicalize merged asset registry: {exc}"
            ) from exc

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TimelineValidationError("created_at must be a non-empty string")

        changed = uow.update_projection(
            "timelines",
            {"asset_registry_json": assets_json, "updated_at": stamp},
            {"id": timeline_id, "project_id": project_id},
        )
        if changed != 1:
            raise TimelineNotFoundError(ref=timeline_id, project_id=project_id)

        append = self._events.append(
            uow,
            stream_id=str(row["event_stream_id"]),
            project_id=project_id,
            event_kind=TIMELINE_REGISTRY_MERGED_EVENT_KIND,
            data={
                "timeline_id": timeline_id,
                "assets": merged_assets,
                "added_keys": added_keys,
                "base_head": base_head,
            },
            changes=["registry"],
            idempotency_key=(
                f"{TIMELINE_REGISTRY_MERGED_EVENT_KIND}:{project_id}:"
                f"{timeline_id}:{base_head}"
            ),
            txn_id=uuid.uuid4().hex,
            event_id=uuid.uuid4().hex,
            actor_kind=actor_kind,
            expected_head_seq=base_head,
            created_at=stamp,
        )
        return append.stream_seq

    # -- whole-config replacement (m2; the lossless full-replacement path) --

    def replace_config(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        ref: str,
        config: Mapping[str, Any],
        registry: Mapping[str, Any],
        expected_version: int,
        bundle: Mapping[str, Any] | None | object = _BUNDLE_MISSING,
        actor_kind: str = "local",
        command_kind: str = TIMELINE_REPLACE_CONFIG_COMMAND_KIND,
        idempotency_key: str | None = None,
        created_at: str | None = None,
    ) -> TimelineReadModel:
        """Whole-config CAS replacement: one atomic, idempotent commit.

        The runtime full-replacement surface behind the declared
        ``timeline.replace_config`` command. Inside the caller's single
        ``BEGIN IMMEDIATE`` unit of work this is structurally the
        whole-document CAS save (:meth:`save` — same validation, same
        expected-head CAS, same receipt shape) but appends the
        **``timeline.config_replaced``** event kind instead of
        ``timeline.saved``. The event kind is deliberately NOT changed to
        ``timeline.saved``: ``timeline.config_replaced`` is the lossless
        full-config replacement surface consumed by the projection/reset
        path, and routing through ``save()`` would emit ``timeline.saved``
        and break that path.

        - *config*/*registry* are loose JSON objects and *expected_version*
          the integer CAS head (booleans rejected, bridge §6.1), with only
          the frozen bridge top keys
          (:data:`_BRIDGE_CANONICAL_TOP_KEYS`) canonicalized;
        - the expected head is CAS-checked **before** any allocation (a
          stale write raises :class:`TimelineVersionConflictError` and
          changes zero rows);
        - ``document_json``/``asset_registry_json`` are updated, one
          hash-chained ``timeline.config_replaced`` event carrying the
          command delta is appended (advancing stream and project heads),
          and the complete receipt is written;
        - the effective idempotency key mirrors :meth:`save`: the caller's
          key verbatim when supplied (canonical form
          ``timeline.replace_config:{timeline_id}:{expected_version}``),
          otherwise the derived bridge key from project/timeline identity +
          integer expected head + canonical payload.

        Returns the frozen load shape (§5.2) with the new ``config_version``
        — the stream head after the replacement, exactly one greater than
        *expected_version*. An identical retry under the same key replays
        the stored result with zero new rows; a changed request under the
        same key raises :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        ref = _require_non_empty_string("ref", ref)
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if idempotency_key is not None:
            idempotency_key = _require_non_empty_string(
                "idempotency_key", idempotency_key
            )
        if actor_kind not in ACTOR_KINDS:
            raise TimelineValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if not isinstance(config, Mapping):
            raise TimelineValidationError("config must be a JSON object")
        if not isinstance(registry, Mapping):
            raise TimelineValidationError("registry must be a JSON object")
        if bundle is not _BUNDLE_MISSING and bundle is not None:
            try:
                bundle = validate_timeline_bundle(bundle)
            except ValueError as exc:
                raise TimelineValidationError(str(exc)) from exc
        if isinstance(expected_version, bool) or not isinstance(
            expected_version, int
        ):
            raise TimelineValidationError(
                "expected_version must be an integer (a boolean is not a "
                "version), got "
                f"{type(expected_version).__name__}"
            )

        assets = registry.get("assets", {})
        if not isinstance(assets, Mapping):
            raise TimelineValidationError("registry.assets must be a JSON object")
        registry_shape = {"assets": dict(assets)}
        # Canonicalize only the frozen bridge top keys; timeline/project
        # identity stays out of the payload and enters the derived key.
        try:
            config_json = canonical_json(dict(config))
            assets_json = canonical_json(dict(assets))
        except CanonicalizationError as exc:
            raise TimelineValidationError(
                f"cannot canonicalize timeline replace_config payload: {exc}"
            ) from exc
        payload = {
            "config": dict(config),
            "registry": registry_shape,
            "expected_version": expected_version,
            "bundle": "__omitted__" if bundle is _BUNDLE_MISSING else bundle,
        }
        try:
            bridge_request_digest = request_hash(command_kind, payload)
        except CanonicalizationError as exc:
            raise TimelineValidationError(
                f"cannot hash timeline replace_config request: {exc}"
            ) from exc

        # Resolve the address to the canonical timeline id inside the same
        # transaction (project-scoped: UUID, then ULID, then slug).
        timeline_id = self._resolve_id(uow, project_id, ref)

        # Effective idempotency key: the caller's key when supplied,
        # otherwise the derived bridge key — mirroring save's derivation.
        derived_key = (
            f"{command_kind}:{project_id}:{timeline_id}:"
            f"{expected_version}:{bridge_request_digest}"
        )
        if idempotency_key is None:
            effective_key = derived_key
            request_digest = bridge_request_digest
        else:
            caller_request = {
                "project_id": project_id,
                "timeline_id": timeline_id,
                **payload,
            }
            try:
                request_digest = request_hash(command_kind, caller_request)
            except CanonicalizationError as exc:  # pragma: no cover - payload hashed above
                raise TimelineValidationError(
                    f"cannot hash timeline replace_config request: {exc}"
                ) from exc
            effective_key = idempotency_key

        # Idempotency gate first: replay or mismatch before any mutation.
        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=effective_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return TimelineReadModel.from_mapping(replayed)

        row = uow.query_one(
            "SELECT t.id, t.project_id, t.event_stream_id, t.name, "
            "t.project_data_json "
            "FROM timelines t WHERE t.id = ? AND t.project_id = ?",
            (timeline_id, project_id),
        )
        if row is None:
            raise TimelineNotFoundError(ref=ref, project_id=project_id)
        stream = uow._stream_row(str(row["event_stream_id"]))
        if stream is None:
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} is missing its event stream"
            )
        current_head = int(stream["head_seq"])
        current_bundle = self._parse_project_data(
            str(row["project_data_json"]), timeline_id
        )
        committed_bundle = current_bundle if bundle is _BUNDLE_MISSING else bundle

        # Event-backed archive fence (SD1): an archived timeline rejects a
        # later replacement before any allocation or projection change.
        if (
            uow.query_one(
                "SELECT 1 FROM events WHERE stream_id = ? AND kind = ? LIMIT 1",
                (row["event_stream_id"], TIMELINE_ARCHIVED_EVENT_KIND),
            )
            is not None
        ):
            raise TimelineArchivedError(
                timeline_id=timeline_id, project_id=project_id
            )

        # Expected-head CAS before any allocation or projection change; a
        # stale write changes zero rows and carries the current head.
        if current_head != expected_version:
            raise TimelineVersionConflictError(
                project_id=project_id,
                timeline_id=timeline_id,
                expected_version=expected_version,
                current_version=current_head,
            )

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TimelineValidationError("created_at must be a non-empty string")

        # 1. Whole-document projection update: document plus registry.
        changed = uow.update_projection(
            "timelines",
            {
                "document_json": config_json,
                "asset_registry_json": assets_json,
                "project_data_json": canonical_json(committed_bundle),
                "updated_at": stamp,
            },
            {"id": timeline_id, "project_id": project_id},
        )
        if changed != 1:
            raise TimelineNotFoundError(ref=ref, project_id=project_id)

        # 2. The timeline.config_replaced event: the command delta,
        #    hash-chained, with the same effective key and a
        #    defense-in-depth expected-head CAS.
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        event_data = {
            "timeline_id": timeline_id,
            "config": dict(config),
            "registry": registry_shape,
            "expected_version": expected_version,
        }
        if bundle is not _BUNDLE_MISSING:
            event_data["bundle"] = committed_bundle
        append = self._events.append(
            uow,
            stream_id=str(row["event_stream_id"]),
            project_id=project_id,
            event_kind=TIMELINE_CONFIG_REPLACED_EVENT_KIND,
            data=event_data,
            changes=["config", "registry"]
            + ([] if bundle is _BUNDLE_MISSING else ["bundle"]),
            idempotency_key=effective_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            expected_head_seq=expected_version,
            created_at=stamp,
        )

        # 3. Aliases and default projection for the frozen read model — the
        #    timeline.created envelope and settings_json are the only
        #    authorities (SD1), never convenience columns.
        alias = uow.query_one(
            "SELECT json_extract(payload_json, '$.data.timeline_ulid') "
            "AS timeline_ulid, json_extract(payload_json, '$.data.slug') "
            "AS slug FROM events WHERE stream_id = ? AND kind = ? "
            "ORDER BY seq ASC LIMIT 1",
            (row["event_stream_id"], TIMELINE_CREATED_EVENT_KIND),
        )
        if alias is None:
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} is missing its timeline.created "
                "alias metadata"
            )
        timeline_ulid = alias["timeline_ulid"]
        slug = alias["slug"]
        if not isinstance(timeline_ulid, str) or not isinstance(slug, str):
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} has malformed timeline.created "
                "alias metadata"
            )
        project_row = uow.query_one(
            "SELECT settings_json FROM projects WHERE id = ?", (project_id,)
        )
        if project_row is None:
            raise ProjectNotFoundError(project_id=project_id)
        default_id = self._default_timeline_id(
            str(project_row["settings_json"]), project_id
        )

        # 4. The complete receipt and the committed frozen load shape.
        read_model = TimelineReadModel(
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            slug=slug,
            name=str(row["name"]),
            is_default=default_id == timeline_id,
            config=dict(config),
            registry=registry_shape,
            config_version=append.stream_seq,
            bundle=committed_bundle,
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=effective_key,
            request_hash=request_digest,
            command_kind=command_kind,
            txn_id=txn_id,
            first_project_seq=append.project_seq,
            last_project_seq=append.project_seq,
            event_ids=[append.event_id],
            result=read_model.to_dict(),
            primary_stream_id=str(row["event_stream_id"]),
            resulting_stream_seq=append.stream_seq,
            created_at=stamp,
        )
        return read_model

    # -- event-backed archive (m4 plan step 7) -----------------------------

    def archive(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        ref: str,
        idempotency_key: str,
        actor_kind: str = "local",
        created_at: str | None = None,
        command_kind: str = TIMELINE_ARCHIVE_COMMAND_KIND,
    ) -> TimelineArchiveReadModel:
        """Archive one timeline atomically and idempotently, event-backed.

        Inside the caller's active unit of work this appends one hash-chained
        ``timeline.archived`` event on the timeline stream (advancing the
        stream and project heads) and records one complete receipt. The
        frozen ``timelines`` table has no ``archived_at`` column (SD1), so
        the archived state is derived solely from the presence of that event
        on the stream — no projection is updated and no byte is deleted.
        Archived timelines disappear from ordinary lists and reject later
        saves, while direct historical lookup keeps working.

        Rejections happen before any write: a missing or foreign timeline
        raises :class:`TimelineNotFoundError`, an already-archived timeline
        raises :class:`TimelineArchivedError`, and the receipt gate runs
        first so an identical retry replays exactly the stored archive result
        with zero new rows while a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        ref = _require_non_empty_string("ref", ref)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise TimelineValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )

        # Resolve the address inside the same transaction (project-scoped).
        timeline_id = self._resolve_id(uow, project_id, ref)

        # Semantic request identity: project + timeline only; the generated
        # archive timestamp never participates.
        request: dict[str, Any] = {
            "project_id": project_id,
            "timeline_id": timeline_id,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise TimelineValidationError(
                f"cannot hash timeline archive request: {exc}"
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
            return TimelineArchiveReadModel.from_mapping(replayed)

        # Fences before any write: the timeline exists in the project and is
        # still active (no committed timeline.archived event on the stream).
        row = uow.query_one(
            "SELECT t.id, t.event_stream_id FROM timelines t "
            "WHERE t.id = ? AND t.project_id = ?",
            (timeline_id, project_id),
        )
        if row is None:
            raise TimelineNotFoundError(ref=ref, project_id=project_id)
        stream_id = str(row["event_stream_id"])
        if uow._stream_row(stream_id) is None:
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} is missing its event stream"
            )
        if (
            uow.query_one(
                "SELECT 1 FROM events WHERE stream_id = ? AND kind = ? LIMIT 1",
                (stream_id, TIMELINE_ARCHIVED_EVENT_KIND),
            )
            is not None
        ):
            raise TimelineArchivedError(
                timeline_id=timeline_id, project_id=project_id
            )

        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise TimelineValidationError("created_at must be a non-empty string")
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex

        # The single archive write: one hash-chained timeline.archived event
        # (advancing stream and project heads), then the complete receipt.
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=TIMELINE_ARCHIVED_EVENT_KIND,
            data={"timeline_id": timeline_id, "archived_at": stamp},
            changes=["timeline_id", "archived_at"],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        read_model = TimelineArchiveReadModel(
            timeline_id=timeline_id,
            project_id=project_id,
            archived_at=stamp,
            config_version=append.stream_seq,
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

    # -- address resolution ------------------------------------------------

    def assert_current_version(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        ref: str,
        expected_version: int,
    ) -> str:
        """Fence a dependent command against one active timeline head.

        This check is deliberately UoW-only. A caller that validates here and
        then writes its dependent row in the same ``BEGIN IMMEDIATE``
        transaction cannot race a concurrent timeline save between validation
        and admission. It returns the canonical timeline id and mutates no
        timeline state.
        """
        _require_non_empty_string("project_id", project_id)
        _require_non_empty_string("ref", ref)
        if isinstance(expected_version, bool) or not isinstance(
            expected_version, int
        ) or expected_version < 0:
            raise TimelineValidationError(
                "expected_version must be a non-negative integer"
            )
        timeline_id = self._resolve_id(uow, project_id, ref)
        row = uow.query_one(
            "SELECT event_stream_id FROM timelines "
            "WHERE id = ? AND project_id = ?",
            (timeline_id, project_id),
        )
        if row is None:  # pragma: no cover - resolved in this transaction
            raise TimelineNotFoundError(ref=ref, project_id=project_id)
        stream_id = str(row["event_stream_id"])
        if (
            uow.query_one(
                "SELECT 1 FROM events WHERE stream_id = ? AND kind = ? LIMIT 1",
                (stream_id, TIMELINE_ARCHIVED_EVENT_KIND),
            )
            is not None
        ):
            raise TimelineArchivedError(
                timeline_id=timeline_id, project_id=project_id
            )
        stream = uow._stream_row(stream_id)
        if stream is None:
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} is missing its event stream"
            )
        current_version = int(stream["head_seq"])
        if current_version != expected_version:
            raise TimelineVersionConflictError(
                project_id=project_id,
                timeline_id=timeline_id,
                expected_version=expected_version,
                current_version=current_version,
            )
        return timeline_id

    def resolve(self, writer: DatabaseWriter, project_id: str, ref: str) -> str:
        """Resolve a UUID, lowercase ULID, or slug to a timeline id.

        A transaction-free read on a separate read-only connection. Resolution
        is project-scoped (bridge §8 order: canonical UUID, then lowercase
        26-character Crockford ULID, then immutable slug); an address matching
        none of the forms raises :class:`TimelineValidationError` (the bridge
        ``400 invalid_timeline``), a missing project raises
        :class:`ProjectNotFoundError`, and a missing timeline raises
        :class:`TimelineNotFoundError`.
        """
        _require_non_empty_string("project_id", project_id)
        _require_non_empty_string("ref", ref)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            return self._resolve_id(conn, project_id, ref)

    def _resolve_id(
        self, reader: Any, project_id: str, ref: str
    ) -> str:
        """Resolve *ref* to the canonical timeline id through *reader*.

        *reader* is anything exposing ``query_one(sql, parameters)`` (a unit
        of work or writer session) or a ``sqlite3.Connection``; the same
        project-scoped, order-fixed resolution runs both transaction-free on a
        read-only connection and inside a command's ``BEGIN IMMEDIATE``.
        """
        project = _query_one(
            reader, "SELECT id FROM projects WHERE id = ?", (project_id,)
        )
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)
        if _UUID_RE.fullmatch(ref) is not None:
            row = _query_one(
                reader,
                "SELECT id FROM timelines WHERE id = ? AND project_id = ?",
                (ref, project_id),
            )
            if row is None:
                raise TimelineNotFoundError(ref=ref, project_id=project_id)
            return ref
        if is_lowercase_ulid(ref):
            row = _query_one(
                reader,
                "SELECT json_extract(e.payload_json, '$.data.timeline_id') "
                "AS timeline_id FROM events e "
                "JOIN event_streams s ON s.id = e.stream_id "
                "WHERE s.project_id = ? AND e.kind = ? "
                "AND json_extract(e.payload_json, '$.data.timeline_ulid') = ? "
                "LIMIT 1",
                (project_id, TIMELINE_CREATED_EVENT_KIND, ref),
            )
            if row is None or row["timeline_id"] is None:
                raise TimelineNotFoundError(ref=ref, project_id=project_id)
            return str(row["timeline_id"])
        if _SLUG_RE.fullmatch(ref) is not None:
            row = _query_one(
                reader,
                "SELECT json_extract(e.payload_json, '$.data.timeline_id') "
                "AS timeline_id FROM events e "
                "JOIN event_streams s ON s.id = e.stream_id "
                "WHERE s.project_id = ? AND e.kind = ? "
                "AND json_extract(e.payload_json, '$.data.slug') = ? "
                "LIMIT 1",
                (project_id, TIMELINE_CREATED_EVENT_KIND, ref),
            )
            if row is None or row["timeline_id"] is None:
                raise TimelineNotFoundError(ref=ref, project_id=project_id)
            return str(row["timeline_id"])
        raise TimelineValidationError(
            f"timeline address {ref!r} is not a canonical UUID, lowercase "
            "ULID, or immutable slug"
        )

    # -- reads -------------------------------------------------------------

    def list(self, writer: DatabaseWriter, project_id: str) -> list[TimelineListRow]:
        """Sorted read-only list query: every active timeline in one project.

        A transaction-free read on a separate read-only connection (the
        frozen bridge ``GET /timelines`` shape, §5.1). Rows carry exactly
        ``{timeline_id, timeline_ulid, slug, name, is_default}``, ordered by
        ``slug`` ascending (deterministic; ``timeline_id`` breaks ties).
        Archived timelines are hidden (SD1/m4 plan step 7): a timeline whose
        stream has a ``timeline.archived`` event is excluded, while direct
        historical lookup (show/history/diff) keeps returning it. A project
        with no timelines returns ``[]``; a missing project raises
        :class:`ProjectNotFoundError` — never an empty authority-dependent
        view.
        """
        _require_non_empty_string("project_id", project_id)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            project = conn.execute(
                "SELECT settings_json FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)
            default_id = self._default_timeline_id(
                str(project["settings_json"]), project_id
            )
            rows = conn.execute(
                "SELECT t.id AS timeline_id, t.event_stream_id, t.name, "
                "json_extract(e.payload_json, '$.data.timeline_ulid') "
                "AS timeline_ulid, "
                "json_extract(e.payload_json, '$.data.slug') AS slug "
                "FROM timelines t "
                "JOIN event_streams s ON s.id = t.event_stream_id "
                "LEFT JOIN events e ON e.stream_id = t.event_stream_id "
                "AND e.kind = ? "
                "WHERE t.project_id = ? "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM events ae "
                "  WHERE ae.stream_id = t.event_stream_id AND ae.kind = ?"
                ") "
                "ORDER BY slug ASC, timeline_id ASC",
                (
                    TIMELINE_CREATED_EVENT_KIND,
                    project_id,
                    TIMELINE_ARCHIVED_EVENT_KIND,
                ),
            ).fetchall()
        rows_out: list[TimelineListRow] = []
        for row in rows:
            timeline_ulid = row["timeline_ulid"]
            slug = row["slug"]
            if not isinstance(timeline_ulid, str) or not isinstance(slug, str):
                raise TimelineRepositoryError(
                    f"timeline {row['timeline_id']!r} is missing its "
                    "timeline.created alias metadata"
                )
            rows_out.append(
                TimelineListRow(
                    timeline_id=str(row["timeline_id"]),
                    timeline_ulid=timeline_ulid,
                    slug=slug,
                    name=str(row["name"]),
                    is_default=default_id == str(row["timeline_id"]),
                )
            )
        return rows_out

    def show(
        self, writer: DatabaseWriter, project_id: str, ref: str
    ) -> TimelineReadModel:
        """Typed show query: one timeline's frozen load shape (§5.2).

        A transaction-free read on a separate read-only connection: resolves
        *ref* (UUID, ULID, or slug) within *project_id*, then returns the
        immutable :class:`TimelineReadModel` with loose ``config``,
        ``registry.assets``, and ``config_version`` equal to the numeric
        timeline stream head. A missing project raises
        :class:`ProjectNotFoundError`, a missing timeline raises
        :class:`TimelineNotFoundError`, and an address matching no form
        raises :class:`TimelineValidationError`.
        """
        _require_non_empty_string("project_id", project_id)
        _require_non_empty_string("ref", ref)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            timeline_id = self._resolve_id(conn, project_id, ref)
            row = conn.execute(
                "SELECT t.id, t.project_id, t.event_stream_id, t.name, "
                "t.document_json, t.asset_registry_json, t.project_data_json, t.created_at, "
                "t.updated_at, s.head_seq "
                "FROM timelines t "
                "JOIN event_streams s ON s.id = t.event_stream_id "
                "WHERE t.id = ? AND t.project_id = ?",
                (timeline_id, project_id),
            ).fetchone()
            if row is None:
                raise TimelineNotFoundError(ref=ref, project_id=project_id)
            alias = conn.execute(
                "SELECT json_extract(payload_json, '$.data.timeline_ulid') "
                "AS timeline_ulid, "
                "json_extract(payload_json, '$.data.slug') AS slug "
                "FROM events WHERE stream_id = ? AND kind = ? "
                "ORDER BY seq ASC LIMIT 1",
                (row["event_stream_id"], TIMELINE_CREATED_EVENT_KIND),
            ).fetchone()
            project = conn.execute(
                "SELECT settings_json FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if alias is None:
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} is missing its timeline.created "
                "alias metadata"
            )
        timeline_ulid = alias["timeline_ulid"]
        slug = alias["slug"]
        if not isinstance(timeline_ulid, str) or not isinstance(slug, str):
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} has malformed timeline.created "
                "alias metadata"
            )
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)
        default_id = self._default_timeline_id(
            str(project["settings_json"]), project_id
        )
        config = self._parse_document(str(row["document_json"]), timeline_id)
        assets = self._parse_document(
            str(row["asset_registry_json"]), timeline_id
        )
        bundle = self._parse_project_data(
            str(row["project_data_json"]), timeline_id
        )
        return TimelineReadModel(
            timeline_id=timeline_id,
            timeline_ulid=timeline_ulid,
            slug=slug,
            name=str(row["name"]),
            is_default=default_id == timeline_id,
            config=config,
            registry={"assets": assets},
            config_version=int(row["head_seq"]),
            bundle=bundle,
        )

    # -- history and adjacent-version diff reads (m4 plan step 7) ----------

    def history(
        self, writer: DatabaseWriter, project_id: str, ref: str
    ) -> List[TimelineHistoryEntry]:
        """Typed ordered history read: the timeline's lifecycle events.

        A transaction-free read on a separate read-only connection. Returns
        one :class:`TimelineHistoryEntry` per ordered ``timeline.created`` /
        ``timeline.saved`` / ``timeline.archived`` event in stream sequence
        (``version`` equals the event ``seq``). Created/saved entries carry
        their document (``config``) and ``registry`` content; the archive
        entry carries ``archived_at`` and ``None`` content (archive never
        changes the document). A missing project/timeline raises the same
        typed errors as :meth:`show`.
        """
        _require_non_empty_string("project_id", project_id)
        _require_non_empty_string("ref", ref)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            timeline_id = self._resolve_id(conn, project_id, ref)
            events = self._lifecycle_events(
                conn, f"{timeline_id}:{TIMELINE_STREAM_TYPE}"
            )
        entries: list[TimelineHistoryEntry] = []
        for event in events:
            kind = event["kind"]
            data = event["data"]
            if kind in (TIMELINE_CREATED_EVENT_KIND, TIMELINE_SAVED_EVENT_KIND):
                config = data.get("config")
                registry = data.get("registry")
                config = dict(config) if isinstance(config, Mapping) else None
                registry = dict(registry) if isinstance(registry, Mapping) else None
            else:
                config = None
                registry = None
            archived_at = data.get("archived_at")
            entries.append(
                TimelineHistoryEntry(
                    version=event["version"],
                    kind=kind,
                    created_at=event["created_at"],
                    config=config,
                    registry=registry,
                    archived_at=archived_at if isinstance(archived_at, str) else None,
                )
            )
        return entries

    def diff(
        self, writer: DatabaseWriter, project_id: str, ref: str
    ) -> List[TimelineDiffEntry]:
        """Deterministic adjacent-version diff read over document/registry keys.

        A transaction-free read on a separate read-only connection. Content
        versions come from the ordered ``timeline.created`` / ``timeline.saved``
        events (the archive event never changes content), so each adjacent
        pair yields one :class:`TimelineDiffEntry` with ``document`` and
        ``registry`` ``added``/``removed``/``changed`` key lists, all sorted
        deterministically. Registry keys are the asset keys under
        ``registry.assets``. A single-version timeline yields ``[]``.
        """
        _require_non_empty_string("project_id", project_id)
        _require_non_empty_string("ref", ref)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            timeline_id = self._resolve_id(conn, project_id, ref)
            events = self._lifecycle_events(
                conn, f"{timeline_id}:{TIMELINE_STREAM_TYPE}"
            )
        versions: list[dict[str, Any]] = []
        for event in events:
            if event["kind"] not in (
                TIMELINE_CREATED_EVENT_KIND,
                TIMELINE_SAVED_EVENT_KIND,
            ):
                continue
            data = event["data"]
            config = data.get("config")
            registry = data.get("registry")
            config = dict(config) if isinstance(config, Mapping) else {}
            registry = dict(registry) if isinstance(registry, Mapping) else {}
            assets = registry.get("assets")
            assets = dict(assets) if isinstance(assets, Mapping) else {}
            versions.append(
                {
                    "version": event["version"],
                    "kind": event["kind"],
                    "config": config,
                    "assets": assets,
                }
            )
        diffs: list[TimelineDiffEntry] = []
        for before, after in zip(versions, versions[1:]):
            diffs.append(
                TimelineDiffEntry(
                    from_version=before["version"],
                    to_version=after["version"],
                    from_kind=before["kind"],
                    to_kind=after["kind"],
                    document=_key_diff(before["config"], after["config"]),
                    registry=_key_diff(before["assets"], after["assets"]),
                )
            )
        return diffs

    # -- private helpers ---------------------------------------------------

    def _lifecycle_events(
        self, reader: Any, stream_id: str
    ) -> List[dict[str, Any]]:
        """Return the ordered timeline lifecycle events with parsed data.

        Reads ``timeline.created`` / ``timeline.saved`` / ``timeline.archived``
        events in stream ``seq`` order and parses each canonical payload into
        ``{"version", "kind", "created_at", "data"}``. Archive state is
        derived from these ordered events alone (SD1).
        """
        rows = _query_all(
            reader,
            "SELECT seq, kind, created_at, payload_json FROM events "
            "WHERE stream_id = ? AND kind IN (?, ?, ?) ORDER BY seq ASC",
            (stream_id, *_TIMELINE_HISTORY_KINDS),
        )
        events: list[dict[str, Any]] = []
        for row in rows:
            seq = int(row["seq"])
            kind = str(row["kind"])
            created_at = str(row["created_at"])
            try:
                payload = parse_json(str(row["payload_json"]))
            except CanonicalizationError as exc:
                raise TimelineRepositoryError(
                    f"timeline event {kind!r} at seq {seq} has invalid JSON: {exc}"
                ) from exc
            data = payload.get("data") if isinstance(payload, Mapping) else {}
            events.append(
                {
                    "version": seq,
                    "kind": kind,
                    "created_at": created_at,
                    "data": dict(data) if isinstance(data, Mapping) else {},
                }
            )
        return events

    def _default_timeline_id(
        self, settings_json: str, project_id: str
    ) -> str | None:
        """Project the repository-owned default timeline id from settings."""
        try:
            parsed = parse_json(settings_json)
        except CanonicalizationError as exc:
            raise TimelineRepositoryError(
                f"project {project_id!r} has invalid settings_json: {exc}"
            ) from exc
        if not isinstance(parsed, Mapping):
            raise TimelineRepositoryError(
                f"project {project_id!r} settings_json is not a JSON object"
            )
        value = parsed.get(DEFAULT_TIMELINE_SETTINGS_KEY)
        if isinstance(value, str) and value:
            return value
        return None

    def _parse_document(
        self, document_json: str, timeline_id: str
    ) -> dict[str, Any]:
        """Parse one timeline's JSON projection canonically."""
        try:
            parsed = parse_json(document_json)
        except CanonicalizationError as exc:
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} has invalid stored JSON: {exc}"
            ) from exc
        if not isinstance(parsed, Mapping):
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} stored JSON is not an object"
            )
        return dict(parsed)

    def _parse_project_data(
        self, project_data_json: str, timeline_id: str
    ) -> dict[str, Any] | None:
        """Parse the bridge-owned project-data lane, failing closed."""
        try:
            parsed = parse_json(project_data_json)
        except CanonicalizationError as exc:
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} has invalid project data JSON: {exc}"
            ) from exc
        if parsed is None:
            return None
        if not isinstance(parsed, Mapping):
            raise TimelineRepositoryError(
                f"timeline {timeline_id!r} project data is not an object"
            )
        # The bridge validates the opaque bundle at its HTTP boundary so a
        # malformed or future persisted value becomes the typed 422
        # ``schema_incompatible`` response.  The repository keeps the value
        # lossless for SDK/read-model consumers and does not reinterpret an
        # already-committed project-data lane.
        return dict(parsed)


__all__ = [
    "DEFAULT_TIMELINE_KEY_SUFFIX",
    "TIMELINE_ARCHIVE_COMMAND_KIND",
    "TIMELINE_ARCHIVED_EVENT_KIND",
    "TIMELINE_CONFIG_REPLACED_EVENT_KIND",
    "TIMELINE_REGISTRY_MERGED_EVENT_KIND",
    "TIMELINE_CREATE_COMMAND_KIND",
    "TIMELINE_CREATED_EVENT_KIND",
    "TIMELINE_REPLACE_CONFIG_COMMAND_KIND",
    "TIMELINE_SAVE_COMMAND_KIND",
    "TIMELINE_SAVED_EVENT_KIND",
    "TIMELINE_STREAM_TYPE",
    "TimelineAlreadyExistsError",
    "TimelineArchiveReadModel",
    "TimelineArchivedError",
    "TimelineDiffEntry",
    "TimelineHistoryEntry",
    "TimelineListRow",
    "TimelineNotFoundError",
    "TimelineReadModel",
    "TimelineRepository",
    "TimelineRepositoryError",
    "TimelineSlugConflictError",
    "TimelineUlidConflictError",
    "TimelineValidationError",
    "TimelineVersionConflictError",
]
