"""Canonical kernel timeline resolution for the explicit managed render mode."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from astrid.core import timeline
from astrid.core._shared.jsonio import write_json_atomic
from astrid.core.io.managed_media_resolver import (
    rebase_timeline_registry_managed_assets,
)


class ManagedRenderValidationError(ValueError):
    """Actionable, JSON-safe pre-admission failure for a managed render."""

    def __init__(
        self,
        message: str,
        *,
        path: str,
        reason: str,
        recovery: str,
        validator: str | None = None,
        schema_path: str | None = None,
    ) -> None:
        super().__init__(message)
        details: dict[str, Any] = {
            "path": path,
            "reason": reason,
            "recovery": recovery,
        }
        if validator:
            details["validator"] = validator
        if schema_path:
            details["schema_path"] = schema_path
        self.details = details


def _json_path(parts: Any) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        elif isinstance(part, str) and part.isidentifier():
            path += f".{part}"
        else:
            path += f"[{json.dumps(str(part), ensure_ascii=True)}]"
    return path


def _schema_validation_error(
    snapshot: "ManagedRenderSnapshot", exc: Exception
) -> ManagedRenderValidationError:
    absolute_path = getattr(exc, "absolute_path", ())
    absolute_schema_path = getattr(exc, "absolute_schema_path", ())
    path = _json_path(absolute_path)
    reason = str(getattr(exc, "message", None) or exc).strip().splitlines()[0]
    validator = getattr(exc, "validator", None)
    recovery = f"Fix {path} to match the canonical timeline schema, then retry."
    if ".effects" in path or "'effects'" in reason:
        recovery = (
            "Use clip.effects only for fade timing (fade_in/fade_out, or a numeric "
            "fade map). Reference a reusable visual element with clipType:<effect-id> "
            "and params:{...}, then retry."
        )
    message = (
        f"canonical timeline {snapshot.timeline_slug!r} is not renderable at {path}: "
        f"{reason}. Recovery: {recovery}"
    )
    return ManagedRenderValidationError(
        message,
        path=path,
        reason=reason,
        recovery=recovery,
        validator=str(validator) if validator is not None else None,
        schema_path=_json_path(absolute_schema_path) if absolute_schema_path else None,
    )


def _validate_render_element_clip_types(
    snapshot: "ManagedRenderSnapshot", config: Mapping[str, Any]
) -> None:
    """Fail closed for clip types that the managed renderer would drop/fail on.

    The authoring schema deliberately keeps ``clipType`` open for compatibility.
    Canonical render admission is stricter: every non-built-in spelling is a
    reusable visual-element reference and must resolve in the active catalog.
    Opaque data inside ``params``/``generation`` is intentionally not scanned.
    """

    from astrid.core.element import catalog as element_catalog

    theme = config.get("theme")
    active_theme = theme if isinstance(theme, str) and theme else None
    effect_ids = set(element_catalog.list_effect_ids(theme=active_theme))
    aliases = {"text"} if "text-card" in effect_ids else set()
    for effect_id in effect_ids:
        metadata = element_catalog.read_effect_meta(effect_id, theme=active_theme)
        raw_aliases = metadata.get("clipTypeAliases")
        if isinstance(raw_aliases, list):
            aliases.update(alias for alias in raw_aliases if isinstance(alias, str) and alias)
    builtins = {"media", "video", "image", "audio", "effect-layer"}
    known = builtins | effect_ids | aliases
    for index, clip in enumerate(config.get("clips", [])):
        if not isinstance(clip, Mapping):
            continue
        clip_type = clip.get("clipType", "media")
        if not isinstance(clip_type, str) or clip_type in known:
            continue
        path = f"$.clips[{index}].clipType"
        available = ", ".join(sorted(effect_ids)) or "none installed"
        reason = f"unregistered reusable visual element id {clip_type!r}"
        recovery = (
            "Use a built-in clipType (media, video, image, audio, text, or "
            f"effect-layer) or an installed effect id. Available effect ids: {available}."
        )
        raise ManagedRenderValidationError(
            f"canonical timeline {snapshot.timeline_slug!r} is not renderable at "
            f"{path}: {reason}. Recovery: {recovery}",
            path=path,
            reason=reason,
            recovery=recovery,
            validator="registered_element_reference",
        )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class ManagedRenderSnapshot:
    project_id: str
    project_slug: str
    timeline_id: str
    timeline_ulid: str
    timeline_slug: str
    config_version: int
    head_event_id: str
    head_hash: str
    config: Mapping[str, Any]
    registry: Mapping[str, Any]
    config_hash: str
    registry_hash: str
    materialized_registry_hash: str

    def authority(self) -> dict[str, Any]:
        return {
            "authority": "kernel",
            "project_id": self.project_id,
            "project_slug": self.project_slug,
            "timeline_id": self.timeline_id,
            "timeline_ulid": self.timeline_ulid,
            "timeline_slug": self.timeline_slug,
            "config_version": self.config_version,
            "head_event_id": self.head_event_id,
            "head_hash": self.head_hash,
            "config_hash": self.config_hash,
            "registry_hash": self.registry_hash,
            "materialized_registry_hash": self.materialized_registry_hash,
        }


def validate_managed_render_snapshot(snapshot: ManagedRenderSnapshot) -> None:
    """Validate deterministic render requirements before kernel admission.

    Canonical timeline documents intentionally remain permissive authoring
    drafts.  Rendering is a stricter transition: once a managed ref is pinned,
    reject a malformed timeline/registry before materializing execution inputs
    or creating a run.  Backend runtime readiness remains the renderer's job.
    """

    config = dict(snapshot.config)
    output = config.get("output")
    if isinstance(output, Mapping):
        required_output_fields = ("resolution", "fps", "file")
        missing = [field for field in required_output_fields if field not in output]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(
                f"canonical timeline {snapshot.timeline_slug!r} is not renderable: "
                f"config.output is incomplete; missing required field(s): {missing_text}. "
                "Either omit config.output or provide resolution, fps, and file, then retry"
            )
    try:
        timeline.validate_timeline(config)
    except Exception as exc:
        raise _schema_validation_error(snapshot, exc) from exc
    _validate_render_element_clip_types(snapshot, config)

    registry = dict(snapshot.registry)
    try:
        timeline.validate_registry(registry)
    except Exception as exc:
        raise ValueError(
            f"canonical timeline {snapshot.timeline_slug!r} asset registry is not renderable: {exc}"
        ) from exc

    assets = registry.get("assets")
    registered = assets if isinstance(assets, Mapping) else {}
    missing_assets = sorted(
        {
            str(clip.get("asset"))
            for clip in config.get("clips", [])
            if isinstance(clip, Mapping)
            and isinstance(clip.get("asset"), str)
            and clip.get("asset") not in registered
        }
    )
    if missing_assets:
        raise ValueError(
            f"canonical timeline {snapshot.timeline_slug!r} is not renderable: "
            "clips reference missing registry asset id(s): " + ", ".join(missing_assets)
        )


def resolve_managed_render_snapshot(
    projects_root: Path,
    *,
    project_ref: str,
    timeline_ref: str,
    expected_version: int | None = None,
) -> ManagedRenderSnapshot:
    """Resolve one active kernel timeline and pin its immutable stream head."""

    database = Path(projects_root).resolve() / ".astrid" / "astrid.sqlite3"
    if not database.is_file():
        raise ValueError("Astrid kernel database is unavailable")
    conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        project = conn.execute(
            "SELECT id, slug FROM projects WHERE slug = ? OR id = ? LIMIT 1",
            (project_ref, project_ref),
        ).fetchone()
        if project is None:
            raise ValueError(f"project not found: {project_ref!r}")
        row = conn.execute(
            "SELECT t.id, t.document_json, t.asset_registry_json, s.head_seq, "
            "json_extract(created.payload_json, '$.data.timeline_ulid') AS timeline_ulid, "
            "json_extract(created.payload_json, '$.data.slug') AS timeline_slug, "
            "tail.event_id AS head_event_id, "
            "json_extract(tail.payload_json, '$._integrity.event_hash') AS head_hash, "
            "state.kind AS state_kind "
            "FROM timelines t JOIN event_streams s ON s.id = t.event_stream_id "
            "JOIN events created ON created.stream_id = s.id "
            "AND created.kind = 'timeline.created' "
            "JOIN events tail ON tail.stream_id = s.id AND tail.seq = s.head_seq "
            "LEFT JOIN events state ON state.event_id = ("
            "SELECT e.event_id FROM events e WHERE e.stream_id = s.id "
            "AND e.kind IN ('timeline.archived','timeline.unarchived') "
            "ORDER BY e.seq DESC LIMIT 1) "
            "WHERE t.project_id = ? AND (t.id = ? "
            "OR lower(json_extract(created.payload_json, '$.data.timeline_ulid')) = lower(?) "
            "OR lower(json_extract(created.payload_json, '$.data.slug')) = lower(?)) LIMIT 2",
            (str(project["id"]), timeline_ref, timeline_ref, timeline_ref),
        ).fetchall()
        if not row:
            raise ValueError(f"timeline {timeline_ref!r} was not found in project {project_ref!r}")
        if len(row) != 1:
            raise ValueError(f"timeline ref {timeline_ref!r} is ambiguous")
        timeline = row[0]
        if timeline["state_kind"] == "timeline.archived":
            raise ValueError(
                f"timeline {timeline_ref!r} is archived; unarchive it before rendering"
            )
        version = int(timeline["head_seq"])
        if expected_version is not None and expected_version != version:
            raise ValueError(
                f"stale timeline version: expected {expected_version}, current version is {version}; "
                "show the timeline and retry with the current version"
            )
        config = json.loads(str(timeline["document_json"]))
        assets = json.loads(str(timeline["asset_registry_json"]))
        if not isinstance(config, dict) or not isinstance(assets, dict):
            raise ValueError("canonical timeline snapshot is not a JSON object")
        stored_registry = {"assets": assets.get("assets", assets)}
        registry = rebase_timeline_registry_managed_assets(
            stored_registry,
            projects_root=projects_root,
            project_ref=str(project["id"]),
        )
        return ManagedRenderSnapshot(
            project_id=str(project["id"]),
            project_slug=str(project["slug"]),
            timeline_id=str(timeline["id"]),
            timeline_ulid=str(timeline["timeline_ulid"]),
            timeline_slug=str(timeline["timeline_slug"]),
            config_version=version,
            head_event_id=str(timeline["head_event_id"]),
            head_hash=str(timeline["head_hash"]),
            config=config,
            registry=registry,
            config_hash=_digest(config),
            # This hash names the canonical payload in the kernel and therefore
            # remains stable when a project is restored under another root.
            registry_hash=_digest(stored_registry),
            # Renderer locators are a derived, project-local view of that
            # payload. Pin them separately so retries use identical inputs.
            materialized_registry_hash=_digest(registry),
        )
    finally:
        conn.close()


def materialize_managed_render_snapshot(
    projects_root: Path,
    snapshot: ManagedRenderSnapshot,
) -> tuple[Path, Path, dict[str, Any]]:
    """Write deterministic private renderer inputs for one pinned snapshot."""

    authority = snapshot.authority()
    snapshot_key = _digest(authority)
    project_root = Path(projects_root).resolve() / snapshot.project_slug
    destination = project_root / ".astrid" / "render-snapshots" / snapshot_key
    destination.mkdir(parents=True, exist_ok=True)
    timeline_path = destination / "timeline.json"
    registry_path = destination / "assets.json"
    authority_path = destination / "authority.json"
    write_json_atomic(timeline_path, dict(snapshot.config))
    write_json_atomic(registry_path, dict(snapshot.registry))
    write_json_atomic(authority_path, authority)
    return timeline_path, registry_path, authority


__all__ = [
    "ManagedRenderValidationError",
    "ManagedRenderSnapshot",
    "materialize_managed_render_snapshot",
    "resolve_managed_render_snapshot",
    "validate_managed_render_snapshot",
]
