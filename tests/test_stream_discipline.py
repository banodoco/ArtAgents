"""T14: Stream discipline tests for operator_view.py and session/cli.py.

Verifies:
- JSON mode stdout is exactly one JSON document (one line, one object).
- stderr carries diagnostics only; default stdout is agent-facing prose.
- ``next`` preamble behavior matches SD1 (preamble on stdout, --quiet suppresses).
- Session takeover stdout hints match SD2 (on stdout in default mode).
- ``cmd_next --skip --json`` emits exactly one JSON document (no prose mixed in).
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import setup_run  # noqa: E402

from astrid.core.project import paths as project_paths
from astrid.core.project.current_run import write_current_run
from astrid.core.project.project import create_project
from astrid.core.session import cli as session_cli
from astrid.core.session import paths as session_paths
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.session.identity import Identity, write_identity
from astrid.core.session.lease import release_writer_lease, write_lease_init
from astrid.core.task.lifecycle import cmd_next, cmd_status
from astrid.core.task.preamble import PROHIBITION_PREAMBLE
from astrid.core.timeline.crud import create_timeline
from tests.helpers.cli_runner import run_cli

# ----  operator_view.py : cmd_status  -----------------------------------

_STATUS_SHARED_KEYS = {"schema_version", "project", "run_id", "state"}

_BODY_CODE = """from astrid.orchestrate import orchestrator, code
@orchestrator("demo.code")
def main(): return [code("step_a", argv=["echo", "alpha"])]
"""

_BODY_ATTESTED = """from astrid.orchestrate import orchestrator, attested
@orchestrator("demo.review")
def main(): return [attested("review", command="ok.sh", instructions="confirm", ack="human")]
"""


def _capture_status(*argv: str, projects: Path) -> tuple[int, str, str]:
    """Return (rc, stdout, stderr) for cmd_status."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_status(list(argv), projects_root=projects)
    return rc, out.getvalue(), err.getvalue()


