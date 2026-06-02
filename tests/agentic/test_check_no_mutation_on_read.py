from __future__ import annotations

import json
from pathlib import Path

from tests.agentic.checks.no_mutation_on_read import c3_no_mutation_on_read
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


def _c3_enabled() -> TriggerRecord:
    records = resolve_trigger_records(
        scenario_extras={
            "m2_checks": {
                "c3_no_mutation_on_read": {"enabled": True},
            }
        }
    )
    return records["C3"]


def _c3_disabled() -> TriggerRecord:
    records = resolve_trigger_records()
    return records["C3"]


# ---------------------------------------------------------------------------
# na — trigger not declared
# ---------------------------------------------------------------------------

def test_c3_returns_na_when_trigger_not_declared(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_disabled())

    assert result["id"] == "C3"
    assert result["status"] == "na"
    assert result["detail"]["reason"] == "trigger not declared"


def test_c3_returns_na_when_no_trigger_record_provided_and_no_evidence(tmp_path: Path) -> None:
    """When no trigger_record is provided, the check runs but returns na if no evidence."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = c3_no_mutation_on_read(evidence_dir)

    # Without a trigger_record, no gating happens, but missing baseline → fail
    assert result["id"] == "C3"
    assert result["status"] == "fail"
    assert "baseline_events.jsonl missing" in result["detail"]["reason"]


# ---------------------------------------------------------------------------
# fail — declared trigger missing required evidence
# ---------------------------------------------------------------------------

def test_c3_fails_when_baseline_events_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["id"] == "C3"
    assert result["status"] == "fail"
    assert result["detail"]["reason"] == "declared trigger missing required evidence"
    assert "baseline_events" in result["detail"]["missing_evidence"]


def test_c3_fails_when_final_events_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["id"] == "C3"
    assert result["status"] == "fail"
    assert result["detail"]["reason"] == "declared trigger missing required evidence"
    assert "final_events" in result["detail"]["missing_evidence"]


def test_c3_fails_when_git_diff_patch_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["id"] == "C3"
    assert result["status"] == "fail"
    assert result["detail"]["reason"] == "declared trigger missing required evidence"
    assert "git_diff_patch" in result["detail"]["missing_evidence"]


def test_c3_fails_when_all_evidence_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["id"] == "C3"
    assert result["status"] == "fail"
    assert result["detail"]["reason"] == "declared trigger missing required evidence"
    assert set(result["detail"]["missing_evidence"]) == {
        "baseline_events", "final_events", "git_diff_patch",
    }


# ---------------------------------------------------------------------------
# pass — same event counts, empty diff
# ---------------------------------------------------------------------------

def test_c3_passes_when_no_mutation_detected(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    # Baseline: 2 events
    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="plan_initialized"),
    ])
    # Final: same 2 events in a run
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="plan_initialized"),
    ])
    # Empty diff
    (evidence_dir / "git_diff.patch").write_text("", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["id"] == "C3"
    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 2
    assert result["detail"]["final_count"] == 2
    assert result["detail"]["diff_non_empty"] is False
    assert result["detail"]["mismatches"] == []


def test_c3_passes_with_empty_baseline_and_final_single_run(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [])
    _write_run_events(evidence_dir, "run-1", [])
    (evidence_dir / "git_diff.patch").write_text("", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 0
    assert result["detail"]["final_count"] == 0


def test_c3_passes_with_multiple_runs_and_timelines(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    # Baseline: 4 events
    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=i) for i in range(4)
    ])
    # Final: run-1 has 2 events, run-2 has 1 event, timeline has 1 event = 4
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0), _make_basic_event(idx=1)
    ])
    _write_run_events(evidence_dir, "run-2", [
        _make_basic_event(idx=2)
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_basic_event(idx=3, kind="timeline.created")
    ])
    (evidence_dir / "git_diff.patch").write_text("", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 4
    assert result["detail"]["final_count"] == 4


def test_c3_passes_with_only_whitespace_in_diff(tmp_path: Path) -> None:
    """A diff with only whitespace should be treated as empty."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])
    (evidence_dir / "git_diff.patch").write_text("  \n  \n", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["diff_non_empty"] is False


# ---------------------------------------------------------------------------
# fail — extra events
# ---------------------------------------------------------------------------

def test_c3_fails_when_final_has_extra_events_in_run(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="step_dispatched"),  # extra
    ])
    (evidence_dir / "git_diff.patch").write_text("", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["status"] == "fail"
    assert result["detail"]["baseline_count"] == 1
    assert result["detail"]["final_count"] == 2
    mismatch = result["detail"]["mismatches"][0]
    assert mismatch["kind"] == "extra_events"
    assert mismatch["extra_count"] == 1


def test_c3_fails_when_final_has_extra_events_in_timeline(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_basic_event(idx=1, kind="timeline.created"),
        _make_basic_event(idx=2, kind="clip.added"),  # extra
    ])
    (evidence_dir / "git_diff.patch").write_text("", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["status"] == "fail"
    assert result["detail"]["baseline_count"] == 1
    assert result["detail"]["final_count"] == 3  # 1 run + 2 timeline
    mismatch = result["detail"]["mismatches"][0]
    assert mismatch["kind"] == "extra_events"
    assert mismatch["extra_count"] == 2


def test_c3_fails_when_final_has_extra_events_across_multiple_runs(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0), _make_basic_event(idx=1)])
    _write_run_events(evidence_dir, "run-2", [_make_basic_event(idx=2)])
    (evidence_dir / "git_diff.patch").write_text("", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["status"] == "fail"
    assert result["detail"]["baseline_count"] == 1
    assert result["detail"]["final_count"] == 3
    assert result["detail"]["mismatches"][0]["extra_count"] == 2


# ---------------------------------------------------------------------------
# fail — non-empty git diff
# ---------------------------------------------------------------------------

def test_c3_fails_when_git_diff_is_non_empty(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])
    (evidence_dir / "git_diff.patch").write_text(
        "diff --git a/file.txt b/file.txt\n"
        "+new line\n",
        encoding="utf-8",
    )

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["status"] == "fail"
    assert result["detail"]["diff_non_empty"] is True
    mismatch = result["detail"]["mismatches"][0]
    assert mismatch["kind"] == "non_empty_diff"


