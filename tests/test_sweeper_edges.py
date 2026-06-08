"""Edge-case regression for the RunPod sweeper (T15).

Covers: dry_run=True, mode="hard", empty projects_root, and a running-pod
fixture that asserts the sweep_async() path directly.

Complements tests/test_sweeper_async.py (SD1 boundary) and
tests/packs/runpod/test_sweeper.py (full lifecycle integration).
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from astrid.core.integrations.runpod.sweeper import (
    POD_HANDLE_FILENAME,
    sweep_async,
)


# ---------------------------------------------------------------------------
# Shared helpers (mirror test_sweeper.py to avoid cross-test-file imports)
# ---------------------------------------------------------------------------


def _make_handle(pod_id: str = "pod-edge-001", **overrides) -> dict:
    base = {
        "pod_id": pod_id,
        "ssh": "root@10.0.0.1 -p 2222",
        "name": f"astrid-edge-{pod_id}",
        "name_prefix": "astrid-edge",
        "terminate_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "gpu_type": "NVIDIA GeForce RTX 4090",
        "hourly_rate": 0.34,
        "provisioned_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "config_snapshot": {
            "api_key_ref": "RUNPOD_API_KEY",
            "datacenter_id": "US-GA-1",
            "image": "runpod/pytorch:latest",
            "container_disk_in_gb": 200,
        },
    }
    base.update(overrides)
    return base


def _write_handle_tree(base: Path, project: str, run_id: str, step_id: str, handle: dict) -> Path:
    produces_dir = base / project / "runs" / run_id / "steps" / step_id / "v1" / "produces"
    produces_dir.mkdir(parents=True)
    handle_path = produces_dir / POD_HANDLE_FILENAME
    handle_path.write_text(json.dumps(handle), encoding="utf-8")
    return handle_path


def _write_lease(base: Path, project: str, run_id: str, *, attached_session_id: str | None = None) -> None:
    run_dir = base / project / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "writer_epoch": 0,
        "attached_session_id": attached_session_id,
        "plan_hash": "",
    }
    (run_dir / "lease.json").write_text(json.dumps(payload), encoding="utf-8")


# ---------------------------------------------------------------------------
# T15 edge-case tests
# ---------------------------------------------------------------------------


def test_sweep_async_empty_projects_root_nonexistent() -> None:
    """sweep_async() on a nonexistent projects_root returns total=0 immediately."""
    result = asyncio.run(sweep_async(Path("/tmp/__sweeper_edges_nonexistent__")))
    assert result["total"] == 0
    assert result["terminated"] == 0
    assert result["skipped"] == 0
    assert result["errors"] == 0
    assert result["details"] == []


def test_sweep_async_empty_projects_root_empty_dir() -> None:
    """sweep_async() on an existing but empty directory returns total=0."""
    with tempfile.TemporaryDirectory() as tmp:
        result = asyncio.run(sweep_async(Path(tmp)))
    assert result["total"] == 0
    assert result["terminated"] == 0


def test_sweep_async_dry_run_records_would_terminate() -> None:
    """dry_run=True causes sweep_async() to record would_terminate without calling the API."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        handle = _make_handle()
        _write_handle_tree(base, "proj", "run-01", "step-01", handle)
        _write_lease(base, "proj", "run-01", attached_session_id=None)

        mock_pod = AsyncMock()
        mock_pod.is_idle = AsyncMock(return_value=True)
        discovery = SimpleNamespace(
            get_pod=AsyncMock(return_value=mock_pod),
            terminate=AsyncMock(),
        )

        with (
            patch("astrid.core.integrations.runpod.sweeper._rebuild_config", MagicMock()),
            patch("astrid.core.integrations.runpod.sweeper._runpod_discovery", return_value=discovery),
        ):
            result = asyncio.run(sweep_async(base, mode="default", dry_run=True))

    assert result["total"] == 1
    assert result["terminated"] == 1
    assert result["skipped"] == 0
    assert result["errors"] == 0

    detail = result["details"][0]
    assert detail["action"] == "would_terminate"
    assert "dry-run" in detail["reason"]

    # terminate() must NOT be called in dry-run mode
    discovery.terminate.assert_not_called()


