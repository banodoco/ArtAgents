"""Subprocess crash-boundary atomicity proofs (m1 plan step 16 / CF-C5879C04CD49CE32191D).

The conformance kit (``astrid.core.conformance.kit``) proves crash atomicity
with an **in-process** injected exception at every statement boundary. This
module proves the stronger, timing-sensitive claim: each boundary is crashed
in a **child process** that exits abruptly (``os._exit`` — no Python cleanup,
no connection close, no WAL checkpoint), the WAL database is reopened after
every crash, and the reopened state is exactly the old state or the complete
committed state — never a partial intermediate — with:

- full genesis-to-head hash-chain validity on every reopened database
  (``EventAppendService.verify_stream``, NSA-2);
- ``PRAGMA quick_check`` and ``PRAGMA foreign_key_check`` passing on every
  reopened database;
- observable per-boundary diagnostics: statement index, kind, SQL, the
  child's exit status, and the old/complete verdict.

Two commands are crashed at every boundary:

- ``project.create`` — the kernel project-create command (plan step 11);
- ``timeline.save`` — the whole-document CAS save (plan step 14) seeded at
  head 1, so pre-commit boundaries must preserve the seeded document and
  the post-commit boundary must deliver the saved document.

Each boundary runs against a **fresh copy** of one deterministically seeded
template database, so every crash starts from byte-identical old state. The
child re-derives the boundary from the same statement observer the full run
used, guaranteeing the boundary set is exactly the learned set.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from astrid.core.conformance import (
    CommandSpec,
    ConformanceContext,
    standard_command_specs,
)
from astrid.core.events.registry import register_core_vocabulary
from astrid.core.events.service import EventAppendService
from astrid.core.receipts import ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.schema_packs.registry import SchemaPackRegistry
from astrid.core.store.database import open_database
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs import register_standard_schema_packs
from astrid.packs.timeline.repository import TimelineRepository

TS = "2026-08-15T00:00:00.000000+00:00"
_CRASH_EXIT_CODE = 137
"""The child's ``os._exit`` status; the parent asserts it exactly."""

_REPO_ROOT = Path(__file__).resolve().parents[2]

_SNAPSHOT_TABLES = (
    "projects",
    "event_streams",
    "events",
    "command_receipts",
    "timelines",
    "runs",
    "tasks",
    "task_dependencies",
    "execution_attempts",
    "media",
    "media_locations",
    "media_relations",
    "task_outputs",
    "evidence_items",
)
"""Every mutable kernel table whose row count participates in old/complete
state (m1 tables plus the m2 task/media/run tables, plan step 16)."""


# ---------------------------------------------------------------------------
# Context construction (mirrors tests/v10/test_conformance.py)
# ---------------------------------------------------------------------------


def _build_registry():
    """Compose core + exactly timeline, shots, and references, then freeze."""
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    return registry.freeze()


def _build_context(db_path: Path, *, managed_root: Path | None = None) -> ConformanceContext:
    """Build one fresh standard-Astrid conformance context on *db_path*.

    When *managed_root* is supplied the m2 kernel task/media repositories
    are injected (duck-typed) and the media repo's managed publication
    lands under that root — the prepared filesystem fixtures the
    ``core.media.import`` crash matrix needs.
    """
    registry = _build_registry()
    writer = DatabaseWriter(db_path, registry)
    events = EventAppendService(registry)
    receipts = ReceiptService()
    projects = ProjectRepository(events=events, receipts=receipts)
    timelines = TimelineRepository(
        events=events, receipts=receipts, projects=projects
    )
    tasks = None
    media = None
    if managed_root is not None:
        from astrid.core.repositories.media import MediaRepository
        from astrid.core.repositories.tasks import TaskRepository

        tasks = TaskRepository(events=events, receipts=receipts)
        media = MediaRepository(
            events=events, receipts=receipts, projects_root=managed_root
        )
    return ConformanceContext(
        db_path=db_path,
        writer=writer,
        registry=registry,
        events=events,
        receipts=receipts,
        projects=projects,
        timelines=timelines,
        tasks=tasks,
        media=media,
        managed_root=managed_root,
    )


# ---------------------------------------------------------------------------
# Command specs crashed by this module
# ---------------------------------------------------------------------------


def _project_create_spec() -> CommandSpec:
    """The kernel ``project.create`` command crashed at every boundary."""

    def seed(ctx: ConformanceContext, writer: DatabaseWriter) -> dict[str, Any]:
        # Project create needs no pre-state: the command itself creates the
        # project, its core.project stream, the created event, and the receipt.
        return {"project_id": "", "ref": None, "key": "crash-project-create"}

    def invoke(
        ctx: ConformanceContext,
        uow: UnitOfWork,
        *,
        project_id: str,
        key: str,
    ) -> Any:
        return ctx.projects.create(
            uow,
            slug="crash-proj",
            name="Crash Project",
            settings={},
            idempotency_key=key,
            project_id="crash-proj",
            created_at=TS,
        )

    return CommandSpec(
        command_kind="project.create",
        pack_id="core",
        stream_type="core.project",
        event_kinds=("core.project.created",),
        invoke=invoke,
        invoke_changed=invoke,
        read=lambda ctx, writer, project_id, ref: None,
        seed=seed,
        prepare=lambda ctx, writer, **kw: None,
    )


def _command_spec(
    ctx: ConformanceContext, command_kind: str
) -> CommandSpec:
    """Return the crash spec for one command kind."""
    if command_kind == "project.create":
        return _project_create_spec()
    if command_kind == "timeline.save":
        return standard_command_specs(ctx)["timeline.save"]
    if command_kind == "core.media.import":
        if ctx.managed_root is None:
            raise ValueError("core.media.import needs a managed_root")
        return _media_import_spec(ctx.managed_root)
    if command_kind == "core.task.complete":
        if ctx.managed_root is None:
            raise ValueError("core.task.complete needs a managed_root")
        return _task_complete_spec(ctx.managed_root)
    raise ValueError(f"unknown crash command kind: {command_kind!r}")


_MEDIA_FIXTURE_REL = "fixtures/frame.svg"
_MEDIA_FIXTURE_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'/>"


