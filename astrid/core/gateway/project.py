"""Gateway project resolution and auto-bind helpers.

Extracted from ``astrid/gateway.py`` during M4 batch 39 (T40) to keep the
gateway facade narrowly focused while preserving environment constants
and characterized project helper names through the gateway facade.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core._shared.capability_common import _has_cli_option
from astrid.core.contracts.errors import AstridError

# ---------------------------------------------------------------------------
# Project resolution environment constants
# ---------------------------------------------------------------------------

# Compatibility exports retained while auto-binding is intentionally disabled.
# A default is an attach-time suggestion, never execution authorization.
DEFAULT_PROJECT_SLUG = "default"
ASTRID_GATEWAY_RESOLVED_PROJECT_ENV = "ASTRID_GATEWAY_RESOLVED_PROJECT"
_AUTO_BIND_RUN_VERBS: tuple[tuple[str, ...], ...] = ()
_REQUEST_SCOPED_PROJECT_RUN_VERBS: tuple[tuple[str, ...], ...] = (
    ("executors", "run"),
    ("orchestrators", "run"),
    ("scratch", "run"),
    ("timelines", "visualize"),
)


@dataclass(frozen=True)
class TimelineVisualizeViewContext:
    """Trusted owner coordinates for one prior visualization manifest."""

    project_slug: str
    run_id: str
    run_root: Path
    manifest_path: Path


# ---------------------------------------------------------------------------
# Project helpers
# ---------------------------------------------------------------------------


def _extract_project_slug(raw: list[str]) -> str | None:
    for index, token in enumerate(raw):
        if token == "--project":
            return raw[index + 1] if index + 1 < len(raw) else None
        if token.startswith("--project="):
            value = token.split("=", 1)[1]
            return value or None
    return None


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
        from astrid.core.project.run import load_run_record, resolve_record_path
        from astrid.packs.rendering.executors.timeline_visualize.ids import (
            parse_qualified_ref,
        )
        from astrid.packs.rendering.executors.timeline_visualize.frozen import (
            load_frozen_view,
            resolve_focus,
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
        parsed_focus = parse_qualified_ref(focus_values[0])
        if "--refresh-root" in raw:
            refresh_scope = resolve_focus(frozen, focus_values[0])
            if parsed_focus.kind != "TL" or refresh_scope.kind != "timeline":
                return None
        else:
            resolve_focus(frozen, focus_values[0])
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None

    return TimelineVisualizeViewContext(
        project_slug=project_slug,
        run_id=run_id,
        run_root=run_root,
        manifest_path=manifest_path,
    )


def _extract_project_slug_from_run_paths(raw: list[str]) -> str | None:
    """Infer a local project slug from file-scoped run arguments.

    ``executors run`` and friends are often invoked with only explicit file
    paths, e.g. ``--out projects/demo/runs/x`` and
    ``--input timeline=projects/demo/runs/x/hype.timeline.json``. In that
    case, falling back to the configured global default project is surprising
    and can route provenance to the wrong project. Infer the slug only when all
    project-root paths point at the same local project.
    """
    if _extract_project_slug(raw) is not None or not _is_request_scoped_run(raw):
        return None
    slugs = _project_slugs_from_run_paths(raw)
    if len(slugs) == 1:
        return next(iter(slugs))
    return None


def _project_slugs_from_run_paths(raw: list[str]) -> set[str]:
    if _extract_project_slug(raw) is not None or not _is_request_scoped_run(raw):
        return set()
    try:
        from astrid.core.foundation.project_paths import resolve_projects_root

        projects_root = resolve_projects_root().resolve()
    except Exception:
        return set()
    slugs: set[str] = set()
    for value in _iter_file_scoped_run_values(raw):
        slug = _project_slug_for_path_value(value, projects_root)
        if slug:
            slugs.add(slug)
    return slugs


def _raise_on_ambiguous_run_path_projects(raw: list[str]) -> None:
    if _extract_project_slug(raw) is not None or _has_cli_option(raw, "--timeline-id"):
        return
    slugs = _project_slugs_from_run_paths(raw)
    if len(slugs) <= 1:
        return
    choices = ", ".join(sorted(slugs))
    raise AstridError(
        f"ambiguous project context: run paths reference multiple projects ({choices})",
        recovery_command="pass --project <slug> explicitly",
        state_snapshot={"argv": raw, "projects": sorted(slugs)},
    )


def _is_request_scoped_run(raw: list[str]) -> bool:
    for prefix in _REQUEST_SCOPED_PROJECT_RUN_VERBS:
        if tuple(raw[: len(prefix)]) == prefix:
            return True
    return False


def _iter_file_scoped_run_values(raw: list[str]) -> list[str]:
    values: list[str] = []
    index = 0
    while index < len(raw):
        token = raw[index]
        if token in {"--out", "--brief"} and index + 1 < len(raw):
            values.append(raw[index + 1]); index += 2; continue
        if token.startswith("--out=") or token.startswith("--brief="):
            values.append(token.split("=", 1)[1]); index += 1; continue
        if token == "--input" and index + 1 < len(raw):
            values.append(raw[index + 1].split("=", 1)[-1]); index += 2; continue
        if token.startswith("--input="):
            values.append(token.split("=", 1)[1].split("=", 1)[-1]); index += 1; continue
        index += 1
    return values


def _project_slug_for_path_value(value: str, projects_root: Path) -> str | None:
    if not value or "://" in value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        relative = path.resolve(strict=False).relative_to(projects_root)
    except ValueError:
        return None
    if not relative.parts:
        return None
    slug = relative.parts[0]
    project_json = projects_root / slug / "project.json"
    return slug if project_json.is_file() else None


def _invocation_is_auto_bindable_run(raw: list[str]) -> bool:
    """Compatibility predicate: project auto-binding is no longer legal."""

    del raw
    return False


def _auto_bind_default_project_session(raw: list[str]) -> Any:
    """Compatibility shim: auto-binding is disabled and has no side effects."""

    del raw
    return None


def _resolved_request_project_slug(raw: list[str], session: Any) -> str | None:
    if session is None or _extract_project_slug(raw) is not None or _has_cli_option(raw, "--timeline-id"):
        return None
    if _is_request_scoped_run(raw):
        return str(getattr(session, "project", "") or "") or None
    return None


def _dispatch_with_resolved_project(raw: list[str], project_slug: str | None) -> int:
    if not project_slug:
        # Late import to avoid circular dependency at module load time.
        from astrid.core.gateway import _dispatch

        return _dispatch(raw)
    previous = os.environ.get(ASTRID_GATEWAY_RESOLVED_PROJECT_ENV)
    os.environ[ASTRID_GATEWAY_RESOLVED_PROJECT_ENV] = project_slug
    try:
        from astrid.core.gateway import _dispatch

        return _dispatch(raw)
    finally:
        if previous is None:
            os.environ.pop(ASTRID_GATEWAY_RESOLVED_PROJECT_ENV, None)
        else:
            os.environ[ASTRID_GATEWAY_RESOLVED_PROJECT_ENV] = previous
