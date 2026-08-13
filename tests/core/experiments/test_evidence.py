"""Tests for evidence, observation, inference, and decision integrity."""

from __future__ import annotations

from astrid.core.experiments.evidence import (
    check_claim_id_collision,
    validate_claims_batch,
    validate_evidence_integrity,
)


class TestEvidenceIntegrity:
    def test_empty_all_passes(self):
        issues = validate_evidence_integrity(
            observations=[], inferences=[], decisions=[]
        )
        assert issues == []

    def test_valid_cross_references_pass(self):
        obs = [{"id": "obs-1", "type": "observation", "claim": "C", "evidence": []}]
        inf = [
            {
                "id": "inf-1",
                "type": "inference",
                "claim": "I",
                "evidence_ids": ["obs-1"],
            }
        ]
        dec = [{"id": "dec-1", "type": "decision", "claim": "D", "based_on": ["inf-1"]}]
        issues = validate_evidence_integrity(
            observations=obs, inferences=inf, decisions=dec
        )
        assert issues == []

    def test_inference_references_invalid_observation(self):
        inf = [
            {
                "id": "inf-1",
                "type": "inference",
                "claim": "I",
                "evidence_ids": ["nonexistent"],
            }
        ]
        issues = validate_evidence_integrity(
            observations=[], inferences=inf, decisions=[]
        )
        assert len(issues) == 1
        assert "nonexistent" in issues[0]

    def test_decision_references_unknown_claim(self):
        dec = [
            {"id": "dec-1", "type": "decision", "claim": "D", "based_on": ["unknown"]}
        ]
        issues = validate_evidence_integrity(
            observations=[], inferences=[], decisions=dec
        )
        assert len(issues) == 1
        assert "unknown" in issues[0]

    def test_duplicate_observation_ids(self):
        obs = [
            {"id": "dup", "type": "observation", "claim": "A", "evidence": []},
            {"id": "dup", "type": "observation", "claim": "B", "evidence": []},
        ]
        issues = validate_evidence_integrity(
            observations=obs, inferences=[], decisions=[]
        )
        assert len(issues) == 1
        assert "duplicate" in issues[0].lower()

    def test_duplicate_inference_ids(self):
        obs = [
            {"id": "obs", "type": "observation", "claim": "O", "evidence": []}
        ]
        inf = [
            {"id": "dup", "type": "inference", "claim": "A", "evidence_ids": ["obs"]},
            {"id": "dup", "type": "inference", "claim": "B", "evidence_ids": ["obs"]},
        ]
        issues = validate_evidence_integrity(
            observations=obs, inferences=inf, decisions=[]
        )
        assert len(issues) == 1
        assert "duplicate" in issues[0].lower()

    def test_empty_inference_evidence_is_an_issue(self):
        issues = validate_evidence_integrity(
            observations=[],
            inferences=[{"id": "inf", "evidence_ids": []}],
            decisions=[],
        )
        assert any("at least one observation" in issue for issue in issues)

    def test_non_string_inference_evidence_is_an_issue(self):
        issues = validate_evidence_integrity(
            observations=[],
            inferences=[{"id": "inf", "evidence_ids": [123]}],
            decisions=[],
        )
        assert any("string claim id" in issue for issue in issues)

    def test_inference_to_inference_cross_kind_reference_is_an_issue(self):
        issues = validate_evidence_integrity(
            observations=[],
            inferences=[
                {"id": "inf-a", "evidence_ids": ["inf-b"]},
                {"id": "inf-b", "evidence_ids": ["inf-a"]},
            ],
            decisions=[],
        )
        assert any("unsupported claim kind" in issue for issue in issues)

    def test_decision_self_reference_is_an_issue(self):
        issues = validate_evidence_integrity(
            observations=[],
            inferences=[],
            decisions=[{"id": "dec", "based_on": ["dec"]}],
        )
        assert any("itself" in issue for issue in issues)

    def test_non_string_decision_reference_is_an_issue(self):
        issues = validate_evidence_integrity(
            observations=[],
            inferences=[],
            decisions=[{"id": "dec", "based_on": [123]}],
        )
        assert any("string claim id" in issue for issue in issues)


class TestIdCollision:
    def test_no_collision(self):
        issues = check_claim_id_collision(
            observations=[{"id": "o1"}],
            inferences=[{"id": "i1"}],
            decisions=[{"id": "d1"}],
        )
        assert issues == []

    def test_obs_inf_collision(self):
        issues = check_claim_id_collision(
            observations=[{"id": "x"}],
            inferences=[{"id": "x"}],
            decisions=[],
        )
        assert len(issues) == 1
        assert "observation and inference" in issues[0]

    def test_obs_dec_collision(self):
        issues = check_claim_id_collision(
            observations=[{"id": "x"}],
            inferences=[],
            decisions=[{"id": "x"}],
        )
        assert len(issues) == 1
        assert "observation and decision" in issues[0]


class TestValidateClaimsBatch:
    def test_classifies_mixed_claims(self):
        claims = [
            {"id": "o1", "type": "observation", "claim": "Observed.", "evidence": []},
            {
                "id": "i1",
                "type": "inference",
                "claim": "Inferred.",
                "evidence_ids": ["o1"],
                "confidence": "medium",
            },
            {"id": "d1", "type": "decision", "claim": "Decided.", "based_on": ["i1"]},
        ]
        obs, infs, decs, issues = validate_claims_batch(claims)
        assert len(obs) == 1
        assert len(infs) == 1
        assert len(decs) == 1
        assert issues == []

    def test_reports_invalid_claims(self):
        claims = [
            {"id": "bad", "type": "observation"},  # missing claim + evidence
        ]
        obs, infs, decs, issues = validate_claims_batch(claims)
        assert len(obs) == 0
        assert len(issues) > 0

    def test_unknown_type_reported(self):
        claims = [
            {"id": "x", "type": "unknown_kind", "claim": "X", "evidence": []},
        ]
        obs, infs, decs, issues = validate_claims_batch(claims)
        assert len(issues) == 1
        assert "unknown type" in issues[0]

    def test_cross_reference_integrity_in_batch(self):
        claims = [
            {"id": "i1", "type": "inference", "claim": "I", "evidence_ids": ["nonexistent"]},
        ]
        obs, infs, decs, issues = validate_claims_batch(claims)
        assert len(issues) > 0
