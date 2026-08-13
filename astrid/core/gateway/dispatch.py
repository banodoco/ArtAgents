"""Focused dispatch-table and parser helpers for the Astrid gateway."""

from __future__ import annotations

from importlib import import_module
import logging
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from astrid.core.cli import session as _session_cli
from astrid.core.contracts.errors import AstridError

_ALIAS_SUNSET_VERSION = "0.3.0"
_LIFECYCLE_ENGINES = frozenset({"task", "arnold"})
_RELEASE_ID = "release-n"

_logger = logging.getLogger(__name__)


def _dispatch(raw: list[str]) -> int:
    from . import _print_entrypoint_help

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
    from . import _run_default_brief_orchestrator

    return _run_default_brief_orchestrator(args)


def _dispatch_attach(args: list[str]) -> int:
    parsed = _session_cli.build_parser().parse_args(["attach", *args])
    return int(_session_cli.cmd_attach(parsed))


def _dispatch_status(args: list[str]) -> int:
    # The session-status verb fires when no --project is given; lifecycle
    # status keeps working with --project.
    if "--project" in args or any(arg.startswith("--project=") for arg in args):
        engine, stripped_args = _extract_lifecycle_engine(args)
        if engine == "arnold":
            arnold_cli = _load_arnold_host_cli()
            return int(arnold_cli.cmd_status(stripped_args))
        from astrid.core.task.lifecycle import cmd_status

        return cmd_status(stripped_args)
    status_args = ["status", *[arg for arg in args if arg in {"-h", "--help", "--json"}]]
    parsed = _session_cli.build_parser().parse_args(status_args)
    return int(_session_cli.cmd_status(parsed))


def _extract_lifecycle_engine(
    args: list[str],
    *,
    default_engine: str = "task",
) -> tuple[str, list[str]]:
    engine = default_engine
    stripped: list[str] = []
    index = 0

    while index < len(args):
        arg = args[index]
        if arg == "--engine":
            if index + 1 >= len(args):
                raise AstridError(
                    "missing value for '--engine'",
                    valid_options=sorted(_LIFECYCLE_ENGINES),
                    recovery_command="astrid <verb> --engine task|arnold ...",
                    state_snapshot={"args": args},
                )
            candidate = args[index + 1]
            index += 2
        elif arg.startswith("--engine="):
            candidate = arg.partition("=")[2]
            index += 1
        else:
            stripped.append(arg)
            index += 1
            continue

        if candidate not in _LIFECYCLE_ENGINES:
            raise AstridError(
                f"unknown lifecycle engine '{candidate}'",
                valid_options=sorted(_LIFECYCLE_ENGINES),
                recovery_command="astrid <verb> --engine task|arnold ...",
                state_snapshot={"args": args, "engine": candidate},
            )
        engine = candidate

    return engine, stripped


def _emit_fallback_engine_task_warning(
    verb: str,
    stripped_args: list[str],
) -> None:
    project = _extract_project_from_args(stripped_args)
    _logger.warning(
        "FALLBACK_ENGINE_TASK verb=%s project=%s argv=%s release=%s",
        verb,
        project,
        stripped_args,
        _RELEASE_ID,
    )


def _extract_project_from_args(args: list[str]) -> str | None:
    """Extract --project value from stripped args, or None."""
    for i, arg in enumerate(args):
        if arg == "--project" and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith("--project="):
            return arg.partition("=")[2]
    return None


def _load_arnold_host_cli() -> Any:
    return import_module("astrid.core.integrations.arnold.host.cli")


def _dispatch_lifecycle(command: str) -> Any:
    def _handler(args: list[str]) -> int:
        default_engine = "arnold" if command in {"cmd_start", "cmd_next", "cmd_ack", "cmd_abort"} else "task"
        engine, stripped_args = _extract_lifecycle_engine(
            args,
            default_engine=default_engine,
        )
        if engine == "task" and default_engine == "arnold":
            _emit_fallback_engine_task_warning(command, stripped_args)
        if engine == "arnold":
            if command == "cmd_skip":
                raise AstridError(
                    "'astrid skip' does not support '--engine arnold'",
                    valid_options=["task"],
                    recovery_command="astrid skip --reason recover",
                    state_snapshot={"args": args, "command": command},
                )
            arnold_cli = _load_arnold_host_cli()
            return int(getattr(arnold_cli, command)(stripped_args))
        from astrid.core.task import lifecycle

        return int(getattr(lifecycle, command)(stripped_args))

    return _handler


