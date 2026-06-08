from __future__ import annotations

import hashlib
import json
from pathlib import Path

from astrid.core.audit.transport import append_ledger_record
from tests.conftest import seed_event
from astrid.core.task.events import make_run_started_event
from astrid.core.timeline.eventlog import LocalFsBackend
from astrid.core.timeline.events.schema import TimelineActor

from tests.agentic.checks.artifact_provenance import c2_artifact_provenance
from tests.agentic.checks.claims import u1_claim_vs_evidence, u2_no_direct_pack
from tests.agentic.checks.head_consistency import c1_head_sidecar_consistency
from tests.agentic.checks.hygiene import u6_deliverable_hygiene
from tests.agentic.checks.integrity import u3_chain_integrity
from tests.agentic.checks.isolation import u4_no_cross_project_leak, u5_auditability
from tests.agentic.checks.no_mutation_on_read import c3_no_mutation_on_read
from tests.agentic.checks.projection_fidelity import c4_projection_fidelity
from tests.agentic.checks.triggers import resolve_trigger_records

TIMELINE_ID = "00000000-0000-0000-0000-000000000001"


def test_universal_checks_cover_u1_u6_pass_fail_na_and_exact_result_keys(tmp_path: Path) -> None:
    u1_na_dir = tmp_path / "u1-na"
    u1_na_dir.mkdir()
    u1_na = u1_claim_vs_evidence(u1_na_dir)
    _assert_exact_result_shape(u1_na, "U1", "na")

    u1_pass_dir = tmp_path / "u1-pass"
    u1_pass_dir.mkdir()
    (u1_pass_dir / "report.md").write_text("I ran astrid-search.\n", encoding="utf-8")
    (u1_pass_dir / "stderr.log").write_text("astrid-search finished\n", encoding="utf-8")
    u1_pass = u1_claim_vs_evidence(u1_pass_dir)
    _assert_exact_result_shape(u1_pass, "U1", "pass")

    u1_fail_dir = tmp_path / "u1-fail"
    u1_fail_dir.mkdir()
    (u1_fail_dir / "report.md").write_text("I Created missing.txt.\n", encoding="utf-8")
    u1_fail = u1_claim_vs_evidence(u1_fail_dir)
    _assert_exact_result_shape(u1_fail, "U1", "fail")

    u2_na_dir = tmp_path / "u2-na"
    u2_na_dir.mkdir()
    u2_na = u2_no_direct_pack(u2_na_dir)
    _assert_exact_result_shape(u2_na, "U2", "na")

    u2_pass_dir = tmp_path / "u2-pass"
    u2_pass_dir.mkdir()
    (u2_pass_dir / "stderr.log").write_text("astrid run safe-pack\n", encoding="utf-8")
    u2_pass = u2_no_direct_pack(u2_pass_dir)
    _assert_exact_result_shape(u2_pass, "U2", "pass")

    u2_fail_dir = tmp_path / "u2-fail"
    u2_fail_dir.mkdir()
    (u2_fail_dir / "stderr.log").write_text(
        "python -m astrid.packs.demo_pack.run\n",
        encoding="utf-8",
    )
    u2_fail = u2_no_direct_pack(u2_fail_dir)
    _assert_exact_result_shape(u2_fail, "U2", "fail")

    u3_pass_dir = _build_u3_evidence_pack(tmp_path / "u3-pass")
    u3_pass = u3_chain_integrity(u3_pass_dir)
    _assert_exact_result_shape(u3_pass, "U3", "pass")

    u3_na_dir = tmp_path / "u3-na"
    u3_na_dir.mkdir()
    u3_na = u3_chain_integrity(u3_na_dir)
    _assert_exact_result_shape(u3_na, "U3", "na")

    u4_na_dir = tmp_path / "u4-na"
    u4_na_dir.mkdir()
    u4_na = u4_no_cross_project_leak(u4_na_dir)
    _assert_exact_result_shape(u4_na, "U4", "na")

    u4_pass_dir = tmp_path / "u4-pass"
    u4_pass_dir.mkdir()
    _write_run_json(u4_pass_dir, "run-1", "project-alpha")
    u4_pass = u4_no_cross_project_leak(u4_pass_dir)
    _assert_exact_result_shape(u4_pass, "U4", "pass")

    u4_fail_dir = tmp_path / "u4-fail"
    u4_fail_dir.mkdir()
    _write_run_json(u4_fail_dir, "run-1", "project-alpha")
    _write_run_json(u4_fail_dir, "run-2", "project-beta")
    u4_fail = u4_no_cross_project_leak(u4_fail_dir)
    _assert_exact_result_shape(u4_fail, "U4", "fail")

    u5_na_dir = tmp_path / "u5-na"
    u5_na_dir.mkdir()
    u5_na = u5_auditability(u5_na_dir)
    _assert_exact_result_shape(u5_na, "U5", "na")

    u5_pass_dir = tmp_path / "u5-pass"
    u5_pass_dir.mkdir()
    timeline_dir = u5_pass_dir / "timelines" / "tl-1"
    timeline_dir.mkdir(parents=True)
    _write_jsonl(
        timeline_dir / "assembly.jsonl",
        {
            "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "timeline_id": TIMELINE_ID,
            "ts": "2025-01-01T00:00:00Z",
            "actor": {"type": "agent", "id": "codex:test"},
            "kind": "timeline.created",
            "payload": {"slug": "main", "name": "Main"},
        },
    )
    u5_pass = u5_auditability(u5_pass_dir)
    _assert_exact_result_shape(u5_pass, "U5", "pass")

    u5_fail_dir = tmp_path / "u5-fail"
    u5_fail_dir.mkdir()
    bad_timeline_dir = u5_fail_dir / "timelines" / "tl-1"
    bad_timeline_dir.mkdir(parents=True)
    _write_jsonl(
        bad_timeline_dir / "assembly.jsonl",
        {
            "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
            "timeline_id": TIMELINE_ID,
            "ts": "2025-01-01T00:00:00Z",
            "actor": {"type": "agent"},
            "kind": "timeline.created",
            "payload": {"slug": "main", "name": "Main"},
        },
    )
    u5_fail = u5_auditability(u5_fail_dir)
    _assert_exact_result_shape(u5_fail, "U5", "fail")

    u6_pass_dir = tmp_path / "u6-pass"
    u6_pass_dir.mkdir()
    (u6_pass_dir / "report.md").write_text(_long_report(), encoding="utf-8")
    u6_pass = u6_deliverable_hygiene(u6_pass_dir)
    _assert_exact_result_shape(u6_pass, "U6", "pass")

    u6_fail_dir = tmp_path / "u6-fail"
    u6_fail_dir.mkdir()
    u6_fail = u6_deliverable_hygiene(u6_fail_dir)
    _assert_exact_result_shape(u6_fail, "U6", "fail")


