"""Tests for resume intent classification in the A3b session-succession engine.

Coverage:
  * Static runs always return PURE_DATA
  * Explicit plan_mutation in human_input triggers PLAN_MUTATED
  * Ledger scan finds plan_mutated segment_boundary events after segment start
  * Effective plan hash mismatch triggers PLAN_MUTATED
  * Pure data resume (no mutation signals) returns PURE_DATA
  * ResumeIntent fields are correctly populated for each path
  * Existing A3a parse_human_resume_payload() is not imported or called
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from astrid.core.integrations.arnold.session.resume import (
    ResumeIntent,
    ResumeIntentKind,
    classify_resume_intent,
)
from astrid.core.integrations.arnold.session.records import (
    SESSION_SUCCESSION_WORKFLOW_ID,
    ARNOLD_RUN_FILENAME,
)
from astrid.core.integrations.arnold.session.manifest import (
    SESSION_MANIFEST_FILENAME,
    SessionManifest,
    SegmentRecord,
    write_manifest_file,
)
from astrid.core.integrations.arnold.session.state import StateRef, prefixed_hash
from astrid.core.task.events import EVENTS_FILENAME, ZERO_HASH


# ── helpers ────────────────────────────────────────────────────────────


def _write_arnold_run_json(
    run_root: Path,
    *,
    mode: str = "session-succession",
    workflow_id: str = SESSION_SUCCESSION_WORKFLOW_ID,
    run_id: str | None = None,
) -> str:
    """Write a minimal arnold_run.json for a session run. Returns the run_id."""
    rid = run_id or uuid.uuid4().hex
    record = {
        "engine": "arnold",
        "workflow_id": workflow_id,
        "mode": mode,
        "run_id": rid,
        "status": "suspended",
        "current_segment": "seg-1",
    }
    (run_root / ARNOLD_RUN_FILENAME).write_text(json.dumps(record))
    return rid


def _write_session_manifest(
    run_root: Path,
    *,
    segment_id: str = "seg-1",
    plan_hash: str = "sha256:aaaa",
    segment_start_hash: str | None = None,
) -> None:
    """Write a session-manifest.json with a single segment record."""
    state = StateRef.from_state({"key": "val"})
    segment = SegmentRecord(
        segment_id=segment_id,
        plan_hash=plan_hash,
        state=state,
    )
    if segment_start_hash:
        from astrid.core.integrations.arnold.session.manifest import (
            EventLineageHashes,
        )

        segment = SegmentRecord(
            segment_id=segment_id,
            plan_hash=plan_hash,
            state=state,
            event_lineage=EventLineageHashes(
                segment_start_hash=segment_start_hash,
            ),
        )
    manifest = SessionManifest(
        run_id=uuid.uuid4().hex,
        current_segment_id=segment_id,
        segments=(segment,),
    )
    write_manifest_file(run_root, manifest)


def _append_event(
    events_path: Path,
    event: dict,
    *,
    prev_hash: str = ZERO_HASH,
) -> str:
    """Append an event with a computed hash. Returns the event hash."""
    from astrid.core.task.events import canonical_event_json
    import hashlib

    event_without_hash = {k: v for k, v in event.items() if k != "hash"}
    event_hash = (
        "sha256:"
        + hashlib.sha256(
            canonical_event_json(event_without_hash).encode("utf-8")
        ).hexdigest()
    )
    full_event = {**event_without_hash, "hash": event_hash, "prev_hash": prev_hash}
    with events_path.open("a") as fh:
        fh.write(json.dumps(full_event, sort_keys=True) + "\n")
    return event_hash


def _make_segment_start_event(segment_id: str) -> dict:
    """Build a synthetic segment-start event."""
    return {
        "kind": "segment_start",
        "segment_id": segment_id,
        "ts": "2025-01-01T00:00:00Z",
    }


def _make_plan_mutated_event(
    from_segment_id: str,
    to_segment_id: str,
    previous_plan_hash: str,
    next_plan_hash: str,
) -> dict:
    """Build a plan_mutated segment_boundary event."""
    return {
        "kind": "segment_boundary",
        "reason": "plan_mutated",
        "from_segment_id": from_segment_id,
        "to_segment_id": to_segment_id,
        "previous_plan_hash": previous_plan_hash,
        "next_plan_hash": next_plan_hash,
        "cursor_ref": "cursor.json",
        "manifest_hash": "sha256:bbbb",
        "state_hash": "sha256:cccc",
        "state_ref": "state.json",
        "ts": "2025-01-01T01:00:00Z",
    }


# ── tests ──────────────────────────────────────────────────────────────


class TestStaticRunAlwaysPureData:
    """Static runs never enter the session-succession engine."""

    def test_static_mode_returns_pure_data(self, tmp_path: Path):
        run_root = tmp_path / "static_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root, mode="static", workflow_id="we.refine_image")

        intent = classify_resume_intent(run_root)

        assert intent.kind == ResumeIntentKind.PURE_DATA
        assert "static" in intent.reason.lower()
        assert intent.mutation_source is None

    def test_static_mode_with_human_input_returns_pure_data(self, tmp_path: Path):
        """Even if human input carries plan_mutation, static runs ignore it."""
        run_root = tmp_path / "static_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root, mode="static", workflow_id="we.refine_image")

        human_input = {"decision": {"action": "approve"}, "plan_mutation": {"plan_hash": "sha256:ffff"}}

        intent = classify_resume_intent(run_root, human_input=human_input)

        assert intent.kind == ResumeIntentKind.PURE_DATA
        assert "static" in intent.reason.lower()

    def test_static_mode_with_plan_hash_mismatch_returns_pure_data(self, tmp_path: Path):
        """Even if plan hash changed, static runs are pure data."""
        run_root = tmp_path / "static_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root, mode="static", workflow_id="we.refine_image")

        intent = classify_resume_intent(
            run_root, effective_plan_hash="sha256:different"
        )

        assert intent.kind == ResumeIntentKind.PURE_DATA


class TestExplicitPlanMutationInHumanInput:
    """When human_input carries plan_mutation, intent is PLAN_MUTATED."""

    def test_plan_mutation_key_triggers_mutation(self, tmp_path: Path):
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        human_input = {
            "decision": {"action": "approve"},
            "plan_mutation": {"plan_hash": "sha256:bbbb"},
        }

        intent = classify_resume_intent(run_root, human_input=human_input)

        assert intent.kind == ResumeIntentKind.PLAN_MUTATED
        assert intent.mutation_source == "human_input"
        assert "plan_mutation" in intent.reason.lower()
        assert intent.effective_plan_hash == "sha256:bbbb"
        assert intent.previous_plan_hash == "sha256:aaaa"

    def test_plan_mutation_key_without_plan_hash_uses_effective(self, tmp_path: Path):
        """If plan_mutation dict has no plan_hash, falls back to effective_plan_hash."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        human_input = {
            "decision": {"action": "approve"},
            "plan_mutation": {},
        }

        intent = classify_resume_intent(
            run_root,
            human_input=human_input,
            effective_plan_hash="sha256:override",
        )

        assert intent.kind == ResumeIntentKind.PLAN_MUTATED
        assert intent.mutation_source == "human_input"
        assert intent.effective_plan_hash == "sha256:override"


