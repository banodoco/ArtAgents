"""Facade-boundary run-ownership characterization for ``rendering.render`` (T1.1).

Issue 1 rework: the leaf module
``astrid/packs/rendering/executors/render/run.py`` never calls
``prepare_project_run`` (pinned by ``test_run_module_never_prepares_project_run``
in ``test_legacy_renderer_characterization.py``), but the PUBLIC facade —
``run_executor(ExecutorRunRequest(executor_id="rendering.render", ...))``, i.e.
``astrid executors run rendering.render`` — goes through the executor runner,
which DOES own a project run whenever a project is resolved
(``astrid/core/execution/executor/runner.py::_prepare_project_request`` →
``astrid/core/project/run.py::prepare_project_run``; the gate lives in
``astrid/core/contracts/capability_runner.py::CapabilityRunner.run``).
``metadata.requires_timeline: false`` only skips timeline resolution; it does
not disable run ownership.

These tests pin that facade behavior. No real render ever happens: the render
subprocess (``python -m astrid.packs.rendering.executors.render.run``) is
replaced by a test-only no-op that writes ``hype.mp4`` at the ``--out`` path
and returns 0. The real ``rendering.render`` ExecutorDefinition is loaded from
the default registry so the runner, project-prepare, command expansion, and
finalize paths are the production ones.

Baseline recorded in ``.oracle/baseline.md`` (section 10).
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
from astrid.core.execution.executor.runner import ExecutorRunnerError, ExecutorRunRequest, run_executor
from astrid.core.foundation import project_paths as paths
from astrid.core.project.project import create_project
from astrid.core.project.run import resolve_record_path, write_run_record
from astrid.core.subprocess_env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV
from astrid.core.task import gate as task_gate
from astrid.core.task.plan import step_dir_for
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


def _run_json(projects_root: Path) -> dict:
    jsons = _run_jsons(projects_root)
    assert len(jsons) == 1, f"expected exactly one run.json, found {len(jsons)}"
    return json.loads(jsons[0].read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# standalone facade ownership
# ---------------------------------------------------------------------------


def test_facade_standalone_with_project_creates_one_run_json_and_rewrites_out_to_run_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`astrid executors run rendering.render --project demo` owns a project run.

    The runner's prepare step creates exactly one ``run.json`` at the run root
    and rewrites ``request.out`` (None) to ``context.run_root``, so the spawned
    render argv targets ``<run_root>/hype.mp4``.
    """
    projects_root, _ = _setup_project(tmp_path, monkeypatch)
    inputs = _write_project_inputs(projects_root)
    commands: list = []
    _noop_render_subprocess(monkeypatch, commands)

    result = run_executor(
        ExecutorRunRequest(
            executor_id="rendering.render",
            out=None,
            project="demo",
            inputs=inputs,
        ),
        load_default_registry(),
    )

    assert result.returncode == 0
    record = _run_json(projects_root)
    assert record["status"] == "completed"
    assert record["tool_id"] == "rendering.render"
    assert record["kind"] == "executor"
    assert record["metadata"]["project_resolution"] == "explicit"
    run_root = resolve_record_path(record["out"], "demo", root=projects_root)
    assert run_root == _run_jsons(projects_root)[0].parent
    assert result.run_root == run_root
    # The render subprocess wrote its output into the run root (out rewritten).
    assert (run_root / "hype.mp4").read_bytes() == b"fake-mp4"
    assert result.outputs["video"] == str(run_root / "hype.mp4")
    # The spawned argv targets the run root, not any caller-supplied out.
    assert len(commands) == 1
    argv = commands[0][0]
    out_value = argv[argv.index("--out") + 1]
    assert Path(out_value).resolve() == (run_root / "hype.mp4").resolve()
    # The render subprocess env carries the project-run marker.
    env = commands[0][2]
    assert env.get("ASTRID_PROJECT_RUN") == "1"
    assert env.get("ASTRID_PROJECT_SLUG") == "demo"


def test_facade_run_root_in_request_is_replaced_by_run_context_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller-supplied ``run_root`` is ignored for run creation.

    ``_prepare_project_request`` replaces ``request.run_root`` with the actual
    project run root (``projects/<slug>/runs/<run_id>``); the ledger is created
    there, never at the caller's path.
    """
    projects_root, _ = _setup_project(tmp_path, monkeypatch)
    inputs = _write_project_inputs(projects_root)
    caller_run_root = tmp_path / "caller-run-root"
    _noop_render_subprocess(monkeypatch, [])

    result = run_executor(
        ExecutorRunRequest(
            executor_id="rendering.render",
            out=None,
            project="demo",
            run_root=caller_run_root,
            inputs=inputs,
        ),
        load_default_registry(),
    )

    assert result.returncode == 0
    record = _run_json(projects_root)
    run_root = resolve_record_path(record["out"], "demo", root=projects_root)
    assert result.run_root == run_root
    assert run_root != caller_run_root.resolve()
    assert not (caller_run_root / "run.json").exists()
    assert not caller_run_root.exists() or list(caller_run_root.iterdir()) == []


# ---------------------------------------------------------------------------
# task-attached facade ownership
# ---------------------------------------------------------------------------


def test_facade_task_attached_reuses_run_context_without_new_run_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under a matching ASTRID_TASK_* context the facade attaches to the
    orchestrator's run: no NEW ``run.json`` is written (the parent run record
    is the only one) and the render argv targets the task step root.

    The task gate itself (``astrid/core/task/gate``) demands an active
    ``active_run.json`` for real task runs; that gate is separately
    characterized by the task-run suites, so here it is stubbed to pass.
    """
    projects_root, timeline = _setup_project(tmp_path, monkeypatch)
    _attach_task_run(monkeypatch, projects_root, timeline)
    monkeypatch.setattr(task_gate, "gate_command", lambda *args, **kwargs: None)
    inputs = _write_project_inputs(projects_root)
    commands: list = []
    _noop_render_subprocess(monkeypatch, commands)

    result = run_executor(
        ExecutorRunRequest(
            executor_id="rendering.render",
            out=None,
            project="demo",
            inputs=inputs,
        ),
        load_default_registry(),
    )

    assert result.returncode == 0
    step_root = step_dir_for("demo", PARENT_RUN_ID, TASK_STEP_ID, step_version=1, root=projects_root)
    # Orchestrator's run context is reused.
    assert result.run_root == step_root
    # No NEW run.json: only the orchestrator's parent run record exists.
    assert _run_jsons(projects_root) == [projects_root / "demo" / "runs" / PARENT_RUN_ID / "run.json"]
    assert not (step_root / "run.json").exists()
    # The render argv targets the task step root (out rewritten to run root).
    argv = commands[0][0]
    out_value = argv[argv.index("--out") + 1]
    assert Path(out_value).resolve() == (step_root / "hype.mp4").resolve()


def test_facade_task_attached_retains_caller_selected_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under attachment with an auto-resolved project, a caller-selected ``out``
    is RETAINED (not rewritten to the run root): the runner passes it through
    as ``record_out``/effective out while the ledger still attaches to the
    orchestrator's task step root.
    """
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
    step_root = step_dir_for("demo", PARENT_RUN_ID, TASK_STEP_ID, step_version=1, root=projects_root)
    # Run context is still the orchestrator's task step root.
    assert result.run_root == step_root
    # The caller-selected output is retained: render wrote under caller_out.
    assert (caller_out / "hype.mp4").read_bytes() == b"fake-mp4"
    argv = commands[0][0]
    out_value = argv[argv.index("--out") + 1]
    assert Path(out_value).resolve().is_relative_to(caller_out.resolve())
    # Still no NEW run.json.
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
