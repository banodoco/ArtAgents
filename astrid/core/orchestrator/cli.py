"""Canonical command-line interface for Astrid orchestrators."""

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
    QID_RE as _QID_RE,
)
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

from .registry import OrchestratorRegistry, load_default_registry
from .schema import OrchestratorDefinition, OrchestratorValidationError, to_capability_handle


from astrid.core.contracts._capability_common import (
    _aliases_text,
    _banodoco_config_from_args,
    _definition_content_root,
    _definition_pack_id,
    _eprint,
    _filter_by_pack,
    _format_invocation_hint,
    _gateway_resolved_project,
    _print_invocation_example,
    _print_ports,
    _require_pack_match,
    _require_qualified_id,
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parse_argv, passthrough = _split_run_passthrough(list(argv) if argv is not None else sys.argv[1:])
    args = parser.parse_args(parse_argv)
    if getattr(args, "command", None) == "run":
        args.orchestrator_args = passthrough
    try:
        # FLAG-S1-002: 'new' short-circuits BEFORE load_default_registry() so
        # scaffold commands never load the built-in registry or import pack code.
        if getattr(args, "command", None) == "new":
            return int(args.handler(args, registry=None))
        # SD2: orchestrator CLI defaults to Path.cwd() so forks land in the
        # user's current project, not the source-tree REPO_ROOT.
        project_root = getattr(args, "project_root", None) or Path.cwd()
        # Create OverrideStore so --show-overrides and override set/remove/list work.
        override_store = OverrideStore(project_root=project_root)
        registry = load_default_registry(
            banodoco_config=_banodoco_config_from_args(args, agent_flag="banodoco_agent_orchestrators"),
            project_root=project_root,
            extra_pack_roots=tuple(args.pack_root),
        )
        registry.override_store = override_store
        return int(args.handler(args, registry))
    except (KeyError, OrchestratorValidationError, ProjectRunError, ValueError, OverrideStoreError) as exc:
        raise AstridError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = RecoverableArgumentParser(
        prog="python3 -m astrid orchestrators",
        description="List, inspect, validate, and run Astrid orchestrators.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--pack-root", action="append", default=[], metavar="PATH", help="Extra pack root directory to discover orchestrators from; may be repeated.")
    parser.add_argument("--banodoco-agent-orchestrators", action="store_true", help="Opt in to loading orchestrators from the Banodoco website catalog.")
    parser.add_argument("--banodoco-catalog-url", help="Banodoco website catalog Edge Function URL.")
    parser.add_argument("--banodoco-cache-dir", help="Cache directory for git-backed Banodoco orchestrators.")
    parser.add_argument("--banodoco-refresh", action="store_true", help="Refresh cached git checkouts before loading Banodoco orchestrators.")
    parser.add_argument("--no-banodoco-defaults", action="store_true", help="Skip Banodoco catalog orchestrators marked default.")
    parser.add_argument("--no-banodoco-mandatory", action="store_true", help="Skip Banodoco catalog orchestrators marked mandatory.")
    # SD2: executor/orchestrator CLIs fork to Path.cwd() by default.
    parser.add_argument("--project-root", type=Path, help="Project root for local pack discovery and fork targets. Defaults to current working directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", aliases=["ls"], help="List available orchestrators.")
    list_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    add_choice_arg(
        list_parser,
        "--kind",
        values=("built_in", "external"),
        help="Filter orchestrators by kind.",
    )
    list_parser.add_argument("--pack", help="Filter orchestrators by source pack id.")
    list_parser.add_argument("--no-describe", action="store_true", help="Omit the short_description column for legacy parsers.")
    list_parser.add_argument("--show-overrides", action="store_true", help="Annotate capabilities with active overrides.")
    list_parser.set_defaults(handler=_cmd_list)

    search_parser = subparsers.add_parser("search", help="Search orchestrators by id, keywords, and descriptions.")
    search_parser.add_argument("terms", nargs="+", help="One or more search terms.")
    search_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    search_parser.add_argument("--limit", type=int, default=25, help="Maximum number of hits (default 25).")
    search_parser.add_argument("--pack", help="Filter orchestrators by source pack id.")
    search_parser.set_defaults(handler=_cmd_search)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect one orchestrator.")
    inspect_parser.add_argument("orchestrator_id")
    inspect_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    inspect_parser.add_argument("--pack", help="Require the resolved orchestrator to belong to this pack id.")
    inspect_parser.add_argument("--show-overrides", action="store_true", help="Show override status for this capability.")
    inspect_parser.set_defaults(handler=_cmd_inspect)

    validate_parser = subparsers.add_parser("validate", help="Validate orchestrator metadata.")
    validate_parser.add_argument("orchestrator_id", nargs="?")
    validate_parser.set_defaults(handler=_cmd_validate)

    run_parser = subparsers.add_parser(
        "run",
        help="Run or dry-run one orchestrator.",
        description=(
            "Run or dry-run one orchestrator.\n\n"
            "Orchestrators with a command runtime (most built-ins like video_editing.hype) "
            "accept their pack-specific arguments via passthrough AFTER a literal `--`:\n\n"
            "    astrid orchestrators run <id> --project <slug> -- --pack-arg <value> ...\n\n"
            "To discover an orchestrator's pack-specific args:\n"
            "  1. `astrid orchestrators inspect <id>` shows declared inputs and the\n"
            "     runtime invocation pattern.\n"
            "  2. For built-ins, the pack's run.py module accepts `--help` directly:\n"
            "     `python3 -m astrid.packs.<pack>.<orch>.run --help`\n\n"
            "Anything before `--` is consumed by this CLI gateway; anything after is "
            "forwarded verbatim to the pack runtime (substituted into the runtime's "
            "{orchestrator_args} placeholder)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    run_parser.add_argument("orchestrator_id")
    run_parser.add_argument("--out", help="Output directory for runtime placeholders.")
    run_parser.add_argument("--project", help="Project slug for a persistent project run.")
    run_parser.add_argument("--brief", help="Brief path for runtime placeholders.")
    run_parser.add_argument("--input", action="append", default=[], metavar="NAME=VALUE", help="Orchestrator input value; may be repeated.")
    run_parser.add_argument("--dry-run", action="store_true", help="Plan commands without executing command runtimes.")
    run_parser.add_argument("--python-exec", help="Python executable for {python_exec} placeholders.")
    run_parser.add_argument("--verbose", action="store_true", help="Set verbose runtime context.")
    run_parser.set_defaults(handler=_cmd_run)

    new_parser = subparsers.add_parser("new", help="Scaffold a new orchestrator in an existing pack.")
    new_parser.add_argument(
        "qualified_id",
        help="Qualified orchestrator id: <pack>.<slug> (e.g., my_pack.make_trailer).",
    )
    new_parser.set_defaults(handler=_cmd_new)

    fork_parser = subparsers.add_parser("fork", help="Fork an orchestrator into the local pack (astrid/packs/local).")
    fork_parser.add_argument("orchestrator_id", help="Qualified orchestrator id to fork (e.g., video_editing.hype).")
    fork_parser.add_argument("--overwrite", action="store_true", help="Replace an existing local fork.")
    fork_parser.add_argument("--deep", action="store_true", help="Also recursively fork all child executors and orchestrators.")
    fork_parser.set_defaults(handler=_cmd_fork)

    # --- Override subcommands ---
    override_parser = subparsers.add_parser("override", help="Manage capability overrides.")
    override_sub = override_parser.add_subparsers(dest="override_action", required=True)

    override_set = override_sub.add_parser("set", help="Set an override: route an orchestrator to a replacement.")
    override_set.add_argument("orchestrator_id")
    override_set.add_argument("target_id", help="Fully-qualified id of the replacement orchestrator.")
    override_set.set_defaults(handler=_cmd_override)

    override_remove = override_sub.add_parser("remove", help="Remove an override.")
    override_remove.add_argument("orchestrator_id")
    override_remove.set_defaults(handler=_cmd_override)

    override_list = override_sub.add_parser("list", help="List all active overrides.")
    override_list.set_defaults(handler=_cmd_override)

    # --- Dirty subcommands ---
    dirty_parser = subparsers.add_parser("dirty", help="Check or list locally-modified (dirty) orchestrators.")
    dirty_sub = dirty_parser.add_subparsers(dest="dirty_action", required=True)

    dirty_check = dirty_sub.add_parser("check", help="Check dirty state for one orchestrator.")
    dirty_check.add_argument("orchestrator_id")
    dirty_check.set_defaults(handler=_cmd_dirty)

    dirty_list = dirty_sub.add_parser("list", help="List all dirty orchestrators.")
    dirty_list.set_defaults(handler=_cmd_dirty)

    # --- Update subcommands ---
    update_parser = subparsers.add_parser("update", help="Check for or apply upstream updates to forked orchestrators.")
    update_sub = update_parser.add_subparsers(dest="update_action", required=True)

    update_check_parser = update_sub.add_parser("check", help="Compare local fork against upstream.")
    update_check_parser.add_argument("orchestrator_id")
    update_check_parser.set_defaults(handler=_cmd_update)

    update_apply_parser = update_sub.add_parser("apply", help="Apply upstream update to a local fork.")
    update_apply_parser.add_argument("orchestrator_id")
    update_apply_parser.add_argument("--force", action="store_true", help="Apply even if safety escalations are detected.")
    update_apply_parser.add_argument("--skip-safety", action="store_true", help="Skip safety escalation checks.")
    update_apply_parser.set_defaults(handler=_cmd_update)

    return parser


def _cmd_fork(args: argparse.Namespace, registry: OrchestratorRegistry) -> int:
    # SD2: orchestrator CLI forks to Path.cwd() by default so forked
    # orchestrators land in the user's current project, not the source-tree
    # REPO_ROOT.
    project_root = getattr(args, "project_root", None) or Path.cwd()

    # Resolve alias BEFORE fork (watch item): alias → canonical ID,
    # then fork the canonical orchestrator.
    resolver = registry.alias_resolver
    resolved_id = resolver.resolve(args.orchestrator_id) if resolver else args.orchestrator_id

    target = registry.fork(
        resolved_id,
        project_root=project_root,
        overwrite=bool(args.overwrite),
        deep=bool(args.deep),
    )
    print(f"forked: {target}")
    return 0


def _cmd_new(args: argparse.Namespace, registry: Any) -> int:
    """Scaffold a new orchestrator component into an existing pack (CWD-relative).

    Short-circuits before ``load_default_registry()`` — never imports pack code.
    """
    qualified_id: str = args.qualified_id

    # Validate early so we can safely split for the plan-template format.
    if not _QID_RE.fullmatch(qualified_id):
        raise AstridError(
            f"orchestrators new: qualified id {qualified_id!r} must be "
            f"'<pack>.<slug>' with letters/digits/underscore",
            recovery_command="astrid orchestrators new <pack>.<slug>",
            state_snapshot={"qualified_id": qualified_id},
        )

    pack, slug = qualified_id.split(".", 1)

    return _scaffold_component(
        qualified_id=qualified_id,
        component_type="orchestrator",
        yaml_template=_ORCHESTRATOR_YAML_TEMPLATE,
        run_py_template=_RUN_PY_TEMPLATE,
        extra_files={
            "plan_template.py": _ORCHESTRATOR_PLAN_TEMPLATE.format(
                qualified_id=qualified_id,
                pack=pack,
                slug=slug,
            ),
            "tests/__init__.py": "",
            "tests/test_run.py": _TEST_RUN_PY_TEMPLATE.format(
                qualified_id=qualified_id,
                component_type="orchestrator",
            ),
        },
    )


# ---------------------------------------------------------------------------
# Orchestrator-specific scaffold templates
# ---------------------------------------------------------------------------

_ORCHESTRATOR_YAML_TEMPLATE = """\
schema_version: 1
id: {qualified_id}
name: {slug}
kind: built_in
version: 0.1.0
description: \"TODO: describe what this orchestrator does.\"

runtime:
  kind: python
  module: run
  function: main
"""

_RUN_PY_TEMPLATE = """\
\"\"\"{qualified_id} — orchestrator runtime entrypoint.

Implement your orchestrator logic here. The function named ``main`` (or
whatever you set for ``runtime.function`` in the manifest) is the entrypoint.
\"\"\"


def main(*, inputs: dict, outputs: dict, **kwargs) -> int:
    \"\"\"Entrypoint for {qualified_id}.

    Args:
        inputs: Dict of resolved input values (name → path/value).
        outputs: Dict to populate with output values (name → path/value).
        **kwargs: Runtime context (project, brief, etc.).

    Returns:
        Exit code (0 on success, non-zero on failure).
    \"\"\"
    # TODO: implement your orchestration logic here
    return 0
"""


_ORCHESTRATOR_PLAN_TEMPLATE = """\
# {qualified_id} — plan v2 template
#
# This file defines ``build_plan_v2``, the function that produces the plan
# dict emitted by the orchestrator runner.  Import helpers from
# ``astrid.core.orchestrator.plan_template`` so you don't need to copy-paste the
# emit / step-command / produces boilerplate into your pack.

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from astrid.core.orchestrator.plan_template import (
    emit_plan_json,
    build_step_command,
    make_produces,
)


def build_plan_v2(
    *,
    python_exec: str,
    run_root: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    \"\"\"Return a minimal valid plan-v2 dict.

    This stub produces a single ``adapter: local`` step.  Replace the
    placeholder command and expand the step list to match your pipeline.
    \"\"\"
    run_root = Path(run_root)

    # TODO: replace this placeholder with your real step command.
    # Use ``build_step_command`` or construct the command string directly.
    step_id = \"hello\"
    command = f\"{{python_exec}} -c 'print(\\\"hello from {{qualified_id}}\\\")' --out {{run_root}}/steps/{{step_id}}/v1/produces\"

    plan: dict[str, Any] = {{
        \"plan_id\": \"{qualified_id}\",
        \"version\": 2,
        \"steps\": [
            {{
                \"id\": step_id,
                \"adapter\": \"local\",
                \"command\": command,
                \"produces\": {{
                    # TODO: replace with your real produces path(s).
                    \"hello_output\": {{
                        \"path\": \"hello.txt\",
                        \"check\": {{
                            \"check_id\": \"file_nonempty\",
                            \"params\": {{}},
                            \"sentinel\": False,
                        }},
                    }}
                }},
            }}
        ],
    }}
    return plan


if __name__ == \"__main__\":
    # Quick smoke-test: build a plan and emit it to a temp path.
    import tempfile

    run_root = Path(tempfile.mkdtemp(prefix=\"plan-test-\"))
    plan = build_plan_v2(python_exec=sys.executable, run_root=run_root)
    plan_path = run_root / \"plan.json\"
    emit_plan_json(plan, plan_path)
    print(f\"plan emitted to {{plan_path}}\")
"""


def _cmd_list(args: argparse.Namespace, registry: OrchestratorRegistry) -> int:
    orchestrators = _filter_by_pack(registry.list(kind=args.kind), getattr(args, "pack", None))
    show_overrides = bool(getattr(args, "show_overrides", False))
    if args.json:
        result = []
        for item in orchestrators:
            handle = to_capability_handle(item)
            entry = {'_capability': handle.to_dict(), 'source_pack': _definition_pack_id(item), **item.to_dict()}
            if show_overrides and registry.override_store is not None:
                entry['_override'] = registry.override_store.resolve("orchestrator", item.id)
            result.append(entry)
        print(json.dumps({'orchestrators': result}, indent=2, sort_keys=True))
        return 0
    no_describe = bool(getattr(args, "no_describe", False))
    for orchestrator in orchestrators:
        override_tag = ""
        if show_overrides and registry.override_store is not None:
            target = registry.override_store.resolve("orchestrator", orchestrator.id)
            if target is not None:
                override_tag = f"\t→ {target}"
        if no_describe:
            print(f"{orchestrator.id}\t{orchestrator.kind}\t{orchestrator.name}{override_tag}")
        else:
            short = short_description_or_truncated(orchestrator.short_description, orchestrator.description)
            invoke = _format_invocation_hint("orchestrators", orchestrator.id, orchestrator.inputs)
            print(f"{orchestrator.id}\t{orchestrator.kind}\t{orchestrator.name}\t{short}\t{invoke}{override_tag}")
    return 0


def _cmd_search(args: argparse.Namespace, registry: OrchestratorRegistry) -> int:
    resolver = registry.alias_resolver
    records = [
        _orchestrator_search_record(
            item,
            aliases=_aliases_text(resolver, item.id) if resolver else "",
        )
        for item in _filter_by_pack(registry.list(), getattr(args, "pack", None))
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


def _orchestrator_search_record(orchestrator: OrchestratorDefinition, *, aliases: str = "") -> SearchRecord:
    short = short_description_or_truncated(orchestrator.short_description, orchestrator.description)
    fields = {
        "id": orchestrator.id,
        "name": orchestrator.name,
        "short_description": orchestrator.short_description,
        "description": orchestrator.description,
        "keywords": " ".join(orchestrator.keywords),
        "pack_id": orchestrator.id.split(".")[0] if "." in orchestrator.id else orchestrator.id,
        "version": orchestrator.version,
        "category": str(orchestrator.metadata.get("category") or orchestrator.kind),
    }
    if aliases:
        fields["aliases"] = aliases
    return SearchRecord(id=orchestrator.id, kind=orchestrator.kind, short_description=short, fields=fields)


def _cmd_inspect(args: argparse.Namespace, registry: OrchestratorRegistry) -> int:
    _require_qualified_id(args.orchestrator_id, "orchestrator id")

    # Detect alias resolution before get() so we can enrich the handle.
    requested_id = args.orchestrator_id
    alias_record = None
    if registry.alias_resolver is not None and registry.alias_resolver.is_alias(requested_id):
        alias_record = registry.alias_resolver.get_record(requested_id)

    orchestrator = registry.get(requested_id)
    _require_pack_match(orchestrator, getattr(args, "pack", None), component_type="orchestrator")
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
        aliases = tuple(registry.alias_resolver.get_aliases_for(orchestrator.id))

    if args.json:
        handle = to_capability_handle(
            orchestrator,
            aliases=aliases,
            resolved_alias=resolved_alias,
            deprecated=deprecated,
            deprecation_message=deprecation_message,
        )
        result = {"_capability": handle.to_dict(), **orchestrator.to_dict()}
        if show_overrides and registry.override_store is not None:
            result["_override"] = registry.override_store.resolve("orchestrator", orchestrator.id)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    print(f"id: {orchestrator.id}")
    print(f"name: {orchestrator.name}")
    print(f"kind: {orchestrator.kind}")
    print(f"version: {orchestrator.version}")
    print(f"runtime: {orchestrator.runtime.kind}")
    if orchestrator.short_description:
        print(f"short_description: {orchestrator.short_description}")
    if orchestrator.description:
        print(f"description: {orchestrator.description}")
    if orchestrator.keywords:
        print(f"keywords: {', '.join(orchestrator.keywords)}")
    # Alias mapping (human-readable)
    if resolved_alias:
        print(f"requested_alias: {resolved_alias} → {orchestrator.id}")
        if deprecated:
            msg = f"deprecated: {deprecation_message}" if deprecation_message else "deprecated: yes"
            print(msg)
    if aliases:
        alias_ids = [a.alias for a in aliases]
        print(f"aliases: {', '.join(alias_ids)}")
    _print_ports("inputs", orchestrator.inputs)
    _print_outputs(orchestrator)
    if orchestrator.child_executors:
        print(f"child_executors: {', '.join(orchestrator.child_executors)}")
    if orchestrator.child_orchestrators:
        print(f"child_orchestrators: {', '.join(orchestrator.child_orchestrators)}")
    if show_overrides and registry.override_store is not None:
        target = registry.override_store.resolve("orchestrator", orchestrator.id)
        if target is not None:
            print(f"override: orchestrator/{orchestrator.id} → {target}")
        else:
            print("override: none")
    # Fix 6 (v6 dogfood): show a concrete example invocation when the
    # orchestrator declares input ports. The `command` block below also
    # synthesises an invocation snippet for the `{orchestrator_args}`
    # passthrough case, but plain `--input <port>=<path>` wiring needs its
    # own example so agents don't guess at the flag shape from `run --help`.
    if orchestrator.inputs:
        _print_invocation_example("orchestrators", orchestrator.id, orchestrator.inputs)
    if orchestrator.runtime.command is not None:
        print(f"command: {shlex.join(orchestrator.runtime.command.argv)}")
        # Invocation hint (#36): agents repeatedly missed that the `{orchestrator_args}`
        # placeholder is filled by a `--` passthrough. Spell it out explicitly so
        # they don't fall back to `python3 -m astrid.packs.X.run` (which skips
        # task-mode and means events.jsonl never lands a run_started).
        argv = orchestrator.runtime.command.argv
        if any("{orchestrator_args}" in part for part in argv):
            example_args = "<pack-args>"
            # Show the pack's --help one-liner so agents can discover args.
            module = orchestrator.metadata.get("runtime_module") if orchestrator.metadata else None
            print()
            print("invocation:")
            print(f"  astrid orchestrators run {orchestrator.id} --project <slug> -- {example_args}")
            if module:
                print(f"  # discover pack args: python3 -m {module} --help")
            print("  # anything after `--` is forwarded verbatim to the pack runtime.")
    return 0


def _cmd_validate(args: argparse.Namespace, registry: OrchestratorRegistry) -> int:
    registry.validate_all()
    if args.orchestrator_id:
        _require_qualified_id(args.orchestrator_id, "orchestrator id")
    orchestrators = [registry.get(args.orchestrator_id)] if args.orchestrator_id else registry.list()
    if args.orchestrator_id:
        print(f"{args.orchestrator_id}: ok")
    else:
        print(f"{len(orchestrators)} orchestrator(s): ok")
    return 0


def _cmd_run(args: argparse.Namespace, registry: OrchestratorRegistry) -> int:
    from .runner import OrchestratorRunRequest, run_orchestrator

    _require_qualified_id(args.orchestrator_id, "orchestrator id")
    auto_resolved_project = _gateway_resolved_project(args.project)
    project_was_auto_resolved = auto_resolved_project is not None and args.project is None
    effective_project = args.project or auto_resolved_project
    if effective_project and args.out and not project_was_auto_resolved:
        raise ValueError("--project cannot be combined with --out; project runs own their output directory")
    request = OrchestratorRunRequest(
        orchestrator_id=args.orchestrator_id,
        out=Path(args.out) if args.out else None,
        project=effective_project,
        inputs=_parse_input_values(args.input),
        brief=Path(args.brief) if args.brief else None,
        orchestrator_args=tuple(args.orchestrator_args),
        dry_run=bool(args.dry_run),
        python_exec=args.python_exec,
        verbose=bool(args.verbose),
        project_was_auto_resolved=project_was_auto_resolved,
    )
    result = run_orchestrator(request, registry)
    _print_run_result(result)
    return int(result.returncode or 0)


def _parse_input_values(raw_values: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in raw_values:
        if "=" not in raw:
            raise ValueError(f"invalid --input value {raw!r}; expected NAME=VALUE")
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid --input value {raw!r}; expected NAME=VALUE")
        values[key] = value
    return values


def _split_run_passthrough(argv: list[str]) -> tuple[list[str], list[str]]:
    if not argv or argv[0] != "run" or "--" not in argv:
        return argv, []
    separator_index = argv.index("--")
    return argv[:separator_index], argv[separator_index + 1 :]


def _print_run_result(result: Any) -> None:
    commands = result.planned_commands or ((result.command,) if result.command else ())
    for command in commands:
        if command:
            _eprint(shlex.join(command))
    if result.errors:
        for error in result.errors:
            _eprint(f"{error.kind}: {error.message}")


def _print_outputs(orchestrator: OrchestratorDefinition) -> None:
    if not orchestrator.outputs:
        return
    print("outputs:")
    for output in orchestrator.outputs:
        placeholder = f", placeholder={output.placeholder}" if output.placeholder else ""
        print(f"  - {output.name} ({output.type}, {output.mode}{placeholder})")


def _cmd_override(args: argparse.Namespace, registry: OrchestratorRegistry) -> int:
    store = registry.override_store
    if store is None:
        _eprint("orchestrators: override store not available")
        return 1
    action = getattr(args, "override_action", None)
    if action == "set":
        store.set_override("orchestrator", args.orchestrator_id, args.target_id)
        print(f"override set: orchestrator/{args.orchestrator_id} → {args.target_id}")
    elif action == "remove":
        store.remove_override("orchestrator", args.orchestrator_id)
        print(f"override removed: orchestrator/{args.orchestrator_id}")
    elif action == "list":
        overrides = store.list_overrides()
        if not overrides:
            print("no overrides")
            return 0
        for override_type, mappings in sorted(overrides.items()):
            for override_id, target in sorted(mappings.items()):
                print(f"{override_type}/{override_id} → {target}")
    else:
        _eprint(f"orchestrators override: unknown action {action!r}")
        return 2
    return 0


def _cmd_dirty(args: argparse.Namespace, registry: OrchestratorRegistry) -> int:
    action = getattr(args, "dirty_action", None)
    if action == "check":
        orchestrator = registry.get(args.orchestrator_id)
        content_root = _definition_content_root(orchestrator, fallback_root_key="orchestrator_root")
        forked_from = str(orchestrator.metadata.get("forked_from") or "")
        state = detect_local_edits(content_root, forked_from=forked_from)
        print(f"orchestrator/{orchestrator.id}: {state}")
    elif action == "list":
        dirty_found = 0
        for orchestrator in registry.list():
            content_root = _definition_content_root(orchestrator, fallback_root_key="orchestrator_root")
            forked_from = str(orchestrator.metadata.get("forked_from") or "")
            state = detect_local_edits(content_root, forked_from=forked_from)
            if state != "clean":
                print(f"orchestrator/{orchestrator.id}: {state}")
                dirty_found += 1
        if dirty_found == 0:
            print("no dirty orchestrators")
    else:
        _eprint(f"orchestrators dirty: unknown action {action!r}")
        return 2
    return 0


def _cmd_update(args: argparse.Namespace, registry: OrchestratorRegistry) -> int:
    action = getattr(args, "update_action", None)
    if action == "check":
        report = update_check(
            args.orchestrator_id, registry,
            capability_type="orchestrator",
        )
        print(report["report"])
        return 0
    elif action == "apply":
        force = bool(getattr(args, "force", False))
        skip_safety = bool(getattr(args, "skip_safety", False))
        report = update_apply(
            args.orchestrator_id, registry,
            force=force, skip_safety=skip_safety,
            capability_type="orchestrator",
        )
        print(report["report"])
        return 0 if report.get("applied") else 1
    else:
        _eprint(f"orchestrators update: unknown action {action!r}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
