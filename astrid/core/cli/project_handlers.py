"""Command handlers for Astrid project CLI.

Extracted from cli.py (structural split P5-3).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, TypedDict

from astrid.core.contracts.errors import AstridError
from astrid.core.foundation import project_paths as paths
from astrid.core.project.project import (
    ProjectError,
    create_project,
    get_project_theme,
    register_source_file,
    require_project,
    set_project_theme,
    show_project,
    update_project_details,
)
from astrid.core.project.guidance import project_summaries, selected_project
from astrid.core.project.source import add_source
from astrid.core.session.binding import SESSION_FILE_NAME, resolve_current_session
from astrid.core.session.config import (
    load_user_config,
    load_workspace_config,
    resolve_default_project,
    set_default_project,
)
from astrid.core.session.discovery import discover_projects

REPO_ROOT = Path(__file__).resolve().parents[3]
OPS_HELPER = REPO_ROOT / "scripts" / "node" / "ops_helper.mjs"


class OpsHelperResponse(TypedDict):
    timeline: dict[str, Any]
    event_descriptor: dict[str, Any]




def _cmd_create(args: argparse.Namespace) -> int:
    project = create_project(
        args.slug,
        name=args.name,
        description=getattr(args, "description", None),
        project_id=getattr(args, "project_id", None),
    )
    if getattr(args, "default", False):
        set_default_project(project["slug"], scope="workspace")
    if getattr(args, "attach", False):
        return _select_project_session(
            project["slug"],
            default=False,
            json_mode=bool(args.json),
        )
    if args.json:
        _print_json(
            {
                "project": project,
                "root": str(paths.project_dir(project["slug"])),
                "attached": False,
                "default_project": bool(getattr(args, "default", False)),
            }
        )
        return 0
    _print_project_header(project["slug"])
    print(f"created: {project['name']}")
    if project.get("description"):
        print(f"description: {project['description']}")
    if project.get("project_id"):
        print(f"project_id: {project['project_id']}")
    if getattr(args, "default", False):
        print(f"default suggestion: {project['slug']}")
    print(f"next: astrid projects select {project['slug']}")
    return 0


def _cmd_ls(args: argparse.Namespace) -> int:
    summaries = project_summaries(
        include_test_projects=bool(getattr(args, "all", False))
    )
    projects = [row["slug"] for row in summaries]
    selected, selected_source = selected_project(None)
    default = resolve_default_project()
    default_is_available = bool(default and default in projects)
    if args.json:
        _print_json(
            {
                "default_project": default,
                "default_available": default_is_available,
                "selected_project": selected,
                "selection_source": selected_source,
                "projects": projects,
                "project_summaries": summaries,
                "project_themes": {
                    row["slug"]: row["theme"] or None for row in summaries
                },
            }
        )
        return 0
    if default_is_available:
        print(f"default project: {default}")
    elif default:
        print(f"configured default project: {default} (not found under current projects root)")
    if not projects:
        print("no projects discovered under the projects root")
        print('create one with: astrid projects create <slug> --description "…" --attach')
        return 0
    print("projects (most recently active first):")
    for row in summaries:
        markers: list[str] = []
        if row["slug"] == selected:
            markers.append("selected")
        if row["is_default"]:
            markers.append("configured default")
        marker = f" [{', '.join(markers)}]" if markers else ""
        name = f" — {row['name']}" if row["name"] != row["slug"] else ""
        theme = f"  (theme: {row['theme']})" if row["theme"] else ""
        print(f"  {row['slug']}{theme}{name}{marker}")
        if row["description"]:
            print(f"    {row['description']}")
        print(
            f"    {row['runs']} runs · {row['timelines']} timelines · "
            f"{row['experiments']} experiments"
        )
        print(f"    select: astrid projects select {row['slug']}")
    print()
    print("select:")
    print("  astrid projects select <project>         # for this session")
    print("  <command> --project <project>            # for one operation")
    print()
    print("create:")
    print('  astrid projects create <slug> --description "…" --attach')
    if not getattr(args, "all", False):
        print()
        print("show test projects too: astrid projects ls --all")
    return 0


def _cmd_select(args: argparse.Namespace) -> int:
    """Friendly project-selection alias over the session attach primitive."""

    require_project(args.slug)
    return _select_project_session(
        args.slug,
        default=bool(args.default),
        json_mode=bool(args.json),
    )


def _select_project_session(
    slug: str,
    *,
    default: bool,
    json_mode: bool,
) -> int:
    """Attach *slug* and make its pointer the unambiguous CLI fallback."""

    from astrid.core.cli import session as session_cli

    attach_argv = ["attach", slug]
    if default:
        attach_argv.append("--default")
    if json_mode:
        attach_argv.append("--json")
    attach_args = session_cli.build_parser().parse_args(attach_argv)
    result = int(session_cli.cmd_attach(attach_args))
    if result == 0:
        _clear_other_project_session_pointers(slug)
    return result


def _clear_other_project_session_pointers(selected_slug: str) -> None:
    """Keep cross-process selection deterministic without deleting sessions."""

    for slug in discover_projects(root=paths.resolve_projects_root()):
        if slug == selected_slug:
            continue
        pointer = paths.project_dir(slug) / SESSION_FILE_NAME
        try:
            pointer.unlink(missing_ok=True)
        except OSError:
            # Selection already succeeded. A stale pointer only makes fallback
            # fail closed later; it must not roll back the live session.
            continue


def _cmd_update(args: argparse.Namespace) -> int:
    project = update_project_details(
        args.slug,
        name=args.name,
        description=args.description,
    )
    if args.json:
        _print_json({"project": project})
        return 0
    _print_project_header(project["slug"])
    print(f"name: {project['name']}")
    print(f"description: {project.get('description') or '(none)'}")
    return 0


def _cmd_default(args: argparse.Namespace) -> int:
    if args.clear and args.slug:
        raise AstridError(
            "pass either a project slug or --clear, not both",
            recovery_command="python3 -m astrid projects default --help",
        )
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
                    print('create one with: astrid projects create <slug> --description "…" --attach')
        return 0
    require_project(args.slug)
    path = set_default_project(args.slug, scope=scope)
    if args.json:
        _print_json({"default_project": args.slug, "scope": scope, "path": str(path)})
        return 0
    print(f"default project ({scope}): {args.slug}")
    print(f"select it with: astrid projects select {args.slug}")
    return 0


def _cmd_theme(args: argparse.Namespace) -> int:
    slug = args.slug or _bound_project_slug()
    if slug is None:
        raise AstridError(
            "project slug is required when no session is bound",
            recovery_command="python3 -m astrid projects theme --project <slug>",
        )
    require_project(slug)
    if args.clear:
        project = set_project_theme(slug, None)
    elif args.theme is not None:
        project = set_project_theme(slug, args.theme)
    else:
        project = require_project(slug)
    theme = project.get("theme")
    if args.json:
        _print_json({"project": slug, "theme": theme})
        return 0
    print(f"project: {slug}")
    print(f"theme: {theme or '(none)'}")
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
    source = add_source(args.project, args.source_id, asset=asset, kind=args.kind, exist_ok=bool(getattr(args, "force", False)))
    if args.json:
        _print_json({"source": source})
        return 0
    _print_project_header(args.project)
    print(f"source: {source['source_id']}")
    return 0


def _cmd_register_source(args: argparse.Namespace) -> int:
    project_slug = args.project
    if not project_slug:
        session = resolve_current_session()
        if session is None:
            raise AstridError(
                "--project is required when no session is bound",
                recovery_command="python3 -m astrid projects source register --project <slug> <file>",
            )
        project_slug = session.project
    source = register_source_file(project_slug, args.filename)
    if args.json:
        _print_json({"source": source})
        return 0
    _print_project_header(project_slug)
    print(f"source: {source['source_id']}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    """List timelines for a reigh-app project via reigh-data-fetch."""

    from astrid.core.integrations.reigh import env as reigh_env
    from astrid.core.integrations.reigh.supabase_client import post_json

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

    from astrid.core.integrations.reigh import env as reigh_env
    from astrid.core.integrations.reigh.data_provider import SupabaseDataProvider

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
        use_append_transport=False,
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
            raise AstridError(
                f"--clip-json must be valid JSON: {exc.msg}",
                recovery_command="python3 -m astrid projects edit --help",
            ) from exc
        if not isinstance(clip, dict):
            raise AstridError(
                "--clip-json must decode to a JSON object",
                recovery_command="python3 -m astrid projects edit --help",
            )
        body: dict[str, Any] = {"clip": clip}
        if args.position is not None:
            body["position"] = args.position
        return body
    if op == "move-clip":
        return {"clipId": args.clip_id, "newPosition": args.new_position}
    if op == "set-theme":
        return {"themeId": args.theme_id}
    raise AstridError(
        f"unsupported edit op: {op}",
        recovery_command="python3 -m astrid projects edit --help",
    )


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




def _bound_project_slug() -> str | None:
    session = resolve_current_session()
    return session.project if session is not None else None


def _project_theme_suffix(slug: str) -> str:
    try:
        theme = get_project_theme(slug)
    except Exception:  # noqa: BLE001
        return ""
    return f"  (theme: {theme})" if theme else ""




def _print_project_header(slug: str) -> None:
    print(f"Project: {slug}")
    print(f"Root: {paths.project_dir(slug)}")


def _print_project_tree(payload: dict[str, Any]) -> None:
    project = payload["project"]
    print(f"{project['slug']}/")
    print("  project.json")
    if project.get("theme"):
        print(f"  theme: {project['theme']}")
    print("  sources/")
    for source in payload.get("sources", []):
        if isinstance(source, dict):
            source_id = source.get("source_id", "")
            if source.get("kind") == "registered":
                suffix = "" if source.get("valid", True) else "  [invalid id]"
                print(f"    {source_id}/{suffix}")
                print("      source.json")
                print("      analysis/")
            else:
                suffix = "" if source.get("valid", True) else "  [invalid id]"
                print(f"    {source_id}  [file]{suffix}")
        else:
            print(f"    {source}/")
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
