"""Canonical command-line interface for Astrid executors."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from astrid.core.contracts.errors import AstridError
from astrid.core.cli_choices import RecoverableArgumentParser, add_choice_arg
from astrid.core._shared.capability_common import (
    _aliases_text,          # re-export — tests import from cli directly
    _require_qualified_id,  # re-export — tests patch via cli.<name>
)
from astrid.core.pack.override import OverrideStore, OverrideStoreError
from astrid.core.project.run import ProjectRunError

from .registry import ExecutorRegistry, load_default_registry
from .schema import ExecutorValidationError

# ---------------------------------------------------------------------------
# Import all handlers from cli_handlers so build_parser() can wire them.
# Re-export every name that tests import directly from this module path
# (see docs/contracts/monkeypatch-contracts.md §7).
# ---------------------------------------------------------------------------
from .cli_handlers import (  # noqa: E402, F401  — re-exports for tests
    _cmd_fork,
    _cmd_new,
    _cmd_list,
    _cmd_search,
    _cmd_inspect,
    _cmd_validate,
    _cmd_install,
    _cmd_run,
    _cmd_override,
    _cmd_dirty,
    _cmd_update,
    _executor_search_record,
    _emit_uuid_handoff_metadata,
    _project_uuid_or_none,
    _UUID_RE,
    _executor_needs_out,
    _run_inputs,
    _parse_input_values,
    _reject_run_passthrough,
    _print_outputs,
    _EXECUTOR_YAML_TEMPLATE,
    _RUN_PY_TEMPLATE,
)


def _banodoco_config_from_args(
    args: argparse.Namespace,
    *,
    agent_flag: str = "banodoco_agent_executors",
):
    """Build a BanodocoCatalogConfig from CLI args and env.

    ``agent_flag`` is the arg attribute to check for per-capability-type
    override (``banodoco_agent_executors`` or ``banodoco_agent_orchestrators``).
    """
    from astrid.core.execution.executor.banodoco_catalog import BanodocoCatalogConfig

    env_config = BanodocoCatalogConfig.from_env()
    enabled = bool(getattr(args, agent_flag, False) or env_config.enabled)
    return BanodocoCatalogConfig(
        enabled=enabled,
        catalog_url=args.banodoco_catalog_url or env_config.catalog_url,
        include_defaults=False if args.no_banodoco_defaults else env_config.include_defaults,
        include_mandatory=False if args.no_banodoco_mandatory else env_config.include_mandatory,
        cache_dir=Path(args.banodoco_cache_dir).expanduser() if args.banodoco_cache_dir else env_config.cache_dir,
        refresh=bool(args.banodoco_refresh or env_config.refresh),
        timeout_seconds=env_config.timeout_seconds,
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


if __name__ == "__main__":
    raise SystemExit(main())
