"""Shared pending-command helpers for Sprint 0 operator shims."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence


def pending_main(command: str, owner_task: str, argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=command,
        description=(
            f"{command} is the canonical Sprint 0 command path. "
            f"Its implementation is owned by {owner_task}."
        ),
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Print why this command exists before its implementation lands.",
    )
    args, remaining = parser.parse_known_args(argv)

    if args.explain:
        print(
            f"{command} is reserved as the canonical Sprint 0 operator entrypoint. "
            f"{owner_task} will replace this placeholder with the implementation."
        )
        return 0

    print(
        f"ERROR: {command} is the canonical Sprint 0 entrypoint, but its "
        f"implementation has not landed yet ({owner_task}). "
        "Use --explain for context.",
        file=sys.stderr,
    )
    if remaining:
        print(f"Received arguments: {' '.join(remaining)}", file=sys.stderr)
    return 2
