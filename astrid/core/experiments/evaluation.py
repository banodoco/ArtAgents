"""Structured rubric evaluation and epistemic-record (claims) helpers.

This module is provider-independent.  It produces the JSON Schema used to
validate human-review ``/submit`` payloads for an experiment, validates the
final evaluation artifact (``review.final.json``), and validates the separate
``conclusions.json`` artifact that holds observations, inferences, and
decisions.

Design rules honoured here:

- Scores are validated against each rubric dimension's declared scale.
- Reviewer identity and type are required and recorded with timestamps.
- The final payload never rewrites execution evidence; it is a separate
  mutable artifact alongside the immutable normalized review.
- Observations, inferences, and decisions are validated for cross-reference
  integrity (delegated to :mod:`astrid.core.experiments.evidence`).
- No provider execution logic, secrets, or signed URLs are accepted.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from astrid.core.experiments.evidence import (
    check_claim_id_collision,
    validate_evidence_integrity,
)
from astrid.core.experiments.schema import (
    ExperimentValidationError,
    validate_decision,
    validate_experiment_id,
    validate_inference,
    validate_observation,
    validate_review_decision,
)


def _expected_experiment_id(
    *, experiment: Mapping[str, Any] | None, experiment_id: str | None
) -> str | None:
    """Resolve the expected experiment id from an experiment doc or explicit id."""
    if isinstance(experiment_id, str) and experiment_id:
        return experiment_id
    if isinstance(experiment, Mapping):
        candidate = experiment.get("experiment_id")
        if isinstance(candidate, str) and candidate:
            return candidate
    return None

# Verdict vocabulary for rubric review decisions.  Open-but-curated: the
# HTML client may offer these as quick picks, but any non-empty string is
# accepted so reviewers are not forced into a false choice.
_VERDICT_SENTINEL = object()


def _rubric_index(rubric: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(r["id"]): r for r in rubric if isinstance(r, Mapping) and "id" in r}


def build_rubric_response_schema(
    experiment: Mapping[str, Any],
    *,
    case_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a draft-07 JSON Schema for the experiment review ``/submit`` payload.

    The schema constrains:

    - ``schema_version`` (integer, fixed at 1)
    - ``experiment_id`` (``const`` equal to this experiment's id)
    - ``reviewer`` object with ``type`` and ``id`` strings
    - ``decisions`` array, one per included case, each with rubric scores
      bounded by each dimension's ``scale.min`` / ``scale.max``

    When ``case_ids`` is supplied (the included case set), the schema *also*
    enforces the complete case set statically, so a bad payload is rejected by
    the server before it is written or finalized:

    - each decision ``case_id`` must be one of the included ids (``enum``)
    - exactly ``len(case_ids)`` decisions (``minItems`` / ``maxItems``)
    - exactly one decision per included case (one ``contains`` constraint per
      case id); combined with the item count this forces a permutation of the
      included set, so a missing, duplicate, or extra case all fail.

    When ``case_ids`` is omitted the schema cannot enforce membership and
    :func:`validate_review_final` is the line of defense instead.
    """
    rubric = experiment.get("rubric", []) if isinstance(experiment, Mapping) else []
    rubric = [r for r in rubric if isinstance(r, Mapping)]
    score_properties: dict[str, Any] = {}
    score_required: list[str] = []
    for dim in rubric:
        did = str(dim["id"])
        scale = dim.get("scale", {}) if isinstance(dim.get("scale"), Mapping) else {}
        mn = scale.get("min")
        mx = scale.get("max")
        prop: dict[str, Any] = {"type": "integer"}
        if isinstance(mn, int):
            prop["minimum"] = mn
        if isinstance(mx, int):
            prop["maximum"] = mx
        score_properties[did] = prop
        score_required.append(did)

    included = [str(c) for c in case_ids] if case_ids is not None else None
    case_id_prop: dict[str, Any]
    if included is not None:
        case_id_prop = {"type": "string", "enum": included}
    else:
        case_id_prop = {"type": "string", "minLength": 1}

    decision_properties = {
        "case_id": case_id_prop,
        "scores": {
            "type": "object",
            "properties": score_properties,
            "required": score_required,
            "additionalProperties": False,
        },
        "verdict": {"type": "string", "minLength": 1},
        "notes": {"type": ["string", "null"]},
        "created": {"type": "string", "minLength": 1, "format": "date-time"},
    }
    decision_required = ["case_id", "scores", "verdict", "created"]

    decisions_schema: dict[str, Any] = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": decision_properties,
            "required": decision_required,
            "additionalProperties": True,
        },
    }
    if included is not None:
        # Exactly one decision per included case. minItems == maxItems pins
        # the count; one `contains` per case forces each id to appear at least
        # once, so together they require an exact permutation of the set.
        # An empty expected set enforces exactly zero decisions (minItems ==
        # maxItems == 0): the library permits an empty review, while the
        # interactive session fails earlier with an actionable error.
        decisions_schema["minItems"] = len(included)
        decisions_schema["maxItems"] = len(included)
        decisions_schema["allOf"] = [
            {
                "contains": {
                    "type": "object",
                    "required": ["case_id"],
                    "properties": {"case_id": {"const": cid}},
                }
            }
            for cid in included
        ]

    experiment_id_prop: dict[str, Any]
    eid = experiment.get("experiment_id") if isinstance(experiment, Mapping) else None
    if isinstance(eid, str) and eid:
        experiment_id_prop = {"type": "string", "const": eid}
    else:
        experiment_id_prop = {"type": "string", "minLength": 1}

    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "additionalProperties": True,
        "required": ["schema_version", "experiment_id", "reviewer", "decisions"],
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "experiment_id": experiment_id_prop,
            "reviewer": {
                "type": "object",
                "required": ["type", "id"],
                "properties": {
                    "type": {"type": "string", "minLength": 1},
                    "id": {"type": "string", "minLength": 1},
                },
                "additionalProperties": True,
            },
            "decisions": decisions_schema,
            "observations": {"type": "array"},
            "inferences": {"type": "array"},
            "decisions_claim": {"type": "array"},
            "notes": {"type": ["string", "null"]},
        },
    }


