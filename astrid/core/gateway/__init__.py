#!/usr/bin/env python3
"""Astrid top-level command gateway.

Sprint 1 wires the session CLI gate: every verb outside the accepted unbound
allowlist requires ``ASTRID_SESSION_ID`` or a project ``.astrid-session`` file
to resolve to a valid session record. Unbound callers are pointed first at
``astrid status`` so they can attach deliberately. ``--help``/``-h`` is exempt
wherever it appears in argv: usage text is documentation and never requires a
bound session (this also lets a fresh checkout verify documented commands).

The settled Sprint 1 allowlist is recorded in
``SPRINT1_UNBOUND_ALLOWLIST_CONTRACT`` below: help/version, ``status``,
``next``, ``attach``, ``projects ls``, ``projects create``,
``projects default``, ``projects theme``, ``themes ls``, ``sessions ls``,
``sessions takeover``, and ``doctor``
(a diagnostic that must run before any session exists). Unbound
``sessions takeover`` is legal only because it must bootstrap or select a
concrete caller session before it mutates the target lease; anonymous takeover
is outside the contract.

Subcommands dispatch to focused module CLIs. Brief / video flags fall
through to the ``video_editing.hype`` orchestrator resolved through the
orchestrator registry.
"""

from __future__ import annotations

import sys

from astrid.core.contracts.errors import (
    AstridError,
    coerce_astrid_error,
    render_astrid_error,
    wrap_degraded_error,
)
from astrid.core.gateway.dispatch import (
    _TOP_LEVEL_HANDLERS,
    _build_dispatch_parser,
    _dispatch_attach,
    _dispatch_audit,
    _dispatch_claim,
    _dispatch_default_brief,
    _dispatch_doctor,
    _dispatch_elements,
    _dispatch_events,
    _dispatch_executor_main,
    _dispatch_executors,
    _dispatch_hook,
    _dispatch_lifecycle,
    _dispatch_modalities,
    _dispatch_models,
    _dispatch_orchestrate,
    _dispatch_orchestrators,
    _dispatch_packs,
    _dispatch_plan_verbs,
    _dispatch_projects,
    _dispatch_publish,
    _dispatch_publish_youtube,
    _dispatch_reigh_data,
    _dispatch_run,
    _dispatch_runpod,
    _dispatch_runpod_ensure_storage,
    _dispatch_runpod_sweep,
    _dispatch_runpod_volumes,
    _dispatch_runs,
    _dispatch_scratch,
    _dispatch_serve,
    _dispatch_sessions,
    _dispatch_setup,
    _dispatch_skills,
    _dispatch_status,
    _dispatch_step,
    _dispatch_test,
    _dispatch_themes,
    _dispatch_timelines,
    _dispatch_unclaim,
    _dispatch_worker,
    _run_default_brief_from_args,
    _top_level_commands,
)
from astrid.core.gateway.help import (
    _packs_subcommand_list,
    _print_entrypoint_help,
)
from astrid.core.gateway.project import (
    _AUTO_BIND_RUN_VERBS,
    _REQUEST_SCOPED_PROJECT_RUN_VERBS,
    ASTRID_GATEWAY_RESOLVED_PROJECT_ENV,
    DEFAULT_PROJECT_SLUG,
    _auto_bind_default_project_session,
    _dispatch_with_resolved_project,
    _extract_project_slug,
    _extract_project_slug_from_run_paths,
    _has_cli_option,
    _is_request_scoped_run,
    _invocation_is_auto_bindable_run,
    _raise_on_ambiguous_run_path_projects,
    _resolved_request_project_slug,
)
from astrid.core.gateway.wait import (
    _make_run_ctx_for_poll,
    _read_returncode_sidecar,
    _wait_adapter,
    _wait_local_subprocess,
    _wait_remote_artifact,
)
from astrid.core.util.log_and_swallow import log_and_swallow

from . import dispatch as _gateway_dispatch

