"""Caption provider implementations for training.dataset_build."""

from __future__ import annotations

from typing import Any

from ..budget import BudgetTracker
from .understanding import (
    VideoUnderstandCaptionProvider,
    VisualUnderstandCaptionProvider,
    caption_candidate,
    caption_sidecar_path,
)


PROVIDERS = {
    "visual_understand": VisualUnderstandCaptionProvider,
    "video_understand": VideoUnderstandCaptionProvider,
}


def get_caption_provider(provider_id: str, **kwargs: Any):
    try:
        provider_cls = PROVIDERS[provider_id]
    except KeyError as exc:
        available = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"unknown caption provider {provider_id!r}; available providers: {available}") from exc
    return provider_cls(**kwargs)


__all__ = [
    "BudgetTracker",
    "PROVIDERS",
    "VideoUnderstandCaptionProvider",
    "VisualUnderstandCaptionProvider",
    "caption_candidate",
    "caption_sidecar_path",
    "get_caption_provider",
]
