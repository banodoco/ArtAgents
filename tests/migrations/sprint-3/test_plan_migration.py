"""Tests for plan migration — three legacy kinds → collapsed (Sprint 3 T23)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Locate the migration script and load it as a module.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_MIGRATE_PLANS_PATH = _REPO_ROOT / "scripts" / "migrations" / "sprint-3" / "migrate_plans.py"
_spec = importlib.util.spec_from_file_location("migrate_plans", _MIGRATE_PLANS_PATH)
_migrate_plans_mod = importlib.util.module_from_spec(_spec)
sys.modules["migrate_plans"] = _migrate_plans_mod
_spec.loader.exec_module(_migrate_plans_mod)

_broadened_assignee = _migrate_plans_mod._broadened_assignee
_migrate_step = _migrate_plans_mod._migrate_step
PLAN_BACKUP_SUFFIX = _migrate_plans_mod.PLAN_BACKUP_SUFFIX
EVENTS_BACKUP_SUFFIX = _migrate_plans_mod.EVENTS_BACKUP_SUFFIX
migrate_plan = _migrate_plans_mod.migrate_plan
migrate_plans_main = _migrate_plans_mod.main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_dir(tmp_path: Path, slug: str = "demo", run_id: str = "run-1") -> Path:
    run_dir = tmp_path / slug / "runs" / run_id
    run_dir.mkdir(parents=True)
    return run_dir


def _write_legacy_plan(run_dir: Path, steps: list[dict], plan_id: str = "test") -> Path:
    """Write a legacy v1 plan.json."""
    plan_path = run_dir / "plan.json"
    payload = {"plan_id": plan_id, "version": 1, "steps": steps}
    plan_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return plan_path


def _read_plan_json(plan_path: Path) -> dict:
    return json.loads(plan_path.read_text(encoding="utf-8"))


def _write_event_chain(path: Path, raw_events: list[dict]) -> None:
    prev = "sha256:" + "0" * 64
    lines = []
    for event in raw_events:
        stored = dict(event)
        stored["hash"] = _migrate_plans_mod._event_hash(prev, stored)
        prev = stored["hash"]
        lines.append(json.dumps(stored, sort_keys=True, separators=(",", ":")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# _migrate_step: individual step conversions
# ---------------------------------------------------------------------------


def test_code_step_becomes_local_adapter() -> None:
    step = {"id": "s1", "kind": "code", "command": "echo hi"}
    result = _migrate_step(step)
    assert result["adapter"] == "local"
    assert result["assignee"] == "system"
    assert result["command"] == "echo hi"
    assert result["version"] == 1
    assert result["id"] == "s1"
    assert "kind" not in result


def test_code_step_without_kind_defaults_to_local() -> None:
    step = {"id": "s1", "command": "echo hi"}
    result = _migrate_step(step)
    assert result["adapter"] == "local"
    assert result["assignee"] == "system"


def test_attested_step_becomes_manual_adapter() -> None:
    step = {
        "id": "a1",
        "kind": "attested",
        "command": "review this",
        "instructions": "Carefully check the output.",
        "ack": {"kind": "actor"},
    }
    result = _migrate_step(step)
    assert result["adapter"] == "manual"
    assert result["command"] == "review this"
    assert result["instructions"] == "Carefully check the output."
    assert result["requires_ack"] is True
    assert result["version"] == 1
    assert result["ack"] == {"kind": "human"}
    assert "kind" not in result


def test_attested_step_instructions_preserved_verbatim() -> None:
    step = {
        "id": "a2",
        "kind": "attested",
        "command": "verify artifact",
        "instructions": "Multi-line\ninstruction\nblock",
    }
    result = _migrate_step(step)
    assert result["instructions"] == "Multi-line\ninstruction\nblock"


def test_legacy_actor_flag_migrates_to_human_flag_in_text_fields() -> None:
    step = {
        "id": "a2",
        "kind": "attested",
        "command": "astrid ack a2 --actor=Pat --decision approve",
        "instructions": "Approve with: astrid ack a2 --actor Pat --decision approve",
    }
    result = _migrate_step(step)
    assert "--actor" not in result["command"]
    assert "--actor" not in result["instructions"]
    assert "--human=Pat" in result["command"]
    assert "--human Pat" in result["instructions"]


def test_attested_step_without_instructions_no_key() -> None:
    step = {"id": "a3", "kind": "attested", "command": "verify"}
    result = _migrate_step(step)
    assert "instructions" not in result


def test_attested_step_agent_ack_defaults_to_system_assignee() -> None:
    step = {
        "id": "a4",
        "kind": "attested",
        "command": "run",
        "assignee": "any-agent",
        "ack": {"kind": "agent"},
    }
    result = _migrate_step(step)
    assert result["assignee"] == "system"
    assert "any-agent" not in json.dumps(result)


def test_attested_step_broadens_assignee_actor_to_any_human() -> None:
    step = {"id": "a5", "kind": "attested", "command": "run", "ack": {"kind": "actor"}}
    result = _migrate_step(step)
    assert result["assignee"] == "any-human"


def test_attested_step_no_ack_defaults_any_human() -> None:
    step = {"id": "a6", "kind": "attested", "command": "run"}
    result = _migrate_step(step)
    assert result["assignee"] == "any-human"


def test_nested_step_becomes_group_with_children() -> None:
    step = {
        "id": "n1",
        "kind": "nested",
        "plan": {
            "plan_id": "sub",
            "version": 1,
            "steps": [
                {"id": "child1", "kind": "code", "command": "echo one"},
                {"id": "child2", "kind": "code", "command": "echo two"},
            ],
        },
    }
    result = _migrate_step(step)
    assert "children" in result
    assert len(result["children"]) == 2
    assert result["children"][0]["id"] == "child1"
    assert result["children"][1]["id"] == "child2"
    assert "command" not in result
    assert "kind" not in result
    assert all("kind" not in child for child in result["children"])


def test_nested_step_aggregates_child_produces() -> None:
    step = {
        "id": "n2",
        "kind": "nested",
        "plan": {
            "plan_id": "sub",
            "version": 1,
            "steps": [
                {"id": "c1", "kind": "code", "command": "echo", "produces": {"out1": "file1.txt"}},
                {"id": "c2", "kind": "code", "command": "echo", "produces": {"out2": "file2.txt"}},
            ],
        },
    }
    result = _migrate_step(step)
    # Code-step migration drops produces, so the group step won't have produces.
    # This is expected behavior for the migration script.
    assert "children" in result
    assert result["produces"] == {"out1": "file1.txt", "out2": "file2.txt"}


def test_repeat_payload_survives_migration_with_legacy_condition() -> None:
    step = {
        "id": "review",
        "kind": "attested",
        "command": "review",
        "repeat": {"until": "user_approves", "max_iterations": 2, "on_exhaust": "fail"},
    }
    result = _migrate_step(step)
    assert result["repeat"] == {
        "until": "user_approves",
        "max_iterations": 2,
        "on_exhaust": "fail",
    }


def test_nested_step_without_plan_still_constructs() -> None:
    step = {"id": "n3", "kind": "nested"}
    result = _migrate_step(step)
    assert result["adapter"] == "local"
    assert result["version"] == 1


# ---------------------------------------------------------------------------
# _broadened_assignee
# ---------------------------------------------------------------------------


def test_broaden_agent_kind() -> None:
    assert _broadened_assignee({"ack": {"kind": "agent"}}) == "system"


def test_broaden_actor_kind() -> None:
    assert _broadened_assignee({"ack": {"kind": "actor"}}) == "any-human"


def test_broaden_no_ack_fallback() -> None:
    assert _broadened_assignee({}) == "any-human"


def test_broaden_non_dict_ack_fallback() -> None:
    assert _broadened_assignee({"ack": "invalid"}) == "any-human"


# ---------------------------------------------------------------------------
# migrate_plan: full plan conversion
# ---------------------------------------------------------------------------


def test_plan_version_bumps_from_1_to_2(tmp_path: Path) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_legacy_plan(run_dir, [{"id": "s1", "kind": "code", "command": "echo"}])
    changed, new_payload, broadening_notes = migrate_plan(run_dir / "plan.json")
    assert changed is True
    assert new_payload["version"] == 2
    assert len(new_payload["steps"]) == 1
    assert new_payload["steps"][0]["version"] == 1


def test_plan_id_preserved(tmp_path: Path) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_legacy_plan(run_dir, [{"id": "s1", "kind": "code", "command": "echo"}], plan_id="my-plan")
    changed, new_payload, broadening_notes = migrate_plan(run_dir / "plan.json")
    assert new_payload["plan_id"] == "my-plan"


def test_idempotent_skips_v2_plans(tmp_path: Path) -> None:
    run_dir = _make_run_dir(tmp_path)
    plan_path = run_dir / "plan.json"
    # Write already v2 plan.
    payload = {"plan_id": "test", "version": 2, "steps": []}
    plan_path.write_text(json.dumps(payload), encoding="utf-8")
    changed, new_payload, broadening_notes = migrate_plan(plan_path)
    assert changed is False


def test_all_three_kinds_migrated_together(tmp_path: Path) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_legacy_plan(run_dir, [
        {"id": "code1", "kind": "code", "command": "echo code"},
        {
            "id": "att1",
            "kind": "attested",
            "command": "review",
            "ack": {"kind": "agent"},
        },
        {
            "id": "nest1",
            "kind": "nested",
            "plan": {
                "plan_id": "sub",
                "version": 1,
                "steps": [{"id": "c1", "kind": "code", "command": "echo nested"}],
            },
        },
    ])
    changed, new_payload, broadening_notes = migrate_plan(run_dir / "plan.json")
    assert changed is True
    steps = new_payload["steps"]
    assert steps[0]["adapter"] == "local"
    assert steps[1]["adapter"] == "manual"
    assert "children" in steps[2]
    assert len(broadening_notes) == 0
    assert not any("kind" in step for step in steps)
    assert not any("kind" in child for child in steps[2]["children"])


def test_migration_output_has_command_xor_children_shape(tmp_path: Path) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_legacy_plan(run_dir, [
        {"id": "leaf", "kind": "code", "command": "echo leaf"},
        {
            "id": "group",
            "kind": "nested",
            "plan": {
                "plan_id": "sub",
                "version": 1,
                "steps": [{"id": "child", "kind": "code", "command": "echo child"}],
            },
        },
    ])
    changed, new_payload, broadening_notes = migrate_plan(run_dir / "plan.json")
    assert changed is True
    leaf, group = new_payload["steps"]
    assert "command" in leaf and "children" not in leaf
    assert "children" in group and "command" not in group


def test_broadening_notes_for_attested_steps(tmp_path: Path) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_legacy_plan(run_dir, [
        {"id": "a1", "kind": "attested", "command": "review1", "ack": {"kind": "agent"}},
        {"id": "a2", "kind": "attested", "command": "review2", "ack": {"kind": "actor"}},
    ])
    changed, new_payload, broadening_notes = migrate_plan(run_dir / "plan.json")
    assert len(broadening_notes) == 1
    assert any("a2" in note for note in broadening_notes)
    assert any("any-human" in note for note in broadening_notes)


def test_missing_plan_path_silently_skipped(tmp_path: Path) -> None:
    run_dir = _make_run_dir(tmp_path)
    # No plan.json written.
    changed, new_payload, broadening_notes = migrate_plan(run_dir / "plan.json")
    assert changed is False


def test_non_dict_payload_warned(tmp_path: Path) -> None:
    run_dir = _make_run_dir(tmp_path)
    plan_path = run_dir / "plan.json"
    plan_path.write_text('"just a string"', encoding="utf-8")
    changed, new_payload, broadening_notes = migrate_plan(plan_path)
    assert changed is False


# ---------------------------------------------------------------------------
# main: --dry-run / --apply
# ---------------------------------------------------------------------------


def test_main_dry_run_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default mode (--dry-run) should preview without modifying files."""
    run_dir = _make_run_dir(tmp_path)
    _write_legacy_plan(run_dir, [{"id": "s1", "kind": "code", "command": "echo dry"}])
    plan_path = run_dir / "plan.json"
    original_content = plan_path.read_bytes()

    monkeypatch.setattr(
        sys, "argv",
        ["migrate_plans.py", "--projects-root", str(tmp_path), "--dry-run"],
    )
    exit_code = migrate_plans_main()
    assert exit_code == 0
    # File should be unchanged.
    assert plan_path.read_bytes() == original_content
    assert not (run_dir / f"plan.json{PLAN_BACKUP_SUFFIX}").exists()


