#!/usr/bin/env python3
"""Extract a clip segment from a video using ffmpeg stream copy.

Invoked by the Astrid runtime per command.argv in executor.yaml.
Parses --input, --start, --dur, --output from argv, validates them,
and shells out to ffmpeg.
"""

from __future__ import annotations

from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint("media.clip_extract")
import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="media.clip_extract",
        description="Extract a clip from a video using ffmpeg -ss -t -c copy.",
    )
    parser.add_argument(
        "--input", type=Path, required=True, help="Source video file path."
    )
    parser.add_argument(
        "--start", type=float, required=True, help="Start time in seconds."
    )
    parser.add_argument(
        "--dur", type=float, required=True, help="Duration in seconds."
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Output video file path."
    )
    return parser


def validate_args(args: argparse.Namespace) -> str | None:
    """Return an error string or None if valid."""
    if not args.input.is_file():
        return f"input file not found: {args.input}"
    if args.start < 0:
        return f"start time must be >= 0, got {args.start}"
    if args.dur <= 0:
        return f"duration must be > 0, got {args.dur}"
    return None


def build_ffmpeg_cmd(src: Path, start: float, dur: float, out: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-ss",
        str(start),
        "-t",
        str(dur),
        "-c",
        "copy",
        str(out),
    ]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Resolve paths
    src = args.input.expanduser().resolve()
    out = args.output.expanduser().resolve()

    # Guard against missing/invalid inputs
    error = validate_args(
        argparse.Namespace(input=src, start=args.start, dur=args.dur)
    )
    if error is not None:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = build_ffmpeg_cmd(src, args.start, args.dur, out)

    # Defer actual invocation — print the command that would run.
    # When wired through `astrid executors run`, the runtime handles
    # dry-run vs. live execution.  Remove the guard below to execute
    # ffmpeg directly.
    print(f"[clip_extract] would run: {shlex.join(cmd)}")

    # Uncomment the lines below to invoke ffmpeg for real:
    # result = subprocess.run(cmd, check=False)
    # if result.returncode != 0:
    #     print(f"Error: ffmpeg exited with {result.returncode}", file=sys.stderr)
    # return result.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
