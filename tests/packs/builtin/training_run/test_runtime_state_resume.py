"""Runtime dry-run, failure, and resume ordering tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from astrid.packs.builtin.training_run.run import main as training_run_main


def test_dry_run_writes_plan_without_network_gpu_or_runpod_calls(
    tmp_path: Path,
    backend_factory: Callable[..., tuple[object, object, list[str]]],
    clip_pair: Callable[[Path, str], tuple[Path, Path]],
    flat_manifest: Callable[[Path, Path, Path], Path],
    training_config: Callable[[Path, Path, Path, dict | None], Path],
) -> None:
    compute, remote, events = backend_factory()
    clip, caption = clip_pair(tmp_path / "dataset")
    manifest = flat_manifest(tmp_path / "manifest.json", clip, caption)
    run_dir = tmp_path / "dry-run"
    config_path = training_config(tmp_path / "config.json", manifest, run_dir)

    rc = training_run_main(["--config", str(config_path), "--dry-run", "--json"])

    assert rc == 0
    assert events == []
    assert compute.provision_calls == []
    assert remote.exec_calls == []
    assert remote.pull_calls == []
    state = json.loads((run_dir / "last_run.json").read_text(encoding="utf-8"))
    assert state["status"] == "preflight_ready"
    assert Path(state["artifacts"]["normalized_manifest_path"]).is_file()
    assert Path(state["artifacts"]["trainer_config_path"]).is_file()
    assert Path(state["artifacts"]["planned_cost_path"]).is_file()


def test_live_missing_handle_path_records_recoverable_failure_without_teardown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backend_factory: Callable[..., tuple[object, object, list[str]]],
    clip_pair: Callable[[Path, str], tuple[Path, Path]],
    flat_manifest: Callable[[Path, Path, Path], Path],
    training_config: Callable[[Path, Path, Path, dict | None], Path],
) -> None:
    compute, remote, events = backend_factory(include_handle_path=False)
    monkeypatch.setenv("RUNPOD_API_KEY", "present")
    clip, caption = clip_pair(tmp_path / "dataset")
    manifest = flat_manifest(tmp_path / "manifest.json", clip, caption)
    run_dir = tmp_path / "recoverable"
    config_path = training_config(tmp_path / "config.json", manifest, run_dir)

    rc = training_run_main(["--config", str(config_path), "--confirm-spend", "--json"])

    assert rc == 2
    assert events == ["provision"]
    assert compute.teardown_calls == []
    assert remote.exec_calls == []
    state = json.loads((run_dir / "last_run.json").read_text(encoding="utf-8"))
    assert state["status"] == "FAILED_RECOVERABLE"
    assert state["recoverability"]["manual_recovery_required"] is True
    assert state["recoverability"]["unsafe_teardown_reason"] == "missing_handle_path"


def test_live_training_failure_preserves_pod_for_checkpoint_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backend_factory: Callable[..., tuple[object, object, list[str]]],
    clip_pair: Callable[[Path, str], tuple[Path, Path]],
    flat_manifest: Callable[[Path, Path, Path], Path],
    training_config: Callable[[Path, Path, Path, dict | None], Path],
) -> None:
    compute, remote, events = backend_factory(fail_exec_index=2)
    monkeypatch.setenv("RUNPOD_API_KEY", "present")
    clip, caption = clip_pair(tmp_path / "dataset")
    manifest = flat_manifest(tmp_path / "manifest.json", clip, caption)
    run_dir = tmp_path / "training-failure"
    config_path = training_config(tmp_path / "config.json", manifest, run_dir)

    rc = training_run_main(["--config", str(config_path), "--confirm-spend", "--json"])

    assert rc == 2
    assert events == ["provision", "exec", "exec"]
    assert compute.teardown_calls == []
    state = json.loads((run_dir / "last_run.json").read_text(encoding="utf-8"))
    assert state["status"] == "FAILED_RECOVERABLE"
    assert state["final_error"]["phase"] == "training"
    assert state["pod"]["id"] == "pod-test"
    assert state["recoverability"]["manual_recovery_required"] is True
    assert state["recoverability"]["unsafe_teardown_reason"] == "training_may_have_remote_artifacts"
    assert state["recoverability"]["teardown_guard"]["required"] is True


def test_resume_pulls_checkpoint_and_registers_before_teardown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backend_factory: Callable[..., tuple[object, object, list[str]]],
    clip_pair: Callable[[Path, str], tuple[Path, Path]],
    flat_manifest: Callable[[Path, Path, Path], Path],
    training_config: Callable[[Path, Path, Path, dict | None], Path],
) -> None:
    compute, remote, events = backend_factory()
    monkeypatch.setenv("RUNPOD_API_KEY", "present")
    clip, caption = clip_pair(tmp_path / "dataset")
    manifest = flat_manifest(tmp_path / "manifest.json", clip, caption)
    run_dir = tmp_path / "resume"
    config_path = training_config(tmp_path / "config.json", manifest, run_dir)
    assert training_run_main(["--config", str(config_path), "--confirm-spend", "--json"]) == 0
    live_events = list(events)

    rc = training_run_main(["resume", "--out", str(run_dir), "--pick", "final", "--notes", "approved", "--json"])

    assert rc == 0
    assert events[: len(live_events)] == live_events
    assert events[-2:] == ["pull", "teardown"]
    assert remote.pull_calls[-1]["remote_paths"] == ["/workspace/output/demo-final.safetensors"]
    state = json.loads((run_dir / "last_run.json").read_text(encoding="utf-8"))
    assert state["status"] == "REGISTERED"
    assert Path(state["registration"]["registered_lora_path"]).is_file()
    assert state["registration"]["notes"] == "approved"
    assert state["teardown"] == {"skipped": False, "completed": True, "pod_id": "pod-test"}
