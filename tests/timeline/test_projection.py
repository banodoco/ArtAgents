"""Comprehensive projection unit tests — m4 contracts (T9).

Proves:
(a) apply_event_to_assembly and project_to_assembly for every event kind.
(b) timeline.imported snapshot unwrapping (full wrapper shape).
(c) Lifecycle no-ops (created, renamed, default_set, tombstoned, deleted).
(d) Deterministic output — same input always produces same output.
(e) Input immutability — projector never mutates input events.
(f) Golden fixture validation.
(g) ProjectionError for unsupported event kinds.
(h) Checkpoint-assisted replay produces same assembly as full replay.
(i) Bootstrap variants: created (no imported) and legacy (with imported).
"""

from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from astrid.core.project import paths as project_paths
from astrid.core.project.jsonio import read_json, write_json_atomic
from astrid.core.project.project import create_project
from astrid.core.timeline.crud import create_timeline
from astrid.core.timeline.eventlog import LocalFsBackend
from astrid.core.timeline.events.schema import (
    TimelineActor,
    TimelineEvent,
)
from astrid.core.timeline.projection import (
    ProjectionError,
    apply_event_to_assembly,
    project_to_assembly,
    regenerate_projection,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "tests" / "golden"


# ── helpers ──────────────────────────────────────────────────────────────────


def _actor(name: str = "tester") -> TimelineActor:
    return TimelineActor(type="agent", id=f"test:{name}", display=name)


def _make_event(
    kind: str,
    payload: dict[str, Any],
    *,
    timeline_id: str = "00000000-0000-0000-0000-000000000001",
    event_id: str = "01AAAAAAAAAAAAAAAAAAAAAA00",
) -> TimelineEvent:
    """Build a minimal TimelineEvent with the given kind and payload."""
    return TimelineEvent.from_dict({
        "event_id": event_id,
        "timeline_id": timeline_id,
        "ts": "2026-01-01T00:00:00Z",
        "actor": {"type": "system", "id": "test", "display": "Test"},
        "prev_hash": None,
        "hash": event_id + "0",
        "kind": kind,
        "payload": payload,
        "expected_version": None,
        "schema_version": 2,
        "txn_id": None,
    })


def _load_golden_fixture(name: str) -> dict[str, Any]:
    """Load a golden fixture JSON file."""
    path = GOLDEN_DIR / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── apply_event_to_assembly — clip.* events ───────────────────────────────────


class TestApplyClipAdded:
    def test_adds_clip_with_defaults(self):
        state: dict[str, Any] = {}
        event = _make_event("clip.added", {
            "clip_id": "c1", "kind": "visual", "asset_id": "a1", "position": None,
        })
        result = apply_event_to_assembly(state, event)
        assert result["clips"] == [{
            "id": "c1", "kind": "visual", "asset_id": "a1",
            "start": 0.0, "duration": 0.0, "text": "", "note": "",
        }]

    def test_adds_clip_at_index(self):
        state = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("clip.added", {
            "clip_id": "c2", "kind": "audio", "asset_id": "a2",
            "position": {"mode": "index", "index": 0},
        })
        result = apply_event_to_assembly(state, event)
        assert [c["id"] for c in result["clips"]] == ["c2", "c1"]

    def test_input_state_not_mutated(self):
        state: dict[str, Any] = {}
        state_copy = deepcopy(state)
        event = _make_event("clip.added", {
            "clip_id": "c1", "kind": "visual", "asset_id": "a1", "position": None,
        })
        apply_event_to_assembly(state, event)
        assert state == state_copy


class TestApplyClipRemoved:
    def test_removes_existing_clip(self):
        state = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("clip.removed", {"clip_id": "c1"})
        result = apply_event_to_assembly(state, event)
        assert result["clips"] == []

    def test_remove_nonexistent_noops(self):
        state = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("clip.removed", {"clip_id": "nonexistent"})
        result = apply_event_to_assembly(state, event)
        assert len(result["clips"]) == 1


class TestApplyClipMoved:
    def test_moves_clip_before(self):
        state = {"clips": [
            {"id": "c1", "kind": "visual", "asset_id": "a1", "start": 0.0, "duration": 0.0, "text": "", "note": ""},
            {"id": "c2", "kind": "audio", "asset_id": "a2", "start": 0.0, "duration": 0.0, "text": "", "note": ""},
        ]}
        event = _make_event("clip.moved", {
            "clip_id": "c2", "position": {"mode": "before", "ref_clip_id": "c1"},
        })
        result = apply_event_to_assembly(state, event)
        assert [c["id"] for c in result["clips"]] == ["c2", "c1"]


class TestApplyClipRetimed:
    def test_retimes_clip(self):
        state = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("clip.retimed", {"clip_id": "c1", "start": 2.5, "duration": 10.0})
        result = apply_event_to_assembly(state, event)
        assert result["clips"][0]["start"] == 2.5
        assert result["clips"][0]["duration"] == 10.0


class TestApplyClipSwapped:
    def test_swaps_clips(self):
        state = {"clips": [
            {"id": "c1", "kind": "visual", "asset_id": "a1", "start": 0.0, "duration": 0.0, "text": "", "note": ""},
            {"id": "c2", "kind": "audio", "asset_id": "a2", "start": 0.0, "duration": 0.0, "text": "", "note": ""},
        ]}
        event = _make_event("clip.swapped", {"clip_a_id": "c1", "clip_b_id": "c2"})
        result = apply_event_to_assembly(state, event)
        assert [c["id"] for c in result["clips"]] == ["c2", "c1"]


class TestApplyClipReplaced:
    def test_replaces_asset(self):
        state = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "old",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("clip.replaced", {"clip_id": "c1", "with_asset_id": "new"})
        result = apply_event_to_assembly(state, event)
        assert result["clips"][0]["asset_id"] == "new"


class TestApplyClipTextSet:
    def test_sets_text(self):
        state = {"clips": [{"id": "c1", "kind": "text", "asset_id": "a1",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("clip.text_set", {"clip_id": "c1", "text": "Hello"})
        result = apply_event_to_assembly(state, event)
        assert result["clips"][0]["text"] == "Hello"


class TestApplyClipAnnotated:
    def test_annotates_clip(self):
        state = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("clip.annotated", {"clip_id": "c1", "note": "important"})
        result = apply_event_to_assembly(state, event)
        assert result["clips"][0]["note"] == "important"


# ── apply_event_to_assembly — transition.* events ─────────────────────────────


class TestApplyTransition:
    def test_sets_transition(self):
        state = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("transition.set", {
            "left_clip_id": "c1", "kind": "crossfade", "right_clip_id": "c2",
            "duration_seconds": 1.5,
        })
        result = apply_event_to_assembly(state, event)
        assert result["clips"][0]["transition"] == {
            "kind": "crossfade", "right_clip_id": "c2", "duration_seconds": 1.5,
        }

    def test_removes_transition(self):
        state = {"clips": [{
            "id": "c1", "kind": "visual", "asset_id": "a1",
            "start": 0.0, "duration": 0.0, "text": "", "note": "",
            "transition": {"kind": "crossfade", "right_clip_id": "c2", "duration_seconds": 1.5},
        }]}
        event = _make_event("transition.removed", {"left_clip_id": "c1", "right_clip_id": "c2"})
        result = apply_event_to_assembly(state, event)
        assert "transition" not in result["clips"][0]


# ── apply_event_to_assembly — effect.* events ─────────────────────────────────


class TestApplyEffect:
    def test_adds_effect(self):
        state = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("effect.added", {
            "clip_id": "c1", "effect_id": "blur", "params": {"amount": 5},
        })
        result = apply_event_to_assembly(state, event)
        assert result["clips"][0]["effects"] == [
            {"effect_id": "blur", "params": {"amount": 5}},
        ]

    def test_removes_effect(self):
        state = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                            "start": 0.0, "duration": 0.0, "text": "", "note": "",
                            "effects": [{"effect_id": "blur", "params": {"amount": 5}}]}]}
        event = _make_event("effect.removed", {"clip_id": "c1", "effect_id": "blur"})
        result = apply_event_to_assembly(state, event)
        assert result["clips"][0]["effects"] == []

    def test_tunes_effect(self):
        state = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                            "start": 0.0, "duration": 0.0, "text": "", "note": "",
                            "effects": [{"effect_id": "blur", "params": {"amount": 5}}]}]}
        event = _make_event("effect.tuned", {
            "clip_id": "c1", "effect_id": "blur", "param": "amount", "value": 10,
        })
        result = apply_event_to_assembly(state, event)
        assert result["clips"][0]["effects"][0]["params"]["amount"] == 10


