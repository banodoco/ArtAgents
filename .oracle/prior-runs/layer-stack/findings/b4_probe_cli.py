#!/usr/bin/env python3
"""Direct CLI probe: build props + run remotion render manually with the B4
flags, probe the artifact. Isolates CLI flag behavior from backend code."""
import json
import subprocess
import tempfile
from pathlib import Path

from astrid.core import timeline
from astrid.packs.rendering.backends._shared import _serialize_timeline, _theme_for_props

ROOT = Path("/Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan")
PROJECT = ROOT / "remotion"

tmp = Path(tempfile.mkdtemp(prefix="b4-cli-"))
timeline_path = tmp / "stamped.timeline.json"
timeline.save_timeline(
    {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {
                "canvas": {"width": 320, "height": 180, "fps": 24},
                "background": "#1a1a2e",
            }
        },
        "tracks": [{"id": "v1", "kind": "visual", "label": "Title"}],
        "clips": [
            {
                "id": "title",
                "at": 0.0,
                "track": "v1",
                "clipType": "text",
                "hold": 0.5,
                "text": {"content": "ALPHA PROBE", "fontSize": 64, "color": "#ffffff"},
                "params": {"weight": 700},
            }
        ],
        "metadata": {"astrid_layer": {"z": 1, "alpha": True}},
    },
    timeline_path,
)
props = {
    "timeline": _serialize_timeline(timeline_path),
    "assets": {"assets": {}},
    "theme": _theme_for_props(PROJECT / "_active_theme" / "theme.json" if False else ROOT / "themes" / "banodoco-default" / "theme.json"),
}
props_path = tmp / "props.json"
props_path.write_text(json.dumps(props), encoding="utf-8")
out_path = tmp / "alpha-cli.webm"

env = {"PATH": "/Users/peteromalley/.nvm/versions/node/v24.17.0/bin:" + subprocess.os.environ.get("PATH", "")}
cmd = [
    "npx", "remotion", "render", "ThreeTimelineComposition",
    "--props", str(props_path),
    "--output", str(out_path),
    "--allow-html-in-canvas",
    "--enforce-audio-track",
    "--image-format=png",
    "--pixel-format=yuva420p",
    "--codec=vp9",
]
result = subprocess.run(cmd, cwd=str(PROJECT), env=env, capture_output=True, text=True)
print("returncode:", result.returncode)
if result.returncode != 0:
    print("STDERR:", result.stderr[-3000:])
    raise SystemExit(1)
print("OK:", out_path, out_path.stat().st_size)

probe = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,codec_type,pix_fmt,time_base", "-show_entries", "format=format_name", "-of", "json", str(out_path)],
    check=True, capture_output=True, text=True,
).stdout
print("PROBE:", probe)
