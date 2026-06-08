"""Leaf-level gate types and helpers shared across the gate_* modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

from astrid.core.contracts.errors import AstridError
from astrid.core.task.plan import ProducesEntry

ITERATE_FEEDBACK_PREFIX = "iterate_feedback="


class TaskRunGateError(AstridError):
    """Raised when task-mode dispatch is rejected."""

    def __init__(self, reason: str, recovery: str, code: str | None = None) -> None:
        super().__init__(
            reason,
            recovery_command=recovery,
            code=code,
            source_type=type(self).__name__,
        )
        self.reason = reason
        self.recovery = recovery
        # Additive machine-readable slug for agent branching. Optional and
        # appended last so existing catch sites that read only
        # reason/recovery keep working unchanged.
        self.code = code


@dataclass(frozen=True)
class GateDecision:
    active: bool
    run_id: str | None = None
    plan_step_id: str | None = None
    events_path: Path | None = None
    reentry: bool = False
    step_kind: str | None = None
    slug: str | None = None
    plan_step_path: tuple[str, ...] = ()
    produces: tuple[ProducesEntry, ...] = ()
    project_root: Path | None = None
    iteration: int | None = None
    item_id: str | None = None
    # Sprint 1 (T9) extensions — populated when a session is bound at
    # gate_command entry so post-dispatch record_* helpers can flow
    # through writer_context_from_decision.
    run_dir: Path | None = None
    writer_epoch_at_dispatch: int | None = None
    session_id: str | None = None
    session: Any = None  # astrid.core.session.model.Session | None
    # Sprint 3 (T14) adapter dispatch fields.
    step_version: int = 1
    adapter: str | None = None
    pid: int | None = None
    dispatch_event_hash: str | None = None
    # Only populated by _dispatch_attested path; code-step rewinds go through
    # the event log only. See FLAG-S1-005 (correctness-2 / callers-2): we MUST
    # NOT populate this from record_dispatch_complete — code-step rewinds are
    # intentionally NOT surfaced through cmd_ack's 'ack accepted but produces
    # check failed' branch (category error).
    inline_check_result: tuple[str, str] | None = None


@dataclass(frozen=True)
class InlineCheckResult:
    ok: bool
    name: str | None = None
    reason: str | None = None
    events: tuple[dict[str, Any], ...] = field(default_factory=tuple, compare=False)


def _reject(
    slug: str, reason: str, *, abort: bool, code: str = "gate_rejected"
) -> NoReturn:
    verb = "abort" if abort else "next"
    raise TaskRunGateError(
        reason=reason, recovery=f"astrid {verb} --project {slug}", code=code
    )
