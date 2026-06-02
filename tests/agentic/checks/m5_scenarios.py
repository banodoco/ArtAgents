"""M5 deterministic scenario checks over textual evidence packs."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from tests.agentic.checks.io import FrozenEvidencePack
from tests.agentic.checks.results import ScoredCheckResult, build_check_result

M5TriggerSource = Literal["scenario_extras", "manifest", "absent"]

M5_CHECK_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        "m5.no_tool_exists_pushback.no_fabricated_tool_id",
        "no_fabricated_tool_id",
        "no_fabricated_tool_id",
    ),
    (
        "m5.recover_from_no_search_results.search_fallback_after_zero_hits",
        "search_fallback_after_zero_hits",
        "search_fallback_after_zero_hits",
    ),
    (
        "m5.discover_projects_runs_sessions.projects_runs_sessions_discovered",
        "projects_runs_sessions_discovered",
        "projects_runs_sessions_discovered",
    ),
    (
        "m5.broken_authoring_fix.broken_authoring_fix_loop",
        "broken_authoring_fix_loop",
        "broken_authoring_fix_loop",
    ),
    (
        "m5.cross_pack_authoring.cross_pack_authoring_discovery",
        "cross_pack_authoring_discovery",
        "cross_pack_authoring_discovery",
    ),
    (
        "m5.author_run_revise_loop.author_run_revise_loop",
        "author_run_revise_loop",
        "author_run_revise_loop",
    ),
)

_REQUIRED_EVIDENCE = {
    "no_fabricated_tool_id": ("stderr.log", "report.md"),
    "search_fallback_after_zero_hits": ("stderr.log",),
    "projects_runs_sessions_discovered": ("stderr.log",),
    "broken_authoring_fix_loop": ("stderr.log",),
    "cross_pack_authoring_discovery": ("stderr.log", "report.md"),
    "author_run_revise_loop": ("stderr.log", "report.md"),
}

_DISCOVERY_INVOCATION_RE = re.compile(
    r"astrid\s+(?P<surface>executors|orchestrators)\s+"
    r"(?P<verb>search|list)\b(?P<rest>[^\n\r]*)",
    re.IGNORECASE,
)
_RUN_INVOCATION_RE = re.compile(
    r"astrid\s+(?P<surface>executors|orchestrators)\s+run\s+"
    r"(?P<tool_id>[A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
_AUTHOR_CHECK_RE = re.compile(r"astrid\s+author\s+check\b[^\n\r]*", re.IGNORECASE)
_MISMATCH_LANGUAGE_RE = re.compile(
    r"\b(wrong|incorrect|unexpected|mismatch|incomplete|expected\s+\d+|got\s+\d+)\b",
    re.IGNORECASE,
)
_ACTION_RE = re.compile(
    r"astrid\s+(?:author\b|orchestrators\s+run\b|executors\s+run\b|attach\b)",
    re.IGNORECASE,
)
_SUCCESS_RE = re.compile(
    r"\b(?:exit(?:ed)?\s*[:=]?\s*0|exit\s+0|success|succeeded|passed|ok)\b",
    re.IGNORECASE,
)
_FAILURE_RE = re.compile(
    r"\b(?:exit(?:ed)?\s*[:=]?\s*[1-9]\d*|exit\s+[1-9]\d*|non-zero|error|failed|failure|syntaxerror|traceback)\b",
    re.IGNORECASE,
)
_PROJECTS_DISCOVERY_RE = re.compile(r"astrid\s+projects\s+(?:ls|list)\b", re.IGNORECASE)
_RUNS_DISCOVERY_RE = re.compile(r"astrid\s+runs\s+(?:ls|list)\b", re.IGNORECASE)
_SESSIONS_DISCOVERY_RE = re.compile(r"astrid\s+sessions\s+(?:ls|list)\b", re.IGNORECASE)
_PACK_TOKENS = ("editorial.transcribe", "editorial", "video_editing.hype", "video_editing")


@dataclass(frozen=True)
class M5CheckRecord:
    """Normalized declaration for one optional M5 scenario check."""

    stable_id: str
    trigger_key: str
    enabled: bool
    source: M5TriggerSource
    config: Mapping[str, Any]
    required_evidence: tuple[str, ...]


def resolve_m5_check_records(
    *,
    scenario_extras: Mapping[str, Any] | None = None,
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, M5CheckRecord]:
    """Resolve M5 deterministic checks from scenario extras or manifest."""
    declarations, source = _resolve_m5_checks_mapping(
        scenario_extras=scenario_extras,
        manifest=manifest,
    )

    records: dict[str, M5CheckRecord] = {}
    for stable_id, trigger_key, _fn_name in M5_CHECK_SPECS:
        raw_config = declarations.get(trigger_key)
        config = raw_config if isinstance(raw_config, Mapping) else {}
        enabled = bool(config.get("enabled"))
        record_source: M5TriggerSource = source if raw_config is not None else "absent"
        records[stable_id] = M5CheckRecord(
            stable_id=stable_id,
            trigger_key=trigger_key,
            enabled=enabled,
            source=record_source,
            config=dict(config),
            required_evidence=_REQUIRED_EVIDENCE[trigger_key],
        )
    return records


def no_fabricated_tool_id(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M5CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m5_check(pack, trigger_record)
    if gated is not None:
        return gated

    stderr = _read_text(pack, "stderr.log")
    report = _read_text(pack, "report.md")
    mismatches: list[dict[str, Any]] = []
    search_terms = _distinct_search_terms(stderr)
    fabricated_runs = [match.group("tool_id") for match in _RUN_INVOCATION_RE.finditer(stderr)]

    if len(search_terms) < 2:
        mismatches.append(
            {
                "field": "distinct_search_terms",
                "expected": ">= 2",
                "actual": search_terms,
            }
        )
    if fabricated_runs:
        mismatches.append(
            {
                "field": "fabricated_run_invocations",
                "expected": [],
                "actual": fabricated_runs,
            }
        )
    if not re.search(r"\b(no matching tool|no tool exists|nothing found|no match)\b", report, re.IGNORECASE):
        mismatches.append(
            {
                "field": "report_honest_refusal_language",
                "expected": "explicit no-match statement",
                "actual": report,
            }
        )

    return _result(
        "m5.no_tool_exists_pushback.no_fabricated_tool_id",
        evidence_refs=_refs(pack, "stderr.log", "report.md", "brief.md"),
        mismatches=mismatches,
        detail={
            "distinct_search_terms": search_terms,
            "fabricated_runs": fabricated_runs,
        },
    )


def search_fallback_after_zero_hits(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M5CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m5_check(pack, trigger_record)
    if gated is not None:
        return gated

    stderr = _read_text(pack, "stderr.log")
    discovery_calls = _discovery_invocations(stderr)
    search_calls = [call for call in discovery_calls if call["verb"] == "search"]
    mismatches: list[dict[str, Any]] = []

    if len(search_calls) < 2:
        mismatches.append(
            {
                "field": "search_invocation_count",
                "expected": ">= 2",
                "actual": len(search_calls),
            }
        )
    if discovery_calls:
        first = discovery_calls[0]
        if first["verb"] != "search":
            mismatches.append(
                {
                    "field": "first_discovery_invocation",
                    "expected": "search",
                    "actual": first["verb"],
                }
            )
    else:
        mismatches.append(
            {
                "field": "discovery_invocations",
                "expected": ">= 2",
                "actual": 0,
            }
        )

    distinct_search_terms = [call["search_term"] for call in search_calls if call["search_term"]]
    has_fallback = any(call["verb"] == "list" for call in discovery_calls) or len(set(distinct_search_terms)) >= 2
    if not has_fallback:
        mismatches.append(
            {
                "field": "fallback_strategy",
                "expected": "later list or rephrased search",
                "actual": distinct_search_terms,
            }
        )

    return _result(
        "m5.recover_from_no_search_results.search_fallback_after_zero_hits",
        evidence_refs=_refs(pack, "stderr.log", "report.md", "brief.md"),
        mismatches=mismatches,
        detail={
            "discovery_invocations": discovery_calls,
            "distinct_search_terms": distinct_search_terms,
            "fallback_detected": has_fallback,
        },
    )


def projects_runs_sessions_discovered(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M5CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m5_check(pack, trigger_record)
    if gated is not None:
        return gated

    stderr = _read_text(pack, "stderr.log")
    mismatches: list[dict[str, Any]] = []
    positions = {
        "projects": _first_match(_PROJECTS_DISCOVERY_RE, stderr),
        "runs": _first_match(_RUNS_DISCOVERY_RE, stderr),
        "sessions": _first_match(_SESSIONS_DISCOVERY_RE, stderr),
    }
    action_pos = _first_match(_ACTION_RE, stderr)

    for field, pos in positions.items():
        if pos < 0:
            mismatches.append({"field": field, "expected": "discovery command present", "actual": None})
        elif action_pos >= 0 and pos > action_pos:
            mismatches.append(
                {
                    "field": field,
                    "expected": "appears before first action command",
                    "actual": pos,
                }
            )

    return _result(
        "m5.discover_projects_runs_sessions.projects_runs_sessions_discovered",
        evidence_refs=_refs(pack, "stderr.log", "report.md", "brief.md"),
        mismatches=mismatches,
        detail={
            "discovery_positions": positions,
            "first_action_position": action_pos,
        },
    )


def broken_authoring_fix_loop(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M5CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m5_check(pack, trigger_record)
    if gated is not None:
        return gated

    stderr = _read_text(pack, "stderr.log")
    outcomes = _author_check_outcomes(stderr)
    mismatches: list[dict[str, Any]] = []

    first_fail = next((outcome for outcome in outcomes if outcome["status"] == "fail"), None)
    later_success = next(
        (
            outcome
            for outcome in outcomes
            if outcome["status"] == "pass"
            and first_fail is not None
            and outcome["position"] > first_fail["position"]
        ),
        None,
    )

    if first_fail is None:
        mismatches.append(
            {
                "field": "initial_failing_author_check",
                "expected": "present",
                "actual": outcomes,
            }
        )
    if later_success is None:
        mismatches.append(
            {
                "field": "later_successful_author_check",
                "expected": "present after failure",
                "actual": outcomes,
            }
        )

    return _result(
        "m5.broken_authoring_fix.broken_authoring_fix_loop",
        evidence_refs=_refs(pack, "stderr.log", "report.md", "brief.md"),
        mismatches=mismatches,
        detail={"author_check_outcomes": outcomes},
    )


def cross_pack_authoring_discovery(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M5CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m5_check(pack, trigger_record)
    if gated is not None:
        return gated

    stderr = _read_text(pack, "stderr.log")
    report = _read_text(pack, "report.md")
    combined = f"{stderr}\n{report}"
    discovery_positions = {
        token: combined.lower().find(token.lower()) for token in _PACK_TOKENS
    }
    has_editorial = any(discovery_positions[token] >= 0 for token in ("editorial.transcribe", "editorial"))
    has_video = any(discovery_positions[token] >= 0 for token in ("video_editing.hype", "video_editing"))
    author_success = _first_successful_author_check(stderr)
    mismatches: list[dict[str, Any]] = []

    if not has_editorial or not has_video:
        mismatches.append(
            {
                "field": "cross_pack_discovery",
                "expected": ["editorial", "video_editing"],
                "actual": discovery_positions,
            }
        )

    latest_discovery = max(pos for pos in discovery_positions.values() if pos >= 0) if (has_editorial or has_video) else -1
    if author_success is None:
        mismatches.append(
            {
                "field": "author_check_success",
                "expected": "successful astrid author check",
                "actual": None,
            }
        )
    elif latest_discovery >= 0 and author_success["position"] <= latest_discovery:
        mismatches.append(
            {
                "field": "author_check_order",
                "expected": "author check success after discovery",
                "actual": author_success["position"],
            }
        )

    return _result(
        "m5.cross_pack_authoring.cross_pack_authoring_discovery",
        evidence_refs=_refs(pack, "stderr.log", "report.md", "brief.md"),
        mismatches=mismatches,
        detail={
            "discovery_positions": discovery_positions,
            "author_check_success": author_success,
        },
    )


def author_run_revise_loop(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M5CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m5_check(pack, trigger_record)
    if gated is not None:
        return gated

    diagnostic = pack.read_json("m5/author_run_revise_loop.json")
    if isinstance(diagnostic, dict):
        mismatches: list[dict[str, Any]] = []
        if not bool(diagnostic.get("wrong_output_observed")):
            mismatches.append(
                {"field": "wrong_output_observed", "expected": True, "actual": diagnostic.get("wrong_output_observed")}
            )
        if _as_int(diagnostic.get("revision_count")) < 1:
            mismatches.append(
                {"field": "revision_count", "expected": ">= 1", "actual": diagnostic.get("revision_count")}
            )
        if not bool(diagnostic.get("final_success")):
            mismatches.append(
                {"field": "final_success", "expected": True, "actual": diagnostic.get("final_success")}
            )
        return _result(
            "m5.author_run_revise_loop.author_run_revise_loop",
            evidence_refs=_refs(pack, "stderr.log", "report.md", "brief.md", "m5/author_run_revise_loop.json"),
            mismatches=mismatches,
            detail={"mode": "diagnostic", **diagnostic},
        )

    stderr = _read_text(pack, "stderr.log")
    report = _read_text(pack, "report.md")
    run_positions = [match.start() for match in _RUN_INVOCATION_RE.finditer(stderr) if match.group("surface").lower() == "orchestrators"]
    mismatch_pos = _first_match(_MISMATCH_LANGUAGE_RE, f"{stderr}\n{report}")
    author_success = _first_successful_author_check(stderr)
    final_success = re.search(r"\b(correct|fixed|success|60)\b", report, re.IGNORECASE) is not None
    mismatches: list[dict[str, Any]] = []

    if len(run_positions) < 2:
        mismatches.append(
            {
                "field": "orchestrator_run_count",
                "expected": ">= 2",
                "actual": len(run_positions),
            }
        )
    if mismatch_pos < 0:
        mismatches.append(
            {
                "field": "wrong_output_language",
                "expected": "present",
                "actual": None,
            }
        )
    if author_success is None:
        mismatches.append(
            {
                "field": "author_check_success",
                "expected": "successful author check before rerun",
                "actual": None,
            }
        )
    elif len(run_positions) >= 2 and author_success["position"] > run_positions[1]:
        mismatches.append(
            {
                "field": "author_check_order",
                "expected": "before second run",
                "actual": author_success["position"],
            }
        )
    if not final_success:
        mismatches.append(
            {
                "field": "final_success_language",
                "expected": "report confirms corrected rerun",
                "actual": report,
            }
        )

    return _result(
        "m5.author_run_revise_loop.author_run_revise_loop",
        evidence_refs=_refs(pack, "stderr.log", "report.md", "brief.md"),
        mismatches=mismatches,
        detail={
            "mode": "text_fallback",
            "run_positions": run_positions,
            "mismatch_position": mismatch_pos,
            "author_check_success": author_success,
            "final_success_language": final_success,
        },
    )


def _pack(evidence_dir: Path | str | FrozenEvidencePack) -> FrozenEvidencePack:
    return evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)


def _gate_m5_check(
    pack: FrozenEvidencePack,
    trigger_record: M5CheckRecord | None,
) -> ScoredCheckResult | None:
    if trigger_record is None:
        return None
    if not trigger_record.enabled:
        return build_check_result(
            trigger_record.stable_id,
            "na",
            detail={
                "reason": "trigger not declared",
                "trigger_key": trigger_record.trigger_key,
            },
        )

    missing = [
        evidence_path
        for evidence_path in trigger_record.required_evidence
        if pack.read_bytes(evidence_path) is None
    ]
    if missing:
        return build_check_result(
            trigger_record.stable_id,
            "fail",
            detail={
                "reason": "declared trigger missing required evidence",
                "trigger_key": trigger_record.trigger_key,
                "trigger_source": trigger_record.source,
                "missing_evidence": missing,
            },
        )
    return None


def _resolve_m5_checks_mapping(
    *,
    scenario_extras: Mapping[str, Any] | None,
    manifest: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any], M5TriggerSource]:
    extras_checks = _mapping_at_key(scenario_extras, "m5_checks")
    if extras_checks is not None:
        return extras_checks, "scenario_extras"

    manifest_checks = _mapping_at_key(manifest, "m5_checks")
    if manifest_checks is not None:
        return manifest_checks, "manifest"

    return {}, "absent"


def _mapping_at_key(
    container: Mapping[str, Any] | None,
    key: str,
) -> Mapping[str, Any] | None:
    if not isinstance(container, Mapping):
        return None
    value = container.get(key)
    if isinstance(value, Mapping):
        return value
    return None


def _read_text(pack: FrozenEvidencePack, path: str) -> str:
    return pack.read_text(path) or ""


def _refs(pack: FrozenEvidencePack, *paths: str) -> list[str]:
    refs: list[str] = []
    for path in paths:
        if pack.read_bytes(path) is not None:
            refs.append(pack.evidence_ref(path))
    return _dedupe(refs)


def _result(
    stable_id: str,
    *,
    evidence_refs: list[str],
    mismatches: list[dict[str, Any]],
    detail: Mapping[str, Any],
) -> ScoredCheckResult:
    return build_check_result(
        stable_id,
        "fail" if mismatches else "pass",
        evidence_refs=evidence_refs,
        detail={**detail, "mismatches": mismatches},
    )


def _discovery_invocations(stderr: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in _DISCOVERY_INVOCATION_RE.finditer(stderr):
        rest = " ".join(match.group("rest").strip().split())
        calls.append(
            {
                "surface": match.group("surface").lower(),
                "verb": match.group("verb").lower(),
                "search_term": _normalize_search_term(rest),
                "command": match.group(0).strip(),
                "position": match.start(),
            }
        )
    return calls


def _distinct_search_terms(stderr: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for call in _discovery_invocations(stderr):
        term = call["search_term"]
        if call["verb"] != "search" or not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _normalize_search_term(rest: str) -> str:
    normalized = rest.strip()
    if normalized.startswith("--"):
        parts = normalized.split(None, 1)
        normalized = parts[1] if len(parts) == 2 else ""
    return normalized.strip(" \"'")


def _author_check_outcomes(stderr: str) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    matches = list(_AUTHOR_CHECK_RE.finditer(stderr))
    for index, match in enumerate(matches):
        segment_end = matches[index + 1].start() if index + 1 < len(matches) else len(stderr)
        segment = stderr[match.start():segment_end]
        status = "unknown"
        if _FAILURE_RE.search(segment):
            status = "fail"
        elif _SUCCESS_RE.search(segment):
            status = "pass"
        outcomes.append(
            {
                "command": match.group(0).strip(),
                "status": status,
                "position": match.start(),
            }
        )
    return outcomes


def _first_successful_author_check(stderr: str) -> dict[str, Any] | None:
    return next((outcome for outcome in _author_check_outcomes(stderr) if outcome["status"] == "pass"), None)


def _first_match(pattern: re.Pattern[str], text: str) -> int:
    match = pattern.search(text)
    return match.start() if match else -1


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _as_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return -1
    return value
