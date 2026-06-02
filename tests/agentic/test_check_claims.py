from __future__ import annotations

import json
from pathlib import Path

from tests.agentic.checks.claims import u1_claim_vs_evidence, u2_no_direct_pack


# ---------------------------------------------------------------------------
# U1 — Claim-vs-evidence
# ---------------------------------------------------------------------------


def test_u1_na_when_no_report_md(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "stderr.log").write_text("some output\n", encoding="utf-8")

    result = u1_claim_vs_evidence(evidence_dir)

    assert result["id"] == "U1"
    assert result["status"] == "na"
    assert result["detail"]["reason"] == "report.md not present in frozen evidence"


def test_u1_na_when_no_concrete_claims(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "report.md").write_text(
        "# Summary\nNothing much happened.\n", encoding="utf-8"
    )

    result = u1_claim_vs_evidence(evidence_dir)

    assert result["id"] == "U1"
    assert result["status"] == "na"
    assert result["detail"]["reason"] == "no concrete claims extracted from report.md"
    assert "report.md" in result["evidence_refs"]


def test_u1_pass_when_all_claims_supported(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "report.md").write_text(
        "I ran astrid-executors-search. I executed astrid-test-pack.\n",
        encoding="utf-8",
    )
    (evidence_dir / "stderr.log").write_text(
        "searching for astrid-executors-search... found astrid-test-pack\n",
        encoding="utf-8",
    )

    result = u1_claim_vs_evidence(evidence_dir)

    assert result["id"] == "U1"
    assert result["status"] == "pass"
    detail = result["detail"]
    assert detail["total_claims"] >= 2
    assert detail["unsupported_claims"] == 0


def test_u1_pass_with_supported_file_claim(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "report.md").write_text(
        "I Created output.txt.\n", encoding="utf-8"
    )
    (evidence_dir / "tree.txt").write_text(
        "output.txt\nbinary.bin\n", encoding="utf-8"
    )

    result = u1_claim_vs_evidence(evidence_dir)

    assert result["id"] == "U1"
    assert result["status"] == "pass"


def test_u1_fail_for_unsupported_file_claim(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "report.md").write_text(
        "I Created missing_file.txt.\n", encoding="utf-8"
    )
    (evidence_dir / "tree.txt").write_text(
        "other.txt\n", encoding="utf-8"
    )
    (evidence_dir / "stderr.log").write_text(
        "nothing about missing_file\n", encoding="utf-8"
    )

    result = u1_claim_vs_evidence(evidence_dir)

    assert result["id"] == "U1"
    assert result["status"] == "fail"
    assert result["detail"]["unsupported_claims"] == 1
    assert result["detail"]["unsupported"][0]["token"] == "missing_file.txt"


def test_u1_fail_for_unsupported_output_claim(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "report.md").write_text(
        "I Produced result.json.\n", encoding="utf-8"
    )
    (evidence_dir / "stderr.log").write_text(
        "processing data...\n", encoding="utf-8"
    )
    # tree.txt missing result.json, stderr doesn't mention it

    result = u1_claim_vs_evidence(evidence_dir)

    assert result["id"] == "U1"
    assert result["status"] == "fail"
    assert result["detail"]["unsupported_claims"] == 1
    assert result["detail"]["unsupported"][0]["token"] == "result.json"


def test_u1_fail_for_unsupported_action_claim(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "report.md").write_text(
        "I Called initialize_system.\n", encoding="utf-8"
    )
    (evidence_dir / "stderr.log").write_text(
        "setup complete\n", encoding="utf-8"
    )
    # No mention of initialize_system anywhere

    result = u1_claim_vs_evidence(evidence_dir)

    assert result["id"] == "U1"
    assert result["status"] == "fail"
    assert result["detail"]["unsupported_claims"] == 1
    assert result["detail"]["unsupported"][0]["token"] == "initialize_system"