def _media_import_spec(managed_root: Path) -> CommandSpec:
    """The ``core.media.import`` command crashed at every boundary.

    The prepared filesystem fixture lives under *managed_root* (outside any
    transaction); the import publishes verified bytes, creates the media
    row, the managed location, the ``core.media`` stream, the
    ``core.media.imported`` event, both heads, and one receipt in a single
    caller UoW. A crash after the atomic publish but before COMMIT can
    therefore leave an orphan published digest with no media row — the
    reopen must reuse it, never duplicate it.
    """

    def _fixture() -> None:
        path = managed_root / _MEDIA_FIXTURE_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_MEDIA_FIXTURE_BYTES)

    def seed(ctx: ConformanceContext, writer: DatabaseWriter) -> dict[str, Any]:
        _fixture()
        from astrid.core.store.uow import UnitOfWork

        UnitOfWork(writer).run(
            lambda u: ctx.projects.create(
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

    def invoke(
        ctx: ConformanceContext,
        uow: UnitOfWork,
        *,
        project_id: str,
        key: str,
    ) -> Any:
        from astrid.core.io.media_import import prepare_media_file

        prepared = prepare_media_file(
            managed_root / _MEDIA_FIXTURE_REL, root=managed_root
        )
        return ctx.media.import_prepared(
            uow,
            project_id=project_id,
            prepared=prepared,
            idempotency_key=key,
            media_id="media-crash-probe",
            created_at=TS,
        )

    return CommandSpec(
        command_kind="core.media.import",
        pack_id="core",
        stream_type="core.media",
        event_kinds=("core.media.imported",),
        invoke=invoke,
        invoke_changed=invoke,
        read=lambda ctx, writer, project_id, ref: None,
        seed=seed,
        prepare=lambda ctx, writer, **kw: _fixture(),
    )


# ---------------------------------------------------------------------------
# Task-completion crash spec (m2 plan step 16, T27_impl)
# ---------------------------------------------------------------------------

_CRASH_PROJECT_ID = "crash-proj"
_CRASH_RUN_ID = "crash-run-1"
_CRASH_TASK_ID = "crash-task-complete"
_CRASH_DEPENDENT_ID = "crash-task-dependent"
_CRASH_STAGING_TXN = "cafecafecafecafecafecafecafecafe"
"""Deterministic 32-hex staging txn id for the seeded handler outputs."""
_CRASH_SEED_MEDIA = "media-crash-seed-x"
_CRASH_SEED_REL = "fixtures/seed.svg"
_CRASH_SEED_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'/>crash-seed-x"
_CRASH_MEDIA_A = "media-crash-out-a"
_CRASH_MEDIA_B = "media-crash-out-b"
_CRASH_OUT_A = ("frame.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>crash-out-a")
_CRASH_OUT_B = ("story.md", b"# crash story output b")
_CRASH_SPEC = {"frames": 1, "width": 320, "height": 240}
_CRASH_INPUT_MANIFEST = [{"role": "source", "uri": "crash://seed"}]
_TS2 = "2026-08-15T00:00:01.000000+00:00"


def _task_complete_spec(managed_root: Path) -> CommandSpec:
    """The ``core.task.complete`` command crashed at every boundary.

    Seed: one project, one running run containing the completing task plus
    a blocked hard dependent, a claimed+started attempt (``running``,
    status version 2) whose handler outputs are staged under the attempt's
    live staging directory, one pre-existing media row (the relation
    endpoint), and two prepared outputs (primary result plus a secondary
    output carrying one ``variant_of`` relation from the pre-existing
    media to the primary). Invoke: the fenced completion command
    (:meth:`TaskRepository.complete` — the exact command
    ``ExecutionService.complete`` submits, T19) with the media repo's
    in-UoW primitive, so the learned boundary trace interleaves the media
    filesystem hooks (``staged`` / ``published`` / ``repo.published``)
    with every repository SQL statement across runs, tasks, dependencies,
    attempts, outputs, media, locations, relations, events, heads, and
    receipts.
    """

    def _stage_handler_outputs() -> None:
        from astrid.core.io.media_import import staging_path

        staging_dir = staging_path(managed_root, _CRASH_STAGING_TXN)
        staging_dir.mkdir(parents=True, exist_ok=True)
        (staging_dir / _CRASH_OUT_A[0]).write_bytes(_CRASH_OUT_A[1])
        (staging_dir / _CRASH_OUT_B[0]).write_bytes(_CRASH_OUT_B[1])

    def _write_seed_media_fixture() -> None:
        path = managed_root / _CRASH_SEED_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_CRASH_SEED_BYTES)

    def seed(ctx: ConformanceContext, writer: DatabaseWriter) -> dict[str, Any]:
        from astrid.core.receipts.canonical import canonical_json
        from astrid.core.repositories.runs import RunRepository
        from astrid.core.task_executor.service import STAGING_TXN_ID_KEY

        UnitOfWork(writer).run(
            lambda u: ctx.projects.create(
                u,
                slug=_CRASH_PROJECT_ID,
                name="Crash Project",
                settings={},
                idempotency_key="crash-seed-project",
                project_id=_CRASH_PROJECT_ID,
                created_at=TS,
            )
        )
        runs = RunRepository(events=ctx.events, receipts=ctx.receipts)
        UnitOfWork(writer).run(
            lambda u: runs.create(
                u,
                project_id=_CRASH_PROJECT_ID,
                children=[
                    {
                        "capability": "rendering.timeline_visualize",
                        "spec": dict(_CRASH_SPEC),
                        "input_manifest": list(_CRASH_INPUT_MANIFEST),
                        "task_id": _CRASH_TASK_ID,
                        "priority": 10,
                    },
                    {
                        "capability": "rendering.timeline_visualize",
                        "spec": dict(_CRASH_SPEC),
                        "input_manifest": list(_CRASH_INPUT_MANIFEST),
                        "task_id": _CRASH_DEPENDENT_ID,
                        "dependencies": [
                            {"task_id": _CRASH_TASK_ID, "kind": "hard"}
                        ],
                    },
                ],
                idempotency_key="crash-seed-run",
                run_id=_CRASH_RUN_ID,
                kind="fanout",
                title="Crash Run",
                input={},
                created_at=TS,
            )
        )
        claim = UnitOfWork(writer).run(
            lambda u: ctx.tasks.claim(
                u,
                project_id=_CRASH_PROJECT_ID,
                idempotency_key="crash-seed-claim",
                executor_id="executor-crash",
                now=TS,
            )
        )
        assert claim is not None and claim.task.id == _CRASH_TASK_ID, claim

        def _start_and_stage(u: UnitOfWork) -> Any:
            started = ctx.tasks.start(
                u,
                project_id=_CRASH_PROJECT_ID,
                task_id=_CRASH_TASK_ID,
                attempt_id=claim.attempt.id,
                lease_id=claim.attempt.lease_id,
                expected_status_version=1,
                idempotency_key="crash-seed-start",
                now=TS,
            )
            # Record the handler staging id exactly like the execution
            # service does (runtime state only; the startup GC reads it).
            progress = dict(started.progress)
            progress[STAGING_TXN_ID_KEY] = _CRASH_STAGING_TXN
            progress_json = canonical_json(progress)
            u.execute(
                "UPDATE execution_attempts SET progress_json = ?, "
                "updated_at = ? "
                "WHERE id = ? AND task_id = ? AND status = 'running' "
                "AND status_version = ?",
                (
                    progress_json,
                    TS,
                    claim.attempt.id,
                    _CRASH_TASK_ID,
                    started.status_version,
                ),
            )
            return started

        started = UnitOfWork(writer).run(_start_and_stage)
        _stage_handler_outputs()
        # One pre-existing media row so the completion's relation edge has
        # both endpoints materialized before the command runs.
        _write_seed_media_fixture()
        from astrid.core.io.media_import import prepare_media_file

        prepared_seed = prepare_media_file(
            managed_root / _CRASH_SEED_REL, root=managed_root
        )
        UnitOfWork(writer).run(
            lambda u: ctx.media.import_prepared(
                u,
                project_id=_CRASH_PROJECT_ID,
                prepared=prepared_seed,
                idempotency_key="crash-seed-media",
                media_id=_CRASH_SEED_MEDIA,
                created_at=TS,
            )
        )
        return {
            "project_id": _CRASH_PROJECT_ID,
            "ref": None,
            "key": "crash-task-complete-k",
        }

    def invoke(
        ctx: ConformanceContext,
        uow: UnitOfWork,
        *,
        project_id: str,
        key: str,
    ) -> Any:
        from astrid.core.io.media_import import prepare_media_file, staging_path

        # The seeded copy carries exactly one attempt for the completing
        # task; the completion facts (id/lease/version) are read inside
        # the same transaction the command runs in. A succeeded attempt
        # (replay path) advanced its version at completion, so the receipt
        # gate must see the pre-completion fence value.
        attempt_row = uow.query_one(
            "SELECT * FROM execution_attempts WHERE task_id = ? "
            "ORDER BY id LIMIT 1",
            (_CRASH_TASK_ID,),
        )
        assert attempt_row is not None, "seeded attempt missing"
        status_version = int(attempt_row["status_version"])
        if str(attempt_row["status"]) == "succeeded":
            status_version -= 1

        staging_dir = staging_path(ctx.managed_root, _CRASH_STAGING_TXN)
        out_a = prepare_media_file(
            staging_dir / _CRASH_OUT_A[0], root=staging_dir
        )
        out_b = prepare_media_file(
            staging_dir / _CRASH_OUT_B[0], root=staging_dir
        )
        entries: list[dict[str, Any]] = [
            {
                "ordinal": 0,
                "is_primary": True,
                "role": "result",
                "label": _CRASH_OUT_A[0],
                "path": _CRASH_OUT_A[0],
                "media_id": _CRASH_MEDIA_A,
                "prepared": out_a,
            },
            {
                "ordinal": 1,
                "is_primary": False,
                "role": "output",
                "label": _CRASH_OUT_B[0],
                "path": _CRASH_OUT_B[0],
                "media_id": _CRASH_MEDIA_B,
                "relations": [
                    {
                        "from_media_id": _CRASH_SEED_MEDIA,
                        "to_media_id": _CRASH_MEDIA_A,
                        "kind": "variant_of",
                        "ordinal": 0,
                        "metadata": {"note": "crash-proof"},
                    }
                ],
                "prepared": out_b,
            },
        ]
        return ctx.tasks.complete(
            uow,
            project_id=project_id,
            task_id=_CRASH_TASK_ID,
            attempt_id=str(attempt_row["id"]),
            lease_id=str(attempt_row["lease_id"]),
            expected_status_version=status_version,
            idempotency_key=key,
            outputs=entries,
            media_repo=ctx.media,
            actor_kind="local",
            now=_TS2,
        )

    return CommandSpec(
        command_kind="core.task.complete",
        pack_id="core",
        stream_type="core.task",
        event_kinds=(
            "core.task.completed",
            "core.media.imported",
            "core.media.related",
        ),
        invoke=invoke,
        invoke_changed=invoke,
        read=lambda ctx, writer, project_id, ref: None,
        seed=seed,
        prepare=lambda ctx, writer, **kw: (
            _stage_handler_outputs(),
            _write_seed_media_fixture(),
        ),
    )


# ---------------------------------------------------------------------------
# State snapshot and integrity helpers
# ---------------------------------------------------------------------------


def _snapshot_state(ctx: ConformanceContext, db_path: Path) -> dict[str, Any]:
    """Snapshot row counts, heads, documents, and managed/staging files."""
    conn = open_database(db_path, ctx.registry, read_only=True)
    try:
        counts = {
            table: int(
                conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
            for table in _SNAPSHOT_TABLES
        }
        heads = {
            str(row[0]): int(row[1])
            for row in conn.execute(
                "SELECT id, head_seq FROM event_streams ORDER BY id"
            ).fetchall()
        }
        project_heads = {
            str(row[0]): int(row[1])
            for row in conn.execute(
                "SELECT id, event_head_seq FROM projects ORDER BY id"
            ).fetchall()
        }
        docs = {
            str(row[0]): (str(row[1]), str(row[2]))
            for row in conn.execute(
                "SELECT id, document_json, asset_registry_json "
                "FROM timelines ORDER BY id"
            ).fetchall()
        }
    finally:
        conn.close()
    media_files: dict[str, int] = {}
    staging_files: dict[str, int] = {}
    if ctx.managed_root is not None:
        managed = Path(ctx.managed_root) / ".astrid" / "media"
        for path in sorted(managed.rglob("*")):
            if path.is_file():
                rel = str(path.relative_to(managed))
                if ".staging" in path.parts:
                    staging_files[rel] = path.stat().st_size
                else:
                    media_files[rel] = path.stat().st_size
    return {
        "counts": counts,
        "heads": heads,
        "project_heads": project_heads,
        "docs": docs,
        "media_files": media_files,
        "staging_files": staging_files,
    }


def _integrity_checks_pass(ctx: ConformanceContext, db_path: Path) -> bool:
    """PRAGMA quick_check and foreign_key_check both pass on reopen."""
    conn = open_database(db_path, ctx.registry, read_only=True)
    try:
        quick = conn.execute("PRAGMA quick_check").fetchone()
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conn.close()
    return quick is not None and str(quick[0]) == "ok" and not fk


def _verify_all_stream_chains(
    ctx: ConformanceContext, db_path: Path
) -> list[dict[str, Any]]:
    """Reopen writable (WAL recovery) and verify every stream's hash chain.

    Opening a fresh ``DatabaseWriter`` on a crashed WAL database is the real
    application reopen path: SQLite recovers the WAL, the migration runner
    no-ops on the recorded checksums, and the reader thread verifies each
    stream from genesis through its head with
    :meth:`EventAppendService.verify_stream`.
    """
    writer = DatabaseWriter(db_path, ctx.registry)
    try:
        with writer.read_only_connection() as conn:
            stream_ids = [
                str(row[0])
                for row in conn.execute(
                    "SELECT id FROM event_streams ORDER BY id"
                ).fetchall()
            ]
        verified: list[dict[str, Any]] = []
        for stream_id in stream_ids:
            summary = ctx.events.verify_stream(writer, stream_id)
            verified.append(
                {
                    "stream_id": stream_id,
                    "event_count": summary.event_count,
                    "head_seq": summary.head_seq,
                    "head_hash": summary.head_hash,
                }
            )
        return verified
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Seeding, boundary learning, and crash execution
# ---------------------------------------------------------------------------


def _seed_template(
    registry: Any, spec: CommandSpec, template_path: Path
) -> dict[str, Any]:
    """Seed one clean template database and return the seed facts."""
    ctx = _build_context(template_path)
    try:
        return spec.seed(ctx, ctx.writer)
    finally:
        ctx.writer.close()


def _copy_seed(template_path: Path, dst: Path) -> None:
    """Copy the template database (plus any WAL/SHM residue) to *dst*."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, dst)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{template_path}{suffix}")
        if sidecar.exists():
            shutil.copy2(sidecar, Path(f"{dst}{suffix}"))


def _run_command_trace(
    ctx: ConformanceContext,
    spec: CommandSpec,
    facts: dict[str, Any],
) -> list[tuple[str, str]]:
    """Run the full command once, recording (kind, sql) per boundary.

    For media commands (context with a managed root) the trace additionally
    records the deterministic filesystem hook points (``("hook", point)``)
    in their real interleaved order with the SQL statements, so the crash
    child can terminate at exactly the same unified boundary index.
    """
    trace: list[tuple[str, str]] = []

    def observer(kind: str, sql: str, params: tuple[Any, ...]) -> None:
        trace.append((kind, sql))

    def hook(point: str) -> None:
        trace.append(("hook", point))

    if ctx.managed_root is not None:
        from astrid.core.io.media_import import set_media_crash_hook

        set_media_crash_hook(hook)
    try:
        UnitOfWork(ctx.writer, on_statement=observer).run(
            lambda u: spec.invoke(
                ctx, u, project_id=facts["project_id"], key=facts["key"]
            )
        )
    finally:
        if ctx.managed_root is not None:
            from astrid.core.io.media_import import set_media_crash_hook

            set_media_crash_hook(None)
    return trace


def _crash_child(
    crash_db: Path,
    boundary: int,
    command_kind: str,
    project_id: str,
    key: str,
    managed_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the crash child for one boundary and return its result."""
    argv = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child",
        str(crash_db),
        str(boundary),
        command_kind,
        project_id,
        key,
        str(_REPO_ROOT),
    ]
    if managed_root is not None:
        argv.append(str(managed_root))
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(_REPO_ROOT),
        check=False,
        # The child re-imports this module from its absolute path, so it must
        # be able to resolve `astrid` regardless of the caller's PYTHONPATH
        # (the review runner executes the file with PYTHONPATH unset).
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)},
    )


