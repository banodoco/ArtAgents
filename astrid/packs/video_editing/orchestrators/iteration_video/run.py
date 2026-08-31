#!/usr/bin/env python3
"""Orchestrate runtime-authority run discovery, assembly, and rendering."""


from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('video_editing.iteration_video')
import argparse
import json
import os
import sys
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from astrid.core import modalities
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.rendering.attached import invoke_attached_render
from astrid.core.subprocess_env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV
SCHEMA_VERSION = 1
from astrid.packs.iteration.executors.assemble import run as assemble

OUTPUT_FILES = (
    ("iteration.mp4", "video"),
    ("iteration.mp4.provenance.json", "metadata"),
    ("iteration.timeline.json", "metadata"),
    ("iteration.manifest.json", "metadata"),
    ("iteration.report.html", "text"),
    ("iteration.quality.json", "metadata"),
)


class IterationVideoError(RuntimeError):
    pass


@dataclass
class RuntimeRunNode:
    """Small graph view assembled from runtime run resources."""

    run_id: str
    record: dict[str, Any]
    depth: int
    label: str
    parent_edges: list[dict[str, Any]] = field(default_factory=list)
    unresolved_parent_run_ids: list[str] = field(default_factory=list)
    selection_order: int = 999_999


def run_orchestrator(request: Any, orchestrator: Any) -> dict[str, Any]:
    out_path = Path(request.out).expanduser().resolve()
    args = _parse_passthrough(tuple(getattr(request, "orchestrator_args", ()) or ()))
    repo_root = Path(args.repo_root or REPO_ROOT).expanduser().resolve()
    target_run_id = request.inputs.get("target_run_id") or args.target_run_id
    if request.dry_run:
        return _dry_run_result(orchestrator.id, out_path=out_path)

    try:
        # The orchestrator subprocess has no local project/run authority. Open
        # the selected workspace runtime here and pass its client explicitly to
        # the route so all run selection and provenance reads are API-backed.
        with _runtime_client_context() as runtime_client:
            render_binding = _attached_render_binding(request)
            render_binding.pop("project_slug", None)
            result = run_iteration_video(
                repo_root=repo_root,
                out_path=out_path,
                target_run_id=str(target_run_id) if target_run_id else None,
                max_iterations=args.max_iterations,
                renderers=args.renderers,
                renderer=args.renderer,
                clip_mode=args.clip_mode,
                direction=args.direction,
                mode=args.mode,
                audio_bed=args.audio_bed,
                force=args.force,
                no_content=args.no_content,
                project_slug=getattr(request, "project", None),
                runtime_client=runtime_client,
                **render_binding,
            )
    except (IterationVideoError, assemble.AssembleError, OSError, RuntimeError) as exc:
        return {
            "orchestrator_id": orchestrator.id,
            "kind": orchestrator.kind,
            "runtime_kind": "python",
            "returncode": 2,
            "errors": [str(exc)],
        }
    return {
        "orchestrator_id": orchestrator.id,
        "kind": orchestrator.kind,
        "runtime_kind": "python",
        "returncode": 0,
        "outputs": result["outputs"],
        "planned_commands": result["planned_commands"],
    }