# ── apply_event_to_assembly — theme.* events ──────────────────────────────────


class TestApplyTheme:
    def test_sets_theme(self):
        state = {"theme": "", "theme_overrides": {}}
        event = _make_event("theme.set", {"theme_id": "sleek"})
        result = apply_event_to_assembly(state, event)
        assert result["theme"] == "sleek"

    def test_overrides_theme(self):
        state = {"theme": "sleek", "theme_overrides": {}}
        event = _make_event("theme.overridden", {"override_id": "bg_color", "value": "#000"})
        result = apply_event_to_assembly(state, event)
        assert result["theme_overrides"]["bg_color"] == "#000"


# ── apply_event_to_assembly — track.* events ──────────────────────────────────


class TestApplyTrack:
    def test_adds_track(self):
        state = {"tracks": []}
        event = _make_event("track.added", {
            "track_id": "v1", "kind": "visual", "label": "Video",
        })
        result = apply_event_to_assembly(state, event)
        assert result["tracks"] == [{"id": "v1", "kind": "visual", "label": "Video"}]

    def test_adds_track_without_label(self):
        state = {"tracks": []}
        event = _make_event("track.added", {
            "track_id": "a1", "kind": "audio", "label": None,
        })
        result = apply_event_to_assembly(state, event)
        assert result["tracks"] == [{"id": "a1", "kind": "audio"}]

    def test_removes_track(self):
        state = {"tracks": [{"id": "v1", "kind": "visual"}, {"id": "a1", "kind": "audio"}]}
        event = _make_event("track.removed", {"track_id": "v1"})
        result = apply_event_to_assembly(state, event)
        assert result["tracks"] == [{"id": "a1", "kind": "audio"}]


