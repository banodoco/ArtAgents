"""Pack-manifest loading/parsing, discovery, and the packs root."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from astrid.core.pack._common import (
    PACK_MANIFEST_NAMES,
    PackValidationError,
    _optional_string,
    _require_mapping,
    _require_string,
    _validate_pack_id,
)
from astrid.core.pack.definition import PackDefinition
from astrid.core.pack.permissions import (
    _normalize_pack_permissions,
    _optional_pack_aliases,
    _optional_pack_extensions,
)


def packs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "packs"


DEFAULT_PACKS_ROOT = packs_root()


def ensure_local_pack(*, project_root: str | Path = None) -> Path:
    """Create or return the ``local`` scratch pack under *project_root*.

    When *project_root* is ``None``, the pack root is derived from
    ``REPO_ROOT`` so the behaviour matches the old location in
    ``element/registry.py``.
    """
    from astrid.core.paths import REPO_ROOT

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


def pack_manifest_path(root: str | Path) -> Path | None:
    pack_root = Path(root)
    for name in PACK_MANIFEST_NAMES:
        candidate = pack_root / name
        if candidate.is_file():
            return candidate
    return None


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
