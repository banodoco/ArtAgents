"""arrangement.* payload models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._base import TimelineEventSchemaError, _validate_jsonable


@dataclass(frozen=True)
class ArrangementReplacedPayload:
    arrangement: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.arrangement, dict):
            raise TimelineEventSchemaError("payload.arrangement must be an object")
        _validate_jsonable(self.arrangement, "payload.arrangement")

    def to_json_obj(self) -> dict[str, Any]:
        return {"arrangement": dict(self.arrangement)}
