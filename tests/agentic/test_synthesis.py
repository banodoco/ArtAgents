"""Tests for tests.agentic.synthesis — read-only cross-scenario synthesis.

Verifies that:
- synthesis.py discovers Sisypy evidence directories correctly.
- The CLI accepts --reports-dir, --batch-summary, and --out-dir.
- Output synthesis.md and synthesis.json are produced.
- Source evidence files are never mutated.
- Deterministic output (no LLM dependency).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tests.agentic.synthesis import (
    _aggregate_outcomes,
    _discover_scenario_dirs,
    _extract_scenario_outcome,
    _format_synthesis_md,
    _read_evidence,
    main,
    synthesize,
)


# ---------------------------------------------------------------------------
# Synthetic evidence helpers
# ---------------------------------------------------------------------------


def _make_evidence_dir(
    base: Path,
    name: str,
    *,
    report: str | None = None,
    stderr: str | None = None,
    manifest: dict | None = None,
    assessment: dict | None = None,
) -> Path:
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    if report is not None:
        (d / "report.md").write_text(report, encoding="utf-8")
    if stderr is not None:
        (d / "stderr.log").write_text(stderr, encoding="utf-8")
    if manifest is not None:
        (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if assessment is not None:
        (d / "assessment.json").write_text(json.dumps(assessment), encoding="utf-8")
    return d


# ---------------------------------------------------------------------------
# Discovery tests
# ---------------------------------------------------------------------------


def test_discover_scenario_dirs_empty():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        dirs = _discover_scenario_dirs(base)
        assert dirs == []


def test_discover_scenario_dirs_finds_evidence_dirs():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        _make_evidence_dir(base, "scenario_a", report="# A")
        _make_evidence_dir(base, "scenario_b", stderr="log")
        _make_evidence_dir(base, "scenario_c", manifest={})
        _make_evidence_dir(base, "scenario_d", assessment={})
        # Empty dir — no evidence files
        (base / "empty_dir").mkdir()
        # Synthesis output dir — should be skipped
        (base / "_synthesis").mkdir()
        (base / "_synthesis" / "report.md").write_text("nope")

        dirs = _discover_scenario_dirs(base)
        names = {d.name for d in dirs}
        assert names == {"scenario_a", "scenario_b", "scenario_c", "scenario_d"}
        assert "_synthesis" not in names
        assert "empty_dir" not in names


def test_discover_scenario_dirs_skips_dot_dirs():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        _make_evidence_dir(base, ".hidden", report="# hidden")
        _make_evidence_dir(base, "visible", report="# visible")

        dirs = _discover_scenario_dirs(base)
        names = {d.name for d in dirs}
        assert names == {"visible"}


# ---------------------------------------------------------------------------
# Evidence reading tests
# ---------------------------------------------------------------------------


def test_read_evidence_full():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "scenario_x"
        base.mkdir()
        (base / "report.md").write_text("# Full report", encoding="utf-8")
        (base / "stderr.log").write_text("$ astrid run", encoding="utf-8")
        (base / "manifest.json").write_text(
            json.dumps({"files": {"report.md": "ok"}, "capture_gaps": []}), encoding="utf-8"
        )
        (base / "assessment.json").write_text(
            json.dumps({"enforced": {"test_check": {"passed": True}}}), encoding="utf-8"
        )

        evidence = _read_evidence(base)
        assert evidence["scenario"] == "scenario_x"
        assert evidence["report"] == "# Full report"
        assert evidence["stderr"] == "$ astrid run"
        assert evidence["manifest"] == {"files": {"report.md": "ok"}, "capture_gaps": []}
        assert evidence["assessment"] == {"enforced": {"test_check": {"passed": True}}}


def test_read_evidence_partial():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "partial"
        base.mkdir()
        (base / "report.md").write_text("# Only report", encoding="utf-8")

        evidence = _read_evidence(base)
        assert evidence["scenario"] == "partial"
        assert evidence["report"] == "# Only report"
        assert evidence["stderr"] is None
        assert evidence["manifest"] is None
        assert evidence["assessment"] is None


def test_read_evidence_invalid_json():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "bad_json"
        base.mkdir()
        (base / "manifest.json").write_text("not json", encoding="utf-8")
        (base / "assessment.json").write_text("{also not json", encoding="utf-8")

        evidence = _read_evidence(base)
        assert evidence["manifest"] is None
        assert evidence["assessment"] is None


# ---------------------------------------------------------------------------
# Outcome extraction tests
# ---------------------------------------------------------------------------


def test_extract_scenario_outcome_passed():
    evidence = {
        "scenario": "test_scenario",
        "report": "# OK",
        "stderr": "$ astrid run\n$ astrid check\n",
        "manifest": {},
        "assessment": {
            "enforced": {
                "check_a": {"passed": True, "rationale": "ok"},
                "check_b": {"passed": True},
            },
            "graded": {
                "quality_a": {"score": 0.9},
                "quality_b": {"score": 0.7},
            },
            "observed": {
                "shell_calls_count": {"value": 5},
            },
        },
    }
    outcome = _extract_scenario_outcome(evidence)
    assert outcome["outcome"] == "passed"
    assert outcome["quality_score"] == 0.8  # (0.9 + 0.7) / 2
    assert outcome["shell_calls"] == 5
    assert outcome["key_failures"] == []


def test_extract_scenario_outcome_failed_contract():
    evidence = {
        "scenario": "failed",
        "report": "# Failed",
        "stderr": "",
        "manifest": {},
        "assessment": {
            "enforced": {
                "must_pass": {"passed": False, "rationale": "did not pass"},
            },
            "graded": {},
            "observed": {},
        },
    }
    outcome = _extract_scenario_outcome(evidence)
    assert outcome["outcome"] == "failed_contract"
    assert "must_pass" in outcome["key_failures"]


def test_extract_scenario_outcome_no_assessment():
    evidence = {
        "scenario": "bare",
        "report": None,
        "stderr": None,
        "manifest": None,
        "assessment": None,
    }
    outcome = _extract_scenario_outcome(evidence)
    assert outcome["outcome"] == "passed"  # no assessment = no failures
    assert outcome["quality_score"] is None
    assert outcome["key_failures"] == []


def test_extract_scenario_outcome_rejected():
    evidence = {
        "scenario": "rejected_scenario",
        "report": "# Rejected",
        "stderr": "",
        "manifest": {},
        "assessment": {
            "enforced": {
                "invoked_via_canonical_cli": {"passed": False, "rationale": "bypassed"},
            },
            "graded": {},
            "observed": {},
        },
    }
    outcome = _extract_scenario_outcome(evidence)
    assert outcome["outcome"] == "rejected"


# ---------------------------------------------------------------------------
# Aggregation tests
# ---------------------------------------------------------------------------


def test_aggregate_outcomes_empty():
    synth = _aggregate_outcomes([])
    assert synth["contract_failures"] == []
    assert synth["quality_patterns"] == []
    assert synth["by_scenario"] == {}
    assert "No scenarios" in synth["summary"]


def test_aggregate_outcomes_mixed():
    outcomes = [
        {
            "scenario": "scenario_a",
            "outcome": "passed",
            "quality_score": 0.9,
            "key_failures": [],
            "shell_calls": 10,
            "canonical_bypass_forms": [],
            "observations": [],
        },
        {
            "scenario": "scenario_b",
            "outcome": "failed_contract",
            "quality_score": 0.5,
            "key_failures": ["check_x_failed"],
            "shell_calls": 20,
            "canonical_bypass_forms": ["resolved_after_reprompt"],
            "observations": ["capture_gap: missing file"],
        },
        {
            "scenario": "scenario_c",
            "outcome": "rejected",
            "quality_score": None,
            "key_failures": ["invoked_via_canonical_cli"],
            "shell_calls": 5,
            "canonical_bypass_forms": ["rejected"],
            "observations": [],
        },
    ]
    synth = _aggregate_outcomes(outcomes)
    assert synth["by_scenario"]["scenario_a"]["outcome"] == "passed"
    assert synth["by_scenario"]["scenario_b"]["outcome"] == "failed_contract"
    assert synth["by_scenario"]["scenario_c"]["outcome"] == "rejected"
    assert synth["observations"]["shell_calls_median"] == 10
    assert synth["observations"]["shell_calls_p90"] == 20
    assert set(synth["observations"]["canonical_bypass_forms"]) == {
        "rejected",
        "resolved_after_reprompt",
    }
    assert len(synth["contract_failures"]) >= 2


# ---------------------------------------------------------------------------
# Markdown rendering tests
# ---------------------------------------------------------------------------


def test_format_synthesis_md_empty():
    synth = {
        "contract_failures": [],
        "quality_patterns": [],
        "observations": {},
        "summary": "Nothing to report.",
        "by_scenario": {},
    }
    md = _format_synthesis_md(synth)
    assert "# Sisypy agentic synthesis" in md
    assert "Nothing to report" in md
    assert "Contract failures (0)" in md
    assert "- (none)" in md


def test_format_synthesis_md_with_data():
    synth = {
        "contract_failures": [
            {
                "id": "test_failure",
                "title": "Test Failure Pattern",
                "scenarios_affected": ["scenario_a", "scenario_b"],
                "evidence_snippets": ["scenario:scenario_a — failed"],
                "severity": "major",
                "suggested_fix": "Fix it.",
            }
        ],
        "quality_patterns": [],
        "observations": {"shell_calls_median": 12, "shell_calls_p90": 25},
        "summary": "2 passed, 1 failed.",
        "by_scenario": {
            "scenario_a": {"outcome": "passed", "quality_score": 0.85, "key_failures": []},
            "scenario_b": {
                "outcome": "failed_contract",
                "quality_score": 0.4,
                "key_failures": ["test_failure"],
            },
        },
    }
    md = _format_synthesis_md(synth)
    assert "Test Failure Pattern" in md
    assert "2 scenarios" in md
    assert "Shell calls" in md
    assert "median: 12" in md
    assert "**scenario_a**: passed" in md


# ---------------------------------------------------------------------------
# End-to-end synthesis tests
# ---------------------------------------------------------------------------


def test_synthesize_produces_outputs():
    with tempfile.TemporaryDirectory() as td:
        reports_dir = Path(td) / "reports" / "test-tag"
        _make_evidence_dir(
            reports_dir,
            "scenario_a",
            report="# Scenario A Report",
            stderr="$ astrid run a\n",
            manifest={"files": {}, "capture_gaps": []},
            assessment={
                "enforced": {"check_a": {"passed": True}},
                "graded": {"quality_a": {"score": 0.95}},
            },
        )
        _make_evidence_dir(
            reports_dir,
            "scenario_b",
            report="# Scenario B Report",
            stderr="$ astrid run b\n",
            manifest={"files": {}, "capture_gaps": ["missing_stderr"]},
            assessment={
                "enforced": {"check_b": {"passed": False, "rationale": "failed"}},
            },
        )

        md_path, json_path = synthesize(reports_dir)

        assert md_path.exists()
        assert json_path.exists()
        assert md_path.name == "synthesis.md"
        assert json_path.name == "synthesis.json"
        assert md_path.parent.name == "_synthesis"

        md = md_path.read_text(encoding="utf-8")
        js = json.loads(json_path.read_text(encoding="utf-8"))

        assert "Scenario A Report" not in md  # markdown is aggregate, not raw
        assert "scenario_a" in js["by_scenario"]
        assert js["by_scenario"]["scenario_a"]["outcome"] == "passed"
        assert js["by_scenario"]["scenario_b"]["outcome"] == "failed_contract"


def test_synthesize_does_not_mutate_source():
    with tempfile.TemporaryDirectory() as td:
        reports_dir = Path(td) / "reports" / "test-tag"
        sdir = _make_evidence_dir(
            reports_dir,
            "scenario_a",
            report="# Original Report",
            stderr="original stderr\n",
            manifest={"files": {"report.md": "ok"}},
            assessment={"enforced": {"check": {"passed": True}}},
        )

        # Record original content hashes
        original = {}
        for fname in ("report.md", "stderr.log", "manifest.json", "assessment.json"):
            fp = sdir / fname
            if fp.exists():
                original[fname] = fp.read_bytes()

        synthesize(reports_dir)

        # Verify nothing changed
        for fname, orig_bytes in original.items():
            assert (sdir / fname).read_bytes() == orig_bytes, f"{fname} was mutated!"


def test_synthesize_custom_out_dir():
    with tempfile.TemporaryDirectory() as td:
        reports_dir = Path(td) / "reports" / "test-tag"
        _make_evidence_dir(reports_dir, "scenario_a", report="# A")
        custom_out = Path(td) / "custom_synthesis"

        md_path, json_path = synthesize(reports_dir, out_dir=custom_out)

        assert custom_out.exists()
        assert md_path.parent == custom_out
        assert json_path.parent == custom_out


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_cli_requires_reports_dir():
    rc = main(["--out-dir", "/tmp/out"])
    assert rc == 1  # missing --reports-dir


def test_cli_reports_dir_not_found():
    rc = main(["--reports-dir", "/nonexistent/path/12345"])
    assert rc == 1


def test_cli_success():
    with tempfile.TemporaryDirectory() as td:
        reports_dir = Path(td) / "reports" / "test-tag"
        _make_evidence_dir(reports_dir, "scenario_a", report="# A")

        rc = main(["--reports-dir", str(reports_dir)])
        assert rc == 0
        synth_dir = reports_dir / "_synthesis"
        assert synth_dir.is_dir()
        assert (synth_dir / "synthesis.md").exists()
        assert (synth_dir / "synthesis.json").exists()


def test_cli_with_batch_summary():
    with tempfile.TemporaryDirectory() as td:
        reports_dir = Path(td) / "reports" / "test-tag"
        _make_evidence_dir(reports_dir, "scenario_a", report="# A")

        batch_path = Path(td) / "batch.json"
        batch_path.write_text(
            json.dumps(
                {
                    "scenarios": [
                        {
                            "scenario": "from_batch",
                            "outcome": "passed",
                            "quality_score": 0.99,
                            "key_failures": [],
                            "shell_calls": 3,
                            "canonical_bypass_forms": [],
                            "observations": [],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        rc = main(
            [
                "--reports-dir",
                str(reports_dir),
                "--batch-summary",
                str(batch_path),
                "--out-dir",
                str(Path(td) / "out"),
            ]
        )
        assert rc == 0
        js = json.loads((Path(td) / "out" / "synthesis.json").read_text(encoding="utf-8"))
        assert "from_batch" in js["by_scenario"]
        assert "scenario_a" in js["by_scenario"]