def test_c3_fails_with_both_extra_events_and_non_empty_diff(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="run_completed"),
    ])
    (evidence_dir / "git_diff.patch").write_text("+mutation\n", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["status"] == "fail"
    assert len(result["detail"]["mismatches"]) == 2
    kinds = {m["kind"] for m in result["detail"]["mismatches"]}
    assert kinds == {"extra_events", "non_empty_diff"}


# ---------------------------------------------------------------------------
# pass — baseline larger than final (events removed)
# ---------------------------------------------------------------------------

def test_c3_passes_when_final_has_fewer_events_than_baseline(tmp_path: Path) -> None:
    """Fewer events in final than baseline is not a read-mutation failure."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1),
        _make_basic_event(idx=2),
    ])
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0),
    ])
    (evidence_dir / "git_diff.patch").write_text("", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 3
    assert result["detail"]["final_count"] == 1


# ---------------------------------------------------------------------------
# edge cases
# ---------------------------------------------------------------------------

def test_c3_unparseable_baseline_events_fails(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    (evidence_dir / "baseline_events.jsonl").write_text("not valid json\n", encoding="utf-8")
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])
    (evidence_dir / "git_diff.patch").write_text("", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["status"] == "fail"
    assert "baseline_events.jsonl missing or unparseable" in result["detail"]["reason"]


def test_c3_handles_run_with_unparseable_events_gracefully(tmp_path: Path) -> None:
    """An unparseable run events.jsonl should be skipped (counted as 0 events)."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    runs_dir = evidence_dir / "runs" / "run-1"
    runs_dir.mkdir(parents=True)
    (runs_dir / "events.jsonl").write_text("invalid json\n", encoding="utf-8")
    (evidence_dir / "git_diff.patch").write_text("", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    # final_count is 0 (unparseable run skipped), baseline is 1 → pass
    assert result["status"] == "pass"
    assert result["detail"]["final_count"] == 0


def test_c3_evaluates_final_events_across_runs_and_timelines_independently(
    tmp_path: Path,
) -> None:
    """Missing events.jsonl in one run should not prevent reading others."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0), _make_basic_event(idx=1),
    ])
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])
    # run-2 dir exists but no events.jsonl
    (evidence_dir / "runs" / "run-2").mkdir(parents=True)
    (evidence_dir / "git_diff.patch").write_text("", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 2
    assert result["detail"]["final_count"] == 1


def test_c3_returns_evidence_refs_in_result(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])
    (evidence_dir / "git_diff.patch").write_text("", encoding="utf-8")

    result = c3_no_mutation_on_read(evidence_dir, trigger_record=_c3_enabled())

    assert len(result["evidence_refs"]) >= 3
    refs_set = set(result["evidence_refs"])
    assert "baseline_events.jsonl" in refs_set
    assert "runs/run-1/events.jsonl" in refs_set
    assert "git_diff.patch" in refs_set
