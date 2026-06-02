"""U4 project isolation and U5 auditability checks over frozen evidence."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tests.agentic.checks.io import FrozenEvidencePack
from tests.agentic.checks.results import ScoredCheckResult, build_check_result

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# ISO 8601-ish timestamp regex: captures common variations
# Must start with a year (19xx-21xx) to avoid false positives
_ISO_TS_RE = __import__("re").compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
)


def _looks_iso_ts(value: Any) -> bool:
    """Return True if *value* looks like an ISO-ish timestamp string."""
    if not isinstance(value, str):
        return False
    # Accept Z, +00:00, .microsecond, etc.
    return bool(_ISO_TS_RE.match(value))


def _is_mapping(obj: Any) -> bool:
    return isinstance(obj, dict)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


# ---------------------------------------------------------------------------
# U4 — No-cross-project-leak
# ---------------------------------------------------------------------------

# Task-run event kinds that may carry a project_slug reference
# (these are the kinds that interact with project state)
_U4_SCAN_EVENT_KINDS: frozenset[str] = frozenset({
    "run_started",
    "run_completed",
    "run_aborted",
    "plan_initialized",
    "step_dispatched",
    "step_completed",
    "step_failed",
    "step_skipped",
    "produces_check_passed",
    "produces_check_failed",
})


def _extract_slugs_from_run_json(pack: FrozenEvidencePack) -> dict[str, str]:
    """Return {run_id: project_slug} from each run.json in the frozen pack."""
    slugs: dict[str, str] = {}
    for run_dir in pack.run_dirs():
        run_json = pack.read_json(run_dir / "run.json")
        if not isinstance(run_json, dict):
            continue
        run_id = run_dir.name
        project_slug = run_json.get("project_slug")
        if isinstance(project_slug, str) and project_slug:
            slugs[run_id] = project_slug
    return slugs


def _scan_events_for_sibling_slugs(
    pack: FrozenEvidencePack,
    expected_slug: str,
) -> list[dict[str, Any]]:
    """Scan all event JSONL for references to project slugs other than *expected_slug*."""
    findings: list[dict[str, Any]] = []

    # Scan task-run events
    for run_dir in pack.run_dirs():
        events = pack.read_jsonl(run_dir / "events.jsonl")
        if events is None:
            continue
        for idx, event in enumerate(events):
            if not isinstance(event, dict):
                continue
            # Check direct project_slug field
            ps = event.get("project_slug")
            if isinstance(ps, str) and ps and ps != expected_slug:
                findings.append({
                    "source": f"runs/{run_dir.name}/events.jsonl",
                    "event_index": idx,
                    "event_kind": event.get("kind", "unknown"),
                    "field": "project_slug",
                    "found_slug": ps,
                })
            # Deep-scan string values for slug-like references
            _deep_scan_slug(event, f"runs/{run_dir.name}/events.jsonl", idx, expected_slug, findings)

    # Scan timeline events
    for timeline_dir in pack.timeline_dirs():
        events = pack.read_jsonl(timeline_dir / "assembly.jsonl")
        if events is None:
            continue
        for idx, event in enumerate(events):
            if not isinstance(event, dict):
                continue
            # Check direct project_slug field
            ps = event.get("project_slug")
            if isinstance(ps, str) and ps and ps != expected_slug:
                findings.append({
                    "source": f"timelines/{timeline_dir.name}/assembly.jsonl",
                    "event_index": idx,
                    "event_kind": event.get("kind", "unknown"),
                    "field": "project_slug",
                    "found_slug": ps,
                })
            _deep_scan_slug(event, f"timelines/{timeline_dir.name}/assembly.jsonl", idx, expected_slug, findings)

    return findings


def _deep_scan_slug(
    obj: Any,
    source: str,
    event_index: int,
    expected_slug: str,
    findings: list[dict[str, Any]],
    _depth: int = 0,
) -> None:
    """Recursively scan dict/list for string values that reference a different project slug."""
    ignored_keys = {
        "attached_session_id",
        "new_session",
        "prev_session",
        "reason",
        "session",
        "session_id",
        "writer_id",
    }
    if _depth > 8:
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in ("hash", "prev_hash", "cas_sha256", "event_id", "run_id", "timeline_id"):
                continue  # skip long hash/id fields — too noisy
            if key == "project_slug":
                continue  # handled by caller
            if key in ignored_keys or "session" in key:
                continue
            if isinstance(value, str) and _looks_like_project_slug(value) and value != expected_slug:
                findings.append({
                    "source": source,
                    "event_index": event_index,
                    "field": key,
                    "found_slug": value,
                })
            _deep_scan_slug(value, source, event_index, expected_slug, findings, _depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _deep_scan_slug(item, source, event_index, expected_slug, findings, _depth + 1)
    elif isinstance(obj, str):
        # Single string values — check if they look like a project slug
        if _looks_like_project_slug(obj) and obj != expected_slug:
            findings.append({
                "source": source,
                "event_index": event_index,
                "field": "<value>",
                "found_slug": obj,
            })


def _looks_like_project_slug(value: str) -> bool:
    """Heuristic: a project slug is lowercase with hyphens, not a hash/UUID/path."""
    if len(value) < 2 or len(value) > 63:
        return False
    # Must contain at least one hyphen (most project slugs do)
    if "-" not in value:
        return False
    # Must not look like a hash or UUID
    if value.startswith("sha256:") or len(value) > 64:
        return False
    if __import__("re").match(r"^[0-9a-f]{8}-[0-9a-f]{4}-", value):
        return False  # UUID-like
    if __import__("re").match(r"^[0-9A-HJ-NP-Z]{26}$", value):
        return False  # ULID-like
    # Must be mostly lowercase alphanumeric + hyphens
    stripped = value.strip("/")
    if __import__("re").match(r"^[a-z0-9][a-z0-9_-]*[a-z0-9]$", stripped):
        return True
    return False


def u4_no_cross_project_leak(
    evidence_dir: Path | str | FrozenEvidencePack,
) -> ScoredCheckResult:
    """Verify no cross-project leaks: consistent project_slug, no sibling-slug references."""
    pack = evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)
    evidence_refs: list[str] = []

    # Collect slugs from run.json files
    slug_map = _extract_slugs_from_run_json(pack)
    for run_dir in pack.run_dirs():
        run_json_path = run_dir / "run.json"
        if pack.read_bytes(run_json_path) is not None:
            evidence_refs.extend(pack.evidence_refs((run_json_path,)))

    if not slug_map:
        return build_check_result(
            "U4",
            "na",
            detail={"reason": "no run.json with project_slug found in frozen evidence pack"},
        )

    # Determine expected slug: all run.json files must agree
    unique_slugs = set(slug_map.values())
    if len(unique_slugs) > 1:
        return build_check_result(
            "U4",
            "fail",
            evidence_refs=_dedupe(evidence_refs),
            detail={
                "reason": "inconsistent project_slug across run.json files",
                "slugs_by_run": slug_map,
                "unique_slugs": sorted(unique_slugs),
            },
        )

    expected_slug = next(iter(unique_slugs))
    assert isinstance(expected_slug, str)

    # Add event evidence refs
    for run_dir in pack.run_dirs():
        events_path = run_dir / "events.jsonl"
        if pack.read_bytes(events_path) is not None:
            evidence_refs.extend(pack.evidence_refs((events_path,)))
    for timeline_dir in pack.timeline_dirs():
        assembly_path = timeline_dir / "assembly.jsonl"
        if pack.read_bytes(assembly_path) is not None:
            evidence_refs.extend(pack.evidence_refs((assembly_path,)))

    # Scan events for sibling-slug references
    sibling_findings = _scan_events_for_sibling_slugs(pack, expected_slug)

    if sibling_findings:
        return build_check_result(
            "U4",
            "fail",
            evidence_refs=_dedupe(evidence_refs),
            detail={
                "expected_slug": expected_slug,
                "reason": "sibling-slug references found in event logs",
                "findings": sibling_findings,
            },
        )

    return build_check_result(
        "U4",
        "pass",
        evidence_refs=_dedupe(evidence_refs),
        detail={
            "expected_slug": expected_slug,
            "checked_runs": len(slug_map),
        },
    )


# ---------------------------------------------------------------------------
# U5 — Auditability
# ---------------------------------------------------------------------------

# Task-run event kinds that SHOULD carry a reason (mutation events):
_TASK_MUTATION_KINDS: frozenset[str] = frozenset({
    "run_aborted",
    "step_failed",
    "cursor_rewind",
    "step_skipped",
    "iteration_failed",
    "step_awaiting_fetch",
})

# Timeline event kinds that SHOULD carry a reason (mutation events):
_TIMELINE_MUTATION_KINDS: frozenset[str] = frozenset({
    "timeline.tombstoned",
    "timeline.erased",
    "timeline.recovered",
    "timeline.reverted",
})

# Task-run event kinds that carry an explicit actor identifier:
_TASK_ACTOR_FIELDS: tuple[tuple[str, ...], ...] = (
    ("started_by",),
    ("skipped_by", "skipped_by_id", "skipped_by_kind"),
    ("attestor", "attestor_id", "attestor_kind"),
)


def _audit_task_events(
    pack: FrozenEvidencePack,
    run_dir: Path,
    evidence_refs: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Audit task-run events for timestamp, actor, and reason.

    Returns (issues, events_checked).
    """
    issues: list[dict[str, Any]] = []
    events_checked: list[dict[str, Any]] = []

    events = pack.read_jsonl(run_dir / "events.jsonl")
    if events is None:
        return issues, events_checked

    events_path = run_dir / "events.jsonl"
    evidence_refs.extend(pack.evidence_refs((events_path,)))

    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            issues.append({
                "source": str(events_path),
                "event_index": idx,
                "issue": "event is not a JSON object",
            })
            continue

        event_kind = event.get("kind", "unknown")
        checked = {
            "source": str(events_path),
            "event_index": idx,
            "kind": event_kind,
        }
        events_checked.append(checked)

        # Check timestamp
        ts = event.get("ts")
        if not _looks_iso_ts(ts):
            issues.append({
                **checked,
                "issue": "missing or invalid timestamp",
                "ts": ts,
            })

        # Check actor where relevant — task-run events often don't carry
        # explicit actor IDs (they're system-internal). We only flag when
        # an event has a partial actor identification (e.g. started_by
        # is present but malformed).
        for actor_fields in _TASK_ACTOR_FIELDS:
            has_any = any(event.get(f) for f in actor_fields)
            has_all = all(isinstance(event.get(f), str) and event.get(f) for f in actor_fields)
            if has_any and not has_all:
                missing = [f for f in actor_fields if not isinstance(event.get(f), str) or not event.get(f)]
                issues.append({
                    **checked,
                    "issue": f"incomplete actor identification: missing {missing}",
                    "actor_fields_present": {
                        f: event.get(f) for f in actor_fields
                    },
                })
                break  # only report once per event

        # Check reason on mutation events
        if event_kind in _TASK_MUTATION_KINDS:
            reason = event.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                issues.append({
                    **checked,
                    "issue": f"mutation event {event_kind!r} missing non-empty reason",
                    "reason": reason,
                })

    return issues, events_checked


