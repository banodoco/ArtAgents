from __future__ import annotations

import argparse
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
    "--show-error-codes",
]
ERROR_RE = re.compile(r"^(.*?):(\d+):(?:(\d+):)? error: (.*?)\s+\[(.*?)\]$")


def _run() -> dict[str, Any]:
    proc = subprocess.run(COMMAND, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1, 2):
        if proc.stdout:
            sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)

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
    return {
        "tool": "mypy",
        "scope": COMMAND[3:5],
        "command": COMMAND,
        "finding_count": len(findings),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()

    current = _run()
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
