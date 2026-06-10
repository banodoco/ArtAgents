"""Tests for ElementDefinition I/O wiring (T5).

Verifies that:
- ElementDefinition carries inputs/outputs tuples
- load_element_definition parses inputs/outputs with artifact_type support
- to_capability_handle propagates inputs/outputs (no hard-coded ())
- All 9 annotated rendering element manifests load correctly with artifact_type values
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from astrid.core.element.schema import (
    ElementDefinition,
    ElementValidationError,
    load_element_definition,
    to_capability_handle,
    validate_element_definition,
)
from astrid.core.contracts.schema import Port, Output


# Path to rendering pack elements
_RENDERING_ROOT = Path(__file__).resolve().parent.parent.parent / "astrid" / "packs" / "rendering" / "elements"


class ElementDefinitionIOFieldsTest(unittest.TestCase):
    """ElementDefinition now carries inputs/outputs tuples."""

    def test_default_inputs_outputs_are_empty(self) -> None:
        """An ElementDefinition constructed without inputs/outputs gets empty tuples."""
        from astrid.core.pack import ELEMENT_KIND_REGISTRY
        kind = ELEMENT_KIND_REGISTRY.normalize("effects")
        ed = ElementDefinition(
            id="test",
            kind=kind,
            root=Path("/tmp/test"),
            source="test",
            editable=False,
            priority=0,
            component=Path("/tmp/test/component.tsx"),
            schema={},
            defaults={},
        )
        self.assertEqual(ed.inputs, ())
        self.assertEqual(ed.outputs, ())

    def test_inputs_outputs_stored_as_tuples(self) -> None:
        """Inputs/outputs are stored as tuples of Port/Output."""
        from astrid.core.pack import ELEMENT_KIND_REGISTRY
        kind = ELEMENT_KIND_REGISTRY.normalize("effects")
        p = Port(name="clip", type="clip", artifact_type="clip/visual")
        o = Output(name="clip", type="clip", artifact_type="clip/visual")
        ed = ElementDefinition(
            id="test",
            kind=kind,
            root=Path("/tmp/test"),
            source="test",
            editable=False,
            priority=0,
            component=Path("/tmp/test/component.tsx"),
            schema={},
            defaults={},
            inputs=(p,),
            outputs=(o,),
        )
        self.assertEqual(len(ed.inputs), 1)
        self.assertIsInstance(ed.inputs[0], Port)
        self.assertEqual(ed.inputs[0].artifact_type, "clip/visual")
        self.assertEqual(len(ed.outputs), 1)
        self.assertIsInstance(ed.outputs[0], Output)
        self.assertEqual(ed.outputs[0].artifact_type, "clip/visual")


class ToCapabilityHandlePropagationTest(unittest.TestCase):
    """to_capability_handle propagates inputs/outputs from ElementDefinition."""

    def test_propagates_inputs_outputs(self) -> None:
        """The CapabilityHandle gets the element's inputs/outputs, not hard-coded ()."""
        from astrid.core.pack import ELEMENT_KIND_REGISTRY
        kind = ELEMENT_KIND_REGISTRY.normalize("effects")
        p = Port(name="clip", type="clip", artifact_type="clip/visual")
        o = Output(name="clip", type="clip", artifact_type="clip/visual")
        ed = ElementDefinition(
            id="test",
            kind=kind,
            root=Path("/tmp/test"),
            source="test",
            editable=False,
            priority=0,
            component=Path("/tmp/test/component.tsx"),
            schema={},
            defaults={},
            inputs=(p,),
            outputs=(o,),
        )
        handle = to_capability_handle(ed)
        self.assertEqual(len(handle.inputs), 1)
        self.assertEqual(handle.inputs[0].artifact_type, "clip/visual")
        self.assertEqual(len(handle.outputs), 1)
        self.assertEqual(handle.outputs[0].artifact_type, "clip/visual")

    def test_empty_inputs_outputs_propagated(self) -> None:
        """Empty inputs/outputs should not become None."""
        from astrid.core.pack import ELEMENT_KIND_REGISTRY
        kind = ELEMENT_KIND_REGISTRY.normalize("effects")
        ed = ElementDefinition(
            id="test",
            kind=kind,
            root=Path("/tmp/test"),
            source="test",
            editable=False,
            priority=0,
            component=Path("/tmp/test/component.tsx"),
            schema={},
            defaults={},
        )
        handle = to_capability_handle(ed)
        self.assertEqual(handle.inputs, ())
        self.assertEqual(handle.outputs, ())


