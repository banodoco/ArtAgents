"""Parser-introspection coverage for pack run.py static choice helpers."""

from __future__ import annotations

import argparse
import importlib
import os
import unittest
from unittest.mock import patch

from astrid.core.cli_choices import StaticChoices


def _parser_action(
    parser: argparse.ArgumentParser,
    *,
    dest: str,
    parser_path: tuple[str, ...] = (),
) -> argparse.Action:
    current = parser
    for name in parser_path:
        subparsers = next(
            action
            for action in current._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        current = subparsers.choices[name]
    return next(action for action in current._actions if action.dest == dest)


class PackRunCliChoicesTests(unittest.TestCase):
    def test_importable_pack_parsers_use_static_choices(self) -> None:
        cases = [
            ("astrid.packs.generation.executors.generate_image.run", (), "mode"),
            ("astrid.packs.generation.executors.generate_video.run", (), "enable_safety_checker"),
            ("astrid.packs.generation.executors.generate_video.run", (), "enable_prompt_expansion"),
            ("astrid.packs.generation.executors.generate_video.run", (), "acceleration"),
            ("astrid.packs.generation.executors.generate_image_openai.run", (), "preset"),
            ("astrid.packs.generation.executors.generate_image_openai.run", (), "background"),
            ("astrid.packs.generation.executors.generate_image_openai.run", (), "moderation"),
            ("astrid.packs.rendering.executors.sprite_sheet.run", (), "upscale_filter"),
            ("astrid.packs.rendering.executors.sprite_sheet.run", (), "ai_upscale_provider"),
            ("astrid.packs.understanding.executors.video_understand.run", (), "mode"),
            ("astrid.packs.understanding.executors.audio_understand.run", (), "audition_reel"),
            ("astrid.packs.understanding.executors.audio_understand.run", (), "mode"),
            ("astrid.packs.understanding.executors.understand.run", (), "mode"),
            ("astrid.packs.understanding.executors.visual_understand.run", (), "mode"),
            ("astrid.packs.understanding.executors.visual_understand.run", (), "detail"),
            ("astrid.packs.editorial.executors.transcribe.run", (), "diarize"),
            ("astrid.packs.editorial.executors.boundary_candidates.run", (), "kind"),
            ("astrid.packs.training.executors.search_loras.run", (), "mode"),
            ("astrid.packs.training.executors.search_loras.run", (), "match_mode"),
            ("astrid.packs.training.executors.search_loras.run", (), "direction"),
            ("astrid.packs.runpod.executors._common", ("exec",), "upload_mode"),
            ("astrid.packs.runpod.executors._common", ("session",), "upload_mode"),
            ("astrid.packs.foley.orchestrators.foley_map.run", (), "stop_after"),
            ("astrid.packs.video_editing.executors.cut.run", (), "renderer"),
            ("astrid.packs.video_editing.orchestrators.vary_grid.run", (), "quality"),
            ("astrid.packs.video_editing.orchestrators.vary_grid.run", (), "output_format"),
            ("astrid.packs.video_editing.orchestrators.thumbnail_maker.run", (), "quality"),
            ("astrid.packs.video_editing.orchestrators.thumbnail_maker.run", (), "output_format"),
            ("astrid.packs.video_editing.orchestrators.thumbnail_maker.run", (), "visual_mode"),
            ("astrid.packs.video_editing.orchestrators.thumbnail_maker.run", (), "reference_mode"),
            ("astrid.packs.video_editing.orchestrators.logo_ideas.run", (), "provider"),
            ("astrid.packs.video_editing.orchestrators.logo_ideas.run", (), "output_format"),
            ("astrid.packs.vibecomfy.executors.run.run", (), "command"),
            ("astrid.packs.vibecomfy.executors.validate.run", (), "command"),
        ]

        with patch.dict(os.environ, {"ASTRID_INTERNAL_INVOCATION": "1"}):
            for module_name, parser_path, dest in cases:
                with self.subTest(module=module_name, parser_path=parser_path, dest=dest):
                    module = importlib.import_module(module_name)
                    parser = module.build_parser()
                    action = _parser_action(parser, dest=dest, parser_path=parser_path)
                    self.assertIsInstance(action.choices, StaticChoices)

if __name__ == "__main__":
    unittest.main()
