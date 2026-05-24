"""Sprint 3 placeholder for the schema-reserved remote-artifact adapter."""

from __future__ import annotations

from astrid.core.adapter import CompleteResult, DispatchResult, PollResult, RunContext
from astrid.core.task.plan import Step

REMOTE_ARTIFACT_DEFERRAL = (
    "remote-artifact is reserved for Sprint 5a and is runtime-disabled in "
    "Sprint 3; use adapter 'local' or 'manual' for this run."
)


class RemoteArtifactDeferralError(RuntimeError):
    """Raised when a reserved remote-artifact runtime path is reached."""


def _deferral_message(step_id: str | None = None) -> str:
    if step_id:
        return f"{REMOTE_ARTIFACT_DEFERRAL} step={step_id!r}"
    return REMOTE_ARTIFACT_DEFERRAL


def raise_remote_artifact_deferral(step: Step | None = None) -> None:
    raise RemoteArtifactDeferralError(
        _deferral_message(step.id if step is not None else None)
    )


class RemoteArtifactAdapter:
    """Reserved adapter surface.

    Sprint 3 keeps ``remote-artifact`` valid in plan schema so future plans can
    round-trip, but every runtime operation fails closed until the Sprint 5a
    implementation lands.
    """

    name = "remote-artifact"

    def dispatch(self, step: Step, run_ctx: RunContext) -> DispatchResult:
        raise_remote_artifact_deferral(step)

    def poll(self, step: Step, run_ctx: RunContext) -> PollResult:
        raise_remote_artifact_deferral(step)

    def complete(self, step: Step, run_ctx: RunContext) -> CompleteResult:
        raise_remote_artifact_deferral(step)


__all__ = [
    "REMOTE_ARTIFACT_DEFERRAL",
    "RemoteArtifactAdapter",
    "RemoteArtifactDeferralError",
    "_deferral_message",
    "raise_remote_artifact_deferral",
]