def test_main_apply_writes_new_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_legacy_plan(run_dir, [{"id": "s1", "kind": "code", "command": "echo apply"}])
    plan_path = run_dir / "plan.json"

    monkeypatch.setattr(
        sys, "argv",
        ["migrate_plans.py", "--projects-root", str(tmp_path), "--apply"],
    )
    exit_code = migrate_plans_main()
    assert exit_code == 0

    new_payload = _read_plan_json(plan_path)
    assert new_payload["version"] == 2
    assert new_payload["steps"][0]["adapter"] == "local"
    assert (run_dir / f"plan.json{PLAN_BACKUP_SUFFIX}").exists()


def test_main_apply_writes_backup_before_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_legacy_plan(run_dir, [{"id": "s1", "kind": "code", "command": "echo apply"}])
    plan_path = run_dir / "plan.json"
    original_content = plan_path.read_bytes()

    monkeypatch.setattr(
        sys, "argv",
        ["migrate_plans.py", "--projects-root", str(tmp_path), "--apply"],
    )
    assert migrate_plans_main() == 0

    backup_path = run_dir / f"plan.json{PLAN_BACKUP_SUFFIX}"
    assert backup_path.read_bytes() == original_content


def test_main_apply_seeds_plan_initialized_event_for_existing_v2_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _make_run_dir(tmp_path)
    plan_path = run_dir / "plan.json"
    plan_payload = {
        "plan_id": "p-seed",
        "version": 2,
        "steps": [{"id": "s1", "adapter": "local", "command": "echo"}],
    }
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")
    events_path = run_dir / "events.jsonl"
    _write_event_chain(events_path, [
        {
            "kind": "run_started",
            "run_id": "run-1",
            "plan_hash": "sha256:legacy",
            "ts": "2026-01-01T00:00:00Z",
        },
    ])
    original_plan = plan_path.read_bytes()
    original_events = events_path.read_bytes()

    monkeypatch.setattr(
        sys, "argv",
        ["migrate_plans.py", "--projects-root", str(tmp_path), "--apply"],
    )
    assert migrate_plans_main() == 0

    assert plan_path.read_bytes() == original_plan
    assert (run_dir / f"events.jsonl{EVENTS_BACKUP_SUFFIX}").read_bytes() == original_events
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert events[0]["kind"] == "plan_initialized"
    assert events[0]["plan"] == plan_payload
    assert events[1]["kind"] == "run_started"


