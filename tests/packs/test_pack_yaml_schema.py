from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import jsonschema

from astrid.core.pack import (
    PackDefinition,
    PackValidationError,
    load_pack_manifest,
    pack_manifest_path,
    qualified_id_pack_id,
)


class PackYamlSchemaTest(unittest.TestCase):
    def _write_pack(self, root: Path, body: str, *, folder: str = "builtin") -> Path:
        pack_root = root / folder
        pack_root.mkdir(parents=True)
        (pack_root / "pack.yaml").write_text(body + ("\n" if not body.endswith("\n") else ""), encoding="utf-8")
        return pack_root

    def test_minimal_manifest_loads_with_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(Path(tmp), "id: builtin\n")
            manifest_path = pack_manifest_path(pack_root)
            self.assertIsNotNone(manifest_path)
            pack = load_pack_manifest(manifest_path)
            self.assertEqual(pack.id, "builtin")
            self.assertEqual(pack.name, "builtin")
            self.assertEqual(pack.version, "0.1.0")
            self.assertEqual(pack.metadata, {})
            self.assertEqual(pack.content, {})
            self.assertEqual(pack.agent, {})
            self.assertEqual(pack.status, "active")
            self.assertEqual(pack.visibility, "visible")
            self.assertEqual(pack.origin, "unknown")
            self.assertEqual(pack.install_tier, "default")
            self.assertEqual(pack.pack_type, "capability")
            self.assertEqual(pack.domain, "general")
            self.assertEqual(pack.stability, "stable")
            self.assertEqual(pack.support, "project")
            self.assertEqual(pack.permissions, ())
            self.assertEqual(pack.root, pack_root.resolve())

    def test_full_manifest_round_trips_name_version_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                "id: external\nname: External Tools\nversion: 1.2.3\nmetadata: {}\n",
                folder="external",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(pack.id, "external")
            self.assertEqual(pack.name, "External Tools")
            self.assertEqual(pack.version, "1.2.3")
            self.assertEqual(pack.metadata, {})

    def test_permissions_round_trip_with_normalized_optional_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
name: Builtin
version: 0.1.0
permissions:
  - id: project_files
    reason: Needs project artifacts.
    access: read/write project files
  - id: external_services
    reason: Calls hosted APIs.
    services:
      - OpenAI
      - Replicate
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(
                tuple(permission.to_dict() for permission in pack.permissions),
                (
                    {
                        "id": "project_files",
                        "reason": "Needs project artifacts.",
                        "access": "read/write project files",
                    },
                    {
                        "id": "external_services",
                        "reason": "Calls hosted APIs.",
                        "services": ["OpenAI", "Replicate"],
                    },
                ),
            )
            self.assertEqual(pack.to_dict()["permissions"], [permission.to_dict() for permission in pack.permissions])

    def test_permissions_reject_invalid_runtime_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
permissions:
  - id: nope
    reason: bad
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"permissions\[0\]\.id must be one of",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_round_trip_with_normalized_shorthand_and_json_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    backends:
      - id: cloud_plus
        label: Cloud Plus
        module: vendor.backend
        class: CloudBackend
        init_kwargs:
          timeout: 30
          flags:
            - fast
    features:
      - t2i
      - id: img2img
        label: Image to Image
        description: Requires image input
    modes:
      - edit
  elements:
    kinds:
      - id: overlays
        singular: overlay
        plural: overlays
        label: Overlays
        description: Overlay elements
  schemas:
    manifest:
      version: 1
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(
                pack.extensions,
                {
                    "generation": {
                        "backends": [
                            {
                                "id": "cloud_plus",
                                "label": "Cloud Plus",
                                "module": "vendor.backend",
                                "class": "CloudBackend",
                                "init_kwargs": {
                                    "timeout": 30,
                                    "flags": ["fast"],
                                },
                            }
                        ],
                        "features": [
                            {"id": "t2i"},
                            {
                                "id": "img2img",
                                "label": "Image to Image",
                                "description": "Requires image input",
                            },
                        ],
                        "modes": [{"id": "edit"}],
                    },
                    "elements": {
                        "kinds": [
                            {
                                "id": "overlays",
                                "singular": "overlay",
                                "plural": "overlays",
                                "label": "Overlays",
                                "description": "Overlay elements",
                            }
                        ]
                    },
                    "schemas": {"manifest": {"version": 1}},
                },
            )
            self.assertEqual(pack.to_dict()["extensions"], pack.extensions)

    def test_extensions_default_to_empty_and_are_omitted_from_to_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(Path(tmp), "schema_version: 1\nid: builtin\n")
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(pack.extensions, {})
            self.assertNotIn("extensions", pack.to_dict())

    def test_extensions_reject_invalid_runtime_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    backends:
      - id: cloud_plus
        module: vendor.backend
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"missing required field pack\.extensions\.generation\.backends\[0\]\.class",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    # ------------------------------------------------------------------
    # Invalid extension shapes — additional rejection cases
    # ------------------------------------------------------------------

    def test_extensions_reject_unknown_root_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  unknown_section:
    foo: bar
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions has unknown field",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_non_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions: "not_an_object"
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions must be an object",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_generation_non_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation: "not_an_object"
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.generation must be an object",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_backends_not_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    backends: "not_an_array"
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.generation\.backends must be an array",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_backend_missing_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    backends:
      - module: vendor.backend
        class: CloudBackend
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"missing required field pack\.extensions\.generation\.backends\[0\]\.id",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_backend_missing_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    backends:
      - id: cloud_plus
        class: CloudBackend
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"missing required field pack\.extensions\.generation\.backends\[0\]\.module",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_backend_unknown_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    backends:
      - id: cloud_plus
        module: vendor.backend
        class: CloudBackend
        extra_field: true
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.generation\.backends\[0\] has unknown field",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_feature_empty_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    features:
      - ""
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"must be a non-empty string",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_feature_object_missing_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    features:
      - label: "No ID"
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"missing required field pack\.extensions\.generation\.features\[0\]\.id",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_feature_object_unknown_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    features:
      - id: t2i
        extra: true
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.generation\.features\[0\] has unknown field",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_features_not_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    features: "not_an_array"
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.generation\.features must be an array",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_modes_not_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    modes: "not_an_array"
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.generation\.modes must be an array",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_element_kind_missing_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  elements:
    kinds:
      - singular: overlay
        plural: overlays
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"missing required field pack\.extensions\.elements\.kinds\[0\]\.id",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_element_kind_unknown_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  elements:
    kinds:
      - id: overlays
        extra: true
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.elements\.kinds\[0\] has unknown field",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_elements_unknown_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  elements:
    unknown_key: true
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.elements has unknown field",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_kinds_not_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  elements:
    kinds: "not_an_array"
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.elements\.kinds must be an array",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    # ------------------------------------------------------------------
    # Valid extensions — additional shapes
    # ------------------------------------------------------------------

    def test_extensions_minimal_generation_section(self) -> None:
        """A pack with only a minimal generation.backends entry."""
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    backends:
      - id: local
        module: astrid.backend
        class: LocalBackend
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(
                pack.extensions,
                {
                    "generation": {
                        "backends": [
                            {
                                "id": "local",
                                "module": "astrid.backend",
                                "class": "LocalBackend",
                            }
                        ]
                    }
                },
            )

    def test_extensions_multiple_backends(self) -> None:
        """A pack with generation extensions declaring multiple backends."""
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    backends:
      - id: backend_a
        module: mod.a
        class: BackendA
      - id: backend_b
        module: mod.b
        class: BackendB
        label: Backend B
        init_kwargs:
          threads: 4
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(len(pack.extensions["generation"]["backends"]), 2)
            self.assertEqual(
                pack.extensions["generation"]["backends"][0],
                {"id": "backend_a", "module": "mod.a", "class": "BackendA"},
            )
            self.assertEqual(
                pack.extensions["generation"]["backends"][1],
                {
                    "id": "backend_b",
                    "module": "mod.b",
                    "class": "BackendB",
                    "label": "Backend B",
                    "init_kwargs": {"threads": 4},
                },
            )

    def test_extensions_timeline_kinds_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
