"""Parity shim: gate new artifact-type resolution against legacy _effect_ids path.

ASTRID_TIMELINE_TYPECHECK=new (default) | parity | legacy

The new artifact-type resolution path is canonical as of S1 Step 9.
Parity mode (both paths run + assert) and legacy mode remain selectable
for one release as a safety net; removal is scheduled in S4.
"""
from __future__ import annotations

import functools
import os


def _typecheck_mode() -> str:
    return os.environ.get("ASTRID_TIMELINE_TYPECHECK", "new")


@functools.lru_cache(maxsize=1)
def _get_element_registry():
    from astrid.core.element.registry import load_default_registry
    return load_default_registry()


def _get_artifact_type_registry():
    from astrid.core.contracts.artifact_types import ARTIFACT_TYPE_REGISTRY
    return ARTIFACT_TYPE_REGISTRY


def is_effect_clip(clip_type: str, theme: str | None) -> bool:
    """Return True iff *clip_type* resolves to a visual clip element.

    Mode is read from ASTRID_TIMELINE_TYPECHECK (new|parity|legacy, default: new).

    - legacy: delegates to ``_effect_ids`` membership only (original path).
    - new: delegates to ``is_visual_clip_element`` only (artifact-type path).
    - parity: runs both paths, asserts identical verdict, returns new result.

    SD3 branches b/c (resolved→non-clip/visual or unresolved) produce False;
    the Reigh opaque-fallback contract is preserved by callers acting on the
    returned boolean.
    """
    from astrid.core.timeline.banodoco_schema import _effect_ids as _legacy_effect_ids
    from astrid.core.timeline.validators._type_resolve import is_visual_clip_element

    mode = _typecheck_mode()

    if mode == "legacy":
        return clip_type in _legacy_effect_ids(theme)

    new_result = is_visual_clip_element(
        clip_type, theme, _get_element_registry(), _get_artifact_type_registry()
    )

    if mode == "new":
        return new_result

    # parity mode: run both paths and assert identical verdict
    legacy_result = clip_type in _legacy_effect_ids(theme)
    assert legacy_result == new_result, (
        f"PARITY MISMATCH: clip_type={clip_type!r} theme={theme!r}: "
        f"legacy={legacy_result} new={new_result}"
    )
    return new_result
