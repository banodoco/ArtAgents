"""M2 public-surface characterization tests.

Captures the pre-M2 import surface, module identity contracts, deprecated
CLI alias routing, pipeline patch seams, and Banodoco integration imports
so that M2 structural changes can be verified against a known baseline.

These are characterization tests — they test current behavior without
changing it.  No assertion here should be a "fix."
"""

from __future__ import annotations

import sys
import unittest
from unittest import mock

# ---------------------------------------------------------------------------
# Root module imports — every top-level facade must be importable
# ---------------------------------------------------------------------------

class RootModuleImportTest(unittest.TestCase):
    """Root `astrid.*` modules and packages must be importable."""

    def test_gateway_importable(self) -> None:
        import astrid.gateway
        self.assertIsNotNone(astrid.gateway)

    def test_pipeline_importable(self) -> None:
        import astrid.pipeline
        self.assertIsNotNone(astrid.pipeline)

    def test_sdk_importable(self) -> None:
        import astrid.sdk
        self.assertIsNotNone(astrid.sdk)

    def test_paths_importable(self) -> None:
        import astrid.paths
        self.assertIsNotNone(astrid.paths)

    def test_underscore_paths_importable(self) -> None:
        import astrid._paths
        self.assertIsNotNone(astrid._paths)

    def test_media_importable(self) -> None:
        import astrid.media
        self.assertIsNotNone(astrid.media)

    def test_underscore_media_importable(self) -> None:
        import astrid._media
        self.assertIsNotNone(astrid._media)

    def test_theme_schema_importable(self) -> None:
        import astrid.theme_schema
        self.assertIsNotNone(astrid.theme_schema)

    def test_structure_importable(self) -> None:
        import astrid.structure
        self.assertIsNotNone(astrid.structure)

    def test_threads_importable(self) -> None:
        import astrid.threads
        self.assertIsNotNone(astrid.threads)

    def test_timeline_importable(self) -> None:
        import astrid.timeline
        self.assertIsNotNone(astrid.timeline)

    def test_main_importable(self) -> None:
        """__main__ is the package entry point that delegates to gateway."""
        import astrid.__main__
        self.assertIsNotNone(astrid.__main__)


# ---------------------------------------------------------------------------
# Module identity — astrid.pipeline *is* astrid.gateway
# ---------------------------------------------------------------------------

class PipelineGatewayIdentityTest(unittest.TestCase):
    """`astrid.pipeline` must alias `astrid.gateway` by module identity."""

    def test_pipeline_is_gateway_by_identity(self) -> None:
        import astrid.gateway
        import astrid.pipeline

        self.assertIs(astrid.pipeline, astrid.gateway,
                      "astrid.pipeline must be the same module object as astrid.gateway")

    def test_pipeline_in_sys_modules_is_gateway(self) -> None:
        """Verify sys.modules entry points to the gateway."""
        self.assertIs(
            sys.modules.get("astrid.pipeline"),
            sys.modules.get("astrid.gateway"),
            "sys.modules['astrid.pipeline'] must equal sys.modules['astrid.gateway']",
        )

    def test_import_pipeline_gives_gateway(self) -> None:
        """`from astrid import pipeline` should yield the gateway module."""
        from astrid import gateway, pipeline
        self.assertIs(pipeline, gateway)


# ---------------------------------------------------------------------------
# Pipeline patch seams — mock.patch targets must resolve through pipeline
# ---------------------------------------------------------------------------

