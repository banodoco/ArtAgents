"""Pack-scanning factory functions for the generation taxonomy registry.

The taxonomy classes and built-in constants now live in
``astrid.core.model_catalog.taxonomy`` (below ``generation``), where the model
registry validates against them. This module keeps the pack-scanning factory
functions that build a populated :class:`GenerationTaxonomyRegistry` from
``pack.extensions.generation`` metadata — those legitimately depend on the
pack/generation runtime.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.model_catalog.taxonomy import (
    GenerationBackendIdDescriptor,
    GenerationFeatureDescriptor,
    GenerationModeDescriptor,
    GenerationTaxonomyRegistry,
)
from astrid.core.pack import discover_packs
from astrid.core.pack.discovery import discover_pack_metadata

if TYPE_CHECKING:
    from astrid.core.pack import PackDefinition


def feature_descriptors_from_pack(pack: PackDefinition) -> tuple[GenerationFeatureDescriptor, ...]:
    generation = pack.extensions.get("generation")
    if not isinstance(generation, dict):
        return ()
    features = generation.get("features")
    if not isinstance(features, list):
        return ()
    return tuple(
        GenerationFeatureDescriptor(
            id=str(feature["id"]),
            label=str(feature.get("label", "")),
            description=str(feature.get("description", "")),
        )
        for feature in features
        if isinstance(feature, dict)
    )


def mode_descriptors_from_pack(pack: PackDefinition) -> tuple[GenerationModeDescriptor, ...]:
    generation = pack.extensions.get("generation")
    if not isinstance(generation, dict):
        return ()
    modes = generation.get("modes")
    if not isinstance(modes, list):
        return ()
    return tuple(
        GenerationModeDescriptor(
            id=str(mode["id"]),
            label=str(mode.get("label", "")),
            description=str(mode.get("description", "")),
        )
        for mode in modes
        if isinstance(mode, dict)
    )


def backend_descriptors_from_pack(pack: PackDefinition) -> tuple[GenerationBackendIdDescriptor, ...]:
    generation = pack.extensions.get("generation")
    if not isinstance(generation, dict):
        return ()
    backends = generation.get("backends")
    if not isinstance(backends, list):
        return ()
    return tuple(
        GenerationBackendIdDescriptor(
            id=str(backend["id"]),
            label=str(backend.get("label", "")),
        )
        for backend in backends
        if isinstance(backend, dict)
    )


def load_default_generation_taxonomy_registry(
    *,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> GenerationTaxonomyRegistry:
    feature_descriptors: list[GenerationFeatureDescriptor] = []
    mode_descriptors: list[GenerationModeDescriptor] = []
    backend_descriptors: list[GenerationBackendIdDescriptor] = []
    for discovered_pack in discover_pack_metadata(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        discover_packs_fn=discover_packs,
    ):
        feature_descriptors.extend(feature_descriptors_from_pack(discovered_pack.pack))
        mode_descriptors.extend(mode_descriptors_from_pack(discovered_pack.pack))
        backend_descriptors.extend(backend_descriptors_from_pack(discovered_pack.pack))
    return GenerationTaxonomyRegistry(
        feature_descriptors=feature_descriptors,
        mode_descriptors=mode_descriptors,
        backend_descriptors=backend_descriptors,
    )
