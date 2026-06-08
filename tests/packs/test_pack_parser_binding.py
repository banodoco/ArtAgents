"""Parser tests for child-pack managed binding surface (m3.5).

Proves:
1. cut, refine, and assemble parsers accept --project and --timeline-slug.
2. None of them accept --timeline-id (reserved for executor UUID mode).
3. Managed mode (both flags) vs unmanaged mode (neither) is correctly detected.
4. Mixed flags (only one of --project/--timeline-slug) raises an error.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from astrid.core.task.managed_binding import is_managed_mode
from astrid.packs.video_editing.executors.cut.run import build_parser as cut_build_parser
from astrid.packs.editorial.executors.refine.run import build_parser as refine_build_parser
from astrid.packs.iteration.executors.assemble.run import build_parser as assemble_build_parser


class ManagedBindingParserTests(unittest.TestCase):
    """Prove --project and --timeline-slug are accepted, --timeline-id is NOT."""

    # ------------------------------------------------------------------
    # video_editing.cut
    # ------------------------------------------------------------------
    def test_cut_parser_accepts_project_and_timeline_slug(self) -> None:
        parser = cut_build_parser()
        args = parser.parse_args(
            ["--scenes", "/tmp/s.json", "--arrangement", "/tmp/a.json",
             "--pool", "/tmp/p.json", "--brief", "/tmp/b.txt",
             "--out", "/tmp/out", "--project", "my-project",
             "--timeline-slug", "my-timeline"])
        self.assertEqual(args.project, "my-project")
        self.assertEqual(args.timeline_slug, "my-timeline")

    def test_cut_parser_rejects_timeline_id(self) -> None:
        parser = cut_build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["--scenes", "/tmp/s.json", "--arrangement", "/tmp/a.json",
                 "--pool", "/tmp/p.json", "--brief", "/tmp/b.txt",
                 "--out", "/tmp/out", "--timeline-id", "some-uuid"])

    # ------------------------------------------------------------------
    # editorial.refine
    # ------------------------------------------------------------------
    def test_refine_parser_accepts_project_and_timeline_slug(self) -> None:
        parser = refine_build_parser()
        args = parser.parse_args(
            ["--arrangement", "/tmp/a.json", "--pool", "/tmp/p.json",
             "--timeline", "/tmp/t.json", "--assets", "/tmp/a.json",
             "--metadata", "/tmp/m.json", "--transcript", "/tmp/t.json",
             "--out", "/tmp/out", "--project", "my-project",
             "--timeline-slug", "my-timeline"])
        self.assertEqual(args.project, "my-project")
        self.assertEqual(args.timeline_slug, "my-timeline")

    def test_refine_parser_rejects_timeline_id(self) -> None:
        parser = refine_build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["--arrangement", "/tmp/a.json", "--pool", "/tmp/p.json",
                 "--timeline", "/tmp/t.json", "--assets", "/tmp/a.json",
                 "--metadata", "/tmp/m.json", "--transcript", "/tmp/t.json",
                 "--out", "/tmp/out", "--timeline-id", "some-uuid"])

    # ------------------------------------------------------------------
    # iteration.assemble
    # ------------------------------------------------------------------
    def test_assemble_parser_accepts_project_and_timeline_slug(self) -> None:
        parser = assemble_build_parser()
        args = parser.parse_args(
            ["--prepare-dir", "/tmp/prep", "--out", "/tmp/out",
             "--project", "my-project", "--timeline-slug", "my-timeline"])
        self.assertEqual(args.project, "my-project")
        self.assertEqual(args.timeline_slug, "my-timeline")

    def test_assemble_parser_rejects_timeline_id(self) -> None:
        parser = assemble_build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["--prepare-dir", "/tmp/prep", "--out", "/tmp/out",
                 "--timeline-id", "some-uuid"])

    # ------------------------------------------------------------------
    # managed mode detection
    # ------------------------------------------------------------------
    def test_cut_managed_mode_both_flags(self) -> None:
        parser = cut_build_parser()
        args = parser.parse_args(
            ["--scenes", "/tmp/s.json", "--arrangement", "/tmp/a.json",
             "--pool", "/tmp/p.json", "--brief", "/tmp/b.txt",
             "--out", "/tmp/out", "--project", "p", "--timeline-slug", "t"])
        self.assertTrue(is_managed_mode(args))

    def test_cut_unmanaged_mode_neither_flag(self) -> None:
        parser = cut_build_parser()
        args = parser.parse_args(
            ["--scenes", "/tmp/s.json", "--arrangement", "/tmp/a.json",
             "--pool", "/tmp/p.json", "--brief", "/tmp/b.txt",
             "--out", "/tmp/out"])
        self.assertFalse(is_managed_mode(args))

    def test_cut_unmanaged_mode_only_project(self) -> None:
        parser = cut_build_parser()
        args = parser.parse_args(
            ["--scenes", "/tmp/s.json", "--arrangement", "/tmp/a.json",
             "--pool", "/tmp/p.json", "--brief", "/tmp/b.txt",
             "--out", "/tmp/out", "--project", "p"])
        self.assertFalse(is_managed_mode(args))

    def test_refine_managed_mode_both_flags(self) -> None:
        parser = refine_build_parser()
        args = parser.parse_args(
            ["--arrangement", "/tmp/a.json", "--pool", "/tmp/p.json",
             "--timeline", "/tmp/t.json", "--assets", "/tmp/a.json",
             "--metadata", "/tmp/m.json", "--transcript", "/tmp/t.json",
             "--out", "/tmp/out", "--project", "p", "--timeline-slug", "t"])
        self.assertTrue(is_managed_mode(args))

    def test_assemble_managed_mode_both_flags(self) -> None:
        parser = assemble_build_parser()
        args = parser.parse_args(
            ["--prepare-dir", "/tmp/prep", "--out", "/tmp/out",
             "--project", "p", "--timeline-slug", "t"])
        self.assertTrue(is_managed_mode(args))


# ── m3.5 T18: Hype subprocess caller tests ────────────────────────────


class HypeSubprocessCallerTests(unittest.TestCase):
    """Prove managed binding args are passed to child pack subprocess commands."""

    def _make_args(self, project=None, timeline_slug=None):
        """Build a minimal argparse.Namespace like hype main() produces."""
        import argparse
        args = argparse.Namespace()
        args.project = project
        args.timeline_slug = timeline_slug
        # Fields required by build_pool_cut_cmd and friends.
        args.out = Path("/tmp/hype-out")
        args.brief_out = Path("/tmp/hype-brief-out")
        args.brief_copy = Path("/tmp/hype-brief-copy")
        args.python_exec = None
        args.video = None
        args.audio = None
        args.skip = set()
        args.asset_pairs = []
        args.theme_explicit = False
        args.theme = None
        args.primary_asset = None
        return args

    # --------------------------------------------------------------
    # _append_managed_binding
    # --------------------------------------------------------------
    def test_append_managed_binding_with_managed_args(self):
        """_append_managed_binding appends --project and --timeline-slug."""
        from astrid.packs.video_editing.orchestrators.hype.run import _append_managed_binding

        args = self._make_args(project="my-proj", timeline_slug="my-tl")
        cmd = ["python3", "-m", "astrid.packs.video_editing.executors.cut.run", "--pool", "p.json"]
        result = _append_managed_binding(args, cmd)

        self.assertIn("--project", result)
        self.assertIn("--timeline-slug", result)
        idx_proj = result.index("--project")
        idx_slug = result.index("--timeline-slug")
        self.assertEqual(result[idx_proj + 1], "my-proj")
        self.assertEqual(result[idx_slug + 1], "my-tl")
        # Original cmd args are preserved
        self.assertIn("--pool", result)
        self.assertIn("p.json", result)

    def test_append_managed_binding_without_project(self):
        """_append_managed_binding does nothing when project is None."""
        from astrid.packs.video_editing.orchestrators.hype.run import _append_managed_binding

        args = self._make_args(project=None, timeline_slug="my-tl")
        cmd = ["python3", "--flag"]
        result = _append_managed_binding(args, cmd)

        self.assertEqual(result, ["python3", "--flag"])
        self.assertNotIn("--project", result)
        self.assertNotIn("--timeline-slug", result)

    def test_append_managed_binding_without_timeline_slug(self):
        """_append_managed_binding does nothing when timeline_slug is None."""
        from astrid.packs.video_editing.orchestrators.hype.run import _append_managed_binding

        args = self._make_args(project="my-proj", timeline_slug=None)
        cmd = ["python3", "--flag"]
        result = _append_managed_binding(args, cmd)

        self.assertEqual(result, ["python3", "--flag"])
        self.assertNotIn("--project", result)
        self.assertNotIn("--timeline-slug", result)

    def test_append_managed_binding_without_both(self):
        """_append_managed_binding does nothing when both are None."""
        from astrid.packs.video_editing.orchestrators.hype.run import _append_managed_binding

        args = self._make_args(project=None, timeline_slug=None)
        cmd = ["python3", "--flag"]
        result = _append_managed_binding(args, cmd)

        self.assertEqual(result, cmd)
        self.assertNotIn("--project", result)

    def test_append_managed_binding_returns_same_list(self):
        """_append_managed_binding returns the mutated list (same object)."""
        from astrid.packs.video_editing.orchestrators.hype.run import _append_managed_binding

        args = self._make_args(project="proj", timeline_slug="tl")
        cmd = ["base-cmd"]
        result = _append_managed_binding(args, cmd)
        self.assertIs(result, cmd, "should return the same list object for chaining")

    # --------------------------------------------------------------
    # build_pool_cut_cmd
    # --------------------------------------------------------------
    def test_build_pool_cut_cmd_includes_managed_binding(self):
        """build_pool_cut_cmd includes --project and --timeline-slug when managed."""
        from astrid.packs.video_editing.orchestrators.hype.run import build_pool_cut_cmd

        args = self._make_args(project="my-proj", timeline_slug="my-tl")
        cmd = build_pool_cut_cmd(args)

        self.assertIn("--project", cmd)
        self.assertIn("--timeline-slug", cmd)
        idx_proj = cmd.index("--project")
        idx_slug = cmd.index("--timeline-slug")
        self.assertEqual(cmd[idx_proj + 1], "my-proj")
        self.assertEqual(cmd[idx_slug + 1], "my-tl")
        # Core args are present
        self.assertIn("--pool", cmd)
        self.assertIn("--arrangement", cmd)
        self.assertIn("--brief", cmd)
        self.assertIn("--out", cmd)

    def test_build_pool_cut_cmd_excludes_managed_binding_when_unmanaged(self):
        """build_pool_cut_cmd does NOT include --project/--timeline-slug when unmanaged."""
        from astrid.packs.video_editing.orchestrators.hype.run import build_pool_cut_cmd

        args = self._make_args(project=None, timeline_slug=None)
        cmd = build_pool_cut_cmd(args)

        self.assertNotIn("--project", cmd)
        self.assertNotIn("--timeline-slug", cmd)
        # But core args are still present
        self.assertIn("--pool", cmd)
        self.assertIn("--arrangement", cmd)


if __name__ == "__main__":
    unittest.main()
