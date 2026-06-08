"""Baseline public-surface guardrail tests for m5b god-module splits.

Captures the pre-split public import surface of ``astrid.core.timeline`` and
``astrid.core.task.lifecycle``, plus CLI behavior guardrails for default
brief routing, unknown top-level commands, and documented lifecycle command
parsing.  These tests must continue to pass after the splits; only the
compatibility-shim re-exports may change which internal module provides the
symbol.

DO NOT MODIFY the assertions in this module without a corresponding plan
change.  They are the contractual baseline.
"""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from unittest import mock


# ---------------------------------------------------------------------------
# astrid.core.timeline public import surface
# ---------------------------------------------------------------------------

class TimelinePublicSurfaceTest(unittest.TestCase):
    """The pre-split public names of ``astrid.core.timeline`` must remain importable.

    These are the names that external callers (conftest.py, project seeders,
    element catalog tests, etc.) import directly from the module.  Every
    name below must resolve from ``import astrid.core.timeline`` or
    ``from astrid.core.timeline import ...``.
    """

    def test_public_names_importable(self) -> None:
        import astrid.core.timeline as t

        # Re-exports from banodoco_timeline_schema (or fallback TypedDicts)
        for name in (
            "TimelineClip",
            "TimelineConfig",
            "ThemeOverrides",
            "TimelineOutput",
            "AssetEntry",
            "Theme",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(t, name), f"missing {name}")

    def test_materialize_output_importable(self) -> None:
        from astrid.core.timeline import materialize_output

        self.assertTrue(callable(materialize_output))

    def test_timeline_effect_types_importable(self) -> None:
        from astrid.core.timeline import TimelineEffect

        self.assertIsNotNone(TimelineEffect)

    def test_animation_types_importable(self) -> None:
        from astrid.core.timeline import (
            AnimationReference,
            AnimationReferenceList,
            AnimationReferenceObject,
        )

        self.assertIsNotNone(AnimationReference)
        self.assertIsNotNone(AnimationReferenceList)
        self.assertIsNotNone(AnimationReferenceObject)

    def test_parameter_types_importable(self) -> None:
        from astrid.core.timeline import (
            ParameterDefinition,
            ParameterOption,
            ParameterType,
        )

        self.assertIsNotNone(ParameterDefinition)
        self.assertIsNotNone(ParameterOption)
        self.assertIsNotNone(ParameterType)

    def test_track_types_importable(self) -> None:
        from astrid.core.timeline import (
            TrackBlendMode,
            TrackDefinition,
            TrackFit,
            TrackKind,
        )

        self.assertIsNotNone(TrackBlendMode)
        self.assertIsNotNone(TrackDefinition)
        self.assertIsNotNone(TrackFit)
        self.assertIsNotNone(TrackKind)

    def test_clip_entrance_exit_types_importable(self) -> None:
        from astrid.core.timeline import (
            ClipContinuous,
            ClipEntrance,
            ClipExit,
            ClipTransition,
            ClipTransitionReference,
        )

        self.assertIsNotNone(ClipContinuous)
        self.assertIsNotNone(ClipEntrance)
        self.assertIsNotNone(ClipExit)
        self.assertIsNotNone(ClipTransition)
        self.assertIsNotNone(ClipTransitionReference)

    def test_text_clip_data_importable(self) -> None:
        from astrid.core.timeline import TextAlignment, TextClipData

        self.assertIsNotNone(TextAlignment)
        self.assertIsNotNone(TextClipData)

    def test_asset_registry_types_importable(self) -> None:
        from astrid.core.timeline import AssetRegistry, AssetRegistryEntry

        self.assertIsNotNone(AssetRegistry)
        self.assertIsNotNone(AssetRegistryEntry)

    def test_pool_types_importable(self) -> None:
        from astrid.core.timeline import (
            Pool,
            PoolCategory,
            PoolEntry,
            PoolKind,
            PoolScores,
        )

        self.assertIsNotNone(Pool)
        self.assertIsNotNone(PoolCategory)
        self.assertIsNotNone(PoolEntry)
        self.assertIsNotNone(PoolKind)
        self.assertIsNotNone(PoolScores)

    def test_arrangement_types_importable(self) -> None:
        from astrid.core.timeline import (
            Arrangement,
            ArrangementAudioSource,
            ArrangementClip,
            ArrangementTextOverlay,
            ArrangementVisualRole,
            ArrangementVisualSource,
        )

        self.assertIsNotNone(Arrangement)
        self.assertIsNotNone(ArrangementAudioSource)
        self.assertIsNotNone(ArrangementClip)
        self.assertIsNotNone(ArrangementTextOverlay)
        self.assertIsNotNone(ArrangementVisualRole)
        self.assertIsNotNone(ArrangementVisualSource)

    def test_pipeline_metadata_types_importable(self) -> None:
        from astrid.core.timeline import PipelineMetadata, PipelineMetadataClipEntry

        self.assertIsNotNone(PipelineMetadata)
        self.assertIsNotNone(PipelineMetadataClipEntry)

    def test_clip_classified_kind_importable(self) -> None:
        from astrid.core.timeline import ClipClassifiedKind

        self.assertIsNotNone(ClipClassifiedKind)

    def test_canonical_empty_timeline_importable(self) -> None:
        from astrid.core.timeline import canonical_empty_timeline

        self.assertTrue(callable(canonical_empty_timeline))

    def test_validate_timeline_config_for_container_importable(self) -> None:
        from astrid.core.timeline import validate_timeline_config_for_container

        self.assertTrue(callable(validate_timeline_config_for_container))

    def test_canonical_timeline_config_importable(self) -> None:
        from astrid.core.timeline import canonical_timeline_config

        self.assertTrue(callable(canonical_timeline_config))

    def test_timeline_config_digest_importable(self) -> None:
        from astrid.core.timeline import timeline_config_digest

        self.assertTrue(callable(timeline_config_digest))

    def test_timeline_configs_equal_importable(self) -> None:
        from astrid.core.timeline import timeline_configs_equal

        self.assertTrue(callable(timeline_configs_equal))

    def test_load_save_functions_importable(self) -> None:
        import astrid.core.timeline as t

        for name in (
            "load_timeline",
            "save_timeline",
            "validate_timeline",
            "load_registry",
            "save_registry",
            "validate_registry",
            "load_pool",
            "save_pool",
            "validate_pool",
            "load_metadata",
            "save_metadata",
            "validate_metadata",
            "load_arrangement",
            "save_arrangement",
            "validate_arrangement",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(t, name), f"missing {name}")
                self.assertTrue(callable(getattr(t, name)), f"{name} not callable")

    def test_validate_arrangement_duration_window_importable(self) -> None:
        from astrid.core.timeline import validate_arrangement_duration_window

        self.assertTrue(callable(validate_arrangement_duration_window))

    def test_resolve_timeline_theme_importable(self) -> None:
        from astrid.core.timeline import resolve_timeline_theme

        self.assertTrue(callable(resolve_timeline_theme))

    def test_merge_generation_importable(self) -> None:
        from astrid.core.timeline import merge_generation

        self.assertTrue(callable(merge_generation))

    def test_is_all_generative_arrangement_importable(self) -> None:
        from astrid.core.timeline import is_all_generative_arrangement

        self.assertTrue(callable(is_all_generative_arrangement))

    def test_timeline_render_view_importable(self) -> None:
        from astrid.core.timeline import TimelineRenderView

        self.assertIsNotNone(TimelineRenderView)

    def test_timeline_clip_view_importable(self) -> None:
        from astrid.core.timeline import TimelineClipView

        self.assertIsNotNone(TimelineClipView)

    def test_timeline_class_importable(self) -> None:
        """The Timeline dataclass is the main runtime timeline container."""
        from astrid.core.timeline import Timeline

        self.assertIsNotNone(Timeline)

    def test_builtin_clip_types_importable(self) -> None:
        from astrid.core.timeline import BUILTIN_CLIP_TYPES, ClipType

        self.assertIsNotNone(BUILTIN_CLIP_TYPES)
        self.assertIsNotNone(ClipType)

    def test_audio_binding_importable(self) -> None:
        from astrid.core.timeline import AudioBindingSource, AudioBindingValue

        self.assertIsNotNone(AudioBindingSource)
        self.assertIsNotNone(AudioBindingValue)

    def test_source_ids_importable(self) -> None:
        from astrid.core.timeline import SourceIds

        self.assertIsNotNone(SourceIds)

    def test_pipeline_pool_kind_importable(self) -> None:
        from astrid.core.timeline import PipelinePoolKind

        self.assertIsNotNone(PipelinePoolKind)

    def test_version_constants_importable(self) -> None:
        from astrid.core.timeline import ARRANGEMENT_VERSION, METADATA_VERSION, POOL_VERSION

        self.assertIsNotNone(ARRANGEMENT_VERSION)
        self.assertIsNotNone(METADATA_VERSION)
        self.assertIsNotNone(POOL_VERSION)

    def test_carry_forward_source_fields_importable(self) -> None:
        from astrid.core.timeline import CARRY_FORWARD_SOURCE_FIELDS

        self.assertIsNotNone(CARRY_FORWARD_SOURCE_FIELDS)

    def test_arrangement_duration_error_importable(self) -> None:
        from astrid.core.timeline import ArrangementDurationError

        self.assertIsNotNone(ArrangementDurationError)

    def test_fallback_shared_types_importable(self) -> None:
        """The fallback TypedDicts used when banodoco_timeline_schema is absent."""
        import astrid.core.timeline as t

        for name in (
            "SharedAssetEntry",
            "SharedTheme",
            "SharedThemeOverrides",
            "SharedTimelineClip",
            "SharedTimelineConfig",
            "SharedTimelineOutput",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(t, name), f"missing {name}")


