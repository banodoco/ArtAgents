from __future__ import annotations

import unittest
from pathlib import Path

from astrid.core.pack import load_pack_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKS_ROOT = REPO_ROOT / "astrid" / "packs"


EXPECTED_PACKS = {
    "rendering": {
        "origin": "builtin",
        "domain": "media",
        "content": {"executors": "executors", "elements": "elements"},
        "aliases": {
            "builtin.render": "rendering.render",
            "builtin.html_canvas_effect": "rendering.html_canvas_effect",
            "builtin.sprite_sheet": "rendering.sprite_sheet",
        },
    },
    "understanding": {
        "origin": "builtin",
        "domain": "media",
        "content": {"executors": "executors"},
        "aliases": {
            "builtin.scene_describe": "understanding.scene_describe",
            "builtin.understand": "understanding.understand",
            "builtin.video_understand": "understanding.video_understand",
            "builtin.visual_understand": "understanding.visual_understand",
            "builtin.audio_understand": "understanding.audio_understand",
        },
    },
    "generation": {
        "origin": "builtin",
        "domain": "generation",
        "content": {"executors": "executors"},
        "aliases": {
            "builtin.generate_image": "generation.generate_image",
            "builtin.generate_image_openai": "generation.generate_image_openai",
            "builtin.generate_video": "generation.generate_video",
            "builtin.generate_audio": "generation.generate_audio",
        },
    },
    "editorial": {
        "origin": "builtin",
        "domain": "editorial",
        "content": {"executors": "executors"},
        "aliases": {
            "builtin.inspect_cut": "editorial.inspect_cut",
            "builtin.refine": "editorial.refine",
            "builtin.editor_review": "editorial.editor_review",
            "builtin.human_review": "editorial.human_review",
            "builtin.human_notes": "editorial.human_notes",
            "builtin.triage": "editorial.triage",
            "builtin.scenes": "editorial.scenes",
            "builtin.shots": "editorial.shots",
            "builtin.quality_zones": "editorial.quality_zones",
            "builtin.boundary_candidates": "editorial.boundary_candidates",
            "builtin.quote_scout": "editorial.quote_scout",
            "builtin.script_pipeline": "editorial.script_pipeline",
            "builtin.validate": "editorial.validate",
            "builtin.arrange": "editorial.arrange",
            "builtin.transcribe": "editorial.transcribe",
        },
    },
    "video_editing": {
        "origin": "builtin",
        "domain": "media",
        "content": {"executors": "executors", "orchestrators": "orchestrators"},
        "aliases": {
            "builtin.cut": "video_editing.cut",
            "builtin.hype": "video_editing.hype",
            "builtin.event_talks": "video_editing.event_talks",
            "builtin.thumbnail_maker": "video_editing.thumbnail_maker",
            "builtin.iteration_video": "video_editing.iteration_video",
            "builtin.animate_image": "video_editing.animate_image",
            "builtin.logo_ideas": "video_editing.logo_ideas",
            "builtin.vary_grid": "video_editing.vary_grid",
        },
    },
    "foley": {
        "origin": "builtin",
        "domain": "media",
        "content": {"executors": "executors", "orchestrators": "orchestrators"},
        "aliases": {
            "builtin.foley_review": "foley.foley_review",
            "builtin.tile_video": "foley.tile_video",
            "builtin.foley_map": "foley.foley_map",
        },
    },
    "training": {
        "origin": "builtin",
        "domain": "development",
        "content": {"executors": "executors", "orchestrators": "orchestrators"},
        "aliases": {
            "builtin.pool_build": "training.pool_build",
            "builtin.pool_merge": "training.pool_merge",
            "builtin.search_loras": "training.search_loras",
            "builtin.asset_cache": "training.asset_cache",
            "builtin.training_run": "training.training_run",
            "builtin.dataset_build": "training.dataset_build",
        },
    },
    "reigh": {
        "origin": "builtin",
        "domain": "integration",
        "content": {"executors": "executors"},
        "aliases": {
            "builtin.reigh_data": "reigh.reigh_data",
            "builtin.open_in_reigh": "reigh.open_in_reigh",
            "builtin.spatial_audio_page": "reigh.spatial_audio_page",
            "builtin.publish": "reigh.publish",
        },
    },
    "youtube": {
        "origin": "builtin",
        "domain": "integration",
        "content": {"executors": "executors"},
        "aliases": {
            "builtin.youtube_audio": "youtube.youtube_audio",
            "upload.youtube": "youtube.upload",
        },
    },
    "fal": {
        "origin": "external",
        "domain": "integration",
        "content": {"executors": "executors"},
        "aliases": {
            "external.fal_foley": "fal.fal_foley",
        },
    },
    "vibecomfy": {
        "origin": "external",
        "domain": "integration",
        "content": {"executors": "executors"},
        "aliases": {
            "external.vibecomfy.run": "vibecomfy.run",
            "external.vibecomfy.validate": "vibecomfy.validate",
        },
    },
    "runpod": {
        "origin": "external",
        "domain": "infrastructure",
        "content": {"executors": "executors"},
        "aliases": {
            "external.runpod.provision": "runpod.provision",
            "external.runpod.exec": "runpod.exec",
            "external.runpod.pull": "runpod.pull",
            "external.runpod.teardown": "runpod.teardown",
            "external.runpod.session": "runpod.session",
        },
    },
    "moirae": {
        "origin": "external",
        "domain": "integration",
        "content": {"executors": "executors"},
        "aliases": {
            "external.moirae": "moirae.moirae",
        },
    },
}