class PipelinePatchSeamTest(unittest.TestCase):
    """mock.patch('astrid.pipeline.*') targets must work because
    astrid.pipeline is astrid.gateway and _run_default_brief_orchestrator
    lives on gateway."""

    def test_patch_pipeline_run_default_brief_orchestrator(self) -> None:
        """Patching via the pipeline alias must intercept the gateway function."""
        import astrid.gateway

        # Verify the function actually exists on gateway (it's defined there)
        self.assertTrue(
            hasattr(astrid.gateway, "_run_default_brief_orchestrator"),
            "_run_default_brief_orchestrator must be an attribute of astrid.gateway",
        )
        self.assertTrue(callable(astrid.gateway._run_default_brief_orchestrator))

        # Patch through the pipeline alias — it must work transparently
        with mock.patch(
            "astrid.pipeline._run_default_brief_orchestrator",
            return_value=42,
        ) as patched:
            from astrid import pipeline
            result = pipeline._run_default_brief_orchestrator(["dummy"])
            self.assertEqual(result, 42)
            patched.assert_called_once_with(["dummy"])

    def test_patch_gateway_direct_also_works(self) -> None:
        """Patching through the canonical gateway path also works."""
        with mock.patch(
            "astrid.gateway._run_default_brief_orchestrator",
            return_value=99,
        ) as patched:
            import astrid.gateway
            result = astrid.gateway._run_default_brief_orchestrator(["dummy"])
            self.assertEqual(result, 99)
            patched.assert_called_once_with(["dummy"])

    def test_gateway_attributes_on_pipeline(self) -> None:
        """Key gateway attributes must be reachable from astrid.pipeline."""
        import astrid.gateway
        import astrid.pipeline

        for name in (
            "main",
            "_run_default_brief_orchestrator",
            "_dispatch",
            "_build_dispatch_parser",
            "_TOP_LEVEL_HANDLERS",
            "_dispatch_elements",
            "_dispatch_skills",
            "_dispatch_packs",
            "_dispatch_executors",
            "LIFECYCLE_VERBS",
            "SPRINT1_UNBOUND_ALLOWLIST_CONTRACT",
        ):
            with self.subTest(name=name):
                gateway_attr = getattr(astrid.gateway, name)
                pipeline_attr = getattr(astrid.pipeline, name)
                self.assertIs(
                    gateway_attr, pipeline_attr,
                    f"astrid.gateway.{name} and astrid.pipeline.{name} must be "
                    f"the same object",
                )

    def test_patch_dispatch_through_pipeline(self) -> None:
        """Patching _dispatch via astrid.pipeline must intercept at the gateway."""
        import astrid.gateway

        self.assertTrue(
            hasattr(astrid.gateway, "_dispatch"),
            "_dispatch must be an attribute of astrid.gateway",
        )
        self.assertTrue(callable(astrid.gateway._dispatch))

        with mock.patch(
            "astrid.pipeline._dispatch",
            return_value=77,
        ) as patched:
            from astrid import pipeline
            result = pipeline._dispatch(["status"])
            self.assertEqual(result, 77)
            patched.assert_called_once_with(["status"])

    def test_patch_dispatch_elements_through_pipeline(self) -> None:
        """Patching _dispatch_elements via astrid.pipeline must intercept."""
        import astrid.gateway

        self.assertTrue(callable(astrid.gateway._dispatch_elements))

        with mock.patch(
            "astrid.pipeline._dispatch_elements",
            return_value=88,
        ) as patched:
            from astrid import pipeline
            result = pipeline._dispatch_elements(["list"])
            self.assertEqual(result, 88)
            patched.assert_called_once_with(["list"])


# ---------------------------------------------------------------------------
# Deprecated CLI alias routing — astrid run and astrid author
# ---------------------------------------------------------------------------

class DeprecatedCLIAliasTest(unittest.TestCase):
    """Deprecated CLI aliases must route to their canonical equivalents.

    In `astrid/gateway.py`:
      "run" → _dispatch_runs  (deprecated alias for "runs")
      "author" → _dispatch_orchestrate  (deprecated alias for "orchestrate")
    """

    def test_run_alias_maps_to_runs_handler(self) -> None:
        import astrid.gateway

        self.assertIn("run", astrid.gateway._TOP_LEVEL_HANDLERS,
                      "'run' must be a top-level handler key")
        self.assertIn("runs", astrid.gateway._TOP_LEVEL_HANDLERS,
                      "'runs' must be a top-level handler key")

        run_handler = astrid.gateway._TOP_LEVEL_HANDLERS["run"]
        runs_handler = astrid.gateway._TOP_LEVEL_HANDLERS["runs"]

        # The deprecated "run" alias should delegate to _dispatch_runs too
        # (both wrap it via lambdas, so we check the functions are equivalent)
        self.assertIsNotNone(run_handler, "run handler must not be None")
        self.assertIsNotNone(runs_handler, "runs handler must not be None")

    def test_author_alias_maps_to_orchestrate_handler(self) -> None:
        import astrid.gateway

        self.assertIn("author", astrid.gateway._TOP_LEVEL_HANDLERS,
                      "'author' must be a top-level handler key")
        self.assertIn("orchestrate", astrid.gateway._TOP_LEVEL_HANDLERS,
                      "'orchestrate' must be a top-level handler key")

        author_handler = astrid.gateway._TOP_LEVEL_HANDLERS["author"]
        orch_handler = astrid.gateway._TOP_LEVEL_HANDLERS["orchestrate"]

        # M5 keeps "author" as a public alias but routes it through a warning
        # wrapper so callers see the canonical "orchestrate" replacement.
        self.assertIsNotNone(author_handler, "author handler must not be None")
        self.assertIsNot(author_handler, orch_handler,
                         "'author' must use the deprecating wrapper, not the "
                         "canonical orchestrate handler directly")

    def test_help_text_documents_deprecated_aliases(self) -> None:
        """The gateway help text must document that run/author are deprecated."""
        import io

        import astrid.gateway

        # _print_entrypoint_help prints to stdout; capture its output
        captured = io.StringIO()
        with mock.patch("sys.stdout", captured):
            astrid.gateway._print_entrypoint_help()

        text = captured.getvalue()
        self.assertIn("astrid author", text)
        self.assertIn("deprecated aliases", text)

    def test_run_dispatches_to_runs(self) -> None:
        """_dispatch_run delegates to _dispatch_runs."""
        import astrid.gateway

        # The _dispatch_run function is the deprecated alias that delegates
        self.assertTrue(callable(astrid.gateway._dispatch_run))
        self.assertIn(
            "Deprecated alias",
            astrid.gateway._dispatch_run.__doc__ or "",
            "_dispatch_run docstring must note it is a deprecated alias",
        )


