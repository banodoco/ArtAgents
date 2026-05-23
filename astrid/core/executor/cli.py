"""Canonical command-line interface for Astrid executors."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from astrid.core.project.run import ProjectRunError

from astrid.core._search import (
    SearchRecord,
    search as run_search,
    short_description_or_truncated,
)

from astrid.core.dirty import detect_local_edits
from astrid.core.override import OverrideStore, OverrideStoreError
from astrid.core.update import update_check, update_apply

from .banodoco_catalog import BanodocoCatalogConfig
from .registry import ExecutorRegistry, load_default_registry
from .schema import ExecutorDefinition, ExecutorValidationError, to_capability_handle


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
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
            _banodoco_config_from_args(args), project_root=project_root,
            extra_pack_roots=tuple(args.pack_root),
        )
        registry.override_store = override_store
        return int(args.handler(args, registry))
    except (KeyError, ExecutorValidationError, ProjectRunError, ValueError, OverrideStoreError) as exc:
        print(f"executors: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
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

    list_parser = subparsers.add_parser("list", help="List available executors.")
    list_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    list_parser.add_argument("--kind", choices=("built_in", "external"), help="Filter executors by kind.")
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
    run_parser.add_argument("--thread", help="Thread id, @new, or @none for this run.")
    run_parser.add_argument("--variants", type=int, help="Request a sibling variant count for variant-aware producers.")
    run_parser.add_argument("--from", dest="from_ref", help="Consume a specific prior run or variant, e.g. <run-id>:<n>.")
    run_parser.add_argument("--video-url", "--video", dest="video_url", help="Reachable http(s) video URL.")
    run_parser.add_argument("--title", help="YouTube video title.")
    run_parser.add_argument("--description", help="YouTube video description.")
    run_parser.add_argument("--tag", action="append", default=[], help="YouTube tag. May be repeated.")
    run_parser.add_argument("--tags", action="append", default=[], help="Comma-separated YouTube tags.")
    run_parser.add_argument("--privacy-status", default=None, help="YouTube privacy status: private, unlisted, or public.")
    run_parser.add_argument("--playlist-id", help="Optional YouTube playlist ID.")
    run_parser.add_argument("--made-for-kids", action="store_true", help="Mark the video as made for kids.")
    run_parser.set_defaults(handler=_cmd_run)

    new_parser = subparsers.add_parser("new", help="Scaffold a new executor in an existing pack.")
    new_parser.add_argument(
        "qualified_id",
        help="Qualified executor id: <pack>.<slug> (e.g., my_pack.ingest_assets).",
    )
    new_parser.set_defaults(handler=_cmd_new)

    fork_parser = subparsers.add_parser("fork", help="Fork an executor into the local pack (astrid/packs/local).")
    fork_parser.add_argument("executor_id", help="Qualified executor id to fork (e.g., builtin.render).")
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


def _scaffold_component(
    qualified_id: str,
    component_type: str,
    yaml_template: str,
    run_py_template: str,
    *,
    extra_files: dict[str, str] | None = None,
) -> int:
    """Shared scaffolding logic for executors new / orchestrators new.

    Args:
        qualified_id: ``<pack>.<slug>`` identifier.
        component_type: ``'executor'`` or ``'orchestrator'``.
        yaml_template: str.format template for the component manifest.
        run_py_template: str.format template for run.py stub.
        extra_files: Optional mapping of filename → already-formatted content
            to write into the component directory (e.g., ``plan_template.py``).

    Returns:
        Exit code (0 on success, non-zero on failure).
    """
    from astrid.packs.validate import validate_pack

    # Derive the correct CLI prefix for error messages.
    _cli_prefix = f"{component_type}s new"

    # --- 1. Validate the qualified id ------------------------------------------
    if not _QID_RE.fullmatch(qualified_id):
        print(
            f"{_cli_prefix}: qualified id {qualified_id!r} must be "
            f"'<pack>.<slug>' with letters/digits/underscore",
            file=sys.stderr,
        )
        return 2

    pack, slug = qualified_id.split(".", 1)

    # --- 2. Find the target pack root (CWD-relative) ---------------------------
    pack_root = Path.cwd().resolve()
    pack_yaml = pack_root / "pack.yaml"
    if not pack_yaml.is_file():
        print(
            f"{_cli_prefix}: pack.yaml not found at {pack_root}. "
            f"Scaffold the pack first with: python3 -m astrid packs new {pack}",
            file=sys.stderr,
        )
        return 1

    # Verify the pack id in pack.yaml matches
    import yaml as _yaml_module
    try:
        with open(pack_yaml, "r", encoding="utf-8") as fh:
            doc = _yaml_module.safe_load(fh)
    except Exception as exc:
        print(f"{_cli_prefix}: cannot read {pack_yaml}: {exc}", file=sys.stderr)
        return 1

    if isinstance(doc, dict) and doc.get("id") != pack:
        print(
            f"{_cli_prefix}: pack id mismatch — {qualified_id!r} expects "
            f"pack id {pack!r} but {pack_yaml} has id {doc.get('id')!r}",
            file=sys.stderr,
        )
        return 1

    # --- 3. Determine the content root for this component type -----------------
    content = doc.get("content", {}) if isinstance(doc, dict) else {}
    rel_dir = content.get(f"{component_type}s", f"{component_type}s")
    components_root = pack_root / rel_dir
    component_dir = components_root / slug

    # --- 4. Reject overwrite collisions ----------------------------------------
    if component_dir.exists():
        print(
            f"{_cli_prefix}: {component_dir} already exists; refusing to overwrite",
            file=sys.stderr,
        )
        return 1

    # --- 5. Create the scaffold ------------------------------------------------
    component_dir.mkdir(parents=True)
    created: list[str] = []

    # Component manifest (executor.yaml / orchestrator.yaml)
    manifest_path = component_dir / f"{component_type}.yaml"
    manifest_text = yaml_template.format(pack=pack, slug=slug, qualified_id=qualified_id)
    manifest_path.write_text(manifest_text, encoding="utf-8")
    created.append(str(manifest_path.relative_to(pack_root)))

    # run.py stub
    run_py_path = component_dir / "run.py"
    run_py_text = run_py_template.format(qualified_id=qualified_id, component_type=component_type)
    run_py_path.write_text(run_py_text, encoding="utf-8")
    created.append(str(run_py_path.relative_to(pack_root)))

    # STAGE.md stub
    stage_md_path = component_dir / "STAGE.md"
    stage_md_text = _STAGE_MD_TEMPLATE.format(
        qualified_id=qualified_id, component_type=component_type.title()
    )
    stage_md_path.write_text(stage_md_text, encoding="utf-8")
    created.append(str(stage_md_path.relative_to(pack_root)))

    # Extra files (e.g., plan_template.py for orchestrators, tests/)
    for filename, content in (extra_files or {}).items():
        extra_path = component_dir / filename
        extra_path.parent.mkdir(parents=True, exist_ok=True)
        extra_path.write_text(content, encoding="utf-8")
        created.append(str(extra_path.relative_to(pack_root)))

    # --- 6. Validate the pack after scaffolding --------------------------------
    # We only fail when errors involve the JUST-scaffolded file. Pre-existing
    # pack-level issues (other components missing schema_version, stale
    # element manifests, etc.) get surfaced as warnings so they don't mask
    # the scaffold success and don't block the agent from making forward
    # progress. The dogfood found that the pack-author schema (used here)
    # and the runtime registry schema diverge — runtime-form executors that
    # the registry accepts as `kind/command/inputs` look "unknown" to the
    # pack-author schema. Use `astrid executors validate <id>` separately
    # for the authoritative runtime check.
    errors, warnings = validate_pack(pack_root)
    component_rel = str(component_dir.relative_to(pack_root))
    own_errors = [err for err in errors if component_rel in str(err)]
    foreign_errors = [err for err in errors if component_rel not in str(err)]
    if own_errors:
        print(
            f"{_cli_prefix}: scaffolded {component_type} fails validation "
            f"({len(own_errors)} error(s))",
            file=sys.stderr,
        )
        for err in own_errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    if foreign_errors:
        print(
            f"{_cli_prefix}: pre-existing pack issues (not from this scaffold; "
            f"surfaced as a warning):",
            file=sys.stderr,
        )
        for err in foreign_errors:
            print(f"  {err}", file=sys.stderr)

    # --- 7. Report ------------------------------------------------------------
    for rel in created:
        print(f"created {rel}")
    if warnings:
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
    print(f"{component_type} {qualified_id!r} created and validated")
    return 0


# ---------------------------------------------------------------------------
# Qualified-id validation (matches the v1 _defs.json qualified_id pattern)
# ---------------------------------------------------------------------------

import re as _re

_QID_RE = _re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

# ---------------------------------------------------------------------------
# Scaffold templates
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
# resolves to the interpreter; add `--project {{project}}` if you want the
# executor to participate in task-mode gating.
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

_STAGE_MD_TEMPLATE = """\
# {qualified_id}

