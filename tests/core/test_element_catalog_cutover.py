"""Regression coverage for the generated element catalog cutover."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from astrid.core.element import catalog
from astrid.core.element.registry import ElementRegistry


class ElementCatalogCutoverTest(unittest.TestCase):
    def test_workspace_tree_is_not_registered_as_an_element_source(self) -> None:
        """The legacy workspace tree must not regain catalog precedence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            legacy_element = Path(temp_dir) / "effects" / "legacy-only"
            legacy_element.mkdir(parents=True)
            (legacy_element / "component.tsx").write_text(
                "export default function LegacyOnly() { return null; }\n",
                encoding="utf-8",
            )
            (legacy_element / "element.yaml").write_text(
                json.dumps(
                    {
                        "id": "legacy-only",
                        "kind": "effect",
                        "schema": {"type": "object"},
                        "defaults": {},
                    }
                ),
                encoding="utf-8",
            )

            catalog._clear_registry_cache()
            try:
                with (
                    mock.patch.object(catalog, "WORKSPACE_ROOT", Path(temp_dir)),
                    mock.patch.object(catalog, "load_default_registry", return_value=ElementRegistry()),
                ):
                    registry = catalog._registry()
            finally:
                catalog._clear_registry_cache()

        self.assertNotIn("legacy-only", catalog.list_effect_ids())
        self.assertNotIn(
            "legacy_workspace",
            {definition.source for definition in registry.list()},
        )


if __name__ == "__main__":
    unittest.main()