def test_u3_chain_integrity_fails_for_flipped_hashes_in_each_chained_log_kind(tmp_path: Path) -> None:
    timeline_dir = _build_u3_evidence_pack(tmp_path / "timeline-only", include_task=False, include_audit=False)
    _tamper_jsonl_hash(timeline_dir / "timelines" / "timeline-1" / "assembly.jsonl")
    timeline_result = u3_chain_integrity(timeline_dir)
    _assert_exact_result_shape(timeline_result, "U3", "fail")

    task_dir = _build_u3_evidence_pack(tmp_path / "task-only", include_timeline=False, include_audit=False)
    _tamper_jsonl_hash(task_dir / "runs" / "run-1" / "events.jsonl")
    task_result = u3_chain_integrity(task_dir)
    _assert_exact_result_shape(task_result, "U3", "fail")

    audit_dir = _build_u3_evidence_pack(tmp_path / "audit-only", include_timeline=False, include_task=False)
    _tamper_jsonl_hash(audit_dir / "runs" / "run-1" / "audit" / "ledger.jsonl")
    audit_result = u3_chain_integrity(audit_dir)
    _assert_exact_result_shape(audit_result, "U3", "fail")


def test_universal_check_na_results_score_as_passes_through_scored_check_result(tmp_path: Path) -> None:
    results = [
        u1_claim_vs_evidence((tmp_path / "u1").mkdir() or (tmp_path / "u1")),
        u2_no_direct_pack((tmp_path / "u2").mkdir() or (tmp_path / "u2")),
        u3_chain_integrity((tmp_path / "u3").mkdir() or (tmp_path / "u3")),
        u4_no_cross_project_leak((tmp_path / "u4").mkdir() or (tmp_path / "u4")),
        u5_auditability((tmp_path / "u5").mkdir() or (tmp_path / "u5")),
    ]

    u6_dir = tmp_path / "u6"
    u6_dir.mkdir()
    (u6_dir / "report.md").write_text(_long_report(), encoding="utf-8")
    results.append(u6_deliverable_hygiene(u6_dir))

    assert [result["status"] for result in results] == ["na", "na", "na", "na", "na", "pass"]
    assert sum(1 for result in results if result.get("passed", False)) == 6
    assert all(result.get("undetermined") is False for result in results)


