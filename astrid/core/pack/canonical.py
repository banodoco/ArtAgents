"""Canonical v2 pack contract.

This module is deliberately isolated from the active v1 loader.  It parses one
explicit ``pack.yaml`` into immutable declarations and is used by B1 fixture
catalogs only; production discovery remains on the v1 path until cutover.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import jsonschema

from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry


from astrid.core.pack._common import SymlinkedPackPathError, reject_symlinked_path
from astrid.core.pack.manifest import load_manifest_mapping

CANONICAL_MANIFEST_NAME = "pack.yaml"
LEGACY_MANIFEST_NAMES = frozenset({"pack.yml", "pack.json", "schema-pack.yaml"})
_SCHEMA_PATH = Path(__file__).with_name("schemas") / "v2" / "pack.json"

_PACK_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_LOWER_IDENT = _PACK_ID
_NON_BLANK = re.compile(r"^.*\S.*$", re.DOTALL)
_RELATIVE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
_RELEASE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_QUALIFIED = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_VOCABULARY = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
_MIGRATION_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class CanonicalPackError(ValueError):
    """Base error for canonical pack loading and catalog construction."""


class CanonicalPackValidationError(CanonicalPackError):
    """A v2 manifest or its declarations violate the canonical contract."""


class ExternalDatabaseForbidden(CanonicalPackValidationError):
    """An external candidate attempted to declare a database contribution."""


def _freeze(value: Any) -> Any:
    """Recursively freeze strict JSON-shaped values."""
    if isinstance(value, float) and not math.isfinite(value):
        raise CanonicalPackValidationError("manifest values must be finite JSON numbers")
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise CanonicalPackValidationError("manifest object keys must be strings")
        return MappingProxyType(
            {key: _freeze(item) for key, item in sorted(value.items())}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


def _validate_string_keys(
    value: Any, path: str, *, _ancestors: set[int] | None = None
) -> None:
    """Reject YAML keys JSON cannot represent and recursive aliases."""
    if not isinstance(value, (Mapping, list, tuple)):
        return
    ancestors = _ancestors if _ancestors is not None else set()
    identity = id(value)
    if identity in ancestors:
        raise CanonicalPackValidationError(f"{path} contains a recursive YAML alias")
    ancestors.add(identity)
    try:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise CanonicalPackValidationError(f"{path} object keys must be strings")
                _validate_string_keys(item, f"{path}.{key}", _ancestors=ancestors)
        else:
            for item in value:
                _validate_string_keys(item, f"{path}[]", _ancestors=ancestors)
    finally:
        ancestors.remove(identity)


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CanonicalPackValidationError(f"{path} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise CanonicalPackValidationError(f"{path} object keys must be strings")
    return value


def _text(value: Any, path: str, *, non_blank: bool = True) -> str:
    if not isinstance(value, str) or (non_blank and not _NON_BLANK.fullmatch(value.strip())):
        raise CanonicalPackValidationError(f"{path} must be non-blank text")
    return value.strip() if non_blank else value


def _unique_strings(
    value: Any, path: str, *, pattern: re.Pattern[str] | None = None
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise CanonicalPackValidationError(f"{path} must be an array")
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        text = _text(item, f"{path}[{index}]")
        if pattern is not None and not pattern.fullmatch(text):
            raise CanonicalPackValidationError(f"{path}[{index}] has invalid identifier {text!r}")
        if text in seen:
            raise CanonicalPackValidationError(f"{path} contains duplicate {text!r}")
        seen.add(text)
        result.append(text)
    return tuple(sorted(result))


def _relative_path(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise CanonicalPackValidationError(f"{path} must be a non-empty POSIX-relative path")
    if value.startswith("/"):
        raise CanonicalPackValidationError(f"{path} must not be absolute")
    parts = value.split("/")
    if any(
        not part or part in {".", ".."} or not _RELATIVE_SEGMENT.fullmatch(part) for part in parts
    ):
        raise CanonicalPackValidationError(
            f"{path} must not contain traversal or invalid path segments"
        )
    return PurePosixPath(*parts).as_posix()


def _normalize_nested_json(
    value: Any, path: str, *, _ancestors: set[int] | None = None
) -> Any:
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, int) or isinstance(value, str):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalPackValidationError(f"{path} must contain finite JSON numbers")
        return value
    if not isinstance(value, (list, dict)):
        raise CanonicalPackValidationError(f"{path} must contain JSON values")
    ancestors = _ancestors if _ancestors is not None else set()
    identity = id(value)
    if identity in ancestors:
        raise CanonicalPackValidationError(f"{path} contains a recursive YAML alias")
    ancestors.add(identity)
    try:
        if isinstance(value, list):
            return [
                _normalize_nested_json(item, f"{path}[]", _ancestors=ancestors)
                for item in value
            ]
        if any(not isinstance(key, str) for key in value):
            raise CanonicalPackValidationError(f"{path} object keys must be strings")
        return {
            key: _normalize_nested_json(item, f"{path}.{key}", _ancestors=ancestors)
            for key, item in sorted(value.items(), key=lambda item: item[0])
        }
    finally:
        ancestors.remove(identity)


@dataclass(frozen=True, slots=True)
class PackPermission:
    id: str
    reason: str
    access: str | None = None
    services: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PackDependency:
    pack: str
    min_migration: int

    @property
    def version(self) -> int:
        """Database projection spelling used by the migration machinery."""
        return self.min_migration


@dataclass(frozen=True, slots=True)
class MigrationDescriptor:
    version: int
    name: str
    path: str
    tables: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DatabaseContribution:
    default_enabled: bool
    depends_on: tuple[PackDependency, ...]
    migrations: tuple[MigrationDescriptor, ...]
    stream_types: tuple[str, ...]
    event_kinds: tuple[str, ...]
    command_kinds: tuple[str, ...]
    repositories: tuple[str, ...]
    conformance: tuple[str, ...]
    cli_mounts: Mapping[str, str]
    bridge_mounts: tuple[str, ...]

    @property
    def migration_head(self) -> int:
        return self.migrations[-1].version


@dataclass(frozen=True, slots=True)
class ResourceDeclaration:
    path: str
    kind: str


@dataclass(frozen=True, slots=True)
class AuthoringExclusion:
    path: str
    kind: str
    reason: str


@dataclass(frozen=True, slots=True)
class Documentation:
    kind: str
    path: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ResourceHandle:
    path: str
    root: Path
    resolved: Path
    kind: str
    file_kind: str
    size: int
    sha256: str

    @property
    def relative_path(self) -> str:
        return self.path

    @property
    def owner_root(self) -> Path:
        return self.root

    @property
    def resolved_root(self) -> Path:
        return self.root

    @property
    def digest(self) -> str:
        return self.sha256


@dataclass(frozen=True, slots=True)
class CatalogProvenance:
    source: str
    provenance_identity: str
    root: Path
    revision: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalPackDefinition:
    schema_version: int
    id: str
    name: str
    version: str
    description: str
    status: str
    visibility: str
    domain: str
    stability: str
    support: str
    keywords: tuple[str, ...]
    capabilities: tuple[str, ...]
    permissions: tuple[PackPermission, ...]
    content: Mapping[str, str]
    extensions: Mapping[str, Any]
    aliases: tuple[Mapping[str, str], ...]
    agent: Mapping[str, Any]
    documentation: Documentation | None
    secrets: tuple[Mapping[str, Any], ...]
    dependencies: Mapping[str, tuple[str, ...]]
    astrid_version: str | None
    database: DatabaseContribution | None
    resources: tuple[ResourceDeclaration, ...]
    authoring_only: tuple[AuthoringExclusion, ...]

    def to_dict(self) -> dict[str, Any]:
        result = {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "status": self.status,
            "visibility": self.visibility,
            "domain": self.domain,
            "stability": self.stability,
            "support": self.support,
            "keywords": list(self.keywords),
            "capabilities": list(self.capabilities),
            "permissions": [
                {
                    "id": item.id,
                    "reason": item.reason,
                    **({"access": item.access} if item.access is not None else {}),
                    **({"services": list(item.services)} if item.services else {}),
                }
                for item in self.permissions
            ],
            "content": dict(self.content),
            "extensions": _thaw(self.extensions),
            "aliases": [_thaw(item) for item in self.aliases],
            "agent": _thaw(self.agent),
            "secrets": [_thaw(item) for item in self.secrets],
            "dependencies": _thaw(self.dependencies),
            "resources": [{"path": item.path, "kind": item.kind} for item in self.resources],
            "authoring_only": [
                {"path": item.path, "kind": item.kind, "reason": item.reason}
                for item in self.authoring_only
            ],
        }
        if self.documentation is not None:
            result["documentation"] = {
                "kind": self.documentation.kind,
                **({"path": self.documentation.path} if self.documentation.path else {}),
                **({"reason": self.documentation.reason} if self.documentation.reason else {}),
            }
        if self.astrid_version is not None:
            result["astrid_version"] = self.astrid_version
        if self.database is not None:
            result["database"] = {
                "default_enabled": self.database.default_enabled,
                "depends_on": [
                    {"pack": item.pack, "min_migration": item.min_migration}
                    for item in self.database.depends_on
                ],
                "migrations": [
                    {
                        "version": item.version,
                        "name": item.name,
                        "path": item.path,
                        "tables": list(item.tables),
                    }
                    for item in self.database.migrations
                ],
                "stream_types": list(self.database.stream_types),
                "event_kinds": list(self.database.event_kinds),
                "command_kinds": list(self.database.command_kinds),
                "repositories": list(self.database.repositories),
                "conformance": list(self.database.conformance),
                "cli_mounts": dict(self.database.cli_mounts),
                "bridge_mounts": list(self.database.bridge_mounts),
            }
        return result

    @property
    def normalized(self) -> Mapping[str, Any]:
        return _freeze(self.to_dict())


@dataclass(frozen=True, slots=True)
class CapabilityProjection:
    pack_id: str
    capabilities: tuple[str, ...]
    content: Mapping[str, str]
    extensions: Mapping[str, Any]
    aliases: tuple[Mapping[str, str], ...]
    permissions: tuple[PackPermission, ...]


@dataclass(frozen=True, slots=True)
class DatabaseProjection:
    pack_id: str
    database: DatabaseContribution


@dataclass(frozen=True, slots=True)
class ResourceProjection:
    pack_id: str
    resources: tuple[ResourceHandle, ...]


@dataclass(frozen=True, slots=True)
class DocumentationProjection:
    pack_id: str
    documentation: Documentation | None
    required_context: tuple[ResourceHandle, ...]


@dataclass(frozen=True, slots=True)
class CanonicalPackEntry:
    definition: CanonicalPackDefinition
    provenance: CatalogProvenance
    manifest: ResourceHandle
    resources: tuple[ResourceHandle, ...]
    authoring_exclusions: tuple[AuthoringExclusion, ...] = ()

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def pack_id(self) -> str:
        return self.definition.id

    @property
    def root(self) -> Path:
        return self.provenance.root

    @property
    def database(self) -> DatabaseContribution | None:
        return self.definition.database

    @property
    def identity(self) -> Mapping[str, str]:
        return MappingProxyType(
            {"id": self.id, "name": self.definition.name, "version": self.definition.version}
        )

    @property
    def source(self) -> str:
        return self.provenance.source

    @property
    def capabilities(self) -> CapabilityProjection:
        return self.capability_projection()

    @property
    def extensions(self) -> Mapping[str, Any]:
        return self.definition.extensions

    @property
    def documentation(self) -> Documentation | None:
        return self.definition.documentation

    @property
    def resource_handles(self) -> tuple[ResourceHandle, ...]:
        return self.resources

    def capability_projection(self) -> CapabilityProjection:
        definition = self.definition
        return CapabilityProjection(
            definition.id,
            definition.capabilities,
            definition.content,
            definition.extensions,
            definition.aliases,
            definition.permissions,
        )

    def database_projection(self) -> DatabaseProjection | None:
        return None if self.database is None else DatabaseProjection(self.id, self.database)

    def resource_projection(self) -> ResourceProjection:
        return ResourceProjection(self.id, self.resources)

    def documentation_projection(self) -> DocumentationProjection:
        context_paths = set(self.definition.agent.get("required_context", ()))
        return DocumentationProjection(
            self.id,
            self.definition.documentation,
            tuple(item for item in self.resources if item.path in context_paths),
        )


@dataclass(frozen=True, slots=True)
class _BundledAdmission:
    """Unforgeable admission marker held only by :class:`BundledCatalog`."""


_BUNDLED_ADMISSION = _BundledAdmission()
_VALIDATION_SOURCE = "validation"
_STATIC_VALIDATION_ADMISSION = object()


class ExternalPackSource(str, Enum):
    """Supported provenance values for external canonical-pack admission."""

    LOCAL = "local"
    EXTRA = "extra"
    ENV = "env"
    INSTALLED = "installed"
    GIT = "git"

def _schema() -> dict[str, Any]:
    try:
        return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CanonicalPackError(f"cannot read canonical schema {_SCHEMA_PATH}: {exc}") from exc


def _validate_schema_version(data: dict[str, Any], manifest_path: Path) -> None:
    """Require the canonical manifest's exact schema version value."""
    if "schema_version" not in data:
        return
    value = data["schema_version"]
    if type(value) is not int or value != 2:
        raise CanonicalPackValidationError(
            f"{manifest_path}: schema_version must be exactly integer 2, got {value!r}"
        )

