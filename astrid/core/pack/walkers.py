"""Filesystem walkers that locate content roots inside a pack."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from astrid.core.pack._common import (
    EXECUTOR_MANIFEST_NAMES,
    ORCHESTRATOR_MANIFEST_NAMES,
    ElementKind,
    PackValidationError,
)
from astrid.core.pack.registry import (
    ElementKindRegistry,
    element_kind_registry_for_pack,
)

if TYPE_CHECKING:
    from astrid.core.pack.definition import PackDefinition


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
