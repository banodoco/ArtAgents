"""Sprint 5b: event_talks port test (T2 / T12).

Verifies the ported event_talks orchestrator emits a v2 plan.json,
declares ``consumes`` in run.json, and that the plan template has
correct adapter/cost assignments.
"""

from __future__ import annotations

import json
from pathlib import Path


def test_plan_template_emits_v2() -> None:
    """``build_plan_v2`` returns a plan dict with version 2 and valid steps."""
    from astrid.packs.builtin.event_talks.plan_template import build_plan_v2

    plan = build_plan_v2(
        python_exec="python3",
        run_root=Path("/tmp/test"),
        source=Path("/tmp/source.mp4"),
        run_id="test-run",
    )

    assert isinstance(plan, dict)
    assert plan.get("version") == 2
    assert plan.get("plan_id") is not None
    assert isinstance(plan.get("steps"), list)
    assert len(plan["steps"]) > 0

    # Every step must have adapter, command, and cost
    for step in plan["steps"]:
        assert "id" in step
        assert "adapter" in step
        assert "command" in step
        assert isinstance(step.get("cost"), dict)
        assert step["adapter"] in ("local", "manual", "remote-artifact")


def test_plan_template_steps_use_correct_adapters() -> None:
    """All event_talks steps use ``adapter: local`` (no LLM/RunPod calls)."""
    from astrid.packs.builtin.event_talks.plan_template import build_plan_v2

    plan = build_plan_v2(
        python_exec="python3",
        run_root=Path("/tmp/test"),
        source=Path("/tmp/source.mp4"),
        run_id="test-run",
    )

    for step in plan["steps"]:
        assert step["adapter"] == "local", (
            f"Step {step['id']} has adapter={step['adapter']!r}, "
            f"expected 'local'"
        )
        cost = step["cost"]
        assert cost.get("source") == "local"
        assert cost.get("amount") == 0


def test_plan_has_expected_step_ids() -> None:
    """The plan contains the four known event_talks steps."""
    from astrid.packs.builtin.event_talks.plan_template import build_plan_v2

    plan = build_plan_v2(
        python_exec="python3",
        run_root=Path("/tmp/test"),
        source=Path("/tmp/source.mp4"),
        run_id="test-run",
    )

    step_ids = {step["id"] for step in plan["steps"]}
    expected = {
        "ados-sunday-template",
        "search-transcript",
        "find-holding-screens",
        "render",
    }
    assert step_ids == expected, f"Unexpected step ids: {step_ids}"


def test_plan_template_uses_produces_root_placeholder_and_no_shell_redirects() -> None:
    from astrid.packs.builtin.event_talks.plan_template import build_plan_v2

    plan = build_plan_v2(
        python_exec="python3",
        run_root=Path("/tmp/test with spaces"),
        source=Path("/tmp/source with spaces.mp4"),
        transcript=Path("/tmp/transcript with spaces.json"),
        run_id="test-run",
    )

    commands = {step["id"]: step["command"] for step in plan["steps"]}
    assert "{produces_root}" in commands["ados-sunday-template"]
    assert "{produces_root}" in commands["search-transcript"]
    assert "{produces_root}" in commands["find-holding-screens"]
    assert "{produces_root}" in commands["render"]
    assert ">" not in commands["search-transcript"]


def test_emit_plan_json_writes_valid_json(tmp_path: Path) -> None:
    """``emit_plan_json`` writes a parsable plan.json file."""
    from astrid.packs.builtin.event_talks.plan_template import (
        build_plan_v2,
        emit_plan_json,
    )

    plan = build_plan_v2(
        python_exec="python3",
        run_root=tmp_path,
        source=Path("/tmp/source.mp4"),
        run_id="test-run",
    )

    plan_path = tmp_path / "plan.json"
    emit_plan_json(plan, plan_path)

    assert plan_path.is_file()
    loaded = json.loads(plan_path.read_text(encoding="utf-8"))
    assert loaded["version"] == 2
    assert len(loaded["steps"]) == 4


def test_pack_run_started_log_is_non_task_audit_log(tmp_path: Path) -> None:
    """The pack runner must not create a task-run ``events.jsonl`` ledger."""
    from astrid.packs.builtin.event_talks import run as event_talks_run

    event_talks_run._append_pack_run_started(tmp_path)

    assert not (tmp_path / "events.jsonl").exists()
    log_path = tmp_path / "pack_events.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["kind"] == "pack_run_started"
    assert "hash" not in event


def test_consumes_populated() -> None:
    """The plan template includes source media in its ``consumes`` list."""
    from astrid.packs.builtin.event_talks.plan_template import build_plan_v2

    source = Path("/tmp/source.mp4")
    plan = build_plan_v2(
        python_exec="python3",
        run_root=Path("/tmp/test"),
        source=source,
        run_id="test-run",
    )

    # Check that source is referenced in the plan (via command args or consumes)
    source_str = str(source)
    found = False
    for step in plan["steps"]:
        cmd = step.get("command", "")
        if source_str in cmd:
            found = True
            break
    assert found, (
        f"source {source_str!r} must be referenced in at least one step command;"
        f" found in none of {[s['id'] for s in plan['steps']]}"
    )


def test_plan_is_round_trip_stable(tmp_path: Path) -> None:
    """The emitted plan.json loads cleanly through ``load_plan``."""
    from astrid.packs.builtin.event_talks.plan_template import (
        build_plan_v2,
        emit_plan_json,
    )
    from astrid.core.task.plan import load_plan

    plan = build_plan_v2(
        python_exec="python3",
        run_root=tmp_path,
        source=Path("/tmp/source.mp4"),
        run_id="test-run",
    )

    plan_path = tmp_path / "plan.json"
    emit_plan_json(plan, plan_path)

    loaded = load_plan(plan_path)
    assert loaded.plan_id == plan["plan_id"]
    assert loaded.version == 2
    assert len(loaded.steps) == len(plan["steps"])
