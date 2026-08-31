"""Shared leaf types, validators, and coercion helpers for event payloads.

This module holds the pieces that both the canonical envelope module
(``..types``) and the per-domain payload modules depend on. It must NOT import
from ``..types`` so that payload modules can import it without forming a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from astrid.core.contracts.schema_validators import require_uuid_str

from ..ulid import is_event_ulid

ActorType = Literal["agent", "human", "system"]
TimelineImportSource = Literal["legacy_local", "editor_save", "other"]
# Event-level clip classification.  Mirrors a subset of the built-in clip
# catalog (catalog=\"clip\") in ``astrid.core.pack``; the catalog also carries
# \"video\", \"image\", \"effect\", and \"opaque\" which are element-kind
# descriptors rather than event-payload clip kinds.
ClipKind = Literal["visual", "audio", "text"]
# Canonical event-schema TrackKind; mirrors
# ``astrid.core.timeline.banodoco_schema.TrackKind`` and
# the public ``astrid.core.timeline.TrackKind`` export, plus
# the built-in track catalog (catalog="track") in ``astrid.core.pack``.
# This definition is intentionally duplicated rather than imported from the
# schema-model module: keeping event-payload schemas decoupled from the
# Banodoco-schema implementation avoids import-time coupling between the two
# layers. Do not consolidate into a shared kinds module.
TrackKind = Literal["visual", "audio"]


class TimelineEventSchemaError(ValueError):
    """Raised when timeline event schema validation fails."""


def _require_uuid_str(value: object, field: str) -> str:
    return require_uuid_str(value, field, TimelineEventSchemaError)


def _require_ulid_str(value: object, field: str) -> str:
    if not is_event_ulid(value):
        raise TimelineEventSchemaError(f"{field} must be a 26-character Crockford ULID")
    return str(value)


def _require_nonempty_str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TimelineEventSchemaError(f"{field} must be a non-empty string")
    return value


def _validate_jsonable(value: Any, field: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise TimelineEventSchemaError(f"{field} keys must be strings")
            _validate_jsonable(nested, f"{field}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_jsonable(nested, f"{field}[{index}]")
        return
    raise TimelineEventSchemaError(f"{field} must be JSON-serializable")


def _coerce_clip_position(value: object, field: str) -> "ClipPosition | None":
    if value is None:
        return None
    if isinstance(value, ClipPosition):
        return value
    if isinstance(value, dict):
        return ClipPosition.from_dict(value)
    raise TimelineEventSchemaError(f"{field} must be a ClipPosition or dict")


@dataclass(frozen=True)
class ClipPosition:
    """Normalized clip position within a timeline.

    clip 'id' strings are the canonical m2 identity.
    Migration to UUID entity_id/external_id is deferred to a later milestone.
    """

    mode: Literal["index", "after", "before"]
    index: int | None = None
    ref_clip_id: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"index", "after", "before"}:
            raise TimelineEventSchemaError(
                "position.mode must be 'index', 'after', or 'before'"
            )
        if self.mode == "index":
            if self.index is None:
                raise TimelineEventSchemaError(
                    "position.index is required when mode is 'index'"
                )
            if not isinstance(self.index, int) or isinstance(self.index, bool):
                raise TimelineEventSchemaError("position.index must be an integer")
        else:
            if self.ref_clip_id is None:
                raise TimelineEventSchemaError(
                    "position.ref_clip_id is required when mode is 'after' or 'before'"
                )
            _require_nonempty_str(self.ref_clip_id, "position.ref_clip_id")
        if self.index is not None and self.mode != "index":
            object.__setattr__(self, "index", None)

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {"mode": self.mode}
        if self.index is not None:
            result["index"] = self.index
        if self.ref_clip_id is not None:
            result["ref_clip_id"] = self.ref_clip_id
        return result

    @classmethod
    def from_dict(cls, raw: object) -> "ClipPosition":
        if not isinstance(raw, dict):
            raise TimelineEventSchemaError("position must be an object")
        return cls(
            mode=raw.get("mode"),
            index=raw.get("index"),
            ref_clip_id=raw.get("ref_clip_id"),
        )
