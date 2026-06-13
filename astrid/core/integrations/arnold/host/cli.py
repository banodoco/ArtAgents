"""CLI handlers for the Arnold host.

This module provides the command-line interface handlers that route
``--engine arnold`` lifecycle verbs to the Arnold host.  Each handler
follows the same signature convention as the task-engine lifecycle
handlers: they accept a list of raw CLI arguments and return an integer
exit code.

Import boundary: Arnold imports are lazy inside function bodies.
The module-level imports touch only Astrid core and host-internal
modules (registry, shapes, envelope — all Arnold-free).
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any


def _parse_inputs(raw_inputs: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw in raw_inputs:
        key, separator, value = raw.partition("=")
        if not separator or not key:
            raise ValueError("--input values must use key=value format")
        parsed[key] = value
    return parsed


def _load_arnold_run_record(run_root: Path) -> dict[str, Any]:
    record_path = run_root / "arnold_run.json"
    try:
        payload = json.loads(record_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"active run {run_root.name!r} is missing arnold_run.json"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"active run {run_root.name!r} has invalid arnold_run.json: {exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"active run {run_root.name!r} has non-object arnold_run.json")
    return payload


def _active_run_context(project_slug: str) -> tuple[str, Path, Any]:
    from astrid.core.foundation.project_paths import project_dir, validate_project_slug
    from astrid.core.integrations.arnold.session.records import load_arnold_run_record
    from astrid.core.project.current_run import read_current_run

    slug = validate_project_slug(project_slug)
    run_id = read_current_run(slug)
    if run_id is None:
        raise RuntimeError(
            f"project {slug!r} has no active Arnold run; "
            f"recovery: astrid start <workflow-id> --engine arnold --project {slug}"
        )
    run_root = project_dir(slug) / "runs" / run_id
    return slug, run_root, load_arnold_run_record(run_root)


def _resolve_active_workflow_id(project_slug: str, run_root: Path) -> str:
    from astrid.core.integrations.arnold.host.registry import get_host_shape_registry

    payload = _load_arnold_run_record(run_root)
    workflow_id = payload.get("workflow_id")
    if not isinstance(workflow_id, str) or not workflow_id:
        raise RuntimeError(
            f"active run {run_root.name!r} does not record a workflow_id in arnold_run.json"
        )

    registry = get_host_shape_registry()
    if not registry.is_allowlisted(workflow_id):
        raise RuntimeError(
            f"active run for project {project_slug!r} records unsupported Arnold workflow "
            f"{workflow_id!r}"
        )
    return workflow_id


def _render_active_operation(project_slug: str) -> tuple[str, dict[str, Any]]:
    from astrid.core.integrations.arnold.host.registry import get_host_shape_registry
    from astrid.core.integrations.arnold.host.render import render_operation_snapshot
    from astrid.core.integrations.arnold.session.render import (
        load_session_snapshot,
        render_session_snapshot,
    )

    slug, run_root, run_record = _active_run_context(project_slug)
    if run_record.mode == "session-succession":
        rendered = render_session_snapshot(load_session_snapshot(slug, run_root))
        return rendered.text, rendered.lifecycle_json

    workflow_id = _resolve_active_workflow_id(slug, run_root)
    snapshot = get_host_shape_registry().snapshot_operation(
        project_slug=slug,
        workflow_id=workflow_id,
        run_id=run_record.run_id,
    )
    rendered = render_operation_snapshot(snapshot)
    return rendered.text, rendered.lifecycle_json


def _event_tail_hash(run_root: Path) -> str:
    from astrid.core.task.events import EVENTS_FILENAME, ZERO_HASH, read_events

    events = read_events(run_root / EVENTS_FILENAME)
    if not events:
        return ZERO_HASH
    tail_hash = events[-1].get("hash")
    return tail_hash if isinstance(tail_hash, str) else ZERO_HASH


def _current_stage_from_cursor(cursor: dict[str, Any] | None, fallback: str | None) -> str:
    if isinstance(cursor, dict):
        stage = cursor.get("stage")
        if isinstance(stage, str) and stage:
            return stage
    if fallback:
        return fallback
    raise RuntimeError("active Arnold run has no current stage")


def _next_stage_for_decision(
    *,
    pipeline_manifest: dict[str, Any],
    current_stage: str,
    decision: str,
) -> str:
    for raw_edge in pipeline_manifest.get("edges", ()):
        if not isinstance(raw_edge, dict):
            continue
        if raw_edge.get("source") == current_stage and raw_edge.get("label") == decision:
            target = raw_edge.get("target")
            if isinstance(target, str) and target:
                return target
    raise RuntimeError(
        f"stage {current_stage!r} has no Arnold edge labelled {decision!r}"
    )


def _resolve_start_invocation_templates(
    *,
    workflow_id: str,
    shape: Any,
    pipeline: Any,
) -> dict[str, Any]:
    """Resolve the startup invocation contract for a host workflow.

    Compiled workflows must derive their executable/control stage mappings from
    the compiled pipeline itself so startup stays data-driven. Legacy static
    workflows continue to use the frozen allowlisted templates.
    """
    from astrid.core.integrations.arnold.host.invocation import (
        ALLOWLISTED_INVOCATION_TEMPLATES,
        invocation_templates_from_compiled_pipeline,
    )

    shape_metadata = getattr(shape, "metadata", {})
    if isinstance(shape_metadata, dict) and shape_metadata.get("compiled") is True:
        templates = invocation_templates_from_compiled_pipeline(workflow_id, pipeline)
    else:
        templates = dict(ALLOWLISTED_INVOCATION_TEMPLATES.get(workflow_id, {}))

    if getattr(shape, "entry_stage_id", None) not in templates:
        raise RuntimeError(
            f"Arnold workflow {workflow_id!r} could not resolve entry stage "
            f"{getattr(shape, 'entry_stage_id', None)!r} through its startup "
            "invocation templates"
        )
    return templates


def _make_human_resume_cursor(
    *,
    run_id: str,
    current_stage: str,
    next_stage: str,
    human_payload: dict[str, Any],
    lease: dict[str, Any],
) -> Any:
    from astrid.core.integrations.arnold.host.compat import compat
    from astrid.core.integrations.arnold.host.envelope import HOST_PLUGIN_ID
    from astrid.core.integrations.arnold.host.hooks import (
        ASTRID_HOOK_NAMESPACE,
        LEASE_EXTENSION_KEY,
        project_lease_for_arnold,
    )

    step_context = compat.StepContext(
        inputs={"human_input": dict(human_payload)},
        hook_extensions={
            ASTRID_HOOK_NAMESPACE: {
                LEASE_EXTENSION_KEY: project_lease_for_arnold(lease),
            }
        },
    )
    return compat.ResumeCursorRef(
        plugin_id=HOST_PLUGIN_ID,
        run_id=run_id,
        cursor={
            "stage": next_stage,
            "previous_stage": current_stage,
            "human_input": dict(human_payload),
            "ctx": step_context,
        },
    )


def _append_arnold_ack_event(
    *,
    run_root: Path,
    run_id: str,
    current_stage: str,
    next_stage: str,
    decision: dict[str, Any],
    produces_reverify: dict[str, Any],
    lease: dict[str, Any],
) -> None:
    from astrid.core.task.events import append_event_locked
    from astrid.core.util.time import utc_now_iso

    append_event_locked(
        run_root,
        {
            "kind": "human_feedback",
            "engine": "arnold",
            "run_id": run_id,
            "stage_id": current_stage,
            "next_stage_id": next_stage,
            "action": decision["action"],
            "notes": decision.get("notes", ""),
            "state_patch": dict(decision.get("state_patch", {})),
            "produces_reverify": dict(produces_reverify),
            "ts": utc_now_iso(),
        },
        expected_writer_epoch=lease.get("writer_epoch"),
        expected_prev_hash=_event_tail_hash(run_root),
    )


def _resume_cursor_payload(cursor: Any) -> tuple[Any, Any, Any]:
    return (
        getattr(cursor, "plugin_id", None),
        getattr(cursor, "run_id", None),
        getattr(cursor, "cursor", None),
    )


def _ack_active_arnold_stage(
    *,
    project_slug: str,
    stage_arg: str | None,
    human_payload: dict[str, Any],
) -> None:
    from astrid.core._shared.jsonio import write_json_atomic
    from astrid.core.integrations.arnold.host.compat import persist_resume_cursor
    from astrid.core.integrations.arnold.host.driver import get_driver
    from astrid.core.integrations.arnold.host.envelope import project_runtime_envelope
    from astrid.core.integrations.arnold.host.hooks import (
        read_run_state,
        require_lease_for_arnold,
    )
    from astrid.core.integrations.arnold.host.invocation import parse_human_resume_payload
    from astrid.core.integrations.arnold.host.registry import get_host_shape_registry
    from astrid.core.integrations.arnold.session.driver import resume_session_run
    from astrid.core.integrations.arnold.session.render import load_session_snapshot

    slug, run_root, run_record = _active_run_context(project_slug)
    if run_record.mode == "session-succession":
        snapshot = load_session_snapshot(slug, run_root)
        current_stage = snapshot.current_stage_id
        if not current_stage:
            raise RuntimeError("session run has no current stage")
        if stage_arg is not None and stage_arg != current_stage:
            raise RuntimeError(
                f"ack stage {stage_arg!r} does not match active Arnold stage {current_stage!r}"
            )
        from astrid.core.integrations.arnold.host.compat import read_resume_cursor

        _emit_session_plan_mutation_from_payload(
            slug,
            run_root=run_root,
            run_id=run_record.run_id,
            human_payload=human_payload,
        )
        resume_session_run(
            slug,
            run_id=run_record.run_id,
            human_input=human_payload,
            resume_cursor=read_resume_cursor(str(run_root)),
        )
        return

    run_id = run_record.run_id
    workflow_id = _resolve_active_workflow_id(slug, run_root)
    pipeline_manifest = json.loads((run_root / "pipeline.json").read_text(encoding="utf-8"))
    if not isinstance(pipeline_manifest, dict):
        raise RuntimeError(f"active run {run_id!r} has non-object pipeline.json")

    registry = get_host_shape_registry()
    snapshot = registry.snapshot_operation(
        project_slug=slug,
        workflow_id=workflow_id,
        run_id=run_id,
    )
    current_stage = _current_stage_from_cursor(snapshot.cursor, snapshot.next_stage_id)
    if stage_arg is not None and stage_arg != current_stage:
        raise RuntimeError(
            f"ack stage {stage_arg!r} does not match active Arnold stage {current_stage!r}"
        )

    decision, produces_reverify = parse_human_resume_payload(human_payload)
    next_stage = _next_stage_for_decision(
        pipeline_manifest=pipeline_manifest,
        current_stage=current_stage,
        decision=decision["action"],
    )
    lease = require_lease_for_arnold(run_root)
    resume_cursor = _make_human_resume_cursor(
        run_id=run_id,
        current_stage=current_stage,
        next_stage=next_stage,
        human_payload=human_payload,
        lease=lease,
    )

    state = read_run_state(run_root)
    state.update(decision.get("state_patch", {}))

    envelope = project_runtime_envelope(slug, workflow_id=workflow_id, run_id=run_id)
    driver = get_driver()
    prior_cursor = getattr(envelope, "resume_cursor", None)
    resumed = driver.resume(envelope, resume_cursor)
    driver.advance(resumed)
    checkpoint = driver.checkpoint(resumed)
    resulting_cursor = getattr(resumed, "resume_cursor", None)
    if (
        resulting_cursor is None
        or _resume_cursor_payload(resulting_cursor) == _resume_cursor_payload(prior_cursor)
    ):
        resulting_cursor = resume_cursor
    persist_resume_cursor(str(run_root), resulting_cursor)

    write_json_atomic(run_root / "state.json", state)
    raw_run_record = _load_arnold_run_record(run_root)
    write_json_atomic(
        run_root / "arnold_run.json",
        {
            **raw_run_record,
            "status": "running" if next_stage != "halt" else "completed",
            "last_ack": {
                "stage": current_stage,
                "next_stage": next_stage,
                "decision": dict(decision),
                "checkpoint": getattr(checkpoint, "cursor", None),
            },
        },
    )
    _append_arnold_ack_event(
        run_root=run_root,
        run_id=run_id,
        current_stage=current_stage,
        next_stage=next_stage,
        decision=decision,
        produces_reverify=produces_reverify,
        lease=lease,
    )


def _emit_session_plan_mutation_from_payload(
    project_slug: str,
    *,
    run_root: Path,
    run_id: str,
    human_payload: dict[str, Any],
) -> None:
    """Append an explicit plan mutation before A3b successor compilation.

    Session-succession treats ``human_input.plan_mutation`` as a mutation
    marker. When the payload carries a concrete ``diff`` we also persist the
    canonical ``plan_mutated`` task event first, so the successor segment is
    compiled from event-ledger state rather than a live Arnold graph edit.
    """
    plan_mutation = human_payload.get("plan_mutation")
    if not isinstance(plan_mutation, dict):
        return
    raw_diff = plan_mutation.get("diff")
    if raw_diff is None and isinstance(plan_mutation.get("op"), str):
        raw_diff = {
            key: value
            for key, value in plan_mutation.items()
            if key not in {"author", "plan_hash"}
        }
    if not isinstance(raw_diff, dict) or not isinstance(raw_diff.get("op"), str):
        return

    from astrid.core.task.plan import TaskPlanError
    from astrid.core.task.plan.verbs import (
        _apply_diff,
        _load_effective_plan,
        _validate_and_emit,
    )

    prior_plan, _events, plan_path = _load_effective_plan(run_root)
    try:
        proposed_plan = _apply_diff(prior_plan, raw_diff)
    except TaskPlanError as exc:
        raise RuntimeError(f"invalid plan_mutation.diff: {exc}") from exc

    author = plan_mutation.get("author")
    if not isinstance(author, str) or not author:
        author = f"agent:{project_slug}"
    result = _validate_and_emit(
        run_root,
        plan_path,
        project_slug,
        None,
        run_id,
        prior_plan,
        proposed_plan,
        diff=raw_diff,
        author=author,
    )
    if result != 0:
        raise RuntimeError("failed to emit plan_mutated event for Arnold session resume")


def _start_validated_arnold_run(
    *,
    project_slug: str,
    workflow_id: str,
    shape: Any,
    driver: Any,
    initial_state: dict[str, Any],
    input_values: dict[str, str],
    requested_run_id: str | None,
    json_mode: bool,
    argv: list[str],
) -> int:
    from astrid.core._shared.jsonio import write_json_atomic
    from astrid.core.foundation.project_paths import (
        project_dir,
        validate_project_slug,
        validate_run_id,
    )
    from astrid.core.integrations.arnold.host.envelope import project_runtime_envelope
    from astrid.core.io.cas import canonical_json_digest
    from astrid.core.project import require_project
    from astrid.core.project.project import ProjectError
    from astrid.core.project.current_run import read_current_run, write_current_run
    from astrid.core.session.binding import SessionBindingError, resolve_current_session
    from astrid.core.session.lease import write_lease_init
    from astrid.core.task.events import ZERO_HASH, append_event_locked, make_run_started_event
    from astrid.core.util.time import utc_now_iso

    slug = validate_project_slug(project_slug)
    try:
        require_project(slug)
    except ProjectError as exc:
        raise RuntimeError(
            f"project {slug!r} not found; create one with `astrid projects create {slug}`"
        ) from exc
    if read_current_run(slug) is not None:
        raise RuntimeError(
            f"active run already exists for project {slug!r}; "
            f"recovery: astrid abort --project {slug}"
        )

    run_id = validate_run_id(requested_run_id) if requested_run_id else _generate_run_id()
    proj_root = project_dir(slug)
    run_root = proj_root / "runs" / run_id
    if run_root.exists():
        raise RuntimeError(f"run {run_id!r} already exists")

    plan_hash = canonical_json_digest(
        {
            "engine": "arnold",
            "workflow_id": workflow_id,
            "shape_metadata": getattr(shape, "metadata", {}),
            "entry_stage_id": getattr(shape, "entry_stage_id", None),
            "stage_labels": getattr(shape, "stage_labels", {}),
            "state": initial_state,
            "inputs": input_values,
        }
    )

    pipeline_builder = getattr(shape, "pipeline_builder", None)
    if pipeline_builder is None:
        raise RuntimeError(f"Arnold workflow {workflow_id!r} has no pipeline builder")
    pipeline = pipeline_builder(
        state=initial_state,
        project=slug,
        run_root=str(run_root),
        artifact_root=str(run_root),
        cas_project_dir=str(proj_root),
    )
    if getattr(pipeline, "entry_stage_id", None) != getattr(shape, "entry_stage_id", None):
        raise RuntimeError(
            f"shape {workflow_id!r} built entry stage "
            f"{getattr(pipeline, 'entry_stage_id', None)!r}, expected "
            f"{getattr(shape, 'entry_stage_id', None)!r}"
        )
    _resolve_start_invocation_templates(
        workflow_id=workflow_id,
        shape=shape,
        pipeline=pipeline,
    )

    created_run_dir = False
    pointer_written = False
    try:
        run_root.mkdir(parents=True)
        created_run_dir = True
        write_json_atomic(run_root / "arnold_run.json", {
            "engine": "arnold",
            "workflow_id": workflow_id,
            "run_id": run_id,
            "status": "prepared",
            "argv": ["start", *argv],
            "created_at": utc_now_iso(),
            "inputs": input_values,
            "state": initial_state,
            "plan_hash": plan_hash,
        })
        write_json_atomic(run_root / "state.json", dict(initial_state))
        write_json_atomic(run_root / "pipeline.json", _pipeline_manifest(pipeline))

        session_id = "legacy"
        try:
            bound = resolve_current_session(slug=slug)
            if bound is not None:
                session_id = bound.id
        except SessionBindingError:
            session_id = "legacy"
        write_lease_init(run_root, session_id=session_id, plan_hash=plan_hash)

        append_event_locked(
            run_root,
            {
                **make_run_started_event(run_id, plan_hash),
                "engine": "arnold",
                "workflow_id": workflow_id,
            },
            expected_writer_epoch=0,
            expected_prev_hash=ZERO_HASH,
        )

        envelope = project_runtime_envelope(slug, workflow_id=workflow_id, run_id=run_id)
        driver.checkpoint(envelope)

        write_current_run(slug, run_id)
        pointer_written = True
    except Exception:
        if pointer_written:
            from astrid.core.project.current_run import clear_current_run

            clear_current_run(slug)
        if created_run_dir:
            shutil.rmtree(run_root, ignore_errors=True)
        raise

    if json_mode:
        print(
            json.dumps(
                {
                    "engine": "arnold",
                    "project": slug,
                    "run_id": run_id,
                    "state": "started",
                    "workflow_id": workflow_id,
                    "plan_hash": plan_hash,
                    "next_command": f"astrid next --engine arnold --project {slug}",
                },
                sort_keys=True,
            )
        )
    else:
        print(f"started {workflow_id}")
        print(f"  engine:    arnold")
        print(f"  project:   {slug}")
        print(f"  run-id:    {run_id}")
        print(f"  plan-hash: {plan_hash}")
    return 0


def _generate_run_id() -> str:
    return "arnold-" + uuid.uuid4().hex[:12]


def _pipeline_manifest(pipeline: Any) -> dict[str, Any]:
    from astrid.core.integrations.arnold.host.builder import edge_manifest_entry

    stages = []
    for stage in tuple(getattr(pipeline, "stages", ()) or ()):
        stages.append(
            {
                "stage_id": getattr(stage, "stage_id", None),
                "label": getattr(stage, "label", None),
                "metadata": dict(getattr(stage, "metadata", {}) or {}),
            }
        )
    edges = []
    for edge in tuple(getattr(pipeline, "edges", ()) or ()):
        edges.append(
            edge_manifest_entry(
                source=getattr(edge, "source", None),
                target=getattr(edge, "target", None),
                label=getattr(edge, "label", None),
                source_port=getattr(edge, "source_port", None),
                target_port=getattr(edge, "target_port", None),
                logical_type=getattr(edge, "logical_type", None),
                artifact_type=getattr(edge, "artifact_type", None),
                metadata=getattr(edge, "metadata", None),
            )
        )
    return {
        "entry_stage_id": getattr(pipeline, "entry_stage_id", None),
        "stages": stages,
        "edges": edges,
    }


def cmd_start(args: list[str]) -> int:
    """Handle ``astrid start --engine arnold``.

    Creates a new Arnold run envelope, validates the requested workflow
    shape, and initiates the pipeline through the StepwiseDriver.
    """
    # ── Parse arguments ──────────────────────────────────────────────────
    import argparse

    parser = argparse.ArgumentParser(
        prog="astrid start --engine arnold",
        description="Start a new Arnold workflow run.",
    )
    parser.add_argument("workflow_arg", nargs="?", help="Workflow shape ID")
    parser.add_argument("--workflow", help="Workflow shape ID")
    parser.add_argument(
        "--from-plan",
        dest="from_plan",
        help="Start a session-succession run from a plan.json path or run reference.",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project slug for this run.",
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        dest="inputs",
        help="Input values (key=value format).",
    )
    parser.add_argument(
        "--state",
        default="{}",
        help="Initial state as JSON string.",
    )
    parser.add_argument("--name", default=None, help="optional run id")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    try:
        parsed = parser.parse_args(args)
    except SystemExit as exc:
        return int(exc.code or 2)

    try:
        initial_state = json.loads(parsed.state)
    except json.JSONDecodeError as exc:
        print(f"error: invalid --state JSON: {exc.msg}", file=sys.stderr)
        return 2
    if not isinstance(initial_state, dict):
        print("error: --state must decode to a JSON object", file=sys.stderr)
        return 2
    try:
        input_values = _parse_inputs(parsed.inputs)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if parsed.from_plan:
        if parsed.workflow or parsed.workflow_arg:
            print(
                "error: --from-plan is mutually exclusive with a static Arnold workflow id",
                file=sys.stderr,
            )
            return 2
        from astrid.core.integrations.arnold.session.cli import start_session_run

        try:
            return start_session_run(
                project_slug=parsed.project,
                from_plan=parsed.from_plan,
                initial_state=initial_state,
                input_values=input_values,
                requested_run_id=parsed.name,
                json_mode=bool(parsed.json),
                argv=list(args),
            )
        except Exception as exc:
            print(f"error: failed to start Arnold session: {exc}", file=sys.stderr)
            return 1

    workflow_raw = parsed.workflow or parsed.workflow_arg
    if not workflow_raw:
        print("error: Arnold start requires a workflow id", file=sys.stderr)
        return 2

    # ── Validate workflow shape ──────────────────────────────────────────
    from astrid.core.integrations.arnold.host.registry import (
        get_host_shape_registry,
    )

    registry = get_host_shape_registry()

    # Resolve alias
    workflow_id = registry.resolve_alias(workflow_raw) or workflow_raw

    if not registry.is_allowlisted(workflow_id):
        print(
            f"error: unknown Arnold workflow '{workflow_raw}'",
            file=sys.stderr,
        )
        print(
            f"  Valid workflows: {sorted(registry.allowlisted_ids)}",
            file=sys.stderr,
        )
        print(
            f"  Aliases: {registry.aliases}",
            file=sys.stderr,
        )
        return 2
    shape = registry.require(workflow_id)

    # ── Check driver availability ───────────────────────────────────────
    from astrid.core.integrations.arnold.host.driver import (
        get_driver,
        StepwiseDriverContractError,
    )

    try:
        driver = get_driver()
    except StepwiseDriverContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if exc.hint:
            print(f"  hint: {exc.hint}", file=sys.stderr)
        return 3
    except ImportError as exc:
        print(f"error: no compatible Arnold StepwiseDriver available: {exc}", file=sys.stderr)
        return 3

    try:
        return _start_validated_arnold_run(
            project_slug=parsed.project,
            workflow_id=workflow_id,
            shape=shape,
            driver=driver,
            initial_state=initial_state,
            input_values=input_values,
            requested_run_id=parsed.name,
            json_mode=bool(parsed.json),
            argv=list(args),
        )
    except Exception as exc:
        print(f"error: failed to start Arnold workflow: {exc}", file=sys.stderr)
        return 1


def cmd_next(args: list[str]) -> int:
    """Handle ``astrid next --engine arnold``.

    Peek/render only — does not execute a pipeline stage.  Renders the
    next operator-facing stage for human review.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="astrid next --engine arnold",
        description="Peek at the next Arnold pipeline stage (read-only).",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project slug for this run.",
    )

    try:
        parsed = parser.parse_args(args)
    except SystemExit as exc:
        return int(exc.code or 2)

    try:
        text, _ = _render_active_operation(parsed.project)
    except Exception as exc:
        print(f"error: failed to inspect Arnold workflow: {exc}", file=sys.stderr)
        return 1

    print(text, end="")
    return 0