def _validate_schema(data: dict[str, Any], manifest_path: Path) -> None:
    _validate_string_keys(data, "pack")
    validator = jsonschema.Draft202012Validator(_schema())
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.absolute_path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "pack"
        raise CanonicalPackValidationError(f"{manifest_path}: {location}: {error.message}")

def _normalize_permissions(raw: Any) -> tuple[PackPermission, ...]:
    result: list[PackPermission] = []
    seen: set[str] = set()
    for index, item in enumerate(raw or []):
        data = _mapping(item, f"permissions[{index}]")
        permission_id = _text(data["id"], f"permissions[{index}].id")
        if permission_id in seen:
            raise CanonicalPackValidationError(f"permissions contains duplicate {permission_id!r}")
        seen.add(permission_id)
        services = _unique_strings(data.get("services", []), f"permissions[{index}].services")
        result.append(
            PackPermission(
                permission_id,
                _text(data["reason"], f"permissions[{index}].reason"),
                _text(data["access"], f"permissions[{index}].access") if "access" in data else None,
                services,
            )
        )
    return tuple(sorted(result, key=lambda item: item.id))


def _normalize_extensions(raw: Any) -> Mapping[str, Any]:
    if raw is None:
        return MappingProxyType({})
    data = _mapping(raw, "extensions")
    normalized = _normalize_nested_json(data, "extensions")

    def unique_ids(items: Any, path: str) -> None:
        seen: set[str] = set()
        for item in items or []:
            item_id = item.get("id")
            if item_id in seen:
                raise CanonicalPackValidationError(f"{path} contains duplicate ID {item_id!r}")
            seen.add(item_id)

    generation = normalized.get("generation", {})
    unique_ids(generation.get("backends"), "extensions.generation.backends")
    unique_ids(generation.get("features"), "extensions.generation.features")
    unique_ids(generation.get("modes"), "extensions.generation.modes")
    unique_ids(normalized.get("elements", {}).get("kinds"), "extensions.elements.kinds")
    unique_ids(normalized.get("timeline", {}).get("kinds"), "extensions.timeline.kinds")
    unique_ids(normalized.get("artifact_types", {}).get("types"), "extensions.artifact_types.types")

    # Typed resource paths in rendering declarations still receive path checks.
    rendering = normalized.get("rendering", {})
    for family in ("renderers", "planners", "finalizers"):
        seen_paths: set[str] = set()
        for index, path in enumerate(rendering.get(family, [])):
            normalized_path = _relative_path(path, f"extensions.rendering.{family}[{index}]")
            if normalized_path in seen_paths:
                raise CanonicalPackValidationError(
                    f"extensions.rendering.{family} contains duplicate path {normalized_path!r}"
                )
            seen_paths.add(normalized_path)
            rendering[family][index] = normalized_path
    return _freeze(normalized)


