"""Test the RunPod sweeper with mocked lifecycle."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from astrid.core.project.current_run import write_current_run
from astrid.core.integrations.runpod.sweeper import (
    POD_HANDLE_FILENAME,
    RUNPOD_SWEEPER_AUDIT_FILENAME,
    _derive_run_dir,
    append_runpod_sweeper_event,
    collect_handles,
)
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.session.paths import session_path

SPRINT1_STOP_LINE_XFAIL = pytest.mark.xfail(
    strict=True,
    reason="Sprint 1 stop-line: default sweeps must not raw-append into task runs",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_handle(pod_id: str = "pod-test123", **overrides) -> dict:
    """Build a minimal valid pod_handle dict."""
    base = {
        "pod_id": pod_id,
        "ssh": "root@10.0.0.1 -p 2222",
        "name": f"astrid-test-{pod_id}",
        "name_prefix": "astrid-test",
        "terminate_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "gpu_type": "NVIDIA GeForce RTX 4090",
        "hourly_rate": 0.34,
        "provisioned_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "config_snapshot": {
            "api_key_ref": "RUNPOD_API_KEY",
            "datacenter_id": "US-GA-1",
            "image": "runpod/pytorch:latest",
            "container_disk_in_gb": 200,
            "volume_in_gb": 0,
            "network_volume_id": None,
            "ports": "8888/http,22/tcp",
        },
    }
    base.update(overrides)
    return base


def _write_handle_tree(base_dir: Path, project: str, run_id: str, step_id: str, handle: dict) -> Path:
    """Create the directory structure and write a pod_handle.json."""
    produces_dir = base_dir / project / "runs" / run_id / "steps" / step_id / "v1" / "produces"
    produces_dir.mkdir(parents=True)
    handle_path = produces_dir / POD_HANDLE_FILENAME
    handle_path.write_text(json.dumps(handle))
    return handle_path


def _write_lease(base_dir: Path, project: str, run_id: str, lease: dict) -> None:
    """Write a lease.json into a run directory."""
    run_dir = base_dir / project / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {"writer_epoch": 0, "attached_session_id": None, "plan_hash": ""}
    payload.update(lease)
    (run_dir / "lease.json").write_text(json.dumps(payload))


def _write_events(base_dir: Path, project: str, run_id: str, events: list[dict]) -> None:
    """Write events.jsonl into a run directory."""
    from astrid.core.task.events import EVENTS_FILENAME, ZERO_HASH, _event_hash

    run_dir = base_dir / project / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    prev_hash = ZERO_HASH
    lines = []
    for evt in events:
        stored = dict(evt)
        stored.pop("hash", None)
        stored["hash"] = _event_hash(prev_hash, stored)
        lines.append(json.dumps(stored, sort_keys=True, separators=(",", ":")))
        prev_hash = stored["hash"]

    (run_dir / EVENTS_FILENAME).write_text("\n".join(lines) + "\n")


def _read_sweeper_audit(projects_root: Path) -> list[dict]:
    audit_path = projects_root / RUNPOD_SWEEPER_AUDIT_FILENAME
    if not audit_path.exists():
        return []
    return [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _bind_sweeper_session(base_dir: Path, project: str, run_id: str, sid: str) -> None:
    import os

    os.environ[ASTRID_SESSION_ID_ENV] = sid
    from tests.conftest import make_session

    sess = make_session(id=sid, project=project, agent_id="sweeper-test", run_id=run_id)
    path = session_path(sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    sess.to_json(path)
    write_current_run(project, run_id, root=base_dir)


# ---------------------------------------------------------------------------
# collect_handles
# ---------------------------------------------------------------------------


def test_collect_handles_empty_dir() -> None:
    """collect_handles returns empty list when no handles exist."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        handles = collect_handles(base)
        assert handles == []


def test_collect_handles_finds_pod_handles() -> None:
    """collect_handles discovers pod_handle.json files in the canonical path."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        handle = _make_handle(pod_id="pod-xyz")
        _write_handle_tree(base, "myproject", "run-001", "step-a", handle)

        results = collect_handles(base)
        assert len(results) == 1
        path, data = results[0]
        assert data["pod_id"] == "pod-xyz"
        assert path.name == POD_HANDLE_FILENAME


def test_collect_handles_skips_invalid_json() -> None:
    """collect_handles skips files that aren't valid JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        produces_dir = base / "proj" / "runs" / "r1" / "steps" / "s1" / "v1" / "produces"
        produces_dir.mkdir(parents=True)
        (produces_dir / POD_HANDLE_FILENAME).write_text("not json {{{")

        results = collect_handles(base)
        assert len(results) == 0  # invalid JSON is skipped


