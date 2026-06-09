"""effect.* payload models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._base import (
    TimelineEventSchemaError,
    _require_nonempty_str,
    _validate_jsonable,
)


@dataclass(frozen=True)
class EffectAddedPayload:
    clip_id: str
    effect_id: str
    params: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        _require_nonempty_str(self.effect_id, "payload.effect_id")
        if self.params is not None:
            if not isinstance(self.params, dict):
                raise TimelineEventSchemaError("payload.params must be a dict when present")
            _validate_jsonable(self.params, "payload.params")

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {"clip_id": self.clip_id, "effect_id": self.effect_id}
        if self.params is not None:
            result["params"] = dict(self.params)
        return result


@dataclass(frozen=True)
class EffectRemovedPayload:
    clip_id: str
    effect_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        _require_nonempty_str(self.effect_id, "payload.effect_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id, "effect_id": self.effect_id}


@dataclass(frozen=True)
class EffectTunedPayload:
    clip_id: str
    effect_id: str
    param: str
    value: Any

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        _require_nonempty_str(self.effect_id, "payload.effect_id")
        _require_nonempty_str(self.param, "payload.param")
        _validate_jsonable(self.value, "payload.value")

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "effect_id": self.effect_id,
            "param": self.param,
            "value": self.value,
        }
