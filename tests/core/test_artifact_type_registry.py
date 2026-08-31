"""Comprehensive tests for the ArtifactTypeRegistry.

Covers:
- Built-in registration and alias resolution
- Duplicate id / alias rejection
- Invalid descriptor declarations (empty ids, whitespace, etc.)
- Pack-extension loading (pack_artifact_type_descriptors, artifact_type_registry_for_pack)
- Opaque fallthrough (resolve returns None for unknown)
- Pack-level validation: declared-but-unknown raises at pack-load
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from astrid.core.contracts.artifact_types import (
    ARTIFACT_TYPE_REGISTRY,
    ArtifactTypeDescriptor,
    ArtifactTypeRegistry,
    ArtifactTypeRegistryError,
)
from astrid.core.pack import (
    PackValidationError,
    artifact_type_registry_for_pack,
    load_pack_manifest,
    pack_artifact_type_descriptors,
    pack_manifest_path,
)


# ---------------------------------------------------------------------------
# Built-in registration and alias resolution
# ---------------------------------------------------------------------------


class BuiltinRegistrationTest(unittest.TestCase):
    def test_canonical_ids_count(self) -> None:
        """The builtin registry seeds 11 canonical artifact types."""
        ids = ARTIFACT_TYPE_REGISTRY.canonical_ids()
        self.assertEqual(len(ids), 11)

    def test_clip_visual_is_registered(self) -> None:
        self.assertIn("clip/visual", ARTIFACT_TYPE_REGISTRY.canonical_ids())

    def test_expected_canonical_ids(self) -> None:
        expected = (
            "clip/visual",
            "image",
            "audio",
            "mask",
            "prompt",
            "transcript",
            "timeline",
            "asset_registry",
            "lora",
            "pool",
            "arrangement",
        )
        self.assertEqual(ARTIFACT_TYPE_REGISTRY.canonical_ids(), expected)

    def test_resolve_video_clip_to_clip_visual(self) -> None:
        """``video/clip`` alias resolves to canonical ``clip/visual`` (SD1)."""
        self.assertEqual(ARTIFACT_TYPE_REGISTRY.resolve("video/clip"), "clip/visual")

    def test_resolve_visual_to_clip_visual(self) -> None:
        """``visual`` alias resolves to canonical ``clip/visual``."""
        self.assertEqual(ARTIFACT_TYPE_REGISTRY.resolve("visual"), "clip/visual")

    def test_resolve_canonical_is_identity(self) -> None:
        for canonical_id in ARTIFACT_TYPE_REGISTRY.canonical_ids():
            with self.subTest(canonical_id=canonical_id):
                self.assertEqual(ARTIFACT_TYPE_REGISTRY.resolve(canonical_id), canonical_id)

    def test_resolve_unknown_returns_none(self) -> None:
        """Unknown names return None (opaque fallthrough contract)."""
        self.assertIsNone(ARTIFACT_TYPE_REGISTRY.resolve("nonexistent"))
        self.assertIsNone(ARTIFACT_TYPE_REGISTRY.resolve("external-custom-thing"))
        self.assertIsNone(ARTIFACT_TYPE_REGISTRY.resolve(""))

    def test_is_known(self) -> None:
        self.assertTrue(ARTIFACT_TYPE_REGISTRY.is_known("clip/visual"))
        self.assertTrue(ARTIFACT_TYPE_REGISTRY.is_known("video/clip"))
        self.assertTrue(ARTIFACT_TYPE_REGISTRY.is_known("visual"))
        self.assertFalse(ARTIFACT_TYPE_REGISTRY.is_known("unknown"))

    def test_normalize_alias(self) -> None:
        self.assertEqual(ARTIFACT_TYPE_REGISTRY.normalize("video/clip"), "clip/visual")
        self.assertEqual(ARTIFACT_TYPE_REGISTRY.normalize("visual"), "clip/visual")

    def test_normalize_canonical(self) -> None:
        self.assertEqual(ARTIFACT_TYPE_REGISTRY.normalize("clip/visual"), "clip/visual")

    def test_normalize_unknown_raises(self) -> None:
        with self.assertRaises(ArtifactTypeRegistryError) as ctx:
            ARTIFACT_TYPE_REGISTRY.normalize("nonexistent")
        self.assertIn("artifact type must be one of", str(ctx.exception))

    def test_accepted_names_includes_canonical_and_aliases(self) -> None:
        names = ARTIFACT_TYPE_REGISTRY.accepted_names()
        # canonical ids
        for cid in ARTIFACT_TYPE_REGISTRY.canonical_ids():
            self.assertIn(cid, names)
        # aliases
        self.assertIn("video/clip", names)
        self.assertIn("visual", names)

    def test_accepted_names_are_deduplicated(self) -> None:
        names = ARTIFACT_TYPE_REGISTRY.accepted_names()
        self.assertEqual(len(names), len(set(names)))

    def test_descriptors_count(self) -> None:
        descs = ARTIFACT_TYPE_REGISTRY.descriptors()
        self.assertEqual(len(descs), 11)

    def test_descriptors_include_full_metadata(self) -> None:
        for desc in ARTIFACT_TYPE_REGISTRY.descriptors():
            self.assertTrue(desc.id.strip())
            self.assertIsInstance(desc.aliases, tuple)
            self.assertIsInstance(desc.description, str)


# ---------------------------------------------------------------------------
# Alias resolution edge-cases
# ---------------------------------------------------------------------------


class AliasResolutionTest(unittest.TestCase):
    def test_whitespace_name_is_stripped_in_resolve(self) -> None:
        self.assertEqual(ARTIFACT_TYPE_REGISTRY.resolve("  clip/visual  "), "clip/visual")

    def test_whitespace_only_name_returns_none(self) -> None:
        # Empty after strip → not in registry
        self.assertIsNone(ARTIFACT_TYPE_REGISTRY.resolve("   "))

    def test_custom_registry_alias_resolution(self) -> None:
        registry = ArtifactTypeRegistry()
        registry.register(
            ArtifactTypeDescriptor(id="custom/type", aliases=("ct", "c_type"))
        )
        self.assertEqual(registry.resolve("ct"), "custom/type")
        self.assertEqual(registry.resolve("c_type"), "custom/type")
        self.assertEqual(registry.resolve("custom/type"), "custom/type")

    def test_alias_that_matches_an_existing_alias_is_rejected(self) -> None:
        """An alias that collides with an existing *alias* (not canonical id)
        should be rejected — same as ElementKindRegistry alias collision."""
        registry = ArtifactTypeRegistry()
        # "video/clip" is already a registered alias for "clip/visual"
        with self.assertRaises(ArtifactTypeRegistryError):
            registry.register(
                ArtifactTypeDescriptor(id="my_type", aliases=("video/clip",))
            )


# ---------------------------------------------------------------------------
# Duplicate declarations
# ---------------------------------------------------------------------------


class DuplicateDeclarationTest(unittest.TestCase):
    def test_register_same_canonical_id_twice_raises(self) -> None:
        registry = ArtifactTypeRegistry()
        # First one works (builtins already have clip/visual, so pick a fresh id)
        with self.assertRaises(ArtifactTypeRegistryError):
            registry.register(ArtifactTypeDescriptor(id="clip/visual"))

    def test_register_fresh_duplicate_raises(self) -> None:
        registry = ArtifactTypeRegistry()
        registry.register(ArtifactTypeDescriptor(id="fresh_type"))
        with self.assertRaisesRegex(ArtifactTypeRegistryError, "duplicate artifact type 'fresh_type'"):
            registry.register(ArtifactTypeDescriptor(id="fresh_type"))

    def test_register_conflicting_alias_raises(self) -> None:
        registry = ArtifactTypeRegistry()
        with self.assertRaises(ArtifactTypeRegistryError) as ctx:
            registry.register(
                ArtifactTypeDescriptor(id="my_visual", aliases=("video/clip",))
            )
        self.assertIn("duplicate artifact type alias 'video/clip'", str(ctx.exception))

    def test_register_many_with_duplicates_raises(self) -> None:
        registry = ArtifactTypeRegistry()
        with self.assertRaises(ArtifactTypeRegistryError):
            registry.register_many(
                [
                    ArtifactTypeDescriptor(id="type_a"),
                    ArtifactTypeDescriptor(id="type_a"),
                ]
            )

    def test_register_many_is_atomic_when_later_descriptor_conflicts(self) -> None:
        """When a batch contains a conflict later, the earlier valid entries
        must not be committed."""
        registry = ArtifactTypeRegistry()
        before = registry.canonical_ids()
        with self.assertRaises(ArtifactTypeRegistryError):
            registry.register_many(
                [
                    ArtifactTypeDescriptor(id="valid_type"),
                    ArtifactTypeDescriptor(id="another_valid"),
                    ArtifactTypeDescriptor(id="clip/visual"),  # duplicate
                ]
            )
        self.assertEqual(registry.canonical_ids(), before)
        self.assertFalse(registry.is_known("valid_type"))
        self.assertFalse(registry.is_known("another_valid"))

    def test_register_many_is_atomic_when_alias_conflict_in_middle(self) -> None:
        registry = ArtifactTypeRegistry()
        before = registry.canonical_ids()
        with self.assertRaises(ArtifactTypeRegistryError):
            registry.register_many(
                [
                    ArtifactTypeDescriptor(id="valid_type"),
                    ArtifactTypeDescriptor(id="collision", aliases=("video/clip",)),
                ]
            )
        self.assertEqual(registry.canonical_ids(), before)
        self.assertFalse(registry.is_known("valid_type"))


# ---------------------------------------------------------------------------
# Invalid declarations
# ---------------------------------------------------------------------------


class InvalidDeclarationTest(unittest.TestCase):
    def test_empty_id_raises(self) -> None:
        registry = ArtifactTypeRegistry()
        with self.assertRaisesRegex(ValueError, "artifact type id must be a non-empty string"):
            registry.register(ArtifactTypeDescriptor(id=""))

    def test_whitespace_only_id_raises(self) -> None:
        registry = ArtifactTypeRegistry()
        with self.assertRaisesRegex(ValueError, "artifact type id must be a non-empty string"):
            registry.register(ArtifactTypeDescriptor(id="   "))

    def test_whitespace_only_alias_rejected(self) -> None:
        registry = ArtifactTypeRegistry()
        with self.assertRaisesRegex(ValueError, "artifact type alias must be a non-empty string"):
            registry.register(
                ArtifactTypeDescriptor(id="ok_type", aliases=("   ",))
            )

    def test_empty_alias_string_rejected(self) -> None:
        registry = ArtifactTypeRegistry()
        with self.assertRaisesRegex(ValueError, "artifact type alias must be a non-empty string"):
            registry.register(
                ArtifactTypeDescriptor(id="ok_type", aliases=("",))
            )


# ---------------------------------------------------------------------------
# Pack-declared artifact type loading
# ---------------------------------------------------------------------------


class PackDeclaredArtifactTypeLoadingTest(unittest.TestCase):
    def test_load_pack_with_artifact_types_extension(self) -> None:
        """A pack with extensions.artifact_types.types declares new artifact
        types that can be registered into a fresh ArtifactTypeRegistry."""
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
                            "artifact_types": {
                                "types": [
                                    {
                                        "id": "widget/3d",
                                        "aliases": ["3d_widget", "widget3d"],
                                        "description": "A 3D widget.",
                                    },
                                    {
                                        "id": "shader/material",
                                        "aliases": ["material"],
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
            self.assertIn("artifact_types", extensions)
            self.assertIn("types", extensions["artifact_types"])

            types = extensions["artifact_types"]["types"]
            self.assertEqual(len(types), 2)

            descriptors = pack_artifact_type_descriptors(pack)
            self.assertEqual(len(descriptors), 2)

            registry = artifact_type_registry_for_pack(pack)

            # Verify built-ins still present
            self.assertIn("clip/visual", registry.canonical_ids())
            self.assertIn("image", registry.canonical_ids())

            # Verify new types are registered
            self.assertIn("widget/3d", registry.canonical_ids())
            self.assertIn("shader/material", registry.canonical_ids())

            # Verify alias resolution
            self.assertEqual(registry.resolve("3d_widget"), "widget/3d")
            self.assertEqual(registry.resolve("widget3d"), "widget/3d")
            self.assertEqual(registry.resolve("material"), "shader/material")

    def test_pack_with_empty_artifact_types_returns_base_registry(self) -> None:
        """A pack with no artifact_types extension returns the base registry unchanged."""
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
                    }
                ),
                encoding="utf-8",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            registry = artifact_type_registry_for_pack(pack)
            # Should be the same as the global singleton (no extensions)
            self.assertEqual(
                registry.canonical_ids(),
                ARTIFACT_TYPE_REGISTRY.canonical_ids(),
            )

    def test_pack_duplicate_artifact_type_id_raises(self) -> None:
        """Declaring a duplicate artifact type id in pack extensions raises
        PackValidationError at pack-load time."""
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
                            "artifact_types": {
                                "types": [
                                    {"id": "clip/visual", "aliases": ["something"]},
                                ]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            with self.assertRaises(PackValidationError) as ctx:
                artifact_type_registry_for_pack(pack)
            self.assertIn("pack.extensions.artifact_types is invalid", str(ctx.exception))
            self.assertIn("duplicate artifact type 'clip/visual'", str(ctx.exception))

    def test_pack_unknown_extension_key_rejected_at_normalization(self) -> None:
        """An unknown key inside artifact_types raises at normalization time."""
        from astrid.core.pack.permissions import _normalize_artifact_types

        with self.assertRaises(PackValidationError) as ctx:
            _normalize_artifact_types(
                {"types": [], "bad_key": True},
                path="extensions.artifact_types",
            )
        self.assertIn("unknown field", str(ctx.exception))

    def test_pack_artifact_type_missing_id_rejected(self) -> None:
        """An artifact type entry without an 'id' field is rejected."""
        from astrid.core.pack.permissions import _normalize_artifact_type_items

        with self.assertRaises(PackValidationError):
            _normalize_artifact_type_items(
                [{"aliases": ["test"]}],
                path="extensions.artifact_types.types",
            )

    def test_pack_artifact_type_invalid_aliases_type_rejected(self) -> None:
        """Aliases must be an array, not a string."""
        from astrid.core.pack.permissions import _normalize_artifact_type_items

        with self.assertRaises(PackValidationError) as ctx:
            _normalize_artifact_type_items(
                [{"id": "test", "aliases": "not_an_array"}],
                path="extensions.artifact_types.types",
            )
        self.assertIn("aliases must be an array", str(ctx.exception))

    def test_artifact_type_registry_uses_provided_base(self) -> None:
        """artifact_type_registry_for_pack accepts a custom base_registry."""
        base = ArtifactTypeRegistry()
        base.register(ArtifactTypeDescriptor(id="base/type", aliases=("bt",)))

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
                            "artifact_types": {
                                "types": [{"id": "pack/type", "aliases": ["pt"]}]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            registry = artifact_type_registry_for_pack(pack, base_registry=base)

            self.assertIn("base/type", registry.canonical_ids())
            self.assertIn("pack/type", registry.canonical_ids())
            self.assertEqual(registry.resolve("bt"), "base/type")
            self.assertEqual(registry.resolve("pt"), "pack/type")

            # Built-ins are always seeded (mirrors ElementKindRegistry).
            self.assertIn("clip/visual", registry.canonical_ids())


# ---------------------------------------------------------------------------
# Opaque fallthrough (runtime contract)
# ---------------------------------------------------------------------------


class OpaqueFallthroughTest(unittest.TestCase):
    def test_unknown_value_resolve_returns_none(self) -> None:
        """Unknown runtime values return None — caller decides (opaque fallthrough)."""
        self.assertIsNone(ARTIFACT_TYPE_REGISTRY.resolve("external-custom-type"))
        self.assertIsNone(ARTIFACT_TYPE_REGISTRY.resolve("open-string-anything"))

    def test_unknown_value_is_known_returns_false(self) -> None:
        self.assertFalse(ARTIFACT_TYPE_REGISTRY.is_known("external-custom-type"))

    def test_normalize_on_unknown_raises(self) -> None:
        """normalize() should raise for unknown (used in strict validation paths),
        while resolve() returns None (used in opaque fallthrough paths)."""
        with self.assertRaises(ArtifactTypeRegistryError):
            ARTIFACT_TYPE_REGISTRY.normalize("unknown-type")

    def test_custom_registry_unknown_returns_none(self) -> None:
        registry = ArtifactTypeRegistry()
        registry.register(ArtifactTypeDescriptor(id="known/type"))
        self.assertIsNone(registry.resolve("unknown"))
        self.assertTrue(registry.is_known("known/type"))
        self.assertFalse(registry.is_known("unknown"))
