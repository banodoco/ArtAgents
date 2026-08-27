"""Checked orchestrator transition table (doc 27 §3.5, plan task 7).

The single authority for the three orchestration primitives B6's runner
and B5's interleaving suite share:

1. **Child identity** — :func:`orch_child_key` derives the deterministic,
   attempt-independent idempotency key. It is the ONLY place in the code
   base where the ``reigh.orch:v1`` key space is spelled (lint-enforced by
   ``tests/v10/test_orchestrator_interleaving.py``); no orchestration key
   ever embeds an attempt number, so parent retry N+1 resolves to the
   same child rows.

2. **Child planning** — :func:`derive_children` derives the planned
   ``(role, index)`` set from an admitted parent spec. It is pure: no
   RNG, no clock, no filesystem, no network — the same spec always
   yields the same plan, which is what makes "child set == planned set"
   checkable after any crash/retry interleaving.

3. **Admission arbitration** — :data:`ADMISSION_TRANSITIONS` is the
   checked transition table over ``(receipted, parent_running,
   fence_valid, lease_unexpired)`` x child state. ``admit_child``
   consults nothing else: every reachable combination is an explicit
   row, the lookup is total over the fact space, and an unlisted
   combination fails closed to :attr:`Verdict.FORBIDDEN_FENCE_MISMATCH`.
   The table's precedence encodes the coordinator's contract:

   - a receipted deterministic key replays (200, same row) WITHOUT
     re-paying the live fence — identity is the key, not the attempt;
   - a non-running parent is a typed 409 regardless of lease state;
   - a live parent with a mismatched fence is 403, never a silent admit;
   - a valid fence on an expired lease is a typed 409 (the sweeper will
     requeue; the reclaimed attempt replays or re-admits deterministically);
   - the only admission arrow is live parent + valid fence + live lease.

Failure semantics degrade to orphan-or-replay, never mixed state: a
crash between admissions leaves already-receipted children replayable
by key and unadmitted children uncreated — there is no third state.
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
"""The child-key namespace, owned exclusively by :func:`orch_child_key`."""


class OrchestratorPlanError(ValueError):
    """A parent spec has no derivable child plan (fail closed, never silent)."""


# ---------------------------------------------------------------------------
# 1. Child identity: the deterministic, attempt-independent key
# ---------------------------------------------------------------------------


def orch_child_key(parent_task_id: str, role: str, index: int) -> str:
    """Derive the deterministic child idempotency key.

    Pure and attempt-independent by construction: the parameter list has
    no attempt, lease, or time input, so parent retry N+1 — under a new
    attempt id, lease, or status_version — derives the identical key and
    resolves to the SAME child row.
    """
    return f"{KEY_PREFIX}:{parent_task_id}:{role}:{index}"


# ---------------------------------------------------------------------------
# 2. Child planning: pure derivation of the planned (role, index) set
# ---------------------------------------------------------------------------

_JOIN_CLIPS_PLAN = "join_clips"
_TRAVEL_PLAN = "travel_between_images"
_EDIT_PLAN = "edit_video_orchestrator"

_SEGMENT_ROLE = "segment"
_STITCH_ROLE = "stitch"


def _segments_plus_stitch(items: Any) -> tuple[tuple[str, int], ...]:
    if not isinstance(items, (list, tuple)):
        raise OrchestratorPlanError(
            "parent spec params carry no countable child workload"
        )
    return tuple(
        [(_SEGMENT_ROLE, i) for i in range(len(items))]
        + [(_STITCH_ROLE, 0)]
    )


_PLAN_RULES: dict[str, Any] = {
    # N clips -> N segment children + the final stitch (doc 16 §3).
    _JOIN_CLIPS_PLAN: lambda params: _segments_plus_stitch(
        params.get("clips")
    ),
    # N images -> N travel segments + the stitch (doc 16 §3.9).
    _TRAVEL_PLAN: lambda params: _segments_plus_stitch(
        params.get("image_urls")
    ),
    # Edit family is childless by contract (doc 27 §3.1 allowlist is
    # exhaustive and contains no edit_* child): the parent completes
    # explicitly without child admission.
    _EDIT_PLAN: lambda params: (),
}


def derive_children(parent_spec: Mapping[str, Any]) -> tuple[tuple[str, int], ...]:
    """Derive the planned ``(role, index)`` child set from a parent spec.

    Pure: reads only its argument — no RNG, clock, filesystem, or
    network — so the plan is stable across processes, retries, and
    crashes, and "child set == planned set" is a well-defined invariant.
    """
    family = parent_spec.get("family")
    if not isinstance(family, str) or not family:
        raise OrchestratorPlanError(
            "parent spec carries no family; cannot derive a child plan"
        )
    rule = _PLAN_RULES.get(family)
    if rule is None:
        raise OrchestratorPlanError(
            f"family {family!r} has no child plan rule; orchestrator "
            "families must declare one or be explicitly childless"
        )
    params = parent_spec.get("params")
    return rule(params if isinstance(params, Mapping) else {})


class Verdict(enum.Enum):
    """The five arbitration outcomes of :data:`ADMISSION_TRANSITIONS`."""

    ADMIT_NEW = "admit_new"
    REPLAY_RECEIPTED = "replay_receipted"
    CONFLICT_PARENT_NOT_RUNNING = "conflict_parent_not_running"
    CONFLICT_LEASE_EXPIRED = "conflict_lease_expired"
    FORBIDDEN_FENCE_MISMATCH = "forbidden_fence_mismatch"


@dataclass(frozen=True)
class FenceFacts:
    """The observable gate facts of one child-admission request.

    ``fence_valid`` folds the per-attempt checks (attempt exists, belongs
    to the parent, is live, and matches executor/lease/status_version);
    ``lease_unexpired`` is only meaningful when the fence is valid.
    """

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
    """The 16-row table, written out arrow by arrow (no derived rows)."""
    table: dict[tuple[bool, bool, bool, bool], Verdict] = {}
    # Receipted keys replay unconditionally: identity is the deterministic
    # key, never the caller's current fence (retry N+1 after a heartbeat).
    for running in (True, False):
        for fence in (True, False):
            for lease in (True, False):
                table[(True, running, fence, lease)] = Verdict.REPLAY_RECEIPTED
    # Not-running parent -> typed conflict, before any fence inspection.
    for fence in (True, False):
        for lease in (True, False):
            table[(False, False, fence, lease)] = (
                Verdict.CONFLICT_PARENT_NOT_RUNNING
            )
    # Live parent, mismatched fence -> forbidden, regardless of lease.
    for lease in (True, False):
        table[(False, True, False, lease)] = Verdict.FORBIDDEN_FENCE_MISMATCH
    # Live parent, valid fence: the lease decides admit-vs-expired.
    table[(False, True, True, False)] = Verdict.CONFLICT_LEASE_EXPIRED
    table[(False, True, True, True)] = Verdict.ADMIT_NEW
    return table


ADMISSION_TRANSITIONS: dict[tuple[bool, bool, bool, bool], Verdict] = (
    _build_table()
)
"""Every reachable ``(receipted, parent_running, fence_valid,
lease_unexpired)`` combination maps to exactly one verdict. Total over
the fact space; the coordinator performs no arbitration outside this
table."""


def classify_admission(facts: FenceFacts) -> Verdict:
    """Resolve one admission request through the checked table.

    Fail closed: an unlisted fact combination (unreachable over booleans,
    but guarded anyway) arbitrates as a fence mismatch, never as an
    admit.
    """
    return ADMISSION_TRANSITIONS.get(
        facts.key(), Verdict.FORBIDDEN_FENCE_MISMATCH
    )
