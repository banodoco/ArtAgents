"""Kernel/runner ownership boundary for the ``rendering.render`` facade.

Phase B made the kernel the only authoritative run/task ledger writer.  The
lower-level executor runner therefore consumes a kernel-supplied staging root;
it neither invents that root nor writes ``run.json``.  These tests exercise the
real command expansion and publication paths with only the media subprocess
replaced by a no-op.
"""

from __future__ import annotations

import json
import subprocess
from contextlib import nullcontext
from pathlib import Path

import pytest

from astrid.core.contracts.run_status import RunStatus
from astrid.core.execution.executor import runner as executor_runner
from astrid.core.execution.executor.registry import load_default_registry
from astrid.core.execution.executor.runner import (
    ExecutorRunnerError,
    ExecutorRunRequest,
    run_executor,
)
from astrid.core.foundation import project_paths as paths
from astrid.core.project.project import create_project
from astrid.core.project.run import step_dir_for, write_run_record
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


def _attach_task_run(
    monkeypatch: pytest.MonkeyPatch, projects_root: Path, timeline: dict
) -> None:
    """Create the orchestrator's parent run record + matching ASTRID_TASK_* env."""
    write_run_record(
        "demo",
        PARENT_RUN_ID,
        kind="task",
        status=RunStatus.RUNNING,
        timeline_id=timeline["ulid"],
    )
    monkeypatch.setenv(TASK_PROJECT_ENV, "demo")
    monkeypatch.setenv(TASK_RUN_ID_ENV, PARENT_RUN_ID)
    monkeypatch.setenv(TASK_STEP_ID_ENV, TASK_STEP_ID)


class _FakeLogs:
    stdout = None
    stderr = None


def _noop_render_subprocess(monkeypatch: pytest.MonkeyPatch, commands: list) -> None:
    """Replace the render subprocess (log-capture branch: explicit project)."""

    def fake_run_subprocess_with_capture(
        argv,
        *,
        cwd=None,
        env=None,
        stdout_log=None,
        stderr_log=None,
        live_stdout=None,
        live_stderr=None,
    ) -> int:
        argv_list = [str(part) for part in argv]
        commands.append((argv_list, cwd, dict(env or {})))
        out_path = Path(argv_list[argv_list.index("--out") + 1])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"fake-mp4")
        return 0

    monkeypatch.setattr(executor_runner, "run_subprocess_with_capture", fake_run_subprocess_with_capture)
    monkeypatch.setattr(
        executor_runner, "open_run_log_capture", lambda run_root, **kw: nullcontext(_FakeLogs())
    )


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


# ---------------------------------------------------------------------------
# standalone facade ownership
# ---------------------------------------------------------------------------


def test_lower_level_facade_requires_kernel_supplied_staging_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A direct runner call cannot silently recreate the retired ledger path."""
    projects_root, _ = _setup_project(tmp_path, monkeypatch)
    inputs = _write_project_inputs(projects_root)
    commands: list = []
    _noop_render_subprocess(monkeypatch, commands)

    with pytest.raises(ExecutorRunnerError, match="output or staging path"):
        run_executor(
            ExecutorRunRequest(
                executor_id="rendering.render",
                out=None,
                project="demo",
                inputs=inputs,
            ),
            load_default_registry(),
        )

    assert commands == []
    assert _run_jsons(projects_root) == []


def test_lower_level_facade_preserves_kernel_staging_without_writing_a_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner uses, but never takes ownership of, supplied staging."""
    projects_root, _ = _setup_project(tmp_path, monkeypatch)
    inputs = _write_project_inputs(projects_root)
    staging_root = tmp_path / "kernel-staging"
    commands: list = []
    _noop_render_subprocess(monkeypatch, commands)

    result = run_executor(
        ExecutorRunRequest(
            executor_id="rendering.render",
            out=None,
            project="demo",
            run_root=staging_root,
            inputs=inputs,
        ),
        load_default_registry(),
    )

    assert result.returncode == 0
    assert result.run_root == staging_root
    assert (staging_root / "hype.mp4").read_bytes() == b"fake-mp4"
    assert result.outputs["video"] == str(staging_root / "hype.mp4")
    assert _run_jsons(projects_root) == []
    assert not (staging_root / "run.json").exists()
    argv, _cwd, env = commands[0]
    assert Path(argv[argv.index("--out") + 1]).resolve() == (
        staging_root / "hype.mp4"
    ).resolve()
    assert env.get("ASTRID_PROJECT_RUN") == "1"
    assert env.get("ASTRID_PROJECT_SLUG") == "demo"


# ---------------------------------------------------------------------------
# task-attached facade ownership
# ---------------------------------------------------------------------------


def test_facade_task_attached_reuses_run_context_without_new_run_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under a matching ASTRID_TASK_* context the facade attaches to the
    orchestrator's run: no NEW ``run.json`` is written (the parent run record
    is the only one) and the render argv targets the task step root.

"""
    projects_root, timeline = _setup_project(tmp_path, monkeypatch)
    _attach_task_run(monkeypatch, projects_root, timeline)
    inputs = _write_project_inputs(projects_root)
    step_root = step_dir_for(
        "demo", PARENT_RUN_ID, TASK_STEP_ID, step_version=1, root=projects_root
    )
    commands: list = []
    _noop_render_subprocess(monkeypatch, commands)

    result = run_executor(
        ExecutorRunRequest(
            executor_id="rendering.render",
            out=None,
            project="demo",
            run_root=step_root,
            inputs=inputs,
        ),
        load_default_registry(),
    )

    assert result.returncode == 0
    # The kernel-supplied task step staging root is reused.
    assert result.run_root == step_root
    # No NEW run.json: only the orchestrator's parent run record exists.
    assert _run_jsons(projects_root) == [projects_root / "demo" / "runs" / PARENT_RUN_ID / "run.json"]
    assert not (step_root / "run.json").exists()
    # The render argv targets the task step root (out rewritten to run root).
    argv = commands[0][0]
    out_value = argv[argv.index("--out") + 1]
    assert Path(out_value).resolve() == (step_root / "hype.mp4").resolve()


def test_auto_resolved_facade_retains_caller_selected_output_without_new_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auto-resolution may retain output, but never makes the runner a ledger owner."""
    projects_root, timeline = _setup_project(tmp_path, monkeypatch)
    _attach_task_run(monkeypatch, projects_root, timeline)
    # Auto-resolve the project the way a session binding would.
    monkeypatch.setattr(
        executor_runner,
        "selected_project",
        lambda explicit: (explicit, "explicit") if explicit else ("demo", "attached"),
    )
    inputs = _write_project_inputs(projects_root)
    caller_out = tmp_path / "caller-out"
    commands: list = []
    _noop_render_subprocess_direct(monkeypatch, commands)

    result = run_executor(
        ExecutorRunRequest(
            executor_id="rendering.render",
            out=caller_out,
            project=None,
            inputs=inputs,
        ),
        load_default_registry(),
    )

    assert result.returncode == 0
    assert result.run_root is None
    # The caller-selected output is retained: render wrote under caller_out.
    assert (caller_out / "hype.mp4").read_bytes() == b"fake-mp4"
    argv = commands[0][0]
    out_value = argv[argv.index("--out") + 1]
    assert Path(out_value).resolve().is_relative_to(caller_out.resolve())
    # The pre-existing parent remains the only authoritative ledger.
    assert _run_jsons(projects_root) == [projects_root / "demo" / "runs" / PARENT_RUN_ID / "run.json"]


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
