from __future__ import annotations

from typing import Any

from astrid.core.timeline.banodoco_schema import (
    _POOL_ALLOWED,
    _POOL_ENTRY_ALLOWED,
    _POOL_SCORES_ALLOWED,
    _SOURCE_IDS_ALLOWED,
    POOL_VERSION,
    _raise_unknown_keys,
)
from astrid.core.timeline.validators.metadata import _validate_generated_at
# Registry lookups are late-imported through banodoco_schema so that
# mock.patch.object(banodoco_schema, ...) still affects internal callers.


def _validate_source_ids(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    _raise_unknown_keys(path, value, _SOURCE_IDS_ALLOWED)
    segment_ids = value.get("segment_ids")
    if segment_ids is not None:
        if not isinstance(segment_ids, list) or not all(isinstance(segment_id, int) for segment_id in segment_ids):
            raise ValueError(f"{path}.segment_ids must be a list of integers")
    scene_id = value.get("scene_id")
    if scene_id is not None and not isinstance(scene_id, str):
        raise ValueError(f"{path}.scene_id must be a string")


def _validate_pool_scores(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    _raise_unknown_keys(path, value, _POOL_SCORES_ALLOWED)
    for key, score in value.items():
        if not isinstance(score, (int, float)):
            raise ValueError(f"{path}.{key} must be numeric")


def validate_pool(pool: Any) -> None:
    if not isinstance(pool, dict):
        raise ValueError("Pool must be a JSON object")
    _raise_unknown_keys("Pool", pool, _POOL_ALLOWED)
    if pool.get("version") != POOL_VERSION:
        raise ValueError(f"Pool.version must be {POOL_VERSION}")
    _validate_generated_at(pool.get("generated_at"), "Pool.generated_at")
    source_slug = pool.get("source_slug")
    if source_slug is not None and not isinstance(source_slug, str):
        raise ValueError("Pool.source_slug must be a string")
    entries = pool.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Pool.entries must be a list")
    seen_ids: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"Pool.entries[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{path} must be an object")
        _raise_unknown_keys(path, entry, _POOL_ENTRY_ALLOWED)
        for field in ("id", "kind", "category", "duration", "scores", "excluded"):
            if field not in entry:
                raise ValueError(f"{path}.{field} is required")
        entry_id = entry["id"]
        if not isinstance(entry_id, str) or not entry_id:
            raise ValueError(f"{path}.id must be a non-empty string")
        if entry_id in seen_ids:
            raise ValueError(f"{path}.id {entry_id!r} is not unique")
        seen_ids.add(entry_id)
        if entry.get("kind") not in {"source", "generative"}:
            raise ValueError(f"{path}.kind must be one of source, generative")
        if entry.get("category") not in {"dialogue", "visual", "reaction", "applause", "music"}:
            raise ValueError(f"{path}.category must be one of dialogue, visual, reaction, applause, music")
        _validate_pool_scores(entry["scores"], f"{path}.scores")
        if not isinstance(entry.get("excluded"), bool):
            raise ValueError(f"{path}.excluded must be a boolean")
        excluded_reason = entry.get("excluded_reason")
        if excluded_reason is not None and not isinstance(excluded_reason, str):
            raise ValueError(f"{path}.excluded_reason must be a string or null")
        if entry["kind"] == "source":
            for field in ("asset", "src_start", "src_end", "duration", "source_ids"):
                if field not in entry:
                    raise ValueError(f"{path}.{field} is required for source entries")
            if not isinstance(entry.get("asset"), str) or not entry["asset"]:
                raise ValueError(f"{path}.asset must be a non-empty string")
            for field in ("src_start", "src_end", "duration"):
                if not isinstance(entry.get(field), (int, float)):
                    raise ValueError(f"{path}.{field} must be numeric")
            if float(entry["src_start"]) < 0 or float(entry["src_end"]) < 0 or float(entry["duration"]) < 0:
                raise ValueError(f"{path} timing values must be non-negative")
            if float(entry["src_end"]) < float(entry["src_start"]):
                raise ValueError(f"{path}.src_end must be >= src_start")
            _validate_source_ids(entry["source_ids"], f"{path}.source_ids")
        else:
            for field in ("effect_id", "param_schema", "defaults", "meta"):
                if field not in entry:
                    raise ValueError(f"{path}.{field} is required for generative entries")
            if entry.get("duration") is not None:
                raise ValueError(f"{path}.duration must be null for generative entries")
            effect_id = entry.get("effect_id")
            if not isinstance(effect_id, str) or not effect_id:
                raise ValueError(f"{path}.effect_id must be a non-empty string")
            # New artifact-type resolution is canonical; legacy _effect_ids path
            # retained via _parity shim for env-flagged oracle (S4: remove shim).
            from astrid.core.timeline.validators._parity import is_effect_clip
            if not is_effect_clip(effect_id, None):
                raise ValueError(f"{path}.effect_id {effect_id!r} is not present in the effects catalog")
            for field in ("param_schema", "defaults", "meta"):
                if not isinstance(entry.get(field), dict):
                    raise ValueError(f"{path}.{field} must be an object")
