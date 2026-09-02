"""Reusable repository-command conformance kit (m1 plan step 15 / NSA-2).

The kit generalizes the transactional invariants every implemented command
must satisfy across the kernel and pack repositories, so a conformance
inventory cannot give false confidence by omitting a dimension. Each
dimension is a deterministic check over the kernel writer/unit-of-work plus
the command's own adapter — a :class:`CommandSpec` — and every check runs
through the real writer, services, and repositories:

``replay``
    An identical retry under the same idempotency key returns exactly the
    stored complete result with zero new rows (events, receipts, heads).

``mismatch_before_mutation``
    A changed request under the same key is rejected *before* any mutation:
    the stored receipt is never overwritten and no row changes.

``same_project``
    Commands and reads are project-scoped: another project can neither
    address nor mutate this project's data, and every cross-project access
    fails with a typed not-found error.

``vocabulary``
    Every registered command/event/stream name is declared by the frozen
    registry, undeclared names are rejected before any SQL mutation, and
    the executable command set registers **only implemented commands**
    (m1: ``timeline.create`` and ``timeline.save``); declared-but-
    unimplemented shot/reference commands stay explicitly non-executable.

``writer_ownership``
    One writer thread owns one connection, every command runs inside
    exactly one ``BEGIN IMMEDIATE`` transaction with one ``COMMIT``, reads
    run on a separate read-only connection without a writer transaction,
    no connection escapes the writer session, and concurrent semantic
    callers can never obtain parallel write transactions (strict FIFO).

``crash_atomicity``
    Statement-boundary old-or-complete behavior: an injected crash after
    every SQL statement boundary (including pre- and post-commit) reopens
    to either the old state or the complete committed state — never a
    partial intermediate — and ``PRAGMA quick_check`` /
    ``foreign_key_check`` pass on every reopened database.

``hash_chain``
    Full envelope hash-chain verification (NSA-2): the committed stream
    verifies from genesis through its head, and tampering with domain data
    or an integrity field breaks verification — presence of the fields
    alone is never proof.

The kit is kernel code: it never imports a pack module. The timeline
command specs are assembled from the injected :class:`ConformanceContext`
(duck-typed repositories), so no kernel-to-pack import is created and the
architecture lint stays clean.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrid.core.events.registry import (
    validate_command_kind,
    validate_event_kind,
    validate_stream_type,
)
from astrid.core.events.service import (
    EventAppendService,
    EventChainError,
)
from astrid.core.io.media_import import prepare_media_file
from astrid.core.receipts import ReceiptMismatchError, ReceiptService
from astrid.core.repositories.errors import (
    CommandVocabularyError,
    EventVocabularyError,
    RepositoryError,
    StreamVocabularyError,
)
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.database import open_database
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter, WriterSession

TS = "2026-08-15T00:00:00.000000+00:00"
"""Deterministic timestamp used by kit command invocations."""

CONFORMANCE_DIMENSIONS: tuple[str, ...] = (
    "replay",
    "mismatch_before_mutation",
    "same_project",
    "vocabulary",
    "writer_ownership",
    "crash_atomicity",
    "hash_chain",
)
"""Every dimension the kit covers, in canonical order."""

NON_EXECUTABLE_COMMAND_KINDS: tuple[str, ...] = (
    "shot.add_item",
    "reference.set_primary",
)
"""Declared-but-unimplemented command kinds that must never be executable.

