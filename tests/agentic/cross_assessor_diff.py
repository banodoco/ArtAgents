"""Cross-vendor assessor comparison for frozen agentic evidence packs.

Usage:
    python -m tests.agentic.cross_assessor_diff --run-dir tests/agentic/reports/v12

The run dir may be either a batch dir containing batch.json (for example
reports/v12) or a single scenario report dir (for example
reports/v12-specific_transcribe). The script re-assesses each evidence pack
with Kimi via Fireworks and writes <run-dir>-cross-assessor.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("cross_assessor_diff: missing PyYAML; pip install pyyaml", file=sys.stderr)
    sys.exit(2)

AGENTIC_ROOT = Path(__file__).resolve().parent
SCENARIOS_DIR = AGENTIC_ROOT / "scenarios"
KIMI_MODEL = "fireworks:accounts/fireworks/models/kimi-k2p5"


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _scenario_summaries(run_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Return (summary_path, summary_payload) rows for a batch or scenario dir."""
    run_dir = run_dir.resolve()
    if (run_dir / "summary.json").is_file():
        payload = _read_json(run_dir / "summary.json")
        return [(run_dir / "summary.json", payload)] if isinstance(payload, dict) else []

    batch_path = run_dir / "batch.json"
    if batch_path.is_file():
        batch = _read_json(batch_path)
        prefix = run_dir.name
        rows: list[tuple[Path, dict[str, Any]]] = []
        if isinstance(batch, list):
            for item in batch:
                if not isinstance(item, dict):
                    continue
                scenario = item.get("scenario")
                if not isinstance(scenario, str):
                    continue
                summary_path = run_dir.parent / f"{prefix}-{scenario}" / "summary.json"
                if summary_path.is_file():
                    payload = _read_json(summary_path)
                    if isinstance(payload, dict):
                        rows.append((summary_path, payload))
                    continue
                rows.append((batch_path, item))
        return rows

    rows = []
    for summary_path in sorted(run_dir.glob("*/summary.json")):
        payload = _read_json(summary_path)
        if isinstance(payload, dict):
            rows.append((summary_path, payload))
    return rows


def _load_scenario(name: str) -> dict[str, Any]:
    path = SCENARIOS_DIR / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"scenario YAML not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"scenario YAML is not a mapping: {path}")
    return data


def _brief_text(agent: dict[str, Any], summary_path: Path) -> str:
    report_path_raw = agent.get("report_path")
    candidates: list[Path] = []
    if isinstance(report_path_raw, str) and report_path_raw:
        report_path = Path(report_path_raw)
        candidates.append(report_path.with_name(report_path.name.replace(".report.md", ".brief.md")))
    slug = agent.get("slug")
    if isinstance(slug, str):
        candidates.append(summary_path.parent / f"{slug}.brief.md")
    for path in candidates:
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
    return ""


def _passed_value(verdicts: dict[str, Any], qid: str) -> Any:
    value = verdicts.get(qid)
    if isinstance(value, dict):
        return value.get("passed")
    return None


def _rationale(verdicts: dict[str, Any], qid: str) -> str:
    value = verdicts.get(qid)
    if isinstance(value, dict):
        return str(value.get("rationale") or "")
    return "(missing verdict)"


def _machine_passes(agent: dict[str, Any]) -> list[bool]:
    out: list[bool] = []
    for outcome in (agent.get("criteria") or {}).values():
        if isinstance(outcome, dict) and not outcome.get("ungraded", False):
            out.append(bool(outcome.get("passed")))
    return out


def _kimi_outcome(scenario: dict[str, Any], agent: dict[str, Any], kimi: dict[str, Any]) -> str:
    try:
        from tests.agentic.auditor import _compute_three_tier_signals

        return str(
            _compute_three_tier_signals(
                scenario=scenario,
                assessor_block=kimi,
                machine_passes=_machine_passes(agent),
                canonical_bypass=agent.get("canonical_bypass"),
                actor_failed_marker=agent.get("actor_failed"),
            )["outcome"]
        )
    except Exception:
        return "needs_review"


def _format_bool(value: Any) -> str:
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    return "null"