def cmd_ack(args: list[str]) -> int:
    """Handle ``astrid ack --engine arnold``.

    Advances/resumes exactly one operator-facing stage with human input.
    Passes human input through ``ctx.inputs['human_input']``.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="astrid ack --engine arnold",
        description="Acknowledge and advance the current Arnold pipeline stage.",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project slug for this run.",
    )
    parser.add_argument(
        "--stage",
        help="Expected current Arnold stage id.",
    )
    parser.add_argument(
        "--payload",
        help="Composite human resume payload JSON.",
    )
    parser.add_argument(
        "--decision",
        choices=["approve", "reject"],
        help="Human decision for the current stage.",
    )
    parser.add_argument(
        "--notes",
        default="",
        help="Optional notes accompanying the decision.",
    )
    parser.add_argument(
        "--state-patch",
        default="{}",
        help="JSON state patch to apply on approve.",
    )
    parser.add_argument(
        "--produces-artifact",
        action="append",
        default=[],
        dest="produces_artifacts",
        help="Artifact path to re-verify as part of the resume payload.",
    )
    parser.add_argument(
        "--produces-input",
        action="append",
        default=[],
        dest="produces_inputs",
        help="Produces re-verification input (key=value format).",
    )

    try:
        parsed = parser.parse_args(args)
    except SystemExit as exc:
        return int(exc.code or 2)

    try:
        if parsed.payload:
            human_payload = json.loads(parsed.payload)
            if not isinstance(human_payload, dict):
                raise ValueError("--payload must decode to a JSON object")
        else:
            if parsed.decision is None:
                raise ValueError("Arnold ack requires --decision or --payload")
            state_patch = json.loads(parsed.state_patch)
            if not isinstance(state_patch, dict):
                raise ValueError("--state-patch must decode to a JSON object")
            produces_inputs = _parse_inputs(parsed.produces_inputs)
            from astrid.core.integrations.arnold.host.invocation import (
                build_human_resume_payload,
            )

            human_payload = build_human_resume_payload(
                action=parsed.decision,
                notes=parsed.notes,
                state_patch=state_patch,
                artifacts=parsed.produces_artifacts or None,
                inputs=produces_inputs or None,
            )
        _ack_active_arnold_stage(
            project_slug=parsed.project,
            stage_arg=parsed.stage,
            human_payload=human_payload,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"error: invalid Arnold ack payload: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: failed to acknowledge Arnold workflow: {exc}", file=sys.stderr)
        return 1

    print(f"acknowledged Arnold stage for project {parsed.project}")
    return 0


def cmd_status(args: list[str]) -> int:
    """Handle ``astrid status --engine arnold``.

    Reports the current state of an Arnold run including pipeline stage,
    suspension status, and feedback ledger.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="astrid status --engine arnold",
        description="Show status of an Arnold workflow run.",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project slug for this run.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output status as JSON.",
    )

    try:
        parsed = parser.parse_args(args)
    except SystemExit as exc:
        return int(exc.code or 2)

    try:
        text, lifecycle_json = _render_active_operation(parsed.project)
    except Exception as exc:
        print(f"error: failed to inspect Arnold workflow: {exc}", file=sys.stderr)
        return 1

    if parsed.json:
        print(json.dumps(lifecycle_json, sort_keys=True))
    else:
        print(text, end="")
    return 0


def cmd_abort(args: list[str]) -> int:
    """Handle ``astrid abort --engine arnold``.

    Aborts the active Arnold run and cleans up checkpoint state.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="astrid abort --engine arnold",
        description="Abort an active Arnold workflow run.",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project slug for this run.",
    )

    try:
        parsed = parser.parse_args(args)
    except SystemExit as exc:
        return int(exc.code or 2)

    # ── Placeholder: real abort implementation in later tasks ───────────
    print(f"[arnold abort] project={parsed.project}")
    return 0
