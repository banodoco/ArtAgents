"""Shared low-level helpers, constants, and errors for pack metadata.

Leaf module: imported by the other pack submodules; it must not import
from any of them so the package forms a clean dependency DAG.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal


class SymlinkedPackPathError(ValueError):
    """A pack path contains a symlinked component."""


def reject_symlinked_path(path: str | Path) -> Path:
    """Reject symlinked components without resolving the supplied path."""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    current = Path(candidate.anchor)
    for component in candidate.parts[1:]:
        current /= component
        if current.is_symlink():
            raise SymlinkedPackPathError(f"pack path contains a symlink: {current}")
    return candidate


if TYPE_CHECKING:
    from astrid.core.pack.definition import PackDefinition

PACK_MANIFEST_NAMES = ("pack.yaml",)
EXECUTOR_MANIFEST_NAMES = ("executor.yaml", "executor.yml", "executor.json")
ORCHESTRATOR_MANIFEST_NAMES = ("orchestrator.yaml", "orchestrator.yml", "orchestrator.json")
ELEMENT_MANIFEST_NAMES = ("element.yaml", "element.yml", "element.json")

_COMPONENT_MANIFEST_NAMES: dict[str, tuple[str, ...]] = {
    "executor": EXECUTOR_MANIFEST_NAMES,
    "orchestrator": ORCHESTRATOR_MANIFEST_NAMES,
    "element": ELEMENT_MANIFEST_NAMES,
}


def find_component_manifest(comp_dir: Path, kind: str) -> Path | None:
    """Return the first manifest file found in *comp_dir* for *kind*.

    *kind* is one of ``"executor"``, ``"orchestrator"``, or ``"element"``.
    Returns ``None`` when no recognised manifest file exists.
    """
    names = _COMPONENT_MANIFEST_NAMES.get(kind, ())
    for name in names:
        candidate = comp_dir / name
        if candidate.is_file():
            return candidate
    return None
PackAliasKind = Literal["executor", "orchestrator", "renderer", "planner", "finalizer"]
PACK_ALIAS_KINDS: tuple[PackAliasKind, ...] = (
    "executor",
    "orchestrator",
    "renderer",
    "planner",
    "finalizer",
)
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
