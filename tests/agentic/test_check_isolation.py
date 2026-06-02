from __future__ import annotations

import json
from pathlib import Path

from tests.agentic.checks.isolation import u4_no_cross_project_leak, u5_auditability


# ---------------------------------------------------------------------------
# U4 — No-cross-project-leak
# ---------------------------------------------------------------------------


def _write_run_json(evidence_dir: Path, run_id: str, project_slug: str) -> None:
    run_dir = evidence_dir / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps({"project_slug": project_slug, "run_id": run_id}), encoding="utf-8"
    )
    # Also write a minimal events.jsonl so the run dir is complete
    (run_dir / "events.jsonl").write_text(
        json.dumps({"kind": "run_started", "run_id": run_id, "ts": "2025-01-01T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )


def test_u4_na_when_no_run_json(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = u4_no_cross_project_leak(evidence_dir)

    assert result["id"] == "U4"
    assert result["status"] == "na"
    assert "no run.json" in result["detail"]["reason"]


def test_u4_na_when_run_json_has_no_project_slug(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": "run-1", "status": "success"}), encoding="utf-8"
    )

    result = u4_no_cross_project_leak(evidence_dir)

    assert result["id"] == "U4"
    assert result["status"] == "na"


def test_u4_pass_when_single_run_consistent_slug(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_run_json(evidence_dir, "run-1", "my-project")

    result = u4_no_cross_project_leak(evidence_dir)

    assert result["id"] == "U4"
    assert result["status"] == "pass"
    assert result["detail"]["expected_slug"] == "my-project"
    assert result["detail"]["checked_runs"] == 1


def test_u4_pass_when_multiple_runs_same_slug(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_run_json(evidence_dir, "run-1", "shared-project")
    _write_run_json(evidence_dir, "run-2", "shared-project")

    result = u4_no_cross_project_leak(evidence_dir)

    assert result["id"] == "U4"
    assert result["status"] == "pass"
    assert result["detail"]["expected_slug"] == "shared-project"
    assert result["detail"]["checked_runs"] == 2


def test_u4_fail_for_slug_mismatch_across_runs(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_run_json(evidence_dir, "run-1", "project-a")
    _write_run_json(evidence_dir, "run-2", "project-b")

    result = u4_no_cross_project_leak(evidence_dir)

    assert result["id"] == "U4"
    assert result["status"] == "fail"
    assert "inconsistent project_slug" in result["detail"]["reason"]
    assert set(result["detail"]["unique_slugs"]) == {"project-a", "project-b"}
    assert result["detail"]["slugs_by_run"]["run-1"] == "project-a"
    assert result["detail"]["slugs_by_run"]["run-2"] == "project-b"


def test_u4_fail_for_sibling_slug_in_event_project_slug_field(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_run_json(evidence_dir, "run-1", "expected-project")

    # Add an event with an explicit project_slug field that differs
    run_dir = evidence_dir / "runs" / "run-2"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps({"project_slug": "expected-project", "run_id": "run-2"}), encoding="utf-8"
    )
    (run_dir / "events.jsonl").write_text(
        json.dumps({
            "kind": "run_started",
            "run_id": "run-2",
            "project_slug": "other-project",
            "ts": "2025-01-01T00:00:00Z",
        }) + "\n",
        encoding="utf-8",
    )

    result = u4_no_cross_project_leak(evidence_dir)

    assert result["id"] == "U4"
    assert result["status"] == "fail"
    assert "sibling-slug" in result["detail"]["reason"]
    assert len(result["detail"]["findings"]) >= 1
    assert any(f["found_slug"] == "other-project" for f in result["detail"]["findings"])


def test_u4_pass_with_clean_events(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_run_json(evidence_dir, "run-1", "clean-project")

    # Events with no cross-project references
    run_dir = evidence_dir / "runs" / "run-1"
    (run_dir / "events.jsonl").write_text(
        json.dumps({"kind": "run_started", "run_id": "run-1", "ts": "2025-01-01T00:00:00Z"}) + "\n"
        + json.dumps({"kind": "step_dispatched", "plan_step_path": ["build"], "command": "make", "ts": "2025-01-01T00:00:01Z"}) + "\n"
        + json.dumps({"kind": "run_completed", "run_id": "run-1", "ts": "2025-01-01T00:00:02Z"}) + "\n",
        encoding="utf-8",
    )

    result = u4_no_cross_project_leak(evidence_dir)

    assert result["id"] == "U4"
    assert result["status"] == "pass"


def test_u4_ignores_session_and_reason_fields_that_look_slug_like(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_run_json(evidence_dir, "run-1", "clean-project")

    run_dir = evidence_dir / "runs" / "run-1"
    (run_dir / "events.jsonl").write_text(
        json.dumps({
            "kind": "takeover",
            "project_slug": "clean-project",
            "new_session": "writer-b",
            "prev_session": "writer-a",
            "reason": "agentic-m4-concurrent-lease",
            "ts": "2025-01-01T00:00:00Z",
        }) + "\n",
        encoding="utf-8",
    )

    result = u4_no_cross_project_leak(evidence_dir)

    assert result["id"] == "U4"
    assert result["status"] == "pass"


def test_u4_includes_timeline_events_in_sibling_scan(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_run_json(evidence_dir, "run-1", "my-pack")

    # Add timeline events with a sibling slug reference
    timeline_dir = evidence_dir / "timelines" / "tl-1"
    timeline_dir.mkdir(parents=True)
    (timeline_dir / "assembly.jsonl").write_text(
        json.dumps({
            "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "timeline_id": "00000000-0000-0000-0000-000000000001",
            "ts": "2025-01-01T00:00:00Z",
            "actor": {"type": "agent", "id": "test-agent"},
            "kind": "timeline.created",
            "project_slug": "other-pack",
            "payload": {"timeline_id": "00000000-0000-0000-0000-000000000001", "slug": "test", "name": "Test"},
        }) + "\n",
        encoding="utf-8",
    )

    result = u4_no_cross_project_leak(evidence_dir)

    # Should find the sibling slug reference in the timeline event
    assert result["id"] == "U4"
    assert result["status"] == "fail"
    assert any("timelines" in f["source"] for f in result["detail"]["findings"])


# ---------------------------------------------------------------------------
# U5 — Auditability
# ---------------------------------------------------------------------------


def _write_task_event(run_dir: Path, event: dict) -> None:
    """Append a task event JSONL line to a run directory."""
    events_path = run_dir / "events.jsonl"
    existing = ""
    if events_path.exists():
        existing = events_path.read_text(encoding="utf-8")
    events_path.write_text(existing + json.dumps(event) + "\n", encoding="utf-8")


def _write_timeline_event(timeline_dir: Path, event: dict) -> None:
    """Append a timeline event JSONL line to a timeline directory."""
    assembly_path = timeline_dir / "assembly.jsonl"
    existing = ""
    if assembly_path.exists():
        existing = assembly_path.read_text(encoding="utf-8")
    assembly_path.write_text(existing + json.dumps(event) + "\n", encoding="utf-8")


def _make_timeline_event(
    event_id: str,
    kind: str,
    *,
    ts: str = "2025-01-01T00:00:00Z",
    actor: dict | None = None,
    payload: dict | None = None,
    timeline_id: str = "00000000-0000-0000-0000-000000000001",
) -> dict:
    return {
        "event_id": event_id,
        "timeline_id": timeline_id,
        "ts": ts,
        "actor": actor or {"type": "agent", "id": "test-agent"},
        "kind": kind,
        "payload": payload or {},
    }


def test_u5_na_when_no_events(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "na"
    assert "no events" in result["detail"]["reason"]


def test_u5_pass_for_valid_task_events(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    _write_task_event(run_dir, {
        "kind": "plan_initialized",
        "run_id": "run-1",
        "plan": {"steps": []},
        "plan_hash": "sha256:abc",
        "ts": "2025-01-01T00:00:00Z",
    })
    _write_task_event(run_dir, {
        "kind": "run_started",
        "run_id": "run-1",
        "plan_hash": "sha256:abc",
        "started_by": "human:alice",
        "ts": "2025-01-01T00:00:01Z",
    })
    _write_task_event(run_dir, {
        "kind": "step_dispatched",
        "command": "make",
        "plan_step_path": ["build"],
        "ts": "2025-01-01T00:00:02Z",
    })
    _write_task_event(run_dir, {
        "kind": "step_completed",
        "plan_step_path": ["build"],
        "returncode": 0,
        "ts": "2025-01-01T00:00:03Z",
    })
    _write_task_event(run_dir, {
        "kind": "run_completed",
        "run_id": "run-1",
        "ts": "2025-01-01T00:00:04Z",
    })

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "pass"
    assert result["detail"]["total_events"] == 5
    assert result["detail"]["issues_count"] == 0


def test_u5_fail_for_missing_timestamp(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    _write_task_event(run_dir, {
        "kind": "run_completed",
        "run_id": "run-1",
        # missing ts
    })

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "fail"
    assert result["detail"]["issues_count"] == 1
    assert "timestamp" in result["detail"]["issues"][0]["issue"]


def test_u5_fail_for_invalid_timestamp(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    _write_task_event(run_dir, {
        "kind": "run_completed",
        "run_id": "run-1",
        "ts": "not-a-timestamp",
    })

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "fail"
    assert "timestamp" in result["detail"]["issues"][0]["issue"]


def test_u5_pass_for_step_skipped_with_reason(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    _write_task_event(run_dir, {
        "kind": "step_skipped",
        "plan_step_path": ["optional_step"],
        "skipped_by": "human:bob",
        "skipped_by_id": "bob",
        "skipped_by_kind": "human",
        "ts": "2025-01-01T00:00:00Z",
        "reason": "Not needed for this run",
    })

    result = u5_auditability(evidence_dir)

    # step_skipped has reason and proper actor — should pass
    assert result["id"] == "U5"
    assert result["status"] == "pass"


def test_u5_fail_for_mutation_event_missing_reason(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    _write_task_event(run_dir, {
        "kind": "run_aborted",
        "run_id": "run-1",
        "ts": "2025-01-01T00:00:00Z",
        # missing reason
    })

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "fail"
    assert "reason" in result["detail"]["issues"][0]["issue"]


def test_u5_fail_for_empty_reason_on_mutation_event(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    _write_task_event(run_dir, {
        "kind": "cursor_rewind",
        "plan_step_path": ["build"],
        "reason": "   ",
        "ts": "2025-01-01T00:00:00Z",
    })

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "fail"
    assert "reason" in result["detail"]["issues"][0]["issue"]


def test_u5_pass_for_valid_timeline_events(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    timeline_dir = evidence_dir / "timelines" / "tl-1"
    timeline_dir.mkdir(parents=True)

    _write_timeline_event(timeline_dir, _make_timeline_event(
        "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "timeline.created",
        payload={"timeline_id": "00000000-0000-0000-0000-000000000001", "slug": "test", "name": "Test"},
    ))
    _write_timeline_event(timeline_dir, _make_timeline_event(
        "01ARZ3NDEKTSV4RRFFQ69G5FBW",
        "clip.added",
        payload={"clip_id": "c1", "asset": {"file": "/tmp/test.mp4"}},
    ))

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "pass"
    assert result["detail"]["total_events"] == 2


def test_u5_fail_for_timeline_event_missing_actor(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    timeline_dir = evidence_dir / "timelines" / "tl-1"
    timeline_dir.mkdir(parents=True)

    _write_timeline_event(timeline_dir, _make_timeline_event(
        "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "clip.added",
        actor={"type": "invalid_kind", "id": ""},  # bad actor type, empty id
    ))

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "fail"
    issues = result["detail"]["issues"]
    assert len(issues) >= 1
    # Should flag both actor.type and actor.id issues
    issue_texts = " ".join(i["issue"] for i in issues)
    assert "actor" in issue_texts.lower()


def test_u5_fail_for_timeline_mutation_missing_reason(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    timeline_dir = evidence_dir / "timelines" / "tl-1"
    timeline_dir.mkdir(parents=True)

    _write_timeline_event(timeline_dir, _make_timeline_event(
        "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "timeline.erased",
        payload={"selector_summary": {}, "affected_count": 1},  # missing reason
    ))

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "fail"
    assert "reason" in result["detail"]["issues"][0]["issue"]


def test_u5_pass_for_timeline_mutation_with_reason(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    timeline_dir = evidence_dir / "timelines" / "tl-1"
    timeline_dir.mkdir(parents=True)

    _write_timeline_event(timeline_dir, _make_timeline_event(
        "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "timeline.tombstoned",
        payload={"reason": "Deprecated by project policy"},
    ))

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "pass"


def test_u5_fail_for_erased_event_payload_missing_reason(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    timeline_dir = evidence_dir / "timelines" / "tl-1"
    timeline_dir.mkdir(parents=True)

    # An event whose payload has been replaced with ErasedPayload but missing reason
    _write_timeline_event(timeline_dir, {
        "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "timeline_id": "00000000-0000-0000-0000-000000000001",
        "ts": "2025-01-01T00:00:00Z",
        "actor": {"type": "agent", "id": "test-agent"},
        "kind": "clip.added",
        "payload": {
            "erased": True,
            # missing reason, erased_at, erased_by
        },
    })

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "fail"
    assert any("erased" in i["issue"] for i in result["detail"]["issues"])


def test_u5_combines_task_and_timeline_issues(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    # Task event with issue
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    _write_task_event(run_dir, {
        "kind": "run_aborted",
        "run_id": "run-1",
        "ts": "2025-01-01T00:00:00Z",
        # missing reason
    })

    # Timeline event with issue
    timeline_dir = evidence_dir / "timelines" / "tl-1"
    timeline_dir.mkdir(parents=True)
    _write_timeline_event(timeline_dir, _make_timeline_event(
        "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "timeline.erased",
        payload={},  # missing reason
    ))

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "fail"
    # Should have issues from both task and timeline events
    assert result["detail"]["issues_count"] >= 2
    assert result["detail"]["total_events"] == 2


def test_u5_accepts_iso_timestamp_variations(tmp_path: Path) -> None:
    """Verify U5 accepts common ISO-8601 timestamp variations."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    for ts in (
        "2025-01-01T00:00:00Z",
        "2025-01-01T00:00:00+00:00",
        "2025-01-01T00:00:00.123456Z",
        "2025-01-01 00:00:00",
        "2025-06-15T12:30:45.999999+05:30",
    ):
        _write_task_event(run_dir, {
            "kind": "run_completed",
            "run_id": f"run-{ts[:10]}",
            "ts": ts,
        })

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "pass"
    assert result["detail"]["total_events"] == 5
    assert result["detail"]["issues_count"] == 0


def test_u5_accepts_space_separated_iso_timestamp(tmp_path: Path) -> None:
    """U5 should accept space-separated ISO timestamps (common in Python)."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    _write_task_event(run_dir, {
        "kind": "run_completed",
        "run_id": "run-1",
        "ts": "2025-01-01 00:00:00",
    })

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "pass"


def test_u5_pass_for_step_failed_with_reason(tmp_path: Path) -> None:
    """step_failed is a mutation event — should have reason."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    _write_task_event(run_dir, {
        "kind": "step_failed",
        "plan_step_path": ["build"],
        "returncode": 1,
        "reason": "Compilation failed",
        "ts": "2025-01-01T00:00:00Z",
    })

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "pass"


def test_u5_fail_for_step_failed_missing_reason(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    _write_task_event(run_dir, {
        "kind": "step_failed",
        "plan_step_path": ["build"],
        "returncode": 1,
        "ts": "2025-01-01T00:00:00Z",
        # missing reason
    })

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "fail"
    assert "reason" in result["detail"]["issues"][0]["issue"]


def test_u5_fail_for_iteration_failed_missing_reason(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    _write_task_event(run_dir, {
        "kind": "iteration_failed",
        "plan_step_path": ["loop_step"],
        "iteration": 1,
        "ts": "2025-01-01T00:00:00Z",
        # missing reason
    })

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "fail"
    assert "reason" in result["detail"]["issues"][0]["issue"]


def test_u5_pass_for_non_mutation_event_without_reason(tmp_path: Path) -> None:
    """Non-mutation events like step_completed don't need a reason."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    _write_task_event(run_dir, {
        "kind": "step_completed",
        "plan_step_path": ["build"],
        "returncode": 0,
        "ts": "2025-01-01T00:00:00Z",
        # no reason — fine, it's not a mutation event
    })

    result = u5_auditability(evidence_dir)

    assert result["id"] == "U5"
    assert result["status"] == "pass"
