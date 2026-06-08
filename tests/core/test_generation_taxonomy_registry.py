from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.generation.features import (
    BUILTIN_GENERATION_BACKEND_IDS,
    CANONICAL_IMAGE_MODES,
    CANONICAL_VIDEO_MODES,
    GENERATION_TAXONOMY,
    IMAGE_FEATURES,
    VIDEO_FEATURES,
    GenerationBackendIdDescriptor,
    GenerationFeatureDescriptor,
    GenerationModeDescriptor,
    GenerationTaxonomyRegistry,
    load_default_generation_taxonomy_registry,
)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_builtin_generation_taxonomy_preserves_existing_constants() -> None:
    assert GENERATION_TAXONOMY.feature_ids() == VIDEO_FEATURES
    assert GENERATION_TAXONOMY.mode_ids("image") == CANONICAL_IMAGE_MODES
    assert GENERATION_TAXONOMY.mode_ids("video") == CANONICAL_VIDEO_MODES
    assert GENERATION_TAXONOMY.backend_ids() == BUILTIN_GENERATION_BACKEND_IDS
    assert set(IMAGE_FEATURES).issubset(set(GENERATION_TAXONOMY.feature_ids()))


def test_registry_accepts_pack_like_feature_mode_and_backend_ids() -> None:
    registry = GenerationTaxonomyRegistry(
        feature_descriptors=(GenerationFeatureDescriptor(id="mask_ref"),),
        mode_descriptors=(GenerationModeDescriptor(id="storyboard"),),
        backend_descriptors=(GenerationBackendIdDescriptor(id="studio"),),
    )

    assert "mask_ref" in registry.feature_ids()
    assert "storyboard" in registry.mode_ids("image")
    assert "storyboard" in registry.mode_ids("video")
    assert "studio" in registry.backend_ids()
    assert registry.require_feature("mask_ref", path="supports[0]") == "mask_ref"
    assert registry.require_mode("image", "storyboard", path="modes['storyboard']") == "storyboard"


def test_registry_rejects_duplicate_ids_within_each_taxonomy() -> None:
    with pytest.raises(ValueError, match="duplicate generation feature"):
        GenerationTaxonomyRegistry(
            feature_descriptors=(GenerationFeatureDescriptor(id="prompt"),)
        )
    with pytest.raises(ValueError, match="duplicate generation mode"):
        GenerationTaxonomyRegistry(
            mode_descriptors=(GenerationModeDescriptor(id="t2i"),)
        )
    with pytest.raises(ValueError, match="duplicate generation backend id"):
        GenerationTaxonomyRegistry(
            backend_descriptors=(GenerationBackendIdDescriptor(id="local"),)
        )


def test_load_default_generation_taxonomy_registry_adds_pack_declared_ids(
    tmp_path: Path,
) -> None:
    extra_root = tmp_path / "extra-packs"
    pack_root = extra_root / "vendor_pack"
    _write(
        pack_root / "pack.yaml",
        """schema_version: 1
id: vendor_pack
name: Vendor Pack
version: 0.1.0
extensions:
  generation:
    features:
      - id: mask_ref
    modes:
      - id: storyboard
    backends:
      - id: studio
        module: vendor.backend
        class: StudioBackend
""",
    )

    registry = load_default_generation_taxonomy_registry(
        project_root=tmp_path,
        extra_pack_roots=(str(extra_root),),
        include_installed=False,
    )

    assert "mask_ref" in registry.feature_ids()
    assert "storyboard" in registry.mode_ids("image")
    assert "storyboard" in registry.mode_ids("video")
    assert "studio" in registry.backend_ids()
