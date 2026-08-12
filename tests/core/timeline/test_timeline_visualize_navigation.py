"""R8 navigation identities: semantic <-> display ordinals over the desert slice.

Covers the R8 contract for :mod:`astrid.packs.rendering.executors.timeline_visualize.navigation`:
ordinal ordering, duplicate rejection, sealed child copies, round trips,
deterministic range minting, build determinism, and the no-write import sentinel.
"""

from __future__ import annotations

import ast
import json
import shutil
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

from astrid.core.timeline.snapshot import acquire_snapshot
from astrid.packs.rendering.executors.timeline_visualize.ids import (
    SEMANTIC_KIND_TO_CODE,
    parse_qualified_ref,
)
from astrid.packs.rendering.executors.timeline_visualize.model import (
    ShotModel,
    TimelineInspectionModel,
    build_model,
)
from astrid.packs.rendering.executors.timeline_visualize.navigation import (
    IdentityMap,
    assign_range_ids,
    build_identity_map,
    stable_id_for,
)

TESTS_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = TESTS_ROOT / "fixtures" / "timeline_visualize"
SLICE_DIR = FIXTURE_ROOT / "desert_slice"
TRUTH = json.loads((FIXTURE_ROOT / "desert_truth.json").read_text(encoding="utf-8"))
PROJECT_SLUG = "desert-plant-growth"


@pytest.fixture
def desert_model(tmp_path: Path) -> TimelineInspectionModel:
    timeline_dir = tmp_path / "timelines" / TRUTH["timeline"]["ulid"]
    timeline_dir.parent.mkdir(parents=True)
    shutil.copytree(SLICE_DIR, timeline_dir)
    snapshot = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)
    return build_model(snapshot)


def _map(model: TimelineInspectionModel) -> IdentityMap:
    return build_identity_map(
        model,
        root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid,
        timeline_ulid=model.timeline_ulid,
    )


def test_desert_slice_ordinals_follow_clip_asset_and_timeline_order(
    desert_model: TimelineInspectionModel,
) -> None:
    model = desert_model
    identity_map = _map(model)

    assert identity_map.root_sns == model.snapshot_sns
    assert identity_map.timeline_uuid == TRUTH["timeline"]["uuid"]
    assert identity_map.timeline_ulid == TRUTH["timeline"]["ulid"]

    # TL01 is the timeline; its semantic authored id is the timeline UUID.
    assert identity_map.lookup_semantic("timeline", model.timeline_uuid) == "TL01"
    assert identity_map.lookup_display("TL01") == (
        model.timeline_uuid,
        "timeline",
        model.timeline_uuid,
    )

    # CL ordinals match the model's clip ordering exactly.
    clip_ids = [clip.clip_id for clip in model.clips]
    assert clip_ids == [
        "plant-frame-1",
        "plant-frame-2",
        "plant-frame-3",
        "plant-frame-4",
        "toccata-fugue",
    ]
    for ordinal, clip_id in enumerate(clip_ids, start=1):
        assert identity_map.lookup_semantic("clip", clip_id) == f"TL01.CL{ordinal:02d}"

    # AS ordinals follow the sorted registry-key order.
    sorted_asset_keys = sorted(model.registry_keys)
    assert sorted_asset_keys == [
        "plant-frame-1",
        "plant-frame-2",
        "plant-frame-3",
        "plant-frame-4",
        "toccata-fugue",
    ]
    for ordinal, asset_key in enumerate(sorted_asset_keys, start=1):
        assert identity_map.lookup_semantic("asset", asset_key) == f"TL01.AS{ordinal:02d}"
    assert identity_map.lookup_semantic("asset", "toccata-fugue") == "TL01.AS05"

    assert identity_map.lookup_semantic("clip", "missing-clip") is None
    assert identity_map.lookup_display("TL01.CL99") is None

    assert stable_id_for(model, "clip", "plant-frame-1") == "TL01.CL01"
    # Tracks have no R3 display code; M1 raises a clear KeyError.
    with pytest.raises(KeyError) as exc:
        stable_id_for(model, "track", "storyboard")
    assert "track" in str(exc.value) and "storyboard" in str(exc.value)


def test_shot_ordinals_follow_pinned_shot_group_order(
    desert_model: TimelineInspectionModel,
) -> None:
    model = desert_model
    assert model.shots == ()  # the raw desert fixture pins no shot groups

    with_shots = replace(
        model,
        shots=(
            ShotModel("growth-middle", ("plant-frame-2",), None, None),
            ShotModel("growth-late", ("plant-frame-4",), None, None),
        ),
    )
    identity_map = _map(with_shots)
    assert identity_map.lookup_semantic("shot", "growth-middle") == "TL01.SH01"
    assert identity_map.lookup_semantic("shot", "growth-late") == "TL01.SH02"
    assert identity_map.lookup_semantic("clip", "plant-frame-1") == "TL01.CL01"


def test_duplicate_authored_ids_raise_valueerror_listing_every_duplicate(
    desert_model: TimelineInspectionModel,
) -> None:
    model = desert_model
    params = dict(
        root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid,
        timeline_ulid=model.timeline_ulid,
    )

    duplicated_clips = replace(
        model,
        clips=(model.clips[0], model.clips[0], model.clips[1]),
    )
    with pytest.raises(ValueError) as clip_exc:
        build_identity_map(duplicated_clips, **params)
    message = str(clip_exc.value)
    assert "clip" in message and "plant-frame-1" in message

    duplicated_shots = replace(
        model,
        shots=(
            ShotModel("dup-shot", ("plant-frame-1",), None, None),
            ShotModel("dup-shot", ("plant-frame-2",), None, None),
        ),
    )
    with pytest.raises(ValueError) as shot_exc:
        build_identity_map(duplicated_shots, **params)
    assert "shot" in str(shot_exc.value) and "dup-shot" in str(shot_exc.value)

    with pytest.raises(ValueError) as range_exc:
        assign_range_ids(_map(model), [("r1", 0.0, 1.0), ("r1", 2.0, 3.0)])
    assert "range" in str(range_exc.value) and "r1" in str(range_exc.value)


