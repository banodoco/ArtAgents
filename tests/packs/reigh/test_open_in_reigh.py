import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from astrid.packs.reigh.executors.open_in_reigh import run as open_in_reigh


ROOT = Path(__file__).resolve().parents[3]


class OpenInReighTest(unittest.TestCase):
    def make_workspace(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="open-reigh-tests-", dir=ROOT))
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def write_outputs(self, out_dir: Path, *, timeline_bytes: bytes | None = None) -> tuple[bytes, bytes]:
        if timeline_bytes is None:
            timeline_bytes = (
                b'{"theme":"banodoco-default","tracks":[],"clips":[{"id":"c1","at":0,"track":"main","clipType":"text",'
                b'"text":{"content":"hi"},"hold":1}]}\n'
            )
        assets_bytes = b'{"assets":{"main":{"file":"/abs/local path.mov","label":"Bob\'s asset"}}}\n'
        (out_dir / "hype.timeline.json").write_bytes(timeline_bytes)
        (out_dir / "hype.assets.json").write_bytes(assets_bytes)
        return timeline_bytes, assets_bytes

    def run_main(self, argv: list[str]) -> tuple[int | None, str, str, SystemExit | None]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        error = None
        code = None
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = open_in_reigh.main(argv)
            except SystemExit as exc:
                error = exc
        return code, stdout.getvalue(), stderr.getvalue(), error

    # ----- escape hatches: --copy-to / --copy-files -----

    def test_copy_to_preserves_bytes_and_creates_directory(self) -> None:
        root = self.make_workspace()
        out_dir = root / "out"
        out_dir.mkdir()
        timeline_bytes, assets_bytes = self.write_outputs(out_dir)
        dest = root / "handoff"

        code, _, _, error = self.run_main(
            ["--out", str(out_dir), "--copy-to", str(dest), "--timeline-id", "123e4567-e89b-12d3-a456-426614174000"]
        )

        self.assertIsNone(error)
        self.assertEqual(code, 0)
        self.assertEqual((dest / "hype.timeline.json").read_bytes(), timeline_bytes)
        self.assertEqual((dest / "hype.assets.json").read_bytes(), assets_bytes)

    def test_copy_files_probe_uses_public_timelines_first(self) -> None:
        root = self.make_workspace()
        out_dir = root / "out"
        out_dir.mkdir()
        self.write_outputs(out_dir)
        fake_reigh = root / "reigh"
        (fake_reigh / "public" / "timelines").mkdir(parents=True)

        code, _, _, error = self.run_main(
            [
                "--out",
                str(out_dir),
                "--copy-files",
                "--reigh-app",
                str(fake_reigh),
                "--name",
                "demo",
                "--timeline-id",
                "123e4567-e89b-12d3-a456-426614174000",
            ]
        )

        self.assertIsNone(error)
        self.assertEqual(code, 0)
        self.assertTrue((fake_reigh / "public" / "timelines" / "demo" / "hype.timeline.json").exists())
        self.assertTrue((fake_reigh / "public" / "timelines" / "demo" / "hype.assets.json").exists())

    def test_dry_run_prints_destination_without_writing_files(self) -> None:
        root = self.make_workspace()
        out_dir = root / "out"
        out_dir.mkdir()
        self.write_outputs(out_dir)
        dest = root / "handoff"

        code, stdout, _, error = self.run_main(
            [
                "--out",
                str(out_dir),
                "--copy-to",
                str(dest),
                "--dry-run",
                "--timeline-id",
                "123e4567-e89b-12d3-a456-426614174000",
            ]
        )

        self.assertIsNone(error)
        self.assertEqual(code, 0)
        self.assertIn("Would copy", stdout)
        self.assertFalse((dest / "hype.timeline.json").exists())
        self.assertFalse((dest / "hype.assets.json").exists())

    # ----- escape hatch: --print-sql -----

    def test_print_sql_emits_upsert_and_timeline_id_is_argparse_required(self) -> None:
        root = self.make_workspace()
        out_dir = root / "out"
        out_dir.mkdir()
        self.write_outputs(
            out_dir,
            timeline_bytes=b'{"title":"Bob\'s cut","theme":"banodoco-default","tracks":[],"clips":[]}\n',
        )

        code, stdout, _, error = self.run_main(
            [
                "--out",
                str(out_dir),
                "--print-sql",
                "--timeline-id",
                "123e4567-e89b-12d3-a456-426614174000",
            ]
        )

        self.assertIsNone(error)
        self.assertEqual(code, 0)
        self.assertIn("INSERT INTO public.timelines", stdout)
        self.assertIn("ON CONFLICT (id)", stdout)
        self.assertIn("config = EXCLUDED.config", stdout)
        self.assertIn("asset_registry = EXCLUDED.asset_registry", stdout)
        self.assertIn("Bob''s cut", stdout)
        self.assertIn("Bob''s asset", stdout)
        self.assertTrue(stdout.strip().endswith(";"))

        code, _, stderr, error = self.run_main(["--out", str(out_dir), "--print-sql"])
        self.assertIsNone(code)
        self.assertIsNotNone(error)
        self.assertEqual(error.code, 2)
        self.assertIn("--timeline-id", stderr)

    # ----- io guards -----

    def test_missing_required_output_file_returns_non_zero(self) -> None:
        root = self.make_workspace()
        out_dir = root / "out"
        out_dir.mkdir()
        (out_dir / "hype.assets.json").write_text("{}", encoding="utf-8")

        code, _, stderr, error = self.run_main(
            ["--out", str(out_dir), "--timeline-id", "123e4567-e89b-12d3-a456-426614174000"]
        )

        self.assertIsNone(error)
        self.assertEqual(code, 2)
        self.assertIn("missing required output file", stderr)

    # ----- default flow: SupabaseDataProvider.save_timeline -----

    def test_default_emits_bridge_metadata(self) -> None:
        """m3.5: default flow emits bridge metadata, does NOT call save_timeline."""
        root = self.make_workspace()
        out_dir = root / "out"
        out_dir.mkdir()
        self.write_outputs(out_dir)

        code, stdout, stderr, error = self.run_main(
            [
                "--out",
                str(out_dir),
                "--timeline-id",
                "123e4567-e89b-12d3-a456-426614174000",
                "--project-id",
                "proj-uuid-1",
            ]
        )

        self.assertIsNone(error, msg=stderr)
        self.assertEqual(code, 0, msg=stderr)
        bridge = json.loads(stdout.strip())
        self.assertEqual(bridge["bridge"], "open_in_reigh")
        self.assertEqual(bridge["project_id"], "proj-uuid-1")
        self.assertEqual(bridge["timeline_id"], "123e4567-e89b-12d3-a456-426614174000")
        self.assertIn("timeline_path", bridge)
        self.assertIn("m6", bridge["note"].lower())
        self.assertIn("emitted_at", bridge)

    def test_default_bridge_metadata_requires_project_id(self) -> None:
        root = self.make_workspace()
        out_dir = root / "out"
        out_dir.mkdir()
        self.write_outputs(out_dir)

        code, _, stderr, error = self.run_main(
            [
                "--out",
                str(out_dir),
                "--timeline-id",
                "123e4567-e89b-12d3-a456-426614174000",
            ]
        )
        self.assertIsNone(error)
        self.assertEqual(code, 2)
        self.assertIn("--project-id", stderr)

    def test_default_rejects_placement_style_timeline(self) -> None:
        # Once T10 collapsed the parallel placement schema, the DataProvider
        # push must refuse to upload pre-collapse timeline.json blobs that
        # carry the placement-shaped key.
        root = self.make_workspace()
        out_dir = root / "out"
        out_dir.mkdir()
        placement_blob = json.dumps(
            {
                "schema_version": 1,
                "project_slug": "demo",
                "placements": [],
                "tracks": [],
            }
        ).encode("utf-8")
        self.write_outputs(out_dir, timeline_bytes=placement_blob)

        # Patch load_timeline_blob to bypass core timeline schema validation
        # (which would itself reject placement-shaped timelines for unrelated
        # reasons); we want to assert open_in_reigh's own placement-shape guard.
        with patch.object(open_in_reigh, "load_timeline_blob", return_value=json.loads(placement_blob)):
            code, _, stderr, error = self.run_main(
                [
                    "--out",
                    str(out_dir),
                    "--timeline-id",
                    "123e4567-e89b-12d3-a456-426614174000",
                    "--project-id",
                    "proj-uuid-1",
                ]
            )
        self.assertIsNone(error)
        self.assertEqual(code, 2)
        self.assertIn("placement", stderr.lower())

    def test_bridge_metadata_with_service_role_flag(self) -> None:
        """m3.5: --service-role flag still emits bridge metadata (no auth needed)."""
        root = self.make_workspace()
        out_dir = root / "out"
        out_dir.mkdir()
        self.write_outputs(out_dir)

        code, stdout, stderr, error = self.run_main(
            [
                "--out",
                str(out_dir),
                "--timeline-id",
                "123e4567-e89b-12d3-a456-426614174000",
                "--project-id",
                "proj-uuid-1",
                "--service-role",
            ]
        )

        self.assertIsNone(error, msg=stderr)
        self.assertEqual(code, 0)
        bridge = json.loads(stdout.strip())
        self.assertEqual(bridge["bridge"], "open_in_reigh")
        self.assertEqual(bridge["timeline_id"], "123e4567-e89b-12d3-a456-426614174000")

    # ----- bridge seam tests (m3.5) -----

    def test_bridge_metadata_contains_m6_replay_note(self) -> None:
        """Prove bridge metadata documents the m6 replay seam."""
        root = self.make_workspace()
        out_dir = root / "out"
        out_dir.mkdir()
        self.write_outputs(out_dir)

        code, stdout, stderr, error = self.run_main(
            [
                "--out", str(out_dir),
                "--timeline-id", "123e4567-e89b-12d3-a456-426614174000",
                "--project-id", "proj-uuid-1",
            ]
        )
        self.assertIsNone(error, msg=stderr)
        self.assertEqual(code, 0)
        bridge = json.loads(stdout.strip())
        self.assertIn("append_timeline_event", bridge["note"].lower())
        self.assertIn("m6", bridge["note"].lower())
        self.assertIn("no direct save_timeline call", bridge["note"].lower())

    def test_bridge_metadata_dry_run(self) -> None:
        """Prove --dry-run emits bridge intent without writing."""
        root = self.make_workspace()
        out_dir = root / "out"
        out_dir.mkdir()
        self.write_outputs(out_dir)

        code, stdout, stderr, error = self.run_main(
            [
                "--out", str(out_dir),
                "--timeline-id", "123e4567-e89b-12d3-a456-426614174000",
                "--project-id", "proj-uuid-1",
                "--dry-run",
            ]
        )
        self.assertIsNone(error, msg=stderr)
        self.assertEqual(code, 0)
        self.assertIn("Would emit bridge metadata", stdout)
        self.assertIn("post-m6 replay", stdout.lower())


if __name__ == "__main__":
    unittest.main()
