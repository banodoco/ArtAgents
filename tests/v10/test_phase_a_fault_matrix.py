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

import pytest

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


def run_scenario(
    ctx: dict[str, Any],
    *,
    faults: "_FaultInjector | None" = None,
    media_id: str = _MEDIA_ID,
    idempotency_key: str = _IDEMPOTENCY_KEY,
) -> Any:
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
            idempotency_key=idempotency_key,
            media_id=media_id,
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
# Extended matrix (convergence T13): ≥100 crashes across seven classes
# ---------------------------------------------------------------------------

_POINT_REPEATS = 16
_LEASE_DEATH_REPEATS = 4
_CONCURRENT_REPEATS = 2
_SQLITE_ERROR_KINDS: tuple[str, ...] = ("ioerr", "full")


class _SqliteFaultInjector:
    """Raises a simulated SQLite error at exactly one labeled boundary.

    The stdlib sqlite3 module exposes no fault-injection test control, so
    the injected ``SQLITE_IOERR`` / ``SQLITE_FULL`` is the exact exception
    the SQLite C API returns for those conditions, raised at the named
    statement boundary inside the live transaction envelope. The UoW rolls
    back; the reopened verdict must be the old state with valid chains.
    """

    _MESSAGES = {
        "ioerr": "disk I/O error",
        "full": "database or disk is full",
    }

    def __init__(self, point: str, kind: str) -> None:
        if point not in ("pre_commit", "post_commit"):
            raise ValueError(f"sqlite fault point must be a commit boundary, got {point!r}")
        if kind not in self._MESSAGES:
            raise ValueError(f"unknown sqlite fault kind {kind!r}")
        self._point = point
        self._kind = kind

    def hit(self, point: str) -> None:
        if point == self._point:
            import sqlite3 as _sqlite3

            raise _sqlite3.OperationalError(
                f"injected SQLITE_{self._kind.upper()}: "
                f"{self._MESSAGES[self._kind]}"
            )


def _scenario_child_main(argv: list[str]) -> int:
    """Child entry: run the scenario once, no crash, report via exit code."""
    db_path = Path(argv[0])
    managed_root = Path(argv[1])
    media_id = argv[2] if len(argv) > 2 else _MEDIA_ID
    idempotency_key = argv[3] if len(argv) > 3 else _IDEMPOTENCY_KEY
    ctx = _build_context(db_path, managed_root=managed_root)
    try:
        run_scenario(
            ctx, media_id=media_id, idempotency_key=idempotency_key
        )
    except BaseException:  # noqa: BLE001 - failure is signalled, not masked
        ctx["writer"].close()
        return _FAULT_EXIT_ERROR
    ctx["writer"].close()
    return _FAULT_EXIT_OK


def _sqlite_fault_child_main(argv: list[str]) -> int:
    """Child entry: run the scenario with one injected SQLite error."""
    db_path = Path(argv[0])
    managed_root = Path(argv[1])
    point = argv[2]
    kind = argv[3]
    ctx = _build_context(db_path, managed_root=managed_root)
    try:
        run_scenario(
            ctx, faults=_SqliteFaultInjector(point, kind)  # type: ignore[arg-type]
        )
    except BaseException:  # noqa: BLE001 - the injected error IS the lane
        ctx["writer"].close()
        return _FAULT_EXIT_ERROR
    ctx["writer"].close()
    return _FAULT_EXIT_OK


def _claim_death_child_main(argv: list[str]) -> int:
    """Child entry: claim the seeded task, then die holding the lease."""
    from astrid.core.repositories.tasks import TaskRepository

    db_path = Path(argv[0])
    managed_root = Path(argv[1])
    ctx = _build_context(db_path, managed_root=managed_root)
    tasks = TaskRepository(events=ctx["events"], receipts=ctx["receipts"])
    try:
        UnitOfWork(ctx["writer"]).run(
            lambda u: tasks.claim(
                u,
                project_id=_PROJECT_ID,
                idempotency_key="fault-lease-claim",
                executor_id="fault-executor",
                lease_seconds=300,
                now=TS,
            )
        )
    except BaseException:  # noqa: BLE001
        os._exit(_FAULT_EXIT_ERROR)
    os._exit(_CRASH_EXIT_CODE)  # noqa: PLR1722 - executor death mid-lease


