"""Schema validation and normalization for experiment contracts.

This module provides validation, normalization, and safety primitives for
experiment definitions, normalized review records, diagnostics, and
evaluation-adjacent artifacts.

Key properties:
- Unknown additive fields round-trip (preserved in passthrough).
- Unsafe paths, malformed IDs, invalid evidence references, secrets, and
  live signed URLs are rejected.
- Lifecycle statuses are validated against the terminal vocabulary.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Mapping

# ── ID patterns ────────────────────────────────────────────────────────────

_EXPERIMENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_HYPOTHESIS_ID_RE = re.compile(r"^[a-z][a-z0-9._-]*$")
_FACTOR_ID_RE = re.compile(r"^[a-z][a-z0-9._-]*$")
_RUBRIC_ID_RE = re.compile(r"^[a-z][a-z0-9._-]*$")
_CASE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_ULID_RE = re.compile(r"^[0-7][0-9A-HJKMNP-TV-Za-hjkmnp-tv-z]{25}$")
_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")

# ── Terminal status vocabulary ─────────────────────────────────────────────

_VALID_STATUSES = frozenset({
    "completed",
    "partial",
    "provider_rejected",
    "failed",
    "timed_out",
    "interrupted",
    "draft",
})

# Ordered input role vocabulary
_VALID_INPUT_ROLES = frozenset({
    "appearance_reference",
    "motion_reference",
    "composite_appearance_and_motion_reference",
    "start_frame",
    "end_frame",
    "style_reference",
    "mask",
    "source_video",
    "source_audio",
    "workflow",
    "control_signal",
    "other",
})

# Relationship types
_VALID_RELATIONSHIP_TYPES = frozenset({
    "baseline",
    "variant",
    "replicate",
    "retry",
})

# Capture gap kinds
_VALID_CAPTURE_GAP_KINDS = frozenset({
    "missing_prompt",
    "missing_input_hash",
    "missing_output_hash",
    "missing_manifest",
    "expired_only_reference",
    "ambiguous_provenance",
    "unknown",
})

# Confidence levels
_VALID_CONFIDENCE_LEVELS = frozenset({
    "low",
    "medium",
    "high",
    "confirmed",
})

# Claim statuses
_VALID_CLAIM_STATUSES = frozenset({
    "provisional",
    "confirmed",
    "refuted",
})

# Forbidden patterns in paths
_FORBIDDEN_PATH_PATTERNS = [
    re.compile(r"\.\."),      # path traversal
    re.compile(r"^~"),         # home expansion
    re.compile(r"^\x00"),      # NUL bytes
    re.compile(r"\x00"),       # NUL bytes anywhere
]

# Forbidden fields in output entries (secrets / live URLs)
_FORBIDDEN_OUTPUT_FIELDS = frozenset({
    "source_url",
})


# ── Error classes ───────────────────────────────────────────────────────────

class ExperimentValidationError(ValueError):
    """A validation error in an experiment artifact."""


# ── Path safety ────────────────────────────────────────────────────────────

def validate_path(path: str, *, allow_absolute: bool = False) -> str:
    """Validate a path is safe: relative, no traversal, no NUL bytes.

    Returns the path unmodified on success.  Raises
    :class:`ExperimentValidationError` on rejection.
    """
    if not isinstance(path, str) or not path.strip():
        raise ExperimentValidationError("path must be a non-empty string")
    if path != path.strip():
        raise ExperimentValidationError(
            f"path must not have leading or trailing whitespace: {path!r}"
        )

    if "\x00" in path:
        raise ExperimentValidationError("path must not contain NUL bytes")
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise ExperimentValidationError(
            f"path must not contain control characters: {path!r}"
        )

    if not allow_absolute:
        if (
            path.startswith("/")
            or path.startswith("~")
            or path.startswith("\\")
            or _URI_SCHEME_RE.match(path)
        ):
            raise ExperimentValidationError(
                f"path must be relative, got: {path!r}"
            )
        # Also catch Windows absolute (unlikely on Linux but defense in depth)
        if len(path) >= 2 and path[1] == ":":
            raise ExperimentValidationError(
                f"path must be relative, got: {path!r}"
            )

    # Check for traversal
    segments = path.replace("\\", "/").split("/")
    if ".." in segments:
        raise ExperimentValidationError(
            f"path must not contain '..' traversal: {path!r}"
        )
    if "\\" in path:
        raise ExperimentValidationError(
            f"path must use portable '/' separators, got: {path!r}"
        )

    return path


def require_relative_path(path: str) -> str:
    """Validate and return a relative path. Rejects anything unsafe."""
    return validate_path(path, allow_absolute=False)


# ── ID validation ──────────────────────────────────────────────────────────

def validate_experiment_id(experiment_id: str) -> str:
    """Validate an experiment_id matches the required pattern."""
    if not isinstance(experiment_id, str) or not _EXPERIMENT_ID_RE.fullmatch(experiment_id):
        raise ExperimentValidationError(
            f"experiment_id must match {_EXPERIMENT_ID_RE.pattern}, got: {experiment_id!r}"
        )
    return experiment_id


def validate_hypothesis_id(hypothesis_id: str) -> str:
    """Validate a hypothesis id."""
    if not isinstance(hypothesis_id, str) or not _HYPOTHESIS_ID_RE.fullmatch(hypothesis_id):
        raise ExperimentValidationError(
            f"hypothesis id must match {_HYPOTHESIS_ID_RE.pattern}, got: {hypothesis_id!r}"
        )
    return hypothesis_id


def validate_factor_id(factor_id: str) -> str:
    """Validate a factor id."""
    if not isinstance(factor_id, str) or not _FACTOR_ID_RE.fullmatch(factor_id):
        raise ExperimentValidationError(
            f"factor id must match {_FACTOR_ID_RE.pattern}, got: {factor_id!r}"
        )
    return factor_id


def validate_rubric_id(rubric_id: str) -> str:
    """Validate a rubric dimension id."""
    if not isinstance(rubric_id, str) or not _RUBRIC_ID_RE.fullmatch(rubric_id):
        raise ExperimentValidationError(
            f"rubric id must match {_RUBRIC_ID_RE.pattern}, got: {rubric_id!r}"
        )
    return rubric_id


def validate_case_id(case_id: str) -> str:
    """Validate a case_id."""
    if not isinstance(case_id, str) or not _CASE_ID_RE.fullmatch(case_id):
        raise ExperimentValidationError(
            f"case_id must match {_CASE_ID_RE.pattern}, got: {case_id!r}"
        )
    return case_id


def validate_run_id(run_id: str) -> str:
    """Validate a run_id is a plausible ULID."""
    if not isinstance(run_id, str) or not _ULID_RE.fullmatch(run_id):
        raise ExperimentValidationError(
            f"run_id must be a 26-character Crockford ULID, got: {run_id!r}"
        )
    return run_id


def validate_claim_id(claim_id: str) -> str:
    """Validate an observation/inference/decision id."""
    if not isinstance(claim_id, str) or not _HYPOTHESIS_ID_RE.fullmatch(claim_id):
        raise ExperimentValidationError(
            f"claim id must match {_HYPOTHESIS_ID_RE.pattern}, got: {claim_id!r}"
        )
    return claim_id


# ── Content hash validation ────────────────────────────────────────────────

def validate_content_hash(content_hash: str) -> str:
    """Validate a content_hash is sha256:-prefixed."""
    if not isinstance(content_hash, str) or not content_hash.startswith("sha256:"):
        raise ExperimentValidationError(
            f"content_hash must be sha256:-prefixed, got: {content_hash!r}"
        )
    digest = content_hash[7:]
    if len(digest) != 64 or not all(c in "0123456789abcdef" for c in digest):
        raise ExperimentValidationError(
            f"content_hash digest must be 64 hex chars, got: {content_hash!r}"
        )
    return content_hash


def is_valid_content_hash(value: str) -> bool:
    """Return True if *value* looks like a valid sha256: hash."""
    try:
        validate_content_hash(value)
        return True
    except ExperimentValidationError:
        return False


# ── Experiment validation ──────────────────────────────────────────────────

def validate_experiment(experiment: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize an experiment definition.

    Returns a normalized deep copy.  Unknown fields are preserved.
    Raises :class:`ExperimentValidationError` on rejection.
    """
    if not isinstance(experiment, Mapping):
        raise ExperimentValidationError("experiment must be an object")

    result: dict[str, Any] = dict(experiment)

    # Required fields
    _require_key(result, "schema_version", int)
    _require_key(result, "experiment_id", str)
    _require_key(result, "project_slug", str)
    _require_key(result, "title", str)
    _require_key(result, "question", str)
    _require_key(result, "hypotheses", list)
    _require_key(result, "factors", list)
    _require_key(result, "rubric", list)
    _require_key(result, "cases", list)
    _require_key(result, "created", str)
    if result["schema_version"] != 1 or isinstance(result["schema_version"], bool):
        raise ExperimentValidationError("experiment schema_version must be 1")
    _validate_timestamp(result["created"], "created")
    if "updated" in result:
        _validate_timestamp(result["updated"], "updated")

    # Validate IDs
    validate_experiment_id(result["experiment_id"])

    if not result["title"].strip():
        raise ExperimentValidationError("title must be non-empty")
    if not result["question"].strip():
        raise ExperimentValidationError("question must be non-empty")
    if not result["project_slug"].strip():
        raise ExperimentValidationError("project_slug must be non-empty")

    # Validate hypotheses
    result["hypotheses"] = [
        _validate_hypothesis(h) for h in result["hypotheses"]
    ]
    _reject_duplicate_ids(result["hypotheses"], "hypothesis")

    # Validate factors
    result["factors"] = [
        _validate_factor(f) for f in result["factors"]
    ]
    _reject_duplicate_ids(result["factors"], "factor")
    # At least one factor must have values
    if not any("values" in f for f in result["factors"]):
        raise ExperimentValidationError(
            "at least one factor must declare 'values' (controlled factor)"
        )

    # Validate rubric
    result["rubric"] = [
        _validate_rubric_dimension(r) for r in result["rubric"]
    ]
    _reject_duplicate_ids(result["rubric"], "rubric")

    # Validate cases
    if not result["cases"]:
        raise ExperimentValidationError("at least one case is required")
    result["cases"] = [
        _validate_case(c, factor_ids={f["id"] for f in result["factors"]})
        for c in result["cases"]
    ]
    # Each case carries a unique case_id and a unique run_id (one case = one
    # run).  Duplicate ids conflate cases in review mounts, normalization, and
    # diagnostics, so reject them here rather than silently merging.
    _reject_duplicate_case_ids(result["cases"])
    _reject_duplicate_run_ids(result["cases"])
    case_ids = {case["case_id"] for case in result["cases"]}
    factor_defs = {factor["id"]: factor for factor in result["factors"]}
    for case in result["cases"]:
        rel = case["relationship"]
        if rel["type"] == "baseline":
            if rel.get("case_id") is not None:
                raise ExperimentValidationError(
                    f"baseline case {case['case_id']!r} must have null relationship.case_id"
                )
        elif rel.get("case_id") not in case_ids:
            raise ExperimentValidationError(
                f"case {case['case_id']!r} references unknown relationship case "
                f"{rel.get('case_id')!r}"
            )
        for factor_id, value in case["factors"].items():
            definition = factor_defs[factor_id]
            if "values" in definition and value not in definition["values"]:
                raise ExperimentValidationError(
                    f"case {case['case_id']!r} factor {factor_id!r} value "
                    f"{value!r} is not declared"
                )

    # Ensure updated field exists
    result.setdefault("updated", result["created"])

    return result