def test_collect_handles_skips_handles_without_pod_id() -> None:
    """collect_handles skips dicts that don't have a pod_id key."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        produces_dir = base / "proj" / "runs" / "r1" / "steps" / "s1" / "v1" / "produces"
        produces_dir.mkdir(parents=True)
        (produces_dir / POD_HANDLE_FILENAME).write_text(json.dumps({"not_a_handle": True}))

        results = collect_handles(base)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# _derive_run_dir
# ---------------------------------------------------------------------------


def test_derive_run_dir_from_handle_path() -> None:
    """_derive_run_dir extracts the owning run directory."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        handle = _make_handle()
        handle_path = _write_handle_tree(base, "proj", "run-abc", "step-x", handle)

        run_dir = _derive_run_dir(handle_path, base)
        assert run_dir is not None
        assert run_dir.name == "run-abc"


def test_derive_run_dir_returns_none_for_outside_path() -> None:
    """_derive_run_dir returns None when the handle is outside the projects root."""
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        base = Path(tmp1)
        other = Path(tmp2)
        handle_path = other / "orphan.json"
        handle_path.write_text(json.dumps(_make_handle()))

        run_dir = _derive_run_dir(handle_path, base)
        assert run_dir is None


# ---------------------------------------------------------------------------
# Sweeper default-mode: skip cases
# ---------------------------------------------------------------------------