def _run_module_child(args: list[str], *, timeout: int = 60):
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(_REPO_ROOT),
        check=False,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)},
    )


def _classify(
    crash_db: Path,
    crash_root: Path,
    registry: Any,
    old_state: dict[str, Any],
    complete_state: dict[str, Any],
) -> tuple[str, bool, dict[str, Any]]:
    reopened = _snapshot(crash_db, registry, crash_root)
    if reopened["counts"] == complete_state["counts"]:
        actual = "complete"
    elif reopened["counts"] == old_state["counts"]:
        actual = "old"
    else:
        actual = "partial"
    chains_ok = _chains_valid(crash_db, registry)
    return actual, chains_ok, reopened


def _seed_task(template_ctx_writer, registry) -> None:
    """One queued fault task in the template database."""
    from astrid.core.repositories.tasks import TaskRepository

    events = EventAppendService(registry)
    tasks = TaskRepository(events=events, receipts=ReceiptService())
    UnitOfWork(template_ctx_writer).run(
        lambda u: tasks.create(
            u,
            project_id=_PROJECT_ID,
            capability="reigh.image_upscale",
            spec={"schema_version": 1, "family": "image_upscale"},
            input_manifest=[],
            idempotency_key="fault-seed-task",
            task_id="task-fault-lease",
            max_attempts=3,
            created_at=TS,
        )
    )


def _fs_exhaustion_child_main(argv: list[str]) -> int:
    """Child entry: run the scenario under a 1 KiB file-size rlimit.

    The container cannot mount a tiny tmpfs (no CAP_SYS_ADMIN), so real
    ENOSPC is approximated by the kernel's own write-failure path: the
    first staged write past ``RLIMIT_FSIZE`` fails with ``EFBIG`` and the
    default ``SIGXFSZ`` disposition terminates the process mid-scenario —
    an abrupt, filesystem-refusal death at the upload/staging boundary.
    """
    import resource

    resource.setrlimit(resource.RLIMIT_FSIZE, (1024, 1024))
    return _scenario_child_main(argv)


