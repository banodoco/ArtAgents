"""Effect edit primitives (m3 secondary).

Every public function resolves the timeline through the selector seam,
constructs a typed payload from the canonical event schema, emits the
event through ``EventLogBackend.append_event(...)``, and returns the
``TimelineEvent``.

Effects are clip-attached, stored as ``clip["effects"]`` list.
Each effect is ``{"effect_id": str, "params": dict | None}``.
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
    EffectAddedPayload,
    EffectRemovedPayload,
    EffectTunedPayload,
    TimelineActor,
    TimelineEvent,
)


# ---------------------------------------------------------------------------
# effect_add
# ---------------------------------------------------------------------------


def effect_add(
    project_slug: str,
    slug: str,
    *,
    clip_id: str,
    effect_id: str,
    params: dict[str, Any] | None = None,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append an ``effect.added`` event to *slug* in *project_slug*.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        clip_id: The clip to attach the effect to.
        effect_id: The effect identifier.
        params: Optional effect parameters as a dict.
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_id, str) or not clip_id.strip():
        raise TimelineEditError("clip_id must be a non-empty string")
    if not isinstance(effect_id, str) or not effect_id.strip():
        raise TimelineEditError("effect_id must be a non-empty string")
    if params is not None and not isinstance(params, dict):
        raise TimelineEditError("params must be a dict when present")

    act = actor or _default_actor("effect_add")
    event = backend.append_event(
        timeline_id,
        "effect.added",
        EffectAddedPayload(
            clip_id=clip_id,
            effect_id=effect_id,
            params=dict(params) if params else None,
        ),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event


# ---------------------------------------------------------------------------
# effect_remove
# ---------------------------------------------------------------------------


def effect_remove(
    project_slug: str,
    slug: str,
    *,
    clip_id: str,
    effect_id: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append an ``effect.removed`` event to *slug* in *project_slug*.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        clip_id: The clip to remove the effect from.
        effect_id: The effect identifier to remove.
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_id, str) or not clip_id.strip():
        raise TimelineEditError("clip_id must be a non-empty string")
    if not isinstance(effect_id, str) or not effect_id.strip():
        raise TimelineEditError("effect_id must be a non-empty string")

    act = actor or _default_actor("effect_remove")
    event = backend.append_event(
        timeline_id,
        "effect.removed",
        EffectRemovedPayload(clip_id=clip_id, effect_id=effect_id),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event


# ---------------------------------------------------------------------------
# effect_tune
# ---------------------------------------------------------------------------


def effect_tune(
    project_slug: str,
    slug: str,
    *,
    clip_id: str,
    effect_id: str,
    param: str,
    value: Any,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> TimelineEvent:
    """Append an ``effect.tuned`` event to *slug* in *project_slug*.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        clip_id: The clip whose effect to tune.
        effect_id: The effect identifier.
        param: Parameter name to set.
        value: Parameter value (must be JSON-serializable).
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(clip_id, str) or not clip_id.strip():
        raise TimelineEditError("clip_id must be a non-empty string")
    if not isinstance(effect_id, str) or not effect_id.strip():
        raise TimelineEditError("effect_id must be a non-empty string")
    if not isinstance(param, str) or not param.strip():
        raise TimelineEditError("param must be a non-empty string")

    act = actor or _default_actor("effect_tune")
    event = backend.append_event(
        timeline_id,
        "effect.tuned",
        EffectTunedPayload(clip_id=clip_id, effect_id=effect_id, param=param, value=value),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event
