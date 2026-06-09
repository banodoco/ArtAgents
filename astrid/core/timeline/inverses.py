"""Inverse planning for timeline events.

Provides pure functions that, given a timeline event and its before/after
projection state, return an inverse event request that would undo the effect
of that event.

Inverse planning is a **pure function** — no backend calls, no side effects,
no filesystem access.  It uses prior projection state to recover removed
elements and falls back to a ``timeline.reverted`` request with before/after
projections when the event cannot be mechanically inverted.

Non-reversible event kinds (timeline.created, timeline.deleted, etc.) return
a ``timeline.reverted`` request instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from astrid.core.timeline.banodoco_schema import validate_timeline_config_for_container

from .events.schema import (
    ArrangementReplacedPayload,
    AudioBoundPayload,
    AudioUnboundPayload,
    ClipAddedPayload,
    ClipAnnotatedPayload,
    ClipMovedPayload,
    ClipRemovedPayload,
    ClipReplacedPayload,
    ClipRetimedPayload,
    ClipRetrackedPayload,
    ClipSwappedPayload,
    ClipTextSetPayload,
    EffectAddedPayload,
    EffectRemovedPayload,
    EffectTunedPayload,
    ErasedPayload,
    PoolAssetAddedPayload,
    PoolAssetRemovedPayload,
    PoolAssetScoredPayload,
    ThemeOverriddenPayload,
    ThemeSetPayload,
    TimelineConfigReplacedPayload,
    TimelineEvent,
    TrackAddedPayload,
    TrackRemovedPayload,
    TransitionRemovedPayload,
    TransitionSetPayload,
)

# ============================================================================
# Inverse request shape
# ============================================================================


@dataclass(frozen=True)
class InverseRequest:
    """Result of inverse planning for a single event.

    When *invertible* is False, the caller should use *revert_kind* and
    *revert_reason* to construct a ``timeline.reverted`` event with
    *before_projection* and *after_projection* for auditability.
    """

    invertible: bool
    """True when a mechanical inverse event was found."""

    inverse_kind: str | None = None
    """The event kind that would undo this event (e.g. 'clip.removed' for a clip.added)."""

    inverse_payload: dict[str, Any] | None = None
    """The payload for the inverse event."""

    revert_kind: str = "timeline.reverted"
    """Event kind when falling back to reverted (always 'timeline.reverted')."""

    revert_reason: str = ""
    """Human-readable reason for non-invertibility."""

    before_projection: dict[str, Any] | None = None
    """Projection state BEFORE the event (for audit when non-invertible)."""

    after_projection: dict[str, Any] | None = None
    """Projection state AFTER the event (for audit when non-invertible)."""


# ============================================================================
# Non-reversible event kinds
# ============================================================================

# Event kinds that are never blindly invertible — they have structural
# side effects (stream lifecycle, erasure, branching) that cannot be
# undone by a single domain event.
_NON_REVERSIBLE_KINDS: frozenset[str] = frozenset({
    "timeline.created",
    "timeline.imported",
    "timeline.deleted",
    "timeline.tombstoned",
    "timeline.erased",
    "timeline.recovered",
    "timeline.branched_from",
    "timeline.reverted",
})


# ============================================================================
# Internal helpers
# ============================================================================


def _non_invertible(
    event: TimelineEvent,
    before: dict[str, Any],
    after: dict[str, Any],
    reason: str,
) -> InverseRequest:
    """Build a non-invertible InverseRequest with before/after projections."""
    return InverseRequest(
        invertible=False,
        revert_kind="timeline.reverted",
        revert_reason=f"{event.kind} at {event.event_id}: {reason}",
        before_projection=before if before else None,
        after_projection=after if after else None,
    )


def _find_clip(before: dict[str, Any], clip_id: str) -> dict[str, Any] | None:
    """Find a clip dict in *before* projection state by clip_id."""
    clips = before.get("clips", []) if isinstance(before, dict) else []
    for clip in clips:
        if isinstance(clip, dict) and clip.get("id") == clip_id:
            return clip
    return None


# ============================================================================
# Factory for simple forward inverses (payload attrs → inverse payload)
# ============================================================================


def _forward(inverse_kind: str, *attrs: str):
    """Factory returning a handler that builds an InverseRequest from payload attributes.

    Used for event kinds whose inverse is simply: extract attrs from the
    payload and emit the inverse_kind with those attrs as the inverse payload.
    """
    def handler(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
        payload = event.payload
        return InverseRequest(
            invertible=True,
            inverse_kind=inverse_kind,
            inverse_payload={a: getattr(payload, a) for a in attrs},
        )
    return handler


# ============================================================================
# Individual inverse handlers (complex — require before-state lookups)
# ============================================================================


# -- clip.removed -----------------------------------------------------------

def _handle_clip_removed(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of clip.removed: re-add the clip using prior projection state."""
    payload = event.payload
    assert isinstance(payload, ClipRemovedPayload)  # guaranteed by dispatch
    clip_id = payload.clip_id
    before_clips = before.get("clips", []) if isinstance(before, dict) else []
    removed_clip = None
    removed_index = None
    for i, clip in enumerate(before_clips):
        if isinstance(clip, dict) and clip.get("id") == clip_id:
            removed_clip = dict(clip)
            removed_index = i
            break
    if removed_clip is None:
        return _non_invertible(
            event, before, after,
            f"clip {clip_id!r} not found in prior projection state",
        )
    position: dict[str, Any] | None = None
    if removed_index is not None:
        position = {"mode": "index", "index": removed_index}
    inverse: dict[str, Any] = {
        "clip_id": clip_id,
        "kind": removed_clip.get("kind")
        or ("text" if removed_clip.get("clipType") == "text" else "visual"),
        "track_id": removed_clip.get("track", "visual"),
        "asset_id": removed_clip.get("asset")
        or removed_clip.get("asset_id")
        or clip_id,
    }
    if position:
        inverse["position"] = position
    return InverseRequest(
        invertible=True,
        inverse_kind="clip.added",
        inverse_payload=inverse,
    )