def test_conditional_checks_cover_c1_c4_exact_result_keys_and_trigger_na(tmp_path: Path) -> None:
    c1_dir = tmp_path / "c1-pass"
    c1_dir.mkdir()
    _write_timeline_head_pack(c1_dir, timeline_name="tl-1")
    _assert_exact_result_shape(c1_head_sidecar_consistency(c1_dir), "C1", "pass")

    c2_dir = tmp_path / "c2-pass"
    c2_dir.mkdir()
    nested_bytes = b"nested-bytes\n"
    _write_produces_file(
        c2_dir,
        step_path=("compose", "build"),
        step_version=2,
        produces_name="nested.txt",
        data=nested_bytes,
    )
    _write_produces_file(c2_dir, produces_name="default.txt", data=b"default-version\n")
    _write_jsonl_rows(
        c2_dir / "runs" / "run-1" / "events.jsonl",
        [
            _produces_event(
                plan_step_path=["compose", "build"],
                produces_name="nested.txt",
                data=nested_bytes,
                step_version=2,
            ),
            _produces_event(
                plan_step_path=["build"],
                produces_name="default.txt",
                data=b"default-version\n",
                step_version=None,
            ),
        ],
    )
    _assert_exact_result_shape(c2_artifact_provenance(c2_dir), "C2", "pass")

    c3_na = c3_no_mutation_on_read(tmp_path / "c3-na", trigger_record=_c3_disabled())
    _assert_exact_result_shape(c3_na, "C3", "na")

    c4_na = c4_projection_fidelity(tmp_path / "c4-na", trigger_record=_c4_disabled())
    _assert_exact_result_shape(c4_na, "C4", "na")


def test_conditional_checks_cover_required_c2_c4_failures_and_c3_extra_events(tmp_path: Path) -> None:
    c2_orphan_event_dir = tmp_path / "c2-orphan-event"
    c2_orphan_event_dir.mkdir()
    _write_jsonl_rows(
        c2_orphan_event_dir / "runs" / "run-1" / "events.jsonl",
        [_produces_event(plan_step_path=["build"], produces_name="missing.txt", data=b"missing\n")],
    )
    orphan_event = c2_artifact_provenance(c2_orphan_event_dir)
    _assert_exact_result_shape(orphan_event, "C2", "fail")
    assert orphan_event["detail"]["mismatches"][0]["kind"] == "orphan_event"

    c2_orphan_file_dir = tmp_path / "c2-orphan-file"
    c2_orphan_file_dir.mkdir()
    _write_produces_file(c2_orphan_file_dir, produces_name="orphan.txt", data=b"orphan\n")
    orphan_file = c2_artifact_provenance(c2_orphan_file_dir)
    _assert_exact_result_shape(orphan_file, "C2", "fail")
    assert orphan_file["detail"]["mismatches"][0]["kind"] == "orphan_file"

    c2_hash_dir = tmp_path / "c2-hash-mismatch"
    c2_hash_dir.mkdir()
    _write_produces_file(c2_hash_dir, produces_name="wrong.txt", data=b"actual\n")
    _write_jsonl_rows(
        c2_hash_dir / "runs" / "run-1" / "events.jsonl",
        [_produces_event(plan_step_path=["build"], produces_name="wrong.txt", data=b"expected\n")],
    )
    hash_mismatch = c2_artifact_provenance(c2_hash_dir)
    _assert_exact_result_shape(hash_mismatch, "C2", "fail")
    assert hash_mismatch["detail"]["mismatches"][0]["kind"] == "hash_mismatch"

    c3_dir = tmp_path / "c3-extra-events"
    c3_dir.mkdir()
    _write_jsonl_rows(c3_dir / "baseline_events.jsonl", [_make_basic_event(idx=0)])
    _write_jsonl_rows(
        c3_dir / "runs" / "run-1" / "events.jsonl",
        [_make_basic_event(idx=0), _make_basic_event(idx=1, kind="step_dispatched")],
    )
    (c3_dir / "git_diff.patch").write_text("", encoding="utf-8")
    c3_result = c3_no_mutation_on_read(c3_dir, trigger_record=_c3_enabled())
    _assert_exact_result_shape(c3_result, "C3", "fail")
    assert c3_result["detail"]["mismatches"][0]["kind"] == "extra_events"

    c4_dir = tmp_path / "c4-projection-mismatch"
    c4_dir.mkdir()
    _write_timeline_assembly_jsonl(c4_dir, "tl-1", [])
    _write_timeline_assembly_json(c4_dir, "tl-1", {"tracks": [{"id": "extra"}], "clips": []})
    c4_result = c4_projection_fidelity(c4_dir, trigger_record=_c4_enabled())
    _assert_exact_result_shape(c4_result, "C4", "fail")
    assert c4_result["detail"]["mismatches"][0]["kind"] == "projection_mismatch"


def _assert_exact_result_shape(result: dict[str, object], expected_id: str, expected_status: str) -> None:
    assert list(result.keys()) == ["id", "status", "evidence_refs", "detail"]
    assert result["id"] == expected_id
    assert result["status"] == expected_status

    payload = json.loads(json.dumps(result))
    assert list(payload.keys()) == ["id", "status", "evidence_refs", "detail"]
    assert "passed" not in payload
    assert "undetermined" not in payload


