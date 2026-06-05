"""Regression for foley/tile_video ``_ffprobe`` crash on incomplete JSON.

Pre-fix bug: ``_ffprobe`` blindly indexed ``data['streams'][0]`` and
``data['format']['duration']``, raising raw ``KeyError`` / ``IndexError``
that callers were never written to catch. The fix raises a typed
:class:`FoleyProbeError` (subclass of ``ValueError``) including the input
path for all four missing-field branches.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from astrid.packs.foley.executors.tile_video import run as tile_video
from astrid.packs.foley.executors.tile_video.run import FoleyProbeError, _ffprobe


def _patch_ffprobe(payload: dict) -> patch:
    """Patch subprocess.run for the tile_video module so ffprobe returns *payload*."""

    completed = subprocess.CompletedProcess(
        args=["ffprobe"], returncode=0, stdout=json.dumps(payload), stderr=""
    )
    return patch(
        "astrid.packs.foley.executors.tile_video.run.subprocess.run",
        return_value=completed,
    )


def _fake_subprocess_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
    """Mock subprocess.run to return ffprobe data and skip ffmpeg work."""
    cmd = args[0]
    if isinstance(cmd, list) and cmd and cmd[0] == "ffprobe":
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({
                "streams": [{
                    "width": 640, "height": 480,
                    "r_frame_rate": "30/1",
                    "duration": "10.0",
                }],
                "format": {"duration": "10.0"},
            }),
            stderr="",
        )
    # All other calls (ffmpeg) — just succeed.
    return subprocess.CompletedProcess(
        args=cmd if isinstance(cmd, list) else [],
        returncode=0,
        stdout="",
        stderr="",
    )


class FoleyProbeErrorTest(unittest.TestCase):
    VIDEO = Path("/tmp/foley-fake-input.mp4")

    def test_empty_streams_list_raises_typed(self) -> None:
        with _patch_ffprobe({"streams": [], "format": {"duration": "1.0"}}):
            with self.assertRaises(FoleyProbeError) as ctx:
                _ffprobe(self.VIDEO)
        self.assertIn(str(self.VIDEO), str(ctx.exception))
        self.assertIsInstance(ctx.exception, ValueError)

    def test_missing_streams_key_raises_typed(self) -> None:
        with _patch_ffprobe({"format": {"duration": "1.0"}}):
            with self.assertRaises(FoleyProbeError) as ctx:
                _ffprobe(self.VIDEO)
        self.assertIn(str(self.VIDEO), str(ctx.exception))

    def test_missing_format_block_raises_typed(self) -> None:
        # Stream present but with no per-stream duration, and no format block —
        # the code falls back to format.duration, which is absent here.
        with _patch_ffprobe({
            "streams": [{"width": 640, "height": 480, "r_frame_rate": "30/1"}]
        }):
            with self.assertRaises(FoleyProbeError) as ctx:
                _ffprobe(self.VIDEO)
        self.assertIn(str(self.VIDEO), str(ctx.exception))

    def test_missing_format_duration_raises_typed(self) -> None:
        with _patch_ffprobe({
            "streams": [{"width": 640, "height": 480, "r_frame_rate": "30/1"}],
            "format": {},
        }):
            with self.assertRaises(FoleyProbeError) as ctx:
                _ffprobe(self.VIDEO)
        self.assertIn(str(self.VIDEO), str(ctx.exception))

    def test_main_renders_astrid_error_for_missing_video(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = tile_video.main(
                ["--video", str(self.VIDEO), "--out", "/tmp/tiles-out"]
            )
        rendered = stderr.getvalue()
        self.assertEqual(rc, 2)
        self.assertIn(f"video not found: {self.VIDEO.resolve()}", rendered)
        self.assertIn("recovery:", rendered)
        self.assertNotIn("Error:", rendered)


def test_main_writes_result_manifest(tmp_path: Path) -> None:
    """Prove tile_video emits a universal result manifest without live GPU/ffmpeg."""
    video_path = tmp_path / "fake_input.mp4"
    video_path.write_text("fake video content")

    out_dir = tmp_path / "tiles_output"

    with patch(
        "astrid.packs.foley.executors.tile_video.run.subprocess.run",
        side_effect=_fake_subprocess_run,
    ):
        rc = tile_video.main(
            ["--video", str(video_path), "--out", str(out_dir),
             "--grid", "2x2", "--overlap", "0.25"]
        )

    assert rc == 0, f"Expected rc=0, got {rc}"

    # Domain manifest
    tiles_json = out_dir / "tiles.json"
    assert tiles_json.is_file(), f"tiles.json not found at {tiles_json}"
    tiles_data = json.loads(tiles_json.read_text(encoding="utf-8"))
    assert tiles_data["grid"] == {"cols": 2, "rows": 2, "overlap": 0.25}
    assert len(tiles_data["tiles"]) == 4

    # Universal result manifest
    result_manifest_path = out_dir / "manifest.json"
    assert result_manifest_path.is_file(), f"manifest not found at {result_manifest_path}"

    manifest = json.loads(result_manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "tile_video"
    assert manifest["schema_version"] == 1
    assert isinstance(manifest["inputs"], dict)
    assert manifest["inputs"]["video"] == str(video_path.resolve())
    assert manifest["inputs"]["grid"] == [2, 2]
    assert manifest["inputs"]["overlap"] == 0.25
    assert manifest["inputs"]["trim"] is None
    assert isinstance(manifest["outputs"], list)
    assert len(manifest["outputs"]) == 3

    output_paths = {o["path"] for o in manifest["outputs"]}
    assert "tiles.json" in output_paths
    assert "tiles" in output_paths
    assert "frames" in output_paths

    # tiles.json output entry
    tiles_entry = next(o for o in manifest["outputs"] if o["path"] == "tiles.json")
    assert tiles_entry["type"] == "file"
    assert "content_hash" in tiles_entry
    assert "bytes" in tiles_entry

    # tiles directory entry
    tiles_dir_entry = next(o for o in manifest["outputs"] if o["path"] == "tiles")
    assert tiles_dir_entry["type"] == "directory"
    assert "entries" in tiles_dir_entry
    assert "content_hash" in tiles_dir_entry

    # frames directory entry
    frames_dir_entry = next(o for o in manifest["outputs"] if o["path"] == "frames")
    assert frames_dir_entry["type"] == "directory"
    assert "entries" in frames_dir_entry

    assert isinstance(manifest["warnings"], list)
    assert manifest["warnings"] == []


if __name__ == "__main__":
    unittest.main()