# ---------------------------------------------------------------------------
# astrid.__main__ delegates to gateway
# ---------------------------------------------------------------------------

class MainModuleTest(unittest.TestCase):
    """astrid.__main__ must be the package entry point that delegates to gateway."""

    def test_main_uses_gateway_main(self) -> None:
        import astrid.__main__
        import astrid.gateway

        # __main__ sets ASTRID_INTERNAL_INVOCATION and calls gateway.main()
        self.assertIs(
            astrid.__main__.main, astrid.gateway.main,
            "astrid.__main__.main must be astrid.gateway.main",
        )


# ---------------------------------------------------------------------------
# Banodoco integration imports
# ---------------------------------------------------------------------------

class BanodocoIntegrationImportTest(unittest.TestCase):
    """Banodoco integration modules must be importable and remain in place
    for M2 (removal is deferred to a later milestone per SD3)."""

    def test_banodoco_worker_importable(self) -> None:
        import astrid.core.worker.banodoco_worker
        self.assertIsNotNone(astrid.core.worker.banodoco_worker)

    def test_banodoco_schema_importable(self) -> None:
        import astrid.core.timeline.banodoco_schema
        self.assertIsNotNone(astrid.core.timeline.banodoco_schema)

    def test_banodoco_composer_importable(self) -> None:
        import astrid.core.timeline.banodoco_composer
        self.assertIsNotNone(astrid.core.timeline.banodoco_composer)

    def test_timeline_banodoco_composer_shim_importable(self) -> None:
        """The astrid.timeline.banodoco_composer compatibility re-export."""
        import astrid.timeline.banodoco_composer
        self.assertIsNotNone(astrid.timeline.banodoco_composer)


# ---------------------------------------------------------------------------
# astrid.paths and astrid._paths namespace
# ---------------------------------------------------------------------------

class PathsModuleTest(unittest.TestCase):
    """Both astrid.paths and astrid._paths must export canonical path constants."""

    def test_paths_constants_importable(self) -> None:
        import astrid.paths

        for name in ("PACKAGE_ROOT", "REPO_ROOT", "WORKSPACE_ROOT"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(astrid.paths, name),
                                f"astrid.paths missing {name}")

    def test_underscore_paths_re_exports(self) -> None:
        """astrid._paths must re-export from astrid.paths as a compatibility shim."""
        import astrid._paths
        import astrid.paths

        for name in ("PACKAGE_ROOT", "REPO_ROOT", "WORKSPACE_ROOT"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(astrid._paths, name),
                                f"astrid._paths missing {name}")
                self.assertEqual(
                    getattr(astrid._paths, name),
                    getattr(astrid.paths, name),
                    f"astrid._paths.{name} != astrid.paths.{name}",
                )

    def test_paths_functions_importable(self) -> None:
        import astrid.paths

        self.assertTrue(hasattr(astrid.paths, "executor_argv"))
        self.assertTrue(hasattr(astrid.paths, "resolve_executor_runtime_module"))
        self.assertTrue(callable(astrid.paths.resolve_executor_runtime_module))


# ---------------------------------------------------------------------------
# astrid.media and astrid._media namespace
# ---------------------------------------------------------------------------

