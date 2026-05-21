"""Deterministic duration filter stage."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from ..interfaces import FilterResult
from ._common import build_filter_stats, increment_reason, pass_item, reject_item


class DurationFilter:
    @property
    def stage_id(self) -> str:
        return "duration_filter"

    @property
    def stage_order(self) -> int:
        return 0

    def apply(self, items: list[dict[str, Any]], state: dict[str, Any], config: dict[str, Any]) -> FilterResult:
        started = time.perf_counter()
        min_s, max_s = _duration_bounds(config)
        passed: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        reasons: dict[str, int] = {}
        for item in items:
            duration = _duration(item)
            if duration is None:
                reason = "missing_duration"
            elif min_s is not None and duration < min_s:
                reason = "duration_too_short"
            elif max_s is not None and duration > max_s:
                reason = "duration_too_long"
            else:
                updated = pass_item(item, self.stage_id, score=duration)
                passed.append(updated)
                continue
            increment_reason(reasons, reason)
            updated = reject_item(item, self.stage_id, reason=reason, score=duration)
            rejected.append(updated)
        stats = build_filter_stats(
            stage_id=self.stage_id,
            stage_order=self.stage_order,
            items_in=len(items),
            items_passed=len(passed),
            items_rejected=len(rejected),
            rejection_reasons=reasons,
            started=started,
        )
        return FilterResult(passed=passed, rejected=rejected, stats=stats)


def _duration_bounds(config: Mapping[str, Any]) -> tuple[float | None, float | None]:
    min_value = config.get("min_s", config.get("min_duration_s"))
    max_value = config.get("max_s", config.get("max_duration_s"))
    return _optional_float(min_value), _optional_float(max_value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _duration(item: Mapping[str, Any]) -> float | None:
    value = item.get("duration_s")
    if isinstance(value, (int, float)):
        return float(value)
    start = item.get("clip_start_s")
    end = item.get("clip_end_s")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)) and float(end) >= float(start):
        return float(end) - float(start)
    return None
