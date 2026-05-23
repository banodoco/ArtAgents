"""Re-audit helper: walk a tests/agentic/reports/<ts>-*/ family and
re-run audit_scenario against existing summary.json + evidence packs.

Usage:
    python -m tests.agentic._reaudit_v5 <run-tag>

Builds a per-scenario re-audit summary into
reports/<run-tag>-reaudit/<scenario>.summary.json and a top-level
reports/<run-tag>-reaudit/_index.json. Does NOT touch the original
v5 summaries on disk.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

try:
    import yaml
except ImportError:
    print("missing PyYAML", file=sys.stderr)
    sys.exit(2)

AGENTIC_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = AGENTIC_ROOT / "reports"
SCENARIOS_DIR = AGENTIC_ROOT / "scenarios"
BRIEFS_DIR = AGENTIC_ROOT / "briefs"

if str(AGENTIC_ROOT.parent.parent) not in sys.path:
    sys.path.insert(0, str(AGENTIC_ROOT.parent.parent))
from tests.agentic.auditor import audit_scenario  # noqa: E402


def _reaudit(run_tag: str) -> int:
    out_dir = REPORTS_DIR / f"{run_tag}-reaudit"
    out_dir.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []
    for rd in sorted(REPORTS_DIR.glob(f"{run_tag}-*")):
        if not rd.is_dir() or rd.name == f"{run_tag}-reaudit":
            continue
        scenario_name = rd.name[len(run_tag) + 1:]  # strip "<tag>-"
        scen_path = SCENARIOS_DIR / f"{scenario_name}.yaml"
        if not scen_path.is_file():
            continue
        scenario = yaml.safe_load(scen_path.read_text(encoding="utf-8"))
        # Build pseudo-invocations + results from disk.
        summary_path = rd / "summary.json"
        if not summary_path.is_file():
            continue
        old = json.loads(summary_path.read_text(encoding="utf-8"))
        invocations = []
        results = []
        for a in old.get("agents", []):
            slug = a["slug"]
            stdout_path = rd / f"{slug}.report.md"
            stderr_path = rd / f"{slug}.stderr.log"
            # Brief used the scenario's template — reuse it (we don't
            # have the rendered version on disk; brief_path on disk is
            # the rendered one).
            brief_path = rd / f"{slug}.brief.md"
            if not brief_path.is_file():
                # Fall back to the template (acceptable for re-audit).
                brief_path = BRIEFS_DIR / scenario["brief"]
            ev = rd / "evidence" / slug
            inv = SimpleNamespace(
                scenario_name=scenario_name,
                slug=slug,
                agent_id=slug,
                model=a.get("model", "unknown"),
                brief_path=brief_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            invocations.append(inv)
            results.append({
                "slug": slug,
                "agent_id": slug,
                "model": a.get("model", "unknown"),
                "returncode": a.get("returncode", 0),
                "elapsed_sec": a.get("elapsed_sec", 0.0),
                "report_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "evidence_pack": str(ev) if ev.is_dir() else None,
            })
        summary = audit_scenario(scenario, invocations, results, rd)
        out_file = out_dir / f"{scenario_name}.summary.json"
        out_file.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        # Brief index entry.
        bp_count = sum(
            1 for a in summary.get("agents", [])
            if isinstance(a.get("universal"), dict)
            and a["universal"].get("canonical_path_bypass")
        )
        contr = sum(
            len(a.get("universal", {}).get("contradictions") or [])
            for a in summary.get("agents", [])
            if isinstance(a.get("universal"), dict)
        )
        index.append({
            "scenario": scenario_name,
            "agents": len(summary.get("agents", [])),
            "passed": summary.get("aggregate", {}).get("passed", 0),
            "canonical_path_bypass_count": bp_count,
            "contradictions_total": contr,
        })
        print(
            f"{scenario_name}: "
            f"passed={summary['aggregate']['passed']}/{summary['aggregate']['total']} "
            f"bypass={bp_count} contradictions={contr}",
        )
    (out_dir / "_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"\nwrote {out_dir}")
    return 0


if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "20260518-115105"
    sys.exit(_reaudit(tag))
