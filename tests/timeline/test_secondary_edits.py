"""Integration tests for secondary timeline edit primitives (m3).

Tests cover:
- LocalFs materialization and event-log behavior for all 15 secondary events.
- Assembly-shape edge cases for the secondary materializer domains.
- Supabase-selected paths that prove the provisional typed Supabase errors fail explicitly.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.timeline.audio_edits import audio_bind, audio_unbind
from astrid.core.timeline.clip_edits import add_clip
from astrid.core.timeline.crud import create_timeline
from astrid.core.timeline.effect_edits import effect_add, effect_remove, effect_tune
from astrid.core.timeline.eventlog import LocalFsBackend, SupabaseBackend
from astrid.core.timeline.eventlog.types import (
    EventLogMissingConfigError,
    EventLogUnsupportedRpcError,
)
from astrid.core.timeline.events.schema import (
    AudioBoundPayload,
    AudioUnboundPayload,
    EffectAddedPayload,
    EffectRemovedPayload,
    EffectTunedPayload,
    ThemeOverriddenPayload,
    ThemeSetPayload,
    TimelineActor,
    TimelineEvent,
    TrackAddedPayload,
    TrackRemovedPayload,
    TransitionRemovedPayload,
    TransitionSetPayload,
)
from astrid.core.timeline.paths import assembly_identity_path, timeline_dir
from astrid.core.timeline.pool_edits import pool_asset_add, pool_asset_remove, pool_asset_score
from astrid.core.timeline.theme_edits import theme_override, theme_set
from astrid.core.timeline.track_edits import track_add, track_remove
from astrid.core.timeline.transition_edits import (
    reconcile_adjacent_transitions,
    transition_remove,
    transition_set,
)
from astrid.core.timeline._edit_helpers import TimelineEditError


@pytest.fixture
def project_tree(tmp_projects_root: Path) -> Path:
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
def demo_timeline(project_tree: Path) -> dict[str, object]:
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


def _tdir(demo_timeline: dict[str, object]) -> Path:
    return timeline_dir("demo", str(demo_timeline["ulid"]), root=demo_timeline["root"])


def _timeline_id(demo_timeline: dict[str, object]) -> str:
    return str(demo_timeline["identity"]["timeline_id"])  # type: ignore[index]


def _read_assembly_json(tdir: Path) -> dict:
    return json.loads((tdir / "assembly.json").read_text(encoding="utf-8"))


def _backend(demo_timeline: dict[str, object]) -> LocalFsBackend:
    return LocalFsBackend(timeline_id=_timeline_id(demo_timeline), timeline_home=_tdir(demo_timeline))


def _seed_two_clips(demo_timeline: dict[str, object]) -> None:
    add_clip("demo", "primary", kind="visual", asset_id="clip-a", actor=_actor(), root=demo_timeline["root"])
    add_clip("demo", "primary", kind="visual", asset_id="clip-b", actor=_actor(), root=demo_timeline["root"])


def _assert_last_event(
    demo_timeline: dict[str, object],
    event: TimelineEvent,
    *,
    kind: str,
    payload_type: type,
) -> None:
    events = _backend(demo_timeline).read_events()
    assert events[-1].event_id == event.event_id
    assert events[-1].kind == kind
    assert events[-1].timeline_id == _timeline_id(demo_timeline)
    assert isinstance(events[-1].payload, payload_type)
    assert _backend(demo_timeline).verify_chain().ok is True


def test_transition_events_materialize_and_read_back(demo_timeline: dict[str, object]) -> None:
    _seed_two_clips(demo_timeline)
    tdir = _tdir(demo_timeline)

    set_event = transition_set(
        "demo",
        "primary",
        left_clip_id="clip-a",
        right_clip_id="clip-b",
        kind="cross-fade",
        duration_seconds=0.75,
        actor=_actor(),
        root=demo_timeline["root"],
    )
    assert set_event.kind == "transition.set"
    assert isinstance(set_event.payload, TransitionSetPayload)
    assert set_event.payload.duration_seconds == 0.75
    _assert_last_event(demo_timeline, set_event, kind="transition.set", payload_type=TransitionSetPayload)
    assembly = _read_assembly_json(tdir)
    assert assembly["clips"][0]["transition"] == {
        "type": "cross-fade",
        "duration": 0.75,
        "params": {"right_clip_id": "clip-b"},
    }

    remove_event = transition_remove(
        "demo",
        "primary",
        left_clip_id="clip-a",
        right_clip_id="clip-b",
        actor=_actor(),
        root=demo_timeline["root"],
    )
    assert remove_event.kind == "transition.removed"
    assert isinstance(remove_event.payload, TransitionRemovedPayload)
    _assert_last_event(demo_timeline, remove_event, kind="transition.removed", payload_type=TransitionRemovedPayload)
    assembly = _read_assembly_json(tdir)
    assert "transition" not in assembly["clips"][0]


def test_transition_set_on_nonexistent_clips_still_appends_event_and_keeps_assembly_stable(
    demo_timeline: dict[str, object],
) -> None:
    event = transition_set(
        "demo",
        "primary",
        left_clip_id="missing-left",
        right_clip_id="missing-right",
        actor=_actor(),
        root=demo_timeline["root"],
    )

    assert event.kind == "transition.set"
    _assert_last_event(demo_timeline, event, kind="transition.set", payload_type=TransitionSetPayload)
    assert _read_assembly_json(_tdir(demo_timeline))["clips"] == []


def test_transition_set_canonicalizes_registry_alias(
    demo_timeline: dict[str, object],
) -> None:
    _seed_two_clips(demo_timeline)

    event = transition_set(
        "demo",
        "primary",
        left_clip_id="clip-a",
        right_clip_id="clip-b",
        kind="crossfade",
        actor=_actor(),
        root=demo_timeline["root"],
    )

    assert event.payload.kind == "cross-fade"
    assembly = _read_assembly_json(_tdir(demo_timeline))
    assert assembly["clips"][0]["transition"]["type"] == "cross-fade"


# ---------------------------------------------------------------------------
# reconcile_adjacent_transitions tests (T10)
# ---------------------------------------------------------------------------


def _seed_four_clips_same_track(demo_timeline: dict[str, object]) -> None:
    """Add four visual clips (clip-a through clip-d) on the 'visual' track."""
    for asset_id in ("clip-a", "clip-b", "clip-c", "clip-d"):
        add_clip(
            "demo", "primary",
            kind="visual", asset_id=asset_id,
            actor=_actor(), root=demo_timeline["root"],
        )


def test_reconcile_adjacent_transitions_four_clips_produces_three_transitions(
    demo_timeline: dict[str, object],
) -> None:
    """A 4-clip same-track timeline produces exactly N-1 = 3 transitions."""
    _seed_four_clips_same_track(demo_timeline)
    tdir = _tdir(demo_timeline)

    events = reconcile_adjacent_transitions(
        "demo", "primary",
        root=demo_timeline["root"],
    )

    assert len(events) == 3, (
        f"expected 3 transition.set events for 4 same-track clips, got {len(events)}"
    )
    for event in events:
        assert event.kind == "transition.set"
        assert isinstance(event.payload, TransitionSetPayload)

    assembly = _read_assembly_json(tdir)
    clips = assembly["clips"]
    assert len(clips) == 4

    # Every clip except the last should carry a transition to the next clip.
    for i in range(3):
        left = clips[i]
        right = clips[i + 1]
        trans = left.get("transition")
        assert isinstance(trans, dict), f"clip[{i}] missing transition"
        assert trans.get("type") == "cross-fade"
        assert trans["params"]["right_clip_id"] == right["id"]


def test_reconcile_adjacent_transitions_is_idempotent(
    demo_timeline: dict[str, object],
) -> None:
    """Repeated reconciliation on an already-reconciled timeline produces
    zero new events (idempotent)."""
    _seed_four_clips_same_track(demo_timeline)

    first = reconcile_adjacent_transitions(
        "demo", "primary",
        root=demo_timeline["root"],
    )
    assert len(first) == 3

    second = reconcile_adjacent_transitions(
        "demo", "primary",
        root=demo_timeline["root"],
    )
    assert len(second) == 0, (
        f"second reconciliation should produce 0 events, got {len(second)}"
    )


def test_reconcile_adjacent_transitions_empty_timeline(
    demo_timeline: dict[str, object],
) -> None:
    """No clips on a timeline produces zero events."""
    events = reconcile_adjacent_transitions(
        "demo", "primary",
        root=demo_timeline["root"],
    )
    assert events == []


def test_reconcile_adjacent_transitions_single_clip(
    demo_timeline: dict[str, object],
) -> None:
    """A single-clip timeline has no adjacent pairs, produces zero events."""
    add_clip("demo", "primary", kind="visual", asset_id="only-clip",
             actor=_actor(), root=demo_timeline["root"])
    events = reconcile_adjacent_transitions(
        "demo", "primary",
        root=demo_timeline["root"],
    )
    assert events == []


def test_reconcile_adjacent_transitions_respects_existing_transitions(
    demo_timeline: dict[str, object],
) -> None:
    """When some adjacent pairs already have transitions, only missing ones
    are written."""
    _seed_four_clips_same_track(demo_timeline)

    # Manually set a transition on the first pair.
    transition_set(
        "demo", "primary",
        left_clip_id="clip-a",
        right_clip_id="clip-b",
        kind="cross-fade",
        actor=_actor(),
        root=demo_timeline["root"],
    )

    events = reconcile_adjacent_transitions(
        "demo", "primary",
        root=demo_timeline["root"],
    )
    # Only the 2 remaining pairs should get transitions (clip-b→clip-c, clip-c→clip-d).
    assert len(events) == 2

    # Verify the first pair's transition is still the original.
    assembly = _read_assembly_json(_tdir(demo_timeline))
    clip_a = assembly["clips"][0]
    assert clip_a["id"] == "clip-a"
    assert clip_a["transition"]["params"]["right_clip_id"] == "clip-b"


def test_reconcile_adjacent_transitions_multi_track(
    demo_timeline: dict[str, object],
) -> None:
    """Clips on different tracks are reconciled independently."""
    # Add two clips on the audio track.
    add_clip("demo", "primary", kind="audio", asset_id="audio-1",
             track_id="audio", actor=_actor(), root=demo_timeline["root"])
    add_clip("demo", "primary", kind="audio", asset_id="audio-2",
             track_id="audio", actor=_actor(), root=demo_timeline["root"])
    # Add three clips on the visual track.
    for asset_id in ("vis-1", "vis-2", "vis-3"):
        add_clip("demo", "primary", kind="visual", asset_id=asset_id,
                 actor=_actor(), root=demo_timeline["root"])

    events = reconcile_adjacent_transitions(
        "demo", "primary",
        root=demo_timeline["root"],
    )
    # audio: 1 pair (audio-1→audio-2), visual: 2 pairs (vis-1→vis-2, vis-2→vis-3)
    assert len(events) == 3

    assembly = _read_assembly_json(_tdir(demo_timeline))

    # Find clips by track.
    audio_clips = [c for c in assembly["clips"] if c.get("track") == "audio"]
    visual_clips = [c for c in assembly["clips"] if c.get("track") == "visual"]
    assert len(audio_clips) == 2
    assert len(visual_clips) == 3

    # Audio: first clip has transition to second.
    assert audio_clips[0]["transition"]["params"]["right_clip_id"] == audio_clips[1]["id"]
    # Visual: first→second, second→third.
    assert visual_clips[0]["transition"]["params"]["right_clip_id"] == visual_clips[1]["id"]
    assert visual_clips[1]["transition"]["params"]["right_clip_id"] == visual_clips[2]["id"]
    # Last clips on each track have no transition.
    assert "transition" not in audio_clips[1]
    assert "transition" not in visual_clips[2]


def test_reconcile_adjacent_transitions_custom_kind_and_duration(
    demo_timeline: dict[str, object],
) -> None:
    """Custom kind and duration are respected in emitted transitions."""
    _seed_two_clips(demo_timeline)

    events = reconcile_adjacent_transitions(
        "demo", "primary",
        kind="crossfade",  # alias, should canonicalize to cross-fade
        duration_seconds=1.5,
        root=demo_timeline["root"],
    )
    assert len(events) == 1
    event = events[0]
    assert event.payload.kind == "cross-fade"
    assert event.payload.duration_seconds == 1.5

    assembly = _read_assembly_json(_tdir(demo_timeline))
    transition = assembly["clips"][0]["transition"]
    assert transition["type"] == "cross-fade"
    assert transition["duration"] == 1.5


def test_reconcile_adjacent_transitions_is_kernel_helper_no_cli(
    demo_timeline: dict[str, object],
) -> None:
    """Prove the helper is a kernel-level function with no CLI surface.
    It does not touch argparse and is importable without the CLI module."""
    import inspect

    source = inspect.getsource(reconcile_adjacent_transitions)
    # The helper must not reference argparse.
    assert "argparse" not in source, (
        "reconcile_adjacent_transitions must not be a CLI command"
    )
    # The helper must read from projected assembly (calls show_timeline or reads assembly).
    assert "show_timeline" in source or "assembly" in source


def test_effect_events_materialize_and_read_back(demo_timeline: dict[str, object]) -> None:
    add_clip("demo", "primary", kind="visual", asset_id="clip-a", actor=_actor(), root=demo_timeline["root"])
    tdir = _tdir(demo_timeline)

    add_event = effect_add(
        "demo",
        "primary",
        clip_id="clip-a",
        effect_id="text-card",
        params={"opacity": 0.6},
        actor=_actor(),
        root=demo_timeline["root"],
    )
    assert add_event.kind == "effect.added"
    assert isinstance(add_event.payload, EffectAddedPayload)
    assert add_event.payload.params == {"opacity": 0.6}
    _assert_last_event(demo_timeline, add_event, kind="effect.added", payload_type=EffectAddedPayload)
    assembly = _read_assembly_json(tdir)
    assert assembly["clips"][0]["params"]["effects"]["text-card"] == {"opacity": 0.6}

    tune_event = effect_tune(
        "demo",
        "primary",
        clip_id="clip-a",
        effect_id="text-card",
        param="opacity",
        value=0.9,
        actor=_actor(),
        root=demo_timeline["root"],
    )
    assert tune_event.kind == "effect.tuned"
    assert isinstance(tune_event.payload, EffectTunedPayload)
    assert tune_event.payload.value == 0.9
    _assert_last_event(demo_timeline, tune_event, kind="effect.tuned", payload_type=EffectTunedPayload)
    assembly = _read_assembly_json(tdir)
    assert assembly["clips"][0]["params"]["effects"]["text-card"]["opacity"] == 0.9

    remove_event = effect_remove(
        "demo",
        "primary",
        clip_id="clip-a",
        effect_id="text-card",
        actor=_actor(),
        root=demo_timeline["root"],
    )
    assert remove_event.kind == "effect.removed"
    assert isinstance(remove_event.payload, EffectRemovedPayload)
    _assert_last_event(demo_timeline, remove_event, kind="effect.removed", payload_type=EffectRemovedPayload)
    assembly = _read_assembly_json(tdir)
    assert "text-card" not in assembly["clips"][0]["params"].get("effects", {})


def test_effect_add_to_nonexistent_clip_still_appends_event_and_keeps_assembly_stable(
    demo_timeline: dict[str, object],
) -> None:
    event = effect_add(
        "demo",
        "primary",
        clip_id="missing",
        effect_id="glow",
        params={"strength": 1},
        actor=_actor(),
        root=demo_timeline["root"],
    )

    assert event.kind == "effect.added"
    _assert_last_event(demo_timeline, event, kind="effect.added", payload_type=EffectAddedPayload)
    assert _read_assembly_json(_tdir(demo_timeline))["clips"] == []


def test_theme_events_materialize_and_read_back(demo_timeline: dict[str, object]) -> None:
    tdir = _tdir(demo_timeline)

    set_event = theme_set(
        "demo",
        "primary",
        theme_id="banodoco-default",
        actor=_actor(),
        root=demo_timeline["root"],
    )
    assert set_event.kind == "theme.set"
    assert isinstance(set_event.payload, ThemeSetPayload)
    _assert_last_event(demo_timeline, set_event, kind="theme.set", payload_type=ThemeSetPayload)
    assembly = _read_assembly_json(tdir)
    assert assembly["theme"] == "banodoco-default"
    assert assembly["theme_overrides"] == {}

    override_event = theme_override(
        "demo",
        "primary",
        override_id="visual",
        value={"canvas": {"fps": 24}},
        actor=_actor(),
        root=demo_timeline["root"],
    )
    assert override_event.kind == "theme.overridden"
    assert isinstance(override_event.payload, ThemeOverriddenPayload)
    _assert_last_event(demo_timeline, override_event, kind="theme.overridden", payload_type=ThemeOverriddenPayload)
    assembly = _read_assembly_json(tdir)
    assert assembly["theme_overrides"]["visual"] == {"canvas": {"fps": 24}}


def test_theme_override_rejects_invalid_namespace(demo_timeline: dict[str, object]) -> None:
    with pytest.raises(TimelineEditError, match="override_id must be one of"):
        theme_override(
            "demo",
            "primary",
            override_id="invalid",
            value={"x": 1},
            actor=_actor(),
            root=demo_timeline["root"],
        )


def test_track_events_materialize_and_read_back(demo_timeline: dict[str, object]) -> None:
    tdir = _tdir(demo_timeline)

    add_event = track_add(
        "demo",
        "primary",
        track_id="track-v1",
        kind="visual",
        label="Main",
        actor=_actor(),
        root=demo_timeline["root"],
    )
    assert add_event.kind == "track.added"
    assert isinstance(add_event.payload, TrackAddedPayload)
    _assert_last_event(demo_timeline, add_event, kind="track.added", payload_type=TrackAddedPayload)
    assembly = _read_assembly_json(tdir)
    assert {"id": "track-v1", "kind": "visual", "label": "Main"} in assembly["tracks"]

    remove_event = track_remove(
        "demo",
        "primary",
        track_id="track-v1",
        actor=_actor(),
        root=demo_timeline["root"],
    )
    assert remove_event.kind == "track.removed"
    assert isinstance(remove_event.payload, TrackRemovedPayload)
    _assert_last_event(demo_timeline, remove_event, kind="track.removed", payload_type=TrackRemovedPayload)
    assembly = _read_assembly_json(tdir)
    assert {"id": "track-v1", "kind": "visual", "label": "Main"} not in assembly["tracks"]


def test_audio_events_materialize_and_read_back(demo_timeline: dict[str, object]) -> None:
    add_clip("demo", "primary", kind="audio", asset_id="clip-a", actor=_actor(), root=demo_timeline["root"])
    tdir = _tdir(demo_timeline)

    bind_event = audio_bind(
        "demo",
        "primary",
        clip_id="clip-a",
        asset_id="asset-audio-2",
        actor=_actor(),
        root=demo_timeline["root"],
    )
    assert bind_event.kind == "audio.bound"
    assert isinstance(bind_event.payload, AudioBoundPayload)
    _assert_last_event(demo_timeline, bind_event, kind="audio.bound", payload_type=AudioBoundPayload)
    assembly = _read_assembly_json(tdir)
    assert assembly["clips"][0]["asset"] == "asset-audio-2"

    unbind_event = audio_unbind(
        "demo",
        "primary",
        clip_id="clip-a",
        actor=_actor(),
        root=demo_timeline["root"],
    )
    assert unbind_event.kind == "audio.unbound"
    assert isinstance(unbind_event.payload, AudioUnboundPayload)
    _assert_last_event(demo_timeline, unbind_event, kind="audio.unbound", payload_type=AudioUnboundPayload)
    assembly = _read_assembly_json(tdir)
    assert "asset" not in assembly["clips"][0]


def test_pool_events_reject_runtime_edit_paths(demo_timeline: dict[str, object]) -> None:
    with pytest.raises(TimelineEditError, match="non-container read-model"):
        pool_asset_add(
            "demo",
            "primary",
            asset_id="asset-1",
            actor=_actor(),
            root=demo_timeline["root"],
        )

    with pytest.raises(TimelineEditError, match="non-container read-model"):
        pool_asset_score(
            "demo",
            "primary",
            asset_id="asset-1",
            score=0.9,
            actor=_actor(),
            root=demo_timeline["root"],
        )

    with pytest.raises(TimelineEditError, match="non-container read-model"):
        pool_asset_remove(
            "demo",
            "primary",
            asset_id="asset-1",
            actor=_actor(),
            root=demo_timeline["root"],
        )


def test_pool_score_rejects_out_of_range(demo_timeline: dict[str, object]) -> None:
    with pytest.raises(TimelineEditError, match="score must be between 0 and 1"):
        pool_asset_score(
            "demo",
            "primary",
            asset_id="asset-1",
            score=1.5,
            actor=_actor(),
            root=demo_timeline["root"],
        )


def test_secondary_supabase_paths_raise_missing_config_explicitly(
    demo_timeline: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_select(*, timeline_id, timeline_home=None, preferred_backend=None):
        return (
            SimpleNamespace(backend="supabase", source="preferred_backend"),
            SupabaseBackend(timeline_id=timeline_id),
        )

    monkeypatch.setattr("astrid.core.timeline._edit_helpers.select_timeline_backend", fake_select)

    ops = [
        lambda: transition_set("demo", "primary", left_clip_id="a", right_clip_id="b", actor=_actor(), root=demo_timeline["root"]),
        lambda: effect_add("demo", "primary", clip_id="a", effect_id="glow", actor=_actor(), root=demo_timeline["root"]),
        lambda: theme_set("demo", "primary", theme_id="banodoco-default", actor=_actor(), root=demo_timeline["root"]),
        lambda: track_add("demo", "primary", track_id="track-1", kind="visual", label="Main", actor=_actor(), root=demo_timeline["root"]),
        lambda: audio_bind("demo", "primary", clip_id="a", asset_id="asset-1", actor=_actor(), root=demo_timeline["root"]),
    ]

    for op in ops:
        with pytest.raises(EventLogMissingConfigError, match="SupabaseBackend"):
            op()


def test_secondary_supabase_paths_raise_unsupported_rpc_when_configured(
    demo_timeline: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
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
        theme_set("demo", "primary", theme_id="banodoco-default", actor=_actor(), root=demo_timeline["root"])
