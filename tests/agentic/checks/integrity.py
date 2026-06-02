"""Verifier-backed U3 chain-integrity check."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from astrid.audit.graph import verify_audit_ledger
from astrid.core.task.events import verify_chain as task_verify_chain
from astrid.core.timeline.eventlog import LocalFsBackend

from tests.agentic.checks.io import FrozenEvidencePack
from tests.agentic.checks.results import ScoredCheckResult, build_check_result


def u3_chain_integrity(evidence_dir: Path | str | FrozenEvidencePack) -> ScoredCheckResult:
    """Verify every present frozen chain with its production verifier."""

    pack = evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)
    evidence_refs: list[str] = []
    subchecks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for timeline_dir in pack.timeline_dirs():
        events_path = timeline_dir / "assembly.jsonl"
        if pack.read_bytes(events_path) is None:
            continue
        identity_path = timeline_dir / "assembly.identity.json"
        evidence_refs.extend(pack.evidence_refs((events_path,)))
        identity = pack.read_json(identity_path)
        if identity is not None:
            evidence_refs.extend(pack.evidence_refs((identity_path,)))
        result = _verify_timeline_chain(pack, timeline_dir, identity)
        subchecks.append(result)
        if not result["ok"]:
            failures.append(result)

    for run_dir in pack.run_dirs():
        events_path = run_dir / "events.jsonl"
        if pack.read_bytes(events_path) is not None:
            evidence_refs.extend(pack.evidence_refs((events_path,)))
            result = _verify_task_chain(pack, run_dir)
            subchecks.append(result)
            if not result["ok"]:
                failures.append(result)

        ledger_path = run_dir / "audit" / "ledger.jsonl"
        if pack.read_bytes(ledger_path) is not None:
            evidence_refs.extend(pack.evidence_refs((ledger_path,)))
            result = _verify_audit_chain(pack, run_dir)
            subchecks.append(result)
            if not result["ok"]:
                failures.append(result)

    if not subchecks:
        return build_check_result(
            "U3",
            "na",
            detail={"reason": "no chained logs present in frozen evidence pack"},
        )

    return build_check_result(
        "U3",
        "fail" if failures else "pass",
        evidence_refs=_dedupe(evidence_refs),
        detail={
            "checked_streams": len(subchecks),
            "failures": failures,
            "subchecks": subchecks,
        },
    )


def _verify_timeline_chain(
    pack: FrozenEvidencePack,
    timeline_dir: Path,
    identity: Any,
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "kind": "timeline",
        "evidence_ref": pack.evidence_ref(timeline_dir / "assembly.jsonl"),
        "verifier": "LocalFsBackend.verify_chain",
    }
    if not isinstance(identity, Mapping):
        detail["ok"] = False
        detail["error"] = "assembly.identity.json missing or invalid"
        return detail

    timeline_id = identity.get("timeline_id")
    if not isinstance(timeline_id, str) or not timeline_id:
        detail["ok"] = False
        detail["error"] = "assembly.identity.json missing timeline_id"
        return detail

    verification = LocalFsBackend(
        timeline_id=timeline_id,
        timeline_home=timeline_dir,
    ).verify_chain()
    detail.update(
        ok=verification.ok,
        checked_events=verification.checked_events,
        last_event_id=verification.last_event_id,
        error=verification.error,
    )
    return detail


def _verify_task_chain(pack: FrozenEvidencePack, run_dir: Path) -> dict[str, Any]:
    events_path = run_dir / "events.jsonl"
    ok, last_index, error = task_verify_chain(events_path)
    return {
        "kind": "task_run",
        "evidence_ref": pack.evidence_ref(events_path),
        "verifier": "astrid.core.task.events.verify_chain",
        "ok": ok,
        "last_index": last_index,
        "error": error,
    }


def _verify_audit_chain(pack: FrozenEvidencePack, run_dir: Path) -> dict[str, Any]:
    ok, line_number, error = verify_audit_ledger(run_dir)
    return {
        "kind": "audit",
        "evidence_ref": pack.evidence_ref(run_dir / "audit" / "ledger.jsonl"),
        "verifier": "astrid.audit.graph.verify_audit_ledger",
        "ok": ok,
        "line_number": line_number,
        "error": error,
    }


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
