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

from astrid.packs.foley.executors.tile_video.run import FoleyProbeError, _ffprobe
from astrid.packs.foley.executors.tile_video import run as tile_video


def _patch_ffprobe(payload: dict) -> patch:
    """Patch subprocess.run for the tile_video module so ffprobe returns *payload*."""

    completed = subprocess.CompletedProcess(
        args=["ffprobe"], returncode=0, stdout=json.dumps(payload), stderr=""
    )
    return patch(
        "astrid.packs.foley.executors.tile_video.run.subprocess.run",
        return_value=completed,
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


if __name__ == "__main__":
    unittest.main()
