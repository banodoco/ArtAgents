"""Pure, event-sourced timeline snapshots.

This module deliberately does not use the timeline CRUD, repair, bridge, or
``LocalFsBackend.head`` paths.  A snapshot is projected and verified from the
same in-memory event read.  Display lifecycle events are projected over the
identity-sidecar root, with a plain ``display.json`` read only for legacy logs
that contain no display events.  ``assembly.head.json`` is diagnostic-only.
"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from uuid import UUID

from astrid.core.foundation.hash import sha256_file
from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.timeline.eventlog.projector import project_display
from astrid.core.timeline.events.schema import (
    TimelineEvent,
    with_event_hash,
)
from astrid.core.timeline.model import Display
from astrid.core.timeline.paths import validate_timeline_ulid
from astrid.core.timeline.projection import project_to_assembly
from astrid.core.timeline.resolution import resolve_asset_local_path
from astrid.packs.rendering.executors.timeline_visualize.snapshot_digest import (
    SNS_SCHEMA_VERSION,
    canonical_json_bytes,
    sha256_bytes,
    sns_digest,
)
from astrid.packs.rendering.executors.timeline_visualize.validate import (
    validate_structural,
)

_REGISTRY_EVENT_KIND = "timeline.asset_registry_replaced"
_DISPLAY_EVENT_KINDS = frozenset(
    {
        "timeline.created",
        "timeline.renamed",
        "timeline.default_set",
        "timeline.deleted",
    }
)
_READ_CHUNK_SIZE = 1024 * 1024


class ConcurrentAppendError(RuntimeError):
    """Raised when a stable event-log generation cannot be acquired."""


class SnapshotIntegrityError(RuntimeError):
    """Raised when authoritative snapshot input fails integrity validation."""


class _EventReadError(SnapshotIntegrityError):
    """Internal marker for an incomplete or malformed event-log read."""


@dataclass(frozen=True)
class TimelineSnapshot:
    """One deterministic, read-only view of a timeline event generation.

    ``project_slug`` and ``diagnostics`` are explicit additions to the core
    fields: the SNS v1 envelope requires the former, while stale-cache and
    skipped-media states require somewhere deterministic to be recorded.
    They do not otherwise broaden the authority of compatibility sidecars.
    """

    timeline_id: str
    timeline_ulid: str
    slug: str | None
    project_slug: str
    head_version: int
    last_event_id: str | None
    last_hash: str | None
    assembly: dict[str, Any]
    registry: dict[str, Any]
    display: dict[str, Any] | None
    events: list[dict[str, Any]]
    media_hashes: dict[str, str]
    assembly_sha256: str
    registry_sha256: str
    transcript_sha256: str | None
    diagnostics: tuple[str, ...] = ()

    def sns(self) -> str:
        """Return the canonical source-normalized-snapshot identity."""

        fields: dict[str, Any] = {
            "schema_version": SNS_SCHEMA_VERSION,
            "project_slug": self.project_slug,
            "timeline_uuid": self.timeline_id,
            "timeline_ulid": self.timeline_ulid,
            "head_version": self.head_version,
            "head_last_event_id": self.last_event_id,
            "head_last_hash": self.last_hash,
            "assembly_sha256": self.assembly_sha256,
            "registry_sha256": self.registry_sha256,
            "media_hashes": self.media_hashes,
        }
        if self.transcript_sha256 is not None:
            fields["transcript_sha256"] = self.transcript_sha256
        return sns_digest(fields)


def _dedupe_diagnostics(items: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def _read_required_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SnapshotIntegrityError(f"{label} is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SnapshotIntegrityError(
            f"{label} is invalid JSON: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise SnapshotIntegrityError(f"failed to read {label}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SnapshotIntegrityError(f"{label} must contain a JSON object")
    return raw


def _read_identity(timeline_dir: Path) -> tuple[str, str, Any]:
    identity = _read_required_object(
        timeline_dir / "assembly.identity.json",
        label="assembly.identity.json",
    )
    timeline_id = identity.get("timeline_id")
    if not isinstance(timeline_id, str):
        raise SnapshotIntegrityError("assembly.identity.json.timeline_id must be a string")
    try:
        canonical_id = str(UUID(timeline_id))
    except (ValueError, AttributeError) as exc:
        raise SnapshotIntegrityError(
            "assembly.identity.json.timeline_id must be a UUID"
        ) from exc
    if timeline_id != canonical_id:
        raise SnapshotIntegrityError(
            "assembly.identity.json.timeline_id must be a canonical UUID"
        )

    timeline_ulid = identity.get("timeline_ulid")
    try:
        canonical_ulid = validate_timeline_ulid(timeline_ulid)
    except ValueError as exc:
        raise SnapshotIntegrityError(
            "assembly.identity.json.timeline_ulid must be a canonical ULID"
        ) from exc
    return canonical_id, canonical_ulid, deepcopy(identity.get("display"))


def _read_display(timeline_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Plain-read the legacy display fallback without invoking repair."""

    path = timeline_dir / "display.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    except json.JSONDecodeError as exc:
        raise SnapshotIntegrityError(
            f"display.json is invalid JSON: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise SnapshotIntegrityError(f"failed to read display.json: {exc}") from exc
    try:
        display = Display.from_dict(raw)
    except ValueError as exc:
        raise SnapshotIntegrityError(f"display.json is invalid: {exc}") from exc
    return display.to_json_obj(), display.slug


def _display_from_captured_events(
    events: Sequence[TimelineEvent],
    *,
    timeline_dir: Path,
    identity_display: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    """Project display state from the captured generation when it is evented.

    Creation stores the original display in ``assembly.identity.json`` before
    the event log exists.  Current local CRUD emits rename events but may omit
    ``timeline.created``, so that immutable identity display is the replay
    baseline.  A live ``display.json`` is consulted only when the captured log
    has no display lifecycle event at all.
    """

    display_events = [event for event in events if event.kind in _DISPLAY_EVENT_KINDS]
    if not display_events:
        return _read_display(timeline_dir)

    try:
        projection = project_display(display_events)
    except ValueError as exc:
        raise SnapshotIntegrityError(
            f"captured display event projection failed: {exc}"
        ) from exc

    # A created event is a complete display root, and a deleted event can also
    # determine the final state without a baseline.  Rename/default-only logs
    # need the immutable creation display stored in the identity sidecar.
    if projection.display is None and not projection.deleted:
        if identity_display is None:
            raise SnapshotIntegrityError(
                "captured display events require assembly.identity.json.display "
                "as their replay baseline"
            )
        try:
            fallback_display = Display.from_dict(identity_display)
        except ValueError as exc:
            raise SnapshotIntegrityError(
                f"assembly.identity.json.display is invalid: {exc}"
            ) from exc
        try:
            projection = project_display(
                display_events,
                fallback_display=fallback_display,
            )
        except ValueError as exc:
            raise SnapshotIntegrityError(
                f"captured display event projection failed: {exc}"
            ) from exc

    if projection.deleted or projection.display is None:
        return None, None
    return projection.display.to_json_obj(), projection.display.slug


def _event_file_fingerprint(path: Path) -> tuple[int, int, int, int] | None:
    """Return identity/size/mtime facts sufficient for append detection."""

    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SnapshotIntegrityError(f"failed to stat {path}: {exc}") from exc
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


def _read_event_dicts(path: Path) -> list[dict[str, Any]]:
    """Read exactly one JSONL generation without using a backend repair path."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            events: list[dict[str, Any]] = []
            for line_number, line in enumerate(handle, start=1):
                if not line.endswith("\n"):
                    raise _EventReadError(
                        f"{path} line {line_number} is not newline-terminated"
                    )
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise _EventReadError(
                        f"invalid JSON in {path} line {line_number}: {exc.msg}"
                    ) from exc
                if not isinstance(raw, dict):
                    raise _EventReadError(
                        f"{path} line {line_number} must contain a JSON object"
                    )
                events.append(raw)
            return events
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise _EventReadError(f"failed to read {path}: {exc}") from exc


def _parse_events(
    events: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[TimelineEvent]]:
    if not isinstance(events, list):
        raise SnapshotIntegrityError("events must be a list")
    copied = deepcopy(events)
    parsed: list[TimelineEvent] = []
    for index, raw in enumerate(copied):
        try:
            parsed.append(TimelineEvent.from_dict(raw))
        except (TypeError, ValueError) as exc:
            raise SnapshotIntegrityError(
                f"event {index + 1} is schema-invalid: {exc}"
            ) from exc
    return copied, parsed


def _chain_diagnostics(
    events: Sequence[TimelineEvent],
    *,
    timeline_id: str,
) -> list[str]:
    """Verify the captured objects using LocalFsBackend.verify_chain semantics."""

    diagnostics: list[str] = []
    previous_hash: str | None = None
    for index, event in enumerate(events, start=1):
        if event.timeline_id != timeline_id:
            diagnostics.append(
                "EVENT_TIMELINE_MISMATCH: "
                f"event {index} {event.event_id} has timeline_id {event.timeline_id}, "
                f"expected {timeline_id}"
            )
        try:
            unhashed = TimelineEvent.from_dict(
                {**event.to_json_obj(), "hash": None}
            )
            expected = with_event_hash(unhashed, prev_hash=previous_hash)
        except (TypeError, ValueError) as exc:
            diagnostics.append(
                f"EVENT_HASH_UNVERIFIABLE: event {index} {event.event_id}: {exc}"
            )
            previous_hash = event.hash
            continue
        if event.prev_hash != previous_hash:
            diagnostics.append(
                "EVENT_PREV_HASH_MISMATCH: "
                f"event {index} {event.event_id} expected {previous_hash!r}, "
                f"found {event.prev_hash!r}"
            )
        if event.hash != expected.hash:
            diagnostics.append(
                "EVENT_HASH_MISMATCH: "
                f"event {index} {event.event_id} expected {expected.hash!r}, "
                f"found {event.hash!r}"
            )
        previous_hash = event.hash
    return diagnostics


def _registry_from_events(
    events: Sequence[TimelineEvent],
) -> tuple[dict[str, Any], list[str]]:
    """Return the last full registry event, mirroring the bridge reverse scan.

    The bridge helper is intentionally not called: its surrounding recovery
    path persists ``registry.json``.  The event carries a complete registry,
    so a reverse scan over the already captured events is sufficient.
    """

    skipped_replacements = 0
    for event in reversed(events):
        if event.kind != _REGISTRY_EVENT_KIND:
            continue
        registry = getattr(event.payload, "registry", None)
        if not isinstance(registry, dict):
            # Erasure repair keeps the original event kind but replaces its
            # payload.  Match local_bridge._registry_from_event_stream by
            # continuing to the newest still-usable full replacement.
            skipped_replacements += 1
            continue
        copied = deepcopy(registry)
        try:
            _validate_registry_envelope(copied)
        except (TypeError, ValueError) as exc:
            raise SnapshotIntegrityError(
                f"event {event.event_id} registry is invalid: {exc}"
            ) from exc
        diagnostics = []
        if skipped_replacements:
            diagnostics.append(
                "REGISTRY_REPLACEMENT_SKIPPED: "
                f"ignored {skipped_replacements} erased or unusable newer replacement(s)"
            )
        return copied, diagnostics
    return {"assets": {}}, [
        "REGISTRY_EVENT_MISSING: no timeline.asset_registry_replaced event; "
        "using an empty registry"
    ]


def _validate_registry_envelope(registry: Any) -> None:
    """Validate the event-owned envelope without narrowing asset metadata.

    The generic render registry validator intentionally rejects bridge
    provenance fields such as ``sourceId`` and ``sourceVersion`` that are
    present in canonical event history.  Snapshot authority must preserve
    those fields losslessly for R5, so only the stable full-registry shape and
    canonical JSON compatibility are checked here.
    """

    if not isinstance(registry, dict):
        raise ValueError("registry must be an object")
    assets = registry.get("assets")
    if not isinstance(assets, dict):
        raise ValueError("registry.assets must be an object")
    for asset_key, entry in assets.items():
        if not isinstance(asset_key, str) or not asset_key:
            raise ValueError("registry asset keys must be non-empty strings")
        if not isinstance(entry, dict):
            raise ValueError(f"registry asset {asset_key!r} must be an object")
    canonical_json_bytes(registry)


def _canonical_digest(value: Any) -> str:
    try:
        return sha256_bytes(canonical_json_bytes(value))
    except (TypeError, ValueError) as exc:
        raise SnapshotIntegrityError(f"value is not canonical JSON: {exc}") from exc


def _resolve_media_hashes(
    registry: dict[str, Any],
    *,
    project_root: Path | None,
) -> tuple[dict[str, str], list[str]]:
    """Hash only existing files contained by ``project_root/sources``.

    R5 owns the richer typed asset states; both contracts use the same local
    path resolver.  Deterministic diagnostics make every skip explicit without
    URL fetches, thumbnail fallback, or path escape.
    """

    if project_root is None:
        return {}, []

    resolved_project_root = Path(project_root).resolve()
    sources_root = (resolved_project_root / "sources").resolve()
    try:
        sources_root.relative_to(resolved_project_root)
    except ValueError:
        return {}, [
            "MEDIA_SOURCES_OUTSIDE_PROJECT: project sources root escapes project_root"
        ]
    assets = registry.get("assets", {})
    if not isinstance(assets, dict):
        raise SnapshotIntegrityError("registry.assets must be an object")

    hashes: dict[str, str] = {}
    diagnostics: list[str] = []
    by_path: dict[Path, str] = {}
    for asset_key in sorted(assets):
        entry = assets[asset_key]
        if not isinstance(entry, dict):
            diagnostics.append(
                f"MEDIA_INVALID_ENTRY: asset {asset_key!r} is not an object"
            )
            continue
        raw_file = entry.get("file")
        if not isinstance(raw_file, str) or not raw_file.strip():
            url = entry.get("url")
            state = (
                "MEDIA_REMOTE"
                if isinstance(url, str) and url.startswith(("http://", "https://"))
                else "MEDIA_NO_LOCAL_FILE"
            )
            diagnostics.append(f"{state}: asset {asset_key!r} was not hashed")
            continue
        raw_file = raw_file.strip()
        if raw_file.startswith(("http://", "https://")):
            diagnostics.append(
                f"MEDIA_REMOTE: asset {asset_key!r} file is remote and was not hashed"
            )
            continue

        candidate = resolve_asset_local_path(
            raw_file,
            project_root=resolved_project_root,
        )
        if candidate is None:
            diagnostics.append(
                f"MEDIA_MISSING: asset {asset_key!r} local file was not found"
            )
            continue

        observed = by_path.get(candidate)
        if observed is None:
            try:
                observed = sha256_file(candidate)
            except OSError as exc:
                raise SnapshotIntegrityError(f"failed to hash {candidate}: {exc}") from exc
            by_path[candidate] = observed
        hashes[asset_key] = observed
        expected = entry.get("content_sha256")
        if isinstance(expected, str) and expected != observed:
            diagnostics.append(
                f"MEDIA_HASH_MISMATCH: asset {asset_key!r} expected {expected}, "
                f"observed {observed}"
            )
    return hashes, diagnostics


def _read_head_sidecar(
    timeline_dir: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    path = timeline_dir / "assembly.head.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, []
    except json.JSONDecodeError as exc:
        return None, [
            f"HEAD_SIDECAR_INVALID: assembly.head.json is invalid JSON: {exc.msg}"
        ]
    except OSError as exc:
        return None, [f"HEAD_SIDECAR_UNREADABLE: {exc}"]
    if not isinstance(raw, dict):
        return None, ["HEAD_SIDECAR_INVALID: assembly.head.json is not an object"]
    return raw, []


def _head_sidecar_diagnostics(
    head: dict[str, Any] | None,
    *,
    timeline_id: str,
    events: Sequence[TimelineEvent],
) -> list[str]:
    if head is None:
        return []

    count = len(events)
    last_event_id = events[-1].event_id if events else None
    last_hash = events[-1].hash if events else None
    diagnostics: list[str] = []

    for field in ("version", "event_count"):
        value = head.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            diagnostics.append(
                f"HEAD_SIDECAR_INVALID: {field} must be an integer"
            )
            continue
        if value > count:
            diagnostics.append(
                "HEAD_SIDECAR_AHEAD: "
                f"assembly.head.json {field} {value} is ahead of captured "
                f"event count {count}"
            )
        if value < count:
            diagnostics.append(
                f"HEAD_SIDECAR_STALE: {field} is {value}, event tail is {count}"
            )

    if head.get("timeline_id") != timeline_id:
        diagnostics.append(
            "HEAD_SIDECAR_MISMATCH: timeline_id differs from assembly.identity.json"
        )
    if head.get("last_event_id") != last_event_id:
        diagnostics.append(
            "HEAD_SIDECAR_MISMATCH: last_event_id differs from the event tail"
        )
    if head.get("last_hash") != last_hash:
        diagnostics.append(
            "HEAD_SIDECAR_MISMATCH: last_hash differs from the event tail"
        )
    return diagnostics


def _build_snapshot(
    raw_events: list[dict[str, Any]],
    parsed_events: list[TimelineEvent],
    *,
    timeline_id: str,
    timeline_ulid: str,
    display: dict[str, Any] | None,
    slug: str | None,
    project_slug: str,
    project_root: Path | None,
    diagnostics: Sequence[str],
) -> TimelineSnapshot:
    try:
        assembly = project_to_assembly(parsed_events)
    except Exception as exc:
        raise SnapshotIntegrityError(f"event projection failed: {exc}") from exc
    structural_errors = validate_structural(assembly)
    if structural_errors:
        raise SnapshotIntegrityError(
            "projected assembly is invalid: " + "; ".join(structural_errors)
        )

    registry, registry_diagnostics = _registry_from_events(parsed_events)
    media_hashes, media_diagnostics = _resolve_media_hashes(
        registry,
        project_root=project_root,
    )
    last = parsed_events[-1] if parsed_events else None
    snapshot = TimelineSnapshot(
        timeline_id=timeline_id,
        timeline_ulid=timeline_ulid,
        slug=slug,
        project_slug=project_slug,
        head_version=len(parsed_events),
        last_event_id=last.event_id if last is not None else None,
        last_hash=last.hash if last is not None else None,
        assembly=assembly,
        registry=registry,
        display=display,
        events=deepcopy(raw_events),
        media_hashes=media_hashes,
        assembly_sha256=_canonical_digest(assembly),
        registry_sha256=_canonical_digest(registry),
        # Transcript authority is deliberately deferred to R19.  Never guess
        # a transcript from neighboring filenames or generic registry assets.
        transcript_sha256=None,
        diagnostics=_dedupe_diagnostics(
            [*diagnostics, *registry_diagnostics, *media_diagnostics]
        ),
    )
    return snapshot


def snapshot_from_events(
    events: list[dict[str, Any]],
    *,
    timeline_dir: Path,
    project_slug: str,
) -> TimelineSnapshot:
    """Project a snapshot from provided event dictionaries without writes.

    This helper intentionally does not reject a bad hash chain; callers can
    construct forensic fixtures and obtain exact diagnostics from
    :func:`verify_frozen`.  Event schema, projection, display, and registry
    shape are still validated.
    """

    timeline_dir = Path(timeline_dir)
    timeline_id, timeline_ulid, identity_display = _read_identity(timeline_dir)
    raw_events, parsed_events = _parse_events(events)
    display, slug = _display_from_captured_events(
        parsed_events,
        timeline_dir=timeline_dir,
        identity_display=identity_display,
    )
    head, diagnostics = _read_head_sidecar(timeline_dir)
    head_diagnostics = _head_sidecar_diagnostics(
        head,
        timeline_id=timeline_id,
        events=parsed_events,
    )
    return _build_snapshot(
        raw_events,
        parsed_events,
        timeline_id=timeline_id,
        timeline_ulid=timeline_ulid,
        display=display,
        slug=slug,
        project_slug=project_slug,
        project_root=None,
        diagnostics=[*diagnostics, *head_diagnostics],
    )


def _snapshot_projects_root(timeline_dir: Path, project_root: Path | None) -> Path:
    if project_root is not None:
        return Path(project_root)
    # timeline_dir = <projects_root>/<project>/timelines/<ulid>
    try:
        candidate = timeline_dir.parent.parent.parent
        if candidate.exists():
            return candidate
    except Exception:
        pass
    return resolve_projects_root(None)


def _is_timeline_backfilled(timeline_dir: Path, project_root: Path | None) -> tuple[bool, str | None]:
    """Return (is_backfilled, timeline_id_if_known).

    Reads identity sidecar to get timeline_id when present; when missing and
    the marker says backfilled via ULID lookup, resolves timeline_id from
    kernel. Fails closed on garbage marker (raises SnapshotIntegrityError).
    """
    projects_root = _snapshot_projects_root(timeline_dir, project_root)
    # Try to get timeline_id from identity when it exists.
    timeline_id: str | None = None
    identity_path = timeline_dir / "assembly.identity.json"
    if identity_path.is_file():
        try:
            from astrid.core._shared.jsonio import read_json as _read_json

            raw = _read_json(identity_path)
            if isinstance(raw, dict) and isinstance(raw.get("timeline_id"), str):
                timeline_id = str(raw["timeline_id"])
        except Exception:
            pass
    if timeline_id is None:
        # Fallback: try to derive timeline_id from kernel via ULID directory name.
        ulid = timeline_dir.name
        try:
            from astrid.core.integrations.reigh.bridge_service import derive_database_path
            import sqlite3

            db_path = derive_database_path(projects_root)
            if db_path.is_file():
                conn = sqlite3.connect(str(db_path))
                try:
                    conn.row_factory = sqlite3.Row
                    row = conn.execute(
                        "SELECT aggregate_id FROM event_streams WHERE stream_type = ? AND aggregate_id IN "
                        "(SELECT aggregate_id FROM event_streams WHERE id IN "
                        "(SELECT stream_id FROM events WHERE kind = ? AND json_extract(payload_json, '$.data.timeline_ulid') = ? LIMIT 1))",
                        ("timeline.timeline", "timeline.created", ulid),
                    ).fetchone()
                    # Simpler: directly search events for ulid
                    if row is None:
                        row2 = conn.execute(
                            "SELECT json_extract(payload_json, '$.data.timeline_id') as tid FROM events WHERE kind = ? AND json_extract(payload_json, '$.data.timeline_ulid') = ? LIMIT 1",
                            ("timeline.created", ulid),
                        ).fetchone()
                        if row2 is not None and row2["tid"]:
                            timeline_id = str(row2["tid"])
                    else:
                        timeline_id = str(row["aggregate_id"])
                finally:
                    conn.close()
        except Exception:
            pass
    # Consult marker.
    from astrid.packs.timeline.backfill import BackfillError, read_backfill_state

    try:
        state = read_backfill_state(projects_root)
    except BackfillError as exc:
        raise SnapshotIntegrityError(f"backfill authority marker is unreadable: {exc}") from exc
    except Exception as exc:  # pragma: no cover
        raise SnapshotIntegrityError(f"backfill authority marker is unreadable: {exc}") from exc
    if timeline_id is not None and timeline_id in state:
        return True, timeline_id
    # If we could not determine timeline_id, treat as not backfilled (legacy) unless
    # any marker entry matches this ULID's timeline? We already tried lookup, so not.
    return False, timeline_id


def _acquire_snapshot_from_kernel(
    timeline_dir: Path,
    *,
    project_slug: str,
    project_root: Path | None,
    timeline_id: str,
) -> TimelineSnapshot:
    """Kernel-backed snapshot for a backfilled timeline (single authority)."""
    projects_root = _snapshot_projects_root(timeline_dir, project_root)
    from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend

    backend = SqliteEventLogBackend(
        timeline_id=timeline_id,
        timeline_home=timeline_dir,
        projects_root=projects_root,
    )
    events = backend.read_events()
    if not events:
        raise SnapshotIntegrityError(f"kernel has no events for timeline {timeline_id!r}")
    raw_events = [e.to_json_obj() for e in events]
    # parsed_events already are TimelineEvent objects
    parsed_events = events
    # Derive identity from first created event or fallback.
    timeline_ulid = timeline_dir.name
    # Try to get ulid/name from created payload
    for ev in events:
        if ev.kind == "timeline.created":
            payload = ev.payload  # type: ignore[union-attr]
            if isinstance(payload, dict):
                if isinstance(payload.get("timeline_ulid"), str):
                    timeline_ulid = str(payload["timeline_ulid"])
                break
            # dataclass payload
            try:
                obj = payload.to_json_obj()  # type: ignore[union-attr]
                if isinstance(obj.get("timeline_ulid"), str):
                    timeline_ulid = str(obj["timeline_ulid"])
                    break
            except Exception:
                pass
    # Display projection from events (same as file path but without sidecar)
    identity_display = None
    # Try to use kernel display: project_display would normally need events
    # Use _display_from_captured_events helper which already handles event projection.
    # For kernel we have no identity sidecar display, so pass None then fallback to
    # projection.
    display, slug = _display_from_captured_events(
        parsed_events,
        timeline_dir=timeline_dir,
        identity_display=identity_display,
    )
    # If still None (legacy timeline with no display events), fallback to default.
    if display is None:
        display = {"schema_version": 2, "slug": project_slug, "name": project_slug, "is_default": False}
        slug = str(display.get("slug", project_slug))
    return _build_snapshot(
        raw_events,
        parsed_events,
        timeline_id=timeline_id,
        timeline_ulid=timeline_ulid,
        display=display,
        slug=slug or project_slug,
        project_slug=project_slug,
        project_root=project_root,
        diagnostics=[],
    )


def acquire_snapshot(
    timeline_dir: Path,
    *,
    project_slug: str,
    project_root: Path | None = None,
    retries: int = 2,
) -> TimelineSnapshot:
    """Acquire one verified, stable event-sourced timeline snapshot.

    ``retries`` is the number of complete retries after the initial attempt.
    Only a changed JSONL fingerprint discards an attempt.  Every head-sidecar
    mismatch is diagnostic because the captured event tail is authoritative.
    For backfilled timelines (R5 marker present) the snapshot is served from
    kernel SQLite reads; legacy un-backfilled dirs keep the exact file path.
    One timeline never straddles both authorities.
    """

    if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
        raise ValueError("retries must be a non-negative integer")

    # R5 gate: check marker before touching files.
    try:
        is_backfilled, known_id = _is_timeline_backfilled(Path(timeline_dir), project_root)
    except SnapshotIntegrityError:
        raise
    except Exception as exc:
        raise SnapshotIntegrityError(f"failed to check backfill marker: {exc}") from exc
    if is_backfilled and known_id is not None:
        return _acquire_snapshot_from_kernel(
            Path(timeline_dir),
            project_slug=project_slug,
            project_root=Path(project_root) if project_root is not None else None,
            timeline_id=known_id,
        )

    timeline_dir = Path(timeline_dir)
    normalized_project_root = Path(project_root) if project_root is not None else None
    events_path = timeline_dir / "assembly.jsonl"
    attempts = retries + 1

    for attempt in range(attempts):
        before = _event_file_fingerprint(events_path)
        try:
            timeline_id, timeline_ulid, identity_display = _read_identity(timeline_dir)
            raw_events = _read_event_dicts(events_path)
            raw_events, parsed_events = _parse_events(raw_events)
            chain_errors = _chain_diagnostics(
                parsed_events,
                timeline_id=timeline_id,
            )
            if chain_errors:
                raise SnapshotIntegrityError("; ".join(chain_errors))

            display, slug = _display_from_captured_events(
                parsed_events,
                timeline_dir=timeline_dir,
                identity_display=identity_display,
            )
            head, diagnostics = _read_head_sidecar(timeline_dir)
            head_diagnostics = _head_sidecar_diagnostics(
                head,
                timeline_id=timeline_id,
                events=parsed_events,
            )
            snapshot = _build_snapshot(
                raw_events,
                parsed_events,
                timeline_id=timeline_id,
                timeline_ulid=timeline_ulid,
                display=display,
                slug=slug,
                project_slug=project_slug,
                project_root=normalized_project_root,
                diagnostics=[*diagnostics, *head_diagnostics],
            )
        except SnapshotIntegrityError as exc:
            after = _event_file_fingerprint(events_path)
            if before != after:
                if attempt + 1 < attempts:
                    continue
                raise ConcurrentAppendError(
                    f"could not acquire a stable snapshot after {attempts} attempt(s): "
                    "assembly.jsonl changed during acquisition"
                ) from exc
            raise

        after = _event_file_fingerprint(events_path)
        if before != after:
            if attempt + 1 < attempts:
                continue
            raise ConcurrentAppendError(
                f"could not acquire a stable snapshot after {attempts} attempt(s): "
                "assembly.jsonl changed during acquisition"
            )

        try:
            snapshot.sns()
        except (TypeError, ValueError) as exc:
            raise SnapshotIntegrityError(
                f"snapshot identity is invalid: {exc}"
            ) from exc
        return snapshot

    raise AssertionError("snapshot acquisition loop exited unexpectedly")


def verify_frozen(
    snapshot: TimelineSnapshot,
    *,
    expect_version: int | None = None,
) -> list[str]:
    """Re-verify only the data frozen into *snapshot* and return diagnostics."""

    diagnostics = list(snapshot.diagnostics)
    try:
        _raw_events, parsed_events = _parse_events(snapshot.events)
    except SnapshotIntegrityError as exc:
        diagnostics.append(f"EVENT_SCHEMA_INVALID: {exc}")
        return list(_dedupe_diagnostics(diagnostics))

    diagnostics.extend(
        _chain_diagnostics(parsed_events, timeline_id=snapshot.timeline_id)
    )
    if expect_version is not None:
        if (
            isinstance(expect_version, bool)
            or not isinstance(expect_version, int)
            or expect_version < 0
        ):
            diagnostics.append(
                "EXPECTED_VERSION_INVALID: expect_version must be a non-negative integer"
            )
        elif snapshot.head_version != expect_version:
            diagnostics.append(
                "EXPECTED_VERSION_MISMATCH: "
                f"expected {expect_version}, found {snapshot.head_version}"
            )

    if snapshot.head_version != len(parsed_events):
        diagnostics.append(
            "HEAD_VERSION_MISMATCH: "
            f"snapshot says {snapshot.head_version}, events contain {len(parsed_events)}"
        )
    expected_event_id = parsed_events[-1].event_id if parsed_events else None
    expected_hash = parsed_events[-1].hash if parsed_events else None
    if snapshot.last_event_id != expected_event_id:
        diagnostics.append(
            "HEAD_EVENT_ID_MISMATCH: snapshot tail does not match frozen events"
        )
    if snapshot.last_hash != expected_hash:
        diagnostics.append(
            "HEAD_HASH_MISMATCH: snapshot tail hash does not match frozen events"
        )

    try:
        replayed = project_to_assembly(parsed_events)
        structural_errors = validate_structural(replayed)
        for error in structural_errors:
            diagnostics.append(f"ASSEMBLY_INVALID: {error}")
        if replayed != snapshot.assembly:
            diagnostics.append(
                "ASSEMBLY_REPLAY_MISMATCH: frozen assembly differs from event replay"
            )
    except Exception as exc:
        diagnostics.append(f"ASSEMBLY_REPLAY_FAILED: {exc}")

    try:
        observed_assembly_hash = _canonical_digest(snapshot.assembly)
        if observed_assembly_hash != snapshot.assembly_sha256:
            diagnostics.append(
                "ASSEMBLY_DIGEST_MISMATCH: frozen assembly digest is incorrect"
            )
    except SnapshotIntegrityError as exc:
        diagnostics.append(f"ASSEMBLY_DIGEST_INVALID: {exc}")

    try:
        replayed_registry, registry_warnings = _registry_from_events(parsed_events)
        diagnostics.extend(registry_warnings)
        if replayed_registry != snapshot.registry:
            diagnostics.append(
                "REGISTRY_REPLAY_MISMATCH: frozen registry differs from the last registry event"
            )
    except SnapshotIntegrityError as exc:
        diagnostics.append(f"REGISTRY_REPLAY_FAILED: {exc}")

    try:
        _validate_registry_envelope(snapshot.registry)
        observed_registry_hash = _canonical_digest(snapshot.registry)
        if observed_registry_hash != snapshot.registry_sha256:
            diagnostics.append(
                "REGISTRY_DIGEST_MISMATCH: frozen registry digest is incorrect"
            )
    except (SnapshotIntegrityError, TypeError, ValueError) as exc:
        diagnostics.append(f"REGISTRY_INVALID: {exc}")

    try:
        snapshot.sns()
    except (TypeError, ValueError) as exc:
        diagnostics.append(f"SNS_INVALID: {exc}")
    return list(_dedupe_diagnostics(diagnostics))


__all__ = [
    "ConcurrentAppendError",
    "SnapshotIntegrityError",
    "TimelineSnapshot",
    "acquire_snapshot",
    "snapshot_from_events",
    "verify_frozen",
]