class TestPackMigrationM4Shells(unittest.TestCase):
    def test_target_pack_shells_match_migration_contract(self) -> None:
        for pack_id, expected in EXPECTED_PACKS.items():
            with self.subTest(pack=pack_id):
                pack = load_pack_manifest(PACKS_ROOT / pack_id / "pack.yaml")
                self.assertEqual(pack.id, pack_id)
                self.assertEqual(pack.origin, expected["origin"])
                self.assertEqual(pack.install_tier, "core")
                self.assertEqual(pack.pack_type, "capability")
                self.assertEqual(pack.domain, expected["domain"])
                self.assertEqual(pack.stability, "stable")
                self.assertEqual(pack.support, "core")
                self.assertEqual(pack.visibility, "visible")
                self.assertEqual(pack.content, expected["content"])

                aliases = {
                    alias["alias"]: alias["canonical_id"]
                    for alias in pack.aliases
                }
                self.assertEqual(aliases, expected["aliases"])

                for alias in pack.aliases:
                    self.assertTrue(alias.get("deprecated"))
                    self.assertEqual(
                        alias.get("deprecation_message"),
                        f"Moved to {alias['canonical_id']}",
                    )

    def test_physical_migration_creates_active_capability_manifests(self) -> None:
        for pack_id, expected in EXPECTED_PACKS.items():
            with self.subTest(pack=pack_id):
                pack_root = PACKS_ROOT / pack_id
                manifest_files = sorted(
                    path.relative_to(pack_root).as_posix()
                    for path in pack_root.rglob("*")
                    if path.name in {"executor.yaml", "orchestrator.yaml", "element.yaml"}
                )
                # Invariant: every capability directory under the pack's
                # content roots carries exactly one manifest, and no
                # manifest exists outside a capability directory. Container
                # dirs (element kinds) are skipped; leaf dirs with files but
                # no manifest are orphan capabilities and fail the assertIn
                # below. The alias table above is the frozen m4 snapshot;
                # the physical tree is the live truth for the count.
                manifest_names = {
                    "executor.yaml",
                    "orchestrator.yaml",
                    "element.yaml",
                }
                capability_dirs: list[str] = []
                for kind, rel in expected["content"].items():
                    root = pack_root / rel
                    if not root.is_dir():
                        continue
                    for path in root.rglob("*"):
                        if not path.is_dir() or path.name.startswith("__"):
                            continue
                        entries = list(path.iterdir())
                        has_manifest = any(
                            p.name in manifest_names for p in entries
                        )
                        has_subdirs = any(
                            p.is_dir() and not p.name.startswith("__")
                            for p in entries
                        )
                        if has_manifest or (
                            not has_subdirs
                            and any(p.name == "run.py" for p in entries)
                        ):
                            capability_dirs.append(str(path.relative_to(pack_root)))
                self.assertEqual(len(manifest_files), len(capability_dirs))
                for manifest in manifest_files:
                    parent = manifest.rsplit("/", 1)[0]
                    self.assertIn(parent, capability_dirs)


if __name__ == "__main__":
    unittest.main()
