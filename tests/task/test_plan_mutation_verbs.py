"""Tests for plan mutation verbs (Sprint 3 T21)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.task.plan import (
    SUPERSEDE_SCOPES,
    Step,
    TaskPlan,
    TaskPlanError,
    _validate_plan,
    iter_steps_with_path,
)
from astrid.core.task.plan_verbs import (
    PLAN_MUTATED_KIND,
    _apply_diff,
    _dispatched_step_paths,
    apply_mutations,
    build_parser,
    cmd_plan,
    cmd_plan_add_step,
    cmd_plan_edit_step,
    cmd_plan_remove_step,
    cmd_plan_supersede_step,
)
from astrid.core.task.validator import MutationInvariantError
from astrid.core.project.current_run import write_current_run
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.session.lease import bump_epoch_and_swap_session, read_lease
from astrid.core.session.model import Session, now_iso
from astrid.core.session.paths import session_path
from astrid.core.task.events import verify_chain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run_dir(tmp_path: Path, slug: str = "demo", run_id: str = "run-1") -> Path:
    run_dir = tmp_path / slug / "runs" / run_id
    run_dir.mkdir(parents=True)
    return run_dir


def _write_plan(run_dir: Path, steps: list[dict]) -> Path:
    plan_path = run_dir / "plan.json"
    payload = {"plan_id": "test", "version": 2, "steps": steps}
    plan_path.write_text(json.dumps(payload), encoding="utf-8")
    return plan_path


def _write_lease(run_dir: Path, epoch: int = 1) -> None:
    slug = run_dir.parent.parent.name
    run_id = run_dir.name
    projects_root = run_dir.parent.parent.parent
    sid = os.environ.get(ASTRID_SESSION_ID_ENV) or "S-PLAN-MUTATION"
    os.environ[ASTRID_SESSION_ID_ENV] = sid
    try:
        sess = Session.from_json(session_path(sid))
        sess = sess.with_changes(project=slug, run_id=run_id, last_used_at=now_iso())
    except Exception:
        sess = Session(
            id=sid,
            project=slug,
            agent_id="plan-mutation-test",
            attached_at="2026-05-11T00:00:00Z",
            last_used_at="2026-05-11T00:00:00Z",
            role="writer",
            timeline=None,
            run_id=run_id,
        )
    path = session_path(sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    sess.to_json(path)
    write_current_run(slug, run_id, root=projects_root)
    (run_dir / "lease.json").write_text(
        json.dumps({"writer_epoch": epoch, "attached_session_id": sid, "plan_hash": ""})
    )


def _write_events(run_dir: Path, events: list[dict]) -> None:
    events_path = run_dir / "events.jsonl"
    if not events:
        if events_path.exists():
            events_path.unlink()
        return
    lines = []
    for ev in events:
        ev_copy = dict(ev)
        ev_copy.pop("hash", None)
        lines.append(json.dumps(ev_copy, sort_keys=True, separators=(",", ":")))
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# apply_mutations tests
# ---------------------------------------------------------------------------

def test_apply_mutations_noop() -> None:
    plan = _validate_plan({
        "plan_id": "t", "version": 2,
        "steps": [{"id": "s1", "adapter": "local", "command": "echo"}],
    })
    result = apply_mutations(plan, [])
    assert len(result.steps) == 1
    assert result.steps[0].id == "s1"


def test_apply_mutations_add_step() -> None:
    plan = _validate_plan({
        "plan_id": "t", "version": 2,
        "steps": [{"id": "s1", "adapter": "local", "command": "echo a"}],
    })
    events = [{
        "kind": "plan_mutated",
        "diff": {
            "op": "add",
            "step": {"id": "s2", "adapter": "local", "command": "echo b"},
            "after": "s1",
        },
    }]
    result = apply_mutations(plan, events)
    assert len(result.steps) == 2
    assert result.steps[0].id == "s1"
    assert result.steps[1].id == "s2"


def test_apply_mutations_remove_step() -> None:
    plan = _validate_plan({
        "plan_id": "t", "version": 2,
        "steps": [
            {"id": "s1", "adapter": "local", "command": "echo a"},
            {"id": "s2", "adapter": "local", "command": "echo b"},
        ],
    })
    events = [{
        "kind": "plan_mutated",
        "diff": {"op": "remove", "path": "s2"},
    }]
    result = apply_mutations(plan, events)
    assert len(result.steps) == 1
    assert result.steps[0].id == "s1"


def test_apply_mutations_supersede_step() -> None:
    plan = _validate_plan({
        "plan_id": "t", "version": 2,
        "steps": [{"id": "s1", "adapter": "local", "command": "echo old"}],
    })
    events = [{
        "kind": "plan_mutated",
        "diff": {
            "op": "supersede",
            "path": "s1",
            "to_version": 2,
            "scope": "all",
            "step": {"id": "s1", "adapter": "local", "command": "echo new", "version": 2},
        },
    }]
    result = apply_mutations(plan, events)
    assert len(result.steps) == 1
    assert result.steps[0].version == 2
    assert result.steps[0].command == "echo new"


# ---------------------------------------------------------------------------
# argparse tests
# ---------------------------------------------------------------------------

def test_build_parser_has_four_subverbs() -> None:
    import argparse
    parser = build_parser()
    # Verify subparsers exist by checking the registered choices through the actions
    subparser_action = None
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparser_action = action
            break
    assert subparser_action is not None, "Expected subparsers"
    assert "add-step" in subparser_action.choices
    assert "edit-step" in subparser_action.choices
    assert "remove-step" in subparser_action.choices
    assert "supersede-step" in subparser_action.choices


def test_supersede_step_requires_scope() -> None:
    """Missing --scope is rejected at argparse (SystemExit)."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["supersede-step", "s1", "--project", "demo", "--run-id", "run-1"])


