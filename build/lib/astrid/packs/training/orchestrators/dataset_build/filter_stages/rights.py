"""Deterministic rights metadata filter stage."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from ..interfaces import FilterResult
from ._common import build_filter_stats, increment_reason, pass_item, record_warning, reject_item


DEFAULT_REJECT_STATUSES = {"disallowed", "prohibited", "restricted"}
DEFAULT_WARN_STATUSES = {"", "unknown", "needs_review"}


class RightsFilter:
    @property
    def stage_id(self) -> str:
        return "rights_filter"

    @property
    def stage_order(self) -> int:
        return 6

    def apply(self, items: list[dict[str, Any]], state: dict[str, Any], config: dict[str, Any]) -> FilterResult:
        started = time.perf_counter()
        reject_statuses = _string_set(config.get("reject_statuses"), default=DEFAULT_REJECT_STATUSES)
        restricted_licenses = _string_set(config.get("restricted_licenses"), default=set())
        passed: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        reasons: dict[str, int] = {}
        warnings: list[str] = []

        for item in items:
            rights = item.get("rights")
            if not isinstance(rights, Mapping):
                record_warning(warnings, "missing_rights")
                passed.append(pass_item(item, self.stage_id, reason="missing_rights"))
                continue

            status = _norm(rights.get("rights_status"))
            license_id = _norm(rights.get("license"))
            if status in reject_statuses:
                increment_reason(reasons, "rights_status_restricted")
                rejected.append(reject_item(item, self.stage_id, reason="rights_status_restricted"))
                continue
            if license_id and license_id in restricted_licenses:
                increment_reason(reasons, "license_restricted")
                rejected.append(reject_item(item, self.stage_id, reason="license_restricted"))
                continue
            if status in DEFAULT_WARN_STATUSES:
                record_warning(warnings, "unknown_rights")
                passed.append(pass_item(item, self.stage_id, reason="unknown_rights"))
                continue
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


def _string_set(value: Any, *, default: set[str]) -> set[str]:
    if value is None:
        return set(default)
    if isinstance(value, str):
        return {_norm(value)}
    if isinstance(value, list):
        return {_norm(entry) for entry in value}
    return set(default)


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()