def test_child_copy_is_distinct_sealed_and_unaffected_by_parent_mutation(
    desert_model: TimelineInspectionModel,
) -> None:
    parent = _map(desert_model)
    child = parent.child_copy()

    assert child is not parent
    assert child == parent
    assert child.semantic_to_display is not parent.semantic_to_display
    assert child.display_to_semantic is not parent.display_to_semantic
    assert isinstance(child.semantic_to_display, MappingProxyType)
    assert isinstance(child.display_to_semantic, MappingProxyType)

    clip_identity = (parent.timeline_uuid, "clip", "plant-frame-1")
    parent.semantic_to_display[clip_identity] = "TL01.CL99"
    parent.display_to_semantic["TL01"] = (
        parent.timeline_uuid,
        "clip",
        "plant-frame-9",
    )

    assert parent.lookup_semantic("clip", "plant-frame-1") == "TL01.CL99"
    # The sealed child still resolves every original allocation byte-for-byte.
    assert child.lookup_semantic("clip", "plant-frame-1") == "TL01.CL01"
    assert child.lookup_display("TL01") == (
        parent.timeline_uuid,
        "timeline",
        parent.timeline_uuid,
    )
    assert child.lookup_display("TL01.CL99") is None

    with pytest.raises(TypeError):
        child.semantic_to_display[clip_identity] = "TL01.CL99"
    with pytest.raises(TypeError):
        child.display_to_semantic["TL01.CL01"] = clip_identity


def test_semantic_display_round_trip_and_qualified_refs(
    desert_model: TimelineInspectionModel,
) -> None:
    identity_map = _map(desert_model)
    assert identity_map.display_to_semantic

    for display_id, identity in identity_map.display_to_semantic.items():
        _timeline_uuid, kind, authored_id = identity
        assert identity_map.lookup_semantic(kind, authored_id) == display_id

        parsed = parse_qualified_ref(display_id)
        assert parsed.kind == SEMANTIC_KIND_TO_CODE[kind]
        assert str(parsed) == display_id
        if parsed.object_id is not None:
            assert parsed.object_ordinal == int(display_id.rsplit(".", 1)[1][2:])
            assert parsed.timeline_id == "TL01"
        else:
            assert parsed.timeline_ordinal == 1
            assert display_id == "TL01"


def test_assign_range_ids_mints_rg_ordinals_in_start_time_order(
    desert_model: TimelineInspectionModel,
) -> None:
    identity_map = _map(desert_model)
    extended = assign_range_ids(
        identity_map,
        [("late", 9.0, 10.0), ("early", 1.0, 2.0), ("mid", 5.0, 6.0)],
    )

    assert extended.lookup_semantic("range", "early") == "TL01.RG01"
    assert extended.lookup_semantic("range", "mid") == "TL01.RG02"
    assert extended.lookup_semantic("range", "late") == "TL01.RG03"
    # The input map is never mutated.
    assert identity_map.lookup_semantic("range", "early") is None

    # Existing allocations are never renumbered; later calls continue the run.
    later = assign_range_ids(extended, [("after", 11.0, 12.0)])
    assert later.lookup_semantic("range", "after") == "TL01.RG04"
    assert later.lookup_semantic("range", "early") == "TL01.RG01"

    # Re-passing an already allocated range is an idempotent no-op.
    again = assign_range_ids(extended, [("early", 1.0, 2.0), ("mid", 5.0, 6.0)])
    assert again.lookup_semantic("range", "early") == "TL01.RG01"
    assert again.lookup_semantic("range", "mid") == "TL01.RG02"

    # Clip and asset ordinals survive range assignment untouched.
    assert later.lookup_semantic("clip", "plant-frame-1") == "TL01.CL01"
    assert later.lookup_semantic("asset", "toccata-fugue") == "TL01.AS05"


def test_build_is_deterministic_across_repeated_builds(
    tmp_path: Path,
    desert_model: TimelineInspectionModel,
) -> None:
    model = desert_model
    first = _map(model)
    second = _map(model)
    assert first is not second
    assert first == second
    assert list(first.semantic_to_display.items()) == list(second.semantic_to_display.items())

    # Re-acquiring the slice and rebuilding yields a byte-identical map.
    timeline_dir = tmp_path / "rebuilt" / TRUTH["timeline"]["ulid"]
    timeline_dir.parent.mkdir(parents=True)
    shutil.copytree(SLICE_DIR, timeline_dir)
    snapshot = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)
    assert _map(build_model(snapshot)) == first


def test_navigation_imports_no_repair_or_mutation_api() -> None:
    package_dir = (
        Path(__file__).resolve().parents[3]
        / "astrid"
        / "packs"
        / "rendering"
        / "executors"
        / "timeline_visualize"
    )
    tree = ast.parse((package_dir / "navigation.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden = (
        "timeline.crud",
        "timeline.projection",
        "timeline.asset_registry_edits",
        "timeline_storyboard",
        "local_bridge",
    )
    assert not any(token in module for module in imported for token in forbidden)
