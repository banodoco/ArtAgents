from __future__ import annotations

import io
import json
import threading

import pytest

from astrid.core.execution.generic_host import GenericPackHost
from astrid.core.execution.persistent_supervisor import (
    PersistentJsonlSupervisor,
    SupervisorError,
)


def frame(op: str, *, task_id: str = "task-1", attempt_id: str = "attempt-1", lease_id: str = "lease-1", fence: int = 1, **extra):
    return {
        "op": op,
        "task_id": task_id,
        "attempt_id": attempt_id,
        "lease_id": lease_id,
        "fence": fence,
        **extra,
    }


def test_bounded_launch_persists_running_state(tmp_path):
    launches = []
    supervisor = PersistentJsonlSupervisor(
        tmp_path / "supervisor.jsonl",
        launch=lambda value: launches.append(value["task_id"]) or {"pid": 41},
        max_concurrency=1,
    )

    first = supervisor.handle({**frame("start"), "task": {"id": "task-1"}})
    second = supervisor.handle({**frame("start", task_id="task-2", attempt_id="attempt-2", lease_id="lease-2"), "task": {"id": "task-2"}})

    assert first["status"] == "running"
    assert second == {
        "attempt_id": "attempt-2",
        "fence": 1,
        "lease_id": "lease-2",
        "ok": True,
        "retryable": True,
        "status": "busy",
        "task_id": "task-2",
    }
    assert launches == ["task-1"]
    assert json.loads((tmp_path / "supervisor.jsonl").read_text().splitlines()[0])["event"] == "started"


def test_jsonl_framing_returns_one_response_per_input_line(tmp_path):
    supervisor = PersistentJsonlSupervisor(tmp_path / "supervisor.jsonl", max_frame_bytes=128)
    source = io.StringIO(
        json.dumps({"op": "status", "task_id": "missing"}) + "\n"
        + "not-json\n"
        + ("x" * 200) + "\n"
    )
    sink = io.StringIO()

    assert supervisor.serve(source, sink) == 3
    responses = [json.loads(line) for line in sink.getvalue().splitlines()]
    assert len(responses) == 3
    assert responses[0] == {"ok": True, "status": "unknown", "task_id": "missing"}
    assert responses[1]["ok"] is False
    assert responses[2] == {"error": "frame exceeds configured bound", "ok": False}


def test_lease_and_fence_are_required_and_stale_frames_fail_closed(tmp_path):
    heartbeats = []
    supervisor = PersistentJsonlSupervisor(
        tmp_path / "supervisor.jsonl",
        heartbeat=lambda value: heartbeats.append(value["fence"]),
    )
    supervisor.handle(frame("start"))

    assert supervisor.handle(frame("heartbeat"))["status"] == "running"
    assert heartbeats == [1]
    stale = supervisor.process_line(json.dumps(frame("heartbeat", fence=0)) + "\n")
    assert json.loads(stale)["ok"] is False
    with pytest.raises(SupervisorError, match="lease/fence requires attempt_id"):
        supervisor.handle({"op": "start", "task_id": "task-2", "lease_id": "lease-2", "fence": 1})


def test_restart_reclaims_durable_running_attempt_before_new_fence(tmp_path):
    launched = []
    reclaimed = []
    state = tmp_path / "supervisor.jsonl"
    first = PersistentJsonlSupervisor(state, launch=lambda value: launched.append(value["task_id"]))
    first.handle({**frame("start"), "task": {"id": "task-1"}})

    restarted = PersistentJsonlSupervisor(
        state,
        reclaim=lambda value: reclaimed.append((value["task_id"], value["fence"])),
        launch=lambda value: launched.append(value["task_id"]),
    )
    evidence = restarted.reclaim_orphans()
    assert evidence[0]["status"] == "reclaimed"
    assert reclaimed == [("task-1", 1)]
    with pytest.raises(SupervisorError, match="advance the prior fence"):
        restarted.handle({**frame("start"), "task": {"id": "task-1"}})

    relaunched = restarted.handle({
        **frame("start", attempt_id="attempt-2", lease_id="lease-2", fence=2),
        "task": {"id": "task-1"},
    })
    assert relaunched["status"] == "running"
    assert launched == ["task-1", "task-1"]