The shots and references packs declare their normative vocabulary in their
canonical ``pack.yaml`` database projections but ship no executable repository
in this kit (``repositories: []``); the registry still declares them so a
would-be caller gets a typed error, never an allowlist hole.
"""

# Every kernel mutation table the kit snapshots (the frozen 14-table kernel
# DDL plus the timeline pack table). The two packs that ship no executable
# repository (shots, references) contribute no tables any command mutates.
_SNAPSHOT_TABLES: tuple[str, ...] = (
    "projects",
    "event_streams",
    "events",
    "command_receipts",
    "runs",
    "tasks",
    "task_dependencies",
    "execution_attempts",
    "media",
    "media_locations",
    "media_relations",
    "task_outputs",
    "evidence_items",
    "timelines",
)

# Shared plumbing every receipt-protected command touches: the project head,
# the event stream/event rows, and the single complete receipt. A command's
# ``mutable_tables`` declaration covers only the tables it *owns*; the
# replay check allows deltas on the plumbing plus the declared tables.
_PLUMBING_TABLES: frozenset[str] = frozenset(
    {"projects", "event_streams", "events", "command_receipts"}
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ConformanceError(RuntimeError):
    """One or more conformance dimensions failed, with diagnostics."""

    def __init__(self, message: str, failures: list[str] | None = None) -> None:
        self.failures: list[str] = list(failures or [])
        super().__init__(message)


class _InjectedCrash(RuntimeError):
    """Sentinel exception raised at one statement boundary by the crash check."""


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConformanceEvidence:
    """Deterministic evidence one dimension produced for one command."""

    command_kind: str
    dimension: str
    detail: Mapping[str, Any]


@dataclass(slots=True)
class ConformanceReport:
    """Per-dimension evidence accumulated by :func:`run_all`."""

    command_kind: str
    evidence: list[ConformanceEvidence] = field(default_factory=list)

    def add(self, dimension: str, detail: Mapping[str, Any]) -> None:
        self.evidence.append(
            ConformanceEvidence(
                command_kind=self.command_kind,
                dimension=dimension,
                detail=dict(detail),
            )
        )


# ---------------------------------------------------------------------------
# Command adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """One implemented command the kit can drive through every dimension.

    Callables are duck-typed against the injected context repositories so
    the kernel kit never imports a pack module:

    - ``invoke(ctx, uow, *, project_id, key)`` runs a fresh, deterministic
      request under ``key`` and returns the frozen read model;
    - ``invoke_changed(ctx, uow, *, project_id, key)`` runs a *changed*
      request under the same ``key`` (the mismatch sample);
    - ``read(ctx, writer, project_id, ref)`` loads the command's aggregate
      through the transaction-free read surface;
    - ``seed(ctx, writer)`` prepares the pre-command state on a scratch
      database (project, and a timeline at head 1 for saves) and returns
      the seed facts (``project_id``, ``ref``, ``key``) the crash check
      needs.
    """

    command_kind: str
    pack_id: str
    stream_type: str
    event_kinds: tuple[str, ...]
    invoke: Callable[..., Any]
    invoke_changed: Callable[..., Any]
    read: Callable[..., Any]
    seed: Callable[..., dict[str, Any]]
    prepare: Callable[..., None]
    is_expected_mismatch: Callable[[BaseException], bool] | None = None
    # -- m2 declarations (plan step 15, T24_impl) --------------------------
    # ``result_ref`` extracts the aggregate identity from a command's read
    # model (e.g. ``model.id`` for tasks/media) so the same-project and
    # hash-chain checks can address the aggregate generically; the timeline
    # specs keep the historical ``slug``/``timeline_id`` fallback.
    result_ref: Callable[[Any], str] | None = None
    # ``project_ids`` optionally declares the project slugs the spec needs
    # (default: the standard conform-a/conform-b pair run_all creates).
    project_ids: tuple[str, ...] | None = None
    # ``fs_fixtures`` materializes prepared filesystem fixtures under
    # ``ConformanceContext.managed_root`` before a command runs (media
    # import needs real prepared bytes on disk; task/timeline commands do
    # not). It is invoked by the checks right before seed/prepare and must
    # be idempotent (crash re-seeds share one managed root).
    fs_fixtures: Callable[[ConformanceContext], None] | None = None
    # ``mutable_tables`` declares the kernel tables this command owns;
    # replay asserts every row-count delta stays within the declared set
    # plus the shared plumbing (projects/event_streams/events/receipts).
    mutable_tables: tuple[str, ...] | None = None
    # ``list_other`` returns another project's aggregate list (typed
    # empty) for the same-project check; defaults to the timeline list.
    list_other: Callable[
        [ConformanceContext, DatabaseWriter, str], Sequence[Any]
    ] | None = None


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


class ConformanceContext:
    """The kernel services + repositories one conformance run exercises."""

    def __init__(
        self,
        *,
        db_path: str | Path,
        writer: DatabaseWriter,
        registry: Any,
        events: EventAppendService,
        receipts: ReceiptService,
        projects: ProjectRepository,
        timelines: Any = None,
        tasks: Any = None,
        media: Any = None,
        runs: Any = None,
        managed_root: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.writer = writer
        self.registry = registry
        self.events = events
        self.receipts = receipts
        self.projects = projects
        self.timelines = timelines
        # m2 kernel repository verticals (plan step 15, T24_impl): injected
        # duck-typed so the kit never imports a pack; ``managed_root`` is
        # the temporary root the media spec's prepared filesystem fixtures
        # and managed publication share.
        self.tasks = tasks
        self.media = media
        self.runs = runs
        self.managed_root = Path(managed_root) if managed_root is not None else None

    # -- seeding helpers --------------------------------------------------

    def create_project(
        self,
        *,
        slug: str,
        key: str,
        name: str | None = None,
        settings: Mapping[str, Any] | None = None,
    ) -> Any:
        """Create one project through the real repository command."""
        return UnitOfWork(self.writer).run(
            lambda u: self.projects.create(
                u,
                slug=slug,
                name=name or slug,
                settings=dict(settings or {}),
                idempotency_key=key,
                created_at=TS,
            )
        )

    def row_counts(self) -> dict[str, int]:
        """Count rows in every kernel mutation table on a read-only conn."""
        counts: dict[str, int] = {}
        with self.writer.read_only_connection() as conn:
            for table in _SNAPSHOT_TABLES:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                counts[table] = int(row[0])
        return counts

    def table_counts_on(self, db_path: Path) -> dict[str, int]:
        """Count rows in a scratch database through a read-only open."""
        counts: dict[str, int] = {}
        conn = open_database(db_path, self.registry, read_only=True)
        try:
            for table in _SNAPSHOT_TABLES:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                counts[table] = int(row[0])
        finally:
            conn.close()
        return counts

    def head_of(self, writer: DatabaseWriter, stream_id: str) -> int:
        """Read one stream's committed head through a read-only connection."""
        with writer.read_only_connection() as conn:
            row = conn.execute(
                "SELECT head_seq FROM event_streams WHERE id = ?", (stream_id,)
            ).fetchone()
        if row is None:
            raise ConformanceError(f"unknown stream {stream_id!r} in head_of")
        return int(row[0])


def _slug_suffix(key: str) -> str:
    """Derive a slug-safe suffix from a kit key (grammar: [a-z0-9-])."""
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in key.lower())
    return "-".join(part for part in cleaned.split("-") if part)


