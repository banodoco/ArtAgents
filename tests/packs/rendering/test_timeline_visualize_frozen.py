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
from astrid.packs.rendering.executors.timeline_visualize import run as run_module
from astrid.packs.rendering.executors.timeline_visualize.frozen import (
    ContainmentError,
    FocusResolutionError,
    FrozenIntegrityError,
    load_frozen_view,
    resolve_focus,
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
    return astrid.invoke(
        "rendering.timeline_visualize",
        kind="executor",
        include_installed=False,
        project=slug,
        inputs={
            "project_slug": slug,
            "layout": "time-scaled",
            "formats": ["md"],
            "filmstrip": "off",
            **extra_inputs,
        },
        execution_mode="in_process",
    )


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
    assert manifest["inputs"]["from_view"] == root_manifest.relative_to(
        project_root
    ).as_posix()
    assert manifest["inputs"]["focus"] == "TL01.CL03"
    parent = child_frozen.action_index["entries"]["TL01"]["actions"][
        "parent_view"
    ]
    assert parent["focus"] == "TL01"
    marker = parent["argv"].index("--from-view")
    assert Path(parent["argv"][marker + 1]).resolve() == root_manifest


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

    root_manifest = Path(root.manifest_path or "").resolve()
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
    root_manifest = Path(root.manifest_path or "").resolve()
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
    root_manifest = Path(root.manifest_path or "").resolve()
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
