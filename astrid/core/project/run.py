"""Project run lifecycle helpers."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core.contracts.errors import AstridError
from astrid.core.contracts.run_status import RunStatus
from astrid.core.env_vars import (
    ASTRID_PROJECT_SLUG,
    ASTRID_PROJECTS_ROOT,
    ASTRID_SESSION_ID,
)
from astrid.core.foundation import project_paths as paths
from astrid.core.subprocess_env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV
from astrid.core.threads.ids import generate_run_id
from astrid.core.util.time import utc_now_seconds

from .project import require_project
from .schema import build_run_record, validate_run_record

PROJECT_RUN_ENV = "ASTRID_PROJECT_RUN"
# Metadata keys for managed timeline binding (m3.5).
# These are stored in run.metadata and allow the run record to carry
# timeline identity without overloading run.timeline_id (which remains ULID-only).
METADATA_KEY_TIMELINE_SLUG = "timeline_slug"
METADATA_KEY_TIMELINE_EVENT_STREAM_ID = "timeline_event_stream_id"
METADATA_KEY_TIMELINE_BINDING_MODE = "timeline_binding_mode"
# Valid timeline binding modes.
TIMELINE_BINDING_MODE_MANAGED = "managed"
TIMELINE_BINDING_MODE_UNMANAGED = "unmanaged"
TIMELINE_BINDING_MODES = {TIMELINE_BINDING_MODE_MANAGED, TIMELINE_BINDING_MODE_UNMANAGED}
# Normalized (dashes → underscores, no leading dashes) exact-match set
# used by _is_sensitive_key after key normalization.  Keep in sync with
# the substrings below.
_SENSITIVE_NORMALIZED_NAMES: set[str] = {
    "access_key",
    "api_key",
    "apikey",
    "auth",
    "bearer",
    "credential",
    "env_file",
    "fal_key",
    "key",
    "password",
    "secret",
    "token",
}
_SENSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "access_key",
    "api_key",
    "apikey",
    "auth",
    "bearer",
    "credential",
    "fal_key",
    "password",
    "secret",
    "token",
)
HYPE_ARTIFACTS = {
    "timeline": ("hype.timeline.json", "timeline.json"),
    "assets": ("hype.assets.json", "assets.json"),
    "metadata": ("hype.metadata.json", "metadata.json"),
}


class ProjectRunError(AstridError):
    """Raised when a project run cannot be prepared or finalized."""


def step_dir_for(
    slug: str,
    run_id: str,
    plan_step_id: str,
    *,
    step_version: int = 1,
    root: str | Path | None = None,
) -> Path:
    """Return the legacy step directory for a task-run step.

    Retained for attached-child callers (``rendering.attached`` and task-bound
    ``prepare_project_run``) that bind a run record under the parent task
    run's step directory. The kernel no longer executes task plans; the path
    layout is preserved only for artifact placement.
    """

    paths.validate_project_slug(slug)
    paths.validate_run_id(run_id)
    paths.validate_run_id(plan_step_id)
    if not isinstance(step_version, int) or isinstance(step_version, bool) or step_version < 1:
        raise ProjectRunError("step_dir_for: step_version must be an int >= 1")
    return paths.project_dir(slug, root=root) / "runs" / run_id / "steps" / plan_step_id / f"v{step_version}"


@dataclass(frozen=True)
class ProjectRunContext:
    project_slug: str
    run_id: str
    run_root: Path
    run_json_path: Path
    record: dict[str, Any]
    root: Path


def reject_project_with_out(project: str | None, out: str | Path | None) -> None:
    if project and out not in (None, ""):
        raise ProjectRunError("--project cannot be combined with --out; project runs own their output directory")


def project_run_env(
    project_slug: str | None = None, *, root: str | Path | None = None
) -> dict[str, str]:
    env = {PROJECT_RUN_ENV: "1"}
    if project_slug:
        env[ASTRID_PROJECT_SLUG] = project_slug
        from astrid.core.element.catalog import resolve_active_theme
        from astrid.core.theme import ACTIVE_THEME_ENV

        theme_dir = resolve_active_theme(project_slug=project_slug, root=root)
        if theme_dir is not None:
            env[ACTIVE_THEME_ENV] = str(theme_dir)
    return env


def _project_subprocess_env(request: Any) -> dict[str, str]:
    """Return the project-scoped subprocess environment for *request*.

    *request* must have a ``.project`` attribute (``str | None``) and may
    carry an explicit ``.projects_root`` (the SDK/client bound root). When
    set, ``ASTRID_PROJECTS_ROOT`` is pinned to it so a child executor
    process composes its kernel application against the same bound root the
    parent used for run placement.
    """
    env = (
        project_run_env(request.project, root=getattr(request, "projects_root", None))
        if request.project
        else {}
    )
    projects_root = getattr(request, "projects_root", None)
    if projects_root:
        env[ASTRID_PROJECTS_ROOT] = str(Path(projects_root).expanduser().resolve())
    return env


def record_path_value(
    value: str | Path,
    project_slug: str,
    *,
    root: str | Path | None = None,
) -> str:
    """Serialize a record path, using project-relative values when possible."""

    project_root = paths.project_dir(project_slug, root=root).resolve()
    raw_path = Path(value).expanduser()
    absolute = raw_path.resolve() if raw_path.is_absolute() else (Path.cwd() / raw_path).resolve()
    try:
        relative = absolute.relative_to(project_root)
    except ValueError:
        return str(absolute)
    return relative.as_posix() or "."


def resolve_record_path(
    value: str | Path,
    project_slug: str,
    *,
    root: str | Path | None = None,
) -> Path:
    """Resolve a run-record path against a project root when it is relative."""

    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (paths.project_dir(project_slug, root=root) / path).resolve()


def prepare_project_run(
    project_slug: str,
    *,
    tool_id: str | None = None,
    kind: str | None = None,
    argv: Iterable[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
    root: str | Path | None = None,
    run_id: str | None = None,
    timeline_id: str | None = None,
    requires_timeline: bool | None = None,
    ledger_out: str | Path | None = None,
    record_out: str | Path | None = None,
    session_id: str | None = None,
    auto_bound: bool | None = None,
    invocation: str = "cli",
) -> ProjectRunContext:
    """Prepare a project-scoped run directory and run record.

    ``requires_timeline`` controls whether a live project timeline must exist:

    * ``True`` — resolve (and demand) exactly one live timeline (legacy default).
    * ``False`` — skip timeline resolution entirely; the run carries no
      ``timeline_id``. Use for stateless executors (image/video generation,
      understanding, rendering, foley, lora search) that never touch a timeline.
    * ``None`` — default to ``True`` (legacy timeline-required behavior). The
      executor runner resolves an executor's ``metadata.requires_timeline``
      opt-out from the ``ExecutorDefinition`` it already holds and passes the
      concrete boolean, so the project tier never reaches up into the executor
      registry to do this.

    ``session_id`` resolves in order: explicit parameter, then
    ``ASTRID_SESSION_ID`` from the environment, then no value. This function
    does not inspect project binding files directly.
    """
    require_project(project_slug, root=root)
    projects_root = paths.resolve_projects_root(root)
    prepared_at = utc_now_seconds()
    base_metadata = dict(metadata or {})
    base_metadata.setdefault("pid", os.getpid())
    base_metadata.setdefault("prepared_at", prepared_at)
    base_metadata.setdefault("process_platform", sys.platform)
    if requires_timeline is None:
        # Preserve the legacy default while allowing callers that own an
        # executor definition to opt out explicitly.
        requires_timeline = True
    if not requires_timeline:
        # A timeline-unbound run never inherits, records, or contributes to a
        # timeline even when it is attached to a timeline-bound task run.
        timeline_id = None
    effective_session_id = session_id or os.environ.get(ASTRID_SESSION_ID)
    if auto_bound is not None:
        base_metadata.pop("project_was_auto_resolved", None)
    parent_run_id = os.environ.get(TASK_RUN_ID_ENV)
    if parent_run_id:
        task_project = os.environ.get(TASK_PROJECT_ENV)
        if task_project != project_slug:
            raise ProjectRunError(f"task run is bound to project {task_project!r}, refusing to prepare run for {project_slug!r}")
        step_id = os.environ.get(TASK_STEP_ID_ENV)
        if not step_id:
            raise ProjectRunError("ASTRID_TASK_STEP_ID must be set when ASTRID_TASK_RUN_ID is set")
        if timeline_id is None and requires_timeline:
            timeline_id = _timeline_id_from_parent_run(
                project_slug,
                parent_run_id,
                root=projects_root,
            )
        run_root = step_dir_for(project_slug, parent_run_id, step_id, step_version=1, root=projects_root)
        run_root.mkdir(parents=True, exist_ok=True)
        now = prepared_at
        run_metadata = dict(base_metadata)
        run_metadata.update({"attached_to_task_run": True, "task_step_id": step_id})
        record: dict[str, Any] = {
            "artifacts": {},
            "auto_bound": bool(auto_bound) if auto_bound is not None else False,
            "created_at": now,
            "invocation": "task",
            "metadata": run_metadata,
            "out": record_path_value(run_root, project_slug, root=projects_root),
            "project_slug": project_slug,
            "run_id": parent_run_id,
            "schema_version": 1,
            "status": RunStatus.RUNNING.value,
            "updated_at": now,
        }
        if effective_session_id is not None:
            record["session_id"] = effective_session_id
        if tool_id is not None:
            record["tool_id"] = tool_id
        if kind is not None:
            record["kind"] = kind
        if argv is not None:
            record["argv"] = redact_cli_args(list(argv))
        if timeline_id is not None and requires_timeline:
            record["timeline_id"] = timeline_id
            # Contract exemption: task-attached child runs contribute through
            # their parent task run, so the parent is recorded at prepare time.
            _record_contributing_run(project_slug, timeline_id, parent_run_id, root=projects_root)
        return ProjectRunContext(
            project_slug=project_slug,
            run_id=parent_run_id,
            run_root=run_root,
            run_json_path=run_root / "run.json",
            record=record,
            root=projects_root,
        )
    if timeline_id is None and requires_timeline:
        timeline_id, _timeline_slug = resolve_required_project_timeline(project_slug, root=projects_root)
    effective_run_id = paths.validate_run_id(run_id or generate_run_id())
    run_root = (
        Path(ledger_out).expanduser().resolve()
        if ledger_out not in (None, "")
        else paths.run_dir(project_slug, effective_run_id, root=projects_root)
    )
    if run_root.exists() and any(run_root.iterdir()):
        raise ProjectRunError(f"project run directory already exists: {run_root}")
    run_root.mkdir(parents=True, exist_ok=True)
    record = build_run_record(
        project_slug,
        effective_run_id,
        tool_id=tool_id,
        kind=kind,
        status=RunStatus.RUNNING,
        out=record_path_value(
            record_out if record_out not in (None, "") else run_root,
            project_slug,
            root=projects_root,
        ),
        argv=redact_cli_args(list(argv or ())),
        metadata=dict(base_metadata),
        session_id=effective_session_id,
        auto_bound=auto_bound,
        invocation=invocation,
        timeline_id=timeline_id,
    )
    run_json_path = run_root / "run.json"
    write_json_atomic(run_json_path, record)
    return ProjectRunContext(
        project_slug=project_slug,
        run_id=effective_run_id,
        run_root=run_root,
        run_json_path=run_json_path,
        record=record,
        root=projects_root,
    )


def resolve_required_project_timeline(
    project_slug: str,
    *,
    root: str | Path | None = None,
) -> tuple[str, str]:
    """Resolve exactly one non-tombstoned timeline for a project run.

    The project default wins when it points at a live timeline. Without a live
    default, a single live timeline is accepted. Zero or multiple live
    timelines fail with explicit recovery guidance.
    """
    from astrid.core.timeline.crud import list_timelines
    from astrid.core.timeline.defaults import read_project_default
    from astrid.core.timeline.paths import find_timeline_slug_for_ulid

    default_ulid = read_project_default(project_slug, root=root)
    if default_ulid is not None:
        default_slug = find_timeline_slug_for_ulid(project_slug, default_ulid, root=root)
        if default_slug is not None:
            return default_ulid, default_slug

    live = list_timelines(project_slug, root=root)
    if len(live) == 1:
        return live[0].ulid, live[0].slug
    if not live:
        raise ProjectRunError(
            f"project {project_slug!r} has no live timelines; "
            f"recovery: python3 -m astrid attach {project_slug} && "
            "python3 -m astrid timelines create main --default"
        )
    choices = ", ".join(row.slug for row in live)
    raise ProjectRunError(
        f"project {project_slug!r} has no default timeline and {len(live)} live timelines "
        f"({choices}); recovery: python3 -m astrid attach {project_slug} && "
        "python3 -m astrid timelines set-default <slug>"
    )


def _timeline_id_from_parent_run(
    project_slug: str,
    parent_run_id: str,
    *,
    root: str | Path | None = None,
) -> str:
    run_path = paths.run_json_path(project_slug, parent_run_id, root=root)
    if run_path.is_file():
        try:
            parent = validate_run_record(read_json(run_path))
        except Exception:
            parent = None
        if isinstance(parent, dict):
            timeline_id = parent.get("timeline_id")
            if isinstance(timeline_id, str) and timeline_id:
                return timeline_id
    raise ProjectRunError(
        f"task run {parent_run_id!r} is missing run.json.timeline_id; "
        "restart the task run after creating or selecting a timeline"
    )


def _record_contributing_run(
    project_slug: str,
    timeline_ulid: str,
    run_id: str,
    *,
    root: str | Path | None = None,
) -> None:
    from astrid.core.timeline.crud import record_contributing_run

    record_contributing_run(project_slug, timeline_ulid, run_id, root=root)


def finalize_project_run(
    context: ProjectRunContext,
    *,
    status: RunStatus | str,
    returncode: int | None = None,
    error: BaseException | str | None = None,
    metadata: Mapping[str, Any] | None = None,
    brief_slug: str | None = None,
    artifact_roots: Iterable[str | Path] = (),
) -> dict[str, Any]:
    record = dict(context.record)
    merged_metadata = dict(record.get("metadata", {}))
    # In-process executors may add domain metadata (for example the sorted
    # timelines frozen into a project-scoped evidence pack) after prepare.
    # Preserve only that validated metadata surface; the lifecycle remains
    # authoritative for status, paths, timestamps, and artifacts.
    if context.run_json_path.is_file():
        try:
            on_disk = validate_run_record(read_json(context.run_json_path))
        except Exception:
            on_disk = None
        if (
            isinstance(on_disk, dict)
            and on_disk.get("project_slug") == context.project_slug
            and on_disk.get("run_id") == context.run_id
        ):
            merged_metadata.update(dict(on_disk.get("metadata", {})))
    if metadata:
        merged_metadata.update(dict(metadata))
    if returncode is not None:
        merged_metadata["returncode"] = returncode
    if error is not None:
        merged_metadata["error"] = str(error)
    record["metadata"] = merged_metadata
    attached_to_task_run = bool(merged_metadata.get("attached_to_task_run"))
    record["status"] = _normalize_status(status, returncode=returncode)
    record["updated_at"] = utc_now_seconds()
    record_out = record.get("out")
    resolved_out = (
        resolve_record_path(record_out, context.project_slug, root=context.root)
        if isinstance(record_out, (str, Path)) and str(record_out)
        else None
    )
    manifest_path = discover_manifest_path(resolved_out, fallback_root=context.run_root)
    if manifest_path is not None:
        record["manifest_path"] = record_path_value(
            manifest_path,
            context.project_slug,
            root=context.root,
        )
        # Copy numeric manifest cost_usd into run metadata for ledger fallback
        manifest_cost = _read_manifest_cost_usd(manifest_path)
        if manifest_cost is not None:
            merged_metadata["cost_usd"] = manifest_cost
    else:
        record.pop("manifest_path", None)
    artifacts = dict(record.get("artifacts", {}))
    mirror_dest = context.run_root / "produces" if attached_to_task_run else None
    mirrored_artifacts = mirror_hype_artifacts(
        context.run_root,
        brief_slug=brief_slug,
        artifact_roots=artifact_roots,
        dest_root=mirror_dest,
        project_slug=context.project_slug,
        root=context.root,
    )
    artifacts.update(mirrored_artifacts)
    if not mirrored_artifacts and manifest_path is not None:
        manifest_outputs = load_manifest_output_artifacts(manifest_path)
        if manifest_outputs:
            artifacts["outputs"] = manifest_outputs
    record["artifacts"] = artifacts
    normalized = validate_run_record(record)
    if not attached_to_task_run:
        write_json_atomic(context.run_json_path, normalized)
        timeline_id = normalized.get("timeline_id")
        if normalized.get("status") == RunStatus.COMPLETED.value and isinstance(timeline_id, str) and timeline_id:
            _record_contributing_run(context.project_slug, timeline_id, context.run_id, root=context.root)
    context.record.clear()
    context.record.update(normalized)
    return normalized


def write_run_record(
    project_slug: str,
    run_id: str,
    *,
    root: str | Path | None = None,
    **fields: Any,
) -> dict[str, Any]:
    require_project(project_slug, root=root)
    run_root = paths.run_dir(project_slug, run_id, root=root)
    run_root.mkdir(parents=True, exist_ok=True)
    if "argv" in fields and fields["argv"] is not None:
        fields["argv"] = redact_cli_args(list(fields["argv"]))
    if "out" in fields and fields["out"] is not None:
        fields["out"] = record_path_value(fields["out"], project_slug, root=root)
    if "manifest_path" in fields and fields["manifest_path"] is not None:
        fields["manifest_path"] = record_path_value(fields["manifest_path"], project_slug, root=root)
    payload = build_run_record(
        project_slug,
        run_id,
        out=fields.pop("out", record_path_value(run_root, project_slug, root=root)),
        **fields,
    )
    write_json_atomic(paths.run_json_path(project_slug, run_id, root=root), payload)
    return payload


def load_run_record(project_slug: str, run_id: str, *, root: str | Path | None = None) -> dict[str, Any]:
    return validate_run_record(read_json(paths.run_json_path(project_slug, run_id, root=root)))


def require_run_record(project_slug: str, run_id: str, *, root: str | Path | None = None) -> dict[str, Any]:
    run_path = paths.run_json_path(project_slug, run_id, root=root)
    if not run_path.exists():
        raise AstridError(
            f"run not found: {run_id}",
            recovery_command=f"python3 -m astrid projects show --project {project_slug}",
        )
    return validate_run_record(read_json(run_path))


def update_run_record(project_slug: str, run_id: str, updates: dict[str, Any], *, root: str | Path | None = None) -> dict[str, Any]:
    if not isinstance(updates, dict):
        raise TypeError("run updates must be an object")
    payload = require_run_record(project_slug, run_id, root=root)
    payload.update(updates)
    payload["updated_at"] = utc_now_seconds()
    if "argv" in payload and payload["argv"] is not None:
        payload["argv"] = redact_cli_args(list(payload["argv"]))
    if "out" in payload and payload["out"] is not None:
        payload["out"] = record_path_value(payload["out"], project_slug, root=root)
    if "manifest_path" in payload and payload["manifest_path"] is not None:
        payload["manifest_path"] = record_path_value(payload["manifest_path"], project_slug, root=root)
    normalized = validate_run_record(payload)
    write_json_atomic(paths.run_json_path(project_slug, run_id, root=root), normalized)
    return normalized


def bind_managed_timeline(
    project_slug: str,
    timeline_slug: str,
    *,
    root: str | Path | None = None,
) -> tuple[str, str, str]:
    """Resolve or create a managed local timeline container for project-bound runs.

    Returns ``(timeline_ulid, timeline_slug, timeline_event_stream_id)``:

    * ``timeline_ulid`` — 26-char Crockford ULID suitable for ``run.timeline_id``.
    * ``timeline_slug`` — the validated slug (echoed back for convenience).
    * ``timeline_event_stream_id`` — UUID read from the timeline identity sidecar.

    Uses existing timeline CRUD entrypoints rather than writing identity files
    directly.  Callers pass this tuple into ``prepare_project_run`` so the run
    record carries only the ULID in ``timeline_id`` while storing the slug and
    event-stream UUID in ``metadata``.
    """
    from astrid.core._shared.jsonio import read_json
    from astrid.core.timeline.crud import TimelineCrudError, create_timeline
    from astrid.core.timeline.paths import (
        assembly_identity_path,
        find_timeline_by_slug,
        validate_timeline_slug,
    )

    slug = validate_timeline_slug(timeline_slug)

    # 1. Try to find an existing timeline with this slug.
    found = find_timeline_by_slug(project_slug, slug, root=root)
    if found is not None:
        ulid, _tdir = found
    else:
        # 2. Not found — create a fresh managed container.
        try:
            result = create_timeline(project_slug, slug, root=root)
        except TimelineCrudError:
            # Race: another caller created it between find and create.
            found = find_timeline_by_slug(project_slug, slug, root=root)
            if found is None:
                raise
            ulid, _tdir = found
        else:
            ulid = result["ulid"]

    # 3. Read the identity sidecar for the event-stream UUID.
    identity_path = assembly_identity_path(project_slug, ulid, root=root)
    identity = read_json(identity_path)
    timeline_event_stream_id = identity.get("timeline_id")
    if not isinstance(timeline_event_stream_id, str) or not timeline_event_stream_id:
        raise ProjectRunError(
            f"timeline {ulid!r} in project {project_slug!r} is missing a valid "
            f"timeline_id in its identity sidecar"
        )

    return (ulid, slug, str(timeline_event_stream_id))


def redact_cli_args(argv: Iterable[str]) -> list[str]:
    redacted: list[str] = []
    hide_next = False
    for raw in argv:
        arg = str(raw)
        if hide_next:
            redacted.append("<redacted>")
            hide_next = False
            continue
        if "=" in arg:
            key, _value = arg.split("=", 1)
            if _is_sensitive_key(key):
                redacted.append(f"{key}=<redacted>")
                continue
        if _is_sensitive_key(arg):
            redacted.append(arg)
            hide_next = True
            continue
        redacted.append(arg)
    return redacted


def mirror_hype_artifacts(
    run_root: str | Path,
    *,
    brief_slug: str | None = None,
    artifact_roots: Iterable[str | Path] = (),
    dest_root: str | Path | None = None,
    project_slug: str | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    run_path = Path(run_root).expanduser().resolve()
    source = discover_hype_artifact_root(run_path, brief_slug=brief_slug, artifact_roots=artifact_roots)
    if source is None:
        return {}
    dest_path_root = Path(dest_root).expanduser().resolve() if dest_root is not None else run_path
    dest_path_root.mkdir(parents=True, exist_ok=True)
    mirrored: dict[str, Any] = {}
    for key, (source_name, dest_name) in HYPE_ARTIFACTS.items():
        source_path = source / source_name
        dest_path = dest_path_root / dest_name
        shutil.copy2(source_path, dest_path)
        if project_slug is None:
            mirrored[key] = {"path": str(dest_path), "source_path": str(source_path)}
        else:
            mirrored[key] = {
                "path": record_path_value(dest_path, project_slug, root=root),
                "source_path": record_path_value(source_path, project_slug, root=root),
            }
    return mirrored


def discover_manifest_path(
    out_root: str | Path | None,
    *,
    fallback_root: str | Path | None = None,
) -> Path | None:
    roots: list[Path] = []
    for raw in (out_root, fallback_root):
        if raw in (None, ""):
            continue
        candidate = Path(raw).expanduser().resolve()
        if candidate not in roots:
            roots.append(candidate)
    for candidate_root in roots:
        for manifest_path in (
            candidate_root / "manifest.json",
            candidate_root / "agent-view" / "manifest.json",
        ):
            if manifest_path.is_file():
                return manifest_path
    return None


def _read_manifest_cost_usd(manifest_path: str | Path) -> float | None:
    """Read a numeric ``cost_usd`` from a generation manifest, if present."""
    try:
        manifest = read_json(manifest_path)
    except Exception:
        return None
    value = manifest.get("cost_usd")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def load_manifest_output_artifacts(manifest_path: str | Path) -> list[dict[str, Any]]:
    try:
        manifest = read_json(manifest_path)
    except Exception:
        return []
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in outputs:
        if not isinstance(item, Mapping):
            continue
        artifact = dict(item)
        artifact["source"] = "manifest"
        normalized.append(artifact)
    return normalized


def discover_hype_artifact_root(
    run_root: str | Path,
    *,
    brief_slug: str | None = None,
    artifact_roots: Iterable[str | Path] = (),
) -> Path | None:
    run_path = Path(run_root).expanduser().resolve()
    candidates = [Path(item).expanduser().resolve() for item in artifact_roots]
    candidates.append(run_path)
    if brief_slug:
        candidates.append(run_path / "briefs" / brief_slug)
    for candidate in candidates:
        if _has_hype_artifact_set(candidate):
            return candidate
    briefs_root = run_path / "briefs"
    if not briefs_root.is_dir():
        return None
    matches = sorted(path for path in briefs_root.iterdir() if path.is_dir() and _has_hype_artifact_set(path))
    if len(matches) > 1:
        raise ProjectRunError(
            "multiple nested hype artifact sets found; pass brief_slug so Astrid can choose one deterministically"
        )
    return matches[0] if matches else None


def _normalize_status(status: RunStatus | str, *, returncode: int | None) -> str:
    normalized = status if isinstance(status, RunStatus) else _normalize_status_token(status)
    if normalized is RunStatus.COMPLETED and returncode not in (None, 0):
        return RunStatus.FAILED.value
    if normalized is RunStatus.RUNNING and returncode not in (None, 0):
        return RunStatus.FAILED.value
    return normalized.value


def _normalize_status_token(status: str) -> RunStatus:
    try:
        return RunStatus.from_run_record_status(status)
    except ValueError:
        pass
    legacy_map = {
        "attached": RunStatus.RUNNING,
        "ok": RunStatus.COMPLETED,
        "nonzero": RunStatus.FAILED,
        "skip": RunStatus.SKIPPED,
    }
    try:
        return legacy_map[status]
    except KeyError:
        raise ProjectRunError(f"unsupported project run status: {status}") from None


def _has_hype_artifact_set(path: Path) -> bool:
    return all((path / source_name).is_file() for source_name, _dest_name in HYPE_ARTIFACTS.values())


def _is_sensitive_key(value: str) -> bool:
    """Test whether *value* looks like a sensitive CLI argument name.

    Matching is normalized so that kebab-case, snake_case, and
    ``name=value`` / ``--flag=value`` forms all trigger redaction.
    Two-token flag forms (e.g. ``--access-key sk-...``) are handled
    upstream in ``redact_cli_args``.
    """
    normalized = value.strip().lower()
    # Strip leading dashes (up to 2) to handle --flag and -f forms.
    key_part = normalized.lstrip("-")
    # Normalize remaining dashes to underscores so --fal-key ↔ fal_key.
    key_part = key_part.replace("-", "_")
    if key_part in _SENSITIVE_NORMALIZED_NAMES:
        return True
    return any(token in key_part for token in _SENSITIVE_SUBSTRINGS)


__all__ = [
    "METADATA_KEY_TIMELINE_BINDING_MODE",
    "METADATA_KEY_TIMELINE_EVENT_STREAM_ID",
    "METADATA_KEY_TIMELINE_SLUG",
    "PROJECT_RUN_ENV",
    "ProjectRunContext",
    "ProjectRunError",
    "TIMELINE_BINDING_MODE_MANAGED",
    "TIMELINE_BINDING_MODE_UNMANAGED",
    "TIMELINE_BINDING_MODES",
    "_project_subprocess_env",
    "bind_managed_timeline",
    "discover_hype_artifact_root",
    "discover_manifest_path",
    "finalize_project_run",
    "load_run_record",
    "load_manifest_output_artifacts",
    "mirror_hype_artifacts",
    "prepare_project_run",
    "project_run_env",
    "record_path_value",
    "redact_cli_args",
    "reject_project_with_out",
    "require_run_record",
    "resolve_record_path",
    "update_run_record",
    "write_run_record",
]