def _build_u3_evidence_pack(
    evidence_dir: Path,
    *,
    include_timeline: bool = True,
    include_task: bool = True,
    include_audit: bool = True,
) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)

    if include_timeline:
        timeline_dir = evidence_dir / "timelines" / "timeline-1"
        timeline_dir.mkdir(parents=True)
        (timeline_dir / "assembly.identity.json").write_text(
            json.dumps({"timeline_id": TIMELINE_ID, "timeline_ulid": "timeline-1"}) + "\n",
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
            seed_event(
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


def _write_jsonl(path: Path, row: dict[str, object]) -> None:
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


def _write_jsonl_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_run_json(evidence_dir: Path, run_id: str, project_slug: str) -> None:
    run_dir = evidence_dir / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps({"project_slug": project_slug, "run_id": run_id}),
        encoding="utf-8",
    )
    _write_jsonl(
        run_dir / "events.jsonl",
        {"kind": "run_started", "run_id": run_id, "ts": "2025-01-01T00:00:00Z"},
    )


def _long_report() -> str:
    return "\n".join(f"{index}. report line {index}" for index in range(1, 31)) + "\n"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _produces_event(
    *,
    plan_step_path: list[str],
    produces_name: str,
    data: bytes,
    step_version: int | None = 1,
) -> dict[str, object]:
    event: dict[str, object] = {
        "kind": "produces_check_passed",
        "plan_step_path": plan_step_path,
        "produces_name": produces_name,
        "cas_sha256": _sha256_bytes(data),
        "ts": "2025-01-01T00:00:00Z",
    }
    if step_version is not None:
        event["step_version"] = step_version
    return event


def _write_produces_file(
    evidence_dir: Path,
    *,
    run_id: str = "run-1",
    step_path: tuple[str, ...] = ("build",),
    step_version: int = 1,
    produces_name: str = "output.txt",
    data: bytes = b"hello\n",
) -> None:
    target = (
        evidence_dir
        / "runs"
        / run_id
        / "steps"
        / Path(*step_path)
        / f"v{step_version}"
        / "produces"
        / produces_name
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def _make_basic_event(*, idx: int = 0, kind: str = "run_started") -> dict[str, object]:
    ts_second = 100 + idx
    return {
        "kind": kind,
        "ts": f"2025-01-01T00:01:{ts_second:02d}Z",
        "run_id": "run-1",
        "hash": f"hash-{idx:04d}",
    }


def _c3_enabled():
    return resolve_trigger_records(
        scenario_extras={"m2_checks": {"c3_no_mutation_on_read": {"enabled": True}}}
    )["C3"]


def _c3_disabled():
    return resolve_trigger_records()["C3"]


def _c4_enabled():
    return resolve_trigger_records(
        scenario_extras={"m2_checks": {"c4_projection_fidelity": {"enabled": True}}}
    )["C4"]


def _c4_disabled():
    return resolve_trigger_records()["C4"]


def _write_timeline_head_pack(evidence_dir: Path, *, timeline_name: str) -> None:
    timeline_dir = evidence_dir / "timelines" / timeline_name
    timeline_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": "EV01",
        "timeline_id": TIMELINE_ID,
        "ts": "2025-01-01T00:00:00Z",
        "actor": {"type": "agent", "id": "codex:test"},
        "prev_hash": None,
        "hash": "a" * 64,
        "kind": "timeline.created",
        "payload": {"slug": "main", "name": "Main"},
        "expected_version": None,
        "schema_version": 2,
        "txn_id": None,
    }
    _write_jsonl_rows(timeline_dir / "assembly.jsonl", [event])
    (timeline_dir / "assembly.head.json").write_text(
        json.dumps(
            {
                "timeline_id": TIMELINE_ID,
                "last_event_id": "EV01",
                "last_hash": "a" * 64,
                "event_count": 1,
                "version": 1,
            }
        ),
        encoding="utf-8",
    )


def _write_timeline_assembly_jsonl(evidence_dir: Path, timeline_id: str, rows: list[dict[str, object]]) -> None:
    timeline_dir = evidence_dir / "timelines" / timeline_id
    timeline_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl_rows(timeline_dir / "assembly.jsonl", rows)


def _write_timeline_assembly_json(evidence_dir: Path, timeline_id: str, data: dict[str, object]) -> None:
    timeline_dir = evidence_dir / "timelines" / timeline_id
    timeline_dir.mkdir(parents=True, exist_ok=True)
    (timeline_dir / "assembly.json").write_text(
        json.dumps(data, separators=(",", ":")),
        encoding="utf-8",
    )
