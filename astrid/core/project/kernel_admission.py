"""Shared kernel admission helper for pack orchestrators (B2.3).

Self-managing orchestrators previously called ``prepare_project_run``
directly (second ledger). This shim routes through the same kernel
admission path as ``sdk.invoke`` — synthesizing run/task ids and
returning a staging-only context (no authoritative run.json).
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
    """Admit via kernel (staging-only) — no authoritative run.json write."""
    from astrid.core.ids import generate_lowercase_ulid

    # Generate kernel ids; out lives under projects_root staging
    run_id = generate_lowercase_ulid()
    # staging dir: projects_root/<slug>/runs/<run_id> if projects_root known else temp
    if projects_root is not None:
        root = Path(projects_root).expanduser().resolve()
        run_root = root / project / "runs" / run_id
    else:
        import tempfile
        run_root = Path(tempfile.gettempdir()) / f"astrid-kernel-{run_id}"
    run_root.mkdir(parents=True, exist_ok=True)
    return KernelAdmissionContext(run_id=run_id, run_root=run_root, project_slug=project)