def _normalize_database(raw: Any, pack_id: str) -> DatabaseContribution:
    data = _mapping(raw, "database")
    dependencies: list[PackDependency] = []
    seen_dependencies: set[str] = set()
    for index, item in enumerate(data["depends_on"]):
        dependency = _mapping(item, f"database.depends_on[{index}]")
        pack = _text(dependency["pack"], f"database.depends_on[{index}].pack")
        if pack == pack_id:
            raise CanonicalPackValidationError("database.depends_on cannot depend on itself")
        if pack in seen_dependencies:
            raise CanonicalPackValidationError(
                f"database.depends_on contains duplicate pack ID {pack!r}"
            )
        seen_dependencies.add(pack)
        minimum = dependency["min_migration"]
        if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum <= 0:
            raise CanonicalPackValidationError(
                "database.depends_on.min_migration must be a positive integer"
            )
        dependencies.append(PackDependency(pack, minimum))

    migrations: list[MigrationDescriptor] = []
    previous = 0
    names: set[str] = set()
    paths: set[str] = set()
    owned_tables: set[str] = set()
    for index, item in enumerate(data["migrations"]):
        migration = _mapping(item, f"database.migrations[{index}]")
        version = migration["version"]
        if isinstance(version, bool) or not isinstance(version, int) or version <= previous:
            raise CanonicalPackValidationError(
                "database migrations must have strictly increasing positive versions"
            )
        name = _text(migration["name"], f"database.migrations[{index}].name")
        path = _relative_path(migration["path"], f"database.migrations[{index}].path")
        if (
            not _MIGRATION_NAME.fullmatch(name)
            or name in names
            or path in paths
            or not path.endswith(".sql")
        ):
            raise CanonicalPackValidationError(
                f"database.migrations[{index}] has duplicate or invalid name/path"
            )
        tables = _unique_strings(
            migration["tables"], f"database.migrations[{index}].tables", pattern=_LOWER_IDENT
        )
        duplicate_tables = owned_tables.intersection(tables)
        if duplicate_tables:
            raise CanonicalPackValidationError(
                "database migrations duplicate table ownership: "
                + ", ".join(sorted(duplicate_tables))
            )
        owned_tables.update(tables)
        names.add(name)
        paths.add(path)
        previous = version
        migrations.append(MigrationDescriptor(version, name, path, tables))

    def vocab(name: str) -> tuple[str, ...]:
        return _unique_strings(data[name], f"database.{name}", pattern=_VOCABULARY)

    def lower(name: str) -> tuple[str, ...]:
        return _unique_strings(data[name], f"database.{name}", pattern=_LOWER_IDENT)

    repositories = _unique_strings(
        data["repositories"],
        "database.repositories",
        pattern=re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$"),
    )
    mounts: dict[str, str] = {}
    cli_mounts = _mapping(data["cli_mounts"], "database.cli_mounts")
    for key, value in sorted(cli_mounts.items()):
        if (
            not _LOWER_IDENT.fullmatch(key)
            or not isinstance(value, str)
            or not value
            or any(not _LOWER_IDENT.fullmatch(token) for token in value.split(" "))
        ):
            raise CanonicalPackValidationError(f"database.cli_mounts has invalid mount {key!r}")
        mounts[key] = value
    return DatabaseContribution(
        bool(data["default_enabled"]),
        tuple(sorted(dependencies, key=lambda item: item.pack)),
        tuple(migrations),
        vocab("stream_types"),
        vocab("event_kinds"),
        vocab("command_kinds"),
        repositories,
        lower("conformance"),
        MappingProxyType(mounts),
        lower("bridge_mounts"),
    )


