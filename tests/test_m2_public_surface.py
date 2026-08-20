"""M2 public-surface characterization tests.

Captures the canonical import surface, the eight-family CLI surface,
and Banodoco integration imports so that structural changes can be
verified against a known baseline.

These are characterization tests — they test current behavior without
changing it.  No assertion here should be a "fix."
"""

from __future__ import annotations

import unittest
from unittest import mock

# ---------------------------------------------------------------------------
# Root module imports — every top-level facade must be importable
# ---------------------------------------------------------------------------

class RootModuleImportTest(unittest.TestCase):
    """Root `astrid.*` modules and packages must be importable."""

    def test_gateway_importable(self) -> None:
        import astrid.core.gateway
        self.assertIsNotNone(astrid.core.gateway)

    def test_sdk_importable(self) -> None:
        import astrid.sdk
        self.assertIsNotNone(astrid.sdk)

    def test_paths_importable(self) -> None:
        import astrid.core.foundation.paths
        self.assertIsNotNone(astrid.core.foundation.paths)

    def test_media_importable(self) -> None:
        import astrid.core.media
        self.assertIsNotNone(astrid.core.media)

    def test_theme_schema_importable(self) -> None:
        import astrid.core.theme
        self.assertIsNotNone(astrid.core.theme)

    def test_structure_importable(self) -> None:
        import astrid.core.structure
        self.assertIsNotNone(astrid.core.structure)

    def test_threads_importable(self) -> None:
        import astrid.core.threads
        self.assertIsNotNone(astrid.core.threads)

    def test_timeline_importable(self) -> None:
        import astrid.core.timeline
        self.assertIsNotNone(astrid.core.timeline)

    def test_main_importable(self) -> None:
        """__main__ is the package entry point that delegates to gateway."""
        import astrid.__main__
        self.assertIsNotNone(astrid.__main__)


# ---------------------------------------------------------------------------
# Eight-family CLI surface — m6 cutover
# ---------------------------------------------------------------------------

class EightFamilySurfaceTest(unittest.TestCase):
    """The m6 gateway owns exactly eight families and no removed aliases.

    The five product families (projects, timelines, media, tasks, runs)
    plus the three operational families (serve, doctor, backup). The
    deprecated ``run``/``author``/``orchestrate`` aliases and their
    handler wrappers were removed by the m6 teardown.
    """

    def test_top_level_handlers_are_exactly_eight_families(self) -> None:
        import astrid.core.gateway

        self.assertEqual(
            set(astrid.core.gateway._TOP_LEVEL_HANDLERS),
            {
                "projects",
                "timelines",
                "media",
                "tasks",
                "runs",
                "serve",
                "doctor",
                "backup",
            },
        )

    def test_removed_alias_handlers_are_absent(self) -> None:
        import astrid.core.gateway

        for removed in (
            "run",
            "author",
            "orchestrate",
            "renderers",
            "replay",
            "elements",
            "executors",
            "orchestrators",
            "publish",
            "setup",
            "packs",
        ):
            with self.subTest(removed=removed):
                self.assertNotIn(removed, astrid.core.gateway._TOP_LEVEL_HANDLERS)

        # The deprecated alias helper functions are gone too.
        self.assertFalse(hasattr(astrid.core.gateway, "_dispatch_run"))
        self.assertFalse(
            hasattr(astrid.core.gateway, "_run_default_brief_orchestrator")
        )

    def test_top_level_commands_are_exactly_eight_families(self) -> None:
        import astrid.core.gateway

        self.assertEqual(
            astrid.core.gateway._top_level_commands(),
            frozenset(
                {
                    "projects",
                    "timelines",
                    "media",
                    "tasks",
                    "runs",
                    "serve",
                    "doctor",
                    "backup",
                }
            ),
        )

    def test_help_text_documents_the_eight_families(self) -> None:
        """The gateway help text documents the eight families and no
        deprecated aliases."""
        import io

        import astrid.core.gateway

        captured = io.StringIO()
        with mock.patch("sys.stdout", captured):
            astrid.core.gateway._print_entrypoint_help()

        text = captured.getvalue()
        for family in (
            "projects",
            "timelines",
            "media",
            "tasks",
            "runs",
            "serve",
            "doctor",
            "backup",
        ):
            self.assertIn(f"astrid {family}", text)
        for removed in (
            "astrid author",
            "astrid orchestrate",
            "deprecated aliases",
        ):
            self.assertNotIn(removed, text)


# ---------------------------------------------------------------------------
# astrid.__main__ delegates to gateway
# ---------------------------------------------------------------------------

class MainModuleTest(unittest.TestCase):
    """astrid.__main__ must be the package entry point that delegates to gateway."""

    def test_main_uses_gateway_main(self) -> None:
        import astrid.__main__
        import astrid.core.gateway

        # __main__ sets ASTRID_INTERNAL_INVOCATION and calls gateway.main()
        self.assertIs(
            astrid.__main__.main, astrid.core.gateway.main,
            "astrid.__main__.main must be astrid.core.gateway.main",
        )


