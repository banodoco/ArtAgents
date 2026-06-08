"""T6: ``cmd_ack --json`` structured output, abort delegation, and error envelope tests.

Verifies:
- ``--json`` on approve/retry/iterate success emits lifecycle JSON with shared fields.
- ``--decision abort --json`` forwards both ``--project`` and ``--json`` to ``cmd_abort``.
- Recoverable validation failures go through the shared error-envelope path (exit 2, stderr).
- Exactly-one-object-one-newline discipline in JSON mode.
"""

from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import setup_run  # noqa: E402

from astrid.core.task.events import (  # noqa: E402
    append_event,
    make_produces_check_failed_event,
    make_step_attested_event,
)
from astrid.core.task.lifecycle import cmd_ack  # noqa: E402
from tests.helpers.current_run import read_seeded_current_run  # noqa: E402

_ACK_SHARED_KEYS = {
    "schema_version",
    "project",
    "run_id",
    "state",
}

_ATTESTED_REVIEW = '''from astrid.core.orchestrate import orchestrator, attested
@orchestrator("demo.review")
def main(): return [attested("review", command="review.sh", instructions="please review", ack="human")]
'''

_ATTESTED_PRODUCES = '''from astrid.core.orchestrate import orchestrator, attested
from astrid.core.verify import json_file
@orchestrator("demo.with_produces")
def main(): return [attested("review", command="review.sh", instructions="check", ack="human", produces={"out": json_file()})]
'''

_ITER = '''from astrid.core.orchestrate import orchestrator, attested, repeat_until
@orchestrator("demo.iter")
def main(): return [attested("review", command="r.sh", instructions="ok", ack="human",
    repeat=repeat_until(condition="user_approves", max_iterations=3, on_exhaust="fail"))]
'''