def _normalize_definition(data: dict[str, Any], manifest_path: Path) -> CanonicalPackDefinition:
    pack_id = _text(data["id"], "id")
    if not _PACK_ID.fullmatch(pack_id):
        raise CanonicalPackValidationError("id must match the canonical pack identifier grammar")
    status = data.get("status", "active")
    return CanonicalPackDefinition(
        schema_version=2,
        id=pack_id,
        name=_text(data["name"], "name"),
        version=_text(data["version"], "version"),
        description=_text(data.get("description", ""), "description", non_blank=False).strip(),
        status=status,
        visibility=data.get("visibility", "visible"),
        domain=data.get("domain", "general"),
        stability=data.get("stability", "stable"),
        support=data.get("support", "project"),
        keywords=_unique_strings(
            data.get("keywords", []), "keywords", pattern=re.compile(r"^[a-z0-9][a-z0-9_-]*$")
        ),
        capabilities=_unique_strings(
            data.get("capabilities", []), "capabilities", pattern=_LOWER_IDENT
        ),
        permissions=_normalize_permissions(data.get("permissions", [])),
        content=MappingProxyType(
            {
                key: _relative_path(value, f"content.{key}")
                for key, value in sorted(_mapping(data.get("content", {}), "content").items())
            }
        ),
        extensions=_normalize_extensions(data.get("extensions", {})),
        aliases=_normalize_aliases(data.get("aliases", []), pack_id),
        agent=_normalize_agent(data.get("agent", {})),
        documentation=_normalize_documentation(data.get("documentation")),
        secrets=_normalize_secrets(data.get("secrets", [])),
        dependencies=_normalize_dependencies(data.get("dependencies", {})),
        astrid_version=data.get("astrid_version"),
        database=_normalize_database(data["database"], pack_id) if "database" in data else None,
        resources=_normalize_resources(data.get("resources", [])),
        authoring_only=_normalize_authoring(data.get("authoring_only", [])),
    )


