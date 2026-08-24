"""Pure, checked transition rules for Reigh child orchestration.

The bridge owns persistence and fencing; this module owns only the three
deterministic coordinator primitives: child identity, child planning, and
admission arbitration. Keeping these rules pure makes crash/retry schedules
reproducible and gives the HTTP adapter one total, fail-closed decision table.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Mapping

__all__ = [
    "ADMISSION_TRANSITIONS",
    "FenceFacts",
    "KEY_PREFIX",
    "OrchestratorPlanError",
    "Verdict",
    "classify_admission",
    "derive_children",
    "orch_child_key",
]

KEY_PREFIX = "reigh.orch:v1"


class OrchestratorPlanError(ValueError):
    """A parent spec has no deterministic child plan."""


def orch_child_key(parent_task_id: str, role: str, index: int) -> str:
    """Return attempt-independent identity for one planned child slot."""
    return f"{KEY_PREFIX}:{parent_task_id}:{role}:{index}"


_SEGMENT_ROLE = "segment"
_STITCH_ROLE = "stitch"


def _segments_plus_stitch(items: Any) -> tuple[tuple[str, int], ...]:
    if not isinstance(items, (list, tuple)):
        raise OrchestratorPlanError("parent spec params carry no countable child workload")
    return tuple([(_SEGMENT_ROLE, index) for index in range(len(items))] + [(_STITCH_ROLE, 0)])


def derive_children(parent_spec: Mapping[str, Any]) -> tuple[tuple[str, int], ...]:
    """Purely derive the planned child slots for an admitted parent."""
    family = parent_spec.get("family")
    params = parent_spec.get("params")
    params = params if isinstance(params, Mapping) else {}
    if family == "join_clips":
        return _segments_plus_stitch(params.get("clips"))
    if family == "travel_between_images":
        return _segments_plus_stitch(params.get("image_urls"))
    if family == "edit_video_orchestrator":
        return ()
    raise OrchestratorPlanError(
        f"family {family!r} has no child plan rule; declare a plan or "
        "explicitly mark the family childless"
    )


class Verdict(enum.Enum):
    ADMIT_NEW = "admit_new"
    REPLAY_RECEIPTED = "replay_receipted"
    CONFLICT_PARENT_NOT_RUNNING = "conflict_parent_not_running"
    CONFLICT_LEASE_EXPIRED = "conflict_lease_expired"
    FORBIDDEN_FENCE_MISMATCH = "forbidden_fence_mismatch"


@dataclass(frozen=True)
class FenceFacts:
    already_receipted: bool
    parent_running: bool
    fence_valid: bool
    lease_unexpired: bool

    def key(self) -> tuple[bool, bool, bool, bool]:
        return (
            self.already_receipted,
            self.parent_running,
            self.fence_valid,
            self.lease_unexpired,
        )


def _build_table() -> dict[tuple[bool, bool, bool, bool], Verdict]:
    table: dict[tuple[bool, bool, bool, bool], Verdict] = {}
    # A committed deterministic key always replays, even if the caller's
    # current attempt fence is stale: identity is the key, not the attempt.
    for running in (True, False):
        for fence in (True, False):
            for lease in (True, False):
                table[(True, running, fence, lease)] = Verdict.REPLAY_RECEIPTED
    # Parent state wins over fence details.
    for fence in (True, False):
        for lease in (True, False):
            table[(False, False, fence, lease)] = Verdict.CONFLICT_PARENT_NOT_RUNNING
    for lease in (True, False):
        table[(False, True, False, lease)] = Verdict.FORBIDDEN_FENCE_MISMATCH
    table[(False, True, True, False)] = Verdict.CONFLICT_LEASE_EXPIRED
    table[(False, True, True, True)] = Verdict.ADMIT_NEW
    return table


ADMISSION_TRANSITIONS = _build_table()


def classify_admission(facts: FenceFacts) -> Verdict:
    """Classify all gate facts; unknown combinations fail closed."""
    return ADMISSION_TRANSITIONS.get(facts.key(), Verdict.FORBIDDEN_FENCE_MISMATCH)
