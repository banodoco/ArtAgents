"""Registry loading, discovery metadata, and capability resolution helpers."""

from __future__ import annotations

import importlib
import re
from difflib import SequenceMatcher
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


def _canonical_entries(
    catalog: Any,
    *,
    project_root: str | Path | None,
    extra_pack_roots: tuple[str, ...],
    include_installed: bool,
) -> tuple[Any, ...]:
    entries: dict[str, Any] = {entry.id: entry for entry in catalog.ordered_entries}
    if extra_pack_roots or include_installed:
        from astrid.core.foundation.paths import REPO_ROOT
        from astrid.core.pack.discovery import discover_canonical_packs_ordered

        for entry in discover_canonical_packs_ordered(
            project_root=project_root or REPO_ROOT,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        ):
            entries.setdefault(entry.id, entry)
    return tuple(entries.values())


def _canonical_aliases(entries: tuple[Any, ...], kind: str) -> dict[str, list[dict[str, object]]]:
    aliases: dict[str, list[dict[str, object]]] = {}
    for entry in entries:
        matching = [
            dict(alias)
            for alias in entry.definition.aliases
            if alias.get("kind") == kind
        ]
        if matching:
            aliases[entry.id] = matching
    return aliases


def _canonical_executor_registry(
    entries: tuple[Any, ...],
    *,
    project_root: str | Path | None,
    banodoco_config: Any | None,
) -> Any:
    from astrid.core.execution.executor.folder import load_folder_executors
    from astrid.core.execution.executor.registry import (
        ExecutorRegistry,
        _attach_pack_metadata,
    )
    from astrid.core.execution.executor.banodoco_catalog import (
        load_banodoco_catalog_executors,
    )
    from astrid.core.execution.executor.schema import ExecutorValidationError
    from astrid.core.pack import validate_content_id_in_pack
    from astrid.core.pack.alias_resolver import (
        _register_pack_aliases,
        create_shared_alias_resolver,
    )
    from astrid.core.pack.manifest import ManifestParseError
    from astrid.core.pack.override import OverrideStore
    from astrid.core.foundation.paths import REPO_ROOT

    resolver = create_shared_alias_resolver()
    _register_pack_aliases(resolver, _canonical_aliases(entries, "executor"))
    registry = ExecutorRegistry(
        alias_resolver=resolver,
        override_store=OverrideStore(project_root or REPO_ROOT),
    )
    for entry in entries:
        relative_root = entry.definition.content.get("executors")
        if not isinstance(relative_root, str):
            continue
        try:
            definitions = load_folder_executors(entry.root / relative_root)
            for definition in definitions:
                validate_content_id_in_pack(
                    definition.id, entry, content_type="executor"
                )
                registry.register(
                    _attach_pack_metadata(
                        definition,
                        entry.id,
                        pack_root=entry.root,
                        content_root=entry.root / relative_root,
                    )
                )
        except (ExecutorValidationError, ManifestParseError) as exc:
            import logging

            logging.getLogger(__name__).warning(
                "skipping canonical pack %r: executor manifests failed validation: %s",
                entry.id,
                exc,
            )
    if banodoco_config is not None and banodoco_config.enabled:
        for definition in load_banodoco_catalog_executors(banodoco_config):
            registry.register(definition)
    registry.validate_all()
    return registry