class TestLedgerScanForPlanMutated:
    """Plan mutation is detected from the event ledger."""

    def test_plan_mutated_event_after_segment_start(self, tmp_path: Path):
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        events_path = run_root / EVENTS_FILENAME

        # Seed event
        seed_hash = _append_event(
            events_path,
            {"kind": "system", "event": "seed"},
        )

        # Segment start
        start_hash = _append_event(
            events_path,
            _make_segment_start_event("seg-1"),
            prev_hash=seed_hash,
        )

        # Plan mutated boundary (after segment start)
        _append_event(
            events_path,
            _make_plan_mutated_event("seg-1", "seg-2", "sha256:aaaa", "sha256:bbbb"),
            prev_hash=start_hash,
        )

        _write_session_manifest(
            run_root,
            segment_id="seg-1",
            plan_hash="sha256:aaaa",
            segment_start_hash=start_hash,
        )

        intent = classify_resume_intent(run_root)

        assert intent.kind == ResumeIntentKind.PLAN_MUTATED
        assert intent.mutation_source == "ledger"
        assert "ledger" in intent.reason.lower()
        assert intent.previous_plan_hash == "sha256:aaaa"

    def test_no_plan_mutated_event_after_segment_start(self, tmp_path: Path):
        """When no plan_mutated event exists, ledger scan finds nothing."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        events_path = run_root / EVENTS_FILENAME

        seed_hash = _append_event(events_path, {"kind": "system", "event": "seed"})
        start_hash = _append_event(
            events_path,
            _make_segment_start_event("seg-1"),
            prev_hash=seed_hash,
        )

        # Append a non-mutation event after start
        _append_event(
            events_path,
            {"kind": "segment_boundary", "reason": "checkpoint", "ts": "2025-01-01T01:00:00Z"},
            prev_hash=start_hash,
        )

        _write_session_manifest(
            run_root,
            segment_id="seg-1",
            plan_hash="sha256:aaaa",
            segment_start_hash=start_hash,
        )

        intent = classify_resume_intent(run_root)

        assert intent.kind == ResumeIntentKind.PURE_DATA

    def test_plan_mutated_event_before_segment_start_is_ignored(self, tmp_path: Path):
        """A plan_mutated event before the current segment start does not affect classification."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        events_path = run_root / EVENTS_FILENAME

        seed_hash = _append_event(events_path, {"kind": "system", "event": "seed"})

        # Plan mutated from a previous segment transition (before seg-1 starts)
        _append_event(
            events_path,
            _make_plan_mutated_event("seg-0", "seg-1", "sha256:0000", "sha256:aaaa"),
            prev_hash=seed_hash,
        )

        # Segment start for seg-1
        start_hash = _append_event(
            events_path,
            _make_segment_start_event("seg-1"),
            prev_hash=seed_hash,  # Note: this test doesn't chain properly but
            # we just care about hash identity for scanning
        )

        _write_session_manifest(
            run_root,
            segment_id="seg-1",
            plan_hash="sha256:aaaa",
            segment_start_hash=start_hash,
        )

        # The plan_mutated event has a different hash than start_hash, and appears
        # before the start event in the list. Our scanner should skip events before
        # the start hash.
        # However, since our scanner uses hash identity (not ordering), and the
        # start_hash is the third event, the plan_mutated event (second) will be
        # before it and thus skipped.
        intent = classify_resume_intent(run_root)

        # The plan_mutated event is before the segment start, so it should be
        # skipped by the scanner.
        assert intent.kind == ResumeIntentKind.PURE_DATA

    def test_empty_events_file(self, tmp_path: Path):
        """No events.jsonl at all is handled gracefully."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        intent = classify_resume_intent(run_root)

        assert intent.kind == ResumeIntentKind.PURE_DATA

    def test_no_segment_start_hash_scans_from_beginning(self, tmp_path: Path):
        """When segment_start_hash is None, scan from the beginning of the ledger."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        events_path = run_root / EVENTS_FILENAME

        _append_event(events_path, {"kind": "system", "event": "seed"})
        _append_event(
            events_path,
            _make_plan_mutated_event("seg-0", "seg-1", "sha256:0000", "sha256:aaaa"),
        )

        # segment_start_hash is None
        _write_session_manifest(
            run_root,
            segment_id="seg-1",
            plan_hash="sha256:aaaa",
            segment_start_hash=None,
        )

        intent = classify_resume_intent(run_root)

        # Since segment_start_hash is None, we scan from the beginning
        # and find the plan_mutated event
        assert intent.kind == ResumeIntentKind.PLAN_MUTATED
        assert intent.mutation_source == "ledger"


