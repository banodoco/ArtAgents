"""Tests for the foley.foley_review executor.

Covers review.html generation and universal result manifest creation.
"""

from __future__ import annotations

import json
from pathlib import Path

from astrid.packs.foley.executors.foley_review import run as foley_review


def test_generates_review_html_and_writes_result_manifest(tmp_path: Path) -> None:
    """Prove review.html output and manifest creation from a tiles.json input."""
    # Build a minimal tiles.json manifest
    tiles_manifest = {
        "tiles": [
            {
                "id": "tile_001",
                "rect": [0, 0, 640, 360],
                "rect_norm": [0.0, 0.0, 1.0, 1.0],
                "tile_clip": "clips/tile_001.mp4",
                "foley_audio": "audio/tile_001.wav",
                "prompt": "wind blowing through trees",
            },
            {
                "id": "tile_002",
                "rect": [640, 0, 1280, 360],
                "rect_norm": [0.5, 0.0, 1.0, 1.0],
                "tile_clip": "clips/tile_002.mp4",
                "foley_audio": "audio/tile_002.wav",
                "prompt": "footsteps on gravel",
            },
        ],
        "grid": {"cols": 2, "rows": 1, "overlap": 0},
        "video": "source_video.mp4",
        "trimmed_duration": 10.0,
    }

    manifest_dir = tmp_path / "foley_input"
    manifest_dir.mkdir()
    manifest_path = manifest_dir / "tiles.json"
    manifest_path.write_text(json.dumps(tiles_manifest), encoding="utf-8")

    out_dir = tmp_path / "foley_output"
    out_dir.mkdir()
    out_path = out_dir / "review.html"

    rc = foley_review.main(
        ["--manifest", str(manifest_path), "--out", str(out_path)]
    )

    assert rc == 0
    assert out_path.is_file(), f"review.html not found at {out_path}"

    html_content = out_path.read_text(encoding="utf-8")
    assert "tile_001" in html_content
    assert "tile_002" in html_content
    assert "wind blowing through trees" in html_content

    # --- universal result manifest assertions ---
    result_manifest_path = out_dir / "manifest.json"
    assert result_manifest_path.is_file(), f"manifest not found at {result_manifest_path}"

    manifest = json.loads(result_manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "foley_review"
    assert manifest["schema_version"] == 1
    assert isinstance(manifest["inputs"], dict)
    assert manifest["inputs"]["manifest"] == str(manifest_path.resolve())
    assert isinstance(manifest["outputs"], list)
    assert len(manifest["outputs"]) == 1
    assert manifest["outputs"][0]["path"] == out_path.name
    assert manifest["outputs"][0]["type"] == "file"
    assert isinstance(manifest["warnings"], list)
    assert manifest["warnings"] == []
