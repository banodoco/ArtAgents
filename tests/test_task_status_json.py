"""T4: ``cmd_status --json`` structured output and stream-discipline tests.

Verifies:
- ``--json`` emits exactly one JSON object with shared lifecycle fields.
- ``--json`` payload includes progress/current-step metadata.
- Default mode keeps non-diagnostic human prose on stdout.
- Diagnostics (produces-check failures, cursor-rewind errors) go to stderr.
- No-active-run ``--json`` produces a structured error object.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import setup_run  # noqa: E402

from astrid.core.task.events import (  # noqa: E402
    append_event,
    make_step_completed_event,
    make_step_dispatched_event,
)
from astrid.core.task.lifecycle import cmd_status  # noqa: E402

_STATUS_SHARED_KEYS = {
    "schema_version",
    "project",
    "run_id",
    "state",
}

_BODY = '''from astrid.orchestrate import orchestrator, code
@orchestrator("demo.app")
def app(): return [
    code("step_a", argv=["echo","a"]),
    code("step_b", argv=["echo","b"]),
]
'''


def _capture_all(*argv: str, projects: Path) -> tuple[int, str, str]:
    """Return (rc, stdout, stderr)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_status(list(argv), projects_root=projects)
    return rc, out.getvalue(), err.getvalue()


def _json_payload(*argv: str, projects: Path) -> dict:
    rc, stdout, stderr = _capture_all(*argv, projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    assert stdout.count("\n") == 1, f"expected exactly one newline, got {stdout!r}"
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload


def test_status_json_has_shared_lifecycle_fields(tmp_path: Path) -> None:
    """--json emits shared lifecycle fields (schema_version, project, run_id, state)."""
    packs, projects = setup_run(tmp_path, "demo", "app", _BODY, "demo.app", run_id="r1")
    payload = _json_payload("--project", "p", "--json", projects=projects)
    for key in _STATUS_SHARED_KEYS:
        assert key in payload, f"missing shared key {key!r}"
    assert payload["schema_version"] == 1
    assert payload["project"] == "p"
    assert payload["run_id"] == "r1"
    assert payload["state"] in ("running", "blocked", "completed", "failed", "aborted")


def test_status_json_includes_progress_and_current_step(tmp_path: Path) -> None:
    """--json includes progress/total and current-step metadata."""
    packs, projects = setup_run(tmp_path, "demo", "app", _BODY, "demo.app", run_id="r2")
    # Dispatch and complete step_a so the cursor moves to step_b.
    events_path = projects / "p" / "runs" / "r2" / "events.jsonl"
    append_event(events_path, make_step_dispatched_event("step_a", "echo a"))
    append_event(events_path, make_step_completed_event("step_a", 0))

    payload = _json_payload("--project", "p", "--json", projects=projects)

    assert payload["progress_completed"] == 1
    assert payload["progress_total"] == 2
    assert payload["current_step"] == "step_b"
    assert payload["current_step_kind"] == "code"
    assert payload["current_step_version"] is not None
    assert payload["inbox_pending"] == 0


def test_status_json_exhausted_run(tmp_path: Path) -> None:
    """--json on an exhausted run reports current_step as None."""
    packs, projects = setup_run(tmp_path, "demo", "app", _BODY, "demo.app", run_id="r3")
    events_path = projects / "p" / "runs" / "r3" / "events.jsonl"
    # Complete both steps.
    for step_id in ("step_a", "step_b"):
        append_event(events_path, make_step_dispatched_event(step_id, f"echo {step_id[-1]}"))
        append_event(events_path, make_step_completed_event(step_id, 0))

    payload = _json_payload("--project", "p", "--json", projects=projects)

    assert payload["progress_completed"] == 2
    assert payload["progress_total"] == 2
    assert payload["current_step"] is None
    assert payload["state"] in ("completed", "running")  # may or may not have run_completed


def test_status_json_no_active_run(tmp_path: Path) -> None:
    """--json from no-active-run state emits an error field and state=no_active_run."""
    projects = tmp_path / "projects"
    projects.mkdir()
    rc, stdout, stderr = _capture_all("--project", "missing", "--json", projects=projects)
    # JSON mode returns 0 even for no-active-run — the payload conveys the error.
    assert rc == 0
    payload = json.loads(stdout.strip())
    assert payload["state"] == "no_active_run"
    assert payload["project"] == "missing"
    assert payload["run_id"] is None
    assert "no active run" in payload.get("error", "")


def test_default_mode_keeps_prose_on_stdout(tmp_path: Path) -> None:
    """Default mode prints non-diagnostic human prose to stdout."""
    packs, projects = setup_run(tmp_path, "demo", "app", _BODY, "demo.app", run_id="r5")
    events_path = projects / "p" / "runs" / "r5" / "events.jsonl"
    append_event(events_path, make_step_dispatched_event("step_a", "echo a"))
    append_event(events_path, make_step_completed_event("step_a", 0))

    rc, stdout, stderr = _capture_all("--project", "p", projects=projects)
    assert rc == 0
    assert "run-id:" in stdout
    assert "plan-hash:" in stdout
    assert "progress:" in stdout
    assert "current:" in stdout
    assert "recent events:" in stdout
    assert "step_b" in stdout


def test_default_mode_diagnostics_go_to_stderr(tmp_path: Path) -> None:
    """Diagnostics (produces-check failures, cursor-rewind) go to stderr, not stdout."""
    packs, projects = setup_run(tmp_path, "demo", "app", _BODY, "demo.app", run_id="r6")
    events_path = projects / "p" / "runs" / "r6" / "events.jsonl"
    # Simulate a blocked run: produces_check_failed + cursor_rewind tail.
    append_event(events_path, make_step_dispatched_event("step_a", "echo a"))
    append_event(events_path, {"kind": "produces_check_failed", "reason": "missing output", "plan_step_path": ["step_a"]})
    append_event(events_path, {"kind": "cursor_rewind", "reason": "produces check", "plan_step_path": ["step_a"]})

    rc, stdout, stderr = _capture_all("--project", "p", projects=projects)
    assert rc == 0
    # The blocked diagnostics should be on stderr.
    assert "blocked" in stderr.lower() or "produces check failed" in stderr.lower()
    # Non-diagnostic output stays on stdout.
    assert "run-id:" in stdout
    assert "progress:" in stdout
    assert "recent events:" in stdout
    # The blocked message should NOT be on stdout.
    assert "produces check failed" not in stdout
    assert "blocked:" not in stdout.lower() or "blocked:" not in stdout


def test_status_json_one_object_one_newline(tmp_path: Path) -> None:
    """--json emits exactly one JSON object terminated by exactly one newline."""
    packs, projects = setup_run(tmp_path, "demo", "app", _BODY, "demo.app", run_id="r7")
    rc, stdout, stderr = _capture_all("--project", "p", "--json", projects=projects)
    assert rc == 0
    assert stdout.count("\n") == 1, f"expected exactly 1 newline, got {stdout.count(chr(10))} in {stdout!r}"
    # Verify it's valid JSON.
    obj = json.loads(stdout)
    assert isinstance(obj, dict)
