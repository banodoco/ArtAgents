"""Pack discovery and validation helpers."""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml

PACK_MANIFEST_NAMES = ("pack.yaml", "pack.yml", "pack.json")
EXECUTOR_MANIFEST_NAMES = ("executor.yaml", "executor.yml", "executor.json")
ORCHESTRATOR_MANIFEST_NAMES = ("orchestrator.yaml", "orchestrator.yml", "orchestrator.json")
PACK_ALIAS_KINDS: tuple[Literal["executor", "orchestrator"], ...] = ("executor", "orchestrator")
PackAliasKind = Literal["executor", "orchestrator"]
PACK_PERMISSION_IDS: tuple[str, ...] = (
    "project_files",
    "network",
    "subprocess",
    "environment",
    "accelerator",
    "external_services",
)
# Built-in element-kind constants remain stable for compatibility even though
# runtime validation now flows through ElementKindRegistry.
ELEMENT_KINDS: tuple[str, ...] = ("effects", "animations", "transitions")
TIMELINE_KIND_CATALOGS: tuple[str, ...] = ("transition", "clip", "track")
ElementKind = str
_PACK_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class PackValidationError(ValueError):
    """Raised when pack layout or metadata is invalid."""


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


@dataclass(frozen=True)
class PackPermission:
    id: str
    reason: str
    access: str = ""
    services: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "reason": self.reason,
        }
        if self.access:
            payload["access"] = self.access
        if self.services:
            payload["services"] = list(self.services)
        return payload


@dataclass(frozen=True)
class PackDefinition:
    id: str
    name: str
    version: str
    root: Path
    manifest_path: Path
    metadata: dict[str, Any]
    description: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    agent: dict[str, Any] = field(default_factory=dict)
    status: str = field(default="active")
    visibility: str = field(default="visible")
    schema_version: str = field(default="")
    aliases: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    permissions: tuple[PackPermission, ...] = field(default_factory=tuple)
    extensions: dict[str, Any] = field(default_factory=dict)
    origin: str = field(default="unknown")
    install_tier: str = field(default="default")
    pack_type: str = field(default="capability")
    domain: str = field(default="general")
    stability: str = field(default="stable")
    support: str = field(default="project")

    def to_dict(self) -> dict[str, Any]:
        taxonomy = {
            "origin": self.origin,
            "install_tier": self.install_tier,
            "pack_type": self.pack_type,
            "domain": self.domain,
            "stability": self.stability,
            "support": self.support,
        }
        payload = {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "root": str(self.root),
            "manifest_path": str(self.manifest_path),
            "metadata": dict(self.metadata),
            "content": dict(self.content),
            "agent": dict(self.agent),
            "status": self.status,
            "visibility": self.visibility,
            "schema_version": self.schema_version,
            **taxonomy,
            "taxonomy": taxonomy,
        }
        if self.aliases:
            payload["aliases"] = [dict(alias) for alias in self.aliases]
        if self.permissions:
            payload["permissions"] = [permission.to_dict() for permission in self.permissions]
        if self.extensions:
            payload["extensions"] = _normalize_json_value(
                self.extensions,
                path="pack.extensions",
            )
        return payload


def packs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "packs"


DEFAULT_PACKS_ROOT = packs_root()


def ensure_local_pack(*, project_root: str | Path = None) -> Path:
    """Create or return the ``local`` scratch pack under *project_root*.

    When *project_root* is ``None``, the pack root is derived from
    ``REPO_ROOT`` so the behaviour matches the old location in
    ``element/registry.py``.
    """
    from astrid._paths import REPO_ROOT

    root = Path(project_root) if project_root is not None else REPO_ROOT
    pack_root = root / "astrid" / "packs" / "local"
    pack_root.mkdir(parents=True, exist_ok=True)
    manifest = pack_root / "pack.yaml"
    if not manifest.exists():
        manifest.write_text("id: local\nname: Local Scratch Pack\nversion: 0.1.0\n", encoding="utf-8")
    return pack_root


