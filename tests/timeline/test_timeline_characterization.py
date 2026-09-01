"""Characterization test for ``astrid.core.timeline`` before structural migration.

Pins current behavior of:
1. The full public ``__all__`` import surface
2. ``Timeline.load`` → ``timeline_config_digest`` stability (golden hash)
3. ``Timeline.from_config(data).to_json_data()`` output shape and ``from``→``from_``
   serialization round-trip
4. ``Timeline`` domain class passthrough (unknown top-level fields survive)

This test MUST pass before any migration of implementation code into
``astrid/core/timeline/``. After the migration the same assertions must still
hold (the golden hash is the behavior contract, not a cosmetic choice).

DO NOT MODIFY the golden values or assertions in this file without a
corresponding plan change. They pin pre-migration behavior.
"""

from __future__ import annotations

import json
import tempfile
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PATH = REPO_ROOT / "examples" / "hype.timeline.full.json"


class TimelineAllSurfaceTest(unittest.TestCase):
    """Pin the exact ``__all__`` list of ``astrid.core.timeline``.

    The list is the public contract; removing or renaming any name is a
    breaking change. After structural migration the public surface must
    preserve every name.
    """

    # Golden: sorted __all__ as observed before the structural migration.
    GOLDEN_ALL = sorted(
        [
            "ARRANGEMENT_VERSION",
            "AnimationReference",
            "AnimationReferenceList",
            "AnimationReferenceObject",
            "Arrangement",
            "ArrangementAudioSource",
            "ArrangementClip",
            "ArrangementDurationError",
            "ArrangementTextOverlay",
            "ArrangementVisualRole",
            "ArrangementVisualSource",
            "AssetEntry",
            "AssetRegistry",
            "AssetRegistryEntry",
            "AudioBindingSource",
            "AudioBindingValue",
            "BUILTIN_CLIP_TYPES",
            "CARRY_FORWARD_SOURCE_FIELDS",
            "ClipClassifiedKind",
            "ClipContinuous",
            "ClipEntrance",
            "ClipExit",
            "ClipTransition",
            "ClipTransitionReference",
            "ClipType",
            "METADATA_VERSION",
            "POOL_VERSION",
            "ParameterDefinition",
            "ParameterOption",
            "ParameterType",
            "PipelineMetadata",
            "PipelineMetadataClipEntry",
            "PipelinePoolKind",
            "Pool",
            "PoolCategory",
            "PoolEntry",
            "PoolKind",
            "PoolScores",
            "SharedAssetEntry",
            "SharedTheme",
            "SharedThemeOverrides",
            "SharedTimelineClip",
            "SharedTimelineConfig",
            "SharedTimelineOutput",
            "SourceIds",
            "TextAlignment",
            "TextClipData",
            "Theme",
            "ThemeOverrides",
            "Timeline",
            "TimelineClip",
            "TimelineClipView",
            "TimelineConfig",
            "TimelineEffect",
            "TimelineOutput",
            "TimelineRenderView",
            "TrackBlendMode",
            "TrackDefinition",
            "TrackFit",
            "TrackKind",
            "_ASSET_ENTRY_ALLOWED",
            "_CLIP_ALLOWED",
            "_THEME_OVERRIDES_ALLOWED",
            "_TIMELINE_TOP_ALLOWED",
            "_TRACK_ALLOWED",
            "_animation_ids",
            "_animation_meta",
            "_normalize_clip_for_validation",
            "_transition_ids",
            "canonical_empty_timeline",
            "canonical_timeline_config",
            "is_all_generative_arrangement",
            "load_arrangement",
            "load_metadata",
            "load_pool",
            "load_registry",
            "load_timeline",
            "materialize_output",
            "merge_generation",
            "save_arrangement",
            "save_metadata",
            "save_pool",
            "save_registry",
            "save_timeline",
            "timeline_config_digest",
            "timeline_configs_equal",
            "validate_arrangement",
            "validate_arrangement_duration_window",
            "validate_metadata",
            "validate_pool",
            "validate_registry",
            "validate_timeline",
            "validate_timeline_config_for_container",
        ]
    )

    def test_all_exact_contents(self) -> None:
        """``__all__`` must match the pre-migration golden list exactly."""
        from astrid.core.timeline import __all__ as timeline_all

        self.assertEqual(sorted(timeline_all), self.GOLDEN_ALL)

    def test_every_all_name_is_importable(self) -> None:
        """Every name in ``__all__`` must resolve at import time."""
        import astrid.core.timeline as t

        for name in self.GOLDEN_ALL:
            with self.subTest(name=name):
                self.assertTrue(hasattr(t, name), f"missing {name}")

    def test_no_extra_public_attributes(self) -> None:
        """No public names exist beyond ``__all__`` (excluding dunders and
        internal submodule attributes loaded by the public surface).
        """
        import astrid.core.timeline as t

        public = {
            n
            for n in dir(t)
            if not n.startswith("_") or (
                n.startswith("__") and n.endswith("__")
            )
        }
        # dir() includes standard dunders plus __all__, __path__, and the
        # submodule attributes that get loaded when __init__.py does
        # ``from . import timeline_model`` / ``from .banodoco_composer``.
        # The ``annotations`` name comes from ``from __future__ import annotations``.
        allowed_extra = {
            "__all__",
            "__builtins__",
            "__cached__",
            "__doc__",
            "__file__",
            "__loader__",
            "__name__",
            "__package__",
            "__spec__",
            "__path__",
            # Internal submodules loaded by the public surface:
            "banodoco_composer",
            "banodoco_schema",
            "crud",
            "defaults",
            "events",
            "integrity",
            "kinds",
            "model",
            "paths",
            "projection",
            # __future__ import side-effect:
            "annotations",
        }
        allowed_extra.update(
            name
            for name, value in vars(t).items()
            if isinstance(value, types.ModuleType)
            and value.__name__.startswith(f"{t.__name__}.")
        )
        extra = public - set(self.GOLDEN_ALL) - allowed_extra
        self.assertEqual(
            extra,
            set(),
            f"Public names outside __all__: {extra}. "
            f"Add them to __all__ or remove them.",
        )