def _dispatch_claim(args: list[str]) -> int:
    """Dispatch ``astrid claim`` (task-only verb)."""
    engine, stripped_args = _extract_lifecycle_engine(args, default_engine="task")
    if engine == "arnold":
        _reject_arnold_for_task_only_verb("claim", args)
    _emit_task_only_verb_deprecated_warning("claim", stripped_args)

    from astrid.core.task.claim import cmd_claim

    return cmd_claim(stripped_args)


def _dispatch_unclaim(args: list[str]) -> int:
    """Dispatch ``astrid unclaim`` (task-only verb)."""
    engine, stripped_args = _extract_lifecycle_engine(args, default_engine="task")
    if engine == "arnold":
        _reject_arnold_for_task_only_verb("unclaim", args)
    _emit_task_only_verb_deprecated_warning("unclaim", stripped_args)

    from astrid.core.task.claim import cmd_unclaim

    return cmd_unclaim(stripped_args)


def _dispatch_publish(args: list[str]) -> int:
    return _dispatch_executor_main("reigh.publish", args)


def _dispatch_publish_youtube(args: list[str]) -> int:
    return _dispatch_executor_main("youtube.upload", args)


def _dispatch_skills(args: list[str]) -> int:
    from astrid.skills import cli as skills_cli

    return skills_cli.main(args)


def _dispatch_packs(args: list[str]) -> int:
    from astrid.core.pack import cli as packs_cli

    return packs_cli.main(args)


def _dispatch_executors(args: list[str]) -> int:
    from astrid.core.execution.executor import cli as executors_cli

    return executors_cli.main(args)


def _dispatch_orchestrators(args: list[str]) -> int:
    from astrid.core.execution.orchestrator import cli as orchestrators_cli

    return orchestrators_cli.main(args)


def _dispatch_orchestrate(args: list[str]) -> int:
    from astrid.core.orchestrate import cli as author_cli

    return author_cli.main(args)


def _dispatch_author(args: list[str]) -> int:
    _warn_deprecated_alias(alias="author", replacement="orchestrate")
    return _dispatch_orchestrate(args)


def _warn_deprecated_alias(*, alias: str, replacement: str) -> None:
    print(
        f"warning: 'astrid {alias}' is deprecated; use 'astrid {replacement}' "
        f"instead. The alias is scheduled for removal in {_ALIAS_SUNSET_VERSION}.",
        file=sys.stderr,
    )


def _dispatch_models(args: list[str]) -> int:
    from astrid.core.model_catalog import cli as models_cli

    return models_cli.main(args)


def _dispatch_elements(args: list[str]) -> int:
    from astrid.core.element import cli as elements_cli

    return elements_cli.main(args)


def _dispatch_projects(args: list[str]) -> int:
    # TODO(Sprint 5b): astrid projects timeline is a legacy reigh-app
    # subcommand that collides with the Sprint 2 timeline concept.
    from astrid.core.cli import project as projects_cli

    return projects_cli.main(args)


def _dispatch_themes(args: list[str]) -> int:
    from astrid.core.theme import cli

    return cli.main(args)


def _dispatch_timelines(args: list[str]) -> int:
    from astrid.core.cli import timeline as timelines_cli

    return timelines_cli.main(args)


def _dispatch_modalities(args: list[str]) -> int:
    from astrid.core import modalities

    return modalities.main(args)


def _dispatch_renderers(args: list[str]) -> int:
    from astrid.core.rendering import cli as renderers_cli

    return renderers_cli.main(args)


def _dispatch_replay(args: list[str]) -> int:
    """Dispatch ``astrid replay <bundle-dir>`` to the renderer CLI replay verb."""
    from astrid.core.rendering import cli as renderers_cli

    return renderers_cli.main(["replay", *args])


def _dispatch_doctor(args: list[str]) -> int:
    from astrid.core import doctor

    return doctor.main(args)


def _dispatch_setup(args: list[str]) -> int:
    from .setup import main as setup_main

    return setup_main(args)


def _dispatch_audit(args: list[str]) -> int:
    from astrid import audit

    return audit.main(args)


def _dispatch_reigh_data(args: list[str]) -> int:
    return _dispatch_executor_main("reigh.reigh_data", args)


def _dispatch_executor_main(executor_id: str, args: list[str]) -> int:
    from astrid.core.execution.executor.registry import load_default_registry
    from astrid.core.pack.resolver import resolve_callable_from_metadata

    executor = load_default_registry().get(executor_id)
    entrypoint = resolve_callable_from_metadata(executor.metadata, owner_id=executor.id)
    return int(entrypoint(args))


def _dispatch_worker(args: list[str]) -> int:
    from astrid.core.integrations.worker import banodoco_worker

    return banodoco_worker.main(args)


