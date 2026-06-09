"""pool.* payload models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._base import TimelineEventSchemaError, _require_nonempty_str


@dataclass(frozen=True)
class PoolAssetAddedPayload:
    asset_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.asset_id, "payload.asset_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"asset_id": self.asset_id}


@dataclass(frozen=True)
class PoolAssetRemovedPayload:
    asset_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.asset_id, "payload.asset_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"asset_id": self.asset_id}


@dataclass(frozen=True)
class PoolAssetScoredPayload:
    asset_id: str
    score: float

    def __post_init__(self) -> None:
        _require_nonempty_str(self.asset_id, "payload.asset_id")
        if not isinstance(self.score, (int, float)) or isinstance(self.score, bool):
            raise TimelineEventSchemaError("payload.score must be a number")
        if self.score < 0 or self.score > 1:
            raise TimelineEventSchemaError("payload.score must be between 0 and 1")
        object.__setattr__(self, "score", float(self.score))

    def to_json_obj(self) -> dict[str, Any]:
        return {"asset_id": self.asset_id, "score": self.score}