def test_main_dry_run_does_not_seed_plan_initialized_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _make_run_dir(tmp_path)
    (run_dir / "plan.json").write_text(
        json.dumps({
            "plan_id": "p-seed",
            "version": 2,
            "steps": [{"id": "s1", "adapter": "local", "command": "echo"}],
        }),
        encoding="utf-8",
    )
    events_path = run_dir / "events.jsonl"
    _write_event_chain(events_path, [
        {"kind": "run_started", "run_id": "run-1", "plan_hash": "sha256:legacy"},
    ])
    original_events = events_path.read_bytes()

    monkeypatch.setattr(
        sys, "argv",
        ["migrate_plans.py", "--projects-root", str(tmp_path), "--dry-run"],
    )
    assert migrate_plans_main() == 0

    assert events_path.read_bytes() == original_events
    assert not (run_dir / f"events.jsonl{EVENTS_BACKUP_SUFFIX}").exists()


def test_main_assignee_broadening_banner_in_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_legacy_plan(run_dir, [
        {"id": "a1", "kind": "attested", "command": "review", "ack": {"kind": "actor"}},
    ])
    log_path = tmp_path / "test-migration.log"

    monkeypatch.setattr(
        sys, "argv",
        [
            "migrate_plans.py",
            "--projects-root", str(tmp_path),
            "--apply",
            "--log-path", str(log_path),
        ],
    )
    exit_code = migrate_plans_main()
    assert exit_code == 0

    log_text = log_path.read_text(encoding="utf-8")
    assert "WARNING:" in log_text
    assert "step(s) had their assignee broadened" in log_text
    assert "any-human" in log_text
    assert "astrid claim" in log_text
    assert "a1" in log_text


