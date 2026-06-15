"""CLI helpers for starting Arnold session-succession runs."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import write_json_atomic
from astrid.core.foundation.project_paths import (
    project_dir,
    validate_project_slug,
    validate_run_id,
)
from astrid.core.integrations.arnold.host.compat import compat, persist_resume_cursor
from astrid.core.integrations.arnold.host.envelope import HOST_PLUGIN_ID
from astrid.core.project import require_project
from astrid.core.project.current_run import clear_current_run, read_current_run, write_current_run
from astrid.core.project.project import ProjectError
from astrid.core.session.binding import SessionBindingError, resolve_current_session
from astrid.core.session.lease import write_lease_init
from astrid.core.events import ZERO_HASH, append_event_locked, make_plan_initialized_event
from astrid.core.task.plan import load_plan
from astrid.core.util.time import utc_now_iso

from .compiler import compile_plan_segment
from .manifest import EventLineageHashes, SegmentRecord, SessionManifest, write_manifest_file
from .records import ARNOLD_RUN_FILENAME, SESSION_SUCCESSION_WORKFLOW_ID
from .state import StateRef, prefixed_hash, write_state_file


def start_session_run(
    *,
    project_slug: str,
    from_plan: str,
    initial_state: dict[str, Any],
    input_values: dict[str, str],
    requested_run_id: str | None,
    json_mode: bool,
    argv: list[str],
) -> int:
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

    source_plan_path = _resolve_plan_path(slug, from_plan)
    plan = load_plan(source_plan_path)

    run_id = validate_run_id(requested_run_id) if requested_run_id else _generate_run_id()
    proj_root = project_dir(slug)
    run_root = proj_root / "runs" / run_id
    if run_root.exists():
        raise RuntimeError(f"run {run_id!r} already exists")

    compile_result = compile_plan_segment(
        plan,
        project=slug,
        run_root=run_root,
        state=initial_state,
        segment_id="seg-001",
    )
    plan_hash = compile_result.plan_hash
    pipeline_hash = prefixed_hash(compile_result.pipeline_manifest)
    segment_start_hash: str | None = None

    created_run_dir = False
    pointer_written = False
    try:
        run_root.mkdir(parents=True)
        created_run_dir = True
        write_json_atomic(run_root / "plan.json", plan.to_dict())
        write_state_file(run_root, initial_state)
        write_json_atomic(run_root / "pipeline.json", compile_result.pipeline_manifest)

        session_id = _resolve_bound_session_id(slug)
        write_lease_init(run_root, session_id=session_id, plan_hash=plan_hash)

        started = append_event_locked(
            run_root,
            make_plan_initialized_event(run_id, plan.to_dict(), plan_hash),
            expected_writer_epoch=0,
            expected_prev_hash=ZERO_HASH,
        )
        segment_start_hash = str(started["hash"])

        write_manifest_file(
            run_root,
            SessionManifest(
                run_id=run_id,
                artifact_root=str(run_root),
                current_segment_id="seg-001",
                segments=(
                    SegmentRecord(
                        segment_id="seg-001",
                        plan_hash=plan_hash,
                        state=StateRef.from_state(initial_state),
                        status="running",
                        pipeline_ref="pipeline.json",
                        pipeline_hash=pipeline_hash,
                        cursor_ref=_cursor_ref(compile_result.entry_stage_id),
                        event_lineage=EventLineageHashes(
                            segment_start_hash=segment_start_hash
                        ),
                    ),
                ),
            ),
        )

        write_json_atomic(
            run_root / ARNOLD_RUN_FILENAME,
            {
                "engine": "arnold",
                "workflow_id": SESSION_SUCCESSION_WORKFLOW_ID,
                "mode": "session-succession",
                "run_id": run_id,
                "status": _initial_run_status(compile_result.pipeline_manifest),
                "current_segment": "seg-001",
                "argv": ["start", *argv],
                "created_at": utc_now_iso(),
                "inputs": input_values,
                "state": initial_state,
                "plan_hash": plan_hash,
                "from_plan": str(source_plan_path),
            },
        )

        persist_resume_cursor(
            str(run_root),
            compat.ResumeCursorRef(
                plugin_id=HOST_PLUGIN_ID,
                run_id=run_id,
                cursor={"stage": compile_result.entry_stage_id},
            ),
        )

        write_current_run(slug, run_id)
        pointer_written = True
    except Exception:
        if pointer_written:
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
                    "workflow_id": SESSION_SUCCESSION_WORKFLOW_ID,
                    "mode": "session-succession",
                    "plan_hash": plan_hash,
                    "next_command": f"astrid next --engine arnold --project {slug}",
                },
                sort_keys=True,
            )
        )
    else:
        print("started session-succession")
        print("  engine:    arnold")
        print(f"  project:   {slug}")
        print(f"  run-id:    {run_id}")
        print(f"  plan:      {source_plan_path}")
        print(f"  plan-hash: {plan_hash}")
    return 0


def _resolve_plan_path(project_slug: str, plan_ref: str) -> Path:
    explicit = Path(plan_ref).expanduser()
    for candidate in (explicit, project_dir(project_slug) / "runs" / plan_ref):
        plan_path = candidate / "plan.json" if candidate.is_dir() else candidate
        if plan_path.is_file():
            return plan_path.resolve()
    raise RuntimeError(
        f"session start could not resolve plan reference {plan_ref!r}; "
        "expected a plan.json path, a run directory containing plan.json, "
        "or a run id under the target project"
    )


def _resolve_bound_session_id(project_slug: str) -> str:
    try:
        bound = resolve_current_session(slug=project_slug)
    except SessionBindingError:
        return "legacy"
    if bound is None:
        return "legacy"
    return bound.id


def _generate_run_id() -> str:
    return "arnold-" + uuid.uuid4().hex[:12]


def _cursor_ref(stage_id: str) -> str:
    return f"resume-cursor:{stage_id}"


def _initial_run_status(pipeline_manifest: dict[str, Any]) -> str:
    entry_stage_id = pipeline_manifest.get("entry_stage_id")
    if not isinstance(entry_stage_id, str) or not entry_stage_id:
        return "prepared"
    for stage in pipeline_manifest.get("stages", ()):
        if not isinstance(stage, dict):
            continue
        if stage.get("stage_id") != entry_stage_id:
            continue
        metadata = stage.get("metadata")
        if isinstance(metadata, dict) and metadata.get("manual") is True:
            return "suspended"
        if metadata and isinstance(metadata, dict) and metadata.get("terminal") is True:
            return "completed"
        return "running"
    return "running"


__all__ = ["start_session_run"]