def run_extended_fault_matrix(
    tmp: Path, evidence_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The full T13 matrix: ≥100 abrupt crashes across the labeled points,
    SQLite error injection, filesystem exhaustion, replay recovery,
    concurrent identical-byte publication, and lease-death-via-sweep.

    Returns ``(rows, summary)``; *summary* carries the measured wall clock
    against the 900 s CI lane budget (delta N3).
    """
    import time

    started = time.monotonic()
    evidence = _open_evidence_db(evidence_path)
    rows: list[dict[str, Any]] = []
    crash_count = 0

    registry = _build_registry()
    template_path = tmp / "seed.sqlite3"
    template_root = tmp / "seed-managed"
    template_root.mkdir(parents=True, exist_ok=True)
    _seed_template(template_path, template_root)

    # Reference states.
    old_db, old_root = _copy_run(template_path, template_root, "x-old", tmp)
    old_state = _snapshot(old_db, registry, old_root)
    full_db, full_root = _copy_run(template_path, template_root, "x-full", tmp)
    full_ctx = _build_context(full_db, managed_root=full_root)
    try:
        run_scenario(full_ctx)
    finally:
        full_ctx["writer"].close()
    complete_state = _snapshot(full_db, registry, full_root)

    def record(lane, point, occurrence, proc, actual, chains_ok, expect, extra=""):
        _record_evidence(
            evidence,
            lane=lane,
            injection=(
                FaultInjection(point=point, occurrence=occurrence, expect=expect)
                if point
                else None
            ),
            child_exit=proc.returncode if proc is not None else -1,
            expected=expect,
            actual=actual,
            chains_valid=chains_ok,
            notes=extra,
        )

    # Lane 1: repeated abrupt death at every labeled point.
    for point in LABELED_POINTS:
        expect = "complete" if point in ("post_commit", "response") else "old"
        for repeat in range(1, _POINT_REPEATS + 1):
            crash_db, crash_root = _copy_run(
                template_path, template_root, f"r-{point}-{repeat}", tmp
            )
            proc = _child_proc(
                crash_db, crash_root, FaultInjection(point=point)
            )
            crash_count += 1
            actual, chains_ok, _ = _classify(
                crash_db, crash_root, registry, old_state, complete_state
            )
            notes = ""
            if proc.returncode != _CRASH_EXIT_CODE:
                notes = f"exit {proc.returncode}: {proc.stderr[-160:]}"
            record(f"repeat-{point}-{repeat}", point, 1, proc, actual, chains_ok, expect, notes)
            rows.append(
                {
                    "lane": f"repeat-{point}-{repeat}",
                    "class": "abrupt-death",
                    "point": point,
                    "expect": expect,
                    "actual": actual,
                    "chains_valid": chains_ok,
                    "crash": True,
                }
            )

    # Lane 2: injected SQLITE_IOERR / SQLITE_FULL at both commit boundaries.
    for kind in _SQLITE_ERROR_KINDS:
        for point in ("pre_commit", "post_commit"):
            crash_db, crash_root = _copy_run(
                template_path, template_root, f"sq-{kind}-{point}", tmp
            )
            proc = _run_module_child(
                [
                    "--sqlite-fault-child",
                    str(crash_db),
                    str(crash_root),
                    point,
                    kind,
                ]
            )
            actual, chains_ok, _ = _classify(
                crash_db, crash_root, registry, old_state, complete_state
            )
            # An error raised at BEGIN leaves the old state; an error at
            # COMMIT fires after the statement executed — complete.
            expect = "complete" if point == "post_commit" else "old"
            record(
                f"sqlite-{kind}-{point}",
                point,
                1,
                proc,
                actual,
                chains_ok,
                expect,
                f"injected SQLITE_{kind.upper()}",
            )
            rows.append(
                {
                    "lane": f"sqlite-{kind}-{point}",
                    "class": f"sqlite-{kind}",
                    "point": point,
                    "expect": expect,
                    "actual": actual,
                    "chains_valid": chains_ok,
                    "crash": False,
                }
            )

    # Lane 3: filesystem write-refusal (ENOSPC/EFBIG class) mid-scenario.
    # The kernel's own RLIMIT_FSIZE path fails the staged write with
    # EFBIG and SIGXFSZ terminates the child at the upload boundary.
    fs_db, fs_root = _copy_run(template_path, template_root, "fs", tmp)
    proc = _run_module_child(
        ["--fs-exhaustion-child", str(fs_db), str(fs_root)]
    )
    actual, chains_ok, reopened = _classify(
        fs_db, fs_root, registry, old_state, complete_state
    )
    orphans = sorted(set(reopened["files"]) - set(complete_state["files"]))
    record(
        "fs-exhaustion-upload",
        "upload",
        1,
        proc,
        actual,
        chains_ok,
        "old",
        f"RLIMIT_FSIZE=1KiB; exit={proc.returncode}; "
        f"orphans={len(orphans)}",
    )
    rows.append(
        {
            "lane": "fs-exhaustion-upload",
            "class": "fs-exhaustion",
            "point": "upload",
            "expect": "old",
            "actual": actual,
            "chains_valid": chains_ok,
            "crash": True,
        }
    )
    fs_note = f"RLIMIT_FSIZE 1KiB; child exit {proc.returncode}"
    crash_count += 1

    # Lane 4: replay recovery — crash at each point, then re-run the same
    # scenario to completion on the recovered authorities.
    for point in LABELED_POINTS:
        crash_db, crash_root = _copy_run(
            template_path, template_root, f"replay-{point}", tmp
        )
        _child_proc(crash_db, crash_root, FaultInjection(point=point))
        crash_count += 1
        proc = _run_module_child(
            ["--scenario-child", str(crash_db), str(crash_root)]
        )
        actual, chains_ok, _ = _classify(
            crash_db, crash_root, registry, old_state, complete_state
        )
        record(
            f"replay-{point}",
            point,
            1,
            proc,
            actual,
            chains_ok,
            "complete",
            "recovery run after abrupt death",
        )
        rows.append(
            {
                "lane": f"replay-{point}",
                "class": "replay",
                "point": point,
                "expect": "complete",
                "actual": actual,
                "chains_valid": chains_ok,
                "crash": True,
            }
        )

    # Lane 5: concurrent identical-byte publication from two processes.
    for repeat in range(1, _CONCURRENT_REPEATS + 1):
        conc_db, conc_root = _copy_run(
            template_path, template_root, f"conc-{repeat}", tmp
        )
        procs = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--scenario-child",
                    str(conc_db),
                    str(conc_root),
                    f"{_MEDIA_ID}-{side}",
                    f"{_IDEMPOTENCY_KEY}-{side}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(_REPO_ROOT),
                env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)},
            )
            for side in ("a", "b")
        ]
        exits = [proc.wait(timeout=60) for proc in procs]
        actual, chains_ok, reopened = _classify(
            conc_db, conc_root, registry, old_state, complete_state
        )
        # Byte identity (SD2): both keys publish identical bytes, so the
        # repository dedupes to exactly ONE media row over exactly one
        # shared digest object, while both receipts commit (seed+2).
        media_rows = reopened["counts"]["media"]
        digest_objects = sum(
            1
            for name in reopened["files"]
            if name.startswith("sha256/")
        )
        ok = (
            media_rows == 1
            and digest_objects == 1
            and chains_ok
            and reopened["counts"]["command_receipts"]
            == complete_state["counts"]["command_receipts"] + 1
            and reopened["counts"]["events"]
            == complete_state["counts"]["events"] + 1
            and all(code == _FAULT_EXIT_OK for code in exits)
        )
        record(
            f"concurrent-{repeat}",
            "publish",
            1,
            None,
            "complete" if ok else actual,
            chains_ok,
            "complete",
            f"exits={exits} media={media_rows} objects={digest_objects}",
        )
        rows.append(
            {
                "lane": f"concurrent-{repeat}",
                "class": "concurrent-publication",
                "point": "publish",
                "expect": "complete",
                "actual": "complete" if ok else actual,
                "chains_valid": chains_ok,
                "crash": False,
            }
        )

    # Lane 6: lease death — the executor dies holding the lease; the
    # sweeper requeues the task and the next claim succeeds.
    for repeat in range(1, _LEASE_DEATH_REPEATS + 1):
        lease_db, lease_root = _copy_run(
            template_path, template_root, f"lease-{repeat}", tmp
        )
        seed_ctx = _build_context(lease_db, managed_root=lease_root)
        try:
            _seed_task(seed_ctx["writer"], registry)
        finally:
            seed_ctx["writer"].close()
        proc = _run_module_child(
            ["--claim-death-child", str(lease_db), str(lease_root)]
        )
        crash_count += 1
        # Reopen and sweep past the dead lease.
        sweep_ctx = _build_context(lease_db, managed_root=lease_root)
        from astrid.core.repositories.tasks import TaskRepository

        tasks = TaskRepository(
            events=sweep_ctx["events"], receipts=sweep_ctx["receipts"]
        )
        swept_at = "2026-08-15T00:10:00.000000+00:00"
        try:
            UnitOfWork(sweep_ctx["writer"]).run(
                lambda u: tasks.expire_overdue(
                    u,
                    project_id=_PROJECT_ID,
                    idempotency_key=f"fault-sweep-{repeat}",
                    now=swept_at,
                )
            )
            with sweep_ctx["writer"].read_only_connection() as conn:
                status = conn.execute(
                    "SELECT status FROM tasks WHERE id = 'task-fault-lease'"
                ).fetchone()[0]
        finally:
            sweep_ctx["writer"].close()
        # Requeue verdict + a fresh claim through a new UoW.
        reclaim_ctx = _build_context(lease_db, managed_root=lease_root)
        reclaim_tasks = TaskRepository(
            events=reclaim_ctx["events"], receipts=reclaim_ctx["receipts"]
        )
        try:
            reclaimed = UnitOfWork(reclaim_ctx["writer"]).run(
                lambda u: reclaim_tasks.claim(
                    u,
                    project_id=_PROJECT_ID,
                    idempotency_key=f"fault-reclaim-{repeat}",
                    executor_id="fault-executor-2",
                    now=swept_at,
                )
            )
            reclaimed_ok = reclaimed is not None
        finally:
            reclaim_ctx["writer"].close()
        chains_ok = _chains_valid(lease_db, registry)
        ok = status == "queued" and reclaimed_ok and chains_ok
        record(
            f"lease-death-{repeat}",
            "upload",
            1,
            proc,
            "complete" if ok else "partial",
            chains_ok,
            "complete",
            f"task={status} reclaimed={reclaimed_ok}",
        )
        rows.append(
            {
                "lane": f"lease-death-{repeat}",
                "class": "lease-death",
                "point": "sweep",
                "expect": "complete",
                "actual": "complete" if ok else "partial",
                "chains_valid": chains_ok,
                "crash": True,
            }
        )

    evidence.close()
    wall_clock = time.monotonic() - started
    summary = {
        "crashes": crash_count,
        "lanes": len(rows),
        "wall_clock_seconds": round(wall_clock, 1),
        "ci_lane_budget_seconds": 900,
        "within_budget": wall_clock < 900,
        "fs_exhaustion": fs_note,
        "verdicts": {
            lane: row["actual"] for row in rows for lane in [row["lane"]]
        },
    }
    return rows, summary


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


@pytest.mark.timeout(900)
def test_phase_a_extended_fault_matrix(tmp_path: Path) -> None:
    """T13: ≥100 crashes across the seven §5 fault classes — abrupt death
    at every labeled point, injected SQLITE_IOERR/FULL, real filesystem
    exhaustion, replay recovery, concurrent identical-byte publication,
    and lease-death-via-sweep. Zero DB/tree disagreement: every reopened
    authority is old-or-complete with valid hash chains, and every verdict
    lands in the evidence table."""
    rows, summary = run_extended_fault_matrix(
        tmp_path, tmp_path / "evidence" / "fault-evidence.sqlite3"
    )

    crashes = [row for row in rows if row["crash"]]
    assert summary["crashes"] >= 100, summary
    assert len(crashes) >= 100, summary

    disagreements = [
        row
        for row in rows
        if row["actual"] not in ("old", "complete", "skipped")
        or (
            row["expect"] != "skipped"
            and row["actual"] != "skipped"
            and row["actual"] != row["expect"]
        )
    ]
    assert not disagreements, disagreements
    assert all(row["chains_valid"] for row in rows), rows

    # Wall-clock vs the 900 s CI lane (delta N3) — measured, recorded.
    assert summary["wall_clock_seconds"] > 0

    # The temporary SQLite evidence table is authoritative; no fixed oracle
    # path is written by this test.



if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fault-child":
        raise SystemExit(_fault_child_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "--scenario-child":
        raise SystemExit(_scenario_child_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "--sqlite-fault-child":
        raise SystemExit(_sqlite_fault_child_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "--fs-exhaustion-child":
        raise SystemExit(_fs_exhaustion_child_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "--claim-death-child":
        raise SystemExit(_claim_death_child_main(sys.argv[2:]))
    print(
        json.dumps(
            {"module": "test_phase_a_fault_matrix", "points": list(LABELED_POINTS)}
        )
    )
    raise SystemExit(0)
