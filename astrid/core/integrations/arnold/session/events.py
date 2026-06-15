"""Event builders for the Arnold session-succession ledger."""

from __future__ import annotations

from typing import Any

from astrid.core.util.time import utc_now_iso

from .state import STATE_REF

SEGMENT_BOUNDARY_KIND = "segment_boundary"


def make_segment_boundary_event(
    *,
    from_segment_id: str,
    to_segment_id: str,
    previous_plan_hash: str,
    next_plan_hash: str,
    cursor_ref: str,
    manifest_hash: str,
    state_hash: str,
    reason: str = "plan_mutated",
    state_ref: str = STATE_REF,
) -> dict[str, Any]:
    """Build a segment-boundary event for the locked writer append path.

    This helper is intentionally pure: it does not inspect the event log,
    read the lease, or append anything. The caller must commit it via the
    writer-owned locked append path with the current writer epoch and tail
    hash.
    """

    return {
        "kind": SEGMENT_BOUNDARY_KIND,
        "ts": utc_now_iso(),
        "reason": reason,
        "from_segment_id": from_segment_id,
        "to_segment_id": to_segment_id,
        "previous_plan_hash": previous_plan_hash,
        "next_plan_hash": next_plan_hash,
        "cursor_ref": cursor_ref,
        "manifest_hash": manifest_hash,
        "state_ref": state_ref,
        "state_hash": state_hash,
    }


__all__ = ["SEGMENT_BOUNDARY_KIND", "make_segment_boundary_event"]
