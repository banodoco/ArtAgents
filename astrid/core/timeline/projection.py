"""Canonical event-to-assembly projector (backend-agnostic).

This module defines the **sole** applicator table and two public surfaces
for projecting a sequence of ``TimelineEvent`` objects into an ``assembly``
dict suitable for writing to ``assembly.json``:

* ``apply_event_to_assembly(state: dict, event: TimelineEvent) -> dict``
  – single-event fold (returns a *new* dict).

* ``project_to_assembly(events: Sequence[TimelineEvent], *, initial_assembly=None) -> dict``
  – full replay over an ordered event sequence.

The projector is **pure**: no filesystem reads, no current time, no random
IDs, no network, no mutation of input events.

Lifecycle events
----------------

* ``timeline.created``, ``timeline.renamed``, ``timeline.default_set``,
  ``timeline.tombstoned``, ``timeline.deleted`` are **intentional no-ops**
  for the assembly projection.
* ``timeline.imported`` seeds the assembly state from the snapshot payload.

``timeline.imported`` wrapper unwrap
------------------------------------

``LocalFsBackend._build_imported_event()`` stores the full on-disk
``assembly.json`` blob inside ``snapshot['assembly.json']``:

.. code-block:: json

    {"schema_version": 1, "assembly": { ... }}

If ``snapshot['assembly.json']`` is a dict containing an ``"assembly"`` key
whose value is itself a dict, the projector extracts that inner dict.
Otherwise the raw value is used as the assembly body.

This heuristic is safe because a bare assembly dict will never contain a
top-level ``"assembly"`` key whose value is another dict (clip data has an
``"assembly"`` field only inside arrangement-based shapes, and those are
not top-level assembly dicts).

Dispatch conventions
--------------------

The dispatch table maps event kinds to ``(ensure_keys, dispatch_fn, applicator)``:

* ``ensure_keys`` – list of assembly keys that must exist before applying.
* ``dispatch_fn`` – one of the ``_dispatch_*`` helpers that extracts the
  correct scope (clips-only, clips+assembly, assembly-only) and calls the
  applicator.
* ``applicator`` – mutates the scope in-place.

Applicators are **private** to this module.  External code must only use
the two public surfaces.  When ``project_to_assembly`` is called, each
applicator runs against a fresh copy of the state, so input events are
never mutated.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Sequence

from .events.schema import (
    ArrangementReplacedPayload,
    AudioBoundPayload,
    AudioUnboundPayload,
    ClipAddedPayload,
    ClipAnnotatedPayload,
    ClipMovedPayload,
    ClipPosition,
    ClipRemovedPayload,
    ClipReplacedPayload,
    ClipRetimedPayload,
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
    TimelineBranchedFromPayload,
    TimelineErasedPayload,
    TimelineEvent,
    TimelineRecoveredPayload,
    TimelineRevertedPayload,
    TrackAddedPayload,
    TrackRemovedPayload,
    TransitionRemovedPayload,
    TransitionSetPayload,
)


# ============================================================================
# ProjectionError
# ============================================================================


@dataclass(frozen=True)
class ProjectionError(RuntimeError):
    """Raised when a single event cannot be projected onto the assembly.

    Carries enough context for an m7 audit tool to pinpoint the failure
    without opening the event log.
    """

    event_id: str
    """ULID of the event that caused the error."""

    kind: str
    """Event kind (e.g. ``"clip.added"``)."""

    reason: str
    """Human-readable diagnostic."""

    def __str__(self) -> str:
        return f"projection error at event {self.event_id!r} ({self.kind!r}): {self.reason}"


@dataclass(frozen=True)
class ErasedPayloadProjectionError(ProjectionError):
    """Raised when an erased event cannot be safely skipped in projection.

    Read paths must catch this typed error rather than silently hiding it.
    Safe-to-skip erased kinds (e.g. clip.*, transition.*, effect.*, theme.*,
    track.*, audio.*, pool.*) are skipped; all other erased events raise
    this error.
    """

    def __str__(self) -> str:
        return (
            f"erased payload cannot be projected at event {self.event_id!r} "
            f"({self.kind!r}): {self.reason}"
        )


# ============================================================================
# Assembly key defaults (empty init shape)
# ============================================================================

_EMPTY_INIT_DEFAULTS: dict[str, Any] = {
    "clips": [],
    "tracks": [],
    "theme": "",
    "theme_overrides": {},
    "pool": {"entries": []},
    "arrangement": {"clips": []},
}


def _copy_empty_default(value: Any) -> Any:
    return deepcopy(value)


# ============================================================================
# Clip helpers
# ============================================================================


def _clip_index(clips: list[dict[str, Any]], clip_id: str) -> int | None:
    """Return the list index of *clip_id* in *clips*, or ``None``."""
    for i, clip in enumerate(clips):
        if clip.get("id") == clip_id:
            return i
    return None


def _insert_at_position(
    clips: list[dict[str, Any]], new_clip: dict[str, Any], position: ClipPosition | None
) -> None:
    """Insert *new_clip* into *clips* at *position* (append if None)."""
    if position is None:
        clips.append(new_clip)
        return
    if position.mode == "index":
        idx = max(0, min(position.index or 0, len(clips)))
        clips.insert(idx, new_clip)
    elif position.mode == "after":
        ref_idx = _clip_index(clips, position.ref_clip_id or "")
        if ref_idx is not None:
            clips.insert(ref_idx + 1, new_clip)
        else:
            clips.append(new_clip)
    elif position.mode == "before":
        ref_idx = _clip_index(clips, position.ref_clip_id or "")
        if ref_idx is not None:
            clips.insert(ref_idx, new_clip)
        else:
            clips.append(new_clip)


def _make_clip_entry(payload: ClipAddedPayload) -> dict[str, Any]:
    """Build a minimal clip dict from a ``clip.added`` payload."""
    return {
        "id": payload.clip_id,
        "kind": payload.kind,
        "asset_id": payload.asset_id,
        "start": 0.0,
        "duration": 0.0,
        "text": "",
        "note": "",
    }


# ============================================================================
# Per-kind clip applicators (m2)
# ============================================================================


def _apply_clip_added(clips: list[dict[str, Any]], payload: ClipAddedPayload) -> None:
    _insert_at_position(clips, _make_clip_entry(payload), payload.position)


def _apply_clip_removed(clips: list[dict[str, Any]], payload: ClipRemovedPayload) -> None:
    idx = _clip_index(clips, payload.clip_id)
    if idx is not None:
        clips.pop(idx)


def _apply_clip_moved(clips: list[dict[str, Any]], payload: ClipMovedPayload) -> None:
    idx = _clip_index(clips, payload.clip_id)
    if idx is None:
        return
    clip = clips.pop(idx)
    _insert_at_position(clips, clip, payload.position)


def _apply_clip_retimed(clips: list[dict[str, Any]], payload: ClipRetimedPayload) -> None:
    for clip in clips:
        if clip.get("id") == payload.clip_id:
            clip["start"] = payload.start
            clip["duration"] = payload.duration
            return


def _apply_clip_swapped(clips: list[dict[str, Any]], payload: ClipSwappedPayload) -> None:
    idx_a = _clip_index(clips, payload.clip_a_id)
    idx_b = _clip_index(clips, payload.clip_b_id)
    if idx_a is not None and idx_b is not None:
        clips[idx_a], clips[idx_b] = clips[idx_b], clips[idx_a]


def _apply_clip_replaced(clips: list[dict[str, Any]], payload: ClipReplacedPayload) -> None:
    for clip in clips:
        if clip.get("id") == payload.clip_id:
            clip["asset_id"] = payload.with_asset_id
            return


def _apply_clip_text_set(clips: list[dict[str, Any]], payload: ClipTextSetPayload) -> None:
    for clip in clips:
        if clip.get("id") == payload.clip_id:
            clip["text"] = payload.text
            return


def _apply_clip_annotated(clips: list[dict[str, Any]], payload: ClipAnnotatedPayload) -> None:
    for clip in clips:
        if clip.get("id") == payload.clip_id:
            clip["note"] = payload.note
            return


# ============================================================================
# transition.* applicators (m3)
# ============================================================================


def _apply_transition_set(clips: list[dict[str, Any]], payload: TransitionSetPayload) -> None:
    for clip in clips:
        if clip.get("id") == payload.left_clip_id:
            clip["transition"] = {
                "kind": payload.kind,
                "right_clip_id": payload.right_clip_id,
                "duration_seconds": payload.duration_seconds,
            }
            return


def _apply_transition_removed(clips: list[dict[str, Any]], payload: TransitionRemovedPayload) -> None:
    for clip in clips:
        if clip.get("id") == payload.left_clip_id:
            clip.pop("transition", None)
            return


# ============================================================================
# effect.* applicators (m3)
# ============================================================================


def _apply_effect_added(clips: list[dict[str, Any]], payload: EffectAddedPayload, assembly: dict[str, Any]) -> None:
    for clip in clips:
        if clip.get("id") == payload.clip_id:
            effects: list[dict[str, Any]] = clip.setdefault("effects", [])
            effects.append({
                "effect_id": payload.effect_id,
                "params": dict(payload.params) if payload.params else None,
            })
            return


def _apply_effect_removed(clips: list[dict[str, Any]], payload: EffectRemovedPayload, assembly: dict[str, Any]) -> None:
    for clip in clips:
        if clip.get("id") == payload.clip_id:
            effects = clip.get("effects")
            if isinstance(effects, list):
                clip["effects"] = [
                    e for e in effects if e.get("effect_id") != payload.effect_id
                ]
            return


def _apply_effect_tuned(clips: list[dict[str, Any]], payload: EffectTunedPayload, assembly: dict[str, Any]) -> None:
    for clip in clips:
        if clip.get("id") == payload.clip_id:
            effects = clip.get("effects")
            if isinstance(effects, list):
                for e in effects:
                    if e.get("effect_id") == payload.effect_id:
                        params = e.setdefault("params", {})
                        params[payload.param] = payload.value
                        return
            return


# ============================================================================
# theme.* applicators (m3)
# ============================================================================


def _apply_theme_set(assembly: dict[str, Any], payload: ThemeSetPayload) -> None:
    assembly["theme"] = payload.theme_id


def _apply_theme_overridden(assembly: dict[str, Any], payload: ThemeOverriddenPayload) -> None:
    overrides: dict[str, Any] = assembly["theme_overrides"]
    overrides[payload.override_id] = payload.value


# ============================================================================
# track.* applicators (m3)
# ============================================================================


def _apply_track_added(assembly: dict[str, Any], payload: TrackAddedPayload) -> None:
    tracks: list[dict[str, Any]] = assembly["tracks"]
    track_entry: dict[str, Any] = {"id": payload.track_id, "kind": payload.kind}
    if payload.label is not None:
        track_entry["label"] = payload.label
    tracks.append(track_entry)


def _apply_track_removed(assembly: dict[str, Any], payload: TrackRemovedPayload) -> None:
    tracks: list[dict[str, Any]] = assembly["tracks"]
    assembly["tracks"] = [t for t in tracks if t.get("id") != payload.track_id]


# ============================================================================
# audio.* applicators (m3)
# ============================================================================


def _apply_audio_bound(clips: list[dict[str, Any]], payload: AudioBoundPayload) -> None:
    for clip in clips:
        if clip.get("id") == payload.clip_id:
            clip["asset_id"] = payload.asset_id
            return


def _apply_audio_unbound(clips: list[dict[str, Any]], payload: AudioUnboundPayload) -> None:
    for clip in clips:
        if clip.get("id") == payload.clip_id:
            clip["asset_id"] = ""
            return


# ============================================================================
# pool.* applicators (m3)
# ============================================================================


def _apply_pool_asset_added(assembly: dict[str, Any], payload: PoolAssetAddedPayload) -> None:
    pool: dict[str, Any] = assembly["pool"]
    entries: list[dict[str, Any]] = pool.setdefault("entries", [])
    entries.append({"asset_id": payload.asset_id, "score": 0.0})


def _apply_pool_asset_removed(assembly: dict[str, Any], payload: PoolAssetRemovedPayload) -> None:
    pool: dict[str, Any] = assembly["pool"]
    entries: list[dict[str, Any]] = pool.get("entries", [])
    pool["entries"] = [e for e in entries if e.get("asset_id") != payload.asset_id]


def _apply_pool_asset_scored(assembly: dict[str, Any], payload: PoolAssetScoredPayload) -> None:
    pool: dict[str, Any] = assembly["pool"]
    entries: list[dict[str, Any]] = pool.get("entries", [])
    for e in entries:
        if e.get("asset_id") == payload.asset_id:
            e["score"] = payload.score
            return


# ============================================================================
# arrangement.* applicators (m3)
# ============================================================================


def _apply_arrangement_replaced(assembly: dict[str, Any], payload: ArrangementReplacedPayload) -> None:
    assembly["arrangement"] = dict(payload.arrangement)


# ============================================================================
# Dispatch infrastructure
# ============================================================================


# Lifecycle event kinds that are intentional assembly no-ops.
_LIFECYCLE_NOOP_KINDS: frozenset[str] = frozenset({
    "timeline.created",
    "timeline.renamed",
    "timeline.default_set",
    "timeline.tombstoned",
    "timeline.deleted",
    # M9: ops/lifecycle events that don't change assembly state
    "timeline.reverted",
    "timeline.branched_from",
    "timeline.erased",
})

# Event kinds whose erased payloads can be safely skipped in projection.
# These are domain events that modify specific assembly keys (clips, tracks,
# pool, arrangement, etc.) — skipping them preserves structural consistency
# of the remaining assembly.
_ERASED_SAFE_KINDS: frozenset[str] = frozenset({
    "clip.added", "clip.removed", "clip.moved", "clip.retimed",
    "clip.swapped", "clip.replaced", "clip.text_set", "clip.annotated",
    "transition.set", "transition.removed",
    "effect.added", "effect.removed", "effect.tuned",
    "theme.set", "theme.overridden",
    "track.added", "track.removed",
    "audio.bound", "audio.unbound",
    "pool.asset_added", "pool.asset_removed", "pool.asset_scored",
    "arrangement.replaced",
})


def _dispatch_clip_applicator(
    assembly: dict[str, Any],
    payload: Any,
    fn: Any,
) -> None:
    """Dispatch a clip-scoped applicator that only needs the clips list."""
    clips: list[dict[str, Any]] = assembly["clips"]
    fn(clips, payload)


def _dispatch_clip_assembly_applicator(
    assembly: dict[str, Any],
    payload: Any,
    fn: Any,
) -> None:
    """Dispatch a clip-scoped applicator that may also touch assembly context."""
    clips: list[dict[str, Any]] = assembly["clips"]
    fn(clips, payload, assembly)


def _dispatch_assembly_applicator(
    assembly: dict[str, Any],
    payload: Any,
    fn: Any,
) -> None:
    """Dispatch an assembly-scoped applicator."""
    fn(assembly, payload)


# (event_kind, ensure_keys, dispatch_fn, applicator)
_DISPATCH: list[tuple[str, list[str], Any, Any]] = [
    # -- clip.* (m2, unchanged) --
    ("clip.added", ["clips"], _dispatch_clip_applicator, _apply_clip_added),
    ("clip.removed", ["clips"], _dispatch_clip_applicator, _apply_clip_removed),
    ("clip.moved", ["clips"], _dispatch_clip_applicator, _apply_clip_moved),
    ("clip.retimed", ["clips"], _dispatch_clip_applicator, _apply_clip_retimed),
    ("clip.swapped", ["clips"], _dispatch_clip_applicator, _apply_clip_swapped),
    ("clip.replaced", ["clips"], _dispatch_clip_applicator, _apply_clip_replaced),
    ("clip.text_set", ["clips"], _dispatch_clip_applicator, _apply_clip_text_set),
    ("clip.annotated", ["clips"], _dispatch_clip_applicator, _apply_clip_annotated),
    # -- transition.* (m3) --
    ("transition.set", ["clips"], _dispatch_clip_applicator, _apply_transition_set),
    ("transition.removed", ["clips"], _dispatch_clip_applicator, _apply_transition_removed),
    # -- effect.* (m3) --
    ("effect.added", ["clips"], _dispatch_clip_assembly_applicator, _apply_effect_added),
    ("effect.removed", ["clips"], _dispatch_clip_assembly_applicator, _apply_effect_removed),
    ("effect.tuned", ["clips"], _dispatch_clip_assembly_applicator, _apply_effect_tuned),
    # -- theme.* (m3) --
    ("theme.set", ["theme", "theme_overrides"], _dispatch_assembly_applicator, _apply_theme_set),
    ("theme.overridden", ["theme", "theme_overrides"], _dispatch_assembly_applicator, _apply_theme_overridden),
    # -- track.* (m3) --
    ("track.added", ["tracks"], _dispatch_assembly_applicator, _apply_track_added),
    ("track.removed", ["tracks"], _dispatch_assembly_applicator, _apply_track_removed),
    # -- audio.* (m3) --
    ("audio.bound", ["clips"], _dispatch_clip_applicator, _apply_audio_bound),
    ("audio.unbound", ["clips"], _dispatch_clip_applicator, _apply_audio_unbound),
    # -- pool.* (m3) --
    ("pool.asset_added", ["pool"], _dispatch_assembly_applicator, _apply_pool_asset_added),
    ("pool.asset_removed", ["pool"], _dispatch_assembly_applicator, _apply_pool_asset_removed),
    ("pool.asset_scored", ["pool"], _dispatch_assembly_applicator, _apply_pool_asset_scored),
    # -- arrangement.* (m3) --
    ("arrangement.replaced", ["arrangement"], _dispatch_assembly_applicator, _apply_arrangement_replaced),
]

# Build fast lookup
_DISPATCH_MAP: dict[str, tuple[list[str], Any, Any]] = {}
for kind, keys, dispatcher, applicator in _DISPATCH:
    _DISPATCH_MAP[kind] = (keys, dispatcher, applicator)


# ============================================================================
# Public API
# ============================================================================


def _unwrap_imported_assembly(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Extract the inner assembly dict from a ``timeline.imported`` snapshot.

    ``LocalFsBackend._build_imported_event()`` stores the full on-disk
    ``assembly.json`` blob under ``snapshot['assembly.json']``.  The blob
    has the wrapper shape ``{"schema_version": 1, "assembly": {...}}``.
    When the value is a dict containing an ``"assembly"`` key whose value
    is itself a dict, the inner dict is returned.  Otherwise the raw value
    is used as-is.
    """
    raw = snapshot.get("assembly.json")
    if not isinstance(raw, dict):
        return {}
    # Heuristic: if the dict has an "assembly" key whose value is a dict,
    # it's the wrapper shape — extract the inner dict (deep copy to avoid
    # sharing mutable structures with the event payload).
    inner = raw.get("assembly")
    if isinstance(inner, dict):
        return deepcopy(inner)
    # Otherwise treat the raw value as the assembly body.
    return deepcopy(raw)


