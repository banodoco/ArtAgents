"""Project repository: atomic, idempotent project creation (m1 plan step 11).

:class:`ProjectRepository.create` is the first complete repository vertical:
one writer transaction commits the ``projects`` read model, the ``core.project``
event stream, the ``core.project.created`` event (canonical SD2 envelope,
hash-chained), both heads (``projects.event_head_seq`` and
``event_streams.head_seq``), and one complete ``command_receipts`` row.

Replay contract: callers pass a **stable project ID** (a lowercase Crockford
ULID, see ``astrid.core.ids``). The receipt idempotency gate runs first,
inside the same unit of work, so an identical retry returns exactly the
stored complete result with zero additional rows, and a changed request under
the same key is rejected (:class:`ReceiptMismatchError`) before any mutation.

The repository is stateless apart from the event append and receipt services;
a single instance is safe to share across command callers, and every command
must run inside the caller's :class:`astrid.core.store.uow.UnitOfWork` so all
five writes share one ``BEGIN IMMEDIATE`` transaction. There is no filesystem
project authority: the read model lives only in the kernel database.

Plan step 12 extends the vertical with the read surface and the eventful
update path:

- :meth:`ProjectRepository.list` and :meth:`ProjectRepository.show` are
  **transaction-free** reads over a separate read-only connection: no writer
  transaction is opened and no row is mutated. ``show`` raises the typed
  :class:`ProjectNotFoundError` for a missing project; ``list`` returns rows
  sorted by ``slug`` ascending (the frozen bridge ``GET /projects`` shape).
- :meth:`ProjectRepository.update` eventfully updates ``name``/``settings``
  through the same command path — projection, one hash-chained
  ``core.project.updated`` event, both heads, and one complete receipt in the
  caller's single ``BEGIN IMMEDIATE`` — with the same receipt idempotency gate
  as :meth:`create`.
- Default-timeline metadata is **repository-owned** state persisted inside
  ``settings_json`` under :data:`DEFAULT_TIMELINE_SETTINGS_KEY` (the frozen
  v10 DDL has no default column, SD1). Only
  :meth:`ProjectRepository.set_default_timeline` may write it; caller settings
  updates merge over the current state and can never overwrite it.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from typing import Protocol

from astrid.core.repositories.errors import ACTOR_KINDS

class EventAppendPort(Protocol):
    def append(self, stream_id: str, event: object, **kwargs: object) -> tuple[int, int]:
        ...
from astrid.core.ids import generate_lowercase_ulid, is_lowercase_ulid
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
    parse_json,
    request_hash,
)
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.errors import RepositoryError
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.util.time import utc_now_iso

CORE_PROJECT_STREAM_TYPE = "core.project"
"""The kernel stream type every project aggregate owns (one per project)."""

CORE_PROJECT_CREATED_EVENT_KIND = "core.project.created"
"""The m1 event kind emitted by project creation."""

CORE_PROJECT_CREATE_COMMAND_KIND = "core.project.create"
"""The m1 command kind that project creation receipts are keyed on."""

CORE_PROJECT_UPDATE_COMMAND_KIND = "core.project.update"
"""The m1 command kind that project update receipts are keyed on."""

CORE_PROJECT_UPDATED_EVENT_KIND = "core.project.updated"
"""The m1 event kind emitted by every eventful project update."""

DEFAULT_TIMELINE_SETTINGS_KEY = "default_timeline_id"
"""Repository-owned ``settings_json`` key holding the default timeline id.

