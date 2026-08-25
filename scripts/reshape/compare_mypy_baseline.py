from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

BASELINE_PATH = Path("scripts/reshape/baselines/mypy_astrid.json")
COMMAND = [
    sys.executable,
    "-m",
    "mypy",
    "astrid",
    "scripts/reshape",
    "--hide-error-context",
    "--no-color-output",
    "--no-pretty",
    "--show-error-codes",
]
ERROR_RE = re.compile(r"^(.*?):(\d+):(?:(\d+):)? error: (.*?)\s+\[(.*?)\]$")


def _run() -> dict[str, Any]:
    try:
        proc = subprocess.run(COMMAND, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"mypy failed to execute: {exc}") from exc
    findings = []
    for line in (proc.stdout.splitlines() + proc.stderr.splitlines()):
        match = ERROR_RE.match(line)
        if not match:
            continue
        findings.append(
            {
                "path": match.group(1),
                "line": int(match.group(2)),
                "column": int(match.group(3) or 0),
                "message": match.group(4),
                "code": match.group(5),
            }
        )
    if proc.returncode not in (0, 1) or (proc.returncode == 1 and not findings):
        detail = (proc.stderr or proc.stdout).strip() or "no diagnostic output"
        raise RuntimeError(f"mypy failed to execute (exit {proc.returncode}): {detail}")
    return {
        "tool": "mypy",
        "scope": COMMAND[3:5],
        "command": COMMAND,
        "finding_count": len(findings),
        "code_counts": dict(
            sorted(collections.Counter(item["code"] for item in findings).items())
        ),
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
        print(f"Wrote mypy baseline to {args.baseline} ({current['finding_count']} findings)")
        return 0

    baseline = json.loads(args.baseline.read_text())
    baseline_count = int(baseline["finding_count"])
    current_count = int(current["finding_count"])
    print(f"Mypy findings: current={current_count} baseline={baseline_count}")
    if current_count <= baseline_count:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
