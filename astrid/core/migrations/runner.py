"""Dependency-ordered, checksummed, forward-only SQLite migrations.

(m1 plan step 5.) This module is the single gate between a composed
:class:`~astrid.core.schema_packs.registry.FrozenSchemaPackRegistry` and a
mutable Astrid database:

- ``topological_migration_order`` orders every registered migration so pack
  dependencies (``depends_on``) are applied before their dependents and
  versions ascend within each pack; dependency cycles are rejected.
- ``probe_database`` opens the database **read-only** and never mutates it:
  it reads ``schema_migrations`` and rejects too-new schemas (applied version
  beyond the highest registered version, or an applied pack that is not part
  of this composition), migration name drift, and exact-byte SHA-256 checksum
  drift before any write transaction can start.
- ``apply_pending_migrations`` applies each pending migration in its own
  ``BEGIN IMMEDIATE`` transaction with the migration row recorded in the same
  transaction, so application is atomic and happens exactly once. PRAGMA
  statements (connection-level settings that cannot change inside a
  transaction) are executed before the transaction begins.

The runner never opens a database on its own and never imports the
capability-pack loader; it consumes only registry entries and filesystem
resources declared by the composed registry (decision artifact section 4).
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from astrid.core.migrations.catalog import CORE_PACK
from astrid.core.schema_packs.registry import (
    FrozenSchemaPackRegistry,
    RegisteredMigration,
)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MigrationError(RuntimeError):
    """Base error for schema migration ordering, probing, and application."""


class MigrationCycleError(MigrationError):
    """Raised when schema-pack ``depends_on`` declarations contain a cycle."""


class MigrationTooNewError(MigrationError):
    """Raised when the database schema is newer than the composed registry.

    The probe is read-only and nonmutating; the database is left byte-for-byte
    untouched when this error is raised.
    """


class MigrationNameDriftError(MigrationError):
    """Raised when an applied version's name no longer matches the registry."""


class MigrationChecksumDriftError(MigrationError):
    """Raised when an applied migration's recorded SHA-256 differs from the bytes."""


class MigrationApplyError(MigrationError):
    """Raised when a pending migration's SQL fails inside its transaction."""


# ---------------------------------------------------------------------------
# Immutable probe models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AppliedMigration:
    """One ``schema_migrations`` row exactly as recorded by the runner."""

    pack: str
    version: int
    name: str
    checksum: str
    applied_at: str


@dataclass(frozen=True, slots=True)
class DatabaseProbe:
    """Read-only view of an existing (or absent) database's migration state."""

    path: Path
    exists: bool
    applied: tuple[AppliedMigration, ...]


# ---------------------------------------------------------------------------
# Exact-byte SHA-256
# ---------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase hex SHA-256 of ``data`` (exact byte content)."""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Migration resource resolution
# ---------------------------------------------------------------------------


def pack_resource_root(pack_id: str) -> Path:
    """Return the filesystem root that a pack's migration paths are relative to.

    The kernel (``core``) declares no ``schema-pack.yaml``; its migration
    path ``sql/core/0001_initial.sql`` is relative to the
    ``astrid/core/migrations`` package. In-tree packs declare paths relative
    to ``astrid/packs/<pack_id>``. Both derive from this module's own
    location so the runner never imports the capability-pack machinery.
    """
    if pack_id == CORE_PACK:
        return Path(__file__).resolve().parent
    return Path(__file__).resolve().parents[2] / "packs" / pack_id


def read_migration_bytes(registered: RegisteredMigration) -> bytes:
    """Read the exact bytes of one registered migration's SQL resource.

    Raises :class:`MigrationError` when the declared resource is missing.
    """
    path = pack_resource_root(registered.pack) / registered.path
    if not path.is_file():
        raise MigrationError(
            f"migration resource for {registered.pack}/{registered.version} "
            f"({registered.name}) not found at {path}"
        )
    return path.read_bytes()


# ---------------------------------------------------------------------------
# Topological ordering and cycle detection
# ---------------------------------------------------------------------------


