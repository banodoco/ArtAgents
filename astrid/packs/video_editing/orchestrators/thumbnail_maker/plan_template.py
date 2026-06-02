"""Thumbnail-maker plan-template for Sprint 5b — emits a plan v2 for five-step pipeline."""

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
    query: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a plan v2 dict for the thumbnail_maker pipeline.

    Steps:
      resolve-video → plan-evidence → discover-video-evidence →
      build-reference-pack → generate-thumbnails

    All steps use ``adapter: local``. Cost is $0 (local-only operations).
    """
    run_root = Path(run_root)
    plan_id = f"thumbnail-maker-{run_id or uuid.uuid4().hex[:12]}"

    query = query or "auto"
    cmd_resolve = _build_resolve_cmd(python_exec, run_root, source, query)
    cmd_plan = _build_plan_cmd(python_exec, run_root, query)
    cmd_discover = _build_discover_cmd(python_exec, run_root, query, source)
    cmd_build_ref = _build_build_ref_cmd(python_exec, run_root, query)
    cmd_generate = _build_generate_cmd(python_exec, run_root, query)

    local_zero = cost_entry(0, source="local")
    return build_plan_template(
        plan_id=plan_id,
        steps=[
            build_leaf_template(
                "resolve-video",
                command=cmd_resolve,
                produces=[file_output("resolve_output", "video-resolution.json")],
                cost=local_zero,
            ),
            build_leaf_template(
                "plan-evidence",
                command=cmd_plan,
                produces=[file_output("evidence_plan_output", "evidence/evidence-plan.json")],
                cost=local_zero,
            ),
            build_leaf_template(
                "discover-video-evidence",
                command=cmd_discover,
                produces=[file_output("candidates_output", "evidence/candidates.json")],
                cost=local_zero,
            ),
            build_leaf_template(
                "build-reference-pack",
                command=cmd_build_ref,
                produces=[file_output("reference_pack_output", "evidence/reference-pack.json")],
                cost=local_zero,
            ),
            build_leaf_template(
                "generate-thumbnails",
                command=cmd_generate,
                produces=[file_output("thumbnail_output", "thumbnail-manifest.json")],
                cost=local_zero,
            ),
        ],
    )


def _build_resolve_cmd(
    python_exec: str,
    run_root: Path,
    source: str | Path | None,
    query: str,
) -> str:
    _ = (run_root, query)
    src = shlex.quote(str(Path(source).resolve())) if source else "''"
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.thumbnail_maker.run "
        f"resolve-video --video {src} "
        f"--out {shlex.quote('{produces_root}/video-resolution.json')}"
    )


def _build_plan_cmd(python_exec: str, run_root: Path, query: str) -> str:
    _ = run_root
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.thumbnail_maker.run "
        f"plan-evidence --query {shlex.quote(query)} "
        f"--out {shlex.quote('{produces_root}/evidence/evidence-plan.json')}"
    )


def _build_discover_cmd(
    python_exec: str,
    run_root: Path,
    query: str,
    source: str | Path | None,
) -> str:
    evidence_plan = (
        run_root
        / "steps"
        / "plan-evidence"
        / "v1"
        / "produces"
        / "evidence"
        / "evidence-plan.json"
    )
    video_flag = ""
    if source is not None:
        video_flag = f"--video {shlex.quote(str(Path(source).resolve()))} "
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.thumbnail_maker.run "
        f"discover-video-evidence {video_flag}"
        f"--out {shlex.quote('{produces_root}/evidence/candidates.json')} "
        f"--query {shlex.quote(query)} "
        f"--previous-manifest {shlex.quote(str(evidence_plan))}"
    )


def _build_build_ref_cmd(python_exec: str, run_root: Path, query: str) -> str:
    candidates = (
        run_root
        / "steps"
        / "discover-video-evidence"
        / "v1"
        / "produces"
        / "evidence"
        / "candidates.json"
    )
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.thumbnail_maker.run "
        f"build-reference-pack "
        f"--out {shlex.quote('{produces_root}/evidence/reference-pack.json')} "
        f"--query {shlex.quote(query)} "
        f"--previous-manifest {shlex.quote(str(candidates))}"
    )


def _build_generate_cmd(python_exec: str, run_root: Path, query: str) -> str:
    ref_pack = (
        run_root
        / "steps"
        / "build-reference-pack"
        / "v1"
        / "produces"
        / "evidence"
        / "reference-pack.json"
    )
    return (
        f"{shlex.quote(str(python_exec))} -m astrid.packs.video_editing.orchestrators.thumbnail_maker.run "
        f"generate-thumbnails "
        f"--out {shlex.quote('{produces_root}/thumbnail-manifest.json')} "
        f"--query {shlex.quote(query)} "
        f"--previous-manifest {shlex.quote(str(ref_pack))}"
    )


__all__ = ["build_plan_v2", "emit_plan_json"]