def _normalize_aliases(raw: Any, pack_id: str) -> tuple[Mapping[str, str], ...]:
    result: list[Mapping[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(raw):
        data = _mapping(item, f"aliases[{index}]")
        kind = _text(data["kind"], f"aliases[{index}].kind")
        alias = _text(data["alias"], f"aliases[{index}].alias")
        canonical = _text(data["canonical_id"], f"aliases[{index}].canonical_id")
        if (
            not _QUALIFIED.fullmatch(alias)
            or not _QUALIFIED.fullmatch(canonical)
            or alias == canonical
            or alias.split(".")[0] != pack_id
            or canonical.split(".")[0] != pack_id
        ):
            raise CanonicalPackValidationError(
                f"aliases[{index}] must be distinct IDs owned by {pack_id!r}"
            )
        if (kind, alias) in seen:
            raise CanonicalPackValidationError(f"aliases contains duplicate {kind}/{alias}")
        seen.add((kind, alias))
        result.append(MappingProxyType({"kind": kind, "alias": alias, "canonical_id": canonical}))
    return tuple(sorted(result, key=lambda item: (item["kind"], item["alias"])))


def _normalize_agent(raw: Any) -> Mapping[str, Any]:
    data = _mapping(raw, "agent")
    result: dict[str, Any] = {}
    for key in ("purpose", "do_not_use_for"):
        if key in data:
            result[key] = _text(data[key], f"agent.{key}")
    if "normal_entrypoints" in data:
        result["normal_entrypoints"] = tuple(
            _text(item, "agent.normal_entrypoints[]") for item in data["normal_entrypoints"]
        )
    if "required_context" in data:
        result["required_context"] = tuple(
            _relative_path(item, "agent.required_context[]")
            for item in _unique_strings(data["required_context"], "agent.required_context")
        )
    return _freeze(result)


def _normalize_documentation(raw: Any) -> Documentation | None:
    if raw is None:
        return None
    data = _mapping(raw, "documentation")
    kind = data["kind"]
    if kind == "none":
        return Documentation(kind, reason=_text(data["reason"], "documentation.reason"))
    return Documentation(kind, path=data["path"])


def _normalize_secrets(raw: Any) -> tuple[Mapping[str, Any], ...]:
    result = []
    seen = set()
    for index, item in enumerate(raw):
        data = _mapping(item, f"secrets[{index}]")
        name = _text(data["name"], f"secrets[{index}].name")
        if name in seen:
            raise CanonicalPackValidationError(f"secrets contains duplicate {name!r}")
        seen.add(name)
        result.append(
            _freeze(
                {
                    "name": name,
                    "required": bool(data.get("required", False)),
                    **(
                        {"description": data["description"].strip()}
                        if "description" in data
                        else {}
                    ),
                }
            )
        )
    return tuple(sorted(result, key=lambda item: item["name"]))


def _normalize_dependencies(raw: Any) -> Mapping[str, tuple[str, ...]]:
    data = _mapping(raw, "dependencies")
    result = {}
    for key in ("python", "npm", "system"):
        result[key] = _unique_strings(data.get(key, []), f"dependencies.{key}")
    return MappingProxyType(result)


def _normalize_resources(raw: Any, *, field: str = "resources") -> tuple[ResourceDeclaration, ...]:
    result = []
    seen = set()
    for index, item in enumerate(raw):
        data = _mapping(item, f"{field}[{index}]")
        path = _relative_path(data["path"], f"{field}[{index}].path")
        if path in seen:
            raise CanonicalPackValidationError(f"{field} contains duplicate path {path!r}")
        seen.add(path)
        result.append(ResourceDeclaration(path, data["kind"]))
    return tuple(sorted(result, key=lambda item: item.path))


def _normalize_authoring(raw: Any) -> tuple[AuthoringExclusion, ...]:
    result = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        data = _mapping(item, f"authoring_only[{index}]")
        path = _relative_path(data["path"], f"authoring_only[{index}].path")
        if path in seen:
            raise CanonicalPackValidationError(
                f"authoring_only contains duplicate path {path!r}"
            )
        seen.add(path)
        result.append(
            AuthoringExclusion(
                path,
                data["kind"],
                _text(data["reason"], f"authoring_only[{index}].reason"),
            )
        )
    return tuple(sorted(result, key=lambda item: item.path))


def _declared_paths(definition: CanonicalPackDefinition) -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    for key, path in definition.content.items():
        paths.append((path, f"content:{key}"))
    for path in definition.agent.get("required_context", ()):
        paths.append((path, "agent.required_context"))
    if definition.documentation and definition.documentation.path:
        paths.append((definition.documentation.path, "documentation"))
    if definition.database:
        paths.extend(
            (migration.path, "database.migration") for migration in definition.database.migrations
        )
    rendering = definition.extensions.get("rendering", {})
    for family in ("renderers", "planners", "finalizers"):
        paths.extend((path, f"extensions.rendering:{family}") for path in rendering.get(family, ()))
    paths.extend((item.path, f"resource:{item.kind}") for item in definition.resources)
    paths.extend((item.path, f"authoring_only:{item.kind}") for item in definition.authoring_only)
    for path, role in paths:
        if path == CANONICAL_MANIFEST_NAME:
            raise CanonicalPackValidationError(
                f"{role} cannot declare the canonical manifest {CANONICAL_MANIFEST_NAME!r}"
            )
    return sorted(paths)


def _provenance_identity(definition: CanonicalPackDefinition, paths: list[tuple[str, str]]) -> str:
    payload = {
        "schema": "astrid.pack_provenance.v1",
        "definition": definition.to_dict(),
        "declared_paths": [{"path": path, "role": role} for path, role in paths],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def _validate_pack_tree(root: Path) -> None:
    """Reject symlinks anywhere in a canonical pack before resource reads."""
    try:
        for child in root.rglob("*"):
            if child.is_symlink():
                raise CanonicalPackValidationError(
                    f"pack tree contains symlinked path: {child.relative_to(root)}"
                )
            resolved = child.resolve(strict=False)
            if not resolved.is_relative_to(root):
                raise CanonicalPackValidationError(
                    f"pack tree path escapes owner root: {child.relative_to(root)}"
                )
    except OSError as exc:
        raise CanonicalPackValidationError(
            f"cannot inspect canonical pack tree {root}: {exc}"
        ) from exc

def _resource_handle(root: Path, path: str, kind: str) -> ResourceHandle:
    candidate = root.joinpath(*path.split("/"))
    try:
        reject_symlinked_path(candidate)
    except SymlinkedPackPathError as exc:
        raise CanonicalPackValidationError(f"resource {path!r} contains a symlink") from exc
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise CanonicalPackValidationError(f"resource {path!r} escapes owner root")
    if not candidate.exists():
        raise CanonicalPackValidationError(f"resource {path!r} does not exist")
    if candidate.is_dir():
        return ResourceHandle(path, root, resolved, kind, "directory", 0, "")
    if not candidate.is_file():
        raise CanonicalPackValidationError(f"resource {path!r} is not a regular file")
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    return ResourceHandle(path, root, resolved, kind, "file", candidate.stat().st_size, digest)


def _resolve_resources(
    root: Path, definition: CanonicalPackDefinition
) -> tuple[ResourceHandle, ...]:
    handles: dict[str, ResourceHandle] = {}
    declaration_roles: dict[str, str] = {}
    authoring_paths = {item.path for item in definition.authoring_only}

    def add_handle(handle: ResourceHandle, role: str) -> None:
        prior_role = declaration_roles.get(handle.path)
        if prior_role is not None and prior_role != role:
            raise CanonicalPackValidationError(
                f"resource {handle.path!r} has overlapping declarations ({prior_role} and {role})"
            )
        declaration_roles[handle.path] = role
        handles[handle.path] = handle

    for path, role in _declared_paths(definition):
        if role.startswith("authoring_only:"):
            continue
        if any(path == excluded or path.startswith(excluded + "/") for excluded in authoring_paths):
            raise CanonicalPackValidationError(
                f"runtime resource {path!r} overlaps authoring-only path"
            )
        expected_kind = "directory" if role.startswith("content:") else None
        if role in {
            "documentation",
            "agent.required_context",
            "database.migration",
        } or role.startswith("extensions.rendering:"):
            expected_kind = "file"
        handle = _resource_handle(root, path, role)
        if expected_kind is not None and handle.file_kind != expected_kind:
            raise CanonicalPackValidationError(
                f"resource {path!r} must resolve to a {expected_kind}"
            )
        if handle.file_kind == "directory":
            directory = root / path
            for child in sorted(directory.rglob("*"), key=lambda item: item.as_posix()):
                rel = child.relative_to(root).as_posix()
                if any(rel == excluded or rel.startswith(excluded + "/") for excluded in authoring_paths):
                    continue
                if child.is_symlink():
                    raise CanonicalPackValidationError(f"resource {rel!r} contains a symlink")
                if child.is_file():
                    add_handle(_resource_handle(root, rel, role), role)
        else:
            add_handle(handle, role)

    return tuple(handles[path] for path in sorted(handles))


def _validate_canonical_manifest_path(manifest_path: str | Path) -> Path:
    """Validate canonical manifest custody without reading its bytes."""
    path = Path(manifest_path).expanduser()
    if path.name != CANONICAL_MANIFEST_NAME:
        raise CanonicalPackValidationError(
            f"canonical manifest filename must be exactly {CANONICAL_MANIFEST_NAME!r}"
        )
    try:
        root = reject_symlinked_path(path.parent)
    except SymlinkedPackPathError as exc:
        if path.parent.is_symlink():
            message = f"pack root must not be a symlink: {path.parent}"
        else:
            message = f"pack root contains a symlinked ancestor: {path.parent}"
        raise CanonicalPackValidationError(message) from exc
    if path.is_symlink() or not path.is_file():
        raise CanonicalPackValidationError(f"canonical manifest is not a regular file: {path}")
    root = root.resolve()
    if root.name.startswith(".") or not root.is_dir():
        raise CanonicalPackValidationError(f"invalid pack root: {root}")
    try:
        resolved = path.resolve(strict=False)
    except OSError as exc:
        raise CanonicalPackValidationError(
            f"cannot resolve canonical manifest {path}: {exc}"
        ) from exc
    if not resolved.is_relative_to(root):
        raise CanonicalPackValidationError(f"canonical manifest escapes owner root: {path}")
    return path


def canonical_manifest_path(pack_root: str | Path) -> Path | None:
    """Return a present, confined ``pack.yaml`` without reading its bytes."""
    root = Path(pack_root).expanduser()
    candidate = root / CANONICAL_MANIFEST_NAME
    if not candidate.exists() and not candidate.is_symlink():
        return None
    return _validate_canonical_manifest_path(candidate)


def _read_normalize_validate(
    manifest_path: str | Path,
    *,
    provenance_source: str,
    admission: object | None,
    resolve_resources: bool,
    expected_pack_id: str | None = None,
) -> CanonicalPackEntry:
    """Read one manifest after the caller's admission authority is established."""
    path = _validate_canonical_manifest_path(manifest_path)
    root = path.parent.resolve()
    _validate_pack_tree(root)
    legacy = sorted(
        name
        for name in LEGACY_MANIFEST_NAMES
        if (root / name).exists() or (root / name).is_symlink()
    )
    if legacy:
        raise CanonicalPackValidationError(
            f"legacy/alternate manifest(s) beside canonical pack: {', '.join(legacy)}"
        )
    try:
        data = load_manifest_mapping(
            path, manifest_kind="canonical pack", reject_duplicate_keys=True
        )
    except Exception as exc:
        if isinstance(exc, CanonicalPackError):
            raise
        raise CanonicalPackValidationError(str(exc)) from exc
    _validate_schema_version(data, path)
    _validate_schema(data, path)
    definition = _normalize_definition(data, path)
    if expected_pack_id is None and root.name != definition.id:
        raise CanonicalPackValidationError(
            f"pack id {definition.id!r} must match folder name {root.name!r}"
        )
    if expected_pack_id is not None and definition.id != expected_pack_id:
        raise CanonicalPackValidationError(
            f"staged pack id {definition.id!r} does not match expected pack id "
            f"{expected_pack_id!r}"
        )
    if not any(
        (
            definition.capabilities,
            definition.content,
            definition.extensions,
            definition.documentation and definition.documentation.kind != "none",
            definition.database,
            definition.resources,
        )
    ):
        raise CanonicalPackValidationError(
            "pack must contribute capabilities, content, extensions, documentation, "
            "database, or resources"
        )

    declared = _declared_paths(definition)
    identity = _provenance_identity(definition, declared)
    if (
        admission is not _BUNDLED_ADMISSION
        and admission is not _STATIC_VALIDATION_ADMISSION
        and definition.database is not None
    ):
        raise ExternalDatabaseForbidden(f"external pack {definition.id!r} cannot declare database")
    resources = _resolve_resources(root, definition) if resolve_resources else ()
    manifest_handle = _resource_handle(root, CANONICAL_MANIFEST_NAME, "manifest")
    return CanonicalPackEntry(
        definition,
        CatalogProvenance(provenance_source, identity, root),
        manifest_handle,
        resources,
        definition.authoring_only,
    )


def read_normalize_validate(
    manifest_path: str | Path,
    *,
    source: ExternalPackSource | str,
    resolve_resources: bool = True,
    expected_pack_id: str | None = None,
) -> CanonicalPackEntry:
    """Admit a canonical pack from one supported external source seam.

    Bundled trust is intentionally unavailable here; only ``BundledCatalog``
    holds the private admission marker that permits database contributions.
    """
    if isinstance(source, ExternalPackSource):
        source_value = source.value
    elif isinstance(source, str) and source in {
        item.value for item in ExternalPackSource
    }:
        source_value = source
    else:
        raise CanonicalPackValidationError(
            "source must be one of: "
            + ", ".join(item.value for item in ExternalPackSource)
        )
    return _read_normalize_validate(
        manifest_path,
        provenance_source=source_value,
        admission=None,
        resolve_resources=resolve_resources,
        expected_pack_id=expected_pack_id,
    )


def _validate_staged_canonical_pack(
    pack_root: str | Path, expected_pack_id: str
) -> CanonicalPackEntry:
    root = Path(pack_root)
    return _read_normalize_validate(
        root / CANONICAL_MANIFEST_NAME,
        provenance_source=ExternalPackSource.INSTALLED.value,
        admission=None,
        resolve_resources=True,
        expected_pack_id=expected_pack_id,
    )


def validate_canonical_pack(pack_root: str | Path) -> CanonicalPackEntry:
    """Statically validate one isolated fixture, including database declarations."""
    root = Path(pack_root)
    return _read_normalize_validate(
        root / CANONICAL_MANIFEST_NAME,
        provenance_source=_VALIDATION_SOURCE,
        admission=_STATIC_VALIDATION_ADMISSION,
        resolve_resources=True,
    )


@dataclass(frozen=True, slots=True)
class BundledCatalog:
    root: Path
    entries: tuple[CanonicalPackEntry, ...]

    @classmethod
    def from_root(cls, root: str | Path) -> "BundledCatalog":
        try:
            supplied = reject_symlinked_path(Path(root).expanduser())
        except SymlinkedPackPathError as exc:
            raise CanonicalPackValidationError(
                f"catalog root must not contain a symlink: {root}"
            ) from exc
        resolved = supplied.resolve()
        if not resolved.is_dir():
            raise CanonicalPackValidationError(f"catalog root is not a directory: {resolved}")
        entries: list[CanonicalPackEntry] = []
        for child in sorted(resolved.iterdir(), key=lambda item: item.name):
            if child.is_symlink():
                raise CanonicalPackValidationError(
                    f"bundled pack directory must not be a symlink: {child}"
                )
            if not child.is_dir() or child.name == "_core" or child.name.startswith("."):
                continue

            present = {item.name for item in child.iterdir()}
            legacy = present & LEGACY_MANIFEST_NAMES
            if legacy or CANONICAL_MANIFEST_NAME in present:
                if legacy:
                    raise CanonicalPackValidationError(
                        f"legacy/alternate manifest(s) in {child}: {', '.join(sorted(legacy))}"
                    )
                entries.append(
                    _read_normalize_validate(
                        child / CANONICAL_MANIFEST_NAME,
                        provenance_source="bundled",
                        admission=_BUNDLED_ADMISSION,
                        resolve_resources=True,
                    )
                )
        ids = [entry.id for entry in entries]
        if len(ids) != len(set(ids)):
            raise CanonicalPackValidationError("catalog contains duplicate pack IDs")
        by_id = {entry.id: entry for entry in entries}

        owners: dict[str, dict[str, str]] = {
            "table": {},
            "stream type": {},
            "event kind": {},
            "command kind": {},
            "repository": {},
            "CLI mount": {},
            "bridge mount": {},
        }
        for entry in sorted(entries, key=lambda item: item.id):
            database = entry.database
            if database is None:
                continue
            declarations = {
                "table": (table for migration in database.migrations for table in migration.tables),
                "stream type": iter(database.stream_types),
                "event kind": iter(database.event_kinds),
                "command kind": iter(database.command_kinds),
                "repository": iter(database.repositories),
                "CLI mount": iter(database.cli_mounts),
                "bridge mount": iter(database.bridge_mounts),
            }
            for label, values in declarations.items():
                for value in values:
                    prior = owners[label].get(value)
                    if prior is not None:
                        raise CanonicalPackValidationError(
                            f"catalog {label} {value!r} is declared by both "
                            f"{prior!r} and {entry.id!r}"
                        )
                    owners[label][value] = entry.id

        # ``core`` is an irreducible code-owned projection, not a bundled
        # catalog entry.  Catalog validation still checks its reserved
        # dependency head so a product catalog can omit a fake core pack.
        from astrid.core.migrations.catalog import CORE_MIGRATIONS, CORE_PACK

        core_head = max((migration.version for migration in CORE_MIGRATIONS), default=0)
        for entry in entries:
            if entry.database is None:
                continue
            for dependency in entry.database.depends_on:
                target = by_id.get(dependency.pack)
                if dependency.pack == CORE_PACK:
                    if core_head < dependency.min_migration:
                        raise CanonicalPackValidationError(
                            f"{entry.id}: dependency {dependency.pack!r} has migration head "
                            f"{core_head}, requires {dependency.min_migration}"
                        )
                    continue
                if target is None or target.database is None:
                    raise CanonicalPackValidationError(
                        f"{entry.id}: database dependency {dependency.pack!r} is missing or not database-bearing"
                    )
                if target.database.migration_head < dependency.min_migration:
                    raise CanonicalPackValidationError(
                        f"{entry.id}: dependency {dependency.pack!r} has migration head "
                        f"{target.database.migration_head}, requires {dependency.min_migration}"
                    )
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(pack_id: str) -> None:
            if pack_id in visiting:
                raise CanonicalPackValidationError(
                    f"catalog database dependencies contain a cycle at {pack_id!r}"
                )
            if pack_id in visited:
                return
            visiting.add(pack_id)
            entry = by_id[pack_id]
            if entry.database:
                for dependency in entry.database.depends_on:
                    if dependency.pack == CORE_PACK:
                        continue
                    visit(dependency.pack)
            visiting.remove(pack_id)
            visited.add(pack_id)

        for pack_id in sorted(by_id):
            visit(pack_id)
        return cls(resolved, tuple(sorted(entries, key=lambda entry: entry.id)))

    @property
    def entries_by_id(self) -> Mapping[str, CanonicalPackEntry]:
        return MappingProxyType({entry.id: entry for entry in self.entries})

    @property
    def ordered_entries(self) -> tuple[CanonicalPackEntry, ...]:
        return self.entries

    def get(self, pack_id: str) -> CanonicalPackEntry:
        try:
            return self.entries_by_id[pack_id]
        except KeyError as exc:
            raise KeyError(f"unknown canonical pack {pack_id!r}") from exc

    @property
    def capabilities(self) -> tuple[CapabilityProjection, ...]:
        return tuple(entry.capability_projection() for entry in self.entries)

    @property
    def databases(self) -> tuple[DatabaseProjection, ...]:
        return tuple(
            projection
            for entry in self.entries
            if (projection := entry.database_projection()) is not None
        )

    @property
    def resources(self) -> tuple[ResourceProjection, ...]:
        return tuple(entry.resource_projection() for entry in self.entries)

    @property
    def documentation(self) -> tuple[DocumentationProjection, ...]:
        return tuple(entry.documentation_projection() for entry in self.entries)




def _core_database_projection() -> tuple[str, DatabaseContribution, Path, tuple[ResourceHandle, ...]]:
    """Build the reserved kernel database projection from audited code declarations."""
    from astrid.core.events.registry import (
        CORE_COMMAND_KINDS,
        CORE_CONFORMANCE_DIMENSIONS,
        CORE_EVENT_KINDS,
        CORE_PACK_ID,
        CORE_REPOSITORIES,
        CORE_STREAM_TYPES,
    )
    from astrid.core.migrations.catalog import CORE_MIGRATIONS, core_sql_path

    declared = CORE_MIGRATIONS
    migrations = tuple(
        MigrationDescriptor(
            version=descriptor.version,
            name=descriptor.name,
            path=descriptor.path,
            tables=tuple(sorted(descriptor.owned_tables)),
        )
        for descriptor in declared
    )
    database = DatabaseContribution(
        default_enabled=True,
        depends_on=(),
        migrations=migrations,
        stream_types=tuple(CORE_STREAM_TYPES),
        event_kinds=tuple(CORE_EVENT_KINDS),
        command_kinds=tuple(CORE_COMMAND_KINDS),
        repositories=tuple(CORE_REPOSITORIES),
        conformance=tuple(CORE_CONFORMANCE_DIMENSIONS),
        cli_mounts=MappingProxyType({}),
        bridge_mounts=(),
    )
    sql_path = core_sql_path().resolve()
    owner_root = sql_path.parents[2]
    handles = tuple(
        _resource_handle(owner_root, descriptor.path, "database.migration")
        for descriptor in declared
    )
    return CORE_PACK_ID, database, owner_root, handles


def _normalise_projection_ids(value: Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CanonicalPackValidationError(
            "additional_pack_ids must be a sequence of pack IDs"
        )
    result: list[str] = []
    seen: set[str] = set()
    for index, pack_id in enumerate(value):
        if not isinstance(pack_id, str) or not _PACK_ID.fullmatch(pack_id):
            raise CanonicalPackValidationError(
                f"additional_pack_ids[{index}] must be a valid pack ID"
            )
        if pack_id in seen:
            raise CanonicalPackValidationError(
                f"additional_pack_ids contains duplicate pack ID {pack_id!r}"
            )
        seen.add(pack_id)
        result.append(pack_id)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class DatabasePackProjection:
    """Compose selected canonical database entries into the schema registry."""

    catalog: BundledCatalog
    additional_pack_ids: tuple[str, ...] = ()

    def project(self) -> FrozenSchemaPackRegistry:
        from astrid.core.schema_packs.registry import SchemaPackRegistry

        if not isinstance(self.catalog, BundledCatalog):
            raise CanonicalPackValidationError("catalog must be a BundledCatalog")
        explicit = _normalise_projection_ids(self.additional_pack_ids)
        if "core" in explicit:
            raise CanonicalPackValidationError(
                "product core is reserved and cannot be explicitly selected"
            )
        entries_by_id = self.catalog.entries_by_id
        if "core" in entries_by_id:
            raise CanonicalPackValidationError(
                "catalog must not contain the reserved product core pack"
            )
        missing = sorted(pack_id for pack_id in explicit if pack_id not in entries_by_id)
        if missing:
            raise CanonicalPackValidationError(
                "additional_pack_ids contains unknown pack ID(s): " + ", ".join(missing)
            )

        explicit_set = set(explicit)
        selected = [
            entry
            for entry in self.catalog.entries
            if entry.database is not None
            and (entry.database.default_enabled or entry.id in explicit_set)
        ]
        for entry in self.catalog.entries:
            if entry.id in explicit_set and entry.database is None:
                raise CanonicalPackValidationError(
                    f"explicit database pack {entry.id!r} is not database-bearing"
                )

        core_id, core_database, core_root, core_resources = _core_database_projection()
        available: dict[str, DatabaseContribution] = {core_id: core_database}
        available.update(
            {entry.id: entry.database for entry in selected if entry.database is not None}
        )
        for entry in selected:
            assert entry.database is not None
            for dependency in entry.database.depends_on:
                target = available.get(dependency.pack)
                if target is None:
                    raise CanonicalPackValidationError(
                        f"{entry.id}: database dependency {dependency.pack!r} "
                        "is not selected or is not database-bearing"
                    )
                if target.migration_head < dependency.min_migration:
                    raise CanonicalPackValidationError(
                        f"{entry.id}: dependency {dependency.pack!r} has migration head "
                        f"{target.migration_head}, requires {dependency.min_migration}"
                    )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(pack_id: str) -> None:
            if pack_id in visiting:
                raise CanonicalPackValidationError(
                    f"selected database dependencies contain a cycle at {pack_id!r}"
                )
            if pack_id in visited:
                return
            visiting.add(pack_id)
            for dependency in available[pack_id].depends_on:
                visit(dependency.pack)
            visiting.remove(pack_id)
            visited.add(pack_id)

        for pack_id in sorted(available):
            visit(pack_id)

        for entry in selected:
            reachable: set[str] = set()
            stack = [entry.id]
            while stack:
                current = stack.pop()
                if current in reachable:
                    continue
                reachable.add(current)
                stack.extend(dependency.pack for dependency in available[current].depends_on)
            if core_id not in reachable:
                raise CanonicalPackValidationError(
                    f"{entry.id}: database dependency graph cannot reach reserved core"
                )

        registry = SchemaPackRegistry()
        registry.register_database_projection(
            core_id,
            core_database,
            owner_root=core_root,
            resources=core_resources,
        )
        for entry in sorted(selected, key=lambda item: item.id):
            registry.register_database_projection(entry)
        return registry.freeze()


def project_catalog_database(
    catalog: BundledCatalog, additional_pack_ids: Sequence[str] = ()
) -> FrozenSchemaPackRegistry:
    """Project default-enabled and explicitly selected database packs."""
    return DatabasePackProjection(catalog, tuple(additional_pack_ids)).project()


def catalog_from_root(root: str | Path) -> BundledCatalog:
    return BundledCatalog.from_root(root)


__all__ = [
    "AuthoringExclusion",
    "BundledCatalog",
    "CanonicalPackDefinition",
    "CanonicalPackEntry",
    "CanonicalPackError",
    "CanonicalPackValidationError",
    "CapabilityProjection",
    "CatalogProvenance",
    "DatabaseContribution",
    "DatabasePackProjection",
    "DatabaseProjection",
    "Documentation",
    "DocumentationProjection",
    "ExternalDatabaseForbidden",
    "ExternalPackSource",
    "MigrationDescriptor",
    "PackDependency",
    "read_normalize_validate",
    "canonical_manifest_path",
    "ResourceDeclaration",
    "ResourceHandle",
    "ResourceProjection",
    "project_catalog_database",
    "catalog_from_root",
    "validate_canonical_pack",
]
