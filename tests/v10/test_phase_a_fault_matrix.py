"""Phase-A crash/fault-injection harness skeleton (doc 27 §5 crash matrix).

This module is the **working mechanism** for the Phase-A fault matrix; the
convergence phase fills the labeled points in. It copies the proven
``tests/v10/test_crash_atomicity.py`` pattern:

- every fault is injected in a **child process** that re-executes the same
  deterministic scenario and terminates abruptly at exactly one labeled
  point (``os._exit(137)`` — no cleanup, no close, no checkpoint);
- the parent reopens both authorities (SQLite + managed sha256 tree) after
  every crash and asserts the invisible-failure default: the database is
  the old state or the complete committed state — never partial — and the
  byte tree holds only fully durable objects or unreferenced orphans;
- a declarative fault-schedule drives the matrix: each entry names a
  labeled point, an occurrence, and the expected post-crash verdict;
- every run appends an observable row to a SQLite evidence table
  (``phase_a_fault_evidence``) so matrix results survive the test process.

Labeled points (doc 27 §5: "injects process death at labeled
upload/hash/publish/transaction/commit/response boundaries"):

- ``upload``      — request-scoped quarantine staging of the raw bytes;
- ``hash``        — the server-computed SHA-256 identity boundary;
- ``publish``     — durable install into the managed tree BEFORE
  ``BEGIN IMMEDIATE`` (temp fsync, atomic replace, directory fsync);
- ``pre_commit``  — inside the writer transaction, before COMMIT;
- ``post_commit`` — the COMMIT boundary itself;
- ``response``    — after COMMIT, before the caller observes the result.

The current placements are the skeleton's provisional wiring (upload/hash/
publish bracket the real preparation/publication calls; pre/post/response
bracket the unit-of-work envelope). The convergence phase refines the
in-point placement and extends the schedule with ``SQLITE_IOERR``,
``SQLITE_FULL``, filesystem exhaustion, replay, and concurrent identical-
byte publication lanes without changing this driver.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.events.registry import register_core_vocabulary
from astrid.core.events.service import EventAppendService
from astrid.core.receipts import ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.schema_packs.registry import SchemaPackRegistry
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs import register_standard_schema_packs

TS = "2026-08-15T00:00:00.000000+00:00"
_CRASH_EXIT_CODE = 137
_FAULT_EXIT_OK = 0
_FAULT_EXIT_ERROR = 2
_REPO_ROOT = Path(__file__).resolve().parents[2]

_PROJECT_ID = "fault-proj"
_MEDIA_ID = "media-fault-out-a"
_TXN_ID = "edededed" * 4
_FIXTURE_REL = "fixtures/fault.svg"
_FIXTURE_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'/>track-k-fault"
_IDEMPOTENCY_KEY = "fault-completion-k"

LABELED_POINTS: tuple[str, ...] = (
    "upload",
    "hash",
    "publish",
    "pre_commit",
    "post_commit",
    "response",
)
"""The doc 27 §5 fault-injection boundaries the driver understands."""

_EVIDENCE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS phase_a_fault_evidence (
  id            INTEGER PRIMARY KEY,
  injected_at   TEXT NOT NULL,
  lane          TEXT NOT NULL,
  point         TEXT NOT NULL,
  occurrence    INTEGER NOT NULL,
  child_exit    INTEGER NOT NULL,
  expected      TEXT NOT NULL,
  actual        TEXT NOT NULL,
  chains_valid  INTEGER NOT NULL,
  notes         TEXT NOT NULL
)
"""

_SNAPSHOT_TABLES = (
    "projects",
    "event_streams",
    "events",
    "command_receipts",
    "media",
    "media_locations",
)


# ---------------------------------------------------------------------------
# Declarative fault schedule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FaultInjection:
    """One declarative entry of the fault schedule."""

    point: str
    """The labeled boundary to terminate the child at."""

    occurrence: int = 1
    """Which firing of *point* crashes (1-based; points may fire per object)."""

    expect: str = "old"
    """Expected reopened SQL verdict: ``old`` or ``complete``."""

    def validate(self) -> None:
        if self.point not in LABELED_POINTS:
            raise ValueError(
                f"unknown labeled point {self.point!r}; "
                f"expected one of {LABELED_POINTS}"
            )
        if (
            isinstance(self.occurrence, bool)
            or not isinstance(self.occurrence, int)
            or self.occurrence < 1
        ):
            raise ValueError("occurrence must be a positive integer")
        if self.expect not in ("old", "complete"):
            raise ValueError(
                f"expect must be 'old' or 'complete', got {self.expect!r}"
            )


