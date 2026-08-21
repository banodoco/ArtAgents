"""SQLite database opening: read-only probe, writable PRAGMAs, migrations.

(m1 plan step 5.) :func:`open_database` is the only supported way to open an
Astrid database:

1. It probes the database **read-only** through the migration runner
   (:func:`astrid.core.migrations.runner.probe_database`), rejecting too-new
   schemas, name drift, and exact-byte checksum drift before any mutation is
   possible.
2. For a writable open it applies the declared connection-level PRAGMAs
   (:data:`astrid.core.migrations.catalog.CONNECTION_PRAGMAS`) and then
   applies pending migrations dependency-ordered and transactionally.

The writable PRAGMAs are inspectable afterwards through
:func:`inspect_connection_pragmas`, so tests and operators can prove
``foreign_keys``, ``journal_mode``, ``synchronous``, and ``busy_timeout``
settings on a live connection.

This module never imports the capability-pack loader or discovery machinery,
and a read-only open never mutates the database file.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from astrid.core.migrations.catalog import CONNECTION_PRAGMAS
from astrid.core.migrations.runner import (
    apply_pending_migrations,
    probe_database,
    read_only_uri,
)
from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry

PRAGMA_QUERIES: tuple[tuple[str, str], ...] = (
    ("foreign_keys", "PRAGMA foreign_keys"),
    ("journal_mode", "PRAGMA journal_mode"),
    ("synchronous", "PRAGMA synchronous"),
    ("busy_timeout", "PRAGMA busy_timeout"),
)
"""Inspectable writable PRAGMA surface (``name -> query``)."""


def apply_connection_pragmas(conn: sqlite3.Connection) -> None:
    """Apply the declared writable connection-level PRAGMAs.

    Each entry of :data:`CONNECTION_PRAGMAS` is a ``key = value`` fragment;
    this runs them exactly as cataloged on a writable connection.
    """
    for pragma in CONNECTION_PRAGMAS:
        conn.execute(f"PRAGMA {pragma}")


def inspect_connection_pragmas(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return the live values of the inspectable writable PRAGMAs.

    Example: ``{'foreign_keys': 1, 'journal_mode': 'wal', 'synchronous': 1,
    'busy_timeout': 5000}``.
    """
    return {
        name: conn.execute(query).fetchone()[0] for name, query in PRAGMA_QUERIES
    }


def open_database(
    path: str | Path,
    registry: FrozenSchemaPackRegistry,
    *,
    read_only: bool = False,
) -> sqlite3.Connection:
    """Open (and, for writable opens, migrate) an Astrid database.

    Read-only opens perform the same nonmutating incompatibility probe and
    then open with ``mode=ro``; they never apply PRAGMAs or migrations.
    Writable opens probe, apply the declared PRAGMAs, apply pending
    migrations forward-only and exactly once, and return the configured
    connection.
    """
    db_path = Path(path)
    probe = probe_database(db_path, registry)
    if read_only:
        if not probe.exists:
            raise FileNotFoundError(
                f"cannot open database read-only: {db_path} does not exist"
            )
        return sqlite3.connect(
            read_only_uri(db_path), uri=True, isolation_level=None
        )
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        apply_connection_pragmas(conn)
        apply_pending_migrations(conn, registry, probe)
    except Exception:
        conn.close()
        raise
    return conn


__all__ = [
    "PRAGMA_QUERIES",
    "apply_connection_pragmas",
    "inspect_connection_pragmas",
    "open_database",
]
