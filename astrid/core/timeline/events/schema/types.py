"""Canonical timeline event envelope and lifecycle payloads."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from astrid.core.contracts.schema_validators import require_uuid_str
from astrid.core.timeline.kinds import (
    normalize_event_clip_kind,
    normalize_track_kind,
    normalize_transition_kind,
)
from astrid.core.timeline.banodoco_schema import validate_timeline_config_for_container

from .ulid import generate_event_ulid, is_event_ulid

EVENT_SCHEMA_VERSION = 2

ActorType = Literal["agent", "human", "system"]
TimelineEventKind = Literal[
    "timeline.created",
    "timeline.renamed",
    "timeline.default_set",
    "timeline.tombstoned",
    "timeline.deleted",
    "timeline.imported",
    "timeline.config_replaced",
    "timeline.recovered",
    "timeline.reverted",
    "timeline.branched_from",
    "timeline.erased",
    "clip.added",
    "clip.removed",
    "clip.moved",
    "clip.retracked",
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
# Event-level clip classification.  Mirrors a subset of the built-in clip
# catalog (catalog=\"clip\") in ``astrid.core.pack``; the catalog also carries
# \"video\", \"image\", \"effect\", and \"opaque\" which are element-kind
# descriptors rather than event-payload clip kinds.
ClipKind = Literal["visual", "audio", "text"]
# Canonical event-schema TrackKind; mirrors
# ``astrid.core.timeline.banodoco_schema.TrackKind`` and
# the public ``astrid.core.timeline.TrackKind`` export, plus
# the built-in track catalog (catalog="track") in ``astrid.core.pack``.
# This definition is intentionally duplicated rather than imported from the
# schema-model module: keeping event-payload schemas decoupled from the
# Banodoco-schema implementation avoids import-time coupling between the two
# layers. Do not consolidate into a shared kinds module.
TrackKind = Literal["visual", "audio"]


class TimelineEventSchemaError(ValueError):
    """Raised when timeline event schema validation fails."""


def _require_uuid_str(value: object, field: str) -> str:
    return require_uuid_str(value, field, TimelineEventSchemaError)


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
    track_id: str
    position: ClipPosition | dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        object.__setattr__(
            self,
            "kind",
            normalize_event_clip_kind(self.kind, error_cls=TimelineEventSchemaError),
        )
        _require_nonempty_str(self.track_id, "payload.track_id")
        _require_nonempty_str(self.asset_id, "payload.asset_id")
        coerced = _coerce_clip_position(self.position, "payload.position")
        if coerced is not self.position:
            object.__setattr__(self, "position", coerced)

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "clip_id": self.clip_id,
            "kind": self.kind,
            "track_id": self.track_id,
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
class ClipRetrackedPayload:
    clip_id: str
    track_id: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.clip_id, "payload.clip_id")
        _require_nonempty_str(self.track_id, "payload.track_id")

    def to_json_obj(self) -> dict[str, Any]:
        return {"clip_id": self.clip_id, "track_id": self.track_id}


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
    label: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.track_id, "payload.track_id")
        object.__setattr__(
            self,
            "kind",
            normalize_track_kind(self.kind, error_cls=TimelineEventSchemaError),
        )
        _require_nonempty_str(self.label, "payload.label")

    def to_json_obj(self) -> dict[str, Any]:
        return {"track_id": self.track_id, "kind": self.kind, "label": self.label}


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


# ---------------------------------------------------------------------------
# recovery / lifecycle / erasure payload models
# ---------------------------------------------------------------------------

_ERASED_PAYLOAD_FIELDS = frozenset({"erased", "reason", "erased_at", "erased_by", "policy_ref"})


@dataclass(frozen=True)
class ErasedPayload:
    """Canonical erased envelope for any event kind whose payload has been erased.

    This replaces the original domain payload of affected historical events.
    It is accepted by ``TimelineEvent.from_dict()`` for **any** event kind
    before per-kind coercion runs.
    """

    erased: Literal[True]
    reason: str
    erased_at: str
    erased_by: str
    policy_ref: str | None = None

    def __post_init__(self) -> None:
        if self.erased is not True:
            raise TimelineEventSchemaError("erased must be True")
        _require_nonempty_str(self.reason, "payload.reason")
        _require_nonempty_str(self.erased_at, "payload.erased_at")
        _require_nonempty_str(self.erased_by, "payload.erased_by")
        if self.policy_ref is not None:
            _require_nonempty_str(self.policy_ref, "payload.policy_ref")

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "erased": True,
            "reason": self.reason,
            "erased_at": self.erased_at,
            "erased_by": self.erased_by,
        }
        if self.policy_ref is not None:
            result["policy_ref"] = self.policy_ref
        return result


@dataclass(frozen=True)
class TimelineRecoveredPayload:
    anchor_event_id: str
    anchor_type: Literal["event", "snapshot"]
    reason: str
    projected_state_summary: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_nonempty_str(self.anchor_event_id, "payload.anchor_event_id")
        if self.anchor_type not in {"event", "snapshot"}:
            raise TimelineEventSchemaError("payload.anchor_type must be 'event' or 'snapshot'")
        _require_nonempty_str(self.reason, "payload.reason")
        if self.projected_state_summary is not None:
            try:
                projected_state_summary = validate_timeline_config_for_container(
                    self.projected_state_summary
                )
            except Exception as exc:
                raise TimelineEventSchemaError(str(exc)) from exc
            object.__setattr__(self, "projected_state_summary", projected_state_summary)

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "anchor_event_id": self.anchor_event_id,
            "anchor_type": self.anchor_type,
            "reason": self.reason,
        }
        if self.projected_state_summary is not None:
            result["projected_state_summary"] = deepcopy(self.projected_state_summary)
        return result


@dataclass(frozen=True)
class TimelineRevertedPayload:
    target_event_id: str
    reason: str
    before_projection: dict[str, Any] | None = None
    after_projection: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_nonempty_str(self.target_event_id, "payload.target_event_id")
        _require_nonempty_str(self.reason, "payload.reason")
        if self.before_projection is not None:
            _validate_jsonable(self.before_projection, "payload.before_projection")
        if self.after_projection is not None:
            _validate_jsonable(self.after_projection, "payload.after_projection")

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "target_event_id": self.target_event_id,
            "reason": self.reason,
        }
        if self.before_projection is not None:
            result["before_projection"] = dict(self.before_projection)
        if self.after_projection is not None:
            result["after_projection"] = dict(self.after_projection)
        return result


@dataclass(frozen=True)
class TimelineBranchedFromPayload:
    branch_timeline_id: str
    anchor_event_id: str
    reason: str | None = None

    def __post_init__(self) -> None:
        _require_uuid_str(self.branch_timeline_id, "payload.branch_timeline_id")
        _require_nonempty_str(self.anchor_event_id, "payload.anchor_event_id")
        if self.reason is not None:
            _require_nonempty_str(self.reason, "payload.reason")

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "branch_timeline_id": self.branch_timeline_id,
            "anchor_event_id": self.anchor_event_id,
        }
        if self.reason is not None:
            result["reason"] = self.reason
        return result


@dataclass(frozen=True)
class TimelineErasedPayload:
    """Audit/control event payload for ``timeline.erased``.

    This is the control event that describes the erasure operation,
    not the erased envelope that replaces affected historical payloads.
    """

    selector_summary: dict[str, Any]
    reason: str
    affected_count: int
    policy_ref: str | None = None
    affected_event_ids: list[str] | None = None

    def __post_init__(self) -> None:
        _validate_jsonable(self.selector_summary, "payload.selector_summary")
        _require_nonempty_str(self.reason, "payload.reason")
        if not isinstance(self.affected_count, int) or isinstance(self.affected_count, bool):
            raise TimelineEventSchemaError("payload.affected_count must be an integer")
        if self.affected_count < 0:
            raise TimelineEventSchemaError("payload.affected_count must be >= 0")
        if self.policy_ref is not None:
            _require_nonempty_str(self.policy_ref, "payload.policy_ref")
        if self.affected_event_ids is not None:
            if not isinstance(self.affected_event_ids, list):
                raise TimelineEventSchemaError("payload.affected_event_ids must be a list when present")
            for idx, eid in enumerate(self.affected_event_ids):
                _require_nonempty_str(eid, f"payload.affected_event_ids[{idx}]")

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "selector_summary": dict(self.selector_summary),
            "reason": self.reason,
            "affected_count": self.affected_count,
        }
        if self.policy_ref is not None:
            result["policy_ref"] = self.policy_ref
        if self.affected_event_ids is not None:
            result["affected_event_ids"] = list(self.affected_event_ids)
        return result


PayloadModel = (
    TimelineCreatedPayload
    | TimelineRenamedPayload
    | TimelineDefaultSetPayload
    | TimelineTombstonedPayload
    | TimelineDeletedPayload
    | TimelineImportedPayload
    | TimelineConfigReplacedPayload
    | TimelineRecoveredPayload
    | TimelineRevertedPayload
    | TimelineBranchedFromPayload
    | TimelineErasedPayload
    | ErasedPayload
    | ClipAddedPayload
    | ClipRemovedPayload
    | ClipMovedPayload
    | ClipRetrackedPayload
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
    "timeline.config_replaced": TimelineConfigReplacedPayload,
    "timeline.recovered": TimelineRecoveredPayload,
    "timeline.reverted": TimelineRevertedPayload,
    "timeline.branched_from": TimelineBranchedFromPayload,
    "timeline.erased": TimelineErasedPayload,
    "clip.added": ClipAddedPayload,
    "clip.removed": ClipRemovedPayload,
    "clip.moved": ClipMovedPayload,
    "clip.retracked": ClipRetrackedPayload,
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


def _is_erased_payload_dict(payload: object) -> bool:
    """Return True when *payload* is a dict whose ``erased`` key is truthy."""
    return isinstance(payload, dict) and bool(payload.get("erased"))


def _has_mixed_erased_and_domain_fields(payload: dict[str, Any]) -> bool:
    """Return True when *payload* mixes erased-envelope keys with domain-specific keys."""
    erased_keys = _ERASED_PAYLOAD_FIELDS
    extra_keys = set(payload.keys()) - erased_keys
    return len(extra_keys) > 0


def coerce_payload(kind: str, payload: PayloadModel | dict[str, Any]) -> PayloadModel:
    # ------------------------------------------------------------------
    # Erased payload envelope: accepted for ANY event kind (including
    # timeline.erased itself) BEFORE per-kind coercion.
    # ------------------------------------------------------------------
    if isinstance(payload, ErasedPayload):
        return payload
    if _is_erased_payload_dict(payload):
        assert isinstance(payload, dict)
        if _has_mixed_erased_and_domain_fields(payload):
            raise TimelineEventSchemaError(
                "erased payload must not include domain-specific fields; "
                "only erased, reason, erased_at, erased_by, and optional policy_ref are allowed"
            )
        return ErasedPayload(
            erased=True,
            reason=payload["reason"],
            erased_at=payload["erased_at"],
            erased_by=payload["erased_by"],
            policy_ref=payload.get("policy_ref"),
        )

    # Normal per-kind coercion
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
    # --- import metadata (cross-backend transfer provenance) ---
    source_backend: str | None = None
    source_timeline_id: str | None = None
    source_event_id: str | None = None
    source_version: int | None = None
    source_hash: str | None = None

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
        if self.kind not in _PAYLOAD_TYPES and not isinstance(self.payload, ErasedPayload):
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
        # Validate import metadata fields when present
        if self.source_backend is not None:
            _require_nonempty_str(self.source_backend, "source_backend")
        if self.source_timeline_id is not None:
            _require_uuid_str(self.source_timeline_id, "source_timeline_id")
        if self.source_event_id is not None:
            _require_nonempty_str(self.source_event_id, "source_event_id")
        if self.source_version is not None:
            if not isinstance(self.source_version, int) or isinstance(self.source_version, bool):
                raise TimelineEventSchemaError("source_version must be an integer when present")
        if self.source_hash is not None:
            _require_nonempty_str(self.source_hash, "source_hash")

    def to_json_obj(self) -> dict[str, Any]:
        result: dict[str, Any] = {
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
        if self.source_backend is not None:
            result["source_backend"] = self.source_backend
        if self.source_timeline_id is not None:
            result["source_timeline_id"] = self.source_timeline_id
        if self.source_event_id is not None:
            result["source_event_id"] = self.source_event_id
        if self.source_version is not None:
            result["source_version"] = self.source_version
        if self.source_hash is not None:
            result["source_hash"] = self.source_hash
        return result

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
        source_backend: str | None = None,
        source_timeline_id: str | None = None,
        source_event_id: str | None = None,
        source_version: int | None = None,
        source_hash: str | None = None,
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
            source_backend=source_backend,
            source_timeline_id=source_timeline_id,
            source_event_id=source_event_id,
            source_version=source_version,
            source_hash=source_hash,
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
            source_backend=raw.get("source_backend"),  # type: ignore[arg-type]
            source_timeline_id=raw.get("source_timeline_id"),  # type: ignore[arg-type]
            source_event_id=raw.get("source_event_id"),  # type: ignore[arg-type]
            source_version=raw.get("source_version"),  # type: ignore[arg-type]
            source_hash=raw.get("source_hash"),  # type: ignore[arg-type]
        )