name: Builtin
version: 0.1.0
extensions:
  timeline:
    kinds:
      - catalog: clip
        id: still
        aliases:
          - image_still
      - catalog: track
        id: music
        default: true
      - catalog: transition
        id: dip-to-white
        aliases:
          - dip
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(
                pack.extensions["timeline"]["kinds"],
                [
                    {"catalog": "clip", "id": "still", "aliases": ["image_still"]},
                    {"catalog": "track", "id": "music", "default": True},
                    {"catalog": "transition", "id": "dip-to-white", "aliases": ["dip"]},
                ],
            )

    def test_extensions_reject_invalid_timeline_kind_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  timeline:
    kinds:
      - catalog: layer
        id: hero
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.timeline\.kinds\[0\]\.catalog must be one of",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_timeline_kind_missing_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  timeline:
    kinds:
      - catalog: clip
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"missing required field pack\.extensions\.timeline\.kinds\[0\]\.id",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_timeline_kind_empty_string_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  timeline:
    kinds:
      - catalog: clip
        id: ""
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.timeline\.kinds\[0\]\.id must be a non-empty string",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_timeline_kind_non_string_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  timeline:
    kinds:
      - catalog: clip
        id: 42
""",
            )
            with self.assertRaises(PackValidationError):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_timeline_kind_non_boolean_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  timeline:
    kinds:
      - catalog: clip
        id: still
        default: "yes"
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.timeline\.kinds\[0\]\.default must be a boolean",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_timeline_kind_non_array_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  timeline:
    kinds:
      - catalog: clip
        id: still
        aliases: "not_an_array"
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.timeline\.kinds\[0\]\.aliases must be an array",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_timeline_kind_empty_string_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  timeline:
    kinds:
      - catalog: clip
        id: still
        aliases:
          - ""
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"must be a non-empty string",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_timeline_kind_non_string_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  timeline:
    kinds:
      - catalog: clip
        id: still
        aliases:
          - 123
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"must be a non-empty string",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_timeline_kind_unknown_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  timeline:
    kinds:
      - catalog: clip
        id: still
        unknown_field: true
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"has unknown field",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_extensions_reject_timeline_kinds_non_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  timeline:
    kinds: "not_an_array"
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"pack\.extensions\.timeline\.kinds must be an array",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    # ------------------------------------------------------------------
    # JSON serialization / to_dict() round-trip
    # ------------------------------------------------------------------

    def test_extensions_to_dict_is_json_serializable(self) -> None:
        """pack.to_dict() must produce a value accepted by json.dumps."""
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    backends:
      - id: cloud_plus
        label: Cloud Plus
        module: vendor.backend
        class: CloudBackend
        init_kwargs:
          timeout: 30
          flags:
            - fast
    features:
      - t2i
      - id: img2img
        label: Image to Image
        description: Requires image input
    modes:
      - edit
  elements:
    kinds:
      - id: overlays
        singular: overlay
        plural: overlays
        label: Overlays
        description: Overlay elements
  schemas:
    manifest:
      version: 1
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            payload = pack.to_dict()
            # Smoke test: must not raise TypeError
            serialized = json.dumps(payload)
            self.assertIsInstance(serialized, str)
            # Round-trip: json.loads should recover the same structure
            restored = json.loads(serialized)
            self.assertEqual(restored["extensions"], payload["extensions"])

    def test_extensions_to_dict_round_trip_through_json(self) -> None:
        """Full JSON round-trip: pack -> to_dict -> json.dumps -> json.loads -> check."""
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    features:
      - t2i
  schemas:
    manifest:
      version: 1
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            original = pack.to_dict()
            reloaded = json.loads(json.dumps(original))
            self.assertEqual(reloaded, original)

    # ------------------------------------------------------------------
    # Proof: static validation does not import backend adapter modules
    # ------------------------------------------------------------------

    def test_extensions_backend_modules_not_imported(self) -> None:
        """Loading a manifest with backend module/class references must NOT
        import those modules. The parser treats them as inert strings."""
        with tempfile.TemporaryDirectory() as tmp:
            # Record sys.modules keys before loading
            import sys
            modules_before = set(sys.modules.keys())

            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
extensions:
  generation:
    backends:
      - id: fake_backend
        module: nonexistent.module.path
        class: FakeBackendClass
      - id: another_backend
        module: also.nonexistent.vendor
        class: AnotherClass
        init_kwargs:
          key: value
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))

            # sys.modules must NOT have gained any new entries
            modules_after = set(sys.modules.keys())
            new_modules = modules_after - modules_before
            self.assertEqual(
                new_modules,
                set(),
                f"Loading extensions backends imported modules: {new_modules}",
            )

            # The module and class fields are preserved as inert strings
            self.assertEqual(
                pack.extensions["generation"]["backends"][0]["module"],
                "nonexistent.module.path",
            )
            self.assertEqual(
                pack.extensions["generation"]["backends"][0]["class"],
                "FakeBackendClass",
            )

    def test_taxonomy_fields_round_trip_and_emit_taxonomy_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
origin: builtin
install_tier: bundled
pack_type: product_surface
domain: video
stability: beta
support: core
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            payload = pack.to_dict()
            self.assertEqual(pack.origin, "builtin")
            self.assertEqual(pack.install_tier, "bundled")
            self.assertEqual(pack.pack_type, "product_surface")
            self.assertEqual(pack.domain, "video")
            self.assertEqual(pack.stability, "beta")
            self.assertEqual(pack.support, "core")
            self.assertEqual(
                payload["taxonomy"],
                {
                    "origin": "builtin",
                    "install_tier": "bundled",
                    "pack_type": "product_surface",
                    "domain": "video",
                    "stability": "beta",
                    "support": "core",
                },
            )
            self.assertEqual(payload["origin"], "builtin")
            self.assertEqual(payload["stability"], "beta")

    def test_missing_id_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(Path(tmp), "name: builtin\n")
            with self.assertRaisesRegex(PackValidationError, "missing required field pack.id"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_pack_id_must_be_safe_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(Path(tmp), "id: 1invalid\n", folder="invalid")
            with self.assertRaisesRegex(PackValidationError, "safe pack identifier"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_pack_id_rejects_uppercase_and_hyphen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for bad_id, folder in (("Invalid", "Invalid"), ("my-pack", "my-pack")):
                with self.subTest(bad_id=bad_id):
                    pack_root = self._write_pack(Path(tmp), f"id: {bad_id}\n", folder=folder)
                    with self.assertRaisesRegex(PackValidationError, "safe pack identifier"):
                        load_pack_manifest(pack_manifest_path(pack_root))

    def test_canonical_nested_manifest_loads_content_agent_status_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
name: Builtin
version: 1.2.3
description: Canonical nested manifest.
content:
  executors: executors
  orchestrators: orchestrators
agent:
  purpose: Test purpose
status: experimental
visibility: hidden
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(pack.description, "Canonical nested manifest.")
            self.assertEqual(pack.content["executors"], "executors")
            self.assertEqual(pack.agent["purpose"], "Test purpose")
            self.assertEqual(pack.status, "experimental")
            self.assertEqual(pack.visibility, "hidden")
            self.assertEqual(pack.stability, "experimental")

    def test_deprecated_status_defaults_stability_to_deprecated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(Path(tmp), "id: builtin\nstatus: deprecated\n")
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(pack.stability, "deprecated")

    def test_pack_id_must_match_folder_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(Path(tmp), "id: external\n", folder="other")
            with self.assertRaisesRegex(PackValidationError, "must match folder name"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_metadata_must_be_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(Path(tmp), "id: builtin\nmetadata: scalar\n")
            with self.assertRaisesRegex(PackValidationError, "metadata must be an object"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_qualified_id_pack_segment_helper_accepts_qualified_ids(self) -> None:
        self.assertEqual(qualified_id_pack_id("video_editing.cut"), "video_editing")
        self.assertEqual(qualified_id_pack_id("vibecomfy.run"), "vibecomfy")

    def test_qualified_id_pack_segment_helper_rejects_bare_or_blank(self) -> None:
        with self.assertRaisesRegex(PackValidationError, "qualified"):
            qualified_id_pack_id("cut")
        with self.assertRaisesRegex(PackValidationError, "qualified"):
            qualified_id_pack_id("")
        with self.assertRaisesRegex(PackValidationError, "qualified"):
            qualified_id_pack_id("builtin.")

    def test_partial_taxonomy_fields_get_defaults_for_unspecified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                "id: builtin\norigin: community\ndomain: media\n",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(pack.origin, "community")
            self.assertEqual(pack.domain, "media")
            self.assertEqual(pack.install_tier, "default")
            self.assertEqual(pack.pack_type, "capability")
            self.assertEqual(pack.stability, "stable")
            self.assertEqual(pack.support, "project")

    def test_status_stub_defaults_to_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(Path(tmp), "id: builtin\nstatus: stub\n")
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(pack.status, "stub")
            self.assertEqual(pack.stability, "stable")

    def test_explicit_stability_overrides_status_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp), "id: builtin\nstatus: experimental\nstability: beta\n"
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(pack.status, "experimental")
            self.assertEqual(pack.stability, "beta")

    def test_to_dict_includes_all_taxonomy_top_level_and_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
origin: builtin
install_tier: core
pack_type: capability
domain: system
stability: stable
support: core
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            payload = pack.to_dict()
            for field in ("origin", "install_tier", "pack_type", "domain", "stability", "support"):
                self.assertEqual(
                    payload[field],
                    getattr(pack, field),
                    f"top-level {field} must match pack.{field}",
                )
            self.assertEqual(payload["taxonomy"]["origin"], pack.origin)
            self.assertEqual(payload["taxonomy"]["domain"], pack.domain)

    def test_taxonomy_accepts_non_standard_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                "id: builtin\norigin: vendor-x\ndomain: finance\n",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(pack.origin, "vendor-x")
            self.assertEqual(pack.domain, "finance")

    def test_taxonomy_whitespace_only_string_is_rejected(self) -> None:
        for field in ("origin", "install_tier", "pack_type", "domain", "stability", "support"):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as tmp:
                    pack_root = self._write_pack(
                        Path(tmp),
                        f"id: builtin\n{field}: " "\n",
                    )
                    with self.assertRaisesRegex(
                        PackValidationError,
                        rf"pack\.{field} must be a non-empty string",
                    ):
                        load_pack_manifest(pack_manifest_path(pack_root))

    def test_taxonomy_empty_string_defaults_to_builtin_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                'id: builtin\norigin: ""\nstability: ""\n',
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(pack.origin, "unknown")
            self.assertEqual(pack.stability, "stable")


class PackAliasSchemaTest(unittest.TestCase):
    def _write_pack(self, root: Path, body: str, *, folder: str = "builtin") -> Path:
        pack_root = root / folder
        pack_root.mkdir(parents=True)
        (pack_root / "pack.yaml").write_text(
            body + ("\n" if not body.endswith("\n") else ""), encoding="utf-8"
        )
        return pack_root

    # ------------------------------------------------------------------
    # Valid alias arrays
    # ------------------------------------------------------------------

    def test_valid_executor_alias_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.legacy_cut
    canonical_id: video_editing.cut
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(len(pack.aliases), 1)
            self.assertEqual(pack.aliases[0]["kind"], "executor")
            self.assertEqual(pack.aliases[0]["alias"], "builtin.legacy_cut")
            self.assertEqual(pack.aliases[0]["canonical_id"], "video_editing.cut")
            self.assertNotIn("deprecated", pack.aliases[0])

    def test_valid_orchestrator_alias_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: orchestrator
    alias: builtin.legacy_hype
    canonical_id: video_editing.hype
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(len(pack.aliases), 1)
            self.assertEqual(pack.aliases[0]["kind"], "orchestrator")

    def test_multiple_aliases_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.a1
    canonical_id: builtin.real1
  - kind: executor
    alias: builtin.a2
    canonical_id: builtin.real2
  - kind: orchestrator
    alias: builtin.a3
    canonical_id: builtin.real3
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(len(pack.aliases), 3)
            kinds = [a["kind"] for a in pack.aliases]
            self.assertEqual(kinds, ["executor", "executor", "orchestrator"])

    def test_aliases_not_present_defaults_to_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(Path(tmp), "id: builtin\n")
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(pack.aliases, ())

    def test_aliases_null_defaults_to_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                "schema_version: 1\nid: builtin\naliases:\n",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(pack.aliases, ())

    def test_aliases_empty_array_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                "schema_version: 1\nid: builtin\naliases: []\n",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(pack.aliases, ())

    def test_alias_with_full_deprecation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.old
    canonical_id: builtin.new
    deprecated: true
    deprecation_message: "Use builtin.new instead."
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            self.assertEqual(len(pack.aliases), 1)
            self.assertEqual(pack.aliases[0]["deprecated"], True)
            self.assertEqual(
                pack.aliases[0]["deprecation_message"], "Use builtin.new instead."
            )

    # ------------------------------------------------------------------
    # Missing/invalid fields
    # ------------------------------------------------------------------

    def test_aliases_not_array_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                "schema_version: 1\nid: builtin\naliases: not_an_array\n",
            )
            with self.assertRaisesRegex(PackValidationError, "must be an array"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_aliases_string_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                'schema_version: 1\nid: builtin\naliases: "string"\n',
            )
            with self.assertRaisesRegex(PackValidationError, "must be an array"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_entry_not_object_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                "schema_version: 1\nid: builtin\naliases:\n  - just_a_string\n",
            )
            with self.assertRaisesRegex(PackValidationError, r"pack\.aliases\[0\] must be an object"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_missing_kind_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - alias: builtin.x
    canonical_id: builtin.y
""",
            )
            with self.assertRaisesRegex(PackValidationError, r"missing required field pack.aliases\[0\].kind"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_missing_alias_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    canonical_id: builtin.y
""",
            )
            with self.assertRaisesRegex(PackValidationError, r"missing required field pack.aliases\[0\].alias"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_missing_canonical_id_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.x
""",
            )
            with self.assertRaisesRegex(
                PackValidationError,
                r"missing required field pack.aliases\[0\].canonical_id",
            ):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_empty_string_alias_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: ""
    canonical_id: builtin.y