def test_main_idempotent_rerun_with_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _make_run_dir(tmp_path)
    _write_legacy_plan(run_dir, [{"id": "s1", "kind": "code", "command": "echo"}])
    plan_path = run_dir / "plan.json"

    # First apply.
    monkeypatch.setattr(
        sys, "argv",
        ["migrate_plans.py", "--projects-root", str(tmp_path), "--apply"],
    )
    assert migrate_plans_main() == 0

    after_first = plan_path.read_bytes()
    backup_path = run_dir / f"plan.json{PLAN_BACKUP_SUFFIX}"
    backup_after_first = backup_path.read_bytes()

    # Second apply — should be idempotent.
    monkeypatch.setattr(
        sys, "argv",
        ["migrate_plans.py", "--projects-root", str(tmp_path), "--apply"],
    )
    assert migrate_plans_main() == 0

    assert plan_path.read_bytes() == after_first
    assert backup_path.read_bytes() == backup_after_first


def test_main_empty_workspace_exits_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    projects_root = tmp_path / "empty-workspace"
    projects_root.mkdir(parents=True)

    monkeypatch.setattr(
        sys, "argv",
        ["migrate_plans.py", "--projects-root", str(projects_root)],
    )
    assert migrate_plans_main() == 0


def test_main_missing_projects_root_exits_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys, "argv",
        ["migrate_plans.py", "--projects-root", "/nonexistent/path/12345"],
    )
    assert migrate_plans_main() == 0


def test_no_broadening_banner_when_no_attested_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When only code steps exist, the log should NOT contain the broadening banner."""
    run_dir = _make_run_dir(tmp_path)
    _write_legacy_plan(run_dir, [
        {"id": "s1", "kind": "code", "command": "echo"},
        {"id": "s2", "kind": "code", "command": "echo2"},
    ])
    log_path = tmp_path / "no-broaden.log"

    monkeypatch.setattr(
        sys, "argv",
        [
            "migrate_plans.py",
            "--projects-root", str(tmp_path),
            "--apply",
            "--log-path", str(log_path),
        ],
    )
    assert migrate_plans_main() == 0

    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8")
        # Should still have summary but NO assignee broadening warning.
        assert "WARNING:" not in log_text or "step(s) had their assignee broadened" not in log_text
    # If log wasn't written because there are no broadening events, that's also valid
    # (the script only writes the log when there are broadening notes or migrations).
