"""Astrid pack content and the explicit standard-Astrid schema-pack composition.

(m1 plan step 2.) :func:`register_standard_schema_packs` is the single explicit
composition function: it registers exactly the three in-tree schema packs
(timeline, shots, references) through ``register_pack()``. There is no dynamic
discovery, no install/uninstall path, and no reuse of the capability-pack
loader or definition machinery (v10 section 2 "Boundary now, loader later";
decision artifact section 4).

Core vocabulary is registered independently by
``astrid.core.events.registry.register_core_vocabulary``; this module registers
only the three shipped packs. ``astrid.core.gateway.dispatch`` is the single
application-composition boundary allowed to import this standard composition.

(m1 plan step 18.) :func:`compose_standard_bridge` is the standard
repository-backed bridge composition: standard registry + one
``DatabaseWriter`` over ``${ASTRID_PROJECTS_ROOT}/.astrid/astrid.sqlite3`` +
the kernel services + the project/timeline repositories + the timeline bridge
adapter. It is invoked **only** at the gateway serve composition root
(``astrid.core.gateway.dispatch._dispatch_serve``); constructing the database
or the registered packs anywhere else is an architecture violation, and there
is no legacy file/JSONL/FSA/Supabase authority fallback.

(m2 plan step 3/4.) :func:`compose_standard_bridge` additionally runs the
startup selective staging GC through the **single** already-constructed
``DatabaseWriter``: :func:`collect_live_staging_txn_ids` reads the
``execution_attempts`` rows that are live (``claimed``/``running``) on the
writer's read-only connection and extracts each attempt's reserved
``staging_txn_id`` from ``progress_json``, then
:func:`run_startup_staging_gc` calls the pure filesystem
``gc_unreferenced_staging`` so only staging directories unreferenced by live
attempts are removed. No second writer, no new write authority, and the
managed ``media/sha256`` digest tree is never touched (SD5).

(BC3 ops-lens gap 1.) :func:`compose_standard_bridge` also starts the daemon
:class:`LeaseExpirySweeper`: a background thread that, on a fixed tick,
enumerates projects read-only and submits one receipt-protected
``core.task.expire`` command per project through the single shared writer
queue so a crashed executor's expired lease is transitioned (attempt
``expired``, task requeued or failed terminally) instead of wedging forever.
It stops cleanly when the writer closes or :meth:`LeaseExpirySweeper.stop`
is called at the serve composition root.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

from astrid.core.backup.operations import recover_restore_staging
from astrid.core.model_setup.journal import resolve_boot_state as _replay_setup_journal
from astrid.core.events.registry import register_core_vocabulary
from astrid.core.events.service import EventAppendService
from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.io.media_import import (
    MediaPreparationError,
    StagingGcResult,
    gc_unreferenced_staging,
    validate_txn_id,
)
from astrid.core.receipts import ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.repositories.tasks import TaskRepository
from astrid.core.schema_packs.manifest import load_schema_pack_manifest
from astrid.core.schema_packs.registry import (
    FrozenSchemaPackRegistry,
    SchemaPackRegistry,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter, WriterShutdownError
from astrid.packs.timeline.bridge import TimelineBridgeAdapter
from astrid.packs.timeline.repository import TimelineRepository
from astrid.sdk.projects import ProjectsService

STANDARD_SCHEMA_PACKS: tuple[str, ...] = ("timeline", "shots", "references")
"""Exactly the in-tree schema packs the standard composition registers.

The literal tuple is required by the deterministic pack-factoring surgery
(``scripts/reshape/check_pack_factoring.py`` patches this exact literal in
temporary copies), so it must stay defined here verbatim.
"""

LIVE_ATTEMPT_STAGING_KEY = "staging_txn_id"
"""Reserved ``execution_attempts.progress_json`` key holding the staging txn id.