class TestEffectivePlanHashMismatch:
    """Hash mismatch between the current segment and the effective plan."""

    def test_hash_mismatch_triggers_plan_mutated(self, tmp_path: Path):
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        intent = classify_resume_intent(
            run_root, effective_plan_hash="sha256:bbbb"
        )

        assert intent.kind == ResumeIntentKind.PLAN_MUTATED
        assert intent.mutation_source == "hash_mismatch"
        assert "differs" in intent.reason.lower()
        assert intent.effective_plan_hash == "sha256:bbbb"
        assert intent.previous_plan_hash == "sha256:aaaa"

    def test_hash_match_does_not_trigger(self, tmp_path: Path):
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        intent = classify_resume_intent(
            run_root, effective_plan_hash="sha256:aaaa"
        )

        assert intent.kind == ResumeIntentKind.PURE_DATA

    def test_no_effective_hash_no_mismatch(self, tmp_path: Path):
        """When no effective_plan_hash is supplied, hash mismatch is skipped."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        intent = classify_resume_intent(run_root)

        assert intent.kind == ResumeIntentKind.PURE_DATA

    def test_hash_mismatch_with_human_input_but_no_plan_mutation(self, tmp_path: Path):
        """Hash mismatch takes priority as a mutation signal, but the
        human_input check is evaluated first (explicit plan_mutation wins)."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        # Human input without plan_mutation key, but hash differs
        human_input = {"decision": {"action": "approve"}, "notes": "looks good"}

        intent = classify_resume_intent(
            run_root,
            human_input=human_input,
            effective_plan_hash="sha256:bbbb",
        )

        # plan_mutation key not present, so human_input check passes through.
        # Then ledger scan finds nothing, but hash mismatch fires.
        assert intent.kind == ResumeIntentKind.PLAN_MUTATED
        assert intent.mutation_source == "hash_mismatch"