def _canonical_orchestrator_registry(
    entries: tuple[Any, ...],
    *,
    project_root: str | Path | None,
    executor_registry: Any,
) -> Any:
    from astrid.core.execution.orchestrator.folder import load_folder_orchestrators
    from astrid.core.execution.orchestrator.registry import (
        OrchestratorRegistry,
        _attach_pack_metadata,
    )
    from astrid.core.execution.orchestrator.schema import OrchestratorValidationError
    from astrid.core.foundation.paths import REPO_ROOT
    from astrid.core.pack import validate_content_id_in_pack
    from astrid.core.pack.alias_resolver import (
        _register_pack_aliases,
        create_shared_alias_resolver,
    )
    from astrid.core.pack.manifest import ManifestParseError
    from astrid.core.pack.override import OverrideStore

    resolver = create_shared_alias_resolver()
    _register_pack_aliases(resolver, _canonical_aliases(entries, "orchestrator"))
    registry = OrchestratorRegistry(
        executor_registry=executor_registry,
        alias_resolver=resolver,
        override_store=OverrideStore(project_root or REPO_ROOT),
    )
    for entry in entries:
        relative_root = entry.definition.content.get("orchestrators")
        if not isinstance(relative_root, str):
            continue
        try:
            definitions = load_folder_orchestrators(entry.root / relative_root)
            for definition in definitions:
                validate_content_id_in_pack(
                    definition.id, entry, content_type="orchestrator"
                )
                registry.register(
                    _attach_pack_metadata(
                        definition,
                        entry.id,
                        content_root=entry.root / relative_root,
                    )
                )
        except (OrchestratorValidationError, ManifestParseError) as exc:
            import logging

            logging.getLogger(__name__).warning(
                "skipping canonical pack %r: orchestrator manifests failed validation: %s",
                entry.id,
                exc,
            )
    registry.validate_all(executor_registry=executor_registry)
    return registry


def _canonical_element_registry(
    entries: tuple[Any, ...],
    *,
    active_theme: str | Path | None,
    include_missing_roots: bool,
    project_root: str | Path | None,
) -> Any:
    from astrid.core.element.registry import ElementRegistry
    from astrid.core.element.schema import (
        ElementValidationError,
        load_element_definition,
    )
    from astrid.core.foundation.paths import REPO_ROOT
    from astrid.core.pack import ELEMENT_KIND_REGISTRY, validate_element_pack_id
    from astrid.core.pack.override import OverrideStore
    from astrid.core.theme import resolve_theme_dir

    registry = ElementRegistry(
        override_store=OverrideStore(project_root or REPO_ROOT),
        element_kind_registry=ELEMENT_KIND_REGISTRY,
    )
    for entry in entries:
        relative_root = entry.definition.content.get("elements")
        if not isinstance(relative_root, str):
            continue
        root = entry.root / relative_root
        for kind in ELEMENT_KIND_REGISTRY.canonical_kinds():
            kind_root = root / kind
            if not kind_root.is_dir():
                continue
            for element_root in sorted(kind_root.iterdir(), key=lambda path: path.name):
                if not element_root.is_dir():
                    continue
                try:
                    definition = load_element_definition(
                        element_root,
                        kind=kind,
                        source=entry.source,
                        editable=False,
                        priority=30,
                        element_kind_registry=ELEMENT_KIND_REGISTRY,
                    )
                    validate_element_pack_id(
                        definition.metadata.get("pack_id"),
                        entry,
                        element_root=element_root,
                    )
                    registry.register(definition)
                except ElementValidationError:
                    continue
    if active_theme is not None:
        # Canonical pack loading does not replace the explicit theme seam.
        resolve_theme_dir(active_theme)
    if include_missing_roots:
        return registry
    return registry




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
    catalog: Any | None = None,
) -> tuple[Any, Any, Any | None]:
    if catalog is not None:
        entries = _canonical_entries(
            catalog,
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        )
        executor_registry = _canonical_executor_registry(
            entries,
            project_root=project_root,
            banodoco_config=banodoco_config,
        )
        orchestrator_registry = _canonical_orchestrator_registry(
            entries,
            project_root=project_root,
            executor_registry=executor_registry,
        )
        element_registry = (
            _canonical_element_registry(
                entries,
                active_theme=active_theme,
                include_missing_roots=include_missing_roots,
                project_root=project_root,
            )
            if include_elements
            else None
        )
        return executor_registry, orchestrator_registry, element_registry

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
    catalog: Any | None = None,
) -> tuple[Any, ...]:
    if catalog is not None:
        from astrid.core.pack.canonical import _thaw
        from astrid.core.pack.definition import PackDefinition, PackPermission
        from astrid.core.pack.discovery import DiscoveredPack

        discovered: list[Any] = []
        for priority_index, entry in enumerate(catalog.ordered_entries):
            definition = entry.definition
            pack = PackDefinition(
                id=definition.id,
                name=definition.name,
                version=definition.version,
                root=entry.root,
                manifest_path=entry.manifest.resolved,
                metadata={"capabilities": list(definition.capabilities)},
                description=definition.description,
                content=dict(_thaw(definition.content)),
                agent=dict(_thaw(definition.agent)),
                status=definition.status,
                visibility=definition.visibility,
                schema_version=str(definition.schema_version),
                aliases=tuple(dict(_thaw(alias)) for alias in definition.aliases),
                permissions=tuple(
                    PackPermission(
                        id=permission.id,
                        reason=permission.reason,
                        access=permission.access,
                        services=permission.services,
                    )
                    for permission in definition.permissions
                ),
                extensions=dict(_thaw(definition.extensions)),
                origin="bundled",
                install_tier="default",
                pack_type="capability",
                domain=definition.domain,
                stability=definition.stability,
                support=definition.support,
            )
            discovered.append(
                DiscoveredPack(
                    pack=pack,
                    source_kind="source",
                    priority_index=priority_index,
                )
            )
        return tuple(discovered)

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
    permissions = payload.get("permissions", [])
    if not isinstance(permissions, list):
        permissions = list(permissions) if isinstance(permissions, tuple) else []
    payload["permissions"] = permissions
    payload["permission_ids"] = [
        item.get("id")
        for item in permissions
        if isinstance(item, Mapping) and item.get("id")
    ]
    payload["trust"] = {
        "sandbox": "none",
        "runs_with_user_process_permissions": True,
        "permission_enforcement": "disclosure_only",
    }
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
    permission_ids = ()
    if pack_permission_ids_by_pack_id:
        permission_ids = pack_permission_ids_by_pack_id.get(capability.handle.pack_id, ())
    # A pack-level permission describes the common substrate.  A capability
    # may additionally require a narrower permission (for example, the
    # editorial transcription executor calls the OpenAI API while the rest of
    # the editorial pack is local-only).  Keep those per-capability additions
    # in the public safety block without widening every sibling capability.
    required = capability.definition.get("metadata", {}).get("required_permissions", ())
    if isinstance(required, (list, tuple)):
        permission_ids = tuple(dict.fromkeys((*permission_ids, *(str(item) for item in required))))
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


