"""Event-talks workflow built via the Arnold authoring facade.

Provides ``build_workflow()`` which returns a compiled Arnold pipeline
for the four-step event_talks orchestrator:

    ados-sunday-template → search-transcript → find-holding-screens → render

This is the facade-backed equivalent of ``plan_template.build_plan_v2()``.
The parity test in ``tests/packs/event_talks/test_event_talks_parity.py``
compares the two lowering paths to verify they produce equal stage ids and
edge topology.
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

EVENT_TALKS_WORKFLOW_ID = "video_editing.event_talks"

# Ordered stage ids for the linear topology
_STAGE_IDS = (
    "ados-sunday-template",
    "search-transcript",
    "find-holding-screens",
    "render",
)

# Human-readable labels matching plan_template.py / shapes.py
_STAGE_LABELS = {
    "ados-sunday-template": "Ados Sunday Template",
    "search-transcript": "Search Transcript",
    "find-holding-screens": "Find Holding Screens",
    "render": "Render",
}

# Produces mappings (name -> output filename)
_PRODUCES = {
    "ados-sunday-template": {"template_output": "ados-sunday-template.json"},
    "search-transcript": {"search_output": "search-results.txt"},
    "find-holding-screens": {"holding_output": "holding-screens.json"},
    "render": {"render_output": "render-manifest.json"},
}


def build_workflow(
    *,
    python_exec: str = "python3",
    run_root: str | Path = "/tmp/event-talks-run",
    source: str | Path | None = None,
    transcript: str | Path | None = None,
    run_id: str | None = None,
) -> Any:
    """Build a compiled Arnold pipeline for the event_talks orchestrator.

    Parameters
    ----------
    python_exec:
        Python executable path for step commands.
    run_root:
        Run root directory for artifact placement.
    source:
        Path to the source video file (used by find-holding-screens).
    transcript:
        Path to a pre-existing transcript file (used by search-transcript).
    run_id:
        Stable run identifier (embedded in plan_id by plan_template).

    Returns
    -------
    Arnold pipeline object (from ``lowering.build_pipeline`` via compat).
    """
    import shlex

    run_root_path = Path(run_root)
    resolved_source = Path(source).resolve() if source else None
    resolved_transcript = Path(transcript).resolve() if transcript else None

    # ── Build step commands (mirror plan_template.py) ──────────────────────
    cmd_ados = (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.event_talks.run "
        f"ados-sunday-template --out {shlex.quote('{produces_root}/ados-sunday-template.json')}"
    )

    transcript_flag = ""
    if resolved_transcript is not None:
        transcript_flag = f"--transcript {shlex.quote(str(resolved_transcript))}"
    cmd_search = (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.event_talks.run "
        f"search-transcript {transcript_flag} "
        f"--out {shlex.quote('{produces_root}/search-results.txt')}"
    )

    src_flag = shlex.quote(str(resolved_source)) if resolved_source else "''"
    cmd_holding = (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.event_talks.run "
        f"find-holding-screens --video {src_flag} "
        f"--out {shlex.quote('{produces_root}/holding-screens.json')}"
    )

    manifest_ref = (
        "{step_dir}/../ados-sunday-template/v1/produces/ados-sunday-template.json"
    )
    cmd_render = (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.event_talks.run "
        f"render --manifest {shlex.quote(manifest_ref)} "
        f"--out-dir {shlex.quote('{produces_root}')}"
    )

    # ── Build stage commands keyed by stage id ──────────────────────────────
    _commands = {
        "ados-sunday-template": cmd_ados,
        "search-transcript": cmd_search,
        "find-holding-screens": cmd_holding,
        "render": cmd_render,
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
            segment_id=EVENT_TALKS_WORKFLOW_ID,
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


__all__ = ["EVENT_TALKS_WORKFLOW_ID", "build_workflow"]
