"""Run-scoped API budget and rate tracking for dataset-build."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any


class BudgetTracker:
    """Track API/model calls across all API-backed dataset-build stages."""

    def __init__(
        self,
        *,
        max_api_calls: int | None = None,
        provider_limits: Mapping[str, int] | None = None,
        provider_rate_limits: Mapping[str, int] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_api_calls = max_api_calls
        self.provider_limits = dict(provider_limits or {})
        self.provider_rate_limits = dict(provider_rate_limits or {})
        self._clock = clock
        self._sleep = sleep
        self.total_api_calls = 0
        self.provider_calls: dict[str, int] = {}
        self.observed_calls_by_provider: dict[str, int] = {}
        self._last_call_at: dict[str, float] = {}

    @classmethod
    def from_config(
        cls,
        config: Mapping[str, Any],
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> "BudgetTracker":
        budgets = config.get("budgets") or {}
        if not isinstance(budgets, Mapping):
            return cls(clock=clock, sleep=sleep)
        providers = budgets.get("providers") or {}
        provider_limits: dict[str, int] = {}
        provider_rate_limits: dict[str, int] = {}
        if isinstance(providers, Mapping):
            for provider_id, provider_budget in providers.items():
                if not isinstance(provider_budget, Mapping):
                    continue
                if isinstance(provider_budget.get("max_calls"), int):
                    provider_limits[str(provider_id)] = int(provider_budget["max_calls"])
                if isinstance(provider_budget.get("rate_limit_per_minute"), int):
                    provider_rate_limits[str(provider_id)] = int(provider_budget["rate_limit_per_minute"])
        max_api_calls = budgets.get("max_api_calls")
        return cls(
            max_api_calls=max_api_calls if isinstance(max_api_calls, int) else None,
            provider_limits=provider_limits,
            provider_rate_limits=provider_rate_limits,
            clock=clock,
            sleep=sleep,
        )

    def increment(self, provider_id: str, *, calls: int = 1) -> None:
        if calls < 0:
            raise ValueError("calls must be non-negative")
        next_total = self.total_api_calls + calls
        if self.max_api_calls is not None and next_total > self.max_api_calls:
            raise RuntimeError(f"API budget exceeded: total API calls {next_total} > {self.max_api_calls}")
        next_provider = self.provider_calls.get(provider_id, 0) + calls
        provider_limit = self.provider_limits.get(provider_id)
        if provider_limit is not None and next_provider > provider_limit:
            raise RuntimeError(f"API budget exceeded for {provider_id}: API calls {next_provider} > {provider_limit}")

        for _ in range(calls):
            self._enforce_rate_limit(provider_id)
            self.total_api_calls += 1
            self.provider_calls[provider_id] = self.provider_calls.get(provider_id, 0) + 1
            self.observed_calls_by_provider[provider_id] = self.observed_calls_by_provider.get(provider_id, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_api_calls": self.total_api_calls,
            "provider_calls": dict(self.provider_calls),
            "observed_calls_by_provider": dict(self.observed_calls_by_provider),
            "max_api_calls": self.max_api_calls,
            "provider_limits": dict(self.provider_limits),
            "provider_rate_limits": dict(self.provider_rate_limits),
        }

    def _enforce_rate_limit(self, provider_id: str) -> None:
        rate_limit = self.provider_rate_limits.get(provider_id)
        if rate_limit is None:
            return
        if rate_limit <= 0:
            raise RuntimeError(f"API rate limit for {provider_id} must be positive")
        min_interval = 60.0 / float(rate_limit)
        now = float(self._clock())
        last_call_at = self._last_call_at.get(provider_id)
        if last_call_at is not None:
            wait_s = (last_call_at + min_interval) - now
            if wait_s > 0:
                self._sleep(wait_s)
                now = float(self._clock())
        self._last_call_at[provider_id] = now
