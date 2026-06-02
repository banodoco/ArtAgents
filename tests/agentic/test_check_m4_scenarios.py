from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.agentic.checks.m4_scenarios import (
    M4_CHECK_SPECS,
    artifact_pipeline_provenance_handoff,
    durability_after_crash_head_jsonl_desync_detected,
    orchestrator_run_persists_terminal_success,
    resolve_m4_check_records,
    taskrun_concurrent_lease_single_writer_lease,
    timeline_compose_edit_composite_projection,
    timeline_concurrent_version_conflict_stale_version_conflict,
    timeline_large_audit_large_chain_verified,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_m4_check_specs_are_stable_and_unique() -> None:
    stable_ids = [stable_id for stable_id, _trigger_key, _fn_name in M4_CHECK_SPECS]
    trigger_keys = [trigger_key for _stable_id, trigger_key, _fn_name in M4_CHECK_SPECS]
    function_names = [fn_name for _stable_id, _trigger_key, fn_name in M4_CHECK_SPECS]

    assert len(M4_CHECK_SPECS) == 7
    assert len(set(stable_ids)) == len(stable_ids)
    assert len(set(trigger_keys)) == len(trigger_keys)
    assert len(set(function_names)) == len(function_names)


def test_m4_trigger_resolution_prefers_scenario_extras_over_manifest() -> None:
    records = resolve_m4_check_records(
        scenario_extras={
            "m4_checks": {
                "orchestrator_run_persists": {"enabled": True, "note": "extras"},
            }
        },
        manifest={
            "m4_checks": {
                "orchestrator_run_persists": {"enabled": False},
                "artifact_pipeline": {"enabled": True},
            }
        },
    )

    assert records["m4.orchestrator_run_persists.terminal_success"].enabled is True
    assert records["m4.orchestrator_run_persists.terminal_success"].source == "scenario_extras"
    assert records["m4.orchestrator_run_persists.terminal_success"].config == {
        "enabled": True,
        "note": "extras",
    }
    assert records["m4.artifact_pipeline.provenance_handoff"].enabled is False
    assert records["m4.artifact_pipeline.provenance_handoff"].source == "absent"


def test_m4_trigger_resolution_falls_back_to_manifest_when_extras_missing() -> None:
    records = resolve_m4_check_records(
        scenario_extras={"project_slug": "m4-only"},
        manifest={"m4_checks": {"artifact_pipeline": {"enabled": True, "mode": "frozen"}}},
    )

    assert records["m4.artifact_pipeline.provenance_handoff"].enabled is True
    assert records["m4.artifact_pipeline.provenance_handoff"].source == "manifest"
    assert records["m4.artifact_pipeline.provenance_handoff"].config == {
        "enabled": True,
        "mode": "frozen",
    }


def test_absent_m4_trigger_returns_na(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "m4-na"
    evidence_dir.mkdir()
    records = resolve_m4_check_records()

    result = orchestrator_run_persists_terminal_success(
        evidence_dir,
        trigger_record=records["m4.orchestrator_run_persists.terminal_success"],
    )

    assert result == {
        "id": "m4.orchestrator_run_persists.terminal_success",
        "status": "na",
        "evidence_refs": [],
        "detail": {
            "reason": "trigger not declared",
            "trigger_key": "orchestrator_run_persists",
        },
    }


@pytest.mark.parametrize(
    ("stable_id", "fn", "trigger_key", "setup"),
    [
        (
            "m4.orchestrator_run_persists.terminal_success",
            orchestrator_run_persists_terminal_success,
            "orchestrator_run_persists",
            lambda root: (
                _write_json(
                    root / "m4" / "orchestrator_run_persists.json",
                    {
                        "terminal_status": "success",
                        "run_json_status": "success",
                        "artifacts_match_cas": True,
                        "produces_event_count": 1,
                        "artifact_count": 1,
                    },
                ),
                _write_jsonl(root / "runs" / "run-1" / "events.jsonl", [{"kind": "project_run_finalized"}]),
                _write_json(root / "runs" / "run-1" / "run.json", {"status": "success"}),
            ),
        ),
        (
            "m4.artifact_pipeline.provenance_handoff",
            artifact_pipeline_provenance_handoff,
            "artifact_pipeline",
            lambda root: (
                _write_json(
                    root / "m4" / "artifact_pipeline.json",
                    {
                        "upstream_artifact_sha256": "abc123",
                        "downstream_input_sha256": "abc123",
                        "handoff_matches": True,
                        "matched_provenance": True,
                        "orphan_artifacts": [],
                    },
                ),
                _write_jsonl(root / "runs" / "run-a" / "events.jsonl", [{"kind": "produces_check_passed"}]),
            ),
        ),
        (
            "m4.timeline_compose_edit.composite_projection",
            timeline_compose_edit_composite_projection,
            "timeline_compose_edit",
            lambda root: (
                _write_json(
                    root / "m4" / "timeline_compose_edit.json",
                    {
                        "verify_chain_ok": True,
                        "head_consistency_ok": True,
                        "projection_fidelity_ok": True,
                        "features_present": [
                            "track",
                            "clip",
                            "audio_bind",
                            "transition",
                            "effect",
                            "theme",
                        ],
                    },
                ),
                _write_jsonl(root / "timelines" / "tl-1" / "assembly.jsonl", [{"kind": "timeline_event"}]),
                _write_json(root / "timelines" / "tl-1" / "assembly.json", {"tracks": []}),
            ),
        ),
        (
            "m4.timeline_concurrent_version_conflict.stale_version_conflict",
            timeline_concurrent_version_conflict_stale_version_conflict,
            "timeline_concurrent_version_conflict",
            lambda root: (
                _write_json(
                    root / "m4" / "timeline_concurrent_version_conflict.json",
                    {
                        "loser_error": "EventLogStaleVersionError",
                        "winner_appended": True,
                        "verify_chain_ok": True,
                        "mechanism": "expected_version_conflict",
                        "mentions_lease": False,
                    },
                ),
                _write_jsonl(root / "timelines" / "tl-2" / "assembly.jsonl", [{"kind": "timeline_event"}]),
            ),
        ),
        (
            "m4.taskrun_concurrent_lease.single_writer_lease",
            taskrun_concurrent_lease_single_writer_lease,
            "taskrun_concurrent_lease",
            lambda root: (
                _write_json(
                    root / "m4" / "taskrun_concurrent_lease.json",
                    {
                        "rejection_error": "StaleEpochError",
                        "writer_count": 1,
                        "verify_chain_ok": True,
                        "lease_file_present": True,
                    },
                ),
                _write_jsonl(root / "runs" / "run-lease" / "events.jsonl", [{"kind": "task_event"}]),
                _write_json(root / "runs" / "run-lease" / "lease.json", {"epoch": 2}),
            ),
        ),
        (
            "m4.durability_after_crash.head_jsonl_desync_detected",
            durability_after_crash_head_jsonl_desync_detected,
            "durability_after_crash",
            lambda root: (
                _write_json(
                    root / "m4" / "durability_after_crash.json",
                    {
                        "detection_ok": True,
                        "mismatch_kind": "head_vs_jsonl_desync",
                        "served_stale_state": False,
                    },
                ),
                _write_json(root / "m4" / "desync" / "assembly.head.json", {"event_count": 1}),
                _write_jsonl(root / "m4" / "desync" / "assembly.jsonl", [{"kind": "timeline_event"}]),
            ),
        ),
        (
            "m4.timeline_large_audit.large_chain_verified",
            timeline_large_audit_large_chain_verified,
            "timeline_large_audit",
            lambda root: (
                _write_json(
                    root / "m4" / "timeline_large_audit.json",
                    {
                        "event_count": 500,
                        "verify_chain_ok": True,
                        "within_budget": True,
                    },
                ),
                _write_jsonl(root / "timelines" / "tl-large" / "assembly.jsonl", [{"kind": "timeline_event"}]),
            ),
        ),
    ],
)
def test_each_m4_check_returns_pass_for_matching_frozen_evidence(
    tmp_path: Path,
    stable_id: str,
    fn,
    trigger_key: str,
    setup,
) -> None:
    evidence_dir = tmp_path / trigger_key
    setup(evidence_dir)
    records = resolve_m4_check_records(
        scenario_extras={"m4_checks": {trigger_key: {"enabled": True}}}
    )

    result = fn(evidence_dir, trigger_record=records[stable_id])

    assert result["id"] == stable_id
    assert result["status"] == "pass"
    assert result["detail"]["mismatches"] == []
