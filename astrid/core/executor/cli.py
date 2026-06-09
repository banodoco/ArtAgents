"""Canonical command-line interface for Astrid executors."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any

from astrid.core.contracts.errors import AstridError
from astrid.core.cli_choices import RecoverableArgumentParser, add_choice_arg
from astrid.core.dirty import detect_local_edits
from astrid.core.pack.override import OverrideStore, OverrideStoreError
from astrid.core.project.run import ProjectRunError
from astrid.core.scaffold import (
    TEST_RUN_PY_TEMPLATE as _TEST_RUN_PY_TEMPLATE,
)
from astrid.core.scaffold import (
    scaffold_component as _scaffold_component,
)
from astrid.core.search import (
    SearchRecord,
    short_description_or_truncated,
)
from astrid.core.search import (
    search as run_search,
)
from astrid.core.update import update_apply, update_check

from .registry import ExecutorRegistry, load_default_registry
from .schema import ExecutorDefinition, ExecutorValidationError, to_capability_handle


from astrid.core.contracts._capability_common import (
    _aliases_text,
    _banodoco_config_from_args,
    _eprint,
    _example_path_for_port,
    _format_invocation_hint,
    _gateway_resolved_project,
    _print_invocation_example,
    _print_ports,
    _require_qualified_id,
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(raw_argv)
    setattr(args, "_raw_argv", raw_argv)
    # FLAG-S1-002: 'new' short-circuits BEFORE load_default_registry() so
    # scaffold commands never load the built-in registry or import pack code.
    if getattr(args, "command", None) == "new":
        return int(args.handler(args, registry=None))
    try:
        # SD2: executor CLI defaults to Path.cwd() so forks land in the
        # user's current project, not the source-tree REPO_ROOT.
        project_root = getattr(args, "project_root", None) or Path.cwd()
        # Create OverrideStore so --show-overrides and override set/remove/list work.
        override_store = OverrideStore(project_root=project_root)
        registry = load_default_registry(
            _banodoco_config_from_args(args, agent_flag="banodoco_agent_executors"), project_root=project_root,
            extra_pack_roots=tuple(args.pack_root),
        )
        registry.override_store = override_store
        return int(args.handler(args, registry))
    except (KeyError, ExecutorValidationError, ProjectRunError, ValueError, OverrideStoreError) as exc:
        raise AstridError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = RecoverableArgumentParser(
        prog="python3 -m astrid executors",
        description="List, inspect, validate, install, and run Astrid executors.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--pack-root", action="append", default=[], metavar="PATH", help="Extra pack root directory to discover executors from; may be repeated.")
    parser.add_argument("--banodoco-agent-executors", action="store_true", help="Opt in to loading executors from the Banodoco website catalog.")
    parser.add_argument("--banodoco-catalog-url", help="Banodoco website agent-executor catalog Edge Function URL.")
    parser.add_argument("--banodoco-cache-dir", help="Cache directory for git-backed Banodoco executors.")
    parser.add_argument("--banodoco-refresh", action="store_true", help="Refresh cached git checkouts before loading Banodoco executors.")
    parser.add_argument("--no-banodoco-defaults", action="store_true", help="Skip Banodoco catalog executors marked default.")
    parser.add_argument("--no-banodoco-mandatory", action="store_true", help="Skip Banodoco catalog executors marked mandatory.")
    # SD2: executor/orchestrator CLIs fork to Path.cwd() by default.
    parser.add_argument("--project-root", type=Path, help="Project root for local pack discovery and fork targets. Defaults to current working directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", aliases=["ls"], help="List available executors.")
    list_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    add_choice_arg(
        list_parser,
        "--kind",
        values=("built_in", "external"),
        help="Filter executors by kind.",
    )
    list_parser.add_argument("--pack", help="Filter executors by source pack id.")
    list_parser.add_argument("--no-describe", action="store_true", help="Omit the short_description column for legacy parsers.")
    list_parser.add_argument("--show-overrides", action="store_true", help="Annotate capabilities with active overrides.")
    list_parser.set_defaults(handler=_cmd_list)

    search_parser = subparsers.add_parser("search", help="Search executors by id, keywords, descriptions, and binaries.")
    search_parser.add_argument("terms", nargs="+", help="One or more search terms.")
    search_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    search_parser.add_argument("--limit", type=int, default=25, help="Maximum number of hits (default 25).")
    search_parser.add_argument("--pack", help="Filter executors by source pack id.")
    search_parser.set_defaults(handler=_cmd_search)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect one executor.")
    inspect_parser.add_argument("executor_id")
    inspect_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    inspect_parser.add_argument("--pack", help="Require the resolved executor to belong to this pack id.")
    inspect_parser.add_argument("--show-overrides", action="store_true", help="Show override status for this capability.")
    inspect_parser.set_defaults(handler=_cmd_inspect)

    validate_parser = subparsers.add_parser("validate", help="Validate executor metadata.")
    validate_parser.add_argument("executor_id", nargs="?")
    validate_parser.add_argument("--check-binaries", action="store_true", help="Also require declared external binaries to be on PATH.")
    validate_parser.set_defaults(handler=_cmd_validate)

    install_parser = subparsers.add_parser("install", help="Install dependencies for one executor.")
    install_parser.add_argument("executor_id")
    install_parser.add_argument("--dry-run", action="store_true", help="Print install commands without executing them.")
    install_parser.set_defaults(handler=_cmd_install)

    run_parser = subparsers.add_parser("run", help="Run or dry-run one executor.")
    run_parser.add_argument("executor_id")
    run_parser.add_argument("--out", help="Output directory for runtime placeholders.")
    run_parser.add_argument(
        "--project",
        help=(
            "Project identifier. A project slug runs in cache-only/offline mode "
            "(local sources/ + runs/ provenance). A reigh-app project UUID "
            "(8-4-4-4-12 hex) runs in UUID handoff mode: the executor completes "
            "locally, emits bridge metadata, and does NOT push to Supabase. "
            "Pair with --timeline-id. The actual Supabase push is deferred to m6 "
            "(open_in_reigh bridge replay)."
        ),
    )
    run_parser.add_argument(
        "--timeline-id",
        dest="timeline_id",
        help="reigh-app timeline UUID; required when --project is a reigh-app UUID.",
    )
    run_parser.add_argument(
        "--service-role",
        action="store_true",
        help="Worker-only escape hatch for service-role authenticated operations (Supabase push deferred to m6).",
    )
    run_parser.add_argument("--input", action="append", default=[], metavar="NAME=VALUE", help="Executor input value; may be repeated.")
    run_parser.add_argument("--brief", help="Brief path for built-in pipeline context synthesis.")
    run_parser.add_argument("--dry-run", action="store_true", help="Build and print the command without executing it.")
    run_parser.add_argument("--check-binaries", action="store_true", help="Also require declared external binaries to be on PATH.")
    run_parser.add_argument("--python-exec", help="Python executable for {python_exec} placeholders.")
    run_parser.add_argument("--verbose", action="store_true", help="Stream subprocess output for built-in pipeline steps.")
    run_parser.add_argument("--video-url", "--video", dest="video_url", help="Reachable http(s) video URL.")
    run_parser.add_argument("--title", help="YouTube video title.")
    run_parser.add_argument("--description", help="YouTube video description.")
    run_parser.add_argument("--tag", action="append", default=[], help="YouTube tag. May be repeated.")
    run_parser.add_argument("--tags", action="append", default=[], help="Comma-separated YouTube tags.")
    run_parser.add_argument("--privacy-status", default=None, help="YouTube privacy status: private, unlisted, or public.")
    run_parser.add_argument("--playlist-id", help="Optional YouTube playlist ID.")
    run_parser.add_argument("--made-for-kids", action="store_true", help="Mark the video as made for kids.")
    run_parser.add_argument("--json", action="store_true", help="Suppress the command echo and emit only the JSON payload to stdout.")
    run_parser.set_defaults(handler=_cmd_run)

    new_parser = subparsers.add_parser("new", help="Scaffold a new executor in an existing pack.")
    new_parser.add_argument(
        "qualified_id",
        help="Qualified executor id: <pack>.<slug> (e.g., my_pack.ingest_assets).",
    )
    new_parser.set_defaults(handler=_cmd_new)

    fork_parser = subparsers.add_parser("fork", help="Fork an executor into the local pack (astrid/packs/local).")
    fork_parser.add_argument("executor_id", help="Qualified executor id to fork (e.g., rendering.render).")
    fork_parser.add_argument("--overwrite", action="store_true", help="Replace an existing local fork.")
    fork_parser.add_argument("--deep", action="store_true", help="Also recursively fork all depended-on executors.")
    fork_parser.set_defaults(handler=_cmd_fork)

    # --- Override subcommands ---
    override_parser = subparsers.add_parser("override", help="Manage capability overrides.")
    override_sub = override_parser.add_subparsers(dest="override_action", required=True)

    override_set = override_sub.add_parser("set", help="Set an override: route an executor to a replacement.")
    override_set.add_argument("executor_id")
    override_set.add_argument("target_id", help="Fully-qualified id of the replacement executor.")
    override_set.set_defaults(handler=_cmd_override)

    override_remove = override_sub.add_parser("remove", help="Remove an override.")
    override_remove.add_argument("executor_id")
    override_remove.set_defaults(handler=_cmd_override)

    override_list = override_sub.add_parser("list", help="List all active overrides.")
    override_list.set_defaults(handler=_cmd_override)

    # --- Dirty subcommands ---
    dirty_parser = subparsers.add_parser("dirty", help="Check or list locally-modified (dirty) executors.")
    dirty_sub = dirty_parser.add_subparsers(dest="dirty_action", required=True)

    dirty_check = dirty_sub.add_parser("check", help="Check dirty state for one executor.")
    dirty_check.add_argument("executor_id")
    dirty_check.set_defaults(handler=_cmd_dirty)

    dirty_list = dirty_sub.add_parser("list", help="List all dirty executors.")
    dirty_list.set_defaults(handler=_cmd_dirty)

    # --- Update subcommands ---
    update_parser = subparsers.add_parser("update", help="Check for or apply upstream updates to forked executors.")
    update_sub = update_parser.add_subparsers(dest="update_action", required=True)

    update_check_parser = update_sub.add_parser("check", help="Compare local fork against upstream.")
    update_check_parser.add_argument("executor_id")
    update_check_parser.set_defaults(handler=_cmd_update)

    update_apply_parser = update_sub.add_parser("apply", help="Apply upstream update to a local fork.")
    update_apply_parser.add_argument("executor_id")
    update_apply_parser.add_argument("--force", action="store_true", help="Apply even if safety escalations are detected.")
    update_apply_parser.add_argument("--skip-safety", action="store_true", help="Skip safety escalation checks.")
    update_apply_parser.set_defaults(handler=_cmd_update)

    return parser


def _cmd_fork(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    # SD2: executor CLI forks to Path.cwd() by default so forked executors
    # land in the user's current project, not the source-tree REPO_ROOT.
    project_root = getattr(args, "project_root", None) or Path.cwd()

    # Resolve alias BEFORE fork (watch item): alias → canonical ID,
    # then fork the canonical executor.
    resolver = registry.alias_resolver
    resolved_id = resolver.resolve(args.executor_id) if resolver else args.executor_id

    target = registry.fork(
        resolved_id,
        project_root=project_root,
        overwrite=bool(args.overwrite),
        deep=bool(args.deep),
    )
    print(f"forked: {target}")
    return 0


def _cmd_new(args: argparse.Namespace, registry: Any) -> int:
    """Scaffold a new executor component into an existing pack (CWD-relative).

    Short-circuits before ``load_default_registry()`` — never imports pack code.
    """
    qualified_id: str = args.qualified_id
    return _scaffold_component(
        qualified_id=qualified_id,
        component_type="executor",
        yaml_template=_EXECUTOR_YAML_TEMPLATE,
        run_py_template=_RUN_PY_TEMPLATE,
        extra_files={
            "tests/__init__.py": "",
            "tests/test_run.py": _TEST_RUN_PY_TEMPLATE.format(
                qualified_id=qualified_id,
                component_type="executor",
            ),
        },
    )


# ---------------------------------------------------------------------------
# Scaffold templates (executor-specific; shared helpers live in
# astrid.core.scaffold)
# ---------------------------------------------------------------------------

_EXECUTOR_YAML_TEMPLATE = """\
schema_version: 1
id: {qualified_id}
name: {slug}
kind: built_in
version: 0.1.0
description: "TODO: describe what this executor does."
short_description: "TODO: one-line summary used in `astrid executors list`."
keywords: []

