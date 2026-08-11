"""JSON contract tests for session attach/status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.foundation import project_paths
from astrid.core.project.current_run import write_current_run
from astrid.core.project.project import create_project
from astrid.core.cli import session as session_cli
from astrid.core.session import paths as session_paths
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.session.identity import Identity, write_identity
from astrid.core.session.lease import release_writer_lease, write_lease_init
from astrid.core.task.events import ZERO_HASH, append_event_locked
from astrid.core.timeline.crud import create_timeline
from tests.helpers.cli_runner import run_cli


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    (tmp_path / "home").mkdir()
    return {"home": tmp_path / "home", "projects": tmp_path / "projects"}


def _load_json(stdout: str) -> dict[str, object]:
    assert stdout.endswith("\n")
    lines = stdout.splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def test_attach_json_emits_single_object_and_routes_default_timeline_notice_to_stderr(
    env: dict[str, Path]
) -> None:
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")
    create_timeline("demo", "primary", is_default=True)

    result = run_cli(session_cli.main, ["attach", "demo", "--json"])

    assert result.exit_code == 0
    payload = _load_json(result.stdout)
    assert payload["schema_version"] == 1
    assert payload["state"] == "attached"
    assert payload["project"] == "demo"
    assert payload["timeline"] == "primary"
    assert payload["run_id"] is None
    assert payload["role"] == "writer"
    assert payload["attach_kind"] == "fresh"
    assert payload["agent_id"] == "claude-1"
    assert payload["export_line"] == f"export ASTRID_SESSION_ID={payload['session_id']}"
    assert "Using default timeline: primary. Use --timeline to override." in result.stderr
    assert "session created" not in result.stdout


def test_attach_json_reused_session_reports_reused_attach_kind(
    env: dict[str, Path]
) -> None:
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")
    create_timeline("demo", "primary")

    first = run_cli(session_cli.main, ["attach", "demo", "--timeline", "primary", "--json"])
    second = run_cli(session_cli.main, ["attach", "demo", "--timeline", "primary", "--json"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    first_payload = _load_json(first.stdout)
    second_payload = _load_json(second.stdout)
    assert first_payload["attach_kind"] == "fresh"
    assert second_payload["attach_kind"] == "reused"
    assert second_payload["session_id"] == first_payload["session_id"]


def test_attach_json_first_run_identity_fails_closed_without_prompt(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    create_project("demo")
    create_timeline("demo", "primary", is_default=True)

    def _fail_input(_prompt: str) -> str:
        raise AssertionError("attach --json should not prompt for identity bootstrap")

    monkeypatch.setattr("builtins.input", _fail_input)

    result = run_cli(session_cli.main, ["attach", "demo", "--json"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "attach: agent identity is not configured" in result.stderr
    assert "recovery: astrid attach demo" in result.stderr


def test_attach_json_missing_timeline_fails_closed_without_prompting(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")
    create_timeline("demo", "alpha")
    create_timeline("demo", "beta")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def _fail_input(_prompt: str) -> str:
        raise AssertionError("attach --json should not prompt for timeline selection")

    monkeypatch.setattr("builtins.input", _fail_input)

    result = run_cli(session_cli.main, ["attach", "demo", "--json"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "attach: no default timeline; pass --timeline <slug>" in result.stderr
    assert "valid options: alpha, beta" in result.stderr
    assert "recovery: astrid attach demo --timeline <slug>" in result.stderr


def test_status_json_unbound_emits_structured_recovery_context(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    result = run_cli(session_cli.main, ["status", "--json"])

    assert result.exit_code == 0
    payload = _load_json(result.stdout)
    assert payload["state"] == "no_session_bound"
    assert payload["project"] is None
    assert payload["session_id"] is None
    assert payload["discovered_projects"] == ["demo"]
    assert payload["next_command"] == "astrid projects select demo"
    assert result.stderr == ""


def test_status_json_bound_reader_emits_structured_session_fields(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mint_session
) -> None:
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")
    create_timeline("demo", "primary")
    run_dir = env["projects"] / "demo" / "runs" / "01RUN"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").touch()
    write_lease_init(run_dir, session_id="S-WRITER", plan_hash="")
    write_current_run("demo", "01RUN")
    reader = mint_session(
        env["home"],
        "S-READER",
        project="demo",
        run_id="01RUN",
        role="reader",
        timeline="primary",
    )
    append_event_locked(
        run_dir,
        {"kind": "step_dispatched", "plan_step_id": "step-1", "command": "noop"},
        expected_writer_epoch=0,
        expected_prev_hash=ZERO_HASH,
    )
    inbox = run_dir / "inbox"
    inbox.mkdir()
    (inbox / "ping.json").write_text('{"hello":"world"}', encoding="utf-8")
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, reader.id)

    result = run_cli(session_cli.main, ["status", "--json"])

    assert result.exit_code == 0
    payload = _load_json(result.stdout)
    assert payload["state"] == "reader"
    assert payload["session_id"] == "S-READER"
    assert payload["project"] == "demo"
    assert payload["timeline"] == "primary"
    assert payload["run_id"] == "01RUN"
    assert payload["current_step"] == "step-1"
    assert payload["inbox_count"] == 1
    assert payload["role"] == "reader"
    assert payload["task_command"] == "astrid next --project demo"
    assert payload["takeover_hint"] == "another session (S-WRITER) holds this run; take over with: astrid sessions takeover 01RUN"
    assert payload["recent_events"] == [{"kind": "step_dispatched", "ts": ""}]
    assert result.stderr == ""


def test_status_default_breadcrumb_prose_still_keeps_takeover_hint_on_stdout(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mint_session
) -> None:
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")
    run_dir = env["projects"] / "demo" / "runs" / "01RUN"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").touch()
    write_lease_init(run_dir, session_id="S-OLD", plan_hash="")
    release_writer_lease(run_dir)
    write_current_run("demo", "01RUN")
    caller = mint_session(
        env["home"], "S-CALL", project="demo", run_id="01RUN", timeline="primary"
    )
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, caller.id)

    result = run_cli(session_cli.main, ["status"])

    assert result.exit_code == 0
    assert "role: orphan-pending" in result.stdout
    assert "astrid sessions takeover 01RUN" in result.stdout
    assert result.stderr == ""