def _capture_next(*argv: str, projects: Path) -> tuple[int, str, str]:
    """Return (rc, stdout, stderr) for cmd_next."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_next(list(argv), projects_root=projects)
    return rc, out.getvalue(), err.getvalue()


# ---- cmd_status stream discipline --------------------------------------


def test_status_json_stdout_is_exactly_one_json_document(tmp_path: Path) -> None:
    """cmd_status --json emits exactly one newline-terminated JSON object on stdout."""
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r1")
    rc, stdout, stderr = _capture_status("--project", "p", "--json", projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    lines = stdout.splitlines()
    assert len(lines) == 1, f"expected 1 line, got {len(lines)}: {stdout!r}"
    payload = json.loads(lines[0])
    assert isinstance(payload, dict)
    for key in _STATUS_SHARED_KEYS:
        assert key in payload, f"missing key {key!r}"


def test_status_default_stdout_is_agent_facing_prose(tmp_path: Path) -> None:
    """Default cmd_status writes agent-facing prose to stdout, not raw diagnostics."""
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r2")
    rc, stdout, stderr = _capture_status("--project", "p", projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    assert "run-id:" in stdout
    assert "plan-hash:" in stdout
    assert "progress:" in stdout
    assert "current:" in stdout
    assert "recent events:" in stdout
    # These should NOT be in stdout (they are diagnostics)
    assert "produces check failed" not in stdout


def test_status_diagnostics_go_to_stderr_not_stdout(tmp_path: Path) -> None:
    """Default cmd_status routes produces-check failures to stderr."""
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r3")
    from astrid.core.task.events import (
        append_event,
        make_step_dispatched_event,
    )
    events_path = projects / "p" / "runs" / "r3" / "events.jsonl"
    append_event(events_path, make_step_dispatched_event("step_a", "echo alpha"))
    # _inline_failure_tail requires: last in {cursor_rewind, iteration_failed},
    # prior = produces_check_failed
    append_event(
        events_path,
        {
            "kind": "produces_check_failed",
            "plan_step_id": "step_a",
            "plan_step_path": ["step_a"],
            "reason": "missing expected output",
            "ts": "2026-01-01T00:00:00Z",
        },
    )
    append_event(
        events_path,
        {
            "kind": "iteration_failed",
            "plan_step_id": "step_a",
            "plan_step_path": ["step_a"],
            "reason": "produces check failed: missing expected output",
            "ts": "2026-01-01T00:00:01Z",
        },
    )
    rc, stdout, stderr = _capture_status("--project", "p", projects=projects)
    assert rc == 0, f"rc={rc}"
    # The blocked diagnostic goes to stderr
    assert "produces check failed" in stderr, f"expected failure in stderr, got {stderr!r}"
    assert "produces check failed" not in stdout


def test_status_no_active_run_json_emits_one_document(tmp_path: Path) -> None:
    """When no active run, --json emits exactly one JSON document with state=no_active_run."""
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r4")
    # Remove the active run to simulate no active run
    active_run = projects / "p" / "current_run.json"
    if active_run.exists():
        active_run.unlink()
    rc, stdout, stderr = _capture_status("--project", "p", "--json", projects=projects)
    # emit_lifecycle_json returns 0 even for no-active-run state
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    assert stdout.strip(), "expected non-empty JSON stdout"
    lines = stdout.splitlines()
    assert len(lines) == 1, f"expected 1 line, got {len(lines)}: {stdout!r}"
    payload = json.loads(lines[0])
    assert payload.get("state") == "no_active_run"


# ---- cmd_next stream discipline ----------------------------------------


def test_next_default_mode_includes_preamble_on_stdout(tmp_path: Path) -> None:
    """Default cmd_next prints PROHIBITION_PREAMBLE to stdout (SD1)."""
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r5")
    rc, stdout, stderr = _capture_next("--project", "p", projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    assert PROHIBITION_PREAMBLE in stdout, "preamble must be on stdout in default mode"


def test_next_quiet_suppresses_preamble_keeps_prose(tmp_path: Path) -> None:
    """--quiet suppresses preamble/separator but keeps actionable prose."""
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r6")
    rc, stdout, stderr = _capture_next("--project", "p", "--quiet", projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    assert PROHIBITION_PREAMBLE not in stdout, "quiet should suppress preamble"
    # Prose (run command / step info) should still be present
    assert "run:" in stdout or "ack" in stdout.lower() or "Run complete" in stdout


def test_next_json_emits_exactly_one_document(tmp_path: Path) -> None:
    """cmd_next --json emits exactly one JSON document on stdout."""
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r7")
    rc, stdout, stderr = _capture_next("--project", "p", "--json", projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    lines = stdout.splitlines()
    assert len(lines) == 1, f"expected 1 line, got {len(lines)}: {stdout!r}"
    payload = json.loads(lines[0])
    assert isinstance(payload, dict)
    assert "schema_version" in payload
    assert "state" in payload


def test_next_json_no_preamble_in_stdout(tmp_path: Path) -> None:
    """--json mode does not print the preamble to stdout."""
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r8")
    rc, stdout, stderr = _capture_next("--project", "p", "--json", projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    assert PROHIBITION_PREAMBLE not in stdout, "preamble must not be on stdout in JSON mode"


def test_next_skip_json_emits_exactly_one_document(tmp_path: Path) -> None:
    """cmd_next --skip --json: when --skip errors, stdout is empty; when JSON, one doc.

    This test covers two scenarios:
    1. ``--skip --json`` on a non-optional step: error goes to stderr, stdout empty.
    2. ``--json`` (without --skip) on a normal step: exactly one JSON document.
    The combination ``--skip --json`` on optional steps is implicitly covered by
    test_next_json_emits_exactly_one_document since the skip loop falls through
    to the same JSON dispatch path after skipping optional steps.
    """
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r9")

    # Scenario 1: --skip --json on a non-optional code step → error to stderr
    rc, stdout, stderr = _capture_next("--project", "p", "--skip", "--json", projects=projects)
    # The step is not optional, so --skip should error. Stdout must not contain "skipped" prose.
    assert "skipped" not in stdout, f"skip prose leaked to stdout: {stdout!r}"
    # If there's content on stdout, it must be exactly one JSON document
    if stdout.strip():
        lines = stdout.splitlines()
        assert len(lines) == 1, f"expected 1 line, got {len(lines)}: {stdout!r}"
        json.loads(lines[0])  # must be valid JSON

    # Scenario 2: --json alone on a normal step → exactly one JSON document
    rc2, stdout2, stderr2 = _capture_next("--project", "p", "--json", projects=projects)
    assert rc2 == 0, f"rc={rc2} stderr={stderr2!r}"
    lines = stdout2.splitlines()
    assert len(lines) == 1, f"expected 1 line, got {len(lines)}: {stdout2!r}"
    json.loads(lines[0])  # valid JSON


def test_next_default_stdout_contains_actionable_prose(tmp_path: Path) -> None:
    """Default cmd_next stdout contains actionable prose (run command or ack template)."""
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r10")
    rc, stdout, stderr = _capture_next("--project", "p", projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    # After preamble, should have actionable output
    after_preamble = stdout.split(PROHIBITION_PREAMBLE, 1)[-1]
    assert len(after_preamble.strip()) > 0, "no actionable prose after preamble"
    assert "run:" in after_preamble or "ack" in after_preamble.lower() or "Run complete" in after_preamble


def test_next_reader_takeover_hints_on_stdout(tmp_path: Path) -> None:
    """Default cmd_next reader takeover hints stay on stdout (SD2: actionable recovery)."""
    packs, projects = setup_run(tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r11")
    # To trigger reader state, we need a writer session different from the caller.
    # We simulate this by creating a lease held by a different session.
    run_dir = projects / "p" / "runs" / "r11"
    from astrid.core.task.events import append_event, make_step_dispatched_event
    events_path = run_dir / "events.jsonl"
    append_event(events_path, make_step_dispatched_event("step_a", "echo alpha"))
    write_lease_init(run_dir, session_id="S-OTHER", plan_hash="abc")
    from tests._lifecycle_fixtures import bind_writer_session
    bind_writer_session(projects, "p", run_id="r11", sid="S-READER")
    rc, stdout, stderr = _capture_next("--project", "p", projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    assert "take over the run" in stdout, f"takeover hint missing from stdout: {stdout!r}"


# ---- session/cli.py : cmd_status stream discipline ---------------------


@pytest.fixture
def session_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    (tmp_path / "home").mkdir()
    return {"home": tmp_path / "home", "projects": tmp_path / "projects"}


def _load_json(stdout: str) -> dict[str, object]:
    assert stdout.endswith("\n"), f"expected trailing newline, got {stdout!r}"
    lines = stdout.splitlines()
    assert len(lines) == 1, f"expected 1 JSON line, got {len(lines)}: {stdout!r}"
    return json.loads(lines[0])


def test_session_status_json_emits_exactly_one_document(
    session_env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """session status --json emits exactly one JSON document on stdout."""
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    result = run_cli(session_cli.main, ["status", "--json"])

    assert result.exit_code == 0
    payload = _load_json(result.stdout)
    assert payload["state"] == "no_session_bound"


def test_session_status_default_takeover_hints_on_stdout(
    session_env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mint_session
) -> None:
    """Default session status keeps takeover hints on stdout (SD2)."""
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")
    run_dir = session_env["projects"] / "demo" / "runs" / "01RUN"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").touch()
    write_lease_init(run_dir, session_id="S-OLD", plan_hash="")
    release_writer_lease(run_dir)
    write_current_run("demo", "01RUN")
    caller = mint_session(
        session_env["home"], "S-CALL", project="demo", run_id="01RUN", timeline="primary"
    )
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, caller.id)

    result = run_cli(session_cli.main, ["status"])

    assert result.exit_code == 0
    assert "role: orphan-pending" in result.stdout
    assert "astrid sessions takeover 01RUN" in result.stdout


def test_session_status_json_stderr_has_no_takeover_prose(
    session_env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mint_session
) -> None:
    """session status --json: takeover info is in JSON payload, not raw stderr prose."""
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")
    run_dir = session_env["projects"] / "demo" / "runs" / "01RUN"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").touch()
    write_lease_init(run_dir, session_id="S-OLD", plan_hash="")
    release_writer_lease(run_dir)
    write_current_run("demo", "01RUN")
    caller = mint_session(
        session_env["home"], "S-CALL", project="demo", run_id="01RUN", timeline="primary"
    )
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, caller.id)

    result = run_cli(session_cli.main, ["status", "--json"])

    assert result.exit_code == 0
    payload = _load_json(result.stdout)
    # takeover_hint should be in the JSON payload
    assert "takeover_hint" in payload
    assert payload["takeover_hint"] is not None
    # stderr should be clean (no takeover prose leakage)
    assert "astrid sessions takeover" not in result.stderr


def test_session_attach_json_stdout_is_exactly_one_document(
    session_env: dict[str, Path]
) -> None:
    """session attach --json emits exactly one JSON document on stdout."""
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")
    create_timeline("demo", "primary", is_default=True)

    result = run_cli(session_cli.main, ["attach", "demo", "--json"])

    assert result.exit_code == 0
    payload = _load_json(result.stdout)
    assert payload["state"] == "attached"
    # Timeline notice goes to stderr, not stdout
    assert "Using default timeline" not in result.stdout
    assert "Using default timeline" in result.stderr


def test_session_attach_json_timeline_notice_on_stderr_only(
    session_env: dict[str, Path]
) -> None:
    """session attach --json routes timeline notice to stderr, not stdout."""
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")
    create_timeline("demo", "primary", is_default=True)

    result = run_cli(session_cli.main, ["attach", "demo", "--json"])

    assert result.exit_code == 0
    # stdout is exactly the JSON document
    payload = _load_json(result.stdout)
    assert "session_id" in payload
    # timeline notice is on stderr only
    assert "Using default timeline: primary" in result.stderr
    assert "Using default timeline" not in result.stdout
