"""Trigger resolution helpers for optional M2 classified checks."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from tests.agentic.checks.results import ScoredCheckResult, build_check_result

TriggerSource = Literal["scenario_extras", "manifest", "absent"]

_TRIGGER_KEYS = {
    "C3": "c3_no_mutation_on_read",
    "C4": "c4_projection_fidelity",
    "S1": "s1_append_not_rewrite",
    "S2": "s2_idempotent_reattach",
}

_REQUIRED_EVIDENCE = {
    "C3": ("baseline_events", "final_events", "git_diff_patch"),
    "S1": ("baseline_events", "final_events"),
    "S2": ("baseline_events", "final_events", "reattach_diagnostics"),
}


@dataclass(frozen=True)
class TriggerRecord:
    """Normalized declaration for one optional classified check."""

    check_id: str
    trigger_key: str
    enabled: bool
    source: TriggerSource
    config: Mapping[str, Any]
    required_evidence: tuple[str, ...]


def resolve_trigger_records(
    *,
    scenario_extras: Mapping[str, Any] | None = None,
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, TriggerRecord]:
    """Resolve supported trigger declarations from scenario extras or manifest."""
    declarations, source = _resolve_m2_checks_mapping(
        scenario_extras=scenario_extras,
        manifest=manifest,
    )

    records: dict[str, TriggerRecord] = {}
    for check_id, trigger_key in _TRIGGER_KEYS.items():
        raw_config = declarations.get(trigger_key)
        config = raw_config if isinstance(raw_config, Mapping) else {}
        enabled = bool(config.get("enabled"))
        record_source: TriggerSource = source if raw_config is not None else "absent"
        records[check_id] = TriggerRecord(
            check_id=check_id,
            trigger_key=trigger_key,
            enabled=enabled,
            source=record_source,
            config=dict(config),
            required_evidence=_REQUIRED_EVIDENCE.get(check_id, ()),
        )
    return records


def gate_trigger(
    record: TriggerRecord,
    *,
    available_evidence: Collection[str],
) -> ScoredCheckResult | None:
    """Apply absent-trigger and declared-trigger-evidence semantics."""
    if not record.enabled:
        return build_check_result(
            record.check_id,
            "na",
            detail={
                "reason": "trigger not declared",
                "trigger_key": record.trigger_key,
            },
        )

    missing = [
        evidence_name
        for evidence_name in record.required_evidence
        if evidence_name not in available_evidence
    ]
    if missing:
        return build_check_result(
            record.check_id,
            "fail",
            detail={
                "reason": "declared trigger missing required evidence",
                "trigger_key": record.trigger_key,
                "trigger_source": record.source,
                "missing_evidence": missing,
            },
        )

    return None


def _resolve_m2_checks_mapping(
    *,
    scenario_extras: Mapping[str, Any] | None,
    manifest: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any], TriggerSource]:
    extras_checks = _mapping_at_key(scenario_extras, "m2_checks")
    if extras_checks is not None:
        return extras_checks, "scenario_extras"

    manifest_checks = _mapping_at_key(manifest, "m2_checks")
    if manifest_checks is not None:
        return manifest_checks, "manifest"

    return {}, "absent"


def _mapping_at_key(
    container: Mapping[str, Any] | None,
    key: str,
) -> Mapping[str, Any] | None:
    if not isinstance(container, Mapping):
        return None
    value = container.get(key)
    if isinstance(value, Mapping):
        return value
    return None