def topological_migration_order(
    registry: FrozenSchemaPackRegistry,
) -> tuple[RegisteredMigration, ...]:
    """Return every registered migration in deterministic forward-only order.

    Pack order is a post-order DFS over the ``depends_on`` graph (dependencies
    first, dependents last), so ``core`` always precedes the timeline, shots,
    and references packs. Migrations within one pack ascend by version.

    Raises :class:`MigrationError` for unregistered dependencies and
    :class:`MigrationCycleError` for dependency cycles.
    """
    for pack_id, manifest in registry.packs.items():
        for dependency in manifest.depends_on:
            if dependency.pack not in registry.packs:
                raise MigrationError(
                    f"pack {pack_id!r} depends on unregistered pack "
                    f"{dependency.pack!r}"
                )

    white, gray, black = 0, 1, 2
    color = {pack_id: white for pack_id in registry.packs}
    pack_order: list[str] = []

    def visit(pack_id: str, stack: list[str]) -> None:
        color[pack_id] = gray
        stack.append(pack_id)
        dependencies = sorted(registry.packs[pack_id].depends_on, key=lambda d: d.pack)
        for dependency in dependencies:
            dependency_id = dependency.pack
            if color[dependency_id] == gray:
                cycle_start = stack.index(dependency_id)
                cycle = stack[cycle_start:] + [dependency_id]
                raise MigrationCycleError(
                    "schema-pack dependency cycle detected: "
                    + " -> ".join(cycle)
                )
            if color[dependency_id] == white:
                visit(dependency_id, stack)
        stack.pop()
        color[pack_id] = black
        pack_order.append(pack_id)

    for pack_id in sorted(registry.packs):
        if color[pack_id] == white:
            visit(pack_id, [])

    ordered: list[RegisteredMigration] = []
    for pack_id in pack_order:
        ordered.extend(
            sorted(
                (m for m in registry.migrations if m.pack == pack_id),
                key=lambda m: m.version,
            )
        )
    return tuple(ordered)


# ---------------------------------------------------------------------------
# Reading and validating applied state (read-only, nonmutating)
# ---------------------------------------------------------------------------


def read_schema_migrations(conn: sqlite3.Connection) -> tuple[AppliedMigration, ...]:
    """Read every ``schema_migrations`` row, or ``()`` when the table is absent."""
    try:
        cursor = conn.execute(
            "SELECT pack, version, name, checksum, applied_at"
            " FROM schema_migrations ORDER BY pack, version"
        )
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return ()
        raise
    rows = cursor.fetchall()
    return tuple(
        AppliedMigration(
            pack=row[0],
            version=row[1],
            name=row[2],
            checksum=row[3],
            applied_at=row[4],
        )
        for row in rows
    )


def _validate_applied_migrations(
    applied: tuple[AppliedMigration, ...],
    registry: FrozenSchemaPackRegistry,
) -> None:
    """Reject too-new schemas, name drift, and checksum drift (no mutation)."""
    per_pack: dict[str, list[AppliedMigration]] = {}
    for row in applied:
        per_pack.setdefault(row.pack, []).append(row)

    for pack_id in sorted(per_pack):
        rows = sorted(per_pack[pack_id], key=lambda row: row.version)
        if pack_id not in registry.packs:
            raise MigrationTooNewError(
                "database contains applied migrations for pack "
                f"{pack_id!r}, which is not registered in this composition"
            )
        max_version = max(
            (m.version for m in registry.migrations if m.pack == pack_id),
            default=0,
        )
        for row in rows:
            if row.version > max_version:
                raise MigrationTooNewError(
                    f"database schema for pack {pack_id!r} is too new: "
                    f"applied version {row.version} exceeds the highest "
                    f"registered version {max_version}"
                )
            registered = registry.migration(pack_id, row.version)
            if registered is None:
                raise MigrationError(
                    f"applied migration {pack_id}/{row.version} has no "
                    "registered descriptor in this composition"
                )
            if registered.name != row.name:
                raise MigrationNameDriftError(
                    f"migration name drift for {pack_id}/{row.version}: "
                    f"database records name {row.name!r}, registry declares "
                    f"{registered.name!r}"
                )
            expected = sha256_bytes(read_migration_bytes(registered))
            if expected != row.checksum:
                raise MigrationChecksumDriftError(
                    f"migration checksum drift for {pack_id}/{row.version} "
                    f"({registered.name}): database records {row.checksum}, "
                    f"registered file bytes hash to {expected}"
                )