def _stable_timeline_id(key: str) -> str:
    """Deterministic timeline id for one kit key (stable-ID replay)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"astrid-conformance:{key}"))


def _stable_timeline_ulid(key: str) -> str:
    """Deterministic lowercase Crockford ULID for one kit key.

    The timeline ULID alias participates in the create request identity, so
    a replay under the same key must present the same alias. 128 bits from
    SHA-256 encode into the canonical 26-character Crockford base32 shape
    (first character 0-7 by construction).
    """
    value = int.from_bytes(
        hashlib.sha256(f"astrid-conformance-ulid:{key}".encode()).digest()[:16],
        "big",
    )
    chars = ["0"] * 26
    for index in range(25, -1, -1):
        chars[index] = "0123456789abcdefghjkmnpqrstvwxyz"[value & 0x1F]
        value >>= 5
    return "".join(chars)


def standard_command_specs(
    ctx: ConformanceContext, *, include_kernel: bool = False
) -> dict[str, CommandSpec]:
    """Register the implemented timeline commands and (opt-in) kernel specs.

    m1 implements ``timeline.create`` and ``timeline.save``; the kit's
    executable set is exactly these two pack commands by default. m2
    (T24_impl) registers the kernel ``core.task.create`` and
    ``core.media.import`` specs alongside them when *include_kernel* is
    true — the proof task flips the flag once the enumerating tests are
    extended. The declared-but-unimplemented ``shot.add_item`` /
    ``reference.set_primary`` commands are never registered (their packs
    ship ``repositories: []``).
    """

    def _timeline_create_invoke(
        context: ConformanceContext,
        uow: UnitOfWork,
        *,
        project_id: str,
        key: str,
    ) -> Any:
        return context.timelines.create(
            uow,
            project_id=project_id,
            slug=f"main-{_slug_suffix(key)}",
            name=f"Timeline {key}",
            config={"fps": 24, "nested": {"scene": key}},
            registry={"assets": {"hero": {"path": "hero.png", "kind": "image"}}},
            idempotency_key=key,
            timeline_id=_stable_timeline_id(key),
            timeline_ulid=_stable_timeline_ulid(key),
            created_at=TS,
        )

    def _timeline_create_changed(
        context: ConformanceContext,
        uow: UnitOfWork,
        *,
        project_id: str,
        key: str,
    ) -> Any:
        return context.timelines.create(
            uow,
            project_id=project_id,
            slug=f"main-{_slug_suffix(key)}",
            name="Changed name under the same key",
            config={"fps": 30},
            registry={"assets": {}},
            idempotency_key=key,
            timeline_id=_stable_timeline_id(key),
            timeline_ulid=_stable_timeline_ulid(key),
            created_at=TS,
        )

    def _timeline_save_invoke(
        context: ConformanceContext,
        uow: UnitOfWork,
        *,
        project_id: str,
        key: str,
    ) -> Any:
        return context.timelines.save(
            uow,
            project_id=project_id,
            ref=f"main-{_slug_suffix(key)}",
            config={"fps": 30, "nested": {"scene": "saved"}},
            registry={"assets": {"hero": {"path": "hero-v2.png", "kind": "image"}}},
            expected_version=1,
            created_at=TS,
        )

    def _timeline_save_changed(
        context: ConformanceContext,
        uow: UnitOfWork,
        *,
        project_id: str,
        key: str,
    ) -> Any:
        return context.timelines.save(
            uow,
            project_id=project_id,
            ref=f"main-{_slug_suffix(key)}",
            config={"fps": 60, "nested": {"scene": "changed"}},
            registry={"assets": {"hero": {"path": "hero-v3.png", "kind": "image"}}},
            expected_version=1,
            created_at=TS,
        )

    def _timeline_read(
        context: ConformanceContext,
        writer: DatabaseWriter,
        project_id: str,
        ref: str,
    ) -> Any:
        return context.timelines.show(writer, project_id, ref)

    def _timeline_create_seed(
        context: ConformanceContext, writer: DatabaseWriter
    ) -> dict[str, Any]:
        UnitOfWork(writer).run(
            lambda u: context.projects.create(
                u,
                slug="crash-proj",
                name="Crash Project",
                settings={},
                idempotency_key="crash-seed-project",
                project_id="crash-proj",
                created_at=TS,
            )
        )
        return {"project_id": "crash-proj", "ref": None, "key": "crash-create"}

    def _timeline_save_seed(
        context: ConformanceContext, writer: DatabaseWriter
    ) -> dict[str, Any]:
        def _seed(uow: UnitOfWork) -> Any:
            project = context.projects.create(
                uow,
                slug="crash-proj",
                name="Crash Project",
                settings={},
                idempotency_key="crash-seed-project",
                project_id="crash-proj",
                created_at=TS,
            )
            return context.timelines.create(
                uow,
                project_id=project.id,
                slug=f"main-{_slug_suffix('crash-save')}",
                name="Main",
                config={"fps": 24},
                registry={"assets": {}},
                idempotency_key="crash-seed-timeline",
                timeline_id="00000000-0000-4000-8000-000000000001",
                timeline_ulid=_stable_timeline_ulid("crash-seed-timeline"),
                created_at=TS,
            )

        UnitOfWork(writer).run(_seed)
        ref = f"main-{_slug_suffix('crash-save')}"
        return {"project_id": "crash-proj", "ref": ref, "key": "crash-save"}

    def _timeline_create_prepare(
        context: ConformanceContext,
        writer: DatabaseWriter,
        *,
        project_id: str,
        key: str,
    ) -> None:
        """Create needs no per-project pre-state beyond the project row."""

    def _timeline_save_prepare(
        context: ConformanceContext,
        writer: DatabaseWriter,
        *,
        project_id: str,
        key: str,
    ) -> None:
        """A whole-document save needs a timeline at head 1 to target."""

        def _prepare(uow: UnitOfWork) -> None:
            context.timelines.create(
                uow,
                project_id=project_id,
                slug=f"main-{_slug_suffix(key)}",
                name="Main",
                config={"fps": 24},
                registry={"assets": {}},
                idempotency_key=f"prepare-{key}",
                timeline_id=_stable_timeline_id(f"save-{key}"),
                timeline_ulid=_stable_timeline_ulid(f"save-{key}"),
                created_at=TS,
            )

        UnitOfWork(writer).run(_prepare)

    def _is_repository_error(exc: BaseException) -> bool:
        return isinstance(exc, RepositoryError)

    specs: dict[str, CommandSpec] = {
        "timeline.create": CommandSpec(
            command_kind="timeline.create",
            pack_id="timeline",
            stream_type="timeline.timeline",
            event_kinds=("timeline.created", "timeline.saved"),
            invoke=_timeline_create_invoke,
            invoke_changed=_timeline_create_changed,
            read=_timeline_read,
            seed=_timeline_create_seed,
            prepare=_timeline_create_prepare,
            is_expected_mismatch=lambda e: isinstance(e, ReceiptMismatchError),
            mutable_tables=("timelines",),
        ),
        "timeline.save": CommandSpec(
            command_kind="timeline.save",
            pack_id="timeline",
            stream_type="timeline.timeline",
            event_kinds=("timeline.created", "timeline.saved"),
            invoke=_timeline_save_invoke,
            invoke_changed=_timeline_save_changed,
            read=_timeline_read,
            seed=_timeline_save_seed,
            prepare=_timeline_save_prepare,
            is_expected_mismatch=_is_repository_error,
            mutable_tables=("timelines",),
        ),
    }

    # -- m2 kernel command specs (plan step 15, T24_impl) ------------------
    # Registered alongside the timeline specs; opt-in so the m1-era tests
    # that enumerate the exact executable set stay green while the proof
    # task flips ``include_kernel``. All closures are assembled from the
    # injected context repositories — the kit never imports a pack.

    def _stable_kernel_id(key: str, namespace: str) -> str:
        """Deterministic aggregate id for one kit key (stable-ID replay)."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"astrid-conformance-{namespace}:{key}"))

    def _task_create_invoke(
        context: ConformanceContext,
        uow: UnitOfWork,
        *,
        project_id: str,
        key: str,
    ) -> Any:
        return context.tasks.create(
            uow,
            project_id=project_id,
            capability="rendering.timeline_visualize",
            spec={"backend": "rendering.remotion", "composition": "main", "fps": 24},
            input_manifest=["media_1"],
            idempotency_key=key,
            task_id=_stable_kernel_id(key, "task"),
            created_at=TS,
        )

    def _task_create_changed(
        context: ConformanceContext,
        uow: UnitOfWork,
        *,
        project_id: str,
        key: str,
    ) -> Any:
        return context.tasks.create(
            uow,
            project_id=project_id,
            capability="rendering.timeline_visualize",
            spec={"backend": "rendering.remotion", "composition": "changed", "fps": 30},
            input_manifest=["media_1"],
            idempotency_key=key,
            task_id=_stable_kernel_id(key, "task"),
            created_at=TS,
        )

    def _task_read(
        context: ConformanceContext,
        writer: DatabaseWriter,
        project_id: str,
        ref: str,
    ) -> Any:
        # The typed not-found contract: another project cannot address this
        # project's task (no existence leak), so a foreign read raises the
        # same typed error an unknown id raises.
        model = context.tasks.show(writer, ref)
        if model.project_id != project_id:
            from astrid.core.repositories import TaskNotFoundError

            raise TaskNotFoundError(task_id=ref)
        return model

    def _task_create_seed(
        context: ConformanceContext, writer: DatabaseWriter
    ) -> dict[str, Any]:
        UnitOfWork(writer).run(
            lambda u: context.projects.create(
                u,
                slug="crash-proj",
                name="Crash Project",
                settings={},
                idempotency_key="crash-seed-project",
                project_id="crash-proj",
                created_at=TS,
            )
        )
        return {"project_id": "crash-proj", "ref": None, "key": "crash-task-create"}

    def _task_create_prepare(
        context: ConformanceContext,
        writer: DatabaseWriter,
        *,
        project_id: str,
        key: str,
    ) -> None:
        """Task admission needs no per-project pre-state beyond the project."""

    # -- prepared filesystem fixtures (media.import) -----------------------

    _MEDIA_FIXTURE_REL = "fixtures/frame.svg"
    _MEDIA_FIXTURE_CHANGED_REL = "fixtures/changed.svg"
    _MEDIA_FIXTURE_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'/>"
    _MEDIA_FIXTURE_CHANGED_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg' width='2'/>"

    def _media_fixtures(context: ConformanceContext) -> None:
        """Materialize (idempotently) the prepared filesystem fixtures.

        Written under the context's temporary managed root, outside any
        transaction; re-seeding a scratch crash database overwrites the same
        bytes so digests stay stable across iterations.
        """
        root = context.managed_root
        if root is None:
            raise ConformanceError(
                "core.media.import conformance needs a managed_root"
            )
        for rel, payload in (
            (_MEDIA_FIXTURE_REL, _MEDIA_FIXTURE_BYTES),
            (_MEDIA_FIXTURE_CHANGED_REL, _MEDIA_FIXTURE_CHANGED_BYTES),
        ):
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

    def _media_import_invoke(
        context: ConformanceContext,
        uow: UnitOfWork,
        *,
        project_id: str,
        key: str,
    ) -> Any:
        prepared = prepare_media_file(
            context.managed_root / _MEDIA_FIXTURE_REL,
            root=context.managed_root,
        )
        return context.media.import_prepared(
            uow,
            project_id=project_id,
            prepared=prepared,
            idempotency_key=key,
            media_id=_stable_kernel_id(key, "media"),
            created_at=TS,
        )

    def _media_import_changed(
        context: ConformanceContext,
        uow: UnitOfWork,
        *,
        project_id: str,
        key: str,
    ) -> Any:
        prepared = prepare_media_file(
            context.managed_root / _MEDIA_FIXTURE_CHANGED_REL,
            root=context.managed_root,
        )
        return context.media.import_prepared(
            uow,
            project_id=project_id,
            prepared=prepared,
            idempotency_key=key,
            media_id=_stable_kernel_id(key, "media"),
            created_at=TS,
        )

    def _media_read(
        context: ConformanceContext,
        writer: DatabaseWriter,
        project_id: str,
        ref: str,
    ) -> Any:
        model = context.media.show(writer, ref)
        if model.project_id != project_id:
            from astrid.core.repositories import MediaNotFoundError

            raise MediaNotFoundError(media_id=ref)
        return model

    def _media_import_seed(
        context: ConformanceContext, writer: DatabaseWriter
    ) -> dict[str, Any]:
        _media_fixtures(context)
        UnitOfWork(writer).run(
            lambda u: context.projects.create(
                u,
                slug="crash-proj",
                name="Crash Project",
                settings={},
                idempotency_key="crash-seed-project",
                project_id="crash-proj",
                created_at=TS,
            )
        )
        return {"project_id": "crash-proj", "ref": None, "key": "crash-media-import"}

    def _media_import_prepare(
        context: ConformanceContext,
        writer: DatabaseWriter,
        *,
        project_id: str,
        key: str,
    ) -> None:
        """Media import needs the prepared fixture bytes on disk."""
        _media_fixtures(context)

    if include_kernel:
        specs["core.task.create"] = CommandSpec(
            command_kind="core.task.create",
            pack_id="core",
            stream_type="core.task",
            event_kinds=("core.task.created",),
            invoke=_task_create_invoke,
            invoke_changed=_task_create_changed,
            read=_task_read,
            seed=_task_create_seed,
            prepare=_task_create_prepare,
            is_expected_mismatch=lambda e: isinstance(e, ReceiptMismatchError),
            result_ref=lambda model: model.id,
            mutable_tables=("tasks", "task_dependencies"),
            list_other=lambda ctx, writer, project_id: ctx.tasks.list(
                writer, project_id
            ),
        )
        specs["core.media.import"] = CommandSpec(
            command_kind="core.media.import",
            pack_id="core",
            stream_type="core.media",
            event_kinds=("core.media.imported",),
            invoke=_media_import_invoke,
            invoke_changed=_media_import_changed,
            read=_media_read,
            seed=_media_import_seed,
            prepare=_media_import_prepare,
            is_expected_mismatch=lambda e: isinstance(e, ReceiptMismatchError),
            fs_fixtures=_media_fixtures,
            result_ref=lambda model: model.id,
            mutable_tables=("media", "media_locations"),
            list_other=lambda ctx, writer, project_id: ctx.media.list(
                writer, project_id
            ),
        )

    return specs