# Declared inputs the runner will substitute into command.argv at dispatch.
# Each input becomes a `{{name}}` placeholder. Add more as needed; common
# types: string, path, integer, number, boolean, json.
inputs:
  - name: input_arg
    type: string
    required: true
    description: "TODO: describe this input."

# Declared outputs the runner expects to find on disk after the command
# completes. {{out}} is the run's output directory (resolved at runtime).
outputs:
  - name: result
    type: file
    path_template: "{{out}}/result.json"

# command.argv runs the runtime as a subprocess. Placeholders in braces are
# substituted from the inputs / outputs / runtime context. {{python_exec}}
# resolves to the interpreter. Task-mode identity is supplied by ASTRID_TASK_*
# environment variables; do not add a local --project flag to --out commands.
command:
  argv:
    - "{{python_exec}}"
    - "-m"
    - "astrid.packs.{pack}.executors.{slug}.run"
    - "--input"
    - "{{input_arg}}"
    - "--out"
    - "{{out}}"
"""

_RUN_PY_TEMPLATE = """\
\"\"\"{qualified_id} — executor runtime entrypoint.

Invoked as a subprocess by the Astrid runtime per the `command.argv`
declared in executor.yaml. Argv parsing is the executor's responsibility;
the runtime supplies the substituted argv (one input at a time as
declared in the manifest's `inputs:` block, plus `--out <run-dir>`).

Implement `main(argv)` to do the work, write artifacts to {{out}}, and
return an integer exit code (0 on success).
\"\"\"

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="{qualified_id}")
    parser.add_argument("--input", required=True, help="TODO: describe this input.")
    parser.add_argument("--out", required=True, help="Output directory.")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # TODO: implement your logic here. Write artifacts under out_dir.
    # Example: (out_dir / "result.json").write_text('{{"input": "{{}}"}}'.format(args.input))

    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

