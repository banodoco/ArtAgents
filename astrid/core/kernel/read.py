"""Single kernel reader helper (R3.2).

ONE store, ONE path: readers resolve the canonical managed database through
the projects-root path helper and open it read-only through the application
boundary, resolving ``slug ↔ ULID`` project identity once.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator

from astrid.core.foundation.project_paths import derive_database_path, resolve_projects_root
from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry

_ACTIVE_SCHEMA_REGISTRY: ContextVar[FrozenSchemaPackRegistry | None] = ContextVar(
    "astrid_active_schema_registry", default=None
)


def _db_path(projects_root: Path) -> Path | None:
    """Return the canonical managed database path."""

    return derive_database_path(projects_root)


def _read_registry(
    registry: FrozenSchemaPackRegistry | None,
) -> FrozenSchemaPackRegistry:
    """Return the database composition used by this read.

    Project databases are the standard Astrid composition, not core-only
    stores: their migration ledger includes the in-tree timeline, shots, and
    references packs.  Core-only readers therefore fail with
    ``MigrationTooNewError`` as soon as one of those packs has been used.  A
    caller handling an explicitly extended composition can still provide its
    already-composed registry; the default only chooses the standard in-tree
    composition and never weakens migration validation.
    """

    if registry is None:
        registry = _ACTIVE_SCHEMA_REGISTRY.get()
    if registry is not None:
        return registry
    from astrid.core.schema_packs.standard import build_standard_registry

    return build_standard_registry()


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
        from astrid.core.store.database import open_database

        conn = open_database(db_path, _read_registry(registry), read_only=True)
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
        from astrid.core.store.database import open_database

        conn = open_database(db_path, _read_registry(registry), read_only=True)
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