class ManifestLoadIOTest(unittest.TestCase):
    """Loading element manifests parses inputs/outputs with artifact_type."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.rendering_root = _RENDERING_ROOT

    def _load_element(self, kind: str, element_id: str) -> ElementDefinition:
        root = self.rendering_root / kind / element_id
        return load_element_definition(
            root=root,
            kind=kind,
            source="pack:rendering",
            editable=False,
            priority=0,
        )

    # --- Animations (consume + produce clip/visual) ---

    def test_animation_fade_up_io(self) -> None:
        ed = self._load_element("animations", "fade-up")
        self.assertEqual(len(ed.inputs), 1)
        self.assertEqual(ed.inputs[0].name, "clip")
        self.assertEqual(ed.inputs[0].artifact_type, "clip/visual")
        self.assertTrue(ed.inputs[0].required)
        self.assertEqual(len(ed.outputs), 1)
        self.assertEqual(ed.outputs[0].name, "clip")
        self.assertEqual(ed.outputs[0].artifact_type, "clip/visual")

    def test_animation_fade_io(self) -> None:
        ed = self._load_element("animations", "fade")
        self.assertEqual(len(ed.inputs), 1)
        self.assertEqual(ed.inputs[0].name, "clip")
        self.assertEqual(ed.inputs[0].artifact_type, "clip/visual")
        self.assertEqual(len(ed.outputs), 1)
        self.assertEqual(ed.outputs[0].artifact_type, "clip/visual")

    def test_animation_scale_in_io(self) -> None:
        ed = self._load_element("animations", "scale-in")
        self.assertEqual(len(ed.inputs), 1)
        self.assertEqual(ed.inputs[0].artifact_type, "clip/visual")
        self.assertEqual(len(ed.outputs), 1)
        self.assertEqual(ed.outputs[0].artifact_type, "clip/visual")

    def test_animation_slide_left_io(self) -> None:
        ed = self._load_element("animations", "slide-left")
        self.assertEqual(len(ed.inputs), 1)
        self.assertEqual(ed.inputs[0].artifact_type, "clip/visual")
        self.assertEqual(len(ed.outputs), 1)
        self.assertEqual(ed.outputs[0].artifact_type, "clip/visual")

    def test_animation_slide_up_io(self) -> None:
        ed = self._load_element("animations", "slide-up")
        self.assertEqual(len(ed.inputs), 1)
        self.assertEqual(ed.inputs[0].artifact_type, "clip/visual")
        self.assertEqual(len(ed.outputs), 1)
        self.assertEqual(ed.outputs[0].artifact_type, "clip/visual")

    def test_animation_type_on_io(self) -> None:
        ed = self._load_element("animations", "type-on")
        self.assertEqual(len(ed.inputs), 1)
        self.assertEqual(ed.inputs[0].artifact_type, "clip/visual")
        self.assertEqual(len(ed.outputs), 1)
        self.assertEqual(ed.outputs[0].artifact_type, "clip/visual")

    # --- Effects (produce clip/visual, no input clip) ---

    def test_effect_text_card_io(self) -> None:
        ed = self._load_element("effects", "text-card")
        # text-card has no inputs
        self.assertEqual(len(ed.inputs), 0)
        self.assertEqual(len(ed.outputs), 1)
        self.assertEqual(ed.outputs[0].name, "clip")
        self.assertEqual(ed.outputs[0].artifact_type, "clip/visual")

    # --- Transitions (consume two clips, produce one) ---

    def test_transition_cross_fade_io(self) -> None:
        ed = self._load_element("transitions", "cross-fade")
        self.assertEqual(len(ed.inputs), 2)
        self.assertEqual(ed.inputs[0].name, "from_clip")
        self.assertEqual(ed.inputs[0].artifact_type, "clip/visual")
        self.assertEqual(ed.inputs[1].name, "to_clip")
        self.assertEqual(ed.inputs[1].artifact_type, "clip/visual")
        self.assertEqual(len(ed.outputs), 1)
        self.assertEqual(ed.outputs[0].artifact_type, "clip/visual")

    def test_transition_fade_io(self) -> None:
        ed = self._load_element("transitions", "fade")
        self.assertEqual(len(ed.inputs), 2)
        self.assertEqual(ed.inputs[0].artifact_type, "clip/visual")
        self.assertEqual(ed.inputs[1].artifact_type, "clip/visual")
        self.assertEqual(len(ed.outputs), 1)
        self.assertEqual(ed.outputs[0].artifact_type, "clip/visual")


class RuntimeAdapterComponentOptionalTest(unittest.TestCase):
    """When runtime.adapter is declared, component.tsx is optional."""

    def setUp(self) -> None:
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _write_manifest(self, element_id: str, extra: dict[str, Any] | None = None) -> Path:
        import json
        payload: dict[str, Any] = {
            "schema_version": 1,
            "id": element_id,
            "kind": "effects",
            "pack_id": "test",
            "metadata": {},
            "schema": {},
            "defaults": {},
        }
        if extra:
            payload.update(extra)
        manifest_path = self.tmp / element_id / "element.yaml"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(payload))
        return manifest_path.parent

    def test_adapter_makes_component_optional(self) -> None:
        """Manifest with runtime.adapter loads OK even without component.tsx."""
        root = self._write_manifest("adapter-test", {"runtime": {"adapter": "remotion"}})
        ed = load_element_definition(
            root=root,
            kind="effects",
            source="test",
            editable=False,
            priority=0,
        )
        self.assertEqual(ed.runtime.get("adapter"), "remotion")
        # component path is still resolved even if the file doesn't exist
        self.assertEqual(ed.component.name, "component.tsx")

    def test_no_adapter_still_requires_component(self) -> None:
        """Without runtime.adapter, missing component.tsx still raises."""
        root = self._write_manifest("no-adapter-test")
        with self.assertRaises(ElementValidationError) as ctx:
            load_element_definition(
                root=root,
                kind="effects",
                source="test",
                editable=False,
                priority=0,
            )
        self.assertIn("missing component.tsx", str(ctx.exception))

    def test_runtime_not_dict_still_requires_component(self) -> None:
        """runtime: null or non-dict still requires component.tsx."""
        root = self._write_manifest("bad-runtime-test", {"runtime": None})
        with self.assertRaises(ElementValidationError) as ctx:
            load_element_definition(
                root=root,
                kind="effects",
                source="test",
                editable=False,
                priority=0,
            )
        self.assertIn("missing component.tsx", str(ctx.exception))

    def test_adapter_empty_string_still_requires_component(self) -> None:
        """runtime.adapter: '' (empty string) should still require component.tsx."""
        root = self._write_manifest("empty-adapter-test", {"runtime": {"adapter": ""}})
        with self.assertRaises(ElementValidationError) as ctx:
            load_element_definition(
                root=root,
                kind="effects",
                source="test",
                editable=False,
                priority=0,
            )
        # empty adapter is falsy, so component.tsx is still required
        self.assertIn("missing component.tsx", str(ctx.exception))

    def test_validate_definition_adapter_optional(self) -> None:
        """validate_element_definition also allows missing component.tsx with adapter."""
        from astrid.core.pack import ELEMENT_KIND_REGISTRY
        kind = ELEMENT_KIND_REGISTRY.normalize("effects")
        root = self.tmp / "validate-test"
        root.mkdir(parents=True, exist_ok=True)
        (root / "element.yaml").write_text("id: validate-test\nkind: effects\npack_id: test\nmetadata: {}\nschema: {}\ndefaults: {}\nruntime:\n  adapter: remotion\n")
        ed = ElementDefinition(
            id="validate-test",
            kind=kind,
            root=root.resolve(),
            source="test",
            editable=False,
            priority=0,
            component=(root / "component.tsx").resolve(),
            schema={},
            defaults={},
            runtime={"adapter": "remotion"},
        )
        # should not raise
        validated = validate_element_definition(ed)
        self.assertEqual(validated.runtime.get("adapter"), "remotion")


if __name__ == "__main__":
    unittest.main()