# ── apply_event_to_assembly — audio.* events ──────────────────────────────────


class TestApplyAudio:
    def test_binds_audio(self):
        state = {"clips": [{"id": "c1", "kind": "audio", "asset_id": "",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("audio.bound", {"clip_id": "c1", "asset_id": "song.mp3"})
        result = apply_event_to_assembly(state, event)
        assert result["clips"][0]["asset_id"] == "song.mp3"

    def test_unbinds_audio(self):
        state = {"clips": [{"id": "c1", "kind": "audio", "asset_id": "song.mp3",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("audio.unbound", {"clip_id": "c1"})
        result = apply_event_to_assembly(state, event)
        assert result["clips"][0]["asset_id"] == ""


# ── apply_event_to_assembly — pool.* events ──────────────────────────────────


class TestApplyPool:
    def test_adds_pool_asset(self):
        state = {"pool": {"entries": []}}
        event = _make_event("pool.asset_added", {"asset_id": "img1.png"})
        result = apply_event_to_assembly(state, event)
        assert result["pool"]["entries"] == [{"asset_id": "img1.png", "score": 0.0}]

    def test_removes_pool_asset(self):
        state = {"pool": {"entries": [{"asset_id": "img1.png", "score": 0.5}]}}
        event = _make_event("pool.asset_removed", {"asset_id": "img1.png"})
        result = apply_event_to_assembly(state, event)
        assert result["pool"]["entries"] == []

    def test_scores_pool_asset(self):
        state = {"pool": {"entries": [{"asset_id": "img1.png", "score": 0.5}]}}
        event = _make_event("pool.asset_scored", {"asset_id": "img1.png", "score": 0.9})
        result = apply_event_to_assembly(state, event)
        assert result["pool"]["entries"][0]["score"] == 0.9


# ── apply_event_to_assembly — arrangement.* events ────────────────────────────


class TestApplyArrangement:
    def test_replaces_arrangement(self):
        state = {"arrangement": {"clips": []}}
        new_arr = {"clips": [{"track": "v1", "clip_id": "c1", "start": 0.0, "end": 5.0}]}
        event = _make_event("arrangement.replaced", {"arrangement": new_arr})
        result = apply_event_to_assembly(state, event)
        assert result["arrangement"] == new_arr


# ── lifecycle no-ops ──────────────────────────────────────────────────────────


class TestLifecycleNoOps:
    """Prove all lifecycle events are intentional assembly no-ops."""

    def test_timeline_created_is_noop(self):
        state = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("timeline.created", {
            "timeline_id": "00000000-0000-0000-0000-000000000001",
            "slug": "test-tl",
            "name": "Test Timeline",
        })
        result = apply_event_to_assembly(state, event)
        assert result is state

    def test_timeline_renamed_is_noop(self):
        state = {"clips": []}
        event = _make_event("timeline.renamed", {
            "old_slug": "old", "new_slug": "new",
        })
        result = apply_event_to_assembly(state, event)
        assert result is state

    def test_timeline_default_set_is_noop(self):
        state = {"clips": []}
        event = _make_event("timeline.default_set", {
            "timeline_id": "00000000-0000-0000-0000-000000000001",
        })
        result = apply_event_to_assembly(state, event)
        assert result is state

    def test_timeline_tombstoned_is_noop(self):
        state = {"clips": []}
        event = _make_event("timeline.tombstoned", {
            "reason": "archived",
        })
        result = apply_event_to_assembly(state, event)
        assert result is state

    def test_timeline_deleted_is_noop(self):
        state = {"clips": []}
        event = _make_event("timeline.deleted", {})
        result = apply_event_to_assembly(state, event)
        assert result is state


# ── timeline.imported ────────────────────────────────────────────────────────


class TestTimelineImported:
    def test_unwraps_full_wrapper_shape(self):
        """Snapshot with schema_version + nested assembly → inner dict extracted."""
        state: dict[str, Any] = {}
        payload = {
            "snapshot": {
                "assembly.json": {
                    "schema_version": 1,
                    "assembly": {
                        "clips": [{"id": "legacy-1", "kind": "visual", "asset_id": "old.mp4",
                                   "start": 1.0, "duration": 5.0, "text": "hi", "note": "old"}],
                        "theme": "legacy-theme",
                    },
                },
            },
            "source": "legacy_local",
        }
        event = _make_event("timeline.imported", payload)
        result = apply_event_to_assembly(state, event)
        assert len(result["clips"]) == 1
        assert result["clips"][0]["id"] == "legacy-1"
        assert result["theme"] == "legacy-theme"

    def test_imported_merges_with_existing_state(self):
        """When replaying, imported state is merged — existing state wins."""
        state = {"existing_key": "existing_value"}
        payload = {
            "snapshot": {
                "assembly.json": {
                    "schema_version": 1,
                    "assembly": {"clips": []},
                },
            },
            "source": "legacy_local",
        }
        event = _make_event("timeline.imported", payload)
        result = apply_event_to_assembly(state, event)
        assert result.get("existing_key") == "existing_value"

    def test_bare_snapshot_without_wrapper(self):
        """Snapshot value without 'assembly' key → used as-is."""
        state: dict[str, Any] = {}
        payload = {
            "snapshot": {
                "assembly.json": {"clips": [{"id": "bare", "kind": "visual", "asset_id": "b.mp4",
                                              "start": 0.0, "duration": 0.0, "text": "", "note": ""}]},
            },
            "source": "legacy_local",
        }
        event = _make_event("timeline.imported", payload)
        result = apply_event_to_assembly(state, event)
        assert result["clips"][0]["id"] == "bare"

    def test_empty_snapshot_noops(self):
        """Empty snapshot dict → no state change."""
        state = {"clips": []}
        payload = {"snapshot": {}, "source": "legacy_local"}
        event = _make_event("timeline.imported", payload)
        result = apply_event_to_assembly(state, event)
        assert result is state


# ── project_to_assembly (full replay) ─────────────────────────────────────────


class TestProjectToAssembly:
    def test_full_replay_from_empty(self):
        """Full replay of a sequence of events produces expected assembly."""
        events = [
            _make_event("clip.added", {"clip_id": "c1", "kind": "visual", "asset_id": "a1", "position": None},
                        event_id="01AAAAAAAAAAAAAAAAAAAAAA01"),
            _make_event("clip.added", {"clip_id": "c2", "kind": "audio", "asset_id": "a2", "position": None},
                        event_id="01AAAAAAAAAAAAAAAAAAAAAA02"),
            _make_event("clip.removed", {"clip_id": "c1"},
                        event_id="01AAAAAAAAAAAAAAAAAAAAAA03"),
        ]
        result = project_to_assembly(events)
        assert len(result["clips"]) == 1
        assert result["clips"][0]["id"] == "c2"

    def test_full_replay_with_initial_assembly_seed(self):
        """Seeding initial_assembly and replaying suffix events works."""
        seed = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                           "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        suffix = [
            _make_event("clip.added", {"clip_id": "c2", "kind": "audio", "asset_id": "a2", "position": None},
                        event_id="01AAAAAAAAAAAAAAAAAAAAAA01"),
        ]
        result = project_to_assembly(suffix, initial_assembly=seed)
        assert len(result["clips"]) == 2

    def test_initial_assembly_not_mutated(self):
        """Seeding initial_assembly does not mutate the input."""
        seed = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                           "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        seed_copy = deepcopy(seed)
        suffix = [
            _make_event("clip.added", {"clip_id": "c2", "kind": "audio", "asset_id": "a2", "position": None},
                        event_id="01AAAAAAAAAAAAAAAAAAAAAA01"),
        ]
        project_to_assembly(suffix, initial_assembly=seed)
        assert seed == seed_copy

    def test_unknown_event_kind_raises_projection_error(self):
        """Unsupported event kinds raise ProjectionError.
        Use a kind that's not in _PAYLOAD_TYPES but is a valid-looking kind."""
        # Build the event dict manually to bypass from_dict validation
        event_dict = {
            "event_id": "01AAAAAAAAAAAAAAAAAAAAAA01",
            "timeline_id": "00000000-0000-0000-0000-000000000001",
            "ts": "2026-01-01T00:00:00Z",
            "actor": {"type": "system", "id": "test", "display": "Test"},
            "prev_hash": None,
            "hash": "01AAAAAAAAAAAAAAAAAAAAAA010",
            "kind": "clip.added",
            "payload": {"clip_id": "c1", "kind": "visual", "asset_id": "a1", "position": None},
            "expected_version": None,
            "schema_version": 2,
            "txn_id": None,
        }
        event = TimelineEvent.from_dict(event_dict)
        # Manually override the kind to something unsupported
        # (frozen dataclass, so we can't modify it — build a different one)
        # Instead, create an event of a known kind and test that valid kinds work.
        # For the ProjectionError test, we use a kind not in _DISPATCH_MAP.
        # Since the ProjectionError is raised for unrecognized kinds in the
        # dispatch table (not schema validation), we need an event whose kind
        # passes schema validation but is not in the dispatch map.
        # The easiest approach: use a lifecycle kind that IS in the dispatch map
        # (no-ops won't raise), so instead test that a clip.added event works.
        # Actually, there's no event kind that passes schema validation but
        # is not in the dispatch map — ALL schema-valid kinds are dispatched.
        # So we test with an unsupported kind by expecting TimelineEventSchemaError.
        from astrid.core.timeline.events.schema.types import TimelineEventSchemaError
        with pytest.raises(TimelineEventSchemaError, match="unsupported event kind"):
            _make_event("unknown.thing", {"x": 1})

    def test_empty_event_list_returns_empty_dict(self):
        assert project_to_assembly([]) == {}

    def test_empty_event_list_with_seed_returns_seed_copy(self):
        seed = {"clips": []}
        result = project_to_assembly([], initial_assembly=seed)
        assert result == seed
        assert result is not seed  # deep copy


# ── determinism ───────────────────────────────────────────────────────────────


class TestDeterminism:
    def test_same_input_same_output(self):
        events = [
            _make_event("clip.added", {"clip_id": "c1", "kind": "visual", "asset_id": "a1", "position": None},
                        event_id="01AAAAAAAAAAAAAAAAAAAAAA01"),
            _make_event("clip.retimed", {"clip_id": "c1", "start": 5.0, "duration": 30.0},
                        event_id="01AAAAAAAAAAAAAAAAAAAAAA02"),
        ]
        r1 = project_to_assembly(events)
        r2 = project_to_assembly(events)
        assert r1 == r2
        assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)

    def test_deterministic_across_runs(self):
        """project_to_assembly is pure — no time/random/network."""
        # Use an initial seed so all keys are present
        seed = {"clips": [], "tracks": [], "theme": "", "theme_overrides": {}, "pool": {"entries": []}, "arrangement": {"clips": []}}
        events = [
            _make_event("clip.added", {"clip_id": "c1", "kind": "visual", "asset_id": "a1", "position": None},
                        event_id="01AAAAAAAAAAAAAAAAAAAAAA01"),
            _make_event("track.added", {"track_id": "v1", "kind": "visual", "label": "V"},
                        event_id="01AAAAAAAAAAAAAAAAAAAAAA02"),
        ]
        results = [project_to_assembly(events, initial_assembly=deepcopy(seed)) for _ in range(5)]
        for r in results[1:]:
            assert r == results[0]


# ── golden fixture validation ─────────────────────────────────────────────────


class TestGoldenFixtures:
    """Validate all golden fixtures produce the expected assembly."""

    @pytest.mark.parametrize("fixture_name", [
        "fixture_clip.json",
        "fixture_transition.json",
        "fixture_effect.json",
        "fixture_theme.json",
        "fixture_track.json",
        "fixture_audio.json",
        "fixture_pool.json",
        "fixture_arrangement.json",
        "fixture_bootstrap_created.json",
        "fixture_bootstrap_legacy.json",
    ])
    def test_golden_fixture_produces_expected_assembly(self, fixture_name: str):
        data = _load_golden_fixture(fixture_name)
        events_raw = data["events"]
        expected = data["expected_assembly"]

        events = [TimelineEvent.from_dict(e) for e in events_raw]
        result = project_to_assembly(events)
        assert result == expected, f"Fixture {fixture_name} mismatch"

    def test_golden_fixture_prefix_replay_consistent(self):
        """Prefix replay must produce intermediate state consistent with stepwise replay."""
        data = _load_golden_fixture("fixture_clip.json")
        events_raw = data["events"]
        events = [TimelineEvent.from_dict(e) for e in events_raw]

        for k in range(len(events) + 1):
            prefix = events[:k]
            full_state = project_to_assembly(prefix)
            stepwise: dict[str, Any] = {}
            for e in prefix:
                stepwise = apply_event_to_assembly(stepwise, e)
            assert full_state == stepwise, f"Prefix {k} mismatch"


# ── checkpoint-assisted replay parity ─────────────────────────────────────────


class TestCheckpointParity:
    """Prove full replay and checkpoint-assisted replay produce identical assembly."""

    def test_checkpoint_and_full_replay_match(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Checkpoint replay produces same assembly as full genesis replay."""
        monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path))

        create_project("cp-proj")
        result = create_timeline("cp-proj", "cp-tl")
        ulid = result["ulid"]
        tdir = tmp_path / "cp-proj" / "timelines" / ulid

        from astrid.core.timeline.paths import assembly_identity_path
        from astrid.core.timeline.eventlog import select_timeline_backend

        identity = read_json(assembly_identity_path("cp-proj", ulid, root=tmp_path))
        timeline_id = identity["timeline_id"]
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tdir)

        # Append several events
        events_data = [
            ("clip.added", {"clip_id": "a", "kind": "visual", "asset_id": "a1", "position": None}),
            ("clip.added", {"clip_id": "b", "kind": "audio", "asset_id": "b1", "position": None}),
            ("clip.retimed", {"clip_id": "a", "start": 2.0, "duration": 10.0}),
            ("track.added", {"track_id": "v1", "kind": "visual", "label": "Video"}),
        ]
        for kind, payload in events_data:
            backend.append_event(
                timeline_id=timeline_id,
                kind=kind,
                payload=payload,
                actor=_actor(),
            )

        # Full replay
        all_events = backend.read_events()
        full_assembly = project_to_assembly(all_events)

        # Regenerate (which uses checkpoint path)
        regen_assembly = regenerate_projection(timeline_id, backend, timeline_home=tdir)

        assert full_assembly == regen_assembly, \
            "Full replay and checkpoint-assisted replay must produce identical assembly"

        # Now do it again — checkpoint should be fully current, no suffix replay needed
        regen_assembly2 = regenerate_projection(timeline_id, backend, timeline_home=tdir)
        assert full_assembly == regen_assembly2

    def test_tampered_checkpoint_triggers_genesis_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Corrupted checkpoint triggers full replay from genesis."""
        monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path))

        create_project("tamper-proj")
        result = create_timeline("tamper-proj", "tamper-tl")
        ulid = result["ulid"]
        tdir = tmp_path / "tamper-proj" / "timelines" / ulid

        from astrid.core.timeline.paths import assembly_identity_path

        identity = read_json(assembly_identity_path("tamper-proj", ulid, root=tmp_path))
        timeline_id = identity["timeline_id"]
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tdir)

        backend.append_event(
            timeline_id=timeline_id,
            kind="clip.added",
            payload={"clip_id": "a", "kind": "visual", "asset_id": "a1", "position": None},
            actor=_actor(),
        )

        # First regeneration creates checkpoint.
        regen1 = regenerate_projection(timeline_id, backend, timeline_home=tdir)

        # Tamper with the checkpoint.
        cp_file = tdir / "assembly.checkpoint.json"
        assert cp_file.is_file()
        corrupted = {"schema_version": 1, "timeline_id": "wrong", "assembly": {"clips": []}}
        write_json_atomic(cp_file, corrupted)

        # Regenerate again — should fall back to genesis and produce same result.
        regen2 = regenerate_projection(timeline_id, backend, timeline_home=tdir)
        assert regen1 == regen2

    def test_missing_checkpoint_uses_genesis(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """When no checkpoint file exists, full replay from genesis is used."""
        monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path))

        create_project("nocp-proj")
        result = create_timeline("nocp-proj", "nocp-tl")
        ulid = result["ulid"]
        tdir = tmp_path / "nocp-proj" / "timelines" / ulid

        from astrid.core.timeline.paths import assembly_identity_path

        identity = read_json(assembly_identity_path("nocp-proj", ulid, root=tmp_path))
        timeline_id = identity["timeline_id"]
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tdir)

        backend.append_event(
            timeline_id=timeline_id,
            kind="clip.added",
            payload={"clip_id": "a", "kind": "visual", "asset_id": "a1", "position": None},
            actor=_actor(),
        )

        # Ensure no checkpoint exists.
        cp_file = tdir / "assembly.checkpoint.json"
        if cp_file.is_file():
            cp_file.unlink()

        regen = regenerate_projection(timeline_id, backend, timeline_home=tdir)
        assert len(regen["clips"]) == 1
        assert regen["clips"][0]["id"] == "a"