# ---------------------------------------------------------------------------
# Banodoco integration imports
# ---------------------------------------------------------------------------

class BanodocoIntegrationImportTest(unittest.TestCase):
    """Banodoco integration modules must be importable and remain in place
    for M2 (removal is deferred to a later milestone per SD3)."""

    def test_banodoco_worker_importable(self) -> None:
        import astrid.core.integrations.worker.banodoco_worker
        self.assertIsNotNone(astrid.core.integrations.worker.banodoco_worker)

    def test_banodoco_schema_importable(self) -> None:
        import astrid.core.timeline.banodoco_schema
        self.assertIsNotNone(astrid.core.timeline.banodoco_schema)

    def test_banodoco_composer_importable(self) -> None:
        import astrid.core.timeline.banodoco_composer
        self.assertIsNotNone(astrid.core.timeline.banodoco_composer)


# ---------------------------------------------------------------------------
# astrid.core.foundation.paths namespace
# ---------------------------------------------------------------------------

class PathsModuleTest(unittest.TestCase):
    """astrid.core.foundation.paths must export canonical path constants."""

    def test_paths_constants_importable(self) -> None:
        import astrid.core.foundation.paths

        for name in ("PACKAGE_ROOT", "REPO_ROOT", "WORKSPACE_ROOT"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(astrid.core.foundation.paths, name),
                                f"astrid.core.foundation.paths missing {name}")

    def test_paths_functions_importable(self) -> None:
        import astrid.core.execution.executor.argv

        self.assertTrue(hasattr(astrid.core.execution.executor.argv, "executor_argv"))
        self.assertTrue(hasattr(astrid.core.execution.executor.argv, "resolve_executor_runtime_module"))
        self.assertTrue(callable(astrid.core.execution.executor.argv.resolve_executor_runtime_module))


# ---------------------------------------------------------------------------
# astrid.core.media namespace
# ---------------------------------------------------------------------------

class MediaModuleTest(unittest.TestCase):
    """astrid.core.media must export media-probing helpers."""

    def test_media_importable(self) -> None:
        import astrid.core.media

        self.assertTrue(hasattr(astrid.core.media, "ffprobe_duration_seconds"),
                        "astrid.core.media missing ffprobe_duration_seconds")
        self.assertTrue(callable(astrid.core.media.ffprobe_duration_seconds))

# ---------------------------------------------------------------------------
# astrid.core.theme validation surface
# ---------------------------------------------------------------------------

class ThemeSchemaTest(unittest.TestCase):
    """astrid.core.theme must export theme validation helpers."""

    def test_theme_schema_constants_importable(self) -> None:
        import astrid.core.theme

        self.assertTrue(hasattr(astrid.core.theme, "THEME_SCHEMA"))
        self.assertTrue(hasattr(astrid.core.theme, "ThemeValidationError"))

    def test_validate_theme_importable(self) -> None:
        from astrid.core.theme import load_theme

        self.assertTrue(callable(load_theme))


# ---------------------------------------------------------------------------
# astrid.core.structure validation surface
# ---------------------------------------------------------------------------

class StructureModuleTest(unittest.TestCase):
    """astrid.core.structure must export repository structure guardrails."""

    def test_structure_importable(self) -> None:
        import astrid.core.structure

        self.assertTrue(hasattr(astrid.core.structure, "TOP_LEVEL_ASTRID_FILES"))
        self.assertTrue(hasattr(astrid.core.structure, "LEGACY_PUBLIC_DIRS"))


# ---------------------------------------------------------------------------
# astrid.core.threads internal library surface
# ---------------------------------------------------------------------------

class ThreadsModuleTest(unittest.TestCase):
    """astrid.core.threads is retained as an internal library (DEC-001).
    Its exported names must remain importable."""

    def test_threads_exports_importable(self) -> None:
        import astrid.core.threads

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
                self.assertTrue(hasattr(astrid.core.threads, name),
                                f"astrid.core.threads missing {name}")


# ---------------------------------------------------------------------------
# astrid.core.timeline public surface
# ---------------------------------------------------------------------------

class TimelinePublicSurfaceTest(unittest.TestCase):
    """The public names of `astrid.core.timeline` must remain importable."""

    def test_timeline_core_types_importable(self) -> None:
        import astrid.core.timeline as t

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
        import astrid.core.timeline as t

        for name in ("ARRANGEMENT_VERSION", "METADATA_VERSION", "POOL_VERSION"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(t, name), f"missing {name}")

    def test_timeline_functions_importable(self) -> None:
        import astrid.core.timeline as t

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
#   - timeline render views, track types, clip entrance/exit, pool types,
#     arrangement types, pipeline metadata, etc. (test_m5b already covers)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    unittest.main()
