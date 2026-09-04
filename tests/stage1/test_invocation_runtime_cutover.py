"""Focused checks for SDK invocation's runtime-only admission path."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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


def test_kernel_invoke_forwards_storage_estimate_to_runtime_and_audit_metadata() -> None:
    client = _Client()
    invocation._kernel_invoke(
        _Capability(),
        kind="executor",
        project="demo",
        inputs={"prompt": "hello"},
        outputs={},
        admission_metadata={
            "storage_estimate": {"estimated_total_bytes": 123},
            "runtime_enforced": True,
        },
        storage_estimate={"scratch_bytes": 100, "output_bytes": 23},
        _client=client,
    )

    spec = client.tasks.kwargs["spec"]
    assert spec["inputs"] == {"prompt": "hello"}
    assert spec["admission_metadata"] == {
        "storage_estimate": {"estimated_total_bytes": 123},
        "runtime_enforced": True,
    }
    assert client.tasks.kwargs["storage_estimate"] == {
        "scratch_bytes": 100,
        "output_bytes": 23,
    }


def test_kernel_invoke_authorizes_digest_when_media_id_is_not_an_object_id() -> None:
    client = _Client()
    digest = "a" * 64
    invocation._kernel_invoke(
        _Capability(),
        kind="executor",
        project="demo",
        inputs={
            "timeline_snapshot": {
                "registry": {
                    "assets": {
                        "clip": {
                            "media_id": "human-facing-media-id",
                            "object_id": f"sha256:{digest}",
                            "content_sha256": digest,
                        }
                    }
                }
            }
        },
        outputs={},
        _client=client,
    )

    assert client.tasks.kwargs["input_manifest"] == [f"sha256:{digest}"]


def test_kernel_invoke_requires_explicit_runtime_client() -> None:
    import pytest

    with pytest.raises(invocation.CapabilityInvocationError, match="explicit generated"):
        invocation._kernel_invoke(
            _Capability(),
            kind="executor",
            project="demo",
            inputs={},
            outputs={},
        )


def test_wait_for_kernel_task_returns_runtime_outputs(monkeypatch) -> None:
    states = iter(
        [
            {"state": "running", "attempt_id": "attempt-1"},
            {
                "state": "succeeded",
                "attempt_id": "attempt-1",
                "result": {
                    "outputs": [
                        {
                            "name": "video",
                            "digest": "sha256:" + "a" * 64,
                            "media_type": "video/mp4",
                            "size": 123,
                        }
                    ]
                },
            },
        ]
    )
    tasks = SimpleNamespace(
        show=lambda _task_id: SimpleNamespace(ok=True, data=next(states))
    )
    monkeypatch.setattr(invocation.time, "sleep", lambda _seconds: None)

    raw, ok, attempt_id = invocation._wait_for_kernel_task(
        SimpleNamespace(tasks=tasks),
        task_id="task-1",
        run_id="run-1",
        timeout_seconds=10,
        poll_seconds=0.1,
    )

    assert ok is True
    assert attempt_id == "attempt-1"
    assert raw["state"] == "completed"
    assert raw["outputs"]["artifacts"][0]["name"] == "video"


def test_wait_for_kernel_task_propagates_terminal_failure() -> None:
    tasks = SimpleNamespace(
        show=lambda _task_id: SimpleNamespace(
            ok=True,
            data={
                "state": "failed",
                "attempt_id": "attempt-2",
                "result": {"error": {"message": "encoder exploded"}},
            },
        )
    )

    raw, ok, attempt_id = invocation._wait_for_kernel_task(
        SimpleNamespace(tasks=tasks),
        task_id="task-2",
        run_id="run-2",
        timeout_seconds=10,
        poll_seconds=0.1,
    )

    assert ok is False
    assert attempt_id == "attempt-2"
    assert raw["error"]["code"] == "task_failed"
    assert raw["error"]["message"] == "encoder exploded"


def test_wait_for_kernel_task_rejects_non_finite_timeout() -> None:
    import pytest

    with pytest.raises(invocation.CapabilityValidationError, match="positive"):
        invocation._wait_for_kernel_task(
            SimpleNamespace(tasks=SimpleNamespace(show=lambda _task_id: None)),
            task_id="task-3",
            run_id="run-3",
            timeout_seconds=float("nan"),
            poll_seconds=0.1,
        )