def _dispatch_test(args: list[str]) -> int:
    """Run the CI check suite via the hermetic bash script (SD2)."""
    _REPO_ROOT = Path(__file__).resolve().parent.parent
    _CI_SCRIPT = _REPO_ROOT / "scripts" / "reshape" / "run_ci_checks.sh"
    result = subprocess.run([str(_CI_SCRIPT)] + args)
    return result.returncode


def _dispatch_scratch(args: list[str]) -> int:
    """Run a throwaway Python script with default project context."""
    from .scratch import dispatch_scratch

    return dispatch_scratch(args)


def _dispatch_serve(args: list[str]) -> int:
    """Start the Astrid local read bridge HTTP server."""
    import argparse

    from astrid.core.integrations.reigh.local_bridge_server import create_local_bridge_server

    parser = argparse.ArgumentParser(prog="astrid serve", description="Start the Astrid local read bridge.")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=0, help="Port to bind (default: 0 = OS-assigned)",
    )
    parser.add_argument(
        "--projects-root", default=None, help="Astrid projects root (default: ASTRID_PROJECTS_ROOT env or ~/astrid-projects)",
    )
    parsed = parser.parse_args(args)

    server = create_local_bridge_server(
        host=parsed.host,
        port=parsed.port,
        projects_root=parsed.projects_root,
    )
    host, port = server.server_address
    print(f"Astrid local bridge listening on http://{host}:{port}")

    def _shutdown(_signum: int, _frame: Any) -> None:
        print("\nShutting down...", flush=True)
        server.shutdown()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


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
    "orchestrate": _dispatch_orchestrate,
    "author": _dispatch_author,
    "models": _dispatch_models,
    "elements": _dispatch_elements,
    "projects": _dispatch_projects,
    "themes": _dispatch_themes,
    "timelines": _dispatch_timelines,
    "modalities": _dispatch_modalities,
    "renderers": _dispatch_renderers,
    "replay": _dispatch_replay,
    "runpod": lambda args: _dispatch_runpod(args),
    "scratch": _dispatch_scratch,
    "doctor": _dispatch_doctor,
    "setup": _dispatch_setup,
    "audit": _dispatch_audit,
    "events": lambda args: _dispatch_events(args),
    "reigh-data": _dispatch_reigh_data,
    "worker": _dispatch_worker,
    "test": _dispatch_test,
    "serve": _dispatch_serve,
}


def _dispatch_sessions(args: list[str]) -> int:
    parser = _session_cli.build_parser()
    try:
        parsed = parser.parse_args(args)
    except SystemExit as exc:
        return int(exc.code or 2)
    if parsed.command == "ls":
        return int(_session_cli.cmd_sessions_ls(parsed))
    if parsed.command == "detach":
        return int(_session_cli.cmd_sessions_detach(parsed))
    if parsed.command == "takeover":
        return int(_session_cli.cmd_sessions_takeover(parsed))
    parser.error("expected one of ls / detach / takeover")
    return 2


def _emit_task_only_verb_deprecated_warning(
    verb: str,
    stripped_args: list[str],
) -> None:
    """Emit TASK_ONLY_VERB_DEPRECATED for hardcoded task-only verbs."""
    # TODO(m5b): remove this compatibility warning after task-only lifecycle
    # verbs finish moving behind explicit engine routing.
    project = _extract_project_from_args(stripped_args)
    _logger.warning(
        "TASK_ONLY_VERB_DEPRECATED verb=%s project=%s argv=%s release=%s",
        verb,
        project,
        stripped_args,
        _RELEASE_ID,
    )


def _reject_arnold_for_task_only_verb(
    verb: str,
    args: list[str],
    *,
    recovery_command: str | None = None,
) -> None:
    """Raise AstridError when ``--engine arnold`` is used with a task-only verb."""
    if recovery_command is None:
        recovery_command = f"astrid {verb} --help"
    raise AstridError(
        f"'astrid {verb}' does not support '--engine arnold'",
        valid_options=["task"],
        recovery_command=recovery_command,
        state_snapshot={"args": args, "verb": verb},
    )


def _dispatch_runs(args: list[str]) -> int:
    """Dispatch ``astrid runs {ls,show,artifacts,trace,cost,gc}`` sub-verbs."""
    import argparse

    engine, stripped_args = _extract_lifecycle_engine(args, default_engine="task")
    if engine == "arnold":
        _reject_arnold_for_task_only_verb("runs", args)
    _emit_task_only_verb_deprecated_warning("runs", stripped_args)

    from astrid.core.task.lifecycle import cmd_runs_ls
    from astrid.core.task.run.audit import (
        cmd_run_artifacts,
        cmd_run_cost,
        cmd_run_show,
        cmd_run_trace,
    )
    from astrid.core.task.run.gc import cmd_runs_gc

    parser = argparse.ArgumentParser(prog="astrid runs")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ls").set_defaults(handler=lambda tail: cmd_runs_ls(tail))
    sub.add_parser("show").set_defaults(handler=cmd_run_show)
    sub.add_parser("artifacts").set_defaults(handler=cmd_run_artifacts)
    sub.add_parser("trace").set_defaults(handler=cmd_run_trace)
    sub.add_parser("cost").set_defaults(handler=cmd_run_cost)
    sub.add_parser("gc").set_defaults(handler=cmd_runs_gc)
    parsed, tail = parser.parse_known_args(stripped_args)
    return int(parsed.handler(tail))


