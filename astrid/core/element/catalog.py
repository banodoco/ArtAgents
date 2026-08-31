#!/usr/bin/env python3
"""Element catalog facade over the Astrid elements registry."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from astrid.core.element.registry import (
    ElementRegistry,
    clear_default_registry_cache,
    load_default_registry,
)
from astrid.core.element.schema import ElementKind
from astrid.core.foundation.paths import REPO_ROOT, WORKSPACE_ROOT

TOOLS_DIR = REPO_ROOT


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


def _registry(theme: str | Path | None = None, *, project_slug: str | None = None) -> ElementRegistry:
    # Timeline theme slugs are authoring metadata.  They cannot select
    # executable element definitions; only discovered Astrid packs do that.
    del theme
    return _cached_registry(
        project_slug,
        _path_cache_key(TOOLS_DIR),
    )


def _path_cache_key(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return str(Path(path).resolve())


@lru_cache(maxsize=None)
def _cached_registry(
    project_slug: str | None,
    project_root_key: str | None,
) -> ElementRegistry:
    project_root = Path(project_root_key) if project_root_key is not None else TOOLS_DIR
    return load_default_registry(project_root=project_root)


def _clear_registry_cache() -> None:
    _cached_registry.cache_clear()
    clear_default_registry_cache()


def list_element_ids(
    kind: ElementKind,
    theme: str | Path | None = None,
    *,
    project_slug: str | None = None,
) -> list[str]:
    registry = _registry(theme, project_slug=project_slug)
    normalized_kind = registry.element_kind_registry.normalize(kind)
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
