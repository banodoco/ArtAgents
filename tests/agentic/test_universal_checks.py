"""pytest tests for universal checks.

Covers contradiction detection, canonical-path bypass, deliverable shape,
and a clean-pass summary. All tests use synthetic tmp_path evidence packs
with deterministic findings — no subprocess, no network, no LLM.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.agentic.universal_checks import (
    detect_contradictions,
    canonical_path_bypass,
    deliverable_shape,
)


# ---------------------------------------------------------------------------
# Helper: write files into a tmp_path evidence pack
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ===================================================================
# 1. Contradiction detection — 6 tests
# ===================================================================

class TestContradictions:
    """detect_contradictions(evidence_pack, narrative) returns list of unsupported claims."""

    def test_empty_narrative_no_claims(self, tmp_path: Path) -> None:
        """Empty narrative yields zero claims, hence zero contradictions."""
        _write(tmp_path / "stderr.log", "some output")
        _write(tmp_path / "plan.json", "{}")
        result = detect_contradictions(tmp_path, "")
        assert result == []

    def test_claim_supported_in_stderr(self, tmp_path: Path) -> None:
        """A claim whose token appears in stderr.log is supported."""
        _write(tmp_path / "stderr.log", "I ran transcribe on the file")
        result = detect_contradictions(tmp_path, "I ran transcribe and it worked.")
        assert result == []

    def test_claim_supported_in_events(self, tmp_path: Path) -> None:
        """A claim whose token appears in events.jsonl is supported."""
        runs = tmp_path / "runs" / "r1"
        runs.mkdir(parents=True)
        _write(runs / "events.jsonl", '{"kind":"step_attested","step":"cut"}')
        result = detect_contradictions(tmp_path, "I ran cut successfully.")
        assert result == []

    def test_claim_supported_in_plan_json(self, tmp_path: Path) -> None:
        """A claim whose token appears in plan.json is supported."""
        _write(tmp_path / "plan.json", '{"steps":[{"id":"refine"}]}')
        result = detect_contradictions(tmp_path, "I invoked refine and it was great.")
        assert result == []

    def test_unsupported_claim_detected(self, tmp_path: Path) -> None:
        """A claim with no supporting trace is flagged as a major contradiction."""
        _write(tmp_path / "stderr.log", "hello world")
        _write(tmp_path / "plan.json", "{}")
        result = detect_contradictions(tmp_path, "I ran missing-tool and it failed.")
        assert len(result) == 1
        assert result[0]["severity"] == "major"
        assert "missing-tool" in result[0]["evidence_against"]

    def test_no_evidence_files_still_works(self, tmp_path: Path) -> None:
        """When no supporting files exist at all, claims are still extractable."""
        # No stderr.log, plan.json, tree.txt, or run dirs
        result = detect_contradictions(tmp_path, "I ran something.")
        assert len(result) >= 1  # at least the claim found


# ===================================================================
# 2. Canonical-path bypass — 7 tests
# ===================================================================

class TestCanonicalPathBypass:
    """canonical_path_bypass(evidence_pack, scenario_cfg) returns bool."""

    def test_no_bypass_with_canonical_cli(self, tmp_path: Path) -> None:
        """stderr shows only canonical `astrid orchestrators run ...` — no bypass."""
        _write(tmp_path / "stderr.log", "astrid orchestrators run builtin.hype --brief foo")
        cfg = {"target_orchestrator": "builtin.hype"}
        assert canonical_path_bypass(tmp_path, cfg) is False

    def test_python_m_bypass_detected(self, tmp_path: Path) -> None:
        """`python -m astrid.packs.X.run` in stderr triggers bypass."""
        _write(tmp_path / "stderr.log",
               "python -m astrid.packs.builtin.executors.cut.run --input foo")
        cfg = {"target_executor": "builtin.cut"}
        assert canonical_path_bypass(tmp_path, cfg) is True

    def test_direct_path_invocation_detected(self, tmp_path: Path) -> None:
        """`python astrid/packs/X/run.py` triggers bypass."""
        _write(tmp_path / "stderr.log",
               "python astrid/packs/builtin/executors/transcribe/run.py --audio clip.wav")
        cfg = {"target_executor": "builtin.transcribe"}
        assert canonical_path_bypass(tmp_path, cfg) is True

    def test_from_import_bypass_detected(self, tmp_path: Path) -> None:
        """`from astrid.packs.X import Y` triggers bypass."""
        _write(tmp_path / "report.md",
               "from astrid.packs.builtin.executors.render import run")
        cfg = {"target_executor": "builtin.render"}
        assert canonical_path_bypass(tmp_path, cfg) is True

    def test_import_bypass_detected(self, tmp_path: Path) -> None:
        """`import astrid.packs.X` triggers bypass."""
        _write(tmp_path / "stderr.log",
               "import astrid.packs.builtin.orchestrators.hype.run")
        cfg = {"target_orchestrator": "builtin.hype"}
        assert canonical_path_bypass(tmp_path, cfg) is True

    def test_bypass_exempt_honored(self, tmp_path: Path) -> None:
        """When scenario sets bypass_exempt=true, bypass detection is suppressed."""
        _write(tmp_path / "stderr.log",
               "python -m astrid.packs.builtin.executors.cut.run --input foo")
        cfg = {
            "target_executor": "builtin.cut",
            "assessment": {"bypass_exempt": True},
        }
        assert canonical_path_bypass(tmp_path, cfg) is False

    def test_no_canonical_surface_no_bypass_flag(self, tmp_path: Path) -> None:
        """Without target_orchestrator/target_executor and no canonical rubric,
        bypass is not flagged even if bypass patterns appear."""
        _write(tmp_path / "stderr.log",
               "python -m astrid.packs.X.run")
        cfg: dict = {}
        assert canonical_path_bypass(tmp_path, cfg) is False

    def test_bare_path_not_flagged(self, tmp_path: Path) -> None:
        """A bare path mention without an execution prefix (python, ./, bash, exec)
        is NOT flagged as a bypass — regression guard for false positives."""
        _write(tmp_path / "report.md",
               "The pipeline lives at astrid/packs/builtin/executors/cut/run.py.")
        cfg = {"target_executor": "builtin.cut"}
        assert canonical_path_bypass(tmp_path, cfg) is False


# ===================================================================
# 3. Deliverable shape — 6 tests
# ===================================================================

class TestDeliverableShape:
    """deliverable_shape(evidence_pack, brief_text) returns a shape dict."""

    def test_report_missing(self, tmp_path: Path) -> None:
        """When report.md doesn't exist, ok=False with a reason."""
        brief = "1. **What you did** — explain the steps taken."
        result = deliverable_shape(tmp_path, brief)
        assert result["ok"] is False
        assert "not present" in result["reason"]

    def test_all_sections_present(self, tmp_path: Path) -> None:
        """When report.md covers all numbered brief sections, ok=True."""
        brief = "1. **What you did**\n2. **What went wrong**\n3. **Next steps**"
        report = "## 1. What I did\nI ran the tool.\n\n## 2. What went wrong\nNothing.\n\n## 3. Next steps\nDone."
        _write(tmp_path / "report.md", report)
        result = deliverable_shape(tmp_path, brief)
        assert result["ok"] is True
        assert result["missing_sections"] == []

    def test_missing_sections_detected(self, tmp_path: Path) -> None:
        """When report.md is missing some required sections, they are listed."""
        brief = "1. **What you did**\n2. **What went wrong**\n3. **Next steps**"
        report = "## 1. What I did\nI ran the tool.\n\n## 3. Next steps\nDone."
        _write(tmp_path / "report.md", report)
        result = deliverable_shape(tmp_path, brief)
        assert result["ok"] is False
        assert 2 in result["missing_sections"]

    def test_bold_numbered_format_accepted(self, tmp_path: Path) -> None:
        """Bold-numbered format (**1.** Foo) is accepted as a valid section."""
        brief = "1. **Summary**"
        report = "**1.** Summary: it worked."
        _write(tmp_path / "report.md", report)
        result = deliverable_shape(tmp_path, brief)
        assert result["ok"] is True

    def test_non_contiguous_brief_truncated(self, tmp_path: Path) -> None:
        """Only contiguous-from-1 sections are required. A floating '5. Foo'
        without 2,3,4 does not demand section 5."""
        brief = "1. **Intro**\n5. **Random item**"
        report = "## 1. Intro\nHere is the intro."
        _write(tmp_path / "report.md", report)
        result = deliverable_shape(tmp_path, brief)
        assert result["ok"] is True
        assert result["required_sections"] == [1]

    def test_empty_brief_no_requirements(self, tmp_path: Path) -> None:
        """An empty brief yields zero required sections, so any report is ok."""
        report = "# Unstructured report\nJust some text."
        _write(tmp_path / "report.md", report)
        result = deliverable_shape(tmp_path, "")
        assert result["ok"] is True
        assert result["required_sections"] == []