def _child_main(argv: list[str]) -> int:
    """Child entry: open the copied DB, crash abruptly at one boundary."""
    _db_path = Path(argv[0])
    boundary = int(argv[1])
    command_kind = argv[2]
    project_id = argv[3]
    key = argv[4]
    root = Path(argv[5])
    managed_root = Path(argv[6]) if len(argv) > 6 else None
    sys.path.insert(0, str(root))

    ctx = _build_context(_db_path, managed_root=managed_root)
    spec = _command_spec(ctx, command_kind)
    seen = {"count": 0}

    def _crash_at() -> None:
        if seen["count"] == boundary:
            # Abrupt termination: no Python cleanup, no connection close, no
            # WAL checkpoint — exactly a killed process.
            os._exit(_CRASH_EXIT_CODE)  # noqa: PLR1722 - the point of the test
        seen["count"] += 1

    def observer(kind: str, sql: str, params: tuple[Any, ...]) -> None:
        _crash_at()

    if managed_root is not None:
        # Media commands also expose deterministic filesystem boundaries
        # (staged / published / reused / repo.published); the hook shares
        # the SQL observer's counter so the boundary index is the same
        # unified index the parent learned.
        from astrid.core.io.media_import import set_media_crash_hook

        def hook(point: str) -> None:
            _crash_at()

        set_media_crash_hook(hook)

    try:
        UnitOfWork(ctx.writer, on_statement=observer).run(
            lambda u: spec.invoke(
                ctx, u, project_id=project_id, key=key
            )
        )
    except BaseException:
        # The command failed before reaching the boundary (or the boundary
        # index was out of range); never mask it with a success exit.
        os._exit(2)
    # Every learned boundary is crashed; reaching here means the boundary
    # index was out of range — the parent treats a non-137 exit as a failure.
    os._exit(0)