def test_sweep_async_dry_run_mode_hard() -> None:
    """dry_run=True + mode='hard' records would_terminate and skips session/idle checks."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        handle = _make_handle()
        _write_handle_tree(base, "proj", "run-02", "step-01", handle)
        # Live session attached — default mode would skip, hard mode proceeds
        _write_lease(base, "proj", "run-02", attached_session_id="ses-live-123")
        discovery = SimpleNamespace(get_pod=AsyncMock(), terminate=AsyncMock())

        with (
            patch("astrid.core.integrations.runpod.sweeper._rebuild_config", MagicMock()),
            patch("astrid.core.integrations.runpod.sweeper._runpod_discovery", return_value=discovery),
        ):
            result = asyncio.run(sweep_async(base, mode="hard", dry_run=True))

    assert result["total"] == 1
    assert result["terminated"] == 1  # would_terminate counts as terminated
    assert result["skipped"] == 0

    detail = result["details"][0]
    assert detail["action"] == "would_terminate"

    # Hard mode must not call get_pod (idle check bypassed)
    discovery.get_pod.assert_not_called()
    discovery.terminate.assert_not_called()


def test_sweep_async_running_pod_fixture_default_mode_skips() -> None:
    """Default mode skips a pod that has a live session (running-pod fixture)."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        handle = _make_handle(pod_id="pod-running-01")
        _write_handle_tree(base, "proj", "run-03", "step-01", handle)
        # Attach a live writer session — simulates a "running pod"
        _write_lease(base, "proj", "run-03", attached_session_id="ses-running-abc")
        discovery = SimpleNamespace(get_pod=AsyncMock(), terminate=AsyncMock())

        with (
            patch("astrid.core.integrations.runpod.sweeper._rebuild_config", MagicMock()),
            patch("astrid.core.integrations.runpod.sweeper._runpod_discovery", return_value=discovery),
        ):
            result = asyncio.run(sweep_async(base, mode="default", dry_run=True))

    assert result["total"] == 1
    assert result["skipped"] == 1
    assert result["terminated"] == 0

    detail = result["details"][0]
    assert detail["action"] == "skip"
    assert "ses-running-abc" in detail["reason"]

    # No idle check or terminate when session is live
    discovery.get_pod.assert_not_called()
    discovery.terminate.assert_not_called()


def test_sweep_async_running_pod_fixture_hard_mode_proceeds() -> None:
    """Hard mode proceeds past live-session check on running-pod fixture (dry_run)."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        handle = _make_handle(pod_id="pod-running-02")
        _write_handle_tree(base, "proj", "run-04", "step-01", handle)
        _write_lease(base, "proj", "run-04", attached_session_id="ses-live-xyz")
        discovery = SimpleNamespace(get_pod=AsyncMock(), terminate=AsyncMock())

        with (
            patch("astrid.core.integrations.runpod.sweeper._rebuild_config", MagicMock()),
            patch("astrid.core.integrations.runpod.sweeper._runpod_discovery", return_value=discovery),
        ):
            result = asyncio.run(sweep_async(base, mode="hard", dry_run=True))

    # Hard mode bypasses session check → would_terminate
    assert result["total"] == 1
    assert result["terminated"] == 1
    assert result["skipped"] == 0

    detail = result["details"][0]
    assert detail["action"] == "would_terminate"
    assert detail["pod_id"] == "pod-running-02"

    # Idle check bypassed in hard mode
    discovery.get_pod.assert_not_called()
    discovery.terminate.assert_not_called()


def test_sweep_async_missing_terminate_at_skips() -> None:
    """Handles without terminate_at are skipped (not errors)."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        handle = _make_handle()
        del handle["terminate_at"]
        _write_handle_tree(base, "proj", "run-05", "step-01", handle)

        # No discovery mock needed — exits before idle/terminate checks
        result = asyncio.run(sweep_async(base, mode="default", dry_run=True))

    assert result["total"] == 1
    assert result["skipped"] == 1
    assert result["terminated"] == 0
    assert result["details"][0]["reason"] == "missing terminate_at in handle"


def test_sweep_async_terminate_at_future_skips() -> None:
    """Handles whose terminate_at is in the future are skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        handle = _make_handle(terminate_at=future)
        _write_handle_tree(base, "proj", "run-06", "step-01", handle)

        # No discovery mock needed — exits before idle/terminate checks
        result = asyncio.run(sweep_async(base, mode="default", dry_run=True))

    assert result["total"] == 1
    assert result["skipped"] == 1
    assert "not yet passed" in result["details"][0]["reason"]
