"""Element registry and canonical pack-source discovery."""

import logging
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.pack import (
    ELEMENT_KIND_REGISTRY,
    ElementKindRegistry,
    PackDefinition,
    PackValidationError,
    discover_packs,
    iter_element_roots,
    pack_element_kind_descriptors,
    validate_element_pack_id,
)
from astrid.core.pack.alias_resolver import (
    AliasResolver,
    _register_pack_aliases,
    create_shared_alias_resolver,
)
from astrid.core.pack.discovery import discover_pack_metadata
from astrid.core.registry import CapabilityRegistry

from .schema import (
    ElementDefinition,
    ElementKind,
    ElementValidationError,
    load_element_definition,
)

class ElementRegistryError(ElementValidationError):
    """Raised when element registry state is inconsistent."""


_LOGGER = logging.getLogger(__name__)
@dataclass(frozen=True)
class ElementSource:
    name: str
    root: Path
    priority: int
    editable: bool


@dataclass(frozen=True)
class ElementConflict:
    kind: ElementKind
    id: str
    winner: ElementDefinition
    shadowed: tuple[ElementDefinition, ...]


class ElementRegistry(CapabilityRegistry[tuple[str, str], ElementDefinition]):
    """Resolved element registry keyed by kind and element id.

    Inherits generic storage and conflict detection from
    :class:`CapabilityRegistry`.
    """

    def __init__(
        self,
        elements: Iterable[ElementDefinition] = (),
        *,
        alias_resolver: AliasResolver | None = None,
        element_kind_registry: ElementKindRegistry | None = None,
    ) -> None:
        super().__init__(alias_resolver=alias_resolver)
        self.element_kind_registry = element_kind_registry or ELEMENT_KIND_REGISTRY
        for element in elements:
            self.register(element)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, element: ElementDefinition) -> ElementDefinition:
        key = (element.kind, element.id)
        self._register_impl(
            key,
            element,
            # The first discovered source owns a duplicate id.  A local
            # Editable packs are ordinary source content, never a special
            # precedence layer.
            priority_key=lambda item: item.priority,
        )
        return element

    def get(self, kind: ElementKind, element_id: str) -> ElementDefinition:
        normalized_kind = self.element_kind_registry.normalize(kind, error_cls=ElementRegistryError)
        key = (normalized_kind, element_id)
        try:
            definition = self._resolve_entry(self._entries[key])
        except KeyError as exc:
            raise KeyError(f"unknown {normalized_kind} element {element_id!r}") from exc
        return definition

    def list(self, kind: ElementKind | None = None) -> tuple[ElementDefinition, ...]:
        normalized_kind = None
        if kind is not None:
            normalized_kind = self.element_kind_registry.normalize(kind, error_cls=ElementRegistryError)
        winners = [
            self._resolve_entry(definitions)
            for (item_kind, _), definitions in self._entries.items()
            if normalized_kind is None or item_kind == normalized_kind
        ]
        return tuple(sorted(winners, key=lambda item: (item.kind, item.id)))

    def conflicts(self) -> tuple[ElementConflict, ...]:
        conflicts: list[ElementConflict] = []
        for (kind, element_id), definitions in self._entries.items():
            if len(definitions) > 1:
                conflicts.append(
                    ElementConflict(
                        kind=kind,
                        id=element_id,
                        winner=definitions[0],
                        shadowed=tuple(definitions[1:]),
                    )
                )
        return tuple(sorted(conflicts, key=lambda item: (item.kind, item.id)))

    def as_mapping(self) -> dict[tuple[str, str], ElementDefinition]:
        """Return winners-only mapping (return type narrowed for element callers).

        Inherited ``as_mapping()`` returns ``MappingProxyType``; element
        callers may rely on mutable dict access, so we preserve the dict
        return type here.
        """
        return {key: definitions[0] for key, definitions in self._entries.items()}

@lru_cache(maxsize=None)
def _load_default_registry_data(
    project_root_key: str,
    include_missing_roots: bool,
    extra_pack_roots_key: tuple[str, ...],
) -> tuple[tuple[ElementDefinition, ...], ElementKindRegistry]:
    """Parse the static element corpus once; return raw definitions.

    The corpus (packs + default element sources) is static repo content.  A
    fresh parse costs seconds of YAML work per call (measured: ~2s per load,
    ~189 ``yaml.safe_load`` calls — a 93-event timeline replay that validates
    four config events spends ~6s total).  Callers rebuild a fresh
    :class:`ElementRegistry` from the cached raw definitions, so per-call
    registry mutation never leaks into the shared cache.
    """
    project_root = Path(project_root_key)
    pack_defs = tuple(
        discovered.pack
        for discovered in discover_pack_metadata(
            project_root=project_root,
            extra_pack_roots=tuple(Path(key) for key in extra_pack_roots_key),
            discover_packs_fn=discover_packs,
        )
    )
    element_kind_registry = _element_kind_registry_for_packs(pack_defs)
    elements: list[ElementDefinition] = list(
        _load_pack_elements_from_packs(
            pack_defs,
            element_kind_registry=element_kind_registry,
        )
    )
    for source in default_sources(project_root=project_root):
        if not source.root.exists():
            if include_missing_roots:
                source.root.mkdir(parents=True, exist_ok=True)
            else:
                continue
        elements.extend(
            load_source_elements(
                source,
                element_kind_registry=element_kind_registry,
            )
        )
    return (tuple(elements), element_kind_registry)


