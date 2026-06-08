"""Executor task-entry contracts for env-bound task runs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lifecycle_fixtures import setup_run  # noqa: E402

from astrid.core.contracts.schema import CommandInputArg, CommandSpec, Port
from astrid.core.executor.runner import ExecutorRunRequest, run_executor
from astrid.core.executor.schema import ExecutorDefinition
from astrid.core.task.env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV
from astrid.core.task.events import append_event, make_step_dispatched_event, read_events


_BODY_EXECUTOR = '''from astrid.core.orchestrate import orchestrator, code
@orchestrator("demo.executor_entry")
def main():
    return [code("render", argv=[
        "executors", "run", "local.echo",
        "--out", "/tmp/task-out",
        "--input", "first=one",
        "--input", "second=two",
        "--python-exec", "/usr/bin/python3",
        "--dry-run",
    ])]
'''


class _Registry:
    def get(self, executor_id: str) -> ExecutorDefinition:
        assert executor_id == "local.echo"
        return ExecutorDefinition(
            id="local.echo",
            name="Echo",
            kind="external",
            version="1",
            inputs=(
                Port(name="first", required=True),
                Port(name="second", required=True),
            ),
            command=CommandSpec(argv=("echo", "{first}", "{second}", "{python_exec}", "{out}")),
        )


class _RepeatRegistry:
    def get(self, executor_id: str) -> ExecutorDefinition:
        assert executor_id == "local.echo"
        return ExecutorDefinition(
            id="local.echo",
            name="Echo",
            kind="external",
            version="1",
            inputs=(
                Port(name="tag", required=True),
                Port(name="optional_note", required=False),
            ),
            command=CommandSpec(
                argv=("echo", "start"),
                input_args=(
                    CommandInputArg(input="tag", flag="--tag", repeatable=True),
                    CommandInputArg(input="optional_note", flag="--note", optional=True),
                ),
            ),
        )


def test_executor_run_enters_task_from_env_preserving_full_runner_argv(
    tmp_path: Path, monkeypatch
) -> None:
    _packs, projects = setup_run(
        tmp_path,
        "demo",
        "executor_entry",
        _BODY_EXECUTOR,
        "demo.executor_entry",
        run_id="r-exec",
    )
    argv = (
        "executors", "run", "local.echo",
        "--out", "/tmp/task-out",
        "--input", "first=one",
        "--input", "second=two",
        "--python-exec", "/usr/bin/python3",
        "--dry-run",
    )
    monkeypatch.setenv(TASK_PROJECT_ENV, "p")
    monkeypatch.setenv(TASK_RUN_ID_ENV, "r-exec")
    monkeypatch.setenv(TASK_STEP_ID_ENV, "render")
    events_path = projects / "p" / "runs" / "r-exec" / "events.jsonl"
    append_event(events_path, make_step_dispatched_event("render", " ".join(argv), adapter="local"))

    result = run_executor(
        ExecutorRunRequest(
            executor_id="local.echo",
            out="/tmp/task-out",
            inputs={"first": "one", "second": "two"},
            dry_run=True,
            python_exec="/usr/bin/python3",
            argv=argv,
        ),
        _Registry(),  # type: ignore[arg-type]
    )

    assert result.dry_run is True
    assert result.command == ("echo", "one", "two", "/usr/bin/python3", str(Path("/tmp/task-out").resolve()))
    events = read_events(events_path)
    dispatched = [event for event in events if event.get("kind") == "step_dispatched"]
    assert dispatched[-1]["command"] == " ".join(argv)
    assert "--project" not in dispatched[-1]["command"]


def test_executor_task_env_rejects_shortened_runner_argv(tmp_path: Path, monkeypatch) -> None:
    setup_run(
        tmp_path,
        "demo",
        "executor_entry",
        _BODY_EXECUTOR,
        "demo.executor_entry",
        run_id="r-exec-short",
    )
    monkeypatch.setenv(TASK_PROJECT_ENV, "p")
    monkeypatch.setenv(TASK_RUN_ID_ENV, "r-exec-short")
    monkeypatch.setenv(TASK_STEP_ID_ENV, "render")

    try:
        run_executor(
            ExecutorRunRequest(
                executor_id="local.echo",
                out="/tmp/task-out",
                inputs={"first": "one", "second": "two"},
                dry_run=True,
                python_exec="/usr/bin/python3",
                argv=("executors", "run", "local.echo", "--out", "/tmp/task-out", "--dry-run"),
            ),
            _Registry(),  # type: ignore[arg-type]
        )
    except Exception as exc:
        assert "incoming command does not match plan[cursor]" in str(exc)
    else:
        raise AssertionError("shortened executor argv was accepted")


def test_executor_reentry_preserves_ordered_repeated_inputs_through_gate_and_expansion(
    tmp_path: Path, monkeypatch
) -> None:
    body = '''from astrid.core.orchestrate import orchestrator, code
@orchestrator("demo.executor_repeat")
def main():
    return [code("render", argv=[
        "executors", "run", "local.echo",
        "--out", "/tmp/task-out",
        "--input", "tag=alpha",
        "--input", "tag=beta",
        "--dry-run",
    ])]
'''
    _packs, projects = setup_run(
        tmp_path,
        "demo",
        "executor_repeat",
        body,
        "demo.executor_repeat",
        run_id="r-exec-repeat",
    )
    argv = (
        "executors", "run", "local.echo",
        "--out", "/tmp/task-out",
        "--input", "tag=alpha",
        "--input", "tag=beta",
        "--dry-run",
    )
    monkeypatch.setenv(TASK_PROJECT_ENV, "p")
    monkeypatch.setenv(TASK_RUN_ID_ENV, "r-exec-repeat")
    monkeypatch.setenv(TASK_STEP_ID_ENV, "render")
    events_path = projects / "p" / "runs" / "r-exec-repeat" / "events.jsonl"
    append_event(events_path, make_step_dispatched_event("render", " ".join(argv), adapter="local"))

    result = run_executor(
        ExecutorRunRequest(
            executor_id="local.echo",
            out="/tmp/task-out",
            inputs={"tag": ["alpha", "beta"]},
            dry_run=True,
            argv=argv,
        ),
        _RepeatRegistry(),  # type: ignore[arg-type]
    )

    assert result.command == ("echo", "start", "--tag", "alpha", "--tag", "beta")
    dispatched = [event for event in read_events(events_path) if event.get("kind") == "step_dispatched"]
    assert dispatched[-1]["command"].split("--input")[1:] == [" tag=alpha ", " tag=beta --dry-run"]
