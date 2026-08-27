"""Shared kernel admission helper for pack orchestrators (B2.3).

Self-managing orchestrators previously called ``prepare_project_run``
directly (second ledger). This shim routes through the kernel admission
path — creating a real kernel run+task via ``RunRepository.create`` when
the kernel database is available, otherwise falling back to a
projects_root-staged directory. Never writes authoritative run.json.

Admission is create-only; driving the hard-chain to terminal status is
the caller's responsibility (harness/orchestrator).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.receipts.service import ReceiptMismatchError


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
    """Admit via kernel — projects_root threaded, no authoritative run.json write.

    Create-only: admits 1 run + 1 task via ``RunRepository`` (single-task
    generic fan-out; N only if capability manifest declares children).
    Returns the reconciled kernel ``run_id`` on idempotent replay (no orphan
    ULID). Raises ``ReceiptMismatchError`` on idempotency-key reuse with a
    different request hash; does not swallow it. Drive (claim/start/complete)
    is the caller's responsibility.
    """
    from astrid.application import compose_standard_application
    from astrid.core.foundation.project_paths import resolve_projects_root
    from astrid.core.ids import generate_lowercase_ulid
    from astrid.core.project.run import ProjectRunError
    from astrid.core.repositories.projects import (
        ProjectNotFoundError,
        ProjectSlugConflictError,
    )
    from astrid.core.repositories.tasks import compute_spec_hash
    from astrid.core.store.uow import UnitOfWork

    root = resolve_projects_root(projects_root)

    # Idempotency key derived from tool+argv only (no run_id) so replay is stable.
    spec_payload: dict[str, Any] = {"tool_id": tool_id, "argv": list(argv)}
    application = None
    try:
        idempotency_key = compute_spec_hash(spec_payload, [])
        application = compose_standard_application(root)
        writer = application.writer
        runs = application.runs
        projects = application.projects

        try:
            project_id = projects.resolve(writer, project)
        except ProjectNotFoundError:
            generated_id = generate_lowercase_ulid()
            try:
                created = UnitOfWork(writer).run(
                    lambda u: projects.create(
                        u,
                        slug=project,
                        name=project,
                        settings={},
                        idempotency_key=f"proj:{project}",
                        project_id=generated_id,
                    )
                )
                project_id = created.id
            except ProjectSlugConflictError:
                project_id = projects.resolve(writer, project)

        deterministic_run_id = hashlib.sha256(
            f"run:{idempotency_key}".encode()
        ).hexdigest()[:26]
        deterministic_task_id = hashlib.sha256(
            f"task:{idempotency_key}:0".encode()
        ).hexdigest()[:26]
        children: list[dict[str, Any]] = [
            {
                "capability": tool_id,
                "spec": {
                    "tool_id": tool_id,
                    "argv": list(argv),
                    "project": project,
                },
                "input_manifest": [],
                "task_id": deterministic_task_id,
                "dependencies": [],
            }
        ]
        fanout = UnitOfWork(writer).run(
            lambda u: runs.create(
                u,
                project_id=project_id,
                children=children,
                idempotency_key=idempotency_key,
                kind="orchestrator",
                title=tool_id,
                input={"tool_id": tool_id, "argv": list(argv)},
                run_id=deterministic_run_id,
            )
        )
        run_id = str(fanout.run_id)
        run_root = root / project / "runs" / run_id
        run_root.mkdir(parents=True, exist_ok=True)
        return KernelAdmissionContext(run_id=run_id, run_root=run_root, project_slug=project)
    except (ProjectRunError, ReceiptMismatchError):
        raise
    except Exception as exc:  # noqa: BLE001 - translate composition boundary
        raise ProjectRunError(
            f"kernel run unavailable for project {project!r}: {exc}"
        ) from exc
    finally:
        if application is not None:
            application.close()