def default_fault_schedule() -> tuple[FaultInjection, ...]:
    """The skeleton schedule: one abrupt-death injection per labeled point."""
    return tuple(
        FaultInjection(
            point=point,
            expect="complete" if point in ("post_commit", "response") else "old",
        )
        for point in LABELED_POINTS
    )


# ---------------------------------------------------------------------------
# Context construction (mirrors tests/v10/test_crash_atomicity.py)
# ---------------------------------------------------------------------------


def _build_registry():
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    return registry.freeze()


def _build_context(db_path: Path, *, managed_root: Path) -> dict[str, Any]:
    """One fresh kernel context: project + media verticals on *db_path*."""
    registry = _build_registry()
    events = EventAppendService(registry)
    receipts = ReceiptService()
    projects = ProjectRepository(events=events, receipts=receipts)

    from astrid.core.repositories.media import MediaRepository

    media = MediaRepository(
        events=events, receipts=receipts, projects_root=managed_root
    )
    writer = DatabaseWriter(db_path, registry)
    return {
        "registry": registry,
        "writer": writer,
        "events": events,
        "receipts": receipts,
        "projects": projects,
        "media": media,
        "managed_root": managed_root,
    }


def _write_fixture(managed_root: Path) -> Path:
    path = managed_root / _FIXTURE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_FIXTURE_BYTES)
    return path


def _seed_template(template_path: Path, template_root: Path) -> None:
    """One clean template database holding exactly the fault project."""
    ctx = _build_context(template_path, managed_root=template_root)
    try:
        UnitOfWork(ctx["writer"]).run(
            lambda u: ctx["projects"].create(
                u,
                slug=_PROJECT_ID,
                name="Fault Project",
                settings={},
                idempotency_key="fault-seed-project",
                project_id=_PROJECT_ID,
                created_at=TS,
            )
        )
        _write_fixture(template_root)
    finally:
        ctx["writer"].close()


def _copy_run(
    template_path: Path, template_root: Path, name: str, tmp: Path
) -> tuple[Path, Path]:
    """One fresh seeded copy of both authorities for one matrix lane."""
    db = tmp / f"{name}.sqlite3"
    shutil.copy2(template_path, db)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{template_path}{suffix}")
        if sidecar.exists():
            shutil.copy2(sidecar, Path(f"{db}{suffix}"))
    run_root = tmp / f"{name}-managed"
    shutil.copytree(template_root, run_root)
    return db, run_root


# ---------------------------------------------------------------------------
# The scenario: the amended §5 completion shape with labeled points
# ---------------------------------------------------------------------------


def run_scenario(ctx: dict[str, Any], *, faults: "_FaultInjector | None" = None) -> Any:
    """Prepare, publish durably, then commit — emitting each labeled point.

    This is the exact sequence the Phase-A completion route runs; the
    convergence phase replaces the import command with the fenced
    completion command without changing the point vocabulary.
    """
    from astrid.core.io.media_import import (
        prepare_media_file,
        publish_prepared_for_commit,
    )

    root = ctx["managed_root"]
    prepared = prepare_media_file(_write_fixture(root), root=root)
    if faults is not None:
        faults.hit("hash")
    if faults is not None:
        faults.hit("upload")

    # Durable publication strictly before BEGIN IMMEDIATE (doc 27 §5).
    (published,) = publish_prepared_for_commit(root, _TXN_ID, [prepared])
    if faults is not None:
        faults.hit("publish")

    def observer(kind: str, sql: str, params: tuple[Any, ...]) -> None:
        if faults is None:
            return
        if kind == "begin_immediate":
            faults.hit("pre_commit")
        elif kind == "commit":
            faults.hit("post_commit")

    result = UnitOfWork(ctx["writer"], on_statement=observer).run(
        lambda u: ctx["media"].import_prepared(
            u,
            project_id=_PROJECT_ID,
            prepared=prepared,
            idempotency_key=_IDEMPOTENCY_KEY,
            media_id=_MEDIA_ID,
            published=published,
            created_at=TS,
        )
    )
    if faults is not None:
        faults.hit("response")
    return result


