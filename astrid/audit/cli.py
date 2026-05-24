from __future__ import annotations

import argparse
import json
from pathlib import Path

from .graph import build_graph, load_ledger, verify_audit_ledger
from .report import write_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render an Astrid run audit report.")
    parser.add_argument("--run", type=Path, required=True, help="Run directory containing audit/ledger.jsonl.")
    parser.add_argument("--out", type=Path, help="HTML output path. Defaults to <run>/audit/report.html.")
    parser.add_argument("--json", action="store_true", help="Print graph summary JSON instead of writing HTML.")
    parser.add_argument("--verify", action="store_true", help="Verify audit ledger hash-chain integrity before rendering.")
    args = parser.parse_args(argv)
    if args.verify:
        ok, line_number, reason = verify_audit_ledger(args.run)
        if not ok:
            location = f" line {line_number}" if line_number is not None else ""
            print(f"audit ledger verification failed{location}: {reason}")
            return 1
    try:
        graph = build_graph(load_ledger(args.run))
    except FileNotFoundError as exc:
        raise SystemExit(str(exc))
    if args.json:
        print(json.dumps(graph, indent=2))
        return 0
    output = write_report(args.run, args.out)
    print(f"Wrote {output}")
    return 0
