"""Read-only timeline observability utilities (m7).

Provides the shared resolver (slug / ULID / event-stream UUID) and the
ops-log reader that all observability CLI verbs route through.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astrid.threads.ids import is_ulid

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

    # --- Strategy 1: ULID-direct ---
    if is_ulid(slug_or_id):
        tdir = timeline_dir(project_slug, slug_or_id, root=root)
        if tdir.is_dir():
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

    # --- Strategy 2: event-stream UUID (check before slug to avoid slug validation) ---
    _is_uuid = _looks_like_uuid(slug_or_id)
    if _is_uuid:
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
    """Read ``assembly.identity.json``, returning None on any error."""
    from astrid.core.project.jsonio import read_json

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
    from astrid.core.project.jsonio import read_json

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
