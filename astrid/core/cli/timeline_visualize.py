"""Focused ``astrid timelines visualize`` CLI façade."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import astrid
from astrid.core.contracts.errors import AstridError
from astrid.core.gateway.project import (
    ASTRID_GATEWAY_RESOLVED_PROJECT_ENV,
    _validated_timeline_visualize_view_context,
)
from astrid.core.task import env as task_env
from astrid.core.timeline._shared import (
    _resolve_edit_context,
    _resolve_optional_session,
)
from astrid.sdk import AstridSDKError

_CORE_ENTRYPOINTS = (
    "ground_truth",
    "view_map",
    "action_index",
    "asset_index",
    "transcript_index",
    "diagnostics",
    "reading_guide",
)


def _validate_arguments(args: argparse.Namespace) -> None:
    from_view = getattr(args, "from_view", None)
    focus = getattr(args, "focus", None)
    if bool(from_view) != bool(focus):
        raise AstridError(
            "--from-view and --focus must be supplied together",
            recovery_command="supply both --from-view MANIFEST and --focus FOCUS_REF",
        )
    if getattr(args, "refresh_root", False) and not from_view:
        raise AstridError(
            "--refresh-root requires --from-view and --focus",
            recovery_command="use the refresh_root action from action-index.json",
        )
    if getattr(args, "timeline_slug", None) is not None and getattr(args, "select_all", False):
        raise AstridError(
            "timeline-slug and --all are mutually exclusive",
            recovery_command="remove timeline-slug or --all",
        )
    if from_view:
        if getattr(args, "refresh_root", False):
            from astrid.packs.rendering.executors.timeline_visualize.ids import (
                parse_qualified_ref,
            )

            try:
                refresh_focus = parse_qualified_ref(str(focus))
            except ValueError as exc:
                raise AstridError(str(exc)) from exc
            if refresh_focus.kind != "TL":
                raise AstridError(
                    "--refresh-root focus must be the frozen timeline reference",
                    recovery_command="use --focus TL01 with --refresh-root",
                )
        conflicts = [
            label
            for label, selected in (
                ("timeline-slug", getattr(args, "timeline_slug", None) is not None),
                ("--project", getattr(args, "project", None) is not None),
                ("--all", bool(getattr(args, "select_all", False))),
                ("--shot", getattr(args, "shot", None) is not None),
                ("--range", getattr(args, "range_value", None) is not None),
                ("--at", getattr(args, "at", None) is not None),
                ("--clip", getattr(args, "clip", None) is not None),
                ("--asset", getattr(args, "asset", None) is not None),
            )
            if selected
        ]
        if conflicts:
            raise AstridError(
                "--from-view/--focus cannot be combined with " + ", ".join(conflicts),
                recovery_command="remove the cold project/timeline selectors",
            )
    if args.context < 0:
        raise AstridError("--context must be non-negative")
    if args.neighbors < 0:
        raise AstridError("--neighbors must be non-negative")
    if args.rendered_video and args.filmstrip not in {"auto", "rendered"}:
        raise AstridError("--rendered-video requires --filmstrip auto or rendered")
    if args.filmstrip == "rendered" and not args.rendered_video:
        raise AstridError("--filmstrip rendered requires --rendered-video PATH")


def _view_context(args: argparse.Namespace):
    raw = [
        "timelines",
        "visualize",
        "--from-view",
        str(args.from_view),
        "--focus",
        str(args.focus),
    ]
    if getattr(args, "refresh_root", False):
        raw.append("--refresh-root")
    context = _validated_timeline_visualize_view_context(raw)
    if context is None:
        raise AstridError(
            "invalid --from-view: expected a contained, hash-verified visualization run manifest",
            recovery_command="start a new root view with --project <slug>",
        )

    attached = _resolve_optional_session(args)
    if attached is not None and getattr(attached, "project", None) != context.project_slug:
        raise AstridError(
            "--from-view belongs to a different project than the attached session",
            recovery_command=f"astrid attach {context.project_slug}",
        )
    gateway_project = os.environ.get(ASTRID_GATEWAY_RESOLVED_PROJECT_ENV)
    if gateway_project and gateway_project != context.project_slug:
        raise AstridError(
            "--from-view project does not match the gateway project context",
            recovery_command=f"astrid attach {context.project_slug}",
        )

    resolved_args = copy.copy(args)
    resolved_args.project = context.project_slug
    _actor, project_slug = _resolve_edit_context(context.project_slug, resolved_args)
    return context, project_slug


def _cold_project(args: argparse.Namespace) -> str:
    gateway_project = os.environ.get(ASTRID_GATEWAY_RESOLVED_PROJECT_ENV)
    requested_project = getattr(args, "project", None) or gateway_project
    resolved_args = copy.copy(args)
    resolved_args.project = requested_project
    _actor, project_slug = _resolve_edit_context(requested_project, resolved_args)
    return project_slug


def _scope_name(args: argparse.Namespace) -> str:
    if args.select_all:
        return "project"
    if args.shot is not None:
        return "shot"
    if args.range_value is not None:
        return "range"
    if args.at is not None:
        return "timestamp"
    if args.clip is not None:
        return "clip"
    if args.asset is not None:
        return "asset"
    return "timeline"


def _executor_inputs(
    args: argparse.Namespace,
    *,
    project_slug: str,
    verified_from_view: Path | None,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "project_slug": project_slug,
        "all": bool(args.select_all),
        "scope": _scope_name(args),
        "context": args.context,
        "neighbors": args.neighbors,
        "layout": args.layout,
        "formats": list(args.formats or ["all"]),
        "filmstrip": args.filmstrip,
    }
    if getattr(args, "refresh_root", False):
        inputs["refresh_root"] = True
    for key, value in (
        ("timeline_slug", args.timeline_slug),
        ("shot", args.shot),
        ("range", args.range_value),
        ("at", args.at),
        ("clip", args.clip),
        ("asset", args.asset),
        ("from_view", str(verified_from_view) if verified_from_view else None),
        ("focus", args.focus),
        ("rendered_video", args.rendered_video),
    ):
        if value not in (None, ""):
            inputs[key] = value
    return inputs


def _result_error_message(result: Any) -> str:
    error = getattr(result, "error", None)
    if isinstance(error, Mapping):
        for key in ("message", "cause", "detail", "sdk_category"):
            value = error.get(key)
            if isinstance(value, str) and value:
                return value
    if error:
        return str(error)
    return "timeline visualization failed"


def _contained_entrypoint(pack_root: Path, raw: object, *, label: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise AstridError(f"timeline visualization manifest is missing {label}")
    candidate = Path(raw)
    resolved = (
        candidate.expanduser().resolve()
        if candidate.is_absolute()
        else (pack_root / candidate).resolve()
    )
    if not resolved.is_relative_to(pack_root) or not resolved.is_file():
        raise AstridError(f"timeline visualization {label} is not a contained file")
    return str(resolved)


def _leaf_manifests(root_manifest_path: Path, document: Mapping[str, Any]) -> list[Path]:
    if document.get("kind") != "timeline_visualize_project":
        return [root_manifest_path]
    reading_order = document.get("reading_order")
    if not isinstance(reading_order, list) or not reading_order:
        raise AstridError("project visualization manifest has no timeline reading order")
    return [
        Path(
            _contained_entrypoint(
                root_manifest_path.parent,
                raw,
                label="timeline manifest",
            )
        )
        for raw in reading_order
    ]


def _collapse(values: list[str]) -> str | list[str] | None:
    unique = list(dict.fromkeys(values))
    if not unique:
        return None
    return unique[0] if len(unique) == 1 else unique


def _result_summary(result: Any) -> dict[str, Any]:
    run_id = getattr(result, "run_id", None)
    run_root_raw = getattr(result, "run_root", None)
    manifest_raw = getattr(result, "manifest_path", None)
    if not all(isinstance(value, str) and value for value in (run_id, run_root_raw, manifest_raw)):
        raise AstridError("timeline visualization SDK result is missing managed run pointers")
    run_root = Path(run_root_raw).expanduser().resolve()
    manifest_path = Path(manifest_raw).expanduser().resolve()
    if not run_root.is_dir() or not manifest_path.is_file() or not manifest_path.is_relative_to(run_root):
        raise AstridError("timeline visualization SDK returned invalid managed run pointers")

    try:
        root_document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AstridError(f"cannot read timeline visualization manifest: {exc}") from exc
    if not isinstance(root_document, dict):
        raise AstridError("timeline visualization manifest must be a JSON object")

    leaf_paths = _leaf_manifests(manifest_path, root_document)
    core: dict[str, list[str]] = {key: [] for key in _CORE_ENTRYPOINTS}
    format_paths: dict[str, list[str]] = {"png": [], "svg": [], "md": []}
    format_reasons: dict[str, list[str]] = {"png": [], "svg": [], "md": []}
    page_count = 0
    for leaf_path in leaf_paths:
        try:
            leaf = json.loads(leaf_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AstridError(f"cannot read timeline visualization child manifest: {exc}") from exc
        if not isinstance(leaf, dict) or leaf.get("kind") != "timeline_visualize":
            raise AstridError("timeline visualization child manifest has the wrong kind")
        raw_page_count = leaf.get("page_count")
        if isinstance(raw_page_count, bool) or not isinstance(raw_page_count, int):
            raise AstridError("timeline visualization manifest has an invalid page_count")
        page_count += raw_page_count
        entrypoints = leaf.get("entrypoints")
        optional = leaf.get("optional_formats")
        if not isinstance(entrypoints, dict) or not isinstance(optional, dict):
            raise AstridError("timeline visualization manifest is missing entrypoints")
        for key in _CORE_ENTRYPOINTS:
            core[key].append(
                _contained_entrypoint(leaf_path.parent, entrypoints.get(key), label=key)
            )
        for output_key, manifest_key in (("png", "png"), ("svg", "svg"), ("md", "structure")):
            block = optional.get(manifest_key)
            if not isinstance(block, dict):
                raise AstridError(f"timeline visualization manifest is missing {manifest_key} format state")
            raw_path = block.get("path")
            reason = block.get("reason")
            if raw_path is not None:
                format_paths[output_key].append(
                    _contained_entrypoint(leaf_path.parent, raw_path, label=manifest_key)
                )
            elif isinstance(reason, str) and reason:
                format_reasons[output_key].append(reason)
            else:
                raise AstridError(f"omitted {manifest_key} format has no reason")

    formats = {
        key: {
            "path": _collapse(format_paths[key]),
            "reason": (
                None
                if format_paths[key]
                else "; ".join(dict.fromkeys(format_reasons[key]))
            ),
        }
        for key in ("png", "svg", "md")
    }
    entrypoints: dict[str, Any] = {
        "manifest": str(manifest_path),
        **{key: _collapse(paths) for key, paths in core.items()},
        "primary_image": formats["png"]["path"],
        "factual_markdown": formats["md"]["path"],
    }
    if len(leaf_paths) > 1:
        entrypoints["timeline_manifests"] = [str(path) for path in leaf_paths]
    return {
        "run_id": run_id,
        "run_root": str(run_root),
        "manifest_path": str(manifest_path),
        "pages": page_count,
        "entrypoints": entrypoints,
        "formats": formats,
    }


def cmd_visualize(args: argparse.Namespace) -> int:
    """Invoke ``rendering.timeline_visualize`` and print one compact JSON value."""

    _validate_arguments(args)
    verified_from_view: Path | None = None
    if args.from_view:
        context, project_slug = _view_context(args)
        verified_from_view = context.manifest_path
    else:
        project_slug = _cold_project(args)
    inputs = _executor_inputs(
        args,
        project_slug=project_slug,
        verified_from_view=verified_from_view,
    )
    invoke_kwargs: dict[str, Any] = {
        "kind": "executor",
        "project": project_slug,
        "inputs": inputs,
        "execution_mode": "in_process",
    }
    if task_env.is_in_task_run(project_slug):
        raw_argv = tuple(getattr(args, "_raw_argv", ()))
        if raw_argv:
            invoke_kwargs["argv"] = ("timelines", *raw_argv)
    try:
        result = astrid.invoke("rendering.timeline_visualize", **invoke_kwargs)
    except AstridSDKError as exc:
        raise AstridError(
            str(exc),
            recovery_command="inspect the managed run diagnostics and retry",
        ) from exc
    if not getattr(result, "ok", False):
        raise AstridError(
            _result_error_message(result),
            recovery_command="inspect the managed run diagnostics and retry",
        )

    summary = _result_summary(result)
    sys.stdout.write(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


__all__ = ["cmd_visualize"]