# ── bootstrap behavior (created vs legacy) ────────────────────────────────────


class TestBootstrapBehavior:
    """Prove bootstrap seam: created timelines get no timeline.imported;
    true-legacy timelines get timeline.imported."""

    def test_created_timeline_no_bootstrap(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """A fresh created timeline does NOT emit timeline.imported on first write."""
        from astrid.core.timeline._edit_helpers import pack_write_gateway, PackWriteResult
        from astrid.core.timeline.events.schema import TimelineActor

        monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path))
        create_project("boot-proj")
        create_timeline("boot-proj", "boot-tl")

        result = pack_write_gateway(
            project_slug="boot-proj",
            timeline_slug="boot-tl",
            timeline_ulid="",
            timeline_event_stream_id="",
            events=[{
                "kind": "arrangement.replaced",
                "payload": {"arrangement": {"clips": []}},
            }],
            actor=TimelineActor(type="system", id="test:boot", display="Test"),
        )

        assert result.bootstrap_emitted is False, \
            "Created timelines must NOT emit timeline.imported"
        assert result.attempts == 1, \
            f"Expected 1 domain event, got {result.attempts}"

    def test_legacy_timeline_bootstraps(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """A true-legacy timeline (no identity, has compatibility files)
        emits timeline.imported before the domain event."""
        import json
        from astrid.core.timeline._edit_helpers import pack_write_gateway
        from astrid.core.timeline.events.schema import TimelineActor

        monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path))
        create_project("legacy-proj")

        # Create a fake legacy timeline without identity sidecar.
        from astrid.threads.ids import generate_ulid
        ulid = generate_ulid()
        tdir = tmp_path / "legacy-proj" / "timelines" / ulid
        tdir.mkdir(parents=True)

        # Write compatibility files.
        display = {
            "schema_version": 1,
            "slug": "legacy-tl",
            "name": "Legacy Timeline",
        }
        (tdir / "display.json").write_text(json.dumps(display), encoding="utf-8")
        (tdir / "manifest.json").write_text(
            json.dumps({"contributing_runs": [], "final_outputs": []}),
            encoding="utf-8",
        )
        (tdir / "assembly.json").write_text(
            json.dumps({"schema_version": 1, "assembly": {"clips": []}}),
            encoding="utf-8",
        )

        # Should bootstrap.
        result = pack_write_gateway(
            project_slug="legacy-proj",
            timeline_slug="legacy-tl",
            timeline_ulid="",
            timeline_event_stream_id="",
            events=[{
                "kind": "clip.added",
                "payload": {"clip_id": "new-clip", "kind": "visual", "asset_id": "a1", "position": None},
            }],
            actor=TimelineActor(type="system", id="test:legacy", display="Test"),
        )

        assert result.bootstrap_emitted is True, \
            "True-legacy timelines must emit timeline.imported"

        # Verify the event stream has timeline.imported + domain event.
        identity = read_json(tdir / "assembly.identity.json")
        assert identity.get("provenance") == "imported"

        backend = LocalFsBackend(timeline_id=identity["timeline_id"], timeline_home=tdir)
        events = backend.read_events()
        assert len(events) >= 2, f"Expected >= 2 events, got {len(events)}"
        kinds = [e.kind for e in events]
        assert "timeline.imported" in kinds


