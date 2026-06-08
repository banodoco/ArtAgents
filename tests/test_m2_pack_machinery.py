"""M2 pack-machinery characterization tests.

Captures the canonical pack import surface, module contracts,
patch seams (install), and the ``astrid/packs/`` data-tree layout
so that structural changes can be verified against a known baseline.

These are characterization tests — they test current behavior without
changing it.  No assertion here should be a "fix."
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# astrid.core.pack exported public surface
# ---------------------------------------------------------------------------

class PackCoreExportsTest(unittest.TestCase):
    """All 17 ``__all__`` names from ``astrid.core.pack`` must be importable."""

    _ALL_NAMES = (
        "ElementKindDescriptor",
        "ElementKindRegistry",
        "ELEMENT_KIND_REGISTRY",
        "PackDefinition",
        "PackValidationError",
        "discover_packs",
        "element_kind_registry_for_pack",
        "ensure_local_pack",
        "iter_element_roots",
        "iter_executor_roots",
        "iter_orchestrator_roots",
        "load_pack_manifest",
        "pack_taxonomy_from_manifest",
        "pack_manifest_path",
        "packs_root",
        "qualified_id_pack_id",
        "validate_content_id_in_pack",
        "validate_element_pack_id",
    )

    # Note: __all__ lists 17 names but validate_element_pack_id is the 17th
    # and it appears on 2 lines in __all__.  We test the superset here.

    def test_all_names_importable_from_pack_module(self) -> None:
        """Every __all__ name resolves from ``from astrid.core.pack import ...``."""
        import astrid.core.pack as p

        for name in self._ALL_NAMES:
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(p, name),
                    f"astrid.core.pack missing __all__ member: {name}",
                )

    def test_dot_imports_resolve(self) -> None:
        """Key names can be imported via ``from astrid.core.pack import X``."""
        from astrid.core.pack import (
            ELEMENT_KIND_REGISTRY,
            ElementKindDescriptor,
            ElementKindRegistry,
            PackDefinition,
            PackValidationError,
            discover_packs,
            element_kind_registry_for_pack,
            ensure_local_pack,
            iter_element_roots,
            iter_executor_roots,
            iter_orchestrator_roots,
            load_pack_manifest,
            pack_manifest_path,
            pack_taxonomy_from_manifest,
            packs_root,
            qualified_id_pack_id,
            validate_content_id_in_pack,
            validate_element_pack_id,
        )

        self.assertIsNotNone(PackDefinition)
        self.assertIsNotNone(PackValidationError)
        self.assertIsNotNone(ELEMENT_KIND_REGISTRY)
        self.assertTrue(callable(discover_packs))

    def test_pack_model_types_are_classes(self) -> None:
        from astrid.core.pack import (
            ElementKindDescriptor,
            ElementKindRegistry,
            PackDefinition,
            PackValidationError,
        )

        self.assertTrue(issubclass(PackValidationError, ValueError))
        self.assertTrue(issubclass(PackValidationError, Exception))

        # PackDefinition is a frozen dataclass; verify it has expected
        # dataclass fields (__dataclass_fields__).
        self.assertTrue(
            hasattr(PackDefinition, "__dataclass_fields__"),
            "PackDefinition must be a dataclass",
        )
        fields = PackDefinition.__dataclass_fields__
        for field_name in ("id", "name", "version", "root", "manifest_path"):
            with self.subTest(field=field_name):
                self.assertIn(
                    field_name,
                    fields,
                    f"PackDefinition missing dataclass field {field_name}",
                )

        # ElementKindRegistry is instantiable
        registry = ElementKindRegistry()
        self.assertIsNotNone(registry)

    def test_manifest_name_constants_available(self) -> None:
        """Manifest-name tuples are public by convention even if not in __all__."""
        import astrid.core.pack as p

        for name in (
            "PACK_MANIFEST_NAMES",
            "EXECUTOR_MANIFEST_NAMES",
            "ORCHESTRATOR_MANIFEST_NAMES",
        ):
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(p, name),
                    f"astrid.core.pack missing manifest-name constant: {name}",
                )

    def test_kind_constants_available(self) -> None:
        import astrid.core.pack as p

        for name in (
            "ELEMENT_KINDS",
            "TIMELINE_KIND_CATALOGS",
            "PACK_ALIAS_KINDS",
            "PACK_PERMISSION_IDS",
            "DEFAULT_PACKS_ROOT",
        ):
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(p, name),
                    f"astrid.core.pack missing kind constant: {name}",
                )

    def test_pack_module_is_a_package(self) -> None:
        """M2 converts astrid.core.pack into a package namespace."""
        import astrid.core.pack

        self.assertIsNotNone(
            getattr(astrid.core.pack, "__path__", None),
            "M2: astrid.core.pack should expose a package path for future submodules",
        )


# ---------------------------------------------------------------------------
# astrid.core.pack submodule imports (canonical paths)
# ---------------------------------------------------------------------------

class PackSubmoduleImportsTest(unittest.TestCase):
    """Canonical pack submodules must be importable."""

    def test_cli_importable(self) -> None:
        import astrid.core.pack.cli as cli

        for name in (
            "build_parser",
            "cmd_inspect",
            "cmd_list",
            "cmd_new",
            "cmd_validate",
            "main",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(cli, name), f"cli missing {name}")

        self.assertTrue(callable(cli.build_parser))

    def test_validate_importable(self) -> None:
        import astrid.core.pack.validate as v

        for name in (
            "PackValidator",
            "PackLayoutContractError",
            "PackLayoutException",
            "LayoutValidationIssue",
            "ValidationError",
            "LayoutExceptionClass",
            "LayoutExceptionLifecycle",
            "CanonicalLayoutRule",
            "CANONICAL_PACK_LAYOUT_RULES",
            "KNOWN_SCHEMA_VERSIONS",
            "KNOWN_VERSIONS_STR",
            "V1_TRUST_BLOCK",
            "extract_trust_summary",
            "is_first_party_packs_root_candidate",
            "validate_first_party_packs_root",
            "validate_pack",
            "json_loads",
            "iter_executor_roots",
            "iter_orchestrator_roots",
            "iter_element_roots",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(v, name), f"validate missing {name}")

    def test_agent_index_importable(self) -> None:
        import astrid.core.pack.agent_index as ai

        self.assertTrue(hasattr(ai, "build_agent_index"))
        self.assertTrue(callable(ai.build_agent_index))
        self.assertTrue(hasattr(ai, "_assemble_pack_entry"))

    def test_gitignore_importable(self) -> None:
        import astrid.core.pack.gitignore as gi

        self.assertTrue(hasattr(gi, "GitIgnoreFilter"))
        self.assertTrue(hasattr(gi, "gitignore_filter"))
        self.assertTrue(callable(gi.gitignore_filter))

    def test_install_importable(self) -> None:
        """astrid.core.pack.install is the canonical install module."""
        import astrid.core.pack.install as inst

        self.assertIsNotNone(inst)

    def test_pack_module_is_a_package(self) -> None:
        """astrid.core.pack is a package namespace."""
        import astrid.core.pack

        self.assertIsNotNone(
            getattr(astrid.core.pack, "__path__", None),
            "astrid.core.pack should expose a package path for submodules",
        )


# ---------------------------------------------------------------------------
# astrid.core.pack sub-submodules (discovery, resolver, store)
# ---------------------------------------------------------------------------

class PackSubSubmodulesTest(unittest.TestCase):
    """Canonical ``astrid.core.pack.*`` sub-submodules must be importable."""

    def test_pack_discovery_importable(self) -> None:
        import astrid.core.pack.discovery as pd

        for name in (
            "DiscoveredPack",
            "discover_pack_metadata",
            "SOURCE_KINDS",
            "ASTRID_PACKS_PATH_ENV",
        ):
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(pd, name),
                    f"astrid.core.pack.discovery missing {name}",
                )

        self.assertTrue(callable(pd.discover_pack_metadata))

    def test_pack_resolver_importable(self) -> None:
        import astrid.core.pack.resolver as pr

        for name in (
            "PackResolverError",
            "CallableNotFoundError",
            "importlib_resolve",
            "resolve_callable_from_metadata",
        ):
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(pr, name),
                    f"astrid.core.pack.resolver missing {name}",
                )

        self.assertTrue(issubclass(pr.PackResolverError, RuntimeError))
        self.assertTrue(issubclass(pr.CallableNotFoundError, pr.PackResolverError))

    def test_pack_store_importable(self) -> None:
        import astrid.core.pack.store as ps

        for name in ("InstallRecord", "InstalledPackStore"):
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(ps, name),
                    f"astrid.core.pack.store missing {name}",
                )

    def test_submodules_importable_as_modules(self) -> None:
        """discovery, resolver, store are importable under astrid.core.pack."""
        for module_path in (
            "astrid.core.pack.discovery",
            "astrid.core.pack.resolver",
            "astrid.core.pack.store",
        ):
            with self.subTest(module=module_path):
                mod = __import__(module_path, fromlist=["__path__"])
                self.assertIsNotNone(mod)


# ---------------------------------------------------------------------------
# Patch seams — install (canonical)
# ---------------------------------------------------------------------------

class PackInstallPatchSeamsTest(unittest.TestCase):
    """``mock.patch('astrid.core.pack.install.*')`` targets must resolve."""

    def test_patch_install_confirm_trust_resolves(self) -> None:
        """Patching _confirm_trust through astrid.core.pack.install must work."""
        import astrid.core.pack.install

        self.assertTrue(
            hasattr(astrid.core.pack.install, "_confirm_trust"),
            "_confirm_trust must exist on astrid.core.pack.install",
        )
        self.assertTrue(callable(astrid.core.pack.install._confirm_trust))

        with mock.patch(
            "astrid.core.pack.install._confirm_trust",
            return_value=True,
        ) as patched:
            result = astrid.core.pack.install._confirm_trust("dummy")
            self.assertTrue(result)
            patched.assert_called_once_with("dummy")

    def test_patch_install_confirm_resolves(self) -> None:
        """Patching _confirm through astrid.core.pack.install must work."""
        import astrid.core.pack.install

        self.assertTrue(
            hasattr(astrid.core.pack.install, "_confirm"),
            "_confirm must exist on astrid.core.pack.install",
        )

        with mock.patch(
            "astrid.core.pack.install._confirm",
            return_value=True,
        ) as patched:
            result = astrid.core.pack.install._confirm("prompt")
            self.assertTrue(result)
            patched.assert_called_once_with("prompt")

    def test_patch_install_pack_resolves(self) -> None:
        """Patching install_pack through astrid.core.pack.install must work."""
        import astrid.core.pack.install

        with mock.patch(
            "astrid.core.pack.install.install_pack",
            return_value=0,
        ) as patched:
            result = astrid.core.pack.install.install_pack(Path("/tmp"))
            self.assertEqual(result, 0)
            patched.assert_called_once_with(Path("/tmp"))

    def test_patch_update_pack_resolves(self) -> None:
        """Patching update_pack through astrid.core.pack.install must work."""
        import astrid.core.pack.install

        with mock.patch(
            "astrid.core.pack.install.update_pack",
            return_value=0,
        ) as patched:
            result = astrid.core.pack.install.update_pack("test_pack")
            self.assertEqual(result, 0)
            patched.assert_called_once_with("test_pack")


# ---------------------------------------------------------------------------
# astrid.core.pack.entrypoint shim
# ---------------------------------------------------------------------------

class CanonicalEntrypointShimTest(unittest.TestCase):
    """``astrid.core.pack.entrypoint`` must export guard helpers."""

    def test_guard_canonical_entrypoint_importable(self) -> None:
        from astrid.core.pack.entrypoint import guard_canonical_entrypoint

        self.assertTrue(callable(guard_canonical_entrypoint))

    def test_run_pack_main_importable(self) -> None:
        from astrid.core.pack.entrypoint import run_pack_main

        self.assertTrue(callable(run_pack_main))

    def test_warn_if_unledgered_importable(self) -> None:
        from astrid.core.pack.entrypoint import warn_if_unledgered

        self.assertTrue(callable(warn_if_unledgered))

    def test_canonical_runtime_entrypoint_importable(self) -> None:
        from astrid.core.pack.entrypoint import canonical_runtime_entrypoint

        self.assertTrue(callable(canonical_runtime_entrypoint))

    def test_guard_canonical_entrypoint_allows_internal_invocation(self) -> None:
        """When ASTRID_INTERNAL_INVOCATION is set, the guard passes silently."""
        from astrid.core.pack.entrypoint import guard_canonical_entrypoint

        with mock.patch.dict(os.environ, {"ASTRID_INTERNAL_INVOCATION": "1"}):
            # Should not raise or exit
            guard_canonical_entrypoint("test_pack")

    def test_guard_canonical_entrypoint_rejects_direct_invocation(self) -> None:
        """Without ASTRID_INTERNAL_INVOCATION, the guard should exit(2)."""
        from astrid.core.pack.entrypoint import guard_canonical_entrypoint

        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                guard_canonical_entrypoint("test_pack")
            self.assertEqual(ctx.exception.code, 2)


# ---------------------------------------------------------------------------
# astrid/packs/ data-tree layout
# ---------------------------------------------------------------------------

class PacksDataTreeTest(unittest.TestCase):
    """``astrid/packs/`` must contain pack data directories with pack.yaml manifests.

    This fails if the tree contains only implementation shims but no data.
    """

    _PACKS_ROOT = Path(__file__).resolve().parents[1] / "astrid" / "packs"

    def test_packs_root_exists(self) -> None:
        self.assertTrue(self._PACKS_ROOT.is_dir(), "astrid/packs/ must be a directory")

    def test_known_pack_dirs_exist(self) -> None:
        """Several well-known shipped pack directories must exist."""
        for pack_id in (
            "stream_content",
            "comfy_wrap",
            "text_analysis",
            "_core",
            "builtin",
        ):
            pack_dir = self._PACKS_ROOT / pack_id
            with self.subTest(pack_id=pack_id):
                self.assertTrue(
                    pack_dir.is_dir(),
                    f"astrid/packs/{pack_id} must exist as a pack data directory",
                )

    def test_pack_manifests_exist_in_shipped_packs(self) -> None:
        """Shipped pack directories must each contain a pack manifest."""
        for pack_id in ("stream_content", "comfy_wrap", "text_analysis"):
            pack_dir = self._PACKS_ROOT / pack_id
            if not pack_dir.is_dir():
                continue
            manifests = [
                f
                for f in ("pack.yaml", "pack.yml", "pack.json")
                if (pack_dir / f).is_file()
            ]
            self.assertGreater(
                len(manifests),
                0,
                f"astrid/packs/{pack_id} must contain a pack manifest",
            )

    def test_shell_packs_exist(self) -> None:
        """_core and builtin are top-level visible shell/compatibility packs."""
        for pack_id in ("_core", "builtin"):
            pack_dir = self._PACKS_ROOT / pack_id
            with self.subTest(pack_id=pack_id):
                self.assertTrue(
                    pack_dir.is_dir(),
                    f"astrid/packs/{pack_id} shell pack must exist as a directory",
                )


# ---------------------------------------------------------------------------
# Schema access (validate module)
# ---------------------------------------------------------------------------

class PackSchemasAccessTest(unittest.TestCase):
    """Validate module must expose KNOWN_SCHEMA_VERSIONS and schema constants."""

    def test_known_schema_versions_available(self) -> None:
        from astrid.core.pack.validate import KNOWN_SCHEMA_VERSIONS

        # KNOWN_SCHEMA_VERSIONS maps version int → dict of schema name → Path.
        # We characterise the container type and key presence here.
        self.assertIsInstance(KNOWN_SCHEMA_VERSIONS, dict)
        self.assertIn(1, KNOWN_SCHEMA_VERSIONS)
        v1_schemas = KNOWN_SCHEMA_VERSIONS[1]
        self.assertIsInstance(v1_schemas, dict)
        # Canonical schema keys for v1
        for key in ("pack", "executor", "orchestrator", "element"):
            with self.subTest(schema=key):
                self.assertIn(key, v1_schemas)

    def test_canonical_layout_rules_exist(self) -> None:
        from astrid.core.pack.validate import (
            CANONICAL_PACK_LAYOUT_RULES,
            CanonicalLayoutRule,
        )

        self.assertIsInstance(CANONICAL_PACK_LAYOUT_RULES, tuple)
        self.assertGreater(len(CANONICAL_PACK_LAYOUT_RULES), 0)

        for rule in CANONICAL_PACK_LAYOUT_RULES:
            with self.subTest(rule=rule):
                self.assertIsInstance(rule, CanonicalLayoutRule)

    def test_v1_trust_block_available(self) -> None:
        from astrid.core.pack.validate import V1_TRUST_BLOCK

        # V1_TRUST_BLOCK is a dict mapping trust metadata keys to values.
        self.assertIsInstance(V1_TRUST_BLOCK, dict)
        # Canonical keys for the v1 trust block
        for key in ("sandbox", "runs_with_user_process_permissions", "permission_enforcement"):
            with self.subTest(trust_key=key):
                self.assertIn(key, V1_TRUST_BLOCK)


if __name__ == "__main__":
    unittest.main()