# ---------------------------------------------------------------------------
# astrid.core.timeline canonical-source verification
# ---------------------------------------------------------------------------

class TimelineCanonicalSourceTest(unittest.TestCase):
    """The public ``astrid.core.timeline`` module must expose every required name
    and each name's ``__module__`` must point to the canonical source submodule.

    This confirms the implementation source resolution within the canonical
    ``astrid.core.timeline`` package.
    """

    def test_top_level_names_resolve_to_canonical_core(self) -> None:
        import astrid.core.timeline as t

        # Functions and classes *defined* in our canonical core → strict check
        strict_schema_checks: list[tuple[str, str]] = [
            ("validate_timeline", "astrid.core.timeline.banodoco_schema"),
            ("validate_timeline_config_for_container", "astrid.core.timeline.banodoco_schema"),
            ("canonical_timeline_config", "astrid.core.timeline.banodoco_schema"),
            ("canonical_empty_timeline", "astrid.core.timeline.banodoco_schema"),
            ("timeline_config_digest", "astrid.core.timeline.banodoco_schema"),
            ("timeline_configs_equal", "astrid.core.timeline.banodoco_schema"),
            ("ArrangementDurationError", "astrid.core.timeline.banodoco_schema"),
            ("_effect_ids", "astrid.core.timeline.banodoco_schema"),
        ]
        for name, expected_module in strict_schema_checks:
            with self.subTest(group="strict-schema", name=name):
                obj = getattr(t, name)
                self.assertEqual(
                    getattr(obj, "__module__", None),
                    expected_module,
                    f"{name}.__module__ = {getattr(obj, '__module__', None)!r}",
                )

        strict_composer_checks: list[tuple[str, str]] = [
            ("Timeline", "astrid.core.timeline.banodoco_composer"),
            ("TimelineClipView", "astrid.core.timeline.banodoco_composer"),
            ("TimelineRenderView", "astrid.core.timeline.banodoco_composer"),
            ("save_timeline", "astrid.core.timeline.banodoco_composer"),
            ("load_timeline", "astrid.core.timeline.banodoco_composer"),
            ("merge_generation", "astrid.core.timeline.banodoco_composer"),
            ("resolve_timeline_theme", "astrid.core.timeline.banodoco_composer"),
        ]
        for name, expected_module in strict_composer_checks:
            with self.subTest(group="strict-composer", name=name):
                obj = getattr(t, name)
                self.assertEqual(
                    getattr(obj, "__module__", None),
                    expected_module,
                    f"{name}.__module__ = {getattr(obj, '__module__', None)!r}",
                )

        # TypedDict types: on Python >= 3.12 they resolve to our module;
        # on Python < 3.12 they keep the external package __module__.
        # Both are valid — the facade is a thin re-export.
        typed_dict_ok = (
            "astrid.core.timeline.banodoco_schema",
            "banodoco_timeline_schema.generated",
        )
        for name in ("TimelineClip", "TimelineConfig", "ThemeOverrides",
                      "AssetEntry", "SharedAssetEntry"):
            with self.subTest(group="typed-dict", name=name):
                obj = getattr(t, name)
                actual = getattr(obj, "__module__", None)
                self.assertIn(
                    actual, typed_dict_ok,
                    f"{name}.__module__ = {actual!r} not in {typed_dict_ok}",
                )

        # Typing constructs (Literal, Union aliases) → 'typing' or our module
        typing_ok = (
            "astrid.core.timeline.banodoco_schema",
            "typing",
        )
        for name in ("AnimationReference", "TrackKind", "ParameterType"):
            with self.subTest(group="typing-alias", name=name):
                obj = getattr(t, name)
                actual = getattr(obj, "__module__", None)
                self.assertIn(
                    actual, typing_ok,
                    f"{name}.__module__ = {actual!r} not in {typing_ok}",
                )

    def test_no_private_hooks_in_timeline_package(self) -> None:
        """The ``astrid.core.timeline`` package must not define private hooks
        or validation wrappers — its ``__init__.py`` is the public surface."""
        import astrid.core.timeline

        init_file = astrid.core.timeline.__file__
        self.assertIsNotNone(init_file)
        self.assertIn("__init__.py", str(init_file))

        # _sync_private_hooks must not exist anywhere in the public surface
        self.assertFalse(
            hasattr(astrid.core.timeline, "_sync_private_hooks"),
            "astrid.core.timeline must not expose _sync_private_hooks",
        )




