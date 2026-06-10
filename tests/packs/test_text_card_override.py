"""Test the OverrideStore mechanism through the ElementRegistry for text-card.

Exercises the kernel OverrideStore to verify that a same-ID override pointing
at the rendering-pack canonical id causes the registry to return the
rendering-pack winner with ``local_edit_state == "clean"`` and
``override_target == "text-card"``.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from astrid.core.element.registry import ElementRegistry
from astrid.core.element.schema import (
    ElementDefinition,
    load_element_definition,
    to_capability_handle,
)
from astrid.core.pack import ELEMENT_KIND_REGISTRY
from astrid.core.pack.override import OverrideStore

RENDERING_PACK = Path(__file__).resolve().parent.parent.parent / "astrid" / "packs" / "rendering"


def _write_local_pack_element(
    pack_root: Path,
    kind: str,
    element_id: str,
    *,
    pack_id: str = "local",
    label: str = "Local Element",
) -> Path:
    """Create a minimal local pack element manifest on disk."""
    _KIND_SINGULAR = {
        "effects": "effect",
        "animations": "animation",
        "transitions": "transition",
        "widgets": "widget",
    }
    if not any((pack_root / name).exists() for name in ("pack.yaml", "pack.yml", "pack.json")):
        pack_root.mkdir(parents=True, exist_ok=True)
        (pack_root / "pack.yaml").write_text(
            f"id: {pack_id}\nname: {pack_id}\nversion: 0.1.0\n", encoding="utf-8"
        )
    element_root = pack_root / "elements" / kind / element_id
    element_root.mkdir(parents=True)
    (element_root / "element.yaml").write_text(
        json.dumps(
            {
                "id": element_id,
                "kind": _KIND_SINGULAR[kind],
                "pack_id": pack_id,
                "metadata": {"label": label},
                "schema": {"type": "object"},
                "defaults": {"content": ""},
                "dependencies": {
                    "js_packages": [],
                    "python_requirements": [],
                },
                "runtime": {"adapter": "remotion"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return element_root


def test_text_card_override_resolves_to_rendering_pack_winner() -> None:
    """OverrideStore same-ID override returns the rendering-pack canonical element."""
    with tempfile.TemporaryDirectory(prefix="text-card-override-") as tmp:
        project_root = Path(tmp)

        # -- 1. Create a synthetic local pack with effects/text-card ----------
        local_pack_root = project_root / "astrid" / "packs" / "local"
        _write_local_pack_element(
            local_pack_root,
            "effects",
            "text-card",
            pack_id="local",
            label="Local Text Card",
        )

        # -- 2. Configure the OverrideStore -----------------------------------
        override_store = OverrideStore(project_root=project_root)
        override_store.set_override("effects", "text-card", "text-card")

        # Sanity: the override store returns the expected mapping.
        assert override_store.resolve("effects", "text-card") == "text-card"
        serialized = override_store.list_overrides()
        assert serialized == {"effects": {"text-card": "text-card"}}

        # -- 3. Load the rendering-pack text-card ----------------------------
        rendering_root = RENDERING_PACK / "elements" / "effects" / "text-card"
        rendering_elem: ElementDefinition = load_element_definition(
            rendering_root,
            kind="effects",
            source="pack:rendering",
            editable=False,
            priority=30,
        )

        # -- 4. Load the local-pack text-card --------------------------------
        local_elem: ElementDefinition = load_element_definition(
            local_pack_root / "elements" / "effects" / "text-card",
            kind="effects",
            source="pack:local",
            editable=True,
            priority=10,
        )

        # -- 5. Build the registry with both elements ------------------------
        registry = ElementRegistry(
            override_store=override_store,
            element_kind_registry=ELEMENT_KIND_REGISTRY,
        )
        registry.register(rendering_elem)
        registry.register(local_elem)

        # -- 6. Resolve via get() — override should select rendering-pack -----
        result = registry.get("effects", "text-card")

        # -- 7. Assertions ---------------------------------------------------
        handle = to_capability_handle(result)

        # The override target is the rendering-pack canonical id.
        assert handle.override_target == "text-card", (
            f"Expected override_target='text-card', got {handle.override_target!r}"
        )

        # The rendering-pack element has no local edits.
        assert handle.local_edit_state == "clean", (
            f"Expected local_edit_state='clean', got {handle.local_edit_state!r}"
        )

        # The resolved definition comes from the rendering pack.
        assert result.metadata["pack_id"] == "rendering", (
            f"Expected pack_id='rendering', got {result.metadata.get('pack_id')!r}"
        )
        assert result.source == "pack:rendering", (
            f"Expected source='pack:rendering', got {result.source!r}"
        )
        assert result.editable is False
        assert result.metadata["label"] == "Text Card"

        # The local element is still registered; the override tips resolution
        # at get()-time without reordering internal conflict lists.
        conflicts = registry.conflicts()
        text_card_conflicts = [
            c for c in conflicts if c.kind == "effects" and c.id == "text-card"
        ]
        assert len(text_card_conflicts) == 1
        # Priority order still has local first; get() override is a
        # resolution-time annotation, not a storage reorder.
        assert text_card_conflicts[0].winner.source == "pack:local"
        assert text_card_conflicts[0].shadowed[0].source == "pack:rendering"


def test_text_card_override_without_conflict_is_noop() -> None:
    """When only one entry exists, a same-ID override adds no annotation."""
    with tempfile.TemporaryDirectory(prefix="text-card-override-noop-") as tmp:
        project_root = Path(tmp)

        override_store = OverrideStore(project_root=project_root)
        override_store.set_override("effects", "text-card", "text-card")

        rendering_root = RENDERING_PACK / "elements" / "effects" / "text-card"
        rendering_elem = load_element_definition(
            rendering_root,
            kind="effects",
            source="pack:rendering",
            editable=False,
            priority=30,
        )

        registry = ElementRegistry(
            override_store=override_store,
            element_kind_registry=ELEMENT_KIND_REGISTRY,
        )
        registry.register(rendering_elem)

        result = registry.get("effects", "text-card")
        handle = to_capability_handle(result)

        # No annotation because the override didn't change anything.
        assert handle.override_target is None
        assert handle.local_edit_state == "clean"
        assert result.source == "pack:rendering"


def test_text_card_override_cleanup() -> None:
    """Temporary directory is cleaned up; override store file does not leak."""
    tmp_path: str | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="text-card-override-cleanup-") as tmp:
            tmp_path = tmp
            project_root = Path(tmp)
            override_store = OverrideStore(project_root=project_root)
            override_store.set_override("effects", "text-card", "text-card")
            overrides_file = project_root / "astrid" / "packs" / "local" / ".overrides.json"
            assert overrides_file.is_file()
    finally:
        # After the context manager exits the directory should be gone.
        if tmp_path is not None:
            assert not Path(tmp_path).exists(), "Temp directory was not cleaned up"