def run_iteration_video(
    *,
    repo_root: Path,
    out_path: Path,
    target_run_id: str | None = None,
    max_iterations: int | None = None,
    renderers: str | None = None,
    renderer: str = "remotion",
    clip_mode: str | None = None,
    direction: str | None = None,
    mode: str = "chaptered",
    audio_bed: str = "auto",
    force: bool = False,
    no_content: bool = False,
    project_slug: str | None = None,
    runtime_client: Any | None = None,
    parent_run_id: str | None = None,
    render_step_id: str | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.expanduser().resolve()
    out_path = out_path.expanduser().resolve()
    del max_iterations  # Runtime reads are bounded by the API page, not summaries.
    with _runtime_client_context(runtime_client) as client:
        target, records = resolve_target_run_id(
            repo_root,
            target_run_id=target_run_id,
            project_slug=project_slug,
            runtime_client=client,
        )
        nodes = _collect_runtime_graph(records, target["target_run_id"])
        input_manifest, input_quality = _build_runtime_inputs(
            nodes,
            target_run_id=target["target_run_id"],
            project_slug=target["project_slug"],
        )
        assemble_result = assemble.assemble_iteration(
            out_path=out_path,
            repo_root=repo_root,
            force=force,
            direction=direction,
            mode=mode,
            audio_bed=audio_bed,
            input_manifest=input_manifest,
            input_quality=input_quality,
            runtime_client=client,
            runtime_project=target["project_slug"],
        )
    _record_requested_flags(
        out_path / "iteration.manifest.json",
        renderers=renderers,
        clip_mode=clip_mode,
        no_content=no_content,
    )
    iteration_mp4 = run_builtin_render(
        out_path,
        repo_root=repo_root,
        renderer=renderer,
        # Render must use the same selected runtime project that supplied the
        # input runs.  This matters for direct SDK callers that omit the
        # optional project argument and rely on runtime selection.
        project_slug=target["project_slug"],
        parent_run_id=parent_run_id,
        step_id=render_step_id,
    )
    return {
        "target_run_id": target["target_run_id"],
        "assemble": assemble_result,
        "outputs": {name: str(out_path / name) for name, _kind in OUTPUT_FILES},
        "planned_commands": (
            ("runtime.runs.list/show", target["project_slug"], target["target_run_id"]),
            ("iteration.assemble", str(out_path)),
            ("rendering.render", str(out_path / "hype.timeline.json"), str(out_path / "hype.assets.json")),
        ),
    }


def run_builtin_render(
    brief_out: Path,
    *,
    repo_root: Path,
    renderer: str,
    project_slug: str | None = None,
    parent_run_id: str | None = None,
    step_id: str | None = None,
) -> Path:
    return invoke_attached_render(
        brief_out / "hype.timeline.json",
        brief_out / "hype.assets.json",
        brief_out / "iteration.mp4",
        project_slug=project_slug,
        parent_run_id=parent_run_id,
        step_id=step_id,
        engine=renderer,
        project_root=repo_root,
    )


def _attached_render_binding(request: Any) -> dict[str, str | None]:
    """Return the existing parent ledger binding without creating another run."""

    env_project = os.environ.get(TASK_PROJECT_ENV)
    env_run = os.environ.get(TASK_RUN_ID_ENV)
    if env_project is not None or env_run is not None:
        return {
            "project_slug": None,
            "parent_run_id": None,
            "render_step_id": "iteration-render",
        }
    project_slug = getattr(request, "project", None)
    run_root = getattr(request, "run_root", None)
    # A runtime-selected project without a parent run is a valid public route;
    # only an orphaned run-root is an invalid binding. The render helper will
    # use its unbound service path while the outer invocation remains runtime
    # admitted.
    if run_root and not project_slug:
        raise IterationVideoError(
            "iteration render received a run context without a parent project"
        )
    if project_slug and run_root:
        return {
            "project_slug": str(project_slug),
            "parent_run_id": Path(run_root).name,
            "render_step_id": "iteration-render",
        }
    return {
        "project_slug": None,
        "parent_run_id": None,
        "render_step_id": None,
    }


def inspect_iteration_run(
    *,
    repo_root: Path,
    target_run_id: str | None = None,
    summarizer_model_version: str = "runtime.runs.v1",
    cost_per_call: float = 0.0,
    project_slug: str | None = None,
    runtime_client: Any | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.expanduser().resolve()
    with _runtime_client_context(runtime_client) as client:
        target, records = resolve_target_run_id(
            repo_root,
            target_run_id=target_run_id,
            project_slug=project_slug,
            runtime_client=client,
        )
        nodes = _collect_runtime_graph(records, target["target_run_id"])
        quality = _build_runtime_inputs(
            nodes,
            target_run_id=target["target_run_id"],
            project_slug=target["project_slug"],
        )[1]
        renderers = renderer_decisions(nodes)
    cache_stats = {"hits": 0, "misses": 0}
    uncached = 0
    return {
        "schema_version": SCHEMA_VERSION,
        "target_run_id": target["target_run_id"],
        "run_count": len(nodes),
        "detected_modalities": sorted({item["kind"] for item in renderers if item.get("kind")}),
        "chosen_renderers": renderers,
        "quality": quality,
        "summary_cache": cache_stats,
        "cost_estimate": {
            "uncached_summarize_calls": uncached,
            "cost_per_call": cost_per_call,
            "estimated_cost": round(uncached * cost_per_call, 6),
            "summarizer_model_version": summarizer_model_version,
        },
    }


def format_inspection(report: Mapping[str, Any], *, no_content: bool = False) -> str:
    cost = report["cost_estimate"]
    lines = [
        f"target_run_id: {report['target_run_id']}",
        f"runs: {report['run_count']}",
        f"data_quality: {report['quality']['data_quality']}",
        f"modalities: {', '.join(report['detected_modalities']) or 'none'}",
        f"summary_cache: {report['summary_cache']['hits']} hit(s), {report['summary_cache']['misses']} miss(es)",
        f"Estimated cost: ~${cost['estimated_cost']:.3f} ({cost['uncached_summarize_calls']} call(s) x ${cost['cost_per_call']:.3f})",
        "renderers:",
    ]
    for item in report["chosen_renderers"]:
        suffix = " fallback" if item.get("fallback") else ""
        lines.append(f"  - {item.get('kind') or 'unknown'} -> {item['renderer']}{suffix}")
    if no_content:
        lines.append("content: suppressed")
    return "\n".join(lines) + "\n"


def _runtime_client_context(client: Any | None = None):
    if client is not None:
        return nullcontext(client)
    from astrid.sdk.client import AstridClient

    return AstridClient.open()


def _resolve_runtime_project(client: Any, project_slug: str | None) -> str:
    if project_slug:
        return str(project_slug)
    selected = getattr(client, "selected_project_ref", None)
    if callable(selected):
        value = selected()
        if value:
            return str(value)
    raise IterationVideoError(
        "iteration video requires a runtime project; pass --project <project> "
        "or select a current project in the workspace runtime"
    )


def _unwrap_runtime_result(value: Any) -> Any:
    if hasattr(value, "ok") and hasattr(value, "data"):
        if not bool(value.ok):
            error = getattr(value, "error", None)
            raise IterationVideoError(str(error or "runtime run read failed"))
        return value.data
    return value


def _runtime_run_list(client: Any, project: str) -> list[Any]:
    runs = getattr(client, "runs", None)
    method = getattr(runs, "list", None)
    if callable(method):
        value = _unwrap_runtime_result(method(project))
    else:
        method = getattr(client, "list_project_runs", None)
        if not callable(method):
            raise IterationVideoError("runtime client does not expose project run listing")
        value = method(project)
    if isinstance(value, Mapping):
        value = value.get("items", ())
    if not isinstance(value, (list, tuple)):
        raise IterationVideoError("runtime project run listing returned an invalid response")
    return list(value)


def _runtime_run_show(client: Any, project: str, run_id: str) -> dict[str, Any] | None:
    runs = getattr(client, "runs", None)
    method = getattr(runs, "show", None)
    try:
        value = _unwrap_runtime_result(method(project, run_id)) if callable(method) else client.get_run(run_id)
    except Exception:
        return None
    return _normalize_runtime_record(value, client=client, project=project)


def _load_runtime_records(client: Any, project: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for raw in _runtime_run_list(client, project):
        record = _normalize_runtime_record(raw, client=client, project=project)
        run_id = str(record.get("run_id") or "")
        if run_id:
            records[run_id] = record
    return records


def _normalize_runtime_record(raw: Any, *, client: Any, project: str) -> dict[str, Any]:
    if hasattr(raw, "__dict__") and not isinstance(raw, Mapping):
        raw = vars(raw)
    if not isinstance(raw, Mapping):
        raise IterationVideoError("runtime run resource is not an object")
    source = dict(raw)
    run_id = str(source.get("run_id") or source.get("id") or "")
    spec = source.get("spec") if isinstance(source.get("spec"), Mapping) else {}
    # The runtime run resource wraps the admitted capability spec in a
    # transport envelope (`spec.spec`).  Normalize that envelope once so the
    # pack consumes the exact fields supplied at admission.
    if isinstance(spec.get("spec"), Mapping):
        spec = dict(spec["spec"])
    result = source.get("result") if isinstance(source.get("result"), Mapping) else {}
    record: dict[str, Any] = {**dict(spec), **source}
    record["run_id"] = run_id
    record["executor_id"] = str(
        source.get("executor_id") or source.get("capability") or source.get("capability_id")
        or spec.get("executor_id") or "runtime.run"
    )
    record["out_path"] = source.get("out_path") or source.get("run_root") or spec.get("out_path")
    record["parent_run_ids"] = source.get("parent_run_ids") or spec.get("parent_run_ids") or []
    record["provenance"] = source.get("provenance") or spec.get("provenance") or {}
    record["input_artifacts"] = _artifact_list(
        source.get("input_artifacts") or spec.get("input_artifacts") or source.get("inputs") or spec.get("inputs")
    )
    output_raw = (
        source.get("output_artifacts") or source.get("outputs") or result.get("output_artifacts")
        or result.get("outputs") or result.get("output_objects") or spec.get("output_artifacts")
    )
    record["output_artifacts"] = _artifact_list(output_raw)
    if not record["output_artifacts"]:
        _hydrate_task_outputs(record, client=client, project=project)
    return record


def _hydrate_task_outputs(record: dict[str, Any], *, client: Any, project: str) -> None:
    task_ids = record.get("task_ids") or []
    tasks = getattr(client, "tasks", None)
    show = getattr(tasks, "show", None)
    if not callable(show):
        show = getattr(client, "get_task", None)
    if not callable(show):
        return
    outputs: list[Any] = []
    for task_id in task_ids if isinstance(task_ids, (list, tuple)) else ():
        try:
            value = _unwrap_runtime_result(show(task_id, project) if tasks is not None and hasattr(tasks, "show") else show(task_id))
        except Exception:
            continue
        if not isinstance(value, Mapping):
            continue
        result = value.get("result") if isinstance(value.get("result"), Mapping) else value
        outputs.extend(_artifact_list(result.get("output_artifacts") or result.get("outputs") or result.get("output_objects")))
    record["output_artifacts"] = outputs


def _artifact_list(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, Mapping):
        raw = list(raw.values())
    if not isinstance(raw, (list, tuple)):
        return []
    result: list[dict[str, Any]] = []
    for value in raw:
        if hasattr(value, "__dict__") and not isinstance(value, Mapping):
            value = vars(value)
        if not isinstance(value, Mapping):
            continue
        item = dict(value)
        digest = item.get("sha256") or item.get("content_sha256") or item.get("digest")
        if isinstance(digest, str):
            item["sha256"] = digest.removeprefix("sha256:")
        if not item.get("path"):
            for key in ("file", "locator", "local_path"):
                if item.get(key):
                    item["path"] = item[key]
                    break
        if not item.get("kind"):
            media_type = str(item.get("media_type") or item.get("mime_type") or "")
            item["kind"] = media_type.split("/", 1)[0] if "/" in media_type else "opaque"
        result.append(item)
    return result


def _collect_runtime_graph(records: Mapping[str, dict[str, Any]], target_run_id: str) -> list[RuntimeRunNode]:
    if target_run_id not in records:
        raise IterationVideoError(f"unknown runtime run: {target_run_id}")
    nodes: dict[str, RuntimeRunNode] = {}
    queue: list[tuple[str, int]] = [(target_run_id, 0)]
    while queue:
        run_id, depth = queue.pop(0)
        record = records.get(run_id)
        if record is None:
            continue
        existing = nodes.get(run_id)
        if existing is not None and existing.depth >= depth:
            continue
        parents, unresolved = _runtime_parent_edges(record, records)
        nodes[run_id] = RuntimeRunNode(
            run_id=run_id,
            record=record,
            depth=depth,
            label="target" if run_id == target_run_id else "pulled_by_ancestry",
            parent_edges=parents,
            unresolved_parent_run_ids=unresolved,
        )
        queue.extend((str(edge["run_id"]), depth + 1) for edge in parents)
    return sorted(nodes.values(), key=lambda item: (-item.depth, item.selection_order, item.run_id))


def _runtime_parent_edges(record: Mapping[str, Any], records: Mapping[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    raw_edges: list[Any] = list(record.get("parent_run_ids") or [])
    provenance = record.get("provenance") if isinstance(record.get("provenance"), Mapping) else {}
    raw_edges.extend(provenance.get("contributing_runs") or [])
    edges: list[dict[str, Any]] = []
    unresolved: list[str] = []
    seen: set[str] = set()
    for raw in raw_edges:
        value = raw if isinstance(raw, Mapping) else {"run_id": raw}
        run_id = value.get("run_id") if isinstance(value, Mapping) else None
        if not isinstance(run_id, str) or not _is_runtime_identifier(run_id) or run_id in seen:
            continue
        seen.add(run_id)
        edge = {"run_id": run_id, "kind": str(value.get("kind") or "causal")}
        if run_id not in records:
            unresolved.append(run_id)
        else:
            edges.append(edge)
    return edges, unresolved


def _build_runtime_inputs(nodes: list[RuntimeRunNode], *, target_run_id: str, project_slug: str) -> tuple[dict[str, Any], dict[str, Any]]:
    total = len(nodes)
    unresolved = [
        {"run_id": node.run_id, "missing_parent_run_ids": node.unresolved_parent_run_ids}
        for node in nodes if node.unresolved_parent_run_ids
    ]
    quality = {
        "schema_version": SCHEMA_VERSION,
        "target_run_id": target_run_id,
        "total_runs": total,
        "data_quality": 1.0 if total and not unresolved else (0.8 if total else 0.0),
        "unresolved_producer_runs": unresolved,
        "authority": {"kind": "runtime", "project": project_slug},
    }
    runs = []
    for node in nodes:
        runs.append({
            "run_id": node.run_id,
            "label": node.label,
            "causal_depth": node.depth,
            "selection_order": node.selection_order,
            "parent_run_ids": node.parent_edges,
            "unresolved_parent_run_ids": node.unresolved_parent_run_ids,
            "out_path": node.record.get("out_path"),
            "executor_id": node.record.get("executor_id"),
            "orchestrator_id": node.record.get("orchestrator_id"),
            "output_artifacts": node.record.get("output_artifacts", []),
            "summary": None,
        })
    target = next((node for node in nodes if node.run_id == target_run_id), None)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "target_run_id": target_run_id,
        "runs": runs,
        "quality": dict(quality),
        "summary_cache": {"hits": 0, "misses": 0},
        "cost_estimate": {"summarize_calls": 0, "uncached_summarize_calls": 0, "cost_per_call": 0.0, "estimated_cost": 0.0},
        "authority": {"kind": "runtime", "project": project_slug, "run_ids": [node.run_id for node in nodes]},
    }
    return manifest, quality


def resolve_target_run_id(
    repo_root: Path,
    *,
    target_run_id: str | None,
    project_slug: str | None = None,
    runtime_client: Any | None = None,
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    del repo_root
    client = runtime_client
    if client is None:
        raise IterationVideoError("runtime client is required for iteration-video run discovery")
    project = _resolve_runtime_project(client, project_slug)
    all_records = _load_runtime_records(client, project)
    if not target_run_id or not _is_runtime_identifier(target_run_id):
        raise IterationVideoError(
            "target_run_id is required; pass the runtime-issued run id explicitly"
        )
    if target_run_id not in all_records:
        fetched = _runtime_run_show(client, project, target_run_id)
        if fetched is not None:
            all_records[target_run_id] = fetched
    record = all_records.get(target_run_id)
    if record is None:
        raise IterationVideoError(f"unknown runtime run: {target_run_id}")
    return ({
        "target_run_id": target_run_id,
        "project_slug": project,
    }, all_records)


def _is_runtime_identifier(value: object) -> bool:
    """Validate opaque runtime ids without imposing a local ULID dialect."""

    if not isinstance(value, str) or not value or len(value) > 128:
        return False
    return all(char.isalnum() or char in "_-" for char in value)


def renderer_decisions(nodes: list[RuntimeRunNode]) -> list[dict[str, Any]]:
    decisions = []
    for node in nodes:
        for artifact in node.record.get("output_artifacts", []) or []:
            if not isinstance(artifact, Mapping):
                continue
            kind = str(artifact.get("kind") or "unknown")
            resolution = modalities.resolve_renderer_for_kind(kind)
            decisions.append(
                {
                    "run_id": node.run_id,
                    "kind": kind,
                    "renderer": resolution["renderer"],
                    "fallback": bool(resolution.get("fallback")),
                }
            )
    return decisions


def inspect_cache(repo_root: Path, nodes: list[RuntimeRunNode], *, summarizer_model_version: str) -> dict[str, int]:
    del repo_root, nodes, summarizer_model_version
    return {"hits": 0, "misses": 0}


def main(argv: list[str] | None = None) -> int:
    raw = list(argv) if argv is not None else sys.argv[1:]
    if raw and raw[0] == "inspect":
        parser = _inspect_parser()
        args = parser.parse_args(raw[1:])
        try:
            report = inspect_iteration_run(
                repo_root=Path(args.repo_root),
                target_run_id=args.target_run_id,
                cost_per_call=args.cost_per_call,
                project_slug=args.project,
            )
        except IterationVideoError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(format_inspection(report, no_content=args.no_content), end="")
        return 0
    parser = _run_parser()
    args = parser.parse_args(raw)
    try:
        result = run_iteration_video(
            repo_root=Path(args.repo_root),
            out_path=Path(args.out),
            target_run_id=args.target_run_id,
            max_iterations=args.max_iterations,
            renderers=args.renderers,
            renderer=args.renderer,
            clip_mode=args.clip_mode,
            direction=args.direction,
            mode=args.mode,
            audio_bed=args.audio_bed,
            force=args.force,
            no_content=args.no_content,
            project_slug=args.project,
        )
    except (IterationVideoError, assemble.AssembleError, OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result["outputs"], indent=2, sort_keys=True))
    return 0


def _parse_passthrough(argv: tuple[str, ...]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--target-run-id", default=None)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--renderers", default=None)
    parser.add_argument(
        "--renderer",
        default="remotion",
        help="Deprecated render selector; forwarded to rendering.render as its engine selector.",
    )
    parser.add_argument("--clip-mode", default=None)
    parser.add_argument("--direction", default=None)
    parser.add_argument("--mode", default="chaptered")
    parser.add_argument("--audio-bed", default="auto")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-content", action="store_true")
    return parser.parse_args(list(argv))


def _run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an iteration video from a runtime run.")
    parser.add_argument("--target-run-id", default=None)
    parser.add_argument("--project", default=None, help="Runtime project id or slug (defaults to the selected project).")
    parser.add_argument("--out", required=True)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--renderers", default=None)
    parser.add_argument(
        "--renderer",
        default="remotion",
        help="Deprecated render selector; forwarded to rendering.render as its engine selector.",
    )
    parser.add_argument("--clip-mode", default=None)
    parser.add_argument("--direction", default=None)
    parser.add_argument("--mode", default="chaptered")
    parser.add_argument("--audio-bed", default="auto")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-content", action="store_true")
    return parser


def _inspect_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect an iteration video plan without render or summarize.")
    parser.add_argument("target_run_id", help="Runtime-issued target run id.")
    parser.add_argument("--project", default=None, help="Runtime project id or slug (defaults to the selected project).")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--cost-per-call", type=float, default=0.0)
    parser.add_argument("--no-content", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def _dry_run_result(orchestrator_id: str, *, out_path: Path) -> dict[str, Any]:
    return {
        "orchestrator_id": orchestrator_id,
        "runtime_kind": "python",
        "returncode": None,
        "dry_run": True,
        "planned_commands": (
            ("runtime.runs.list/show", "selected project"),
            ("iteration.assemble", str(out_path)),
            ("rendering.render", str(out_path / "hype.timeline.json"), str(out_path / "hype.assets.json")),
        ),
    }


def _record_requested_flags(manifest_path: Path, *, renderers: str | None, clip_mode: str | None, no_content: bool) -> None:
    manifest = _read_json(manifest_path)
    manifest["iteration_video"] = {
        "schema_version": SCHEMA_VERSION,
        "requested_renderers": _csv(renderers),
        "clip_mode": clip_mode,
        "no_content": bool(no_content),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
