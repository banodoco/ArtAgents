"""Project and source file schemas and validators."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.core.contracts.errors import AstridError
from astrid.core.contracts.identifiers import validate_timeline_ulid
from astrid.core.contracts.project_theme import validate_theme_identifier
from astrid.core.foundation.project_paths import (
    validate_project_slug,
    validate_source_id,
)
from astrid.core.util.time import utc_now_seconds

PROJECT_SCHEMA_VERSION = 1
SOURCE_SCHEMA_VERSION = 1
SOURCE_KINDS = {"audio", "image", "other", "video"}


class ProjectValidationError(AstridError, ValueError):
    """Raised when project state fails validation."""

    def __init__(self, cause: str) -> None:
        super().__init__(cause)


def build_project(
    slug: str,
    *,
    name: str | None = None,
    description: str | None = None,
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
    if description is not None:
        payload["description"] = _require_string(description, "project.description")
    if theme is not None:
        payload["theme"] = validate_theme_identifier(theme)
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


def validate_project(raw: Any) -> dict[str, Any]:
    data = _require_mapping(raw, "project")
    _require_version(data, PROJECT_SCHEMA_VERSION, "project")
    slug = validate_project_slug(_require_string(data.get("slug"), "project.slug"))
    name = _require_string(data.get("name"), "project.name")
    created_at = _require_string(data.get("created_at"), "project.created_at")
    updated_at = _require_string(data.get("updated_at"), "project.updated_at")
    payload = dict(data)
    payload.update({"created_at": created_at, "name": name, "slug": slug, "updated_at": updated_at})
    if "description" in payload:
        if payload["description"] is None:
            payload.pop("description")
        else:
            payload["description"] = _require_string(
                payload["description"], "project.description"
            )
    if "project_id" in payload:
        if payload["project_id"] is None:
            payload.pop("project_id")
        else:
            payload["project_id"] = _require_string(payload["project_id"], "project.project_id")
    if "theme" in payload:
        if payload["theme"] is None:
            payload.pop("theme")
        else:
            payload["theme"] = validate_theme_identifier(
                _require_string(payload["theme"], "project.theme")
            )
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
    if "duration" in payload:
        dur = payload["duration"]
        if not isinstance(dur, (int, float)) or isinstance(dur, bool):
            raise ProjectValidationError(
                f"{path}.duration must be a finite positive number, got {dur!r}"
            )
        import math
        if not (math.isfinite(dur) and dur > 0):
            raise ProjectValidationError(
                f"{path}.duration must be a finite positive number, got {dur!r}"
            )
    return payload


def _validate_default_timeline_id(raw: Any) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ProjectValidationError("project.default_timeline_id must be a ULID string or null")
    try:
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
