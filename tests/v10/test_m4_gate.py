"""Focused B2 regressions for task-bound M4 feasibility admission."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.reshape import m4_gate


def _run_docs() -> Path:
    for parent in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        candidate = parent / ".otto" / "runs" / "timeline-text-workstream-20260831"
        if (candidate / "plan.md").is_file() and (candidate / "tasklist.md").is_file():
            return candidate
    raise AssertionError("frozen OTTO plan/tasklist not found")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    run_root = tmp_path / "run"
    evidence = run_root / "evidence"
    evidence.mkdir(parents=True)
    docs = _run_docs()
    shutil.copy2(docs / "plan.md", run_root / "plan.md")
    shutil.copy2(docs / "tasklist.md", run_root / "tasklist.md")
    feasibility = evidence / "m4-text-binding-feasibility.json"
    feasibility.write_text(
        json.dumps(
            {
                "schema_version": m4_gate.FEASIBILITY_SCHEMA,
                "plan_hash": m4_gate._sha256_prefixed(run_root / "plan.md"),
                "task_contract_hash": m4_gate._sha256_prefixed(run_root / "tasklist.md"),
                "task_count": 33,
                "admitted": True,
            }
        ),
        encoding="utf-8",
    )
    return run_root, evidence, feasibility


def test_canonical_counter_rejects_malformed_rows(tmp_path: Path) -> None:
    tasklist = tmp_path / "tasklist.md"
    tasklist.write_text(
        "## Canonical task table\n\n"
        "| Task ID | Batch | Depends on | Classification | Model |\n"
        "| --- | --- | --- | --- | --- |\n"
        "not a row\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="malformed canonical task row"):
        m4_gate._count_canonical_tasks(tasklist)


def test_live_authority_freezes_exact_writer_baseline_and_parser_edges() -> None:
    from scripts.reshape import authority_lint

    assert (
        frozenset(authority_lint._writer_call_sites(m4_gate.REPO_ROOT))
        == authority_lint.FROZEN_BASELINE_WRITER_CALL_SITES
    )
    ok, violations, exemptions = m4_gate._run_authority_lint()
    assert ok, violations
    assert len(exemptions) == 2
    assert all("astrid.packs.shots.cli" in item or "astrid.packs.references.cli" in item for item in exemptions)


def test_valid_feasibility_is_bound_to_frozen_siblings(tmp_path: Path) -> None:
    _run_root, _evidence, feasibility = _fixture(tmp_path)
    record, problems = m4_gate._check_feasibility(feasibility)
    assert problems == []
    assert record["accepted"] is True
    assert record["authority_validated"] is True
    assert record["observed_task_count"] == 33


def test_feasibility_rejects_boolean_count_and_extra_fields(tmp_path: Path) -> None:
    _run_root, _evidence, feasibility = _fixture(tmp_path)
    data = json.loads(feasibility.read_text(encoding="utf-8"))
    data["task_count"] = True
    data["unexpected"] = "nope"
    feasibility.write_text(json.dumps(data), encoding="utf-8")
    _record, problems = m4_gate._check_feasibility(feasibility)
    assert any("positive non-boolean integer" in problem for problem in problems)
    assert any("unexpected field" in problem for problem in problems)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("schema_version", "wrong", "schema_version"),
        ("plan_hash", "SHA256:" + "a" * 64, "canonical sha256 hash"),
        ("task_contract_hash", "not-a-hash", "canonical sha256 hash"),
        ("task_count", 0, "positive non-boolean integer"),
        ("admitted", False, "exactly true"),
    ),
)
def test_full_run_negative_matrix_rejects_invalid_feasibility(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    _run_root, _evidence, feasibility = _fixture(tmp_path)
    data = json.loads(feasibility.read_text(encoding="utf-8"))
    data[field] = value
    feasibility.write_text(json.dumps(data), encoding="utf-8")
    _record, problems = m4_gate._check_feasibility(feasibility)
    assert any(message in problem for problem in problems), problems


def test_full_run_negative_matrix_rejects_outside_evidence(tmp_path: Path) -> None:
    run_root, _evidence, feasibility = _fixture(tmp_path)
    outside = run_root / "outside.json"
    shutil.copy2(feasibility, outside)
    _record, problems = m4_gate._check_feasibility(outside)
    assert any("beneath the run evidence" in problem for problem in problems)


def test_check_only_freshly_validates_and_does_not_rewrite(
    tmp_path: Path,
) -> None:
    _run_root, evidence, feasibility = _fixture(tmp_path)
    admission_path = evidence / "m4-admission.json"
    admission, exit_code = m4_gate.run_gate(
        out=admission_path,
        evidence_dir=evidence / "lanes",
        feasibility_path=feasibility,
        selectors=("authority_lint",),
        python_secondary="/does/not/exist",
    )
    assert exit_code == 0, admission
    before = admission_path.read_bytes()
    retained, check_exit = m4_gate.check_admission(
        admission_path, feasibility_path=feasibility
    )
    assert check_exit == 0
    assert retained["ok"] is True
    assert admission_path.read_bytes() == before

    tampered = json.loads(admission_path.read_text(encoding="utf-8"))
    tampered["feasibility"]["task_count"] = 32
    admission_path.write_text(json.dumps(tampered), encoding="utf-8")
    tampered_before = admission_path.read_bytes()
    _retained, check_exit = m4_gate.check_admission(
        admission_path, feasibility_path=feasibility
    )
    assert check_exit == 1
    assert admission_path.read_bytes() == tampered_before


def test_makefile_requires_and_forwards_explicit_feasibility(tmp_path: Path) -> None:
    omitted = subprocess.run(
        ["make", "m4-gate"],
        cwd=m4_gate.REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert omitted.returncode == 2
    assert "M4_FEASIBILITY" in omitted.stderr

    explicit = tmp_path / "feasibility.json"
    explicit.write_text("{}\n", encoding="utf-8")
    dry_run = subprocess.run(
        ["make", "-n", "m4-gate", f"M4_FEASIBILITY={explicit}"],
        cwd=m4_gate.REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert dry_run.returncode == 0
    assert f'--feasibility "{explicit}"' in dry_run.stdout


def test_programmatic_run_gate_omission_fails_before_lanes(tmp_path: Path) -> None:
    admission, exit_code = m4_gate.run_gate(
        out=tmp_path / "admission.json",
        evidence_dir=tmp_path / "evidence",
        selectors=("authority_lint",),
        python_secondary="/does/not/exist",
    )
    assert exit_code == 1
    assert admission["ok"] is False
    assert admission["lanes"] == {}
    assert admission["feasibility"]["present"] is False
