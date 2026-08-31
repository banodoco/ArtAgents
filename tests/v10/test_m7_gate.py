"""Focused tests for the m7 finalizer feasibility admission boundary."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from scripts.reshape import m7_gate


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, tuple[Path, ...]]:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    plan_dir = root / ".megaplan" / "plans" / m7_gate.PLAN_NAME
    plan_dir.mkdir(parents=True)
    plan = plan_dir / "plan_v2.md"
    plan.write_text("fixture plan\n", encoding="utf-8")
    plan_hash = m7_gate._sha256_file(plan)
    meta = plan_dir / "plan_v2.meta.json"
    meta.write_text(json.dumps({"version": 2, "hash": plan_hash}), encoding="utf-8")
    extras = []
    for name in ("plan_v1.meta.json", "state.json", "finalize.json"):
        path = plan_dir / name
        path.write_text("{}\n", encoding="utf-8")
        extras.append(path)
    return root, plan, meta, tuple(extras)


def _admit(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    root, plan, meta, extras = _fixture(tmp_path)
    # The production identity is intentionally fixed.  Replace the fixture's
    # bytes with the approved plan while retaining a hermetic artifact dir.
    source = m7_gate.DEFAULT_PLAN.read_bytes()
    plan.write_bytes(source)
    meta.write_text(json.dumps({"version": 2, "hash": m7_gate.PLAN_HASH}), encoding="utf-8")
    return m7_gate.run_admission(
        repo_root=root,
        plan_path=plan,
        plan_meta_path=meta,
        artifact_dir=tmp_path / "artifacts" / "m7",
        admission_path=tmp_path / "artifacts" / "m7" / "finalizer-admission.json",
        required_inputs=(plan, meta, *extras),
        finalizer_command=("python3", "-c", "pass"),
        **kwargs,
    )


def test_admission_records_hash_and_removes_only_atomic_probe(tmp_path: Path) -> None:
    record = _admit(tmp_path)
    assert record["admitted"] is True
    assert record["content_hash"] == record["record_hash"]
    assert record["checks"]["atomic_temporary_replacement"]["removed"] is True
    artifact_dir = tmp_path / "artifacts" / "m7"
    assert list(artifact_dir.glob(".m7-atomic-probe-*")) == []
    retained = json.loads((artifact_dir / "finalizer-admission.json").read_text())
    assert m7_gate.validate_admission(
        retained,
        plan_path=tmp_path / "repo" / ".megaplan" / "plans" / m7_gate.PLAN_NAME / "plan_v2.md",
        expected_command=("python3", "-c", "pass"),
    ) == []


def test_missing_required_input_fails_closed(tmp_path: Path) -> None:
    root, plan, meta, extras = _fixture(tmp_path)
    plan.write_bytes(m7_gate.DEFAULT_PLAN.read_bytes())
    meta.write_text(json.dumps({"version": 2, "hash": m7_gate.PLAN_HASH}), encoding="utf-8")
    extras[1].unlink()
    record = m7_gate.run_admission(
        repo_root=root,
        plan_path=plan,
        plan_meta_path=meta,
        artifact_dir=tmp_path / "artifacts" / "m7",
        admission_path=tmp_path / "artifacts" / "m7" / "admission.json",
        required_inputs=(plan, meta, *extras),
        finalizer_command=("python3", "-c", "pass"),
    )
    assert record["admitted"] is False
    assert any("required input unavailable" in error for error in record["errors"])


def test_immutable_collision_is_rejected_without_overwriting_ledger(tmp_path: Path) -> None:
    root, plan, meta, extras = _fixture(tmp_path)
    plan.write_bytes(m7_gate.DEFAULT_PLAN.read_bytes())
    meta.write_text(json.dumps({"version": 2, "hash": m7_gate.PLAN_HASH}), encoding="utf-8")
    ledger = tmp_path / "immutable-ledger.json"
    ledger.write_text("keep\n", encoding="utf-8")
    record = m7_gate.run_admission(
        repo_root=root,
        plan_path=plan,
        plan_meta_path=meta,
        artifact_dir=tmp_path / "artifacts" / "m7",
        admission_path=ledger,
        required_inputs=(plan, meta, *extras),
        finalizer_command=("python3", "-c", "pass"),
        immutable_paths=(ledger,),
    )
    assert record["admitted"] is False
    assert ledger.read_text() == "keep\n"
    assert any("immutable-ledger collision" in error for error in record["errors"])


def test_resume_rejects_stale_conflicting_and_plan_mismatched_records(tmp_path: Path) -> None:
    record = _admit(tmp_path)
    path = tmp_path / "artifacts" / "m7" / "finalizer-admission.json"
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)
    record["timestamp"]["finished_at"] = old.isoformat().replace("+00:00", "Z")
    record["content_hash"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(record), encoding="utf-8")
    loaded, errors = m7_gate.check_admission(path, plan_path=tmp_path / "repo" / ".megaplan" / "plans" / m7_gate.PLAN_NAME / "plan_v2.md")
    assert loaded
    assert any("content hash" in error for error in errors)
    assert any("stale" in error for error in errors)

    record = _admit(tmp_path / "second")
    record["plan"]["actual_hash"] = "sha256:" + "1" * 64
    assert any("plan hash" in error for error in m7_gate.validate_admission(record, plan_path=(tmp_path / "second" / "repo" / ".megaplan" / "plans" / m7_gate.PLAN_NAME / "plan_v2.md")))


def _green_selector(item: int, selectors: tuple[str, ...], _root: Path) -> dict[str, object]:
    return {
        "item": item,
        "selectors": list(selectors),
        "command": f"timeout 120 python3 -m pytest {' '.join(selectors)} -q",
        "status": "pass",
        "stage": "executed-green",
        "counts": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
        "log": "1 passed\n",
        "log_sha256": "sha256:" + "a" * 64,
        "junit_sha256": "sha256:" + "b" * 64,
    }


def test_gate_publishes_complete_matrix_with_honest_deferred_items(tmp_path: Path) -> None:
    record = _admit(tmp_path)
    admission_path = tmp_path / "artifacts" / "m7" / "finalizer-admission.json"
    defects_path = tmp_path / "artifacts" / "m7" / "defects.md"
    defects_path.write_text("# m7 defects ledger\n\nNo open correctness defects.\n", encoding="utf-8")
    acceptance_path = tmp_path / "artifacts" / "m7" / "acceptance.json"
    selectors = {item: ("tests/v10/test_m7_gate.py",) for item in range(1, 11)}

    published, exit_code = m7_gate.run_gate(
        repo_root=m7_gate.REPO_ROOT,
        admission_path=admission_path,
        acceptance_path=acceptance_path,
        defects_path=defects_path,
        plan_path=tmp_path / "repo" / ".megaplan" / "plans" / m7_gate.PLAN_NAME / "plan_v2.md",
        selectors=selectors,
        finalizer_command=("python3", "-c", "pass"),
        runner=_green_selector,
    )

    assert exit_code == 0
    assert published["published"] is True
    accepted = json.loads(acceptance_path.read_text(encoding="utf-8"))
    assert accepted["status"] == "pass"
    assert set(accepted["ga_items"]) == {str(item) for item in range(1, 13)}
    assert all(accepted["ga_items"][str(item)]["status"] == "pass" for item in range(1, 11))
    assert accepted["ga_items"]["11"]["label"] == "provisional"
    assert accepted["ga_items"]["12"]["label"] == "retained"
    assert accepted["finalizer_admission"]["hash"] == record["content_hash"]
    assert all(
        gate["id"] != "external-reigh-editor"
        for gate in accepted["unresolved_external_manual_gates"]
    )
    assert "M7 gate disposition" in defects_path.read_text(encoding="utf-8")


def test_gate_does_not_publish_after_admission_changes_before_finalization(tmp_path: Path, monkeypatch) -> None:
    _admit(tmp_path)
    admission_path = tmp_path / "artifacts" / "m7" / "finalizer-admission.json"
    defects_path = tmp_path / "artifacts" / "m7" / "defects.md"
    defects_path.write_text("# m7 defects ledger\n", encoding="utf-8")
    acceptance_path = tmp_path / "artifacts" / "m7" / "acceptance.json"
    original = m7_gate.check_admission
    calls = 0

    def change_on_second_check(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        loaded, errors = original(*args, **kwargs)
        if calls == 2:
            loaded["content_hash"] = "sha256:" + "0" * 64
        return loaded, errors

    monkeypatch.setattr(m7_gate, "check_admission", change_on_second_check)
    selectors = {item: ("tests/v10/test_m7_gate.py",) for item in range(1, 11)}
    published, exit_code = m7_gate.run_gate(
        repo_root=m7_gate.REPO_ROOT,
        admission_path=admission_path,
        acceptance_path=acceptance_path,
        defects_path=defects_path,
        plan_path=tmp_path / "repo" / ".megaplan" / "plans" / m7_gate.PLAN_NAME / "plan_v2.md",
        selectors=selectors,
        finalizer_command=("python3", "-c", "pass"),
        runner=_green_selector,
    )

    assert calls == 2
    assert exit_code == 1
    assert published["published"] is False
    assert not acceptance_path.exists()
