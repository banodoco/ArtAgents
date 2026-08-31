"""Regression coverage for the final Astrid authority cutover.

The runtime owns durable events, receipts, evidence, and schema state. These
tests make the negative boundary executable so a deleted local authority
cannot quietly return through an import or a supposedly optional helper.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module_name",
    (
        "astrid.core.events.stream",
        "astrid.core.audit.transport",
        "astrid.core.audit.graph",
        "astrid.core.audit.report",
        "astrid.core.audit.cli",
        "astrid.core.migrations.runner",
        "astrid.core.session.paths",
    ),
)
def test_retired_local_authority_modules_are_not_importable(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_runtime_event_dto_does_not_depend_on_filesystem_stream() -> None:
    from astrid.sdk.dto import EventStreamRecord

    assert EventStreamRecord.__module__ == "astrid.sdk.dto"
    assert not hasattr(importlib.import_module("astrid.core.events"), "read_events")
    assert not hasattr(importlib.import_module("astrid.core.events"), "append_event_locked")


def test_pack_audit_is_ephemeral_and_never_creates_ledger(tmp_path: Path) -> None:
    from astrid.core.audit import AuditContext

    run_dir = tmp_path / "run"
    artifact = run_dir / "artifact.txt"
    artifact.parent.mkdir()
    artifact.write_text("runtime-owned provenance input", encoding="utf-8")

    context = AuditContext.for_run(run_dir)
    asset_id = context.register_asset(kind="source", path=artifact, label="Source")

    assert asset_id
    assert context.records
    assert not (run_dir / "events.jsonl").exists()
    assert not (run_dir / "audit" / "ledger.jsonl").exists()
    assert not hasattr(context, "ledger_path")


def test_core_source_has_no_local_event_or_sqlite_authority() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not (root / "astrid/core/migrations").exists()
    assert "events.jsonl" not in (root / "astrid/core/events/__init__.py").read_text()
    assert "sqlite3" not in (root / "astrid/core/audit/context.py").read_text()