@pytest.fixture
def sweeper_projects_root() -> Path:
    """Create a temporary projects root with test data."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def test_sweeper_skip_terminate_at_not_passed(sweeper_projects_root: Path) -> None:
    """Default mode skips pods whose terminate_at is in the future."""
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    handle = _make_handle(pod_id="pod-future", terminate_at=future)
    _write_handle_tree(sweeper_projects_root, "proj", "run-1", "step-1", handle)
    _write_lease(sweeper_projects_root, "proj", "run-1", {"writer_epoch": 0, "attached_session_id": None})

    from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

    summary = run_sweep(sweeper_projects_root, mode="default", dry_run=True)
    assert summary["terminated"] == 0
    assert summary["skipped"] >= 1
    # The skip reason should mention time
    reasons = [d["reason"] for d in summary["details"]]
    assert any("not yet passed" in r for r in reasons)


def test_sweeper_skip_live_session_acked(sweeper_projects_root: Path) -> None:
    """Default mode skips pods whose owning run has a live session."""
    handle = _make_handle(pod_id="pod-live")
    _write_handle_tree(sweeper_projects_root, "proj", "run-live", "step-1", handle)
    _write_lease(sweeper_projects_root, "proj", "run-live", {
        "writer_epoch": 5,
        "attached_session_id": "sess-live-123",
    })

    from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

    summary = run_sweep(sweeper_projects_root, mode="default", dry_run=True)
    assert summary["terminated"] == 0
    reasons = [d["reason"] for d in summary["details"]]
    assert any("live session" in r for r in reasons)


def test_sweeper_default_skips_any_attached_writer_even_epoch_zero(
    sweeper_projects_root: Path,
) -> None:
    """Default mode requires no live writer, even before the writer epoch advances."""
    handle = _make_handle(pod_id="pod-live-epoch-zero")
    _write_handle_tree(sweeper_projects_root, "proj", "run-live-zero", "step-1", handle)
    _write_lease(
        sweeper_projects_root,
        "proj",
        "run-live-zero",
        {"writer_epoch": 0, "attached_session_id": "sess-live-zero"},
    )
    _write_events(
        sweeper_projects_root,
        "proj",
        "run-live-zero",
        [{"kind": "run_started", "ts": "2024-01-01T00:00:00Z"}],
    )

    import os

    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"
    try:
        with patch("runpod_lifecycle.discovery.terminate", AsyncMock()) as terminate:
            from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

            summary = run_sweep(sweeper_projects_root, mode="default", dry_run=False)

        terminate.assert_not_awaited()
        assert summary["terminated"] == 0
        assert summary["skipped"] == 1
        assert summary["event_append"] == {"not_attempted": 1}
        assert "live session" in summary["details"][0]["reason"]
        assert _read_sweeper_audit(sweeper_projects_root) == []
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


def test_sweeper_skip_pod_not_idle(sweeper_projects_root: Path) -> None:
    """Default mode skips pods that are not idle."""
    handle = _make_handle(pod_id="pod-busy")
    _write_handle_tree(sweeper_projects_root, "proj", "run-busy", "step-1", handle)
    _write_lease(sweeper_projects_root, "proj", "run-busy", {
        "writer_epoch": 0,
        "attached_session_id": None,
    })

    # Mock Pod.is_idle to return False
    mock_pod = MagicMock()
    mock_pod.is_idle = AsyncMock(return_value=False)

    import os
    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"

    try:
        with patch("runpod_lifecycle.discovery.get_pod", AsyncMock(return_value=mock_pod)), \
             patch("runpod_lifecycle.RunPodConfig", MagicMock()):
            from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

            summary = run_sweep(sweeper_projects_root, mode="default", dry_run=True)
            reasons = [d["reason"] for d in summary["details"]]
            assert any("not idle" in r for r in reasons)
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


# ---------------------------------------------------------------------------
# Sweeper default-mode: terminate
# ---------------------------------------------------------------------------


def test_sweeper_default_terminate_idle_pod(sweeper_projects_root: Path) -> None:
    """Default mode terminates idle pods with no live session and past terminate_at."""
    handle = _make_handle(pod_id="pod-idle")
    _write_handle_tree(sweeper_projects_root, "proj", "run-idle", "step-1", handle)
    _write_lease(sweeper_projects_root, "proj", "run-idle", {
        "writer_epoch": 0,
        "attached_session_id": None,
    })

    # Pre-seed events.jsonl so the writer-authenticated append has a chain.
    _write_events(sweeper_projects_root, "proj", "run-idle", [
        {"kind": "run_started", "ts": "2024-01-01T00:00:00Z"},
    ])

    mock_pod = MagicMock()
    mock_pod.is_idle = AsyncMock(return_value=True)

    import os
    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"

    try:
        with patch("runpod_lifecycle.discovery.get_pod", AsyncMock(return_value=mock_pod)), \
             patch("runpod_lifecycle.discovery.terminate", AsyncMock()), \
             patch("runpod_lifecycle.RunPodConfig", MagicMock()):
            from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

            # Dry run: just assert it would terminate
            summary = run_sweep(sweeper_projects_root, mode="default", dry_run=True)
            assert summary["terminated"] == 1
            # Verify details
            terminated = [d for d in summary["details"] if d["action"] == "would_terminate"]
            assert len(terminated) == 1
            assert terminated[0]["pod_id"] == "pod-idle"
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


# ---------------------------------------------------------------------------
# Sweeper --hard mode
# ---------------------------------------------------------------------------


def test_sweeper_hard_overrides_live_session_check(sweeper_projects_root: Path) -> None:
    """--hard mode bypasses the live-session check."""
    handle = _make_handle(pod_id="pod-hard-live")
    _write_handle_tree(sweeper_projects_root, "proj", "run-hard-live", "step-1", handle)
    _write_lease(sweeper_projects_root, "proj", "run-hard-live", {
        "writer_epoch": 5,
        "attached_session_id": "sess-live-active",
    })

    # Pre-seed events.jsonl
    _write_events(sweeper_projects_root, "proj", "run-hard-live", [
        {"kind": "run_started", "ts": "2024-01-01T00:00:00Z"},
    ])

    mock_pod = MagicMock()
    mock_pod.is_idle = AsyncMock(return_value=False)  # Even if not idle, --hard bypasses

    import os
    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"

    try:
        with patch("runpod_lifecycle.discovery.get_pod", AsyncMock(return_value=mock_pod)), \
             patch("runpod_lifecycle.discovery.terminate", AsyncMock()), \
             patch("runpod_lifecycle.RunPodConfig", MagicMock()):
            from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

            summary = run_sweep(sweeper_projects_root, mode="hard", dry_run=True)
            # --hard should permit termination despite live session and busy pod
            assert summary["terminated"] == 1
            terminated = [d for d in summary["details"] if d["action"] == "would_terminate"]
            assert len(terminated) == 1
            assert terminated[0]["pod_id"] == "pod-hard-live"
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


def test_sweeper_hard_requires_terminate_at_passed(sweeper_projects_root: Path) -> None:
    """--hard mode still requires terminate_at passed."""
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    handle = _make_handle(pod_id="pod-hard-future", terminate_at=future)
    _write_handle_tree(sweeper_projects_root, "proj", "run-hard-future", "step-1", handle)

    from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

    summary = run_sweep(sweeper_projects_root, mode="hard", dry_run=True)
    assert summary["terminated"] == 0
    assert summary["skipped"] >= 1


# ---------------------------------------------------------------------------
# pod_terminated_by_sweep event emission
# ---------------------------------------------------------------------------


def test_sweeper_emits_pod_terminated_event(sweeper_projects_root: Path) -> None:
    """Sweeper appends pod_terminated_by_sweep events to events.jsonl."""
    handle = _make_handle(pod_id="pod-event-test")
    _write_handle_tree(sweeper_projects_root, "proj", "run-event", "step-1", handle)
    _write_lease(sweeper_projects_root, "proj", "run-event", {
        "writer_epoch": 0,
        "attached_session_id": None,
    })

    # Pre-seed events.jsonl
    _write_events(sweeper_projects_root, "proj", "run-event", [
        {"kind": "run_started", "ts": "2024-01-01T00:00:00Z"},
    ])

    mock_pod = MagicMock()
    mock_pod.is_idle = AsyncMock(return_value=True)

    import os
    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"

    try:
        with patch("runpod_lifecycle.discovery.get_pod", AsyncMock(return_value=mock_pod)), \
             patch("runpod_lifecycle.discovery.terminate", AsyncMock()), \
             patch("runpod_lifecycle.RunPodConfig", MagicMock()):
            from astrid.core.integrations.runpod.sweeper import sweep as run_sweep
            from astrid.core.task.events import EVENTS_FILENAME

            # Real (non-dry-run) sweep
            summary = run_sweep(sweeper_projects_root, mode="default", dry_run=False)
            assert summary["terminated"] == 1

            # Verify events.jsonl now has the pod_terminated_by_sweep event
            events_path = sweeper_projects_root / "proj" / "runs" / "run-event" / EVENTS_FILENAME
            assert events_path.is_file()
            lines = events_path.read_text().strip().split("\n")
            # Should have the original run_started + the sweeper event
            assert len(lines) >= 2
            sweeper_events = [json.loads(line) for line in lines if "sweep" in line]
            assert len(sweeper_events) >= 1
            sweeper_event = sweeper_events[0]
            assert sweeper_event["kind"] == "pod_terminated_by_sweep"
            assert sweeper_event["pod_id"] == "pod-event-test"
            assert sweeper_event["mode"] == "default"
            assert "hash" in sweeper_event  # Hash-chained
            detail = summary["details"][0]
            assert detail["event_append_status"] == "appended"
            assert detail["event_hash"] == sweeper_event["hash"]
            audit = _read_sweeper_audit(sweeper_projects_root)
            assert audit[-1]["event_append_status"] == "appended"
            assert audit[-1]["event_hash"] == sweeper_event["hash"]
            assert audit[-1]["task_event"] is False
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


def test_default_sweep_appends_owned_event_without_bound_writer_session(
    sweeper_projects_root: Path,
) -> None:
    handle = _make_handle(pod_id="pod-no-bound-writer")
    _write_handle_tree(sweeper_projects_root, "proj", "run-no-bound-writer", "step-1", handle)
    _write_lease(
        sweeper_projects_root,
        "proj",
        "run-no-bound-writer",
        {"writer_epoch": 0, "attached_session_id": None},
    )
    _write_events(
        sweeper_projects_root,
        "proj",
        "run-no-bound-writer",
        [{"kind": "run_started", "ts": "2024-01-01T00:00:00Z"}],
    )

    mock_pod = MagicMock()
    mock_pod.is_idle = AsyncMock(return_value=True)

    import os

    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"
    try:
        with patch("runpod_lifecycle.discovery.get_pod", AsyncMock(return_value=mock_pod)), \
             patch("runpod_lifecycle.discovery.terminate", AsyncMock()), \
             patch("runpod_lifecycle.RunPodConfig", MagicMock()):
            from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

            summary = run_sweep(sweeper_projects_root, mode="default", dry_run=False)
            assert summary["terminated"] == 1
            assert summary["event_append"]["appended"] == 1

            events_path = sweeper_projects_root / "proj" / "runs" / "run-no-bound-writer" / "events.jsonl"
            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").strip().split("\n")]
            assert events[-1]["kind"] == "pod_terminated_by_sweep"
            assert events[-1]["pod_id"] == "pod-no-bound-writer"
            assert "hash" in events[-1]
            assert summary["details"][0]["event_append_status"] == "appended"
            assert _read_sweeper_audit(sweeper_projects_root)[-1]["event_append_status"] == "appended"
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


def test_sweeper_rejects_noncanonical_handle_path_before_termination(
    sweeper_projects_root: Path,
) -> None:
    """Hard mode still requires a stale canonical handle under a produces directory."""
    run_dir = sweeper_projects_root / "proj" / "runs" / "run-bad-handle"
    bad_handle_path = run_dir / "steps" / "step-1" / "v1" / "scratch" / POD_HANDLE_FILENAME
    bad_handle_path.parent.mkdir(parents=True)
    bad_handle_path.write_text(json.dumps(_make_handle(pod_id="pod-bad-handle")), encoding="utf-8")
    _write_lease(sweeper_projects_root, "proj", "run-bad-handle", {
        "writer_epoch": 99,
        "attached_session_id": "sess-active",
    })
    _write_events(
        sweeper_projects_root,
        "proj",
        "run-bad-handle",
        [{"kind": "run_started", "ts": "2024-01-01T00:00:00Z"}],
    )

    import os

    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"
    try:
        with patch("runpod_lifecycle.discovery.terminate", AsyncMock()) as terminate:
            from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

            summary = run_sweep(sweeper_projects_root, mode="hard", dry_run=False)

        terminate.assert_not_awaited()
        assert summary["terminated"] == 0
        assert summary["errors"] == 1
        assert summary["event_append"] == {"not_attempted": 1}
        assert "canonical owned" in summary["details"][0]["reason"]
        assert _read_sweeper_audit(sweeper_projects_root) == []
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


def test_sweeper_missing_lease_fails_before_termination_or_append(
    sweeper_projects_root: Path,
) -> None:
    handle = _make_handle(pod_id="pod-missing-lease")
    _write_handle_tree(sweeper_projects_root, "proj", "run-missing-lease", "step-1", handle)
    _write_events(
        sweeper_projects_root,
        "proj",
        "run-missing-lease",
        [{"kind": "run_started", "ts": "2024-01-01T00:00:00Z"}],
    )
    events_path = sweeper_projects_root / "proj" / "runs" / "run-missing-lease" / "events.jsonl"
    before = events_path.read_bytes()

    from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

    summary = run_sweep(sweeper_projects_root, mode="hard", dry_run=False)
    assert summary["terminated"] == 0
    assert summary["errors"] == 1
    assert "missing lease" in summary["details"][0]["reason"]
    assert events_path.read_bytes() == before


def test_sweeper_malformed_lease_fails_before_termination_or_append(
    sweeper_projects_root: Path,
) -> None:
    handle = _make_handle(pod_id="pod-malformed-lease")
    _write_handle_tree(sweeper_projects_root, "proj", "run-malformed-lease", "step-1", handle)
    run_dir = sweeper_projects_root / "proj" / "runs" / "run-malformed-lease"
    (run_dir / "lease.json").write_text("not-json", encoding="utf-8")
    _write_events(
        sweeper_projects_root,
        "proj",
        "run-malformed-lease",
        [{"kind": "run_started", "ts": "2024-01-01T00:00:00Z"}],
    )
    events_path = run_dir / "events.jsonl"
    before = events_path.read_bytes()

    from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

    summary = run_sweep(sweeper_projects_root, mode="hard", dry_run=False)
    assert summary["terminated"] == 0
    assert summary["errors"] == 1
    assert "invalid JSON" in summary["details"][0]["reason"]
    assert events_path.read_bytes() == before


def test_sweeper_hard_appends_owned_task_event_without_bound_writer_session(
    sweeper_projects_root: Path,
) -> None:
    """--hard mode bypasses live-session policy but still uses the locked event log."""
    handle = _make_handle(pod_id="pod-hard-event")
    _write_handle_tree(sweeper_projects_root, "proj", "run-hard-event", "step-1", handle)
    _write_lease(sweeper_projects_root, "proj", "run-hard-event", {
        "writer_epoch": 99,  # Active high epoch — --hard should bypass
        "attached_session_id": "sess-active-hard",
    })

    # Pre-seed events.jsonl
    _write_events(sweeper_projects_root, "proj", "run-hard-event", [
        {"kind": "run_started", "ts": "2024-01-01T00:00:00Z"},
    ])
    events_path = sweeper_projects_root / "proj" / "runs" / "run-hard-event" / "events.jsonl"

    import os
    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"

    try:
        with patch("runpod_lifecycle.discovery.terminate", AsyncMock()), \
             patch("runpod_lifecycle.RunPodConfig", MagicMock()):
            from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

            summary = run_sweep(sweeper_projects_root, mode="hard", dry_run=False)
            assert summary["terminated"] == 1
            assert summary["event_append"]["appended"] == 1

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").strip().split("\n")]
            assert events[-1]["kind"] == "pod_terminated_by_sweep"
            assert events[-1]["mode"] == "hard"
            assert events[-1]["pod_id"] == "pod-hard-event"
            assert events[-1]["handle_path"].endswith("/proj/runs/run-hard-event/steps/step-1/v1/produces/pod_handle.json")
            assert "hash" in events[-1]
            assert summary["details"][0]["event_append_status"] == "appended"
            audit = _read_sweeper_audit(sweeper_projects_root)
            assert audit[-1]["event_append_status"] == "appended"
            assert audit[-1]["event_hash"] == events[-1]["hash"]
            assert audit[-1]["task_event"] is False
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


def test_sweeper_reports_event_append_failures_in_summary_and_audit(
    sweeper_projects_root: Path,
) -> None:
    handle = _make_handle(pod_id="pod-append-fails")
    _write_handle_tree(sweeper_projects_root, "proj", "run-append-fails", "step-1", handle)
    _write_lease(
        sweeper_projects_root,
        "proj",
        "run-append-fails",
        {"writer_epoch": 99, "attached_session_id": "sess-active"},
    )
    _write_events(
        sweeper_projects_root,
        "proj",
        "run-append-fails",
        [{"kind": "run_started", "ts": "2024-01-01T00:00:00Z"}],
    )

    import os

    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"
    try:
        with patch("runpod_lifecycle.discovery.terminate", AsyncMock()), \
             patch(
                 "astrid.core.integrations.runpod.sweeper.append_runpod_sweeper_event",
                 side_effect=RuntimeError("append down"),
             ):
            from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

            summary = run_sweep(sweeper_projects_root, mode="hard", dry_run=False)

        assert summary["terminated"] == 0
        assert summary["errors"] == 1
        assert summary["event_append"] == {"failed": 1}
        assert summary["details"][0]["event_append_status"] == "failed"
        assert "append down" in summary["details"][0]["reason"]
        audit = _read_sweeper_audit(sweeper_projects_root)
        assert audit[-1]["event_append_status"] == "failed"
        assert audit[-1]["event_append_error"] == "append down"
        assert audit[-1]["task_event"] is False
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


def test_sweeper_already_gone_pod_still_appends_owned_event(
    sweeper_projects_root: Path,
) -> None:
    """A missing pod is an idempotent termination success, not an event skip."""
    handle = _make_handle(pod_id="pod-already-gone")
    _write_handle_tree(sweeper_projects_root, "proj", "run-already-gone", "step-1", handle)
    _write_lease(
        sweeper_projects_root,
        "proj",
        "run-already-gone",
        {"writer_epoch": 17, "attached_session_id": "sess-active"},
    )
    _write_events(
        sweeper_projects_root,
        "proj",
        "run-already-gone",
        [{"kind": "run_started", "ts": "2024-01-01T00:00:00Z"}],
    )
    events_path = sweeper_projects_root / "proj" / "runs" / "run-already-gone" / "events.jsonl"

    import os

    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"
    try:
        with patch("runpod_lifecycle.discovery.terminate", AsyncMock(side_effect=RuntimeError("pod not found"))):
            from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

            summary = run_sweep(sweeper_projects_root, mode="hard", dry_run=False)

        assert summary["terminated"] == 1
        assert summary["errors"] == 0
        assert summary["event_append"] == {"appended": 1}
        assert summary["details"][0]["event_append_status"] == "appended"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").strip().split("\n")]
        assert events[-1]["kind"] == "pod_terminated_by_sweep"
        assert events[-1]["pod_id"] == "pod-already-gone"
        assert events[-1]["mode"] == "hard"
        audit = _read_sweeper_audit(sweeper_projects_root)
        assert audit[-1]["event_append_status"] == "appended"
        assert audit[-1]["event_hash"] == events[-1]["hash"]
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


# ---------------------------------------------------------------------------
# Hash-chain integrity under --hard against active run
# ---------------------------------------------------------------------------


def test_sweeper_hard_preserves_task_hash_chain(sweeper_projects_root: Path) -> None:
    """--hard mode appends through the same task-run hash-chain transport."""
    handle = _make_handle(pod_id="pod-chain-test")
    _write_handle_tree(sweeper_projects_root, "proj", "run-chain", "step-1", handle)
    _write_lease(sweeper_projects_root, "proj", "run-chain", {
        "writer_epoch": 42,
        "attached_session_id": "sess-chain-active",
    })

    # Pre-seed with chain-starting events
    _write_events(sweeper_projects_root, "proj", "run-chain", [
        {"kind": "run_started", "ts": "2024-01-01T00:00:00Z"},
        {"kind": "step_completed", "step": "intro", "ts": "2024-01-01T00:01:00Z"},
    ])

    import os
    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"

    try:
        with patch("runpod_lifecycle.discovery.terminate", AsyncMock()), \
             patch("runpod_lifecycle.RunPodConfig", MagicMock()):
            from astrid.core.integrations.runpod.sweeper import sweep as run_sweep
            from astrid.core.task.events import EVENTS_FILENAME, verify_chain

            run_sweep(sweeper_projects_root, mode="hard", dry_run=False)

            # Verify the full task-run chain is intact and unchanged by hard mode.
            events_path = sweeper_projects_root / "proj" / "runs" / "run-chain" / EVENTS_FILENAME
            ok, bad_idx, err = verify_chain(events_path)
            assert ok, f"Chain broken at event {bad_idx}: {err}"
            assert len(events_path.read_text(encoding="utf-8").strip().split("\n")) == 3
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


def test_append_runpod_sweeper_event_rejects_wrong_kind_or_foreign_handle(
    sweeper_projects_root: Path,
) -> None:
    handle_path = _write_handle_tree(sweeper_projects_root, "proj", "run-owned", "step-1", _make_handle())
    _write_lease(sweeper_projects_root, "proj", "run-owned", {"writer_epoch": 0, "attached_session_id": None})
    _write_events(
        sweeper_projects_root,
        "proj",
        "run-owned",
        [{"kind": "run_started", "ts": "2024-01-01T00:00:00Z"}],
    )
    run_dir = sweeper_projects_root / "proj" / "runs" / "run-owned"

    with pytest.raises(ValueError, match="pod_terminated_by_sweep"):
        append_runpod_sweeper_event(
            run_dir,
            {"kind": "step_completed", "handle_path": str(handle_path)},
        )

    foreign = sweeper_projects_root / "proj" / "runs" / "other" / "steps" / "s" / "v1" / "produces" / POD_HANDLE_FILENAME
    foreign.parent.mkdir(parents=True)
    foreign.write_text(json.dumps(_make_handle()), encoding="utf-8")
    with pytest.raises(ValueError, match="does not belong"):
        append_runpod_sweeper_event(
            run_dir,
            {"kind": "pod_terminated_by_sweep", "pod_id": "pod", "handle_path": str(foreign)},
        )


def test_append_runpod_sweeper_event_retries_tail_conflicts(
    sweeper_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import astrid.core.integrations.runpod.sweeper as sweeper_module
    from astrid.core.task.events import StaleTailError

    handle_path = _write_handle_tree(sweeper_projects_root, "proj", "run-retry", "step-1", _make_handle())
    _write_lease(sweeper_projects_root, "proj", "run-retry", {"writer_epoch": 99, "attached_session_id": "active"})
    _write_events(
        sweeper_projects_root,
        "proj",
        "run-retry",
        [{"kind": "run_started", "ts": "2024-01-01T00:00:00Z"}],
    )
    run_dir = sweeper_projects_root / "proj" / "runs" / "run-retry"
    calls = 0

    def flaky_append(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise StaleTailError(expected="sha256:old", actual="sha256:new")
        return {"kind": "pod_terminated_by_sweep", "hash": "sha256:ok"}

    monkeypatch.setattr(sweeper_module, "append_event_locked", flaky_append)

    event = append_runpod_sweeper_event(
        run_dir,
        {"kind": "pod_terminated_by_sweep", "pod_id": "pod-retry", "handle_path": str(handle_path)},
    )

    assert calls == 2
    assert event["kind"] == "pod_terminated_by_sweep"
