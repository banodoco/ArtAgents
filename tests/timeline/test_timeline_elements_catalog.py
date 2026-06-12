import tempfile
import unittest
from pathlib import Path
from unittest import mock

from astrid.core.element import catalog as effects_catalog
from astrid.core import timeline


class TimelineElementsCatalogTest(unittest.TestCase):
    def test_package_imported_timeline_uses_non_empty_element_catalogs(self) -> None:
        self.assertIn("text-card", effects_catalog.list_effect_ids())
        self.assertIn("fade-up", effects_catalog.list_animation_ids())
        self.assertIn("cross-fade", effects_catalog.list_transition_ids())
        self.assertIn("text-card", effects_catalog.list_element_ids("effect"))

        config = {
            "theme": "banodoco-default",
            "tracks": [{"id": "v1", "kind": "visual", "label": "Visual"}],
            "clips": [
                {
                    "id": "a",
                    "at": 0,
                    "track": "v1",
                    "clipType": "text-card",
                    "hold": 1,
                    "params": {"content": "A", "entrance": "fade-up"},
                    "transition": {"id": "cross-fade", "durationFrames": 8},
                },
                {"id": "b", "at": 1, "track": "v1", "clipType": "text-card", "hold": 1, "params": {"content": "B"}},
            ],
        }

        timeline.validate_timeline(config)
        config["clips"][0]["params"]["entrance"] = "missing-animation"
        with self.assertRaisesRegex(ValueError, "animations catalog"):
            timeline.validate_timeline(config)

    def test_explicit_theme_arg_enables_theme_override_behavior(self) -> None:
        import json
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp) / "theme"
            root = theme / "effects" / "theme-only"
            root.mkdir(parents=True)
            (root / "component.tsx").write_text("export default function ThemeOnly() { return null; }\n", encoding="utf-8")
            (root / "element.yaml").write_text(
                json.dumps(
                    {
                        "id": "theme-only",
                        "kind": "effect",
                        "metadata": {"clipTypeAliases": ["theme"]},
                        "schema": {"type": "object"},
                        "defaults": {},
                        "dependencies": {"js_packages": [], "python_requirements": []},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            self.assertIn("theme-only", effects_catalog.list_effect_ids(theme=theme))
            self.assertEqual(effects_catalog.read_effect_meta("theme-only", theme=theme)["clipTypeAliases"], ["theme"])

    def test_catalog_exposes_pack_declared_custom_kinds(self) -> None:
        import json

        from astrid.core.element import registry as registry_module
        from astrid.core.pack import discover_packs as real_discover_packs

        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = packs_root / "demo"
            pack_root.mkdir(parents=True)
            (pack_root / "pack.json").write_text(
                json.dumps(
                    {
                        "id": "demo",
                        "name": "Demo Pack",
                        "version": "0.1.0",
                        "schema_version": "1",
                        "extensions": {
                            "elements": {
                                "kinds": [
                                    {"id": "widgets", "singular": "widget"},
                                ]
                            }
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            element_root = pack_root / "elements" / "widgets" / "glow"
            element_root.mkdir(parents=True)
            (element_root / "component.tsx").write_text(
                "export default function Glow() { return null; }\n",
                encoding="utf-8",
            )
            (element_root / "element.yaml").write_text(
                json.dumps(
                    {
                        "id": "glow",
                        "kind": "widget",
                        "pack_id": "demo",
                        "metadata": {"label": "Glow"},
                        "schema": {"type": "object"},
                        "defaults": {"enabled": True},
                        "dependencies": {"js_packages": [], "python_requirements": []},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                registry_module,
                "discover_packs",
                side_effect=lambda root=None: real_discover_packs() + real_discover_packs(packs_root),
            ):
                effects_catalog._clear_registry_cache()
                try:
                    self.assertIn("glow", effects_catalog.list_element_ids("widget"))
                    self.assertEqual(effects_catalog.read_element_meta("glow", kind="widget")["label"], "Glow")
                    self.assertEqual(effects_catalog.element_root("widget").name, "widgets")
                finally:
                    effects_catalog._clear_registry_cache()


if __name__ == "__main__":
    unittest.main()
