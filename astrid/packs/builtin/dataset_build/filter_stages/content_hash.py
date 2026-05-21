"""Deterministic content-hash duplicate filter stage."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from ..interfaces import FilterResult
from ._common import build_filter_stats, increment_reason, pass_item, record_warning, reject_item


class ContentHashFilter:
    @property
    def stage_id(self) -> str:
        return "content_hash_filter"

    @property
    def stage_order(self) -> int:
        return 4

    def apply(self, items: list[dict[str, Any]], state: dict[str, Any], config: dict[str, Any]) -> FilterResult:
        started = time.perf_counter()
        passed: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        reasons: dict[str, int] = {}
        warnings: list[str] = []
        seen: dict[str, Mapping[str, Any]] = {}

        for item in items:
            content_hash = _content_hash(item)
            if content_hash is None:
                record_warning(warnings, "missing_content_hash")
                passed.append(pass_item(item, self.stage_id, reason="missing_content_hash"))
                continue
            duplicate = seen.get(content_hash)
            if duplicate is not None:
                increment_reason(reasons, "duplicate_content_hash")
                rejected.append(
                    reject_item(
                        item,
                        self.stage_id,
                        reason="duplicate_content_hash",
                        extra={
                            "duplicate_of_item_id": str(duplicate.get("item_id") or ""),
                            "duplicate_of_source_id": str(duplicate.get("source_id") or ""),
                        },
                    )
                )
                continue
            seen[content_hash] = item
            passed.append(pass_item(item, self.stage_id))

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


def _content_hash(item: Mapping[str, Any]) -> str | None:
    value = item.get("content_hash")
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value or None
