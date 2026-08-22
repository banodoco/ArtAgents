"""SQLite-cutover backfill: JSONL / Supabase-export -> kernel events, zero-loss.

This is the S1 product surface that drives the recorded cutover (North Star:
local-first SQLite for reigh timelines). For every timeline it migrates the
immutable source event stream into the kernel ``events`` table 1:1 — one
kernel stream row per timeline, ``event_streams.head_seq`` EXACTLY equal to
the source ``assembly.head.json`` version after import — plus the
whole-document ``timelines`` projection (projected config + projected
registry), all in one ``BEGIN IMMEDIATE`` unit of work. The editor CAS
continues seamlessly: a bridge save against the backfilled head appends the
next event at ``head_seq + 1``.

Decision fed (recorded cutover): the backfilled SQLite database is the
authoritative store replacing JSONL files and the Supabase eventlog. This
verb is a **new product surface for the recorded cutover** — deliberately
distinct from the retired legacy migration/push/pull/sync verbs, which are
absent from the product CLI and never return.

Immutability guarantee (R4): source exports are never mutated. The importer
reads ``assembly.jsonl`` / ``assembly.identity.json`` /
``assembly.head.json`` read-only (the head sidecar is parsed directly, never
healed through ``LocalFsBackend.head()``, so a corrupt sidecar fails closed
instead of being rewritten), and Supabase exports are read from a file. The
import copies nothing into the source directories: its only writes are the
kernel database at ``<projects_root>/.astrid/astrid.sqlite3``, the run
checkpoint under ``<project>/runs/migrations/<ts>/checkpoint.json``, and the
authority marker at ``<projects_root>/.astrid/backfill-state.json``.

Authority marker (R5) — schema documented here as the contract:

    ``<projects_root>/.astrid/backfill-state.json`` (atomic write via
    ``astrid.core.foundation.atomic_io.write_json_atomic``)::

        {
          "<timeline_id>": {
            "backfilled_at": "<iso-8601-utc>",
            "source": "local_fs" | "supabase_export",
            "source_head_version": <int>,
            "events_sha256": "<sha256 hex of the canonical source events>"
          }
        }

The marker is written ONLY after every zero-loss invariant passes (see
:func:`verify_backfill`). A failed import writes NO marker and leaves NO
authority claim. Any later request whose source/head/sha disagree with the
marker for the same timeline is refused with :class:`BackfillAuthorityError`
(no authority mixing per timeline).

Zero-loss invariants (each backfilled timeline fails closed unless ALL hold;
the checker is reusable — :func:`verify_backfill`):

a. source event count == kernel event count for the mapped stream;
b. head continuity: source ``assembly.head.json`` version ==
   ``event_streams.head_seq`` after import;
c. content projection: for every source event the preserved fields
   (``kind``, payload ``data``, ``actor_kind``, ``created_at``, ``event_id``)
   are canonically equal to the kernel row; see :func:`map_source_event` for
   the exact field mapping and the documented drops/additions;
d. idempotency: running the same import twice yields ZERO new kernel events
   and an unchanged head (kernel identical-replay semantic: the per-timeline
   command receipt replays the stored result);
e. unknown-kind pass-through: per-kind counts are preserved, including kinds
   the timeline schema does not register (raw-dict payloads);
f. the marker is written only after (a)-(e) hold; a failed import writes no
   marker.

Field mapping ``LocalFs/Supabase TimelineEvent -> kernel events`` (invariant
c), derived from the conversion in ``astrid/core/timeline/migration.py`` and
``astrid/core/timeline/eventlog/reigh_events.py``:

- ``kind``            -> ``events.kind`` (verbatim; unknown kinds pass through
  as raw dicts per ``coerce_payload``);
- ``payload``         -> ``events.payload_json`` ``data`` (verbatim, wrapped
  in the canonical SD2 integrity envelope);
- ``actor.type``      -> ``events.actor_kind`` via the derived mapping
  ``agent -> executor``, ``human -> local``, ``system -> system`` (the kernel
  CHECK vocabulary is ``local|system|executor``; the mapping is deterministic
  and part of the contract);
- ``ts``              -> ``events.created_at`` (verbatim);
- ``event_id``        -> ``events.event_id`` (verbatim, kernel PK);
- ``txn_id``          -> ``events.txn_id`` (verbatim when present, else
  deterministically derived from the source event id);
- ``payload`` keys    -> ``events.changes_json`` (derived: sorted payload
  keys; documented, not compared for equality);
- ``schema_version``  -> NOT copied: the source ``schema_version`` is the
  timeline-eventlog schema axis; ``events.schema_version`` is the kernel
  envelope axis and stays 1 (documented drop, not load-bearing);
- ``prev_hash``/``hash`` -> NOT copied: the kernel chains its own SD2
  envelope hashes (``previous_event_hash``/``event_hash``) inside
  ``payload_json`` (documented drop, replaced by the kernel chain);
- ``actor.id``/``actor.display``/``actor.via`` -> NOT copied: the frozen
  ``events`` table has only ``actor_kind`` (R1 forbids new columns). The
  kernel/bridge never reads actor identity beyond the kind, so the drop is
  not load-bearing (documented);
- ``expected_version`` -> NOT copied: the kernel stream head IS the version
  (documented drop, not load-bearing);
- ``timeline.created`` data -> ENRICHED with ``timeline_ulid`` taken from
  the source identity sidecar (or deterministically derived for
  ``supabase_export`` sources). The timeline schema's created payload has
  only ``{timeline_id, slug, name}``, but kernel alias resolution
  (``show``/``list``/``save``) reads ``data.timeline_ulid`` from the
  ``timeline.created`` event, so the conversion adds exactly that one field;
  every source field stays verbatim (documented addition, load-bearing for
  bridge addressability).

Interruption/resume: each timeline imports in ONE unit of work (a killed
process rolls the whole timeline back — no partial timeline), the per-timeline
command receipt replays identical retries with zero new rows, and the
per-project run loop reuses the checkpoint machinery from
``astrid/core/timeline/migration.py`` (``checkpoint_path_for_run`` /
``write_resumable_checkpoint`` / ``read_resumable_checkpoint``) so a resumed
run skips already-completed timelines. Convergence: an interrupted run
followed by a resume reaches exactly the same database state as an
uninterrupted run (proven by ``tests/timeline/test_backfill_resume.py``).

Supabase-export leg: the documented envelope is the
``VersionedTimelineEvent.to_append_json_obj()`` shape (per-timeline
contiguous 1-based ``version``, ``prev_hash`` chain) — exactly the
``p_events`` payload of the ``append_timeline_event`` RPC, so a cloud export
``SELECT ... ORDER BY version`` feeds this importer directly. Reads go
through the same ``EventLogBackend`` seam as local_fs; tests inject a mocked
transport (``tests/timeline/test_transfer.py`` pattern). The single remaining
operational step is documented in the CLI help and here: export the live
deployed Supabase ``public.timeline_events`` rows (version-ordered, per
timeline) to a file and run ``astrid timelines backfill --from
supabase-export <path>``. No credentials are needed on this box and none are
read by this module.

How to read results: each timeline yields a JSON report (see
:func:`backfill_timeline`) with the source/kernel counts, head versions,
per-kind counts, ``events_sha256``, every check outcome, the marker path and
write state, and the projected config/registry signatures. Exit code 0 means
every imported timeline passed every invariant; any discrepancy fails the
command closed (exit 1) with no marker written for the failed timeline.
"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.events.service import build_integrity_envelope
from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.project_paths import (
    resolve_projects_root,
    validate_project_slug,
)
from astrid.core.integrations.reigh.bridge_service import ASTROID_DIR_NAME
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
    parse_json,
    request_hash,
)
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.errors import RepositoryError
from astrid.core.repositories.events import EventRepository
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
from astrid.core.timeline.events.schema import (
    TimelineActor,
    TimelineEvent,
    canonical_json_bytes,
)
from astrid.core.timeline.projection import replay_projection
from astrid.core.util.time import utc_now_iso

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BACKFILL_COMMAND_KIND = "timeline.backfill"
"""Receipt command kind for one timeline backfill (receipts table only; not a
declared pack command kind — the backfill writes through the typed
``UnitOfWork.append_event`` surface, not the registry-validating event
append service, because source event kinds exceed the four declared timeline
kinds by design (unknown-kind pass-through, invariant e)."""

BACKFILL_STATE_FILENAME = "backfill-state.json"
"""Authority-marker file name beside the database (R5)."""

BACKFILL_MARKER_SOURCE_LOCAL_FS = "local_fs"
BACKFILL_MARKER_SOURCE_SUPABASE = "supabase_export"

_TIMELINE_STREAM_TYPE = "timeline.timeline"
_TIMELINE_CREATED_KIND = "timeline.created"
_TIMELINE_ASSET_REGISTRY_REPLACED_KIND = "timeline.asset_registry_replaced"
_ACTOR_KIND_MAP: Mapping[str, str] = {
    "agent": "executor",
    "human": "local",
    "system": "system",
}
"""Derived source-actor-type -> kernel ``actor_kind`` mapping (kernel CHECK
vocabulary is ``local|system|executor``; see module docstring)."""

_CROCKFORD_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
"""Lowercase Crockford base32 alphabet (no I, L, O, U), mirroring the SDK's
deterministic ULID alias derivation."""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BackfillError(RepositoryError):
    """Base error for the SQLite-cutover backfill.

    Subclasses :class:`astrid.core.repositories.errors.RepositoryError` so
    the kernel store error family catches backfill contract violations. All
    messages avoid absolute filesystem paths so SDK redaction never mangles
    them.
    """


class BackfillAuthorityError(BackfillError):
    """A backfill request would mix authorities for one timeline.

    The marker already records a source/head/sha for this timeline and the
    new request disagrees with it. Fail closed (R5): refuse before any write.
    """


class BackfillDiscrepancyError(BackfillError):
    """A zero-loss invariant did not hold; the import failed closed."""


class BackfillSourceError(BackfillError):
    """The source export is missing, unreadable, or internally inconsistent."""


# ---------------------------------------------------------------------------
# Structured result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BackfillSource:
    """One validated, immutable source export (never mutated by the import)."""

    source_name: str  # "local_fs" | "supabase_export"
    timeline_id: str
    timeline_ulid: str
    name: str | None
    events: tuple[TimelineEvent, ...]  # ordered 1..head_version
    head_version: int
    events_sha256: str
    projected_config: dict[str, Any]
    projected_registry: dict[str, Any]  # {"assets": {...}}

    @property
    def kind_counts(self) -> dict[str, int]:
        return dict(Counter(event.kind for event in self.events))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_name,
            "timeline_id": self.timeline_id,
            "timeline_ulid": self.timeline_ulid,
            "source_event_count": len(self.events),
            "source_head_version": self.head_version,
            "events_sha256": self.events_sha256,
            "kinds": self.kind_counts,
            "projected_config_sha256": sha256_hex(self.projected_config),
            "projected_registry_sha256": sha256_hex(self.projected_registry),
        }


@dataclass(frozen=True, slots=True)
class BackfillVerification:
    """The reusable zero-loss verification for one backfilled timeline.

    ``mismatches`` carries one human-readable detail per failing invariant so
    a discrepancy is actionable; ``ok`` is False unless (a) count, (b) head,
    (c) content, and (e) per-kind preservation all hold.
    """

    source_event_count: int
    kernel_event_count: int
    source_head_version: int
    kernel_head_seq: int
    source_kinds: dict[str, int]
    kernel_kinds: dict[str, int]
    mismatches: tuple[str, ...] = ()

    @property
    def count_ok(self) -> bool:
        return self.source_event_count == self.kernel_event_count

    @property
    def head_ok(self) -> bool:
        return self.source_head_version == self.kernel_head_seq

    @property
    def content_ok(self) -> bool:
        return not any(item.startswith("content") for item in self.mismatches)

    @property
    def kinds_ok(self) -> bool:
        return self.source_kinds == self.kernel_kinds

    @property
    def ok(self) -> bool:
        return (
            self.count_ok
            and self.head_ok
            and self.content_ok
            and self.kinds_ok
            and not self.mismatches
        )

    def checks_dict(self) -> dict[str, bool]:
        return {
            "count": self.count_ok,
            "head": self.head_ok,
            "content": self.content_ok,
            "kinds": self.kinds_ok,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_event_count": self.source_event_count,
            "kernel_event_count": self.kernel_event_count,
            "source_head_version": self.source_head_version,
            "kernel_head_seq": self.kernel_head_seq,
            "source_kinds": self.source_kinds,
            "kernel_kinds": self.kernel_kinds,
            "checks": self.checks_dict(),
            "mismatches": list(self.mismatches),
        }


@dataclass(frozen=True, slots=True)
class BackfillReport:
    """The immutable per-timeline result of one backfill (JSON-ready).

    ``written`` is True only when the import committed and the marker was
    written; ``replayed`` is True when an identical earlier import's receipt
    was replayed with zero new rows; ``dry_run`` reports without writing.
    """

    project: str
    timeline_id: str
    timeline_ulid: str
    source: str
    source_event_count: int
    kernel_event_count: int
    source_head_version: int
    kernel_head_seq: int
    events_sha256: str
    kinds: dict[str, int]
    checks: dict[str, bool]
    marker_path: str
    marker_written: bool
    written: bool
    replayed: bool
    dry_run: bool
    projected_config_sha256: str
    projected_registry_sha256: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "timeline_id": self.timeline_id,
            "timeline_ulid": self.timeline_ulid,
            "source": self.source,
            "source_event_count": self.source_event_count,
            "kernel_event_count": self.kernel_event_count,
            "source_head_version": self.source_head_version,
            "kernel_head_seq": self.kernel_head_seq,
            "events_sha256": self.events_sha256,
            "kinds": dict(self.kinds),
            "checks": dict(self.checks),
            "marker_path": self.marker_path,
            "marker_written": self.marker_written,
            "written": self.written,
            "replayed": self.replayed,
            "dry_run": self.dry_run,
            "projected_config_sha256": self.projected_config_sha256,
            "projected_registry_sha256": self.projected_registry_sha256,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def sha256_hex(value: Any) -> str:
    """Return the stable canonical SHA-256 hex of *value* (S parity form)."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def source_events_sha256(events: Sequence[TimelineEvent]) -> str:
    """Hash the ordered canonical form of every source event.

    Parsed/canonical form (never raw line bytes): park24-style writers emit
    non-canonical bytes that still verify, so hashing raw lines would make
    identical streams hash differently.
    """
    digest = hashlib.sha256()
    for event in events:
        digest.update(canonical_json_bytes(event.to_json_obj()))
        digest.update(b"\n")
    return digest.hexdigest()


def map_actor_kind(actor_type: str) -> str:
    """Map a source ``TimelineActor.type`` to the kernel ``actor_kind``.

    Deterministic and total (``TimelineActor`` enforces the three source
    types); see the module docstring for the derivation.
    """
    try:
        return _ACTOR_KIND_MAP[actor_type]
    except KeyError:
        raise BackfillSourceError(
            f"source actor.type {actor_type!r} is not agent/human/system"
        ) from None


def derive_timeline_ulid(timeline_id: str) -> str:
    """Deterministic lowercase Crockford ULID alias from a timeline id.

    Mirrors the SDK's alias derivation so supabase-export sources without a
    timeline_ulid get a stable, valid ULID address form.
    """
    digest = hashlib.sha256(timeline_id.encode("utf-8")).digest()
    value = int.from_bytes(digest, "big") & ((1 << 130) - 1)
    chars = ["0"] * 26
    for index in range(25, -1, -1):
        chars[index] = _CROCKFORD_ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(chars)


def _payload_dict(event: TimelineEvent) -> dict[str, Any]:
    """Return the canonical payload dict of one source event."""
    payload = event.payload
    if isinstance(payload, dict):
        return dict(payload)
    return dict(payload.to_json_obj())


def _enrich_created_data(
    data: dict[str, Any], *, timeline_ulid: str
) -> dict[str, Any]:
    """Add the kernel-required ``timeline_ulid`` to a created payload.

    The source created event carries ``{timeline_id, slug, name}``; kernel
    alias resolution additionally reads ``data.timeline_ulid``, so the
    conversion adds exactly that one field from the source identity (module
    docstring, invariant c — documented addition).
    """
    enriched = dict(data)
    enriched.setdefault("timeline_ulid", timeline_ulid)
    return enriched


@dataclass(frozen=True, slots=True)
class MappedEvent:
    """One source event mapped to kernel append parameters (invariant c)."""

    event_id: str
    kind: str
    data: dict[str, Any]
    actor_kind: str
    created_at: str
    txn_id: str
    changes: tuple[str, ...]
    expected_kernel_data: dict[str, Any]  # exact data the checker compares


def map_source_event(
    event: TimelineEvent, *, timeline_ulid: str
) -> MappedEvent:
    """Map one source event to its kernel append parameters.

    See the module docstring for the exact field mapping and the documented
    drops/additions. ``expected_kernel_data`` is the exact payload the kernel
    row must carry (source data, plus the created-event ``timeline_ulid``
    enrichment), so the checker compares against the mapping, never a guess.
    """
    data = _payload_dict(event)
    if event.kind == _TIMELINE_CREATED_KIND:
        data = _enrich_created_data(data, timeline_ulid=timeline_ulid)
    txn_id = event.txn_id if event.txn_id is not None else (
        "bf-" + hashlib.sha256(event.event_id.encode("utf-8")).hexdigest()[:32]
    )
    return MappedEvent(
        event_id=event.event_id,
        kind=event.kind,
        data=data,
        actor_kind=map_actor_kind(event.actor.type),
        created_at=event.ts,
        txn_id=txn_id,
        changes=tuple(sorted(data.keys())),
        expected_kernel_data=data,
    )


def _project_registry(
    events: Sequence[TimelineEvent],
) -> dict[str, Any] | None:
    """Project the registry from the last asset_registry_replaced event.

    Mirrors the local-bridge recovery rule: the last usable
    ``timeline.asset_registry_replaced`` payload is the registry authority.
    Returns ``None`` when no such event exists (caller falls back to the
    ``registry.json`` sidecar, then an empty registry).
    """
    for event in reversed(events):
        if event.kind != _TIMELINE_ASSET_REGISTRY_REPLACED_KIND:
            continue
        payload = event.payload
        registry = (
            payload.get("registry")
            if isinstance(payload, dict)
            else getattr(payload, "registry", None)
        )
        if isinstance(registry, dict) and isinstance(registry.get("assets"), dict):
            return {"assets": registry["assets"]}
    return None


def _read_identity(home: Path) -> dict[str, Any]:
    from astrid.core._shared.jsonio import read_json

    identity_path = home / "assembly.identity.json"
    if not identity_path.is_file():
        raise BackfillSourceError(
            f"timeline source is missing assembly.identity.json in {home.name}"
        )
    try:
        identity = read_json(identity_path)
    except Exception as exc:
        raise BackfillSourceError(
            f"timeline source identity is unreadable in {home.name}: {exc}"
        ) from exc
    if not isinstance(identity, dict) or not isinstance(
        identity.get("timeline_id"), str
    ):
        raise BackfillSourceError(
            f"timeline source identity is malformed in {home.name}"
        )
    return identity


def _read_head_version(home: Path, event_count: int) -> int:
    """Read the source head version without healing the sidecar (R4).

    Reads ``assembly.head.json`` directly; a missing/unparseable sidecar
    falls back to the parsed event count, and an internally inconsistent
    sidecar fails closed.
    """
    from astrid.core._shared.jsonio import read_json

    head_path = home / "assembly.head.json"
    if not head_path.is_file():
        return event_count
    try:
        head = read_json(head_path)
    except Exception:
        raise BackfillSourceError(
            f"timeline source head is unreadable in {home.name}"
        ) from None
    if not isinstance(head, dict):
        raise BackfillSourceError(
            f"timeline source head is not an object in {home.name}"
        )
    version = head.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version <= 0:
        raise BackfillSourceError(
            f"timeline source head has no valid version in {home.name}"
        )
    declared_count = head.get("event_count")
    if (
        isinstance(declared_count, int)
        and not isinstance(declared_count, bool)
        and declared_count != event_count
    ):
        raise BackfillSourceError(
            f"timeline source head event_count {declared_count} disagrees "
            f"with the parsed log ({event_count} events) in {home.name}"
        )
    if version != event_count:
        raise BackfillSourceError(
            f"timeline source head version {version} disagrees with the "
            f"parsed log ({event_count} events) in {home.name}"
        )
    return version


def _identity_ulid_and_name(identity: dict[str, Any], timeline_id: str) -> tuple[str, str | None]:
    timeline_ulid = identity.get("timeline_ulid")
    if not isinstance(timeline_ulid, str) or not timeline_ulid:
        timeline_ulid = derive_timeline_ulid(timeline_id)
    display = identity.get("display")
    name = None
    if isinstance(display, dict) and isinstance(display.get("name"), str):
        name = display["name"]
    return timeline_ulid, name


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------


def load_local_fs_source(
    timeline_home: str | Path,
    *,
    timeline_id: str | None = None,
) -> BackfillSource:
    """Load and validate one immutable LocalFs source export (read-only).

    Never writes to *timeline_home*: events are read through
    ``LocalFsBackend.read_events`` and the head sidecar is parsed directly
    (see :func:`_read_head_version`). Fail closed on any inconsistency.
    """
    home = Path(timeline_home)
    identity = _read_identity(home)
    source_timeline_id = str(identity["timeline_id"])
    if timeline_id is not None and timeline_id != source_timeline_id:
        raise BackfillSourceError(
            f"requested timeline {timeline_id!r} does not match the source "
            f"identity {source_timeline_id!r} in {home.name}"
        )
    backend = LocalFsBackend(
        timeline_id=source_timeline_id, timeline_home=home
    )
    events = tuple(backend.read_events())
    if not events:
        raise BackfillSourceError(
            f"timeline source has an empty event log in {home.name}"
        )
    for event in events:
        if event.timeline_id != source_timeline_id:
            raise BackfillSourceError(
                f"source event {event.event_id} timeline_id disagrees with "
                f"the identity in {home.name}"
            )
    head_version = _read_head_version(home, len(events))
    timeline_ulid, name = _identity_ulid_and_name(identity, source_timeline_id)
    projected_config = replay_projection(backend)
    registry = _project_registry(events)
    if registry is None:
        registry = _read_registry_sidecar(home)
    return BackfillSource(
        source_name=BACKFILL_MARKER_SOURCE_LOCAL_FS,
        timeline_id=source_timeline_id,
        timeline_ulid=timeline_ulid,
        name=name,
        events=events,
        head_version=head_version,
        events_sha256=source_events_sha256(events),
        projected_config=dict(projected_config),
        projected_registry=registry,
    )


def _read_registry_sidecar(home: Path) -> dict[str, Any]:
    from astrid.core._shared.jsonio import read_json

    registry_path = home / "registry.json"
    if not registry_path.is_file():
        return {"assets": {}}
    try:
        raw = read_json(registry_path)
    except Exception:
        raise BackfillSourceError(
            f"timeline source registry.json is unreadable in {home.name}"
        ) from None
    if isinstance(raw, dict) and isinstance(raw.get("assets"), dict):
        return {"assets": raw["assets"]}
    raise BackfillSourceError(
        f"timeline source registry.json is malformed in {home.name}"
    )


def parse_export_items(text: str, *, label: str) -> list[Any]:
    """Parse an export as a JSON array OR JSONL (one object per line).

    Raises :class:`BackfillSourceError` naming *label* when neither form
    parses. Shared by :class:`SupabaseExportReader` and the project run
    scan so the CLI ``--from supabase-export`` path accepts both forms.
    """
    import json

    stripped = text.strip()
    if not stripped:
        return []
    # A JSON array is the single-document form; JSONL is one object per
    # line. Try the array form first, then fall back to line parsing.
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass  # not a single JSON document; try JSONL below
    try:
        lines = [
            json.loads(line) for line in text.splitlines() if line.strip()
        ]
    except json.JSONDecodeError as exc:
        raise BackfillSourceError(
            f"supabase export is not a JSON array or valid JSONL: {label}"
        ) from exc
    return lines


class SupabaseExportReader:
    """Read a version-ordered Supabase export file (read-only transport).

    The documented export envelope is ``VersionedTimelineEvent.to_append_json_obj()``
    (``astrid/core/timeline/eventlog/reigh_events.py``): a TimelineEvent JSON
    object plus a 1-based contiguous ``version`` key — exactly the
    ``p_events`` payload of the ``append_timeline_event`` RPC. The file is
    either a JSON array of such objects or one JSON object per line.

    The reader implements the ``read_events`` transport surface used by
    :class:`SupabaseBackend` (or can be passed as the reader directly), so
    the import path is identical for file-backed and mocked transports.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        timeline_id: str,
    ) -> None:
        self.path = Path(path)
        self.timeline_id = timeline_id
        self._events: tuple[TimelineEvent, ...] | None = None
        self._versions: tuple[int, ...] | None = None

    def _load(self) -> tuple[tuple[TimelineEvent, ...], tuple[int, ...]]:
        if self._events is not None:
            assert self._versions is not None
            return self._events, self._versions
        if not self.path.is_file():
            raise BackfillSourceError(
                f"supabase export file is missing: {self.path.name}"
            )
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise BackfillSourceError(
                f"supabase export file is unreadable: {self.path.name}"
            ) from exc
        raw_items = self._parse_items(text)
        rows: list[tuple[int, TimelineEvent]] = []
        for index, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                raise BackfillSourceError(
                    f"supabase export item {index} is not a JSON object"
                )
            version = raw.get("version")
            if not isinstance(version, int) or isinstance(version, bool) or version <= 0:
                raise BackfillSourceError(
                    f"supabase export item {index} has no positive version"
                )
            timeline_id = raw.get("timeline_id")
            if timeline_id != self.timeline_id:
                continue
            try:
                event = TimelineEvent.from_dict(raw)
            except Exception as exc:
                raise BackfillSourceError(
                    f"supabase export item {index} is not a valid event "
                    f"envelope: {exc}"
                ) from exc
            rows.append((version, event))
        rows.sort(key=lambda pair: pair[0])
        versions = tuple(version for version, _ in rows)
        expected = tuple(range(1, len(rows) + 1))
        if versions != expected:
            raise BackfillSourceError(
                f"supabase export versions are not 1-based contiguous for "
                f"timeline {self.timeline_id!r}"
            )
        events = tuple(event for _, event in rows)
        self._events = events
        self._versions = versions
        return events, versions

    def _parse_items(self, text: str) -> list[Any]:
        return parse_export_items(text, label=self.path.name)

    # -- EventLogBackend-compatible transport surface -----------------------

    def read_events(
        self,
        *,
        after: str | None = None,
        limit: int | None = None,
    ) -> list[TimelineEvent]:
        events, _ = self._load()
        return list(events)

    def head_version(self) -> int:
        _, versions = self._load()
        return versions[-1] if versions else 0

    def verify_chain(self) -> Any:
        from astrid.core.timeline.eventlog.types import EventLogVerification

        events, _ = self._load()
        from astrid.core.timeline.events.schema import with_event_hash

        prev_hash: str | None = None
        for index, event in enumerate(events):
            expected = with_event_hash(
                TimelineEvent.from_dict(
                    {**event.to_json_obj(), "hash": None}
                ),
                prev_hash=prev_hash,
            )
            if event.prev_hash != prev_hash or event.hash != expected.hash:
                return EventLogVerification(
                    ok=False,
                    checked_events=index,
                    last_event_id=None,
                    error=f"export event {event.event_id} chain link broken",
                )
            prev_hash = event.hash
        return EventLogVerification(
            ok=True,
            checked_events=len(events),
            last_event_id=events[-1].event_id if events else None,
            error=None,
        )


def _build_supabase_source(
    events: Sequence[TimelineEvent],
    *,
    timeline_id: str,
    head_version: int,
    reader: Any,
) -> BackfillSource:
    """Shared source construction for the Supabase leg (file or transport)."""
    if not events:
        raise BackfillSourceError(
            f"supabase export contains no events for timeline {timeline_id!r}"
        )
    for event in events:
        if event.timeline_id != timeline_id:
            raise BackfillSourceError(
                f"supabase event {event.event_id} timeline_id disagrees "
                f"with {timeline_id!r}"
            )
    if head_version != len(events):
        raise BackfillSourceError(
            f"supabase export head version {head_version} disagrees with "
            f"{len(events)} events for timeline {timeline_id!r}"
        )
    timeline_ulid, name = _export_identity(events, timeline_id)
    projected_config = replay_projection(reader)
    registry = _project_registry(events)
    if registry is None:
        registry = {"assets": {}}
    return BackfillSource(
        source_name=BACKFILL_MARKER_SOURCE_SUPABASE,
        timeline_id=timeline_id,
        timeline_ulid=timeline_ulid,
        name=name,
        events=tuple(events),
        head_version=head_version,
        events_sha256=source_events_sha256(events),
        projected_config=dict(projected_config),
        projected_registry=registry,
    )


def load_supabase_export_source(
    path: str | Path,
    *,
    timeline_id: str,
) -> BackfillSource:
    """Load and validate one version-ordered Supabase export file.

    Reads through :class:`SupabaseExportReader` (read-only; the file is never
    modified) and projects the config/registry from the export events exactly
    like the local_fs path.
    """
    reader = SupabaseExportReader(path, timeline_id=timeline_id)
    events = tuple(reader.read_events())
    return _build_supabase_source(
        events,
        timeline_id=timeline_id,
        head_version=reader.head_version(),
        reader=reader,
    )


def load_supabase_backend_source(
    backend: Any,
    *,
    timeline_id: str,
    head_version: int | None = None,
) -> BackfillSource:
    """Load a Supabase source through a transport-backed backend.

    The transport seam (``SupabaseBackend`` with an injected
    ``SupabaseEventLogTransport`` — the mocked pattern from
    ``tests/timeline/test_transfer.py``) feeds the same import path as the
    export file: events are read via ``backend.read_events()`` and the head
    version is the contiguous event count unless the transport reports one.
    """
    events = tuple(backend.read_events())
    effective_head = head_version if head_version is not None else len(events)
    return _build_supabase_source(
        events,
        timeline_id=timeline_id,
        head_version=effective_head,
        reader=backend,
    )


def _export_identity(
    events: Sequence[TimelineEvent], timeline_id: str
) -> tuple[str, str | None]:
    """Derive the ULID alias and display name from an export's created event.

    The created event data carries ``timeline_id``/``slug``/``name``; the
    ULID alias is derived deterministically (the export envelope has no
    identity sidecar).
    """
    name: str | None = None
    for event in events:
        if event.kind != _TIMELINE_CREATED_KIND:
            continue
        data = _payload_dict(event)
        candidate = data.get("name")
        if isinstance(candidate, str) and candidate:
            name = candidate
        break
    return derive_timeline_ulid(timeline_id), name


# ---------------------------------------------------------------------------
# Authority marker (R5)
# ---------------------------------------------------------------------------


def backfill_state_path(projects_root: str | Path) -> Path:
    """Return ``<projects_root>/.astrid/backfill-state.json`` (R5)."""
    return Path(projects_root) / ASTROID_DIR_NAME / BACKFILL_STATE_FILENAME


def read_backfill_state(
    projects_root: str | Path,
) -> dict[str, dict[str, Any]]:
    """Read the authority marker file, or ``{}`` when absent/corrupt-empty.

    A corrupt marker fails closed (raises) rather than being overwritten:
    the marker is the authority claim, so garbage must surface, never be
    silently replaced.
    """
    from astrid.core._shared.jsonio import read_json

    path = backfill_state_path(projects_root)
    if not path.is_file():
        return {}
    try:
        raw = read_json(path)
    except Exception as exc:
        raise BackfillError(
            f"backfill authority marker is unreadable: {path.name}"
        ) from exc
    if not isinstance(raw, dict):
        raise BackfillError(
            f"backfill authority marker is not an object: {path.name}"
        )
    result: dict[str, dict[str, Any]] = {}
    for timeline_id, entry in raw.items():
        if not isinstance(entry, dict):
            raise BackfillError(
                f"backfill authority marker entry for {timeline_id!r} is "
                "not an object"
            )
        result[str(timeline_id)] = entry
    return result


def write_backfill_state(
    projects_root: str | Path,
    *,
    timeline_id: str,
    source: str,
    source_head_version: int,
    events_sha256: str,
    backfilled_at: str | None = None,
) -> dict[str, Any]:
    """Atomically record one timeline's authority state (R5).

    Read-modify-write of the whole marker file through
    ``foundation.atomic_io.write_json_atomic``; the schema is documented in
    the module docstring.
    """
    state = read_backfill_state(projects_root)
    entry = {
        "backfilled_at": backfilled_at or utc_now_iso(),
        "source": source,
        "source_head_version": source_head_version,
        "events_sha256": events_sha256,
    }
    state[str(timeline_id)] = entry
    write_json_atomic(backfill_state_path(projects_root), state)
    return entry


# ---------------------------------------------------------------------------
# The reusable zero-loss checker
# ---------------------------------------------------------------------------


def verify_backfill(
    source: BackfillSource,
    *,
    stream_id: str,
    writer: DatabaseWriter,
) -> BackfillVerification:
    """Run the zero-loss invariants (a),(b),(c),(e) against the kernel.

    Read-only: runs on the writer's transaction-free read-only connection
    and never mutates state. ``mismatches`` names every failed check.
    """
    mismatches: list[str] = []
    with writer.read_only_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT head_seq FROM event_streams WHERE id = ?", (stream_id,)
        ).fetchone()
    kernel_head_seq = int(row["head_seq"]) if row is not None else 0
    events_repo = EventRepository(writer)
    kernel_models = events_repo.list_events(
        stream_id=stream_id, limit=10_000
    )
    kernel_event_count = len(kernel_models)
    kernel_kinds = dict(
        Counter(model.kind for model in kernel_models)
    )

    if source.head_version != kernel_head_seq:
        mismatches.append(
            f"head: source {source.head_version} != kernel head_seq "
            f"{kernel_head_seq}"
        )
    if len(source.events) != kernel_event_count:
        mismatches.append(
            f"count: source {len(source.events)} != kernel "
            f"{kernel_event_count}"
        )
    if source.kind_counts != kernel_kinds:
        mismatches.append(
            f"kinds: source {source.kind_counts} != kernel {kernel_kinds}"
        )

    # (c) content projection, position by position (kernel seq == source
    # version == 1-based index).
    for index, (source_event, model) in enumerate(
        zip(source.events, kernel_models), start=1
    ):
        if model.seq != index:
            mismatches.append(f"content: kernel seq {model.seq} != {index}")
            continue
        mapped = map_source_event(source_event, timeline_ulid=source.timeline_ulid)
        if model.kind != mapped.kind:
            mismatches.append(
                f"content: event {index} kind {model.kind!r} != "
                f"source {mapped.kind!r}"
            )
        try:
            kernel_data = dict(model.data)
        except Exception:
            kernel_data = {}
        if canonical_json(kernel_data) != canonical_json(mapped.expected_kernel_data):
            mismatches.append(
                f"content: event {index} payload data differs from source"
            )
        if model.actor_kind != mapped.actor_kind:
            mismatches.append(
                f"content: event {index} actor_kind {model.actor_kind!r} != "
                f"mapped {mapped.actor_kind!r}"
            )
        if model.created_at != mapped.created_at:
            mismatches.append(
                f"content: event {index} created_at differs from source ts"
            )
        if model.event_id != source_event.event_id:
            mismatches.append(
                f"content: event {index} event_id not preserved"
            )

    return BackfillVerification(
        source_event_count=len(source.events),
        kernel_event_count=kernel_event_count,
        source_head_version=source.head_version,
        kernel_head_seq=kernel_head_seq,
        source_kinds=source.kind_counts,
        kernel_kinds=kernel_kinds,
        mismatches=tuple(mismatches),
    )


# ---------------------------------------------------------------------------
# The import orchestrator
# ---------------------------------------------------------------------------


def _stream_id(timeline_id: str) -> str:
    return f"{timeline_id}:{_TIMELINE_STREAM_TYPE}"


def _append_timeline_events(
    uow: UnitOfWork,
    *,
    project_id: str,
    timeline_id: str,
    stream_id: str,
    mapped_events: Sequence[MappedEvent],
    created_at: str,
    on_before_append: Callable[[int], None] | None = None,
) -> tuple[tuple[str, ...], int, int, int]:
    """Append mapped events as one hash-chained kernel batch.

    Builds the canonical SD2 envelopes in Python (``previous_event_hash``
    chains across the batch), appends every event through the typed
    ``UnitOfWork.append_event`` surface, and returns
    ``(event_ids, first_project_seq, last_project_seq, resulting_stream_seq)``.
    """
    event_ids: list[str] = []
    prev_hash: str | None = None
    first_project_seq: int | None = None
    last_project_seq: int | None = None
    resulting_stream_seq: int | None = None
    for index, mapped in enumerate(mapped_events, start=1):
        if on_before_append is not None:
            on_before_append(index)
        envelope, event_hash = build_integrity_envelope(
            mapped.data, prev_hash
        )
        payload_json = canonical_json(envelope)
        changes_json = canonical_json(list(mapped.changes))
        project_seq, stream_seq = uow.append_event(
            stream_id=stream_id,
            project_id=project_id,
            event_id=mapped.event_id,
            subject_type="timeline",
            subject_id=timeline_id,
            changes_json=changes_json,
            kind=mapped.kind,
            schema_version=1,
            idempotency_key=(
                f"{BACKFILL_COMMAND_KIND}:{timeline_id}:{mapped.event_id}"
            ),
            txn_id=mapped.txn_id,
            actor_kind=mapped.actor_kind,
            payload_json=payload_json,
            created_at=mapped.created_at,
        )
        if first_project_seq is None:
            first_project_seq = project_seq
        last_project_seq = project_seq
        resulting_stream_seq = stream_seq
        event_ids.append(mapped.event_id)
        prev_hash = event_hash
    assert first_project_seq is not None and last_project_seq is not None
    assert resulting_stream_seq is not None
    return (
        tuple(event_ids),
        first_project_seq,
        last_project_seq,
        resulting_stream_seq,
    )


def _current_stream_state(
    writer: DatabaseWriter, timeline_id: str
) -> tuple[int, bool]:
    """Return ``(head_seq, stream_exists)`` for one timeline (read-only)."""
    stream_id = _stream_id(timeline_id)
    with writer.read_only_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT head_seq FROM event_streams WHERE id = ?", (stream_id,)
        ).fetchone()
    if row is None:
        return 0, False
    return int(row["head_seq"]), True


def backfill_timeline(
    *,
    writer: DatabaseWriter,
    projects: ProjectRepository,
    receipts: ReceiptService,
    project_slug: str,
    source: BackfillSource,
    projects_root: str | Path | None = None,
    dry_run: bool = False,
    on_before_append: Callable[[int], None] | None = None,
) -> BackfillReport:
    """Backfill ONE timeline into the kernel database, fail-closed.

    Order of operations (``dry_run`` stops before any write):

    1. resolve the project (must exist in the kernel database);
    2. authority-marker guard (R5): an existing marker that disagrees with
       this source is refused before any write;
    3. receipt idempotency gate: an identical earlier import replays its
       stored result with zero new rows;
    4. one ``BEGIN IMMEDIATE`` unit of work: insert the timeline stream and
       the whole-document projection, append every source event 1:1
       (hash-chained SD2 envelopes), record the complete receipt;
    5. verify the zero-loss invariants (a),(b),(c),(e) read-only;
    6. write the authority marker (f) — only after every check passes.

    Any discrepancy raises :class:`BackfillDiscrepancyError` and the whole
    timeline rolls back: no events, no receipt, no marker (no partial
    authority claim).
    """
    root = resolve_projects_root(projects_root)
    project_slug = validate_project_slug(project_slug)
    project_id = projects.resolve(writer, project_slug)
    marker_path = str(backfill_state_path(root))
    marker_matches = False
    if not dry_run:
        state = read_backfill_state(root)
        existing = state.get(source.timeline_id)
        if existing is not None:
            if (
                existing.get("source") != source.source_name
                or existing.get("source_head_version") != source.head_version
                or existing.get("events_sha256") != source.events_sha256
            ):
                raise BackfillAuthorityError(
                    f"timeline {source.timeline_id} is already backfilled from "
                    f"{existing.get('source')} at head "
                    f"{existing.get('source_head_version')}; refusing to mix "
                    f"authorities with {source.source_name} at head "
                    f"{source.head_version}"
                )
            marker_matches = True

    stream_id = _stream_id(source.timeline_id)
    head_seq, stream_exists = _current_stream_state(writer, source.timeline_id)

    # The conversion itself is a check: mapping every event must succeed
    # (actor mapping, payload canonicalization, created-event enrichment)
    # before any write.
    mapped_events = tuple(
        map_source_event(event, timeline_ulid=source.timeline_ulid)
        for event in source.events
    )
    source_consistent = (
        len(source.events) == source.head_version
        and source.kind_counts == source.kind_counts
    )
    source_checks = {
        "count": source_consistent,
        "head": source_consistent,
        "content": True,
        "kinds": True,
    }

    if dry_run:
        return BackfillReport(
            project=project_slug,
            timeline_id=source.timeline_id,
            timeline_ulid=source.timeline_ulid,
            source=source.source_name,
            source_event_count=len(source.events),
            kernel_event_count=head_seq if stream_exists else 0,
            source_head_version=source.head_version,
            kernel_head_seq=head_seq if stream_exists else 0,
            events_sha256=source.events_sha256,
            kinds=source.kind_counts,
            checks=source_checks,
            marker_path=marker_path,
            marker_written=False,
            written=False,
            replayed=False,
            dry_run=True,
            projected_config_sha256=sha256_hex(source.projected_config),
            projected_registry_sha256=sha256_hex(source.projected_registry),
            detail=(
                "dry-run: no events, receipts, or markers written"
                if not stream_exists
                else f"dry-run: stream already exists at head {head_seq}; "
                "no writes performed"
            ),
        )

    if stream_exists:
        # The stream exists: either this timeline was already backfilled
        # (marker matches -> receipt replay below) or it is foreign kernel
        # state with no matching marker — fail closed rather than append to
        # an unknown authority.
        if head_seq != 0 and not marker_matches:
            raise BackfillAuthorityError(
                f"timeline {source.timeline_id} already has a kernel stream "
                f"at head {head_seq} with no matching backfill marker; "
                "refusing to append backfill events to non-empty state"
            )

    request = {
        "timeline_id": source.timeline_id,
        "source": source.source_name,
        "source_head_version": source.head_version,
        "events_sha256": source.events_sha256,
    }
    try:
        request_digest = request_hash(BACKFILL_COMMAND_KIND, request)
    except CanonicalizationError as exc:
        raise BackfillError(
            f"cannot hash backfill request: {exc}"
        ) from exc
    idempotency_key = (
        f"{BACKFILL_COMMAND_KIND}:{project_id}:{source.timeline_id}"
    )

    def _command(uow: UnitOfWork) -> BackfillReport:
        # Idempotency gate first: identical retry replays the stored result.
        replayed = receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=BACKFILL_COMMAND_KIND,
        )
        if replayed is not None:
            return _report_from_mapping(replayed, replayed=True)

        stamp = utc_now_iso()
        # 1. The timeline.timeline stream (head_seq starts at 0; the appends
        #    advance it to N in the same transaction). Inserted before the
        #    timelines projection because timelines.event_stream_id is an
        #    immediate FK into event_streams.
        uow.execute(
            "INSERT INTO event_streams "
            "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (
                stream_id,
                project_id,
                _TIMELINE_STREAM_TYPE,
                source.timeline_id,
                stamp,
            ),
        )
        # 2. The whole-document timelines projection: the source-side
        #    projected config + registry (bridge GET reads this row).
        uow.execute(
            "INSERT INTO timelines "
            "(id, project_id, event_stream_id, name, document_json, "
            "asset_registry_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source.timeline_id,
                project_id,
                stream_id,
                source.name or source.timeline_ulid,
                canonical_json(source.projected_config),
                canonical_json(source.projected_registry["assets"]),
                stamp,
                stamp,
            ),
        )
        # 3. The source events, 1:1, hash-chained (head advances to
        #    source.head_version).
        event_ids, first_seq, last_seq, resulting_seq = _append_timeline_events(
            uow,
            project_id=project_id,
            timeline_id=source.timeline_id,
            stream_id=stream_id,
            mapped_events=mapped_events,
            created_at=stamp,
            on_before_append=on_before_append,
        )
        # 4. The complete receipt (raw numbers; checks are re-verified
        #    read-only after commit, so replay never trusts stored checks).
        report = BackfillReport(
            project=project_slug,
            timeline_id=source.timeline_id,
            timeline_ulid=source.timeline_ulid,
            source=source.source_name,
            source_event_count=len(source.events),
            kernel_event_count=len(source.events),
            source_head_version=source.head_version,
            kernel_head_seq=source.head_version,
            events_sha256=source.events_sha256,
            kinds=source.kind_counts,
            checks=source_checks,
            marker_path=marker_path,
            marker_written=False,
            written=False,
            replayed=False,
            dry_run=False,
            projected_config_sha256=sha256_hex(source.projected_config),
            projected_registry_sha256=sha256_hex(source.projected_registry),
            detail="imported",
        )
        receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=BACKFILL_COMMAND_KIND,
            txn_id=uuid.uuid4().hex,
            primary_stream_id=stream_id,
            resulting_stream_seq=resulting_seq,
            first_project_seq=first_seq,
            last_project_seq=last_seq,
            event_ids=event_ids,
            result=report.to_dict(),
            created_at=stamp,
        )
        return report

    report = UnitOfWork(writer).run(_command)
    replayed = report.replayed
    # Fresh import or identical retry: verify every invariant (a)-(e)
    # read-only, then the marker (f). No new rows are written on replay.
    verification = verify_backfill(source, stream_id=stream_id, writer=writer)
    if not verification.ok:
        raise BackfillDiscrepancyError(
            "backfill verification failed: "
            + "; ".join(verification.mismatches)
        )
    marker_written = _write_marker_if_absent(root, source)
    return _final_report(
        report,
        verification=verification,
        marker_written=marker_written,
        written=True,
        replayed=replayed,
        dry_run=False,
        detail=(
            "replayed with zero new rows; verification passed"
            if replayed
            else "imported and verified"
        ),
    )


def _final_report(
    base: BackfillReport,
    *,
    verification: BackfillVerification,
    marker_written: bool,
    written: bool,
    replayed: bool,
    dry_run: bool,
    detail: str,
) -> BackfillReport:
    """Rebuild a report with post-commit verification and marker state."""
    return BackfillReport(
        project=base.project,
        timeline_id=base.timeline_id,
        timeline_ulid=base.timeline_ulid,
        source=base.source,
        source_event_count=verification.source_event_count,
        kernel_event_count=verification.kernel_event_count,
        source_head_version=verification.source_head_version,
        kernel_head_seq=verification.kernel_head_seq,
        events_sha256=base.events_sha256,
        kinds=verification.kernel_kinds,
        checks=verification.checks_dict(),
        marker_path=base.marker_path,
        marker_written=marker_written,
        written=written,
        replayed=replayed,
        dry_run=dry_run,
        projected_config_sha256=base.projected_config_sha256,
        projected_registry_sha256=base.projected_registry_sha256,
        detail=detail,
    )


def _write_marker_if_absent(
    root: Path, source: BackfillSource
) -> bool:
    """Write the authority marker entry when none exists; return written."""
    state = read_backfill_state(root)
    existing = state.get(source.timeline_id)
    if existing is not None:
        return False
    write_backfill_state(
        root,
        timeline_id=source.timeline_id,
        source=source.source_name,
        source_head_version=source.head_version,
        events_sha256=source.events_sha256,
    )
    return True


# -- BackfillReport replay helper -------------------------------------------


def _report_from_mapping(value: Mapping[str, Any], *, replayed: bool) -> BackfillReport:
    return BackfillReport(
        project=str(value["project"]),
        timeline_id=str(value["timeline_id"]),
        timeline_ulid=str(value["timeline_ulid"]),
        source=str(value["source"]),
        source_event_count=int(value["source_event_count"]),
        kernel_event_count=int(value["kernel_event_count"]),
        source_head_version=int(value["source_head_version"]),
        kernel_head_seq=int(value["kernel_head_seq"]),
        events_sha256=str(value["events_sha256"]),
        kinds=dict(value["kinds"]),
        checks=dict(value["checks"]),
        marker_path=str(value.get("marker_path", "")),
        marker_written=bool(value.get("marker_written", False)),
        written=bool(value.get("written", False)),
        replayed=replayed,
        dry_run=bool(value.get("dry_run", False)),
        projected_config_sha256=str(value.get("projected_config_sha256", "")),
        projected_registry_sha256=str(value.get("projected_registry_sha256", "")),
        detail=str(value.get("detail", "")),
    )


# ---------------------------------------------------------------------------
# Project-level run loop (multi-timeline, checkpointed)
# ---------------------------------------------------------------------------


def backfill_project(
    *,
    writer: DatabaseWriter,
    projects: ProjectRepository,
    receipts: ReceiptService,
    project_slug: str,
    timeline_refs: Sequence[str] | None = None,
    from_supabase_export: str | Path | None = None,
    projects_root: str | Path | None = None,
    dry_run: bool = False,
    run_ts: str | None = None,
    on_before_append: Callable[[int], None] | None = None,
) -> dict[str, BackfillReport]:
    """Backfill every selected timeline of one project, in deterministic order.

    Local-FS sources are discovered under
    ``<root>/<project_slug>/timelines/<ULID>/`` (``already_event_sourced``
    directories only; other classifications are reported as skipped). With
    ``from_supabase_export`` the export file is the source for every
    timeline id it contains (optionally narrowed by *timeline_refs*).

    The run reuses the migration checkpoint machinery
    (``checkpoint_path_for_run`` / ``write_resumable_checkpoint`` /
    ``read_resumable_checkpoint``): after each successful timeline the
    checkpoint records progress under ``<project>/runs/migrations/<ts>/``,
    and a resumed run (same ``run_ts``) skips the completed prefix. A
    timeline failure aborts the run (fail closed) with the checkpoint left
    at the last completed timeline.
    """
    from astrid.core.timeline.migration import (
        checkpoint_path_for_run,
        read_resumable_checkpoint,
        write_resumable_checkpoint,
        ResumableStatus,
    )

    root = resolve_projects_root(projects_root)
    project_slug = validate_project_slug(project_slug)
    # Resolve the project id up front so a missing project fails before any
    # source scan.
    projects.resolve(writer, project_slug)

    if from_supabase_export is not None:
        sources = _supabase_run_sources(
            from_supabase_export, timeline_refs=timeline_refs
        )
    else:
        sources = _local_fs_run_sources(
            root, project_slug, timeline_refs=timeline_refs
        )

    checkpoint_file = None
    if not dry_run:
        checkpoint_file = checkpoint_path_for_run(
            project_slug, root=root, run_ts=run_ts
        )
    completed_prefix = 0
    if checkpoint_file is not None:
        status = read_resumable_checkpoint(checkpoint_file)
        if status is not None and status.last_completed_timeline_ulid:
            for index, (source, _classification) in enumerate(sources):
                if source.timeline_ulid == status.last_completed_timeline_ulid:
                    completed_prefix = index + 1
                    break

    reports: dict[str, BackfillReport] = {}
    skipped: dict[str, str] = {}
    for index, (source, classification) in enumerate(sources):
        if classification != "already_event_sourced":
            skipped[source.timeline_id] = classification
            continue
        if index < completed_prefix:
            # Resumed run: this timeline already committed in the
            # interrupted run (checkpoint records it as completed). Skipping
            # is safe because its receipt, events, projection, and marker
            # are durable; an identical re-import would replay anyway.
            continue
        report = backfill_timeline(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug=project_slug,
            source=source,
            projects_root=root,
            dry_run=dry_run,
            on_before_append=on_before_append,
        )
        reports[source.timeline_id] = report
        if not dry_run and checkpoint_file is not None:
            write_resumable_checkpoint(
                ResumableStatus(
                    last_completed_project=project_slug,
                    last_completed_timeline_ulid=source.timeline_ulid,
                    imported_count=len(reports),
                    skipped_count=len(skipped),
                ),
                checkpoint_file,
            )
    if skipped and not reports:
        raise BackfillSourceError(
            f"no event-sourced timelines found in project {project_slug!r}; "
            f"skipped {sorted(skipped.values())}"
        )
    return reports


def _local_fs_run_sources(
    root: Path,
    project_slug: str,
    timeline_refs: Sequence[str] | None,
) -> list[tuple[BackfillSource, str]]:
    """Discover and load every selected LocalFs source (read-only)."""
    from astrid.core._shared.jsonio import read_json
    from astrid.core.timeline.migration import classify_timeline_dir
    from astrid.core.threads.ids import is_ulid

    timelines_dir = root / project_slug / "timelines"
    if not timelines_dir.is_dir():
        if timeline_refs:
            raise BackfillSourceError(
                f"project {project_slug!r} has no timelines directory"
            )
        return []
    refs = set(timeline_refs or ())
    sources: list[tuple[BackfillSource, str]] = []
    for child in sorted(timelines_dir.iterdir()):
        if not child.is_dir() or not is_ulid(child.name):
            continue
        classification = classify_timeline_dir(child)
        identity_path = child / "assembly.identity.json"
        timeline_id = child.name
        try:
            if identity_path.is_file():
                identity = read_json(identity_path)
                if isinstance(identity, dict) and isinstance(
                    identity.get("timeline_id"), str
                ):
                    timeline_id = identity["timeline_id"]
        except Exception:
            pass
        if refs and child.name not in refs and timeline_id not in refs:
            continue
        if refs and classification != "already_event_sourced":
            raise BackfillSourceError(
                f"timeline {child.name} is {classification!r}, not "
                "already_event_sourced"
            )
        source = load_local_fs_source(child, timeline_id=timeline_id)
        sources.append((source, classification))
    if refs and not sources:
        raise BackfillSourceError(
            f"no timeline matches {sorted(refs)} in project {project_slug!r}"
        )
    if not sources:
        raise BackfillSourceError(
            f"no event-sourced timelines found in project {project_slug!r}"
        )
    return sources


def _supabase_run_sources(
    path: str | Path,
    timeline_refs: Sequence[str] | None,
) -> list[tuple[BackfillSource, str]]:
    """Load every selected timeline from one version-ordered export file."""
    export = Path(path)
    if not export.is_file():
        raise BackfillSourceError(
            f"supabase export file is missing: {export.name}"
        )
    try:
        text = export.read_text(encoding="utf-8")
    except OSError as exc:
        raise BackfillSourceError(
            f"supabase export file is unreadable: {export.name}"
        ) from exc
    parsed = parse_export_items(text, label=export.name)
    timeline_ids: set[str] = set()
    for raw in parsed:
        if not isinstance(raw, dict):
            continue
        tid = raw.get("timeline_id")
        if isinstance(tid, str) and tid:
            timeline_ids.add(tid)
    refs = set(timeline_refs or ())
    if refs:
        timeline_ids = {tid for tid in timeline_ids if tid in refs}
    sources: list[tuple[BackfillSource, str]] = []
    for timeline_id in sorted(timeline_ids):
        source = load_supabase_export_source(export, timeline_id=timeline_id)
        sources.append((source, "already_event_sourced"))
    if refs and not sources:
        raise BackfillSourceError(
            f"no timeline matches {sorted(refs)} in the supabase export"
        )
    return sources


__all__ = [
    "BACKFILL_COMMAND_KIND",
    "BACKFILL_MARKER_SOURCE_LOCAL_FS",
    "BACKFILL_MARKER_SOURCE_SUPABASE",
    "BACKFILL_STATE_FILENAME",
    "BackfillAuthorityError",
    "BackfillDiscrepancyError",
    "BackfillError",
    "BackfillReport",
    "BackfillSource",
    "BackfillSourceError",
    "BackfillVerification",
    "MappedEvent",
    "SupabaseExportReader",
    "backfill_project",
    "backfill_state_path",
    "backfill_timeline",
    "derive_timeline_ulid",
    "load_local_fs_source",
    "load_supabase_backend_source",
    "load_supabase_export_source",
    "map_actor_kind",
    "map_source_event",
    "parse_export_items",
    "read_backfill_state",
    "sha256_hex",
    "source_events_sha256",
    "verify_backfill",
    "write_backfill_state",
]
