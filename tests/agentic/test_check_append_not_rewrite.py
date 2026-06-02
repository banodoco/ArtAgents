from __future__ import annotations

import json
from pathlib import Path

from tests.agentic.checks.append_not_rewrite import s1_append_not_rewrite
from tests.agentic.checks.triggers import TriggerRecord, resolve_trigger_records


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_run_events(evidence_dir: Path, run_id: str, rows: list[dict]) -> Path:
    events_path = evidence_dir / "runs" / run_id / "events.jsonl"
    _write_jsonl(events_path, rows)
    return events_path


def _write_timeline_assembly(evidence_dir: Path, timeline_id: str, rows: list[dict]) -> Path:
    assembly_path = evidence_dir / "timelines" / timeline_id / "assembly.jsonl"
    _write_jsonl(assembly_path, rows)
    return assembly_path


def _make_basic_event(*, idx: int = 0, kind: str = "run_started") -> dict:
    ts_second = 100 + idx
    return {
        "kind": kind,
        "ts": f"2025-01-01T00:01:{ts_second:02d}Z",
        "run_id": "run-1",
        "hash": f"hash-{idx:04d}",
    }


def _make_timeline_event(
    *,
    event_id: str,
    kind: str = "timeline.created",
    hash_val: str | None = None,
    idx: int = 0,
) -> dict:
    ts_second = 100 + idx
    event: dict = {
        "event_id": event_id,
        "kind": kind,
        "ts": f"2025-01-01T00:01:{ts_second:02d}Z",
        "timeline_id": "tl-test",
    }
    if hash_val is not None:
        event["hash"] = hash_val
    return event


def _s1_enabled() -> TriggerRecord:
    records = resolve_trigger_records(
        scenario_extras={
            "m2_checks": {
                "s1_append_not_rewrite": {"enabled": True},
            }
        }
    )
    return records["S1"]


def _s1_disabled() -> TriggerRecord:
    records = resolve_trigger_records()
    return records["S1"]


# ---------------------------------------------------------------------------
# na — trigger not declared
# ---------------------------------------------------------------------------

def test_s1_returns_na_when_trigger_not_declared(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_disabled())

    assert result["id"] == "S1"
    assert result["status"] == "na"
    assert result["detail"]["reason"] == "trigger not declared"


def test_s1_returns_na_when_no_trigger_record_provided_and_no_evidence(tmp_path: Path) -> None:
    """Without trigger_record, no gating happens, but missing baseline → fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = s1_append_not_rewrite(evidence_dir)

    assert result["id"] == "S1"
    assert result["status"] == "fail"
    assert "baseline_events.jsonl missing" in result["detail"]["reason"]


# ---------------------------------------------------------------------------
# fail — declared trigger missing required evidence
# ---------------------------------------------------------------------------

def test_s1_fails_when_baseline_events_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["id"] == "S1"
    assert result["status"] == "fail"
    assert result["detail"]["reason"] == "declared trigger missing required evidence"
    assert "baseline_events" in result["detail"]["missing_evidence"]


def test_s1_fails_when_final_events_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["id"] == "S1"
    assert result["status"] == "fail"
    assert result["detail"]["reason"] == "declared trigger missing required evidence"
    assert "final_events" in result["detail"]["missing_evidence"]


def test_s1_fails_when_all_evidence_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["id"] == "S1"
    assert result["status"] == "fail"
    assert result["detail"]["reason"] == "declared trigger missing required evidence"
    assert set(result["detail"]["missing_evidence"]) == {"baseline_events", "final_events"}


# ---------------------------------------------------------------------------
# pass — append-only growth (no rewrites)
# ---------------------------------------------------------------------------

def test_s1_passes_when_identical_events(tmp_path: Path) -> None:
    """Same events in baseline and final → pass."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    events = [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="plan_initialized"),
    ]
    _write_jsonl(evidence_dir / "baseline_events.jsonl", events)
    _write_run_events(evidence_dir, "run-1", events)

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["id"] == "S1"
    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 2
    assert result["detail"]["final_count"] == 2
    assert result["detail"]["mismatches"] == []


