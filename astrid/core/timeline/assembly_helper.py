"""Assembly.json compatibility contract for clip-level mutations.

This module defines the **only** allowed mutation path for ``assembly.json``
during m2 clip editing.  Every clip edit that must keep ``assembly.json``
in sync with the event stream does so through the helpers here.

Contract (locked for m2)
-------------------------

The compatibility target is ``Assembly.assembly`` — the opaque dict stored
under the ``"assembly"`` key of the on-disk ``assembly.json`` file:

.. code-block:: json

    {"schema_version": 1, "assembly": { ... }}

Three explicit behaviors:

    (a) **Empty assembly** (``assembly == {}``)
        Initialised for clip editing with ``{"clips": []}``.

    (b) **Existing assembly with a ``"clips"`` key**
        The caller updates the clip list in-place; the helper simply
        ensures the pre-condition holds.

    (c) **Non-empty assembly without a ``"clips"`` key**
        The helper raises ``AssemblyMutationError`` at mutation time.
        This protects unknown assembly shapes from accidental corruption
        by clip-editing code that does not know what the other keys mean.

.. note::

    ``assembly.json`` is maintained by a **compatibility materializer**
    that runs synchronously after each clip event append.  In m4 this
    file will become a projection-rebuild target and the synchronous
    materializer will be removed.

    Until m4, a crash between ``append_event`` and the materializer write
    can leave the event stream ahead of ``assembly.json``.  Accept this
    window; m4 projection will close it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .events.schema import (
    ClipAddedPayload,
    ClipAnnotatedPayload,
    ClipMovedPayload,
    ClipPosition,
    ClipRemovedPayload,
    ClipReplacedPayload,
    ClipRetimedPayload,
    ClipSwappedPayload,
    ClipTextSetPayload,
    TimelineEvent,
)
from .model import Assembly, TIMELINE_SCHEMA_VERSION


class AssemblyMutationError(RuntimeError):
    """Raised when *assembly.json* cannot be safely mutated by clip-editing code."""


# ---------------------------------------------------------------------------
# Core contract: ensure clips key
# ---------------------------------------------------------------------------


def ensure_clips_key(assembly: dict[str, Any]) -> dict[str, Any]:
    """Return *assembly* guaranteed to contain a ``"clips"`` key.

    Cases:

    * *assembly* is empty → return ``{"clips": []}``
    * *assembly* has ``"clips"`` → return as-is
    * *assembly* is non-empty but lacks ``"clips"`` → raise ``AssemblyMutationError``
    """
    if not isinstance(assembly, dict):
        raise AssemblyMutationError(
            f"assembly must be a dict, got {type(assembly).__name__}"
        )

    if not assembly:
        # Case (a): empty — initialise with clips list.
        return {"clips": []}

    if "clips" in assembly:
        # Case (b): already has clips — caller will update in-place.
        if not isinstance(assembly["clips"], list):
            raise AssemblyMutationError(
                "assembly has a 'clips' key but it is not a list"
            )
        return assembly

    # Case (c): non-empty, no clips — we don't know what this is.
    raise AssemblyMutationError(
        "assembly has existing content but no 'clips' key. "
        "Clip-editing code cannot safely mutate an unknown assembly shape. "
        f"Existing keys: {sorted(assembly.keys())}"
    )


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
# Compatibility materializer (m4 removal seam)
# ============================================================================
#
# Every function below is part of the **synchronous compatibility
# materializer** that keeps ``assembly.json`` in sync with the event stream
# after each clip.* event append.
#
# In m4 this entire block will be removed when projection becomes the
# authoritative source for ``assembly.json``.  Until then, ``clip_edits.py``
# calls ``materialize_clip_event()`` after every successful
# ``backend.append_event(...)`` to maintain backwards compatibility for
# readers like ``crud.show_timeline()``.
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


# -- per-kind applicators ----------------------------------------------------


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


# -- materializer dispatch ----------------------------------------------------


_APPLICATORS = {
    "clip.added": _apply_clip_added,
    "clip.removed": _apply_clip_removed,
    "clip.moved": _apply_clip_moved,
    "clip.retimed": _apply_clip_retimed,
    "clip.swapped": _apply_clip_swapped,
    "clip.replaced": _apply_clip_replaced,
    "clip.text_set": _apply_clip_text_set,
    "clip.annotated": _apply_clip_annotated,
}


def materialize_clip_event(timeline_home: Path, event: TimelineEvent) -> None:
    """Apply a single ``clip.*`` event to ``assembly.json`` on disk.

    Reads ``assembly.json``, applies *event* to
    ``Assembly.assembly['clips']``, and writes the result back atomically.

    Preserves unrelated ``Assembly.assembly`` keys.  Raises
    ``AssemblyMutationError`` when the assembly shape is incompatible
    (non-empty, no ``clips`` key).

    **m4 removal seam**: this function and the synchronous materializer
    block above will be removed in m4 when projection becomes the
    authoritative source for ``assembly.json``.  Until then it is called
    by ``clip_edits.py`` after each successful ``append_event``.
    """
    applicator = _APPLICATORS.get(event.kind)
    if applicator is None:
        raise AssemblyMutationError(
            f"materialize_clip_event does not support event kind {event.kind!r}"
        )

    assembly_path = timeline_home / "assembly.json"
    assembly = Assembly.from_json(assembly_path)
    assembly_dict = ensure_clips_key(dict(assembly.assembly))
    clips: list[dict[str, Any]] = assembly_dict["clips"]

    applicator(clips, event.payload)

    new_assembly = materialise_assembly(assembly_dict)
    new_assembly.write(assembly_path)
