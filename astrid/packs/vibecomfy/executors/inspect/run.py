"""Canonical runtime entrypoint for ``vibecomfy.inspect``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint("vibecomfy.inspect")

from astrid.packs.vibecomfy.executors._workflow_ir import (  # noqa: E402
    WorkflowIrBridgeError,
    inspect_workflow,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Project a ComfyUI UI graph through VibeComfy's readable IR."
    )
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inspect_workflow(args.workflow, args.out)
    except WorkflowIrBridgeError as exc:
        print(f"vibecomfy.inspect: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
