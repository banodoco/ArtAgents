"""Cross-scenario synthesis CLI for Sisypy evidence packs.

Read-only deterministic aggregation over per-scenario Sisypy evidence
directories.  Produces `synthesis.md` (human-readable) and
`synthesis.json` (machine-readable) without mutating source evidence.

No live LLM dependency — all aggregation is structural.

Usage:
    python -m tests.agentic.synthesis --reports-dir tests/agentic/reports/<tag>/
    python -m tests.agentic.synthesis --reports-dir tests/agentic/reports/<tag>/ --out-dir custom/
    python -m tests.agentic.synthesis --batch-summary batch.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


AGENTIC_ROOT = Path(__file__).resolve().parent
DEFAULT_REPORTS_DIR = AGENTIC_ROOT / "reports"

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


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


def _append_observation(observations: dict[str, Any], note: str) -> None:
    other = observations.setdefault("other", [])
    if isinstance(other, list) and note not in other:
        other.append(note)


# ---------------------------------------------------------------------------
# Evidence pack discovery
# ---------------------------------------------------------------------------


def _discover_scenario_dirs(reports_dir: Path) -> list[Path]:
    """Find per-scenario directories under the reports directory.

    Looks for subdirectories that contain at least one of the
    expected evidence files (report.md, stderr.log, manifest.json,
    assessment.json).  Skips synthesis output directories.
    """
    results: list[Path] = []
    if not reports_dir.is_dir():
        return results
    for entry in sorted(reports_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("_synthesis") or entry.name.startswith("."):
            continue
        # Must have at least one evidence file
        if any(
            (entry / f).is_file()
            for f in ("report.md", "stderr.log", "manifest.json", "assessment.json")
        ):
            results.append(entry)
    return results


def _read_evidence(scenario_dir: Path) -> dict[str, Any]:
    """Read the Sisypy evidence files from a single scenario directory."""
    evidence: dict[str, Any] = {
        "scenario": scenario_dir.name,
        "report": None,
        "stderr": None,
        "manifest": None,
        "assessment": None,
    }
    rp = scenario_dir / "report.md"
    if rp.is_file():
        evidence["report"] = rp.read_text(encoding="utf-8", errors="replace")

    sp = scenario_dir / "stderr.log"
    if sp.is_file():
        evidence["stderr"] = sp.read_text(encoding="utf-8", errors="replace")

    mp = scenario_dir / "manifest.json"
    if mp.is_file():
        try:
            evidence["manifest"] = json.loads(mp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            evidence["manifest"] = None

    ap = scenario_dir / "assessment.json"
    if ap.is_file():
        try:
            evidence["assessment"] = json.loads(ap.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            evidence["assessment"] = None

    return evidence


# ---------------------------------------------------------------------------
# Evidence aggregation
# ---------------------------------------------------------------------------


def _extract_scenario_outcome(evidence: dict[str, Any]) -> dict[str, Any]:
    """Derive a per-scenario outcome from Sisypy evidence."""
    name = evidence["scenario"]
    outcome: dict[str, Any] = {
        "scenario": name,
        "outcome": "needs_review",
        "quality_score": None,
        "key_failures": [],
        "shell_calls": None,
        "canonical_bypass_forms": [],
        "observations": [],
    }

    assessment = evidence.get("assessment") or {}
    manifest = evidence.get("manifest") or {}

    # Check assessment for contract failures
    enforced = assessment.get("enforced") or {}
    graded = assessment.get("graded") or {}
    observed = assessment.get("observed") or {}

    contract_failures: list[str] = []
    quality_scores: list[float] = []

    # Enforced checks — contract failures gate the run
    for qid, verdict in (enforced if isinstance(enforced, dict) else {}).items():
        if isinstance(verdict, dict):
            passed = verdict.get("passed")
            if passed is False:
                contract_failures.append(qid)
            elif passed is None:
                outcome["key_failures"].append(f"{qid}:ungraded")

    # Graded checks — quality scores
    for qid, verdict in (graded if isinstance(graded, dict) else {}).items():
        if isinstance(verdict, dict):
            score = verdict.get("score")
            if isinstance(score, (int, float)):
                quality_scores.append(float(score))

    # Observed — telemetry
    for qid, verdict in (observed if isinstance(observed, dict) else {}).items():
        if isinstance(verdict, dict):
            if "shell" in qid.lower() and "count" in qid.lower():
                v = verdict.get("value") or verdict.get("count")
                if isinstance(v, (int, float)):
                    outcome["shell_calls"] = int(v)
            if "canonical" in qid.lower() and "bypass" in qid.lower():
                v = verdict.get("value") or verdict.get("form")
                if v:
                    outcome["canonical_bypass_forms"].append(str(v))

    # Determine overall outcome
    if contract_failures:
        # Check if any failure is a canonical CLI bypass rejection
        canonical_rejected = any("canonical" in f.lower() or "invoked_via" in f.lower() for f in contract_failures)
        outcome["outcome"] = "rejected" if canonical_rejected else "failed_contract"
    else:
        outcome["outcome"] = "passed"

    outcome["key_failures"] = contract_failures
    if quality_scores:
        outcome["quality_score"] = round(sum(quality_scores) / len(quality_scores), 3)

    # Manifest-based observations
    if isinstance(manifest, dict):
        gaps = manifest.get("capture_gaps") or []
        for gap in gaps:
            if isinstance(gap, str):
                outcome["observations"].append(f"capture_gap: {gap}")

    # Stderr-based observations
    stderr = evidence.get("stderr") or ""
    if stderr:
        # Rough shell call count from stderr
        shell_pattern = re.findall(r"^\s*\$ |^\s*\+\s|\b(astrid|python3?)\s", stderr, re.MULTILINE)
        if shell_pattern and outcome["shell_calls"] is None:
            outcome["shell_calls"] = len(shell_pattern)

    return outcome


# ---------------------------------------------------------------------------
# Synthesis aggregation
# ---------------------------------------------------------------------------


def _aggregate_outcomes(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Build cross-scenario synthesis from per-scenario outcomes."""
    contract_map: dict[str, dict[str, Any]] = {}
    shell_counts: list[int] = []
    canonical_forms: set[str] = set()
    global_observations: dict[str, Any] = {"other": []}

    passed = 0
    failed = 0
    rejected = 0
    needs_review = 0
    quality_values: list[float] = []

    for oc in outcomes:
        name = oc["scenario"]
        ostatus = oc["outcome"]

        if ostatus == "passed":
            passed += 1
        elif ostatus == "failed_contract":
            failed += 1
        elif ostatus == "rejected":
            rejected += 1
        else:
            needs_review += 1

        q = oc["quality_score"]
        if isinstance(q, (int, float)):
            quality_values.append(float(q))

        sc = oc.get("shell_calls")
        if isinstance(sc, int) and sc >= 0:
            shell_counts.append(sc)

        for form in oc.get("canonical_bypass_forms") or []:
            canonical_forms.add(str(form))

        for obs in oc.get("observations") or []:
            _append_observation(global_observations, f"{name}: {obs}")

        # Aggregate contract failures
        for fid in oc.get("key_failures") or []:
            pid = _slugify_id(fid)
            title = fid.replace("_", " ").replace(".", " ")
            entry = contract_map.setdefault(
                pid,
                {
                    "id": pid,
                    "title": title,
                    "scenarios_affected": [],
                    "evidence_snippets": [],
                    "severity": "major",
                    "suggested_fix": "Inspect the failing check and tighten the relevant CLI guidance or test fixture.",
                },
            )
            if name not in entry["scenarios_affected"]:
                entry["scenarios_affected"].append(name)
            entry["evidence_snippets"].append(f"scenario:{name} — check `{fid}` failed")

    global_observations["shell_calls_median"] = _median_int(shell_counts)
    global_observations["shell_calls_p90"] = _p90_int(shell_counts)
    global_observations["canonical_bypass_forms"] = sorted(canonical_forms)

    total = passed + failed + rejected + needs_review
    summary_parts: list[str] = []
    if total:
        summary_parts.append(
            f"{passed} passed, {failed} failed_contract, "
            f"{rejected} rejected, {needs_review} needs_review (of {total} scenarios)"
        )
    if quality_values:
        mean_q = sum(quality_values) / len(quality_values)
        summary_parts.append(
            f"Mean quality score: {mean_q:.2f} "
            f"(range {min(quality_values):.2f}–{max(quality_values):.2f})"
        )

    by_scenario: dict[str, dict[str, Any]] = {}
    for oc in outcomes:
        by_scenario[oc["scenario"]] = {
            "outcome": oc["outcome"],
            "quality_score": oc.get("quality_score"),
            "key_failures": oc.get("key_failures") or [],
        }

    return {
        "contract_failures": sorted(
            contract_map.values(),
            key=lambda p: len(p.get("scenarios_affected") or []),
            reverse=True,
        ),
        "quality_patterns": [],
        "observations": global_observations,
        "summary": "; ".join(summary_parts) if summary_parts else "No scenarios analyzed.",
        "by_scenario": by_scenario,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _format_synthesis_md(synth: dict[str, Any]) -> str:
    """Render the JSON synthesis to a human-readable markdown report."""
    lines: list[str] = ["# Sisypy agentic synthesis", ""]

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
        lines.append(f"**Mean quality score:** {mean_q:.2f} (range {lo:.2f}–{hi:.2f}).")

    summary = synth.get("summary") or "(no summary)"
    lines.append("")
    lines.append(f"_{summary}_")
    lines.append("")

    # Contract failures
    contract_failures = synth.get("contract_failures") or []
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

    # Quality patterns
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

    # Observations
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
        bf = observations.get("canonical_bypass_forms") or []
        if bf:
            lines.append("- Canonical-bypass forms seen:")
            for f in bf:
                lines.append(f"  - {f}")
        other = observations.get("other") or []
        for o in other:
            lines.append(f"- {o}")
    lines.append("")

    # Per-scenario verdict table
    if by_sc:
        lines.append("## Per-scenario verdict")
        lines.append("")
        for name, info in sorted(by_sc.items()):
            outcome = info.get("outcome") or "needs_review"
            q = info.get("quality_score")
            q_str = f", quality={q:.2f}" if isinstance(q, (int, float)) else ""
            keys = ", ".join(info.get("key_failures") or []) or "—"
            lines.append(f"- **{name}**: {outcome}{q_str} — key failures: {keys}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core synthesis function
# ---------------------------------------------------------------------------


def synthesize(
    reports_dir: Path,
    out_dir: Path | None = None,
    *,
    batch_summary: Path | None = None,
) -> tuple[Path, Path]:
    """Read Sisypy evidence packs and produce synthesis reports.

    Args:
        reports_dir: Directory containing per-scenario evidence subdirectories.
        out_dir: Output directory for synthesis files (default: <reports_dir>/_synthesis/).
        batch_summary: Optional path to a batch summary JSON (merged into results).

    Returns:
        Tuple of (synthesis_md_path, synthesis_json_path).
    """
    reports_dir = Path(reports_dir)
    if out_dir is None:
        out_dir = reports_dir / "_synthesis"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Discover scenario directories
    scenario_dirs = _discover_scenario_dirs(reports_dir)

    outcomes: list[dict[str, Any]] = []
    for sdir in scenario_dirs:
        evidence = _read_evidence(sdir)
        outcome = _extract_scenario_outcome(evidence)
        outcomes.append(outcome)

    # If batch summary provided, merge it
    if batch_summary is not None:
        bsp = Path(batch_summary)
        if bsp.is_file():
            try:
                batch_data = json.loads(bsp.read_text(encoding="utf-8"))
                if isinstance(batch_data, dict):
                    batch_outcomes = batch_data.get("scenarios") or batch_data.get("outcomes") or []
                    for bo in batch_outcomes:
                        if isinstance(bo, dict):
                            outcomes.append(bo)
            except (json.JSONDecodeError, OSError):
                pass

    # Build synthesis
    synth = _aggregate_outcomes(outcomes)

    # Write output files
    json_path = out_dir / "synthesis.json"
    md_path = out_dir / "synthesis.md"

    json_path.write_text(json.dumps(synth, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_format_synthesis_md(synth), encoding="utf-8")

    return md_path, json_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Cross-scenario synthesis over Sisypy evidence packs."
    )
    ap.add_argument(
        "--reports-dir",
        default=None,
        help="Directory containing per-scenario evidence subdirectories "
        "(default: tests/agentic/reports/<tag>/).",
    )
    ap.add_argument(
        "--batch-summary",
        default=None,
        help="Optional path to a batch summary JSON file to merge.",
    )
    ap.add_argument(
        "--out-dir",
        default=None,
        help="Output directory for synthesis files (default: <reports_dir>/_synthesis/).",
    )
    args = ap.parse_args(argv)

    if args.reports_dir is None:
        print("error: --reports-dir is required", file=sys.stderr)
        return 1

    reports_dir = Path(args.reports_dir)
    if not reports_dir.is_absolute():
        reports_dir = (Path.cwd() / reports_dir).resolve()

    if not reports_dir.is_dir():
        print(f"error: reports directory not found: {reports_dir}", file=sys.stderr)
        return 1

    batch_summary = Path(args.batch_summary) if args.batch_summary else None
    out_dir = Path(args.out_dir) if args.out_dir else None

    md_path, json_path = synthesize(reports_dir, out_dir, batch_summary=batch_summary)

    print(f"wrote {md_path}")
    print(f"wrote {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
