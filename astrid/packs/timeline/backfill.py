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

    ``<projects_root>/.astrid/backfill-state.json`` (read-modify-write
    serialized by an ``flock`` on
    ``<projects_root>/.astrid/backfill-state.lock``, then an atomic replace
    via ``astrid.core.foundation.atomic_io.write_json_atomic``)::

        {
          "<timeline_id>": {
            "backfilled_at": "<iso-8601-utc>",
            "source": "local_fs" | "supabase_export",
            "source_head_version": <int>,
            "events_sha256": "<sha256 hex of the canonical source events>",
            "synthesized_bootstrap": <bool>,
            "identity_sha256": "<sha256 of the identity-sidecar file bytes>",
            "registry_sha256": "<sha256 of registry.json bytes when the
                                fallback supplied the projection, else ''>"
          }
        }

``synthesized_bootstrap`` records whether the import synthesized a
``timeline.created`` bootstrap event (W3: sources without one get exactly
one deterministic bootstrap event at kernel position 0). The key is always
present (shape extended additively; R5 semantics preserved).

``identity_sha256`` / ``registry_sha256`` (round-3 P2#1) bind the LocalFs
sidecars that sit OUTSIDE the event hash chain: the sha256 of the
``assembly.identity.json`` file bytes (always; ``""`` for supabase_export
sources, which have no sidecar), and of the ``registry.json`` file bytes
when the fallback supplied the projection (else ``""``). Resume
revalidation and re-import recompute them from the CURRENT sidecar bytes
and fail closed with the named digest on mismatch (W2 machinery); a
matching digest refreshes the marker unchanged.

The marker is written ONLY after every zero-loss invariant passes (see
:func:`verify_backfill`). A failed import writes NO marker and leaves NO
authority claim. Any later request whose source/head/sha disagree with the
marker for the same timeline is refused with :class:`BackfillAuthorityError`
(no authority mixing per timeline). A request whose source identity
MATCHES an existing marker is not refused: it re-verifies and idempotently
refreshes the marker (crash-convergent "complete-the-marker", W1.3).

Zero-loss invariants (each backfilled timeline fails closed unless ALL hold;
the checker is reusable — :func:`verify_backfill`):

a. expected event count == kernel event count for the mapped stream
   (``len(source.events) + synthesized_count``);
b. head continuity: ``event_streams.head_seq`` == source head version +
   ``synthesized_count`` (synthesized bootstrap occupies kernel position 0,
   so a slice without ``timeline.created`` ends at ``source_version + 1``);
c. content projection: for every expected event (synthesized bootstrap
   first, then each source event) the preserved fields (``kind``, payload
   ``data``, ``actor_kind``, ``created_at``, ``event_id``) plus the
   mapper-derived ``txn_id`` and ``changes_json`` are canonically equal to
   the kernel row; see :func:`map_source_event` for the exact field mapping
   and the documented drops/additions;
d. idempotency: running the same import twice yields ZERO new kernel events
   and an unchanged head (kernel identical-replay semantic: the per-timeline
   command receipt replays the stored result);
e. unknown-kind pass-through: per-kind counts are preserved, including kinds
   the timeline schema does not register (raw-dict payloads);
f. the marker is written only after (a)-(e) hold; a failed import writes no
   marker;
g. projections: stored ``timelines.document_json`` == canonical
   ``source.projected_config`` and stored ``asset_registry_json`` ==
   canonical ``source.projected_registry["assets"]``, AND the
   bridge-served identity columns of the same row equal their expected
   import values — ``project_id`` == the project the import targets,
   ``event_stream_id`` == the mapped stream id, ``name`` == the
   source-side identity name (fallback ``timeline_ulid``) (verify what
   you serve, W4; round-2 P2#1); AND the stream row's OWN identity
   columns equal their expected import values — ``event_streams.project_id``
   == the import-target project (alias resolution, repository.py:1588),
   ``.stream_type`` == the pack ``TIMELINE_STREAM_TYPE`` constant imported
   from ``astrid.packs.timeline.repository`` (save agreement check,
   service.py:372), ``.aggregate_id`` == ``source.timeline_id`` (save
   subject authority) (round-3 P1#1).

Verification placement (W1): the full verifier runs TWICE per fresh import —
once INSIDE the ``BEGIN IMMEDIATE`` unit of work against the transaction
connection (any mismatch rolls the whole timeline back: zero
events/receipts/projections), and once read-only after commit before the
marker write. Verification reads the stream via a COUNT query plus paged
iteration (keyset on ``seq``, page 1000), so there is no 10k repository
hard-cap in this path. A retry that finds an existing kernel stream + a
matching backfill receipt fully re-verifies read-only and then idempotently
writes/refreshes the marker — after ANY interruption the state converges to
exactly ``{nothing written}`` or ``{events + receipt + marker, fully
verified}``.

Bootstrap synthesis (W3): when a source has no ``timeline.created`` event,
the import synthesizes ONE deterministic bootstrap event inside the same
transaction before the source events — kind ``timeline.created``,
deterministic event id via :func:`derive_timeline_ulid`, data
``{timeline_id, slug, name}`` enriched per :func:`_enrich_created_data`
conventions (the enriched ``timeline_ulid`` follows the existing identity
rules: the identity sidecar ULID for local_fs, the deterministic
:func:`derive_timeline_ulid` derivation for supabase-export sources, so
the editor's ULID addressability is unchanged), actor_kind ``system``,
created_at = the first source event's ts. The synthesis is deterministic,
so retries produce the identical kernel row and the content check treats
it as the expected position-0 row.

Contract notes (W7d): the frozen ``events`` table carries only
``actor_kind``, so ``actor.id`` / ``actor.display`` / ``actor.via`` are
intentionally not preserved (documented drop); the legacy undo/erasure
selector surfaces are retired and never emitted; transfer provenance rides
the receipts and the marker (``events_sha256`` + per-timeline source
identity), never hidden columns.

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

Honesty boundary (round-3 P2#1, part 3): the LocalFs identity sidecar and
the fallback ``registry.json`` are NOT part of the event hash chain. A
FIRST-import tamper of an unanchored sidecar — one with no
``timeline.created`` event to cross-check (slice-shaped sources), or of a
sidecar field the created event does not carry (e.g. the ULID, which today
lives only in the sidecar) — is undetectable in a trustless file export,
exactly like any correctly-rehashed event tamper: the import receives a
consistent, digestable source and certifies it. The sidecar digests do NOT
close that window; they make every LATER import (resume/re-import) fail
closed with named drift, and the created-event cross-check closes the name
leg for full-lifecycle sources. This is the same accepted limit as rehashed
event tampering: the export is trusted on first import. Do not oversell the
guarantee. Crash-after-commit replay also validates the sidecar digests
against the receipt's persisted digests: before a replay completes or
refreshes the marker, any ``identity_sha256``/``registry_sha256`` mismatch
fails closed with :class:`BackfillDiscrepancyError` and zero marker
mutation (G). A bridge save against a corrupted stream identity
(``event_streams.project_id``/``stream_type``/``aggregate_id`` drifting
from the backfilled source) maps to 400 ``invalid_timeline`` via the
pre-existing taxonomy (``bridge.py:251``) — corruption is surfaced, not
silently served.
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
import time
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
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
import importlib as _il
LocalFsBackend = _il.import_module("astrid.core.timeline.eventlog.local_fs").LocalFsBackend  # type: ignore[attr-defined]
from astrid.core.timeline.events.schema import (
    TimelineActor,
    TimelineEvent,
    canonical_json_bytes,
)
from astrid.core.timeline.projection import replay_projection
from astrid.core.util.time import utc_now_iso
from astrid.packs.timeline.repository import TIMELINE_STREAM_TYPE

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

_TIMELINE_STREAM_TYPE = TIMELINE_STREAM_TYPE
"""Pack stream type (single source of truth: ``packs/timeline/repository.py``
``TIMELINE_STREAM_TYPE`` — never a second literal, round-3 P1#1)."""

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
    slug: str | None  # immutable alias slug (identity display for local_fs)
    events: tuple[TimelineEvent, ...]  # ordered 1..head_version
    head_version: int
    events_sha256: str
    projected_config: dict[str, Any]
    projected_registry: dict[str, Any]  # {"assets": {...}}
    # Round-3 P2#1: sha256 of the identity-sidecar FILE BYTES (raw bytes,
    # never canonical re-serialization) for local_fs sources; "" for
    # supabase_export sources (no identity sidecar exists — identity is
    # derived from chained events). ``registry_sha256`` is the sha256 of
    # the ``registry.json`` sidecar file bytes when the fallback supplied
    # the projection (no asset_registry_replaced event), None when the
    # registry came from events. Both bind post-import sidecar drift on
    # resume/re-import (W2 machinery).
    identity_sha256: str = ""
    registry_sha256: str | None = None

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
            "identity_sha256": self.identity_sha256,
            "registry_sha256": self.registry_sha256 or "",
        }


@dataclass(frozen=True, slots=True)
class BackfillVerification:
    """The reusable zero-loss verification for one backfilled timeline.

    ``mismatches`` carries one human-readable detail per failing invariant so
    a discrepancy is actionable; ``ok`` is False unless (a) count, (b) head,
    (c) content, (e) per-kind preservation, and (g) projection checks all
    hold. ``synthesized_count`` is the number of synthesized bootstrap
    events the expected stream carries (0 or 1; W3), and
    ``projection_mismatches`` carries the W4 column/index details separately
    so the report can distinguish them — including the bridge-served
    identity columns (``project_id`` / ``event_stream_id`` / ``name``,
    round-2 P2#1).
    """

    source_event_count: int
    kernel_event_count: int
    source_head_version: int
    kernel_head_seq: int
    source_kinds: dict[str, int]
    kernel_kinds: dict[str, int]
    mismatches: tuple[str, ...] = ()
    synthesized_count: int = 0
    projection_mismatches: tuple[str, ...] = ()

    @property
    def expected_event_count(self) -> int:
        """The expected kernel event count (source + synthesized bootstrap)."""
        return self.source_event_count + self.synthesized_count

    @property
    def expected_head(self) -> int:
        """The expected kernel head (source version + synthesized count)."""
        return self.source_head_version + self.synthesized_count

    @property
    def count_ok(self) -> bool:
        return self.expected_event_count == self.kernel_event_count

    @property
    def head_ok(self) -> bool:
        return self.expected_head == self.kernel_head_seq

    @property
    def content_ok(self) -> bool:
        return not any(item.startswith("content") for item in self.mismatches)

    @property
    def kinds_ok(self) -> bool:
        return self.source_kinds == self.kernel_kinds

    @property
    def projection_ok(self) -> bool:
        return not self.projection_mismatches

    @property
    def synthesized_bootstrap(self) -> bool:
        return self.synthesized_count > 0

    @property
    def ok(self) -> bool:
        return (
            self.count_ok
            and self.head_ok
            and self.content_ok
            and self.kinds_ok
            and self.projection_ok
            and not self.mismatches
        )

    def checks_dict(self) -> dict[str, bool]:
        return {
            "count": self.count_ok,
            "head": self.head_ok,
            "content": self.content_ok,
            "kinds": self.kinds_ok,
            "projections": self.projection_ok,
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
            "synthesized_bootstrap": self.synthesized_bootstrap,
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
    synthesized_bootstrap: bool
    evaluated: bool
    projected_config_sha256: str
    projected_registry_sha256: str
    detail: str = ""
    # Round-3 P2#1: identity/registry sidecar file digests ("" when no
    # sidecar applies — supabase_export sources have none). Carried by the
    # report so the receipt and the authority marker bind post-import
    # sidecar drift on resume/re-import.
    identity_sha256: str = ""
    registry_sha256: str = ""

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
            "synthesized_bootstrap": self.synthesized_bootstrap,
            "evaluated": self.evaluated,
            "projected_config_sha256": self.projected_config_sha256,
            "projected_registry_sha256": self.projected_registry_sha256,
            "detail": self.detail,
            "identity_sha256": self.identity_sha256,
            "registry_sha256": self.registry_sha256,
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


def _identity_ulid_and_name(identity: dict[str, Any], timeline_id: str) -> tuple[str, str | None, str | None]:
    timeline_ulid = identity.get("timeline_ulid")
    if not isinstance(timeline_ulid, str) or not timeline_ulid:
        timeline_ulid = derive_timeline_ulid(timeline_id)
    display = identity.get("display")
    name = None
    slug = None
    if isinstance(display, dict):
        if isinstance(display.get("name"), str):
            name = display["name"]
        if isinstance(display.get("slug"), str) and display["slug"]:
            slug = display["slug"]
    return timeline_ulid, name, slug


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------


def load_local_fs_source(
    timeline_home: str | Path,
    *,
    timeline_id: str | None = None,
) -> BackfillSource:
    """Load and validate one immutable LocalFs source export (read-only).

    Never writes to *timeline_home*: the hash chain is verified first
    (``LocalFsBackend.verify_chain`` — a broken chain fails closed before
    any event is read, round-2 P3#5), events are read through
    ``LocalFsBackend.read_events`` and the head sidecar is parsed directly
    (see :func:`_read_head_version`). Fail closed on any inconsistency.

    Round-3 P2#1: the identity sidecar and the fallback ``registry.json``
    are load-bearing but UNANCHORED (outside the event hash chain), so:

    - when the events contain ``timeline.created``, the sidecar name and
      timeline_ulid must equal the event-derived values (the created event
      carries ``name`` and — when present — ``timeline_ulid``); any
      disagreement raises :class:`BackfillSourceError` naming it. The
      Supabase-export leg needs no such check: it derives identity from
      chained events (``_export_identity``), so there is no sidecar to
      launder through;
    - the sha256 of the identity-sidecar FILE BYTES (and of the
      ``registry.json`` bytes when the fallback supplies the projection) is
      carried by the source, recorded in the receipt AND the authority
      marker, and recomputed on resume/re-import — drift fails closed with
      the named digest (W2 machinery).
    """
    home = Path(timeline_home)
    identity = _read_identity(home)
    source_timeline_id = str(identity["timeline_id"])
    identity_sha256 = hashlib.sha256(
        (home / "assembly.identity.json").read_bytes()
    ).hexdigest()
    if timeline_id is not None and timeline_id != source_timeline_id:
        raise BackfillSourceError(
            f"requested timeline {timeline_id!r} does not match the source "
            f"identity {source_timeline_id!r} in {home.name}"
        )
    backend = LocalFsBackend(
        timeline_id=source_timeline_id, timeline_home=home
    )
    # Round-2 P3#5: verify the hash chain BEFORE any event is read into the
    # source. A payload edited without recomputing its hash must fail closed
    # here, never laundered into a fresh kernel chain downstream (the same
    # guard the Supabase-export leg runs in ``_build_supabase_source``).
    chain = backend.verify_chain()
    if not chain.ok:
        detail = chain.error or "unknown chain error"
        raise BackfillSourceError(
            f"source chain invalid: {detail} "
            f"(checked {chain.checked_events} events)"
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
    timeline_ulid, name, slug = _identity_ulid_and_name(
        identity, source_timeline_id
    )
    # Round-3 P2#1 (part 1): derivable cross-checks fail closed at load.
    # When the events carry ``timeline.created``, the sidecar name (and
    # timeline_ulid when the created event carries one) must equal the
    # event-derived values — a sidecar tamper can no longer launder through
    # with ``chain_ok=True``. The created event today carries
    # ``{timeline_id, slug, name}`` (no ULID), so the ULID leg is checked
    # only when an event-derived ULID exists; the honesty boundary in the
    # module docstring states the residual first-import limit.
    _cross_check_identity_sidecar(
        events,
        timeline_id=source_timeline_id,
        timeline_ulid=timeline_ulid,
        name=name,
        home_name=home.name,
    )
    projected_config = replay_projection(backend)
    registry = _project_registry(events)
    registry_sha256: str | None = None
    if registry is None:
        registry, registry_bytes = _read_registry_sidecar_with_digest(home)
        registry_sha256 = hashlib.sha256(registry_bytes).hexdigest()
    return BackfillSource(
        source_name=BACKFILL_MARKER_SOURCE_LOCAL_FS,
        timeline_id=source_timeline_id,
        timeline_ulid=timeline_ulid,
        name=name,
        slug=slug,
        events=events,
        head_version=head_version,
        events_sha256=source_events_sha256(events),
        projected_config=dict(projected_config),
        projected_registry=registry,
        identity_sha256=identity_sha256,
        registry_sha256=registry_sha256,
    )


def _cross_check_identity_sidecar(
    events: Sequence[TimelineEvent],
    *,
    timeline_id: str,
    timeline_ulid: str,
    name: str | None,
    home_name: str,
) -> None:
    """Fail closed when a ``timeline.created`` event disagrees with the
    identity sidecar (round-3 P2#1 part 1).

    The created event's payload carries the event-derived ``name`` (and,
    when present, ``timeline_ulid``); the sidecar's claims must equal them
    or the source is internally inconsistent — an unanchored sidecar tamper
    must not launder into the kernel chain with ``chain_ok=True``. The
    created event has no other identity fields today, so nothing else is
    derivable; the module docstring records the honest first-import limit.
    """
    created = next(
        (event for event in events if event.kind == _TIMELINE_CREATED_KIND),
        None,
    )
    if created is None:
        return
    data = _payload_dict(created)
    event_name = data.get("name")
    if isinstance(event_name, str) and event_name:
        if name != event_name:
            raise BackfillSourceError(
                f"timeline source identity name {name!r} disagrees with the "
                f"timeline.created event name {event_name!r} in {home_name}"
            )
    event_ulid = data.get("timeline_ulid")
    if isinstance(event_ulid, str) and event_ulid:
        if timeline_ulid != event_ulid:
            raise BackfillSourceError(
                f"timeline source identity timeline_ulid {timeline_ulid!r} "
                f"disagrees with the timeline.created event timeline_ulid "
                f"{event_ulid!r} in {home_name}"
            )
    # The event timeline_id is already enforced per-event above; slug is
    # carried by the created event but not load-bearing for the sidecar
    # (the kernel alias comes from the created event, enriched from the
    # sidecar ULID only).


def _read_registry_sidecar_with_digest(home: Path) -> tuple[dict[str, Any], bytes]:
    """Read the fallback ``registry.json`` sidecar and its RAW file bytes.

    Returns ``(projection, bytes)`` — the bytes feed the digest that binds
    post-import sidecar drift (round-3 P2#1 part 2); an absent file yields
    the empty projection with empty bytes (digest of ``b""``), since the
    fallback still "supplied" the projection.
    """
    from astrid.core._shared.jsonio import read_json

    registry_path = home / "registry.json"
    if not registry_path.is_file():
        return {"assets": {}}, b""
    try:
        raw_bytes = registry_path.read_bytes()
        raw = read_json(registry_path)
    except Exception:
        raise BackfillSourceError(
            f"timeline source registry.json is unreadable in {home.name}"
        ) from None
    if isinstance(raw, dict) and isinstance(raw.get("assets"), dict):
        return {"assets": raw["assets"]}, raw_bytes
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
        if not raw_items:
            raise BackfillSourceError(
                f"supabase export contains no rows: {self.path.name}"
            )
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
            raw_timeline_id = raw.get("timeline_id")
            if not isinstance(raw_timeline_id, str) or not raw_timeline_id:
                raise BackfillSourceError(
                    f"supabase export item {index} has no timeline_id"
                )
            if raw_timeline_id != self.timeline_id:
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
        import importlib as _il2
        EventLogVerification = _il2.import_module("astrid.core.timeline.eventlog.types").EventLogVerification  # type: ignore[attr-defined]

        events, versions = self._load()
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
                version = versions[index] if index < len(versions) else index + 1
                return EventLogVerification(
                    ok=False,
                    checked_events=index,
                    last_event_id=None,
                    error=(
                        f"chain link broken at version {version} "
                        f"(event {event.event_id})"
                    ),
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
    """Shared source construction for the Supabase leg (file or transport).

    Fail-closed envelope (W5): the chain is verified BEFORE the source is
    built — a broken chain raises :class:`BackfillSourceError` naming the
    failing version — an empty export is rejected, and every malformed row
    rejects the whole export naming its index (no silent skips).
    """
    if not events:
        raise BackfillSourceError(
            f"supabase export contains no rows for timeline {timeline_id!r}"
        )
    chain = reader.verify_chain() if hasattr(reader, "verify_chain") else None
    if chain is not None and not chain.ok:
        detail = chain.error or "unknown chain error"
        raise BackfillSourceError(
            f"supabase export chain verification failed for timeline "
            f"{timeline_id!r}: {detail}"
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
    timeline_ulid, name, slug = _export_identity(events, timeline_id)
    projected_config = replay_projection(reader)
    registry = _project_registry(events)
    if registry is None:
        registry = {"assets": {}}
    return BackfillSource(
        source_name=BACKFILL_MARKER_SOURCE_SUPABASE,
        timeline_id=timeline_id,
        timeline_ulid=timeline_ulid,
        name=name,
        slug=slug,
        events=tuple(events),
        head_version=head_version,
        events_sha256=source_events_sha256(events),
        projected_config=dict(projected_config),
        projected_registry=registry,
        # No identity/registry sidecars exist for supabase exports —
        # identity is derived from chained events (``_export_identity``) and
        # the registry from events; no sidecar digests apply (round-3
        # P2#1: stated explicitly — no change to this leg).
        identity_sha256="",
        registry_sha256=None,
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
) -> tuple[str, str | None, str | None]:
    """Derive the ULID alias, display name, and slug from an export's
    created event.

    The created event data carries ``timeline_id``/``slug``/``name``; the
    ULID alias is derived deterministically (the export envelope has no
    identity sidecar). A source without a created event yields ``None``
    name/slug — the bootstrap synthesis then derives deterministic
    fallbacks.
    """
    name: str | None = None
    slug: str | None = None
    for event in events:
        if event.kind != _TIMELINE_CREATED_KIND:
            continue
        data = _payload_dict(event)
        candidate = data.get("name")
        if isinstance(candidate, str) and candidate:
            name = candidate
        candidate_slug = data.get("slug")
        if isinstance(candidate_slug, str) and candidate_slug:
            slug = candidate_slug
        break
    return derive_timeline_ulid(timeline_id), name, slug


# ---------------------------------------------------------------------------
# Authority marker (R5)
# ---------------------------------------------------------------------------


BACKFILL_STATE_LOCK_FILENAME = "backfill-state.lock"
"""Advisory flock file serializing marker read-modify-write (W7a)."""


def _state_lock_path(projects_root: str | Path) -> Path:
    """Return ``<projects_root>/.astrid/backfill-state.lock`` (W7a)."""
    return Path(projects_root) / ASTROID_DIR_NAME / BACKFILL_STATE_LOCK_FILENAME


def _state_lock(projects_root: str | Path) -> Any:
    """Acquire the exclusive marker-write flock (W7a).

    The lock file lives beside the marker (same ``.astrid`` directory) and
    is created on demand; the flock serializes concurrent backfill runs'
    read-modify-write of ``backfill-state.json`` while the atomic replace
    (``write_json_atomic``) preserves the write itself.
    """
    import fcntl

    path = _state_lock_path(projects_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


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
    synthesized_bootstrap: bool = False,
    backfilled_at: str | None = None,
) -> dict[str, Any]:
    """Atomically record one timeline's authority state (R5).

    Read-modify-write of the whole marker file through
    ``foundation.atomic_io.write_json_atomic``, serialized by the
    ``backfill-state.lock`` flock (W7a); the schema is documented in the
    module docstring. ``synthesized_bootstrap`` is always recorded (shape
    extended additively).
    """
    with _state_lock(projects_root):
        state = read_backfill_state(projects_root)
        entry = {
            "backfilled_at": backfilled_at or utc_now_iso(),
            "source": source,
            "source_head_version": source_head_version,
            "events_sha256": events_sha256,
            "synthesized_bootstrap": bool(synthesized_bootstrap),
        }
        state[str(timeline_id)] = entry
        write_json_atomic(backfill_state_path(projects_root), state)
    return entry


# ---------------------------------------------------------------------------
# The reusable zero-loss checker
# ---------------------------------------------------------------------------

_VERIFY_PAGE_SIZE = 1000
"""Keyset page size for verification reads (W1.2: no repository hard-cap)."""

_STREAM_EVENT_SELECT = (
    "SELECT event_id, project_id, project_seq, stream_id, seq, subject_type, "
    "subject_id, changes_json, kind, schema_version, idempotency_key, txn_id, "
    "actor_kind, payload_json, created_at FROM events"
)


class _ConnectionReader:
    """Thin query adapter over a raw ``sqlite3.Connection`` (read-only)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def query(self, sql: str, parameters: Sequence[Any] = ()) -> list[Any]:
        return list(self._conn.execute(sql, tuple(parameters)).fetchall())

    def query_one(self, sql: str, parameters: Sequence[Any] = ()) -> Any:
        return self._conn.execute(sql, tuple(parameters)).fetchone()


def _stream_count(reader: Any, stream_id: str) -> int:
    """Return the event COUNT for one stream (W1.2 COUNT query)."""
    row = reader.query_one(
        "SELECT COUNT(*) AS n FROM events WHERE stream_id = ?", (stream_id,)
    )
    return int(row["n"]) if row is not None else 0


def _paged_stream_models(
    reader: Any, stream_id: str, *, page_size: int = _VERIFY_PAGE_SIZE
) -> list[Any]:
    """Read one stream's full event list, keyset-paged on ``seq``.

    Reads ``page_size`` rows per page using ``seq > last`` (the stream's
    ``UNIQUE (stream_id, seq)`` index), so verification never hits the
    repository's 10k single-read cap (W1.2). The reader must expose
    ``query(sql, parameters)`` returning rows addressable by column name —
    a :class:`~astrid.core.store.uow.UnitOfWork` (transaction connection)
    or a read-only connection adapter both qualify.
    """
    from astrid.core.repositories.events import _read_model_from_row

    models: list[Any] = []
    after_seq = 0
    while True:
        rows = reader.query(
            _STREAM_EVENT_SELECT
            + " WHERE stream_id = ? AND seq > ? ORDER BY seq ASC LIMIT ?",
            (stream_id, after_seq, page_size),
        )
        if not rows:
            break
        for row in rows:
            models.append(_read_model_from_row(row))
        after_seq = int(rows[-1]["seq"])
    return models


def _verify_on(
    reader: Any,
    source: BackfillSource,
    *,
    stream_id: str,
    project_id: str,
    synthesized_events: Sequence[TimelineEvent] = (),
) -> BackfillVerification:
    """Run the zero-loss invariants (a),(b),(c),(e),(g) against *reader*.

    *reader* may be a :class:`~astrid.core.store.uow.UnitOfWork` (inside
    the import transaction, W1) or a read-only connection adapter (public
    :func:`verify_backfill`). The expected stream is the synthesized
    bootstrap event(s) followed by every source event; expected head is
    ``source.head_version + synthesized_count`` (invariant b, W3).
    ``mismatches`` names every failed check, ``projection_mismatches`` the
    W4 stored-projection diffs (column + timeline id) — including the
    bridge-served identity columns ``project_id`` / ``event_stream_id`` /
    ``name``, each compared against the expected value the import wrote
    (round-2 P2#1), and the ``event_streams`` stream-identity columns
    ``project_id`` / ``stream_type`` / ``aggregate_id`` the bridge/save
    surface keys on (round-3 P1#1): expected values are the threaded
    import-target project, the pack ``TIMELINE_STREAM_TYPE`` constant
    imported from ``astrid.packs.timeline.repository``, and
    ``source.timeline_id``.
    """
    mismatches: list[str] = []
    projection_mismatches: list[str] = []
    synthesized_events = tuple(synthesized_events)
    expected_events = synthesized_events + source.events

    # Round-3 P1#1: the bridge/save surface ALSO keys on the stream's
    # identity columns, so the SELECT carries them alongside ``head_seq`` —
    # ``project_id`` (alias resolution, repository.py:1588), ``stream_type``
    # (save agreement check, service.py:372) and ``aggregate_id`` (save
    # subject authority). A tampered value must fail certification here, not
    # merely mis-serve the bridge later.
    row = reader.query_one(
        "SELECT head_seq, project_id, stream_type, aggregate_id "
        "FROM event_streams WHERE id = ?",
        (stream_id,),
    )
    kernel_head_seq = int(row["head_seq"]) if row is not None else 0
    kernel_event_count = _stream_count(reader, stream_id)
    kernel_models = _paged_stream_models(reader, stream_id)

    expected_head = source.head_version + len(synthesized_events)
    expected_count = len(source.events) + len(synthesized_events)

    if expected_head != kernel_head_seq:
        mismatches.append(
            f"head: expected {expected_head} (source {source.head_version} "
            f"+ {len(synthesized_events)} synthesized) != kernel head_seq "
            f"{kernel_head_seq}"
        )
    if expected_count != kernel_event_count:
        mismatches.append(
            f"count: expected {expected_count} (source {len(source.events)} "
            f"+ {len(synthesized_events)} synthesized) != kernel "
            f"{kernel_event_count}"
        )
    kernel_kinds = dict(Counter(model.kind for model in kernel_models))
    expected_kinds = dict(
        Counter(event.kind for event in expected_events)
    )
    if expected_kinds != kernel_kinds:
        mismatches.append(
            f"kinds: expected {expected_kinds} != kernel {kernel_kinds}"
        )

    # (c) content projection, position by position (kernel seq == expected
    # stream position == 1-based index), plus the mapper-derived txn_id and
    # changes_json (W4).
    for index, (expected_event, model) in enumerate(
        zip(expected_events, kernel_models), start=1
    ):
        if model.seq != index:
            mismatches.append(f"content: kernel seq {model.seq} != {index}")
            continue
        mapped = map_source_event(
            expected_event, timeline_ulid=source.timeline_ulid
        )
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
        if model.event_id != expected_event.event_id:
            mismatches.append(
                f"content: event {index} event_id not preserved"
            )
        if model.txn_id != mapped.txn_id:
            mismatches.append(
                f"content: event {index} txn_id {model.txn_id!r} != "
                f"mapped {mapped.txn_id!r}"
            )
        if list(model.changes) != list(mapped.changes):
            mismatches.append(
                f"content: event {index} changes_json differs from "
                "mapper-derived changes"
            )

    # (g) verify what you serve (W4): stored whole-document projections vs
    # the source-side projected config/registry, naming column + timeline id.
    # Round-2 P2#1: the bridge also serves ``project_id``, ``event_stream_id``
    # and ``name`` from this row (repository.py:1706), so all three identity
    # columns are verified against the expected import values too — each
    # mismatch names the column. The expected ``name`` is the source-side
    # identity value (local_fs: identity sidecar ``display.name``;
    # supabase_export: the created-event data name), falling back to the
    # timeline ULID exactly like the import write; the source carries no
    # project identity of its own, so the kernel ``project_id`` is compared
    # against the project the import targets (threaded from the caller).
    timeline_row = reader.query_one(
        "SELECT project_id, event_stream_id, name, document_json, "
        "asset_registry_json FROM timelines WHERE id = ?",
        (source.timeline_id,),
    )
    if timeline_row is None:
        projection_mismatches.append(
            f"projection: timelines row missing for index {source.timeline_id}"
        )
    else:
        expected_name = source.name or source.timeline_ulid
        if str(timeline_row["event_stream_id"]) != stream_id:
            projection_mismatches.append(
                f"identity: event_stream_id (index {source.timeline_id}) "
                f"{timeline_row['event_stream_id']!r} != expected {stream_id!r}"
            )
        if str(timeline_row["name"]) != expected_name:
            projection_mismatches.append(
                f"identity: name (index {source.timeline_id}) "
                f"{timeline_row['name']!r} != expected {expected_name!r}"
            )
        if str(timeline_row["project_id"]) != project_id:
            projection_mismatches.append(
                f"identity: project_id (index {source.timeline_id}) "
                f"{timeline_row['project_id']!r} != expected {project_id!r}"
            )
        try:
            stored_document = parse_json(str(timeline_row["document_json"]))
        except CanonicalizationError:
            stored_document = None
        if canonical_json(stored_document) != canonical_json(source.projected_config):
            projection_mismatches.append(
                f"projection: document_json (index {source.timeline_id}) "
                "differs from source.projected_config"
            )
        try:
            stored_registry = parse_json(
                str(timeline_row["asset_registry_json"])
            )
        except CanonicalizationError:
            stored_registry = None
        if canonical_json(stored_registry) != canonical_json(
            source.projected_registry["assets"]
        ):
            projection_mismatches.append(
                f"projection: asset_registry_json (index {source.timeline_id}) "
                "differs from source.projected_registry.assets"
            )

    # Round-3 P1#1: the stream row's OWN identity columns are bridge/save
    # surface too — ``event_streams.project_id`` (alias resolution,
    # repository.py:1588), ``.stream_type`` (save agreement check,
    # service.py:372) and ``.aggregate_id`` (save subject authority). Each
    # is compared against the value the import wrote and each mismatch names
    # the column (the ``identity: …`` style above). ``stream_type`` is
    # compared against the pack constant imported from
    # ``astrid.packs.timeline.repository`` — never a second literal.
    if row is None:
        projection_mismatches.append(
            f"identity: event_streams row missing (index {source.timeline_id})"
        )
    else:
        if str(row["project_id"]) != project_id:
            projection_mismatches.append(
                f"identity: event_streams.project_id (index "
                f"{source.timeline_id}) {row['project_id']!r} != expected "
                f"{project_id!r}"
            )
        if str(row["stream_type"]) != TIMELINE_STREAM_TYPE:
            projection_mismatches.append(
                f"identity: event_streams.stream_type (index "
                f"{source.timeline_id}) {row['stream_type']!r} != expected "
                f"{TIMELINE_STREAM_TYPE!r}"
            )
        if str(row["aggregate_id"]) != source.timeline_id:
            projection_mismatches.append(
                f"identity: event_streams.aggregate_id (index "
                f"{source.timeline_id}) {row['aggregate_id']!r} != expected "
                f"{source.timeline_id!r}"
            )

    return BackfillVerification(
        source_event_count=len(source.events),
        kernel_event_count=kernel_event_count,
        source_head_version=source.head_version,
        kernel_head_seq=kernel_head_seq,
        source_kinds=expected_kinds,
        kernel_kinds=kernel_kinds,
        mismatches=tuple(mismatches),
        synthesized_count=len(synthesized_events),
        projection_mismatches=tuple(projection_mismatches),
    )


def verify_backfill(
    source: BackfillSource,
    *,
    stream_id: str,
    project_id: str,
    writer: DatabaseWriter,
    synthesized_events: Sequence[TimelineEvent] = (),
) -> BackfillVerification:
    """Run the zero-loss invariants (a),(b),(c),(e),(g) against the kernel.

    Read-only: runs on the writer's transaction-free read-only connection
    and never mutates state. ``mismatches`` names every failed check;
    ``projection_mismatches`` names the W4 stored-projection diffs
    (including the bridge-served identity columns, round-2 P2#1, and the
    ``event_streams`` stream-identity columns, round-3 P1#1).
    ``synthesized_events`` carries the deterministic bootstrap event(s) the
    expected stream prepends (W3); verification reads the stream via a
    COUNT query plus keyset paging, so there is no 10k cap in this path.
    ``project_id`` is the project the import targets (the caller resolves
    it); the stored ``timelines.project_id`` must equal it.
    """
    with writer.read_only_connection() as conn:
        reader = _ConnectionReader(conn)
        return _verify_on(
            reader,
            source,
            stream_id=stream_id,
            project_id=project_id,
            synthesized_events=synthesized_events,
        )


# ---------------------------------------------------------------------------
# The import orchestrator
# ---------------------------------------------------------------------------


def _stream_id(timeline_id: str) -> str:
    return f"{timeline_id}:{_TIMELINE_STREAM_TYPE}"


def _bootstrap_fallback_slug(source: BackfillSource) -> str:
    """Deterministic slug fallback for a source with no identity slug.

    ``timeline-<8 hex>`` is always a valid immutable slug (lowercase hex +
    hyphen); used only when the source carries no slug at all (a Supabase
    export without a created event). Local-FS sources always carry the
    identity ``display.slug``.
    """
    return f"timeline-{source.timeline_id[:8]}"


def _synthesize_created_event(source: BackfillSource) -> TimelineEvent:
    """Deterministic bootstrap ``timeline.created`` event (W3).

    Built for a source that has no ``timeline.created`` event: kind
    ``timeline.created``, deterministic event id via
    :func:`derive_timeline_ulid`, data ``{timeline_id, slug, name}``
    enriched per :func:`_enrich_created_data` conventions (the enriched
    ``timeline_ulid`` follows the existing identity rules — the identity
    sidecar ULID for local_fs, the deterministic derivation for
    supabase-export sources, so the editor's ULID addressability is
    unchanged), actor_kind ``system``, created_at = the first source
    event's ts. Deterministic, so every retry produces the identical kernel
    row and the content check treats it as the expected position-0 row.
    """
    if not source.events:
        raise BackfillSourceError(
            f"cannot synthesize a bootstrap event for empty timeline "
            f"{source.timeline_id!r}"
        )
    return TimelineEvent(
        event_id=derive_timeline_ulid(source.timeline_id).upper(),
        timeline_id=source.timeline_id,
        ts=source.events[0].ts,
        actor=TimelineActor(type="system", id="system:backfill-bootstrap"),
        prev_hash=None,
        hash=None,
        kind=_TIMELINE_CREATED_KIND,
        payload={
            "timeline_id": source.timeline_id,
            "slug": source.slug or _bootstrap_fallback_slug(source),
            "name": source.name or f"timeline-{source.timeline_id[:8]}",
        },
        expected_version=None,
        schema_version=1,
        txn_id=None,
    )


def _expected_stream(
    source: BackfillSource,
) -> tuple[tuple[TimelineEvent, ...], tuple[MappedEvent, ...]]:
    """Return ``(synthesized_events, mapped_events)`` for one source.

    When the source has no ``timeline.created`` event, exactly one
    deterministic bootstrap event is synthesized FIRST (W3); every expected
    event is then mapped to its kernel append parameters. Deterministic and
    shared by the import, the resume revalidation, and the content check.
    """
    synthesized: tuple[TimelineEvent, ...] = ()
    if not any(
        event.kind == _TIMELINE_CREATED_KIND for event in source.events
    ):
        synthesized = (_synthesize_created_event(source),)
    mapped = tuple(
        map_source_event(event, timeline_ulid=source.timeline_ulid)
        for event in synthesized + source.events
    )
    return synthesized, mapped


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


def allocate_run_checkpoint_id(
    project_slug: str, *, root: str | Path | None = None
) -> str:
    """Exclusively allocate one fresh run checkpoint id (round-3 P3#1).

    Creates ``<project>/runs/migrations/<epoch>-<uuid4().hex>/`` with
    fail-if-exists semantics (``mkdir(parents=True, exist_ok=False)``) and
    a bounded retry on collision: each attempt uses a FRESH full-length
    ``uuid4().hex`` and a hard error surfaces after 5 attempts. Uniqueness
    becomes a filesystem guarantee — two runs started in the same second
    can never share one checkpoint dir. The explicit-resume path (caller
    passes ``run_ts``) never allocates; it reuses the interrupted run's
    dir. Public surface for the SDK/CLI to return the ACTIVE run id so an
    interrupted fresh run is resumable verbatim (round-3 P3#2).
    """
    root_path = resolve_projects_root(root)
    slug = validate_project_slug(project_slug)
    return _allocate_run_checkpoint_id(slug, root=root_path)


def _allocate_run_checkpoint_id(project_slug: str, *, root: Path) -> str:
    """Bounded-retry exclusive allocation (see :func:`allocate_run_checkpoint_id`)."""
    from astrid.core.timeline.migration import checkpoint_path_for_run

    for attempt in range(5):
        candidate = f"{int(time.time())}-{uuid.uuid4().hex}"
        checkpoint_file = checkpoint_path_for_run(
            project_slug, root=root, run_ts=candidate
        )
        run_dir = checkpoint_file.parent
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return candidate
    raise BackfillError(
        "could not allocate a fresh backfill run checkpoint directory for "
        f"project {project_slug!r} after 5 attempts"
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
    2. bootstrap synthesis (W3): a source without ``timeline.created`` gets
       exactly one deterministic synthesized event, prepended inside the
       same transaction (invariant b becomes ``head_seq == source_version +
       synthesized_count``);
    3. authority-marker guard (R5): an existing marker that DISAGREES with
       this source (different source identity for the same timeline) is
       refused before any write — a MATCHING marker is not refused;
    4. one ``BEGIN IMMEDIATE`` unit of work: receipt idempotency gate
       first (an identical earlier import replays its stored result with
       zero new rows; a stream that exists WITHOUT a matching receipt is
       foreign kernel state and fences); then insert the timeline stream
       and the whole-document projection, append every expected event 1:1
       (hash-chained SD2 envelopes), and run the FULL verifier AGAINST THE
       TRANSACTION CONNECTION (W1) — any mismatch raises
       :class:`BackfillDiscrepancyError` and the whole timeline rolls back:
       zero events, zero receipts, zero projections;
    5. after commit, re-verify every invariant read-only (W1.3) and then
       idempotently write/refresh the authority marker (f) — matching
       retries converge the marker instead of raising, so a crash between
       commit and marker-write is healed on the next run.

    After ANY interruption the state converges to exactly ``{nothing
    written}`` or ``{events + receipt + marker, fully verified}``.
    """
    root = resolve_projects_root(projects_root)
    project_slug = validate_project_slug(project_slug)
    project_id = projects.resolve(writer, project_slug)
    marker_path = str(backfill_state_path(root))

    synthesized_events, mapped_events = _expected_stream(source)
    synthesized_count = len(synthesized_events)
    expected_head = source.head_version + synthesized_count

    # Authority-marker guard (R5): only a MISMATCH fences as foreign
    # authority; a matching marker is convergence territory (W1.3).
    if not dry_run:
        state = read_backfill_state(root)
        existing = state.get(source.timeline_id)
        if existing is not None and (
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
        # Round-3 P2#1 (part 2): the sidecar digests are part of the source
        # identity for local_fs — a post-import sidecar edit must fail
        # closed with NAMED digest drift (never silently refresh the marker
        # with the new bytes). Supabase sources record "" and compare
        # trivially (no sidecar exists).
        if existing is not None and existing.get(
            "identity_sha256", ""
        ) != source.identity_sha256:
            raise BackfillDiscrepancyError(
                f"timeline {source.timeline_id} identity sidecar drifted "
                f"since backfill: identity_sha256 "
                f"{existing.get('identity_sha256', '')} (marker) != "
                f"{source.identity_sha256} (current); operator reruns fresh"
            )
        if existing is not None and existing.get(
            "registry_sha256", ""
        ) != (source.registry_sha256 or ""):
            raise BackfillDiscrepancyError(
                f"timeline {source.timeline_id} registry sidecar drifted "
                f"since backfill: registry_sha256 "
                f"{existing.get('registry_sha256', '')} (marker) != "
                f"{source.registry_sha256 or ''} (current); operator reruns "
                "fresh"
            )

    stream_id = _stream_id(source.timeline_id)
    head_seq, stream_exists = _current_stream_state(writer, source.timeline_id)

    if dry_run:
        # Honest dry-run (W6): source-side consistency only. When a kernel
        # stream exists, run the REAL read-only verifier against it and
        # report those numbers truthfully; otherwise the target-side checks
        # are None with ``evaluated`` false — never hardcoded trues.
        if stream_exists:
            verification = verify_backfill(
                source,
                stream_id=stream_id,
                project_id=project_id,
                writer=writer,
                synthesized_events=synthesized_events,
            )
            return BackfillReport(
                project=project_slug,
                timeline_id=source.timeline_id,
                timeline_ulid=source.timeline_ulid,
                source=source.source_name,
                source_event_count=len(source.events),
                kernel_event_count=verification.kernel_event_count,
                source_head_version=source.head_version,
                kernel_head_seq=verification.kernel_head_seq,
                events_sha256=source.events_sha256,
                kinds=verification.kernel_kinds,
                checks=verification.checks_dict(),
                marker_path=marker_path,
                marker_written=False,
                written=False,
                replayed=False,
                dry_run=True,
                synthesized_bootstrap=synthesized_count > 0,
                evaluated=True,
                projected_config_sha256=sha256_hex(source.projected_config),
                projected_registry_sha256=sha256_hex(source.projected_registry),
                detail=(
                    f"dry-run: stream exists at head {head_seq}; "
                    "re-verified read-only, no writes performed"
                ),
                identity_sha256=source.identity_sha256,
                registry_sha256=source.registry_sha256 or "",
            )
        return BackfillReport(
            project=project_slug,
            timeline_id=source.timeline_id,
            timeline_ulid=source.timeline_ulid,
            source=source.source_name,
            source_event_count=len(source.events),
            kernel_event_count=0,
            source_head_version=source.head_version,
            kernel_head_seq=0,
            events_sha256=source.events_sha256,
            kinds={},
            checks={
                "count": None,
                "head": None,
                "content": None,
                "kinds": None,
                "projections": None,
            },
            marker_path=marker_path,
            marker_written=False,
            written=False,
            replayed=False,
            dry_run=True,
            synthesized_bootstrap=synthesized_count > 0,
            evaluated=False,
            projected_config_sha256=sha256_hex(source.projected_config),
            projected_registry_sha256=sha256_hex(source.projected_registry),
            detail="dry-run: no events, receipts, or markers written",
            identity_sha256=source.identity_sha256,
            registry_sha256=source.registry_sha256 or "",
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
        # Idempotency gate first: identical retry replays the stored result
        # (crash-after-commit convergence — W1.3). Before replay succeeds,
        # validate the sidecar digests against the receipt's persisted
        # values (G): a post-commit sidecar edit must fail closed with
        # BackfillDiscrepancyError and zero marker mutation, not silently
        # re-anchor the marker from drifted bytes.
        replayed = receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_digest,
            command_kind=BACKFILL_COMMAND_KIND,
        )
        if replayed is not None:
            # G: digest binding — compare receipt-persisted digests against
            # the freshly loaded source before replay converges.
            receipt_identity = str(replayed.get("identity_sha256", ""))
            receipt_registry = str(replayed.get("registry_sha256", ""))
            source_registry = source.registry_sha256 or ""
            drift_parts: list[str] = []
            if receipt_identity != source.identity_sha256:
                drift_parts.append(
                    f"identity_sha256 {receipt_identity} (receipt) != "
                    f"{source.identity_sha256} (current)"
                )
            if receipt_registry != source_registry:
                drift_parts.append(
                    f"registry_sha256 {receipt_registry} (receipt) != "
                    f"{source_registry} (current)"
                )
            if drift_parts:
                raise BackfillDiscrepancyError(
                    f"timeline {source.timeline_id} sidecar drifted since "
                    f"backfill (receipt vs current): "
                    + ", ".join(drift_parts)
                    + "; operator reruns fresh"
                )
            return _report_from_mapping(replayed, replayed=True)
        # No receipt: an existing kernel stream here is foreign state (the
        # backfill never committed it) — fail closed rather than append to
        # an unknown authority.
        stream_row = uow.query_one(
            "SELECT head_seq FROM event_streams WHERE id = ?", (stream_id,)
        )
        if stream_row is not None:
            raise BackfillAuthorityError(
                f"timeline {source.timeline_id} already has a kernel stream "
                f"at head {int(stream_row['head_seq'])} with no matching "
                "backfill receipt; refusing to append backfill events to "
                "non-empty state"
            )

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
        # 3. The expected events (synthesized bootstrap first, then every
        #    source event), 1:1, hash-chained.
        event_ids, first_seq, last_seq, resulting_seq = _append_timeline_events(
            uow,
            project_id=project_id,
            timeline_id=source.timeline_id,
            stream_id=stream_id,
            mapped_events=mapped_events,
            created_at=stamp,
            on_before_append=on_before_append,
        )
        # 4. W1: run the FULL verifier AGAINST THE TRANSACTION CONNECTION
        #    before commit — any mismatch raises here and the rollback
        #    leaves zero events/receipts/projections.
        verification = _verify_on(
            uow,
            source,
            stream_id=stream_id,
            project_id=project_id,
            synthesized_events=synthesized_events,
        )
        if not verification.ok:
            raise BackfillDiscrepancyError(
                "backfill verification failed: "
                + "; ".join(
                    (*verification.mismatches, *verification.projection_mismatches)
                )
            )
        # 5. The complete receipt (raw numbers; checks are re-verified
        #    read-only after commit, so replay never trusts stored checks).
        report = BackfillReport(
            project=project_slug,
            timeline_id=source.timeline_id,
            timeline_ulid=source.timeline_ulid,
            source=source.source_name,
            source_event_count=len(source.events),
            kernel_event_count=verification.kernel_event_count,
            source_head_version=source.head_version,
            kernel_head_seq=verification.kernel_head_seq,
            events_sha256=source.events_sha256,
            kinds=verification.kernel_kinds,
            checks=verification.checks_dict(),
            marker_path=marker_path,
            marker_written=False,
            written=False,
            replayed=False,
            dry_run=False,
            synthesized_bootstrap=synthesized_count > 0,
            evaluated=True,
            projected_config_sha256=sha256_hex(source.projected_config),
            projected_registry_sha256=sha256_hex(source.projected_registry),
            detail="imported",
            identity_sha256=source.identity_sha256,
            registry_sha256=source.registry_sha256 or "",
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
    # G: crash-after-commit replay that bypassed the in-UoW drift gate
    # (e.g. future path without receipt digests) still fails closed before
    # any marker mutation — compare the replayed report's persisted digests
    # against the freshly loaded source.
    if replayed:
        receipt_identity = report.identity_sha256
        receipt_registry = report.registry_sha256
        source_registry = source.registry_sha256 or ""
        drift_parts: list[str] = []
        if receipt_identity != source.identity_sha256:
            drift_parts.append(
                f"identity_sha256 {receipt_identity} (receipt) != "
                f"{source.identity_sha256} (current)"
            )
        if receipt_registry != source_registry:
            drift_parts.append(
                f"registry_sha256 {receipt_registry} (receipt) != "
                f"{source_registry} (current)"
            )
        if drift_parts:
            raise BackfillDiscrepancyError(
                f"timeline {source.timeline_id} sidecar drifted since "
                f"backfill (receipt vs current): "
                + ", ".join(drift_parts)
                + "; operator reruns fresh"
            )
    # Fresh import or identical retry: re-verify every invariant (a)-(g)
    # read-only (W1.3 full re-verify), then idempotently write/refresh the
    # marker (f). No new rows are written on replay.
    verification = verify_backfill(
        source,
        stream_id=stream_id,
        project_id=project_id,
        writer=writer,
        synthesized_events=synthesized_events,
    )
    if not verification.ok:
        raise BackfillDiscrepancyError(
            "backfill verification failed: "
            + "; ".join(
                (*verification.mismatches, *verification.projection_mismatches)
            )
        )
    marker_written = _write_marker(
        root,
        source,
        synthesized_bootstrap=synthesized_count > 0,
    )
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
        synthesized_bootstrap=base.synthesized_bootstrap,
        evaluated=True,
        projected_config_sha256=base.projected_config_sha256,
        projected_registry_sha256=base.projected_registry_sha256,
        detail=detail,
        identity_sha256=base.identity_sha256,
        registry_sha256=base.registry_sha256,
    )


def _write_marker(
    root: Path,
    source: BackfillSource,
    *,
    synthesized_bootstrap: bool = False,
) -> bool:
    """Idempotently write or refresh one timeline's authority marker.

    Returns whether a marker entry was written by THIS call (``True`` when
    the entry did not exist before). A matching existing entry is refreshed
    (same source identity, fresh ``backfilled_at``) rather than refused —
    crash-after-commit convergence (W1.3). The read-modify-write runs under
    ONE acquisition of the ``backfill-state.lock`` flock (W7a); the atomic
    replace is preserved.
    """
    with _state_lock(root):
        state = read_backfill_state(root)
        existing = state.get(source.timeline_id)
        entry = {
            "backfilled_at": utc_now_iso(),
            "source": source.source_name,
            "source_head_version": source.head_version,
            "events_sha256": source.events_sha256,
            "synthesized_bootstrap": synthesized_bootstrap,
            # Round-3 P2#1 (part 2): identity/registry sidecar file digests
            # ("" when no sidecar applies). Resume/re-import recomputes them
            # from the CURRENT sidecar bytes and fails closed with named
            # drift on mismatch (W2 machinery).
            "identity_sha256": source.identity_sha256,
            "registry_sha256": source.registry_sha256 or "",
        }
        state[source.timeline_id] = entry
        write_json_atomic(backfill_state_path(root), state)
        return existing is None


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
        synthesized_bootstrap=bool(value.get("synthesized_bootstrap", False)),
        evaluated=bool(value.get("evaluated", True)),
        projected_config_sha256=str(value.get("projected_config_sha256", "")),
        projected_registry_sha256=str(value.get("projected_registry_sha256", "")),
        detail=str(value.get("detail", "")),
        identity_sha256=str(value.get("identity_sha256", "")),
        registry_sha256=str(value.get("registry_sha256", "")),
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
    and a resumed run (same explicit ``run_ts``) revalidates the completed
    prefix instead of skipping it blindly (W2): the CURRENT source
    ``events_sha256`` + head are recomputed for every timeline — a marker
    disagreeing with either fails the resume closed with named drift (the
    operator reruns fresh), a matching marker is re-verified read-only, and
    a marker-missing timeline converges through W1.3 (idempotent
    marker completion). A timeline failure aborts the run (fail closed)
    with the checkpoint left at the last completed timeline. When
    ``run_ts`` is omitted the run gets an EXCLUSIVELY allocated id (epoch
    second + full-length ``uuid4().hex``; the run dir is created with
    fail-if-exists semantics and a bounded retry, round-3 P3#1) so two runs
    started in the same second can never share one checkpoint dir; pass the
    same explicit ``run_ts`` to resume a run (round-3 P3#2: the checkpoint
    JSON also carries the active ``run_ts`` so an interrupted fresh run is
    resumable through the SDK response / CLI ``--run-ts``).
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
        # Round-3 P3#1: a fresh run (no explicit run_ts) gets an EXCLUSIVELY
        # allocated id — the run checkpoint dir is created with
        # fail-if-exists semantics and a bounded retry on collision (fresh
        # full-length uuid4().hex each attempt; hard error after 5), so
        # uniqueness is a filesystem guarantee, not a probability. Shared
        # dirs would let a changed source of the SECOND run enter
        # resume-drift handling and report the wrong failure class. An
        # explicit run_ts (resume) is preserved verbatim so the resumed run
        # reuses its checkpoint dir. The legacy ``migration.py`` default is
        # intentionally untouched (zero impact on legacy callers).
        effective_run_ts = run_ts
        if effective_run_ts is None:
            effective_run_ts = _allocate_run_checkpoint_id(
                project_slug, root=root
            )
        checkpoint_file = checkpoint_path_for_run(
            project_slug, root=root, run_ts=effective_run_ts
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
            # interrupted run (checkpoint records it as completed). W2:
            # NEVER skip blindly — recompute the CURRENT source identity
            # (events_sha256 + head). A marker that disagrees with either is
            # named drift and fails the resume closed (the operator reruns
            # fresh); a matching marker is re-verified read-only; a missing
            # marker means the commit landed but the marker never did
            # (crash-after-commit) — the import below converges it through
            # W1.3 (receipt replay + idempotent marker completion).
            if _revalidate_resumed(
                writer=writer,
                projects=projects,
                receipts=receipts,
                project_slug=project_slug,
                source=source,
                root=root,
            ):
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
                    # Round-3 P3#2: the ACTIVE run id is persisted in the
                    # checkpoint JSON itself (writer+reader), so an
                    # interrupted fresh run is resumable through the
                    # operator surface, not only the dir name.
                    run_ts=effective_run_ts,
                ),
                checkpoint_file,
            )
    if skipped and not reports:
        raise BackfillSourceError(
            f"no event-sourced timelines found in project {project_slug!r}; "
            f"skipped {sorted(skipped.values())}"
        )
    return reports


def _revalidate_resumed(
    *,
    writer: DatabaseWriter,
    projects: ProjectRepository,
    receipts: ReceiptService,
    project_slug: str,
    source: BackfillSource,
    root: Path,
) -> bool:
    """W2 resume revalidation for one checkpoint-completed timeline.

    Recomputes the CURRENT source ``events_sha256`` + head + sidecar
    digests (``identity_sha256`` / ``registry_sha256``, round-3 P2#1 — all
    already carried by the freshly loaded *source*) and compares them with
    the recorded marker for the same timeline:

    - a marker whose source identity differs in EITHER value is named drift
      (``BackfillDiscrepancyError`` naming the timeline and both values —
      the operator reruns fresh); the resume fails closed before any write;
    - a matching marker is fully re-verified read-only (a failed
      re-verification also fails closed) and the timeline can be skipped;
    - no marker: the timeline committed but the marker never landed
      (crash-after-commit) — returns ``False`` so the caller imports it and
      W1.3 converges the marker idempotently.

    Returns ``True`` when the timeline was revalidated and can be skipped,
    ``False`` when no marker exists (the caller must converge via import).
    """
    state = read_backfill_state(root)
    existing = state.get(source.timeline_id)
    if existing is None:
        return False
    # W2 drift naming (round-3 P2#1 part 2): the identity/registry sidecar
    # digests are recomputed from the CURRENT source (freshly loaded above)
    # and compared with the marker — a sidecar edit fails the resume closed
    # with the named digest, exactly like event drift.
    drift_parts: list[str] = []
    if existing.get("events_sha256") != source.events_sha256:
        drift_parts.append(
            f"events_sha256 {existing.get('events_sha256')} (marker) != "
            f"{source.events_sha256} (current)"
        )
    if existing.get("source_head_version") != source.head_version:
        drift_parts.append(
            f"head {existing.get('source_head_version')} (marker) != "
            f"{source.head_version} (current)"
        )
    if existing.get("identity_sha256", "") != source.identity_sha256:
        drift_parts.append(
            f"identity_sha256 {existing.get('identity_sha256', '')} "
            f"(marker) != {source.identity_sha256} (current)"
        )
    if existing.get("registry_sha256", "") != (source.registry_sha256 or ""):
        drift_parts.append(
            f"registry_sha256 {existing.get('registry_sha256', '')} "
            f"(marker) != {source.registry_sha256 or ''} (current)"
        )
    if drift_parts:
        raise BackfillDiscrepancyError(
            f"timeline {source.timeline_id} source drifted since backfill: "
            + ", ".join(drift_parts)
            + "; operator reruns fresh"
        )
    synthesized_events, _mapped = _expected_stream(source)
    verification = verify_backfill(
        source,
        stream_id=_stream_id(source.timeline_id),
        project_id=projects.resolve(writer, project_slug),
        writer=writer,
        synthesized_events=synthesized_events,
    )
    if not verification.ok:
        raise BackfillDiscrepancyError(
            f"timeline {source.timeline_id} failed read-only re-verification "
            "on resume: "
            + "; ".join(
                (*verification.mismatches, *verification.projection_mismatches)
            )
        )
    return True


def _local_fs_run_sources(
    root: Path,
    project_slug: str,
    timeline_refs: Sequence[str] | None,
) -> list[tuple[BackfillSource, str]]:
    from astrid.core._shared.jsonio import read_json
    from astrid.core.timeline.migration import classify_timeline_dir
    import re as _re

    _ULID_RE = _re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$", _re.IGNORECASE)

    def is_ulid(value: object) -> bool:
        return isinstance(value, str) and bool(_ULID_RE.fullmatch(value))

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
    """Load every selected timeline from one version-ordered export file.

    Fail-closed scanner (W5): an empty export is rejected, and every
    malformed row (non-object, missing ``timeline_id``, non-positive or
    gapped version) rejects the WHOLE export naming its index — no silent
    skips anywhere in the scanner.
    """
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
    if not parsed:
        raise BackfillSourceError(
            f"supabase export contains no rows: {export.name}"
        )
    timeline_ids: set[str] = set()
    for index, raw in enumerate(parsed):
        if not isinstance(raw, dict):
            raise BackfillSourceError(
                f"supabase export item {index} is not a JSON object"
            )
        tid = raw.get("timeline_id")
        if not isinstance(tid, str) or not tid:
            raise BackfillSourceError(
                f"supabase export item {index} has no timeline_id"
            )
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
    "BACKFILL_STATE_LOCK_FILENAME",
    "BackfillAuthorityError",
    "BackfillDiscrepancyError",
    "BackfillError",
    "BackfillReport",
    "BackfillSource",
    "BackfillSourceError",
    "BackfillVerification",
    "MappedEvent",
    "SupabaseExportReader",
    "allocate_run_checkpoint_id",
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
