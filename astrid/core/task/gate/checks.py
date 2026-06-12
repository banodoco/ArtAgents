"""Inline produces-check execution and CAS interning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from astrid.core.io.cas import intern, link_identity_artifact, link_into_produces
from astrid.core.task.events import (
    make_cursor_rewind_event,
    make_iteration_failed_event,
    make_produces_check_failed_event,
    make_produces_check_passed_event,
)
from astrid.core.task.gate.base import GateDecision, InlineCheckResult
from astrid.core.task.plan import ProducesEntry, step_dir_for_path


# step_dir_for_path is the ONLY directory API used in this gate path (FLAG-P3-001).
@dataclass(frozen=True)
class _InternedArtifactRef:
    cas_sha256: str | None = None
    cas_identity_sha256: str | None = None


def _run_inline_checks(
    decision: GateDecision,
    produces: tuple[ProducesEntry, ...],
    append_fn: Callable[[dict[str, Any]], Any],
) -> InlineCheckResult:
    if (
        decision.events_path is None
        or decision.run_id is None
        or decision.slug is None
        or decision.project_root is None
        or not decision.plan_step_path
    ):
        return InlineCheckResult(ok=True)
    projects_root = decision.project_root.parent
    step_dir = step_dir_for_path(
        decision.slug,
        decision.run_id,
        decision.plan_step_path,
        step_version=decision.step_version,
        iteration=decision.iteration,
        item_id=None if decision.iteration is not None else decision.item_id,
        root=projects_root,
    )
    produces_root = step_dir / "produces"
    emitted: list[dict[str, Any]] = []

    def _append_inline(event: dict[str, Any]) -> None:
        emitted.append(event)
        append_fn(event)

    for entry in produces:
        artifact_path = produces_root / entry.path
        result = entry.check.run(artifact_path)
        if not result.ok:
            _append_inline(
                make_produces_check_failed_event(
                    decision.plan_step_path,
                    entry.name,
                    check_id=entry.check.check_id,
                    reason=result.reason,
                    step_version=decision.step_version,
                    dispatch_event_hash=decision.dispatch_event_hash,
                ),
            )
            if decision.iteration is not None or decision.item_id is not None:
                _append_inline(
                    make_iteration_failed_event(
                        decision.plan_step_path,
                        decision.iteration if decision.iteration is not None else 0,
                        reason=f"produces check failed: {entry.name}",
                        step_version=decision.step_version,
                    ),
                )
            else:
                _append_inline(
                    make_cursor_rewind_event(
                        decision.plan_step_path,
                        reason=f"produces check failed: {entry.name}",
                        step_version=decision.step_version,
                        dispatch_event_hash=decision.dispatch_event_hash,
                    ),
                )
            return InlineCheckResult(
                ok=False,
                name=entry.name,
                reason=result.reason,
                events=tuple(emitted),
            )
        cas_ref = _intern_produces_artifact(decision, artifact_path)
        _append_inline(
            make_produces_check_passed_event(
                decision.plan_step_path,
                entry.name,
                check_id=entry.check.check_id,
                cas_sha256=cas_ref.cas_sha256,
                cas_identity_sha256=cas_ref.cas_identity_sha256,
                step_version=decision.step_version,
                dispatch_event_hash=decision.dispatch_event_hash,
            ),
        )
    return InlineCheckResult(ok=True, events=tuple(emitted))


def _intern_produces_artifact(
    decision: GateDecision, artifact_path: Path
) -> _InternedArtifactRef:
    if decision.project_root is None:
        return _InternedArtifactRef()
    if artifact_path.is_symlink():
        return _InternedArtifactRef()
    if decision.artifact_identity is not None:
        cas_target = link_identity_artifact(
            decision.project_root,
            artifact_path,
            decision.artifact_identity.identity_key,
        )
        link_into_produces(cas_target, artifact_path)
        return _InternedArtifactRef(cas_identity_sha256=decision.artifact_identity.identity_key)
    cas_target = intern(decision.project_root, artifact_path)
    link_into_produces(cas_target, artifact_path)
    return _InternedArtifactRef(cas_sha256=cas_target.name)
