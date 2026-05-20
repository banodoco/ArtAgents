"""Canonical timeline event envelope and lifecycle payloads."""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from .version import EVENT_SCHEMA_VERSION

ActorType = Literal["agent", "human", "system"]
TimelineEventKind = Literal[
    "timeline.created",
    "timeline.renamed",
    "timeline.default_set",
    "timeline.tombstoned",
    "timeline.deleted",
    "timeline.imported",
    "clip.added",
    "clip.removed",
    "clip.moved",
    "clip.retimed",
    "clip.swapped",
    "clip.replaced",
    "clip.text_set",
    "clip.annotated",
    "transition.set",
    "transition.removed",
    "effect.added",
    "effect.removed",
    "effect.tuned",
    "theme.set",
    "theme.overridden",
    "track.added",
    "track.removed",
    "audio.bound",
    "audio.unbound",
    "pool.asset_added",
    "pool.asset_removed",
    "pool.asset_scored",
    "arrangement.replaced",
]
TimelineImportSource = Literal["legacy_local", "supabase_config", "other"]
ClipKind = Literal["visual", "audio", "text"]
TrackKind = Literal["visual", "audio"]


class TimelineEventSchemaError(ValueError):
    """Raised when timeline event schema validation fails."""


_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_RE = re.compile(r"^[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{26}$")
_ULID_RANDOM_BITS = 80
_ULID_RANDOM_MASK = (1 << _ULID_RANDOM_BITS) - 1
_ULID_LOCK = threading.Lock()
_ULID_LAST_MS = -1
_ULID_LAST_RANDOM = 0


def generate_event_ulid() -> str:
    global _ULID_LAST_MS, _ULID_LAST_RANDOM

    now_ms = int(time.time() * 1000)
    with _ULID_LOCK:
        if now_ms > _ULID_LAST_MS:
            _ULID_LAST_MS = now_ms
            _ULID_LAST_RANDOM = int.from_bytes(os.urandom(10), "big")
        else:
            _ULID_LAST_RANDOM = (_ULID_LAST_RANDOM + 1) & _ULID_RANDOM_MASK
            if _ULID_LAST_RANDOM == 0:
                while now_ms <= _ULID_LAST_MS:
                    time.sleep(0.001)
                    now_ms = int(time.time() * 1000)
                _ULID_LAST_MS = now_ms
                _ULID_LAST_RANDOM = int.from_bytes(os.urandom(10), "big")
        value = (_ULID_LAST_MS << _ULID_RANDOM_BITS) | _ULID_LAST_RANDOM
    chars = ["0"] * 26
    for index in range(25, -1, -1):
        chars[index] = _CROCKFORD_ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(chars)


def is_event_ulid(value: object) -> bool:
    return isinstance(value, str) and _ULID_RE.fullmatch(value) is not None


