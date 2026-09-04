"""Supported product CLI contracts for the canonical tasks/runs API.

The retired ``runs retry-failed`` spelling and project arguments on per-id
operations are intentionally not compatibility surfaces.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import pytest

from astrid.core.cli.domain_product import run_product_family
from astrid.core.receipts.contract import CommandReceipt
from astrid.sdk.contracts import DomainResult, ErrorObject

ENVELOPE_KEYS = {"ok", "data", "error", "receipt", "idempotency_key"}


def _receipt(kind: str, key: str) -> CommandReceipt:
    return CommandReceipt(receipt_id=f"R-{kind}", command_kind=kind,
        idempotency_key=key, request_hash="hash", project_id="P-1",
        project_seq=(1, 1), event_ids=("E-1",), result={"ok": True},
        created_at="2026-01-01T00:00:00Z")


class _Tasks:
    def __init__(self, owner: "_Client") -> None:
        self.owner = owner

    def create(self, *, project_id, capability, spec, input_manifest=None, idempotency_key=None):
        self.owner.calls.append(("tasks.create", {"project_id": project_id,
            "capability": capability, "spec": spec, "input_manifest": input_manifest,
            "idempotency_key": idempotency_key}))
        key = idempotency_key or "generated-key"
        return DomainResult.success({"id": "T-1", "project_id": project_id, "status": "queued"},
            receipt=_receipt("core.task.create", key), idempotency_key=key)

    def list(self, project_id):
        self.owner.calls.append(("tasks.list", {"project_id": project_id}))
        return DomainResult.success([{"id": "T-1", "status": "queued"}])

    def show(self, task_id):
        self.owner.calls.append(("tasks.show", {"task_id": task_id}))
        return DomainResult.success({"id": task_id, "status": "queued"})

    def cancel(self, task_id, *, idempotency_key=None):
        self.owner.calls.append(("tasks.cancel", {"task_id": task_id, "idempotency_key": idempotency_key}))
        key = idempotency_key or "generated-key"
        return DomainResult.success({"id": task_id, "status": "cancelled"},
            receipt=_receipt("core.task.cancel", key), idempotency_key=key)

    def retry(self, task_id, *, idempotency_key=None):
        self.owner.calls.append(("tasks.retry", {"task_id": task_id, "idempotency_key": idempotency_key}))
        key = idempotency_key or "generated-key"
        return DomainResult.success({"id": task_id, "status": "queued"},
            receipt=_receipt("core.task.retry", key), idempotency_key=key)

    def events(self, task_id):
        self.owner.calls.append(("tasks.events", {"task_id": task_id}))
        return DomainResult.success([{"seq": 1, "kind": "core.task.created", "task_id": task_id}])


class _Runs:
    def __init__(self, owner: "_Client") -> None:
        self.owner = owner

    def list(self, project_id):
        self.owner.calls.append(("runs.list", {"project_id": project_id}))
        return DomainResult.success([{"id": "R-1", "project_id": project_id, "status": "running"}])

    def show(self, run_id):
        self.owner.calls.append(("runs.show", {"run_id": run_id}))
        return DomainResult.success({"id": run_id, "status": "failed", "progress": {"failed": 1}})

    def cancel(self, run_id, *, idempotency_key=None):
        self.owner.calls.append(("runs.cancel", {"run_id": run_id, "idempotency_key": idempotency_key}))
        key = idempotency_key or "generated-key"
        return DomainResult.success({"run_id": run_id, "status": "cancelled"},
            receipt=_receipt("run.cancel", key), idempotency_key=key)

    def retry(self, run_id, *, selected_task_ids=None, idempotency_key=None):
        self.owner.calls.append(("runs.retry", {"run_id": run_id,
            "selected_task_ids": selected_task_ids, "idempotency_key": idempotency_key}))
        key = idempotency_key or "generated-key"
        return DomainResult.success({"run_id": run_id,
            "retried_task_ids": list(selected_task_ids or ["T-2"])},
            receipt=_receipt("run.retry", key), idempotency_key=key)

    def events(self, run_id):
        self.owner.calls.append(("runs.events", {"run_id": run_id}))
        return DomainResult.success([{"seq": 1, "kind": "core.run.created", "run_id": run_id}])

    def open(self, run_id=None, *, project=None):
        self.owner.calls.append(("runs.open", {"project": project, "run_id": run_id}))
        return DomainResult.success(
            {"project_id": project or "P-current", "run_id": run_id or "R-latest", "opened": True}
        )


class _Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.tasks, self.runs = _Tasks(self), _Runs(self)


def _run(family: str, args: list[str], client: _Client | None = None) -> int:
    return run_product_family(family, args, client=client or _Client())


def _choices(parser: argparse.ArgumentParser) -> set[str]:
    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return set(action.choices)


def test_tasks_and_runs_expose_only_canonical_verbs() -> None:
    from astrid.core.cli.domain_tasks import COMMANDS as TASK_COMMANDS, build_parser as task_parser
    from astrid.core.cli.domain_runs import COMMANDS as RUN_COMMANDS, build_parser as run_parser
    assert tuple(c.name for c in TASK_COMMANDS) == ("create", "list", "show", "cancel", "retry", "events", "follow")
    assert _choices(task_parser(_Client())) == {"create", "list", "show", "cancel", "retry", "events", "follow"}
    assert tuple(c.name for c in RUN_COMMANDS) == ("list", "show", "cancel", "retry", "events", "open")
    assert _choices(run_parser(_Client())) == {"list", "show", "cancel", "retry", "events", "open"}


def test_runs_open_defaults_to_latest_in_current_project(capsys) -> None:
    client = _Client()

    assert _run("runs", ["open", "--json"], client) == 0

    assert client.calls == [("runs.open", {"project": None, "run_id": None})]
    assert json.loads(capsys.readouterr().out)["data"]["run_id"] == "R-latest"


def test_runs_open_accepts_exact_run_and_project_override(capsys) -> None:
    client = _Client()

    assert _run("runs", ["open", "R-23", "--project", "demo", "--json"], client) == 0

    assert client.calls == [("runs.open", {"project": "demo", "run_id": "R-23"})]
    assert json.loads(capsys.readouterr().out)["data"]["run_id"] == "R-23"


@pytest.mark.parametrize("family,verb,identifier,call", [
    ("tasks", "show", "T-1", "tasks.show"), ("tasks", "events", "T-1", "tasks.events"),
    ("runs", "show", "R-1", "runs.show"), ("runs", "events", "R-1", "runs.events"),
])
def test_per_id_reads_use_generated_client_shape(family, verb, identifier, call, capsys) -> None:
    client = _Client()
    assert _run(family, [verb, "--project", "P-1", identifier, "--json"], client) == 0
    key = "task_id" if family == "tasks" else "run_id"
    assert client.calls == [(call, {key: identifier})]
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_mutations_forward_only_canonical_arguments(capsys) -> None:
    client = _Client()
    assert _run("tasks", ["cancel", "--project", "P-1", "T-1", "--idempotency-key", "k", "--json"], client) == 0
    assert client.calls[-1] == ("tasks.cancel", {"task_id": "T-1", "idempotency_key": "k"})
    assert _run("runs", ["retry", "--project", "P-1", "R-1", "--task", "T-2", "--json"], client) == 0
    assert client.calls[-1] == ("runs.retry", {"run_id": "R-1", "selected_task_ids": ["T-2"], "idempotency_key": None})
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["receipt"]["command_kind"] == "run.retry"


def test_tasks_create_forwards_generated_contract(capsys) -> None:
    client = _Client()
    assert _run("tasks", ["create", "--project", "P-1", "--capability", "cap.a",
        "--spec", '{"x": 1}', "--input-manifest", '[{"media_id":"M-1"}]', "--json"], client) == 0
    assert client.calls == [("tasks.create", {"project_id": "P-1", "capability": "cap.a",
        "spec": {"x": 1}, "input_manifest": [{"media_id": "M-1"}], "idempotency_key": None})]
    envelope = json.loads(capsys.readouterr().out)
    assert set(envelope) == ENVELOPE_KEYS and envelope["receipt"] is not None
    assert envelope["data"]["handoff"]["follow"] == (
        "python3 -m astrid tasks follow T-1 --project P-1"
    )


def test_tasks_follow_prints_only_durable_changes_and_exits_on_success(capsys) -> None:
    client = _Client()
    snapshots = [
        {"task_id": "T-1", "run_id": "R-1", "state": "queued", "version": 1,
         "created_at": "2026-09-04T10:00:00Z", "updated_at": "2026-09-04T10:00:00Z"},
        {"task_id": "T-1", "run_id": "R-1", "state": "queued", "version": 1,
         "created_at": "2026-09-04T10:00:00Z", "updated_at": "2026-09-04T10:00:00Z"},
        {"task_id": "T-1", "run_id": "R-1", "state": "running", "version": 2,
         "attempt_id": "A-1", "created_at": "2026-09-04T10:00:00Z",
         "updated_at": "2026-09-04T10:00:01Z"},
        {"task_id": "T-1", "run_id": "R-1", "state": "succeeded", "version": 2,
         "attempt_id": "A-1", "created_at": "2026-09-04T10:00:00Z",
         "updated_at": "2026-09-04T10:00:02Z", "result": {"outputs": []}},
    ]

    def show(task_id):
        client.calls.append(("tasks.show", {"task_id": task_id}))
        return DomainResult.success(snapshots.pop(0))

    client.tasks.show = show
    assert _run(
        "tasks",
        ["follow", "T-1", "--project", "P-1", "--poll-seconds", "0.001"],
        client,
    ) == 0

    output = capsys.readouterr().out
    assert output.count("phase=queued") == 1
    assert output.count("phase=running") == 1
    assert output.count("phase=succeeded") == 1
    assert "heartbeat=" in output
    assert "attempt=A-1" in output
    assert "waiting=awaiting_execution" in output


def test_tasks_follow_json_is_one_envelope_with_observation_history(capsys) -> None:
    client = _Client()
    snapshots = [
        {"task_id": "T-1", "run_id": "R-1", "state": "queued", "version": 1,
         "waiting_reason": "waiting_for_gpu", "updated_at": "2026-09-04T10:00:00Z"},
        {"task_id": "T-1", "run_id": "R-1", "state": "succeeded", "version": 2,
         "attempt_id": "A-2", "updated_at": "2026-09-04T10:00:01Z",
         "result": {"outputs": [{"url": "https://example.test/render.mp4"}]}},
    ]
    client.tasks.show = lambda _task_id: DomainResult.success(snapshots.pop(0))

    assert _run(
        "tasks",
        ["follow", "T-1", "--project", "P-1", "--poll-seconds", "0.001", "--json"],
        client,
    ) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert len(captured.out.splitlines()) == 1
    envelope = json.loads(captured.out)
    assert set(envelope) == ENVELOPE_KEYS
    assert envelope["data"]["state"] == "succeeded"
    assert [row["state"] for row in envelope["data"]["observations"]] == [
        "queued", "succeeded"
    ]
    assert envelope["data"]["observations"][0]["waiting_reason"] == "waiting_for_gpu"
    assert envelope["data"]["outputs"][0]["location"] == "https://example.test/render.mp4"
    assert envelope["data"]["handoff"]["open"] == (
        "python3 -m astrid runs open R-1 --project P-1"
    )


def test_tasks_follow_reports_defensible_progress_speed_and_eta(capsys) -> None:
    client = _Client()
    client.tasks.show = lambda _task_id: DomainResult.success({
        "task_id": "T-1", "run_id": "R-1", "state": "succeeded", "version": 2,
        "attempt_id": "A-1", "progress": {
            "phase": "encoding", "completed_units": 75, "total_units": 100,
            "current_speed": 5, "speed_unit": "units/s",
        },
    })

    assert _run("tasks", ["follow", "T-1", "--project", "P-1", "--json"], client) == 0
    observation = json.loads(capsys.readouterr().out)["data"]["observations"][0]
    assert observation["phase"] == "encoding"
    assert observation["progress_percent"] == 75.0
    assert observation["current_speed"] == 5.0
    assert observation["eta_seconds"] == 5
    assert observation["eta_source"] == "remaining/current_speed"


def test_tasks_follow_does_not_invent_queue_progress_or_eta(capsys) -> None:
    client = _Client()
    client.tasks.show = lambda _task_id: DomainResult.success(
        {"task_id": "T-1", "state": "succeeded", "version": 2}
    )

    assert _run("tasks", ["follow", "T-1", "--project", "P-1"], client) == 0
    output = capsys.readouterr().out
    assert "queue=unavailable" in output
    assert "progress=unavailable" in output
    assert "speed=unavailable" in output
    assert "eta=unavailable" in output
    assert "runtime did not report queue position" in output


def test_tasks_follow_terminal_failure_is_exit_one(capsys) -> None:
    client = _Client()
    client.tasks.show = lambda _task_id: DomainResult.success(
        {"task_id": "T-1", "state": "failed", "version": 3, "attempt_id": "A-2"}
    )

    assert _run("tasks", ["follow", "T-1", "--project", "P-1", "--json"], client) == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["error"]["code"] == "task_failed"


@pytest.mark.parametrize("flag,value", [("--poll-seconds", "0"), ("--timeout-seconds", "nan")])
def test_tasks_follow_rejects_non_positive_or_non_finite_intervals(flag, value) -> None:
    client = _Client()
    with pytest.raises(SystemExit) as exc:
        _run("tasks", ["follow", "T-1", "--project", "P-1", flag, value], client)
    assert exc.value.code == 2
    assert client.calls == []


def test_tasks_create_does_not_advertise_unsupported_runtime_admission_fields() -> None:
    from astrid.core.cli.domain_tasks import build_parser

    parser = build_parser(_Client())
    help_text = parser.format_help()
    assert all(flag not in help_text for flag in ("--priority", "--available-at", "--max-attempts", "--dependencies"))
    for flag in ("--priority", "--available-at", "--max-attempts", "--dependencies"):
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["create", "--project", "P-1", "--capability", "cap.a", "--spec", "{}", flag, "1"])
        assert exc.value.code == 2


def test_runs_show_preserves_runtime_progress_and_optional_evidence(capsys) -> None:
    client = _Client()
    client.runs.show = lambda run_id: DomainResult.success({
        "run_id": run_id,
        "status": "failed",
        "progress": {"total_children": 3, "succeeded": 1, "failed": 2, "cancelled": 0},
        "evidence": [{"evidence_id": "EV-1", "kind": "preview"}],
    })
    assert _run("runs", ["show", "--project", "P-1", "R-1", "--evidence", "--json"], client) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert set(envelope) == ENVELOPE_KEYS
    assert envelope["data"]["progress"]["failed"] == 2
    assert envelope["data"]["evidence"][0]["evidence_id"] == "EV-1"


def test_tasks_and_runs_help_explain_supported_envelope_and_event_scope(capsys) -> None:
    client = _Client()
    with pytest.raises(SystemExit) as tasks_help:
        _run("tasks", ["create", "--help"], client)
    assert tasks_help.value.code == 0
    assert "ok/data/error/receipt/idempotency_key" in capsys.readouterr().out
    with pytest.raises(SystemExit) as runs_help:
        _run("runs", ["events", "--help"], client)
    assert runs_help.value.code == 0
    assert "Child task transitions" in capsys.readouterr().out


def test_project_list_is_one_sdk_call(capsys) -> None:
    client = _Client()
    assert _run("tasks", ["list", "--project", "slug", "--json"], client) == 0
    assert _run("runs", ["list", "--project", "slug", "--json"], client) == 0
    assert client.calls == [("tasks.list", {"project_id": "slug"}), ("runs.list", {"project_id": "slug"})]
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["ok"] is True


def test_typed_failure_renders_json_and_exit_one(capsys) -> None:
    class FailingTasks(_Tasks):
        def retry(self, task_id, *, idempotency_key=None):
            return DomainResult.failure(ErrorObject(code="stale_version", message="m", details={}),
                idempotency_key=idempotency_key or "generated-key")
    client = _Client(); client.tasks = FailingTasks(client)
    assert _run("tasks", ["retry", "--project", "P-1", "T-1", "--json"], client) == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is False and envelope["error"]["code"] == "stale_version"


def test_missing_project_is_usage_error_without_sdk_call() -> None:
    client = _Client()
    with pytest.raises(SystemExit) as exc:
        _run("runs", ["show", "R-1"], client)
    assert exc.value.code == 2 and client.calls == []


def test_retired_retry_failed_spelling_is_rejected() -> None:
    with pytest.raises(SystemExit) as exc:
        _run("runs", ["retry-failed", "--project", "P-1", "R-1"], _Client())
    assert exc.value.code == 2


def test_gateway_registers_plural_families() -> None:
    from astrid.core.gateway import dispatch
    assert {"tasks", "runs"} <= dispatch._top_level_commands()
