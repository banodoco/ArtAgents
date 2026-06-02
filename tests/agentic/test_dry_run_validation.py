"""pytest tests for validate_scenario_dry_run.

Covers canonical success, token replacement, unexpanded-token failure,
and malformed-scenario failure. All tests monkeypatch runner.SCENARIOS_DIR
and runner.BRIEFS_DIR to temp directories via a shared fixture.
"""

from __future__ import annotations

import pytest
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Shared fixture: temporary scenario + brief directories
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Create temp SCENARIOS_DIR and BRIEFS_DIR, monkeypatch runner globals."""
    scn_dir = tmp_path / "scenarios"
    brf_dir = tmp_path / "briefs"
    scn_dir.mkdir()
    brf_dir.mkdir()

    import tests.agentic.runner as runner

    monkeypatch.setattr(runner, "SCENARIOS_DIR", scn_dir)
    monkeypatch.setattr(runner, "BRIEFS_DIR", brf_dir)
    return scn_dir, brf_dir


# ---------------------------------------------------------------------------
# Helper: write a scenario YAML
# ---------------------------------------------------------------------------

def _write_scenario(path: Path, scenario: dict) -> None:
    path.write_text(yaml.dump(scenario), encoding="utf-8")


def _write_brief(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Minimal valid scenario dict
# ---------------------------------------------------------------------------

_VALID_SCENARIO = {
    "name": "canonical_dry_run",
    "tier": "dry_run",
    "description": "Canonical dry-run test.",
    "brief": "canonical.md",
    "agents": [{"model": "deepseek-v4-pro", "count": 1}],
    "acceptance": ["no_aborts"],
}


# ===================================================================
# Canonical success
# ===================================================================

def test_canonical_success(temp_dirs: tuple[Path, Path]) -> None:
    """validate_scenario_dry_run with a fully valid scenario + brief."""
    scn_dir, brf_dir = temp_dirs

    _write_scenario(scn_dir / "canonical_dry_run.yaml", _VALID_SCENARIO)
    _write_brief(
        brf_dir / "canonical.md",
        "You are $AGENT_ID working in project $SLUG (run $RUN_TAG).\n"
        "Use orchestrator $TARGET_ORCH.\n",
    )

    import tests.agentic.runner as runner

    result = runner.validate_scenario_dry_run("canonical_dry_run", run_tag="test")

    assert result["ok"] is True
    assert result["errors"] == []
    assert result["warnings"] == []
    assert len(result["invocations"]) == 1
    inv = result["invocations"][0]
    assert inv["index"] == 1
    assert inv["model"] == "deepseek-v4-pro"
    assert inv["slug"].startswith("agentic-canonical-dry-run-ds-")
    assert inv["agent_id"].startswith("agentic-canonical_dry_run-ds-")
    assert inv["unresolved_tokens"] == []


# ===================================================================
# Token replacement — known tokens
# ===================================================================

def test_token_replacement(temp_dirs: tuple[Path, Path]) -> None:
    """Known tokens $SLUG/$AGENT_ID/$RUN_TAG/$TARGET_ORCH are substituted."""
    scn_dir, brf_dir = temp_dirs

    _write_scenario(scn_dir / "canonical_dry_run.yaml", _VALID_SCENARIO)
    _write_brief(
        brf_dir / "canonical.md",
        "SLUG=$SLUG AGENT=$AGENT_ID RUN=$RUN_TAG ORCH=$TARGET_ORCH\n",
    )

    import tests.agentic.runner as runner

    result = runner.validate_scenario_dry_run(
        "canonical_dry_run", run_tag="test", report_dir=brf_dir
    )

    assert result["ok"] is True
    # Read the rendered brief from the temp dir and verify tokens are gone.
    inv = result["invocations"][0]
    brief_file = brf_dir / f"{inv['slug']}.brief.md"
    rendered = brief_file.read_text(encoding="utf-8")

    for token in ("$SLUG", "$AGENT_ID", "$RUN_TAG", "$TARGET_ORCH"):
        assert token not in rendered, f"{token!r} appears in rendered brief"


# ===================================================================
# Unexpanded-token failure
# ===================================================================

def test_unexpanded_token_failure(temp_dirs: tuple[Path, Path]) -> None:
    """$UNKNOWN_TOKEN and $ANOTHER_MISSING are detected as unresolved."""
    scn_dir, brf_dir = temp_dirs

    _write_scenario(scn_dir / "canonical_dry_run.yaml", _VALID_SCENARIO)
    _write_brief(
        brf_dir / "canonical.md",
        "Use $UNKNOWN_TOKEN and also $ANOTHER_MISSING. SLUG=$SLUG.\n",
    )

    import tests.agentic.runner as runner

    result = runner.validate_scenario_dry_run("canonical_dry_run", run_tag="test")

    # ok is False because unresolved tokens are errors.
    assert result["ok"] is False
    assert len(result["errors"]) >= 1
    # The global error list includes the unresolved-tokens error.
    combined = " ".join(result["errors"])
    assert "$UNKNOWN_TOKEN" in combined
    assert "$ANOTHER_MISSING" in combined

    # Per-invocation unresolved list.
    inv = result["invocations"][0]
    unresolved = set(inv["unresolved_tokens"])
    assert "$UNKNOWN_TOKEN" in unresolved
    assert "$ANOTHER_MISSING" in unresolved
    # Known tokens are not reported.
    assert "$SLUG" not in unresolved

    # Warnings list also flags them.
    combined_warnings = " ".join(result["warnings"])
    assert "$UNKNOWN_TOKEN" in combined_warnings
    assert "$ANOTHER_MISSING" in combined_warnings


# ===================================================================
# Malformed-scenario failures
# ===================================================================

def test_missing_required_fields(temp_dirs: tuple[Path, Path]) -> None:
    """Scenario missing 'name' and 'agents' produces ok=false."""
    scn_dir, brf_dir = temp_dirs

    bad = {
        "tier": "dry_run",
        "description": "Missing name and agents.",
        "brief": "canonical.md",
        "acceptance": [],
    }
    _write_scenario(scn_dir / "missing_fields.yaml", bad)
    _write_brief(brf_dir / "canonical.md", "Hello $SLUG\n")

    import tests.agentic.runner as runner

    result = runner.validate_scenario_dry_run("missing_fields", run_tag="test")

    assert result["ok"] is False
    combined = " ".join(result["errors"])
    assert "missing required keys" in combined
    assert "name" in combined
    assert "agents" in combined


def test_name_field_mismatch(temp_dirs: tuple[Path, Path]) -> None:
    """Scenario file name differs from its `name` field."""
    scn_dir, brf_dir = temp_dirs

    bad = dict(_VALID_SCENARIO)
    bad["name"] = "different_name"
    _write_scenario(scn_dir / "canonical_dry_run.yaml", bad)
    _write_brief(brf_dir / "canonical.md", "Hello $SLUG\n")

    import tests.agentic.runner as runner

    result = runner.validate_scenario_dry_run("canonical_dry_run", run_tag="test")

    assert result["ok"] is False
    # _load_scenario raises ValueError before validate_scenario_dry_run appends
    # its own "name-field mismatch" string, so we check for either phrasing.
    assert any(
        "name-field mismatch" in e or "name` field is" in e
        for e in result["errors"]
    )


def test_non_mapping_yaml(temp_dirs: tuple[Path, Path]) -> None:
    """Non-mapping top-level YAML produces ok=false."""
    scn_dir, brf_dir = temp_dirs

    (scn_dir / "list_scenario.yaml").write_text(
        "- not: a mapping\n", encoding="utf-8"
    )

    import tests.agentic.runner as runner

    result = runner.validate_scenario_dry_run("list_scenario", run_tag="test")

    assert result["ok"] is False
    assert any("must be a mapping" in e for e in result["errors"])


def test_empty_agents(temp_dirs: tuple[Path, Path]) -> None:
    """Scenario with empty agents list returns ok=false."""
    scn_dir, brf_dir = temp_dirs

    bad = dict(_VALID_SCENARIO)
    bad["agents"] = []
    _write_scenario(scn_dir / "canonical_dry_run.yaml", bad)
    _write_brief(brf_dir / "canonical.md", "Hello $SLUG\n")

    import tests.agentic.runner as runner

    result = runner.validate_scenario_dry_run("canonical_dry_run", run_tag="test")

    assert result["ok"] is False
    assert any("agents must be a non-empty list" in e for e in result["errors"])


def test_missing_brief_template(temp_dirs: tuple[Path, Path]) -> None:
    """Scenario references a brief that does not exist on disk."""
    scn_dir, brf_dir = temp_dirs

    bad = dict(_VALID_SCENARIO)
    bad["brief"] = "nonexistent.md"
    _write_scenario(scn_dir / "canonical_dry_run.yaml", bad)

    import tests.agentic.runner as runner

    result = runner.validate_scenario_dry_run("canonical_dry_run", run_tag="test")

    assert result["ok"] is False
    assert any("brief template not found" in e for e in result["errors"])


def test_missing_name_alone(temp_dirs: tuple[Path, Path]) -> None:
    """Scenario missing only 'name' field is caught."""
    scn_dir, brf_dir = temp_dirs

    bad = {
        "tier": "dry_run",
        "description": "No name.",
        "brief": "canonical.md",
        "agents": [{"model": "deepseek-v4-pro"}],
        "acceptance": [],
    }
    _write_scenario(scn_dir / "noname.yaml", bad)
    _write_brief(brf_dir / "canonical.md", "Hello\n")

    import tests.agentic.runner as runner

    result = runner.validate_scenario_dry_run("noname", run_tag="test")

    assert result["ok"] is False
    assert any("missing required keys" in e for e in result["errors"])
    assert any("name" in e for e in result["errors"])


def test_missing_acceptance_alone(temp_dirs: tuple[Path, Path]) -> None:
    """Scenario missing only 'acceptance' field is caught."""
    scn_dir, brf_dir = temp_dirs

    bad = {
        "name": "missing_accept",
        "tier": "dry_run",
        "description": "No acceptance.",
        "brief": "canonical.md",
        "agents": [{"model": "deepseek-v4-pro"}],
    }
    _write_scenario(scn_dir / "missing_accept.yaml", bad)
    _write_brief(brf_dir / "canonical.md", "Hello\n")

    import tests.agentic.runner as runner

    result = runner.validate_scenario_dry_run("missing_accept", run_tag="test")

    assert result["ok"] is False
    assert any("missing required keys" in e for e in result["errors"])
    assert any("acceptance" in e for e in result["errors"])


def test_non_existent_scenario_file(temp_dirs: tuple[Path, Path]) -> None:
    """Asking for a scenario that has no YAML file at all."""
    # temp_dirs sets up dirs but we don't write a file for "ghost".

    import tests.agentic.runner as runner

    result = runner.validate_scenario_dry_run("ghost", run_tag="test")

    assert result["ok"] is False
    assert any("not found" in e for e in result["errors"])
