"""Public SDK discovery and invocation helpers.

This module keeps invocation orchestration behind the SDK package boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import stat
import tempfile
import warnings
from collections.abc import Mapping
from contextlib import contextmanager, nullcontext, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry

from ._module import _sdk_module
from .exceptions import (
    AstridSDKError,
    CapabilityInvocationError,
    CapabilityValidationError,
    UnsupportedCapabilityError,
    _error_payload_from_internal_error,
    _internal_error_from_result,
    _sdk_error_from_exception,
)
from .results import DiscoveryResult, InvocationResult, _json_safe, _json_safe_mapping


def _expanded_config_hash(config: Mapping[str, Any]) -> str:
    """Hash the exact in-memory expansion sent to the renderer."""
    payload = json.dumps(
        config, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_executor(request: Any, registry: Any) -> Any:
    from astrid.core.execution.executor.runner import run_executor as _run_executor

    return _run_executor(request, registry)


def run_orchestrator(request: Any, registry: Any) -> Any:
    from astrid.core.execution.orchestrator.runner import run_orchestrator as _run_orchestrator

    return _run_orchestrator(request, registry)


def dispatch_retried_task(
    *,
    writer: Any,
    task_repo: Any,
    media_repo: Any,
    projects_root: str | Path,
    task: Any,
    attempt: Any,
    idempotency_key: str,
    registry: FrozenSchemaPackRegistry | None = None,
) -> tuple[Any, Any]:
    """Execute one newly retried kernel attempt through the public path.

    Retry admission deliberately remains a small repository transaction. The
    service then dispatches the same immutable capability/spec through the
    normal handler, execution, and media-completion fences. This is kept here
    so task and run retry surfaces cannot drift into two subtly different
    worker implementations. Callers must invoke this only for a fresh retry
    receipt; exact receipt replays are read-only and must not dispatch again.
    """
    from astrid.core.kernel.read import schema_registry_context
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.task_executor import CapabilityTaskHandler, ExecutionService

    spec = dict(getattr(task, "spec", {}) or {})
    capability_kind = str(spec.get("kind") or "executor")
    handler = CapabilityTaskHandler(
        capability_kind=capability_kind,
        capability_id=str(task.capability),
        projects_root=projects_root,
        invocation="sdk",
        require_executor_version=True,
    )
    service = ExecutionService(projects_root=projects_root, task_repo=task_repo)
    with schema_registry_context(registry) if registry is not None else nullcontext():
        execution = service.execute(
            UnitOfWork(writer),
            project_id=str(task.project_id),
            task_id=str(task.id),
            attempt_id=str(attempt.id),
            lease_id=str(attempt.lease_id),
            expected_status_version=int(attempt.status_version),
            idempotency_key=f"{idempotency_key}:exec",
            handler=handler,
        )
    completion = None
    if execution.outcome == "prepared" and execution.prepared is not None:
        with schema_registry_context(registry) if registry is not None else nullcontext():
            completion = service.complete(
                UnitOfWork(writer),
                prepared=execution.prepared,
                media_repo=media_repo,
                idempotency_key=f"{idempotency_key}:complete",
            )
        if completion.outcome == "completed":
            service.cleanup_staging(execution.prepared.staging_dir)
    return execution, completion


def discover(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
    kind: str | None = None,
) -> DiscoveryResult:
    sdk_module = _sdk_module()
    discovered_packs = sdk_module._discover_pack_inventory(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    )
    pack_permission_ids_by_pack_id = sdk_module._pack_permission_ids_by_pack_id(discovered_packs)
    executor_registry, orchestrator_registry, element_registry = sdk_module._load_registries(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        include_elements=True,
    )
    if element_registry is None:
        raise CapabilityInvocationError("element registry was not loaded")
    (
        packs,
        generation_backends,
        element_kinds,
        generation_features,
        generation_modes,
    ) = sdk_module._build_discovery_metadata(
        discovered_packs,
        element_registry=element_registry,
    )

    if pack_permission_ids_by_pack_id:
        executors = tuple(
            sdk_module._capability_from_executor(
                definition,
                executor_registry,
                pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
            )
            for definition in executor_registry.list()
        )
        orchestrators = tuple(
            sdk_module._capability_from_orchestrator(
                definition,
                orchestrator_registry,
                pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
            )
            for definition in orchestrator_registry.list()
        )
        elements = tuple(
            sdk_module._capability_from_element(
                definition,
                pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
            )
            for definition in element_registry.list()
        )
    else:
        executors = tuple(
            sdk_module._capability_from_executor(definition, executor_registry)
            for definition in executor_registry.list()
        )
        orchestrators = tuple(
            sdk_module._capability_from_orchestrator(definition, orchestrator_registry)
            for definition in orchestrator_registry.list()
        )
        elements = tuple(
            sdk_module._capability_from_element(definition)
            for definition in element_registry.list()
        )
    if kind is not None and kind not in ("executor", "orchestrator", "element"):
        raise CapabilityValidationError(
            f"discover(kind=...) must be one of 'executor', 'orchestrator', "
            f"'element' — got {kind!r}"
        )
    executors = executors if kind in (None, "executor") else ()
    orchestrators = orchestrators if kind in (None, "orchestrator") else ()
    elements = elements if kind in (None, "element") else ()
    return DiscoveryResult(
        executors=executors,
        orchestrators=orchestrators,
        elements=elements,
        capabilities=executors + orchestrators + elements,
        packs=packs,
        generation_backends=generation_backends,
        element_kinds=element_kinds,
        generation_features=generation_features,
        generation_modes=generation_modes,
    )


def get_capability(
    capability_id: str,
    *,
    kind: Any | None = None,
    element_kind: str | None = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    include_elements: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
    _registries: tuple[Any, Any, Any | None] | None = None,
):
    sdk_module = _sdk_module()
    if _registries is None:
        executor_registry, orchestrator_registry, element_registry = sdk_module._load_registries(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
            banodoco_config=banodoco_config,
            active_theme=active_theme,
            include_missing_roots=include_missing_roots,
            include_elements=include_elements or kind == "element" or kind is None,
        )
    else:
        executor_registry, orchestrator_registry, element_registry = _registries

    resolved = sdk_module._resolve_capability(
        capability_id,
        kind=kind,
        element_kind=element_kind,
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
        element_registry=element_registry,
    )
    # Keep direct describes consistent with discover(): pack-level and
    # capability-specific safety permissions are part of the public handle,
    # not only of the full inventory DTO.
    discovered_packs = sdk_module._discover_pack_inventory(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    )
    return sdk_module._apply_pack_permission_ids(
        resolved,
        pack_permission_ids_by_pack_id=sdk_module._pack_permission_ids_by_pack_id(discovered_packs),
    )


def _normalize_executor_result(result: Any) -> dict[str, Any]:
    payload = {
        "executor_id": result.executor_id,
        "kind": result.kind,
        "command": result.command,
        "cwd": result.cwd,
        "env": result.env,
        "payload": result.payload,
        "returncode": result.returncode,
        "dry_run": result.dry_run,
        "skipped": result.skipped,
        "skipped_reason": result.skipped_reason,
        "missing_binaries": result.missing_binaries,
        "error": result.error,
        "ok": result.ok,
        "run_id": getattr(result, "run_id", None),
        "run_root": getattr(result, "run_root", None),
        "outputs": getattr(result, "outputs", {}),
        "executor_version": getattr(result, "executor_version", None),
    }
    return _json_safe_mapping(payload)


def _normalize_orchestrator_result(result: Any) -> dict[str, Any]:
    return _json_safe_mapping(result.to_dict())


def _validate_timeline_visualize_inputs(
    inputs: Mapping[str, Any] | None,
    *,
    project: str | None,
    project_root: str | Path | None = None,
    out: str | Path | None = None,
) -> dict[str, Any]:
    """Validate visualization's selector/ownership contract before admission.

    This is intentionally read-only.  Timeline visualization's runner repeats
    the checks as defense-in-depth, but a public SDK call must reject a
    foreign, missing, or malformed timeline before kernel admission.
    """

    values = dict(inputs or {})
    raw_formats = values.get("formats")
    if raw_formats is not None:
        if isinstance(raw_formats, str):
            raw_formats = [raw_formats]
        if not isinstance(raw_formats, (list, tuple, set)):
            raise CapabilityValidationError(
                "rendering.timeline_visualize formats must be a list of png, svg, md, or all"
            )
        formats = {
            part.strip().lower()
            for token in raw_formats
            for part in str(token).split(",")
            if part.strip()
        }
        if not formats:
            raise CapabilityValidationError(
                "rendering.timeline_visualize formats must contain png, svg, md, or all"
            )
        allowed = {"png", "svg", "md", "all"}
        invalid = sorted(formats - allowed)
        if invalid:
            raise CapabilityValidationError(
                f"invalid visualization format(s): {', '.join(invalid)}; "
                "choose png, svg, md, or all"
            )
        if "all" in formats and len(formats) > 1:
            raise CapabilityValidationError(
                "visualization format 'all' cannot be combined with another format"
            )
    if out not in (None, ""):
        raise CapabilityValidationError(
            "--out is not supported for project timeline visualization; "
            "omit it and use the returned durable manifest_path"
        )
    source = values.get("timeline_source")
    source_supplied = "timeline_source" in values and source is not None
    if source_supplied and (
        source == ""
        or isinstance(source, (list, tuple, set))
        and not source
    ):
        raise CapabilityValidationError("timeline_source must contain at least one path")
    has_source = source_supplied
    has_ref = values.get("timeline_slug") not in (None, "")
    select_all = bool(values.get("all", False))
    if has_source and (has_ref or select_all):
        raise CapabilityValidationError(
            "timeline_source cannot be combined with timeline_slug or all; "
            "choose a managed path, a timeline ref, or all"
        )
    if has_ref and select_all:
        raise CapabilityValidationError(
            "timeline_slug and all are mutually exclusive; choose one timeline ref or all"
        )
    from_view = values.get("from_view") not in (None, "")
    focus = values.get("focus") not in (None, "")
    if from_view != focus:
        raise CapabilityValidationError(
            "from_view and focus must be supplied together for visualization navigation"
        )
    cold_selectors = [
        name
        for name in ("shot", "range", "at", "clip", "asset")
        if values.get(name) not in (None, "")
    ]
    if len(cold_selectors) > 1:
        raise CapabilityValidationError(
            "cold selectors are mutually exclusive: "
            + ", ".join(f"--{name}" for name in cold_selectors)
        )
    refresh_root = bool(values.get("refresh_root", False))
    if refresh_root and not from_view:
        raise CapabilityValidationError("refresh_root requires from_view and focus")
    if from_view:
        conflicts = [
            name
            for name, present in (
                ("timeline_source", has_source),
                ("timeline_slug", has_ref),
                ("all", select_all),
                *((name, name in cold_selectors) for name in cold_selectors),
            )
            if present
        ]
        if conflicts:
            raise CapabilityValidationError(
                "from_view/focus cannot be combined with "
                + ", ".join(f"--{name.replace('_', '-')}" for name in conflicts)
            )
    filmstrip = values.get("filmstrip")
    rendered_video = values.get("rendered_video")
    layout = values.get("layout")
    if layout is not None and (
        not isinstance(layout, str) or layout not in {"time-scaled", "linear", "both"}
    ):
        raise CapabilityValidationError(
            "layout must be time-scaled, linear, or both"
        )
    if filmstrip is not None and (
        not isinstance(filmstrip, str)
        or filmstrip not in {"auto", "off", "assets", "rendered"}
    ):
        raise CapabilityValidationError(
            "filmstrip must be auto, off, assets, or rendered"
        )
    scope = values.get("scope")
    if scope is not None and (
        not isinstance(scope, str)
        or scope not in {
            "project",
            "timeline",
            "shot",
            "range",
            "clip",
            "asset",
            "timestamp",
        }
    ):
        raise CapabilityValidationError(
            "scope must be project, timeline, shot, range, clip, asset, or timestamp"
        )
    raw_context = values.get("context", 3.0)
    if (
        isinstance(raw_context, bool)
        or not isinstance(raw_context, (int, float))
        or not math.isfinite(float(raw_context))
        or float(raw_context) < 0
    ):
        raise CapabilityValidationError("context must be a finite non-negative number")
    raw_neighbors = values.get("neighbors", 0)
    if (
        isinstance(raw_neighbors, bool)
        or not isinstance(raw_neighbors, int)
        or raw_neighbors < 0
    ):
        raise CapabilityValidationError("neighbors must be a non-negative integer")
    if rendered_video not in (None, "") and filmstrip not in (None, "auto", "rendered"):
        raise CapabilityValidationError(
            "rendered_video requires filmstrip auto or rendered"
        )
    if filmstrip == "rendered" and rendered_video in (None, ""):
        raise CapabilityValidationError("filmstrip rendered requires rendered_video")
    requested_project = values.get("project_slug")
    if (
        requested_project not in (None, "")
        and project not in (None, "")
        and requested_project != project
    ):
        raise CapabilityValidationError(
            f"project_slug {requested_project!r} does not match project {project!r}"
        )

    if project is None or not str(project).strip():
        raise CapabilityValidationError(
            "rendering.timeline_visualize requires project=<slug> to resolve a managed timeline"
        )

    # Resolve the same project root the kernel will bind, without opening the
    # ledger.  This keeps pre-admission ownership checks independent of the
    # ambient workspace and makes foreign absolute paths fail closed.
    from astrid.core.foundation.project_paths import ProjectPathError, project_dir
    from astrid.core.project.ownership import ProjectOwnershipError, require_project_owned_artifact
    from astrid.packs.rendering.executors.timeline_visualize.select import (
        discover_timelines,
        select_kernel_timelines,
        select_timeline,
    )

    bound_root = _resolve_projects_root(project_root, project)
    try:
        managed_project = project_dir(project, root=bound_root).resolve()
    except ProjectPathError as exc:
        raise CapabilityValidationError(str(exc)) from exc
    if not (managed_project / "project.json").is_file():
        raise CapabilityValidationError(
            f"project not found: {project!r}; create it before visualizing a timeline"
        )

    if from_view:
        raw_view = Path(str(values["from_view"])).expanduser()
        view_path = raw_view if raw_view.is_absolute() else Path.cwd() / raw_view
        if not view_path.is_file():
            raise CapabilityValidationError(
                f"from_view must name an existing visualization manifest: {view_path}"
            )
        from astrid.packs.rendering.executors.timeline_visualize.frozen import (
            FrozenViewError,
            discard_rehydrated_pack,
            load_frozen_view,
            resolve_focus,
        )
        from astrid.packs.rendering.executors.timeline_visualize.ids import (
            parse_qualified_ref,
        )

        try:
            frozen = load_frozen_view(view_path, project_root=managed_project)
        except FrozenViewError as exc:
            raise CapabilityValidationError(f"from_view rejected: {exc}") from exc
        try:
            try:
                resolved_focus = resolve_focus(
                    frozen,
                    str(values["focus"]),
                    context_seconds=float(raw_context),
                    neighbors=raw_neighbors,
                )
                parsed_focus = parse_qualified_ref(str(values["focus"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise CapabilityValidationError(f"focus rejected: {exc}") from exc
            if refresh_root and (
                parsed_focus.kind != "TL" or resolved_focus.kind != "timeline"
            ):
                raise CapabilityValidationError(
                    "refresh_root focus must be the frozen timeline reference"
                )
            return {
                "mode": "frozen_view",
                "manifest_sha256": hashlib.sha256(view_path.read_bytes()).hexdigest(),
                "focus": str(values["focus"]),
                "snapshot_sns": frozen.snapshot_sns,
            }
        finally:
            discard_rehydrated_pack(frozen.pack_root)

    selected: list[Any] = []
    diagnostics: list[str] = []
    if not has_source:
        selected, diagnostics = select_kernel_timelines(
            managed_project,
            project_slug=str(project),
            slug=str(values["timeline_slug"]) if has_ref else None,
            all=select_all,
            default=not has_ref and not select_all,
        )
    if (has_ref or select_all or not has_source) and not selected:
        detail = "; ".join(diagnostics) or "no eligible managed timeline was selected"
        raise CapabilityValidationError(f"timeline selection failed: {detail}")

    if not has_source:
        return {
            "mode": "kernel",
            "timelines": [
                {
                    "timeline_id": row.timeline_id,
                    "head_version": row.config_version,
                    "head_event_id": row.head_event_id,
                    "head_hash": row.head_hash,
                }
                for row in selected
            ],
        }
    if isinstance(source, (str, Path)):
        source_items = [source]
    elif isinstance(source, (list, tuple, set)):
        source_items = list(source)
        if not source_items:
            raise CapabilityValidationError("timeline_source must contain at least one path")
    else:
        raise CapabilityValidationError(
            "timeline_source must be a path or a list of paths inside the project's managed timelines"
        )

    timelines, diagnostics = select_timeline(managed_project, all=True)
    discovered_timelines = discover_timelines(managed_project)
    timelines_root = (managed_project / "timelines").resolve()
    legacy_heads: list[dict[str, str]] = []
    selected_legacy_ids: set[str] = set()
    for raw in source_items:
        if not isinstance(raw, (str, Path)) or not str(raw).strip():
            raise CapabilityValidationError(
                f"timeline_source entries must be non-empty paths; got {raw!r}"
            )
        try:
            candidate = require_project_owned_artifact(
                project,
                "timeline",
                raw,
                root=bound_root,
            )
        except ProjectOwnershipError as exc:
            raise CapabilityValidationError(str(exc)) from exc
        if not candidate.exists() or not (candidate.is_file() or candidate.is_dir()):
            raise CapabilityValidationError(
                f"timeline_source does not exist or is not a file/directory: {candidate}"
            )
        if not candidate.is_relative_to(timelines_root):
            raise CapabilityValidationError(
                f"timeline_source must be inside the project's managed timelines: {candidate}"
            )
        if not any(
            row.timeline_dir is not None and candidate.is_relative_to(row.timeline_dir.resolve())
            for row in timelines
        ):
            tombstoned = next(
                (
                    row
                    for row in discovered_timelines
                    if row.is_tombstoned
                    and row.timeline_dir is not None
                    and candidate.is_relative_to(row.timeline_dir.resolve())
                ),
                None,
            )
            if tombstoned is not None:
                raise CapabilityValidationError(
                    f"timeline_source belongs to tombstoned timeline "
                    f"{tombstoned.timeline_ulid!r}: {candidate}"
                )
            detail = "; ".join(diagnostics) or "not a live managed timeline"
            raise CapabilityValidationError(
                f"timeline_source is not a managed timeline directory/file for project {project!r}: "
                f"{candidate} ({detail})"
            )
        timeline_dir = next(
            row.timeline_dir.resolve()
            for row in timelines
            if row.timeline_dir is not None and candidate.is_relative_to(row.timeline_dir.resolve())
        )
        eventlog = timeline_dir / "assembly.jsonl"
        if not eventlog.is_file():
            raise CapabilityValidationError(
                f"legacy timeline_source has no assembly.jsonl event log: {timeline_dir}"
            )
        if timeline_dir.name in selected_legacy_ids:
            raise CapabilityValidationError(
                f"timeline_source selects timeline {timeline_dir.name!r} more than once"
            )
        selected_legacy_ids.add(timeline_dir.name)
        legacy_heads.append(
            {
                "timeline_ulid": timeline_dir.name,
                "eventlog_sha256": hashlib.sha256(eventlog.read_bytes()).hexdigest(),
            }
        )
    return {
        "mode": "legacy_file",
        "timelines": sorted(legacy_heads, key=lambda row: row["timeline_ulid"]),
    }


def _payload_manifest_path(raw_result: Mapping[str, Any]) -> str | None:
    payload = raw_result.get("payload")
    if not isinstance(payload, Mapping):
        return None
    for key in ("manifest_path", "manifest"):
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        path = Path(value).expanduser().resolve()
        if path.name == "manifest.json":
            return str(path)
    return None


_RENDER_PROFILE_REQUIRED_FIELDS = (
    "width",
    "height",
    "fps_rational",
    "time_base",
    "container",
    "video_codec",
    "video_profile",
    "video_level",
    "pixel_format",
    "duration_tolerance",
)
_RENDER_PROFILE_AUDIO_FIELDS = (
    "audio_codec",
    "audio_sample_rate",
    "audio_channel_layout",
)
_RENDER_PROFILE_ALLOWED_FIELDS = frozenset(
    (*_RENDER_PROFILE_REQUIRED_FIELDS, *_RENDER_PROFILE_AUDIO_FIELDS)
)
_RENDER_PROFILE_EXAMPLE = {
    "width": 1920,
    "height": 1080,
    "fps_rational": [30, 1],
    "time_base": [1, 90000],
    "container": "mp4",
    "video_codec": "h264",
    "video_profile": None,
    "video_level": None,
    "pixel_format": "yuv420p",
    "audio_codec": "aac",
    "audio_sample_rate": 48000,
    "audio_channel_layout": "stereo",
    "duration_tolerance": 1,
}


def _render_profile_guidance() -> str:
    example = json.dumps(_RENDER_PROFILE_EXAMPLE, separators=(",", ":"))
    return (
        "--profile uses the flat RenderProfile v1 object (no video/audio nesting); "
        "audio_codec, audio_sample_rate, and audio_channel_layout must be supplied "
        "together or all omitted. Explicit profiles must match the authoritative "
        "theme canvas; set theme_overrides.visual.canvas for a different size. "
        f"Complete Remotion MP4 example: {example}"
    )


def _validate_explicit_render_profile(profile: Any) -> None:
    """Validate the frozen flat profile contract before kernel admission."""

    if profile is None:
        return
    if not isinstance(profile, Mapping):
        raise CapabilityValidationError(
            f"invalid render profile: expected a JSON object. {_render_profile_guidance()}"
        )
    missing = [field for field in _RENDER_PROFILE_REQUIRED_FIELDS if field not in profile]
    unknown = sorted(str(field) for field in profile if field not in _RENDER_PROFILE_ALLOWED_FIELDS)
    key_issues: list[str] = []
    if missing:
        key_issues.append("missing required field(s): " + ", ".join(missing))
    if unknown:
        key_issues.append("unknown field(s): " + ", ".join(unknown))
    if key_issues:
        raise CapabilityValidationError(
            "invalid render profile: " + "; ".join(key_issues) + ". " + _render_profile_guidance()
        )
    from astrid.core.rendering.contracts import RenderProfile

    try:
        RenderProfile.from_dict(profile)
    except (TypeError, ValueError) as exc:
        raise CapabilityValidationError(
            f"invalid render profile: {exc}. {_render_profile_guidance()}"
        ) from exc


def _validate_managed_profile_theme_compatibility(
    profile: Mapping[str, Any] | None,
    *,
    timeline: Mapping[str, Any],
    registry: Mapping[str, Any],
    timeline_slug: str,
) -> None:
    """Reject canvas/fps profiles that cannot match the canonical theme.

    This is intentionally managed-ref-only. Explicit file-mode callers retain
    the renderer's historical support-selection semantics.
    """

    if profile is None:
        return
    from astrid.core.rendering.profile import resolve_render_profile

    try:
        authoritative = resolve_render_profile(
            timeline,
            registry,
            audio_ownership="rendered",
        )
    except (TypeError, ValueError, OSError, FileNotFoundError) as exc:
        raise CapabilityValidationError(
            f"cannot resolve authoritative theme canvas for canonical timeline "
            f"{timeline_slug!r}: {exc}. Fix the timeline theme and retry"
        ) from exc

    mismatches: list[str] = []
    for field, expected in (
        ("width", authoritative.width),
        ("height", authoritative.height),
        ("fps_rational", list(authoritative.fps_rational)),
    ):
        requested = profile.get(field)
        if requested != expected:
            mismatches.append(
                f"{field}={requested!r} (authoritative theme canvas produces {expected!r})"
            )
    if mismatches:
        raise CapabilityValidationError(
            f"invalid render profile for canonical timeline {timeline_slug!r}: "
            + "; ".join(mismatches)
            + ". Explicit profiles must match the authoritative theme canvas; "
            "use the default profile from timelines render --help or set "
            "theme_overrides.visual.canvas to the requested width, height, and fps, then retry"
        )


def _prepare_managed_render_inputs(
    inputs: Mapping[str, Any] | None,
    *,
    project: str | None,
    project_root: str | Path | None,
    _client: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Resolve and materialize the explicit ``rendering.render`` ref mode."""

    values = dict(inputs or {})
    timeline_ref = values.get("timeline_ref")
    expected_version = values.get("expected_version")
    if timeline_ref in (None, ""):
        if expected_version is not None:
            raise CapabilityValidationError(
                "expected_version is only valid with rendering.render timeline_ref"
            )
        if values.get("timeline") in (None, ""):
            raise CapabilityValidationError(
                "rendering.render requires exactly one input mode: timeline=<project-owned file> "
                "or timeline_ref=<kernel slug/UUID/ULID>"
            )
        _validate_explicit_render_profile(values.get("profile"))
        from astrid.core.project.ownership import (
            ProjectOwnershipError,
            require_project_owned_artifact,
        )
        from astrid.core.rendering.output_policy import (
            DEFAULT_RENDER_OUTPUT_NAME,
            RenderOutputPolicyError,
            validate_render_output_policy,
        )

        raw_timeline = values["timeline"]
        timeline_path = Path(str(raw_timeline)).expanduser()
        if project is not None and str(project).strip():
            try:
                timeline_path = require_project_owned_artifact(
                    str(project),
                    "timeline",
                    timeline_path,
                    root=_resolve_projects_root(project_root, project),
                )
            except ProjectOwnershipError as exc:
                raise CapabilityValidationError(str(exc)) from exc
        output_name = values.get("output_name", DEFAULT_RENDER_OUTPUT_NAME)
        if output_name is None:
            output_name = DEFAULT_RENDER_OUTPUT_NAME
        try:
            validate_render_output_policy(
                output_name,
                timeline=timeline_path,
                profile=values.get("profile"),
            )
        except RenderOutputPolicyError as exc:
            raise CapabilityValidationError(str(exc), details=exc.details) from exc
        warnings.warn(
            "rendering.render raw-file mode (timeline=<path>) keys idempotency by file "
            "path, not timeline content: editing the timeline at the same path and "
            "re-invoking returns the cached run without recomputing. Use the canonical "
            "managed path for iteration instead: timelines create/save + timelines "
            "render <timeline_ref>, or pass timeline_ref=<ref>, so renders are "
            "content-hashed and never serve stale results.",
            RuntimeWarning,
            stacklevel=2,
        )
        return values, None
    if values.get("timeline") not in (None, ""):
        raise CapabilityValidationError(
            "timeline and timeline_ref are mutually exclusive; use timeline for explicit "
            "file mode or timeline_ref for canonical managed mode"
        )
    if values.get("assets_registry") not in (None, ""):
        raise CapabilityValidationError(
            "assets_registry cannot be overridden with timeline_ref; the canonical timeline "
            "registry is pinned with the snapshot"
        )
    if project is None or not str(project).strip():
        raise CapabilityValidationError("rendering.render timeline_ref requires project=<slug>")
    if not isinstance(timeline_ref, str) or not timeline_ref.strip():
        raise CapabilityValidationError("timeline_ref must be a non-empty slug, UUID, or ULID")
    if expected_version is not None and (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 1
    ):
        raise CapabilityValidationError("expected_version must be a positive integer")
    _validate_explicit_render_profile(values.get("profile"))
    from astrid.packs.rendering.executors.render.managed_timeline import (
        ManagedRenderValidationError,
        materialize_managed_render_snapshot,
        resolve_managed_render_snapshot,
        validate_managed_render_snapshot,
    )

    if _client is None:
        # Global SDK callers do not own an application object. Use a bounded
        # client lifetime for the read/materialization transaction; callers
        # using AstridClient.invoke inject their already-open client.
        from astrid.sdk.client import AstridClient

        with AstridClient.open(project_root) as owned_client:
            return _prepare_managed_render_inputs(
                values,
                project=project,
                project_root=project_root,
                _client=owned_client,
            )

    projects_root = _resolve_projects_root(project_root, project)
    try:
        snapshot = resolve_managed_render_snapshot(
            projects_root,
            project_ref=str(project),
            timeline_ref=timeline_ref.strip(),
            expected_version=expected_version,
            client=_client,
        )
        from astrid.core.timeline._edit_helpers import TimelineEditError
        from astrid.core.timeline.expand_shots import expand_shot_clips

        # Admission is intentionally split: the authoring parent may contain
        # composite ``shot`` clips, but every reference must resolve through
        # the SDK before expansion. The expander never invents or fetches a
        # missing shot and never talks to storage itself.
        child_records: list[dict[str, Any]] = []
        raw_clips = snapshot.config.get("clips", [])
        for index, clip in enumerate(raw_clips):
            if not isinstance(clip, Mapping) or clip.get("clipType") != "shot":
                continue
            params = clip.get("params")
            shot_id = params.get("shot_id") if isinstance(params, Mapping) else None
            timeline_document_id = (
                params.get("timeline_document_id") if isinstance(params, Mapping) else None
            )
            if not isinstance(shot_id, str) or not shot_id:
                raise CapabilityValidationError(
                    f"canonical timeline {snapshot.timeline_slug!r} shot clip at index {index} "
                    "is missing a registered shot_id"
                )
            shot_result = _client.shots.show(str(project), shot_id)
            if not shot_result.ok or not shot_result.data:
                raise CapabilityValidationError(
                    f"canonical timeline {snapshot.timeline_slug!r} references unregistered shot "
                    f"{shot_id!r}"
                )
            if not isinstance(timeline_document_id, str) or not timeline_document_id:
                raise CapabilityValidationError(
                    f"canonical timeline {snapshot.timeline_slug!r} shot {shot_id!r} "
                    "is missing timeline_document_id"
                )

        def load_child(ref: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
            child_result = _client.timelines.show(str(project), ref)
            if not child_result.ok or not child_result.data:
                raise TimelineEditError(f"timeline {ref!r} was not found")
            child = child_result.data
            child_config = child.get("config")
            child_registry = child.get("registry")
            if not isinstance(child_config, Mapping) or not isinstance(child_registry, Mapping):
                raise TimelineEditError(f"timeline {ref!r} has an invalid snapshot")
            child_records.append(
                {
                    "timeline_id": str(child["timeline_id"]),
                    "timeline_ulid": str(child["timeline_ulid"]),
                    "slug": str(child["slug"]),
                    "config_version": int(child["config_version"]),
                    "config_hash": _expanded_config_hash(child_config),
                }
            )
            return child_config, child_registry

        try:
            expanded_config, expanded_registry = expand_shot_clips(
                snapshot.config,
                snapshot.registry,
                load_timeline=load_child,
            )
        except TimelineEditError as exc:
            raise CapabilityValidationError(str(exc)) from exc
        from dataclasses import replace

        snapshot = replace(
            snapshot,
            config=expanded_config,
            registry=expanded_registry,
            materialized_registry_hash=_expanded_config_hash(expanded_registry),
            expansion={
                "children": child_records,
                "expanded_config_hash": _expanded_config_hash(expanded_config),
            },
        )
        validate_managed_render_snapshot(snapshot)
    except ManagedRenderValidationError as exc:
        raise CapabilityValidationError(str(exc), details=exc.details) from exc
    except ValueError as exc:
        raise CapabilityValidationError(str(exc)) from exc
    _validate_managed_profile_theme_compatibility(
        values.get("profile"),
        timeline=snapshot.config,
        registry=snapshot.registry,
        timeline_slug=snapshot.timeline_slug,
    )
    from astrid.core.rendering.output_policy import (
        DEFAULT_RENDER_OUTPUT_NAME,
        RenderOutputPolicyError,
        validate_render_output_policy,
    )

    output_name = values.get("output_name", DEFAULT_RENDER_OUTPUT_NAME)
    if output_name is None:
        output_name = DEFAULT_RENDER_OUTPUT_NAME
    try:
        validate_render_output_policy(
            output_name,
            timeline=snapshot.config,
            profile=values.get("profile"),
        )
    except RenderOutputPolicyError as exc:
        raise CapabilityValidationError(str(exc), details=exc.details) from exc
    timeline_path, registry_path, authority = materialize_managed_render_snapshot(
        projects_root,
        snapshot,
    )
    values.update(
        {
            "timeline": str(timeline_path),
            "assets_registry": str(registry_path),
            "timeline_authority": authority,
        }
    )
    # The public selector and CAS guard are admission-only controls. The
    # resolved authority object below is the durable run input/cache identity;
    # do not leak these two controls as undeclared renderer CLI flags.
    values.pop("timeline_ref", None)
    values.pop("expected_version", None)
    return values, authority


def _discover_invocation_manifest_path(
    raw_result: Mapping[str, Any],
    *,
    out: Path | str | None,
) -> str | None:
    manifest_path = _payload_manifest_path(raw_result)
    if manifest_path is not None:
        return manifest_path
    outputs = raw_result.get("outputs")
    if isinstance(outputs, Mapping):
        output_manifest = outputs.get("manifest_path")
        if isinstance(output_manifest, str):
            candidate = Path(output_manifest).expanduser().resolve()
            if candidate.name == "manifest.json" and candidate.is_file():
                return str(candidate)
    roots: list[Path] = []
    for raw in (raw_result.get("run_root"), out):
        if raw in (None, ""):
            continue
        root = Path(str(raw)).expanduser().resolve()
        if root not in roots:
            roots.append(root)
    for root in roots:
        for candidate in (root / "manifest.json", root / "agent-view" / "manifest.json"):
            if candidate.is_file():
                return str(candidate)
    return None


def _invocation_outputs(
    raw_result: Mapping[str, Any],
    *,
    manifest_path: str | None,
    project_root: Path | None = None,
    capability_id: str | None = None,
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    declared = raw_result.get("outputs")
    if isinstance(declared, Mapping):
        outputs.update(declared)
    payload = raw_result.get("payload")
    if isinstance(payload, Mapping) and isinstance(payload.get("outputs"), Mapping):
        outputs.update(payload["outputs"])
    if manifest_path is not None:
        manifest = Path(manifest_path)
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            document = None
        is_timeline_manifest = isinstance(document, dict) and document.get("kind") in {
            "timeline_visualize",
            "timeline_visualize_project",
        }
        if capability_id == "rendering.timeline_visualize" or is_timeline_manifest:
            pack_root = manifest.parent
            # Kernel completion publishes every evidence-pack member as its
            # own managed CAS object and removes private staging.  The parent
            # of the durable manifest is therefore a hash fan-out directory,
            # not the logical pack root.  Reuse the frozen loader's verified
            # task-output rehydration so the long-standing ``pack_root`` SDK
            # convenience remains an actually navigable directory.
            if project_root is not None and not manifest.is_relative_to(project_root):
                from astrid.packs.rendering.executors.timeline_visualize.frozen import (
                    discard_rehydrated_pack,
                    rehydrate_managed_pack,
                )

                rehydrated = rehydrate_managed_pack(
                    manifest,
                    project_root=project_root,
                )
                try:
                    pack_root = _persist_visualization_pack(
                        rehydrated,
                        project_root=project_root,
                        manifest=manifest,
                    )
                finally:
                    discard_rehydrated_pack(rehydrated)
            elif project_root is not None and capability_id == "rendering.timeline_visualize":
                from astrid.packs.rendering.executors.timeline_visualize.frozen import (
                    discard_rehydrated_pack,
                    load_frozen_view,
                )

                frozen = load_frozen_view(
                    manifest,
                    project_root=project_root,
                )
                try:
                    pack_root = _persist_visualization_pack(
                        frozen.pack_root,
                        project_root=project_root,
                        manifest=manifest,
                    )
                finally:
                    discard_rehydrated_pack(frozen.pack_root)
            elif capability_id == "rendering.timeline_visualize":
                raise CapabilityInvocationError(
                    "timeline visualization result cannot be verified without a project root"
                )
            outputs["pack_root"] = str(pack_root)
            outputs["manifest_path"] = str(manifest)
            outputs["pages"] = [
                str(path)
                for path in sorted(pack_root.rglob("PG*.png"))
                if "filmstrip" not in path.relative_to(pack_root).parts
            ]
            outputs["file_hashes"] = {
                path.relative_to(pack_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in sorted(pack_root.rglob("*"))
                if path.is_file()
            }
    return _json_safe_mapping(outputs)


def _persist_visualization_pack(
    source: Path,
    *,
    project_root: Path,
    manifest: Path,
) -> Path:
    """Copy a verified CAS pack into a durable, non-authoritative view cache.

    ``load_frozen_view`` deliberately rehydrates managed outputs in a private
    temporary directory. Public SDK results routinely cross a CLI process
    boundary, so returning that temporary path would immediately produce a
    dangling ``pack_root``. The cache is keyed by the durable manifest bytes,
    never linked to CAS, and remains a derived convenience: ``manifest_path``
    is still the authoritative navigation handle.
    """

    project = Path(project_root).resolve(strict=True)
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    cache_parent = project
    for part in (".astrid", "views", "timeline_visualize"):
        cache_parent = cache_parent / part
        if cache_parent.is_symlink():
            raise CapabilityInvocationError(
                f"visualization cache path must not contain symlinks: {cache_parent}"
            )
        cache_parent.mkdir(exist_ok=True)
        if cache_parent.resolve() != cache_parent or not cache_parent.is_relative_to(project):
            raise CapabilityInvocationError("visualization cache path escapes its owning project")
    destination = cache_parent / digest

    def _tree_state(root: Path) -> dict[str, str]:
        paths = sorted(root.rglob("*"))
        symlinks = [path for path in paths if path.is_symlink()]
        if symlinks:
            raise CapabilityInvocationError(
                f"visualization cache tree must not contain symlinks: {symlinks[0]}"
            )
        state: dict[str, str] = {}
        for path in paths:
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                state[f"{relative}/"] = "directory"
            elif path.is_file():
                state[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            else:
                raise CapabilityInvocationError(
                    f"visualization cache tree contains a non-regular entry: {path}"
                )
        return state

    source_state = _tree_state(source)
    with _visualization_cache_lock(cache_parent / f".{digest}.lock"):
        try:
            destination_stat = destination.lstat()
        except FileNotFoundError:
            destination_stat = None
        if destination_stat is not None and stat.S_ISLNK(destination_stat.st_mode):
            raise CapabilityInvocationError(
                f"visualization cache destination must not be a symlink: {destination}"
            )
        destination_identity: tuple[int, int] | None = None
        destination_state: dict[str, str] | None = None
        if destination_stat is not None and stat.S_ISDIR(destination_stat.st_mode):
            destination_identity = (destination_stat.st_dev, destination_stat.st_ino)
            destination_state = _tree_state(destination)
            after = destination.lstat()
            if (after.st_dev, after.st_ino) != destination_identity:
                raise CapabilityInvocationError(
                    "visualization cache destination changed during verification"
                )
            if destination_state == source_state:
                return destination
        if destination_stat is not None and not stat.S_ISDIR(destination_stat.st_mode):
            raise CapabilityInvocationError(
                f"visualization cache destination is not a directory: {destination}"
            )

        staging_parent = Path(tempfile.mkdtemp(prefix=f".{digest}.", dir=cache_parent)).resolve()
        staging = staging_parent / "pack"
        quarantined_original: Path | None = None
        quarantine_parent: Path | None = None
        try:
            shutil.copytree(source, staging)
            if _tree_state(staging) != source_state:
                raise CapabilityInvocationError(
                    "visualization cache source changed while it was being copied"
                )
            if destination.exists():
                # This digest-keyed directory is generated cache, not project
                # authority. Atomically quarantine the exact inode that was
                # inspected. A concurrent replacement is restored and rejected
                # rather than recursively deleted through a stale pathname.
                if destination_identity is None:
                    raise CapabilityInvocationError(
                        "visualization cache destination appeared during repair"
                    )
                quarantine_parent = Path(
                    tempfile.mkdtemp(prefix=f".corrupt-{digest}.", dir=cache_parent)
                ).resolve()
                quarantine = quarantine_parent / "pack"
                os.replace(destination, quarantine)
                quarantined = quarantine.lstat()
                if (quarantined.st_dev, quarantined.st_ino) != destination_identity:
                    if not destination.exists():
                        os.replace(quarantine, destination)
                        os.rmdir(quarantine_parent)
                    raise CapabilityInvocationError(
                        "visualization cache destination changed during repair; preserved replacement"
                    )
                # Keep the corrupt derived tree as a forensic quarantine. It
                # is never authority and, crucially, Astrid does not path-delete
                # it after a non-atomic identity check.
                quarantined_original = quarantine
            os.replace(staging, destination)
        except Exception:
            if quarantined_original is not None and not destination.exists():
                os.replace(quarantined_original, destination)
                if quarantine_parent is not None:
                    os.rmdir(quarantine_parent)
            raise
        finally:
            shutil.rmtree(staging_parent, ignore_errors=True)
    return destination


@contextmanager
def _visualization_cache_lock(path: Path):
    """Hold a persistent-inode exclusive lock for one cache digest."""

    try:
        import fcntl
    except ImportError as exc:  # pragma: no cover - frozen release matrix is POSIX
        raise CapabilityInvocationError(
            "durable visualization cache requires POSIX file locking"
        ) from exc
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise CapabilityInvocationError(
            f"cannot open visualization cache lock {path}: {exc}"
        ) from exc
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _resolve_projects_root(project_root: str | Path | None, project: str | None) -> Path:
    from astrid.core.foundation.project_paths import resolve_projects_root

    if project_root is not None:
        return Path(project_root).expanduser().resolve()
    try:
        return resolve_projects_root(None)
    except Exception:
        return Path.cwd().expanduser().resolve()


def _kernel_invoke(
    capability: Any,
    *,
    kind: Any,
    project: str | None,
    projects_root: Path,
    inputs: Mapping[str, Any] | None,
    outputs: Mapping[str, Any] | None,
    extra_pack_roots: tuple[str, ...] = (),
    idempotency_context: Mapping[str, Any] | None = None,
    registry: FrozenSchemaPackRegistry | None = None,
) -> tuple[str, str, str, Path | None, dict[str, Any], bool, Any]:
    """Real kernel admission: RunRepository.create with compute_spec_hash idempotency, claim/start, handler, execute/complete."""
    from astrid.core.events.service import EventAppendService
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
    from astrid.core.io.media_import import managed_media_path
    from astrid.core.kernel.read import schema_registry_context
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.media import MediaRepository
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.core.repositories.runs import RunRepository
    from astrid.core.repositories.tasks import TaskRepository, compute_spec_hash
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.store.writer import open_database_writer
    from astrid.core.task_executor import CapabilityTaskHandler, ExecutionService

    if registry is None:
        from astrid.core.schema_packs.standard import build_standard_registry

        registry = build_standard_registry()
    db_path = derive_database_path(projects_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer = open_database_writer(db_path, registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        runs = RunRepository(events=events, receipts=receipts)
        tasks = TaskRepository(events=events, receipts=receipts)
        projects = ProjectRepository(events=events, receipts=receipts)
        media_repo = MediaRepository(events=events, receipts=receipts, projects_root=projects_root)
        project_id = project if project else "default"
        try:
            UnitOfWork(writer).run(
                lambda u: projects.create(
                    u,
                    slug=project_id,
                    name=project_id,
                    settings={},
                    idempotency_key=f"proj:{project_id}",
                    project_id=project_id,
                )
            )
        except Exception:
            pass
        # Public SDK callers address projects by slug or id.  RunRepository
        # stores the canonical project id, so resolve the reference after the
        # idempotent create attempt rather than leaking a slug into runs.
        project_id = projects.resolve(writer, project_id)
        spec_payload = {
            "capability_id": capability.id,
            "inputs": dict(inputs or {}),
            "outputs": dict(outputs or {}),
            "project": project,
            "kind": str(kind),
            "extra_pack_roots": list(extra_pack_roots),
        }
        idempotency_payload = dict(spec_payload)
        if idempotency_context is not None:
            idempotency_payload["authority_context"] = dict(idempotency_context)
        authority_context = dict(idempotency_context or {})
        stored_executor_version = authority_context.get("executor_version")
        if not isinstance(stored_executor_version, str) or not stored_executor_version:
            stored_executor_version = None
        idempotency_key = compute_spec_hash(idempotency_payload, [])
        # Deterministic ids for idempotent replay: run_id derived from
        # idempotency_key so identical retry returns same run_id via receipt
        # (request_hash includes run_id). Child task_id also deterministic
        # so request identity is stable; receipt replay returns same ids.
        deterministic_run_id = hashlib.sha256(f"run:{idempotency_key}".encode()).hexdigest()[:26]
        deterministic_task_id = hashlib.sha256(f"task:{idempotency_key}:0".encode()).hexdigest()[
            :26
        ]
        child_spec = {
            "capability_id": capability.id,
            "inputs": dict(inputs or {}),
            "outputs": dict(outputs or {}),
            "project": project,
            "kind": str(kind),
            "extra_pack_roots": list(extra_pack_roots),
            "authority_context": authority_context,
        }

        def _create(u):
            return runs.create(
                u,
                project_id=project_id,
                children=[
                    {
                        "capability": capability.id,
                        "spec": child_spec,
                        "input_manifest": [],
                        "task_id": deterministic_task_id,
                    }
                ],
                idempotency_key=idempotency_key,
                kind=capability.capability_type,
                title=capability.id,
                input=child_spec,
                run_id=deterministic_run_id,
            )

        fanout = UnitOfWork(writer).run(_create)
        run_id = fanout.run_id
        task_id = fanout.task_ids[0] if fanout.task_ids else None
        if task_id is None:
            raise RuntimeError("kernel admission produced no task")
        # If run already terminal (idempotent replay after success), skip re-drive.
        # Query run status without receipt side-effects.
        try:
            row = UnitOfWork(writer).run(
                lambda u: u.query_one("SELECT status FROM runs WHERE id = ?", (run_id,))
            )
            if row is not None and row["status"] in ("succeeded", "failed", "cancelled"):
                # Derive winning attempt for stable return.
                trow = UnitOfWork(writer).run(
                    lambda u: u.query_one(
                        "SELECT winning_attempt_id, spec_json FROM tasks WHERE id = ?", (task_id,)
                    )
                )
                replay_executor_version = stored_executor_version
                if trow is not None:
                    try:
                        persisted_spec = json.loads(str(trow["spec_json"]))
                    except (TypeError, ValueError):
                        persisted_spec = None
                    persisted_context = (
                        persisted_spec.get("authority_context")
                        if isinstance(persisted_spec, Mapping)
                        else None
                    )
                    persisted_version = (
                        persisted_context.get("executor_version")
                        if isinstance(persisted_context, Mapping)
                        else None
                    )
                    if isinstance(persisted_version, str) and persisted_version:
                        replay_executor_version = persisted_version
                winning = (
                    trow["winning_attempt_id"]
                    if trow is not None and trow["winning_attempt_id"]
                    else f"{idempotency_key}:complete"
                )
                terminal_attempt = None
                if row["status"] != "succeeded":
                    terminal_attempt = UnitOfWork(writer).run(
                        lambda u: u.query_one(
                            "SELECT id, error_json FROM execution_attempts "
                            "WHERE task_id = ? AND status IN ('failed', 'cancelled') "
                            "ORDER BY attempt_no DESC LIMIT 1",
                            (task_id,),
                        )
                    )
                    if terminal_attempt is not None:
                        winning = str(terminal_attempt["id"])
                raw_result = {
                    "ok": row["status"] == "succeeded",
                    "run_id": run_id,
                    "kernel_run_id": run_id,
                    "kernel_task_id": task_id,
                    "kernel_attempt_id": winning,
                    "executor_version": replay_executor_version,
                }
                if row["status"] == "succeeded":
                    # Exact replay returns the durable stored output set, not
                    # an empty success envelope whose artifacts vanished with
                    # staging cleanup.
                    output_rows = UnitOfWork(writer).run(
                        lambda u: u.query(
                            "SELECT o.ordinal, o.role, o.is_primary, o.params_json, "
                            "m.id AS media_id, m.content_hash, l.locator "
                            "FROM task_outputs o JOIN media m ON m.id = o.media_id "
                            "JOIN media_locations l ON l.media_id = m.id "
                            "AND l.realm = 'managed_local' "
                            "WHERE o.task_id = ? ORDER BY o.ordinal ASC",
                            (task_id,),
                        )
                    )
                    artifacts: list[dict[str, Any]] = []
                    mpath = None
                    for output_row in output_rows:
                        try:
                            params = json.loads(str(output_row["params_json"]))
                        except (TypeError, ValueError):
                            params = {}
                        label = params.get("label") if isinstance(params, Mapping) else None
                        locator = str(output_row["locator"])
                        artifact = {
                            "path": locator,
                            "label": label,
                            "role": str(output_row["role"]),
                            "is_primary": bool(output_row["is_primary"]),
                            "media_id": str(output_row["media_id"]),
                            "content_hash": str(output_row["content_hash"]),
                        }
                        artifacts.append(artifact)
                        if label == "manifest.json":
                            mpath = Path(locator)
                    raw_result["outputs"] = {"artifacts": artifacts}
                    return (
                        run_id,
                        task_id,
                        winning,
                        mpath,
                        raw_result,
                        row["status"] == "succeeded",
                        None,
                    )
                if terminal_attempt is not None:
                    try:
                        terminal_error = json.loads(str(terminal_attempt["error_json"]))
                    except (TypeError, ValueError):
                        terminal_error = None
                    if isinstance(terminal_error, Mapping):
                        raw_result["error"] = dict(terminal_error)
                return run_id, task_id, winning, None, raw_result, False, None
        except Exception:
            pass
        claim_key = f"{idempotency_key}:claim"
        claim = UnitOfWork(writer).run(
            lambda u: tasks.claim(u, project_id=project_id, idempotency_key=claim_key)
        )
        if claim is None:
            # Idempotent replay after task already succeeded but run not yet
            # marked terminal (task succeeded before run derived status).
            raw_result: dict[str, Any] = {
                "ok": True,
                "run_id": run_id,
                "kernel_run_id": run_id,
                "kernel_task_id": task_id,
                "kernel_attempt_id": claim_key,
                "executor_version": stored_executor_version,
            }
            return run_id, task_id, claim_key, None, raw_result, True, None
        handler = CapabilityTaskHandler(
            capability_kind=capability.capability_type,
            capability_id=capability.id,
            projects_root=projects_root,
        )
        svc = ExecutionService(projects_root=projects_root, task_repo=tasks)
        with schema_registry_context(registry):
            exec_res = svc.execute(
                UnitOfWork(writer),
                project_id=project_id,
                task_id=claim.task.id,
                attempt_id=claim.attempt.id,
                lease_id=claim.attempt.lease_id,
                expected_status_version=claim.attempt.status_version,
                idempotency_key=f"{idempotency_key}:exec",
                handler=handler,
            )
        if exec_res.outcome == "failed":
            raw_result: dict[str, Any] = {
                "ok": False,
                "run_id": run_id,
                "kernel_run_id": run_id,
                "kernel_task_id": task_id,
                "kernel_attempt_id": claim.attempt.id,
                "error": exec_res.error,
                "executor_version": stored_executor_version,
            }
            return run_id, task_id, claim.attempt.id, None, raw_result, False, None
        if exec_res.outcome == "cancelled":
            raw_result = {
                "ok": False,
                "run_id": run_id,
                "kernel_run_id": run_id,
                "kernel_task_id": task_id,
                "kernel_attempt_id": claim.attempt.id,
                "error": exec_res.error
                or {
                    "reason": "cancelled",
                    "message": "operator cancellation won; no artifact was published",
                },
                "executor_version": stored_executor_version,
            }
            return run_id, task_id, claim.attempt.id, None, raw_result, False, None
        assert exec_res.prepared is not None
        prepared = exec_res.prepared
        with schema_registry_context(registry):
            comp = svc.complete(
                UnitOfWork(writer),
                prepared=prepared,
                media_repo=media_repo,
                idempotency_key=f"{idempotency_key}:complete",
            )
        ok = comp.outcome == "completed"
        # A kernel invocation has no durable filesystem run root. The attempt
        # directory is a private publication fence and is removed after CAS
        # completion; exposing it as ``run_root`` leaves callers holding a
        # path that is guaranteed to be stale. Durable locators are returned
        # under outputs.artifacts instead.
        raw_result = {
            "ok": ok,
            "run_id": run_id,
            "kernel_run_id": run_id,
            "kernel_task_id": task_id,
            "kernel_attempt_id": prepared.attempt.id,
            "executor_version": stored_executor_version,
        }
        if comp.outcome != "completed":
            raw_result["error"] = dict(
                comp.error
                or {
                    "reason": "cancelled",
                    "message": "operator cancellation won; no artifact was published",
                }
            )
        durable_manifest_path = None
        if comp.completed is not None:
            # The universal manifest is intentionally held in the kernel
            # completion boundary rather than written as a second authority.
            # Return its ordered media identities and staged paths without
            # pretending the first artifact is a JSON manifest (rendering
            # outputs are commonly MP4s, with a provenance sidecar alongside).
            artifacts: list[dict[str, Any]] = []
            for prepared_output, stored_output in zip(prepared.outputs, comp.completed.outputs):
                digest = (
                    prepared_output.prepared.digest
                    if prepared_output.prepared is not None
                    else None
                )
                # The staging tree is an execution detail and is cleaned up
                # after terminal completion. Return the managed digest path
                # for materialized media so callers can open the artifact
                # after the invocation has finished.
                durable_path = (
                    str(managed_media_path(projects_root, digest)) if digest is not None else None
                )
                artifact: dict[str, Any] = {
                    "path": durable_path,
                    "label": prepared_output.label,
                    "role": stored_output.role,
                    "is_primary": stored_output.is_primary,
                    "media_id": stored_output.media_id,
                    "content_hash": digest,
                }
                if prepared_output.label == "manifest.json" and durable_path is not None:
                    durable_manifest_path = Path(durable_path)
                requested_name = inputs.get("output_name") if isinstance(inputs, Mapping) else None
                if isinstance(requested_name, str) and requested_name:
                    artifact["requested_output_name"] = requested_name
                artifacts.append(artifact)
            raw_result["outputs"] = {"artifacts": artifacts}
        mpath = None
        # CapabilityTaskHandler returns an in-memory universal manifest. If an
        # executor produced its own manifest, expose the durable managed media
        # locator rather than the execution-only staging path.
        if durable_manifest_path is not None:
            mpath = durable_manifest_path
        # A successful completion has materialized every output into managed
        # media; the exact generated staging directory is no longer live and
        # can be removed. Failed handlers already clean their staging in
        # ExecutionService.execute. Leave a non-completed/stale completion
        # quarantined for startup GC because another worker may still own it.
        if comp.outcome in ("completed", "losing"):
            svc.cleanup_staging(prepared.staging_dir)
        return run_id, task_id, prepared.attempt.id, mpath, raw_result, ok, None
    finally:
        try:
            writer.close()
        except Exception:
            pass


def invoke(
    capability_id: str,
    *,
    kind: Any,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
    out: Path | str | None = None,
    project: str | None = None,
    inputs: Mapping[str, Any] | None = None,
    outputs: Mapping[str, Any] | None = None,
    brief: Path | str | None = None,
    dry_run: bool = False,
    check_binaries: bool = False,
    python_exec: str | None = None,
    verbose: bool = False,
    execution_mode: str = "subprocess",
    argv: tuple[str, ...] = (),
    orchestrator_args: tuple[str, ...] = (),
    registry: FrozenSchemaPackRegistry | None = None,
    _client: Any | None = None,
) -> InvocationResult:
    sdk_module = _sdk_module()
    include_elements = kind == "element"
    registries = sdk_module._load_registries(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        include_elements=include_elements,
    )
    capability = sdk_module.get_capability(
        capability_id,
        kind=kind,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        _registries=registries,
    )
    if capability.capability_type == "element":
        raise UnsupportedCapabilityError(f"elements are not invokable via the SDK: {capability.id}")

    # Validate the public selector/format contract before the runner can
    # create a ledger row or spawn a subprocess.  The runner repeats these
    # checks for direct CLI callers, but SDK callers should get the same
    # actionable typed error at admission time.
    invocation_authority_context: dict[str, Any] | None = None
    if capability.id == "rendering.timeline_visualize":
        invocation_authority_context = _validate_timeline_visualize_inputs(
            inputs,
            project=project,
            project_root=project_root,
            out=out,
        )
    elif capability.id == "rendering.render":
        inputs, invocation_authority_context = _prepare_managed_render_inputs(
            inputs,
            project=project,
            project_root=project_root,
            _client=_client,
        )

    # Generation requests have a single read-only preflight for both dry-run
    # and live invocation.  This keeps generic ``sdk.invoke`` from accepting
    # an impossible model/mode/backend cell (or FLF request missing its end
    # frame) and discovering the problem only after kernel admission.
    generation_modalities = {
        "generation.generate_image": "image",
        "generation.generate_video": "video",
        "generation.generate_audio": "audio",
    }
    modality = generation_modalities.get(capability.id)
    if modality is not None:
        request_inputs = dict(inputs or {})
        model_registry = sdk_module._load_model_registry(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        )
        from astrid.core.generation.preflight import (
            require_local_generation_readiness,
            validate_generation_request,
        )

        model_entry, _mode_spec = validate_generation_request(
            model_registry,
            model=request_inputs.get("model"),
            mode=request_inputs.get("mode"),
            execution=request_inputs.get("execution"),
            inputs=request_inputs,
            modality=modality,
        )
        if request_inputs.get("execution") == "local":
            require_local_generation_readiness(
                model_entry,
                request_inputs["mode"],
                python_executable=python_exec,
            )

    # Ledger exemption: dry_run never admitted
    if dry_run:
        try:
            if capability.capability_type == "executor":
                from astrid.core.execution.executor.runner import ExecutorRunRequest

                executor_registry, _, _ = registries
                request = ExecutorRunRequest(
                    executor_id=capability.id,
                    out=out,
                    project=project,
                    inputs=dict(inputs or {}),
                    outputs=dict(outputs or {}),
                    brief=brief,
                    dry_run=True,
                    check_binaries=check_binaries,
                    python_exec=python_exec,
                    verbose=verbose,
                    execution_mode=execution_mode,
                    argv=tuple(argv),
                    invocation="sdk",
                    projects_root=project_root,
                )
                with redirect_stdout(StringIO()):
                    result = sdk_module.run_executor(request, executor_registry)
                raw_result = _normalize_executor_result(result)
            else:
                from astrid.core.execution.orchestrator.runner import OrchestratorRunRequest

                _, orchestrator_registry, _ = registries
                request = OrchestratorRunRequest(
                    orchestrator_id=capability.id,
                    out=out,
                    project=project,
                    inputs=dict(inputs or {}),
                    outputs=dict(outputs or {}),
                    brief=brief,
                    orchestrator_args=tuple(orchestrator_args),
                    dry_run=True,
                    python_exec=python_exec,
                    verbose=verbose,
                    execution_mode=execution_mode,
                    invocation="sdk",
                    projects_root=project_root,
                )
                with redirect_stdout(StringIO()):
                    result = sdk_module.run_orchestrator(request, orchestrator_registry)
                raw_result = _normalize_orchestrator_result(result)
        except AstridSDKError:
            raise
        except Exception as exc:
            mapped = _sdk_error_from_exception(exc)
            if mapped is not None:
                raise mapped from exc
            raise CapabilityInvocationError(
                f"failed to invoke {capability.capability_type} {capability.id!r}"
            ) from exc
        internal_error = _internal_error_from_result(result)
        error = (
            _error_payload_from_internal_error(internal_error, json_safe=_json_safe)
            if internal_error is not None
            else None
        )
        manifest_path = _discover_invocation_manifest_path(raw_result, out=out)
        run_id_raw = raw_result.get("run_id")
        run_root_raw = raw_result.get("run_root")
        executor_version_raw = raw_result.get("executor_version")
        return InvocationResult(
            capability_id=capability.id,
            capability_type=capability.capability_type,
            native_kind=capability.native_kind,
            ok=bool(getattr(result, "ok", False)),
            error=error,
            manifest_path=manifest_path,
            raw_result=raw_result,
            run_id=run_id_raw if isinstance(run_id_raw, str) and run_id_raw else None,
            run_root=str(Path(run_root_raw).expanduser().resolve())
            if isinstance(run_root_raw, str) and run_root_raw
            else None,
            outputs=_invocation_outputs(
                raw_result,
                manifest_path=manifest_path,
                project_root=(
                    (_resolve_projects_root(project_root, project) / project).resolve()
                    if project is not None
                    else None
                ),
                capability_id=capability.id,
            ),
            executor_version=executor_version_raw
            if isinstance(executor_version_raw, str) and executor_version_raw
            else None,
            kernel_run_id=None,
            kernel_task_id=None,
            kernel_attempt_id=None,
        )

    # Real kernel admission path — no fallback; failures raise CapabilityInvocationError.
    # Project is required: mirror runner's selected_project check so missing
    # project maps to CapabilityValidationError (not silent default).
    from astrid.core.project.guidance import format_project_required_guidance, selected_project

    resolved_project, _src = selected_project(project)
    if resolved_project is None:
        raise CapabilityValidationError(
            format_project_required_guidance(operation=f"{capability.capability_type} run")
        )
    # Use resolved project (handles auto-resolved via selected_project)
    project = resolved_project
    projects_root = _resolve_projects_root(project_root, project)
    kernel_capability_version: str | None = None
    if capability.capability_type == "executor":
        from astrid.core.io.cas import executor_definition_digest

        executor_registry, _, _ = registries
        kernel_capability_version = executor_definition_digest(executor_registry.get(capability.id))
        invocation_authority_context = dict(invocation_authority_context or {})
        invocation_authority_context["executor_version"] = kernel_capability_version
    try:
        # Keep the private seam backwards-compatible for callers that replace
        # it with a narrow test double, while still forwarding an explicitly
        # composed registry for long-lived clients.  ``None`` means the
        # kernel will build its normal standard composition; passing it as a
        # keyword adds no information and needlessly breaks older doubles.
        kernel_kwargs: dict[str, Any] = {
            "kind": kind,
            "project": project,
            "projects_root": projects_root,
            "inputs": inputs,
            "outputs": outputs,
            "extra_pack_roots": extra_pack_roots,
            "idempotency_context": invocation_authority_context,
        }
        if registry is not None:
            kernel_kwargs["registry"] = registry
        kr, kt, ka, mpath, raw_result, ok, _ = _kernel_invoke(
            capability,
            **kernel_kwargs,
        )
        run_id_raw = raw_result.get("run_id") if isinstance(raw_result, dict) else None
        run_root_raw = raw_result.get("run_root") if isinstance(raw_result, dict) else None
        raw_result = dict(raw_result) if isinstance(raw_result, dict) else {}
        if kernel_capability_version is not None:
            raw_result.setdefault("executor_version", kernel_capability_version)
        executor_version_raw = raw_result.get("executor_version")
        raw_result.setdefault("kernel_run_id", kr)
        raw_result.setdefault("kernel_task_id", kt)
        raw_result.setdefault("kernel_attempt_id", ka)
        manifest_path = (
            str(mpath) if mpath else _discover_invocation_manifest_path(raw_result, out=out)
        )
        return InvocationResult(
            capability_id=capability.id,
            capability_type=capability.capability_type,
            native_kind=capability.native_kind,
            ok=ok,
            # Preserve the kernel's typed handler failure on the primary
            # result surface.  Historically this was only available under
            # ``raw_result.error`` and task events, forcing callers to make a
            # second ledger query to understand a failed invocation.
            error=(
                {
                    **dict(raw_result.get("error")),
                    "sdk_error": "CapabilityRuntimeError",
                    "sdk_category": "runtime",
                }
                if isinstance(raw_result.get("error"), Mapping)
                else None
            ),
            manifest_path=manifest_path,
            raw_result=raw_result,
            run_id=run_id_raw if isinstance(run_id_raw, str) and run_id_raw else kr,
            # Kernel-managed invocations publish through private staging and
            # then remove it. Only propagate a run_root explicitly supplied
            # by a durable/custom kernel result; never synthesize the projects
            # root or leak the attempt staging path.
            run_root=(
                str(Path(run_root_raw).expanduser().resolve())
                if isinstance(run_root_raw, str) and run_root_raw
                else None
            ),
            outputs=_invocation_outputs(
                raw_result,
                manifest_path=manifest_path,
                project_root=(projects_root / project).resolve(),
                capability_id=capability.id,
            ),
            executor_version=executor_version_raw
            if isinstance(executor_version_raw, str) and executor_version_raw
            else None,
            kernel_run_id=kr,
            kernel_task_id=kt,
            kernel_attempt_id=ka,
        )
    except AstridSDKError:
        raise
    except Exception as exc:
        mapped = _sdk_error_from_exception(exc)
        if mapped is not None:
            raise mapped from exc
        raise CapabilityInvocationError(
            f"failed to invoke {capability.capability_type} {capability.id!r}"
        ) from exc


def invoke_result(
    capability_id: str,
    *,
    kind: Any,
    **kwargs: Any,
) -> InvocationResult:
    """Invoke while keeping typed preflight failures in the result contract.

    ``invoke`` remains the exception-oriented API for callers that want typed
    recovery branches.  Maker-facing agents that need one uniform JSON-safe
    branch can use this sibling: validation/precondition failures raised before
    kernel admission become an ``InvocationResult(ok=False)`` with the same
    ``error`` mapping used by a post-admission failure.  No run, task, staging
    directory, network call, or provider request is created by this adapter.
    """

    try:
        return invoke(capability_id, kind=kind, **kwargs)
    except AstridSDKError as exc:
        category = getattr(exc, "category", "invocation")
        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "sdk_error": type(exc).__name__,
            "sdk_category": category,
        }
        details = getattr(exc, "details", None)
        if isinstance(details, Mapping) and details:
            error["validation"] = _json_safe(dict(details))
        return InvocationResult(
            capability_id=capability_id,
            capability_type=kind if kind in ("executor", "orchestrator") else "executor",
            native_kind="unknown",
            ok=False,
            error=error,
            raw_result={"ok": False, "error": error},
        )
