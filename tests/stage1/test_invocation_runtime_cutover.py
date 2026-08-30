"""Focused checks for SDK invocation's runtime-only admission path."""

from __future__ import annotations

import ast
from pathlib import Path

from astrid.sdk import invocation


class _Capability:
    id = "render.basic"


class _Tasks:
    def __init__(self) -> None:
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return type(
            "Result",
            (),
            {
                "ok": True,
                "data": {
                    "run_id": "run-1",
                    "task_id": "task-1",
                    "attempt_id": None,
                    "state": "queued",
                },
            },
        )()


class _Client:
    def __init__(self) -> None:
        self.tasks = _Tasks()


def test_kernel_invoke_admits_task_through_injected_runtime_client() -> None:
    client = _Client()
    result = invocation._kernel_invoke(
        _Capability(),
        kind="executor",
        project="demo",
        projects_root=Path("/unused/local/root"),
        inputs={"prompt": "hello"},
        outputs={"format": "json"},
        _client=client,
    )

    run_id, task_id, attempt_id, manifest, raw, ok, error = result
    assert (run_id, task_id, attempt_id, manifest, ok, error) == (
        "run-1",
        "task-1",
        "",
        None,
        True,
        None,
    )
    assert raw["kernel_run_id"] == "run-1"
    assert client.tasks.kwargs["project_id"] == "demo"
    assert client.tasks.kwargs["capability"] == "render.basic"
    assert client.tasks.kwargs["spec"]["inputs"] == {"prompt": "hello"}


def test_kernel_invoke_opens_runtime_without_project_root(monkeypatch) -> None:
    client = _Client()

    class _Opened:
        def __enter__(self):
            return client

        def __exit__(self, *exc_info):
            return False

    calls = []

    def open_runtime(*args, **kwargs):
        calls.append((args, kwargs))
        return _Opened()

    monkeypatch.setattr("astrid.sdk.client.AstridClient.open", open_runtime)
    invocation._kernel_invoke(
        _Capability(),
        kind="executor",
        project="demo",
        projects_root=Path("/unused/local/root"),
        inputs={},
        outputs={},
    )

    assert calls == [((), {})]


def test_retried_task_dispatch_has_no_local_execution_authority() -> None:
    """Retry callbacks never reopen the local writer or execute a pack."""
    source = Path(invocation.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "dispatch_retried_task"
    )
    names = {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name)
    }
    assert not {"UnitOfWork", "ExecutionService", "CapabilityTaskHandler"} & names


def test_retried_task_dispatch_uses_explicit_runtime_claim_client() -> None:
    class _Runtime:
        def __init__(self) -> None:
            self.calls = []

        def claim_next(self, **kwargs):
            self.calls.append(kwargs)
            return {"attempt_id": "attempt-1", "task_id": "task-1"}

    runtime = _Runtime()
    claim, completion = invocation.dispatch_retried_task(
        writer=object(),
        task_repo=object(),
        media_repo=object(),
        projects_root=Path("/never/opened"),
        task=object(),
        attempt=object(),
        idempotency_key="retry-1",
        runtime=runtime,
        executor_id="worker-1",
        capability_ids=["render.basic"],
    )

    assert claim == {"attempt_id": "attempt-1", "task_id": "task-1"}
    assert completion is None
    assert runtime.calls == [
        {
            "executor_id": "worker-1",
            "capability_ids": ["render.basic"],
            "idempotency_key": "retry-1:claim",
        }
    ]


def test_retried_task_dispatch_is_inert_without_runtime_client() -> None:
    assert invocation.dispatch_retried_task(
        writer=object(),
        task_repo=object(),
        media_repo=object(),
        projects_root=Path("/never/opened"),
        task=object(),
        attempt=object(),
        idempotency_key="retry-1",
    ) == (None, None)