class TestResumeIntentDataclass:
    """ResumeIntent fields are correctly populated for each path."""

    def test_pure_data_intent_fields(self):
        intent = ResumeIntent(
            kind=ResumeIntentKind.PURE_DATA,
            reason="test",
            effective_plan_hash="sha256:aaaa",
        )
        assert intent.kind == ResumeIntentKind.PURE_DATA
        assert intent.reason == "test"
        assert intent.effective_plan_hash == "sha256:aaaa"
        assert intent.previous_plan_hash is None
        assert intent.mutation_source is None

    def test_plan_mutated_intent_fields(self):
        intent = ResumeIntent(
            kind=ResumeIntentKind.PLAN_MUTATED,
            reason="plan changed",
            effective_plan_hash="sha256:bbbb",
            previous_plan_hash="sha256:aaaa",
            mutation_source="human_input",
        )
        assert intent.kind == ResumeIntentKind.PLAN_MUTATED
        assert intent.effective_plan_hash == "sha256:bbbb"
        assert intent.previous_plan_hash == "sha256:aaaa"
        assert intent.mutation_source == "human_input"

    def test_resume_intent_is_frozen(self):
        intent = ResumeIntent(
            kind=ResumeIntentKind.PURE_DATA,
            reason="test",
        )
        with pytest.raises(Exception):
            intent.kind = ResumeIntentKind.PLAN_MUTATED  # type: ignore[misc]


class TestNoA3aParseHumanResumePayloadImport:
    """The resume module must not import or call the A3a parse_human_resume_payload."""

    def test_resume_module_does_not_import_a3a_parser(self):
        """Verify that the resume module's namespace does not contain
        parse_human_resume_payload."""
        import astrid.core.integrations.arnold.session.resume as resume_mod

        assert not hasattr(resume_mod, "parse_human_resume_payload")
        assert "parse_human_resume_payload" not in dir(resume_mod)


class TestPureHumanDataResumeStaysInSegment:
    """Pure human data resumes (decision payloads without plan mutation signals)
    return PURE_DATA, meaning no segment_boundary should be created."""

    def test_human_input_decision_no_mutation_signals(self, tmp_path: Path):
        """Session run with a decision payload, clean ledger, matching hash
        -> PURE_DATA.  This is the canonical 'stay in-segment' path."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        # A realistic human decision payload — no plan_mutation key
        human_input = {
            "decision": {"action": "approve", "notes": "looks good"},
            "produces_reverify": {"artifacts": [], "inputs": {}},
        }

        intent = classify_resume_intent(
            run_root,
            human_input=human_input,
            effective_plan_hash="sha256:aaaa",
        )

        assert intent.kind == ResumeIntentKind.PURE_DATA
        assert intent.reason == "no plan mutation detected — pure data resume"
        assert intent.mutation_source is None
        assert intent.effective_plan_hash == "sha256:aaaa"

    def test_human_input_decision_no_mutation_signals_no_hash(self, tmp_path: Path):
        """Session run with decision payload, no effective_plan_hash supplied
        -> still PURE_DATA (hash mismatch skipped when None)."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        human_input = {
            "decision": {"action": "reject", "notes": "needs work"},
        }

        intent = classify_resume_intent(run_root, human_input=human_input)

        assert intent.kind == ResumeIntentKind.PURE_DATA
        assert intent.mutation_source is None

    def test_human_input_none_session_mode(self, tmp_path: Path):
        """human_input=None in session mode with clean ledger and matching hash
        -> PURE_DATA."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        intent = classify_resume_intent(
            run_root,
            human_input=None,
            effective_plan_hash="sha256:aaaa",
        )

        assert intent.kind == ResumeIntentKind.PURE_DATA
        assert intent.mutation_source is None

    def test_empty_human_input_dict(self, tmp_path: Path):
        """Empty human_input dict {} is not a plan mutation."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        intent = classify_resume_intent(
            run_root,
            human_input={},
            effective_plan_hash="sha256:aaaa",
        )

        assert intent.kind == ResumeIntentKind.PURE_DATA
        assert intent.mutation_source is None


