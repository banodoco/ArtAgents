#!/usr/bin/env python3
"""Probe the REAL alpha artifact: render a stamped timeline via the backend's
execution helper and ffprobe the output. Bypasses declared-profile validation
so we can record the ground truth."""
import json
import subprocess
import tempfile
from pathlib import Path

from astrid.core import timeline
from astrid.packs.rendering.backends.remotion import run as remotion

ROOT = Path("/Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan")
PROJECT = ROOT / "remotion"

tmp = Path(tempfile.mkdtemp(prefix="b4-probe-"))
timeline_path = tmp / "stamped.timeline.json"
assets_path = tmp / "assets.json"
out_path = tmp / "alpha.webm"

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
timeline.save_registry({"assets": {}}, assets_path)

details = remotion._execute_remotion(
    timeline_path,
    assets_path,
    out_path,
    provenance_out_path=tmp / "provenance.json",
    project_dir=PROJECT,
    composition_id="ThreeTimelineComposition",
    theme_path=None,
    min_free_gb=None,
)
print("staged:", out_path, out_path.stat().st_size, "bytes")

probe = subprocess.run(
    [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_name,codec_type,pix_fmt,time_base,avg_frame_rate,width,height",
        "-show_entries", "format=format_name,duration",
        "-of", "json",
        str(out_path),
    ],
    check=True, capture_output=True, text=True,
).stdout
print("PROBE:", probe)
print("TMPDIR:", tmp)
