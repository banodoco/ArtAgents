"""Runtime entrypoint for vibecomfy.*."""


from __future__ import annotations

from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('vibecomfy.run')
import argparse
import subprocess
import sys
from pathlib import Path

from astrid.core.cli_choices import add_choice_arg


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run VibeComfy workflow commands.")
    add_choice_arg(parser, "command", values=("run", "validate"))
    parser.add_argument("workflow", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return subprocess.run([sys.executable, "-m", "vibecomfy.cli", args.command, str(args.workflow)]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