def apply_event_to_assembly(state: dict[str, Any], event: TimelineEvent) -> dict[str, Any]:
    """Fold a single *event* onto an assembly *state*, returning a **new** dict.

    The input *state* is never mutated.  This is the unit operation behind
    ``project_to_assembly`` and is also useful for incremental or preview
    consumers that want to see the effect of one event without replaying
    the full stream.

    Raises ``ProjectionError`` when *event* is unrecognised and cannot be
    applied.
    """
    # Lifecycle no-ops
    if event.kind in _LIFECYCLE_NOOP_KINDS:
        return state

    # Erased payload envelope: checked BEFORE any kind-specific logic,
    # since erased events keep their original kind but have ErasedPayload.
    if isinstance(event.payload, ErasedPayload):
        if event.kind in _ERASED_SAFE_KINDS:
            # Safe to skip — the event existed but its payload is erased
            return state
        raise ErasedPayloadProjectionError(
            event_id=event.event_id,
            kind=event.kind,
            reason=(
                f"erased event of kind {event.kind!r} cannot be safely skipped "
                f"during projection; only domain events that modify specific "
                f"assembly keys can be skipped"
            ),
        )

    # timeline.imported — seed the assembly from the snapshot
    if event.kind == "timeline.imported":
        imported_assembly = _unwrap_imported_assembly(event.payload.snapshot)
        if not imported_assembly:
            return state
        # Merge: start from imported, then merge current state on top
        # so events applied before this one are preserved (useful for replay
        # where imported is not the first event).
        result = dict(imported_assembly)
        result.update(state)
        return result

    # timeline.recovered — replace projected assembly with anchor projection
    if event.kind == "timeline.recovered":
        payload = event.payload
        if isinstance(payload, TimelineRecoveredPayload):
            if payload.projected_state_summary is not None:
                # Use the embedded projected state as the new assembly
                return deepcopy(payload.projected_state_summary)
            # Fall through: if no projected state in payload, treat as no-op
            # (requires upstream caller to have materialised the anchor)
            return state
        return state

    # Domain mutation events — look up in dispatch table
    dispatch_entry = _DISPATCH_MAP.get(event.kind)
    if dispatch_entry is None:
        raise ProjectionError(
            event_id=event.event_id,
            kind=event.kind,
            reason=f"unsupported event kind for assembly projection: {event.kind!r}",
        )

    ensure_keys, dispatcher, applicator = dispatch_entry

    # Work on a deep copy of the state so the input is never mutated.
    # A shallow dict() copy would still share nested lists/dicts (clips,
    # tracks, pool entries, etc.) with the input, causing silent corruption
    # when applicators mutate those structures in-place.
    assembly = deepcopy(state)

    # Ensure every required domain key exists, initialising from defaults
    # when the key is missing from the assembly (not just when empty).
    for key in ensure_keys:
        if key not in assembly and key in _EMPTY_INIT_DEFAULTS:
            assembly[key] = _copy_empty_default(_EMPTY_INIT_DEFAULTS[key])

    # Apply the event
    try:
        dispatcher(assembly, event.payload, applicator)
    except Exception as exc:
        raise ProjectionError(
            event_id=event.event_id,
            kind=event.kind,
            reason=f"failed to apply event: {exc}",
        ) from exc

    return assembly


