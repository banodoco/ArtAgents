#!/usr/bin/env python3
"""Render a timeline and gate on black-frame validation.

Wraps the Astrid ``rendering.render`` executor with the black-frame checker
(``check_black_frames.py``). After a successful render it runs blackdetect and
FAILS (exit 1) if any unexpected black region is found — the remotion
"tail-black" render artifact — so a bad render never ships silently.

Usage:
  python3 tools/render_and_check.py \\
      --timeline <hype.timeline.json> --assets <hype.assets.json> \\
      --out <render-dir> [extra render inputs...]

Exit 0 = render ok and no black artifacts. 1 = render failed or black issues.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--timeline", type=Path, required=True)
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True, help="Render output dir.")
    p.add_argument("--min-duration", type=float, default=0.2)
    p.add_argument("--flag-duration", type=float, default=0.3)
    p.add_argument("--allow", default="", help="Known-good black regions (start:end, comma separated).")
    p.add_argument("--bypass", action="store_true", help="Skip black-frame validation (force pass).")
    p.add_argument("--python-exec", default=sys.executable)
    args = p.parse_args()

    py = args.python_exec
    render_cmd = [
        py, "-m", "astrid", "executors", "run", "rendering.render",
        "--out", str(args.out),
        "--input", f"timeline={args.timeline}",
        "--input", f"assets_registry={args.assets}",
    ]
    print(">> rendering...", flush=True)
    r = subprocess.run(render_cmd, cwd=REPO)
    if r.returncode != 0:
        print("FAIL: render exited non-zero.", flush=True)
        return 1

    video = args.out / "hype.mp4"
    if not video.exists():
        print(f"FAIL: expected render output {video} not found.", flush=True)
        return 1

    if args.bypass:
        print(">> black-frame validation BYPASSED (--bypass).", flush=True)
        print("OK: rendered (validation skipped).", flush=True)
        return 0

    check_cmd = [
        py, str(REPO / "tools" / "check_black_frames.py"),
        "--video", str(video),
        "--timeline", str(args.timeline),
        "--assets", str(args.assets),
        "--min-duration", str(args.min_duration),
        "--flag-duration", str(args.flag_duration),
    ]
    if args.allow:
        check_cmd += ["--allow", args.allow]
    print(">> validating black frames...", flush=True)
    c = subprocess.run(check_cmd, cwd=REPO)
    if c.returncode != 0:
        print("FAIL: black-frame validation found issues.", flush=True)
        return 1

    print("OK: rendered and validated (no black-frame artifacts).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
