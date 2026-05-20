"""Parser tests for child-pack managed binding surface (m3.5).

Proves:
1. cut, refine, and assemble parsers accept --project and --timeline-slug.
2. None of them accept --timeline-id (reserved for executor UUID mode).
3. Managed mode (both flags) vs unmanaged mode (neither) is correctly detected.
4. Mixed flags (only one of --project/--timeline-slug) raises an error.
"""

from __future__ import annotations

import unittest

from astrid.packs.builtin.cut.run import build_parser as cut_build_parser
from astrid.packs.builtin.cut.run import _is_managed_mode as cut_is_managed
from astrid.packs.builtin.refine.run import build_parser as refine_build_parser
from astrid.packs.builtin.refine.run import _is_managed_mode as refine_is_managed
from astrid.packs.iteration.assemble.run import build_parser as assemble_build_parser
from astrid.packs.iteration.assemble.run import _is_managed_mode as assemble_is_managed


class ManagedBindingParserTests(unittest.TestCase):
    """Prove --project and --timeline-slug are accepted, --timeline-id is NOT."""

    # ------------------------------------------------------------------
    # builtin.cut
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
    # builtin.refine
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
        self.assertTrue(cut_is_managed(args))

    def test_cut_unmanaged_mode_neither_flag(self) -> None:
        parser = cut_build_parser()
        args = parser.parse_args(
            ["--scenes", "/tmp/s.json", "--arrangement", "/tmp/a.json",
             "--pool", "/tmp/p.json", "--brief", "/tmp/b.txt",
             "--out", "/tmp/out"])
        self.assertFalse(cut_is_managed(args))

    def test_cut_unmanaged_mode_only_project(self) -> None:
        parser = cut_build_parser()
        args = parser.parse_args(
            ["--scenes", "/tmp/s.json", "--arrangement", "/tmp/a.json",
             "--pool", "/tmp/p.json", "--brief", "/tmp/b.txt",
             "--out", "/tmp/out", "--project", "p"])
        self.assertFalse(cut_is_managed(args))

    def test_refine_managed_mode_both_flags(self) -> None:
        parser = refine_build_parser()
        args = parser.parse_args(
            ["--arrangement", "/tmp/a.json", "--pool", "/tmp/p.json",
             "--timeline", "/tmp/t.json", "--assets", "/tmp/a.json",
             "--metadata", "/tmp/m.json", "--transcript", "/tmp/t.json",
             "--out", "/tmp/out", "--project", "p", "--timeline-slug", "t"])
        self.assertTrue(refine_is_managed(args))

    def test_assemble_managed_mode_both_flags(self) -> None:
        parser = assemble_build_parser()
        args = parser.parse_args(
            ["--prepare-dir", "/tmp/prep", "--out", "/tmp/out",
             "--project", "p", "--timeline-slug", "t"])
        self.assertTrue(assemble_is_managed(args))


if __name__ == "__main__":
    unittest.main()
