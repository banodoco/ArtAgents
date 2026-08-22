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

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.receipts.service import ReceiptMismatchError  # noqa: F401 — needed for outer except


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
    from astrid.core.foundation.project_paths import resolve_projects_root
    from astrid.core.ids import generate_lowercase_ulid

    root = resolve_projects_root(projects_root)

    # Idempotency key derived from tool+argv only (no run_id) so replay is stable.
    # Compute early so we can return reconciled run_id without allocating orphan.
    spec_payload: dict[str, Any] = {"tool_id": tool_id, "argv": list(argv)}
    reconciled_run_id: str | None = None
    try:
        from astrid.core.events.registry import core_only_registry
        from astrid.core.events.service import EventAppendService
        from astrid.core.receipts.service import ReceiptService
        from astrid.core.repositories.projects import ProjectRepository
        from astrid.core.repositories.runs import RunRepository
        from astrid.core.repositories.tasks import compute_spec_hash
        from astrid.core.store.uow import UnitOfWork
        from astrid.core.store.writer import DatabaseWriter

        idempotency_key = compute_spec_hash(spec_payload, [])

        registry = core_only_registry()
        db_path = Path(root) / "kernel.sqlite3"
        writer = DatabaseWriter(db_path, registry)
        try:
            events = EventAppendService(registry)  # type: ignore[arg-type]
            receipts = ReceiptService()
            runs = RunRepository(events=events, receipts=receipts)  # type: ignore[arg-type]
            projects = ProjectRepository(events=events, receipts=receipts)  # type: ignore[arg-type]
            try:
                UnitOfWork(writer).run(
                    lambda u: projects.create(
                        u,
                        slug=project,
                        name=project,
                        settings={},
                        idempotency_key=f"proj:{project}",
                        project_id=project,
                    )
                )
            except ReceiptMismatchError:
                raise
            except Exception:
                pass

            _steps = ["run"]
            import hashlib
            # Deterministic ids for idempotent replay (no orphan mismatch):
            # run_id and child task_id derived from idempotency_key.
            deterministic_run_id = hashlib.sha256(f"run:{idempotency_key}".encode()).hexdigest()[:26]
            deterministic_task_id = hashlib.sha256(f"task:{idempotency_key}:0".encode()).hexdigest()[:26]
            _children: list[dict[str, Any]] = [
                {
                    "capability": tool_id,
                    "spec": {"tool_id": tool_id, "argv": list(argv), "project": project},
                    "input_manifest": [],
                    "task_id": deterministic_task_id,
                    "dependencies": [],
                }
            ]

            def _create(u):
                return runs.create(
                    u,
                    project_id=project,
                    children=_children,
                    idempotency_key=idempotency_key,
                    kind="orchestrator",
                    title=tool_id,
                    input={"tool_id": tool_id, "argv": list(argv)},
                    run_id=deterministic_run_id,
                )

            # ReceiptMismatch must not be swallowed — it indicates key reuse with different hash.
            # On identical replay, runs.create returns stored fan-out via receipt check (no exception).
            fanout = UnitOfWork(writer).run(_create)
            reconciled_run_id = str(fanout.run_id)
        finally:
            try:
                writer.close()
            except Exception:
                pass
    except ReceiptMismatchError:
        raise
    except Exception:
        # Kernel unavailable or other non-mismatch error — fall back to orphan fallback below.
        pass

    if reconciled_run_id is not None:
        run_id = reconciled_run_id
        run_root = root / project / "runs" / run_id
        run_root.mkdir(parents=True, exist_ok=True)
        return KernelAdmissionContext(run_id=run_id, run_root=run_root, project_slug=project)

    # Kernel unavailable with no reconciled run — fail closed (no filesystem ghost).
    # Every invocation is a kernel run+task; without a kernel run there is
    # no derived projection to write.
    from astrid.core.project.run import ProjectRunError

    raise ProjectRunError(
        f"kernel run unavailable for project {project!r}: database not reachable or project has no kernel row"
    )
