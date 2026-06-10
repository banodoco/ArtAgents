import json
import tempfile
import unittest
from pathlib import Path

from astrid.core import element as element_module
from astrid.core.element import load_default_registry


_KIND_SINGULAR = {
    "effects": "effect",
    "animations": "animation",
    "transitions": "transition",
    "widgets": "widget",
}


def write_pack_element(
    pack_root: Path,
    kind: str,
    element_id: str,
    *,
    pack_id: str,
    label: str,
    js_packages: list[str] | None = None,
) -> Path:
    if not any((pack_root / name).exists() for name in ("pack.yaml", "pack.yml", "pack.json")):
        pack_root.mkdir(parents=True, exist_ok=True)
        (pack_root / "pack.yaml").write_text(f"id: {pack_id}\nname: {pack_id}\nversion: 0.1.0\n", encoding="utf-8")
    element_root = pack_root / "elements" / kind / element_id
    element_root.mkdir(parents=True)
    (element_root / "component.tsx").write_text("export default function Element() { return null; }\n", encoding="utf-8")
    (element_root / "element.yaml").write_text(
        json.dumps(
            {
                "id": element_id,
                "kind": _KIND_SINGULAR[kind],
                "pack_id": pack_id,
                "metadata": {"label": label},
                "schema": {"type": "object"},
                "defaults": {"enabled": True},
                "dependencies": {
                    "js_packages": list(js_packages or []),
                    "python_requirements": [],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return element_root


def write_theme_element(theme_root: Path, kind: str, element_id: str, *, label: str) -> Path:
    element_root = theme_root / "elements" / kind / element_id
    element_root.mkdir(parents=True)
    (element_root / "component.tsx").write_text("export default function Element() { return null; }\n", encoding="utf-8")
    (element_root / "element.yaml").write_text(
        json.dumps(
            {
                "id": element_id,
                "kind": _KIND_SINGULAR[kind],
                "metadata": {"label": label},
                "schema": {"type": "object"},
                "defaults": {"enabled": True},
                "dependencies": {"js_packages": [], "python_requirements": []},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return element_root


class ElementRegistryTest(unittest.TestCase):
    def test_element_public_surface_exports_dynamic_kind_registry(self) -> None:
        self.assertIs(element_module.ElementKindRegistry, type(element_module.ELEMENT_KIND_REGISTRY))
        self.assertTrue(hasattr(element_module, "ElementKindDescriptor"))
        self.assertTrue(hasattr(element_module, "load_source_elements"))

    def test_pack_declared_kind_is_lookupable_and_theme_overrides_still_apply(self) -> None:
        from unittest import mock

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
            write_pack_element(
                pack_root,
                "widgets",
                "glow",
                pack_id="demo",
                label="Pack Glow",
            )
            theme = Path(tmp) / "theme"
            write_theme_element(theme, "widgets", "glow", label="Theme Glow")

            with mock.patch.object(
                registry_module,
                "discover_packs",
                side_effect=lambda root=None: real_discover_packs() + real_discover_packs(packs_root),
            ):
                registry = load_default_registry(active_theme=theme)

        winner = registry.get("widget", "glow")
        listed = registry.list("widget")

        self.assertEqual(winner.kind, "widgets")
        self.assertEqual(winner.source, "active_theme")
        self.assertEqual(winner.metadata["label"], "Theme Glow")
        self.assertEqual([(element.kind, element.id) for element in listed], [("widgets", "glow")])

    def test_singular_aliases_normalize_to_builtin_kind_keys(self) -> None:
        registry = load_default_registry()

        effect = registry.get("effect", "text-card")
        animation = registry.get("animation", "fade")
        transitions = registry.list("transition")

        self.assertEqual(effect.kind, "effects")
        self.assertEqual(animation.kind, "animations")
        self.assertIn("cross-fade", {item.id for item in transitions})

    def test_fade_animation_and_fade_transition_coexist_under_kind_keys(self) -> None:
        registry = load_default_registry()
        animation_fade = registry.get("animations", "fade")
        transition_fade = registry.get("transitions", "fade")
        self.assertEqual(animation_fade.kind, "animations")
        self.assertEqual(transition_fade.kind, "transitions")
        self.assertNotEqual(animation_fade.root, transition_fade.root)
        self.assertTrue(str(animation_fade.root).endswith("astrid/packs/rendering/elements/animations/fade"))
        self.assertTrue(str(transition_fade.root).endswith("astrid/packs/rendering/elements/transitions/fade"))

    def test_rendering_pack_defaults_are_discovered_with_pack_source(self) -> None:
        from unittest import mock

        from astrid.core.element import registry as registry_module
        from astrid.core.pack import discover_packs as real_discover_packs

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            with mock.patch.object(
                registry_module,
                "discover_packs",
                side_effect=lambda root=None: tuple(p for p in real_discover_packs() if p.id != "local"),
            ):
                registry = load_default_registry(project_root=project)

            by_key = registry.as_mapping()

            self.assertIn(("effects", "text-card"), by_key)
            self.assertIn(("animations", "fade"), by_key)
            self.assertIn(("transitions", "cross-fade"), by_key)
            text_card = registry.get("effects", "text-card")
            self.assertEqual(text_card.source, "pack:rendering")
            self.assertFalse(text_card.editable)
            self.assertEqual(text_card.metadata["label"], "Text Card")
            self.assertEqual(text_card.metadata["pack_id"], "rendering")

    def test_active_theme_overrides_builtin_pack(self) -> None:
        from unittest import mock

        from astrid.core.element import registry as registry_module
        from astrid.core.pack import discover_packs as real_discover_packs

        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp) / "theme"
            write_theme_element(theme, "effects", "text-card", label="Theme")

            with mock.patch.object(
                registry_module,
                "discover_packs",
                side_effect=lambda root=None: tuple(p for p in real_discover_packs() if p.id != "local"),
            ):
                registry = load_default_registry(active_theme=theme)

        winner = registry.get("effects", "text-card")
        self.assertEqual(winner.source, "active_theme")
        self.assertTrue(winner.editable)
        self.assertEqual(winner.metadata["label"], "Theme")
        conflicts = registry.conflicts()
        text_card_conflicts = [item for item in conflicts if item.kind == "effects" and item.id == "text-card"]
        self.assertEqual(len(text_card_conflicts), 1)
        self.assertEqual(
            [item.source for item in text_card_conflicts[0].shadowed],
            ["pack:rendering"],
        )


if __name__ == "__main__":
    unittest.main()
