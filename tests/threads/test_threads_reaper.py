from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.contracts.run_status import RunStatus
from astrid.core.threads.attribute import _reset_reaper_for_tests, reap_orphans_once
from astrid.core.threads.ids import generate_run_id, generate_thread_id
from astrid.core.threads.record import build_run_record, write_run_record


def test_lazy_reaper_marks_abandoned_running_run_orphaned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("ASTRID_REPO_ROOT", str(repo))
    out = repo / "runs" / "stale"
    record = build_run_record(
        run_id=generate_run_id(),
        thread_id=generate_thread_id(),
        kind="executor",
        executor_id="test.stale",
        out_path=out,
        repo_root=repo,
    )
    record["pid"] = 99999999
    write_run_record(record, out / "run.json")
    _reset_reaper_for_tests()

    assert reap_orphans_once(repo) == 1
    assert reap_orphans_once(repo) == 0

    updated = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert updated["status"] == RunStatus.FAILED.value
    assert updated["returncode"] == -1
    assert updated["ended_at"]
    assert updated["error"]["type"] == "orphaned"


def test_lazy_reaper_treats_legacy_prepared_status_as_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("ASTRID_REPO_ROOT", str(repo))
    out = repo / "runs" / "legacy-prepared"
    record = build_run_record(
        run_id=generate_run_id(),
        thread_id=generate_thread_id(),
        kind="executor",
        executor_id="test.legacy",
        out_path=out,
        repo_root=repo,
    )
    record["status"] = "prepared"
    record["pid"] = 99999999
    write_run_record(record, out / "run.json")
    _reset_reaper_for_tests()

    assert reap_orphans_once(repo) == 1

    updated = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert updated["status"] == RunStatus.FAILED.value
    assert updated["returncode"] == -1
    assert updated["ended_at"]
    assert updated["error"]["type"] == "orphaned"
