"""Training-run plan template for A5a wrapped-opaque Arnold compatibility.

The training runner remains wrapped opaque in A5a: Arnold sees one local stage
that re-enters the existing ``training.training_run`` entrypoint with the same
CLI contract, and ``last_run.json`` stays the authoritative resume cursor.
"""

from __future__ import annotations

import shlex
import uuid
from pathlib import Path
from typing import Any

from astrid.core.execution.orchestrator.plan_template import (
    build_leaf_template,
    build_plan_template,
    cost_entry,
    emit_plan_json,
    file_output,
)


def build_plan_v2(
    *,
    python_exec: str,
    run_root: str | Path,
    config: str | Path,
    manifest: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a single-stage opaque plan for ``training.training_run``."""
    run_root = Path(run_root).expanduser().resolve()
    config = Path(config).expanduser().resolve()
    plan_id = f"training-run-{run_id or uuid.uuid4().hex[:12]}"

    command = _build_training_run_cmd(
        python_exec=python_exec,
        config=config,
        run_root=run_root,
        manifest=manifest,
    )

    return build_plan_template(
        plan_id=plan_id,
        steps=[
            build_leaf_template(
                "training-run",
                command=command,
                produces=[
                    file_output(
                        "run_state",
                        run_root / "last_run.json",
                    )
                ],
                cost=cost_entry(0, source="local"),
            )
        ],
    )


def _build_training_run_cmd(
    *,
    python_exec: str,
    config: Path,
    run_root: Path,
    manifest: str | Path | None,
) -> str:
    parts = [
        shlex.quote(str(python_exec)),
        "-m",
        "astrid.packs.training.orchestrators.training_run.run",
        "--config",
        shlex.quote(str(config)),
        "--out",
        shlex.quote(str(run_root)),
    ]
    if manifest is not None:
        manifest_path = Path(manifest).expanduser().resolve()
        parts.extend(["--manifest", shlex.quote(str(manifest_path))])
    return " ".join(parts)


__all__ = ["build_plan_v2", "emit_plan_json"]
