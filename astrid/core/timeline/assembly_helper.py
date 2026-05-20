"""Assembly.json compatibility contract for clip-level and secondary mutations.

This module defines the **only** allowed mutation path for ``assembly.json``
during m2+m3 editing.  Every edit that must keep ``assembly.json`` in sync
with the event stream does so through the helpers here.

Contract (locked for m2, extended for m3)
------------------------------------------

The compatibility target is ``Assembly.assembly`` — the opaque dict stored
under the ``"assembly"`` key of the on-disk ``assembly.json`` file:

.. code-block:: json

    {"schema_version": 1, "assembly": { ... }}

Three explicit behaviors for each domain key:

    (a) **Empty assembly** (``assembly == {}``)
        Initialised with the domain's default shape (e.g. ``{"clips": []}``).

    (b) **Existing assembly with the expected key**
        The caller updates in-place; the helper ensures the pre-condition holds.

    (c) **Non-empty assembly without the expected key**
        The helper raises ``AssemblyMutationError`` at mutation time.
        This protects unknown assembly shapes from accidental corruption.

.. note::

    ``assembly.json`` is maintained by a **compatibility materializer**
    that runs synchronously after each event append.  In m4 this
    file will become a projection-rebuild target and the synchronous
    materializer will be removed.

    Until m4, a crash between ``append_event`` and the materializer write
    can leave the event stream ahead of ``assembly.json``.  Accept this
    window; m4 projection will close it.

Compatibility assembly.json shape per domain (m4 projection target)
-------------------------------------------------------------------

**clips** (existing m2):
    ``assembly.clips``: ``list[dict]`` where each dict has at minimum:
    ``{"id": str, "kind": str, "asset_id": str, "start": float, "duration": float,
      "text": str, "note": str}``.
    Optional: ``"transition"`` dict, ``"effects"`` list.

**tracks** (new m3):
    ``assembly.tracks``: ``list[dict]`` where each dict has:
    ``{"id": str, "kind": "visual"|"audio", "label": str | None}``.

**theme** (new m3):
    ``assembly.theme``: ``str`` — the active theme id.

**theme_overrides** (new m3):
    ``assembly.theme_overrides``: ``dict[str, Any]`` — keyed by namespace
    (e.g. ``"visual"``, ``"generation"``, ``"voice"``, ``"audio"``, ``"pacing"``).
    Nested values are treated as opaque JSON.

**pool** (new m3):
    ``assembly.pool``: ``{"entries": [{"asset_id": str, "score": float}]}``.

**arrangement** (new m3):
    ``assembly.arrangement``: ``dict`` — opaque arrangement dict with at minimum
    ``{"clips": [...]}``.  Fully replaced on ``arrangement.replaced``.

**Transitions** live on clips:
    ``clip["transition"] = {"kind": str, "right_clip_id": str, "duration_seconds": float}``.
    The transition is keyed on the LEFT clip of the adjacent pair.

**Effects** live on clips:
    ``clip["effects"] = [{"effect_id": str, "params": dict | None}]``.

**Audio bindings** target the clip's ``asset_id`` field:
    ``clip["asset_id"] = asset_id`` (bound) or ``""`` (unbound).
    This targets the renderable timeline clip asset relationship.
    Arrangement-level audio (``audio_source.pool_id``) stays with
    ``arrangement.replaced``.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

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
    PoolAssetAddedPayload,
    PoolAssetRemovedPayload,
    PoolAssetScoredPayload,
    ThemeOverriddenPayload,
    ThemeSetPayload,
    TimelineEvent,
    TrackAddedPayload,
    TrackRemovedPayload,
    TransitionRemovedPayload,
    TransitionSetPayload,
)
from .model import Assembly, TIMELINE_SCHEMA_VERSION


class AssemblyMutationError(RuntimeError):
    """Raised when *assembly.json* cannot be safely mutated by editing code."""


# ============================================================================
# Generic ensure-key infrastructure
# ============================================================================


def _ensure_key(
    assembly: dict[str, Any],
    key: str,
    default: Any,
    *,
    type_check: type | None = None,
) -> dict[str, Any]:
    """Return *assembly* guaranteed to contain *key*.

    Cases:
    * *assembly* is empty → initialise with ``{key: default}``
    * *assembly* has *key* → return as-is
    * *assembly* is non-empty but lacks *key* → raise ``AssemblyMutationError``
    """
    if not isinstance(assembly, dict):
        raise AssemblyMutationError(
            f"assembly must be a dict, got {type(assembly).__name__}"
        )

    if not assembly:
        return {key: default}

    if key in assembly:
        if type_check is not None and not isinstance(assembly[key], type_check):
            raise AssemblyMutationError(
                f"assembly has a {key!r} key but it is not {type_check.__name__}"
            )
        return assembly

    raise AssemblyMutationError(
        f"assembly has existing content but no {key!r} key. "
        f"Editing code cannot safely mutate an unknown assembly shape. "
        f"Existing keys: {sorted(assembly.keys())}"
    )


# ---------------------------------------------------------------------------
# Domain-specific ensure-key helpers
# ---------------------------------------------------------------------------


def ensure_clips_key(assembly: dict[str, Any]) -> dict[str, Any]:
    """Return *assembly* guaranteed to contain a ``"clips"`` key (list)."""
    return _ensure_key(assembly, "clips", [], type_check=list)


def ensure_tracks_key(assembly: dict[str, Any]) -> dict[str, Any]:
    """Return *assembly* guaranteed to contain a ``"tracks"`` key (list).

    Compatible shape: ``[{"id": str, "kind": "visual"|"audio", "label": str | None}]``
    """
    return _ensure_key(assembly, "tracks", [], type_check=list)


def ensure_theme_key(assembly: dict[str, Any]) -> dict[str, Any]:
    """Return *assembly* guaranteed to contain a ``"theme"`` key (str).

    Compatible shape: a string theme id (empty string means no theme set).
    """
    return _ensure_key(assembly, "theme", "", type_check=str)


def ensure_theme_overrides_key(assembly: dict[str, Any]) -> dict[str, Any]:
    """Return *assembly* guaranteed to contain a ``"theme_overrides"`` key (dict).

    Compatible shape: ``{"namespace": opaque_value}`` keyed by namespace
    (visual, generation, voice, audio, pacing).  Nested values are opaque JSON.
    """
    return _ensure_key(assembly, "theme_overrides", {}, type_check=dict)


def ensure_pool_key(assembly: dict[str, Any]) -> dict[str, Any]:
    """Return *assembly* guaranteed to contain a ``"pool"`` key (dict).

    Compatible shape: ``{"entries": [{"asset_id": str, "score": float}]}``.
    """
    return _ensure_key(assembly, "pool", {"entries": []}, type_check=dict)


def ensure_arrangement_key(assembly: dict[str, Any]) -> dict[str, Any]:
    """Return *assembly* guaranteed to contain an ``"arrangement"`` key (dict).

    Compatible shape: ``{"clips": [...]}`` — opaque arrangement with at least
    a clips list.  Fully replaced on ``arrangement.replaced``.
    """
    return _ensure_key(assembly, "arrangement", {"clips": []}, type_check=dict)


# ---------------------------------------------------------------------------
# Convenience: load / materialise loop
# ---------------------------------------------------------------------------


def load_assembly_with_clips(assembly: Assembly) -> dict[str, Any]:
    """Load the opaque ``assembly.assembly`` dict and enforce the clips contract.

    Returns a mutable dict that the caller can update in-place.  The
    returned dict is a *copy* of the assembly content so that the frozen
    ``Assembly`` is not accidentally mutated.
    """
    return ensure_clips_key(dict(assembly.assembly))


def materialise_assembly(assembly_dict: dict[str, Any]) -> Assembly:
    """Wrap *assembly_dict* back into a frozen ``Assembly`` ready for writing.

    The caller is responsible for writing the returned ``Assembly`` to disk
    via ``assembly.write(path)`` or ``write_json_atomic(path, assembly.to_json_obj())``.
    """
    return Assembly(
        schema_version=TIMELINE_SCHEMA_VERSION,
        assembly=dict(assembly_dict),
    )


def get_clips(assembly: Assembly) -> list[dict[str, Any]]:
    """Return the clips list from *assembly*, enforcing the contract.

    Convenience accessor for code that reads clips without mutating them.
    Raises ``AssemblyMutationError`` when the assembly shape is incompatible.
    """
    checked = ensure_clips_key(dict(assembly.assembly))
    return checked["clips"]


def set_clips(assembly: Assembly, clips: list[dict[str, Any]]) -> Assembly:
    """Return a new ``Assembly`` with the clips list replaced.

    Preserves unrelated keys inside ``assembly.assembly``.
    """
    checked = ensure_clips_key(dict(assembly.assembly))
    checked["clips"] = list(clips)
    return materialise_assembly(checked)


# ============================================================================
# Clip helpers (existing m2, unchanged)
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


# -- per-kind clip applicators ------------------------------------------------


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
# Secondary primitive applicators (new m3)
# ============================================================================


# ---------------------------------------------------------------------------
# transition.* applicators
# ---------------------------------------------------------------------------
# Transition identity is keyed by the LEFT clip of the adjacent pair.
# Materialized as ``clip["transition"] = {kind, right_clip_id, duration_seconds}``.


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


# ---------------------------------------------------------------------------
# effect.* applicators
# ---------------------------------------------------------------------------
# Effects are clip-attached, stored as ``clip["effects"]`` list.
# Each effect is ``{"effect_id": str, "params": dict | None}``.


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


# ---------------------------------------------------------------------------
# theme.* applicators
# ---------------------------------------------------------------------------


def _apply_theme_set(assembly: dict[str, Any], payload: ThemeSetPayload) -> None:
    assembly["theme"] = payload.theme_id


def _apply_theme_overridden(assembly: dict[str, Any], payload: ThemeOverriddenPayload) -> None:
    overrides: dict[str, Any] = assembly["theme_overrides"]
    overrides[payload.override_id] = payload.value


# ---------------------------------------------------------------------------
# track.* applicators
# ---------------------------------------------------------------------------


def _apply_track_added(assembly: dict[str, Any], payload: TrackAddedPayload) -> None:
    tracks: list[dict[str, Any]] = assembly["tracks"]
    track_entry: dict[str, Any] = {"id": payload.track_id, "kind": payload.kind}
    if payload.label is not None:
        track_entry["label"] = payload.label
    tracks.append(track_entry)


def _apply_track_removed(assembly: dict[str, Any], payload: TrackRemovedPayload) -> None:
    tracks: list[dict[str, Any]] = assembly["tracks"]
    assembly["tracks"] = [t for t in tracks if t.get("id") != payload.track_id]


# ---------------------------------------------------------------------------
# audio.* applicators
# ---------------------------------------------------------------------------
# Audio bind/unbind targets the clip's ``asset_id`` field.
# This is the renderable timeline clip asset relationship.
# Arrangement-level audio (audio_source.pool_id) stays with arrangement.replaced.


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


# ---------------------------------------------------------------------------
# pool.* applicators
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# arrangement.* applicators
# ---------------------------------------------------------------------------


def _apply_arrangement_replaced(assembly: dict[str, Any], payload: ArrangementReplacedPayload) -> None:
    assembly["arrangement"] = dict(payload.arrangement)


# ============================================================================
# Unified dispatch table
# ============================================================================
# Maps every event kind -> (applicator, list of ensure_keys to call first)
# Each applicator receives (assembly_dict, payload) and mutates assembly in-place.
# For clip-scoped events, clips are extracted from assembly["clips"] and the
# applicator receives (clips, payload, assembly_dict) to also allow clip-scoped
# mutations that need assembly context (e.g. effects).


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
_ENSURE_FN: dict[str, Any] = {
    "clips": ensure_clips_key,
    "tracks": ensure_tracks_key,
    "theme": ensure_theme_key,
    "theme_overrides": ensure_theme_overrides_key,
    "pool": ensure_pool_key,
    "arrangement": ensure_arrangement_key,
}

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

_DISPATCH_MAP: dict[str, tuple[list[str], Any, Any]] = {}
for kind, keys, dispatcher, applicator in _DISPATCH:
    _DISPATCH_MAP[kind] = (keys, dispatcher, applicator)


# ============================================================================
# Materializer entry points (m4 removal seam)
# ============================================================================


def materialize_event(timeline_home: Path, event: TimelineEvent) -> None:
    """Apply a single event to ``assembly.json`` on disk.

    Reads ``assembly.json``, ensures the required keys for *event*'s domain,
    applies the event, and writes the result back atomically.

    Raises ``AssemblyMutationError`` when the event kind is unsupported or the
    assembly shape is incompatible.

    **m4 removal seam**: this function and the synchronous materializer
    block above will be removed in m4 when projection becomes the
    authoritative source for ``assembly.json``.
    """
    dispatch_entry = _DISPATCH_MAP.get(event.kind)
    if dispatch_entry is None:
        raise AssemblyMutationError(
            f"materialize_event does not support event kind {event.kind!r}"
        )

    ensure_keys, dispatcher, applicator = dispatch_entry

    assembly_path = timeline_home / "assembly.json"
    assembly = Assembly.from_json(assembly_path)
    assembly_dict = dict(assembly.assembly)

    if not assembly_dict:
        for key in ensure_keys:
            if key in _EMPTY_INIT_DEFAULTS:
                assembly_dict[key] = _copy_empty_default(_EMPTY_INIT_DEFAULTS[key])

    # Ensure all required keys exist
    for key in ensure_keys:
        ensure_fn = _ENSURE_FN.get(key)
        if ensure_fn is not None:
            assembly_dict = ensure_fn(assembly_dict)

    # Apply the event
    dispatcher(assembly_dict, event.payload, applicator)

    new_assembly = materialise_assembly(assembly_dict)
    new_assembly.write(assembly_path)


def materialize_clip_event(timeline_home: Path, event: TimelineEvent) -> None:
    """Apply a single ``clip.*`` event to ``assembly.json`` on disk.

    Delegates to ``materialize_event`` — kept for backward compatibility
    with existing ``clip_edits.py`` callers.

    **m4 removal seam**: this function and the synchronous materializer
    will be removed in m4 when projection becomes the authoritative source
    for ``assembly.json``.
    """
    materialize_event(timeline_home, event)
