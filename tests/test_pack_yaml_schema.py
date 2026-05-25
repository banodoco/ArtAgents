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
        self.assertEqual(qualified_id_pack_id("builtin.cut"), "builtin")
        self.assertEqual(qualified_id_pack_id("external.vibecomfy.run"), "external")

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


if __name__ == "__main__":
    unittest.main()
