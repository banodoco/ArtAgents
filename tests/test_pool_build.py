import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from astrid.packs.training.executors.pool_build import run as pool_build


class PoolBuildMainTests(unittest.TestCase):
    def make_tempdir(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="pool-build-test-"))
        self.addCleanup(shutil.rmtree, path, True)
        return path

    def test_main_renders_astrid_error_when_no_survivors_exist(self) -> None:
        tmp_dir = self.make_tempdir()
        triage = tmp_dir / "triage.json"
        scene_descriptions = tmp_dir / "scene_descriptions.json"
        quote_candidates = tmp_dir / "quote_candidates.json"
        transcript = tmp_dir / "transcript.json"
        scenes = tmp_dir / "scenes.json"

        triage.write_text(
            json.dumps({"entries": [{"scene_id": "scene_001", "triage_score": 0}]}),
            encoding="utf-8",
        )
        scene_descriptions.write_text(json.dumps({"entries": []}), encoding="utf-8")
        quote_candidates.write_text(json.dumps({"candidates": []}), encoding="utf-8")
        transcript.write_text(json.dumps({"segments": []}), encoding="utf-8")
        scenes.write_text(
            json.dumps(
                [{"index": 1, "start": 0.0, "end": 1.0, "duration": 1.0}]
            ),
            encoding="utf-8",
        )
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            rc = pool_build.main(
                [
                    "--triage",
                    str(triage),
                    "--scene-descriptions",
                    str(scene_descriptions),
                    "--quote-candidates",
                    str(quote_candidates),
                    "--transcript",
                    str(transcript),
                    "--scenes",
                    str(scenes),
                    "--source-slug",
                    "demo",
                    "--out",
                    str(tmp_dir / "out"),
                ]
            )

        rendered = stderr.getvalue()
        self.assertEqual(rc, 2)
        self.assertIn(
            "pool_build requires at least one surviving visual and one surviving dialogue entry",
            rendered,
        )
        self.assertIn("recovery:", rendered)
        self.assertNotIn("Traceback", rendered)


if __name__ == "__main__":
    unittest.main()
