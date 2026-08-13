"""Project-owned artifact path enforcement.

Runs and sources have always been rooted in a project. Timelines and
experiments use the same invariant: managed work may consume them only from
the owning project's tree.
"""

from __future__ import annotations

from pathlib import Path

from astrid.core.contracts.errors import AstridError
from astrid.core.foundation import project_paths


class ProjectOwnershipError(AstridError):
    """Raised when a managed artifact is outside its owning project."""


def require_project_owned_artifact(
    project_slug: str,
    artifact_type: str,
    value: str | Path,
    *,
    root: str | Path | None = None,
) -> Path:
    """Return a resolved artifact path after enforcing project ownership.

    Timeline artifacts may be either canonical containers under ``timelines``
    or derived timeline files under project ``runs``. Experiment definitions
    must live under ``experiments`` and experiment run roots under ``runs``.
    """

    project_root = project_paths.project_dir(project_slug, root=root).resolve()
    if not (project_root / "project.json").is_file():
        raise ProjectOwnershipError(
            f"project not found: {project_slug}",
            recovery_command=f"python3 -m astrid projects create {project_slug}",
        )

    normalized_type = artifact_type.strip().lower().replace("-", "_")
    if normalized_type == "experiment" or normalized_type.startswith("experiment/"):
        owned_root = project_paths.experiments_dir(project_slug, root=root).resolve()
    elif normalized_type in {"project_runs", "experiment_runs"}:
        owned_root = project_paths.runs_dir(project_slug, root=root).resolve()
    elif normalized_type == "timeline" or normalized_type.startswith("timeline/"):
        owned_root = project_root
    else:
        return Path(value).expanduser().resolve()

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    candidate = candidate.resolve(strict=False)
    try:
        candidate.relative_to(owned_root)
    except ValueError as exc:
        destination = owned_root if owned_root != project_root else project_root
        raise ProjectOwnershipError(
            f"{artifact_type} input is not owned by project {project_slug!r}: {candidate}",
            recovery_command=(
                f"import or copy it under {destination} and run with "
                f"--project {project_slug}"
            ),
            state_snapshot={
                "artifact_type": artifact_type,
                "path": str(candidate),
                "project": project_slug,
                "owned_root": str(owned_root),
            },
        ) from exc
    return candidate


__all__ = ["ProjectOwnershipError", "require_project_owned_artifact"]
