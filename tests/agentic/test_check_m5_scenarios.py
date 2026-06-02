from __future__ import annotations

import json
from pathlib import Path

import yaml

from tests.agentic.checks.m5_scenarios import (
    M5_CHECK_SPECS,
    author_run_revise_loop,
    broken_authoring_fix_loop,
    cross_pack_authoring_discovery,
    no_fabricated_tool_id,
    projects_runs_sessions_discovered,
    resolve_m5_check_records,
    search_fallback_after_zero_hits,
)
from tests.agentic.normalize import normalize_scenario


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_m5_check_specs_are_stable_and_unique() -> None:
    stable_ids = [stable_id for stable_id, _trigger_key, _fn_name in M5_CHECK_SPECS]
    trigger_keys = [trigger_key for _stable_id, trigger_key, _fn_name in M5_CHECK_SPECS]
    function_names = [fn_name for _stable_id, _trigger_key, fn_name in M5_CHECK_SPECS]

    assert len(M5_CHECK_SPECS) == 6
    assert len(set(stable_ids)) == len(stable_ids)
    assert len(set(trigger_keys)) == len(trigger_keys)
    assert len(set(function_names)) == len(function_names)


def test_m5_trigger_resolution_prefers_scenario_extras_over_manifest() -> None:
    records = resolve_m5_check_records(
        scenario_extras={
            "m5_checks": {
                "no_fabricated_tool_id": {"enabled": True, "note": "extras"},
            }
        },
        manifest={
            "m5_checks": {
                "no_fabricated_tool_id": {"enabled": False},
                "broken_authoring_fix_loop": {"enabled": True},
            }
        },
    )

    target = records["m5.no_tool_exists_pushback.no_fabricated_tool_id"]
    assert target.enabled is True
    assert target.source == "scenario_extras"
    assert target.config == {"enabled": True, "note": "extras"}

    missing = records["m5.broken_authoring_fix.broken_authoring_fix_loop"]
    assert missing.enabled is False
    assert missing.source == "absent"


def test_m5_trigger_resolution_falls_back_to_manifest_when_extras_missing() -> None:
    records = resolve_m5_check_records(
        scenario_extras={"project_slug": "m5-only"},
        manifest={
            "m5_checks": {
                "projects_runs_sessions_discovered": {"enabled": True, "mode": "frozen"},
            }
        },
    )

    target = records["m5.discover_projects_runs_sessions.projects_runs_sessions_discovered"]
    assert target.enabled is True
    assert target.source == "manifest"
    assert target.config == {"enabled": True, "mode": "frozen"}