## Purpose

TODO: describe what this {component_type} does and when to use it.

## Inputs

TODO: list the inputs this {component_type} expects.

## Outputs

TODO: list the outputs this {component_type} produces.

## Dependencies

TODO: any Python, npm, or system dependencies.
"""

_TEST_RUN_PY_TEMPLATE = '''\
"""Basic smoke test for {qualified_id}."""
import subprocess
import sys


def test_dry_run() -> None:
    """Verify the {component_type} runs in dry-run mode without errors."""
    result = subprocess.run(
        [sys.executable, "-m", "astrid", "{component_type}s", "run",
         "{qualified_id}", "--dry-run"],
        capture_output=True,
        text=True,
    )
    # TODO: assert on expected behavior
    assert result.returncode == 0, f"dry-run failed: {{result.stderr}}"
'''


def _banodoco_config_from_args(args: argparse.Namespace) -> BanodocoCatalogConfig:
    env_config = BanodocoCatalogConfig.from_env()
    enabled = bool(args.banodoco_agent_executors or env_config.enabled)
    return BanodocoCatalogConfig(
        enabled=enabled,
        catalog_url=args.banodoco_catalog_url or env_config.catalog_url,
        include_defaults=False if args.no_banodoco_defaults else env_config.include_defaults,
        include_mandatory=False if args.no_banodoco_mandatory else env_config.include_mandatory,
        cache_dir=Path(args.banodoco_cache_dir).expanduser() if args.banodoco_cache_dir else env_config.cache_dir,
        refresh=bool(args.banodoco_refresh or env_config.refresh),
        timeout_seconds=env_config.timeout_seconds,
    )


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
    records = [_executor_search_record(executor) for executor in _filter_by_pack(registry.list(), getattr(args, "pack", None))]
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


def _executor_search_record(executor: ExecutorDefinition) -> SearchRecord:
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
    return SearchRecord(id=executor.id, kind=executor.kind, short_description=short, fields=fields)


def _cmd_inspect(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    # Resolve alias BEFORE _require_qualified_id (SD1): alias → canonical ID
    # (which always contains a dot), then qualify, then lookup.
    resolver = registry.alias_resolver
    resolved_id = resolver.resolve(args.executor_id) if resolver else args.executor_id
    _require_qualified_id(resolved_id, "executor id")
    executor = registry.get(resolved_id)
    _require_pack_match(executor, getattr(args, "pack", None))
    show_overrides = bool(getattr(args, "show_overrides", False))
    if args.json:
        handle = to_capability_handle(executor)
        if resolver is not None:
            aliases = resolver.get_aliases_for(resolved_id)
            handle = replace(handle, aliases=tuple(aliases))
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
    _print_active_thread_footer()
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
            print(f"{executor_id}: missing binaries: {', '.join(missing)}", file=sys.stderr)
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
        print(shlex.join(command))
    return result.returncode


def _cmd_run(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    from .runner import ExecutorRunRequest, run_executor

    _require_qualified_id(args.executor_id, "executor id")
    executor = registry.get(args.executor_id)
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
        local_project = args.project
        if local_project and args.out:
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
        thread=args.thread,
        variants=args.variants,
        from_ref=args.from_ref,
    )
    result = run_executor(request, registry)
    if result.missing_binaries:
        print(f"{args.executor_id}: missing binaries: {', '.join(result.missing_binaries)}", file=sys.stderr)
        return 1
    if result.skipped:
        print(f"{args.executor_id}: skipped: {result.skipped_reason}")
        return 0
    if result.command:
        print(shlex.join(result.command))
    if result.payload:
        print(json.dumps(dict(result.payload), separators=(",", ":"), sort_keys=True))
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
    explicit bridge metadata, and does NOT call SupabaseDataProvider.save_timeline().
    The actual Supabase push is deferred to m6 (open_in_reigh bridge replay).

    When hype.timeline.json is present, emit JSON handoff metadata on stdout
    so downstream tooling can pick up the bridge intent.  When it is absent,
    log and return 0 (non-producing runs are valid handoffs).
    """
    timeline_path = out_dir / "hype.timeline.json"
    if not timeline_path.is_file():
        print(
            f"executors: --project {project_id} UUID mode: {timeline_path} not produced; "
            f"handoff complete (no timeline to bridge)",
            file=sys.stderr,
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
    if executor.id == "upload.youtube":
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


def _parse_input_values(raw_values: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in raw_values:
        if "=" not in raw:
            raise ValueError(f"invalid --input value {raw!r}; expected NAME=VALUE")
        key, value = raw.split("=", 1)
        key = key.strip().replace("-", "_")
        if not key:
            raise ValueError(f"invalid --input value {raw!r}; expected NAME=VALUE")
        if key in values:
            values[key] = f"{values[key]},{value}"
        else:
            values[key] = value
    return values


def _require_qualified_id(value: str, label: str) -> None:
    if "." not in value or any(not part for part in value.split(".")):
        raise ValueError(f"{label} must be qualified as <pack>.<name>")


def _example_path_for_port(port: Any) -> str:
    """Fix 6: render a plausible ``<path>`` placeholder for an input port.

    Uses the port name as the filename so the example looks like a real
    invocation; the suffix is best-effort based on the port type (image →
    .png, video → .mp4, audio → .wav, text → .txt, otherwise no suffix).
    """
    type_to_ext = {
        "image": ".png",
        "video": ".mp4",
        "audio": ".wav",
        "text": ".txt",
        "json": ".json",
        "directory": "",
        "dir": "",
    }
    port_type = getattr(port, "type", None) or ""
    suffix = type_to_ext.get(str(port_type).lower(), "")
    return f"/path/to/{port.name}{suffix}"


def _format_invocation_hint(verb: str, qid: str, inputs: tuple[Any, ...]) -> str:
    parts = [f"astrid {verb} run {qid}"]
    required = [port for port in inputs if getattr(port, "required", False)]
    for port in required[:3]:
        flag = str(getattr(port, "name", "input")).replace("_", "-")
        parts.append(f"--{flag} <path>")
    if len(required) > 3:
        parts.append("...")
    return " ".join(parts)


def _print_invocation_example(verb: str, qid: str, inputs: tuple[Any, ...]) -> None:
    """Fix 6 (v6 dogfood): the v5 cross-report flagged that agents read
    inputs/outputs from ``inspect`` and then guessed at the
    ``--input <port>=<path>`` syntax from ``run --help``. Append a
    synthesized example to the inspect output so the wiring is explicit.

    ``verb`` is ``"executors"`` or ``"orchestrators"``.
    """
    print()
    print("Example:")
    parts = [f"  astrid {verb} run {qid}"]
    for port in inputs:
        if not getattr(port, "required", False):
            continue
        parts.append(f"--input {port.name}={_example_path_for_port(port)}")
    parts.append("--out /path/to/output")
    print(" ".join(parts))


def _print_ports(label: str, ports: tuple[Any, ...]) -> None:
    if not ports:
        return
    print(f"{label}:")
    for port in ports:
        required = "required" if port.required else "optional"
        print(f"  - {port.name} ({port.type}, {required})")


def _print_outputs(executor: ExecutorDefinition) -> None:
    if not executor.outputs:
        return
    print("outputs:")
    for output in executor.outputs:
        placeholder = f", placeholder={output.placeholder}" if output.placeholder else ""
        print(f"  - {output.name} ({output.type}, {output.mode}{placeholder})")


def _print_active_thread_footer() -> None:
    try:
        import os

        from astrid._paths import REPO_ROOT
        from astrid.threads.index import ThreadIndexStore

        index = ThreadIndexStore(Path(os.environ.get("ASTRID_REPO_ROOT", REPO_ROOT))).read()
    except Exception:
        print("active_thread: unavailable")
        print("thread_details: python3 -m astrid thread show @active")
        return
    active = index.get("active_thread_id")
    thread = index.get("threads", {}).get(active) if isinstance(active, str) else None
    if isinstance(thread, dict):
        print(f"active_thread: {thread.get('label') or 'unlabeled'} ({active})")
    else:
        print("active_thread: none")
    print("thread_details: python3 -m astrid thread show @active")


def _cmd_override(args: argparse.Namespace, registry: ExecutorRegistry) -> int:
    store = registry.override_store
    if store is None:
        print("executors: override store not available", file=sys.stderr)
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
        print(f"executors override: unknown action {action!r}", file=sys.stderr)
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
        print(f"executors dirty: unknown action {action!r}", file=sys.stderr)
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
        print(f"executors update: unknown action {action!r}", file=sys.stderr)
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
