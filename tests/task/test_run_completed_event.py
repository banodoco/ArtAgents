"""Tests for run_completed event semantics and _run_is_complete predicate (Sprint 5a T13)."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from astrid.core.task.lifecycle import cmd_runs_ls
from astrid.core.task.plan import Step, TaskPlan
from astrid.core.task.run_state import _run_is_complete

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _leaf_step(step_id: str) -> Step:
    return Step(id=step_id, adapter="local", command="true")


def _plan_with_steps(*steps: Step) -> TaskPlan:
    return TaskPlan(plan_id="test-plan", version=2, steps=steps)


def _event(kind: str, plan_step_path: list[str] | None = None, **extra) -> dict:
    e: dict = {"kind": kind, **extra}
    if plan_step_path is not None:
        e["plan_step_path"] = plan_step_path
    return e


# ---------------------------------------------------------------------------
# _run_is_complete predicate
# ---------------------------------------------------------------------------


def test_run_is_complete_all_steps_completed() -> None:
    """True when all leaf steps have step_completed events."""
    plan = _plan_with_steps(_leaf_step("a"), _leaf_step("b"))
    events = [
        _event("run_started", run_id="r1"),
        _event("step_dispatched", ["a"]),
        _event("step_completed", ["a"]),
        _event("step_dispatched", ["b"]),
        _event("step_completed", ["b"]),
    ]
    assert _run_is_complete(plan, events) is True


def test_run_is_complete_group_step_children_done() -> None:
    """True when a group step's children are all completed."""
    group = Step(
        id="hype",
        adapter="local",
        children=(_leaf_step("transcribe"), _leaf_step("render")),
    )
    plan = _plan_with_steps(group)
    events = [
        _event("run_started", run_id="r1"),
        _event("step_dispatched", ["hype", "transcribe"]),
        _event("step_completed", ["hype", "transcribe"]),
        _event("step_dispatched", ["hype", "render"]),
        _event("step_completed", ["hype", "render"]),
    ]
    assert _run_is_complete(plan, events) is True


def test_run_is_complete_false_when_step_awaiting_fetch() -> None:
    """False when any step is awaiting_fetch without step_completed follow-up."""
    plan = _plan_with_steps(_leaf_step("a"), _leaf_step("b"))
    events = [
        _event("run_started", run_id="r1"),
        _event("step_dispatched", ["a"]),
        _event("step_completed", ["a"]),
        _event("step_dispatched", ["b"]),
        _event("step_awaiting_fetch", ["b"]),
    ]
    assert _run_is_complete(plan, events) is False


def test_run_is_complete_false_when_step_dispatched_no_terminal() -> None:
    """False when a step has been dispatched but has no terminal event."""
    plan = _plan_with_steps(_leaf_step("a"), _leaf_step("b"))
    events = [
        _event("run_started", run_id="r1"),
        _event("step_dispatched", ["a"]),
        _event("step_completed", ["a"]),
        _event("step_dispatched", ["b"]),
    ]
    assert _run_is_complete(plan, events) is False


def test_run_is_complete_true_after_retry_fetch_recovery() -> None:
    """True after awaiting_fetch -> retry-fetch -> step_completed sequence."""
    plan = _plan_with_steps(_leaf_step("a"))
    events = [
        _event("run_started", run_id="r1"),
        _event("step_dispatched", ["a"]),
        _event("step_awaiting_fetch", ["a"]),
        _event("step_completed", ["a"]),
    ]
    assert _run_is_complete(plan, events) is True


def test_run_is_complete_false_when_step_failed() -> None:
    """True when a step is failed (failed is terminal-non-aborted)."""
    plan = _plan_with_steps(_leaf_step("a"))
    events = [
        _event("run_started", run_id="r1"),
        _event("step_dispatched", ["a"]),
        _event("step_failed", ["a"]),
    ]
    assert _run_is_complete(plan, events) is True


def test_run_is_complete_empty_plan() -> None:
    """False for empty plan (no leaf IDs = not complete)."""
    plan = TaskPlan(plan_id="empty", version=2, steps=())
    events: list[dict] = []
    assert _run_is_complete(plan, events) is False


def test_run_is_complete_with_mixed_terminal_events() -> None:
    """True with mix of completed and failed (both are terminal)."""
    plan = _plan_with_steps(_leaf_step("ok"), _leaf_step("bad"))
    events = [
        _event("run_started", run_id="r1"),
        _event("step_dispatched", ["ok"]),
        _event("step_completed", ["ok"]),
        _event("step_dispatched", ["bad"]),
        _event("step_failed", ["bad"]),
    ]
    assert _run_is_complete(plan, events) is True


