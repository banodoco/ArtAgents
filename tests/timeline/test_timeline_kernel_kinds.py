"""Kernel and event-schema tests proving bogus clip, track, and transition
kinds are rejected through registry validation when CLI parsing is bypassed.

Covers:
- ``normalize_event_clip_kind`` rejects invalid clip kinds.
- ``normalize_track_kind`` rejects invalid track kinds.
- ``normalize_transition_kind`` rejects invalid transition kinds and accepts
  ``cross-fade`` / ``crossfade`` alias.
- ``default_transition_kind`` and ``transition_kind_options`` return
  registry-backed values including ``cross-fade``.
- Event-schema payloads (``ClipAddedPayload``, ``TrackAddedPayload``,
  ``TransitionSetPayload``) validate through the same registry path
  independent of CLI argparse.
- Projection boundary validates track kinds through the registry.
- The retired local doctor module is absent and the public doctor route fails
  closed when runtime discovery is unavailable.

All tests bypass CLI parsing — they exercise the kernel/SDK APIs directly.
"""

from __future__ import annotations

import contextlib
import io
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from astrid.core.timeline.events.schema import (
    ClipAddedPayload,
    TimelineEventSchemaError,
    TrackAddedPayload,
    TransitionSetPayload,
)
from astrid.core.timeline.kinds import (
    default_transition_kind,
    normalize_event_clip_kind,
    normalize_track_kind,
    normalize_transition_kind,
    transition_kind_options,
    valid_event_clip_kinds,
)


# ============================================================================
# Kernel helpers — clip kind validation
# ============================================================================


class KernelClipKindTest(unittest.TestCase):
    """Direct tests of ``normalize_event_clip_kind`` (CLI-bypassed)."""

    def test_accepts_valid_event_clip_kinds(self) -> None:
        """Every documented event clip kind normalises to itself."""
        for kind in ("visual", "audio", "text"):
            with self.subTest(kind=kind):
                self.assertEqual(normalize_event_clip_kind(kind), kind)

    def test_canonicalises_registry_aliases_to_event_clip_kind(self) -> None:
        """Registry clip-catalog ids (video, image) map to 'visual' event kind."""
        self.assertEqual(normalize_event_clip_kind("video"), "visual")
        self.assertEqual(normalize_event_clip_kind("image"), "visual")

    def test_rejects_empty_clip_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "clip kind must be a non-empty string"):
            normalize_event_clip_kind("")

    def test_rejects_whitespace_clip_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "clip kind must be a non-empty string"):
            normalize_event_clip_kind("   ")

    def test_rejects_non_string_clip_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "clip kind must be a non-empty string"):
            normalize_event_clip_kind(None)  # type: ignore[arg-type]

    def test_rejects_bogus_clip_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, r"clip kind must be one of \["):
            normalize_event_clip_kind("visualzzz")

    def test_rejects_completely_unknown_clip_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, r"clip kind must be one of \["):
            normalize_event_clip_kind("bogus_kind_xyz")

    def test_valid_event_clip_kinds_tuple(self) -> None:
        kinds = valid_event_clip_kinds()
        self.assertIsInstance(kinds, tuple)
        self.assertIn("visual", kinds)
        self.assertIn("audio", kinds)
        self.assertIn("text", kinds)
        # Registry-level clip catalog ids are not event clip kinds.
        self.assertNotIn("video", kinds)
        self.assertNotIn("image", kinds)
        self.assertNotIn("effect", kinds)

    def test_rejects_with_custom_error_cls(self) -> None:
        class CustomErr(RuntimeError):
            pass

        with self.assertRaises(CustomErr):
            normalize_event_clip_kind("nope", error_cls=CustomErr)


# ============================================================================
# Kernel helpers — track kind validation
# ============================================================================


class KernelTrackKindTest(unittest.TestCase):
    """Direct tests of ``normalize_track_kind`` (CLI-bypassed)."""

    def test_accepts_valid_track_kinds(self) -> None:
        self.assertEqual(normalize_track_kind("visual"), "visual")
        self.assertEqual(normalize_track_kind("audio"), "audio")

    def test_rejects_empty_track_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "track kind must be a non-empty string"):
            normalize_track_kind("")

    def test_rejects_whitespace_track_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "track kind must be a non-empty string"):
            normalize_track_kind("   ")

    def test_rejects_non_string_track_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "track kind must be a non-empty string"):
            normalize_track_kind(None)  # type: ignore[arg-type]

    def test_rejects_bogus_track_kind_caption(self) -> None:
        """'caption' is not a valid track kind — captions are visual tracks."""
        with self.assertRaisesRegex(ValueError, r"track kind must be one of \["):
            normalize_track_kind("caption")

    def test_rejects_completely_unknown_track_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, r"track kind must be one of \["):
            normalize_track_kind("videotrack")

    def test_rejects_with_custom_error_cls(self) -> None:
        class CustomErr(RuntimeError):
            pass

        with self.assertRaises(CustomErr):
            normalize_track_kind("nope", error_cls=CustomErr)


