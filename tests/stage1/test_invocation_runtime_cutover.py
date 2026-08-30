"""Focused checks for SDK invocation's runtime-only admission path."""

from __future__ import annotations

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
