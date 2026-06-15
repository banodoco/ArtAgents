"""Transactional resume driver for Arnold session-succession runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from astrid.core._shared.jsonio import write_json_atomic
from astrid.core.integrations.arnold.host.compat import (
    persist_resume_cursor,
    read_resume_cursor,
)
from astrid.core.integrations.arnold.host.envelope import project_runtime_envelope
from astrid.core.events import EVENTS_FILENAME, read_events
from astrid.core.task.plan import TaskPlan, load_plan
from astrid.core.task.plan.verbs import apply_mutations

from .compiler import CompileResult, compile_plan_segment
from .events import make_segment_boundary_event
from .manifest import EventLineageHashes, PIPELINE_REF, SegmentRecord, SessionManifest
from .records import (
    ARNOLD_RUN_FILENAME,
    SESSION_SUCCESSION_WORKFLOW_ID,
    load_arnold_run_record,
    load_session_manifest,
    load_state,
    write_session_manifest,
)
from .resume import ResumeIntent, ResumeIntentKind, classify_resume_intent
from .state import StateRef, prefixed_hash, write_state_file


class SessionDriverError(RuntimeError):
    """Raised when the session-succession driver cannot safely transition."""


@dataclass(frozen=True)
class SessionResumeResult:
    """Result of resuming an Arnold session run."""

    intent: ResumeIntent
    run_id: str
    from_segment_id: str | None
    to_segment_id: str | None
    writer_epoch: int | None
    boundary_hash: str | None
    manifest_hash: str | None
    checkpoint: Any | None


WriterContextFactory = Callable[..., Any]


def resume_session_run(
    project_slug: str,
    *,
    run_id: str | None = None,
    root: str | Path | None = None,
    plan_path: str | Path | None = None,
    human_input: dict[str, Any] | None = None,
    resume_cursor: Any | None = None,
    driver: Any | None = None,
    writer_context_factory: WriterContextFactory | None = None,
) -> SessionResumeResult:
    """Resume a session run, freezing a successor segment on plan mutation.

    Pure data resumes delegate to the normal Arnold ``StepwiseDriver.resume``.
    Plan mutations pass through the canonical Astrid writer lease and append
    exactly one ``segment_boundary`` event before updating rebuildable
    projections and launching the successor pipeline.
    """

    run_root = _resolve_run_root(project_slug, run_id=run_id, root=root)
    run_record = load_arnold_run_record(run_root)
    if run_record.mode != "session-succession":
        raise SessionDriverError("resume_session_run requires a session-succession run")

    events = read_events(run_root / EVENTS_FILENAME)
    base_plan = load_plan(plan_path or run_root / "plan.json")
    effective_plan = apply_mutations(base_plan, events)
    effective_plan_hash = _hash_plan(effective_plan)
    intent = classify_resume_intent(
        run_root,
        human_input=human_input,
        effective_plan_hash=effective_plan_hash,
    )

    driver = driver if driver is not None else _get_host_driver()
    if intent.kind is ResumeIntentKind.PURE_DATA:
        envelope = project_runtime_envelope(
            project_slug,
            workflow_id=SESSION_SUCCESSION_WORKFLOW_ID,
            run_id=run_record.run_id,
            root=root,
        )
        cursor = resume_cursor if resume_cursor is not None else getattr(envelope, "resume_cursor", None)
        resumed = driver.resume(envelope, cursor)
        checkpoint = driver.checkpoint(resumed)
        _persist_session_cursor(run_root, checkpoint=checkpoint, envelope=resumed, fallback=cursor)
        _write_session_run_status(
            run_root,
            run_record=run_record,
            stage_id=_current_cursor_stage(run_root),
        )
        return SessionResumeResult(
            intent=intent,
            run_id=run_record.run_id,
            from_segment_id=run_record.current_segment,
            to_segment_id=run_record.current_segment,
            writer_epoch=None,
            boundary_hash=None,
            manifest_hash=None,
            checkpoint=checkpoint,
        )

    factory = writer_context_factory or _default_writer_context_factory
    with factory(project_slug, root=root) as writer:
        writer_run_root = Path(writer.run_dir)
        if writer_run_root.resolve() != run_root.resolve():
            raise SessionDriverError(
                f"writer is bound to {writer_run_root.name!r}, not {run_root.name!r}"
            )
        writer_epoch = int(writer.expected_writer_epoch)
        current_run_record = load_arnold_run_record(run_root)
        manifest = _validated_manifest(run_root, current_run_record)
        current_segment = _current_segment(manifest, current_run_record.current_segment)

        persisted_cursor = _persist_and_read_back_cursor(
            run_root,
            cursor=resume_cursor,
            run_id=current_run_record.run_id,
        )
        state = load_state(run_root)
        next_segment_id = _next_segment_id(manifest)
        compile_result = compile_plan_segment(
            effective_plan,
            project=project_slug,
            run_root=run_root,
            state=state,
            segment_id=next_segment_id,
        )
        pipeline_hash = prefixed_hash(compile_result.pipeline_manifest)
        candidate_manifest = _candidate_manifest(
            manifest,
            run_root=run_root,
            from_segment=current_segment,
            next_segment_id=next_segment_id,
            next_plan_hash=compile_result.plan_hash,
            state=state,
            pipeline_hash=pipeline_hash,
            cursor_ref=_cursor_ref(persisted_cursor),
        )
        candidate_manifest_hash = candidate_manifest.compute_projection_hash()

        boundary = make_segment_boundary_event(
            from_segment_id=current_segment.segment_id,
            to_segment_id=next_segment_id,
            previous_plan_hash=current_segment.plan_hash,
            next_plan_hash=compile_result.plan_hash,
            cursor_ref=_cursor_ref(persisted_cursor),
            manifest_hash=candidate_manifest_hash,
            state_hash=StateRef.from_state(state).state_hash,
        )
        stored_boundary = writer.append(boundary)

        committed_manifest = _with_boundary_hash(
            candidate_manifest,
            segment_id=next_segment_id,
            boundary_hash=str(stored_boundary["hash"]),
        )
        _commit_successor_projection(
            run_root,
            run_record=current_run_record,
            manifest=committed_manifest,
            compile_result=compile_result,
            state=state,
            next_segment_id=next_segment_id,
        )

    envelope = project_runtime_envelope(
        project_slug,
        workflow_id=SESSION_SUCCESSION_WORKFLOW_ID,
        run_id=run_record.run_id,
        root=root,
        resume_cursor=persisted_cursor,
    )
    driver.advance(envelope)
    checkpoint = driver.checkpoint(envelope)
    _persist_session_cursor(
        run_root,
        checkpoint=checkpoint,
        envelope=envelope,
        fallback=persisted_cursor,
    )
    _write_session_run_status(
        run_root,
        run_record=load_arnold_run_record(run_root),
        stage_id=_current_cursor_stage(run_root),
        infer_from_stage=False,
    )
    return SessionResumeResult(
        intent=intent,
        run_id=run_record.run_id,
        from_segment_id=current_segment.segment_id,
        to_segment_id=next_segment_id,
        writer_epoch=writer_epoch,
        boundary_hash=str(stored_boundary["hash"]),
        manifest_hash=committed_manifest.compute_projection_hash(),
        checkpoint=checkpoint,
    )


def _default_writer_context_factory(project_slug: str, *, root: str | Path | None = None) -> Any:
    from astrid.core.session.writer import writer_context_for_project

    return writer_context_for_project(project_slug, root=root)


def _get_host_driver() -> Any:
    from astrid.core.integrations.arnold.host.driver import get_driver

    return get_driver()


def _resolve_run_root(
    project_slug: str,
    *,
    run_id: str | None,
    root: str | Path | None,
) -> Path:
    from astrid.core.integrations.arnold.host.envelope import resolve_run_root

    return resolve_run_root(project_slug, run_id=run_id, root=root)


def _hash_plan(plan: TaskPlan) -> str:
    from astrid.core.events import canonical_event_json
    import hashlib

    payload = canonical_event_json(plan.to_dict()).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _validated_manifest(run_root: Path, run_record: Any) -> SessionManifest:
    manifest = load_session_manifest(run_root)
    if manifest.run_id and manifest.run_id != run_record.run_id:
        raise SessionDriverError(
            f"manifest run_id {manifest.run_id!r} does not match {run_record.run_id!r}"
        )
    if manifest.current_segment_id != run_record.current_segment:
        raise SessionDriverError(
            "arnold_run.json current_segment does not match session-manifest.json"
        )
    return manifest


def _current_segment(manifest: SessionManifest, segment_id: str | None) -> SegmentRecord:
    if segment_id is None:
        raise SessionDriverError("session run has no current segment")
    for segment in manifest.segments:
        if segment.segment_id == segment_id:
            return segment
    raise SessionDriverError(f"current segment {segment_id!r} is missing from manifest")


def _persist_and_read_back_cursor(run_root: Path, *, cursor: Any, run_id: str) -> Any:
    from astrid.core.integrations.arnold.host.compat import (
        persist_resume_cursor,
        read_resume_cursor,
    )

    if cursor is None:
        raise SessionDriverError("mutation resume requires a concrete resume cursor")
    persist_resume_cursor(str(run_root), cursor)
    persisted = read_resume_cursor(str(run_root))
    if persisted is None:
        raise SessionDriverError("persisted resume cursor could not be read back")
    _validate_cursor(persisted, run_id=run_id)
    return persisted


def _validate_cursor(cursor: Any, *, run_id: str) -> None:
    cursor_run_id = getattr(cursor, "run_id", None)
    if cursor_run_id is not None and cursor_run_id != run_id:
        raise SessionDriverError(
            f"resume cursor run_id {cursor_run_id!r} does not match {run_id!r}"
        )
    payload = getattr(cursor, "cursor", None)
    if not isinstance(payload, dict):
        raise SessionDriverError("resume cursor must expose a cursor payload dict")
    stage = payload.get("stage")
    if not isinstance(stage, str) or not stage:
        raise SessionDriverError("resume cursor payload must include non-empty stage")


def _cursor_ref(cursor: Any) -> str:
    payload = getattr(cursor, "cursor", None)
    if isinstance(payload, dict):
        stage = payload.get("stage")
        if isinstance(stage, str) and stage:
            return f"resume-cursor:{stage}"
    return "resume-cursor"


def _next_segment_id(manifest: SessionManifest) -> str:
    used = {segment.segment_id for segment in manifest.segments}
    index = len(used) + 1
    while True:
        candidate = f"seg-{index:03d}"
        if candidate not in used:
            return candidate
        index += 1


def _candidate_manifest(
    manifest: SessionManifest,
    *,
    run_root: Path,
    from_segment: SegmentRecord,
    next_segment_id: str,
    next_plan_hash: str,
    state: dict[str, Any],
    pipeline_hash: str,
    cursor_ref: str,
) -> SessionManifest:
    next_segment = SegmentRecord(
        segment_id=next_segment_id,
        parent_segment_id=from_segment.segment_id,
        plan_hash=next_plan_hash,
        state=StateRef.from_state(state),
        status="prepared",
        pipeline_ref=PIPELINE_REF,
        pipeline_hash=pipeline_hash,
        cursor_ref=cursor_ref,
        event_lineage=EventLineageHashes(
            segment_start_hash=from_segment.event_lineage.segment_boundary_hash
            or from_segment.event_lineage.segment_start_hash,
        ),
    )
    segments = tuple(
        segment if segment.segment_id != from_segment.segment_id else _freeze_segment(segment)
        for segment in manifest.segments
    ) + (next_segment,)
    return SessionManifest(
        run_id=manifest.run_id or run_root.name,
        artifact_root=str(run_root),
        current_segment_id=next_segment_id,
        segments=segments,
    )


def _freeze_segment(segment: SegmentRecord) -> SegmentRecord:
    return SegmentRecord(
        segment_id=segment.segment_id,
        plan_hash=segment.plan_hash,
        state=segment.state,
        parent_segment_id=segment.parent_segment_id,
        status="frozen",
        pipeline_ref=segment.pipeline_ref,
        pipeline_hash=segment.pipeline_hash,
        cursor_ref=segment.cursor_ref,
        artifacts=segment.artifacts,
        event_lineage=segment.event_lineage,
        frozen_at=segment.frozen_at,
        launched_at=segment.launched_at,
    )


def _with_boundary_hash(
    manifest: SessionManifest,
    *,
    segment_id: str,
    boundary_hash: str,
) -> SessionManifest:
    segments: list[SegmentRecord] = []
    for segment in manifest.segments:
        if segment.segment_id != segment_id:
            segments.append(segment)
            continue
        segments.append(
            SegmentRecord(
                segment_id=segment.segment_id,
                plan_hash=segment.plan_hash,
                state=segment.state,
                parent_segment_id=segment.parent_segment_id,
                status="running",
                pipeline_ref=segment.pipeline_ref,
                pipeline_hash=segment.pipeline_hash,
                cursor_ref=segment.cursor_ref,
                artifacts=segment.artifacts,
                event_lineage=EventLineageHashes(
                    segment_start_hash=segment.event_lineage.segment_start_hash,
                    segment_boundary_hash=boundary_hash,
                ),
                frozen_at=segment.frozen_at,
                launched_at=segment.launched_at,
            )
        )
    return SessionManifest(
        run_id=manifest.run_id,
        artifact_root=manifest.artifact_root,
        current_segment_id=manifest.current_segment_id,
        segments=tuple(segments),
    )


def _commit_successor_projection(
    run_root: Path,
    *,
    run_record: Any,
    manifest: SessionManifest,
    compile_result: CompileResult,
    state: dict[str, Any],
    next_segment_id: str,
) -> None:
    write_state_file(run_root, state)
    write_json_atomic(run_root / PIPELINE_REF, compile_result.pipeline_manifest)
    write_session_manifest(run_root, manifest)
    raw_record = _load_run_payload(run_root)
    write_json_atomic(
        run_root / ARNOLD_RUN_FILENAME,
        {
            **raw_record,
            "engine": run_record.engine,
            "workflow_id": run_record.workflow_id,
            "mode": run_record.mode,
            "run_id": run_record.run_id,
            "status": "running",
            "current_segment": next_segment_id,
            "plan_hash": compile_result.plan_hash,
        },
    )


def _load_run_payload(run_root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((run_root / ARNOLD_RUN_FILENAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _persist_session_cursor(
    run_root: Path,
    *,
    checkpoint: Any | None,
    envelope: Any | None,
    fallback: Any | None,
) -> None:
    cursor = None
    if checkpoint is not None:
        cursor = getattr(checkpoint, "cursor", None)
    if cursor is None and envelope is not None:
        cursor = getattr(envelope, "resume_cursor", None)
    if cursor is None:
        cursor = fallback
    if cursor is not None:
        persist_resume_cursor(str(run_root), cursor)


def _current_cursor_stage(run_root: Path) -> str | None:
    try:
        cursor = read_resume_cursor(str(run_root))
    except FileNotFoundError:
        return None
    payload = getattr(cursor, "cursor", None)
    if not isinstance(payload, dict):
        return None
    stage = payload.get("stage")
    return stage if isinstance(stage, str) and stage else None


def _write_session_run_status(
    run_root: Path,
    *,
    run_record: Any,
    stage_id: str | None,
    infer_from_stage: bool = True,
) -> None:
    raw_record = _load_run_payload(run_root)
    status = run_record.status
    if infer_from_stage:
        status = _status_for_stage(run_root, stage_id, fallback=run_record.status)
    write_json_atomic(
        run_root / ARNOLD_RUN_FILENAME,
        {
            **raw_record,
            "engine": run_record.engine,
            "workflow_id": run_record.workflow_id,
            "mode": run_record.mode,
            "run_id": run_record.run_id,
            "status": status,
            "current_segment": run_record.current_segment,
            "plan_hash": run_record.plan_hash,
        },
    )


def _status_for_stage(run_root: Path, stage_id: str | None, *, fallback: str) -> str:
    if stage_id is None:
        return fallback
    try:
        payload = json.loads((run_root / PIPELINE_REF).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback
    if not isinstance(payload, dict):
        return fallback
    for stage in payload.get("stages", ()):
        if not isinstance(stage, dict) or stage.get("stage_id") != stage_id:
            continue
        metadata = stage.get("metadata")
        if not isinstance(metadata, dict):
            return fallback
        if metadata.get("terminal") is True:
            return "completed"
        if metadata.get("manual") is True:
            return "suspended"
        return "running"
    return fallback


__all__ = [
    "SessionDriverError",
    "SessionResumeResult",
    "resume_session_run",
]