def _crash_matrix(
    registry: Any,
    spec: CommandSpec,
    tmp: Path,
) -> list[dict[str, Any]]:
    """Run every learned boundary in a child and return per-boundary rows.

    Each row carries observable diagnostics: index, kind, SQL, child exit
    status, the expected verdict (old for every pre-commit boundary, complete
    for the post-commit boundary), and the actual verdict.
    """
    template = tmp / "seed.sqlite3"
    facts = _seed_template(registry, spec, template)

    # Learn the exact boundary set from two full runs (deterministic).
    learned: list[tuple[str, str]] | None = None
    for name in ("learn-1", "learn-2"):
        db = tmp / f"{name}.sqlite3"
        _copy_seed(template, db)
        ctx = _build_context(db)
        try:
            trace = _run_command_trace(ctx, spec, facts)
        finally:
            ctx.writer.close()
        if learned is None:
            learned = trace
        elif trace != learned:
            raise AssertionError(
                f"command {spec.command_kind!r} is not deterministic: "
                f"boundaries {learned} then {trace}"
            )
    assert learned is not None and learned, "learned boundary set is empty"
    if learned[-1][0] != "commit":
        raise AssertionError(
            f"full {spec.command_kind!r} run never committed: {learned}"
        )

    # Complete reference state on its own seeded copy.
    complete_db = tmp / "complete.sqlite3"
    _copy_seed(template, complete_db)
    complete_ctx = _build_context(complete_db)
    try:
        _run_command_trace(complete_ctx, spec, facts)
    finally:
        complete_ctx.writer.close()
    complete_state = _snapshot_state(complete_ctx, complete_db)
    if not _integrity_checks_pass(complete_ctx, complete_db):
        raise AssertionError(
            f"complete {spec.command_kind!r} run failed quick/FK checks"
        )
    complete_chains = _verify_all_stream_chains(complete_ctx, complete_db)

    rows: list[dict[str, Any]] = []
    for index, (kind, sql) in enumerate(learned):
        crash_dir = tmp / f"crash-{index}"
        crash_db = crash_dir / "astrid.sqlite3"
        _copy_seed(template, crash_db)
        old_state = _snapshot_state(complete_ctx, crash_db)
        if not _integrity_checks_pass(complete_ctx, crash_db):
            raise AssertionError(
                f"seed copy for boundary {index} failed quick/FK checks"
            )

        proc = _crash_child(
            crash_db, index, spec.command_kind,
            facts["project_id"], facts["key"],
            managed_root=ctx.managed_root,
        )
        if proc.returncode != _CRASH_EXIT_CODE:
            raise AssertionError(
                f"boundary {index} ({kind}) child exited "
                f"{proc.returncode} instead of {_CRASH_EXIT_CODE}: "
                f"{proc.stdout[-500:]}{proc.stderr[-500:]}"
            )

        reopened = _snapshot_state(complete_ctx, crash_db)
        if not _integrity_checks_pass(complete_ctx, crash_db):
            raise AssertionError(
                f"boundary {index} ({kind}) left quick/FK failures"
            )
        chains = _verify_all_stream_chains(complete_ctx, crash_db)

        is_post_commit = index == len(learned) - 1
        expected = "complete" if is_post_commit else "old"
        if is_post_commit:
            actual = "complete" if reopened == complete_state else "partial"
            if actual != "complete":
                raise AssertionError(
                    f"boundary {index} ({kind}) after COMMIT is not the "
                    f"complete state: {reopened} vs {complete_state}"
                )
        else:
            actual = "old" if reopened == old_state else "partial"
            if actual != "old":
                raise AssertionError(
                    f"boundary {index} ({kind}) left a partial state: "
                    f"{reopened} vs old {old_state}"
                )
        rows.append(
            {
                "index": index,
                "kind": kind,
                "sql": sql,
                "exit": proc.returncode,
                "expected": expected,
                "actual": actual,
                "chains": chains,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Media crash matrix: filesystem + SQL boundaries, reopen integrity, staging
# GC, and orphan-digest reuse (m2 plan step 16, T26_impl)
# ---------------------------------------------------------------------------


def _sql_only(snapshot: dict[str, Any]) -> dict[str, Any]:
    """The SQLite-only portion of a state snapshot (no filesystem)."""
    return {
        key: snapshot[key]
        for key in ("counts", "heads", "project_heads", "docs")
    }


def _media_files_on(managed_root: Path) -> dict[str, int]:
    """Every managed digest file under ``.astrid/media/sha256`` as rel->size."""
    managed = Path(managed_root) / ".astrid" / "media" / "sha256"
    if not managed.is_dir():
        return {}
    return {
        str(path.relative_to(managed)): path.stat().st_size
        for path in sorted(managed.rglob("*"))
        if path.is_file()
    }


def _staging_files_on(managed_root: Path) -> dict[str, int]:
    """Every staged file under ``.astrid/media/.staging`` as rel->size."""
    staging = Path(managed_root) / ".astrid" / "media" / ".staging"
    if not staging.is_dir():
        return {}
    return {
        str(path.relative_to(staging)): path.stat().st_size
        for path in sorted(staging.rglob("*"))
        if path.is_file()
    }


def _verify_media_state(
    ctx: ConformanceContext, db_path: Path, managed_root: Path
) -> dict[str, Any]:
    """Verify every media byte reference and every managed digest file.

    - Every ``media_locations`` row whose realm is ``managed_local`` must
      resolve to a regular file whose bytes hash to the media row's
      ``content_hash`` (missing/mutated detection via ``verify_media_bytes``);
    - Every managed digest file in the sha256 tree must hash to the digest
      its path encodes — whether it is referenced by a media row (the
      complete state) or an orphan left by a pre-commit crash (SD5: safe,
      non-semantic, reusable).
    """
    from astrid.core.io.media_import import verify_media_bytes

    conn = open_database(db_path, ctx.registry, read_only=True)
    try:
        rows = conn.execute(
            "SELECT m.id, m.content_hash, l.realm, l.locator "
            "FROM media m JOIN media_locations l ON l.media_id = m.id "
            "ORDER BY m.id, l.realm, l.locator"
        ).fetchall()
    finally:
        conn.close()
    referenced: list[dict[str, Any]] = []
    for row in rows:
        media_id, content_hash, realm, locator = (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            str(row[3]),
        )
        if realm == "managed_local":
            size = verify_media_bytes(locator, content_hash)  # raises on miss
            referenced.append(
                {
                    "media_id": media_id,
                    "realm": realm,
                    "locator": locator,
                    "verified": True,
                    "byte_size": size,
                }
            )
        else:
            referenced.append(
                {"media_id": media_id, "realm": realm, "locator": locator}
            )
    referenced_hashes = {str(row[1]) for row in rows}
    sha256_root = Path(managed_root) / ".astrid" / "media" / "sha256"
    digests: list[dict[str, Any]] = []
    for rel in sorted(_media_files_on(managed_root)):
        path = sha256_root / rel
        digest = Path(rel).name
        actual_size = verify_media_bytes(path, digest)  # raises on mutation
        digests.append(
            {
                "rel": rel,
                "digest": digest,
                "byte_size": actual_size,
                # Referenced by content_hash (byte identity, SD2), not by
                # stored locator string: a pre-existing media row seeded on
                # the template root legitimately resolves to a different
                # absolute path on each copied run root.
                "status": (
                    "referenced"
                    if digest in referenced_hashes
                    else "orphan"
                ),
            }
        )
    return {"referenced": referenced, "digests": digests}


def _run_startup_staging_gc(managed_root: Path) -> dict[str, Any]:
    """Run the standard selective startup staging GC with no live attempts.

    Returns the staging files before/after the pass plus the GC counts, so
    the test can assert that only unreferenced staging was removed and the
    managed sha256 tree was never touched.
    """
    from astrid.core.io.media_import import gc_unreferenced_staging

    managed_before = _media_files_on(managed_root)
    before = _staging_files_on(managed_root)
    result = gc_unreferenced_staging(managed_root, live_txn_ids=())
    after = _staging_files_on(managed_root)
    return {
        "before": before,
        "removed_directories": result.removed_directories,
        "removed_files": result.removed_files,
        "after": after,
        "managed_before": managed_before,
        "managed_after": _media_files_on(managed_root),
    }


def _prove_orphan_digest_reuse(
    crash_db: Path, crash_root: Path, facts: dict[str, Any]
) -> dict[str, Any]:
    """Re-import on the reopened DB and prove orphan-digest verified reuse.

    SD5: a verified managed digest published before a rollback is safe and
    reusable. Re-running the full import on the crashed database must
    verify the orphan's bytes and reuse them (``reused: true`` in the
    ``core.media.imported`` event payload) — never duplicating the digest
    file. When no orphan exists the import publishes fresh (``reused:
    false``) and the digest file count grows by exactly one.
    """
    ctx = _build_context(crash_db, managed_root=crash_root)
    try:
        spec = _media_import_spec(crash_root)
        before = _media_files_on(crash_root)
        model = UnitOfWork(ctx.writer).run(
            lambda u: spec.invoke(
                ctx, u, project_id=facts["project_id"], key=facts["key"]
            )
        )
        after = _media_files_on(crash_root)
        with ctx.writer.read_only_connection() as conn:
            row = conn.execute(
                "SELECT payload_json FROM events WHERE stream_id = ? "
                "AND kind = 'core.media.imported' ORDER BY seq DESC LIMIT 1",
                (f"{model.id}:core.media",),
            ).fetchone()
        reused = None
        if row is not None:
            payload = json.loads(str(row[0]))
            reused = bool((payload.get("data") or {}).get("reused"))
        return {
            "media_id": model.id,
            "reused": reused,
            "digest_files_before": before,
            "digest_files_after": after,
            "duplicated": after != before,
        }
    finally:
        ctx.writer.close()


def _media_crash_matrix(registry: Any, tmp: Path) -> list[dict[str, Any]]:
    """Crash core.media.import at every SQL + filesystem boundary.

    The media command spans two authorities — the filesystem
    staging/publication pipeline and SQLite — so each run gets its own
    managed root (copied from the seeded template, exactly like the
    database copy), and the learned boundary trace interleaves the
    deterministic hook points with repository SQL statements. Every crash
    reopens to SQL old-or-complete, then the reopened root is checked for
    quick/FK integrity, genesis-to-head chains, media byte references,
    startup staging GC (only unreferenced staging removed), and verified
    reuse of any orphan published digest (SD5).
    """
    template = tmp / "seed.sqlite3"
    template_root = tmp / "seed-managed"
    template_root.mkdir(parents=True, exist_ok=True)
    template_ctx = _build_context(template, managed_root=template_root)
    try:
        facts = _media_import_spec(template_root).seed(
            template_ctx, template_ctx.writer
        )
    finally:
        template_ctx.writer.close()

    def _copy_run(name: str) -> tuple[Path, Path]:
        db = tmp / f"{name}.sqlite3"
        _copy_seed(template, db)
        run_root = tmp / f"{name}-managed"
        shutil.copytree(template_root, run_root)
        return db, run_root

    def _run_full(name: str) -> tuple[list[tuple[str, str]], ConformanceContext]:
        db, run_root = _copy_run(name)
        ctx = _build_context(db, managed_root=run_root)
        try:
            trace = _run_command_trace(ctx, _media_import_spec(run_root), facts)
        finally:
            ctx.writer.close()
        return trace, ctx

    learned: list[tuple[str, str]] | None = None
    for name in ("learn-1", "learn-2"):
        trace, _ctx = _run_full(name)
        if learned is None:
            learned = trace
        elif trace != learned:
            raise AssertionError(
                "core.media.import is not deterministic: "
                f"boundaries {learned} then {trace}"
            )
    assert learned is not None and learned, "learned boundary set is empty"
    if learned[-1][0] != "commit":
        raise AssertionError("full core.media.import run never committed")

    complete_db, complete_root = _copy_run("complete")
    complete_ctx = _build_context(complete_db, managed_root=complete_root)
    try:
        complete_trace = _run_command_trace(
            complete_ctx, _media_import_spec(complete_root), facts
        )
    finally:
        complete_ctx.writer.close()
    if complete_trace != learned:
        raise AssertionError(
            "core.media.import boundary set differs between runs"
        )
    complete_state = _snapshot_state(complete_ctx, complete_db)
    if not _integrity_checks_pass(complete_ctx, complete_db):
        raise AssertionError("complete core.media.import run failed quick/FK")
    complete_chains = _verify_all_stream_chains(complete_ctx, complete_db)
    complete_media = _verify_media_state(
        complete_ctx, complete_db, complete_root
    )
    complete_sql = _sql_only(complete_state)

    rows: list[dict[str, Any]] = []
    for index, (kind, sql) in enumerate(learned):
        crash_db, crash_root = _copy_run(f"crash-{index}")
        crash_ctx = _build_context(crash_db, managed_root=crash_root)
        try:
            old_state = _snapshot_state(crash_ctx, crash_db)
            old_sql = _sql_only(old_state)
        finally:
            crash_ctx.writer.close()
        if not _integrity_checks_pass(crash_ctx, crash_db):
            raise AssertionError(
                f"seed copy for boundary {index} failed quick/FK checks"
            )

        proc = _crash_child(
            crash_db, index, "core.media.import",
            facts["project_id"], facts["key"],
            managed_root=crash_root,
        )
        if proc.returncode != _CRASH_EXIT_CODE:
            raise AssertionError(
                f"boundary {index} ({kind}) child exited "
                f"{proc.returncode} instead of {_CRASH_EXIT_CODE}: "
                f"{proc.stdout[-500:]}{proc.stderr[-500:]}"
            )

        reopen_ctx = _build_context(crash_db, managed_root=crash_root)
        try:
            if not _integrity_checks_pass(reopen_ctx, crash_db):
                raise AssertionError(
                    f"boundary {index} ({kind}) left quick/FK failures"
                )
            chains = _verify_all_stream_chains(reopen_ctx, crash_db)
            media_state = _verify_media_state(
                reopen_ctx, crash_db, crash_root
            )
            staging_gc = _run_startup_staging_gc(crash_root)
            reopened = _snapshot_state(reopen_ctx, crash_db)
        finally:
            reopen_ctx.writer.close()
        reuse = _prove_orphan_digest_reuse(crash_db, crash_root, facts)

        reopened_sql = _sql_only(reopened)
        is_post_commit = index == len(learned) - 1
        expected = "complete" if is_post_commit else "old"
        if is_post_commit:
            actual = (
                "complete"
                if reopened_sql == complete_sql
                and _media_files_on(crash_root)
                == _media_files_on(complete_root)
                else "partial"
            )
            if actual != "complete":
                raise AssertionError(
                    f"boundary {index} ({kind}) after COMMIT is not the "
                    f"complete state: {reopened_sql} vs {complete_sql}"
                )
        else:
            actual = "old" if reopened_sql == old_sql else "partial"
            if actual != "old":
                raise AssertionError(
                    f"boundary {index} ({kind}) left a partial SQL state: "
                    f"{reopened_sql} vs old {old_sql}"
                )
        rows.append(
            {
                "index": index,
                "kind": kind,
                "sql": sql,
                "exit": proc.returncode,
                "expected": expected,
                "actual": actual,
                "chains": chains,
                "media_verified": (
                    all(
                        item["verified"] for item in media_state["referenced"]
                    )
                    and all(
                        item["byte_size"] >= 0
                        for item in media_state["digests"]
                    )
                ),
                "orphan_digests": [
                    item["rel"]
                    for item in media_state["digests"]
                    if item["status"] == "orphan"
                ],
                "staging_gc": staging_gc,
                "reuse": reuse,
            }
        )
    return rows


def _run_startup_gc_with_live(
    ctx: ConformanceContext, managed_root: Path
) -> dict[str, Any]:
    """Run the standard selective startup staging GC with live attempts.

    The completion matrix's seed leaves the completing attempt ``running``
    with a live handler staging quarantine, so the reopen GC must use the
    real startup path — collect live ``staging_txn_id`` references from
    ``execution_attempts`` through the reopened writer and remove only
    unreferenced staging directories (never the managed sha256 tree).
    """
    from astrid.packs import run_startup_staging_gc

    managed_before = _media_files_on(managed_root)
    before = _staging_files_on(managed_root)
    result = run_startup_staging_gc(managed_root, ctx.writer)
    after = _staging_files_on(managed_root)
    live_prefix = f"{_CRASH_STAGING_TXN}/"
    return {
        "before": before,
        "after": after,
        "removed_directories": result.removed_directories,
        "removed_files": result.removed_files,
        "managed_before": managed_before,
        "managed_after": _media_files_on(managed_root),
        # The running attempt's handler quarantine survives every pre-commit
        # crash (its txn id stays live); a committed completion drains it.
        "live_staging_preserved": all(
            rel.startswith(live_prefix) for rel in after
        )
        if after
        else False,
    }


def _prove_completion_rerun(
    crash_db: Path,
    crash_root: Path,
    facts: dict[str, Any],
    complete_sql: dict[str, Any],
    complete_media: dict[str, int],
) -> dict[str, Any]:
    """Re-invoke completion on the reopened DB and prove it converges.

    The reopened database must be exactly old or complete, and a full
    re-completion must converge to the **complete** state: for a pre-commit
    crash the fenced completion re-wins (verified-reusing any orphan
    published digest — SD5 — never duplicating bytes), and for a
    post-commit crash the receipt gate replays the stored result with zero
    new rows. Either way the final SQL state and the managed digest tree
    must equal the complete run's, proving no missing bytes, no partial
    outputs/relations/receipts, and no duplicated digests.
    """
    ctx = _build_context(crash_db, managed_root=crash_root)
    try:
        spec = _task_complete_spec(crash_root)
        # Re-stage the deterministic handler outputs: the reopen GC may
        # already have drained the committed completion's staging (and the
        # live attempt's quarantine), so the re-completion re-creates the
        # exact staged bytes it prepares (idempotent, byte-identical).
        spec.prepare(ctx, ctx.writer)
        before_sql = _sql_only(_snapshot_state(ctx, crash_db))
        before_media = _media_files_on(crash_root)
        # Orphans are digests on disk whose bytes are not referenced by any
        # committed media row — computed BEFORE the rerun, because the rerun
        # (re)completion references them.
        with ctx.writer.read_only_connection() as conn:
            referenced_rows = conn.execute(
                "SELECT DISTINCT content_hash FROM media WHERE project_id = ?",
                (facts["project_id"],),
            ).fetchall()
        referenced_digests = {str(row[0]) for row in referenced_rows}
        orphan_digests = sorted(
            {
                str(Path(rel).name)
                for rel in before_media
                if str(Path(rel).name) not in referenced_digests
            }
        )
        UnitOfWork(ctx.writer).run(
            lambda u: spec.invoke(
                ctx, u, project_id=facts["project_id"], key=facts["key"]
            )
        )
        after_sql = _sql_only(_snapshot_state(ctx, crash_db))
        after_media = _media_files_on(crash_root)
        with ctx.writer.read_only_connection() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM events "
                "WHERE kind = 'core.media.imported' "
                "ORDER BY project_seq ASC"
            ).fetchall()
        reused_by_digest: dict[str, bool] = {}
        for row in rows:
            data = (json.loads(str(row[0])) or {}).get("data") or {}
            if data.get("reused") is not None:
                reused_by_digest[str(data["content_hash"])] = bool(
                    data["reused"]
                )
        return {
            "sql_matches_complete": after_sql == complete_sql,
            "media_matches_complete": after_media == complete_media,
            "zero_new_rows_on_replay": after_sql == before_sql,
            "orphan_digests_before": orphan_digests,
            "reused_orphans": (
                None
                if not orphan_digests
                else all(
                    reused_by_digest.get(digest) is True
                    for digest in orphan_digests
                )
            ),
        }
    finally:
        ctx.writer.close()


def _completion_crash_matrix(registry: Any, tmp: Path) -> list[dict[str, Any]]:
    """Crash core.task.complete at every SQL + filesystem boundary.

    The completion command spans two authorities — the filesystem
    staging/publication pipeline (via the media in-UoW primitive's hooks)
    and SQLite — so each run gets its own managed root (copied from the
    seeded template, exactly like the media matrix), and the learned
    boundary trace interleaves the deterministic hook points with
    repository SQL statements. Every crash reopens to SQL old-or-complete,
    then the reopened root is checked for quick/FK integrity,
    genesis-to-head chains, media byte references, selective startup
    staging GC (the live attempt's handler quarantine preserved, the
    completion's own staging drained), and a full re-completion converging
    to the complete state (orphan digests verified-reused, never
    duplicated).
    """
    template = tmp / "seed.sqlite3"
    template_root = tmp / "seed-managed"
    template_root.mkdir(parents=True, exist_ok=True)
    template_ctx = _build_context(template, managed_root=template_root)
    try:
        facts = _task_complete_spec(template_root).seed(
            template_ctx, template_ctx.writer
        )
    finally:
        template_ctx.writer.close()

    def _copy_run(name: str) -> tuple[Path, Path]:
        db = tmp / f"{name}.sqlite3"
        _copy_seed(template, db)
        run_root = tmp / f"{name}-managed"
        shutil.copytree(template_root, run_root)
        return db, run_root

    def _run_full(name: str) -> tuple[list[tuple[str, str]], ConformanceContext]:
        db, run_root = _copy_run(name)
        ctx = _build_context(db, managed_root=run_root)
        try:
            trace = _run_command_trace(
                ctx, _task_complete_spec(run_root), facts
            )
        finally:
            ctx.writer.close()
        return trace, ctx

    learned: list[tuple[str, str]] | None = None
    for name in ("learn-1", "learn-2"):
        trace, _ctx = _run_full(name)
        if learned is None:
            learned = trace
        elif trace != learned:
            raise AssertionError(
                "core.task.complete is not deterministic: "
                f"boundaries {learned} then {trace}"
            )
    assert learned is not None and learned, "learned boundary set is empty"
    if learned[-1][0] != "commit":
        raise AssertionError("full core.task.complete run never committed")

    complete_db, complete_root = _copy_run("complete")
    complete_ctx = _build_context(complete_db, managed_root=complete_root)
    try:
        complete_trace = _run_command_trace(
            complete_ctx, _task_complete_spec(complete_root), facts
        )
    finally:
        complete_ctx.writer.close()
    if complete_trace != learned:
        raise AssertionError(
            "core.task.complete boundary set differs between runs"
        )
    complete_state = _snapshot_state(complete_ctx, complete_db)
    if not _integrity_checks_pass(complete_ctx, complete_db):
        raise AssertionError("complete core.task.complete run failed quick/FK")
    complete_chains = _verify_all_stream_chains(complete_ctx, complete_db)
    complete_media = _verify_media_state(
        complete_ctx, complete_db, complete_root
    )
    complete_sql = _sql_only(complete_state)
    complete_media_files = _media_files_on(complete_root)

    # Every boundary is an independent fresh copy, so the crash loop runs
    # in a small thread pool (each worker spawns its own crash child and
    # reopens its own database; no shared mutable state) — keeping the
    # subprocess matrix bounded while the harness's test-timeout budget is
    # respected. Rows are collected in learned boundary order.
    def _crash_boundary(index: int, kind: str, sql: str) -> dict[str, Any]:
        crash_db, crash_root = _copy_run(f"crash-{index}")
        crash_ctx = _build_context(crash_db, managed_root=crash_root)
        try:
            old_state = _snapshot_state(crash_ctx, crash_db)
            old_sql = _sql_only(old_state)
        finally:
            crash_ctx.writer.close()
        if not _integrity_checks_pass(crash_ctx, crash_db):
            raise AssertionError(
                f"seed copy for boundary {index} failed quick/FK checks"
            )

        proc = _crash_child(
            crash_db, index, "core.task.complete",
            facts["project_id"], facts["key"],
            managed_root=crash_root,
        )
        if proc.returncode != _CRASH_EXIT_CODE:
            raise AssertionError(
                f"boundary {index} ({kind}) child exited "
                f"{proc.returncode} instead of {_CRASH_EXIT_CODE}: "
                f"{proc.stdout[-500:]}{proc.stderr[-500:]}"
            )

        reopen_ctx = _build_context(crash_db, managed_root=crash_root)
        try:
            if not _integrity_checks_pass(reopen_ctx, crash_db):
                raise AssertionError(
                    f"boundary {index} ({kind}) left quick/FK failures"
                )
            chains = _verify_all_stream_chains(reopen_ctx, crash_db)
            media_state = _verify_media_state(
                reopen_ctx, crash_db, crash_root
            )
            staging_gc = _run_startup_gc_with_live(reopen_ctx, crash_root)
            reopened = _snapshot_state(reopen_ctx, crash_db)
        finally:
            reopen_ctx.writer.close()
        rerun = _prove_completion_rerun(
            crash_db, crash_root, facts, complete_sql, complete_media_files
        )

        reopened_sql = _sql_only(reopened)
        is_post_commit = index == len(learned) - 1
        expected = "complete" if is_post_commit else "old"
        if is_post_commit:
            actual = (
                "complete"
                if reopened_sql == complete_sql
                and _media_files_on(crash_root) == complete_media_files
                else "partial"
            )
            if actual != "complete":
                raise AssertionError(
                    f"boundary {index} ({kind}) after COMMIT is not the "
                    f"complete state: {reopened_sql} vs {complete_sql}"
                )
        else:
            actual = "old" if reopened_sql == old_sql else "partial"
            if actual != "old":
                raise AssertionError(
                    f"boundary {index} ({kind}) left a partial SQL state: "
                    f"{reopened_sql} vs old {old_sql}"
                )
        return {
            "index": index,
            "kind": kind,
            "sql": sql,
            "exit": proc.returncode,
            "expected": expected,
            "actual": actual,
            "chains": chains,
            "media_verified": (
                all(item["verified"] for item in media_state["referenced"])
                and all(
                    item["byte_size"] >= 0
                    for item in media_state["digests"]
                )
            ),
            "orphan_digests": [
                item["rel"]
                for item in media_state["digests"]
                if item["status"] == "orphan"
            ],
            "staging_gc": staging_gc,
            "rerun": rerun,
        }

    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(
            pool.map(
                lambda item: _crash_boundary(item[0], *item[1]),
                enumerate(learned),
            )
        )
    return rows


def _emit_diagnostics(command_kind: str, rows: list[dict[str, Any]]) -> None:
    """Print the observable per-boundary crash matrix for the record."""
    print(
        f"\n[crash_atomicity:{command_kind}] "
        f"{len(rows)} boundaries crashed in child processes",
        flush=True,
    )
    for row in rows:
        extra = ""
        if "rerun" in row:
            extra = (
                f" orphans={len(row['orphan_digests'])} "
                f"gc_removed={row['staging_gc']['removed_directories']} "
                f"live_preserved={row['staging_gc']['live_staging_preserved']} "
                f"rerun_sql={row['rerun']['sql_matches_complete']} "
                f"rerun_media={row['rerun']['media_matches_complete']} "
                f"rerun_reused_orphans={row['rerun']['reused_orphans']}"
            )
        elif "orphan_digests" in row:
            extra = (
                f" orphans={len(row['orphan_digests'])} "
                f"gc_removed={row['staging_gc']['removed_directories']} "
                f"reuse_reused={row['reuse']['reused']} "
                f"reuse_duplicated={row['reuse']['duplicated']}"
            )
        print(
            f"  boundary {row['index']:>2} {row['kind']:<16} "
            f"exit={row['exit']} verdict={row['expected']}->{row['actual']} "
            f"sql={row['sql'][:80]!r}{extra}",
            flush=True,
        )
    print(
        f"[crash_atomicity:{command_kind}] every reopened database passed "
        "quick_check, foreign_key_check, and genesis-to-head chain "
        "verification",
        flush=True,
    )



# ---------------------------------------------------------------------------
# Doc 27 section 5 spike: bytes durable BEFORE BEGIN IMMEDIATE (track K)
# ---------------------------------------------------------------------------
#
# The amendment premise: verified bytes can be made durable in the SHA-256
# tree *before* the writer transaction opens — same-filesystem temp copy
# with file fsync (:func:`stage_prepared_media`), then atomic ``os.replace``
# onto the frozen hash path followed by file and parent-directory fsyncs
# (:func:`publish_staged_media`) — so a process death at any later point,
# including inside ``BEGIN IMMEDIATE``, finds the bytes fully durable or
# absent at the hash path, never partial, while SQLite reopens old or
# complete. This matrix crashes the exact sequence
#
#   stage -> publish -> BEGIN IMMEDIATE -> import statements -> COMMIT
#
# in a child process (``os._exit(137)``) at every unified boundary and
# reopens both authorities after each crash. Ordinary power-loss reordering
# is out of scope here (no test harness can force a power fail); what is
# proven is abrupt-process-death atomicity on this filesystem, the same
# standard every other matrix in this module uses.

_SPIKE_PROJECT_ID = "spike-proj"
_SPIKE_MEDIA_ID = "media-spike-out-a"
_SPIKE_TXN_ID = "dededededededededededededededede"
_SPIKE_REL = "fixtures/spike.svg"
_SPIKE_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'/>track-k-spike"
_SPIKE_KEY = "spike-import-k"


def _write_spike_fixture(managed_root: Path) -> Path:
    """Write the spike's prepared-bytes fixture under the managed root."""
    path = managed_root / _SPIKE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_SPIKE_BYTES)
    return path


