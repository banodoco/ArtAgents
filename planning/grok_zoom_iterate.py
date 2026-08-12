"""Grok-driven zoom UX iteration harness.

Renders the fal storyboard at multiple zoom levels (root, clip-zoom, range),
sends the pages to Grok 4.6 for critique, collects its concrete fix requests,
and applies them to layout.py/render_png.py — then re-renders and repeats
until Grok rates every zoom >= 4/5 with no blocking confusion.

Usage: python3 planning/grok_zoom_iterate.py [--rounds N]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

GROK = "/Users/peteromalley/.grok/bin/grok"
MODEL = "grok-4.6"
WORKTREE = Path("/Users/peteromalley/Documents/.megaplan-worktrees/astrid-timeline-vlm")
FAL = WORKTREE / "tests/fixtures/timeline_visualize/storyboard_fal"

sys.path.insert(0, str(WORKTREE / "tests"))
os.environ["ASTRID_HOME"] = tempfile.mkdtemp()
os.environ["ASTRID_PROJECTS_ROOT"] = tempfile.mkdtemp()
os.environ.pop("ASTRID_SESSION_ID", None)
os.environ.setdefault("ASTRID_NO_NUDGE", "1")


def grok(prompt: str, timeout: int = 240) -> str:
    cmd = ["script", "-q", "/dev/null", GROK, "--single", prompt, "-m", MODEL]
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    out = r.stdout
    return out[2:] if out.startswith("^D") else out


def build_pack(slug: str) -> Path:
    """Build a fal-storyboard project + root pack; return pack root."""
    from tests.packs.rendering.test_timeline_visualize_executor import _prepare_project, _invoke
    from astrid.core.timeline.events.schema.serialize import with_event_hash
    from astrid.core.timeline.events.schema.types import TimelineEvent
    import hashlib, shutil

    pr, td = _prepare_project(Path(tempfile.mkdtemp()), slug)
    src = pr / "sources"
    for i in range(1, 5):
        (src / f"fal-frame-{i}.png").write_bytes((FAL / f"plant-frame-{i}.png").read_bytes())
    reg = json.loads((td / "registry.json").read_text())
    for i, key in enumerate(["plant-frame-1", "plant-frame-2", "plant-frame-3", "plant-frame-4"], start=1):
        e = reg["assets"][key]
        e["file"] = f"fal-frame-{i}.png"
        e["content_sha256"] = hashlib.sha256((FAL / f"plant-frame-{i}.png").read_bytes()).hexdigest()
    (td / "registry.json").write_text(json.dumps(reg, sort_keys=True, separators=(",", ":")))
    lines = [json.loads(l) for l in (td / "assembly.jsonl").read_text().splitlines() if l.strip()]
    for ev in lines:
        if ev.get("kind") == "timeline.asset_registry_replaced":
            ev["payload"] = {"registry": {"assets": reg["assets"]}}
    prev = None
    for ev in lines:
        t = TimelineEvent.from_dict(ev)
        u = with_event_hash(t, prev_hash=prev)
        ev["prev_hash"] = u.prev_hash
        ev["hash"] = u.hash
        prev = u.hash
    (td / "assembly.jsonl").write_text("\n".join(json.dumps(e, sort_keys=True, separators=(",", ":")) for e in lines) + "\n")
    r = _invoke(slug, timeline_source=str(td), formats=["png", "svg", "md"])
    assert r.ok, r.error
    return Path(r.outputs["pack_root"])


def drill(pack_root: Path, focus: str) -> Path:
    """Run the focus_context action for `focus`; return the child pack root."""
    from astrid.core import gateway
    from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
    from contextlib import redirect_stdout, redirect_stderr
    from io import StringIO

    ai = json.load(open(pack_root / "action-index.json"))
    action = ai["entries"][focus]["actions"]["focus_context"]
    argv = action["argv"][3:]
    for i, tok in enumerate(argv):
        if tok == "--from-view" and i + 1 < len(argv):
            argv[i + 1] = str((pack_root / argv[i + 1]).resolve())
    stdout, stderr = StringIO(), StringIO()
    os.environ.pop(ASTRID_SESSION_ID_ENV, None)
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            rc = gateway.main(argv)
        except SystemExit as exc:
            rc = int(exc.code) if isinstance(exc.code, int) else 2
    assert rc == 0, stderr.getvalue()
    return Path(json.loads(stdout.getvalue())["manifest_path"]).parent


CRITIQUE_PROMPT = """You are a UX reviewer for a timeline visualization. You see rendered pages at
THREE zoom levels of the same storyboard:
- ROOT: the full timeline overview.
- ZOOM: a focused clip (large frame, neighbors visible).
- RANGE: a time-window zoom.