# ============================================================================
# Kernel helpers — transition kind validation
# ============================================================================


class KernelTransitionKindTest(unittest.TestCase):
    """Direct tests of ``normalize_transition_kind`` (CLI-bypassed)."""

    def test_accepts_cross_fade(self) -> None:
        self.assertEqual(normalize_transition_kind("cross-fade"), "cross-fade")

    def test_canonicalises_crossfade_alias(self) -> None:
        self.assertEqual(normalize_transition_kind("crossfade"), "cross-fade")

    def test_rejects_empty_transition_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "transition kind must be a non-empty string"):
            normalize_transition_kind("")

    def test_rejects_whitespace_transition_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "transition kind must be a non-empty string"):
            normalize_transition_kind("   ")

    def test_rejects_non_string_transition_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "transition kind must be a non-empty string"):
            normalize_transition_kind(None)  # type: ignore[arg-type]

    def test_rejects_unknown_transition_kind_wipe(self) -> None:
        with self.assertRaisesRegex(ValueError, r"transition kind must be one of \["):
            normalize_transition_kind("wipe")

    def test_rejects_unknown_transition_kind_dissolve(self) -> None:
        with self.assertRaisesRegex(ValueError, r"transition kind must be one of \["):
            normalize_transition_kind("dissolve")

    def test_error_message_includes_cross_fade_in_options(self) -> None:
        """Error message must include 'cross-fade' in the valid options list."""
        with self.assertRaises(ValueError) as ctx:
            normalize_transition_kind("wipe")
        msg = str(ctx.exception)
        self.assertIn("cross-fade", msg,
                      "Error message must include 'cross-fade' as a valid option")
        self.assertIn("transition kind must be one of", msg)

    def test_rejects_with_custom_error_cls(self) -> None:
        class CustomErr(RuntimeError):
            pass

        with self.assertRaises(CustomErr):
            normalize_transition_kind("nope", error_cls=CustomErr)


# ============================================================================
# Kernel helpers — default / options
# ============================================================================


class KernelTransitionDefaultsTest(unittest.TestCase):
    """Tests for ``default_transition_kind`` and ``transition_kind_options``."""

    def test_default_transition_kind_is_cross_fade(self) -> None:
        self.assertEqual(default_transition_kind(), "cross-fade")

    def test_transition_kind_options_includes_cross_fade(self) -> None:
        options = transition_kind_options()
        self.assertIsInstance(options, tuple)
        self.assertIn("cross-fade", options)

    def test_transition_kind_options_are_canonical_only(self) -> None:
        """Options returned are canonical names, not aliases."""
        options = transition_kind_options()
        for opt in options:
            self.assertEqual(opt, normalize_transition_kind(opt))


# ============================================================================
# Event-schema payload tests — bypass CLI, validate through registry
# ============================================================================


