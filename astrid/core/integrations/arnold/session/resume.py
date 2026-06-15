"""Resume intent classification for the Arnold session-succession engine.

This module answers one question: when a session run is resumed (the
Arnold runtime delivers ``ctx.inputs['human_input']`` to a suspended
manual stage), does the resume payload represent a **pure data resume**
(stay in the current segment) or a **plan mutation** (requires a new
segment boundary)?

Pure data resumes are forwarded to the existing A3a
``parse_human_resume_payload()`` unchanged.  Plan-mutation resumes are
handled by the session driver, which compiles a new segment from the
mutated plan and advances the cursor.

Classification logic (in priority order)
-----------------------------------------

1. **Static runs are always pure data resumes.**  The session-succession
   engine is never active for static runs; the existing A3a path handles
   resumes without mutation awareness.

2. **Explicit ``human_input.plan_mutation`` key** — when the human payload
   carries a ``"plan_mutation"`` dict, the intent is ``PLAN_MUTATED``
   regardless of the ledger.

3. **Ledger scan for ``plan_mutated``** — if a ``segment_boundary`` event
   with ``reason == "plan_mutated"`` appears in ``events.jsonl`` after the
   current segment's start event, the intent is ``PLAN_MUTATED`` (the
   ledger already recorded a mutation that has not yet been compiled).

4. **Effective plan hash mismatch** — when the caller supplies an
   *effective plan hash* (usually the hash of the current ``TaskPlan``
   loaded from the project) and it differs from the current segment's
   ``plan_hash`` recorded in ``session-manifest.json``, the intent is
   ``PLAN_MUTATED``.

5. **Otherwise** the intent is ``PURE_DATA``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from astrid.core.events import EVENTS_FILENAME, read_events

from .events import SEGMENT_BOUNDARY_KIND
from .records import is_session_run, load_session_manifest


class ResumeIntentKind(Enum):
    """Outcome of resume intent classification."""

    PURE_DATA = "pure_data"
    """The resume is a pure data injection (human decision / state patch).
    
    The session driver forwards the human payload to the existing A3a
    ``parse_human_resume_payload()`` without creating a new segment.
    """

    PLAN_MUTATED = "plan_mutated"
    """The resume carries or implies a plan mutation.
    
    The session driver MUST create a new segment boundary, compile a fresh
    pipeline from the mutated plan, freeze it, and launch the successor.
    """


@dataclass(frozen=True)
class ResumeIntent:
    """Classified resume intent with supporting evidence."""

    kind: ResumeIntentKind
    """Whether this is a pure data resume or a plan mutation."""

    reason: str
    """Human-readable explanation of the classification decision."""

    effective_plan_hash: str | None = None
    """The plan hash that should be used for the current/resuming segment.
    
    When ``kind == PLAN_MUTATED`` this is the **new** plan hash to compile.
    When ``kind == PURE_DATA`` this is the unchanged plan hash (or None if
    the caller did not supply one).
    """

    previous_plan_hash: str | None = None
    """The plan hash of the segment **before** the mutation.
    
    Only meaningful when ``kind == PLAN_MUTATED``; otherwise None.
    """

    mutation_source: str | None = None
    """What triggered the mutation classification.

    One of:
    - ``"human_input"`` — ``human_input.plan_mutation`` key was present.
    - ``"ledger"`` — a ``segment_boundary`` event with reason
      ``"plan_mutated"`` was found in the event ledger after the current
      segment start.
    - ``"hash_mismatch"`` — the effective plan hash differs from the
      current segment's recorded ``plan_hash``.
    - ``None`` — no mutation was detected (``PURE_DATA``).
    """


def _scan_ledger_for_plan_mutation(
    events: list[dict[str, Any]],
    *,
    segment_start_hash: str | None,
) -> bool:
    """Return True if any ``segment_boundary`` event with reason
    ``"plan_mutated"`` appears after the segment start event."""

    # If we know the segment start hash, skip events until we pass it.
    # The segment start event itself is the boundary; we want events *after* it.
    past_start = segment_start_hash is None  # if no start hash, scan from beginning

    for event in events:
        event_hash = event.get("hash")
        if not past_start:
            if event_hash == segment_start_hash:
                past_start = True
            continue  # still before or at the start event; keep looking

        # We are now after the segment start event.
        if event.get("kind") == SEGMENT_BOUNDARY_KIND and event.get("reason") == "plan_mutated":
            return True

    return False


def classify_resume_intent(
    run_root: Path,
    *,
    human_input: dict[str, Any] | None = None,
    effective_plan_hash: str | None = None,
) -> ResumeIntent:
    """Classify the resume intent for a session run.

    Parameters
    ----------
    run_root:
        Path to the run directory (must contain ``arnold_run.json``,
        ``session-manifest.json``, and ``events.jsonl``).
    human_input:
        The raw human resume payload as delivered by the Arnold runtime
        via ``ctx.inputs['human_input']``.  May be ``None`` when the
        caller is probing the ledger before receiving actual input.
    effective_plan_hash:
        The content-hash of the current ``TaskPlan`` loaded from the
        project.  When supplied, the classifier compares it against the
        current segment's recorded ``plan_hash``.

    Returns
    -------
    ResumeIntent
        The classified intent with supporting evidence.

    Notes
    -----
    Static runs (``arnold_run.json.mode != "session-succession"``) always
    return ``PURE_DATA``.  The existing A3a ``parse_human_resume_payload()``
    path is left untouched.
    """

    # ── static runs: always pure data ──────────────────────────────────
    if not is_session_run(run_root):
        return ResumeIntent(
            kind=ResumeIntentKind.PURE_DATA,
            reason="static run — session-succession engine not active",
            effective_plan_hash=effective_plan_hash,
        )

    # ── load manifest for current segment context ──────────────────────
    manifest = load_session_manifest(run_root)
    current_segment_id = manifest.current_segment_id

    # Find the current segment record
    current_segment = None
    for seg in manifest.segments:
        if seg.segment_id == current_segment_id:
            current_segment = seg
            break

    # ── check 1: explicit plan_mutation in human input ─────────────────
    if isinstance(human_input, dict) and "plan_mutation" in human_input:
        plan_mutation = human_input["plan_mutation"]
        new_plan_hash = (
            str(plan_mutation.get("plan_hash", ""))
            if isinstance(plan_mutation, dict)
            else ""
        )
        return ResumeIntent(
            kind=ResumeIntentKind.PLAN_MUTATED,
            reason="human input carries explicit plan_mutation marker",
            effective_plan_hash=new_plan_hash or effective_plan_hash,
            previous_plan_hash=current_segment.plan_hash if current_segment else None,
            mutation_source="human_input",
        )

    # ── check 2: ledger scan for plan_mutated events ───────────────────
    try:
        events = read_events(run_root / EVENTS_FILENAME)
    except Exception:
        events = []

    segment_start_hash = (
        current_segment.event_lineage.segment_start_hash
        if current_segment is not None
        else None
    )

    if _scan_ledger_for_plan_mutation(
        events,
        segment_start_hash=segment_start_hash,
    ):
        return ResumeIntent(
            kind=ResumeIntentKind.PLAN_MUTATED,
            reason="plan_mutated segment_boundary event found in ledger after current segment start",
            effective_plan_hash=effective_plan_hash,
            previous_plan_hash=current_segment.plan_hash if current_segment else None,
            mutation_source="ledger",
        )

    # ── check 3: effective plan hash mismatch ──────────────────────────
    if (
        effective_plan_hash is not None
        and current_segment is not None
        and current_segment.plan_hash
        and effective_plan_hash != current_segment.plan_hash
    ):
        return ResumeIntent(
            kind=ResumeIntentKind.PLAN_MUTATED,
            reason=(
                f"effective plan hash {effective_plan_hash!r} differs from "
                f"current segment plan hash {current_segment.plan_hash!r}"
            ),
            effective_plan_hash=effective_plan_hash,
            previous_plan_hash=current_segment.plan_hash,
            mutation_source="hash_mismatch",
        )

    # ── default: pure data resume ──────────────────────────────────────
    return ResumeIntent(
        kind=ResumeIntentKind.PURE_DATA,
        reason="no plan mutation detected — pure data resume",
        effective_plan_hash=effective_plan_hash,
    )


__all__ = [
    "ResumeIntent",
    "ResumeIntentKind",
    "classify_resume_intent",
]
