"""Single-ledger boundary tests for the internal ``rendering.render`` runner.

Project-scoped public calls are admitted by the kernel.  The internal runner
receives a kernel-owned staging directory and must never create or finalize a
second filesystem ``run.json`` ledger.  These tests use the production
executor definition while replacing only the render subprocess.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from astrid.core.execution.executor import runner as executor_runner
from astrid.core.execution.executor.registry import load_default_registry
from astrid.core.execution.executor.runner import (
    ExecutorRunnerError,
    ExecutorRunRequest,
    run_executor,
)
from astrid.core.foundation import project_paths as paths
from astrid.core.project.project import create_project
from astrid.core.subprocess_env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV
from astrid.core.timeline.crud import create_timeline

PARENT_RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAT"
TASK_STEP_ID = "render"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ASTRID_SESSION_ID",
        "ASTRID_PROJECT_RUN",
        "ASTRID_TASK_RUN_ID",
        "ASTRID_TASK_PROJECT",
        "ASTRID_TASK_STEP_ID",
        "ASTRID_TASK_ITEM_ID",
        "ASTRID_TASK_ITERATION",
        "ASTRID_THREADS_OFF",
        "ASTRID_THREAD_INHERITED",
        "ASTRID_THREAD_ID",
        "ASTRID_RUN_ID",
        "ASTRID_PARENT_RUN_ID",
    ):
        monkeypatch.delenv(name, raising=False)


def _setup_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, with_timeline: bool = True
) -> tuple[Path, dict | None]:
    """Create a temp project and return ``(projects_root, timeline)``."""
    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_env(monkeypatch)
    create_project("demo")
    timeline = create_timeline("demo", "main", is_default=True) if with_timeline else None
    return projects_root, timeline


def _write_project_inputs(projects_root: Path) -> dict[str, str]:
    """Write timeline/assets inputs inside the project tree (ownership gate)."""
    inputs_dir = projects_root / "demo" / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    timeline = inputs_dir / "hype.timeline.json"
    assets = inputs_dir / "hype.assets.json"
    timeline.write_text(
        json.dumps({"theme": "banodoco-default", "tracks": [], "clips": []}),
        encoding="utf-8",
    )
    assets.write_text(json.dumps({"assets": {}}), encoding="utf-8")
    return {"timeline": str(timeline), "assets_registry": str(assets)}


def _attach_task_run(monkeypatch: pytest.MonkeyPatch, timeline: dict) -> None:
    """Set the runtime-owned parent binding without a local projection."""
    del timeline
    monkeypatch.setenv(TASK_PROJECT_ENV, "demo")
    monkeypatch.setenv(TASK_RUN_ID_ENV, PARENT_RUN_ID)
    monkeypatch.setenv(TASK_STEP_ID_ENV, TASK_STEP_ID)


def _noop_render_subprocess_direct(monkeypatch: pytest.MonkeyPatch, commands: list) -> None:
    """Replace the render subprocess (plain subprocess.run branch: auto-resolved)."""

    real_run = subprocess.run

    def fake_run(argv, **kwargs):
        argv_list = [str(part) for part in argv]
        commands.append((argv_list, kwargs.get("cwd"), dict(kwargs.get("env") or {})))
        if "astrid.packs.rendering.executors.render.run" in " ".join(argv_list):
            out_path = Path(argv_list[argv_list.index("--out") + 1])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(b"fake-mp4")
            return subprocess.CompletedProcess(argv_list, 0, stdout="", stderr="")
        return real_run(argv, **kwargs)

    monkeypatch.setattr(executor_runner.subprocess, "run", fake_run)


def _run_jsons(projects_root: Path) -> list[Path]:
    return sorted((projects_root / "demo" / "runs").glob("**/run.json"))


def test_direct_project_runner_requires_kernel_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root, _ = _setup_project(tmp_path, monkeypatch)
    inputs = _write_project_inputs(projects_root)
    with pytest.raises(ExecutorRunnerError, match="requires kernel admission"):
        run_executor(
            ExecutorRunRequest(
                executor_id="rendering.render",
                out=None,
                project="demo",
                inputs=inputs,
            ),
            load_default_registry(),
        )
    assert _run_jsons(projects_root) == []


def test_kernel_admitted_runner_uses_staging_without_filesystem_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root, _ = _setup_project(tmp_path, monkeypatch)
    inputs = _write_project_inputs(projects_root)
    staging = tmp_path / "kernel-staging"
    commands: list = []
    _noop_render_subprocess_direct(monkeypatch, commands)

    result = run_executor(
        ExecutorRunRequest(
            executor_id="rendering.render",
            out=staging,
            project="demo",
            inputs=inputs,
            project_was_auto_resolved=True,
        ),
        load_default_registry(),
    )

    assert result.returncode == 0
    assert result.run_root is None
    assert (staging / "hype.mp4").read_bytes() == b"fake-mp4"
    assert result.outputs["video"] == str(staging / "hype.mp4")
    assert _run_jsons(projects_root) == []
    assert not (staging / "run.json").exists()
    assert len(commands) == 1


# ---------------------------------------------------------------------------
# task-attached facade ownership
# ---------------------------------------------------------------------------


def test_attached_runner_does_not_create_a_secondary_filesystem_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root, timeline = _setup_project(tmp_path, monkeypatch)
    assert timeline is not None
    _attach_task_run(monkeypatch, timeline)
    inputs = _write_project_inputs(projects_root)
    staging = tmp_path / "attached-kernel-staging"
    commands: list = []
    _noop_render_subprocess_direct(monkeypatch, commands)

    result = run_executor(
        ExecutorRunRequest(
            executor_id="rendering.render",
            out=staging,
            project="demo",
            inputs=inputs,
            project_was_auto_resolved=True,
        ),
        load_default_registry(),
    )

    assert result.returncode == 0
    assert result.run_root is None
    assert (staging / "hype.mp4").read_bytes() == b"fake-mp4"
    assert _run_jsons(projects_root) == []
    assert not (staging / "run.json").exists()


def test_auto_resolved_project_retains_kernel_selected_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root, _ = _setup_project(tmp_path, monkeypatch)
    monkeypatch.setattr(
        executor_runner,
        "selected_project",
        lambda explicit: (explicit, "explicit") if explicit else ("demo", "attached"),
    )
    inputs = _write_project_inputs(projects_root)
    staging = tmp_path / "auto-resolved-staging"
    commands: list = []
    _noop_render_subprocess_direct(monkeypatch, commands)

    result = run_executor(
        ExecutorRunRequest(
            executor_id="rendering.render",
            out=staging,
            project=None,
            inputs=inputs,
        ),
        load_default_registry(),
    )

    assert result.returncode == 0
    assert result.run_root is None
    assert (staging / "hype.mp4").read_bytes() == b"fake-mp4"
    argv = commands[0][0]
    out_value = argv[argv.index("--out") + 1]
    assert Path(out_value).resolve().is_relative_to(staging.resolve())
    assert _run_jsons(projects_root) == []


# ---------------------------------------------------------------------------
# no project
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("out", [None, "tmp/out"])
def test_facade_without_project_fails_before_creating_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, out
) -> None:
    """With no project resolved the facade fails fast with an
    ``ExecutorRunnerError`` (project required) and creates NO ledger anywhere.
    """
    projects_root, _ = _setup_project(tmp_path, monkeypatch)
    inputs = _write_project_inputs(projects_root)
    out_arg = None if out is None else tmp_path / "out"

    with pytest.raises(ExecutorRunnerError, match="project required"):
        run_executor(
            ExecutorRunRequest(
                executor_id="rendering.render",
                out=out_arg,
                project=None,
                inputs=inputs,
            ),
            load_default_registry(),
        )

    assert _run_jsons(projects_root) == []
    if out_arg is not None:
        assert not (out_arg / "run.json").exists()
