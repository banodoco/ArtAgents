"""S2 — idempotent-reattach check over frozen evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.agentic.checks.io import FrozenEvidencePack
from tests.agentic.checks.results import ScoredCheckResult, build_check_result
from tests.agentic.checks.triggers import TriggerRecord, gate_trigger

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def s2_idempotent_reattach(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: TriggerRecord | None = None,
) -> ScoredCheckResult:
    """Verify idempotent reattach: no duplicate events, stable event IDs.

    Triggered by ``m2_checks.s2_idempotent_reattach.enabled``.
    Returns ``na`` when undeclared.
    Fails when declared trigger is missing baseline/final/reattach evidence,
    or when duplicate events or changed event IDs are detected.
    Returns ``pass`` when event IDs are stable and no duplicates exist.
    """
    pack = (
        evidence_dir
        if isinstance(evidence_dir, FrozenEvidencePack)
        else FrozenEvidencePack(evidence_dir)
    )

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
            "S2",
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

    # ── Reattach diagnostics ─────────────────────────────────────────
    diagnostics = _load_reattach_diagnostics(pack)
    for diag_ref in diagnostics["refs"]:
        evidence_refs.append(diag_ref)

    # ── Idempotent-reattach check ────────────────────────────────────
    issues = _check_idempotent_reattach(baseline_rows, final_events)

    if issues:
        return build_check_result(
            "S2",
            "fail",
            evidence_refs=_dedupe(evidence_refs),
            detail={
                "baseline_count": len(baseline_rows),
                "final_count": len(final_events),
                "diagnostics": diagnostics["summary"],
                "issues": issues,
            },
        )

    return build_check_result(
        "S2",
        "pass",
        evidence_refs=_dedupe(evidence_refs),
        detail={
            "baseline_count": len(baseline_rows),
            "final_count": len(final_events),
            "diagnostics": diagnostics["summary"],
            "issues": [],
        },
    )


# ---------------------------------------------------------------------------
# Evidence detection
# ---------------------------------------------------------------------------

_REATTACH_STDOUT_GLOBS = ("reattach_stdout.txt", "reattach_stdout.log")
_REATTACH_STDERR_GLOBS = ("reattach_stderr.txt", "reattach_stderr.log")


def _available_evidence(pack: FrozenEvidencePack) -> set[str]:
    """Determine which S2 evidence names are present in the frozen pack."""
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

    # reattach_diagnostics — any stdout or stderr file present
    for glob_pat in _REATTACH_STDOUT_GLOBS + _REATTACH_STDERR_GLOBS:
        try:
            files = pack.glob_files(glob_pat)
        except Exception:
            continue
        if files:
            available.add("reattach_diagnostics")
            break

    return available


def _load_reattach_diagnostics(pack: FrozenEvidencePack) -> dict[str, Any]:
    """Load stdout/stderr diagnostics from the frozen pack.

    Returns a dict with ``refs`` (list of evidence refs) and ``summary``
    (a dict with stdout/stderr content summaries).
    """
    refs: list[str] = []
    summary: dict[str, str | None] = {"stdout": None, "stderr": None}

    for glob_pat in _REATTACH_STDOUT_GLOBS:
        try:
            files = pack.glob_files(glob_pat)
        except Exception:
            continue
        for file_path in files:
            text = pack.read_text(file_path)
            if text is not None:
                refs.append(pack.evidence_ref(file_path))
                if summary["stdout"] is None:
                    summary["stdout"] = text[:2000]  # first 2000 chars for summary
                break
        if summary["stdout"] is not None:
            break

    for glob_pat in _REATTACH_STDERR_GLOBS:
        try:
            files = pack.glob_files(glob_pat)
        except Exception:
            continue
        for file_path in files:
            text = pack.read_text(file_path)
            if text is not None:
                refs.append(pack.evidence_ref(file_path))
                if summary["stderr"] is None:
                    summary["stderr"] = text[:2000]
                break
        if summary["stderr"] is not None:
            break

    return {"refs": refs, "summary": summary}


# ---------------------------------------------------------------------------
# Idempotent-reattach core logic
# ---------------------------------------------------------------------------


def _hash_val(event: dict[str, Any]) -> str | None:
    """Return the hash value from an event, or None."""
    h = event.get("hash")
    if isinstance(h, str) and h:
        return h
    return None


def _event_identity(event: dict[str, Any]) -> str | None:
    """Return a stable identity string for an event.

    Uses ``event_id`` for timeline events; falls back to a positional
    identity derived from kind + hash for task events.
    """
    event_id = event.get("event_id")
    if isinstance(event_id, str) and event_id:
        return f"id:{event_id}"

    # For task events without event_id, derive identity from kind + hash
    kind = event.get("kind")
    h = _hash_val(event)
    if isinstance(kind, str) and h:
        return f"kind:{kind}:hash:{h}"
    return None


def _check_idempotent_reattach(
    baseline: list[dict[str, Any]],
    final: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check for duplicate events and stable event IDs.

    Returns a list of issue dicts (empty if idempotent).
    """
    issues: list[dict[str, Any]] = []

    # ── Build baseline identity→event map ────────────────────────────
    baseline_by_id: dict[str, dict[str, Any]] = {}
    baseline_identities: set[str] = set()
    for idx, event in enumerate(baseline):
        identity = _event_identity(event)
        if identity is None:
            continue
        baseline_by_id[identity] = event
        baseline_identities.add(identity)

    # ── Scan final events for duplicates and changes ────────────────
    seen_identities: dict[str, int] = {}  # identity → first index
    final_by_id: dict[str, dict[str, Any]] = {}

    for idx, event in enumerate(final):
        identity = _event_identity(event)
        if identity is None:
            continue

        # Duplicate detection
        if identity in seen_identities:
            first_idx = seen_identities[identity]
            issues.append({
                "kind": "duplicate_event",
                "identity": identity,
                "first_index": first_idx,
                "duplicate_index": idx,
            })
        else:
            seen_identities[identity] = idx
            final_by_id[identity] = event

    # ── Compare identities across baseline and final ─────────────────
    # Events in baseline that are missing from final
    for identity, baseline_event in baseline_by_id.items():
        if identity not in final_by_id:
            issues.append({
                "kind": "missing_event",
                "identity": identity,
                "baseline_hash": _hash_val(baseline_event),
            })

    # NOTE: Events in final that weren't in baseline are NOT flagged.
    # Extra events after reattach are legitimate new activity.

    # ── Hash stability check for events in both ──────────────────────
    for identity in baseline_by_id:
        if identity in final_by_id:
            baseline_hash = _hash_val(baseline_by_id[identity])
            final_hash = _hash_val(final_by_id[identity])
            if baseline_hash is not None and final_hash is not None and baseline_hash != final_hash:
                issues.append({
                    "kind": "hash_changed",
                    "identity": identity,
                    "baseline_hash": baseline_hash,
                    "final_hash": final_hash,
                })

    return issues


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out
