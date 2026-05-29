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
``projects default``, ``sessions ls``, ``sessions takeover``, and ``doctor``
(a diagnostic that must run before any session exists). Unbound
``sessions takeover`` is legal only because it must bootstrap or select a
concrete caller session before it mutates the target lease; anonymous takeover
is outside the contract.

Subcommands dispatch to focused module CLIs. Brief / video flags fall
through to the ``video_editing.hype`` orchestrator resolved through the
orchestrator registry.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


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
    ("projects", "default"),
    ("sessions", "ls"),
    ("sessions", "takeover"),
    ("packs",),
    ("test",),
    ("doctor",),
)
_SPRINT1_UNBOUND_ALLOWLIST = frozenset(SPRINT1_UNBOUND_ALLOWLIST_CONTRACT)


def main(argv: list[str] | None = None) -> int:
    raw = sys.argv[1:] if argv is None else list(argv)
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
        from .skills import nudge_if_needed

        nudge_if_needed(argv=raw)
    except Exception:
        # Never let the nudge break a real command.
        pass

    # Session gate. Verbs outside the unbound allowlist require a resolvable
    # session record; print the documented hint and exit 2 otherwise.
    if not _verb_is_unbound_allowlisted(raw):
        from .core.session.binding import (
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
                    file=sys.stderr,
                )

            from astrid.core.project.paths import resolve_projects_root

            session = resolve_current_session_with_fs_fallback(
                slug=_slug_hint,
                on_auto_resolve=_nudge,
                projects_root=resolve_projects_root(),
            )
        except SessionBindingError as exc:
            _print_unbound_gate_recovery(f"session: {exc}")
            return 2
        if session is None:
            project_hint = _extract_project_slug(raw)
            attach_hint = (
                f"`astrid attach {project_hint}`"
                if project_hint
                else "`astrid attach <project>`"
            )
            _print_unbound_gate_recovery(
                f"no session bound — run `astrid status` to list projects, then {attach_hint} "
                "(or `astrid attach` if a default project is configured)"
            )
            return 2

    if _verb_bypasses_task_gate(raw):
        return _dispatch(raw)
    project_slug = _extract_project_slug(raw)
    if project_slug is None:
        return _dispatch(raw)

    from .core.task import gate as task_gate

    try:
        decision = task_gate.gate_command(project_slug, task_gate.command_for_argv(raw), raw)
    except task_gate.TaskRunGateError as exc:
        print(f"task-mode gate rejected: {exc.reason}\nrecovery: {exc.recovery}", file=sys.stderr)
        return 1
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
            returncode = _dispatch(raw)
        return returncode
    finally:
        task_gate.record_dispatch_complete(decision, returncode)


def _verb_bypasses_task_gate(raw: list[str]) -> bool:
    first = next(iter(raw), None)
    if first in LIFECYCLE_VERBS:
        return True
    if len(raw) >= 2 and tuple(raw[:2]) in TASK_GATE_READONLY_VERBS:
        return True
    return False


def _verb_is_unbound_allowlisted(raw: list[str]) -> bool:
    """Decide whether the invocation may run without a bound session.

    The final Sprint 1 contract is ``SPRINT1_UNBOUND_ALLOWLIST_CONTRACT``.
    Exact top-level entries match one token; exact subcommand entries match
    their listed prefix. No other discovery, setup, task, RunPod, or builder
    verb is sessionless.
    """

    if not raw:
        return True  # empty argv → entrypoint help

    for allowed in _SPRINT1_UNBOUND_ALLOWLIST:
        if tuple(raw[: len(allowed)]) == allowed:
            return True
    return False


def _print_unbound_gate_recovery(message: str) -> None:
    print("first recovery action: astrid status", file=sys.stderr)
    print(message, file=sys.stderr)


def _dispatch(raw: list[str]) -> int:
    if not raw:
        _print_entrypoint_help()
        return 0

    first, *_ = raw
    if first.startswith("-"):
        return _dispatch_default_brief(raw)
    if first not in _top_level_commands():
        print(f"astrid: unknown command '{first}'", file=sys.stderr)
        raise SystemExit(2)

    parser = _build_dispatch_parser()
    parsed, tail = parser.parse_known_args(raw)
    return int(parsed.handler(tail))