def _seed_spike_template(template_path: Path, template_root: Path) -> None:
    """One clean template database holding exactly the spike project."""
    ctx = _build_context(template_path, managed_root=template_root)
    try:
        UnitOfWork(ctx.writer).run(
            lambda u: ctx.projects.create(
                u,
                slug=_SPIKE_PROJECT_ID,
                name="Spike Project",
                settings={},
                idempotency_key="spike-seed-project",
                project_id=_SPIKE_PROJECT_ID,
                created_at=TS,
            )
        )
        _write_spike_fixture(template_root)
    finally:
        ctx.writer.close()


def _run_spike_flow(
    ctx: ConformanceContext,
    *,
    on_boundary: Any = None,
) -> Any:
    """Run the amended section 5 sequence against *ctx*.

    Publication (stage + fsync, then atomic replace + fsyncs) completes
    strictly before the unit of work opens ``BEGIN IMMEDIATE``; the
    optional *on_boundary* callback observes each filesystem hook point
    and SQL statement in real order (the crash child terminates at exactly
    one of them).
    """
    from astrid.core.io.media_import import (
        prepare_media_file,
        publish_staged_media,
        set_media_crash_hook,
        stage_prepared_media,
    )

    fixture = _write_spike_fixture(ctx.managed_root)
    prepared = prepare_media_file(fixture, root=ctx.managed_root)

    if on_boundary is not None:
        set_media_crash_hook(lambda point: on_boundary("hook", point))

    def observer(kind: str, sql: str, params: tuple[Any, ...]) -> None:
        if on_boundary is not None:
            on_boundary(kind, sql)

    try:
        # 1. Outside any transaction: make the bytes durable at the frozen
        #    hash path (temp copy + fsync, atomic rename, dir fsyncs).
        staged = stage_prepared_media(ctx.managed_root, _SPIKE_TXN_ID, prepared)
        published = publish_staged_media(ctx.managed_root, staged)
        assert published.reused is False, published
        # 2. Only now does BEGIN IMMEDIATE open.
        return UnitOfWork(ctx.writer, on_statement=observer).run(
            lambda u: ctx.media.import_prepared(
                u,
                project_id=_SPIKE_PROJECT_ID,
                prepared=prepared,
                idempotency_key=_SPIKE_KEY,
                media_id=_SPIKE_MEDIA_ID,
                created_at=TS,
            )
        )
    finally:
        set_media_crash_hook(None)


