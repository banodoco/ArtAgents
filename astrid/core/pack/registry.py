"""Element- and timeline-kind registry for packs."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from astrid.core.pack._common import (
    TIMELINE_KIND_CATALOGS,
    PackValidationError,
)

if TYPE_CHECKING:
    from astrid.core.contracts.artifact_types import (
        ArtifactTypeDescriptor,
        ArtifactTypeRegistry,
    )
    from astrid.core.pack.definition import PackDefinition


@dataclass(frozen=True)
class ElementKindDescriptor:
    id: str
    catalog: str = "element"
    aliases: tuple[str, ...] = ()
    default: bool = False
    singular: str = ""
    plural: str = ""
    label: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        aliases: list[str] = []
        for candidate in (self.id, self.plural, self.singular, *self.aliases):
            if isinstance(candidate, str) and candidate and candidate not in aliases:
                aliases.append(candidate)
        object.__setattr__(self, "aliases", tuple(aliases))

    @property
    def canonical_kind(self) -> str:
        return self.plural or self.id

    @property
    def canonical_name(self) -> str:
        return self.canonical_kind

    @property
    def catalog_label(self) -> str:
        return f"{self.catalog} kind"


class ElementKindRegistry:
    """Runtime registry for element and timeline kind catalogs."""

    def __init__(
        self,
        descriptors: Iterable[ElementKindDescriptor] | None = None,
    ) -> None:
        self._descriptors: dict[str, OrderedDict[str, ElementKindDescriptor]] = {}
        self._aliases: dict[str, dict[str, str]] = {}
        self._defaults: dict[str, str] = {}
        self.register_many(_builtin_kind_descriptors())
        self.register_many(descriptors or ())

    def register(self, descriptor: ElementKindDescriptor) -> None:
        self.register_many((descriptor,))

    def register_many(self, descriptors: Iterable[ElementKindDescriptor]) -> None:
        descriptors_by_catalog = {
            catalog: OrderedDict(entries)
            for catalog, entries in self._descriptors.items()
        }
        aliases_by_catalog = {
            catalog: dict(entries)
            for catalog, entries in self._aliases.items()
        }
        defaults_by_catalog = dict(self._defaults)
        for descriptor in descriptors:
            normalized_descriptor = self._normalize_descriptor(descriptor)
            catalog = normalized_descriptor.catalog
            canonical = normalized_descriptor.canonical_name
            catalog_descriptors = descriptors_by_catalog.setdefault(catalog, OrderedDict())
            catalog_aliases = aliases_by_catalog.setdefault(catalog, {})
            if canonical in catalog_descriptors:
                raise ValueError(f"duplicate {normalized_descriptor.catalog_label} {canonical!r}")
            for alias in normalized_descriptor.aliases:
                existing = catalog_aliases.get(alias)
                if existing is not None:
                    raise ValueError(
                        f"duplicate {normalized_descriptor.catalog_label} alias {alias!r}: "
                        f"{existing!r} and {canonical!r}"
                    )
            if normalized_descriptor.default:
                existing_default = defaults_by_catalog.get(catalog)
                if existing_default is not None:
                    raise ValueError(
                        f"duplicate default {normalized_descriptor.catalog_label}: "
                        f"{existing_default!r} and {canonical!r}"
                    )
                defaults_by_catalog[catalog] = canonical
            catalog_descriptors[canonical] = normalized_descriptor
            for alias in normalized_descriptor.aliases:
                catalog_aliases[alias] = canonical
        self._descriptors = descriptors_by_catalog
        self._aliases = aliases_by_catalog
        self._defaults = defaults_by_catalog

    def canonical_kinds(self, *, catalog: str = "element") -> tuple[str, ...]:
        return tuple(self._catalog_descriptors(catalog))

    def accepted_names(self, *, catalog: str = "element") -> tuple[str, ...]:
        names: list[str] = []
        for canonical, descriptor in self._catalog_descriptors(catalog).items():
            names.append(canonical)
            for alias in descriptor.aliases:
                if alias != canonical:
                    names.append(alias)
        return tuple(names)

    def valid_options(self, *, catalog: str = "element") -> tuple[str, ...]:
        return self.canonical_kinds(catalog=catalog)

    def default_kind(self, *, catalog: str = "element") -> str | None:
        return self._defaults.get(catalog)

    def descriptors(self, *, catalog: str | None = "element") -> tuple[ElementKindDescriptor, ...]:
        if catalog is None:
            return tuple(
                descriptor
                for catalog_descriptors in self._descriptors.values()
                for descriptor in catalog_descriptors.values()
            )
        return tuple(self._catalog_descriptors(catalog).values())

    def normalize(
        self,
        kind: str,
        *,
        catalog: str = "element",
        error_cls: type[Exception] = ValueError,
    ) -> str:
        canonical = self._catalog_aliases(catalog).get(kind)
        if canonical is None:
            available = ", ".join(self.valid_options(catalog=catalog))
            raise error_cls(f"{catalog} kind must be one of [{available}]")
        return canonical

    def singular(
        self,
        kind: str,
        *,
        catalog: str = "element",
        error_cls: type[Exception] = ValueError,
    ) -> str:
        descriptor = self.descriptor(kind, catalog=catalog, error_cls=error_cls)
        return descriptor.singular or descriptor.canonical_kind.rstrip("s")

    def descriptor(
        self,
        kind: str,
        *,
        catalog: str = "element",
        error_cls: type[Exception] = ValueError,
    ) -> ElementKindDescriptor:
        canonical = self.normalize(kind, catalog=catalog, error_cls=error_cls)
        return self._catalog_descriptors(catalog)[canonical]

    @staticmethod
    def _require_token(value: str, *, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value.strip()

    @classmethod
    def _normalize_optional_token(cls, value: str) -> str:
        if not value:
            return ""
        return cls._require_token(value, field_name="element kind alias")

    @staticmethod
    def _catalog_descriptors_store(
        descriptors: dict[str, OrderedDict[str, ElementKindDescriptor]],
        catalog: str,
    ) -> OrderedDict[str, ElementKindDescriptor]:
        return descriptors.setdefault(catalog, OrderedDict())

    def _catalog_descriptors(self, catalog: str) -> OrderedDict[str, ElementKindDescriptor]:
        return self._catalog_descriptors_store(self._descriptors, catalog)

    def _catalog_aliases(self, catalog: str) -> dict[str, str]:
        return self._aliases.setdefault(catalog, {})

    def _normalize_descriptor(self, descriptor: ElementKindDescriptor) -> ElementKindDescriptor:
        catalog = self._require_token(descriptor.catalog, field_name="kind catalog")
        canonical = self._require_token(
            descriptor.canonical_name,
            field_name=f"{catalog} kind",
        )
        normalized_aliases = tuple(
            self._require_token(alias, field_name=f"{catalog} kind alias")
            for alias in descriptor.aliases
        )
        normalized_descriptor = ElementKindDescriptor(
            catalog=catalog,
            id=self._require_token(descriptor.id, field_name=f"{catalog} kind id"),
            aliases=normalized_aliases,
            default=bool(descriptor.default),
            singular=self._normalize_optional_token(descriptor.singular),
            plural=self._normalize_optional_token(descriptor.plural),
            label=descriptor.label,
            description=descriptor.description,
        )
        if normalized_descriptor.canonical_name != canonical:
            normalized_descriptor = ElementKindDescriptor(
                catalog=normalized_descriptor.catalog,
                id=normalized_descriptor.id,
                aliases=normalized_aliases,
                default=normalized_descriptor.default,
                singular=normalized_descriptor.singular,
                plural=canonical,
                label=normalized_descriptor.label,
                description=normalized_descriptor.description,
            )
        return normalized_descriptor


def _builtin_element_kind_descriptors() -> tuple[ElementKindDescriptor, ...]:
    return (
        ElementKindDescriptor(id="effects", singular="effect", plural="effects"),
        ElementKindDescriptor(id="animations", singular="animation", plural="animations"),
        ElementKindDescriptor(id="transitions", singular="transition", plural="transitions"),
    )


def _builtin_kind_descriptors() -> tuple[ElementKindDescriptor, ...]:
    return (
        *_builtin_element_kind_descriptors(),
        ElementKindDescriptor(catalog="transition", id="cross-fade", aliases=("crossfade",), default=True),
        ElementKindDescriptor(catalog="clip", id="video"),
        ElementKindDescriptor(catalog="clip", id="image"),
        ElementKindDescriptor(catalog="clip", id="audio"),
        ElementKindDescriptor(catalog="clip", id="text"),
        ElementKindDescriptor(catalog="clip", id="effect"),
        ElementKindDescriptor(catalog="clip", id="opaque"),
        ElementKindDescriptor(catalog="track", id="visual", default=True),
        ElementKindDescriptor(catalog="track", id="audio"),
    )


_BUILTIN_KIND_IDS_BY_CATALOG: dict[str, frozenset[str]] = {}
for _descriptor in _builtin_kind_descriptors():
    _BUILTIN_KIND_IDS_BY_CATALOG.setdefault(_descriptor.catalog, set()).add(_descriptor.canonical_name)
_BUILTIN_KIND_IDS_BY_CATALOG = {
    catalog: frozenset(ids)
    for catalog, ids in _BUILTIN_KIND_IDS_BY_CATALOG.items()
}


ELEMENT_KIND_REGISTRY = ElementKindRegistry()


def pack_rendering_manifest_paths(
    pack: "PackDefinition",
) -> tuple[tuple[Path, ...], tuple[Path, ...], tuple[Path, ...]]:
    """Return contained renderer, planner, and finalizer manifest paths.

    Rendering extensions name manifests relative to the pack root. Resolving
    every path before returning it also rejects traversal and symlink escapes.
    """
    rendering = pack.extensions.get("rendering", {})
    renderers = _resolve_pack_rendering_manifest_paths(
        pack,
        rendering.get("renderers", ()),
        kind="renderers",
    )
    planners = _resolve_pack_rendering_manifest_paths(
        pack,
        rendering.get("planners", ()),
        kind="planners",
    )
    finalizers = _resolve_pack_rendering_manifest_paths(
        pack,
        rendering.get("finalizers", ()),
        kind="finalizers",
    )
    return renderers, planners, finalizers


def _resolve_pack_rendering_manifest_paths(
    pack: "PackDefinition",
    paths: Iterable[str],
    *,
    kind: str,
) -> tuple[Path, ...]:
    root = pack.root.resolve()
    resolved_paths: list[Path] = []
    for index, raw_path in enumerate(paths):
        relative_path = Path(raw_path)
        resolved = (root / relative_path).resolve()
        if relative_path.is_absolute() or not resolved.is_relative_to(root):
            raise PackValidationError(
                f"pack.extensions.rendering.{kind}[{index}] must stay within the pack root"
            )
        resolved_paths.append(resolved)
    return tuple(resolved_paths)


def pack_element_kind_descriptors(pack: "PackDefinition") -> tuple[ElementKindDescriptor, ...]:
    element_extensions = pack.extensions.get("elements", {})
    kinds = element_extensions.get("kinds", ())
    return tuple(
        ElementKindDescriptor(
            id=kind["id"],
            singular=kind.get("singular", ""),
            plural=kind.get("plural", ""),
            label=kind.get("label", ""),
            description=kind.get("description", ""),
        )
        for kind in kinds
    )


def pack_timeline_kind_descriptors(pack: "PackDefinition") -> tuple[ElementKindDescriptor, ...]:
    timeline_extensions = pack.extensions.get("timeline", {})
    kinds = timeline_extensions.get("kinds", ())
    return tuple(
        ElementKindDescriptor(
            catalog=kind["catalog"],
            id=kind["id"],
            aliases=tuple(kind.get("aliases", ())),
            default=bool(kind.get("default", False)),
        )
        for kind in kinds
    )


def pack_kind_descriptors(pack: "PackDefinition") -> tuple[ElementKindDescriptor, ...]:
    return pack_element_kind_descriptors(pack) + pack_timeline_kind_descriptors(pack)


def element_kind_registry_for_pack(
    pack: "PackDefinition",
    *,
    base_registry: ElementKindRegistry | None = None,
) -> ElementKindRegistry:
    registry = base_registry or ELEMENT_KIND_REGISTRY
    descriptors = _extension_kind_descriptors(registry) + pack_kind_descriptors(pack)
    if not descriptors:
        return registry
    try:
        return ElementKindRegistry(descriptors=descriptors)
    except ValueError as exc:
        raise PackValidationError(_pack_kind_registry_error(pack, str(exc))) from exc


def _extension_kind_descriptors(
    registry: ElementKindRegistry,
) -> tuple[ElementKindDescriptor, ...]:
    return tuple(
        descriptor
        for descriptor in registry.descriptors(catalog=None)
        if descriptor.canonical_name not in _BUILTIN_KIND_IDS_BY_CATALOG.get(descriptor.catalog, frozenset())
    )


def _pack_kind_registry_error(pack: "PackDefinition", message: str) -> str:
    if " element kind " in f" {message} ":
        return f"pack.extensions.elements.kinds is invalid: {message}"
    if any(f" {catalog} kind " in f" {message} " for catalog in TIMELINE_KIND_CATALOGS):
        return f"pack.extensions.timeline.kinds is invalid: {message}"
    return f"pack kind extensions are invalid: {message}"


# ---------------------------------------------------------------------------
# Artifact-type registry (mirrors the element/timeline kind pattern above)
# ---------------------------------------------------------------------------


def pack_artifact_type_descriptors(
    pack: "PackDefinition",
) -> "tuple[ArtifactTypeDescriptor, ...]":
    """Extract :class:`ArtifactTypeDescriptor` entries from a pack's
    ``extensions.artifact_types.types`` block."""
    from astrid.core.contracts.artifact_types import ArtifactTypeDescriptor

    artifact_extensions = pack.extensions.get("artifact_types", {})
    types = artifact_extensions.get("types", ())
    return tuple(
        ArtifactTypeDescriptor(
            id=item["id"],
            aliases=tuple(item.get("aliases", ())),
            description=item.get("description", ""),
        )
        for item in types
    )


def artifact_type_registry_for_pack(
    pack: "PackDefinition",
    *,
    base_registry: "ArtifactTypeRegistry | None" = None,
) -> "ArtifactTypeRegistry":
    """Build an :class:`ArtifactTypeRegistry` seeded from *pack* extensions.

    Follows the same pattern as :func:`element_kind_registry_for_pack`.
    """
    from astrid.core.contracts.artifact_types import (
        ARTIFACT_TYPE_REGISTRY,
        ArtifactTypeDescriptor,
        ArtifactTypeRegistry,
        ArtifactTypeRegistryError,
    )

    registry = base_registry or ARTIFACT_TYPE_REGISTRY
    descriptors = _extension_artifact_type_descriptors(registry) + pack_artifact_type_descriptors(pack)
    if not descriptors:
        return registry
    try:
        # Seed with all non-builtin descriptors (from base + pack), builtins
        # are added automatically by ArtifactTypeRegistry.__init__.
        return ArtifactTypeRegistry(descriptors=descriptors)
    except ArtifactTypeRegistryError as exc:
        raise PackValidationError(
            f"pack.extensions.artifact_types is invalid: {exc}"
        ) from exc


def _extension_artifact_type_descriptors(
    registry: "ArtifactTypeRegistry",
) -> "tuple[ArtifactTypeDescriptor, ...]":
    """Return descriptors from *registry* that are NOT builtins."""
    from astrid.core.contracts.artifact_types import (
        ARTIFACT_TYPE_REGISTRY,
        ArtifactTypeDescriptor,
    )

    builtin_ids = set(ARTIFACT_TYPE_REGISTRY.canonical_ids())
    return tuple(
        ArtifactTypeDescriptor(
            id=desc.id,
            aliases=desc.aliases,
            description=desc.description,
        )
        for desc in registry.descriptors()
        if desc.id not in builtin_ids
    )
