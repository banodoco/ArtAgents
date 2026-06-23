"""Thumbnail-maker workflow built via the Arnold authoring facade.

Provides ``build_workflow()`` which returns a compiled Arnold pipeline
for the five-step thumbnail_maker orchestrator:

    resolve-video → plan-evidence → discover-video-evidence →
    build-reference-pack → generate-thumbnails

This is the facade-backed equivalent of ``plan_template.build_plan_v2()``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.core.integrations.arnold.authoring import (
    edge,
    executor_step,
    halt,
    pipeline,
)

THUMBNAIL_MAKER_WORKFLOW_ID = "video_editing.thumbnail_maker"

# Ordered stage ids for the linear topology
_STAGE_IDS = (
    "resolve-video",
    "plan-evidence",
    "discover-video-evidence",
    "build-reference-pack",
    "generate-thumbnails",
)

# Human-readable labels matching plan_template.py
_STAGE_LABELS = {
    "resolve-video": "Resolve Video",
    "plan-evidence": "Plan Evidence",
    "discover-video-evidence": "Discover Video Evidence",
    "build-reference-pack": "Build Reference Pack",
    "generate-thumbnails": "Generate Thumbnails",
}

# Produces mappings (name -> output filename)
_PRODUCES = {
    "resolve-video": {"resolve_output": "video-resolution.json"},
    "plan-evidence": {"evidence_plan_output": "evidence/evidence-plan.json"},
    "discover-video-evidence": {"candidates_output": "evidence/candidates.json"},
    "build-reference-pack": {"reference_pack_output": "evidence/reference-pack.json"},
    "generate-thumbnails": {"thumbnail_output": "thumbnail-manifest.json"},
}


def build_workflow(
    *,
    python_exec: str = "python3",
    run_root: str | Path = "/tmp/thumbnail-maker-run",
    source: str | Path | None = None,
    query: str | None = None,
    run_id: str | None = None,
) -> Any:
    """Build a compiled Arnold pipeline for the thumbnail_maker orchestrator.

    Parameters
    ----------
    python_exec:
        Python executable path for step commands.
    run_root:
        Run root directory for artifact placement.
    source:
        Path to the source video file (used by resolve-video and
        discover-video-evidence).
    query:
        Thumbnail direction or search query (defaults to ``"auto"``).
    run_id:
        Stable run identifier (embedded in plan_id by plan_template).

    Returns
    -------
    Arnold pipeline object (from ``lowering.build_pipeline`` via compat).
    """
    import shlex

    run_root_path = Path(run_root)
    resolved_source = Path(source).resolve() if source else None
    effective_query = query or "auto"

    # ── Build step commands (mirror plan_template.py) ──────────────────────
    src_flag = shlex.quote(str(resolved_source)) if resolved_source else "''"
    cmd_resolve = (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.thumbnail_maker.run "
        f"resolve-video --video {src_flag} "
        f"--out {shlex.quote('{produces_root}/video-resolution.json')}"
    )

    cmd_plan = (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.thumbnail_maker.run "
        f"plan-evidence --query {shlex.quote(effective_query)} "
        f"--out {shlex.quote('{produces_root}/evidence/evidence-plan.json')}"
    )

    # Relative to this step's {step_dir}, the plan-evidence produces live at
    # ../plan-evidence/v1/produces/ — stable under both task-gate and Arnold.
    evidence_plan_ref = (
        "{step_dir}/../plan-evidence/v1/produces/evidence/evidence-plan.json"
    )
    video_flag = ""
    if resolved_source is not None:
        video_flag = f"--video {shlex.quote(str(resolved_source))} "
    cmd_discover = (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.thumbnail_maker.run "
        f"discover-video-evidence {video_flag}"
        f"--out {shlex.quote('{produces_root}/evidence/candidates.json')} "
        f"--query {shlex.quote(effective_query)} "
        f"--previous-manifest {shlex.quote(evidence_plan_ref)}"
    )

    candidates_ref = (
        "{step_dir}/../discover-video-evidence/v1/produces/evidence/candidates.json"
    )
    cmd_build_ref = (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.thumbnail_maker.run "
        f"build-reference-pack "
        f"--out {shlex.quote('{produces_root}/evidence/reference-pack.json')} "
        f"--query {shlex.quote(effective_query)} "
        f"--previous-manifest {shlex.quote(candidates_ref)}"
    )

    ref_pack_ref = (
        "{step_dir}/../build-reference-pack/v1/produces/evidence/reference-pack.json"
    )
    cmd_generate = (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.thumbnail_maker.run "
        f"generate-thumbnails "
        f"--out {shlex.quote('{produces_root}/thumbnail-manifest.json')} "
        f"--query {shlex.quote(effective_query)} "
        f"--previous-manifest {shlex.quote(ref_pack_ref)}"
    )

    # ── Build stage commands keyed by stage id ──────────────────────────────
    _commands = {
        "resolve-video": cmd_resolve,
        "plan-evidence": cmd_plan,
        "discover-video-evidence": cmd_discover,
        "build-reference-pack": cmd_build_ref,
        "generate-thumbnails": cmd_generate,
    }

    # ── Declare steps via the real facade (returns StageSpec) ──────────────
    stages: list[Any] = []
    for sid in _STAGE_IDS:
        produces = _PRODUCES[sid]
        produces_meta = [
            {"name": name, "path": path} for name, path in produces.items()
        ]
        stage_spec = executor_step(
            stage_id=sid,
            label=_STAGE_LABELS[sid],
            executor_id="task.local",
            segment_id=THUMBNAIL_MAKER_WORKFLOW_ID,
            project="default",
            run_root=run_root_path,
            command=_commands[sid],
            outputs=produces,
            metadata={
                "produces": produces_meta,
            },
        )
        stages.append(stage_spec)

    # ── Stitch linear edges between consecutive stages ────────────────────
    edges: list[Any] = []
    for i in range(len(stages) - 1):
        edges.append(
            edge(
                source=stages[i].stage_id,
                target=stages[i + 1].stage_id,
                label="next",
            )
        )

    # ── Append halt stage ─────────────────────────────────────────────────
    halt_stage = halt()
    if stages:
        edges.append(
            edge(
                source=stages[-1].stage_id,
                target=halt_stage.stage_id,
                label="next",
            )
        )
    all_stages = tuple(stages) + (halt_stage,)

    # ── Compile into an Arnold Pipeline ────────────────────────────────────
    return pipeline(
        entry_stage_id=stages[0].stage_id if stages else "halt",
        stages=all_stages,
        edges=tuple(edges),
    )


__all__ = ["THUMBNAIL_MAKER_WORKFLOW_ID", "build_workflow"]