def run_diff(run_dir: Path) -> tuple[Path, dict[str, Any]]:
    from tests.agentic.assessor import assess

    summaries = _scenario_summaries(run_dir)
    if not summaries:
        raise FileNotFoundError(f"no scenario summaries found under {run_dir}")

    scenario_rows: list[dict[str, Any]] = []
    total_agree = 0
    total_questions = 0
    flips: list[dict[str, str]] = []

    for summary_path, summary in summaries:
        scenario_name = str(summary.get("scenario") or summary_path.parent.name)
        scenario = _load_scenario(scenario_name)
        rubric = scenario.get("assessment") or {}
        agents = summary.get("agents") or []
        for agent in agents:
            if not isinstance(agent, dict):
                continue
            original = agent.get("assessor") or {}
            original_verdicts = original.get("verdicts") if isinstance(original, dict) else {}
            if not isinstance(original_verdicts, dict) or not original_verdicts:
                continue
            evidence_pack = agent.get("evidence_pack")
            if not isinstance(evidence_pack, str) or not Path(evidence_pack).is_dir():
                continue

            kimi = assess(
                evidence_pack=Path(evidence_pack),
                rubric=rubric,
                brief_text=_brief_text(agent, summary_path),
                model=KIMI_MODEL,
            )
            kimi_verdicts = kimi.get("verdicts") if isinstance(kimi, dict) else {}
            if not isinstance(kimi_verdicts, dict):
                kimi_verdicts = {}

            qids = sorted(set(original_verdicts) | set(kimi_verdicts))
            agreements = []
            disagreements = []
            for qid in qids:
                original_passed = _passed_value(original_verdicts, qid)
                kimi_passed = _passed_value(kimi_verdicts, qid)
                row = {
                    "qid": qid,
                    "original": original_passed,
                    "kimi": kimi_passed,
                    "original_rationale": _rationale(original_verdicts, qid),
                    "kimi_rationale": _rationale(kimi_verdicts, qid),
                }
                if original_passed == kimi_passed:
                    agreements.append(row)
                else:
                    disagreements.append(row)

            original_outcome = str(agent.get("outcome") or "")
            kimi_outcome = _kimi_outcome(scenario, agent, kimi)
            if (original_outcome == "passed") != (kimi_outcome == "passed"):
                flips.append(
                    {
                        "scenario": scenario_name,
                        "slug": str(agent.get("slug") or ""),
                        "original": original_outcome,
                        "kimi": kimi_outcome,
                    }
                )

            total_agree += len(agreements)
            total_questions += len(qids)
            scenario_rows.append(
                {
                    "scenario": scenario_name,
                    "slug": agent.get("slug"),
                    "original_model": original.get("model") if isinstance(original, dict) else None,
                    "kimi_model": kimi.get("model"),
                    "original_outcome": original_outcome,
                    "kimi_outcome": kimi_outcome,
                    "agreement_count": len(agreements),
                    "question_count": len(qids),
                    "disagreements": disagreements,
                    "kimi_ungraded": kimi.get("ungraded"),
                    "kimi_reason": kimi.get("reason"),
                }
            )

    out_path = run_dir.resolve().parent / f"{run_dir.resolve().name}-cross-assessor.md"
    payload = {
        "agreement_count": total_agree,
        "question_count": total_questions,
        "agreement_rate": (total_agree / total_questions) if total_questions else 0.0,
        "flips": flips,
        "scenarios": scenario_rows,
    }
    out_path.write_text(_format_report(run_dir, payload), encoding="utf-8")
    return out_path, payload


def _format_report(run_dir: Path, payload: dict[str, Any]) -> str:
    total_agree = int(payload["agreement_count"])
    total_questions = int(payload["question_count"])
    rate = float(payload["agreement_rate"])
    lines = [
        "# Cross-Assessor Diff",
        "",
        f"Run dir: `{run_dir}`",
        f"Overall agreement: {total_agree}/{total_questions} ({rate:.1%})",
        "",
    ]

    flips = payload.get("flips") or []
    if flips:
        lines.append("## Outcome Flips")
        lines.append("")
        for flip in flips:
            lines.append(
                f"- `{flip['scenario']}` / `{flip['slug']}`: "
                f"{flip['original']} -> {flip['kimi']}"
            )
        lines.append("")
    else:
        lines.extend(["## Outcome Flips", "", "None.", ""])

    lines.append("## Per Scenario Agreement")
    lines.append("")
    lines.append("| scenario | slug | original | Kimi | agreement |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in payload.get("scenarios") or []:
        agree = int(row["agreement_count"])
        total = int(row["question_count"])
        lines.append(
            f"| `{row['scenario']}` | `{row['slug']}` | "
            f"{row['original_outcome']} | {row['kimi_outcome']} | "
            f"{agree}/{total} |"
        )
    lines.append("")

    lines.append("## Disagreements")
    lines.append("")
    any_disagreement = False
    for row in payload.get("scenarios") or []:
        disagreements = row.get("disagreements") or []
        if not disagreements:
            continue
        any_disagreement = True
        lines.append(f"### {row['scenario']} / {row['slug']}")
        lines.append("")
        for item in disagreements:
            lines.append(
                f"- `{item['qid']}`: DeepSeek={_format_bool(item['original'])}, "
                f"Kimi={_format_bool(item['kimi'])}"
            )
            lines.append(f"  - DeepSeek: {item['original_rationale']}")
            lines.append(f"  - Kimi: {item['kimi_rationale']}")
        lines.append("")
    if not any_disagreement:
        lines.append("None.")
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tests.agentic.cross_assessor_diff")
    parser.add_argument("--run-dir", required=True, help="Batch or scenario report directory")
    args = parser.parse_args(argv)

    try:
        out_path, payload = run_diff(Path(args.run_dir))
    except Exception as exc:
        print(f"cross_assessor_diff: {exc}", file=sys.stderr)
        return 1

    rate = float(payload["agreement_rate"])
    print(
        f"wrote {out_path} — agreement "
        f"{payload['agreement_count']}/{payload['question_count']} ({rate:.1%})"
    )
    if payload.get("flips"):
        print(f"outcome flips: {len(payload['flips'])}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
