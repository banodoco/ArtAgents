"""Library support for timeline migration classification and discovery.

Provides:
- Dataclasses for structured migration results
- Project discovery using existing project discovery APIs
- Timeline directory classification (already-event-sourced, legacy-local,
  malformed/incomplete)
- Read-only source blob classification that never mutates files

The sprint-2 migration script at
``scripts/migrations/sprint-2/migrate_timelines.py`` remains the supported
runnable surface for legacy migration. This module intentionally keeps only
the live classification, discovery, and import helpers used by runtime code
and tests.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from astrid.core.contracts.remote_timeline import RemoteTimelineLister

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
    malformed: list[str] = field(default_factory=list)  # timeline ULIDs
    resumable: ResumableStatus = field(default_factory=ResumableStatus)
    started_at: str = ""
    finished_at: str = ""

    @property
    def ok(self) -> bool:
        return len(self.parity_failures) == 0 and len(self.malformed) == 0


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
    from astrid.core.foundation.project_paths import resolve_projects_root, validate_project_slug
    from astrid.core.threads.ids import is_ulid

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
            from astrid.core._shared.jsonio import read_json
            identity = read_json(identity_path)
            if isinstance(identity, dict) and "timeline_id" in identity:
                return "already_event_sourced"
        except Exception:
            pass  # fall through to malformed

    # Legacy-local: assembly.json exists but no event log.
    if assembly_path.is_file() and not events_path.is_file():
        try:
            from astrid.core._shared.jsonio import read_json
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
    """Reject runtime legacy-local conversion.

    Historical ``assembly.json`` wrappers and old full-state snapshots are
    decoded only by ``scripts/migrations/sprint-2``. This runtime entry point is
    retained as a compatibility import surface, but it must fail closed instead
    of appending ``timeline.imported`` or unwrapping legacy blobs.
    """
    return {
        "ok": False,
        "imported": False,
        "event_id": None,
        "parity_ok": None,
        "detail": (
            "runtime legacy-local import is disabled; run "
            "scripts/migrations/sprint-2/migrate_timelines.py"
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
    lister: RemoteTimelineLister | None = None,
    project_id: str | None = None,
    supabase_url: str | None = None,
    service_role_key: str | None = None,
) -> list[SupabaseTimelineCandidate]:
    """List candidate Supabase timelines for migration.

    Discovery uses an injected :class:`RemoteTimelineLister` (the structural
    contract in ``astrid.core.contracts.remote_timeline``) so that the timeline
    tier does not depend on the higher ``integrations.reigh`` transport. The
    caller injects the concrete reigh implementation; the
    ``astrid.core.integrations.reigh.timeline_io`` module satisfies the Protocol
    directly (its ``list_timelines`` / ``timeline_has_events`` functions match).

    **No-credentials behaviour**: when *supabase_url* and *service_role_key*
    are both absent (the default local-only scenario), this function
    returns an empty list immediately without any network calls — and without
    requiring a *lister*.

    Parameters
    ----------
    lister:
        Remote timeline transport seam. Required whenever credentials are
        present (the network path); ignored in the no-credentials short-circuit.
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
    import os as _os

    url = supabase_url or _os.environ.get("SUPABASE_URL", "").strip()
    key = service_role_key or _os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    # No credentials → skip gracefully (local-only mode)
    if not url or not key:
        return []

    if lister is None:
        raise ValueError(
            "discover_supabase_timelines requires a RemoteTimelineLister when "
            "credentials are present; inject astrid.core.integrations.reigh."
            "timeline_io"
        )

    # Build service-role auth tuple (matching supabase_client.Auth contract)
    auth = ("service_role", key)

    # ------------------------------------------------------------------
    # 1. List public.timelines via the injected Reigh transport seam (SD3)
    # ------------------------------------------------------------------
    raw_timelines = lister.list_timelines(
        supabase_url=url,
        auth=auth,
        project_id=project_id,
    )

    # ------------------------------------------------------------------
    # 2. For each timeline, check if timeline_events exist
    # ------------------------------------------------------------------
    candidates: list[SupabaseTimelineCandidate] = []
    for row in raw_timelines:
        tid = row.get("id")
        pid = row.get("project_id")
        if not isinstance(tid, str) or not tid:
            continue
        if not isinstance(pid, str):
            pid = ""

        has_events = lister.timeline_has_events(
            supabase_url=url,
            auth=auth,
            timeline_id=tid,
        )

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
# Idempotent Supabase config import (T5)
# ---------------------------------------------------------------------------