# ---------------------------------------------------------------------------
# Dimension checks
# ---------------------------------------------------------------------------


def _identical_read_models(first: Any, second: Any) -> bool:
    """Two read models carry identical JSON-safe values."""
    return first.to_dict() == second.to_dict()


def check_replay(
    ctx: ConformanceContext,
    spec: CommandSpec,
    *,
    project_id: str,
    key: str,
) -> ConformanceEvidence:
    """An identical retry returns the stored result with zero new rows."""
    if spec.fs_fixtures is not None:
        spec.fs_fixtures(ctx)
    spec.prepare(ctx, ctx.writer, project_id=project_id, key=key)
    before = ctx.row_counts()
    first = UnitOfWork(ctx.writer).run(
        lambda u: spec.invoke(ctx, u, project_id=project_id, key=key)
    )
    mid = ctx.row_counts()
    second = UnitOfWork(ctx.writer).run(
        lambda u: spec.invoke(ctx, u, project_id=project_id, key=key)
    )
    after = ctx.row_counts()
    if not _identical_read_models(first, second):
        raise ConformanceError(
            f"replay of {spec.command_kind!r} did not return the stored result: "
            f"{second.to_dict()} != {first.to_dict()}"
        )
    if mid != after:
        raise ConformanceError(
            f"replay of {spec.command_kind!r} mutated state: "
            f"before {mid} after {after}"
        )
    # Command-owned mutable tables (T24_impl): the first invoke may only
    # change the declared tables plus the shared plumbing. A command that
    # writes an undeclared kernel table fails conformance here.
    delta = {table for table in mid if mid[table] != before[table]}
    undeclared = delta - _PLUMBING_TABLES - set(spec.mutable_tables or ())
    if undeclared:
        raise ConformanceError(
            f"replay of {spec.command_kind!r} mutated undeclared tables: "
            f"{sorted(undeclared)} (declared mutable: "
            f"{sorted(spec.mutable_tables or ())})"
        )
    return ConformanceEvidence(
        command_kind=spec.command_kind,
        dimension="replay",
        detail={
            "identical_result": True,
            "rows_unchanged": True,
            "mutation_within_declared_tables": True,
        },
    )