# ---------------------------------------------------------------------------
# astrid.core.task.lifecycle public import surface
# ---------------------------------------------------------------------------

class LifecyclePublicSurfaceTest(unittest.TestCase):
    """The pre-split public names of ``astrid.core.task.lifecycle``.

    The module's ``__all__`` enumerates the eight canonical lifecycle verbs.
    After the split every name in ``__all__`` must remain importable from
    this exact module path (the module itself may become a shim).
    """

    def test_all_names_importable(self) -> None:
        import astrid.core.task.lifecycle as lc

        self.assertTrue(hasattr(lc, "__all__"), "lifecycle module must define __all__")
        for name in lc.__all__:
            with self.subTest(name=name):
                self.assertTrue(hasattr(lc, name), f"missing {name} from lifecycle")
                self.assertTrue(
                    callable(getattr(lc, name)),
                    f"lifecycle.{name} not callable",
                )

    def test_all_exact_members(self) -> None:
        """Pin the exact __all__ contents so the split is auditable."""
        from astrid.core.task.lifecycle import __all__ as lifecycle_all

        expected = [
            "cmd_abort",
            "cmd_ack",
            "cmd_next",
            "cmd_runs_ls",
            "cmd_skip",
            "cmd_start",
            "cmd_status",
            "cmd_step_retry_fetch",
        ]
        self.assertEqual(sorted(lifecycle_all), sorted(expected))

    def test_cmd_start_signature_accepts_args(self) -> None:
        """cmd_start must accept a list of argv tokens."""
        from astrid.core.task.lifecycle import cmd_start

        # --help path does not require a project
        self.assertIsInstance(cmd_start(["--help"]), int)

    def test_cmd_next_signature_accepts_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_next

        self.assertIsInstance(cmd_next(["--help"]), int)

    def test_cmd_ack_signature_accepts_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_ack

        self.assertIsInstance(cmd_ack(["--help"]), int)

    def test_cmd_skip_signature_accepts_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_skip

        self.assertIsInstance(cmd_skip(["--help"]), int)

    def test_cmd_abort_signature_accepts_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_abort

        self.assertIsInstance(cmd_abort(["--help"]), int)

    def test_cmd_status_signature_accepts_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_status

        self.assertIsInstance(cmd_status(["--help"]), int)

    def test_cmd_runs_ls_signature_accepts_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_runs_ls

        self.assertIsInstance(cmd_runs_ls(["--help"]), int)

    def test_cmd_step_retry_fetch_signature_accepts_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_step_retry_fetch

        self.assertIsInstance(cmd_step_retry_fetch(["--help"]), int)

    def test_render_step_instructions_importable(self) -> None:
        """render_step_instructions is a key public helper used by cmd_next and friends."""
        from astrid.core.task.lifecycle import render_step_instructions

        self.assertTrue(callable(render_step_instructions))

    def test_lifecycle_imports_peek_current_step(self) -> None:
        """peek_current_step is re-exported from lifecycle for convenience."""
        from astrid.core.task.lifecycle import peek_current_step

        self.assertTrue(callable(peek_current_step))

    def test_lifecycle_functions_help_clean_exit(self) -> None:
        """Lifecycle verbs print help cleanly (most exit 0; cmd_skip has a known quirk)."""
        from astrid.core.task.lifecycle import (
            cmd_abort,
            cmd_ack,
            cmd_next,
            cmd_runs_ls,
            cmd_skip,
            cmd_start,
            cmd_status,
            cmd_step_retry_fetch,
        )

        verbs: dict[str, tuple[object, int]] = {
            "cmd_start": (cmd_start, 0),
            "cmd_next": (cmd_next, 0),
            "cmd_ack": (cmd_ack, 0),
            # Pre-split quirk: cmd_skip --help returns 2 because
            # ``int(exc.code or 2)`` converts argparse's exit-0 to 2.
            "cmd_skip": (cmd_skip, 2),
            "cmd_abort": (cmd_abort, 0),
            "cmd_status": (cmd_status, 0),
            "cmd_runs_ls": (cmd_runs_ls, 0),
            "cmd_step_retry_fetch": (cmd_step_retry_fetch, 0),
        }
        for name, (fn, expected) in verbs.items():
            with self.subTest(verb=name):
                self.assertEqual(
                    fn(["--help"]), expected, f"{name} --help returned unexpected code"
                )