IMAGE PATHS (in that order):
{paths}

The pages are 1920x1080. The clip cards should show the FULL source frames
(contain-fit, never cropped), with the lane area used well (no large dead
space below the frames). The cue line (FOCUS/PARENT/SOURCE/NEXT) must be
readable.

Critique each zoom level for:
1. Is the full frame visible (not cropped)? Is there dead space that should
   hold a larger frame or useful content?
2. Are the cue line and labels legible?
3. Is the focused object clearly the subject?
4. What EXACTLY should change (concrete, actionable)?

Respond with ONE JSON object:
{{"root": {{"rating": 1-5, "dead_space": <true/false>, "frame_cropped": <true/false>, "confusing": [...], "fix": "..."}},
 "zoom": {{...same...}},
 "range": {{...same...}},
 "blocking": <true if any rating < 4 or any frame_cropped/dead_space>,
 "priority_fixes": ["concrete fix 1", "concrete fix 2", ...]}}
Under 500 words. Be specific about geometry (heights, positions)."""


def main() -> int:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    root_pack = build_pack("grokiter")
    zoom_pack = drill(root_pack, "TL01.CL02")
    range_pack = drill(root_pack, "TL01.RG01") if "TL01.RG01" in json.load(
        open(root_pack / "action-index.json"))["entries"] else None
    packs = {"root": root_pack, "zoom": zoom_pack}
    if range_pack:
        packs["range"] = range_pack
    for round_no in range(1, rounds + 1):
        paths = [str(packs[k] / "PG001.png") for k in ("root", "zoom", "range") if k in packs]
        print(f"=== iteration {round_no}: rendering {paths}", flush=True)
        prompt = CRITIQUE_PROMPT.format(paths="\n".join(paths))
        raw = grok(prompt)
        verdict = None
        try:
            start = raw.find("{")
            verdict = json.loads(raw[start: raw.rfind("}") + 1])
        except Exception:
            print("no JSON verdict; raw tail:", raw[-400:], flush=True)
            continue
        blocking = verdict.get("blocking", False)
        fixes = verdict.get("priority_fixes", [])
        print(f"blocking={blocking} fixes={fixes}", flush=True)
        (Path("/tmp") / f"grok-iter-{round_no}.json").write_text(json.dumps(verdict, indent=2))
        if not blocking:
            print(f"=== Grok approves after {round_no} iterations", flush=True)
            return 0
        # Ask grok for the concrete code-level patch, applied by a grok agent
        # with workspace-write (the proven executor path).
        patch_prompt = (
            "You are fixing the layout code. The UX reviewer asked for these fixes: "
            + json.dumps(fixes)
            + "\n\nIn /Users/peteromalley/Documents/.megaplan-worktrees/astrid-timeline-vlm, "
            "the time-scaled layout is astrid/packs/rendering/executors/timeline_visualize/layout.py "
            "and the PNG renderer is render_png.py. Apply the fixes to those files "
            "(lane heights, positions, frame sizing, cue placement). Read the current code first, "
            "make minimal surgical edits, do NOT break the frozen invariants "
            "(deterministic output, 1920x1080, no datetime). Then report the exact changes made."
        )
        patch_cmd = [
            "script", "-q", "/dev/null", GROK, "--single", patch_prompt,
            "--always-approve", "-m", MODEL,
        ]
        patched = subprocess.run(
            patch_cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=500,
            cwd=WORKTREE,
        ).stdout
        patched = patched[2:] if patched.startswith("^D") else patched
        print("patch output tail:", patched[-400:], flush=True)
        # rebuild with the patched code
        root_pack = build_pack(f"grokiter{round_no}")
        zoom_pack = drill(root_pack, "TL01.CL02")
        packs = {"root": root_pack, "zoom": zoom_pack}
    print("=== iteration cap reached; final state saved", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
