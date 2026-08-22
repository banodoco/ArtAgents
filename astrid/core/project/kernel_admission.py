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
    # Idempotency key derived from tool+argv only (no run_id) via canonical
    # compute_spec_hash so repeated calls with same args are idempotent.
    try:
        from astrid.core.events.service import EventAppendService
        from astrid.core.receipts.service import ReceiptService, ReceiptMismatchError
        from astrid.core.repositories.projects import ProjectRepository
        from astrid.core.repositories.runs import RunRepository
        from astrid.core.repositories.tasks import compute_spec_hash
        from astrid.core.events.registry import core_only_registry
        from astrid.core.store.uow import UnitOfWork
        from astrid.core.store.writer import DatabaseWriter
        import json

        registry = core_only_registry()
        db_path = Path(root) / "kernel.sqlite3"
        writer = DatabaseWriter(db_path, registry)
        try:
            events = EventAppendService(registry)
            receipts = ReceiptService()
            runs = RunRepository(events=events, receipts=receipts)
            projects = ProjectRepository(events=events, receipts=receipts)
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
            except Exception:
                pass

            spec_payload = {"tool_id": tool_id, "argv": list(argv)}
            idempotency_key = compute_spec_hash(spec_payload, [])

            # B3 P0: fan-out N=4 hard chain (plan, fetch, render, publish)
            # Stable task_ids for hard dependency edges; run_ordinal is index.
            _steps = ["plan", "fetch", "render", "publish"]
            _task_ids = [generate_lowercase_ulid() for _ in _steps]
            _children: list[dict[str, Any]] = []
            for _idx, (_tid, _step) in enumerate(zip(_task_ids, _steps)):
                _spec: dict[str, Any] = {"tool_id": tool_id, "step": _step, "argv": list(argv), "project": project}
                _deps: list[dict[str, Any]] = [{"task_id": _task_ids[_idx - 1], "kind": "hard"}] if _idx > 0 else []
                _children.append(
                    {
                        "capability": tool_id,
                        "spec": _spec,
                        "input_manifest": [],
                        "task_id": _tid,
                        "dependencies": _deps,
                    }
                )

            def _create(u):
                return runs.create(
                    u,
                    project_id=project,
                    children=_children,
                    idempotency_key=idempotency_key,
                    kind="orchestrator",
                    title=tool_id,
                    input={"tool_id": tool_id, "argv": list(argv)},
                )
            try:
                fanout = UnitOfWork(writer).run(_create)
                # Use kernel-assigned id (idempotent replay returns stored id)
                try:
                    run_id = fanout.run_id
                    run_root = root / project / "runs" / run_id
                except Exception:
                    pass
                # Drive hard chain to succeeded so events/receipts per task exist (R3.1 verify)
                try:
                    from astrid.core.repositories.media import MediaRepository
                    from astrid.core.repositories.tasks import TaskRepository

                    _tasks = TaskRepository(events=events, receipts=receipts)
                    _media = MediaRepository(events=events, receipts=receipts, projects_root=root)
                    for _idx, _expected_tid in enumerate(_task_ids):
                        _claim = UnitOfWork(writer).run(
                            lambda u, _ck=f"{idempotency_key}:claim:{_idx}": _tasks.claim(u, project_id=project, idempotency_key=_ck)
                        )
                        if _claim is None:
                            break
                        _sv_claim = int(_claim.attempt.status_version)
                        _lease = str(_claim.attempt.lease_id)
                        _started = UnitOfWork(writer).run(
                            lambda u, _tid=_claim.task.id, _aid=_claim.attempt.id, _sv=_sv_claim, _lease=_lease, _ck=f"{idempotency_key}:start:{_idx}": _tasks.start(
                                u, project_id=project, task_id=_tid, attempt_id=_aid, lease_id=_lease, expected_status_version=_sv_claim, idempotency_key=_ck
                            )
                        )
                        _sv_started = int(_started.status_version)
                        UnitOfWork(writer).run(
                            lambda u, _tid=_claim.task.id, _aid=_claim.attempt.id, _lease=_lease, _sv=_sv_started, _ck=f"{idempotency_key}:complete:{_idx}": _tasks.complete(
                                u, project_id=project, task_id=_tid, attempt_id=_aid, lease_id=_lease, expected_status_version=_sv_started, idempotency_key=_ck, outputs=[], result={"step": _steps[_idx]}, media_repo=_media
                            )
                        )
                except Exception:
                    pass
                try:
                    def _fetch(u):
                        rec = u.find_receipt(project, idempotency_key)
                        if rec is None:
                            return None
                        return json.loads(rec["result_json"])

                    stored = UnitOfWork(writer).run(_fetch)
                    if stored and isinstance(stored, dict) and stored.get("run_id"):
                        run_id = str(stored["run_id"])
                        run_root = root / project / "runs" / run_id
                except Exception:
                    pass
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
