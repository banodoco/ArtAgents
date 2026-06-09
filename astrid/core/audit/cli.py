from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from astrid.core.contracts.errors import AstridError

from .graph import build_graph, load_ledger, verify_audit_ledger
from .report import _verification_failure_message, write_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render an Astrid run audit report.")
    parser.add_argument("--run", type=Path, required=True, help="Run directory containing audit/ledger.jsonl.")
    parser.add_argument("--out", type=Path, help="HTML output path. Defaults to <run>/audit/report.html.")
    parser.add_argument("--json", action="store_true", help="Print graph summary JSON instead of writing HTML.")
    verify_group = parser.add_mutually_exclusive_group()
    verify_group.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="Deprecated compatibility flag; verification is now enabled by default.",
    )
    verify_group.add_argument(
        "--no-verify",
        action="store_false",
        dest="verify",
        default=True,
        help="Skip audit ledger hash-chain verification before rendering. Emits a warning.",
    )
    args = parser.parse_args(argv)
    if not args.verify:
        print("warning: rendering audit report without ledger verification", file=sys.stderr)
    if args.verify:
        ok, line_number, reason = verify_audit_ledger(args.run)
        if not ok:
            print(_verification_failure_message(line_number, reason))
            return 1
    try:
        graph = build_graph(load_ledger(args.run))
    except FileNotFoundError as exc:
        raise AstridError(
            str(exc),
            recovery_command="run the audited command first to produce audit/ledger.jsonl",
        ) from exc
    if args.json:
        print(json.dumps(graph, indent=2))
        return 0
    output = write_report(args.run, args.out, verify=False)
    print(f"Wrote {output}")
    return 0