def _coerce_decisions(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return the rubric decisions list, tolerating legacy 'review_decisions'."""
    if "decisions" in payload:
        decisions = payload["decisions"]
    elif "review_decisions" in payload:
        decisions = payload["review_decisions"]
    else:
        raise ExperimentValidationError(
            "review.final must include a decisions list"
        )
    if not isinstance(decisions, list):
        raise ExperimentValidationError("review.final decisions must be a list")
    if not all(isinstance(d, Mapping) for d in decisions):
        raise ExperimentValidationError(
            "review.final decisions must contain only objects"
        )
    return [dict(d) for d in decisions]


def validate_review_final(
    payload: Mapping[str, Any],
    *,
    experiment: Mapping[str, Any],
    case_ids: Sequence[str],
) -> dict[str, Any]:
    """Validate a final review payload against the experiment rubric.

    Raises :class:`ExperimentValidationError` on any violation.  Returns a
    normalized deep copy (unknown additive fields preserved).
    """
    if not isinstance(payload, Mapping):
        raise ExperimentValidationError("review.final must be an object")

    result = dict(payload)
    if (
        not isinstance(result.get("schema_version"), int)
        or isinstance(result.get("schema_version"), bool)
        or result["schema_version"] != 1
    ):
        raise ExperimentValidationError("review.final schema_version must be 1")
    eid = result.get("experiment_id")
    if not isinstance(eid, str) or not eid.strip():
        raise ExperimentValidationError("review.final must include experiment_id")
    # Canonical syntax — a malformed id can never match a real experiment.
    validate_experiment_id(eid)
    # Exact identity: the final payload must be for THIS experiment, never a
    # cross-experiment artifact rendered or embedded alongside another review.
    expected_eid = _expected_experiment_id(
        experiment=experiment, experiment_id=None
    )
    if isinstance(expected_eid, str) and expected_eid and eid != expected_eid:
        raise ExperimentValidationError(
            f"review.final experiment_id {eid!r} does not match experiment {expected_eid!r}"
        )

    reviewer = result.get("reviewer")
    if not isinstance(reviewer, Mapping):
        raise ExperimentValidationError("review.final must include a reviewer object")
    if not isinstance(reviewer.get("type"), str) or not reviewer["type"].strip():
        raise ExperimentValidationError("reviewer.type must be a non-empty string")
    if not isinstance(reviewer.get("id"), str) or not reviewer["id"].strip():
        raise ExperimentValidationError("reviewer.id must be a non-empty string")

    rubric = experiment.get("rubric", []) if isinstance(experiment, Mapping) else []
    rubric = [r for r in rubric if isinstance(r, Mapping)]
    allowed_case_ids = set(case_ids)

    decisions = _coerce_decisions(result)
    if not decisions and allowed_case_ids:
        raise ExperimentValidationError("review.final must include at least one decision")

    seen_cases: set[str] = set()
    for idx, dec in enumerate(decisions):
        case_id = dec.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ExperimentValidationError(f"decision[{idx}] missing case_id")
        if case_id not in allowed_case_ids:
            raise ExperimentValidationError(
                f"decision[{idx}] references unknown case_id {case_id!r}"
            )
        if case_id in seen_cases:
            raise ExperimentValidationError(
                f"decision[{idx}] duplicates case_id {case_id!r}"
            )
        seen_cases.add(case_id)

        scores = dec.get("scores")
        if not isinstance(scores, Mapping):
            raise ExperimentValidationError(
                f"decision[{idx}] for {case_id!r} missing scores object"
            )
        for dim in rubric:
            did = str(dim["id"])
            if did not in scores:
                raise ExperimentValidationError(
                    f"decision[{idx}] for {case_id!r} missing rubric score {did!r}"
                )
            value = scores[did]
            scale = dim.get("scale", {}) if isinstance(dim.get("scale"), Mapping) else {}
            mn = scale.get("min")
            mx = scale.get("max")
            if not isinstance(value, int) or isinstance(value, bool):
                raise ExperimentValidationError(
                    f"decision[{idx}] score {did!r} must be an integer"
                )
            if isinstance(mn, int) and value < mn:
                raise ExperimentValidationError(
                    f"decision[{idx}] score {did!r}={value} below minimum {mn}"
                )
            if isinstance(mx, int) and value > mx:
                raise ExperimentValidationError(
                    f"decision[{idx}] score {did!r}={value} above maximum {mx}"
                )
        unknown_scores = set(scores) - {str(r["id"]) for r in rubric}
        if unknown_scores:
            raise ExperimentValidationError(
                f"decision[{idx}] for {case_id!r} has unknown rubric scores: "
                f"{sorted(unknown_scores)}"
            )

        verdict = dec.get("verdict")
        if not isinstance(verdict, str) or not verdict.strip():
            raise ExperimentValidationError(
                f"decision[{idx}] for {case_id!r} missing verdict"
            )
        created = dec.get("created")
        if not isinstance(created, str) or not created.strip():
            raise ExperimentValidationError(
                f"decision[{idx}] for {case_id!r} missing created timestamp"
            )
        try:
            parsed_created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ExperimentValidationError(
                f"decision[{idx}] created must be an ISO-8601 timestamp"
            ) from exc
        if parsed_created.tzinfo is None:
            raise ExperimentValidationError(
                f"decision[{idx}] created must include a timezone"
            )
        # Reuse the schema-level review-decision validator for structural checks
        # (reviewer presence, created timestamp shape) without re-implementing.
        validate_review_decision(
            {
                "case_id": case_id,
                "reviewer": reviewer,
                "scores": dict(scores),
                "verdict": verdict,
                "created": dec.get("created") or "",
            }
        )

    # Exact-set enforcement (second line of defense behind the JSON Schema):
    # exactly one decision for every included case — no missing, no extra.
    missing = sorted(allowed_case_ids - seen_cases)
    if missing:
        raise ExperimentValidationError(
            f"review.final missing decisions for case_id(s): {missing}"
        )
    if len(decisions) != len(allowed_case_ids):
        raise ExperimentValidationError(
            f"review.final has {len(decisions)} decisions but "
            f"{len(allowed_case_ids)} cases are included"
        )

    result["decisions"] = decisions
    return result


def build_review_final(
    *,
    experiment: Mapping[str, Any],
    reviewer: Mapping[str, Any],
    decisions: Sequence[Mapping[str, Any]],
    created: str,
    notes: str | None = None,
) -> dict[str, Any]:
    """Assemble a review.final.json dict (used by tests and the session)."""
    payload: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": experiment["experiment_id"],
        "reviewer": dict(reviewer),
        "decisions": [dict(d) for d in decisions],
        "created": created,
    }
    if notes is not None:
        payload["notes"] = notes
    return payload


def validate_conclusions(
    payload: Mapping[str, Any],
    *,
    case_ids: Sequence[str] | None = None,
    experiment: Mapping[str, Any] | None = None,
    experiment_id: str | None = None,
) -> dict[str, Any]:
    """Validate a conclusions.json artifact.

    A conclusions artifact holds the mutable epistemic records — observations,
    inferences, and decisions — that are *separate* from both the immutable
    normalized review and the rubric ``review.final.json``.  Cross-reference
    integrity is enforced; evidence references to case ids are checked when a
    known case-id set is supplied.

    When *experiment* (or an explicit *experiment_id*) is supplied, the
    payload's ``experiment_id`` must match exactly — a cross-experiment
    conclusions artifact is never embedded alongside another review.
    """
    if not isinstance(payload, Mapping):
        raise ExperimentValidationError("conclusions must be an object")
    result = dict(payload)
    if (
        not isinstance(result.get("schema_version"), int)
        or isinstance(result.get("schema_version"), bool)
        or result["schema_version"] != 1
    ):
        raise ExperimentValidationError("conclusions schema_version must be 1")
    eid = result.get("experiment_id")
    if not isinstance(eid, str) or not eid.strip():
        raise ExperimentValidationError("conclusions must include experiment_id")
    validate_experiment_id(eid)
    expected_eid = _expected_experiment_id(experiment=experiment, experiment_id=experiment_id)
    if isinstance(expected_eid, str) and expected_eid and eid != expected_eid:
        raise ExperimentValidationError(
            f"conclusions experiment_id {eid!r} does not match experiment {expected_eid!r}"
        )

    observations = result.get("observations", [])
    inferences = result.get("inferences", [])
    decisions = result.get("decisions", [])
    for key, seq in (
        ("observations", observations),
        ("inferences", inferences),
        ("decisions", decisions),
    ):
        if not isinstance(seq, list):
            raise ExperimentValidationError(f"conclusions.{key} must be a list")
    try:
        observations = [validate_observation(item) for item in observations]
        inferences = [validate_inference(item) for item in inferences]
        decisions = [validate_decision(item) for item in decisions]
    except ExperimentValidationError as exc:
        raise ExperimentValidationError(
            f"conclusions record validation failed: {exc}"
        ) from exc
    result["observations"] = observations
    result["inferences"] = inferences
    result["decisions"] = decisions

    issues = validate_evidence_integrity(
        observations=observations,
        inferences=inferences,
        decisions=decisions,
    )
    issues.extend(check_claim_id_collision(
        observations=observations,
        inferences=inferences,
        decisions=decisions,
    ))
    if issues:
        raise ExperimentValidationError(
            "conclusions evidence integrity failed: " + "; ".join(issues)
        )

    # Validate evidence case references when a known case set is supplied.
    if case_ids is not None:
        known = set(case_ids)
        for obs in observations:
            for ev in obs["evidence"]:
                cid = ev["case_id"]
                if cid not in known:
                    raise ExperimentValidationError(
                        f"observation {obs.get('id')!r} evidence references "
                        f"unknown case_id {cid!r}"
                    )

    return result


__all__ = [
    "build_review_final",
    "build_rubric_response_schema",
    "validate_conclusions",
    "validate_review_final",
]
