import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from astrid.core import timeline
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

    def test_pool_build_writes_universal_result_manifest(self) -> None:
        """training.pool_build writes manifest.json as sibling to pool.json,
        preserves POOL_VERSION, and uses kind='pool'."""
        tmp_dir = self.make_tempdir()
        out_dir = tmp_dir / "out"

        triage = tmp_dir / "triage.json"
        scene_descriptions = tmp_dir / "scene_descriptions.json"
        quote_candidates = tmp_dir / "quote_candidates.json"
        transcript = tmp_dir / "transcript.json"
        scenes = tmp_dir / "scenes.json"

        scenes.write_text(
            json.dumps([{"index": 1, "start": 0.0, "end": 3.0, "duration": 3.0}]),
            encoding="utf-8",
        )
        triage.write_text(
            json.dumps({
                "version": 1,
                "generated_at": "2026-04-21T12:00:00Z",
                "entries": [{"scene_id": "scene_001", "triage_score": 4, "triage_tag": "speaker"}],
            }),
            encoding="utf-8",
        )
        scene_descriptions.write_text(
            json.dumps({
                "version": 1,
                "generated_at": "2026-04-21T12:00:00Z",
                "entries": [{
                    "scene_id": "scene_001",
                    "description": "speaker on stage",
                    "mood": "energetic",
                    "motion_level": "high",
                    "speaker_visible": True,
                    "dialogue_salient": True,
                    "motion_tags": ["walk"],
                    "mood_tags": ["bright"],
                    "deep_score": 0.85,
                }],
            }),
            encoding="utf-8",
        )
        quote_candidates.write_text(
            json.dumps({
                "version": 1,
                "generated_at": "2026-04-21T12:00:00Z",
                "candidates": [{
                    "segment_ids": [0],
                    "power": 4,
                    "text": "hello world",
                    "speaker": "Alice",
                    "quote_kind": "one_liner",
                }],
            }),
            encoding="utf-8",
        )
        transcript.write_text(
            json.dumps({
                "segments": [{"start": 0.5, "end": 1.5, "text": "hello world"}],
            }),
            encoding="utf-8",
        )

        rc = pool_build.main([
            "--triage", str(triage),
            "--scene-descriptions", str(scene_descriptions),
            "--quote-candidates", str(quote_candidates),
            "--transcript", str(transcript),
            "--scenes", str(scenes),
            "--source-slug", "demo",
            "--out", str(out_dir),
        ])

        self.assertEqual(rc, 0)

        # pool.json preserved with original shape and POOL_VERSION
        pool_path = out_dir / "pool.json"
        self.assertTrue(pool_path.is_file())
        pool_data = json.loads(pool_path.read_text(encoding="utf-8"))
        self.assertEqual(pool_data["version"], timeline.POOL_VERSION)
        self.assertIn("generated_at", pool_data)
        self.assertEqual(pool_data["source_slug"], "demo")
        self.assertIn("entries", pool_data)
        self.assertIsInstance(pool_data["entries"], list)
        self.assertGreater(len(pool_data["entries"]), 0)

        # manifest.json written as sibling
        manifest_path = out_dir / "manifest.json"
        self.assertTrue(manifest_path.is_file(), f"manifest.json not found at {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["kind"], "pool")
        self.assertIsInstance(manifest["inputs"], dict)
        self.assertEqual(manifest["inputs"]["triage"], str(triage.resolve()))
        self.assertEqual(manifest["inputs"]["scene_descriptions"], str(scene_descriptions.resolve()))
        self.assertEqual(manifest["inputs"]["quote_candidates"], str(quote_candidates.resolve()))
        self.assertEqual(manifest["inputs"]["transcript"], str(transcript.resolve()))
        self.assertEqual(manifest["inputs"]["scenes"], str(scenes.resolve()))
        self.assertEqual(manifest["inputs"]["source_slug"], "demo")
        self.assertIsInstance(manifest["outputs"], list)
        self.assertEqual(len(manifest["outputs"]), 1)
        self.assertEqual(manifest["outputs"][0]["type"], "file")
        self.assertIn("content_hash", manifest["outputs"][0])
        self.assertIn("bytes", manifest["outputs"][0])

        # created is a non-empty ISO string
        self.assertIsInstance(manifest["created"], str)
        self.assertGreater(len(manifest["created"]), 0)
        self.assertIsInstance(manifest["warnings"], list)


if __name__ == "__main__":
    unittest.main()
