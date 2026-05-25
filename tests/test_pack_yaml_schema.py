from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from astrid.core.pack import (
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
            with self.assertRaisesRegex(PackValidationError, "missing required field pack.aliases\\[0\\].kind"):
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
            with self.assertRaisesRegex(PackValidationError, "missing required field pack.aliases\\[0\\].alias"):
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
            with self.assertRaisesRegex(PackValidationError, "missing required field pack.aliases\\[0\\].canonical_id"):
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
            from astrid.packs.validate import PackValidator

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


if __name__ == "__main__":
    unittest.main()