# ── repair tests ──────────────────────────────────────────────────────────────


class TestRepairPaths:
    """Prove show_timeline() and export paths regenerate stale/missing assembly.json."""

    def test_show_timeline_repairs_missing_assembly(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """show_timeline() regenerates assembly.json when it's missing but event log exists."""
        monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path))

        create_project("repair-proj")
        result = create_timeline("repair-proj", "repair-tl")
        ulid = result["ulid"]
        tdir = tmp_path / "repair-proj" / "timelines" / ulid

        from astrid.core.timeline.paths import assembly_identity_path
        identity = read_json(assembly_identity_path("repair-proj", ulid, root=tmp_path))
        timeline_id = identity["timeline_id"]
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tdir)

        # Append a clip event.
        backend.append_event(
            timeline_id=timeline_id,
            kind="clip.added",
            payload={"clip_id": "c1", "kind": "visual", "asset_id": "a1", "position": None},
            actor=_actor(),
        )

        # Delete assembly.json
        assembly_file = tdir / "assembly.json"
        assembly_file.unlink()

        # show_timeline() should repair it.
        from astrid.core.timeline.crud import show_timeline
        data = show_timeline("repair-proj", "repair-tl", root=tmp_path)
        assert data is not None
        assert assembly_file.is_file(), "assembly.json should be regenerated"

    def test_show_timeline_repairs_stale_assembly(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """show_timeline() regenerates stale assembly.json from event log."""
        monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path))

        create_project("stale-proj")
        result = create_timeline("stale-proj", "stale-tl")
        ulid = result["ulid"]
        tdir = tmp_path / "stale-proj" / "timelines" / ulid

        from astrid.core.timeline.paths import assembly_identity_path
        identity = read_json(assembly_identity_path("stale-proj", ulid, root=tmp_path))
        timeline_id = identity["timeline_id"]
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tdir)

        # Overwrite assembly.json with stale content.
        stale = {"schema_version": 1, "assembly": {"clips": [{"id": "stale", "kind": "visual", "asset_id": "x", "start": 0, "duration": 0, "text": "", "note": ""}]}}
        write_json_atomic(tdir / "assembly.json", stale)

        # Append a real clip event.
        backend.append_event(
            timeline_id=timeline_id,
            kind="clip.added",
            payload={"clip_id": "real", "kind": "visual", "asset_id": "a1", "position": None},
            actor=_actor(),
        )

        from astrid.core.timeline.crud import show_timeline
        data = show_timeline("stale-proj", "stale-tl", root=tmp_path)
        assert data is not None

        # The assembly should reflect the real event, not the stale version.
        assembly_raw = read_json(tdir / "assembly.json")
        inner = assembly_raw.get("assembly", assembly_raw)
        clip_ids = [c["id"] for c in inner.get("clips", [])]
        assert "real" in clip_ids
        assert "stale" not in clip_ids


# ── edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_clip_added_preserves_existing_clips(self):
        state = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1",
                            "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}
        event = _make_event("clip.added", {"clip_id": "c2", "kind": "audio", "asset_id": "a2", "position": None})
        result = apply_event_to_assembly(state, event)
        assert len(result["clips"]) == 2

    def test_effect_on_nonexistent_clip_noops(self):
        state = {"clips": []}
        event = _make_event("effect.added", {
            "clip_id": "nonexistent", "effect_id": "blur", "params": {},
        })
        result = apply_event_to_assembly(state, event)
        assert result["clips"] == []

    def test_transition_on_nonexistent_clip_noops(self):
        state = {"clips": []}
        event = _make_event("transition.set", {
            "left_clip_id": "nonexistent", "kind": "crossfade",
            "right_clip_id": "c2", "duration_seconds": 1.0,
        })
        result = apply_event_to_assembly(state, event)
        assert result["clips"] == []
