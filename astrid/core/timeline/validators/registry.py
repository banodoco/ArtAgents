from __future__ import annotations

import re
from typing import Any

from astrid.core.timeline.banodoco_schema import _ASSET_ENTRY_ALLOWED, _raise_unknown_keys
from astrid.core.timeline.validators.metadata import _validate_generated_at


def _effect_ids(theme: str | None = None) -> set[str]:
    from astrid.core.element import catalog as effects_catalog
    return set(effects_catalog.list_effect_ids(theme=theme))


def _animation_ids() -> set[str]:
    from astrid.core.element import catalog as effects_catalog
    return set(effects_catalog.list_animation_ids())


def _transition_ids() -> set[str]:
    from astrid.core.element import catalog as effects_catalog
    return set(effects_catalog.list_transition_ids())


def _animation_meta(animation_id: str) -> dict[str, Any]:
    from astrid.core.element import catalog as effects_catalog
    try:
        return effects_catalog.read_animation_meta(animation_id)
    except Exception:
        return {}


def validate_registry(registry: Any) -> None:
    if not isinstance(registry, dict):
        raise ValueError("Asset registry must be a JSON object")
    _raise_unknown_keys("Asset registry", registry, frozenset({"assets"}))
    assets = registry.get("assets")
    if not isinstance(assets, dict):
        raise ValueError("Asset registry.assets must be an object")
    for key, entry in assets.items():
        if not isinstance(entry, dict):
            raise ValueError(f"Asset registry.assets[{key!r}] must be an object")
        _raise_unknown_keys(f"Asset registry.assets[{key!r}]", entry, _ASSET_ENTRY_ALLOWED)
        if "file" not in entry and "url" not in entry:
            raise ValueError(f"Asset {key!r} must have 'file' or 'url'")
        url = entry.get("url")
        if url is not None and (not isinstance(url, str) or not url.startswith(("http://", "https://"))):
            raise ValueError(f"Asset {key!r}.url must be an http(s) URL")
        content_sha256 = entry.get("content_sha256")
        if content_sha256 is not None and (
            not isinstance(content_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", content_sha256) is None
        ):
            raise ValueError(f"Asset {key!r}.content_sha256 must be a 64-character lowercase hex string")
        if "url_expires_at" in entry:
            _validate_generated_at(entry.get("url_expires_at"), f"Asset {key!r}.url_expires_at")
        etag = entry.get("etag")
        if etag is not None and (not isinstance(etag, str) or not etag):
            raise ValueError(f"Asset {key!r}.etag must be a non-empty string")