class TestResumeClassificationPriority:
    """When multiple mutation signals exist, human_input.plan_mutation wins."""

    def test_human_input_plan_mutation_wins_over_ledger(self, tmp_path: Path):
        """Even when the ledger has plan_mutated AND hash mismatches,
        explicit human_input.plan_mutation takes priority."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)

        events_path = run_root / EVENTS_FILENAME
        seed_hash = _append_event(events_path, {"kind": "system", "event": "seed"})
        start_hash = _append_event(
            events_path,
            _make_segment_start_event("seg-1"),
            prev_hash=seed_hash,
        )
        _append_event(
            events_path,
            _make_plan_mutated_event("seg-1", "seg-2", "sha256:aaaa", "sha256:bbbb"),
            prev_hash=start_hash,
        )

        _write_session_manifest(
            run_root,
            segment_id="seg-1",
            plan_hash="sha256:aaaa",
            segment_start_hash=start_hash,
        )

        human_input = {
            "decision": {"action": "approve"},
            "plan_mutation": {"plan_hash": "sha256:cccc"},
        }

        intent = classify_resume_intent(
            run_root,
            human_input=human_input,
            effective_plan_hash="sha256:zzzz",  # also different
        )

        # human_input.plan_mutation wins over ledger and hash mismatch
        assert intent.kind == ResumeIntentKind.PLAN_MUTATED
        assert intent.mutation_source == "human_input"
        assert intent.effective_plan_hash == "sha256:cccc"
        assert intent.previous_plan_hash == "sha256:aaaa"

    def test_ledger_wins_when_no_human_input_plan_mutation(self, tmp_path: Path):
        """When human_input has no plan_mutation, ledger plan_mutated is detected."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)

        events_path = run_root / EVENTS_FILENAME
        seed_hash = _append_event(events_path, {"kind": "system", "event": "seed"})
        start_hash = _append_event(
            events_path,
            _make_segment_start_event("seg-1"),
            prev_hash=seed_hash,
        )
        _append_event(
            events_path,
            _make_plan_mutated_event("seg-1", "seg-2", "sha256:aaaa", "sha256:bbbb"),
            prev_hash=start_hash,
        )

        _write_session_manifest(
            run_root,
            segment_id="seg-1",
            plan_hash="sha256:aaaa",
            segment_start_hash=start_hash,
        )

        human_input = {"decision": {"action": "approve"}}  # no plan_mutation

        intent = classify_resume_intent(
            run_root,
            human_input=human_input,
            effective_plan_hash="sha256:aaaa",  # hash matches
        )

        # Ledger plan_mutated is found; hash match doesn't matter
        assert intent.kind == ResumeIntentKind.PLAN_MUTATED
        assert intent.mutation_source == "ledger"


class TestPlanMutationEdgeCases:
    """Non-dict plan_mutation values and other edge cases."""

    def test_plan_mutation_string_value(self, tmp_path: Path):
        """plan_mutation key with a string value (not a dict) still triggers
        PLAN_MUTATED, with empty effective_plan_hash."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        human_input = {
            "decision": {"action": "approve"},
            "plan_mutation": "just a string, not a dict",
        }

        intent = classify_resume_intent(run_root, human_input=human_input)

        assert intent.kind == ResumeIntentKind.PLAN_MUTATED
        assert intent.mutation_source == "human_input"
        # Non-dict plan_mutation with no effective_plan_hash supplied
        # -> new_plan_hash is "" which is falsy, so or-fallback yields None
        assert intent.effective_plan_hash is None

    def test_plan_mutation_none_value(self, tmp_path: Path):
        """plan_mutation key with None value still triggers PLAN_MUTATED
        (the key presence is the signal)."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        human_input = {
            "decision": {"action": "approve"},
            "plan_mutation": None,
        }

        intent = classify_resume_intent(run_root, human_input=human_input)

        assert intent.kind == ResumeIntentKind.PLAN_MUTATED
        assert intent.mutation_source == "human_input"

    def test_plan_mutation_int_value(self, tmp_path: Path):
        """plan_mutation key with an int value still triggers PLAN_MUTATED."""
        run_root = tmp_path / "session_run"
        run_root.mkdir()
        _write_arnold_run_json(run_root)
        _write_session_manifest(run_root, plan_hash="sha256:aaaa")

        human_input = {
            "decision": {"action": "approve"},
            "plan_mutation": 42,
        }

        intent = classify_resume_intent(run_root, human_input=human_input)

        assert intent.kind == ResumeIntentKind.PLAN_MUTATED
        assert intent.mutation_source == "human_input"