def test_s1_passes_when_final_has_extra_events(tmp_path: Path) -> None:
    """Extra events in final (append-only growth) → pass."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0),
    ])
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="step_dispatched"),  # extra/appended
        _make_basic_event(idx=2, kind="step_completed"),   # extra/appended
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 1
    assert result["detail"]["final_count"] == 3


def test_s1_passes_with_empty_baseline_and_final(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [])
    _write_run_events(evidence_dir, "run-1", [])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 0
    assert result["detail"]["final_count"] == 0


def test_s1_passes_with_extra_events_across_runs_and_timelines(tmp_path: Path) -> None:
    """Append-only across multiple runs and timelines."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    # Baseline: 3 events
    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="plan_initialized"),
        _make_basic_event(idx=2, kind="step_dispatched"),
    ])
    # Final: run-1 has first 2, timeline has last 1 + 1 extra
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="plan_initialized"),
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-0002", idx=2),
        _make_timeline_event(event_id="evt-002", kind="clip.added", hash_val="hash-extra", idx=3),  # extra
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 3
    assert result["detail"]["final_count"] == 4


# ---------------------------------------------------------------------------
# fail — rewrite detected (no exemption)
# ---------------------------------------------------------------------------

def test_s1_fails_when_event_hash_changes(tmp_path: Path) -> None:
    """Same event identity, different hash → rewrite → fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0, kind="run_started"),
    ])
    # Same kind/position, but different hash
    _write_run_events(evidence_dir, "run-1", [
        {"kind": "run_started", "ts": "2025-01-01T00:01:40Z", "run_id": "run-1", "hash": "hash-changed"},
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "fail"
    mismatches = result["detail"]["mismatches"]
    assert len(mismatches) >= 1
    # Should detect the hash mismatch
    kinds = {m["kind"] for m in mismatches}
    assert "hash_mismatch_positional" in kinds or "hash_not_in_final" in kinds


def test_s1_fails_when_baseline_event_missing_from_final(tmp_path: Path) -> None:
    """Fewer events in final than baseline → events removed → fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="plan_initialized"),
        _make_basic_event(idx=2, kind="step_dispatched"),
    ])
    # Final has fewer events
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0),
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "fail"


def test_s1_fails_when_timeline_event_hash_changes(tmp_path: Path) -> None:
    """Timeline event with same event_id but different hash → rewrite → fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-original", idx=0),
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-rewritten", idx=0),
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "fail"
    mismatches = result["detail"]["mismatches"]
    hash_mismatches = [m for m in mismatches if m["kind"] == "hash_mismatch"]
    assert len(hash_mismatches) >= 1
    assert hash_mismatches[0]["identity"] == "id:evt-001"
    assert hash_mismatches[0]["baseline_hash"] == "hash-original"
    assert hash_mismatches[0]["final_hash"] == "hash-rewritten"


def test_s1_fails_when_timeline_event_missing(tmp_path: Path) -> None:
    """Timeline event in baseline not found in final → fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-001", idx=0),
        _make_timeline_event(event_id="evt-002", kind="clip.added", hash_val="hash-002", idx=1),
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-001", idx=0),
        # evt-002 is missing
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "fail"
    mismatches = result["detail"]["mismatches"]
    missing = [m for m in mismatches if m["kind"] == "missing_event"]
    assert len(missing) >= 1


def test_s1_fails_with_mixed_rewrites(tmp_path: Path) -> None:
    """Multiple kinds of mismatches in one check."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0, kind="run_started"),
        _make_basic_event(idx=1, kind="plan_initialized"),
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-original", idx=2),
    ])
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0, kind="run_started"),  # same
        {"kind": "plan_initialized", "ts": "2025-01-01T00:01:41Z", "run_id": "run-1", "hash": "hash-rewritten"},  # changed
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-rewritten-tl", idx=2),  # changed
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "fail"
    assert len(result["detail"]["mismatches"]) >= 2


# ---------------------------------------------------------------------------
# pass — erasure/repair exemption
# ---------------------------------------------------------------------------

def test_s1_passes_with_erasure_exemption_despite_rewrite(tmp_path: Path) -> None:
    """When erasure events exist in the timeline, rewrites are exempted."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-original", idx=0),
        _make_timeline_event(event_id="evt-002", kind="clip.added", hash_val="hash-002", idx=1),
    ])
    # Final: evt-001 has different hash (rewritten), but erasure events exist
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-rewritten", idx=0),
        _make_timeline_event(event_id="evt-002", kind="clip.added", hash_val="hash-002", idx=1),
        _make_timeline_event(event_id="evt-eras", kind="timeline.erased", hash_val="hash-eras", idx=2),
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["exemption_applied"] is True


