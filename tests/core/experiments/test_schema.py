"""Tests for experiment schema validation primitives."""
from __future__ import annotations

import pytest

from astrid.core.experiments.schema import (
    ExperimentValidationError,
    is_terminal_status,
    normalize_status,
    require_relative_path,
    validate_case_id,
    validate_content_hash,
    validate_decision,
    validate_diagnostics,
    validate_experiment,
    validate_experiment_id,
    validate_factor_id,
    validate_hypothesis_id,
    validate_inference,
    validate_observation,
    validate_path,
    validate_review,
    validate_review_decision,
    validate_rubric_id,
    validate_run_id,
)

# ── Path safety ────────────────────────────────────────────────────────────

class TestPathValidation:
    def test_accepts_relative_path(self):
        assert validate_path("inputs/image.png") == "inputs/image.png"

    def test_accepts_nested_relative_path(self):
        assert validate_path("a/b/c/d.json") == "a/b/c/d.json"

    def test_rejects_absolute_path(self):
        with pytest.raises(ExperimentValidationError, match="must be relative"):
            validate_path("/etc/passwd")

    def test_rejects_home_expansion(self):
        with pytest.raises(ExperimentValidationError, match="must be relative"):
            validate_path("~/secret.txt")

    def test_rejects_parent_traversal(self):
        with pytest.raises(ExperimentValidationError, match="must not contain"):
            validate_path("../../../etc/passwd")

    def test_rejects_dotdot_anywhere(self):
        with pytest.raises(ExperimentValidationError, match="must not contain"):
            validate_path("foo/../bar")

    def test_rejects_nul_bytes(self):
        with pytest.raises(ExperimentValidationError, match="NUL"):
            validate_path("foo\x00bar")

    def test_rejects_empty_string(self):
        with pytest.raises(ExperimentValidationError, match="non-empty"):
            validate_path("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ExperimentValidationError, match="non-empty"):
            validate_path("   ")

    def test_require_relative_path_same(self):
        assert require_relative_path("foo/bar.json") == "foo/bar.json"


# ── ID validation ──────────────────────────────────────────────────────────

class TestIdValidation:
    def test_valid_experiment_id(self):
        assert validate_experiment_id("desert-plant-2026") == "desert-plant-2026"

    def test_experiment_id_rejects_uppercase_start(self):
        with pytest.raises(ExperimentValidationError):
            validate_experiment_id("Desert")

    def test_experiment_id_rejects_special_chars(self):
        with pytest.raises(ExperimentValidationError):
            validate_experiment_id("test@id")

    def test_valid_hypothesis_id(self):
        assert validate_hypothesis_id("h-composite-video") == "h-composite-video"

    def test_hypothesis_id_rejects_numeric_start(self):
        with pytest.raises(ExperimentValidationError):
            validate_hypothesis_id("1-hypothesis")

    def test_valid_factor_id(self):
        assert validate_factor_id("conditioning") == "conditioning"

    def test_valid_rubric_id(self):
        assert validate_rubric_id("continuity") == "continuity"

    def test_valid_case_id(self):
        assert validate_case_id("four-images-seed-35635335") == "four-images-seed-35635335"

    def test_case_id_rejects_empty(self):
        with pytest.raises(ExperimentValidationError):
            validate_case_id("")

    def test_valid_run_id_ulid(self):
        assert validate_run_id("00123456789ABCDEFGHJKMNPQR") == "00123456789ABCDEFGHJKMNPQR"

    def test_run_id_rejects_short(self):
        with pytest.raises(ExperimentValidationError):
            validate_run_id("short")

    def test_run_id_rejects_invalid_chars(self):
        with pytest.raises(ExperimentValidationError):
            validate_run_id("01JABCDEFGHIJKLMNOPQRSTUVW!")  # invalid char

    def test_run_id_rejects_lowercase_l(self):
        with pytest.raises(ExperimentValidationError):
            validate_run_id("01JABCDEFGHIJKLMNOPQRSTUVWl")  # lowercase L is invalid in Crockford


# ── Content hash validation ────────────────────────────────────────────────

class TestContentHashValidation:
    def test_valid_sha256(self):
        h = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert validate_content_hash(h) == h

    def test_rejects_missing_prefix(self):
        with pytest.raises(ExperimentValidationError):
            validate_content_hash("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    def test_rejects_short_digest(self):
        with pytest.raises(ExperimentValidationError):
            validate_content_hash("sha256:abc123")

    def test_rejects_invalid_hex(self):
        with pytest.raises(ExperimentValidationError):
            validate_content_hash("sha256:" + "g" * 64)


# ── Experiment validation ─────────────────────────────────────────────────

class TestExperimentValidation:
    def test_valid_experiment_passes(self):
        exp = {
            "schema_version": 1,
            "experiment_id": "test-experiment-1",
            "project_slug": "test-project",
            "title": "Test Experiment",
            "question": "What is the answer?",
            "hypotheses": [
                {"id": "h-test", "claim": "Something is true."}
            ],
            "factors": [
                {"id": "method", "values": ["a", "b"]}
            ],
            "rubric": [
                {"id": "quality", "label": "Quality", "scale": {"min": 1, "max": 5}}
            ],
            "cases": [
                {
                    "case_id": "case-a",
                    "label": "Case A",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "attempt": 1,
                    "factors": {"method": "a"},
                    "relationship": {"type": "baseline", "case_id": None},
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        result = validate_experiment(exp)
        assert result["experiment_id"] == "test-experiment-1"
        assert result["updated"] == "2026-07-27T00:00:00Z"  # auto-set

    def test_missing_required_field(self):
        with pytest.raises(ExperimentValidationError, match="missing required field"):
            validate_experiment({"experiment_id": "test"})

    def test_rejects_non_object(self):
        with pytest.raises(ExperimentValidationError, match="must be an object"):
            validate_experiment("not an object")  # type: ignore[arg-type]

    def test_rejects_empty_title(self):
        exp = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "project_slug": "p",
            "title": "",
            "question": "?",
            "hypotheses": [],
            "factors": [{"id": "f", "values": ["a"]}],
            "rubric": [{"id": "r", "label": "L", "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": "c1",
                    "label": "C1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "factors": {"f": "a"},
                    "relationship": {"type": "baseline", "case_id": None},
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        with pytest.raises(ExperimentValidationError, match="title must be non-empty"):
            validate_experiment(exp)

    def test_requires_controlled_factor(self):
        exp = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "project_slug": "p",
            "title": "T",
            "question": "Q",
            "hypotheses": [],
            "factors": [{"id": "seed", "type": "integer"}],
            "rubric": [{"id": "r", "label": "L", "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": "c1",
                    "label": "C1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "factors": {"seed": 42},
                    "relationship": {"type": "baseline", "case_id": None},
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        with pytest.raises(ExperimentValidationError, match="controlled factor"):
            validate_experiment(exp)

    def test_case_must_declare_all_factors(self):
        exp = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "project_slug": "p",
            "title": "T",
            "question": "Q",
            "hypotheses": [],
            "factors": [
                {"id": "method", "values": ["a", "b"]},
                {"id": "seed", "type": "integer"},
            ],
            "rubric": [{"id": "r", "label": "L", "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": "c1",
                    "label": "C1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "factors": {"method": "a"},
                    "relationship": {"type": "baseline", "case_id": None},
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        with pytest.raises(ExperimentValidationError, match="missing factor"):
            validate_experiment(exp)

    def test_rejects_unknown_factor_in_case(self):
        exp = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "project_slug": "p",
            "title": "T",
            "question": "Q",
            "hypotheses": [],
            "factors": [{"id": "method", "values": ["a"]}],
            "rubric": [{"id": "r", "label": "L", "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": "c1",
                    "label": "C1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "factors": {"method": "a", "unknown_factor": "x"},
                    "relationship": {"type": "baseline", "case_id": None},
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        with pytest.raises(ExperimentValidationError, match="unknown factor"):
            validate_experiment(exp)

    def test_relationship_variant_requires_case_id(self):
        exp = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "project_slug": "p",
            "title": "T",
            "question": "Q",
            "hypotheses": [],
            "factors": [{"id": "f", "values": ["a"]}],
            "rubric": [{"id": "r", "label": "L", "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": "c1",
                    "label": "C1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "factors": {"f": "a"},
                    "relationship": {"type": "variant", "case_id": None},
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        with pytest.raises(ExperimentValidationError, match="requires case_id"):
            validate_experiment(exp)

    def test_preserves_unknown_fields(self):
        exp = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "project_slug": "p",
            "title": "T",
            "question": "Q",
            "hypotheses": [],
            "factors": [{"id": "f", "values": ["a"]}],
            "rubric": [{"id": "r", "label": "L", "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": "c1",
                    "label": "C1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "factors": {"f": "a"},
                    "relationship": {"type": "baseline", "case_id": None},
                    "extra_field": "preserved",
                }
            ],
            "created": "2026-07-27T00:00:00Z",
            "custom_meta": {"nested": True},
        }
        result = validate_experiment(exp)
        assert result["custom_meta"] == {"nested": True}
        assert result["cases"][0]["extra_field"] == "preserved"

    def test_rejects_invalid_input_role(self):
        exp = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "project_slug": "p",
            "title": "T",
            "question": "Q",
            "hypotheses": [],
            "factors": [{"id": "f", "values": ["a"]}],
            "rubric": [{"id": "r", "label": "L", "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": "c1",
                    "label": "C1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "factors": {"f": "a"},
                    "relationship": {"type": "baseline", "case_id": None},
                    "expected_input_roles": ["nonexistent_role"],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        with pytest.raises(ExperimentValidationError, match="unknown input role"):
            validate_experiment(exp)

    def test_accepts_valid_input_roles(self):
        exp = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "project_slug": "p",
            "title": "T",
            "question": "Q",
            "hypotheses": [],
            "factors": [{"id": "f", "values": ["a"]}],
            "rubric": [{"id": "r", "label": "L", "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": "c1",
                    "label": "C1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "factors": {"f": "a"},
                    "relationship": {"type": "baseline", "case_id": None},
                    "expected_input_roles": ["appearance_reference", "motion_reference"],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        result = validate_experiment(exp)
        assert result["cases"][0]["expected_input_roles"] == ["appearance_reference", "motion_reference"]


# ── Review validation ─────────────────────────────────────────────────────

class TestReviewValidation:
    def test_valid_review_passes(self):
        review = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "cases": [
                {
                    "case_id": "case-a",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "model": "flux-dev",
                    "prompt": "test prompt",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/img.png",
                            "content_hash": "sha256:" + "a" * 64,
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        result = validate_review(review)
        assert result["experiment_id"] == "test-1"

    def test_rejects_invalid_status(self):
        review = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "cases": [
                {
                    "case_id": "case-a",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "unknown_status",
                    "inputs": [],
                    "outputs": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        with pytest.raises(ExperimentValidationError, match="status must be one of"):
            validate_review(review)

    def test_failure_requires_error(self):
        review = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "cases": [
                {
                    "case_id": "case-a",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "failed",
                    "inputs": [],
                    "outputs": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        with pytest.raises(ExperimentValidationError, match="requires an error"):
            validate_review(review)

    def test_accepts_failure_with_error(self):
        review = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "cases": [
                {
                    "case_id": "case-a",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "failed",
                    "error": "something went wrong",
                    "inputs": [],
                    "outputs": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        result = validate_review(review)
        assert result["cases"][0]["status"] == "failed"

    def test_rejects_duplicate_input_ordinals(self):
        review = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "cases": [
                {
                    "case_id": "case-a",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "inputs": [
                        {
                            "ordinal": 1,
                            "role": "appearance_reference",
                            "path": "a.png",
                            "content_hash": "sha256:" + "a" * 64,
                            "verified": True,
                        },
                        {
                            "ordinal": 1,
                            "role": "motion_reference",
                            "path": "b.mp4",
                            "content_hash": "sha256:" + "b" * 64,
                            "verified": True,
                        },
                    ],
                    "outputs": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        with pytest.raises(ExperimentValidationError, match="duplicate input ordinal"):
            validate_review(review)

    def test_rejects_source_url_in_output(self):
        review = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "cases": [
                {
                    "case_id": "case-a",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/img.png",
                            "content_hash": "sha256:" + "a" * 64,
                            "verified": True,
                            "source_url": "https://secret-url.example.com/token=abc",
                        }
                    ],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        with pytest.raises(ExperimentValidationError, match="forbidden field"):
            validate_review(review)


# ── Diagnostics validation ────────────────────────────────────────────────

class TestDiagnosticsValidation:
    def test_valid_diagnostics(self):
        diag = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "total_cases": 5,
        }
        result = validate_diagnostics(diag)
        assert result["total_cases"] == 5
        assert "status_counts" in result
        assert "duplicate_output_groups" in result


# ── Evidence / claims validation ──────────────────────────────────────────

class TestClaimsValidation:
    def test_valid_observation(self):
        obs = {
            "id": "obs-1",
            "type": "observation",
            "claim": "The request was rejected.",
            "evidence": [{"case_id": "case-a", "kind": "provider_response"}],
        }
        result = validate_observation(obs)
        assert result["id"] == "obs-1"

    def test_observation_must_be_type_observation(self):
        with pytest.raises(ExperimentValidationError, match="must be 'observation'"):
            validate_observation({"id": "x", "type": "inference", "claim": "X", "evidence": []})

    def test_valid_inference(self):
        inf = {
            "id": "inf-1",
            "type": "inference",
            "claim": "Mixed media is rejected.",
            "evidence_ids": ["obs-1", "obs-2"],
            "confidence": "high",
            "status": "provisional",
        }
        result = validate_inference(inf)
        assert result["confidence"] == "high"

    def test_inference_rejects_invalid_confidence(self):
        with pytest.raises(ExperimentValidationError, match="confidence must be"):
            validate_inference({
                "id": "inf-1",
                "type": "inference",
                "claim": "X",
                "evidence_ids": [],
                "confidence": "certain",
            })

    def test_valid_decision(self):
        dec = {
            "id": "dec-1",
            "type": "decision",
            "claim": "Use composite video.",
            "based_on": ["inf-1"],
        }
        result = validate_decision(dec)
        assert result["claim"] == "Use composite video."

    def test_decision_requires_based_on(self):
        with pytest.raises(ExperimentValidationError):
            validate_decision({
                "id": "dec-1",
                "type": "decision",
                "claim": "X",
                "based_on": [],
            })

    def test_review_decision(self):
        rd = {
            "case_id": "case-a",
            "reviewer": {"type": "human", "id": "peter"},
            "scores": {"continuity": 3},
            "verdict": "iterate",
            "created": "2026-07-27T00:00:00Z",
        }
        result = validate_review_decision(rd)
        assert result["verdict"] == "iterate"


# ── Status normalization ──────────────────────────────────────────────────

class TestStatusNormalization:
    def test_maps_success_to_completed(self):
        assert normalize_status("success") == "completed"

    def test_maps_error_to_failed(self):
        assert normalize_status("error") == "failed"

    def test_maps_rejected(self):
        assert normalize_status("rejected") == "provider_rejected"

    def test_maps_timeout(self):
        assert normalize_status("timeout") == "timed_out"

    def test_passes_through_unknown(self):
        assert normalize_status("custom_status") == "custom_status"

    def test_terminal_status_check(self):
        assert is_terminal_status("completed")
        assert is_terminal_status("failed")
        assert not is_terminal_status("draft")
        assert not is_terminal_status("unknown")


# ── Regression tests for G1 findings ───────────────────────────────────────

class TestSchemaRegression:
    def test_review_output_without_content_hash_passes(self):
        """Output entries may omit content_hash for unresolved capture-gap artifacts."""
        review = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "cases": [
                {
                    "case_id": "case-a",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/img.png",
                            "verified": False,
                        }
                    ],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        result = validate_review(review)
        assert len(result["cases"]) == 1

    def test_review_output_with_null_content_hash_rejected(self):
        """Null content_hash is not valid — must be absent or a valid hash."""
        review = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "cases": [
                {
                    "case_id": "case-a",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/img.png",
                            "content_hash": None,
                        }
                    ],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        with pytest.raises(ExperimentValidationError):
            validate_review(review)

    def test_review_input_without_content_hash_passes(self):
        """Input entries may omit content_hash for unresolved artifacts."""
        review = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "cases": [
                {
                    "case_id": "case-a",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "inputs": [
                        {
                            "ordinal": 1,
                            "role": "appearance_reference",
                            "path": "inputs/ref.png",
                            "verified": False,
                        }
                    ],
                    "outputs": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        result = validate_review(review)
        assert len(result["cases"]) == 1

    def test_source_manifest_without_content_hash_passes(self):
        """source_manifest may omit content_hash for unreadable manifests."""
        review = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "cases": [
                {
                    "case_id": "case-a",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "inputs": [],
                    "outputs": [],
                    "source_manifest": {
                        "path": "manifest.json",
                    },
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        result = validate_review(review)
        assert "source_manifest" in result["cases"][0]

    def test_review_includes_optional_context_fields(self):
        """Review may include title, question, hypotheses, factors, rubric."""
        review = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "title": "Test Title",
            "question": "What?",
            "hypotheses": [{"id": "h-1", "claim": "C", "status": "provisional"}],
            "factors": [{"id": "f", "values": ["a"]}],
            "rubric": [{"id": "r", "label": "L", "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": "case-a",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "inputs": [],
                    "outputs": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        result = validate_review(review)
        assert result["title"] == "Test Title"
        assert result["question"] == "What?"


# ── Gate-G2 §3: exact case-set contract (duplicate rejection) ──────────────


def _two_case_experiment(case_b_id: str = "case-b", case_b_run: str = "1789ABCDEFGHJKMNPQRSTVWXYZ"):
    return {
        "schema_version": 1,
        "experiment_id": "dup-test",
        "project_slug": "p",
        "title": "Dup Test",
        "question": "q?",
        "hypotheses": [],
        "factors": [{"id": "method", "values": ["a", "b"]}],
        "rubric": [{"id": "quality", "label": "Q", "scale": {"min": 1, "max": 5}}],
        "cases": [
            {
                "case_id": "case-a",
                "label": "A",
                "run_id": "00123456789ABCDEFGHJKMNPQR",
                "factors": {"method": "a"},
                "relationship": {"type": "baseline", "case_id": None},
            },
            {
                "case_id": case_b_id,
                "label": "B",
                "run_id": case_b_run,
                "factors": {"method": "b"},
                "relationship": {"type": "baseline", "case_id": None},
            },
        ],
        "created": "2026-07-27T00:00:00Z",
    }


class TestDuplicateCaseContract:
    def test_duplicate_case_id_rejected(self):
        exp = _two_case_experiment(case_b_id="case-a")
        with pytest.raises(ExperimentValidationError, match="duplicate case_id"):
            validate_experiment(exp)

    def test_duplicate_run_id_rejected(self):
        exp = _two_case_experiment(case_b_run="00123456789ABCDEFGHJKMNPQR")
        with pytest.raises(ExperimentValidationError, match="duplicate run_id"):
            validate_experiment(exp)

    def test_distinct_case_and_run_ids_pass(self):
        result = validate_experiment(_two_case_experiment())
        assert {c["case_id"] for c in result["cases"]} == {"case-a", "case-b"}

    def test_review_duplicate_case_id_rejected(self):
        review = {
            "schema_version": 1,
            "experiment_id": "test-1",
            "cases": [
                {"case_id": "case-a", "run_id": "00123456789ABCDEFGHJKMNPQR",
                 "status": "completed", "inputs": [], "outputs": []},
                {"case_id": "case-a", "run_id": "1789ABCDEFGHJKMNPQRSTVWXYZ",
                 "status": "completed", "inputs": [], "outputs": []},
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        with pytest.raises(ExperimentValidationError, match="duplicate case_id"):
            validate_review(review)


class TestGateG3AdversarialSchema:
    @pytest.mark.parametrize(
        "path",
        [
            " https://attacker.invalid/media.png",
            "\thTtPs://attacker.invalid/media.png",
            "data:image/png;base64,AAAA",
            "javascript:alert(1)",
            "file:///etc/passwd",
            "custom+transport:payload",
            "outputs/image.png ",
            "outputs/\nimage.png",
        ],
    )
    def test_whitespace_control_and_uri_artifact_paths_rejected(self, path):
        with pytest.raises(
            ExperimentValidationError,
            match="relative|whitespace|control",
        ):
            require_relative_path(path)

    @staticmethod
    def _review():
        return {
            "schema_version": 1,
            "experiment_id": "test-1",
            "cases": [{
                "case_id": "case-a",
                "run_id": "00123456789ABCDEFGHJKMNPQR",
                "status": "completed",
                "inputs": [],
                "outputs": [],
            }],
            "created": "2026-07-27T00:00:00Z",
        }

    @pytest.mark.parametrize("schema_version", [True, 2, 1.0, "1"])
    def test_review_requires_exact_non_bool_schema_version(self, schema_version):
        review = self._review()
        review["schema_version"] = schema_version
        with pytest.raises(ExperimentValidationError, match="schema_version"):
            validate_review(review)

    def test_experiment_rejects_boolean_schema_version(self):
        experiment = _two_case_experiment()
        experiment["schema_version"] = True
        with pytest.raises(ExperimentValidationError, match="schema_version"):
            validate_experiment(experiment)

    @pytest.mark.parametrize(
        "created",
        ["", "not-a-timestamp", "2026-07-27T00:00:00"],
    )
    def test_review_requires_valid_timezone_aware_created(self, created):
        review = self._review()
        review["created"] = created
        with pytest.raises(ExperimentValidationError, match="created"):
            validate_review(review)

    def test_review_requires_created(self):
        review = self._review()
        del review["created"]
        with pytest.raises(ExperimentValidationError, match="created"):
            validate_review(review)

    @pytest.mark.parametrize("field", ["inputs", "outputs"])
    @pytest.mark.parametrize("wrong_type", ["", {}, False, 0])
    def test_review_rejects_falsey_wrong_collection_types(
        self, field, wrong_type
    ):
        review = self._review()
        review["cases"][0][field] = wrong_type
        with pytest.raises(ExperimentValidationError, match=field):
            validate_review(review)

    def test_missing_output_verified_rejected(self):
        review = self._review()
        review["cases"][0]["outputs"] = [{"path": "out.png"}]
        with pytest.raises(ExperimentValidationError, match="verified"):
            validate_review(review)

    def test_missing_input_verified_rejected(self):
        review = self._review()
        review["cases"][0]["inputs"] = [{
            "ordinal": 1,
            "role": "appearance_reference",
            "path": "input.png",
        }]
        with pytest.raises(ExperimentValidationError, match="verified"):
            validate_review(review)

    def test_string_verified_rejected(self):
        review = self._review()
        review["cases"][0]["outputs"] = [{
            "path": "out.png",
            "content_hash": "sha256:" + "a" * 64,
            "verified": "false",
        }]
        with pytest.raises(ExperimentValidationError, match="verified must be a boolean"):
            validate_review(review)

    @pytest.mark.parametrize(
        ("validator", "record"),
        [
            (
                validate_inference,
                {
                    "id": "inf-1",
                    "type": "inference",
                    "claim": "Unsupported.",
                    "evidence_ids": [],
                    "confidence": "medium",
                },
            ),
            (
                validate_decision,
                {
                    "id": "dec-1",
                    "type": "decision",
                    "claim": "Unsupported.",
                    "based_on": [],
                },
            ),
        ],
    )
    def test_claim_reference_lists_must_be_nonempty(self, validator, record):
        with pytest.raises(ExperimentValidationError, match="at least one"):
            validator(record)

    @pytest.mark.parametrize("reference", [1, False, None, {}, "Bad ID!"])
    def test_inference_references_must_be_string_claim_ids(self, reference):
        with pytest.raises(ExperimentValidationError, match="claim id|string"):
            validate_inference({
                "id": "inf-1",
                "type": "inference",
                "claim": "Unsupported.",
                "evidence_ids": [reference],
                "confidence": "medium",
            })

    @pytest.mark.parametrize("reference", [1, False, None, {}, "Bad ID!"])
    def test_decision_references_must_be_string_claim_ids(self, reference):
        with pytest.raises(ExperimentValidationError, match="claim id|string"):
            validate_decision({
                "id": "dec-1",
                "type": "decision",
                "claim": "Unsupported.",
                "based_on": [reference],
            })

    def test_observation_case_reference_must_be_string_id(self):
        with pytest.raises(ExperimentValidationError, match="case_id"):
            validate_observation({
                "id": "obs-1",
                "type": "observation",
                "claim": "Observed.",
                "evidence": [{"case_id": 123}],
            })

    def test_review_decision_created_must_be_valid_timestamp(self):
        with pytest.raises(ExperimentValidationError, match="created"):
            validate_review_decision({
                "case_id": "case-a",
                "reviewer": {"type": "human", "id": "peter"},
                "scores": {"quality": 3},
                "verdict": "ship",
                "created": "not-a-timestamp",
            })
