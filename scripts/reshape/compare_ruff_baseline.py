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
    proc = subprocess.run(COMMAND, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        if proc.stdout:
            sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)
    findings = json.loads(proc.stdout or "[]")
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

    current = _run()
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
