"""Shared acquisition request helpers for dataset-build source providers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def build_acquisition_request(
    *,
    processed_source_ids: Any,
    acquisition_request: Mapping[str, Any] | None,
) -> dict[str, Any]:
    incoming = dict(acquisition_request or {})
    target_shortfalls = incoming.get("target_shortfalls") if isinstance(incoming.get("target_shortfalls"), Mapping) else {}
    limit_hint = incoming.get("limit_hint")
    if limit_hint is None and target_shortfalls:
        limit_hint = sum(int(value) for value in target_shortfalls.values() if isinstance(value, int))
    return {
        "round_index": int(incoming.get("round_index", 0)),
        "target_shortfalls": dict(target_shortfalls or {}),
        "limit_hint": int(limit_hint) if isinstance(limit_hint, int) and limit_hint >= 0 else None,
        "exclude_candidate_ids": sorted(string_set(incoming.get("exclude_candidate_ids"))),
        "exclude_source_ids": sorted(string_set(incoming.get("exclude_source_ids"))),
        "exclude_media_hashes": sorted(string_set(incoming.get("exclude_media_hashes"))),
        "feedback_hints": sorted(string_set(incoming.get("feedback_hints"))),
        "processed_source_ids": sorted(string_set(processed_source_ids, incoming.get("processed_source_ids"))),
    }


def request_from_config(config: Mapping[str, Any]) -> Mapping[str, Any]:
    request = config.get("acquisition_request")
    return request if isinstance(request, Mapping) else {}


def limit_hint_from_config(config: Mapping[str, Any], request: Mapping[str, Any]) -> int | None:
    value = config.get("limit_hint", request.get("limit_hint"))
    return int(value) if isinstance(value, int) and value >= 0 else None


def record_acquisition_result(
    provider: Any,
    config: Mapping[str, Any],
    *,
    provider_id: str,
    request: Mapping[str, Any],
    considered: int,
    yielded: int,
    skipped_processed: int = 0,
    skipped_excluded: int = 0,
    skipped_duplicate_media: int = 0,
) -> dict[str, Any]:
    result = {
        "provider": provider_id,
        "round_index": int(request.get("round_index", 0)) if isinstance(request.get("round_index", 0), int) else 0,
        "limit_hint": request.get("limit_hint"),
        "considered": considered,
        "yielded": yielded,
        "skipped_processed": skipped_processed,
        "skipped_excluded": skipped_excluded,
        "skipped_duplicate_media": skipped_duplicate_media,
        "no_new_candidates": yielded == 0,
        "reason": "no_new_candidates" if yielded == 0 else "candidates_yielded",
    }
    setattr(provider, "last_acquisition_result", result)
    if isinstance(config, dict):
        config["acquisition_result"] = result
    return result


def string_set(*values: Any) -> set[str]:
    result: set[str] = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, (str, bytes)):
            text = str(value)
            if text:
                result.add(text)
            continue
        try:
            for item in value:
                text = str(item)
                if text:
                    result.add(text)
        except TypeError:
            text = str(value)
            if text:
                result.add(text)
    return result
