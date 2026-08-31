"""Product CLI family tests: tasks and runs (m4 plan steps 28-29).

Task T31 (plan step 28) proves the ``tasks`` product family
(``astrid/core/cli/domain_tasks.py``): exactly the six product verbs
``create/list/show/cancel/retry/events`` are one-call SDK adapters,
executor lifecycle verbs (``claim``/``start``/``heartbeat``) and
plan/step semantics (``plan``/``step``/``next``/``ack``/``skip``/``hook``)
are absent from product parsing, and typed terminal/stale/not-found
envelopes, keys, receipts, and executable help are covered.

Task T32 (plan step 29) proves the ``runs`` product family
(``astrid/core/cli/domain_runs.py``): exactly the five plural verbs
``list/show/cancel/retry-failed/events`` are one-call SDK adapters over
the grouped run service, with derived grouped progress, optional evidence,
partial failure, cancellation, retry selection, typed terminal/stale
errors, keys, receipts, and executable help; the singular ``run`` alias is
not a product family and never registers here.
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


def _receipt(command_kind: str, key: str) -> CommandReceipt:
    return CommandReceipt(
        receipt_id=f"R-{command_kind}",
        command_kind=command_kind,
        idempotency_key=key,
        request_hash="hash",
        project_id="P-1",
        project_seq=(1, 1),
        event_ids=("E-1",),
        result={"ok": True},
        created_at="2026-01-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Recording fake client (one call per service method, canned envelopes)
# ---------------------------------------------------------------------------


class _RecordingTasks:
    def __init__(self, owner: "_FakeClient") -> None:
        self._owner = owner

    def create(
        self,
        *,
        project_id,
        capability,
        spec,
        input_manifest=None,
        priority=0,
        available_at=None,
        max_attempts=1,
        dependencies=None,
        idempotency_key=None,
    ):
        self._owner.calls.append(
            (
                "tasks.create",
                {
                    "project_id": project_id,
                    "capability": capability,
                    "spec": spec,
                    "input_manifest": input_manifest,
                    "priority": priority,
                    "available_at": available_at,
                    "max_attempts": max_attempts,
                    "dependencies": dependencies,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {"id": "T-1", "project_id": project_id, "status": "queued"},
            receipt=_receipt("core.task.create", key),
            idempotency_key=key,
        )

    def list(self, project_id):
        self._owner.calls.append(("tasks.list", {"project_id": project_id}))
        return DomainResult.success(
            [{"id": "T-1", "status": "queued"}, {"id": "T-2", "status": "succeeded"}]
        )

    def show(self, task_id):
        self._owner.calls.append(("tasks.show", {"task_id": task_id}))
        return DomainResult.success(
            {"id": task_id, "project_id": "P-1", "status": "queued"}
        )

    def cancel(self, project_id, task_id, *, idempotency_key=None):
        self._owner.calls.append(
            (
                "tasks.cancel",
                {"project_id": project_id, "task_id": task_id, "idempotency_key": idempotency_key},
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {"id": task_id, "project_id": project_id, "status": "cancelled"},
            receipt=_receipt("core.task.cancel", key),
            idempotency_key=key,
        )

    def retry(self, project_id, task_id, *, idempotency_key=None):
        self._owner.calls.append(
            (
                "tasks.retry",
                {"project_id": project_id, "task_id": task_id, "idempotency_key": idempotency_key},
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {"id": task_id, "project_id": project_id, "status": "queued"},
            receipt=_receipt("core.task.retry", key),
            idempotency_key=key,
        )

    def events(self, task_id):
        self._owner.calls.append(("tasks.events", {"task_id": task_id}))
        return DomainResult.success(
            [
                {"seq": 1, "kind": "core.task.created", "task_id": task_id},
                {"seq": 2, "kind": "core.task.cancelled", "task_id": task_id},
            ]
        )


class _RecordingRuns:
    def __init__(self, owner: "_FakeClient") -> None:
        self._owner = owner

    def list(self, project_id):
        self._owner.calls.append(("runs.list", {"project_id": project_id}))
        return DomainResult.success(
            [
                {"id": "R-1", "project_id": project_id, "kind": "render", "status": "running"},
                {"id": "R-2", "project_id": project_id, "kind": "render", "status": "succeeded"},
            ]
        )

    def show(self, project_id, run_id, *, include_evidence=False):
        self._owner.calls.append(
            (
                "runs.show",
                {"project_id": project_id, "run_id": run_id, "include_evidence": include_evidence},
            )
        )
        data = {
            "id": run_id,
            "project_id": project_id,
            "kind": "render",
            "status": "failed",
            "title": "Render main",
            "input": {},
            "result": {},
            "started_at": "2026-08-18T00:00:00+00:00",
            "finished_at": "2026-08-18T00:01:00+00:00",
            "progress": {
                "run_id": run_id,
                "project_id": project_id,
                "status": "failed",
                "total_children": 3,
                "succeeded": 1,
                "failed": 2,
                "cancelled": 0,
                "ordered": [
                    {"ordinal": 0, "task_id": "T-1", "status": "succeeded"},
                    {"ordinal": 1, "task_id": "T-2", "status": "failed"},
                    {"ordinal": 2, "task_id": "T-3", "status": "failed"},
                ],
            },
        }
        if include_evidence:
            data["evidence"] = [
                {"evidence_id": "EV-1", "run_id": run_id, "kind": "png", "path": "out/1.png"},
                {"evidence_id": "EV-2", "run_id": run_id, "kind": "png", "path": "out/2.png"},
            ]
        return DomainResult.success(data)

    def cancel(self, project_id, run_id, *, idempotency_key=None):
        self._owner.calls.append(
            (
                "runs.cancel",
                {"project_id": project_id, "run_id": run_id, "idempotency_key": idempotency_key},
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {
                "run_id": run_id,
                "project_id": project_id,
                "cancelled_task_ids": ["T-2", "T-3"],
                "status": "cancelled",
            },
            receipt=_receipt("run.cancel", key),
            idempotency_key=key,
        )

    def retry_failed(self, project_id, run_id, *, selected_task_ids=None, idempotency_key=None):
        self._owner.calls.append(
            (
                "runs.retry_failed",
                {
                    "project_id": project_id,
                    "run_id": run_id,
                    "selected_task_ids": selected_task_ids,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {
                "run_id": run_id,
                "project_id": project_id,
                "retried_task_ids": list(selected_task_ids or ["T-2", "T-3"]),
                "status": "running",
            },
            receipt=_receipt("run.retry_failed", key),
            idempotency_key=key,
        )

    def events(self, project_id, run_id):
        self._owner.calls.append(
            ("runs.events", {"project_id": project_id, "run_id": run_id})
        )
        return DomainResult.success(
            [
                {"seq": 1, "kind": "core.run.created", "run_id": run_id},
                {"seq": 2, "kind": "core.run.finished", "run_id": run_id},
            ]
        )


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.tasks = _RecordingTasks(self)
        self.runs = _RecordingRuns(self)


def _run(family: str, args: list[str], client: _FakeClient | None = None) -> int:
    return run_product_family(family, args, client=client or _FakeClient())


def _subparser_choices(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("parser has no subparsers")


# ---------------------------------------------------------------------------
# T31 — tasks family
# ---------------------------------------------------------------------------


def test_tasks_parser_has_exactly_six_verbs() -> None:
    from astrid.core.cli.domain_tasks import COMMANDS, build_parser

    assert tuple(spec.name for spec in COMMANDS) == (
        "create",
        "list",
        "show",
        "cancel",
        "retry",
        "events",
    )
    assert _subparser_choices(build_parser(_FakeClient())) == {
        "create",
        "list",
        "show",
        "cancel",
        "retry",
        "events",
    }


def test_tasks_parser_excludes_executor_and_plan_verbs() -> None:
    """Claim/start/heartbeat and plan/step semantics never reach parsing."""
    from astrid.core.cli.domain_tasks import build_parser

    choices = _subparser_choices(build_parser(_FakeClient()))
    for forbidden in (
        "claim",
        "start",
        "heartbeat",
        "plan",
        "step",
        "next",
        "ack",
        "skip",
        "hook",
    ):
        assert forbidden not in choices


def test_tasks_create_is_one_sdk_call_with_exact_envelope(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "tasks",
        ["create", "--project", "P-1", "--capability", "cap.a", "--spec", '{"x": 1}', "--json"],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        (
            "tasks.create",
            {
                "project_id": "P-1",
                "capability": "cap.a",
                "spec": {"x": 1},
                "input_manifest": None,
                "priority": 0,
                "available_at": None,
                "max_attempts": 1,
                "dependencies": None,
                "idempotency_key": None,
            },
        )
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert set(envelope) == ENVELOPE_KEYS
    assert envelope["ok"] is True
    assert envelope["data"]["id"] == "T-1"
    assert envelope["receipt"]["command_kind"] == "core.task.create"
    assert envelope["idempotency_key"] == "generated-key"


def test_tasks_create_forwards_caller_key_and_admission_options(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "tasks",
        [
            "create",
            "--project",
            "P-1",
            "--capability",
            "cap.a",
            "--spec",
            '{"x": 1}',
            "--input-manifest",
            '[{"media_id": "M-1"}]',
            "--priority",
            "5",
            "--available-at",
            "2026-08-18T12:00:00+00:00",
            "--max-attempts",
            "3",
            "--dependencies",
            '[{"task_id": "T-0"}]',
            "--idempotency-key",
            "caller-key",
            "--json",
        ],
        client=client,
    )
    assert rc == 0
    (verb, kwargs) = client.calls[0]
    assert verb == "tasks.create"
    assert kwargs == {
        "project_id": "P-1",
        "capability": "cap.a",
        "spec": {"x": 1},
        "input_manifest": [{"media_id": "M-1"}],
        "priority": 5,
        "available_at": "2026-08-18T12:00:00+00:00",
        "max_attempts": 3,
        "dependencies": [{"task_id": "T-0"}],
        "idempotency_key": "caller-key",
    }
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["idempotency_key"] == "caller-key"
    assert envelope["receipt"]["command_kind"] == "core.task.create"


def test_tasks_list_is_one_sdk_call(capsys) -> None:
    client = _FakeClient()
    rc = _run("tasks", ["list", "--project", "P-1", "--json"], client=client)
    assert rc == 0
    assert client.calls == [("tasks.list", {"project_id": "P-1"})]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert len(envelope["data"]) == 2
    assert envelope["receipt"] is None
    assert envelope["idempotency_key"] == ""


def test_tasks_show_is_one_sdk_call(capsys) -> None:
    client = _FakeClient()
    rc = _run("tasks", ["show", "T-1"], client=client)
    assert rc == 0
    assert client.calls == [("tasks.show", {"task_id": "T-1"})]
    assert capsys.readouterr().out == "id: T-1\n"


def test_tasks_cancel_is_one_sdk_call_with_receipt_and_key(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "tasks",
        ["cancel", "--project", "P-1", "T-1", "--idempotency-key", "cancel-key", "--json"],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        ("tasks.cancel", {"project_id": "P-1", "task_id": "T-1", "idempotency_key": "cancel-key"})
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["data"]["status"] == "cancelled"
    assert envelope["receipt"]["command_kind"] == "core.task.cancel"
    assert envelope["idempotency_key"] == "cancel-key"


def test_tasks_retry_is_one_sdk_call_with_generated_key(capsys) -> None:
    client = _FakeClient()
    rc = _run("tasks", ["retry", "--project", "P-1", "T-2", "--json"], client=client)
    assert rc == 0
    assert client.calls == [
        ("tasks.retry", {"project_id": "P-1", "task_id": "T-2", "idempotency_key": None})
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["data"]["status"] == "queued"
    assert envelope["receipt"]["command_kind"] == "core.task.retry"
    assert envelope["idempotency_key"] == "generated-key"


def test_tasks_events_is_one_sdk_call_with_ordered_stream(capsys) -> None:
    client = _FakeClient()
    rc = _run("tasks", ["events", "T-1", "--json"], client=client)
    assert rc == 0
    assert client.calls == [("tasks.events", {"task_id": "T-1"})]
    envelope = json.loads(capsys.readouterr().out)
    assert [event["kind"] for event in envelope["data"]] == [
        "core.task.created",
        "core.task.cancelled",
    ]
    assert envelope["receipt"] is None


def test_tasks_cancel_terminal_state_failure_exits_one(capsys) -> None:
    class _TerminalTasks(_RecordingTasks):
        def cancel(self, project_id, task_id, *, idempotency_key=None):
            self._owner.calls.append(
                ("tasks.cancel", {"project_id": project_id, "task_id": task_id})
            )
            return DomainResult.failure(
                ErrorObject(
                    code="terminal_state",
                    message="task is already terminal",
                    details={"task_id": task_id, "status": "succeeded"},
                ),
                idempotency_key=idempotency_key or "generated-key",
            )

    class _TerminalClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.tasks = _TerminalTasks(self)

    client = _TerminalClient()
    rc = _run(
        "tasks",
        ["cancel", "--project", "P-1", "T-1", "--json"],
        client=client,
    )
    assert rc == 1
    assert len(client.calls) == 1
    captured = capsys.readouterr()
    envelope = json.loads(captured.out)
    assert envelope["ok"] is False
    assert envelope["data"] is None
    assert envelope["error"]["code"] == "terminal_state"
    assert envelope["receipt"] is None
    assert envelope["idempotency_key"] == "generated-key"
    assert captured.err == ""


def test_tasks_retry_stale_version_failure_exits_one(capsys) -> None:
    class _StaleTasks(_RecordingTasks):
        def retry(self, project_id, task_id, *, idempotency_key=None):
            self._owner.calls.append(("tasks.retry", {"task_id": task_id}))
            return DomainResult.failure(
                ErrorObject(
                    code="stale_version",
                    message="task moved while retrying",
                    details={"task_id": task_id},
                ),
                idempotency_key=idempotency_key or "generated-key",
            )

    class _StaleClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.tasks = _StaleTasks(self)

    client = _StaleClient()
    rc = _run(
        "tasks",
        ["retry", "--project", "P-1", "T-2", "--idempotency-key", "retry-key", "--json"],
        client=client,
    )
    assert rc == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "stale_version"
    assert envelope["idempotency_key"] == "retry-key"


def test_tasks_create_idempotency_mismatch_failure_exits_one(capsys) -> None:
    class _MismatchTasks(_RecordingTasks):
        def create(self, *, project_id, capability, spec, **kwargs):
            self._owner.calls.append(("tasks.create", {"spec": spec}))
            return DomainResult.failure(
                ErrorObject(
                    code="idempotency_mismatch",
                    message="same key with a changed request",
                    details={"project_id": project_id},
                ),
                idempotency_key=kwargs.get("idempotency_key") or "generated-key",
            )

    class _MismatchClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.tasks = _MismatchTasks(self)

    client = _MismatchClient()
    rc = _run(
        "tasks",
        [
            "create",
            "--project",
            "P-1",
            "--capability",
            "cap.a",
            "--spec",
            '{"x": 2}',
            "--idempotency-key",
            "same-key",
            "--json",
        ],
        client=client,
    )
    assert rc == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "idempotency_mismatch"
    assert envelope["idempotency_key"] == "same-key"


def test_tasks_show_not_found_human_mode_prints_error_to_stderr(capsys) -> None:
    class _NotFoundTasks(_RecordingTasks):
        def show(self, task_id):
            self._owner.calls.append(("tasks.show", {"task_id": task_id}))
            return DomainResult.failure(
                ErrorObject(
                    code="not_found",
                    message="no such task",
                    details={"task_id": task_id},
                )
            )

    class _NotFoundClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.tasks = _NotFoundTasks(self)

    client = _NotFoundClient()
    rc = _run("tasks", ["show", "T-999"], client=client)
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error not_found: no such task\n"


def test_tasks_create_missing_required_args_is_a_usage_error() -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run("tasks", ["create", "--project", "P-1"], client=client)
    assert excinfo.value.code == 2
    assert client.calls == []


def test_tasks_help_is_executable_and_names_exactly_the_six_verbs(capsys) -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run("tasks", ["--help"], client=client)
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    for verb in ("create", "list", "show", "cancel", "retry", "events"):
        assert verb in out
    for forbidden in ("claim", "start", "heartbeat", "plan", "step", "hook"):
        assert forbidden not in out
    assert client.calls == []


def test_tasks_verb_help_is_executable(capsys) -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run("tasks", ["create", "--help"], client=client)
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "--capability" in out
    assert "--spec" in out
    assert "--idempotency-key" in out


# ---------------------------------------------------------------------------
# T32 — runs family
# ---------------------------------------------------------------------------


def test_runs_parser_has_exactly_five_verbs_and_no_singular_alias() -> None:
    from astrid.core.cli.domain_runs import COMMANDS, build_parser

    assert tuple(spec.name for spec in COMMANDS) == (
        "list",
        "show",
        "cancel",
        "retry-failed",
        "events",
    )
    choices = _subparser_choices(build_parser(_FakeClient()))
    assert choices == {
        "list",
        "show",
        "cancel",
        "retry-failed",
        "events",
    }
    assert "run" not in choices


def test_runs_list_is_one_sdk_call(capsys) -> None:
    client = _FakeClient()
    rc = _run("runs", ["list", "--project", "P-1", "--json"], client=client)
    assert rc == 0
    assert client.calls == [("runs.list", {"project_id": "P-1"})]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert [run["id"] for run in envelope["data"]] == ["R-1", "R-2"]
    assert envelope["receipt"] is None
    assert envelope["idempotency_key"] == ""


def test_runs_show_derives_grouped_progress_with_partial_failure(capsys) -> None:
    client = _FakeClient()
    rc = _run("runs", ["show", "--project", "P-1", "R-1", "--json"], client=client)
    assert rc == 0
    assert client.calls == [
        ("runs.show", {"project_id": "P-1", "run_id": "R-1", "include_evidence": False})
    ]
    envelope = json.loads(capsys.readouterr().out)
    data = envelope["data"]
    assert data["status"] == "failed"
    progress = data["progress"]
    assert progress["status"] == "failed"
    assert progress["total_children"] == 3
    assert progress["succeeded"] == 1
    assert progress["failed"] == 2
    assert progress["cancelled"] == 0
    assert progress["ordered"] == [
        {"ordinal": 0, "task_id": "T-1", "status": "succeeded"},
        {"ordinal": 1, "task_id": "T-2", "status": "failed"},
        {"ordinal": 2, "task_id": "T-3", "status": "failed"},
    ]
    assert "evidence" not in data


def test_runs_show_evidence_flag_appends_ordered_evidence(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "runs",
        ["show", "--project", "P-1", "R-1", "--evidence", "--json"],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        ("runs.show", {"project_id": "P-1", "run_id": "R-1", "include_evidence": True})
    ]
    envelope = json.loads(capsys.readouterr().out)
    evidence = envelope["data"]["evidence"]
    assert [item["evidence_id"] for item in evidence] == ["EV-1", "EV-2"]


def test_runs_cancel_is_one_sdk_call_with_receipt_and_key(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "runs",
        ["cancel", "--project", "P-1", "R-1", "--idempotency-key", "cancel-key", "--json"],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        ("runs.cancel", {"project_id": "P-1", "run_id": "R-1", "idempotency_key": "cancel-key"})
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["data"]["cancelled_task_ids"] == ["T-2", "T-3"]
    assert envelope["receipt"]["command_kind"] == "run.cancel"
    assert envelope["idempotency_key"] == "cancel-key"


def test_runs_retry_failed_is_one_sdk_call_with_selected_tasks(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "runs",
        [
            "retry-failed",
            "--project",
            "P-1",
            "R-1",
            "--task",
            "T-2",
            "--task",
            "T-3",
            "--json",
        ],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        (
            "runs.retry_failed",
            {
                "project_id": "P-1",
                "run_id": "R-1",
                "selected_task_ids": ["T-2", "T-3"],
                "idempotency_key": None,
            },
        )
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["data"]["retried_task_ids"] == ["T-2", "T-3"]
    assert envelope["receipt"]["command_kind"] == "run.retry_failed"
    assert envelope["idempotency_key"] == "generated-key"


def test_runs_retry_failed_without_selection_retries_all(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "runs",
        ["retry-failed", "--project", "P-1", "R-1", "--idempotency-key", "all-key", "--json"],
        client=client,
    )
    assert rc == 0
    (verb, kwargs) = client.calls[0]
    assert verb == "runs.retry_failed"
    assert kwargs["selected_task_ids"] is None
    assert kwargs["idempotency_key"] == "all-key"
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["data"]["retried_task_ids"] == ["T-2", "T-3"]


def test_runs_retry_failed_all_mode_is_one_sdk_call(capsys) -> None:
    """Frozen batch-retry decision: with no ``--task`` the retry targets every
    eligible failed/expired child, so ``retry-failed <run_id>`` makes exactly
    one ``client.runs.retry_failed`` call with ``selected_task_ids=None``.
    An explicit subset requires repeatable ``--task``; no ``--run`` flag is
    added to ``tasks retry``."""
    client = _FakeClient()
    rc = _run(
        "runs",
        ["retry-failed", "--project", "P-1", "R-1", "--json"],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        (
            "runs.retry_failed",
            {
                "project_id": "P-1",
                "run_id": "R-1",
                "selected_task_ids": None,
                "idempotency_key": None,
            },
        )
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["data"]["retried_task_ids"] == ["T-2", "T-3"]
    assert envelope["receipt"]["command_kind"] == "run.retry_failed"
    assert envelope["idempotency_key"] == "generated-key"


def test_runs_retry_failed_subset_mode_is_one_sdk_call(capsys) -> None:
    """An explicit ``--task T1 --task T2`` subset retries only those children:
    exactly one ``client.runs.retry_failed`` call with
    ``selected_task_ids=["T1", "T2"]``."""
    client = _FakeClient()
    rc = _run(
        "runs",
        [
            "retry-failed",
            "--project",
            "P-1",
            "R-1",
            "--task",
            "T1",
            "--task",
            "T2",
            "--json",
        ],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        (
            "runs.retry_failed",
            {
                "project_id": "P-1",
                "run_id": "R-1",
                "selected_task_ids": ["T1", "T2"],
                "idempotency_key": None,
            },
        )
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["data"]["retried_task_ids"] == ["T1", "T2"]
    assert envelope["receipt"]["command_kind"] == "run.retry_failed"
    assert envelope["idempotency_key"] == "generated-key"


def test_runs_retry_failed_rejects_terminal_run(capsys) -> None:
    """A terminal run cannot be retried: the SDK's typed ``terminal_state``
    error surfaces as a failing envelope (exit 1, null data/receipt)."""
    class _TerminalRuns(_RecordingRuns):
        def retry_failed(
            self, project_id, run_id, *, selected_task_ids=None, idempotency_key=None
        ):
            self._owner.calls.append(
                (
                    "runs.retry_failed",
                    {
                        "project_id": project_id,
                        "run_id": run_id,
                        "selected_task_ids": selected_task_ids,
                        "idempotency_key": idempotency_key,
                    },
                )
            )
            return DomainResult.failure(
                ErrorObject(
                    code="terminal_state",
                    message="run is already terminal",
                    details={"run_id": run_id, "status": "succeeded"},
                ),
                idempotency_key=idempotency_key or "generated-key",
            )

    class _TerminalClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.runs = _TerminalRuns(self)

    client = _TerminalClient()
    rc = _run(
        "runs",
        ["retry-failed", "--project", "P-1", "R-1", "--json"],
        client=client,
    )
    assert rc == 1
    assert len(client.calls) == 1
    captured = capsys.readouterr()
    envelope = json.loads(captured.out)
    assert envelope["ok"] is False
    assert envelope["data"] is None
    assert envelope["error"]["code"] == "terminal_state"
    assert envelope["receipt"] is None
    assert envelope["idempotency_key"] == "generated-key"
    assert captured.err == ""


def test_runs_events_is_one_sdk_call(capsys) -> None:
    client = _FakeClient()
    rc = _run("runs", ["events", "--project", "P-1", "R-1", "--json"], client=client)
    assert rc == 0
    assert client.calls == [("runs.events", {"project_id": "P-1", "run_id": "R-1"})]
    envelope = json.loads(capsys.readouterr().out)
    assert [event["kind"] for event in envelope["data"]] == [
        "core.run.created",
        "core.run.finished",
    ]
    assert envelope["receipt"] is None


def test_runs_cancel_terminal_state_failure_exits_one(capsys) -> None:
    class _TerminalRuns(_RecordingRuns):
        def cancel(self, project_id, run_id, *, idempotency_key=None):
            self._owner.calls.append(("runs.cancel", {"run_id": run_id}))
            return DomainResult.failure(
                ErrorObject(
                    code="terminal_state",
                    message="run is already terminal",
                    details={"run_id": run_id, "status": "succeeded"},
                ),
                idempotency_key=idempotency_key or "generated-key",
            )

    class _TerminalClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.runs = _TerminalRuns(self)

    client = _TerminalClient()
    rc = _run("runs", ["cancel", "--project", "P-1", "R-1", "--json"], client=client)
    assert rc == 1
    assert len(client.calls) == 1
    captured = capsys.readouterr()
    envelope = json.loads(captured.out)
    assert envelope["ok"] is False
    assert envelope["data"] is None
    assert envelope["error"]["code"] == "terminal_state"
    assert envelope["receipt"] is None
    assert envelope["idempotency_key"] == "generated-key"
    assert captured.err == ""


def test_runs_retry_failed_stale_version_failure_exits_one(capsys) -> None:
    class _StaleRuns(_RecordingRuns):
        def retry_failed(self, project_id, run_id, *, selected_task_ids=None, idempotency_key=None):
            self._owner.calls.append(("runs.retry_failed", {"run_id": run_id}))
            return DomainResult.failure(
                ErrorObject(
                    code="stale_version",
                    message="run head moved while retrying",
                    details={"run_id": run_id},
                ),
                idempotency_key=idempotency_key or "generated-key",
            )

    class _StaleClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.runs = _StaleRuns(self)

    client = _StaleClient()
    rc = _run(
        "runs",
        ["retry-failed", "--project", "P-1", "R-1", "--task", "T-2", "--json"],
        client=client,
    )
    assert rc == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "stale_version"


def test_runs_show_not_found_human_mode_prints_error_to_stderr(capsys) -> None:
    class _NotFoundRuns(_RecordingRuns):
        def show(self, project_id, run_id, *, include_evidence=False):
            self._owner.calls.append(("runs.show", {"run_id": run_id}))
            return DomainResult.failure(
                ErrorObject(
                    code="not_found",
                    message="no such run",
                    details={"run_id": run_id},
                )
            )

    class _NotFoundClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.runs = _NotFoundRuns(self)

    client = _NotFoundClient()
    rc = _run("runs", ["show", "--project", "P-1", "R-999"], client=client)
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error not_found: no such run\n"


def test_runs_show_missing_project_is_a_usage_error() -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run("runs", ["show", "R-1"], client=client)
    assert excinfo.value.code == 2
    assert client.calls == []


def test_runs_help_is_executable_and_names_exactly_the_five_verbs(capsys) -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run("runs", ["--help"], client=client)
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    for verb in ("list", "show", "cancel", "retry-failed", "events"):
        assert verb in out
    assert client.calls == []


def test_runs_retry_failed_help_is_executable(capsys) -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run("runs", ["retry-failed", "--help"], client=client)
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "--task" in out
    assert "--idempotency-key" in out


def test_runs_events_help_explains_run_and_child_event_scope(capsys) -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run("runs", ["events", "--help"], client=client)
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "run-level" in out
    assert "tasks events" in out
    assert client.calls == []



# ---------------------------------------------------------------------------
# Project slug pass-through and loud unknown-address failure (v10 sensecheck)
# ---------------------------------------------------------------------------


def test_tasks_and_runs_forward_project_slug_untouched(capsys) -> None:
    """The CLI hands the slug string straight to the SDK service; slug ->
    id resolution lives in ``TasksService``/``RunsService`` (the same
    repository-driven resolution the media family relies on)."""
    client = _FakeClient()
    rc = _run("tasks", ["list", "--project", "my-slug"], client=client)
    assert rc == 0
    rc = _run("runs", ["list", "--project", "my-slug"], client=client)
    assert rc == 0
    assert client.calls == [
        ("tasks.list", {"project_id": "my-slug"}),
        ("runs.list", {"project_id": "my-slug"}),
    ]


def test_unknown_project_slug_is_a_loud_not_found_exit_one(capsys) -> None:
    """``runs list --project nope`` must fail loudly (typed ``not_found``,
    stderr error line, exit 1) — never a silently empty ``ok`` envelope."""

    class _NotFoundListRuns(_RecordingRuns):
        def list(self, project_id):
            return DomainResult.failure(
                ErrorObject(
                    code="not_found",
                    message=f"project address {project_id!r} not found",
                    details={},
                )
            )

    class _Client(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.runs = _NotFoundListRuns(self)

    client = _Client()
    rc = _run("runs", ["list", "--project", "nope", "--json"], client=client)
    assert rc == 1
    envelope = json.loads(capsys.readouterr().out)
    assert set(envelope) == ENVELOPE_KEYS
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "not_found"

# ---------------------------------------------------------------------------
# Gateway dispatch cutover for the tasks/runs families (m6)
# ---------------------------------------------------------------------------


def test_tasks_and_runs_are_registered_top_level_families() -> None:
    from astrid.core.gateway import dispatch

    assert {"tasks", "runs"} <= dispatch._top_level_commands()
    assert "tasks" in dispatch._TOP_LEVEL_HANDLERS
    assert "runs" in dispatch._TOP_LEVEL_HANDLERS


def test_dispatch_tasks_routes_through_product_dispatch(monkeypatch) -> None:
    from astrid.core.gateway import dispatch

    seen: dict[str, object] = {}

    def _fake_product(args):  # noqa: ANN001
        seen["args"] = list(args)
        return 7

    monkeypatch.setattr(dispatch, "_dispatch_product", _fake_product)
    handler = dispatch._TOP_LEVEL_HANDLERS["tasks"]
    assert handler(["list", "--project", "demo"]) == 7
    assert seen["args"] == ["tasks", "list", "--project", "demo"]


def test_dispatch_runs_routes_through_product_dispatch(monkeypatch) -> None:
    from astrid.core.gateway import dispatch

    seen: dict[str, object] = {}

    def _fake_product(args):  # noqa: ANN001
        seen["args"] = list(args)
        return 7

    monkeypatch.setattr(dispatch, "_dispatch_product", _fake_product)
    handler = dispatch._TOP_LEVEL_HANDLERS["runs"]
    assert handler(["list"]) == 7
    assert seen["args"] == ["runs", "list"]
