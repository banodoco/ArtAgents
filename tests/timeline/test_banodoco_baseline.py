"""Regression for SD-008 baseline_snapshot write-failure propagation.

Pre-fix bug: ``_write_baseline_snapshot`` swallowed write failures via a bare
``except Exception``, logged a warning, and returned a success-shaped digest.
The claim loop never noticed and posted Complete with stale provenance.

The fix re-raises from ``_write_baseline_snapshot`` (None is reserved ONLY
for the "no project slug" branch) and wraps the single caller in the claim
loop in a try/except that calls ``self._fail(...)`` mirroring the existing
load_timeline failure pattern.
"""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from astrid.core.reigh.task_client import ClaimResult
from astrid.core.reigh.worker_jwt import VerifiedJwt
from astrid.core.worker import banodoco_worker as bw_mod
from astrid.core.worker.banodoco_worker import (
    BanodocoWorker,
    WorkerConfig,
    _write_baseline_snapshot,
)


def _claim() -> ClaimResult:
    return ClaimResult(
        task_id="task-snap",
        run_id="run-snap",
        project_id="proj-snap",
        task_type="banodoco_timeline_generate",
        user_jwt="jwt-token",
        params={
            "timeline_id": "tl-snap",
            "expected_version": 1,
            "correlation_id": "corr-snap",
            "intent": "passthrough",
        },
        raw={},
    )


class _FakeProvider:
    def __init__(self) -> None:
        self.supabase_url = "https://example.supabase.co"
        self.timeout = 10.0

    def load_timeline(self, project_id, timeline_id):
        return ({"theme": "t", "tracks": [], "clips": []}, 1)


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


class WriteBaselineSnapshotPropagationTest(unittest.TestCase):
    """Direct unit test of ``_write_baseline_snapshot`` exception propagation."""

    def test_write_run_record_failure_propagates(self) -> None:
        boom = RuntimeError("disk full")
        with patch.object(bw_mod, "write_run_record", side_effect=boom):
            with self.assertRaises(RuntimeError) as ctx:
                _write_baseline_snapshot(
                    project_slug="some-project",
                    run_id="run-1",
                    payload={"clips": []},
                )
        self.assertIs(ctx.exception, boom)

    def test_no_project_slug_returns_none(self) -> None:
        """None remains reserved for the 'no project slug configured' branch."""
        result = _write_baseline_snapshot(
            project_slug=None,
            run_id="run-1",
            payload={"clips": []},
        )
        self.assertIsNone(result)


class ClaimLoopWrappingBaselineFailureTest(unittest.TestCase):
    """Claim-loop wrapper must call ``_fail`` and never post a success."""

    def setUp(self) -> None:
        self.recorder = _StatusRecorder()
        self.provider = _FakeProvider()

        def dispatcher(*, intent, params, verified):
            def _mutator(config, _v):
                return dict(config)

            return _mutator

        self.dispatcher = dispatcher

    def _patches(self) -> list:
        return [
            patch.object(bw_mod, "update_task_status", side_effect=self.recorder),
            patch.object(bw_mod, "_verify_project_ownership", return_value=None),
            patch.object(
                bw_mod,
                "verify_user_jwt",
                return_value=VerifiedJwt(
                    user_id="user-1",
                    audience="authenticated",
                    raw_claims={"sub": "user-1"},
                ),
            ),
            # write_run_record raises — the snapshot helper must propagate.
            patch.object(
                bw_mod,
                "write_run_record",
                side_effect=RuntimeError("snapshot write failed: disk full"),
            ),
        ]

    def test_snapshot_failure_calls_fail_and_records_no_success(self) -> None:
        for p in self._patches():
            p.start()
            self.addCleanup(p.stop)

        worker = BanodocoWorker(
            dispatcher=self.dispatcher,
            config=WorkerConfig(max_iterations=1, project_slug="snap-project"),
            provider=self.provider,
        )

        # Must NOT raise out of _handle_claim — wrapper catches it.
        worker._handle_claim(_claim(), service_role_key="srv-key")

        # Exactly one status update — Failed, never Complete.
        self.assertEqual(len(self.recorder.calls), 1, self.recorder.calls)
        call = self.recorder.calls[0]
        self.assertEqual(call["status"], "Failed")
        self.assertIn("baseline snapshot write failed", call["error"])
        # correlation_id is the only success-shaped field on _fail's
        # result_data — config_version and timeline_id must be absent.
        self.assertEqual(call["result_data"], {"correlation_id": "corr-snap"})
        self.assertNotIn("config_version", call["result_data"])
        self.assertNotIn("timeline_id", call["result_data"])


if __name__ == "__main__":
    unittest.main()
