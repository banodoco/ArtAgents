#!/usr/bin/env python3
"""Cache-aware subprocess orchestrator for the hype pipeline, including refine between cut and render in pool flow.

.. note::

    The ``hype.timeline.json`` artifacts produced by the ``cut`` step (and
    consumed by downstream steps like ``refine``, ``render``, ``validate``) are
    Remotion timeline files. Managed TimelineConfig-producing steps emit the
    same validated raw container to the project timeline as
    ``timeline.config_replaced``; arrangement-only editor artifacts remain
    non-container compatibility read models."""

from __future__ import annotations

from astrid.core.contracts.errors import AstridError, render_astrid_error
from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('video_editing.hype')
import os
import sys

from astrid.core.project.run import (
    METADATA_KEY_TIMELINE_EVENT_STREAM_ID,
    METADATA_KEY_TIMELINE_SLUG,
    ProjectRunError,
    finalize_project_run,
    prepare_project_run,
    reject_project_with_out,
)
from astrid.packs.training.executors.asset_cache import run as asset_cache

# Extracted modules (M4 T62)
from astrid.packs.video_editing.orchestrators.hype.config import (  # noqa: F401 — re-exported for facade compatibility
    STEP_ORDER,
    load_config,
    normalize_config,
    normalize_extra_args,
    normalize_many,
    parse_asset_entry,
    usage_error,
)
from astrid.packs.video_editing.orchestrators.hype.parser import (  # noqa: F401 — build_parser re-exported for facade compatibility
    build_parser,
    resolve_args,
)

# Extracted module (M4 T66)
from astrid.packs.video_editing.orchestrators.hype.project_adapter import (  # noqa: F401 — re-exported for facade compatibility
    _prepare_project_main,
    _project_hype_artifact_roots,
    _project_hype_metadata,
    _project_slug_for_gate,
    _restore_project_env,
    _set_project_env,
    _system_exit_code,
)
from astrid.packs.video_editing.orchestrators.hype.runner import (  # noqa: F401 — re-exported for facade compatibility
    _apply_trim_deltas_to_arrangement,
    _asset_kind_for_sentinel,
    _brief_allow_generative_visuals,
    _clear_per_brief_sentinels,
    _coerce_frontmatter_value,
    _invalidate_downstream_sentinels,
    _notes_overlap_ratio,
    _parse_url_expiry,
    _plan_action,
    _prefetch_url_inputs,
    _preflight_url_expiry,
    _redact_command,
    _register_run_inputs,
    _register_step_outputs,
    _rotate_editor_review,
    _run_revise,
    _run_steps_once,
    _url_inputs,
    _write_run_json,
    log_dir_for_step,
    parse_brief_frontmatter,
    pool_main,
    prepare_brief_artifacts,
    print_log_tail,
    run_step,
    sentinel_paths,
    should_rerun,
    step_output_root,
    write_skip_log,
)

# Extracted modules (M4 T64)
from astrid.packs.video_editing.orchestrators.hype.steps import (  # noqa: F401 — re-exported for facade compatibility
    PER_BRIEF_SENTINELS,
    PER_SOURCE_SENTINELS,
    Step,
    _append_managed_binding,
    _arrange_target_duration,
    _initial_facts,
    _verdict_build_cmd,
    _write_dry_run_plan,
    add_extra_args,
    asset_args,
    build_pool_cut_cmd,
    build_pool_steps,
    probe_audio_duration,
    select_steps,
    step_argv,
)


# === Main entry point (kept in run.py facade) ===
# Project/gate adapter helpers imported from .project_adapter (M4 T66)
def main(argv: list[str] | None = None) -> int:
    project_context = None
    project_env: dict[str, str | None] = {}
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    try:
        try:
            project_context, effective_argv = _prepare_project_main(effective_argv)
        except ProjectRunError as exc:
            raise AstridError(
                str(exc),
                recovery_command="Check project configuration and retry: astrid status",
            ) from exc
        if project_context is not None:
            project_env = _set_project_env()
        try:
            args = resolve_args(effective_argv)
        except AstridError as exc:
            if project_context is not None:
                finalize_project_run(
                    project_context,
                    status="error",
                    returncode=2,
                    error=exc,
                )
                render_astrid_error(exc)
                return 2
            raise
        except SystemExit as exc:
            if project_context is not None:
                finalize_project_run(project_context, status="error", returncode=_system_exit_code(exc), error=exc)
                return _system_exit_code(exc)
            raise
        if project_context is not None:
            args.project = project_context.project_slug
            args.render_parent_run_id = project_context.run_id
            # Propagate managed timeline slug and event-stream id from run
            # metadata so subprocess callers (cut, refine, etc.) can pass
            # --project + --timeline-slug, and hype-owned managed mutations
            # (e.g. _apply_trim_deltas_to_arrangement) can use the gateway.
            managed_meta = project_context.run.get("metadata", {}) if hasattr(project_context, "run") else {}
            if isinstance(managed_meta, dict):
                args.timeline_slug = managed_meta.get(METADATA_KEY_TIMELINE_SLUG)
                args.timeline_event_stream_id = managed_meta.get(METADATA_KEY_TIMELINE_EVENT_STREAM_ID)
            # m3.5 actor provenance: when managed, determine who launched hype
            # and set args.actor_via so child packs and in-process mutations
            # can chain upstream provenance in actor.via.
            if not hasattr(args, "actor_via") or args.actor_via is None:
                from astrid.core.timeline.events.schema import TimelineActor as _HypeActor

                _hype_actor_type = "agent" if os.environ.get("ASTRID_INTERNAL_INVOCATION") else "human"
                args.actor_via = _HypeActor(
                    type=_hype_actor_type,
                    id=f"hype:{project_context.project_slug}",
                    display=f"hype ({_hype_actor_type})",
                )
        keep_env = os.environ.get("HYPE_KEEP_DOWNLOADS", "").strip().lower() in {"1", "true", "yes"}
        keep_flag = bool(getattr(args, "keep_downloads", False))
        session_enabled = not (keep_flag or keep_env)
        try:
            with asset_cache.ephemeral_session(enabled=session_enabled):
                returncode = pool_main(args)
        except SystemExit as exc:
            if project_context is not None:
                finalize_project_run(
                    project_context,
                    status="error",
                    returncode=_system_exit_code(exc),
                    error=exc,
                    metadata=_project_hype_metadata(args),
                    brief_slug=getattr(args, "brief_slug", None),
                    artifact_roots=_project_hype_artifact_roots(args),
                )
                return _system_exit_code(exc)
            raise
        except Exception as exc:
            if project_context is not None:
                finalize_project_run(
                    project_context,
                    status="error",
                    returncode=-1,
                    error=exc,
                    metadata=_project_hype_metadata(args),
                    brief_slug=getattr(args, "brief_slug", None),
                    artifact_roots=_project_hype_artifact_roots(args),
                )
            raise
        if project_context is not None:
            finalize_project_run(
                project_context,
                status="skipped" if bool(getattr(args, "dry_run", False)) else ("success" if returncode == 0 else "failed"),
                returncode=returncode,
                metadata=_project_hype_metadata(args),
                brief_slug=getattr(args, "brief_slug", None),
                artifact_roots=_project_hype_artifact_roots(args),
            )
        return returncode
    finally:
        _restore_project_env(project_env)


if __name__ == "__main__":
    raise SystemExit(main())