def clear_default_registry_cache() -> None:
    """Drop the cached element corpus.

    Test seam / hot-reload hook: tests that patch pack discovery must clear
    this cache (the catalog's ``_clear_registry_cache`` does) so a re-discovered
    corpus (e.g. a temp pack declaring a custom element kind) is re-parsed.
    """
    _load_default_registry_data.cache_clear()


def load_default_registry(
    *,
    project_root: str | Path = REPO_ROOT,
    include_missing_roots: bool = False,
    extra_pack_roots: tuple[str, ...] = (),
) -> ElementRegistry:
    """Load the default element registry (corpus parse is cached).

    Registry assembly stays per-call so callers may register additional
    elements without polluting the shared corpus cache.
    """
    elements, element_kind_registry = _load_default_registry_data(
        str(Path(project_root).resolve()),
        include_missing_roots,
        tuple(str(Path(root).resolve()) for root in extra_pack_roots),
    )
    resolver = create_shared_alias_resolver()
    _register_pack_aliases(resolver, {})  # M1: no aliases yet
    registry = ElementRegistry(
        alias_resolver=resolver,
        element_kind_registry=element_kind_registry,
    )
    for element in elements:
        registry.register(element)
    return registry


def default_sources(*, project_root: str | Path = REPO_ROOT) -> tuple[ElementSource, ...]:
    """Return no filesystem Styledoc sources.

    Executable element definitions belong to discovered packs.  A runtime
    theme document is visual data and cannot add or override element code.
    ``project_root`` is retained for callers that construct the source list.
    """

    del project_root
    return ()


def load_pack_elements(
    *,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
    element_kind_registry: ElementKindRegistry | None = None,
) -> tuple[ElementDefinition, ...]:
    packs = tuple(
        discovered.pack
        for discovered in discover_pack_metadata(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            discover_packs_fn=discover_packs,
        )
    )
    registry = element_kind_registry or _element_kind_registry_for_packs(packs)
    return _load_pack_elements_from_packs(
        packs,
        element_kind_registry=registry,
    )


def load_source_elements(
    source: ElementSource,
    *,
    element_kind_registry: ElementKindRegistry | None = None,
) -> tuple[ElementDefinition, ...]:
    from .schema import ELEMENT_MANIFEST_NAMES

    elements: list[ElementDefinition] = []
    registry = element_kind_registry or ELEMENT_KIND_REGISTRY
    for kind in registry.canonical_kinds():
        kind_root = source.root / kind
        if not kind_root.is_dir():
            continue
        for child in sorted(kind_root.iterdir(), key=lambda path: path.name):
            if not child.is_dir():
                continue
            if not any((child / name).is_file() for name in ELEMENT_MANIFEST_NAMES):
                continue
            try:
                elements.append(
                    load_element_definition(
                        child,
                        kind=kind,
                        source=source.name,
                        editable=source.editable,
                        priority=source.priority,
                        element_kind_registry=registry,
                    )
                )
            except ElementValidationError as exc:
                print(f"WARN skipping {child}: {exc}", file=sys.stderr)
    return tuple(elements)

def _element_kind_registry_for_packs(
    packs: Iterable[PackDefinition],
) -> ElementKindRegistry:
    descriptors = []
    for pack in packs:
        descriptors.extend(pack_element_kind_descriptors(pack))
    if not descriptors:
        return ELEMENT_KIND_REGISTRY
    try:
        return ElementKindRegistry(descriptors=descriptors)
    except ValueError as exc:
        raise PackValidationError(f"pack.extensions.elements.kinds is invalid: {exc}") from exc


def _load_pack_elements_from_packs(
    packs: Iterable[PackDefinition],
    *,
    element_kind_registry: ElementKindRegistry,
) -> tuple[ElementDefinition, ...]:
    from .schema import ELEMENT_MANIFEST_NAMES

    elements: list[ElementDefinition] = []
    for pack in packs:
        # All discovered packs share the same priority.  Discovery order is
        # canonical; the local editable pack cannot shadow a source pack.
        priority = 30
        # Per-pack fault tolerance: one broken element manifest (e.g. from an
        # installed external pack) must not abort the whole discovery/invoke.
        # The pack is skipped with a warning; pack-alignment failures
        # (``PackValidationError`` from ``validate_element_pack_id``) still
        # propagate — a misplaced pack_id is a packaging contract breach.
        try:
            for kind, root in iter_element_roots(
                pack,
                element_kind_registry=element_kind_registry,
            ):
                if not any((root / name).is_file() for name in ELEMENT_MANIFEST_NAMES):
                    continue
                element = load_element_definition(
                    root,
                    kind=kind,
                    source=f"pack:{pack.id}",
                    editable=pack.id == "local",
                    priority=priority,
                    element_kind_registry=element_kind_registry,
                )
                validate_element_pack_id(element.metadata.get("pack_id"), pack, element_root=root)
                elements.append(element)
        except ElementValidationError as exc:
            _LOGGER.warning(
                "skipping pack %r: element definitions failed validation: %s",
                pack.id,
                exc,
            )
            continue
    return tuple(elements)