def _digest_file_state(managed_root: Path, digest: str, byte_size: int) -> str:
    """Classify the managed digest object: absent/durable/partial/mutated."""
    from astrid.core.io.media_import import (
        managed_media_path,
        sha256_file_bytes,
    )

    path = managed_media_path(managed_root, digest)
    if not path.exists():
        return "absent"
    data = path.read_bytes()
    if len(data) != byte_size:
        return "partial"
    if sha256_file_bytes(path) != digest:
        return "mutated"
    return "durable"


def _spike_child_main(argv: list[str]) -> int:
    """Child entry: re-run the section 5 flow, crash abruptly at one boundary."""
    db_path = Path(argv[0])
    managed_root = Path(argv[1])
    boundary = int(argv[2])
    sys.path.insert(0, str(_REPO_ROOT))

    ctx = _build_context(db_path, managed_root=managed_root)
    seen = {"count": 0}

    def on_boundary(kind: str, label: str) -> None:
        if seen["count"] == boundary:
            os._exit(_CRASH_EXIT_CODE)  # noqa: PLR1722 - the point of the test
        seen["count"] += 1

    try:
        _run_spike_flow(ctx, on_boundary=on_boundary)
    except BaseException:
        # The boundary index was out of range (or the flow failed); never
        # mask it with a success exit.
        os._exit(2)
    os._exit(0)


