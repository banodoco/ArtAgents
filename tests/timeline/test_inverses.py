"""Table-driven tests for inverse planning (T9).

Covers every m2/m3 reversible event kind listed in the milestone brief:
clips, effects, tracks, audio bindings, transitions, theme values,
annotations, pool metadata, scores.

Also covers non-reversible cases and erased payload handling.
"""

from __future__ import annotations

import pytest

from astrid.core.timeline.events.schema import (
    ArrangementReplacedPayload,
    AudioBoundPayload,
    AudioUnboundPayload,
    ClipAddedPayload,
    ClipAnnotatedPayload,
    ClipMovedPayload,
    ClipPosition,
    ClipRemovedPayload,
    ClipReplacedPayload,
    ClipRetimedPayload,
    ClipSwappedPayload,
    ClipTextSetPayload,
    EffectAddedPayload,
    EffectRemovedPayload,
    EffectTunedPayload,
    ErasedPayload,
    PoolAssetAddedPayload,
    PoolAssetRemovedPayload,
    PoolAssetScoredPayload,
    ThemeOverriddenPayload,
    ThemeSetPayload,
    TimelineActor,
    TimelineEvent,
    TrackAddedPayload,
    TrackRemovedPayload,
    TransitionRemovedPayload,
    TransitionSetPayload,
)
from astrid.core.timeline.inverses import (
    InverseRequest,
    plan_inverse,
    plan_inverses,
)

_ACTOR = TimelineActor(type="agent", id="inverse-test")


def _make_event(kind: str, payload: object) -> TimelineEvent:
    """Build a minimal event for testing."""
    return TimelineEvent.new(
        timeline_id="00000000-0000-0000-0000-000000000001",
        ts="2026-05-21T00:00:00Z",
        actor=_ACTOR,
        kind=kind,  # type: ignore[arg-type]
        payload=payload,  # type: ignore[arg-type]
    )


# ============================================================================
# Table-driven tests: every m2/m3 reversible event kind
# ============================================================================


