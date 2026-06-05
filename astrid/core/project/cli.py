"""Command-line interface for Astrid projects.

T10 collapsed the parallel placement schema. T11 reinstates ``edit
<project_id>`` (sub-verbs ``add-clip``/``move-clip``/``set-theme``) and
``list <project_id>`` that operate on reigh-app UUIDs through
``astrid.core.reigh.SupabaseDataProvider``. Edit verbs shell out to
``scripts/node/ops_helper.mjs`` to apply timeline-ops primitives, then call
``SupabaseDataProvider.save_timeline`` with the required
``expected_version`` (read from reigh-data-fetch's ``config_version``).

Auth scope (FLAG-012, SD-009): the CLI is an ownership-bound client, so the
write path uses a user PAT (``REIGH_PAT``) by default rather than the
worker-only service-role key. ``--service-role`` is provided as a documented
escape hatch for operators who know the row is theirs to edit; the worker
itself uses a separate code path (``astrid.core.worker.banodoco_worker``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any, TypedDict

from astrid.contracts.errors import AstridError, coerce_astrid_error
from astrid.core.cli_choices import RecoverableArgumentParser, add_choice_arg
from astrid.core.session.binding import (
    SessionBindingError,
    resolve_current_session,
)
from astrid.core.session.config import (
    load_user_config,
    load_workspace_config,
    resolve_default_project,
    set_default_project,
)
from astrid.core.session.discovery import discover_projects
from astrid.core.util.log_and_swallow import log_and_swallow

from . import paths
from .project import ProjectError, create_project, require_project, show_project
from .schema import SOURCE_KINDS
from .source import add_source


REPO_ROOT = Path(__file__).resolve().parents[3]
OPS_HELPER = REPO_ROOT / "scripts" / "node" / "ops_helper.mjs"


class OpsHelperResponse(TypedDict):
    timeline: dict[str, Any]
    event_descriptor: dict[str, Any]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except ProjectError as exc:
        raise coerce_astrid_error(exc) from exc
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        raise AstridError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = RecoverableArgumentParser(
        prog="python3 -m astrid projects",
        description="Create, inspect, and manage persistent Astrid projects.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a project.")
    create_parser.add_argument("slug")
    create_parser.add_argument("--name")
    create_parser.add_argument(
        "--project-id",
        dest="project_id",
        help="Optional reigh-app project UUID (stored opaque in project.json).",
    )
    create_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    create_parser.set_defaults(handler=_cmd_create)

    ls_parser = subparsers.add_parser("ls", help="List local Astrid projects.")
    ls_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    ls_parser.set_defaults(handler=_cmd_ls)

    default_parser = subparsers.add_parser("default", help="Show, set, or clear the default project.")
    default_parser.add_argument("slug", nargs="?", help="Project slug to remember as the default.")
    default_parser.add_argument("--clear", action="store_true", help="Clear the configured default project.")
    default_parser.add_argument(
        "--user",
        action="store_true",
        help="Write the user-wide default instead of the workspace default.",
    )
    default_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    default_parser.set_defaults(handler=_cmd_default)

    show_parser = subparsers.add_parser("show", help="Show a project tree.")
    _add_project_arg(show_parser)
    show_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    show_parser.set_defaults(handler=_cmd_show)

    source_parser = subparsers.add_parser("source", help="Manage project sources.")
    source_subparsers = source_parser.add_subparsers(dest="source_command", required=True)
    source_add = source_subparsers.add_parser("add", help="Add a source to a project.")
    _add_project_arg(source_add)
    source_add.add_argument("source_id")
    asset_group = source_add.add_mutually_exclusive_group(required=True)
    asset_group.add_argument("--file", dest="file_path", help="Local source media file.")
    asset_group.add_argument("--url", help="Remote http(s) source media URL.")
    add_choice_arg(
        source_add,
        "--kind",
        values=sorted(SOURCE_KINDS),
        help="Source media kind.",
    )
    source_add.add_argument("--type", help="Asset type such as video/mp4, image/png, or audio/mpeg.")
    source_add.add_argument("--duration", type=float, help="Asset duration in seconds.")
    source_add.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    source_add.set_defaults(handler=_cmd_source_add)

    list_parser = subparsers.add_parser(
        "list",
        help="List timelines on a reigh-app project (project_id UUID).",
    )
    list_parser.add_argument("project_id", help="reigh-app project UUID.")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(handler=_cmd_list)

    edit_parser = subparsers.add_parser(
        "edit",
        help="Edit a reigh-app timeline via timeline-ops primitives + SupabaseDataProvider.",
    )
    edit_parser.add_argument("project_id", help="reigh-app project UUID.")
    edit_parser.add_argument("--timeline-id", required=True, help="reigh-app timeline UUID.")
    edit_parser.add_argument(
        "--service-role",
        action="store_true",
        help="Worker-only escape hatch: authenticate via REIGH_SUPABASE_SERVICE_ROLE_KEY.",
    )
    edit_parser.add_argument("--json", action="store_true")
    edit_subparsers = edit_parser.add_subparsers(dest="edit_op", required=True)

    add_clip = edit_subparsers.add_parser("add-clip", help="Insert a clip via timeline-ops.addClip.")
    add_clip.add_argument("--clip-json", required=True, help="JSON object describing the clip.")
    add_clip.add_argument("--position", type=int, help="Insertion index (default: append).")
    add_clip.set_defaults(handler=_cmd_edit, edit_op_name="add-clip")

    move_clip = edit_subparsers.add_parser("move-clip", help="Reposition a clip via timeline-ops.moveClip.")
    move_clip.add_argument("--clip-id", required=True)
    move_clip.add_argument("--new-position", required=True, type=float, help="New start time in seconds.")
    move_clip.set_defaults(handler=_cmd_edit, edit_op_name="move-clip")

    set_theme = edit_subparsers.add_parser("set-theme", help="Set the active theme via timeline-ops.setTimelineTheme.")
    set_theme.add_argument("--theme-id", required=True)
    set_theme.set_defaults(handler=_cmd_edit, edit_op_name="set-theme")

    # --- cost (Sprint 5b) ---
    cost_parser = subparsers.add_parser("cost", help="Show cost rollup for a project.")
    _add_project_arg(cost_parser)
    cost_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON instead of pretty-print.",
    )
    cost_parser.add_argument(
        "--include-aborted",
        action="store_true",
        help="Include aborted runs in the cost rollup.",
    )
    cost_parser.set_defaults(handler=_cmd_project_cost)

    # --- export (Sprint 5b) ---
    export_parser = subparsers.add_parser("export", help="Export a project bundle.")
    _add_project_arg(export_parser)
    export_parser.add_argument("--out", required=True, help="Output tarball path (.tar.gz).")
    export_parser.add_argument(
        "--include-aborted",
        action="store_true",
        help="Include aborted runs in the export bundle.",
    )
    export_parser.set_defaults(handler=_cmd_project_export)

    return parser


def _add_project_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", required=True, help="Project slug.")


def _cmd_create(args: argparse.Namespace) -> int:
    project = create_project(args.slug, name=args.name, project_id=getattr(args, "project_id", None))
    if args.json:
        _print_json({"project": project, "root": str(paths.project_dir(project["slug"]))})
        return 0
    _print_project_header(project["slug"])
    print(f"created: {project['name']}")
    if project.get("project_id"):
        print(f"project_id: {project['project_id']}")
    print(f"next: python3 -m astrid attach {project['slug']} --default")
    return 0


def _cmd_ls(args: argparse.Namespace) -> int:
    projects = discover_projects()
    default = resolve_default_project()
    default_is_available = bool(default and default in projects)
    if args.json:
        _print_json(
            {
                "default_project": default,
                "default_available": default_is_available,
                "projects": projects,
            }
        )
        return 0
    if default_is_available:
        print(f"default project: {default}")
    elif default:
        print(f"configured default project: {default} (not found under current projects root)")
    if not projects:
        print("no projects discovered under the projects root")
        print("create one with: python3 -m astrid projects create <slug>")
        return 0
    print("projects:")
    for slug in projects:
        marker = " *" if slug == default and default_is_available else ""
        print(f"  {slug}{marker}")
    print("attach:")
    if default_is_available:
        print("  python3 -m astrid attach")
    print("  python3 -m astrid attach <project>")
    return 0


def _cmd_default(args: argparse.Namespace) -> int:
    if args.clear and args.slug:
        raise ValueError("pass either a project slug or --clear, not both")
    scope = "user" if args.user else "workspace"
    if args.clear:
        path = set_default_project(None, scope=scope)
        if args.json:
            _print_json({"default_project": None, "scope": scope, "path": str(path)})
            return 0
        print(f"cleared default project ({scope})")
        return 0
    if not args.slug:
        default = resolve_default_project()
        if args.json:
            projects = discover_projects()
            _print_json(
                {
                    "default_project": default,
                    "default_available": bool(default and default in projects),
                }
            )
            return 0
        print(f"default project: {default or '(none)'}")
        if default is None:
            projects = discover_projects()
            if projects:
                print(f"set one with: python3 -m astrid projects default {projects[0]}")
            else:
                print("no projects discovered under the projects root")
        else:
            projects = discover_projects()
            if default not in projects:
                print("warning: configured default project is not under the current projects root")
                workspace_default = load_workspace_config().get("default_project")
                user_default = load_user_config().get("default_project")
                if workspace_default == default and user_default and user_default != default:
                    print("clear workspace default to use the user default:")
                    print("  python3 -m astrid projects default --clear")
                elif projects:
                    print(f"choose an available project with: python3 -m astrid projects default {projects[0]}")
                else:
                    print("create one with: python3 -m astrid projects create <slug>")
        return 0
    require_project(args.slug)
    path = set_default_project(args.slug, scope=scope)
    if args.json:
        _print_json({"default_project": args.slug, "scope": scope, "path": str(path)})
        return 0
    print(f"default project ({scope}): {args.slug}")
    print("attach with: python3 -m astrid attach")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    project = require_project(args.project)
    payload = show_project(args.project)
    if args.json:
        _print_json(payload)
        return 0
    _print_project_header(project["slug"])
    _print_project_tree(payload)
    return 0


def _cmd_source_add(args: argparse.Namespace) -> int:
    require_project(args.project)
    asset: dict[str, Any] = {}
    if args.file_path:
        asset["file"] = args.file_path
    if args.url:
        asset["url"] = args.url
    if args.type:
        asset["type"] = args.type
    if args.duration is not None:
        asset["duration"] = args.duration
    source = add_source(args.project, args.source_id, asset=asset, kind=args.kind)
    if args.json:
        _print_json({"source": source})
        return 0
    _print_project_header(args.project)
    print(f"source: {source['source_id']}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    """List timelines for a reigh-app project via reigh-data-fetch."""

    from astrid.core.reigh import env as reigh_env
    from astrid.core.reigh.supabase_client import post_json

    auth = ("pat", reigh_env.resolve_pat())
    payload = post_json(
        reigh_env.resolve_api_url(),
        {"project_id": args.project_id},
        auth=auth,
    )
    timelines = []
    if isinstance(payload, dict):
        raw = payload.get("timelines")
        if isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                timelines.append(
                    {
                        "id": entry.get("id"),
                        "name": entry.get("name"),
                        "config_version": entry.get("config_version"),
                        "updated_at": entry.get("updated_at"),
                    }
                )
    if args.json:
        _print_json({"project_id": args.project_id, "timelines": timelines})
        return 0
    print(f"project_id: {args.project_id}")
    if not timelines:
        print("timelines: none")
        return 0
    print("timelines:")
    for entry in timelines:
        print(f"  - {entry['id']} v={entry.get('config_version')} name={entry.get('name')}")
    return 0


def _cmd_edit(args: argparse.Namespace) -> int:
    """Edit a reigh-app timeline via timeline-ops + SupabaseDataProvider."""

    from astrid.core.reigh import env as reigh_env
    from astrid.core.reigh.data_provider import SupabaseDataProvider

    op = args.edit_op_name
    op_args = _build_op_args(args, op)

    if not OPS_HELPER.is_file():
        raise ProjectError(f"ops helper missing: {OPS_HELPER}")
    if shutil.which("node") is None:
        raise ProjectError("node executable not found on PATH; install Node 20+ to run edit verbs")

    provider = SupabaseDataProvider.from_env()
    if args.service_role:
        write_auth = ("service_role", reigh_env.resolve_service_role_key())
    else:
        write_auth = ("pat", reigh_env.resolve_pat())

    # First load to know expected_version (the mutator path will re-fetch on
    # conflict, but we need a starting version to satisfy the
    # save_timeline contract).
    _, current_version = provider.load_timeline(args.project_id, args.timeline_id)
    helper_response: OpsHelperResponse | None = None

    def mutator(config: dict[str, Any], version: int) -> dict[str, Any]:
        nonlocal helper_response
        helper_response = _run_ops_helper(config, version, op, op_args)
        return helper_response["timeline"]

    result = provider.save_timeline(
        args.timeline_id,
        mutator,
        project_id=args.project_id,
        auth=write_auth,
        expected_version=current_version,
        retries=3,
        force=False,
    )
    if args.json:
        _print_json(
            {
                "timeline_id": args.timeline_id,
                "project_id": args.project_id,
                "op": op,
                "new_version": result.new_version,
                "attempts": result.attempts,
                "event_descriptor": helper_response["event_descriptor"] if helper_response else None,
            }
        )
        return 0
    print(
        f"edited timeline {args.timeline_id} project_id={args.project_id} "
        f"op={op} new_version={result.new_version} attempts={result.attempts}"
    )
    if helper_response is not None:
        print(f"event_descriptor: {json.dumps(helper_response['event_descriptor'], sort_keys=True)}")
    return 0


def _build_op_args(args: argparse.Namespace, op: str) -> dict[str, Any]:
    if op == "add-clip":
        try:
            clip = json.loads(args.clip_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--clip-json must be valid JSON: {exc.msg}") from exc
        if not isinstance(clip, dict):
            raise ValueError("--clip-json must decode to a JSON object")
        body: dict[str, Any] = {"clip": clip}
        if args.position is not None:
            body["position"] = args.position
        return body
    if op == "move-clip":
        return {"clipId": args.clip_id, "newPosition": args.new_position}
    if op == "set-theme":
        return {"themeId": args.theme_id}
    raise ValueError(f"unsupported edit op: {op}")


def _run_ops_helper(
    timeline: dict[str, Any],
    version: int,
    op: str,
    op_args: dict[str, Any],
) -> OpsHelperResponse:
    request = json.dumps({"timeline": timeline, "version": version, "op": op, "args": op_args})
    completed = subprocess.run(
        ["node", str(OPS_HELPER)],
        input=request,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or "ops_helper exited non-zero"
        raise ProjectError(f"ops_helper failed: {stderr}")
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ProjectError(f"ops_helper produced non-JSON stdout: {exc.msg}") from exc
    timeline_out = response.get("timeline")
    if not isinstance(timeline_out, dict):
        raise ProjectError("ops_helper response missing .timeline object")
    event_descriptor = response.get("event_descriptor")
    if event_descriptor is None:
        event_descriptor = _synthesize_event_descriptor(op, op_args, response.get("detail"))
    if not isinstance(event_descriptor, dict):
        raise ProjectError("ops_helper response missing .event_descriptor object")
    kind = event_descriptor.get("kind")
    payload = event_descriptor.get("payload")
    if not isinstance(kind, str) or not kind:
        raise ProjectError("ops_helper event_descriptor.kind must be a non-empty string")
    if not isinstance(payload, dict):
        raise ProjectError("ops_helper event_descriptor.payload must be an object")
    return {
        "timeline": timeline_out,
        "event_descriptor": event_descriptor,
    }


def _synthesize_event_descriptor(
    op: str,
    op_args: dict[str, Any],
    detail: Any,
) -> dict[str, Any]:
    """Compatibility bridge for pre-event_descriptor helper outputs."""
    if op == "add-clip":
        clip = op_args.get("clip")
        if isinstance(clip, dict):
            return {
                "kind": "clip.added",
                "payload": {
                    "clip_id": clip.get("id"),
                    "kind": clip.get("kind", clip.get("clipType")),
                    "track_id": clip.get("track", clip.get("track_id")),
                    "asset_id": clip.get("asset", clip.get("assetId", clip.get("asset_id"))),
                    "position": (
                        {"mode": "index", "index": op_args["position"]}
                        if isinstance(op_args.get("position"), int)
                        else None
                    ),
                },
            }
    if op == "move-clip":
        return {
            "kind": "clip.moved",
            "payload": {
                "clip_id": op_args.get("clipId"),
                "position": (
                    {"mode": "index", "index": op_args["newPosition"]}
                    if isinstance(op_args.get("newPosition"), (int, float))
                    else None
                ),
            },
        }
    if op == "set-theme":
        return {
            "kind": "theme.set",
            "payload": {
                "theme_id": op_args.get("themeId"),
                "detail": detail if isinstance(detail, dict) else None,
            },
        }
    raise ProjectError(f"ops_helper response missing event_descriptor for unsupported op: {op}")


# ---------------------------------------------------------------------------
# Handler: project cost (Sprint 5b T8)
# ---------------------------------------------------------------------------


def _cmd_project_cost(args: argparse.Namespace) -> int:
    """Aggregate cost across all timelines in a project."""
    _require_project_session(args.project)

    from astrid.core.project.paths import project_dir
    from astrid.core.task.events import read_events
    from astrid.core.task.run_audit import _cost_by_source, _run_status
    from astrid.core.timeline.crud import list_timelines

    include_aborted = bool(getattr(args, "include_aborted", False))
    json_out = bool(getattr(args, "json", False))

    proj_root = project_dir(args.project)
    runs_dir = proj_root / "runs"

    timelines = list_timelines(args.project)
    if not timelines:
        if json_out:
            _print_json({"project": args.project, "grand_total": 0.0, "by_source": {}, "timeline_count": 0})
            return 0
        print(f"Project cost for '{args.project}': no timelines found")
        return 0

    # Collect unique contributing runs across all timelines
    seen_runs: set[str] = set()
    run_ids: list[str] = []
    for ts in timelines:
        try:
            from astrid.core.timeline.model import Manifest as TLManifest
            mp = project_dir(args.project) / "timelines" / ts.ulid / "manifest.json"
            if mp.is_file():
                manifest = TLManifest.from_json(mp)
                for rid in manifest.contributing_runs:
                    if rid not in seen_runs:
                        seen_runs.add(rid)
                        run_ids.append(rid)
        except Exception as exc:  # noqa: BLE001
            log_and_swallow(exc, context="project.cost.timeline_scan")
            continue

    # Aggregate costs across runs
    by_source: dict[str, dict[str, Any]] = {}
    grand_total = 0.0
    selected_run_ids = _project_selected_runs(
        runs_dir,
        run_ids,
        include_aborted=include_aborted,
    )

    for run_id in selected_run_ids:
        events = read_events(runs_dir / run_id / "events.jsonl")
        cost_summary = _cost_by_source(events)

        # Ledger fallback: when events provide no usable cost, read
        # cost_usd from run.json metadata (set during finalization).
        if not cost_summary:
            run_json = _read_run_json_for_cost(runs_dir / run_id / "run.json")
            ledger_cost = _extract_ledger_cost_usd(run_json)
            if ledger_cost is not None:
                cost_summary = {
                    "ledger": {
                        "amount": ledger_cost,
                        "currency": "USD",
                        "source": "ledger",
                    }
                }

        grand_total += _merge_project_cost_summaries(by_source, cost_summary)

    if json_out:
        payload: dict[str, Any] = {
            "project": args.project,
            "timeline_count": len(timelines),
            "contributing_runs": len(selected_run_ids),
            "include_aborted": include_aborted,
            "grand_total": round(grand_total, 6),
            "by_source": by_source,
        }
        _print_json(payload)
        return 0

    print(f"Cost rollup for project '{args.project}' ({len(timelines)} timelines, {len(selected_run_ids)} contributing runs):")
    print()
    if not by_source:
        print("  (no cost data)")
    else:
        for source in sorted(by_source):
            amt = float(by_source[source].get("amount", 0.0))
            print(f"  {source:<20} ${amt:>10.4f}")
    print(f"  {'─' * 32}")
    print(f"  {'TOTAL':<20} ${grand_total:>10.4f}")
    return 0


# ---------------------------------------------------------------------------
# Handler: project export (Sprint 5b T9)
# ---------------------------------------------------------------------------


def _cmd_project_export(args: argparse.Namespace) -> int:
    """Export a project as a self-contained tarball bundle."""
    _require_project_session(args.project)

    from astrid.core.project.paths import project_dir
    from astrid.core.task.events import read_events
    from astrid.core.task.run_audit import _run_status
    from astrid.core.timeline.crud import list_timelines

    include_aborted = bool(getattr(args, "include_aborted", False))
    out_path = Path(args.out).expanduser().resolve()
    proj_root = project_dir(args.project)
    runs_dir = proj_root / "runs"

    timelines = list_timelines(args.project)

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        manifest_entries: list[tuple[str, str]] = []

        def _add_file(src: Path, rel: str) -> None:
            dst = tmpdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            sha = hashlib.sha256(dst.read_bytes()).hexdigest()
            manifest_entries.append((rel, sha))

        def _add_bytes(data: bytes, rel: str) -> None:
            dst = tmpdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            manifest_entries.append((rel, sha))

        # Collect unique contributing runs across all timelines
        seen_runs: set[str] = set()
        all_run_ids: list[str] = []
        for ts in timelines:
            # Repair assembly.json from the event log before copying (ensures
            # the exported tarball carries the current projected state).
            tdir = proj_root / "timelines" / ts.ulid
            try:
                from astrid.core.timeline.paths import load_assembly_json_with_repair
                load_assembly_json_with_repair(tdir)
            except Exception as exc:  # noqa: BLE001
                log_and_swallow(exc, context="project.export.timeline_repair")

            # Copy timeline container files
            for name in ("assembly.json", "manifest.json", "display.json"):
                src = tdir / name
                if src.is_file():
                    _add_file(src, f"timelines/{ts.ulid}/{name}")

            # Collect run IDs
            try:
                from astrid.core.timeline.model import Manifest as TLManifest
                mp = tdir / "manifest.json"
                if mp.is_file():
                    manifest = TLManifest.from_json(mp)
                    for rid in manifest.contributing_runs:
                        if rid not in seen_runs:
                            seen_runs.add(rid)
                            all_run_ids.append(rid)
            except Exception as exc:  # noqa: BLE001
                log_and_swallow(exc, context="project.export.run_id_collection")
                continue

        # Copy project-level files
        project_json = proj_root / "project.json"
        if project_json.is_file():
            _add_file(project_json, "project.json")

        # Copy contributing runs
        for run_id in _project_selected_runs(
            runs_dir,
            all_run_ids,
            include_aborted=include_aborted,
        ):
            run_root = runs_dir / run_id
            if not run_root.is_dir():
                continue

            # Copy the run's own plan snapshot. Older runs may only have the
            # initial plan embedded in events.jsonl; export that snapshot
            # rather than the mutable project-level plan cache.
            plan_path = run_root / "plan.json"
            if plan_path.is_file():
                _add_file(plan_path, f"runs/{run_id}/plan.json")
            else:
                plan_payload = _run_initial_plan_payload(run_root / "events.jsonl")
                if plan_payload is not None:
                    data = json.dumps(
                        plan_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    _add_bytes(
                        data,
                        f"runs/{run_id}/plan.json",
                    )

            # Copy events.jsonl
            events_path = run_root / "events.jsonl"
            if events_path.is_file():
                _add_file(events_path, f"runs/{run_id}/events.jsonl")

            # Copy produces/ tree
            produces_root = run_root / "produces"
            if produces_root.is_dir():
                for src_file in produces_root.rglob("*"):
                    if src_file.is_file():
                        rel = str(Path("runs") / run_id / "produces" / src_file.relative_to(produces_root))
                        _add_file(src_file, rel)

            # Copy run.json if present
            run_json = run_root / "run.json"
            if run_json.is_file():
                _add_file(run_json, f"runs/{run_id}/run.json")

            # Bundle the executor manifest. Prefer the path recorded in
            # run.json (manifest_path) when it points to a valid file;
            # otherwise fall back to manifest.json under the run root.
            manifest_src: Path | None = None
            if run_json.is_file():
                try:
                    run_record = json.loads(run_json.read_text(encoding="utf-8"))
                except Exception:
                    run_record = {}
                mp = run_record.get("manifest_path")
                if isinstance(mp, str) and mp:
                    candidate = Path(mp).expanduser().resolve()
                    if candidate.is_file():
                        manifest_src = candidate
            if manifest_src is None:
                fallback = run_root / "manifest.json"
                if fallback.is_file():
                    manifest_src = fallback
            if manifest_src is not None:
                _add_file(manifest_src, f"runs/{run_id}/manifest.json")

        # Write MANIFEST.txt
        manifest_txt = tmpdir / "MANIFEST.txt"
        lines = [f"{sha}  {rel}" for rel, sha in sorted(manifest_entries)]
        manifest_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Build tarball
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(out_path, "w:gz") as tar:
            for member in sorted(tmpdir.iterdir()):
                tar.add(member, arcname=member.name)

    print(f"exported project '{args.project}' to {out_path}")
    return 0


def _run_initial_plan_payload(events_path: Path) -> dict[str, object] | None:
    if not events_path.is_file():
        return None
    from astrid.core.task.events import read_events

    for event in read_events(events_path):
        if event.get("kind") == "plan_initialized" and isinstance(
            event.get("plan"), dict
        ):
            return event["plan"]
    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SESSION_GATE_HINT = (
    "A project command requires a bound session. "
    "Run 'astrid attach <project>' first."
)


def _require_project_session(project_slug: str) -> None:
    # T9 / FLAG-S1-003: plumb slug for file-bound .astrid-session fallback.
    session = resolve_current_session(slug=project_slug)
    if session is None:
        raise SessionBindingError(_SESSION_GATE_HINT)


def _project_selected_runs(
    runs_dir: Path,
    run_ids: list[str],
    *,
    include_aborted: bool,
) -> list[str]:
    from astrid.core.task.events import read_events
    from astrid.core.task.run_audit import _run_status

    selected: list[str] = []
    for run_id in run_ids:
        run_root = runs_dir / run_id
        if not run_root.is_dir():
            continue
        events_path = run_root / "events.jsonl"
        if events_path.exists():
            events = read_events(events_path)
            if _run_status(events) == "aborted" and not include_aborted:
                continue
        selected.append(run_id)
    return selected


def _merge_project_cost_summaries(
    target: dict[str, dict[str, Any]],
    incoming: dict[str, dict[str, Any]],
) -> float:
    added_total = 0.0
    for source, info in incoming.items():
        if not isinstance(info, dict):
            continue
        amount = float(info.get("amount", 0.0))
        currency = str(info.get("currency", "USD"))
        bucket = target.setdefault(
            source,
            {"amount": 0.0, "currency": currency, "source": source},
        )
        bucket["amount"] = round(float(bucket.get("amount", 0.0)) + amount, 6)
        bucket["currency"] = currency
        bucket["source"] = source
        added_total += amount
    return added_total


def _read_run_json_for_cost(path: Path) -> dict[str, Any]:
    """Read a run.json file for cost fallback purposes."""
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return loaded
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _extract_ledger_cost_usd(record: dict[str, Any]) -> float | None:
    """Extract a numeric ``cost_usd`` from run record metadata."""
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("cost_usd")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _print_project_header(slug: str) -> None:
    print(f"Project: {slug}")
    print(f"Root: {paths.project_dir(slug)}")


def _print_project_tree(payload: dict[str, Any]) -> None:
    project = payload["project"]
    print(f"{project['slug']}/")
    print("  project.json")
    print("  sources/")
    for source_id in payload.get("sources", []):
        print(f"    {source_id}/")
        print("      source.json")
        print("      analysis/")
    print("  runs/")
    for run_id in payload.get("runs", []):
        print(f"    {run_id}/")
        print("      run.json")
        print("      assets.json")
        print("      metadata.json")
    # Sprint 2: timelines as first-class containers.
    try:
        from astrid.core.timeline import crud as timeline_crud
        summaries = timeline_crud.list_timelines(payload["project"]["slug"])
    except Exception:  # noqa: BLE001
        summaries = []
    if summaries:
        print("  timelines/")
        for t in summaries:
            print(f"    {t.ulid}/  (slug: {t.slug}, name: {t.name})")
            print("      assembly.json")
            print("      manifest.json")
            print("      display.json")
    if payload.get("project_id"):
        print(f"reigh project_id: {payload['project_id']}")


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))