The frozen v10 ``projects`` table has no default-timeline column (SD1), so
the repository persists the default inside ``settings_json``. The key is
writable only through :meth:`ProjectRepository.set_default_timeline`;
caller settings updates never touch it.
"""

REPOSITORY_OWNED_SETTINGS_KEYS: frozenset[str] = frozenset(
    {DEFAULT_TIMELINE_SETTINGS_KEY}
)
"""Caller-invisible ``settings_json`` keys owned by the repository."""

_SLUG_RE = re.compile(r"^(?=.{1,63}$)[a-z0-9]+(?:-[a-z0-9]+)*$")
"""Immutable slug grammar: lowercase letters/digits joined by single hyphens."""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProjectRepositoryError(RepositoryError):
    """Base error for the project repository family.

    Subclasses :class:`astrid.core.repositories.errors.RepositoryError`
    (and therefore :class:`astrid.core.store.writer.WriterError`), so the
    kernel store error family catches project contract violations too.
    """


class ProjectValidationError(ProjectRepositoryError):
    """Raised when a project create/get argument is invalid."""

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        self.details: dict[str, Any] = dict(details or {})
        super().__init__(message)


class ProjectAlreadyExistsError(ProjectRepositoryError):
    """Raised when a create targets an already-existing project id."""

    def __init__(self, *, project_id: str) -> None:
        self.project_id: str = project_id
        super().__init__(f"project already exists: {project_id!r}")


class ProjectSlugConflictError(ProjectRepositoryError):
    """Raised when a create targets an already-used slug."""

    def __init__(self, *, slug: str) -> None:
        self.slug: str = slug
        super().__init__(f"project slug already in use: {slug!r}")


class ProjectAmbiguousError(ProjectRepositoryError):
    """Raised when a display name matches multiple projects."""

    def __init__(self, *, name: str, candidates: Sequence[Mapping[str, Any]]) -> None:
        self.name = name
        self.candidates = [dict(candidate) for candidate in candidates]
        super().__init__(f"project display name is ambiguous: {name!r}")


class ProjectNotFoundError(ProjectRepositoryError):
    """Raised when a read targets a project id with no projects row."""

    def __init__(self, *, project_id: str) -> None:
        self.project_id: str = project_id
        super().__init__(f"unknown project: {project_id!r}")


# ---------------------------------------------------------------------------
# Immutable read model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProjectReadModel:
    """Immutable project read model (m1 plan step 11).

    A frozen projection of the ``projects`` row plus the parsed
    ``settings_json``. Read models are never mutated in place; repository
    commands return new instances.
    """

    id: str
    slug: str
    name: str
    settings: Mapping[str, Any]
    event_head_seq: int
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe dict persisted as the receipt result."""
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "settings": dict(self.settings),
            "event_head_seq": self.event_head_seq,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ProjectReadModel:
        """Rebuild the frozen read model from a stored result mapping."""
        return cls(
            id=str(value["id"]),
            slug=str(value["slug"]),
            name=str(value["name"]),
            settings=dict(value.get("settings") or {}),
            event_head_seq=int(value["event_head_seq"]),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
        )

    @property
    def default_timeline_id(self) -> str | None:
        """The repository-owned default timeline id from ``settings_json``.

        The frozen v10 DDL has no default-timeline column (SD1), so the
        repository persists the default inside ``settings_json`` under
        :data:`DEFAULT_TIMELINE_SETTINGS_KEY`. This property projects it
        for read consumers (the timeline pack and the bridge); it is
        ``None`` until :meth:`ProjectRepository.set_default_timeline`
        has been called.
        """
        value = self.settings.get(DEFAULT_TIMELINE_SETTINGS_KEY)
        if isinstance(value, str) and value:
            return value
        return None


@dataclass(frozen=True, slots=True)
class ProjectListRow:
    """One sorted project list row (frozen bridge ``GET /projects`` shape).

    A lightweight read-only projection of exactly the ``{slug, name}``
    fields the frozen bridge list contract exposes, ordered by ``slug``
    ascending. Never mutated; produced only by the transaction-free
    :meth:`ProjectRepository.list` read.
    """

    slug: str
    name: str

    def to_dict(self) -> dict[str, str]:
        """Return the JSON-safe dict serialized by the bridge list route."""
        return {"slug": self.slug, "name": self.name}


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ProjectValidationError(f"{name} must be a non-empty string")
    return value


