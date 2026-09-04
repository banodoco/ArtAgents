from __future__ import annotations

import hashlib
from pathlib import Path

from astrid.sdk.remote import RemoteRuns


class _Runtime:
    def __init__(self, data: bytes = b"video-bytes") -> None:
        self.data = data
        self.digest = "sha256:" + hashlib.sha256(data).hexdigest()
        self.opened: list[list[str]] = []
        self.runs = [
            {"run_id": "R-old", "project_id": "P-1", "capability_id": "rendering.render", "status": "completed", "created_at": "2026-01-01", "task_ids": ["T-old"]},
            {"run_id": "R-failed", "project_id": "P-1", "capability_id": "rendering.render", "status": "failed", "created_at": "2026-01-03", "task_ids": ["T-failed"]},
            {"run_id": "R-new", "project_id": "P-1", "capability_id": "rendering.render", "status": "completed", "created_at": "2026-01-02", "task_ids": ["T-new"]},
        ]

    def get_project(self, ref):
        return {"project_id": "P-1", "slug": ref}

    def current_project(self):
        return {
            "project": {"project_id": "P-1", "slug": "demo"},
            "scope": "workspace",
        }

    def list_project_runs(self, project_id, *, cursor=None, limit=50):
        assert project_id == "P-1"
        return [self.runs, None]

    def get_run(self, run_id):
        return next(run for run in self.runs if run["run_id"] == run_id)

    def get_task(self, task_id):
        return {
            "task_id": task_id,
            "capability_id": "rendering.render",
            "state": "completed",
            "spec": {"inputs": {"output_name": "review.mp4"}},
            "result": {"outputs": [{"name": "video", "digest": self.digest, "size": len(self.data)}]},
        }

    def list_project_objects(self, project_id, *, cursor=None, limit=50):
        assert project_id == "P-1"
        return [[{"object_id": "O-video", "digest": self.digest, "size": len(self.data), "filename": "video"}], None]

    def get_object(self, object_id):
        assert object_id == "O-video"
        return {"data": self.data, "status": 200, "headers": {}}


def test_open_selects_latest_successful_runtime_render(monkeypatch, tmp_path: Path) -> None:
    runtime = _Runtime()
    launched: list[list[str]] = []
    monkeypatch.setattr("astrid.sdk.project_render.platform.system", lambda: "Darwin")
    monkeypatch.setattr("astrid.sdk.project_render.subprocess.run", lambda argv, check: launched.append(argv))

    result = RemoteRuns(runtime).open(cache_root=tmp_path)

    assert result.ok
    assert result.data["run_id"] == "R-new"
    assert result.data["digest"] == runtime.digest
    assert Path(result.data["local_path"]).read_bytes() == runtime.data
    assert Path(result.data["local_path"]).suffix == ".mp4"
    assert launched == [["open", result.data["local_path"]]]


def test_open_exact_run_rejects_cross_project_before_download(monkeypatch, tmp_path: Path) -> None:
    runtime = _Runtime()
    runtime.runs.append({
        "run_id": "R-other", "project_id": "P-2", "capability_id": "rendering.render",
        "status": "completed", "created_at": "2026-01-04", "task_ids": ["T-other"],
    })
    monkeypatch.setattr("astrid.sdk.project_render.platform.system", lambda: "Darwin")

    result = RemoteRuns(runtime).open("R-other", cache_root=tmp_path)

    assert not result.ok
    assert result.error.code == "not_found"
    assert not list(tmp_path.rglob("*.mp4"))


def test_open_fails_closed_on_ambiguous_video_outputs(monkeypatch, tmp_path: Path) -> None:
    runtime = _Runtime()
    original = runtime.get_task

    def ambiguous(task_id):
        task = original(task_id)
        task["result"]["outputs"].append(dict(task["result"]["outputs"][0]))
        return task

    runtime.get_task = ambiguous
    monkeypatch.setattr("astrid.sdk.project_render.platform.system", lambda: "Darwin")

    result = RemoteRuns(runtime).open(cache_root=tmp_path)

    assert not result.ok
    assert result.error.code == "validation_error"


def test_open_verifies_downloaded_bytes(monkeypatch, tmp_path: Path) -> None:
    runtime = _Runtime()
    runtime.data = b"tampered-after-settlement"
    monkeypatch.setattr("astrid.sdk.project_render.platform.system", lambda: "Darwin")

    result = RemoteRuns(runtime).open(cache_root=tmp_path)

    assert not result.ok
    assert result.error.code == "integrity_error"


def test_open_explicit_project_overrides_current_selection(monkeypatch, tmp_path: Path) -> None:
    runtime = _Runtime()
    runtime.current_project = lambda: (_ for _ in ()).throw(
        AssertionError("current selection must not be read")
    )
    monkeypatch.setattr("astrid.sdk.project_render.platform.system", lambda: "Darwin")
    monkeypatch.setattr("astrid.sdk.project_render.subprocess.run", lambda argv, check: None)

    result = RemoteRuns(runtime).open(project="demo", cache_root=tmp_path)

    assert result.ok


def test_open_without_current_project_returns_typed_recovery(monkeypatch, tmp_path: Path) -> None:
    runtime = _Runtime()
    runtime.current_project = lambda: {"project": None, "scope": None}
    monkeypatch.setattr("astrid.sdk.project_render.platform.system", lambda: "Darwin")

    result = RemoteRuns(runtime).open(cache_root=tmp_path)

    assert not result.ok
    assert result.error.code == "not_found"
    assert result.error.details["next_action"] == "astrid projects select <project>"
