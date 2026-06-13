"""Canonical run-directory record definitions for the A3b session-succession engine.

File-ownership contract
------------------------

This module **defines and documents** which file owns which piece of
run-directory state.  The contract is non-negotiable: every piece of
driver, compiler, or CLI code that reads or writes these files MUST go
through the helpers defined here (or through the existing event/lease
modules for ``events.jsonl`` / ``lease.json`` — those are intentionally
not re-wrapped).

============================  ===============================================  =====================================================
File                          Owns                                             Notes
============================  ===============================================  =====================================================
``arnold_run.json``           identity, mode, status, current segment          **Canonical run record.**  This is the single source
                              (``current_segment``), workflow marker           of truth for what kind of run this is and where it
                                                                               currently sits in the session lifecycle.

``events.jsonl``              hash-chained event ledger                        Owned by ``astrid.core.task.events``.  The session
                                                                               engine appends through the established locked-append
                                                                               path and never bypasses it.

``state.json``                accumulated key-value state across segments      Written atomically.  Successor segments read the
                                                                               accumulated state from here; no artifact bytes are
                                                                               inlined.

``session-manifest.json``     rebuildable segment projection                   **Not a second ledger.**  This file is a convenience
                                                                               projection of the segments that have been frozen and
                                                                               launched.  It can be rebuilt from ``events.jsonl``
                                                                               at any time.  It carries segment records with refs
                                                                               (plan hashes, cursor refs, state/artifact refs),
                                                                               never artifact bytes.
``lease.json``                writer epoch and attached session                Owned by ``astrid.core.session.lease``.
============================  ===============================================  =====================================================

Run-mode contract
-----------------

Every ``arnold_run.json`` record carries an optional ``mode`` field:

* **Absent / ``null``** — the run is a **static** Arnold workflow.  The
  existing A3a host path (static shape allowlist, one-shot pipeline) is used.
  The field ``current_segment`` is meaningless in this mode.

* **``"session-succession"``** — the run is driven by the A3b
  session-succession engine.  The ``workflow_id`` in the run record is the
  reserved marker ``"session-succession"`` (see below) and is **never**
  routed through the static shape allowlist.  The field ``current_segment``
  tracks the active segment id.

The default (absent-mode) is always ``"static"``.  This preserves backward
compatibility with every ``arnold_run.json`` written before A3b existed.

Reserved workflow marker
-------------------------

``workflow_id = "session-succession"`` is reserved as a **metadata-only**
marker for session runs.  It is NOT registered in the static shape
allowlist (``SHAPE_DEFINITIONS`` / ``ShapeRegistry``) and MUST bypass the
allowlist check in ``_resolve_active_workflow_id()``.  The session engine
compiles pipelines on-the-fly from ``TaskPlan`` / plan-mutation deltas;
there is no pre-authored shape graph for this workflow id.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .manifest import (
    SESSION_MANIFEST_FILENAME,
    EventLineageHashes,
    SegmentRecord as _ManifestSegmentRecord,
    SessionManifest,
    load_manifest_file,
    write_manifest_file,
)
from .state import STATE_REF as STATE_FILENAME
from .state import ArtifactRef, StateRef, load_state_file, write_state_file

# ── reserved workflow marker ───────────────────────────────────────────
SESSION_SUCCESSION_WORKFLOW_ID: str = "session-succession"
"""Reserved metadata-only workflow id for session-succession runs.

This value MUST NOT appear in ``SHAPE_DEFINITIONS`` or the static
``ShapeRegistry`` allowlist.  When a run record carries this workflow id
its ``mode`` MUST be ``"session-succession"`` and routing MUST bypass
``_resolve_active_workflow_id()``.
"""

# ── well-known filenames (NOT redefining EVENTS_FILENAME / LEASE_FILENAME) ──
ARNOLD_RUN_FILENAME: str = "arnold_run.json"
# ═══════════════════════════════════════════════════════════════════════
#  Canonical record types
# ═══════════════════════════════════════════════════════════════════════

RunMode = Literal["static", "session-succession"]
"""Valid run modes.

``"static"``       — classic A3a static Arnold workflow (allowlisted shape).
``"session-succession"`` — A3b session-succession engine.
"""

RunStatus = Literal[
    "prepared",
    "running",
    "suspended",
    "completed",
    "aborted",
]
"""Valid run statuses.

