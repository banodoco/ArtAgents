"""Invoke the rendering facade as a child of an existing project run.

The helper has two deliberately distinct paths:

* a bound call invokes the override-aware ``rendering.render`` executor and
  records its committed video/provenance pair under the parent run's task-step
  ``produces`` directory;
* a completely unbound call invokes :class:`RenderService` directly and does
  not create project ledger state.

Partial or invalid bindings never degrade to the unbound path.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from astrid.core.contracts.run_status import RunStatus
from astrid.core.execution.executor.registry import ExecutorRegistry, load_default_registry
from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.foundation.project_paths import (
    project_dir,
    resolve_projects_root,
    validate_project_slug,
    validate_run_id,
)
from astrid.core.io.cas import link_into_produces
from astrid.core.project.run import load_run_record, step_dir_for
from astrid.core.subprocess_env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV

from .service import RenderService


class AttachedRenderError(RuntimeError):
    """Raised when a render cannot be safely attached to its parent run."""


def invoke_attached_render(
    timeline_path: str | Path,
    assets_path: str | Path | None,
    output_path: str | Path,
    *,
    project_slug: str | None = None,
    parent_run_id: str | None = None,
    step_id: str | None = None,
    selector: str | None = None,
    engine: str | None = None,
    backend: str | None = None,
    backend_config: Mapping[str, Mapping[str, Any]] | None = None,
    theme_path: str | Path | None = None,
    keep_previous_renders: bool = False,
    root: str | Path | None = None,
    project_root: str | Path = REPO_ROOT,
    executor_registry: ExecutorRegistry | None = None,
    service: RenderService | None = None,
) -> Path:
    """Render to ``output_path``, attaching to a parent ledger when bound.

    ``project_slug`` and ``parent_run_id`` must be supplied together.  When
    omitted, an existing ``ASTRID_TASK_PROJECT``/``ASTRID_TASK_RUN_ID`` pair is
    used.  A bound call also requires a unique, single-segment ``step_id``.
    Only the absence of all binding information selects the public
    :class:`RenderService` path.

    The three required ``ASTRID_TASK_*`` variables are scoped to the child and
    restored byte-for-byte (including unset versus empty) after success or
    failure.
    """

    timeline = Path(timeline_path).expanduser().resolve()
    assets = None if assets_path is None else Path(assets_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    selected = _one_selector(selector=selector, engine=engine, backend=backend)
    bound_project, bound_run = _resolve_parent_binding(
        project_slug=project_slug,
        parent_run_id=parent_run_id,
        step_id=step_id,
    )

    if bound_project is None:
        public_service = service or RenderService(project_root=project_root)
        return public_service.render(
            timeline,
            assets,
            output,
            selector=selected,
            backend_config=backend_config,
        )

    if step_id is None or not str(step_id):
        raise AttachedRenderError("step_id is required for an attached render")
    child_step = validate_run_id(step_id)
    projects_root = resolve_projects_root(root)
    _validate_parent_run(bound_project, bound_run, root=projects_root)
    step_root = step_dir_for(
        bound_project,
        bound_run,
        child_step,
        step_version=1,
        root=projects_root,
    )
    if step_root.parent.exists():
        raise AttachedRenderError(
            f"attached render step {child_step!r} already exists in run {bound_run!r}"
        )

    inputs: dict[str, Any] = {
        "timeline": str(timeline),
        "output_name": output.name,
    }
    if assets is not None:
        inputs["assets_registry"] = str(assets)
    if selected is not None:
        inputs["engine"] = selected
    if backend_config is not None:
        inputs["backend_config"] = {
            str(key): dict(value) for key, value in backend_config.items()
        }
    if theme_path is not None:
        inputs["theme"] = str(Path(theme_path).expanduser().resolve())
    if keep_previous_renders:
        inputs["keep_previous_renders"] = True

    request = ExecutorRunRequest(
        executor_id="rendering.render",
        out=output.parent,
        project=bound_project,
        inputs=inputs,
        project_was_auto_resolved=True,
        invocation="attached-child",
    )
    registry = executor_registry or load_default_registry(project_root=project_root)
    with _scoped_task_env(
        project_slug=bound_project,
        parent_run_id=bound_run,
        step_id=child_step,
    ):
        result = run_executor(request, registry)

    if not result.ok:
        message = result.error.message if result.error is not None else "render executor failed"
        raise AttachedRenderError(message)

    video = _result_path(result.outputs.get("video"), fallback=output)
    provenance = _result_path(
        result.outputs.get("provenance"),
        fallback=Path(f"{video}.provenance.json"),
    )
    _require_output(video, label="video")
    _require_output(provenance, label="provenance sidecar")
    _record_step_outputs(step_root, video=video, provenance=provenance)

    return video


def _resolve_parent_binding(
    *,
    project_slug: str | None,
    parent_run_id: str | None,
    step_id: str | None,
) -> tuple[str | None, str | None]:
    explicit = (project_slug is not None, parent_run_id is not None)
    if explicit[0] != explicit[1]:
        raise AttachedRenderError(
            "project_slug and parent_run_id must be supplied together"
        )
    if all(explicit):
        return str(project_slug), str(parent_run_id)

    env_project = os.environ.get(TASK_PROJECT_ENV)
    env_run = os.environ.get(TASK_RUN_ID_ENV)
    if bool(env_project) != bool(env_run):
        raise AttachedRenderError(
            "partial ASTRID task binding: project and run id must both be set"
        )
    if env_project and env_run:
        return env_project, env_run
    if os.environ.get(TASK_STEP_ID_ENV) or step_id is not None:
        raise AttachedRenderError("step binding was supplied without a parent project/run")
    return None, None


def _validate_parent_run(
    project_slug: str,
    parent_run_id: str,
    *,
    root: Path,
) -> dict[str, Any]:
    project = validate_project_slug(project_slug)
    run_id = validate_run_id(parent_run_id)
    try:
        record = load_run_record(project, run_id, root=root)
    except Exception as exc:
        raise AttachedRenderError(
            f"invalid parent project/run ledger {project!r}/{run_id!r}: {exc}"
        ) from exc
    if record.get("project_slug") != project or record.get("run_id") != run_id:
        raise AttachedRenderError("parent run record identity does not match its ledger path")
    if record.get("status") != RunStatus.RUNNING.value:
        raise AttachedRenderError(
            f"parent run {run_id!r} is not running (status={record.get('status')!r})"
        )
    run_root = project_dir(project, root=root) / "runs" / run_id
    if not run_root.is_dir():
        raise AttachedRenderError(f"parent run directory is missing: {run_root}")
    return record


@contextmanager
def _scoped_task_env(
    *, project_slug: str, parent_run_id: str, step_id: str
) -> Iterator[None]:
    values = {
        TASK_PROJECT_ENV: project_slug,
        TASK_RUN_ID_ENV: parent_run_id,
        TASK_STEP_ID_ENV: step_id,
    }
    missing = object()
    previous: dict[str, object] = {
        name: os.environ[name] if name in os.environ else missing for name in values
    }
    os.environ.update(values)
    try:
        yield
    finally:
        for name, old_value in previous.items():
            if old_value is missing:
                os.environ.pop(name, None)
            else:
                os.environ[name] = str(old_value)


def _result_path(value: object, *, fallback: Path) -> Path:
    if isinstance(value, (str, Path)) and str(value):
        return Path(value).expanduser().resolve()
    return fallback.resolve()


def _require_output(path: Path, *, label: str) -> None:
    if not path.is_file():
        raise AttachedRenderError(f"attached render did not produce {label}: {path}")


def _record_step_outputs(step_root: Path, *, video: Path, provenance: Path) -> None:
    produces = step_root / "produces"
    produces.mkdir(parents=True, exist_ok=True)
    for source in (video, provenance):
        target = produces / source.name
        if source == target:
            continue
        link_into_produces(source, target)


def _one_selector(
    *, selector: str | None, engine: str | None, backend: str | None
) -> str | None:
    supplied = [value for value in (selector, engine, backend) if value is not None]
    if len(supplied) > 1:
        raise AttachedRenderError("selector, engine, and backend are mutually exclusive")
    return supplied[0] if supplied else None


__all__ = ["AttachedRenderError", "invoke_attached_render"]