def test_terminal_failure_is_exactly_once_across_duplicates_and_restart(tmp_path):
    failures = []
    state = tmp_path / "supervisor.jsonl"
    supervisor = PersistentJsonlSupervisor(
        state,
        launch=lambda value: None,
        fail=lambda value: failures.append((value["task_id"], value["fence"], value["error"])),
    )
    supervisor.handle(frame("start"))
    first = supervisor.handle(frame("fail", error="fake child crashed"))
    duplicate = supervisor.handle(frame("fail", error="different wording"))

    restarted = PersistentJsonlSupervisor(
        state,
        fail=lambda value: failures.append((value["task_id"], value["fence"], value["error"])),
    )
    after_restart = restarted.handle(frame("fail", error="third wording"))

    assert first["status"] == duplicate["status"] == after_restart["status"] == "failed"
    assert duplicate["duplicate"] is True
    assert after_restart["duplicate"] is True
    assert failures == [("task-1", 1, "fake child crashed")]
    events = [json.loads(line)["event"] for line in state.read_text().splitlines()]
    assert events.count("terminal_failure") == 1
    assert events.count("failure_delivery") == 1


def test_transcript_captures_fenced_cpu_lifecycle(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    supervisor = PersistentJsonlSupervisor(state, launch=lambda value: {"fake": True})
    source = io.StringIO(
        json.dumps({**frame("start"), "task": {"id": "task-1"}}) + "\n"
        + json.dumps(frame("heartbeat")) + "\n"
        + json.dumps(frame("complete", result={"answer": 42})) + "\n"
        + json.dumps(frame("status")) + "\n"
    )
    sink = io.StringIO()

    supervisor.serve(source, sink)
    responses = [json.loads(line) for line in sink.getvalue().splitlines()]
    assert [item["status"] for item in responses] == ["running", "running", "completed", "completed"]
    assert responses[2]["fence"] == 1
    transcript = [json.loads(line) for line in state.read_text().splitlines()]
    assert [event["event"] for event in transcript] == ["started", "heartbeat", "completed"]

def test_generic_host_persistent_adapter_runs_cpu_fake_task(tmp_path):
    pack = tmp_path / "echo"
    pack.mkdir(parents=True)
    (pack / "executor.yaml").write_text(
        json.dumps({
            "schema_version": 1,
            "id": "test.echo",
            "name": "Echo",
            "kind": "external",
            "version": "1.0",
            "command": {
                "argv": [
                    "{python_exec}",
                    "-c",
                    "from pathlib import Path; Path('{out}/answer.txt').write_text('ok')",
                ]
            },
            "outputs": [
                {
                    "name": "answer",
                    "type": "file",
                    "path_template": "{out}/answer.txt",
                    "artifact_type": "text/plain",
                }
            ],
            "metadata": {"resource_keys": ["cpu"]},
        }),
        encoding="utf-8",
    )

    class Runtime:
        def __init__(self):
            self.tasks = {}
            self.heartbeats = []
            self.settlements = []

        def health(self):
            return {"runtime_epoch": 1}

        def task(self, task_id):
            return self.tasks[task_id]

        def heartbeat(self, task_id, lease_id, *, attempt_id, fence):
            self.heartbeats.append((task_id, lease_id, attempt_id, fence))

        def upload_object(self, path, *, project_id, media_type, filename=None):
            return type(
                "Object",
                (),
                {"object_id": "fake-object", "digest": "d" * 64, "size": 2},
            )()

        def settle(self, task_id, lease_id, **payload):
            self.settlements.append(payload)
            return {"task": {"id": task_id, "status": "completed"}}

        def fail(self, *args, **kwargs):
            raise AssertionError("CPU fake task should not fail")

    runtime = Runtime()
    task = {
        "task": {
            "id": "task-1",
            "capability": "test.echo",
            "project_id": "demo",
            "spec": {"spec": {"inputs": {}}},
        }
    }
    runtime.tasks["task-1"] = task
    host = GenericPackHost(pack_roots=[tmp_path], client=runtime)
    host.discover()
    supervisor = host.persistent_supervisor(tmp_path / "supervisor.jsonl")

    response = supervisor.handle({
        **frame("run", attempt_id="attempt-1", lease_id="lease-1"),
        "task": task,
    })

    assert response["status"] == "completed"
    assert runtime.heartbeats == [("task-1", "lease-1", "attempt-1", 1)]
    assert len(runtime.settlements) == 1

def test_warm_reuse_and_cold_release_match_fake_runner_contract(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    launches = []
    supervisor = PersistentJsonlSupervisor(
        state,
        launch=lambda value: launches.append(value["task_id"]) or {"status": "succeeded"},
    )

    cold = supervisor.handle({
        **frame("run", task_id="task-1"),
        "fingerprint": "runner-1",
        "warmth_identity": "warm-1",
    })
    warm = supervisor.handle({
        **frame("run", task_id="task-2", attempt_id="attempt-2", lease_id="lease-2"),
        "fingerprint": "runner-1",
        "warmth_identity": "warm-1",
    })
    switched = supervisor.handle({
        **frame("run", task_id="task-3", attempt_id="attempt-3", lease_id="lease-3"),
        "fingerprint": "runner-2",
        "warmth_identity": "warm-2",
    })

    assert cold["lifecycle"] == "cold"
    assert cold["warm_reused"] is False
    assert warm["lifecycle"] == "warm"
    assert warm["warm_reused"] is True
    assert switched["lifecycle"] == "cold"
    assert launches == ["task-1", "task-2", "task-3"]

    assert supervisor.handle({"op": "release", "reason": "model switch"})["status"] == "cold"
    reopened = PersistentJsonlSupervisor(
        state,
        launch=lambda value: {"status": "succeeded"},
    )
    after_release = reopened.handle({
        **frame("run", task_id="task-4", attempt_id="attempt-4", lease_id="lease-4"),
        "fingerprint": "runner-2",
        "warmth_identity": "warm-2",
    })
    assert after_release["lifecycle"] == "cold"
    events = [json.loads(line)["event"] for line in state.read_text().splitlines()]
    assert events.count("runner_released") == 1


def test_cancel_is_terminal_journalled_before_callback_and_contains_launch(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    started = threading.Event()
    stop = threading.Event()
    callback_seen = []

    def launch(_frame):
        started.set()
        stop.wait(5)
        return {"status": "cancelled"}

    def cancel(_value):
        callback_seen.append(
            [json.loads(line)["event"] for line in state.read_text().splitlines()]
        )
        stop.set()

    supervisor = PersistentJsonlSupervisor(state, launch=launch, cancel=cancel)
    result = []
    worker = threading.Thread(
        target=lambda: result.append(supervisor.handle({**frame("run"), "task": {"id": "task-1"}})),
        daemon=True,
    )
    worker.start()
    assert started.wait(2)
    cancellation = supervisor.handle({**frame("cancel"), "reason": "fixture stop"})
    worker.join(2)

    assert cancellation["status"] == "cancelled"
    assert result[0]["status"] == "cancelled"
    assert callback_seen == [["started", "cancel_requested", "cancelled"]]
    events = [json.loads(line)["event"] for line in state.read_text().splitlines()]
    assert events == ["started", "cancel_requested", "cancelled", "cancellation_delivery"]
    assert supervisor.handle({**frame("cancel"), "reason": "again"})["duplicate"] is True


def test_terminal_callback_observes_journal_before_delivery(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    seen = []

    def complete(value):
        seen.append([json.loads(line)["event"] for line in state.read_text().splitlines()])
        return {"delivered": True}

    supervisor = PersistentJsonlSupervisor(state, complete=complete)
    supervisor.handle(frame("start"))
    result = supervisor.handle({**frame("complete"), "result": {"answer": 42}})

    assert result["status"] == "completed"
    assert seen == [["started", "completed"]]
    assert [json.loads(line)["event"] for line in state.read_text().splitlines()] == [
        "started",
        "completed",
        "completion_delivery",
    ]


def test_reclaim_is_durable_idempotent_and_contains_orphan(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    reclaimed = []
    first = PersistentJsonlSupervisor(
        state,
        launch=lambda _value: None,
    )
    first.handle(frame("start"))
    restarted = PersistentJsonlSupervisor(
        state,
        reclaim=lambda value: reclaimed.append(value["task_id"]),
    )

    evidence = restarted.reclaim_orphans()
    second_pass = restarted.reclaim_orphans()

    assert evidence[0]["status"] == "reclaimed"
    assert second_pass == []
    assert reclaimed == ["task-1"]
    assert restarted.status({"task_id": "task-1"})["status"] == "reclaimed"
    events = [json.loads(line)["event"] for line in state.read_text().splitlines()]
    assert events.count("reclaimed") == 1
    assert events.count("reclaim_delivery") == 1

def test_generic_host_adapter_forwards_cancel_to_runtime(tmp_path):
    runtime_cancelled = threading.Event()
    launched = threading.Event()
    calls = []

    class Runtime:
        def cancel(self, task_id):
            calls.append(task_id)
            runtime_cancelled.set()
            return {"task_id": task_id, "status": "cancelled"}

    host = GenericPackHost(pack_roots=[], client=Runtime())

    def fake_run_task(_task, **_kwargs):
        launched.set()
        runtime_cancelled.wait(2)
        return {"task_id": "task-1", "status": "cancelled", "cancelled": True}

    host.run_task = fake_run_task
    supervisor = host.persistent_supervisor(tmp_path / "supervisor.jsonl")
    run_result = []
    worker = threading.Thread(
        target=lambda: run_result.append(supervisor.handle({
            **frame("run"),
            "task": {"id": "task-1"},
        })),
        daemon=True,
    )
    worker.start()
    assert launched.wait(2)
    cancellation = supervisor.handle({**frame("cancel"), "reason": "operator stop"})
    worker.join(2)

    assert cancellation["status"] == "cancelled"
    assert run_result[0]["status"] == "cancelled"
    assert calls == ["task-1"]


def test_cancellation_preserves_compatible_warm_runner(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    started = threading.Event()
    stop = threading.Event()

    def launch(_frame):
        started.set()
        stop.wait(2)
        return {"status": "succeeded"}

    def cancel(_frame):
        stop.set()

    supervisor = PersistentJsonlSupervisor(state, launch=launch, cancel=cancel)
    result = []
    worker = threading.Thread(
        target=lambda: result.append(supervisor.handle({
            **frame("run"),
            "fingerprint": "runner-1",
            "warmth_identity": "warm-1",
        })),
        daemon=True,
    )
    worker.start()
    assert started.wait(2)
    cancellation = supervisor.handle({**frame("cancel"), "reason": "fixture stop"})
    worker.join(2)

    assert cancellation["status"] == "cancelled"
    assert result[0]["status"] == "cancelled"
    assert cancellation["reason"] == "fixture stop"

    reopened = PersistentJsonlSupervisor(state, launch=lambda _frame: {"status": "succeeded"})
    warm = reopened.handle({
        **frame("run", task_id="task-2", attempt_id="attempt-2", lease_id="lease-2"),
        "fingerprint": "runner-1",
        "warmth_identity": "warm-1",
    })
    assert warm["lifecycle"] == "warm"
    assert warm["warm_reused"] is True


def test_reclaim_fences_late_completion_and_releases_warm_runner(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    started = threading.Event()
    stop = threading.Event()

    def launch(_frame):
        started.set()
        stop.wait(2)
        return {"status": "succeeded"}

    def reclaim(_frame):
        stop.set()

    supervisor = PersistentJsonlSupervisor(state, launch=launch, reclaim=reclaim)
    result = []
    worker = threading.Thread(
        target=lambda: result.append(supervisor.handle({**frame("run"), "task": {"id": "task-1"}})),
        daemon=True,
    )
    worker.start()
    assert started.wait(2)

    evidence = supervisor.reclaim_orphans()
    worker.join(2)

    assert evidence[0]["status"] == "reclaimed"
    assert result[0]["status"] == "reclaimed"
    assert supervisor.handle({**frame("status")})["status"] == "reclaimed"
    assert [json.loads(line)["event"] for line in state.read_text().splitlines()] == [
        "started",
        "reclaimed",
        "reclaim_delivery",
        "runner_released",
    ]


def test_failure_callback_observes_durable_terminal_intent(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    seen = []

    def fail(value):
        seen.append([json.loads(line)["event"] for line in state.read_text().splitlines()])
        assert value["error"] == "fixture failure"

    supervisor = PersistentJsonlSupervisor(state, fail=fail)
    supervisor.handle(frame("start"))

    result = supervisor.handle({**frame("fail"), "error": "fixture failure"})

    assert result["status"] == "failed"
    assert seen == [["started", "terminal_failure"]]
    assert [json.loads(line)["event"] for line in state.read_text().splitlines()] == [
        "started",
        "terminal_failure",
        "failure_delivery",
    ]


def test_release_is_durable_idempotent_and_callback_sees_journal(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    seen = []
    releases = []

    def release(value):
        releases.append(value["reason"])
        seen.append([json.loads(line)["event"] for line in state.read_text().splitlines()])

    supervisor = PersistentJsonlSupervisor(state, release=release)
    supervisor.handle({**frame("run"), "fingerprint": "runner-1"})

    first = supervisor.handle({"op": "release", "reason": "fixture drain"})
    second = supervisor.handle({"op": "release", "reason": "repeat"})

    assert first["status"] == "cold"
    assert second == {"duplicate": True, "ok": True, "status": "cold"}
    assert releases == ["fixture drain"]
    assert seen == [["started", "completed", "runner_released"]]


def test_stale_failure_is_rejected_before_journal_append_and_reopen(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    supervisor = PersistentJsonlSupervisor(state)
    supervisor.handle(frame("start"))
    before = state.read_text()

    with pytest.raises(SupervisorError, match="stale lease/fence"):
        supervisor.handle(frame("fail", fence=0, error="late failure"))

    assert state.read_text() == before
    PersistentJsonlSupervisor(state)


def test_terminal_heartbeat_is_rejected_before_callback_or_journal_append(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    heartbeats = []
    supervisor = PersistentJsonlSupervisor(
        state,
        heartbeat=lambda value: heartbeats.append(value),
        cancel=lambda _value: None,
    )
    supervisor.handle(frame("start"))
    supervisor.handle(frame("cancel"))
    before = state.read_text()

    with pytest.raises(SupervisorError, match="heartbeat follows a terminal state"):
        supervisor.handle(frame("heartbeat"))

    assert heartbeats == []
    assert state.read_text() == before
    PersistentJsonlSupervisor(state)


def test_pending_cancellation_retries_after_restart(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    attempts = []

    def fail_once(_value):
        attempts.append("failed")
        raise RuntimeError("runtime unavailable")

    first = PersistentJsonlSupervisor(state, cancel=fail_once)
    first.handle(frame("start"))
    result = first.handle(frame("cancel"))
    assert result["ok"] is False
    assert result["status"] == "requires_fence"

    restarted = PersistentJsonlSupervisor(
        state,
        cancel=lambda value: attempts.append(value["attempt_id"]),
    )
    evidence = restarted.reclaim_orphans()

    assert evidence[0]["status"] == "cancelled"
    assert attempts == ["failed", "attempt-1"]
    assert "cancellation_delivery" in state.read_text()


def test_pending_release_retries_after_restart(tmp_path):
    state = tmp_path / "supervisor.jsonl"
    attempts = []

    def fail_once(_value):
        attempts.append("failed")
        raise RuntimeError("release unavailable")

    first = PersistentJsonlSupervisor(state, release=fail_once)
    first.handle({**frame("run"), "fingerprint": "runner-1"})
    result = first.handle({"op": "release", "reason": "drain"})
    assert result["ok"] is False
    assert result["status"] == "pending_release"

    restarted = PersistentJsonlSupervisor(
        state,
        release=lambda value: attempts.append(value["reason"]),
    )
    assert restarted.handle({"op": "release"})["status"] == "cold"
    assert attempts == ["failed", "drain"]
    assert "release_delivery" in state.read_text()


def test_generic_persistent_cancel_requires_containment_adapter(tmp_path):
    host = GenericPackHost(pack_roots=[], client=object())
    supervisor = host.persistent_supervisor(tmp_path / "supervisor.jsonl")
    host.run_task = lambda *_args, **_kwargs: None
    supervisor.handle({**frame("start"), "task": {"id": "task-1"}})

    result = supervisor.handle(frame("cancel"))

    assert result["ok"] is False
    assert result["status"] == "requires_fence"
    assert result["requires_fence"] is True


def test_generic_reclaim_forwards_orphan_attempt_identity(tmp_path):
    calls = []

    class Runtime:
        def cancel(self, task_id, *, attempt_id, fence, lease_id):
            calls.append((task_id, attempt_id, fence, lease_id))
            return {"status": "cancelled"}

    host = GenericPackHost(pack_roots=[], client=Runtime())
    supervisor = host.persistent_supervisor(tmp_path / "supervisor.jsonl")
    host.run_task = lambda *_args, **_kwargs: None
    supervisor.handle({**frame("start"), "task": {"id": "task-1"}})

    evidence = supervisor.reclaim_orphans()

    assert evidence[0]["status"] == "reclaimed"
    assert calls == [("task-1", "attempt-1", 1, "lease-1")]
