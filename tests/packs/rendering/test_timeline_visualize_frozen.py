"""R16 acceptance: snapshot-safe drill-down and explicit root refresh."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

import astrid
from astrid.core.foundation.project_paths import project_dir
from astrid.core.project.project import create_project
from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
from astrid.core.timeline.events.schema import TimelineActor
from astrid.packs.rendering.executors.timeline_visualize import frozen as frozen_module
from astrid.packs.rendering.executors.timeline_visualize import run as run_module
from astrid.packs.rendering.executors.timeline_visualize.frozen import (
    ContainmentError,
    FocusResolutionError,
    FrozenIntegrityError,
    discard_rehydrated_pack,
    load_frozen_view,
    model_from_frozen,
    resolve_focus,
    snapshot_from_frozen,
)
from tests.packs.rendering._helpers import (
    admit_runtime_run,
    invoke_local_visualization,
    settle_runtime_pack,
)

TESTS_ROOT = Path(__file__).resolve().parents[2]
SLICE_DIR = TESTS_ROOT / "fixtures" / "timeline_visualize" / "desert_slice"
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"
TIMELINE_UUID = "ed70ef66-43da-4182-9f14-69361c6c5e10"


def _prepare_project(projects_root: Path, slug: str) -> tuple[Path, Path]:
    create_project(slug, root=projects_root)
    root = project_dir(slug, root=projects_root)
    timeline = root / "timelines" / TIMELINE_ULID
    shutil.copytree(SLICE_DIR, timeline)
    return root, timeline


def _invoke(slug: str, **extra_inputs: Any):
    inputs = {
        "project_slug": slug,
        "layout": "time-scaled",
        "formats": ["md"],
        "filmstrip": "off",
        **extra_inputs,
    }
    return invoke_local_visualization(slug, run_module=run_module, **inputs)


def _pack_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _root_view(projects_root: Path, slug: str):
    project_root, timeline_dir = _prepare_project(projects_root, slug)
    result = _invoke(slug, timeline_source=str(timeline_dir))
    assert result.ok is True, result.error
    return project_root, timeline_dir, result


def test_discard_never_deletes_user_owned_prefix_path(tmp_path: Path) -> None:
    user_root = tmp_path / "astrid-frozen-view-user-owned"
    nested = user_root / "nested" / "manifest.json"
    nested.parent.mkdir(parents=True)
    nested.write_text("user bytes", encoding="utf-8")

    discard_rehydrated_pack(nested)

    assert nested.read_text(encoding="utf-8") == "user bytes"


def test_failed_managed_load_reclaims_its_rehydrated_temp_root(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _timeline, result = _root_view(
        tmp_projects_root, "timeline-frozen-failed-cleanup"
    )
    before = set(frozen_module._REHYDRATED_PACKS)

    def reject(_pack_root: Path):
        raise FrozenIntegrityError("forced verifier failure")

    monkeypatch.setattr(frozen_module, "_verify_pack", reject)
    with pytest.raises(FrozenIntegrityError, match="forced verifier failure"):
        load_frozen_view(Path(result.manifest_path or ""), project_root=project_root)

    assert set(frozen_module._REHYDRATED_PACKS) == before


def test_discard_does_not_delete_a_same_path_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    (owned / "original").write_text("derived", encoding="utf-8")
    moved = tmp_path / "moved-owned"
    frozen_module._register_rehydrated_pack(owned)
    real_fstat = frozen_module.os.fstat
    swapped = False

    def swap_after_open(fd: int):
        nonlocal swapped
        result = real_fstat(fd)
        if not swapped:
            swapped = True
            owned.rename(moved)
            owned.mkdir()
            (owned / "user-sentinel").write_text("preserve", encoding="utf-8")
        return result

    monkeypatch.setattr(frozen_module.os, "fstat", swap_after_open)
    discard_rehydrated_pack(owned)

    assert (owned / "user-sentinel").read_text(encoding="utf-8") == "preserve"


def test_frozen_snapshot_preserves_registry_media_types(tmp_projects_root: Path) -> None:
    project_root, _timeline, root = _root_view(
        tmp_projects_root, "timeline-frozen-media-types"
    )
    frozen = load_frozen_view(Path(root.manifest_path or ""), project_root=project_root)
    snapshot = snapshot_from_frozen(frozen, model_from_frozen(frozen))
    media_types = {
        key: entry.get("type") for key, entry in snapshot.registry["assets"].items()
    }
    assert media_types["plant-frame-1"] == "image"
    assert media_types["toccata-fugue"] == "audio"


def _editable_manifest(result: Any, project_root: Path) -> Path:
    """Copy a durable pack to a distinct project-owned run for forgery tests."""

    durable = Path(result.manifest_path or "").resolve()
    frozen = load_frozen_view(durable, project_root=project_root)
    # The copied pack is still project-owned, so give it a fresh runtime run
    # and settle the copied bytes before integrity tests exercise it.  This
    # keeps the mutation tests focused on their intended hash/lineage failure
    # instead of falling through to the production ownership guard.
    runtime_context, run_id, task_id = admit_runtime_run(project_root.name)
    run_root = project_root / "runs" / run_id
    target = run_root / "agent-view"
    shutil.copytree(frozen.pack_root, target, dirs_exist_ok=True)
    record = json.loads((project_root / "runs" / str(result.run_id) / "run.json").read_text())
    record.update(
        {
            "run_id": run_id,
            "out": f"runs/{run_id}",
            "manifest_path": f"runs/{run_id}/agent-view/manifest.json",
        }
    )
    (run_root / "run.json").write_text(
        json.dumps(record, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    settle_runtime_pack(
        runtime_context, task_id=task_id, pack_root=target
    )
    return target / "manifest.json"


def _append_v160(timeline_dir: Path) -> None:
    backend = LocalFsBackend(timeline_id=TIMELINE_UUID, timeline_home=timeline_dir)
    head = backend.head()
    assert head.version == 159
    backend.append_event(
        TIMELINE_UUID,
        "timeline.renamed",
        {
            "old_slug": "plant-growth-storyboard",
            "new_slug": "plant-growth-storyboard-v160",
        },
        actor=TimelineActor(type="agent", id="codex:r16"),
        expected_version=head.version,
    )
    assert backend.head().version == 160


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_bytes(value: object, *, ordered: bool = False) -> bytes:
    return json.dumps(
        value,
        sort_keys=not ordered,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _rewrite_ground_truth_with_valid_hashes(manifest_path: Path, value: dict) -> None:
    pack_root = manifest_path.parent
    ground_truth_path = pack_root / "ground-truth.json"
    ground_truth_bytes = _json_bytes(value)
    ground_truth_path.write_bytes(ground_truth_bytes)
    ground_truth_digest = hashlib.sha256(ground_truth_bytes).hexdigest()

    manifest = _json(manifest_path)
    output = next(
        row for row in manifest["outputs"] if row["path"] == "ground-truth.json"
    )
    output["bytes"] = len(ground_truth_bytes)
    output["content_hash"] = f"sha256:{ground_truth_digest}"
    output["sha256"] = ground_truth_digest
    manifest_bytes = _json_bytes(manifest)
    manifest_path.write_bytes(manifest_bytes)

    ledger_path = pack_root / "pack-hashes.json"
    ledger = _json(ledger_path)
    ledger["files"]["ground-truth.json"] = {
        "sha256": ground_truth_digest,
        "bytes": len(ground_truth_bytes),
    }
    ledger["files"]["manifest.json"] = {
        "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "bytes": len(manifest_bytes),
    }
    ledger_path.write_bytes(_json_bytes(ledger, ordered=True))


def test_valid_drill_down_keeps_root_ids_sns_and_exact_parent(
    tmp_projects_root: Path,
) -> None:
    project_root, _timeline, root = _root_view(
        tmp_projects_root, "timeline-frozen-valid"
    )
    root_manifest = Path(root.manifest_path or "").resolve()

    child = _invoke(
        "timeline-frozen-valid",
        from_view=str(root_manifest),
        focus="TL01.CL03",
    )

    assert child.ok is True, child.error
    child_manifest = Path(child.manifest_path or "").resolve()
    root_frozen = load_frozen_view(root_manifest, project_root=project_root)
    child_frozen = load_frozen_view(child_manifest, project_root=project_root)
    assert list(child_frozen.identity_map.semantic_to_display.items()) == list(
        root_frozen.identity_map.semantic_to_display.items()
    )
    assert child_frozen.snapshot_sns == root_frozen.snapshot_sns
    assert child_frozen.ground_truth["frozen_objects"] == root_frozen.ground_truth[
        "frozen_objects"
    ]
    manifest = child_frozen.manifest
    expected_parent = (
        root_manifest.relative_to(project_root).as_posix()
        if root_manifest.is_relative_to(project_root)
        else str(root_manifest)
    )
    assert manifest["inputs"]["from_view"] == expected_parent
    assert manifest["inputs"]["focus"] == "TL01.CL03"
    parent = child_frozen.action_index["entries"]["TL01"]["actions"][
        "parent_view"
    ]
    assert parent["focus"] == "TL01"
    marker = parent["argv"].index("--from-view")
    assert Path(parent["argv"][marker + 1]).resolve() == root_manifest


def test_cold_range_root_mints_rg_and_is_a_valid_frozen_parent(
    tmp_projects_root: Path,
) -> None:
    slug = "timeline-frozen-range-root"
    project_root, timeline = _prepare_project(tmp_projects_root, slug)
    root = _invoke(
        slug,
        timeline_source=str(timeline),
        range="00:05..00:12",
    )
    assert root.ok is True, root.error
    root_manifest = Path(root.manifest_path or "").resolve()
    root_frozen = load_frozen_view(root_manifest, project_root=project_root)
    ground_truth = root_frozen.ground_truth

    assert ground_truth["scope"] == {
        "kind": "range",
        "ref": "TL01.RG01",
        "start_frame": 120,
        "end_frame": 288,
        "start_seconds": 5.0,
        "end_seconds": 12.0,
    }
    assert ground_truth["frozen_ranges"] == [
        {
            "stable_id": "RG01",
            "qualified_ref": "TL01.RG01",
            "canonical_ref": {
                "timeline_uuid": TIMELINE_UUID,
                "kind": "range",
                "authored_id": "range:5:12",
            },
            "start_frame": 120,
            "end_frame": 288,
            "start_seconds": 5.0,
            "end_seconds": 12.0,
        }
    ]

    child = _invoke(slug, from_view=str(root_manifest), focus="TL01.RG01")
    assert child.ok is True, child.error
    child_manifest = Path(child.manifest_path or "").resolve()
    child_frozen = load_frozen_view(child_manifest, project_root=project_root)

    assert child_frozen.manifest["scope"] == ground_truth["scope"]
    assert list(child_frozen.identity_map.semantic_to_display.items()) == list(
        root_frozen.identity_map.semantic_to_display.items()
    )
    assert child_frozen.ground_truth["frozen_ranges"] == ground_truth[
        "frozen_ranges"
    ]
    parent = child_frozen.action_index["entries"]["TL01"]["actions"][
        "parent_view"
    ]
    assert parent["focus"] == "TL01.RG01"
    assert parent["result_scope"] == "range"
    marker = parent["argv"].index("--from-view")
    assert Path(parent["argv"][marker + 1]).resolve() == root_manifest


def test_cold_range_root_id_is_deterministic_across_selector_spellings(
    tmp_projects_root: Path,
) -> None:
    slug = "timeline-frozen-range-deterministic"
    _project_root, timeline = _prepare_project(tmp_projects_root, slug)
    ground_truths: list[dict] = []
    for selector in ("5..12", "00:05..00:12"):
        result = _invoke(
            slug,
            timeline_source=str(timeline),
            range=selector,
        )
        assert result.ok is True, result.error
        frozen = load_frozen_view(
            Path(result.manifest_path or ""), project_root=_project_root
        )
        ground_truths.append(frozen.ground_truth)

    assert [ground_truth["scope"]["ref"] for ground_truth in ground_truths] == [
        "TL01.RG01",
        "TL01.RG01",
    ]
    assert [
        ground_truth["frozen_ranges"][0]["canonical_ref"]["authored_id"]
        for ground_truth in ground_truths
    ] == ["range:5:12", "range:5:12"]


def test_live_append_cannot_change_frozen_child_bytes(
    tmp_projects_root: Path,
) -> None:
    _project_root, timeline, root = _root_view(
        tmp_projects_root, "timeline-frozen-independent"
    )
    root_manifest = Path(root.manifest_path or "").resolve()
    before = _invoke(
        "timeline-frozen-independent",
        from_view=str(root_manifest),
        focus="TL01.CL03",
    )
    assert before.ok is True, before.error

    _append_v160(timeline)
    after = _invoke(
        "timeline-frozen-independent",
        from_view=str(root_manifest),
        focus="TL01.CL03",
    )

    assert after.ok is True, after.error
    assert _pack_bytes(Path(before.outputs["pack_root"])) == _pack_bytes(
        Path(after.outputs["pack_root"])
    )


def test_containment_and_full_hash_preflight_reject_forgery(
    tmp_projects_root: Path,
    tmp_path: Path,
) -> None:
    project_root, _timeline, root = _root_view(
        tmp_projects_root, "timeline-frozen-integrity"
    )
    outside = tmp_path / "manifest.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ContainmentError):
        load_frozen_view(outside, project_root=project_root)

    root_manifest = _editable_manifest(root, project_root)
    ledger_path = root_manifest.parent / "pack-hashes.json"
    ledger = _json(ledger_path)
    ledger["files"]["ground-truth.json"]["sha256"] = "0" * 64
    ledger_path.write_text(
        json.dumps(ledger, separators=(",", ":")), encoding="utf-8"
    )
    with pytest.raises(FrozenIntegrityError, match="ground-truth.json"):
        load_frozen_view(root_manifest, project_root=project_root)


def test_hash_valid_dangling_frozen_clip_track_is_rejected(
    tmp_projects_root: Path,
) -> None:
    project_root, _timeline, root = _root_view(
        tmp_projects_root, "timeline-frozen-dangling-track"
    )
    root_manifest = _editable_manifest(root, project_root)
    ground_truth = _json(root_manifest.parent / "ground-truth.json")
    clip = ground_truth["frozen_timeline"]["clips"][0]
    clip_ref = clip["qualified_ref"]
    clip["track_authored_id"] = "MISSING_TRACK"
    _rewrite_ground_truth_with_valid_hashes(root_manifest, ground_truth)

    with pytest.raises(FrozenIntegrityError, match="MISSING_TRACK") as rejected:
        load_frozen_view(root_manifest, project_root=project_root)
    assert clip_ref in str(rejected.value)
    assert "frozen_timeline.tracks[].authored_id" in str(rejected.value)


def test_hash_valid_dangling_frozen_shot_member_is_rejected(
    tmp_projects_root: Path,
) -> None:
    project_root, _timeline, root = _root_view(
        tmp_projects_root, "timeline-frozen-dangling-shot-member"
    )
    root_manifest = _editable_manifest(root, project_root)
    ground_truth = _json(root_manifest.parent / "ground-truth.json")
    shot_ref = "TL01.SH01"
    canonical_ref = {
        "timeline_uuid": TIMELINE_UUID,
        "kind": "shot",
        "authored_id": "synthetic-shot",
    }
    ground_truth["frozen_objects"].append(
        {
            "stable_id": "SH01",
            "qualified_ref": shot_ref,
            "canonical_ref": canonical_ref,
        }
    )
    ground_truth["frozen_shots"].append(
        {
            "stable_id": "SH01",
            "qualified_ref": shot_ref,
            "canonical_ref": canonical_ref,
            "member_clip_ids": ["MISSING_CLIP"],
            "authored_interval": None,
            "frame_interval": None,
            "warnings": [],
        }
    )
    _rewrite_ground_truth_with_valid_hashes(root_manifest, ground_truth)

    with pytest.raises(FrozenIntegrityError, match="MISSING_CLIP") as rejected:
        load_frozen_view(root_manifest, project_root=project_root)
    assert shot_ref in str(rejected.value)
    assert (
        "frozen_timeline.clips[].canonical_ref.authored_id"
        in str(rejected.value)
    )


def test_unknown_display_id_and_m1_text_refs_fail_closed(
    tmp_projects_root: Path,
) -> None:
    project_root, _timeline, root = _root_view(
        tmp_projects_root, "timeline-frozen-unknown"
    )
    frozen = load_frozen_view(
        Path(root.manifest_path or ""), project_root=project_root
    )
    with pytest.raises(FocusResolutionError, match="frozen identity map"):
        resolve_focus(frozen, "TL01.CL999")
    with pytest.raises(FocusResolutionError, match="not available in this snapshot"):
        resolve_focus(frozen, "TL01.TS01")
    with pytest.raises(FocusResolutionError, match="not available in this snapshot"):
        resolve_focus(frozen, "TL01.SP01")


def test_timestamp_locator_preserves_exact_at_seconds(
    tmp_projects_root: Path,
) -> None:
    project_root, _timeline, root = _root_view(
        tmp_projects_root, "timeline-frozen-timestamp"
    )
    frozen = load_frozen_view(
        Path(root.manifest_path or ""), project_root=project_root
    )

    scope = resolve_focus(
        frozen, "TL01@00:00:02.000", context_seconds=3.0
    )

    assert scope.kind == "timestamp"
    assert scope.ref == "TL01@00:00:02.000"
    assert scope.at_seconds == 2.0
    assert scope.context_frames == 72


def test_refresh_root_is_the_only_transition_to_v160(
    tmp_projects_root: Path,
) -> None:
    project_root, timeline, root = _root_view(
        tmp_projects_root, "timeline-frozen-refresh"
    )
    root_manifest = Path(root.manifest_path or "").resolve()
    old = load_frozen_view(root_manifest, project_root=project_root)
    old_bytes = _pack_bytes(root_manifest.parent)
    _append_v160(timeline)

    refreshed = _invoke(
        "timeline-frozen-refresh",
        from_view=str(root_manifest),
        focus="TL01",
        refresh_root=True,
    )

    assert refreshed.ok is True, refreshed.error
    fresh = load_frozen_view(
        Path(refreshed.manifest_path or ""), project_root=project_root
    )
    assert fresh.manifest["snapshots"][0]["event_head"]["version"] == 160
    assert fresh.snapshot_sns != old.snapshot_sns
    assert fresh.manifest["inputs"]["from_view"] is None
    assert _pack_bytes(root_manifest.parent) == old_bytes
    old_child = _invoke(
        "timeline-frozen-refresh",
        from_view=str(root_manifest),
        focus="TL01.CL03",
    )
    assert old_child.ok is True, old_child.error
    assert load_frozen_view(
        Path(old_child.manifest_path or ""), project_root=project_root
    ).snapshot_sns == old.snapshot_sns


def test_drill_down_calls_no_current_timeline_reader(
    tmp_projects_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _project_root, _timeline, root = _root_view(
        tmp_projects_root, "timeline-frozen-no-live-read"
    )

    def forbidden(*_args: Any, **_kwargs: Any):
        raise AssertionError("current timeline state was read during frozen drill-down")

    monkeypatch.setattr(run_module, "acquire_snapshot", forbidden)
    monkeypatch.setattr(run_module, "_select_timelines", forbidden)
    result = run_module.execute(
        [
            "--project-slug",
            "timeline-frozen-no-live-read",
            "--from-view",
            str(Path(root.manifest_path or "")),
            "--focus",
            "TL01.CL03",
            "--layout",
            "time-scaled",
            "--format",
            "md",
            "--filmstrip",
            "off",
            "--out",
            str(tmp_path / "frozen-child-run"),
        ]
    )

    assert result["returncode"] == 0


def test_two_drill_downs_are_byte_identical(
    tmp_projects_root: Path,
) -> None:
    _project_root, _timeline, root = _root_view(
        tmp_projects_root, "timeline-frozen-deterministic"
    )
    manifest = str(Path(root.manifest_path or ""))
    first = _invoke(
        "timeline-frozen-deterministic",
        from_view=manifest,
        focus="TL01.CL03",
    )
    second = _invoke(
        "timeline-frozen-deterministic",
        from_view=manifest,
        focus="TL01.CL03",
    )

    assert first.ok is second.ok is True
    assert _pack_bytes(Path(first.outputs["pack_root"])) == _pack_bytes(
        Path(second.outputs["pack_root"])
    )