def check_mismatch_before_mutation(
    ctx: ConformanceContext,
    spec: CommandSpec,
    *,
    project_id: str,
    key: str,
) -> ConformanceEvidence:
    """A changed request under the same key mutates nothing."""
    if spec.fs_fixtures is not None:
        spec.fs_fixtures(ctx)
    spec.prepare(ctx, ctx.writer, project_id=project_id, key=key)
    UnitOfWork(ctx.writer).run(
        lambda u: spec.invoke(ctx, u, project_id=project_id, key=key)
    )
    before = ctx.row_counts()
    raised: BaseException | None = None
    try:
        UnitOfWork(ctx.writer).run(
            lambda u: spec.invoke_changed(ctx, u, project_id=project_id, key=key)
        )
    except BaseException as exc:  # noqa: BLE001 - classified by the spec
        raised = exc
    after = ctx.row_counts()
    if raised is None:
        raise ConformanceError(
            f"changed request for {spec.command_kind!r} under key {key!r} "
            "did not raise"
        )
    predicate = spec.is_expected_mismatch or (lambda e: isinstance(e, ReceiptMismatchError))
    if not predicate(raised):
        raise ConformanceError(
            f"changed request for {spec.command_kind!r} raised unexpected "
            f"{type(raised).__name__}: {raised}"
        )
    if before != after:
        raise ConformanceError(
            f"mismatch for {spec.command_kind!r} mutated state: "
            f"before {before} after {after}"
        )
    return ConformanceEvidence(
        command_kind=spec.command_kind,
        dimension="mismatch_before_mutation",
        detail={
            "raised": type(raised).__name__,
            "rows_unchanged": True,
        },
    )


def check_same_project(
    ctx: ConformanceContext,
    spec: CommandSpec,
    *,
    project_id: str,
    other_project_id: str,
    key: str,
) -> ConformanceEvidence:
    """Another project can neither address nor mutate this project's data."""
    if spec.fs_fixtures is not None:
        spec.fs_fixtures(ctx)
    spec.prepare(ctx, ctx.writer, project_id=project_id, key=key)
    model = UnitOfWork(ctx.writer).run(
        lambda u: spec.invoke(ctx, u, project_id=project_id, key=key)
    )
    if spec.result_ref is not None:
        ref = spec.result_ref(model)
    else:
        ref = model.slug if hasattr(model, "slug") else model.timeline_id
    before_other = ctx.row_counts()
    if spec.list_other is not None:
        other_rows = list(spec.list_other(ctx, ctx.writer, other_project_id))
    else:
        other_rows = (
            ctx.timelines.list(ctx.writer, other_project_id) if ctx.timelines else []
        )
    raised: BaseException | None = None
    try:
        spec.read(ctx, ctx.writer, other_project_id, ref)
    except BaseException as exc:  # noqa: BLE001 - typed not-found expected
        raised = exc
    after_other = ctx.row_counts()
    if raised is None or not isinstance(raised, RepositoryError):
        raise ConformanceError(
            f"cross-project read of {spec.command_kind!r} aggregate {ref!r} "
            f"in project {other_project_id!r} did not raise a typed "
            f"RepositoryError (got {raised!r})"
        )
    if other_rows:
        raise ConformanceError(
            f"project {other_project_id!r} can see another project's "
            f"aggregates ({len(other_rows)} rows)"
        )
    if before_other != after_other:
        raise ConformanceError(
            f"cross-project read mutated state: before {before_other} "
            f"after {after_other}"
        )
    return ConformanceEvidence(
        command_kind=spec.command_kind,
        dimension="same_project",
        detail={
            "cross_project_read": type(raised).__name__,
            "other_list_empty": True,
            "rows_unchanged": True,
        },
    )


