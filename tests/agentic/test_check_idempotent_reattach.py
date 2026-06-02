from __future__ import annotations

import json
from pathlib import Path

from tests.agentic.checks.idempotent_reattach import s2_idempotent_reattach
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


def _write_reattach_stdout(evidence_dir: Path, content: str) -> Path:
    path = evidence_dir / "reattach_stdout.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_reattach_stderr(evidence_dir: Path, content: str) -> Path:
    path = evidence_dir / "reattach_stderr.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


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


def _s2_enabled() -> TriggerRecord:
    records = resolve_trigger_records(
        scenario_extras={
            "m2_checks": {
                "s2_idempotent_reattach": {"enabled": True},
            }
        }
    )
    return records["S2"]


def _s2_disabled() -> TriggerRecord:
    records = resolve_trigger_records()
    return records["S2"]


# ---------------------------------------------------------------------------
# na — trigger not declared
# ---------------------------------------------------------------------------


def test_s2_returns_na_when_trigger_not_declared(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_disabled())

    assert result["id"] == "S2"
    assert result["status"] == "na"
    assert result["detail"]["reason"] == "trigger not declared"


def test_s2_returns_fail_when_no_trigger_record_and_no_baseline(tmp_path: Path) -> None:
    """Without trigger_record, no gating happens, but missing baseline → fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = s2_idempotent_reattach(evidence_dir)

    assert result["id"] == "S2"
    assert result["status"] == "fail"
    assert "baseline_events.jsonl missing" in result["detail"]["reason"]


# ---------------------------------------------------------------------------
# fail — declared trigger missing required evidence
# ---------------------------------------------------------------------------


def test_s2_fails_when_baseline_events_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["id"] == "S2"
    assert result["status"] == "fail"
    assert result["detail"]["reason"] == "declared trigger missing required evidence"
    assert "baseline_events" in result["detail"]["missing_evidence"]


def test_s2_fails_when_final_events_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["id"] == "S2"
    assert result["status"] == "fail"
    assert result["detail"]["reason"] == "declared trigger missing required evidence"
    assert "final_events" in result["detail"]["missing_evidence"]


def test_s2_fails_when_reattach_diagnostics_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["id"] == "S2"
    assert result["status"] == "fail"
    assert result["detail"]["reason"] == "declared trigger missing required evidence"
    assert "reattach_diagnostics" in result["detail"]["missing_evidence"]


def test_s2_fails_when_all_evidence_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["id"] == "S2"
    assert result["status"] == "fail"
    assert result["detail"]["reason"] == "declared trigger missing required evidence"
    assert set(result["detail"]["missing_evidence"]) == {
        "baseline_events", "final_events", "reattach_diagnostics",
    }


# ---------------------------------------------------------------------------
# pass — stable reattach (idempotent)
# ---------------------------------------------------------------------------


def test_s2_passes_when_identical_events(tmp_path: Path) -> None:
    """Same events in baseline and final → pass."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    events = [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="plan_initialized"),
    ]
    _write_jsonl(evidence_dir / "baseline_events.jsonl", events)
    _write_run_events(evidence_dir, "run-1", events)
    _write_reattach_stdout(evidence_dir, "reattach successful\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["id"] == "S2"
    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 2
    assert result["detail"]["final_count"] == 2
    assert result["detail"]["issues"] == []


def test_s2_passes_when_final_has_extra_events(tmp_path: Path) -> None:
    """Extra events in final (reattach with new activity) → pass."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0),
    ])
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0),
        _make_basic_event(idx=1, kind="step_dispatched"),
        _make_basic_event(idx=2, kind="step_completed"),
    ])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 1
    assert result["detail"]["final_count"] == 3


def test_s2_passes_with_empty_baseline_and_final(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [])
    _write_run_events(evidence_dir, "run-1", [])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 0
    assert result["detail"]["final_count"] == 0


def test_s2_passes_with_stable_reattach_across_runs_and_timelines(tmp_path: Path) -> None:
    """Stable event IDs across multiple runs and timelines."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    # Baseline: 3 events (1 run, 2 timeline)
    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0),
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-0001", idx=1),
        _make_timeline_event(event_id="evt-002", kind="clip.added", hash_val="hash-0002", idx=2),
    ])
    # Final: same events across run and timeline
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0),
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-0001", idx=1),
        _make_timeline_event(event_id="evt-002", kind="clip.added", hash_val="hash-0002", idx=2),
    ])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 3
    assert result["detail"]["final_count"] == 3


