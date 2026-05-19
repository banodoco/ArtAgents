"""Cross-scenario friction-pattern synthesis for the agentic test pipeline.

Reads every summary.json under a single dogfood run directory and asks
DeepSeek V4 Pro to synthesize the recurring failure modes / friction
patterns into `run.md` + `run.json`. Output lands in `<out-dir>/`
(default `<run-dir>-synthesis/`). The runner does NOT auto-invoke this
— it's a human-driven CLI step (read-only pipeline output).

Usage:
    python -m tests.agentic.pattern_finder --run-dir reports/<ts>
    python -m tests.agentic.pattern_finder --run-dir reports/<ts> --out-dir reports/<ts>-custom
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

# Reuse the assessor's dispatcher (same DeepSeek API, same retry policy).
from tests.agentic.assessor import (  # noqa: E402
    DEFAULT_MODEL,
    _call_with_retry,
    _load_deepseek_key,
)

AGENTIC_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = AGENTIC_ROOT / "reports"

SYNTH_MAX_TOKENS = 16384

SYSTEM_PROMPT = """You are a synthesis agent for the Astrid agentic test pipeline. You
read the per-scenario summaries from a single dogfood run (machine
criteria + universal checks + per-scenario three-tier verdicts:
enforced contracts, graded quality, observed telemetry) and produce a
cross-scenario friction-pattern report.

Output JSON only. No prose. No preamble. No code fences.

The output must be a JSON object with this structure:

{
  "contract_failures": [
    {
      "id": "<short_snake_case>",
      "title": "<concise pattern name>",
      "scenarios_affected": ["<scenario-name>", ...],
      "evidence_snippets": ["scenario:<name> — <quote or stat>", ...],
      "severity": "minor" | "major",
      "suggested_fix": "<one or two sentences — concrete fix>"
    }
  ],
  "quality_patterns": [
    {
      "id": "<short_snake_case>",
      "title": "<concise pattern name>",
      "mean_score": 0.NN,
      "scenarios_below_0_5": ["<scenario-name>", ...],
      "observation": "<one or two sentences>",
      "evidence_snippets": ["scenario:<name> — <quote or stat>", ...]
    }
  ],
  "observations": {
    "shell_calls_median": <int or null>,
    "shell_calls_p90": <int or null>,
    "report_lines_median": <int or null>,
    "report_lines_range": [<int>, <int>] or null,
    "canonical_bypass_forms": ["<string>", ...],
    "other": ["<short bullet>", ...]
  },
  "summary": "<≤500 chars — top-level read of the run>",
  "by_scenario": {
    "<scenario-name>": {
      "outcome": "passed" | "failed_contract" | "rejected" | "needs_review",
      "quality_score": <number or null>,
      "key_failures": ["<short label>", ...]
    }
  }
}

Rules:
1. Each rubric verdict in the prompt has an explicit `bucket` and
   `synthesis_section`. Respect them exactly.
2. Items from `acceptance` and `enforced` go in Contract failures only
   when `contract_eligible=true` and their outcome was failed_contract
   or rejected.
3. Items from `graded` go in Quality patterns.
4. Items from `observed` go in Observations regardless of value. Report
   line counts, shell call counts, and canonical-bypass form strings are
   telemetry, never contract failures.
5. `canonical_bypass: "resolved_after_reprompt"` means the first
   attempt bypassed but recovered. Mention it in Observations, not
   Contract failures, and mark that scenario passed unless another
   eligible contract failed.
6. `canonical_cli_bypass` as a Contract failure is reserved for
   scenarios whose `canonical_bypass` is `"rejected"`.
7. `contract_failures` should be sorted by scenarios_affected count desc.
8. Each contract_failure must aggregate evidence from ≥1 scenario,
   ideally ≥2. Quote evidence verbatim.
9. Major patterns are ones that suggest a system gap (the Astrid
   surface itself made the failure likely), not single-agent slip-ups.
10. Suggested fixes are short and concrete (one knob, one doc, one
   verb), not roadmaps.
