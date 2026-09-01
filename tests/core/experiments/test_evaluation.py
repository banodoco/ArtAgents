"""Tests for rubric response schema generation and final/conclusions validation."""

from __future__ import annotations

import pytest

from astrid.core.experiments.evaluation import (
    build_review_final,
    build_rubric_response_schema,
    validate_conclusions,
    validate_review_final,
)
from astrid.core.experiments.schema import ExperimentValidationError

RUBRIC = [
    {"id": "continuity", "label": "Continuity", "scale": {"min": 1, "max": 5}},
    {"id": "appearance", "label": "Appearance", "scale": {"min": 1, "max": 5}},
]
EXPERIMENT = {
    "schema_version": 1,
    "experiment_id": "eval-test",
    "rubric": RUBRIC,
}
CASE_IDS = ["case-a", "case-b"]


def _payload(**overrides):
    base = {
        "schema_version": 1,
        "experiment_id": "eval-test",
        "reviewer": {"type": "human", "id": "peter"},
        "decisions": [
            {
                "case_id": "case-a",
                "scores": {"continuity": 3, "appearance": 4},
                "verdict": "iterate",
                "notes": "ok",
                "created": "2026-07-27T00:00:00Z",
            },
            {
                "case_id": "case-b",
                "scores": {"continuity": 2, "appearance": 5},
                "verdict": "ship",
                "notes": "",
                "created": "2026-07-27T00:00:00Z",
            },
        ],
    }
    base.update(overrides)
    return base


class TestRubricResponseSchema:
    def test_schema_has_required_shape(self):
        schema = build_rubric_response_schema(EXPERIMENT, case_ids=CASE_IDS)
        assert schema["type"] == "object"
        assert "decisions" in schema["required"]
        decision_item = schema["properties"]["decisions"]["items"]
        assert "case_id" in decision_item["required"]
        scores = decision_item["properties"]["scores"]["properties"]
        assert set(scores) == {"continuity", "appearance"}
        assert scores["continuity"]["minimum"] == 1
        assert scores["continuity"]["maximum"] == 5

    def test_schema_pins_experiment_id_const(self):
        schema = build_rubric_response_schema(EXPERIMENT, case_ids=CASE_IDS)
        assert schema["properties"]["experiment_id"]["const"] == "eval-test"

    def test_schema_enforces_case_id_enum_and_exact_set(self):
        schema = build_rubric_response_schema(EXPERIMENT, case_ids=CASE_IDS)
        decisions = schema["properties"]["decisions"]
        item_case_id = decisions["items"]["properties"]["case_id"]
        assert item_case_id["enum"] == ["case-a", "case-b"]
        # Exactly one decision per included case.
        assert decisions["minItems"] == 2
        assert decisions["maxItems"] == 2
        contains_ids = {
            sub["contains"]["properties"]["case_id"]["const"]
            for sub in decisions["allOf"]
        }
        assert contains_ids == {"case-a", "case-b"}

    def test_schema_without_case_ids_has_no_case_enforcement(self):
        schema = build_rubric_response_schema(EXPERIMENT)
        decisions = schema["properties"]["decisions"]
        assert "minItems" not in decisions
        assert "maxItems" not in decisions
        assert "allOf" not in decisions
        item_case_id = decisions["items"]["properties"]["case_id"]
        assert "enum" not in item_case_id


class TestSchemaRejectsBadPayloads:
    """The schema itself (server-side /submit first line of defense)."""

    def _schema(self):
        return build_rubric_response_schema(EXPERIMENT, case_ids=CASE_IDS)

    def _valid(self):
        return _payload()

    def _validate(self, payload):
        import jsonschema

        jsonschema.Draft7Validator(self._schema()).validate(payload)

    def test_valid_payload_passes_schema(self):
        self._validate(self._valid())  # no exception

    def test_wrong_experiment_id_rejected(self):
        import jsonschema

        bad = self._valid()
        bad["experiment_id"] = "not-eval-test"
        with pytest.raises(jsonschema.ValidationError):
            self._validate(bad)

    def test_unknown_case_id_rejected(self):
        import jsonschema

        bad = self._valid()
        bad["decisions"][0]["case_id"] = "not-a-case"
        with pytest.raises(jsonschema.ValidationError):
            self._validate(bad)

    def test_duplicate_case_rejected(self):
        import jsonschema

        bad = self._valid()
        # Duplicate case-a, dropping case-b → wrong set + duplicate.
        bad["decisions"][1]["case_id"] = "case-a"
        with pytest.raises(jsonschema.ValidationError):
            self._validate(bad)

    def test_missing_case_rejected(self):
        import jsonschema

        bad = self._valid()
        bad["decisions"] = bad["decisions"][:1]  # drop case-b
        with pytest.raises(jsonschema.ValidationError):
            self._validate(bad)

    def test_extra_case_rejected(self):
        import jsonschema

        bad = self._valid()
        bad["decisions"].append(dict(bad["decisions"][0]))  # 3 decisions
        with pytest.raises(jsonschema.ValidationError):
            self._validate(bad)


