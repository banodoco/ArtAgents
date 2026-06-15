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

from astrid.core.integrations.arnold.session.authoring import (
    build_workflow as _build_workflow,
)
from astrid.core.integrations.arnold.session.authoring import (
    executor_step,
)

EVENT_TALKS_WORKFLOW_ID = "video_editing.event_talks"


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

    # ── Declare steps via the facade ───────────────────────────────────────
    steps = [
        executor_step(
            "ados-sunday-template",
            segment_id=EVENT_TALKS_WORKFLOW_ID,
            adapter="local",
            command=cmd_ados,
            produces={"template_output": "ados-sunday-template.json"},
            label="Ados Sunday Template",
        ),
        executor_step(
            "search-transcript",
            segment_id=EVENT_TALKS_WORKFLOW_ID,
            adapter="local",
            command=cmd_search,
            produces={"search_output": "search-results.txt"},
            label="Search Transcript",
        ),
        executor_step(
            "find-holding-screens",
            segment_id=EVENT_TALKS_WORKFLOW_ID,
            adapter="local",
            command=cmd_holding,
            produces={"holding_output": "holding-screens.json"},
            label="Find Holding Screens",
        ),
        executor_step(
            "render",
            segment_id=EVENT_TALKS_WORKFLOW_ID,
            adapter="local",
            command=cmd_render,
            produces={"render_output": "render-manifest.json"},
            label="Render",
        ),
    ]

    return _build_workflow(
        steps,
        segment_id=EVENT_TALKS_WORKFLOW_ID,
        project="default",
        run_root_path=run_root_path,
    )


__all__ = ["EVENT_TALKS_WORKFLOW_ID", "build_workflow"]
