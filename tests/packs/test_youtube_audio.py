import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from astrid.packs.youtube.executors.youtube_audio import run as youtube_audio


class YoutubeAudioMainTests(unittest.TestCase):
    def test_main_renders_astrid_error_when_yt_dlp_is_missing(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch.object(youtube_audio.shutil, "which", return_value=None),
            contextlib.redirect_stderr(stderr),
        ):
            rc = youtube_audio.main(
                ["--query", "cats", "--out", "/tmp/cats.mp3"]
            )

        rendered = stderr.getvalue()
        self.assertEqual(rc, 2)
        self.assertIn("yt-dlp not found on PATH", rendered)
        self.assertIn("recovery:", rendered)
        self.assertNotIn("Error:", rendered)
        self.assertNotIn("Traceback", rendered)

    def test_main_writes_result_manifest_on_success(self) -> None:
        """Prove manifest creation after successful download using fake yt-dlp."""
        tmp_dir = Path(tempfile.mkdtemp(prefix="youtube-audio-test-"))
        self.addCleanup(shutil.rmtree, tmp_dir, ignore_errors=True)
        out_file = tmp_dir / "subdir" / "cats.mp3"

        def fake_which(cmd: str) -> str | None:
            # yt-dlp and ffmpeg both "found"
            return f"/usr/local/bin/{cmd}"

        def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
            # Create the expected output file so out.exists() passes
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_bytes(b"fake-mp3-data")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with (
            mock.patch.object(youtube_audio.shutil, "which", side_effect=fake_which),
            mock.patch.object(youtube_audio.subprocess, "run", side_effect=fake_run),
        ):
            rc = youtube_audio.main(
                ["--query", "cats", "--out", str(out_file)]
            )

        self.assertEqual(rc, 0)

        manifest_path = out_file.parent / "manifest.json"
        self.assertTrue(manifest_path.is_file(), f"manifest not found at {manifest_path}")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "youtube_audio")
        self.assertEqual(manifest["schema_version"], 1)
        self.assertIsInstance(manifest["inputs"], dict)
        self.assertIn("target", manifest["inputs"])
        self.assertEqual(manifest["inputs"]["mode"], "audio")
        self.assertIsInstance(manifest["outputs"], list)
        self.assertEqual(len(manifest["outputs"]), 1)
        self.assertEqual(manifest["outputs"][0]["path"], out_file.name)
        self.assertEqual(manifest["outputs"][0]["type"], "file")
        self.assertIsInstance(manifest["warnings"], list)
        self.assertEqual(manifest["warnings"], [])


if __name__ == "__main__":
    unittest.main()