# ---------------------------------------------------------------------------
# CLI guardrails — unknown top-level commands
# ---------------------------------------------------------------------------

class UnknownCommandGuardrailTest(unittest.TestCase):
    """Unknown top-level non-option subcommands must exit nonzero.

    The gateway MUST NOT silently route unknown commands into the default
    hype orchestrator.  The error must be printed to stderr and the exit
    code must be 2.
    """

    def test_unknown_top_level_command_exits_2(self) -> None:
        from astrid.core import gateway

        with mock.patch(
            "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
            return_value=object(),
        ):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = gateway.main(["nonexistentcmd123"])
            self.assertEqual(exit_code, 2)
            self.assertIn("unknown command", stderr.getvalue())
            self.assertIn("nonexistentcmd123", stderr.getvalue())

    def test_multiple_unknown_commands(self) -> None:
        """A spread of non-existent commands all produce the same guardrail."""
        from astrid.core import gateway

        bogus = ["xyzzy", "floob", "gargleblaster", "notarealthing"]
        with mock.patch(
            "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
            return_value=object(),
        ):
            for cmd in bogus:
                with self.subTest(cmd=cmd):
                    stderr = io.StringIO()
                    with contextlib.redirect_stderr(stderr):
                        exit_code = gateway.main([cmd])
                    self.assertEqual(exit_code, 2)
                    self.assertIn(f"unknown command '{cmd}'", stderr.getvalue())

    def test_unknown_command_with_args(self) -> None:
        """Unknown command followed by extra args still exits 2."""
        from astrid.core import gateway

        with mock.patch(
            "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
            return_value=object(),
        ):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = gateway.main(["flarg", "--unknown-arg"])
            self.assertEqual(exit_code, 2)
            self.assertIn("unknown command", stderr.getvalue())

    def test_unknown_command_never_routes_to_default_orchestrator(self) -> None:
        """Verify that an unknown command does NOT invoke the default orchestrator."""
        from astrid.core import gateway

        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch(
                "astrid.core.gateway._run_default_brief_orchestrator",
            ) as mock_fallback,
        ):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = gateway.main(["boguscmd"])
            self.assertEqual(exit_code, 2)
            mock_fallback.assert_not_called()


