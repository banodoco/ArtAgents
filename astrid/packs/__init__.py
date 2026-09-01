"""Bundled canonical pack composition and bridge construction.

The bundled catalog is the only database ownership authority. This module
provides operation-scoped catalog/registry composition and the single writer
and bridge seams.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from astrid.core.backup.operations import recover_restore_staging
from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.io.media_import import (
    MediaPreparationError,
    StagingGcResult,
    gc_unreferenced_staging,
    validate_txn_id,
)
from astrid.core.pack.canonical import (
    BundledCatalog,
    CanonicalPackValidationError,
    project_catalog_database,
)
from astrid.core.events.service import EventAppendService
from astrid.core.receipts import ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry
from astrid.core.store.ownership import DatabaseOwnerLock, OwnerLockError
from astrid.core.store.writer import DatabaseWriter
from astrid.sdk.exceptions import ServiceUnavailableError
from astrid.packs.timeline.bridge import TimelineBridgeAdapter
from astrid.packs.timeline.repository import TimelineRepository
from astrid.sdk.projects import ProjectsService

@dataclass(frozen=True, slots=True)
class StandardPackComposition:
    """One operation-owned immutable catalog and database projection."""

    catalog: BundledCatalog
    registry: FrozenSchemaPackRegistry


def compose_standard_pack_database(
    *,
    catalog: BundledCatalog | None = None,
    registry: FrozenSchemaPackRegistry | None = None,
    additional_pack_ids: Sequence[str] = (),
) -> StandardPackComposition:
    """Compose the standard bundled catalog and its typed database projection.

    The pair is intentionally operation-scoped: callers retain it for the
    operation lifetime and pass the exact frozen registry to their writer and
    typed consumers.  No process-global cache or service locator is involved.
    An injected registry is retained verbatim, which permits focused
    compositions such as an explicitly selected ``runaway`` projection.
    """
    if catalog is None:
        from astrid.core.pack.loader import DEFAULT_PACKS_ROOT

        catalog = BundledCatalog.from_root(DEFAULT_PACKS_ROOT)
    if not isinstance(catalog, BundledCatalog):
        raise CanonicalPackValidationError("catalog must be a BundledCatalog")
    if registry is None:
        registry = project_catalog_database(catalog, additional_pack_ids)
    elif additional_pack_ids:
        raise CanonicalPackValidationError(
            "additional_pack_ids cannot be combined with an injected registry"
        )
    if not isinstance(registry, FrozenSchemaPackRegistry):
        raise CanonicalPackValidationError(
            "registry must be a FrozenSchemaPackRegistry"
        )
    return StandardPackComposition(catalog=catalog, registry=registry)


LIVE_ATTEMPT_STAGING_KEY = "staging_txn_id"
"""Reserved ``execution_attempts.progress_json`` key holding the staging txn id.

The frozen v10 DDL has no staging column, so the executor records the
per-transaction staging id of a live attempt inside its ``progress_json``
under this key. Startup GC reads it to distinguish live-attempt staging
directories from orphaned ones.
"""

LIVE_ATTEMPT_STATUSES: tuple[str, ...] = ("claimed", "running")
"""The attempt statuses that own a live staging directory (lease held)."""



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
        registry = compose_standard_pack_database().registry
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


@dataclass(frozen=True, slots=True)
class StandardBridgeComposition:
    """Everything the gateway serve root constructed for the bridge."""

    projects_root: Path
    database_path: Path
    catalog: BundledCatalog
    registry: FrozenSchemaPackRegistry
    writer: DatabaseWriter
    projects: ProjectRepository
    timelines: TimelineRepository
    bridge: TimelineBridgeAdapter
    owner_lock: DatabaseOwnerLock
    """The exclusive-owner lock held for the composition's lifetime."""

    def close(self) -> None:
        """Close the writer, then release the owner lock.

        Mirrors ``CoreApplication.close``: the lock is released only after
        the writer is closed, so a second owner can never acquire the
        database while this process still holds an open writer. Both steps
        are idempotent, so a double ``close()`` is safe.
        """
        self.writer.close()
        if self.owner_lock is not None:
            self.owner_lock.release()