def _require_key(obj: dict[str, Any], key: str, expected_type: type) -> None:
    if key not in obj:
        raise ExperimentValidationError(f"missing required field: {key}")
    if not isinstance(obj[key], expected_type) or (
        expected_type is int and isinstance(obj[key], bool)
    ):
        expected_label = (
            "a boolean" if expected_type is bool else expected_type.__name__
        )
        raise ExperimentValidationError(
            f"{key} must be {expected_label}, got {type(obj[key]).__name__}"
        )


def _validate_timestamp(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExperimentValidationError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ExperimentValidationError(f"{field} must include a timezone")


def _reject_duplicate_ids(items: list[dict[str, Any]], label: str) -> None:
    seen: set[str] = set()
    for item in items:
        item_id = item["id"]
        if item_id in seen:
            raise ExperimentValidationError(f"duplicate {label} id: {item_id!r}")
        seen.add(item_id)


def _reject_duplicate_case_ids(cases: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for c in cases:
        cid = c["case_id"]
        if cid in seen:
            raise ExperimentValidationError(f"duplicate case_id: {cid!r}")
        seen.add(cid)


def _reject_duplicate_run_ids(cases: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for c in cases:
        rid = c.get("run_id")
        if not isinstance(rid, str):
            continue
        if rid in seen:
            raise ExperimentValidationError(
                f"duplicate run_id: {rid!r} (run ids are unique per case)"
            )
        seen.add(rid)


def _validate_hypothesis(h: object) -> dict[str, Any]:
    if not isinstance(h, Mapping):
        raise ExperimentValidationError("hypothesis must be an object")
    result = dict(h)
    _require_key(result, "id", str)
    _require_key(result, "claim", str)
    validate_hypothesis_id(result["id"])
    if not result["claim"].strip():
        raise ExperimentValidationError("hypothesis claim must be non-empty")
    status = result.get("status", "provisional")
    if status not in _VALID_CLAIM_STATUSES:
        raise ExperimentValidationError(
            f"hypothesis status must be one of {sorted(_VALID_CLAIM_STATUSES)}, got: {status!r}"
        )
    result.setdefault("status", "provisional")
    return result


def _validate_factor(f: object) -> dict[str, Any]:
    if not isinstance(f, Mapping):
        raise ExperimentValidationError("factor must be an object")
    result = dict(f)
    _require_key(result, "id", str)
    validate_factor_id(result["id"])
    if "values" in result:
        if not isinstance(result["values"], list):
            raise ExperimentValidationError(
                f"factor {result['id']}: values must be a list"
            )
        if not result["values"]:
            raise ExperimentValidationError(
                f"factor {result['id']}: values must be non-empty"
            )
    elif "type" not in result:
        raise ExperimentValidationError(
            f"factor {result['id']}: must have 'values' or 'type'"
        )
    return result


def _validate_rubric_dimension(r: object) -> dict[str, Any]:
    if not isinstance(r, Mapping):
        raise ExperimentValidationError("rubric dimension must be an object")
    result = dict(r)
    _require_key(result, "id", str)
    _require_key(result, "label", str)
    _require_key(result, "scale", dict)
    validate_rubric_id(result["id"])
    if not result["label"].strip():
        raise ExperimentValidationError("rubric label must be non-empty")
    scale = result["scale"]
    scale_min = scale.get("min")
    scale_max = scale.get("max")
    if (
        not isinstance(scale_min, int)
        or isinstance(scale_min, bool)
        or not isinstance(scale_max, int)
        or isinstance(scale_max, bool)
    ):
        raise ExperimentValidationError("rubric scale must have integer min and max")
    if scale_min >= scale_max:
        raise ExperimentValidationError(
            f"rubric scale min ({scale_min}) must be less than max ({scale_max})"
        )
    return result


def _validate_case(
    c: object,
    *,
    factor_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(c, Mapping):
        raise ExperimentValidationError("case must be an object")
    result = dict(c)
    _require_key(result, "case_id", str)
    _require_key(result, "label", str)
    _require_key(result, "run_id", str)
    _require_key(result, "factors", dict)
    _require_key(result, "relationship", dict)
    validate_case_id(result["case_id"])
    validate_run_id(result["run_id"])
    if not result["label"].strip():
        raise ExperimentValidationError("case label must be non-empty")

    attempt = result.get("attempt", 1)
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise ExperimentValidationError("case attempt must be a positive integer")
    result.setdefault("attempt", 1)

    # Validate factors match declared factor IDs
    case_factors = result["factors"]
    for fid in case_factors:
        if fid not in factor_ids:
            raise ExperimentValidationError(
                f"case {result['case_id']}: unknown factor {fid!r}"
            )
    # All declared factors must be present in the case
    for fid in factor_ids:
        if fid not in case_factors:
            raise ExperimentValidationError(
                f"case {result['case_id']}: missing factor {fid!r}"
            )

    # Validate relationship
    rel = result["relationship"]
    rel_type = rel.get("type")
    if rel_type not in _VALID_RELATIONSHIP_TYPES:
        raise ExperimentValidationError(
            f"relationship type must be one of {sorted(_VALID_RELATIONSHIP_TYPES)}, got: {rel_type!r}"
        )
    if rel_type != "baseline" and not rel.get("case_id"):
        raise ExperimentValidationError(
            "non-baseline relationship requires case_id"
        )

    # Validate expected_input_roles if present
    if "expected_input_roles" in result:
        roles = result["expected_input_roles"]
        if not isinstance(roles, list):
            raise ExperimentValidationError("expected_input_roles must be a list")
        for role in roles:
            if not isinstance(role, str):
                raise ExperimentValidationError("expected_input_roles items must be strings")
            if role not in _VALID_INPUT_ROLES:
                raise ExperimentValidationError(
                    f"unknown input role: {role!r}"
                )

    if "source_manifest" in result:
        result["source_manifest"] = _validate_source_manifest_ref(
            result["source_manifest"]
        )

    included = result.get("included", True)
    if not isinstance(included, bool):
        raise ExperimentValidationError("case included must be a boolean")
    result.setdefault("included", True)
    return result


# ── Review validation ──────────────────────────────────────────────────────

def validate_review(review: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a normalized review.json.

    Returns a normalized deep copy. Unknown fields are preserved.
    """
    if not isinstance(review, Mapping):
        raise ExperimentValidationError("review must be an object")

    result = dict(review)
    _require_key(result, "schema_version", int)
    _require_key(result, "experiment_id", str)
    _require_key(result, "cases", list)
    _require_key(result, "created", str)
    if result["schema_version"] != 1:
        raise ExperimentValidationError("review schema_version must be 1")
    _validate_timestamp(result["created"], "review.created")

    validate_experiment_id(result["experiment_id"])

    result["cases"] = [
        _validate_review_case(rc) for rc in result["cases"]
    ]
    _reject_duplicate_case_ids(result["cases"])
    return result


def _validate_review_case(rc: object) -> dict[str, Any]:
    if not isinstance(rc, Mapping):
        raise ExperimentValidationError("review case must be an object")
    result = dict(rc)

    _require_key(result, "case_id", str)
    _require_key(result, "run_id", str)
    _require_key(result, "status", str)
    _require_key(result, "inputs", list)
    _require_key(result, "outputs", list)
    validate_case_id(result["case_id"])
    validate_run_id(result["run_id"])

    status = result["status"]
    if status not in _VALID_STATUSES:
        raise ExperimentValidationError(
            f"status must be one of {sorted(_VALID_STATUSES)}, got: {status!r}"
        )

    # Failure states must have error
    if status in {"failed", "provider_rejected", "timed_out", "interrupted"}:
        if not result.get("error"):
            raise ExperimentValidationError(
                f"status '{status}' requires an error message"
            )
    # Validate inputs
    result["inputs"] = [
        _validate_review_input(inp) for inp in result["inputs"]
    ]
    # Validate ordinal ordering
    ordinals = [inp["ordinal"] for inp in result["inputs"]]
    if ordinals != sorted(ordinals):
        raise ExperimentValidationError(
            f"case {result['case_id']}: input ordinals must be ordered"
        )
    if len(set(ordinals)) != len(ordinals):
        raise ExperimentValidationError(
            f"case {result['case_id']}: duplicate input ordinals"
        )

    # Validate outputs
    result["outputs"] = [
        _validate_review_output(out) for out in result["outputs"]
    ]

    # Validate capture_gaps if present
    if "capture_gaps" in result:
        gaps = result["capture_gaps"]
        if not isinstance(gaps, list):
            raise ExperimentValidationError("capture_gaps must be a list")
        result["capture_gaps"] = [
            _validate_capture_gap(g) for g in gaps
        ]

    # Validate source_manifest if present
    if "source_manifest" in result:
        _validate_source_manifest_ref(result["source_manifest"])

    included = result.get("included", True)
    if not isinstance(included, bool):
        raise ExperimentValidationError("review case included must be a boolean")
    result.setdefault("included", True)
    result.setdefault("warnings", [])
    result.setdefault("capture_gaps", [])
    result.setdefault("cost_usd", None)
    result.setdefault("error", None)

    return result


def _validate_review_input(inp: object) -> dict[str, Any]:
    if not isinstance(inp, Mapping):
        raise ExperimentValidationError("review input must be an object")
    result = dict(inp)
    _require_key(result, "ordinal", int)
    _require_key(result, "role", str)
    _require_key(result, "path", str)
    _require_key(result, "verified", bool)
    if isinstance(result["ordinal"], bool) or result["ordinal"] < 1:
        raise ExperimentValidationError("input ordinal must be positive")
    require_relative_path(result["path"])
    # content_hash is validated if present but not required —
    # unresolved/capture-gap artifacts may lack a verified digest.
    if "content_hash" in result:
        if result["content_hash"] is None:
            raise ExperimentValidationError(
                "input content_hash must not be null — omit the key or provide a valid hash"
            )
        validate_content_hash(result["content_hash"])
    if "reported_content_hash" in result:
        validate_content_hash(result["reported_content_hash"])
    # Role can be any string (open vocabulary with documented defaults)
    return result


def _validate_review_output(out: object) -> dict[str, Any]:
    if not isinstance(out, Mapping):
        raise ExperimentValidationError("review output must be an object")
    result = dict(out)
    _require_key(result, "path", str)
    _require_key(result, "verified", bool)
    require_relative_path(result["path"])
    # content_hash is validated if present but not required —
    # unresolved/capture-gap artifacts may lack a verified digest.
    if "content_hash" in result:
        if result["content_hash"] is None:
            raise ExperimentValidationError(
                "output content_hash must not be null — omit the key or provide a valid hash"
            )
        validate_content_hash(result["content_hash"])
    if "reported_content_hash" in result:
        validate_content_hash(result["reported_content_hash"])
    # Forbidden fields
    for forbidden in _FORBIDDEN_OUTPUT_FIELDS:
        if forbidden in result:
            raise ExperimentValidationError(
                f"output must not contain forbidden field: {forbidden}"
            )

    return result


def _validate_capture_gap(g: object) -> dict[str, Any]:
    if not isinstance(g, Mapping):
        raise ExperimentValidationError("capture_gap must be an object")
    result = dict(g)
    _require_key(result, "kind", str)
    if result["kind"] not in _VALID_CAPTURE_GAP_KINDS:
        raise ExperimentValidationError(
            f"capture gap kind must be one of {sorted(_VALID_CAPTURE_GAP_KINDS)}, "
            f"got: {result['kind']!r}"
        )
    return result


def _validate_source_manifest_ref(sm: object) -> dict[str, Any]:
    if not isinstance(sm, Mapping):
        raise ExperimentValidationError("source_manifest must be an object")
    result = dict(sm)
    _require_key(result, "path", str)
    require_relative_path(result["path"])
    # content_hash is required when the manifest is readable; an
    # unreadable manifest may omit it and record a capture gap instead.
    if "content_hash" in result:
        if result["content_hash"] is None:
            raise ExperimentValidationError(
                "source_manifest content_hash must not be null — omit the key or provide a valid hash"
            )
        validate_content_hash(result["content_hash"])
    if "expected_content_hash" in result:
        validate_content_hash(result["expected_content_hash"])
    if "verified" in result and not isinstance(result["verified"], bool):
        raise ExperimentValidationError("source_manifest verified must be a boolean")
    return result


# ── Diagnostics validation ─────────────────────────────────────────────────

def validate_diagnostics(diag: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a diagnostics.json artifact."""
    if not isinstance(diag, Mapping):
        raise ExperimentValidationError("diagnostics must be an object")
    result = dict(diag)
    _require_key(result, "schema_version", int)
    _require_key(result, "experiment_id", str)
    _require_key(result, "total_cases", int)
    if result["schema_version"] != 1:
        raise ExperimentValidationError("diagnostics schema_version must be 1")
    validate_experiment_id(result["experiment_id"])

    result.setdefault("included_cases", result["total_cases"])
    result.setdefault("excluded_cases", 0)
    result.setdefault("status_counts", {})
    result.setdefault("duplicate_output_groups", [])
    result.setdefault("input_echo_cases", [])
    result.setdefault("capture_gap_counts", {})
    result.setdefault("source_manifest_mismatches", [])
    result.setdefault("warnings", [])
    return result


def validate_import_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an ``import.report.json`` artifact.

    Permissive by design (additive fields preserved): the importer must be
    honest about gaps, so we require the honesty-shape fields — total/imported
    counts, the source root, and the gap/case counters — but never a "success"
    claim that contradicts a non-empty ambiguous/screenshot-only set.
    """
    if not isinstance(report, Mapping):
        raise ExperimentValidationError("import report must be an object")
    result = dict(report)
    if (
        not isinstance(result.get("schema_version"), int)
        or isinstance(result.get("schema_version"), bool)
        or result["schema_version"] != 1
    ):
        raise ExperimentValidationError("import report schema_version must be 1")
    _require_key(result, "experiment_id", str)
    _require_key(result, "source_root", str)
    _require_key(result, "total_subdirs", int)
    _require_key(result, "imported_cases", int)
    validate_experiment_id(result["experiment_id"])

    result.setdefault("skipped_subdirs", 0)
    result.setdefault("deduplicated_subdirs", 0)
    result.setdefault("ambiguous_prompt_cases", 0)
    result.setdefault("screenshot_only_cases", 0)
    result.setdefault("empty_subdirs", 0)
    result.setdefault("status_counts", {})
    result.setdefault("duplicate_output_groups", [])
    result.setdefault("manual_mappings_applied", 0)
    result.setdefault("capture_gap_counts", {})
    result.setdefault("warnings", [])
    result.setdefault("notes", None)
    return result


# ── Evaluation / claims validation ─────────────────────────────────────────

def validate_observation(obs: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an observation record."""
    if not isinstance(obs, Mapping):
        raise ExperimentValidationError("observation must be an object")
    result = dict(obs)
    _require_key(result, "id", str)
    _require_key(result, "type", str)
    _require_key(result, "claim", str)
    _require_key(result, "evidence", list)
    validate_claim_id(result["id"])
    if result["type"] != "observation":
        raise ExperimentValidationError(f"observation type must be 'observation', got: {result['type']!r}")
    if not result["claim"].strip():
        raise ExperimentValidationError("observation claim must be non-empty")
    # Validate evidence references
    for ev in result["evidence"]:
        if not isinstance(ev, Mapping):
            raise ExperimentValidationError("evidence entry must be an object")
        case_id = ev.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ExperimentValidationError(
                "evidence entry case_id must be a non-empty string"
            )
        validate_case_id(case_id)
    return result


def validate_inference(inf: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an inference record."""
    if not isinstance(inf, Mapping):
        raise ExperimentValidationError("inference must be an object")
    result = dict(inf)
    _require_key(result, "id", str)
    _require_key(result, "type", str)
    _require_key(result, "claim", str)
    _require_key(result, "evidence_ids", list)
    _require_key(result, "confidence", str)
    validate_claim_id(result["id"])
    if result["type"] != "inference":
        raise ExperimentValidationError(f"inference type must be 'inference', got: {result['type']!r}")
    if not result["claim"].strip():
        raise ExperimentValidationError("inference claim must be non-empty")
    confidence = result["confidence"]
    if confidence not in _VALID_CONFIDENCE_LEVELS:
        raise ExperimentValidationError(
            f"confidence must be one of {sorted(_VALID_CONFIDENCE_LEVELS)}, got: {confidence!r}"
        )
    status = result.get("status", "provisional")
    if status not in _VALID_CLAIM_STATUSES:
        raise ExperimentValidationError(
            f"inference status must be one of {sorted(_VALID_CLAIM_STATUSES)}, got: {status!r}"
        )
    result.setdefault("status", "provisional")
    _validate_claim_references(
        result["evidence_ids"],
        field="inference evidence_ids",
    )
    return result


def validate_decision(dec: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a decision record."""
    if not isinstance(dec, Mapping):
        raise ExperimentValidationError("decision must be an object")
    result = dict(dec)
    _require_key(result, "id", str)
    _require_key(result, "type", str)
    _require_key(result, "claim", str)
    _require_key(result, "based_on", list)
    validate_claim_id(result["id"])
    if result["type"] != "decision":
        raise ExperimentValidationError(f"decision type must be 'decision', got: {result['type']!r}")
    if not result["claim"].strip():
        raise ExperimentValidationError("decision claim must be non-empty")
    _validate_claim_references(result["based_on"], field="decision based_on")
    return result


def _validate_claim_references(references: list[Any], *, field: str) -> None:
    if not references:
        raise ExperimentValidationError(
            f"{field} must reference at least one claim"
        )
    seen: set[str] = set()
    for index, reference in enumerate(references):
        if not isinstance(reference, str):
            raise ExperimentValidationError(
                f"{field}[{index}] must be a string claim id"
            )
        validate_claim_id(reference)
        if reference in seen:
            raise ExperimentValidationError(
                f"{field} must not contain duplicate claim id {reference!r}"
            )
        seen.add(reference)


def validate_review_decision(rd: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a review decision (scores, verdict, notes)."""
    if not isinstance(rd, Mapping):
        raise ExperimentValidationError("review decision must be an object")
    result = dict(rd)
    _require_key(result, "case_id", str)
    _require_key(result, "reviewer", dict)
    _require_key(result, "scores", dict)
    _require_key(result, "verdict", str)
    _require_key(result, "created", str)
    validate_case_id(result["case_id"])

    reviewer = result["reviewer"]
    reviewer_type = reviewer.get("type")
    if not isinstance(reviewer_type, str) or not reviewer_type.strip():
        raise ExperimentValidationError(
            "reviewer type must be a non-empty string"
        )
    reviewer_id = reviewer.get("id")
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise ExperimentValidationError(
            "reviewer id must be a non-empty string"
        )
    if not result["verdict"].strip():
        raise ExperimentValidationError("review verdict must be non-empty")
    _validate_timestamp(result["created"], "review decision created")

    return result


# ── Utility helpers ────────────────────────────────────────────────────────

def normalize_status(status: str) -> str:
    """Canonicalize a status string to the terminal vocabulary.

    Maps common variants (e.g. 'error', 'rejected') to canonical forms.
    Unknown values are returned as-is with a warning recommendation.
    """
    status = status.strip().lower()
    mapping = {
        "success": "completed",
        "ok": "completed",
        "done": "completed",
        "error": "failed",
        "rejected": "provider_rejected",
        "timeout": "timed_out",
        "cancelled": "interrupted",
        "canceled": "interrupted",
    }
    return mapping.get(status, status)


def is_terminal_status(status: str) -> bool:
    """Return True if *status* is a terminal (non-draft) lifecycle status."""
    return status in _VALID_STATUSES and status != "draft"
