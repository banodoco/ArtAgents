"""Behavioral tests for the claim → work → release loop in BanodocoWorker.

Uses a fake claim backend to exercise all loop branches without real network
calls.  Verifies T1's baseline-snapshot-failure wrapper is wired into the loop.

Branches covered:
  - retry: transport error on claim_next_task → worker logs warning and retries
  - no-work-available: claim_next_task returns None → worker idles
  - lost-claim: claim received but _fail is called (status update fails → logged)
  - baseline-snapshot-failure → _fail (verifies T1's try/except wrapper at :404-417)
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

from astrid.core.integrations.reigh.task_client import ClaimResult
from astrid.core.integrations.reigh.worker_jwt import VerifiedJwt
from astrid.core.integrations.worker import banodoco_worker as bw_mod
from astrid.core.integrations.worker.banodoco_worker import BanodocoWorker, WorkerConfig


class _FakeProvider:
    """Minimal SupabaseDataProvider stand-in that avoids env-var resolution."""

    supabase_url: str = "https://fake.supabase.co"
    timeout: float = 10.0

    def load_timeline(self, project_id, timeline_id):
        return ({"theme": "t", "tracks": [], "clips": []}, 1)


def _make_claim(
    task_id: str = "task-001",
    task_type: str = "banodoco_timeline_generate",
    timeline_id: str = "tl-abc",
    correlation_id: str = "corr-001",
) -> ClaimResult:
    return ClaimResult(
        task_id=task_id,
        run_id=f"run-{task_id}",
        project_id="proj-123",
        task_type=task_type,
        user_jwt="test-jwt",
        params={
            "timeline_id": timeline_id,
            "correlation_id": correlation_id,
            "intent": "passthrough",
            "current_timeline": {"theme": "t", "tracks": [], "clips": []},
        },
        raw={},
    )


class _StatusRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, task_id, *, status, service_role_key, result_data=None, error=None, **_):
        self.calls.append(
            {
                "task_id": task_id,
                "status": status,
                "result_data": dict(result_data or {}),
                "error": error,
            }
        )


_VERIFIED_JWT = VerifiedJwt(
    user_id="user-1",
    audience="authenticated",
    raw_claims={"sub": "user-1"},
)


def _common_patches(recorder: _StatusRecorder):
    return [
        patch("astrid.core.integrations.worker.banodoco_worker.time.sleep"),
        patch("astrid.core.integrations.reigh.env.resolve_service_role_key", return_value="srv-key"),
        patch.object(bw_mod, "update_task_status", side_effect=recorder),
        patch.object(bw_mod, "verify_user_jwt", return_value=_VERIFIED_JWT),
        patch.object(bw_mod, "_verify_project_ownership", return_value=None),
        patch.object(
            bw_mod,
            "_write_baseline_snapshot",
            return_value="abc123",
        ),
    ]


class TestRetryOnTransportError:
    """claim_next_task raises → worker logs warning and retries on next iteration."""

    def test_transport_error_retried_then_exits(self, caplog) -> None:
        recorder = _StatusRecorder()
        transport_error = RuntimeError("connection refused")

        call_count = 0

        def _fake_claim(**_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise transport_error
            # Second call returns None → idle, then max_iterations exit.
            return None

        patches = _common_patches(recorder) + [
            patch.object(bw_mod, "claim_next_task", side_effect=_fake_claim),
        ]

        with caplog.at_level(logging.WARNING, logger="astrid.core.integrations.worker.banodoco_worker"):
            for p in patches:
                p.start()
            try:
                worker = BanodocoWorker(
                    dispatcher=lambda **_: (lambda c, v: c),
                    config=WorkerConfig(max_iterations=2, poll_interval_sec=0, idle_sleep_sec=0),
                )
                ret = worker.run()
            finally:
                for p in reversed(patches):
                    p.stop()

        assert ret == 0
        # Warning was logged for the transport error
        assert any("transport error" in r.message for r in caplog.records)
        # No status updates — transport error is handled by retrying, not by _fail
        assert len(recorder.calls) == 0
        assert call_count == 2


class TestNoWorkAvailable:
    """claim_next_task returns None → worker idles (no _fail or _complete call)."""

    def test_no_work_idles_and_exits(self) -> None:
        recorder = _StatusRecorder()
        patches = _common_patches(recorder) + [
            patch.object(bw_mod, "claim_next_task", return_value=None),
        ]
        for p in patches:
            p.start()
        try:
            worker = BanodocoWorker(
                dispatcher=lambda **_: (lambda c, v: c),
                config=WorkerConfig(max_iterations=3, poll_interval_sec=0, idle_sleep_sec=0),
            )
            ret = worker.run()
        finally:
            for p in reversed(patches):
                p.stop()

        assert ret == 0
        # Zero status updates — no claim was processed
        assert len(recorder.calls) == 0


class TestLostClaim:
    """Claim is received but processing fails → _fail is called.

    'Lost-claim' scenario: the task type is unsupported, so the task is
    immediately marked Failed without any real work.  The claim is 'lost'
    in the sense that it cannot be retried.
    """

    def test_unsupported_task_type_calls_fail(self) -> None:
        recorder = _StatusRecorder()
        claim = _make_claim(task_id="task-lost", task_type="unsupported_type")

        patches = _common_patches(recorder) + [
            patch.object(bw_mod, "claim_next_task", side_effect=[claim, None]),
        ]
        for p in patches:
            p.start()
        try:
            worker = BanodocoWorker(
                dispatcher=lambda **_: (lambda c, v: c),
                config=WorkerConfig(max_iterations=2, poll_interval_sec=0, idle_sleep_sec=0),
            )
            worker.run()
        finally:
            for p in reversed(patches):
                p.stop()

        assert len(recorder.calls) == 1
        call = recorder.calls[0]
        assert call["status"] == "Failed"
        assert call["task_id"] == "task-lost"
        assert "unsupported" in (call["error"] or "")

    def test_lost_claim_when_status_update_fails(self, caplog) -> None:
        """If _fail's update_task_status itself raises, the error is logged and the
        loop continues (claim is 'lost' — neither success nor failure was recorded)."""
        recorder_calls = []
        claim = _make_claim(task_id="task-doubleloss", task_type="unsupported_type")

        def _fail_update(task_id, *, status, service_role_key, **_):
            recorder_calls.append(task_id)
            raise RuntimeError("status endpoint unreachable")

        patches = [
            patch("astrid.core.integrations.worker.banodoco_worker.time.sleep"),
            patch("astrid.core.integrations.reigh.env.resolve_service_role_key", return_value="srv-key"),
            patch.object(bw_mod, "update_task_status", side_effect=_fail_update),
            patch.object(bw_mod, "claim_next_task", side_effect=[claim, None]),
        ]
        with caplog.at_level(logging.ERROR, logger="astrid.core.integrations.worker.banodoco_worker"):
            for p in patches:
                p.start()
            try:
                worker = BanodocoWorker(
                    dispatcher=lambda **_: (lambda c, v: c),
                    config=WorkerConfig(max_iterations=2, poll_interval_sec=0, idle_sleep_sec=0),
                )
                # Must not raise — _fail swallows its own failures
                ret = worker.run()
            finally:
                for p in reversed(patches):
                    p.stop()

        assert ret == 0
        # update_task_status was attempted for the failed task
        assert "task-doubleloss" in recorder_calls
        # Error was logged
        assert any("failed to post Failed" in r.message for r in caplog.records)


class TestBaselineSnapshotFailureRoutesToFail:
    """T1's wrapper: baseline-snapshot write failure calls _fail, never _complete.

    This test verifies the claim loop's try/except at :404-417 in banodoco_worker.py
    routes snapshot write failures through self._fail() and records no success.
    """

    def test_snapshot_failure_routes_to_fail(self) -> None:
        recorder = _StatusRecorder()
        claim = _make_claim(task_id="task-snap", correlation_id="corr-snap")

        patches = _common_patches(recorder) + [
            patch.object(bw_mod, "claim_next_task", side_effect=[claim, None]),
            patch.object(
                bw_mod,
                "_write_baseline_snapshot",
                side_effect=RuntimeError("disk full"),
            ),
        ]
        for p in patches:
            p.start()
        try:
            worker = BanodocoWorker(
                dispatcher=lambda **_: (lambda c, v: c),
                config=WorkerConfig(
                    max_iterations=2,
                    poll_interval_sec=0,
                    idle_sleep_sec=0,
                    project_slug="test-project",
                ),
                provider=_FakeProvider(),
            )
            ret = worker.run()
        finally:
            for p in reversed(patches):
                p.stop()

        assert ret == 0
        assert len(recorder.calls) == 1
        call = recorder.calls[0]
        assert call["status"] == "Failed"
        assert call["task_id"] == "task-snap"
        assert "baseline snapshot write failed" in (call["error"] or "")
        # result_data must have correlation_id only — no config_version or timeline_id
        assert "correlation_id" in call["result_data"]
        assert "config_version" not in call["result_data"]
        assert "timeline_id" not in call["result_data"]

    def test_snapshot_failure_no_complete_call(self) -> None:
        """Ensure _complete is never called when snapshot write fails."""
        claim = _make_claim(task_id="task-snap2", correlation_id="corr-2")
        complete_calls = []

        patches = [
            patch("astrid.core.integrations.worker.banodoco_worker.time.sleep"),
            patch("astrid.core.integrations.reigh.env.resolve_service_role_key", return_value="srv-key"),
            patch.object(bw_mod, "update_task_status"),
            patch.object(bw_mod, "verify_user_jwt", return_value=_VERIFIED_JWT),
            patch.object(bw_mod, "_verify_project_ownership", return_value=None),
            patch.object(bw_mod, "claim_next_task", side_effect=[claim, None]),
            patch.object(bw_mod, "_write_baseline_snapshot", side_effect=RuntimeError("no space")),
        ]
        for p in patches:
            p.start()
        try:
            worker = BanodocoWorker(
                dispatcher=lambda **_: (lambda c, v: c),
                config=WorkerConfig(
                    max_iterations=2,
                    poll_interval_sec=0,
                    idle_sleep_sec=0,
                    project_slug="test-project",
                ),
                provider=_FakeProvider(),
            )
            original_complete = worker._complete
            def _spy_complete(*args, **kwargs):
                complete_calls.append((args, kwargs))
                return original_complete(*args, **kwargs)
            worker._complete = _spy_complete

            worker.run()
        finally:
            for p in reversed(patches):
                p.stop()

        assert complete_calls == [], "_complete must not be called after snapshot failure"


class TestFullHappyPath:
    """Smoke test: a valid claim goes through the full loop without errors."""

    def test_valid_claim_calls_no_fail(self) -> None:
        recorder = _StatusRecorder()
        claim = _make_claim()

        patches = _common_patches(recorder) + [
            patch.object(bw_mod, "claim_next_task", side_effect=[claim, None]),
            patch.object(bw_mod, "_worker_append_events", return_value=42),
        ]
        for p in patches:
            p.start()
        try:
            worker = BanodocoWorker(
                dispatcher=lambda **_: (lambda c, v: c),
                config=WorkerConfig(
                    max_iterations=2,
                    poll_interval_sec=0,
                    idle_sleep_sec=0,
                    project_slug="test-project",
                ),
                provider=_FakeProvider(),
            )
            ret = worker.run()
        finally:
            for p in reversed(patches):
                p.stop()

        assert ret == 0
        assert len(recorder.calls) == 1
        call = recorder.calls[0]
        assert call["status"] == "Complete"
        assert call["result_data"]["config_version"] == 42
        assert call["result_data"]["baseline_snapshot"] == "abc123"