# ---------------------------------------------------------------------------
# CLI guardrails — default brief routing
# ---------------------------------------------------------------------------

class DefaultBriefRoutingTest(unittest.TestCase):
    """Top-level brief/--video flags must route to the default orchestrator.

    The gateway routes flag-style invocations (those whose first token
    starts with ``--``) to ``_run_default_brief_orchestrator``, which
    resolves ``video_editing.hype`` via the orchestrator registry.
    """

    def test_double_dash_brief_routes_to_default(self) -> None:
        from astrid.core import gateway

        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch(
                "astrid.core.gateway._run_default_brief_orchestrator",
                return_value=42,
            ) as mock_fallback,
        ):
            exit_code = gateway.main(["--brief", "test brief content"])
            self.assertEqual(exit_code, 42)
            mock_fallback.assert_called_once_with(["--brief", "test brief content"])

    def test_double_dash_video_routes_to_default(self) -> None:
        from astrid.core import gateway

        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch(
                "astrid.core.gateway._run_default_brief_orchestrator",
                return_value=43,
            ) as mock_fallback,
        ):
            exit_code = gateway.main(["--video", "some/video.mp4", "--brief", "desc"])
            self.assertEqual(exit_code, 43)
            mock_fallback.assert_called_once_with(
                ["--video", "some/video.mp4", "--brief", "desc"]
            )

    def test_flag_style_out_routes_to_default(self) -> None:
        from astrid.core import gateway

        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch(
                "astrid.core.gateway._run_default_brief_orchestrator",
                return_value=44,
            ) as mock_fallback,
        ):
            exit_code = gateway.main(["--out", "runs/testrun", "--brief", "b"])
            self.assertEqual(exit_code, 44)
            mock_fallback.assert_called_once()

    def test_double_dash_render_routes_to_default(self) -> None:
        from astrid.core import gateway

        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch(
                "astrid.core.gateway._run_default_brief_orchestrator",
                return_value=45,
            ) as mock_fallback,
        ):
            exit_code = gateway.main(
                ["--brief", "hello", "--out", "runs/x", "--render"]
            )
            self.assertEqual(exit_code, 45)
            mock_fallback.assert_called_once()

    def test_target_duration_flag_routes_to_default(self) -> None:
        from astrid.core import gateway

        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch(
                "astrid.core.gateway._run_default_brief_orchestrator",
                return_value=46,
            ) as mock_fallback,
        ):
            exit_code = gateway.main(
                ["--brief", "x", "--out", "runs/y", "--target-duration", "60"]
            )
            self.assertEqual(exit_code, 46)
            mock_fallback.assert_called_once()

    def test_default_routing_preserves_all_args(self) -> None:
        """The complete argv is forwarded to the default orchestrator."""
        from astrid.core import gateway

        argv = [
            "--video",
            "input.mp4",
            "--brief",
            "Make a video about cats",
            "--out",
            "runs/cats",
            "--render",
            "--target-duration",
            "90",
        ]
        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch(
                "astrid.core.gateway._run_default_brief_orchestrator",
                return_value=47,
            ) as mock_fallback,
        ):
            exit_code = gateway.main(argv)
            self.assertEqual(exit_code, 47)
            mock_fallback.assert_called_once_with(argv)