def test_absent_m5_trigger_returns_na(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "m5-na"
    evidence_dir.mkdir()
    records = resolve_m5_check_records()
    check_fns = {
        "m5.no_tool_exists_pushback.no_fabricated_tool_id": no_fabricated_tool_id,
        "m5.recover_from_no_search_results.search_fallback_after_zero_hits": (
            search_fallback_after_zero_hits
        ),
        "m5.discover_projects_runs_sessions.projects_runs_sessions_discovered": (
            projects_runs_sessions_discovered
        ),
        "m5.broken_authoring_fix.broken_authoring_fix_loop": broken_authoring_fix_loop,
        "m5.cross_pack_authoring.cross_pack_authoring_discovery": (
            cross_pack_authoring_discovery
        ),
        "m5.author_run_revise_loop.author_run_revise_loop": author_run_revise_loop,
    }

    for stable_id, trigger_key, _fn_name in M5_CHECK_SPECS:
        result = check_fns[stable_id](
            evidence_dir,
            trigger_record=records[stable_id],
        )

        assert result == {
            "id": stable_id,
            "status": "na",
            "evidence_refs": [],
            "detail": {
                "reason": "trigger not declared",
                "trigger_key": trigger_key,
            },
        }


def test_each_m5_check_returns_pass_for_matching_evidence(tmp_path: Path) -> None:
    cases = [
        (
            "m5.no_tool_exists_pushback.no_fabricated_tool_id",
            "no_fabricated_tool_id",
            no_fabricated_tool_id,
            lambda root: (
                _write_text(
                    root / "stderr.log",
                    "\n".join(
                        [
                            "$ astrid executors search music clearance",
                            "$ astrid orchestrators search sync licensing",
                        ]
                    ),
                ),
                _write_text(
                    root / "report.md",
                    "No matching tool exists in the Astrid registry. Nothing found after both searches.\n",
                ),
            ),
        ),
        (
            "m5.recover_from_no_search_results.search_fallback_after_zero_hits",
            "search_fallback_after_zero_hits",
            search_fallback_after_zero_hits,
            lambda root: _write_text(
                root / "stderr.log",
                "\n".join(
                    [
                        "$ astrid executors search batch-retime tempo map",
                        "0 results",
                        "$ astrid executors list",
                        "$ astrid executors search retime duration",
                    ]
                ),
            ),
        ),
        (
            "m5.discover_projects_runs_sessions.projects_runs_sessions_discovered",
            "projects_runs_sessions_discovered",
            projects_runs_sessions_discovered,
            lambda root: _write_text(
                root / "stderr.log",
                "\n".join(
                    [
                        "$ astrid projects ls",
                        "$ astrid runs ls",
                        "$ astrid sessions ls",
                        "$ astrid orchestrators list",
                    ]
                ),
            ),
        ),
        (
            "m5.broken_authoring_fix.broken_authoring_fix_loop",
            "broken_authoring_fix_loop",
            broken_authoring_fix_loop,
            lambda root: _write_text(
                root / "stderr.log",
                "\n".join(
                    [
                        "$ astrid author check video_editing.hype",
                        "SyntaxError: unexpected indent",
                        "exit 1",
                        "$ astrid author check video_editing.hype",
                        "success",
                        "exit 0",
                    ]
                ),
            ),
        ),
        (
            "m5.cross_pack_authoring.cross_pack_authoring_discovery",
            "cross_pack_authoring_discovery",
            cross_pack_authoring_discovery,
            lambda root: (
                _write_text(
                    root / "stderr.log",
                    "\n".join(
                        [
                            "$ astrid executors search editorial transcribe",
                            "found editorial.transcribe",
                            "$ astrid executors search hype transcript",
                            "found video_editing.hype",
                            "$ astrid author check custom.cross_pack",
                            "success",
                            "exit 0",
                        ]
                    ),
                ),
                _write_text(
                    root / "report.md",
                    "I discovered editorial.transcribe and video_editing.hype before authoring.\n",
                ),
            ),
        ),
        (
            "m5.author_run_revise_loop.author_run_revise_loop",
            "author_run_revise_loop",
            author_run_revise_loop,
            lambda root: (
                _write_text(root / "stderr.log", "$ astrid orchestrators run demo.loop\n"),
                _write_text(root / "report.md", "The rerun was correct.\n"),
                _write_json(
                    root / "m5" / "author_run_revise_loop.json",
                    {
                        "wrong_output_observed": True,
                        "revision_count": 1,
                        "final_success": True,
                    },
                ),
            ),
        ),
    ]

    for stable_id, trigger_key, fn, setup in cases:
        evidence_dir = tmp_path / trigger_key
        setup(evidence_dir)
        records = resolve_m5_check_records(
            scenario_extras={"m5_checks": {trigger_key: {"enabled": True}}}
        )

        result = fn(evidence_dir, trigger_record=records[stable_id])

        assert result["id"] == stable_id
        assert result["status"] == "pass"
        assert result["detail"]["mismatches"] == []


def test_each_m5_check_returns_fail_for_non_matching_evidence(tmp_path: Path) -> None:
    cases = [
        (
            "m5.no_tool_exists_pushback.no_fabricated_tool_id",
            "no_fabricated_tool_id",
            no_fabricated_tool_id,
            lambda root: (
                _write_text(
                    root / "stderr.log",
                    "\n".join(
                        [
                            "$ astrid executors search music clearance",
                            "$ astrid orchestrators run made.up.tool",
                        ]
                    ),
                ),
                _write_text(root / "report.md", "I found something close enough.\n"),
            ),
        ),
        (
            "m5.recover_from_no_search_results.search_fallback_after_zero_hits",
            "search_fallback_after_zero_hits",
            search_fallback_after_zero_hits,
            lambda root: _write_text(
                root / "stderr.log",
                "$ astrid executors search batch-retime tempo map\n",
            ),
        ),
        (
            "m5.discover_projects_runs_sessions.projects_runs_sessions_discovered",
            "projects_runs_sessions_discovered",
            projects_runs_sessions_discovered,
            lambda root: _write_text(
                root / "stderr.log",
                "\n".join(
                    [
                        "$ astrid projects ls",
                        "$ astrid author check demo.loop",
                        "$ astrid runs ls",
                    ]
                ),
            ),
        ),
        (
            "m5.broken_authoring_fix.broken_authoring_fix_loop",
            "broken_authoring_fix_loop",
            broken_authoring_fix_loop,
            lambda root: _write_text(
                root / "stderr.log",
                "\n".join(
                    [
                        "$ astrid author check video_editing.hype",
                        "success",
                        "exit 0",
                    ]
                ),
            ),
        ),
        (
            "m5.cross_pack_authoring.cross_pack_authoring_discovery",
            "cross_pack_authoring_discovery",
            cross_pack_authoring_discovery,
            lambda root: (
                _write_text(
                    root / "stderr.log",
                    "\n".join(
                        [
                            "$ astrid executors search editorial transcribe",
                            "$ astrid author check custom.cross_pack",
                            "success",
                            "exit 0",
                        ]
                    ),
                ),
                _write_text(root / "report.md", "Only editorial was mentioned.\n"),
            ),
        ),
        (
            "m5.author_run_revise_loop.author_run_revise_loop",
            "author_run_revise_loop",
            author_run_revise_loop,
            lambda root: (
                _write_text(
                    root / "stderr.log",
                    "\n".join(
                        [
                            "$ astrid orchestrators run demo.loop",
                            "output was wrong",
                            "$ astrid orchestrators run demo.loop",
                        ]
                    ),
                ),
                _write_text(root / "report.md", "Still wrong on the rerun.\n"),
            ),
        ),
    ]

    for stable_id, trigger_key, fn, setup in cases:
        evidence_dir = tmp_path / f"{trigger_key}-fail"
        setup(evidence_dir)
        records = resolve_m5_check_records(
            scenario_extras={"m5_checks": {trigger_key: {"enabled": True}}}
        )

        result = fn(evidence_dir, trigger_record=records[stable_id])

        assert result["id"] == stable_id
        assert result["status"] == "fail"
        assert result["detail"]["mismatches"]


def test_author_run_revise_loop_text_fallback_passes_without_diagnostic(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "fallback"
    _write_text(
        evidence_dir / "stderr.log",
        "\n".join(
            [
                "$ astrid orchestrators run demo.loop",
                "wrong output: expected 60, got 30",
                "$ astrid author check demo.loop",
                "success",
                "exit 0",
                "$ astrid orchestrators run demo.loop",
            ]
        ),
    )
    _write_text(
        evidence_dir / "report.md",
        "The first run was incorrect, then I fixed the DSL and the rerun produced 60.\n",
    )
    records = resolve_m5_check_records(
        scenario_extras={"m5_checks": {"author_run_revise_loop": {"enabled": True}}}
    )

    result = author_run_revise_loop(
        evidence_dir,
        trigger_record=records["m5.author_run_revise_loop.author_run_revise_loop"],
    )

    assert result["status"] == "pass"
    assert result["detail"]["mode"] == "text_fallback"


def test_m5_scenarios_preserve_m5_checks_through_normalization() -> None:
    scenarios_dir = Path("tests/agentic/scenarios")

    for name in (
        "cross_pack_authoring",
        "broken_authoring_fix",
        "no_tool_exists_pushback",
        "discover_projects_runs_sessions",
        "author_run_revise_loop",
        "recover_from_no_search_results",
    ):
        raw = yaml.safe_load((scenarios_dir / f"{name}.yaml").read_text(encoding="utf-8"))
        normalized = normalize_scenario(raw)
        extras = normalized.get("extras") or {}
        m5_checks = extras.get("m5_checks")

        assert isinstance(m5_checks, dict), (
            f"{name}: normalized extras.m5_checks must be a dict, got {type(m5_checks).__name__}"
        )
        assert m5_checks, f"{name}: normalized extras.m5_checks must not be empty"