""",
            )
            with self.assertRaisesRegex(PackValidationError, "must be a non-empty"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_empty_string_canonical_id_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.x
    canonical_id: ""
""",
            )
            with self.assertRaisesRegex(PackValidationError, "must be a non-empty"):
                load_pack_manifest(pack_manifest_path(pack_root))

    # ------------------------------------------------------------------
    # Unknown alias keys
    # ------------------------------------------------------------------

    def test_alias_unknown_key_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.x
    canonical_id: builtin.y
    extra_field: true
""",
            )
            with self.assertRaisesRegex(PackValidationError, "has unknown field"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_multiple_unknown_keys_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.x
    canonical_id: builtin.y
    foo: 1
    bar: 2
""",
            )
            with self.assertRaisesRegex(PackValidationError, "bar, foo"):
                load_pack_manifest(pack_manifest_path(pack_root))

    # ------------------------------------------------------------------
    # Invalid kind
    # ------------------------------------------------------------------

    def test_alias_invalid_kind_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: invalid_kind
    alias: builtin.x
    canonical_id: builtin.y
""",
            )
            with self.assertRaisesRegex(PackValidationError, "kind must be one of"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_kind_element_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: element
    alias: builtin.x
    canonical_id: builtin.y
""",
            )
            with self.assertRaisesRegex(PackValidationError, "kind must be one of"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_kind_numeric_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: 42
    alias: builtin.x
    canonical_id: builtin.y
""",
            )
            with self.assertRaises(PackValidationError):
                load_pack_manifest(pack_manifest_path(pack_root))

    # ------------------------------------------------------------------
    # Unqualified ids
    # ------------------------------------------------------------------

    def test_alias_unqualified_alias_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: bare_name
    canonical_id: builtin.y
""",
            )
            with self.assertRaisesRegex(PackValidationError, "must be qualified as"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_unqualified_canonical_id_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.x
    canonical_id: bare_name
""",
            )
            with self.assertRaisesRegex(PackValidationError, "must be qualified as"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_trailing_dot_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.
    canonical_id: builtin.y
""",
            )
            with self.assertRaisesRegex(PackValidationError, "must be qualified as"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_leading_dot_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: .builtin
    canonical_id: builtin.y
""",
            )
            with self.assertRaisesRegex(PackValidationError, "must be qualified as"):
                load_pack_manifest(pack_manifest_path(pack_root))

    # ------------------------------------------------------------------
    # Bad deprecation metadata types
    # ------------------------------------------------------------------

    def test_alias_deprecated_not_bool_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.x
    canonical_id: builtin.y
    deprecated: "yes"
""",
            )
            with self.assertRaisesRegex(PackValidationError, "deprecated must be a boolean"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_deprecated_integer_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.x
    canonical_id: builtin.y
    deprecated: 1
""",
            )
            with self.assertRaisesRegex(PackValidationError, "deprecated must be a boolean"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_deprecation_message_not_string_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.x
    canonical_id: builtin.y
    deprecation_message: 123
""",
            )
            with self.assertRaisesRegex(PackValidationError, "deprecation_message must be a string"):
                load_pack_manifest(pack_manifest_path(pack_root))

    def test_alias_deprecation_message_boolean_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.x
    canonical_id: builtin.y
    deprecation_message: true
