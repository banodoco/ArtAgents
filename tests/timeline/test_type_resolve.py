"""Tests for T6 type-resolution helper (resolve_clip_to_artifact_type).

SC6 coverage:
- 'text-card'  → clip/visual  (registered effect, annotated)
- 'fade-up'    → clip/visual  (registered animation, annotated)
- 'cross-fade' → clip/visual  (registered transition, annotated)
- 'nonexistent-clip' → None  (unregistered — opaque fallthrough)
- 'media'      → None         (clip kind, not an element id)
- theme-scoped lookup: theme parameter is forwarded to list_element_ids
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from astrid.core.contracts.artifact_types import ARTIFACT_TYPE_REGISTRY
from astrid.core.element import catalog as _catalog
from astrid.core.element.registry import load_default_registry
from astrid.core.timeline.validators._type_resolve import (
    is_visual_clip_element,
    resolve_clip_to_artifact_type,
)


def _build_registry():
    return load_default_registry()


class ResolveClipToArtifactTypeTest(unittest.TestCase):
    """resolve_clip_to_artifact_type returns correct artifact_type or None."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = _build_registry()
        cls.artifact_registry = ARTIFACT_TYPE_REGISTRY

    def _resolve(self, clip_type: str, theme: str | None = None) -> str | None:
        return resolve_clip_to_artifact_type(
            clip_type, theme, self.registry, self.artifact_registry
        )

    # --- Annotated elements resolve to clip/visual ---

    def test_text_card_resolves_to_clip_visual(self) -> None:
        """text-card is a registered effect with a clip/visual output."""
        self.assertEqual(self._resolve("text-card"), "clip/visual")

    def test_fade_up_resolves_to_clip_visual(self) -> None:
        """fade-up is a registered animation with a clip/visual output."""
        self.assertEqual(self._resolve("fade-up"), "clip/visual")

    def test_cross_fade_resolves_to_clip_visual(self) -> None:
        """cross-fade is a registered transition with a clip/visual output."""
        self.assertEqual(self._resolve("cross-fade"), "clip/visual")

    # --- Unresolved cases return None ---

    def test_nonexistent_returns_none(self) -> None:
        """An unknown clip_type string returns None (opaque fallthrough)."""
        self.assertIsNone(self._resolve("nonexistent-clip"))

    def test_media_clip_kind_returns_none(self) -> None:
        """'media' is a timeline clip kind, not an element id — returns None."""
        self.assertIsNone(self._resolve("media"))

    # --- Scan order: effects first ---

    def test_effects_scanned_before_animations(self) -> None:
        """effects kind is checked before animations in the scan order."""
        from astrid.core.timeline.validators._type_resolve import _ELEMENT_KIND_SCAN_ORDER
        self.assertEqual(_ELEMENT_KIND_SCAN_ORDER[0], "effects")
        self.assertEqual(_ELEMENT_KIND_SCAN_ORDER[1], "animations")
        self.assertEqual(_ELEMENT_KIND_SCAN_ORDER[2], "transitions")

    # --- Theme parameter passthrough ---

    def test_theme_parameter_forwarded_to_catalog(self) -> None:
        """theme is forwarded to list_element_ids for each kind scanned."""
        observed_themes: list[str | None] = []
        orig = _catalog.list_element_ids

        def tracking_list(kind, theme=None, **kwargs):
            observed_themes.append(theme)
            return orig(kind, theme=theme, **kwargs)

        with patch.object(_catalog, "list_element_ids", side_effect=tracking_list):
            result = resolve_clip_to_artifact_type(
                "fade-up", "test-theme-sentinel", self.registry, self.artifact_registry
            )

        self.assertIn("test-theme-sentinel", observed_themes)
        # fade-up is in the rendering pack (always available), so still resolves
        self.assertEqual(result, "clip/visual")


class IsVisualClipElementTest(unittest.TestCase):
    """is_visual_clip_element convenience wrapper."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = _build_registry()
        cls.artifact_registry = ARTIFACT_TYPE_REGISTRY

    def test_true_for_clip_visual_elements(self) -> None:
        self.assertTrue(
            is_visual_clip_element("text-card", None, self.registry, self.artifact_registry)
        )
        self.assertTrue(
            is_visual_clip_element("fade-up", None, self.registry, self.artifact_registry)
        )
        self.assertTrue(
            is_visual_clip_element("cross-fade", None, self.registry, self.artifact_registry)
        )

    def test_false_for_unknown(self) -> None:
        self.assertFalse(
            is_visual_clip_element("nonexistent", None, self.registry, self.artifact_registry)
        )

    def test_false_for_media_kind(self) -> None:
        self.assertFalse(
            is_visual_clip_element("media", None, self.registry, self.artifact_registry)
        )


if __name__ == "__main__":
    unittest.main()
