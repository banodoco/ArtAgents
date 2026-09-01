"""Focused coverage for runtime-owned pack orchestration admission."""

from __future__ import annotations

import ast
from pathlib import Path

from astrid.core.project import kernel_admission


class _Result:
    ok = True

    def __init__(self, data):
        self.data = data


class _Tasks:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Result({"run_id": "run-1", "task_id": "task-1"})


class _Client:
    def __init__(self) -> None:
        self.tasks = _Tasks()


def test_admission_uses_injected_runtime_task_client() -> None:
    client = _Client()
    context = kernel_admission.admit_orchestrator_project_run(
        project="demo",
        tool_id="video_editing.hype",
        argv=["--project", "demo"],
        client=client,
    )

    assert context.run_id == "run-1"
    assert context.project_slug == "demo"
    assert context.run_root.is_dir()
    assert client.tasks.calls[0]["project_id"] == "demo"
    assert client.tasks.calls[0]["capability"] == "video_editing.hype"
    assert client.tasks.calls[0]["spec"]["argv"] == ["--project", "demo"]


def test_admission_requires_explicit_runtime_client() -> None:
    import pytest

    with pytest.raises(kernel_admission.ProjectRuntimeError, match="explicit generated"):
        kernel_admission.admit_orchestrator_project_run(
            project="demo",
            tool_id="video_editing.hype",
            argv=[],
        )


def test_admission_and_normal_callers_have_no_local_composition() -> None:
    paths = [
        Path(kernel_admission.__file__),
        Path(__file__).parents[2]
        / "astrid"
        / "packs"
        / "video_editing"
        / "orchestrators"
        / "thumbnail_maker"
        / "run.py",
        Path(__file__).parents[2]
        / "astrid"
        / "packs"
        / "video_editing"
        / "orchestrators"
        / "event_talks"
        / "run.py",
        Path(__file__).parents[2]
        / "astrid"
        / "packs"
        / "video_editing"
        / "orchestrators"
        / "hype"
        / "project_adapter.py",
    ]
    forbidden = {"compose_standard_application", "derive_database_path", "UnitOfWork"}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }
        assert not forbidden & names, f"local authority remains in {path}"