"""


def _is_canonical_cli_verdict(qid: str) -> bool:
    q = qid.lower()
    return "canonical" in q or "invoked_via" in q or "via_canonical" in q


def _trim_verdict(
    qid: str,
    bucket: str,
    verdict: Any,
    *,
    canonical_bypass: str | None,
) -> dict[str, Any]:
    """Return a compact verdict with explicit synthesis routing.

    The source summaries already contain bucketed verdicts, but the LLM also
    sees legacy fields and synthesized names. Make the intended routing local
    to every verdict so telemetry cannot be promoted into contract failures.
    """
    if isinstance(verdict, dict):
        passed = verdict.get("passed")
        rationale = verdict.get("rationale")
        confidence = verdict.get("confidence")
        value = verdict.get("value")
        if value is None:
            value = verdict.get("count")
    else:
        passed = None
        rationale = None
        confidence = None
        value = None

    if bucket == "acceptance":
        section = "contract_failures"
        contract_eligible = passed is False
    elif bucket == "enforced":
        section = "contract_failures"
        contract_eligible = passed is False
    elif bucket == "graded":
        section = "quality_patterns"
        contract_eligible = False
    else:
        section = "observations"
        contract_eligible = False

    note = None
    if canonical_bypass == "resolved_after_reprompt" and _is_canonical_cli_verdict(qid):
        section = "observations"
        contract_eligible = False
        note = "first attempt bypassed but recovered after re-prompt"

    return {
        "id": qid,
        "bucket": bucket,
        "synthesis_section": section,
        "contract_eligible": contract_eligible,
        "passed": passed,
        "rationale": rationale,
        "confidence": confidence,
        "value": value,
        "note": note,
    }


def _trim_acceptance_criteria(criteria: Any, *, canonical_bypass: str | None) -> list[dict[str, Any]]:
    if not isinstance(criteria, dict):
        return []
    out: list[dict[str, Any]] = []
    for qid, verdict in criteria.items():
        if isinstance(verdict, dict) and verdict.get("ungraded"):
            continue
        out.append(_trim_verdict(qid, "acceptance", verdict, canonical_bypass=canonical_bypass))
    return out


def _trim_assessment_verdicts(
    assessment: Any,
    *,
    canonical_bypass: str | None,
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {
        "enforced": [],
        "graded": [],
        "observed": [],
    }
    if not isinstance(assessment, dict):
        return out
    for bucket in out:
        verdicts = assessment.get(bucket)
        if not isinstance(verdicts, dict):
            continue
        for qid, verdict in verdicts.items():
            out[bucket].append(
                _trim_verdict(qid, bucket, verdict, canonical_bypass=canonical_bypass)
            )
    return out


def _synthesis_outcome(agent: dict[str, Any], rubric_verdicts: dict[str, Any]) -> str:
    """Derive the synthesis-facing outcome from explicit eligibility.

    This intentionally differs from historical summaries when a canonical
    bypass was resolved by re-prompt: synthesis reports the recovery as
    telemetry instead of carrying forward the first failed attempt.
    """
    canonical_bypass = agent.get("canonical_bypass")
    if canonical_bypass == "rejected":
        return "rejected"

    acceptance = rubric_verdicts.get("acceptance") or []
    enforced = rubric_verdicts.get("enforced") or []
    if any(v.get("contract_eligible") for v in [*acceptance, *enforced]):
        return "failed_contract"

    if any(v.get("passed") is None for v in enforced):
        return "needs_review"

    return "passed"


def _trim_universal(universal: Any) -> dict[str, Any] | None:
    if not isinstance(universal, dict):
        return None
    out: dict[str, Any] = {
        "contradictions": universal.get("contradictions"),
    }
    if "canonical_path_bypass" in universal:
        out["canonical_path_bypass"] = {
            "bucket": "observed",
            "synthesis_section": "observations",
            "contract_eligible": False,
            "value": universal.get("canonical_path_bypass"),
        }
    ds = universal.get("deliverable_shape")
    if isinstance(ds, dict):
        out["deliverable_shape"] = {
            "bucket": "observed",
            "synthesis_section": "observations",
            "contract_eligible": False,
            "ok": ds.get("ok"),
            "line_count": ds.get("line_count"),
            "reason": ds.get("reason"),
            "missing_sections": ds.get("missing_sections"),
        }
    return out


def _collect_summaries(run_dir: Path) -> list[dict[str, Any]]:
    """Load every per-scenario summary.json under the run directory.

    Layout: `<run-dir>-<scenario>/summary.json` (the runner's convention)
    OR `<run-dir>/<scenario>.summary.json` (the re-audit convention).
    """
    summaries: list[dict[str, Any]] = []
    # Pattern 1: runner's per-scenario sub-directories.
    parent = run_dir.parent
    tag = run_dir.name
    for sib in sorted(parent.glob(f"{tag}-*")):
        sj = sib / "summary.json"
        if sj.is_file():
            try:
                data = json.loads(sj.read_text(encoding="utf-8"))
                summaries.append(data)
            except Exception:
                continue
    # Pattern 2: re-audit / flat layout.
    for sj in sorted(run_dir.glob("*.summary.json")):
        try:
            data = json.loads(sj.read_text(encoding="utf-8"))
            summaries.append(data)
        except Exception:
            continue
    return summaries


def _trim_summary_for_prompt(s: dict[str, Any]) -> dict[str, Any]:
    """Strip the noisy fields (verbatim evidence_refs deep nests) from
    a per-scenario summary so the cross-run prompt fits in budget.
    Keep the load-bearing signals: name/tier, per-agent passed,
    universal block, and rubric verdicts with explicit bucket origin."""
    out: dict[str, Any] = {
        "scenario": s.get("scenario"),
        "tier": s.get("tier"),
        "aggregate": s.get("aggregate", {}),
        "agents": [],
    }
    for a in s.get("agents") or []:
        ass = a.get("assessor") or {}
        canonical_bypass = a.get("canonical_bypass")
        assessment = _trim_assessment_verdicts(
            a.get("assessment"),
            canonical_bypass=canonical_bypass,
        )
        rubric_verdicts: dict[str, Any] = {
            "acceptance": _trim_acceptance_criteria(
                a.get("criteria"),
                canonical_bypass=canonical_bypass,
            ),
            "enforced": assessment["enforced"],
            "graded": assessment["graded"],
            "observed": assessment["observed"],
        }
        synthesis_outcome = _synthesis_outcome(a, rubric_verdicts)
        out["agents"].append({
            "slug": a.get("slug"),
            "model": a.get("model"),
            "passed": a.get("passed"),
            # v10 prep: three-tier signal model.
            "source_outcome": a.get("outcome"),
            "synthesis_outcome": synthesis_outcome,
            "quality_score": a.get("quality_score"),
            "canonical_bypass": canonical_bypass,
            "metadata": a.get("metadata"),
            "rubric_verdicts": rubric_verdicts,
            "universal_observed": _trim_universal(a.get("universal")),
            "assessor": {
                "contradictions": ass.get("contradictions"),
                "overall_passed": ass.get("overall_passed"),
                "summary": ass.get("summary"),
            } if ass else None,
        })
    return out


def _format_run_md(synth: dict[str, Any]) -> str:
    """Render the JSON synthesis to a human-readable markdown report.

    v10 prep: three-section output — Contract failures (most
    actionable), Quality patterns, Observations.
    """
    lines: list[str] = ["# v10 dogfood synthesis", ""]

    # Top-of-doc outcome banner derived from `by_scenario` outcomes,
    # falling back to summary string when the structured field is missing.
    by_sc = synth.get("by_scenario") or {}
    outcome_counts = {"passed": 0, "failed_contract": 0, "rejected": 0, "needs_review": 0}
    quality_values: list[float] = []
    for _name, info in by_sc.items():
        o = info.get("outcome")
        if isinstance(o, str) and o in outcome_counts:
            outcome_counts[o] += 1
        q = info.get("quality_score")
        if isinstance(q, (int, float)):
            quality_values.append(float(q))
    total = sum(outcome_counts.values())
    if total:
        lines.append(
            "**Outcomes:** "
            f"{outcome_counts['passed']} passed, "
            f"{outcome_counts['failed_contract']} failed_contract, "
            f"{outcome_counts['rejected']} rejected, "
            f"{outcome_counts['needs_review']} needs_review (of {total} scenarios)."
        )
    if quality_values:
        mean_q = sum(quality_values) / len(quality_values)
        lo, hi = min(quality_values), max(quality_values)
        lines.append(
            f"**Mean quality score:** {mean_q:.2f} (range {lo:.2f}–{hi:.2f})."
        )
    summary = synth.get("summary") or "(no summary)"
    lines.append("")
    lines.append(f"_{summary}_")
    lines.append("")

    # --- Contract failures (most actionable, sorted by scenarios affected) ---
    contract_failures = synth.get("contract_failures") or []
    # Fallback: older synthesis runs put everything under `patterns` — surface
    # those under Contract failures so we don't drop signal during the
    # transition.
    if not contract_failures and synth.get("patterns"):
        contract_failures = synth.get("patterns") or []
    contract_failures = sorted(
        contract_failures,
        key=lambda p: len((p or {}).get("scenarios_affected") or []),
        reverse=True,
    )
    lines.append(f"## Contract failures ({len(contract_failures)})")
    lines.append("")
    if not contract_failures:
        lines.append("- (none)")
        lines.append("")
    for p in contract_failures:
        sev = (p.get("severity") or "minor").upper()
        scen = p.get("scenarios_affected") or []
        fix = p.get("suggested_fix") or "(no fix suggested)"
        lines.append(
            f"- [{sev}] **{p.get('title','(untitled)')}** "
            f"`({p.get('id','?')})` — {len(scen)} scenarios — {fix}"
        )
        ev = p.get("evidence_snippets") or []
        if ev:
            for e in ev[:4]:
                lines.append(f"  - {e}")
    lines.append("")

    # --- Quality patterns ---
    quality_patterns = synth.get("quality_patterns") or []
    lines.append(f"## Quality patterns ({len(quality_patterns)})")
    lines.append("")
    if not quality_patterns:
        lines.append("- (none)")
        lines.append("")
    for p in quality_patterns:
        mean = p.get("mean_score")
        below = p.get("scenarios_below_0_5") or []
        obs = p.get("observation") or ""
        mean_str = f"{mean:.2f}" if isinstance(mean, (int, float)) else "n/a"
        lines.append(
            f"- **{p.get('title','(untitled)')}** "
            f"`({p.get('id','?')})` — mean score {mean_str}, "
            f"{len(below)} below 0.5 — {obs}"
        )
        if below:
            lines.append(f"  - scenarios below 0.5: {', '.join(below)}")
    lines.append("")

    # --- Observations (telemetry) ---
    observations = synth.get("observations") or {}
    lines.append("## Observations")
    lines.append("")
    if not observations:
        lines.append("- (none)")
    else:
        sm = observations.get("shell_calls_median")
        sp = observations.get("shell_calls_p90")
        if sm is not None or sp is not None:
            lines.append(f"- Shell calls — median: {sm}, p90: {sp}")
        rm = observations.get("report_lines_median")
        rr = observations.get("report_lines_range")
        if rm is not None or rr:
            rr_str = f" (range {rr[0]}–{rr[1]})" if isinstance(rr, list) and len(rr) == 2 else ""
            lines.append(f"- Report lines — median: {rm}{rr_str}")
        bf = observations.get("canonical_bypass_forms") or []
        if bf:
            lines.append("- Canonical-bypass forms seen:")
            for f in bf:
                lines.append(f"  - {f}")
        other = observations.get("other") or []
        for o in other:
            lines.append(f"- {o}")
    lines.append("")

    # --- Per-scenario verdict table ---
    if by_sc:
        lines.append("## Per-scenario verdict")
        lines.append("")
        for name, info in by_sc.items():
            outcome = info.get("outcome") or ("PASS" if info.get("passed") else "FAIL")
            q = info.get("quality_score")
            q_str = f", quality={q:.2f}" if isinstance(q, (int, float)) else ""
            keys = ", ".join(info.get("key_failures") or []) or "—"
            lines.append(f"- **{name}**: {outcome}{q_str} — key failures: {keys}")
        lines.append("")

    return "\n".join(lines)


def _scenario_outcomes_from_payload(trimmed: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for s in trimmed:
        name = s.get("scenario")
        if not isinstance(name, str) or not name:
            continue
        outcomes: list[str] = []
        qualities: list[float] = []
        key_failures: set[str] = set()
        for a in s.get("agents") or []:
            outcome = a.get("synthesis_outcome")
            if isinstance(outcome, str):
                outcomes.append(outcome)
            q = a.get("quality_score")
            if isinstance(q, (int, float)):
                qualities.append(float(q))
            rv = a.get("rubric_verdicts") or {}
            for verdict in [*(rv.get("acceptance") or []), *(rv.get("enforced") or [])]:
                if verdict.get("contract_eligible"):
                    key_failures.add(str(verdict.get("id") or "contract_failure"))

        if "rejected" in outcomes:
            scenario_outcome = "rejected"
        elif "failed_contract" in outcomes:
            scenario_outcome = "failed_contract"
        elif "needs_review" in outcomes:
            scenario_outcome = "needs_review"
        elif outcomes:
            scenario_outcome = "passed"
        else:
            scenario_outcome = "needs_review"

        out[name] = {
            "outcome": scenario_outcome,
            "quality_score": round(sum(qualities) / len(qualities), 3) if qualities else None,
            "key_failures": sorted(key_failures),
        }
    return out


def _payload_scenario_sets(trimmed: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    rejected: set[str] = set()
    recovered: set[str] = set()
    for s in trimmed:
        name = s.get("scenario")
        if not isinstance(name, str):
            continue
        for a in s.get("agents") or []:
            if a.get("canonical_bypass") == "rejected":
                rejected.add(name)
            elif a.get("canonical_bypass") == "resolved_after_reprompt":
                recovered.add(name)
    return rejected, recovered


def _pattern_text(p: dict[str, Any]) -> str:
    return " ".join(
        str(p.get(k) or "")
        for k in ("id", "title", "suggested_fix")
    ).lower()


def _is_report_line_pattern(p: dict[str, Any]) -> bool:
    text = _pattern_text(p)
    return "report" in text and ("line" in text or "minimum" in text)


def _is_canonical_bypass_pattern(p: dict[str, Any]) -> bool:
    text = _pattern_text(p)
    return "canonical" in text and "bypass" in text


def _append_observation(observations: dict[str, Any], note: str) -> None:
    other = observations.setdefault("other", [])
    if isinstance(other, list) and note not in other:
        other.append(note)


def _median_int(values: list[int]) -> int | None:
    if not values:
        return None
    vals = sorted(values)
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return round((vals[mid - 1] + vals[mid]) / 2)


def _p90_int(values: list[int]) -> int | None:
    if not values:
        return None
    vals = sorted(values)
    idx = min(len(vals) - 1, round((len(vals) - 1) * 0.9))
    return vals[idx]


def _slugify_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "contract_failure"


def _scenario_agent_iter(trimmed: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for s in trimmed:
        name = s.get("scenario")
        if not isinstance(name, str) or not name:
            continue
        for a in s.get("agents") or []:
            if isinstance(a, dict):
                out.append((name, a))
    return out


def _fallback_synthesis_from_payload(
    trimmed: list[dict[str, Any]],
    *,
    summary: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Build a minimal report without the LLM.

    Pattern finding is less nuanced here, but the classification rules are the
    same ones used by the normal synthesis guardrails.
    """
    contract_map: dict[str, dict[str, Any]] = {}
    report_lines: list[int] = []
    shell_counts: list[int] = []
    canonical_forms: set[str] = set()
    observations: dict[str, Any] = {"other": []}

    for scenario, agent in _scenario_agent_iter(trimmed):
        canonical_bypass = agent.get("canonical_bypass")
        if canonical_bypass:
            canonical_forms.add(str(canonical_bypass))
        if canonical_bypass == "resolved_after_reprompt":
            _append_observation(
                observations,
                f"canonical_cli_bypass in {scenario}: first attempt bypassed but recovered after re-prompt.",
            )

        metadata = agent.get("metadata") or {}
        if isinstance(metadata, dict):
            for key, value in metadata.items():
                if "canonical_bypass" in str(key) and value:
                    canonical_forms.add(str(value))

        universal = agent.get("universal_observed") or {}
        if isinstance(universal, dict):
            ds = universal.get("deliverable_shape") or {}
            if isinstance(ds, dict):
                line_count = ds.get("line_count")
                if isinstance(line_count, int):
                    report_lines.append(line_count)
                reason_text = ds.get("reason")
                if reason_text:
                    _append_observation(
                        observations,
                        f"report_below_minimum_lines in {scenario}: {reason_text}.",
                    )

        rv = agent.get("rubric_verdicts") or {}
        for verdict in [*(rv.get("acceptance") or []), *(rv.get("enforced") or [])]:
            if not verdict.get("contract_eligible"):
                continue
            qid = str(verdict.get("id") or "contract_failure")
            if canonical_bypass == "rejected" and _is_canonical_cli_verdict(qid):
                pid = "canonical_cli_bypass"
                title = "Canonical CLI bypass rejected after re-prompt"
            else:
                pid = _slugify_id(qid)
                title = qid.replace("_", " ").replace(".", " ")
            entry = contract_map.setdefault(
                pid,
                {
                    "id": pid,
                    "title": title,
                    "scenarios_affected": [],
                    "evidence_snippets": [],
                    "severity": "major",
                    "suggested_fix": "Inspect the named failing contract and tighten the relevant CLI guidance or test fixture.",
                },
            )
            if scenario not in entry["scenarios_affected"]:
                entry["scenarios_affected"].append(scenario)
            rationale = verdict.get("rationale")
            if rationale:
                entry["evidence_snippets"].append(f"scenario:{scenario} — {rationale}")

    observations["shell_calls_median"] = _median_int(shell_counts)
    observations["shell_calls_p90"] = _p90_int(shell_counts)
    observations["report_lines_median"] = _median_int(report_lines)
    observations["report_lines_range"] = [min(report_lines), max(report_lines)] if report_lines else None
    observations["canonical_bypass_forms"] = sorted(canonical_forms)
    if reason:
        _append_observation(observations, f"LLM synthesis unavailable: {reason}")

    return {
        "contract_failures": sorted(
            contract_map.values(),
            key=lambda p: len(p.get("scenarios_affected") or []),
            reverse=True,
        ),
        "quality_patterns": [],
        "observations": observations,
        "summary": summary,
        "by_scenario": _scenario_outcomes_from_payload(trimmed),
    }


def _scenario_evidence_only(evidence: list[Any], scenarios: set[str]) -> list[Any]:
    kept: list[Any] = []
    for item in evidence:
        text = str(item)
        if any(f"scenario:{s}" in text for s in scenarios):
            kept.append(item)
    return kept


def _enforce_three_tier_synthesis_rules(
    synth: dict[str, Any],
    trimmed: list[dict[str, Any]],
) -> dict[str, Any]:
    """Make the LLM output obey the v10 synthesis contract.

    The model still does the cross-scenario grouping and wording, but these
    rules are structural enough to enforce deterministically before rendering.
    """
    observations = synth.setdefault("observations", {})
    if not isinstance(observations, dict):
        observations = {}
        synth["observations"] = observations

    rejected, recovered = _payload_scenario_sets(trimmed)
    filtered: list[dict[str, Any]] = []
    for raw in synth.get("contract_failures") or []:
        if not isinstance(raw, dict):
            continue
        p = dict(raw)
        if _is_report_line_pattern(p):
            scenarios = p.get("scenarios_affected") or []
            if scenarios:
                _append_observation(
                    observations,
                    "report_below_minimum_lines is observed telemetry, not a contract failure; "
                    f"seen in {', '.join(str(s) for s in scenarios)}.",
                )
            continue

        if _is_canonical_bypass_pattern(p):
            scenarios = [str(s) for s in (p.get("scenarios_affected") or [])]
            allowed = [s for s in scenarios if s in rejected]
            removed_recovered = [s for s in scenarios if s in recovered]
            for s in removed_recovered:
                _append_observation(
                    observations,
                    f"canonical_cli_bypass in {s}: first attempt bypassed but recovered after re-prompt.",
                )
            if not allowed:
                continue
            p["scenarios_affected"] = allowed
            p["evidence_snippets"] = _scenario_evidence_only(
                p.get("evidence_snippets") or [],
                set(allowed),
            )

        filtered.append(p)

    synth["contract_failures"] = filtered

    by_scenario = synth.get("by_scenario")
    if not isinstance(by_scenario, dict):
        by_scenario = {}
    policy_by_scenario = _scenario_outcomes_from_payload(trimmed)
    for name, policy in policy_by_scenario.items():
        existing = by_scenario.get(name)
        if not isinstance(existing, dict):
            existing = {}
        existing["outcome"] = policy["outcome"]
        existing["quality_score"] = policy["quality_score"]
        existing["key_failures"] = policy["key_failures"]
        by_scenario[name] = existing
    synth["by_scenario"] = by_scenario
    return synth


def synthesize(run_dir: Path, out_dir: Path) -> Path:
    run_dir = Path(run_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summaries = _collect_summaries(run_dir)
    trimmed = [_trim_summary_for_prompt(s) for s in summaries]
    user_payload = (
        "Synthesize the friction patterns across these per-scenario summaries.\n\n"
        "## Per-scenario summaries (JSON)\n"
        + json.dumps(trimmed, indent=2, default=str)
    )

    api_key = _load_deepseek_key()
    started = time.time()
    if not api_key:
        synth = _fallback_synthesis_from_payload(
            trimmed,
            summary="Deterministic synthesis fallback because DEEPSEEK_API_KEY is missing.",
            reason="DEEPSEEK_API_KEY missing",
        )
        synth["ungraded"] = True
        synth["reason"] = "DEEPSEEK_API_KEY missing"
        synth["elapsed_sec"] = 0.0
    else:
        content, err, status = _call_with_retry(
            api_key, DEFAULT_MODEL, SYSTEM_PROMPT, user_payload, SYNTH_MAX_TOKENS
        )
        if content is None:
            reason = f"dispatch failed (status={status}): {err}"
            synth = _fallback_synthesis_from_payload(
                trimmed,
                summary="Deterministic synthesis fallback because LLM synthesis failed.",
                reason=reason,
            )
            synth["ungraded"] = True
            synth["reason"] = reason
            synth["elapsed_sec"] = round(time.time() - started, 2)
        else:
            try:
                synth = json.loads(content)
            except json.JSONDecodeError as exc:
                reason = f"json parse error: {exc}"
                synth = _fallback_synthesis_from_payload(
                    trimmed,
                    summary="Deterministic synthesis fallback because LLM returned non-JSON.",
                    reason=reason,
                )
                synth["error"] = reason
                synth["raw"] = content[:4000]
            synth["elapsed_sec"] = round(time.time() - started, 2)
            synth["model"] = DEFAULT_MODEL
    synth = _enforce_three_tier_synthesis_rules(synth, trimmed)

    (out_dir / "run.json").write_text(
        json.dumps(synth, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / "run.md").write_text(_format_run_md(synth), encoding="utf-8")
    return out_dir / "run.md"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = (Path.cwd() / run_dir).resolve()
    out_dir = Path(args.out_dir) if args.out_dir else Path(f"{run_dir}-synthesis")
    out = synthesize(run_dir, out_dir)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