def check_vocabulary(
    ctx: ConformanceContext,
    spec: CommandSpec,
    *,
    executable_kinds: set[str],
) -> ConformanceEvidence:
    """Every registered name is declared; undeclared names are rejected."""
    validate_command_kind(ctx.registry, spec.command_kind)
    validate_stream_type(ctx.registry, spec.stream_type)
    for event_kind in spec.event_kinds:
        validate_event_kind(ctx.registry, event_kind)

    undeclared_failures: list[str] = []
    for kind, guard, error in (
        ("timeline.nonexistent", validate_command_kind, CommandVocabularyError),
        ("timeline.nonexistent.event", validate_event_kind, EventVocabularyError),
        ("timeline.nonexistent.stream", validate_stream_type, StreamVocabularyError),
    ):
        try:
            guard(ctx.registry, kind)
        except error:
            continue
        undeclared_failures.append(f"{kind!r} was accepted by {guard.__name__}")
    if undeclared_failures:
        raise ConformanceError(
            f"vocabulary check for {spec.command_kind!r} failed: "
            + "; ".join(undeclared_failures)
        )

    not_executable = sorted(
        kind for kind in NON_EXECUTABLE_COMMAND_KINDS if kind in executable_kinds
    )
    if not_executable:
        raise ConformanceError(
            f"non-executable commands are registered as executable: "
            f"{not_executable}"
        )
    declared_non_executable = {
        kind: validate_command_kind(ctx.registry, kind)
        for kind in NON_EXECUTABLE_COMMAND_KINDS
    }
    return ConformanceEvidence(
        command_kind=spec.command_kind,
        dimension="vocabulary",
        detail={
            "declared": True,
            "undeclared_rejected": True,
            "non_executable_not_registered": sorted(
                declared_non_executable
            ),
        },
    )