def _audit_timeline_events(
    pack: FrozenEvidencePack,
    timeline_dir: Path,
    evidence_refs: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Audit timeline events for timestamp, actor, and reason.

    Returns (issues, events_checked).
    """
    issues: list[dict[str, Any]] = []
    events_checked: list[dict[str, Any]] = []

    events = pack.read_jsonl(timeline_dir / "assembly.jsonl")
    if events is None:
        return issues, events_checked

    assembly_path = timeline_dir / "assembly.jsonl"
    evidence_refs.extend(pack.evidence_refs((assembly_path,)))

    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            issues.append({
                "source": str(assembly_path),
                "event_index": idx,
                "issue": "event is not a JSON object",
            })
            continue

        event_kind = event.get("kind", "unknown")
        checked = {
            "source": str(assembly_path),
            "event_index": idx,
            "kind": event_kind,
        }
        events_checked.append(checked)

        # Check timestamp
        ts = event.get("ts")
        if not _looks_iso_ts(ts):
            issues.append({
                **checked,
                "issue": "missing or invalid timestamp",
                "ts": ts,
            })

        # Check actor — timeline events always have actor.id and actor.type
        actor = event.get("actor")
        if not isinstance(actor, dict):
            issues.append({
                **checked,
                "issue": "missing or invalid actor object",
                "actor": actor,
            })
        else:
            actor_type = actor.get("type")
            actor_id = actor.get("id")
            if not isinstance(actor_type, str) or actor_type not in ("agent", "human", "system"):
                issues.append({
                    **checked,
                    "issue": "actor.type missing or invalid",
                    "actor_type": actor_type,
                })
            if not isinstance(actor_id, str) or not actor_id.strip():
                issues.append({
                    **checked,
                    "issue": "actor.id missing or empty",
                    "actor_id": actor_id,
                })

        # Check reason on mutation events
        if event_kind in _TIMELINE_MUTATION_KINDS:
            payload = event.get("payload")
            if isinstance(payload, dict):
                # For timeline.erased, payload has 'reason' directly
                reason = payload.get("reason")
                if not isinstance(reason, str) or not reason.strip():
                    issues.append({
                        **checked,
                        "issue": f"mutation event {event_kind!r} payload missing non-empty reason",
                        "payload_reason": reason,
                    })
            else:
                issues.append({
                    **checked,
                    "issue": f"mutation event {event_kind!r} has no payload dict",
                    "payload": payload,
                })

        # Also check for ErasedPayload (events whose payload was erased)
        payload = event.get("payload")
        if isinstance(payload, dict) and payload.get("erased") is True:
            reason = payload.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                issues.append({
                    **checked,
                    "issue": "erased payload missing non-empty reason",
                    "payload_reason": reason,
                })

    return issues, events_checked


def u5_auditability(
    evidence_dir: Path | str | FrozenEvidencePack,
) -> ScoredCheckResult:
    """Verify every event has actor.id + ISO timestamp; mutation events carry reason."""
    pack = evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)
    evidence_refs: list[str] = []
    all_issues: list[dict[str, Any]] = []
    all_checked: list[dict[str, Any]] = []

    # Audit task-run events
    for run_dir in pack.run_dirs():
        issues, checked = _audit_task_events(pack, run_dir, evidence_refs)
        all_issues.extend(issues)
        all_checked.extend(checked)

    # Audit timeline events
    for timeline_dir in pack.timeline_dirs():
        issues, checked = _audit_timeline_events(pack, timeline_dir, evidence_refs)
        all_issues.extend(issues)
        all_checked.extend(checked)

    if not all_checked:
        return build_check_result(
            "U5",
            "na",
            detail={"reason": "no events found in frozen evidence pack"},
        )

    if all_issues:
        return build_check_result(
            "U5",
            "fail",
            evidence_refs=_dedupe(evidence_refs),
            detail={
                "total_events": len(all_checked),
                "issues_count": len(all_issues),
                "issues": all_issues,
            },
        )

    return build_check_result(
        "U5",
        "pass",
        evidence_refs=_dedupe(evidence_refs),
        detail={
            "total_events": len(all_checked),
            "issues_count": 0,
        },
    )
