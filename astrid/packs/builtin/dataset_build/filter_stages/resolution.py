"""Deterministic resolution filter stage."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from ..interfaces import FilterResult
from ._common import build_filter_stats, increment_reason, pass_item, record_warning, reject_item


class ResolutionFilter:
    @property
    def stage_id(self) -> str:
        return "resolution_filter"

    @property
    def stage_order(self) -> int:
        return 2

    def apply(self, items: list[dict[str, Any]], state: dict[str, Any], config: dict[str, Any]) -> FilterResult:
        started = time.perf_counter()
        min_width = _optional_int(config.get("min_width"))
        min_height = _optional_int(config.get("min_height"))
        require_metadata = bool(config.get("require_metadata", False))
        passed: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        reasons: dict[str, int] = {}
        warnings: list[str] = []

        for item in items:
            resolution = _resolution(item)
            if resolution is None:
                if require_metadata:
                    increment_reason(reasons, "missing_resolution")
                    rejected.append(reject_item(item, self.stage_id, reason="missing_resolution"))
                    continue
                record_warning(warnings, "missing_resolution")
                passed.append(pass_item(item, self.stage_id, reason="missing_resolution"))
                continue

            width, height = resolution
            score = float(width * height)
            if min_width is not None and width < min_width:
                increment_reason(reasons, "resolution_too_small")
                rejected.append(reject_item(item, self.stage_id, reason="resolution_too_small", score=score))
                continue
            if min_height is not None and height < min_height:
                increment_reason(reasons, "resolution_too_small")
                rejected.append(reject_item(item, self.stage_id, reason="resolution_too_small", score=score))
                continue
            passed.append(pass_item(item, self.stage_id, score=score))

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


def _resolution(item: Mapping[str, Any]) -> tuple[int, int] | None:
    metadata = item.get("source_metadata")
    if isinstance(metadata, Mapping):
        parsed = _parse_resolution(metadata.get("resolution"))
        if parsed is not None:
            return parsed
    return _parse_resolution(item.get("resolution"))


def _parse_resolution(value: Any) -> tuple[int, int] | None:
    if isinstance(value, Mapping):
        width = _optional_int(value.get("width"))
        height = _optional_int(value.get("height"))
        if width is not None and height is not None:
            return width, height
    if isinstance(value, str) and "x" in value.lower():
        left, right = value.lower().split("x", 1)
        width = _optional_int(left)
        height = _optional_int(right)
        if width is not None and height is not None:
            return width, height
    return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
