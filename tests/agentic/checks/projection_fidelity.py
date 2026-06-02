"""C4 — projection-fidelity check over frozen evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astrid.core.timeline.events.schema.types import TimelineEvent
from astrid.core.timeline.projection import project_to_assembly

from tests.agentic.checks.io import FrozenEvidencePack
from tests.agentic.checks.results import ScoredCheckResult, build_check_result
from tests.agentic.checks.triggers import TriggerRecord


def c4_projection_fidelity(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: TriggerRecord | None = None,
) -> ScoredCheckResult:
    """Verify projection fidelity against a frozen read-only assembly.json snapshot.

    Triggered by ``m2_checks.c4_projection_fidelity.enabled``.
    Returns ``na`` when undeclared or when no frozen ``assembly.json`` snapshot
    exists in any timeline directory.
    Returns ``fail`` when projection output disagrees with the frozen snapshot,
    or when required event/log files are missing/unparseable.
    Returns ``pass`` when all timeline projections match their snapshots.
    """
    pack = evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)

    # Gate: absent/undeclared trigger → na
    if trigger_record is not None and not trigger_record.enabled:
        return build_check_result(
            "C4",
            "na",
            detail={
                "reason": "trigger not declared",
                "trigger_key": trigger_record.trigger_key,
            },
        )

    evidence_refs: list[str] = []
    timeline_dirs = pack.timeline_dirs()

    # ── Snapshot presence gate ───────────────────────────────────────
    # Find timelines that have an assembly.json snapshot
    timelines_with_snapshot: list[Path] = []
    for tdir in timeline_dirs:
        snapshot_path = tdir / "assembly.json"
        if pack.read_bytes(snapshot_path) is not None:
            timelines_with_snapshot.append(tdir)

    if not timelines_with_snapshot:
        # No snapshot in any timeline → na (trigger not satisfied)
        return build_check_result(
            "C4",
            "na",
            detail={
                "reason": "no frozen assembly.json snapshot in any timeline",
                "timeline_count": len(timeline_dirs),
            },
        )

    # ── Project and compare per timeline ─────────────────────────────
    mismatches: list[dict[str, Any]] = []
    passed: list[str] = []
    failed: list[str] = []

    for tdir in sorted(timelines_with_snapshot):
        timeline_name = tdir.name
        snapshot_path = tdir / "assembly.json"
        stream_path = tdir / "assembly.jsonl"

        snapshot_ref = pack.evidence_ref(snapshot_path)
        evidence_refs.append(snapshot_ref)

        # Read the frozen snapshot
        frozen_json = pack.read_json(snapshot_path)
        if frozen_json is None:
            mismatch = {
                "timeline": timeline_name,
                "kind": "snapshot_unparseable",
                "detail": "assembly.json exists but cannot be parsed as JSON",
            }
            mismatches.append(mismatch)
            failed.append(timeline_name)
            continue

        # Read the frozen event stream
        stream_rows = pack.read_jsonl(stream_path)
        stream_ref = pack.evidence_ref(stream_path)
        evidence_refs.append(stream_ref)

        if stream_rows is None:
            mismatch = {
                "timeline": timeline_name,
                "kind": "stream_missing_or_unparseable",
                "detail": "assembly.jsonl missing or unparseable",
            }
            mismatches.append(mismatch)
            failed.append(timeline_name)
            continue

        # Convert raw dicts to TimelineEvent objects
        try:
            events = [TimelineEvent.from_dict(row) for row in stream_rows]
        except Exception as exc:
            mismatch = {
                "timeline": timeline_name,
                "kind": "stream_schema_error",
                "detail": f"assembly.jsonl events cannot be deserialized: {exc}",
            }
            mismatches.append(mismatch)
            failed.append(timeline_name)
            continue

        # Project
        try:
            projected = project_to_assembly(events)
        except Exception as exc:
            mismatch = {
                "timeline": timeline_name,
                "kind": "projection_error",
                "detail": f"project_to_assembly raised: {exc}",
            }
            mismatches.append(mismatch)
            failed.append(timeline_name)
            continue

        # Canonical compare (deep equality via JSON round-trip for stability)
        if not _deep_equal(projected, frozen_json):
            mismatch = {
                "timeline": timeline_name,
                "kind": "projection_mismatch",
                "projected": projected,
                "frozen": frozen_json,
            }
            mismatches.append(mismatch)
            failed.append(timeline_name)
        else:
            passed.append(timeline_name)

    # ── Verdict ──────────────────────────────────────────────────────
    if not mismatches:
        return build_check_result(
            "C4",
            "pass",
            evidence_refs=_dedupe(evidence_refs),
            detail={
                "timelines_checked": passed,
                "mismatches": [],
            },
        )

    return build_check_result(
        "C4",
        "fail",
        evidence_refs=_dedupe(evidence_refs),
        detail={
            "timelines_passed": passed,
            "timelines_failed": failed,
            "mismatches": mismatches,
        },
    )


def _deep_equal(a: Any, b: Any) -> bool:
    """Canonical comparison via JSON round-trip for stable ordering."""
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out
