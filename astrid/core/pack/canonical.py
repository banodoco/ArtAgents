"""Strict, read-only canonical pack v2 capability catalog.

The neutral workspace runtime owns product state, schemas, and migrations.
This module therefore admits only executable capability, documentation, and
resource declarations; a ``database`` field fails closed before projection.
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
from typing import Any, Mapping

import jsonschema
import yaml


class SymlinkedPackPathError(ValueError):
    """A canonical pack path contains a symlinked component."""


def reject_symlinked_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    # Do not reject operating-system aliases in ancestors such as macOS's
    # /var -> /private/var.  The pack-tree walk below checks every component
    # owned by the pack itself; this helper guards the supplied node.
    if candidate.is_symlink():
        raise SymlinkedPackPathError(f"pack path contains a symlink: {candidate}")
    return candidate


CANONICAL_MANIFEST_NAME = "pack.yaml"
LEGACY_MANIFEST_NAMES = frozenset({"pack.yml", "pack.json", "schema-" + "pack.yaml"})
_SCHEMA_PATH = Path(__file__).with_name("schemas") / "v2" / "pack.json"
_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")
_QUALIFIED = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_RELEASE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


class CanonicalPackError(ValueError):
    """Base error for canonical manifest admission."""


class CanonicalPackValidationError(CanonicalPackError):
    """A manifest or its declared resource tree violates v2."""


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise CanonicalPackValidationError(f"{path} must be an object with string keys")
    return value


def _text(value: Any, path: str, *, blank: bool = False) -> str:
    if not isinstance(value, str) or (not blank and not value.strip()):
        raise CanonicalPackValidationError(f"{path} must be non-blank text")
    return value.strip() if not blank else value


def _strings(value: Any, path: str, pattern: re.Pattern[str] | None = None) -> tuple[str, ...]:
    if value is None:
        value = []
    if not isinstance(value, list):
        raise CanonicalPackValidationError(f"{path} must be an array")
    result: list[str] = []
    for index, item in enumerate(value):
        item = _text(item, f"{path}[{index}]")
        if pattern is not None and not pattern.fullmatch(item):
            raise CanonicalPackValidationError(f"{path}[{index}] has invalid identifier {item!r}")
        if item in result:
            raise CanonicalPackValidationError(f"{path} contains duplicate {item!r}")
        result.append(item)
    return tuple(sorted(result))


def _relative(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise CanonicalPackValidationError(f"{path} must be a POSIX-relative path")
    parts = value.split("/")
    if value.startswith("/") or any(
        not part or part in {".", ".."} or not _PATH_SEGMENT.fullmatch(part) for part in parts
    ):
        raise CanonicalPackValidationError(f"{path} must be a safe POSIX-relative path")
    return PurePosixPath(*parts).as_posix()


def _freeze(value: Any, path: str = "manifest") -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        raise CanonicalPackValidationError(f"{path} must contain finite JSON numbers")
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise CanonicalPackValidationError(f"{path} object keys must be strings")
        return MappingProxyType({k: _freeze(v, f"{path}.{k}") for k, v in sorted(value.items())})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item, f"{path}[]") for item in value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise CanonicalPackValidationError(f"{path} must contain JSON values")


class _UniqueLoader(yaml.SafeLoader):
    pass


def _construct_mapping(
    loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[str, Any]:
    pairs = loader.construct_pairs(node, deep=deep)
    result: dict[str, Any] = {}
    for key, value in pairs:
        if not isinstance(key, str):
            raise CanonicalPackValidationError("manifest object keys must be strings")
        if key in result:
            raise CanonicalPackValidationError(f"manifest contains duplicate key {key!r}")
        result[key] = value
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


@dataclass(frozen=True, slots=True)
class PackPermission:
    id: str
    reason: str
    access: str | None = None
    services: tuple[str, ...] = ()


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
    resources: tuple[ResourceDeclaration, ...]
    authoring_only: tuple[AuthoringExclusion, ...]

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
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
                    "id": p.id,
                    "reason": p.reason,
                    **({"access": p.access} if p.access else {}),
                    **({"services": list(p.services)} if p.services else {}),
                }
                for p in self.permissions
            ],
            "content": dict(self.content),
            "extensions": _thaw(self.extensions),
            "aliases": [_thaw(v) for v in self.aliases],
            "agent": _thaw(self.agent),
            "secrets": [_thaw(v) for v in self.secrets],
            "dependencies": _thaw(self.dependencies),
            "resources": [{"path": r.path, "kind": r.kind} for r in self.resources],
            "authoring_only": [
                {"path": a.path, "kind": a.kind, "reason": a.reason} for a in self.authoring_only
            ],
        }
        if self.documentation:
            result["documentation"] = {
                "kind": self.documentation.kind,
                **({"path": self.documentation.path} if self.documentation.path else {}),
                **({"reason": self.documentation.reason} if self.documentation.reason else {}),
            }
        if self.astrid_version:
            result["astrid_version"] = self.astrid_version
        return result

    @property
    def normalized(self) -> Mapping[str, Any]:
        return _freeze(self.to_dict())


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


@dataclass(frozen=True, slots=True)
class CapabilityProjection:
    pack_id: str
    capabilities: tuple[str, ...]
    content: Mapping[str, str]
    extensions: Mapping[str, Any]
    aliases: tuple[Mapping[str, str], ...]
    permissions: tuple[PackPermission, ...]


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

    id = property(lambda self: self.definition.id)
    pack_id = property(lambda self: self.definition.id)
    root = property(lambda self: self.provenance.root)
    source = property(lambda self: self.provenance.source)
    extensions = property(lambda self: self.definition.extensions)
    documentation = property(lambda self: self.definition.documentation)
    resource_handles = property(lambda self: self.resources)

    @property
    def identity(self) -> Mapping[str, str]:
        return MappingProxyType(
            {"id": self.id, "name": self.definition.name, "version": self.definition.version}
        )

    def capability_projection(self) -> CapabilityProjection:
        d = self.definition
        return CapabilityProjection(
            d.id, d.capabilities, d.content, d.extensions, d.aliases, d.permissions
        )

    @property
    def capabilities(self) -> CapabilityProjection:
        return self.capability_projection()

    def resource_projection(self) -> ResourceProjection:
        return ResourceProjection(self.id, self.resources)

    def documentation_projection(self) -> DocumentationProjection:
        required = set(self.definition.agent.get("required_context", ()))
        return DocumentationProjection(
            self.id, self.documentation, tuple(r for r in self.resources if r.path in required)
        )


class ExternalPackSource(str, Enum):
    LOCAL = "local"
    EXTRA = "extra"
    ENV = "env"


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            data = yaml.load(stream, Loader=_UniqueLoader)
    except OSError as exc:
        raise CanonicalPackValidationError(f"cannot read canonical pack {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise CanonicalPackValidationError(f"invalid YAML canonical pack {path}: {exc}") from exc
    return _mapping(data, f"{path}")


def _validate_schema(data: dict[str, Any], path: Path) -> None:
    try:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CanonicalPackError(f"cannot read canonical schema {_SCHEMA_PATH}: {exc}") from exc
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(data),
        key=lambda e: list(e.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(item) for item in error.absolute_path) or "pack"
        raise CanonicalPackValidationError(f"{path}: {location}: {error.message}")


def _normalize_definition(data: dict[str, Any]) -> CanonicalPackDefinition:
    pack_id = _text(data.get("id"), "id")
    if not _IDENT.fullmatch(pack_id):
        raise CanonicalPackValidationError("id has invalid canonical pack identifier")
    version = _text(data.get("version"), "version")
    if not _RELEASE.fullmatch(version):
        raise CanonicalPackValidationError("version must be a release version")
    content = _mapping(data.get("content", {}), "content")
    content_map = MappingProxyType(
        {k: _relative(v, f"content.{k}") for k, v in sorted(content.items())}
    )
    perms: list[PackPermission] = []
    for i, item in enumerate(data.get("permissions", [])):
        x = _mapping(item, f"permissions[{i}]")
        pid = _text(x.get("id"), f"permissions[{i}].id")
        perms.append(
            PackPermission(
                pid,
                _text(x.get("reason"), f"permissions[{i}].reason"),
                _text(x["access"], f"permissions[{i}].access") if "access" in x else None,
                _strings(x.get("services", []), f"permissions[{i}].services"),
            )
        )
    aliases: list[Mapping[str, str]] = []
    for i, item in enumerate(data.get("aliases", [])):
        x = _mapping(item, f"aliases[{i}]")
        alias = _text(x.get("alias"), f"aliases[{i}].alias")
        target = _text(x.get("canonical_id"), f"aliases[{i}].canonical_id")
        if (
            not _QUALIFIED.fullmatch(alias)
            or not _QUALIFIED.fullmatch(target)
            or alias == target
            or alias.split(".")[0] != pack_id
            or target.split(".")[0] != pack_id
        ):
            raise CanonicalPackValidationError(
                f"aliases[{i}] must be distinct IDs owned by {pack_id!r}"
            )
        aliases.append(
            MappingProxyType(
                {
                    "kind": _text(x.get("kind"), f"aliases[{i}].kind"),
                    "alias": alias,
                    "canonical_id": target,
                }
            )
        )
    documentation = None
    if data.get("documentation") is not None:
        x = _mapping(data["documentation"], "documentation")
        kind = _text(x.get("kind"), "documentation.kind")
        documentation = Documentation(kind, x.get("path"), x.get("reason"))
    agent = _mapping(data.get("agent", {}), "agent")
    agent_norm = dict(agent)
    if "required_context" in agent_norm:
        agent_norm["required_context"] = _strings(
            agent_norm["required_context"], "agent.required_context"
        )
    resources: list[ResourceDeclaration] = []
    for i, item in enumerate(data.get("resources", [])):
        x = _mapping(item, f"resources[{i}]")
        resources.append(
            ResourceDeclaration(
                _relative(x.get("path"), f"resources[{i}].path"),
                _text(x.get("kind"), f"resources[{i}].kind"),
            )
        )
    authoring: list[AuthoringExclusion] = []
    for i, item in enumerate(data.get("authoring_only", [])):
        x = _mapping(item, f"authoring_only[{i}]")
        authoring.append(
            AuthoringExclusion(
                _relative(x.get("path"), f"authoring_only[{i}].path"),
                _text(x.get("kind"), f"authoring_only[{i}].kind"),
                _text(x.get("reason"), f"authoring_only[{i}].reason"),
            )
        )
    ext = _freeze(data.get("extensions", {}), "extensions")
    return CanonicalPackDefinition(
        2,
        pack_id,
        _text(data.get("name"), "name"),
        version,
        _text(data.get("description", ""), "description", blank=True).strip(),
        data.get("status", "active"),
        data.get("visibility", "visible"),
        data.get("domain", "general"),
        data.get("stability", "stable"),
        data.get("support", "project"),
        _strings(data.get("keywords", []), "keywords", re.compile(r"^[a-z0-9][a-z0-9_-]*$")),
        _strings(data.get("capabilities", []), "capabilities", _IDENT),
        tuple(sorted(perms, key=lambda p: p.id)),
        content_map,
        ext,
        tuple(sorted(aliases, key=lambda a: (a["kind"], a["alias"]))),
        _freeze(agent_norm, "agent"),
        documentation,
        tuple(),
        MappingProxyType(
            {
                k: _strings(
                    _mapping(data.get("dependencies", {}), "dependencies").get(k, []),
                    f"dependencies.{k}",
                )
                for k in ("python", "npm", "system")
            }
        ),
        _text(data["astrid_version"], "astrid_version") if "astrid_version" in data else None,
        tuple(sorted(resources, key=lambda r: r.path)),
        tuple(sorted(authoring, key=lambda a: a.path)),
    )


def _declared_paths(definition: CanonicalPackDefinition) -> tuple[tuple[str, str], ...]:
    paths: list[tuple[str, str]] = [(v, f"content:{k}") for k, v in definition.content.items()]
    paths += [(v, "agent.required_context") for v in definition.agent.get("required_context", ())]
    if definition.documentation and definition.documentation.path:
        paths.append((definition.documentation.path, "documentation"))
    paths += [(r.path, f"resource:{r.kind}") for r in definition.resources]
    paths += [(a.path, f"authoring_only:{a.kind}") for a in definition.authoring_only]
    for path, role in paths:
        if path == CANONICAL_MANIFEST_NAME:
            raise CanonicalPackValidationError(f"{role} cannot declare {CANONICAL_MANIFEST_NAME!r}")
    return tuple(sorted(paths))


def _resource_handle(root: Path, path: str, kind: str) -> ResourceHandle:
    candidate = root.joinpath(*path.split("/"))
    try:
        reject_symlinked_path(candidate)
    except SymlinkedPackPathError as exc:
        raise CanonicalPackValidationError(f"resource {path!r} contains a symlink") from exc
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root) or not candidate.exists():
        raise CanonicalPackValidationError(f"resource {path!r} is missing or escapes owner root")
    if candidate.is_dir():
        return ResourceHandle(path, root, resolved, kind, "directory", 0, "")
    if not candidate.is_file():
        raise CanonicalPackValidationError(f"resource {path!r} is not a regular file")
    try:
        payload = candidate.read_bytes()
    except OSError as exc:
        raise CanonicalPackValidationError(
            f"resource {path!r} cannot be read: {exc.strerror or exc}"
        ) from exc
    return ResourceHandle(
        path, root, resolved, kind, "file", len(payload), hashlib.sha256(payload).hexdigest()
    )


def _resolve_resources(
    root: Path, definition: CanonicalPackDefinition
) -> tuple[ResourceHandle, ...]:
    excluded = {x.path for x in definition.authoring_only}
    handles: dict[str, ResourceHandle] = {}
    for path, role in _declared_paths(definition):
        if role.startswith("authoring_only:"):
            continue
        if any(path == x or path.startswith(x + "/") for x in excluded):
            raise CanonicalPackValidationError(
                f"runtime resource {path!r} overlaps authoring-only path"
            )
        handle = _resource_handle(root, path, role)
        if role.startswith("content:"):
            for child in sorted(handle.resolved.rglob("*"), key=lambda p: p.as_posix()):
                rel = child.relative_to(root).as_posix()
                if child.is_symlink() or any(rel == x or rel.startswith(x + "/") for x in excluded):
                    raise (
                        CanonicalPackValidationError(
                            f"resource {rel!r} contains a symlink or authoring overlap"
                        )
                        if child.is_symlink()
                        else None
                    )
                if child.is_file():
                    handles[rel] = _resource_handle(root, rel, role)
        else:
            handles[path] = handle
    return tuple(handles[path] for path in sorted(handles))


def _validate_path(manifest_path: str | Path) -> Path:
    path = Path(manifest_path).expanduser()
    if path.name != CANONICAL_MANIFEST_NAME:
        raise CanonicalPackValidationError(
            f"canonical manifest filename must be {CANONICAL_MANIFEST_NAME!r}"
        )
    if path.is_symlink() or not path.is_file():
        raise CanonicalPackValidationError(f"canonical manifest is not a regular file: {path}")
    try:
        if path.parent.is_symlink():
            raise SymlinkedPackPathError(f"pack root is a symlink: {path.parent}")
        root = path.parent.resolve()
    except SymlinkedPackPathError as exc:
        raise CanonicalPackValidationError(
            f"pack root must not contain a symlink: {path.parent}"
        ) from exc
    if root.name.startswith(".") or not root.is_dir():
        raise CanonicalPackValidationError(f"invalid pack root: {root}")
    return path


def _admit(
    manifest_path: str | Path,
    *,
    source: str,
    resolve_resources: bool,
    expected_pack_id: str | None = None,
) -> CanonicalPackEntry:
    path = _validate_path(manifest_path)
    root = path.parent.resolve()
    for child in root.rglob("*"):
        if child.is_symlink() or not child.resolve(strict=False).is_relative_to(root):
            raise CanonicalPackValidationError(
                f"pack tree contains symlink or escaping path: {child}"
            )
    legacy = sorted(
        name
        for name in LEGACY_MANIFEST_NAMES
        if (root / name).exists() or (root / name).is_symlink()
    )
    if legacy:
        raise CanonicalPackValidationError(
            f"legacy/alternate manifest(s) beside canonical pack: {', '.join(legacy)}"
        )
    data = _read_manifest(path)
    if "database" in data:
        raise CanonicalPackValidationError(
            f"{path}: database contributions are forbidden; the neutral workspace runtime owns persistence"
        )
    _validate_schema(data, path)
    if data.get("schema_version") != 2 or type(data.get("schema_version")) is not int:
        raise CanonicalPackValidationError(f"{path}: schema_version must be exactly integer 2")
    definition = _normalize_definition(data)
    if expected_pack_id is not None and definition.id != expected_pack_id:
        raise CanonicalPackValidationError(
            f"staged pack id {definition.id!r} does not match {expected_pack_id!r}"
        )
    if expected_pack_id is None and root.name != definition.id:
        raise CanonicalPackValidationError(
            f"pack id {definition.id!r} must match folder name {root.name!r}"
        )
    declared = _declared_paths(definition)
    identity = hashlib.sha256(
        json.dumps(
            {"definition": definition.to_dict(), "declared_paths": declared},
            sort_keys=True,
            default=list,
        ).encode()
    ).hexdigest()
    resources = _resolve_resources(root, definition) if resolve_resources else ()
    manifest = ResourceHandle(
        CANONICAL_MANIFEST_NAME,
        root,
        path.resolve(),
        "manifest",
        "file",
        path.stat().st_size,
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    return CanonicalPackEntry(
        definition,
        CatalogProvenance(source, identity, root),
        manifest,
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
    value = source.value if isinstance(source, ExternalPackSource) else source
    if value not in {item.value for item in ExternalPackSource}:
        raise CanonicalPackValidationError(
            "source must be one of: " + ", ".join(item.value for item in ExternalPackSource)
        )
    return _admit(
        manifest_path,
        source=value,
        resolve_resources=resolve_resources,
        expected_pack_id=expected_pack_id,
    )


def validate_canonical_pack(pack_root: str | Path) -> CanonicalPackEntry:
    return _admit(
        Path(pack_root) / CANONICAL_MANIFEST_NAME,
        source="validation",
        resolve_resources=True,
    )


def canonical_manifest_path(pack_root: str | Path) -> Path | None:
    candidate = Path(pack_root).expanduser() / CANONICAL_MANIFEST_NAME
    if not candidate.exists() and not candidate.is_symlink():
        return None
    return _validate_path(candidate)


@dataclass(frozen=True, slots=True)
class BundledCatalog:
    root: Path
    entries: tuple[CanonicalPackEntry, ...]

    @classmethod
    def from_root(cls, root: str | Path) -> "BundledCatalog":
        supplied = Path(root).expanduser()
        try:
            resolved = reject_symlinked_path(supplied).resolve()
        except SymlinkedPackPathError as exc:
            raise CanonicalPackValidationError(
                f"catalog root must not contain a symlink: {root}"
            ) from exc
        if not resolved.is_dir():
            raise CanonicalPackValidationError(f"catalog root is not a directory: {resolved}")
        entries: list[CanonicalPackEntry] = []
        for child in sorted(resolved.iterdir(), key=lambda p: p.name):
            if child.is_symlink():
                raise CanonicalPackValidationError(
                    f"bundled pack directory must not be a symlink: {child}"
                )
            if not child.is_dir() or child.name.startswith(".") or child.name == "_core":
                continue
            legacy = {p.name for p in child.iterdir()} & LEGACY_MANIFEST_NAMES
            if legacy:
                raise CanonicalPackValidationError(
                    f"legacy/alternate manifest(s) in {child}: {', '.join(sorted(legacy))}"
                )
            if (child / CANONICAL_MANIFEST_NAME).is_file():
                entries.append(
                    _admit(
                        child / CANONICAL_MANIFEST_NAME,
                        source="bundled",
                        resolve_resources=True,
                    )
                )
        ids = [entry.id for entry in entries]
        if len(ids) != len(set(ids)):
            raise CanonicalPackValidationError("catalog contains duplicate pack IDs")
        return cls(resolved, tuple(sorted(entries, key=lambda e: e.id)))

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
        return tuple(e.capability_projection() for e in self.entries)

    @property
    def resources(self) -> tuple[ResourceProjection, ...]:
        return tuple(e.resource_projection() for e in self.entries)

    @property
    def documentation(self) -> tuple[DocumentationProjection, ...]:
        return tuple(e.documentation_projection() for e in self.entries)


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
    "Documentation",
    "DocumentationProjection",
    "ExternalPackSource",
    "ResourceDeclaration",
    "ResourceHandle",
    "ResourceProjection",
    "canonical_manifest_path",
    "catalog_from_root",
    "read_normalize_validate",
    "validate_canonical_pack",
]
