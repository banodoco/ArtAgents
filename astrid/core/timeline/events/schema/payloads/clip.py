"""clip.* payload models.

clip 'id' strings are the canonical m2 identity.
Migration to UUID entity_id/external_id is deferred to a later milestone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from astrid.core.timeline.kinds import normalize_event_clip_kind

from ._base import (
    ClipKind,
    ClipPosition,
    TimelineEventSchemaError,
    _coerce_clip_position,
    _require_nonempty_str,
)


@dataclass(frozen=True)
class ClipAddedPayload:
    clip_id: str
    kind: ClipKind
    asset_id: str
    track_id: str
    position: ClipPosition | dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        object.__setattr__(
            self,
            "kind",
            normalize_event_clip_kind(self.kind, error_cls=TimelineEventSchemaError),
        )
        _require_nonempty_str(self.track_id, "payload.track_id")
        _require_nonempty_str(self.asset_id, "payload.asset_id")
        coerced = _coerce_clip_position(self.position, "payload.position")
        if coerced is not self.position:
            object.__setattr__(self, "position", coerced)

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "clip_id": self.clip_id,
            "kind": self.kind,
            "track_id": self.track_id,
            "asset_id": self.asset_id,
        }
        if self.position is not None:
            result["position"] = self.position.to_json_obj()
        return result


@dataclass(frozen=True)
class ClipRemovedPayload:
    clip_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id}


@dataclass(frozen=True)
class ClipMovedPayload:
    clip_id: str
    position: ClipPosition | dict[str, Any]

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        coerced = _coerce_clip_position(self.position, "payload.position")
        if coerced is None:
            raise TimelineEventSchemaError("payload.position is required for clip.moved")
        if coerced is not self.position:
            object.__setattr__(self, "position", coerced)

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "position": self.position.to_json_obj(),
        }


@dataclass(frozen=True)
class ClipRetrackedPayload:
    clip_id: str
    track_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        _require_nonempty_str(self.track_id, "payload.track_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id, "track_id": self.track_id}


@dataclass(frozen=True)
class ClipRetimedPayload:
    clip_id: str
    start: float
    duration: float

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        if not isinstance(self.start, (int, float)) or isinstance(self.start, bool):
            raise TimelineEventSchemaError("payload.start must be a number")
        if self.start < 0:
            raise TimelineEventSchemaError("payload.start must be >= 0")
        object.__setattr__(self, "start", float(self.start))
        if not isinstance(self.duration, (int, float)) or isinstance(self.duration, bool):
            raise TimelineEventSchemaError("payload.duration must be a number")
        if self.duration <= 0:
            raise TimelineEventSchemaError("payload.duration must be > 0")
        object.__setattr__(self, "duration", float(self.duration))

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "start": self.start,
            "duration": self.duration,
        }


@dataclass(frozen=True)
class ClipSwappedPayload:
    clip_a_id: str
    clip_b_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_a_id, "payload.clip_a_id")
        _require_nonempty_str(self.clip_b_id, "payload.clip_b_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_a_id": self.clip_a_id, "clip_b_id": self.clip_b_id}


@dataclass(frozen=True)
class ClipReplacedPayload:
    clip_id: str
    with_asset_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        _require_nonempty_str(self.with_asset_id, "payload.with_asset_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id, "with_asset_id": self.with_asset_id}


@dataclass(frozen=True)
class ClipTextSetPayload:
    clip_id: str
    text: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        if not isinstance(self.text, str):
            raise TimelineEventSchemaError("payload.text must be a string")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id, "text": self.text}


@dataclass(frozen=True)
class ClipAnnotatedPayload:
    clip_id: str
    note: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        if not isinstance(self.note, str):
            raise TimelineEventSchemaError("payload.note must be a string")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id, "note": self.note}
