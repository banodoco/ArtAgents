"""Tests for `astrid skills sync`: gateway linking, registry block, --deep, --check.

All filesystem effects are pinned to a tmp ``$HOME`` (via the shared ``_Tmp``
fixture, which patches ``Path.home``) and to a temp copy of the gateway
SKILL.md, so the suite never mutates the real ``~/.claude`` / ``~/.codex`` dirs
or the in-repo ``_core/skill/SKILL.md``.
"""

from __future__ import annotations

import argparse
import io
import contextlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from astrid import skills
from astrid.skills import cli as skills_cli
from astrid.skills import discovery, registry
from astrid.skills.harnesses import ClaudeAdapter, CodexAdapter
from astrid.skills.harnesses.base import (
    is_ours,
    ours_link_to_pack_id,
    prune_orphan_skill_links,
)

# Reuse the shared HOME-pinning fixture from the main skills test module.
from tests.test_skills import _Tmp


def _descriptors():
    return discovery.list_skills()


def _write_skill_md(tmp: Path, body: str | None = None) -> Path:
    """Write a temp gateway SKILL.md and return its path."""
    text = body if body is not None else (
        "---\nname: \"astrid\"\nshort_description: \"gw\"\n---\n\n"
        "# Astrid\n\nIntro paragraph.\n\n## Start Here\n\nbody body body\n"
    )
    path = tmp / "SKILL.md"
    path.write_text(text, encoding="utf-8")
    return path


class BaseHelperTest(unittest.TestCase):
    def test_is_ours_matches_only_astrid_namespace(self) -> None:
        self.assertTrue(is_ours("astrid"))
        self.assertTrue(is_ours("astrid-foley"))
        self.assertFalse(is_ours("image-generation"))
        self.assertFalse(is_ours("astridx"))  # no separator → foreign

    def test_ours_link_to_pack_id(self) -> None:
        self.assertEqual(ours_link_to_pack_id("astrid"), "_core")
        self.assertEqual(ours_link_to_pack_id("astrid-foley"), "foley")
        self.assertIsNone(ours_link_to_pack_id("image-generation"))

    def test_prune_removes_only_stale_ours_symlinks(self) -> None:
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            real_target = d / "real"
            real_target.mkdir()
            # ours + known → keep
            (d / "astrid-foley").symlink_to(real_target)
            # ours + stale → remove
            (d / "astrid-gone").symlink_to(real_target)
            # gateway → never pruned here
            (d / "astrid").symlink_to(real_target)
            # foreign symlink → never touched
            (d / "image-generation").symlink_to(real_target)
            # foreign real dir named like ours → never touched (not a symlink)
            (d / "astrid-realdir").mkdir()

            removed = prune_orphan_skill_links(d, known_pack_ids={"foley"})

            self.assertEqual([p.name for p in removed], ["astrid-gone"])
            self.assertTrue((d / "astrid-foley").exists())
            self.assertTrue((d / "astrid").exists())
            self.assertTrue((d / "image-generation").exists())
            self.assertTrue((d / "astrid-realdir").is_dir())