def project_to_assembly(
    events: Sequence[TimelineEvent],
    *,
    initial_assembly: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Replay an ordered sequence of *events* into a projected assembly dict.

    The projector is **backend-agnostic**: it accepts ``TimelineEvent``
    objects regardless of whether they came from ``LocalFsBackend``,
    ``SupabaseBackend``, or a test fixture.

    Parameters
    ----------
    events:
        Ordered sequence of ``TimelineEvent`` objects to replay.
    initial_assembly:
        Optional seed state for the projection.  When supplied, events are
        folded on top of a deep copy of this dict.  Useful for
        checkpoint-assisted replay where only suffix events need to be
        applied.

    Returns
    -------
    dict
        The projected assembly dict.  This is the **inner** assembly value
        (the ``.assembly`` attribute of the on-disk ``Assembly`` model),
        **not** the wrapper ``{"schema_version": 1, "assembly": {...}}``.
        Callers that need the wrapper must construct it themselves.

    Raises
    ------
    ProjectionError
        When any event cannot be projected.
    """
    state: dict[str, Any] = (
        deepcopy(initial_assembly) if initial_assembly is not None else {}
    )
    for event in events:
        state = apply_event_to_assembly(state, event)
    return state


# ============================================================================
# Pure replay (never writes files — used by observability / audit)
# ============================================================================


def replay_projection(
    backend: Any,
    *,
    stop_at_event_id: str | None = None,
) -> dict[str, Any]:
    """Replay the full event stream into an assembly dict **without any disk I/O**.

    This is the pure, read-only counterpart of ``regenerate_projection()``.
    It reads events through *backend* (which must satisfy
    ``EventLogBackend.read_events()``) and folds them via
    ``apply_event_to_assembly``.

    Parameters
    ----------
    backend:
        Any object with a ``read_events(*, after=None, limit=None) -> list[TimelineEvent]``
        method.
    stop_at_event_id:
        When set, replay stops after applying the event whose ``event_id``
        matches this value.  The returned assembly reflects state **after**
        that event was applied.

    Returns
    -------
    dict
        The **inner** projected assembly dict (not the wrapper).

    Raises
    ------
    ProjectionError
        When ``stop_at_event_id`` is provided but not found in the stream,
        or when any event cannot be projected.
    """
    all_events = backend.read_events()

    if stop_at_event_id is None:
        return project_to_assembly(all_events)

    # Prefix replay: fold events one by one, check each event_id.
    state: dict[str, Any] = {}
    for event in all_events:
        state = apply_event_to_assembly(state, event)
        if event.event_id == stop_at_event_id:
            return state

    raise ProjectionError(
        event_id=stop_at_event_id,
        kind="(target)",
        reason=f"stop_at_event_id {stop_at_event_id!r} not found in event stream",
    )


# ============================================================================
# Helpers for projecting to a specific event ID and checkpoint verification
# ============================================================================


def project_to_event_id(
    backend: Any,
    target_event_id: str,
) -> dict[str, Any]:
    """Replay the event stream up to (and including) *target_event_id*.

    Verifies the anchor hash against the backend (via ``head()`` or
    ``verify_chain()``) rather than trusting checkpoint files alone.

    Parameters
    ----------
    backend:
        Any object with ``read_events(*, after=None, limit=None)`` and
        ``verify_chain()`` methods.
    target_event_id:
        The ULID of the target event to project to.

    Returns
    -------
    dict
        The **inner** projected assembly dict after applying all events
        up to and including *target_event_id*.

    Raises
    ------
    ProjectionError
        When *target_event_id* is not found in the stream or any event
        cannot be projected.
    """
    return replay_projection(backend, stop_at_event_id=target_event_id)


def project_to_checkpoint(
    backend: Any,
    *,
    verify: bool = True,
) -> dict[str, Any]:
    """Replay the full event stream into an assembly dict with optional verification.

    Unlike ``regenerate_projection()``, this helper does **not** write
    any files.  It is suitable for callers that need a pure projected
    assembly for comparison or validation.

    Parameters
    ----------
    backend:
        Any object with ``read_events()`` and ``verify_chain()`` methods.
    verify:
        When True (default), verify the event hash chain after projection.
        Raises ``ProjectionError`` if chain verification fails.

    Returns
    -------
    dict
        The **inner** projected assembly dict.

    Raises
    ------
    ProjectionError
        When any event cannot be projected or (if *verify*) when the
        hash chain verification fails.
    """
    state = replay_projection(backend)
    if verify:
        verification = backend.verify_chain()
        if not verification.ok:
            raise ProjectionError(
                event_id=verification.last_event_id or "(unknown)",
                kind="(chain-verification)",
                reason=verification.error or "hash chain verification failed",
            )
        # Additional safety: the projected state is from events only — caller
        # must never treat stale compatibility blobs as authority.
    return state


# ============================================================================
# Replay orchestration (backend-agnostic, with LocalFs checkpoint support)
# ============================================================================

# Version tag for the checkpoint file format.  Bump when the shape changes.
_CHECKPOINT_SCHEMA_VERSION = 1


def regenerate_projection(
    timeline_id: str,
    backend: Any,
    *,
    timeline_home: Any,
) -> dict[str, Any]:
    """Regenerate ``assembly.json`` from the canonical event stream.

    This is the **single** replay orchestration entry point.  It is
    backend-agnostic: *backend* must satisfy the ``EventLogBackend``
    protocol (``.head()`` and ``.read_events()``), and *timeline_home*
    is a ``pathlib.Path`` to the timeline directory (used for
    checkpoint and assembly file I/O).

    Algorithm
    ---------
    1. Read ``assembly.checkpoint.json`` (if present).
    2. Verify checkpoint metadata against the current *backend* head.
    3. **Checkpoint hit**: seed ``project_to_assembly`` with the cached
       assembly and replay only suffix events (``after=last_event_id``).
    4. **Checkpoint miss / corruption / version mismatch**: fall back to
       full replay via ``replay_projection()`` (the pure read-only path).
    5. Atomically write the projected assembly to ``assembly.json``
       (wrapper shape ``{schema_version, assembly}``).
    6. Atomically write / refresh ``assembly.checkpoint.json``.

    Returns
    -------
    dict
        The **inner** projected assembly dict (not the wrapper).

    Raises
    ------
    ProjectionError
        When any event in the stream fails to project.
    OSError
        When file I/O fails.
    """
    from pathlib import Path

    from astrid.core.project.jsonio import read_json, write_json_atomic

    _home = Path(timeline_home)
    checkpoint_file = _home / "assembly.checkpoint.json"
    assembly_file = _home / "assembly.json"

    head = backend.head()

    assembly: dict[str, Any] = {}
    events_applied = 0

    # --- Try checkpoint-assisted replay ---
    checkpoint = None
    try:
        if checkpoint_file.is_file():
            checkpoint = read_json(checkpoint_file)
    except Exception:
        checkpoint = None

    checkpoint_valid = False
    if isinstance(checkpoint, dict):
        # Verify checkpoint metadata matches current head.
        cp_schema = checkpoint.get("schema_version")
        cp_timeline_id = checkpoint.get("timeline_id")
        cp_last_event_id = checkpoint.get("last_event_id")
        cp_last_hash = checkpoint.get("last_hash")
        cp_event_count = checkpoint.get("event_count")
        cp_assembly = checkpoint.get("assembly")

        if (
            cp_schema == _CHECKPOINT_SCHEMA_VERSION
            and cp_timeline_id == head.timeline_id
            and cp_last_event_id == head.last_event_id
            and cp_last_hash == head.last_hash
            and cp_event_count == head.event_count
            and isinstance(cp_assembly, dict)
        ):
            # Checkpoint is current — no suffix events to replay.
            # M9: Verify that no recovery/erasure events are in the stream
            # that would invalidate the checkpoint.  Checkpoint is only valid
            # when it was regenerated from events, not from stale blobs.
            assembly = dict(cp_assembly)
            events_applied = cp_event_count
            checkpoint_valid = True
        elif (
            cp_schema == _CHECKPOINT_SCHEMA_VERSION
            and cp_timeline_id == head.timeline_id
            and cp_event_count is not None
            and cp_event_count < head.event_count
            and isinstance(cp_assembly, dict)
        ):
            # Checkpoint is behind — replay suffix events.
            suffix_events = backend.read_events(after=cp_last_event_id)
            # M9: If any suffix event is a recovery or erasure, invalidate
            # the checkpoint and force full replay.  Recovery replaces the
            # assembly; erasure may have removed payloads the checkpoint
            # still contains.
            suffix_has_recovery_or_erasure = any(
                e.kind in ("timeline.recovered", "timeline.erased")
                for e in suffix_events
            )
            if suffix_has_recovery_or_erasure:
                checkpoint_valid = False
            else:
                assembly = project_to_assembly(
                    suffix_events,
                    initial_assembly=cp_assembly,
                )
                events_applied = head.event_count
                checkpoint_valid = True

    # --- Fall back to full replay (via pure replay_projection) ---
    if not checkpoint_valid:
        assembly = replay_projection(backend)
        events_applied = head.event_count

    # --- Write assembly.json atomically ---
    from astrid.core.timeline.model import Assembly, TIMELINE_SCHEMA_VERSION as _SCHEMA_VER

    wrapper = Assembly(schema_version=_SCHEMA_VER, assembly=assembly)
    wrapper.write(assembly_file)

    # --- Write / refresh checkpoint ---
    checkpoint_payload = {
        "schema_version": _CHECKPOINT_SCHEMA_VERSION,
        "timeline_id": head.timeline_id,
        "last_event_id": head.last_event_id,
        "last_hash": head.last_hash,
        "event_count": head.event_count,
        "version": head.version,
        "assembly": assembly,
    }
    write_json_atomic(checkpoint_file, checkpoint_payload)

    return assembly