def probe_database(
    path: str | Path,
    registry: FrozenSchemaPackRegistry,
) -> DatabaseProbe:
    """Probe a database read-only and reject incompatible applied state.

    This is the nonmutating too-new probe: the database is opened with
    ``mode=ro``, no PRAGMA is written, and no transaction is started. An
    absent file is a fresh database with no applied migrations. Incompatible
    state raises :class:`MigrationTooNewError`, :class:`MigrationNameDriftError`,
    or :class:`MigrationChecksumDriftError` before any write is possible.
    """
    db_path = Path(path)
    if not db_path.exists():
        return DatabaseProbe(path=db_path, exists=False, applied=())
    conn = sqlite3.connect(
        f"file:{db_path}?mode=ro", uri=True, isolation_level=None
    )
    try:
        applied = read_schema_migrations(conn)
    finally:
        conn.close()
    _validate_applied_migrations(applied, registry)
    return DatabaseProbe(path=db_path, exists=True, applied=applied)


# ---------------------------------------------------------------------------
# Statement splitting and transactional application
# ---------------------------------------------------------------------------


def _split_sql_statements(sql: str) -> list[str]:
    """Split one SQL script into statements on ``;`` outside string literals.

    Full-line ``--`` comments are skipped and single-quoted strings (with the
    SQLite ``''`` escape) are preserved. The shipped migration files are
    simple DDL with no semicolons inside string literals; the state machine
    keeps the splitter correct even if that invariant is ever broken.
    """
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        if in_string:
            current.append(char)
            if char == "'":
                if index + 1 < length and sql[index + 1] == "'":
                    current.append(sql[index + 1])
                    index += 1
                else:
                    in_string = False
            index += 1
            continue
        if char == "'":
            in_string = True
            current.append(char)
            index += 1
            continue
        if char == "-" and index + 1 < length and sql[index + 1] == "-":
            while index < length and sql[index] != "\n":
                index += 1
            continue
        if char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _is_pragma_statement(statement: str) -> bool:
    return statement.lstrip().upper().startswith("PRAGMA")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_pending_migrations(
    conn: sqlite3.Connection,
    registry: FrozenSchemaPackRegistry,
    probe: DatabaseProbe,
) -> tuple[AppliedMigration, ...]:
    """Apply every pending registered migration exactly once, transactionally.

    Each pending migration runs inside its own ``BEGIN IMMEDIATE`` transaction:
    its DDL/DML statements and the ``schema_migrations`` row commit together or
    roll back together. PRAGMA statements (which cannot change inside a
    transaction) run before ``BEGIN IMMEDIATE``. Already-applied versions are
    skipped, so reopening a migrated database is a no-op.
    """
    applied_keys = {(row.pack, row.version) for row in probe.applied}
    recorded: list[AppliedMigration] = []
    for registered in topological_migration_order(registry):
        key = (registered.pack, registered.version)
        if key in applied_keys:
            continue
        sql_bytes = read_migration_bytes(registered)
        checksum = sha256_bytes(sql_bytes)
        statements = _split_sql_statements(sql_bytes.decode("utf-8"))
        pragma_statements = [
            statement
            for statement in statements
            if _is_pragma_statement(statement)
        ]
        ddl_statements = [
            statement
            for statement in statements
            if not _is_pragma_statement(statement)
        ]
        applied_at = _utc_now()

        for statement in pragma_statements:
            conn.execute(statement)

        conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in ddl_statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations"
                " (pack, version, name, checksum, applied_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    registered.pack,
                    registered.version,
                    registered.name,
                    checksum,
                    applied_at,
                ),
            )
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise MigrationApplyError(
                f"migration {registered.pack}/{registered.version} "
                f"({registered.name}) failed: {exc}"
            ) from exc
        recorded.append(
            AppliedMigration(
                pack=registered.pack,
                version=registered.version,
                name=registered.name,
                checksum=checksum,
                applied_at=applied_at,
            )
        )
    return tuple(recorded)


__all__ = [
    "AppliedMigration",
    "DatabaseProbe",
    "MigrationApplyError",
    "MigrationChecksumDriftError",
    "MigrationCycleError",
    "MigrationError",
    "MigrationNameDriftError",
    "MigrationTooNewError",
    "apply_pending_migrations",
    "pack_resource_root",
    "probe_database",
    "read_migration_bytes",
    "read_schema_migrations",
    "sha256_bytes",
    "topological_migration_order",
]
