"""Tests for A3b session-succession records, manifest, state, events, and event-ledger interaction.

Coverage:
  * Ownership defaults (absent mode → static, cross-validation rules, is_session_run)
  * Manifest round-trip (write → read → all fields preserved)
  * Ref-only artifact/state entries (no inline bytes allowed)
  * Projection hash stability (deterministic same-data, different-data changes)
  * verify_chain() preservation when a segment_boundary event is appended
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from astrid.core.integrations.arnold.session.events import (
    SEGMENT_BOUNDARY_KIND,
    make_segment_boundary_event,
)
from astrid.core.integrations.arnold.session.manifest import (
    SESSION_MANIFEST_FILENAME,
    EventLineageHashes,
    SegmentRecord,
    SessionManifest,
    load_manifest_file,
    write_manifest_file,
)
from astrid.core.integrations.arnold.session.records import (
    SESSION_SUCCESSION_WORKFLOW_ID,
    is_session_run,
    load_arnold_run_record,
    resolve_mode,
)
from astrid.core.integrations.arnold.session.state import (
    ArtifactRef,
    StateRef,
    load_state_file,
    write_state_file,
)
from astrid.core.task.events import (
    EVENTS_FILENAME,
    LEASE_FILENAME,
    read_events,
    verify_chain,
)
from tests.conftest import seed_event

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_run_root(tmp_path: Path) -> Path:
    """Create a fresh run directory."""
    run_dir = tmp_path / "runs" / f"run-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_arnold_run_json(run_dir: Path, payload: dict) -> Path:
    """Write arnold_run.json and return the path."""
    path = run_dir / "arnold_run.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_lease_json(run_dir: Path, writer_epoch: int = 0) -> Path:
    """Write a minimal lease.json for event seeding."""
    path = run_dir / LEASE_FILENAME
    path.write_text(
        json.dumps({"writer_epoch": writer_epoch, "attached_session_id": "sess-test"}),
        encoding="utf-8",
    )
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# Ownership defaults
# ═══════════════════════════════════════════════════════════════════════════════

class TestOwnershipDefaults:
    """arnold_run.json mode defaults and cross-validation."""

    def test_absent_mode_defaults_to_static(self) -> None:
        """Absent / None / '' mode all resolve to 'static'."""
        assert resolve_mode(None) == "static"
        assert resolve_mode("") == "static"

    def test_explicit_static_mode(self) -> None:
        """Explicit 'static' mode resolves correctly."""
        assert resolve_mode("static") == "static"

    def test_session_succession_mode(self) -> None:
        """Explicit 'session-succession' mode resolves correctly."""
        assert resolve_mode("session-succession") == "session-succession"

    def test_invalid_mode_raises(self) -> None:
        """Invalid modes raise ValueError."""
        with pytest.raises(ValueError, match="invalid run mode"):
            resolve_mode("bogus")

    def test_load_minimal_arnold_run_static_default(self, tmp_path: Path) -> None:
        """A minimal arnold_run.json without mode → static."""
        run_dir = _make_run_root(tmp_path)
        _write_arnold_run_json(
            run_dir,
            {
                "engine": "arnold",
                "workflow_id": "builtin.agent_probe",
                "run_id": "run-abc",
            },
        )
        record = load_arnold_run_record(run_dir)
        assert record.mode == "static"
        assert record.engine == "arnold"
        assert record.workflow_id == "builtin.agent_probe"
        assert record.run_id == "run-abc"

    def test_load_session_succession_record(self, tmp_path: Path) -> None:
        """A session-succession record loads correctly."""
        run_dir = _make_run_root(tmp_path)
        _write_arnold_run_json(
            run_dir,
            {
                "engine": "arnold",
                "workflow_id": SESSION_SUCCESSION_WORKFLOW_ID,
                "run_id": "run-ss-1",
                "mode": "session-succession",
                "status": "running",
                "current_segment": "seg-01",
            },
        )
        record = load_arnold_run_record(run_dir)
        assert record.mode == "session-succession"
        assert record.workflow_id == SESSION_SUCCESSION_WORKFLOW_ID
        assert record.current_segment == "seg-01"
        assert record.status == "running"

    def test_session_succession_mode_requires_reserved_workflow_id(
        self, tmp_path: Path
    ) -> None:
        """mode='session-succession' with non-reserved workflow_id → RuntimeError."""
        run_dir = _make_run_root(tmp_path)
        _write_arnold_run_json(
            run_dir,
            {
                "engine": "arnold",
                "workflow_id": "some.other.shape",
                "run_id": "run-bad",
                "mode": "session-succession",
            },
        )
        with pytest.raises(RuntimeError, match="mode='session-succession'"):
            load_arnold_run_record(run_dir)

    def test_reserved_workflow_id_requires_session_succession_mode(
        self, tmp_path: Path
    ) -> None:
        """workflow_id='session-succession' with static mode → RuntimeError."""
        run_dir = _make_run_root(tmp_path)
        _write_arnold_run_json(
            run_dir,
            {
                "engine": "arnold",
                "workflow_id": SESSION_SUCCESSION_WORKFLOW_ID,
                "run_id": "run-bad-2",
                "mode": "static",
            },
        )
        with pytest.raises(RuntimeError, match="workflow_id='session-succession'"):
            load_arnold_run_record(run_dir)

    def test_is_session_run_true(self, tmp_path: Path) -> None:
        """is_session_run returns True for session-succession runs."""
        run_dir = _make_run_root(tmp_path)
        _write_arnold_run_json(
            run_dir,
            {
                "engine": "arnold",
                "workflow_id": SESSION_SUCCESSION_WORKFLOW_ID,
                "run_id": "run-ss",
                "mode": "session-succession",
            },
        )
        assert is_session_run(run_dir) is True

    def test_is_session_run_false_for_static(self, tmp_path: Path) -> None:
        """is_session_run returns False for static runs."""
        run_dir = _make_run_root(tmp_path)
        _write_arnold_run_json(
            run_dir,
            {
                "engine": "arnold",
                "workflow_id": "builtin.agent_probe",
                "run_id": "run-static",
            },
        )
        assert is_session_run(run_dir) is False

    def test_is_session_run_false_when_no_file(self, tmp_path: Path) -> None:
        """is_session_run returns False when arnold_run.json doesn't exist."""
        run_dir = _make_run_root(tmp_path)
        assert is_session_run(run_dir) is False

    def test_arnold_run_round_trip_preserves_extra_fields(self, tmp_path: Path) -> None:
        """Extra fields in arnold_run.json are preserved in _extra."""
        run_dir = _make_run_root(tmp_path)
        _write_arnold_run_json(
            run_dir,
            {
                "engine": "arnold",
                "workflow_id": "builtin.agent_probe",
                "run_id": "run-extra",
                "custom_field": 42,
                "nested": {"a": 1},
            },
        )
        record = load_arnold_run_record(run_dir)
        assert record._extra == {"custom_field": 42, "nested": {"a": 1}}