def _require_uuid_str(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise TimelineEventSchemaError(f"{field} must be a UUID string")
    try:
        UUID(value)
    except ValueError as exc:
        raise TimelineEventSchemaError(f"{field} must be a UUID string") from exc
    return value


def _require_ulid_str(value: object, field: str) -> str:
    if not is_event_ulid(value):
        raise TimelineEventSchemaError(f"{field} must be a 26-character Crockford ULID")
    return str(value)


def _require_nonempty_str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TimelineEventSchemaError(f"{field} must be a non-empty string")
    return value


def _validate_jsonable(value: Any, field: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise TimelineEventSchemaError(f"{field} keys must be strings")
            _validate_jsonable(nested, f"{field}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_jsonable(nested, f"{field}[{index}]")
        return
    raise TimelineEventSchemaError(f"{field} must be JSON-serializable")


def _coerce_clip_position(value: object, field: str) -> "ClipPosition | None":
    if value is None:
        return None
    if isinstance(value, ClipPosition):
        return value
    if isinstance(value, dict):
        return ClipPosition.from_dict(value)
    raise TimelineEventSchemaError(f"{field} must be a ClipPosition or dict")


@dataclass(frozen=True)
class ClipPosition:
    """Normalized clip position within a timeline.

    clip 'id' strings are the canonical m2 identity.
    Migration to UUID entity_id/external_id is deferred to a later milestone.
    """

    mode: Literal["index", "after", "before"]
    index: int | None = None
    ref_clip_id: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"index", "after", "before"}:
            raise TimelineEventSchemaError(
                "position.mode must be 'index', 'after', or 'before'"
            )
        if self.mode == "index":
            if self.index is None:
                raise TimelineEventSchemaError(
                    "position.index is required when mode is 'index'"
                )
            if not isinstance(self.index, int) or isinstance(self.index, bool):
                raise TimelineEventSchemaError("position.index must be an integer")
        else:
            if self.ref_clip_id is None:
                raise TimelineEventSchemaError(
                    "position.ref_clip_id is required when mode is 'after' or 'before'"
                )
            _require_nonempty_str(self.ref_clip_id, "position.ref_clip_id")
        if self.index is not None and self.mode != "index":
            object.__setattr__(self, "index", None)

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {"mode": self.mode}
        if self.index is not None:
            result["index"] = self.index
        if self.ref_clip_id is not None:
            result["ref_clip_id"] = self.ref_clip_id
        return result

    @classmethod
    def from_dict(cls, raw: object) -> "ClipPosition":
        if not isinstance(raw, dict):
            raise TimelineEventSchemaError("position must be an object")
        return cls(
            mode=raw.get("mode"),
            index=raw.get("index"),
            ref_clip_id=raw.get("ref_clip_id"),
        )


@dataclass(frozen=True)
class TimelineActor:
    type: ActorType
    id: str
    display: str | None = None
    via: list["TimelineActor"] | None = None

    def __post_init__(self) -> None:
        if self.type not in {"agent", "human", "system"}:
            raise TimelineEventSchemaError("actor.type must be one of agent, human, system")
        _require_nonempty_str(self.id, "actor.id")
        if self.display is not None:
            _require_nonempty_str(self.display, "actor.display")
        if self.via is not None:
            if not isinstance(self.via, list):
                raise TimelineEventSchemaError("actor.via must be a list when present")
            for index, actor in enumerate(self.via):
                if not isinstance(actor, TimelineActor):
                    raise TimelineEventSchemaError(
                        f"actor.via[{index}] must be a TimelineActor"
                    )

    def to_json_obj(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": self.type, "id": self.id}
        if self.display is not None:
            payload["display"] = self.display
        if self.via is not None:
            payload["via"] = [actor.to_json_obj() for actor in self.via]
        return payload

    @classmethod
    def from_dict(cls, raw: object) -> "TimelineActor":
        if not isinstance(raw, dict):
            raise TimelineEventSchemaError("actor must be an object")
        via = raw.get("via")
        nested = None if via is None else [cls.from_dict(item) for item in via]
        return cls(
            type=raw.get("type"),  # type: ignore[arg-type]
            id=raw.get("id"),  # type: ignore[arg-type]
            display=raw.get("display"),  # type: ignore[arg-type]
            via=nested,
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


# ---------------------------------------------------------------------------
# clip.* payload models
#
# clip 'id' strings are the canonical m2 identity.
# Migration to UUID entity_id/external_id is deferred to a later milestone.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClipAddedPayload:
    clip_id: str
    kind: ClipKind
    asset_id: str
    position: ClipPosition | dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        if self.kind not in {"visual", "audio", "text"}:
            raise TimelineEventSchemaError(
                "payload.kind must be 'visual', 'audio', or 'text'"
            )
        _require_nonempty_str(self.asset_id, "payload.asset_id")
        coerced = _coerce_clip_position(self.position, "payload.position")
        if coerced is not self.position:
            object.__setattr__(self, "position", coerced)

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "clip_id": self.clip_id,
            "kind": self.kind,
            "asset_id": self.asset_id,
        }
        if self.position is not None:
            result["position"] = self.position.to_json_obj()
        return result


@dataclass(frozen=True)
class ClipRemovedPayload:
    clip_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id}


@dataclass(frozen=True)
class ClipMovedPayload:
    clip_id: str
    position: ClipPosition | dict[str, Any]

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        coerced = _coerce_clip_position(self.position, "payload.position")
        if coerced is None:
            raise TimelineEventSchemaError("payload.position is required for clip.moved")
        if coerced is not self.position:
            object.__setattr__(self, "position", coerced)

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "position": self.position.to_json_obj(),
        }


@dataclass(frozen=True)
class ClipRetimedPayload:
    clip_id: str
    start: float
    duration: float

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        if not isinstance(self.start, (int, float)) or isinstance(self.start, bool):
            raise TimelineEventSchemaError("payload.start must be a number")
        if self.start < 0:
            raise TimelineEventSchemaError("payload.start must be >= 0")
        object.__setattr__(self, "start", float(self.start))
        if not isinstance(self.duration, (int, float)) or isinstance(self.duration, bool):
            raise TimelineEventSchemaError("payload.duration must be a number")
        if self.duration <= 0:
            raise TimelineEventSchemaError("payload.duration must be > 0")
        object.__setattr__(self, "duration", float(self.duration))

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "start": self.start,
            "duration": self.duration,
        }


@dataclass(frozen=True)
class ClipSwappedPayload:
    clip_a_id: str
    clip_b_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_a_id, "payload.clip_a_id")
        _require_nonempty_str(self.clip_b_id, "payload.clip_b_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_a_id": self.clip_a_id, "clip_b_id": self.clip_b_id}


