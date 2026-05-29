"""Source-level contract checks for the Remotion render surface.

These are deliberately dependency-light: the Remotion typecheck requires
`remotion/node_modules`, which is absent in CI by default, so the typecheck is
run only as an opportunistic smoke when dependencies are present. The remaining
checks prove the augmentation import resolves and that the builtin text-card
renders visible markup rather than an empty frame.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTION = ROOT / "remotion"
TEXT_CARD = ROOT / "astrid" / "packs" / "rendering" / "elements" / "effects" / "text-card" / "component.tsx"


class RemotionAugmentationImportTest(unittest.TestCase):
    def test_root_augmentation_import_resolves(self) -> None:
        root_tsx = (REMOTION / "src" / "Root.tsx").read_text(encoding="utf-8")
        # Collect the symbols Root.tsx imports from ./types.augmentations.
        match = re.search(
            r"import type \{([^}]*)\} from './types\.augmentations'", root_tsx
        )
        self.assertIsNotNone(match, "Root.tsx must import types from ./types.augmentations")
        imported = {name.strip() for name in match.group(1).split(",") if name.strip()}

        aug_path = REMOTION / "src" / "types.augmentations.ts"
        self.assertTrue(aug_path.is_file(), "types.augmentations.ts must exist (no missing augmentation import)")
        aug_src = aug_path.read_text(encoding="utf-8")
        for name in imported:
            self.assertRegex(
                aug_src,
                rf"export (interface|type) {re.escape(name)}\b",
                f"types.augmentations.ts must export {name}",
            )


class TextCardVisibleMarkupTest(unittest.TestCase):
    def test_text_card_renders_visible_markup(self) -> None:
        src = TEXT_CARD.read_text(encoding="utf-8")
        # It must no longer be the empty `() => null` stub.
        self.assertNotRegex(
            src.replace("\n", " "),
            r"export default function \w+\(\)\s*\{\s*return null;\s*\}",
        )
        # It must render content via JSX markup keyed off the manifest params.
        self.assertIn("content", src)
        self.assertIn("AbsoluteFill", src)
        self.assertIn("narrowParams", src)
        self.assertRegex(src, r"<AbsoluteFill")


class RemotionTypecheckSmokeTest(unittest.TestCase):
    def test_remotion_typecheck_when_dependencies_present(self) -> None:
        if not (REMOTION / "node_modules").is_dir():
            self.skipTest("remotion/node_modules absent; typecheck smoke skipped")
        result = subprocess.run(
            ["npm", "run", "typecheck"],
            cwd=str(REMOTION),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"remotion typecheck failed:\n{result.stdout}\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