def _dispatch_run(args: list[str]) -> int:
    """Deprecated alias for ``astrid runs``. Delegates to ``_dispatch_runs``."""
    engine, stripped_args = _extract_lifecycle_engine(args, default_engine="task")
    if engine == "arnold":
        _reject_arnold_for_task_only_verb("run", args)
    _warn_deprecated_alias(alias="run", replacement="runs")
    _emit_task_only_verb_deprecated_warning("run", stripped_args)
    return _dispatch_runs(stripped_args)


def _dispatch_step(args: list[str]) -> int:
    """Dispatch ``astrid step {retry-fetch}`` sub-verbs (task-only verb)."""
    import argparse

    engine, stripped_args = _extract_lifecycle_engine(args, default_engine="task")
    if engine == "arnold":
        _reject_arnold_for_task_only_verb("step", args)
    _emit_task_only_verb_deprecated_warning("step", stripped_args)

    from astrid.core.task.lifecycle import cmd_step_retry_fetch

    parser = argparse.ArgumentParser(prog="astrid step")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("retry-fetch").set_defaults(handler=cmd_step_retry_fetch)
    parsed, tail = parser.parse_known_args(stripped_args)
    return int(parsed.handler(tail))


def _dispatch_hook(args: list[str]) -> int:
    """Dispatch ``astrid hook {stop}`` sub-verbs (task-only verb)."""
    import argparse

    engine, stripped_args = _extract_lifecycle_engine(args, default_engine="task")
    if engine == "arnold":
        _reject_arnold_for_task_only_verb("hook", args)
    _emit_task_only_verb_deprecated_warning("hook", stripped_args)

    from astrid.core.task.hook import cmd_hook_stop

    parser = argparse.ArgumentParser(prog="astrid hook")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("stop").set_defaults(handler=cmd_hook_stop)
    parsed, tail = parser.parse_known_args(stripped_args)
    return int(parsed.handler(tail))


def _dispatch_plan_verbs(args: list[str]) -> int:
    """Delegate plan sub-verbs to plan_verbs.cmd_plan (task-only verb)."""
    engine, stripped_args = _extract_lifecycle_engine(args, default_engine="task")
    if engine == "arnold":
        _reject_arnold_for_task_only_verb("plan", args)
    _emit_task_only_verb_deprecated_warning("plan", stripped_args)

    from astrid.core.task.plan.verbs import cmd_plan

    return cmd_plan(stripped_args)


def _dispatch_events(args: list[str]) -> int:
    """Dispatch ``astrid events {verify,tail}`` (task-only verb)."""
    import argparse

    engine, stripped_args = _extract_lifecycle_engine(args, default_engine="task")
    if engine == "arnold":
        _reject_arnold_for_task_only_verb("events", args)
    _emit_task_only_verb_deprecated_warning("events", stripped_args)

    from astrid.core.task.run.audit import cmd_events_tail, cmd_events_verify

    parser = argparse.ArgumentParser(prog="astrid events")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify").set_defaults(handler=cmd_events_verify)
    sub.add_parser("tail").set_defaults(handler=cmd_events_tail)
    parsed, tail = parser.parse_known_args(stripped_args)
    return int(parsed.handler(tail))


def _dispatch_runpod(args: list[str]) -> int:
    """Dispatch ``astrid runpod {sweep,volumes,ensure-storage} ...`` sub-verbs."""
    from .runpod import dispatch_runpod

    return dispatch_runpod(args)


def _dispatch_runpod_sweep(parsed: Any, _tail: list[str]) -> int:
    """Thin delegator to runpod module."""
    from .runpod import dispatch_runpod_sweep

    return dispatch_runpod_sweep(parsed, _tail)


def _dispatch_runpod_volumes(_parsed: Any, args: list[str]) -> int:
    """Thin delegator to runpod module."""
    from .runpod import dispatch_runpod_volumes

    return dispatch_runpod_volumes(_parsed, args)


def _dispatch_runpod_ensure_storage(_parsed: Any, args: list[str]) -> int:
    """Thin delegator to runpod module."""
    from .runpod import dispatch_runpod_ensure_storage

    return dispatch_runpod_ensure_storage(_parsed, args)
