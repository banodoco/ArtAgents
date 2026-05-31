"""Theme edit primitives (m3 secondary).

Every public function resolves the timeline through the selector seam,
constructs a typed payload from the canonical event schema, emits the
event through ``EventLogBackend.append_event(...)``, and returns the
``TimelineEvent``.

Theme overrides are keyed by namespace (visual, generation, voice, audio,
pacing).  Nested values are treated as opaque JSON.
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
    ThemeOverriddenPayload,
    ThemeSetPayload,
    TimelineActor,
    TimelineEvent,
)

# Valid top-level theme override namespaces
_VALID_OVERRIDE_NAMESPACES = frozenset(
    {"visual", "generation", "voice", "audio", "pacing"}
)


# ---------------------------------------------------------------------------
# theme_set
# ---------------------------------------------------------------------------


def theme_set(
    project_slug: str,
    slug: str,
    *,
    theme_id: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``theme.set`` event to *slug* in *project_slug*.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        theme_id: The theme identifier to set as active.
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(theme_id, str) or not theme_id.strip():
        raise TimelineEditError("theme_id must be a non-empty string")

    act = actor or _default_actor("theme_set")
    event = backend.append_event(
        timeline_id,
        "theme.set",
        ThemeSetPayload(theme_id=theme_id),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
    return event


# ---------------------------------------------------------------------------
# theme_override
# ---------------------------------------------------------------------------


def theme_override(
    project_slug: str,
    slug: str,
    *,
    override_id: str,
    value: Any,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append a ``theme.overridden`` event to *slug* in *project_slug*.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        override_id: The override namespace (visual, generation, voice,
                     audio, pacing).
        value: The override value (must be JSON-serializable).
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend, _bootstrap = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(override_id, str) or not override_id.strip():
        raise TimelineEditError("override_id must be a non-empty string")
    if override_id not in _VALID_OVERRIDE_NAMESPACES:
        raise TimelineEditError(
            f"override_id must be one of {sorted(_VALID_OVERRIDE_NAMESPACES)}, "
            f"got {override_id!r}"
        )

    act = actor or _default_actor("theme_override")
    event = backend.append_event(
        timeline_id,
        "theme.overridden",
        ThemeOverriddenPayload(override_id=override_id, value=value),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event, timeline_id=timeline_id, backend=backend)
    return event