def _top_level_commands() -> frozenset[str]:
    return frozenset(_TOP_LEVEL_HANDLERS)


def _build_dispatch_parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(prog="astrid", add_help=False)
    sub = parser.add_subparsers(dest="command", required=True)
    for command, handler in _TOP_LEVEL_HANDLERS.items():
        command_parser = sub.add_parser(command, add_help=False)
        command_parser.set_defaults(handler=handler)
    return parser


def _dispatch_default_brief(args: list[str]) -> int:
    """Route the legacy explicit brief/video entrypoint through hype."""
    import argparse

    parser = argparse.ArgumentParser(prog="astrid", add_help=False)
    parser.add_argument("--video")
    parser.add_argument("--brief")
    parser.add_argument("--out")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--target-duration")
    try:
        parsed = parser.parse_args(args)
    except SystemExit as exc:
        return int(exc.code or 2)
    if parsed.brief is None:
        parser.error("default brief routing requires --brief")
    return _run_default_brief_from_args(args)


def _run_default_brief_from_args(args: list[str]) -> int:
    return _run_default_brief_orchestrator(args)


def _dispatch_attach(args: list[str]) -> int:
    from .core.session.cli import build_parser, cmd_attach

    parsed = build_parser().parse_args(["attach", *args])
    return int(cmd_attach(parsed))


def _dispatch_status(args: list[str]) -> int:
    # The session-status verb fires when no --project is given; lifecycle
    # status keeps working with --project.
    if "--project" in args or any(arg.startswith("--project=") for arg in args):
        from .core.task.lifecycle import cmd_status

        return cmd_status(args)
    from .core.session.cli import build_parser
    from .core.session.cli import cmd_status as session_status

    status_args = ["status", *[arg for arg in args if arg in {"-h", "--help"}]]
    parsed = build_parser().parse_args(status_args)
    return int(session_status(parsed))


def _dispatch_lifecycle(command: str) -> Any:
    def _handler(args: list[str]) -> int:
        from .core.task import lifecycle

        return int(getattr(lifecycle, command)(args))

    return _handler


def _dispatch_claim(args: list[str]) -> int:
    from .core.task.claim import cmd_claim

    return cmd_claim(args)


def _dispatch_unclaim(args: list[str]) -> int:
    from .core.task.claim import cmd_unclaim

    return cmd_unclaim(args)


def _dispatch_publish(args: list[str]) -> int:
    return _dispatch_executor_main("reigh.publish", args)


def _dispatch_publish_youtube(args: list[str]) -> int:
    return _dispatch_executor_main("youtube.upload", args)


def _dispatch_skills(args: list[str]) -> int:
    from .skills import cli as skills_cli

    return skills_cli.main(args)


def _dispatch_packs(args: list[str]) -> int:
    from .packs import cli as packs_cli

    return packs_cli.main(args)


def _dispatch_executors(args: list[str]) -> int:
    from .core.executor import cli as executors_cli

    return executors_cli.main(args)


def _dispatch_orchestrators(args: list[str]) -> int:
    from .core.orchestrator import cli as orchestrators_cli

    return orchestrators_cli.main(args)


def _dispatch_author(args: list[str]) -> int:
    from .orchestrate import cli as author_cli

    return author_cli.main(args)


def _dispatch_models(args: list[str]) -> int:
    from .core.model_catalog import cli as models_cli

    return models_cli.main(args)


def _dispatch_elements(args: list[str]) -> int:
    from .core.element import cli as elements_cli

    return elements_cli.main(args)


def _dispatch_projects(args: list[str]) -> int:
    # TODO(Sprint 5b): astrid projects timeline is a legacy reigh-app
    # subcommand that collides with the Sprint 2 timeline concept.
    from .core.project import cli as projects_cli

    return projects_cli.main(args)


def _dispatch_timelines(args: list[str]) -> int:
    from .core.timeline import cli as timelines_cli

    return timelines_cli.main(args)


def _dispatch_modalities(args: list[str]) -> int:
    from . import modalities

    return modalities.main(args)


