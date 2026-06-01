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
# Authoritative element-kind contract (mirrored as a Literal in
# astrid.core.element.schema; kept here too because pack.py is loaded
# before element/__init__.py and importing from there causes a cycle).
ELEMENT_KINDS: tuple[Literal["effects", "animations", "transitions"], ...] = (
    "effects", "animations", "transitions",
)
ElementKind = Literal["effects", "animations", "transitions"]
_PACK_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class PackValidationError(ValueError):
    """Raised when pack layout or metadata is invalid."""


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


def iter_element_roots(pack: PackDefinition, *, kind: str | None = None) -> tuple[tuple[ElementKind, Path], ...]:
    kinds: Iterable[str] = ELEMENT_KINDS if kind is None else (kind,)
    roots: list[tuple[ElementKind, Path]] = []
    elements_root = _declared_content_root(pack, "elements") or (pack.root / "elements")
    for element_kind in kinds:
        if element_kind not in ELEMENT_KINDS:
            raise PackValidationError(f"element kind must be one of {list(ELEMENT_KINDS)}")
        kind_root = elements_root / element_kind
        if not kind_root.is_dir():
            continue
        roots.extend((element_kind, child) for child in sorted(kind_root.iterdir()) if child.is_dir())
    return tuple(roots)


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


def _validate_pack_id(value: str, path: str) -> None:
    if not _PACK_ID_RE.fullmatch(value):
        raise PackValidationError(f"{path} must be a safe pack identifier matching ^[a-z][a-z0-9_]*$")


__all__ = [
    "PackDefinition",
    "PackValidationError",
    "discover_packs",
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
