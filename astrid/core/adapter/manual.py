"""Manual-adapter: out-of-band ack-driven OR inbox-driven completion."""

from __future__ import annotations

import json
from pathlib import Path

from astrid.core.adapter import CompleteResult, DispatchResult, PollResult, RunContext
from astrid.core.adapter._common import _step_dir
from astrid.core.project.sidecar import write_json_sidecar
from astrid.core.task.plan import CostEntry, Step
from astrid.core.util.time import utc_now_milliseconds

# Inbox completion-entry contract — parity with the ack identity contract:
# every inbox-driven completion MUST carry submitted_by + submitted_by_kind.
REQUIRED_INBOX_KEYS = ("submitted_by", "submitted_by_kind")


class ManualAdapter:
    """Manual adapter — agent or human runs work out-of-band; completion arrives via ack or inbox."""

    name = "manual"

    def dispatch(self, step: Step, run_ctx: RunContext) -> DispatchResult:
        if step.command is None or not step.command.strip():
            return DispatchResult(status="rejected", reason="manual adapter requires a non-empty command (dispatch payload)")
        step_dir = _step_dir(run_ctx)
        step_dir.mkdir(parents=True, exist_ok=True)
        dispatch_path = step_dir / "dispatch.json"
        started_at = utc_now_milliseconds()
        payload: dict[str, object] = {
            "step_id": step.id,
            "step_version": run_ctx.step_version,
            "command": run_ctx.canonical_command or step.command,
            "display_command": run_ctx.display_command,
            "task_env": run_ctx.task_env or {},
            "adapter": "manual",
            "assignee": step.assignee,
            "requires_ack": step.requires_ack,
            "dispatched_at": started_at,
        }
        if step.instructions is not None:
            payload["instructions"] = step.instructions
        if step.ack is not None:
            payload["ack"] = {"kind": step.ack.kind}
        write_json_sidecar(dispatch_path, payload)
        return DispatchResult(status="dispatched", started_at=started_at)

    def poll(self, step: Step, run_ctx: RunContext) -> PollResult:
        completion = _read_completion(_step_dir(run_ctx))
        if completion is None:
            return PollResult(status="pending")
        return PollResult(status="done" if completion.get("status") != "failed" else "failed")

    def complete(self, step: Step, run_ctx: RunContext) -> CompleteResult:
        """Read produces/completion.json (inbox-driven path) OR rely on caller-supplied ack.

        cmd_next + the inbox consumer write produces/completion.json to this dir
        when an inbox entry routes here; ack-driven completion writes the same
        sidecar from cmd_ack. Either way the format is identical.
        """
        step_dir = _step_dir(run_ctx)
        completion = _read_completion(step_dir)
        if completion is None:
            return CompleteResult(status="failed", reason="manual completion not found")

        # Identity enforcement — parity with the ack identity contract.
        if completion.get("source") == "inbox":
            for key in REQUIRED_INBOX_KEYS:
                if not completion.get(key):
                    return CompleteResult(
                        status="failed",
                        reason=f"inbox completion missing required {key!r}",
                    )

        cost = _read_cost(completion)
        status = completion.get("status")
        if status not in {"completed", "failed"}:
            return CompleteResult(
                status="failed",
                returncode=None,
                reason="manual completion status missing or unknown",
                cost=cost,
            )
        if status == "failed":
            return CompleteResult(status="failed", returncode=None, reason=str(completion.get("reason", "manual completion reported failure")), cost=cost)
        missing = _missing_declared_produces(step, step_dir)
        if missing:
            return CompleteResult(
                status="failed",
                returncode=None,
                reason=f"produces check failed: missing {missing!r}",
                cost=cost,
            )
        return CompleteResult(status="completed", cost=cost)


def _read_completion(step_dir: Path) -> dict[str, object] | None:
    candidate = step_dir / "produces" / "completion.json"
    if not candidate.exists():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _missing_declared_produces(step: Step, step_dir: Path) -> list[str]:
    produces_root = step_dir / "produces"
    missing: list[str] = []
    for entry in step.produces:
        artifact = produces_root / entry.path
        if not artifact.exists() or artifact.stat().st_size == 0:
            missing.append(entry.path)
    return missing


def _read_cost(payload: dict[str, object]) -> CostEntry | None:
    cost = payload.get("cost")
    if not isinstance(cost, dict):
        return None
    amount = cost.get("amount")
    currency = cost.get("currency")
    source = cost.get("source")
    if not isinstance(amount, (int, float)) or not isinstance(currency, str) or not isinstance(source, str):
        return None
    return CostEntry(amount=float(amount), currency=currency, source=source)
