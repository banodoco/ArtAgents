"""Shot clip expansion for render preparation (A4 B2).

Expands `clipType == "shot"` clips by loading their sub-documents and
offsetting their clips into the parent timeline's `at`/`hold` window.

The stored SQLite timeline document is NEVER mutated: this module is purely
memory-only. CLI `timelines show` uses this to print derived expanded counts.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from pathlib import Path

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
      positive remainder inside the parent window are dropped. Overlong child
      windows are clamped to the parent's remaining window (including bounded
      media ``to`` values). Sub-clip ids are preserved, so the expanded
      document is byte-equivalent to a flat compile modulo clip ids.
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

    def _is_still_asset(asset_id: object) -> bool:
        """Recognize image assets before they can reach FFmpeg validation.

        The FFmpeg backend deliberately rejects media ``hold`` semantics. A
        typed image entry (or a conventional image filename in an older
        registry) is enough to fail the invalid authored shape at expansion,
        where it can be repaired, rather than after renderer admission.
        """
        if not isinstance(asset_id, str):
            return False
        entry = merged_assets.get(asset_id)
        if not isinstance(entry, Mapping):
            return False
        kind = str(entry.get("type", "")).lower()
        if kind in {"image", "still", "image/png", "image/jpeg", "image/webp"}:
            return True
        file_value = entry.get("file")
        return isinstance(file_value, str) and Path(file_value).suffix.lower() in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
            ".bmp",
            ".tif",
            ".tiff",
        }

    def _reject_unbounded_stills(doc_clips: list[object]) -> None:
        for raw_clip in doc_clips:
            if not isinstance(raw_clip, Mapping):
                continue
            if (
                raw_clip.get("clipType") == "media"
                and "hold" in raw_clip
                and ("from" not in raw_clip or "to" not in raw_clip)
                and _is_still_asset(raw_clip.get("asset"))
            ):
                raise TimelineEditError(
                    f"Image media clip {raw_clip.get('id', '?')} uses hold without "
                    "explicit from/to source bounds"
                )

    _reject_unbounded_stills(clips)

    for clip in clips:
        if not isinstance(clip, Mapping):
            raise TimelineEditError("timeline clips must be objects")
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
        sub_assets = (
            sub_registry.get("assets", {})
            if isinstance(sub_registry, dict)
            else getattr(sub_registry, "assets", {})
        )
        if not isinstance(sub_assets, Mapping):
            raise TimelineEditError(
                f"sub-timeline {timeline_document_id} has an invalid asset registry"
            )
        # Parent entries are authoritative.  A child may add an asset, but it
        # cannot replace the parent's identity for a colliding key.
        for asset_id, entry in sub_assets.items():
            merged_assets.setdefault(asset_id, entry)
        _reject_unbounded_stills(sub_clips)
        if not sub_clips:
            # Empty sub-doc contributes nothing; the shot clip expands to
            # nothing (renderers must never receive a `shot` clip).
            continue

        for sub_clip in sub_clips:
            if not isinstance(sub_clip, Mapping):
                raise TimelineEditError(
                    f"sub-clip inside sub-timeline {timeline_document_id} must be an object"
                )
            if sub_clip.get("clipType") == "shot":
                raise TimelineEditError(
                    f"nested shot clip detected inside sub-timeline {timeline_document_id}"
                )

            sub_id = sub_clip.get("id")
            if not sub_id:
                raise TimelineEditError(
                    f"Sub-clip missing id inside sub-timeline {timeline_document_id}"
                )
            asset_id = sub_clip.get("asset")
            if (
                isinstance(asset_id, str)
                and asset_id not in sub_assets
                and asset_id not in merged_assets
            ):
                raise TimelineEditError(
                    f"Sub-clip {sub_id} references missing asset {asset_id!r} "
                    f"inside sub-timeline {timeline_document_id}"
                )

            sub_at = float(sub_clip.get("at", 0.0))
            # Sub-clip duration: `hold` for stills/text; `to-from` for bounded
            # media (VO audio clips carry from/to with no hold).
            sub_hold = float(sub_clip.get("hold", 0.0))
            speed = float(sub_clip.get("speed", 1.0))
            if speed <= 0.0:
                raise TimelineEditError(
                    f"Sub-clip {sub_id} inside sub-timeline {timeline_document_id} has invalid speed"
                )
            source_from = float(sub_clip.get("from", 0.0))
            source_to = float(sub_clip.get("to", 0.0))
            if sub_hold <= 0.0:
                if source_to > source_from:
                    sub_hold = (source_to - source_from) / speed
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
            remaining = parent_end - new_at
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
            if new_end > parent_end:
                # Preserve source semantics while making the timeline window
                # finite.  ``hold`` is timeline time; bounded media ``to`` is
                # source time and therefore scales by playback speed.
                if "hold" in expanded_sub:
                    expanded_sub["hold"] = remaining
                if source_to > source_from:
                    expanded_sub["to"] = source_from + remaining * speed
            if sub_clip.get("track") is None:
                expanded_sub["track"] = clip.get("track")
            expanded_clips.append(expanded_sub)

    expanded_config = deepcopy(dict(config))
    expanded_config["clips"] = expanded_clips
    # Return the merged assets as an AssetRegistry-style mapping (the same
    # shape test fixtures and consumers use: {"assets": {id: entry}}).
    return expanded_config, {"assets": merged_assets}
