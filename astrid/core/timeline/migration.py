"""Library entry-point for timeline migration (milestone 8).

Provides:
- Dataclasses for structured migration results
- Project discovery using existing project discovery APIs
- Timeline directory classification (already-event-sourced, legacy-local,
  malformed/incomplete)
- Read-only source blob classification that never mutates files

The sprint-2 migration script at
``scripts/migrations/sprint-2/migrate_timelines.py`` remains the supported
runnable surface for legacy migration.  This module re-exports its ``main``
and ``audit`` entry points so that existing callers continue to work.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Sprint-2 compatibility re-exports
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "scripts" / "migrations" / "sprint-2" / "migrate_timelines.py"
)

_spec = importlib.util.spec_from_file_location(
    "_astrid_sprint2_migrate_timelines", _SCRIPT_PATH
)
if _spec is None or _spec.loader is None:  # pragma: no cover - import-time guard
    raise ImportError(f"could not load migration script from {_SCRIPT_PATH}")

_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)

main = _module.main
audit = _module.audit

# ---------------------------------------------------------------------------
# Structured result types
# ---------------------------------------------------------------------------

TimelineClassification = Literal[
    "already_event_sourced",  # assembly.jsonl + assembly.identity.json exist
    "legacy_local",           # assembly.json exists but no event log
    "malformed_incomplete",   # missing both or unreadable
]


@dataclass(frozen=True)
class SkippedTimeline:
    """Why a timeline was skipped during discovery or migration."""

    project_slug: str
    timeline_ulid: str | None  # None when the timeline has no ULID (malformed)
    reason: str
    classification: TimelineClassification


@dataclass(frozen=True)
class ParityFailure:
    """A timeline whose projected assembly did not match the source blob.

    Source blobs are never mutated — the caller is expected to decide
    whether to retry, skip, or escalate.
    """

    project_slug: str
    timeline_ulid: str
    source_hash: str
    projected_hash: str
    detail: str = ""


@dataclass(frozen=True)
class ResumableStatus:
    """Checkpoint-able progress so a migration can be paused and resumed."""

    last_completed_project: str | None = None
    last_completed_timeline_ulid: str | None = None
    imported_count: int = 0
    skipped_count: int = 0


@dataclass(frozen=True)
class MigrationResult:
    """Aggregated outcome of a migration run."""

    imported: list[str] = field(default_factory=list)  # timeline ULIDs
    skipped: list[SkippedTimeline] = field(default_factory=list)
    parity_failures: list[ParityFailure] = field(default_factory=list)
    resumable: ResumableStatus = field(default_factory=ResumableStatus)
    started_at: str = ""
    finished_at: str = ""

    @property
    def ok(self) -> bool:
        return len(self.parity_failures) == 0


# ---------------------------------------------------------------------------
# Project discovery (delegates to existing APIs)
# ---------------------------------------------------------------------------


def discover_projects_for_migration(
    *, root: str | Path | None = None
) -> list[str]:
    """Return project slugs suitable for timeline migration.

    Delegates to ``astrid.core.session.discovery.discover_projects``
    so that migration discovery stays aligned with the rest of the app.

    Source blobs are never read or written by this function — it only
    lists directory names.
    """
    from astrid.core.session.discovery import discover_projects

    return discover_projects(root=root)


def discover_timelines_for_project(
    project_slug: str, *, root: str | Path | None = None
) -> list[tuple[str, TimelineClassification]]:
    """List timeline ULIDs inside a project along with their classification.

    Returns ``[(ulid, classification), ...]``.  An empty list means no
    timeline directories exist.

    This function is **read-only** — it never creates, writes, or deletes
    any file under the project directory.
    """
    from astrid.core.project.paths import resolve_projects_root, validate_project_slug
    from astrid.threads.ids import is_ulid

    slug = validate_project_slug(project_slug)
    projects_root = resolve_projects_root(root)
    timelines_dir = projects_root / slug / "timelines"

    if not timelines_dir.is_dir():
        return []

    results: list[tuple[str, TimelineClassification]] = []
    for child in sorted(timelines_dir.iterdir()):
        if not child.is_dir() or not is_ulid(child.name):
            continue
        ulid = child.name
        classification = classify_timeline_dir(child)
        results.append((ulid, classification))

    return results


def classify_timeline_dir(timeline_home: Path) -> TimelineClassification:
    """Classify a timeline directory without mutating any file.

    Classification rules (read-only):

    - ``already_event_sourced`` — ``assembly.jsonl`` **and**
      ``assembly.identity.json`` both exist and are readable.
    - ``legacy_local`` — ``assembly.json`` exists but no event log.
    - ``malformed_incomplete`` — everything else (missing both files,
      unreadable JSON, etc.).

    Source blobs are never touched — this function only checks file
    existence and, when necessary for shape validation, parses JSON.
    """
    events_path = timeline_home / "assembly.jsonl"
    identity_path = timeline_home / "assembly.identity.json"
    assembly_path = timeline_home / "assembly.json"

    # Already event-sourced: both event log and identity sidecar exist.
    if events_path.is_file() and identity_path.is_file():
        # Quick sanity — do the files parse?
        try:
            from astrid.core.project.jsonio import read_json
            identity = read_json(identity_path)
            if isinstance(identity, dict) and "timeline_id" in identity:
                return "already_event_sourced"
        except Exception:
            pass  # fall through to malformed

    # Legacy-local: assembly.json exists but no event log.
    if assembly_path.is_file() and not events_path.is_file():
        try:
            from astrid.core.project.jsonio import read_json
            assembly = read_json(assembly_path)
            if isinstance(assembly, dict):
                return "legacy_local"
        except Exception:
            pass

    return "malformed_incomplete"


# ---------------------------------------------------------------------------
# Idempotent LocalFs import
# ---------------------------------------------------------------------------


def import_from_legacy_local(
    *,
    backend: Any,
    timeline_home: Path,
    actor: Any,
    run_ts: str | None = None,
) -> dict[str, Any]:
    """Idempotently import a legacy-local timeline into the event log.

    (a) When the event log is empty, reads ``assembly.json`` from
        *timeline_home*, appends exactly one ``timeline.imported`` event
        with ``source='legacy_local'`` and the snapshot containing the
        assembly blob, and writes progress artifacts under
        ``runs/migrations/<timestamp>/``.

    (b) Verifies projection parity: ``project_to_assembly(backend.read_events())``
        must equal the legacy ``assembly.json`` body.  Returns a result
        dict with ``ok``, ``parity_ok``, ``event_id``, etc.

    (c) No-op rerun: when the first event in the log is already a
        ``timeline.imported`` event with ``source='legacy_local'`` **and**
        projection parity holds, this function returns immediately without
        appending any new events.

    (d) Progress files are written under ``runs/migrations/<timestamp>/``,
        never inside the source timeline directory.

    Source blobs are **never** mutated — only the event log and progress
    artifacts are written.

    Parameters
    ----------
    backend:
        A ``LocalFsBackend`` instance pointed at *timeline_home*.
    timeline_home:
        Path to the timeline directory (must contain ``assembly.json``).
    actor:
        ``TimelineActor`` recorded on the imported event.
    run_ts:
        Optional timestamp string for the migration run directory.
        Defaults to the current Unix timestamp.

    Returns
    -------
    dict
        Keys: ``ok`` (bool), ``imported`` (bool), ``event_id`` (str|None),
        ``parity_ok`` (bool | None), ``detail`` (str).
    """
    import time as _time
    import json as _json

    from astrid.core.project.jsonio import read_json
    from astrid.core.timeline.projection import project_to_assembly
    from astrid.core.timeline.events.schema import (
        TimelineImportedPayload,
        TimelineEvent,
    )

    ts = run_ts if run_ts is not None else str(int(_time.time()))

    # ------------------------------------------------------------------
    # 1. Read the existing event stream
    # ------------------------------------------------------------------
    events = backend.read_events()

    # ------------------------------------------------------------------
    # 2. If the stream already has events, check idempotence
    # ------------------------------------------------------------------
    if events:
        first = events[0]

        # (c) No-op: first event is already timeline.imported with
        # source='legacy_local' and parity holds.
        if first.kind == "timeline.imported":
            source = first.payload.source if hasattr(first.payload, 'source') else None
            if source == "legacy_local":
                # Verify projection parity
                projected = project_to_assembly(events)
                try:
                    raw_assembly = read_json(timeline_home / "assembly.json")
                except Exception:
                    return {
                        "ok": False,
                        "imported": False,
                        "event_id": None,
                        "parity_ok": False,
                        "detail": "Cannot read source assembly.json for parity check",
                    }

                # Unwrap the wrapper if present
                if isinstance(raw_assembly, dict) and "assembly" in raw_assembly:
                    legacy_body = raw_assembly["assembly"]
                else:
                    legacy_body = raw_assembly

                if projected == legacy_body:
                    return {
                        "ok": True,
                        "imported": False,
                        "event_id": first.event_id,
                        "parity_ok": True,
                        "detail": "Already imported — parity holds, skipping",
                    }
                else:
                    return {
                        "ok": False,
                        "imported": False,
                        "event_id": first.event_id,
                        "parity_ok": False,
                        "detail": "Already imported but parity does NOT hold",
                    }

        # Stream exists but first event is not timeline.imported —
        # do not clobber an existing event-sourced timeline.
        return {
            "ok": False,
            "imported": False,
            "event_id": None,
            "parity_ok": None,
            "detail": (
                f"Event log is not empty and first event is "
                f"{first.kind!r}, not timeline.imported — refusing to import"
            ),
        }

    # ------------------------------------------------------------------
    # 3. Event log is empty — perform the import
    # ------------------------------------------------------------------

    # Read assembly.json (source blob — never mutated)
    try:
        raw_assembly = read_json(timeline_home / "assembly.json")
    except FileNotFoundError:
        return {
            "ok": False,
            "imported": False,
            "event_id": None,
            "parity_ok": None,
            "detail": "Source assembly.json not found",
        }
    except Exception as exc:
        return {
            "ok": False,
            "imported": False,
            "event_id": None,
            "parity_ok": None,
            "detail": f"Failed to read source assembly.json: {exc}",
        }

    # Build snapshot (matching LocalFsBackend._build_imported_event shape)
    snapshot: dict[str, Any] = {"assembly.json": raw_assembly}
    # Also include display.json and manifest.json if they exist
    for name in ("display.json", "manifest.json"):
        path = timeline_home / name
        if path.is_file():
            try:
                snapshot[name] = read_json(path)
            except Exception:
                pass

    # Append the timeline.imported event
    try:
        event = backend.append_event(
            backend.timeline_id,
            "timeline.imported",
            {
                "snapshot": snapshot,
                "source": "legacy_local",
            },
            actor=actor,
        )
    except Exception as exc:
        return {
            "ok": False,
            "imported": False,
            "event_id": None,
            "parity_ok": None,
            "detail": f"Failed to append timeline.imported: {exc}",
        }

    # ------------------------------------------------------------------
    # 4. Verify projection parity (b)
    # ------------------------------------------------------------------
    all_events = backend.read_events()
    projected = project_to_assembly(all_events)

    # Unwrap legacy assembly.json if it has the wrapper shape
    if isinstance(raw_assembly, dict) and "assembly" in raw_assembly:
        legacy_body = raw_assembly["assembly"]
    else:
        legacy_body = raw_assembly

    parity_ok = projected == legacy_body

    # ------------------------------------------------------------------
    # 5. Write progress artifacts under runs/migrations/<timestamp>/ (d)
    # ------------------------------------------------------------------
    progress_dir = timeline_home.parent.parent / "runs" / "migrations" / ts
    try:
        progress_dir.mkdir(parents=True, exist_ok=True)
        progress_file = progress_dir / "import_result.json"
        progress_data = {
            "run_ts": ts,
            "timeline_ulid": timeline_home.name,
            "imported": True,
            "event_id": event.event_id,
            "parity_ok": parity_ok,
        }
        progress_file.write_text(
            _json.dumps(progress_data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except Exception:
        # Progress artifact is best-effort; do not fail the import.
        pass

    return {
        "ok": parity_ok,
        "imported": True,
        "event_id": event.event_id,
        "parity_ok": parity_ok,
        "detail": (
            "Import succeeded, parity matches"
            if parity_ok
            else "Import succeeded but projection parity does NOT match source assembly.json"
        ),
    }


# ---------------------------------------------------------------------------
# Supabase timeline discovery (uses existing Reigh transport seam — SD3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SupabaseTimelineCandidate:
    """A Supabase timeline discovered via the Reigh transport seam.

    This is NOT an eventlog protocol extension — discovery stays on the
    existing Reigh blob-config transport (``timeline_io.py`` /
    ``data_provider.py``) per SD3.
    """

    project_id: str
    timeline_id: str
    has_config: bool = False   # public.timelines row exists
    has_events: bool = False   # public.timeline_events rows exist
    config_version: int | None = None


def discover_supabase_timelines(
    *,
    project_id: str | None = None,
    supabase_url: str | None = None,
    service_role_key: str | None = None,
) -> list[SupabaseTimelineCandidate]:
    """List candidate Supabase timelines for migration.

    Uses the existing Reigh transport seam to query ``public.timelines``
    and check whether ``public.timeline_events`` rows exist.

    **No-credentials behaviour**: when *supabase_url* and *service_role_key*
    are both absent (the default local-only scenario), this function
    returns an empty list immediately without any network calls.

    Parameters
    ----------
    project_id:
        Optional filter.  When ``None``, all timelines are returned.
    supabase_url:
        Supabase project URL.  Defaults to ``SUPABASE_URL`` env var.
    service_role_key:
        Service-role key for admin access.  Defaults to
        ``SUPABASE_SERVICE_ROLE_KEY`` env var.

    Returns
    -------
    list[SupabaseTimelineCandidate]
        Always a list (empty when config is absent or no timelines found).
    """
    import json as _json
    import os as _os
    import urllib.request as _request

    url = supabase_url or _os.environ.get("SUPABASE_URL", "").strip()
    key = service_role_key or _os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    # No credentials → skip gracefully (local-only mode)
    if not url or not key:
        return []

    base_url = url.rstrip("/")

    def _get_json(endpoint: str) -> Any:
        """Thin GET helper using the Reigh auth pattern (service_role)."""
        headers = {
            "Authorization": f"Bearer {key}",
            "apikey": key,
            "Accept": "application/json",
        }
        req = _request.Request(f"{base_url}{endpoint}", headers=headers, method="GET")
        try:
            with _request.urlopen(req, timeout=30.0) as resp:
                return _json.loads(resp.read().decode("utf-8"))
        except Exception:
            raise

    # ------------------------------------------------------------------
    # 1. List public.timelines (via Reigh transport seam — SD3)
    # ------------------------------------------------------------------
    try:
        timeline_endpoint = "/rest/v1/timelines?select=id,project_id,config_version"
        if project_id:
            from urllib.parse import quote
            timeline_endpoint += f"&project_id=eq.{quote(project_id, safe='')}"
        raw_timelines = _get_json(timeline_endpoint)
    except Exception:
        return []

    if not isinstance(raw_timelines, list):
        return []

    # ------------------------------------------------------------------
    # 2. For each timeline, check if timeline_events exist
    # ------------------------------------------------------------------
    candidates: list[SupabaseTimelineCandidate] = []
    for row in raw_timelines:
        if not isinstance(row, dict):
            continue
        tid = row.get("id")
        pid = row.get("project_id")
        if not isinstance(tid, str) or not tid:
            continue
        if not isinstance(pid, str):
            pid = ""

        has_events = False
        try:
            from urllib.parse import quote
            events_endpoint = (
                f"/rest/v1/timeline_events"
                f"?timeline_id=eq.{quote(tid, safe='')}"
                f"&limit=1&select=event_id"
            )
            events_result = _get_json(events_endpoint)
            if isinstance(events_result, list) and len(events_result) > 0:
                has_events = True
        except Exception:
            pass

        cv = row.get("config_version")
        candidates.append(
            SupabaseTimelineCandidate(
                project_id=pid,
                timeline_id=tid,
                has_config=True,
                has_events=has_events,
                config_version=cv if isinstance(cv, int) else None,
            )
        )

    return candidates


# ---------------------------------------------------------------------------
# Resumable checkpoint helpers
# ---------------------------------------------------------------------------


def checkpoint_path_for_run(
    project_slug: str,
    *,
    root: str | Path | None = None,
    run_ts: str | None = None,
) -> Path:
    """Return the path for a migration checkpoint file.

    Checkpoints live under ``<project>/runs/migrations/<timestamp>/``
    and are never written inside source timeline directories.
    """
    from astrid.core.project.paths import project_dir, validate_project_slug

    slug = validate_project_slug(project_slug)
    ts = run_ts if run_ts is not None else str(int(time.time()))
    return project_dir(slug, root=root) / "runs" / "migrations" / ts / "checkpoint.json"


def write_resumable_checkpoint(
    status: ResumableStatus,
    checkpoint_file: Path,
) -> None:
    """Persist *status* to *checkpoint_file* atomically."""
    from astrid.core.project.jsonio import write_json_atomic

    write_json_atomic(
        checkpoint_file,
        {
            "last_completed_project": status.last_completed_project,
            "last_completed_timeline_ulid": status.last_completed_timeline_ulid,
            "imported_count": status.imported_count,
            "skipped_count": status.skipped_count,
        },
    )


def read_resumable_checkpoint(checkpoint_file: Path) -> ResumableStatus | None:
    """Load a previously-saved checkpoint, or ``None``."""
    from astrid.core.project.jsonio import read_json

    if not checkpoint_file.is_file():
        return None
    try:
        data = read_json(checkpoint_file)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return ResumableStatus(
        last_completed_project=data.get("last_completed_project"),
        last_completed_timeline_ulid=data.get("last_completed_timeline_ulid"),
        imported_count=data.get("imported_count", 0),
        skipped_count=data.get("skipped_count", 0),
    )


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    # Sprint-2 compatibility
    "main",
    "audit",
    # Structured result types
    "MigrationResult",
    "SkippedTimeline",
    "ParityFailure",
    "ResumableStatus",
    "SupabaseTimelineCandidate",
    # Classification
    "TimelineClassification",
    "classify_timeline_dir",
    # Discovery (delegates to existing APIs)
    "discover_projects_for_migration",
    "discover_timelines_for_project",
    "discover_supabase_timelines",
    # Idempotent import
    "import_from_legacy_local",
    # Checkpointing
    "checkpoint_path_for_run",
    "write_resumable_checkpoint",
    "read_resumable_checkpoint",
]
