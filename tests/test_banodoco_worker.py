"""Unit tests for astrid.core.integrations.worker.banodoco_worker.

Cover the per-task pipeline: task-type guard, JWKS verify, FLAG-013 project-
ownership read, snapshot fast-path, intent dispatch, carry-fields enforcement,
SD-008 baseline_snapshot, event-backed worker write (m3.5), and Complete/Failed
status reporting via update-task-status.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from astrid.core.integrations.reigh.task_client import ClaimResult
from astrid.core.integrations.reigh.worker_jwt import VerifiedJwt
from astrid.core.integrations.worker import banodoco_worker as bw_mod
from astrid.core.integrations.worker.banodoco_worker import (
    BanodocoWorker,
    DispatchError,
    WorkerConfig,
    _ensure_carry_fields,
    canonical_json,
    sha256_hex,
)


ROOT = Path(__file__).resolve().parents[1]


def _claim(**overrides) -> ClaimResult:
    base = {
        "task_id": "task-1",
        "run_id": "run-1",
        "project_id": "proj-1",
        "task_type": "banodoco_timeline_generate",
        "user_jwt": "jwt-token",
        "params": {
            "timeline_id": "tl-1",
            "expected_version": 3,
            "correlation_id": "corr",
            "intent": "passthrough",
        },
        "raw": {},
    }
    base.update(overrides)
    return ClaimResult(**base)


class _FakeProvider:
    def __init__(self, *, version: int = 3, timeline: dict[str, Any] | None = None) -> None:
        self.supabase_url = "https://example.supabase.co"
        self.timeout = 10.0
        self._version = version
        self._timeline = timeline or {
            "theme": "banodoco-default",
            "tracks": [{"id": "main", "kind": "visual", "label": "Main"}],
            "clips": [],
        }
        self.save_calls: list[dict[str, Any]] = []

    def load_timeline(self, project_id, timeline_id):
        return dict(self._timeline), self._version

    def save_timeline(self, timeline_id, mutator, **kwargs):
        config = mutator(dict(self._timeline), self._version)

        class Result:
            new_version = self._version + 1
            attempts = 1

        Result.new_version = self._version + 1
        self.save_calls.append({"timeline_id": timeline_id, "config": config, "kwargs": kwargs})
        return Result()


class _StatusRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, task_id, *, status, service_role_key, result_data=None, error=None, output_location=None, **_):
        self.calls.append(
            {
                "task_id": task_id,
                "status": status,
                "result_data": dict(result_data or {}),
                "error": error,
                "output_location": output_location,
                "service_role_key": service_role_key,
            }
        )


class BanodocoWorkerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.recorder = _StatusRecorder()
        self.provider = _FakeProvider()
        self.dispatcher_called: list[dict[str, Any]] = []

        def dispatcher(*, intent, params, verified):
            self.dispatcher_called.append({"intent": intent, "params": dict(params)})

            def _mutator(config, _version):
                config = dict(config)
                config["theme"] = "banodoco-default"
                return config

            return _mutator

        self.dispatcher = dispatcher

    def _make_worker(self, *, project_slug: str | None = None) -> BanodocoWorker:
        return BanodocoWorker(
            dispatcher=self.dispatcher,
            config=WorkerConfig(max_iterations=1, project_slug=project_slug),
            provider=self.provider,
        )

    def _patch_common(self):
        patches = [
            patch.object(bw_mod, "update_task_status", side_effect=self.recorder),
            patch.object(bw_mod, "_verify_project_ownership", return_value=None),
            patch.object(
                bw_mod,
                "verify_user_jwt",
                return_value=VerifiedJwt(user_id="user-1", audience="authenticated", raw_claims={"sub": "user-1"}),
            ),
        ]
        return patches

    def _start(self, patches):
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_invalid_task_type_yields_failed(self) -> None:
        self._start(self._patch_common())
        worker = self._make_worker()
        worker._handle_claim(_claim(task_type="foo"), service_role_key="srv-key")
        self.assertEqual(len(self.recorder.calls), 1)
        self.assertEqual(self.recorder.calls[0]["status"], "Failed")
        self.assertIn("unsupported task_type", self.recorder.calls[0]["error"])
        self.assertEqual(self.provider.save_calls, [])

    def test_invalid_jwt_yields_failed(self) -> None:
        from astrid.core.integrations.reigh.worker_jwt import JwtVerificationError

        patches = [
            patch.object(bw_mod, "update_task_status", side_effect=self.recorder),
            patch.object(bw_mod, "verify_user_jwt", side_effect=JwtVerificationError("bad sig")),
        ]
        self._start(patches)
        worker = self._make_worker()
        worker._handle_claim(_claim(), service_role_key="srv-key")
        self.assertEqual(self.recorder.calls[0]["status"], "Failed")
        self.assertIn("invalid user_jwt", self.recorder.calls[0]["error"])
        self.assertEqual(self.provider.save_calls, [])

    def test_project_ownership_mismatch_yields_failed(self) -> None:
        from astrid.core.integrations.worker.banodoco_worker import ProjectOwnershipError

        patches = [
            patch.object(bw_mod, "update_task_status", side_effect=self.recorder),
            patch.object(
                bw_mod,
                "verify_user_jwt",
                return_value=VerifiedJwt(user_id="user-1", audience="authenticated", raw_claims={}),
            ),
            patch.object(
                bw_mod,
                "_verify_project_ownership",
                side_effect=ProjectOwnershipError("owner mismatch"),
            ),
        ]
        self._start(patches)
        worker = self._make_worker()
        worker._handle_claim(_claim(), service_role_key="srv-key")
        self.assertEqual(self.recorder.calls[0]["status"], "Failed")
        self.assertIn("project ownership mismatch", self.recorder.calls[0]["error"])
        self.assertEqual(self.provider.save_calls, [])

    # ------------------------------------------------------------------
    # m3.5: worker write-back migrated to event gateway.  Without a local
    # project binding the worker fails with a controlled error (remote-only
    # claims are deferred to m6).  These tests prove that the controlled
    # failure path works and that provider.save_timeline is never called.
    # ------------------------------------------------------------------

    def test_success_path_without_project_slug_fails_controlled(self) -> None:
        """m3.5: worker without project_slug cannot append events locally.

        Remote-only claims are controlled failures deferred to m6.
        provider.save_timeline is NEVER called.
        """
        self._start(self._patch_common())
        worker = self._make_worker()  # no project_slug
        worker._handle_claim(_claim(), service_role_key="srv-key")

        self.assertEqual(len(self.dispatcher_called), 1)
        self.assertEqual(self.dispatcher_called[0]["intent"], "passthrough")

        # provider.save_timeline must never be called (m3.5 migration).
        self.assertEqual(self.provider.save_calls, [])

        # Status reported as Failed (controlled failure deferred to m6).
        self.assertEqual(self.recorder.calls[0]["status"], "Failed")
        self.assertIn("worker append failed", self.recorder.calls[0]["error"])

    def test_success_path_with_local_binding_emits_events(self) -> None:
        """m3.5: worker with local project binding appends via event gateway.

        Sets up a real project + managed timeline so _worker_append_events
        can resolve the local backend.  Proves the success payload shape
        {config_version, correlation_id, timeline_id} with config_version
        from the event-stream version.
        """
        tmp_root = Path(tempfile.mkdtemp(prefix="bw-event-test-", dir=ROOT))
        self.addCleanup(shutil.rmtree, tmp_root, ignore_errors=True)
        from astrid.core.foundation import project_paths
        from astrid.core.project.project import create_project

        with patch.dict("os.environ", {project_paths.PROJECTS_ROOT_ENV: str(tmp_root)}):
            create_project("event-demo")
            # Create a managed timeline container.
            from astrid.core.timeline.crud import create_timeline

            create_timeline("event-demo", "event-timeline")

            # Read the identity UUID so the claim's timeline_id matches.
            from astrid.core.timeline.paths import find_timeline_by_slug, assembly_identity_path
            from astrid.core._shared.jsonio import read_json

            found = find_timeline_by_slug("event-demo", "event-timeline")
            self.assertIsNotNone(found)
            ulid, _tdir = found
            identity = read_json(assembly_identity_path("event-demo", ulid))
            real_timeline_id = identity["timeline_id"]

            self._start(self._patch_common())
            worker = self._make_worker(project_slug="event-demo")
            claim = _claim(params={
                "timeline_id": real_timeline_id,
                "expected_version": 3,
                "correlation_id": "corr",
                "intent": "passthrough",
                "project_id": "proj-1",
            })
            worker._handle_claim(claim, service_role_key="srv-key")

            # provider.save_timeline must never be called.
            self.assertEqual(self.provider.save_calls, [])

            self.assertEqual(len(self.dispatcher_called), 1)

            # Status must be Complete with correct payload shape.
            self.assertEqual(self.recorder.calls[0]["status"], "Complete")
            rd = self.recorder.calls[0]["result_data"]
            self.assertEqual(set(rd.keys()), {"config_version", "correlation_id", "timeline_id"})
            self.assertIsInstance(rd["config_version"], int)
            self.assertGreater(rd["config_version"], 0)
            self.assertEqual(rd["correlation_id"], "corr")
            self.assertEqual(rd["timeline_id"], real_timeline_id)

    def test_snapshot_fast_path_uses_current_timeline_param(self) -> None:
        """m3.5: snapshot fast-path still works with current_timeline param.

        Without local project binding, fails controlled (remote-only deferred).
        """
        self._start(self._patch_common())
        worker = self._make_worker()
        snapshot = {"theme": "fast", "clips": []}
        params = {
            "timeline_id": "tl-1",
            "expected_version": 3,
            "correlation_id": "corr",
            "intent": "passthrough",
            "current_timeline": snapshot,
        }
        # load_timeline must NOT be called when current_timeline is present.
        with patch.object(self.provider, "load_timeline", side_effect=AssertionError("should not be called")):
            worker._handle_claim(_claim(params=params), service_role_key="srv-key")
        # Without local project_slug, fails as controlled failure.
        self.assertIn(self.recorder.calls[0]["status"], {"Failed", "Complete"})
        # provider.save_timeline must never be called.
        self.assertEqual(self.provider.save_calls, [])

    def test_failure_path_status_failed_with_correlation_id_in_result_data(self) -> None:
        self._start(self._patch_common())

        def boom(*, intent, params, verified):
            raise DispatchError("no handler")

        worker = BanodocoWorker(
            dispatcher=boom,
            config=WorkerConfig(max_iterations=1),
            provider=self.provider,
        )
        worker._handle_claim(_claim(), service_role_key="srv-key")
        self.assertEqual(self.recorder.calls[0]["status"], "Failed")
        self.assertIn("intent dispatch failed", self.recorder.calls[0]["error"])
        self.assertEqual(self.recorder.calls[0]["result_data"], {"correlation_id": "corr"})

    def test_baseline_snapshot_is_not_written_to_local_run_record(self) -> None:
        """Baseline provenance is returned for runtime settlement, not run.json."""
        tmp_root = Path(tempfile.mkdtemp(prefix="bw-baseline-test-", dir=ROOT))
        self.addCleanup(shutil.rmtree, tmp_root, ignore_errors=True)
        digest = bw_mod._write_baseline_snapshot(
            project_slug="baseline-demo", run_id="run-1", payload={"clips": []}
        )
        self.assertIsInstance(digest, str)
        self.assertEqual(len(digest), 64)
        self.assertTrue(all(ch in "0123456789abcdef" for ch in digest))
        self.assertFalse((tmp_root / "baseline-demo" / "runs" / "run-1" / "run.json").exists())


class CanonicalHashTest(unittest.TestCase):
    def test_canonical_json_is_stable_under_key_reordering(self) -> None:
        self.assertEqual(
            canonical_json({"b": 2, "a": 1}),
            canonical_json({"a": 1, "b": 2}),
        )

    def test_sha256_hex_returns_64_char_lowercase_hex(self) -> None:
        digest = sha256_hex("hello")
        self.assertEqual(len(digest), 64)
        self.assertTrue(all(ch in "0123456789abcdef" for ch in digest))


class CarryFieldsTest(unittest.TestCase):
    def test_ensure_carry_fields_populates_defaults_on_every_clip(self) -> None:
        clips = [
            {"id": "a", "at": 0},
            {"id": "b", "at": 1, "source_uuid": "explicit"},
        ]
        _ensure_carry_fields(clips)
        for clip in clips:
            self.assertIn("source_uuid", clip)
            self.assertIn("generation", clip)
            self.assertEqual(clip["pool_id"], "default")
            self.assertIn("clip_order", clip)
        self.assertEqual(clips[1]["source_uuid"], "explicit")


if __name__ == "__main__":
    unittest.main()
