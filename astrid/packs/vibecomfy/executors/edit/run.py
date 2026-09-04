"""Canonical runtime entrypoint for ``vibecomfy.edit``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint("vibecomfy.edit")

from astrid.packs.vibecomfy.executors._workflow_ir import (  # noqa: E402
    WorkflowIrBridgeError,
    edit_workflow,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply one atomic VibeComfy typed-delta batch to a UI graph."
    )
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--operations", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        edit_workflow(args.workflow, args.operations, args.out)
    except WorkflowIrBridgeError as exc:
        print(f"vibecomfy.edit: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
