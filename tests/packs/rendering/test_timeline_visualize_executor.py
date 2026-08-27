"""R14 acceptance: packaged executor, SDK identity, and evidence retention."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest
import yaml

import astrid
from astrid.core.execution.executor.registry import load_default_registry
from astrid.core.execution.executor.schema import load_executor_manifest
from astrid.core.foundation.project_paths import project_dir
from astrid.core.project.project import create_project

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


def _kernel_run_state(projects_root: Path, run_id: str) -> dict[str, object]:
    """Read the authoritative run/task projection without a run.json sidecar."""

    database = projects_root / ".astrid" / "astrid.sqlite3"
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        run = connection.execute(
            "SELECT r.id, r.kind, r.title, r.status, p.slug AS project_slug "
            "FROM runs r JOIN projects p ON p.id = r.project_id "
            "WHERE r.id = ?",
            (run_id,),
        ).fetchone()
        tasks = connection.execute(
            "SELECT id, status, winning_attempt_id FROM tasks "
            "WHERE run_id = ? ORDER BY run_ordinal",
            (run_id,),
        ).fetchall()
        output_count = connection.execute(
            "SELECT COUNT(*) FROM task_outputs o "
            "JOIN tasks t ON t.id = o.task_id WHERE t.run_id = ?",
            (run_id,),
        ).fetchone()[0]
    assert run is not None
    return {
        **dict(run),
        "tasks": [dict(task) for task in tasks],
        "output_count": int(output_count),
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
    assert manifest_path.is_file()
    assert pack_root.is_relative_to(
        project_root / ".astrid" / "views" / "timeline_visualize"
    )
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

    state = _kernel_run_state(tmp_projects_root, first.run_id)
    assert state["project_slug"] == slug
    assert state["kind"] == "executor"
    assert state["title"] == "rendering.timeline_visualize"
    assert state["status"] == "succeeded"
    assert state["output_count"] >= 1
    assert len(state["tasks"]) == 1
    assert state["tasks"][0]["status"] == "succeeded"
    assert state["tasks"][0]["winning_attempt_id"] == first.kernel_attempt_id
    assert [
        row["ulid"] for row in manifest["inputs"]["resolved_timelines"]
    ] == [TIMELINE_ULID]
    assert first.raw_result["executor_version"] == first.executor_version
    assert not (project_root / "runs" / first.run_id).exists()
    assert (timeline_dir / "manifest.json").read_bytes() == sentinel


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
    assert result.run_id is not None
    assert _kernel_run_state(tmp_projects_root, result.run_id)["status"] == "succeeded"
    assert result.run_root is None


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


def test_two_managed_runs_emit_identical_pack_bytes(
    tmp_projects_root: Path,
) -> None:
    slug = "timeline-visualize-deterministic"
    _project_root, timeline_dir = _prepare_project(tmp_projects_root, slug)

    first = _invoke(slug, timeline_source=str(timeline_dir))
    second = _invoke(slug, timeline_source=str(timeline_dir))

    assert first.ok is second.ok is True
    assert first.run_id == second.run_id
    assert first.kernel_task_id == second.kernel_task_id
    assert first.kernel_attempt_id == second.kernel_attempt_id
    first_pack = Path(first.outputs["pack_root"])
    second_pack = Path(second.outputs["pack_root"])
    assert _pack_bytes(first_pack) == _pack_bytes(second_pack)


def test_multi_timeline_selection_writes_sorted_kernel_owned_metadata(
    tmp_projects_root: Path,
) -> None:
    slug = "timeline-visualize-all"
    project_root, first_timeline = _prepare_project(
        tmp_projects_root,
        slug,
        second_timeline=True,
    )
    second_timeline = project_root / "timelines" / SECOND_TIMELINE_ULID

    result = _invoke(
        slug,
        timeline_source=[str(first_timeline), str(second_timeline)],
    )

    assert result.ok is True
    assert result.run_id is not None
    state = _kernel_run_state(tmp_projects_root, result.run_id)
    assert state["status"] == "succeeded"
    assert state["tasks"][0]["status"] == "succeeded"
    expected_timeline_ids = sorted([SECOND_TIMELINE_ULID, TIMELINE_ULID])
    manifest = json.loads(Path(result.manifest_path or "").read_text(encoding="utf-8"))
    assert manifest["kind"] == "timeline_visualize_project"
    assert manifest["timeline_ids"] == expected_timeline_ids
    assert manifest["reading_order"] == ["TL01/manifest.json", "TL02/manifest.json"]
    assert all(
        (Path(result.outputs["pack_root"]) / item).is_file() for item in manifest["reading_order"]
    )


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
    assert "rendered filmstrip refused: hash_unrecorded" in json.dumps(result.error)
    assert result.run_id is not None
    assert _kernel_run_state(tmp_projects_root, result.run_id)["status"] == "failed"


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
    asset_index = json.loads((pack_root / "asset-index.json").read_text(encoding="utf-8"))
    asset_refs = {asset["qualified_ref"] for asset in asset_index["assets"]}
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
