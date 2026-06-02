"""Smoke tests for Fix A post-actor enforcement helpers.

Tests the enforcement functions preserved from decommissioned legacy modules:
  - _check_canonical_bypass
  - _reprompt_actor  (not tested in smoke — requires a live agent)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.agentic.enforcement import _check_canonical_bypass


# ---------------------------------------------------------------------------
# _check_canonical_bypass
# ---------------------------------------------------------------------------


def test_check_canonical_bypass_no_false_positive_on_read(tmp_path: Path) -> None:
    """File-read mentions ('📖 read ./astrid/packs/video_editing/orchestrators/hype/run.py')
    must NOT trigger bypass detection.  Only execution-context patterns
    (python/python3 prefix + module or path) should match."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text(
        "📖 read ./astrid/packs/video_editing/orchestrators/hype/run.py\n"
        "Checked astrid/packs/video_editing/orchestrators/hype/orchestrator.yaml\n"
        "Looking at astrid.packs.video_editing.orchestrators.hype.run module docs\n"
    )
    assert _check_canonical_bypass(stderr, scenario_cfg=None) is None


def test_check_canonical_bypass_detects_execution_python3_m(tmp_path: Path) -> None:
    """Direct 'python3 -m astrid.packs.video_editing.orchestrators.hype.run' must trigger."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text(
        "Starting...\n"
        "python3 -m astrid.packs.video_editing.orchestrators.hype.run --some-flag\n"
        "Done.\n"
    )
    result = _check_canonical_bypass(stderr, scenario_cfg=None)
    assert result is not None
    assert "python3 -m astrid.packs.video_editing.orchestrators.hype.run" in result


def test_check_canonical_bypass_detects_execution_python_path(tmp_path: Path) -> None:
    """'python /path/to/astrid/packs/video_editing/orchestrators/hype/run.py' must trigger."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text(
        "python /home/user/astrid/packs/video_editing/orchestrators/hype/run.py --verbose\n"
    )
    result = _check_canonical_bypass(stderr, scenario_cfg=None)
    assert result is not None
    assert "python /home/user/astrid/packs/video_editing/orchestrators/hype/run.py" in result


def test_check_canonical_bypass_detects_execution_python3_space(tmp_path: Path) -> None:
    """'python3  ./astrid/packs/video_editing/orchestrators/hype/run.py' must trigger
    (path with leading ./ still matches /astrid/packs/ pattern)."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text(
        "python3  ./astrid/packs/video_editing/orchestrators/hype/run.py\n"
    )
    result = _check_canonical_bypass(stderr, scenario_cfg=None)
    assert result is not None
    assert "python3" in result


def test_check_canonical_bypass_no_filter_on_launcher(tmp_path: Path) -> None:
    """The hermes launcher itself uses python3 — but with
    launch_hermes_agent.py (not astrid/packs/...), so it must NOT trigger."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text(
        "python3 launch_hermes_agent.py --model=deepseek:deepseek-v4-pro\n"
    )
    assert _check_canonical_bypass(stderr, scenario_cfg=None) is None


def test_check_canonical_bypass_no_filter_on_plain_python(tmp_path: Path) -> None:
    """'python3 script.py' without astrid.packs must NOT trigger."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text("python3 my_script.py --help\n")
    assert _check_canonical_bypass(stderr, scenario_cfg=None) is None


def test_check_canonical_bypass_from_offset_skips_old_content(tmp_path: Path) -> None:
    """Re-check with from_offset past an old bypass + marker line
    must return None (only new content is scanned)."""
    stderr = tmp_path / "stderr.log"
    old_content = "python3 -m astrid.packs.video_editing.orchestrators.hype.run\n"
    marker = "--- REPROMPT: canonical CLI bypass detected ---\n"
    new_content = "astrid author run hype --check\n"  # canonical, no bypass
    stderr.write_text(old_content + marker + new_content)

    # from_offset past old_content + marker
    offset = len(old_content.encode("utf-8")) + len(marker.encode("utf-8"))
    result = _check_canonical_bypass(stderr, scenario_cfg=None, from_offset=offset)
    assert result is None


def test_check_canonical_bypass_from_offset_zero_finds_bypass(tmp_path: Path) -> None:
    """With from_offset=0, old bypass is scanned and detected."""
    stderr = tmp_path / "stderr.log"
    old_content = "python3 -m astrid.packs.video_editing.orchestrators.hype.run\n"
    marker = "--- REPROMPT: canonical CLI bypass detected ---\n"
    new_content = "astrid author run hype --check\n"
    stderr.write_text(old_content + marker + new_content)

    result = _check_canonical_bypass(stderr, scenario_cfg=None, from_offset=0)
    assert result is not None
    assert "python3 -m astrid.packs.video_editing" in result


def test_check_canonical_bypass_bypass_exempt(tmp_path: Path) -> None:
    """Scenario with bypass_exempt: true returns None regardless."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text("python3 -m astrid.packs.video_editing.orchestrators.hype.run\n")

    scenario_cfg = {"assessment": {"bypass_exempt": True}}
    assert _check_canonical_bypass(stderr, scenario_cfg=scenario_cfg) is None


