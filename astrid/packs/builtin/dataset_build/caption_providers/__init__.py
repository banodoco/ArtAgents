"""Caption provider implementations for builtin.dataset_build."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .understanding import (
    VideoUnderstandCaptionProvider,
    VisualUnderstandCaptionProvider,
    caption_candidate,
    caption_sidecar_path,
)


class BudgetTracker:
    """Small API-call counter for caption providers.

    It intentionally tracks calls, not dollars. Cost estimates stay in config
    preflight until concrete provider pricing is wired into orchestration.
    """

    def __init__(self, *, max_api_calls: int | None = None, provider_limits: Mapping[str, int] | None = None) -> None:
        self.max_api_calls = max_api_calls
        self.provider_limits = dict(provider_limits or {})
        self.total_api_calls = 0
        self.provider_calls: dict[str, int] = {}

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "BudgetTracker":
        budgets = config.get("budgets") or {}
        if not isinstance(budgets, Mapping):
            return cls()
        providers = budgets.get("providers") or {}
        provider_limits: dict[str, int] = {}
        if isinstance(providers, Mapping):
            for provider_id, provider_budget in providers.items():
                if isinstance(provider_budget, Mapping) and isinstance(provider_budget.get("max_calls"), int):
                    provider_limits[str(provider_id)] = int(provider_budget["max_calls"])
        max_api_calls = budgets.get("max_api_calls")
        return cls(max_api_calls=max_api_calls if isinstance(max_api_calls, int) else None, provider_limits=provider_limits)

    def increment(self, provider_id: str, *, calls: int = 1) -> None:
        if calls < 0:
            raise ValueError("calls must be non-negative")
        next_total = self.total_api_calls + calls
        if self.max_api_calls is not None and next_total > self.max_api_calls:
            raise RuntimeError(f"caption budget exceeded: total API calls {next_total} > {self.max_api_calls}")
        next_provider = self.provider_calls.get(provider_id, 0) + calls
        provider_limit = self.provider_limits.get(provider_id)
        if provider_limit is not None and next_provider > provider_limit:
            raise RuntimeError(f"caption budget exceeded for {provider_id}: API calls {next_provider} > {provider_limit}")
        self.total_api_calls = next_total
        self.provider_calls[provider_id] = next_provider

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_api_calls": self.total_api_calls,
            "provider_calls": dict(self.provider_calls),
            "max_api_calls": self.max_api_calls,
            "provider_limits": dict(self.provider_limits),
        }


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