# ═══════════════════════════════════════════════════════════════════════════════
# Manifest round-trip
# ═══════════════════════════════════════════════════════════════════════════════

class TestManifestRoundTrip:
    """session-manifest.json write → read → verify all fields preserved."""

    def test_empty_manifest_round_trip(self, tmp_path: Path) -> None:
        """Empty manifest writes and reads back correctly."""
        run_dir = _make_run_root(tmp_path)
        manifest = SessionManifest(run_id="run-1", artifact_root=".")
        write_manifest_file(run_dir, manifest)
        loaded = load_manifest_file(run_dir)
        assert loaded.run_id == "run-1"
        assert loaded.artifact_root == "."
        assert loaded.segments == ()
        assert loaded.current_segment_id is None

    def test_manifest_with_segments_round_trip(self, tmp_path: Path) -> None:
        """Manifest with two segment records round-trips all fields."""
        run_dir = _make_run_root(tmp_path)
        state = {"key_a": "val_a", "key_b": 42}
        state_ref = StateRef.from_state(state)

        seg1 = SegmentRecord(
            segment_id="seg-01",
            plan_hash="sha256:aaa",
            state=state_ref,
            parent_segment_id=None,
            status="completed",
            pipeline_ref="pipeline.json",
            pipeline_hash="sha256:bbb",
            cursor_ref="cursor-01.json",
            artifacts=(
                ArtifactRef(path="out/1.png", sha256="sha256:ccc", label="output"),
            ),
            event_lineage=EventLineageHashes(
                segment_start_hash="sha256:start1",
                segment_boundary_hash="sha256:boundary1",
            ),
            frozen_at="2026-01-01T00:00:00Z",
            launched_at="2026-01-01T00:01:00Z",
        )
        seg2_state = {"key_a": "val_a_updated", "key_c": "new"}
        seg2_state_ref = StateRef.from_state(seg2_state)
        seg2 = SegmentRecord(
            segment_id="seg-02",
            plan_hash="sha256:ddd",
            state=seg2_state_ref,
            parent_segment_id="seg-01",
            status="running",
        )

        manifest = SessionManifest(
            run_id="run-2",
            artifact_root="artifacts",
            current_segment_id="seg-02",
            segments=(seg1, seg2),
        )
        # Compute and set projection hash
        manifest = SessionManifest(
            run_id=manifest.run_id,
            artifact_root=manifest.artifact_root,
            current_segment_id=manifest.current_segment_id,
            segments=manifest.segments,
            projection_hash=manifest.compute_projection_hash(),
        )

        write_manifest_file(run_dir, manifest)
        loaded = load_manifest_file(run_dir)

        assert loaded.run_id == "run-2"
        assert loaded.artifact_root == "artifacts"
        assert loaded.current_segment_id == "seg-02"
        assert len(loaded.segments) == 2

        # seg-01
        s1 = loaded.segments[0]
        assert s1.segment_id == "seg-01"
        assert s1.plan_hash == "sha256:aaa"
        assert s1.state.state_ref == "state.json"
        assert s1.state.state_hash == state_ref.state_hash
        assert s1.state.state_keys == ("key_a", "key_b")
        assert s1.parent_segment_id is None
        assert s1.status == "completed"
        assert s1.pipeline_hash == "sha256:bbb"
        assert s1.cursor_ref == "cursor-01.json"
        assert len(s1.artifacts) == 1
        assert s1.artifacts[0].path == "out/1.png"
        assert s1.artifacts[0].sha256 == "sha256:ccc"
        assert s1.artifacts[0].label == "output"
        assert s1.event_lineage.segment_start_hash == "sha256:start1"
        assert s1.event_lineage.segment_boundary_hash == "sha256:boundary1"
        assert s1.frozen_at == "2026-01-01T00:00:00Z"
        assert s1.launched_at == "2026-01-01T00:01:00Z"

        # seg-02
        s2 = loaded.segments[1]
        assert s2.segment_id == "seg-02"
        assert s2.plan_hash == "sha256:ddd"
        assert s2.parent_segment_id == "seg-01"
        assert s2.status == "running"
        assert s2.state.state_hash == seg2_state_ref.state_hash

    def test_manifest_load_file_not_found_returns_empty(self, tmp_path: Path) -> None:
        """load_manifest_file returns empty SessionManifest when file missing."""
        run_dir = _make_run_root(tmp_path)
        manifest = load_manifest_file(run_dir)
        assert manifest.run_id == ""
        assert manifest.segments == ()

    def test_manifest_projection_hash_mismatch_raises(self, tmp_path: Path) -> None:
        """A manifest with wrong projection_hash raises RuntimeError on load."""
        run_dir = _make_run_root(tmp_path)
        manifest = SessionManifest(run_id="run-3", artifact_root=".")
        payload = manifest.to_dict()
        payload["projection_hash"] = "sha256:badbad"  # deliberately wrong
        (run_dir / SESSION_MANIFEST_FILENAME).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        with pytest.raises(RuntimeError, match="projection_hash mismatch"):
            load_manifest_file(run_dir)


