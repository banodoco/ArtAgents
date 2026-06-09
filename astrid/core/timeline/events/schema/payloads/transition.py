"""transition.* payload models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from astrid.core.timeline.kinds import normalize_transition_kind

from ._base import TimelineEventSchemaError, _require_nonempty_str


@dataclass(frozen=True)
class TransitionSetPayload:
    left_clip_id: str
    right_clip_id: str
    # ``kind`` is intentionally ``str`` rather than a ``Literal`` type alias.
    # The set of valid transition kinds is defined by the runtime catalog
    # (catalog=\"transition\") in ``astrid.core.pack``, which may be extended
    # by packs via ``extensions.timeline.kinds``.  Validation occurs at
    # runtime through the registry rather than at static-analysis time.
    kind: str
    duration_seconds: float

    def __post_init__(self) -> None:
        _require_nonempty_str(self.left_clip_id, "payload.left_clip_id")
        _require_nonempty_str(self.right_clip_id, "payload.right_clip_id")
        object.__setattr__(
            self,
            "kind",
            normalize_transition_kind(self.kind, error_cls=TimelineEventSchemaError),
        )
        if not isinstance(self.duration_seconds, (int, float)) or isinstance(self.duration_seconds, bool):
            raise TimelineEventSchemaError("payload.duration_seconds must be a number")
        if self.duration_seconds <= 0:
            raise TimelineEventSchemaError("payload.duration_seconds must be > 0")
        object.__setattr__(self, "duration_seconds", float(self.duration_seconds))

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "left_clip_id": self.left_clip_id,
            "right_clip_id": self.right_clip_id,
            "kind": self.kind,
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True)
class TransitionRemovedPayload:
    left_clip_id: str
    right_clip_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.left_clip_id, "payload.left_clip_id")
        _require_nonempty_str(self.right_clip_id, "payload.right_clip_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"left_clip_id": self.left_clip_id, "right_clip_id": self.right_clip_id}