def _spike_crash_matrix(tmp: Path) -> list[dict[str, Any]]:
    """Crash the pre-lock publication flow at every unified boundary.

    Each row records the SQL verdict (old-or-complete, via the SQLite-only
    snapshot because unreferenced published digests are allowed orphans)
    and the byte verdict for the managed digest object.
    """
    template = tmp / "seed.sqlite3"
    template_root = tmp / "seed-managed"
    template_root.mkdir(parents=True, exist_ok=True)
    _seed_spike_template(template, template_root)

    def _copy_run(name: str) -> tuple[Path, Path]:
        db = tmp / f"{name}.sqlite3"
        _copy_seed(template, db)
        run_root = tmp / f"{name}-managed"
        shutil.copytree(template_root, run_root)
        return db, run_root

    # Learn the boundary set from two deterministic full runs.
    learned: list[tuple[str, str]] | None = None
    for name in ("learn-1", "learn-2"):
        db, run_root = _copy_run(name)
        ctx = _build_context(db, managed_root=run_root)
        trace: list[tuple[str, str]] = []
        try:
            _run_spike_flow(
                ctx, on_boundary=lambda kind, label: trace.append((kind, label))
            )
        finally:
            ctx.writer.close()
        if learned is None:
            learned = trace
        elif trace != learned:
            raise AssertionError(
                f"spike flow not deterministic: {learned} then {trace}"
            )
    assert learned is not None and learned, "learned boundary set is empty"
    if learned[-1][0] != "commit":
        raise AssertionError(f"spike flow never committed: {learned}")
    published_index = learned.index(("hook", "published"))
    begin_index = learned.index(("begin_immediate", "BEGIN IMMEDIATE"))
    # The core ordering claim, checked on the trace itself: publication is
    # strictly before BEGIN IMMEDIATE.
    assert published_index < begin_index, learned

    from astrid.core.io.media_import import prepare_media_file

    reference = prepare_media_file(
        template_root / _SPIKE_REL, root=template_root
    )

    # Complete reference state on its own seeded copy.
    complete_db, complete_root = _copy_run("complete")
    complete_ctx = _build_context(complete_db, managed_root=complete_root)
    try:
        _run_spike_flow(complete_ctx)
        complete_state = _sql_only(_snapshot_state(complete_ctx, complete_db))
        if not _integrity_checks_pass(complete_ctx, complete_db):
            raise AssertionError("complete spike run failed quick/FK checks")
    finally:
        complete_ctx.writer.close()

    rows: list[dict[str, Any]] = []
    for index, (kind, label) in enumerate(learned):
        crash_db, crash_root = _copy_run(f"crash-{index}")
        old_ctx = _build_context(crash_db, managed_root=crash_root)
        try:
            old_state = _sql_only(_snapshot_state(old_ctx, crash_db))
        finally:
            old_ctx.writer.close()
        if not _integrity_checks_pass(old_ctx, crash_db):
            raise AssertionError(
                f"seed copy for boundary {index} failed quick/FK checks"
            )

        argv = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--spike-child",
            str(crash_db),
            str(crash_root),
            str(index),
        ]
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(_REPO_ROOT),
            check=False,
            env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)},
        )
        if proc.returncode != _CRASH_EXIT_CODE:
            raise AssertionError(
                f"boundary {index} ({kind}:{label}) child exited "
                f"{proc.returncode} instead of {_CRASH_EXIT_CODE}: "
                f"{proc.stdout[-500:]}{proc.stderr[-500:]}"
            )

        reopen_ctx = _build_context(crash_db, managed_root=crash_root)
        try:
            if not _integrity_checks_pass(reopen_ctx, crash_db):
                raise AssertionError(
                    f"boundary {index} ({kind}:{label}) left quick/FK failures"
                )
            chains = _verify_all_stream_chains(reopen_ctx, crash_db)
            reopened = _sql_only(_snapshot_state(reopen_ctx, crash_db))
        finally:
            reopen_ctx.writer.close()

        is_post_commit = index == len(learned) - 1
        expected = "complete" if is_post_commit else "old"
        actual = (
            "complete" if reopened == complete_state else
            "old" if reopened == old_state else "partial"
        )
        if actual != expected:
            raise AssertionError(
                f"boundary {index} ({kind}:{label}) SQL verdict {actual}, "
                f"expected {expected}"
            )

        bytes_state = _digest_file_state(
            crash_root, reference.digest, reference.byte_size
        )
        if bytes_state in ("partial", "mutated"):
            raise AssertionError(
                f"boundary {index} ({kind}:{label}) left "
                f"{bytes_state} digest bytes"
            )
        expected_bytes = "durable" if index >= published_index else "absent"
        rows.append(
            {
                "index": index,
                "kind": kind,
                "sql": label,
                "exit": proc.returncode,
                "expected": expected,
                "actual": actual,
                "bytes": bytes_state,
                "expected_bytes": expected_bytes,
                "chains": chains,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_project_create_crashes_at_every_boundary_to_old_or_complete() -> None:
    """Every project.create statement boundary: old or complete, never torn.

    Includes the pre-commit boundaries (every statement before COMMIT, which
    must leave the seed state — no project row, no stream, no receipt) and
    the post-commit boundary (which must deliver the complete created
    project, stream, event, and receipt atomically).
    """
    spec = _project_create_spec()
    with tempfile.TemporaryDirectory(
        prefix="astrid-crash-project-create-"
    ) as tmp:
        root = Path(tmp)
        rows = _crash_matrix(_build_registry(), spec, root)
    assert len(rows) >= 4, f"expected several boundaries, got {len(rows)}"
    assert rows[-1]["kind"] == "commit"
    _emit_diagnostics(spec.command_kind, rows)
    # Every boundary actually crashed with the child's abrupt exit code.
    assert all(row["exit"] == _CRASH_EXIT_CODE for row in rows)
    # Pre-commit boundaries yielded the old state; post-commit the complete.
    assert all(
        row["actual"] == row["expected"] for row in rows
    ), [row for row in rows if row["actual"] != row["expected"]]
    # Genesis-to-head verification ran on every reopened database without
    # raising (EventChainError would propagate); the complete post-commit
    # state always carries at least one stream to verify.
    assert rows[-1]["chains"], rows[-1]
    assert all(
        row["chains"] for row in rows if row["expected"] == "complete"
    )


def test_timeline_save_crashes_at_every_boundary_to_old_or_complete(
    tmp_path: Path,
) -> None:
    """Every timeline.save boundary: old or complete, never torn.

    The seed places the timeline at head 1 (one ``timeline.created`` event);
    the post-commit boundary must deliver the saved document at head 2 with
    the ``timeline.saved`` event and the receipt, while every pre-commit
    boundary must leave the head-1 document, registry, event, and receipt
    state byte-identical.
    """
    ctx = _build_context(tmp_path / "probe.sqlite3")
    try:
        spec = standard_command_specs(ctx)["timeline.save"]
    finally:
        ctx.writer.close()
    with tempfile.TemporaryDirectory(
        prefix="astrid-crash-timeline-save-"
    ) as tmp:
        root = Path(tmp)
        rows = _crash_matrix(_build_registry(), spec, root)
    assert len(rows) >= 6, f"expected several boundaries, got {len(rows)}"
    assert rows[-1]["kind"] == "commit"
    _emit_diagnostics(spec.command_kind, rows)
    assert all(row["exit"] == _CRASH_EXIT_CODE for row in rows)
    assert all(
        row["actual"] == row["expected"] for row in rows
    ), [row for row in rows if row["actual"] != row["expected"]]
    # Genesis-to-head verification ran on every reopened database without
    # raising; the complete state always carries at least one stream.
    assert rows[-1]["chains"], rows[-1]
    # The complete state advanced the timeline stream to exactly head 2.
    complete = rows[-1]["chains"]
    assert any(item["head_seq"] == 2 for item in complete)


def test_media_import_crashes_at_every_boundary_to_old_or_complete() -> None:
    """Every core.media.import boundary (filesystem + SQL): old-or-complete.

    The media import command spans two authorities: the filesystem
    staging/publication pipeline (with the new deterministic hook points
    ``staged`` / ``published`` / ``repo.published``) and the repository's
    SQL statements. Each boundary is crashed in a child process that exits
    abruptly; every reopened database must be **SQL** old-or-complete with
    clean ``quick_check`` / ``foreign_key_check`` and genesis-to-head
    chains. On top of the SQL verdict, each reopened run is checked for:

    - **media byte references** — every ``media_locations`` managed
      locator must hash to its media row's ``content_hash``, and every
      managed digest file must hash to the digest its path encodes
      (missing/mutated detection);
    - **startup staging GC** — the standard selective GC (no live
      attempts) removes every unreferenced staging directory and never
      touches the managed sha256 digest tree;
    - **orphan-digest reuse (SD5)** — a verified managed digest published
      before rollback is retained and the next import reuses it
      (``reused: true``), never duplicating the digest file.
    """
    with tempfile.TemporaryDirectory(
        prefix="astrid-crash-media-import-"
    ) as tmp:
        root = Path(tmp)
        rows = _media_crash_matrix(_build_registry(), root)
    assert len(rows) >= 12, f"expected several boundaries, got {len(rows)}"
    assert rows[-1]["kind"] == "commit"
    _emit_diagnostics("core.media.import", rows)
    # Every boundary actually crashed with the child's abrupt exit code.
    assert all(row["exit"] == _CRASH_EXIT_CODE for row in rows)
    # SQL old-or-complete at every boundary (never a partial intermediate).
    assert all(
        row["actual"] == row["expected"] for row in rows
    ), [row for row in rows if row["actual"] != row["expected"]]
    # Genesis-to-head verification ran on every reopened database; the
    # post-commit complete state always carries the media stream.
    assert rows[-1]["chains"], rows[-1]
    assert all(row["chains"] for row in rows if row["expected"] == "complete")
    # Every reopened database's media bytes verified (rows and digest tree).
    assert all(row["media_verified"] for row in rows)
    # Staging GC drained every unreferenced staging directory on reopen and
    # never swept managed digest bytes: the managed sha256 tree is
    # byte-identical before and after the GC pass on every reopened root.
    for row in rows:
        assert row["staging_gc"]["after"] == {}, row
        assert (
            row["staging_gc"]["managed_before"]
            == row["staging_gc"]["managed_after"]
        ), row
    # Orphan published digests (crash at/after publication with rolled-back
    # SQL) are retained and reused by the next import — never duplicated.
    orphan_rows = [row for row in rows if row["orphan_digests"]]
    assert orphan_rows, "expected pre-commit publication crashes to leave orphans"
    for row in orphan_rows:
        assert row["reuse"]["duplicated"] is False, row
        assert row["reuse"]["reused"] is True, row
    # The complete (post-commit) import was a fresh publication.
    assert rows[-1]["reuse"]["reused"] is False, rows[-1]


def test_task_completion_crashes_at_every_boundary_to_old_or_complete() -> None:
    """Every core.task.complete boundary (filesystem + SQL): old-or-complete.

    The completion command spans two authorities: the filesystem
    staging/publication pipeline of the in-UoW media primitive (with the
    deterministic hook points ``staged`` / ``published`` /
    ``repo.published``) and the repository's SQL statements across runs,
    tasks, dependencies, attempts, outputs, media, locations, relations,
    events, heads, and receipts. Each boundary is crashed in a child
    process that exits abruptly; every reopened database must be **SQL**
    old-or-complete with clean ``quick_check`` / ``foreign_key_check`` and
    genesis-to-head chains. On top of the SQL verdict, each reopened run
    is checked for:

    - **media byte references** — every ``media_locations`` managed
      locator must hash to its media row's ``content_hash``, every managed
      digest file must hash to the digest its path encodes, and every
      committed ``task_outputs`` row must resolve to that verified media
      (missing/mutated detection, no partial outputs);
    - **selective startup staging GC** — the real startup path (live
      ``staging_txn_id`` references collected from ``execution_attempts``)
      preserves the running attempt's handler quarantine on every
      pre-commit crash, drains the completion's own unreferenced staging,
      and never touches the managed sha256 digest tree;
    - **convergent re-completion (SD5)** — re-running the fenced
      completion on the reopened database converges to the complete state:
      pre-commit crashes re-win with every orphan published digest
      verified-reused (never duplicated), and the post-commit crash
      replays the stored receipt with zero new rows.
    """
    with tempfile.TemporaryDirectory(
        prefix="astrid-crash-task-complete-"
    ) as tmp:
        root = Path(tmp)
        rows = _completion_crash_matrix(_build_registry(), root)
    assert len(rows) >= 30, f"expected many boundaries, got {len(rows)}"
    assert rows[-1]["kind"] == "commit"
    _emit_diagnostics("core.task.complete", rows)
    # Every boundary actually crashed with the child's abrupt exit code.
    assert all(row["exit"] == _CRASH_EXIT_CODE for row in rows)
    # SQL old-or-complete at every boundary (never a partial intermediate).
    assert all(
        row["actual"] == row["expected"] for row in rows
    ), [row for row in rows if row["actual"] != row["expected"]]
    # Genesis-to-head verification ran on every reopened database; the
    # post-commit complete state always carries the task and media streams.
    assert rows[-1]["chains"], rows[-1]
    assert all(row["chains"] for row in rows if row["expected"] == "complete")
    # The complete state advanced the task stream to its terminal head and
    # the run projection to one succeeded child (never a partial run).
    complete_chains = rows[-1]["chains"]
    assert any(
        item["head_seq"] >= 2 for item in complete_chains
    ), complete_chains
    # Every reopened database's media bytes verified (rows + digest tree),
    # so no committed row references missing or mutated bytes.
    assert all(row["media_verified"] for row in rows)
    # Startup staging GC: the live attempt's handler quarantine survives
    # every pre-commit crash, the committed completion drains all staging,
    # and the managed sha256 tree is never touched.
    for row in rows:
        assert (
            row["staging_gc"]["managed_before"]
            == row["staging_gc"]["managed_after"]
        ), row
        if row["expected"] == "old":
            assert row["staging_gc"]["live_staging_preserved"] is True, row
        else:
            assert row["staging_gc"]["after"] == {}, row
    # A full re-completion on every reopened database converges to exactly
    # the complete SQL state and digest tree — no missing bytes, no partial
    # outputs/relations/receipts, no duplicated digests.
    for row in rows:
        assert row["rerun"]["sql_matches_complete"] is True, row
        assert row["rerun"]["media_matches_complete"] is True, row
    # The post-commit crash replays the stored receipt with zero new rows.
    assert rows[-1]["rerun"]["zero_new_rows_on_replay"] is True, rows[-1]
    # Orphan published digests (crash at/after publication with rolled-back
    # SQL) are retained and reused by the re-completion — every orphan's
    # bytes are verified-reused (SD5), never duplicated.
    orphan_rows = [row for row in rows if row["orphan_digests"]]
    assert orphan_rows, "expected pre-commit publication crashes to leave orphans"
    for row in orphan_rows:
        assert row["rerun"]["reused_orphans"] is True, row
    # The complete (post-commit) completion left no orphans at all.
    assert rows[-1]["orphan_digests"] == [], rows[-1]


def test_publication_is_durable_before_begin_immediate_at_every_boundary(
    tmp_path: Path,
) -> None:
    """Section 5 spike: pre-lock publication survives process death.

    The managed digest object becomes durable (temp fsync, atomic
    ``os.replace`` onto the frozen hash path, directory fsyncs) strictly
    before ``BEGIN IMMEDIATE``; crashing a child at every boundary from
    staged-copy through COMMIT reopens with byte-correct-or-absent digest
    bytes — never partial — and SQLite old-or-complete. Every boundary at
    or after the publication hook finds the bytes fully durable, which is
    exactly the amended ordering premise the completion route builds on.
    """
    rows = _spike_crash_matrix(tmp_path)
    assert len(rows) >= 4, f"expected several boundaries, got {len(rows)}"
    assert all(row["exit"] == _CRASH_EXIT_CODE for row in rows), rows
    assert all(
        row["actual"] == row["expected"] for row in rows
    ), [row for row in rows if row["actual"] != row["expected"]]
    # No boundary ever left partial or mutated digest bytes.
    assert all(
        row["bytes"] in ("absent", "durable") for row in rows
    ), [row for row in rows if row["bytes"] not in ("absent", "durable")]
    # From the publication boundary onward — including every crash inside
    # BEGIN IMMEDIATE, mid-transaction, and at COMMIT — the bytes are fully
    # durable at the hash path before any SQL authority exists for them.
    published = next(
        row["index"] for row in rows if row["kind"] == "hook"
        and row["sql"] == "published"
    )
    begin = next(
        row["index"] for row in rows if row["kind"] == "begin_immediate"
    )
    assert published < begin, rows
    for row in rows:
        if row["index"] >= published:
            assert row["bytes"] == "durable", row
        else:
            assert row["bytes"] == "absent", row
    assert rows[-1]["chains"], rows[-1]
    _emit_diagnostics("spike.pre_lock_publish", rows)


def test_pre_published_import_in_lock_work_is_stat_only(tmp_path: Path) -> None:
    """Amended §5 flow: publish before BEGIN IMMEDIATE, O(stat) in lock.

    The prepared source fixture and the whole staging tree are deleted
    after the pre-transaction publication, so a successful in-lock import
    proves the writer transaction never copies or re-reads source bytes:
    its only filesystem work is the O(stat) presence validation, observed
    as exactly one ``repo.published`` hook and no staging/publication
    hooks. A mismatched publication digest and an absent managed object
    both raise before any projection write.
    """
    from astrid.core.io.media_import import (
        MediaLocationError,
        managed_media_path,
        prepare_media_file,
        publish_prepared_for_commit,
        set_media_crash_hook,
        validate_published_presence,
    )
    from astrid.core.repositories.media import MediaValidationError

    db = tmp_path / "astrid.sqlite3"
    root = tmp_path / "managed"
    root.mkdir(parents=True, exist_ok=True)
    _seed_spike_template(db, root)
    ctx = _build_context(db, managed_root=root)
    try:
        fixture = root / _SPIKE_REL
        prepared = prepare_media_file(fixture, root=root)

        # Outside any transaction: durable publication at the hash path.
        (publications,) = publish_prepared_for_commit(
            root, _SPIKE_TXN_ID, [prepared]
        )
        assert publications.reused is False
        # The in-lock phase must not need the source or staging bytes.
        fixture.unlink()
        shutil.rmtree(root / ".astrid" / "media" / ".staging")

        hooks: list[str] = []
        set_media_crash_hook(hooks.append)
        try:
            model = UnitOfWork(ctx.writer).run(
                lambda u: ctx.media.import_prepared(
                    u,
                    project_id=_SPIKE_PROJECT_ID,
                    prepared=prepared,
                    idempotency_key="prepublished-import",
                    media_id=_SPIKE_MEDIA_ID,
                    published=publications,
                    created_at=TS,
                )
            )
        finally:
            set_media_crash_hook(None)
        assert model.content_hash == prepared.digest
        assert hooks == ["repo.published"], hooks
        assert not fixture.exists(), "in-lock work resurrected source bytes"
        assert (
            validate_published_presence(root, prepared.digest)
            == prepared.byte_size
        )
        wrong = publications.__class__(
            digest="0" * 64,
            managed_path=managed_media_path(root, "0" * 64),
            byte_size=prepared.byte_size,
            reused=False,
        )
        try:
            UnitOfWork(ctx.writer).run(
                lambda u: ctx.media.import_prepared(
                    u,
                    project_id=_SPIKE_PROJECT_ID,
                    prepared=prepared,
                    idempotency_key="wrong-digest",
                    media_id=_SPIKE_MEDIA_ID + "-x",
                    published=wrong,
                    created_at=TS,
                )
            )
            raise AssertionError("mismatched published digest was accepted")
        except MediaValidationError:
            pass

        # An absent managed object can never back a committed row.
        managed_media_path(root, prepared.digest).unlink()
        try:
            UnitOfWork(ctx.writer).run(
                lambda u: ctx.media.import_prepared(
                    u,
                    project_id=_SPIKE_PROJECT_ID,
                    prepared=prepare_media_file(
                        _write_spike_fixture(root), root=root
                    ),
                    idempotency_key="absent-object",
                    media_id=_SPIKE_MEDIA_ID + "-y",
                    published=publications,
                    created_at=TS,
                )
            )
            raise AssertionError("import committed against absent bytes")
        except MediaLocationError:
            pass
    finally:
        ctx.writer.close()


def test_publish_for_commit_is_idempotent_and_reuses_orphans(
    tmp_path: Path,
) -> None:
    """Pre-lock publication is idempotent; crashes leave reusable orphans."""
    from astrid.core.io.media_import import (
        prepare_media_file,
        publish_prepared_for_commit,
    )

    db = tmp_path / "astrid.sqlite3"
    root = tmp_path / "managed"
    root.mkdir(parents=True, exist_ok=True)
    _seed_spike_template(db, root)
    prepared = prepare_media_file(root / _SPIKE_REL, root=root)

    first = publish_prepared_for_commit(root, _SPIKE_TXN_ID, [prepared])[0]
    second = publish_prepared_for_commit(root, _SPIKE_TXN_ID, [prepared])[0]
    assert first.reused is False and second.reused is True
    assert second.byte_size == prepared.byte_size
    assert first.managed_path == second.managed_path


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        raise SystemExit(_child_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "--spike-child":
        raise SystemExit(_spike_child_main(sys.argv[2:]))
    raise SystemExit(2)