def _dispatch_doctor(args: list[str]) -> int:
    from . import doctor

    return doctor.main(args)


def _dispatch_setup(args: list[str]) -> int:
    from . import setup_cli

    return setup_cli.main(args)


def _dispatch_audit(args: list[str]) -> int:
    from . import audit

    return audit.main(args)


def _dispatch_reigh_data(args: list[str]) -> int:
    return _dispatch_executor_main("reigh.reigh_data", args)


def _dispatch_executor_main(executor_id: str, args: list[str]) -> int:
    from .core.executor.registry import load_default_registry
    from .core.pack_resolver import resolve_callable_from_metadata

    executor = load_default_registry().get(executor_id)
    entrypoint = resolve_callable_from_metadata(executor.metadata, owner_id=executor.id)
    return int(entrypoint(args))


def _dispatch_worker(args: list[str]) -> int:
    from .core.worker import banodoco_worker

    return banodoco_worker.main(args)


def _dispatch_test(args: list[str]) -> int:
    """Run the CI check suite via the hermetic bash script (SD2).

    Resolves ``scripts/reshape/run_ci_checks.sh`` relative to the Astrid
    repo root and forwards all trailing arguments (e.g. ``--changed``,
    ``--json``) through to the script via ``subprocess.run``.
    """
    _REPO_ROOT = Path(__file__).resolve().parent.parent
    _CI_SCRIPT = _REPO_ROOT / "scripts" / "reshape" / "run_ci_checks.sh"
    result = subprocess.run([str(_CI_SCRIPT)] + args)
    return result.returncode


_TOP_LEVEL_HANDLERS = {
    "attach": _dispatch_attach,
    "sessions": lambda args: _dispatch_sessions(args),
    "start": _dispatch_lifecycle("cmd_start"),
    "next": _dispatch_lifecycle("cmd_next"),
    "ack": _dispatch_lifecycle("cmd_ack"),
    "skip": _dispatch_lifecycle("cmd_skip"),
    "abort": _dispatch_lifecycle("cmd_abort"),
    "status": _dispatch_status,
    "runs": lambda args: _dispatch_runs(args),
    "run": lambda args: _dispatch_run(args),
    "step": lambda args: _dispatch_step(args),
    "hook": lambda args: _dispatch_hook(args),
    "plan": lambda args: _dispatch_plan_verbs(args),
    "claim": _dispatch_claim,
    "unclaim": _dispatch_unclaim,
    "publish": _dispatch_publish,
    "publish-youtube": _dispatch_publish_youtube,
    "upload-youtube": _dispatch_publish_youtube,
    "skills": _dispatch_skills,
    "packs": _dispatch_packs,
    "executors": _dispatch_executors,
    "orchestrators": _dispatch_orchestrators,
    "author": _dispatch_author,
    "models": _dispatch_models,
    "elements": _dispatch_elements,
    "projects": _dispatch_projects,
    "timelines": _dispatch_timelines,
    "modalities": _dispatch_modalities,
    "runpod": lambda args: _dispatch_runpod(args),
    "doctor": _dispatch_doctor,
    "setup": _dispatch_setup,
    "audit": _dispatch_audit,
    "events": lambda args: _dispatch_events(args),
    "reigh-data": _dispatch_reigh_data,
    "worker": _dispatch_worker,
    "test": _dispatch_test,
}


def _dispatch_sessions(args: list[str]) -> int:
    from .core.session.cli import (
        build_parser,
        cmd_sessions_detach,
        cmd_sessions_ls,
        cmd_sessions_takeover,
    )

    parser = build_parser()
    try:
        parsed = parser.parse_args(args)
    except SystemExit as exc:
        return int(exc.code or 2)
    if parsed.command == "ls":
        return int(cmd_sessions_ls(parsed))
    if parsed.command == "detach":
        return int(cmd_sessions_detach(parsed))
    if parsed.command == "takeover":
        return int(cmd_sessions_takeover(parsed))
    parser.error("expected one of ls / detach / takeover")
    return 2