class TestValidateReviewFinal:
    def test_valid_payload_passes(self):
        result = validate_review_final(_payload(), experiment=EXPERIMENT, case_ids=CASE_IDS)
        assert result["experiment_id"] == "eval-test"
        assert result["reviewer"]["id"] == "peter"

    def test_legacy_review_decisions_key_is_rejected(self):
        payload = _payload()
        payload["review_decisions"] = payload.pop("decisions")
        with pytest.raises(ExperimentValidationError, match="decisions list"):
            validate_review_final(payload, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_score_below_minimum_rejected(self):
        p = _payload()
        p["decisions"][0]["scores"]["continuity"] = 0
        with pytest.raises(ExperimentValidationError, match="below minimum"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_score_above_maximum_rejected(self):
        p = _payload()
        p["decisions"][0]["scores"]["continuity"] = 6
        with pytest.raises(ExperimentValidationError, match="above maximum"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_unknown_case_rejected(self):
        p = _payload()
        p["decisions"][0]["case_id"] = "not-a-case"
        with pytest.raises(ExperimentValidationError, match="unknown case_id"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_duplicate_case_rejected(self):
        p = _payload()
        p["decisions"].append(dict(p["decisions"][0]))
        with pytest.raises(ExperimentValidationError, match="duplicates case_id"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_missing_case_rejected(self):
        p = _payload()
        p["decisions"] = p["decisions"][:1]  # drop case-b
        with pytest.raises(ExperimentValidationError, match="missing decisions"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_extra_case_rejected(self):
        p = _payload()
        p["decisions"].append(dict(p["decisions"][0]))  # duplicate → 3 decisions
        with pytest.raises(ExperimentValidationError, match="duplicates case_id"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_missing_rubric_score_rejected(self):
        p = _payload()
        del p["decisions"][0]["scores"]["appearance"]
        with pytest.raises(ExperimentValidationError, match="missing rubric score"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_unknown_rubric_score_rejected(self):
        p = _payload()
        p["decisions"][0]["scores"]["bogus"] = 3
        with pytest.raises(ExperimentValidationError, match="unknown rubric scores"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_missing_reviewer_rejected(self):
        p = _payload()
        del p["reviewer"]
        with pytest.raises(ExperimentValidationError, match="reviewer"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_empty_reviewer_id_rejected(self):
        p = _payload()
        p["reviewer"] = {"type": "human", "id": ""}
        with pytest.raises(ExperimentValidationError, match="reviewer.id"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_empty_decisions_rejected(self):
        p = _payload(decisions=[])
        with pytest.raises(ExperimentValidationError, match="at least one decision"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_non_integer_score_rejected(self):
        p = _payload()
        p["decisions"][0]["scores"]["continuity"] = 3.5
        with pytest.raises(ExperimentValidationError, match="must be an integer"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_boolean_schema_version_rejected(self):
        p = _payload(schema_version=True)
        with pytest.raises(ExperimentValidationError, match="schema_version"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    @pytest.mark.parametrize("decisions", [{}, "", False, 0])
    def test_falsey_wrong_decisions_collection_rejected(self, decisions):
        p = _payload(decisions=decisions)
        with pytest.raises(ExperimentValidationError, match="decisions must be a list"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_non_object_decision_rejected_without_filtering(self):
        p = _payload(decisions=[None, *_payload()["decisions"][1:]])
        with pytest.raises(ExperimentValidationError, match="only objects"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    @pytest.mark.parametrize(
        "created",
        ["", "not-a-timestamp", "2026-07-27T00:00:00"],
    )
    def test_decision_created_must_be_timezone_aware_iso8601(self, created):
        p = _payload()
        p["decisions"][0]["created"] = created
        with pytest.raises(ExperimentValidationError, match="created"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)


class TestBuildReviewFinalRoundTrip:
    """Phase 2 exit: scores and notes survive a build→validate round trip
    (the in-process analogue of 'draft reload + final validation')."""

    def test_build_then_validate(self):
        decisions = [
            {
                "case_id": "case-a",
                "scores": {"continuity": 2, "appearance": 5},
                "verdict": "ship",
                "notes": "great",
                "created": "2026-07-27T00:00:00Z",
            },
            {
                "case_id": "case-b",
                "scores": {"continuity": 4, "appearance": 3},
                "verdict": "iterate",
                "notes": "ok",
                "created": "2026-07-27T00:00:00Z",
            },
        ]
        payload = build_review_final(
            experiment=EXPERIMENT,
            reviewer={"type": "human", "id": "peter"},
            decisions=decisions,
            created="2026-07-27T00:00:00Z",
            notes="session note",
        )
        # Reload from serialized form (simulating draft persistence).
        import json

        reloaded = json.loads(json.dumps(payload))
        result = validate_review_final(reloaded, experiment=EXPERIMENT, case_ids=CASE_IDS)
        assert result["decisions"][0]["scores"]["appearance"] == 5
        assert result["notes"] == "session note"


class TestValidateConclusions:
    def _good(self):
        return {
            "schema_version": 1,
            "experiment_id": "eval-test",
            "observations": [
                {
                    "id": "obs-1",
                    "type": "observation",
                    "claim": "The request was rejected.",
                    "evidence": [{"case_id": "case-a", "kind": "provider_response"}],
                }
            ],
            "inferences": [
                {
                    "id": "inf-1",
                    "type": "inference",
                    "claim": "Route rejects mixed media.",
                    "evidence_ids": ["obs-1"],
                    "confidence": "medium",
                }
            ],
            "decisions": [
                {"id": "dec-1", "type": "decision", "claim": "Use composite.", "based_on": ["inf-1"]}
            ],
        }

    def test_valid_conclusions(self):
        result = validate_conclusions(self._good(), case_ids=CASE_IDS)
        assert len(result["observations"]) == 1

    def test_inference_dangling_evidence_rejected(self):
        bad = self._good()
        bad["inferences"][0]["evidence_ids"] = ["nonexistent"]
        with pytest.raises(ExperimentValidationError, match="evidence integrity"):
            validate_conclusions(bad, case_ids=CASE_IDS)

    def test_observation_unknown_case_rejected(self):
        bad = self._good()
        bad["observations"][0]["evidence"][0]["case_id"] = "no-such-case"
        with pytest.raises(ExperimentValidationError, match="unknown case_id"):
            validate_conclusions(bad, case_ids=CASE_IDS)

    def test_bad_schema_version_rejected(self):
        bad = self._good()
        bad["schema_version"] = 2
        with pytest.raises(ExperimentValidationError, match="schema_version"):
            validate_conclusions(bad)

    def test_boolean_schema_version_rejected(self):
        bad = self._good()
        bad["schema_version"] = True
        with pytest.raises(ExperimentValidationError, match="schema_version"):
            validate_conclusions(bad)

    @pytest.mark.parametrize("field", ["observations", "inferences", "decisions"])
    @pytest.mark.parametrize("wrong_type", ["", {}, False, 0])
    def test_falsey_wrong_collection_types_rejected(self, field, wrong_type):
        bad = self._good()
        bad[field] = wrong_type
        with pytest.raises(ExperimentValidationError, match=field):
            validate_conclusions(bad, case_ids=CASE_IDS)

    def test_empty_inference_evidence_rejected(self):
        bad = self._good()
        bad["inferences"][0]["evidence_ids"] = []
        with pytest.raises(ExperimentValidationError, match="at least one"):
            validate_conclusions(bad, case_ids=CASE_IDS)

    def test_numeric_inference_evidence_reference_rejected(self):
        bad = self._good()
        bad["inferences"][0]["evidence_ids"] = [123]
        with pytest.raises(ExperimentValidationError, match="string claim id"):
            validate_conclusions(bad, case_ids=CASE_IDS)

    def test_numeric_decision_reference_rejected(self):
        bad = self._good()
        bad["decisions"][0]["based_on"] = [123]
        with pytest.raises(ExperimentValidationError, match="string claim id"):
            validate_conclusions(bad, case_ids=CASE_IDS)

    def test_inference_cannot_be_supported_by_an_inference(self):
        bad = self._good()
        bad["inferences"].append({
            "id": "inf-2",
            "type": "inference",
            "claim": "Second inference.",
            "evidence_ids": ["inf-1"],
            "confidence": "medium",
        })
        with pytest.raises(ExperimentValidationError, match="unsupported claim kind"):
            validate_conclusions(bad, case_ids=CASE_IDS)

    def test_inference_cannot_use_itself_as_evidence(self):
        bad = self._good()
        bad["inferences"][0]["evidence_ids"] = ["inf-1"]
        with pytest.raises(ExperimentValidationError, match="itself"):
            validate_conclusions(bad, case_ids=CASE_IDS)

    def test_decision_cannot_be_supported_by_another_decision(self):
        bad = self._good()
        bad["decisions"].append({
            "id": "dec-2",
            "type": "decision",
            "claim": "Second decision.",
            "based_on": ["dec-1"],
        })
        with pytest.raises(ExperimentValidationError, match="decisions cannot support"):
            validate_conclusions(bad, case_ids=CASE_IDS)

    def test_malformed_claim_shape_rejected(self):
        bad = self._good()
        bad["observations"][0].pop("type")
        with pytest.raises(ExperimentValidationError, match="record validation"):
            validate_conclusions(bad, case_ids=CASE_IDS)

    def test_cross_kind_id_collision_rejected(self):
        bad = self._good()
        bad["inferences"][0]["id"] = "obs-1"
        with pytest.raises(ExperimentValidationError, match="share id"):
            validate_conclusions(bad, case_ids=CASE_IDS)

    def test_decision_cannot_support_itself(self):
        bad = self._good()
        bad["decisions"][0]["based_on"] = ["dec-1"]
        with pytest.raises(ExperimentValidationError, match="itself"):
            validate_conclusions(bad, case_ids=CASE_IDS)


# ── Gate-G2 §3: empty expected case set permits exactly zero decisions ─────


class TestEmptyCaseSet:
    def test_schema_permits_exactly_zero_decisions(self):
        schema = build_rubric_response_schema(EXPERIMENT, case_ids=[])
        decisions = schema["properties"]["decisions"]
        assert decisions["minItems"] == 0
        assert decisions["maxItems"] == 0

    def test_schema_rejects_any_decision_for_empty_set(self):
        import jsonschema

        schema = build_rubric_response_schema(EXPERIMENT, case_ids=[])
        payload = {
            "schema_version": 1,
            "experiment_id": "eval-test",
            "reviewer": {"type": "human", "id": "p"},
            "decisions": [
                {"case_id": "case-a", "scores": {"continuity": 3, "appearance": 4},
                 "verdict": "x", "created": "t"}
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.Draft7Validator(schema).validate(payload)

    def test_validate_review_final_accepts_zero_decisions_for_empty_set(self):
        payload = {
            "schema_version": 1,
            "experiment_id": "eval-test",
            "reviewer": {"type": "human", "id": "p"},
            "decisions": [],
        }
        result = validate_review_final(payload, experiment=EXPERIMENT, case_ids=[])
        assert result["decisions"] == []

    def test_validate_review_final_rejects_decision_for_empty_set(self):
        payload = {
            "schema_version": 1,
            "experiment_id": "eval-test",
            "reviewer": {"type": "human", "id": "p"},
            "decisions": [
                {"case_id": "case-a", "scores": {"continuity": 3, "appearance": 4},
                 "verdict": "x", "created": "t"}
            ],
        }
        with pytest.raises(ExperimentValidationError, match="unknown case_id"):
            validate_review_final(payload, experiment=EXPERIMENT, case_ids=[])


# ── Gate-G2 §2: experiment identity enforcement ────────────────────────────


class TestExperimentIdentityEnforcement:
    def test_review_final_wrong_experiment_rejected(self):
        p = _payload()
        p["experiment_id"] = "other-experiment"
        with pytest.raises(ExperimentValidationError, match="does not match experiment"):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_review_final_malformed_experiment_id_rejected(self):
        p = _payload()
        p["experiment_id"] = "Bad ID!"
        with pytest.raises(ExperimentValidationError):
            validate_review_final(p, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_conclusions_wrong_experiment_rejected(self):
        bad = {
            "schema_version": 1,
            "experiment_id": "other-experiment",
            "observations": [],
            "inferences": [],
            "decisions": [],
        }
        with pytest.raises(ExperimentValidationError, match="does not match experiment"):
            validate_conclusions(bad, experiment=EXPERIMENT, case_ids=CASE_IDS)

    def test_conclusions_accepts_expected_id_directly(self):
        good = {
            "schema_version": 1,
            "experiment_id": "eval-test",
            "observations": [],
            "inferences": [],
            "decisions": [],
        }
        result = validate_conclusions(good, experiment_id="eval-test")
        assert result["experiment_id"] == "eval-test"
