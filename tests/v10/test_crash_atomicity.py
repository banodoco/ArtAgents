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

import os
import shutil
import subprocess
import sys
import tempfile
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
)
"""Every mutable table whose row count participates in old/complete state."""


# ---------------------------------------------------------------------------
# Context construction (mirrors tests/v10/test_conformance.py)
# ---------------------------------------------------------------------------


def _build_registry():
    """Compose core + exactly timeline, shots, and references, then freeze."""
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    return registry.freeze()


def _build_context(db_path: Path) -> ConformanceContext:
    """Build one fresh standard-Astrid conformance context on *db_path*."""
    registry = _build_registry()
    writer = DatabaseWriter(db_path, registry)
    events = EventAppendService(registry)
    receipts = ReceiptService()
    projects = ProjectRepository(events=events, receipts=receipts)
    timelines = TimelineRepository(
        events=events, receipts=receipts, projects=projects
    )
    return ConformanceContext(
        db_path=db_path,
        writer=writer,
        registry=registry,
        events=events,
        receipts=receipts,
        projects=projects,
        timelines=timelines,
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
    raise ValueError(f"unknown crash command kind: {command_kind!r}")


# ---------------------------------------------------------------------------
# State snapshot and integrity helpers
# ---------------------------------------------------------------------------


def _snapshot_state(ctx: ConformanceContext, db_path: Path) -> dict[str, Any]:
    """Snapshot row counts, stream heads, project heads, and documents."""
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
    return {
        "counts": counts,
        "heads": heads,
        "project_heads": project_heads,
        "docs": docs,
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
    """Run the full command once, recording (kind, sql) per boundary."""
    trace: list[tuple[str, str]] = []

    def observer(kind: str, sql: str, params: tuple[Any, ...]) -> None:
        trace.append((kind, sql))

    UnitOfWork(ctx.writer, on_statement=observer).run(
        lambda u: spec.invoke(
            ctx, u, project_id=facts["project_id"], key=facts["key"]
        )
    )
    return trace


def _crash_child(
    crash_db: Path,
    boundary: int,
    command_kind: str,
    project_id: str,
    key: str,
) -> subprocess.CompletedProcess[str]:
    """Run the crash child for one boundary and return its result."""
    return subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--child",
            str(crash_db),
            str(boundary),
            command_kind,
            project_id,
            key,
            str(_REPO_ROOT),
        ],
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
    sys.path.insert(0, str(root))

    ctx = _build_context(_db_path)
    spec = _command_spec(ctx, command_kind)
    seen = {"count": 0}

    def observer(kind: str, sql: str, params: tuple[Any, ...]) -> None:
        if seen["count"] == boundary:
            # Abrupt termination: no Python cleanup, no connection close, no
            # WAL checkpoint — exactly a killed process.
            os._exit(_CRASH_EXIT_CODE)  # noqa: PLR1722 - the point of the test
        seen["count"] += 1

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


def _emit_diagnostics(command_kind: str, rows: list[dict[str, Any]]) -> None:
    """Print the observable per-boundary crash matrix for the record."""
    print(
        f"\n[crash_atomicity:{command_kind}] "
        f"{len(rows)} boundaries crashed in child processes",
        flush=True,
    )
    for row in rows:
        print(
            f"  boundary {row['index']:>2} {row['kind']:<16} "
            f"exit={row['exit']} verdict={row['expected']}->{row['actual']} "
            f"sql={row['sql'][:80]!r}",
            flush=True,
        )
    print(
        f"[crash_atomicity:{command_kind}] every reopened database passed "
        "quick_check, foreign_key_check, and genesis-to-head chain "
        "verification",
        flush=True,
    )


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


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        raise SystemExit(_child_main(sys.argv[2:]))
    raise SystemExit(2)
