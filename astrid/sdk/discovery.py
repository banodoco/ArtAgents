"""Registry loading, discovery metadata, and capability resolution helpers."""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from ._module import _sdk_module
from .exceptions import (
    CapabilityAmbiguousError,
    CapabilityNotFoundError,
    CapabilityValidationError,
)
from .results import Capability, CapabilityType, _json_safe_mapping


def _registry_load_kwargs(
    *,
    project_root: str | Path | None,
    extra_pack_roots: tuple[str, ...],
    include_installed: bool,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "extra_pack_roots": extra_pack_roots,
        "include_installed": include_installed,
    }
    if project_root is not None:
        kwargs["project_root"] = project_root
    return kwargs


def _load_executor_registry(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
) -> Any:
    from astrid.core.execution.executor.registry import load_default_registry

    return load_default_registry(
        banodoco_config=banodoco_config,
        **_registry_load_kwargs(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        ),
    )


def _load_orchestrator_registry(
    *,
    executor_registry: Any | None = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
) -> Any:
    from astrid.core.execution.orchestrator.registry import load_default_registry

    return load_default_registry(
        executor_registry=executor_registry,
        banodoco_config=banodoco_config,
        **_registry_load_kwargs(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        ),
    )


def _load_element_registry(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
) -> Any:
    from astrid.core.element.registry import load_default_registry

    return load_default_registry(
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        **_registry_load_kwargs(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        ),
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
    sdk_module = _sdk_module()
    executor_registry = sdk_module._load_executor_registry(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
    )
    orchestrator_registry = sdk_module._load_orchestrator_registry(
        executor_registry=executor_registry,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
    )
    element_registry = None
    if include_elements:
        element_registry = sdk_module._load_element_registry(
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
    from astrid.core.pack.discovery import discover_pack_metadata

    return discover_pack_metadata(
        **_registry_load_kwargs(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        ),
    )


def _pack_record(discovered_pack: Any) -> dict[str, Any]:
    payload = discovered_pack.pack.to_dict()
    from astrid.core.pack.validate import extract_trust_summary

    trust_summary = extract_trust_summary(discovered_pack.pack.root)
    if "permissions" in trust_summary:
        payload["permissions"] = trust_summary["permissions"]
    if "permission_ids" in trust_summary:
        payload["permission_ids"] = trust_summary["permission_ids"]
    if "trust" in trust_summary:
        payload["trust"] = trust_summary["trust"]
    payload["source_kind"] = discovered_pack.source_kind
    payload["priority_index"] = discovered_pack.priority_index
    return _json_safe_mapping(payload)


def _pack_permission_ids_by_pack_id(discovered_packs: tuple[Any, ...]) -> dict[str, tuple[str, ...]]:
    permission_ids_by_pack_id: dict[str, tuple[str, ...]] = {}
    for discovered_pack in discovered_packs:
        pack = getattr(discovered_pack, "pack", None)
        if pack is None:
            continue
        permissions = getattr(pack, "permissions", ())
        permission_ids_by_pack_id[pack.id] = tuple(permission.id for permission in permissions)
    return permission_ids_by_pack_id


def _apply_pack_permission_ids(
    capability: Capability,
    *,
    pack_permission_ids_by_pack_id: Mapping[str, tuple[str, ...]] | None = None,
) -> Capability:
    if not pack_permission_ids_by_pack_id:
        return capability
    permission_ids = pack_permission_ids_by_pack_id.get(capability.handle.pack_id, ())
    if not permission_ids:
        return capability
    if capability.handle.safety.permissions == permission_ids:
        return capability
    return replace(
        capability,
        handle=replace(
            capability.handle,
            safety=replace(capability.handle.safety, permissions=permission_ids),
        ),
    )


def _generation_backend_record(descriptor: Any) -> dict[str, Any]:
    return _json_safe_mapping(
        {
            "id": descriptor.backend_id,
            "label": descriptor.label,
            "module": descriptor.module,
            "class": descriptor.class_name,
            "init_kwargs": descriptor.init_kwargs,
        }
    )


def _element_kind_record(descriptor: Any) -> dict[str, Any]:
    return _json_safe_mapping(
        {
            "id": descriptor.id,
            "singular": descriptor.singular,
            "plural": descriptor.plural,
            "canonical_kind": descriptor.canonical_kind,
            "aliases": descriptor.aliases,
            "label": descriptor.label,
            "description": descriptor.description,
        }
    )


def _generation_feature_record(descriptor: Any) -> dict[str, Any]:
    return _json_safe_mapping(
        {
            "id": descriptor.id,
            "label": descriptor.label,
            "description": descriptor.description,
        }
    )


def _generation_mode_record(descriptor: Any) -> dict[str, Any]:
    return _json_safe_mapping(
        {
            "id": descriptor.id,
            "modalities": descriptor.modalities,
            "label": descriptor.label,
            "description": descriptor.description,
        }
    )


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
    from astrid.core.generation.backends.registry import (
        GenerationBackendRegistry,
        descriptors_from_pack,
    )
    from astrid.core.generation.features import (
        backend_descriptors_from_pack,
        feature_descriptors_from_pack,
        mode_descriptors_from_pack,
    )
    from astrid.core.model_catalog.taxonomy import GenerationTaxonomyRegistry

    packs = tuple(_pack_record(discovered_pack) for discovered_pack in discovered_packs)

    backend_registry = GenerationBackendRegistry(
        descriptors=tuple(
            descriptor
            for discovered_pack in discovered_packs
            for descriptor in descriptors_from_pack(discovered_pack.pack)
        )
    )
    taxonomy_registry = GenerationTaxonomyRegistry(
        feature_descriptors=tuple(
            descriptor
            for discovered_pack in discovered_packs
            for descriptor in feature_descriptors_from_pack(discovered_pack.pack)
        ),
        mode_descriptors=tuple(
            descriptor
            for discovered_pack in discovered_packs
            for descriptor in mode_descriptors_from_pack(discovered_pack.pack)
        ),
        backend_descriptors=tuple(
            descriptor
            for discovered_pack in discovered_packs
            for descriptor in backend_descriptors_from_pack(discovered_pack.pack)
        ),
    )

    generation_backends = tuple(
        _generation_backend_record(descriptor) for descriptor in backend_registry.descriptors()
    )
    element_kinds = tuple(
        _element_kind_record(descriptor)
        for descriptor in element_registry.element_kind_registry.descriptors()
    )
    generation_features = tuple(
        _generation_feature_record(descriptor) for descriptor in taxonomy_registry.feature_descriptors()
    )
    generation_modes = tuple(
        _generation_mode_record(descriptor) for descriptor in taxonomy_registry.mode_descriptors()
    )
    return (
        packs,
        generation_backends,
        element_kinds,
        generation_features,
        generation_modes,
    )


def _capability_from_definition(
    definition: Any,
    registry: Any,
    *,
    capability_type: str,
    requested_id: str | None = None,
    pack_permission_ids_by_pack_id: Mapping[str, tuple[str, ...]] | None = None,
) -> Capability:
    _schema_package = {
        "executor": "astrid.core.execution.executor",
        "orchestrator": "astrid.core.execution.orchestrator",
    }.get(capability_type, f"astrid.core.{capability_type}")
    schema_module_path = f"{_schema_package}.schema"
    to_capability_handle = importlib.import_module(schema_module_path).to_capability_handle

    resolved_alias = None
    deprecated = False
    deprecation_message = ""
    aliases = ()
    if registry.alias_resolver is not None:
        aliases = tuple(registry.alias_resolver.get_aliases_for(definition.id))
        if requested_id is not None and registry.alias_resolver.is_alias(requested_id):
            alias_record = registry.alias_resolver.get_record(requested_id)
            if alias_record is not None:
                resolved_alias = requested_id
                deprecated = alias_record.deprecated
                deprecation_message = alias_record.deprecation_message
    definition_mapping = _json_safe_mapping(definition.to_dict())
    return _apply_pack_permission_ids(
        Capability(
            id=definition.id,
            capability_type=capability_type,
            native_kind=definition.kind,
            handle=to_capability_handle(
                definition,
                aliases=aliases,
                resolved_alias=resolved_alias,
                deprecated=deprecated,
                deprecation_message=deprecation_message,
            ),
            inputs=tuple(definition.inputs),
            outputs=tuple(definition.outputs),
            schema=definition_mapping,
            defaults={},
            definition=definition_mapping,
        ),
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _capability_from_executor(
    definition: Any,
    registry: Any,
    *,
    requested_id: str | None = None,
    pack_permission_ids_by_pack_id: Mapping[str, tuple[str, ...]] | None = None,
) -> Capability:
    return _capability_from_definition(
        definition,
        registry,
        capability_type="executor",
        requested_id=requested_id,
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _capability_from_orchestrator(
    definition: Any,
    registry: Any,
    *,
    requested_id: str | None = None,
    pack_permission_ids_by_pack_id: Mapping[str, tuple[str, ...]] | None = None,
) -> Capability:
    return _capability_from_definition(
        definition,
        registry,
        capability_type="orchestrator",
        requested_id=requested_id,
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _capability_from_element(
    definition: Any,
    *,
    pack_permission_ids_by_pack_id: Mapping[str, tuple[str, ...]] | None = None,
) -> Capability:
    from astrid.core.element.schema import to_capability_handle

    return _apply_pack_permission_ids(
        Capability(
            id=f"{definition.kind}/{definition.id}",
            capability_type="element",
            native_kind=definition.kind,
            handle=to_capability_handle(definition),
            schema=_json_safe_mapping(definition.schema),
            defaults=_json_safe_mapping(definition.defaults),
            definition=_json_safe_mapping(definition.to_dict()),
        ),
        pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
    )


def _is_qualified_capability_id(capability_id: str) -> bool:
    return "." in capability_id


def _split_canonical_element_id(
    capability_id: str,
    *,
    registry: Any,
    strict: bool = False,
) -> tuple[str, str] | None:
    kind, sep, local_id = capability_id.partition("/")
    if not (sep and local_id):
        return None
    try:
        canonical_kind = registry.element_kind_registry.normalize(kind)
    except ValueError as exc:
        if strict:
            raise CapabilityValidationError(str(exc)) from exc
        return None
    return canonical_kind, local_id


def _candidate_label(kind: str, capability_id: str) -> str:
    return f"{kind}:{capability_id}"


def _format_candidates(candidates: tuple[str, ...]) -> str:
    return ", ".join(sorted(candidates))


def _resolve_typed_capability(
    capability_id: str, registry: Any, *, capability_type: str
) -> Capability:
    resolver = registry.alias_resolver
    alias_requested = resolver is not None and resolver.is_alias(capability_id)
    if alias_requested or _is_qualified_capability_id(capability_id):
        try:
            definition = registry.get(capability_id)
        except KeyError as exc:
            raise CapabilityNotFoundError(
                f"unknown {capability_type} {capability_id!r}"
            ) from exc
        return _capability_from_definition(
            definition, registry, capability_type=capability_type, requested_id=capability_id,
        )

    matches = [
        definition
        for definition in registry.list()
        if definition.id.rsplit(".", 1)[-1] == capability_id
    ]
    if not matches:
        raise CapabilityNotFoundError(f"unknown {capability_type} {capability_id!r}")
    if len(matches) > 1:
        candidates = tuple(
            _candidate_label(capability_type, definition.id) for definition in matches
        )
        raise CapabilityAmbiguousError(
            f"ambiguous {capability_type} {capability_id!r};"
            f" candidates: {_format_candidates(candidates)}"
        )
    return _capability_from_definition(
        matches[0], registry, capability_type=capability_type, requested_id=capability_id,
    )


def _resolve_executor_capability(capability_id: str, registry: Any) -> Capability:
    return _resolve_typed_capability(
        capability_id, registry, capability_type="executor"
    )


def _resolve_orchestrator_capability(capability_id: str, registry: Any) -> Capability:
    return _resolve_typed_capability(
        capability_id, registry, capability_type="orchestrator"
    )


def _resolve_element_capability(
    capability_id: str,
    registry: Any,
    *,
    element_kind: str | None,
) -> Capability:
    lookup_id = capability_id
    if element_kind is not None:
        try:
            normalized_kind = registry.element_kind_registry.normalize(element_kind)
        except ValueError as exc:
            raise CapabilityValidationError(str(exc)) from exc
        canonical = _split_canonical_element_id(capability_id, registry=registry, strict=True)
        if canonical is not None:
            requested_kind, requested_local_id = canonical
            if requested_kind != normalized_kind:
                raise CapabilityNotFoundError(
                    f"unknown element {capability_id!r} for explicit element_kind={normalized_kind!r}"
                )
            lookup_id = requested_local_id
        try:
            definition = registry.get(normalized_kind, lookup_id)
        except KeyError as exc:
            raise CapabilityNotFoundError(
                f"unknown element {capability_id!r} for explicit element_kind={normalized_kind!r}"
            ) from exc
        return _capability_from_element(definition)

    canonical = _split_canonical_element_id(capability_id, registry=registry, strict=True)
    if canonical is not None:
        requested_kind, requested_local_id = canonical
        try:
            definition = registry.get(requested_kind, requested_local_id)
        except KeyError as exc:
            raise CapabilityNotFoundError(f"unknown element {capability_id!r}") from exc
        return _capability_from_element(definition)

    matches = [definition for definition in registry.list() if definition.id == capability_id]
    if not matches:
        raise CapabilityNotFoundError(f"unknown element {capability_id!r}")
    if len(matches) > 1:
        candidates = tuple(
            _candidate_label("element", f"{definition.kind}/{definition.id}") for definition in matches
        )
        raise CapabilityAmbiguousError(
            f"ambiguous element {capability_id!r}; candidates: {_format_candidates(candidates)}"
        )
    return _capability_from_element(matches[0])


def _resolve_capability_kindless(
    capability_id: str,
    *,
    executor_registry: Any,
    orchestrator_registry: Any,
    element_registry: Any | None,
) -> Capability:
    matches: list[Capability] = []

    try:
        matches.append(
            _resolve_typed_capability(
                capability_id, executor_registry, capability_type="executor"
            )
        )
    except CapabilityNotFoundError:
        pass
    try:
        matches.append(
            _resolve_typed_capability(
                capability_id, orchestrator_registry, capability_type="orchestrator"
            )
        )
    except CapabilityNotFoundError:
        pass
    if element_registry is not None:
        try:
            matches.append(
                _resolve_element_capability(
                    capability_id,
                    element_registry,
                    element_kind=None,
                )
            )
        except CapabilityNotFoundError:
            pass

    if not matches:
        raise CapabilityNotFoundError(f"unknown capability {capability_id!r}")
    if len(matches) > 1:
        candidates = tuple(_candidate_label(match.capability_type, match.id) for match in matches)
        raise CapabilityAmbiguousError(
            f"ambiguous capability {capability_id!r}; candidates: {_format_candidates(candidates)}"
        )
    return matches[0]


def _resolve_capability(
    capability_id: str,
    *,
    kind: CapabilityType | None,
    element_kind: str | None,
    executor_registry: Any,
    orchestrator_registry: Any,
    element_registry: Any | None,
) -> Capability:
    if kind == "executor":
        return _resolve_typed_capability(
            capability_id, executor_registry, capability_type="executor"
        )
    if kind == "orchestrator":
        return _resolve_typed_capability(
            capability_id, orchestrator_registry, capability_type="orchestrator"
        )
    if kind == "element":
        if element_registry is None:
            raise CapabilityNotFoundError("element registry was not loaded")
        return _resolve_element_capability(
            capability_id,
            element_registry,
            element_kind=element_kind,
        )
    if kind is None:
        return _resolve_capability_kindless(
            capability_id,
            executor_registry=executor_registry,
            orchestrator_registry=orchestrator_registry,
            element_registry=element_registry,
        )
    raise CapabilityNotFoundError(
        f"unsupported capability kind {kind!r}; expected 'executor', 'orchestrator', 'element', or None"
    )