""",
            )
            with self.assertRaisesRegex(PackValidationError, "deprecation_message must be a string"):
                load_pack_manifest(pack_manifest_path(pack_root))

    # ------------------------------------------------------------------
    # Serialization through PackDefinition.to_dict()
    # ------------------------------------------------------------------

    def test_aliases_serialize_in_to_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.old
    canonical_id: builtin.new
    deprecated: true
    deprecation_message: Migrated
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            payload = pack.to_dict()
            self.assertIn("aliases", payload)
            self.assertEqual(len(payload["aliases"]), 1)
            self.assertEqual(payload["aliases"][0]["kind"], "executor")
            self.assertEqual(payload["aliases"][0]["alias"], "builtin.old")
            self.assertEqual(payload["aliases"][0]["canonical_id"], "builtin.new")
            self.assertEqual(payload["aliases"][0]["deprecated"], True)
            self.assertEqual(payload["aliases"][0]["deprecation_message"], "Migrated")

    def test_aliases_not_in_to_dict_when_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(Path(tmp), "id: builtin\n")
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            payload = pack.to_dict()
            self.assertNotIn("aliases", payload)

    def test_aliases_round_trip_through_to_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.alpha
    canonical_id: builtin.beta
  - kind: orchestrator
    alias: builtin.gamma
    canonical_id: builtin.delta
    deprecated: false
""",
            )
            pack = load_pack_manifest(pack_manifest_path(pack_root))
            payload = pack.to_dict()
            self.assertEqual(len(payload["aliases"]), 2)
            # First alias (no deprecation)
            self.assertNotIn("deprecated", payload["aliases"][0])
            # Second alias (deprecated: false is present)
            self.assertIn("deprecated", payload["aliases"][1])
            self.assertEqual(payload["aliases"][1]["deprecated"], False)

    def test_aliases_preserved_through_discovery_path(self) -> None:
        """Verify _pack_definition_for_discovery preserves identical aliases."""
        with tempfile.TemporaryDirectory() as tmp:
            from astrid.core.pack.validate import PackValidator

            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
