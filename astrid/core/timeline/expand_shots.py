"""Shot clip expansion for render preparation (A4 B2).

Expands `clipType == "shot"` clips by loading their sub-documents and
offsetting their clips into the parent timeline's `at`/`hold` window.

The stored SQLite timeline document is NEVER mutated: this module is purely
memory-only. CLI `timelines show` uses this to print derived expanded counts.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy

import logging

_LOGGER = logging.getLogger(__name__)

# Registry shape used across the timeline packs: {"assets": {asset_id: entry}}.
_ShotRegistry = Mapping[str, object]
_LoadTimelineFn = Callable[[str], tuple[Mapping[str, object], _ShotRegistry]]

__all__ = ["expand_shot_clips", "_total_assets"]


def _total_assets(registry: Mapping[str, object]) -> int:
    """Count total assets in an AssetRegistry dict."""
    return len(registry.get("assets", {}))


def expand_shot_clips(
    config: Mapping[str, object],
    registry: Mapping[str, object],
    *,
    load_timeline: _LoadTimelineFn,
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    """Expand ``clipType == "shot"`` clips into their sub-document clips.

    Memory-only: the input ``config``/``registry`` dictionaries are NOT mutated;
    the returned config is a deep copy with ``clips`` expanded, and the returned
    registry is a fresh ``{"assets": {...}}`` union (parent wins on conflict).

    Rules (frozen design):
    - Each ``shot`` clip must carry ``params.shot_id`` and
      ``params.timeline_document_id``; anything else fails closed.
    - Sub-clips are offset ``new_at = parent.at + sub.at``; sub-clips with no
      positive remainder inside the parent window are dropped. Sub-clip ids are
      preserved, so the expanded document is byte-equivalent to a flat compile
      modulo clip ids.
    - A ``shot`` clip nested inside a sub-document fails closed (no recursion).
    - Unknown/missing timeline_document_id fails closed via the loader error.
    """
    from astrid.core.timeline._edit_helpers import TimelineEditError

    clips = list(config.get("clips", []))
    expanded_clips: list[dict[str, object]] = []
    merged_assets: dict[str, object] = {}
    # registry may be a dict {"assets": {...}} or an AssetRegistry-like object
    # exposing an ``assets`` attribute (tests use banodoco_schema.AssetRegistry):
    reg_assets = registry.get("assets", {}) if isinstance(registry, dict) else getattr(
        registry, "assets", {}
    )
    merged_assets.update(reg_assets)

    for clip in clips:
        if clip.get("clipType") != "shot":
            expanded_clips.append(dict(clip))
            continue

        params = clip.get("params")
        if not isinstance(params, dict):
            raise TimelineEditError(
                f"Shot clip {clip.get('id', '?')} missing valid params"
            )
        shot_id = params.get("shot_id")
        timeline_document_id = params.get("timeline_document_id")
        if shot_id is None or timeline_document_id is None:
            raise TimelineEditError(
                f"Shot clip {clip.get('id', '?')} missing shot_id or timeline_document_id in params"
            )

        parent_at = float(clip.get("at", 0.0))
        parent_hold = float(clip.get("hold", 0.0))
        parent_end = parent_at + parent_hold

        try:
            sub_config, sub_registry = load_timeline(timeline_document_id)
        except Exception as exc:
            raise TimelineEditError(
                f"Failed to load sub-timeline {timeline_document_id}: {exc}"
            ) from exc

        sub_clips = list(sub_config.get("clips", []))
        if not sub_clips:
            # Empty sub-doc contributes nothing; the shot clip expands to
            # nothing (renderers must never receive a `shot` clip).
            continue

        for sub_clip in sub_clips:
            if sub_clip.get("clipType") == "shot":
                raise TimelineEditError(
                    f"nested shot clip detected inside sub-timeline {timeline_document_id}"
                )

            sub_id = sub_clip.get("id")
            if not sub_id:
                raise TimelineEditError(
                    f"Sub-clip missing id inside sub-timeline {timeline_document_id}"
                )

            sub_at = float(sub_clip.get("at", 0.0))
            # Sub-clip duration: `hold` for stills/text; `to-from` for bounded
            # media (VO audio clips carry from/to with no hold).
            sub_hold = float(sub_clip.get("hold", 0.0))
            if sub_hold <= 0.0:
                from_v = float(sub_clip.get("from", 0.0))
                to_v = float(sub_clip.get("to", 0.0))
                if to_v > from_v:
                    sub_hold = to_v - from_v
            new_at = parent_at + sub_at
            new_end = new_at + sub_hold
            if new_end <= parent_at:
                # No positive remainder inside the parent window; drop.
                _LOGGER.debug(
                    "Dropping sub-clip %s with new_at=%s <= parent_at=%s",
                    sub_id,
                    new_at,
                    parent_at,
                )
                continue
            if new_end > parent_end:
                # Clamp into the parent window: drop if the clip's own start is
                # at/past the parent end (nothing remains to render).
                if new_at >= parent_end:
                    _LOGGER.debug(
                        "Dropping sub-clip %s: new_at=%s >= parent_end=%s",
                        sub_id,
                        new_at,
                        parent_end,
                    )
                    continue

            expanded_sub = dict(sub_clip)
            expanded_sub["at"] = new_at
            if sub_clip.get("track") is None:
                expanded_sub["track"] = clip.get("track")
            expanded_clips.append(expanded_sub)
            sub_assets = (
                sub_registry.get("assets", {})
                if isinstance(sub_registry, dict)
                else getattr(sub_registry, "assets", {})
            )
            merged_assets.update(sub_assets)

    expanded_config = deepcopy(dict(config))
    expanded_config["clips"] = expanded_clips
    # Return the merged assets as an AssetRegistry-style mapping (the same
    # shape test fixtures and consumers use: {"assets": {id: entry}}).
    return expanded_config, {"assets": merged_assets}