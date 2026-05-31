"""Integration tests for astrid.core.timeline.clip_edits — all 8 clip primitives.

Tests cover:
- All 8 primitives on LocalFsBackend with event kind, timeline_id, actor,
  payload, and assembly.json output verification.
- Assembly-shape edge cases: empty initialization, existing with clips,
  incompatible non-empty without 'clips'.
- Supabase-selected paths that prove the provisional typed error contract
  surfaces from SupabaseBackend itself (not a preemptive local_fs guard).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.timeline.clip_edits import (
    ClipEditError,
    add_clip,
    annotate_clip,
    move_clip,
    remove_clip,
    replace_clip,
    retime_clip,
    set_clip_text,
    swap_clips,
)
from astrid.core.timeline.track_edits import track_add
from astrid.core.timeline.crud import create_timeline, show_timeline
from astrid.core.timeline.eventlog import (
    EventLogBackend,
    LocalFsBackend,
    SupabaseBackend,
    select_timeline_backend,
)
from astrid.core.timeline.eventlog.types import (
    EventLogMissingConfigError,
    EventLogUnsupportedRpcError,
)
from astrid.core.timeline.events.schema import (
    ClipAddedPayload,
    ClipAnnotatedPayload,
    ClipMovedPayload,
    ClipPosition,
    ClipRemovedPayload,
    ClipReplacedPayload,
    ClipRetimedPayload,
    ClipSwappedPayload,
    ClipTextSetPayload,
    TimelineActor,
    TimelineEvent,
)
from astrid.core.timeline.paths import (
    assembly_head_path,
    assembly_identity_path,
    timeline_dir,
)


# ── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def project_tree(tmp_projects_root: Path) -> Path:
    """Seed a minimal project under the monkeypatched ASTRID_PROJECTS_ROOT."""
    slug = "demo"
    pdir = tmp_projects_root / slug
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "runs").mkdir()
    (pdir / "sources").mkdir()
    (pdir / "project.json").write_text(
        json.dumps(
            {
                "created_at": "2026-05-11T00:00:00Z",
                "name": slug,
                "schema_version": 1,
                "slug": slug,
                "updated_at": "2026-05-11T00:00:00Z",
                "default_timeline_id": None,
            }
        ),
        encoding="utf-8",
    )
    return tmp_projects_root


@pytest.fixture
def demo_timeline(project_tree: Path) -> dict:
    """Create a timeline and return its metadata dict."""
    result = create_timeline("demo", "primary", name="Primary Timeline", root=project_tree)
    track_add(
        "demo",
        "primary",
        track_id="visual",
        kind="visual",
        label="Visual",
        actor=_actor("seed"),
        root=project_tree,
    )
    track_add(
        "demo",
        "primary",
        track_id="audio",
        kind="audio",
        label="Audio",
        actor=_actor("seed"),
        root=project_tree,
    )
    return {
        "ulid": result["ulid"],
        "slug": "primary",
        "identity": json.loads(
            assembly_identity_path("demo", result["ulid"], root=project_tree).read_text(
                encoding="utf-8"
            )
        ),
        "root": project_tree,
    }


def _actor(name: str = "tester") -> TimelineActor:
    return TimelineActor(type="agent", id=f"test:{name}", display=name)


def _read_assembly_json(tdir: Path) -> dict:
    """Read assembly.json from the timeline directory and return parsed contents."""
    return json.loads((tdir / "assembly.json").read_text(encoding="utf-8"))


# ── add_clip ────────────────────────────────────────────────────────────────


class TestAddClip:
    def test_add_clip_emits_correct_event_kind_and_payload(
        self, demo_timeline: dict
    ) -> None:
        ulid = demo_timeline["ulid"]
        timeline_id = demo_timeline["identity"]["timeline_id"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        event = add_clip(
            "demo",
            "primary",
            kind="visual",
            asset_id="asset_v1",
            actor=_actor(),
            root=demo_timeline["root"],
        )

        assert event.kind == "clip.added"
        assert event.timeline_id == timeline_id
        assert event.actor.id == "test:tester"
        assert isinstance(event.payload, ClipAddedPayload)
        assert event.payload.clip_id == "asset_v1"
        assert event.payload.kind == "visual"
        assert event.payload.asset_id == "asset_v1"

        # Verify assembly.json was updated
        assembly = _read_assembly_json(tdir)
        clips = assembly["clips"]
        assert len(clips) == 1
        assert clips[0]["id"] == "asset_v1"
        assert clips[0]["clipType"] == "media"
        assert clips[0]["track"] == "visual"
        assert clips[0]["asset"] == "asset_v1"

        # Verify event chain is valid
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tdir)
        assert backend.verify_chain().ok is True

    def test_add_clip_with_position_index(self, demo_timeline: dict) -> None:
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        add_clip("demo", "primary", kind="visual", asset_id="first", actor=_actor(), root=demo_timeline["root"])
        add_clip(
            "demo", "primary",
            kind="audio", asset_id="second",
            position=ClipPosition(mode="index", index=0),
            actor=_actor(),
            root=demo_timeline["root"],
        )
        add_clip("demo", "primary", kind="text", asset_id="third", actor=_actor(), root=demo_timeline["root"])

        assembly = _read_assembly_json(tdir)
        clips = assembly["clips"]
        assert len(clips) == 3
        # second was inserted at index 0
        assert clips[0]["id"] == "second"
        assert clips[1]["id"] == "first"
        assert clips[2]["id"] == "third"

    def test_add_clip_position_via_dict(self, demo_timeline: dict) -> None:
        add_clip(
            "demo", "primary",
            kind="visual", asset_id="a",
            position={"mode": "index", "index": 0},
            actor=_actor(),
            root=demo_timeline["root"],
        )
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])
        assembly = _read_assembly_json(tdir)
        assert assembly["clips"][0]["id"] == "a"

    def test_add_clip_rejects_invalid_kind(self, demo_timeline: dict) -> None:
        with pytest.raises(ClipEditError, match="kind must be"):
            add_clip("demo", "primary", kind="invalid", asset_id="a", actor=_actor(), root=demo_timeline["root"])  # type: ignore[arg-type]

    def test_add_clip_rejects_empty_asset_id(self, demo_timeline: dict) -> None:
        with pytest.raises(ClipEditError, match="asset_id must be"):
            add_clip("demo", "primary", kind="visual", asset_id="", actor=_actor(), root=demo_timeline["root"])

    def test_add_clip_passes_through_expected_version_and_txn_id(self, demo_timeline: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify expected_version and txn_id are forwarded to backend.append_event."""
        seen: dict = {}

        class SpyBackend:
            def backend_name(self) -> str:
                return "spy"
            def append_event(self, timeline_id, kind, payload, *, actor, expected_version=None, txn_id=None):
                seen["expected_version"] = expected_version
                seen["txn_id"] = txn_id
                seen["kind"] = kind
                return TimelineEvent.new(
                    timeline_id=timeline_id,
                    ts="2026-05-20T12:00:00Z",
                    actor=actor,
                    kind=kind,
                    payload=payload,
                )

        def fake_select(*, timeline_id, timeline_home=None, preferred_backend=None):
            return (SimpleNamespace(backend="spy"), SpyBackend())

        monkeypatch.setattr("astrid.core.timeline._edit_helpers.select_timeline_backend", fake_select)

        # Need to patch lower-level helpers that _resolve_backend calls.
        # We use a real timeline from demo_timeline to bypass path validation issues.
        ulid = demo_timeline["ulid"]
        identity = demo_timeline["identity"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        monkeypatch.setattr("astrid.core.timeline._edit_helpers.find_timeline_by_slug",
                            lambda ps, s, root=None: (ulid, tdir))
        monkeypatch.setattr("astrid.core.timeline._edit_helpers.read_json",
                            lambda p: identity)
        monkeypatch.setattr("astrid.core.timeline.clip_edits._materialize",
                            lambda tdir, event, **kwargs: None)

        add_clip(
            "demo", "primary",
            kind="visual", asset_id="a",
            actor=_actor(),
            expected_version=42,
            txn_id="01J00000000000000000000000",
            root=None,
        )

        assert seen.get("expected_version") == 42
        assert seen.get("txn_id") == "01J00000000000000000000000"


# ── remove_clip ─────────────────────────────────────────────────────────────


class TestRemoveClip:
    def test_remove_clip_emits_correct_event(self, demo_timeline: dict) -> None:
        ulid = demo_timeline["ulid"]
        timeline_id = demo_timeline["identity"]["timeline_id"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        # First add a clip
        add_clip("demo", "primary", kind="visual", asset_id="to_remove", actor=_actor(), root=demo_timeline["root"])

        event = remove_clip(
            "demo", "primary",
            clip_id="to_remove",
            actor=_actor(),
            root=demo_timeline["root"],
        )

        assert event.kind == "clip.removed"
        assert event.timeline_id == timeline_id
        assert isinstance(event.payload, ClipRemovedPayload)
        assert event.payload.clip_id == "to_remove"

        # Verify assembly.json no longer has the clip
        assembly = _read_assembly_json(tdir)
        assert len(assembly["clips"]) == 0

    def test_remove_nonexistent_clip_noops(self, demo_timeline: dict) -> None:
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        add_clip("demo", "primary", kind="visual", asset_id="keep", actor=_actor(), root=demo_timeline["root"])

        event = remove_clip("demo", "primary", clip_id="nonexistent", actor=_actor(), root=demo_timeline["root"])
        assert event.kind == "clip.removed"

        # Clip "keep" still exists
        assembly = _read_assembly_json(tdir)
        assert len(assembly["clips"]) == 1

    def test_remove_clip_rejects_empty_clip_id(self, demo_timeline: dict) -> None:
        with pytest.raises(ClipEditError, match="clip_id must be"):
            remove_clip("demo", "primary", clip_id="", actor=_actor(), root=demo_timeline["root"])


# ── move_clip ───────────────────────────────────────────────────────────────


class TestMoveClip:
    def test_move_clip_reorders(self, demo_timeline: dict) -> None:
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        add_clip("demo", "primary", kind="visual", asset_id="a", actor=_actor(), root=demo_timeline["root"])
        add_clip("demo", "primary", kind="visual", asset_id="b", actor=_actor(), root=demo_timeline["root"])
        add_clip("demo", "primary", kind="visual", asset_id="c", actor=_actor(), root=demo_timeline["root"])

        # Move "c" before "a"
        event = move_clip(
            "demo", "primary",
            clip_id="c",
            position=ClipPosition(mode="before", ref_clip_id="a"),
            actor=_actor(),
            root=demo_timeline["root"],
        )

        assert event.kind == "clip.moved"
        assert isinstance(event.payload, ClipMovedPayload)
        assert event.payload.clip_id == "c"
        assert event.payload.position.mode == "before"

        assembly = _read_assembly_json(tdir)
        ids = [c["id"] for c in assembly["clips"]]
        assert ids == ["c", "a", "b"]

    def test_move_clip_requires_position(self, demo_timeline: dict) -> None:
        add_clip("demo", "primary", kind="visual", asset_id="a", actor=_actor(), root=demo_timeline["root"])
        with pytest.raises(ClipEditError, match="position is required"):
            move_clip("demo", "primary", clip_id="a", position=None, actor=_actor(), root=demo_timeline["root"])  # type: ignore[arg-type]


# ── retime_clip ─────────────────────────────────────────────────────────────


class TestRetimeClip:
    def test_retime_clip_updates_start_and_duration(self, demo_timeline: dict) -> None:
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        add_clip("demo", "primary", kind="visual", asset_id="v1", actor=_actor(), root=demo_timeline["root"])

        event = retime_clip(
            "demo", "primary",
            clip_id="v1",
            start=3.5,
            duration=10.0,
            actor=_actor(),
            root=demo_timeline["root"],
        )

        assert event.kind == "clip.retimed"
        assert isinstance(event.payload, ClipRetimedPayload)
        assert event.payload.clip_id == "v1"
        assert event.payload.start == 3.5
        assert event.payload.duration == 10.0

        assembly = _read_assembly_json(tdir)
        clip = assembly["clips"][0]
        assert clip["at"] == 3.5
        assert clip["hold"] == 10.0

    def test_retime_rejects_negative_start(self, demo_timeline: dict) -> None:
        add_clip("demo", "primary", kind="visual", asset_id="v1", actor=_actor(), root=demo_timeline["root"])
        with pytest.raises(ClipEditError, match="start must be >= 0"):
            retime_clip("demo", "primary", clip_id="v1", start=-1, duration=5, actor=_actor(), root=demo_timeline["root"])

    def test_retime_rejects_non_positive_duration(self, demo_timeline: dict) -> None:
        add_clip("demo", "primary", kind="visual", asset_id="v1", actor=_actor(), root=demo_timeline["root"])
        with pytest.raises(ClipEditError, match="duration must be > 0"):
            retime_clip("demo", "primary", clip_id="v1", start=0, duration=0, actor=_actor(), root=demo_timeline["root"])


# ── swap_clips ──────────────────────────────────────────────────────────────


class TestSwapClips:
    def test_swap_clips_exchanges_positions(self, demo_timeline: dict) -> None:
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        add_clip("demo", "primary", kind="visual", asset_id="a", actor=_actor(), root=demo_timeline["root"])
        add_clip("demo", "primary", kind="visual", asset_id="b", actor=_actor(), root=demo_timeline["root"])

        event = swap_clips(
            "demo", "primary",
            clip_a_id="a", clip_b_id="b",
            actor=_actor(),
            root=demo_timeline["root"],
        )

        assert event.kind == "clip.swapped"
        assert isinstance(event.payload, ClipSwappedPayload)
        assert event.payload.clip_a_id == "a"
        assert event.payload.clip_b_id == "b"

        assembly = _read_assembly_json(tdir)
        ids = [c["id"] for c in assembly["clips"]]
        assert ids == ["b", "a"]

    def test_swap_rejects_same_ids(self, demo_timeline: dict) -> None:
        add_clip("demo", "primary", kind="visual", asset_id="a", actor=_actor(), root=demo_timeline["root"])
        with pytest.raises(ClipEditError, match="must be different"):
            swap_clips("demo", "primary", clip_a_id="a", clip_b_id="a", actor=_actor(), root=demo_timeline["root"])


# ── replace_clip ────────────────────────────────────────────────────────────


class TestReplaceClip:
    def test_replace_clip_changes_asset(self, demo_timeline: dict) -> None:
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        add_clip("demo", "primary", kind="visual", asset_id="old", actor=_actor(), root=demo_timeline["root"])

        event = replace_clip(
            "demo", "primary",
            clip_id="old",
            with_asset_id="new_asset",
            actor=_actor(),
            root=demo_timeline["root"],
        )

        assert event.kind == "clip.replaced"
        assert isinstance(event.payload, ClipReplacedPayload)
        assert event.payload.clip_id == "old"
        assert event.payload.with_asset_id == "new_asset"

        assembly = _read_assembly_json(tdir)
        assert assembly["clips"][0]["asset"] == "new_asset"

    def test_replace_rejects_empty_with_asset_id(self, demo_timeline: dict) -> None:
        add_clip("demo", "primary", kind="visual", asset_id="old", actor=_actor(), root=demo_timeline["root"])
        with pytest.raises(ClipEditError, match="with_asset_id must be"):
            replace_clip("demo", "primary", clip_id="old", with_asset_id="", actor=_actor(), root=demo_timeline["root"])


# ── set_clip_text ───────────────────────────────────────────────────────────


class TestSetClipText:
    def test_set_text_updates_text_field(self, demo_timeline: dict) -> None:
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        add_clip("demo", "primary", kind="text", asset_id="t1", actor=_actor(), root=demo_timeline["root"])

        event = set_clip_text(
            "demo", "primary",
            clip_id="t1",
            text="Hello World",
            actor=_actor(),
            root=demo_timeline["root"],
        )

        assert event.kind == "clip.text_set"
        assert isinstance(event.payload, ClipTextSetPayload)
        assert event.payload.clip_id == "t1"
        assert event.payload.text == "Hello World"

        assembly = _read_assembly_json(tdir)
        assert assembly["clips"][0]["text"] == {"content": "Hello World"}

    def test_set_text_accepts_empty_string(self, demo_timeline: dict) -> None:
        add_clip("demo", "primary", kind="text", asset_id="t1", actor=_actor(), root=demo_timeline["root"])
        event = set_clip_text("demo", "primary", clip_id="t1", text="", actor=_actor(), root=demo_timeline["root"])
        assert event.payload.text == ""


# ── annotate_clip ───────────────────────────────────────────────────────────


class TestAnnotateClip:
    def test_annotate_is_non_container_event_and_does_not_mutate_assembly(self, demo_timeline: dict) -> None:
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        add_clip("demo", "primary", kind="visual", asset_id="v1", actor=_actor(), root=demo_timeline["root"])

        event = annotate_clip(
            "demo", "primary",
            clip_id="v1",
            note="This is an important clip",
            actor=_actor(),
            root=demo_timeline["root"],
        )

        assert event.kind == "clip.annotated"
        assert isinstance(event.payload, ClipAnnotatedPayload)
        assert event.payload.clip_id == "v1"
        assert event.payload.note == "This is an important clip"

        assembly = _read_assembly_json(tdir)
        assert "params" not in assembly["clips"][0]

    def test_annotate_rejects_non_string_note(self, demo_timeline: dict) -> None:
        add_clip("demo", "primary", kind="visual", asset_id="v1", actor=_actor(), root=demo_timeline["root"])
        with pytest.raises(ClipEditError, match="note must be"):
            annotate_clip("demo", "primary", clip_id="v1", note=None, actor=_actor(), root=demo_timeline["root"])  # type: ignore[arg-type]


# ── assembly-shape edge cases ───────────────────────────────────────────────


class TestAssemblyShapeEdgeCases:
    def test_empty_assembly_initialised_with_clips_key(self, demo_timeline: dict) -> None:
        """Case (a): empty assembly → clips: [] initialized."""
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        # After create_timeline, assembly is empty {} → add_clip initializes it
        add_clip("demo", "primary", kind="visual", asset_id="v1", actor=_actor(), root=demo_timeline["root"])

        assembly = _read_assembly_json(tdir)
        assert "clips" in assembly
        assert isinstance(assembly["clips"], list)
        assert len(assembly["clips"]) == 1

    def test_existing_clips_updated_in_place(self, demo_timeline: dict) -> None:
        """Case (b): existing assembly with 'clips' → updated in place."""
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        add_clip("demo", "primary", kind="visual", asset_id="v1", actor=_actor(), root=demo_timeline["root"])
        add_clip("demo", "primary", kind="audio", asset_id="a1", actor=_actor(), root=demo_timeline["root"])

        assembly = _read_assembly_json(tdir)
        assert len(assembly["clips"]) == 2

    def test_assembly_regenerated_from_event_stream(self, demo_timeline: dict) -> None:
        """Under m4 regeneration, assembly.json is fully regenerated from the
        canonical event stream on every edit.  Manual tampering with
        assembly.json between edits is overwritten."""
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        # Add a clip
        add_clip("demo", "primary", kind="visual", asset_id="v1", actor=_actor(), root=demo_timeline["root"])

        # Manually inject an unrelated key into assembly.json
        new_assembly_dict = dict(_read_assembly_json(tdir))
        new_assembly_dict["other_key"] = "preserved_value"
        (tdir / "assembly.json").write_text(json.dumps(new_assembly_dict), encoding="utf-8")

        # Now add another clip — assembly.json is regenerated from the event stream,
        # so the manually injected key is overwritten.
        add_clip("demo", "primary", kind="audio", asset_id="a1", actor=_actor(), root=demo_timeline["root"])

        assembly_after = _read_assembly_json(tdir)
        # The manually injected key is NOT preserved because assembly.json is
        # fully regenerated from the canonical event stream.
        assert "other_key" not in assembly_after
        assert len(assembly_after["clips"]) == 2

    def test_assembly_regenerated_even_from_corrupted_file(
        self, demo_timeline: dict
    ) -> None:
        """A corrupted assembly.json does not prevent edits — regeneration
        rebuilds from the event stream."""
        ulid = demo_timeline["ulid"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        # Replace assembly.json with incompatible shape
        (tdir / "assembly.json").write_text(
            json.dumps({"some_other_key": "value"}), encoding="utf-8"
        )

        # Under m4, add_clip regenerates assembly.json from the event stream
        # before applying the new event.  Since the event stream is empty
        # (no clips yet), the assembly starts empty and the clip is added.
        event = add_clip("demo", "primary", kind="visual", asset_id="v1", actor=_actor(), root=demo_timeline["root"])
        assert event.kind == "clip.added"

        assembly_after = _read_assembly_json(tdir)
        assert "clips" in assembly_after
        assert len(assembly_after["clips"]) == 1


# ── Supabase-selected paths ─────────────────────────────────────────────────


class TestSupabaseSelectedPaths:
    def test_supabase_backend_raises_missing_config_on_clip_edit(
        self, demo_timeline: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prove clip-edit code calls SupabaseBackend.append_event and
        surfaces the typed missing-config error (not a preemptive local_fs guard)."""
        ulid = demo_timeline["ulid"]
        identity = demo_timeline["identity"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        # Force the selector to return SupabaseBackend
        def fake_select(*, timeline_id, timeline_home=None, preferred_backend=None):
            return (
                SimpleNamespace(backend="supabase", source="preferred_backend"),
                SupabaseBackend(timeline_id=timeline_id),
            )

        monkeypatch.setattr("astrid.core.timeline._edit_helpers.select_timeline_backend", fake_select)

        # find_timeline_by_slug and read_json still work normally for resolution
        with pytest.raises(EventLogMissingConfigError, match="SupabaseBackend"):
            add_clip("demo", "primary", kind="visual", asset_id="v1", actor=_actor(), root=demo_timeline["root"])

    def test_supabase_error_not_preemptive_local_fs_guard(
        self, demo_timeline: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Confirm the Supabase error is NOT a preemptive local_fs
        AvailabilityError — it comes from SupabaseBackend.append_event itself."""
        ulid = demo_timeline["ulid"]
        timeline_id = demo_timeline["identity"]["timeline_id"]

        called_backend = []

        class TrackingSupabaseBackend:
            def __init__(self, timeline_id):
                self._real = SupabaseBackend(timeline_id=timeline_id)

            def backend_name(self) -> str:
                return "supabase"

            def append_event(self, timeline_id, kind, payload, *, actor, expected_version=None, txn_id=None):
                called_backend.append("append_event")
                return self._real.append_event(
                    timeline_id, kind, payload,
                    actor=actor,
                    expected_version=expected_version,
                    txn_id=txn_id,
                )

        def fake_select(*, timeline_id, timeline_home=None, preferred_backend=None):
            return (
                SimpleNamespace(backend="supabase", source="preferred_backend"),
                TrackingSupabaseBackend(timeline_id=timeline_id),
            )

        monkeypatch.setattr("astrid.core.timeline._edit_helpers.select_timeline_backend", fake_select)

        with pytest.raises(EventLogMissingConfigError, match="SupabaseBackend"):
            add_clip("demo", "primary", kind="visual", asset_id="v1", actor=_actor(), root=demo_timeline["root"])

        # This proves the error came from SupabaseBackend.append_event, not a preemptive guard
        assert "append_event" in called_backend

    def test_all_eight_primitives_raise_on_supabase_without_config(
        self, demo_timeline: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All 8 clip.* verbs raise typed missing-config errors on unconfigured Supabase."""
        # Force Supabase selection
        def fake_select(*, timeline_id, timeline_home=None, preferred_backend=None):
            return (
                SimpleNamespace(backend="supabase", source="preferred_backend"),
                SupabaseBackend(timeline_id=timeline_id),
            )

        monkeypatch.setattr("astrid.core.timeline._edit_helpers.select_timeline_backend", fake_select)

        # First add a clip on local_fs so we have something to operate on for remove/move/etc.
        # We need to bypass the monkeypatch for setup
        # Actually, we just test that each function hits the Supabase stub.
        # For operations that need existing clips, we test only the call path.

        ops = [
            lambda: add_clip("demo", "primary", kind="visual", asset_id="x", actor=_actor(), root=demo_timeline["root"]),
            lambda: remove_clip("demo", "primary", clip_id="x", actor=_actor(), root=demo_timeline["root"]),
            lambda: move_clip("demo", "primary", clip_id="x", position=ClipPosition(mode="index", index=0), actor=_actor(), root=demo_timeline["root"]),
            lambda: retime_clip("demo", "primary", clip_id="x", start=0, duration=5, actor=_actor(), root=demo_timeline["root"]),
            lambda: swap_clips("demo", "primary", clip_a_id="x", clip_b_id="y", actor=_actor(), root=demo_timeline["root"]),
            lambda: replace_clip("demo", "primary", clip_id="x", with_asset_id="y", actor=_actor(), root=demo_timeline["root"]),
            lambda: set_clip_text("demo", "primary", clip_id="x", text="hi", actor=_actor(), root=demo_timeline["root"]),
            lambda: annotate_clip("demo", "primary", clip_id="x", note="n", actor=_actor(), root=demo_timeline["root"]),
        ]

        for i, op in enumerate(ops):
            with pytest.raises(EventLogMissingConfigError, match="SupabaseBackend"):
                op()

    def test_configured_supabase_backend_raises_unsupported_rpc_on_clip_edit(
        self, demo_timeline: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_select(*, timeline_id, timeline_home=None, preferred_backend=None):
            return (
                SimpleNamespace(backend="supabase", source="preferred_backend"),
                SupabaseBackend(
                    timeline_id=timeline_id,
                    supabase_url="https://example.supabase.co",
                    auth_token="pat-token",
                    enabled=True,
                ),
            )

        monkeypatch.setattr("astrid.core.timeline._edit_helpers.select_timeline_backend", fake_select)

        with pytest.raises(EventLogUnsupportedRpcError, match="append_timeline_event"):
            add_clip("demo", "primary", kind="visual", asset_id="x", actor=_actor(), root=demo_timeline["root"])


# ── default actor fallback ──────────────────────────────────────────────────


class TestDefaultActor:
    def test_add_clip_uses_default_actor_when_none_given(
        self, demo_timeline: dict
    ) -> None:
        event = add_clip("demo", "primary", kind="visual", asset_id="v1", root=demo_timeline["root"])
        assert event.actor.type == "system"
        assert event.actor.id == "timeline-edits:add_clip"

    def test_remove_clip_uses_default_actor(self, demo_timeline: dict) -> None:
        add_clip("demo", "primary", kind="visual", asset_id="x", root=demo_timeline["root"])
        event = remove_clip("demo", "primary", clip_id="x", root=demo_timeline["root"])
        assert event.actor.id == "timeline-edits:remove_clip"


# ── hash chain integrity across multiple operations ─────────────────────────


class TestHashChainIntegrity:
    def test_multiple_operations_preserve_hash_chain(self, demo_timeline: dict) -> None:
        ulid = demo_timeline["ulid"]
        timeline_id = demo_timeline["identity"]["timeline_id"]
        tdir = timeline_dir("demo", ulid, root=demo_timeline["root"])

        # Perform all 8 operations
        add_clip("demo", "primary", kind="visual", asset_id="a", actor=_actor(), root=demo_timeline["root"])
        add_clip("demo", "primary", kind="audio", asset_id="b", actor=_actor(), root=demo_timeline["root"])
        add_clip("demo", "primary", kind="text", asset_id="c", actor=_actor(), root=demo_timeline["root"])
        move_clip("demo", "primary", clip_id="c", position=ClipPosition(mode="before", ref_clip_id="a"), actor=_actor(), root=demo_timeline["root"])
        retime_clip("demo", "primary", clip_id="b", start=2.0, duration=8.0, actor=_actor(), root=demo_timeline["root"])
        swap_clips("demo", "primary", clip_a_id="a", clip_b_id="b", actor=_actor(), root=demo_timeline["root"])
        replace_clip("demo", "primary", clip_id="a", with_asset_id="a_v2", actor=_actor(), root=demo_timeline["root"])
        set_clip_text("demo", "primary", clip_id="c", text="Caption", actor=_actor(), root=demo_timeline["root"])
        annotate_clip("demo", "primary", clip_id="b", note="Background music", actor=_actor(), root=demo_timeline["root"])
        remove_clip("demo", "primary", clip_id="a", actor=_actor(), root=demo_timeline["root"])

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tdir)
        events = backend.read_events()
        assert len(events) == 12
        assert backend.verify_chain().ok is True

        # Verify final assembly.json state
        assembly = _read_assembly_json(tdir)
        clips = assembly["clips"]
        assert len(clips) == 2  # a was removed
        clip_ids = {c["id"] for c in clips}
        assert clip_ids == {"b", "c"}
        for c in clips:
            if c["id"] == "b":
                assert c["at"] == 2.0
                assert c["hold"] == 8.0
                assert "params" not in c
            if c["id"] == "c":
                assert c["text"] == {"content": "Caption"}


# ── missing timeline error ──────────────────────────────────────────────────


class TestMissingTimeline:
    def test_add_clip_raises_for_nonexistent_timeline(self, project_tree: Path) -> None:
        with pytest.raises(ClipEditError, match="not found"):
            add_clip("demo", "nonexistent", kind="visual", asset_id="v1", root=project_tree)

    def test_missing_identity_sidecar(self, project_tree: Path) -> None:
        """If the identity sidecar is removed, add_clip cannot resolve the
        timeline via _resolve_backend and raises an error."""
        create_timeline("demo", "primary", root=project_tree)
        from astrid.core.timeline.paths import find_timeline_by_slug
        found = find_timeline_by_slug("demo", "primary", root=project_tree)
        assert found is not None
        ulid, tdir = found

        # Remove both identity and display so find_timeline_by_slug returns None
        (tdir / "assembly.identity.json").unlink()
        (tdir / "display.json").unlink()

        with pytest.raises(ClipEditError, match="not found"):
            add_clip("demo", "primary", kind="visual", asset_id="v1", root=project_tree)
