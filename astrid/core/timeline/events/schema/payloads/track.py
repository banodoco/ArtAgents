"""track.* payload models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from astrid.core.timeline.kinds import normalize_track_kind

from ._base import (
    TimelineEventSchemaError,
    TrackKind,
    _require_nonempty_str,
)


@dataclass(frozen=True)
class TrackAddedPayload:
    track_id: str
    kind: TrackKind
    label: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.track_id, "payload.track_id")
        object.__setattr__(
            self,
            "kind",
            normalize_track_kind(self.kind, error_cls=TimelineEventSchemaError),
        )
        _require_nonempty_str(self.label, "payload.label")

    def to_json_obj(self) -> dict[str, Any]:
        return {"track_id": self.track_id, "kind": self.kind, "label": self.label}


@dataclass(frozen=True)
class TrackRemovedPayload:
    track_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.track_id, "payload.track_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"track_id": self.track_id}
