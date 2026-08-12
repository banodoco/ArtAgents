"""Grok-driven zoom UX iteration (invoked via pytest for correct env).

Iterates: render root+zoom+range -> Grok critiques -> Grok agent patches the
layout code -> re-render -> repeat until Grok rates every zoom >= 4.
Marked `grok-iter` (opt-in; NOT in default CI).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from astrid.core import gateway
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO

from tests.packs.rendering.test_timeline_visualize_executor import _prepare_project, _invoke
from astrid.core.timeline.events.schema.serialize import with_event_hash
from astrid.core.timeline.events.schema.types import TimelineEvent

pytestmark = pytest.mark.grok_iter

GROK = "/Users/peteromalley/.grok/bin/grok"
MODEL = "grok-4.6"
FAL = Path("tests/fixtures/timeline_visualize/storyboard_fal")


def grok(prompt: str, timeout: int = 240) -> str:
    cmd = ["script", "-q", "/dev/null", GROK, "--single", prompt, "-m", MODEL]
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    out = r.stdout
    return out[2:] if out.startswith("^D") else out


def build_pack(tmp, slug: str) -> Path:
    import hashlib
    pr, td = _prepare_project(tmp, slug)
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


CRITIQUE = """You are a UX reviewer for a timeline visualization. You see rendered pages at
THREE zoom levels: ROOT (full overview), ZOOM (focused clip), RANGE (window zoom).
IMAGE PATHS (in order): 
{paths}

The pages are 1920x1080. Clip cards must show FULL source frames (contain-fit,
never cropped) with the lane area used well (no large dead space). The cue
line (FOCUS/PARENT/SOURCE/NEXT) must be readable.

Critique each zoom: (1) full frame visible, not cropped? dead space that
should hold a larger frame? (2) cue + labels legible? (3) focused object the
clear subject? (4) exact concrete change?

Respond with ONE JSON object:
{{"root": {{"rating":1-5,"dead_space":bool,"frame_cropped":bool,"confusing":[],"fix":"..."}},
 "zoom": {{...}}, "range": {{...}},
 "blocking": <true if any rating<4 or cropped or dead_space>,
 "priority_fixes": ["concrete fix", ...]}}
Under 500 words. Be specific about geometry."""


@pytest.mark.timeout(3600)
def test_grok_iterates_zoom_ux(tmp_projects_root: Path) -> None:
    rounds = 4
    root_pack = build_pack(tmp_projects_root, "grokiter")
    zoom_pack = drill(root_pack, "TL01.CL02")
    packs = {"root": root_pack, "zoom": zoom_pack}
    for round_no in range(1, rounds + 1):
        paths = [str(packs[k] / "PG001.png") for k in ("root", "zoom")]
        raw = grok(CRITIQUE.format(paths="\n".join(paths)))
        verdict = None
        try:
            start = raw.find("{")
            verdict = json.loads(raw[start: raw.rfind("}") + 1])
        except Exception:
            pytest.fail(f"no JSON verdict from grok: {raw[-400:]}")
        blocking = verdict.get("blocking", False)
        fixes = verdict.get("priority_fixes", [])
        (Path("/tmp") / f"grok-iter-{round_no}.json").write_text(json.dumps(verdict, indent=2))
        if not blocking:
            return
        patch_prompt = (
            "You are fixing timeline visualization layout code. The UX reviewer requested: "
            + json.dumps(fixes)
            + "\n\nFiles (worktree /Users/peteromalley/Documents/.megaplan-worktrees/astrid-timeline-vlm): "
            "astrid/packs/rendering/executors/timeline_visualize/layout.py and render_png.py. "
            "Apply minimal surgical fixes (lane heights, positions, frame sizing, cue placement). "
            "Preserve: deterministic output, 1920x1080, no datetime. Report exact changes."
        )
        patch_cmd = ["script", "-q", "/dev/null", GROK, "--single", patch_prompt, "--always-approve", "-m", MODEL]
        subprocess.run(patch_cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=500,
                       cwd=Path(__file__).resolve().parents[3])
        root_pack = build_pack(tmp_projects_root, f"grokiter{round_no}")
        zoom_pack = drill(root_pack, "TL01.CL02")
        packs = {"root": root_pack, "zoom": zoom_pack}
    pytest.fail("grok iteration cap reached without approval")