@dataclass(frozen=True)
class ClipReplacedPayload:
    clip_id: str
    with_asset_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        _require_nonempty_str(self.with_asset_id, "payload.with_asset_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id, "with_asset_id": self.with_asset_id}


@dataclass(frozen=True)
class ClipTextSetPayload:
    clip_id: str
    text: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        if not isinstance(self.text, str):
            raise TimelineEventSchemaError("payload.text must be a string")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id, "text": self.text}


@dataclass(frozen=True)
class ClipAnnotatedPayload:
    clip_id: str
    note: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        if not isinstance(self.note, str):
            raise TimelineEventSchemaError("payload.note must be a string")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id, "note": self.note}


# ---------------------------------------------------------------------------
# transition.* payload models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransitionSetPayload:
    left_clip_id: str
    right_clip_id: str
    kind: str
    duration_seconds: float

    def __post_init__(self) -> None:
        _require_nonempty_str(self.left_clip_id, "payload.left_clip_id")
        _require_nonempty_str(self.right_clip_id, "payload.right_clip_id")
        _require_nonempty_str(self.kind, "payload.kind")
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


# ---------------------------------------------------------------------------
# effect.* payload models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# theme.* payload models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# track.* payload models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrackAddedPayload:
    track_id: str
    kind: TrackKind
    label: str | None = None

    def __post_init__(self) -> None:
        _require_nonempty_str(self.track_id, "payload.track_id")
        if self.kind not in {"visual", "audio"}:
            raise TimelineEventSchemaError("payload.kind must be 'visual' or 'audio'")
        if self.label is not None:
            _require_nonempty_str(self.label, "payload.label")

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {"track_id": self.track_id, "kind": self.kind}
        if self.label is not None:
            result["label"] = self.label
        return result


@dataclass(frozen=True)
class TrackRemovedPayload:
    track_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.track_id, "payload.track_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"track_id": self.track_id}


# ---------------------------------------------------------------------------
# audio.* payload models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# pool.* payload models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# arrangement.* payload models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArrangementReplacedPayload:
    arrangement: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.arrangement, dict):
            raise TimelineEventSchemaError("payload.arrangement must be an object")
        _validate_jsonable(self.arrangement, "payload.arrangement")

    def to_json_obj(self) -> dict[str, Any]:
        return {"arrangement": dict(self.arrangement)}


PayloadModel = (
    TimelineCreatedPayload
    | TimelineRenamedPayload
    | TimelineDefaultSetPayload
    | TimelineTombstonedPayload
    | TimelineDeletedPayload
    | TimelineImportedPayload
    | ClipAddedPayload
    | ClipRemovedPayload
    | ClipMovedPayload
    | ClipRetimedPayload
    | ClipSwappedPayload
    | ClipReplacedPayload
    | ClipTextSetPayload
    | ClipAnnotatedPayload
    | TransitionSetPayload
    | TransitionRemovedPayload
    | EffectAddedPayload
    | EffectRemovedPayload
    | EffectTunedPayload
    | ThemeSetPayload
    | ThemeOverriddenPayload
    | TrackAddedPayload
    | TrackRemovedPayload
    | AudioBoundPayload
    | AudioUnboundPayload
    | PoolAssetAddedPayload
    | PoolAssetRemovedPayload
    | PoolAssetScoredPayload
    | ArrangementReplacedPayload
)


_PAYLOAD_TYPES: dict[str, type[PayloadModel]] = {
    "timeline.created": TimelineCreatedPayload,
    "timeline.renamed": TimelineRenamedPayload,
    "timeline.default_set": TimelineDefaultSetPayload,
    "timeline.tombstoned": TimelineTombstonedPayload,
    "timeline.deleted": TimelineDeletedPayload,
    "timeline.imported": TimelineImportedPayload,
    "clip.added": ClipAddedPayload,
    "clip.removed": ClipRemovedPayload,
    "clip.moved": ClipMovedPayload,
    "clip.retimed": ClipRetimedPayload,
    "clip.swapped": ClipSwappedPayload,
    "clip.replaced": ClipReplacedPayload,
    "clip.text_set": ClipTextSetPayload,
    "clip.annotated": ClipAnnotatedPayload,
    "transition.set": TransitionSetPayload,
    "transition.removed": TransitionRemovedPayload,
    "effect.added": EffectAddedPayload,
    "effect.removed": EffectRemovedPayload,
    "effect.tuned": EffectTunedPayload,
    "theme.set": ThemeSetPayload,
    "theme.overridden": ThemeOverriddenPayload,
    "track.added": TrackAddedPayload,
    "track.removed": TrackRemovedPayload,
    "audio.bound": AudioBoundPayload,
    "audio.unbound": AudioUnboundPayload,
    "pool.asset_added": PoolAssetAddedPayload,
    "pool.asset_removed": PoolAssetRemovedPayload,
    "pool.asset_scored": PoolAssetScoredPayload,
    "arrangement.replaced": ArrangementReplacedPayload,
}