class EventSchemaClipKindValidationTest(unittest.TestCase):
    """ClipAddedPayload kind validation bypasses CLI and uses the registry."""

    def test_clip_added_payload_accepts_event_clip_kinds(self) -> None:
        for kind in ("visual", "audio", "text"):
            with self.subTest(kind=kind):
                p = ClipAddedPayload(
                    clip_id="c1", kind=kind,  # type: ignore[arg-type]
                    asset_id="a1", track_id="visual",
                )
                self.assertEqual(p.kind, kind)

    def test_clip_added_payload_rejects_bogus_kind(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipAddedPayload(
                clip_id="c1", kind="visualzzz",  # type: ignore[arg-type]
                asset_id="a1", track_id="visual",
            )

    def test_clip_added_payload_rejects_empty_kind(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipAddedPayload(
                clip_id="c1", kind="",  # type: ignore[arg-type]
                asset_id="a1", track_id="visual",
            )


class EventSchemaTrackKindValidationTest(unittest.TestCase):
    """TrackAddedPayload kind validation bypasses CLI and uses the registry."""

    def test_track_added_payload_accepts_valid_kinds(self) -> None:
        for kind in ("visual", "audio"):
            with self.subTest(kind=kind):
                p = TrackAddedPayload(
                    track_id="trk-1", kind=kind, label="L",  # type: ignore[arg-type]
                )
                self.assertEqual(p.kind, kind)

    def test_track_added_payload_rejects_bogus_kind(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TrackAddedPayload(
                track_id="trk-1", kind="caption", label="L",  # type: ignore[arg-type]
            )

    def test_track_added_payload_rejects_empty_kind(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TrackAddedPayload(
                track_id="trk-1", kind="", label="L",  # type: ignore[arg-type]
            )


class EventSchemaTransitionKindValidationTest(unittest.TestCase):
    """TransitionSetPayload kind validation bypasses CLI and uses the registry."""

    def test_transition_set_payload_accepts_cross_fade(self) -> None:
        p = TransitionSetPayload(
            left_clip_id="a", right_clip_id="b",
            kind="cross-fade", duration_seconds=1.0,
        )
        self.assertEqual(p.kind, "cross-fade")

    def test_transition_set_payload_canonicalises_crossfade_alias(self) -> None:
        p = TransitionSetPayload(
            left_clip_id="a", right_clip_id="b",
            kind="crossfade", duration_seconds=1.0,
        )
        self.assertEqual(p.kind, "cross-fade")

    def test_transition_set_payload_rejects_unknown_kind_wipe(self) -> None:
        with self.assertRaisesRegex(TimelineEventSchemaError,
                                    r"transition kind must be one of \["):
            TransitionSetPayload(
                left_clip_id="a", right_clip_id="b",
                kind="wipe", duration_seconds=1.0,
            )

    def test_transition_set_payload_rejects_unknown_kind_dissolve(self) -> None:
        with self.assertRaisesRegex(TimelineEventSchemaError,
                                    r"transition kind must be one of \["):
            TransitionSetPayload(
                left_clip_id="a", right_clip_id="b",
                kind="dissolve", duration_seconds=1.0,
            )

    def test_transition_set_payload_rejects_empty_kind(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TransitionSetPayload(
                left_clip_id="a", right_clip_id="b",
                kind="", duration_seconds=1.0,
            )

    def test_transition_set_error_includes_cross_fade(self) -> None:
        """Error message must list 'cross-fade' as a valid option."""
        with self.assertRaises(TimelineEventSchemaError) as ctx:
            TransitionSetPayload(
                left_clip_id="a", right_clip_id="b",
                kind="wipe", duration_seconds=1.0,
            )
        self.assertIn("cross-fade", str(ctx.exception),
                      "Transition validation error must mention 'cross-fade'")


# ============================================================================
# Projection boundary tests — registry-backed track kind validation
# ============================================================================


class ProjectionBoundaryKindTest(unittest.TestCase):
    """Projection boundary validates track kinds through the registry."""

    def test_valid_track_kinds_pass_boundary_validation(self) -> None:
        from astrid.core.timeline.projection import _validate_projected_timeline_boundary
        state = {
            "tracks": [
                {"id": "t1", "kind": "visual", "label": "Visual Track"},
                {"id": "t2", "kind": "audio", "label": "Audio Track"},
            ],
            "clips": [],
        }
        result = _validate_projected_timeline_boundary(state)
        self.assertIsInstance(result, dict)
        self.assertIn("tracks", result)

    def test_bogus_track_kind_rejected_by_boundary(self) -> None:
        from astrid.core.contracts.errors import AstridError
        from astrid.core.timeline.projection import (
            TimelineProjectionBoundaryError,
            _validate_projected_timeline_boundary,
        )
        state = {
            "tracks": [
                {"id": "t1", "kind": "caption", "label": "Bad Track"},
            ],
            "clips": [],
        }
        with self.assertRaises(TimelineProjectionBoundaryError) as ctx:
            _validate_projected_timeline_boundary(state)
        self.assertIsInstance(ctx.exception, AstridError)
        self.assertIn("track kind must be one of", str(ctx.exception))

    def test_bogus_track_kind_error_includes_options(self) -> None:
        from astrid.core.timeline.projection import _validate_projected_timeline_boundary
        state = {
            "tracks": [
                {"id": "t1", "kind": "nope_track", "label": "Nope"},
            ],
            "clips": [],
        }
        with self.assertRaises(ValueError) as ctx:
            _validate_projected_timeline_boundary(state)
        self.assertIn("track kind must be one of", str(ctx.exception))
        self.assertIn("visual", str(ctx.exception))
        self.assertIn("audio", str(ctx.exception))


# ============================================================================
# Doctor expectations — six v10 checks with a stable fail-closed JSON shape
# ============================================================================


class DoctorV10ChecksTest(unittest.TestCase):
    """The retired local doctor is replaced by the runtime gateway route."""

    def test_retired_local_doctor_module_is_absent(self) -> None:
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("astrid.core.doctor")

    def test_public_doctor_route_fails_closed_without_runtime(self) -> None:
        from astrid.core.gateway import dispatch

        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with patch.dict(
                os.environ,
                {
                    "BANODOCO_RUNTIME_ENDPOINT": "",
                    "BANODOCO_RUNTIME_DISCOVERY": str(Path(tmp) / "missing.json"),
                    "BANODOCO_RUNTIME_CREDENTIAL": str(Path(tmp) / "missing.token"),
                },
                clear=False,
            ), contextlib.redirect_stdout(output):
                code = dispatch._dispatch_doctor(["--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["state"], "unavailable")
        self.assertIn("banodoco-local up --profile astrid", payload["next_action"])
