"""Read-side rendering for session-succession Arnold runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.integrations.arnold.host.compat import read_resume_cursor

from .manifest import SegmentRecord
from .records import load_arnold_run_record, load_session_manifest, load_state


@dataclass(frozen=True)
class SessionRenderSnapshot:
    project_slug: str
    run_id: str
    run_root: Path
    run_record: Any
    manifest: Any
    state: dict[str, Any]
    pipeline_manifest: dict[str, Any]
    cursor: dict[str, Any] | None
    current_segment: SegmentRecord
    current_stage_id: str | None
    current_stage_label: str | None
    current_stage_metadata: dict[str, Any]
    segment_lineage: tuple[str, ...]


@dataclass(frozen=True)
class SessionRenderView:
    text: str
    lifecycle_json: dict[str, Any]


def load_session_snapshot(project_slug: str, run_root: Path) -> SessionRenderSnapshot:
    run_record = load_arnold_run_record(run_root)
    if run_record.mode != "session-succession":
        raise RuntimeError(
            f"run {run_root.name!r} is mode={run_record.mode!r}, not 'session-succession'"
        )

    manifest = load_session_manifest(run_root)
    if manifest.current_segment_id != run_record.current_segment:
        raise RuntimeError(
            "arnold_run.json current_segment does not match session-manifest.json"
        )
    if run_record.current_segment is None:
        raise RuntimeError("session run has no current segment")

    current_segment = _require_segment(manifest.segments, run_record.current_segment)
    pipeline_manifest = _load_pipeline_manifest(run_root)
    cursor = _load_cursor(run_root)
    current_stage_id = _current_stage_id(cursor, pipeline_manifest)
    current_stage_label, current_stage_metadata = _stage_details(pipeline_manifest, current_stage_id)
    return SessionRenderSnapshot(
        project_slug=project_slug,
        run_id=run_record.run_id,
        run_root=run_root,
        run_record=run_record,
        manifest=manifest,
        state=load_state(run_root),
        pipeline_manifest=pipeline_manifest,
        cursor=cursor,
        current_segment=current_segment,
        current_stage_id=current_stage_id,
        current_stage_label=current_stage_label,
        current_stage_metadata=current_stage_metadata,
        segment_lineage=_segment_lineage(manifest.segments, current_segment.segment_id),
    )


def render_session_snapshot(snapshot: SessionRenderSnapshot) -> SessionRenderView:
    derived_status = _derive_status(snapshot)
    action = "ack" if _is_ackable(snapshot) else None
    command = _ack_template(snapshot) if action == "ack" else None
    lifecycle_json = {
        "schema_version": 1,
        "project": snapshot.project_slug,
        "run_id": snapshot.run_id,
        "state": _lifecycle_state(snapshot, derived_status),
        "action": action,
        "command": command,
        "step": snapshot.current_stage_id,
        "blocked": False,
        "reason": None,
        "mode": "session-succession",
        "status": derived_status,
        "segment": snapshot.current_segment.segment_id,
        "lineage": list(snapshot.segment_lineage),
    }
    sections = [
        _header(snapshot),
        _summary(snapshot, derived_status),
        _ready_ack_section(command),
        _lineage_section(snapshot.segment_lineage),
        _state_section(snapshot.state),
    ]
    return SessionRenderView(
        text="\n".join(section for section in sections if section).rstrip() + "\n",
        lifecycle_json=lifecycle_json,
    )


def render_session_snapshot_text(snapshot: SessionRenderSnapshot) -> str:
    return render_session_snapshot(snapshot).text


def render_session_snapshot_json(snapshot: SessionRenderSnapshot) -> dict[str, Any]:
    return render_session_snapshot(snapshot).lifecycle_json


def _load_pipeline_manifest(run_root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((run_root / "pipeline.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"session run {run_root.name!r} is missing pipeline.json") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid pipeline.json for run {run_root.name!r}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"pipeline.json for run {run_root.name!r} is not a JSON object")
    return payload


def _load_cursor(run_root: Path) -> dict[str, Any] | None:
    try:
        cursor = read_resume_cursor(str(run_root))
    except FileNotFoundError:
        return None
    payload = getattr(cursor, "cursor", None)
    return dict(payload) if isinstance(payload, dict) else None


def _current_stage_id(cursor: dict[str, Any] | None, pipeline_manifest: dict[str, Any]) -> str | None:
    if isinstance(cursor, dict):
        stage = cursor.get("stage")
        if isinstance(stage, str) and stage:
            return stage
    entry_stage_id = pipeline_manifest.get("entry_stage_id")
    return entry_stage_id if isinstance(entry_stage_id, str) and entry_stage_id else None


def _stage_details(
    pipeline_manifest: dict[str, Any],
    stage_id: str | None,
) -> tuple[str | None, dict[str, Any]]:
    if stage_id is None:
        return None, {}
    for stage in pipeline_manifest.get("stages", ()):
        if not isinstance(stage, dict) or stage.get("stage_id") != stage_id:
            continue
        metadata = stage.get("metadata")
        return (
            str(stage.get("label") or stage_id),
            dict(metadata) if isinstance(metadata, dict) else {},
        )
    return stage_id, {}


def _require_segment(segments: tuple[SegmentRecord, ...], segment_id: str) -> SegmentRecord:
    for segment in segments:
        if segment.segment_id == segment_id:
            return segment
    raise RuntimeError(f"current segment {segment_id!r} is missing from session-manifest.json")


def _segment_lineage(segments: tuple[SegmentRecord, ...], segment_id: str) -> tuple[str, ...]:
    index = {segment.segment_id: segment for segment in segments}
    lineage: list[str] = []
    current_id: str | None = segment_id
    while current_id is not None:
        lineage.append(current_id)
        segment = index.get(current_id)
        if segment is None:
            break
        current_id = segment.parent_segment_id
    lineage.reverse()
    return tuple(lineage)


def _derive_status(snapshot: SessionRenderSnapshot) -> str:
    if snapshot.run_record.status in {"completed", "aborted"}:
        return snapshot.run_record.status
    if snapshot.current_stage_metadata.get("terminal") is True:
        return "completed"
    if _is_ackable(snapshot):
        return "suspended"
    return snapshot.run_record.status


def _is_ackable(snapshot: SessionRenderSnapshot) -> bool:
    if snapshot.current_stage_id is None:
        return False
    if snapshot.current_stage_metadata.get("terminal") is True:
        return False
    return snapshot.current_stage_metadata.get("manual") is True


def _lifecycle_state(snapshot: SessionRenderSnapshot, status: str) -> str:
    if status == "completed":
        return "done"
    if _is_ackable(snapshot):
        return "ready"
    return status


def _header(snapshot: SessionRenderSnapshot) -> str:
    label = snapshot.current_stage_label or snapshot.current_stage_id or "none"
    return (
        "Arnold session-succession\n"
        f"segment: {snapshot.current_segment.segment_id}\n"
        f"stage: {label} ({snapshot.current_stage_id or 'none'})"
    )


def _summary(snapshot: SessionRenderSnapshot, status: str) -> str:
    return (
        f"status: {status}\n"
        f"segment-status: {snapshot.current_segment.status}"
    )


def _ready_ack_section(command: str | None) -> str:
    if command is None:
        return "No acknowledgement pending."
    return f"ready for acknowledgement:\n{command}"


def _ack_template(snapshot: SessionRenderSnapshot) -> str:
    stage_id = snapshot.current_stage_id or "<stage>"
    return (
        "astrid ack --engine arnold "
        f"--project {snapshot.project_slug} "
        f"--stage {stage_id} "
        "--decision approve|reject "
        "--notes <notes>"
    )


def _lineage_section(lineage: tuple[str, ...]) -> str:
    if not lineage:
        return "successor lineage:\n  (none)"
    return "successor lineage:\n  " + " -> ".join(lineage)


def _state_section(state: dict[str, Any]) -> str:
    if not state:
        return "state keys:\n  (none)"
    return "state keys:\n  " + ", ".join(sorted(state))


__all__ = [
    "SessionRenderSnapshot",
    "SessionRenderView",
    "load_session_snapshot",
    "render_session_snapshot",
    "render_session_snapshot_json",
    "render_session_snapshot_text",
]
