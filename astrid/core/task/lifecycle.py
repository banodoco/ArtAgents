"""Task lifecycle command facade.

Implementation lives in focused modules:
- plan_builder: start-plan construction and cmd_start
- orchestrator_resolver: qualified id and registry/alias resolution helpers
- run_store: run terminal state, run listing, abort, retry-fetch
- operator_view: status/next rendering and operator-facing instructions
- session_discovery: session/project discovery hints for next
"""

from __future__ import annotations

from astrid.core.project.paths import project_dir, validate_project_slug, validate_run_id
from astrid.core.task.events import _run_is_complete
from astrid.core.task.gate import peek_current_step
from astrid.core.task import operator_view as _operator_view
from astrid.core.task import run_store as _run_store
from astrid.core.task.operator_view import (
    _emit_for_each_autoclose_audit,
    _format_ack_template,
    _format_claim_line,
    _format_schema_requirements,
    _inline_failure_tail,
    _leaf_progress,
    _dispatch_from_tail,
    _print_post_completion_handoff,
    render_step_instructions,
)
from astrid.core.task.orchestrator_resolver import (
    _canonical_orchestrator_id,
    _list_orchestrator_ids,
    _qualified_split,
    _resolve_packs_root,
)
from astrid.core.task.plan_builder import (
    _build_canonical_start_plan,
    _event_talks_project_inputs,
    _hype_project_inputs,
    _thumbnail_maker_project_inputs,
    cmd_start,
)
from astrid.core.task.run_store import (
    _emit_run_completed_if_needed,
    _summarize_run_dir,
)
from astrid.core.task.session_discovery import (
    _list_project_slugs,
    _most_recent_session_slug,
    _os_environ_has_session,
    _print_next_no_run_hint,
    _print_next_unbound_hint,
)
from astrid.core.task.lifecycle_ack import cmd_ack
from astrid.core.task.lifecycle_skip import cmd_skip


def _sha256_file(path):
    # TODO(m5b): compatibility placeholder for the pre-split lifecycle surface.
    from astrid.core.task.plan_builder import _plan_sha256_file

    return _plan_sha256_file(path)


_ORIGINAL_RENDER_STEP_INSTRUCTIONS = _operator_view.render_step_instructions
_ORIGINAL_EMIT_RUN_COMPLETED_IF_NEEDED = _operator_view._emit_run_completed_if_needed
_ORIGINAL_DISPATCH_FROM_TAIL = _operator_view._dispatch_from_tail


def cmd_next(argv, *, projects_root=None):
    """Compatibility wrapper for monkeypatchable lifecycle helpers."""
    # Preserve old tests/hooks that patch lifecycle.* while keeping the
    # implementation in operator_view. The real feedback ledger path in
    # operator_view calls step_dir_for_path(..., step_version=peek.step.version).
    _sync_run_store_globals()
    _operator_view.render_step_instructions = render_step_instructions
    _operator_view._emit_run_completed_if_needed = _emit_run_completed_if_needed
    _operator_view._dispatch_from_tail = _dispatch_from_tail
    try:
        return _operator_view.cmd_next(argv, projects_root=projects_root)
    finally:
        _operator_view.render_step_instructions = _ORIGINAL_RENDER_STEP_INSTRUCTIONS
        _operator_view._emit_run_completed_if_needed = _ORIGINAL_EMIT_RUN_COMPLETED_IF_NEEDED
        _operator_view._dispatch_from_tail = _ORIGINAL_DISPATCH_FROM_TAIL


def cmd_status(argv, *, projects_root=None):
    return _operator_view.cmd_status(argv, projects_root=projects_root)


def _sync_run_store_globals() -> None:
    _run_store.project_dir = project_dir
    _run_store.validate_project_slug = validate_project_slug
    _run_store.validate_run_id = validate_run_id
    _run_store._run_is_complete = _run_is_complete


def cmd_abort(argv, *, projects_root=None):
    _sync_run_store_globals()
    return _run_store.cmd_abort(argv, projects_root=projects_root)


def cmd_runs_ls(argv, *, projects_root=None):
    _sync_run_store_globals()
    return _run_store.cmd_runs_ls(argv, projects_root=projects_root)


def cmd_step_retry_fetch(argv, *, projects_root=None):
    """Compatibility wrapper for tests that patch lifecycle module globals."""
    _sync_run_store_globals()
    return _run_store.cmd_step_retry_fetch(argv, projects_root=projects_root)


__all__ = [
    "cmd_abort",
    "cmd_ack",
    "cmd_next",
    "cmd_runs_ls",
    "cmd_skip",
    "cmd_start",
    "cmd_status",
    "cmd_step_retry_fetch",
]
