"""Single kernel reader helper (R3.2).

ONE store, ONE path: callers that previously opened ``kernel.sqlite3`` with
raw ``sqlite3.connect(..., mode=ro)`` now call these two helpers, which open
through :func:`astrid.core.store.database.open_database` (read-only, probe)
and resolve ``slug ↔ ULID`` project identity once.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator

from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.kernel.database import resolve_kernel_database_path
from astrid.core.migrations.runner import MigrationError, probe_database
from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry

_ACTIVE_SCHEMA_REGISTRY: ContextVar[FrozenSchemaPackRegistry | None] = ContextVar(
    "astrid_active_schema_registry", default=None
)


def current_schema_registry() -> FrozenSchemaPackRegistry | None:
    """Return the registry bound to the current operation, if any."""

    return _ACTIVE_SCHEMA_REGISTRY.get()


def _db_path(projects_root: Path) -> Path | None:
    """Compatibility wrapper around the shared database-authority policy."""

    return resolve_kernel_database_path(projects_root)


def _read_registry(
    registry: FrozenSchemaPackRegistry | None,
) -> FrozenSchemaPackRegistry:
    """Return the exact registry supplied by this operation.

    Kernel reads may run inside :func:`schema_registry_context`, but they
    never construct or discover a standard registry themselves.  A missing
    registry is an invalid operation composition and fails closed.
    """

    effective = registry if registry is not None else current_schema_registry()
    if effective is None:
        raise MigrationError(
            "kernel read requires an operation-bound FrozenSchemaPackRegistry"
        )
    return effective


def _open_complete_read_only(
    db_path: Path,
    registry: FrozenSchemaPackRegistry,
) -> sqlite3.Connection:
    """Open a read-only database only after its migration head is complete."""

    probe = probe_database(db_path, registry)
    if not probe.exists:
        raise FileNotFoundError(
            f"cannot open database read-only: {db_path} does not exist"
        )
    expected = {(migration.pack, migration.version) for migration in registry.migrations}
    applied = {(migration.pack, migration.version) for migration in probe.applied}
    if applied != expected:
        missing = sorted(expected - applied)
        unexpected = sorted(applied - expected)
        raise MigrationError(
            "kernel read refused incomplete migration state"
            f" (missing={missing!r}, unexpected={unexpected!r})"
        )
    from astrid.core.store.database import open_database

    return open_database(db_path, registry, read_only=True)


@contextmanager
def schema_registry_context(
    registry: FrozenSchemaPackRegistry,
) -> Iterator[None]:
    """Bind one composed registry to nested canonical kernel reads.

    Capability execution can perform a read after the outer SDK has admitted
    the task.  A context variable carries the client's exact composition into
    those in-process reads without a process-global mutable registry or an
    ambient auto-discovery of arbitrary schemas.
    """

    token = _ACTIVE_SCHEMA_REGISTRY.set(registry)
    try:
        yield
    finally:
        _ACTIVE_SCHEMA_REGISTRY.reset(token)


def _resolve_project_id(conn: sqlite3.Connection, slug: str) -> str | None:
    # Slug-first, then raw id fallback. Narrow to sqlite3.Error at caller.
    row = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
    if row is not None:
        return str(row[0] if row[0] is not None else row["id"])
    row2 = conn.execute("SELECT id FROM projects WHERE id = ?", (slug,)).fetchone()
    if row2 is not None:
        return str(row2[0] if row2[0] is not None else row2["id"])
    return None


def kernel_run_info(
    slug: str,
    run_id: str,
    *,
    projects_root: str | Path | None = None,
    root: str | Path | None = None,
    registry: FrozenSchemaPackRegistry | None = None,
) -> dict[str, Any] | None:
    """Return kernel run info for one project/run, or None.

    Resolves ``slug → project_id (ULID)`` correctly via the projects table
    (no slug-as-id fallback leaking into ``runs.project_id``), then loads the
    run row and first-child capability/spec. Uses :func:`open_database`
    read-only; callers see ``sqlite3.Error`` only.
    """
    raw_root = projects_root if projects_root is not None else root
    pr = resolve_projects_root(raw_root)
    db_path = _db_path(pr)
    if db_path is None or not db_path.is_file():
        return None
    try:
        conn = _open_complete_read_only(db_path, _read_registry(registry))
    except (sqlite3.Error, FileNotFoundError, OSError):
        return None
    try:
        conn.row_factory = sqlite3.Row
        project_id = _resolve_project_id(conn, slug)
        effective_pid = project_id if project_id is not None else slug
        row = conn.execute(
            "SELECT id, project_id, status, kind, title FROM runs WHERE id = ? AND project_id = ?",
            (run_id, effective_pid),
        ).fetchone()
        if row is None:
            if project_id is not None and project_id != slug:
                row = conn.execute(
                    "SELECT id, project_id, status, kind, title FROM runs WHERE id = ? AND project_id = ?",
                    (run_id, slug),
                ).fetchone()
            if row is None:
                return None
        t = conn.execute(
            "SELECT id, capability, spec_json FROM tasks WHERE run_id = ? AND project_id = ? ORDER BY run_ordinal ASC LIMIT 1",
            (str(row["id"]), str(row["project_id"])),
        ).fetchone()
        capability = str(t["capability"]) if t is not None and t["capability"] is not None else None
        task_id = str(t["id"]) if t is not None and t["id"] is not None else None
        timeline_ids = None
        if t is not None and t["spec_json"] is not None:
            try:
                import json as _json

                spec = _json.loads(str(t["spec_json"]))
                if isinstance(spec, dict):
                    md = spec.get("metadata")
                    if isinstance(md, dict) and md.get("timeline_ids") is not None:
                        timeline_ids = md.get("timeline_ids")
                    else:
                        timeline_ids = spec.get("timeline_ids")
                    if timeline_ids is None and "step" in spec:
                        timeline_ids = spec.get("timeline_ids")
            except (ValueError, TypeError):
                timeline_ids = None
        return {
            "id": str(row["id"]),
            "project_id": str(row["project_id"]),
            "project_slug": slug,
            "run_id": str(row["id"]),
            "status": str(row["status"]),
            "kind": str(row["kind"]) if row["kind"] is not None else None,
            "title": row["title"],
            "capability": capability,
            "task_id": task_id,
            "tool_id": capability,
            "timeline_ids": timeline_ids,
        }
    except sqlite3.Error:
        return None
    finally:
        try:
            conn.close()
        except sqlite3.Error:
            pass


def kernel_runs_for_project(
    slug: str,
    *,
    projects_root: str | Path | None = None,
    root: str | Path | None = None,
    registry: FrozenSchemaPackRegistry | None = None,
) -> list[str]:
    """Return ordered run ids for one project slug (kernel-first, empty if no DB)."""
    raw_root = projects_root if projects_root is not None else root
    pr = resolve_projects_root(raw_root)
    db_path = _db_path(pr)
    if db_path is None or not db_path.is_file():
        return []
    try:
        conn = _open_complete_read_only(db_path, _read_registry(registry))
    except (sqlite3.Error, FileNotFoundError, OSError):
        return []
    try:
        conn.row_factory = sqlite3.Row
        project_id = _resolve_project_id(conn, slug)
        effective_pid = project_id if project_id is not None else slug
        rows = conn.execute(
            "SELECT id FROM runs WHERE project_id = ? ORDER BY id ASC",
            (effective_pid,),
        ).fetchall()
        if rows:
            return [str(r[0] if r[0] is not None else r["id"]) for r in rows]
        if project_id is not None and project_id != slug:
            rows2 = conn.execute(
                "SELECT id FROM runs WHERE project_id = ? ORDER BY id ASC",
                (slug,),
            ).fetchall()
            if rows2:
                return [str(r[0] if r[0] is not None else r["id"]) for r in rows2]
        return []
    except sqlite3.Error:
        return []
    finally:
        try:
            conn.close()
        except sqlite3.Error:
            pass