def _dispatch_runs(args: list[str]) -> int:
    import argparse

    from .core.task.lifecycle import cmd_runs_ls

    parser = argparse.ArgumentParser(prog="astrid runs")
    sub = parser.add_subparsers(dest="command", required=True)
    ls = sub.add_parser("ls")
    ls.set_defaults(handler=lambda tail: cmd_runs_ls(tail))
    parsed, tail = parser.parse_known_args(args)
    return int(parsed.handler(tail))


def _dispatch_run(args: list[str]) -> int:
    """Dispatch ``astrid run {show,artifacts,trace,cost}`` sub-verbs."""
    import argparse

    from astrid.core.task.run_audit import (
        cmd_run_artifacts,
        cmd_run_cost,
        cmd_run_show,
        cmd_run_trace,
    )

    parser = argparse.ArgumentParser(prog="astrid run")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show").set_defaults(handler=cmd_run_show)
    sub.add_parser("artifacts").set_defaults(handler=cmd_run_artifacts)
    sub.add_parser("trace").set_defaults(handler=cmd_run_trace)
    sub.add_parser("cost").set_defaults(handler=cmd_run_cost)
    parsed, tail = parser.parse_known_args(args)
    return int(parsed.handler(tail))


def _dispatch_step(args: list[str]) -> int:
    """Dispatch ``astrid step {retry-fetch}`` sub-verbs."""
    import argparse

    from astrid.core.task.lifecycle import cmd_step_retry_fetch

    parser = argparse.ArgumentParser(prog="astrid step")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("retry-fetch").set_defaults(handler=cmd_step_retry_fetch)
    parsed, tail = parser.parse_known_args(args)
    return int(parsed.handler(tail))


def _dispatch_hook(args: list[str]) -> int:
    import argparse

    from .core.task.hook import cmd_hook_stop

    parser = argparse.ArgumentParser(prog="astrid hook")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("stop").set_defaults(handler=cmd_hook_stop)
    parsed, tail = parser.parse_known_args(args)
    return int(parsed.handler(tail))


def _dispatch_plan_verbs(args: list[str]) -> int:
    """Delegate plan sub-verbs to plan_verbs.cmd_plan (T8/T17)."""
    from .core.task.plan_verbs import cmd_plan

    return cmd_plan(args)


def _dispatch_events(args: list[str]) -> int:
    """Dispatch ``astrid events {verify,tail}`` top-level verbs (Sprint 5b).

    Both verbs read run state (events.jsonl) and require ASTRID_SESSION_ID.
    They are NOT listed in ``_verb_is_unbound_allowlisted``.
    """
    import argparse

    from astrid.core.task.run_audit import cmd_events_verify, cmd_events_tail

    parser = argparse.ArgumentParser(prog="astrid events")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify").set_defaults(handler=cmd_events_verify)
    sub.add_parser("tail").set_defaults(handler=cmd_events_tail)
    parsed, tail = parser.parse_known_args(args)
    return int(parsed.handler(tail))


def _dispatch_runpod(args: list[str]) -> int:
    """Dispatch ``astrid runpod {sweep,volumes,ensure-storage} ...`` sub-verbs."""
    import argparse

    parser = argparse.ArgumentParser(prog="astrid runpod")
    sub = parser.add_subparsers(dest="command", required=True)
    sweep = sub.add_parser("sweep")
    sweep.add_argument("--hard", action="store_true")
    sweep.add_argument("--dry-run", action="store_true")
    sweep.add_argument("--projects-root")
    sweep.set_defaults(handler=_dispatch_runpod_sweep)
    sub.add_parser("volumes").set_defaults(handler=_dispatch_runpod_volumes)
    ensure = sub.add_parser("ensure-storage")
    ensure.set_defaults(handler=_dispatch_runpod_ensure_storage)
    parsed, tail = parser.parse_known_args(args)
    return int(parsed.handler(parsed, tail))


def _dispatch_runpod_sweep(parsed: Any, _tail: list[str]) -> int:
    from pathlib import Path
    from typing import Literal

    from .core.project.paths import resolve_projects_root
    from .core.runpod.sweeper import sweep as run_sweep

    mode: Literal["default", "hard"] = "hard" if parsed.hard else "default"
    projects_root = (
        Path(parsed.projects_root) if parsed.projects_root else resolve_projects_root()
    )
    summary = run_sweep(projects_root, mode=mode, dry_run=parsed.dry_run)
    print(json.dumps(summary, indent=2, default=str))
    return 0