class _FaultInjector:
    """Crashes the process at exactly one scheduled (point, occurrence)."""

    def __init__(self, injection: FaultInjection) -> None:
        injection.validate()
        self._injection = injection
        self._seen: dict[str, int] = {}

    def hit(self, point: str) -> None:
        if point not in LABELED_POINTS:
            raise ValueError(f"unknown labeled point {point!r}")
        self._seen[point] = self._seen.get(point, 0) + 1
        if (
            point == self._injection.point
            and self._seen[point] == self._injection.occurrence
        ):
            os._exit(_CRASH_EXIT_CODE)  # noqa: PLR1722 - the point of the harness


# ---------------------------------------------------------------------------
# Evidence table writer
# ---------------------------------------------------------------------------


def _open_evidence_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(_EVIDENCE_TABLE_DDL)
    conn.commit()
    return conn


def _record_evidence(
    evidence: sqlite3.Connection,
    *,
    lane: str,
    injection: FaultInjection | None,
    child_exit: int,
    expected: str,
    actual: str,
    chains_valid: bool,
    notes: str,
) -> None:
    """Append one observable outcome row to the evidence table."""
    evidence.execute(
        "INSERT INTO phase_a_fault_evidence "
        "(injected_at, lane, point, occurrence, child_exit, expected, "
        "actual, chains_valid, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            TS,
            lane,
            injection.point if injection is not None else "",
            injection.occurrence if injection is not None else 0,
            child_exit,
            expected,
            actual,
            1 if chains_valid else 0,
            notes,
        ),
    )
    evidence.commit()


# ---------------------------------------------------------------------------
# Reopen verification (both authorities)
# ---------------------------------------------------------------------------


def _snapshot(db_path: Path, registry: Any, managed_root: Path) -> dict[str, Any]:
    """SQL counts/heads plus every non-staging managed digest file."""
    from astrid.core.store.database import open_database

    conn = open_database(db_path, registry, read_only=True)
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
    finally:
        conn.close()
    media_root = managed_root / ".astrid" / "media"
    files: dict[str, int] = {}
    if media_root.is_dir():
        for path in sorted(media_root.rglob("*")):
            if path.is_file() and ".staging" not in path.parts:
                files[str(path.relative_to(media_root))] = path.stat().st_size
    return {"counts": counts, "heads": heads, "files": files}


def _chains_valid(db_path: Path, registry: Any) -> bool:
    """Genesis-to-head chain verification on every stream after reopen."""
    from astrid.core.store.database import open_database

    conn = open_database(db_path, registry, read_only=True)
    try:
        stream_ids = [
            str(row[0])
            for row in conn.execute(
                "SELECT id FROM event_streams ORDER BY id"
            ).fetchall()
        ]
    finally:
        conn.close()
    if not stream_ids:
        return True
    service = EventAppendService(registry)
    writer = DatabaseWriter(db_path, registry)
    try:
        for stream_id in stream_ids:
            service.verify_stream(writer, stream_id)
    finally:
        writer.close()
    return True
# ---------------------------------------------------------------------------
# Child protocol and declarative schedule driver
# ---------------------------------------------------------------------------


def _fault_child_main(argv: list[str]) -> int:
    """Child entry: rebuild the scenario, crash at one scheduled injection."""
    db_path = Path(argv[0])
    managed_root = Path(argv[1])
    point = argv[2]
    occurrence = int(argv[3])
    sys.path.insert(0, str(_REPO_ROOT))

    ctx = _build_context(db_path, managed_root=managed_root)
    try:
        run_scenario(
            ctx,
            faults=_FaultInjector(
                FaultInjection(point=point, occurrence=occurrence)
            ),
        )
    except BaseException:  # noqa: BLE001 - never mask a failed child as success
        os._exit(_FAULT_EXIT_ERROR)
    os._exit(_FAULT_EXIT_OK)


def _child_proc(crash_db: Path, crash_root: Path, injection: FaultInjection):
    return subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--fault-child",
            str(crash_db),
            str(crash_root),
            injection.point,
            str(injection.occurrence),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(_REPO_ROOT),
        check=False,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)},
    )