def _reject_repository_owned_settings(settings: Mapping[str, Any]) -> None:
    """Reject caller attempts to write repository-owned settings keys.

    Default-timeline metadata is repository-owned state persisted inside
    ``settings_json`` (SD1); only
    :meth:`ProjectRepository.set_default_timeline` may write it. A caller
    passing such a key directly violates that contract and is rejected
    with a typed error before any mutation.
    """
    owned = REPOSITORY_OWNED_SETTINGS_KEYS.intersection(settings)
    if owned:
        raise ProjectValidationError(
            "settings must not contain repository-owned keys: "
            + ", ".join(sorted(owned))
        )


def _query_one(reader: Any, sql: str, parameters: Sequence[Any] = ()) -> Any:
    """Run one read on a UoW/WriterSession reader or a raw connection.

    The unit of work and the writer session expose ``query_one(sql, params)``;
    a ``sqlite3.Connection`` exposes ``execute(...).fetchone()``. Both shapes
    are accepted so the same address-resolution helper works transaction-free
    on a read-only connection and inside a command's ``BEGIN IMMEDIATE``.
    """
    query_one = getattr(reader, "query_one", None)
    if query_one is not None:
        return query_one(sql, parameters)
    cursor = reader.execute(sql, parameters)
    return cursor.fetchone()