# Phase 5 lifecycle verbs short-circuit the implicit task-mode gate at the top
# of main(): for these verbs the --project flag identifies the run, NOT a
# command to dispatch through plan[cursor]. cmd_ack approve re-enters the gate
# explicitly (see lifecycle_ack._ack_approve), so the short-circuit only
# bypasses the gate's command-match step.
LIFECYCLE_VERBS = {
    "start",
    "next",
    "ack",
    "skip",
    "abort",
    "status",
    "runs",
    "hook",
    "plan",
    "claim",
    "unclaim",
    "step",
    # Fix 4 (ticket #45 / v6 idempotent_reattach): `astrid run {show,trace,
    # artifacts,cost}` are read-only audit verbs that must not be blocked by
    # the task-mode active-run gate. Without this, agents have to `astrid
    # abort` just to inspect a stuck run — destroying the very state they
    # were trying to read.
    "run",
    "events",
}

TASK_GATE_READONLY_VERBS = {
    ("projects", "cost"),
    ("projects", "export"),
    ("timelines", "cost"),
    ("timelines", "export"),
}


# Canonical accepted unbound contract for Sprint 1. The gate implementation
# below is deliberately table-driven: do not add ad hoc unbound exceptions
# outside this tuple.
SPRINT1_UNBOUND_ALLOWLIST_CONTRACT: tuple[tuple[str, ...], ...] = (
    ("-h",),
    ("--help",),
    ("help",),
    ("--version",),
    ("status",),
    ("next",),
    ("attach",),
    ("projects", "ls"),
    ("projects", "create"),
    ("projects", "select"),
    ("projects", "use"),
    ("projects", "default"),
    ("projects", "theme"),
    ("themes", "ls"),
    ("sessions", "ls"),
    ("sessions", "takeover"),
    ("packs",),
    ("test",),
    ("doctor",),
    ("serve",),
)
_SPRINT1_UNBOUND_ALLOWLIST = frozenset(SPRINT1_UNBOUND_ALLOWLIST_CONTRACT)

# Project resolution constants and helpers live in gateway/project.py.
# They are re-exported here so the gateway facade remains the canonical
# access point for all callers (including astrid.core.gateway).


def main(argv: list[str] | None = None) -> int:
    raw = sys.argv[1:] if argv is None else list(argv)
    try:
        return _main_impl(raw)
    except AstridError as exc:
        return render_astrid_error(exc)
    except Exception as exc:  # noqa: BLE001
        bug = wrap_degraded_error(
            exc,
            state_snapshot={"argv": raw, "entrypoint": "astrid.core.gateway.main"},
        )
        return render_astrid_error(bug)


