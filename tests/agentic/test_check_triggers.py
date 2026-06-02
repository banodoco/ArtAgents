from __future__ import annotations

from pathlib import Path

from sisypy.public_api import load_scenario

from tests.agentic.checks.triggers import gate_trigger, resolve_trigger_records


def test_trigger_resolution_prefers_scenario_extras_over_manifest() -> None:
    records = resolve_trigger_records(
        scenario_extras={
            "project_slug": "scenario-slug",
            "m2_checks": {
                "c3_no_mutation_on_read": {"enabled": True, "note": "from-extras"},
                "s1_append_not_rewrite": {"enabled": False},
            },
            "ignored_surface": {"enabled": True},
        },
        manifest={
            "m2_checks": {
                "c3_no_mutation_on_read": {"enabled": False},
                "s1_append_not_rewrite": {"enabled": True},
                "s2_idempotent_reattach": {"enabled": True},
            },
            "tags": ["not-a-trigger-source"],
        },
    )

    assert records["C3"].enabled is True
    assert records["C3"].source == "scenario_extras"
    assert records["C3"].config == {"enabled": True, "note": "from-extras"}
    assert records["S1"].enabled is False
    assert records["S1"].source == "scenario_extras"
    assert records["S2"].enabled is False
    assert records["S2"].source == "absent"


def test_trigger_resolution_falls_back_to_manifest_when_extras_missing() -> None:
    records = resolve_trigger_records(
        scenario_extras={"project_slug": "scenario-only"},
        manifest={
            "m2_checks": {
                "s2_idempotent_reattach": {"enabled": True, "baseline": "captured"},
            },
            "assessment": {"ignored": True},
        },
    )

    assert records["S2"].enabled is True
    assert records["S2"].source == "manifest"
    assert records["S2"].config == {"enabled": True, "baseline": "captured"}
    assert records["C3"].source == "absent"


def test_absent_trigger_gates_c3_s1_and_s2_to_na() -> None:
    records = resolve_trigger_records()

    for check_id in ("C3", "S1", "S2"):
        result = gate_trigger(records[check_id], available_evidence=set())
        assert result == {
            "id": check_id,
            "status": "na",
            "evidence_refs": [],
            "detail": {
                "reason": "trigger not declared",
                "trigger_key": records[check_id].trigger_key,
            },
        }


def test_declared_trigger_missing_required_evidence_fails_for_c3_s1_and_s2() -> None:
    records = resolve_trigger_records(
        scenario_extras={
            "m2_checks": {
                "c3_no_mutation_on_read": {"enabled": True},
                "s1_append_not_rewrite": {"enabled": True},
                "s2_idempotent_reattach": {"enabled": True},
            }
        }
    )

    expected_missing = {
        "C3": ["final_events", "git_diff_patch"],
        "S1": ["final_events"],
        "S2": ["final_events", "reattach_diagnostics"],
    }
    available = {"baseline_events"}

    for check_id in ("C3", "S1", "S2"):
        result = gate_trigger(records[check_id], available_evidence=available)
        assert result == {
            "id": check_id,
            "status": "fail",
            "evidence_refs": [],
            "detail": {
                "reason": "declared trigger missing required evidence",
                "trigger_key": records[check_id].trigger_key,
                "trigger_source": "scenario_extras",
                "missing_evidence": expected_missing[check_id],
            },
        }


def test_declared_trigger_with_required_evidence_passes_gate() -> None:
    records = resolve_trigger_records(
        manifest={
            "m2_checks": {
                "c3_no_mutation_on_read": {"enabled": True},
                "c4_projection_fidelity": {"enabled": True},
            }
        }
    )

    assert gate_trigger(
        records["C3"],
        available_evidence={"baseline_events", "final_events", "git_diff_patch"},
    ) is None
    assert gate_trigger(records["C4"], available_evidence=set()) is None


def test_sisypy_loader_preserves_yaml_extras_m2_checks(tmp_path: Path) -> None:
    scenario_path = tmp_path / "triggered.yaml"
    scenario_path.write_text(
        "\n".join(
            [
                "name: triggered",
                "tier: 1",
                "description: loader contract",
                "extras:",
                "  project_slug: preserved-slug",
                "  m2_checks:",
                "    c3_no_mutation_on_read:",
                "      enabled: true",
                "      baseline: frozen",
                "    s2_idempotent_reattach:",
                "      enabled: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    scenario = load_scenario(scenario_path)

    assert scenario.extras == {
        "project_slug": "preserved-slug",
        "m2_checks": {
            "c3_no_mutation_on_read": {
                "enabled": True,
                "baseline": "frozen",
            },
            "s2_idempotent_reattach": {
                "enabled": True,
            },
        },
    }
