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
    lineage_incomplete: bool = False
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
    renderer: str = "rendering.remotion",
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
        selector=renderer,
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
        value = _unwrap_runtime_result(method(project))
    if isinstance(value, Mapping):
        if "items" not in value:
            raise IterationVideoError("runtime project run listing returned an invalid response")
        value = value["items"]
    if not isinstance(value, (list, tuple)):
        raise IterationVideoError("runtime project run listing returned an invalid response")
    return list(value)


def _runtime_run_show(
    client: Any,
    project: str,
    run_id: str,
    *,
    project_identities: set[str] | None = None,
) -> dict[str, Any] | None:
    runs = getattr(client, "runs", None)
    method = getattr(runs, "show", None)
    # A project-scoped run read is required. A generic workspace lookup would
    # allow a foreign project record into the lineage graph.
    if not callable(method):
        return None
    try:
        value = _unwrap_runtime_result(method(project, run_id))
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return None
    record = _normalize_runtime_record(value, client=client, project=project)
    _assert_runtime_project(record, project, project_identities=project_identities)
    return record


def _load_runtime_records(
    client: Any,
    project: str,
    *,
    project_identities: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for raw in _runtime_run_list(client, project):
        record = _normalize_runtime_record(raw, client=client, project=project)
        _assert_runtime_project(record, project, project_identities=project_identities)
        run_id = str(record.get("run_id") or "")
        if run_id:
            records[run_id] = record
    _attach_runtime_lineage(
        records,
        client=client,
        project=project,
        project_identities=project_identities,
    )
    return records


def _attach_runtime_lineage(
    records: dict[str, dict[str, Any]],
    *,
    client: Any,
    project: str,
    project_identities: set[str] | None = None,
) -> None:
    """Attach only runtime-owned lineage reads to each run resource.

    The generated workspace client currently exposes runs/tasks, their event
    streams, and project media relations.  Evidence and command receipts are
    not yet read operations in that client; those fields therefore remain
    explicitly unavailable instead of being reconstructed from local files or
    inferred from parent ids.
    """

    if project_identities is None:
        project_identities = _runtime_project_identities(client, project)
    tasks, tasks_available = _runtime_task_records(
        client, project, project_identities=project_identities
    )
    relations, relations_available = _runtime_relations(client, project)
    run_relations, relation_binding_available = _runtime_run_relations(
        relations, known_run_ids=set(records)
    )
    for run_id, record in records.items():
        run_tasks = tasks.get(run_id, [])
        record["task_records"] = run_tasks
        if run_tasks:
            record["task_ids"] = [
                str(item["task_id"]) for item in run_tasks if item.get("task_id")
            ]
        else:
            record["task_ids"] = [
                str(value)
                for value in record.get("task_ids", [])
                if isinstance(value, (str, int)) and str(value)
            ]
        if not record.get("output_artifacts"):
            record["output_artifacts"] = [
                artifact
                for task in run_tasks
                for artifact in task.get("output_artifacts", [])
            ]
        record["runtime_relations"] = [
            relation
            for relation in run_relations
            if relation.get("from_run_id") == run_id or relation.get("to_run_id") == run_id
        ]
        record["runtime_relations_available"] = relations_available and relation_binding_available
        record["runtime_tasks_available"] = tasks_available
        record["runtime_run_events"], run_events_available = _runtime_run_events(
            client, project, run_id
        )
        record["runtime_run_events_available"] = run_events_available
        task_events: dict[str, list[dict[str, Any]]] = {}
        task_events_available = tasks_available
        for task in run_tasks:
            task_id = str(task.get("task_id") or "")
            if not task_id:
                continue
            events, available = _runtime_task_events(client, project, task_id)
            task_events[task_id] = events
            task_events_available = task_events_available and available
        record["runtime_task_events"] = task_events
        record["runtime_task_events_available"] = task_events_available
        record["runtime_evidence"] = _runtime_attached_values(
            record, run_tasks, "evidence", "evidence_items"
        )
        record["runtime_receipts"] = _runtime_attached_values(
            record, run_tasks, "receipt", "receipts", "command_receipt"
        )
        record["runtime_lineage_gaps"] = _lineage_gaps(record)


def _runtime_task_records(
    client: Any,
    project: str,
    *,
    project_identities: set[str] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], bool]:
    tasks_family = getattr(client, "tasks", None)
    method = getattr(tasks_family, "list", None)
    if not callable(method):
        method = getattr(client, "list_project_tasks", None)
    if not callable(method):
        return {}, False
    try:
        value = _unwrap_runtime_result(
            method(project) if tasks_family is not None and hasattr(tasks_family, "list") else method(project)
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return {}, False
    if isinstance(value, Mapping):
        if "items" not in value:
            return {}, False
        value = value["items"]
    if not isinstance(value, (list, tuple)):
        return {}, False
    by_run: dict[str, list[dict[str, Any]]] = {}
    accepted_projects = project_identities or {str(project)}
    binding_available = True
    for raw in value:
        item = _as_mapping(raw)
        if item is None:
            binding_available = False
            continue
        supplied_projects = _runtime_project_owners(item)
        if not supplied_projects or any(value not in accepted_projects for value in supplied_projects):
            # A project-scoped list must identify the owning project. Never
            # accept an unowned task or a task from another project, even if a
            # hostile/misbehaving service reuses a run id.
            binding_available = False
            continue
        task_id = str(item.get("task_id") or item.get("id") or "")
        run_id = str(item.get("run_id") or "")
        if not task_id or not run_id:
            continue
        task = dict(item)
        task["task_id"] = task_id
        output_raw = task.get("output_artifacts") or task.get("outputs")
        if not output_raw and isinstance(task.get("result"), Mapping):
            result = task["result"]
            output_raw = result.get("output_artifacts") or result.get("outputs")
        task["output_artifacts"] = _artifact_list(output_raw)
        by_run.setdefault(run_id, []).append(task)
    if not binding_available:
        return {}, False
    return by_run, binding_available


def _runtime_relations(client: Any, project: str) -> tuple[list[dict[str, Any]], bool]:
    media = getattr(client, "media", None)
    method = getattr(media, "list_relations", None)
    if not callable(method):
        method = getattr(client, "list_media_relations", None)
    if not callable(method):
        return [], False
    try:
        value = _unwrap_runtime_result(method(project))
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return [], False
    if isinstance(value, Mapping):
        if "items" not in value:
            return [], False
        value = value["items"]
    if not isinstance(value, (list, tuple)):
        return [], False
    return [item for raw in value if (item := _as_mapping(raw)) is not None], True


def _runtime_run_relations(
    relations: list[dict[str, Any]], *, known_run_ids: set[str]
) -> tuple[list[dict[str, Any]], bool]:
    """Filter media relations to explicit, supported run-to-run bindings.

    The runtime contract defines media relations as directional
    ``from_object_id``/``to_object_id`` links.  Those object links cannot be
    promoted to run lineage.  A relation is usable here only when the runtime
    explicitly supplies ``from_run_id`` and ``to_run_id`` and uses the
    canonical ``derived_from`` kind (from/child -> to/parent).
    """

    if not relations:
        return [], True
    selected: list[dict[str, Any]] = []
    binding_available = True
    for relation in relations:
        kind = relation.get("kind")
        from_run = relation.get("from_run_id")
        to_run = relation.get("to_run_id")
        if kind != "derived_from" or not isinstance(from_run, str) or not isinstance(to_run, str):
            return [], False
        if from_run in known_run_ids and to_run in known_run_ids:
            selected.append({"from_run_id": from_run, "to_run_id": to_run, "kind": kind})
        else:
            binding_available = False
    return selected, binding_available


def _runtime_project_identities(client: Any, project: str) -> set[str]:
    """Resolve the selected runtime project's accepted id and slug."""

    identities = {str(project)}
    projects = getattr(client, "projects", None)
    method = getattr(projects, "show", None)
    if not callable(method):
        method = getattr(client, "get_project", None)
    if not callable(method):
        return identities
    try:
        value = _unwrap_runtime_result(method(project))
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return identities
    resource = _as_mapping(value)
    if resource is None:
        return identities
    for key in ("project_id", "id", "slug", "project_slug"):
        value = resource.get(key)
        if value is not None and str(value):
            identities.add(str(value))
    return identities


def _assert_runtime_project(
    record: Mapping[str, Any],
    project: str,
    *,
    project_identities: set[str] | None = None,
) -> None:
    accepted = project_identities or {str(project)}
    supplied_projects = _runtime_project_owners(record)
    if not supplied_projects:
        raise IterationVideoError(
            f"runtime run {record.get('run_id') or '<unknown>'} has no project ownership"
        )
    if any(value not in accepted for value in supplied_projects):
        supplied = supplied_projects[0]
        raise IterationVideoError(
            f"runtime run {record.get('run_id') or '<unknown>'} belongs to project {supplied!r}, "
            f"not selected project {project!r}"
        )


def _runtime_project_owners(record: Mapping[str, Any]) -> list[str]:
    """Return every explicit project owner, rejecting empty owner fields.

    Runtime resources may expose an id and a slug simultaneously. Treating
    those fields as an ``or`` chain would let a foreign value hide behind a
    valid one, so ownership is valid only when every supplied value is a
    non-empty identity.
    """
    owners: list[str] = []
    for key in ("project_id", "project", "project_slug"):
        if key not in record:
            continue
        value = record[key]
        if value is None or not str(value):
            return []
        owners.append(str(value))
    return owners


def _runtime_run_events(
    client: Any, project: str, run_id: str
) -> tuple[list[dict[str, Any]], bool]:
    runs = getattr(client, "runs", None)
    method = getattr(runs, "events", None)
    if not callable(method):
        method = getattr(client, "list_run_events", None)
    if not callable(method):
        return [], False
    try:
        value = _unwrap_runtime_result(method(project, run_id)) if runs is not None and hasattr(runs, "events") else _unwrap_runtime_result(method(run_id))
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return [], False
    return _scoped_events(value, aggregate_id=run_id)


def _runtime_task_events(
    client: Any, project: str, task_id: str
) -> tuple[list[dict[str, Any]], bool]:
    tasks = getattr(client, "tasks", None)
    method = getattr(tasks, "events", None)
    if not callable(method):
        method = getattr(client, "list_events", None)
    if not callable(method):
        return [], False
    try:
        value = _unwrap_runtime_result(method(task_id, project)) if tasks is not None and hasattr(tasks, "events") else _unwrap_runtime_result(method(aggregate_id=task_id))
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return [], False
    return _scoped_events(value, aggregate_id=task_id)


def _scoped_events(value: Any, *, aggregate_id: str) -> tuple[list[dict[str, Any]], bool]:
    """Return only events explicitly bound to the requested run/task.

    A malformed response or one containing an event for another aggregate is
    unavailable, even when some entries happen to match.  This prevents a
    broad project event read from becoming an accidental lineage source.
    """

    if isinstance(value, Mapping):
        if "items" not in value:
            return [], False
        raw = value["items"]
    else:
        raw = value
    if not isinstance(raw, (list, tuple)):
        return [], False
    events = [_as_mapping(item) for item in raw]
    if any(item is None for item in events):
        return [], False
    exact = [item for item in events if item.get("aggregate_id") == aggregate_id]
    return exact, len(exact) == len(events)


def _as_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return None


def _runtime_attached_values(
    run: Mapping[str, Any], tasks: list[Mapping[str, Any]], *keys: str
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    bound_task_ids = {
        str(task.get("task_id"))
        for task in tasks
        if task.get("task_id") is not None and str(task.get("task_id"))
    }
    raw_run_task_ids = run.get("task_ids")
    if isinstance(raw_run_task_ids, (list, tuple)):
        bound_task_ids.update(
            str(value) for value in raw_run_task_ids if value is not None and str(value)
        )
    for resource in (run, *tasks):
        owner_run_id = str(run.get("run_id") or "")
        owner_task_id = str(resource.get("task_id") or "")
        resource_task_ids = {owner_task_id} if owner_task_id else bound_task_ids
        for key in keys:
            value = resource.get(key)
            if key == "receipt" and value is not None and not isinstance(value, (list, tuple)):
                value = [value]
            if isinstance(value, Mapping):
                value = [value]
            if isinstance(value, (list, tuple)):
                found.extend(
                    item
                    for raw in value
                    if (item := _as_mapping(raw)) is not None
                    and _fact_belongs_to(
                        item,
                        run_id=owner_run_id,
                        task_id=owner_task_id,
                        task_ids=resource_task_ids,
                        require_subject=True,
                    )
                )
        events = list(resource.get("runtime_run_events", ()) or ())
        task_events = resource.get("runtime_task_events", {})
        if isinstance(task_events, Mapping):
            events.extend(event for values in task_events.values() for event in values or ())
        for event in events:
            payload = event.get("payload") if isinstance(event, Mapping) else None
            if isinstance(payload, Mapping):
                for key in keys:
                    value = payload.get(key)
                    if isinstance(value, Mapping):
                        item = dict(value)
                        if _fact_belongs_to(
                            item,
                            run_id=owner_run_id,
                            task_id=owner_task_id,
                            task_ids=resource_task_ids,
                            require_subject=False,
                        ):
                            found.append(item)
                    elif isinstance(value, (list, tuple)):
                        found.extend(
                            item
                            for raw in value
                            if (item := _as_mapping(raw)) is not None
                            and _fact_belongs_to(
                                item,
                                run_id=owner_run_id,
                                task_id=owner_task_id,
                                task_ids=resource_task_ids,
                                require_subject=False,
                            )
                        )
    return found


def _fact_belongs_to(
    fact: Mapping[str, Any],
    *,
    run_id: str,
    task_id: str,
    task_ids: set[str],
    require_subject: bool,
) -> bool:
    fact_run_id = fact.get("run_id")
    if fact_run_id is not None and str(fact_run_id) != run_id:
        return False
    fact_task_id = fact.get("task_id")
    if fact_task_id is not None:
        if task_id and str(fact_task_id) != task_id:
            return False
        if str(fact_task_id) not in task_ids:
            return False
    return not require_subject or fact_run_id is not None or fact_task_id is not None


def _lineage_gaps(record: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not record.get("runtime_parent_lineage_available"):
        gaps.append("lineage_unavailable")
    if not record.get("runtime_tasks_available"):
        gaps.append("tasks_unavailable")
    if not record.get("runtime_relations_available"):
        gaps.append("relations_unavailable")
    if not record.get("runtime_run_events_available"):
        gaps.append("run_events_unavailable")
    if not record.get("runtime_task_events_available"):
        gaps.append("task_events_unavailable")
    if not record.get("runtime_evidence"):
        gaps.append("evidence_unavailable")
    if not record.get("runtime_receipts"):
        gaps.append("receipts_unavailable")
    if not record.get("output_artifacts") and not any(
        task.get("output_artifacts") for task in record.get("task_records", ())
    ):
        gaps.append("task_outputs_unavailable")
    return gaps


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
    parent_present = "parent_run_ids" in source or "parent_run_ids" in spec
    parent_run_ids = source.get("parent_run_ids") if "parent_run_ids" in source else spec.get("parent_run_ids")
    if parent_present:
        record["parent_run_ids"] = parent_run_ids
    provenance_present = "provenance" in source or "provenance" in spec
    provenance = source.get("provenance") if "provenance" in source else spec.get("provenance")
    if provenance_present:
        record["provenance"] = provenance
    record["runtime_parent_lineage_available"] = (
        (not parent_present or _valid_parent_collection(parent_run_ids))
        and (not provenance_present or _valid_provenance(provenance))
        and (parent_present or provenance_present)
    )
    record["input_artifacts"] = _artifact_list(
        source.get("input_artifacts") or spec.get("input_artifacts") or source.get("inputs") or spec.get("inputs")
    )
    output_raw = (
        source.get("output_artifacts") or source.get("outputs") or result.get("output_artifacts")
        or result.get("outputs") or result.get("output_objects") or spec.get("output_artifacts")
    )
    record["output_artifacts"] = _artifact_list(output_raw)
    return record


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
        lineage_incomplete = (
            not bool(record.get("runtime_parent_lineage_available"))
            or "invalid_parent_lineage" in unresolved
        )
        nodes[run_id] = RuntimeRunNode(
            run_id=run_id,
            record=record,
            depth=depth,
            label="target" if run_id == target_run_id else "pulled_by_ancestry",
            parent_edges=parents,
            unresolved_parent_run_ids=unresolved,
            lineage_incomplete=lineage_incomplete,
        )
        queue.extend((str(edge["run_id"]), depth + 1) for edge in parents)
    return sorted(nodes.values(), key=lambda item: (-item.depth, item.selection_order, item.run_id))


def _runtime_parent_edges(record: Mapping[str, Any], records: Mapping[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    raw_parent_ids = record.get("parent_run_ids")
    raw_edges: list[Any] = list(raw_parent_ids) if isinstance(raw_parent_ids, (list, tuple)) else []
    invalid_lineage = raw_parent_ids is not None and not _valid_parent_collection(raw_parent_ids)
    provenance_value = record.get("provenance")
    provenance = provenance_value if isinstance(provenance_value, Mapping) else {}
    if provenance_value is not None and not _valid_provenance(provenance_value):
        invalid_lineage = True
    contributing = provenance.get("contributing_runs")
    if contributing is not None and isinstance(contributing, (list, tuple)):
        raw_edges.extend(contributing)
    elif contributing is not None:
        invalid_lineage = True
    for relation in record.get("runtime_relations", []) or []:
        if isinstance(relation, Mapping) and relation.get("from_run_id") == record.get("run_id"):
            raw_edges.append({
                "run_id": relation.get("to_run_id"),
                "kind": relation.get("kind"),
            })
    edges: list[dict[str, Any]] = []
    unresolved: list[str] = []
    if invalid_lineage:
        unresolved.append("invalid_parent_lineage")
    seen: set[str] = set()
    for raw in raw_edges:
        value = raw if isinstance(raw, Mapping) else {"run_id": raw}
        run_id = value.get("run_id") if isinstance(value, Mapping) else None
        if not isinstance(run_id, str) or not _is_runtime_identifier(run_id):
            if "invalid_parent_lineage" not in unresolved:
                unresolved.append("invalid_parent_lineage")
            continue
        if run_id in seen:
            continue
        seen.add(run_id)
        edge = {"run_id": run_id, "kind": str(value.get("kind") or "causal")}
        if run_id not in records:
            unresolved.append(run_id)
        else:
            edges.append(edge)
    return edges, unresolved


def _valid_parent_collection(value: Any) -> bool:
    if not isinstance(value, (list, tuple)):
        return False
    for item in value:
        candidate = item.get("run_id") if isinstance(item, Mapping) else item
        if not isinstance(candidate, str) or not _is_runtime_identifier(candidate):
            return False
    return True


def _valid_provenance(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    contributing = value.get("contributing_runs")
    return contributing is None or _valid_parent_collection(contributing)


def _build_runtime_inputs(nodes: list[RuntimeRunNode], *, target_run_id: str, project_slug: str) -> tuple[dict[str, Any], dict[str, Any]]:
    total = len(nodes)
    unresolved = [
        {"run_id": node.run_id, "missing_parent_run_ids": node.unresolved_parent_run_ids}
        for node in nodes if node.unresolved_parent_run_ids
    ]
    missing_lineage = [
        node.run_id
        for node in nodes
        if node.lineage_incomplete
        or not node.record.get("runtime_parent_lineage_available")
    ]
    missing_task_outputs = [
        node.run_id
        for node in nodes
        if not node.record.get("runtime_tasks_available")
        or not node.record.get("task_records")
        or not node.record.get("output_artifacts")
    ]
    missing_evidence = [node.run_id for node in nodes if not node.record.get("runtime_evidence")]
    missing_receipts = [node.run_id for node in nodes if not node.record.get("runtime_receipts")]
    missing_relations = [node.run_id for node in nodes if not node.record.get("runtime_relations_available")]
    missing_events = [
        node.run_id
        for node in nodes
        if not node.record.get("runtime_run_events_available")
        or not node.record.get("runtime_task_events_available")
    ]
    dimensions = {
        "lineage": not unresolved and not missing_lineage,
        "task_outputs": not missing_task_outputs,
        "evidence": not missing_evidence,
        "relations": not missing_relations,
        "receipts": not missing_receipts,
        "events": not missing_events,
    }
    # A complete score requires every canonical runtime source.  In
    # particular, resolved parent IDs alone never imply complete lineage.
    data_quality = round(sum(dimensions.values()) / len(dimensions), 3) if total else 0.0
    unavailable_sources = {
        gap for node in nodes for gap in node.record.get("runtime_lineage_gaps", [])
    }
    if missing_lineage:
        unavailable_sources.add("lineage_unavailable")
    quality = {
        "schema_version": SCHEMA_VERSION,
        "target_run_id": target_run_id,
        "total_runs": total,
        "data_quality": data_quality,
        "dimensions": dimensions,
        "unresolved_producer_runs": unresolved,
        "missing_lineage": missing_lineage,
        "missing_task_outputs": missing_task_outputs,
        "missing_evidence": missing_evidence,
        "missing_relations": missing_relations,
        "missing_receipts": missing_receipts,
        "missing_events": missing_events,
        "unavailable_sources": sorted(unavailable_sources),
        "relation_count": sum(len(node.record.get("runtime_relations", [])) for node in nodes),
        "evidence_count": sum(len(node.record.get("runtime_evidence", [])) for node in nodes),
        "receipt_count": sum(len(node.record.get("runtime_receipts", [])) for node in nodes),
        "run_event_count": sum(len(node.record.get("runtime_run_events", [])) for node in nodes),
        "task_event_count": sum(
            len(events)
            for node in nodes
            for events in (node.record.get("runtime_task_events", {}) or {}).values()
        ),
        "events_role": "observational_only",
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
            "lineage_incomplete": node.lineage_incomplete,
            "out_path": node.record.get("out_path"),
            "executor_id": node.record.get("executor_id"),
            "orchestrator_id": node.record.get("orchestrator_id"),
            "output_artifacts": node.record.get("output_artifacts", []),
            "task_ids": list(node.record.get("task_ids", [])),
            "relations": list(node.record.get("runtime_relations", [])),
            "evidence": list(node.record.get("runtime_evidence", [])),
            "receipts": list(node.record.get("runtime_receipts", [])),
            "run_events": list(node.record.get("runtime_run_events", [])),
            "task_events": dict(node.record.get("runtime_task_events", {})),
            "lineage_gaps": list(node.record.get("runtime_lineage_gaps", [])),
            "summary": None,
        })
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
    project_identities = _runtime_project_identities(client, project)
    all_records = _load_runtime_records(
        client, project, project_identities=project_identities
    )
    if not target_run_id or not _is_runtime_identifier(target_run_id):
        raise IterationVideoError(
            "target_run_id is required; pass the runtime-issued run id explicitly"
        )
    if target_run_id not in all_records:
        fetched = _runtime_run_show(
            client,
            project,
            target_run_id,
            project_identities=project_identities,
        )
        if fetched is not None:
            all_records[target_run_id] = fetched
            _attach_runtime_lineage(
                all_records,
                client=client,
                project=project,
                project_identities=project_identities,
            )
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
        default="rendering.remotion",
        help="Qualified rendering backend id.",
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
        default="rendering.remotion",
        help="Qualified rendering backend id.",
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
