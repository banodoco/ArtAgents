"""Canonical kernel timeline resolution for the explicit managed render mode."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from astrid.core import timeline
from astrid.core._shared.jsonio import write_json_atomic


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
    expansion: Mapping[str, Any] | None = None

    def authority(self) -> dict[str, Any]:
        result = {
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
        if self.expansion is not None:
            result["expansion"] = dict(self.expansion)
        return result


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
    client: Any | None = None,
) -> ManagedRenderSnapshot:
    """Resolve one active timeline through the generated SDK read surface.

    ``client`` is injectable so a long-lived ``AstridClient`` can be reused
    without opening a competing database owner.  Direct callers get a short
    lived client for backwards compatibility; no renderer path owns or opens
    a SQLite connection.
    """
    if client is None:
        from astrid.sdk.client import AstridClient

        # The workspace runtime is the sole authority.  ``projects_root`` is
        # only the attempt-local materialization destination and must never be
        # passed to the client composition root (which deliberately accepts no
        # local-storage arguments after the runtime cutover).
        with AstridClient.open() as owned_client:
            return resolve_managed_render_snapshot(
                projects_root,
                project_ref=project_ref,
                timeline_ref=timeline_ref,
                expected_version=expected_version,
                client=owned_client,
            )

    project_result = client.projects.show(project_ref)
    if not project_result.ok or not project_result.data:
        raise ValueError(f"project not found: {project_ref!r}")
    project = project_result.data
    timeline_result = client.timelines.show(project_ref, timeline_ref)
    if not timeline_result.ok or not timeline_result.data:
        raise ValueError(
            f"timeline {timeline_ref!r} was not found in project {project_ref!r}"
        )
    timeline_data = timeline_result.data
    version = int(timeline_data["config_version"])
    if expected_version is not None and expected_version != version:
        raise ValueError(
            f"stale timeline version: expected {expected_version}, current version is {version}; "
            "show the timeline and retry with the current version"
        )
    listed = client.timelines.list(project_ref, include_archived=True)
    if listed.ok:
        for row in listed.data or []:
            if row.get("timeline_id") == timeline_data.get("timeline_id") and row.get("archived_at"):
                raise ValueError(
                    f"timeline {timeline_ref!r} is archived; unarchive it before rendering"
                )
    config = timeline_data.get("config")
    stored_registry = timeline_data.get("registry")
    if not isinstance(config, dict) or not isinstance(stored_registry, dict):
        raise ValueError("canonical timeline snapshot is not a JSON object")
    # The SDK's read model is already the canonical persisted registry. Any
    # path rebasing belongs to the client/runtime media surface, not this
    # resolver's authority read.
    registry = dict(stored_registry)
    project_id = str(project["id"])
    config_hash = _digest(config)
    registry_hash = _digest(stored_registry)
    head_event_id = f"timeline:{timeline_data['timeline_id']}:{version}"
    head_hash = config_hash
    try:
        events = client.app.event_log.list_events(project_id=project_id, limit=10000)
        matching = [
            event for event in events
            if event.subject_id == str(timeline_data["timeline_id"])
            and event.seq == version
        ]
        if matching:
            head_event_id = matching[-1].event_id
            head_hash = matching[-1].event_hash
    except (AttributeError, TypeError, ValueError):
        # Older equivalent clients may not expose ordered event reads. The
        # content digest remains deterministic evidence for materialization.
        pass
    return ManagedRenderSnapshot(
        project_id=project_id,
        project_slug=str(project["slug"]),
        timeline_id=str(timeline_data["timeline_id"]),
        timeline_ulid=str(timeline_data["timeline_ulid"]),
        timeline_slug=str(timeline_data["slug"]),
        config_version=version,
        head_event_id=head_event_id,
        head_hash=head_hash,
        config=config,
        registry=registry,
        config_hash=config_hash,
        registry_hash=registry_hash,
        materialized_registry_hash=_digest(registry),
    )


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