def payload_to_json_obj(payload: PayloadModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        _validate_jsonable(payload, "payload")
        return dict(payload)
    return payload.to_json_obj()


def coerce_payload(kind: str, payload: PayloadModel | dict[str, Any]) -> PayloadModel:
    model_type = _PAYLOAD_TYPES.get(kind)
    if model_type is None:
        raise TimelineEventSchemaError(f"unsupported event kind: {kind}")
    if isinstance(payload, model_type):
        return payload
    if not isinstance(payload, dict):
        raise TimelineEventSchemaError("payload must be an object")
    if model_type is TimelineDeletedPayload:
        if payload:
            raise TimelineEventSchemaError("timeline.deleted payload must be an empty object")
        return TimelineDeletedPayload()
    return model_type(**payload)


@dataclass(frozen=True)
class TimelineEvent:
    event_id: str
    timeline_id: str
    ts: str
    actor: TimelineActor
    prev_hash: str | None
    hash: str | None
    kind: TimelineEventKind
    payload: PayloadModel | dict[str, Any]
    expected_version: int | None = None
    schema_version: int = EVENT_SCHEMA_VERSION
    txn_id: str | None = None

    def __post_init__(self) -> None:
        _require_ulid_str(self.event_id, "event_id")
        _require_uuid_str(self.timeline_id, "timeline_id")
        _require_nonempty_str(self.ts, "ts")
        if not isinstance(self.actor, TimelineActor):
            raise TimelineEventSchemaError("actor must be a TimelineActor")
        if self.prev_hash is not None:
            _require_nonempty_str(self.prev_hash, "prev_hash")
        if self.hash is not None:
            _require_nonempty_str(self.hash, "hash")
        if self.kind not in _PAYLOAD_TYPES:
            raise TimelineEventSchemaError(f"unsupported event kind: {self.kind}")
        object.__setattr__(self, "payload", coerce_payload(self.kind, self.payload))
        if self.expected_version is not None and (
            not isinstance(self.expected_version, int) or isinstance(self.expected_version, bool)
        ):
            raise TimelineEventSchemaError("expected_version must be an integer when present")
        if self.schema_version != EVENT_SCHEMA_VERSION:
            raise TimelineEventSchemaError(
                f"schema_version must be {EVENT_SCHEMA_VERSION}"
            )
        if self.txn_id is not None:
            _require_ulid_str(self.txn_id, "txn_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timeline_id": self.timeline_id,
            "ts": self.ts,
            "actor": self.actor.to_json_obj(),
            "prev_hash": self.prev_hash,
            "hash": self.hash,
            "kind": self.kind,
            "payload": payload_to_json_obj(self.payload),
            "expected_version": self.expected_version,
            "schema_version": self.schema_version,
            "txn_id": self.txn_id,
        }

    @classmethod
    def new(
        cls,
        *,
        timeline_id: str,
        ts: str,
        actor: TimelineActor,
        kind: TimelineEventKind,
        payload: PayloadModel | dict[str, Any],
        prev_hash: str | None = None,
        expected_version: int | None = None,
        txn_id: str | None = None,
    ) -> "TimelineEvent":
        return cls(
            event_id=generate_event_ulid(),
            timeline_id=timeline_id,
            ts=ts,
            actor=actor,
            prev_hash=prev_hash,
            hash=None,
            kind=kind,
            payload=payload,
            expected_version=expected_version,
            txn_id=txn_id,
        )

    @classmethod
    def from_dict(cls, raw: object) -> "TimelineEvent":
        if not isinstance(raw, dict):
            raise TimelineEventSchemaError("event must be an object")
        return cls(
            event_id=raw.get("event_id"),  # type: ignore[arg-type]
            timeline_id=raw.get("timeline_id"),  # type: ignore[arg-type]
            ts=raw.get("ts"),  # type: ignore[arg-type]
            actor=TimelineActor.from_dict(raw.get("actor")),
            prev_hash=raw.get("prev_hash"),  # type: ignore[arg-type]
            hash=raw.get("hash"),  # type: ignore[arg-type]
            kind=raw.get("kind"),  # type: ignore[arg-type]
            payload=raw.get("payload"),  # type: ignore[arg-type]
            expected_version=raw.get("expected_version"),  # type: ignore[arg-type]
            schema_version=raw.get("schema_version", EVENT_SCHEMA_VERSION),  # type: ignore[arg-type]
            txn_id=raw.get("txn_id"),  # type: ignore[arg-type]
        )