The frozen v10 DDL has no staging column, so the executor records the
per-transaction staging id of a live attempt inside its ``progress_json``
under this key. Startup GC reads it to distinguish live-attempt staging
directories from orphaned ones.
"""

LIVE_ATTEMPT_STATUSES: tuple[str, ...] = ("claimed", "running")
"""The attempt statuses that own a live staging directory (lease held)."""

_PACKS_ROOT = Path(__file__).parent


def register_standard_schema_packs(registry: SchemaPackRegistry) -> SchemaPackRegistry:
    """Register exactly timeline, shots, and references into ``registry``.

    Each manifest is loaded from its in-tree ``schema-pack.yaml`` and passed to
    the immutable registry's ``register_pack()``. Nothing is discovered and the
    capability-pack loader is never consulted; core vocabulary must already be
    registered (or be registered separately) for a complete standard registry.
    """
    for pack_id in STANDARD_SCHEMA_PACKS:
        manifest = load_schema_pack_manifest(_PACKS_ROOT / pack_id / "schema-pack.yaml")
        registry.register_pack(manifest)
    return registry


def build_standard_registry() -> FrozenSchemaPackRegistry:
    """Compose and freeze the standard-Astrid registry (core + three packs)."""
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    return registry.freeze()


def open_standard_writer(
    database_path: str | Path,
    *,
    registry: FrozenSchemaPackRegistry | None = None,
) -> DatabaseWriter:
    """Open the single standard-Astrid database writer at ``database_path``.

    This is the one writer-construction seam for the standard application
    composition (``astrid.application.compose_standard_application``): it
    keeps :mod:`astrid.packs` the single place that constructs the standard
    database/writer (authority lint), returns exactly one
    :class:`DatabaseWriter` (the single write queue), and never opens a
    second writer or a legacy authority. The parent directory must already
    exist; the caller owns the writer lifecycle (``close()`` on shutdown).
    """
    if registry is None:
        registry = build_standard_registry()
    return DatabaseWriter(database_path, registry)


def collect_live_staging_txn_ids(writer: DatabaseWriter) -> set[str]:
    """Return the staging transaction ids referenced by live attempts.

    Reads ``execution_attempts`` rows whose status is ``claimed`` or
    ``running`` — the lease-holding live states — through the caller's
    **single** writer using the transaction-free read-only connection. No
    second writer, no write transaction, and no new authority is opened
    (m2 plan step 3/4; v10 section 2.3 single-writer rule).

    For each row the reserved :data:`LIVE_ATTEMPT_STAGING_KEY` value of
    ``progress_json`` is extracted when present. Values that are not valid
    kernel transaction ids are skipped: startup GC is best-effort cleanup,
    so a corrupt progress entry must never block composition.
    """
    live: set[str] = set()
    with writer.read_only_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT progress_json FROM execution_attempts "
            "WHERE status IN ('claimed', 'running')"
        ).fetchall()
    for row in rows:
        try:
            progress = json.loads(str(row["progress_json"] or "{}"))
        except ValueError:
            continue
        if not isinstance(progress, dict):
            continue
        value = progress.get(LIVE_ATTEMPT_STAGING_KEY)
        if not isinstance(value, str) or not value:
            continue
        try:
            live.add(validate_txn_id(value))
        except MediaPreparationError:
            continue
    return live


def run_startup_staging_gc(
    projects_root: str | Path,
    writer: DatabaseWriter,
) -> StagingGcResult:
    """Run the selective startup staging GC through the standard composition.

    Collects the live-attempt staging references through *writer* (the single
    database writer, never a second authority) and removes every
    ``.astrid/media/.staging/<txn_id>`` directory whose transaction id is not
    referenced by a live attempt. Managed digest bytes under
    ``media/sha256`` are never touched (SD5), and a missing staging root is a
    no-op. Returns the typed :class:`StagingGcResult` outcome.
    """
    live_txn_ids = collect_live_staging_txn_ids(writer)
    return gc_unreferenced_staging(projects_root, live_txn_ids)


DEFAULT_LEASE_SWEEP_INTERVAL_SECONDS = 15.0
"""Seconds between lease-expiry sweeps (the crashed-executor recovery tick)."""


class LeaseExpirySweeper:
    """Daemon background thread that expires overdue attempt leases.

    A crashed executor leaves its attempt live forever: heartbeat rejects an
    already-expired lease without transitioning it, and the retry predicates
    require a prior expired attempt — a dead end until something expires the
    attempt. This sweeper closes that wedge by driving
    :meth:`TaskRepository.expire_overdue` through the single shared writer
    queue with one fresh ULID idempotency key per project per sweep (the
    expiry request hash is empty, so a repeated key would replay the stored
    receipt instead of sweeping again).

    Projects are enumerated read-only on a separate read-only connection;
    only the expiry commands themselves enter the writer FIFO. The thread is
    a daemon: it stops cleanly when :meth:`stop` is called or when the writer
    closes (the next submission raises ``WriterShutdownError``).
    """

    def __init__(
        self,
        writer: DatabaseWriter,
        tasks: TaskRepository,
        *,
        interval_seconds: float = DEFAULT_LEASE_SWEEP_INTERVAL_SECONDS,
    ) -> None:
        self._writer = writer
        self._tasks = tasks
        self._interval_seconds = interval_seconds
        self._stop_requested = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="astrid-lease-expiry-sweeper",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal stop and join the sweep thread (idempotent)."""
        self._stop_requested.set()
        if self._thread.is_alive():
            self._thread.join()

    def _run(self) -> None:
        while not self._stop_requested.wait(self._interval_seconds):
            if not self._sweep_once():
                return

    def _sweep_once(self) -> bool:
        """Run one full sweep; return ``False`` only after writer close."""
        try:
            with self._writer.read_only_connection() as connection:
                rows = connection.execute(
                    "SELECT id FROM projects ORDER BY slug ASC"
                ).fetchall()
        except sqlite3.Error:
            # Transient read failure (e.g. mid-checkpoint); retry next tick.
            return True
        for row in rows:
            project_id = str(row[0])
            key = generate_lowercase_ulid()
            try:
                UnitOfWork(self._writer).run(
                    lambda uow, project_id=project_id, key=key: (
                        self._tasks.expire_overdue(
                            uow, project_id=project_id, idempotency_key=key
                        )
                    )
                )
            except WriterShutdownError:
                return False
            except Exception:  # noqa: BLE001 - best-effort per project
                continue
        return True


