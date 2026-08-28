"""Shot clip expansion for render preparation (A4 B2).

Expands `clipType == "shot"` clips by loading their sub-documents and
offsetting their clips into the parent timeline's `at`/`hold` window.

The stored SQLite timeline document is NEVER mutated: this module is purely
memory-only. CLI `timelines show` uses this to print derived expanded counts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astrid.core.timeline.asset_registry import AssetRegistry

    _LoadTimelineFn = Callable[[str], tuple[Mapping[str, object], AssetRegistry]]

__all__ = ["expand_shot_clips", "_total_assets"]

def _total_assets(registry: Mapping[str, object]) -> int:
    """Count total assets in an AssetRegistry dict."""
    return len(registry.get("assets", {}))


_LOGGER = logging.getLogger(__name__)


def expand_shot_clips(
    config: Mapping[str, object],
    registry: AssetRegistry,
    *,
    load_timeline: _LoadTimelineFn,
) -> tuple[Mapping[str, object], AssetRegistry]:
    """Expand shot clips in-place (memory-only; no DB write).

    For each clip with ``clipType == "shot"``:
    - Requires ``params.shot_id`` and ``params.timeline_document_id``.
    - Loads the sub-document via ``load_timeline(timeline_document_id)``.
    - Offsets every sub-clip: ``new_at = parent.at + sub.at``.
    - Clamps sub-clips into the parent's ``at + hold`` window.
    - Drops sub-clips with non-positive remainder.
    - Merges ``sub_registry`` assets into ``registry`` (union, no clobber;
      parent wins on conflict).
    - Nested ``shot`` clips (shot inside a sub-doc) raise
      ``TimelineEditError``.
    - Missing params raise ``TimelineEditError``.
    - Unknown ``timeline_document_id`` raises ``TimelineEditError``.
    - Preserves sub-clip IDs.
    - The returned ``config`` clips are the result of the expansion.

    The function mutates ``config`` (by applying edits to its clips list) and
    returns it along with the updated ``registry``. Neither the input dict nor
    the original timeline document is persisted.

    Args:
        config: Timeline document dict with a ``"clips"`` list.
        registry: Asset registry to merge sub-doc assets into.
        load_timeline: Callable that takes a timeline ID and returns
            ``(sub_config, sub_registry)``. This callback MUST read from the
            same database connection used by the caller (no second DB hit).

    Returns:
        ``(expanded_config, merged_registry)`` where ``expanded_config`` has
        the expanded clips list (shot clips replaced by their expanded content)
        and ``merged_registry`` is the union of the parent and all sub-registries.

    Raises:
        TimelineEditError: If any shot clip is malformed, references an
            unknown timeline, or is nested inside another shot clip.
    """
    from astrid.core.timeline._edit_helpers import TimelineEditError

    # Extract the clips list; fail closed if missing/empty.
    clips = list(config.get("clips", []))
    if not clips:
        return config, registry

    # Track expanded clips to avoid nested expansion.
    expanded_shot_ids = set[str]()

    for clip in clips:
        clip_type = clip.get("clipType")
        if clip_type != "shot":
            continue

        # Require params.
        params = clip.get("params", {})
        if not isinstance(params, dict):
            raise TimelineEditError(f"Shot clip {clip.get('id', '?')} missing valid params")
        shot_id = params.get("shot_id")
        timeline_document_id = params.get("timeline_document_id")
        if shot_id is None or timeline_document_id is None:
            raise TimelineEditError(
                f"Shot clip {clip.get('id', '?')} missing shot_id or timeline_document_id in params"
            )

        # Fail closed on nested shot.
        if shot_id in expanded_shot_ids:
            raise TimelineEditError(f"Nested shot clip detected: parent shot_id={shot_id}")

        # Load sub-document.
        try:
            sub_config, sub_registry = load_timeline(timeline_document_id)
        except Exception as exc:
            # Wrap any DB/JSON error into a TimelineEditError for fail-closed behavior.
            raise TimelineEditError(f"Failed to load sub-timeline {timeline_document_id}: {exc}") from exc

        # Validate sub-config has a clips list.
        sub_clips = list(sub_config.get("clips", []))
        if not sub_clips:
            # Empty sub-doc is allowed; no clips to expand.
            continue

        # Load parent clip to get its at/hold boundaries.
        parent_at = float(clip.get("at", 0.0))

        # Track new clips to insert at the shot clip position.
        new_sub_clips: list[dict] = []

        for sub_clip in sub_clips:
            # Use the original sub-clip ID as the unique identifier.
            sub_clip_id = sub_clip.get("id", "")
            if not sub_clip_id:
                raise TimelineEditError(f"Sub-clip {sub_clip.get('id', '?')} missing id")

            # Offset into parent timeline.
            sub_at = float(sub_clip.get("at", 0.0))
            new_at = parent_at + sub_at

            # Clamp into parent's hold window.
            hold = float(sub_clip.get("hold", 0.0))
            new_end = new_at + hold

            if new_end <= parent_at:
                # No remainder; drop the sub-clip.
                _LOGGER.debug(
                    f"Dropping sub-clip {sub_clip_id} with new_at={new_at:.3f} <= parent_at={parent_at:.3f}"
                )
                continue
            expanded_sub = dict(sub_clip)
            expanded_sub["at"] = new_at
            expanded_sub["hold"] = hold
            # Preserve the original ID so it's still distinct from parent-level clips.
            new_sub_clips.append(expanded_sub)

        if not new_sub_clips:
            # All sub-clips dropped; the shot clip becomes empty.
            _LOGGER.debug(f"All sub-clips dropped for shot clip {shot_id}; keeping shot placeholder")
            # Keep the shot clip but with empty clips list (no expansion).
            expanded_shot_ids.add(shot_id)
            continue

        # Merge sub-registry into parent registry (union, no clobber; parent wins).
        # Merge sub-registry into parent registry (union, no clobber; parent wins).
        merged_registry = {"assets": dict(registry.get("assets", {}))}
        merged_assets = merged_registry["assets"]
        merged_assets.update(sub_registry.get("assets", {}))

        # Replace the shot clip with its expanded clips.
        shot_index = next(
            (i for i, c in enumerate(clips) if c.get("clipType") == "shot" and c.get("id") == shot_id),
            None,
        )
        if shot_index is None:
            raise TimelineEditError(f"Shot clip {shot_id} not found in parent after initial pass")

        # Insert expanded clips after the shot placeholder.
        clips[shot_index : shot_index + 1] = new_sub_clips
        expanded_shot_ids.add(shot_id)
        registry = merged_registry

    # Apply the expanded clips back to the config.
    # We can safely mutate config["clips"] since we're operating on the input dict.
    if "clips" in config:
        config["clips"] = clips

    return config, registry