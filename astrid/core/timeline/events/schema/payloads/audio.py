"""audio.* payload models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._base import _require_nonempty_str


@dataclass(frozen=True)
class AudioBoundPayload:
    clip_id: str
    asset_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        _require_nonempty_str(self.asset_id, "payload.asset_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id, "asset_id": self.asset_id}


@dataclass(frozen=True)
class AudioUnboundPayload:
    clip_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id}
