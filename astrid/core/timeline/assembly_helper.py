"""Thin delegation wrapper around ``projection.py`` for assembly.json
compatibility writes.

After m4 this module no longer contains an independent dispatch table or
applicator functions.  ``materialize_event()`` and ``materialize_clip_event()``
delegate to the canonical projector in ``projection.py``: they load the current
``assembly.json`` from disk, fold a single event onto it via
``apply_event_to_assembly()``, and atomically write the result back.

In m4 the authority model shifted: mutation paths now call
``regenerate_projection()`` (via ``_edit_helpers._materialize()``) to rebuild
``assembly.json`` from the full canonical event stream.  This module remains
as a thin compatibility shim for callers that still need the per-event fold
(e.g. tests importing ``AssemblyMutationError`` or ``materialize_event``).

External callers
----------------
* ``_edit_helpers._materialize()`` no longer calls ``materialize_event()`` —
  it now calls ``regenerate_projection()`` directly.
* ``clip_edits.py`` callers in tests import ``AssemblyMutationError``.
* ``test_secondary_edits.py`` imports ``AssemblyMutationError`` and
  ``materialize_event``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.core.project.jsonio import read_json, write_json_atomic
from astrid.core.timeline.model import Assembly, TIMELINE_SCHEMA_VERSION

from .events.schema import TimelineEvent
from .projection import _DISPATCH_MAP, apply_event_to_assembly


# ---------------------------------------------------------------------------
# Exception (kept for backward compatibility with test imports)
# ---------------------------------------------------------------------------


class AssemblyMutationError(RuntimeError):
    """Raised when *assembly.json* cannot be safely mutated by editing code."""


# ---------------------------------------------------------------------------
# Generic ensure-key infrastructure (preserved for backward-compatible error
# messages; the projector owns the authoritative applicator logic).
# ---------------------------------------------------------------------------


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


def ensure_clips_key(assembly: dict[str, Any]) -> dict[str, Any]:
    return _ensure_key(assembly, "clips", [], type_check=list)


def ensure_tracks_key(assembly: dict[str, Any]) -> dict[str, Any]:
    return _ensure_key(assembly, "tracks", [], type_check=list)


def ensure_theme_key(assembly: dict[str, Any]) -> dict[str, Any]:
    return _ensure_key(assembly, "theme", "", type_check=str)


def ensure_theme_overrides_key(assembly: dict[str, Any]) -> dict[str, Any]:
    return _ensure_key(assembly, "theme_overrides", {}, type_check=dict)


def ensure_pool_key(assembly: dict[str, Any]) -> dict[str, Any]:
    return _ensure_key(assembly, "pool", {"entries": []}, type_check=dict)


def ensure_arrangement_key(assembly: dict[str, Any]) -> dict[str, Any]:
    return _ensure_key(assembly, "arrangement", {"clips": []}, type_check=dict)


# Map of key → ensure function (mirrors the keys used by the projector's
# dispatch table).  Used for pre-flight validation before delegating to
# the projector, so error messages remain backward-compatible.
_ENSURE_FN: dict[str, Any] = {
    "clips": ensure_clips_key,
    "tracks": ensure_tracks_key,
    "theme": ensure_theme_key,
    "theme_overrides": ensure_theme_overrides_key,
    "pool": ensure_pool_key,
    "arrangement": ensure_arrangement_key,
}


# ---------------------------------------------------------------------------
# Compatibility materializer entry points (delegation wrappers)
# ---------------------------------------------------------------------------


def materialize_event(timeline_home: Path, event: TimelineEvent) -> None:
    """Apply a single *event* to ``assembly.json`` on disk.

    1. Load ``assembly.json`` (wrapper shape ``{schema_version, assembly}``).
    2. Pre-validate assembly shape via ``_ENSURE_FN`` (backward-compatible
       error messages).
    3. Fold *event* onto the inner assembly dict via
       ``apply_event_to_assembly()``.
    4. Atomically write the projected result back to ``assembly.json``,
       preserving the wrapper shape.

    Raises ``AssemblyMutationError`` when the assembly file is malformed or
    the projector raises a ``ProjectionError``.
    """
    assembly_path = timeline_home / "assembly.json"
    try:
        assembly = Assembly.from_json(assembly_path)
    except FileNotFoundError:
        assembly = Assembly(
            schema_version=TIMELINE_SCHEMA_VERSION,
            assembly={},
        )
    except Exception as exc:
        raise AssemblyMutationError(
            f"failed to read assembly.json for materialization: {exc}"
        ) from exc

    current_state = dict(assembly.assembly)

    # Pre-validate: look up which keys this event kind requires and run the
    # backward-compatible ensure checks so error messages match the old format.
    # Important: when the assembly is empty we initialize ALL required keys
    # at once (as the old code did via _EMPTY_INIT_DEFAULTS), then run the
    # type-checking ensure functions which will find the keys present.
    dispatch_entry = _DISPATCH_MAP.get(event.kind)
    if dispatch_entry is not None:
        ensure_keys, _dispatcher, _applicator = dispatch_entry
        if not current_state:
            # Empty assembly: bulk-initialise all required keys.
            from copy import deepcopy

            _EMPTY_INIT_DEFAULTS: dict[str, Any] = {
                "clips": [],
                "tracks": [],
                "theme": "",
                "theme_overrides": {},
                "pool": {"entries": []},
                "arrangement": {"clips": []},
            }
            for key in ensure_keys:
                if key in _EMPTY_INIT_DEFAULTS:
                    current_state[key] = deepcopy(_EMPTY_INIT_DEFAULTS[key])
        else:
            # Non-empty assembly: run each ensure check independently.
            for key in ensure_keys:
                ensure_fn = _ENSURE_FN.get(key)
                if ensure_fn is not None:
                    current_state = ensure_fn(current_state)

    # Fold the single event onto the current state.
    try:
        new_state = apply_event_to_assembly(current_state, event)
    except Exception as exc:
        raise AssemblyMutationError(
            f"projection failed for event {event.event_id!r} "
            f"({event.kind!r}): {exc}"
        ) from exc

    # Write back atomically with the wrapper shape.
    new_assembly = Assembly(
        schema_version=TIMELINE_SCHEMA_VERSION,
        assembly=new_state,
    )
    new_assembly.write(assembly_path)


def materialize_clip_event(timeline_home: Path, event: TimelineEvent) -> None:
    """Apply a single ``clip.*`` event to ``assembly.json`` on disk.

    Delegates to ``materialize_event`` — kept for backward compatibility
    with existing ``clip_edits.py`` callers.
    """
    materialize_event(timeline_home, event)
