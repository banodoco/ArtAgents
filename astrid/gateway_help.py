"""Entrypoint help rendering for the Astrid gateway.

Extracted from ``astrid/gateway.py`` during M4 batch 41 (T42) to keep the
gateway facade focused while preserving the help-printing entrypoints that
callers and monkeypatch seams rely on via ``astrid.gateway._print_entrypoint_help``
and ``astrid.gateway._packs_subcommand_list``.
"""

from __future__ import annotations


def _packs_subcommand_list() -> str:
    """Return a comma-separated list of ``astrid packs`` subcommands."""
    try:
        import argparse

        from .core.pack.cli import build_parser as packs_build_parser

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
        f"""Astrid command gateway — Python SDK + CLI

The canonical Python boundary is ``import astrid`` (see docs/sdk.md).
This gateway is the CLI entry point for orchestration, authoring, and task management.

Usage:
  python3 -m astrid doctor
  python3 -m astrid setup [--apply]

Start here:
  python3 -m astrid next
  python3 -m astrid status
  python3 -m astrid attach [<project>]  # only when next/status tells you to bind

    # orchestrators — multi-step pipelines
  python3 -m astrid orchestrators {{list,inspect,validate,fork,run}} ...
    # orchestrate — create and compile new orchestration tools
  python3 -m astrid orchestrate {{new,check,describe,compile,test,explain}} <pack>.<name>
    # task-mode — lifecycle verbs for running orchestrated plans
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
  python3 -m astrid projects {{ls,default,create,show,theme,source}} ...
  python3 -m astrid themes ls
    # timelines -- timeline management
  python3 -m astrid timelines {{ls,create,show,rename,finalize,tombstone,purge,set-default}} ...
    # models -- model catalog discovery
  python3 -m astrid models {{list,show}} ...
    # modalities -- output modality discovery
  python3 -m astrid modalities {{list,inspect}} ...
  python3 -m astrid reigh-data --project-id PROJECT_ID [--out PATH]
  python3 -m astrid worker --pool banodoco [--worker-id ID] [--max-iterations N]
    # run-audit — inspect completed runs
  python3 -m astrid runs {{ls,show,artifacts,trace,cost}} ...
  python3 -m astrid events {{verify,tail}} --run <id> --project <slug>
  python3 -m astrid audit --run RUN_DIR
    # infrastructure — setup, events, worker, runpod
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

Recent renames (both old forms still work):
  astrid author → astrid orchestrate   (preferred: ``astrid orchestrate``)
  astrid run {{show,...}} → astrid runs {{ls,show,artifacts,trace,cost}}  (preferred: ``astrid runs``)
  ``astrid author`` and ``astrid run`` are deprecated aliases. Migration is cosmetic — old invocations are accepted.
"""
    )
