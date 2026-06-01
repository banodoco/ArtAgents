"""Comprehensive tests for the ElementKindRegistry.

Covers:
- Built-in registration and singular alias normalization
- Duplicate kind / alias rejection
- Invalid descriptor declarations (empty ids, whitespace, etc.)
- Pack-declared kind loading from extension metadata
- Strict typo detection for undeclared roots
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from astrid.core.element.registry import load_pack_elements
from astrid.core.pack import (
    ELEMENT_KINDS,
    ELEMENT_KIND_REGISTRY,
    ElementKindDescriptor,
    ElementKindRegistry,
    PackValidationError,
    _normalize_element_kinds,
    discover_packs,
    element_kind_registry_for_pack,
    iter_element_roots,
    load_pack_manifest,
    pack_manifest_path,
)


# ---------------------------------------------------------------------------
# Built-in registration and alias normalization
# ---------------------------------------------------------------------------

class BuiltinRegistrationTest(unittest.TestCase):
    def test_builtin_constants_tuple_is_correct(self) -> None:
        self.assertEqual(ELEMENT_KINDS, ("effects", "animations", "transitions"))

    def test_builtin_canonical_kinds_match_constants(self) -> None:
        self.assertEqual(ELEMENT_KIND_REGISTRY.canonical_kinds(), ELEMENT_KINDS)

    def test_builtin_accepted_names_include_canonical_and_singular(self) -> None:
        self.assertEqual(
            ELEMENT_KIND_REGISTRY.accepted_names(),
            (
                "effects",
                "effect",
                "animations",
                "animation",
                "transitions",
                "transition",
            ),
        )

    def test_builtin_singular_aliases_normalize_to_canonical(self) -> None:
        self.assertEqual(ELEMENT_KIND_REGISTRY.normalize("effects"), "effects")
        self.assertEqual(ELEMENT_KIND_REGISTRY.normalize("effect"), "effects")
        self.assertEqual(ELEMENT_KIND_REGISTRY.normalize("animations"), "animations")
        self.assertEqual(ELEMENT_KIND_REGISTRY.normalize("animation"), "animations")
        self.assertEqual(ELEMENT_KIND_REGISTRY.normalize("transitions"), "transitions")
        self.assertEqual(ELEMENT_KIND_REGISTRY.normalize("transition"), "transitions")

    def test_builtin_singular_getter_returns_correct_form(self) -> None:
        self.assertEqual(ELEMENT_KIND_REGISTRY.singular("effects"), "effect")
        self.assertEqual(ELEMENT_KIND_REGISTRY.singular("animations"), "animation")
        self.assertEqual(ELEMENT_KIND_REGISTRY.singular("transitions"), "transition")
        # Singular input should also work (returns the stored singular)
        self.assertEqual(ELEMENT_KIND_REGISTRY.singular("effect"), "effect")
        self.assertEqual(ELEMENT_KIND_REGISTRY.singular("animation"), "animation")
        self.assertEqual(ELEMENT_KIND_REGISTRY.singular("transition"), "transition")

    def test_builtin_descriptor_returns_full_metadata(self) -> None:
        desc = ELEMENT_KIND_REGISTRY.descriptor("effects")
        self.assertEqual(desc.id, "effects")
        self.assertEqual(desc.singular, "effect")
        self.assertEqual(desc.plural, "effects")
        self.assertEqual(desc.canonical_kind, "effects")

    def test_builtin_descriptor_via_singular_alias(self) -> None:
        desc = ELEMENT_KIND_REGISTRY.descriptor("effect")
        self.assertEqual(desc.id, "effects")
        self.assertEqual(desc.singular, "effect")
        self.assertEqual(desc.canonical_kind, "effects")

    def test_aliases_property_includes_all_nonempty_identifiers(self) -> None:
        desc = ElementKindDescriptor(id="widgets", singular="widget", plural="widgets")
        self.assertEqual(desc.aliases, ("widgets", "widget"))

    def test_aliases_deduplicates_when_singular_equals_plural(self) -> None:
        desc = ElementKindDescriptor(id="data", singular="data", plural="data")
        self.assertEqual(desc.aliases, ("data",))

    def test_aliases_omits_empty_singular(self) -> None:
        desc = ElementKindDescriptor(id="things", singular="", plural="things")
        # id and plural are the same, so only one alias
        self.assertEqual(desc.aliases, ("things",))


# ---------------------------------------------------------------------------
# Alias normalization edge-cases
# ---------------------------------------------------------------------------

class AliasNormalizationTest(unittest.TestCase):
    def test_canonical_to_canonical_is_identity(self) -> None:
        for kind in ELEMENT_KINDS:
            with self.subTest(kind=kind):
                self.assertEqual(ELEMENT_KIND_REGISTRY.normalize(kind), kind)

    def test_custom_descriptor_with_explicit_plural(self) -> None:
        registry = ElementKindRegistry()
        registry.register(
            ElementKindDescriptor(
                id="brushes",
                singular="brush",
                plural="brushes",
            )
        )
        self.assertIn("brushes", registry.canonical_kinds())
        self.assertEqual(registry.normalize("brush"), "brushes")
        self.assertEqual(registry.normalize("brushes"), "brushes")

    def test_custom_descriptor_plural_falls_back_to_id(self) -> None:
        registry = ElementKindRegistry()
        registry.register(
            ElementKindDescriptor(
                id="brushes",
                singular="brush",
                plural="",  # empty → id used as canonical
            )
        )
        self.assertEqual(registry.normalize("brush"), "brushes")
        self.assertEqual(registry.normalize("brushes"), "brushes")
        self.assertIn("brushes", registry.canonical_kinds())

    def test_custom_descriptor_with_only_id(self) -> None:
        registry = ElementKindRegistry()
        registry.register(ElementKindDescriptor(id="materials"))
        self.assertIn("materials", registry.canonical_kinds())
        self.assertEqual(registry.normalize("materials"), "materials")


# ---------------------------------------------------------------------------
# Duplicate declarations
# ---------------------------------------------------------------------------

class DuplicateDeclarationTest(unittest.TestCase):
    def test_register_same_canonical_id_twice_raises(self) -> None:
        registry = ElementKindRegistry()
        with self.assertRaisesRegex(ValueError, "duplicate element kind 'brushes'"):
            registry.register(ElementKindDescriptor(id="brushes"))
            registry.register(ElementKindDescriptor(id="brushes"))

    def test_register_conflicting_singular_alias_raises(self) -> None:
        registry = ElementKindRegistry()
        # "effect" is already a built-in alias for "effects"
        with self.assertRaisesRegex(
            ValueError,
            "duplicate element kind alias 'effect'",
        ):
            registry.register(
                ElementKindDescriptor(
                    id="overlay-effects",
                    singular="effect",
                    plural="overlay-effects",
                )
            )

    def test_register_descriptor_whose_id_collides_with_existing_alias_raises(self) -> None:
        registry = ElementKindRegistry()
        # "effect" is an alias for "effects"
        with self.assertRaisesRegex(
            ValueError,
            "duplicate element kind alias 'effect'",
        ):
            registry.register(
                ElementKindDescriptor(
                    id="effect",  # collides with existing alias
                    singular="fx",
                    plural="effect",
                )
            )

    def test_register_many_with_duplicates_raises(self) -> None:
        registry = ElementKindRegistry()
        with self.assertRaises(ValueError):
            registry.register_many(
                [
                    ElementKindDescriptor(id="brushes"),
                    ElementKindDescriptor(id="brushes"),
                ]
            )


# ---------------------------------------------------------------------------
# Invalid declarations
# ---------------------------------------------------------------------------

class InvalidDeclarationTest(unittest.TestCase):
    def test_empty_id_raises(self) -> None:
        registry = ElementKindRegistry()
        with self.assertRaisesRegex(ValueError, "element kind must be a non-empty string"):
            registry.register(ElementKindDescriptor(id=""))

    def test_whitespace_only_id_raises(self) -> None:
        registry = ElementKindRegistry()
        with self.assertRaisesRegex(ValueError, "element kind must be a non-empty string"):
            registry.register(ElementKindDescriptor(id="   "))

    def test_whitespace_only_singular_rejected(self) -> None:
        registry = ElementKindRegistry()
        with self.assertRaisesRegex(ValueError, "element kind alias must be a non-empty string"):
            registry.register(
                ElementKindDescriptor(id="brushes", singular="   ")
            )

    def test_whitespace_only_plural_rejected(self) -> None:
        registry = ElementKindRegistry()
        with self.assertRaisesRegex(ValueError, "element kind must be a non-empty string"):
            registry.register(
                ElementKindDescriptor(id="brushes", singular="brush", plural="   ")
            )


# ---------------------------------------------------------------------------
# Pack-declared kind loading
# ---------------------------------------------------------------------------

class PackDeclaredKindLoadingTest(unittest.TestCase):
    def test_load_pack_with_extension_element_kinds(self) -> None:
        """A pack with extensions.elements.kinds declares new element kinds
        that can be registered into a fresh ElementKindRegistry."""
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = Path(tmp) / "demo"
            pack_root.mkdir(parents=True)
            # Use pack.json to avoid flat-YAML parser issues with nested
            # extensions blocks.
            import json
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
                                    {
                                        "id": "widgets",
                                        "singular": "widget",
                                        "plural": "widgets",
                                    },
                                    {
                                        "id": "overlays",
                                        "singular": "overlay",
                                        "plural": "overlays",
                                    },
                                ]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            extensions = pack.extensions
            self.assertIn("elements", extensions)
            self.assertIn("kinds", extensions["elements"])

            kinds = extensions["elements"]["kinds"]
            self.assertEqual(len(kinds), 2)

            descriptors = tuple(
                ElementKindDescriptor(
                    id=kind["id"],
                    singular=kind.get("singular", ""),
                    plural=kind.get("plural", ""),
                    label=kind.get("label", ""),
                    description=kind.get("description", ""),
                )
                for kind in kinds
            )

            registry = ElementKindRegistry(descriptors=descriptors)

            # Verify built-ins still present
            self.assertIn("effects", registry.canonical_kinds())
            self.assertIn("animations", registry.canonical_kinds())
            self.assertIn("transitions", registry.canonical_kinds())

            # Verify new kinds are registered
            self.assertIn("widgets", registry.canonical_kinds())
            self.assertIn("overlays", registry.canonical_kinds())

            # Verify alias normalization for new kinds
            self.assertEqual(registry.normalize("widget"), "widgets")
            self.assertEqual(registry.normalize("widgets"), "widgets")
            self.assertEqual(registry.normalize("overlay"), "overlays")
            self.assertEqual(registry.normalize("overlays"), "overlays")

    def test_pack_element_kinds_rejects_bare_string_entries(self) -> None:
        """Bare string entries in extensions.elements.kinds are rejected;
        each kind entry must be an object with at least an 'id' field."""
        with self.assertRaisesRegex(PackValidationError, "must be an object"):
            _normalize_element_kinds(["widgets"], path="extensions.elements.kinds")

    def test_pack_declared_kinds_via_normalize_element_kinds_helper(self) -> None:
        """The _normalize_element_kinds helper rejects non-array input."""
        with self.assertRaisesRegex(PackValidationError, "must be an array"):
            _normalize_element_kinds("not-a-list", path="extensions.elements.kinds")

    def test_pack_declared_kinds_rejects_non_dict_entry(self) -> None:
        """_normalize_element_kinds rejects non-object entries in the array."""
        with self.assertRaisesRegex(PackValidationError, "must be an object"):
            _normalize_element_kinds([42], path="extensions.elements.kinds")

    def test_pack_declared_kinds_rejects_missing_id(self) -> None:
        """Each kind entry must have an 'id' field."""
        with self.assertRaisesRegex(PackValidationError, "missing required field"):
            _normalize_element_kinds([{}], path="extensions.elements.kinds")

    def test_pack_declared_kinds_rejects_unknown_key(self) -> None:
        """Unknown fields in a kind entry are rejected."""
        with self.assertRaisesRegex(PackValidationError, "unknown field"):
            _normalize_element_kinds(
                [{"id": "ok", "bad_key": "value"}],
                path="extensions.elements.kinds",
            )

    def test_iter_element_roots_with_pack_declared_kind_after_registration(self) -> None:
        """After registering a pack-declared kind into a fresh registry,
        iterating element roots with that kind name resolves correctly.
        
        This verifies the full pipeline: manifest → extensions → descriptors
        → registry → element root iteration."""
        import json

        with tempfile.TemporaryDirectory() as tmp:
            pack_root = Path(tmp) / "demo"
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
                                    {
                                        "id": "widgets",
                                        "singular": "widget",
                                    }
                                ]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            # Create elements directory structure for the new kind
            widget_dir = pack_root / "elements" / "widgets" / "glow"
            widget_dir.mkdir(parents=True)

            pack = load_pack_manifest(pack_manifest_path(pack_root))

            # Extract kinds from extensions and build a fresh registry
            kinds = [
                ElementKindDescriptor(
                    id=k["id"],
                    singular=k.get("singular", ""),
                    plural=k.get("plural", ""),
                )
                for k in pack.extensions["elements"]["kinds"]
            ]
            registry = ElementKindRegistry(descriptors=kinds)

            # Verify the pack-declared kind is registered
            self.assertIn("widgets", registry.canonical_kinds())
            self.assertEqual(registry.normalize("widget"), "widgets")

            # Verify built-ins are still present
            self.assertIn("effects", registry.canonical_kinds())

            # Verify the elements directory exists under the pack-declared kind
            elements_root = pack.root / "elements"
            kind_root = elements_root / "widgets"
            self.assertTrue(kind_root.is_dir())

            # Verify child directories exist
            children = [child for child in sorted(kind_root.iterdir()) if child.is_dir()]
            self.assertEqual(len(children), 1)
            self.assertEqual(children[0].name, "glow")

    def test_element_kind_registry_for_pack_includes_declared_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = Path(tmp) / "demo"
            pack_root.mkdir(parents=True)
            import json
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
                ),
                encoding="utf-8",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))

            registry = element_kind_registry_for_pack(pack)

            self.assertEqual(registry.normalize("widget"), "widgets")
            self.assertIn("widgets", registry.canonical_kinds())
            self.assertEqual(registry.normalize("effect"), "effects")

    def test_iter_element_roots_derives_pack_declared_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = Path(tmp) / "demo"
            pack_root.mkdir(parents=True)
            import json
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
                ),
                encoding="utf-8",
            )
            element_root = pack_root / "elements" / "widgets" / "glow"
            element_root.mkdir(parents=True)
            pack = load_pack_manifest(pack_manifest_path(pack_root))

            roots = iter_element_roots(pack, kind="widget")

            self.assertEqual(roots, (("widgets", element_root.resolve()),))

    def test_iter_element_roots_rejects_undeclared_kind_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = Path(tmp) / "demo"
            pack_root.mkdir(parents=True)
            import json
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
                ),
                encoding="utf-8",
            )
            (pack_root / "elements" / "widgets" / "glow").mkdir(parents=True)
            (pack_root / "elements" / "widgtes" / "typo").mkdir(parents=True)
            pack = load_pack_manifest(pack_manifest_path(pack_root))

            with self.assertRaisesRegex(PackValidationError, "element kind must be one of"):
                iter_element_roots(pack)

    def test_load_pack_elements_derives_pack_declared_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = packs_root / "demo"
            pack_root.mkdir(parents=True)
            import json
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
                ),
                encoding="utf-8",
            )
            element_root = pack_root / "elements" / "widgets" / "glow"
            element_root.mkdir(parents=True)
            (element_root / "component.tsx").write_text(
                "export default function Element() { return null; }\n",
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
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.element.registry.discover_packs", return_value=packs):
                elements = load_pack_elements(include_installed=False)

            self.assertEqual(
                [(element.kind, element.id, element.source) for element in elements],
                [("widgets", "glow", "pack:demo")],
            )


# ---------------------------------------------------------------------------
# Strict typo detection
# ---------------------------------------------------------------------------

class TypoDetectionTest(unittest.TestCase):
    def test_typo_rejected_with_available_kinds_in_message(self) -> None:
        with self.assertRaisesRegex(ValueError, "element kind must be one of"):
            ELEMENT_KIND_REGISTRY.normalize("effcts")

    def test_typo_rejected_effects_misspelled(self) -> None:
        with self.assertRaises(ValueError):
            ELEMENT_KIND_REGISTRY.normalize("effectss")

    def test_typo_rejected_animations_misspelled(self) -> None:
        with self.assertRaises(ValueError):
            ELEMENT_KIND_REGISTRY.normalize("animaton")

    def test_typo_rejected_transitions_misspelled(self) -> None:
        with self.assertRaises(ValueError):
            ELEMENT_KIND_REGISTRY.normalize("transitons")

    def test_completely_undeclared_root_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "element kind must be one of"):
            ELEMENT_KIND_REGISTRY.normalize("nonsense")

    def test_empty_string_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "element kind must be one of"):
            ELEMENT_KIND_REGISTRY.normalize("")

    def test_available_kinds_listed_in_error_message(self) -> None:
        try:
            ELEMENT_KIND_REGISTRY.normalize("zzz")
        except ValueError as exc:
            message = str(exc)
            for canonical in ELEMENT_KIND_REGISTRY.canonical_kinds():
                self.assertIn(canonical, message)

    def test_descriptor_also_rejects_undeclared_root(self) -> None:
        with self.assertRaisesRegex(ValueError, "element kind must be one of"):
            ELEMENT_KIND_REGISTRY.descriptor("typo_root")

    def test_singular_also_rejects_undeclared_root(self) -> None:
        with self.assertRaisesRegex(ValueError, "element kind must be one of"):
            ELEMENT_KIND_REGISTRY.singular("typo_root")

    def test_custom_error_cls_used_when_provided(self) -> None:
        class CustomError(Exception):
            pass

        with self.assertRaises(CustomError):
            ELEMENT_KIND_REGISTRY.normalize("bad_kind", error_cls=CustomError)


# ---------------------------------------------------------------------------
# Existing (preserved) tests from T15
# ---------------------------------------------------------------------------

class ElementKindRegistryTest(unittest.TestCase):
    def test_builtin_registry_preserves_constants_and_singular_aliases(self) -> None:
        self.assertEqual(ELEMENT_KINDS, ("effects", "animations", "transitions"))
        self.assertEqual(ELEMENT_KIND_REGISTRY.canonical_kinds(), ELEMENT_KINDS)
        self.assertEqual(
            ELEMENT_KIND_REGISTRY.accepted_names(),
            ("effects", "effect", "animations", "animation", "transitions", "transition"),
        )
        self.assertEqual(ELEMENT_KIND_REGISTRY.normalize("effects"), "effects")
        self.assertEqual(ELEMENT_KIND_REGISTRY.normalize("effect"), "effects")
        self.assertEqual(ELEMENT_KIND_REGISTRY.singular("effects"), "effect")

    def test_registry_rejects_duplicate_aliases(self) -> None:
        registry = ElementKindRegistry()

        with self.assertRaisesRegex(ValueError, "duplicate element kind alias 'effect'"):
            registry.register(
                ElementKindDescriptor(
                    id="overlay-effects",
                    singular="effect",
                    plural="overlay-effects",
                )
            )

    def test_iter_element_roots_accepts_singular_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = Path(tmp) / "demo"
            pack_root.mkdir(parents=True)
            (pack_root / "pack.yaml").write_text(
                "id: demo\nname: Demo\nversion: 0.1.0\n",
                encoding="utf-8",
            )
            element_root = pack_root / "elements" / "effects" / "glow"
            element_root.mkdir(parents=True)
            pack = load_pack_manifest(pack_manifest_path(pack_root))

            roots = iter_element_roots(pack, kind="effect")

            self.assertEqual(roots, (("effects", element_root.resolve()),))


if __name__ == "__main__":
    unittest.main()