def compose_standard_bridge(
    projects_root: str | Path | None = None,
    *,
    catalog: BundledCatalog | None = None,
    registry: FrozenSchemaPackRegistry | None = None,
    additional_pack_ids: Sequence[str] = (),
) -> StandardBridgeComposition:
    """Construct the bridge over one operation-owned catalog/registry pair.

    The pair is composed once (or retained from explicit injection), then the
    exact frozen registry is passed to restore-adjacent writer startup, events,
    repositories, services, and bridge construction.  Default selection is
    core plus timeline, shots, and references; ``additional_pack_ids`` supports
    explicit projections such as ``("runaway",)``.

    Resolves the projects root (argument, ``ASTRID_PROJECTS_ROOT``, or the
    default), derives ``${root}/.astrid/astrid.sqlite3``, recovers restore
    staging before the writer opens, acquires the exclusive-owner lock, and
    constructs one writable ``DatabaseWriter``. The caller owns the returned
    composition lifecycle.
    """
    root = resolve_projects_root(projects_root)
    pack_composition = compose_standard_pack_database(
        catalog=catalog,
        registry=registry,
        additional_pack_ids=additional_pack_ids,
    )
    catalog = pack_composition.catalog
    registry = pack_composition.registry
    # Restore recovery is a read-before-write filesystem decision. It must
    # resolve any journal left by a hard-dead restore before the database
    # writer can open and observe a mixed database/media pair.
    recover_restore_staging(root, registry=registry)
    database_path = derive_database_path(root)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive-owner lock (SD3-m4): acquired before any writable connection
    # or writer queue can open, exactly like compose_standard_application,
    # so a second writer for the same database fails closed with the typed
    # unavailable contract instead of silently coexisting.
    try:
        owner_lock = DatabaseOwnerLock(database_path)
    except OwnerLockError as exc:
        raise ServiceUnavailableError(
            "the canonical store is owned by another Astrid process. When "
            "astrid serve is running, its bridge owns the store: use GET "
            "/routes and its HTTP routes while it is running, or wait for a "
            "clean shutdown. "
            "Reads may retry after release. For writes, preserve the exact "
            "payload and idempotency key, retry after release, and verify "
            "state.",
            details={
                "reason": "store_owned",
                "retryable": True,
            },
        ) from exc
    writer: DatabaseWriter | None = None
    try:
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
        # The bridge adapter is composed over the **typed SDK services**
        # (m4 plan step 20, task T21) — the same project/timeline services the
        # standard application wires for SDK/CLI consumers, over the one shared
        # writer queue. The adapter holds no SQL and never opens a writer of
        # its own; it supplies the hidden deterministic bridge save key through
        # the service's caller-key slot.
        from astrid.sdk.timelines import TimelinesService  # lazy: pack-owned (m4)

        projects_service = ProjectsService(
            writer, projects, receipts, projects_root=root
        )
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
            catalog=catalog,
            registry=registry,
            writer=writer,
            projects=projects,
            timelines=timelines,
            bridge=bridge,
            owner_lock=owner_lock,
        )
    except BaseException:
        if writer is not None:
            writer.close()
        owner_lock.release()
        raise


__all__: list[str] = [
    "BundledCatalog",
    "FrozenSchemaPackRegistry",
    "LIVE_ATTEMPT_STAGING_KEY",
    "LIVE_ATTEMPT_STATUSES",
    "StandardBridgeComposition",
    "StandardPackComposition",
    "collect_live_staging_txn_ids",
    "compose_standard_bridge",
    "compose_standard_pack_database",
    "open_standard_writer",
    "run_startup_staging_gc",
]