def test_s1_passes_with_repair_exemption_despite_rewrite(tmp_path: Path) -> None:
    """When repair events exist, rewrites are exempted."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0, kind="run_started"),
        _make_basic_event(idx=1, kind="plan_initialized"),
    ])
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0, kind="run_started"),
        {"kind": "plan_initialized", "ts": "2025-01-01T00:01:41Z", "run_id": "run-1", "hash": "hash-rewritten"},
    ])
    # Timeline has repair event
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-r01", kind="timeline.repaired", hash_val="hash-repair", idx=0),
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["exemption_applied"] is True


def test_s1_passes_with_tombstone_exemption_despite_rewrite(tmp_path: Path) -> None:
    """When tombstoned events exist, rewrites are exempted."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-original", idx=0),
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-rewritten", idx=0),
        _make_timeline_event(event_id="evt-tom", kind="timeline.tombstoned", hash_val="hash-tomb", idx=1),
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["exemption_applied"] is True


def test_s1_passes_with_erased_payload_exemption(tmp_path: Path) -> None:
    """When an event payload is ErasedPayload, rewrites are exempted."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_timeline_event(event_id="evt-001", kind="clip.added", hash_val="hash-original", idx=0),
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="clip.added", hash_val="hash-rewritten", idx=0),
        {
            "event_id": "evt-eras",
            "kind": "timeline.erased",
            "ts": "2025-01-01T00:01:42Z",
            "timeline_id": "tl-test",
            "hash": "hash-eras",
            "payload": {"kind": "ErasedPayload", "original_kind": "clip.added"},
        },
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["exemption_applied"] is True


# ---------------------------------------------------------------------------
# fail — no exemption, but rewrite detected
# ---------------------------------------------------------------------------

def test_s1_fails_when_no_exemption_and_rewrite_detected(tmp_path: Path) -> None:
    """Rewrite without erasure/repair → fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-original", idx=0),
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-rewritten", idx=0),
        # No erasure/repair events
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "fail"
    assert result["detail"]["exemption_applied"] is False


# ---------------------------------------------------------------------------
# pass — exemption not needed when no rewrite
# ---------------------------------------------------------------------------

def test_s1_passes_no_exemption_needed_when_no_rewrite(tmp_path: Path) -> None:
    """When there's no rewrite, exemption flag is irrelevant but pass."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0),
    ])
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="step_dispatched"),
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["exemption_applied"] is False  # no exemption needed


# ---------------------------------------------------------------------------
# edge cases
# ---------------------------------------------------------------------------

def test_s1_handles_unparseable_baseline(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    (evidence_dir / "baseline_events.jsonl").write_text("not valid json\n", encoding="utf-8")
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert result["status"] == "fail"
    assert "baseline_events.jsonl missing or unparseable" in result["detail"]["reason"]


def test_s1_handles_run_with_unparseable_events_gracefully(tmp_path: Path) -> None:
    """An unparseable run events.jsonl should be skipped."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    runs_dir = evidence_dir / "runs" / "run-1"
    runs_dir.mkdir(parents=True)
    (runs_dir / "events.jsonl").write_text("invalid json\n", encoding="utf-8")

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    # Unparseable run → 0 final events, baseline has 1 → position mismatch → fail
    assert result["status"] == "fail"


def test_s1_returns_evidence_refs(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    assert len(result["evidence_refs"]) >= 2
    refs_set = set(result["evidence_refs"])
    assert "baseline_events.jsonl" in refs_set
    assert "runs/run-1/events.jsonl" in refs_set


def test_s1_passes_when_final_has_fewer_events_but_all_match(tmp_path: Path) -> None:
    """If final has fewer events but all present events match baseline, 
    S1 still fails because events were removed (not just append)."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="plan_initialized"),
        _make_basic_event(idx=2, kind="step_dispatched"),
    ])
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="plan_initialized"),
    ])

    result = s1_append_not_rewrite(evidence_dir, trigger_record=_s1_enabled())

    # Fewer events → fail (events removed)
    assert result["status"] == "fail"
