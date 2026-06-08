"""Focused dispatch-table and parser helpers for the Astrid gateway."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from astrid.contracts.errors import AstridError
from astrid.core.runtime.log_capture import (
    open_run_log_capture,
    run_subprocess_with_capture,
)


def _dispatch(raw: list[str]) -> int:
    from .gateway import _print_entrypoint_help

    if not raw:
        _print_entrypoint_help()
        return 0

    first, *_ = raw
    if first.startswith("-"):
        return _dispatch_default_brief(raw)
    if first not in _top_level_commands():
        raise AstridError(
            f"unknown command '{first}'",
            valid_options=sorted(_top_level_commands()),
            recovery_command="astrid --help",
            state_snapshot={"command": first},
        )

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
    from .gateway import _run_default_brief_orchestrator

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

    status_args = ["status", *[arg for arg in args if arg in {"-h", "--help", "--json"}]]
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
    from .core.pack import cli as packs_cli

    return packs_cli.main(args)


def _dispatch_executors(args: list[str]) -> int:
    from .core.executor import cli as executors_cli

    return executors_cli.main(args)


def _dispatch_orchestrators(args: list[str]) -> int:
    from .core.orchestrator import cli as orchestrators_cli

    return orchestrators_cli.main(args)


def _dispatch_orchestrate(args: list[str]) -> int:
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


def _dispatch_themes(args: list[str]) -> int:
    from .core import theme_cli

    return theme_cli.main(args)


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
    """Run the CI check suite via the hermetic bash script (SD2)."""
    _REPO_ROOT = Path(__file__).resolve().parent.parent
    _CI_SCRIPT = _REPO_ROOT / "scripts" / "reshape" / "run_ci_checks.sh"
    result = subprocess.run([str(_CI_SCRIPT)] + args)
    return result.returncode


def _dispatch_scratch(args: list[str]) -> int:
    """Run a throwaway Python script with default project context."""
    import argparse

    from astrid.contracts.run_status import RunStatus
    from astrid.core.project.run import (
        finalize_project_run,
        prepare_project_run,
    )
    from astrid.core.subprocess_env import build_child_subprocess_env

    from .gateway import ASTRID_GATEWAY_RESOLVED_PROJECT_ENV, DEFAULT_PROJECT_SLUG

    parser = argparse.ArgumentParser(prog="astrid scratch")
    sub = parser.add_subparsers(dest="scratch_command")
    run_parser = sub.add_parser("run", help="Run a throwaway Python script")
    run_parser.add_argument("file", help="Python file to run")
    run_parser.add_argument(
        "extra", nargs=argparse.REMAINDER, help="Extra arguments forwarded to the script"
    )

    parsed = parser.parse_args(args)
    if parsed.scratch_command != "run":
        parser.print_help()
        return 1

    file_path = Path(parsed.file)
    if not file_path.is_file():
        print(f"scratch: file not found: {file_path}", file=sys.__stderr__)
        return 1

    project_slug = os.environ.get(ASTRID_GATEWAY_RESOLVED_PROJECT_ENV)
    if not project_slug:
        try:
            from astrid.core.project.paths import resolve_projects_root
            from astrid.core.session.binding import resolve_current_session_with_fs_fallback

            session = resolve_current_session_with_fs_fallback(
                projects_root=resolve_projects_root(),
            )
            if session and getattr(session, "project", None):
                project_slug = session.project
        except Exception:
            pass
    if not project_slug:
        project_slug = DEFAULT_PROJECT_SLUG

    extra = parsed.extra or []
    argv = [str(file_path)] + extra

    context = prepare_project_run(
        project_slug,
        tool_id="scratch.run",
        kind="scratch",
        argv=argv,
        requires_timeline=False,
        auto_bound=True,
        invocation="scratch",
    )

    child_env = build_child_subprocess_env(
        explicit_env={
            "ASTRID_PROJECT_RUN": "1",
        },
    )
    with open_run_log_capture(context.run_root) as logs:
        returncode = run_subprocess_with_capture(
            [sys.executable, str(file_path)] + extra,
            env=child_env,
            stdout_log=logs.stdout,
            stderr_log=logs.stderr,
        )

    status = RunStatus.COMPLETED if returncode == 0 else RunStatus.FAILED
    finalize_project_run(
        context,
        status=status,
        returncode=returncode,
    )

    return returncode


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
    "run": lambda args: _dispatch_runs(args),
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
    "orchestrate": _dispatch_orchestrate,
    "author": _dispatch_orchestrate,
    "models": _dispatch_models,
    "elements": _dispatch_elements,
    "projects": _dispatch_projects,
    "themes": _dispatch_themes,
    "timelines": _dispatch_timelines,
    "modalities": _dispatch_modalities,
    "runpod": lambda args: _dispatch_runpod(args),
    "scratch": _dispatch_scratch,
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
    """Dispatch ``astrid runs {ls,show,artifacts,trace,cost,gc}`` sub-verbs."""
    import argparse

    from astrid.core.task.run_audit import (
        cmd_run_artifacts,
        cmd_run_cost,
        cmd_run_show,
        cmd_run_trace,
    )

    from .core.task.lifecycle import cmd_runs_ls
    from .core.task.run_gc import cmd_runs_gc

    parser = argparse.ArgumentParser(prog="astrid runs")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ls").set_defaults(handler=lambda tail: cmd_runs_ls(tail))
    sub.add_parser("show").set_defaults(handler=cmd_run_show)
    sub.add_parser("artifacts").set_defaults(handler=cmd_run_artifacts)
    sub.add_parser("trace").set_defaults(handler=cmd_run_trace)
    sub.add_parser("cost").set_defaults(handler=cmd_run_cost)
    sub.add_parser("gc").set_defaults(handler=cmd_runs_gc)
    parsed, tail = parser.parse_known_args(args)
    return int(parsed.handler(tail))


def _dispatch_run(args: list[str]) -> int:
    """Deprecated alias for ``astrid runs``. Delegates to ``_dispatch_runs``."""
    return _dispatch_runs(args)


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
    """Dispatch ``astrid events {verify,tail}`` top-level verbs (Sprint 5b)."""
    import argparse

    from astrid.core.task.run_audit import cmd_events_tail, cmd_events_verify

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
        raise AstridError(
            "usage: astrid runpod volumes ls",
            recovery_command="astrid runpod volumes ls",
            state_snapshot={"command": "runpod volumes"},
        )

    from .core.runpod.storage import list_volumes

    try:

        async def _volumes_ls() -> None:
            volumes = await list_volumes()
            print(json.dumps(volumes, indent=2, default=str))

        import asyncio

        asyncio.run(_volumes_ls())
        return 0
    except Exception as exc:
        raise AstridError(
            f"runpod volumes ls failed: {exc}",
            recovery_command="astrid runpod volumes ls",
            state_snapshot={"command": "runpod volumes ls"},
        ) from exc


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
        raise AstridError(
            f"ensure-storage failed: {exc}",
            recovery_command="astrid runpod ensure-storage <name>",
            state_snapshot={"command": "runpod ensure-storage"},
        ) from exc