def test_supersede_step_accepts_scope() -> None:
    parser = build_parser()
    args = parser.parse_args([
        "supersede-step", "s1", "--project", "demo", "--run-id", "run-1",
        "--scope", "all",
    ])
    assert args.scope == "all"


# ---------------------------------------------------------------------------
# Dispatched-step detection
# ---------------------------------------------------------------------------

def test_dispatched_step_paths_detects_dispatched() -> None:
    events = [
        {"kind": "step_dispatched", "plan_step_path": ["s1"], "command": "echo"},
        {"kind": "step_dispatched", "plan_step_path": ["parent", "c1"], "command": "echo child"},
    ]
    dispatched = _dispatched_step_paths(events)
    assert "s1" in dispatched
    assert "parent/c1" in dispatched


def test_dispatched_step_paths_empty() -> None:
    assert _dispatched_step_paths([]) == set()


# ---------------------------------------------------------------------------
# edit-step / remove-step guard on dispatched steps
# ---------------------------------------------------------------------------

def test_edit_step_rejects_dispatched(tmp_path: Path) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_plan(run_dir, [{"id": "s1", "adapter": "local", "command": "echo"}])
    _write_lease(run_dir)
    _write_events(run_dir, [
        {"kind": "step_dispatched", "plan_step_path": ["s1"], "command": "echo"},
    ])
    argv = ["s1", "--project", "demo", "--run-id", "run-1", "--command", "echo new"]
    result = cmd_plan_edit_step(argv, projects_root=tmp_path)
    assert result == 1


def test_remove_step_rejects_dispatched(tmp_path: Path) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_plan(run_dir, [{"id": "s1", "adapter": "local", "command": "echo"}])
    _write_lease(run_dir)
    _write_events(run_dir, [
        {"kind": "step_dispatched", "plan_step_path": ["s1"], "command": "echo"},
    ])
    argv = ["s1", "--project", "demo", "--run-id", "run-1"]
    result = cmd_plan_remove_step(argv, projects_root=tmp_path)
    assert result == 1


# ---------------------------------------------------------------------------
# remove-step tombstone on undispatched
# ---------------------------------------------------------------------------

def test_remove_step_tombstone_undispatched(tmp_path: Path) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_plan(run_dir, [
        {"id": "s1", "adapter": "local", "command": "echo a"},
        {"id": "s2", "adapter": "local", "command": "echo b"},
    ])
    _write_lease(run_dir)
    _write_events(run_dir, [])
    argv = ["s2", "--project", "demo", "--run-id", "run-1"]
    result = cmd_plan_remove_step(argv, projects_root=tmp_path)
    assert result == 0
    # Verify event was written
    events = []
    events_path = run_dir / "events.jsonl"
    if events_path.exists():
        for line in events_path.read_text().strip().split("\n"):
            if line:
                events.append(json.loads(line))
    plan_mutated = [e for e in events if e.get("kind") == "plan_mutated"]
    assert len(plan_mutated) == 1
    assert plan_mutated[0]["diff"]["op"] == "remove"
    assert plan_mutated[0]["diff"]["path"] == "s2"


def test_stale_writer_plan_mutation_after_takeover_rejected_without_append(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_plan(run_dir, [
        {"id": "s1", "adapter": "local", "command": "echo a"},
        {"id": "s2", "adapter": "local", "command": "echo b"},
    ])
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, "S-TAB-A")
    _write_lease(run_dir, epoch=0)
    _write_events(run_dir, [])
    lease_path = run_dir / "lease.json"
    lease = json.loads(lease_path.read_text(encoding="utf-8"))
    lease["timeline_id"] = "01HTIMELINEPASSTHROUGH"
    lease["future_metadata"] = {"kept": True}
    lease_path.write_text(json.dumps(lease), encoding="utf-8")

    bump_epoch_and_swap_session(
        run_dir,
        new_session_id="S-TAB-B",
        prev_session_id="S-TAB-A",
        reason="test-takeover",
        force=True,
    )
    after_takeover_events = (run_dir / "events.jsonl").read_bytes()

    result = cmd_plan_remove_step(
        ["s2", "--project", "demo", "--run-id", "run-1"],
        projects_root=tmp_path,
    )

    assert result == 1
    assert (run_dir / "events.jsonl").read_bytes() == after_takeover_events
    ok, bad_idx, err = verify_chain(run_dir / "events.jsonl")
    assert ok, f"chain broken at event {bad_idx}: {err}"
    updated_lease = read_lease(run_dir)
    assert updated_lease["attached_session_id"] == "S-TAB-B"
    assert updated_lease["writer_epoch"] == 1
    assert updated_lease["timeline_id"] == "01HTIMELINEPASSTHROUGH"
    assert updated_lease["future_metadata"] == {"kept": True}
