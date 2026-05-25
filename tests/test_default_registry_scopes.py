from __future__ import annotations

import unittest

from astrid.core.executor.registry import load_default_registry as load_executor_registry
from astrid.core.orchestrator.registry import load_default_registry as load_orchestrator_registry


class DefaultRegistryScopeTest(unittest.TestCase):
    def test_default_executor_registries_include_packs(self) -> None:
        canonical = load_executor_registry()
        canonical_ids = set(canonical.as_mapping())

        self.assertIn("rendering.render", canonical_ids)
        self.assertIn("youtube.upload", canonical_ids)
        self.assertIn("moirae.moirae", canonical_ids)
        self.assertIn("vibecomfy.run", canonical_ids)
        self.assertIn("vibecomfy.validate", canonical_ids)

        youtube = canonical.get("youtube.upload")
        self.assertEqual(youtube.metadata["source"], "pack")
        self.assertEqual(youtube.metadata["source_pack"], "youtube")
        self.assertNotIn("pack_id", youtube.metadata)
        self.assertTrue(youtube.metadata["executor_root"].endswith("astrid/packs/youtube/executors/upload"))
        self.assertTrue(youtube.metadata["manifest_file"].endswith("astrid/packs/youtube/executors/upload/executor.yaml"))

        for executor_id, folder in (
            ("understanding.audio_understand", "audio_understand"),
            ("understanding.visual_understand", "visual_understand"),
            ("understanding.video_understand", "video_understand"),
        ):
            with self.subTest(executor_id=executor_id):
                action = canonical.get(executor_id)
                self.assertEqual(action.metadata["source"], "pack")
                self.assertEqual(action.metadata["source_pack"], "understanding")
                self.assertNotIn("pack_id", action.metadata)
                self.assertTrue(action.metadata["executor_root"].endswith(f"astrid/packs/understanding/executors/{folder}"))
                self.assertTrue(action.metadata["manifest_file"].endswith(f"astrid/packs/understanding/executors/{folder}/executor.yaml"))

        vibecomfy = canonical.get("vibecomfy.run")
        self.assertEqual(vibecomfy.kind, "external")
        self.assertEqual(vibecomfy.metadata["pack_id"], "vibecomfy")
        self.assertEqual(vibecomfy.metadata["source_pack"], "vibecomfy")
        self.assertEqual(vibecomfy.metadata["source"], "pack")
        self.assertTrue(vibecomfy.metadata["executor_root"].endswith("astrid/packs/vibecomfy/executors/run"))

    def test_default_orchestrator_registries_do_not_classify_vibecomfy_as_orchestrator(self) -> None:
        canonical = load_orchestrator_registry(executor_registry=load_executor_registry())
        canonical_ids = set(canonical.as_mapping())

        self.assertIn("video_editing.hype", canonical_ids)
        self.assertIn("video_editing.event_talks", canonical_ids)
        self.assertIn("video_editing.thumbnail_maker", canonical_ids)
        self.assertFalse(any("vibecomfy" in orchestrator_id for orchestrator_id in canonical_ids))
        self.assertFalse(any(orchestrator_id == "youtube.upload" for orchestrator_id in canonical_ids))
        with self.assertRaises(KeyError):
            canonical.get("vibecomfy.run")

    def test_canonical_builtin_executor_runtime_module(self) -> None:
        canonical = load_executor_registry()
        render = canonical.get("rendering.render")
        self.assertEqual(render.metadata["runtime_module"], "astrid.packs.rendering.executors.render.run")

    def test_external_executor_roots_are_pack_native(self) -> None:
        registry = load_executor_registry()

        self.assertTrue(registry.get("moirae.moirae").metadata["executor_root"].endswith("astrid/packs/moirae/executors/moirae"))
        self.assertTrue(
            registry.get("vibecomfy.run").metadata["executor_root"].endswith("astrid/packs/vibecomfy/executors/run")
        )


if __name__ == "__main__":
    unittest.main()
