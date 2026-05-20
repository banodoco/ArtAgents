"""Arrangement edit primitives (m3 secondary).

Every public function resolves the timeline through the selector seam,
constructs a typed payload from the canonical event schema, emits the
event through ``EventLogBackend.append_event(...)``, and returns the
``TimelineEvent``.

``arrangement.replaced`` is the coarse-grained escape hatch for arrangement
changes that cannot yet be represented as smaller semantic events.
It must still be deterministic and replayable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._edit_helpers import (
    TimelineEditError,
    _default_actor,
    _materialize,
    _resolve_backend,
)
from .events.schema import (
    ArrangementReplacedPayload,
    TimelineActor,
    TimelineEvent,
)


# ---------------------------------------------------------------------------
# arrangement_replace
# ---------------------------------------------------------------------------


def arrangement_replace(
    project_slug: str,
    slug: str,
    *,
    arrangement: dict[str, Any],
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append an ``arrangement.replaced`` event to *slug* in *project_slug*.

    Fully replaces the existing arrangement with *arrangement*.  This is
    the coarse-grained escape hatch for arrangement changes that cannot
    yet be expressed as smaller semantic events.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        arrangement: The new arrangement dict (must be JSON-serializable).
                     Should contain at minimum ``{"clips": [...]}``.
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(arrangement, dict):
        raise TimelineEditError("arrangement must be a dict")

    act = actor or _default_actor("arrangement_replace")
    event = backend.append_event(
        timeline_id,
        "arrangement.replaced",
        ArrangementReplacedPayload(arrangement=dict(arrangement)),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event
