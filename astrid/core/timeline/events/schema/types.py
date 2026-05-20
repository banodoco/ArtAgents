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
]
TimelineImportSource = Literal["legacy_local", "supabase_config", "other"]


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


PayloadModel = (
    TimelineCreatedPayload
    | TimelineRenamedPayload
    | TimelineDefaultSetPayload
    | TimelineTombstonedPayload
    | TimelineDeletedPayload
    | TimelineImportedPayload
)


_PAYLOAD_TYPES: dict[str, type[PayloadModel]] = {
    "timeline.created": TimelineCreatedPayload,
    "timeline.renamed": TimelineRenamedPayload,
    "timeline.default_set": TimelineDefaultSetPayload,
    "timeline.tombstoned": TimelineTombstonedPayload,
    "timeline.deleted": TimelineDeletedPayload,
    "timeline.imported": TimelineImportedPayload,
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