@dataclass(frozen=True, slots=True)
class StandardBridgeComposition:
    """Everything the gateway serve root constructed for the bridge."""

    projects_root: Path
    database_path: Path
    registry: FrozenSchemaPackRegistry
    writer: DatabaseWriter
    projects: ProjectRepository
    timelines: TimelineRepository
    bridge: TimelineBridgeAdapter
    expiry_sweeper: LeaseExpirySweeper


def compose_standard_bridge(
    projects_root: str | Path | None = None,
    *,
    registry: FrozenSchemaPackRegistry | None = None,
) -> StandardBridgeComposition:
    """Construct the standard database and registered packs for the bridge.

    Resolves the projects root (argument, ``ASTRID_PROJECTS_ROOT``, or the
    default), derives ``${root}/.astrid/astrid.sqlite3``, creates the
    managed-data directory, composes the standard registry (unless one is
    injected), opens exactly one ``DatabaseWriter`` (the single write
    authority), wires the kernel services and repositories, constructs the
    typed project/timeline **services** over that one writer, and returns
    the frozen composition whose bridge adapter is backed by those services
    (plan step 20) — the adapter holds no SQL and never opens a writer of
    its own.

    Must be called only from the gateway serve composition root. The caller
    owns the writer lifecycle (``close()`` on shutdown) and the lease-expiry
    sweeper lifecycle (:meth:`LeaseExpirySweeper.stop` before close; the
    sweeper also self-stops on writer shutdown).
    """
    root = resolve_projects_root(projects_root)
    # Restore recovery is a read-before-write filesystem decision. It must
    # resolve any journal left by a hard-dead restore before the database
    # writer can open and observe a mixed database/media pair.
    recover_restore_staging(root)
    # Setup-journal boot replay (B8, doc 27 §6.1): resolve any dangling
    # acquisition transaction BEFORE the database path is derived. The
    # journal is a sidecar replay log, never truth; this completes or
    # resumes interrupted installs from filesystem reality and never
    # creates the product database.
    _replay_setup_journal(root)
    database_path = derive_database_path(root)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if registry is None:
        registry = build_standard_registry()
    writer = DatabaseWriter(database_path, registry)
    # Startup staging GC (m2 plan step 3/4): through the single writer just
    # constructed, collect live-attempt staging references and remove only
    # staging directories no live attempt references. No second writer or
    # write authority is opened; best-effort cleanup never touches the
    # managed digest tree.
    run_startup_staging_gc(root, writer)
    events = EventAppendService(registry)
    receipts = ReceiptService()
    projects = ProjectRepository(events=events, receipts=receipts)
    timelines = TimelineRepository(
        events=events, receipts=receipts, projects=projects
    )
    # Lease-expiry sweeper (BC3 ops-lens gap 1): a crashed executor must not
    # wedge its attempt live forever. The daemon enumerates projects
    # read-only and submits one receipt-protected ``core.task.expire``
    # command per project per tick through the single shared writer queue,
    # with a fresh ULID idempotency key per invocation.
    expiry_sweeper = LeaseExpirySweeper(
        writer, TaskRepository(events=events, receipts=receipts)
    )
    # The bridge adapter is composed over the **typed SDK services**
    # (m4 plan step 20, task T21) — the same project/timeline services the
    # standard application wires for SDK/CLI consumers, over the one shared
    # writer queue. The adapter holds no SQL and never opens a writer of
    # its own; it supplies the hidden deterministic bridge save key through
    # the service's caller-key slot.
    from astrid.sdk.timelines import TimelinesService  # lazy: pack-owned (m4)

    projects_service = ProjectsService(writer, projects, receipts)
    timelines_service = TimelinesService(
        writer, projects, timelines, receipts
    )
    bridge = TimelineBridgeAdapter(
        writer=writer,
        projects=projects_service,
        timelines=timelines_service,
    )
    return StandardBridgeComposition(
        projects_root=root,
        database_path=database_path,
        registry=registry,
        writer=writer,
        projects=projects,
        timelines=timelines,
        bridge=bridge,
        expiry_sweeper=expiry_sweeper,
    )


__all__: list[str] = [
    "DEFAULT_LEASE_SWEEP_INTERVAL_SECONDS",
    "FrozenSchemaPackRegistry",
    "LIVE_ATTEMPT_STAGING_KEY",
    "LIVE_ATTEMPT_STATUSES",
    "LeaseExpirySweeper",
    "STANDARD_SCHEMA_PACKS",
    "SchemaPackRegistry",
    "StandardBridgeComposition",
    "TimelineBridgeAdapter",
    "build_standard_registry",
    "collect_live_staging_txn_ids",
    "compose_standard_bridge",
    "open_standard_writer",
    "register_standard_schema_packs",
    "run_startup_staging_gc",
]
