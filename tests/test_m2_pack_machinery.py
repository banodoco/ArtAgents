"""M2 pack-machinery characterization tests.

Captures the pre-M2 pack import surface, module identity contracts,
``astrid.packs`` shim resolution, patch seams (install, validate),
and the ``astrid/packs/`` data-tree layout so that M2 structural
changes can be verified against a known baseline.

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
# astrid.core.pack and astrid.core.pack_machinery submodule imports
# ---------------------------------------------------------------------------

class PackMachineryModulesTest(unittest.TestCase):
    """Canonical pack modules and pack_machinery shims must be importable."""

    def test_cli_importable(self) -> None:
        import astrid.core.pack.cli as canonical
        import astrid.core.pack_machinery.cli as cli

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
                self.assertIs(getattr(cli, name), getattr(canonical, name))

        self.assertTrue(callable(cli.build_parser))

    def test_validate_importable(self) -> None:
        import astrid.core.pack.validate as canonical
        import astrid.core.pack_machinery.validate as v

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
                self.assertIs(getattr(v, name), getattr(canonical, name))

    def test_agent_index_importable(self) -> None:
        import astrid.core.pack.agent_index as canonical
        import astrid.core.pack_machinery.agent_index as ai

        self.assertTrue(hasattr(ai, "build_agent_index"))
        self.assertTrue(callable(ai.build_agent_index))
        self.assertTrue(hasattr(ai, "_assemble_pack_entry"))
        self.assertIs(ai.build_agent_index, canonical.build_agent_index)
        self.assertIs(ai._assemble_pack_entry, canonical._assemble_pack_entry)

    def test_gitignore_importable(self) -> None:
        import astrid.core.pack.gitignore as canonical
        import astrid.core.pack_machinery.gitignore as gi

        self.assertTrue(hasattr(gi, "GitIgnoreFilter"))
        self.assertTrue(hasattr(gi, "gitignore_filter"))
        self.assertTrue(callable(gi.gitignore_filter))
        self.assertIs(gi.GitIgnoreFilter, canonical.GitIgnoreFilter)
        self.assertIs(gi.gitignore_filter, canonical.gitignore_filter)

    def test_install_shim_importable(self) -> None:
        """pack_machinery.install is now an alias to astrid.core.pack.install."""
        import astrid.core.pack.install as canonical
        import astrid.core.pack_machinery.install as inst

        self.assertIs(inst, canonical)

    def test_machinery_init_empty(self) -> None:
        """pack_machinery/__init__.py is deliberately empty (docs-only)."""
        import astrid.core.pack_machinery

        # It should exist but with no substantive exports
        self.assertIsNotNone(astrid.core.pack_machinery)


# ---------------------------------------------------------------------------
# astrid.packs shim resolution — each shim delegates to pack_machinery
# ---------------------------------------------------------------------------

class PacksShimResolutionTest(unittest.TestCase):
    """Each ``astrid.packs.*`` shim must delegate to its core.pack canonical (through pack_machinery)."""

    def test_cli_shim_delegates_to_machinery(self) -> None:
        import astrid.core.pack_machinery.cli as machinery
        import astrid.packs.cli as shim

        # The shim imports from ``astrid.core.pack.cli``; machinery also
        # delegates there, so key public names should be the same object.
        for name in ("build_parser", "cmd_new", "cmd_validate", "main"):
            with self.subTest(name=name):
                self.assertIs(
                    getattr(shim, name),
                    getattr(machinery, name),
                    f"astrid.packs.cli.{name} must be the same as "
                    f"astrid.core.pack_machinery.cli.{name}",
                )

    def test_validate_shim_delegates_to_machinery(self) -> None:
        import astrid.core.pack_machinery.validate as machinery
        import astrid.packs.validate as shim

        for name in (
            "PackValidator",
            "PackLayoutContractError",
            "PackLayoutException",
            "LayoutValidationIssue",
            "ValidationError",
            "V1_TRUST_BLOCK",
            "extract_trust_summary",
            "validate_pack",
            "validate_first_party_packs_root",
        ):
            with self.subTest(name=name):
                self.assertIs(
                    getattr(shim, name),
                    getattr(machinery, name),
                    f"astrid.packs.validate.{name} must be the same as "
                    f"astrid.core.pack_machinery.validate.{name}",
                )

    def test_agent_index_shim_delegates_to_machinery(self) -> None:
        import astrid.core.pack_machinery.agent_index as machinery
        import astrid.packs.agent_index as shim

        self.assertIs(
            shim.build_agent_index,
            machinery.build_agent_index,
            "astrid.packs.agent_index.build_agent_index must be the same as "
            "astrid.core.pack_machinery.agent_index.build_agent_index",
        )
        self.assertIs(
            shim._assemble_pack_entry,
            machinery._assemble_pack_entry,
            "astrid.packs.agent_index._assemble_pack_entry must be the same as "
            "astrid.core.pack_machinery.agent_index._assemble_pack_entry",
        )

    def test_gitignore_shim_delegates_to_machinery(self) -> None:
        import astrid.core.pack_machinery.gitignore as machinery
        import astrid.packs.gitignore as shim

        self.assertIs(
            shim.GitIgnoreFilter,
            machinery.GitIgnoreFilter,
            "astrid.packs.gitignore.GitIgnoreFilter must be the same as "
            "astrid.core.pack_machinery.gitignore.GitIgnoreFilter",
        )
        self.assertIs(
            shim.gitignore_filter,
            machinery.gitignore_filter,
            "astrid.packs.gitignore.gitignore_filter must be the same as "
            "astrid.core.pack_machinery.gitignore.gitignore_filter",
        )

    def test_install_shims_delegate_to_canonical_module(self) -> None:
        """Legacy install paths alias the canonical core.pack module."""
        import astrid.core.pack.install as canonical
        import astrid.core.pack_machinery.install as machinery_reexport
        import astrid.packs.install as public_shim

        self.assertIs(machinery_reexport, canonical)
        self.assertIs(public_shim, canonical)

        for name in (
            "cmd_install",
            "cmd_update",
            "cmd_uninstall",
            "cmd_rollback",
            "install_pack",
            "update_pack",
            "uninstall_pack",
            "rollback_pack",
        ):
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(canonical, name),
                    f"astrid.core.pack.install missing {name}",
                )
                self.assertIs(getattr(public_shim, name), getattr(canonical, name))
                self.assertIs(getattr(machinery_reexport, name), getattr(canonical, name))


# ---------------------------------------------------------------------------
# astrid.packs.__init__ shim exports
# ---------------------------------------------------------------------------

class PacksInitShimTest(unittest.TestCase):
    """``astrid.packs.__init__`` must re-export selected public names."""

    def test_init_all_exports(self) -> None:
        import astrid.packs

        expected = {
            "GitIgnoreFilter",
            "build_agent_index",
            "cmd_install",
            "cmd_rollback",
            "cmd_uninstall",
            "cmd_update",
            "gitignore_filter",
            "install_pack",
            "rollback_pack",
            "uninstall_pack",
            "update_pack",
        }
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(astrid.packs, name),
                    f"astrid.packs missing {name}",
                )

    def test_init_exports_are_callable_or_usable(self) -> None:
        import astrid.packs

        # install functions
        for name in (
            "cmd_install",
            "cmd_rollback",
            "cmd_uninstall",
            "cmd_update",
            "install_pack",
            "rollback_pack",
            "uninstall_pack",
            "update_pack",
        ):
            with self.subTest(name=name):
                self.assertTrue(
                    callable(getattr(astrid.packs, name)),
                    f"astrid.packs.{name} must be callable",
                )

        # build_agent_index
        self.assertTrue(callable(astrid.packs.build_agent_index))

        # GitIgnoreFilter is a class
        self.assertTrue(isinstance(astrid.packs.GitIgnoreFilter, type))

    def test_same_object_as_source_module(self) -> None:
        """Confirm the re-export is the same object, not a copy."""
        import astrid.packs
        from astrid.core.pack_machinery.agent_index import build_agent_index as ai_bi
        from astrid.core.pack_machinery.gitignore import (
            GitIgnoreFilter as gi_GIF,
            gitignore_filter as gi_gf,
        )
        from astrid.packs.install import install_pack as inst_ip

        self.assertIs(astrid.packs.build_agent_index, ai_bi)
        self.assertIs(astrid.packs.GitIgnoreFilter, gi_GIF)
        self.assertIs(astrid.packs.gitignore_filter, gi_gf)
        self.assertIs(astrid.packs.install_pack, inst_ip)


# ---------------------------------------------------------------------------
# Loose pack modules (astrid.core.pack_discovery, pack_resolver, pack_store)
# ---------------------------------------------------------------------------

class LoosePackModulesTest(unittest.TestCase):
    """The loose ``astrid.core.pack_*`` modules must be importable pre-M2."""

    def test_pack_discovery_importable(self) -> None:
        import astrid.core.pack_discovery as pd

        for name in (
            "DiscoveredPack",
            "discover_pack_metadata",
            "SOURCE_KINDS",
            "ASTRID_PACKS_PATH_ENV",
        ):
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(pd, name),
                    f"astrid.core.pack_discovery missing {name}",
                )

        self.assertTrue(callable(pd.discover_pack_metadata))

    def test_pack_resolver_importable(self) -> None:
        import astrid.core.pack_resolver as pr

        for name in (
            "PackResolverError",
            "CallableNotFoundError",
            "importlib_resolve",
            "resolve_callable_from_metadata",
        ):
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(pr, name),
                    f"astrid.core.pack_resolver missing {name}",
                )

        self.assertTrue(issubclass(pr.PackResolverError, RuntimeError))
        self.assertTrue(issubclass(pr.CallableNotFoundError, pr.PackResolverError))

    def test_pack_store_importable(self) -> None:
        import astrid.core.pack_store as ps

        for name in ("InstallRecord", "InstalledPackStore"):
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(ps, name),
                    f"astrid.core.pack_store missing {name}",
                )

    def test_loose_modules_are_not_packages(self) -> None:
        """Pre-M2, the loose pack_* modules are .py files, not packages."""
        for module_path in (
            "astrid.core.pack_discovery",
            "astrid.core.pack_resolver",
            "astrid.core.pack_store",
        ):
            with self.subTest(module=module_path):
                mod = __import__(module_path, fromlist=["__path__"])
                self.assertIsNone(
                    getattr(mod, "__path__", None),
                    f"Pre-M2: {module_path} must be a module, not a package",
                )


# ---------------------------------------------------------------------------
# Patch seams — install
# ---------------------------------------------------------------------------

class PackInstallPatchSeamsTest(unittest.TestCase):
    """``mock.patch('astrid.packs.install.*')`` targets must resolve."""

    def test_patch_install_confirm_trust_resolves(self) -> None:
        """Patching _confirm_trust through astrid.packs.install must work."""
        import astrid.packs.install

        self.assertTrue(
            hasattr(astrid.packs.install, "_confirm_trust"),
            "_confirm_trust must exist on astrid.packs.install",
        )
        self.assertTrue(callable(astrid.packs.install._confirm_trust))

        with mock.patch(
            "astrid.packs.install._confirm_trust",
            return_value=True,
        ) as patched:
            result = astrid.packs.install._confirm_trust("dummy")
            self.assertTrue(result)
            patched.assert_called_once_with("dummy")

    def test_patch_install_confirm_resolves(self) -> None:
        """Patching _confirm through astrid.packs.install must work."""
        import astrid.packs.install

        self.assertTrue(
            hasattr(astrid.packs.install, "_confirm"),
            "_confirm must exist on astrid.packs.install",
        )

        with mock.patch(
            "astrid.packs.install._confirm",
            return_value=True,
        ) as patched:
            result = astrid.packs.install._confirm("prompt")
            self.assertTrue(result)
            patched.assert_called_once_with("prompt")

    def test_patch_install_pack_resolves(self) -> None:
        """Patching install_pack through astrid.packs.install must work."""
        import astrid.packs.install

        with mock.patch(
            "astrid.packs.install.install_pack",
            return_value=0,
        ) as patched:
            result = astrid.packs.install.install_pack(Path("/tmp"))
            self.assertEqual(result, 0)
            patched.assert_called_once_with(Path("/tmp"))

    def test_patch_update_pack_resolves(self) -> None:
        """Patching update_pack through astrid.packs.install must work."""
        import astrid.packs.install

        with mock.patch(
            "astrid.packs.install.update_pack",
            return_value=0,
        ) as patched:
            result = astrid.packs.install.update_pack("test_pack")
            self.assertEqual(result, 0)
            patched.assert_called_once_with("test_pack")


# ---------------------------------------------------------------------------
# Patch seams — validate
# ---------------------------------------------------------------------------

class PackValidatePatchSeamsTest(unittest.TestCase):
    """``astrid.packs.validate.iter_*_roots`` must be patchable pre-M2."""

    def test_iter_executor_roots_through_validate_shim(self) -> None:
        """iter_executor_roots is re-exported by validate for patch compatibility."""
        import astrid.packs.validate

        self.assertTrue(
            hasattr(astrid.packs.validate, "iter_executor_roots"),
            "iter_executor_roots must be on astrid.packs.validate for "
            "backward compatibility with tests that patch through the shim",
        )

        from astrid.core.pack import iter_executor_roots as canonical

        self.assertIs(
            astrid.packs.validate.iter_executor_roots,
            canonical,
            "astrid.packs.validate.iter_executor_roots must be the same as "
            "astrid.core.pack.iter_executor_roots",
        )

    def test_iter_orchestrator_roots_through_validate_shim(self) -> None:
        import astrid.packs.validate

        self.assertTrue(hasattr(astrid.packs.validate, "iter_orchestrator_roots"))

        from astrid.core.pack import iter_orchestrator_roots as canonical

        self.assertIs(
            astrid.packs.validate.iter_orchestrator_roots,
            canonical,
        )

    def test_iter_element_roots_through_validate_shim(self) -> None:
        import astrid.packs.validate

        self.assertTrue(hasattr(astrid.packs.validate, "iter_element_roots"))

        from astrid.core.pack import iter_element_roots as canonical

        self.assertIs(
            astrid.packs.validate.iter_element_roots,
            canonical,
        )

    def test_validate_pack_patchable(self) -> None:
        """Patching validate_pack through astrid.packs.validate must work."""
        import astrid.packs.validate

        with mock.patch(
            "astrid.packs.validate.validate_pack",
            return_value=("ok", []),
        ) as patched:
            result = astrid.packs.validate.validate_pack(Path("/tmp"))
            self.assertEqual(result, ("ok", []))
            patched.assert_called_once_with(Path("/tmp"))


# ---------------------------------------------------------------------------
# astrid.packs._canonical_entrypoint shim
# ---------------------------------------------------------------------------

class CanonicalEntrypointShimTest(unittest.TestCase):
    """``astrid.packs._canonical_entrypoint`` must export guard helpers."""

    def test_guard_canonical_entrypoint_importable(self) -> None:
        from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint

        self.assertTrue(callable(guard_canonical_entrypoint))

    def test_run_pack_main_importable(self) -> None:
        from astrid.packs._canonical_entrypoint import run_pack_main

        self.assertTrue(callable(run_pack_main))

    def test_warn_if_unledgered_importable(self) -> None:
        from astrid.packs._canonical_entrypoint import warn_if_unledgered

        self.assertTrue(callable(warn_if_unledgered))

    def test_canonical_runtime_entrypoint_importable(self) -> None:
        from astrid.packs._canonical_entrypoint import canonical_runtime_entrypoint

        self.assertTrue(callable(canonical_runtime_entrypoint))

    def test_guard_canonical_entrypoint_allows_internal_invocation(self) -> None:
        """When ASTRID_INTERNAL_INVOCATION is set, the guard passes silently."""
        from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint

        with mock.patch.dict(os.environ, {"ASTRID_INTERNAL_INVOCATION": "1"}):
            # Should not raise or exit
            guard_canonical_entrypoint("test_pack")

    def test_guard_canonical_entrypoint_rejects_direct_invocation(self) -> None:
        """Without ASTRID_INTERNAL_INVOCATION, the guard should exit(2)."""
        from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint

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

    def test_implementation_shim_modules_exist(self) -> None:
        """The compatibility shim .py files must exist in astrid/packs/."""
        for name in (
            "__init__.py",
            "cli.py",
            "validate.py",
            "agent_index.py",
            "install.py",
            "gitignore.py",
            "_canonical_entrypoint.py",
        ):
            shim_path = self._PACKS_ROOT / name
            with self.subTest(shim=name):
                self.assertTrue(
                    shim_path.is_file(),
                    f"astrid/packs/{name} must exist as a compatibility shim",
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
        from astrid.core.pack_machinery.validate import KNOWN_SCHEMA_VERSIONS

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
        from astrid.core.pack_machinery.validate import (
            CANONICAL_PACK_LAYOUT_RULES,
            CanonicalLayoutRule,
        )

        self.assertIsInstance(CANONICAL_PACK_LAYOUT_RULES, tuple)
        self.assertGreater(len(CANONICAL_PACK_LAYOUT_RULES), 0)

        for rule in CANONICAL_PACK_LAYOUT_RULES:
            with self.subTest(rule=rule):
                self.assertIsInstance(rule, CanonicalLayoutRule)

    def test_v1_trust_block_available(self) -> None:
        from astrid.core.pack_machinery.validate import V1_TRUST_BLOCK

        # V1_TRUST_BLOCK is a dict mapping trust metadata keys to values.
        self.assertIsInstance(V1_TRUST_BLOCK, dict)
        # Canonical keys for the v1 trust block
        for key in ("sandbox", "runs_with_user_process_permissions", "permission_enforcement"):
            with self.subTest(trust_key=key):
                self.assertIn(key, V1_TRUST_BLOCK)


if __name__ == "__main__":
    unittest.main()