def test_s2_passes_when_final_has_extra_timeline_events(tmp_path: Path) -> None:
    """Extra timeline events after reattach → pass."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-001", idx=0),
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-001", idx=0),
        _make_timeline_event(event_id="evt-002", kind="clip.added", hash_val="hash-002", idx=1),
    ])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["baseline_count"] == 1
    assert result["detail"]["final_count"] == 2


def test_s2_passes_with_reattach_stderr_only(tmp_path: Path) -> None:
    """Reattach diagnostics via stderr only (no stdout)."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    events = [_make_basic_event(idx=0)]
    _write_jsonl(evidence_dir / "baseline_events.jsonl", events)
    _write_run_events(evidence_dir, "run-1", events)
    _write_reattach_stderr(evidence_dir, "reattach completed (stderr)\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# fail — duplicate events detected
# ---------------------------------------------------------------------------


def test_s2_fails_when_duplicate_timeline_event(tmp_path: Path) -> None:
    """Same event_id appears twice in final timeline → duplicate → fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-001", idx=0),
    ])
    # Final has duplicate event_id
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-001", idx=0),
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-001", idx=1),  # duplicate
    ])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "fail"
    issues = result["detail"]["issues"]
    dupes = [i for i in issues if i["kind"] == "duplicate_event"]
    assert len(dupes) >= 1
    assert dupes[0]["identity"] == "id:evt-001"


def test_s2_fails_when_duplicate_task_event(tmp_path: Path) -> None:
    """Same kind+hash appears twice in final run → duplicate → fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0, kind="run_started"),
    ])
    # Final has duplicate (same kind + hash)
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0, kind="run_started"),
        _make_basic_event(idx=0, kind="run_started"),  # duplicate
    ])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "fail"
    issues = result["detail"]["issues"]
    dupes = [i for i in issues if i["kind"] == "duplicate_event"]
    assert len(dupes) >= 1


def test_s2_fails_when_multiple_duplicates(tmp_path: Path) -> None:
    """Multiple duplicate events in final stream → fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-001", idx=0),
        _make_timeline_event(event_id="evt-002", kind="clip.added", hash_val="hash-002", idx=1),
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-001", idx=0),
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-001", idx=1),  # duplicate
        _make_timeline_event(event_id="evt-002", kind="clip.added", hash_val="hash-002", idx=2),
        _make_timeline_event(event_id="evt-002", kind="clip.added", hash_val="hash-002", idx=3),  # duplicate
    ])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "fail"
    dupes = [i for i in result["detail"]["issues"] if i["kind"] == "duplicate_event"]
    assert len(dupes) >= 2


# ---------------------------------------------------------------------------
# fail — missing baseline events
# ---------------------------------------------------------------------------


def test_s2_fails_when_baseline_timeline_event_missing_from_final(tmp_path: Path) -> None:
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
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "fail"
    missing = [i for i in result["detail"]["issues"] if i["kind"] == "missing_event"]
    assert len(missing) >= 1
    assert missing[0]["identity"] == "id:evt-002"


def test_s2_fails_when_baseline_task_event_missing_from_final(tmp_path: Path) -> None:
    """Task event in baseline not found in final → fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0, kind="run_started"),
        _make_basic_event(idx=1, kind="plan_initialized"),
    ])
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0, kind="run_started"),
        # plan_initialized is missing
    ])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "fail"
    missing = [i for i in result["detail"]["issues"] if i["kind"] == "missing_event"]
    assert len(missing) >= 1


# ---------------------------------------------------------------------------
# fail — hash changed (same identity, different hash)
# ---------------------------------------------------------------------------


def test_s2_fails_when_timeline_event_hash_changes(tmp_path: Path) -> None:
    """Same event_id, different hash → fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-original", idx=0),
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-rewritten", idx=0),
    ])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "fail"
    hash_issues = [i for i in result["detail"]["issues"] if i["kind"] == "hash_changed"]
    assert len(hash_issues) >= 1
    assert hash_issues[0]["identity"] == "id:evt-001"
    assert hash_issues[0]["baseline_hash"] == "hash-original"
    assert hash_issues[0]["final_hash"] == "hash-rewritten"


def test_s2_fails_when_task_event_hash_changes(tmp_path: Path) -> None:
    """Same kind, different hash → identity changes, so this appears as missing+unexpected."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0, kind="run_started"),
    ])
    _write_run_events(evidence_dir, "run-1", [
        {"kind": "run_started", "ts": "2025-01-01T00:01:40Z", "run_id": "run-1", "hash": "hash-changed"},
    ])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    # When the hash changes, the kind:hash identity changes, so we get
    # missing_event (baseline identity not in final).  Extra events after
    # reattach are legitimate, so the new identity is not flagged.
    assert result["status"] == "fail"
    issue_kinds = {i["kind"] for i in result["detail"]["issues"]}
    assert "missing_event" in issue_kinds


