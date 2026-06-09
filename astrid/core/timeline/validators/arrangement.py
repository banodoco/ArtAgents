from __future__ import annotations

import re
from typing import Any

from astrid.core.timeline.banodoco_schema import (
    _ARRANGEMENT_ALLOWED,
    _ARRANGEMENT_AUDIO_SOURCE_ALLOWED,
    _ARRANGEMENT_CLIP_ALLOWED,
    _ARRANGEMENT_TEXT_OVERLAY_ALLOWED,
    _ARRANGEMENT_VISUAL_SOURCE_ALLOWED,
    _FORBIDDEN_ARRANGEMENT_TIME_KEYS,
    ARRANGEMENT_VERSION,
    _raise_unknown_keys,
)
from astrid.core.timeline.validators.metadata import _validate_generated_at


def _reject_forbidden_arrangement_time_keys(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _FORBIDDEN_ARRANGEMENT_TIME_KEYS:
                raise ValueError(f"{path} contains forbidden time key {key!r}")
            _reject_forbidden_arrangement_time_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden_arrangement_time_keys(child, f"{path}[{index}]")


class ArrangementDurationError(ValueError):
    """Raised when a caller opts into the source-cut duration window."""


def validate_arrangement_duration_window(
    arrangement: Any,
    *,
    min_sec: float = 75.0,
    max_sec: float = 90.0,
) -> None:
    target_duration_sec = arrangement.get("target_duration_sec") if isinstance(arrangement, dict) else None
    if not isinstance(target_duration_sec, (int, float)):
        raise ArrangementDurationError("Arrangement.target_duration_sec must be numeric")
    if not min_sec <= float(target_duration_sec) <= max_sec:
        raise ArrangementDurationError(
            f"Arrangement.target_duration_sec must be between {min_sec:.1f} and {max_sec:.1f} seconds"
        )


def is_all_generative_arrangement(arrangement: Any, pool: Any) -> bool:
    if not isinstance(arrangement, dict) or not isinstance(pool, dict):
        return False
    entries = {
        entry.get("id"): entry
        for entry in pool.get("entries", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    referenced: set[str] = set()
    for clip in arrangement.get("clips", []):
        if not isinstance(clip, dict):
            continue
        for key in ("audio_source", "visual_source"):
            source = clip.get(key)
            if isinstance(source, dict) and isinstance(source.get("pool_id"), str):
                referenced.add(source["pool_id"])
    if not referenced:
        return False
    return all(isinstance(entries.get(pool_id), dict) and entries[pool_id].get("kind") == "generative" for pool_id in referenced)


def validate_arrangement(arrangement: Any, pool_ids: set[str] | None = None) -> None:
    if not isinstance(arrangement, dict):
        raise ValueError("Arrangement must be a JSON object")
    _raise_unknown_keys("Arrangement", arrangement, _ARRANGEMENT_ALLOWED)
    if arrangement.get("version") != ARRANGEMENT_VERSION:
        raise ValueError(f"Arrangement.version must be {ARRANGEMENT_VERSION}")
    _validate_generated_at(arrangement.get("generated_at"), "Arrangement.generated_at")
    brief_text = arrangement.get("brief_text")
    if not isinstance(brief_text, str) or not brief_text:
        raise ValueError("Arrangement.brief_text must be a non-empty string")
    target_duration_sec = arrangement.get("target_duration_sec")
    if not isinstance(target_duration_sec, (int, float)):
        raise ValueError("Arrangement.target_duration_sec must be numeric")
    for field in ("source_slug", "brief_slug", "pool_sha256", "brief_sha256"):
        value = arrangement.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Arrangement.{field} must be a string")
    clips = arrangement.get("clips")
    if not isinstance(clips, list):
        raise ValueError("Arrangement.clips must be a list")
    allowed_ids = set(pool_ids) if pool_ids is not None else None
    seen_orders: set[int] = set()
    seen_uuids: set[str] = set()
    audio_ranges_by_pool: dict[str, list[tuple[float, float, int]]] = {}
    for index, clip in enumerate(clips):
        path = f"Arrangement.clips[{index}]"
        if not isinstance(clip, dict):
            raise ValueError(f"{path} must be an object")
        _raise_unknown_keys(path, clip, _ARRANGEMENT_CLIP_ALLOWED)
        _reject_forbidden_arrangement_time_keys(clip, path)
        for field in ("uuid", "order", "audio_source", "visual_source", "rationale"):
            if field not in clip:
                raise ValueError(f"{path}.{field} is required")
        clip_uuid = clip["uuid"]
        if not isinstance(clip_uuid, str) or re.fullmatch(r"[0-9a-f]{8}", clip_uuid) is None:
            raise ValueError(f"{path}.uuid must be an 8-character lowercase hex string")
        if clip_uuid in seen_uuids:
            raise ValueError(f"{path}.uuid {clip_uuid!r} is not unique")
        seen_uuids.add(clip_uuid)
        order = clip["order"]
        if not isinstance(order, int) or order <= 0:
            raise ValueError(f"{path}.order must be a positive integer")
        if order in seen_orders:
            raise ValueError(f"{path}.order {order} is not unique")
        seen_orders.add(order)
        audio_source = clip.get("audio_source")
        if audio_source is not None:
            if not isinstance(audio_source, dict):
                raise ValueError(f"{path}.audio_source must be an object or null")
            _raise_unknown_keys(f"{path}.audio_source", audio_source, _ARRANGEMENT_AUDIO_SOURCE_ALLOWED)
            pool_id = audio_source.get("pool_id")
            if not isinstance(pool_id, str) or not pool_id:
                raise ValueError(f"{path}.audio_source.pool_id must be a non-empty string")
            if allowed_ids is not None and pool_id not in allowed_ids:
                raise ValueError(f"{path}.audio_source.pool_id {pool_id!r} is not present in the pool")
            trim_sub_range = audio_source.get("trim_sub_range")
            if not isinstance(trim_sub_range, list) or len(trim_sub_range) != 2:
                raise ValueError(f"{path}.audio_source.trim_sub_range must be a 2-item list")
            if not all(isinstance(value, (int, float)) for value in trim_sub_range):
                raise ValueError(f"{path}.audio_source.trim_sub_range entries must be numeric")
            if float(trim_sub_range[1]) <= float(trim_sub_range[0]):
                raise ValueError(f"{path}.audio_source.trim_sub_range must have end > start")
            audio_ranges_by_pool.setdefault(pool_id, []).append(
                (float(trim_sub_range[0]), float(trim_sub_range[1]), order)
            )
        visual_source = clip["visual_source"]
        if visual_source is None:
            if audio_source is None:
                raise ValueError(f"{path}.visual_source must be set when audio_source is null (stinger needs a visual)")
        else:
            if not isinstance(visual_source, dict):
                raise ValueError(f"{path}.visual_source must be an object or null")
            _raise_unknown_keys(f"{path}.visual_source", visual_source, _ARRANGEMENT_VISUAL_SOURCE_ALLOWED)
            visual_pool_id = visual_source.get("pool_id")
            if not isinstance(visual_pool_id, str) or not visual_pool_id:
                raise ValueError(f"{path}.visual_source.pool_id must be a non-empty string")
            if allowed_ids is not None and visual_pool_id not in allowed_ids:
                raise ValueError(f"{path}.visual_source.pool_id {visual_pool_id!r} is not present in the pool")
            role = visual_source.get("role")
            if role not in {"primary", "overlay", "stinger"}:
                raise ValueError(f"{path}.visual_source.role must be one of primary, overlay, stinger")
            params = visual_source.get("params")
            if params is not None and not isinstance(params, dict):
                raise ValueError(f"{path}.visual_source.params must be an object")
        text_overlay = clip.get("text_overlay")
        if text_overlay is not None:
            if not isinstance(text_overlay, dict):
                raise ValueError(f"{path}.text_overlay must be an object or null")
            _raise_unknown_keys(f"{path}.text_overlay", text_overlay, _ARRANGEMENT_TEXT_OVERLAY_ALLOWED)
            content = text_overlay.get("content")
            if not isinstance(content, str) or not content:
                raise ValueError(f"{path}.text_overlay.content must be a non-empty string")
            style_preset = text_overlay.get("style_preset")
            if style_preset is not None and not isinstance(style_preset, str):
                raise ValueError(f"{path}.text_overlay.style_preset must be a string")
        rationale = clip.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(f"{path}.rationale must be a non-empty string")
    for pool_id, ranges in audio_ranges_by_pool.items():
        prev_start = prev_end = None
        prev_order = None
        for trim_start, trim_end, order in sorted(ranges, key=lambda item: item[0]):
            if prev_end is not None and prev_order is not None and prev_end > trim_start + 1e-3:
                raise ValueError(
                    f"Arrangement clips {prev_order} and {order} overlap on "
                    f"audio_source.pool_id {pool_id!r}: "
                    f"[{prev_start:.3f}, {prev_end:.3f}] vs [{trim_start:.3f}, {trim_end:.3f}]"
                )
            prev_start, prev_end, prev_order = trim_start, trim_end, order