# -- clip.moved -------------------------------------------------------------

def _handle_clip_moved(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of clip.moved: move the clip back to its previous position."""
    payload = event.payload
    assert isinstance(payload, ClipMovedPayload)
    clip_id = payload.clip_id
    before_clips = before.get("clips", []) if isinstance(before, dict) else []
    original_index = None
    for i, clip in enumerate(before_clips):
        if isinstance(clip, dict) and clip.get("id") == clip_id:
            original_index = i
            break
    if original_index is None:
        return _non_invertible(
            event, before, after,
            f"clip {clip_id!r} not found in prior projection state",
        )
    return InverseRequest(
        invertible=True,
        inverse_kind="clip.moved",
        inverse_payload={
            "clip_id": clip_id,
            "position": {"mode": "index", "index": original_index},
        },
    )


# -- clip.retracked ---------------------------------------------------------

def _handle_clip_retracked(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of clip.retracked: restore the clip's previous track."""
    payload = event.payload
    assert isinstance(payload, ClipRetrackedPayload)
    clip_id = payload.clip_id
    clip = _find_clip(before, clip_id)
    if clip is not None:
        previous_track = clip.get("track")
        if isinstance(previous_track, str) and previous_track:
            return InverseRequest(
                invertible=True,
                inverse_kind="clip.retracked",
                inverse_payload={
                    "clip_id": clip_id,
                    "track_id": previous_track,
                },
            )
    return _non_invertible(
        event, before, after,
        f"clip {clip_id!r} not found in prior projection state",
    )


# -- clip.retimed -----------------------------------------------------------

def _handle_clip_retimed(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of clip.retimed: restore original start/duration from prior state."""
    payload = event.payload
    assert isinstance(payload, ClipRetimedPayload)
    clip_id = payload.clip_id
    original = _find_clip(before, clip_id)
    if original is None:
        return _non_invertible(
            event, before, after,
            f"clip {clip_id!r} not found in prior projection state",
        )
    return InverseRequest(
        invertible=True,
        inverse_kind="clip.retimed",
        inverse_payload={
            "clip_id": clip_id,
            "start": float(original.get("start", 0)),
            "duration": float(original.get("duration", 0)),
        },
    )


# -- clip.replaced ----------------------------------------------------------

def _handle_clip_replaced(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of clip.replaced: restore original asset from prior state."""
    payload = event.payload
    assert isinstance(payload, ClipReplacedPayload)
    clip_id = payload.clip_id
    clip = _find_clip(before, clip_id)
    if clip is None:
        return _non_invertible(
            event, before, after,
            f"clip {clip_id!r} not found in prior projection state",
        )
    original_asset = clip.get("asset_id")
    if original_asset is None:
        return _non_invertible(
            event, before, after,
            f"clip {clip_id!r} not found in prior projection state",
        )
    return InverseRequest(
        invertible=True,
        inverse_kind="clip.replaced",
        inverse_payload={
            "clip_id": clip_id,
            "with_asset_id": original_asset,
        },
    )


# -- clip.text_set ----------------------------------------------------------

def _handle_clip_text_set(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of clip.text_set: restore original text from prior state."""
    payload = event.payload
    assert isinstance(payload, ClipTextSetPayload)
    clip_id = payload.clip_id
    clip = _find_clip(before, clip_id)
    original_text = clip.get("text", "") if clip else ""
    return InverseRequest(
        invertible=True,
        inverse_kind="clip.text_set",
        inverse_payload={
            "clip_id": clip_id,
            "text": original_text,
        },
    )


# -- clip.annotated ---------------------------------------------------------

def _handle_clip_annotated(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of clip.annotated: restore original note from prior state."""
    payload = event.payload
    assert isinstance(payload, ClipAnnotatedPayload)
    clip_id = payload.clip_id
    clip = _find_clip(before, clip_id)
    original_note = clip.get("note", "") if clip else ""
    return InverseRequest(
        invertible=True,
        inverse_kind="clip.annotated",
        inverse_payload={
            "clip_id": clip_id,
            "note": original_note,
        },
    )


# -- transition.removed -----------------------------------------------------

def _handle_transition_removed(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of transition.removed: re-set the transition from prior state."""
    payload = event.payload
    assert isinstance(payload, TransitionRemovedPayload)
    left_id = payload.left_clip_id
    clip = _find_clip(before, left_id)
    if clip is not None:
        transition = clip.get("transition")
        if isinstance(transition, dict):
            return InverseRequest(
                invertible=True,
                inverse_kind="transition.set",
                inverse_payload={
                    "left_clip_id": left_id,
                    "right_clip_id": transition.get("right_clip_id", ""),
                    "kind": transition.get("kind", "dissolve"),
                    "duration_seconds": float(transition.get("duration_seconds", 1.0)),
                },
            )
    return _non_invertible(
        event, before, after,
        f"prior transition state for {left_id!r} not found",
    )


# -- effect.removed ---------------------------------------------------------

def _handle_effect_removed(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of effect.removed: re-add the effect from prior state."""
    payload = event.payload
    assert isinstance(payload, EffectRemovedPayload)
    clip_id = payload.clip_id
    effect_id = payload.effect_id
    clip = _find_clip(before, clip_id)
    if clip is not None:
        effects = clip.get("effects", [])
        if isinstance(effects, list):
            for e in effects:
                if isinstance(e, dict) and e.get("effect_id") == effect_id:
                    inverse: dict[str, Any] = {
                        "clip_id": clip_id,
                        "effect_id": effect_id,
                    }
                    params = e.get("params")
                    if isinstance(params, dict):
                        inverse["params"] = dict(params)
                    return InverseRequest(
                        invertible=True,
                        inverse_kind="effect.added",
                        inverse_payload=inverse,
                    )
    return _non_invertible(
        event, before, after,
        f"prior effect {effect_id!r} on clip {clip_id!r} not found",
    )


# -- effect.tuned -----------------------------------------------------------

def _handle_effect_tuned(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of effect.tuned: restore original param value from prior state."""
    payload = event.payload
    assert isinstance(payload, EffectTunedPayload)
    clip_id = payload.clip_id
    effect_id = payload.effect_id
    param = payload.param
    clip = _find_clip(before, clip_id)
    if clip is not None:
        effects = clip.get("effects", [])
        if isinstance(effects, list):
            for e in effects:
                if isinstance(e, dict) and e.get("effect_id") == effect_id:
                    effects_params = e.get("params", {})
                    original = effects_params.get(param) if isinstance(effects_params, dict) else None
                    return InverseRequest(
                        invertible=True,
                        inverse_kind="effect.tuned",
                        inverse_payload={
                            "clip_id": clip_id,
                            "effect_id": effect_id,
                            "param": param,
                            "value": original,
                        },
                    )
    return _non_invertible(
        event, before, after,
        f"prior effect {effect_id!r} param {param!r} on clip {clip_id!r} not found",
    )


# -- track.removed ----------------------------------------------------------

def _handle_track_removed(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of track.removed: re-add the track from prior state."""
    payload = event.payload
    assert isinstance(payload, TrackRemovedPayload)
    track_id = payload.track_id
    before_tracks = before.get("tracks", []) if isinstance(before, dict) else []
    for track in before_tracks:
        if isinstance(track, dict) and track.get("id") == track_id:
            inverse: dict[str, Any] = {
                "track_id": track_id,
                "kind": track.get("kind", "visual"),
            }
            label = track.get("label")
            if isinstance(label, str) and label:
                inverse["label"] = label
            return InverseRequest(
                invertible=True,
                inverse_kind="track.added",
                inverse_payload=inverse,
            )
    return _non_invertible(
        event, before, after,
        f"track {track_id!r} not found in prior projection state",
    )


# -- audio.unbound ----------------------------------------------------------

def _handle_audio_unbound(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of audio.unbound: re-bind audio from prior state."""
    payload = event.payload
    assert isinstance(payload, AudioUnboundPayload)
    clip_id = payload.clip_id
    clip = _find_clip(before, clip_id)
    if clip is not None:
        asset_id = clip.get("asset_id", "")
        if asset_id:
            return InverseRequest(
                invertible=True,
                inverse_kind="audio.bound",
                inverse_payload={
                    "clip_id": clip_id,
                    "asset_id": asset_id,
                },
            )
    return _non_invertible(
        event, before, after,
        f"prior audio binding for clip {clip_id!r} not available",
    )


# -- theme.set --------------------------------------------------------------

def _handle_theme_set(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of theme.set: restore previous theme from prior state."""
    payload = event.payload
    assert isinstance(payload, ThemeSetPayload)
    before_theme = before.get("theme", "") if isinstance(before, dict) else ""
    return InverseRequest(
        invertible=True,
        inverse_kind="theme.set",
        inverse_payload={"theme_id": before_theme if before_theme else ""},
    )


# -- theme.overridden -------------------------------------------------------

def _handle_theme_overridden(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of theme.overridden: restore original override value from prior state."""
    payload = event.payload
    assert isinstance(payload, ThemeOverriddenPayload)
    override_id = payload.override_id
    before_overrides = before.get("theme_overrides", {}) if isinstance(before, dict) else {}
    original = before_overrides.get(override_id) if isinstance(before_overrides, dict) else None
    return InverseRequest(
        invertible=True,
        inverse_kind="theme.overridden",
        inverse_payload={
            "override_id": override_id,
            "value": original,
        },
    )


# -- pool.asset_removed -----------------------------------------------------

def _handle_pool_asset_removed(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of pool.asset_removed: re-add the asset from prior state."""
    payload = event.payload
    assert isinstance(payload, PoolAssetRemovedPayload)
    asset_id = payload.asset_id
    before_pool = before.get("pool", {}) if isinstance(before, dict) else {}
    before_entries = before_pool.get("entries", []) if isinstance(before_pool, dict) else []
    for entry in before_entries:
        if isinstance(entry, dict) and entry.get("asset_id") == asset_id:
            return InverseRequest(
                invertible=True,
                inverse_kind="pool.asset_added",
                inverse_payload={"asset_id": asset_id},
            )
    return _non_invertible(
        event, before, after,
        f"pool asset {asset_id!r} not found in prior projection state",
    )


# -- pool.asset_scored ------------------------------------------------------

def _handle_pool_asset_scored(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of pool.asset_scored: restore original score from prior state."""
    payload = event.payload
    assert isinstance(payload, PoolAssetScoredPayload)
    asset_id = payload.asset_id
    before_pool = before.get("pool", {}) if isinstance(before, dict) else {}
    before_entries = before_pool.get("entries", []) if isinstance(before_pool, dict) else []
    for entry in before_entries:
        if isinstance(entry, dict) and entry.get("asset_id") == asset_id:
            original_score = float(entry.get("score", 0))
            return InverseRequest(
                invertible=True,
                inverse_kind="pool.asset_scored",
                inverse_payload={
                    "asset_id": asset_id,
                    "score": original_score,
                },
            )
    return _non_invertible(
        event, before, after,
        f"pool asset {asset_id!r} not found in prior projection state",
    )


# -- arrangement.replaced ---------------------------------------------------

def _handle_arrangement_replaced(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of arrangement.replaced: restore prior arrangement from before state."""
    payload = event.payload
    assert isinstance(payload, ArrangementReplacedPayload)
    before_arrangement = before.get("arrangement", {}) if isinstance(before, dict) else {}
    return InverseRequest(
        invertible=True,
        inverse_kind="arrangement.replaced",
        inverse_payload={"arrangement": dict(before_arrangement) if isinstance(before_arrangement, dict) else {}},
    )


# -- timeline.config_replaced ------------------------------------------------

def _handle_timeline_config_replaced(event: TimelineEvent, before: dict[str, Any], after: dict[str, Any]) -> InverseRequest:
    """Inverse of timeline.config_replaced: restore the prior raw TimelineConfig."""
    payload = event.payload
    assert isinstance(payload, TimelineConfigReplacedPayload)
    try:
        config = validate_timeline_config_for_container(before)
    except ValueError as exc:
        return _non_invertible(
            event, before, after,
            f"prior projection is not a valid TimelineConfig: {exc}",
        )
    return InverseRequest(
        invertible=True,
        inverse_kind="timeline.config_replaced",
        inverse_payload={"config": config},
    )


# ============================================================================
# Declarative inverse dispatch table
# ============================================================================

# Table entries: (event_kind, expected_payload_type, handler_fn)
# Handler signature: (event, before, after) -> InverseRequest
# The dispatch machinery (plan_inverse) performs isinstance checks before
# calling the handler, so handlers can assume correct payload type.

_INVERSE_TABLE: list[tuple[str, type, Any]] = [
    # -- clip.* (7 simple-forward, 7 complex) --
    ("clip.added",           ClipAddedPayload,           _forward("clip.removed", "clip_id")),
    ("clip.removed",         ClipRemovedPayload,         _handle_clip_removed),
    ("clip.moved",           ClipMovedPayload,           _handle_clip_moved),
    ("clip.retracked",       ClipRetrackedPayload,       _handle_clip_retracked),
    ("clip.retimed",         ClipRetimedPayload,         _handle_clip_retimed),
    ("clip.swapped",         ClipSwappedPayload,         _forward("clip.swapped", "clip_a_id", "clip_b_id")),
    ("clip.replaced",        ClipReplacedPayload,        _handle_clip_replaced),
    ("clip.text_set",        ClipTextSetPayload,         _handle_clip_text_set),
    ("clip.annotated",       ClipAnnotatedPayload,       _handle_clip_annotated),
    # -- transition.* (1 simple-forward, 1 complex) --
    ("transition.set",       TransitionSetPayload,       _forward("transition.removed", "left_clip_id", "right_clip_id")),
    ("transition.removed",   TransitionRemovedPayload,   _handle_transition_removed),
    # -- effect.* (1 simple-forward, 2 complex) --
    ("effect.added",         EffectAddedPayload,         _forward("effect.removed", "clip_id", "effect_id")),
    ("effect.removed",       EffectRemovedPayload,       _handle_effect_removed),
    ("effect.tuned",         EffectTunedPayload,         _handle_effect_tuned),
    # -- theme.* (2 complex) --
    ("theme.set",            ThemeSetPayload,            _handle_theme_set),
    ("theme.overridden",     ThemeOverriddenPayload,     _handle_theme_overridden),
    # -- track.* (1 simple-forward, 1 complex) --
    ("track.added",          TrackAddedPayload,          _forward("track.removed", "track_id")),
    ("track.removed",        TrackRemovedPayload,        _handle_track_removed),
    # -- audio.* (1 simple-forward, 1 complex) --
    ("audio.bound",          AudioBoundPayload,          _forward("audio.unbound", "clip_id")),
    ("audio.unbound",        AudioUnboundPayload,        _handle_audio_unbound),
    # -- pool.* (1 simple-forward, 2 complex) --
    ("pool.asset_added",     PoolAssetAddedPayload,      _forward("pool.asset_removed", "asset_id")),
    ("pool.asset_removed",   PoolAssetRemovedPayload,    _handle_pool_asset_removed),
    ("pool.asset_scored",    PoolAssetScoredPayload,     _handle_pool_asset_scored),
    # -- arrangement.* (1 complex) --
    ("arrangement.replaced", ArrangementReplacedPayload, _handle_arrangement_replaced),
    # -- timeline.* (1 complex) --
    ("timeline.config_replaced", TimelineConfigReplacedPayload, _handle_timeline_config_replaced),
]

# Build fast lookup: kind -> (expected_payload_type, handler_fn)
_INVERSE_DISPATCH: dict[str, tuple[type, Any]] = {
    kind: (p_type, handler) for kind, p_type, handler in _INVERSE_TABLE
}


# ============================================================================
# Public API
# ============================================================================


def plan_inverse(
    event: TimelineEvent,
    *,
    before_projection: dict[str, Any] | None = None,
    after_projection: dict[str, Any] | None = None,
) -> InverseRequest:
    """Plan an inverse event for *event* given its before/after projection state.

    This is a **pure function** — no backend calls, no side effects.

    For reversible event kinds (clips, effects, tracks, audio bindings,
    transitions, theme values, annotations, pool metadata, scores), returns
    a mechanical inverse event request.

    For non-reversible kinds (timeline.created, timeline.imported,
    timeline.deleted, timeline.tombstoned, timeline.erased, timeline.recovered,
    timeline.branched_from, timeline.reverted), returns a ``timeline.reverted``
    request with the before/after projections for auditability.

    For erased historical payloads (``ErasedPayload``), treats the event as
    non-invertible since the original content cannot be recovered.

    Args:
        event: The event to invert.
        before_projection: Projection state BEFORE *event* was applied.
        after_projection: Projection state AFTER *event* was applied.

    Returns:
        InverseRequest with the plan.
    """
    before: dict[str, Any] = before_projection if isinstance(before_projection, dict) else {}
    after: dict[str, Any] = after_projection if isinstance(after_projection, dict) else {}

    # Non-reversible lifecycle/ops kinds
    if event.kind in _NON_REVERSIBLE_KINDS:
        return InverseRequest(
            invertible=False,
            revert_kind="timeline.reverted",
            revert_reason=(
                f"event {event.event_id!r} of kind {event.kind!r} "
                f"is not blindly invertible"
            ),
            before_projection=before if before else None,
            after_projection=after if after else None,
        )

    # Erased historical payloads: treated as non-invertible
    if isinstance(event.payload, ErasedPayload):
        return InverseRequest(
            invertible=False,
            revert_kind="timeline.reverted",
            revert_reason=(
                f"event {event.event_id!r} has an erased payload; "
                f"original content cannot be recovered for inversion"
            ),
            before_projection=before if before else None,
            after_projection=after if after else None,
        )

    # Look up in the dispatch table
    entry = _INVERSE_DISPATCH.get(event.kind)
    if entry is None:
        return _non_invertible(
            event, before, after,
            f"no inverse planner registered for event kind {event.kind!r}",
        )

    expected_type, handler = entry
    if not isinstance(event.payload, expected_type):
        return _non_invertible(
            event, before, after,
            f"{event.kind} payload not available",
        )

    return handler(event, before, after)


def plan_inverses(
    events: Sequence[TimelineEvent],
    *,
    initial_projection: dict[str, Any] | None = None,
) -> list[InverseRequest]:
    """Plan inverse events for a sequence of events.

    Walks the event sequence, maintaining a running projection so each
    inverse planner receives accurate before/after state.

    Args:
        events: Ordered sequence of events to invert.
        initial_projection: Initial projection state (default empty).

    Returns:
        List of InverseRequest, one per event (in the same order).
    """
    from astrid.core.timeline.projection import apply_event_to_assembly

    state: dict[str, Any] = (
        dict(initial_projection) if isinstance(initial_projection, dict) else {}
    )
    results: list[InverseRequest] = []

    for event in events:
        before = dict(state)
        try:
            state = apply_event_to_assembly(state, event)
        except Exception:
            # If projection fails, still try to plan the inverse with
            # whatever before state we have
            pass
        after = dict(state)

        result = plan_inverse(
            event,
            before_projection=before,
            after_projection=after,
        )
        results.append(result)

    return results