# ---------------------------------------------------------------------------
# CLI guardrails — documented lifecycle command parsing
# ---------------------------------------------------------------------------

class LifecycleCommandParsingTest(unittest.TestCase):
    """Documented lifecycle commands must parse their expected argument shapes.

    These tests verify that each lifecycle verb's argparse parser accepts
    the documented flags and rejects malformed invocations.  They do NOT
    require a project directory or session — they test the parser layer.
    """

    def test_start_help_shows_required_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_start

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_start(["--help"])
        self.assertEqual(result, 0)
        help_text = stdout.getvalue()
        self.assertIn("--project", help_text)
        self.assertIn("--name", help_text)
        self.assertIn("start", help_text)

    def test_start_missing_required_arg_exits_2(self) -> None:
        """cmd_start without --project should exit non-zero."""
        from astrid.core.task.lifecycle import cmd_start

        # Without --project and without --help, the parser should fail
        result = cmd_start([])
        self.assertNotEqual(result, 0, "cmd_start with no args should fail")

    def test_next_help_shows_expected_options(self) -> None:
        from astrid.core.task.lifecycle import cmd_next

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_next(["--help"])
        self.assertEqual(result, 0)
        help_text = stdout.getvalue()
        self.assertIn("--project", help_text)
        self.assertIn("--skip", help_text)

    def test_ack_help_shows_expected_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_ack

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_ack(["--help"])
        self.assertEqual(result, 0)
        help_text = stdout.getvalue()
        self.assertIn("--project", help_text)
        self.assertIn("--decision", help_text)

    def test_skip_help_shows_expected_args(self) -> None:
        """cmd_skip --help prints usage but returns 2 due to argparse exception handling.

        NOTE: This is the current pre-split behavior.  The argparse SystemExit
        for --help carries code 0, but the except clause ``int(exc.code or 2)``
        converts it to 2.  This baseline documents the actual behavior.
        """
        from astrid.core.task.lifecycle import cmd_skip

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_skip(["--help"])
        # Pre-split behaviour: returns 2 (not 0) due to `int(code or 2)`.
        self.assertEqual(result, 2)
        help_text = stdout.getvalue()
        self.assertIn("--project", help_text)

    def test_abort_help_shows_expected_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_abort

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_abort(["--help"])
        self.assertEqual(result, 0)
        help_text = stdout.getvalue()
        self.assertIn("--project", help_text)

    def test_status_help_shows_expected_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_status

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_status(["--help"])
        self.assertEqual(result, 0)
        help_text = stdout.getvalue()
        self.assertIn("--project", help_text)

    def test_runs_ls_help_shows_expected_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_runs_ls

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_runs_ls(["--help"])
        self.assertEqual(result, 0)
        help_text = stdout.getvalue()
        self.assertIn("--project", help_text)

    def test_step_retry_fetch_help_shows_expected_args(self) -> None:
        from astrid.core.task.lifecycle import cmd_step_retry_fetch

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_step_retry_fetch(["--help"])
        self.assertEqual(result, 0)
        help_text = stdout.getvalue()
        self.assertIn("--project", help_text)

    def test_entrypoint_help_lists_core_lifecycle_verbs(self) -> None:
        """The top-level help must mention the core lifecycle verbs.

        NOTE: ``skip`` is intentionally omitted from the top-level help in the
        pre-split state — it is documented in ``cmd_skip``'s own --help output.
        """
        from astrid.core.gateway import _print_entrypoint_help

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            _print_entrypoint_help()
        help_text = stdout.getvalue()

        lifecycle_verbs = [
            "start",
            "next",
            "ack",
            "abort",
            "status",
        ]
        for verb in lifecycle_verbs:
            with self.subTest(verb=verb):
                self.assertIn(f"astrid {verb}", help_text, f"missing {verb} in help")

        # After T11 normalization, skip is listed in top-level help
        self.assertIn("astrid skip", help_text)

    def test_entrypoint_help_lists_runs_and_claim(self) -> None:
        """Top-level help mentions the 'runs ls' and 'claim' verbs."""
        from astrid.core.gateway import _print_entrypoint_help

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            _print_entrypoint_help()
        help_text = stdout.getvalue()

        self.assertIn("runs ls", help_text)
        self.assertIn("claim", help_text)

    def test_top_level_help_exits_0(self) -> None:
        """python3 -m astrid --help exits 0."""
        from astrid.core import gateway

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = gateway.main(["--help"])
        self.assertEqual(result, 0)

    def test_top_level_help_mentions_canonical_gateway(self) -> None:
        from astrid.core import gateway

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            gateway.main(["--help"])
        help_text = stdout.getvalue()
        self.assertIn("Astrid command gateway", help_text)
        self.assertIn("python3 -m astrid", help_text)

    def test_top_level_h_flag_exits_0(self) -> None:
        from astrid.core import gateway

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = gateway.main(["-h"])
        self.assertEqual(result, 0)
        self.assertIn("Astrid command gateway", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
