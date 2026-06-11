import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from astrid.core.contracts.errors import AstridError
from astrid.core import timeline
from astrid.packs.video_editing.executors.cut import run as cut
from astrid.packs.video_editing.executors.cut.registry import (
    _carry_forward_registry_metadata,
    _PRESERVED_REGISTRY_FIELDS,
    build_registry,
)


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
REMOTION_NODE_MODULES = ROOT / "remotion" / "node_modules"


def remotion_launch_blocked(error: RuntimeError) -> bool:
    message = str(error)
    return (
        "Failed to launch the browser process" in message
        or "MachPortRendezvous" in message
        or "Permission denied (1100)" in message
    )


class CutTimelineResumeTest(unittest.TestCase):
    maxDiff = None

    def copy_examples(self) -> Path:
        tmp_root = Path(tempfile.mkdtemp(prefix="cut-resume-"))
        self.addCleanup(shutil.rmtree, tmp_root, ignore_errors=True)
        source_dir = tmp_root / "source"
        shutil.copytree(EXAMPLES, source_dir)
        return source_dir

    def test_same_dir_roundtrip_is_byte_identical(self) -> None:
        # Sprint 6 (SD-009): resume-mode backfills `output` if the loaded
        # timeline lacks it. This test pre-stamps `output` matching the theme
        # so the roundtrip remains byte-identical (the byte-equivalence claim
        # is for "no semantic drift", not "literally untouched"; if the input
        # already carries output, save_timeline preserves it verbatim).
        source_dir = self.copy_examples()
        timeline_path = source_dir / "hype.timeline.json"
        assets_path = source_dir / "hype.assets.json"
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        timeline.setdefault("output", {"resolution": "1920x1080", "fps": 30, "file": "output.mp4"})
        timeline_path.write_text(json.dumps(timeline, indent=2) + "\n", encoding="utf-8")
        original_timeline = timeline_path.read_bytes()
        original_assets = assets_path.read_bytes()

        result = cut.main(["--timeline", str(timeline_path), "--out", str(source_dir)])

        self.assertEqual(result, 0)
        self.assertEqual(timeline_path.read_bytes(), original_timeline)
        self.assertEqual(assets_path.read_bytes(), original_assets)
        self.assertFalse((source_dir / "hype.edl.csv").exists())

        # --- universal result manifest assertions ---
        manifest_path = source_dir / "manifest.json"
        self.assertTrue(manifest_path.is_file(), f"manifest not found at {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "cut")
        self.assertEqual(manifest["schema_version"], 1)
        self.assertIsInstance(manifest["inputs"], dict)
        self.assertIn("timeline", manifest["inputs"])
        self.assertIsInstance(manifest["outputs"], list)
        output_paths = {o["path"] for o in manifest["outputs"]}
        self.assertIn("hype.timeline.json", output_paths)
        self.assertIn("hype.assets.json", output_paths)
        self.assertIn("hype.metadata.json", output_paths)
        self.assertNotIn("hype.mp4", output_paths)  # no render
        self.assertIsInstance(manifest["warnings"], list)

    def test_different_out_rebases_registry_paths(self) -> None:
        source_dir = self.copy_examples()
        timeline_path = source_dir / "hype.timeline.json"
        assets_path = source_dir / "hype.assets.json"
        registry_payload = json.loads(assets_path.read_text(encoding="utf-8"))
        registry_payload["assets"]["main"].update({
            "origin": "refreshable-from-generation",
            "etag": '"etag-main"',
            "content_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "url_expires_at": "2026-12-31T23:59:59Z",
            "thumbnailUrl": "https://cdn.example.com/main-thumb.jpg",
            "derivedFrom": {
                "assetId": "parent-main",
                "content_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                "role": "proxy",
            },
        })
        assets_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        out_dir = source_dir.parent / "out"
        original_timeline = json.loads(timeline_path.read_text(encoding="utf-8"))

        result = cut.main(["--timeline", str(timeline_path), "--out", str(out_dir)])

        self.assertEqual(result, 0)
        # Sprint 6 (SD-009): resume-mode now backfills `output` from the theme
        # when missing. Other fields (theme slug, clips, tracks) round-trip
        # verbatim.
        rewritten = json.loads((out_dir / "hype.timeline.json").read_text(encoding="utf-8"))
        for key in ("theme", "clips", "tracks", "theme_overrides"):
            if key in original_timeline:
                self.assertEqual(rewritten.get(key), original_timeline[key])
        self.assertIn("output", rewritten)
        self.assertEqual(set(rewritten["output"].keys()) & {"resolution", "fps", "file"},
                         {"resolution", "fps", "file"})
        registry = json.loads((out_dir / "hype.assets.json").read_text(encoding="utf-8"))
        self.assertEqual(
            Path(registry["assets"]["main"]["file"]),
            (source_dir / "main.mp4").resolve(),
        )
        self.assertEqual(
            Path(registry["assets"]["broll"]["file"]),
            (source_dir / "broll.mp4").resolve(),
        )
        self.assertTrue(Path(registry["assets"]["main"]["file"]).is_absolute())
        self.assertEqual(registry["assets"]["main"]["origin"], "refreshable-from-generation")
        self.assertEqual(registry["assets"]["main"]["etag"], '"etag-main"')
        self.assertEqual(
            registry["assets"]["main"]["content_sha256"],
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        )
        self.assertEqual(registry["assets"]["main"]["url_expires_at"], "2026-12-31T23:59:59Z")
        self.assertEqual(registry["assets"]["main"]["thumbnailUrl"], "https://cdn.example.com/main-thumb.jpg")
        self.assertEqual(
            registry["assets"]["main"]["derivedFrom"],
            {
                "assetId": "parent-main",
                "content_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                "role": "proxy",
            },
        )
        self.assertFalse((out_dir / "hype.edl.csv").exists())

        # --- universal result manifest assertions ---
        manifest_path = out_dir / "manifest.json"
        self.assertTrue(manifest_path.is_file(), f"manifest not found at {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "cut")
        self.assertEqual(manifest["schema_version"], 1)
        self.assertIsInstance(manifest["inputs"], dict)
        self.assertIn("timeline", manifest["inputs"])
        self.assertIsInstance(manifest["outputs"], list)
        output_paths = {o["path"] for o in manifest["outputs"]}
        self.assertIn("hype.timeline.json", output_paths)
        self.assertIn("hype.assets.json", output_paths)
        self.assertIn("hype.metadata.json", output_paths)
        self.assertNotIn("hype.mp4", output_paths)  # no render
        self.assertIsInstance(manifest["warnings"], list)

    def test_conflicting_flags_are_rejected(self) -> None:
        source_dir = self.copy_examples()
        timeline_path = source_dir / "hype.timeline.json"
        out_dir = source_dir.parent / "out"
        conflicts = [
            ("--scenes", str(source_dir / "scenes.json")),
            ("--video", str(source_dir / "main.mp4")),
            ("--shots", str(source_dir / "shots.json")),
            ("--transcript", str(source_dir / "transcript.json")),
            ("--primary-asset", "main"),
            ("--asset", "main=/tmp/main.mp4"),
        ]
        self.assertEqual(len(conflicts), 6)

        for flag, value in conflicts:
            with self.subTest(flag=flag):
                with self.assertRaises(AstridError) as ctx:
                    cut.main(["--timeline", str(timeline_path), "--out", str(out_dir), flag, value])
                self.assertIn(flag, str(ctx.exception))

    def test_missing_asset_key_is_rejected(self) -> None:
        source_dir = self.copy_examples()
        timeline_path = source_dir / "hype.timeline.json"
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        timeline["clips"][0]["asset"] = "ghost"
        timeline_path.write_text(json.dumps(timeline, indent=2) + "\n", encoding="utf-8")

        with self.assertRaises(AstridError) as ctx:
            cut.main(["--timeline", str(timeline_path), "--out", str(source_dir.parent / "out")])

        self.assertIn("ghost", str(ctx.exception))

    def test_ffmpeg_legacy_renderer_is_rejected(self) -> None:
        source_dir = self.copy_examples()
        timeline_path = source_dir / "hype.timeline.json"

        with self.assertRaises(SystemExit) as ctx:
            cut.main(
                [
                    "--timeline",
                    str(timeline_path),
                    "--out",
                    str(source_dir.parent / "out"),
                    "--render",
                    "--renderer",
                    "ffmpeg-legacy",
                ]
            )

        self.assertEqual(ctx.exception.code, 2)

    def test_metadata_carry_forward_preserves_clip_rationale(self) -> None:
        source_dir = self.copy_examples()
        timeline_path = source_dir / "hype.timeline.json"
        metadata_path = source_dir / "hype.metadata.json"
        timeline_payload = json.loads(timeline_path.read_text(encoding="utf-8"))
        # Use a clip id that actually exists in the current example timeline.
        # The legacy "clip_001"/"clip_999" naming drifted after the example
        # was rewritten to use semantic clip ids (src_open, brand_wordmark, ...).
        live_clip_id = timeline_payload["clips"][0]["id"]
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["generated_at"] = "2025-01-01T00:00:00Z"
        metadata.setdefault("clips", {})
        metadata["clips"][live_clip_id] = {"pick_rationale": "Keep this rationale."}
        metadata["clips"]["clip_999"] = {"pick_rationale": "orphan"}
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

        out_dir = source_dir.parent / "out"
        result = cut.main(["--timeline", str(timeline_path), "--out", str(out_dir)])

        self.assertEqual(result, 0)
        updated = json.loads((out_dir / "hype.metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(updated["clips"][live_clip_id]["pick_rationale"], "Keep this rationale.")
        self.assertNotIn("clip_999", updated["clips"])
        self.assertEqual(updated["sources"], metadata["sources"])
        self.assertNotEqual(updated["generated_at"], metadata["generated_at"])
        self.assertEqual(updated["pipeline"]["config_snapshot"]["mode"], "timeline_resume")

        # --- universal result manifest assertions ---
        manifest_path = out_dir / "manifest.json"
        self.assertTrue(manifest_path.is_file(), f"manifest not found at {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "cut")
        self.assertEqual(manifest["schema_version"], 1)
        self.assertIsInstance(manifest["inputs"], dict)
        self.assertIn("timeline", manifest["inputs"])
        self.assertIsInstance(manifest["outputs"], list)
        output_paths = {o["path"] for o in manifest["outputs"]}
        self.assertIn("hype.timeline.json", output_paths)
        self.assertIn("hype.assets.json", output_paths)
        self.assertIn("hype.metadata.json", output_paths)
        self.assertNotIn("hype.mp4", output_paths)  # no render
        self.assertIsInstance(manifest["warnings"], list)

    def test_resume_mode_render_smoke(self) -> None:
        if shutil.which("ffmpeg") is None or shutil.which("npx") is None or not REMOTION_NODE_MODULES.exists():
            self.skipTest("ffmpeg, npx, and remotion/node_modules are required for the render smoke")

        source_dir = self.copy_examples()
        # The committed examples reference main.mp4 / broll.mp4 in
        # hype.assets.json but do not ship the media files (the .mp4s are too
        # heavy for a sample dir). Skip when the assets aren't present rather
        # than fail with an opaque "Asset 'main' resolved to missing file"
        # from the renderer's path resolver.
        for asset_name in ("main.mp4", "broll.mp4"):
            if not (source_dir / asset_name).exists():
                self.skipTest(
                    f"examples/ does not ship {asset_name}; render smoke needs real media"
                )
        timeline_path = source_dir / "hype.timeline.json"
        out_dir = source_dir.parent / "rendered"

        try:
            result = cut.main(["--timeline", str(timeline_path), "--out", str(out_dir), "--render"])
        except RuntimeError as exc:
            if remotion_launch_blocked(exc):
                self.skipTest(f"Remotion browser launch is blocked in this environment: {exc}")
            raise

        self.assertEqual(result, 0)
        output = out_dir / "hype.mp4"
        self.assertTrue(output.exists())
        self.assertGreater(output.stat().st_size, 0)

        # --- universal result manifest assertions ---
        manifest_path = out_dir / "manifest.json"
        self.assertTrue(manifest_path.is_file(), f"manifest not found at {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "cut")
        self.assertEqual(manifest["schema_version"], 1)
        self.assertIsInstance(manifest["inputs"], dict)
        self.assertIn("timeline", manifest["inputs"])
        self.assertIsInstance(manifest["outputs"], list)
        output_paths = {o["path"] for o in manifest["outputs"]}
        self.assertIn("hype.timeline.json", output_paths)
        self.assertIn("hype.assets.json", output_paths)
        self.assertIn("hype.metadata.json", output_paths)
        self.assertIn("hype.mp4", output_paths)  # render enabled
        self.assertIsInstance(manifest["warnings"], list)

    def test_execute_resume_mode_returns_saved_registry_and_paths_for_bridge_writeback(self) -> None:
        source_dir = self.copy_examples()
        timeline_path = source_dir / "hype.timeline.json"
        out_dir = source_dir.parent / "out"

        args = cut.build_parser().parse_args([
            "--timeline",
            str(timeline_path),
            "--out",
            str(out_dir),
        ])

        result = cut.execute_resume_mode(args)

        self.assertEqual(result.source_timeline_path, timeline_path.resolve())
        self.assertEqual(result.source_assets_path, (source_dir / "hype.assets.json").resolve())
        self.assertEqual(result.timeline_path, (out_dir / "hype.timeline.json").resolve())
        self.assertEqual(result.assets_path, (out_dir / "hype.assets.json").resolve())
        self.assertEqual(result.metadata_path, (out_dir / "hype.metadata.json").resolve())
        self.assertIsNone(result.rendered_path)
        self.assertIn("assets", result.registry)

    # -------------------------------------------------------------------
    # Carry-forward registry metadata — unit-level coverage
    # -------------------------------------------------------------------

    def test_carry_forward_preserves_all_registry_extended_fields(self) -> None:
        """_carry_forward_registry_metadata copies every field in
        _PRESERVED_REGISTRY_FIELDS from the existing entry when values are
        non-None and non-empty."""
        existing = {
            "origin": "refreshable-from-generation",
            "etag": '"etag-abc123"',
            "content_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "url_expires_at": "2026-12-31T23:59:59Z",
            "thumbnailUrl": "https://cdn.example.com/thumb.jpg",
            "derivedFrom": {
                "assetId": "parent-main",
                "content_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                "role": "proxy",
            },
            "generationId": "gen-main",
            "variantId": "variant-main",
        }
        entry: dict = {"file": "main.mp4", "type": "video/mp4", "duration": 42.0}
        _carry_forward_registry_metadata(entry, existing)

        self.assertEqual(entry["origin"], "refreshable-from-generation")
        self.assertEqual(entry["etag"], '"etag-abc123"')
        self.assertEqual(
            entry["content_sha256"],
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        )
        self.assertEqual(entry["url_expires_at"], "2026-12-31T23:59:59Z")
        self.assertEqual(entry["thumbnailUrl"], "https://cdn.example.com/thumb.jpg")
        self.assertEqual(
            entry["derivedFrom"],
            {
                "assetId": "parent-main",
                "content_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                "role": "proxy",
            },
        )
        self.assertEqual(entry["generationId"], "gen-main")
        self.assertEqual(entry["variantId"], "variant-main")
        # Original fields still present
        self.assertEqual(entry["file"], "main.mp4")
        self.assertEqual(entry["duration"], 42.0)

    def test_carry_forward_skips_none_and_empty_string_values(self) -> None:
        """Empty strings and None values are NOT carried forward so they
        don't pollute the rebuilt entry."""
        existing = {
            "origin": None,
            "etag": "",
            "content_sha256": None,
            "url_expires_at": "2026-12-31T23:59:59Z",
            "thumbnailUrl": "",
            "derivedFrom": None,
            "generationId": None,
            "variantId": "",
        }
        entry: dict = {"file": "main.mp4", "type": "video/mp4"}
        _carry_forward_registry_metadata(entry, existing)

        # Only url_expires_at is non-None, non-empty-string
        self.assertEqual(entry.get("url_expires_at"), "2026-12-31T23:59:59Z")
        self.assertNotIn("origin", entry)
        self.assertNotIn("etag", entry)
        self.assertNotIn("content_sha256", entry)
        self.assertNotIn("thumbnailUrl", entry)
        self.assertNotIn("derivedFrom", entry)
        self.assertNotIn("generationId", entry)
        self.assertNotIn("variantId", entry)

    def test_carry_forward_noop_when_existing_is_none(self) -> None:
        entry: dict = {"file": "main.mp4", "type": "video/mp4"}
        original = dict(entry)
        _carry_forward_registry_metadata(entry, None)
        self.assertEqual(entry, original)

    # -------------------------------------------------------------------
    # Resume-mode registry preservation — extended metadata round-trip
    # -------------------------------------------------------------------

    def test_resume_mode_preserves_extended_metadata_in_registry(self) -> None:
        """Pre-seed the assets file with every extended metadata field,
        run resume mode to a different output directory, and verify all
        fields survive the rebase."""
        source_dir = self.copy_examples()
        timeline_path = source_dir / "hype.timeline.json"
        assets_path = source_dir / "hype.assets.json"

        registry_payload = json.loads(assets_path.read_text(encoding="utf-8"))
        registry_payload["assets"]["main"].update({
            "origin": "refreshable-from-generation",
            "etag": '"etag-main-v2"',
            "content_sha256": "aaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd",
            "url_expires_at": "2027-06-15T00:00:00Z",
            "thumbnailUrl": "https://cdn.example.com/main-v2.jpg",
            "derivedFrom": {
                "assetId": "parent-main",
                "content_sha256": "bbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaa",
                "role": "proxy",
            },
            "generationId": "gen-main-v2",
            "variantId": "variant-main-v2",
        })
        # Also add metadata to another asset to test multi-asset preservation
        if "broll" in registry_payload["assets"]:
            registry_payload["assets"]["broll"].update({
                "origin": "immutable-public",
                "content_sha256": "ccccddddbbbbaaaaccccddddbbbbaaaaccccddddbbbbaaaaccccddddbbbbaaaa",
                "thumbnailUrl": "https://cdn.example.com/broll-thumb.jpg",
            })
        assets_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        out_dir = source_dir.parent / "out-preserve"
        result = cut.main(["--timeline", str(timeline_path), "--out", str(out_dir)])
        self.assertEqual(result, 0)

        reloaded = json.loads((out_dir / "hype.assets.json").read_text(encoding="utf-8"))
        main_entry = reloaded["assets"]["main"]

        self.assertEqual(main_entry["origin"], "refreshable-from-generation")
        self.assertEqual(main_entry["etag"], '"etag-main-v2"')
        self.assertEqual(
            main_entry["content_sha256"],
            "aaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd",
        )
        self.assertEqual(main_entry["url_expires_at"], "2027-06-15T00:00:00Z")
        self.assertEqual(main_entry["thumbnailUrl"], "https://cdn.example.com/main-v2.jpg")
        self.assertEqual(
            main_entry["derivedFrom"],
            {
                "assetId": "parent-main",
                "content_sha256": "bbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaa",
                "role": "proxy",
            },
        )
        self.assertEqual(main_entry["generationId"], "gen-main-v2")
        self.assertEqual(main_entry["variantId"], "variant-main-v2")
        # Core fields survived
        self.assertIn("file", main_entry)
        self.assertIn("duration", main_entry)

        if "broll" in reloaded["assets"]:
            broll = reloaded["assets"]["broll"]
            self.assertEqual(broll.get("origin"), "immutable-public")
            self.assertEqual(
                broll.get("content_sha256"),
                "ccccddddbbbbaaaaccccddddbbbbaaaaccccddddbbbbaaaaccccddddbbbbaaaa",
            )
            self.assertEqual(broll.get("thumbnailUrl"), "https://cdn.example.com/broll-thumb.jpg")

    def test_resume_mode_saved_registry_is_equivalent_to_on_disk(self) -> None:
        """The registry returned inside ResumeModeResult must be
        structurally equivalent to the on-disk JSON so the bridge can
        safely use the in-memory copy for writeback."""
        source_dir = self.copy_examples()
        timeline_path = source_dir / "hype.timeline.json"
        out_dir = source_dir.parent / "out-equiv"

        args = cut.build_parser().parse_args([
            "--timeline", str(timeline_path),
            "--out", str(out_dir),
        ])
        result = cut.execute_resume_mode(args)

        on_disk = json.loads(result.assets_path.read_text(encoding="utf-8"))
        # The in-memory registry and on-disk JSON must carry the same asset keys
        self.assertEqual(set(result.registry["assets"].keys()), set(on_disk["assets"].keys()))
        for key in result.registry["assets"]:
            self.assertEqual(result.registry["assets"][key], on_disk["assets"][key])

    # -------------------------------------------------------------------
    # Bridge render-output writeback simulation
    # -------------------------------------------------------------------

    def test_bridge_writeback_simulates_adding_render_output_entry(self) -> None:
        """Simulate the bridge pattern: take the ResumeModeResult, add a
        render-output derived entry to the returned registry, save, and
        verify the render-output survives a reload with correct parent
        linkage both when the source hash is present and when it is not."""
        source_dir = self.copy_examples()
        timeline_path = source_dir / "hype.timeline.json"
        assets_path = source_dir / "hype.assets.json"

        # Pre-seed the source asset with a content_sha256 so the render-output
        # entry can carry a parent hash.
        registry_payload = json.loads(assets_path.read_text(encoding="utf-8"))
        registry_payload["assets"]["main"].update({
            "content_sha256": "fffeeeddddccccbbbbfffeeeddddccccbbbbfffeeeddddccccbbbbfffeeedddd",
            "origin": "refreshable-from-generation",
        })
        assets_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        out_dir = source_dir.parent / "out-writeback"
        args = cut.build_parser().parse_args([
            "--timeline", str(timeline_path),
            "--out", str(out_dir),
        ])
        result = cut.execute_resume_mode(args)

        # Bridge: add a render-output derived entry, using the source hash
        registry = result.registry
        self.assertIn("main", registry["assets"])
        render_output_entry = {
            "file": str(out_dir / "hype-rendered.mp4"),
            "type": "video/mp4",
            "duration": 42.0,
            "origin": "opaque-foreign",
            "derivedFrom": {
                "assetId": "main",
                "content_sha256": registry["assets"]["main"].get("content_sha256"),
                "role": "render-output",
            },
        }
        registry["assets"]["hype-output"] = render_output_entry

        # Save through the core timeline save_registry
        assets_out = out_dir / "hype.assets.json"
        timeline.save_registry(registry, assets_out)

        # Reload and verify
        reloaded = timeline.load_registry(assets_out)
        self.assertIn("hype-output", reloaded["assets"])
        output_entry = reloaded["assets"]["hype-output"]
        self.assertEqual(output_entry["origin"], "opaque-foreign")
        self.assertEqual(output_entry["derivedFrom"]["assetId"], "main")
        self.assertEqual(
            output_entry["derivedFrom"]["content_sha256"],
            "fffeeeddddccccbbbbfffeeeddddccccbbbbfffeeeddddccccbbbbfffeeedddd",
        )
        self.assertEqual(output_entry["derivedFrom"]["role"], "render-output")
        # Source entry still intact
        self.assertIn("main", reloaded["assets"])
        self.assertEqual(
            reloaded["assets"]["main"]["content_sha256"],
            "fffeeeddddccccbbbbfffeeeddddccccbbbbfffeeeddddccccbbbbfffeeedddd",
        )

    def test_bridge_writeback_render_output_without_parent_hash(self) -> None:
        """When the source entry has no content_sha256, the render-output
        derived entry should still be writeable with only assetId and role
        (no content_sha256 in derivedFrom)."""
        source_dir = self.copy_examples()
        timeline_path = source_dir / "hype.timeline.json"
        assets_path = source_dir / "hype.assets.json"

        # Ensure the source does NOT have content_sha256
        registry_payload = json.loads(assets_path.read_text(encoding="utf-8"))
        registry_payload["assets"]["main"].pop("content_sha256", None)
        registry_payload["assets"]["main"]["origin"] = "immutable-public"
        assets_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        out_dir = source_dir.parent / "out-writeback-nohash"
        args = cut.build_parser().parse_args([
            "--timeline", str(timeline_path),
            "--out", str(out_dir),
        ])
        result = cut.execute_resume_mode(args)

        # Bridge: add render-output without a parent hash
        registry = result.registry
        render_output_entry = {
            "file": str(out_dir / "hype-rendered.mp4"),
            "type": "video/mp4",
            "origin": "opaque-foreign",
            "derivedFrom": {
                "assetId": "main",
                "role": "render-output",
            },
        }
        registry["assets"]["hype-output"] = render_output_entry
        assets_out = out_dir / "hype.assets.json"
        timeline.save_registry(registry, assets_out)

        reloaded = timeline.load_registry(assets_out)
        output_entry = reloaded["assets"]["hype-output"]
        self.assertEqual(output_entry["derivedFrom"]["assetId"], "main")
        self.assertEqual(output_entry["derivedFrom"]["role"], "render-output")
        # No content_sha256 because source had none
        self.assertNotIn("content_sha256", output_entry["derivedFrom"])

    # -------------------------------------------------------------------
    # build_registry carry-forward through URL path
    # -------------------------------------------------------------------

    def test_build_registry_carries_forward_extended_metadata_for_url_assets(self) -> None:
        """When rebuild_registry sees a URL asset whose key matches an
        existing registry entry, it carries forward extended metadata
        through _carry_forward_registry_metadata."""
        existing_registry = {
            "assets": {
                "main": {
                    "url": "https://cdn.example.com/main.mp4",
                    "duration": 42.0,
                    "type": "video",
                    "resolution": "1920x1080",
                    "fps": 30.0,
                    "origin": "immutable-public",
                    "etag": '"etag-cached"',
                    "content_sha256": "fffeeeddddccccbbbbfffeeeddddccccbbbbfffeeeddddccccbbbbfffeeedddd",
                    "url_expires_at": "2027-12-31T23:59:59Z",
                    "thumbnailUrl": "https://cdn.example.com/old-thumb.jpg",
                    "derivedFrom": {
                        "assetId": "origin-asset",
                        "content_sha256": "aaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd",
                        "role": "proxy",
                    },
                    "generationId": "gen-1",
                    "variantId": "var-1",
                },
            },
        }

        registry, sources_meta = build_registry(
            asset_paths={},
            asset_urls={"main": "https://cdn.example.com/main.mp4"},
            existing_registry=existing_registry,
            prior_meta=None,
        )

        self.assertIn("main", registry["assets"])
        main = registry["assets"]["main"]
        self.assertEqual(main["origin"], "immutable-public")
        self.assertEqual(main["etag"], '"etag-cached"')
        self.assertEqual(
            main["content_sha256"],
            "fffeeeddddccccbbbbfffeeeddddccccbbbbfffeeeddddccccbbbbfffeeedddd",
        )
        self.assertEqual(main["url_expires_at"], "2027-12-31T23:59:59Z")
        self.assertEqual(main["thumbnailUrl"], "https://cdn.example.com/old-thumb.jpg")
        self.assertEqual(main["derivedFrom"]["assetId"], "origin-asset")
        self.assertEqual(main["derivedFrom"]["role"], "proxy")
        self.assertEqual(main["generationId"], "gen-1")
        self.assertEqual(main["variantId"], "var-1")


if __name__ == "__main__":
    unittest.main()
