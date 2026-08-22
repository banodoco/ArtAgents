#!/usr/bin/env python3
"""Element catalog facade over the Astrid elements registry."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from astrid.core.element.registry import (
    ElementRegistry,
    ElementSource,
    clear_default_registry_cache,
    load_default_registry,
    load_source_elements,
)
from astrid.core.element.schema import ElementKind
from astrid.core.foundation.paths import REPO_ROOT, WORKSPACE_ROOT
from astrid.core.theme import ACTIVE_THEME_ENV, resolve_theme_dir, resolve_themes_root

TOOLS_DIR = REPO_ROOT
THEMES_ROOT = resolve_themes_root()


def effects_root() -> Path:
    return element_root("effects")


def animations_root() -> Path:
    return element_root("animations")


def transitions_root() -> Path:
    return element_root("transitions")


def element_root(kind: ElementKind) -> Path:
    return WORKSPACE_ROOT / _validate_kind(kind)


def _validate_kind(kind: str) -> ElementKind:
    return _registry().element_kind_registry.normalize(kind)


@lru_cache(maxsize=None)
def _resolve_theme_dir(theme: str | Path | None) -> Path | None:
    return resolve_theme_dir(theme)


def resolve_active_theme(
    project_slug: str | None = None, *, root: str | Path | None = None
) -> Path | None:
    raw = os.environ.get(ACTIVE_THEME_ENV)
    if raw:
        return resolve_theme_dir(raw)
    if project_slug:
        from astrid.core.project.project import get_project_theme

        theme = get_project_theme(project_slug, root=root)
        if theme:
            return resolve_theme_dir(theme)
    return None


def _registry(theme: str | Path | None = None, *, project_slug: str | None = None) -> ElementRegistry:
    theme_dir = _resolve_theme_dir(theme) if theme is not None else resolve_active_theme(project_slug)
    return _cached_registry(
        _path_cache_key(theme_dir),
        project_slug,
        _path_cache_key(TOOLS_DIR),
        _path_cache_key(WORKSPACE_ROOT),
    )


def _path_cache_key(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return str(Path(path).resolve())


@lru_cache(maxsize=None)
def _cached_registry(
    theme_dir_key: str | None,
    project_slug: str | None,
    project_root_key: str | None,
    legacy_root_key: str | None,
) -> ElementRegistry:
    theme_dir = Path(theme_dir_key) if theme_dir_key is not None else None
    project_root = Path(project_root_key) if project_root_key is not None else TOOLS_DIR
    registry = load_default_registry(active_theme=theme_dir, project_root=project_root)
    legacy_root = Path(legacy_root_key) if legacy_root_key is not None else WORKSPACE_ROOT
    if legacy_root.exists():
        legacy_source = ElementSource("legacy_workspace", legacy_root, 15, True)
        for element in load_source_elements(
            legacy_source,
            element_kind_registry=registry.element_kind_registry,
        ):
            registry.register(element)
    return registry


def _clear_registry_cache() -> None:
    _cached_registry.cache_clear()
    _resolve_theme_dir.cache_clear()
    clear_default_registry_cache()


def _warn_conflicts(registry: ElementRegistry, *, kind: ElementKind) -> None:
    singular = registry.element_kind_registry.singular(kind)
    for conflict in registry.conflicts():
        if conflict.kind != kind:
            continue
        if conflict.winner.source == "active_theme":
            for shadowed in conflict.shadowed:
                if shadowed.source in {"legacy_workspace", "overrides", "managed", "bundled"}:
                    print(
                        f"WARN theme '{_theme_name_for_element(conflict.winner)}' overrides workspace {singular} '{conflict.id}'",
                        file=sys.stderr,
                    )
                    break


def _theme_name_for_element(element: Any) -> str:
    if element.root.parent.parent.name == "elements":
        return element.root.parent.parent.parent.name
    return element.root.parent.parent.name


def list_element_ids(
    kind: ElementKind,
    theme: str | Path | None = None,
    *,
    project_slug: str | None = None,
) -> list[str]:
    registry = _registry(theme, project_slug=project_slug)
    normalized_kind = registry.element_kind_registry.normalize(kind)
    _warn_conflicts(registry, kind=normalized_kind)
    return [element.id for element in registry.list(kind=normalized_kind)]


def _element(
    element_id: str,
    *,
    kind: ElementKind,
    theme: str | Path | None = None,
    project_slug: str | None = None,
):
    return _registry(theme, project_slug=project_slug).get(kind, element_id)


def read_element_schema(
    element_id: str,
    *,
    kind: ElementKind,
    theme: str | Path | None = None,
) -> dict[str, Any]:
    return dict(_element(element_id, kind=kind, theme=theme).schema)


def read_element_meta(
    element_id: str,
    *,
    kind: ElementKind,
    theme: str | Path | None = None,
) -> dict[str, Any]:
    return dict(_element(element_id, kind=kind, theme=theme).metadata)


def read_element_defaults(
    element_id: str,
    *,
    kind: ElementKind,
    theme: str | Path | None = None,
) -> dict[str, Any]:
    return dict(_element(element_id, kind=kind, theme=theme).defaults)


def list_effect_ids(theme: str | Path | None = None) -> list[str]:
    return list_element_ids("effects", theme=theme)


def read_effect_schema(effect_id: str, theme: str | Path | None = None) -> dict[str, Any]:
    return read_element_schema(effect_id, kind="effects", theme=theme)


def read_effect_meta(effect_id: str, theme: str | Path | None = None) -> dict[str, Any]:
    return read_element_meta(effect_id, kind="effects", theme=theme)


def read_effect_defaults(effect_id: str, theme: str | Path | None = None) -> dict[str, Any]:
    return read_element_defaults(effect_id, kind="effects", theme=theme)


def list_animation_ids(theme: str | Path | None = None) -> list[str]:
    return list_element_ids("animations", theme=theme)


def read_animation_schema(animation_id: str, theme: str | Path | None = None) -> dict[str, Any]:
    return read_element_schema(animation_id, kind="animations", theme=theme)


def read_animation_meta(animation_id: str, theme: str | Path | None = None) -> dict[str, Any]:
    return read_element_meta(animation_id, kind="animations", theme=theme)


def read_animation_defaults(animation_id: str, theme: str | Path | None = None) -> dict[str, Any]:
    return read_element_defaults(animation_id, kind="animations", theme=theme)


def list_transition_ids(theme: str | Path | None = None) -> list[str]:
    return list_element_ids("transitions", theme=theme)


def read_transition_schema(transition_id: str, theme: str | Path | None = None) -> dict[str, Any]:
    return read_element_schema(transition_id, kind="transitions", theme=theme)


def read_transition_meta(transition_id: str, theme: str | Path | None = None) -> dict[str, Any]:
    return read_element_meta(transition_id, kind="transitions", theme=theme)


def read_transition_defaults(transition_id: str, theme: str | Path | None = None) -> dict[str, Any]:
    return read_element_defaults(transition_id, kind="transitions", theme=theme)
