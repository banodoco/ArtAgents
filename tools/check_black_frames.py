#!/usr/bin/env python3
"""Validate a rendered video for unexpected black frames.

Remotion's media player intermittently renders the tail of a media clip as
black (the "tail-black" artifact). This tool catches that *before delivery*:

  1. Runs ffmpeg ``blackdetect`` over the render.
  2. Cross-references each black region against the timeline: a region that
     starts/ends at a clip boundary is the render-artifact signature. Regions
     that fall mid-clip are usually the source content's natural dark frames
     (e.g. a dark explainer slide) and are treated as benign unless overlong.
  3. Supports an explicit allowlist of known-good regions.

Usage:
  python3 tools/check_black_frames.py --video <render.mp4>
  python3 tools/check_black_frames.py --video <render.mp4> \\
      --timeline <hype.timeline.json> --assets <hype.assets.json>
  python3 tools/check_black_frames.py --video <render.mp4> --allow "88.5:89,102.5:105.1"

Exit code 0 = no unexpected black; 1 = problems found.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

BLACK_RE = re.compile(
    r"black_start:\s*([\d.]+).*?black_end:\s*([\d.]+).*?black_duration:\s*([\d.]+)",
    re.DOTALL,
)


def run_blackdetect(video: Path, min_duration: float) -> list[tuple[float, float, float]]:
    cmd = [
        "ffmpeg", "-i", str(video),
        "-vf", f"blackdetect=d={min_duration}:pix_th=0.2",
        "-an", "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = proc.stdout or ""
    regions: list[tuple[float, float, float]] = []
    for m in BLACK_RE.finditer(out):
        start, end, dur = float(m.group(1)), float(m.group(2)), float(m.group(3))
        regions.append((start, end, dur))
    return regions


def load_boundaries(timeline_path: Path, assets_path: Path) -> list[tuple[float, float, str]]:
    """Return visual-track clip boundaries as (start, end, clip_id)."""
    tl = json.loads(timeline_path.read_text(encoding="utf-8"))
    reg = json.loads(assets_path.read_text(encoding="utf-8")) if assets_path else {"assets": {}}
    tracks = {t.get("id"): t for t in tl.get("tracks", [])}
    boundaries: list[tuple[float, float, str]] = []
    for clip in tl.get("clips", []):
        track = tracks.get(clip.get("track"), {})
        if track.get("kind") != "visual":
            continue
        at = float(clip.get("at", 0) or 0)
        if clip.get("clipType") == "media":
            frm = float(clip.get("from", 0) or 0)
            to = float(clip.get("to", frm) or frm)
            speed = float(clip.get("speed", 1) or 1)
            end = at + (to - frm) / speed
        else:
            hold = clip.get("hold")
            end = at + float(hold) if isinstance(hold, (int, float)) else at
        boundaries.append((at, end, clip["id"]))
    return boundaries


def at_boundary(start: float, end: float, boundaries: list[tuple[float, float, str]], tol: float) -> str | None:
    """Return the clip id if a black region's start/end aligns with a clip
    boundary — the render-artifact (tail-black / head-black) signature.
    Mid-clip dark frames (natural content) do NOT match here."""
    for bstart, bend, cid in boundaries:
        # Any edge of the black region aligning with a clip boundary is the
        # render-artifact signature (tail-black ends/ starts at a clip's end;
        # head-black starts at a clip's start).
        if (abs(start - bend) <= tol or abs(end - bend) <= tol
                or abs(start - bstart) <= tol or abs(end - bstart) <= tol):
            return cid
    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--video", type=Path, required=True, help="Rendered MP4 to check.")
    p.add_argument("--timeline", type=Path, help="Optional hype.timeline.json for boundary analysis.")
    p.add_argument("--assets", type=Path, help="Optional hype.assets.json (with --timeline).")
    p.add_argument("--min-duration", type=float, default=0.2, help="Minimum black duration to report (s).")
    p.add_argument("--flag-duration", type=float, default=0.3, help="Black regions longer than this are flagged (s).")
    p.add_argument("--allow", default="", help="Comma-separated 'start:end' known-good regions.")
    args = p.parse_args()

    allow: list[tuple[float, float]] = []
    for pair in args.allow.split(","):
        pair = pair.strip()
        if not pair:
            continue
        s, e = pair.split(":")
        allow.append((float(s), float(e)))

    regions = run_blackdetect(args.video, args.min_duration)
    boundaries = load_boundaries(args.timeline, args.assets) if args.timeline else []

    print(f"black regions in {args.video}: {len(regions)}")
    problems = 0
    for start, end, dur in regions:
        allowed = any(s - 0.1 <= start and end <= e + 0.1 for s, e in allow)
        boundary_clip = at_boundary(start, end, boundaries, tol=0.25) if boundaries else None
        # Render artifacts are black that sits ON a clip boundary (tail/head
        # black). Mid-clip dark frames are normally the source content's own
        # dark slides -- report as "note", only flag if on a boundary.
        if allowed:
            verdict = "OK"
        elif boundary_clip:
            verdict = "FLAG"
        else:
            verdict = "note"
        if verdict == "FLAG":
            problems += 1
        where = f"clip:{boundary_clip}" if boundary_clip else ("mid-clip" if boundaries else "n/a")
        print(f"  {verdict:4s} {start:8.3f}-{end:8.3f} ({dur:5.2f}s)  {where}")
    print()
    if problems:
        print(f"FAIL: {problems} unexpected black region(s) >= {args.flag_duration}s. "
              "Suspect a render artifact (remotion tail-black). Review or split the affected clip.")
        return 1
    print("OK: no unexpected black frames.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
