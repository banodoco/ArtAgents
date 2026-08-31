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
        "aliases": {},
    },
    "understanding": {
        "origin": "builtin",
        "domain": "media",
        "content": {"executors": "executors"},
        "aliases": {},
    },
    "generation": {
        "origin": "builtin",
        "domain": "generation",
        "content": {"executors": "executors"},
        "aliases": {},
    },
    "editorial": {
        "origin": "builtin",
        "domain": "editorial",
        "content": {"executors": "executors"},
        "aliases": {},
    },
    "video_editing": {
        "origin": "builtin",
        "domain": "media",
        "content": {"executors": "executors", "orchestrators": "orchestrators"},
        "aliases": {},
    },
    "foley": {
        "origin": "builtin",
        "domain": "media",
        "content": {"executors": "executors", "orchestrators": "orchestrators"},
        "aliases": {},
    },
    "training": {
        "origin": "builtin",
        "domain": "development",
        "content": {"executors": "executors", "orchestrators": "orchestrators"},
        "aliases": {},
    },
    "youtube": {
        "origin": "builtin",
        "domain": "integration",
        "content": {"executors": "executors"},
        "aliases": {},
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
