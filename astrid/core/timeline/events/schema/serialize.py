"""Canonical JSON serialization and hash helpers for timeline events."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import is_dataclass
from typing import Any

from astrid.core.contracts.event_hash import hash_embedded
from .types import TimelineEvent, TimelineEventSchemaError


def _normalize_for_canonical_json(value: Any) -> Any:
    if isinstance(value, TimelineEvent):
        return _normalize_for_canonical_json(value.to_json_obj())
    if hasattr(value, "to_json_obj"):
        return _normalize_for_canonical_json(value.to_json_obj())
    if is_dataclass(value):
        raise TimelineEventSchemaError(
            "dataclass payloads must define to_json_obj() before canonicalization"
        )
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise TimelineEventSchemaError("canonical JSON does not allow NaN or Infinity")
        return value
    if isinstance(value, list):
        return [_normalize_for_canonical_json(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, nested in value.items():
            if not isinstance(key, str):
                raise TimelineEventSchemaError("canonical JSON object keys must be strings")
            if nested is None:
                continue
            normalized[key] = _normalize_for_canonical_json(nested)
        return normalized
    raise TimelineEventSchemaError("canonical JSON payload must be JSON-serializable")


def canonical_json_bytes(value: Any, *, exclude_hash: bool = False) -> bytes:
    normalized = _normalize_for_canonical_json(value)
    if exclude_hash and isinstance(normalized, dict):
        normalized = {key: nested for key, nested in normalized.items() if key != "hash"}
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_text(value: Any, *, exclude_hash: bool = False) -> str:
    return canonical_json_bytes(value, exclude_hash=exclude_hash).decode("utf-8")


def sha256_hex(value: Any, *, exclude_hash: bool = False) -> str:
    return hashlib.sha256(canonical_json_bytes(value, exclude_hash=exclude_hash)).hexdigest()


def with_event_hash(event: TimelineEvent, *, prev_hash: str | None) -> TimelineEvent:
    digest = hash_embedded(prev_hash, event)
    return TimelineEvent.from_dict({**event.to_json_obj(), "prev_hash": prev_hash, "hash": digest})