_SUGGESTION_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _capability_suggestions(
    capability_id: str,
    *,
    executor_registry: Any,
    orchestrator_registry: Any,
    element_registry: Any | None,
    limit: int = 3,
) -> tuple[str, ...]:
    """Return a small, deterministic set of nearby public capability ids."""
    query = str(capability_id).strip().lower()
    if not query:
        return ()
    query_tokens = set(_SUGGESTION_TOKEN_RE.findall(query))
    records: list[tuple[float, str, str]] = []

    def add_registry(registry: Any, capability_type: str) -> None:
        resolver = getattr(registry, "alias_resolver", None)
        for definition in registry.list():
            aliases = tuple(
                str(record.alias) for record in resolver.get_aliases_for(definition.id)
            ) if resolver is not None else ()
            fields = (
                definition.id,
                getattr(definition, "name", ""),
                getattr(definition, "short_description", ""),
                getattr(definition, "description", ""),
                *getattr(definition, "keywords", ()),
                *aliases,
            )
            field_text = " ".join(fields).lower()
            field_tokens = set(_SUGGESTION_TOKEN_RE.findall(field_text))
            exact_tokens = len(query_tokens & field_tokens)
            ratio = max(
                SequenceMatcher(None, query, candidate.lower()).ratio()
                for candidate in (definition.id, *aliases)
            )
            # A single generic word from a long query (for example ``edge``
            # in ``far.unknown.capability.edge.zzzz``) is not enough to offer
            # an unrelated capability. Keep typo/alias matches and concise
            # natural queries, but suppress low-confidence semantic matches.
            semantic_confidence = exact_tokens / max(len(query_tokens), 1)
            if ratio < 0.45 and semantic_confidence < 0.5:
                continue
            substring = 1.0 if query in field_text else 0.0
            score = exact_tokens * 12.0 + ratio * 8.0 + substring * 12.0
            if score >= 10.0:
                alias_hint = f" (alias: {aliases[0]})" if aliases else ""
                records.append((score, f"{capability_type}:{definition.id}{alias_hint}", definition.id))

    add_registry(executor_registry, "executor")
    add_registry(orchestrator_registry, "orchestrator")
    if element_registry is not None:
        add_registry(element_registry, "element")
    records.sort(key=lambda item: (-item[0], item[2]))
    return tuple(item[1] for item in records[:limit])


