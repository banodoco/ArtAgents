from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path

import pytest

from astrid.audit import AuditContext
from astrid.audit.graph import build_graph, load_ledger
from astrid.audit.report import render_html


def _load_migration_module():
    path = Path("scripts/migrations/sprint-3/migrate_audit_ledgers.py").resolve()
    spec = importlib.util.spec_from_file_location("_astrid_migrate_audit_ledgers_test", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_audit_append_writes_v2_hash_chain(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    ctx = AuditContext.for_run(run_dir)

    ctx.register_node(stage="prepare", label="Prepare")
    ctx.register_node(stage="render", label="Render")

    records = [
        json.loads(line)
        for line in (run_dir / "audit" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["schema_version"] for record in records] == [2, 2]
    assert records[0]["prev_hash"] is None
    assert isinstance(records[0]["hash"], str)
    assert records[1]["prev_hash"] == records[0]["hash"]
    assert isinstance(records[1]["hash"], str)


def test_verify_audit_ledger_detects_corruption(tmp_path: Path) -> None:
    from astrid.audit.graph import verify_audit_ledger

    run_dir = tmp_path / "run"
    ctx = AuditContext.for_run(run_dir)
    ctx.register_node(stage="prepare", label="Prepare")
    ledger_path = run_dir / "audit" / "ledger.jsonl"
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["stage"] = "tampered"
    ledger_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    ok, line_number, reason = verify_audit_ledger(run_dir)

    assert ok is False
    assert line_number == 1
    assert "hash" in reason.lower()


def test_legacy_v1_and_v2_ledgers_both_render(tmp_path: Path) -> None:
    legacy_run = tmp_path / "legacy"
    legacy_ledger = legacy_run / "audit" / "ledger.jsonl"
    legacy_ledger.parent.mkdir(parents=True)
    legacy_ledger.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "event": "node.created",
                "node_id": "legacy-node",
                "stage": "legacy",
                "kind": "step",
                "label": "Legacy",
                "parents": [],
                "outputs": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    v2_run = tmp_path / "v2"
    AuditContext.for_run(v2_run).register_node(stage="v2", label="V2")

    for run_dir in (legacy_run, v2_run):
        events = load_ledger(run_dir)
        graph = build_graph(events)
        html = render_html(run_dir, graph)
        assert graph["nodes"]
        assert "Audit" in html


def test_audit_cli_renders_legacy_and_v2_ledgers(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from astrid.audit import cli as audit_cli

    legacy_run = tmp_path / "legacy"
    legacy_ledger = legacy_run / "audit" / "ledger.jsonl"
    legacy_ledger.parent.mkdir(parents=True)
    legacy_ledger.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "event": "node.created",
                "node_id": "legacy-node",
                "stage": "legacy",
                "kind": "step",
                "label": "Legacy",
                "parents": [],
                "outputs": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    v2_run = tmp_path / "v2"
    AuditContext.for_run(v2_run).register_node(stage="v2", label="V2")

    for run_dir in (legacy_run, v2_run):
        assert audit_cli.main(["--run", str(run_dir), "--json", "--verify"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["nodes"]


def test_audit_cli_verifies_by_default_and_no_verify_is_explicit_escape_hatch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from astrid.audit import cli as audit_cli

    run_dir = tmp_path / "run"
    ctx = AuditContext.for_run(run_dir)
    ctx.register_node(stage="prepare", label="Prepare")
    ledger_path = run_dir / "audit" / "ledger.jsonl"
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["stage"] = "tampered"
    ledger_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    assert audit_cli.main(["--run", str(run_dir), "--json"]) == 1
    assert "verification failed" in capsys.readouterr().out

    assert audit_cli.main(["--run", str(run_dir), "--json", "--no-verify"]) == 0
    assert json.loads(capsys.readouterr().out)["nodes"]


def test_audit_report_write_report_verifies_by_default(tmp_path: Path) -> None:
    from astrid.audit.report import write_report

    run_dir = tmp_path / "run"
    ctx = AuditContext.for_run(run_dir)
    ctx.register_node(stage="prepare", label="Prepare")
    ledger_path = run_dir / "audit" / "ledger.jsonl"
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["stage"] = "tampered"
    ledger_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="audit ledger verification failed"):
        write_report(run_dir)

    report = write_report(run_dir, verify=False)
    assert report.is_file()


def test_verify_audit_ledger_detects_truncation(tmp_path: Path) -> None:
    from astrid.audit.graph import verify_audit_ledger

    run_dir = tmp_path / "run"
    ctx = AuditContext.for_run(run_dir)
    ctx.register_node(stage="prepare", label="Prepare")
    ledger_path = run_dir / "audit" / "ledger.jsonl"
    original = ledger_path.read_text(encoding="utf-8")
    ledger_path.write_text(original[: len(original) // 2], encoding="utf-8")

    ok, line_number, reason = verify_audit_ledger(run_dir)

    assert ok is False
    assert line_number == 1
    assert "truncated" in reason.lower() or "json" in reason.lower()


def test_audit_ledger_migration_dry_run_apply_and_idempotence(tmp_path: Path) -> None:
    migration = _load_migration_module()
    projects_root = tmp_path / "projects"
    ledger_path = projects_root / "demo" / "runs" / "run-1" / "audit" / "ledger.jsonl"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "event": "node.created",
                "node_id": "legacy-node",
                "stage": "legacy",
                "kind": "step",
                "label": "Legacy",
                "parents": [],
                "outputs": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    original = ledger_path.read_text(encoding="utf-8")

    assert migration.main(["--projects-root", str(projects_root), "--dry-run"]) == 0
    assert ledger_path.read_text(encoding="utf-8") == original
    assert not ledger_path.with_name("ledger.jsonl" + migration.BACKUP_SUFFIX).exists()

    assert migration.main(["--projects-root", str(projects_root), "--apply"]) == 0
    backup_path = ledger_path.with_name("ledger.jsonl" + migration.BACKUP_SUFFIX)
    assert backup_path.read_text(encoding="utf-8") == original
    records = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert records[0]["schema_version"] == 2
    assert records[0]["prev_hash"] is None
    assert isinstance(records[0]["hash"], str)

    applied_once = ledger_path.read_text(encoding="utf-8")
    assert migration.main(["--projects-root", str(projects_root), "--apply"]) == 0
    assert ledger_path.read_text(encoding="utf-8") == applied_once
    assert backup_path.read_text(encoding="utf-8") == original


def test_audit_ledger_migration_reports_corruption_without_backup(tmp_path: Path) -> None:
    migration = _load_migration_module()
    projects_root = tmp_path / "projects"
    ledger_path = projects_root / "demo" / "runs" / "run-1" / "audit" / "ledger.jsonl"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text('{"schema_version":1', encoding="utf-8")

    assert migration.main(["--projects-root", str(projects_root), "--apply"]) == 1
    assert ledger_path.read_text(encoding="utf-8") == '{"schema_version":1'
    assert not ledger_path.with_name("ledger.jsonl" + migration.BACKUP_SUFFIX).exists()
