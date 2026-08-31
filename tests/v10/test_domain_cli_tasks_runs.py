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
    assert tuple(c.name for c in TASK_COMMANDS) == ("create", "list", "show", "cancel", "retry", "events")
    assert _choices(task_parser(_Client())) == {"create", "list", "show", "cancel", "retry", "events"}
    assert tuple(c.name for c in RUN_COMMANDS) == ("list", "show", "cancel", "retry", "events")
    assert _choices(run_parser(_Client())) == {"list", "show", "cancel", "retry", "events"}


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
