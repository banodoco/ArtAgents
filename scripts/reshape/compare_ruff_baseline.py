from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BASELINE_PATH = Path("scripts/reshape/baselines/ruff_astrid.json")
COMMAND = [
    sys.executable,
    "-m",
    "ruff",
    "check",
    ".",
    "--output-format",
    "json",
]


def _run() -> dict[str, Any]:
    try:
        proc = subprocess.run(COMMAND, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"ruff failed to execute: {exc}") from exc
    if proc.returncode not in (0, 1):
        detail = (proc.stderr or proc.stdout).strip() or "no diagnostic output"
        raise RuntimeError(f"ruff failed to execute (exit {proc.returncode}): {detail}")
    try:
        findings = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        detail = (proc.stderr or proc.stdout).strip() or "invalid JSON output"
        raise RuntimeError(f"ruff failed to execute: {detail}") from exc
    if not isinstance(findings, list):
        raise RuntimeError("ruff failed to execute: expected a JSON findings list")
    if proc.returncode == 1 and not findings:
        detail = (proc.stderr or proc.stdout).strip() or "no diagnostic output"
        raise RuntimeError(f"ruff failed to execute (exit 1): {detail}")
    return {
        "tool": "ruff",
        "scope": ["pyproject.toml [tool.ruff].include"],
        "command": COMMAND,
        "finding_count": len(findings),
        "code_counts": dict(collections.Counter(item["code"] for item in findings)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()

    try:
        current = _run()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.write_baseline:
        args.baseline.write_text(json.dumps(current, indent=2) + "\n")
        print(f"Wrote Ruff baseline to {args.baseline} ({current['finding_count']} findings)")
        return 0

    baseline = json.loads(args.baseline.read_text())
    baseline_count = int(baseline["finding_count"])
    current_count = int(current["finding_count"])
    print(f"Ruff findings: current={current_count} baseline={baseline_count}")
    if current_count <= baseline_count:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
