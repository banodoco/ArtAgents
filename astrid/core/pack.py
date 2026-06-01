"""Pack discovery and validation helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml

PACK_MANIFEST_NAMES = ("pack.yaml", "pack.yml", "pack.json")
EXECUTOR_MANIFEST_NAMES = ("executor.yaml", "executor.yml", "executor.json")
ORCHESTRATOR_MANIFEST_NAMES = ("orchestrator.yaml", "orchestrator.yml", "orchestrator.json")
PACK_ALIAS_KINDS: tuple[Literal["executor", "orchestrator"], ...] = ("executor", "orchestrator")
PackAliasKind = Literal["executor", "orchestrator"]
# Built-in element-kind constants remain stable for compatibility even though
# runtime validation now flows through ElementKindRegistry.
ELEMENT_KINDS: tuple[str, ...] = ("effects", "animations", "transitions")
ElementKind = str
_PACK_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class PackValidationError(ValueError):
    """Raised when pack layout or metadata is invalid."""


@dataclass(frozen=True)
class ElementKindDescriptor:
    id: str
    singular: str = ""
    plural: str = ""
    label: str = ""
    description: str = ""

    @property
    def canonical_kind(self) -> str:
        return self.plural or self.id

    @property
    def aliases(self) -> tuple[str, ...]:
        aliases: list[str] = []
        for candidate in (self.id, self.plural, self.singular):
            if candidate and candidate not in aliases:
                aliases.append(candidate)
        return tuple(aliases)


class ElementKindRegistry:
    """Runtime registry for canonical element kinds and accepted aliases."""

    def __init__(
        self,
        descriptors: Iterable[ElementKindDescriptor] | None = None,
    ) -> None:
        self._descriptors: dict[str, ElementKindDescriptor] = {}
        self._aliases: dict[str, str] = {}
        self.register_many(_builtin_element_kind_descriptors())
        self.register_many(descriptors or ())

    def register(self, descriptor: ElementKindDescriptor) -> None:
        canonical = self._require_token(descriptor.canonical_kind, field_name="element kind")
        if canonical in self._descriptors:
            raise ValueError(f"duplicate element kind {canonical!r}")

        normalized_descriptor = ElementKindDescriptor(
            id=self._require_token(descriptor.id, field_name="element kind id"),
            singular=self._normalize_optional_token(descriptor.singular),
            plural=self._normalize_optional_token(descriptor.plural),
            label=descriptor.label,
            description=descriptor.description,
        )
        if normalized_descriptor.canonical_kind != canonical:
            normalized_descriptor = ElementKindDescriptor(
                id=normalized_descriptor.id,
                singular=normalized_descriptor.singular,
                plural=canonical,
                label=normalized_descriptor.label,
                description=normalized_descriptor.description,
            )

        for alias in normalized_descriptor.aliases:
            existing = self._aliases.get(alias)
            if existing is not None:
                raise ValueError(
                    f"duplicate element kind alias {alias!r}: {existing!r} and {canonical!r}"
                )

        self._descriptors[canonical] = normalized_descriptor
        for alias in normalized_descriptor.aliases:
            self._aliases[alias] = canonical

    def register_many(self, descriptors: Iterable[ElementKindDescriptor]) -> None:
        for descriptor in descriptors:
            self.register(descriptor)

    def canonical_kinds(self) -> tuple[str, ...]:
        return tuple(self._descriptors)

    def accepted_names(self) -> tuple[str, ...]:
        names: list[str] = []
        for canonical, descriptor in self._descriptors.items():
            names.append(canonical)
            for alias in descriptor.aliases:
                if alias != canonical:
                    names.append(alias)
        return tuple(names)

    def descriptors(self) -> tuple[ElementKindDescriptor, ...]:
        return tuple(self._descriptors.values())

    def normalize(self, kind: str, *, error_cls: type[Exception] = ValueError) -> str:
        canonical = self._aliases.get(kind)
        if canonical is None:
            available = ", ".join(self.canonical_kinds())
            raise error_cls(f"element kind must be one of [{available}]")
        return canonical

    def singular(self, kind: str, *, error_cls: type[Exception] = ValueError) -> str:
        descriptor = self.descriptor(kind, error_cls=error_cls)
        return descriptor.singular or descriptor.canonical_kind.rstrip("s")

    def descriptor(
        self,
        kind: str,
        *,
        error_cls: type[Exception] = ValueError,
    ) -> ElementKindDescriptor:
        return self._descriptors[self.normalize(kind, error_cls=error_cls)]

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


def _builtin_element_kind_descriptors() -> tuple[ElementKindDescriptor, ...]:
    return (
        ElementKindDescriptor(id="effects", singular="effect", plural="effects"),
        ElementKindDescriptor(id="animations", singular="animation", plural="animations"),
        ElementKindDescriptor(id="transitions", singular="transition", plural="transitions"),
    )


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


def element_kind_registry_for_pack(
    pack: "PackDefinition",
    *,
    base_registry: ElementKindRegistry | None = None,
) -> ElementKindRegistry:
    registry = base_registry or ELEMENT_KIND_REGISTRY
    descriptors = (
        _extension_element_kind_descriptors(registry)
        + pack_element_kind_descriptors(pack)
    )
    if not descriptors:
        return registry
    try:
        return ElementKindRegistry(descriptors=descriptors)
    except ValueError as exc:
        raise PackValidationError(f"pack.extensions.elements.kinds is invalid: {exc}") from exc


def _extension_element_kind_descriptors(
    registry: ElementKindRegistry,
) -> tuple[ElementKindDescriptor, ...]:
    return tuple(
        descriptor
        for canonical, descriptor in registry._descriptors.items()
        if canonical not in ELEMENT_KINDS
    )


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
        if self.extensions:
            payload["extensions"] = _normalize_json_value(
                self.extensions,
                path="pack.extensions",
            )
        return payload


def packs_root() -> Path:
    return Path(__file__).resolve().parents[1] / "packs"


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


def _optional_pack_extensions(value: Any, *, path: str) -> dict[str, Any]:
    if value is None:
        return {}
    data = _require_mapping(value, path)
    allowed_keys = {"generation", "elements", "schemas"}
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