def test_check_canonical_bypass_missing_file(tmp_path: Path) -> None:
    """Non-existent stderr returns None."""
    assert _check_canonical_bypass(tmp_path / "nope.log", scenario_cfg=None) is None


def test_check_canonical_bypass_empty_file(tmp_path: Path) -> None:
    """Empty stderr returns None."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text("")
    assert _check_canonical_bypass(stderr, scenario_cfg=None) is None


# ---------------------------------------------------------------------------
# T3: Compatibility tests — dual-format placeholder substitution and
#     extras fallback paths added in T1/T2.
# ---------------------------------------------------------------------------


# --- _render_brief (preserved in enforcement.py) -----------------------


def test_render_brief_sisypy_style_substitutes_all_vars(tmp_path: Path) -> None:
    """_render_brief must replace ${SLUG}, ${AGENT_ID}, ${RUN_TAG},
    ${TARGET_ORCH} when the template uses Sisypy-style placeholders."""
    from tests.agentic.enforcement import _render_brief

    brief = tmp_path / "brief.md"
    brief.write_text("Project: ${SLUG} / Agent: ${AGENT_ID} / Run: ${RUN_TAG} / Orch: ${TARGET_ORCH}")
    result = _render_brief(brief, slug="my-slug", agent_id="agent-1",
                           run_tag="20250101", target_orchestrator="builtin.test")
    assert "my-slug" in result
    assert "agent-1" in result
    assert "20250101" in result
    assert "builtin.test" in result
    assert "${SLUG}" not in result
    assert "${AGENT_ID}" not in result
    assert "${RUN_TAG}" not in result
    assert "${TARGET_ORCH}" not in result


def test_render_brief_legacy_style_substitutes_all_vars(tmp_path: Path) -> None:
    """_render_brief must still replace legacy $SLUG, $AGENT_ID, $RUN_TAG,
    $TARGET_ORCH for backward compatibility."""
    from tests.agentic.enforcement import _render_brief

    brief = tmp_path / "brief.md"
    brief.write_text("Project: $SLUG / Agent: $AGENT_ID / Run: $RUN_TAG / Orch: $TARGET_ORCH")
    result = _render_brief(brief, slug="my-slug", agent_id="agent-1",
                           run_tag="20250101", target_orchestrator="builtin.test")
    assert "my-slug" in result
    assert "agent-1" in result
    assert "20250101" in result
    assert "builtin.test" in result
    assert "$SLUG" not in result
    assert "$AGENT_ID" not in result
    assert "$RUN_TAG" not in result
    assert "$TARGET_ORCH" not in result


def test_render_brief_sisypy_not_corrupted_by_legacy_substitution(tmp_path: Path) -> None:
    """Sisypy-style ${VAR} tokens must NOT be corrupted by the legacy $VAR
    pass.  Since ${VAR} is replaced first, a template that uses both
    styles must produce fully-rendered output with no stray $ or {}
    fragments."""
    from tests.agentic.enforcement import _render_brief

    brief = tmp_path / "brief.md"
    # Mix both styles — the Sisypy pass must consume ${SLUG} before
    # the legacy pass sees the raw $ character.
    brief.write_text("A: ${SLUG}  B: $SLUG  C: ${AGENT_ID}  D: $RUN_TAG")
    result = _render_brief(brief, slug="s", agent_id="a",
                           run_tag="r", target_orchestrator="t")
    # All tokens gone.
    assert "${" not in result, f"stray ${{ in: {result!r}"
    assert "$SLUG" not in result
    assert "$RUN_TAG" not in result
    # All values present.
    assert "A: s" in result
    assert "B: s" in result
    assert "C: a" in result
    assert "D: r" in result


def test_render_brief_partial_string_substitution(tmp_path: Path) -> None:
    """Placeholders embedded in longer strings (e.g. 'agentic-${SLUG}-${AGENT_ID}')
    must be replaced in-place without disturbing surrounding text."""
    from tests.agentic.enforcement import _render_brief

    brief = tmp_path / "brief.md"
    brief.write_text("attach agentic-${SLUG}-${AGENT_ID} --tag ${RUN_TAG}")
    result = _render_brief(brief, slug="proj", agent_id="a1",
                           run_tag="t1", target_orchestrator="orch")
    assert "agentic-proj-a1" in result
    assert "--tag t1" in result


def test_render_brief_none_target_orchestrator_defaults_placeholder(tmp_path: Path) -> None:
    """When target_orchestrator is None, the placeholder must render as
    '<not-specified>'."""
    from tests.agentic.enforcement import _render_brief

    brief = tmp_path / "brief.md"
    brief.write_text("Orch: ${TARGET_ORCH}")
    result = _render_brief(brief, slug="s", agent_id="a",
                           run_tag="r", target_orchestrator=None)
    assert "<not-specified>" in result


# --- _load_scenario (preserved in enforcement.py) ----------------------


def test_load_scenario_promotes_extras_target_orchestrator(tmp_path: Path) -> None:
    """When a scenario YAML carries target_orchestrator ONLY in
    ``extras``, _load_scenario must promote it to top-level."""
    import yaml

    from tests.agentic.enforcement import _load_scenario, SCENARIOS_DIR

    # Write a temporary scenario that exercises the fallback path.
    name = "_t3_test_load_scenario_extras_orch"
    path = SCENARIOS_DIR / f"{name}.yaml"
    try:
        path.write_text(yaml.dump({
            "name": name,
            "tier": "discovery",
            "description": "T3 compat test",
            "brief": "reader_takeover.md",
            "agents": [{"model": "deepseek-v4-pro", "count": 1}],
            "acceptance": [{"events_contain": "run_completed"}],
            "extras": {
                "target_orchestrator": "builtin.fake_orch",
                "project_slug": "t3-test",
            },
        }))
        scenario = _load_scenario(name)
        assert scenario["target_orchestrator"] == "builtin.fake_orch", (
            f"expected promotion, got {scenario.get('target_orchestrator')!r}"
        )
    finally:
        path.unlink(missing_ok=True)


def test_load_scenario_does_not_overwrite_existing_top_level_orch(tmp_path: Path) -> None:
    """When target_orchestrator is already at top-level, _load_scenario
    must NOT overwrite it with the extras value."""
    import yaml

    from tests.agentic.enforcement import _load_scenario, SCENARIOS_DIR

    name = "_t3_test_load_scenario_existing_orch"
    path = SCENARIOS_DIR / f"{name}.yaml"
    try:
        path.write_text(yaml.dump({
            "name": name,
            "tier": "discovery",
            "description": "T3 compat test — existing top-level orch",
            "brief": "reader_takeover.md",
            "agents": [{"model": "deepseek-v4-pro", "count": 1}],
            "acceptance": [{"events_contain": "run_completed"}],
            "target_orchestrator": "builtin.top_level_orch",
            "extras": {
                "target_orchestrator": "builtin.should_not_win",
                "project_slug": "t3-test",
            },
        }))
        scenario = _load_scenario(name)
        assert scenario["target_orchestrator"] == "builtin.top_level_orch", (
            f"expected top-level to win, got {scenario.get('target_orchestrator')!r}"
        )
    finally:
        path.unlink(missing_ok=True)


# --- canonical_path_bypass (universal_checks.py) -----------------------


def test_canonical_path_bypass_finds_has_canonical_in_extras(tmp_path: Path) -> None:
    """canonical_path_bypass must treat ``extras.target_orchestrator``
    (Sisypy compat) as declaring a canonical surface, triggering bypass
    detection when a bypass pattern is present."""
    from tests.agentic.enforcement import canonical_path_bypass

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    stderr = evidence / "stderr.log"
    stderr.write_text("python3 -m astrid.packs.video_editing.orchestrators.hype.run\n")

    # target_orchestrator ONLY in extras — top-level absent.
    scenario_cfg = {
        "extras": {"target_orchestrator": "video_editing.hype"},
    }
    assert canonical_path_bypass(evidence, scenario_cfg) is True, (
        "bypass must be detected when extras.target_orchestrator declares a canonical surface"
    )


def test_canonical_path_bypass_finds_has_canonical_in_extras_executor(tmp_path: Path) -> None:
    """Same as above but via ``extras.target_executor``."""
    from tests.agentic.enforcement import canonical_path_bypass

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    stderr = evidence / "stderr.log"
    stderr.write_text("python3 -m astrid.packs.editorial.executors.transcribe.run\n")

    scenario_cfg = {
        "extras": {"target_executor": "editorial.transcribe"},
    }
    assert canonical_path_bypass(evidence, scenario_cfg) is True, (
        "bypass must be detected when extras.target_executor declares a canonical surface"
    )


def test_canonical_path_bypass_no_bypass_when_no_has_canonical_at_all(tmp_path: Path) -> None:
    """When neither top-level nor extras declares target_orchestrator or
    target_executor, has_canonical must be False and bypass must not fire."""
    from tests.agentic.enforcement import canonical_path_bypass

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    stderr = evidence / "stderr.log"
    stderr.write_text("python3 -m astrid.packs.foo.bar\n")

    scenario_cfg: dict = {}
    assert canonical_path_bypass(evidence, scenario_cfg) is False, (
        "bypass must NOT fire when no canonical surface is declared"
    )


def test_canonical_path_bypass_bypass_exempt_in_assessment(tmp_path: Path) -> None:
    """When assessment.bypass_exempt is True, bypass must not fire even
    with extras.target_orchestrator present."""
    from tests.agentic.enforcement import canonical_path_bypass

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    stderr = evidence / "stderr.log"
    stderr.write_text("python3 -m astrid.packs.foo.bar\n")

    scenario_cfg = {
        "extras": {"target_orchestrator": "foo.bar"},
        "assessment": {"bypass_exempt": True},
    }
    assert canonical_path_bypass(evidence, scenario_cfg) is False, (
        "bypass_exempt must prevent bypass detection"
    )


# --- _validate_rubrics — extras.legacy_acceptance fallback -------------


def test_validate_rubrics_extract_subjective_keys_falls_back_to_extras(tmp_path: Path) -> None:
    """_extract_subjective_keys must read ``extras.legacy_acceptance``
    when the top-level ``acceptance`` key is absent."""
    import yaml

    from tests.agentic._validate_rubrics import SCENARIOS_DIR, validate_one

    name = "_t3_test_validate_extras_acceptance"
    path = SCENARIOS_DIR / f"{name}.yaml"
    try:
        path.write_text(yaml.dump({
            "name": name,
            "tier": "discovery",
            "description": "T3 compat — extras.legacy_acceptance",
            "brief": "reader_takeover.md",
            "agents": [{"model": "deepseek-v4-pro", "count": 1}],
            "assessment": {
                "universal_checks": True,
                "rubric": [
                    {"id": "canonical_cli_used", "question": "Was the canonical CLI used?",
                     "failure_mode": "Agent bypassed CLI by directly invoking the executor."},
                    {"id": "no_bypass_confirmed", "question": "Did the agent avoid bypass?",
                     "failure_mode": "Agent used python -m astrid.packs..."},
                    {"id": "events_show_run", "question": "Do events show a run?",
                     "failure_mode": "No run events found."},
                    {"id": "report_complete", "question": "Is the report complete?",
                     "failure_mode": "Report missing sections."},
                    {"id": "no_errors", "question": "Are there errors?",
                     "failure_mode": "Errors found in stderr."},
                ],
            },
            "extras": {
                "target_orchestrator": "builtin.fake",
                "project_slug": "t3-test",
                "legacy_acceptance": [
                    {"subjective": ["canonical_cli_used"]},
                    {"subjective": ["no_bypass_confirmed"]},
                ],
            },
        }))
        errors = validate_one(path)
        # The rubric covers both subjective keys → no errors expected.
        assert errors == [], f"expected no errors, got {errors}"
    finally:
        path.unlink(missing_ok=True)


def test_validate_rubrics_warns_on_missing_assessment_block(tmp_path: Path) -> None:
    """When a scenario has acceptance criteria (via extras.legacy_acceptance)
    but no ``assessment`` block, validate_one must warn (print to stderr)
    rather than error out."""
    import yaml

    from tests.agentic._validate_rubrics import SCENARIOS_DIR, validate_one

    name = "_t3_test_validate_no_assessment"
    path = SCENARIOS_DIR / f"{name}.yaml"
    try:
        path.write_text(yaml.dump({
            "name": name,
            "tier": "discovery",
            "description": "T3 compat — no assessment block",
            "brief": "reader_takeover.md",
            "agents": [{"model": "deepseek-v4-pro", "count": 1}],
            "extras": {
                "target_orchestrator": "builtin.fake",
                "project_slug": "t3-test",
                "legacy_acceptance": [
                    {"subjective": ["some_concern"]},
                ],
            },
        }))
        errors = validate_one(path)
        # Must not error — just warn.
        assert errors == [], f"expected no errors when assessment block missing, got {errors}"
    finally:
        path.unlink(missing_ok=True)


def test_validate_rubrics_skips_scenario_with_no_criteria(tmp_path: Path) -> None:
    """When a scenario has neither ``acceptance`` nor
    ``extras.legacy_acceptance``, validate_one must return an empty
    list (skip — not an error)."""
    import yaml

    from tests.agentic._validate_rubrics import SCENARIOS_DIR, validate_one

    name = "_t3_test_validate_no_criteria"
    path = SCENARIOS_DIR / f"{name}.yaml"
    try:
        path.write_text(yaml.dump({
            "name": name,
            "tier": "discovery",
            "description": "T3 compat — no criteria at all",
            "brief": "reader_takeover.md",
            "agents": [{"model": "deepseek-v4-pro", "count": 1}],
        }))
        errors = validate_one(path)
        assert errors == [], f"expected skip (empty errors), got {errors}"
    finally:
        path.unlink(missing_ok=True)