aliases:
  - kind: executor
    alias: builtin.old
    canonical_id: builtin.new
    deprecated: true
    deprecation_message: Migrated
""",
            )
            pack_direct = load_pack_manifest(pack_manifest_path(pack_root))
            validator = PackValidator(pack_root)
            validator._pack_data = validator._load_yaml(pack_root / "pack.yaml")
            pack_discovery = validator._pack_definition_for_discovery({})
            self.assertEqual(pack_direct.aliases, pack_discovery.aliases)
            self.assertEqual(
                pack_direct.to_dict()["aliases"],
                pack_discovery.to_dict()["aliases"],
            )

    def test_permissions_preserved_through_discovery_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from astrid.core.pack.validate import PackValidator

            pack_root = self._write_pack(
                Path(tmp),
                """schema_version: 1
id: builtin
permissions:
  - id: network
    reason: Talks to remote APIs.
    services:
      - github
""",
            )
            pack_direct = load_pack_manifest(pack_manifest_path(pack_root))
            validator = PackValidator(pack_root)
            validator._pack_data = validator._load_yaml(pack_root / "pack.yaml")
            pack_discovery = validator._pack_definition_for_discovery({})
            self.assertEqual(pack_direct.permissions, pack_discovery.permissions)
            self.assertEqual(
                pack_direct.to_dict()["permissions"],
                pack_discovery.to_dict()["permissions"],
            )


# ------------------------------------------------------------------
# Parity suite — JSON Schema vs runtime parser agreement
# ------------------------------------------------------------------


class PackSchemaRuntimeParityTest(unittest.TestCase):
    """Every payload is validated through JSON Schema AND `load_pack_manifest()`.

    Both paths MUST agree on accept/reject and runtime defaults.
    """

    _pack_schema: dict[str, Any] | None = None
    _pack_registry: Any | None = None

    @classmethod
    def setUpClass(cls) -> None:
        from referencing import Registry, Resource

        schemas_root = Path(__file__).resolve().parents[2] / "astrid" / "core" / "pack" / "schemas" / "v1"
        defs_path = schemas_root / "_defs.json"
        pack_path = schemas_root / "pack.json"

        registry = Registry()
        if defs_path.is_file():
            defs_schema = json.loads(defs_path.read_text(encoding="utf-8"))
            registry = registry.with_resource("_defs.json", Resource.from_contents(defs_schema))

        pack_schema = json.loads(pack_path.read_text(encoding="utf-8"))
        schema_id = pack_schema.get("$id")
        if schema_id:
            registry = registry.with_resource(schema_id, Resource.from_contents(pack_schema))

        cls._pack_schema = pack_schema
        cls._pack_registry = registry

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _json_schema_errors(yaml_body: str) -> list[str]:
        """Validate *yaml_body* against pack.json schema; return error messages."""
        import yaml as _yaml
        data = _yaml.safe_load(yaml_body)
        if not isinstance(data, dict):
            return ["root must be an object"]
        validator = jsonschema.Draft7Validator(
            PackSchemaRuntimeParityTest._pack_schema,
            registry=PackSchemaRuntimeParityTest._pack_registry,
        )
        return sorted(err.message for err in validator.iter_errors(data))

    @staticmethod
    def _runtime_error(yaml_body: str, pack_id: str) -> str | None:
        """Try to load *yaml_body* through `load_pack_manifest`; return error or None."""
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = Path(tmp) / pack_id
            pack_root.mkdir()
            (pack_root / "pack.yaml").write_text(yaml_body, encoding="utf-8")
            try:
                load_pack_manifest(pack_root / "pack.yaml")
                return None
            except PackValidationError as e:
                return str(e)

    @staticmethod
    def _runtime_pack(yaml_body: str, pack_id: str) -> PackDefinition | None:
        """Load *yaml_body* through `load_pack_manifest`; return pack or None."""
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = Path(tmp) / pack_id
            pack_root.mkdir()
            (pack_root / "pack.yaml").write_text(yaml_body, encoding="utf-8")
            try:
                return load_pack_manifest(pack_root / "pack.yaml")
            except PackValidationError:
                return None

    # -- parity: valid payloads (both paths accept) -----------------------

    def test_parity_minimal_manifest_with_name_version_both_accept(self) -> None:
        """JSON Schema requires name+version; runtime also accepts them explicitly."""
        yaml_body = "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNone(rt_error, f"Runtime rejected: {rt_error}")

    def test_parity_runtime_defaults_name_version_when_absent(self) -> None:
        """Runtime defaults name→id and version→0.1.0; JSON Schema requires them."""
        yaml_body = "schema_version: 1\nid: builtin\n"
        pack = self._runtime_pack(yaml_body, "builtin")
        self.assertIsNotNone(pack)
        assert pack is not None
        self.assertEqual(pack.name, "builtin")
        self.assertEqual(pack.version, "0.1.0")
        self.assertEqual(pack.status, "active")
        self.assertEqual(pack.visibility, "visible")
        self.assertEqual(pack.origin, "unknown")
        self.assertEqual(pack.install_tier, "default")
        self.assertEqual(pack.pack_type, "capability")
        self.assertEqual(pack.domain, "general")
        self.assertEqual(pack.stability, "stable")
        self.assertEqual(pack.support, "project")
        self.assertEqual(pack.description, "")
        self.assertEqual(pack.metadata, {})
        self.assertEqual(pack.content, {})
        self.assertEqual(pack.agent, {})
        self.assertEqual(pack.extensions, {})

    def test_parity_timeline_kind_extensions_both_accept(self) -> None:
        yaml_body = """schema_version: 1
