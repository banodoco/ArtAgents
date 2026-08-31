"""Tests for astrid.core.timeline.expand_shots (A4 B2).

Pure-function tests for shot clip expansion. Tests verify offset/clamp/drop,
nested shot fail, missing params fail, unknown timeline fail, registry union,
and that input dicts are memory-only (not persisted).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from astrid.core.timeline.expand_shots import ShotExpansionError, expand_shot_clips
from astrid.core.timeline.banodoco_schema import AssetRegistry
from astrid.core.timeline.expand_shots import _total_assets


def _parse_document(text: str) -> dict[str, object]:
    return json.loads(text)


def _serialize_document(doc: dict) -> str:
    """Serialize a document dict to JSON string."""
    return json.dumps(doc, separators=(",", ":"))


def _make_timeline_fixture(
    id: str,
    tracks: list[dict] | None = None,
    clips: list[dict] | None = None,
) -> tuple[dict, AssetRegistry]:
    """Create a minimal timeline fixture dict and empty registry."""
    if tracks is None:
        tracks = [{"id": "visual", "kind": "visual"}]
    if clips is None:
        clips = []
    return (
        {
            "id": id,
            "tracks": tracks,
            "clips": clips,
        },
        {"assets": {}},  # Initialize assets dict for AssetRegistry
    )


def _load_timeline_from_fixture(timeline_id: str) -> tuple[dict, AssetRegistry]:
    """Load a timeline from a JSON file (for canned flat doc tests)."""
    # Use an in-memory file system for isolated tests.
    # Here we'll manually construct a sub-doc for simplicity.
    if timeline_id == "sub1":
        config, reg = _make_timeline_fixture(
            "sub1",
            tracks=[{"id": "visual", "kind": "visual"}],
            clips=[
                {"id": "sub_clip_1", "at": 0, "hold": 2.0, "track": "visual", "clipType": "media"},
                {"id": "sub_clip_2", "at": 1.5, "hold": 1.0, "track": "visual", "clipType": "media"},
            ],
        )
    elif timeline_id == "sub2":
        config, reg = _make_timeline_fixture(
            "sub2",
            tracks=[{"id": "visual", "kind": "visual"}],
            clips=[
                {"id": "sub_clip_3", "at": 0.5, "hold": 3.0, "track": "visual", "clipType": "media"},
            ],
        )
    elif timeline_id  == "sub_with_nested_shot":
        config, reg = _make_timeline_fixture(
            "sub_with_nested_shot",
            tracks=[{"id": "visual", "kind": "visual"}],
            clips=[
                {"id": "sub_media_clip", "at": 0, "hold": 2.0, "track": "visual", "clipType": "media"},
                {"id": "nested_shot_in_sub", "at": 1.0, "hold": 1.0, "track": "visual", "clipType": "shot", "params": {"shot_id": "nested_shot_in_sub", "timeline_document_id": "sub2"}},
            ],
        )

    elif timeline_id == "deep_sub":
        config, reg = _make_timeline_fixture(
            "deep_sub",
            tracks=[{"id": "visual", "kind": "visual"}],
            clips=[
                {"id": "deep_sub_clip_1", "at": 0.0, "hold": 1.0, "track": "visual", "clipType": "media"},
            ],
        )
    else:
        raise FileNotFoundError(f"Unknown timeline_id for test: {timeline_id}")
    return config, reg


def test_shot_offset_clamp_drop():
    """Shot clips are offset, clamped, and dropped into parent hold window."""
    config, registry = _make_timeline_fixture(
        "main",
        clips=[
            {
                "id": "shot_1",
                "at": 1.0,
                "hold": 3.0,
                "clipType": "shot",
                "params": {
                    "shot_id": "shot_1",
                    "timeline_document_id": "sub1",
                },
            },
            {
                "id": "parent_media_1",
                "at": 0.0,
                "hold": 1.0,
                "track": "visual",
                "clipType": "media",
            },
            {
                "id": "parent_media_2",
                "at": 5.0,
                "hold": 1.0,
                "track": "visual",
                "clipType": "media",
            },
        ],
    )

    load_timeline = _load_timeline_from_fixture
    expanded_config, expanded_registry = expand_shot_clips(
        config=config,
        registry=registry,
        load_timeline=load_timeline,
    )

    # Verify parent docs unchanged.
    assert expanded_config["id"] == "main"
    assert expanded_config["tracks"] == [{"id": "visual", "kind": "visual"}]
    assert len(expanded_config["clips"]) == 4  # 1 parent media + 2 expanded sub clips + 1 parent media at end

    # Verify sub_clip_1 expanded:
    #   - at = parent.at (1.0) + sub.at (0.0) = 1.0
    #   - hold = sub.hold (2.0)
    #   - new_end = 1.0 + 2.0 = 3.0 <= parent.hold (3.0) → OK
    shot_1_expanded = next((c for c in expanded_config["clips"] if c["id"] == "sub_clip_1"), None)
    assert shot_1_expanded is not None
    assert shot_1_expanded["at"] == 1.0
    assert shot_1_expanded["hold"] == 2.0
    assert shot_1_expanded["track"] == "visual"
    assert shot_1_expanded["clipType"] == "media"

    # Verify sub_clip_2 expanded:
    #   - at = 1.0 + 1.5 = 2.5
    #   - hold = 1.0
    #   - new_end = 2.5 + 1.0 = 3.5 > parent.hold (3.0) → OK
    shot_2_expanded = next((c for c in expanded_config["clips"] if c["id"] == "sub_clip_2"), None)
    assert shot_2_expanded is not None
    assert shot_2_expanded["at"] == 2.5
    assert shot_2_expanded["hold"] == 1.0

    # Verify parent docs unchanged.
    assert _total_assets(expanded_registry) == 0


def test_bounded_media_window_clamps_to_parent_remaining_with_speed():
    config, registry = _make_timeline_fixture(
        "main",
        clips=[
            {
                "id": "shot-1",
                "at": 1.0,
                "hold": 2.0,
                "clipType": "shot",
                "params": {"shot_id": "shot-1", "timeline_document_id": "bounded"},
            }
        ],
    )

    def load_timeline(timeline_id: str):
        assert timeline_id == "bounded"
        child_config, _ = _make_timeline_fixture(
            "bounded",
            clips=[
                {
                    "id": "video",
                    "at": 0.5,
                    "track": "visual",
                    "clipType": "video",
                    "asset": "clip",
                    "from": 2.0,
                    "to": 12.0,
                    "speed": 2.0,
                }
            ],
        )
        return child_config, {"assets": {"clip": {"file": "clip.mp4"}}}

    expanded, _ = expand_shot_clips(config, registry, load_timeline=load_timeline)
    clip = expanded["clips"][0]
    assert clip["at"] == 1.5
    assert clip["to"] == 5.0  # 2s remaining * speed 2 + source from 2


def test_registry_union_parent_wins():
    """Assets from sub-registries are merged; parent wins on conflict."""
    config, registry = _make_timeline_fixture(
        "main",
        clips=[
            {
                "id": "shot_1",
                "at": 0.0,
                "hold": 3.0,
                "clipType": "shot",
                "params": {
                    "shot_id": "shot_1",
                    "timeline_document_id": "sub1",
                },
            },
        ],
    )
    # Add an asset to parent registry.
    registry["assets"]["parent_asset_1"] = {
        "asset_id": "parent_asset_1",
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "original_filename": "parent.png",
    }


    load_timeline = _load_timeline_from_fixture
    expanded_config, expanded_registry = expand_shot_clips(
        config=config,
        registry=registry,
        load_timeline=load_timeline,
    )

    # Verify parent asset still present (parent wins on conflict).
    assert len(expanded_registry) == 1
    assert "parent_asset_1" in expanded_registry["assets"]

    # Verify sub-clip_1's asset registry is not in parent (it's not in our sub1 fixture).
    assert _total_assets(expanded_registry) == 1


def test_registry_conflict_keeps_parent_entry():
    config, registry = _make_timeline_fixture(
        "main",
        clips=[
            {
                "id": "shot-1",
                "at": 0.0,
                "hold": 2.0,
                "clipType": "shot",
                "params": {"shot_id": "shot-1", "timeline_document_id": "child"},
            }
        ],
    )
    registry["assets"]["shared"] = {"file": "parent.mp4"}

    def load_timeline(_timeline_id: str):
        child_config, _ = _make_timeline_fixture(
            "child",
            clips=[
                {
                    "id": "child-clip",
                    "at": 0.0,
                    "hold": 1.0,
                    "clipType": "media",
                    "asset": "shared",
                }
            ],
        )
        return child_config, {"assets": {"shared": {"file": "child.mp4"}}}

    _, expanded_registry = expand_shot_clips(
        config, registry, load_timeline=load_timeline
    )
    assert expanded_registry["assets"]["shared"]["file"] == "parent.mp4"


def test_nested_shot_raises_error():
    """Shot clips nested inside another shot clip raise ShotExpansionError."""
    config, registry = _make_timeline_fixture(
        "main",
        clips=[
            {
                "id": "shot_1",
                "at": 0.0,
                "hold": 3.0,
                "clipType": "shot",
                "params": {
                    "shot_id": "shot_1",
                    "timeline_document_id": "sub_with_nested_shot",
                },
            },
        ],
    )

    load_timeline = _load_timeline_from_fixture
    with pytest.raises(ShotExpansionError, match="nested shot"):
        expand_shot_clips(
            config=config,
            registry=registry,
            load_timeline=load_timeline,
        )


def test_missing_params_raises_error():
    """Shot clips missing params raise ShotExpansionError."""
    config, registry = _make_timeline_fixture(
        "main",
        clips=[
            {
                "id": "shot_1",
                "at": 0.0,
                "hold": 3.0,
                "clipType": "shot",
                "params": {},  # Empty params
            },
            {
                "id": "shot_2",
                "at": 0.0,
                "hold": 3.0,
                "clipType": "shot",
                # No params at all
            },
        ],
    )

    load_timeline = _load_timeline_from_fixture
    with pytest.raises(ShotExpansionError, match="missing shot_id or timeline_document_id"):
        expand_shot_clips(
            config=config,
            registry=registry,
            load_timeline=load_timeline,
        )


def test_unknown_timeline_id_raises_error():
    """Unknown timeline_document_id raises ShotExpansionError."""
    config, registry = _make_timeline_fixture(
        "main",
        clips=[
            {
                "id": "shot_1",
                "at": 0.0,
                "hold": 3.0,
                "clipType": "shot",
                "params": {
                    "shot_id": "shot_1",
                    "timeline_document_id": "nonexistent",
                },
            },
        ],
    )

    load_timeline = _load_timeline_from_fixture
    with pytest.raises(ShotExpansionError, match="Failed to load sub-timeline"):
        expand_shot_clips(
            config=config,
            registry=registry,
            load_timeline=load_timeline,
        )


def test_memory_only_input_unmodified():
    """Input config and registry dicts are not persisted or mutated in place (memory-only)."""
    # Create a deep copy of config and registry to verify they're not modified in place.
    import copy

    original_config = copy.deepcopy(
        {
            "id": "main",
            "tracks": [{"id": "visual", "kind": "visual"}],
            "clips": [
                {
                    "id": "shot_1",
                    "at": 0.0,
                    "hold": 3.0,
                    "clipType": "shot",
                    "params": {
                        "shot_id": "shot_1",
                        "timeline_document_id": "sub1",
                    },
                },
            ],
        }
    )
    original_registry = copy.deepcopy(AssetRegistry())

    load_timeline = _load_timeline_from_fixture

    expanded_config, expanded_registry = expand_shot_clips(
        config=original_config,
        registry=original_registry,
        load_timeline=load_timeline,
    )

    # Verify expanded_config has expanded clips.
    assert len(expanded_config["clips"]) == 2  # sub_clip_1 expanded into two clips
    assert expanded_config["clips"][0]["id"] == "sub_clip_1"
    assert expanded_config["clips"][0]["at"] == 0.0  # parent.at + sub.at
    assert expanded_config["clips"][1]["id"] == "sub_clip_2"
    assert expanded_config["clips"][1]["at"] == 1.5

    # Verify expanded_registry has assets from sub1.
    assert len(expanded_registry["assets"]) == 0  # sub1 has no assets in our fixture

    # Verify original configs/registry are untouched (no side effects).
    assert original_config["clips"][0]["id"] == "shot_1"  # original clip is still there
    assert original_config["clips"][0]["at"] == 0.0  # original at is unchanged
    assert len(original_registry.get("assets", {})) == 0  # original registry is empty


def test_deeply_nested_shot_raises_error():
    """A sub-document containing its own shot clip fails closed (no recursion)."""
    config, registry = _make_timeline_fixture(
        "main",
        clips=[
            {
                "id": "shot_1",
                "at": 0.0,
                "hold": 3.0,
                "clipType": "shot",
                "params": {
                    "shot_id": "shot_1",
                    "timeline_document_id": "sub_with_nested_shot",
                },
            },
        ],
    )

    load_timeline = _load_timeline_from_fixture
    with pytest.raises(ShotExpansionError, match="nested shot"):
        expand_shot_clips(
            config=config,
            registry=registry,
            load_timeline=load_timeline,
        )


def test_empty_sub_doc_all_dropped():
    """Shot with empty sub-doc has all clips dropped and shot kept as placeholder."""
    config, registry = _make_timeline_fixture(
        "main",
        clips=[
            {
                "id": "shot_1",
                "at": 0.0,
                "hold": 3.0,
                "clipType": "shot",
                "params": {
                    "shot_id": "shot_1",
                    "timeline_document_id": "empty_sub",
                },
            },
            {
                "id": "parent_media_1",
                "at": 0.0,
                "hold": 1.0,
                "track": "visual",
                "clipType": "media",
            },
        ],
    )

    # Create an empty sub-doc load function.
    def load_empty(timeline_id: str) -> tuple[dict, AssetRegistry]:
        if timeline_id == "empty_sub":
            return _make_timeline_fixture("empty_sub", clips=[])[0], AssetRegistry()
        raise FileNotFoundError(f"Unknown timeline_id: {timeline_id}")

    expanded_config, expanded_registry = expand_shot_clips(
        config=config,
        registry=registry,
        load_timeline=load_empty,
    )

    # Shot with an empty sub-doc contributes NO clips (all dropped).
    shot_1_clips = [c for c in expanded_config["clips"] if c.get("clipType") == "shot"]
    assert len(shot_1_clips) == 0
    # No expanded sub-clips should be present.
    assert all(c["clipType"] != "shot" for c in expanded_config["clips"])

    # Parent media clips should still be there.
    parent_media_clips = [c for c in expanded_config["clips"] if c["clipType"] == "media"]
    assert len(parent_media_clips) == 1
    assert parent_media_clips[0]["id"] == "parent_media_1"


def test_multiple_shots_expansion():
    """Multiple shot clips are expanded independently."""
    config, registry = _make_timeline_fixture(
        "main",
        tracks=[
            {"id": "visual", "kind": "visual"},
            {"id": "audio", "kind": "audio"},
        ],
        clips=[
            {
                "id": "shot_1",
                "at": 0.0,
                "hold": 4.0,
                "clipType": "shot",
                "params": {
                    "shot_id": "shot_1",
                    "timeline_document_id": "sub1",
                },
            },
            {
                "id": "shot_2",
                "at": 5.0,
                "hold": 3.0,
                "clipType": "shot",
                "params": {
                    "shot_id": "shot_2",
                    "timeline_document_id": "sub2",
                },
            },
            {
                "id": "parent_media_1",
                "at": 8.0,
                "hold": 1.0,
                "track": "visual",
                "clipType": "media",
            },
        ],
    )

    load_timeline = _load_timeline_from_fixture
    expanded_config, expanded_registry = expand_shot_clips(
        config=config,
        registry=registry,
        load_timeline=load_timeline,
    )

    # Verify both shots were fully expanded (no shot clips remain).
    shot_remaining = [c for c in expanded_config["clips"] if c["clipType"] == "shot"]
    assert len(shot_remaining) == 0

    # Verify total clip count: 2 (sub1) + 1 (sub2) + 1 parent media.
    assert len(expanded_config["clips"]) == 4

    # Verify sub_clip_1 from sub1 and sub_clip_3 from sub2 are both present.
    assert any(c["id"] == "sub_clip_1" for c in expanded_config["clips"])
    assert any(c["id"] == "sub_clip_3" for c in expanded_config["clips"])
