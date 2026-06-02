from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from tests.agentic.normalize import (
    SCENARIOS_DIR,
    discover_scenarios,
    normalize_scenario,
)

EXPECTED_PRODUCTION_SCENARIOS = 45  # 36 M3/M4 + 6 M5 + 3 reconciled (midstream_shrink, abandon_and_return_changed_intent, advanced_assemble_sequence)
M4_SCENARIO_NAMES = frozenset(
    [
        "artifact_pipeline",
        "durability_after_crash",
        "orchestrator_run_persists",
        "taskrun_concurrent_lease",
        "timeline_compose_edit",
        "timeline_concurrent_version_conflict",
        "timeline_large_audit",
    ]
)
M5_SCENARIO_NAMES = frozenset(
    [
        "cross_pack_authoring",
        "broken_authoring_fix",
        "no_tool_exists_pushback",
        "discover_projects_runs_sessions",
        "author_run_revise_loop",
        "recover_from_no_search_results",
    ]
)


def test_discover_scenarios_defaults_to_36_production_yamls() -> None:
    discovered = discover_scenarios()

    assert len(discovered) == EXPECTED_PRODUCTION_SCENARIOS
    assert all(path.suffix == ".yaml" for path in discovered)
    assert all(not path.name.startswith("_") for path in discovered)
    assert SCENARIOS_DIR / "_schema.yaml" not in discovered
    assert SCENARIOS_DIR / "_smoke.yaml" not in discovered

    discovered_stems = {path.stem for path in discovered}
    for name in M4_SCENARIO_NAMES:
        assert name in discovered_stems, f"M4 scenario {name!r} must be discovered by default"


def test_discover_scenarios_allows_explicit_smoke_and_preserves_order() -> None:
    discovered = discover_scenarios(["reader_takeover", "_smoke"])

    assert [path.name for path in discovered] == [
        "reader_takeover.yaml",
        "_smoke.yaml",
    ]


