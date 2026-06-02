"""C3 — no-mutation-on-read check over frozen evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.agentic.checks.io import FrozenEvidencePack
from tests.agentic.checks.results import ScoredCheckResult, build_check_result
from tests.agentic.checks.triggers import TriggerRecord, gate_trigger

_BASELINE_PATH = "baseline_events.jsonl"
_GIT_DIFF_PATH = "git_diff.patch"


def c3_no_mutation_on_read(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: TriggerRecord | None = None,
) -> ScoredCheckResult:
    """Verify no mutation occurred during read/audit operations.

    Triggered by ``m2_checks.c3_no_mutation_on_read.enabled``.
    Returns ``na`` when undeclared.
    Fails when declared trigger is missing baseline/final evidence,
    extra events exist beyond the baseline snapshot, or the frozen
    ``git_diff.patch`` is non-empty.
    """
    pack = evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)

    # Determine available evidence from the frozen pack
    available = _available_evidence(pack)

    # Gate: absent/undeclared trigger → na; missing required evidence → fail
    if trigger_record is not None:
        gated = gate_trigger(trigger_record, available_evidence=available)
        if gated is not None:
            return gated

    evidence_refs: list[str] = []

    # ── Baseline events ──────────────────────────────────────────────
    baseline_path = Path(_BASELINE_PATH)
    baseline_rows = pack.read_jsonl(baseline_path)
    if baseline_rows is None:
        return build_check_result(
            "C3",
            "fail",
            detail={
                "reason": "baseline_events.jsonl missing or unparseable",
            },
        )
    baseline_ref = pack.evidence_ref(baseline_path)
    evidence_refs.append(baseline_ref)
    baseline_count = len(baseline_rows)

    # ── Final events ─────────────────────────────────────────────────
    final_count = 0
    for run_dir in pack.run_dirs():
        events_path = run_dir / "events.jsonl"
        rows = pack.read_jsonl(events_path)
        if rows is not None:
            evidence_refs.append(pack.evidence_ref(events_path))
            final_count += len(rows)

    for timeline_dir in pack.timeline_dirs():
        assembly_path = timeline_dir / "assembly.jsonl"
        rows = pack.read_jsonl(assembly_path)
        if rows is not None:
            evidence_refs.append(pack.evidence_ref(assembly_path))
            final_count += len(rows)

    # ── Git diff ─────────────────────────────────────────────────────
    diff_path = Path(_GIT_DIFF_PATH)
    diff_text = pack.read_text(diff_path)
    diff_ref = pack.evidence_ref(diff_path)
    evidence_refs.append(diff_ref)

    diff_non_empty = bool(diff_text is not None and diff_text.strip())

    # ── Verdict ──────────────────────────────────────────────────────
    mismatches: list[dict[str, Any]] = []

    if final_count > baseline_count:
        mismatches.append({
            "kind": "extra_events",
            "baseline_count": baseline_count,
            "final_count": final_count,
            "extra_count": final_count - baseline_count,
        })

    if diff_non_empty:
        mismatches.append({
            "kind": "non_empty_diff",
            "diff_path": _GIT_DIFF_PATH,
        })

    if mismatches:
        return build_check_result(
            "C3",
            "fail",
            evidence_refs=_dedupe(evidence_refs),
            detail={
                "baseline_count": baseline_count,
                "final_count": final_count,
                "diff_non_empty": diff_non_empty,
                "mismatches": mismatches,
            },
        )

    return build_check_result(
        "C3",
        "pass",
        evidence_refs=_dedupe(evidence_refs),
        detail={
            "baseline_count": baseline_count,
            "final_count": final_count,
            "diff_non_empty": False,
            "mismatches": [],
        },
    )


def _available_evidence(pack: FrozenEvidencePack) -> set[str]:
    """Determine which C3 evidence names are present in the frozen pack.

    Evidence is considered *available* when the file exists in the pack, even
    if it is later unparseable.  The check itself reports the specific failure
    when it hits unparseable content.
    """
    available: set[str] = set()

    # baseline_events — check file existence, not parse success
    if pack.read_bytes(_BASELINE_PATH) is not None:
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

    # git_diff_patch — check file existence
    if pack.read_bytes(_GIT_DIFF_PATH) is not None:
        available.add("git_diff_patch")

    return available


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out