# ═══════════════════════════════════════════════════════════════════════════════
# Ref-only artifact / state entries (no inline bytes)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRefOnlyEntries:
    """ArtifactRef and StateRef enforce ref-only (no inline bytes)."""

    def test_artifact_ref_from_dict_rejects_inline_bytes(self) -> None:
        """ArtifactRef.from_dict raises when inline payload keys present."""
        for key in ("artifact_bytes", "bytes", "content", "data"):
            with pytest.raises(RuntimeError, match="ref-only"):
                ArtifactRef.from_dict({"path": f"out/{key}.png", key: "some bytes"})

    def test_artifact_ref_from_dict_accepts_valid_ref(self) -> None:
        """ArtifactRef.from_dict succeeds with valid ref fields."""
        ref = ArtifactRef.from_dict(
            {
                "path": "out/result.png",
                "sha256": "sha256:abc123",
                "label": "final_output",
                "source_step_path": ["step_a", "step_b"],
            }
        )
        assert ref.path == "out/result.png"
        assert ref.sha256 == "sha256:abc123"
        assert ref.label == "final_output"
        assert ref.source_step_path == ("step_a", "step_b")

    def test_artifact_ref_to_dict_no_inline_keys(self) -> None:
        """ArtifactRef.to_dict never emits inline payload keys."""
        ref = ArtifactRef(path="out/x.png", sha256="sha256:fff")
        d = ref.to_dict()
        assert "artifact_bytes" not in d
        assert "bytes" not in d
        assert "content" not in d
        assert "data" not in d
        assert d == {"path": "out/x.png", "sha256": "sha256:fff"}

    def test_artifact_ref_minimal(self) -> None:
        """ArtifactRef with only path (no optional fields)."""
        ref = ArtifactRef.from_dict({"path": "out/minimal.png"})
        assert ref.path == "out/minimal.png"
        assert ref.sha256 is None
        assert ref.label is None
        assert ref.source_step_path == ()
        d = ref.to_dict()
        assert d == {"path": "out/minimal.png"}

    def test_state_ref_from_dict_requires_canonical_state_ref(self) -> None:
        """StateRef.from_dict enforces state_ref='state.json'."""
        with pytest.raises(RuntimeError, match="state_ref must be 'state.json'"):
            StateRef.from_dict({"state_ref": "other_state.json", "state_hash": "sha256:abc"})

    def test_state_ref_from_state_produces_deterministic_hash(self) -> None:
        """StateRef.from_state produces same hash for same dict content."""
        state = {"a": 1, "b": 2}
        ref1 = StateRef.from_state(state)
        ref2 = StateRef.from_state({"b": 2, "a": 1})  # different order
        assert ref1.state_hash == ref2.state_hash
        assert ref1.state_keys == ("a", "b")

    def test_state_ref_from_state_different_keys_produce_different_hash(self) -> None:
        """Different state data produces different hash."""
        ref1 = StateRef.from_state({"a": 1})
        ref2 = StateRef.from_state({"a": 2})
        assert ref1.state_hash != ref2.state_hash

    def test_state_file_write_and_read_round_trip(self, tmp_path: Path) -> None:
        """Write state.json via write_state_file, read back via load_state_file."""
        run_dir = _make_run_root(tmp_path)
        original = {"counter": 5, "notes": "hello"}
        write_state_file(run_dir, original)
        loaded = load_state_file(run_dir)
        assert loaded == original

    def test_state_file_not_found_returns_empty_dict(self, tmp_path: Path) -> None:
        """load_state_file returns {} when state.json missing."""
        run_dir = _make_run_root(tmp_path)
        assert load_state_file(run_dir) == {}