def _dispatch_runpod_volumes(_parsed: Any, args: list[str]) -> int:
    """Dispatch ``astrid runpod volumes ls``."""
    import argparse

    parser = argparse.ArgumentParser(prog="astrid runpod volumes")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ls", help="List RunPod network volumes as JSON.")
    try:
        parsed = parser.parse_args(args)
    except SystemExit:
        return 2
    if parsed.command != "ls":
        print("usage: astrid runpod volumes ls", file=sys.stderr)
        return 2

    from .core.runpod.storage import list_volumes

    try:

        async def _volumes_ls() -> None:
            volumes = await list_volumes()
            print(json.dumps(volumes, indent=2, default=str))

        import asyncio

        asyncio.run(_volumes_ls())
        return 0
    except Exception as exc:
        print(f"runpod volumes ls: {exc}", file=sys.stderr)
        return 1


def _dispatch_runpod_ensure_storage(_parsed: Any, args: list[str]) -> int:
    """Dispatch ``astrid runpod ensure-storage <name> [--size <GB>] [--datacenter <id>]``."""
    import argparse

    parser = argparse.ArgumentParser(prog="astrid runpod ensure-storage")
    parser.add_argument("name", help="Volume name to find or create.")
    parser.add_argument("--size", type=int, default=50, help="Size in GB for new volumes (default: 50).")
    parser.add_argument("--datacenter", "--datacenter-id", dest="datacenter_id", default=None, help="RunPod datacenter ID.")
    try:
        parsed = parser.parse_args(args)
    except SystemExit:
        return 2

    from .core.runpod.storage import ensure_storage

    try:

        async def _ensure() -> None:
            result = await ensure_storage(
                parsed.name,
                size_gb=parsed.size,
                datacenter_id=parsed.datacenter_id,
            )
            print(json.dumps(result, indent=2, default=str))

        import asyncio

        asyncio.run(_ensure())
        return 0
    except Exception as exc:
        print(f"ensure-storage: {exc}", file=sys.stderr)
        return 1


def _wait_adapter(decision: Any) -> int:
    """Wait for an adapter-dispatched step to complete. Returns a returncode.

    For local adapter: poll the subprocess until it exits, capture returncode.
    For manual adapter: the agent does work out-of-band; return 0 immediately.
    For remote-artifact adapter: wait for the generic subprocess wrapper.
    """
    adapter_kind = getattr(decision, "adapter", None)
    if adapter_kind == "local":
        return _wait_local_subprocess(decision)
    if adapter_kind == "manual":
        # Manual steps: dispatch payload already written; agent works out-of-band.
        # Completion arrives via ack or inbox — not a subprocess exit code.
        return 0
    if adapter_kind == "remote-artifact":
        return _wait_remote_artifact(decision)
    # Legacy / unknown: fall through to 0 (adapter handles it in record_dispatch_complete).
    return 0


def _wait_local_subprocess(decision: Any) -> int:
    """Block until the local-adapter subprocess exits. Return its exit code."""
    import os
    import time

    pid = getattr(decision, "pid", None)
    if pid is None:
        return -1
    try:
        while True:
            try:
                wpid, status = os.waitpid(pid, os.WNOHANG)
                if wpid == pid:
                    if os.WIFEXITED(status):
                        return os.WEXITSTATUS(status)
                    if os.WIFSIGNALED(status):
                        return -abs(os.WTERMSIG(status))
                    return -1
            except ChildProcessError:
                # Already reaped — check returncode sidecar.
                return _read_returncode_sidecar(decision)
            except ProcessLookupError:
                return _read_returncode_sidecar(decision)
            time.sleep(0.1)
    except KeyboardInterrupt:
        # Forward the interrupt to the child but don't crash.
        try:
            os.kill(pid, 2)  # SIGINT
        except OSError:
            pass
        return -1