class MediaModuleTest(unittest.TestCase):
    """Both astrid.media and astrid._media must export media-probing helpers."""

    def test_media_importable(self) -> None:
        import astrid.media

        self.assertTrue(hasattr(astrid.media, "ffprobe_duration_seconds"),
                        "astrid.media missing ffprobe_duration_seconds")
        self.assertTrue(callable(astrid.media.ffprobe_duration_seconds))

    def test_underscore_media_re_exports(self) -> None:
        """astrid._media must re-export from astrid.media as a compatibility shim."""
        import astrid._media
        import astrid.media

        self.assertTrue(hasattr(astrid._media, "ffprobe_duration_seconds"))
        self.assertEqual(
            astrid._media.ffprobe_duration_seconds,
            astrid.media.ffprobe_duration_seconds,
            "astrid._media.ffprobe_duration_seconds must be the same as "
            "astrid.media.ffprobe_duration_seconds",
        )


# ---------------------------------------------------------------------------
# astrid.theme_schema validation surface
# ---------------------------------------------------------------------------

class ThemeSchemaTest(unittest.TestCase):
    """astrid.theme_schema must export theme validation helpers."""

    def test_theme_schema_constants_importable(self) -> None:
        import astrid.theme_schema

        self.assertTrue(hasattr(astrid.theme_schema, "THEME_SCHEMA"))
        self.assertTrue(hasattr(astrid.theme_schema, "ThemeValidationError"))

    def test_validate_theme_importable(self) -> None:
        from astrid.theme_schema import load_theme

        self.assertTrue(callable(load_theme))


# ---------------------------------------------------------------------------
# astrid.structure validation surface
# ---------------------------------------------------------------------------

class StructureModuleTest(unittest.TestCase):
    """astrid.structure must export repository structure guardrails."""

    def test_structure_importable(self) -> None:
        import astrid.structure

        self.assertTrue(hasattr(astrid.structure, "TOP_LEVEL_ASTRID_FILES"))
        self.assertTrue(hasattr(astrid.structure, "LEGACY_PUBLIC_DIRS"))


# ---------------------------------------------------------------------------
# astrid.threads internal library surface
# ---------------------------------------------------------------------------

class ThreadsModuleTest(unittest.TestCase):
    """astrid.threads is retained as an internal library (DEC-001).
    Its exported names must remain importable."""

    def test_threads_exports_importable(self) -> None:
        import astrid.threads

        for name in (
            "SCHEMA_VERSION",
            "ThreadIndexError",
            "ThreadIndexLockTimeout",
            "ThreadIndexStore",
            "build_run_record",
            "finalize_run_record",
            "generate_group_id",
            "generate_run_id",
            "generate_thread_id",
            "is_ulid",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(astrid.threads, name),
                                f"astrid.threads missing {name}")


# ---------------------------------------------------------------------------
# astrid.timeline public compatibility re-exports
# ---------------------------------------------------------------------------

class TimelinePublicSurfaceTest(unittest.TestCase):
    """The public names of `astrid.timeline` must remain importable."""

    def test_timeline_core_types_importable(self) -> None:
        import astrid.timeline as t

        for name in (
            "TimelineClip",
            "TimelineConfig",
            "ThemeOverrides",
            "TimelineOutput",
            "AssetEntry",
            "Theme",
            "Timeline",
            "TimelineEffect",
            "ClipType",
            "BUILTIN_CLIP_TYPES",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(t, name), f"missing {name}")

    def test_timeline_constants_importable(self) -> None:
        import astrid.timeline as t

        for name in ("ARRANGEMENT_VERSION", "METADATA_VERSION", "POOL_VERSION"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(t, name), f"missing {name}")

    def test_timeline_functions_importable(self) -> None:
        import astrid.timeline as t

        for name in (
            "materialize_output",
            "canonical_empty_timeline",
            "canonical_timeline_config",
            "load_timeline",
            "save_timeline",
            "validate_timeline",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(t, name), f"missing {name}")
                self.assertTrue(callable(getattr(t, name)),
                                f"{name} not callable")


# ---------------------------------------------------------------------------
# Deliberately not covered here (handled by test_m5b_baseline_public_surface.py):
#   - Deep timeline_model re-export surface (test_m5b already covers)
#   - banodoco_composer deep re-export surface (test_m5b already covers)
#   - timeline render views, track types, clip entrance/exit, pool types,
#     arrangement types, pipeline metadata, etc. (test_m5b already covers)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    unittest.main()
