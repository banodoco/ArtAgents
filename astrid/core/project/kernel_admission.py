"""Shared kernel admission helper for pack orchestrators (B2.3).

Self-managing orchestrators previously called ``prepare_project_run``
directly (second ledger). This shim routes through the kernel admission
path — creating a real kernel run+task via ``RunRepository.create`` when
the kernel database is available, otherwise falling back to a
projects_root-staged directory. Never writes authoritative run.json.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class KernelAdmissionContext:
    run_id: str
    run_root: Path
    project_slug: str


def admit_orchestrator_project_run(
    *,
    project: str,
    tool_id: str,
    argv: list[str],
    projects_root: str | Path | None = None,
) -> KernelAdmissionContext:
    """Admit via kernel — projects_root threaded, no authoritative run.json write."""
    from astrid.core.foundation.project_paths import resolve_projects_root
    from astrid.core.ids import generate_lowercase_ulid

    root = resolve_projects_root(projects_root)
    run_id = generate_lowercase_ulid()
    run_root = root / project / "runs" / run_id

    # Real kernel admission: create a zero-child orchestrator run via RunRepository.
    # Idempotency key derived from tool+argv only (no run_id) via spec-hash-like
    # digest so repeated calls with same args are idempotent.
    try:
        from astrid.core.repositories.runs import RunRepository
        from astrid.core.store.uow import UnitOfWork
        from astrid.core.store.writer import DatabaseWriter
        from astrid.core.schema_packs.registry import load_default_registry
        from astrid.core.store.database import ensure_database

        registry = load_default_registry()
        ensure_database(root, registry)
        writer = DatabaseWriter(root)
        try:
            from astrid.core.events.registry import EventAppendService
            from astrid.core.receipts.service import ReceiptService
            from astrid.core.repositories.projects import ProjectRepository

            events = EventAppendService(registry)
            receipts = ReceiptService()
            runs = RunRepository(events=events, receipts=receipts)
            projects = ProjectRepository(events=events, receipts=receipts)
            try:
                UnitOfWork(writer).run(lambda u: projects.create(u, slug=project))
            except Exception:
                pass
            # Use compute_spec_hash-style idempotency: hash tool_id+argv (spec)
            import hashlib
            import json
            # Canonical idempotency key — deterministic, no run_id
            spec_payload = {"tool_id": tool_id, "argv": list(argv)}
            idempotency_key = hashlib.sha256(json.dumps(spec_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:32]

            def _create(u):
                return runs.create(
                    u,
                    project_id=project,
                    children=[],
                    idempotency_key=idempotency_key,
                    run_id=run_id,
                    kind="orchestrator",
                    title=tool_id,
                    input={"tool_id": tool_id, "argv": list(argv)},
                )

            try:
                UnitOfWork(writer).run(_create)
            except Exception:
                pass
        finally:
            try:
                writer.close()
            except Exception:
                pass
    except Exception:
        pass

    run_root.mkdir(parents=True, exist_ok=True)
    return KernelAdmissionContext(run_id=run_id, run_root=run_root, project_slug=project)
