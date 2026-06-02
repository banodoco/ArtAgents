"""S1 — append-not-rewrite check over frozen evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.agentic.checks.io import FrozenEvidencePack
from tests.agentic.checks.results import ScoredCheckResult, build_check_result
from tests.agentic.checks.triggers import TriggerRecord, gate_trigger

# Erasure/repair event kinds that exempt rewrites
# Timeline-side: timeline.erased, timeline.repaired, timeline.recovered,
#   timeline.reverted, timeline.tombstoned
# Task-side (via events.jsonl): run_aborted, step_failed, cursor_rewind,
#   step_skipped, iteration_failed
_ERASURE_REPAIR_KINDS: frozenset[str] = frozenset({
    "timeline.erased",
    "timeline.repaired",
    "timeline.recovered",
    "timeline.reverted",
    "timeline.tombstoned",
    # ErasedPayload appears as the payload kind when an event payload
    # has been erased (the event itself retains its original kind)
})


def s1_append_not_rewrite(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: TriggerRecord | None = None,
) -> ScoredCheckResult:
    """Verify append-only event stream growth (no rewrites).

    Triggered by ``m2_checks.s1_append_not_rewrite.enabled``.
    Returns ``na`` when undeclared.
    Fails when declared trigger is missing baseline/final evidence,
    or when event ID/hash prefix comparison detects a rewrite without
    an erasure/repair exemption.
    Returns ``pass`` when the event stream is append-only or when
    an erasure/repair exemption applies.
    """
    pack = evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)

    # Determine available evidence
    available = _available_evidence(pack)

    # Gate: absent/undeclared trigger → na; missing required evidence → fail
    if trigger_record is not None:
        gated = gate_trigger(trigger_record, available_evidence=available)
        if gated is not None:
            return gated

    evidence_refs: list[str] = []

    # ── Baseline events ──────────────────────────────────────────────
    baseline_path = Path("baseline_events.jsonl")
    baseline_rows = pack.read_jsonl(baseline_path)
    if baseline_rows is None:
        return build_check_result(
            "S1",
            "fail",
            detail={"reason": "baseline_events.jsonl missing or unparseable"},
        )
    baseline_ref = pack.evidence_ref(baseline_path)
    evidence_refs.append(baseline_ref)

    # ── Final events ─────────────────────────────────────────────────
    final_events: list[dict[str, Any]] = []
    for run_dir in pack.run_dirs():
        events_path = run_dir / "events.jsonl"
        rows = pack.read_jsonl(events_path)
        if rows is not None:
            evidence_refs.append(pack.evidence_ref(events_path))
            final_events.extend(rows)

    for timeline_dir in pack.timeline_dirs():
        assembly_path = timeline_dir / "assembly.jsonl"
        rows = pack.read_jsonl(assembly_path)
        if rows is not None:
            evidence_refs.append(pack.evidence_ref(assembly_path))
            final_events.extend(rows)

    # ── Erasure/repair exemption ─────────────────────────────────────
    exempt = _has_erasure_repair_exemption(final_events)

    # ── Compare events ───────────────────────────────────────────────
    mismatches = _compare_streams(baseline_rows, final_events)

    if mismatches and not exempt:
        return build_check_result(
            "S1",
            "fail",
            evidence_refs=_dedupe(evidence_refs),
            detail={
                "baseline_count": len(baseline_rows),
                "final_count": len(final_events),
                "exemption_applied": False,
                "mismatches": mismatches,
            },
        )

    return build_check_result(
        "S1",
        "pass",
        evidence_refs=_dedupe(evidence_refs),
        detail={
            "baseline_count": len(baseline_rows),
            "final_count": len(final_events),
            "exemption_applied": exempt and bool(mismatches),
            "mismatches": [],
        },
    )


def _available_evidence(pack: FrozenEvidencePack) -> set[str]:
    """Determine which S1 evidence names are present in the frozen pack."""
    available: set[str] = set()

    # baseline_events — check file existence
    if pack.read_bytes("baseline_events.jsonl") is not None:
        available.add("baseline_events")

    # final_events — any run or timeline JSONL file present
    has_final = False
    for run_dir in pack.run_dirs():
        if pack.read_bytes(run_dir / "events.jsonl") is not None:
            has_final = True
            break
    if not has_final:
        for timeline_dir in pack.timeline_dirs():
            if pack.read_bytes(timeline_dir / "assembly.jsonl") is not None:
                has_final = True
                break
    if has_final:
        available.add("final_events")

    return available


def _event_hash_val(event: dict[str, Any]) -> str | None:
    """Return the hash value from an event, or None."""
    h = event.get("hash")
    if isinstance(h, str) and h:
        return h
    return None


def _is_erasure_repair_event(event: dict[str, Any]) -> bool:
    """Check if an event indicates erasure/repair activity."""
    if not isinstance(event, dict):
        return False

    kind = event.get("kind")
    if isinstance(kind, str) and kind in _ERASURE_REPAIR_KINDS:
        return True

    # Check for ErasedPayload in the payload
    payload = event.get("payload")
    if isinstance(payload, dict):
        payload_kind = payload.get("kind")
        if payload_kind == "ErasedPayload":
            return True

    return False


def _has_erasure_repair_exemption(events: list[dict[str, Any]]) -> bool:
    """Return True if any event in the stream indicates erasure/repair."""
    return any(_is_erasure_repair_event(e) for e in events)


def _compare_streams(
    baseline: list[dict[str, Any]],
    final: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compare baseline and final event streams for append-only growth.

    Two-phase comparison:

    1. **Event-ID match** (timeline events): events with ``event_id`` are
       matched by identity.  Same identity + different hash → rewrite.

    2. **Positional + hash-presence match** (task events): events without
       ``event_id`` are compared positionally within the concatenated
       final stream.  If a baseline event's hash does not appear in final
       at all, it was removed or rewritten.

    Returns a list of mismatch details (empty if append-only).
    """
    mismatches: list[dict[str, Any]] = []

    # Separate baseline events into those with event_id and those without
    baseline_with_id: list[tuple[str, str | None, int, dict[str, Any]]] = []
    baseline_no_id: list[tuple[str | None, int, dict[str, Any]]] = []
    for idx, event in enumerate(baseline):
        h = _event_hash_val(event)
        event_id = event.get("event_id")
        if isinstance(event_id, str) and event_id:
            baseline_with_id.append((event_id, h, idx, event))
        else:
            baseline_no_id.append((h, idx, event))

    # Build final identity map (event_id → list of (hash, index))
    final_by_event_id: dict[str, list[tuple[str | None, int]]] = {}
    final_by_hash: dict[str, list[int]] = {}
    for idx, event in enumerate(final):
        h = _event_hash_val(event)
        event_id = event.get("event_id")
        if isinstance(event_id, str) and event_id:
            final_by_event_id.setdefault(event_id, []).append((h, idx))
        if h:
            final_by_hash.setdefault(h, []).append(idx)

    # Collect all final hashes for presence check
    final_hashes: set[str] = set(final_by_hash.keys())

    # ── Phase 1: Event-ID matching ────────────────────────────────────
    for event_id, baseline_hash, baseline_idx, _baseline_event in baseline_with_id:
        final_matches = final_by_event_id.get(event_id, [])
        if not final_matches:
            mismatches.append({
                "kind": "missing_event",
                "identity": f"id:{event_id}",
                "baseline_hash": baseline_hash,
                "baseline_index": baseline_idx,
            })
            continue
        # Use the first match (in practice there should be only one)
        final_hash, final_idx = final_matches[0]
        if baseline_hash is not None and final_hash is not None and baseline_hash != final_hash:
            mismatches.append({
                "kind": "hash_mismatch",
                "identity": f"id:{event_id}",
                "baseline_hash": baseline_hash,
                "final_hash": final_hash,
                "baseline_index": baseline_idx,
                "final_index": final_idx,
            })

    # ── Phase 2: Positional + hash-presence matching ──────────────────
    for baseline_hash, baseline_idx, _baseline_event in baseline_no_id:
        # Check if the baseline hash appears in final at all
        if baseline_hash is not None and baseline_hash in final_hashes:
            # Hash present → event exists in final, OK
            continue

        # Hash not present → event was removed or rewritten
        # Check positionally: did the event at this position change?
        if baseline_idx < len(final):
            final_event = final[baseline_idx]
            final_hash = _event_hash_val(final_event)
            mismatches.append({
                "kind": "hash_mismatch_positional",
                "baseline_index": baseline_idx,
                "baseline_hash": baseline_hash,
                "final_hash": final_hash,
            })
        else:
            mismatches.append({
                "kind": "missing_event_positional",
                "baseline_index": baseline_idx,
                "baseline_hash": baseline_hash,
            })

    return mismatches


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out