def _wait_remote_artifact(decision: Any) -> int:
    """Block until the generic remote-artifact subprocess exits."""
    return _wait_local_subprocess(decision)


def _make_run_ctx_for_poll(
    project_root: Any, run_id: Any, path_tuple: Any, step_version: Any
) -> Any:
    """Build a minimal RunContext for adapter.poll() calls."""
    from astrid.core.adapter import RunContext

    return RunContext(
        slug="",
        run_id=str(run_id),
        project_root=Path(project_root) if not isinstance(project_root, Path) else project_root,
        plan_step_path=tuple(path_tuple),
        step_version=int(step_version),
    )


def _read_returncode_sidecar(decision: Any) -> int:
    """If the subprocess pid is gone, try to read the returncode sidecar file."""
    from pathlib import Path

    project_root = getattr(decision, "project_root", None)
    run_id = getattr(decision, "run_id", None)
    path_tuple = getattr(decision, "plan_step_path", ())
    step_version = getattr(decision, "step_version", 1)
    if not project_root or not run_id or not path_tuple:
        return -1
    step_dir = project_root / "runs" / run_id / "steps"
    for seg in path_tuple:
        step_dir = step_dir / seg
    step_dir = step_dir / f"v{step_version}"
    rc_path = step_dir / "returncode"
    if rc_path.exists():
        try:
            return int(rc_path.read_text().strip())
        except (ValueError, OSError):
            pass
    return -1


def _extract_project_slug(raw: list[str]) -> str | None:
    for index, token in enumerate(raw):
        if token == "--project":
            return raw[index + 1] if index + 1 < len(raw) else None
        if token.startswith("--project="):
            value = token.split("=", 1)[1]
            return value or None
    return None


def _run_default_brief_orchestrator(argv: list[str]) -> int:
    from importlib import import_module

    from .core.orchestrator.registry import load_default_registry

    registry = load_default_registry()
    orchestrator = registry.get("video_editing.hype")
    runtime_module = orchestrator.metadata.get("runtime_module")
    runtime_entrypoint = orchestrator.metadata.get("runtime_entrypoint", "main")
    if not isinstance(runtime_module, str) or not runtime_module:
        raise RuntimeError("video_editing.hype manifest is missing metadata.runtime_module")
    module = import_module(runtime_module)
    entrypoint = getattr(module, runtime_entrypoint)
    return int(entrypoint(argv))


def _packs_subcommand_list() -> str:
    """Return a comma-separated list of ``astrid packs`` subcommands."""
    try:
        import argparse

        from .packs.cli import build_parser as packs_build_parser

        packs_parser = packs_build_parser()
        # Extract subcommand names from the parser's subparsers action.
        for action in packs_parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                return ",".join(sorted(action.choices.keys()))
    except Exception:
        pass
    # Fallback: canonical list matching the packs CLI as of m5b.
    return "agent-index,install,inspect,list,new,rollback,status,uninstall,update,validate"


