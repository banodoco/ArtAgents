"""Project file schemas and validators (project / source / run only).

The parallel placement schema (build_project_timeline / build_placement /
validate_project_timeline / validate_placement / validate_reference / REF_KINDS
/ source_ref / run_ref / TIMELINE_SCHEMA_VERSION) was removed when AA collapsed
onto reigh-app's canonical ``timelines`` rows. Timeline reads/writes now go
through ``astrid.core.reigh.SupabaseDataProvider`` as a legacy compatibility
bridge; the local provenance cache (sources/, runs/, project.json) is what
survives.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from astrid.contracts.errors import AstridError
from astrid.contracts.run_status import RunStatus
from astrid.contracts.schema_validators import require_uuid_str
from astrid.core.util.time import utc_now_seconds

from .paths import validate_project_slug, validate_run_id, validate_source_id

PROJECT_SCHEMA_VERSION = 1
SOURCE_SCHEMA_VERSION = 1
RUN_SCHEMA_VERSION = 1
SOURCE_KINDS = {"audio", "image", "other", "video"}
RUN_STATUSES = {status.value for status in RunStatus}
RUN_INVOCATIONS = {"cli", "sdk", "scratch", "task"}


class ProjectValidationError(AstridError, ValueError):
    """Raised when project state fails validation."""

    def __init__(self, cause: str) -> None:
        super().__init__(cause)
def build_project(
    slug: str,
    *,
    name: str | None = None,
    project_id: str | None = None,
    theme: str | None = None,
    created_at: str | None = None,
    default_timeline_id: str | None = None,
) -> dict[str, Any]:
    now = created_at or utc_now_seconds()
    slug = validate_project_slug(slug)
    payload: dict[str, Any] = {
        "created_at": now,
        # Sprint 1 sentinel: Sprint 2 will populate this when timelines become a
        # first-class container; emitted even when None so the field is
        # discoverable.
        "default_timeline_id": _validate_default_timeline_id(default_timeline_id),
        "name": name or slug,
        "schema_version": PROJECT_SCHEMA_VERSION,
        "slug": slug,
        "updated_at": now,
    }
    if project_id is not None:
        payload["project_id"] = _require_string(project_id, "project.project_id")
    if theme is not None:
        payload["theme"] = validate_project_slug(theme)
    return payload


def build_source(
    project_slug: str,
    source_id: str,
    *,
    asset: dict[str, Any],
    kind: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    now = created_at or utc_now_seconds()
    normalized_asset = _normalize_asset(asset, path="source.asset")
    return {
        "asset": normalized_asset,
        "created_at": now,
        "kind": validate_source_kind(kind or _infer_source_kind(normalized_asset), path="source.kind"),
        "metadata": dict(metadata or {}),
        "project_slug": validate_project_slug(project_slug),
        "schema_version": SOURCE_SCHEMA_VERSION,
        "source_id": validate_source_id(source_id),
        "updated_at": now,
    }


def build_run_record(
    project_slug: str,
    run_id: str,
    *,
    tool_id: str | None = None,
    kind: str | None = None,
    status: str | RunStatus = RunStatus.RUNNING,
    out: str | Path | None = None,
    argv: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
    created_at: str | None = None,
    session_id: str | None = None,
    auto_bound: bool | None = None,
    invocation: str = "cli",
    timeline_id: str | None = None,
    timeline_slug: str | None = None,
    timeline_event_stream_id: str | None = None,
    timeline_binding_mode: str | None = None,
) -> dict[str, Any]:
    now = created_at or utc_now_seconds()
    merged_metadata = dict(metadata or {})
    legacy_auto_bound = merged_metadata.get("project_was_auto_resolved")
    if auto_bound is None and legacy_auto_bound is not None:
        auto_bound = _require_bool(legacy_auto_bound, "run.metadata.project_was_auto_resolved")
    elif auto_bound is not None:
        merged_metadata.pop("project_was_auto_resolved", None)
    if timeline_slug is not None:
        merged_metadata["timeline_slug"] = timeline_slug
    if timeline_event_stream_id is not None:
        merged_metadata["timeline_event_stream_id"] = timeline_event_stream_id
    if timeline_binding_mode is not None:
        merged_metadata["timeline_binding_mode"] = timeline_binding_mode
    payload: dict[str, Any] = {
        "auto_bound": bool(auto_bound) if auto_bound is not None else False,
        "artifacts": dict(artifacts or {}),
        "created_at": now,
        "invocation": _validate_run_invocation(invocation),
        "metadata": merged_metadata,
        "project_slug": validate_project_slug(project_slug),
        "run_id": validate_run_id(run_id),
        "schema_version": RUN_SCHEMA_VERSION,
        "session_id": _optional_string(session_id, "run.session_id"),
        "status": _normalize_run_record_status(status),
        "updated_at": now,
    }
    if tool_id is not None:
        payload["tool_id"] = _require_string(tool_id, "run.tool_id")
    if kind is not None:
        payload["kind"] = _require_string(kind, "run.kind")
    if out is not None:
        payload["out"] = str(out)
    if argv is not None:
        payload["argv"] = [_require_string(item, "run.argv[]") for item in argv]
    if timeline_id is not None:
        from astrid.core.timeline.paths import validate_timeline_ulid
        payload["timeline_id"] = validate_timeline_ulid(timeline_id)
    return validate_run_record(payload)


def validate_project(raw: Any) -> dict[str, Any]:
    data = _require_mapping(raw, "project")
    _require_version(data, PROJECT_SCHEMA_VERSION, "project")
    slug = validate_project_slug(_require_string(data.get("slug"), "project.slug"))
    name = _require_string(data.get("name"), "project.name")
    created_at = _require_string(data.get("created_at"), "project.created_at")
    updated_at = _require_string(data.get("updated_at"), "project.updated_at")
    payload = dict(data)
    payload.update({"created_at": created_at, "name": name, "slug": slug, "updated_at": updated_at})
    if "project_id" in payload:
        if payload["project_id"] is None:
            payload.pop("project_id")
        else:
            payload["project_id"] = _require_string(payload["project_id"], "project.project_id")
    if "theme" in payload:
        if payload["theme"] is None:
            payload.pop("theme")
        else:
            payload["theme"] = validate_project_slug(_require_string(payload["theme"], "project.theme"))
    if "default_timeline_id" in payload:
        payload["default_timeline_id"] = _validate_default_timeline_id(
            payload["default_timeline_id"]
        )
    return payload


def validate_source(raw: Any) -> dict[str, Any]:
    data = _require_mapping(raw, "source")
    _require_version(data, SOURCE_SCHEMA_VERSION, "source")
    payload = dict(data)
    payload.update(
        {
            "asset": _normalize_asset(data.get("asset"), path="source.asset"),
            "kind": validate_source_kind(data.get("kind"), path="source.kind"),
            "metadata": _optional_mapping(data.get("metadata", {}), "source.metadata"),
            "project_slug": validate_project_slug(_require_string(data.get("project_slug"), "source.project_slug")),
            "schema_version": SOURCE_SCHEMA_VERSION,
            "source_id": validate_source_id(_require_string(data.get("source_id"), "source.source_id")),
        }
    )
    payload.setdefault("created_at", utc_now_seconds())
    payload.setdefault("updated_at", payload["created_at"])
    return payload


def validate_run_record(raw: Any) -> dict[str, Any]:
    data = _require_mapping(raw, "run")
    _require_version(data, RUN_SCHEMA_VERSION, "run")
    status = _normalize_run_record_status(data.get("status"))
    payload = dict(data)
    metadata = _optional_mapping(data.get("metadata", {}), "run.metadata")
    legacy_auto_bound = metadata.get("project_was_auto_resolved")
    auto_bound = data.get("auto_bound")
    if auto_bound is None and legacy_auto_bound is not None:
        auto_bound = _require_bool(legacy_auto_bound, "run.metadata.project_was_auto_resolved")
    payload.update(
        {
            "auto_bound": _require_bool(auto_bound if auto_bound is not None else False, "run.auto_bound"),
            "artifacts": _optional_mapping(data.get("artifacts", {}), "run.artifacts"),
            "invocation": _validate_run_invocation(data.get("invocation", "cli")),
            "metadata": metadata,
            "project_slug": validate_project_slug(_require_string(data.get("project_slug"), "run.project_slug")),
            "run_id": validate_run_id(_require_string(data.get("run_id"), "run.run_id")),
            "schema_version": RUN_SCHEMA_VERSION,
            "session_id": _optional_string(data.get("session_id"), "run.session_id"),
            "status": status,
        }
    )
    if "argv" in payload:
        argv = payload["argv"]
        if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
            raise ProjectValidationError("run.argv must be a list of strings")
    if "manifest_path" in payload:
        manifest_path = payload["manifest_path"]
        if manifest_path is None:
            payload.pop("manifest_path")
        else:
            payload["manifest_path"] = _require_string(manifest_path, "run.manifest_path")
    if "timeline_id" in payload:
        tid = payload["timeline_id"]
        if tid is None:
            payload.pop("timeline_id")
        else:
            from astrid.core.timeline.paths import validate_timeline_ulid
            payload["timeline_id"] = validate_timeline_ulid(tid)
    # Validate managed timeline binding metadata sub-keys (m3.5).
    meta = payload.get("metadata", {})
    if isinstance(meta, dict):
        if "timeline_slug" in meta:
            from astrid.core.timeline.paths import validate_timeline_slug
            meta["timeline_slug"] = validate_timeline_slug(meta["timeline_slug"])
        if "timeline_event_stream_id" in meta:
            meta["timeline_event_stream_id"] = _require_uuid_str(
                meta["timeline_event_stream_id"], "run.metadata.timeline_event_stream_id"
            )
        if "timeline_binding_mode" in meta:
            mode = meta["timeline_binding_mode"]
            if mode not in ("managed", "unmanaged"):
                raise ProjectValidationError(
                    f"run.metadata.timeline_binding_mode must be 'managed' or 'unmanaged', got {mode!r}"
                )
        payload["metadata"] = meta
    payload.setdefault("created_at", utc_now_seconds())
    payload.setdefault("updated_at", payload["created_at"])
    return payload


def _normalize_run_record_status(raw: Any) -> str:
    if isinstance(raw, RunStatus):
        return raw.value
    status = _require_string(raw, "run.status")
    try:
        return RunStatus.from_run_record_status(status).value
    except ValueError as exc:
        raise ProjectValidationError(str(exc)) from None


def validate_source_kind(raw: Any, *, path: str = "source.kind") -> str:
    kind = _require_string(raw, path)
    if kind not in SOURCE_KINDS:
        raise ProjectValidationError(f"{path} must be one of {sorted(SOURCE_KINDS)}")
    return kind


def _infer_source_kind(asset: dict[str, Any]) -> str:
    asset_type = asset.get("type")
    if isinstance(asset_type, str):
        if asset_type.startswith("video/"):
            return "video"
        if asset_type.startswith("audio/"):
            return "audio"
        if asset_type.startswith("image/"):
            return "image"
    return "other"


def _normalize_asset(raw: Any, *, path: str) -> dict[str, Any]:
    data = _require_mapping(raw, path)
    has_file = isinstance(data.get("file"), str) and bool(data.get("file"))
    has_url = isinstance(data.get("url"), str) and bool(data.get("url"))
    if has_file == has_url:
        raise ProjectValidationError(f"{path} must contain exactly one of file or url")
    payload = dict(data)
    if has_file:
        payload["file"] = str(Path(payload["file"]).expanduser().resolve())
        payload.pop("url", None)
    else:
        payload["url"] = payload["url"]
        payload.pop("file", None)
    return payload


def _validate_default_timeline_id(raw: Any) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ProjectValidationError("project.default_timeline_id must be a ULID string or null")
    try:
        from astrid.core.timeline.paths import validate_timeline_ulid
        return validate_timeline_ulid(raw)
    except ValueError as exc:
        raise ProjectValidationError(f"project.default_timeline_id: {exc}") from exc


def _require_version(data: dict[str, Any], expected: int, path: str) -> None:
    if data.get("schema_version") != expected:
        raise ProjectValidationError(f"{path}.schema_version must be {expected}")


def _require_mapping(raw: Any, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProjectValidationError(f"{path} must be an object")
    return raw


def _optional_mapping(raw: Any, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProjectValidationError(f"{path} must be an object")
    return dict(raw)


def _require_string(raw: Any, path: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise ProjectValidationError(f"{path} must be a non-empty string")
    return raw


def _require_number(raw: Any, path: str) -> int | float:
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        raise ProjectValidationError(f"{path} must be a number")
    return raw


def _require_bool(raw: Any, path: str) -> bool:
    if not isinstance(raw, bool):
        raise ProjectValidationError(f"{path} must be a boolean")
    return raw


def _optional_string(raw: Any, path: str) -> str | None:
    if raw is None:
        return None
    return _require_string(raw, path)


def _validate_run_invocation(raw: Any) -> str:
    invocation = _require_string(raw, "run.invocation")
    if invocation not in RUN_INVOCATIONS:
        raise ProjectValidationError(f"run.invocation must be one of {sorted(RUN_INVOCATIONS)}")
    return invocation


def _require_uuid_str(value: object, field: str) -> str:
    return require_uuid_str(value, field, ProjectValidationError)
