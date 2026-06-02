"""M4 deterministic scenario checks over frozen evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from tests.agentic.checks.io import FrozenEvidencePack
from tests.agentic.checks.results import ScoredCheckResult, build_check_result

M4TriggerSource = Literal["scenario_extras", "manifest", "absent"]

M4_CHECK_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        "m4.orchestrator_run_persists.terminal_success",
        "orchestrator_run_persists",
        "orchestrator_run_persists_terminal_success",
    ),
    (
        "m4.artifact_pipeline.provenance_handoff",
        "artifact_pipeline",
        "artifact_pipeline_provenance_handoff",
    ),
    (
        "m4.timeline_compose_edit.composite_projection",
        "timeline_compose_edit",
        "timeline_compose_edit_composite_projection",
    ),
    (
        "m4.timeline_concurrent_version_conflict.stale_version_conflict",
        "timeline_concurrent_version_conflict",
        "timeline_concurrent_version_conflict_stale_version_conflict",
    ),
    (
        "m4.taskrun_concurrent_lease.single_writer_lease",
        "taskrun_concurrent_lease",
        "taskrun_concurrent_lease_single_writer_lease",
    ),
    (
        "m4.durability_after_crash.head_jsonl_desync_detected",
        "durability_after_crash",
        "durability_after_crash_head_jsonl_desync_detected",
    ),
    (
        "m4.timeline_large_audit.large_chain_verified",
        "timeline_large_audit",
        "timeline_large_audit_large_chain_verified",
    ),
)

_REQUIRED_EVIDENCE = {
    "orchestrator_run_persists": ("m4/orchestrator_run_persists.json",),
    "artifact_pipeline": ("m4/artifact_pipeline.json",),
    "timeline_compose_edit": ("m4/timeline_compose_edit.json",),
    "timeline_concurrent_version_conflict": ("m4/timeline_concurrent_version_conflict.json",),
    "taskrun_concurrent_lease": ("m4/taskrun_concurrent_lease.json",),
    "durability_after_crash": (
        "m4/durability_after_crash.json",
        "m4/desync/assembly.head.json",
        "m4/desync/assembly.jsonl",
    ),
    "timeline_large_audit": ("m4/timeline_large_audit.json",),
}

_TIMELINE_COMPOSE_FEATURES = frozenset(
    {"track", "clip", "audio_bind", "transition", "effect", "theme"}
)
_TASKRUN_LEASE_ERRORS = frozenset({"StaleEpochError", "NotWriterError"})


@dataclass(frozen=True)
class M4CheckRecord:
    """Normalized declaration for one optional M4 scenario check."""

    stable_id: str
    trigger_key: str
    enabled: bool
    source: M4TriggerSource
    config: Mapping[str, Any]
    required_evidence: tuple[str, ...]


def resolve_m4_check_records(
    *,
    scenario_extras: Mapping[str, Any] | None = None,
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, M4CheckRecord]:
    """Resolve M4 deterministic checks from scenario extras or manifest."""
    declarations, source = _resolve_m4_checks_mapping(
        scenario_extras=scenario_extras,
        manifest=manifest,
    )

    records: dict[str, M4CheckRecord] = {}
    for stable_id, trigger_key, _fn_name in M4_CHECK_SPECS:
        raw_config = declarations.get(trigger_key)
        config = raw_config if isinstance(raw_config, Mapping) else {}
        enabled = bool(config.get("enabled"))
        record_source: M4TriggerSource = source if raw_config is not None else "absent"
        records[stable_id] = M4CheckRecord(
            stable_id=stable_id,
            trigger_key=trigger_key,
            enabled=enabled,
            source=record_source,
            config=dict(config),
            required_evidence=_REQUIRED_EVIDENCE[trigger_key],
        )
    return records


def orchestrator_run_persists_terminal_success(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M4CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m4_check(pack, trigger_record)
    if gated is not None:
        return gated

    diagnostic_path = "m4/orchestrator_run_persists.json"
    payload = _load_json_object(pack, diagnostic_path)
    evidence_refs = _evidence_refs(pack, diagnostic_path, *pack.glob_files("runs/*/events.jsonl"), *pack.glob_files("runs/*/run.json"))
    mismatches: list[dict[str, Any]] = []

    if payload.get("terminal_status") != "success":
        mismatches.append({"field": "terminal_status", "expected": "success", "actual": payload.get("terminal_status")})
    if payload.get("run_json_status") != "success":
        mismatches.append({"field": "run_json_status", "expected": "success", "actual": payload.get("run_json_status")})
    if not bool(payload.get("artifacts_match_cas")):
        mismatches.append({"field": "artifacts_match_cas", "expected": True, "actual": payload.get("artifacts_match_cas")})
    if _as_int(payload.get("produces_event_count")) < 1:
        mismatches.append({"field": "produces_event_count", "expected": ">= 1", "actual": payload.get("produces_event_count")})
    if _as_int(payload.get("artifact_count")) < 1:
        mismatches.append({"field": "artifact_count", "expected": ">= 1", "actual": payload.get("artifact_count")})

    return _result(
        "m4.orchestrator_run_persists.terminal_success",
        evidence_refs=evidence_refs,
        mismatches=mismatches,
        detail=payload,
    )


def artifact_pipeline_provenance_handoff(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M4CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m4_check(pack, trigger_record)
    if gated is not None:
        return gated

    diagnostic_path = "m4/artifact_pipeline.json"
    payload = _load_json_object(pack, diagnostic_path)
    evidence_refs = _evidence_refs(pack, diagnostic_path, *pack.glob_files("runs/*/events.jsonl"))
    mismatches: list[dict[str, Any]] = []

    upstream_sha = payload.get("upstream_artifact_sha256")
    downstream_sha = payload.get("downstream_input_sha256")
    if not isinstance(upstream_sha, str) or not upstream_sha:
        mismatches.append({"field": "upstream_artifact_sha256", "expected": "non-empty sha256", "actual": upstream_sha})
    if not isinstance(downstream_sha, str) or not downstream_sha:
        mismatches.append({"field": "downstream_input_sha256", "expected": "non-empty sha256", "actual": downstream_sha})
    if upstream_sha != downstream_sha:
        mismatches.append({"field": "sha256_handoff", "expected": upstream_sha, "actual": downstream_sha})
    if not bool(payload.get("handoff_matches")):
        mismatches.append({"field": "handoff_matches", "expected": True, "actual": payload.get("handoff_matches")})
    if not bool(payload.get("matched_provenance")):
        mismatches.append({"field": "matched_provenance", "expected": True, "actual": payload.get("matched_provenance")})
    if payload.get("orphan_artifacts") not in ([], None):
        mismatches.append({"field": "orphan_artifacts", "expected": [], "actual": payload.get("orphan_artifacts")})

    return _result(
        "m4.artifact_pipeline.provenance_handoff",
        evidence_refs=evidence_refs,
        mismatches=mismatches,
        detail=payload,
    )


def timeline_compose_edit_composite_projection(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M4CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m4_check(pack, trigger_record)
    if gated is not None:
        return gated

    diagnostic_path = "m4/timeline_compose_edit.json"
    payload = _load_json_object(pack, diagnostic_path)
    evidence_refs = _evidence_refs(pack, diagnostic_path, *pack.glob_files("timelines/*/assembly.jsonl"), *pack.glob_files("timelines/*/assembly.json"))
    features_present = {
        str(feature)
        for feature in payload.get("features_present", [])
        if isinstance(feature, str) and feature
    }
    mismatches: list[dict[str, Any]] = []

    if not bool(payload.get("verify_chain_ok")):
        mismatches.append({"field": "verify_chain_ok", "expected": True, "actual": payload.get("verify_chain_ok")})
    if not bool(payload.get("head_consistency_ok")):
        mismatches.append({"field": "head_consistency_ok", "expected": True, "actual": payload.get("head_consistency_ok")})
    if not bool(payload.get("projection_fidelity_ok")):
        mismatches.append({"field": "projection_fidelity_ok", "expected": True, "actual": payload.get("projection_fidelity_ok")})
    missing_features = sorted(_TIMELINE_COMPOSE_FEATURES - features_present)
    if missing_features:
        mismatches.append({"field": "features_present", "expected": sorted(_TIMELINE_COMPOSE_FEATURES), "actual": sorted(features_present)})

    return _result(
        "m4.timeline_compose_edit.composite_projection",
        evidence_refs=evidence_refs,
        mismatches=mismatches,
        detail={**payload, "missing_features": missing_features},
    )


def timeline_concurrent_version_conflict_stale_version_conflict(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M4CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m4_check(pack, trigger_record)
    if gated is not None:
        return gated

    diagnostic_path = "m4/timeline_concurrent_version_conflict.json"
    payload = _load_json_object(pack, diagnostic_path)
    evidence_refs = _evidence_refs(pack, diagnostic_path, *pack.glob_files("timelines/*/assembly.jsonl"))
    mismatches: list[dict[str, Any]] = []

    if payload.get("loser_error") != "EventLogStaleVersionError":
        mismatches.append({"field": "loser_error", "expected": "EventLogStaleVersionError", "actual": payload.get("loser_error")})
    if not bool(payload.get("winner_appended")):
        mismatches.append({"field": "winner_appended", "expected": True, "actual": payload.get("winner_appended")})
    if not bool(payload.get("verify_chain_ok")):
        mismatches.append({"field": "verify_chain_ok", "expected": True, "actual": payload.get("verify_chain_ok")})
    if payload.get("mechanism") not in {"expected_version_conflict", "cas_conflict"}:
        mismatches.append({"field": "mechanism", "expected": "expected_version_conflict|cas_conflict", "actual": payload.get("mechanism")})
    if bool(payload.get("mentions_lease")):
        mismatches.append({"field": "mentions_lease", "expected": False, "actual": payload.get("mentions_lease")})

    return _result(
        "m4.timeline_concurrent_version_conflict.stale_version_conflict",
        evidence_refs=evidence_refs,
        mismatches=mismatches,
        detail=payload,
    )


def taskrun_concurrent_lease_single_writer_lease(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M4CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m4_check(pack, trigger_record)
    if gated is not None:
        return gated

    diagnostic_path = "m4/taskrun_concurrent_lease.json"
    payload = _load_json_object(pack, diagnostic_path)
    evidence_refs = _evidence_refs(pack, diagnostic_path, *pack.glob_files("runs/*/events.jsonl"), *pack.glob_files("runs/*/lease.json"))
    mismatches: list[dict[str, Any]] = []

    if payload.get("rejection_error") not in _TASKRUN_LEASE_ERRORS:
        mismatches.append({"field": "rejection_error", "expected": sorted(_TASKRUN_LEASE_ERRORS), "actual": payload.get("rejection_error")})
    if _as_int(payload.get("writer_count")) != 1:
        mismatches.append({"field": "writer_count", "expected": 1, "actual": payload.get("writer_count")})
    if not bool(payload.get("verify_chain_ok")):
        mismatches.append({"field": "verify_chain_ok", "expected": True, "actual": payload.get("verify_chain_ok")})
    if not bool(payload.get("lease_file_present")):
        mismatches.append({"field": "lease_file_present", "expected": True, "actual": payload.get("lease_file_present")})

    return _result(
        "m4.taskrun_concurrent_lease.single_writer_lease",
        evidence_refs=evidence_refs,
        mismatches=mismatches,
        detail=payload,
    )


def durability_after_crash_head_jsonl_desync_detected(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M4CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m4_check(pack, trigger_record)
    if gated is not None:
        return gated

    diagnostic_path = "m4/durability_after_crash.json"
    payload = _load_json_object(pack, diagnostic_path)
    evidence_refs = _evidence_refs(
        pack,
        diagnostic_path,
        "m4/desync/assembly.head.json",
        "m4/desync/assembly.jsonl",
    )
    mismatches: list[dict[str, Any]] = []

    if not bool(payload.get("detection_ok")):
        mismatches.append({"field": "detection_ok", "expected": True, "actual": payload.get("detection_ok")})
    if payload.get("mismatch_kind") != "head_vs_jsonl_desync":
        mismatches.append({"field": "mismatch_kind", "expected": "head_vs_jsonl_desync", "actual": payload.get("mismatch_kind")})
    if bool(payload.get("served_stale_state")):
        mismatches.append({"field": "served_stale_state", "expected": False, "actual": payload.get("served_stale_state")})

    return _result(
        "m4.durability_after_crash.head_jsonl_desync_detected",
        evidence_refs=evidence_refs,
        mismatches=mismatches,
        detail=payload,
    )


def timeline_large_audit_large_chain_verified(
    evidence_dir: Path | str | FrozenEvidencePack,
    *,
    trigger_record: M4CheckRecord | None = None,
) -> ScoredCheckResult:
    pack = _pack(evidence_dir)
    gated = _gate_m4_check(pack, trigger_record)
    if gated is not None:
        return gated

    diagnostic_path = "m4/timeline_large_audit.json"
    payload = _load_json_object(pack, diagnostic_path)
    evidence_refs = _evidence_refs(pack, diagnostic_path, *pack.glob_files("timelines/*/assembly.jsonl"))
    mismatches: list[dict[str, Any]] = []

    if _as_int(payload.get("event_count")) < 500:
        mismatches.append({"field": "event_count", "expected": ">= 500", "actual": payload.get("event_count")})
    if not bool(payload.get("verify_chain_ok")):
        mismatches.append({"field": "verify_chain_ok", "expected": True, "actual": payload.get("verify_chain_ok")})
    if not bool(payload.get("within_budget")):
        mismatches.append({"field": "within_budget", "expected": True, "actual": payload.get("within_budget")})

    return _result(
        "m4.timeline_large_audit.large_chain_verified",
        evidence_refs=evidence_refs,
        mismatches=mismatches,
        detail=payload,
    )


def _pack(evidence_dir: Path | str | FrozenEvidencePack) -> FrozenEvidencePack:
    return evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)


def _result(
    stable_id: str,
    *,
    evidence_refs: list[str],
    mismatches: list[dict[str, Any]],
    detail: Mapping[str, Any],
) -> ScoredCheckResult:
    return build_check_result(
        stable_id,
        "fail" if mismatches else "pass",
        evidence_refs=_dedupe(evidence_refs),
        detail={**detail, "mismatches": mismatches},
    )


def _gate_m4_check(
    pack: FrozenEvidencePack,
    trigger_record: M4CheckRecord | None,
) -> ScoredCheckResult | None:
    if trigger_record is None:
        return None
    if not trigger_record.enabled:
        return build_check_result(
            trigger_record.stable_id,
            "na",
            detail={
                "reason": "trigger not declared",
                "trigger_key": trigger_record.trigger_key,
            },
        )

    missing = [
        evidence_path
        for evidence_path in trigger_record.required_evidence
        if pack.read_bytes(evidence_path) is None
    ]
    if missing:
        return build_check_result(
            trigger_record.stable_id,
            "fail",
            detail={
                "reason": "declared trigger missing required evidence",
                "trigger_key": trigger_record.trigger_key,
                "trigger_source": trigger_record.source,
                "missing_evidence": missing,
            },
        )
    return None


def _resolve_m4_checks_mapping(
    *,
    scenario_extras: Mapping[str, Any] | None,
    manifest: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any], M4TriggerSource]:
    extras_checks = _mapping_at_key(scenario_extras, "m4_checks")
    if extras_checks is not None:
        return extras_checks, "scenario_extras"

    manifest_checks = _mapping_at_key(manifest, "m4_checks")
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


def _load_json_object(pack: FrozenEvidencePack, path: str) -> dict[str, Any]:
    payload = pack.read_json(path)
    if isinstance(payload, dict):
        return payload
    return {}


def _evidence_refs(
    pack: FrozenEvidencePack,
    *paths: Path | str,
) -> list[str]:
    refs: list[str] = []
    for path in paths:
        if pack.read_bytes(path) is not None:
            refs.append(pack.evidence_ref(path))
    return refs


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _as_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return -1
    return value
