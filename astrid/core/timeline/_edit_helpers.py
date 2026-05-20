"""Shared internal helpers for timeline edit modules.

Extracted from ``clip_edits.py`` to avoid duplication across the seven
secondary domain edit modules (transition_edits, effect_edits, theme_edits,
track_edits, audio_edits, pool_edits, arrangement_edits).

Every public mutation function in the edit modules uses:

* ``_resolve_backend`` — resolve (timeline_id, timeline_home, backend)
* ``_materialize`` — synchronous compatibility materializer (m4 removal seam)
* ``_default_actor`` — sensible system actor for editing operations
* ``TimelineEditError`` — shared exception base caught by the CLI handler
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.core.project.jsonio import read_json

from .assembly_helper import materialize_event
from .eventlog import EventLogBackend, select_timeline_backend
from .events.schema import TimelineActor, TimelineEvent
from .paths import assembly_identity_path, find_timeline_by_slug


# ---------------------------------------------------------------------------
# Shared exception base
# ---------------------------------------------------------------------------


class TimelineEditError(RuntimeError):
    """Raised when a timeline edit cannot be completed.

    All domain edit modules (clip_edits, transition_edits, effect_edits,
    theme_edits, track_edits, audio_edits, pool_edits, arrangement_edits)
    raise this exception or a subclass.  The CLI entrypoint catches it
    via a single ``except TimelineEditError`` clause.
    """


# Backward-compatible alias for clip_edits
ClipEditError = TimelineEditError


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_backend(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
) -> tuple[str, Path, EventLogBackend]:
    """Look up *slug* in *project_slug*, read the identity sidecar, and
    return ``(timeline_id, timeline_home, backend)``.

    Raises ``TimelineEditError`` when the timeline cannot be found or its
    identity sidecar is missing/malformed.
    """
    found = find_timeline_by_slug(project_slug, slug, root=root)
    if found is None:
        raise TimelineEditError(
            f"timeline '{slug}' not found in project '{project_slug}'"
        )
    ulid, tdir = found

    identity = read_json(assembly_identity_path(project_slug, ulid, root=root))
    if not isinstance(identity, dict):
        raise TimelineEditError("timeline identity sidecar is malformed")

    timeline_id = identity.get("timeline_id")
    if not isinstance(timeline_id, str) or not timeline_id:
        raise TimelineEditError("timeline identity sidecar is missing timeline_id")

    preferred_backend = identity.get("backend")
    if preferred_backend is not None and not isinstance(preferred_backend, str):
        raise TimelineEditError("timeline identity sidecar has malformed backend")

    _stream, backend = select_timeline_backend(
        timeline_id=timeline_id,
        timeline_home=tdir,
        preferred_backend=preferred_backend,
    )
    return timeline_id, tdir, backend


def _materialize(tdir: Path, event: TimelineEvent) -> None:
    """Synchronous compatibility materializer call — m4 removal seam.

    Keeps ``assembly.json`` in sync with the event stream so that
    readers like ``crud.show_timeline()`` see the latest state
    before projection becomes authoritative in m4.

    A crash between ``append_event`` and this call leaves the event log
    ahead of ``assembly.json``.  Accept this window for m2+m3; m4 projection
    will close it.
    """
    materialize_event(tdir, event)


def _default_actor(fn_name: str) -> TimelineActor:
    """Return a sensible system actor for timeline editing operations."""
    return TimelineActor(
        type="system",
        id=f"timeline-edits:{fn_name}",
        display="timeline-edits",
    )