# ---------------------------------------------------------------------------
# fail — mixed issues
# ---------------------------------------------------------------------------


def test_s2_fails_with_mixed_issues(tmp_path: Path) -> None:
    """Multiple kinds of issues in one check: duplicate + missing + hash change."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [
        _make_basic_event(idx=0, kind="run_started"),
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-original", idx=1),
        _make_timeline_event(event_id="evt-002", kind="clip.added", hash_val="hash-002", idx=2),
    ])
    _write_run_events(evidence_dir, "run-1", [
        _make_basic_event(idx=0, kind="run_started"),
    ])
    _write_timeline_assembly(evidence_dir, "tl-1", [
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-rewritten", idx=1),  # hash changed
        _make_timeline_event(event_id="evt-001", kind="timeline.created", hash_val="hash-rewritten", idx=2),  # duplicate
        # evt-002 is missing
    ])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "fail"
    issue_kinds = {i["kind"] for i in result["detail"]["issues"]}
    assert "duplicate_event" in issue_kinds
    assert "missing_event" in issue_kinds
    assert "hash_changed" in issue_kinds


# ---------------------------------------------------------------------------
# edge cases
# ---------------------------------------------------------------------------


def test_s2_handles_unparseable_baseline(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    (evidence_dir / "baseline_events.jsonl").write_text("not valid json\n", encoding="utf-8")
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "fail"
    assert "baseline_events.jsonl missing or unparseable" in result["detail"]["reason"]


def test_s2_handles_run_with_unparseable_events_gracefully(tmp_path: Path) -> None:
    """An unparseable run events.jsonl should be skipped."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    runs_dir = evidence_dir / "runs" / "run-1"
    runs_dir.mkdir(parents=True)
    (runs_dir / "events.jsonl").write_text("invalid json\n", encoding="utf-8")
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    # Unparseable run → 0 final events, baseline has 1 → missing_event → fail
    assert result["status"] == "fail"
    missing = [i for i in result["detail"]["issues"] if i["kind"] == "missing_event"]
    assert len(missing) >= 1


def test_s2_returns_evidence_refs(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_jsonl(evidence_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_run_events(evidence_dir, "run-1", [_make_basic_event(idx=0)])
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert len(result["evidence_refs"]) >= 3
    refs_set = set(result["evidence_refs"])
    assert "baseline_events.jsonl" in refs_set
    assert "runs/run-1/events.jsonl" in refs_set
    # reattach stdout ref should be present
    assert any("reattach_stdout" in r for r in refs_set)


def test_s2_passes_with_reattach_stdout_log(tmp_path: Path) -> None:
    """Reattach diagnostics via .log extension."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    events = [_make_basic_event(idx=0)]
    _write_jsonl(evidence_dir / "baseline_events.jsonl", events)
    _write_run_events(evidence_dir, "run-1", events)

    stdout_log = evidence_dir / "reattach_stdout.log"
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    stdout_log.write_text("reattach log output\n", encoding="utf-8")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "pass"


def test_s2_diagnostics_summary_includes_stdout_stderr(tmp_path: Path) -> None:
    """Result detail includes diagnostics summary."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    events = [_make_basic_event(idx=0)]
    _write_jsonl(evidence_dir / "baseline_events.jsonl", events)
    _write_run_events(evidence_dir, "run-1", events)
    _write_reattach_stdout(evidence_dir, "stdout: reattach succeeded\n")
    _write_reattach_stderr(evidence_dir, "stderr: no warnings\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    assert result["status"] == "pass"
    assert result["detail"]["diagnostics"]["stdout"] is not None
    assert result["detail"]["diagnostics"]["stderr"] is not None
    assert "reattach succeeded" in result["detail"]["diagnostics"]["stdout"]
    assert "no warnings" in result["detail"]["diagnostics"]["stderr"]


def test_s2_passes_when_final_has_fewer_events(tmp_path: Path) -> None:
    """If final has fewer events than baseline, should fail because events are missing."""
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
    _write_reattach_stdout(evidence_dir, "reattach ok\n")

    result = s2_idempotent_reattach(evidence_dir, trigger_record=_s2_enabled())

    # Fewer events → fail
    assert result["status"] == "fail"
    missing = [i for i in result["detail"]["issues"] if i["kind"] == "missing_event"]
    assert len(missing) >= 1