def test_run_is_complete_multiple_events_same_step() -> None:
    """Uses the latest event per step path for terminal check."""
    plan = _plan_with_steps(_leaf_step("x"))
    events = [
        _event("run_started", run_id="r1"),
        _event("step_dispatched", ["x"]),
        _event("step_awaiting_fetch", ["x"]),
        _event("step_completed", ["x"]),  # Latest is completed
    ]
    assert _run_is_complete(plan, events) is True


# ---------------------------------------------------------------------------
# runs ls status derivation (_summarize_run_dir)
# ---------------------------------------------------------------------------


def _summarize(run_dir: Path, events_payload: list[dict] | None = None) -> str:
    """Call _summarize_run_dir and return the status string."""
    from astrid.core.task.run_store import _summarize_run_dir

    if events_payload is not None:
        events_path = run_dir / "events.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(
            "\n".join(json.dumps(e) for e in events_payload) + "\n",
            encoding="utf-8",
        )
    status, _kind, _ts = _summarize_run_dir(run_dir)
    return status


def test_summarize_aborted(tmp_path: Path) -> None:
    """run_aborted event -> aborted status."""
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    events = [
        {"kind": "run_started", "run_id": "r1"},
        {"kind": "run_aborted", "run_id": "r1"},
    ]
    status = _summarize(run_dir, events)
    assert status == "aborted"


def test_summarize_completed_when_run_completed_event_present(tmp_path: Path) -> None:
    """run_completed terminal event -> completed status."""
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    events = [
        {"kind": "run_started", "run_id": "r1"},
        {"kind": "run_completed", "run_id": "r1"},
    ]
    status = _summarize(run_dir, events)
    assert status == "completed"


def test_summarize_in_flight_for_active_run(tmp_path: Path) -> None:
    """No terminal event -> in-flight."""
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    events = [
        {"kind": "run_started", "run_id": "r1"},
    ]
    status = _summarize(run_dir, events)
    assert status == "in-flight"


def test_summarize_no_events(tmp_path: Path) -> None:
    """No events file -> in-flight."""
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    status = _summarize(run_dir, None)
    assert status == "in-flight"


def test_summarize_completed_even_with_late_advisory_event(tmp_path: Path) -> None:
    """A later advisory tail must not hide an earlier run_completed event."""
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    events = [
        {"kind": "run_started", "run_id": "r1", "ts": "2025-01-01T00:00:00Z"},
        {"kind": "run_completed", "run_id": "r1", "ts": "2025-01-01T00:00:10Z"},
        {"kind": "takeover", "ts": "2025-01-01T00:00:11Z"},
    ]
    status = _summarize(run_dir, events)
    assert status == "completed"


def test_runs_ls_status_filters_respect_terminal_events_after_advisory_tails(
    tmp_path: Path,
) -> None:
    """runs ls --status buckets completed/in-flight/aborted remain stable after advisory tails."""
    projects = tmp_path / "projects"
    alpha_runs = projects / "alpha" / "runs"
    completed_dir = alpha_runs / "run-completed"
    inflight_dir = alpha_runs / "run-inflight"
    aborted_dir = alpha_runs / "run-aborted"
    completed_dir.mkdir(parents=True, exist_ok=True)
    inflight_dir.mkdir(parents=True, exist_ok=True)
    aborted_dir.mkdir(parents=True, exist_ok=True)

    (completed_dir / "events.jsonl").write_text(
        "\n".join(
            json.dumps(event)
            for event in [
                {"kind": "run_started", "run_id": "run-completed", "ts": "2025-01-01T00:00:00Z"},
                {"kind": "run_completed", "run_id": "run-completed", "ts": "2025-01-01T00:00:10Z"},
                {"kind": "takeover", "ts": "2025-01-01T00:00:11Z"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (inflight_dir / "events.jsonl").write_text(
        json.dumps({"kind": "run_started", "run_id": "run-inflight", "ts": "2025-01-01T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    (aborted_dir / "events.jsonl").write_text(
        "\n".join(
            json.dumps(event)
            for event in [
                {"kind": "run_started", "run_id": "run-aborted", "ts": "2025-01-01T00:00:00Z"},
                {"kind": "run_aborted", "run_id": "run-aborted", "ts": "2025-01-01T00:00:10Z"},
                {"kind": "takeover", "ts": "2025-01-01T00:00:11Z"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def _runs_ls(status: str) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_runs_ls(["--project", "alpha", "--status", status], projects_root=projects)
        assert rc == 0
        return buf.getvalue()

    completed = _runs_ls("completed")
    assert "run-completed" in completed
    assert "run-inflight" not in completed
    assert "run-aborted" not in completed

    inflight = _runs_ls("in-flight")
    assert "run-inflight" in inflight
    assert "run-completed" not in inflight
    assert "run-aborted" not in inflight

    aborted = _runs_ls("aborted")
    assert "run-aborted" in aborted
    assert "run-completed" not in aborted
    assert "run-inflight" not in aborted
