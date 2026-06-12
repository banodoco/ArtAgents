"""Phase 8 — happy path: inbox approve consumed via cmd_next.

Includes import-path compatibility: both ``astrid.core.io.inbox`` and
``astrid.core.task.operator.inbox`` expose identical symbols.
"""

from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import setup_run  # noqa: E402

from astrid.core.task.events import read_events, verify_chain
from astrid.core.task.lifecycle import cmd_next

# ---------------------------------------------------------------------------
# Import compatibility — prove the shim exposes identical symbols
# ---------------------------------------------------------------------------
import astrid.core.io.inbox as io_inbox
import astrid.core.task.operator.inbox as shim_inbox

_PUBLIC_HELPERS = (
    "CONSUMED_DIR_NAME",
    "INBOX_DIR_NAME",
    "REJECTED_DIR_NAME",
    "InboxEntry",
    "InboxValidationError",
    "consume_inbox_entry",
    "inbox_dir",
    "pending_count",
    "scan_inbox",
)


_BODY_AGENT = '''from astrid.core.orchestrate import orchestrator, attested
@orchestrator("demo.review_agent")
def main(): return [attested("review", command="review.sh", instructions="please review", ack="agent")]
'''


def _drop_inbox(run_dir: Path, payload: dict) -> Path:
    inbox = run_dir / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    file_path = inbox / "approve.json"
    file_path.write_text(json.dumps(payload), encoding="utf-8")
    return file_path


def test_inbox_approve_consumed_into_step_attested(tmp_path: Path) -> None:
    packs, projects = setup_run(
        tmp_path, "demo", "review_agent", _BODY_AGENT, "demo.review_agent", run_id="r-inbox-1"
    )
    run_dir = projects / "p" / "runs" / "r-inbox-1"
    events_path = run_dir / "events.jsonl"

    inbox_file = _drop_inbox(
        run_dir,
        {
            "step_id": "review",
            "decision": "approve",
            "evidence": {"note": "looks good"},
            "submitted_at": "2026-05-01T10:00:00Z",
            "submitted_by": "external-script",
        },
    )

    # Run cmd_next: T4 hooks scan_inbox + consume_inbox_entry into cmd_next.
    os.environ["ASTRID_ACTOR"] = "bob"
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        rc = cmd_next(["--project", "p"], projects_root=projects)
    assert rc == 0

    events = read_events(events_path)
    attested = [e for e in events if e.get("kind") == "step_attested"]
    assert len(attested) == 1
    ev = attested[0]
    assert ev.get("attestor_kind") == "agent"
    assert ev.get("attestor_id") == "external-script"
    assert ev.get("plan_step_id") == "review"

    ok, _last, _err = verify_chain(events_path)
    assert ok

    # Inbox file moved to inbox/.consumed/, not deleted.
    consumed_dir = run_dir / "inbox" / ".consumed"
    assert consumed_dir.is_dir()
    assert not inbox_file.exists()
    consumed_files = list(consumed_dir.iterdir())
    assert len(consumed_files) == 1

    # Follow-up cmd_next: run is exhausted. Completion is recorded by appending a
    # ``run_completed`` event to events.jsonl (cmd_next no longer prints a banner).
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(io.StringIO()):
        rc2 = cmd_next(["--project", "p"], projects_root=projects)
    assert rc2 == 0
    final_events = read_events(events_path)
    assert any(e.get("kind") == "run_completed" for e in final_events)


# ---------------------------------------------------------------------------
# Import compatibility: shim path exposes identical symbols
# ---------------------------------------------------------------------------


def test_shim_exports_all_public_helpers() -> None:
    """Every public helper is importable from ``astrid.core.task.operator.inbox``."""
    for name in _PUBLIC_HELPERS:
        assert hasattr(shim_inbox, name), f"shim missing {name}"


def test_shim_helpers_are_same_objects_as_io_inbox() -> None:
    """``astrid.core.task.operator.inbox`` re-exports the exact same function objects."""
    for name in _PUBLIC_HELPERS:
        io_obj = getattr(io_inbox, name)
        shim_obj = getattr(shim_inbox, name)
        assert io_obj is shim_obj, (
            f"{name}: io.inbox.{name} is not shim.{name}"
        )


def test_inbox_dir_through_shim(tmp_path: Path) -> None:
    """inbox_dir called through the shim returns the same path as io.inbox."""
    assert shim_inbox.inbox_dir(tmp_path) == io_inbox.inbox_dir(tmp_path)


def test_constants_through_shim() -> None:
    """Constants match between io.inbox and shim."""
    assert shim_inbox.INBOX_DIR_NAME == io_inbox.INBOX_DIR_NAME
    assert shim_inbox.CONSUMED_DIR_NAME == io_inbox.CONSUMED_DIR_NAME
    assert shim_inbox.REJECTED_DIR_NAME == io_inbox.REJECTED_DIR_NAME
