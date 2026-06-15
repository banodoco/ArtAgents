"""timeline.asset_registry_replaced payload model."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ._base import TimelineEventSchemaError, _require_nonempty_str, _validate_jsonable


@dataclass(frozen=True)
class AssetRegistryReplacedPayload:
    """Payload for ``timeline.asset_registry_replaced`` events.

    Carries the full projected asset registry (a JSON-able dict mapping
    asset IDs to their metadata) and an optional source provenance marker.
    The registry is validated for JSON-serialisability but is intentionally
    not validated against the Banodoco container schema — asset registries
    are a non-container read model that lives alongside (not inside) the
    projected TimelineConfig assembly.
    """

    registry: dict[str, Any]
    source: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.registry, dict):
            raise TimelineEventSchemaError("payload.registry must be an object")
        _validate_jsonable(self.registry, "payload.registry")
        if self.source is not None:
            _require_nonempty_str(self.source, "payload.source")

    def to_json_obj(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"registry": deepcopy(self.registry)}
        if self.source is not None:
            payload["source"] = self.source
        return payload
