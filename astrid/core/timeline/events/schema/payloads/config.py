"""timeline.* lifecycle and configuration payload models."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from astrid.core.timeline.banodoco_schema import validate_timeline_config_for_container

from ._base import (
    TimelineEventSchemaError,
    TimelineImportSource,
    _require_nonempty_str,
    _require_uuid_str,
    _validate_jsonable,
)


@dataclass(frozen=True)
class TimelineCreatedPayload:
    timeline_id: str
    slug: str
    name: str

    def __post_init__(self) -> None:
        _require_uuid_str(self.timeline_id, "payload.timeline_id")
        _require_nonempty_str(self.slug, "payload.slug")
        _require_nonempty_str(self.name, "payload.name")

    def to_json_obj(self) -> dict[str, Any]:
        return {"timeline_id": self.timeline_id, "slug": self.slug, "name": self.name}


@dataclass(frozen=True)
class TimelineRenamedPayload:
    old_slug: str
    new_slug: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.old_slug, "payload.old_slug")
        _require_nonempty_str(self.new_slug, "payload.new_slug")

    def to_json_obj(self) -> dict[str, Any]:
        return {"old_slug": self.old_slug, "new_slug": self.new_slug}


@dataclass(frozen=True)
class TimelineDefaultSetPayload:
    timeline_id: str

    def __post_init__(self) -> None:
        _require_uuid_str(self.timeline_id, "payload.timeline_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"timeline_id": self.timeline_id}


@dataclass(frozen=True)
class TimelineTombstonedPayload:
    reason: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.reason, "payload.reason")

    def to_json_obj(self) -> dict[str, Any]:
        return {"reason": self.reason}


@dataclass(frozen=True)
class TimelineDeletedPayload:
    def to_json_obj(self) -> dict[str, Any]:
        return {}


@dataclass(frozen=True)
class TimelineConfigReplacedPayload:
    config: dict[str, Any]
    source: str | None = None

    def __post_init__(self) -> None:
        if self.source is not None:
            _require_nonempty_str(self.source, "payload.source")
        try:
            config = validate_timeline_config_for_container(self.config)
        except Exception as exc:
            raise TimelineEventSchemaError(str(exc)) from exc
        object.__setattr__(self, "config", config)
        if self.source is not None:
            _require_nonempty_str(self.source, "payload.source")

    def to_json_obj(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"config": deepcopy(self.config)}
        if self.source is not None:
            payload["source"] = self.source
        return payload


@dataclass(frozen=True)
class TimelineAssetRegistryReplacedPayload:
    registry: dict[str, Any]
    source: str | None = None

    def __post_init__(self) -> None:
        _validate_jsonable(self.registry, "payload.registry")
        if self.source is not None:
            _require_nonempty_str(self.source, "payload.source")

    def to_json_obj(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"registry": deepcopy(self.registry)}
        if self.source is not None:
            payload["source"] = self.source
        return payload