def check_writer_ownership(
    ctx: ConformanceContext,
    spec: CommandSpec,
    *,
    project_id: str,
    key: str,
) -> ConformanceEvidence:
    """One writer, one BEGIN IMMEDIATE, separate reads, no escape, FIFO."""
    if spec.fs_fixtures is not None:
        spec.fs_fixtures(ctx)
    spec.prepare(ctx, ctx.writer, project_id=project_id, key=key)
    trace: list[str] = []
    UnitOfWork(
        ctx.writer, on_statement=lambda kind, sql, params: trace.append(kind)
    ).run(lambda u: spec.invoke(ctx, u, project_id=project_id, key=key))
    begins = [k for k in trace if k == "begin_immediate"]
    commits = [k for k in trace if k == "commit"]
    rollbacks = [k for k in trace if k == "rollback"]
    if len(begins) != 1 or len(commits) != 1 or rollbacks:
        raise ConformanceError(
            f"command {spec.command_kind!r} transaction shape is wrong: "
            f"begins={len(begins)} commits={len(commits)} "
            f"rollbacks={len(rollbacks)}"
        )

    writer_conn_id: list[int] = []
    ctx.writer.submit(
        lambda session: writer_conn_id.append(id(session._connection))
    )
    with ctx.writer.read_only_connection() as read_conn:
        read_conn_id = id(read_conn)
    if read_conn_id == writer_conn_id[0]:
        raise ConformanceError(
            f"read for {spec.command_kind!r} shared the writer connection"
        )

    no_escape: list[bool] = []
    ctx.writer.submit(
        lambda session: no_escape.append(not hasattr(session, "connection"))
    )
    if not no_escape or not no_escape[0]:
        raise ConformanceError("WriterSession leaked a public connection")

    intervals: list[tuple[int, int]] = []
    thread_errors: list[BaseException] = []
    lock = threading.Lock()

    def _observed_run(barrier: threading.Barrier) -> None:
        local: list[str] = []
        started: int | None = None
        finished: int | None = None

        def observer(kind: str, sql: str, params: tuple[Any, ...]) -> None:
            nonlocal started, finished
            local.append(kind)
            if kind == "begin_immediate":
                started = time.perf_counter_ns()
            elif kind == "commit":
                finished = time.perf_counter_ns()

        barrier.wait()
        try:
            UnitOfWork(
                ctx.writer, on_statement=observer
            ).run(lambda u: spec.invoke(ctx, u, project_id=project_id, key=key))
        except BaseException as exc:  # noqa: BLE001 - recorded and re-raised
            with lock:
                thread_errors.append(exc)
            raise
        with lock:
            intervals.append((started or 0, finished or 0))

    barrier = threading.Barrier(2)
    threads = [
        threading.Thread(target=_observed_run, args=(barrier,)) for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    if any(thread.is_alive() for thread in threads):
        raise ConformanceError(
            f"concurrent {spec.command_kind!r} callers deadlocked the writer"
        )
    if thread_errors:
        raise ConformanceError(
            f"concurrent {spec.command_kind!r} caller failed: "
            f"{type(thread_errors[0]).__name__}: {thread_errors[0]}"
        )
    if len(intervals) != 2:
        raise ConformanceError(
            f"concurrent {spec.command_kind!r} callers produced "
            f"{len(intervals)} transactions, expected 2"
        )
    first_begin, first_end = intervals[0]
    second_begin, second_end = intervals[1]
    # Intervals are appended in COMPLETION order (the lock is taken at the
    # end of each thread's run), so intervals[0] is not necessarily the
    # first-started transaction. The historical `second_begin < first_end`
    # test false-positives when the first-FINISHED transaction started last
    # (its begin precedes the other's end trivially, with no real overlap).
    # Test true overlap order-independently: both transactions must have
    # begun before the other committed. BEGIN IMMEDIATE serializes writers,
    # so a compliant command never overlaps; a genuine FIFO violation where
    # two write transactions are actually concurrent still trips here.
    if first_begin < second_end and second_begin < first_end:
        raise ConformanceError(
            "concurrent semantic callers obtained overlapping write "
            f"transactions (FIFO serialization violated): intervals "
            f"{intervals}"
        )
    return ConformanceEvidence(
        command_kind=spec.command_kind,
        dimension="writer_ownership",
        detail={
            "exactly_one_begin": True,
            "exactly_one_commit": True,
            "reads_on_separate_connection": True,
            "no_connection_escape": True,
            "concurrent_transactions_serialized": True,
        },
    )


def _snapshot_state(ctx: ConformanceContext, db_path: Path) -> dict[str, Any]:
    """Snapshot row counts plus timeline/project heads on a scratch DB."""
    counts = ctx.table_counts_on(db_path)
    heads: dict[str, int] = {}
    conn = open_database(db_path, ctx.registry, read_only=True)
    try:
        for row in conn.execute(
            "SELECT id, head_seq FROM event_streams ORDER BY id"
        ).fetchall():
            heads[str(row[0])] = int(row[1])
    finally:
        conn.close()
    return {"counts": counts, "heads": heads}


def _integrity_checks_pass(ctx: ConformanceContext, db_path: Path) -> bool:
    """PRAGMA quick_check and foreign_key_check both pass on a scratch DB."""
    conn = open_database(db_path, ctx.registry, read_only=True)
    try:
        quick = conn.execute("PRAGMA quick_check").fetchone()
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conn.close()
    return quick is not None and str(quick[0]) == "ok" and not fk


def check_crash_atomicity(
    ctx: ConformanceContext,
    spec: CommandSpec,
) -> ConformanceEvidence:
    """Statement-boundary old-or-complete behavior on scratch databases.

    Every SQL statement boundary (including pre- and post-commit) is
    crashed in a fresh writer on its own database; the reopened database
    must be exactly the old state (every boundary before commit) or the
    complete committed state (the post-commit boundary) — never a partial
    intermediate — and both integrity PRAGMAs pass on every reopen.
    """
    with tempfile.TemporaryDirectory(prefix="astrid-conformance-crash-") as tmp:
        root = Path(tmp)

        def _seed_and_run_full(db_path: Path) -> list[str]:
            """Seed one scratch DB, run the command fully, return boundaries."""
            boundary_trace: list[str] = []
            seed_writer = DatabaseWriter(db_path, ctx.registry)
            try:
                facts = spec.seed(ctx, seed_writer)
            finally:
                seed_writer.close()
            writer = DatabaseWriter(db_path, ctx.registry)
            try:
                UnitOfWork(
                    writer,
                    on_statement=lambda kind, sql, params: boundary_trace.append(
                        kind
                    ),
                ).run(
                    lambda u: spec.invoke(
                        ctx,
                        u,
                        project_id=facts["project_id"],
                        key=facts["key"],
                    )
                )
            finally:
                writer.close()
            return boundary_trace

        # Learn the exact statement boundaries from one full run.
        learn_path = root / "learn.sqlite3"
        boundaries = _seed_and_run_full(learn_path)
        if not boundaries:
            raise ConformanceError(
                f"full {spec.command_kind!r} run produced no statement "
                "boundaries"
            )
        if "commit" not in boundaries:
            raise ConformanceError(
                f"full {spec.command_kind!r} run never committed"
            )

        # Complete reference state on its own scratch database.
        complete_path = root / "complete.sqlite3"
        complete_boundaries = _seed_and_run_full(complete_path)
        if complete_boundaries != boundaries:
            raise ConformanceError(
                f"full {spec.command_kind!r} run is not deterministic: "
                f"boundaries {boundaries} then {complete_boundaries}"
            )
        complete_state = _snapshot_state(ctx, complete_path)
        if not _integrity_checks_pass(ctx, complete_path):
            raise ConformanceError(
                f"full {spec.command_kind!r} run failed quick/FK checks"
            )

        partials: list[int] = []
        for index in range(len(boundaries)):
            crash_path = root / f"crash-{index}.sqlite3"
            seed_writer = DatabaseWriter(crash_path, ctx.registry)
            try:
                facts = spec.seed(ctx, seed_writer)
            finally:
                seed_writer.close()
            old_state = _snapshot_state(ctx, crash_path)

            crash_writer = DatabaseWriter(crash_path, ctx.registry)
            counter = {"seen": 0}

            def observer(kind: str, sql: str, params: tuple[Any, ...]) -> None:
                if counter["seen"] == index:
                    raise _InjectedCrash(
                        f"injected at boundary {index} ({kind})"
                    )
                counter["seen"] += 1

            try:
                try:
                    UnitOfWork(crash_writer, on_statement=observer).run(
                        lambda u: spec.invoke(
                            ctx,
                            u,
                            project_id=facts["project_id"],
                            key=facts["key"],
                        )
                    )
                except _InjectedCrash:
                    pass
                except BaseException as exc:  # noqa: BLE001
                    raise ConformanceError(
                        f"crash at boundary {index} surfaced unexpected "
                        f"{type(exc).__name__}: {exc}"
                    ) from exc
            finally:
                crash_writer.close()

            state = _snapshot_state(ctx, crash_path)
            is_last = index == len(boundaries) - 1
            if is_last:
                if state != old_state and state != complete_state:
                    partials.append(index)
            elif state != old_state:
                partials.append(index)
            if not _integrity_checks_pass(ctx, crash_path):
                raise ConformanceError(
                    f"crash at boundary {index} left quick/FK failures"
                )

        if partials:
            raise ConformanceError(
                f"crash_atomicity for {spec.command_kind!r} found partial "
                f"states at boundaries {sorted(set(partials))}"
            )
    return ConformanceEvidence(
        command_kind=spec.command_kind,
        dimension="crash_atomicity",
        detail={
            "boundaries_crashed": len(boundaries),
            "old_or_complete_at_every_boundary": True,
            "quick_check_ok": True,
            "foreign_key_check_ok": True,
        },
    )


def check_hash_chain(
    ctx: ConformanceContext,
    spec: CommandSpec,
    *,
    project_id: str,
    key: str,
) -> ConformanceEvidence:
    """Full envelope hash-chain verification passes and tampering fails."""
    if spec.fs_fixtures is not None:
        spec.fs_fixtures(ctx)
    spec.prepare(ctx, ctx.writer, project_id=project_id, key=key)
    model = UnitOfWork(ctx.writer).run(
        lambda u: spec.invoke(ctx, u, project_id=project_id, key=key)
    )
    if ctx.timelines is None and spec.result_ref is None:
        raise ConformanceError("hash_chain needs a timelines repository")
    if spec.result_ref is not None:
        ref = spec.result_ref(model)
    else:
        ref = model.slug if hasattr(model, "slug") else model.timeline_id
    loaded = spec.read(ctx, ctx.writer, project_id, ref)
    if spec.result_ref is not None:
        stream_id = f"{spec.result_ref(loaded)}:{spec.stream_type}"
    else:
        stream_id = f"{loaded.timeline_id}:{spec.stream_type}"
    verification = ctx.events.verify_stream(ctx.writer, stream_id)
    if verification.event_count != verification.head_seq:
        raise ConformanceError(
            f"hash chain for {spec.command_kind!r}: event_count "
            f"{verification.event_count} != head {verification.head_seq}"
        )
    if verification.head_hash is None:
        raise ConformanceError(
            f"hash chain for {spec.command_kind!r} has no head hash"
        )

    original: dict[str, Any] = {}

    def _tamper() -> None:
        def _mutate(session: WriterSession) -> None:
            row = session.query_one(
                "SELECT payload_json FROM events WHERE stream_id = ? "
                "ORDER BY seq ASC LIMIT 1",
                (stream_id,),
            )
            if row is None:
                raise ConformanceError("hash_chain tamper found no events")
            original["payload"] = str(row["payload_json"])
            payload = {
                "data": {"tampered": True},
                "_integrity": {"previous_event_hash": None, "event_hash": "0" * 64},
            }

            session.execute(
                "UPDATE events SET payload_json = ? WHERE stream_id = ? "
                "AND seq = 1",
                (json.dumps(payload, sort_keys=True), stream_id),
            )

        ctx.writer.submit(_mutate)

    _tamper()
    tamper_rejected = False
    try:
        ctx.events.verify_stream(ctx.writer, stream_id)
    except EventChainError:
        tamper_rejected = True
    if not tamper_rejected:
        raise ConformanceError(
            f"tampered {spec.command_kind!r} stream still verified (NSA-2)"
        )

    def _restore() -> None:
        ctx.writer.submit(
            lambda session: session.execute(
                "UPDATE events SET payload_json = ? WHERE stream_id = ? "
                "AND seq = 1",
                (original["payload"], stream_id),
            )
        )

    _restore()
    restored = ctx.events.verify_stream(ctx.writer, stream_id)
    if restored.head_hash != verification.head_hash:
        raise ConformanceError(
            "hash chain did not restore after undoing the tamper"
        )
    return ConformanceEvidence(
        command_kind=spec.command_kind,
        dimension="hash_chain",
        detail={
            "event_count": verification.event_count,
            "head_seq": verification.head_seq,
            "tampering_rejected": True,
            "restored_after_undo": True,
        },
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_all(
    ctx: ConformanceContext,
    spec: CommandSpec,
    *,
    key: str = "conformance",
) -> ConformanceReport:
    """Run every dimension for one command and report per-dimension evidence.

    Each dimension gets its own project (and key) so evidence never
    interferes; ``crash_atomicity`` runs on its own scratch database.
    Raises :class:`ConformanceError` listing every failed dimension.
    """
    report = ConformanceReport(command_kind=spec.command_kind)
    failures: list[str] = []

    def _record(dimension: str, fn: Callable[[], ConformanceEvidence]) -> None:
        try:
            report.add(dimension, fn().detail)
        except ConformanceError as exc:
            failures.append(f"{dimension}: {exc}")

    slug_suffix = _slug_suffix(spec.command_kind)
    project_a = ctx.create_project(
        slug=f"conform-a-{slug_suffix}",
        key=f"{key}-project-a",
        name="Conformance A",
    )
    project_b = ctx.create_project(
        slug=f"conform-b-{slug_suffix}",
        key=f"{key}-project-b",
        name="Conformance B",
    )

    _record(
        "replay",
        lambda: check_replay(
            ctx, spec, project_id=project_a.id, key=f"{key}-replay"
        ),
    )
    _record(
        "mismatch_before_mutation",
        lambda: check_mismatch_before_mutation(
            ctx, spec, project_id=project_a.id, key=f"{key}-mismatch"
        ),
    )
    _record(
        "same_project",
        lambda: check_same_project(
            ctx,
            spec,
            project_id=project_a.id,
            other_project_id=project_b.id,
            key=f"{key}-same-project",
        ),
    )
    _record(
        "vocabulary",
        lambda: check_vocabulary(
            ctx,
            spec,
            executable_kinds=set(standard_command_specs(ctx, include_kernel=True)),
        ),
    )
    _record(
        "writer_ownership",
        lambda: check_writer_ownership(
            ctx, spec, project_id=project_a.id, key=f"{key}-writer"
        ),
    )
    _record("crash_atomicity", lambda: check_crash_atomicity(ctx, spec))
    _record(
        "hash_chain",
        lambda: check_hash_chain(
            ctx, spec, project_id=project_a.id, key=f"{key}-hash"
        ),
    )

    if failures:
        raise ConformanceError(
            f"conformance failed for {spec.command_kind!r}: "
            + "; ".join(failures),
            failures=failures,
        )
    return report


__all__ = [
    "CONFORMANCE_DIMENSIONS",
    "CommandSpec",
    "ConformanceContext",
    "ConformanceError",
    "ConformanceEvidence",
    "ConformanceReport",
    "NON_EXECUTABLE_COMMAND_KINDS",
    "TS",
    "check_crash_atomicity",
    "check_hash_chain",
    "check_mismatch_before_mutation",
    "check_replay",
    "check_same_project",
    "check_vocabulary",
    "check_writer_ownership",
    "run_all",
    "standard_command_specs",
]