def discover_packs(
    root: str | Path | None = None,
    *,
    include_hidden: bool = False,
) -> tuple[PackDefinition, ...]:
    source_root = Path(root) if root is not None else packs_root()
    if not source_root.is_dir():
        return ()
    packs: list[PackDefinition] = []
    seen: dict[str, Path] = {}
    for child in sorted(source_root.iterdir(), key=lambda path: path.name):
        if not child.is_dir() or child.name.startswith(".") or child.name == "__pycache__":
            continue
        manifest_path = pack_manifest_path(child)
        if manifest_path is None:
            continue
        pack = load_pack_manifest(manifest_path)
        if pack.visibility == "hidden" and not include_hidden:
            continue
        if pack.id in seen:
            raise PackValidationError(f"duplicate pack id {pack.id!r}: {seen[pack.id]} and {manifest_path}")
        seen[pack.id] = manifest_path
        packs.append(pack)
    return tuple(packs)


def load_pack_manifest(path: str | Path) -> PackDefinition:
    manifest_path = Path(path).expanduser().resolve()
    raw = _load_manifest_payload(manifest_path)
    data = _require_mapping(raw, "pack")
    pack_id = _require_string(data, "id", "pack.id")
    _validate_pack_id(pack_id, "pack.id")
    root = manifest_path.parent
    if root.name != pack_id:
        raise PackValidationError(f"pack id {pack_id!r} must match folder name {root.name!r}")
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise PackValidationError("pack.metadata must be an object")
    content = data.get("content", {})
    if not isinstance(content, dict):
        raise PackValidationError("pack.content must be an object")
    agent = data.get("agent", {})
    if not isinstance(agent, dict):
        raise PackValidationError("pack.agent must be an object")
    status = _optional_string(data, "status", "pack.status", default="active")
    visibility = _optional_string(data, "visibility", "pack.visibility", default="visible")
    schema_version = str(data.get("schema_version", "")) if "schema_version" in data else ""
    aliases = _optional_pack_aliases(data.get("aliases"), path="pack.aliases")
    permissions = _normalize_pack_permissions(data.get("permissions"))
    extensions = _optional_pack_extensions(data.get("extensions"), path="pack.extensions")
    taxonomy = pack_taxonomy_from_manifest(data, status=status)
    return PackDefinition(
        id=pack_id,
        name=_optional_string(data, "name", "pack.name", default=pack_id),
        version=_optional_string(data, "version", "pack.version", default="0.1.0"),
        root=root,
        manifest_path=manifest_path,
        metadata=dict(metadata),
        description=_optional_string(data, "description", "pack.description", default=""),
        content=dict(content),
        agent=dict(agent),
        status=status,
        visibility=visibility,
        schema_version=schema_version,
        aliases=aliases,
        permissions=permissions,
        extensions=extensions,
        **taxonomy,
    )


def pack_taxonomy_from_manifest(data: dict[str, Any], *, status: str) -> dict[str, str]:
    """Return the deterministic taxonomy projection for a pack manifest.

    These defaults are the M1 taxonomy baseline for manifests that do not yet
    declare an explicit taxonomy block.
    """
    return {
        "origin": _optional_string(data, "origin", "pack.origin", default="unknown"),
        "install_tier": _optional_string(data, "install_tier", "pack.install_tier", default="default"),
        "pack_type": _optional_string(data, "pack_type", "pack.pack_type", default="capability"),
        "domain": _optional_string(data, "domain", "pack.domain", default="general"),
        "stability": _optional_string(
            data,
            "stability",
            "pack.stability",
            default=_default_stability_for_status(status),
        ),
        "support": _optional_string(data, "support", "pack.support", default="project"),
    }


def _default_stability_for_status(status: str) -> str:
    if status == "experimental":
        return "experimental"
    if status == "deprecated":
        return "deprecated"
    return "stable"