class ProjectRepository:
    """Stateless project command/read surface over the kernel unit of work."""

    def __init__(
        self,
        events: EventAppendPort,
        receipts: ReceiptService,
    ) -> None:
        self._events = events
        self._receipts = receipts

    # -- create ------------------------------------------------------------

    def create(
        self,
        uow: UnitOfWork,
        *,
        slug: str,
        name: str,
        settings: Mapping[str, Any],
        idempotency_key: str,
        actor_kind: str = "local",
        project_id: str | None = None,
        command_kind: str = CORE_PROJECT_CREATE_COMMAND_KIND,
        created_at: str | None = None,
    ) -> ProjectReadModel:
        """Create a project atomically and idempotently.

        Inside the caller's active unit of work this persists, in one
        ``BEGIN IMMEDIATE`` transaction: the ``projects`` read model, the
        ``core.project`` event stream, the ``core.project.created`` event
        (canonical envelope, chained from genesis), both heads, and one
        complete receipt.

        Idempotency: the receipt gate runs before any mutation. When
        *project_id* is supplied (the stable-ID replay contract), an
        identical retry returns exactly the stored result with zero new
        rows, and a changed request under the same key raises
        :class:`ReceiptMismatchError` before any sequence allocation.

        When *project_id* is omitted a fresh lowercase Crockford ULID is
        generated; for replay, callers must supply the same stable
        *project_id* on retries.
        """
        slug = _require_non_empty_string("slug", slug)
        name = _require_non_empty_string("name", name)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if not isinstance(settings, Mapping):
            raise ProjectValidationError("settings must be a JSON object")
        _reject_repository_owned_settings(settings)
        if actor_kind not in ACTOR_KINDS:
            raise ProjectValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if _SLUG_RE.fullmatch(slug) is None:
            raise ProjectValidationError(
                "slug must be lowercase letters/digits joined by single "
                f"hyphens, got {slug!r}"
            )
        if project_id is None:
            project_id = generate_lowercase_ulid()
        else:
            _require_non_empty_string("project_id", project_id)

        try:
            settings_json = canonical_json(dict(settings))
        except CanonicalizationError as exc:
            raise ProjectValidationError(
                f"cannot canonicalize project settings: {exc}"
            ) from exc

        # Semantic request identity: stable project id, slug, name, and
        # settings all participate; generated values are excluded.
        request = {
            "project_id": project_id,
            "slug": slug,
            "name": name,
            "settings": dict(settings),
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ProjectValidationError(
                f"cannot hash project create request: {exc}"
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
            return ProjectReadModel.from_mapping(replayed)

        # Typed duplicate rejection before the UNIQUE constraints fire.
        existing = uow.query_one(
            "SELECT id FROM projects WHERE id = ? OR slug = ?",
            (project_id, slug),
        )
        if existing is not None:
            if existing["id"] == project_id:
                raise ProjectAlreadyExistsError(project_id=project_id)
            raise ProjectSlugConflictError(slug=slug)

        # Generated values for this attempt (excluded from request identity).
        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stream_id = f"{project_id}:{CORE_PROJECT_STREAM_TYPE}"
        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ProjectValidationError("created_at must be a non-empty string")

        # 1. The projects read model (event_head_seq starts at 0; the append
        #    below advances it to 1 in the same transaction).
        uow.execute(
            "INSERT INTO projects "
            "(id, slug, name, settings_json, event_head_seq, created_at, "
            "updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (project_id, slug, name, settings_json, stamp, stamp),
        )
        # 2. The core.project stream (head_seq starts at 0).
        uow.execute(
            "INSERT INTO event_streams "
            "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (stream_id, project_id, CORE_PROJECT_STREAM_TYPE, project_id, stamp),
        )
        # 3. The hash-chained core.project.created event; this advances
        #    projects.event_head_seq and event_streams.head_seq together.
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_PROJECT_CREATED_EVENT_KIND,
            data={"slug": slug, "name": name, "settings": dict(settings)},
            changes=["slug", "name", "settings"],
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 4. The complete receipt: transaction id, stream association,
        #    exact project sequence range, ordered event ids, and result.
        read_model = ProjectReadModel(
            id=project_id,
            slug=slug,
            name=name,
            settings=dict(settings),
            event_head_seq=append.project_seq,
            created_at=stamp,
            updated_at=stamp,
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

    # -- reads -------------------------------------------------------------

    def get(self, uow: UnitOfWork, project_id: str) -> ProjectReadModel | None:
        """Return the immutable read model for one project, or ``None``.

        Runs inside the caller's active unit of work (the typed command
        read path). Parses ``settings_json`` canonically and returns a
        frozen :class:`ProjectReadModel`. No filesystem authority is
        involved. For the transaction-free read surface see
        :meth:`show` (typed not-found) and :meth:`list`.
        """
        _require_non_empty_string("project_id", project_id)
        row = uow.query_one(
            "SELECT id, slug, name, settings_json, event_head_seq, "
            "created_at, updated_at FROM projects WHERE id = ?",
            (project_id,),
        )
        if row is None:
            return None
        return self._row_to_read_model(row, project_id)

    def show(self, writer: DatabaseWriter, project_id: str) -> ProjectReadModel:
        """Typed show query: one project's immutable read model.

        A transaction-free read: opens a separate read-only connection via
        the writer's ``read_only_connection()`` path, so no writer
        transaction is opened and no row is mutated. Raises
        :class:`ProjectNotFoundError` when no ``projects`` row exists for
        *project_id* — the typed not-found contract of plan step 12 (never
        an empty authority-dependent view).
        """
        _require_non_empty_string("project_id", project_id)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, slug, name, settings_json, event_head_seq, "
                "created_at, updated_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise ProjectNotFoundError(project_id=project_id)
        return self._row_to_read_model(row, project_id)

    def list(self, writer: DatabaseWriter) -> list[ProjectListRow]:
        """Sorted read-only list query: every project, slug ascending.

        A transaction-free read on a separate read-only connection (the
        frozen bridge ``GET /projects`` ordering). Returns one
        :class:`ProjectListRow` per project; a root with no projects
        returns ``[]``. No writer transaction is opened and no row is
        mutated.
        """
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT slug, name FROM projects ORDER BY slug ASC"
            ).fetchall()
        return [
            ProjectListRow(slug=str(row["slug"]), name=str(row["name"]))
            for row in rows
        ]

    def resolve(self, writer: DatabaseWriter, ref: str) -> str:
        """Resolve a project id or immutable slug to the canonical project id.

        A transaction-free read on a separate read-only connection (the same
        path as :meth:`show`/:meth:`list`). Resolution order is an exact
        ``id`` match first (project ids are opaque strings — a lowercase
        Crockford ULID when generated by the repository, or a deterministic
        derived id from the SDK), then an immutable slug. An address
        matching neither the id nor slug grammar raises
        :class:`ProjectValidationError`; a well-formed address with no
        matching row raises :class:`ProjectNotFoundError` (the typed
        not-found contract, never an empty authority-dependent view).
        """
        _require_non_empty_string("ref", ref)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            return self._resolve_ref(conn, ref)

    def _resolve_ref(self, reader: Any, ref: str) -> str:
        """Resolve *ref* to the canonical project id through *reader*.

        *reader* is anything exposing ``query_one(sql, parameters)`` (a unit
        of work or writer session) or a ``sqlite3.Connection``; the same
        exact-id-first, then-slug resolution runs both transaction-free on
        a read-only connection and inside a command's ``BEGIN IMMEDIATE``.
        """
        row = _query_one(reader, "SELECT id FROM projects WHERE id = ?", (ref,))
        if row is not None:
            return str(row[0])
        if _SLUG_RE.fullmatch(ref) is not None:
            row = _query_one(
                reader, "SELECT id FROM projects WHERE slug = ?", (ref,)
            )
            if row is not None:
                return str(row[0])
        if is_lowercase_ulid(ref) or _SLUG_RE.fullmatch(ref) is not None:
            raise ProjectNotFoundError(project_id=ref)
        name_rows = reader.execute(
            "SELECT id, slug, name FROM projects WHERE name = ? ORDER BY slug ASC",
            (ref,),
        ).fetchall() if hasattr(reader, "execute") else reader.query(
            "SELECT id, slug, name FROM projects WHERE name = ? ORDER BY slug ASC",
            (ref,),
        )
        if name_rows:
            candidates = [
                {"id": str(row["id"]), "slug": str(row["slug"]), "name": str(row["name"])}
                for row in name_rows
            ]
            if len(candidates) > 1:
                raise ProjectAmbiguousError(name=ref, candidates=candidates)
            raise ProjectValidationError(
                f"project display name {ref!r} is not an address; use its slug or id",
                details={
                    "field": "ref",
                    "reason": "display_name_not_addressable",
                    "candidates": candidates,
                    "recovery": "retry with candidates[0].slug or candidates[0].id",
                },
            )
        raise ProjectValidationError(
            f"project address {ref!r} is not a canonical id or slug",
            details={
                "field": "ref",
                "expected": "project id or lowercase slug",
                "recovery": "run `astrid projects list --json`, then retry with slug or id",
            },
        )

    # -- eventful update (m1 plan step 12) ---------------------------------

    def update(
        self,
        uow: UnitOfWork,
        project_id: str,
        *,
        name: str | None = None,
        settings: Mapping[str, Any] | None = None,
        idempotency_key: str,
        actor_kind: str = "local",
        command_kind: str = CORE_PROJECT_UPDATE_COMMAND_KIND,
        created_at: str | None = None,
    ) -> ProjectReadModel:
        """Eventfully and idempotently update a project's name and/or settings.

        Inside the caller's active unit of work this persists, in one
        ``BEGIN IMMEDIATE`` transaction: the ``projects`` projection
        (``name``, ``settings_json``, ``updated_at``), one hash-chained
        ``core.project.updated`` event, both heads, and one complete
        receipt — the same command path as :meth:`create`.

        Idempotency mirrors :meth:`create`: the receipt gate runs first,
        an identical retry returns exactly the stored result with zero new
        rows, and a changed request under the same key raises
        :class:`ReceiptMismatchError` before any mutation. A missing
        project raises :class:`ProjectNotFoundError` before any mutation,
        and an update that changes nothing is rejected.

        ``name``/``settings`` are the provided delta: ``None`` leaves the
        field unchanged. Caller ``settings`` merge over the current state
        but can never write repository-owned keys (default-timeline
        metadata stays repository-owned).
        """
        project_id = _require_non_empty_string("project_id", project_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise ProjectValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )
        if name is not None:
            name = _require_non_empty_string("name", name)
        if settings is not None:
            if not isinstance(settings, Mapping):
                raise ProjectValidationError("settings must be a JSON object")
            _reject_repository_owned_settings(settings)
            try:
                canonical_json(dict(settings))
            except CanonicalizationError as exc:
                raise ProjectValidationError(
                    f"cannot canonicalize project settings: {exc}"
                ) from exc

        # Semantic request identity: the provided delta only; generated
        # values and the current projection state are excluded.
        request = {
            "project_id": project_id,
            "name": name,
            "settings": dict(settings) if settings is not None else None,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ProjectValidationError(
                f"cannot hash project update request: {exc}"
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
            return ProjectReadModel.from_mapping(replayed)

        # Typed not-found before any mutation.
        row = uow.query_one(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        )
        if row is None:
            raise ProjectNotFoundError(project_id=project_id)

        existing_name = str(row["name"])
        existing_settings = self._parse_settings(
            row["settings_json"], project_id
        )
        new_name = existing_name if name is None else name
        new_settings = dict(existing_settings)
        if settings is not None:
            new_settings.update(dict(settings))

        changes: list[str] = []
        if new_name != existing_name:
            changes.append("name")
        if new_settings != existing_settings:
            changes.append("settings")
        if not changes:
            raise ProjectValidationError(
                "update requires a change: name and settings are unchanged"
            )

        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ProjectValidationError("created_at must be a non-empty string")

        return self._persist_update(
            uow,
            project_id=project_id,
            slug=str(row["slug"]),
            created_at=str(row["created_at"]),
            name=new_name,
            settings=new_settings,
            changes=changes,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            command_kind=command_kind,
            actor_kind=actor_kind,
            txn_id=txn_id,
            event_id=event_id,
            stamp=stamp,
        )

    def set_default_timeline(
        self,
        uow: UnitOfWork,
        project_id: str,
        timeline_id: str,
        *,
        idempotency_key: str,
        actor_kind: str = "system",
        command_kind: str = CORE_PROJECT_UPDATE_COMMAND_KIND,
        created_at: str | None = None,
    ) -> ProjectReadModel:
        """Set the repository-owned default timeline id in ``settings_json``.

        The frozen v10 ``projects`` DDL has no default-timeline column
        (SD1), so the default is repository-owned state persisted inside
        ``settings_json`` under :data:`DEFAULT_TIMELINE_SETTINGS_KEY`.
        This is the only supported way to change it; caller ``settings``
        updates never touch the key. The change is eventful
        (``core.project.updated``) and receipted like :meth:`update`.

        Setting the id that is already the default is idempotent-in-effect:
        the current read model is returned and no event, head advance, or
        receipt is written, so the timeline pack can call this safely
        during timeline creation replay.
        """
        project_id = _require_non_empty_string("project_id", project_id)
        timeline_id = _require_non_empty_string("timeline_id", timeline_id)
        idempotency_key = _require_non_empty_string(
            "idempotency_key", idempotency_key
        )
        command_kind = _require_non_empty_string("command_kind", command_kind)
        if actor_kind not in ACTOR_KINDS:
            raise ProjectValidationError(
                f"actor_kind must be one of {sorted(ACTOR_KINDS)}, "
                f"got {actor_kind!r}"
            )

        request = {
            "project_id": project_id,
            "default_timeline_id": timeline_id,
        }
        try:
            request_digest = request_hash(command_kind, request)
        except CanonicalizationError as exc:
            raise ProjectValidationError(
                f"cannot hash default timeline update request: {exc}"
            ) from exc

        replayed = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=command_kind,
        )
        if replayed is not None:
            return ProjectReadModel.from_mapping(replayed)

        row = uow.query_one(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        )
        if row is None:
            raise ProjectNotFoundError(project_id=project_id)

        existing_settings = self._parse_settings(
            row["settings_json"], project_id
        )
        new_settings = dict(existing_settings)
        new_settings[DEFAULT_TIMELINE_SETTINGS_KEY] = timeline_id
        if new_settings == existing_settings:
            # Idempotent-in-effect: already the default; current model.
            return self._row_to_read_model(row, project_id)

        txn_id = uuid.uuid4().hex
        event_id = uuid.uuid4().hex
        stamp = created_at if created_at is not None else utc_now_iso()
        if not isinstance(stamp, str) or not stamp:
            raise ProjectValidationError("created_at must be a non-empty string")

        return self._persist_update(
            uow,
            project_id=project_id,
            slug=str(row["slug"]),
            created_at=str(row["created_at"]),
            name=str(row["name"]),
            settings=new_settings,
            changes=["settings"],
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            command_kind=command_kind,
            actor_kind=actor_kind,
            txn_id=txn_id,
            event_id=event_id,
            stamp=stamp,
        )

    # -- private helpers ---------------------------------------------------

    def _parse_settings(
        self, settings_json: str, project_id: str
    ) -> dict[str, Any]:
        """Parse one project's ``settings_json`` canonically."""
        try:
            parsed = parse_json(settings_json)
        except CanonicalizationError as exc:
            raise ProjectRepositoryError(
                f"project {project_id!r} has invalid settings_json: {exc}"
            ) from exc
        if not isinstance(parsed, Mapping):
            raise ProjectRepositoryError(
                f"project {project_id!r} settings_json is not a JSON object"
            )
        return dict(parsed)

    def _row_to_read_model(
        self, row: Any, project_id: str
    ) -> ProjectReadModel:
        """Build the frozen read model from a ``projects`` row."""
        return ProjectReadModel(
            id=str(row["id"]),
            slug=str(row["slug"]),
            name=str(row["name"]),
            settings=self._parse_settings(row["settings_json"], project_id),
            event_head_seq=int(row["event_head_seq"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _persist_update(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        slug: str,
        created_at: str,
        name: str,
        settings: Mapping[str, Any],
        changes: Sequence[str],
        idempotency_key: str,
        request_digest: str,
        command_kind: str,
        actor_kind: str,
        txn_id: str,
        event_id: str,
        stamp: str,
    ) -> ProjectReadModel:
        """Commit one eventful project update: projection, event, receipt.

        Runs inside the caller's active unit of work and persists, in one
        ``BEGIN IMMEDIATE`` transaction, the projection change, one
        hash-chained ``core.project.updated`` event (advancing both
        heads), and one complete update receipt.
        """
        try:
            settings_json = canonical_json(dict(settings))
        except CanonicalizationError as exc:
            raise ProjectValidationError(
                f"cannot canonicalize project settings: {exc}"
            ) from exc

        # 1. The projects projection (name, settings_json, updated_at).
        changed = uow.update_projection(
            "projects",
            {
                "name": name,
                "settings_json": settings_json,
                "updated_at": stamp,
            },
            {"id": project_id},
        )
        if changed != 1:
            raise ProjectNotFoundError(project_id=project_id)

        # 2. The hash-chained core.project.updated event; this advances
        #    projects.event_head_seq and event_streams.head_seq together.
        stream_id = f"{project_id}:{CORE_PROJECT_STREAM_TYPE}"
        append = self._events.append(
            uow,
            stream_id=stream_id,
            project_id=project_id,
            event_kind=CORE_PROJECT_UPDATED_EVENT_KIND,
            data={"name": name, "settings": dict(settings)},
            changes=changes,
            idempotency_key=idempotency_key,
            txn_id=txn_id,
            actor_kind=actor_kind,
            command_kind=command_kind,
            event_id=event_id,
            created_at=stamp,
        )
        # 3. The complete receipt for the update command.
        read_model = ProjectReadModel(
            id=project_id,
            slug=slug,
            name=name,
            settings=dict(settings),
            event_head_seq=append.project_seq,
            created_at=created_at,
            updated_at=stamp,
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


__all__ = [
    "CORE_PROJECT_CREATE_COMMAND_KIND",
    "CORE_PROJECT_CREATED_EVENT_KIND",
    "CORE_PROJECT_STREAM_TYPE",
    "CORE_PROJECT_UPDATE_COMMAND_KIND",
    "CORE_PROJECT_UPDATED_EVENT_KIND",
    "DEFAULT_TIMELINE_SETTINGS_KEY",
    "ProjectAlreadyExistsError",
    "ProjectListRow",
    "ProjectNotFoundError",
    "ProjectReadModel",
    "ProjectRepository",
    "ProjectRepositoryError",
    "ProjectSlugConflictError",
    "ProjectValidationError",
    "REPOSITORY_OWNED_SETTINGS_KEYS",
]
