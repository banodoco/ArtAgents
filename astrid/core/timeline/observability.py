"""Read-only timeline observability utilities (m7).

Provides the shared resolver (slug / ULID / event-stream UUID) and the
ops-log reader that all observability CLI verbs route through.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astrid.core.threads.ids import is_ulid

from .eventlog.types import OpsLogEntry, ResolvedTarget
from .paths import (
    find_timeline_by_event_stream_id,
    find_timeline_by_slug,
    timeline_dir,
)

# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


def resolve_timeline_target(
    project_slug: str,
    slug_or_id: str,
    *,
    root: str | Path | None = None,
) -> ResolvedTarget:
    """Resolve a user-supplied *slug_or_id* to a concrete timeline target.

    Resolution chain (first match wins):

    1. **ULID-direct**: if *slug_or_id* is a valid Crockford ULID, look up
       ``<root>/<project_slug>/timelines/<ulid>``.  When the directory
       exists read ``assembly.identity.json`` for ``timeline_id`` and
       ``backend``, and ``display.json`` for the slug.

    2. **Slug**: call ``find_timeline_by_slug()``.

    3. **Event-stream UUID**: call ``find_timeline_by_event_stream_id()``.

    Returns a fully-populated ``ResolvedTarget``.

    Raises ``ValueError`` with a distinct message for each not-found case
    (never leaks filesystem paths).
    """
    # --- Strategy 1: ULID-direct (kernel-first for marked timelines) ---
    _is_ulid_obs = is_ulid(slug_or_id) or is_ulid(slug_or_id.upper()) or is_ulid(slug_or_id.lower())
    if _is_ulid_obs:
        # Normalize to upper for dir lookup (filesystem may be upper)
        _ulid_norm = slug_or_id.upper() if is_ulid(slug_or_id.upper()) else slug_or_id
        tdir = timeline_dir(project_slug, _ulid_norm, root=root)
        if not tdir.is_dir():
            # Try alternate case — guard invalid ULID casing (lower) that fails validation.
            tdir_alt = None
            try:
                if _ulid_norm != slug_or_id.lower():
                    tdir_alt = timeline_dir(project_slug, slug_or_id.lower(), root=root)
            except Exception:
                tdir_alt = None
            if tdir_alt is not None and tdir_alt.is_dir():
                tdir = tdir_alt
            elif not tdir.is_dir():
                # Fallback try original — also guarded.
                tdir_orig = None
                try:
                    tdir_orig = timeline_dir(project_slug, slug_or_id, root=root)
                except Exception:
                    tdir_orig = None
                if tdir_orig is not None and tdir_orig.is_dir():
                    tdir = tdir_orig
        if tdir.is_dir():
            # Kernel-first: authoritative id via directory binding
            _auth_ulid: str | None = None
            try:
                import importlib as _il_obs

                from astrid.core.foundation.project_paths import resolve_projects_root as _rr_obs
                from astrid.core.timeline.authority import (
                    resolve_authoritative_timeline_id as _res_auth_obs,
                )
                _bf_obs = _il_obs.import_module("astrid.packs.timeline.backfill")
                BackfillErrorObs = _bf_obs.BackfillError  # type: ignore[attr-defined]
                _pr_obs = None
                try:
                    _pr_obs = _rr_obs(root)
                    _cand = tdir.parent.parent
                    if _cand.name == "timelines" and _cand.parent.is_dir():
                        _pr_obs = _cand.parent.parent
                except Exception:
                    _pr_obs = None
                _auth_ulid = _res_auth_obs(tdir, _pr_obs)
                if isinstance(_auth_ulid, str) and _auth_ulid.strip():
                    try:
                        from astrid.core.timeline.authority import (
                            is_backfilled_timeline as _is_bf_obs,
                        )
                        if _is_bf_obs(_auth_ulid.strip(), _pr_obs):
                            # Marked: use kernel id, ignore sidecar
                            slug = _read_slug(tdir)
                            # For marked, also derive slug from authority repair if needed
                            return ResolvedTarget(
                                backend="local_fs",
                                timeline_id=_auth_ulid.strip(),
                                timeline_ulid=slug_or_id,
                                timeline_home=tdir,
                                slug=slug if slug is not None else slug_or_id,
                                backend_name_display="local_fs",
                            )
                    except BackfillErrorObs:
                        raise
                    except Exception:
                        pass
            except BackfillErrorObs:
                raise
            except Exception:
                pass
            identity = _read_identity(tdir)
            timeline_id = identity.get("timeline_id") if isinstance(identity, dict) else None
            if isinstance(timeline_id, str):
                backend = identity.get("backend", "local_fs") if isinstance(identity, dict) else "local_fs"
                if not isinstance(backend, str) or backend not in ("local_fs", "supabase"):
                    backend = "local_fs"
                slug = _read_slug(tdir)
                return ResolvedTarget(
                    backend=backend,  # type: ignore[arg-type]
                    timeline_id=timeline_id,
                    timeline_ulid=slug_or_id,
                    timeline_home=tdir,
                    slug=slug if slug is not None else slug_or_id,
                    backend_name_display=backend,
                )
        raise ValueError(
            f"timeline with ULID '{slug_or_id}' not found in project '{project_slug}'"
        )

    # --- Strategy 2: event-stream UUID (kernel-first for marked timelines) ---
    _is_uuid = _looks_like_uuid(slug_or_id)
    if _is_uuid:
        # Kernel-first: try to locate marked timeline by UUID via kernel/authority (project-scoped)
        try:
            import importlib as _il_uuid
            import sqlite3 as _sq_uuid

            from astrid.core.foundation.project_paths import resolve_projects_root as _rr_uuid
            from astrid.core.integrations.reigh.bridge_service import (
                derive_database_path as _dd_uuid,
            )
            _bf_uuid = _il_uuid.import_module("astrid.packs.timeline.backfill")
            _rbs_uuid = _bf_uuid.read_backfill_state  # type: ignore[attr-defined]
            BackfillErrorUuid = _bf_uuid.BackfillError  # type: ignore[attr-defined]
            _pr_uuid = _rr_uuid(root)
            _db_uuid = _dd_uuid(_pr_uuid)
            if _db_uuid.is_file():
                _st_uuid = _rbs_uuid(_pr_uuid)
                if isinstance(_st_uuid, dict) and slug_or_id in _st_uuid:
                    conn = _sq_uuid.connect(f"file:{_db_uuid}?mode=ro", uri=True)
                    try:
                        conn.row_factory = _sq_uuid.Row
                        _proj_uuid = conn.execute("SELECT id FROM projects WHERE slug=?", (project_slug,)).fetchone()
                        if _proj_uuid is not None:
                            _pid_uuid = str(_proj_uuid["id"])
                            r = conn.execute("SELECT json_extract(payload_json,'$.data.timeline_ulid') as ulid FROM events WHERE kind='timeline.created' AND project_id=? AND json_extract(payload_json,'$.data.timeline_id')=? LIMIT 1", (_pid_uuid, slug_or_id,)).fetchone()
                            if r and r["ulid"]:
                                ulid = str(r["ulid"])
                                tdir = timeline_dir(project_slug, ulid, root=root)
                                if tdir.is_dir():
                                    slug = _read_slug(tdir)
                                    # Verify directory is indeed marked via authority (fail-closed)
                                    try:
                                        from astrid.core.timeline.authority import (
                                            resolve_authoritative_timeline_id as _res_uuid,
                                        )
                                        _chk = _res_uuid(tdir, _pr_uuid)
                                        if _chk == slug_or_id:
                                            return ResolvedTarget(
                                                backend="local_fs",
                                                timeline_id=slug_or_id,
                                                timeline_ulid=ulid,
                                                timeline_home=tdir,
                                                slug=slug if slug is not None else ulid,
                                                backend_name_display="local_fs",
                                            )
                                    except BackfillErrorUuid:
                                        raise
                                    except Exception:
                                        pass
                    finally:
                        conn.close()
        except BackfillErrorUuid:
            raise
        except Exception:
            pass
        uuid_found = find_timeline_by_event_stream_id(project_slug, slug_or_id, root=root)
        if uuid_found is not None:
            ulid, slug = uuid_found
            tdir = timeline_dir(project_slug, ulid, root=root)
            return ResolvedTarget(
                backend="local_fs",
                timeline_id=slug_or_id,
                timeline_ulid=ulid,
                timeline_home=tdir,
                slug=slug,
                backend_name_display="local_fs",
            )
        raise ValueError(
            f"timeline with event-stream UUID '{slug_or_id}' not found in project '{project_slug}'"
        )
    # --- Strategy 3: slug ---
    try:
        found = find_timeline_by_slug(project_slug, slug_or_id, root=root)
    except Exception:
        found = None
    if found is not None:
        ulid, tdir = found
        # Kernel-first for marked timelines: authoritative id overrides stale sidecar
        _kid: str | None = None
        try:
            import importlib as _il_slug

            from astrid.core.foundation.project_paths import resolve_projects_root as _rr_slug
            from astrid.core.timeline.authority import (
                resolve_authoritative_timeline_id as _res_auth_slug,
            )
            _bf_slug = _il_slug.import_module("astrid.packs.timeline.backfill")
            BackfillErrorSlug = _bf_slug.BackfillError  # type: ignore[attr-defined]
            _pr_slug = None
            try:
                _pr_slug = _rr_slug(root)
            except Exception:
                _pr_slug = None
            _kid = _res_auth_slug(tdir, _pr_slug)
            if isinstance(_kid, str) and _kid.strip():
                try:
                    from astrid.core.timeline.authority import is_backfilled_timeline as _is_bf_slug
                    if _is_bf_slug(_kid.strip(), _pr_slug):
                        backend = "local_fs"
                        # Check supabase declaration from identity only for unbackfilled? For marked, keep local_fs sqlite will be chosen by selector
                        return ResolvedTarget(
                            backend="local_fs",  # type: ignore[arg-type]
                            timeline_id=_kid.strip(),
                            timeline_ulid=ulid,
                            timeline_home=tdir,
                            slug=slug_or_id,
                            backend_name_display="local_fs",
                        )
                except BackfillErrorSlug:
                    raise
                except Exception:
                    pass
        except BackfillErrorSlug:
            raise
        except Exception:
            pass
        identity = _read_identity(tdir)
        timeline_id = identity.get("timeline_id") if isinstance(identity, dict) else None
        backend = identity.get("backend", "local_fs") if isinstance(identity, dict) else "local_fs"
        if not isinstance(backend, str) or backend not in ("local_fs", "supabase"):
            backend = "local_fs"
        if isinstance(timeline_id, str):
            return ResolvedTarget(
                backend=backend,  # type: ignore[arg-type]
                timeline_id=timeline_id,
                timeline_ulid=ulid,
                timeline_home=tdir,
                slug=slug_or_id,
                backend_name_display=backend,
            )
        raise ValueError(
            f"timeline '{slug_or_id}' has no identity sidecar in project '{project_slug}'"
        )

    raise ValueError(
        f"timeline '{slug_or_id}' not found in project '{project_slug}'"
    )


# ---------------------------------------------------------------------------
# Ops log reader
# ---------------------------------------------------------------------------


def read_ops_log(timeline_home: str | Path) -> list[OpsLogEntry] | None:
    """Read ``events_ops.jsonl`` from *timeline_home*.

    Returns a list of ``OpsLogEntry`` when the file exists, or ``None``
    when it is absent (graceful absence — never raises).
    """
    ops_path = Path(timeline_home) / "events_ops.jsonl"
    if not ops_path.is_file():
        return None

    entries: list[OpsLogEntry] = []
    try:
        with ops_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entries.append(
                    OpsLogEntry(
                        ts=raw.get("ts", ""),
                        event_id=raw.get("event_id"),
                        kind=raw.get("kind"),
                        error=raw.get("error", "(unknown)"),
                        raw=raw,
                    )
                )
    except OSError:
        return None

    return entries if entries else None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_UUID_RE = __import__("re").compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _looks_like_uuid(value: str) -> bool:
    """Return True when *value* matches the standard UUID hex-dashed format."""
    return bool(_UUID_RE.match(value))


def _read_identity(timeline_home: Path) -> dict[str, Any] | None:
    """Read ``assembly.identity.json``, returning None on any error.

    SD1: ``source_timeline_id`` is audit provenance only and may equal
    ``timeline_id``.  Callers MUST use explicit ``provenance`` and
    ``backend`` fields, NOT infer imported/remote identity from
    ``timeline_id != source_timeline_id``.
    """
    from astrid.core._shared.jsonio import read_json

    identity_path = timeline_home / "assembly.identity.json"
    if not identity_path.is_file():
        return None
    try:
        raw = read_json(identity_path)
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _read_slug(timeline_home: Path) -> str | None:
    """Read the slug from ``display.json``, returning None on any error."""
    from astrid.core._shared.jsonio import read_json

    display_path = timeline_home / "display.json"
    if not display_path.is_file():
        return None
    try:
        raw = read_json(display_path)
    except Exception:
        return None
    if isinstance(raw, dict):
        slug = raw.get("slug")
        if isinstance(slug, str):
            return slug
    return None
