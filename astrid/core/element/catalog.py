#!/usr/bin/env python3
"""Element catalog facade over the Astrid elements registry."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from astrid.core.element.registry import (
    ElementRegistry,
    ElementSource,
    load_default_registry,
    load_source_elements,
)
from astrid.core.element.schema import ElementKind
from astrid.core.theme import ACTIVE_THEME_ENV, resolve_theme_dir, resolve_themes_root
from astrid.core.paths import REPO_ROOT, WORKSPACE_ROOT

TOOLS_DIR = REPO_ROOT
THEMES_ROOT = resolve_themes_root()


def _initial_active_theme() -> Path | None:
    raw = os.environ.get(ACTIVE_THEME_ENV)
    if not raw:
        return None
    return resolve_theme_dir(raw)


_ACTIVE_THEME_DIR: Path | None = None


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


def _resolve_theme_dir(theme: str | Path | None) -> Path | None:
    return resolve_theme_dir(theme)


def set_active_theme(theme: str | Path | None) -> None:
    global _ACTIVE_THEME_DIR
    _ACTIVE_THEME_DIR = _resolve_theme_dir(theme)


_ACTIVE_THEME_DIR = _initial_active_theme()


def _active_theme_dir(theme: str | Path | None = None) -> Path | None:
    return _resolve_theme_dir(theme) if theme is not None else _ACTIVE_THEME_DIR


def resolve_active_theme(project_slug: str | None = None) -> Path | None:
    if project_slug is None and _ACTIVE_THEME_DIR is not None:
        return _ACTIVE_THEME_DIR
    raw = os.environ.get(ACTIVE_THEME_ENV)
    if raw:
        return resolve_theme_dir(raw)
    if project_slug:
        from astrid.core.project.project import get_project_theme

        theme = get_project_theme(project_slug)
        if theme:
            return resolve_theme_dir(theme)
    return _ACTIVE_THEME_DIR


def _registry(theme: str | Path | None = None, *, project_slug: str | None = None) -> ElementRegistry:
    theme_dir = _resolve_theme_dir(theme) if theme is not None else resolve_active_theme(project_slug)
    registry = load_default_registry(active_theme=theme_dir, project_root=TOOLS_DIR)
    legacy_root = WORKSPACE_ROOT
    if legacy_root.exists():
        legacy_source = ElementSource("legacy_workspace", legacy_root, 15, True)
        for element in load_source_elements(
            legacy_source,
            element_kind_registry=registry.element_kind_registry,
        ):
            registry.register(element)
    return registry


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