# ===================================================================
# 4. Clean pass — 1 test
# ===================================================================

class TestCleanPass:
    """All three checks pass simultaneously with well-formed evidence."""

    def test_all_three_checks_pass(self, tmp_path: Path) -> None:
        """Well-formed evidence yields zero contradictions, no bypass, and shape ok."""
        # --- Evidence pack ---
        _write(tmp_path / "stderr.log",
               "astrid executors run builtin.cut --input foo.mp4\n"
               "Processing... done.")
        _write(tmp_path / "plan.json", json.dumps({"steps": [{"id": "cut"}]}))
        runs = tmp_path / "runs" / "r1"
        runs.mkdir(parents=True)
        _write(runs / "events.jsonl",
               '{"kind":"step_started","step":"cut"}\n'
               '{"kind":"step_completed","step":"cut"}')

        # --- Report with all required sections ---
        brief = "1. **What you did**\n2. **What you found**"
        report = "## 1. What I did\nI invoked cut.\n\n## 2. What I found\nIt worked."
        _write(tmp_path / "report.md", report)

        # --- Scenario config ---
        cfg = {"target_executor": "builtin.cut"}

        # (1) Contradictions: narrative matches evidence
        contradictions = detect_contradictions(tmp_path, "I ran cut and it succeeded.")
        assert contradictions == []

        # (2) Canonical-path bypass: canonical CLI used, no bypass patterns
        assert canonical_path_bypass(tmp_path, cfg) is False

        # (3) Deliverable shape: all sections present
        shape = deliverable_shape(tmp_path, brief)
        assert shape["ok"] is True
        assert shape["missing_sections"] == []