def import_supabase_config(
    *,
    backend: Any,
    project_id: str,
    timeline_id: str,
    config: dict[str, Any],
    actor: Any,
    config_version: int | None = None,
) -> dict[str, Any]:
    """Idempotently seed a Supabase TimelineConfig with ``timeline.config_replaced``.

    Per SD2, parity is **config-as-snapshot**: the stored snapshot must equal
    the source config blob — NOT projected assembly.  This is a different data
    model from the LocalFs path, where the source blob is an assembly document.

    (a) When the event log is empty, validates *config* as a raw TimelineConfig
        and appends exactly one ``timeline.config_replaced`` event.

    (b) Idempotent guard: if the first event is already
        ``timeline.config_replaced`` and full-config parity
        holds, returns immediately without appending.

    (c) ``timeline.imported`` remains migration-only legacy and is never
        emitted by this runtime path.

    Parameters
    ----------
    backend:
        A ``SupabaseBackend`` instance or compatible mock with the same
        ``read_events()`` / ``append_event()`` surface.
    project_id:
        Supabase project identifier (used for logging / error messages only).
    timeline_id:
        Supabase timeline identifier.
    config:
        The full Reigh config blob (as loaded from ``public.timelines.config``
        via the Reigh transport seam).
    actor:
        ``TimelineActor`` recorded on the imported event.
    config_version:
        Optional config version from Supabase (for logging / audit).

    Returns
    -------
    dict
        Keys: ``ok`` (bool), ``imported`` (bool), ``event_id`` (str|None),
        ``parity_ok`` (bool | None), ``detail`` (str), ``skipped_state``
        (str|None).  ``skipped_state`` is one of ``"already_imported"``,
        ``"already_event_sourced"``, ``"no_config"``, or ``None``.
    """
    from astrid.core.timeline.banodoco_schema import (
        canonical_timeline_config,
        timeline_configs_equal,
    )

    # ------------------------------------------------------------------
    # 0. Null config guard
    # ------------------------------------------------------------------
    if not config or not isinstance(config, dict):
        return {
            "ok": False,
            "imported": False,
            "event_id": None,
            "parity_ok": None,
            "detail": "No config blob provided — nothing to import",
            "skipped_state": "no_config",
        }

    try:
        validated_config = canonical_timeline_config(config)
    except Exception as exc:
        return {
            "ok": False,
            "imported": False,
            "event_id": None,
            "parity_ok": None,
            "detail": f"Supabase config is not a raw TimelineConfig: {exc}",
            "skipped_state": "invalid_config",
        }

    # ------------------------------------------------------------------
    # 1. Read existing event stream
    # ------------------------------------------------------------------
    events = backend.read_events()

    # ------------------------------------------------------------------
    # 2. Idempotence: if already imported, verify config-as-snapshot parity
    # ------------------------------------------------------------------
    if events:
        first = events[0]

        if first.kind == "timeline.config_replaced":
            stored_config = (
                first.payload.config if hasattr(first.payload, "config") else None
            )
            parity_ok = (
                isinstance(stored_config, dict)
                and timeline_configs_equal(
                    stored_config, validated_config
                )
            )

            if parity_ok:
                return {
                    "ok": True,
                    "imported": False,
                    "event_id": first.event_id,
                    "parity_ok": True,
                    "detail": "Already imported — TimelineConfig parity holds, skipping",
                    "skipped_state": "already_imported",
                }
            return {
                "ok": False,
                "imported": False,
                "event_id": first.event_id,
                "parity_ok": False,
                "detail": "Already imported but TimelineConfig parity does NOT hold",
                "skipped_state": None,
            }

        # Stream exists but first event is not a matching full-config seed.
        return {
            "ok": False,
            "imported": False,
            "event_id": None,
            "parity_ok": None,
            "detail": (
                f"Event log is not empty and first event is "
                f"{first.kind!r}, not timeline.config_replaced — "
                f"refusing to import"
            ),
            "skipped_state": "already_event_sourced",
        }

    # ------------------------------------------------------------------
    # 3. Event log is empty — perform the import
    # ------------------------------------------------------------------
    try:
        event = backend.append_event(
            timeline_id,
            "timeline.config_replaced",
            {
                "config": validated_config,
            },
            actor=actor,
        )
    except Exception as exc:
        return {
            "ok": False,
            "imported": False,
            "event_id": None,
            "parity_ok": None,
            "detail": f"Failed to append timeline.config_replaced: {exc}",
            "skipped_state": None,
        }

    # ------------------------------------------------------------------
    # 4. Verify full-config parity
    # ------------------------------------------------------------------
    all_events = backend.read_events()
    if all_events:
        imported_event = all_events[0]
        stored_config = (
            imported_event.payload.config
            if hasattr(imported_event.payload, "config")
            else None
        )
        parity_ok = (
            isinstance(stored_config, dict)
            and timeline_configs_equal(stored_config, validated_config)
        )
    else:
        parity_ok = False

    return {
        "ok": parity_ok,
        "imported": True,
        "event_id": event.event_id,
        "parity_ok": parity_ok,
        "detail": (
            "Import succeeded, TimelineConfig parity matches"
            if parity_ok
            else "Import succeeded but TimelineConfig parity does NOT match"
        ),
        "skipped_state": None,
    }


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
    from astrid.core.foundation.project_paths import project_dir, validate_project_slug

    slug = validate_project_slug(project_slug)
    ts = run_ts if run_ts is not None else str(int(time.time()))
    return project_dir(slug, root=root) / "runs" / "migrations" / ts / "checkpoint.json"


def write_resumable_checkpoint(
    status: ResumableStatus,
    checkpoint_file: Path,
) -> None:
    """Persist *status* to *checkpoint_file* atomically."""
    from astrid.core._shared.jsonio import write_json_atomic

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
    from astrid.core._shared.jsonio import read_json

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
    "import_supabase_config",
    # Checkpointing
    "checkpoint_path_for_run",
    "write_resumable_checkpoint",
    "read_resumable_checkpoint",
]
