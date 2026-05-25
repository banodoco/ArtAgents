"""Element registry and source precedence."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Iterable, cast

from astrid._paths import REPO_ROOT
from astrid.core.alias_resolver import (
    AliasResolver,
    _register_pack_aliases,
    create_shared_alias_resolver,
)
from astrid.core.manifest import dump_manifest_payload, load_manifest_mapping
from astrid.core.pack import (
    discover_packs,
    ensure_local_pack,
    iter_element_roots,
    validate_element_pack_id,
)

from .schema import (
    ELEMENT_KINDS,
    ElementDefinition,
    ElementKind,
    ElementValidationError,
    load_element_definition,
)

if TYPE_CHECKING:
    from astrid.core.override import OverrideStore


class ElementRegistryError(ElementValidationError):
    """Raised when element registry state is inconsistent."""


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


class ElementRegistry:
    """Resolved element registry keyed by kind and element id."""

    def __init__(
        self,
        elements: Iterable[ElementDefinition] = (),
        *,
        alias_resolver: AliasResolver | None = None,
        override_store: "OverrideStore | None" = None,
    ) -> None:
        self._all: dict[tuple[str, str], list[ElementDefinition]] = {}
        self.alias_resolver = alias_resolver
        self.override_store = override_store
        for element in elements:
            self.register(element)

    def register(self, element: ElementDefinition) -> ElementDefinition:
        key = (element.kind, element.id)
        self._all.setdefault(key, []).append(element)
        self._all[key].sort(key=lambda item: (item.priority, item.source, str(item.root)))
        return element

    def get(self, kind: ElementKind, element_id: str) -> ElementDefinition:
        key = (kind, element_id)
        try:
            definition = self._all[key][0]
        except KeyError as exc:
            raise KeyError(f"unknown {kind} element {element_id!r}") from exc

        # Check override store for a remapped target.
        if self.override_store is not None:
            target_id = self.override_store.resolve(kind, element_id)
            if target_id is not None and target_id != element_id:
                # Validate that the override target exists.
                target_key = (kind, target_id)
                if target_key not in self._all:
                    raise ElementRegistryError(
                        f"override target {target_id!r} for {kind} {element_id!r} not found in registry"
                    )
                target_def = self._all[target_key][0]
                # Annotate the returned definition with override_target metadata.
                target_metadata = dict(target_def.metadata)
                target_metadata["override_target"] = target_id
                from dataclasses import replace as _replace
                return _replace(target_def, metadata=target_metadata)

        return definition

    def list(self, kind: ElementKind | None = None) -> tuple[ElementDefinition, ...]:
        if kind is not None and kind not in ELEMENT_KINDS:
            raise ElementRegistryError(f"kind must be one of {list(ELEMENT_KINDS)}")
        winners = [definitions[0] for (item_kind, _), definitions in self._all.items() if kind is None or item_kind == kind]
        return tuple(sorted(winners, key=lambda item: (item.kind, item.id)))

    def conflicts(self) -> tuple[ElementConflict, ...]:
        conflicts: list[ElementConflict] = []
        for (kind, element_id), definitions in self._all.items():
            if len(definitions) > 1:
                conflicts.append(
                    ElementConflict(
                        kind=cast(ElementKind, kind),
                        id=element_id,
                        winner=definitions[0],
                        shadowed=tuple(definitions[1:]),
                    )
                )
        return tuple(sorted(conflicts, key=lambda item: (item.kind, item.id)))

    def as_mapping(self) -> MappingProxyType[tuple[str, str], ElementDefinition]:
        return MappingProxyType({key: definitions[0] for key, definitions in self._all.items()})

    def fork_target(self, kind: ElementKind, element_id: str, *, project_root: str | Path = REPO_ROOT) -> Path:
        element = self.get(kind, element_id)
        return Path(project_root) / element.fork_target

    def fork(self, kind: ElementKind, element_id: str, *, project_root: str | Path = REPO_ROOT, overwrite: bool = False) -> Path:
        element = self.get(kind, element_id)
        target = self.fork_target(kind, element_id, project_root=project_root)
        if target.exists() and not overwrite:
            raise ElementRegistryError(f"element override already exists: {target}")
        ensure_local_pack(project_root=project_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(element.root, target)
        _rewrite_pack_id(target, "local")
        return target


def load_default_registry(
    *,
    active_theme: str | Path | None = None,
    project_root: str | Path = REPO_ROOT,
    include_missing_roots: bool = False,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> ElementRegistry:
    resolver = create_shared_alias_resolver()
    _register_pack_aliases(resolver, {})  # M1: no aliases yet
    registry = ElementRegistry(alias_resolver=resolver)
    for element in load_pack_elements(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    ):
        registry.register(element)
    for source in default_sources(active_theme=active_theme, project_root=project_root):
        if not source.root.exists():
            if include_missing_roots:
                source.root.mkdir(parents=True, exist_ok=True)
            else:
                continue
        for element in load_source_elements(source):
            registry.register(element)
    return registry


def default_sources(*, active_theme: str | Path | None = None, project_root: str | Path = REPO_ROOT) -> tuple[ElementSource, ...]:
    theme_dir = _resolve_theme_dir(active_theme)
    sources: list[ElementSource] = []
    if theme_dir is not None:
        sources.extend(
            [
                ElementSource("active_theme", theme_dir / "elements", 0, True),
                ElementSource("active_theme", theme_dir, 0, True),
            ]
        )
    return tuple(sources)


def load_pack_elements(
    *,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> tuple[ElementDefinition, ...]:
    from .schema import ELEMENT_MANIFEST_NAMES

    # The `local` scratch pack is project-scoped (gitignored) — load it from
    # <project_root>/astrid/packs/local only when project_root is distinct
    # from the source-tree REPO_ROOT, so the workspace scratch pack never
    # leaks into discovery for code that did not opt into a project.
    repo_pack_root = (REPO_ROOT / "astrid" / "packs").resolve()
    project_pack_root = (Path(project_root) / "astrid" / "packs").resolve()

    packs: list = []
    for pack in discover_packs():
        if pack.id == "local":
            continue
        packs.append(pack)
    if project_pack_root != repo_pack_root and project_pack_root.is_dir():
        for pack in discover_packs(project_pack_root):
            if pack.id == "local":
                packs.append(pack)

    # Additional pack roots: extra roots + installed packs (PR #8 operational layer)
    if extra_pack_roots or include_installed:
        _discover_root = Path(project_root) if project_root != REPO_ROOT else REPO_ROOT
        for extra_root in extra_pack_roots:
            extra_path = Path(extra_root)
            if not extra_path.is_absolute():
                extra_path = (_discover_root / extra_path).resolve()
            if extra_path.is_dir():
                for pack in discover_packs(extra_path):
                    if pack.id == "local":
                        continue
                    packs.append(pack)
        if include_installed:
            from astrid.core.pack_store import installed_pack_roots
            from astrid.core.pack import load_pack_manifest, pack_manifest_path as _pmp

            for installed_root in installed_pack_roots():
                if installed_root.is_dir():
                    mp = _pmp(installed_root)
                    if mp is not None:
                        pack = load_pack_manifest(mp)
                        if pack.id == "local":
                            continue
                        packs.append(pack)

    elements: list[ElementDefinition] = []
    for pack in packs:
        priority = 10 if pack.id == "local" else 30
        for kind, root in iter_element_roots(pack):
            if not any((root / name).is_file() for name in ELEMENT_MANIFEST_NAMES):
                continue
            element = load_element_definition(
                root,
                kind=kind,
                source=f"pack:{pack.id}",
                editable=pack.id == "local",
                priority=priority,
            )
            validate_element_pack_id(element.metadata.get("pack_id"), pack, element_root=root)
            elements.append(element)
    return tuple(elements)


def _rewrite_pack_id(element_root: Path, new_pack_id: str) -> None:
    from .schema import ELEMENT_MANIFEST_NAMES

    for name in ELEMENT_MANIFEST_NAMES:
        manifest = element_root / name
        if not manifest.is_file():
            continue
        data = load_manifest_mapping(manifest, manifest_kind="element")
        data["pack_id"] = new_pack_id
        dump_manifest_payload(manifest, data)
        return


def load_source_elements(source: ElementSource) -> tuple[ElementDefinition, ...]:
    from .schema import ELEMENT_MANIFEST_NAMES

    elements: list[ElementDefinition] = []
    for kind in ELEMENT_KINDS:
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
                    )
                )
            except ElementValidationError as exc:
                print(f"WARN skipping {child}: {exc}", file=sys.stderr)
    return tuple(elements)


def _resolve_theme_dir(theme: str | Path | None) -> Path | None:
    raw = os.environ.get("HYPE_ACTIVE_THEME") if theme is None else theme
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if candidate.name == "theme.json":
        return candidate.parent.resolve()
    if candidate.exists():
        return (candidate if candidate.is_dir() else candidate.parent).resolve()
    return (REPO_ROOT.parent / "themes" / str(raw)).resolve()