def test_discover_scenarios_raises_for_missing_legacy_name(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        discover_scenarios(["missing_scenario"], scenarios_dir=tmp_path)


def test_normalize_scenario_expands_agents_and_mirrors_legacy_fields() -> None:
    scenario = {
        "name": "normalize-contract",
        "target_orchestrator": "builtin.agent_probe",
        "acceptance": [{"events_contain": "run_completed"}],
        "agents": [
            {
                "model": "deepseek-v4-pro",
                "count": 2,
                "subagent_type": "general-purpose",
                "config": {"temperature": 0.1},
            },
            {
                "model": "",
                "count": 1,
                "dispatcher": "fake",
            },
        ],
        "extras": {"project_slug": "keep-me"},
        "assessment": {
            "universal_checks": True,
            "enforced": [{"id": "kept"}],
        },
    }

    normalized = normalize_scenario(scenario)

    assert scenario["agents"][0]["count"] == 2
    assert scenario["assessment"]["universal_checks"] is True

    assert normalized["target_orchestrator"] == "builtin.agent_probe"
    assert normalized["acceptance"] == [{"events_contain": "run_completed"}]
    assert normalized["extras"] == {
        "project_slug": "keep-me",
        "target_orchestrator": "builtin.agent_probe",
        "legacy_acceptance": [{"events_contain": "run_completed"}],
        "universal_checks": True,
    }
    assert normalized["assessment"] == {
        "enforced": [{"id": "kept"}],
    }
    assert normalized["agents"] == [
        {
            "model": "deepseek-v4-pro",
            "config": {
                "temperature": 0.1,
                "subagent_type": "general-purpose",
            },
        },
        {
            "model": "deepseek-v4-pro",
            "config": {
                "temperature": 0.1,
                "subagent_type": "general-purpose",
            },
        },
        {
            "model": "",
            "dispatcher": "fake",
        },
    ]


def test_runner_main_normalizes_selected_scenarios_and_preserves_sisypy_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.agentic import runner

    captured: dict[str, object] = {}
    parsed_args = argparse.Namespace(
        scenarios=["reader_takeover", "_smoke"],
        scenarios_dir="scenarios",
        briefs_dir="briefs",
        reports_dir="reports",
        mode="structural",
        actor="fake",
        tag="batch-6",
        tags=["reader_state"],
        var=["SLUG=demo-project"],
        dry_run=True,
        cross_diff=False,
        parallel=True,
        no_parallel=True,
        capture_interval_sec=0,
        verbose=True,
        reassess=None,
    )

    class FakeParser:
        def parse_args(self, argv: list[str]) -> argparse.Namespace:
            captured["argv"] = list(argv)
            return parsed_args

    def fake_build_cli_parser(adapter: object) -> FakeParser:
        captured["adapter"] = adapter
        return FakeParser()

    def fake_run_from_args(adapter: object, args: argparse.Namespace) -> dict[str, object]:
        captured["run_adapter"] = adapter
        captured["args"] = SimpleNamespace(**vars(args))
        temp_dir = Path(args.scenarios_dir)
        captured["normalized_files"] = sorted(path.name for path in temp_dir.glob("*.yaml"))
        captured["normalized_reader_takeover"] = yaml.safe_load(
            (temp_dir / "reader_takeover.yaml").read_text(encoding="utf-8")
        )
        captured["normalized_smoke"] = yaml.safe_load(
            (temp_dir / "_smoke.yaml").read_text(encoding="utf-8")
        )
        return {"scenario_count": 2, "scenario_names": ["reader_takeover", "_smoke"]}

    monkeypatch.setattr("sisypy.build_cli_parser", fake_build_cli_parser)
    monkeypatch.setattr("sisypy.run_from_args", fake_run_from_args)
    monkeypatch.setattr("sisypy.summary_exit_code", lambda result: 0)

    with pytest.raises(SystemExit) as excinfo:
        runner.main(
            [
                "reader_takeover",
                "_smoke",
                "--actor",
                "fake",
                "--mode",
                "structural",
                "--dry-run",
                "--tag",
                "batch-6",
                "--tags",
                "reader_state",
                "--var",
                "SLUG=demo-project",
                "--no-parallel",
                "--verbose",
            ]
        )

    assert excinfo.value.code == 0
    assert captured["argv"] == [
        "reader_takeover",
        "_smoke",
        "--actor",
        "fake",
        "--mode",
        "structural",
        "--dry-run",
        "--tag",
        "batch-6",
        "--tags",
        "reader_state",
        "--var",
        "SLUG=demo-project",
        "--no-parallel",
        "--verbose",
    ]

    forwarded_args = captured["args"]
    assert forwarded_args.scenarios == ["reader_takeover", "_smoke"]
    assert forwarded_args.actor == "fake"
    assert forwarded_args.mode == "structural"
    assert forwarded_args.dry_run is True
    assert forwarded_args.tag == "batch-6"
    assert forwarded_args.tags == ["reader_state"]
    assert forwarded_args.var == ["SLUG=demo-project"]
    assert forwarded_args.no_parallel is True
    assert Path(forwarded_args.briefs_dir) == runner.BRIEFS_DIR
    assert captured["normalized_files"] == ["_smoke.yaml", "reader_takeover.yaml"]
    assert captured["normalized_reader_takeover"]["extras"]["target_orchestrator"] == "builtin.agent_probe"
    assert captured["normalized_reader_takeover"]["extras"]["legacy_acceptance"] == [
        {"events_contain": "takeover"},
        {"events_contain": "run_completed"},
        {"leaf_count_complete": 6},
        {"subjective": ["reader_warning_appeared_before_failed_ack"]},
    ]
    assert captured["normalized_reader_takeover"]["extras"]["universal_checks"] is True
    assert "universal_checks" not in captured["normalized_reader_takeover"]["assessment"]
    assert captured["normalized_smoke"]["name"] == "_smoke"


def test_runner_main_defaults_to_36_production_scenarios(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.agentic import runner

    captured: dict[str, object] = {}
    parsed_args = argparse.Namespace(
        scenarios=[],
        scenarios_dir="scenarios",
        briefs_dir="briefs",
        reports_dir="reports",
        mode="structural",
        actor="fake",
        tag="default-batch",
        tags=[],
        var=[],
        dry_run=True,
        cross_diff=False,
        parallel=False,
        no_parallel=True,
        capture_interval_sec=0,
        verbose=False,
        reassess=None,
    )

    class FakeParser:
        def parse_args(self, argv: list[str]) -> argparse.Namespace:
            return parsed_args

    def fake_run_from_args(adapter: object, args: argparse.Namespace) -> dict[str, object]:
        temp_dir = Path(args.scenarios_dir)
        captured["normalized_files"] = sorted(path.name for path in temp_dir.glob("*.yaml"))
        captured["briefs_dir"] = args.briefs_dir
        return {"scenario_count": len(captured["normalized_files"]), "scenario_names": []}

    monkeypatch.setattr("sisypy.build_cli_parser", lambda adapter: FakeParser())
    monkeypatch.setattr("sisypy.run_from_args", fake_run_from_args)
    monkeypatch.setattr("sisypy.summary_exit_code", lambda result: 0)

    with pytest.raises(SystemExit) as excinfo:
        runner.main(["--dry-run", "--no-parallel"])

    assert excinfo.value.code == 0
    normalized_files = captured["normalized_files"]
    assert len(normalized_files) == EXPECTED_PRODUCTION_SCENARIOS
    assert "_schema.yaml" not in normalized_files
    assert "_smoke.yaml" not in normalized_files
    assert all(not name.startswith("_") for name in normalized_files)
    assert Path(captured["briefs_dir"]) == runner.BRIEFS_DIR

    discovered_stems = {Path(name).stem for name in normalized_files}
    for name in M4_SCENARIO_NAMES:
        assert name in discovered_stems, f"M4 scenario {name!r} must appear in normalized default output"


def test_runner_main_strips_structural_guard_warning_from_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.agentic import runner

    parsed_args = argparse.Namespace(
        scenarios=["timeline_compose_edit"],
        scenarios_dir="scenarios",
        briefs_dir="briefs",
        reports_dir="reports",
        mode="structural",
        actor="fake",
        tag="m4-structural",
        tags=[],
        var=[],
        dry_run=False,
        cross_diff=False,
        parallel=False,
        no_parallel=True,
        capture_interval_sec=0,
        verbose=False,
        reassess=None,
    )

    class FakeParser:
        def parse_args(self, argv: list[str]) -> argparse.Namespace:
            return parsed_args

    captured: dict[str, object] = {}

    def fake_run_from_args(adapter: object, args: argparse.Namespace) -> dict[str, object]:
        return {
            "scenarios": [
                {
                    "scenario_name": "timeline_compose_edit",
                    "outcome_counts": {"fake_no_op": 1},
                    "runs": [
                        {
                            "outcome": "fake_no_op",
                            "errors": [runner._STRUCTURAL_GUARD_WARNING],
                        }
                    ],
                }
            ],
            "has_blocked_or_error": True,
        }

    def fake_summary_exit_code(result: dict[str, object]) -> int:
        captured["result"] = result
        return 0

    monkeypatch.setattr("sisypy.build_cli_parser", lambda adapter: FakeParser())
    monkeypatch.setattr("sisypy.run_from_args", fake_run_from_args)
    monkeypatch.setattr("sisypy.summary_exit_code", fake_summary_exit_code)

    with pytest.raises(SystemExit) as excinfo:
        runner.main(["timeline_compose_edit", "--actor", "fake", "--mode", "structural"])

    assert excinfo.value.code == 0
    result = captured["result"]
    assert isinstance(result, dict)
    assert result["has_blocked_or_error"] is False
    run = result["scenarios"][0]["runs"][0]
    assert run["errors"] == []
    assert run["warnings"] == [runner._STRUCTURAL_GUARD_WARNING]


def test_m4_scenarios_normalize_with_slug_rendering_and_preserved_extras() -> None:
    """Every M4 scenario loads via discovery, has ${SLUG} in priming,
    and preserves extras.m4_checks / extras.m4_fixture through normalization."""
    import yaml as _yaml

    for name in sorted(M4_SCENARIO_NAMES):
        path = SCENARIOS_DIR / f"{name}.yaml"
        raw = _yaml.safe_load(path.read_text(encoding="utf-8"))

        # -- priming must contain ${SLUG} template ---------------------------
        priming = raw.get("priming")
        assert isinstance(priming, list), f"{name}: priming must be a list"
        slug_priming = [
            item for item in priming
            if isinstance(item, dict) and item.get("create_project") == "${SLUG}"
        ]
        assert len(slug_priming) >= 1, f"{name}: priming must contain create_project: ${{SLUG}}"

        # -- normalize and check extras --------------------------------------
        normalized = normalize_scenario(raw)
        extras = normalized.get("extras") or {}

        m4_checks = extras.get("m4_checks")
        m4_fixture = extras.get("m4_fixture")

        assert isinstance(m4_checks, dict), (
            f"{name}: normalized extras.m4_checks must be a dict, got {type(m4_checks).__name__}"
        )
        assert m4_checks, f"{name}: normalized extras.m4_checks must not be empty"
        assert name in m4_checks, f"{name}: normalized extras.m4_checks must contain key {name!r}"

        assert isinstance(m4_fixture, dict), (
            f"{name}: normalized extras.m4_fixture must be a dict, got {type(m4_fixture).__name__}"
        )
        assert m4_fixture.get("name") == name, (
            f"{name}: normalized extras.m4_fixture.name must be {name!r}"
        )


def test_non_m4_scenario_preserves_m2_checks_through_normalization() -> None:
    """A scenario with extras.m2_checks (e.g. reader_takeover) keeps them after normalize."""
    import yaml as _yaml

    path = SCENARIOS_DIR / "reader_takeover.yaml"
    raw = _yaml.safe_load(path.read_text(encoding="utf-8"))
    normalized = normalize_scenario(raw)

    extras = normalized.get("extras") or {}
    m2_checks = extras.get("m2_checks")
    assert isinstance(m2_checks, dict), (
        f"reader_takeover: normalized extras.m2_checks must be a dict, got {type(m2_checks).__name__}"
    )
    assert "c3_no_mutation_on_read" in m2_checks, (
        "reader_takeover: normalized extras.m2_checks must contain c3_no_mutation_on_read"
    )


def test_m5_scenarios_preserve_m5_checks_through_normalization() -> None:
    """Every M5 scenario keeps extras.m5_checks intact after normalize."""
    import yaml as _yaml

    for name in sorted(M5_SCENARIO_NAMES):
        path = SCENARIOS_DIR / f"{name}.yaml"
        raw = _yaml.safe_load(path.read_text(encoding="utf-8"))
        normalized = normalize_scenario(raw)

        extras = normalized.get("extras") or {}
        m5_checks = extras.get("m5_checks")
        assert isinstance(m5_checks, dict), (
            f"{name}: normalized extras.m5_checks must be a dict, got {type(m5_checks).__name__}"
        )
        assert m5_checks, f"{name}: normalized extras.m5_checks must not be empty"
