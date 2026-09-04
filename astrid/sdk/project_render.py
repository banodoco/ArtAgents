"""Resolve, verify, materialize, and open a runtime render output."""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .contracts import DomainResult, ErrorObject
from .pagination import paged_rows
from .workspace_client import WorkspaceClientError

_SUCCESS_STATES = frozenset({"completed", "succeeded", "success"})
_VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".webm", ".mkv"})


def _failure(code: str, message: str, **details: Any) -> DomainResult[Any]:
    return DomainResult.failure(ErrorObject(code, message, details))


def _identifier(row: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def _state(row: Mapping[str, Any]) -> str:
    return _identifier(row, "status", "state").lower()


def _render_capability(row: Mapping[str, Any]) -> str:
    return _identifier(row, "capability_id", "capability")


def _output_name(spec: Any) -> str | None:
    if not isinstance(spec, Mapping):
        return None
    value = spec.get("output_name")
    if isinstance(value, str) and Path(value).suffix.lower() in _VIDEO_SUFFIXES:
        return Path(value).name
    for key in ("inputs", "params", "spec"):
        nested = _output_name(spec.get(key))
        if nested:
            return nested
    return None


def _default_cache_root() -> Path:
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Caches" / "Astrid" / "renders"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "astrid" / "renders"


def _materialize(data: bytes, *, digest: str, filename: str, cache_root: Path) -> Path:
    normalized = digest.removeprefix("sha256:").lower()
    destination = cache_root / normalized / Path(filename).name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == normalized:
        return destination
    handle, temporary = tempfile.mkstemp(prefix=".astrid-render-", dir=destination.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return destination


def open_project_render(
    client: Any,
    project_ref: str | None = None,
    *,
    run_id: str | None = None,
    cache_root: Path | None = None,
) -> DomainResult[Any]:
    """Open one exact render, or the current project's newest successful render."""
    if platform.system() != "Darwin":
        return _failure("unsupported_platform", "opening renders is currently supported on macOS only")
    try:
        if project_ref is None:
            current = client.current_project()
            project = current.get("project") if isinstance(current, Mapping) else None
        else:
            project = client.get_project(project_ref)
        if not isinstance(project, Mapping):
            if project_ref is None:
                return _failure(
                    "not_found",
                    "no current project is selected",
                    next_action="astrid projects select <project>",
                )
            return _failure("protocol_error", "runtime project response is malformed")
        project_id = _identifier(project, "project_id", "id")
        if not project_id:
            return _failure("protocol_error", "runtime project response has no project id")

        if run_id is not None:
            run = client.get_run(run_id)
            if not isinstance(run, Mapping):
                return _failure("protocol_error", "runtime run response is malformed", run_id=run_id)
            if _identifier(run, "project_id", "project") != project_id:
                return _failure("not_found", "render run is not owned by the selected project", run_id=run_id, project_id=project_id)
            candidates = [run]
        else:
            rows = paged_rows(client.list_project_runs, project_id, limit=50)
            if rows is None:
                return _failure("protocol_error", "runtime project run listing is malformed", project_id=project_id)
            candidates = [
                row for row in rows
                if isinstance(row, Mapping)
                and _render_capability(row) == "rendering.render"
                and _state(row) in _SUCCESS_STATES
            ]
            candidates.sort(
                key=lambda row: (str(row.get("created_at") or row.get("updated_at") or ""), _identifier(row, "run_id", "id")),
                reverse=True,
            )
        if not candidates:
            return _failure(
                "not_found",
                "project has no successful rendering.render run",
                project_id=project_id,
                next_action="astrid timelines render <timeline> --project <project>",
            )

        run = candidates[0]
        selected_run_id = _identifier(run, "run_id", "id")
        if not selected_run_id:
            return _failure("protocol_error", "runtime render run has no id")
        if _render_capability(run) not in {"", "rendering.render"} or _state(run) not in _SUCCESS_STATES:
            return _failure("validation_error", "selected run is not a successful rendering.render run", run_id=selected_run_id)
        if not isinstance(run.get("task_ids"), list):
            run = client.get_run(selected_run_id)
        task_ids = run.get("task_ids") if isinstance(run, Mapping) else None
        if not isinstance(task_ids, list) or not all(isinstance(item, str) and item for item in task_ids):
            return _failure("protocol_error", "runtime render run has no valid task ids", run_id=selected_run_id)

        render_tasks: list[Mapping[str, Any]] = []
        for task_id in task_ids:
            task = client.get_task(task_id)
            if (
                isinstance(task, Mapping)
                and _render_capability(task) == "rendering.render"
                and _state(task) in _SUCCESS_STATES
            ):
                render_tasks.append(task)
        if len(render_tasks) != 1:
            return _failure("validation_error", "render run must contain exactly one successful render task", run_id=selected_run_id, count=len(render_tasks))
        task = render_tasks[0]
        result = task.get("result")
        outputs = result.get("outputs") if isinstance(result, Mapping) else None
        if not isinstance(outputs, list):
            outputs = result.get("output_objects") if isinstance(result, Mapping) else None
        video_outputs = [item for item in (outputs or []) if isinstance(item, Mapping) and item.get("name") == "video"]
        if len(video_outputs) != 1:
            return _failure("validation_error", "render task must publish exactly one named video output", run_id=selected_run_id, count=len(video_outputs))
        output = video_outputs[0]
        digest = _identifier(output, "digest", "object_id")
        normalized_digest = digest.removeprefix("sha256:").lower()
        if len(normalized_digest) != 64 or any(char not in "0123456789abcdef" for char in normalized_digest.lower()):
            return _failure("protocol_error", "render output has no valid SHA-256 digest", run_id=selected_run_id)

        objects = paged_rows(client.list_project_objects, project_id, limit=50)
        if objects is None:
            return _failure("protocol_error", "runtime project media listing is malformed", project_id=project_id)
        media = next(
            (
                item for item in objects
                if isinstance(item, Mapping)
                and normalized_digest in {
                    _identifier(item, "digest").removeprefix("sha256:").lower(),
                    _identifier(item, "object_id").removeprefix("sha256:").lower(),
                }
            ),
            None,
        )
        if media is None:
            return _failure("not_found", "render output is not owned by the selected project", digest=digest, project_id=project_id)
        object_id = _identifier(media, "object_id") or digest
        response = client.get_object(object_id)
        data = response.get("data") if isinstance(response, Mapping) else None
        if not isinstance(data, bytes):
            return _failure("protocol_error", "runtime object download returned no bytes", object_id=object_id)
        actual_digest = hashlib.sha256(data).hexdigest()
        raw_size = output.get("size", media.get("size", len(data)))
        if isinstance(raw_size, bool) or not isinstance(raw_size, int) or raw_size < 0:
            return _failure("protocol_error", "render output has no valid byte size", object_id=object_id)
        expected_size = raw_size
        if actual_digest != normalized_digest or len(data) != expected_size:
            return _failure("integrity_error", "downloaded render does not match its runtime digest and size", object_id=object_id)

        media_filename = _identifier(media, "filename")
        if Path(media_filename).suffix.lower() not in _VIDEO_SUFFIXES:
            media_filename = ""
        filename = _output_name(task.get("spec")) or media_filename or "render.mp4"
        path = _materialize(data, digest=digest, filename=filename, cache_root=cache_root or _default_cache_root())
        subprocess.run(["open", str(path)], check=True)
        return DomainResult.success(
            {
                "project_id": project_id,
                "run_id": selected_run_id,
                "task_id": _identifier(task, "task_id", "id"),
                "object_id": object_id,
                "digest": "sha256:" + normalized_digest,
                "size": len(data),
                "local_path": str(path),
                "opened": True,
            }
        )
    except WorkspaceClientError as exc:
        return _failure(exc.code, exc.message, **dict(exc.details))
    except (OSError, subprocess.SubprocessError) as exc:
        return _failure("open_failed", "could not materialize or open the render", detail=str(exc))
