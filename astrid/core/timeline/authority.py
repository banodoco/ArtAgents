"""Single-authority marker helper (R5).

Centralizes the authority-state classification for a timeline: whether the
timeline is marked as backfilled (SQLite authority) or legacy (file authority).

Every request path must consult this helper before mixing authorities for one
timeline (R5). The helper fails closed on unreadable/corrupt markers (R4):
a corrupt ``backfill-state.json`` raises :class:`BackfillError` instead of
falling back to a file authority.
"""
from __future__ import annotations

from pathlib import Path

from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.integrations.reigh.bridge_service import derive_database_path


def _projects_root_from_timeline_home(timeline_home: Path | str | None, fallback: Path | None = None) -> Path:
    """Derive projects_root from a timeline home layout ``<root>/<project>/timelines/<ulid>``."""
    if timeline_home is not None:
        try:
            p = Path(timeline_home)
            # timelines/<ulid> -> project dir -> projects root
            cand = p.parent.parent.parent
            if cand.is_dir():
                return cand
        except Exception:
            pass
    if fallback is not None:
        return Path(fallback)
    return resolve_projects_root(None)


def _load_backfill_state(projects_root: Path):  # type: ignore[no-untyped-def]
    import importlib as _il
    mod = _il.import_module("astrid.packs.timeline.backfill")
    return mod.read_backfill_state(projects_root)


def resolve_authoritative_timeline_id(
    timeline_home: Path | str | None,
    projects_root: str | Path | None = None,
) -> str | None:
    """Kernel-first authoritative timeline_id for *timeline_home* (H2).

    Derive the authoritative ``timeline_id`` from the directory ULID via the
    kernel ``timeline.created`` event and the backfill marker FIRST; consult
    ``assembly.identity.json`` ONLY for unbackfilled legacy dirs. Fail-closed
    on corrupt marker (BackfillError).

    Returns the authoritative id string, or ``None`` if no kernel or sidecar
    identity exists.
    """
    # 1) Kernel-first: ULID dir -> DB -> marker binding.
    if timeline_home is not None:
        try:
            th = Path(timeline_home)
            ulid = th.name
            # Derive projects_root for kernel lookup
            pr: Path
            if projects_root is not None:
                pr = Path(projects_root)
            else:
                # Try layout-derived first, then ambient
                try:
                    cand = th.parent.parent.parent
                    if cand.is_dir():
                        pr = cand
                    else:
                        pr = resolve_projects_root(None)
                except Exception:
                    pr = resolve_projects_root(None)
            db = derive_database_path(pr)
            if db.is_file() and ulid:
                # Fail-closed marker read
                state = _load_backfill_state(pr)
                # Kernel lookup by ULID (case-insensitive for ULID)
                # Tenant scoping: derive owning project from timeline_home layout
                # <root>/<project>/timelines/<ulid> => th.parent.parent.name is slug.
                project_slug: str | None = None
                try:
                    if th.parent.name == "timelines" and th.parent.parent.is_dir():
                        cand_slug = th.parent.parent.name
                        if cand_slug:
                            project_slug = cand_slug
                except Exception:
                    project_slug = None
                import sqlite3 as _sql

                conn = _sql.connect(f"file:{db}?mode=ro", uri=True)
                try:
                    conn.row_factory = _sql.Row
                    row = None
                    if project_slug is not None:
                        # Try to scope by project_id when layout derivable
                        try:
                            prow = conn.execute("SELECT id FROM projects WHERE slug=?", (project_slug,)).fetchone()
                            if prow is not None and prow["id"]:
                                pid = str(prow["id"])
                                row = conn.execute(
                                    "SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND project_id=? AND lower(json_extract(payload_json,'$.data.timeline_ulid'))=lower(?) LIMIT 1",
                                    (pid, ulid),
                                ).fetchone()
                            else:
                                # Layout derivable but project not in DB -> scoped miss (do NOT fall back to global, prevents cross-project leak)
                                row = None
                        except Exception:
                            # On lookup failure, fall back to unscoped for backward compat (non-layout case)
                            row = conn.execute(
                                "SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND lower(json_extract(payload_json,'$.data.timeline_ulid'))=lower(?) LIMIT 1",
                                (ulid,),
                            ).fetchone()
                    else:
                        # Non-layout fallback (e.g. in-memory tmp without <root>/<project>/timelines): keep current global behavior
                        row = conn.execute(
                            "SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND lower(json_extract(payload_json,'$.data.timeline_ulid'))=lower(?) LIMIT 1",
                            (ulid,),
                        ).fetchone()
                    if row and row["tid"]:
                        tid = str(row["tid"])
                        if tid in state:
                            return tid
                        # Not backfilled: fall through to sidecar for legacy decision
                        # (do not return kernel tid for unmarked legacy)
                finally:
                    conn.close()
        except Exception as exc:
            # Propagate BackfillError fail-closed — MUST be outside any swallowing handler.
            _is_bf = False
            try:
                import importlib as _il2

                _bf = _il2.import_module("astrid.packs.timeline.backfill")
                _is_bf = isinstance(exc, _bf.BackfillError)  # type: ignore[attr-defined]
            except Exception:
                _is_bf = False
            if _is_bf:
                raise
            # Non-marker errors are best-effort fallback to sidecar
            pass
    # 2) Legacy fallback: sidecar ONLY for unbackfilled dirs
    if timeline_home is not None:
        try:
            from astrid.core._shared.jsonio import read_json

            ip = Path(timeline_home) / "assembly.identity.json"
            if ip.is_file():
                raw = read_json(ip)
                if isinstance(raw, dict):
                    tid = raw.get("timeline_id")
                    if isinstance(tid, str) and tid.strip():
                        return tid.strip()
        except Exception:
            pass
    return None


def is_backfilled_timeline(timeline_id: str, projects_root: str | Path | None = None) -> bool:
    """Return True iff *timeline_id* is marked as backfilled (SQLite authority).

    Consults ``backfill-state.json`` beside the database. When the database
    file does not exist, the timeline is considered legacy (False). When the
    marker is present but unreadable or corrupt, the function raises
    :class:`BackfillError` (fail-closed) — callers must not silently degrade
    to a file backend.
    """
    pr = resolve_projects_root(projects_root)
    db = derive_database_path(pr)
    if not db.is_file():
        return False
    state = _load_backfill_state(pr)
    return timeline_id in state


def is_backfilled_by_marker(timeline_id: str, *, projects_root: Path) -> bool:
    """Variant that takes an already-resolved projects_root (no re-resolution)."""
    db = derive_database_path(projects_root)
    if not db.is_file():
        return False
    state = _load_backfill_state(projects_root)
    return timeline_id in state
