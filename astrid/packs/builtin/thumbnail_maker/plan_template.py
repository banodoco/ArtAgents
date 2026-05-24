"""Thumbnail-maker plan-template for Sprint 5b — emits a plan v2 for five-step pipeline."""

from __future__ import annotations

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

    cmd_resolve = _build_resolve_cmd(python_exec, run_root, source)
    cmd_plan = _build_plan_cmd(python_exec, run_root)
    cmd_discover = _build_discover_cmd(python_exec, run_root)
    cmd_build_ref = _build_build_ref_cmd(python_exec, run_root)
    cmd_generate = _build_generate_cmd(python_exec, run_root)

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
    python_exec: str, run_root: Path, source: str | Path | None
) -> str:
    out = run_root / "steps" / "resolve-video" / "v1" / "produces"
    src = str(Path(source).resolve()) if source else ""
    return (
        f"{python_exec} -m astrid.packs.builtin.thumbnail_maker.run "
        f"--video {src} --out {out} --query auto --dry-run"
    )


def _build_plan_cmd(python_exec: str, run_root: Path) -> str:
    out = run_root / "steps" / "plan-evidence" / "v1" / "produces"
    evidence = (
        run_root
        / "steps"
        / "resolve-video"
        / "v1"
        / "produces"
        / "video-resolution.json"
    )
    return (
        f"{python_exec} -m astrid.packs.builtin.thumbnail_maker.run "
        f"--video {evidence} --out {out} --query auto --dry-run"
    )


def _build_discover_cmd(python_exec: str, run_root: Path) -> str:
    out = run_root / "steps" / "discover-video-evidence" / "v1" / "produces"
    evidence_plan = (
        run_root
        / "steps"
        / "plan-evidence"
        / "v1"
        / "produces"
        / "evidence"
        / "evidence-plan.json"
    )
    return (
        f"{python_exec} -m astrid.packs.builtin.thumbnail_maker.run "
        f"--out {out} --query auto --dry-run "
        f"--previous-manifest {evidence_plan}"
    )


def _build_build_ref_cmd(python_exec: str, run_root: Path) -> str:
    out = run_root / "steps" / "build-reference-pack" / "v1" / "produces"
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
        f"{python_exec} -m astrid.packs.builtin.thumbnail_maker.run "
        f"--out {out} --query auto --dry-run "
        f"--previous-manifest {candidates}"
    )


def _build_generate_cmd(python_exec: str, run_root: Path) -> str:
    out = run_root / "steps" / "generate-thumbnails" / "v1" / "produces"
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
        f"{python_exec} -m astrid.packs.builtin.thumbnail_maker.run "
        f"--out {out} --query auto --dry-run "
        f"--previous-manifest {ref_pack}"
    )