def _main_impl(raw: list[str]) -> int:
    raw = _normalize_gateway_lifecycle_compat(raw)
    first_arg = next(iter(raw), None)
    if first_arg in {"-h", "--help", "help"}:
        _print_entrypoint_help()
        return 0
    if first_arg == "--version":
        print("astrid")
        return 0
    # Help for a subcommand (e.g. `astrid elements list --help`) must never
    # require a bound session — argparse should print usage and exit 0
    # regardless of session state. The first-arg check above only catches
    # top-level help; this catches `-h`/`--help` anywhere in the argv.
    if raw and any(tok in {"-h", "--help"} for tok in raw):
        return _dispatch(raw)
    # Nudge runs once per CLI invocation, before the command itself, but never
    # for the `skills` subcommand (would be silly) or help. Cheap state-file
    # read; bails early if no harness is detected or ASTRID_NO_NUDGE is set.
    try:
        from astrid.skills import nudge_if_needed

        nudge_if_needed(argv=raw)
    except Exception as exc:  # noqa: BLE001
        # Never let the nudge break a real command.
        log_and_swallow(exc, context="gateway.nudge_if_needed")

    # File-scoped run invocations that reference more than one local project in
    # their explicit paths are ambiguous: refuse rather than silently routing
    # provenance to the wrong project (or the global default). Raised before the
    # session gate so the error is reported regardless of bound-session state.
    _raise_on_ambiguous_run_path_projects(raw)

    # Session gate. Verbs outside the unbound allowlist require a resolvable
    # session record; print the documented hint and exit 2 otherwise.
    session = None
    if not _verb_is_unbound_allowlisted(raw):
        from astrid.core.session.binding import (
            SessionBindingError,
            resolve_current_session_with_fs_fallback,
        )

        try:
            # T9 / FLAG-S1-003: pass slug from argv when available so
            # file-bound .astrid-session fallback can resolve in a fresh
            # terminal that lost ASTRID_SESSION_ID. Fix 1 (v6 dogfood): when
            # neither env var nor --project is in hand, walk the projects
            # root for a single ``.astrid-session`` (the same generalised
            # cross-shell fallback that ``astrid next`` already provides).
            _slug_hint = _extract_project_slug(raw)

            def _nudge(discovered_slug: str) -> None:
                print(
                    f"(auto-resolved session for project {discovered_slug!r} "
                    f"via .astrid-session; pass --project to override)",
                    file=sys.__stderr__,
                )

            from astrid.core.foundation.project_paths import resolve_projects_root

            session = resolve_current_session_with_fs_fallback(
                slug=_slug_hint,
                on_auto_resolve=_nudge,
                projects_root=resolve_projects_root(),
            )
        except SessionBindingError as exc:
            _project_hint = _extract_project_slug(raw) or _extract_project_slug_from_run_paths(raw)
            _recovery_cmd = f"astrid attach {_project_hint}" if _project_hint else "astrid status"
            raise AstridError(
                f"session: {exc}",
                recovery_command=_recovery_cmd,
                state_snapshot={"argv": raw},
            ) from exc
        if session is None:
            project_hint = _extract_project_slug(raw)
            needs_project_guidance = _is_request_scoped_run(raw) or tuple(raw[:2]) == (
                "timelines",
                "create",
            )
            if needs_project_guidance and project_hint is None:
                from astrid.core.project.guidance import format_project_required_guidance

                operation = (
                    "executor run"
                    if tuple(raw[:2]) == ("executors", "run")
                    else (
                        "scratch run"
                        if tuple(raw[:2]) == ("scratch", "run")
                        else (
                            "timeline"
                            if tuple(raw[:2]) == ("timelines", "create")
                            else "orchestrator run"
                        )
                    )
                )
                raise AstridError(
                    format_project_required_guidance(operation=operation),
                    recovery_command="astrid projects ls",
                    state_snapshot={"argv": raw, "project": None},
                )
            attach_hint = (
                f"`astrid attach {project_hint}`"
                if project_hint
                else "`astrid attach <project>`"
            )
            recovery_cmd = f"astrid attach {project_hint}" if project_hint else "astrid status"
            raise AstridError(
                f"no session bound — run `astrid status` to list projects, then {attach_hint} "
                "or pass `--project <slug>` on the operation",
                recovery_command=recovery_cmd,
                state_snapshot={"argv": raw, "project": project_hint},
            )

    request_project = _resolved_request_project_slug(raw, session)
    if _is_request_scoped_run(raw):
        explicit_project = _extract_project_slug(raw)
        effective_project = explicit_project or request_project
        if effective_project:
            source = "explicit --project" if explicit_project else "attached session"
            print(
                f"project: {effective_project} ({source})",
                file=sys.__stderr__,
            )
    if _verb_bypasses_task_gate(raw):
        return _dispatch_with_resolved_project(raw, request_project)
    project_slug = _extract_project_slug(raw)
    if project_slug is None:
        return _dispatch_with_resolved_project(raw, request_project)

    core_gate = _gateway_gate_module()

    try:
        decision = core_gate.gate_command(project_slug, core_gate.command_for_argv(raw), raw)
    except core_gate.TaskRunGateError as exc:
        raise coerce_astrid_error(
            exc,
            state_snapshot={"argv": raw, "project": project_slug, "gate": "task-mode"},
        ) from exc
    if not decision.active:
        return _dispatch(raw)

    returncode = -1
    try:
        # Sprint 3 (T14): adapter-aware dispatch. For code steps with an adapter
        # (local/manual), the adapter's dispatch() was already called inside
        # gate_command.  Skip _dispatch(raw) to avoid double-execution.
        if decision.step_kind == "code" and decision.adapter:
            returncode = _wait_adapter(decision)
        else:
            returncode = _dispatch_with_resolved_project(raw, request_project)
        return returncode
    finally:
        core_gate.record_dispatch_complete(decision, returncode)