def _optional_pack_aliases(value: Any, *, path: str) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise PackValidationError(f"{path} must be an array")

    normalized: list[dict[str, Any]] = []
    allowed_keys = {"alias", "canonical_id", "kind", "deprecated", "deprecation_message"}
    for index, raw_alias in enumerate(value):
        alias_path = f"{path}[{index}]"
        if not isinstance(raw_alias, dict):
            raise PackValidationError(f"{alias_path} must be an object")
        unknown_keys = sorted(set(raw_alias) - allowed_keys)
        if unknown_keys:
            raise PackValidationError(
                f"{alias_path} has unknown field(s): {', '.join(unknown_keys)}"
            )

        kind = _require_string(raw_alias, "kind", f"{alias_path}.kind")
        if kind not in PACK_ALIAS_KINDS:
            raise PackValidationError(
                f"{alias_path}.kind must be one of {list(PACK_ALIAS_KINDS)}"
            )

        alias = _require_string(raw_alias, "alias", f"{alias_path}.alias")
        qualified_id_pack_id(alias, path=f"{alias_path}.alias")
        canonical_id = _require_string(raw_alias, "canonical_id", f"{alias_path}.canonical_id")
        qualified_id_pack_id(canonical_id, path=f"{alias_path}.canonical_id")

        normalized_alias: dict[str, Any] = {
            "kind": kind,
            "alias": alias,
            "canonical_id": canonical_id,
        }
        if "deprecated" in raw_alias:
            deprecated = raw_alias["deprecated"]
            if not isinstance(deprecated, bool):
                raise PackValidationError(f"{alias_path}.deprecated must be a boolean")
            normalized_alias["deprecated"] = deprecated
        if "deprecation_message" in raw_alias:
            deprecation_message = raw_alias["deprecation_message"]
            if not isinstance(deprecation_message, str):
                raise PackValidationError(f"{alias_path}.deprecation_message must be a string")
            normalized_alias["deprecation_message"] = deprecation_message
        normalized.append(normalized_alias)

    return tuple(normalized)


