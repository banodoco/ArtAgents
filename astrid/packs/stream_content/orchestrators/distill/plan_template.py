"""Plan-v2 template for stream_content.distill."""

from __future__ import annotations

import shlex
import uuid
from pathlib import Path
from typing import Any

from astrid.core.execution.orchestrator.plan_template import (
    build_leaf_template,
    build_plan_template,
    cost_entry,
    emit_plan_json,
    file_output,
)


def build_plan_v2(
    *,
    python_exec: str,
    run_root: str | Path,
    video: str | Path,
    transcript: str | Path | None = None,
    brief: str | Path | None = None,
    include_scenes: bool = True,
    run_id: str | None = None,
) -> dict[str, Any]:
    run_root = Path(run_root)
    plan_id = f"stream-content-{run_id or uuid.uuid4().hex[:12]}"
    local_zero = cost_entry(0, source="local")
    steps: list[dict[str, Any]] = []

    if transcript is None:
        steps.append(
            build_leaf_template(
                "transcribe",
                command=_cmd_transcribe(python_exec, video),
                produces=[file_output("transcript", "transcript.json")],
                cost=local_zero,
            )
        )
        transcript_ref = run_root / "steps" / "transcribe" / "v1" / "produces" / "transcript.json"
    else:
        transcript_ref = Path(transcript).resolve()

    scenes_ref: Path | None = None
    if include_scenes:
        steps.append(
            build_leaf_template(
                "scenes",
                command=_cmd_scenes(python_exec, video),
                produces=[file_output("scenes", "scenes.json")],
                cost=local_zero,
            )
        )
        scenes_ref = run_root / "steps" / "scenes" / "v1" / "produces" / "scenes.json"

    steps.extend(
        [
            build_leaf_template(
                "segment-map",
                command=_cmd_segment_map(python_exec, video, transcript_ref, scenes_ref),
                produces=[file_output("segment_map", "segment_map.json")],
                cost=local_zero,
            ),
            build_leaf_template(
                "extract-segments",
                command=_cmd_extract_segments(python_exec, video, run_root),
                produces=[file_output("segments_manifest", "segments/segments.json")],
                cost=local_zero,
            ),
            build_leaf_template(
                "clip-candidates",
                command=_cmd_clip_candidates(python_exec, transcript_ref, run_root, brief),
                produces=[file_output("candidates", "candidates.json")],
                cost=local_zero,
            ),
            build_leaf_template(
                "review",
                command=_cmd_review(python_exec, video, run_root),
                produces=[file_output("review", "review.html")],
                cost=local_zero,
            ),
        ]
    )
    return build_plan_template(plan_id=plan_id, steps=steps)


def _cmd_transcribe(python_exec: str, video: str | Path) -> str:
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.editorial.executors.transcribe.run "
        f"--audio {shlex.quote(str(Path(video).resolve()))} --out {shlex.quote('{produces_root}')}"
    )


def _cmd_scenes(python_exec: str, video: str | Path) -> str:
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.editorial.executors.scenes.run "
        f"--video {shlex.quote(str(Path(video).resolve()))} --out {shlex.quote('{produces_root}/scenes.json')}"
    )


def _cmd_segment_map(python_exec: str, video: str | Path, transcript: Path, scenes: Path | None) -> str:
    scenes_arg = f" --scenes {shlex.quote(str(scenes))}" if scenes is not None else ""
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.stream_content.executors.segment_map.run "
        f"--video {shlex.quote(str(Path(video).resolve()))} "
        f"--transcript {shlex.quote(str(transcript))}{scenes_arg} "
        f"--out {shlex.quote('{produces_root}/segment_map.json')}"
    )


def _cmd_extract_segments(python_exec: str, video: str | Path, run_root: Path) -> str:
    segment_map = run_root / "steps" / "segment-map" / "v1" / "produces" / "segment_map.json"
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.stream_content.orchestrators.distill.run "
        f"extract-segments --video {shlex.quote(str(Path(video).resolve()))} "
        f"--segment-map {shlex.quote(str(segment_map))} "
        f"--out-dir {shlex.quote('{produces_root}/segments')} "
        f"--manifest {shlex.quote('{produces_root}/segments/segments.json')}"
    )


def _cmd_clip_candidates(python_exec: str, transcript: Path, run_root: Path, brief: str | Path | None) -> str:
    segment_map = run_root / "steps" / "segment-map" / "v1" / "produces" / "segment_map.json"
    brief_arg = f" --brief {shlex.quote(str(Path(brief).resolve()))}" if brief is not None else ""
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.stream_content.executors.clip_candidates.run "
        f"--transcript {shlex.quote(str(transcript))} "
        f"--segment-map {shlex.quote(str(segment_map))}{brief_arg} "
        f"--out {shlex.quote('{produces_root}/candidates.json')}"
    )


def _cmd_review(python_exec: str, video: str | Path, run_root: Path) -> str:
    segment_map = run_root / "steps" / "segment-map" / "v1" / "produces" / "segment_map.json"
    candidates = run_root / "steps" / "clip-candidates" / "v1" / "produces" / "candidates.json"
    segments_manifest = run_root / "steps" / "extract-segments" / "v1" / "produces" / "segments" / "segments.json"
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.stream_content.orchestrators.distill.run "
        f"review --video {shlex.quote(str(Path(video).resolve()))} "
        f"--segment-map {shlex.quote(str(segment_map))} "
        f"--candidates {shlex.quote(str(candidates))} "
        f"--segments-manifest {shlex.quote(str(segments_manifest))} "
        f"--out {shlex.quote('{produces_root}/review.html')}"
    )


__all__ = ["build_plan_v2", "emit_plan_json"]