def _capture_all(*argv: str, projects: Path) -> tuple[int, str, str]:
    """Return (rc, stdout, stderr)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_ack(list(argv), projects_root=projects)
    return rc, out.getvalue(), err.getvalue()


def _json_payload(*argv: str, projects: Path) -> dict:
    """Run cmd_ack with --json, assert success, return parsed payload."""
    rc, stdout, stderr = _capture_all(*argv, projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    assert stdout.count("\n") == 1, f"expected exactly one newline, got {stdout!r}"
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload


# ---------------------------------------------------------------------------
# Normal JSON success
# ---------------------------------------------------------------------------


def test_ack_json_approve_emits_shared_lifecycle_fields(tmp_path: Path) -> None:
    """--json approve emits shared lifecycle fields plus step_path/decision."""
    packs, projects = setup_run(
        tmp_path, "demo", "review", _ATTESTED_REVIEW, "demo.review",
        run_id="r_appr",
        start_actor="bob",
    )
    os.environ["ASTRID_ACTOR"] = "alice"

    payload = _json_payload(
        "review", "--project", "p", "--decision", "approve",
        "--human", "alice", "--json",
        projects=projects,
    )

    for key in _ACK_SHARED_KEYS:
        assert key in payload, f"missing shared key {key!r}"
    assert payload["schema_version"] == 1
    assert payload["project"] == "p"
    assert payload["state"] == "acknowledged"
    assert payload["step_path"] == "review"
    assert payload["decision"] == "approve"


def test_ack_json_retry_emits_shared_lifecycle_fields(tmp_path: Path) -> None:
    """--json retry after produces_check_failed emits state=retry_queued."""
    packs, projects = setup_run(
        tmp_path, "demo", "with_produces", _ATTESTED_PRODUCES,
        "demo.with_produces", run_id="r_retry",
        start_actor="bob",
    )
    os.environ["ASTRID_ACTOR"] = "alice"
    events_path = projects / "p" / "runs" / "r_retry" / "events.jsonl"
    append_event(events_path, make_step_attested_event("review", "human", "alice", ()))
    append_event(
        events_path,
        make_produces_check_failed_event(
            ("review",), "out", check_id="json_file:v1", reason="missing"
        ),
    )

    payload = _json_payload(
        "review", "--project", "p", "--decision", "retry",
        "--human", "alice", "--json",
        projects=projects,
    )

    for key in _ACK_SHARED_KEYS:
        assert key in payload, f"missing shared key {key!r}"
    assert payload["schema_version"] == 1
    assert payload["project"] == "p"
    assert payload["run_id"] == "r_retry"
    assert payload["state"] == "retry_queued"
    assert payload["step_path"] == "review"
    assert payload["decision"] == "retry"

    # Verify cursor_rewind event was appended.
    events = [
        json.loads(line)
        for line in events_path.read_text().splitlines()
    ]
    assert events[-1]["kind"] == "cursor_rewind"
    assert events[-1]["reason"] == "ack retry"


def test_ack_json_iterate_emits_shared_lifecycle_fields(tmp_path: Path) -> None:
    """--json iterate emits state=iteration_failed with iteration and feedback."""
    packs, projects = setup_run(
        tmp_path, "demo", "iter", _ITER, "demo.iter",
        run_id="r_iter",
        start_actor="bob",
    )
    os.environ["ASTRID_ACTOR"] = "alice"

    payload = _json_payload(
        "review", "--project", "p", "--decision", "iterate",
        "--human", "alice", "--feedback", "make it better", "--json",
        projects=projects,
    )

    for key in _ACK_SHARED_KEYS:
        assert key in payload, f"missing shared key {key!r}"
    assert payload["schema_version"] == 1
    assert payload["project"] == "p"
    assert payload["run_id"] == "r_iter"
    assert payload["state"] == "iteration_failed"
    assert payload["step_path"] == "review"
    assert payload["decision"] == "iterate"
    assert payload["iteration"] == 1
    assert payload["feedback"] == "make it better"

    # Verify iteration_failed event was appended.
    events = [
        json.loads(line)
        for line in (projects / "p" / "runs" / "r_iter" / "events.jsonl").read_text().splitlines()
    ]
    iter_failed = [e for e in events if e.get("kind") == "iteration_failed"]
    assert len(iter_failed) == 1
    assert iter_failed[0]["iteration"] == 1


# ---------------------------------------------------------------------------
# Abort delegation with JSON
# ---------------------------------------------------------------------------


def test_ack_json_abort_delegation_forwards_json(tmp_path: Path) -> None:
    """--decision abort --json delegates to cmd_abort with --json, producing abort JSON."""
    packs, projects = setup_run(
        tmp_path, "demo", "review", _ATTESTED_REVIEW, "demo.review",
        run_id="r_abdel",
        start_actor="bob",
    )
    assert read_seeded_current_run("p", root=projects) is not None

    rc, stdout, stderr = _capture_all(
        "review", "--project", "p", "--decision", "abort", "--json",
        projects=projects,
    )
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    assert stdout.count("\n") == 1, f"expected exactly one newline, got {stdout!r}"
    payload = json.loads(stdout)

    # Should have the abort JSON shape (state=aborted).
    for key in _ACK_SHARED_KEYS:
        assert key in payload, f"missing shared key {key!r}"
    assert payload["state"] == "aborted"
    assert payload["project"] == "p"
    assert payload["run_id"] == "r_abdel"

    # Verify run was actually aborted.
    assert read_seeded_current_run("p", root=projects) is None
    events = [
        json.loads(line)
        for line in (projects / "p" / "runs" / "r_abdel" / "events.jsonl").read_text().splitlines()
    ]
    assert events[-1]["kind"] == "run_aborted"


def test_ack_json_abort_delegation_without_json_preserves_human_output(tmp_path: Path) -> None:
    """--decision abort without --json produces human 'aborted <run_id>' on stdout."""
    packs, projects = setup_run(
        tmp_path, "demo", "review", _ATTESTED_REVIEW, "demo.review",
        run_id="r_abtxt",
        start_actor="bob",
    )

    rc, stdout, stderr = _capture_all(
        "review", "--project", "p", "--decision", "abort",
        projects=projects,
    )
    assert rc == 0
    assert "aborted r_abtxt" in stdout


# ---------------------------------------------------------------------------
# Error envelopes for recoverable validation failures
# ---------------------------------------------------------------------------


def test_ack_recoverable_validation_returns_exit_2(tmp_path: Path) -> None:
    """A recoverable validation failure (no active run) returns exit code 2."""
    packs, projects = setup_run(
        tmp_path, "demo", "review", _ATTESTED_REVIEW, "demo.review",
        run_id="r_val",
        start_actor="bob",
    )
    os.environ["ASTRID_ACTOR"] = "alice"

    # First abort to clear active run.
    from astrid.core.task.lifecycle import cmd_abort
    cmd_abort(["--project", "p"], projects_root=projects)

    rc, stdout, stderr = _capture_all(
        "review", "--project", "p", "--decision", "approve",
        "--human", "alice",
        projects=projects,
    )

    # Recoverable failure: no active run. Exit code must be 2 per SD3 taxonomy.
    assert rc == 2, f"expected exit 2 for recoverable failure, got rc={rc}"
    assert "no active run" in stderr


def test_ack_recoverable_error_cause_appears_on_stderr(tmp_path: Path) -> None:
    """The error cause text appears on stderr (via render_astrid_error)."""
    packs, projects = setup_run(
        tmp_path, "demo", "review", _ATTESTED_REVIEW, "demo.review",
        run_id="r_cause",
        start_actor="bob",
    )
    os.environ["ASTRID_ACTOR"] = "alice"

    # Approve on a code step is invalid; try ack on the attested step with a wrong
    # path to trigger step-path-mismatch (recoverable validation failure).
    rc, stdout, stderr = _capture_all(
        "nonexistent", "--project", "p", "--decision", "approve",
        "--human", "alice",
        projects=projects,
    )
    assert rc == 2, f"expected exit 2, got rc={rc}"
    assert "does not match cursor" in stderr


def test_ack_recoverable_error_includes_recovery_on_stderr(tmp_path: Path) -> None:
    """The recovery command is rendered on stderr."""
    packs, projects = setup_run(
        tmp_path, "demo", "review", _ATTESTED_REVIEW, "demo.review",
        run_id="r_rec",
        start_actor="bob",
    )
    os.environ["ASTRID_ACTOR"] = "alice"

    # First abort to clear active run.
    from astrid.core.task.lifecycle import cmd_abort
    cmd_abort(["--project", "p"], projects_root=projects)

    rc, stdout, stderr = _capture_all(
        "review", "--project", "p", "--decision", "approve",
        "--human", "alice",
        projects=projects,
    )
    assert rc == 2
    assert "recovery:" in stderr


# ---------------------------------------------------------------------------
# JSON discipline
# ---------------------------------------------------------------------------


def test_ack_json_one_object_one_newline(tmp_path: Path) -> None:
    """--json emits exactly one JSON object terminated by exactly one newline."""
    packs, projects = setup_run(
        tmp_path, "demo", "review", _ATTESTED_REVIEW, "demo.review",
        run_id="r_disc",
        start_actor="bob",
    )
    os.environ["ASTRID_ACTOR"] = "alice"

    rc, stdout, stderr = _capture_all(
        "review", "--project", "p", "--decision", "approve",
        "--human", "alice", "--json",
        projects=projects,
    )
    assert rc == 0
    assert stdout.count("\n") == 1, (
        f"expected exactly 1 newline, got {stdout.count(chr(10))} in {stdout!r}"
    )
    obj = json.loads(stdout)
    assert isinstance(obj, dict)
