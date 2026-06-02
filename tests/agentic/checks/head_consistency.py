"""C1 — head/sidecar consistency check for frozen timeline assembly."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.agentic.checks.io import FrozenEvidencePack
from tests.agentic.checks.results import ScoredCheckResult, build_check_result


def c1_head_sidecar_consistency(
    evidence_dir: Path | str | FrozenEvidencePack,
) -> ScoredCheckResult:
    """Verify frozen ``assembly.head.json`` sidecars match their ``assembly.jsonl`` streams.

    For each timeline directory under ``timelines/*/``:
    - If no ``assembly.head.json`` exists, skip that timeline.
    - If a head exists but ``assembly.jsonl`` is missing, record a failure.
    - Otherwise, compare ``event_count``, ``last_hash``, and ``version`` from the
      head against the actual JSONL stream.  A mismatch on any field fails the check.

    Returns ``na`` when no timeline carries an ``assembly.head.json`` at all.
    """
    pack = evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)
    evidence_refs: list[str] = []
    timelines_checked: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for timeline_dir in pack.timeline_dirs():
        head_path = timeline_dir / "assembly.head.json"
        events_path = timeline_dir / "assembly.jsonl"

        head_data = pack.read_json(head_path)
        if head_data is None:
            # No head sidecar — skip this timeline
            continue

        evidence_refs.extend(pack.evidence_refs((head_path,)))

        if not isinstance(head_data, dict):
            mismatches.append({
                "timeline": timeline_dir.name,
                "error": "assembly.head.json is not a JSON object",
            })
            continue

        head_event_count = head_data.get("event_count")
        head_last_hash = head_data.get("last_hash")
        head_version = head_data.get("version")

        # Read the JSONL stream
        jsonl_rows = pack.read_jsonl(events_path)
        if jsonl_rows is None:
            # Head exists but stream is missing or unparseable
            entry: dict[str, Any] = {
                "timeline": timeline_dir.name,
                "error": "assembly.jsonl missing or unparseable while assembly.head.json exists",
                "head_event_count": head_event_count,
                "head_last_hash": head_last_hash,
                "head_version": head_version,
                "stream_event_count": None,
                "stream_last_hash": None,
                "stream_version": None,
            }
            mismatches.append(entry)
            continue

        evidence_refs.extend(pack.evidence_refs((events_path,)))

        stream_event_count = len(jsonl_rows)
        last_row = jsonl_rows[-1] if jsonl_rows else None
        stream_last_hash = last_row.get("hash") if isinstance(last_row, dict) else None

        # Derive stream version: the head.version is the number of events (= stream length).
        # The last event's expected_version + 1 should equal the stream length.
        stream_version = stream_event_count

        issues: list[str] = []

        # Compare event_count
        if head_event_count != stream_event_count:
            issues.append(
                f"event_count mismatch: head={head_event_count!r}, stream={stream_event_count!r}"
            )

        # Compare last_hash (both None for empty streams is OK)
        if head_last_hash != stream_last_hash:
            issues.append(
                f"last_hash mismatch: head={head_last_hash!r}, stream={stream_last_hash!r}"
            )

        # Compare version (head.version should equal the stream's event count)
        if head_version != stream_version:
            issues.append(
                f"version mismatch: head.version={head_version!r}, stream version={stream_version!r}"
            )

        timeline_entry: dict[str, Any] = {
            "timeline": timeline_dir.name,
            "head_event_count": head_event_count,
            "head_last_hash": head_last_hash,
            "head_version": head_version,
            "stream_event_count": stream_event_count,
            "stream_last_hash": stream_last_hash,
            "stream_version": stream_version,
        }
        if issues:
            timeline_entry["issues"] = issues
            mismatches.append(timeline_entry)
        timelines_checked.append(timeline_entry)

    if not mismatches and not timelines_checked:
        return build_check_result(
            "C1",
            "na",
            detail={"reason": "no assembly.head.json sidecar present in any frozen timeline"},
        )

    if mismatches:
        return build_check_result(
            "C1",
            "fail",
            evidence_refs=_dedupe(evidence_refs),
            detail={
                "timelines_checked": len(timelines_checked),
                "mismatches": mismatches,
            },
        )

    return build_check_result(
        "C1",
        "pass",
        evidence_refs=_dedupe(evidence_refs),
        detail={
            "timelines_checked": len(timelines_checked),
            "mismatches": [],
        },
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out
