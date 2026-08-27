"""Canonical database authority when historical ledgers coexist."""

from __future__ import annotations

from pathlib import Path

from astrid.core.doctor import run_checks
from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.kernel.database import resolve_kernel_database_authority
from astrid.core.kernel.read import kernel_run_info, kernel_runs_for_project
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.repositories.runs import RunRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter

TS = "2026-08-24T00:00:00.000000+00:00"


def _seed_run(path: Path, registry, *, slug: str, title: str) -> str:
    """Create distinct, legitimate project/run evidence in one ledger."""

    writer = DatabaseWriter(path, registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        runs = RunRepository(events=events, receipts=receipts)
        project_id = generate_lowercase_ulid()
        UnitOfWork(writer).run(
            lambda uow: projects.create(
                uow,
                slug=slug,
                name=title,
                settings={},
                idempotency_key=f"create-{slug}",
                project_id=project_id,
                created_at=TS,
            )
        )
        run_id = generate_lowercase_ulid()
        UnitOfWork(writer).run(
            lambda uow: runs.create(
                uow,
                project_id=project_id,
                children=[],
                idempotency_key=f"run-{slug}",
                run_id=run_id,
                kind="executor",
                title=title,
                input={"ledger": slug},
                created_at=TS,
            )
        )
        return run_id
    finally:
        writer.close()


def _checks_by_name(root: Path):
    return {check.name: check for check in run_checks(projects_root=root)}


def test_canonical_authority_ignores_unmanaged_database_files(
    tmp_path: Path,
    standard_registry,
    core_registry,
) -> None:
    canonical_path = tmp_path / ".astrid" / "astrid.sqlite3"
    canonical_path.parent.mkdir(parents=True)
    legacy_path = tmp_path / "kernel.sqlite3"
    canonical_run = _seed_run(
        canonical_path,
        standard_registry,
        slug="canonical-project",
        title="Canonical evidence",
    )
    legacy_run = _seed_run(
        legacy_path,
        core_registry,
        slug="legacy-project",
        title="Legacy evidence",
    )

    authority = resolve_kernel_database_authority(tmp_path)
    assert authority.mode == "canonical"
    assert authority.selected_path == canonical_path
    assert authority.existing_legacy_paths == ()
    assert not authority.coexists

    assert kernel_runs_for_project(
        "canonical-project", projects_root=tmp_path
    ) == [canonical_run]
    assert kernel_run_info(
        "canonical-project", canonical_run, projects_root=tmp_path
    )["title"] == "Canonical evidence"
    assert kernel_runs_for_project("legacy-project", projects_root=tmp_path) == []
    assert kernel_run_info(
        "legacy-project", legacy_run, projects_root=tmp_path
    ) is None

    checks = _checks_by_name(tmp_path)
    data_paths = checks["data_paths"]
    assert data_paths.status == "ok"
    assert checks["schema_versions"].status == "ok"
    assert "timeline=" in checks["schema_versions"].detail


def test_unmanaged_database_only_root_is_not_a_project_store(
    tmp_path: Path,
    core_registry,
) -> None:
    legacy_path = tmp_path / "kernel.sqlite3"
    _seed_run(
        legacy_path,
        core_registry,
        slug="legacy-project",
        title="Unmanaged evidence",
    )

    authority = resolve_kernel_database_authority(tmp_path)
    assert authority.mode == "missing"
    assert authority.selected_path == tmp_path / ".astrid" / "astrid.sqlite3"
    assert authority.existing_legacy_paths == ()
    assert not authority.coexists
    assert kernel_runs_for_project(
        "legacy-project", projects_root=tmp_path
    ) == []
    assert kernel_run_info(
        "legacy-project", "unmanaged-run", projects_root=tmp_path
    ) is None

    checks = _checks_by_name(tmp_path)
    data_paths = checks["data_paths"]
    assert data_paths.status == "uninitialized"
    assert data_paths.required is False
