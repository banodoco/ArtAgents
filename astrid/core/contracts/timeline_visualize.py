"""Shared timeline-visualize view context (neutral leaf; no cli/gateway imports)."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

@dataclass(frozen=True)
class TimelineVisualizeViewContext:
    """Trusted owner coordinates for one prior visualization manifest."""

    project_slug: str
    run_id: str
    run_root: Path
    manifest_path: Path

def _timeline_visualize_option_values(raw: list[str], option: str) -> list[str]:
    """Return every value supplied for *option* in split or equals form."""

    values: list[str] = []
    index = 0
    while index < len(raw):
        token = raw[index]
        if token == option:
            if index + 1 < len(raw):
                values.append(raw[index + 1])
            index += 2
            continue
        prefix = f"{option}="
        if token.startswith(prefix):
            values.append(token[len(prefix) :])
        index += 1
    return values

def _validated_timeline_visualize_view_context(
    raw: list[str],
) -> TimelineVisualizeViewContext | None:
    """Validate the sole sessionless timeline-visualization exception.

    A prior view is authorization only when its complete evidence pack passes
    R16's containment, hash, schema, chain-of-trust, and run-ownership preflight.
    Any malformed or ambiguous request fails closed by returning ``None`` so
    the caller can issue ordinary project selection guidance.
    """

    if tuple(raw[:2]) != ("timelines", "visualize"):
        return None
    value_options = {
        "--project",
        "--shot",
        "--range",
        "--at",
        "--clip",
        "--asset",
        "--context",
        "--neighbors",
        "--from-view",
        "--focus",
        "--layout",
        "--format",
        "--filmstrip",
        "--rendered-video",
    }
    index = 2
    while index < len(raw):
        token = raw[index]
        if token in value_options:
            if index + 1 >= len(raw):
                return None
            index += 2
            continue
        if any(token.startswith(f"{option}=") for option in value_options):
            index += 1
            continue
        if token == "--all":
            index += 1
            continue
        if token == "--refresh-root":
            index += 1
            continue
        # Positional timeline selection, ``--`` payloads, and unknown flags
        # are never part of the narrowly recognized sessionless grammar.
        return None
    if _timeline_visualize_option_values(raw, "--project"):
        return None
    if any(
        token == flag or token.startswith(f"{flag}=")
        for token in raw[2:]
        for flag in ("--all", "--shot", "--range", "--at", "--clip", "--asset")
    ):
        return None

    from_view_values = _timeline_visualize_option_values(raw, "--from-view")
    focus_values = _timeline_visualize_option_values(raw, "--focus")
    if (
        len(from_view_values) != 1
        or len(focus_values) != 1
        or not from_view_values[0]
        or not focus_values[0]
    ):
        return None

    try:
        from astrid.core.foundation.project_paths import resolve_projects_root
        from astrid.packs.rendering.executors.timeline_visualize.frozen import (
            discard_rehydrated_pack,
            load_frozen_view,
            resolve_focus,
        )
        from astrid.packs.rendering.executors.timeline_visualize.ids import (
            parse_qualified_ref,
        )
        from astrid.packs.rendering.executors.timeline_visualize.select import (
            select_from_manifest,
        )

        parse_qualified_ref(focus_values[0])

        projects_root = resolve_projects_root().resolve(strict=True)
        manifest_path = Path(from_view_values[0]).expanduser().resolve(strict=True)
        if manifest_path.name != "manifest.json" or not manifest_path.is_file():
            return None
        relative = manifest_path.relative_to(projects_root)
        if (
            len(relative.parts) < 5
            or relative.parts[1] != "runs"
            or relative.parts[3] != "agent-view"
        ):
            return None
        project_slug, run_id = relative.parts[0], relative.parts[2]
        run_root = (projects_root / project_slug / "runs" / run_id).resolve(strict=True)
        if not run_root.is_dir() or not manifest_path.is_relative_to(run_root):
            return None
        # Runtime ownership is mandatory.  Historical filesystem ledgers are
        # not a valid authorization source for a public frozen-view route.
        kernel_info = _runtime_visualize_run_info(project_slug, run_id)
        if kernel_info is None:
            return None
        run_project_id = kernel_info.get("project_id")
        current_project_id = kernel_info.get("current_project_id")
        if (
            run_project_id is not None
            and current_project_id is not None
            and str(run_project_id) != str(current_project_id)
        ):
            return None
        if kernel_info.get("status") not in ("succeeded", "completed"):
            return None
        if kernel_info.get("tool_id") not in (None, "rendering.timeline_visualize"):
            if kernel_info.get("capability") not in (None, "rendering.timeline_visualize"):
                return None
        # The runtime run resource does not carry an authoritative filesystem
        # manifest pointer; the contained manifest supplied by the caller is
        # the frozen artifact being verified.
        record_manifest = manifest_path

        hashes_path = (manifest_path.parent / "pack-hashes.json").resolve(strict=True)
        if hashes_path.parent != manifest_path.parent or not hashes_path.is_file():
            return None
        hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
        if not isinstance(hashes, dict):
            return None
        files = hashes.get("files")
        manifest_record = files.get("manifest.json") if isinstance(files, dict) else None
        coverage = hashes.get("coverage")
        if (
            hashes.get("schema_version") != 1
            or hashes.get("kind") != "timeline_visualize_pack_hashes"
            or not isinstance(coverage, dict)
            or coverage.get("manifest") != "manifest.json"
            or not isinstance(manifest_record, dict)
        ):
            return None

        manifest_bytes = manifest_path.read_bytes()
        expected_hash = manifest_record.get("sha256")
        expected_bytes = manifest_record.get("bytes")
        observed_hash = hashlib.sha256(manifest_bytes).hexdigest()
        if (
            not isinstance(expected_hash, str)
            or not hmac.compare_digest(expected_hash, observed_hash)
            or isinstance(expected_bytes, bool)
            or not isinstance(expected_bytes, int)
            or expected_bytes != len(manifest_bytes)
        ):
            return None
        manifest = json.loads(manifest_bytes)
        if not isinstance(manifest, dict) or select_from_manifest(manifest) is None:
            return None
        inputs = manifest.get("inputs")
        # New packs identify their authority explicitly.  A raw
        # ``timeline_source`` field is forbidden: accepting it would revive
        # the retired filesystem timeline handoff on the sessionless route.
        if (
            not isinstance(inputs, dict)
            or "timeline_source" in inputs
            or inputs.get("source_mode") not in {"kernel", "frozen"}
        ):
            return None
        frozen = load_frozen_view(
            manifest_path,
            project_root=projects_root / project_slug,
        )
        try:
            parsed_focus = parse_qualified_ref(focus_values[0])
            if "--refresh-root" in raw:
                refresh_scope = resolve_focus(frozen, focus_values[0])
                if parsed_focus.kind != "TL" or refresh_scope.kind != "timeline":
                    return None
            else:
                resolve_focus(frozen, focus_values[0])
        finally:
            discard_rehydrated_pack(frozen.pack_root)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None

    return TimelineVisualizeViewContext(
        project_slug=project_slug,
        run_id=run_id,
        run_root=run_root,
        manifest_path=manifest_path,
    )

def _runtime_visualize_run_info(project_slug: str, run_id: str) -> dict[str, Any] | None:
    """Read visualization-run ownership from the generated runtime client.

    The gateway's ``--from-view`` exception runs before a normal product
    session exists, but it still must use the same runtime authority as the
    executor.  In particular, this leaf must never open the local ledger merely
    to validate a durable view manifest.
    """
    try:
        from astrid.sdk.workspace_client import WorkspaceClient, resolve_runtime_connection

        endpoint, token = resolve_runtime_connection()
        runtime = WorkspaceClient(endpoint, token)
        info = runtime.get_run(run_id)
        if not isinstance(info, Mapping):
            return None
        capability = info.get("capability") or info.get("capability_id")
        metadata = info.get("metadata")
        timeline_ids = info.get("timeline_ids")
        if timeline_ids is None and isinstance(metadata, Mapping):
            timeline_ids = metadata.get("timeline_ids")
        from astrid.sdk.pagination import paged_rows

        project_rows = paged_rows(runtime.list_projects)
        if project_rows is None:
            return None
        current = next(
            (
                row
                for row in project_rows
                if isinstance(row, Mapping) and row.get("slug") == project_slug
            ),
            None,
        )
        run_project_id = info.get("project_id") or info.get("project")
        return {
            "status": str(info.get("status", info.get("state", ""))),
            "kind": str(info.get("kind")) if info.get("kind") is not None else None,
            "title": info.get("title"),
            "capability": str(capability) if capability is not None else None,
            "tool_id": str(capability) if capability is not None else None,
            "timeline_ids": timeline_ids,
            "project_id": run_project_id,
            "current_project_id": (
                current.get("project_id") or current.get("id")
                if isinstance(current, Mapping)
                else None
            ),
        }
    except Exception:  # noqa: BLE001 - unavailable runtime fails closed
        return None