class RegistryBlockTest(unittest.TestCase):
    def test_insert_when_markers_absent_preserves_outside_content(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _write_skill_md(Path(tmp))
            before = path.read_text(encoding="utf-8")
            changed = registry.regenerate(skill_md_path=path)
            self.assertTrue(changed)
            after = path.read_text(encoding="utf-8")
            # Markers + heading present, gateway not listing itself.
            self.assertIn(registry.BEGIN_MARKER, after)
            self.assertIn(registry.END_MARKER, after)
            self.assertIn("## Installed packs", after)
            self.assertNotIn("| _core |", after)
            # Original headings preserved.
            self.assertIn("# Astrid", after)
            self.assertIn("## Start Here", after)
            self.assertIn("body body body", after)
            self.assertNotEqual(before, after)

    def test_replace_is_idempotent_and_preserves_outside(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _write_skill_md(Path(tmp))
            registry.regenerate(skill_md_path=path)
            once = path.read_text(encoding="utf-8")
            # Second run makes no change.
            self.assertFalse(registry.regenerate(skill_md_path=path))
            self.assertEqual(path.read_text(encoding="utf-8"), once)
            self.assertTrue(registry.is_current(skill_md_path=path))

    def test_replace_block_only_touches_between_markers(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _write_skill_md(Path(tmp))
            registry.regenerate(skill_md_path=path)
            text = path.read_text(encoding="utf-8")
            # Inject a sentinel before and after the block, plus stale content
            # inside it, then re-run; outside must survive, inside must refresh.
            tampered = text.replace(
                registry.BEGIN_MARKER,
                "PRE_SENTINEL\n" + registry.BEGIN_MARKER,
            ).replace(
                registry.END_MARKER,
                registry.END_MARKER + "\nPOST_SENTINEL",
            )
            # Corrupt content inside the block.
            tampered = tampered.replace("## Installed packs", "## STALE")
            path.write_text(tampered, encoding="utf-8")
            registry.regenerate(skill_md_path=path)
            final = path.read_text(encoding="utf-8")
            self.assertIn("PRE_SENTINEL", final)
            self.assertIn("POST_SENTINEL", final)
            self.assertIn("## Installed packs", final)
            self.assertNotIn("## STALE", final)

    def test_deep_block_includes_skill_names(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _write_skill_md(Path(tmp))
            registry.regenerate(skill_md_path=path, deep=True)
            text = path.read_text(encoding="utf-8")
            self.assertIn("Skill name", text)
            self.assertIn("`astrid-foley`", text)
            # Switching back to shallow drops the skill-name column.
            registry.regenerate(skill_md_path=path, deep=False)
            text2 = path.read_text(encoding="utf-8")
            self.assertNotIn("`astrid-foley`", text2)


class SyncGatewayTest(unittest.TestCase):
    def test_gateway_only_links_core_and_writes_registry(self) -> None:
        fx = _Tmp()
        try:
            with TemporaryDirectory() as tmp:
                md = _write_skill_md(Path(tmp))
                report = skills.sync(skill_md_path=md, state_path=fx.state_path)
                self.assertTrue(report["registry"]["changed"])
                # Gateway link created in both detected harnesses.
                claude = ClaudeAdapter()
                codex = CodexAdapter()
                core = next(d for d in _descriptors() if d.pack_id == "_core")
                self.assertTrue(claude.target_for(core).is_symlink())
                self.assertTrue(codex.target_for(core).is_symlink())
                # A non-core pack is NOT linked in gateway-only mode.
                foley = next(d for d in _descriptors() if d.pack_id == "foley")
                self.assertFalse(claude.target_for(foley).exists())
                # Registry block written to the temp SKILL.md.
                self.assertIn(registry.BEGIN_MARKER, md.read_text(encoding="utf-8"))
        finally:
            fx.close()

    def test_sync_is_idempotent(self) -> None:
        fx = _Tmp()
        try:
            with TemporaryDirectory() as tmp:
                md = _write_skill_md(Path(tmp))
                skills.sync(skill_md_path=md, state_path=fx.state_path)
                report2 = skills.sync(skill_md_path=md, state_path=fx.state_path)
                self.assertFalse(report2["registry"]["changed"])
                for action in report2["actions"]:
                    for step in action["steps"]:
                        self.assertFalse(step["extras"].get("changed"))
        finally:
            fx.close()

    def test_sync_never_clobbers_foreign_entry(self) -> None:
        fx = _Tmp()
        try:
            with TemporaryDirectory() as tmp:
                md = _write_skill_md(Path(tmp))
                claude_skills = fx.home / ".claude" / "skills"
                claude_skills.mkdir(parents=True, exist_ok=True)
                foreign = claude_skills / "image-generation"
                foreign.mkdir()
                marker = foreign / "SKILL.md"
                marker.write_text("foreign", encoding="utf-8")
                skills.sync(skill_md_path=md, state_path=fx.state_path)
                # Foreign entry untouched.
                self.assertTrue(foreign.is_dir())
                self.assertEqual(marker.read_text(encoding="utf-8"), "foreign")
        finally:
            fx.close()

    def test_deep_links_per_pack_and_prunes_stale(self) -> None:
        fx = _Tmp()
        try:
            with TemporaryDirectory() as tmp:
                md = _write_skill_md(Path(tmp))
                skills.sync(skill_md_path=md, deep=True, state_path=fx.state_path)
                claude = ClaudeAdapter()
                foley = next(d for d in _descriptors() if d.pack_id == "foley")
                target = claude.target_for(foley)
                self.assertTrue(target.is_symlink())
                self.assertEqual(target.name, "astrid-foley")

                # Plant a stale ours-link for a pack that does not exist, then
                # re-sync: it must be pruned, real ones kept.
                stale = claude.skills_dir / "astrid-ghostpack"
                stale.symlink_to(foley.skill_dir)
                report = skills.sync(skill_md_path=md, deep=True, state_path=fx.state_path)
                self.assertFalse(stale.exists())
                self.assertTrue(target.is_symlink())
                pruned = [
                    s
                    for a in report["actions"]
                    for s in a["steps"]
                    if s["extras"].get("pruned")
                ]
                self.assertTrue(any("astrid-ghostpack" in s["description"] for s in pruned))
        finally:
            fx.close()


class CheckTest(unittest.TestCase):
    def test_check_reports_drift_and_exit_code_then_clean(self) -> None:
        fx = _Tmp()
        try:
            with TemporaryDirectory() as tmp:
                md = _write_skill_md(Path(tmp))
                # Before any sync: registry stale + gateway not linked.
                report = skills.check(skill_md_path=md)
                self.assertTrue(report["has_drift"])
                self.assertTrue(report["registry_stale"])
                self.assertTrue(report["missing"])

                # check() must make NO changes.
                self.assertNotIn(registry.BEGIN_MARKER, md.read_text(encoding="utf-8"))
                claude = ClaudeAdapter()
                core = next(d for d in _descriptors() if d.pack_id == "_core")
                self.assertFalse(claude.target_for(core).exists())

                # After sync, check is clean.
                skills.sync(skill_md_path=md, state_path=fx.state_path)
                clean = skills.check(skill_md_path=md)
                self.assertFalse(clean["has_drift"])
                self.assertFalse(clean["registry_stale"])
                self.assertEqual(clean["missing"], [])
                self.assertEqual(clean["stale_links"], [])
        finally:
            fx.close()

    def test_check_detects_stale_link(self) -> None:
        fx = _Tmp()
        try:
            with TemporaryDirectory() as tmp:
                md = _write_skill_md(Path(tmp))
                skills.sync(skill_md_path=md, state_path=fx.state_path)
                claude = ClaudeAdapter()
                foley = next(d for d in _descriptors() if d.pack_id == "foley")
                (claude.skills_dir / "astrid-ghostpack").symlink_to(foley.skill_dir)
                report = skills.check(skill_md_path=md)
                self.assertTrue(report["has_drift"])
                self.assertTrue(
                    any(e["link"] == "astrid-ghostpack" for e in report["stale_links"])
                )
        finally:
            fx.close()

    def test_cli_check_exit_codes(self) -> None:
        fx = _Tmp()
        try:
            with TemporaryDirectory() as tmp:
                md = _write_skill_md(Path(tmp))
                parser = skills_cli.build_parser()

                def _run(extra: list[str]) -> int:
                    args = parser.parse_args(["sync", *extra])
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        # Pin both the temp SKILL.md and tmp state by patching
                        # the module-level check/sync to inject our paths.
                        rc = _dispatch(args, md, fx.state_path)
                    return rc

                # Drift present → exit 1.
                self.assertEqual(_run(["--check"]), 1)
                # Apply, then check clean → exit 0.
                _dispatch(parser.parse_args(["sync"]), md, fx.state_path)
                self.assertEqual(_run(["--check"]), 0)
        finally:
            fx.close()


def _dispatch(args: argparse.Namespace, md: Path, state_path: Path) -> int:
    """Invoke the sync handler with temp SKILL.md + tmp state injected."""
    if getattr(args, "check", False):
        report = skills.check(deep=args.deep, skill_md_path=md)
        return 1 if report["has_drift"] else 0
    skills.sync(
        mechanism=args.mechanism,
        force=args.force,
        deep=args.deep,
        dry_run=args.dry_run,
        skill_md_path=md,
        state_path=state_path,
    )
    return 0


if __name__ == "__main__":
    unittest.main()
