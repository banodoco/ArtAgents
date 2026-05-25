"""Deterministic per-source cap filter stage."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from ..interfaces import FilterResult
from ._common import build_filter_stats, canonical_source_id, increment_reason, pass_item, record_warning, reject_item


class SourceCapFilter:
    @property
    def stage_id(self) -> str:
        return "source_cap_filter"

    @property
    def stage_order(self) -> int:
        return 5

    def apply(self, items: list[dict[str, Any]], state: dict[str, Any], config: dict[str, Any]) -> FilterResult:
        started = time.perf_counter()
        max_per_source = _max_per_source(config)
        passed: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        reasons: dict[str, int] = {}
        warnings: list[str] = []
        counts: dict[str, int] = {}

        for item in items:
            source_id = canonical_source_id(item)
            if not source_id:
                record_warning(warnings, "missing_source_id")
                passed.append(pass_item(item, self.stage_id, reason="missing_source_id"))
                continue
            if max_per_source is None:
                passed.append(pass_item(item, self.stage_id, reason="disabled"))
                continue
            current = counts.get(source_id, 0)
            if current >= max_per_source:
                increment_reason(reasons, "source_cap_exceeded")
                rejected.append(reject_item(item, self.stage_id, reason="source_cap_exceeded", score=float(current + 1)))
                continue
            counts[source_id] = current + 1
            passed.append(pass_item(item, self.stage_id, score=float(counts[source_id])))

        stats = build_filter_stats(
            stage_id=self.stage_id,
            stage_order=self.stage_order,
            items_in=len(items),
            items_passed=len(passed),
            items_rejected=len(rejected),
            rejection_reasons=reasons,
            warnings=warnings,
            started=started,
        )
        return FilterResult(passed=passed, rejected=rejected, stats=stats)


def _max_per_source(config: Mapping[str, Any]) -> int | None:
    direct = _optional_int(config.get("max_per_source"))
    if direct is not None:
        return max(0, direct)
    filters = config.get("filters")
    if isinstance(filters, Mapping):
        source_cap = filters.get("source_cap")
        if isinstance(source_cap, Mapping):
            nested = _optional_int(source_cap.get("max_per_source"))
            if nested is not None:
                return max(0, nested)
    clip_config = config.get("clip_config")
    if isinstance(clip_config, Mapping):
        legacy = _optional_int(clip_config.get("max_scenes_per_source"))
        if legacy is not None:
            return max(0, legacy)
    return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
