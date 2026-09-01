"""Focused contract tests for the executable Stage 1 evidence capture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.reshape import stage1_evidence_capture as capture
from scripts.reshape.stage1_acceptance import CHECK_CATEGORY, RECEIPT_SCHEMA, sha256_bytes


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _b12_receipt(root: Path) -> tuple[Path, bytes]:
    artifact = _write(root / "migration" / "trace.log", "real B12 operator trace\n")
    payload = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": "b12-real-20260901",
        "category": "migration",
        "status": "pass",
        "observed_at": "2026-09-01T12:00:00Z",
        "command": ["astrid-live-migrate", "live-migrate"],
        "observations": {"evidence_mode": "live", "operator": "b12"},
        "checks": [
            {
                "id": "10.1.migration-backup-activation-rollback",
                "status": "pass",
                "observations": {"result": "observed"},
                "artifacts": [
                    {
                        "path": artifact.name,
                        "sha256": sha256_bytes(artifact.read_bytes()),
                        "kind": "b12-operator-trace",
                    }
                ],
            },
            {
                "id": "13.05.migration-backup-activation-rollback",
                "status": "pass",
                "observations": {"result": "observed"},
                "artifacts": [
                    {
                        "path": artifact.name,
                        "sha256": sha256_bytes(artifact.read_bytes()),
                        "kind": "b12-operator-trace",
                    }
                ],
            },
        ],
    }
    receipt = root / "migration" / "receipt.json"
    raw = json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n"
    receipt.write_bytes(raw)
    return receipt, raw


def test_capture_imports_b12_receipts_byte_for_byte(tmp_path: Path) -> None:
    source = tmp_path / "b12-source"
    receipt, raw = _b12_receipt(source)

    report, exit_code = capture.capture_evidence(
        tmp_path / "evidence",
        repo_root=Path(capture.REPO_ROOT),
        categories=(),
        run_commands=False,
        b12_evidence_dir=source,
    )

    assert exit_code == 1  # Other required categories are intentionally absent.
    imported = tmp_path / "evidence" / "b12" / "migration" / receipt.name
    assert imported.read_bytes() == raw
    assert report["status"] == "blocked"


def test_skipped_command_writes_failed_receipt_and_retains_junit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skipped = _write(
        tmp_path / "skip_test.py",
        "import pytest\n@pytest.mark.skip(reason='contract test')\ndef test_skipped():\n    assert False\n",
    )
    monkeypatch.setattr(
        capture,
        "GATE_SPECS",
        (capture.GateSpec("docs", (str(skipped),)),),
    )

    capture.capture_evidence(
        tmp_path / "evidence",
        repo_root=Path(capture.REPO_ROOT),
        categories=("docs",),
        run_commands=True,
    )
    receipt = json.loads(
        (tmp_path / "evidence" / "receipts" / "docs.json").read_text()
    )
    assert receipt["status"] == "fail"
    assert receipt["observations"]["skipped"] == 1
    assert (tmp_path / "evidence" / "artifacts" / "docs" / "junit.xml").is_file()
    assert (tmp_path / "evidence" / "artifacts" / "docs" / "combined.log").is_file()


def test_capture_gate_table_covers_every_non_b12_category() -> None:
    categories = {spec.category for spec in capture.GATE_SPECS}
    assert set(capture.CAPTURE_CATEGORIES) - {"source_identity", "dependency_locks", "source_manifests"} <= categories
    assert capture.MIGRATION_CATEGORIES.isdisjoint(categories)
    assert set(capture.MIGRATION_CATEGORIES) == {
        category for category in capture.REQUIRED_CATEGORIES if category not in capture.CAPTURE_CATEGORIES
    }
    assert set(CHECK_CATEGORY.values()) == set(capture.REQUIRED_CATEGORIES)
