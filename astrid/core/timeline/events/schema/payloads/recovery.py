"""recovery / lifecycle / erasure payload models."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from astrid.core.timeline.banodoco_schema import validate_timeline_config_for_container

from ._base import (
    TimelineEventSchemaError,
    _require_nonempty_str,
    _require_uuid_str,
    _validate_jsonable,
)


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
