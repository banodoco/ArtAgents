"""Regression tests for package-owned generated element registries.

Executable timeline elements are discovered from Astrid packs and generated
into the timeline-composition package. A theme is authoring data and cannot
add executable code to that registry.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from astrid.core.element import catalog as effects_catalog


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts" / "gen_effect_registry.py"

_SPEC = importlib.util.spec_from_file_location("gen_effect_registry", GENERATOR)
assert _SPEC is not None and _SPEC.loader is not None
gen_effect_registry = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = gen_effect_registry
_SPEC.loader.exec_module(gen_effect_registry)
GENERATED_FILES = tuple(gen_effect_registry.OUTPUTS.values())


class EffectsCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self._generated_before = {
            path: path.read_bytes() if path.exists() else None
            for path in GENERATED_FILES
        }

    def tearDown(self) -> None:
        for path, content in self._generated_before.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

    def _run_generator(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(GENERATOR), *args],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )

    def test_catalog_reads_pack_owned_element_files(self) -> None:
        self.assertIn("text-card", effects_catalog.list_effect_ids())
        schema = effects_catalog.read_effect_schema("text-card")
        defaults = effects_catalog.read_effect_defaults("text-card")
        meta = effects_catalog.read_effect_meta("text-card")
        self.assertEqual(schema["type"], "object")
        self.assertIsInstance(defaults, dict)
        self.assertEqual(meta["id"], "text-card")

    def test_generator_outputs_package_owned_registries(self) -> None:
        self._run_generator()
        effects = gen_effect_registry.OUTPUTS["effects"].read_text(encoding="utf-8")
        animations = gen_effect_registry.OUTPUTS["animations"].read_text(encoding="utf-8")
        transitions = gen_effect_registry.OUTPUTS["transitions"].read_text(encoding="utf-8")

        self.assertIn("EFFECT_IDS = ['audio-reactive-colour', 'text-card']", effects)
        self.assertIn("'text-card': TextCard", effects)
        self.assertIn("export const EFFECT_FINGERPRINTS", effects)
        self.assertRegex(effects, r"'text-card': '[0-9a-f]{64}'")
        self.assertIn("ANIMATION_IDS = ['fade', 'fade-up', 'scale-in', 'slide-left', 'slide-up', 'type-on']", animations)
        self.assertIn("TRANSITION_IDS = ['cross-fade', 'fade']", transitions)

    def test_generator_requires_writable_package_outputs(self) -> None:
        def deny_package_output(path: Path, content: str) -> bool:
            self.assertIn(path, GENERATED_FILES)
            return False

        with mock.patch.object(
            gen_effect_registry,
            "_write_generated_registry",
            side_effect=deny_package_output,
        ):
            exit_code = gen_effect_registry._main_unlocked([])

        self.assertEqual(exit_code, 1)

    def test_generator_is_idempotent_for_package_outputs(self) -> None:
        self._run_generator()
        first = {path: path.read_bytes() for path in GENERATED_FILES}
        self._run_generator()
        second = {path: path.read_bytes() for path in GENERATED_FILES}
        self.assertEqual(first, second)

    def test_generated_fingerprint_changes_with_element_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            pack = project / "astrid" / "packs" / "local"
            element = pack / "elements" / "effects" / "hash-probe"
            element.mkdir(parents=True)
            (pack / "pack.yaml").write_text(
                "schema_version: 2\nid: local\nname: Local\nversion: 0.1.0\n"
                "capabilities: [elements]\n",
                encoding="utf-8",
            )
            component = element / "component.tsx"
            component.write_text("export default function HashProbe() { return null; }\n", encoding="utf-8")
            (element / "element.yaml").write_text(
                json.dumps(
                    {
                        "id": "hash-probe",
                        "kind": "effect",
                        "pack_id": "local",
                        "metadata": {"label": "Hash Probe"},
                        "schema": {"type": "object"},
                        "defaults": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            from astrid.core.element import registry as element_registry
            from astrid.core.pack import discover_packs as real_discover_packs

            old_tools_dir = gen_effect_registry.TOOLS_DIR
            old_discover = element_registry.discover_packs
            try:
                gen_effect_registry.TOOLS_DIR = project
                element_registry.discover_packs = lambda root=None: real_discover_packs(pack.parent)
                element_registry.clear_default_registry_cache()
                generated = gen_effect_registry.generate_element_registry("effects")
                first_match = re.search(r"'hash-probe': '([0-9a-f]{64})'", generated)
                self.assertIsNotNone(first_match)
                first = first_match.group(1)
                component.write_text("export default function HashProbe() { return 'v2'; }\n", encoding="utf-8")
                element_registry.clear_default_registry_cache()
                generated = gen_effect_registry.generate_element_registry("effects")
                second_match = re.search(r"'hash-probe': '([0-9a-f]{64})'", generated)
                self.assertIsNotNone(second_match)
                second = second_match.group(1)
            finally:
                gen_effect_registry.TOOLS_DIR = old_tools_dir
                element_registry.discover_packs = old_discover
                element_registry.clear_default_registry_cache()
            self.assertNotEqual(first, second)

    def test_theme_metadata_cannot_add_executable_elements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp) / "theme"
            effect = theme / "effects" / "theme-only"
            effect.mkdir(parents=True)
            (effect / "component.tsx").write_text("export default function ThemeOnly() { return null; }\n", encoding="utf-8")
            (effect / "element.yaml").write_text(
                json.dumps({"id": "theme-only", "kind": "effect", "schema": {"type": "object"}}),
                encoding="utf-8",
            )
            self.assertNotIn("theme-only", effects_catalog.list_effect_ids(theme=theme))
            with self.assertRaises(KeyError):
                effects_catalog.read_effect_meta("theme-only", theme=theme)


if __name__ == "__main__":
    unittest.main()
