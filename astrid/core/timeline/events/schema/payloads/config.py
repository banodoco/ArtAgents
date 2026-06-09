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
class TimelineImportedPayload:
    snapshot: dict[str, Any]
    source: TimelineImportSource

    def __post_init__(self) -> None:
        if self.source not in {"legacy_local", "supabase_config", "other"}:
            raise TimelineEventSchemaError(
                "payload.source must be legacy_local, supabase_config, or other"
            )
        _validate_jsonable(self.snapshot, "payload.snapshot")

    def to_json_obj(self) -> dict[str, Any]:
        return {"snapshot": dict(self.snapshot), "source": self.source}


@dataclass(frozen=True)
class TimelineConfigReplacedPayload:
    config: dict[str, Any]

    def __post_init__(self) -> None:
        try:
            config = validate_timeline_config_for_container(self.config)
        except Exception as exc:
            raise TimelineEventSchemaError(str(exc)) from exc
        object.__setattr__(self, "config", config)

    def to_json_obj(self) -> dict[str, Any]:
        return {"config": deepcopy(self.config)}
