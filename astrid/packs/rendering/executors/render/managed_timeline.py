"""Canonical kernel timeline resolution for the explicit managed render mode."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from astrid.core import timeline
from astrid.core._shared.jsonio import write_json_atomic
from astrid.core.io.media_import import validate_digest


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


def _runtime_media_admissions(client: Any, project_ref: str) -> dict[str, str]:
    """Read the project-scoped runtime media identity map.

    A timeline's ``media_id`` and digest are authored input, not proof of
    ownership.  Only the generated runtime client's project-scoped media read
    can authorize turning that identity into an attempt-local materialization.
    Keep the
    result deliberately small so it can be used as an admission snapshot and
    never requires a child renderer to reopen runtime storage.
    """

    try:
        result = client.media.list(project_ref)
    except Exception:  # noqa: BLE001 - an unavailable authority fails closed
        return {}
    if not result.ok:
        return {}
    rows = result.data
    if isinstance(rows, Mapping):
        rows = rows.get("items", rows.get("media", rows))
    if not isinstance(rows, (list, tuple, set)):
        return {}
    admitted: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        scope = row.get("project_ref") or row.get("project_slug")
        if scope is not None and str(scope) != project_ref:
            continue
        media_id = row.get("media_id") or row.get("id") or row.get("object_id")
        if not isinstance(media_id, str) or not media_id.strip():
            continue
        raw_digest = (
            row.get("content_hash")
            or row.get("content_sha256")
            or row.get("sha256")
            or row.get("digest")
            or row.get("object_id")
        )
        if not isinstance(raw_digest, str):
            continue
        try:
            digest = validate_digest(raw_digest.removeprefix("sha256:"))
        except (TypeError, ValueError):
            continue
        previous = admitted.get(media_id)
        if previous is not None and previous != digest:
            # A runtime response that is internally contradictory cannot
            # authorize either value.
            admitted.pop(media_id, None)
            continue
        admitted[media_id] = digest
    return admitted


def _runtime_snapshot_registry(
    registry: Mapping[str, Any], *, project_ref: str, client: Any
) -> dict[str, Any]:
    """Validate runtime-admitted media identities without replacing locators.

    The runtime snapshot is the authority and carries the stable ``media_id``
    and content digest. The generic host materializes bytes into the fenced
    attempt; this function never derives or writes a filesystem locator.
    """

    rebased = json.loads(json.dumps(dict(registry), ensure_ascii=False))
    raw_assets = rebased.get("assets", rebased)
    if not isinstance(raw_assets, dict):
        return rebased
    admitted = _runtime_media_admissions(client, project_ref)
    seen_media: dict[str, str] = {}
    # Detect contradictory authored aliases before checking runtime presence so
    # malformed canonical documents are reported deterministically even when
    # the runtime has no matching object.
    for entry in raw_assets.values():
        if not isinstance(entry, dict):
            continue
        media_id = entry.get("object_id") or entry.get("media_id")
        digest_value = (
            entry.get("content_sha256") or entry.get("sha256") or entry.get("hash")
        )
        if not isinstance(media_id, str) or not media_id.strip() or digest_value in (None, ""):
            continue
        try:
            digest = validate_digest(str(digest_value).removeprefix("sha256:"))
        except (TypeError, ValueError):
            continue
        previous = seen_media.get(media_id)
        if previous is not None and previous != digest:
            raise ManagedRenderValidationError(
                f"canonical registry contains conflicting entries for media_id {media_id!r}",
                path="$.assets",
                reason="one media_id claims multiple content digests",
                recovery="Keep one runtime-admitted digest for each media_id and retry.",
                validator="managed_media_identity",
            )
        seen_media[media_id] = digest
    seen_media.clear()
    for key, entry in raw_assets.items():
        if not isinstance(entry, dict):
            continue
        forbidden = [field for field in ("url", "file", "path", "source_path", "locator", "realm") if field in entry]
        if forbidden:
            raise ManagedRenderValidationError(
                f"canonical registry asset {key!r} contains retired media locator field(s): {', '.join(forbidden)}",
                path=f"$.assets[{json.dumps(str(key))}]",
                reason="live rendering accepts runtime-managed object ids and digests only",
                recovery="Import the bytes into the runtime and reference its object_id/digest.",
                validator="managed_media_locator",
            )
        media_id = entry.get("object_id") or entry.get("media_id")
        digest_value = (
            entry.get("content_sha256") or entry.get("sha256") or entry.get("hash")
        )
        if not isinstance(media_id, str) or not media_id.strip():
            raise ManagedRenderValidationError(
                f"canonical registry asset {key!r} is missing object_id",
                path=f"$.assets[{json.dumps(str(key))}].object_id",
                reason="path and URL media references are retired",
                recovery="Import the bytes into the runtime and reference its object_id.",
                validator="managed_media_identity",
            )
        admitted_digest = admitted.get(media_id)
        if admitted_digest is None:
            raise ManagedRenderValidationError(
                f"canonical registry asset {key!r} references media_id {media_id!r} "
                "that is not admitted by the selected project runtime",
                path=f"$.assets[{json.dumps(str(key))}].media_id",
                reason="media identity is missing from the project-scoped runtime read",
                recovery="Import the media into this project, refresh the timeline, and retry.",
                validator="managed_media_runtime_admission",
            )
        if digest_value in (None, ""):
            digest = admitted_digest
        else:
            try:
                digest = validate_digest(str(digest_value).removeprefix("sha256:"))
            except (TypeError, ValueError) as exc:
                raise ManagedRenderValidationError(
                    f"canonical registry asset {key!r} has an invalid content_sha256; "
                    "runtime media snapshots require a lowercase 64-hex digest",
                    path=f"$.assets[{json.dumps(str(key))}].content_sha256",
                    reason="invalid managed media digest",
                    recovery="Refresh the timeline from the runtime media snapshot and retry.",
                    validator="managed_media_digest",
                ) from exc
            if digest != admitted_digest:
                raise ManagedRenderValidationError(
                    f"canonical registry asset {key!r} claims digest {digest!r} for "
                    f"runtime media_id {media_id!r}, but the runtime admitted {admitted_digest!r}",
                    path=f"$.assets[{json.dumps(str(key))}].content_sha256",
                    reason="authored media identity does not match project runtime admission",
                    recovery="Refresh the timeline from the runtime media snapshot and retry.",
                    validator="managed_media_runtime_admission",
                )
        previous_digest = seen_media.get(media_id)
        if previous_digest is not None and previous_digest != digest:
            raise ManagedRenderValidationError(
                f"canonical registry contains conflicting entries for media_id {media_id!r}",
                path="$.assets",
                reason="one media_id claims multiple content digests",
                recovery="Keep one runtime-admitted digest for each media_id and retry.",
                validator="managed_media_identity",
            )
        seen_media[media_id] = digest
        # Keep the runtime identity in the child snapshot. The generic host,
        # not the timeline resolver, materializes bytes into its attempt.
        entry["media_id"] = media_id
        entry.pop("object_id", None)
        entry["content_sha256"] = digest
    return rebased


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
        admissions: dict[str, str] = {}
        assets = self.registry.get("assets", {})
        if isinstance(assets, Mapping):
            for entry in assets.values():
                if not isinstance(entry, Mapping):
                    continue
                media_id = entry.get("object_id") or entry.get("media_id")
                digest = entry.get("content_sha256")
                if (
                    isinstance(media_id, str)
                    and media_id.strip()
                    and isinstance(digest, str)
                ):
                    admissions[media_id] = digest
        if admissions:
            # This is the immutable parent-to-child handoff.  A child may use
            # it only as a runtime-admitted allowlist; registry media_id and
            # digest fields alone are never ownership proof.
            result["managed_media_admissions"] = admissions
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
    *,
    project_ref: str,
    timeline_ref: str,
    expected_version: int | None = None,
    client: Any,
) -> ManagedRenderSnapshot:
    """Resolve one active timeline through the generated SDK read surface.

    ``client`` is the already-bound runtime client for this attempt. No
    renderer path opens a competing database owner or accepts local storage
    configuration.
    """
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
    listed = client.timelines.list(project_ref)
    if listed.ok:
        rows = listed.data[0] if isinstance(listed.data, tuple) else listed.data
        for row in rows or []:
            if row.get("timeline_id") == timeline_data.get("timeline_id") and row.get("archived_at"):
                raise ValueError(
                    f"timeline {timeline_ref!r} is archived; unarchive it before rendering"
                )
    config = timeline_data.get("config")
    stored_registry = timeline_data.get("registry")
    if not isinstance(config, dict) or not isinstance(stored_registry, dict):
        raise ValueError("canonical timeline snapshot is not a JSON object")
    # The SDK's read model is the authority. Keep runtime-admitted media
    # identities in the snapshot; the generic host supplies bytes to the child
    # attempt without any local database or filesystem lookup.
    registry = _runtime_snapshot_registry(
        stored_registry,
        project_ref=project_ref,
        client=client,
    )
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
