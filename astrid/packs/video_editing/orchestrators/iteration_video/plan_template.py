"""Iteration-video task plan-template using the canonical orchestrator builders."""

from __future__ import annotations

import uuid
import shlex
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
    target_run_id: str,
    repo_root: str | Path | None = None,
    run_id: str | None = None,
    renderer: str = "remotion",
) -> dict[str, Any]:
    """Build a task plan for prepare → assemble → render iteration-video work."""

    run_root = Path(run_root)
    plan_id = f"iteration-video-{run_id or uuid.uuid4().hex[:12]}"
    cmd_prepare = _build_prepare_cmd(python_exec, run_root, target_run_id, repo_root)
    cmd_assemble = _build_assemble_cmd(python_exec, run_root, repo_root)
    cmd_render = _build_render_cmd(python_exec, run_root, renderer=renderer)
    local_zero = cost_entry(0, source="local")

    return build_plan_template(
        plan_id=plan_id,
        steps=[
            build_leaf_template(
                "prepare",
                command=cmd_prepare,
                produces=[
                    file_output("manifest", "iteration.manifest.json"),
                    file_output("quality", "iteration.quality.json"),
                ],
                cost=local_zero,
            ),
            build_leaf_template(
                "assemble",
                command=cmd_assemble,
                produces=[
                    file_output("timeline", "iteration.timeline.json"),
                    file_output("manifest", "iteration.manifest.json"),
                    file_output("report", "iteration.report.html"),
                    file_output("quality", "iteration.quality.json"),
                    file_output("hype_timeline", "hype.timeline.json"),
                    file_output("hype_assets", "hype.assets.json"),
                ],
                cost=local_zero,
            ),
            build_leaf_template(
                "render",
                command=cmd_render,
                produces=[
                    file_output("video", "iteration.mp4"),
                    file_output("provenance", "iteration.mp4.provenance.json"),
                ],
                cost=local_zero,
            ),
        ],
    )


def _build_prepare_cmd(
    python_exec: str,
    run_root: Path,
    target_run_id: str,
    repo_root: str | Path | None,
) -> str:
    out = run_root / "steps" / "prepare" / "v1" / "produces"
    repo_flag = f" --repo-root {Path(repo_root).resolve()}" if repo_root else ""
    return (
        f"{python_exec} -m astrid.packs.iteration.executors.prepare.run "
        f"--target-run-id {target_run_id} --out {out}{repo_flag}"
    )


def _build_assemble_cmd(
    python_exec: str,
    run_root: Path,
    repo_root: str | Path | None,
) -> str:
    out = run_root / "steps" / "assemble" / "v1" / "produces"
    prepare_dir = run_root / "steps" / "prepare" / "v1" / "produces"
    repo_flag = f" --repo-root {Path(repo_root).resolve()}" if repo_root else ""
    return (
        f"{python_exec} -m astrid.packs.iteration.executors.assemble.run "
        f"--prepare-dir {prepare_dir} --out {out}{repo_flag}"
    )


def _build_render_cmd(
    python_exec: str,
    run_root: Path,
    *,
    renderer: str = "remotion",
) -> str:
    timeline = run_root / "steps" / "assemble" / "v1" / "produces" / "hype.timeline.json"
    assets = run_root / "steps" / "assemble" / "v1" / "produces" / "hype.assets.json"
    parts = [
        shlex.quote(str(python_exec)),
        "-m",
        "astrid",
        "executors",
        "run",
        "rendering.render",
        "--out",
        "{produces_root}",
    ]
    for name, value in (
        ("timeline", timeline),
        ("assets_registry", assets),
        ("output_name", "iteration.mp4"),
        ("engine", renderer),
    ):
        parts.extend(["--input", shlex.quote(f"{name}={value}")])
    return " ".join(parts)


__all__ = ["build_plan_v2", "emit_plan_json"]
