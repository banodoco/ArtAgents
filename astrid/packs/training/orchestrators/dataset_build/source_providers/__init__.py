"""Source provider registry for ``training.dataset_build``."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from .local_folder import LocalFolderSourceProvider
from .youtube import YouTubeSourceProvider

PROVIDERS = {
    "local_folder": LocalFolderSourceProvider,
    "youtube": YouTubeSourceProvider,
}


def get_source_provider(provider_id: str, **kwargs: Any):
    try:
        provider_type = PROVIDERS[provider_id]
    except KeyError as exc:
        known = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"unknown source provider {provider_id!r}; known providers: {known}") from exc
    return provider_type(**kwargs)


def iter_source_candidates(config: Mapping[str, Any], **kwargs: Any) -> Iterator[dict[str, Any]]:
    for source in config.get("sources", []) or []:
        provider_id = source.get("provider")
        provider_config = dict(source.get("config") or {})
        provider_config.setdefault("dataset_config", config)
        provider = get_source_provider(provider_id, **kwargs)
        yield from provider.acquire(provider_config)


__all__ = [
    "LocalFolderSourceProvider",
    "YouTubeSourceProvider",
    "get_source_provider",
    "iter_source_candidates",
]