def _print_entrypoint_help() -> None:
    packs_verbs = _packs_subcommand_list()
    print(
        f"""Astrid command gateway

Usage:
  python3 -m astrid doctor
  python3 -m astrid setup [--apply]

Start here:
  python3 -m astrid next
  python3 -m astrid status
  python3 -m astrid attach [<project>]  # only when next/status tells you to bind

    # orchestrators — multi-step pipelines
  python3 -m astrid orchestrators {{list,inspect,validate,fork,run}} ...
    # authoring -- create and compile new tools
  python3 -m astrid author {{new,check,describe,compile,test,explain}} <pack>.<name>
    # task-mode -- lifecycle verbs for running orchestrated plans
  Task-mode operator verbs:
    python3 -m astrid start <pack>.<name> --project <slug> [--name <run-id>]
    python3 -m astrid abort --project <slug>
    python3 -m astrid status --project <slug>
    python3 -m astrid runs ls [--project <slug>]
  Plan-mutation verbs (Sprint 3):
    python3 -m astrid plan add-step --project <slug> --run-id <id> --step-id <id> --command '...' [--adapter local|manual] [--after|--before|--into <path>]
    python3 -m astrid plan edit-step <path> --project <slug> --run-id <id> [--command '...'] [--assignee ...]
    python3 -m astrid plan remove-step <path> --project <slug> --run-id <id>
    python3 -m astrid plan supersede-step <path> --project <slug> --run-id <id> --scope {{all,future-iterations,future-items}}
    python3 -m astrid claim <step> --project <slug> --run-id <id> [--for agent:<id>|human:<name>]
    python3 -m astrid unclaim <step> --project <slug> --run-id <id> [--for agent:<id>|human:<name>]
  Task-mode agent-facing verbs (mid-run):
    python3 -m astrid next --project <slug>
    python3 -m astrid ack <step> --project <slug> --decision {{approve,retry,iterate,abort}} [--agent <id> | --human <name>] [--evidence path] [--feedback "..."] [--item id]
    python3 -m astrid hook stop   # Claude Code Stop-hook entry point; see docs/HOOKS.md
    python3 -m astrid skip   # skip a step (use --help for details)
    # sessions -- tab binding and takeover
  Session verbs (Sprint 1):
    python3 -m astrid attach [<project>] [--default] [--timeline <slug>] [--session <id>] [--as agent:<id>]
    python3 -m astrid status
    python3 -m astrid sessions {{ls,detach,takeover}} ...
    # skills -- installable agent capabilities
  python3 -m astrid skills {{list,install,uninstall,sync,doctor}} ...
    # packs -- build and validate packs
  python3 -m astrid packs {{{packs_verbs}}} ...
    # executors — single-step CLI tools
  python3 -m astrid executors {{new,list,inspect,validate,fork,install,run}} ...
    # elements — reusable building blocks
  python3 -m astrid elements {{list,inspect,fork,install}} ...
    # projects — project CRUD
  python3 -m astrid projects {{ls,default,create,show,source}} ...
    # timelines -- timeline management
  python3 -m astrid timelines {{ls,create,show,rename,finalize,tombstone,purge,set-default}} ...
    # models -- model catalog discovery
  python3 -m astrid models {{list,show}} ...
    # modalities -- output modality discovery
  python3 -m astrid modalities {{list,inspect}} ...
  python3 -m astrid reigh-data --project-id PROJECT_ID [--out PATH]
  python3 -m astrid worker --pool banodoco [--worker-id ID] [--max-iterations N]
    # run-audit -- inspect completed runs
  python3 -m astrid events {{verify,tail}} --run <id> --project <slug>
  python3 -m astrid audit --run RUN_DIR
    # infrastructure -- setup, events, worker, runpod
  python3 -m astrid runpod sweep [--hard] [--dry-run] [--projects-root PATH]
  python3 -m astrid runpod volumes ls
  python3 -m astrid runpod ensure-storage <name> [--size <GB>] [--datacenter <id>]
    # publish / reigh-data (executor-backed)
  python3 -m astrid publish ...
  python3 -m astrid publish-youtube ...
  python3 -m astrid upload-youtube ...
  python3 -m astrid --video SRC --brief BRIEF --out out/runs/name [--render]
  python3 -m astrid --brief BRIEF --out out/runs/name --target-duration SECONDS [--render]
Build a new pack:
  python3 -m astrid packs new <id>
  python3 -m astrid executors new <pack>.<slug>
  python3 -m astrid orchestrators new <pack>.<slug>
  python3 -m astrid packs validate <path>

Browse available tools:
  python3 -m astrid orchestrators list
  python3 -m astrid executors list
  python3 -m astrid elements list
  python3 -m astrid projects show --project PROJECT
  python3 -m astrid modalities list

Inspect before running:
  python3 -m astrid orchestrators inspect video_editing.hype --json
  python3 -m astrid executors inspect rendering.render --json
  python3 -m astrid elements inspect effects text-card --json
  python3 -m astrid modalities inspect generic_card --json

Run any tool through this gateway:
  python3 -m astrid orchestrators run ORCHESTRATOR_ID ...
  python3 -m astrid executors run EXECUTOR_ID ...

Notes:
  python3 -m astrid is the package entry point.
  Use orchestrators for workflows, executors for concrete work, and elements for render building blocks.
"""
    )


if __name__ == "__main__":
    raise SystemExit(main())
