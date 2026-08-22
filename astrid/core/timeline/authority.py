"""Single-authority marker helper (R5).

Centralizes the authority-state classification for a timeline: whether the
timeline is marked as backfilled (SQLite authority) or legacy (file authority).

Every request path must consult this helper before mixing authorities for one
timeline (R5). The helper fails closed on unreadable/corrupt markers (R4):
a corrupt ``backfill-state.json`` raises :class:`BackfillError` instead of
falling back to a file authority.
"""

from pathlib import Path

from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.integrations.reigh.bridge_service import derive_database_path


def _load_backfill_state(projects_root: Path):  # type: ignore[no-untyped-def]
    import importlib as _il
    mod = _il.import_module("astrid.packs.timeline.backfill")
    return mod.read_backfill_state(projects_root)


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
