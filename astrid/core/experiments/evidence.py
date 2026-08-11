"""Evidence, observation, inference, and decision record helpers.

Provides validation, cross-referencing, and integrity checks for
epistemic records that sit alongside experiment review artifacts.

Key properties:
- Observations are distinct from inferences.
- Inferences must reference valid observation IDs.
- Decisions must reference valid inference or observation IDs.
- Confidence and status are validated against the defined vocabulary.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from astrid.core.experiments.schema import (
    ExperimentValidationError,
    validate_claim_id,
    validate_decision,
    validate_inference,
    validate_observation,
)


def validate_evidence_integrity(
    *,
    observations: Sequence[Mapping[str, Any]],
    inferences: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Validate cross-referencing integrity across epistemic records.

    Returns a list of issue descriptions. An empty list means all
    cross-references are valid.

    Checks:
    - Observation IDs are unique.
    - Inference IDs are unique.
    - Decision IDs are unique.
    - Inference evidence_ids reference valid observations.
    - Decision based_on references valid observations or inferences.
    """
    issues: list[str] = []

    obs_ids: set[str] = set()
    inf_ids: set[str] = set()
    dec_ids: set[str] = set()

    for obs in observations:
        oid = obs.get("id")
        if not isinstance(oid, str):
            issues.append("observation missing id")
            continue
        if oid in obs_ids:
            issues.append(f"duplicate observation id: {oid}")
        obs_ids.add(oid)

    for inf in inferences:
        iid = inf.get("id")
        if not isinstance(iid, str):
            issues.append("inference missing id")
            continue
        if iid in inf_ids:
            issues.append(f"duplicate inference id: {iid}")
        inf_ids.add(iid)

    for dec in decisions:
        did = dec.get("id")
        if not isinstance(did, str):
            issues.append("decision missing id")
            continue
        if did in dec_ids:
            issues.append(f"duplicate decision id: {did}")
        dec_ids.add(did)
    for inf in inferences:
        iid = inf.get("id")
        evidence_ids = inf.get("evidence_ids")
        if not isinstance(evidence_ids, list):
            issues.append(f"inference {iid}: evidence_ids must be a list")
            continue
        if not evidence_ids:
            issues.append(
                f"inference {iid}: evidence_ids must reference at least one observation"
            )
            continue
        seen_evidence: set[str] = set()
        for index, eid in enumerate(evidence_ids):
            if not isinstance(eid, str):
                issues.append(
                    f"inference {iid}: evidence_ids[{index}] must be a string claim id"
                )
                continue
            try:
                validate_claim_id(eid)
            except ExperimentValidationError:
                issues.append(
                    f"inference {iid}: evidence_ids[{index}] is a malformed claim id"
                )
                continue
            if eid in seen_evidence:
                issues.append(
                    f"inference {iid}: duplicate evidence id {eid!r}"
                )
                continue
            seen_evidence.add(eid)
            if eid == iid:
                issues.append(f"inference {iid}: cannot use itself as evidence")
            elif eid in obs_ids:
                continue
            elif eid in inf_ids or eid in dec_ids:
                issues.append(
                    f"inference {iid}: evidence {eid!r} has unsupported claim kind; "
                    "only observations may support an inference"
                )
            else:
                issues.append(
                    f"inference {iid}: evidence {eid!r} is not a valid observation id"
                )

    for dec in decisions:
        did = dec.get("id")
        based_on = dec.get("based_on")
        if not isinstance(based_on, list):
            issues.append(f"decision {did}: based_on must be a list")
            continue
        if not based_on:
            issues.append(
                f"decision {did}: based_on must reference at least one claim"
            )
            continue
        seen_support: set[str] = set()
        for index, bid in enumerate(based_on):
            if not isinstance(bid, str):
                issues.append(
                    f"decision {did}: based_on[{index}] must be a string claim id"
                )
                continue
            try:
                validate_claim_id(bid)
            except ExperimentValidationError:
                issues.append(
                    f"decision {did}: based_on[{index}] is a malformed claim id"
                )
                continue
            if bid in seen_support:
                issues.append(
                    f"decision {did}: duplicate based_on id {bid!r}"
                )
                continue
            seen_support.add(bid)
            if bid == did:
                issues.append(f"decision {did}: cannot be based on itself")
            elif bid in obs_ids or bid in inf_ids:
                continue
            elif bid in dec_ids:
                issues.append(
                    f"decision {did}: based_on {bid!r} has unsupported claim kind; "
                    "decisions cannot support decisions"
                )
            else:
                issues.append(
                    f"decision {did}: based_on {bid!r} does not reference "
                    "an observation or inference"
                )

    return issues


def check_claim_id_collision(
    *,
    observations: Sequence[Mapping[str, Any]],
    inferences: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Check for ID collisions across claim types."""
    issues: list[str] = []
    obs_ids = {
        o["id"] for o in observations if isinstance(o.get("id"), str)
    }
    inf_ids = {
        i["id"] for i in inferences if isinstance(i.get("id"), str)
    }
    dec_ids = {
        d["id"] for d in decisions if isinstance(d.get("id"), str)
    }

    for oid in obs_ids & inf_ids:
        issues.append(f"observation and inference share id: {oid}")
    for oid in obs_ids & dec_ids:
        issues.append(f"observation and decision share id: {oid}")
    for iid in inf_ids & dec_ids:
        issues.append(f"inference and decision share id: {iid}")

    return issues


def validate_claims_batch(
    claims: Sequence[Mapping[str, Any]],
) -> tuple[
    list[dict[str, Any]],  # valid observations
    list[dict[str, Any]],  # valid inferences
    list[dict[str, Any]],  # valid decisions
    list[str],  # issues
]:
    """Validate and classify a batch of claims records.

    Each claim is validated against its declared type and sorted into
    the appropriate output list. Validation issues are collected.
    """
    observations: list[dict[str, Any]] = []
    inferences: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    issues: list[str] = []

    for idx, claim in enumerate(claims):
        if not isinstance(claim, Mapping):
            issues.append(f"claim[{idx}]: not an object")
            continue

        claim_type = claim.get("type")
        if claim_type == "observation":
            try:
                observations.append(validate_observation(claim))
            except ExperimentValidationError as e:
                issues.append(f"observation[{idx}]: {e}")
        elif claim_type == "inference":
            try:
                inferences.append(validate_inference(claim))
            except ExperimentValidationError as e:
                issues.append(f"inference[{idx}]: {e}")
        elif claim_type == "decision":
            try:
                decisions.append(validate_decision(claim))
            except ExperimentValidationError as e:
                issues.append(f"decision[{idx}]: {e}")
        else:
            issues.append(f"claim[{idx}]: unknown type {claim_type!r}")

    # Cross-reference integrity
    issues.extend(
        validate_evidence_integrity(
            observations=observations,
            inferences=inferences,
            decisions=decisions,
        )
    )
    issues.extend(
        check_claim_id_collision(
            observations=observations,
            inferences=inferences,
            decisions=decisions,
        )
    )

    return observations, inferences, decisions, issues
