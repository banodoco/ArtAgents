"""Shared adapter helpers used across multiple adapter modules."""

from __future__ import annotations

import json
from pathlib import Path

from astrid.core.adapter import RunContext
from astrid.core.command_render import step_dir_for_context
from astrid.core.task.plan import CostEntry


def _step_dir(run_ctx: RunContext) -> Path:
    """Resolve runs/<run>/steps/<id>/v<N>/[iterations|items]/... for this dispatch."""
    return step_dir_for_context(
        run_ctx.project_root,
        run_ctx.run_id,
        run_ctx.plan_step_path,
        run_ctx.step_version,
        iteration=run_ctx.iteration,
        item_id=run_ctx.item_id,
    )


def _read_cost_sidecar(step_dir: Path) -> CostEntry | None:
    """Honor the hype-spike G2 convention: subprocess MAY write produces/cost.json."""
    candidate = step_dir / "produces" / "cost.json"
    if not candidate.exists():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    amount = payload.get("amount")
    currency = payload.get("currency")
    source = payload.get("source")
    if not isinstance(amount, (int, float)) or not isinstance(currency, str) or not isinstance(source, str):
        return None
    return CostEntry(amount=float(amount), currency=currency, source=source)
