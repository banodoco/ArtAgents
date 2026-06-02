"""Registry-backed helpers for timeline kind validation."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from astrid.core.pack import ELEMENT_KIND_REGISTRY, ElementKindRegistry

_EVENT_CLIP_KIND_TO_REGISTRY_IDS: dict[str, tuple[str, ...]] = {
    "visual": ("video", "image"),
    "audio": ("audio",),
    "text": ("text",),
}


@lru_cache(maxsize=4)
def _timeline_kind_registry(root: str | None = None) -> ElementKindRegistry:
    if root is None:
        return ELEMENT_KIND_REGISTRY
    from astrid.core.pack import discover_packs, pack_timeline_kind_descriptors

    descriptors = []
    for pack in discover_packs(Path(root), include_hidden=True):
        descriptors.extend(pack_timeline_kind_descriptors(pack))
    if not descriptors:
        return ELEMENT_KIND_REGISTRY
    return ElementKindRegistry(descriptors=descriptors)


def _registry(root: str | Path | None = None) -> ElementKindRegistry:
    return _timeline_kind_registry(None if root is None else str(Path(root).resolve()))


def valid_event_clip_kinds() -> tuple[str, ...]:
    return tuple(_EVENT_CLIP_KIND_TO_REGISTRY_IDS)


def normalize_event_clip_kind(
    kind: str,
    *,
    error_cls: type[Exception] = ValueError,
    root: str | Path | None = None,
) -> str:
    if not isinstance(kind, str) or not kind.strip():
        raise error_cls("clip kind must be a non-empty string")
    normalized = kind.strip()
    if normalized in _EVENT_CLIP_KIND_TO_REGISTRY_IDS:
        _validate_event_clip_registry_support(normalized, error_cls=error_cls, root=root)
        return normalized
    canonical = _registry(root).normalize(normalized, catalog="clip", error_cls=error_cls)
    if canonical in {"video", "image"}:
        _validate_event_clip_registry_support("visual", error_cls=error_cls, root=root)
        return "visual"
    if canonical in {"audio", "text"}:
        return canonical
    available = ", ".join(valid_event_clip_kinds())
    raise error_cls(f"clip kind must be one of [{available}]")


def _validate_event_clip_registry_support(
    kind: str,
    *,
    error_cls: type[Exception],
    root: str | Path | None,
) -> None:
    registry = _registry(root)
    for registry_id in _EVENT_CLIP_KIND_TO_REGISTRY_IDS[kind]:
        registry.normalize(registry_id, catalog="clip", error_cls=error_cls)


def normalize_track_kind(
    kind: str,
    *,
    error_cls: type[Exception] = ValueError,
    root: str | Path | None = None,
) -> str:
    if not isinstance(kind, str) or not kind.strip():
        raise error_cls("track kind must be a non-empty string")
    return _registry(root).normalize(kind, catalog="track", error_cls=error_cls)


def normalize_transition_kind(
    kind: str,
    *,
    error_cls: type[Exception] = ValueError,
    root: str | Path | None = None,
) -> str:
    if not isinstance(kind, str) or not kind.strip():
        raise error_cls("transition kind must be a non-empty string")
    return _registry(root).normalize(kind, catalog="transition", error_cls=error_cls)


def default_transition_kind(*, root: str | Path | None = None) -> str:
    return _registry(root).default_kind(catalog="transition") or "cross-fade"


def transition_kind_options(*, root: str | Path | None = None) -> tuple[str, ...]:
    return _registry(root).valid_options(catalog="transition")