# _STAGE_MD_TEMPLATE, _TEST_RUN_PY_TEMPLATE and the qualified-id regex now live
# in astrid.core.scaffold; _scaffold_component consumes STAGE_MD_TEMPLATE there.


def _cmd_list(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    executors = _filter_by_pack(registry.list(kind=args.kind), getattr(args, "pack", None))
    show_overrides = bool(getattr(args, "show_overrides", False))
    if args.json:
        result = []
        for item in executors:
            handle = to_capability_handle(item)
            entry = {'_capability': handle.to_dict(), 'source_pack': _definition_pack_id(item), **item.to_dict()}
            if show_overrides and registry.override_store is not None:
                entry['_override'] = registry.override_store.resolve("executor", item.id)
            result.append(entry)
        print(json.dumps({'executors': result}, indent=2, sort_keys=True))
        return 0
    no_describe = bool(getattr(args, "no_describe", False))
    for executor in executors:
        override_tag = ""
        if show_overrides and registry.override_store is not None:
            target = registry.override_store.resolve("executor", executor.id)
            if target is not None:
                override_tag = f"\t→ {target}"
        if no_describe:
            print(f"{executor.id}\t{executor.kind}\t{executor.name}{override_tag}")
        else:
            short = short_description_or_truncated(executor.short_description, executor.description)
            invoke = _format_invocation_hint("executors", executor.id, executor.inputs)
            print(f"{executor.id}\t{executor.kind}\t{executor.name}\t{short}\t{invoke}{override_tag}")
    return 0


def _cmd_search(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    resolver = registry.alias_resolver
    records = [
        _executor_search_record(
            executor,
            aliases=_aliases_text(resolver, executor.id) if resolver else "",
        )
        for executor in _filter_by_pack(registry.list(), getattr(args, "pack", None))
    ]
    hits = run_search(records, list(args.terms), limit=int(args.limit))
    if args.json:
        payload = [
            {
                "id": hit.record.id,
                "kind": hit.record.kind,
                "score": round(hit.score, 3),
                "short_description": hit.record.short_description,
            }
            for hit in hits
        ]
        print(json.dumps({"hits": payload}, indent=2, sort_keys=True))
        return 0
    for hit in hits:
        print(f"{hit.score:.2f}\t{hit.record.id}\t{hit.record.kind}\t{hit.record.short_description}")
    return 0


def _executor_search_record(executor: ExecutorDefinition, *, aliases: str = "") -> SearchRecord:
    short = short_description_or_truncated(executor.short_description, executor.description)
    fields = {
        "id": executor.id,
        "name": executor.name,
        "short_description": executor.short_description,
        "description": executor.description,
        "keywords": " ".join(executor.keywords),
        "binaries": " ".join(executor.isolation.binaries),
        "pack_id": executor.id.split(".")[0] if "." in executor.id else executor.id,
        "version": executor.version,
        "category": str(executor.metadata.get("category") or executor.kind),
    }
    if aliases:
        fields["aliases"] = aliases
    return SearchRecord(id=executor.id, kind=executor.kind, short_description=short, fields=fields)


def _cmd_inspect(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    _require_qualified_id(args.executor_id, "executor id")

    # Detect alias resolution before get() so we can enrich the handle.
    requested_id = args.executor_id
    alias_record = None
    if registry.alias_resolver is not None and registry.alias_resolver.is_alias(requested_id):
        alias_record = registry.alias_resolver.get_record(requested_id)

    executor = registry.get(requested_id)
    _require_pack_match(executor, getattr(args, "pack", None))
    show_overrides = bool(getattr(args, "show_overrides", False))

    # Collect alias metadata for the capability handle.
    resolved_alias: str | None = None
    aliases: tuple = ()
    deprecated: bool = False
    deprecation_message: str = ""
    if alias_record is not None:
        resolved_alias = requested_id
        deprecated = alias_record.deprecated
        deprecation_message = alias_record.deprecation_message
    if registry.alias_resolver is not None:
        aliases = tuple(registry.alias_resolver.get_aliases_for(executor.id))

    if args.json:
        handle = to_capability_handle(
            executor,
            aliases=aliases,
            resolved_alias=resolved_alias,
            deprecated=deprecated,
            deprecation_message=deprecation_message,
        )
        result = {"_capability": handle.to_dict(), **executor.to_dict()}
        if show_overrides and registry.override_store is not None:
            result["_override"] = registry.override_store.resolve("executor", executor.id)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    print(f"id: {executor.id}")
    print(f"name: {executor.name}")
    print(f"kind: {executor.kind}")
    print(f"version: {executor.version}")
    if executor.short_description:
        print(f"short_description: {executor.short_description}")
    if executor.description:
        print(f"description: {executor.description}")
    if executor.keywords:
        print(f"keywords: {', '.join(executor.keywords)}")
    # Alias mapping (human-readable)
    if resolved_alias:
        print(f"requested_alias: {resolved_alias} → {executor.id}")
        if deprecated:
            msg = f"deprecated: {deprecation_message}" if deprecation_message else "deprecated: yes"
            print(msg)
    if aliases:
        alias_ids = [a.alias for a in aliases]
        print(f"aliases: {', '.join(alias_ids)}")
    _print_ports("inputs", executor.inputs)
    _print_outputs(executor)
    if executor.command is not None:
        print(f"command: {shlex.join(executor.command.argv)}")
    print(f"cache: {executor.cache.mode}")
    if executor.cache.sentinels:
        print(f"cache_sentinels: {', '.join(executor.cache.sentinels)}")
    if executor.isolation.binaries:
        print(f"binaries: {', '.join(executor.isolation.binaries)}")
    if show_overrides and registry.override_store is not None:
        target = registry.override_store.resolve("executor", executor.id)
        if target is not None:
            print(f"override: executor/{executor.id} → {target}")
        else:
            print("override: none")
    _print_invocation_example("executors", executor.id, executor.inputs)
    return 0


def _definition_pack_id(definition: ExecutorDefinition) -> str:
    source_pack = definition.metadata.get("source_pack")
    if isinstance(source_pack, str) and source_pack:
        return source_pack
    return definition.id.split(".", 1)[0]


def _filter_by_pack(definitions: list[ExecutorDefinition], pack_id: str | None) -> list[ExecutorDefinition]:
    if not pack_id:
        return definitions
    return [definition for definition in definitions if _definition_pack_id(definition) == pack_id]


def _require_pack_match(definition: ExecutorDefinition, pack_id: str | None) -> None:
    if pack_id and _definition_pack_id(definition) != pack_id:
        raise ValueError(f"executor {definition.id!r} does not belong to pack {pack_id!r}")


def _cmd_validate(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    registry.validate_all()
    if args.executor_id:
        _require_qualified_id(args.executor_id, "executor id")
    executors = [registry.get(args.executor_id)] if args.executor_id else registry.list()
    missing_by_executor: dict[str, tuple[str, ...]] = {}
    if args.check_binaries:
        from .runner import check_executor_binaries

        for executor in executors:
            missing = check_executor_binaries(executor)
            if missing:
                missing_by_executor[executor.id] = missing
    if missing_by_executor:
        for executor_id, missing in missing_by_executor.items():
            _eprint(f"{executor_id}: missing binaries: {', '.join(missing)}")
        return 1
    if args.executor_id:
        print(f"{args.executor_id}: ok")
    else:
        print(f"{len(executors)} executor(s): ok")
    return 0


def _cmd_install(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    from .install import install_executor

    _require_qualified_id(args.executor_id, "executor id")
    executor = registry.get(args.executor_id)
    result = install_executor(executor, dry_run=bool(args.dry_run))
    plan = result.plan
    if plan.noop_reason:
        print(f"{executor.id}: no install needed: {plan.noop_reason}")
        return result.returncode
    if plan.environment_path is not None:
        print(f"env: {plan.environment_path}")
    if plan.python_path is not None:
        print(f"python: {plan.python_path}")
    for command in plan.commands:
        _eprint(shlex.join(command))
    return result.returncode


def _cmd_run(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    from .runner import ExecutorRunRequest, run_executor

    _reject_run_passthrough(getattr(args, "_raw_argv", ()) or ())
    _require_qualified_id(args.executor_id, "executor id")
    executor = registry.get(args.executor_id)
    auto_resolved_project = _gateway_resolved_project(args.project)
    project_was_auto_resolved = auto_resolved_project is not None and args.project is None
    project_uuid = _project_uuid_or_none(args.project)
    if project_uuid is not None:
        # UUID mode: --project is a reigh-app UUID, runs need an --out for
        # local placeholders + a --timeline-id to address the row.
        if not getattr(args, "timeline_id", None):
            raise ValueError("--timeline-id is required when --project is a reigh-app UUID")
        if not args.out:
            raise ValueError("--out is required when --project is a reigh-app UUID")
        local_project: str | None = None
    else:
        local_project = args.project or auto_resolved_project
        if local_project and args.out and not project_was_auto_resolved:
            raise ValueError("--project cannot be combined with --out; project runs own their output directory")
    if not args.out and local_project is None and project_uuid is None and _executor_needs_out(executor):
        raise ValueError("--out is required for this executor")
    request = ExecutorRunRequest(
        executor_id=args.executor_id,
        out=Path(args.out) if args.out else "",
        project=local_project,
        inputs=_run_inputs(args),
        brief=Path(args.brief) if args.brief else None,
        dry_run=bool(args.dry_run),
        check_binaries=bool(args.check_binaries),
        python_exec=args.python_exec,
        verbose=bool(args.verbose),
        argv=tuple(getattr(args, "_raw_argv", ()) or ()),
        project_was_auto_resolved=project_was_auto_resolved,
    )
    result = run_executor(request, registry)
    if result.missing_binaries:
        _eprint(f"{args.executor_id}: missing binaries: {', '.join(result.missing_binaries)}")
        return 1
    if result.skipped:
        print(f"{args.executor_id}: skipped: {result.skipped_reason}")
        return 0
    emit_json = bool(getattr(args, "json", False))
    if result.command and not emit_json:
        _eprint(shlex.join(result.command))
    if emit_json:
        from astrid.sdk import (
            InvocationResult,
            _discover_invocation_manifest_path,
            _error_payload_from_internal_error,
            _internal_error_from_result,
            _normalize_executor_result,
        )

        raw_result = _normalize_executor_result(result)
        internal_error = _internal_error_from_result(result)
        error = (
            _error_payload_from_internal_error(internal_error)
            if internal_error is not None
            else None
        )
        manifest_path = _discover_invocation_manifest_path(
            raw_result,
            out=request.out or None,
        )
        payload = InvocationResult(
            capability_id=args.executor_id,
            capability_type="executor",
            native_kind=result.kind,
            ok=bool(result.ok),
            error=error,
            manifest_path=manifest_path,
            raw_result=raw_result,
        ).to_dict()
        print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    elif result.payload:
        print(json.dumps(dict(result.payload), separators=(",", ":"), sort_keys=True))
    # Success/failure flows through ``ok``/``error`` (returncode is descriptive).
    if not result.ok:
        if result.error is not None:
            _eprint(f"{args.executor_id}: {result.error.message}")
        return int(result.returncode or 1)
    rc = int(result.returncode or 0)
    if rc == 0 and project_uuid is not None and not args.dry_run:
        rc = _emit_uuid_handoff_metadata(
            project_id=project_uuid,
            timeline_id=args.timeline_id,
            out_dir=Path(args.out),
        )
    return rc


_UUID_RE = __import__("re").compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _project_uuid_or_none(value: str | None) -> str | None:
    if not value:
        return None
    return value if _UUID_RE.match(value) else None


def _emit_uuid_handoff_metadata(
    *,
    project_id: str,
    timeline_id: str,
    out_dir: Path,
) -> int:
    """Emit bridge/handoff metadata for UUID-mode runs (m3.5).

    UUID mode is a handoff contract: the local executor completes, produces
    explicit bridge metadata, and does NOT call the SupabaseDataProvider
    save_timeline method.
    The actual Supabase push is deferred to m6 (open_in_reigh bridge replay).

    When hype.timeline.json is present, emit JSON handoff metadata on stdout
    so downstream tooling can pick up the bridge intent.  When it is absent,
    log and return 0 (non-producing runs are valid handoffs).
    """
    timeline_path = out_dir / "hype.timeline.json"
    if not timeline_path.is_file():
        _eprint(
            f"executors: --project {project_id} UUID mode: {timeline_path} not produced; "
            f"handoff complete (no timeline to bridge)"
        )
        return 0

    import time as _time
    handoff = {
        "bridge": "executor-uuid-mode",
        "schema_version": 1,
        "project_id": project_id,
        "timeline_id": timeline_id,
        "out_dir": str(out_dir.resolve()),
        "timeline_path": str(timeline_path.resolve()),
        "note": "Bridge metadata for m6 replay.  Replay via open_in_reigh after m6 Supabase RPC exists.",
        "emitted_at": _time.time(),
    }
    print(json.dumps(handoff, separators=(",", ":"), sort_keys=True))
    return 0


def _executor_needs_out(executor: ExecutorDefinition) -> bool:
    if executor.id == "youtube.upload":
        return False
    if executor.kind == "built_in" and "pipeline_step" in executor.metadata:
        return True
    if executor.command is not None:
        parts = [*executor.command.argv]
        if executor.command.cwd:
            parts.append(executor.command.cwd)
        parts.extend(executor.command.env.values())
        if any("{out}" in part for part in parts):
            return True
    return any((output.path_template and "{out}" in output.path_template) for output in executor.outputs)


def _run_inputs(args: argparse.Namespace) -> dict[str, Any]:
    inputs = _parse_input_values(args.input)
    for key in ("video_url", "title", "description", "privacy_status", "playlist_id"):
        value = getattr(args, key)
        if value not in (None, ""):
            inputs[key] = value
    tags = [*getattr(args, "tag", []), *getattr(args, "tags", [])]
    if tags:
        inputs["tags"] = tags
    if getattr(args, "made_for_kids", False):
        inputs["made_for_kids"] = True
    return inputs


def _parse_input_values(raw_values: list[str]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for raw in raw_values:
        if "=" not in raw:
            raise ValueError(f"invalid --input value {raw!r}; expected NAME=VALUE")
        key, value = raw.split("=", 1)
        key = key.strip().replace("-", "_")
        if not key:
            raise ValueError(f"invalid --input value {raw!r}; expected NAME=VALUE")
        if key in values:
            existing = values[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                values[key] = [existing, value]
        else:
            values[key] = value
    return values


def _reject_run_passthrough(raw_argv: tuple[str, ...] | list[str]) -> None:
    if "--" not in raw_argv:
        return
    marker = list(raw_argv).index("--")
    extra = list(raw_argv)[marker + 1 :]
    if extra:
        raise ValueError("executors run does not accept arbitrary passthrough arguments after --")


def _print_outputs(executor: ExecutorDefinition) -> None:
    if not executor.outputs:
        return
    print("outputs:")
    for output in executor.outputs:
        placeholder = f", placeholder={output.placeholder}" if output.placeholder else ""
        print(f"  - {output.name} ({output.type}, {output.mode}{placeholder})")


def _cmd_override(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    store = registry.override_store
    if store is None:
        _eprint("executors: override store not available")
        return 1
    action = getattr(args, "override_action", None)
    if action == "set":
        store.set_override("executor", args.executor_id, args.target_id)
        print(f"override set: executor/{args.executor_id} → {args.target_id}")
    elif action == "remove":
        store.remove_override("executor", args.executor_id)
        print(f"override removed: executor/{args.executor_id}")
    elif action == "list":
        overrides = store.list_overrides()
        if not overrides:
            print("no overrides")
            return 0
        for override_type, mappings in sorted(overrides.items()):
            for override_id, target in sorted(mappings.items()):
                print(f"{override_type}/{override_id} → {target}")
    else:
        _eprint(f"executors override: unknown action {action!r}")
        return 2
    return 0


def _cmd_dirty(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    action = getattr(args, "dirty_action", None)
    if action == "check":
        executor = registry.get(args.executor_id)
        content_root = _definition_content_root(executor)
        forked_from = str(executor.metadata.get("forked_from") or "")
        state = detect_local_edits(content_root, forked_from=forked_from)
        print(f"executor/{executor.id}: {state}")
    elif action == "list":
        dirty_found = 0
        for executor in registry.list():
            content_root = _definition_content_root(executor)
            forked_from = str(executor.metadata.get("forked_from") or "")
            state = detect_local_edits(content_root, forked_from=forked_from)
            if state != "clean":
                print(f"executor/{executor.id}: {state}")
                dirty_found += 1
        if dirty_found == 0:
            print("no dirty executors")
    else:
        _eprint(f"executors dirty: unknown action {action!r}")
        return 2
    return 0


def _cmd_update(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    action = getattr(args, "update_action", None)
    if action == "check":
        report = update_check(
            args.executor_id, registry,
            capability_type="executor",
        )
        print(report["report"])
        return 0
    elif action == "apply":
        force = bool(getattr(args, "force", False))
        skip_safety = bool(getattr(args, "skip_safety", False))
        report = update_apply(
            args.executor_id, registry,
            force=force, skip_safety=skip_safety,
            capability_type="executor",
        )
        print(report["report"])
        return 0 if report.get("applied") else 1
    else:
        _eprint(f"executors update: unknown action {action!r}")
        return 2


def _definition_content_root(definition: ExecutorDefinition) -> Path:
    """Extract content root from executor definition metadata."""
    root_str = definition.metadata.get("content_root")
    if root_str:
        return Path(root_str)
    # Fallback to executor_root metadata key.
    root_str = definition.metadata.get("executor_root")
    if root_str:
        return Path(root_str)
    return Path.cwd()


if __name__ == "__main__":
    raise SystemExit(main())
