"""Project-run and gate environment adapter helpers for the hype orchestrator.

Extracted from ``run.py`` as part of M4 giant-file decomposition (T66).
Kept separate from the main ``run.py`` facade so that project binding,
gate command interception, and environment variable management are
isolated from the manifest-facing ``main()`` entrypoint.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from astrid.core.project.run import (
    METADATA_KEY_TIMELINE_BINDING_MODE,
    METADATA_KEY_TIMELINE_EVENT_STREAM_ID,
    METADATA_KEY_TIMELINE_SLUG,
    TIMELINE_BINDING_MODE_MANAGED,
    ProjectRunError,
    bind_managed_timeline,
    # prepare_project_run – imported late via run.py facade for monkeypatch seam
    project_run_env,
    reject_project_with_out,
)


def _project_slug_for_gate(argv: list[str]) -> str | None:
    """Extract the ``--project`` value from *argv* for gate interception."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--project")
    parsed, _unknown = parser.parse_known_args(argv)
    return parsed.project


def _prepare_project_main(argv: list[str]) -> tuple[Any | None, list[str]]:
    """Prepare a project run context when ``--project`` is present.

    Returns ``(context, effective_argv)`` where *context* is the
    ``prepare_project_run`` result or ``None`` when no ``--project`` was
    requested.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--project")
    parser.add_argument("--out")
    parser.add_argument("--brief")
    parser.add_argument("--brief-slug", dest="brief_slug")
    parsed, _unknown = parser.parse_known_args(argv)
    if not parsed.project:
        return None, argv
    reject_project_with_out(parsed.project, parsed.out)

    # Derive managed timeline slug from brief (m3.5 managed binding).
    brief_slug = getattr(parsed, "brief_slug", None) or None
    if brief_slug is None:
        brief_path = getattr(parsed, "brief", None) or None
        if brief_path is not None:
            brief_stem = Path(brief_path).stem
            generic_brief_names = {"brief", "plan", "prompt"}
            brief_slug = brief_stem if brief_stem.lower() not in generic_brief_names else None
    # Fall back to a slug derived from the project name when no brief is available.
    if brief_slug is None:
        brief_slug = parsed.project

    # Establish managed timeline binding.
    try:
        timeline_ulid, timeline_slug, timeline_event_stream_id = bind_managed_timeline(
            parsed.project, brief_slug
        )
    except Exception as exc:
        raise ProjectRunError(
            f"failed to bind managed timeline for project {parsed.project!r}: {exc}"
        ) from exc

    managed_metadata: dict[str, Any] = {
        "entrypoint": "direct",
        METADATA_KEY_TIMELINE_SLUG: timeline_slug,
        METADATA_KEY_TIMELINE_EVENT_STREAM_ID: timeline_event_stream_id,
        METADATA_KEY_TIMELINE_BINDING_MODE: TIMELINE_BINDING_MODE_MANAGED,
    }
    # Late import through the run.py facade to preserve the monkeypatch
    # seam on ``astrid.packs.video_editing.orchestrators.hype.run.prepare_project_run``.
    from astrid.packs.video_editing.orchestrators.hype import run as _hype_run

    context = _hype_run.prepare_project_run(
        parsed.project,
        tool_id="video_editing.hype",
        kind="orchestrator",
        argv=["hype", *argv],
        metadata=managed_metadata,
        timeline_id=timeline_ulid,
    )
    return context, [*argv, "--out", str(context.run_root)]


def _set_project_env() -> dict[str, str | None]:
    """Capture and set project environment variables.

    Returns a prior-state dict suitable for ``_restore_project_env``.
    """
    prior = {key: os.environ.get(key) for key in project_run_env()}
    os.environ.update(project_run_env())
    return prior


def _restore_project_env(prior: dict[str, str | None]) -> None:
    """Restore environment variables to their *prior* state."""
    for key, value in prior.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _system_exit_code(exc: SystemExit) -> int:
    """Extract an integer exit code from a :exc:`SystemExit` exception."""
    if isinstance(exc.code, int):
        return exc.code
    return 1


def _project_hype_metadata(args: argparse.Namespace) -> dict[str, Any]:
    """Build hype-specific project metadata for run finalization."""
    return {
        "brief_out": str(getattr(args, "brief_out", "")),
        "brief_slug": str(getattr(args, "brief_slug", "")),
        "dry_run": bool(getattr(args, "dry_run", False)),
    }


def _project_hype_artifact_roots(args: argparse.Namespace) -> list[Path]:
    """Collect artifact root paths from *args* for run finalization."""
    roots: list[Path] = []
    brief_out = getattr(args, "brief_out", None)
    if brief_out is not None:
        roots.append(Path(brief_out))
    out = getattr(args, "out", None)
    if out is not None:
        roots.append(Path(out))
    return roots
