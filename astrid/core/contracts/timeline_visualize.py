"""Shared timeline-visualize view context (neutral leaf; no cli/gateway imports)."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ASTRID_GATEWAY_RESOLVED_PROJECT_ENV = "ASTRID_GATEWAY_RESOLVED_PROJECT"

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
        from astrid.core.contracts.run_record import (
            load_run_record_unvalidated as load_run_record,
        )
        from astrid.core.contracts.run_record import (
            resolve_record_path,
        )
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
        # Kernel-first ownership: prefer kernel run status; FS fallback for historical dirs.
        kernel_info = _kernel_visualize_run_info(project_slug, run_id, projects_root)
        if kernel_info is not None:
            if kernel_info.get("status") not in ("succeeded", "completed"):
                return None
            if kernel_info.get("tool_id") not in (None, "rendering.timeline_visualize"):
                # When kernel task capability is available, enforce it; otherwise rely on manifest checks below
                if kernel_info.get("capability") not in (None, "rendering.timeline_visualize"):
                    return None
            # Kernel run has no authoritative run.json; skip FS manifest pointer checks
            record_manifest = manifest_path
        else:
            run_json_path = (run_root / "run.json").resolve(strict=True)
            if run_json_path.parent != run_root or not run_json_path.is_file():
                return None

            record = load_run_record(project_slug, run_id, root=projects_root)
            metadata = record.get("metadata")
            if (
                record.get("project_slug") != project_slug
                or record.get("run_id") != run_id
                or record.get("tool_id") != "rendering.timeline_visualize"
                or record.get("status") != "completed"
                or not isinstance(metadata, dict)
                or metadata.get("evidence") is not True
            ):
                return None

            record_manifest_raw = record.get("manifest_path")
            if not isinstance(record_manifest_raw, str) or not record_manifest_raw:
                return None
            record_manifest = resolve_record_path(
                record_manifest_raw,
                project_slug,
                root=projects_root,
            ).resolve(strict=True)
            if not record_manifest.is_file() or not record_manifest.is_relative_to(run_root):
                return None
            if manifest_path != record_manifest:
                root_manifest = json.loads(record_manifest.read_text(encoding="utf-8"))
                if (
                    not isinstance(root_manifest, dict)
                    or root_manifest.get("kind") != "timeline_visualize_project"
                ):
                    return None
                reading_order = root_manifest.get("reading_order")
                if not isinstance(reading_order, list):
                    return None
                declared_children: set[Path] = set()
                for raw_child in reading_order:
                    if not isinstance(raw_child, str) or not raw_child:
                        return None
                    child = (record_manifest.parent / raw_child).resolve(strict=True)
                    if not child.is_file() or not child.is_relative_to(record_manifest.parent):
                        return None
                    declared_children.add(child)
                if manifest_path not in declared_children:
                    return None
        # Record_manifest resolved (kernel path uses manifest_path itself)
        if "record_manifest" not in locals():
            return None

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
        if not isinstance(inputs, dict) or inputs.get("timeline_source") != [project_slug]:
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

def _kernel_visualize_run_info(project_slug: str, run_id: str, projects_root: Path) -> dict[str, Any] | None:
    try:
        import sqlite3

        from astrid.core.kernel.read import kernel_run_info

        info = kernel_run_info(project_slug, run_id, projects_root=projects_root)
        if info is None:
            return None
        return {
            "status": str(info["status"]),
            "kind": str(info["kind"]) if info.get("kind") is not None else None,
            "title": info.get("title"),
            "capability": str(info["capability"]) if info.get("capability") is not None else None,
            "tool_id": str(info["capability"]) if info.get("capability") is not None else None,
        }
    except sqlite3.Error:
        return None