class TimelineDigestGoldenTest(unittest.TestCase):
    """Golden ``timeline_config_digest`` for the canonical hype fixture.

    The digest is a sha256 over the canonically-sorted, minified JSON of the
    validated timeline config. If the digest changes, something in the
    validate→canonicalize→serialize chain shifted.
    """

    # Golden: pre-migration digest computed from the fixture.
    # This hash pins the exact stable serialization contract.
    GOLDEN_DIGEST = "872b50fab9248ef3497490f88fdc772526c74a391c5286040367e25fada10f9a"

    def setUp(self) -> None:
        self.assertTrue(
            FIXTURE_PATH.is_file(),
            f"fixture missing: {FIXTURE_PATH}",
        )

    def test_digest_matches_golden(self) -> None:
        """The digest of the hype fixture must match the golden hash."""
        from astrid.core.timeline import timeline_config_digest

        config = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        actual = timeline_config_digest(config)
        self.assertEqual(
            actual,
            self.GOLDEN_DIGEST,
            "timeline_config_digest drifted from golden. "
            "If the fixture content changed, update GOLDEN_DIGEST. "
            "If only the serialization changed, investigate.",
        )

    def test_digest_is_stable(self) -> None:
        """Repeated digests of the same config must produce the same hash."""
        from astrid.core.timeline import timeline_config_digest

        config = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        first = timeline_config_digest(config)
        second = timeline_config_digest(config)
        self.assertEqual(first, second)

    def test_digest_is_deterministic_after_roundtrip(self) -> None:
        """load → save → load produces a stable (internally consistent) digest.

        The digest after a full round-trip may differ from the golden because
        ``to_config()`` returns the internal representation (with ``from_``
        keys) while the fixture uses ``from`` keys. However, repeated
        round-trips must produce the same digest.
        """
        from astrid.core.timeline import load_timeline, save_timeline, timeline_config_digest

        config = load_timeline(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "roundtrip.json"
            save_timeline(config, out)
            reloaded = load_timeline(out)
        digest_after_roundtrip = timeline_config_digest(reloaded)
        # Round-trip digest must be self-consistent (stable across repeated loads).
        with tempfile.TemporaryDirectory() as tmp2:
            out2 = Path(tmp2) / "roundtrip2.json"
            save_timeline(reloaded, out2)
            reloaded2 = load_timeline(out2)
        self.assertEqual(
            timeline_config_digest(reloaded2),
            digest_after_roundtrip,
            "Digest not stable across repeated load→save→load round-trips.",
        )


class TimelineFromConfigToJsonDataTest(unittest.TestCase):
    """Characterize ``Timeline.from_config(data).to_json_data()`` behavior.

    This exercises the direct domain-class chain without the
    ``load_timeline``/``save_timeline`` convenience functions.
    """

    def setUp(self) -> None:
        self.assertTrue(
            FIXTURE_PATH.is_file(),
            f"fixture missing: {FIXTURE_PATH}",
        )
        self.raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_from_config_to_json_data_is_valid(self) -> None:
        """``to_json_data()`` output must pass ``validate_timeline``."""
        from astrid.core.timeline import Timeline, validate_timeline

        tl = Timeline.from_config(self.raw)
        output = tl.to_json_data()
        # Should not raise
        validate_timeline(output)

    def test_from_config_to_json_data_preserves_top_level(self) -> None:
        """Top-level keys from the fixture survive the chain."""
        from astrid.core.timeline import Timeline

        tl = Timeline.from_config(self.raw)
        output = tl.to_json_data()

        for key in ("theme", "theme_overrides", "tracks", "clips"):
            self.assertIn(key, output, f"missing top-level key {key!r}")

    def test_from_config_to_json_data_preserves_clip_count(self) -> None:
        """The number of clips must not change."""
        from astrid.core.timeline import Timeline

        tl = Timeline.from_config(self.raw)
        output = tl.to_json_data()
        self.assertEqual(
            len(output.get("clips", [])),
            len(self.raw.get("clips", [])),
        )

    def test_from_config_to_json_data_unknown_field_survives(self) -> None:
        """Unknown top-level fields pass through ``to_json_data()``."""
        from astrid.core.timeline import Timeline

        sentinel = "_char_canary_v1"
        data = dict(self.raw)
        data[sentinel] = "keep me"
        tl = Timeline.from_config(data)
        output = tl.to_json_data()
        self.assertEqual(output.get(sentinel), "keep me")

    def test_from_config_to_json_data_converts_from_to_from_(self) -> None:
        """``to_json_data()`` must convert internal ``from_`` back to ``from``.

        The fixture stores ``from`` (JSON key). The domain class stores
        ``from_`` internally (Python attribute). ``to_json_data()`` must
        restore the wire key ``from``.
        """
        from astrid.core.timeline import Timeline

        tl = Timeline.from_config(self.raw)
        output = tl.to_json_data()

        clips = output.get("clips", [])
        for clip in clips:
            if isinstance(clip, dict) and "from_" in clip:
                self.fail(
                    f"to_json_data() leaked internal 'from_' key: {clip.get('id', '?')}"
                )
            if isinstance(clip, dict) and "from" in clip:
                # Expected — the wire key is restored
                pass

    def test_from_config_to_json_data_rounds_at_to_three_decimal_places(self) -> None:
        """Float ``at`` values must be rounded to 3 decimal places in output."""
        from astrid.core.timeline import Timeline

        # Use exact integer to avoid float-precision noise in the assertion.
        data = {
            "theme": "banodoco-default",
            "tracks": [{"id": "t", "kind": "visual", "label": "Test", "fit": "cover"}],
            "clips": [
                {
                    "id": "c",
                    "at": 1.23456789,
                    "track": "t",
                    "clipType": "text",
                    "text": {"content": "x", "fontSize": 24.0, "align": "left"},
                }
            ],
        }
        tl = Timeline.from_config(data)
        output = tl.to_json_data()
        clip = output["clips"][0]
        self.assertEqual(clip.get("at"), 1.235)

    def test_from_config_to_json_data_idempotent(self) -> None:
        """Two calls to ``to_json_data()`` produce equal output."""
        from astrid.core.timeline import Timeline

        tl = Timeline.from_config(self.raw)
        out1 = tl.to_json_data()
        out2 = tl.to_json_data()
        self.assertEqual(out1, out2)

    def test_to_config_matches_to_json_data_internals(self) -> None:
        """``to_config()`` preserves internal representation.

        ``to_config()`` is a deep copy of the raw stored data (with ``from_``
        keys). ``to_json_data()`` re-serializes. They should agree on all
        non-serialization-convention fields.
        """
        from astrid.core.timeline import Timeline

        tl = Timeline.from_config(self.raw)
        cfg = tl.to_config()
        jd = tl.to_json_data()

        # to_config keeps from_; to_json_data restores from.
        # Aside from that convention, the data should agree.
        for key in ("theme", "theme_overrides", "tracks"):
            self.assertEqual(cfg.get(key), jd.get(key), f"key {key!r} drifted")

        # Clip count must match
        self.assertEqual(len(cfg.get("clips", [])), len(jd.get("clips", [])))

    _TRACK_WITH_LABEL = {"id": "t", "kind": "visual", "label": "Test", "fit": "cover"}
    _TEXT_CLIP = {
        "id": "c",
        "at": 0.0,
        "track": "t",
        "clipType": "text",
        "text": {"content": "hi", "fontSize": 24.0, "align": "left"},
    }

    def test_for_render_sets_default_theme(self) -> None:
        """``for_render(default_theme=...)`` fills in a missing theme."""
        from astrid.core.timeline import Timeline

        data: dict = {
            "tracks": [dict(self._TRACK_WITH_LABEL)],
            "clips": [dict(self._TEXT_CLIP)],
        }
        tl = Timeline.from_config(data)
        rv = tl.for_render(default_theme="my-theme")
        self.assertEqual(rv.theme, "my-theme")
        self.assertEqual(rv.to_json_data().get("theme"), "my-theme")

    def test_for_render_rejects_empty_theme_slug(self) -> None:
        """``for_render`` must raise ValueError for an empty theme slug."""
        from astrid.core.timeline import Timeline

        tl = Timeline.from_config(
            {
                "theme": "banodoco-default",
                "tracks": [dict(self._TRACK_WITH_LABEL)],
                "clips": [dict(self._TEXT_CLIP)],
            }
        )
        with self.assertRaises(ValueError):
            tl.for_render(default_theme="")
        with self.assertRaises(ValueError):
            tl.for_render(default_theme=42)  # type: ignore[arg-type]


class TimelineClassifiedClipsTest(unittest.TestCase):
    """Characterize ``classified_clips`` behavior."""

    def setUp(self) -> None:
        self.assertTrue(
            FIXTURE_PATH.is_file(),
            f"fixture missing: {FIXTURE_PATH}",
        )
        self.raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_classified_clips_count_matches(self) -> None:
        """Every clip in the fixture produces a ``TimelineClipView``."""
        from astrid.core.timeline import Timeline

        tl = Timeline.from_config(self.raw)
        views = tl.classified_clips()
        self.assertEqual(len(views), len(self.raw.get("clips", [])))

    def test_classified_clips_kinds(self) -> None:
        """Known clip kinds classify correctly."""
        from astrid.core.timeline import ClipClassifiedKind, Timeline

        tl = Timeline.from_config(self.raw)
        views = tl.classified_clips()

        kinds = [v.classified_kind for v in views]
        # clip_manual_image → media: OPAQUE (no asset entry in fixture)
        # clip_cover_video → media: OPAQUE
        # clip_text → TEXT
        # clip_audio → media: OPAQUE
        # clip_text_card → text-card: OPAQUE (not recognized as text)
        self.assertIn(ClipClassifiedKind.TEXT, kinds)


class TimelineConvenienceFunctionsTest(unittest.TestCase):
    """Characterize load/save convenience functions."""

    def setUp(self) -> None:
        self.assertTrue(
            FIXTURE_PATH.is_file(),
            f"fixture missing: {FIXTURE_PATH}",
        )

    def test_load_timeline_returns_config(self) -> None:
        """``load_timeline`` returns a TimelineConfig (dict)."""
        from astrid.core.timeline import load_timeline

        config = load_timeline(FIXTURE_PATH)
        self.assertIsInstance(config, dict)
        self.assertIn("clips", config)
        self.assertIn("tracks", config)

    def test_load_timeline_raises_on_non_object(self) -> None:
        """``load_timeline`` raises on a JSON array."""
        from astrid.core.timeline import load_timeline

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "array.json"
            p.write_text("[1, 2, 3]", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_timeline(p)

    def test_timeline_configs_equal_same_config(self) -> None:
        """Identical configs are equal after canonicalization."""
        from astrid.core.timeline import load_timeline, timeline_configs_equal

        config = load_timeline(FIXTURE_PATH)
        self.assertTrue(timeline_configs_equal(config, config))

    def test_canonical_timeline_config_is_stable(self) -> None:
        """``canonical_timeline_config`` produces a stable ordered dict."""
        from astrid.core.timeline import canonical_timeline_config, load_timeline

        config = load_timeline(FIXTURE_PATH)
        c1 = canonical_timeline_config(config)
        c2 = canonical_timeline_config(config)
        self.assertEqual(c1, c2)
        self.assertEqual(json.dumps(c1, sort_keys=True), json.dumps(c2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
