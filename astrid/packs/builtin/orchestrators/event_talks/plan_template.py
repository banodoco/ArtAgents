"""Event-talks plan-template for Sprint 5b — emits a plan v2 for the four-step pipeline."""

from __future__ import annotations

import shlex
import uuid
from pathlib import Path
from typing import Any

from astrid.core.orchestrator.plan_template import (
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
    source: str | Path | None = None,
    transcript: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a plan v2 dict for the event_talks pipeline.

    Steps:
      ados-sunday-template → search-transcript → find-holding-screens → render

    All steps use ``adapter: local`` — the pipeline is pure local ffmpeg/OCR/static writes.
    Cost is $0 for all steps (no LLM or RunPod calls).
    """
    run_root = Path(run_root)
    plan_id = f"event-talks-{run_id or uuid.uuid4().hex[:12]}"

    cmd_ados = _build_ados_cmd(python_exec, run_root)
    cmd_search = _build_search_cmd(python_exec, run_root, transcript)
    cmd_holding = _build_holding_cmd(python_exec, run_root, source)
    cmd_render = _build_render_cmd(python_exec, run_root)

    local_zero = cost_entry(0, source="local")
    return build_plan_template(
        plan_id=plan_id,
        steps=[
            build_leaf_template(
                "ados-sunday-template",
                command=cmd_ados,
                produces=[file_output("template_output", "ados-sunday-template.json")],
                cost=local_zero,
            ),
            build_leaf_template(
                "search-transcript",
                command=cmd_search,
                produces=[file_output("search_output", "search-results.txt")],
                cost=local_zero,
            ),
            build_leaf_template(
                "find-holding-screens",
                command=cmd_holding,
                produces=[file_output("holding_output", "holding-screens.json")],
                cost=local_zero,
            ),
            build_leaf_template(
                "render",
                command=cmd_render,
                produces=[file_output("render_output", "render-manifest.json")],
                cost=local_zero,
            ),
        ],
    )


def _build_ados_cmd(python_exec: str, run_root: Path) -> str:
    _ = run_root
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.builtin.orchestrators.event_talks.run "
        f"ados-sunday-template --out {shlex.quote('{produces_root}/ados-sunday-template.json')}"
    )


def _build_search_cmd(
    python_exec: str,
    run_root: Path,
    transcript: str | Path | None,
) -> str:
    _ = run_root
    transcript_flag = ""
    if transcript is not None:
        transcript_flag = f"--transcript {shlex.quote(str(Path(transcript).resolve()))}"
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.builtin.orchestrators.event_talks.run "
        f"search-transcript {transcript_flag} "
        f"--out {shlex.quote('{produces_root}/search-results.txt')}"
    )


def _build_holding_cmd(
    python_exec: str, run_root: Path, source: str | Path | None
) -> str:
    src = shlex.quote(str(Path(source).resolve())) if source else "''"
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.builtin.orchestrators.event_talks.run "
        f"find-holding-screens --video {src} "
        f"--out {shlex.quote('{produces_root}/holding-screens.json')}"
    )


def _build_render_cmd(python_exec: str, run_root: Path) -> str:
    manifest = run_root / "steps" / "ados-sunday-template" / "v1" / "produces" / "ados-sunday-template.json"
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.builtin.orchestrators.event_talks.run "
        f"render --manifest {shlex.quote(str(manifest))} "
        f"--out-dir {shlex.quote('{produces_root}')}"
    )


__all__ = ["build_plan_v2", "emit_plan_json"]
