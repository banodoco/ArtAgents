"""Run-completion state determination.

Houses ``_run_is_complete``, the predicate that decides when every leaf step
of a run is terminal. It lives here (rather than in ``events.py``) so it can
import ``plan.py`` at module scope: ``plan.py`` imports ``events.py`` for
``canonical_event_json``, so a module-scope ``plan`` import inside ``events.py``
would be a cycle. Nothing in ``plan``/``events`` imports this module, so the
``plan`` import below is cycle-free.
"""

from __future__ import annotations

from typing import Any

from astrid.contracts.run_status import STEP_LIFECYCLE_KINDS, STEP_TERMINAL_KINDS
from astrid.core.task.plan import STEP_PATH_SEP, iter_steps_with_path

__all__ = ["_run_is_complete"]

_RUN_STATE_LIFECYCLE_KINDS = STEP_LIFECYCLE_KINDS
_RUN_STATE_TERMINAL_KINDS = STEP_TERMINAL_KINDS


def _run_is_complete(plan: Any, events: list[dict[str, Any]]) -> bool:
    """Return True only when all leaf steps are terminal-non-aborted.

    Terminal-non-aborted means the step has one of the canonical step terminal
    events and is NOT in ``awaiting_fetch`` or ``dispatched`` without terminal
    follow-up.
    """
    leaves: list[tuple[str, int]] = []
    if hasattr(plan, "steps") and plan.steps is not None:
        for path_tuple, step in iter_steps_with_path(plan):
            if step.children is None:
                leaves.append((STEP_PATH_SEP.join(path_tuple), step.version))

    if not leaves:
        return False

    # Map step path -> latest event kind for terminal checks.
    # ``step_attested`` events carry the legacy ``plan_step_id`` string instead of
    # a ``plan_step_path`` list (see make_step_attested_event), so accept both.
    #
    # Only "step lifecycle" events count. Advisory events like
    # ``produces_check_passed`` / ``produces_check_failed`` are appended by
    # ``_run_inline_checks`` immediately AFTER a step has already transitioned
    # to ``step_attested``/``step_completed``, and shadowing the lifecycle
    # event with the advisory one was the root cause of the C2 bug surfaced by
    # the 12-DeepSeek regression probe: every run hit 6/6 attested but
    # ``_run_is_complete`` returned False because the per-leaf latest_kind was
    # ``produces_check_passed``, not ``step_attested``.
    latest_by_path: dict[tuple[str, int], str] = {}
    latest_dispatch_version_by_path: dict[str, int] = {}
    for event in events:
        kind = event.get("kind")
        if not isinstance(kind, str):
            continue
        if kind not in _RUN_STATE_LIFECYCLE_KINDS:
            continue
        raw_version = event.get("step_version")
        path_list = event.get("plan_step_path")
        if isinstance(path_list, list) and path_list:
            path_str = "/".join(str(p) for p in path_list)
            if isinstance(raw_version, int) and not isinstance(raw_version, bool) and raw_version >= 1:
                step_version = raw_version
            else:
                step_version = latest_dispatch_version_by_path.get(path_str, 1)
            if kind == "step_dispatched":
                latest_dispatch_version_by_path[path_str] = step_version
            latest_by_path[(path_str, step_version)] = kind
            continue
        legacy_id = event.get("plan_step_id")
        if isinstance(legacy_id, str) and legacy_id:
            if isinstance(raw_version, int) and not isinstance(raw_version, bool) and raw_version >= 1:
                step_version = raw_version
            else:
                step_version = latest_dispatch_version_by_path.get(legacy_id, 1)
            if kind == "step_dispatched":
                latest_dispatch_version_by_path[legacy_id] = step_version
            latest_by_path[(legacy_id, step_version)] = kind

    for path_str, step_version in leaves:
        latest_kind = latest_by_path.get((path_str, step_version))
        if latest_kind is None and STEP_PATH_SEP in path_str:
            # Legacy synthetic tests and pre-path event logs may record only
            # the leaf id. Prefer the exact path above; this fallback keeps
            # old unambiguous logs readable without allowing a stale version
            # to satisfy a superseded step.
            latest_kind = latest_by_path.get((path_str.rsplit(STEP_PATH_SEP, 1)[-1], step_version))

        if latest_kind is None:
            # No event at all for this leaf — not terminal.
            return False
        if latest_kind == "step_awaiting_fetch":
            return False
        if latest_kind == "step_dispatched":
            return False
        # ``step_attested`` is the terminal event for attested steps (the gate
        # at gate.py:275 already treats it as advance-eligible alongside the
        # other terminal kinds), so completion must accept it too.
        if latest_kind not in _RUN_STATE_TERMINAL_KINDS:
            return False

    return True
