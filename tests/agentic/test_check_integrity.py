from __future__ import annotations

import json
from pathlib import Path

from astrid.core.audit.transport import append_ledger_record
from astrid.core.task.events import append_event, make_run_started_event
from astrid.core.timeline.eventlog import LocalFsBackend
from astrid.core.timeline.events.schema import TimelineActor

from tests.agentic.checks import integrity

TIMELINE_ID = "00000000-0000-0000-0000-000000000001"


def test_u3_chain_integrity_passes_and_calls_all_three_production_verifiers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    evidence_dir = _build_evidence_pack(tmp_path)
    calls: dict[str, list[object]] = {"timeline": [], "task": [], "audit": []}

    original_timeline_verify = LocalFsBackend.verify_chain
    original_task_verify = integrity.task_verify_chain
    original_audit_verify = integrity.verify_audit_ledger

    def spy_timeline_verify(self: LocalFsBackend):
        calls["timeline"].append((self.timeline_id, self.timeline_home))
        return original_timeline_verify(self)

    def spy_task_verify(path: str | Path):
        calls["task"].append(Path(path))
        return original_task_verify(path)

    def spy_audit_verify(run_dir: str | Path):
        calls["audit"].append(Path(run_dir))
        return original_audit_verify(run_dir)

    monkeypatch.setattr(LocalFsBackend, "verify_chain", spy_timeline_verify)
    monkeypatch.setattr(integrity, "task_verify_chain", spy_task_verify)
    monkeypatch.setattr(integrity, "verify_audit_ledger", spy_audit_verify)

    result = integrity.u3_chain_integrity(evidence_dir)

    assert result["status"] == "pass"
    assert calls["timeline"] == [(TIMELINE_ID, evidence_dir / "timelines" / "timeline-1")]
    assert calls["task"] == [evidence_dir / "runs" / "run-1" / "events.jsonl"]
    assert calls["audit"] == [evidence_dir / "runs" / "run-1"]


def test_u3_chain_integrity_fails_for_tampered_timeline_chain(tmp_path: Path) -> None:
    evidence_dir = _build_evidence_pack(tmp_path, include_task=False, include_audit=False)
    _tamper_jsonl_hash(evidence_dir / "timelines" / "timeline-1" / "assembly.jsonl")

    result = integrity.u3_chain_integrity(evidence_dir)

    assert result["status"] == "fail"
    assert _subcheck_by_kind(result, "timeline")["verifier"] == "LocalFsBackend.verify_chain"


def test_u3_chain_integrity_fails_for_tampered_task_chain(tmp_path: Path) -> None:
    evidence_dir = _build_evidence_pack(tmp_path, include_timeline=False, include_audit=False)
    _tamper_jsonl_hash(evidence_dir / "runs" / "run-1" / "events.jsonl")

    result = integrity.u3_chain_integrity(evidence_dir)

    assert result["status"] == "fail"
    assert _subcheck_by_kind(result, "task_run")["verifier"] == "astrid.core.task.events.verify_chain"


def test_u3_chain_integrity_fails_for_tampered_audit_chain(tmp_path: Path) -> None:
    evidence_dir = _build_evidence_pack(tmp_path, include_timeline=False, include_task=False)
    _tamper_jsonl_hash(evidence_dir / "runs" / "run-1" / "audit" / "ledger.jsonl")

    result = integrity.u3_chain_integrity(evidence_dir)

    assert result["status"] == "fail"
    assert _subcheck_by_kind(result, "audit")["verifier"] == "astrid.core.audit.graph.verify_audit_ledger"


def test_u3_chain_integrity_returns_na_when_no_chains_are_present(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)

    result = integrity.u3_chain_integrity(evidence_dir)

    assert result == {
        "id": "U3",
        "status": "na",
        "evidence_refs": [],
        "detail": {"reason": "no chained logs present in frozen evidence pack"},
    }


def _build_evidence_pack(
    tmp_path: Path,
    *,
    include_timeline: bool = True,
    include_task: bool = True,
    include_audit: bool = True,
) -> Path:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    if include_timeline:
        timeline_dir = evidence_dir / "timelines" / "timeline-1"
        timeline_dir.mkdir(parents=True)
        (timeline_dir / "assembly.identity.json").write_text(
            json.dumps(
                {
                    "timeline_id": TIMELINE_ID,
                    "timeline_ulid": "timeline-1",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        backend = LocalFsBackend(timeline_id=TIMELINE_ID, timeline_home=timeline_dir)
        backend.append_event(
            TIMELINE_ID,
            "timeline.renamed",
            {"old_slug": "main", "new_slug": "main-v2"},
            actor=TimelineActor(type="agent", id="codex:test"),
        )

    if include_task or include_audit:
        run_dir = evidence_dir / "runs" / "run-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        if include_task:
            append_event(
                run_dir / "events.jsonl",
                make_run_started_event("run-1", "sha256:" + "1" * 64),
            )
        if include_audit:
            append_ledger_record(
                run_dir / "audit" / "ledger.jsonl",
                {
                    "event": "asset.created",
                    "asset_id": "asset-1",
                    "parents": [],
                    "stage": "seed",
                },
            )

    return evidence_dir


def _tamper_jsonl_hash(path: Path) -> None:
    rows = path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(rows[0])
    payload["hash"] = "0" * 64
    rows[0] = json.dumps(payload, separators=(",", ":"))
    path.write_text("".join(f"{row}\n" for row in rows), encoding="utf-8")


def _subcheck_by_kind(result: dict[str, object], kind: str) -> dict[str, object]:
    detail = result["detail"]
    assert isinstance(detail, dict)
    subchecks = detail["subchecks"]
    assert isinstance(subchecks, list)
    for subcheck in subchecks:
        assert isinstance(subcheck, dict)
        if subcheck.get("kind") == kind:
            return subcheck
    raise AssertionError(f"missing subcheck {kind!r}: {subchecks!r}")
