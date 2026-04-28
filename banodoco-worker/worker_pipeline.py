"""Banodoco pipeline wrapper for the worker (Sprint 7).

Translates a `banodoco_timeline_generate` task payload into a canonical
TimelineConfig by composing the existing tools/ modules:

  - tools/pool_merge.py  — merges brief sources into a pool
  - tools/arrange.py     — arranges the pool into a brief plan
  - tools/cut.py         — produces the timeline JSON
  - tools/timeline.py    — schema mirror, reused for validation

Validation: `banodoco_timeline_schema.validate_timeline(config, strict=True)`
(Sprint 5's strict-mode validator) — see the import below.

NOTE: Sprint 7 ships the wrapper API. The pipeline subprocess invocations
remain in their existing CLI form (`pipeline.py` orchestrates them); the
wrapper here is structured so a future iteration can substitute in-process
calls without changing the worker's call sites.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    config: Dict[str, Any]
    runs_dir: Path


class PipelineError(Exception):
    """Raised when the pipeline can't produce a valid TimelineConfig."""


def _tools_dir() -> Path:
    # Worker image lays the pipeline under /app/tools.
    explicit = os.getenv("BANODOCO_TOOLS_DIR")
    if explicit:
        return Path(explicit)
    return Path("/app/tools")


def run_pipeline(
    *,
    intent: str,
    brief_inputs: Dict[str, Any],
    theme_id: str,
    current_timeline: Optional[Dict[str, Any]] = None,
    work_dir: Optional[Path] = None,
) -> PipelineResult:
    """Invoke the Banodoco pipeline and return a parsed TimelineConfig.

    The pipeline writes `hype.timeline.json` into a runs/ subdir; we read
    that file back as the canonical config.
    """
    tools = _tools_dir()
    pipeline_py = tools / "pipeline.py"
    if not pipeline_py.exists():
        raise PipelineError(
            f"Pipeline entry not found at {pipeline_py}; check BANODOCO_TOOLS_DIR"
        )

    work_dir = work_dir or Path(tempfile.mkdtemp(prefix="banodoco-worker-"))
    work_dir.mkdir(parents=True, exist_ok=True)

    brief_path = work_dir / "brief.json"
    brief_payload = {
        "intent": intent,
        "theme_id": theme_id,
        "brief_inputs": brief_inputs,
        "current_timeline": current_timeline,
    }
    brief_path.write_text(json.dumps(brief_payload, indent=2))

    # Sprint 7 invokes the pipeline orchestrator with brief + theme;
    # `pipeline.py` writes outputs into work_dir/runs/<id>/.
    cmd = [
        sys.executable,
        str(pipeline_py),
        "--brief",
        str(brief_path),
        "--theme",
        theme_id,
        "--out",
        str(work_dir),
    ]
    logger.info("[BANODOCO_PIPELINE] Invoking %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("BANODOCO_PIPELINE_TIMEOUT_SEC", "1800")),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PipelineError(f"Pipeline invocation failed: {exc}") from exc

    if proc.returncode != 0:
        raise PipelineError(
            f"Pipeline exited with code {proc.returncode}: {proc.stderr[-2000:]}"
        )

    timeline_path = _find_timeline_output(work_dir)
    if timeline_path is None or not timeline_path.exists():
        raise PipelineError(
            f"Pipeline produced no hype.timeline.json under {work_dir}"
        )
    try:
        config = json.loads(timeline_path.read_text())
    except (OSError, ValueError) as exc:
        raise PipelineError(f"Failed to read TimelineConfig: {exc}") from exc

    if not isinstance(config, dict):
        raise PipelineError("Pipeline output is not a JSON object")

    return PipelineResult(config=config, runs_dir=work_dir)


def _find_timeline_output(work_dir: Path) -> Optional[Path]:
    # Pipeline writes to work_dir/runs/<id>/hype.timeline.json. Take the
    # newest one if multiple exist (multi-run case).
    runs_root = work_dir / "runs"
    if not runs_root.exists():
        # Some test fixtures place the file directly under work_dir.
        direct = work_dir / "hype.timeline.json"
        return direct if direct.exists() else None
    candidates = sorted(
        runs_root.rglob("hype.timeline.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def validate_timeline_strict(config: Dict[str, Any]) -> None:
    """Validate against `@banodoco/timeline-schema` strict mode (Sprint 5).

    Raises PipelineError on validation failure. Stays a thin wrapper so
    the worker logs include the validation diagnostics directly.
    """
    try:
        from banodoco_timeline_schema import validate_timeline  # type: ignore
    except ImportError as exc:
        raise PipelineError(
            "banodoco_timeline_schema is not installed in the worker image; "
            "rebuild banodoco-worker."
        ) from exc

    try:
        validate_timeline(config, strict=True)
    except Exception as exc:  # noqa: BLE001 — surface any validator type
        raise PipelineError(f"TimelineConfig failed strict validation: {exc}") from exc


__all__ = [
    "PipelineError",
    "PipelineResult",
    "run_pipeline",
    "validate_timeline_strict",
]
