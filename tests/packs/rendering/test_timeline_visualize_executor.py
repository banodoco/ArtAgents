"""R14 acceptance: packaged executor, SDK identity, and evidence retention."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
import yaml

import astrid
from astrid.core.execution.executor.registry import load_default_registry
from astrid.core.execution.executor.schema import load_executor_manifest
from astrid.core.foundation.project_paths import project_dir
from astrid.core.kernel.read import kernel_run_info
from astrid.core.project.project import create_project
from astrid.packs.rendering.executors.timeline_visualize import frozen as frozen_module
from astrid.packs.rendering.executors.timeline_visualize import run as run_module
from astrid.packs.rendering.executors.timeline_visualize.frozen import (
    FrozenSchemaError,
    discard_rehydrated_pack,
    rehydrate_managed_pack,
)
from astrid.packs.rendering.executors.timeline_visualize.select import select_timeline
from astrid.sdk.exceptions import CapabilityInvocationError, CapabilityValidationError
from astrid.sdk.invocation import _persist_visualization_pack, invoke_result

TESTS_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = TESTS_ROOT.parent
SLICE_DIR = TESTS_ROOT / "fixtures" / "timeline_visualize" / "desert_slice"
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"
SECOND_TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8243"
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def _prepare_project(
    projects_root: Path,
    slug: str,
    *,
    manifest_bytes: bytes | None = None,
    second_timeline: bool = False,
) -> tuple[Path, Path]:
    create_project(slug, root=projects_root)
    root = project_dir(slug, root=projects_root)
    first = root / "timelines" / TIMELINE_ULID
    shutil.copytree(SLICE_DIR, first)
    if manifest_bytes is not None:
        (first / "manifest.json").write_bytes(manifest_bytes)
    if second_timeline:
        second = root / "timelines" / SECOND_TIMELINE_ULID
        shutil.copytree(SLICE_DIR, second)
        identity_path = second / "assembly.identity.json"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["timeline_ulid"] = SECOND_TIMELINE_ULID
        identity_path.write_text(
            json.dumps(identity, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
    return root, first


def _invoke(slug: str, *, execution_mode: str = "in_process", **extra_inputs):
    inputs = {
        "project_slug": slug,
        "layout": "time-scaled",
        "formats": ["png", "svg", "md"],
        "filmstrip": "off",
        **extra_inputs,
    }
    return astrid.invoke(
        "rendering.timeline_visualize",
        kind="executor",
        include_installed=False,
        project=slug,
        inputs=inputs,
        execution_mode=execution_mode,
    )


def _pack_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_executor_registration_and_non_exemption() -> None:
    executor_path = REPO_ROOT / "astrid/packs/rendering/executors/timeline_visualize/executor.yaml"
    definition = load_executor_manifest(executor_path)
    assert definition.id == "rendering.timeline_visualize"
    assert definition.version == "1.0"
    assert definition.metadata["requires_timeline"] is False
    assert definition.metadata["output_result_manifest"] is True
    assert definition.metadata["run_metadata"] == {"evidence": True}
    input_names = {port.name for port in definition.inputs}
    assert {
        "project_slug",
        "timeline_source",
        "timeline_slug",
        "all",
        "shot",
        "range",
        "at",
        "clip",
        "asset",
        "context",
        "neighbors",
        "from_view",
        "focus",
        "layout",
        "formats",
        "filmstrip",
        "rendered_video",
    } <= input_names

    pack = yaml.safe_load(
        (REPO_ROOT / "astrid/packs/rendering/pack.yaml").read_text(encoding="utf-8")
    )
    assert "timeline_visualize" in pack["capabilities"]
    assert "rendering.timeline_visualize" in pack["agent"]["normal_entrypoints"]
    registered = load_default_registry().get("rendering.timeline_visualize")
    assert registered.id == definition.id
    assert registered.metadata["runtime_module"] == definition.metadata["runtime_module"]

    core_skill = (REPO_ROOT / "astrid/packs/_core/skill/SKILL.md").read_text(encoding="utf-8")
    rendering_skill = (REPO_ROOT / "astrid/packs/rendering/skill/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "`rendering.timeline_visualize`" in core_skill
    assert "`rendering.timeline_visualize`" in rendering_skill

    exemptions = json.loads(
        (REPO_ROOT / "astrid/core/contracts/output_result_exemptions.json").read_text(
            encoding="utf-8"
        )
    )
    assert "rendering.timeline_visualize" in exemptions["non_exempt"]
    assert "rendering.timeline_visualize" not in exemptions["exemptions"]
    assert exemptions["m1_adopters"] == len(exemptions["non_exempt"])
    assert exemptions["exempted"] == len(exemptions["exemptions"])


def test_full_managed_executor_pack_conforms_and_timeline_manifest_is_unchanged(
    tmp_projects_root: Path,
) -> None:
    slug = "timeline-visualize-managed"
    sentinel = b'{\n  "sentinel": "timeline-owned bytes",\n  "tombstoned_at": null\n}\n'
    project_root, timeline_dir = _prepare_project(
        tmp_projects_root,
        slug,
        manifest_bytes=sentinel,
    )

    first = _invoke(slug, timeline_source=str(timeline_dir))

    assert first.ok is True
    assert first.run_id is not None
    assert first.run_root is None
    assert first.manifest_path is not None
    assert first.executor_version is not None
    assert _DIGEST_RE.fullmatch(first.executor_version)
    assert {"pack_root", "manifest_path", "pages", "file_hashes"} <= set(first.outputs)

    pack_root = Path(first.outputs["pack_root"])
    manifest_path = Path(first.manifest_path)
    assert pack_root.is_relative_to(project_root / ".astrid" / "views")
    assert manifest_path.is_relative_to(tmp_projects_root / ".astrid" / "media")
    assert manifest_path != pack_root / "manifest.json"
    assert manifest_path.is_file()
    assert (pack_root / "manifest.json").read_bytes() == manifest_path.read_bytes()
    expected = {
        "manifest.json",
        "ground-truth.json",
        "view-map.json",
        "action-index.json",
        "asset-index.json",
        "transcript-index.json",
        "diagnostics.json",
        "metric-definitions.json",
        "reading-guide.md",
        "structure.md",
        "pack-hashes.json",
        "PG001.png",
        "PG002.png",
        "PG001.svg",
        "PG002.svg",
    }
    assert set(_pack_bytes(pack_root)) == expected
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert {"schema_version", "kind", "inputs", "outputs", "created", "warnings"} <= set(manifest)

    info = kernel_run_info(slug, first.run_id, projects_root=tmp_projects_root)
    assert info is not None
    assert info["status"] == "succeeded"
    assert info["capability"] == "rendering.timeline_visualize"
    assert info["task_id"] == first.kernel_task_id
    assert not (project_root / "runs" / first.run_id / "run.json").exists()
    assert (timeline_dir / "manifest.json").read_bytes() == sentinel
    cached_manifest = pack_root / "manifest.json"
    durable_bytes = manifest_path.read_bytes()
    assert cached_manifest.stat().st_ino != manifest_path.stat().st_ino
    cached_manifest.write_bytes(b"locally modified derived view")
    assert manifest_path.read_bytes() == durable_bytes
    repaired = _invoke(slug, timeline_source=str(timeline_dir))
    assert repaired.ok is True, repaired.error
    assert repaired.run_id == first.run_id
    assert Path(repaired.outputs["pack_root"]) == pack_root
    assert cached_manifest.read_bytes() == durable_bytes


def test_requires_timeline_false_runs_without_manifest_and_never_creates_one(
    tmp_projects_root: Path,
) -> None:
    slug = "timeline-visualize-no-manifest"
    _project_root, timeline_dir = _prepare_project(tmp_projects_root, slug)
    timeline_manifest = timeline_dir / "manifest.json"
    assert not timeline_manifest.exists()

    result = _invoke(slug, timeline_source=str(timeline_dir))

    assert result.ok is True
    assert Path(result.manifest_path or "").is_file()
    assert not timeline_manifest.exists()
    info = kernel_run_info(
        slug,
        result.run_id or "",
        projects_root=tmp_projects_root,
    )
    assert info is not None
    assert info["status"] == "succeeded"


def test_sdk_return_shape_and_stdout_are_cli_ready(
    tmp_projects_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    slug = "timeline-visualize-sdk"
    _project_root, timeline_dir = _prepare_project(tmp_projects_root, slug)

    capsys.readouterr()
    result = _invoke(
        slug,
        timeline_source=str(timeline_dir),
        execution_mode="subprocess",
    )
    captured = capsys.readouterr()

    assert captured.out == ""
    assert result.ok is True
    assert result.run_id
    assert result.run_root is None
    assert result.manifest_path and Path(result.manifest_path).is_file()
    assert result.executor_version and _DIGEST_RE.fullmatch(result.executor_version)
    assert {"pack_root", "manifest_path", "pages", "file_hashes"} <= set(result.outputs)
    serialized = result.to_dict()
    assert serialized["run_id"] == result.run_id
    assert serialized["run_root"] == result.run_root
    assert serialized["manifest_path"] == result.manifest_path
    assert serialized["executor_version"] == result.executor_version
    assert serialized["outputs"] == result.outputs


def test_replayed_managed_invocation_reuses_kernel_identity_and_pack_bytes(
    tmp_projects_root: Path,
) -> None:
    slug = "timeline-visualize-deterministic"
    _project_root, timeline_dir = _prepare_project(tmp_projects_root, slug)

    first = _invoke(slug, timeline_source=str(timeline_dir))
    second = _invoke(slug, timeline_source=str(timeline_dir))

    assert first.ok is second.ok is True
    assert first.run_id == second.run_id
    assert first.kernel_task_id == second.kernel_task_id
    assert first.executor_version == second.executor_version
    with sqlite3.connect(tmp_projects_root / ".astrid" / "astrid.sqlite3") as conn:
        row = conn.execute(
            "SELECT spec_json FROM tasks WHERE id = ?", (first.kernel_task_id,)
        ).fetchone()
    assert row is not None
    stored_spec = json.loads(row[0])
    assert stored_spec["authority_context"]["executor_version"] == first.executor_version
    assert stored_spec["authority_context"]["mode"] == "legacy_file"
    first_pack = Path(first.outputs["pack_root"])
    second_pack = Path(second.outputs["pack_root"])
    assert _pack_bytes(first_pack) == _pack_bytes(second_pack)


def test_legacy_eventlog_change_after_admission_is_execution_fenced(
    tmp_projects_root: Path,
) -> None:
    slug = "timeline-visualize-authority-race"
    project_root, timeline_dir = _prepare_project(tmp_projects_root, slug)
    selected, diagnostics = select_timeline(project_root, all=True)
    assert selected and not diagnostics
    eventlog = timeline_dir / "assembly.jsonl"
    authority = {
        "mode": "legacy_file",
        "timelines": [
            {
                "timeline_ulid": selected[0].timeline_ulid,
                "eventlog_sha256": hashlib.sha256(eventlog.read_bytes()).hexdigest(),
            }
        ],
    }
    eventlog.write_bytes(eventlog.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="changed after admission"):
        run_module._verify_selected_execution_authority(selected, authority)


def test_duplicate_legacy_timeline_source_is_rejected_before_admission(
    tmp_projects_root: Path,
) -> None:
    slug = "timeline-visualize-duplicate-source"
    _project_root, timeline_dir = _prepare_project(tmp_projects_root, slug)

    with pytest.raises(CapabilityValidationError, match="more than once"):
        _invoke(slug, timeline_source=[str(timeline_dir), str(timeline_dir)])


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"timeline_source": []}, "at least one path"),
        ({"formats": []}, "formats must contain"),
        ({"shot": "shot-1", "clip": "clip-1"}, "mutually exclusive"),
        ({"refresh_root": True}, "requires from_view and focus"),
        ({"filmstrip": "rendered"}, "requires rendered_video"),
        ({"filmstrip": "bogus"}, "filmstrip must be"),
        ({"filmstrip": {}}, "filmstrip must be"),
        ({"layout": "bogus"}, "layout must be"),
        ({"layout": []}, "layout must be"),
        ({"scope": "bogus"}, "scope must be"),
        ({"scope": []}, "scope must be"),
        ({"context": -1}, "finite non-negative"),
        ({"neighbors": -1}, "non-negative integer"),
        (
            {"filmstrip": "assets", "rendered_video": "render.mp4"},
            "requires filmstrip auto or rendered",
        ),
    ],
)
def test_invalid_selector_combinations_are_rejected_before_admission(
    tmp_projects_root: Path,
    inputs: dict[str, object],
    message: str,
) -> None:
    slug = "timeline-visualize-preflight"
    _prepare_project(tmp_projects_root, slug)

    with pytest.raises(CapabilityValidationError, match=message):
        _invoke(slug, **inputs)


def test_project_visualization_rejects_out_before_admission(
    tmp_projects_root: Path,
) -> None:
    slug = "timeline-visualize-managed-out"
    _project_root, timeline_dir = _prepare_project(tmp_projects_root, slug)

    with pytest.raises(CapabilityValidationError, match="durable manifest_path"):
        astrid.invoke(
            "rendering.timeline_visualize",
            kind="executor",
            include_installed=False,
            project=slug,
            out=tmp_projects_root / "manual-output",
            inputs={"timeline_source": str(timeline_dir)},
        )


def test_invalid_project_slug_returns_typed_preflight_result(
    tmp_projects_root: Path,
) -> None:
    result = invoke_result(
        "rendering.timeline_visualize",
        kind="executor",
        include_installed=False,
        project="bad/project",
        project_root=tmp_projects_root,
        inputs={},
    )

    assert result.ok is False
    assert result.run_id is None
    assert result.error is not None
    assert result.error["sdk_error"] == "CapabilityValidationError"


def test_durable_pack_cache_serializes_concurrent_publishers(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source = tmp_path / "verified-pack"
    source.mkdir()
    manifest = source / "manifest.json"
    manifest.write_text('{"kind":"timeline_visualize"}', encoding="utf-8")
    (source / "ground-truth.json").write_text(
        '{"project_slug":"project"}', encoding="utf-8"
    )
    expected = _pack_bytes(source)
    start = Barrier(8)

    def persist() -> Path:
        return _persist_visualization_pack(
            source,
            project_root=project_root,
            manifest=manifest,
        )

    def publish(_index: int) -> Path:
        start.wait()
        return persist()

    with ThreadPoolExecutor(max_workers=8) as pool:
        published = list(pool.map(publish, range(8)))

    assert len(set(published)) == 1
    assert _pack_bytes(published[0]) == expected
    assert published[0].is_relative_to(
        project_root / ".astrid" / "views" / "timeline_visualize"
    )
    cache_parent = published[0].parent
    assert not [
        path
        for path in cache_parent.iterdir()
        if path.is_dir() and path.name.startswith(f".{published[0].name}.")
    ]
    extra_directory = published[0] / "undeclared-empty-directory"
    extra_directory.mkdir()
    repaired = persist()
    assert repaired == published[0]
    assert not extra_directory.exists()


def test_durable_pack_cache_rejects_symlink_destination(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source = tmp_path / "verified-pack"
    source.mkdir()
    manifest = source / "manifest.json"
    manifest.write_text('{"kind":"timeline_visualize"}', encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    cache_parent = project_root / ".astrid" / "views" / "timeline_visualize"
    cache_parent.mkdir(parents=True)
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    (cache_parent / digest).symlink_to(outside, target_is_directory=True)

    with pytest.raises(CapabilityInvocationError, match="must not be a symlink"):
        _persist_visualization_pack(
            source,
            project_root=project_root,
            manifest=manifest,
        )

    assert list(outside.iterdir()) == []


def test_durable_cache_repair_preserves_same_path_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source = tmp_path / "verified-pack"
    source.mkdir()
    manifest = source / "manifest.json"
    manifest.write_text('{"kind":"timeline_visualize"}', encoding="utf-8")
    published = _persist_visualization_pack(
        source, project_root=project_root, manifest=manifest
    )
    (published / "corrupt").write_text("derived", encoding="utf-8")
    moved = tmp_path / "moved-cache"

    # Replace the verified destination after its tree walk but before repair.
    real_lstat = Path.lstat
    root_lstats = 0

    def swapping_lstat(path: Path, *args, **kwargs):
        nonlocal root_lstats
        if path == published:
            root_lstats += 1
        if path == published and root_lstats == 2:
            published.rename(moved)
            published.mkdir()
            (published / "user-sentinel").write_text("preserve", encoding="utf-8")
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", swapping_lstat)
    with pytest.raises(CapabilityInvocationError, match="changed during verification"):
        _persist_visualization_pack(source, project_root=project_root, manifest=manifest)

    assert (published / "user-sentinel").read_text(encoding="utf-8") == "preserve"


def test_multi_timeline_selection_writes_sorted_run_owned_metadata(
    tmp_projects_root: Path,
) -> None:
    slug = "timeline-visualize-all"
    _project_root, _timeline_dir = _prepare_project(
        tmp_projects_root,
        slug,
        second_timeline=True,
    )

    second_timeline = tmp_projects_root / slug / "timelines" / SECOND_TIMELINE_ULID
    result = _invoke(
        slug,
        timeline_source=[str(_timeline_dir), str(second_timeline)],
    )

    assert result.ok is True
    info = kernel_run_info(
        slug,
        result.run_id or "",
        projects_root=tmp_projects_root,
    )
    assert info is not None
    assert info["status"] == "succeeded"
    assert info["capability"] == "rendering.timeline_visualize"
    manifest = json.loads(Path(result.manifest_path or "").read_text(encoding="utf-8"))
    assert manifest["kind"] == "timeline_visualize_project"
    assert manifest["timeline_ids"] == sorted([SECOND_TIMELINE_ULID, TIMELINE_ULID])
    assert manifest["reading_order"] == ["TL01/manifest.json", "TL02/manifest.json"]
    assert all(
        (Path(result.outputs["pack_root"]) / item).is_file() for item in manifest["reading_order"]
    )


def test_legacy_project_index_without_child_digests_remains_readable(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slug = "timeline-visualize-legacy-project-index"
    project_root, first = _prepare_project(tmp_projects_root, slug, second_timeline=True)
    second = project_root / "timelines" / SECOND_TIMELINE_ULID
    result = _invoke(slug, timeline_source=[str(first), str(second)])
    assert result.ok is True, result.error
    original_loader = frozen_module._load_json_file

    def legacy_loader(*args, **kwargs):
        document = original_loader(*args, **kwargs)
        if document.get("kind") == "timeline_visualize_project":
            document = dict(document)
            document["outputs"] = [
                {key: value for key, value in row.items() if key != "manifest_sha256"}
                for row in document["outputs"]
            ]
        return document

    monkeypatch.setattr(frozen_module, "_load_json_file", legacy_loader)
    restored = rehydrate_managed_pack(
        Path(result.manifest_path or ""), project_root=project_root
    )
    try:
        assert (restored / "TL01" / "manifest.json").is_file()
        assert (restored / "TL02" / "manifest.json").is_file()
    finally:
        discard_rehydrated_pack(restored)

    def null_digest_loader(*args, **kwargs):
        document = original_loader(*args, **kwargs)
        if document.get("kind") == "timeline_visualize_project":
            document = dict(document)
            document["outputs"] = [dict(row) for row in document["outputs"]]
            document["outputs"][0]["manifest_sha256"] = None
        return document

    monkeypatch.setattr(frozen_module, "_load_json_file", null_digest_loader)
    with pytest.raises(FrozenSchemaError, match="invalid child manifest path"):
        rehydrate_managed_pack(Path(result.manifest_path or ""), project_root=project_root)


def test_project_index_rejects_duplicate_timeline_ids(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slug = "timeline-visualize-duplicate-project-index"
    project_root, first = _prepare_project(tmp_projects_root, slug, second_timeline=True)
    second = project_root / "timelines" / SECOND_TIMELINE_ULID
    result = _invoke(slug, timeline_source=[str(first), str(second)])
    assert result.ok is True, result.error
    original_loader = frozen_module._load_json_file

    def duplicate_loader(*args, **kwargs):
        document = original_loader(*args, **kwargs)
        if document.get("kind") == "timeline_visualize_project":
            document = dict(document)
            document["timeline_ids"] = [document["timeline_ids"][0]] * 2
        return document

    monkeypatch.setattr(frozen_module, "_load_json_file", duplicate_loader)
    with pytest.raises(FrozenSchemaError, match="invalid project index"):
        rehydrate_managed_pack(Path(result.manifest_path or ""), project_root=project_root)


def _rewrite_registry_event(
    timeline_dir: Path,
    mutate,
) -> None:
    """Mutate the newest asset_registry_replaced EVENT (the snapshot
    authority) and recompute the event hash chain so the frozen snapshot
    stays clean (no chain diagnostics)."""
    from astrid.core.timeline.events.schema.serialize import with_event_hash
    from astrid.core.timeline.events.schema.types import TimelineEvent

    events_path = timeline_dir / "assembly.jsonl"
    raw = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    last_idx = max(
        index
        for index, event in enumerate(raw)
        if event.get("kind") == "timeline.asset_registry_replaced"
    )
    item = dict(raw[last_idx])
    payload = dict(item["payload"])
    registry = dict(payload["registry"])
    assets = dict(registry["assets"])
    mutate(assets)
    registry["assets"] = assets
    payload["registry"] = registry
    item["payload"] = payload
    raw[last_idx] = item

    previous_hash: str | None = None
    for event_dict in raw:
        event = TimelineEvent.from_dict(event_dict)
        updated = with_event_hash(event, prev_hash=previous_hash)
        event_dict["prev_hash"] = updated.prev_hash
        event_dict["hash"] = updated.hash
        previous_hash = updated.hash
    events_path.write_text(
        "\n".join(json.dumps(event, sort_keys=True, separators=(",", ":")) for event in raw) + "\n",
        encoding="utf-8",
    )


def _register_rendered_sample(
    timeline_dir: Path,
    project_root: Path,
    *,
    ffmpeg: str,
) -> Path:
    """Render a real output video under sources and register it as
    rendered_sample in the newest registry EVENT (the snapshot authority)."""
    sources = project_root / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    rendered = sources / "rendered-output.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=64x36:rate=10",
            "-pix_fmt",
            "yuv420p",
            str(rendered),
        ],
        capture_output=True,
        check=True,
    )
    digest = hashlib.sha256(rendered.read_bytes()).hexdigest()

    def _add(assets: dict) -> None:
        assets["rendered-output"] = {
            "file": "rendered-output.mp4",
            "content_sha256": digest,
            "role": "rendered_sample",
        }

    _rewrite_registry_event(timeline_dir, _add)
    return rendered


def test_rendered_video_mode_verifies_then_samples(tmp_projects_root: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg not installed")
    slug = "timeline-visualize-rendered"
    project_root, timeline_dir = _prepare_project(tmp_projects_root, slug)

    rendered = _register_rendered_sample(timeline_dir, project_root, ffmpeg=ffmpeg)

    result = _invoke(
        slug,
        timeline_source=str(timeline_dir),
        filmstrip="rendered",
        rendered_video=str(rendered),
    )
    assert result.ok is True
    pack_root = Path(result.outputs["pack_root"])
    frames = sorted((pack_root / "filmstrip").glob("PG0*_film_*.png"))
    assert frames, "rendered mode must sample frames from the verified output"
    # Per-page hard cap: each page's strip carries at most 12 frames.
    for page_id in ("PG001", "PG002"):
        page_frames = [frame for frame in frames if frame.name.startswith(f"{page_id}_film_")]
        assert len(page_frames) <= 12, f"{page_id} exceeds the per-page frame budget"
    # The rendered strip is present in the declared reading order and hashed.
    manifest = json.loads((pack_root / "manifest.json").read_text(encoding="utf-8"))
    assert any("filmstrip/" in record["path"] for record in manifest["outputs"])


def test_rendered_video_mode_refuses_unverified_output(tmp_projects_root: Path) -> None:
    slug = "timeline-visualize-rendered-refused"
    project_root, timeline_dir = _prepare_project(tmp_projects_root, slug)
    # A rendered file with NO registry record: hash_unrecorded -> refused.
    unregistered = project_root / "sources" / "unregistered.mp4"
    unregistered.parent.mkdir(parents=True, exist_ok=True)
    unregistered.write_bytes(b"rendered bytes with no provenance record")

    result = _invoke(
        slug,
        timeline_source=str(timeline_dir),
        filmstrip="rendered",
        rendered_video=str(unregistered),
        execution_mode="subprocess",
    )
    assert result.ok is False
    assert result.run_root is None
    assert result.error is not None
    assert "rendered filmstrip refused: hash_unrecorded" in result.error["message"]


def test_multi_asset_scope_respects_per_page_frame_budget(tmp_projects_root: Path) -> None:
    slug = "timeline-visualize-budget"
    project_root, timeline_dir = _prepare_project(tmp_projects_root, slug)
    # Write real contained media so every asset verifies and can be sampled
    # (images must be decodable PNGs; the audio asset is never opened).
    import io

    from PIL import Image

    registry = json.loads((timeline_dir / "registry.json").read_text(encoding="utf-8"))
    hashes: dict[str, str] = {}
    for key, entry in registry["assets"].items():
        payload: bytes
        if entry["file"].endswith(".mp3"):
            payload = b"fake audio bytes (never opened: audio filmstrips are empty)"
        else:
            buffer = io.BytesIO()
            Image.new("RGB", (4, 4), (10, 20, 30)).save(buffer, format="PNG")
            payload = buffer.getvalue()
        target = project_root / "sources" / entry["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        hashes[key] = hashlib.sha256(payload).hexdigest()

    # The snapshot's registry comes from the newest registry EVENT, so record
    # the real hashes there (registry.json is the bridge's persisted copy).
    def _align_hashes(assets: dict) -> None:
        for key, digest in hashes.items():
            if "content_sha256" in assets[key]:
                assets[key]["content_sha256"] = digest

    _rewrite_registry_event(timeline_dir, _align_hashes)
    (timeline_dir / "registry.json").write_text(
        json.dumps(registry, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    result = _invoke(slug, timeline_source=str(timeline_dir), filmstrip="assets")
    assert result.ok is True
    pack_root = Path(result.outputs["pack_root"])
    view_map = json.loads((pack_root / "view-map.json").read_text(encoding="utf-8"))
    filmstrip_dir = pack_root / "filmstrip"
    assert filmstrip_dir.is_dir()
    # Filmstrips are keyed per page (copied stem = "{page_id}_{asset_ref}"),
    # so a page's total frames are the files whose name starts with the page id.
    total_frames = 0
    for page in view_map["pages"]:
        frame_count = len(list(filmstrip_dir.glob(f"{page['page_id']}_*_film_*.png")))
        assert frame_count <= 12, f"{page['page_id']} exceeds the per-page frame budget"
        total_frames += frame_count
    # The desert slice has four verified image assets on the visual page —
    # the assertion must be non-vacuous.
    assert total_frames > 0
    pages = [Path(path) for path in result.outputs["pages"]]
    assert {path.name for path in pages} == {"PG001.png", "PG002.png"}
    assert all(path.parent == pack_root for path in pages)