id: builtin
name: Builtin
version: 0.1.0
extensions:
  timeline:
    kinds:
      - catalog: clip
        id: still
        aliases:
          - image_still
      - catalog: track
        id: music
        default: true
"""
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNone(rt_error, f"Runtime rejected: {rt_error}")

    def test_parity_full_manifest_both_accept(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: external\nname: Ext\nversion: 2.0.0\n"
            "description: Test pack\nstatus: experimental\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        rt_error = self._runtime_error(yaml_body, "external")
        self.assertIsNone(rt_error, f"Runtime rejected: {rt_error}")

    def test_parity_full_manifest_defaults_determined_by_status(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: external\nname: Ext\nversion: 1.0.0\n"
            "status: experimental\n"
        )
        pack = self._runtime_pack(yaml_body, "external")
        self.assertIsNotNone(pack)
        assert pack is not None
        self.assertEqual(pack.status, "experimental")
        # stability defaults from status: experimental → "experimental"
        self.assertEqual(pack.stability, "experimental")

    def test_parity_full_manifest_defaults_deprecated_status(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: external\nname: Ext\nversion: 1.0.0\n"
            "status: deprecated\n"
        )
        pack = self._runtime_pack(yaml_body, "external")
        self.assertIsNotNone(pack)
        assert pack is not None
        self.assertEqual(pack.status, "deprecated")
        self.assertEqual(pack.stability, "deprecated")

    def test_parity_extensions_valid_both_accept(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n"
            "  generation:\n    backends:\n"
            "      - id: cloud_plus\n        module: vendor.backend\n"
            "        class: CloudBackend\n    features:\n      - t2i\n"
            "    modes:\n      - edit\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNone(rt_error, f"Runtime rejected: {rt_error}")

    def test_parity_extensions_minimal_generation_both_accept(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n  generation: {}\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNone(rt_error, f"Runtime rejected: {rt_error}")

    def test_parity_extensions_full_element_kinds_both_accept(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n"
            "  elements:\n    kinds:\n"
            "      - id: overlays\n        singular: overlay\n"
            "        plural: overlays\n        label: Overlays\n"
            "        description: Overlay elements\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNone(rt_error, f"Runtime rejected: {rt_error}")

    def test_parity_taxonomy_explicit_values_both_accept(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "origin: builtin\ninstall_tier: core\npack_type: capability\n"
            "domain: media\nstability: stable\nsupport: core\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNone(rt_error, f"Runtime rejected: {rt_error}")

    def test_parity_taxonomy_explicit_values_preserved(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "origin: external\ninstall_tier: core\npack_type: capability\n"
            "domain: generation\nstability: experimental\nsupport: core\n"
        )
        pack = self._runtime_pack(yaml_body, "builtin")
        self.assertIsNotNone(pack)
        assert pack is not None
        self.assertEqual(pack.origin, "external")
        self.assertEqual(pack.install_tier, "core")
        self.assertEqual(pack.pack_type, "capability")
        self.assertEqual(pack.domain, "generation")
        self.assertEqual(pack.stability, "experimental")
        self.assertEqual(pack.support, "core")

    def test_parity_taxonomy_non_standard_values_both_accept(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "origin: vendor-x\ninstall_tier: optional-plus\npack_type: adapter\n"
            "domain: finance\nstability: beta\nsupport: community\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        pack = self._runtime_pack(yaml_body, "builtin")
        self.assertIsNotNone(pack)
        assert pack is not None
        self.assertEqual(pack.origin, "vendor-x")
        self.assertEqual(pack.install_tier, "optional-plus")
        self.assertEqual(pack.pack_type, "adapter")
        self.assertEqual(pack.domain, "finance")
        self.assertEqual(pack.stability, "beta")
        self.assertEqual(pack.support, "community")

    def test_parity_taxonomy_whitespace_only_string_both_reject(self) -> None:
        for field in ("origin", "install_tier", "pack_type", "domain", "stability", "support"):
            with self.subTest(field=field):
                yaml_body = (
                    "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
                    f'{field}: " "\n'
                )
                js_errors = self._json_schema_errors(yaml_body)
                self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
                rt_error = self._runtime_error(yaml_body, "builtin")
                self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_taxonomy_empty_string_uses_defaults(self) -> None:
        yaml_body = (
            'schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n'
            'origin: ""\nstability: ""\n'
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        pack = self._runtime_pack(yaml_body, "builtin")
        self.assertIsNotNone(pack)
        assert pack is not None
        self.assertEqual(pack.origin, "unknown")
        self.assertEqual(pack.stability, "stable")

    def test_parity_permissions_valid_both_accept(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "permissions:\n"
            "  - id: project_files\n"
            "    reason: Reads and writes project assets.\n"
            "    access: read/write project files\n"
            "  - id: external_services\n"
            "    reason: Calls remote APIs.\n"
            "    services:\n"
            "      - openai\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        pack = self._runtime_pack(yaml_body, "builtin")
        self.assertIsNotNone(pack)
        assert pack is not None
        self.assertEqual(
            pack.to_dict()["permissions"],
            [
                {
                    "id": "project_files",
                    "reason": "Reads and writes project assets.",
                    "access": "read/write project files",
                },
                {
                    "id": "external_services",
                    "reason": "Calls remote APIs.",
                    "services": ["openai"],
                },
            ],
        )

    # -- parity: invalid payloads — both MUST reject -----------------------

    def test_parity_missing_id_both_reject(self) -> None:
        yaml_body = "schema_version: 1\nname: builtin\nversion: 0.1.0\n"
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_non_object_extensions_both_reject(self) -> None:
        yaml_body = (
            'schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n'
            'extensions: "not_an_object"\n'
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_permissions_invalid_shapes_both_reject(self) -> None:
        cases = (
            (
                "permissions:\n  - id: nope\n    reason: bad\n",
                r"permissions\[0\]\.id",
            ),
            (
                "permissions:\n  - id: network\n",
                r"permissions\[0\].*reason",
            ),
            (
                'permissions:\n  - id: network\n    reason: " "\n',
                r"permissions\[0\]\.reason",
            ),
            (
                "permissions:\n  - id: network\n    reason: ok\n    services: not-an-array\n",
                r"permissions\[0\]\.services",
            ),
            (
                "permissions:\n  - id: network\n    reason: ok\n    services:\n      - ""\n",
                r"permissions\[0\]\.services",
            ),
            (
                "permissions:\n  - id: network\n    reason: ok\n    unknown: true\n",
                r"Additional properties are not allowed|has unknown field",
            ),
        )
        for body, error_pattern in cases:
            with self.subTest(body=body):
                yaml_body = (
                    "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
                    f"{body}"
                )
                js_errors = self._json_schema_errors(yaml_body)
                self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
                rt_error = self._runtime_error(yaml_body, "builtin")
                self.assertIsNotNone(rt_error, "Runtime should have rejected")
                assert rt_error is not None
                self.assertRegex(rt_error, error_pattern)

    def test_parity_unknown_extension_root_key_both_reject(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n  unknown_section:\n    foo: bar\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_backend_missing_required_both_reject(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n  generation:\n    backends:\n"
            "      - id: cloud_plus\n        module: vendor.backend\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_backend_unknown_field_both_reject(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n  generation:\n    backends:\n"
            "      - id: cloud_plus\n        module: vendor.backend\n"
            "        class: CloudBackend\n        unknown: true\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_element_kind_missing_id_both_reject(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n  elements:\n    kinds:\n"
            "      - singular: overlay\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_element_kind_unknown_field_both_reject(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n  elements:\n    kinds:\n"
            "      - id: overlays\n        unknown: true\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_non_array_kinds_both_reject(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n  elements:\n    kinds: not_an_array\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_non_array_backends_both_reject(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n  generation:\n    backends: not_an_array\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_non_object_generation_both_reject(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            'extensions:\n  generation: "not_an_object"\n'
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_non_object_elements_both_reject(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            'extensions:\n  elements: "not_an_object"\n'
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_wrong_type_for_status_both_reject(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "status: 123\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    def test_parity_wrong_type_for_status_both_reject(self) -> None:
        yaml_body = "schema_version: 1\nid: builtin\nstatus: 123\n"
        js_errors = self._json_schema_errors(yaml_body)
        self.assertNotEqual(js_errors, [], "JSON Schema should have rejected")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNotNone(rt_error, "Runtime should have rejected")

    # -- parity: valid features/modes shorthand ----------------------------

    def test_parity_features_string_shorthand_both_accept(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n  generation:\n    features:\n      - t2i\n      - i2i\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNone(rt_error, f"Runtime rejected: {rt_error}")

    def test_parity_features_object_form_both_accept(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n  generation:\n    features:\n"
            "      - id: t2i\n        label: Text to Image\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNone(rt_error, f"Runtime rejected: {rt_error}")

    def test_parity_modes_string_shorthand_both_accept(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n  generation:\n    modes:\n      - edit\n"
        )
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema rejected: {js_errors}")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNone(rt_error, f"Runtime rejected: {rt_error}")

    # -- parity: extensions round-trip defaults ----------------------------

    def test_parity_extensions_round_trip_normalized_shape(self) -> None:
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n"
            "  generation:\n    backends:\n"
            "      - id: cloud_plus\n        module: vendor.backend\n"
            "        class: CloudBackend\n        init_kwargs:\n"
            "          timeout: 30\n"
            "    features:\n      - t2i\n"
            "      - id: img2img\n        label: Image to Image\n"
            "        description: Requires image input\n"
            "    modes:\n      - edit\n"
        )
        pack = self._runtime_pack(yaml_body, "builtin")
        self.assertIsNotNone(pack)
        assert pack is not None
        self.assertEqual(
            pack.extensions,
            {
                "generation": {
                    "backends": [
                        {
                            "id": "cloud_plus",
                            "module": "vendor.backend",
                            "class": "CloudBackend",
                            "init_kwargs": {"timeout": 30},
                        }
                    ],
                    "features": [
                        {"id": "t2i"},
                        {
                            "id": "img2img",
                            "label": "Image to Image",
                            "description": "Requires image input",
                        },
                    ],
                    "modes": [{"id": "edit"}],
                }
            },
        )

    # -- parity: JSON serialization agreement --------------------------------

    def test_parity_to_dict_is_json_serializable(self) -> None:
        yaml_body = "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
        pack = self._runtime_pack(yaml_body, "builtin")
        self.assertIsNotNone(pack)
        assert pack is not None
        payload = pack.to_dict()
        json_str = json.dumps(payload)
        self.assertIsInstance(json_str, str)
        round_tripped = json.loads(json_str)
        self.assertEqual(round_tripped["id"], "builtin")

    # -- parity: no import during static validation --------------------------

    def test_parity_no_import_during_static_validation(self) -> None:
        """Prove static validation does not import backend adapter modules."""
        yaml_body = (
            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
            "extensions:\n"
            "  generation:\n    backends:\n"
            "      - id: cloud_plus\n        module: nonexistent.module\n"
            "        class: FakeBackend\n"
        )
        before = set(sys.modules.keys())
        js_errors = self._json_schema_errors(yaml_body)
        self.assertEqual(js_errors, [], f"JSON Schema should accept: {js_errors}")
        rt_error = self._runtime_error(yaml_body, "builtin")
        self.assertIsNone(rt_error, f"Runtime should accept: {rt_error}")
        after = set(sys.modules.keys())
        new_modules = after - before
        # loading yaml may add modules, but the fake module should never appear
        self.assertNotIn("nonexistent.module", new_modules)
        self.assertNotIn("nonexistent", new_modules)


if __name__ == "__main__":
    unittest.main()