def _verb_bypasses_task_gate(raw: list[str]) -> bool:
    first = next(iter(raw), None)
    if first in LIFECYCLE_VERBS:
        return True
    if len(raw) >= 2 and tuple(raw[:2]) in TASK_GATE_READONLY_VERBS:
        return True
    return False


def _normalize_gateway_lifecycle_compat(raw: list[str]) -> list[str]:
    if not raw or raw[0] not in {"start", "next", "ack", "abort"} or _has_engine_flag(raw):
        return raw
    return [*raw, "--engine", "task"]


def _has_engine_flag(raw: list[str]) -> bool:
    return "--engine" in raw or any(arg.startswith("--engine=") for arg in raw)


def _gateway_gate_module() -> Any:
    from astrid.core import gate as stable_gate
    from astrid.core.task import gate as legacy_gate

    legacy_gate_command = getattr(legacy_gate, "gate_command")
    stable_gate_command = getattr(stable_gate, "gate_command")
    if hasattr(legacy_gate_command, "assert_called_once_with"):
        return legacy_gate
    if hasattr(stable_gate_command, "assert_called_once_with"):
        return stable_gate
    return stable_gate


def _verb_is_unbound_allowlisted(raw: list[str]) -> bool:
    """Decide whether the invocation may run without a bound session.

    The final Sprint 1 contract is ``SPRINT1_UNBOUND_ALLOWLIST_CONTRACT``.
    Exact top-level entries match one token; exact subcommand entries match
    their listed prefix. No other discovery, setup, task, RunPod, or builder
    verb is sessionless.
    """

    if not raw:
        return True  # empty argv → entrypoint help

    # An explicit project is complete context for one-shot capability runs and
    # timeline creation. These commands do not require a persistent attached
    # session merely to identify their owner.
    if _extract_project_slug(raw) is not None:
        if tuple(raw[:2]) in {
            ("executors", "run"),
            ("orchestrators", "run"),
            ("scratch", "run"),
            ("timelines", "create"),
            ("projects", "source"),
        }:
            return True
        # Timeline edit verbs that are exempt with explicit --project:
        # clip, track, effect, transition, theme, audio, arrangement, pool, registry
        if raw[0] == "timelines" and len(raw) >= 2 and raw[1] in {
            "clip", "track", "effect", "transition", "theme", "audio",
            "arrangement", "pool", "registry",
        }:
            return True

    for allowed in _SPRINT1_UNBOUND_ALLOWLIST:
        if tuple(raw[: len(allowed)]) == allowed:
            return True
    return False


def _dispatch(raw: list[str]) -> int:
    return _gateway_dispatch._dispatch(raw)


# _extract_project_slug, _resolved_request_project_slug,
# _dispatch_with_resolved_project, _has_cli_option,
# _invocation_is_auto_bindable_run, and _auto_bind_default_project_session
# are now defined in gateway/project.py and re-exported at the top of this
# module so callers (including astrid.core.gateway) continue to resolve them
# through the gateway facade unchanged.


def _run_default_brief_orchestrator(argv: list[str]) -> int:
    from importlib import import_module

    from astrid.core.execution.orchestrator.registry import load_default_registry

    registry = load_default_registry()
    orchestrator = registry.get("video_editing.hype")
    runtime_module = orchestrator.metadata.get("runtime_module")
    runtime_entrypoint = orchestrator.metadata.get("runtime_entrypoint", "main")
    if not isinstance(runtime_module, str) or not runtime_module:
        raise AstridError(
            "video_editing.hype manifest is missing metadata.runtime_module",
            recovery_command="astrid orchestrators inspect video_editing.hype --json",
            state_snapshot={"orchestrator_id": "video_editing.hype"},
        )
    module = import_module(runtime_module)
    entrypoint = getattr(module, runtime_entrypoint)
    return int(entrypoint(argv))


# _packs_subcommand_list and _print_entrypoint_help are now defined in
# gateway/help.py and re-exported at the top of this module so callers
# (including gateway.dispatch._dispatch and astrid.core.gateway) continue to
# resolve them through the gateway facade unchanged.


if __name__ == "__main__":
    raise SystemExit(main())