# ═══════════════════════════════════════════════════════════════════════════════
# Projection hash stability
# ═══════════════════════════════════════════════════════════════════════════════

class TestProjectionHashStability:
    """SessionManifest projection_hash is deterministic and data-sensitive."""

    def test_same_data_produces_same_hash(self) -> None:
        """Two manifests with identical data produce the same projection_hash."""
        state_ref = StateRef.from_state({"x": 1})
        seg = SegmentRecord(
            segment_id="seg-01",
            plan_hash="sha256:plan",
            state=state_ref,
        )
        m1 = SessionManifest(run_id="r1", segments=(seg,))
        m2 = SessionManifest(run_id="r1", segments=(seg,))
        assert m1.compute_projection_hash() == m2.compute_projection_hash()

    def test_different_data_produces_different_hash(self) -> None:
        """Different manifest data produces different projection_hash."""
        state_ref = StateRef.from_state({"x": 1})
        seg_a = SegmentRecord(segment_id="seg-01", plan_hash="sha256:plan", state=state_ref)
        seg_b = SegmentRecord(segment_id="seg-02", plan_hash="sha256:plan", state=state_ref)
        m_a = SessionManifest(run_id="r1", segments=(seg_a,))
        m_b = SessionManifest(run_id="r1", segments=(seg_b,))
        assert m_a.compute_projection_hash() != m_b.compute_projection_hash()

    def test_hash_uses_prefixed_format(self) -> None:
        """Projection hash starts with 'sha256:'."""
        m = SessionManifest(run_id="r1")
        h = m.compute_projection_hash()
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 64  # 64 hex chars

    def test_write_read_preserves_projection_hash(self, tmp_path: Path) -> None:
        """After writing and reading, the projection_hash matches."""
        run_dir = _make_run_root(tmp_path)
        state_ref = StateRef.from_state({"val": 1})
        seg = SegmentRecord(segment_id="s1", plan_hash="sha256:pp", state=state_ref)
        manifest = SessionManifest(
            run_id="r-hash",
            segments=(seg,),
            projection_hash=None,
        )
        computed = manifest.compute_projection_hash()
        manifest = SessionManifest(
            run_id=manifest.run_id,
            artifact_root=manifest.artifact_root,
            current_segment_id=manifest.current_segment_id,
            segments=manifest.segments,
            projection_hash=computed,
        )
        write_manifest_file(run_dir, manifest)
        loaded = load_manifest_file(run_dir)
        assert loaded.projection_hash == computed

    def test_empty_manifest_hash_is_deterministic(self) -> None:
        """Empty manifests produce a deterministic hash."""
        m1 = SessionManifest(run_id="")
        m2 = SessionManifest(run_id="")
        assert m1.compute_projection_hash() == m2.compute_projection_hash()


