from __future__ import annotations

from typing import Any

from astrid.core.timeline.banodoco_schema import METADATA_VERSION


def _validate_generated_at(value: Any, path: str) -> None:
    if not isinstance(value, str) or not value or not value.endswith("Z"):
        raise ValueError(f"{path} must be a non-empty UTC timestamp ending in 'Z'")


def validate_metadata(meta: Any) -> None:
    if not isinstance(meta, dict):
        raise ValueError("Metadata must be a JSON object")
    if meta.get("version") != METADATA_VERSION:
        raise ValueError(f"Metadata.version must be {METADATA_VERSION}")
    generated_at = meta.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at or not generated_at.endswith("Z"):
        raise ValueError("Metadata.generated_at must be a non-empty UTC timestamp ending in 'Z'")
    for field in ("pipeline", "clips", "sources"):
        value = meta.get(field)
        if not isinstance(value, dict):
            raise ValueError(f"Metadata.{field} must be an object")
    for clip_id, clip_meta in meta["clips"].items():
        if not isinstance(clip_meta, dict):
            raise ValueError(f"Metadata.clips[{clip_id!r}] must be an object")
    for source_key, source_meta in meta["sources"].items():
        if not isinstance(source_meta, dict):
            raise ValueError(f"Metadata.sources[{source_key!r}] must be an object")