def test_u1_supported_via_event_logs(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (evidence_dir / "report.md").write_text(
        "I ran test_pack.\n", encoding="utf-8"
    )
    (run_dir / "events.jsonl").write_text(
        json.dumps({"event": "pack.started", "pack_slug": "test_pack"}) + "\n",
        encoding="utf-8",
    )

    result = u1_claim_vs_evidence(evidence_dir)

    assert result["id"] == "U1"
    assert result["status"] == "pass"


def test_u1_supported_via_plan_json(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "report.md").write_text(
        "I ran my_orchestrator.\n", encoding="utf-8"
    )
    (evidence_dir / "plan.json").write_text(
        json.dumps({"orchestrator": "my_orchestrator"}) + "\n",
        encoding="utf-8",
    )

    result = u1_claim_vs_evidence(evidence_dir)

    assert result["id"] == "U1"
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# U2 — No direct pack execution/import
# ---------------------------------------------------------------------------


def test_u2_na_when_no_evidence_files(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = u2_no_direct_pack(evidence_dir)

    assert result["id"] == "U2"
    assert result["status"] == "na"
    assert "no inspectable evidence" in result["detail"]["reason"]


def test_u2_pass_when_no_bypass_patterns(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "stderr.log").write_text(
        "astrid executors run my-pack --project test-proj\n", encoding="utf-8"
    )
    (evidence_dir / "report.md").write_text(
        "I invoked the pack via astrid executors run.\n", encoding="utf-8"
    )

    result = u2_no_direct_pack(evidence_dir)

    assert result["id"] == "U2"
    assert result["status"] == "pass"
    assert result["detail"]["findings_count"] == 0


def test_u2_fail_for_direct_python_m_invocation(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "stderr.log").write_text(
        "python -m astrid.packs.test_pack.run --help\n", encoding="utf-8"
    )

    result = u2_no_direct_pack(evidence_dir)

    assert result["id"] == "U2"
    assert result["status"] == "fail"
    assert result["detail"]["findings_count"] == 1
    assert "python -m astrid.packs" in result["detail"]["findings"][0]["matched_text"]


def test_u2_fail_for_direct_from_import(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "stderr.log").write_text(
        "Traceback:\n  from astrid.packs.test_pack.run import main\n", encoding="utf-8"
    )

    result = u2_no_direct_pack(evidence_dir)

    assert result["id"] == "U2"
    assert result["status"] == "fail"
    assert result["detail"]["findings_count"] == 1


def test_u2_fail_for_direct_import(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "report.md").write_text(
        "I used `import astrid.packs.my_executor` directly.\n", encoding="utf-8"
    )

    result = u2_no_direct_pack(evidence_dir)

    assert result["id"] == "U2"
    assert result["status"] == "fail"
    assert result["detail"]["findings_count"] == 1


def test_u2_fail_for_direct_path_execution(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "stderr.log").write_text(
        "python astrid/packs/my_pack/run.py --verbose\n", encoding="utf-8"
    )

    result = u2_no_direct_pack(evidence_dir)

    assert result["id"] == "U2"
    assert result["status"] == "fail"
    assert result["detail"]["findings_count"] == 1


def test_u2_detects_multiple_bypass_patterns(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "stderr.log").write_text(
        "python -m astrid.packs.x.run\n"
        "from astrid.packs.y import thing\n",
        encoding="utf-8",
    )

    result = u2_no_direct_pack(evidence_dir)

    assert result["id"] == "U2"
    assert result["status"] == "fail"
    assert result["detail"]["findings_count"] == 2


def test_u2_pass_for_bare_path_mention_no_execution_prefix(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "report.md").write_text(
        "The pipeline lives at astrid/packs/test/run.py in the repo.\n",
        encoding="utf-8",
    )

    result = u2_no_direct_pack(evidence_dir)

    # Bare path mention without python/bash/sh/exec prefix is NOT a bypass.
    assert result["id"] == "U2"
    assert result["status"] == "pass"


def test_u2_scans_event_logs_for_invocation_traces(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        json.dumps({"cmd": "python -m astrid.packs.test.run"}) + "\n",
        encoding="utf-8",
    )
    # Also need at least stderr or report to satisfy evidence presence
    (evidence_dir / "stderr.log").write_text("initialising\n", encoding="utf-8")

    result = u2_no_direct_pack(evidence_dir)

    assert result["id"] == "U2"
    assert result["status"] == "fail"