# ═══════════════════════════════════════════════════════════════════════════════
# segment_boundary event + verify_chain() preservation
# ═══════════════════════════════════════════════════════════════════════════════

class TestSegmentBoundaryEventVerifyChain:
    """Append segment_boundary event via seed_event; verify_chain() stays valid."""

    def _seed_run_started(self, events_path: Path) -> dict:
        """Seed a run_started event (a common anchor event)."""
        event = {
            "kind": "run_started",
            "run_id": "verify-test-run",
            "ts": "2026-01-01T00:00:00Z",
        }
        return seed_event(events_path, event)

    def test_verify_chain_empty_file_returns_true(self, tmp_path: Path) -> None:
        """verify_chain on a non-existent file returns True."""
        run_dir = _make_run_root(tmp_path)
        ok, _, _ = verify_chain(run_dir / EVENTS_FILENAME)
        assert ok is True

    def test_verify_chain_after_seed_and_segment_boundary(self, tmp_path: Path) -> None:
        """After seeding run_started + segment_boundary, verify_chain passes."""
        run_dir = _make_run_root(tmp_path)
        _write_lease_json(run_dir)
        events_path = run_dir / EVENTS_FILENAME

        # Seed a run_started event
        self._seed_run_started(events_path)

        # Build a segment_boundary event
        boundary = make_segment_boundary_event(
            from_segment_id="seg-01",
            to_segment_id="seg-02",
            previous_plan_hash="sha256:prev",
            next_plan_hash="sha256:next",
            cursor_ref="cursor-01.json",
            manifest_hash="sha256:man",
            state_hash="sha256:st",
            reason="plan_mutated",
        )
        assert boundary["kind"] == SEGMENT_BOUNDARY_KIND
        assert boundary["from_segment_id"] == "seg-01"
        assert boundary["to_segment_id"] == "seg-02"
        assert boundary["state_ref"] == "state.json"

        # Append via seed_event (locked append path)
        stored = seed_event(events_path, boundary)
        assert "hash" in stored
        assert stored["hash"].startswith("sha256:")

        # verify_chain must pass
        ok, last_idx, err = verify_chain(events_path)
        assert ok is True, f"verify_chain failed: {err} at line {last_idx}"
        assert last_idx == 1  # 0-indexed, two events

    def test_verify_chain_preserves_chain_across_multiple_boundaries(
        self, tmp_path: Path
    ) -> None:
        """Multiple events including two segment_boundary events still verify."""
        run_dir = _make_run_root(tmp_path)
        _write_lease_json(run_dir)
        events_path = run_dir / EVENTS_FILENAME

        # Seed a run_started
        self._seed_run_started(events_path)

        # First boundary
        b1 = make_segment_boundary_event(
            from_segment_id="seg-01",
            to_segment_id="seg-02",
            previous_plan_hash="sha256:p1",
            next_plan_hash="sha256:p2",
            cursor_ref="c1.json",
            manifest_hash="sha256:m1",
            state_hash="sha256:s1",
            reason="plan_mutated",
        )
        seed_event(events_path, b1)

        # Second boundary
        b2 = make_segment_boundary_event(
            from_segment_id="seg-02",
            to_segment_id="seg-03",
            previous_plan_hash="sha256:p2",
            next_plan_hash="sha256:p3",
            cursor_ref="c2.json",
            manifest_hash="sha256:m2",
            state_hash="sha256:s2",
            reason="human_resume",
        )
        seed_event(events_path, b2)

        ok, last_idx, err = verify_chain(events_path)
        assert ok is True, f"verify_chain failed: {err} at line {last_idx}"
        assert last_idx == 2  # 0-indexed, three events

        # All events readable
        events = read_events(events_path)
        assert len(events) == 3
        kinds = [e["kind"] for e in events]
        assert kinds == ["run_started", SEGMENT_BOUNDARY_KIND, SEGMENT_BOUNDARY_KIND]

    def test_segment_boundary_event_has_required_fields(self) -> None:
        """make_segment_boundary_event returns all required fields."""
        boundary = make_segment_boundary_event(
            from_segment_id="seg-01",
            to_segment_id="seg-02",
            previous_plan_hash="sha256:prev",
            next_plan_hash="sha256:next",
            cursor_ref="cursor.json",
            manifest_hash="sha256:man",
            state_hash="sha256:st",
        )
        required = {
            "kind", "ts", "reason", "from_segment_id", "to_segment_id",
            "previous_plan_hash", "next_plan_hash", "cursor_ref",
            "manifest_hash", "state_ref", "state_hash",
        }
        assert required.issubset(set(boundary.keys()))

    def test_segment_boundary_event_does_not_modify_ledger_directly(
        self, tmp_path: Path
    ) -> None:
        """make_segment_boundary_event is pure: it doesn't touch the event file."""
        run_dir = _make_run_root(tmp_path)
        _write_lease_json(run_dir)
        events_path = run_dir / EVENTS_FILENAME

        # Seed one event
        self._seed_run_started(events_path)
        before = read_events(events_path)

        # Call make_segment_boundary_event (no append)
        boundary = make_segment_boundary_event(
            from_segment_id="s1",
            to_segment_id="s2",
            previous_plan_hash="sha256:p",
            next_plan_hash="sha256:n",
            cursor_ref="c.json",
            manifest_hash="sha256:m",
            state_hash="sha256:s",
        )
        assert isinstance(boundary, dict)

        # Events file must be unchanged
        after = read_events(events_path)
        assert len(after) == len(before)
        assert after == before

    def test_verify_chain_rejects_tampered_event(self, tmp_path: Path) -> None:
        """verify_chain detects tampered event hash."""
        run_dir = _make_run_root(tmp_path)
        _write_lease_json(run_dir)
        events_path = run_dir / EVENTS_FILENAME

        self._seed_run_started(events_path)
        boundary = make_segment_boundary_event(
            from_segment_id="s1",
            to_segment_id="s2",
            previous_plan_hash="sha256:p",
            next_plan_hash="sha256:n",
            cursor_ref="c.json",
            manifest_hash="sha256:m",
            state_hash="sha256:s",
        )
        seed_event(events_path, boundary)

        # Tamper with the boundary event hash
        lines = events_path.read_text(encoding="utf-8").splitlines(keepends=True)
        # Parse second line, replace hash
        event = json.loads(lines[1])
        event["hash"] = "sha256:" + "f" * 64  # wrong hash
        lines[1] = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        events_path.write_text("".join(lines), encoding="utf-8")

        ok, line_idx, err = verify_chain(events_path)
        assert ok is False
        assert "hash mismatch" in (err or "").lower()
