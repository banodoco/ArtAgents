"""Registry loading, discovery metadata, and capability resolution helpers.

Re-exports discovery infrastructure from ``astrid.sdk_discovery`` and provides
thin public wrappers (``discover``, ``get_capability``) plus private registry
loader seams needed by ``astrid.sdk_invocation`` and tests.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from astrid.sdk_discovery import _apply_pack_permission_ids as _sdk_apply_pack_permission_ids
from astrid.sdk_discovery import _build_discovery_metadata as _sdk_build_discovery_metadata
from astrid.sdk_discovery import _candidate_label as _sdk_candidate_label
from astrid.sdk_discovery import _capability_from_element as _sdk_capability_from_element
from astrid.sdk_discovery import _capability_from_executor as _sdk_capability_from_executor
from astrid.sdk_discovery import _capability_from_orchestrator as _sdk_capability_from_orchestrator
from astrid.sdk_discovery import _discover_pack_inventory as _sdk_discover_pack_inventory
from astrid.sdk_discovery import _element_kind_record as _sdk_element_kind_record
from astrid.sdk_discovery import _format_candidates as _sdk_format_candidates
from astrid.sdk_discovery import _generation_backend_record as _sdk_generation_backend_record
from astrid.sdk_discovery import _generation_feature_record as _sdk_generation_feature_record
from astrid.sdk_discovery import _generation_mode_record as _sdk_generation_mode_record
from astrid.sdk_discovery import _is_qualified_capability_id as _sdk_is_qualified_capability_id
from astrid.sdk_discovery import _load_element_registry as _sdk_load_element_registry
from astrid.sdk_discovery import _load_executor_registry as _sdk_load_executor_registry
from astrid.sdk_discovery import _load_orchestrator_registry as _sdk_load_orchestrator_registry
from astrid.sdk_discovery import _load_registries as _sdk_load_registries
from astrid.sdk_discovery import _pack_permission_ids_by_pack_id as _sdk_pack_permission_ids_by_pack_id
from astrid.sdk_discovery import _pack_record as _sdk_pack_record
from astrid.sdk_discovery import _registry_load_kwargs as _sdk_registry_load_kwargs
from astrid.sdk_discovery import _resolve_capability as _sdk_resolve_capability
from astrid.sdk_discovery import _resolve_capability_kindless as _sdk_resolve_capability_kindless
from astrid.sdk_discovery import _resolve_element_capability as _sdk_resolve_element_capability
from astrid.sdk_discovery import _resolve_executor_capability as _sdk_resolve_executor_capability
from astrid.sdk_discovery import _resolve_orchestrator_capability as _sdk_resolve_orchestrator_capability
from astrid.sdk_discovery import _split_canonical_element_id as _sdk_split_canonical_element_id

from .dto import Capability, CapabilityType, DiscoveryResult


# ---------------------------------------------------------------------------
# Private registry loader seams (used by sdk_invocation via _sdk_module())
# ---------------------------------------------------------------------------

def _registry_load_kwargs(
    *,
    project_root: str | Path | None,
    extra_pack_roots: tuple[str, ...],
    include_installed: bool,
) -> dict[str, Any]:
    return _sdk_registry_load_kwargs(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    )


def _load_executor_registry(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
) -> Any:
    return _sdk_load_executor_registry(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
    )


def _load_orchestrator_registry(
    *,
    executor_registry: Any | None = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
) -> Any:
    return _sdk_load_orchestrator_registry(
        executor_registry=executor_registry,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
    )


def _load_element_registry(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
) -> Any:
    return _sdk_load_element_registry(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
    )


def _load_registries(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
    include_elements: bool = False,
) -> tuple[Any, Any, Any | None]:
    # Resolve through the astrid.sdk module namespace so monkeypatch
    # seams applied to ``astrid.sdk._load_executor_registry`` etc. are
    # visible to callers that go through _sdk_module().
    _sdk = sys.modules["astrid.sdk"]
    executor_registry = _sdk._load_executor_registry(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
    )
    orchestrator_registry = _sdk._load_orchestrator_registry(
        executor_registry=executor_registry,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
    )
    element_registry = None
    if include_elements:
        element_registry = _sdk._load_element_registry(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
            active_theme=active_theme,
            include_missing_roots=include_missing_roots,
        )
    return executor_registry, orchestrator_registry, element_registry


def _discover_pack_inventory(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> tuple[Any, ...]:
    return _sdk_discover_pack_inventory(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    )


def _pack_record(discovered_pack: Any) -> dict[str, Any]:
    return _sdk_pack_record(discovered_pack)


def _pack_permission_ids_by_pack_id(discovered_packs: tuple[Any, ...]) -> dict[str, tuple[str, ...]]:
    return _sdk_pack_permission_ids_by_pack_id(discovered_packs)


def _apply_pack_permission_ids(
    capability: Capability,
    *,
    pack_permission_ids_by_pack_id: dict[str, tuple[str, ...]] | None = None,
) -> Capability:
    return _sdk_apply_pack_permission_ids(
        capability,
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _generation_backend_record(descriptor: Any) -> dict[str, Any]:
    return _sdk_generation_backend_record(descriptor)


def _element_kind_record(descriptor: Any) -> dict[str, Any]:
    return _sdk_element_kind_record(descriptor)


def _generation_feature_record(descriptor: Any) -> dict[str, Any]:
    return _sdk_generation_feature_record(descriptor)


def _generation_mode_record(descriptor: Any) -> dict[str, Any]:
    return _sdk_generation_mode_record(descriptor)


def _build_discovery_metadata(
    discovered_packs: tuple[Any, ...],
    *,
    element_registry: Any,
) -> tuple[
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    return _sdk_build_discovery_metadata(
        discovered_packs,
        element_registry=element_registry,
    )


def _capability_from_executor(
    definition: Any,
    registry: Any,
    *,
    requested_id: str | None = None,
    pack_permission_ids_by_pack_id: dict[str, tuple[str, ...]] | None = None,
) -> Capability:
    return _sdk_capability_from_executor(
        definition,
        registry,
        requested_id=requested_id,
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _capability_from_orchestrator(
    definition: Any,
    registry: Any,
    *,
    requested_id: str | None = None,
    pack_permission_ids_by_pack_id: dict[str, tuple[str, ...]] | None = None,
) -> Capability:
    return _sdk_capability_from_orchestrator(
        definition,
        registry,
        requested_id=requested_id,
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _capability_from_element(
    definition: Any,
    *,
    pack_permission_ids_by_pack_id: dict[str, tuple[str, ...]] | None = None,
) -> Capability:
    return _sdk_capability_from_element(
        definition,
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _is_qualified_capability_id(capability_id: str) -> bool:
    return _sdk_is_qualified_capability_id(capability_id)


def _split_canonical_element_id(
    capability_id: str,
    *,
    registry: Any,
    strict: bool = False,
) -> tuple[str, str] | None:
    return _sdk_split_canonical_element_id(
        capability_id,
        registry=registry,
        strict=strict,
    )


def _candidate_label(kind: str, capability_id: str) -> str:
    return _sdk_candidate_label(kind, capability_id)


def _format_candidates(candidates: tuple[str, ...]) -> str:
    return _sdk_format_candidates(candidates)


def _resolve_executor_capability(capability_id: str, registry: Any) -> Capability:
    return _sdk_resolve_executor_capability(capability_id, registry)


def _resolve_orchestrator_capability(capability_id: str, registry: Any) -> Capability:
    return _sdk_resolve_orchestrator_capability(capability_id, registry)


def _resolve_element_capability(
    capability_id: str,
    registry: Any,
    *,
    element_kind: str | None,
) -> Capability:
    return _sdk_resolve_element_capability(
        capability_id,
        registry,
        element_kind=element_kind,
    )


def _resolve_capability_kindless(
    capability_id: str,
    *,
    executor_registry: Any,
    orchestrator_registry: Any,
    element_registry: Any | None,
) -> Capability:
    return _sdk_resolve_capability_kindless(
        capability_id,
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
        element_registry=element_registry,
    )


def _resolve_capability(
    capability_id: str,
    *,
    kind: CapabilityType | None,
    element_kind: str | None,
    executor_registry: Any,
    orchestrator_registry: Any,
    element_registry: Any | None,
) -> Capability:
    return _sdk_resolve_capability(
        capability_id,
        kind=kind,
        element_kind=element_kind,
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
        element_registry=element_registry,
    )


# ---------------------------------------------------------------------------
# Public discovery entry points
# ---------------------------------------------------------------------------

# The real implementations live in astrid.sdk_invocation; they are thin
# wrappers that route through the monkeypatch seams above.  We import them
# here so the astrid.sdk package presents discover/get_capability alongside
# the private helpers.

from astrid.sdk_invocation import discover as _sdk_discover  # noqa: E402
from astrid.sdk_invocation import get_capability as _sdk_get_capability  # noqa: E402


def discover(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
) -> DiscoveryResult:
    return _sdk_discover(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
    )


def get_capability(
    capability_id: str,
    *,
    kind: CapabilityType | None = None,
    element_kind: str | None = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    include_elements: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
    _registries: tuple[Any, Any, Any | None] | None = None,
) -> Capability:
    return _sdk_get_capability(
        capability_id,
        kind=kind,
        element_kind=element_kind,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        include_elements=include_elements,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        _registries=_registries,
    )


__all__ = [
    "discover",
    "get_capability",
    "_apply_pack_permission_ids",
    "_build_discovery_metadata",
    "_candidate_label",
    "_capability_from_element",
    "_capability_from_executor",
    "_capability_from_orchestrator",
    "_discover_pack_inventory",
    "_element_kind_record",
    "_format_candidates",
    "_generation_backend_record",
    "_generation_feature_record",
    "_generation_mode_record",
    "_is_qualified_capability_id",
    "_load_element_registry",
    "_load_executor_registry",
    "_load_orchestrator_registry",
    "_load_registries",
    "_pack_permission_ids_by_pack_id",
    "_pack_record",
    "_registry_load_kwargs",
    "_resolve_capability",
    "_resolve_capability_kindless",
    "_resolve_element_capability",
    "_resolve_executor_capability",
    "_resolve_orchestrator_capability",
    "_split_canonical_element_id",
]