def _lookup_guidance(
    capability_id: str,
    *,
    requested_kind: str | None,
    executor_registry: Any,
    orchestrator_registry: Any,
    element_registry: Any | None,
) -> str:
    registries = (
        ("executor", executor_registry),
        ("orchestrator", orchestrator_registry),
        ("element", element_registry),
    )
    exact_other: list[str] = []
    for kind, registry in registries:
        if registry is None or kind == requested_kind:
            continue
        if kind == "element":
            found = any(definition.id == capability_id for definition in registry.list())
        else:
            try:
                registry.get(capability_id)
            except (KeyError, ValueError):
                found = False
            else:
                found = True
        if not found:
            continue
        exact_other.append(kind)
    parts: list[str] = []
    if exact_other and requested_kind is not None:
        choices = ", ".join(f"kind={kind!r}" for kind in exact_other)
        parts.append(f"registered as {', '.join(exact_other)}; retry with {choices}")
    suggestions = _capability_suggestions(
        capability_id,
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
        element_registry=element_registry,
    )
    if suggestions:
        parts.append("nearest matches: " + ", ".join(suggestions))
    if not suggestions and not exact_other:
        parts.append(
            "no close catalog match; recovery: call "
            "discover(include_installed=False) and filter capabilities by id, "
            "name, or aliases; supported kinds: executor, orchestrator, element"
        )
    return "; ".join(parts)


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
        try:
            return _resolve_typed_capability(
                capability_id, executor_registry, capability_type="executor"
            )
        except CapabilityNotFoundError as exc:
            guidance = _lookup_guidance(
                capability_id,
                requested_kind="executor",
                executor_registry=executor_registry,
                orchestrator_registry=orchestrator_registry,
                element_registry=element_registry,
            )
            if guidance:
                raise CapabilityNotFoundError(f"{exc}; {guidance}") from exc
            raise
    if kind == "orchestrator":
        try:
            return _resolve_typed_capability(
                capability_id, orchestrator_registry, capability_type="orchestrator"
            )
        except CapabilityNotFoundError as exc:
            guidance = _lookup_guidance(
                capability_id,
                requested_kind="orchestrator",
                executor_registry=executor_registry,
                orchestrator_registry=orchestrator_registry,
                element_registry=element_registry,
            )
            if guidance:
                raise CapabilityNotFoundError(f"{exc}; {guidance}") from exc
            raise
    if kind == "element":
        if element_registry is None:
            raise CapabilityNotFoundError("element registry was not loaded")
        try:
            return _resolve_element_capability(
                capability_id,
                element_registry,
                element_kind=element_kind,
            )
        except CapabilityNotFoundError as exc:
            guidance = _lookup_guidance(
                capability_id,
                requested_kind="element",
                executor_registry=executor_registry,
                orchestrator_registry=orchestrator_registry,
                element_registry=element_registry,
            )
            if guidance:
                raise CapabilityNotFoundError(f"{exc}; {guidance}") from exc
            raise
    if kind is None:
        try:
            return _resolve_capability_kindless(
                capability_id,
                executor_registry=executor_registry,
                orchestrator_registry=orchestrator_registry,
                element_registry=element_registry,
            )
        except CapabilityNotFoundError as exc:
            guidance = _lookup_guidance(
                capability_id,
                requested_kind=None,
                executor_registry=executor_registry,
                orchestrator_registry=orchestrator_registry,
                element_registry=element_registry,
            )
            if guidance:
                raise CapabilityNotFoundError(f"{exc}; {guidance}") from exc
            raise
    raise CapabilityNotFoundError(
        f"unsupported capability kind {kind!r}; expected 'executor', 'orchestrator', 'element', or None"
    )
