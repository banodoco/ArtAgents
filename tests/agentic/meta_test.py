"""Calibration test: compare assessor verdicts to hand-graded ground truth.

For each scenario with a ground_truth/<scenario>.expected.json file,
loads the corresponding assessor verdict (preferring the latest
re-audit summary under reports/) and computes per-question agreement
at three confidence thresholds {0.0, 0.5, 0.8}.

Prints a per-scenario + overall agreement table.

Usage:
    python -m tests.agentic.meta_test
    python -m tests.agentic.meta_test --reaudit-dir 20260518-115105-reaudit
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

AGENTIC_ROOT = Path(__file__).resolve().parent
GROUND_TRUTH_DIR = AGENTIC_ROOT / "ground_truth"
REPORTS_DIR = AGENTIC_ROOT / "reports"

CONFIDENCE_THRESHOLDS = (0.0, 0.5, 0.8)


def _load_ground_truth() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(GROUND_TRUTH_DIR.glob("*.expected.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            name = data.get("scenario") or p.stem.split(".")[0]
            out[name] = data
        except Exception as exc:
            print(f"warn: failed to load {p}: {exc}", file=sys.stderr)
    return out


def _load_reaudit_summaries(reaudit_dir: Path) -> dict[str, dict[str, Any]]:
    """Map scenario_name -> per-agent assessor record. We pick the first
    agent in each scenario summary (ground truth is per-scenario and
    matches the first-agent run for our 13-scenario v5 set)."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(reaudit_dir.glob("*.summary.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        name = data.get("scenario") or p.stem.split(".")[0]
        agents = data.get("agents") or []
        for a in agents:
            ass = a.get("assessor")
            if isinstance(ass, dict) and ass.get("verdicts"):
                out[name] = ass
                break
    return out


def _verdict_match(gt_passed: Any, asr_v: dict[str, Any], threshold: float) -> bool:
    """True iff at confidence ≥ threshold the assessor's verdict equals
    ground truth (or both are null). Below the threshold, the assessor's
    verdict is treated as ungraded (counted as a non-match unless gt is
    also null)."""
    asr_passed = asr_v.get("passed")
    conf_raw = asr_v.get("confidence")
    try:
        conf = float(conf_raw) if conf_raw is not None else 0.0
    except (TypeError, ValueError):
        conf = 0.0

    if conf < threshold:
        # Assessor low-confidence: treat as null/ungraded for matching.
        asr_effective = None
    else:
        asr_effective = asr_passed

    # Compare. Both null → match. Both bool and equal → match. Else no.
    if gt_passed is None and asr_effective is None:
        return True
    if gt_passed is None or asr_effective is None:
        return False
    return bool(gt_passed) == bool(asr_effective)


def _calibrate(
    ground_truth: dict[str, dict[str, Any]],
    assessor_by_scenario: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    overall = {c: {"matches": 0, "total": 0} for c in CONFIDENCE_THRESHOLDS}
    for scenario, gt in sorted(ground_truth.items()):
        gt_verdicts = gt.get("verdicts") or {}
        asr = assessor_by_scenario.get(scenario)
        if asr is None:
            print(f"warn: no assessor record for {scenario}", file=sys.stderr)
            continue
        asr_verdicts = asr.get("verdicts") or {}
        per_threshold: dict[float, dict[str, int]] = {
            c: {"matches": 0, "total": 0} for c in CONFIDENCE_THRESHOLDS
        }
        missing: list[str] = []
        for qid, gt_v in gt_verdicts.items():
            if qid not in asr_verdicts:
                missing.append(qid)
                continue
            for c in CONFIDENCE_THRESHOLDS:
                ok = _verdict_match(gt_v.get("passed"), asr_verdicts[qid], c)
                per_threshold[c]["total"] += 1
                if ok:
                    per_threshold[c]["matches"] += 1
                overall[c]["total"] += 1
                if ok:
                    overall[c]["matches"] += 1
        rows.append({
            "scenario": scenario,
            "per_threshold": per_threshold,
            "missing_questions": missing,
        })
    return {"rows": rows, "overall": overall}


def _format_report(calibration: dict[str, Any]) -> str:
    lines = ["# Meta-test calibration report", ""]
    lines.append("Per-scenario agreement (matches/total) at C ∈ {0.0, 0.5, 0.8}:")
    lines.append("")
    lines.append("| scenario | C=0.0 | C=0.5 | C=0.8 |")
    lines.append("| --- | --- | --- | --- |")
    for row in calibration["rows"]:
        pt = row["per_threshold"]
        cells = [
            f"{pt[c]['matches']}/{pt[c]['total']}"
            for c in CONFIDENCE_THRESHOLDS
        ]
        lines.append(f"| {row['scenario']} | {cells[0]} | {cells[1]} | {cells[2]} |")
        if row["missing_questions"]:
            lines.append(
                f"  *missing questions in assessor output:* "
                f"{', '.join(row['missing_questions'])}"
            )
    overall = calibration["overall"]
    lines.append("")
    lines.append("**Overall:**")
    for c in CONFIDENCE_THRESHOLDS:
        o = overall[c]
        rate = (o["matches"] / o["total"] * 100) if o["total"] else 0.0
        lines.append(f"- C={c}: {o['matches']}/{o['total']} ({rate:.1f}%)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--reaudit-dir",
        default="20260518-115105-reaudit",
        help="reports/<this>/ subdirectory holding *.summary.json files",
    )
    args = ap.parse_args(argv)

    reaudit_dir = REPORTS_DIR / args.reaudit_dir
    if not reaudit_dir.is_dir():
        print(f"reaudit dir not found: {reaudit_dir}", file=sys.stderr)
        return 1

    gt = _load_ground_truth()
    if not gt:
        print("no ground truth files found", file=sys.stderr)
        return 1
    asr = _load_reaudit_summaries(reaudit_dir)

    calibration = _calibrate(gt, asr)
    print(_format_report(calibration))

    # Persist alongside the reaudit dir for traceability.
    out = reaudit_dir / "meta_test.json"
    out.write_text(json.dumps(calibration, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {out}")

    overall_c0 = calibration["overall"][0.0]
    rate = (overall_c0["matches"] / overall_c0["total"]) if overall_c0["total"] else 0.0
    return 0 if rate >= 0.80 else 2


if __name__ == "__main__":
    sys.exit(main())