``"prepared"``   — run directory created, pipeline built, not yet advanced.
``"running"``    — at least one segment is actively executing.
``"suspended"``  — waiting for human input at a suspension stage.
``"completed"``  — terminal stage reached.
``"aborted"``    — user- or system-initiated abort.

Note: these are the values stored in ``arnold_run.json.status``, NOT the
segment-level status tracked inside ``session-manifest.json``.
"""


@dataclass
class ArnoldRunRecord:
    """Canonical representation of ``arnold_run.json``.

    This is the **authoritative** record for run identity, mode, status,
    and current-segment tracking.  Every read of ``arnold_run.json``
    SHOULD go through :func:`load_arnold_run_record` rather than
    ``json.load()``-ing the file directly, because that function applies
    the absent-mode → ``"static"`` default and validates required fields.
    """

    engine: str
    """Always ``"arnold"`` for Arnold-hosted runs."""

    workflow_id: str
    """The workflow marker.

    For static runs this is an allowlisted shape id (e.g. ``"we.refine_image"``).
    For session-succession runs this is ``"session-succession"`` (the reserved
    marker).
    """

    mode: RunMode
    """Run mode.  Defaults to ``"static"`` when absent from the on-disk record."""

    run_id: str
    """Unique run identifier (UUID or user-supplied)."""

    status: RunStatus
    """High-level run status."""

    current_segment: str | None = None
    """Active segment id (meaningful only when ``mode == "session-succession"``).

    ``None`` in static mode or before the first segment is launched.
    """

    argv: list[str] = field(default_factory=list)
    """CLI argv that started this run (includes the ``"start"`` verb)."""

    created_at: str = ""
    """ISO-8601 creation timestamp."""

    inputs: dict[str, str] = field(default_factory=dict)
    """Key-value inputs supplied at start time (``--input key=value``)."""

    state: dict[str, Any] = field(default_factory=dict)
    """Snapshot of the initial state at start time.

    Note: the *live* accumulated state is stored in ``state.json``, not
    here.  This field reflects the state that was passed to the pipeline
    builder.
    """

    plan_hash: str = ""
    """Content-hash of the run plan at creation time."""

    # ── passthrough / future keys are preserved in _extra ──────────────
    _extra: dict[str, Any] = field(default_factory=dict, repr=False)
    """Preserve any unrecognised fields so round-trips are lossless."""


SegmentManifestEntry = _ManifestSegmentRecord


# ═══════════════════════════════════════════════════════════════════════
#  Load / write helpers
# ═══════════════════════════════════════════════════════════════════════


def resolve_mode(raw_mode: Any) -> RunMode:
    """Resolve a raw ``mode`` value to a concrete :data:`RunMode`.

    * ``None``, missing, or the empty string → ``"static"``.
    * ``"session-succession"`` → ``"session-succession"``.
    * ``"static"`` → ``"static"``.
    * Anything else raises :class:`ValueError`.
    """
    if raw_mode is None or raw_mode == "":
        return "static"
    if raw_mode in ("static", "session-succession"):
        return raw_mode  # type: ignore[return-value]
    raise ValueError(
        f"invalid run mode {raw_mode!r}; expected 'static' or 'session-succession'"
    )


def load_arnold_run_record(run_root: Path) -> ArnoldRunRecord:
    """Load and validate ``arnold_run.json`` from *run_root*.

    Applies the absent-mode → ``"static"`` default, validates required
    fields, and returns a fully-populated :class:`ArnoldRunRecord`.

    Raises :class:`FileNotFoundError` if the file does not exist.
    Raises :class:`json.JSONDecodeError` if the file is not valid JSON.
    Raises :class:`RuntimeError` if the payload is not a JSON object or
        required fields are missing / malformed.
    """
    record_path = run_root / ARNOLD_RUN_FILENAME
    try:
        payload = json.loads(record_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"invalid JSON in {ARNOLD_RUN_FILENAME} for run {run_root.name!r}: {exc.msg}"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            f"{ARNOLD_RUN_FILENAME} for run {run_root.name!r} is not a JSON object"
        )

    engine = payload.get("engine")
    if not isinstance(engine, str) or not engine:
        raise RuntimeError(
            f"missing or invalid 'engine' field in {ARNOLD_RUN_FILENAME} "
            f"for run {run_root.name!r}"
        )

    workflow_id = payload.get("workflow_id")
    if not isinstance(workflow_id, str) or not workflow_id:
        raise RuntimeError(
            f"missing or invalid 'workflow_id' field in {ARNOLD_RUN_FILENAME} "
            f"for run {run_root.name!r}"
        )

    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise RuntimeError(
            f"missing or invalid 'run_id' field in {ARNOLD_RUN_FILENAME} "
            f"for run {run_root.name!r}"
        )

    raw_mode = payload.get("mode")
    mode = resolve_mode(raw_mode)

    # cross-validate: session-succession mode requires the reserved workflow id
    if mode == "session-succession" and workflow_id != SESSION_SUCCESSION_WORKFLOW_ID:
        raise RuntimeError(
            f"run {run_root.name!r} has mode='session-succession' but "
            f"workflow_id={workflow_id!r} instead of the reserved "
            f"{SESSION_SUCCESSION_WORKFLOW_ID!r}"
        )

    # cross-validate: reserved workflow id requires session-succession mode
    if workflow_id == SESSION_SUCCESSION_WORKFLOW_ID and mode != "session-succession":
        raise RuntimeError(
            f"run {run_root.name!r} has workflow_id={SESSION_SUCCESSION_WORKFLOW_ID!r} "
            f"but mode={mode!r}; expected mode='session-succession'"
        )

    status = payload.get("status", "prepared")
    if status not in ("prepared", "running", "suspended", "completed", "aborted"):
        status = "prepared"  # defensive: tolerate unknown status values

    current_segment = payload.get("current_segment")
    if current_segment is not None and not isinstance(current_segment, str):
        current_segment = None

    # Collect known fields and preserve extras
    known_keys = {
        "engine",
        "workflow_id",
        "mode",
        "run_id",
        "status",
        "current_segment",
        "argv",
        "created_at",
        "inputs",
        "state",
        "plan_hash",
    }
    extra = {k: v for k, v in payload.items() if k not in known_keys}

    return ArnoldRunRecord(
        engine=engine,
        workflow_id=workflow_id,
        mode=mode,
        run_id=run_id,
        status=status,  # type: ignore[arg-type]
        current_segment=current_segment,
        argv=list(payload.get("argv", [])),
        created_at=str(payload.get("created_at", "")),
        inputs=dict(payload.get("inputs", {}) or {}),
        state=dict(payload.get("state", {}) or {}),
        plan_hash=str(payload.get("plan_hash", "")),
        _extra=extra,
    )


def load_state(run_root: Path) -> dict[str, Any]:
    """Load accumulated state from ``state.json``.

    Returns an empty dict if the file does not (yet) exist.
    """
    return load_state_file(run_root)


def write_state(run_root: Path, state: dict[str, Any]) -> None:
    """Atomically write accumulated state to ``state.json``."""
    write_state_file(run_root, state)


def load_session_manifest(run_root: Path) -> SessionManifest:
    """Load the session manifest from ``session-manifest.json``.

    Returns an empty :class:`SessionManifest` if the file does not (yet)
    exist (the manifest is rebuildable).
    """
    return load_manifest_file(run_root)


def write_session_manifest(
    run_root: Path,
    manifest: SessionManifest,
) -> None:
    """Atomically write the session manifest to ``session-manifest.json``."""
    write_manifest_file(run_root, manifest)


def is_session_run(run_root: Path) -> bool:
    """Return ``True`` if *run_root* contains a session-succession run.

    This is a cheap check that reads only ``arnold_run.json.mode``.
    """
    try:
        record = load_arnold_run_record(run_root)
    except (FileNotFoundError, RuntimeError, json.JSONDecodeError):
        return False
    return record.mode == "session-succession"


# ═══════════════════════════════════════════════════════════════════════
#  Public API surface
# ═══════════════════════════════════════════════════════════════════════

__all__ = [
    # ── reserved marker ──
    "SESSION_SUCCESSION_WORKFLOW_ID",
    # ── well-known filenames ──
    "ARNOLD_RUN_FILENAME",
    "STATE_FILENAME",
    "SESSION_MANIFEST_FILENAME",
    "ArtifactRef",
    # ── types ──
    "RunMode",
    "RunStatus",
    "ArnoldRunRecord",
    "EventLineageHashes",
    "SegmentManifestEntry",
    "SessionManifest",
    "StateRef",
    # ── load / write ──
    "load_arnold_run_record",
    "load_state",
    "write_state",
    "load_session_manifest",
    "write_session_manifest",
    "is_session_run",
    "resolve_mode",
]
