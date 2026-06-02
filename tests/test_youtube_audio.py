import contextlib
import io
import unittest
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


if __name__ == "__main__":
    unittest.main()