def _normalize_pack_permissions(raw: Any, field: str = "permissions") -> tuple[PackPermission, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise PackValidationError(f"{field} must be an array")

    normalized: list[PackPermission] = []
    allowed_keys = {"id", "reason", "access", "services"}
    for index, raw_permission in enumerate(raw):
        permission_path = f"{field}[{index}]"
        permission = _require_mapping(raw_permission, permission_path)
        unknown_keys = sorted(set(permission) - allowed_keys)
        if unknown_keys:
            raise PackValidationError(
                f"{permission_path} has unknown field(s): {', '.join(unknown_keys)}"
            )

        permission_id = _require_string(permission, "id", f"{permission_path}.id")
        if permission_id not in PACK_PERMISSION_IDS:
            raise PackValidationError(
                f"{permission_path}.id must be one of {list(PACK_PERMISSION_IDS)}"
            )

        normalized.append(
            PackPermission(
                id=permission_id,
                reason=_require_string(permission, "reason", f"{permission_path}.reason"),
                access=_optional_string(permission, "access", f"{permission_path}.access", default=""),
                services=_normalize_pack_permission_services(
                    permission.get("services"),
                    path=f"{permission_path}.services",
                ),
            )
        )

    return tuple(normalized)


def _normalize_pack_permission_services(value: Any, *, path: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise PackValidationError(f"{path} must be an array")

    normalized: list[str] = []
    for index, raw_service in enumerate(value):
        service_path = f"{path}[{index}]"
        if not isinstance(raw_service, str) or not raw_service.strip():
            raise PackValidationError(f"{service_path} must be a non-empty string")
        normalized.append(raw_service.strip())
    return tuple(normalized)


def _optional_pack_extensions(value: Any, *, path: str) -> dict[str, Any]:
    if value is None:
        return {}
    data = _require_mapping(value, path)
    allowed_keys = {"generation", "elements", "timeline", "schemas"}
    unknown_keys = sorted(set(data) - allowed_keys)
    if unknown_keys:
        raise PackValidationError(f"{path} has unknown field(s): {', '.join(unknown_keys)}")

    normalized: dict[str, Any] = {}
    if "generation" in data:
        normalized["generation"] = _normalize_generation_extensions(
            data["generation"],
            path=f"{path}.generation",
        )
    if "elements" in data:
        normalized["elements"] = _normalize_element_extensions(
            data["elements"],
            path=f"{path}.elements",
        )
    if "timeline" in data:
        normalized["timeline"] = _normalize_timeline_extensions(
            data["timeline"],
            path=f"{path}.timeline",
        )
    if "schemas" in data:
        normalized["schemas"] = _normalize_json_object(
            data["schemas"],
            path=f"{path}.schemas",
        )
    return normalized


def _normalize_generation_extensions(value: Any, *, path: str) -> dict[str, Any]:
    data = _require_mapping(value, path)
    allowed_keys = {"backends", "features", "modes"}
    unknown_keys = sorted(set(data) - allowed_keys)
    if unknown_keys:
        raise PackValidationError(f"{path} has unknown field(s): {', '.join(unknown_keys)}")

    normalized: dict[str, Any] = {}
    if "backends" in data:
        normalized["backends"] = _normalize_generation_backends(
            data["backends"],
            path=f"{path}.backends",
        )
    if "features" in data:
        normalized["features"] = _normalize_named_extension_list(
            data["features"],
            path=f"{path}.features",
        )
    if "modes" in data:
        normalized["modes"] = _normalize_named_extension_list(
            data["modes"],
            path=f"{path}.modes",
        )
    return normalized


def _normalize_generation_backends(value: Any, *, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise PackValidationError(f"{path} must be an array")

    normalized: list[dict[str, Any]] = []
    allowed_keys = {"id", "label", "module", "class", "init_kwargs"}
    for index, raw_backend in enumerate(value):
        backend_path = f"{path}[{index}]"
        backend = _require_mapping(raw_backend, backend_path)
        unknown_keys = sorted(set(backend) - allowed_keys)
        if unknown_keys:
            raise PackValidationError(
                f"{backend_path} has unknown field(s): {', '.join(unknown_keys)}"
            )
        normalized_backend = {
            "id": _require_string(backend, "id", f"{backend_path}.id"),
            "module": _require_string(backend, "module", f"{backend_path}.module"),
            "class": _require_string(backend, "class", f"{backend_path}.class"),
        }
        if "label" in backend:
            normalized_backend["label"] = _optional_string(
                backend,
                "label",
                f"{backend_path}.label",
                default="",
            )
        if "init_kwargs" in backend:
            normalized_backend["init_kwargs"] = _normalize_json_object(
                backend["init_kwargs"],
                path=f"{backend_path}.init_kwargs",
            )
        normalized.append(normalized_backend)
    return normalized


def _normalize_named_extension_list(value: Any, *, path: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise PackValidationError(f"{path} must be an array")

    normalized: list[dict[str, str]] = []
    allowed_keys = {"id", "label", "description"}
    for index, raw_item in enumerate(value):
        item_path = f"{path}[{index}]"
        if isinstance(raw_item, str):
            if not raw_item.strip():
                raise PackValidationError(f"{item_path} must be a non-empty string")
            normalized.append({"id": raw_item})
            continue
        item = _require_mapping(raw_item, item_path)
        unknown_keys = sorted(set(item) - allowed_keys)
        if unknown_keys:
            raise PackValidationError(
                f"{item_path} has unknown field(s): {', '.join(unknown_keys)}"
            )
        normalized_item = {
            "id": _require_string(item, "id", f"{item_path}.id"),
        }
        if "label" in item:
            normalized_item["label"] = _optional_string(
                item,
                "label",
                f"{item_path}.label",
                default="",
            )
        if "description" in item:
            normalized_item["description"] = _optional_string(
                item,
                "description",
                f"{item_path}.description",
                default="",
            )
        normalized.append(normalized_item)
    return normalized


def _normalize_element_extensions(value: Any, *, path: str) -> dict[str, Any]:
    data = _require_mapping(value, path)
    allowed_keys = {"kinds"}
    unknown_keys = sorted(set(data) - allowed_keys)
    if unknown_keys:
        raise PackValidationError(f"{path} has unknown field(s): {', '.join(unknown_keys)}")

    normalized: dict[str, Any] = {}
    if "kinds" in data:
        normalized["kinds"] = _normalize_element_kinds(
            data["kinds"],
            path=f"{path}.kinds",
        )
    return normalized


def _normalize_timeline_extensions(value: Any, *, path: str) -> dict[str, Any]:
    data = _require_mapping(value, path)
    allowed_keys = {"kinds"}
    unknown_keys = sorted(set(data) - allowed_keys)
    if unknown_keys:
        raise PackValidationError(f"{path} has unknown field(s): {', '.join(unknown_keys)}")

    normalized: dict[str, Any] = {}
    if "kinds" in data:
        normalized["kinds"] = _normalize_timeline_kinds(
            data["kinds"],
            path=f"{path}.kinds",
        )
    return normalized


def _normalize_element_kinds(value: Any, *, path: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise PackValidationError(f"{path} must be an array")

    normalized: list[dict[str, str]] = []
    allowed_keys = {"id", "singular", "plural", "label", "description"}
    for index, raw_kind in enumerate(value):
        kind_path = f"{path}[{index}]"
        kind = _require_mapping(raw_kind, kind_path)
        unknown_keys = sorted(set(kind) - allowed_keys)
        if unknown_keys:
            raise PackValidationError(
                f"{kind_path} has unknown field(s): {', '.join(unknown_keys)}"
            )
        normalized_kind = {
            "id": _require_string(kind, "id", f"{kind_path}.id"),
        }
        for key in ("singular", "plural", "label", "description"):
            if key in kind:
                normalized_kind[key] = _optional_string(
                    kind,
                    key,
                    f"{kind_path}.{key}",
                    default="",
                )
        normalized.append(normalized_kind)
    return normalized


def _normalize_timeline_kinds(value: Any, *, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise PackValidationError(f"{path} must be an array")

    normalized: list[dict[str, Any]] = []
    allowed_keys = {"catalog", "id", "aliases", "default"}
    for index, raw_kind in enumerate(value):
        kind_path = f"{path}[{index}]"
        kind = _require_mapping(raw_kind, kind_path)
        unknown_keys = sorted(set(kind) - allowed_keys)
        if unknown_keys:
            raise PackValidationError(
                f"{kind_path} has unknown field(s): {', '.join(unknown_keys)}"
            )
        catalog = _require_string(kind, "catalog", f"{kind_path}.catalog")
        if catalog not in TIMELINE_KIND_CATALOGS:
            raise PackValidationError(
                f"{kind_path}.catalog must be one of {list(TIMELINE_KIND_CATALOGS)}"
            )
        normalized_kind: dict[str, Any] = {
            "catalog": catalog,
            "id": _require_string(kind, "id", f"{kind_path}.id"),
        }
        if "aliases" in kind:
            aliases = kind["aliases"]
            if not isinstance(aliases, list):
                raise PackValidationError(f"{kind_path}.aliases must be an array")
            normalized_aliases: list[str] = []
            for alias_index, raw_alias in enumerate(aliases):
                alias_path = f"{kind_path}.aliases[{alias_index}]"
                if not isinstance(raw_alias, str) or not raw_alias.strip():
                    raise PackValidationError(f"{alias_path} must be a non-empty string")
                normalized_aliases.append(raw_alias.strip())
            normalized_kind["aliases"] = normalized_aliases
        if "default" in kind:
            default = kind["default"]
            if not isinstance(default, bool):
                raise PackValidationError(f"{kind_path}.default must be a boolean")
            normalized_kind["default"] = default
        normalized.append(normalized_kind)
    return normalized


def pack_manifest_path(root: str | Path) -> Path | None:
    pack_root = Path(root)
    for name in PACK_MANIFEST_NAMES:
        candidate = pack_root / name
        if candidate.is_file():
            return candidate
    return None


def qualified_id_pack_id(value: str, *, path: str = "id") -> str:
    if not isinstance(value, str) or not value.strip():
        raise PackValidationError(f"{path} must be a non-empty qualified id")
    parts = value.split(".")
    if len(parts) < 2 or any(not part for part in parts):
        raise PackValidationError(f"{path} must be qualified as <pack>.<name>")
    _validate_pack_id(parts[0], f"{path} pack segment")
    return parts[0]


def validate_content_id_in_pack(content_id: str, pack: PackDefinition, *, content_type: str) -> None:
    owner = qualified_id_pack_id(content_id, path=f"{content_type}.id")
    if owner != pack.id:
        raise PackValidationError(
            f"{content_type} id {content_id!r} belongs to pack {owner!r} but was found in pack {pack.id!r}"
        )


def validate_element_pack_id(pack_id: str | None, pack: PackDefinition, *, element_root: str | Path) -> None:
    if not pack_id:
        raise PackValidationError(f"element {Path(element_root)} is missing metadata.pack_id")
    if pack_id != pack.id:
        raise PackValidationError(
            f"element {Path(element_root)} declares pack_id {pack_id!r} but was found in pack {pack.id!r}"
        )


def iter_executor_roots(pack: PackDefinition) -> tuple[Path, ...]:
    declared = _declared_content_root(pack, "executors")
    if declared is not None:
        return tuple(_direct_content_roots(declared, EXECUTOR_MANIFEST_NAMES))
    return _content_roots(pack.root, EXECUTOR_MANIFEST_NAMES, excluded_parts={"elements"})


def iter_orchestrator_roots(pack: PackDefinition) -> tuple[Path, ...]:
    declared = _declared_content_root(pack, "orchestrators")
    if declared is not None:
        return tuple(_direct_content_roots(declared, ORCHESTRATOR_MANIFEST_NAMES))
    return _content_roots(pack.root, ORCHESTRATOR_MANIFEST_NAMES, excluded_parts={"elements"})


def iter_element_roots(
    pack: PackDefinition,
    *,
    kind: str | None = None,
    element_kind_registry: ElementKindRegistry | None = None,
) -> tuple[tuple[ElementKind, Path], ...]:
    registry = element_kind_registry or element_kind_registry_for_pack(pack)
    roots: list[tuple[ElementKind, Path]] = []
    elements_root = _declared_content_root(pack, "elements") or (pack.root / "elements")
    kind_roots = _iter_element_kind_dirs(elements_root, registry=registry)
    if kind is not None:
        requested_kind = registry.normalize(kind, error_cls=PackValidationError)
        kind_roots = tuple(
            (element_kind, kind_root)
            for element_kind, kind_root in kind_roots
            if element_kind == requested_kind
        )
    for element_kind, kind_root in kind_roots:
        roots.extend((element_kind, child) for child in sorted(kind_root.iterdir()) if child.is_dir())
    return tuple(roots)


def _iter_element_kind_dirs(
    elements_root: Path,
    *,
    registry: ElementKindRegistry,
) -> tuple[tuple[ElementKind, Path], ...]:
    if not elements_root.is_dir():
        return ()
    kind_roots: list[tuple[ElementKind, Path]] = []
    for child in sorted(elements_root.iterdir(), key=lambda path: path.name):
        if (
            not child.is_dir()
            or child.name.startswith(".")
            or child.name.startswith("_")
            or child.name == "__pycache__"
        ):
            continue
        kind_roots.append(
            (
                registry.normalize(child.name, error_cls=PackValidationError),
                child,
            )
        )
    return tuple(kind_roots)


def _declared_content_root(pack: PackDefinition, key: str) -> Path | None:
    if not pack.content:
        return None
    value = pack.content.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    return (pack.root / value).resolve()


def _direct_content_roots(root: Path, manifest_names: tuple[str, ...]) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    roots: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name):
        if not child.is_dir() or child.name.startswith(".") or child.name == "__pycache__":
            continue
        if any((child / name).is_file() for name in manifest_names):
            roots.append(child.resolve())
    return tuple(roots)


def _content_roots(root: Path, manifest_names: tuple[str, ...], *, excluded_parts: set[str]) -> tuple[Path, ...]:
    vendored = _vendored_subdirs(root)
    roots = {
        path.parent.resolve()
        for manifest_name in manifest_names
        for path in root.rglob(manifest_name)
        if "__pycache__" not in path.parts
        and excluded_parts.isdisjoint(path.relative_to(root).parts)
        and not any(parent in vendored for parent in path.parents)
    }
    return tuple(sorted(roots))


def _vendored_subdirs(root: Path) -> set[Path]:
    # Any subdirectory containing a .git entry is a vendored submodule/clone;
    # its manifests belong to the upstream project, not this pack.
    return {
        marker.parent.resolve()
        for marker in root.rglob(".git")
        if marker.parent != root
    }


def _load_manifest_payload(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PackValidationError(f"pack manifest not found: {path}") from exc
    if path.suffix.lower() == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise PackValidationError(f"invalid JSON pack manifest {path}: {exc.msg}") from exc
    # Try canonical YAML parsing first (handles both flat and nested manifests).
    # Fall back to the legacy flat parser for manifests that yaml.safe_load cannot parse.
    try:
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            if "schema_version" in data:
                return data
            try:
                return _parse_flat_yaml(text, path=path)
            except PackValidationError:
                return data
    except yaml.YAMLError:
        pass
    return _parse_flat_yaml(text, path=path)


def _parse_flat_yaml(text: str, *, path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw_line[: len(raw_line) - len(raw_line.lstrip())].strip():
            raise PackValidationError(f"{path}: invalid indentation at line {line_number}")
        if ":" not in stripped:
            raise PackValidationError(f"{path}: expected key: value at line {line_number}")
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = _strip_comment(value.strip())
        if not key:
            raise PackValidationError(f"{path}: empty key at line {line_number}")
        if value in {"", "{}"}:
            data[key] = {}
        else:
            data[key] = _unquote(value)
    if not data:
        raise PackValidationError(f"{path}: empty pack manifest")
    return data


def _strip_comment(value: str) -> str:
    in_quote: str | None = None
    for index, char in enumerate(value):
        if char in {"'", '"'} and (index == 0 or value[index - 1] != "\\"):
            in_quote = None if in_quote == char else char if in_quote is None else in_quote
        if char == "#" and in_quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _require_mapping(raw: Any, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise PackValidationError(f"{path} must be an object")
    return raw


def _require_string(data: dict[str, Any], key: str, path: str) -> str:
    if key not in data:
        raise PackValidationError(f"missing required field {path}")
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise PackValidationError(f"{path} must be a non-empty string")
    return value


def _optional_string(data: dict[str, Any], key: str, path: str, *, default: str) -> str:
    if key not in data or data[key] == "":
        return default
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise PackValidationError(f"{path} must be a non-empty string")
    return value


def _normalize_json_object(value: Any, *, path: str) -> dict[str, Any]:
    normalized = _normalize_json_value(value, path=path)
    if not isinstance(normalized, dict):
        raise PackValidationError(f"{path} must be an object")
    return normalized


def _normalize_json_value(value: Any, *, path: str) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [
            _normalize_json_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise PackValidationError(f"{path} keys must be non-empty strings")
            normalized[key] = _normalize_json_value(item, path=f"{path}.{key}")
        return normalized
    raise PackValidationError(f"{path} must be JSON-serializable")


def _validate_pack_id(value: str, path: str) -> None:
    if not _PACK_ID_RE.fullmatch(value):
        raise PackValidationError(f"{path} must be a safe pack identifier matching ^[a-z][a-z0-9_]*$")


__all__ = [
    "ElementKindDescriptor",
    "ElementKindRegistry",
    "ELEMENT_KIND_REGISTRY",
    "PackDefinition",
    "PackValidationError",
    "discover_packs",
    "element_kind_registry_for_pack",
    "ensure_local_pack",
    "iter_element_roots",
    "iter_executor_roots",
    "iter_orchestrator_roots",
    "load_pack_manifest",
    "pack_taxonomy_from_manifest",
    "pack_manifest_path",
    "packs_root",
    "qualified_id_pack_id",
    "validate_content_id_in_pack",
    "validate_element_pack_id",
]