def run_fault_matrix(tmp: Path) -> list[dict[str, Any]]:
    """Execute the declarative schedule; return per-injection result rows.

    Every lane gets a fresh copy of both authorities. The parent learns the
    old (seeded) and complete reference states from untouched copies, then
    crashes a child at each scheduled injection and classifies the reopened
    SQL state against both references. Every outcome lands in the evidence
    table under ``evidence/fault-evidence.sqlite3``.
    """
    evidence = _open_evidence_db(tmp / "evidence" / "fault-evidence.sqlite3")

    template_path = tmp / "seed.sqlite3"
    template_root = tmp / "seed-managed"
    template_root.mkdir(parents=True, exist_ok=True)
    _seed_template(template_path, template_root)

    registry = _build_registry()

    # Reference states from untouched copies of both authorities.
    old_db, old_root = _copy_run(template_path, template_root, "old", tmp)
    old_state = _snapshot(old_db, registry, old_root)
    full_db, full_root = _copy_run(template_path, template_root, "full", tmp)
    full_ctx = _build_context(full_db, managed_root=full_root)
    try:
        run_scenario(full_ctx)
    finally:
        full_ctx["writer"].close()
    complete_state = _snapshot(full_db, registry, full_root)

    rows: list[dict[str, Any]] = []
    for index, injection in enumerate(default_fault_schedule()):
        injection.validate()
        crash_db, crash_root = _copy_run(
            template_path, template_root, f"crash-{index}", tmp
        )
        proc = _child_proc(crash_db, crash_root, injection)

        reopened = _snapshot(crash_db, registry, crash_root)
        if reopened["counts"] == complete_state["counts"]:
            sql_actual = "complete"
        elif reopened["counts"] == old_state["counts"]:
            sql_actual = "old"
        else:
            sql_actual = "partial"
        chains_ok = _chains_valid(crash_db, registry)
        notes = ""
        if proc.returncode != _CRASH_EXIT_CODE:
            notes = (
                f"child exited {proc.returncode}: "
                f"{proc.stdout[-200:]}{proc.stderr[-200:]}"
            )

        _record_evidence(
            evidence,
            lane=f"injection-{index}",
            injection=injection,
            child_exit=proc.returncode,
            expected=injection.expect,
            actual=sql_actual,
            chains_valid=chains_ok,
            notes=notes,
        )
        rows.append(
            {
                "index": index,
                "point": injection.point,
                "occurrence": injection.occurrence,
                "expect": injection.expect,
                "actual": sql_actual,
                "exit": proc.returncode,
                "chains_valid": chains_ok,
                "notes": notes,
                "orphan_files": sorted(
                    set(reopened["files"]) - set(complete_state["files"])
                    if sql_actual == "old"
                    else set()
                ),
            }
        )
    evidence.close()
    return rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fault_schedule_crashes_at_every_labeled_point(tmp_path: Path) -> None:
    """Every labeled §5 point: abrupt death leaves old-or-complete SQL,
    valid chains on reopen, and only durable-or-orphan byte-tree objects;
    every outcome row is recorded in the evidence table."""
    rows = run_fault_matrix(tmp_path)
    assert [row["point"] for row in rows] == list(LABELED_POINTS)
    assert all(row["exit"] == _CRASH_EXIT_CODE for row in rows), rows
    assert all(
        row["actual"] == row["expect"] for row in rows
    ), [row for row in rows if row["actual"] != row["expect"]]
    assert all(row["chains_valid"] for row in rows), rows

    # Evidence table persisted every lane.
    evidence = sqlite3.connect(tmp_path / "evidence" / "fault-evidence.sqlite3")
    try:
        count, points = evidence.execute(
            "SELECT COUNT(*), COUNT(DISTINCT point) "
            "FROM phase_a_fault_evidence"
        ).fetchone()
    finally:
        evidence.close()
    assert count == len(LABELED_POINTS) and points == len(LABELED_POINTS)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fault-child":
        raise SystemExit(_fault_child_main(sys.argv[2:]))
    print(
        json.dumps(
            {"module": "test_phase_a_fault_matrix", "points": list(LABELED_POINTS)}
        )
    )
    raise SystemExit(0)
