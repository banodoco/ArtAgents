"""pytest tests for assessor stderr filtering of structured AstridError envelopes.

Proves that invalid-enum structured stderr (as produced by
``_render_astrid_error`` in ``astrid.pipeline``) survives the assessor's
``_head_tail_filter_stderr`` and remains usable by the downstream LLM grader.

All tests are synthetic — no network, no LLM, no subprocess.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.agentic.assessor import _head_tail_filter_stderr, _build_user_payload


# ---------------------------------------------------------------------------
# Helper: write files into a tmp_path evidence pack
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ===================================================================
# 1. Structured envelope lines survive filtering — 7 tests
# ===================================================================

class TestStructuredEnvelopeSurvivesFiltering:
    """``_head_tail_filter_stderr`` preserves the four structured envelope markers
    that ``_render_astrid_error`` emits."""

    def test_valid_options_line_survives(self) -> None:
        """The ``valid options: ...`` line is preserved by the case-sensitive key."""
        stderr = "valid options: cross-fade, hard-cut, fade-to-black"
        result = _head_tail_filter_stderr(stderr)
        assert "valid options:" in result
        assert "cross-fade" in result

    def test_recovery_line_survives(self) -> None:
        """The ``recovery: ...`` line is preserved by the case-sensitive key."""
        stderr = "recovery: astrid timelines transition set --kind cross-fade"
        result = _head_tail_filter_stderr(stderr)
        assert "recovery:" in result
        assert "astrid timelines" in result

    def test_state_snapshot_line_survives(self) -> None:
        """The ``state snapshot: ...`` line is preserved by the case-sensitive key."""
        stderr = 'state snapshot: {"catalog": "transition", "argv": ["--kind", "crossfade"]}'
        result = _head_tail_filter_stderr(stderr)
        assert "state snapshot:" in result
        assert "catalog" in result

    def test_unstructured_degraded_flag_survives(self) -> None:
        """The ``unstructured - this is a bug.`` line is preserved."""
        stderr = "unstructured - this is a bug."
        result = _head_tail_filter_stderr(stderr)
        assert "unstructured" in result
        assert "bug" in result

    def test_cause_line_with_invalid_survives(self) -> None:
        """Cause lines containing 'invalid' (case-insensitive) survive filtering."""
        stderr = "argument --kind: invalid choice: crossfade (choose from cross-fade)"
        result = _head_tail_filter_stderr(stderr)
        assert "invalid choice" in result
        assert "crossfade" in result

    def test_cause_line_with_cannot_survives(self) -> None:
        """Cause lines containing 'cannot' (case-insensitive) survive filtering."""
        stderr = "cannot parse argument: unrecognized option"
        result = _head_tail_filter_stderr(stderr)
        assert "cannot parse" in result

    def test_cause_line_with_failed_survives(self) -> None:
        """Cause lines containing 'failed' (case-insensitive) survive filtering."""
        stderr = "operation failed: invalid transition kind 'wipe'"
        result = _head_tail_filter_stderr(stderr)
        assert "failed" in result
        assert "wipe" in result


# ===================================================================
# 2. Full envelope assembly survives — 4 tests
# ===================================================================

# ---------------------------------------------------------------------------
# Shared fixture stderr strings (module-level so multiple test classes can
# reference them).
# ---------------------------------------------------------------------------

_ENVELOPE_STDERR = (
    "argument --kind: invalid choice: crossfade (choose from cross-fade)\n"
    "valid options: cross-fade\n"
    "recovery: astrid timelines transition set --kind cross-fade\n"
    "state snapshot: {\"catalog\": \"transition\"}"
)

_DEGRADED_STDERR = (
    "unstructured - this is a bug.\n"
    "ValueError: unexpected transition catalog state\n"
    "state snapshot: {\"entrypoint\": \"astrid.pipeline.main\"}"
)


class TestFullEnvelopeSurvives:
    """A complete ``_render_astrid_error`` output survives filtering with all
    structured lines intact, while unrelated noise is stripped."""

    def test_full_envelope_all_lines_preserved(self) -> None:
        """Every structured line in a non-degraded envelope survives."""
        result = _head_tail_filter_stderr(_ENVELOPE_STDERR)
        assert "invalid choice" in result
        assert "valid options: cross-fade" in result
        assert "recovery: astrid timelines transition set --kind cross-fade" in result
        assert 'state snapshot: {"catalog": "transition"}' in result

    def test_degraded_envelope_all_lines_preserved(self) -> None:
        """Every structured line in a degraded envelope survives."""
        result = _head_tail_filter_stderr(_DEGRADED_STDERR)
        assert "unstructured - this is a bug." in result
        assert "ValueError: unexpected" in result
        assert "state snapshot:" in result

    def test_envelope_with_noise_filters_irrelevant_lines(self) -> None:
        """Unrelated stderr lines (no error/envelope markers) are stripped;
        structured envelope and error lines survive."""
        stderr = (
            "Downloading model weights...\n"
            "[tool] initializing runtime\n"
            "Extracting frames from input video...\n"
            + _ENVELOPE_STDERR +
            "\nCleaning up temporary files...\n"
        )
        result = _head_tail_filter_stderr(stderr)
        # Structured envelope lines preserved
        assert "invalid choice" in result
        assert "valid options:" in result
        assert "recovery:" in result
        assert "state snapshot:" in result
        # Tool marker preserved
        assert "[tool] initializing runtime" in result
        # Noise lines stripped
        assert "Downloading model weights" not in result
        assert "Extracting frames" not in result
        assert "Cleaning up" not in result

    def test_envelope_preserved_under_cap(self) -> None:
        """A full envelope within the character cap is returned whole (no truncation)."""
        result = _head_tail_filter_stderr(_ENVELOPE_STDERR)
        assert len(result) <= 8000  # CAP_STDERR_CHARS
        assert "... [truncated] ..." not in result


# ===================================================================
# 3. Usable by the assessor — 5 tests
# ===================================================================

class TestUsableByAssessor:
    """The filtered stderr, when embedded in the user payload, carries enough
    structured information that the assessor LLM can grade recovery behavior."""

    _BASIC_RUBRIC: dict = {
        "questions": [
            {
                "id": "q1",
                "question": "Does the agent detect the invalid choice and suggest the correct alternative?",
                "weight": 2,
            }
        ]
    }

    def _minimal_evidence_pack(self, tmp_path: Path, stderr: str) -> Path:
        """Create a minimal evidence pack with the given stderr."""
        ep = tmp_path / "evidence"
        _write(ep / "stderr.log", stderr)
        _write(ep / "report.md", "## 1. Summary\nThe agent tried --kind crossfade and got a recovery hint.")
        _write(ep / "plan.json", "{}")
        runs = ep / "runs" / "r1"
        _write(runs / "events.jsonl", '{"kind":"step_completed","step":"transcribe"}')
        _write(ep / "tree.txt", "project-root/\n  plan.json\n  runs/")
        _write(ep / ".astrid-session", "astrid_session_id=test")
        return ep

    def test_payload_contains_valid_options_for_llm(self, tmp_path: Path) -> None:
        """The user payload embeds the valid_options line so the LLM can see the correct choice."""
        stderr = _ENVELOPE_STDERR
        ep = self._minimal_evidence_pack(tmp_path, stderr)
        payload = _build_user_payload(ep, self._BASIC_RUBRIC, "test brief")
        assert "valid options: cross-fade" in payload

    def test_payload_contains_recovery_for_llm(self, tmp_path: Path) -> None:
        """The user payload embeds the recovery line so the LLM can see the fix."""
        stderr = _ENVELOPE_STDERR
        ep = self._minimal_evidence_pack(tmp_path, stderr)
        payload = _build_user_payload(ep, self._BASIC_RUBRIC, "test brief")
        assert "recovery: astrid timelines transition set --kind cross-fade" in payload

    def test_payload_contains_state_snapshot_for_llm(self, tmp_path: Path) -> None:
        """The user payload embeds the state snapshot so the LLM can see the context."""
        stderr = _ENVELOPE_STDERR
        ep = self._minimal_evidence_pack(tmp_path, stderr)
        payload = _build_user_payload(ep, self._BASIC_RUBRIC, "test brief")
        assert 'state snapshot: {"catalog": "transition"}' in payload

    def test_payload_contains_degraded_flag_for_llm(self, tmp_path: Path) -> None:
        """The user payload embeds the degraded bug-flag so the LLM can classify severity."""
        stderr = _DEGRADED_STDERR
        ep = self._minimal_evidence_pack(tmp_path, stderr)
        payload = _build_user_payload(ep, self._BASIC_RUBRIC, "test brief")
        assert "unstructured - this is a bug." in payload

    def test_noise_free_payload_helps_llm_focus(self, tmp_path: Path) -> None:
        """Noise lines (without error/envelope markers) are absent from the
        payload, so the LLM is not distracted by irrelevant stderr content."""
        stderr = (
            "Downloading model weights...\n"
            + _ENVELOPE_STDERR
            + "\nCleaning up temporary files...\n"
        )
        ep = self._minimal_evidence_pack(tmp_path, stderr)
        payload = _build_user_payload(ep, self._BASIC_RUBRIC, "test brief")
        assert "valid options: cross-fade" in payload  # structured survives
        assert "Downloading model weights" not in payload  # noise stripped
        assert "Cleaning up" not in payload  # noise stripped


# ===================================================================
# 4. Edge cases — 4 tests
# ===================================================================

class TestEdgeCases:
    """Boundary behavior of ``_head_tail_filter_stderr``."""

    def test_empty_stderr_returns_empty(self) -> None:
        """Empty stderr produces empty output."""
        assert _head_tail_filter_stderr("") == ""

    def test_stderr_with_no_matching_lines_returns_full_fallback(self) -> None:
        """When no lines match any key, the full stderr is returned as fallback.
        This ensures the LLM never gets a completely empty stderr section."""
        stderr = "Downloading model weights...\nExtracting frames...\nDone."
        result = _head_tail_filter_stderr(stderr)
        # Fallback: full stderr returned since nothing matched
        assert "Downloading model weights" in result
        assert "Extracting frames" in result

    def test_stderr_with_only_tool_lines_survives(self) -> None:
        """Tool/done-prefixed lines survive filtering even without error content."""
        stderr = "[tool] initializing\n[done] task completed\n[tool] cleaning up"
        result = _head_tail_filter_stderr(stderr)
        assert "[tool] initializing" in result
        assert "[done] task completed" in result

    def test_case_insensitive_error_matching(self) -> None:
        """CASE variations of error keywords still match (ci_keys are lowercased)."""
        stderr = "ERROR: something went wrong\nREJECTED: invalid input\nFailed to process"
        result = _head_tail_filter_stderr(stderr)
        assert "ERROR: something went wrong" in result
        assert "REJECTED: invalid input" in result
        assert "Failed to process" in result
