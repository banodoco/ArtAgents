"""theme.* payload models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._base import _require_nonempty_str, _validate_jsonable


@dataclass(frozen=True)
class ThemeSetPayload:
    theme_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.theme_id, "payload.theme_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"theme_id": self.theme_id}


@dataclass(frozen=True)
class ThemeOverriddenPayload:
    override_id: str
    value: Any

    def __post_init__(self) -> None:
        _require_nonempty_str(self.override_id, "payload.override_id")
        _validate_jsonable(self.value, "payload.value")

    def to_json_obj(self) -> dict[str, Any]:
        return {"override_id": self.override_id, "value": self.value}
