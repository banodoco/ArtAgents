"""Dataset-build plan template for Sprint 5b.

The dataset builder remains wrapped opaque in A5a: Arnold sees one local stage
that re-enters the existing ``training.dataset_build`` entrypoint with the same
CLI contract, and ``review_state.json`` stays the authoritative resume cursor.
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
    review_decisions: str | Path | None = None,
    skip_review: bool = False,
    review_only: bool = False,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a single-stage opaque plan for ``training.dataset_build``."""
    run_root = Path(run_root).expanduser().resolve()
    config = Path(config).expanduser().resolve()
    plan_id = f"dataset-build-{run_id or uuid.uuid4().hex[:12]}"

    command = _build_dataset_build_cmd(
        python_exec=python_exec,
        config=config,
        run_root=run_root,
        review_decisions=review_decisions,
        skip_review=skip_review,
        review_only=review_only,
    )

    return build_plan_template(
        plan_id=plan_id,
        steps=[
            build_leaf_template(
                "dataset-build",
                command=command,
                produces=[
                    file_output(
                        "review_state",
                        run_root / "review_state.json",
                    )
                ],
                cost=cost_entry(0, source="local"),
            )
        ],
    )


def _build_dataset_build_cmd(
    *,
    python_exec: str,
    config: Path,
    run_root: Path,
    review_decisions: str | Path | None,
    skip_review: bool,
    review_only: bool,
) -> str:
    parts = [
        shlex.quote(str(python_exec)),
        "-m",
        "astrid.packs.training.orchestrators.dataset_build.run",
        "--config",
        shlex.quote(str(config)),
        "--out",
        shlex.quote(str(run_root)),
    ]
    if review_decisions is not None:
        decisions_path = Path(review_decisions).expanduser().resolve()
        parts.extend(["--review-decisions", shlex.quote(str(decisions_path))])
    if skip_review:
        parts.append("--skip-review")
    if review_only:
        parts.append("--review-only")
    return " ".join(parts)


__all__ = ["build_plan_v2", "emit_plan_json"]
