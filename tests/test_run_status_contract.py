"""Tests for the canonical RunStatus enum and its serialization boundaries."""

from __future__ import annotations

import pytest

from astrid.contracts.run_status import RunStatus
from astrid.core.reigh.task_client import ALLOWED_STATUSES


class TestEventKindMapping:
    def test_run_completed_maps_to_completed(self):
        events = [{"kind": "run_started"}, {"kind": "run_completed"}]
        assert RunStatus.from_run_events(events) is RunStatus.COMPLETED

    def test_run_failed_maps_to_failed(self):
        events = [{"kind": "run_started"}, {"kind": "run_failed"}]
        assert RunStatus.from_run_events(events) is RunStatus.FAILED

    def test_run_aborted_maps_to_aborted(self):
        events = [{"kind": "run_started"}, {"kind": "run_aborted"}]
        assert RunStatus.from_run_events(events) is RunStatus.ABORTED

    def test_run_started_no_terminal_maps_to_running(self):
        events = [{"kind": "run_started"}, {"kind": "step_dispatched"}]
        assert RunStatus.from_run_events(events) is RunStatus.RUNNING

    def test_empty_events_default_running(self):
        assert RunStatus.from_run_events([]) is RunStatus.RUNNING

    def test_gate_rejection_tail_maps_to_blocked(self):
        events = [
            {"kind": "run_started"},
            {"kind": "produces_check_failed"},
            {"kind": "cursor_rewind", "reason": "missing output"},
        ]
        assert RunStatus.from_run_events(events) is RunStatus.BLOCKED

    def test_iteration_failed_tail_maps_to_blocked(self):
        events = [{"kind": "run_started"}, {"kind": "iteration_failed"}]
        assert RunStatus.from_run_events(events) is RunStatus.BLOCKED

    def test_terminal_wins_over_blocked_tail(self):
        # A completed run that happened to rewind earlier is COMPLETED, not BLOCKED.
        events = [
            {"kind": "run_started"},
            {"kind": "cursor_rewind"},
            {"kind": "run_completed"},
        ]
        assert RunStatus.from_run_events(events) is RunStatus.COMPLETED

    def test_aborted_takes_precedence_over_completed(self):
        events = [{"kind": "run_completed"}, {"kind": "run_aborted"}]
        assert RunStatus.from_run_events(events) is RunStatus.ABORTED


class TestReighWireBoundaryRoundTrip:
    @pytest.mark.parametrize(
        "status",
        [RunStatus.RUNNING, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.ABORTED],
    )
    def test_status_to_wire_and_back(self, status):
        assert RunStatus.from_reigh_wire(status.to_reigh_wire()) is status

    @pytest.mark.parametrize(
        "wire", ["In Progress", "Complete", "Failed", "Cancelled"]
    )
    def test_wire_to_status_and_back(self, wire):
        assert RunStatus.from_reigh_wire(wire).to_reigh_wire() == wire

    def test_wire_tokens_are_title_case_and_accepted_by_reigh_client(self):
        for status in (RunStatus.RUNNING, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.ABORTED):
            assert status.to_reigh_wire() in ALLOWED_STATUSES

    def test_internal_only_statuses_have_no_wire_token(self):
        for status in (RunStatus.BLOCKED, RunStatus.SKIPPED):
            with pytest.raises(ValueError):
                status.to_reigh_wire()

    def test_unmapped_wire_token_rejected(self):
        with pytest.raises(ValueError):
            RunStatus.from_reigh_wire("Queued")
        with pytest.raises(ValueError):
            RunStatus.from_reigh_wire("complete")  # lowercase not accepted


class TestBlockedRepresentableEndToEnd:
    def test_blocked_is_a_canonical_member(self):
        assert RunStatus.BLOCKED.value == "blocked"
        assert RunStatus("blocked") is RunStatus.BLOCKED

    def test_blocked_derivable_from_events(self):
        events = [{"kind": "run_started"}, {"kind": "iteration_failed"}]
        assert RunStatus.from_run_events(events) is RunStatus.BLOCKED

    def test_run_audit_surface_reports_blocked(self):
        from astrid.core.task.run_audit import _run_status

        events = [{"kind": "run_started"}, {"kind": "cursor_rewind"}]
        assert _run_status(events) == "blocked"

    def test_run_audit_preserves_legacy_in_flight_spelling(self):
        from astrid.core.task.run_audit import _run_status

        assert _run_status([{"kind": "run_started"}]) == "in-flight"
        assert _run_status([{"kind": "run_completed"}]) == "completed"
        assert _run_status([{"kind": "run_aborted"}]) == "aborted"


class TestRunRecordBoundary:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("running", RunStatus.RUNNING),
            ("completed", RunStatus.COMPLETED),
            ("failed", RunStatus.FAILED),
            ("blocked", RunStatus.BLOCKED),
            ("aborted", RunStatus.ABORTED),
            ("skipped", RunStatus.SKIPPED),
            ("prepared", RunStatus.RUNNING),
            ("success", RunStatus.COMPLETED),
            ("succeeded", RunStatus.COMPLETED),
            ("error", RunStatus.FAILED),
            ("orphaned", RunStatus.FAILED),
        ],
    )
    def test_from_run_record_status_accepts_canonical_and_legacy_tokens(self, raw, expected):
        assert RunStatus.from_run_record_status(raw) is expected

    def test_run_record_boundary_serializes_canonically(self):
        assert RunStatus.from_run_record_status("prepared").value == "running"
        assert RunStatus.from_run_record_status("success").value == "completed"
        assert RunStatus.from_run_record_status("succeeded").value == "completed"
        assert RunStatus.from_run_record_status("error").value == "failed"
        assert RunStatus.from_run_record_status("orphaned").value == "failed"

    def test_unknown_run_record_status_rejected(self):
        with pytest.raises(ValueError):
            RunStatus.from_run_record_status("success-ish")


class TestProjectRecordBoundary:
    def test_project_record_status_tokens(self):
        assert RunStatus.COMPLETED.to_project_record_status() == "success"
        assert RunStatus.FAILED.to_project_record_status() == "failed"
        assert RunStatus.SKIPPED.to_project_record_status() == "skipped"

    def test_running_has_no_project_record_token(self):
        with pytest.raises(ValueError):
            RunStatus.RUNNING.to_project_record_status()
