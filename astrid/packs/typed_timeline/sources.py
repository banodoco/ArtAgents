from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence



def _row_to_dict(row: Any) -> dict[str, Any]:
    # RunawayTransitionReadModel or sqlite Row mapping
    if hasattr(row, "to_dict"):
        return row.to_dict()  # type: ignore
    if isinstance(row, Mapping):
        return dict(row)
    # sqlite Row
    try:
        return dict(row)
    except Exception:
        return {k: row[k] for k in row.keys()}  # type: ignore


def _resolve_project_id(conn: sqlite3.Connection, project_id: str) -> str:
    """Resolve slug→id via projects table when project_id looks like a slug.

    The capability may supply the human slug (e.g. runaway-piano-colour-demo)
    but the kernel table is keyed by id. Probe: SELECT id, slug FROM projects
    WHERE slug='runaway-piano-colour-demo' must resolve to the kernel project
    that holds the 566 rows. Heuristic: slug contains '-' or is not a ULID/hash.
    """
    pid = str(project_id)
    looks_like_slug = "-" in pid
    # also treat non-ULID/non-hex as slug
    if not looks_like_slug:
        try:
            from astrid.core.ids import is_lowercase_ulid

            if not is_lowercase_ulid(pid):
                looks_like_slug = True
        except Exception:
            # fallback: if not 26-char alnum, treat as slug
            if len(pid) != 26 or not pid.isalnum():
                looks_like_slug = True
    if looks_like_slug:
        try:
            cur = conn.execute("SELECT id FROM projects WHERE slug = ?", (pid,))
            row = cur.fetchone()
            if row is not None:
                # Row may be sqlite3.Row or tuple
                try:
                    resolved = row["id"]
                except Exception:
                    resolved = row[0]
                if resolved:
                    return str(resolved)
            # also accept id == slug case (already stored as id)
            cur2 = conn.execute("SELECT id FROM projects WHERE id = ?", (pid,))
            row2 = cur2.fetchone()
            if row2 is not None:
                try:
                    return str(row2["id"])
                except Exception:
                    return str(row2[0])
        except Exception:
            pass
    return pid


def load_runaway_transitions(
    *,
    projects_root: Path | str | None = None,
    project_id: str,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    """Load runaway transitions via RunawayRepository.list, sorted by ordinal."""
    from astrid.core.foundation.project_paths import resolve_projects_root
    from astrid.core.events.registry import core_only_registry
    from astrid.core.receipts.service import ReceiptService
    from astrid.packs.runaway.repository import RunawayRepository

    if projects_root is None:
        projects_root = resolve_projects_root(None)
    else:
        projects_root = Path(projects_root).expanduser().resolve()
    db_path = Path(projects_root) / "kernel.sqlite3"
    # transaction-free read via sqlite connection
    import sqlite3 as _sqlite

    conn = _sqlite.connect(str(db_path))
    conn.row_factory = _sqlite.Row
    try:
        resolved_id = _resolve_project_id(conn, project_id)
        repo = RunawayRepository(receipts=ReceiptService())
        models = repo.list(conn, project_id=resolved_id, run_id=run_id)
        rows = [_row_to_dict(m) for m in models]
    finally:
        conn.close()
    # ensure ordinal stitch: sorted ascending
    rows.sort(key=lambda r: (int(r.get("ordinal", 0)), str(r.get("id", ""))))
    return rows


def load_json_rows(path: Path | str) -> list[dict[str, Any]]:
    p = Path(path).expanduser().resolve()
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        # support {rows: []} or {transitions: []} or {resolved_events: []}
        for key in ("rows", "transitions", "items", "resolved_events"):
            if key in data and isinstance(data[key], list):
                return [dict(r) if isinstance(r, Mapping) else {"value": r} for r in data[key]]
        # single object -> one row
        return [dict(data)]
    if isinstance(data, list):
        return [dict(r) if isinstance(r, Mapping) else {"value": r} for r in data]
    raise ValueError(f"unsupported JSON shape at {p}")


def load_rows(
    *,
    source: str,
    projects_root: Path | str | None = None,
    project_id: str | None = None,
    run_id: str | None = None,
    json_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    if source == "runaway":
        if not project_id:
            raise ValueError("project_id required for runaway source")
        return load_runaway_transitions(
            projects_root=projects_root, project_id=project_id, run_id=run_id
        )
    if source == "json":
        if json_path is None:
            raise ValueError("json_path required for json source")
        return load_json_rows(json_path)
    raise ValueError(f"unknown source {source!r}")
