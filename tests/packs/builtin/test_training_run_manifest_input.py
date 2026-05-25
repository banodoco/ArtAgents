"""Training-run manifest input normalization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import jsonschema

from astrid.packs.training.orchestrators.dataset_build.manifest import validate_schema
from astrid.packs.training.orchestrators.training_run.manifest_input import (
    TrainingManifestError,
    normalize_ai_toolkit_manifest,
    seed_from_dataset_run,
)


def _clip(root: Path, clip_id: str = "clip-a") -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    clip = root / f"{clip_id}.mp4"
    caption = root / f"{clip_id}.caption.json"
    clip.write_bytes(b"mp4")
    caption.write_text(json.dumps({"text": "caption"}) + "\n", encoding="utf-8")
    return clip, caption


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_canonical_manifest_uses_ai_toolkit_adapter_and_manifest_dir_relative_paths(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    _clip(dataset, "clip-a")
    canonical = _write_json(
        dataset / "final.manifest.json",
        {
            "items": [
                {
                    "item_id": "clip-a",
                    "media_path": "clip-a.mp4",
                    "caption_file": "clip-a.caption.json",
                    "source_url": "file://clip-a",
                    "content_hash": "0" * 64,
                    "rights": {"rights_status": "verified"},
                    "bucket": "wide",
                    "duration_s": 1.0,
                }
            ],
            "created_at": "2026-05-22T00:00:00Z",
        },
    )

    result = normalize_ai_toolkit_manifest(canonical, tmp_path / "training-run", repo_root=tmp_path)
    payload = json.loads(result.normalized_manifest_path.read_text(encoding="utf-8"))

    assert result.source_format == "canonical-final"
    assert payload["clips"][0]["clip_file"] == "dataset/clip-a.mp4"
    assert payload["clips"][0]["caption_file"] == "dataset/clip-a.caption.json"
    assert payload["source_manifest"] == "dataset/final.manifest.json"
    validate_schema(payload, "ai-toolkit-adapter-manifest.schema.json")


def test_flat_manifest_accepts_dataset_builder_path_and_repo_root_relative_files(tmp_path: Path) -> None:
    clip, caption = _clip(tmp_path / "clips", "clip-b")
    dataset_run = tmp_path / "dataset-run"
    manifest = _write_json(
        dataset_run / "ai-toolkit-ltx.manifest.json",
        {
            "clips": [
                {
                    "clip_id": "clip-b",
                    "clip_file": "clips/clip-b.mp4",
                    "caption_file": "clips/clip-b.caption.json",
                    "rights_status": "unknown",
                }
            ]
        },
    )

    result = seed_from_dataset_run(dataset_run, tmp_path / "training-run", repo_root=tmp_path)
    payload = json.loads(result.normalized_manifest_path.read_text(encoding="utf-8"))

    assert manifest == result.source_manifest_path
    assert payload["clips"][0]["clip_file"] == "clips/clip-b.mp4"
    assert payload["clips"][0]["caption_file"] == "clips/clip-b.caption.json"
    validate_schema(payload, "ai-toolkit-adapter-manifest.schema.json")


def test_flat_manifest_accepts_manifest_dir_relative_files_and_explicit_captions(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "manifests"
    _clip(manifest_dir / "media", "clip-c")
    manifest = _write_json(
        manifest_dir / "flat.json",
        {
            "clips": [
                {
                    "clip_id": "clip-c",
                    "clip_file": "media/clip-c.mp4",
                    "caption_file": "media/clip-c.caption.json",
                }
            ]
        },
    )

    result = normalize_ai_toolkit_manifest(manifest, tmp_path / "training-run", repo_root=tmp_path / "repo")
    payload = json.loads(result.normalized_manifest_path.read_text(encoding="utf-8"))

    assert payload["clips"][0]["clip_file"] == str(manifest_dir / "media" / "clip-c.mp4")
    assert payload["clips"][0]["caption_file"] == str(manifest_dir / "media" / "clip-c.caption.json")
    validate_schema(payload, "ai-toolkit-adapter-manifest.schema.json")


def test_flat_manifest_infers_existing_caption_sidecars_for_seinfeld_compatible_callers(tmp_path: Path) -> None:
    clip, caption = _clip(tmp_path / "clips", "clip-d")
    manifest = _write_json(
        tmp_path / "flat.json",
        {"clips": [{"clip_id": "clip-d", "clip_file": str(clip)}]},
    )

    result = normalize_ai_toolkit_manifest(manifest, tmp_path / "training-run")
    payload = json.loads(result.normalized_manifest_path.read_text(encoding="utf-8"))

    assert payload["clips"][0]["caption_file"] == str(caption)


def test_flat_manifest_validates_schema_and_fails_on_missing_files_before_provisioning(tmp_path: Path) -> None:
    clip, _caption = _clip(tmp_path / "clips", "clip-e")
    bad_schema = _write_json(
        tmp_path / "bad-schema.json",
        {"clips": [{"clip_id": "clip-e", "clip_file": str(clip), "unexpected": "nope"}]},
    )
    with pytest.raises(jsonschema.ValidationError):
        normalize_ai_toolkit_manifest(bad_schema, tmp_path / "training-run")

    missing_caption = _write_json(
        tmp_path / "missing-caption.json",
        {"clips": [{"clip_id": "clip-missing", "clip_file": str(clip)}]},
    )
    with pytest.raises(TrainingManifestError, match="inferred caption sidecar missing"):
        normalize_ai_toolkit_manifest(missing_caption, tmp_path / "training-run")

    missing_clip = _write_json(
        tmp_path / "missing-clip.json",
        {"clips": [{"clip_id": "clip-x", "clip_file": "clips/nope.mp4", "caption_file": str(tmp_path / "x.caption.json")}]},
    )
    with pytest.raises(TrainingManifestError, match="clip_file missing"):
        normalize_ai_toolkit_manifest(missing_clip, tmp_path / "training-run")