@pytest.mark.parametrize(
    "kind, payload, before_state, after_state, expected_inverse_kind",
    [
        # clip.added → clip.removed
        (
            "clip.added",
            ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
            {"clips": []},
            {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1"}]},
            "clip.removed",
        ),
        # clip.removed → clip.added (recovers from prior state)
        (
            "clip.removed",
            ClipRemovedPayload(clip_id="c1"),
            {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1"}]},
            {"clips": []},
            "clip.added",
        ),
        # clip.moved → clip.moved back to original position
        (
            "clip.moved",
            ClipMovedPayload(clip_id="c1", position=ClipPosition(mode="index", index=5)),
            {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1"}]},
            {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1"}]},
            "clip.moved",
        ),
        # clip.retimed → clip.retimed with original values
        (
            "clip.retimed",
            ClipRetimedPayload(clip_id="c1", start=10.0, duration=5.0),
            {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1", "start": 0.0, "duration": 3.0}]},
            {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1", "start": 10.0, "duration": 5.0}]},
            "clip.retimed",
        ),
        # clip.swapped → clip.swapped back
        (
            "clip.swapped",
            ClipSwappedPayload(clip_a_id="c1", clip_b_id="c2"),
            {"clips": [{"id": "c1"}, {"id": "c2"}]},
            {"clips": [{"id": "c2"}, {"id": "c1"}]},
            "clip.swapped",
        ),
        # clip.replaced → clip.replaced with original asset
        (
            "clip.replaced",
            ClipReplacedPayload(clip_id="c1", with_asset_id="new_a1"),
            {"clips": [{"id": "c1", "asset_id": "old_a1"}]},
            {"clips": [{"id": "c1", "asset_id": "new_a1"}]},
            "clip.replaced",
        ),
        # clip.text_set → clip.text_set with original text
        (
            "clip.text_set",
            ClipTextSetPayload(clip_id="c1", text="new text"),
            {"clips": [{"id": "c1", "text": "old text"}]},
            {"clips": [{"id": "c1", "text": "new text"}]},
            "clip.text_set",
        ),
        # clip.annotated → clip.annotated with original note
        (
            "clip.annotated",
            ClipAnnotatedPayload(clip_id="c1", note="new note"),
            {"clips": [{"id": "c1", "note": "old note"}]},
            {"clips": [{"id": "c1", "note": "new note"}]},
            "clip.annotated",
        ),
        # transition.set → transition.removed
        (
            "transition.set",
            TransitionSetPayload(left_clip_id="c1", right_clip_id="c2", kind="dissolve", duration_seconds=1.0),
            {"clips": []},
            {"clips": [{"id": "c1", "transition": {"kind": "dissolve", "right_clip_id": "c2", "duration_seconds": 1.0}}]},
            "transition.removed",
        ),
        # transition.removed → transition.set (from prior state)
        (
            "transition.removed",
            TransitionRemovedPayload(left_clip_id="c1", right_clip_id="c2"),
            {"clips": [{"id": "c1", "transition": {"kind": "dissolve", "right_clip_id": "c2", "duration_seconds": 1.0}}]},
            {"clips": [{"id": "c1"}]},
            "transition.set",
        ),
        # effect.added → effect.removed
        (
            "effect.added",
            EffectAddedPayload(clip_id="c1", effect_id="blur"),
            {"clips": []},
            {"clips": [{"id": "c1", "effects": [{"effect_id": "blur"}]}]},
            "effect.removed",
        ),
        # effect.removed → effect.added (from prior state)
        (
            "effect.removed",
            EffectRemovedPayload(clip_id="c1", effect_id="blur"),
            {"clips": [{"id": "c1", "effects": [{"effect_id": "blur", "params": {"radius": 5}}]}]},
            {"clips": [{"id": "c1", "effects": []}]},
            "effect.added",
        ),
        # effect.tuned → effect.tuned with original value
        (
            "effect.tuned",
            EffectTunedPayload(clip_id="c1", effect_id="blur", param="radius", value=10),
            {"clips": [{"id": "c1", "effects": [{"effect_id": "blur", "params": {"radius": 5}}]}]},
            {"clips": [{"id": "c1", "effects": [{"effect_id": "blur", "params": {"radius": 10}}]}]},
            "effect.tuned",
        ),
        # track.added → track.removed
        (
            "track.added",
            TrackAddedPayload(track_id="t1", kind="visual"),
            {"tracks": []},
            {"tracks": [{"id": "t1", "kind": "visual"}]},
            "track.removed",
        ),
        # track.removed → track.added (from prior state)
        (
            "track.removed",
            TrackRemovedPayload(track_id="t1"),
            {"tracks": [{"id": "t1", "kind": "audio", "label": "music"}]},
            {"tracks": []},
            "track.added",
        ),
        # audio.bound → audio.unbound
        (
            "audio.bound",
            AudioBoundPayload(clip_id="c1", asset_id="song.mp3"),
            {"clips": []},
            {"clips": [{"id": "c1", "asset_id": "song.mp3"}]},
            "audio.unbound",
        ),
        # audio.unbound → audio.bound (from prior state)
        (
            "audio.unbound",
            AudioUnboundPayload(clip_id="c1"),
            {"clips": [{"id": "c1", "asset_id": "song.mp3"}]},
            {"clips": [{"id": "c1", "asset_id": ""}]},
            "audio.bound",
        ),
        # theme.set → theme.set with previous theme
        (
            "theme.set",
            ThemeSetPayload(theme_id="dark"),
            {"theme": "light", "theme_overrides": {}},
            {"theme": "dark", "theme_overrides": {}},
            "theme.set",
        ),
        # theme.overridden → theme.overridden with original value
        (
            "theme.overridden",
            ThemeOverriddenPayload(override_id="color.primary", value="#000"),
            {"theme": "dark", "theme_overrides": {"color.primary": "#fff"}},
            {"theme": "dark", "theme_overrides": {"color.primary": "#000"}},
            "theme.overridden",
        ),
        # pool.asset_added → pool.asset_removed
        (
            "pool.asset_added",
            PoolAssetAddedPayload(asset_id="img1.png"),
            {"pool": {"entries": []}},
            {"pool": {"entries": [{"asset_id": "img1.png", "score": 0.0}]}},
            "pool.asset_removed",
        ),
        # pool.asset_removed → pool.asset_added (from prior state)
        (
            "pool.asset_removed",
            PoolAssetRemovedPayload(asset_id="img1.png"),
            {"pool": {"entries": [{"asset_id": "img1.png", "score": 0.5}]}},
            {"pool": {"entries": []}},
            "pool.asset_added",
        ),
        # pool.asset_scored → pool.asset_scored with original score
        (
            "pool.asset_scored",
            PoolAssetScoredPayload(asset_id="img1.png", score=0.9),
            {"pool": {"entries": [{"asset_id": "img1.png", "score": 0.5}]}},
            {"pool": {"entries": [{"asset_id": "img1.png", "score": 0.9}]}},
            "pool.asset_scored",
        ),
        # arrangement.replaced → arrangement.replaced with prior arrangement
        (
            "arrangement.replaced",
            ArrangementReplacedPayload(arrangement={"clips": [{"id": "c2"}]}),
            {"arrangement": {"clips": [{"id": "c1"}]}},
            {"arrangement": {"clips": [{"id": "c2"}]}},
            "arrangement.replaced",
        ),
    ],
)
def test_reversible_event_kind(
    kind, payload, before_state, after_state, expected_inverse_kind
):
    """Every m2/m3 reversible event kind produces a mechanical inverse."""
    event = _make_event(kind, payload)
    result = plan_inverse(
        event,
        before_projection=before_state,
        after_projection=after_state,
    )
    assert result.invertible is True, (
        f"{kind} should be invertible, got: {result.revert_reason}"
    )
    assert result.inverse_kind == expected_inverse_kind, (
        f"{kind} inverse should be {expected_inverse_kind}, got {result.inverse_kind}"
    )
    assert result.inverse_payload is not None


# ============================================================================
# Non-reversible event kinds
# ============================================================================


@pytest.mark.parametrize(
    "kind, payload",
    [
        ("timeline.created", {"timeline_id": "00000000-0000-0000-0000-000000000001", "slug": "test", "name": "Test"}),
        ("timeline.imported", {"snapshot": {}, "source": "legacy_local"}),
        ("timeline.deleted", {}),
        ("timeline.tombstoned", {"reason": "test"}),
        ("timeline.erased", {"selector_summary": {}, "reason": "test", "affected_count": 1}),
        ("timeline.recovered", {"anchor_event_id": "01J00000000000000000000001", "anchor_type": "event", "reason": "test"}),
        ("timeline.branched_from", {"branch_timeline_id": "00000000-0000-0000-0000-000000000002", "anchor_event_id": "01J00000000000000000000001"}),
        ("timeline.reverted", {"target_event_id": "01J00000000000000000000001", "reason": "test"}),
    ],
)
def test_non_reversible_event_kinds(kind, payload):
    """Non-reversible kinds fall back to timeline.reverted with before/after projections."""
    event = _make_event(kind, payload)
    before = {"clips": [{"id": "c1"}]}
    after = {"clips": []}

    result = plan_inverse(
        event,
        before_projection=before,
        after_projection=after,
    )

    assert result.invertible is False, f"{kind} should NOT be invertible"
    assert result.revert_kind == "timeline.reverted"
    assert result.before_projection is not None
    assert result.after_projection is not None
    # Should include the event_id in the reason
    assert event.event_id in result.revert_reason


# ============================================================================
# Erased payload handling
# ============================================================================


def test_erased_payload_non_invertible():
    """Events with ErasedPayload are treated as non-invertible."""
    erased = ErasedPayload(
        erased=True,
        reason="policy",
        erased_at="2026-05-21T00:00:00Z",
        erased_by="admin",
    )
    event = _make_event("clip.added", erased)

    result = plan_inverse(event)
    assert result.invertible is False
    assert result.revert_kind == "timeline.reverted"
    assert "erased" in result.revert_reason.lower()


def test_erased_payload_does_not_expose_content():
    """Erased payload inversion does not expose erased content in projections."""
    erased = ErasedPayload(
        erased=True,
        reason="policy",
        erased_at="2026-05-21T00:00:00Z",
        erased_by="admin",
    )
    event = _make_event("clip.removed", erased)

    before = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "secret.mp4"}]}
    after = {"clips": []}

    result = plan_inverse(
        event,
        before_projection=before,
        after_projection=after,
    )

    # Should be non-invertible even though before state has the clip
    assert result.invertible is False
    assert "erased" in result.revert_reason.lower()


# ============================================================================
# plan_inverses: walking events with before/after projections
# ============================================================================


def test_plan_inverses_walk_sequence():
    """plan_inverses walks a sequence and produces one inverse per event."""
    e1 = _make_event(
        "clip.added",
        ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
    )
    e2 = _make_event(
        "track.added",
        TrackAddedPayload(track_id="t1", kind="visual"),
    )
    e3 = _make_event(
        "pool.asset_added",
        PoolAssetAddedPayload(asset_id="img1.png"),
    )

    results = plan_inverses([e1, e2, e3])

    assert len(results) == 3
    # All should be invertible
    for r in results:
        assert r.invertible is True

    assert results[0].inverse_kind == "clip.removed"
    assert results[1].inverse_kind == "track.removed"
    assert results[2].inverse_kind == "pool.asset_removed"


def test_plan_inverses_mixed_reversible_non_reversible():
    """plan_inverses handles mixed reversible and non-reversible events."""
    e1 = _make_event(
        "clip.added",
        ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
    )
    e2 = _make_event("timeline.deleted", {})

    results = plan_inverses([e1, e2])

    assert len(results) == 2
    assert results[0].invertible is True  # clip.added → clip.removed
    assert results[1].invertible is False  # timeline.deleted → timeline.reverted


def test_plan_inverses_with_erased_event():
    """plan_inverses handles erased events in sequence."""
    e1 = _make_event(
        "clip.added",
        ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
    )
    erased = ErasedPayload(
        erased=True,
        reason="policy",
        erased_at="2026-05-21T00:00:00Z",
        erased_by="admin",
    )
    e2 = _make_event("clip.moved", erased)

    results = plan_inverses([e1, e2])

    assert len(results) == 2
    assert results[0].invertible is True
    assert results[1].invertible is False


# ============================================================================
# Pure function property
# ============================================================================


def test_plan_inverse_is_pure():
    """plan_inverse is a pure function — same inputs, same outputs."""
    event = _make_event(
        "clip.added",
        ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
    )
    before = {"clips": []}
    after = {"clips": [{"id": "c1"}]}

    r1 = plan_inverse(event, before_projection=before, after_projection=after)
    r2 = plan_inverse(event, before_projection=before, after_projection=after)

    assert r1.invertible == r2.invertible
    assert r1.inverse_kind == r2.inverse_kind
    assert r1.inverse_payload == r2.inverse_payload


def test_plan_inverses_is_pure():
    """plan_inverses is a pure function — same inputs, same outputs."""
    e1 = _make_event(
        "clip.added",
        ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
    )
    e2 = _make_event(
        "track.added",
        TrackAddedPayload(track_id="t1", kind="visual"),
    )

    r1 = plan_inverses([e1, e2])
    r2 = plan_inverses([e1, e2])

    assert len(r1) == len(r2)
    for a, b in zip(r1, r2):
        assert a.invertible == b.invertible
        assert a.inverse_kind == b.inverse_kind
        assert a.inverse_payload == b.inverse_payload
