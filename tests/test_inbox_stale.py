"""Phase 8 — stale and malformed inbox files don't corrupt run state.

Includes import-path compatibility: both ``astrid.core.io.inbox`` and
``astrid.core.task.operator.inbox`` expose identical symbols.
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import setup_run  # noqa: E402

from astrid.core.task.events import read_events
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

_BODY_HUMAN = '''from astrid.core.orchestrate import orchestrator, attested
@orchestrator("demo.review_human")
def main(): return [attested("review", command="ok.sh", instructions="confirm", ack="human")]
'''


def _drop(run_dir: Path, name: str, payload) -> Path:
    inbox = run_dir / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    file_path = inbox / name
    if isinstance(payload, str):
        file_path.write_text(payload, encoding="utf-8")
    else:
        file_path.write_text(json.dumps(payload), encoding="utf-8")
    return file_path


def _run_next(projects: Path) -> int:
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return cmd_next(["--project", "p"], projects_root=projects)


def test_step_id_mismatch_leaves_file_in_place(tmp_path: Path) -> None:
    packs, projects = setup_run(
        tmp_path, "demo", "review_agent", _BODY_AGENT, "demo.review_agent",
        run_id="r-stale-a",
    )
    run_dir = projects / "p" / "runs" / "r-stale-a"
    events_path = run_dir / "events.jsonl"
    initial_count = len(read_events(events_path))

    inbox_file = _drop(
        run_dir,
        "wrong.json",
        {
            "step_id": "not-the-current-step",
            "decision": "approve",
            "evidence": {"note": "x"},
            "submitted_at": "2026-05-01T10:00:00Z",
            "submitted_by": "external-script",
        },
    )

    os.environ["ASTRID_ACTOR"] = "bob"
    rc = _run_next(projects)
    assert rc == 0

    # No new event — cursor unchanged.
    assert len(read_events(events_path)) == initial_count
    # Sprint-5b contract change (STOP-LINE in astrid/core/task/operator/inbox.py): stale
    # entries — including step_id mismatches against tombstoned/missing steps —
    # are now quarantined to inbox/.rejected/ rather than left in inbox/.
    assert not inbox_file.exists()
    rejected_dir = run_dir / "inbox" / ".rejected"
    assert rejected_dir.is_dir()
    assert len(list(rejected_dir.iterdir())) == 1


def test_approve_on_human_step_quarantined_to_rejected(
    tmp_path: Path, caplog
) -> None:
    packs, projects = setup_run(
        tmp_path, "demo", "review_human", _BODY_HUMAN, "demo.review_human",
        run_id="r-stale-b",
    )
    run_dir = projects / "p" / "runs" / "r-stale-b"
    events_path = run_dir / "events.jsonl"
    initial_count = len(read_events(events_path))

    inbox_file = _drop(
        run_dir,
        "human-approve.json",
        {
            "step_id": "review",
            "decision": "approve",
            "evidence": {"note": "x"},
            "submitted_at": "2026-05-01T10:00:00Z",
            "submitted_by": "external-script",
        },
    )

    os.environ["ASTRID_ACTOR"] = "bob"
    with caplog.at_level(logging.WARNING, logger="astrid.core.io.inbox"):
        rc = _run_next(projects)
    assert rc == 0

    # No event written.
    assert len(read_events(events_path)) == initial_count
    # File quarantined to inbox/.rejected/.
    rejected_dir = run_dir / "inbox" / ".rejected"
    assert rejected_dir.is_dir()
    assert len(list(rejected_dir.iterdir())) == 1
    assert not inbox_file.exists()
    assert any(
        "ack.kind=human" in record.message for record in caplog.records
    )


def test_malformed_json_skipped_and_logged(tmp_path: Path, caplog) -> None:
    packs, projects = setup_run(
        tmp_path, "demo", "review_agent", _BODY_AGENT, "demo.review_agent",
        run_id="r-stale-c",
    )
    run_dir = projects / "p" / "runs" / "r-stale-c"
    events_path = run_dir / "events.jsonl"
    initial_count = len(read_events(events_path))

    inbox_file = _drop(run_dir, "broken.json", "not valid json {")

    os.environ["ASTRID_ACTOR"] = "bob"
    with caplog.at_level(logging.WARNING, logger="astrid.core.io.inbox"):
        rc = _run_next(projects)
    assert rc == 0

    assert len(read_events(events_path)) == initial_count
    # Sprint-5b STOP-LINE: malformed JSON is quarantined to inbox/.rejected/ so it
    # does not loop on subsequent cmd_next invocations.
    assert not inbox_file.exists()
    rejected_dir = run_dir / "inbox" / ".rejected"
    assert rejected_dir.is_dir()
    assert len(list(rejected_dir.iterdir())) == 1
    assert any("broken.json" in record.message for record in caplog.records)


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
    run_dir = tmp_path / "run-shim"
    assert shim_inbox.inbox_dir(run_dir) == io_inbox.inbox_dir(run_dir)


def test_constants_through_shim() -> None:
    """Constants match between io.inbox and shim."""
    assert shim_inbox.INBOX_DIR_NAME == io_inbox.INBOX_DIR_NAME
    assert shim_inbox.CONSUMED_DIR_NAME == io_inbox.CONSUMED_DIR_NAME
    assert shim_inbox.REJECTED_DIR_NAME == io_inbox.REJECTED_DIR_NAME
