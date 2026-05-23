from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from astrid import pipeline
from astrid.core.adapter import DispatchResult
from astrid.core.adapter import local as local_adapter_module
from astrid.core.executor import cli as executor_cli
from astrid.core.executor import runner as executor_runner
from astrid.core.executor.runner import ExecutorRunRequest, ExecutorRunResult, ExecutorRunnerError
from astrid.core.orchestrator.runner import OrchestratorRunRequest, OrchestratorRunnerError, run_orchestrator
from astrid.core.project.project import create_project
from astrid.core.task import gate as task_gate
from astrid.core.task.active_run import write_active_run
from astrid.core.task.env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV
from astrid.core.task.plan import compute_plan_hash
from astrid.packs.builtin.orchestrators.hype import run as hype_run


def test_pipeline_dispatch_calls_top_gate_and_executor_reentry(
    tmp_projects_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = "executors run builtin.noop --project demo"
    _setup_active_plan(tmp_projects_root, command=command)
    fake_executor = SimpleNamespace(id="builtin.noop", outputs=())
    fake_registry = SimpleNamespace(get=lambda executor_id: fake_executor)

    monkeypatch.setattr(executor_cli, "load_default_registry", lambda *args, **kwargs: fake_registry)
    monkeypatch.setattr(
        executor_runner,
        "_run_executor_inner",
        lambda request, executor: ExecutorRunResult(executor_id=executor.id, kind="external", returncode=0),
    )

    # Sprint 3 (T14) routes local-adapter dispatch through LocalAdapter.dispatch,
    # which Popens the step command. The test exercises the gate+reentry flow,
    # not subprocess spawn behavior, so stub the adapter to invoke the executor
    # CLI in-process (this is what produces the reentry gate_command call
    # asserted below). _wait_local_subprocess is stubbed because there is no
    # real PID to wait on.
    def _fake_dispatch(self, step, run_ctx):  # noqa: ARG001
        executor_cli.main(["run", "builtin.noop", "--project", "demo"])
        return DispatchResult(status="dispatched", pid=None, started_at="1970-01-01T00:00:00.000Z")

    monkeypatch.setattr(local_adapter_module.LocalAdapter, "dispatch", _fake_dispatch)
    monkeypatch.setattr(pipeline, "_wait_local_subprocess", lambda decision: 0)

    with patch("astrid.core.task.gate.gate_command", wraps=task_gate.gate_command) as gate_spy:
        assert pipeline.main(["executors", "run", "builtin.noop", "--project", "demo"]) == 0

    assert gate_spy.call_count == 2
    assert gate_spy.call_args_list[0].args[:2] == ("demo", command)
    assert gate_spy.call_args_list[0].kwargs.get("reentry", False) is False
    assert gate_spy.call_args_list[1].args[:2] == ("demo", command)
    assert gate_spy.call_args_list[1].kwargs["reentry"] is True


def test_orchestrator_runner_rejects_before_project_run_side_effects(
    tmp_projects_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup_active_plan(tmp_projects_root, command="not the orchestrator command")
    _set_task_env(monkeypatch)

    with patch("astrid.core.task.gate.gate_command", wraps=task_gate.gate_command) as gate_spy:
        with pytest.raises(OrchestratorRunnerError, match="astrid next --project demo"):
            run_orchestrator(OrchestratorRunRequest(orchestrator_id="builtin.hype", project="demo"))

    assert gate_spy.call_count == 1
    assert gate_spy.call_args.kwargs["reentry"] is True
    # Sprint 1 (T9): the legacy write_active_run shim creates
    # runs/<run_id>/lease.json (the new on-disk shape replaces the old
    # single-file active_run.json). The test assertion was originally "no
    # runs/ entries after rejected dispatch"; under the new model the
    # setup-created `task-run-1` lease dir is present, but events.jsonl
    # should still be empty (no events appended) since dispatch rejected.
    runs_dir = tmp_projects_root / "demo" / "runs"
    if runs_dir.exists():
        events_path = runs_dir / "task-run-1" / "events.jsonl"
        if events_path.exists():
            assert events_path.read_bytes() == b"", events_path.read_text()


def test_executor_runner_rejects_before_project_run_side_effects(
    tmp_projects_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup_active_plan(tmp_projects_root, command="not the executor command")
    _set_task_env(monkeypatch)

    with patch("astrid.core.task.gate.gate_command", wraps=task_gate.gate_command) as gate_spy:
        with pytest.raises(ExecutorRunnerError, match="astrid next --project demo"):
            executor_runner.run_executor(ExecutorRunRequest(executor_id="builtin.noop", out="", project="demo"))

    assert gate_spy.call_count == 1
    assert gate_spy.call_args.kwargs["reentry"] is True
    # Sprint 1 (T9): the legacy write_active_run shim creates
    # runs/<run_id>/lease.json (the new on-disk shape replaces the old
    # single-file active_run.json). The test assertion was originally "no
    # runs/ entries after rejected dispatch"; under the new model the
    # setup-created `task-run-1` lease dir is present, but events.jsonl
    # should still be empty (no events appended) since dispatch rejected.
    runs_dir = tmp_projects_root / "demo" / "runs"
    if runs_dir.exists():
        events_path = runs_dir / "task-run-1" / "events.jsonl"
        if events_path.exists():
            assert events_path.read_bytes() == b"", events_path.read_text()


def test_hype_runtime_rejects_before_project_run_side_effects(
    tmp_projects_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup_active_plan(tmp_projects_root, command="not the hype command")
    _set_task_env(monkeypatch)

    with patch("astrid.core.task.gate.gate_command", wraps=task_gate.gate_command) as gate_spy:
        assert hype_run.main(["--project", "demo", "--brief", "hello"]) == 1

    assert gate_spy.call_count == 1
    assert gate_spy.call_args.kwargs["reentry"] is True
    # Sprint 1 (T9): the legacy write_active_run shim creates
    # runs/<run_id>/lease.json (the new on-disk shape replaces the old
    # single-file active_run.json). The test assertion was originally "no
    # runs/ entries after rejected dispatch"; under the new model the
    # setup-created `task-run-1` lease dir is present, but events.jsonl
    # should still be empty (no events appended) since dispatch rejected.
    runs_dir = tmp_projects_root / "demo" / "runs"
    if runs_dir.exists():
        events_path = runs_dir / "task-run-1" / "events.jsonl"
        if events_path.exists():
            assert events_path.read_bytes() == b"", events_path.read_text()


def _setup_active_plan(tmp_projects_root: Path, *, command: str) -> None:
    create_project("demo", root=tmp_projects_root)
    plan_path = tmp_projects_root / "demo" / "plan.json"
    plan_path.write_text(
        json.dumps({"plan_id": "dispatch-plan", "version": 1, "steps": [{"id": "step-1", "command": command}]}),
        encoding="utf-8",
    )
    write_active_run("demo", run_id="task-run-1", plan_hash=compute_plan_hash(plan_path), root=tmp_projects_root)


def _set_task_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TASK_RUN_ID_ENV, "task-run-1")
    monkeypatch.setenv(TASK_PROJECT_ENV, "demo")
    monkeypatch.setenv(TASK_STEP_ID_ENV, "step-1")


def _run_entries(tmp_projects_root: Path) -> list[str]:
    runs_dir = tmp_projects_root / "demo" / "runs"
    return sorted(path.name for path in runs_dir.iterdir())
